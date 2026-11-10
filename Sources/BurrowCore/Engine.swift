import Foundation

/// What the engine decided to do with a question, and why, in words a person can read.
public struct Route: Sendable, Equatable {
    public let mode: Mode
    public let why: String
}

/// A place an answer pointed at, and whether the model had really been shown it.
public struct Citation: Sendable, Equatable {
    public let path: String
    public let line: Int
    public let shown: Bool
}

/// A question made ready for any model: the rules, the method, and the excerpts, sized for that model.
public struct Brief: Sendable {
    public let route: Route
    public let skill: Skill?
    public let skillCloseness: Float?
    public let retrieved: Retrieved
    public let system: String
    public let user: String
    /// Time spent deciding, searching and packing, before any model is called.
    public let seconds: Double
}

public struct EngineReply: Sendable {
    public let brief: Brief
    public let result: ChatResult
    public let citations: [Citation]
    /// True when the first answer cited places it was not shown and the model was asked again.
    public let retried: Bool
    public let profile: ModelProfile
    public var unverified: [Citation] { citations.filter { !$0.shown } }
}

/// The thresholds the engine decides by. They were set on development questions before any scored run.
public struct EngineSettings: Sendable {
    /// Below this closeness, and with no shared words, the vault has nothing on the question and stays out of the way.
    public var memoryFloor: Float = 0.40
    /// Between the floor and this, the vault is only a loose match. A task that needs no vault then goes without it.
    public var looseMatch: Float = 0.52
    /// A skill is matched to a question only when its "when" line is this close, and clearly closer than the next skill.
    public var skillFloor: Float = 0.55
    public var skillMargin: Float = 0.10
    public var useSkills = true
    public var check = true
    public init() {}
}

public enum Engine {
    static let codeKinds: Set<String> = [
        "swift", "py", "js", "ts", "tsx", "jsx", "go", "rs", "java", "kt", "c", "h", "cpp", "hpp", "cc", "m", "mm", "rb", "php", "cs",
        "scala", "sh", "sql", "html", "css", "vue", "dart", "lua", "r",
    ]

    static func isCode(_ path: String) -> Bool { codeKinds.contains((path as NSString).pathExtension.lowercased()) }

