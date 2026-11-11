import BurrowCore
import BurrowTools
import Foundation

/// The places across the top of the terminal view, the same as the Mac app's sidebar: the files themselves, what
/// programs did with them, what AIs understood, the models' saved memory, and the programs that connect.
enum Place: Int, CaseIterable {
    case library = 1, conversations, ledger, shelf, programs

    var title: String {
        switch self {
        case .library: return "Library"
        case .conversations: return "Conversations"
        case .ledger: return "Ledger"
        case .shelf: return "Shelf"
        case .programs: return "Programs"
        }
    }

    var page: Page {
        switch self {
        case .library: return .vault
        case .conversations: return .conversations
        case .ledger: return .ledger
        case .shelf: return .shelf
        case .programs: return .programs
        }
    }

    static func of(_ page: Page) -> Place? { allCases.first { $0.page == page } }
}

/// A connected program, named the way a person knows it.
enum Client: String, CaseIterable {
    case claudeCode = "Claude Code", openCode = "OpenCode", lmStudio = "LM Studio", llamaCpp = "llama.cpp", ollama = "Ollama", other = "Other"

    static let known: [Client] = [.claudeCode, .openCode, .lmStudio, .llamaCpp, .ollama]

    init(_ client: String?) {
        let name = (client ?? "").lowercased().replacingOccurrences(of: " ", with: "").replacingOccurrences(of: "-", with: "")
        if name.contains("claude") { self = .claudeCode }
        else if name.contains("opencode") { self = .openCode }
        else if name.contains("lmstudio") { self = .lmStudio }
        else if name.contains("ollama") { self = .ollama }   // before llama.cpp: "ollama" contains "llama"
        else if name.contains("llama") { self = .llamaCpp }
        else { self = .other }
    }

    var setup: String {
        switch self {
        case .claudeCode: return "claude mcp add burrow -- burrow mcp <vault>, then burrow hook install claude <vault>"
        case .openCode: return "opencode.json: \"mcp\": { \"burrow\": { \"type\": \"local\", \"command\": [\"burrow\", \"mcp\", \"<vault>\"] } }"
        case .lmStudio: return "~/.lmstudio/mcp.json: \"burrow\": { \"command\": \"burrow\", \"args\": [\"mcp\", \"<vault>\"] }"
        case .llamaCpp: return "llama-server --jinja --slot-save-path <vault>/.burrow/kv, then an MCP client: burrow mcp <vault> --llama URL"
        case .ollama: return "a 16k model alias (docs/connect.md), then OpenCode's ollama provider with burrow mcp <vault>"
        case .other: return "burrow mcp <vault>"
        }
    }
}

/// What the Conversations, Shelf and Programs pages read, loaded when one of them opens.
struct PlacesState {
    var sessions: [SessionRecord] = []
    var conversationFilter: Client?
    var conversationSelected = 0
    var shelf: [(entry: KVShelf.Entry, stale: String?)] = []
    var shelfSelected = 0
    var programSelected = 0

    var conversations: [SessionRecord] {
        guard let conversationFilter else { return sessions }
        return sessions.filter { Client($0.client) == conversationFilter }
    }

    var clientsShown: [Client] { Client.known + (sessions.contains { Client($0.client) == .other } ? [.other] : []) }

    func today(_ client: Client) -> [TrailStep] {
        sessions.filter { Client($0.client) == client }.flatMap { $0.trail ?? [] }.filter { Calendar.current.isDateInToday($0.at) }
    }

    func active(_ client: Client) -> Bool {
        sessions.contains { Client($0.client) == client && Date().timeIntervalSince($0.updated) < 30 * 60 }
    }
}

extension Model {
    func loadPlaces() {
        var state = places
        state.sessions = SessionStore(vault: vault).list().filter { !$0.isEmpty }
        let shelf = KVShelf(vault: vault)
        state.shelf = shelf.entries().map { ($0, shelf.stale($0, model: $0.model)) }
            .sorted { ($0.entry.lastUsed ?? $0.entry.created) > ($1.entry.lastUsed ?? $1.entry.created) }
        state.conversationSelected = min(state.conversationSelected, max(0, state.conversations.count - 1))
        state.shelfSelected = min(state.shelfSelected, max(0, state.shelf.count - 1))
        places = state
        loadLedger()
    }

