import BurrowCore
import BurrowTools
import Foundation

/// The Ledger in the terminal: what AI sessions understood, as a list of commits beside the one picked.
struct LedgerViewState {
    var all: [LedgerCommit] = []
    var reverted: Set<String> = []
    /// Commit id → cited files that changed since it was written.
    var stale: [String: [String]] = [:]
    var branches: [String] = []
    /// 0 is every branch; then one per branch.
    var branchIndex = 0
    var selected = 0
    var showResume = false
    var resume = ""

    var branch: String? { branchIndex == 0 ? nil : branches[branchIndex - 1] }
    var commits: [LedgerCommit] { branch.map { name in all.filter { $0.branch == name } } ?? all }
    var picked: LedgerCommit? { commits.indices.contains(selected) ? commits[selected] : nil }
}

extension Model {
    func loadLedger() {
        let ledger = Ledger(vault: vault)
        var state = LedgerViewState()
        state.all = ledger.log(limit: 1_000)
        state.reverted = ledger.reverted()
        for commit in state.all { let changed = ledger.changed(commit); if !changed.isEmpty { state.stale[commit.id] = changed } }
        state.branches = Array(Set(state.all.map(\.branch))).sorted()
        if let old = ledgerView.branch, let index = state.branches.firstIndex(of: old) { state.branchIndex = index + 1 }
        state.selected = min(ledgerView.selected, max(0, state.commits.count - 1))
        ledgerView = state
    }

    func handleLedger(_ key: Key) -> [Effect]? {
        let count = ledgerView.commits.count
        switch key {
        case .escape:
            if ledgerView.showResume { ledgerView.showResume = false } else { page = .vault }
        case .up, .character("k"): ledgerView.selected = max(0, ledgerView.selected - 1)
        case .down, .character("j"): ledgerView.selected = min(max(0, count - 1), ledgerView.selected + 1)
        case .home, .character("g"): ledgerView.selected = 0
        case .end, .character("G"): ledgerView.selected = max(0, count - 1)
        case .tab, .backTab:
            let choices = ledgerView.branches.count + 1
            ledgerView.branchIndex = (ledgerView.branchIndex + (key == .tab ? 1 : choices - 1)) % choices
            ledgerView.selected = 0
            if ledgerView.showResume { ledgerView.resume = Ledger(vault: vault).resume(branch: ledgerView.branch) }
        case .character("r"):
            ledgerView.showResume.toggle()
            if ledgerView.showResume { ledgerView.resume = Ledger(vault: vault).resume(branch: ledgerView.branch) }
        case .enter:
            // Opens the first file the commit rests on that the vault still has.
            if let path = ledgerView.picked?.cites.keys.sorted().first(where: { path in files.contains { $0.path == path } }) {
                page = .vault
                open(path)
            } else {
                setStatus("That commit rests on no file this vault has.")
            }
        default:
            return nil
        }
        return []
    }
}

enum LedgerScreen {
    static func style(_ commit: LedgerCommit, _ state: LedgerViewState) -> Style {
        if state.reverted.contains(commit.id) || state.stale[commit.id] != nil || commit.kind == .correction { return .alert }
        switch commit.kind {
        case .handoff: return .code
        case .code: return .quiet
        default: return .strong
        }
    }

