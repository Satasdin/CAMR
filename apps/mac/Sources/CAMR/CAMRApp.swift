import AppKit
import SwiftUI

@main
struct CAMRApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var world = World()

    var body: some Scene {
        WindowGroup("CAMR") {
            RootView(world: world, engine: world.engine, chat: world.chat, code: world.code, weights: world.weights)
                .frame(minWidth: 1100, minHeight: 700)
                .preferredColorScheme(.dark)
                .onAppear { delegate.world = world }
        }
        .windowStyle(.hiddenTitleBar)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandMenu("View") {
                Button(world.expanded ? "Weights in the Sidebar" : "Weights Large") { world.expanded.toggle() }
                    .keyboardShortcut("e", modifiers: [.command])
            }
            CommandMenu("Memory") {
                Button("Memory On") { Task { await world.chat.setMemory(true) } }.keyboardShortcut("m", modifiers: [.command])
                Button("Memory Off") { Task { await world.chat.setMemory(false) } }
                    .keyboardShortcut("m", modifiers: [.command, .shift])
            }
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    var world: World?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationWillTerminate(_ notification: Notification) {
        MainActor.assumeIsolated { world?.engine.stop() }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

/// Everything the window shows, made once.
@MainActor
final class World: ObservableObject {
    let weights = WeightsModel()
    let engine: Engine
    let chat: ChatModel
    let code: CodeModel
    @Published var tab = "chat"
    @Published var expanded = false  // the weights view large, beside the chat, for a projector
    var played = false

    init() {
        engine = Engine(weights: weights)
        chat = ChatModel(engine: engine, weights: weights)
        code = CodeModel(engine: engine, weights: weights)
        let saved = UserDefaults.standard.string(forKey: "model")
        if let m = MODELS.first(where: { $0.id == saved }) { engine.model = m }
        engine.start()
        Script.startShots()
    }

    func pick(_ m: ModelChoice) {
        UserDefaults.standard.set(m.id, forKey: "model")
        chat.turns = []
        engine.start(m)
    }
}

struct RootView: View {
    @ObservedObject var world: World
    @ObservedObject var engine: Engine
    @ObservedObject var chat: ChatModel
    @ObservedObject var code: CodeModel
    @ObservedObject var weights: WeightsModel

    var body: some View {
        HStack(spacing: 0) {
            if !world.expanded {
                sidebar.frame(width: 330)
                Rectangle().fill(Theme.line).frame(width: 1)
            }
            ZStack {
                if world.tab == "chat" {
                    ChatView(chat: chat, engine: engine)
                } else {
                    CodeView(code: code, engine: engine)
                }
                if case .failed(let why) = engine.phase { failure(why) }
            }
            .frame(minWidth: 480)
            if world.expanded {
                Rectangle().fill(Theme.line).frame(width: 1)
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("CAMR · \(engine.model.name)").font(Theme.mono(12, .semibold)).foregroundStyle(Theme.text)
                        Spacer()
                        Button { withAnimation(.easeInOut(duration: 0.25)) { world.expanded = false } } label: {
                            Label("Sidebar  ⌘E", systemImage: "sidebar.left").font(Theme.mono(10))
                                .foregroundStyle(Theme.faint)
                        }
                        .buttonStyle(.plain)
                    }
                    .padding(.top, 20)
                    WeightsView(w: weights)
                }
                .padding(.horizontal, 28)
                .padding(.bottom, 24)
                .frame(minWidth: 520, maxWidth: .infinity)
                .background(Theme.ink)
            }
        }
        .background(Theme.ink)
        .onChange(of: engine.phase) { _, p in
            if p == .ready {
                Task { await chat.refresh(); await code.refresh() }
                if !world.played { world.played = true; Script.play(world) }
            }
        }
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 8) {
                Text("CAMR").font(Theme.mono(15, .bold)).foregroundStyle(Theme.text)
                Circle().fill(engine.phase == .ready ? Theme.memory : Theme.model).frame(width: 7, height: 7)
                    .glow(engine.phase == .ready ? Theme.memory : Theme.model, radius: 5)
                Spacer()
                Text(phaseText).font(Theme.mono(10)).foregroundStyle(Theme.faint)
            }
            .padding(.top, 28)

            HStack(spacing: 4) {
                tabButton("chat", "Chat", "bubble.left.and.bubble.right")
                tabButton("code", "Code", "chevron.left.forwardslash.chevron.right")
            }
            .padding(3)
            .background(RoundedRectangle(cornerRadius: 10).fill(Theme.panel))

            VStack(alignment: .leading, spacing: 8) {
                Text("MODEL").font(Theme.mono(10, .semibold)).foregroundStyle(Theme.faint)
                Menu {
                    ForEach(MODELS) { m in
                        Button("\(m.name) · \(m.size)") { world.pick(m) }
                    }
                } label: {
                    HStack {
                        Text(engine.model.name).font(Theme.ui(14, .semibold)).foregroundStyle(Theme.text)
                        Spacer()
                        Text(engine.model.size).font(Theme.mono(11)).foregroundStyle(Theme.dim)
                    }
                }
                .menuStyle(.borderlessButton)
                .padding(10)
                .background(RoundedRectangle(cornerRadius: 10).fill(Theme.panel))
            }

            Toggle(isOn: Binding(get: { world.tab == "chat" ? chat.memoryOn : code.memoryOn }, set: { on in
                if world.tab == "chat" { Task { await chat.setMemory(on) } } else { code.memoryOn = on; weights.memoryOn = on }
            })) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Memory").font(Theme.ui(14, .semibold)).foregroundStyle(Theme.text)
                    Text((world.tab == "chat" ? chat.memoryOn : code.memoryOn) ? "answers read what it remembers"
                         : "the model answers alone")
                        .font(Theme.ui(11)).foregroundStyle(Theme.dim)
                }
            }
            .toggleStyle(.switch)
            .tint(Theme.memory)
            .disabled(engine.phase != .ready)

            if world.expanded {
                Spacer()
            } else {
                WeightsView(w: weights)
                    .frame(maxHeight: .infinity)
                    .padding(.bottom, 4)
            }
            Button { withAnimation(.easeInOut(duration: 0.25)) { world.expanded.toggle() } } label: {
                Label(world.expanded ? "Weights in the sidebar" : "Weights large  ⌘E",
                      systemImage: world.expanded ? "sidebar.left" : "arrow.up.left.and.arrow.down.right")
                    .font(Theme.mono(10)).foregroundStyle(Theme.faint)
            }
            .buttonStyle(.plain)
            .padding(.bottom, 14)
        }
        .padding(.horizontal, 18)
        .background(Theme.panel.opacity(0.6))
    }

    private var phaseText: String {
        switch engine.phase {
        case .stopped: return "stopped"
        case .starting: return weights.loadedLayers > 0 ? "loading weights" : "starting"
        case .ready: return "ready"
        case .failed: return "stopped"
        }
    }

    private func tabButton(_ id: String, _ title: String, _ icon: String) -> some View {
        Button { world.tab = id } label: {
            Label(title, systemImage: icon).font(Theme.ui(13, .semibold))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .foregroundStyle(world.tab == id ? Color.black : Theme.dim)
                .background(RoundedRectangle(cornerRadius: 8).fill(world.tab == id ? Theme.text : .clear))
        }
        .buttonStyle(.plain)
    }

    private func failure(_ why: String) -> some View {
        VStack(spacing: 12) {
            Text("The engine stopped").font(Theme.ui(18, .semibold)).foregroundStyle(Theme.text)
            Text(why).font(Theme.mono(11)).foregroundStyle(Theme.dim).multilineTextAlignment(.center)
                .frame(maxWidth: 560)
            Button("Start again") { engine.start() }.buttonStyle(Pill(color: Theme.model))
        }
        .padding(28)
        .background(RoundedRectangle(cornerRadius: 14).fill(Theme.panel))
    }
}