    func go(_ place: Place) {
        loadPlaces()
        page = place.page
    }

    private func move(_ value: inout Int, _ key: Key, count: Int) -> Bool {
        switch key {
        case .up, .character("k"): value = max(0, value - 1)
        case .down, .character("j"): value = min(max(0, count - 1), value + 1)
        case .home, .character("g"): value = 0
        case .end, .character("G"): value = max(0, count - 1)
        default: return false
        }
        return true
    }

    func handleConversations(_ key: Key) -> [Effect]? {
        if move(&places.conversationSelected, key, count: places.conversations.count) { return [] }
        switch key {
        case .escape: page = .vault
        case .tab, .backTab:
            let choices: [Client?] = [nil] + places.clientsShown
            let at = choices.firstIndex { $0 == places.conversationFilter } ?? 0
            places.conversationFilter = choices[(at + (key == .tab ? 1 : choices.count - 1)) % choices.count]
            places.conversationSelected = 0
        case .enter:
            let record = places.conversations.indices.contains(places.conversationSelected) ? places.conversations[places.conversationSelected] : nil
            let paths = record?.filesInPlay.map { $0.components(separatedBy: ":").first ?? $0 } ?? []
            if let path = paths.first(where: { path in files.contains { $0.path == path } }) {
                page = .vault
                open(path)
            } else {
                setStatus("This conversation read no file the vault still has.")
            }
        default: return nil
        }
        return []
    }

    func handleShelf(_ key: Key) -> [Effect]? {
        if move(&places.shelfSelected, key, count: places.shelf.count) { return [] }
        switch key {
        case .escape: page = .vault
        case .enter:
            if places.shelf.indices.contains(places.shelfSelected), let path = places.shelf[places.shelfSelected].entry.sources.keys.sorted().first(where: { path in files.contains { $0.path == path } }) {
                page = .vault
                open(path)
            }
        default: return nil
        }
        return []
    }

    func handlePrograms(_ key: Key) -> [Effect]? {
        if move(&places.programSelected, key, count: places.clientsShown.count) { return [] }
        switch key {
        case .escape: page = .vault
        case .enter:
            let client = places.clientsShown[min(places.programSelected, places.clientsShown.count - 1)]
            places.conversationFilter = client
            places.conversationSelected = 0
            page = .conversations
        default: return nil
        }
        return []
    }
}

/// How a model is named: Ollama's blobs by the name Ollama knows them by.
enum ModelLabel {
    nonisolated(unsafe) private static var known: [String: String] = [:]

    static func of(_ reported: String) -> String {
        if let name = known[reported] { return name }
        var name = (reported as NSString).lastPathComponent
        if name.hasPrefix("sha256-") {
            let digest = "sha256:" + name.dropFirst("sha256-".count)
            let library = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".ollama/models/manifests/registry.ollama.ai/library")
            outer: for model in (try? FileManager.default.contentsOfDirectory(atPath: library.path)) ?? [] {
                for tag in (try? FileManager.default.contentsOfDirectory(atPath: library.appendingPathComponent(model).path)) ?? [] {
                    if let text = try? String(contentsOf: library.appendingPathComponent(model).appendingPathComponent(tag), encoding: .utf8), text.contains(digest) {
                        name = "\(model):\(tag)"
                        break outer
                    }
                }
            }
            if name.hasPrefix("sha256-") { name = "model " + name.dropFirst(7).prefix(8) }
        } else if name.hasSuffix(".gguf") {
            name = (name as NSString).deletingPathExtension
        }
        known[reported] = name
        return name
    }
}

extension SessionRecord {
    var lookups: Int { (trail ?? []).count }
    var question: String? { turns.first?.question ?? trail?.first(where: { !$0.asked.isEmpty })?.asked }
}

extension Model {
    /// The ink a vault path is drawn in: amber for documents and pictures read in, blue for code, plain for notes.
    static func ink(for path: String) -> Ink {
        let ext = (path as NSString).pathExtension.lowercased()
        if ["md", "markdown"].contains(ext) { return .plain }
        if Extractor.handles(path) { return .doc }
        return .code
    }
}

// MARK: Drawing

