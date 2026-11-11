import AppKit
import BurrowCore
import BurrowTools
import Charts
import SwiftUI

// MARK: Conversations

/// What other programs did with the vault, day by day. Burrow keeps these itself; it never chats.
struct ConversationsPage: View {
    let workspace: Workspace
    let program: Program?

    private var days: [(day: Date, records: [VaultSession])] {
        let calendar = Calendar.current
        let grouped = Dictionary(grouping: workspace.sessions(for: program)) { calendar.startOfDay(for: $0.updated) }
        return grouped.keys.sorted(by: >).map { ($0, grouped[$0]!.sorted { $0.updated > $1.updated }) }
    }

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 28) {
                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    Text(program?.name ?? "Conversations").font(.system(size: 28, weight: .bold)).tracking(-0.4)
                    Text("\(workspace.sessions(for: program).count) kept by Burrow").foregroundStyle(Night.dim).monospacedDigit()
                }
                if days.isEmpty {
                    ContentUnavailableView("No conversations yet", systemImage: "point.3.connected.trianglepath.dotted",
                                           description: Text("When Claude Code, OpenCode, LM Studio, llama.cpp or Ollama use the vault through burrow mcp, each conversation lands here with what it looked up."))
                        .foregroundStyle(Night.dim).frame(maxWidth: .infinity).padding(.top, 60)
                }
                ForEach(days, id: \.day) { day in
                    VStack(alignment: .leading, spacing: 12) {
                        Text(day.day.dayTitle).font(.system(size: 15, weight: .semibold))
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 300, maximum: 420), spacing: 16, alignment: .top)], alignment: .leading, spacing: 16) {
                            ForEach(day.records, id: \.id) { record in
                                SessionCard(workspace: workspace, record: record).onTapGesture { workspace.go(.session(record.id)) }
                            }
                        }
                    }
                }
            }
            .padding(.horizontal, 28).padding(.vertical, 22)
        }
        .background(Night.ground)
        .environment(\.colorScheme, .dark)
    }
}

/// One conversation: the program, what it asked first, and covers of the files it read.
struct SessionCard: View {
    let workspace: Workspace
    let record: VaultSession
    @State private var hovering = false

    private var files: [String] {
        var seen: [String] = []
        for place in record.filesInPlay {
            let path = place.components(separatedBy: ":").first ?? place
            if !seen.contains(path), workspace.map.files.contains(where: { $0.path == path }) { seen.append(path) }
        }
        return seen
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: record.program.symbol).foregroundStyle(Night.conversation).frame(width: 20)
                Text(record.program.name).font(.system(size: 13, weight: .semibold))
                if let model = record.turns.last?.model, model != "unnamed", !model.isEmpty { Text(model).font(.system(size: 11.5)).foregroundStyle(Night.faint).lineLimit(1) }
                Spacer()
                Text(record.updated.formatted(date: .omitted, time: .shortened)).font(.system(size: 11.5)).foregroundStyle(Night.faint).monospacedDigit()
            }
            if let question = record.question {
                Text(question).font(.system(size: 13)).foregroundStyle(Night.note.opacity(0.9)).lineLimit(2)
            }
            if !files.isEmpty {
                HStack(spacing: 6) {
                    ForEach(files.prefix(4), id: \.self) { path in
                        CoverImage(workspace: workspace, path: path, size: CGSize(width: 200, height: 150))
                            .aspectRatio(4 / 3, contentMode: .fit).clipShape(.rect(cornerRadius: 5))
                            .overlay { RoundedRectangle(cornerRadius: 5).strokeBorder((LibraryKind.colour(of: path) ?? Night.line).opacity(0.5)) }
                            .help(path)
                    }
                    if files.count > 4 {
                        Text("+\(files.count - 4)").font(.system(size: 12, weight: .medium)).foregroundStyle(Night.dim).frame(width: 34)
                    }
                }
            }
            HStack(spacing: 14) {
                stat("magnifyingglass", record.lookups.counted("lookup"))
                stat("doc.on.doc", files.count.counted("file"))
                if !record.turns.isEmpty { stat("text.bubble", record.turns.count.counted("turn")) }
                if record.resumedFrom != nil { stat("arrow.turn.down.right", "carried on") }
            }
        }
        .padding(14)
        .background(hovering ? Night.cardHover : Night.card, in: .rect(cornerRadius: 12))
        .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder(Night.conversation.opacity(hovering ? 0.55 : 0.18)) }
        .contentShape(Rectangle())
        .onHover { hovering = $0 }
    }

    private func stat(_ symbol: String, _ text: String) -> some View {
        Label(text, systemImage: symbol).font(.system(size: 11.5)).foregroundStyle(Night.dim).monospacedDigit()
    }
}

