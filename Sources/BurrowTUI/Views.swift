import BurrowCore
import BurrowTools
import Foundation

/// Draws the model. Nothing here changes it, so the same state always draws the same frame.
enum View {
    static func render(_ model: Model) -> Frame {
        var frame = Frame(width: model.width, height: model.height)
        guard model.width >= Layout.minimumWidth, model.height >= Layout.minimumHeight else {
            let message = "Burrow needs \(Layout.minimumWidth)×\(Layout.minimumHeight) or more."
            frame.put(0, 0, Cells.truncate(message, to: model.width), .plain)
            frame.put(0, min(1, model.height - 1), Cells.truncate("This window is \(model.width)×\(model.height).", to: model.width), .quiet)
            return frame
        }
        drawTitle(&frame, model)
        let top = Layout.bodyTop(height: model.height)
        let body = Rect(x: 0, y: top, width: model.width, height: Layout.bodyHeight(height: model.height))
        switch model.page {
        case .vault: drawVault(&frame, model)
        case .star: StarMap.draw(&frame, model, in: body)
        case .ask: drawAsk(&frame, model, in: body)
        case .ledger: LedgerScreen.draw(&frame, model, in: body)
        case .conversations: PlacesScreen.drawConversations(&frame, model, in: body)
        case .shelf: PlacesScreen.drawShelf(&frame, model, in: body)
        case .programs: PlacesScreen.drawPrograms(&frame, model, in: body)
        }
        drawStatus(&frame, model)
        drawHints(&frame, model)
        switch model.overlay {
        case .none: break
        case .help: drawHelp(&frame, model)
        case .quickOpen: drawQuickOpen(&frame, model)
        case .search: drawSearch(&frame, model)
        }
        return frame
    }

    // MARK: Top and bottom

    /// The places, one row under the title: the same five as the Mac app, each with what it holds.
    private static func drawPlaces(_ frame: inout Frame, _ model: Model) {
        guard Layout.bodyTop(height: model.height) >= 2 else { return }
        let current = Place.of(model.page)
        let ledger = model.ledgerView
        let flagged = ledger.all.filter { ledger.reverted.contains($0.id) || ledger.stale[$0.id] != nil }.count
        let staleCaches = model.places.shelf.filter { $0.stale != nil }.count
        var x = 1
        for place in Place.allCases {
            let count: (String, Style)?
            switch place {
            case .library: count = (model.files.count.description, .quiet)
            case .conversations: count = model.places.sessions.isEmpty ? nil : (model.places.sessions.count.description, Style(ink: .talk))
            case .ledger: count = ledger.all.isEmpty ? nil : flagged > 0 ? ("\(ledger.all.count) · \(flagged)!", .alert) : (ledger.all.count.description, .quiet)
            case .shelf: count = model.places.shelf.isEmpty ? nil : staleCaches > 0 ? ("\(model.places.shelf.count) · \(staleCaches)!", .alert) : (model.places.shelf.count.description, Style(ink: .cache))
            case .programs: count = nil
            }
            let label = " \(place.rawValue) \(place.title) "
            let cost = Cells.width(of: label) + (count.map { Cells.width(of: $0.0) + 1 } ?? 0) + 1
            if x + cost > model.width - 1 { break }
            if place == current {
                x = frame.put(x, 1, label, Style(ink: .note, bold: true, reverse: true))
            } else {
                x = frame.put(x, 1, " ", .plain)
                x = frame.put(x, 1, "\(place.rawValue)", .quiet)
                x = frame.put(x + 1, 1, place.title + " ", .plain)
            }
            if let count { x = frame.put(x + 1, 1, count.0, count.1) }
            x += 2
        }
    }

