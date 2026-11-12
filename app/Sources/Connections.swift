import AppKit
import Foundation

/// Whether each program on this Mac is actually wired to this vault, read from the programs' own settings files.
/// The Programs page shows this so a person can see at a glance which program will find the vault and which won't.
struct Connection: Equatable {
    enum State: Equatable {
        /// Its settings start `burrow mcp` on this vault.
        case thisVault
        /// Its settings start `burrow mcp` on a different folder.
        case otherVault(String)
        /// A model server (Ollama, llama.cpp) that is running; it reaches the vault through OpenCode.
        case serving
        /// Its own settings don't start Burrow, yet it has used this vault: set up in a project folder.
        case usedElsewhere
        /// Installed, but nothing points it at Burrow.
        case notSetUp
        /// Not found on this Mac.
        case missing
    }
    var state: State
    /// Where that was read, for the person to check.
    var source: String?

    var label: String {
        switch state {
        case .thisVault: return "Connected"
        case .otherVault: return "Another vault"
        case .serving: return "Server running"
        case .usedElsewhere: return "Set up in a project"
        case .notSetUp: return "Not set up"
        case .missing: return "Not installed"
        }
    }

    var detail: String {
        switch state {
        case .thisVault: return "Its settings start Burrow on this vault" + (source.map { " (\($0))" } ?? "")
        case let .otherVault(path): return "Its settings start Burrow on \((path as NSString).abbreviatingWithTildeInPath)"
        case .serving: return "Serving models on this Mac; point OpenCode at it to reach the vault"
        case .usedElsewhere: return "Has used this vault through a project's own settings; its global settings don't start Burrow"
        case .notSetUp: return "Installed, but it does not start Burrow yet"
        case .missing: return "Not found on this Mac"
        }
    }

    var isLinked: Bool { state == .thisVault || state == .usedElsewhere }
}

enum Connections {
    static let home = FileManager.default.homeDirectoryForCurrentUser

    /// The `burrow` command to write into settings files. Always a full path: programs opened from the Dock
    /// (LM Studio, Claude Desktop) do not get the shell's PATH, so a bare `burrow` would not start.
    static var command: String {
        let candidates = ["/opt/homebrew/bin/burrow", "/usr/local/bin/burrow", home.appendingPathComponent(".local/bin/burrow").path]
        if let found = candidates.first(where: { FileManager.default.isExecutableFile(atPath: $0) }) { return found }
        let bundled = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/bin/burrow").path
        if FileManager.default.isExecutableFile(atPath: bundled) { return bundled }
        return "burrow"
    }

    static var commandIsInstalled: Bool { command != "burrow" }

    /// Reads every program's settings once. Cheap: a few small JSON files and two port checks.
    static func read(vault: URL) async -> [Program: Connection] {
        let path = vault.standardizedFileURL.path
        var out: [Program: Connection] = [:]
        out[.claudeCode] = scan(files: [home.appendingPathComponent(".claude.json")], vault: path, installed: installed("claude"))
        out[.openCode] = scan(files: [vault.appendingPathComponent("opencode.json"), home.appendingPathComponent(".config/opencode/opencode.json")],
                              vault: path, installed: installed("opencode"))
        out[.lmStudio] = scan(files: [home.appendingPathComponent(".lmstudio/mcp.json")], vault: path,
                              installed: FileManager.default.fileExists(atPath: "/Applications/LM Studio.app") || FileManager.default.fileExists(atPath: home.appendingPathComponent(".lmstudio").path))
        async let ollama = listening(11434)
        async let llama = listening(8080)
        out[.ollama] = Connection(state: await ollama ? .serving : (installed("ollama") ? .notSetUp : .missing), source: "127.0.0.1:11434")
        out[.llamaCpp] = Connection(state: await llama ? .serving : (installed("llama-server") ? .notSetUp : .missing), source: "127.0.0.1:8080")
        return out
    }

    private static func installed(_ tool: String) -> Bool {
        ["/opt/homebrew/bin", "/usr/local/bin", home.appendingPathComponent(".local/bin").path, home.appendingPathComponent(".opencode/bin").path]
            .contains { FileManager.default.isExecutableFile(atPath: "\($0)/\(tool)") }
    }

