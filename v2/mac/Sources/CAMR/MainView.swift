// The window: sidebar, the place you picked, and (for chat) the memory inspector.

import SwiftUI

enum Place: Hashable {
    case chat, memory, agents, browser, models, connections
    case shelf(String)

    var title: String {
        switch self {
        case .chat: return "Chat"
        case .memory: return "Memory"
        case .agents: return "Agents"
        case .browser: return "Browser"
        case .models: return "Models"
        case .connections: return "Connections"
        case let .shelf(name): return name
        }
    }

    var symbol: String {
        switch self {
        case .chat: return "bubble.left"
        case .memory: return "books.vertical"
        case .agents: return "person.2"
        case .browser: return "globe"
        case .models: return "cube"
        case .connections: return "powerplug"
        case .shelf: return "square.stack"
        }
    }
}

struct MainView: View {
    @ObservedObject var engine: Engine
    @StateObject private var chat: ChatStore
    @State private var place: Place? = .chat
    @State private var showMemory = true
    @StateObject private var browser = BrowserModel()

    init(engine: Engine) {
        self.engine = engine
        _chat = StateObject(wrappedValue: ChatStore(engine: engine))
    }

    var body: some View {
        NavigationSplitView {
            Sidebar(place: $place, chat: chat, model: engine.model)
                .navigationSplitViewColumnWidth(min: 210, ideal: 236, max: 300)
        } detail: {
            Group { switch place ?? .chat {
            case .chat:
                ChatView(chat: chat) { url in
                    browser.go(url.absoluteString)
                    place = .browser
                }
                    .inspector(isPresented: $showMemory) {
                        MemoryPanel(chat: chat)
                            .inspectorColumnWidth(min: 280, ideal: 320, max: 420)
                    }
                    .toolbar {
                        ToolbarItem(placement: .primaryAction) {
                            Button { showMemory.toggle() } label: { Label("Memory", systemImage: "sidebar.right") }
                                .help(showMemory ? "Hide what CAMR takes from memory" : "Show what CAMR takes from memory")
                        }
                    }
            case .memory:
                MemoryView(chat: chat)
            case .agents:
                AgentsView(engine: engine)
            case .models:
                ModelsView(engine: engine)
            case .connections:
                ConnectionsView(engine: engine)
            case .browser:
                BrowserView(model: browser)
            case let other:
                ComingNext(place: other)
            } }
            .transition(.opacity)
            .animation(.easeOut(duration: 0.16), value: place)
        }
        .task {
            await chat.refresh()
            await chat.loadChats()
            if !Script.steps.isEmpty { await Script.run(chat: chat, place: $place) }
        }
    }
}

struct Sidebar: View {
    @Binding var place: Place?
    @ObservedObject var chat: ChatStore
    let model: String

    var body: some View {
        List(selection: $place) {
            ForEach([Place.chat, .memory, .agents, .browser, .models, .connections], id: \.self) { p in
                Label(p.title, systemImage: p.symbol).tag(p)
            }
            if !chat.chats.isEmpty {
                Section("Recent chats") {
                    ForEach(chat.chats.prefix(6), id: \.id) { c in
                        Button {
                            place = .chat
                            Task { await chat.open(c.id) }
                        } label: {
                            Label(c.title, systemImage: "text.bubble").lineLimit(1)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            Section("Shelves") {
                ForEach(chat.shelves) { s in
                    HStack(spacing: 8) {
                        Label(s.label, systemImage: "books.vertical")
                        Spacer(minLength: 4)
                        MiniShelf(shelf: s)
                    }
                    .tag(Place.shelf(s.label))
                }
            }
        }
        .listStyle(.sidebar)
        .safeAreaInset(edge: .bottom) {
            HStack(spacing: 8) {
                Circle().fill(Channel.used).frame(width: 7, height: 7)
                Text(model.isEmpty ? "model" : model).font(.caption)
                Spacer()
            }
            .padding(.horizontal, 14).padding(.vertical, 10)
        }
    }
}

/// A shelf in three tiny spines: green when something on it was used this answer, blue when awake.
struct MiniShelf: View {
    let shelf: Shelf
    var body: some View {
        HStack(spacing: 1.5) {
            ForEach(0..<3, id: \.self) { i in
                RoundedRectangle(cornerRadius: 1)
                    .fill(i < shelf.used ? Channel.used : (shelf.memories > 0 ? Channel.ssd.opacity(0.75) : .clear))
                    .overlay(RoundedRectangle(cornerRadius: 1)
                        .strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [2, 1.5]))
                        .foregroundStyle(shelf.memories > 0 ? .clear : Color.white.opacity(0.3)))
                    .frame(width: 6, height: 4)
            }
        }
        .animation(.easeOut(duration: 0.25), value: shelf.used)
    }
}

struct ComingNext: View {
    let place: Place
    var body: some View {
        ContentUnavailableView {
            Label(place.title, systemImage: place.symbol)
        } description: {
            Text("This part of the app is designed and comes in the next build. Chat, your shelves and the browser work now.")
        }
        .navigationTitle(place.title)
    }
}