    /// `path/file.ext:12`, as the rules ask for, and the way a model says it in a sentence: "file.ext at line 12", "file.ext, lines 12".
    private static let cited = try! NSRegularExpression(
        pattern: #"([A-Za-z0-9_][A-Za-z0-9_./\-]*\.[A-Za-z0-9]{1,8})[`'"*)\]]*(?::|,? (?:at |on |in )?lines? )(\d+)"#, options: [.caseInsensitive])

    /// Every place an answer names, checked against what the model was shown.
    public static func citations(in answer: String, shown excerpts: [Excerpt]) -> [Citation] {
        let range = NSRange(answer.startIndex..., in: answer)
        var seen = Set<String>()
        var found: [Citation] = []
        for match in cited.matches(in: answer, range: range) {
            guard let pathRange = Range(match.range(at: 1), in: answer), let lineRange = Range(match.range(at: 2), in: answer),
                  let line = Int(answer[lineRange]) else { continue }
            let path = String(answer[pathRange])
            guard seen.insert("\(path):\(line)").inserted else { continue }
            let shown = excerpts.contains { piece in
                (piece.path == path || piece.path.hasSuffix("/" + path) || (piece.path as NSString).lastPathComponent == (path as NSString).lastPathComponent)
                    && line >= piece.startLine && line <= piece.endLine
            }
            found.append(Citation(path: path, line: line, shown: shown))
        }
        return found
    }

    static func correction(_ wrong: [Citation]) -> String {
        let places = wrong.prefix(6).map { "\($0.path):\($0.line)" }.joined(separator: ", ")
        return """


        Your earlier answer pointed at places that are not in the excerpts: \(places).
        Answer again. Use only the excerpts above, and name only lines that appear in them with their numbers.
        If the excerpts do not contain the answer, say so.
        """
    }
}

extension Vault {
    /// Decides what a question needs and packs it for a model, without calling one.
    /// This is the engine's face for a model Burrow does not host: a cloud model, another framework, an MCP client.
    public func brief(_ question: String, budget: Budget = Budget(), embedder: Embedder? = nil, scope: String? = nil,
                      settings: EngineSettings = EngineSettings()) async throws -> Brief {
        let started = Date()
        // A plain search is cheap and says how well the vault knows the subject and what kind of file answers it.
        var found = try await retrieve(question, mode: .search, budget: budget, embedder: embedder, scope: scope)
        let ranking = settings.useSkills ? try await skillRanking(for: question, embedder: embedder) : []
        // A match counts only when one skill stands clear of the rest. A method that half fits is worse than none.
        var matched: (skill: Skill, closeness: Float)?
        if let top = ranking.first, top.closeness >= settings.skillFloor,
           ranking.count < 2 || top.closeness - ranking[1].closeness >= settings.skillMargin { matched = top }

        var route: Route
        let nearest = found.signal.nearest
        if found.excerpts.isEmpty {
            route = Route(mode: .none, why: "the vault has nothing on this")
        } else if let nearest, nearest < settings.memoryFloor {
            route = Route(mode: .none, why: String(format: "nothing in the vault is close to this (closest %.2f)", nearest))
        } else if let nearest, nearest < settings.looseMatch, let matched, !matched.skill.needsVault, matched.closeness > nearest {
            route = Route(mode: .none, why: "this is a task to work out, not something to look up")
        } else if nearest == nil, found.signal.wordMatches == 0 {
            route = Route(mode: .none, why: "no file shares a word with this")
        } else {
            let first = found.paths.prefix(4)
            let code = first.filter(Engine.isCode).count
            if code * 2 >= first.count, code > 0 {
                route = Route(mode: .walk, why: "the closest files are code, so their links are followed")
                found = try await retrieve(question, mode: .walk, budget: budget, embedder: embedder, scope: scope)
            } else {
                route = Route(mode: .search, why: "the closest files are notes and documents")
            }
        }
        if route.mode == .none { found = Retrieved(mode: .none, excerpts: [], seconds: found.seconds, signal: found.signal) }

        let memory = route.mode != .none
        var chosen = matched.flatMap { $0.skill.needsVault && !memory ? nil : $0 }
        if chosen == nil, memory {
            // No skill stood out, so the method follows the material: one for documents, one for code.
            let kind = route.mode == .walk ? "code" : "documents"
            chosen = ranking.first { $0.skill.fallbackFor == kind }
        }
        return Brief(route: route, skill: chosen?.skill, skillCloseness: chosen?.closeness, retrieved: found,
                     system: Asking.system(for: question, memory: memory, skill: chosen?.skill),
                     user: Asking.prompt(question: question, excerpts: found.excerpts), seconds: Date().timeIntervalSince(started))
    }

    /// The whole loop for a model Burrow hosts: decide, fit, answer, check.
    public func engage(_ question: String, profile: ModelProfile, embedder: Embedder? = nil, scope: String? = nil, answerer: Answerer,
                       settings: EngineSettings = EngineSettings(), onWord: @escaping @Sendable (String) -> Void = { _ in }) async throws -> EngineReply {
        let brief = try await brief(question, budget: profile.budget, embedder: embedder, scope: scope, settings: settings)
        var result = try await answerer.answer(system: brief.system, user: brief.user, onWord: onWord)
        var citations = Engine.citations(in: result.text, shown: brief.retrieved.excerpts)
        var retried = false
        let wrong = citations.filter { !$0.shown }
        if settings.check, !wrong.isEmpty, !brief.retrieved.excerpts.isEmpty {
            let second = try await answerer.answer(system: brief.system, user: brief.user + Engine.correction(wrong), onWord: { _ in })
            let recheck = Engine.citations(in: second.text, shown: brief.retrieved.excerpts)
            // The second answer is kept only if it is better grounded than the first.
            if recheck.filter({ !$0.shown }).count < wrong.count {
                result = ChatResult(text: second.text, secondsToFirstWord: result.secondsToFirstWord,
                                    totalSeconds: result.totalSeconds + second.totalSeconds,
                                    promptTokens: result.promptTokens + second.promptTokens, answerTokens: result.answerTokens + second.answerTokens,
                                    promptSeconds: result.promptSeconds + second.promptSeconds, answerSeconds: result.answerSeconds + second.answerSeconds)
                citations = recheck
            }
            retried = true
        }
        return EngineReply(brief: brief, result: result, citations: citations, retried: retried, profile: profile)
    }
}

// MARK: Learning

/// Something worth keeping from a conversation, with the person's own words that back it.
public struct Lesson: Sendable, Equatable {
    public let kind: NoteKind
    public let text: String
    public let quote: String
}

public enum Learning {
    static let system = """
    You read a conversation between a person and an assistant and pick out what is worth remembering next time.
    Keep only what the PERSON said or confirmed: a decision they made, a correction they gave, a fix they rejected, a rule they want followed.
    Do not keep questions, small talk, or anything only the assistant said.
    Write each item on its own line as JSON: {"kind": "decision" | "rejected" | "bug" | "convention" | "note", "text": "one clear sentence that stands alone", "quote": "the person's exact words that show it"}
    At most three lines. If nothing is worth keeping, write the single word NONE.
    """

