import BurrowCore
import BurrowTools
import Foundation

enum Page: Equatable { case vault, star, ask, ledger }
enum Focus: Equatable { case tree, reader, links }
enum Overlay: Equatable { case none, quickOpen, search, help }

/// What the app has to do outside its own state.
enum Effect: Equatable {
    case ask(question: String, folder: String?)
    case cancelAsk
    case reindex
    case quit
    case suspend
}

struct TreeRow: Equatable {
    let path: String
    let name: String
    let depth: Int
    let isFolder: Bool
    let isNote: Bool
    let isLinked: Bool
    let fileCount: Int
}

struct SideRow: Equatable {
    enum Kind: Equatable { case heading, link }
    let kind: Kind
    let text: String
    var path: String? = nil
    var line: Int? = nil
    var detail: String? = nil
    var isNote = false
    var forward = true
}

struct OpenDocument {
    let path: String
    let source: String
    let isNote: Bool
    var rendered = RenderedDocument()
    var renderedWidth = -1
    var scroll = 0
    /// The link picked with Tab.
    var activeLink: Int?
    /// A source line to mark, after arriving from a search or an answer.
    var markedLine: Int?
}

struct QuickOpenState {
    var field = TextField()
    var results: [MapFile] = []
    var selected = 0
}

struct SearchState {
    var field = TextField()
    var results: [FoundLine] = []
    var selected = 0
    var problem: String?
}

struct AskEntry {
    var question: String
    var scope: String?
    var answer = ""
    var sources: [ToolResult.Source] = []
    var how = ""
    var seconds: Double?
    var problem: String?
}

enum AskStatus: Equatable { case idle, searching, answering }

struct AskState {
    var field = TextField()
    var scope: String?
    var entries: [AskEntry] = []
    var status = AskStatus.idle
    var startedAt: Date?
    /// How far up from the end the reader has scrolled. Zero follows the answer as it arrives.
    var scrollUp = 0
    var selectedSource = 0
}

struct StarNeighbour: Equatable {
    let path: String
    let isNote: Bool
    let forward: Bool
    let kind: String
    let via: String?
    /// How many other things this one connects to.
    let further: Int
}

struct StarState {
    var center: String?
    var selected = 0
    var neighbours: [StarNeighbour] = []
    /// Links that didn't fit on the screen.
    var hidden = 0
}

/// Everything the screen shows. Keys change it, background jobs change it, and views only read it.
final class Model {
    let vault: Vault
    let modelName: String
    var width = 100
    var height = 30

    var page = Page.vault
    var focus = Focus.tree
    var overlay = Overlay.none
    var showSide = true

    private(set) var files: [MapFile] = []
    private var filePaths = Set<String>()
    private var linkedNames = Set<String>()
    var folders: [String] = []
    var stats: VaultStats?

    private(set) var rows: [TreeRow] = []
    var expanded = Set<String>()
    private var hasOpenedFolders = false
    var treeSelected = 0
    var treeScroll = 0

    var document: OpenDocument?
    private var back: [(path: String, scroll: Int)] = []
    private var forward: [(path: String, scroll: Int)] = []

    var sideRows: [SideRow] = []
    var sideSelected = 0
    var sideScroll = 0

    var quick = QuickOpenState()
    var search = SearchState()
    var ask = AskState()
    var ledgerView = LedgerViewState()
    var star = StarState()

    var status: String?
    var statusIsProblem = false
    var indexing: String? = "Reading the vault…"

    init(vault: Vault, modelName: String) {
        self.vault = vault
        self.modelName = modelName
    }

    // MARK: Loading

    /// Reads the current index. Called at the start and after every re-index.
    func reload() {
        files = ((try? vault.projectMap().files) ?? [])
        filePaths = Set(files.map(\.path))
        linkedNames = Set(vault.linkedFolders().map(\.name))
        folders = vault.folders()
        stats = try? vault.stats()
        if !hasOpenedFolders, !files.isEmpty {
            hasOpenedFolders = true
            if files.count <= 60 { expanded = Set(allFolders) }
        }
        rebuildRows()
        if let current = document {
            if filePaths.contains(current.path), let text = vault.text(of: current.path) {
                if text != current.source {
                    var next = OpenDocument(path: current.path, source: text, isNote: current.isNote)
                    next.scroll = current.scroll
                    document = next
                }
                loadSide(current.path)
            } else {
                document = nil
                sideRows = []
            }
        }
        syncDocument()
    }

