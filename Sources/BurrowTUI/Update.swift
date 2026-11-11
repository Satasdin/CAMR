import BurrowCore
import BurrowTools
import Foundation

/// How keys change the model. Nothing here draws.
extension Model {
    /// Applies one key and returns anything the app must do outside the model.
    func handle(_ key: Key) -> [Effect] {
        if key == .control("c") { return [.quit] }
        if key == .control("z") { return [.suspend] }
        setStatus(nil)
        var effects: [Effect] = []
        switch overlay {
        case .help:
            if [.escape, .enter, .character("?"), .character("q")].contains(key) { overlay = .none }
        case .quickOpen: handleQuickOpen(key)
        case .search: handleSearch(key)
        case .none:
            switch page {
            case .vault: effects = handleVault(key)
            case .star: effects = handleStar(key)
            case .ask: effects = handleAsk(key)
            case .ledger: effects = handleLedger(key) ?? globalKey(key) ?? []
            case .conversations: effects = handleConversations(key) ?? globalKey(key) ?? []
            case .shelf: effects = handleShelf(key) ?? globalKey(key) ?? []
            case .programs: effects = handlePrograms(key) ?? globalKey(key) ?? []
            }
        }
        syncDocument()
        return effects
    }

    private func handleQuickOpen(_ key: Key) {
        switch key {
        case .escape: overlay = .none
        case .enter:
            if quick.results.indices.contains(quick.selected) {
                open(quick.results[quick.selected].path)
                quick = QuickOpenState()
            }
        case .up, .control("p"): quick.selected = max(0, quick.selected - 1)
        case .down, .control("n"): quick.selected = min(max(0, quick.results.count - 1), quick.selected + 1)
        default:
            if quick.field.apply(key) { updateQuickResults() }
        }
    }

    private func handleSearch(_ key: Key) {
        switch key {
        case .escape: overlay = .none
        case .enter:
            if search.results.indices.contains(search.selected) {
                let hit = search.results[search.selected]
                open(hit.path, line: hit.line)
            }
        case .up, .control("p"): search.selected = max(0, search.selected - 1)
        case .down, .control("n"): search.selected = min(max(0, search.results.count - 1), search.selected + 1)
        case .tab:
            cycleScope(by: 1)
            updateSearchResults()
        case .backTab:
            cycleScope(by: -1)
            updateSearchResults()
        default:
            if search.field.apply(key) { updateSearchResults() }
        }
    }

    func globalKey(_ key: Key) -> [Effect]? {
        switch key {
        case .character("q"): return [.quit]
        case .character("?"): overlay = .help
        case .character("/"):
            overlay = .search
            updateSearchResults()
        case .character("o"), .control("p"):
            quick = QuickOpenState()
            overlay = .quickOpen
            updateQuickResults()
        case .character("L"):
            go(.ledger)
        case let .character(digit) where ("1"..."5").contains(digit):
            if let place = Place(rawValue: Int(String(digit))!) { go(place) }
        case .character("a"):
            page = .ask
        case .character("*"), .character("s"):
            centerStar()
            page = .star
        case .character("R"):
            return [.reindex]
        default: return nil
        }
        return []
    }

    private func handleVault(_ key: Key) -> [Effect] {
        if let effects = globalKey(key) { return effects }
        switch key {
        case .character("i"):
            showSide.toggle()
            if !showSide, focus == .links { focus = .reader }
            return []
        case .character("["), .backspace:
            goBack()
            return []
        case .character("]"):
            goForward()
            return []
        default: break
        }
        switch focus {
        case .tree: handleTree(key)
        case .reader: handleReader(key)
        case .links: handleLinks(key)
        }
        return []
    }

