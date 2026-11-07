import AppKit
import SwiftUI

@main
struct CAMRApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var world = World()

    var body: some Scene {
        WindowGroup("CAMR") {
            RootView(world: world, engine: world.engine, chat: world.chat, weights: world.weights)
                .frame(minWidth: 1100, minHeight: 700)
                .preferredColorScheme(.dark)
                .onAppear { delegate.world = world }
        }
        .windowStyle(.hiddenTitleBar)
        Settings { SettingsView(engine: world.engine) }
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("New Chat") { Task { await world.chat.newChat() } }.keyboardShortcut("n", modifiers: .command)
            }
            CommandMenu("View") {
                Button(world.expanded ? "Weights in the Sidebar" : "Weights Large") { world.expanded.toggle() }
                    .keyboardShortcut("e", modifiers: [.command])
            }
            CommandMenu("Memory") {
                Button("CAMR: Notes Already Read") { Task { await world.chat.setMode("camr") } }
                    .keyboardShortcut("1", modifiers: [.command])
                Button("RAG: Chunks Pasted as Text") { Task { await world.chat.setMode("rag") } }
                    .keyboardShortcut("2", modifiers: [.command])
                Button("Off: The Model Alone") { Task { await world.chat.setMode("off") } }
                    .keyboardShortcut("3", modifiers: [.command])
                Divider()
                Button("Compare CAMR · RAG · Off") { Task { await world.chat.compare() } }
                    .keyboardShortcut(.return, modifiers: [.option])
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
    @Published var expanded = false {  // the weights view large, beside the chat, for a projector
        didSet { weights.watched = expanded || showTensors }
    }
    @Published var showTensors = false {  // the weights view in the sidebar; it also shows itself while a model loads
        didSet { weights.watched = expanded || showTensors }
    }
    var played = false

    init() {
        engine = Engine(weights: weights)
        chat = ChatModel(engine: engine, weights: weights)
        // CAMR_MODEL (a rehearsal's choice, never saved), else the model picked before
        let wanted = ProcessInfo.processInfo.environment["CAMR_MODEL"] ?? UserDefaults.standard.string(forKey: "model")
        if let m = MODELS.first(where: { $0.id == wanted || $0.name == wanted }) { engine.model = m }
        engine.start()
        Script.startShots()
        Script.startHangWatch()
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
    @ObservedObject var weights: WeightsModel

    var body: some View {
        HStack(spacing: 0) {
            if !world.expanded {
                sidebar.frame(width: 330)
                Rectangle().fill(Theme.line).frame(width: 1)
            }
            ZStack {
                ChatView(chat: chat, engine: engine)
                WindowEdge(w: weights)
                if case .failed(let why) = engine.phase { failure(why) }
            }
            .frame(minWidth: 480)
            PreviewDock(center: PreviewCenter.shared)
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
                    WeightsView(w: weights, large: true)
                }
                .padding(.horizontal, 28)
                .padding(.bottom, 24)
                .frame(minWidth: 520, maxWidth: .infinity)
                .background(Theme.ink)
            }
        }
        .background(Theme.ink)
        .sheet(item: $chat.shelfAsk) { ask in ShelfSheet(chat: chat, ask: ask) }
        .onChange(of: engine.phase) { _, p in
            if p == .ready {
                Task { await chat.useShelves(); await chat.loadChats() }
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

            VStack(alignment: .leading, spacing: 8) {
                Text("MODEL").font(Theme.mono(10, .semibold)).foregroundStyle(Theme.faint)
                Menu {
                    ForEach(MODELS) { m in
                        Button("\(m.name) · \(m.size) · \(m.note)") { world.pick(m) }
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
                Menu {
                    Button("This app's model, with CAMR memory") { Task { await chat.setAgentModel(nil) } }
                    if !chat.ollamaModels.isEmpty {
                        Section("In Ollama (no CAMR memory: facts as text)") {
                            ForEach(chat.ollamaModels, id: \.self) { m in
                                Button(m) { Task { await chat.setAgentModel("ollama:" + m) } }
                            }
                        }
                    }
                    Section("Side by side (API, paid)") {
                        Button("Claude Sonnet 5.5") { Task { await chat.setAgentModel("claude-sonnet-5-5") } }
                    }
                } label: {
                    HStack {
                        Text("Builds with").font(Theme.mono(10)).foregroundStyle(Theme.faint)
                        Spacer()
                        Text(chat.agentModel.map { $0.hasPrefix("ollama:") ? String($0.dropFirst(7)) + " · Ollama" : $0 } ?? "this model + memory")
                            .font(Theme.mono(10, .semibold)).foregroundStyle(chat.agentModel == nil ? Theme.memory : Theme.model)
                    }
                }
                .menuStyle(.borderlessButton)
                .padding(.horizontal, 10)
                .task { await chat.loadAgentModels() }
                HStack(spacing: 6) {
                    Text(engine.model.note).font(Theme.mono(10)).foregroundStyle(Theme.faint)
                    Spacer()
                    Label("images: on-device OCR", systemImage: "text.viewfinder").font(Theme.mono(9))
                        .foregroundStyle(Theme.faint)
                        .help("Images, video frames and scanned pages dropped on the chat are read on this Mac by Apple's own text recognition; no vision model is loaded")
                }
            }

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("SHELVES").font(Theme.mono(10, .semibold)).foregroundStyle(Theme.faint)
                    Spacer()
                    Button {
                        chat.shelfName = ""
                        chat.shelfAsk = .add
                    } label: {
                        Label("New shelf", systemImage: "plus").font(Theme.mono(10))
                    }
                    .buttonStyle(.plain).foregroundStyle(Theme.dim)
                    .help("Make a shelf of your own")
                    Menu {
                        let have = Set(chat.shelves.map(\.name))
                        let missing = chat.curated.filter { !have.contains("curated-\($0.name)") }
                        if !missing.isEmpty {
                            Button("All \(missing.count) curated shelves") { Task { await chat.addCurated(missing.map(\.name)) } }
                            Divider()
                        }
                        ForEach(chat.curated, id: \.name) { c in
                            Button("\(c.label) · \(c.notes) rules") { Task { await chat.addCurated([c.name]) } }
                                .disabled(have.contains("curated-\(c.name)"))
                        }
                    } label: {
                        Label("Curated", systemImage: "books.vertical").font(Theme.mono(10))
                    }
                    .menuStyle(.borderlessButton).fixedSize().foregroundStyle(Theme.dim)
                    .help("Shelves of rules and corrections for coding, design, writing and more, read only when called")
                    .task { await chat.loadCurated() }
                }
                VStack(spacing: 1) {
                    shelfRow("auto", "Auto: file by meaning", nil)
                    ForEach(chat.shelves, id: \.name) { sh in shelfRow(sh.name, sh.label, sh) }
                }
                .padding(3)
                .background(RoundedRectangle(cornerRadius: 9).fill(Theme.panel))
                if let n = chat.shelfNotice {
                    Text(n).font(Theme.mono(10)).foregroundStyle(Theme.memory.opacity(0.85))
                        .fixedSize(horizontal: false, vertical: true)
                        .onTapGesture { chat.shelfNotice = nil }
                }
            }
            .disabled(engine.phase != .ready)

            do {
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

            VStack(alignment: .leading, spacing: 8) {
                Text("MEMORY").font(Theme.mono(10, .semibold)).foregroundStyle(Theme.faint)
                HStack(spacing: 4) {
                    modeButton("camr", "CAMR")
                    modeButton("rag", "RAG")
                    modeButton("off", "Off")
                }
                .padding(3)
                .background(RoundedRectangle(cornerRadius: 9).fill(Theme.panel))
                Text(modeText).font(Theme.ui(11)).foregroundStyle(Theme.dim).fixedSize(horizontal: false, vertical: true)
            }
            .disabled(engine.phase != .ready || chat.busy)

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

    private func shelfRow(_ id: String, _ title: String, _ shelf: ShelfInfo?) -> some View {
        let on = chat.shelf == id
        return Button { Task { await chat.pick(shelf: id) } } label: {
            HStack(spacing: 6) {
                Text(title).font(Theme.ui(12, .semibold)).lineLimit(1)
                Spacer(minLength: 4)
                if let s = shelf {
                    if s.called { Text("called").font(Theme.mono(9)).foregroundStyle(on ? Color.black.opacity(0.6) : Theme.faint) }
                    Text("\(s.moments)").font(Theme.mono(10)).foregroundStyle(on ? Color.black.opacity(0.6) : Theme.faint)
                }
            }
            .padding(.horizontal, 8).padding(.vertical, 4)
            .contentShape(Rectangle())
            .foregroundStyle(on ? Color.black : Theme.dim)
            .background(RoundedRectangle(cornerRadius: 6).fill(on ? Theme.memory : .clear))
        }
        .buttonStyle(.plain)
        .help(shelf == nil ? "Put each remembered moment on the shelf it is closest to by meaning"
              : "Remember on \(title). Right-click to rename, empty or remove.")
        .contextMenu {
            if let s = shelf {
                Button("Rename…") {
                    chat.shelfName = s.label
                    chat.shelfAsk = .rename(s)
                }
                Button("Empty…") { chat.shelfAsk = .empty(s) }
                Button("Remove…", role: .destructive) { chat.shelfAsk = .remove(s) }
            }
        }
    }

    private var modeText: String {
        switch chat.mode {
        case "rag": return "Conventional RAG: the 8 closest moments pasted in as text, read again every question."
        case "off": return "The model alone: nothing read, nothing kept."
        default: return "CAMR: one room of notes laid on the desk already read, its closest moments as words."
        }
    }

    private func modeButton(_ id: String, _ title: String) -> some View {
        Button { Task { await chat.setMode(id) } } label: {
            Text(title).font(Theme.ui(12, .semibold))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 7)
                .foregroundStyle(chat.mode == id ? Color.black : Theme.dim)
                .background(RoundedRectangle(cornerRadius: 7).fill(chat.mode == id ? (id == "off" ? Theme.text : Theme.memory) : .clear))
        }
        .buttonStyle(.plain)
        .help(id == "camr" ? "Answer from a room of saved notes (⌘1)" : id == "rag" ? "Answer from chunks pasted as text (⌘2)"
              : "Answer with no memory (⌘3)")
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

/// Make, rename, empty or remove a shelf. Emptying and removing say plainly what happens to the notes.
struct ShelfSheet: View {
    @ObservedObject var chat: ChatModel
    let ask: ChatModel.ShelfAsk

    private var title: String {
        switch ask {
        case .add: return "New shelf"
        case .rename(let s): return "Rename \(s.label)"
        case .empty(let s): return "Empty \(s.label)?"
        case .remove(let s): return "Remove \(s.label)?"
        }
    }

    private var message: String {
        switch ask {
        case .add: return "A shelf keeps one kind of memory together. Every question still reads every shelf."
        case .rename: return "The notes stay where they are."
        case .empty(let s):
            return "The \(s.moments) notes on this shelf stop being used. They are moved to the removed folder beside your memory, not deleted."
        case .remove(let s):
            return "The shelf goes, and its \(s.moments) notes stop being used. They are moved to the removed folder beside your memory, not deleted."
        }
    }

    private var asksName: Bool {
        switch ask {
        case .add, .rename: return true
        default: return false
        }
    }

    private var action: String {
        switch ask {
        case .add: return "Make shelf"
        case .rename: return "Rename"
        case .empty: return "Empty shelf"
        case .remove: return "Remove shelf"
        }
    }

    private func go() {
        let name = chat.shelfName.trimmingCharacters(in: .whitespacesAndNewlines)
        let current = ask
        chat.shelfAsk = nil
        Task {
            switch current {
            case .add: await chat.addShelf(name)
            case .rename(let s): await chat.renameShelf(s.name, name)
            case .empty(let s): await chat.emptyShelf(s.name)
            case .remove(let s): await chat.removeShelf(s.name)
            }
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(title).font(Theme.ui(16, .semibold)).foregroundStyle(Theme.text)
            Text(message).font(Theme.ui(13)).foregroundStyle(Theme.dim).fixedSize(horizontal: false, vertical: true)
            if asksName {
                TextField("Name", text: $chat.shelfName)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit { if !chat.shelfName.isEmpty { go() } }
            }
            HStack {
                Spacer()
                Button("Cancel") { chat.shelfAsk = nil }.keyboardShortcut(.cancelAction)
                Button(action) { go() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(asksName && chat.shelfName.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(20)
        .frame(width: 380)
        .background(Theme.ink)
    }
}