enum PlacesScreen {
    static func bytes(_ count: Int) -> String { ByteCountFormatter.string(fromByteCount: Int64(count), countStyle: .file) }

    static func day(_ date: Date) -> String {
        let calendar = Calendar.current
        if calendar.isDateInToday(date) { return "Today" }
        if calendar.isDateInYesterday(date) { return "Yesterday" }
        let format = DateFormatter()
        format.dateFormat = "EEEE d MMMM"
        return format.string(from: date)
    }

    static func time(_ date: Date) -> String {
        let format = DateFormatter()
        format.dateFormat = "HH:mm"
        return format.string(from: date)
    }

    /// A bar of `width` cells, `share` of it filled. Partial blocks keep small differences visible.
    static func bar(_ share: Double, width: Int) -> String {
        let eighths = Int((max(0, min(1, share)) * Double(width * 8)).rounded())
        let partial = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉"]
        let full = String(repeating: "█", count: eighths / 8)
        let rest = eighths % 8 > 0 ? partial[eighths % 8] : ""
        return full + rest + String(repeating: " ", count: max(0, width - full.count - (rest.isEmpty ? 0 : 1)))
    }

    static func header(_ frame: inout Frame, _ title: String, _ detail: String, at y: Int, ink: Ink) {
        let x = frame.put(2, y, title, Style(ink: ink, bold: true))
        frame.put(x + 2, y, detail, .quiet)
    }

    static func split(_ model: Model, body: Rect) -> (list: Rect, detail: Rect) {
        let wide = model.width >= 96
        let listWidth = wide ? model.width * 46 / 100 : model.width - 4
        let listRows = wide ? body.height - 2 : max(3, (body.height - 2) / 2)
        let list = Rect(x: 2, y: body.y + 2, width: listWidth, height: listRows)
        let detail = wide ? Rect(x: list.right + 3, y: body.y + 2, width: model.width - list.right - 5, height: body.height - 2)
                          : Rect(x: 2, y: list.bottom + 1, width: model.width - 4, height: body.height - listRows - 3)
        return (list, detail)
    }

    static func wrapped(_ frame: inout Frame, _ text: String, _ style: Style, in area: Rect, y: inout Int, indent: Int = 0) {
        for piece in View.plainWrap(text, width: max(4, area.width - indent)) where y < area.bottom {
            frame.put(area.x + indent, y, piece, style, limit: area.right)
            y += 1
        }
    }

    // MARK: Conversations

    static func drawConversations(_ frame: inout Frame, _ model: Model, in body: Rect) {
        let state = model.places
        let records = state.conversations
        header(&frame, "Conversations", "\(records.count) kept by Burrow" + (state.conversationFilter.map { " · \($0.rawValue)" } ?? " · every program"), at: body.y, ink: .talk)
        let (list, detail) = split(model, body: body)
        guard !records.isEmpty else {
            var y = list.y
            wrapped(&frame, "No conversations yet. When Claude Code, OpenCode, LM Studio, llama.cpp or Ollama use the vault through burrow mcp, each one lands here with what it looked up.", .quiet, in: list, y: &y)
            return
        }
        // Rows: a day heading before the first conversation of each day.
        var rows: [(text: String?, record: Int?)] = []
        var lastDay: Date?
        for (index, record) in records.enumerated() {
            let start = Calendar.current.startOfDay(for: record.updated)
            if start != lastDay {
                rows.append((day(record.updated), nil))
                lastDay = start
            }
            rows.append((nil, index))
        }
        let selectedRow = rows.firstIndex { $0.record == state.conversationSelected } ?? 0
        let scroll = max(0, min(selectedRow - list.height / 2, rows.count - list.height))
        for (offset, row) in rows.dropFirst(scroll).prefix(list.height).enumerated() {
            let y = list.y + offset
            if let heading = row.text {
                frame.put(list.x, y, heading, Style(bold: true, dim: false))
                continue
            }
            let index = row.record!
            let record = records[index]
            let client = Client(record.client).rawValue
            let tail = "  \(record.lookups)↗  " + time(record.updated)
            let name = Cells.pad(client, to: 12)
            let room = max(6, list.width - 4 - 12 - Cells.width(of: tail))
            let question = Cells.truncate(record.question ?? "a lookup", to: room)
            if index == state.conversationSelected {
                frame.put(list.x, y, Cells.pad("  ● " + name + question + tail, to: list.width), Style(ink: .talk, bold: true, reverse: true), limit: list.right)
            } else {
                var x = frame.put(list.x + 2, y, "●", Style(ink: .talk))
                x = frame.put(x + 1, y, name, Style(ink: .talk))
                frame.put(x, y, question, .plain, limit: list.right)
                frame.put(list.right - Cells.width(of: tail), y, tail, .quiet, limit: list.right)
            }
        }
        guard records.indices.contains(state.conversationSelected) else { return }
        drawTrail(&frame, records[state.conversationSelected], in: detail)
    }

