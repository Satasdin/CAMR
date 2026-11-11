import BurrowCore
import SwiftUI

struct MainWindow: View {
    let library: Library
    @Bindable var workspace: Workspace
    @State private var showInspector = true

    private var subtitle: String {
        if let progress = workspace.progress { return progress }
        guard let stats = workspace.stats else { return "" }
        return "\(stats.notes) notes, \(stats.files) files, \(stats.links) links"
    }

    var body: some View {
        NavigationSplitView {
            Sidebar(library: library, workspace: workspace)
                .navigationSplitViewColumnWidth(min: 220, ideal: 270, max: 400)
        } detail: {
            VStack(spacing: 0) {
                TabStrip(workspace: workspace)
                content
            }
            .inspector(isPresented: $showInspector) {
                InspectorPane(workspace: workspace)
                    .inspectorColumnWidth(min: 260, ideal: 300, max: 420)
            }
            .navigationTitle(workspace.name)
            .navigationSubtitle(subtitle)
            .toolbar { tools }
        }
        .overlay(alignment: .top) {
            if workspace.paletteOpen {
                Palette(workspace: workspace)
                    .padding(.top, 90)
                    .transition(.scale(scale: 0.97, anchor: .top).combined(with: .opacity))
            }
        }
        .animation(.spring(response: 0.25, dampingFraction: 1), value: workspace.paletteOpen)
        .safeAreaInset(edge: .bottom, spacing: 0) {
            VStack(spacing: 0) {
                if let warning = workspace.warning {
                    HStack(spacing: 8) {
                        Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.yellow)
                        Text(warning).lineLimit(2)
                        Spacer()
                        Button("Dismiss") { workspace.warning = nil }.buttonStyle(.link)
                    }
                    .padding(.horizontal, 14).padding(.vertical, 8).background(.bar)
                }
                StatusBar(workspace: workspace)
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in
            Task { await workspace.readAgain() }
        }
    }

    @ViewBuilder private var content: some View {
        switch workspace.currentTab?.content {
        case let .file(path):
            FilePage(workspace: workspace, document: workspace.document(path)).id(path)
        case .graph:
            GraphPage(workspace: workspace)
        case .ask:
            AskPage(workspace: workspace)
        case let .library(kind):
            LibraryPage(workspace: workspace, kind: kind)
        case let .conversations(program):
            ConversationsPage(workspace: workspace, program: program)
        case let .session(id):
            SessionPage(workspace: workspace, id: id)
        case .shelf:
            ShelfPage(workspace: workspace)
        case .programs:
            ProgramsPage(workspace: workspace)
        case let .ledger(branch):
            LedgerPage(workspace: workspace, branch: branch)
        case nil:
            EmptyPage(workspace: workspace)
        }
    }

    @ToolbarContentBuilder private var tools: some ToolbarContent {
        ToolbarItemGroup(placement: .navigation) {
            Button { workspace.goBack() } label: { Label("Back", systemImage: "chevron.backward") }
                .disabled(workspace.currentTab?.back.isEmpty ?? true)
            Button { workspace.goForward() } label: { Label("Forward", systemImage: "chevron.forward") }
                .disabled(workspace.currentTab?.forward.isEmpty ?? true)
        }
        ToolbarItemGroup(placement: .primaryAction) {
            if workspace.progress != nil { ProgressView().controlSize(.small) }
            Button { workspace.paletteOpen = true } label: { Label("Quick Open", systemImage: "magnifyingglass") }
                .help("Open anything or run a command (⌘K)")
            if workspace.currentPath?.isMarkdownPath == true {
                Button { workspace.isReading.toggle() } label: {
                    Label(workspace.isReading ? "Edit" : "Read", systemImage: workspace.isReading ? "pencil" : "book")
                }
                .help(workspace.isReading ? "Edit this note (⌘E)" : "Read this note (⌘E)")
            }
            if let path = workspace.currentPath {
                Button { Task { await workspace.toggleBookmark(path) } } label: {
                    Label(workspace.isBookmarked(path) ? "Remove Bookmark" : "Bookmark", systemImage: workspace.isBookmarked(path) ? "bookmark.fill" : "bookmark")
                }
                .help(workspace.isBookmarked(path) ? "Remove this file from Bookmarks" : "Bookmark this file")
            }
            Button { showInspector.toggle() } label: { Label("Details", systemImage: "sidebar.right") }
                .help("Show or hide links and outline")
        }
    }
}

