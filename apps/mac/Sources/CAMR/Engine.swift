import Darwin
import Foundation
import SwiftUI

/// A model the memory can read with: its rooms are that model's own notes, so each model has its own memory folder.
struct ModelChoice: Identifiable, Hashable {
    let id: String  // the Hugging Face repo, already downloaded
    let name: String
    let size: String
    let note: String  // what it is good at, in a few words
}

let MODELS = [
    ModelChoice(id: "mlx-community/Qwen3-1.7B-4bit", name: "Qwen3 1.7B", size: "1.0 GB", note: "reasons · quickest"),
    ModelChoice(id: "mlx-community/Qwen3-4B-4bit", name: "Qwen3 4B", size: "2.3 GB", note: "reasons · best balance"),
    ModelChoice(id: "mlx-community/Qwen3-4B-Instruct-2507-4bit", name: "Qwen3 4B Instruct", size: "2.3 GB",
                note: "best memory recall · no reasoning"),
    ModelChoice(id: "mlx-community/Qwen3-8B-4bit", name: "Qwen3 8B", size: "4.6 GB", note: "reasons · strongest"),
]

/// The CAMR engine as a local process: started with the chosen model, watched as its weights load (its CAMR-LIVE
/// lines), then talked to over its local API with a token only this app knows.
@MainActor
final class Engine: ObservableObject {
    enum Phase: Equatable {
        case stopped, starting, ready
        case failed(String)
    }

    @Published var phase: Phase = .stopped
    @Published var model: ModelChoice = MODELS[1]
    @Published var lines: [String] = []

    let weights: WeightsModel
    private(set) var port: Int
    private var token = Engine.newToken()
    private var bound = false  // our own engine said it holds the port (its CAMR-PORT line): only then the token goes
    private var process: Process?
    private var stopping = false
    private var buffer = Data()

    init(weights: WeightsModel) {
        self.weights = weights
        self.port = Engine.freePort()
    }