/// One conversation opened up: each question, the lookups made for it, the files they opened, then the answer.
struct SessionPage: View {
    let workspace: Workspace
    let id: String

    private var record: VaultSession? { workspace.sessions.first { $0.id == id } }

    /// Questions and lookups in the order they happened. Lookups before the first logged question stand on their own.
    private var steps: [Step] {
        guard let record else { return [] }
        var out: [Step] = (record.trail ?? []).map { .lookup($0) }
        out += record.turns.map { .turn($0) }
        return out.sorted { $0.at < $1.at }
    }

    enum Step {
        case lookup(TrailStep)
        case turn(SessionTurn)
        var at: Date {
            switch self {
            case let .lookup(step): return step.at
            case let .turn(turn): return turn.at
            }
        }
    }

    var body: some View {
        ScrollView {
            if let record {
                VStack(alignment: .leading, spacing: 18) {
                    HStack(spacing: 10) {
                        Image(systemName: record.program.symbol).font(.system(size: 20)).foregroundStyle(Night.conversation)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(record.program.name).font(.system(size: 24, weight: .bold)).tracking(-0.3)
                            Text("\(record.started.formatted(date: .abbreviated, time: .shortened)) · \(record.lookups.counted("lookup")) · \(Set(record.filesInPlay.map { $0.components(separatedBy: ":").first ?? $0 }).count.counted("file")) read\(record.models.isEmpty ? "" : " · " + record.models.joined(separator: ", "))")
                                .foregroundStyle(Night.dim).font(.system(size: 12.5)).monospacedDigit()
                        }
                    }
                    SessionActions(workspace: workspace, record: record)
                    if let from = record.resumedFrom {
                        Button { workspace.go(.session(from)) } label: { Label("Carried on from an earlier conversation", systemImage: "arrow.turn.left.up") }
                            .buttonStyle(.link)
                    }
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                            TrailRow(workspace: workspace, step: step, last: index == steps.count - 1)
                        }
                    }
                }
                .padding(.horizontal, 28).padding(.vertical, 22).frame(maxWidth: 860, alignment: .leading)
            } else {
                ContentUnavailableView("This conversation is gone", systemImage: "questionmark.folder").padding(.top, 80)
            }
        }
        .frame(maxWidth: .infinity)
        .background(Night.ground)
        .environment(\.colorScheme, .dark)
    }
}

/// Hand this conversation to another model, or keep something from it in the Ledger.
struct SessionActions: View {
    let workspace: Workspace
    let record: VaultSession
    @State private var keeping = false
    @State private var words = ""
    @State private var kind = LedgerCommit.Kind.decision
    @State private var copied = false

