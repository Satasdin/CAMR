import Foundation

public struct IndexReport: Sendable, Equatable {
    public var filesSeen = 0
    public var filesChanged = 0
    public var filesRemoved = 0
    public var chunks = 0
    public var links = 0
    public var embedded = 0
}

public struct VaultStats: Sendable {
    public let files: Int
    public let notes: Int
    public let chunks: Int
    public let links: Int
    public let clusters: Int
    public let vectors: Int
    public let indexBytes: Int
}

public enum NoteKind: String, CaseIterable, Sendable {
    case decision, rejected, bug, convention, note
}

/// One project's memory. The code and the Markdown notes are the truth; `index.sqlite` is built from them
/// and can be deleted at any time.
public final class Vault {
    public let root: URL
    public let store: URL
    /// True for a vault of everything, where every Markdown file is a note. False for one project with notes kept beside it.
    public let everything: Bool
    public var notesFolder: URL { everything ? root.appendingPathComponent("Memory") : store.appendingPathComponent("notes") }
    let database: Database

    /// Raised when files must be cut into pieces differently, so an existing index rebuilds itself.
    private static let indexVersion = 3

    private static let schema = """
    CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, is_note INTEGER NOT NULL, cluster TEXT NOT NULL, hash TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE, start_line INTEGER NOT NULL, end_line INTEGER NOT NULL, body TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS chunks_file ON chunks(file_id);
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(path, body, tokenize="unicode61 tokenchars '_'");
    CREATE TABLE IF NOT EXISTS vectors(chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE, vector BLOB NOT NULL);
    CREATE TABLE IF NOT EXISTS links(source TEXT NOT NULL, target TEXT NOT NULL, kind TEXT NOT NULL, via TEXT, PRIMARY KEY(source, target, kind));
    CREATE INDEX IF NOT EXISTS links_target ON links(target);
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value INTEGER NOT NULL);
    """

    /// - Parameter store: where the memory lives. Defaults to `.burrow` inside the project.
    public init(project root: URL, store: URL? = nil, everything: Bool = false) throws {
        self.root = root.standardizedFileURL
        self.store = (store ?? root.appendingPathComponent(".burrow")).standardizedFileURL
        self.everything = everything
        let files = FileManager.default
        try files.createDirectory(at: self.store, withIntermediateDirectories: true)
        if !everything { try files.createDirectory(at: self.store.appendingPathComponent("notes"), withIntermediateDirectories: true) }
        database = try Database(path: self.store.appendingPathComponent("index.sqlite").path)
        try database.execute(Self.schema)
        // Indexes from before version 3 have no section column. Adding it empty is enough: the version bump re-indexes every file.
        if try !database.rows("PRAGMA table_info(chunks)").contains(where: { $0[1].text == "section" }) {
            try database.execute("ALTER TABLE chunks ADD COLUMN section TEXT NOT NULL DEFAULT ''")
        }
    }

    // MARK: Building the index

    /// Brings the index up to date with the files, touching only what changed.
    @discardableResult
    public func refresh(embedder: Embedder? = nil, onProgress: ((String) -> Void)? = nil) async throws -> IndexReport {
        var report = IndexReport()
        var found: [String: Scanner.Found] = [:]
        var notes = Set<String>()
        for path in Scanner.paths(in: root) {
            guard let file = Scanner.read(path, in: root) else { continue }
            found[path] = file
            if everything, Vault.isMarkdown(path) { notes.insert(path) }
        }
        for folder in linkedFolders() {
            for path in Scanner.paths(in: folder.url) {
                guard let file = Scanner.read(path, in: folder.url) else { continue }
                let shown = folder.name + "/" + path
                found[shown] = Scanner.Found(path: shown, text: file.text, hash: file.hash)
            }
        }
        if !everything {
            for note in noteFiles() {
                let path = notePath(note)
                if let data = try? Data(contentsOf: note), let text = String(data: data, encoding: .utf8) {
                    found[path] = Scanner.Found(path: path, text: text, hash: Scanner.digest(data))
                    notes.insert(path)
                }
            }
        }
        report.filesSeen = found.count

        var known: [String: String] = [:]
        for row in try database.rows("SELECT path, hash FROM files") { known[row[0].text!] = row[1].text! }
        let outOfDate = try database.rows("PRAGMA user_version").first?[0].int != Self.indexVersion

        try database.transaction {
            for path in known.keys where found[path] == nil {
                try remove(path)
                report.filesRemoved += 1
            }
            for path in found.keys.sorted() where outOfDate || known[path] != found[path]!.hash {
                if known[path] != nil { try remove(path) }
                try insert(found[path]!, isNote: notes.contains(path))
                report.filesChanged += 1
            }
            if outOfDate { try database.execute("PRAGMA user_version = \(Self.indexVersion)") }
            let texts = found.mapValues(\.text)
            let links = LinkFinder.links(files: texts, notes: notes)
            try database.run("DELETE FROM links")
            for link in links {
                try database.run("INSERT INTO links(source, target, kind, via) VALUES(?,?,?,?)",
                                 [.text(link.from), .text(link.to), .text(link.kind.rawValue), link.via.map(Value.text) ?? .null])
            }
            report.links = links.count
            if outOfDate || report.filesChanged + report.filesRemoved > 0 { try bumpGeneration() }
        }
        database.locked { forgetCaches() }
        if let embedder { report.embedded = try await embedMissing(embedder, onProgress: onProgress) }
        report.chunks = try count("chunks")
        return report
    }

