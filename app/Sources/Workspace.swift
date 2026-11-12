import BurrowCore
import BurrowTrial
import BurrowTools
import Foundation
import Observation
import AppKit

/// Owns the vault, so its database is only ever touched from one place.
actor Engine {
    private let vault: Vault
    private let ollama = Ollama()

    /// Where Burrow keeps its own files for this vault: the index, conversations and the Ledger.
    nonisolated let store: URL

    init(folder: URL, store: URL?) throws {
        vault = try Vault(project: folder, store: store, everything: true)
        self.store = vault.store
    }

    func index() async throws { try await vault.refresh(embedder: nil) }
    func embed(onProgress: @escaping @Sendable (String) -> Void) async throws {
        try await vault.refresh(embedder: ollama.embedder(), onProgress: onProgress)
    }

    func map() throws -> ProjectMap { try vault.projectMap() }
    func ledger() -> LedgerState {
        let ledger = Ledger(vault: vault)
        let commits = ledger.log(limit: 2_000)
        var stale: [String: [String]] = [:]
        for commit in commits { let changed = ledger.changed(commit); if !changed.isEmpty { stale[commit.id] = changed } }
        return LedgerState(commits: commits, reverted: ledger.reverted(), stale: stale, current: ledger.current)
    }
    func commit(_ kind: LedgerCommit.Kind, _ message: String, files: [String], branch: String?, session: String?) throws -> LedgerCommit {
        try Ledger(vault: vault).commit(kind, message, files: files, author: "person", client: "Burrow app", branch: branch, session: session)
    }
    func revert(_ id: String, why: String) throws { try Ledger(vault: vault).revert(id, why: why, author: "person", client: "Burrow app") }
    func resumeText(_ branch: String?) -> String { Ledger(vault: vault).resume(branch: branch) }
    /// Bookmarks live beside the index, as Obsidian keeps its own in the vault: a plain list of vault paths.
    func bookmarks() -> [String] {
        let file = vault.store.appendingPathComponent("bookmarks.json")
        return (try? JSONDecoder().decode([String].self, from: Data(contentsOf: file))) ?? []
    }
    func saveBookmarks(_ paths: [String]) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .withoutEscapingSlashes]
        try encoder.encode(paths).write(to: vault.store.appendingPathComponent("bookmarks.json"), options: .atomic)
    }
    func sessions() -> [VaultSession] { SessionStore(vault: vault).list().filter { !$0.isEmpty } }

    func shelf() -> [ShelfItem] {
        let shelf = KVShelf(vault: vault)
        return shelf.entries().map { ShelfItem(entry: $0, stale: shelf.stale($0, model: $0.model)) }
    }
    func stats() throws -> VaultStats { try vault.stats() }
    func folders() -> [String] { vault.folders() }
    func linked() -> [LinkedFolder] { vault.linkedFolders() }
    func tags() -> [String: [String]] { (try? vault.tags()) ?? [:] }
    func text(of path: String) -> String? { vault.text(of: path) }
    func canEdit(_ path: String) -> Bool { vault.canEdit(path) }
    func neighbours(of path: String) -> [Vault.Neighbour] { (try? vault.neighbours(of: path)) ?? [] }
    func mentions(of path: String) -> [FoundLine] { (try? vault.mentions(of: path)) ?? [] }
    func search(_ query: String, scope: String?) -> [FoundLine] { (try? vault.searchLines(query, scope: scope)) ?? [] }

    func write(_ path: String, text: String) throws { try vault.writeNote(path, text: text) }
    func createNote(named name: String, in folder: String, text: String) throws -> String { try vault.createNote(named: name, in: folder, text: text) }
    func createFolder(named name: String, in folder: String) throws -> String { try vault.createFolder(named: name, in: folder) }
    func rename(_ path: String, to name: String) throws -> String { try vault.rename(path, to: name) }
    func move(_ path: String, to folder: String) throws -> String { try vault.move(path, to: folder) }
    func trash(_ path: String) throws { try vault.trash(path) }
    func link(_ url: URL) throws -> LinkedFolder { try vault.linkFolder(url) }
    func unlink(_ name: String) throws { try vault.unlinkFolder(name) }
    func addNote(_ text: String, kind: NoteKind) throws -> String { try vault.addNote(text, kind: kind) }
    func apply(_ path: String, expecting old: String, with new: String) throws { try vault.applyChange(path, expecting: old, with: new) }

    func retrieve(_ question: String, scope: String?) async throws -> Retrieved {
        let usable = try vault.stats().vectors > 0
        do {
            return try await vault.retrieve(question, mode: .walk, embedder: usable ? ollama.embedder() : nil, scope: scope)
        } catch is URLError {
            return try await vault.retrieve(question, mode: .walk, embedder: nil, scope: scope)
        }
    }

    /// The engine's whole decision for a question, sized for the model that will answer.
    func brief(_ question: String, scope: String?, model: String) async throws -> (brief: Brief, profile: ModelProfile) {
        let profile = await vault.profile(for: model, ollama: ollama)
        let usable = try vault.stats().vectors > 0
        do {
            return (try await vault.brief(question, budget: profile.budget, embedder: usable ? ollama.embedder() : nil, scope: scope), profile)
        } catch is URLError {
            return (try await vault.brief(question, budget: profile.budget, embedder: nil, scope: scope), profile)
        }
    }
}