    private var files: [String] {
        record.filesInPlay.map { $0.components(separatedBy: ":").first ?? $0 }.reduce(into: [String]()) { if !$0.contains($1) { $0.append($1) } }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                Button { NSPasteboard.general.clearContents(); NSPasteboard.general.setString(Handoff.text(record), forType: .string); copied = true } label: {
                    Label(copied ? "Copied" : "Copy Handoff", systemImage: "arrow.right.circle")
                }
                .help("The short handoff any model can carry this conversation on from")
                Button { keeping.toggle() } label: { Label("Keep in Ledger", systemImage: "books.vertical") }
                    .help("Keep a decision, fact or plan from this conversation, resting on the files it read")
            }
            .controlSize(.small)
            if keeping {
                HStack(spacing: 8) {
                    Picker("", selection: $kind) {
                        ForEach([LedgerCommit.Kind.decision, .fact, .plan], id: \.self) { Text($0.title).tag($0) }
                    }
                    .labelsHidden().frame(width: 110)
                    TextField("What to keep, in a sentence", text: $words).textFieldStyle(.roundedBorder)
                    Button("Keep") {
                        let message = words, chosen = kind
                        Task { await workspace.keep(chosen, message, files: Array(files.prefix(12)), session: record.id) }
                        words = ""
                        keeping = false
                    }
                    .disabled(words.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                .controlSize(.small)
            }
        }
    }
}

/// One step on the trail, drawn as a node on a line, like a trace.
struct TrailRow: View {
    let workspace: Workspace
    let step: SessionPage.Step
    let last: Bool
    @State private var showAnswer = false

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            VStack(spacing: 0) {
                Circle().fill(dot).frame(width: isTurn ? 12 : 8, height: isTurn ? 12 : 8).shadow(color: dot, radius: isTurn ? 6 : 3)
                    .padding(.top, isTurn ? 4 : 6)
                if !last { Rectangle().fill(Night.line).frame(width: 1.5).frame(maxHeight: .infinity) }
            }
            .frame(width: 14)
            content.padding(.bottom, 18)
            Spacer(minLength: 0)
        }
    }

    private var isTurn: Bool { if case .turn = step { return true } else { return false } }
    private var dot: Color { isTurn ? Night.note : Night.conversation }

    @ViewBuilder private var content: some View {
        switch step {
        case let .lookup(trail):
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 8) {
                    Text(toolName(trail.tool)).font(.system(size: 12, weight: .semibold, design: .monospaced)).foregroundStyle(Night.conversation)
                    Text(trail.at.formatted(date: .omitted, time: .standard)).font(.system(size: 11)).foregroundStyle(Night.faint).monospacedDigit()
                }
                if !trail.asked.isEmpty { Text(trail.asked).font(.system(size: 13)).foregroundStyle(Night.note.opacity(0.85)).lineLimit(3) }
                files(trail.files)
            }
        case let .turn(turn):
            VStack(alignment: .leading, spacing: 8) {
                Text(turn.question).font(.system(size: 15, weight: .semibold)).foregroundStyle(Night.note)
                HStack(spacing: 10) {
                    Text("\(turn.model)").foregroundStyle(Night.dim)
                    if turn.seconds > 0 { Text(String(format: "%.1f s", turn.seconds)).foregroundStyle(Night.faint) }
                    if turn.promptTokens > 0 { Text("\(turn.promptTokens.formatted()) prompt tokens").foregroundStyle(Night.faint) }
                }
                .font(.system(size: 11.5)).monospacedDigit()
                files(turn.sources)
                if !turn.answer.isEmpty {
                    DisclosureGroup(isExpanded: $showAnswer) {
                        Text(turn.answer).font(.system(size: 13)).foregroundStyle(Night.note.opacity(0.85)).textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading).padding(.top, 6)
                    } label: {
                        Text("Answer").font(.system(size: 12, weight: .medium)).foregroundStyle(Night.dim)
                    }
                }
            }
        }
    }

    private func toolName(_ tool: String) -> String {
        tool.replacingOccurrences(of: "vault_", with: "").replacingOccurrences(of: "_", with: " ")
    }

    @ViewBuilder private func files(_ places: [String]) -> some View {
        let paths = places.map { $0.components(separatedBy: ":").first ?? $0 }.reduce(into: [String]()) { if !$0.contains($1) { $0.append($1) } }
        if !paths.isEmpty {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(paths.prefix(10), id: \.self) { path in
                        Button { workspace.go(.file(path), newTab: true) } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                if workspace.map.files.contains(where: { $0.path == path }) {
                                    CoverImage(workspace: workspace, path: path, size: CGSize(width: 220, height: 165))
                                        .frame(width: 104, height: 78).clipShape(.rect(cornerRadius: 5))
                                        .overlay { RoundedRectangle(cornerRadius: 5).strokeBorder((LibraryKind.colour(of: path) ?? Night.line).opacity(0.5)) }
                                }
                                Text(path.fileName).font(.system(size: 10.5)).foregroundStyle(Night.dim).lineLimit(1).frame(width: 104, alignment: .leading)
                            }
                        }
                        .buttonStyle(.plain).help(path)
                    }
                }
            }
        }
    }
}

