import AppKit
import BurrowCore
import BurrowTools
import SwiftUI

/// What the Ledger holds, read once per refresh: every commit, which were marked wrong, and which rest on changed files.
struct LedgerState: Sendable {
    var commits: [LedgerCommit] = []
    var reverted: Set<String> = []
    /// Commit id → the cited files that changed since it was written.
    var stale: [String: [String]] = [:]
    var current = Ledger.defaultBranch

    var branches: [String] { Array(Set(commits.map(\.branch))).sorted() }
    func commits(on branch: String?) -> [LedgerCommit] { branch.map { name in commits.filter { $0.branch == name } } ?? commits }
    func citing(_ path: String) -> [LedgerCommit] { commits.filter { $0.cites.keys.contains(path) } }
}

extension LedgerCommit.Kind {
    var title: String {
        switch self {
        case .decision: return "Decision"
        case .fact: return "Fact"
        case .correction: return "Correction"
        case .plan: return "Plan"
        case .handoff: return "Handoff"
        case .code: return "Code commit"
        }
    }

    var symbol: String {
        switch self {
        case .decision: return "checkmark.seal"
        case .fact: return "text.book.closed"
        case .correction: return "arrow.uturn.backward.circle"
        case .plan: return "list.bullet.clipboard"
        case .handoff: return "arrow.right.circle"
        case .code: return "chevron.left.forwardslash.chevron.right"
        }
    }

    /// The colour key holds: notes white, conversations cyan, wrong or stale red. Code commits are the plain case.
    var colour: Color {
        switch self {
        case .decision, .fact, .plan: return Night.note
        case .handoff: return Night.conversation
        case .correction: return Night.stale
        case .code: return Night.dim
        }
    }
}

/// The Ledger: what AIs understood, decided, were corrected on and where they stopped, as a timeline per branch.
struct LedgerPage: View {
    let workspace: Workspace
    let branch: String?
    @State private var resume: String?
    @State private var copied = false

    private var commits: [LedgerCommit] { workspace.ledger.commits(on: branch) }
    private var days: [(day: Date, commits: [LedgerCommit])] {
        let calendar = Calendar.current
        let grouped = Dictionary(grouping: commits) { calendar.startOfDay(for: $0.at) }
        return grouped.keys.sorted(by: >).map { ($0, grouped[$0]!) }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    Text("Ledger").font(.system(size: 28, weight: .bold)).tracking(-0.4)
                    Text("\(commits.count.counted("commit"))\(branch.map { " on \($0)" } ?? " on \(workspace.ledger.branches.count.counted("branch", "branches"))")")
                        .foregroundStyle(Night.dim).monospacedDigit()
                    Spacer()
                    Button { Task { await showResume() } } label: { Label("Resume", systemImage: "arrow.right.circle") }
                        .help("What a model that lost its memory would be handed for this branch")
                }
                branchChips
                if let resume { resumeCard(resume) }
                if commits.isEmpty {
                    ContentUnavailableView("Nothing kept yet", systemImage: "books.vertical",
                                           description: Text("Programs keep decisions, plans and where they stopped here, through burrow_commit and the Claude Code and git hooks. Run burrow hook install claude <vault> to start."))
                        .foregroundStyle(Night.dim).frame(maxWidth: .infinity).padding(.top, 40)
                }
                ForEach(days, id: \.day) { day in
                    VStack(alignment: .leading, spacing: 0) {
                        Text(day.day.dayTitle).font(.system(size: 15, weight: .semibold)).padding(.bottom, 12)
                        ForEach(Array(day.commits.enumerated()), id: \.element.id) { index, commit in
                            CommitRow(workspace: workspace, commit: commit, last: index == day.commits.count - 1)
                        }
                    }
                }
            }
            .padding(.horizontal, 28).padding(.vertical, 22).frame(maxWidth: 920, alignment: .leading)
        }
        .frame(maxWidth: .infinity)
        .background(Night.ground)
        .environment(\.colorScheme, .dark)
        .task(id: branch) { resume = nil }
    }

    private var branchChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                chip("All", selected: branch == nil) { workspace.go(.ledger(nil)) }
                ForEach(workspace.ledger.branches, id: \.self) { name in
                    chip(name + (name == workspace.ledger.current ? " ·" : ""), selected: branch == name) { workspace.go(.ledger(name)) }
                }
            }
        }
    }

    private func chip(_ title: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title).font(.system(size: 12.5, weight: .medium)).padding(.horizontal, 12).padding(.vertical, 5)
                .background(selected ? Color.white.opacity(0.16) : Night.card, in: .capsule)
                .overlay { Capsule().strokeBorder(Night.line) }
        }
        .buttonStyle(.plain)
    }

    private func resumeCard(_ text: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Label("What the next model is handed", systemImage: "arrow.right.circle").font(.system(size: 13, weight: .semibold)).foregroundStyle(Night.conversation)
                Spacer()
                Button(copied ? "Copied" : "Copy") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(text, forType: .string)
                    copied = true
                }
                .controlSize(.small)
                Button { resume = nil } label: { Image(systemName: "xmark") }.buttonStyle(.plain).foregroundStyle(Night.dim)
            }
            Text(text).font(.system(size: 12, design: .monospaced)).foregroundStyle(Night.note.opacity(0.85)).textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(14)
        .background(Night.card, in: .rect(cornerRadius: 12))
        .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder(Night.conversation.opacity(0.3)) }
    }

    private func showResume() async {
        copied = false
        resume = await workspace.resumeText(branch)
    }
}