struct Source: Identifiable, Hashable {
    let id = UUID()
    let path: String
    let startLine: Int
    let endLine: Int
    let isNote: Bool
    let how: String
}

/// A change the model suggests. Nothing touches the file until someone accepts it.
@MainActor @Observable
final class Proposal: Identifiable {
    enum State { case waiting, accepted, rejected }
    let id = UUID()
    let path: String
    let old: String
    let new: String
    var state = State.waiting
    init(path: String, old: String, new: String) {
        self.path = path
        self.old = old
        self.new = new
    }
}

@MainActor @Observable
final class Turn: Identifiable {
    let id = UUID()
    let question: String
    let wantsChange: Bool
    let scope: String?
    var answer = ""
    var sources: [Source] = []
    var seconds: Double?
    var failure: String?
    var finished = false
    var proposals: [Proposal] = []
    var refused: [String] = []
    var remembering = false
    var toRemember: [ProposedNote]?
    var kept = Set<String>()
    /// What the engine decided for this question, in words, and the method it handed the model.
    var decided: String?
    var method: String?
    /// Places the answer pointed at that were not among what the model read.
    var unverified: [String] = []
    init(question: String, wantsChange: Bool, scope: String?) {
        self.question = question
        self.wantsChange = wantsChange
        self.scope = scope
    }

