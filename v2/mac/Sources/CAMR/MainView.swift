// The window: sidebar, the place you picked, and (for chat) the memory inspector.

import SwiftUI

enum Place: Hashable {
    case chat, today, memory, agents, browser, models, connections
    case shelf(String)

    var title: String {
        switch self {
        case .chat: return "Chat"
        case .today: return "Today"
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
        case .today: return "sun.max"
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
    @StateObject private var place = Box<Place?>(.chat)
    @StateObject private var showMemory = Box(true)

    init(engine: Engine) {
        self.engine = engine
        _chat = StateObject(wrappedValue: ChatStore(engine: engine))
    }

    var body: some View {
        NavigationSplitView {
            Sidebar(place: $place.value, chat: chat, model: engine.model)
                .navigationSplitViewColumnWidth(min: 210, ideal: 236, max: 300)
        } detail: {
            switch place.value ?? .chat {
            case .chat:
                ChatView(chat: chat)
                    .inspector(isPresented: $showMemory.value) {
                        MemoryPanel(chat: chat)
                            .inspectorColumnWidth(min: 280, ideal: 320, max: 420)
                    }
                    .toolbar {
                        ToolbarItem(placement: .primaryAction) {
                            Button { showMemory.value.toggle() } label: { Label("Memory", systemImage: "sidebar.right") }
                                .help(showMemory.value ? "Hide what CAMR takes from memory" : "Show what CAMR takes from memory")
                        }
                    }
            case .browser:
                BrowserView()
            case let other:
                ComingNext(place: other)
            }
        }
        .task { await chat.refresh() }
    }
}

struct Sidebar: View {
    @Binding var place: Place?
    @ObservedObject var chat: ChatStore
    let model: String

    var body: some View {
        List(selection: $place) {
            ForEach([Place.chat, .today, .memory, .agents, .browser, .models, .connections], id: \.self) { p in
                Label(p.title, systemImage: p.symbol).tag(p)
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
