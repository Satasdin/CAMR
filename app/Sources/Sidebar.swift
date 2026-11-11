import BurrowCore
import SwiftUI
import UniformTypeIdentifiers

struct Sidebar: View {
    let library: Library
    @Bindable var workspace: Workspace

    var body: some View {
        VStack(spacing: 0) {
            Places(workspace: workspace).padding(.horizontal, 10).padding(.bottom, 8)
            Picker("Show", selection: $workspace.sidebarMode) {
                Label("Files", systemImage: "folder").tag(SidebarMode.files)
                Label("Search", systemImage: "magnifyingglass").tag(SidebarMode.search)
                Label("Tags", systemImage: "number").tag(SidebarMode.tags)
            }
            .pickerStyle(.segmented).labelsHidden().labelStyle(.iconOnly)
            .padding(.horizontal, 10).padding(.bottom, 6)

            switch workspace.sidebarMode {
            case .files: FileTree(workspace: workspace)
            case .search: SearchPanel(workspace: workspace)
            case .tags: TagPanel(workspace: workspace)
            }
        }
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Menu {
                    Button("New Note") { Task { await workspace.newNote() } }
                    Button("New Folder") { Task { await workspace.newFolder() } }
                    Button("Today's Note") { Task { await workspace.dailyNote() } }
                    Divider()
                    Button("Link a Folder…") { pickLinkedFolder(workspace) }
                    Button("Open Another Vault…") { pickVault(library) }
                    let others = library.recents.filter { $0 != workspace.folder.path }
                    if !others.isEmpty {
                        Divider()
                        ForEach(others, id: \.self) { path in
                            Button(path.fileName) { library.open(URL(fileURLWithPath: path)) }
                        }
                    }
                } label: { Label("Add", systemImage: "plus") }
            }
        }
    }
}

/// The places of the Night Library: what the vault holds, what programs did with it, and its saved model memory.
struct Places: View {
    let workspace: Workspace

    private var content: TabContent? { workspace.currentTab?.content }

    var body: some View {
        VStack(alignment: .leading, spacing: 1) {
            heading("Library")
            ForEach(LibraryKind.allCases, id: \.self) { kind in
                let count = kind == .all ? workspace.map.files.count : workspace.count(kind)
                if kind == .all || count > 0 {
                    PlaceRow(title: kind.title, icon: kind.symbol, active: content == .library(kind), count: count,
                             dot: kind == .notes ? Night.note : (kind == .documents || kind == .images) ? Night.document : nil) {
                        workspace.go(.library(kind))
                    }
                }
            }
            heading("Conversations")
            PlaceRow(title: "All", icon: "point.3.connected.trianglepath.dotted", active: content == .conversations(nil), count: workspace.sessions.count, dot: Night.conversation) {
                workspace.go(.conversations(nil))
            }
            ForEach(Program.allCases) { program in
                let count = workspace.sessions(for: program).count
                if count > 0 {
                    PlaceRow(title: program.name, icon: program.symbol, active: content == .conversations(program), count: count, dot: nil) {
                        workspace.go(.conversations(program))
                    }
                }
            }
            heading("Memory")
            PlaceRow(title: "Shelf", icon: "memorychip", active: content == .shelf, count: workspace.shelf.count,
                     dot: workspace.shelf.contains { $0.stale != nil } ? Night.stale : Night.cache) { workspace.go(.shelf) }
            PlaceRow(title: "Programs", icon: "app.connected.to.app.below.fill", active: content == .programs, count: nil, dot: nil) { workspace.go(.programs) }
            PlaceRow(title: "Map", icon: "circle.hexagongrid", active: content == .graph, count: nil, dot: nil) { workspace.go(.graph) }
        }
    }

    private func heading(_ text: String) -> some View {
        Text(text).font(.system(size: 11, weight: .semibold)).foregroundStyle(.secondary).padding(.horizontal, 8).padding(.top, 10).padding(.bottom, 2)
    }
}

struct PlaceRow: View {
    let title: String
    let icon: String
    let active: Bool
    var count: Int? = nil
    var dot: Color? = nil
    let action: () -> Void
    @State private var hovering = false

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Label(title, systemImage: icon)
                Spacer()
                if let dot { Circle().fill(dot).frame(width: 6, height: 6).shadow(color: dot, radius: 3) }
                if let count { Text("\(count)").foregroundStyle(.secondary).monospacedDigit().font(.system(size: 11.5)) }
            }
            .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 8).frame(height: 26).contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .background(active ? Color.primary.opacity(0.12) : hovering ? Color.primary.opacity(0.05) : .clear, in: .rect(cornerRadius: 7))
        .onHover { hovering = $0 }
    }
}

struct FileTree: View {
    let workspace: Workspace
    @State private var renaming: FileNode?
    @State private var newName = ""

    private var selection: Binding<String?> {
        Binding(get: { workspace.currentPath }, set: { path in
            guard let path, workspace.map.files.contains(where: { $0.path == path }) else { return }
            workspace.go(.file(path))
        })
    }

