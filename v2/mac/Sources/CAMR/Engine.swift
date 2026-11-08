// The engine: CAMR's Python memory engine, started by this app as a child process and reached over 127.0.0.1.
//
// The app picks a free port and a secret token, starts `python -m camr_engine.app --port N --live` with
// CAMR_TOKEN set, and waits for the engine's `CAMR-PORT N` line. While the model loads, the engine prints one
// `CAMR-LIVE {...}` line per layer, which drives the loading screen. Every API call carries the token in
// X-CAMR-Token; the engine refuses calls without it. The engine stops by itself when this app goes away.

import Darwin
import Foundation

typealias JSON = [String: Any]

enum EngineError: LocalizedError {
    case notReady
    case refused(Int, String)
    case badReply

    var errorDescription: String? {
        switch self {
        case .notReady: return "CAMR's engine isn't running yet."
        case let .refused(code, why): return "\(why) (\(code))"
        case .badReply: return "The engine sent something this app couldn't read."
        }
    }
}

@MainActor
final class Engine: ObservableObject {
    enum Phase: Equatable {
        case starting
        case loading(layer: Int, of: Int, gb: Double)
        case ready
        case failed(String)
    }

    @Published private(set) var phase: Phase = .starting
    @Published private(set) var model = ""
    @Published private(set) var lastLines: [String] = []
    @Published private(set) var hint = ""

    private(set) var port = 0
    private let token = (UUID().uuidString + UUID().uuidString).replacingOccurrences(of: "-", with: "")
    private var process: Process?
    private var buffer = ""
    private var loadedBytes = 0

    /// Where the engine lives: CAMR_ENGINE_DIR, else the copy mac/build.sh installs in Application Support (outside
    /// the folders macOS protects, so starting it never stops on a privacy question).
    static var engineDir: URL {
        if let dir = ProcessInfo.processInfo.environment["CAMR_ENGINE_DIR"] { return URL(fileURLWithPath: dir) }
        return FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("CAMR/engine")
    }