// MARK: Shelf

/// Saved model memory: what each cache holds, how big it is, and whether it still matches its files.
struct ShelfPage: View {
    let workspace: Workspace

    private var total: Int { workspace.shelf.reduce(0) { $0 + $1.entry.bytes } }
    private var byModel: [(model: String, bytes: Int)] {
        Dictionary(grouping: workspace.shelf, by: \.entry.model).map { ($0.key, $0.value.reduce(0) { $0 + $1.entry.bytes }) }.sorted { $0.bytes > $1.bytes }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    Text("Shelf").font(.system(size: 28, weight: .bold)).tracking(-0.4)
                    Text("\(workspace.shelf.count.counted("saved cache")) · \(total.bytesText)").foregroundStyle(Night.dim).monospacedDigit()
                }
                if workspace.shelf.isEmpty {
                    ContentUnavailableView("The shelf is empty", systemImage: "memorychip",
                                           description: Text("A model's working memory of a file is kept here after `burrow kv save`, so the next question loads it instead of reading the file again."))
                        .foregroundStyle(Night.dim).frame(maxWidth: .infinity).padding(.top, 60)
                } else {
                    HStack(alignment: .center, spacing: 34) {
                        ring.frame(width: 230, height: 230)
                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(byModel, id: \.model) { item in
                                HStack(spacing: 10) {
                                    Circle().fill(Night.cache.opacity(shade(item.model))).frame(width: 10, height: 10)
                                    Text(ModelName.display(item.model)).font(.system(size: 13, weight: .medium)).lineLimit(1)
                                    Text(item.bytes.bytesText).foregroundStyle(Night.dim).monospacedDigit()
                                }
                            }
                            let stale = workspace.shelf.filter { $0.stale != nil }.count
                            if stale > 0 {
                                Label("\(stale) stale: their files changed after they were built", systemImage: "exclamationmark.circle.fill")
                                    .foregroundStyle(Night.stale).font(.system(size: 12.5))
                            }
                        }
                    }
                    buildStrip
                    ForEach(packs, id: \.title) { pack in
                        PackCard(workspace: workspace, title: pack.title, items: pack.items, largest: largest)
                    }
                    VStack(spacing: 10) {
                        ForEach(workspace.shelf.filter { !$0.isPack }.sorted { $0.touched > $1.touched }) { item in
                            ShelfRow(workspace: workspace, item: item, largest: largest)
                        }
                    }
                    Text("The shelf keeps up to 12 GB and clears the caches used longest ago, so a cache can leave between visits. The files themselves always stay.")
                        .font(.system(size: 11.5)).foregroundStyle(Night.faint)
                }
            }
            .padding(.horizontal, 28).padding(.vertical, 22)
        }
        .background(Night.ground)
        .environment(\.colorScheme, .dark)
    }

    private var largest: Int { workspace.shelf.map(\.entry.bytes).max() ?? 1 }

    /// Packs grouped by folder and model, most recently used first; parts in order with the shared start first.
    private var packs: [(title: String, items: [ShelfItem])] {
        let grouped = Dictionary(grouping: workspace.shelf.filter(\.isPack)) { "\($0.entry.scope ?? "")|\($0.entry.model)" }
        return grouped.values.map { items in
            let sorted = items.sorted { ($0.entry.part ?? 0) < ($1.entry.part ?? 0) }
            let scope = sorted.first?.entry.scope ?? ""
            return (scope.isEmpty ? "Whole vault" : scope, sorted)
        }
        .sorted { ($0.items.map(\.touched).max() ?? .distantPast) > ($1.items.map(\.touched).max() ?? .distantPast) }
    }

    private func shade(_ model: String) -> Double {
        let index = byModel.firstIndex { $0.model == model } ?? 0
        return max(0.35, 1 - Double(index) * 0.2)
    }

    /// Where the disk goes: an inner ring by model, an outer ring by cache. Stale caches are red.
    private var ring: some View {
        ZStack {
            Chart(byModel, id: \.model) { item in
                SectorMark(angle: .value("Bytes", item.bytes), innerRadius: .ratio(0.42), outerRadius: .ratio(0.66), angularInset: 1.5)
                    .foregroundStyle(Night.cache.opacity(shade(item.model)))
            }
            Chart(workspace.shelf.sorted { $0.entry.model < $1.entry.model }) { item in
                SectorMark(angle: .value("Bytes", item.entry.bytes), innerRadius: .ratio(0.7), outerRadius: .ratio(1), angularInset: 1.5)
                    .foregroundStyle(item.stale == nil ? Night.cache.opacity(shade(item.entry.model) * 0.8) : Night.stale)
            }
            VStack(spacing: 1) {
                Text(total.bytesText).font(.system(size: 17, weight: .semibold)).monospacedDigit()
                Text("on disk").font(.system(size: 11)).foregroundStyle(Night.faint)
            }
        }
        .shadow(color: Night.cache.opacity(0.35), radius: 18)
    }

    /// How long each cache took to build from its files: the reading the next question skips by loading it instead.
    private var buildStrip: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Reading each cache saves the next question").font(.system(size: 12, weight: .semibold)).foregroundStyle(Night.dim)
            Chart(workspace.shelf.filter { !$0.isSpine }.sorted { $0.entry.buildSeconds > $1.entry.buildSeconds }.prefix(12).map { $0 }) { item in
                BarMark(x: .value("Seconds", item.entry.buildSeconds), y: .value("Cache", item.label))
                    .foregroundStyle(item.stale == nil ? Night.cache : Night.stale)
                    .annotation(position: .trailing) {
                        Text(String(format: "%.1f s · %@ tokens", item.entry.buildSeconds, item.entry.tokens.formatted()))
                            .font(.system(size: 11)).foregroundStyle(Night.dim).monospacedDigit()
                    }
            }
            .chartXAxis { AxisMarks(values: .automatic(desiredCount: 4)) { value in
                AxisGridLine().foregroundStyle(Night.line)
                AxisValueLabel { if let v = value.as(Double.self) { Text(String(format: "%.0f s", v)) } }
            } }
            .chartYAxis { AxisMarks { _ in AxisValueLabel().foregroundStyle(Night.dim) } }
            .frame(height: CGFloat(min(max(workspace.shelf.filter { !$0.isSpine }.count, 1), 12)) * 26 + 24)
        }
        .padding(14).background(Night.card, in: .rect(cornerRadius: 12))
    }
}