    /// The part to read. File blocks are shown as a reviewable change instead.
    var prose: String {
        guard wantsChange, let start = answer.range(of: "=== FILE") ?? answer.range(of: "=== File") else { return answer }
        return String(answer[..<start.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

/// One open note or file, with its unsaved words.
@MainActor @Observable
final class Document {
    let path: String
    var text = ""
    var loaded = false
    var editable = false
    var pendingLine: Int?
    fileprivate var saved = ""
    fileprivate var saveTask: Task<Void, Never>?
    init(path: String) { self.path = path }
}

struct FileNode: Identifiable, Hashable {
    var id: String { path }
    let path: String
    let name: String
    let isFolder: Bool
    let isNote: Bool
    let isLinkedRoot: Bool
    var children: [FileNode]?
}

enum TabContent: Hashable {
    case file(String)
    case graph
    case ask
    case library(LibraryKind)
    case conversations(Program?)
    case session(String)
    case shelf
    case programs
    case ledger(String?)
}

struct Tab: Identifiable, Hashable {
    let id = UUID()
    var content: TabContent
    var back: [TabContent] = []
    var forward: [TabContent] = []
}

enum SidebarMode: Hashable { case files, search, tags, bookmarks }

@MainActor @Observable
final class Workspace {
    let folder: URL
    var name: String { folder.lastPathComponent }
    private let engine: Engine
    private let ollama = Ollama()
    weak var library: Library?

    // What the vault holds.
    var map = ProjectMap(files: [], links: [])
    var tree: [FileNode] = []
    var linked: [LinkedFolder] = []
    var tags: [String: [String]] = [:]
    var stats: VaultStats?
    var sessions: [VaultSession] = []
    var shelf: [ShelfItem] = []
    var ledger = LedgerState()
    var bookmarks: [String] = []
    /// A file shown to the right of a tab's own file, by tab: Obsidian's split view.
    var sideBySide: [UUID: String] = [:]
    var librarySelection: String?
    /// Runs once the files are known, before meanings are learned, so layout checks need not wait for Ollama.
    var afterFirstRead: (() -> Void)?
    let sim = GraphSim()
    var simVersion = 0

    // The window.
    var tabs: [Tab] = [Tab(content: .library(.all))]
    var activeTab: UUID?
    var documents: [String: Document] = [:]
    var sidebarMode = SidebarMode.files
    var isReading = false   // reading view rather than editing
    var paletteOpen = false
    var graphFilter = GraphFilter()
    var progress: String?
    var warning: String?

    // Searching.
    var searchText = ""
    var results: [FoundLine] = []
    var searchScope: String?
    private var searchTask: Task<Void, Never>?

    // Asking.
    var models: [String] = []
    var model = Ollama.defaultModel
    var turns: [Turn] = []
    var askScope: String?
    var lit: [String] = []
    var litCount = 0
    var litLinks: [(from: String, to: String)] = []
    var isAsking = false
    var readingNow: String? { isAsking && litCount > 0 && litCount <= lit.count ? lit[litCount - 1] : nil }

    private var reindexTask: Task<Void, Never>?
    private var isIndexing = false
    private var watchers: [DispatchSourceFileSystemObject] = []
    private var activityTask: Task<Void, Never>?

    init(folder: URL, store: URL?) throws {
        self.folder = folder
        engine = try Engine(folder: folder, store: store)
        activeTab = tabs.first?.id
    }

    // MARK: Opening and indexing

    func open() async {
        progress = "Reading your vault"
        do {
            try await engine.index()
            await reload()
            watchActivity()
            afterFirstRead?()
            afterFirstRead = nil
        } catch {
            warning = "Burrow could not read this folder. \(error)"
            progress = nil
            return
        }
        do {
            let found = try await ollama.models().filter { !$0.lowercased().contains("embed") }.sorted()
            models = found
            if !found.contains(model), let first = found.first { model = first }
            warning = nil
            try await embed()
        } catch {
            warning = "Ollama isn't running, so search by meaning is off. Notes, links, word search and connected programs still work."
        }
        progress = nil
    }

    private func embed() async throws {
        try await engine.embed { line in
            Task { @MainActor [weak self] in self?.progress = "Learning what things mean: \(line.replacingOccurrences(of: "embedded ", with: ""))" }
        }
        await reload()
    }

    /// Programs write their conversations and Ledger commits while the app is open. Watching those folders lets the
    /// Programs, Conversations and Ledger pages move as a model works, instead of waiting for the app to be clicked.
    private func watchActivity() {
        watchers.forEach { $0.cancel() }
        watchers = []
        let store = engine.store
        for folder in [store, store.appendingPathComponent("sessions"), store.appendingPathComponent("ledger")] {
            let handle = Darwin.open(folder.path, O_EVTONLY)
            guard handle >= 0 else { continue }
            let source = DispatchSource.makeFileSystemObjectSource(fileDescriptor: handle, eventMask: [.write, .rename, .delete], queue: .main)
            source.setEventHandler { [weak self] in Task { @MainActor in self?.activityChanged() } }
            source.setCancelHandler { Darwin.close(handle) }
            source.resume()
            watchers.append(source)
        }
    }

    private func activityChanged() {
        activityTask?.cancel()
        activityTask = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(400))
            guard !Task.isCancelled, let self else { return }
            self.sessions = await self.engine.sessions()
            self.ledger = await self.engine.ledger()
            // A folder made since the watch began (the first conversation, the first commit) gets its own watch.
            if self.watchers.count < 3 { self.watchActivity() }
        }
    }

    func readAgain() async {
        guard !isIndexing else { return }
        isIndexing = true
        defer { isIndexing = false }
        try? await engine.index()
        await reload()
        reloadUnchangedDocuments()
        if (try? await embed()) == nil { warning = "Ollama isn't running, so new notes aren't searchable by meaning yet." } else { progress = nil }
        progress = nil
    }

    private func scheduleReindex() {
        reindexTask?.cancel()
        reindexTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(1.5))
            guard !Task.isCancelled else { return }
            await self?.readAgain()
        }
    }

    func reload() async {
        guard let newMap = try? await engine.map() else { return }
        map = newMap
        let foldersNow = await engine.folders()
        linked = await engine.linked()
        tree = Self.buildTree(files: newMap.files, folders: foldersNow, linked: Set(linked.map(\.name)))
        tags = await engine.tags()
        stats = try? await engine.stats()
        sessions = await engine.sessions()
        shelf = await engine.shelf()
        ledger = await engine.ledger()
        bookmarks = await engine.bookmarks()
        let sim = self.sim
        let linkedNames = Set(linked.map(\.name))
        await Task.detached { sim.load(newMap, linked: linkedNames) }.value
        simVersion += 1
    }

