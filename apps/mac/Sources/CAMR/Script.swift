import AppKit
import SwiftUI

/// A rehearsal: CAMR_SCRIPT names a file of lines, played into Chat once the engine is ready ("remember: …" keeps
/// a moment, "ask: …" asks, "compare: …" asks with CAMR, RAG and Off side by side, "mode: camr|rag|off" picks how
/// memory is read, "memory: off" / "memory: on" switches memory, "wait: 2" pauses, "view: large" shows the weights
/// large, "shot: name" saves the window now as name.png). With CAMR_SNAPSHOT_DIR set, the window is saved as a PNG
/// every quarter second while it plays, for screenshots of the real app.
@MainActor
enum Script {
    static var timer: Timer?

    /// Snapshots from launch on (the weights loading too), when CAMR_SNAPSHOT_DIR is set: every 0.25 s.
    static func startShots() {
        // CAMR_WINDOW=1600x1000: a rehearsal's window size, for screenshots at a projector's shape
        if let size = ProcessInfo.processInfo.environment["CAMR_WINDOW"]?.split(separator: "x").compactMap({ Double($0) }),
           size.count == 2 {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
                guard let win = NSApp.windows.first(where: { $0.isVisible }) else { return }
                win.setFrame(NSRect(x: 40, y: 40, width: size[0], height: size[1]), display: true)
            }
        }
        guard let dir = ProcessInfo.processInfo.environment["CAMR_SNAPSHOT_DIR"].map({ URL(fileURLWithPath: $0) })
        else { return }
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        var n = 0
        timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { _ in
            MainActor.assumeIsolated {
                n += 1
                snapshot(dir.appendingPathComponent(String(format: "shot-%04d.png", n)))
            }
        }
    }

    static func play(_ world: World) {
        let env = ProcessInfo.processInfo.environment
        guard let path = env["CAMR_SCRIPT"], let text = try? String(contentsOfFile: path, encoding: .utf8) else { return }
        Task {
            for _ in 0..<40 where world.chat.shelves.isEmpty {  // shelves on before the first line
                try? await Task.sleep(nanoseconds: 250_000_000)
            }
            for raw in text.split(separator: "\n") {
                let line = raw.trimmingCharacters(in: .whitespaces)
                guard let colon = line.firstIndex(of: ":"), !line.hasPrefix("#") else { continue }
                let verb = line[..<colon].lowercased()
                let arg = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
                switch verb {
                case "remember", "ask":
                    world.chat.draft = arg
                    await world.chat.send(remember: verb == "remember")
                case "compare":
                    world.chat.draft = arg
                    await world.chat.compare()
                case "new":
                    await world.chat.newChat()
                case "mode":
                    await world.chat.setMode(arg)
                case "shot":
                    if let dir = env["CAMR_SNAPSHOT_DIR"] {
                        snapshot(URL(fileURLWithPath: dir).appendingPathComponent("\(arg).png"))
                    }
                case "attach":
                    world.chat.attach(URL(fileURLWithPath: arg))
                    while world.chat.turns.last?.pending ?? true { try? await Task.sleep(nanoseconds: 300_000_000) }
                case "research":
                    world.chat.draft = arg
                    await world.chat.send(.research)
                case "model":
                    if let m = MODELS.first(where: { $0.name.contains(arg) }) {
                        world.pick(m)
                        for _ in 0..<600 where world.engine.phase != .ready {
                            try? await Task.sleep(nanoseconds: 250_000_000)
                        }
                        try? await Task.sleep(nanoseconds: 1_500_000_000)  // the shelves on and warmed
                    }
                case "view":
                    world.expanded = arg == "large"
                    world.showTensors = arg != "off"
                case "memory":
                    await world.chat.setMemory(arg != "off")
                case "wait":
                    try? await Task.sleep(nanoseconds: UInt64((Double(arg) ?? 1) * 1e9))
                default:
                    break
                }
                try? await Task.sleep(nanoseconds: 600_000_000)
            }
            try? await Task.sleep(nanoseconds: 1_500_000_000)
            timer?.invalidate()
            timer = nil
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