    private func handleTree(_ key: Key) {
        guard !rows.isEmpty else { return }
        switch key {
        case .up, .character("k"): treeSelected = max(0, treeSelected - 1)
        case .down, .character("j"): treeSelected = min(rows.count - 1, treeSelected + 1)
        case .home, .character("g"): treeSelected = 0
        case .end, .character("G"): treeSelected = rows.count - 1
        case .pageUp, .control("u"): treeSelected = max(0, treeSelected - max(1, (layout.tree?.height ?? 10) / 2))
        case .pageDown, .control("d"): treeSelected = min(rows.count - 1, treeSelected + max(1, (layout.tree?.height ?? 10) / 2))
        case .right, .character("l"), .enter:
            let row = rows[treeSelected]
            if row.isFolder {
                if expanded.contains(row.path) {
                    if key != .enter, treeSelected + 1 < rows.count { treeSelected += 1 } else if key == .enter { expanded.remove(row.path); rebuildRows() }
                } else {
                    expanded.insert(row.path)
                    rebuildRows()
                }
            } else {
                open(row.path)
            }
        case .left, .character("h"):
            let row = rows[treeSelected]
            if row.isFolder, expanded.contains(row.path) {
                expanded.remove(row.path)
                rebuildRows()
            } else {
                let parent = (row.path as NSString).deletingLastPathComponent
                if let found = rows.firstIndex(where: { $0.path == parent }) { treeSelected = found }
            }
        case .tab:
            if document != nil { focus = .reader }
        default: break
        }
        keepTreeVisible()
    }

    private func handleReader(_ key: Key) {
        guard let current = document else {
            if [.left, .character("h"), .tab].contains(key) { focus = .tree }
            return
        }
        let page = max(1, readerRows - 2)
        switch key {
        case .up, .character("k"): scrollDocument(by: -1)
        case .down, .character("j"): scrollDocument(by: 1)
        case .pageDown, .character(" "), .control("d"): scrollDocument(by: page)
        case .pageUp, .control("u"), .character("b"): scrollDocument(by: -page)
        case .home, .character("g"): document?.scroll = 0
        case .end, .character("G"): document?.scroll = current.rendered.lines.count
        case .tab, .character("n"): stepLink(1)
        case .backTab, .character("N"): stepLink(-1)
        case .enter: followActiveLink()
        case .left, .character("h"):
            focus = .tree
        case .right, .character("l"):
            if showSide { focus = .links }
        default: break
        }
        keepDocumentInBounds()
    }

    private func scrollDocument(by amount: Int) {
        document?.scroll += amount
        document?.markedLine = nil
    }

    private func stepLink(_ step: Int) {
        guard let current = document, !current.rendered.links.isEmpty else { return setStatus("This page has no links.") }
        let count = current.rendered.links.count
        let next: Int
        if let active = current.activeLink {
            next = (active + step + count) % count
        } else {
            // Start from what's on the screen, not from the top of the file.
            let visible = current.rendered.lines[min(current.scroll, max(0, current.rendered.lines.count - 1))...].prefix(readerRows)
            let first = visible.flatMap { $0.spans.compactMap(\.link) }.first
            next = first ?? (step > 0 ? 0 : count - 1)
        }
        document?.activeLink = next
        if let line = current.rendered.lines.firstIndex(where: { $0.spans.contains { $0.link == next } }) {
            if line < current.scroll || line >= current.scroll + readerRows { document?.scroll = max(0, line - readerRows / 3) }
        }
        let link = current.rendered.links[next]
        setStatus(link.resolved.map { "→ \($0)" } ?? (link.isExternal ? "Web address: \(link.target)" : "No note called \(link.target) yet"))
    }

    private func followActiveLink() {
        guard let current = document else { return }
        guard let active = current.activeLink, current.rendered.links.indices.contains(active) else { return setStatus("Press Tab to pick a link first.") }
        let link = current.rendered.links[active]
        if let resolved = link.resolved {
            open(resolved)
        } else if link.isExternal {
            setStatus("Burrow doesn't open web addresses: \(link.target)")
        } else {
            setStatus("No note called \(link.target) yet.", problem: true)
        }
    }

