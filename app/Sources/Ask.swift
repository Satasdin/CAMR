import BurrowCore
import BurrowTrial
import SwiftUI

struct AskPage: View {
    @Bindable var workspace: Workspace
    @State private var question = ""
    @State private var wantsChange = false

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { reader in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 34) {
                        if workspace.turns.isEmpty {
                            VStack(spacing: 8) {
                                Text("Ask your vault").font(.system(size: 28, weight: .semibold)).tracking(-0.4)
                                Text("The model on this Mac reads only what Burrow finds, and shows you what it used.")
                                    .foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity).padding(.top, 140)
                        }
                        ForEach(workspace.turns) { turn in
                            AnswerView(workspace: workspace, turn: turn, showQuestion: true).id(turn.id)
                        }
                    }
                    .frame(maxWidth: 760).padding(28).frame(maxWidth: .infinity)
                }
                .onChange(of: workspace.turns.count) { _, _ in
                    if let last = workspace.turns.last { withAnimation { reader.scrollTo(last.id, anchor: .top) } }
                }
            }
            HStack(spacing: 10) {
                Picker("Look in", selection: $workspace.askScope) {
                    Label("Everything", systemImage: "tray.full").tag(String?.none)
                    Divider()
                    ForEach(workspace.scopes, id: \.self) { Label($0, systemImage: "folder").tag(String?.some($0)) }
                }
                .labelsHidden().fixedSize().help("Limit the question to one folder")
                if workspace.models.count > 1 {
                    Picker("Model", selection: $workspace.model) {
                        ForEach(workspace.models, id: \.self) { Text($0).tag($0) }
                    }
                    .labelsHidden().frame(maxWidth: 220).help("The model on this Mac that answers")
                }
                Spacer()
            }
            .frame(maxWidth: 760).padding(.horizontal, 16).padding(.top, 8)
            AskField(workspace: workspace, text: $question, prompt: "Ask your vault", wantsChange: $wantsChange, staysHere: true)
                .frame(maxWidth: 760).padding(.horizontal, 16).padding(.vertical, 10)
        }
        .background(Theme.page)
    }
}

/// What the model is reading, as it reads: one mark per file, in the colour of its folder.
struct ReadingStrip: View {
    let workspace: Workspace

    var body: some View {
        HStack(spacing: 10) {
            HStack(spacing: 3) {
                ForEach(Array(workspace.lit.enumerated()), id: \.offset) { place, path in
                    RoundedRectangle(cornerRadius: 1.5)
                        .fill(place < workspace.litCount ? colour(path) : Color.white.opacity(0.14))
                        .frame(width: 5, height: 16)
                }
            }
            Text(workspace.readingNow.map { "Reading \($0.title)" } ?? "Read \(workspace.lit.count) notes and files")
                .font(.callout).lineLimit(1)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14).padding(.vertical, 8)
        .glassEffect(in: .capsule)
    }

    private func colour(_ path: String) -> Color {
        workspace.sim.index[path].map { workspace.sim.colour(workspace.sim.nodes[$0].group) } ?? Theme.gold
    }
}

struct AskField: View {
    let workspace: Workspace
    @Binding var text: String
    let prompt: String
    var wantsChange: Binding<Bool>?
    var staysHere = false

    var body: some View {
        HStack(spacing: 8) {
            TextField(wantsChange?.wrappedValue == true ? "Describe the change you want" : prompt, text: $text, axis: .vertical)
                .textFieldStyle(.plain).font(.body).lineLimit(1...5)
                .onSubmit(send)
            if let wantsChange {
                Button { wantsChange.wrappedValue.toggle() } label: {
                    Image(systemName: wantsChange.wrappedValue ? "pencil.circle.fill" : "pencil.circle").font(.title2)
                }
                .buttonStyle(.plain).foregroundStyle(wantsChange.wrappedValue ? Color.accentColor : Color.secondary)
                .help("Propose a change you can accept or reject")
                .accessibilityLabel(wantsChange.wrappedValue ? "Asking for a change. Switch to asking a question" : "Switch to proposing a change")
            }
            Button(action: send) { Image(systemName: "arrow.up.circle.fill").font(.title2) }
                .buttonStyle(.plain).foregroundStyle(canSend ? Color.accentColor : Color.secondary)
                .disabled(!canSend)
                .accessibilityLabel("Ask")
        }
        .padding(.horizontal, 16).padding(.vertical, 11)
        .glassEffect(in: .rect(cornerRadius: 22))
    }

