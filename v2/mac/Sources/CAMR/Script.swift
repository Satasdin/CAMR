// A test mode for building without anyone at the screen: with CAMR_SCRIPT set, the app runs a list of steps and
// saves pictures of its own window (an app may always draw its own window; no screen-recording permission).
//
//   CAMR_SCRIPT='[{"size":[1440,900]},{"go":"chat"},{"ask":"Where does my sister live?"},{"wait":"answer"},
//                 {"snap":"chat"},{"go":"memory"},{"wait":1.5},{"snap":"memory"},{"quit":true}]'
//   CAMR_SNAPSHOT_DIR=/some/folder   (PNG files, one per "snap")
//
// These pictures are for layout and content only: an app drawing itself cannot paint Liquid Glass, so the sidebar and
// inspector come out wrong. To judge the look, capture the real window: screencapture -x -o -l<window number> out.png.
//
// Steps: size [w,h] · go <place> · ask <text> · attach <file path> · wait <seconds | "answer" | "ready"> · snap <name> · quit.

import AppKit
import SwiftUI

@MainActor
enum Script {
    static var steps: [JSON] {
        guard let raw = ProcessInfo.processInfo.environment["CAMR_SCRIPT"], let data = raw.data(using: .utf8),
              let list = try? JSONSerialization.jsonObject(with: data) as? [JSON] else { return [] }
        return list
    }

    static func run(chat: ChatStore, place: Binding<Place?>) async {
        let dir = URL(fileURLWithPath: ProcessInfo.processInfo.environment["CAMR_SNAPSHOT_DIR"] ?? NSTemporaryDirectory())
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        for step in steps {
            if let size = step["size"] as? [Double], size.count == 2, let w = window() {
                w.setFrame(NSRect(x: 60, y: 60, width: size[0], height: size[1]), display: true)
            }
            if let p = step["go"] as? String { place.wrappedValue = Place(named: p) }
            if let text = step["ask"] as? String { chat.send(text) }
            if let path = step["attach"] as? String { chat.attach(URL(fileURLWithPath: path)) }
            if let wait = step["wait"] {
                if let s = wait as? Double { try? await Task.sleep(nanoseconds: UInt64(s * 1e9)) }
                if wait as? String == "answer" {
                    for _ in 0..<600 where chat.busy { try? await Task.sleep(nanoseconds: 100_000_000) }
                    try? await Task.sleep(nanoseconds: 600_000_000)
                }
            }
            if let name = step["snap"] as? String {
                try? await Task.sleep(nanoseconds: 300_000_000)
                snap(dir.appendingPathComponent("\(name).png"))
            }
            if step["quit"] as? Bool == true { NSApp.terminate(nil) }
        }
    }

    static func window() -> NSWindow? { NSApp.windows.first { $0.isVisible && $0.contentView != nil } }

    /// The window's own drawing, as a PNG.
    static func snap(_ url: URL) {
        guard let view = window()?.contentView?.superview ?? window()?.contentView,
              let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { return }
        view.cacheDisplay(in: view.bounds, to: rep)
        try? rep.representation(using: .png, properties: [:])?.write(to: url)
    }
}

extension Place {
    init?(named: String) {
        switch named {
        case "chat": self = .chat
        case "today": self = .today
        case "memory": self = .memory
        case "agents": self = .agents
        case "browser": self = .browser
        case "models": self = .models
        case "connections": self = .connections
        default: self = .shelf(named)
        }
    }
}