    private func reloadUnchangedDocuments() {
        for document in documents.values where document.text == document.saved && document.saveTask == nil {
            Task {
                guard let text = await engine.text(of: document.path), text != document.text else { return }
                document.text = text
                document.saved = text
            }
        }
    }

    private static func buildTree(files: [MapFile], folders: [String], linked: Set<String>) -> [FileNode] {
        final class Box { var folders: [String: Box] = [:]; var files: [MapFile] = [] }
        let root = Box()
        func box(_ path: String) -> Box {
            var here = root
            for part in path.split(separator: "/").map(String.init) {
                if here.folders[part] == nil { here.folders[part] = Box() }
                here = here.folders[part]!
            }
            return here
        }
        folders.forEach { _ = box($0) }
        for file in files { box(file.path.folderPath).files.append(file) }
        func nodes(_ here: Box, _ prefix: String) -> [FileNode] {
            let dirs = here.folders.keys.sorted { $0.localizedStandardCompare($1) == .orderedAscending }.map { name -> FileNode in
                let path = prefix.isEmpty ? name : prefix + "/" + name
                return FileNode(path: path, name: name, isFolder: true, isNote: false, isLinkedRoot: prefix.isEmpty && linked.contains(name), children: nodes(here.folders[name]!, path))
            }
            let leaves = here.files.sorted { $0.path.localizedStandardCompare($1.path) == .orderedAscending }.map {
                FileNode(path: $0.path, name: $0.path.title, isFolder: false, isNote: $0.isNote, isLinkedRoot: false, children: nil)
            }
            return dirs + leaves
        }
        return nodes(root, "")
    }

    // MARK: Tabs and navigation

    var currentTab: Tab? { tabs.first { $0.id == activeTab } }
    var currentPath: String? {
        if case let .file(path)? = currentTab?.content { return path }
        return nil
    }

    func tabTitle(_ tab: Tab) -> String {
        switch tab.content {
        case let .file(path): return sideBySide[tab.id].map { "\(path.title) | \($0.title)" } ?? path.title
        case .graph: return "Map"
        case .ask: return "Ask"
        case let .library(kind): return kind.title
        case let .conversations(program): return program?.name ?? "Conversations"
        case let .session(id): return sessions.first { $0.id == id }.map { Program(client: $0.client).name } ?? "Conversation"
        case .shelf: return "Shelf"
        case .programs: return "Programs"
        case let .ledger(branch): return branch.map { "Ledger · \($0)" } ?? "Ledger"
        }
    }

    /// Goes to something in the current tab, or in a new one.
    func go(_ content: TabContent, newTab: Bool = false, line: Int? = nil) {
        if case let .file(path) = content {
            let document = self.document(path)
            if let line { document.pendingLine = line }
        }
        if !newTab, let existing = tabs.first(where: { $0.content == content }) {
            activeTab = existing.id
            return
        }
        if newTab || tabs.isEmpty || activeIsSingleton(content) {
            let tab = Tab(content: content)
            tabs.append(tab)
            activeTab = tab.id
        } else if let index = tabs.firstIndex(where: { $0.id == activeTab }) {
            tabs[index].back.append(tabs[index].content)
            tabs[index].forward = []
            tabs[index].content = content
        }
    }

    /// The Graph and Ask keep their own tabs: opening a note from one shouldn't replace it.
    private func activeIsSingleton(_ content: TabContent) -> Bool {
        guard let current = currentTab?.content else { return true }
        if case .file = current, case .file = content { return false }
        return true
    }

    func goBack() {
        guard let index = tabs.firstIndex(where: { $0.id == activeTab }), let last = tabs[index].back.popLast() else { return }
        tabs[index].forward.append(tabs[index].content)
        tabs[index].content = last
    }

    func goForward() {
        guard let index = tabs.firstIndex(where: { $0.id == activeTab }), let next = tabs[index].forward.popLast() else { return }
        tabs[index].back.append(tabs[index].content)
        tabs[index].content = next
    }

    func close(_ tab: Tab) {
        guard let index = tabs.firstIndex(of: tab) else { return }
        tabs.remove(at: index)
        if activeTab == tab.id { activeTab = tabs[safe: index]?.id ?? tabs.last?.id }
    }

    func closeCurrentTab() { if let currentTab { close(currentTab) } }

    func cycleTab(by step: Int) {
        guard !tabs.isEmpty, let index = tabs.firstIndex(where: { $0.id == activeTab }) else { return }
        activeTab = tabs[(index + step + tabs.count) % tabs.count].id
    }