    /// Looks for a server named `burrow` in each file and reads which folder it opens.
    private static func scan(files: [URL], vault: String, installed: Bool) -> Connection {
        var other: (String, String)?
        for file in files {
            guard let data = try? Data(contentsOf: file), let json = try? JSONSerialization.jsonObject(with: data) else { continue }
            for entry in burrowEntries(in: json) {
                let words = strings(in: entry)
                guard let mcp = words.firstIndex(of: "mcp") else { continue }
                let folder = words.dropFirst(mcp + 1).first.map { URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath).standardizedFileURL.path } ?? ""
                let shown = (file.path as NSString).abbreviatingWithTildeInPath
                if folder == vault { return Connection(state: .thisVault, source: shown) }
                other = other ?? (folder, shown)
            }
        }
        if let other { return Connection(state: .otherVault(other.0), source: other.1) }
        return Connection(state: installed ? .notSetUp : .missing)
    }

    /// Every value stored under a key named "burrow", at any depth: Claude Code keeps servers per project.
    private static func burrowEntries(in json: Any) -> [Any] {
        if let object = json as? [String: Any] {
            return object.flatMap { key, value in (key == "burrow" ? [value] : []) + burrowEntries(in: value) }
        }
        if let list = json as? [Any] { return list.flatMap(burrowEntries) }
        return []
    }

    /// The command and its arguments, in order, whatever the file's shape.
    private static func strings(in json: Any) -> [String] {
        if let text = json as? String { return [text] }
        if let list = json as? [Any] { return list.flatMap(strings) }
        if let object = json as? [String: Any] { return ["command", "args"].flatMap { object[$0].map(strings) ?? [] } }
        return []
    }

    private static func listening(_ port: Int) async -> Bool {
        var request = URLRequest(url: URL(string: "http://127.0.0.1:\(port)/v1/models")!)
        request.timeoutInterval = 0.6
        return (try? await URLSession.shared.data(for: request)) != nil
    }

    // MARK: Setting up

    /// Adds Burrow to LM Studio's `mcp.json`, keeping every other server and a copy of the file as it was.
    static func addToLMStudio(vault: URL) throws -> String {
        let file = home.appendingPathComponent(".lmstudio/mcp.json")
        var root = try existing(file) ?? [:]
        var servers = root["mcpServers"] as? [String: Any] ?? [:]
        servers["burrow"] = ["command": command, "args": ["mcp", vault.standardizedFileURL.path]]
        root["mcpServers"] = servers
        try write(root, to: file)
        return "Added to LM Studio. Restart its chat to see the burrow tools."
    }

    /// Adds Burrow and the `burrow` agent to OpenCode's own settings, keeping what is there.
    static func addToOpenCode(vault: URL) throws -> String {
        let file = home.appendingPathComponent(".config/opencode/opencode.json")
        var root = try existing(file) ?? ["$schema": "https://opencode.ai/config.json"]
        var mcp = root["mcp"] as? [String: Any] ?? [:]
        mcp["burrow"] = ["type": "local", "command": [command, "mcp", vault.standardizedFileURL.path], "enabled": true]
        root["mcp"] = mcp
        var agents = root["agent"] as? [String: Any] ?? [:]
        if agents["burrow"] == nil {
            agents["burrow"] = ["description": "Answers from the Burrow vault only", "mode": "primary",
                                "prompt": "You answer from the user's Burrow vault. Use the burrow tools; name the file for each fact. If the vault does not hold the answer, say so.",
                                "tools": ["*": false, "burrow_*": true]]
        }
        root["agent"] = agents
        try write(root, to: file)
        return "Added to OpenCode, with a burrow agent for small local models."
    }

    /// Runs `claude mcp add` for the person, at user scope so every project sees the vault.
    static func addToClaudeCode(vault: URL) async throws -> String {
        let claude = ["/opt/homebrew/bin/claude", "/usr/local/bin/claude", home.appendingPathComponent(".local/bin/claude").path]
            .first { FileManager.default.isExecutableFile(atPath: $0) }
        guard let claude else { throw SetupError("Claude Code was not found.") }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: claude)
        process.arguments = ["mcp", "add", "--scope", "user", "burrow", "--", command, "mcp", vault.standardizedFileURL.path]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        try process.run()
        await Task.detached { process.waitUntilExit() }.value
        let said = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        guard process.terminationStatus == 0 else { throw SetupError(said.isEmpty ? "claude mcp add failed." : said) }
        return "Added to Claude Code for every project."
    }

    /// The file's settings, nil when there is no file yet. A file that can't be read as plain JSON (comments, a typo)
    /// is left alone rather than replaced.
    private static func existing(_ file: URL) throws -> [String: Any]? {
        guard let data = try? Data(contentsOf: file) else { return nil }
        if data.allSatisfy({ $0 == 32 || $0 == 10 || $0 == 13 || $0 == 9 }) { return nil }
        guard let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw SetupError("\((file.path as NSString).abbreviatingWithTildeInPath) has comments or isn't plain JSON, so Burrow left it alone. Copy the line instead.")
        }
        return root
    }

    private static func write(_ root: [String: Any], to file: URL) throws {
        try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        if FileManager.default.fileExists(atPath: file.path) {
            let copy = file.appendingPathExtension("before-burrow")
            try? FileManager.default.removeItem(at: copy)
            try FileManager.default.copyItem(at: file, to: copy)
        }
        let data = try JSONSerialization.data(withJSONObject: root, options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes])
        try data.write(to: file, options: .atomic)
    }

    struct SetupError: LocalizedError {
        let message: String
        init(_ message: String) { self.message = message }
        var errorDescription: String? { message }
    }
}
