import AppKit
import SwiftUI

struct CodeTurn: Identifiable {
    let id = UUID()
    let kind: String  // you, model, call, answer, error, kept, stopped
    let text: String
    let detail: String
}

/// The coding agent on the local model: a folder to work in, its files, and runs that read, search, edit and run
/// commands there. Every shell command waits for an Allow here first.
@MainActor
final class CodeModel: ObservableObject {
    @Published var root: String?
    @Published var files: [(path: String, dir: Bool)] = []
    @Published var openPath: String?
    @Published var openText = ""
    @Published var turns: [CodeTurn] = []
    @Published var term = ""
    @Published var waiting: [[String: Any]] = []
    @Published var state = ""
    @Published var draft = ""
    @Published var busy = false
    @Published var memoryOn = true
    @Published var error: String?

    let engine: Engine
    let weights: WeightsModel
    private var thread: String?
    private var run: String?
    private var termNext = 0
    private var turnsSeen = 0
    private var liveNext = 0

    init(engine: Engine, weights: WeightsModel) {
        self.engine = engine
        self.weights = weights
    }

    func refresh() async {
        guard let st = try? await engine.get("/api/code/state") else { return }
        root = st.dict("workspace")?.str("root") ?? st.str("workspace") ?? root
        await loadFiles()
    }

    func chooseFolder() {
        let p = NSOpenPanel()
        p.canChooseDirectories = true
        p.canChooseFiles = false
        p.prompt = "Work here"
        guard p.runModal() == .OK, let url = p.url else { return }
        Task {
            do {
                _ = try await engine.post("/api/code/workspace", ["path": url.path])
                root = url.path
                thread = nil
                turns = []
                term = ""
                await loadFiles()
            } catch { self.error = error.localizedDescription }
        }
    }

    func loadFiles() async {
        guard let got = try? await engine.get("/api/code/files") else { return }
        root = got.str("root") ?? root
        files = got.list("files").compactMap { f in f.str("path").map { ($0, (f["dir"] as? Bool) ?? false) } }
    }

    func open(_ path: String) async {
        let q = path.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? path
        guard let got = try? await engine.get("/api/code/file?path=\(q)") else { return }
        openPath = path
        openText = got.str("text") ?? ""
    }

    func start() async {
        let task = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !task.isEmpty, !busy else { return }
        guard root != nil else { error = "Choose a folder to work in first."; return }
        draft = ""
        busy = true
        error = nil
        defer { busy = false }
        weights.beginAnswer(memory: memoryOn)
        do {
            if thread == nil {
                let t = try await engine.post("/api/code/thread", ["title": String(task.prefix(60))])
                thread = t.str("id")
            }
            let r = try await engine.post("/api/code/run", ["thread": thread ?? "", "task": task, "memory": memoryOn])
            run = r.str("id")
            termNext = 0
            turnsSeen = 0
            liveNext = 0
            take(r)
            while let id = run {
                try await Task.sleep(nanoseconds: 250_000_000)
                let s = try await engine.get("/api/code/run?id=\(id)&term=\(termNext)&turns=\(turnsSeen)")
                take(s)
                await follow(id)
                if ["done", "stopped", "failed"].contains(s.str("state") ?? "") { break }
            }
            weights.finish(nil)
            await loadFiles()
            if let p = openPath { await open(p) }
        } catch {
            self.error = error.localizedDescription
            weights.finish(nil)
        }
    }

    /// The run's live events, when the engine reports them (each word with its layers, and the room each step read).
    private func follow(_ id: String) async {
        guard let got = try? await engine.get("/api/code/live?id=\(id)&from=\(liveNext)") else { return }
        for e in got.list("events") {
            switch e.str("kind") {
            case "room": weights.roomEvent(e)
            case "token": weights.token(e)
            case "read": weights.layersEvent(e["layers"] as? [[Double]])
            default: break
            }
        }
        liveNext = Int(got.num("next") ?? Double(liveNext))
    }