    private var canSend: Bool { !workspace.isAsking && !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    private func send() {
        guard canSend else { return }
        workspace.ask(text, wantsChange: wantsChange?.wrappedValue ?? false)
        text = ""
    }
}

struct AnswerView: View {
    let workspace: Workspace
    let turn: Turn
    let showQuestion: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if showQuestion {
                VStack(alignment: .leading, spacing: 3) {
                    Text(turn.question).font(.title3.weight(.semibold)).textSelection(.enabled)
                    if let scope = turn.scope { Label(scope, systemImage: "folder").font(.caption).foregroundStyle(.secondary) }
                }
            }
            if let failure = turn.failure {
                Label(failure, systemImage: "exclamationmark.triangle.fill").foregroundStyle(.yellow)
            } else if turn.prose.isEmpty, !turn.finished {
                HStack(spacing: 8) { ProgressView().controlSize(.small); Text(turn.answer.isEmpty ? "Reading" : "Writing the change").foregroundStyle(.secondary) }
            } else {
                AnswerText(text: turn.prose)
            }
            ForEach(turn.proposals) { ChangeReview(workspace: workspace, proposal: $0) }
            if !turn.refused.isEmpty {
                Text("Left out: " + turn.refused.joined(separator: "; ")).font(.caption).foregroundStyle(.orange)
            }
            if turn.finished, turn.wantsChange, turn.proposals.isEmpty, turn.failure == nil {
                Text("No change to review.").font(.callout).foregroundStyle(.secondary)
            }
            if !turn.sources.isEmpty { sources }
            if turn.finished, turn.failure == nil { actions }
            if let notes = turn.toRemember { remembered(notes) }
        }
    }

    private var actions: some View {
        HStack(spacing: 14) {
            if let seconds = turn.seconds { Text(String(format: "%.1f s, on this Mac", seconds)).foregroundStyle(.tertiary) }
            Button("Keep as Note") { Task { await workspace.keepAsNote(turn) } }.buttonStyle(.link)
            Button(turn.remembering ? "Thinking…" : "What Should Burrow Remember?") { workspace.remember(turn) }
                .buttonStyle(.link).disabled(turn.remembering)
        }
        .font(.caption)
    }

    private func remembered(_ notes: [ProposedNote]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            if notes.isEmpty { Text("Nothing here worth keeping.").foregroundStyle(.secondary) }
            ForEach(notes, id: \.text) { note in
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Text(note.kind.label).font(.caption.weight(.semibold)).foregroundStyle(Theme.colour(for: note.kind)).frame(width: 66, alignment: .leading)
                    Text(note.text).font(.callout).frame(maxWidth: .infinity, alignment: .leading)
                    if turn.kept.contains(note.text) {
                        Label("Kept", systemImage: "checkmark").font(.caption).foregroundStyle(.green)
                    } else {
                        Button("Keep") { Task { await workspace.keep(note, from: turn) } }.controlSize(.small)
                    }
                }
            }
        }
        .padding(12).background(Color.primary.opacity(0.05), in: .rect(cornerRadius: 10))
    }

    private var sources: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Used").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            ForEach(turn.sources) { source in
                Button { workspace.go(.file(source.path), newTab: true, line: source.startLine) } label: {
                    HStack(spacing: 7) {
                        Circle().fill(colour(source.path)).frame(width: 7, height: 7)
                        Text(source.path.title).lineLimit(1)
                        Text(source.isNote ? "note" : "lines \(source.startLine) to \(source.endLine)").foregroundStyle(.tertiary)
                        if source.how != "search" { Image(systemName: "link").foregroundStyle(.secondary).help(source.how) }
                    }
                    .font(.callout)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func colour(_ path: String) -> Color { workspace.sim.index[path].map { workspace.sim.colour(workspace.sim.nodes[$0].group) } ?? Theme.gold }
}

/// Plain words, with fenced code set apart.
struct AnswerText: View {
    let text: String

