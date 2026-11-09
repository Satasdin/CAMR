// CAMR for Mac. Opens on Chat. The sidebar holds the places (Chat, Memory, Agents, Browser, Models,
// Connections) and your shelves; the inspector beside the chat shows what the model takes from memory.

import SwiftUI

/// Colours that mean one thing each, everywhere in the app.
enum Channel {
    static let ssd = Color(red: 0.157, green: 0.722, blue: 0.898)       // on the SSD, waking
    static let ssdRest = Color(red: 0.055, green: 0.251, blue: 0.314)   // a memory at rest on its shelf
    static let ram = Color(red: 1.0, green: 0.718, blue: 0.369)         // taken to the desk (RAM)
    static let used = Color(red: 0.616, green: 1.0, blue: 0.702)        // the model used it
    static let vault = Color(red: 0.616, green: 0.388, blue: 0.890)     // kept as words
    static let fault = Color(red: 0.933, green: 0.2, blue: 0.243)
}

@main
struct CAMRApp: App {
    @StateObject private var engine = Engine()

    var body: some Scene {
        WindowGroup("CAMR") {
            RootView()
                .environmentObject(engine)
                .preferredColorScheme(.dark)
                .containerBackground(Color.black, for: .window)
                .frame(minWidth: 1100, minHeight: 700)
                .onAppear { engine.start() }
                .onReceive(NotificationCenter.default.publisher(for: NSApplication.willTerminateNotification)) { _ in
                    engine.stop()
                }
        }
        .windowToolbarStyle(.unified)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
    }
}

struct RootView: View {
    @EnvironmentObject var engine: Engine

    var body: some View {
        ZStack {
            content.transition(.opacity)
        }
        .animation(.easeInOut(duration: 0.35), value: engine.phase == .ready)
    }

    @ViewBuilder private var content: some View {
        switch engine.phase {
        case .ready:
            MainView(engine: engine)
        case let .failed(why):
            ContentUnavailableView {
                Label("CAMR couldn’t start", systemImage: "exclamationmark.triangle")
            } description: {
                Text(why).textSelection(.enabled)
            } actions: {
                Button("Try again") { engine.start() }
            }
        case .starting:
            LoadingView(title: "Starting CAMR", detail: engine.hint.isEmpty ? "Opening your memory…" : engine.hint,
                        layer: 0, of: 1, gb: 0)
        case let .loading(layer, of, gb):
            LoadingView(title: "Loading \(engine.model.isEmpty ? "the model" : engine.model)",
                        detail: String(format: "layer %d of %d · %.1f GB into memory", layer, of, gb),
                        layer: layer, of: of, gb: gb)
        }
    }
}

/// The model loading into RAM: one cell per layer, filling amber as each layer arrives.
struct LoadingView: View {
    let title: String
    let detail: String
    let layer: Int
    let of: Int
    let gb: Double
    @Environment(\.accessibilityReduceMotion) private var still

    /// Before the first layer the engine has given no count, so a band travels; after it, each cell is a real layer.
    private var counted: Bool { of > 1 }

    var body: some View {
        VStack(spacing: 18) {
            TimelineView(.animation(paused: counted || still)) { t in
                let cells = max(of, 18)
                let head = t.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: 1.6) / 1.6 * Double(cells + 6) - 3
                LazyVGrid(columns: Array(repeating: GridItem(.fixed(10), spacing: 3), count: 18), spacing: 3) {
                    ForEach(0..<cells, id: \.self) { i in
                        RoundedRectangle(cornerRadius: 1.5)
                            .fill(counted ? (i < layer ? Channel.ram : Color.white.opacity(0.08))
                                          : Channel.ram.opacity(0.08 + 0.6 * max(0, 1 - abs(Double(i) - head) / 4)))
                            .frame(width: 10, height: 14)
                            .shadow(color: counted && i == layer - 1 ? Channel.ram.opacity(0.8) : .clear, radius: 4)
                            .animation(.linear(duration: 0.12), value: layer)
                    }
                }
            }
            .frame(width: 18 * 13)
            Text(title).font(.title3.weight(.semibold))
            Text(detail).font(.callout).foregroundStyle(.secondary).monospacedDigit()
                .contentTransition(.numericText())
                .animation(.easeOut(duration: 0.12), value: layer)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