    private func take(_ s: [String: Any]) {
        state = s.str("state") ?? state
        for t in s.list("turns") {
            let kind = t.str("kind") ?? ""
            var detail = ""
            if kind == "call" {
                detail = [t.str("name"), t.str("summary") ?? t.str("args").map { String($0.prefix(160)) }]
                    .compactMap { $0 }.joined(separator: " · ")
            } else if let calls = t["calls"] as? [String], !calls.isEmpty {
                detail = calls.joined(separator: ", ")
            }
            let text = t.str("text") ?? t.str("result") ?? t.str("output") ?? ""
            if kind == "model", detail.isEmpty { continue }  // a step with no tool call is the answer, shown next
            turns.append(CodeTurn(kind: kind, text: text, detail: detail))
        }
        turnsSeen = Int(s.num("turns_total") ?? Double(turnsSeen))
        for chunk in s["term"] as? [String] ?? [] { term += chunk }
        if term.count > 20000 { term = String(term.suffix(20000)) }
        termNext = Int(s.num("term_next") ?? Double(termNext))
        waiting = s.list("waiting")
    }

    func decide(_ id: String, allow: Bool) async {
        _ = try? await engine.post("/api/code/approve", ["id": id, "allow": allow])
        waiting.removeAll { $0.str("id") == id }
    }

    func stop() async {
        guard let id = run else { return }
        _ = try? await engine.post("/api/code/stop", ["run": id])
    }
}

struct CodeView: View {
    @ObservedObject var code: CodeModel
    @ObservedObject var engine: Engine

    var body: some View {
        HSplitView {
            filesPane.frame(width: 230)
            VStack(spacing: 0) {
                transcript
                if !code.waiting.isEmpty { approvals }
                composer
            }
            .frame(minWidth: 420)
            if code.openPath != nil { editor.frame(minWidth: 320, idealWidth: 460) }
        }
        .background(Theme.ink)
        .task { await code.refresh() }
    }