    /// One conversation opened up: each question, then the lookups made and the files they opened, in order.
    static func drawTrail(_ frame: inout Frame, _ record: SessionRecord, in area: Rect) {
        var y = area.y
        var x = frame.put(area.x, y, Client(record.client).rawValue, Style(ink: .talk, bold: true))
        let models = record.models.joined(separator: ", ")
        x = frame.put(x + 2, y, "\(day(record.started)) \(time(record.started))" + (models.isEmpty ? "" : " · " + models), .quiet, limit: area.right)
        y += 2
        enum Step { case lookup(TrailStep), turn(SessionTurn) }
        var steps: [(Date, Step)] = (record.trail ?? []).map { ($0.at, .lookup($0)) }
        steps += record.turns.map { ($0.at, .turn($0)) }
        steps.sort { $0.0 < $1.0 }
        for (_, step) in steps where y < area.bottom {
            switch step {
            case let .turn(turn):
                wrapped(&frame, "› " + turn.question, .strong, in: area, y: &y)
                if !turn.answer.isEmpty {
                    let short = turn.answer.replacingOccurrences(of: "\n", with: " ")
                    wrapped(&frame, String(short.prefix(220)) + (short.count > 220 ? "…" : ""), .quiet, in: area, y: &y, indent: 2)
                }
            case let .lookup(trail):
                guard y < area.bottom else { break }
                let tool = trail.tool.replacingOccurrences(of: "vault_", with: "").replacingOccurrences(of: "burrow_", with: "")
                let tx = frame.put(area.x, y, "↗ " + tool, Style(ink: .talk))
                frame.put(tx + 1, y, Cells.truncate(trail.asked, to: max(4, area.right - tx - 2)), .plain, limit: area.right)
                y += 1
                var seen: [String] = []
                for place in trail.files { let path = place.components(separatedBy: ":").first ?? place; if !seen.contains(path) { seen.append(path) } }
                for path in seen.prefix(3) where y < area.bottom {
                    frame.put(area.x + 2, y, Cells.truncateLeft(path, to: area.width - 4), Style(ink: Model.ink(for: path)), limit: area.right)
                    y += 1
                }
                if seen.count > 3, y < area.bottom {
                    frame.put(area.x + 2, y, "+\(seen.count - 3) more", .quiet)
                    y += 1
                }
            }
            y += 1
        }
    }

    // MARK: Shelf