struct TabStrip: View {
    let workspace: Workspace

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 2) {
                ForEach(workspace.tabs) { tab in TabButton(workspace: workspace, tab: tab) }
                Button { Task { await workspace.newNote() } } label: {
                    Image(systemName: "plus").frame(width: 26, height: 26).contentShape(Rectangle())
                }
                .buttonStyle(.plain).foregroundStyle(.secondary).help("New note (⌘N)").accessibilityLabel("New note")
            }
            .padding(.horizontal, 8).padding(.vertical, 4)
        }
        .background(.bar)
        .overlay(alignment: .bottom) { Divider() }
    }
}

struct TabButton: View {
    let workspace: Workspace
    let tab: Tab
    @State private var hovering = false

    private var active: Bool { workspace.activeTab == tab.id }
    private var icon: String {
        switch tab.content {
        case let .file(path): return path.isMarkdownPath ? "doc.text" : "chevron.left.forwardslash.chevron.right"
        case .graph: return "circle.hexagongrid"
        case .ask: return "bubble.left.and.text.bubble.right"
        case let .library(kind): return kind.symbol
        case .conversations, .session: return "point.3.connected.trianglepath.dotted"
        case .shelf: return "memorychip"
        case .programs: return "app.connected.to.app.below.fill"
        case .ledger: return "books.vertical"
        }
    }

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon).imageScale(.small).foregroundStyle(.secondary)
            Text(workspace.tabTitle(tab)).lineLimit(1).frame(maxWidth: 170, alignment: .leading)
            Button { workspace.close(tab) } label: { Image(systemName: "xmark").font(.system(size: 9, weight: .bold)).frame(width: 16, height: 16) }
                .buttonStyle(.plain).foregroundStyle(.secondary).opacity(hovering || active ? 1 : 0)
                .accessibilityLabel("Close \(workspace.tabTitle(tab))")
        }
        .font(.system(size: 12.5))
        .padding(.leading, 10).padding(.trailing, 6).frame(height: 28)
        .background(active ? Color.primary.opacity(0.11) : hovering ? Color.primary.opacity(0.05) : .clear, in: .rect(cornerRadius: 7))
        .contentShape(Rectangle())
        .onTapGesture { workspace.activeTab = tab.id }
        .onHover { hovering = $0 }
        .contextMenu {
            Button("Close Tab") { workspace.close(tab) }
            Button("Close Other Tabs") { workspace.tabs.filter { $0 != tab }.forEach(workspace.close) }
        }
    }
}

struct EmptyPage: View {
    let workspace: Workspace

    var body: some View {
        ZStack {
            Theme.page
            VStack(spacing: 14) {
                Text("Nothing open").font(.title2.weight(.semibold)).foregroundStyle(Theme.ink)
                HStack(spacing: 10) {
                    Button("New Note") { Task { await workspace.newNote() } }
                    Button("Quick Open") { workspace.paletteOpen = true }
                    Button("Library") { workspace.go(.library(.all)) }
                }
            }
        }
    }
}

/// Obsidian's status bar: a quiet line of counts in the bottom-right corner, about the open file or else the vault.
struct StatusBar: View {
    let workspace: Workspace

    private var items: [String] {
        if let path = workspace.currentPath {
            let text = workspace.document(path).text
            let words = text.split { $0.isWhitespace || $0.isNewline }.count
            var out = ["\(words.formatted()) words", "\(text.count.formatted()) characters"]
            let read = workspace.sessions(reading: path).count
            if read > 0 { out.append("read in \(read.counted("conversation"))") }
            let kept = workspace.ledger.citing(path).count
            if kept > 0 { out.append("\(kept.counted("Ledger commit"))") }
            return out
        }
        var out: [String] = []
        if let stats = workspace.stats { out += ["\(stats.notes.formatted()) notes", "\(stats.files.formatted()) files", "\(stats.links.formatted()) links"] }
        if !workspace.sessions.isEmpty { out.append(workspace.sessions.count.counted("conversation")) }
        if !workspace.ledger.commits.isEmpty { out.append(workspace.ledger.commits.count.counted("Ledger commit")) }
        let shelf = workspace.shelf.reduce(0) { $0 + $1.entry.bytes }
        if shelf > 0 { out.append("\(shelf.bytesText) on the Shelf") }
        return out
    }

    var body: some View {
        HStack(spacing: 14) {
            if let progress = workspace.progress {
                ProgressView().controlSize(.mini)
                Text(progress).lineLimit(1)
            }
            Spacer()
            ForEach(items, id: \.self) { Text($0) }
        }
        .font(.system(size: 11)).foregroundStyle(.secondary).monospacedDigit()
        .padding(.horizontal, 12).frame(height: 22)
        .background(.bar)
        .overlay(alignment: .top) { Divider() }
    }
}