    private static func drawTitle(_ frame: inout Frame, _ model: Model) {
        drawPlaces(&frame, model)
        var x = frame.put(1, 0, "✦ burrow", Style(ink: .note, bold: true))
        x = frame.put(x, 0, "  " + model.vault.root.lastPathComponent, .quiet)
        var right: String
        if let indexing = model.indexing {
            right = indexing
        } else if let stats = model.stats {
            right = "\(stats.notes) notes  \(stats.files) code  \(stats.vectors > 0 ? "meaning on" : "words only")"
        } else {
            right = ""
        }
        right = Cells.truncate(right, to: max(0, model.width / 2 - 2))
        let rightX = model.width - Cells.width(of: right) - 1
        frame.put(rightX, 0, right, model.indexing != nil ? Style(ink: .note, dim: true) : .quiet)
        if model.page == .vault, let path = model.document?.path {
            let room = rightX - x - 4
            if room > 8 {
                let folder = (path as NSString).deletingLastPathComponent
                let name = (path as NSString).lastPathComponent
                let trail = folder.isEmpty ? name : folder.replacingOccurrences(of: "/", with: " / ") + " / " + name
                frame.put(x + 2, 0, Cells.truncateLeft(trail, to: room), .quiet)
            }
        }
    }

    private static func drawStatus(_ frame: inout Frame, _ model: Model) {
        let y = model.height - 2
        if let status = model.status {
            frame.put(2, y, Cells.truncate(status, to: model.width - 12), model.statusIsProblem ? .alert : .quiet)
        }
        if model.page == .vault, model.overlay == .none, let document = model.document, document.rendered.lines.count > model.readerRows {
            let last = max(1, document.rendered.lines.count - model.readerRows)
            let text = "\(min(100, document.scroll * 100 / last))%"
            frame.put(model.width - Cells.width(of: text) - 2, y, text, .quiet)
        }
    }

    private static func hints(_ model: Model) -> [(String, String)] {
        switch model.overlay {
        case .help: return [("esc", "close")]
        case .quickOpen: return [("type", "to filter"), ("↑↓", "pick"), ("⏎", "open"), ("esc", "close")]
        case .search: return [("type", "to search"), ("↑↓", "pick"), ("⏎", "open"), ("tab", "folder"), ("esc", "close")]
        case .none: break
        }
        switch model.page {
        case .star: return [("←→", "pick"), ("⏎", "centre here"), ("space", "open"), ("c", "open centre"), ("esc", "back"), ("?", "keys")]
        case .ask:
            if model.askBusy { return [("↑↓", "scroll"), ("esc", "stop")] }
            return [("⏎", "ask"), ("tab", "folder"), ("↑↓", "scroll"), ("^N ^P", "pick source"), ("^O", "open source"), ("esc", "back")]
        case .ledger:
            return [("↑↓", "pick"), ("tab", "branch"), ("⏎", "open its file"), ("r", "resume"), ("1-5", "places"), ("?", "keys")]
        case .conversations:
            return [("↑↓", "pick"), ("tab", "program"), ("⏎", "open a file it read"), ("1-5", "places"), ("?", "keys"), ("q", "quit")]
        case .shelf:
            return [("↑↓", "pick"), ("⏎", "open its file"), ("1-5", "places"), ("?", "keys"), ("q", "quit")]
        case .programs:
            return [("↑↓", "pick"), ("⏎", "its conversations"), ("1-5", "places"), ("?", "keys"), ("q", "quit")]
        case .vault:
            let common = [("/", "search"), ("o", "open"), ("1-5", "places"), ("s", "star"), ("?", "keys"), ("q", "quit")]
            switch model.focus {
            case .tree: return [("↑↓", "move"), ("→", "open"), ("←", "fold")] + common
            case .reader: return [("↑↓", "scroll"), ("tab", "next link"), ("⏎", "follow"), ("[", "back"), ("←", "files")] + common
            case .links: return [("↑↓", "move"), ("⏎", "open"), ("←", "reader")] + common
            }
        }
    }

    private static func drawHints(_ frame: inout Frame, _ model: Model) {
        let y = model.height - 1
        var x = 2
        for (key, label) in hints(model) {
            let cost = Cells.width(of: key) + 1 + Cells.width(of: label) + 3
            if x + cost > model.width { break }
            x = frame.put(x, y, key, .strong)
            x = frame.put(x + 1, y, label, .quiet)
            x += 3
        }
    }

    // MARK: The vault page