/// A folder read as a pack: a shared start (dimmed, since every part loads it) and parts stacked on it, shown as one bar.
struct PackCard: View {
    let workspace: Workspace
    let title: String
    let items: [ShelfItem]
    let largest: Int

    private var total: Int { items.reduce(0) { $0 + $1.entry.bytes } }
    private var stale: Int { items.filter { $0.stale != nil }.count }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                Image(systemName: "square.stack.3d.up.fill").foregroundStyle(Night.cache)
                Text(title).font(.system(size: 14, weight: .semibold))
                Text(ModelName.display(items.first?.entry.model ?? "")).font(.system(size: 12)).foregroundStyle(Night.dim).lineLimit(1)
                if stale > 0 { Label("\(stale) stale", systemImage: "exclamationmark.circle.fill").foregroundStyle(Night.stale).font(.system(size: 11.5, weight: .medium)) }
                Spacer()
                Text("\(items.filter { !$0.isSpine }.count.counted("part")) · \(total.bytesText)").font(.system(size: 12.5, weight: .medium)).monospacedDigit()
            }
            GeometryReader { box in
                HStack(spacing: 2) {
                    ForEach(items) { item in
                        RoundedRectangle(cornerRadius: 2)
                            .fill(item.stale != nil ? Night.stale : Night.cache.opacity(item.isSpine ? 0.35 : 0.9))
                            .frame(width: max(3, (box.size.width - CGFloat(items.count) * 2) * CGFloat(item.entry.bytes) / CGFloat(max(total, 1))))
                            .help("\(item.label) · \(item.entry.tokens.formatted()) tokens · \(item.entry.bytes.bytesText)\(item.stale.map { " · " + $0 } ?? "")")
                    }
                }
            }
            .frame(height: 10)
            .shadow(color: Night.cache.opacity(0.45), radius: 6)
            HStack(spacing: 6) {
                ForEach(items.filter { !$0.isSpine }.flatMap(\.files).reduce(into: [String]()) { if !$0.contains($1) { $0.append($1) } }.prefix(8), id: \.self) { path in
                    CoverImage(workspace: workspace, path: path, size: CGSize(width: 160, height: 120), compact: true)
                        .frame(width: 52, height: 39).clipShape(.rect(cornerRadius: 4)).help(path)
                }
                Spacer()
                if let used = items.map(\.touched).max() {
                    Text("used \(used.formatted(.relative(presentation: .named)))").font(.system(size: 11.5)).foregroundStyle(Night.faint)
                }
            }
        }
        .padding(12)
        .background(Night.card, in: .rect(cornerRadius: 12))
        .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder((stale > 0 ? Night.stale : Night.cache).opacity(0.22)) }
    }
}