    static func drawShelf(_ frame: inout Frame, _ model: Model, in body: Rect) {
        let state = model.places
        let total = state.shelf.reduce(0) { $0 + $1.entry.bytes }
        let stale = state.shelf.filter { $0.stale != nil }.count
        header(&frame, "Shelf", "\(state.shelf.count) saved cache\(state.shelf.count == 1 ? "" : "s") · \(bytes(total)) on disk" + (stale > 0 ? " · " : ""), at: body.y, ink: .cache)
        if stale > 0 {
            let x = 2 + Cells.width(of: "Shelf") + 2 + Cells.width(of: "\(state.shelf.count) saved cache\(state.shelf.count == 1 ? "" : "s") · \(bytes(total)) on disk · ")
            frame.put(x, body.y, "\(stale) stale", .alert)
        }
        let area = Rect(x: 2, y: body.y + 2, width: model.width - 4, height: body.height - 4)
        guard !state.shelf.isEmpty else {
            var y = area.y
            wrapped(&frame, "The shelf is empty. A model's working memory of a file is kept here after burrow kv save or burrow kv warm, so the next question loads it instead of reading the file again.", .quiet, in: area, y: &y)
            return
        }
        // Where the disk goes, by model: one bar each.
        var y = area.y
        let byModel = Dictionary(grouping: state.shelf, by: { $0.entry.model }).map { ($0.key, $0.value.reduce(0) { $0 + $1.entry.bytes }) }.sorted { $0.1 > $1.1 }
        for (name, size) in byModel.prefix(3) where y < area.bottom {
            var x = frame.put(area.x, y, bar(Double(size) / Double(max(total, 1)), width: 24), Style(ink: .cache))
            x = frame.put(x + 2, y, Cells.pad(bytes(size), to: 9), .strong)
            frame.put(x + 1, y, ModelLabel.of(name), .plain, limit: area.right)
            y += 1
        }
        y += 1
        let largest = state.shelf.map(\.entry.bytes).max() ?? 1
        let rowsLeft = max(1, area.bottom - y - 2)
        let scroll = max(0, min(state.shelfSelected - rowsLeft / 2, state.shelf.count - rowsLeft))
        for (offset, item) in state.shelf.dropFirst(scroll).prefix(rowsLeft).enumerated() {
            let row = y + offset
            let index = scroll + offset
            let entry = item.entry
            let ink: Ink = item.stale == nil ? .cache : .alert
            let label: String
            if entry.key.hasPrefix("pack-"), let part = entry.part {
                label = (entry.scope.map { $0.isEmpty ? "whole vault" : $0 } ?? "pack") + (part == 0 ? " · shared start" : " · part \(part) of \(entry.parts ?? part)")
            } else {
                label = entry.sources.keys.sorted().map { ($0 as NSString).lastPathComponent }.joined(separator: ", ")
            }
            let numbers = String(format: "%@ tok · %.1f s", entry.tokens.formatted(), entry.buildSeconds)
            let size = Cells.pad(bytes(entry.bytes), to: 9)
            let room = max(6, area.width - 16 - 10 - Cells.width(of: numbers) - 4)
            if index == state.shelfSelected {
                let line = bar(Double(entry.bytes) / Double(largest), width: 14) + "  " + size + " " + Cells.pad(Cells.truncate(label, to: room), to: room) + "  " + numbers
                frame.put(area.x, row, Cells.pad(line, to: area.width), Style(ink: ink, bold: true, reverse: true), limit: area.right)
            } else {
                var x = frame.put(area.x, row, bar(Double(entry.bytes) / Double(largest), width: 14), Style(ink: ink, dim: entry.part == 0))
                x = frame.put(x + 2, row, size, .strong)
                frame.put(x + 1, row, Cells.truncate(label, to: room), item.stale == nil ? .plain : .alert, limit: area.right)
                frame.put(area.right - Cells.width(of: numbers), row, numbers, .quiet, limit: area.right)
            }
        }
        if state.shelf.indices.contains(state.shelfSelected) {
            let item = state.shelf[state.shelfSelected]
            let line = item.stale.map { "Stale: \($0)." } ?? "\(ModelLabel.of(item.entry.model)) · built \(day(item.entry.created)) \(time(item.entry.created))\(item.entry.form == "system" ? " · read as a system message" : "")"
            frame.put(area.x, area.bottom - 1, Cells.truncate(line, to: area.width), item.stale == nil ? .quiet : .alert)
        }
        frame.put(area.x, area.bottom, Cells.truncate("The shelf keeps up to 12 GB and clears the caches used longest ago. The files always stay.", to: area.width), .quiet)
    }

    /// The vault's path short enough to read in a command: home as ~, and a very long path cut to its last folders.
    static func shortVault(_ path: String) -> String {
        let short = (path as NSString).abbreviatingWithTildeInPath
        guard short.count > 48 else { return short }
        return "…/" + short.split(separator: "/").suffix(2).joined(separator: "/")
    }

    // MARK: Library at a glance

