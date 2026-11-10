import BurrowCore
import BurrowTools
import Foundation

/// The terminal side of a chat: reads questions, streams answers, and shows each tool call on a dim line.
public final class ChatREPL {
    private let session: ChatSession
    private let tools: VaultTools
    private let backend: ChatBackend
    private let interactive: Bool
    private let useColor: Bool

    public init(session: ChatSession, tools: VaultTools, backend: ChatBackend) {
        self.session = session
        self.tools = tools
        self.backend = backend
        interactive = isatty(STDIN_FILENO) == 1
        let environment = ProcessInfo.processInfo.environment
        useColor = isatty(STDOUT_FILENO) == 1 && environment["NO_COLOR"] == nil && environment["TERM"] != "dumb"
    }

    private func put(_ text: String) {
        FileHandle.standardOutput.write(Data(TerminalText.clean(text).utf8))
    }

    private func dim(_ text: String) -> String { useColor ? "\u{1B}[2m\(text)\u{1B}[22m" : text }
    private func bold(_ text: String) -> String { useColor ? "\u{1B}[1m\(text)\u{1B}[22m" : text }

    private static let help = """
    /folders       show the folders you can limit this chat to
    /folder NAME   limit the chat to one folder. /folder alone clears it
    /keep          write down what you decided in this conversation, one note at a time
    /new           forget this conversation and start again
    /help          show this
    /quit          leave. Control-D works too
    """

    private func observer() -> ChatSession.Observer {
        var watching = ChatSession.Observer()
        watching.word = { [unowned self] word in put(word) }
        watching.toolStarted = { [unowned self] name, arguments, forced in
            put(dim("  · \(name)(\(arguments))\(forced ? "  [always-search fallback: Burrow ran this, the model did not choose it]" : "")\n"))
        }
        watching.toolFinished = { [unowned self] event in
            put(dim("    \(event.failed ? "✗" : "→") \(event.outcome)  \(String(format: "%.2f s", event.seconds))\n"))
        }
        watching.mayRemember = { [unowned self] text, kind in
            guard interactive else {
                put(dim("    ✗ a note can only be kept when someone is at the keyboard\n"))
                return false
            }
            put("\n  The model wants to keep this as a \(kind) note:\n  \(text)\n  Keep it? [y/N] ")
            return Swift.readLine()?.trimmingCharacters(in: .whitespaces).lowercased() == "y"
        }
        return watching
    }

    public func run() async {
        await tools.freshen(checkNow: true)
        let stats = try? tools.vault.stats()
        put(bold("burrow chat") + dim("  \(tools.vault.root.lastPathComponent)  ·  \(backend.model)  ·  \(tools.fixedFolder.map { "folder \($0)" } ?? "whole vault")"))
        put("\n")
        if let stats { put(dim("\(stats.notes) notes, \(stats.files) code files, \(stats.vectors > 0 ? "meaning search on" : "words only")"))  }
        put(dim(session.settings.alwaysSearchFirst ? "  ·  searches the vault first (always-search fallback; --tools-only turns it off)\n" : "\n"))
        put(dim("/help for commands\n\n"))

        while true {
            if interactive { put(bold("› ")) }
            guard let line = Swift.readLine() else { break }
            let question = line.trimmingCharacters(in: .whitespaces)
            if question.isEmpty { continue }
            if !interactive { put("› \(question)\n") }
            if question.hasPrefix("/") {
                if await command(question) { break }
                continue
            }
            do {
                let turn = try await session.ask(question, observer: observer())
                put("\n")
                let read = turn.sources.prefix(8).map { "\($0.path):\($0.startLine)-\($0.endLine)" }.joined(separator: ", ")
                let extra = turn.sources.count > 8 ? " and \(turn.sources.count - 8) more" : ""
                if !read.isEmpty { put(dim("\n  read: \(read)\(extra)\n")) }
                put(dim(String(format: "  %d tool calls, %d rounds, %d prompt tokens, %.1f s%@\n\n", turn.events.count, turn.rounds, turn.promptTokens, turn.seconds, turn.endedAtLimit ? ", stopped at the tool limit" : "")))
            } catch where OllamaReach.isUnreachable(error) {
                put("\n✗ \(OllamaReach.message)\n\n")
            } catch {
                put("\n✗ \(error)\n\n")
            }
        }
        if interactive { put("\n") }
    }

    /// True when the chat should end.
    private func command(_ line: String) async -> Bool {
        let parts = line.split(separator: " ", maxSplits: 1).map(String.init)
        switch parts[0] {
        case "/quit", "/exit": return true
        case "/help": put(Self.help + "\n\n")
        case "/keep":
            guard interactive else {
                put(dim("A note can only be kept when someone is at the keyboard.\n\n"))
                return false
            }
            let ollama = Ollama()
            let embedder: Embedder? = ((try? tools.vault.stats().vectors) ?? 0) > 0 ? ollama.embedder() : nil
            do {
                let found = try await tools.vault.lessons(from: session.exchanges, answerer: ollama.answerer(model: backend.model), embedder: embedder)
                if found.isEmpty { put(dim("Nothing new to keep from this conversation.\n\n")) }
                for lesson in found {
                    put("  \(lesson.kind.rawValue): \(lesson.text)\n  Keep it? [y/N] ")
                    guard Swift.readLine()?.trimmingCharacters(in: .whitespaces).lowercased() == "y" else { continue }
                    let written = try await tools.vault.keep([lesson], embedder: embedder)
                    put(dim("  kept in \(written.joined(separator: ", "))\n"))
                }
                put("\n")
            } catch {
                put("✗ \(error)\n\n")
            }
        case "/new":
            session.clear()
            put(dim("Started again.\n\n"))
        case "/folders":
            let result = try? await tools.call("vault_folders", arguments: [:])
            put((result?.text ?? "Could not list the folders.") + "\n\n")
        case "/folder":
            guard parts.count > 1 else {
                tools.fixedFolder = nil
                put(dim("Using the whole vault.\n\n"))
                return false
            }
            let name = parts[1].trimmingCharacters(in: CharacterSet(charactersIn: " /"))
            if ((try? tools.folderNames()) ?? []).contains(name) {
                tools.fixedFolder = name
                session.clear()
                put(dim("Limited to \(name). Started a new conversation.\n\n"))
            } else {
                put("There is no folder called \(name). /folders lists them.\n\n")
            }
        default: put("Unknown command. /help lists them.\n\n")
        }
        return false
    }
}