    /// The memory this app keeps. CAMR_MEMORY_DIR overrides it; by default the Mac app keeps its own folder, apart
    /// from the older app's memories.
    static var memoryDir: URL {
        if let dir = ProcessInfo.processInfo.environment["CAMR_MEMORY_DIR"] { return URL(fileURLWithPath: dir) }
        return FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".camr/mac")
    }

    func start() {
        guard process == nil else { return }
        let dir = Engine.engineDir
        let python = dir.appendingPathComponent(".venv/bin/python")
        guard FileManager.default.isExecutableFile(atPath: python.path) else {
            phase = .failed("CAMR's engine wasn't found at \(dir.path). Set CAMR_ENGINE_DIR to the folder that holds camr_engine.")
            return
        }
        port = Engine.freePort()
        let memory = Engine.memoryDir
        try? FileManager.default.createDirectory(at: memory, withIntermediateDirectories: true)

        let p = Process()
        p.executableURL = python
        p.currentDirectoryURL = dir
        // the 4B by default: on the benchmarks the 1.7B was unreliable (DECISIONS.md); CAMR_MODEL picks another
        let model = ProcessInfo.processInfo.environment["CAMR_MODEL"] ?? "mlx-community/Qwen3-4B-Instruct-2507-4bit"
        p.arguments = ["-u", "-m", "camr_engine.app", "--port", String(port), "--live", "--model", model,
                       "--memory", memory.appendingPathComponent("default").path]
        var env = ProcessInfo.processInfo.environment
        env["CAMR_TOKEN"] = token
        env["CAMR_APP_MEMORY"] = memory.appendingPathComponent("app").path
        env["CAMR_PROJECTS"] = memory.appendingPathComponent("projects").path
        env["PYTHONUNBUFFERED"] = "1"
        p.environment = env

        let out = Pipe()
        p.standardOutput = out
        p.standardError = out
        out.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            Task { @MainActor in self?.take(text) }
        }
        p.terminationHandler = { [weak self] proc in
            Task { @MainActor in
                guard let self else { return }
                if self.phase != .ready || proc.terminationStatus != 0 {
                    let tail = self.lastLines.suffix(3).joined(separator: " ")
                    self.phase = .failed("The engine stopped (code \(proc.terminationStatus)). \(tail)")
                }
                self.process = nil
            }
        }
        do {
            try p.run()
            process = p
            // a silent engine is almost always macOS waiting on a privacy question: the engine's files are in a
            // protected folder (Desktop, Documents) and the app hasn't been allowed to read them yet
            Task { [weak self] in
                try? await Task.sleep(nanoseconds: 15_000_000_000)
                guard let self, self.phase == .starting, self.lastLines.isEmpty else { return }
                self.hint = "Waiting for macOS: if a dialog asks to let CAMR open files in your Desktop folder, click Allow. The engine's files are at \(dir.path)."
            }
        } catch {
            phase = .failed("Couldn't start the engine: \(error.localizedDescription)")
        }
    }

    func stop() {
        process?.terminate()
        process = nil
    }

    /// The engine's output, line by line: its port when it listens, each layer while the model loads.
    private func take(_ text: String) {
        buffer += text
        while let nl = buffer.firstIndex(of: "\n") {
            let line = String(buffer[..<nl])
            buffer = String(buffer[buffer.index(after: nl)...])
            lastLines = Array((lastLines + [line]).suffix(12))
            if line.hasPrefix("CAMR-LIVE "), let data = line.dropFirst(10).data(using: .utf8),
               let e = try? JSONSerialization.jsonObject(with: data) as? JSON {
                live(e)
            } else if line.hasPrefix("CAMR-PORT ") {
                Task { await self.confirm() }
            }
        }
    }

    private func live(_ e: JSON) {
        switch e["kind"] as? String {
        case "load":
            loadedBytes += e["bytes"] as? Int ?? 0
            if let repo = e["repo"] as? String { model = Engine.shortName(repo) }
            phase = .loading(layer: (e["layer"] as? Int ?? 0) + 1, of: e["layers"] as? Int ?? 1,
                             gb: Double(loadedBytes) / 1e9)
        case "loaded":
            if let repo = e["repo"] as? String { model = Engine.shortName(repo) }
        default:
            break
        }
    }

    /// Ready once the engine answers a real call with the token.
    private func confirm() async {
        for _ in 0..<40 {
            if (try? await get("/api/chat/state")) != nil {
                phase = .ready
                return
            }
            try? await Task.sleep(nanoseconds: 250_000_000)
        }
        phase = .failed("The engine started but didn't answer.")
    }

    static func shortName(_ repo: String) -> String {
        let last = repo.split(separator: "/").last.map(String.init) ?? repo
        return last.replacingOccurrences(of: "-4bit", with: "").replacingOccurrences(of: "-MLX", with: "").lowercased()
    }

    // MARK: calls

    func get(_ path: String, _ query: [String: String] = [:]) async throws -> JSON {
        var c = URLComponents(string: "http://127.0.0.1:\(port)\(path)")!
        if !query.isEmpty { c.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) } }
        var r = URLRequest(url: c.url!)
        r.setValue(token, forHTTPHeaderField: "X-CAMR-Token")
        return try await send(r)
    }

    func post(_ path: String, _ body: JSON = [:]) async throws -> JSON {
        var r = URLRequest(url: URL(string: "http://127.0.0.1:\(port)\(path)")!)
        r.httpMethod = "POST"
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        r.setValue(token, forHTTPHeaderField: "X-CAMR-Token")
        r.httpBody = try JSONSerialization.data(withJSONObject: body)
        return try await send(r)
    }

    private func send(_ r: URLRequest) async throws -> JSON {
        guard port > 0 else { throw EngineError.notReady }
        var r = r
        r.timeoutInterval = 120
        let (data, response) = try await URLSession.shared.data(for: r)
        let code = (response as? HTTPURLResponse)?.statusCode ?? 0
        let json = (try? JSONSerialization.jsonObject(with: data)) as? JSON
        if code != 200 { throw EngineError.refused(code, json?["error"] as? String ?? "refused") }
        guard let json else { throw EngineError.badReply }
        return json
    }

    /// A port nothing is listening on: bind to port 0, read what the system gave, let it go.
    static func freePort() -> Int {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        defer { close(fd) }
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = 0
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")
        var len = socklen_t(MemoryLayout<sockaddr_in>.size)
        _ = withUnsafePointer(to: &addr) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(fd, $0, len) } }
        _ = withUnsafeMutablePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { getsockname(fd, $0, &len) }
        }
        return Int(UInt16(bigEndian: addr.sin_port))
    }
}