    // MARK: Documents

    /// Keeps something in the Ledger from the app, then reads the Ledger again.
    func keep(_ kind: LedgerCommit.Kind, _ message: String, files: [String], branch: String? = nil, session: String? = nil) async {
        do {
            _ = try await engine.commit(kind, message, files: files, branch: branch, session: session)
            ledger = await engine.ledger()
        } catch { warning = "Could not keep that: \(error)" }
    }

    func markWrong(_ id: String, why: String) async {
        do {
            try await engine.revert(id, why: why)
            ledger = await engine.ledger()
        } catch { warning = "Could not mark that wrong: \(error)" }
    }

    func resumeText(_ branch: String?) async -> String { await engine.resumeText(branch) }

    func isBookmarked(_ path: String) -> Bool { bookmarks.contains(path) }

    /// Shows a file to the right of the current one. With no file open, it simply opens.
    func openToTheRight(_ path: String) {
        guard currentPath != nil, let tab = activeTab, currentPath != path else { return go(.file(path)) }
        sideBySide[tab] = path
    }

    func toggleBookmark(_ path: String) async {
        var next = bookmarks
        if let index = next.firstIndex(of: path) { next.remove(at: index) } else { next.append(path) }
        do {
            try await engine.saveBookmarks(next)
            bookmarks = next
        } catch { warning = "Could not save bookmarks: \(error)" }
    }

    /// A file's text as the vault reads it, for covers and previews. Documents come back as their extracted Markdown.
    func text(of path: String) async -> String? { await engine.text(of: path) }

    func document(_ path: String) -> Document {
        if let found = documents[path] { return found }
        let made = Document(path: path)
        documents[path] = made
        Task {
            let text = await engine.text(of: path) ?? ""
            made.text = text
            made.saved = text
            made.editable = await engine.canEdit(path)
            made.loaded = true
        }
        return made
    }

