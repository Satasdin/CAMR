import BurrowCore
import Foundation

/// One question and its answer, with who answered it and what they read.
public struct SessionTurn: Codable, Sendable {
    public var question: String
    public var answer: String
    public var model: String
    public var server: String
    public var tools: [String]
    public var sources: [String]
    public var seconds: Double
    public var promptTokens: Int
    public var at: Date

    public init(question: String, answer: String, model: String, server: String, tools: [String] = [], sources: [String] = [],
                seconds: Double = 0, promptTokens: Int = 0, at: Date = Date()) {
        self.question = question
        self.answer = answer
        self.model = model
        self.server = server
        self.tools = tools
        self.sources = sources
        self.seconds = seconds
        self.promptTokens = promptTokens
        self.at = at
    }
}

/// One thing a connected program looked up, kept by Burrow whether or not the model logs anything.
public struct TrailStep: Codable, Sendable {
    public var tool: String
    public var asked: String
    public var files: [String]
    public var at: Date

    public init(tool: String, asked: String, files: [String], at: Date = Date()) {
        self.tool = tool
        self.asked = asked
        self.files = files
        self.at = at
    }
}

/// A conversation kept in the vault, so another model, another program or another day can pick it up.
public struct SessionRecord: Codable, Sendable {
    public var id: String
    public var started: Date
    public var updated: Date
    public var turns: [SessionTurn]
    /// The session this one was resumed from, if any.
    public var resumedFrom: String?
    /// The program that connected, as it named itself to MCP: opencode, claude-code, LM Studio.
    public var client: String?
    /// What that program looked up, in order. Burrow writes this itself, so a model that forgets to log still leaves a trace.
    public var trail: [TrailStep]?

    public init(id: String = SessionRecord.newID(), resumedFrom: String? = nil) {
        self.id = id
        started = Date()
        updated = started
        turns = []
        self.resumedFrom = resumedFrom
    }

    public static func newID(_ date: Date = Date()) -> String {
        let format = DateFormatter()
        format.locale = Locale(identifier: "en_US_POSIX")
        format.dateFormat = "yyyyMMdd-HHmmss"
        return format.string(from: date) + "-" + String(UUID().uuidString.prefix(4)).lowercased()
    }

    /// Every model that has answered in this session, in order of first appearance.
    public var models: [String] {
        var seen: [String] = []
        for turn in turns where !seen.contains("\(turn.model) (\(turn.server))") { seen.append("\(turn.model) (\(turn.server))") }
        return seen
    }

    /// Files read anywhere in the session, most recent first, without repeats.
    public var filesInPlay: [String] {
        var seen: [String] = []
        for turn in turns.reversed() { for source in turn.sources where !seen.contains(source) { seen.append(source) } }
        for step in (trail ?? []).reversed() { for file in step.files where !seen.contains(file) { seen.append(file) } }
        return seen
    }

    public var isEmpty: Bool { turns.isEmpty && (trail ?? []).isEmpty }
}

/// Sessions live as plain JSON files in the vault's store, one per conversation.
public struct SessionStore: Sendable {
    public let folder: URL

    public init(vault: Vault) { folder = vault.store.appendingPathComponent("sessions") }
    public init(folder: URL) { self.folder = folder }

    private static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()
    private static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()

    public func save(_ record: SessionRecord) throws {
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        var record = record
        record.updated = Date()
        try Self.encoder.encode(record).write(to: folder.appendingPathComponent(record.id + ".json"), options: .atomic)
    }

    /// Newest first.
    public func list() -> [SessionRecord] {
        let names = (try? FileManager.default.contentsOfDirectory(atPath: folder.path)) ?? []
        return names.filter { $0.hasSuffix(".json") }
            .compactMap { try? Self.decoder.decode(SessionRecord.self, from: Data(contentsOf: folder.appendingPathComponent($0))) }
            .sorted { $0.updated > $1.updated }
    }