    static func draw(_ frame: inout Frame, _ model: Model, in body: Rect) {
        let state = model.ledgerView
        let filter = state.branch.map { "branch \($0)" } ?? "every branch"
        var x = frame.put(2, body.y, "Ledger", Style(ink: .note, bold: true))
        x = frame.put(x + 2, body.y, "\(state.commits.count) commit\(state.commits.count == 1 ? "" : "s") on \(filter)", .quiet)
        let flagged = state.commits.filter { state.reverted.contains($0.id) || state.stale[$0.id] != nil }.count
        if flagged > 0 { frame.put(x + 2, body.y, "\(flagged) to check", .alert) }

        let wide = model.width >= 96
        let listWidth = wide ? model.width * 46 / 100 : model.width - 4
        let listRows = wide ? body.height - 2 : max(3, (body.height - 2) / 2)
        let list = Rect(x: 2, y: body.y + 2, width: listWidth, height: listRows)
        let detail = wide ? Rect(x: list.right + 3, y: body.y + 2, width: model.width - list.right - 5, height: body.height - 2)
                          : Rect(x: 2, y: list.bottom + 1, width: model.width - 4, height: body.height - listRows - 3)

        guard !state.commits.isEmpty else {
            let message = "Nothing kept yet. Programs keep decisions, plans and where they stopped through burrow_commit and the hooks. Start with: burrow hook install claude <vault>"
            for (offset, line) in View.plainWrap(message, width: list.width).enumerated() where offset < list.height { frame.put(list.x, list.y + offset, line, .quiet) }
            if state.showResume { drawText(&frame, state.resume, in: detail) }
            return
        }
        let scroll = max(0, min(state.selected - list.height / 2, state.commits.count - list.height))
        for (offset, commit) in state.commits.dropFirst(scroll).prefix(list.height).enumerated() {
            let y = list.y + offset
            let index = scroll + offset
            let selected = index == state.selected
            let mark = style(commit, state)
            let when = Ledger.when(commit.at)
            let tail = "  " + (state.branch == nil ? commit.branch + " · " : "") + when
            let kind = Cells.pad(commit.kind.rawValue, to: 10)
            let room = max(6, list.width - 2 - 11 - Cells.width(of: tail))
            if selected {
                frame.put(list.x, y, Cells.pad("● " + kind + " " + Cells.truncate(commit.message, to: room) + tail, to: list.width), Style(ink: mark.ink, bold: true, reverse: true), limit: list.right)
            } else {
                var cursor = frame.put(list.x, y, "●", mark)
                cursor = frame.put(cursor + 1, y, kind, Style(ink: mark.ink, dim: mark.dim))
                cursor = frame.put(cursor + 1, y, Cells.truncate(commit.message, to: room), state.reverted.contains(commit.id) ? .quiet : .plain, limit: list.right)
                frame.put(list.right - Cells.width(of: tail), y, tail, .quiet, limit: list.right)
            }
        }
        if state.showResume {
            drawText(&frame, state.resume, in: detail, title: "What the next model is handed")
        } else if let commit = state.picked {
            drawCommit(&frame, commit, state, in: detail)
        }
    }

    private static func drawCommit(_ frame: inout Frame, _ commit: LedgerCommit, _ state: LedgerViewState, in area: Rect) {
        var y = area.y
        func line(_ text: String, _ style: Style) {
            for piece in View.plainWrap(text, width: area.width) where y < area.bottom {
                frame.put(area.x, y, piece, style, limit: area.right)
                y += 1
            }
        }
        var x = frame.put(area.x, y, commit.kind.rawValue.capitalized, Style(ink: style(commit, state).ink, bold: true))
        x = frame.put(x + 2, y, "\(commit.branch) · \(Ledger.when(commit.at)) · \(commit.id)", .quiet, limit: area.right)
        y += 2
        if state.reverted.contains(commit.id) { line("Marked wrong: a later correction says what is right.", .alert) }
        if let changed = state.stale[commit.id] { line("Check again: \(changed.joined(separator: ", ")) changed since this was written.", .alert) }
        line(commit.message, state.reverted.contains(commit.id) ? .quiet : .strong)
        if !commit.body.isEmpty {
            y += 1
            for paragraph in commit.body.components(separatedBy: "\n") { line(paragraph, .quiet) }
        }
        y += 1
        line("Written by \(commit.author)\(commit.client.map { " in \($0)" } ?? "")\(commit.sha.map { " · git \($0.prefix(10))" } ?? "")", .quiet)
        if !commit.cites.isEmpty, y < area.bottom - 1 {
            y += 1
            line("Rests on", Style(ink: .note, bold: true))
            for path in commit.cites.keys.sorted() where y < area.bottom {
                let changed = state.stale[commit.id]?.contains(path) == true
                frame.put(area.x, y, Cells.truncate((changed ? "✗ " : "· ") + path + (changed ? "  changed" : ""), to: area.width), changed ? .alert : .code, limit: area.right)
                y += 1
            }
        }
    }

    private static func drawText(_ frame: inout Frame, _ text: String, in area: Rect, title: String? = nil) {
        var y = area.y
        if let title {
            frame.put(area.x, y, title, Style(ink: .code, bold: true))
            y += 2
        }
        for paragraph in text.components(separatedBy: "\n") {
            for piece in View.plainWrap(paragraph, width: area.width) where y < area.bottom {
                frame.put(area.x, y, piece, piece.hasPrefix("<") ? .quiet : .plain, limit: area.right)
                y += 1
            }
        }
    }
}