    private static func drawVault(_ frame: inout Frame, _ model: Model) {
        let layout = model.layout
        if let area = layout.tree { drawTree(&frame, model, in: area) }
        if let area = layout.reader { drawReader(&frame, model, in: area) }
        if let area = layout.side { drawSide(&frame, model, in: area) }
    }

    private static func heading(_ frame: inout Frame, _ text: String, focused: Bool, at x: Int, _ y: Int) {
        frame.put(x, y, text, focused ? Style(ink: .note, bold: true) : .quiet)
    }

    private static func drawTree(_ frame: inout Frame, _ model: Model, in area: Rect) {
        let focused = model.focus == .tree
        heading(&frame, "Files", focused: focused, at: area.x + 1, area.y)
        let listTop = area.y + 1
        let rowsShown = area.height - 1
        guard !model.rows.isEmpty else {
            let message = model.indexing != nil ? "Reading the vault…" : "Nothing here yet. Add a Markdown file, then press R."
            for (offset, line) in plainWrap(message, width: area.width - 2).enumerated() { frame.put(area.x + 1, listTop + 1 + offset, line, .quiet) }
            return
        }
        for (offset, row) in model.rows.dropFirst(model.treeScroll).prefix(rowsShown).enumerated() {
            let y = listTop + offset
            let index = model.treeScroll + offset
            let selected = index == model.treeSelected
            let indent = String(repeating: "  ", count: row.depth)
            let glyph: String
            var style = Style.plain
            if row.isFolder {
                glyph = model.expanded.contains(row.path) ? "▾" : "▸"
                style.bold = row.depth == 0
            } else {
                glyph = row.isNote ? "•" : "·"
                style.ink = Model.ink(for: row.path)
            }
            if model.document?.path == row.path {
                style.bold = true
                style.ink = row.isNote ? .note : Model.ink(for: row.path)
            }
            let suffix = row.isLinked ? " ⇄" : ""
            let text = indent + glyph + " " + Cells.truncate(row.name, to: max(4, area.width - 3 - Cells.width(of: indent) - Cells.width(of: suffix))) + suffix
            if selected && focused {
                frame.put(area.x, y, Cells.pad(" " + text, to: area.width), Style(bold: true, reverse: true), limit: area.right)
            } else {
                frame.put(area.x + 1, y, text, selected ? Style(ink: style.ink, bold: true, underline: true) : style, limit: area.right)
            }
        }
    }

    private static func drawReader(_ frame: inout Frame, _ model: Model, in area: Rect) {
        guard let document = model.document else {
            if model.rows.isEmpty {
                frame.put(area.x + 2, area.y + 1, Cells.truncate("This vault has nothing to read yet.", to: area.width - 2), .quiet)
            } else {
                PlacesScreen.drawLibraryGlance(&frame, model, in: area)
            }
            return
        }
        let textX = area.x + max(1, (area.width - document.renderedWidth) / 2)
        for (offset, line) in document.rendered.lines.dropFirst(document.scroll).prefix(area.height).enumerated() {
            let y = area.y + offset
            var x = textX
            for span in line.spans {
                var style = span.style
                if let link = span.link, link == document.activeLink { style.reverse = true }
                x = frame.put(x, y, span.text, style, limit: area.right)
            }
            if document.markedLine == line.source { frame.put(textX - 2, y, "▸", Style(ink: .note, bold: true)) }
        }
    }