    private var parts: [(code: Bool, text: String)] {
        var out: [(code: Bool, text: String)] = []
        var inCode = false
        var lines: [String] = []
        func flush() {
            let joined = lines.joined(separator: "\n").trimmingCharacters(in: .newlines)
            if !joined.isEmpty { out.append((inCode, joined)) }
            lines = []
        }
        for line in text.components(separatedBy: "\n") {
            if line.trimmingCharacters(in: .whitespaces).hasPrefix("```") {
                flush()
                inCode.toggle()
            } else {
                lines.append(line)
            }
        }
        flush()
        return out
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(Array(parts.enumerated()), id: \.offset) { _, part in
                if part.code {
                    Text(part.text).font(.system(size: 12.5, design: .monospaced)).padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled)
                        .background(Color.primary.opacity(0.06), in: .rect(cornerRadius: 8))
                } else {
                    Text((try? AttributedString(markdown: part.text, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace))) ?? AttributedString(part.text))
                        .font(.system(size: 14)).lineSpacing(4).textSelection(.enabled)
                }
            }
        }
    }
}

/// What a proposed change would do, line by line, with accept and reject.
struct ChangeReview: View {
    let workspace: Workspace
    let proposal: Proposal

    private enum Kind { case same, removed, added, gap }
    private struct Row { let kind: Kind; let text: String }

    private var rows: [Row] {
        let old = proposal.old.components(separatedBy: "\n")
        let new = proposal.new.components(separatedBy: "\n")
        var removed = Set<Int>()
        var added = Set<Int>()
        for change in new.difference(from: old) {
            switch change {
            case let .remove(offset, _, _): removed.insert(offset)
            case let .insert(offset, _, _): added.insert(offset)
            }
        }
        var all: [Row] = []
        var i = 0
        var j = 0
        while i < old.count || j < new.count {
            if i < old.count, removed.contains(i) { all.append(Row(kind: .removed, text: old[i])); i += 1 }
            else if j < new.count, added.contains(j) { all.append(Row(kind: .added, text: new[j])); j += 1 }
            else if i < old.count, j < new.count { all.append(Row(kind: .same, text: new[j])); i += 1; j += 1 }
            else { break }
        }
        let near = Set(all.indices.filter { all[$0].kind != .same }.flatMap { max(0, $0 - 3)...min(all.count - 1, $0 + 3) })
        var out: [Row] = []
        var folded = false
        for index in all.indices {
            if near.contains(index) { out.append(all[index]); folded = false }
            else if !folded { out.append(Row(kind: .gap, text: "")); folded = true }
        }
        return out
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(proposal.path).font(.callout.weight(.semibold)).lineLimit(1)
                Spacer()
                switch proposal.state {
                case .waiting:
                    Button("Reject") { proposal.state = .rejected }
                    Button("Accept") { Task { await workspace.accept(proposal) } }.buttonStyle(.borderedProminent)
                case .accepted: Label("Accepted", systemImage: "checkmark").foregroundStyle(.green)
                case .rejected: Label("Rejected", systemImage: "xmark").foregroundStyle(.secondary)
                }
            }
            .padding(10)
            Divider()
            VStack(alignment: .leading, spacing: 0) {
                ForEach(Array(rows.prefix(120).enumerated()), id: \.offset) { _, row in line(row) }
            }
            .padding(.vertical, 6)
        }
        .background(Color.primary.opacity(0.05), in: .rect(cornerRadius: 10))
        .opacity(proposal.state == .rejected ? 0.45 : 1)
    }

    @ViewBuilder private func line(_ row: Row) -> some View {
        switch row.kind {
        case .gap:
            Text("⋯").foregroundStyle(.tertiary).padding(.horizontal, 12).padding(.vertical, 2)
        case .same, .removed, .added:
            HStack(spacing: 8) {
                Text(row.kind == .added ? "+" : row.kind == .removed ? "−" : " ").frame(width: 10)
                Text(row.text.isEmpty ? " " : row.text)
            }
            .font(.system(size: 12, design: .monospaced))
            .padding(.horizontal, 12).padding(.vertical, 1)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(row.kind == .added ? Color.green.opacity(0.18) : row.kind == .removed ? Color.red.opacity(0.18) : Color.clear)
        }
    }
}

struct AskInspector: View {
    let workspace: Workspace

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            GraphCanvas(workspace: workspace, compact: true).frame(height: 280)
            if workspace.lit.isEmpty {
                Text("What the model reads lights up here.").foregroundStyle(.secondary).padding(16)
            } else {
                ReadingStrip(workspace: workspace).padding(12)
            }
            Spacer()
        }
    }
}
