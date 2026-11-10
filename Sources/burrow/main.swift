import BurrowCore
import Foundation

let usage = """
burrow: private project memory for local models

  burrow                            full-screen terminal view of the last vault, or this folder if it is one
  burrow tui   <vault-folder> [--model NAME] [--store DIR]
  burrow chat  <vault-folder> [--model NAME] [--folder F] [--tools-only]
  burrow mcp   <vault-folder>       MCP server on stdin and stdout
  burrow link  <vault-folder> <code-folder>

  burrow index <project> [--no-embed] [--vault]
  burrow find  <project> "question" [--mode search|walk] [--json]
  burrow ask   <project> "question" [--mode engine|none|search|walk] [--model NAME] [--json] [--no-skills] [--no-check] [--characters N]
  burrow brief <project> "question" [--characters N] [--json]     the question packed for any other model
  burrow fit   <project> [--model NAME]                           measure a model and set how much it is shown
  burrow skills <project> [--install]                             list the skills, or add the starter set
  burrow learn <project> <transcript.json> [--model NAME]         keep what a conversation decided
  burrow note  <project> "text" [--kind decision|rejected|bug|convention|note]
  burrow links <project> <file>
  burrow stats <project>

Add --store DIR to keep the memory somewhere other than <project>/.burrow.
Add --vault to index a whole vault, where every Markdown file is a note.
"""

struct Options {
    var positional: [String] = []
    var flags = Set<String>()
    var values: [String: String] = [:]

    init(_ arguments: [String]) throws {
        let takesValue: Set<String> = ["--mode", "--model", "--kind", "--store", "--folder", "--characters"]
        var index = 0
        while index < arguments.count {
            let word = arguments[index]
            if takesValue.contains(word) {
                guard index + 1 < arguments.count else { throw Failure("\(word) needs a value") }
                values[word] = arguments[index + 1]
                index += 2
            } else {
                if word.hasPrefix("--") { flags.insert(word) } else { positional.append(word) }
                index += 1
            }
        }
    }
}

struct Failure: Error, CustomStringConvertible {
    let description: String
    init(_ description: String) { self.description = description }
}

func jsonLine(_ value: Any) throws -> String {
    String(decoding: try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]), as: UTF8.self)
}

func describe(_ found: Retrieved) -> [[String: Any]] {
    found.excerpts.map {
        ["path": $0.path, "start": $0.startLine, "end": $0.endLine, "reason": $0.reason.label, "note": $0.isNote]
    }
}

func mode(_ options: Options, default fallback: Mode) throws -> Mode {
    guard let word = options.values["--mode"] else { return fallback }
    guard let mode = Mode(rawValue: word) else { throw Failure("unknown mode \(word)") }
    return mode
}

/// Uses embeddings only if this project was indexed with them, so a word-only index stays word-only.
func embedderIfIndexed(_ vault: Vault, _ ollama: Ollama) throws -> Embedder? {
    try vault.stats().vectors > 0 ? ollama.embedder() : nil
}