    private static func drawSide(_ frame: inout Frame, _ model: Model, in area: Rect) {
        guard !model.sideRows.isEmpty else {
            heading(&frame, "Links", focused: model.focus == .links, at: area.x, area.y)
            frame.put(area.x, area.y + 2, "Open a note to see its links.", .quiet, limit: area.right)
            return
        }
        var lines: [(text: String, style: Style, row: Int)] = []
        for (index, row) in model.sideRows.enumerated() {
            if row.kind == .heading {
                if index > 0 { lines.append(("", .plain, index)) }
                lines.append((row.text, Style(ink: model.focus == .links ? .note : .plain, bold: model.focus == .links, dim: model.focus != .links), index))
            } else {
                lines.append(("\(row.forward ? "→" : "←") \(row.text)", Style(ink: row.isNote ? .plain : .code), index))
                if let detail = row.detail, !detail.isEmpty { lines.append(("  \(detail)", .quiet, index)) }
            }
        }
        let selectedLine = lines.firstIndex { $0.row == model.sideSelected && model.sideRows[$0.row].kind == .link } ?? 0
        let scroll = max(0, min(selectedLine - area.height / 2, lines.count - area.height))
        for (offset, line) in lines.dropFirst(scroll).prefix(area.height).enumerated() {
            let y = area.y + offset
            let isSelected = line.row == model.sideSelected && model.sideRows[line.row].kind == .link && !line.text.hasPrefix("  ")
            var style = line.style
            if isSelected, model.focus == .links { style = Style(ink: style.ink, bold: true, reverse: true) }
            frame.put(area.x, y, Cells.truncate(line.text, to: area.width), style, limit: area.right)
        }
    }

    // MARK: Ask

    static func plainWrap(_ text: String, width: Int) -> [String] {
        var lines: [String] = []
        var current = ""
        var used = 0
        for word in text.split(separator: " ", omittingEmptySubsequences: false) {
            let cost = Cells.width(of: String(word))
            if used > 0, used + 1 + cost > width {
                lines.append(current)
                current = ""
                used = 0
            }
            if used > 0 {
                current += " "
                used += 1
            }
            current += word
            used += cost
        }
        lines.append(current)
        return lines
    }

    static func askLines(_ model: Model, width: Int) -> [DocLine] {
        var out: [DocLine] = []
        let renderer = DocumentRenderer(width: width, isNote: { _ in false }, resolve: { _ in nil })
        for (index, entry) in model.ask.entries.enumerated() {
            if index > 0 {
                out.append(DocLine(spans: [], source: 0))
                out.append(DocLine(spans: [], source: 0))
            }
            for line in plainWrap(entry.question, width: width - 2) {
                out.append(DocLine(spans: [DocSpan(text: "› ", style: Style(ink: .note, bold: true)), DocSpan(text: line, style: .strong)], source: 0))
            }
            if let scope = entry.scope { out.append(DocLine(spans: [DocSpan(text: "  in \(scope)", style: .quiet)], source: 0)) }
            out.append(DocLine(spans: [], source: 0))
            let isLast = index == model.ask.entries.count - 1
            if isLast, model.askBusy {
                let elapsed = model.ask.startedAt.map { String(format: " %.0f s", Date().timeIntervalSince($0)) } ?? ""
                let words = model.ask.status == .searching ? "Looking through the vault…" : "\(model.modelName) is reading \(entry.sources.count) excerpts…"
                if entry.answer.isEmpty { out.append(DocLine(spans: [DocSpan(text: words + elapsed, style: Style(ink: .note, dim: true))], source: 0)) }
            }
            if !entry.answer.isEmpty { out += renderer.renderNote(entry.answer).lines }
            if let problem = entry.problem {
                for line in plainWrap("✗ " + problem, width: width) { out.append(DocLine(spans: [DocSpan(text: line, style: .alert)], source: 0)) }
            }
            if let seconds = entry.seconds {
                out.append(DocLine(spans: [], source: 0))
                out.append(DocLine(spans: [DocSpan(text: String(format: "%.1f s  ·  %@", seconds, entry.how), style: .quiet)], source: 0))
            }
        }
        return out
    }