    private func remove(_ path: String) throws {
        let ids = try database.rows("SELECT c.id FROM chunks c JOIN files f ON f.id = c.file_id WHERE f.path = ?", [.text(path)])
        for row in ids { try database.run("DELETE FROM chunks_fts WHERE rowid = ?", [row[0]]) }
        try database.run("DELETE FROM files WHERE path = ?", [.text(path)])
    }

    private func insert(_ file: Scanner.Found, isNote: Bool) throws {
        try database.run("INSERT INTO files(path, is_note, cluster, hash) VALUES(?,?,?,?)",
                         [.text(file.path), .int(isNote ? 1 : 0), .text(isNote && !everything ? "notes" : clusterName(of: file.path)), .text(file.hash)])
        let fileID = database.lastInsertedRow
        let pieces = Vault.readsAsDocument(file.path) ? Chunker.markdownChunks(of: file.text) : Chunker.chunks(of: file.text)
        for chunk in pieces {
            try database.run("INSERT INTO chunks(file_id, start_line, end_line, body, section) VALUES(?,?,?,?,?)",
                             [.int(Int64(fileID)), .int(Int64(chunk.startLine)), .int(Int64(chunk.endLine)), .text(chunk.text), .text(chunk.section)])
            let chunkID = database.lastInsertedRow
            // The heading path is searched with the body, so a clause is found by the heading that names it.
            try database.run("INSERT INTO chunks_fts(rowid, path, body) VALUES(?,?,?)",
                             [.int(Int64(chunkID)), .text(Words.expanded(file.path.replacingOccurrences(of: "/", with: " "))),
                              .text(Words.expanded(chunk.section.isEmpty ? chunk.text : chunk.section + "\n" + chunk.text))])
        }
    }

    private func embedMissing(_ embedder: Embedder, onProgress: ((String) -> Void)?) async throws -> Int {
        let missing = try database.rows("""
            SELECT c.id, f.path, c.body, c.section FROM chunks c JOIN files f ON f.id = c.file_id
            WHERE c.id NOT IN (SELECT chunk_id FROM vectors) ORDER BY c.id
            """)
        var done = 0
        var start = 0
        while start < missing.count {
            let batch = Array(missing[start..<min(start + 32, missing.count)])
            // The path goes first because it often says more about a chunk than its first lines do.
            let vectors = try await embedder.embed(batch.map { row -> String in
                let section = row[3].text ?? ""
                return "\(row[1].text!)\n\(section.isEmpty ? "" : section + "\n")\(String(row[2].text!.prefix(1500)))"
            })
            try database.transaction {
                for (row, vector) in zip(batch, vectors) {
                    try database.run("INSERT OR REPLACE INTO vectors(chunk_id, vector) VALUES(?,?)", [row[0], .blob(Self.pack(vector))])
                }
            }
            done += batch.count
            start += batch.count
            onProgress?("embedded \(done) of \(missing.count)")
        }
        if done > 0 { try bumpGeneration() }
        database.locked { forgetCaches() }
        return done
    }

    // MARK: Vectors

    // What is held in memory between questions. See Index.swift.
    var catalogueCache: Catalogue?
    var vectorIndexCache: VectorIndex?
    var seenDataVersion = -1
    var questionVectors: [String: [Float]] = [:]
    var skillVectorCache: [String: [Float]] = [:]

