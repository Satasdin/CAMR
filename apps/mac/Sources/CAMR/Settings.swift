import AppKit
import SwiftUI

/// What a person can set (⌘,), kept in UserDefaults: how much of the conversation the model reads, how long an
/// answer may be, and whether a thinking model shows its reasoning by default.
@MainActor
final class Prefs: ObservableObject {
    static let shared = Prefs()

    @Published var turns: Int { didSet { UserDefaults.standard.set(turns, forKey: "turns") } }
    @Published var maxTokens: Int { didSet { UserDefaults.standard.set(maxTokens, forKey: "maxTokens") } }
    @Published var reasoning: Bool { didSet { UserDefaults.standard.set(reasoning, forKey: "reasoning") } }

    init() {
        let d = UserDefaults.standard
        turns = d.object(forKey: "turns") as? Int ?? 6
        maxTokens = d.object(forKey: "maxTokens") as? Int ?? 700
        reasoning = d.object(forKey: "reasoning") as? Bool ?? true
    }
}

struct SettingsView: View {
    @ObservedObject var prefs = Prefs.shared
    let engine: Engine

    var body: some View {
        Form {
            Section("Conversation") {
                Stepper("Reads the last \(prefs.turns) turns", value: $prefs.turns, in: 1...20)
                Picker("Longest answer", selection: $prefs.maxTokens) {
                    ForEach([300, 700, 1500, 3000], id: \.self) { Text("\($0) tokens").tag($0) }
                }
                Toggle("Show a thinking model's reasoning", isOn: $prefs.reasoning)
            }
            Section("Memory") {
                LabeledContent("Each shelf's notes on the SSD",
                               value: "at most \(ProcessInfo.processInfo.environment["CAMR_SHELF_DISK_GB"] ?? "8") GB; colder notes are read as words")
                LabeledContent("Folder", value: engine.memoryFolder(engine.model).replacingOccurrences(
                    of: FileManager.default.homeDirectoryForCurrentUser.path, with: "~"))
                Button("Show in Finder") {
                    let url = URL(fileURLWithPath: engine.memoryFolder(engine.model)).deletingLastPathComponent()
                    NSWorkspace.shared.activateFileViewerSelecting([url])
                }
            }
            Section("Images") {
                LabeledContent("Images, video frames and scanned pages are read by",
                               value: "the Mac's on-device text recognition (Vision)")
            }
        }
        .formStyle(.grouped)
        .frame(width: 520, height: 420)
        .preferredColorScheme(.dark)
    }
}
