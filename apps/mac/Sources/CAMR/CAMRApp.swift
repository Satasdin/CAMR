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
            CommandGroup(replacing: .newItem) {
                Button("New Chat") { Task { await world.chat.newChat() } }.keyboardShortcut("n", modifiers: .command)
            }
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
    @Published var showTensors = false  // the weights view in the sidebar; it also shows itself while a model loads
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
        engine.start(m)  // the chat stays: each answer says which model wrote it
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
                Task { await chat.useShelves(); await chat.loadChats(); await code.refresh() }
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

            VStack(alignment: .leading, spacing: 8) {
                Text("REMEMBER ON").font(Theme.mono(10, .semibold)).foregroundStyle(Theme.faint)
                HStack(spacing: 4) {
                    shelfButton("auto", "Auto")
                    ForEach(chat.shelves, id: \.name) { sh in shelfButton(sh.name, sh.label) }
                }
                .padding(3)
                .background(RoundedRectangle(cornerRadius: 9).fill(Theme.panel))
            }
            .disabled(engine.phase != .ready)

            if world.tab == "chat" {
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text("CHATS").font(Theme.mono(10, .semibold)).foregroundStyle(Theme.faint)
                        Spacer()
                        Button { Task { await chat.newChat() } } label: {
                            Label("New  ⌘N", systemImage: "square.and.pencil").font(Theme.mono(10))
                        }
                        .buttonStyle(.plain).foregroundStyle(Theme.dim)
                    }
                    ForEach(chat.chats.prefix(world.showTensors ? 3 : 7), id: \.id) { c in
                        Button { Task { await chat.openChat(c.id) } } label: {
                            Text(c.title).font(Theme.ui(12)).foregroundStyle(Theme.dim).lineLimit(1)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.vertical, 3)
                        }
                        .buttonStyle(.plain)
                    }
                }
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

            if !world.expanded && (world.showTensors || engine.phase != .ready) {  // shown firing up, or when chosen
                WeightsView(w: weights)
                    .frame(maxHeight: .infinity)
                    .padding(.bottom, 4)
                    .transition(.opacity.combined(with: .move(edge: .bottom)))
            } else {
                Spacer()
            }
            HStack(spacing: 14) {
                Button { withAnimation(.easeInOut(duration: 0.25)) { world.showTensors.toggle() } } label: {
                    Label(world.showTensors ? "Hide tensors" : "Show tensors  ⌘T",
                          systemImage: world.showTensors ? "eye.slash" : "cpu")
                        .font(Theme.mono(10)).foregroundStyle(world.showTensors ? Theme.faint : Theme.memory)
                }
                .buttonStyle(.plain)
                .keyboardShortcut("t", modifiers: .command)
                Button { withAnimation(.easeInOut(duration: 0.25)) { world.expanded.toggle() } } label: {
                    Label(world.expanded ? "Sidebar" : "Large  ⌘E",
                          systemImage: world.expanded ? "sidebar.left" : "arrow.up.left.and.arrow.down.right")
                        .font(Theme.mono(10)).foregroundStyle(Theme.faint)
                }
                .buttonStyle(.plain)
            }
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

    private func shelfButton(_ id: String, _ title: String) -> some View {
        Button { Task { await chat.pick(shelf: id) } } label: {
            Text(title).font(Theme.ui(11, .semibold)).lineLimit(1).minimumScaleFactor(0.8)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 6)
                .foregroundStyle(chat.shelf == id ? Color.black : Theme.dim)
                .background(RoundedRectangle(cornerRadius: 7).fill(chat.shelf == id ? Theme.memory : .clear))
        }
        .buttonStyle(.plain)
        .help(id == "auto" ? "Put each remembered moment on the shelf it is closest to by meaning" : "Remember on \(title)")
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
