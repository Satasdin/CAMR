import CryptoKit
import Foundation

/// Working memory a model has already built, kept on disk so it can be loaded instead of rebuilt.
///
/// Text is the format every model can read; a KV cache is the format one model can load. Reading a long document costs a
/// model its whole prefill, every time. Saving the KV cache once means the next time only the question is read. Burrow
/// keeps both: the text for any model, and each model's own cache, filed by the model and the exact files it was built
/// from, so a cache is never loaded into the wrong model or after its files changed.
///
/// The first server is llama.cpp, which saves and restores a slot's cache when started with `--slot-save-path` pointing
/// at this shelf's folder.
public struct KVShelf {
    public struct Entry: Codable, Sendable {
        public var key: String
        /// The model the cache belongs to, as the server reports it. A cache only fits the model that built it.
        public var model: String
        public var file: String
        /// Each source file's content hash when the cache was built.
        public var sources: [String: String]
        public var tokens: Int
        public var bytes: Int
        public var buildSeconds: Double
        public var created: Date
        // Added for packs (D-59). All optional, so a manifest written before them still reads, and a reader that
        // doesn't know them ignores them.
        /// The folder a pack covers, and which of its parts this is.
        public var scope: String? = nil
        public var part: Int? = nil
        public var parts: Int? = nil
        /// The entry this one was stacked on: its cache was loaded and only the rest was read.
        public var base: String? = nil
        /// "system" when the text was read as a system message through the model's chat template; nil for plain text.
        public var form: String? = nil
        /// Last loaded or built, for clearing the oldest when the shelf is over its limit.
        public var lastUsed: Date? = nil
    }

    public let folder: URL
    let vault: Vault

    public init(vault: Vault) {
        self.vault = vault
        folder = vault.store.appendingPathComponent("kv", isDirectory: true)
    }

    private var manifest: URL { folder.appendingPathComponent("shelf.json") }

    public func entries() -> [Entry] {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return (try? decoder.decode([Entry].self, from: Data(contentsOf: manifest))) ?? []
    }

    func write(_ entries: [Entry]) throws {
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        encoder.dateEncodingStrategy = .iso8601
        try encoder.encode(entries).write(to: manifest, options: .atomic)
    }

    /// The text a cache is built from: the files, in order, as excerpts. A client that sends exactly this, then its
    /// question, gets the saved cache; llama.cpp matches the shared start of the prompt token by token.
    public func prefix(for paths: [String]) throws -> String {
        var parts = ["The user's documents from their Burrow vault follow. Answer from them and name the file and line for each fact.\n"]
        for path in paths {
            guard let text = vault.text(of: path) else { throw KVProblem(description: "\(path) could not be read") }
            let numbered = text.components(separatedBy: "\n").enumerated().map { "\($0.offset + 1): \($0.element)" }.joined(separator: "\n")
            parts.append("<excerpt file=\"\(path)\">\n\(numbered)\n</excerpt>\n")
        }
        return parts.joined(separator: "\n") + "\n"
    }

    public static func key(for paths: [String]) -> String {
        let digest = SHA256.hash(data: Data(paths.joined(separator: "\n").utf8)).prefix(6).map { String(format: "%02x", $0) }.joined()
        let name = (paths.first.map { (($0 as NSString).lastPathComponent as NSString).deletingPathExtension } ?? "kv")
            .map { $0.isLetter || $0.isNumber ? $0 : "-" }
        return String(String(name).prefix(40)) + "-" + digest
    }

    func hashes(_ paths: [String]) -> [String: String] {
        var out: [String: String] = [:]
        for path in paths { out[path] = vault.text(of: path).map { Scanner.digest(Data($0.utf8)) } ?? "" }
        return out
    }

    /// Why an entry can't be used now, or nil when it can.
    public func stale(_ entry: Entry, model: String) -> String? {
        if entry.model != model { return "it was built by \(entry.model), and the server is running \(model)" }
        for (path, hash) in entry.sources where hashes([path])[path] != hash { return "\(path) has changed since" }
        if !FileManager.default.fileExists(atPath: folder.appendingPathComponent(entry.file).path) { return "its file is missing" }
        return nil
    }

    // MARK: llama.cpp

    public struct Timing: Sendable {
        public var promptTokens = 0
        public var promptSeconds = 0.0
        public var answer = ""
        public var answerSeconds = 0.0
    }

