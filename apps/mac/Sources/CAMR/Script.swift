import AppKit
import SwiftUI

/// A rehearsal: CAMR_SCRIPT names a file of lines, played into Chat once the engine is ready ("remember: …" keeps
/// a moment, "ask: …" asks, "memory: off" / "memory: on" switches memory, "wait: 2" pauses, "code: /path" opens
/// that folder in Code, "task: …" runs a Code task there). With CAMR_SNAPSHOT_DIR set, the window is saved as a PNG
/// every half second while it plays, for screenshots of the real app.
@MainActor
enum Script {
    static func play(_ world: World) {
        let env = ProcessInfo.processInfo.environment
        guard let path = env["CAMR_SCRIPT"], let text = try? String(contentsOfFile: path, encoding: .utf8) else { return }
        let shots = env["CAMR_SNAPSHOT_DIR"].map { URL(fileURLWithPath: $0) }
        if let shots { try? FileManager.default.createDirectory(at: shots, withIntermediateDirectories: true) }
        var n = 0
        let timer = shots.map { dir in
            Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in
                MainActor.assumeIsolated {
                    n += 1
                    snapshot(dir.appendingPathComponent(String(format: "shot-%04d.png", n)))
                }
            }
        }
        Task {
            for raw in text.split(separator: "\n") {
                let line = raw.trimmingCharacters(in: .whitespaces)
                guard let colon = line.firstIndex(of: ":"), !line.hasPrefix("#") else { continue }
                let verb = line[..<colon].lowercased()
                let arg = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
                switch verb {
                case "remember", "ask":
                    world.tab = "chat"
                    world.chat.draft = arg
                    await world.chat.send(remember: verb == "remember")
                case "memory":
                    await world.chat.setMemory(arg != "off")
                case "wait":
                    try? await Task.sleep(nanoseconds: UInt64((Double(arg) ?? 1) * 1e9))
                case "code":
                    world.tab = "code"
                    _ = try? await world.engine.post("/api/code/workspace", ["path": arg])
                    await world.code.refresh()
                case "task":
                    world.tab = "code"
                    world.code.draft = arg
                    await world.code.start()
                default:
                    break
                }
                try? await Task.sleep(nanoseconds: 600_000_000)
            }
            try? await Task.sleep(nanoseconds: 1_500_000_000)
            timer?.invalidate()
            if env["CAMR_SCRIPT_QUIT"] == "1" { NSApp.terminate(nil) }
        }
    }

    /// The window as drawn now, saved as a PNG.
    static func snapshot(_ url: URL) {
        guard let view = NSApp.windows.first(where: { $0.isVisible })?.contentView else { return }
        guard let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { return }
        view.cacheDisplay(in: view.bounds, to: rep)
        try? rep.representation(using: .png, properties: [:])?.write(to: url)
    }
}