    func edited(_ document: Document, to text: String) {
        guard text != document.text else { return }
        document.text = text
        document.saveTask?.cancel()
        document.saveTask = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(400))
            guard !Task.isCancelled else { return }
            await self?.save(document)
        }
    }

    private func save(_ document: Document) async {
        let text = document.text
        do {
            try await engine.write(document.path, text: text)
            document.saved = text
            document.saveTask = nil
            scheduleReindex()
        } catch {
            warning = "\(document.path.fileName) couldn't be saved. \(error)"
        }
    }

    /// Finds what a [[link]] means, the way a person would: exact path first, then a note of that name.
    func resolve(_ target: String) -> String? {
        let clean = target.components(separatedBy: "#").first?.trimmingCharacters(in: .whitespaces) ?? target
        let paths = map.files.map(\.path)
        if paths.contains(clean) { return clean }
        if paths.contains(clean + ".md") { return clean + ".md" }
        return paths.first { $0.title.caseInsensitiveCompare(clean) == .orderedSame }
            ?? paths.first { $0.fileName.caseInsensitiveCompare(clean) == .orderedSame }
    }

    /// Following a link to a note that doesn't exist yet makes it, as a vault should.
    func follow(_ target: String, newTab: Bool) {
        if let path = resolve(target) {
            go(.file(path), newTab: newTab)
        } else {
            Task {
                await act {
                    let path = try await engine.createNote(named: target, in: "", text: "")
                    await reload()
                    go(.file(path), newTab: newTab)
                }
            }
        }
    }

    // MARK: Changing the vault

    private func act(_ work: () async throws -> Void) async {
        do { try await work() } catch { warning = "\(error)" }
    }

    func newNote(in folder: String = "", named name: String = "Untitled", text: String = "") async {
        await act {
            let path = try await engine.createNote(named: name, in: folder, text: text)
            await reload()
            isReading = false
            go(.file(path))
            sidebarMode = .files
        }
    }

    func newFolder(in folder: String = "", named name: String = "New Folder") async {
        await act {
            _ = try await engine.createFolder(named: name, in: folder)
            await reload()
        }
    }

    func dailyNote() async {
        let day = ISO8601DateFormatter.string(from: Date(), timeZone: .current, formatOptions: [.withFullDate])
        if let existing = resolve("Daily/\(day)") { go(.file(existing)); return }
        await newNote(in: "Daily", named: day)
    }

    func rename(_ path: String, to name: String) async {
        await act {
            let renamed = try await engine.rename(path, to: name)
            await reload()
            documents[path] = nil
            for index in tabs.indices where tabs[index].content == .file(path) { tabs[index].content = .file(renamed) }
        }
    }

    func move(_ path: String, to folder: String) async {
        await act {
            let moved = try await engine.move(path, to: folder)
            await reload()
            documents[path] = nil
            for index in tabs.indices where tabs[index].content == .file(path) { tabs[index].content = .file(moved) }
        }
    }

    func trash(_ path: String) async {
        await act {
            try await engine.trash(path)
            documents[path] = nil
            tabs.removeAll { if case let .file(open) = $0.content { return open == path || open.hasPrefix(path + "/") } else { return false } }
            if !tabs.contains(where: { $0.id == activeTab }) { activeTab = tabs.last?.id }
            await reload()
        }
    }

    func link(_ url: URL) async {
        await act {
            _ = try await engine.link(url)
            await readAgain()
        }
    }

    func unlink(_ name: String) async {
        await act {
            try await engine.unlink(name)
            await readAgain()
        }
    }

    func neighbours(of path: String) async -> [Vault.Neighbour] { await engine.neighbours(of: path) }
    func mentions(of path: String) async -> [FoundLine] { await engine.mentions(of: path) }

    /// Obsidian's unlinked mentions: notes that name this file in plain words without linking to it.
    func unlinkedMentions(of path: String, linked: Set<String>) async -> [FoundLine] {
        let name = path.title
        guard name.count >= 3 else { return [] }
        let lower = name.lowercased()
        let found = await engine.search(name, scope: nil)
        var seen = Set<String>()
        return found.filter { line in
            guard line.path != path, line.path.isMarkdownPath, !linked.contains(line.path), !seen.contains(line.path) else { return false }
            let text = line.text.lowercased()
            guard text.contains(lower), !text.contains("[[" + lower) else { return false }
            seen.insert(line.path)
            return true
        }
    }

    // MARK: Search

    func runSearch() {
        searchTask?.cancel()
        let query = searchText
        let scope = searchScope
        searchTask = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(160))
            guard !Task.isCancelled, let self else { return }
            // Obsidian's operators: path:, file:, tag: and ext: narrow the results; the rest is the search itself.
            let parsed = SearchQuery(query)
            var found: [FoundLine] = []
            if !parsed.words.isEmpty {
                found = await self.engine.search(parsed.words, scope: scope)
            } else if parsed.hasFilters {
                // Filters alone list the matching files, one line each.
                found = self.map.files.map { FoundLine(path: $0.path, line: 1, text: $0.path.title) }
            }
            let tagged = parsed.tags.isEmpty ? nil : Set(parsed.tags.flatMap { self.tags[$0] ?? self.tags["#" + $0] ?? [] })
            found = found.filter { parsed.keeps($0.path, tagged: tagged) }
            guard !Task.isCancelled else { return }
            self.results = found
        }
    }

    // MARK: Asking

    private static let changeRules = Asking.withMemory + """


    The developer wants a change. Files marked whole="true" are shown complete, and they are the only files you may change.
    Say in one short sentence what you changed, then give each changed file complete, exactly like this:
    === FILE: path/to/file ===
    the whole new file
    === END FILE ===
    If a note forbids this change, say so, name the note, and write no files.
    """

    /// Whole files for the model to rewrite: an excerpt alone would lose the rest of the file.
    private func wholeFiles(for found: Retrieved) async -> [(path: String, text: String)] {
        var out: [(path: String, text: String)] = []
        var used = 0
        for piece in found.excerpts where !out.contains(where: { $0.path == piece.path }) {
            guard out.count < 3, let text = await engine.text(of: piece.path), used + text.count <= 9_000 else { continue }
            out.append((piece.path, text))
            used += text.count
        }
        return out
    }

    func accept(_ proposal: Proposal) async {
        await act {
            try await engine.apply(proposal.path, expecting: proposal.old, with: proposal.new)
            proposal.state = .accepted
            documents[proposal.path] = nil
            await readAgain()
        }
    }

    func keepAsNote(_ turn: Turn) async {
        await act {
            let path = try await engine.addNote("\(turn.question)\n\n\(turn.answer)", kind: .note)
            await reload()
            go(.file(path), newTab: true)
        }
    }

    /// Asks the model what this exchange decided, using the same words as the agent test. Nothing is kept until someone says so.
    func remember(_ turn: Turn) {
        guard !turn.remembering else { return }
        turn.remembering = true
        let chosen = model
        Task {
            let brief = "The person asked: \(turn.question)\n\nThe assistant replied: \(turn.prose)"
            let reply = try? await ollama.answerer(model: chosen).answer(system: Agent.notesSystem, user: Agent.notesPrompt(brief: brief)) { _ in }
            turn.toRemember = NoteParser.parse(reply?.text ?? "")
            turn.remembering = false
        }
    }

    func keep(_ note: ProposedNote, from turn: Turn) async {
        await act {
            _ = try await engine.addNote(note.text, kind: note.kind)
            turn.kept.insert(note.text)
            scheduleReindex()
        }
    }

    func ask(_ question: String, wantsChange: Bool = false) {
        let words = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !words.isEmpty, !isAsking else { return }
        let scope = askScope
        let turn = Turn(question: words, wantsChange: wantsChange, scope: scope)
        turns.append(turn)
        isAsking = true
        lit = []
        litCount = 0
        litLinks = []
        let chosen = model
        Task {
            let started = Date()
            do {
                // A plain question goes through the engine. A change request keeps the walk, because it needs whole files.
                var prepared: (brief: Brief, profile: ModelProfile)?
                if !wantsChange { prepared = try await engine.brief(words, scope: scope, model: chosen) }
                let found: Retrieved
                if let prepared { found = prepared.brief.retrieved } else { found = try await engine.retrieve(words, scope: scope) }
                if let brief = prepared?.brief {
                    turn.decided = brief.route.mode == .none ? "Answered without the vault: \(brief.route.why)." : "Read the vault: \(brief.route.why)."
                    turn.method = brief.skill?.name
                }
                turn.sources = found.excerpts.map {
                    Source(path: $0.path, startLine: $0.startLine, endLine: $0.endLine, isNote: $0.isNote, how: $0.reason.label)
                }
                lit = found.paths
                litLinks = found.excerpts.compactMap {
                    if case let .link(from, _, _) = $0.reason { return (from, $0.path) }
                    return nil
                }
                Task { await lightUp() }
                let whole = wantsChange ? await wholeFiles(for: found) : []
                let shown = whole.map { "<file path=\"\($0.path)\" whole=\"true\">\n\($0.text)\n</file>" }.joined(separator: "\n\n")
                let prompt = prepared?.brief.user ?? ((shown.isEmpty ? "" : shown + "\n\n") + Asking.prompt(question: words, excerpts: found.excerpts))
                let answerer = ollama.answerer(model: chosen, contextWords: prepared?.profile.windowTokens ?? 16384)
                let result = try await answerer.answer(system: prepared?.brief.system ?? Self.changeRules, user: prompt) { word in
                    Task { @MainActor in turn.answer += word }
                }
                if !found.excerpts.isEmpty {
                    let cited = BurrowCore.Engine.citations(in: result.text, shown: found.excerpts)
                    turn.unverified = cited.filter { !$0.shown }.map { "\($0.path):\($0.line)" }
                }
                turn.answer = result.text
                turn.seconds = Date().timeIntervalSince(started)
                if wantsChange {
                    let parsed = ReplyParser.parse(result.text, finished: result.answerTokens < 2048)
                    turn.refused = parsed.failures
                    for edit in parsed.edits {
                        if let file = whole.first(where: { $0.path == edit.path }) {
                            if file.text != edit.content { turn.proposals.append(Proposal(path: edit.path, old: file.text, new: edit.content)) }
                        } else {
                            turn.refused.append("\(edit.path) wasn't one of the files it was shown in full")
                        }
                    }
                }
            } catch {
                turn.failure = "No answer. Is Ollama running, and is \(chosen) installed?"
            }
            litCount = lit.count
            turn.finished = true
            isAsking = false
        }
    }

    private func lightUp() async {
        while litCount < lit.count, isAsking {
            litCount += 1
            try? await Task.sleep(for: .milliseconds(220))
        }
    }

    /// Folders a question can be limited to: linked folders first, then the top of the vault.
    var scopes: [String] {
        let linkedNames = linked.map(\.name)
        let top = tree.filter { $0.isFolder && !linkedNames.contains($0.path) }.map(\.path)
        return linkedNames + top
    }
}

