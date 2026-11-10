import Accelerate
import Foundation

/// Which file each piece belongs to, held in memory so a question does not re-read it from disk.
struct Catalogue {
    var fileOf: [Int: (path: String, isNote: Bool)] = [:]
    /// The pieces of each file in reading order.
    var chunksOf: [String: [Int]] = [:]
}

/// Every stored vector as one block of numbers, each row scaled to length 1, so comparing a question with
/// the whole vault is a single matrix multiplication. The block is a file mapped into memory: opening a vault
/// costs nothing until a row is read, and a second process shares the same pages.
struct VectorIndex {
    static let magic: UInt32 = 0x5657_5242  // "BRWV"
    static let version: UInt32 = 1
    static let headerBytes = 32

    let ids: [Int]
    let dimension: Int
    private let storage: Data
    private let offset: Int

    var isEmpty: Bool { ids.isEmpty }

    /// Builds the block from raw vectors. Rows of another width, or of length zero, cannot be compared and are left out.
    static func encode(ids: [Int], vectors: [[Float]], generation: Int) -> Data {
        let dimension = vectors.first?.count ?? 0
        var keptIDs: [Int64] = []
        var rows: [Float] = []
        rows.reserveCapacity(vectors.count * dimension)
        for (id, vector) in zip(ids, vectors) where vector.count == dimension && dimension > 0 {
            var length: Float = 0
            vDSP_svesq(vector, 1, &length, vDSP_Length(dimension))
            guard length > 0 else { continue }
            var scale = 1 / sqrt(length)
            var unit = [Float](repeating: 0, count: dimension)
            vDSP_vsmul(vector, 1, &scale, &unit, 1, vDSP_Length(dimension))
            keptIDs.append(Int64(id))
            rows.append(contentsOf: unit)
        }
        var data = Data(capacity: headerBytes + keptIDs.count * 8 + rows.count * 4)
        func append<T>(_ value: T) { withUnsafeBytes(of: value) { data.append(contentsOf: $0) } }
        append(magic)
        append(version)
        append(Int64(generation))
        append(Int64(keptIDs.count))
        append(Int64(dimension))
        keptIDs.withUnsafeBufferPointer { data.append(Data(buffer: $0)) }
        rows.withUnsafeBufferPointer { data.append(Data(buffer: $0)) }
        return data
    }

    /// Reads a block, or returns nil if it is damaged or was written for another state of the vault.
    init?(_ data: Data, generation: Int) {
        guard data.count >= Self.headerBytes else { return nil }
        func read<T>(_ type: T.Type, at position: Int) -> T { data.withUnsafeBytes { $0.loadUnaligned(fromByteOffset: position, as: type) } }
        guard read(UInt32.self, at: 0) == Self.magic, read(UInt32.self, at: 4) == Self.version,
              read(Int64.self, at: 8) == Int64(generation) else { return nil }
        let count = Int(read(Int64.self, at: 16))
        let dimension = Int(read(Int64.self, at: 24))
        guard count >= 0, dimension >= 0, data.count == Self.headerBytes + count * 8 + count * dimension * 4 else { return nil }
        ids = data.withUnsafeBytes { raw in
            (0..<count).map { Int(raw.loadUnaligned(fromByteOffset: Self.headerBytes + $0 * 8, as: Int64.self)) }
        }
        self.dimension = dimension
        storage = data
        offset = Self.headerBytes + count * 8
    }

    /// The ids of the closest pieces, closest first. Ties go to the lower id so the order never depends on chance.
    func nearest(to query: [Float], limit: Int) -> [Int] {
        guard !ids.isEmpty, query.count == dimension, limit > 0 else { return [] }
        var length: Float = 0
        vDSP_svesq(query, 1, &length, vDSP_Length(dimension))
        guard length > 0 else { return [] }
        var scores = [Float](repeating: 0, count: ids.count)
        storage.withUnsafeBytes { raw in
            let rows = (raw.baseAddress! + offset).assumingMemoryBound(to: Float.self)
            vDSP_mmul(rows, 1, query, 1, &scores, 1, vDSP_Length(ids.count), 1, vDSP_Length(dimension))
        }
        var order = Array(0..<ids.count)
        let wanted = min(limit, order.count)
        // Only the front of the ranking is used, so only the front is put in order.
        if wanted * 8 < order.count {
            var threshold = scores
            threshold.withUnsafeMutableBufferPointer { buffer in
                vDSP_vsort(buffer.baseAddress!, vDSP_Length(buffer.count), -1)
            }
            let cut = threshold[wanted - 1]
            order = order.filter { scores[$0] >= cut }
        }
        order.sort { scores[$0] == scores[$1] ? ids[$0] < ids[$1] : scores[$0] > scores[$1] }
        return order.prefix(wanted).map { ids[$0] }
    }