    private var allFolders: [String] {
        var out = Set<String>()
        for file in files {
            var folder = (file.path as NSString).deletingLastPathComponent
            while !folder.isEmpty, out.insert(folder).inserted { folder = (folder as NSString).deletingLastPathComponent }
        }
        return out.sorted()
    }

    func rebuildRows() {
        final class Folder {
            var folders: [String: Folder] = [:]
            var files: [MapFile] = []
            var total = 0
        }
        let top = Folder()
        for file in files {
            var node = top
            node.total += 1
            let parts = file.path.split(separator: "/").map(String.init)
            for part in parts.dropLast() {
                if node.folders[part] == nil { node.folders[part] = Folder() }
                node = node.folders[part]!
                node.total += 1
            }
            node.files.append(file)
        }
        var out: [TreeRow] = []
        func visit(_ node: Folder, prefix: String, depth: Int) {
            for name in node.folders.keys.sorted(by: { $0.localizedCaseInsensitiveCompare($1) == .orderedAscending }) {
                let path = prefix + name
                out.append(TreeRow(path: path, name: name, depth: depth, isFolder: true, isNote: false, isLinked: depth == 0 && linkedNames.contains(name), fileCount: node.folders[name]!.total))
                if expanded.contains(path) { visit(node.folders[name]!, prefix: path + "/", depth: depth + 1) }
            }
            for file in node.files.sorted(by: { $0.path.localizedCaseInsensitiveCompare($1.path) == .orderedAscending }) {
                let name = (file.path as NSString).lastPathComponent
                out.append(TreeRow(path: file.path, name: file.isNote ? (name as NSString).deletingPathExtension : name, depth: depth, isFolder: false, isNote: file.isNote, isLinked: false, fileCount: 0))
            }
        }
        visit(top, prefix: "", depth: 0)
        rows = out
        treeSelected = min(treeSelected, max(0, rows.count - 1))
    }

    // MARK: Layout helpers

    var layout: Layout { Layout.vault(width: width, height: height, focus: focus, showSide: showSide) }

    func resize(width: Int, height: Int) {
        self.width = width
        self.height = height
        syncDocument()
        keepTreeVisible()
        keepDocumentInBounds()
    }

    /// Lays the open document out for the space it has now.
    func syncDocument() {
        guard var current = document else { return }
        let wanted = max(10, layout.readerTextWidth)
        guard current.renderedWidth != wanted else { return }
        let firstSource = current.rendered.lines.indices.contains(current.scroll) ? current.rendered.lines[current.scroll].source : nil
        let active = current.activeLink
        current.rendered = renderer(width: wanted, path: current.path, isNote: current.isNote).render(current.source, isNote: current.isNote)
        current.renderedWidth = wanted
        if let firstSource, let line = current.rendered.lines.firstIndex(where: { $0.source >= firstSource }) { current.scroll = line }
        if let active, active >= current.rendered.links.count { current.activeLink = nil }
        document = current
        keepDocumentInBounds()
    }

    private func renderer(width: Int, path: String, isNote: Bool) -> DocumentRenderer {
        DocumentRenderer(width: width, isNote: { [unowned self] in filesIsNote($0) }, resolve: { [unowned self] in resolve($0, from: path) })
    }

    private func filesIsNote(_ path: String) -> Bool { files.first { $0.path == path }?.isNote ?? false }

    /// Works out which file a link means, the same way the index does.
    func resolve(_ target: String, from path: String) -> String? {
        let clean = target.trimmingCharacters(in: .whitespaces)
        guard !clean.isEmpty else { return nil }
        let local = Self.normalised(((path as NSString).deletingLastPathComponent as NSString).appendingPathComponent(clean))
        for candidate in [clean, clean + ".md", local, local + ".md"] where filePaths.contains(candidate) { return candidate }
        let name = (clean as NSString).lastPathComponent
        return files.first { ($0.path as NSString).lastPathComponent == name || ($0.path as NSString).lastPathComponent == name + ".md" }?.path
    }

    private static func normalised(_ path: String) -> String {
        var parts: [Substring] = []
        for piece in path.split(separator: "/") where piece != "." {
            if piece == "..", !parts.isEmpty { parts.removeLast() } else { parts.append(piece) }
        }
        return parts.joined(separator: "/")
    }

