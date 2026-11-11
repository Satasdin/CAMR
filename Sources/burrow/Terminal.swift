import BurrowChat
import BurrowCore
import BurrowMCP
import BurrowTUI
import BurrowTools
import Foundation

func logToStandardError(_ line: String) {
    FileHandle.standardError.write(Data("burrow: \(line)\n".utf8))
}

/// Opens a vault of everything. The folder has to exist already, so a mistyped path doesn't quietly become a new vault.
func openVault(_ path: String, store: String?) throws -> Vault {
    var isFolder: ObjCBool = false
    guard FileManager.default.fileExists(atPath: path, isDirectory: &isFolder), isFolder.boolValue else {
        throw Failure("\(path) is not a folder")
    }
    return try Vault(project: URL(fileURLWithPath: path), store: store.map { URL(fileURLWithPath: $0) }, everything: true)
}

/// Where the last-opened vault is remembered, so `burrow` alone can go back to it.
private func stateFile() -> URL {
    if let folder = ProcessInfo.processInfo.environment["BURROW_STATE_DIR"] {
        return URL(fileURLWithPath: folder).appendingPathComponent("last-vault")
    }
    return FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("Burrow/last-vault")
}

/// This folder if it already has a Burrow index, or else the vault opened last. Never a folder Burrow hasn't been pointed at.
private func defaultVault() -> String? {
    let here = FileManager.default.currentDirectoryPath
    if FileManager.default.fileExists(atPath: here + "/.burrow/index.sqlite") { return here }
    guard let saved = try? String(contentsOf: stateFile(), encoding: .utf8) else { return nil }
    let path = saved.trimmingCharacters(in: .whitespacesAndNewlines)
    return FileManager.default.fileExists(atPath: path) ? path : nil
}

private func runFullScreen(_ folder: String, store: String?, model: String) throws {
    var isFolder: ObjCBool = false
    guard FileManager.default.fileExists(atPath: folder, isDirectory: &isFolder), isFolder.boolValue else { throw Failure("\(folder) is not a folder") }
    let url = URL(fileURLWithPath: folder).standardizedFileURL
    do {
        let app = try TerminalApp(vaultFolder: url, store: store.map { URL(fileURLWithPath: $0) }, modelName: model)
        try? FileManager.default.createDirectory(at: stateFile().deletingLastPathComponent(), withIntermediateDirectories: true)
        try? url.path.write(to: stateFile(), atomically: true, encoding: .utf8)
        app.run()
    } catch let problem as TerminalApp.Failure {
        throw Failure(problem.description)
    }
}

/// The commands that keep a whole vault open. Returns false for anything the older commands should handle.
func runTerminalCommand(_ arguments: [String]) async throws -> Bool {
    if arguments.isEmpty {
        // A pipe or a script keeps getting the plain usage text, as it always has.
        guard isatty(STDIN_FILENO) == 1, isatty(STDOUT_FILENO) == 1 else { return false }
        guard let folder = defaultVault() else {
            throw Failure("no vault here yet. Open one with: burrow tui <vault-folder>\n\n\(usage)")
        }
        try runFullScreen(folder, store: nil, model: Ollama.defaultModel)
        return true
    }
    let command = arguments[0]
    guard ["mcp", "link", "chat", "tui"].contains(command) else { return false }
    let options = try Options(Array(arguments.dropFirst()))
    guard let folder = options.positional.first else { throw Failure(usage) }
    if command == "tui" {
        try runFullScreen(folder, store: options.values["--store"], model: options.values["--model"] ?? Ollama.defaultModel)
        return true
    }
    let vault = try openVault(folder, store: options.values["--store"])
    switch command {
    case "mcp":
        let output = ProtocolOutput()
        let tools = VaultTools.onThisMac(vault: vault, model: options.values["--model"] ?? Ollama.defaultModel, log: logToStandardError)
        logToStandardError("MCP server for \(vault.root.path)")
        let server = MCPServer(tools: tools, keepsSessions: !options.flags.contains("--no-sessions"), log: logToStandardError)
        guard let set = ToolSet(rawValue: options.values["--tools"] ?? "door") else { throw Failure("--tools takes door, full or classic") }
        server.toolSet = set
        // Baseline arms of Evaluation 3 only: the search without the trust line, or without Ledger notes.
        if options.flags.contains("--no-trust") { tools.trustLinesOn = false }
        if options.flags.contains("--no-ledger-notes") { tools.ledgerNotesOn = false }
        if let address = options.values["--llama"], let url = URL(string: address) {
            // Whatever a lookup returns is also read into the model's cache on a spare slot, after the reply (D-60).
            let store = options.values["--store"]
            let warmer = KVWarmer(settings: KVWarmer.Settings(server: url), open: { try openVault(folder, store: store) }, log: logToStandardError)
            if case let .ready(_, _, window) = await warmer.connect() { tools.packWindow = window }
            server.afterCall = { name, arguments, result in
                if name == "vault_pack" {
                    let part = (arguments["part"] as? NSNumber)?.intValue ?? Int("\(arguments["part"] ?? 1)") ?? 1
                    warmer.asked(scope: (arguments["folder"] as? String) ?? "", part: part)
                } else {
                    warmer.noticed(result.sources.map(\.path))
                }
            }
        }
        await server.serve(readLine: { Swift.readLine() }, write: output.write)
    case "chat":
        let model = options.values["--model"] ?? Ollama.defaultModel
        // Half the usual search allowance, so two searches and a read still fit in the model's context.
        let tools = VaultTools.onThisMac(vault: vault, model: model, searchCharacters: 6_000, log: { _ in })
        if let folder = options.values["--folder"] {
            await tools.freshen(checkNow: true)
            let clean = folder.trimmingCharacters(in: CharacterSet(charactersIn: " /"))
            guard try tools.folderNames().contains(clean) else { throw Failure("there is no folder called \(clean) in this vault") }
            tools.fixedFolder = clean
        }
        var settings = ChatSession.Settings()
        settings.alwaysSearchFirst = !options.flags.contains("--tools-only")
        let backend = OllamaChat(model: model)
        await ChatREPL(session: ChatSession(tools: tools, backend: backend, settings: settings), tools: tools, backend: backend).run()
    case "link":
        guard options.positional.count > 1 else { throw Failure("link needs a code folder") }
        let target = URL(fileURLWithPath: options.positional[1])
        var isFolder: ObjCBool = false
        guard FileManager.default.fileExists(atPath: target.path, isDirectory: &isFolder), isFolder.boolValue else { throw Failure("\(target.path) is not a folder") }
        let linked = try vault.linkFolder(target)
        print("linked \(linked.path) as \(linked.name), read-only")
    default: break
    }
    return true
}