struct ShelfRow: View {
    let workspace: Workspace
    let item: ShelfItem
    let largest: Int

    var body: some View {
        let entry = item.entry
        HStack(alignment: .center, spacing: 16) {
            HStack(spacing: -18) {
                ForEach(item.files.prefix(3), id: \.self) { path in
                    CoverImage(workspace: workspace, path: path, size: CGSize(width: 160, height: 120), compact: true)
                        .frame(width: 58, height: 44).clipShape(.rect(cornerRadius: 4))
                        .overlay { RoundedRectangle(cornerRadius: 4).strokeBorder(Color.black, lineWidth: 1.5) }
                }
            }
            .frame(width: 96, alignment: .leading)
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    Text(ModelName.display(entry.model)).font(.system(size: 13.5, weight: .semibold)).lineLimit(1)
                    if let stale = item.stale {
                        Label("Stale", systemImage: "exclamationmark.circle.fill").foregroundStyle(Night.stale).font(.system(size: 11.5, weight: .medium)).help(stale)
                    }
                }
                Text(item.files.map(\.fileName).joined(separator: ", ")).font(.system(size: 12)).foregroundStyle(Night.dim).lineLimit(1).truncationMode(.middle)
                GeometryReader { box in
                    ZStack(alignment: .leading) {
                        Capsule().fill(Color.white.opacity(0.06))
                        Capsule().fill(item.stale == nil ? Night.cache : Night.stale)
                            .frame(width: max(4, box.size.width * CGFloat(entry.bytes) / CGFloat(max(largest, 1))))
                            .shadow(color: (item.stale == nil ? Night.cache : Night.stale).opacity(0.6), radius: 5)
                    }
                }
                .frame(height: 5)
            }
            VStack(alignment: .trailing, spacing: 2) {
                Text(entry.bytes.bytesText).font(.system(size: 13, weight: .medium))
                Text("\(entry.tokens.formatted()) tokens · built in \(String(format: "%.1f", entry.buildSeconds)) s").font(.system(size: 11.5)).foregroundStyle(Night.faint)
            }
            .monospacedDigit()
        }
        .padding(12)
        .background(Night.card, in: .rect(cornerRadius: 12))
        .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder((item.stale == nil ? Night.cache : Night.stale).opacity(0.22)) }
    }
}