    private static func drawAsk(_ frame: inout Frame, _ model: Model, in body: Rect) {
        let inputRows = 2
        let showSources = model.width >= 88
        let sourceWidth = showSources ? min(38, model.width * 30 / 100) : 0
        let transcriptX = 2
        let transcriptWidth = min(Layout.readingMeasure, model.width - transcriptX - (showSources ? sourceWidth + 4 : 2))
        let sourcesRows = showSources ? 0 : min(5, (model.ask.entries.last?.sources.count ?? 0) + 1)
        let transcriptRows = max(1, body.height - inputRows - 1 - sourcesRows)

        let lines = askLines(model, width: transcriptWidth)
        if lines.isEmpty {
            frame.put(transcriptX, body.y + 1, "Ask anything about this vault.", .strong)
            frame.put(transcriptX, body.y + 2, Cells.truncate("\(model.modelName) answers on this Mac and shows what it read.", to: transcriptWidth), .quiet)
        }
        let scroll = max(0, lines.count - transcriptRows - min(model.ask.scrollUp, max(0, lines.count - transcriptRows)))
        for (offset, line) in lines.dropFirst(scroll).prefix(transcriptRows).enumerated() {
            var x = transcriptX
            for span in line.spans { x = frame.put(x, body.y + offset, span.text, span.style, limit: transcriptX + transcriptWidth) }
        }

        let sources = model.ask.entries.last?.sources ?? []
        if showSources {
            drawSources(&frame, model, sources, in: Rect(x: model.width - sourceWidth - 1, y: body.y, width: sourceWidth, height: transcriptRows + 1))
        } else if !sources.isEmpty {
            let y = body.y + transcriptRows
            for (offset, source) in sources.prefix(sourcesRows).enumerated() {
                let selected = offset == model.ask.selectedSource
                let text = Cells.truncateLeft("\(offset + 1) \(source.path):\(source.startLine)", to: model.width - 4)
                frame.put(transcriptX, y + offset, text, selected ? Style(reverse: true) : .quiet)
            }
        }

        let scopeY = body.bottom - inputRows
        frame.put(transcriptX, scopeY, Cells.truncate(model.scopeLabel, to: model.width - 4), Style(ink: .note, dim: true))
        let inputY = scopeY + 1
        let prompt = frame.put(transcriptX, inputY, "› ", Style(ink: .note, bold: true))
        let field = model.ask.field.visible(width: model.width - prompt - 2)
        if model.ask.field.text.isEmpty, !model.askBusy {
            frame.put(prompt, inputY, "Type a question", .quiet)
        } else {
            frame.put(prompt, inputY, field.text, model.askBusy ? .quiet : .plain)
        }
        if !model.askBusy, model.overlay == .none { frame.cursor = (prompt + field.cursorColumn, inputY) }
    }

    private static func drawSources(_ frame: inout Frame, _ model: Model, _ sources: [ToolResult.Source], in area: Rect) {
        heading(&frame, sources.isEmpty ? "Sources" : "Sources  \(sources.count)", focused: false, at: area.x, area.y)
        guard !sources.isEmpty else {
            frame.put(area.x, area.y + 2, Cells.truncate("What the model reads shows here.", to: area.width), .quiet)
            return
        }
        let rowsShown = max(1, (area.height - 2) / 2)
        let first = max(0, min(model.ask.selectedSource - rowsShown / 2, sources.count - rowsShown))
        for (offset, source) in sources.dropFirst(first).prefix(rowsShown).enumerated() {
            let index = first + offset
            let selected = index == model.ask.selectedSource
            let y = area.y + 2 + offset * 2
            let isNote = source.path.lowercased().hasSuffix(".md")
            let name = (source.path as NSString).lastPathComponent
            let line = Cells.pad(Cells.truncate("\(index + 1)  \(name):\(source.startLine)", to: area.width - 1), to: area.width - 1)
            frame.put(area.x, y, line, selected ? Style(ink: isNote ? .note : .code, bold: true, reverse: true) : Style(ink: isNote ? .plain : .code))
            frame.put(area.x + 3, y + 1, Cells.truncate(source.reason, to: area.width - 4), .quiet)
        }
    }

    // MARK: Overlays

    private static func box(_ frame: inout Frame, _ rect: Rect, title: String) {
        frame.clear(rect.x, rect.y, width: rect.width, height: rect.height)
        let edge = Style(dim: true)
        frame.put(rect.x, rect.y, "╭─ ", edge)
        let end = frame.put(rect.x + 3, rect.y, title, Style(ink: .note, bold: true))
        frame.put(end, rect.y, " " + String(repeating: "─", count: max(0, rect.right - end - 2)) + "╮", edge)
        for y in (rect.y + 1)..<(rect.bottom - 1) {
            frame.put(rect.x, y, "│", edge)
            frame.put(rect.right - 1, y, "│", edge)
        }
        frame.put(rect.x, rect.bottom - 1, "╰" + String(repeating: "─", count: max(0, rect.width - 2)) + "╯", edge)
    }