    static func transcript(_ turns: [(question: String, answer: String)]) -> String {
        turns.map { "PERSON: \($0.question)\nASSISTANT: \(String($0.answer.prefix(1_200)))" }.joined(separator: "\n\n")
    }

    /// Reads the model's lines. An item is kept only if its quote really is in what the person typed, so the model
    /// cannot turn its own guess, or a sentence from a file it read, into a remembered fact.
    public static func lessons(from reply: String, said: [String]) -> [Lesson] {
        let spoken = said.joined(separator: "\n").lowercased().split(whereSeparator: \.isWhitespace).joined(separator: " ")
        var kept: [Lesson] = []
        for line in reply.components(separatedBy: "\n") {
            guard let open = line.firstIndex(of: "{"), let close = line.lastIndex(of: "}"), open < close,
                  let item = try? JSONSerialization.jsonObject(with: Data(line[open...close].utf8)) as? [String: Any],
                  let text = (item["text"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines), text.count >= 12,
                  let quote = (item["quote"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines), quote.count >= 8 else { continue }
            let wanted = quote.lowercased().split(whereSeparator: \.isWhitespace).joined(separator: " ")
            guard spoken.contains(wanted) else { continue }
            kept.append(Lesson(kind: NoteKind(rawValue: (item["kind"] as? String ?? "note").lowercased()) ?? .note, text: text, quote: quote))
            if kept.count == 3 { break }
        }
        return kept
    }
}

extension Vault {
    /// After a conversation: asks the model what the person decided, and returns what is new. Nothing is written.
    public func lessons(from turns: [(question: String, answer: String)], answerer: Answerer, embedder: Embedder? = nil) async throws -> [Lesson] {
        guard !turns.isEmpty else { return [] }
        let reply = try await answerer.answer(system: Learning.system, user: Learning.transcript(turns), onWord: { _ in })
        var fresh: [Lesson] = []
        for lesson in Learning.lessons(from: reply.text, said: turns.map(\.question)) {
            // Something already written down is not written again.
            let found = try await retrieve(lesson.text, mode: .search, embedder: embedder)
            if let nearest = found.signal.nearest, nearest > 0.90, found.excerpts.first?.isNote == true { continue }
            fresh.append(lesson)
        }
        return fresh
    }

    /// Writes lessons down as notes and brings the index up to date.
    /// - Returns: the paths of the notes written.
    @discardableResult
    public func keep(_ lessons: [Lesson], embedder: Embedder? = nil) async throws -> [String] {
        var written: [String] = []
        for lesson in lessons { written.append(try addNote(lesson.text + "\n\nSaid as: \"" + lesson.quote + "\"", kind: lesson.kind)) }
        if !written.isEmpty { try await refresh(embedder: embedder) }
        return written
    }

    /// Both steps at once, for when a person has asked for the conversation to be kept.
    @discardableResult
    public func learn(from turns: [(question: String, answer: String)], answerer: Answerer, embedder: Embedder? = nil) async throws -> [String] {
        try await keep(try await lessons(from: turns, answerer: answerer, embedder: embedder), embedder: embedder)
    }
}
