import BurrowCore
import SwiftUI

/// ⌘K: type part of a name to open it, or the name of a command to run it.
struct Palette: View {
    @Bindable var workspace: Workspace
    @State private var text = ""
    @State private var selected = 0
    @FocusState private var focused: Bool

    private struct Item: Identifiable {
        let id: String
        let title: String
        let detail: String
        let icon: String
        let run: @MainActor () -> Void
    }

    private var commands: [Item] {
        let w = workspace
        var out: [Item] = [
            Item(id: "c-new", title: "New Note", detail: "⌘N", icon: "square.and.pencil") { Task { await w.newNote() } },
            Item(id: "c-day", title: "Today's Note", detail: "⇧⌘D", icon: "calendar") { Task { await w.dailyNote() } },
            Item(id: "c-folder", title: "New Folder", detail: "⇧⌘N", icon: "folder.badge.plus") { Task { await w.newFolder() } },
            Item(id: "c-link", title: "Link a Folder…", detail: "", icon: "link") { pickLinkedFolder(w) },
            Item(id: "c-library", title: "Library", detail: "⌘1", icon: "square.grid.2x2") { w.go(.library(.all)) },
            Item(id: "c-documents", title: "Documents", detail: "", icon: "doc.richtext") { w.go(.library(.documents)) },
            Item(id: "c-conversations", title: "Conversations", detail: "⌘2", icon: "point.3.connected.trianglepath.dotted") { w.go(.conversations(nil)) },
            Item(id: "c-shelf", title: "Shelf", detail: "⌘3", icon: "memorychip") { w.go(.shelf) },
            Item(id: "c-programs", title: "Programs", detail: "⌘4", icon: "app.connected.to.app.below.fill") { w.go(.programs) },
            Item(id: "c-ledger", title: "Ledger", detail: "⌘5", icon: "books.vertical") { w.go(.ledger(nil)) },
            Item(id: "c-graph", title: "Map", detail: "⇧⌘G", icon: "circle.hexagongrid") { w.go(.graph) },
            Item(id: "c-search", title: "Search Vault", detail: "⇧⌘F", icon: "magnifyingglass") { w.sidebarMode = .search },
            Item(id: "c-read", title: "Read Vault Again", detail: "⌘R", icon: "arrow.clockwise") { Task { await w.readAgain() } },
        ]
        return out
    }

    private func score(_ query: String, _ candidate: String) -> Int? {
        let q = Array(query.lowercased())
        let c = Array(candidate.lowercased())
        var score = 0
        var at = 0
        var last = -1
        for letter in q {
            guard let found = c[at...].firstIndex(of: letter) else { return nil }
            if found == last + 1 { score += 6 }
            if found == 0 || !c[found - 1].isLetter { score += 8 }
            score -= min(3, found - at)
            at = found + 1
            last = found
        }
        return score - c.count / 8
    }

    private var items: [Item] {
        let w = workspace
        let query = text.trimmingCharacters(in: .whitespaces)
        func open(_ path: String) -> Item {
            Item(id: path, title: path.title, detail: path.folderPath, icon: path.isMarkdownPath ? "doc.text" : "chevron.left.forwardslash.chevron.right") {
                w.go(.file(path), newTab: NSEvent.modifierFlags.contains(.command))
            }
        }
        if query.isEmpty {
            let open_ = w.tabs.compactMap { tab -> String? in if case let .file(path) = tab.content { return path } else { return nil } }
            return open_.reversed().map(open) + commands.prefix(5)
        }
        var ranked: [(Int, Item)] = []
        for command in commands { if let s = score(query, command.title) { ranked.append((s + 2, command)) } }
        for file in w.map.files {
            if let s = score(query, file.path.title) { ranked.append((s + (file.isNote ? 3 : 0), open(file.path))) } else if let s = score(query, file.path) { ranked.append((s - 8, open(file.path))) }
        }
        var out = ranked.sorted { ($0.0, $1.1.title) > ($1.0, $0.1.title) }.prefix(40).map(\.1)
        if !w.map.files.contains(where: { $0.path.title.caseInsensitiveCompare(query) == .orderedSame }) {
            out.append(Item(id: "c-create", title: "Create “\(query)”", detail: "New note", icon: "plus") { Task { await w.newNote(named: query) } })
        }
        return out
    }

    var body: some View {
        let list = items
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass").foregroundStyle(.secondary)
                TextField("Open a note, or run a command", text: $text).textFieldStyle(.plain).font(.system(size: 18)).focused($focused)
                    .onSubmit { run(list) }
            }
            .padding(.horizontal, 16).frame(height: 50)
            Divider()
            ScrollViewReader { reader in
                ScrollView {
                    LazyVStack(spacing: 1) {
                        ForEach(Array(list.enumerated()), id: \.element.id) { place, item in
                            row(item, active: place == selected).id(place).onTapGesture {
                                selected = place
                                run(list)
                            }
                        }
                    }
                    .padding(6)
                }
                .frame(maxHeight: 340)
                .onChange(of: selected) { _, new in reader.scrollTo(new) }
            }
        }
        .frame(width: 600)
        .background(.regularMaterial, in: .rect(cornerRadius: 16))
        .overlay { RoundedRectangle(cornerRadius: 16).strokeBorder(Color.primary.opacity(0.12)) }
        .shadow(color: .black.opacity(0.35), radius: 30, y: 12)
        .onAppear { focused = true }
        .onChange(of: text) { _, _ in selected = 0 }
        .onKeyPress(.downArrow) { selected = min(selected + 1, max(0, list.count - 1)); return .handled }
        .onKeyPress(.upArrow) { selected = max(selected - 1, 0); return .handled }
        .onKeyPress(.escape) { workspace.paletteOpen = false; return .handled }
        .onExitCommand { workspace.paletteOpen = false }
    }

    private func row(_ item: Item, active: Bool) -> some View {
        HStack(spacing: 10) {
            Image(systemName: item.icon).frame(width: 18).foregroundStyle(active ? .white : .secondary)
            Text(item.title).lineLimit(1)
            Spacer(minLength: 12)
            Text(item.detail).font(.caption).lineLimit(1).foregroundStyle(active ? .white.opacity(0.8) : .secondary)
        }
        .foregroundStyle(active ? .white : .primary)
        .padding(.horizontal, 10).frame(height: 32)
        .background(active ? Color.accentColor : .clear, in: .rect(cornerRadius: 8))
        .contentShape(Rectangle())
    }

    private func run(_ list: [Item]) {
        guard list.indices.contains(selected) else { return }
        workspace.paletteOpen = false
        list[selected].run()
    }
}