    /// How close one stored piece is to the question, from -1 to 1, or nil if it has no vector.
    func similarity(of id: Int, to query: [Float]) -> Float? {
        guard query.count == dimension, let row = ids.firstIndex(of: id) else { return nil }
        var length: Float = 0
        vDSP_svesq(query, 1, &length, vDSP_Length(dimension))
        guard length > 0 else { return nil }
        var dot: Float = 0
        storage.withUnsafeBytes { raw in
            let start = (raw.baseAddress! + offset + row * dimension * 4).assumingMemoryBound(to: Float.self)
            vDSP_dotpr(start, 1, query, 1, &dot, vDSP_Length(dimension))
        }
        return dot / sqrt(length)
    }
}

extension Vault {
    private var vectorFile: URL { store.appendingPathComponent("vectors.bin") }

    /// Counts every change to the pieces or their vectors, so a saved block can tell whether it is still current.
    func generation() throws -> Int {
        try database.rows("SELECT value FROM meta WHERE key = 'generation'").first?[0].int ?? 0
    }

    func bumpGeneration() throws {
        try database.run("INSERT INTO meta(key, value) VALUES('generation', 1) ON CONFLICT(key) DO UPDATE SET value = value + 1")
    }

    /// Drops what is held in memory if another program has written to this vault since it was read.
    private func forgetIfChangedElsewhere() throws {
        let version = try database.rows("PRAGMA data_version").first?[0].int ?? 0
        if version != seenDataVersion {
            seenDataVersion = version
            forgetCaches()
        }
    }

    func forgetCaches() {
        catalogueCache = nil
        vectorIndexCache = nil
        questionVectors = [:]
    }

    func catalogue() throws -> Catalogue {
        try database.locked {
            try forgetIfChangedElsewhere()
            if let catalogueCache { return catalogueCache }
            var built = Catalogue()
            for row in try database.rows("""
                SELECT c.id, f.path, f.is_note FROM chunks c JOIN files f ON f.id = c.file_id ORDER BY f.path, c.start_line
                """) {
                let id = row[0].int!, path = row[1].text!
                built.fileOf[id] = (path, row[2].int == 1)
                built.chunksOf[path, default: []].append(id)
            }
            catalogueCache = built
            return built
        }
    }

    func vectorIndex() throws -> VectorIndex {
        try database.locked {
            try forgetIfChangedElsewhere()
            if let vectorIndexCache { return vectorIndexCache }
            let current = try generation()
            if let data = try? Data(contentsOf: vectorFile, options: .alwaysMapped), let saved = VectorIndex(data, generation: current) {
                vectorIndexCache = saved
                return saved
            }
            var ids: [Int] = []
            var vectors: [[Float]] = []
            for row in try database.rows("SELECT chunk_id, vector FROM vectors ORDER BY chunk_id") {
                ids.append(row[0].int!)
                vectors.append(Self.unpack(row[1].blob!))
            }
            let data = VectorIndex.encode(ids: ids, vectors: vectors, generation: current)
            // The file only saves time. If it cannot be written, the block in memory still answers.
            try? data.write(to: vectorFile, options: .atomic)
            let mapped = (try? Data(contentsOf: vectorFile, options: .alwaysMapped)) ?? data
            let built = VectorIndex(mapped, generation: current) ?? VectorIndex(data, generation: current)!
            vectorIndexCache = built
            return built
        }
    }

    /// The question as a vector. The same question asked twice is not sent to the embedding model twice.
    func questionVector(_ question: String, embedder: Embedder?) async throws -> [Float]? {
        guard let embedder else { return nil }
        if let known = database.locked({ questionVectors[question] }) { return known }
        guard let vector = try await embedder.embed([question]).first else { return nil }
        database.locked {
            if questionVectors.count >= 256 { questionVectors.removeAll(keepingCapacity: true) }
            questionVectors[question] = vector
        }
        return vector
    }
}