/// Types into the open note through the same route a keyboard takes, for checking that it reaches the file.
@MainActor
func typeIntoEditor(_ words: String) {
    func find(_ view: NSView) -> VaultNSTextView? {
        if let text = view as? VaultNSTextView { return text }
        for child in view.subviews { if let hit = find(child) { return hit } }
        return nil
    }
    guard let root = NSApp.windows.first(where: \.isVisible)?.contentView, let text = find(root) else { return }
    let end = NSRange(location: (text.string as NSString).length, length: 0)
    text.setSelectedRange(end)
    text.insertText(words, replacementRange: end)
}

extension Array {
    subscript(safe index: Int) -> Element? { indices.contains(index) ? self[index] : nil }
}

@MainActor @Observable
final class Library {
    var workspace: Workspace?
    var recents: [String] = UserDefaults.standard.stringArray(forKey: "recentVaults") ?? []
    var failure: String?

    func open(_ folder: URL) {
        let environment = ProcessInfo.processInfo.environment
        do {
            let opened = try Workspace(folder: folder, store: environment["BURROW_STORE"].map { URL(fileURLWithPath: $0) })
            opened.library = self
            workspace = opened
            recents = [folder.path] + recents.filter { $0 != folder.path }
            UserDefaults.standard.set(Array(recents.prefix(8)), forKey: "recentVaults")
            opened.afterFirstRead = { Self.applyCheckHooks(opened, environment) }
            Task { await opened.open() }
        } catch {
            failure = "\(error)"
        }
    }