    var body: some View {
        List(selection: selection) {
            OutlineGroup(workspace.tree, children: \.children) { node in
                row(node).tag(node.path)
            }
        }
        .listStyle(.sidebar)
        .dropDestination(for: String.self) { items, _ in
            for path in items { Task { await workspace.move(path, to: "") } }
            return true
        }
        .overlay {
            if workspace.tree.isEmpty, workspace.progress == nil {
                ContentUnavailableView {
                    Label("Empty Vault", systemImage: "tray")
                } description: {
                    Text("Write a note, or link a folder you already have.")
                } actions: {
                    Button("New Note") { Task { await workspace.newNote() } }
                    Button("Link a Folder…") { pickLinkedFolder(workspace) }
                }
            }
        }
        .alert("Rename", isPresented: Binding(get: { renaming != nil }, set: { if !$0 { renaming = nil } })) {
            TextField("Name", text: $newName)
            Button("Rename") { if let node = renaming { Task { await workspace.rename(node.path, to: newName) } } }
            Button("Cancel", role: .cancel) {}
        }
    }

    @ViewBuilder private func row(_ node: FileNode) -> some View {
        let insideLinked = workspace.linked.contains { node.path == $0.name || node.path.hasPrefix($0.name + "/") }
        Label {
            Text(node.name).lineLimit(1)
        } icon: {
            Image(systemName: icon(node)).foregroundStyle(node.isLinkedRoot ? Color.accentColor : .secondary)
        }
        .draggable(node.path)
        .dropDestination(for: String.self) { items, _ in
            guard node.isFolder, !insideLinked else { return false }
            for path in items where path != node.path { Task { await workspace.move(path, to: node.path) } }
            return true
        }
        .contextMenu { menu(node, insideLinked: insideLinked) }
    }

    private func icon(_ node: FileNode) -> String {
        if node.isLinkedRoot { return "link" }
        if node.isFolder { return "folder" }
        return node.isNote ? "doc.text" : "chevron.left.forwardslash.chevron.right"
    }

    @ViewBuilder private func menu(_ node: FileNode, insideLinked: Bool) -> some View {
        if node.isFolder {
            Button("Search in This Folder") {
                workspace.searchScope = node.path
                workspace.sidebarMode = .search
            }
            if !insideLinked {
                Divider()
                Button("New Note Here") { Task { await workspace.newNote(in: node.path) } }
                Button("New Folder Here") { Task { await workspace.newFolder(in: node.path) } }
            }
        } else {
            Button("Open in New Tab") { workspace.go(.file(node.path), newTab: true) }
            Divider()
        }
        if node.isLinkedRoot {
            Divider()
            Button("Unlink Folder") { Task { await workspace.unlink(node.name) } }
        } else if !insideLinked {
            Divider()
            Button("Rename…") {
                newName = node.isNote || node.isFolder ? node.name : node.path.fileName
                renaming = node
            }
            Button("Move to Trash", role: .destructive) { Task { await workspace.trash(node.path) } }
        }
    }
}

struct SearchPanel: View {
    @Bindable var workspace: Workspace
    @FocusState private var focused: Bool

    private var grouped: [(path: String, lines: [FoundLine])] {
        var order: [String] = []
        var byPath: [String: [FoundLine]] = [:]
        for line in workspace.results {
            if byPath[line.path] == nil { order.append(line.path) }
            byPath[line.path, default: []].append(line)
        }
        return order.map { ($0, byPath[$0]!) }
    }

    var body: some View {
        VStack(spacing: 6) {
            TextField("Search vault", text: $workspace.searchText)
                .textFieldStyle(.roundedBorder).focused($focused)
                .onChange(of: workspace.searchText) { _, _ in workspace.runSearch() }
                .padding(.horizontal, 10)
            HStack {
                Picker("In", selection: $workspace.searchScope) {
                    Text("Everything").tag(String?.none)
                    ForEach(workspace.scopes, id: \.self) { Text($0).tag(String?.some($0)) }
                }
                .labelsHidden().controlSize(.small)
                .onChange(of: workspace.searchScope) { _, _ in workspace.runSearch() }
                Spacer()
                if !workspace.results.isEmpty { Text("\(workspace.results.count)").font(.caption).foregroundStyle(.secondary) }
            }
            .padding(.horizontal, 10)
            List {
                ForEach(grouped, id: \.path) { group in
                    Section {
                        ForEach(group.lines) { line in
                            Button { workspace.go(.file(line.path), line: line.line) } label: {
                                Text(line.text.isEmpty ? " " : line.text).font(.callout).lineLimit(2)
                                    .frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                        }
                    } header: {
                        Text(group.path.title).lineLimit(1).help(group.path)
                    }
                }
            }
            .listStyle(.sidebar)
            .overlay {
                if workspace.results.isEmpty, !workspace.searchText.isEmpty { Text("No matches").foregroundStyle(.secondary) }
            }
        }
        .onAppear { focused = true }
    }
}

struct TagPanel: View {
    let workspace: Workspace

    var body: some View {
        List {
            ForEach(workspace.tags.keys.sorted(), id: \.self) { tag in
                DisclosureGroup {
                    ForEach(workspace.tags[tag] ?? [], id: \.self) { path in
                        Button(path.title) { workspace.go(.file(path)) }.buttonStyle(.plain)
                    }
                } label: {
                    Text("#\(tag)").badge(workspace.tags[tag]?.count ?? 0)
                }
            }
        }
        .listStyle(.sidebar)
        .overlay {
            if workspace.tags.isEmpty { Text("Write #tags in your notes to see them here.").font(.callout).foregroundStyle(.secondary).padding() }
        }
    }
}