/// One commit on the timeline: its kind, what it says, who wrote it, and the files it rests on.
struct CommitRow: View {
    let workspace: Workspace
    let commit: LedgerCommit
    let last: Bool
    @State private var correcting = false
    @State private var right = ""

    private var wrong: Bool { workspace.ledger.reverted.contains(commit.id) }
    private var stale: [String] { workspace.ledger.stale[commit.id] ?? [] }
    private var dot: Color { wrong || !stale.isEmpty ? Night.stale : commit.kind.colour }

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            VStack(spacing: 0) {
                Circle().fill(dot).frame(width: 10, height: 10).shadow(color: dot, radius: 5).padding(.top, 5)
                if !last { Rectangle().fill(Night.line).frame(width: 1.5).frame(maxHeight: .infinity) }
            }
            .frame(width: 14)
            VStack(alignment: .leading, spacing: 7) {
                HStack(spacing: 8) {
                    Label(commit.kind.title, systemImage: commit.kind.symbol).font(.system(size: 12, weight: .semibold)).foregroundStyle(commit.kind.colour)
                    Text(commit.branch).font(.system(size: 11.5)).foregroundStyle(Night.faint)
                    Text(commit.at.formatted(date: .omitted, time: .shortened)).font(.system(size: 11.5)).foregroundStyle(Night.faint).monospacedDigit()
                    if wrong { tag("Marked wrong", Night.stale) }
                    if !stale.isEmpty { tag("Check again", Night.stale).help("Changed since: " + stale.joined(separator: ", ")) }
                }
                Text(commit.message).font(.system(size: 14, weight: commit.kind == .plan || commit.kind == .decision ? .medium : .regular))
                    .foregroundStyle(wrong ? Night.dim : Night.note).strikethrough(wrong, color: Night.stale.opacity(0.7)).textSelection(.enabled)
                if !commit.body.isEmpty {
                    Text(commit.body).font(.system(size: 12)).foregroundStyle(Night.dim).lineLimit(4).textSelection(.enabled)
                }
                Text("Written by \(commit.author)\(commit.client.map { " in \($0)" } ?? "")\(commit.sha.map { " · git \($0.prefix(10))" } ?? "")")
                    .font(.system(size: 11.5)).foregroundStyle(Night.faint)
                files
                if correcting {
                    HStack {
                        TextField("What is right instead", text: $right).textFieldStyle(.roundedBorder)
                        Button("Mark Wrong") {
                            let words = right
                            Task { await workspace.markWrong(commit.id, why: words) }
                            correcting = false
                        }
                        .disabled(right.trimmingCharacters(in: .whitespaces).isEmpty)
                        Button("Cancel") { correcting = false }
                    }
                    .controlSize(.small)
                }
            }
            .padding(.bottom, 20)
            Spacer(minLength: 0)
        }
        .contextMenu {
            if commit.kind != .correction && !wrong { Button("Mark Wrong…") { correcting = true } }
            Button("Copy Message") { NSPasteboard.general.clearContents(); NSPasteboard.general.setString(commit.message, forType: .string) }
            if let session = commit.session, workspace.sessions.contains(where: { $0.id == session }) {
                Button("Open Conversation") { workspace.go(.session(session)) }
            }
        }
    }

    private func tag(_ text: String, _ colour: Color) -> some View {
        Text(text).font(.system(size: 10.5, weight: .semibold)).foregroundStyle(.black).padding(.horizontal, 6).padding(.vertical, 1).background(colour, in: .capsule)
    }

    @ViewBuilder private var files: some View {
        let paths = commit.cites.keys.sorted()
        if !paths.isEmpty {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(paths.prefix(8), id: \.self) { path in
                        Button { workspace.go(.file(path), newTab: true) } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                if workspace.map.files.contains(where: { $0.path == path }) {
                                    CoverImage(workspace: workspace, path: path, size: CGSize(width: 200, height: 150), compact: true)
                                        .frame(width: 84, height: 63).clipShape(.rect(cornerRadius: 5))
                                        .overlay { RoundedRectangle(cornerRadius: 5).strokeBorder(stale.contains(path) ? Night.stale : (LibraryKind.colour(of: path) ?? Night.line).opacity(0.5)) }
                                }
                                Text(path.fileName).font(.system(size: 10.5)).foregroundStyle(stale.contains(path) ? Night.stale : Night.dim).lineLimit(1).frame(width: 84, alignment: .leading)
                            }
                        }
                        .buttonStyle(.plain).help(path)
                    }
                }
            }
        }
    }
}

/// For the Library inspector: what the Ledger says about this file.
struct LedgerAboutFile: View {
    let workspace: Workspace
    let path: String

    var body: some View {
        let found = workspace.ledger.citing(path)
        VStack(alignment: .leading, spacing: 8) {
            Text("In the Ledger").font(.system(size: 12, weight: .semibold))
            if found.isEmpty {
                Text("No session has written about this yet.").font(.system(size: 12)).foregroundStyle(Night.faint)
            }
            ForEach(found.prefix(5), id: \.id) { commit in
                let flagged = workspace.ledger.reverted.contains(commit.id) || workspace.ledger.stale[commit.id] != nil
                Button { workspace.go(.ledger(commit.branch)) } label: {
                    HStack(alignment: .top, spacing: 8) {
                        Image(systemName: commit.kind.symbol).foregroundStyle(flagged ? Night.stale : commit.kind.colour).frame(width: 16)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(commit.message).font(.system(size: 12)).lineLimit(3).foregroundStyle(Night.note.opacity(flagged ? 0.6 : 0.9))
                            Text("\(commit.kind.title) · \(commit.author)").font(.system(size: 11)).foregroundStyle(Night.faint)
                        }
                        Spacer(minLength: 0)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
    }
}
