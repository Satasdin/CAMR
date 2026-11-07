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
                case "type":  // as a person types: one character at a time, for measuring how the window keeps up
                    for ch in arg {
                        world.chat.draft += String(ch)
                        try? await Task.sleep(nanoseconds: 30_000_000)
                    }
                    world.chat.draft = ""
                case "shelf-add":
                    await world.chat.addShelf(arg)
                case "shelf-remove":
                    await world.chat.removeShelf(arg)
                case "shelf-empty":
                    await world.chat.emptyShelf(arg)
                case "shelf-pick":
                    await world.chat.pick(shelf: arg)
                case "preview-last":
                    let text = world.chat.turns.last?.text ?? ""
                    if let page = AnswerText.blocks(text).first(where: { $0.code })?.text { PreviewCenter.shared.show(code: page) }
                case "answers":  // what the person will answer when the agent asks, in order
                    world.chat.scriptAnswers = arg.split(separator: "|").map { $0.trimmingCharacters(in: .whitespaces) }
                case "preview-html":
                    PreviewCenter.shared.show(code: arg)
                case "preview-file":
                    if let page = try? String(contentsOfFile: arg, encoding: .utf8) { PreviewCenter.shared.show(code: page) }
                case "preview-shot":
                    if let dir = env["CAMR_SNAPSHOT_DIR"] {
                        await PreviewCenter.shared.savePage(to: URL(fileURLWithPath: dir).appendingPathComponent("\(arg).png"))
                    }
                case "preview-scripts":
                    PreviewCenter.shared.scripts = arg == "on"
                case "preview-inspect":
                    print("PREVIEW-INSPECT \(await PreviewCenter.shared.inspect())")
                    fflush(stdout)
                case "preview-phone":
                    PreviewCenter.shared.phone = arg != "off"
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

    /// CAMR_HANG_LOG=path: a watchdog for measuring. Every 20 ms a thread asks the main thread to run an empty block
    /// and times how long that took; once a second it appends one line to the file: seconds since launch, the
    /// longest wait that second (ms), and the main thread's stall time that second (the waits of 50 ms or more).
    nonisolated static func startHangWatch() {
        guard let path = ProcessInfo.processInfo.environment["CAMR_HANG_LOG"] else { return }
        FileManager.default.createFile(atPath: path, contents: nil)
        guard let out = FileHandle(forWritingAtPath: path) else { return }
        let thread = Thread {
            let start = DispatchTime.now().uptimeNanoseconds
            var second = 0, worst = 0.0, stalled = 0.0
            while true {
                let t0 = DispatchTime.now().uptimeNanoseconds
                let sem = DispatchSemaphore(value: 0)
                DispatchQueue.main.async { sem.signal() }
                sem.wait()
                let now = DispatchTime.now().uptimeNanoseconds
                let ms = Double(now - t0) / 1e6
                worst = max(worst, ms)
                if ms >= 50 { stalled += ms }
                let s = Int((now - start) / 1_000_000_000)
                if s != second {
                    out.write(String(format: "%d %.1f %.1f\n", second, worst, stalled).data(using: .utf8)!)
                    second = s
                    worst = 0
                    stalled = 0
                }
                usleep(20_000)
            }
        }
        thread.qualityOfService = .userInteractive
        thread.start()
    }

    /// The window as drawn now, saved as a PNG.
    static func snapshot(_ url: URL) {
        guard let view = NSApp.windows.first(where: { $0.isVisible })?.contentView else { return }
        guard let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { return }
        view.cacheDisplay(in: view.bounds, to: rep)
        try? rep.representation(using: .png, properties: [:])?.write(to: url)
    }
}