    /// What the Library shows before a file is open: what the vault holds by kind, and what programs read most.
    static func drawLibraryGlance(_ frame: inout Frame, _ model: Model, in area: Rect) {
        var y = area.y + 1
        frame.put(area.x + 2, y, "What this vault holds", .strong)
        y += 2
        let paths = model.files.map(\.path)
        let kinds: [(String, Int, Ink)] = [
            ("notes", paths.filter { Model.ink(for: $0) == .plain }.count, .plain),
            ("documents and pictures", paths.filter { Model.ink(for: $0) == .doc }.count, .doc),
            ("code and other files", paths.filter { Model.ink(for: $0) == .code }.count, .code),
        ]
        let most = max(1, kinds.map(\.1).max() ?? 1)
        for (name, count, ink) in kinds where y < area.bottom {
            var x = frame.put(area.x + 2, y, bar(Double(count) / Double(most), width: 18), Style(ink: ink))
            x = frame.put(x + 2, y, Cells.pad(count.description, to: 5), .strong)
            frame.put(x + 1, y, name, .quiet, limit: area.right)
            y += 1
        }
        // The files programs opened most, so the vault's working set is one keypress away.
        var reads: [String: Int] = [:]
        for record in model.places.sessions {
            for place in Set(record.filesInPlay.map { $0.components(separatedBy: ":").first ?? $0 }) where model.files.contains(where: { $0.path == place }) {
                reads[place, default: 0] += 1
            }
        }
        let top = reads.sorted { $0.value == $1.value ? $0.key < $1.key : $0.value > $1.value }.prefix(8)
        if !top.isEmpty, y + 3 < area.bottom {
            y += 1
            frame.put(area.x + 2, y, "Read most by programs", .strong)
            y += 2
            for (path, count) in top where y < area.bottom {
                let x = frame.put(area.x + 2, y, Cells.pad("\(count)×", to: 4), Style(ink: .talk))
                frame.put(x + 1, y, Cells.truncateLeft(path, to: area.width - 8), Style(ink: Model.ink(for: path)), limit: area.right)
                y += 1
            }
        }
        if y + 2 < area.bottom {
            frame.put(area.x + 2, y + 1, Cells.truncate("Pick a file on the left, or press o to open one by name.", to: area.width - 4), .quiet)
        }
    }

    // MARK: Programs

    static func drawPrograms(_ frame: inout Frame, _ model: Model, in body: Rect) {
        let state = model.places
        let clients = state.clientsShown
        let active = clients.filter(state.active).count
        header(&frame, "Programs", "\(active) active in the last 30 minutes · all reach the vault through burrow mcp", at: body.y, ink: .talk)
        let area = Rect(x: 2, y: body.y + 2, width: model.width - 4, height: body.height - 2)
        let busiest = max(1, clients.map { state.today($0).count }.max() ?? 1)
        var y = area.y
        for (index, client) in clients.enumerated() where y < area.bottom {
            let lookups = state.today(client).count
            let records = state.sessions.filter { Client($0.client) == client }
            let lit = state.active(client)
            let used = !records.isEmpty
            let dot = lit ? "●" : used ? "◉" : "○"
            let name = Cells.pad(client.rawValue, to: 13)
            let line = bar(Double(lookups) / Double(busiest), width: 20)
            let detail = used ? "\(lookups) lookup\(lookups == 1 ? "" : "s") today · \(records.count) conversation\(records.count == 1 ? "" : "s")" : "not used yet"
            let selected = index == state.programSelected
            if selected {
                frame.put(area.x, y, Cells.pad("\(dot) \(name) \(line)  \(detail)", to: area.width), Style(ink: .talk, bold: true, reverse: true), limit: area.right)
            } else {
                var x = frame.put(area.x, y, dot, used ? Style(ink: .talk, bold: lit) : .quiet)
                x = frame.put(x + 1, y, name, used ? .strong : .quiet)
                x = frame.put(x + 1, y, line, Style(ink: .talk, dim: !lit))
                frame.put(x + 2, y, detail, .quiet, limit: area.right)
            }
            y += 1
            if selected {
                let setup = client.setup.replacingOccurrences(of: "<vault>", with: shortVault(model.vault.root.path))
                for piece in View.plainWrap("connect: " + setup, width: area.width - 4) where y < area.bottom {
                    frame.put(area.x + 4, y, piece, Style(ink: .code), limit: area.right)
                    y += 1
                }
            }
            y += 1
        }
        if y + 2 < area.bottom {
            frame.put(area.x, area.bottom - 1, "● active now   ◉ used before   ○ not used yet   ⏎ shows its conversations", .quiet)
        }
    }
}