    private func handleLinks(_ key: Key) {
        let selectable = sideRows.indices.filter { sideRows[$0].kind == .link }
        switch key {
        case .up, .character("k"):
            if let previous = selectable.last(where: { $0 < sideSelected }) { sideSelected = previous }
        case .down, .character("j"):
            if let next = selectable.first(where: { $0 > sideSelected }) { sideSelected = next }
        case .enter, .right, .character("l"):
            if sideRows.indices.contains(sideSelected), let path = sideRows[sideSelected].path { open(path, line: sideRows[sideSelected].line) }
        case .left, .character("h"), .tab: focus = .reader
        default: break
        }
    }

    // MARK: Star

    private func handleStar(_ key: Key) -> [Effect] {
        if key == .escape {
            page = .vault
            return []
        }
        let neighbours = star.neighbours
        switch key {
        case .up, .character("k"), .left, .character("h"), .backTab:
            if !neighbours.isEmpty { star.selected = (star.selected - 1 + neighbours.count) % neighbours.count }
        case .down, .character("j"), .right, .character("l"), .tab:
            if !neighbours.isEmpty { star.selected = (star.selected + 1) % neighbours.count }
        case .enter:
            if neighbours.indices.contains(star.selected) {
                star.center = neighbours[star.selected].path
                loadStar()
            }
        case .character(" "):
            if neighbours.indices.contains(star.selected) { open(neighbours[star.selected].path) }
        case .character("c"):
            if let center = star.center { open(center) }
        default:
            if key == .character("*") || key == .character("s") {
                page = .vault
                return []
            }
            return globalKey(key) ?? []
        }
        return []
    }

    // MARK: Ask

    private func handleAsk(_ key: Key) -> [Effect] {
        if askBusy {
            switch key {
            case .escape: return [.cancelAsk]
            case .up, .pageUp: ask.scrollUp += key == .up ? 1 : 10
            case .down, .pageDown: ask.scrollUp = max(0, ask.scrollUp - (key == .down ? 1 : 10))
            default: break
            }
            return []
        }
        let sources = ask.entries.last?.sources ?? []
        switch key {
        case .escape:
            page = .vault
        case .enter:
            let question = ask.field.text.trimmingCharacters(in: .whitespaces)
            guard !question.isEmpty else { return [] }
            ask.entries.append(AskEntry(question: question, scope: ask.scope))
            ask.field = TextField()
            ask.status = .searching
            ask.startedAt = Date()
            ask.scrollUp = 0
            ask.selectedSource = 0
            return [.ask(question: question, folder: ask.scope)]
        case .tab: cycleScope(by: 1)
        case .backTab: cycleScope(by: -1)
        case .control("n"):
            ask.selectedSource = min(max(0, sources.count - 1), ask.selectedSource + 1)
        case .control("p"):
            ask.selectedSource = max(0, ask.selectedSource - 1)
        case .control("o"):
            if sources.indices.contains(ask.selectedSource) { open(sources[ask.selectedSource].path, line: sources[ask.selectedSource].startLine) }
        case .up: ask.scrollUp += 1
        case .down: ask.scrollUp = max(0, ask.scrollUp - 1)
        case .pageUp: ask.scrollUp += 10
        case .pageDown: ask.scrollUp = max(0, ask.scrollUp - 10)
        default: _ = ask.field.apply(key)
        }
        return []
    }

    // MARK: Background results

    func askFound(_ found: VaultTools.Found) {
        guard !ask.entries.isEmpty else { return }
        let last = ask.entries.count - 1
        ask.entries[last].sources = found.retrieved.excerpts.map { ToolResult.Source(path: $0.path, startLine: $0.startLine, endLine: $0.endLine, reason: $0.reason.label) }
        ask.entries[last].how = found.how
        ask.status = .answering
    }

    func askWord(_ word: String) {
        guard !ask.entries.isEmpty else { return }
        ask.entries[ask.entries.count - 1].answer += TerminalText.clean(word)
    }

    func askFinished(seconds: Double) {
        guard !ask.entries.isEmpty else { return }
        ask.entries[ask.entries.count - 1].seconds = seconds
        ask.status = .idle
    }

    func askFailed(_ message: String) {
        guard !ask.entries.isEmpty else { return }
        ask.entries[ask.entries.count - 1].problem = message
        ask.status = .idle
    }
}