    private var filesPane: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(code.root.map { URL(fileURLWithPath: $0).lastPathComponent } ?? "No folder")
                    .font(Theme.ui(13, .semibold)).foregroundStyle(Theme.text).lineLimit(1)
                Spacer()
                Button("Open…") { code.chooseFolder() }.buttonStyle(.plain).font(Theme.ui(12))
                    .foregroundStyle(Theme.memory)
            }
            .padding(12)
            Divider().overlay(Theme.line)
            List(code.files, id: \.path) { f in
                HStack(spacing: 6) {
                    Image(systemName: f.dir ? "folder" : "doc.text").font(.system(size: 11))
                        .foregroundStyle(f.dir ? Theme.dim : Theme.faint)
                    Text(f.path).font(Theme.mono(11)).foregroundStyle(f.path == code.openPath ? Theme.model : Theme.text)
                        .lineLimit(1)
                }
                .contentShape(Rectangle())
                .onTapGesture { if !f.dir { Task { await code.open(f.path) } } }
            }
            .scrollContentBackground(.hidden)
            .listStyle(.plain)
        }
        .background(Theme.panel)
    }

    private var transcript: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 14) {
                    if code.turns.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Give it a task in this folder.").font(Theme.ui(24, .semibold)).foregroundStyle(Theme.text)
                            Text("It reads and searches the files, edits them, and runs commands after you allow each one. With memory on it remembers your fixes for next time.")
                                .font(Theme.ui(14)).foregroundStyle(Theme.dim).frame(maxWidth: 480, alignment: .leading)
                        }
                        .padding(.top, 40)
                    }
                    ForEach(code.turns) { t in CodeTurnView(turn: t).id(t.id) }
                    if !code.term.isEmpty {
                        Text(code.term).font(Theme.mono(11)).foregroundStyle(Theme.dim)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(10).background(RoundedRectangle(cornerRadius: 8).fill(Color.black))
                            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line))
                            .textSelection(.enabled)
                    }
                    if let e = code.error { Text(e).font(Theme.ui(13)).foregroundStyle(Theme.error) }
                }
                .padding(24)
            }
            .onChange(of: code.turns.count) { _, _ in
                if let id = code.turns.last?.id { proxy.scrollTo(id, anchor: .bottom) }
            }
        }
    }

    private var approvals: some View {
        VStack(spacing: 8) {
            ForEach(Array(code.waiting.enumerated()), id: \.offset) { _, a in
                HStack(spacing: 10) {
                    Image(systemName: "exclamationmark.shield").foregroundStyle(Theme.model)
                    VStack(alignment: .leading, spacing: 4) {
                        let what = a.str("what") ?? ""
                        let lines = what.split(separator: "\n", omittingEmptySubsequences: false).count
                        Text(lines > 1 ? "Run this? (\(lines) lines)" : "Run this?")
                            .font(Theme.ui(12, .semibold)).foregroundStyle(lines > 1 ? Theme.model : Theme.text)
                        ScrollView {  // the whole command, never cut short, with line breaks shown
                            Text(what.replacingOccurrences(of: "\n", with: "⏎\n").replacingOccurrences(of: "\t", with: "⇥"))
                                .font(Theme.mono(11)).foregroundStyle(Theme.text).textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .frame(maxHeight: 160)
                    }
                    Spacer()
                    Button("Deny") { Task { await code.decide(a.str("id") ?? "", allow: false) } }
                    Button("Allow") { Task { await code.decide(a.str("id") ?? "", allow: true) } }
                        .buttonStyle(Pill(color: Theme.model))
                }
                .padding(12)
                .background(RoundedRectangle(cornerRadius: 10).fill(Theme.panel))
            }
        }
        .padding(.horizontal, 24)
        .padding(.bottom, 8)
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField(code.root == nil ? "Open a folder first" : "Fix the failing test, add a feature, explain this code…",
                      text: $code.draft, axis: .vertical)
                .textFieldStyle(.plain).font(Theme.ui(14)).foregroundStyle(Theme.text).lineLimit(1...6)
                .onSubmit { Task { await code.start() } }
                .padding(12)
                .background(RoundedRectangle(cornerRadius: 12).fill(Theme.panel))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line))
            if code.busy {
                Button("Stop") { Task { await code.stop() } }.buttonStyle(Pill(color: Theme.error))
            } else {
                Button { Task { await code.start() } } label: { Label("Run", systemImage: "play.fill") }
                    .buttonStyle(Pill(color: Theme.model))
                    .disabled(engine.phase != .ready || code.root == nil)
            }
        }
        .padding(16)
        .overlay(alignment: .topLeading) {
            if code.busy {
                Text(code.state.uppercased()).font(Theme.mono(9, .semibold)).foregroundStyle(Theme.model)
                    .padding(.leading, 20).offset(y: -4)
            }
        }
    }

    private var editor: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(code.openPath ?? "").font(Theme.mono(11)).foregroundStyle(Theme.dim).lineLimit(1)
                Spacer()
                Button { code.openPath = nil } label: { Image(systemName: "xmark") }.buttonStyle(.plain)
                    .foregroundStyle(Theme.faint)
            }
            .padding(10)
            Divider().overlay(Theme.line)
            ScrollView([.vertical, .horizontal]) {
                Text(code.openText).font(Theme.mono(12)).foregroundStyle(Theme.text).textSelection(.enabled)
                    .padding(12).frame(maxWidth: .infinity, alignment: .topLeading)
            }
        }
        .background(Color.black)
    }
}

struct CodeTurnView: View {
    let turn: CodeTurn

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(Theme.mono(10, .semibold)).foregroundStyle(color)
            if !turn.detail.isEmpty {
                Text(turn.detail).font(Theme.mono(11)).foregroundStyle(Theme.model.opacity(0.85)).lineLimit(4)
            }
            if !turn.text.isEmpty {
                Text(turn.text).font(turn.kind == "call" ? Theme.mono(11) : Theme.ui(14))
                    .foregroundStyle(turn.kind == "error" ? Theme.error : (turn.kind == "call" ? Theme.dim : Theme.text))
                    .lineLimit(turn.kind == "call" ? 12 : nil)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    var label: String {
        switch turn.kind {
        case "you": return "YOU"
        case "model": return "CAMR · THINKING"
        case "call": return "TOOL"
        case "answer": return "CAMR"
        case "kept": return "KEPT IN MEMORY"
        default: return turn.kind.uppercased()
        }
    }

    var color: Color {
        switch turn.kind {
        case "you": return Theme.dim
        case "kept": return Theme.memory
        case "error": return Theme.error
        default: return Theme.model
        }
    }
}