    /// An id, the start of one, or "last": the newest conversation with logged turns that is not `excluding`
    /// (the caller's own session), or failing that the newest with any lookups.
    public func load(_ id: String, excluding: String? = nil) -> SessionRecord? {
        let all = list().filter { $0.id != excluding && !$0.isEmpty }
        if id == "last" { return all.first { !$0.turns.isEmpty } ?? all.first }
        return all.first { $0.id == id } ?? all.first { $0.id.hasPrefix(id) }
    }
}

/// What a model that did not see a conversation is given to carry it on.
public enum Carry: String, Sendable, CaseIterable {
    /// Burrow's short handoff: earlier questions, files already read, and the last turns.
    case handoff
    /// Every turn, word for word. The baseline a person would get by pasting the transcript.
    case full
    /// Nothing. The baseline of starting again.
    case none
}

public enum Handoff {
    public static let defaultCharacters = 2_400
    static let lastTurnsInFull = 2

    private static func cut(_ text: String, _ most: Int) -> String {
        let flat = text.replacingOccurrences(of: "\n\n", with: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
        return flat.count > most ? String(flat.prefix(most - 1)) + "…" : flat
    }

    /// The handoff as text, held to `characters`. Older material is dropped first: the last turns matter most.
    public static func text(_ record: SessionRecord, characters: Int = defaultCharacters) -> String {
        guard !record.isEmpty else { return "" }
        let by = record.models.isEmpty ? (record.client ?? "another program") : record.models.joined(separator: ", ")
        let head = "This conversation started earlier (session \(record.id), \(record.turns.count) logged turns, answered by \(by)\(record.client.map { " in \($0)" } ?? "")). You are carrying it on. What follows is what happened so far."
        let recentFrom = max(0, record.turns.count - lastTurnsInFull)
        var answerRoom = 700
        var olderRoom = 160
        var dropped = 0
        while true {
            var parts = [head]
            // The short parts go first, so trimming for length never loses them.
            // File names only: the turns matter more than line ranges, and vault_read finds the lines again.
            var names: [String] = []
            for place in record.filesInPlay {
                let name = place.components(separatedBy: ":").first ?? place
                if !names.contains(name) { names.append(name) }
            }
            if !names.isEmpty { parts.append("Files read: " + names.prefix(6).joined(separator: ", ") + ".") }
            let trail = (record.trail ?? []).filter { !$0.asked.isEmpty }
            let kept = trail.filter { $0.tool == "vault_remember" }.suffix(6).map { "- " + cut(String($0.asked.dropFirst("kept a note: ".count)), 400) }
            if !kept.isEmpty { parts.append("Notes kept during the conversation, oldest first:\n" + kept.joined(separator: "\n")) }
            let looked = trail.filter { $0.tool != "vault_remember" }.suffix(8).map { cut($0.asked, 90) }
            if !looked.isEmpty, record.turns.isEmpty { parts.append("Looked up in the vault, oldest first: " + looked.joined(separator: "; ") + ".") }
            // Every turn is numbered the same way, so "my second question" means the same thing to every model.
            if !record.turns.isEmpty {
                let lines = record.turns.enumerated().dropFirst(dropped).map { index, turn -> String in
                    let recent = index >= recentFrom
                    return "Turn \(index + 1). User: \(cut(turn.question, recent ? 300 : 140))\nAnswer (\(turn.model)): \(cut(turn.answer, recent ? answerRoom : olderRoom))"
                }
                let gap = dropped > 0 ? "Turns 1 to \(dropped) are left out for length; vault_session_resume can't show more, but the files above hold what they read.\n\n" : ""
                parts.append("The conversation, \(record.turns.count) turns, oldest first:\n\n" + gap + lines.joined(separator: "\n\n"))
            }
            let text = parts.joined(separator: "\n\n")
            if text.count <= characters { return text }
            if answerRoom > 240 { answerRoom -= 120; olderRoom = max(60, olderRoom - 40); continue }
            if dropped < recentFrom { dropped += 1; continue }
            return String(text.prefix(characters))
        }
    }

    /// The whole conversation as alternating messages, for the `full` baseline.
    public static func messages(_ record: SessionRecord) -> [[String: Any]] {
        record.turns.flatMap { [["role": "user", "content": $0.question], ["role": "assistant", "content": $0.answer]] as [[String: Any]] }
    }
}