// MARK: Programs

/// The programs that use the vault, each drawn as a line into it. Brighter lines did more lookups today.
struct ProgramsPage: View {
    let workspace: Workspace

    private func today(_ program: Program) -> [TrailStep] {
        workspace.sessions(for: program).flatMap { $0.trail ?? [] }.filter { Calendar.current.isDateInToday($0.at) }
    }
    private func active(_ program: Program) -> Bool {
        workspace.sessions(for: program).contains { Date().timeIntervalSince($0.updated) < 30 * 60 }
    }
    private var programs: [Program] {
        Program.known + (workspace.sessions(for: .other).isEmpty ? [] : [.other])
    }
    private var busiest: Int { max(1, programs.map { today($0).count }.max() ?? 1) }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    Text("Programs").font(.system(size: 28, weight: .bold)).tracking(-0.4)
                    Text("\(programs.filter(active).count) active in the last 30 minutes").foregroundStyle(Night.dim).monospacedDigit()
                }
                lines.frame(height: CGFloat(programs.count) * 64 + 20)
                traffic
                VStack(spacing: 10) {
                    ForEach(programs) { program in ProgramRow(workspace: workspace, program: program, lookups: today(program).count, active: active(program)) }
                }
            }
            .padding(.horizontal, 28).padding(.vertical, 22)
        }
        .background(Night.ground)
        .environment(\.colorScheme, .dark)
    }

    /// Each program on the left, a line to the vault on the right; brightness is today's lookups.
    private var lines: some View {
        GeometryReader { box in
            let vault = CGPoint(x: box.size.width - 70, y: box.size.height / 2)
            ZStack {
                Canvas { context, _ in
                    for (index, program) in programs.enumerated() {
                        let from = CGPoint(x: 190, y: 40 + CGFloat(index) * 64)
                        var path = Path()
                        path.move(to: from)
                        path.addCurve(to: vault, control1: CGPoint(x: from.x + (vault.x - from.x) * 0.5, y: from.y),
                                      control2: CGPoint(x: from.x + (vault.x - from.x) * 0.5, y: vault.y))
                        let strength = Double(today(program).count) / Double(busiest)
                        let lit = today(program).isEmpty ? 0.08 : 0.3 + 0.7 * strength
                        context.stroke(path, with: .color(Night.conversation.opacity(lit)), lineWidth: today(program).isEmpty ? 1 : 1.5 + 2.5 * strength)
                        if active(program) {
                            context.addFilter(.shadow(color: Night.conversation, radius: 6))
                            context.stroke(path, with: .color(Night.conversation.opacity(0.5)), lineWidth: 1)
                        }
                    }
                }
                ForEach(Array(programs.enumerated()), id: \.element) { index, program in
                    HStack(spacing: 10) {
                        Image(systemName: program.symbol).frame(width: 22)
                        Text(program.name).font(.system(size: 13.5, weight: .medium))
                    }
                    .foregroundStyle(today(program).isEmpty && !active(program) ? Night.faint : Night.note)
                    .frame(width: 180, alignment: .leading)
                    .position(x: 90, y: 40 + CGFloat(index) * 64)
                }
                VStack(spacing: 6) {
                    Circle().fill(Night.note).frame(width: 18, height: 18).shadow(color: Night.conversation, radius: 14)
                    Text(workspace.name).font(.system(size: 12, weight: .semibold)).lineLimit(1)
                }
                .position(vault)
            }
        }
        .padding(.vertical, 6)
        .background(Night.card.opacity(0.5), in: .rect(cornerRadius: 14))
    }

    private struct Hour: Identifiable { let id = UUID(); let hour: Date; let program: String; let count: Int }

    /// Lookups per hour today, stacked by program.
    private var traffic: some View {
        let calendar = Calendar.current
        let hours: [Hour] = programs.flatMap { program -> [Hour] in
            Dictionary(grouping: today(program)) { calendar.dateInterval(of: .hour, for: $0.at)!.start }
                .map { Hour(hour: $0.key, program: program.name, count: $0.value.count) }
        }
        return VStack(alignment: .leading, spacing: 8) {
            Text("Lookups today").font(.system(size: 12, weight: .semibold)).foregroundStyle(Night.dim)
            if hours.isEmpty {
                Text("No lookups yet today.").font(.system(size: 12)).foregroundStyle(Night.faint).frame(height: 60)
            } else {
                Chart(hours) { item in
                    BarMark(x: .value("Hour", item.hour, unit: .hour), y: .value("Lookups", item.count))
                        .foregroundStyle(Night.conversation.opacity(0.85))
                }
                .chartXScale(domain: calendar.startOfDay(for: Date())...calendar.date(byAdding: .day, value: 1, to: calendar.startOfDay(for: Date()))!)
                .chartYAxis { AxisMarks(position: .leading, values: .automatic(desiredCount: 3)) }
                .frame(height: 70)
            }
        }
        .padding(14).background(Night.card, in: .rect(cornerRadius: 12))
    }
}