    /// For checking layouts without a person at the screen.
    private static func applyCheckHooks(_ workspace: Workspace, _ environment: [String: String]) {
        if let path = environment["BURROW_OPEN"] { workspace.go(.file(path)) }
        if environment["BURROW_READING"] != nil { workspace.isReading = true }
        if environment["BURROW_TAB"] == "ask" { workspace.go(.ask) }
        if environment["BURROW_TAB"] == "graph" { workspace.go(.graph) }
        switch environment["BURROW_TAB"] {
        case "conversations": workspace.go(.conversations(nil))
        case "session": if let first = workspace.sessions.first { workspace.go(.session(first.id)) }
        case "shelf": workspace.go(.shelf)
        case "programs": workspace.go(.programs)
        case "ledger": workspace.go(.ledger(nil))
        case "documents": workspace.go(.library(.documents))
        default: break
        }
        if let pick = environment["BURROW_SELECT"] { workspace.librarySelection = pick }
        if environment["BURROW_PALETTE"] != nil { workspace.paletteOpen = true }
        if let query = environment["BURROW_SEARCH"] {
            workspace.sidebarMode = .search
            workspace.searchText = query
            workspace.runSearch()
        }
        if environment["BURROW_SIDEBAR"] == "tags" { workspace.sidebarMode = .tags }
        if let chosen = environment["BURROW_MODEL"] { workspace.model = chosen }
        workspace.askScope = environment["BURROW_SCOPE"]
        if let question = environment["BURROW_ASK"] { workspace.ask(question, wantsChange: environment["BURROW_CHANGE"] != nil) }
        if let words = environment["BURROW_TYPE"] {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { typeIntoEditor(words) }
        }
    }
}

/// A search box's text split into Obsidian's operators and the words to search for.
struct SearchQuery {
    var words = ""
    var paths: [String] = []
    var files: [String] = []
    var tags: [String] = []
    var extensions: [String] = []

    init(_ text: String) {
        var rest: [String] = []
        for part in text.split(separator: " ") {
            let token = String(part)
            let lower = token.lowercased()
            if lower.hasPrefix("path:"), token.count > 5 { paths.append(String(lower.dropFirst(5))) }
            else if lower.hasPrefix("file:"), token.count > 5 { files.append(String(lower.dropFirst(5))) }
            else if lower.hasPrefix("tag:"), token.count > 4 { tags.append(String(token.dropFirst(4)).trimmingCharacters(in: CharacterSet(charactersIn: "#"))) }
            else if lower.hasPrefix("ext:"), token.count > 4 { extensions.append(String(lower.dropFirst(4)).trimmingCharacters(in: CharacterSet(charactersIn: "."))) }
            else { rest.append(token) }
        }
        words = rest.joined(separator: " ").trimmingCharacters(in: .whitespaces)
    }

    var hasFilters: Bool { !(paths.isEmpty && files.isEmpty && tags.isEmpty && extensions.isEmpty) }

    func keeps(_ path: String, tagged: Set<String>?) -> Bool {
        let lower = path.lowercased()
        if !paths.allSatisfy({ lower.contains($0) }) { return false }
        if !files.allSatisfy({ (lower as NSString).lastPathComponent.contains($0) }) { return false }
        if !extensions.isEmpty, !extensions.contains((lower as NSString).pathExtension) { return false }
        if let tagged, !tagged.contains(path) { return false }
        return true
    }
}