    private static func listStart(selected: Int, count: Int, rows: Int) -> Int { max(0, min(selected - rows / 2, count - rows)) }

    private static func drawField(_ frame: inout Frame, _ field: TextField, placeholder: String, at x: Int, _ y: Int, width: Int) {
        let prompt = frame.put(x, y, "› ", Style(ink: .note, bold: true))
        let shown = field.visible(width: width - 2)
        if field.text.isEmpty { frame.put(prompt, y, placeholder, .quiet, limit: x + width) } else { frame.put(prompt, y, shown.text, .plain) }
        frame.cursor = (prompt + shown.cursorColumn, y)
    }

    private static func drawQuickOpen(_ frame: inout Frame, _ model: Model) {
        let width = min(76, model.width - 4)
        let height = min(18, model.height - 3)
        let rect = Rect(x: (model.width - width) / 2, y: 1, width: width, height: height)
        box(&frame, rect, title: "Open")
        drawField(&frame, model.quick.field, placeholder: "Name of a note or file", at: rect.x + 2, rect.y + 1, width: width - 4)
        let rows = height - 4
        guard !model.quick.results.isEmpty else {
            frame.put(rect.x + 2, rect.y + 3, "Nothing has that name.", .quiet)
            return
        }
        let first = listStart(selected: model.quick.selected, count: model.quick.results.count, rows: rows)
        for (offset, file) in model.quick.results.dropFirst(first).prefix(rows).enumerated() {
            let y = rect.y + 3 + offset
            let selected = first + offset == model.quick.selected
            let name = (file.path as NSString).lastPathComponent
            let shown = file.isNote ? (name as NSString).deletingPathExtension : name
            let folder = (file.path as NSString).deletingLastPathComponent
            let glyph = file.isNote ? "• " : "· "
            if selected { frame.put(rect.x + 1, y, String(repeating: " ", count: width - 2), Style(reverse: true)) }
            var x = frame.put(rect.x + 2, y, glyph, Style(ink: file.isNote ? .note : .code, reverse: selected))
            x = frame.put(x, y, Cells.truncate(shown, to: width / 2), Style(bold: selected, reverse: selected), limit: rect.right - 2)
            frame.put(x + 2, y, Cells.truncateLeft(folder, to: max(0, rect.right - x - 5)), Style(dim: !selected, reverse: selected), limit: rect.right - 2)
        }
    }

    private static func drawSearch(_ frame: inout Frame, _ model: Model) {
        let width = min(100, model.width - 4)
        let height = model.height - 3
        let rect = Rect(x: (model.width - width) / 2, y: 1, width: width, height: height)
        box(&frame, rect, title: "Search")
        drawField(&frame, model.search.field, placeholder: "Words to find", at: rect.x + 2, rect.y + 1, width: width - 4)
        frame.put(rect.x + 2, rect.y + 2, Cells.truncate(model.scopeLabel, to: width - 4), Style(ink: .note, dim: true))
        let rows = height - 5
        if let problem = model.search.problem {
            frame.put(rect.x + 2, rect.y + 4, problem, .alert)
            return
        }
        guard !model.search.results.isEmpty else {
            let word = model.search.field.text.trimmingCharacters(in: .whitespaces).isEmpty ? "Every line in the vault is searchable." : "No line holds those words."
            frame.put(rect.x + 2, rect.y + 4, word, .quiet)
            return
        }
        let words = model.search.field.text.lowercased().split(separator: " ").map(String.init)
        let first = listStart(selected: model.search.selected, count: model.search.results.count, rows: rows)
        for (offset, hit) in model.search.results.dropFirst(first).prefix(rows).enumerated() {
            let y = rect.y + 4 + offset
            let selected = first + offset == model.search.selected
            if selected { frame.put(rect.x + 1, y, String(repeating: " ", count: width - 2), Style(reverse: true)) }
            let isNote = (hit.path as NSString).pathExtension.lowercased() == "md"
            let place = Cells.truncateLeft("\(hit.path):\(hit.line)", to: min(38, width / 2 - 2))
            let x = frame.put(rect.x + 2, y, place, Style(ink: isNote ? .note : .code, reverse: selected))
            let start = max(x + 2, rect.x + 40)
            putHighlighted(&frame, hit.text, words: words, at: start, y, limit: rect.right - 2, selected: selected)
        }
    }