    static func pack(_ vector: [Float]) -> Data { vector.withUnsafeBufferPointer { Data(buffer: $0) } }
    static func unpack(_ data: Data) -> [Float] {
        data.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
    }

    // MARK: Notes

    private func noteFiles() -> [URL] {
        let found = (try? FileManager.default.contentsOfDirectory(at: notesFolder, includingPropertiesForKeys: nil)) ?? []
        return found.filter { $0.pathExtension == "md" }.sorted { $0.path < $1.path }
    }

    func notePath(_ note: URL) -> String {
        everything ? String(note.standardizedFileURL.path.dropFirst(root.path.count + 1)) : "notes/" + note.lastPathComponent
    }

    static func isMarkdown(_ path: String) -> Bool { ["md", "markdown"].contains((path as NSString).pathExtension.lowercased()) }
    /// Markdown notes and documents read into Markdown (PDF, Word, images): cut at headings and focused when shown.
    static func readsAsDocument(_ path: String) -> Bool { isMarkdown(path) || Extractor.handles(path) }

    /// Writes a Markdown note. Nothing about a note is hidden in the index: delete the file and it is gone.
    @discardableResult
    public func addNote(_ text: String, kind: NoteKind = .note, date: Date = Date()) throws -> String {
        let day = ISO8601DateFormatter.string(from: date, timeZone: .current, formatOptions: [.withFullDate])
        let words = Words.identifiers(in: text).prefix(6).joined(separator: "-").lowercased()
        if everything { try FileManager.default.createDirectory(at: notesFolder, withIntermediateDirectories: true) }
        let readable = text.split(whereSeparator: \.isWhitespace).prefix(7).joined(separator: " ")
            .components(separatedBy: CharacterSet(charactersIn: "/:\\#[]|^.")).joined(separator: " ").trimmingCharacters(in: .whitespaces)
        let start = everything ? "\(kind.rawValue.capitalized) - \(readable.isEmpty ? day : readable)" : "\(day)-\(kind.rawValue)-\(words.isEmpty ? "note" : words)"
        var name = start
        var attempt = 2
        while FileManager.default.fileExists(atPath: notesFolder.appendingPathComponent(name + ".md").path) {
            name = everything ? "\(start) \(attempt)" : "\(day)-\(kind.rawValue)-\(words)-\(attempt)"
            attempt += 1
        }
        let body = "---\nkind: \(kind.rawValue)\ndate: \(day)\n---\n\n\(text)\n"
        let url = notesFolder.appendingPathComponent(name + ".md")
        try body.write(to: url, atomically: true, encoding: .utf8)
        return notePath(url)
    }

    // MARK: Reading

    func count(_ table: String) throws -> Int { try database.rows("SELECT count(*) FROM \(table)")[0][0].int ?? 0 }

    public func stats() throws -> VaultStats {
        let notes = try database.rows("SELECT count(*) FROM files WHERE is_note = 1")[0][0].int ?? 0
        let clusters = try database.rows("SELECT count(DISTINCT cluster) FROM files")[0][0].int ?? 0
        var bytes = 0
        for suffix in ["", "-wal", "-shm"] {
            let path = store.appendingPathComponent("index.sqlite" + suffix).path
            bytes += (try? FileManager.default.attributesOfItem(atPath: path)[.size] as? Int) ?? 0
        }
        return VaultStats(files: try count("files") - notes, notes: notes, chunks: try count("chunks"), links: try count("links"),
                          clusters: clusters, vectors: try count("vectors"), indexBytes: bytes)
    }

    public struct Neighbour: Sendable, Equatable {
        public let path: String
        public let kind: LinkKind
        public let via: String?
        public let forward: Bool  // true when this file points at the neighbour
    }

    /// Everything one link away, in either direction.
    public func neighbours(of path: String) throws -> [Neighbour] {
        var out: [Neighbour] = []
        for row in try database.rows("SELECT target, kind, via FROM links WHERE source = ? ORDER BY target", [.text(path)]) {
            out.append(Neighbour(path: row[0].text!, kind: LinkKind(rawValue: row[1].text!)!, via: row[2].text, forward: true))
        }
        for row in try database.rows("SELECT source, kind, via FROM links WHERE target = ? ORDER BY source", [.text(path)]) {
            out.append(Neighbour(path: row[0].text!, kind: LinkKind(rawValue: row[1].text!)!, via: row[2].text, forward: false))
        }
        return out
    }
}
