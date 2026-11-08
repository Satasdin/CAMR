// CAMR for Mac. Opens on Chat. The sidebar holds the places (Chat, Today, Memory, Agents, Browser, Models,
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

    var body: some View {
        VStack(spacing: 18) {
            LazyVGrid(columns: Array(repeating: GridItem(.fixed(10), spacing: 3), count: 18), spacing: 3) {
                ForEach(0..<max(of, 18), id: \.self) { i in
                    RoundedRectangle(cornerRadius: 1.5)
                        .fill(i < layer ? Channel.ram : Color.white.opacity(0.08))
                        .frame(width: 10, height: 14)
                        .animation(.linear(duration: 0.12), value: layer)
                }
            }
            .frame(width: 18 * 13)
            Text(title).font(.title3.weight(.semibold))
            Text(detail).font(.callout).foregroundStyle(.secondary).monospacedDigit()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// View state held in an object, not `@State`: this SDK's `@State` is a macro whose plugin ships only with Xcode,
/// and CAMR builds with the command-line tools alone.
final class Box<T>: ObservableObject {
    @Published var value: T
    init(_ value: T) { self.value = value }
}
