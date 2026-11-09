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
  burrow ask   <project> "question" [--mode none|search|walk] [--model NAME] [--json]
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
        let takesValue: Set<String> = ["--mode", "--model", "--kind", "--store", "--folder"]
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
        let answer = try await vault.ask(text, mode: try mode(options, default: .walk), embedder: try embedderIfIndexed(vault, ollama),
                                         answerer: ollama.answerer(model: options.values["--model"] ?? Ollama.defaultModel)) { word in
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