    var readerRows: Int { layout.reader?.height ?? max(1, height - 4) }

    func keepDocumentInBounds() {
        guard var current = document else { return }
        current.scroll = max(0, min(current.scroll, max(0, current.rendered.lines.count - readerRows)))
        document = current
    }

    func keepTreeVisible() {
        let rowsShown = max(1, (layout.tree?.height ?? height - 4) - 1)
        if treeSelected < treeScroll { treeScroll = treeSelected }
        if treeSelected >= treeScroll + rowsShown { treeScroll = treeSelected - rowsShown + 1 }
        treeScroll = max(0, min(treeScroll, max(0, rows.count - rowsShown)))
    }

    // MARK: Opening things

    func open(_ path: String, line: Int? = nil, remember: Bool = true, scroll: Int? = nil) {
        guard let text = vault.text(of: path) else {
            setStatus("\(path) can't be opened.", problem: true)
            return
        }
        if remember, let current = document, current.path != path || line != nil {
            back.append((current.path, current.scroll))
            forward = []
        }
        document = OpenDocument(path: path, source: text, isNote: filesIsNote(path))
        syncDocument()
        if let scroll {
            document?.scroll = scroll
        } else if let line, let found = document?.rendered.lines.firstIndex(where: { $0.source >= line }) {
            document?.scroll = max(0, found - 3)
            document?.markedLine = line
        }
        keepDocumentInBounds()
        reveal(path)
        loadSide(path)
        page = .vault
        overlay = .none
        focus = .reader
        syncDocument()
    }

    private func reveal(_ path: String) {
        var folder = (path as NSString).deletingLastPathComponent
        while !folder.isEmpty {
            expanded.insert(folder)
            folder = (folder as NSString).deletingLastPathComponent
        }
        rebuildRows()
        if let found = rows.firstIndex(where: { $0.path == path }) { treeSelected = found }
        keepTreeVisible()
    }

    func goBack() {
        guard let last = back.popLast() else { return setStatus("Nothing to go back to.") }
        if let current = document { forward.append((current.path, current.scroll)) }
        open(last.path, remember: false, scroll: last.scroll)
    }

    func goForward() {
        guard let next = forward.popLast() else { return setStatus("Nothing to go forward to.") }
        if let current = document { back.append((current.path, current.scroll)) }
        open(next.path, remember: false, scroll: next.scroll)
    }

    private func loadSide(_ path: String) {
        var out: [SideRow] = []
        let neighbours = (try? vault.neighbours(of: path)) ?? []
        let mentions = (try? vault.mentions(of: path)) ?? []
        func group(_ forward: Bool) -> [Vault.Neighbour] {
            var seen = Set<String>()
            return neighbours.filter { $0.forward == forward && seen.insert($0.path).inserted }
        }
        func title(_ path: String) -> String {
            let name = (path as NSString).lastPathComponent
            return filesIsNote(path) ? (name as NSString).deletingPathExtension : name
        }
        let outgoing = group(true)
        let incoming = group(false)
        out.append(SideRow(kind: .heading, text: "Links to  \(outgoing.count)"))
        for link in outgoing { out.append(SideRow(kind: .link, text: title(link.path), path: link.path, detail: link.via ?? link.kind.rawValue, isNote: filesIsNote(link.path), forward: true)) }
        out.append(SideRow(kind: .heading, text: "Linked from  \(incoming.count)"))
        for link in incoming {
            let mention = mentions.first { $0.path == link.path }.flatMap { found in Self.snippet(found.text).map { (found.line, $0) } }
            out.append(SideRow(kind: .link, text: title(link.path), path: link.path, line: mention?.0, detail: mention?.1 ?? link.via ?? link.kind.rawValue, isNote: filesIsNote(link.path), forward: false))
        }
        sideRows = out
        sideSelected = out.firstIndex { $0.kind == .link } ?? 0
        sideScroll = 0
    }