    private static func putHighlighted(_ frame: inout Frame, _ text: String, words: [String], at x: Int, _ y: Int, limit: Int, selected: Bool) {
        let clean = DocumentRenderer.expandTabs(text)
        let characters = Array(clean)
        let lowered = Array(clean.lowercased())
        var marked = Array(repeating: false, count: characters.count)
        if lowered.count == characters.count {
            for word in words {
                let needle = Array(word)
                guard !needle.isEmpty, lowered.count >= needle.count else { continue }
                for start in 0...(lowered.count - needle.count) where Array(lowered[start..<(start + needle.count)]) == needle {
                    for index in start..<(start + needle.count) { marked[index] = true }
                }
            }
        }
        var column = x
        for (index, character) in characters.enumerated() {
            if column + Cells.width(of: character) > limit { break }
            column = frame.put(column, y, String(character), Style(ink: marked[index] ? .note : .plain, bold: marked[index], dim: !marked[index] && !selected, reverse: selected), limit: limit)
        }
    }

    private static let helpSections: [(String, [(String, String)])] = [
        ("Anywhere", [("/", "search every line"), ("o  ^P", "open by name"), ("1 – 5", "Library, Conversations, Ledger, Shelf, Programs"), ("s  *", "star view"), ("R", "re-index, with meaning if Ollama is up"), ("?", "these keys"), ("q  ^C", "quit"), ("^Z", "suspend")]),
        ("Files", [("↑↓ j k", "move"), ("→ l ⏎", "open or unfold"), ("← h", "fold or go up"), ("tab", "to the reader")]),
        ("Reader", [("↑↓ j k", "scroll"), ("space b", "page"), ("g G", "top, end"), ("tab n", "next link"), ("⇧tab N", "last link"), ("⏎", "follow the link"), ("[  ]", "back, forward"), ("← →", "files, links"), ("i", "hide or show links")]),
        ("Conversations", [("↑↓", "pick one"), ("tab", "one program"), ("⏎", "open a file it read")]),
        ("Ledger", [("↑↓ j k", "pick a commit"), ("tab", "next branch"), ("⏎", "open the file it rests on"), ("r", "what the next model is handed")]),
        ("Star", [("←→ ↑↓", "pick a star"), ("⏎", "centre on it"), ("space", "open it"), ("c", "open the centre")]),
    ]

    private static func drawHelp(_ frame: inout Frame, _ model: Model) {
        let columns = model.width >= 84 ? 2 : 1
        let width = min(model.width - 4, columns == 2 ? 84 : 44)
        let height = model.height - 3
        let rect = Rect(x: (model.width - width) / 2, y: 1, width: width, height: height)
        box(&frame, rect, title: "Keys")
        var x = rect.x + 3
        var y = rect.y + 2
        let columnWidth = (width - 6) / columns
        for section in helpSections {
            let needed = section.1.count + 2
            if y + needed > rect.bottom - 1, columns == 2, x == rect.x + 3 {
                x += columnWidth
                y = rect.y + 2
            }
            if y >= rect.bottom - 1 { break }
            frame.put(x, y, section.0, Style(ink: .note, bold: true))
            y += 1
            for (key, label) in section.1 where y < rect.bottom - 1 {
                frame.put(x, y, key, .strong)
                frame.put(x + 11, y, Cells.truncate(label, to: columnWidth - 13), .quiet)
                y += 1
            }
            y += 1
        }
    }
}