struct ProgramRow: View {
    let workspace: Workspace
    let program: Program
    let lookups: Int
    let active: Bool
    @State private var showSetup = false

    var body: some View {
        let records = workspace.sessions(for: program)
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 12) {
                Image(systemName: program.symbol).font(.system(size: 16)).frame(width: 24).foregroundStyle(records.isEmpty ? Night.faint : Night.conversation)
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 8) {
                        Text(program.name).font(.system(size: 14, weight: .semibold))
                        if active { Text("Active").font(.system(size: 11, weight: .semibold)).foregroundStyle(.black).padding(.horizontal, 6).padding(.vertical, 1).background(Night.conversation, in: .capsule) }
                    }
                    Text(records.isEmpty ? "Not used yet" : "\(records.count.counted("conversation")) · \(lookups.counted("lookup")) today · last \(records.first!.updated.formatted(.relative(presentation: .named)))")
                        .font(.system(size: 12)).foregroundStyle(Night.dim).monospacedDigit()
                }
                Spacer()
                if !records.isEmpty { Button("Conversations") { workspace.go(.conversations(program)) }.controlSize(.small) }
                Button(showSetup ? "Hide Setup" : "Connect") { showSetup.toggle() }.controlSize(.small)
            }
            if showSetup {
                HStack {
                    Text(program.setup(vault: workspace.folder.path))
                        .font(.system(size: 11.5, design: .monospaced)).textSelection(.enabled).foregroundStyle(Night.note.opacity(0.85))
                    Spacer()
                    Button { NSPasteboard.general.clearContents(); NSPasteboard.general.setString(program.setup(vault: workspace.folder.path), forType: .string) } label: {
                        Label("Copy", systemImage: "doc.on.doc")
                    }
                    .controlSize(.small)
                }
                .padding(10).background(Color.white.opacity(0.05), in: .rect(cornerRadius: 8))
            }
        }
        .padding(12)
        .background(Night.card, in: .rect(cornerRadius: 12))
    }
}