    /// A line of a note, as it reads with the Markdown marks gone. Nil if it says nothing, like a front-matter fence.
    static func snippet(_ line: String) -> String? {
        var text = line.replacingOccurrences(of: #"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]"#, with: "$1", options: .regularExpression)
        text = text.replacingOccurrences(of: #"\[([^\]]*)\]\([^)]*\)"#, with: "$1", options: .regularExpression)
        text = text.replacingOccurrences(of: "**", with: "").replacingOccurrences(of: "`", with: "")
        text = text.trimmingCharacters(in: CharacterSet(charactersIn: " #>-*"))
        return text.isEmpty ? nil : text
    }

    func setStatus(_ text: String?, problem: Bool = false) {
        status = text
        statusIsProblem = problem
    }

    // MARK: Lists that come from typing

    func updateQuickResults() {
        let query = quick.field.text
        if query.trimmingCharacters(in: .whitespaces).isEmpty {
            quick.results = Array(files.filter(\.isNote).prefix(200)) + Array(files.filter { !$0.isNote }.prefix(200))
        } else {
            let scored = files.compactMap { file -> (MapFile, Int)? in
                Fuzzy.score(query, in: file.path).map { (file, $0) }
            }
            quick.results = scored.sorted { $0.1 != $1.1 ? $0.1 > $1.1 : $0.0.path.count < $1.0.path.count }.prefix(200).map(\.0)
        }
        quick.selected = min(quick.selected, max(0, quick.results.count - 1))
    }

    func updateSearchResults() {
        let query = search.field.text
        search.selected = 0
        search.problem = nil
        guard !query.trimmingCharacters(in: .whitespaces).isEmpty else {
            search.results = []
            return
        }
        do {
            search.results = try vault.searchLines(query, scope: ask.scope, limit: 100)
        } catch {
            search.results = []
            search.problem = "That search can't be read. Try plain words."
        }
    }

    /// Whole vault, then each folder, for Tab and Shift-Tab.
    func cycleScope(by step: Int) {
        let choices: [String?] = [nil] + folders.map { Optional($0) }
        let current = choices.firstIndex { $0 == ask.scope } ?? 0
        ask.scope = choices[(current + step + choices.count) % choices.count]
    }

    var scopeLabel: String { ask.scope.map { "in \($0)" } ?? "in the whole vault" }

    var askBusy: Bool { ask.status != .idle }

    func centerStar() {
        if let path = document?.path {
            star.center = path
        } else if rows.indices.contains(treeSelected), !rows[treeSelected].isFolder {
            star.center = rows[treeSelected].path
        } else {
            star.center = files.first(where: \.isNote)?.path ?? files.first?.path
        }
        loadStar()
    }

    /// Reads what the star view shows. A star's second ring is only counted, because names two links away would be clutter.
    func loadStar() {
        star.selected = 0
        star.neighbours = []
        star.hidden = 0
        guard let center = star.center, let links = try? vault.neighbours(of: center) else { return }
        var seen = Set<String>()
        var out: [StarNeighbour] = []
        for link in links where link.path != center && seen.insert(link.path).inserted {
            let further = Set(((try? vault.neighbours(of: link.path)) ?? []).map(\.path)).subtracting([center]).count
            out.append(StarNeighbour(path: link.path, isNote: filesIsNote(link.path), forward: link.forward, kind: link.kind.rawValue, via: link.via, further: further))
        }
        let most = max(1, min(24, 2 * max(1, height - 8)))
        star.hidden = max(0, out.count - most)
        star.neighbours = Array(out.prefix(most))
    }

    var starCenterIsNote: Bool { star.center.map(filesIsNote) ?? false }
}

enum Fuzzy {
    /// Scores a typed query against a path, or nil if the letters don't all appear in order. The file's own name counts for more than its folder.
    static func score(_ query: String, in path: String) -> Int? {
        let wanted = Array(query.lowercased().filter { $0 != " " })
        guard !wanted.isEmpty else { return 0 }
        let name = (path as NSString).lastPathComponent
        if let inName = run(wanted, Array(name.lowercased())) { return inName + 100 }
        return run(wanted, Array(path.lowercased()))
    }

    private static func run(_ wanted: [Character], _ target: [Character]) -> Int? {
        var score = 0
        var at = 0
        var previous = -2
        for letter in wanted {
            guard let found = target[at...].firstIndex(of: letter) else { return nil }
            if found == previous + 1 { score += 10 }
            if found == 0 || "/ -_.".contains(target[found - 1]) { score += 8 }
            score -= min(3, found - at)
            previous = found
            at = found + 1
        }
        return score
    }
}

extension DocumentRenderer {
    func render(_ text: String, isNote: Bool) -> RenderedDocument { isNote ? renderNote(text) : renderCode(text) }
}