    /// A port nothing listens on now, picked by the system, so no other process sits where the engine will be.
    static func freePort() -> Int {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        defer { close(fd) }
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")
        addr.sin_port = 0
        var len = socklen_t(MemoryLayout<sockaddr_in>.size)
        let bound = withUnsafeMutablePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                bind(fd, $0, len) == 0 && getsockname(fd, $0, &len) == 0
            }
        }
        return bound ? Int(UInt16(bigEndian: addr.sin_port)) : 49152 + Int.random(in: 0..<16000)
    }

    static func newToken() -> String {
        (UUID().uuidString + UUID().uuidString).replacingOccurrences(of: "-", with: "")
    }

    /// Where the engine lives: CAMR_ROOT, or the folder chosen before, or ~/.camr/engine (the installer's), or the
    /// developer checkout.
    var root: URL {
        let env = ProcessInfo.processInfo.environment
        let home = FileManager.default.homeDirectoryForCurrentUser
        let candidates = [env["CAMR_ROOT"], UserDefaults.standard.string(forKey: "engineRoot"),
                          home.appendingPathComponent(".camr/engine").path,
                          home.appendingPathComponent("Desktop/camr-build-wt/v2").path].compactMap { $0 }
        for c in candidates {
            let u = URL(fileURLWithPath: c)
            if FileManager.default.fileExists(atPath: u.appendingPathComponent("camr_engine").path)
                || FileManager.default.fileExists(atPath: u.appendingPathComponent("bin/python").path) {
                return u
            }
        }
        return URL(fileURLWithPath: candidates.last!)
    }

    var python: URL {
        let venv = root.appendingPathComponent(".venv/bin/python")
        if FileManager.default.fileExists(atPath: venv.path) { return venv }
        return root.appendingPathComponent("bin/python")
    }

    func memoryFolder(_ m: ModelChoice) -> String {
        let slug = m.id.split(separator: "/").last.map(String.init) ?? "model"
        // the reaches live beside this folder, so each model has its own: its rooms are its own notes.
        // CAMR_APP_MEMORY names another home for every model's folder (a rehearsal on a copy).
        if let home = ProcessInfo.processInfo.environment["CAMR_APP_MEMORY"] {
            return URL(fileURLWithPath: home).appendingPathComponent("\(slug)/default").path
        }
        return FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".camr/app/\(slug)/default").path
    }

    func start(_ m: ModelChoice? = nil) {
        if let m { model = m }
        stop()
        stopping = false
        port = Engine.freePort()
        token = Engine.newToken()
        bound = false
        phase = .starting
        lines = []
        weights.beginLoad(model: model.name)
        let p = Process()
        p.executableURL = python
        p.currentDirectoryURL = root
        p.arguments = ["-m", "camr_engine.app", "--port", String(port), "--memory", memoryFolder(model),
                       "--model", model.id, "--live"]
        var env = ProcessInfo.processInfo.environment
        env["CAMR_TOKEN"] = token
        env["PYTHONUNBUFFERED"] = "1"
        env["HF_HUB_OFFLINE"] = "1"
        p.environment = env
        let out = Pipe(), err = Pipe()
        p.standardOutput = out
        p.standardError = err
        out.fileHandleForReading.readabilityHandler = { [weak self] h in
            let d = h.availableData
            guard !d.isEmpty else { return }
            Task { @MainActor in self?.take(d) }
        }
        err.fileHandleForReading.readabilityHandler = { [weak self] h in
            let d = h.availableData
            guard !d.isEmpty, let s = String(data: d, encoding: .utf8) else { return }
            Task { @MainActor in self?.note(s) }
        }
        p.terminationHandler = { [weak self] proc in
            Task { @MainActor in  // only the engine running now counts: the one stopped for a new model does not
                guard let self, !self.stopping, self.process === proc else { return }
                let last = self.lines.suffix(3).joined(separator: " ")
                self.phase = .failed("The engine stopped (exit \(proc.terminationStatus)). \(last)")
            }
        }
        do {
            try p.run()
            process = p
        } catch {
            phase = .failed("Could not start the engine at \(python.path): \(error.localizedDescription)")
            return
        }
        Task { await waitReady() }
    }

    func stop() {
        stopping = true
        if let p = process, p.isRunning {
            p.terminate()
            p.waitUntilExit()
        }
        process = nil
        phase = .stopped
    }

    private func take(_ d: Data) {
        buffer.append(d)
        while let nl = buffer.firstIndex(of: 0x0A) {
            let line = buffer[buffer.startIndex..<nl]
            buffer.removeSubrange(buffer.startIndex...nl)
            guard let s = String(data: line, encoding: .utf8) else { continue }
            if s.hasPrefix("CAMR-LIVE "), let j = s.dropFirst(10).data(using: .utf8),
               let e = try? JSONSerialization.jsonObject(with: j) as? [String: Any] {
                weights.loadEvent(e)
            } else if s == "CAMR-PORT \(port)" {
                bound = true
            } else {
                note(s)
            }
        }
    }

    private func note(_ s: String) {
        for l in s.split(separator: "\n") where !l.contains("Fetching") {
            lines.append(String(l))
        }
        if lines.count > 300 { lines.removeFirst(lines.count - 300) }
    }

    private func waitReady() async {
        for _ in 0..<1200 {
            if case .failed = phase { return }
            guard process?.isRunning == true else { break }  // only our own engine counts as ready
            if bound, (try? await get("/api/chat/state")) != nil {
                phase = .ready
                weights.loadDone()
                return
            }
            try? await Task.sleep(nanoseconds: 250_000_000)
        }
        phase = .failed("The engine did not answer in 5 minutes.")
    }

    // MARK: the local API

    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    private func request(_ path: String, _ body: [String: Any]?) async throws -> [String: Any] {
        var r = URLRequest(url: URL(string: "http://127.0.0.1:\(port)\(path)")!)
        r.timeoutInterval = 600
        r.setValue(token, forHTTPHeaderField: "X-CAMR-Token")
        if let body {
            r.httpMethod = "POST"
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
            r.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (data, resp) = try await URLSession.shared.data(for: r)
        let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard code == 200 else {
            throw Failure(message: json["error"] as? String ?? "HTTP \(code)")
        }
        return json
    }

    func get(_ path: String) async throws -> [String: Any] { try await request(path, nil) }

    func post(_ path: String, _ body: [String: Any]) async throws -> [String: Any] { try await request(path, body) }
}

extension Dictionary where Key == String, Value == Any {
    func num(_ k: String) -> Double? {
        if let d = self[k] as? Double { return d }
        if let i = self[k] as? Int { return Double(i) }
        return nil
    }

    func str(_ k: String) -> String? { self[k] as? String }
    func dict(_ k: String) -> [String: Any]? { self[k] as? [String: Any] }
    func list(_ k: String) -> [[String: Any]] { self[k] as? [[String: Any]] ?? [] }
}