func run() async throws {
    let arguments = Array(CommandLine.arguments.dropFirst())
    if try await runTerminalCommand(arguments) { return }
    guard let command = arguments.first, !["help", "--help", "-h"].contains(command) else {
        print(usage)
        return
    }
    let options = try Options(Array(arguments.dropFirst()))
    guard let projectPath = options.positional.first else { throw Failure(usage) }
    let vault = try Vault(project: URL(fileURLWithPath: projectPath), store: options.values["--store"].map { URL(fileURLWithPath: $0) }, everything: options.flags.contains("--vault"))
    let ollama = Ollama()
    let text = options.positional.dropFirst().first

    switch command {
    case "index":
        let started = Date()
        let report = try await vault.refresh(embedder: options.flags.contains("--no-embed") ? nil : ollama.embedder()) { line in
            FileHandle.standardError.write(Data("\r\(line)   ".utf8))
        }
        FileHandle.standardError.write(Data("\n".utf8))
        print("\(report.filesSeen) files, \(report.filesChanged) changed, \(report.filesRemoved) removed, \(report.chunks) chunks, \(report.links) links, \(report.embedded) embedded in \(String(format: "%.1f", Date().timeIntervalSince(started))) s")

    case "find":
        guard let text else { throw Failure("find needs a question") }
        let found = try await vault.retrieve(text, mode: try mode(options, default: .walk), embedder: try embedderIfIndexed(vault, ollama))
        if options.flags.contains("--json") {
            print(try jsonLine(["seconds": found.seconds, "characters": found.characters, "excerpts": describe(found)]))
        } else {
            for piece in found.excerpts { print("\(piece.path):\(piece.startLine)-\(piece.endLine)   [\(piece.reason.label)]") }
            print(String(format: "\n%d characters in %.3f s", found.characters, found.seconds))
        }

    case "ask":
        guard let text else { throw Failure("ask needs a question") }
        let asJSON = options.flags.contains("--json")
        let model = options.values["--model"] ?? Ollama.defaultModel
        if options.values["--mode"] == "engine" {
            var profile = await vault.profile(for: model, ollama: ollama)
            // For measuring how the amount shown changes the answers: a fixed budget in place of the fitted one.
            if let fixed = options.values["--characters"].flatMap(Int.init), fixed > 0 {
                profile.budgetCharacters = fixed
                let needed = Int(Double(fixed) / ModelProfile.densest) + ModelProfile.reserveTokens
                profile.windowTokens = [4_096, 8_192, 16_384, 32_768].first { $0 >= needed } ?? 32_768
            }
            var settings = EngineSettings()
            settings.useSkills = !options.flags.contains("--no-skills")
            settings.check = !options.flags.contains("--no-check")
            let reply = try await vault.engage(text, profile: profile, embedder: try embedderIfIndexed(vault, ollama), scope: options.values["--folder"],
                                               answerer: ollama.answerer(model: model, contextWords: profile.windowTokens), settings: settings) { word in
                if !asJSON { FileHandle.standardOutput.write(Data(word.utf8)) }
            }
            let found = reply.brief.retrieved
            if asJSON {
                print(try jsonLine([
                    "answer": reply.result.text, "first_word_s": reply.result.secondsToFirstWord, "total_s": reply.result.totalSeconds + reply.brief.seconds,
                    "retrieve_s": reply.brief.seconds, "prompt_tokens": reply.result.promptTokens, "answer_tokens": reply.result.answerTokens,
                    "characters": found.characters, "excerpts": describe(found),
                    "route": ["mode": reply.brief.route.mode.rawValue, "why": reply.brief.route.why],
                    "skills": reply.brief.skill.map { [$0.name] } ?? [],
                    "citations": ["named": reply.citations.count, "not_shown": reply.unverified.count],
                    "retried": reply.retried, "budget_characters": profile.budgetCharacters, "window_tokens": profile.windowTokens,
                    "nearest": found.signal.nearest.map { Double($0) } as Any? ?? NSNull(),
                ]))
            } else {
                if reply.retried { print("\n\nChecked: the first answer pointed at lines it was not shown, so it was asked again.\n\n" + reply.result.text) }
                print("\n\nDecided: \(reply.brief.route.mode.rawValue), because \(reply.brief.route.why)")
                if let skill = reply.brief.skill { print("Skill: \(skill.name)") }
                print("Read: " + (found.paths.isEmpty ? "nothing" : found.paths.joined(separator: ", ")))
                print("Cited \(reply.citations.count) places, \(reply.unverified.count) not among what it read")
                print(String(format: "Prepared in %.3f s, first word %.2f s, whole answer %.2f s, %d tokens read", reply.brief.seconds, reply.result.secondsToFirstWord, reply.result.totalSeconds, reply.result.promptTokens))
            }
            return
        }
        let answer = try await vault.ask(text, mode: try mode(options, default: .walk), embedder: try embedderIfIndexed(vault, ollama),
                                         answerer: ollama.answerer(model: model)) { word in
            if !asJSON { FileHandle.standardOutput.write(Data(word.utf8)) }
        }
        if asJSON {
            print(try jsonLine([
                "answer": answer.result.text, "first_word_s": answer.result.secondsToFirstWord, "total_s": answer.result.totalSeconds,
                "retrieve_s": answer.retrieved.seconds, "prompt_tokens": answer.result.promptTokens, "answer_tokens": answer.result.answerTokens,
                "characters": answer.retrieved.characters, "excerpts": describe(answer.retrieved),
            ]))
        } else {
            print("\n\nRead: " + (answer.retrieved.paths.isEmpty ? "nothing" : answer.retrieved.paths.joined(separator: ", ")))
            print(String(format: "First word %.2f s, whole answer %.2f s, %d tokens read", answer.result.secondsToFirstWord, answer.result.totalSeconds, answer.result.promptTokens))
        }

    case "brief":
        guard let text else { throw Failure("brief needs a question") }
        var budget = Budget()
        budget.characters = options.values["--characters"].flatMap(Int.init) ?? 24_000
        budget.entryFiles = max(4, budget.characters / 3_000)
        var settings = EngineSettings()
        settings.useSkills = !options.flags.contains("--no-skills")
        let brief = try await vault.brief(text, budget: budget, embedder: try embedderIfIndexed(vault, ollama), scope: options.values["--folder"], settings: settings)
        if options.flags.contains("--json") {
            print(try jsonLine([
                "system": brief.system, "user": brief.user, "retrieve_s": brief.seconds, "characters": brief.retrieved.characters,
                "excerpts": describe(brief.retrieved), "route": ["mode": brief.route.mode.rawValue, "why": brief.route.why],
                "skills": brief.skill.map { [$0.name] } ?? [],
                "nearest": brief.retrieved.signal.nearest.map { Double($0) } as Any? ?? NSNull(),
                "word_matches": brief.retrieved.signal.wordMatches,
                "skill_closeness": brief.skillCloseness.map { Double($0) } as Any? ?? NSNull(),
            ]))
        } else {
            print(brief.system + "\n\n" + brief.user)
        }

    case "fit":
        let model = options.values["--model"] ?? Ollama.defaultModel
        let profile = try await ollama.measure(model: model)
        try vault.keep(profile)
        print(String(format: "%@: %.1f billion parameters, accepts %d tokens, reads %.0f and writes %.0f tokens a second, %.2f characters a token",
                     model, profile.billions, profile.contextTokens, profile.readsPerSecond, profile.writesPerSecond, profile.charactersPerToken))
        print("It will be shown up to \(profile.budgetCharacters) characters of the vault in a window of \(profile.windowTokens) tokens.")

    case "skills":
        if options.flags.contains("--install") {
            let written = try vault.installStarterSkills()
            print(written.isEmpty ? "the starter skills are already there" : "added: " + written.joined(separator: ", "))
            if vault.everything { try await vault.refresh(embedder: try embedderIfIndexed(vault, ollama)) }
        }
        for skill in vault.skills() { print("\(skill.name)   when: \(skill.when)") }

    case "learn":
        guard let text else { throw Failure("learn needs a transcript file") }
        let data = try Data(contentsOf: URL(fileURLWithPath: text))
        guard let list = try JSONSerialization.jsonObject(with: data) as? [[String: String]] else { throw Failure("the transcript must be a JSON list of {question, answer}") }
        let turns = list.map { (question: $0["question"] ?? "", answer: $0["answer"] ?? "") }
        let written = try await vault.learn(from: turns, answerer: ollama.answerer(model: options.values["--model"] ?? Ollama.defaultModel),
                                            embedder: try embedderIfIndexed(vault, ollama))
        print(written.isEmpty ? "nothing new to keep" : "kept: " + written.joined(separator: ", "))

    case "note":
        guard let text else { throw Failure("note needs text") }
        let kindName = options.values["--kind"] ?? "note"
        guard let kind = NoteKind(rawValue: kindName) else { throw Failure("unknown kind \(kindName)") }
        print("kept in \(try vault.addNote(text, kind: kind))")
        try await vault.refresh(embedder: try embedderIfIndexed(vault, ollama))

    case "links":
        guard let text else { throw Failure("links needs a file") }
        for link in try vault.neighbours(of: text) {
            print("\(link.forward ? "->" : "<-") \(link.path)   [\(link.kind.rawValue)\(link.via.map { " " + $0 } ?? "")]")
        }

    case "stats":
        let stats = try vault.stats()
        print("\(stats.files) files, \(stats.notes) notes, \(stats.clusters) clusters, \(stats.chunks) chunks, \(stats.links) links, \(stats.vectors) vectors, index \(stats.indexBytes / 1024) KB")

    default:
        throw Failure("unknown command \(command)\n\n\(usage)")
    }
}

do {
    try await run()
} catch {
    FileHandle.standardError.write(Data("burrow: \(error)\n".utf8))
    exit(1)
}