    /// Builds the cache for these files on a llama.cpp server and files it on the shelf.
    public func save(_ paths: [String], server: URL) async throws -> (Entry, Timing) {
        let model = try await LlamaServer(base: server).model()
        let key = Self.key(for: paths)
        let llama = LlamaServer(base: server)
        try await llama.erase()
        let built = try await llama.complete(prompt: try prefix(for: paths), predict: 0)
        let saved = try await llama.slot("save", file: key + ".bin")
        let bytes = (try? FileManager.default.attributesOfItem(atPath: folder.appendingPathComponent(key + ".bin").path)[.size] as? Int) ?? saved
        let entry = Entry(key: key, model: model, file: key + ".bin", sources: hashes(paths), tokens: built.promptTokens,
                          bytes: bytes, buildSeconds: built.promptSeconds, created: Date())
        try write(entries().filter { $0.key != key || $0.model != model } + [entry])
        return (entry, built)
    }

    /// Answers a question about the files, loading the saved cache when there is a fresh one for this model, or reading
    /// everything from the start when `cold` is set. Returns how long loading and reading took.
    public func ask(_ paths: [String], question: String, server: URL, cold: Bool, predict: Int = 200) async throws -> (loaded: Double, timing: Timing, used: Entry?) {
        let llama = LlamaServer(base: server)
        let model = try await llama.model()
        try await llama.erase()
        var loaded = 0.0
        var used: Entry?
        if !cold, let entry = entries().first(where: { $0.key == Self.key(for: paths) && $0.model == model }) {
            if let reason = stale(entry, model: model) { throw KVProblem(description: "the saved cache can't be used: \(reason). Save it again.") }
            let started = Date()
            _ = try await llama.slot("restore", file: entry.file)
            loaded = Date().timeIntervalSince(started)
            used = entry
        }
        let timing = try await llama.complete(prompt: try prefix(for: paths) + "Question: \(question)\nAnswer:", predict: predict)
        return (loaded, timing, used)
    }
}

public struct KVProblem: Error, CustomStringConvertible {
    public let description: String
}

/// The few llama.cpp server calls the shelf needs. Slot 0 is used throughout.
struct LlamaServer {
    let base: URL
    /// The slot to use. Burrow's own builds run on a spare slot, so a client's conversation is never erased.
    var slotID = 0

    func call(_ path: String, _ body: [String: Any]?, method: String = "POST") async throws -> [String: Any] {
        var request = URLRequest(url: URL(string: path, relativeTo: base)!)
        request.httpMethod = method
        request.timeoutInterval = 900
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        let object = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        if let http = response as? HTTPURLResponse, http.statusCode != 200 {
            let said = (object["error"] as? [String: Any])?["message"] as? String ?? String(decoding: data.prefix(300), as: UTF8.self)
            throw KVProblem(description: "llama.cpp answered \(http.statusCode) to \(path): \(said)")
        }
        return object
    }

    func model() async throws -> String {
        let props = try await call("/props", nil, method: "GET")
        if let alias = props["model_alias"] as? String, !alias.isEmpty { return alias }
        return ((props["model_path"] as? String).map { ($0 as NSString).lastPathComponent }) ?? "unknown"
    }

    func erase() async throws { _ = try await call("/slots/\(slotID)?action=erase", [:]) }

    func slot(_ action: String, file: String) async throws -> Int {
        let out = try await call("/slots/\(slotID)?action=\(action)", ["filename": file])
        return out["n_written"] as? Int ?? out["n_read"] as? Int ?? 0
    }

    func complete(prompt: String, predict: Int) async throws -> KVShelf.Timing {
        let started = Date()
        let out = try await call("/completion", ["prompt": prompt, "n_predict": predict, "cache_prompt": true, "id_slot": slotID, "stop": ["\nQuestion:"],
                                                 "temperature": 0, "seed": 7])
        let timings = out["timings"] as? [String: Any] ?? [:]
        var timing = KVShelf.Timing()
        timing.promptTokens = timings["prompt_n"] as? Int ?? 0
        timing.promptSeconds = (timings["prompt_ms"] as? Double ?? 0) / 1000
        timing.answer = (out["content"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        timing.answerSeconds = Date().timeIntervalSince(started)
        return timing
    }
}
