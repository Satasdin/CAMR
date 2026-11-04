import AppKit
import SwiftUI

struct Turn: Identifiable {
    enum Who { case you, camr, note }
    let id = UUID()
    var who: Who
    var text: String
    var meta = ""
    var memory: Bool? = nil  // was memory on for this answer
    var pending = false
    var failed = false
    var raw = ""  // the words as they stream, a <think> block included
    var thinking = ""  // the model's reasoning, shown folded
    var route: String?  // memory, general (the model's own knowledge) or web
    var source: (title: String, url: String)?
    var model = ""  // which model wrote it
    var thinkStart: Date?
    var thinkEnd: Date?
}

/// One chat with the engine: each message is started at once and its live events are read as they come, so the
/// words (and a thinking model's reasoning) appear as they are written and the weights view moves with them.
@MainActor
final class ChatModel: ObservableObject {
    enum Mode { case ask, remember, research }

    @Published var turns: [Turn] = []
    @Published var memoryOn = true
    @Published var busy = false
    @Published var draft = ""
    @Published var reach = ""
    @Published var shelf = "auto"  // where Remember puts a moment: a shelf, or auto (by meaning)
    @Published var shelves: [ShelfInfo] = []
    @Published var thinks = false  // the model is a thinking build
    @Published var reasoning = Prefs.shared.reasoning  // let a thinking model think aloud
    private var job: String?  // the answer being written now, for Stop
    @Published var chats: [(id: String, title: String)] = []

    let engine: Engine
    let weights: WeightsModel

    init(engine: Engine, weights: WeightsModel) {
        self.engine = engine
        self.weights = weights
    }

    func refresh() async {
        guard let st = try? await engine.get("/api/chat/state") else { return }
        if let on = st["on"] as? Bool { memoryOn = on; weights.memoryOn = on }
        thinks = (st.dict("model")?["thinks"] as? Bool) ?? false
        let reaches = st.list("reaches")
        let rooms = reaches.compactMap { $0.num("rooms") }.reduce(0, +)
        if rooms > 0 { weights.rooms = Int(rooms) }
        reach = reaches.first(where: { ($0["written"] as? Bool) == true })?.str("label") ?? ""
        shelves = st.list("shelves").map {
            ShelfInfo(name: $0.str("name") ?? "", label: $0.str("label") ?? "", reach: $0.str("reach") ?? "",
                      notes: Int($0.num("rooms") ?? 0))
        }
        weights.shelves = shelves
        if let sh = st.str("shelf") { shelf = sh }
    }

    /// Shelves on (the engine then reads every shelf), then the warming of the model and the newest notes followed.
    func useShelves() async {
        _ = try? await engine.post("/api/chat/settings", ["shelf": shelf])
        await refresh()
        var next = 0
        for _ in 0..<400 {
            guard let got = try? await engine.get("/api/live?id=warm&from=\(next)") else { break }
            for e in got.list("events") { weights.warmEvent(e) }
            next = Int(got.num("next") ?? Double(next))
            if (got["done"] as? Bool) == true { break }
            try? await Task.sleep(nanoseconds: 50_000_000)
        }
    }

    func pick(shelf name: String) async {
        shelf = name
        _ = try? await engine.post("/api/chat/settings", ["shelf": name])
    }

    func setMemory(_ on: Bool) async {
        memoryOn = on
        weights.memoryOn = on
        _ = try? await engine.post("/api/chat/settings", ["on": on])
        await refresh()
    }

    /// Old callers: remember, or ask.
    func send(remember: Bool) async { await send(remember ? .remember : .ask) }

    func send(_ mode: Mode) async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !busy else { return }
        draft = ""
        busy = true
        defer { busy = false }
        let label = mode == .remember ? "remember" : mode == .research ? "research online" : ""
        turns.append(Turn(who: .you, text: text, meta: label))
        turns.append(Turn(who: .camr, text: "", memory: memoryOn, pending: true, model: engine.model.name))
        let k = turns.count - 1
        weights.beginAnswer(memory: memoryOn)
        let intent = mode == .remember ? "tell" : mode == .research ? "research" : "chat"
        do {
            let prefs = Prefs.shared
            let job = try await engine.post("/api/chat/message", ["text": text, "intent": intent, "shelf": shelf,
                                                                 "thinking": thinks && reasoning,
                                                                 "turns": prefs.turns, "max_tokens": prefs.maxTokens])
            guard let id = job.str("id") else { throw Engine.Failure(message: "no job id") }
            self.job = id
            defer { self.job = nil }
            var next = 0
            var done = false
            while !done {
                let got = try await engine.get("/api/live?id=\(id)&from=\(next)")
                for e in got.list("events") { handle(e, at: k) }
                next = Int(got.num("next") ?? Double(next))
                done = (got["done"] as? Bool) ?? false
                if !done { try await Task.sleep(nanoseconds: 30_000_000) }
            }
        } catch {
            turns[k].text = error.localizedDescription
            turns[k].failed = true
            turns[k].pending = false
            weights.finish(nil)
        }
        await refresh()
    }

    /// Stop the answer being written: the model ends at its next word.
    func stop() async {
        guard let id = job else { return }
        _ = try? await engine.post("/api/live/stop", ["id": id])
    }

    /// A new conversation: the turns start again; memory keeps all it learned.
    func newChat() async {
        guard !busy else { return }
        turns = []
        _ = try? await engine.post("/api/chat/new", [:])
        await loadChats()
    }

    func loadChats() async {
        guard let got = try? await engine.get("/api/chats") else { return }
        chats = got.list("chats").compactMap { c in c.str("id").map { ($0, c.str("title") ?? "Chat") } }
    }

    /// Back to a saved conversation, as it was.
    func openChat(_ id: String) async {
        guard !busy, let got = try? await engine.post("/api/chats/open", ["id": id]) else { return }
        turns = got.list("turns").map { t in
            if t.str("who") == "you" {
                return Turn(who: .you, text: t.str("text") ?? "", meta: t.str("intent") == "tell" ? "remember" : "")
            }
            var turn = Turn(who: .camr, text: t.str("reply") ?? "")
            turn.thinking = t.str("thinking") ?? ""
            turn.route = t.str("route")
            if let src = t.dict("source"), let ti = src.str("title"), let u = src.str("url") { turn.source = (ti, u) }
            return turn
        }
    }

    func ask(_ text: String, _ mode: Mode = .ask) async {
        draft = text
        await send(mode)
    }

    /// A PDF, image, video, text or Markdown file read onto a shelf.
    func attach() {
        let p = NSOpenPanel()
        p.allowsMultipleSelection = false
        p.prompt = "Read into memory"
        guard p.runModal() == .OK, let url = p.url else { return }
        attach(url)
    }

    func attach(_ url: URL) {
        Task {
            turns.append(Turn(who: .you, text: url.lastPathComponent, meta: "attached"))
            turns.append(Turn(who: .camr, text: "Reading \(url.lastPathComponent)…", pending: true))
            let k = turns.count - 1
            do {
                let got = try await engine.post("/api/chat/attach", ["path": url.path, "shelf": shelf])
                let n = Int(got.num("moments") ?? 0)
                let on = shelves.first(where: { $0.name == got.str("shelf") })?.label
                turns[k].text = "Read \(url.lastPathComponent): \(n) piece\(n == 1 ? "" : "s") kept" + (on.map { " on the \($0) shelf." } ?? ".")
            } catch {
                turns[k].text = error.localizedDescription
                turns[k].failed = true
            }
            turns[k].pending = false
            await refresh()
        }
    }

    private func stream(_ piece: String, at k: Int) {
        turns[k].raw += piece
        let raw = turns[k].raw
        if let open = raw.range(of: "<think>") {
            if turns[k].thinkStart == nil { turns[k].thinkStart = Date() }
            if let close = raw.range(of: "</think>") {
                if turns[k].thinkEnd == nil { turns[k].thinkEnd = Date() }
                turns[k].thinking = String(raw[open.upperBound..<close.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
                turns[k].text = String(raw[close.upperBound...]).trimmingCharacters(in: .whitespacesAndNewlines)
            } else {
                turns[k].thinking = String(raw[open.upperBound...]).trimmingCharacters(in: .whitespacesAndNewlines)
            }
        } else {
            turns[k].text = raw
        }
    }

    private func handle(_ e: [String: Any], at k: Int) {
        switch e.str("kind") {
        case "route":
            turns[k].route = e.str("route")
        case "source":
            if let t = e.str("title"), let u = e.str("url") { turns[k].source = (t, u) }
        case "room":
            weights.roomEvent(e)
            if let r = e.num("room") {
                let tier = e.str("tier") ?? ""
                let on = shelves.first(where: { $0.reach == e.str("reach") }).map { " on \($0.label)" } ?? ""
                turns[k].meta = "note \(Int(r))\(on) · " + (tier == "ssd" ? "read from the SSD" : tier == "ram" ? "hot in RAM" : "read as words")
            }
        case "token":
            stream(e.str("text") ?? "", at: k)
            weights.token(e)
        case "read":
            weights.layersEvent(e["layers"] as? [[Double]])
        case "done":
            turns[k].pending = false
            if let err = e.str("error") {
                turns[k].text = err
                turns[k].failed = true
                weights.finish(nil)
                return
            }
            let reply = e.str("reply") ?? turns[k].text
            turns[k].text = reply.trimmingCharacters(in: .whitespacesAndNewlines)
            if let th = e.str("thinking"), !th.isEmpty { turns[k].thinking = th }
            if let r = e.str("route") { turns[k].route = r }
            if let s = e.dict("source"), let t = s.str("title"), let u = s.str("url") { turns[k].source = (t, u) }
            let m = e.dict("metric")
            weights.finish(m)
            var parts: [String] = []
            if e.str("intent") == "tell" {
                if (e["kept"] as? Bool) == true {
                    let label = shelves.first(where: { $0.name == e.str("shelf") })?.label
                    parts.append(label.map { "on the \($0) shelf" } ?? "kept in \(e.str("reach") ?? "memory")")
                    if (e["sorted"] as? Bool) == true { parts.append("sorted by meaning") }
                } else {
                    parts.append("not kept")
                }
            } else {
                switch turns[k].route {
                case "memory": parts.append("from memory")
                case "web": parts.append("from the web")
                case "general": parts.append("from the model")
                default: break
                }
                if let f = m?.num("first_word_s") ?? e.num("wait_s") { parts.append("first word \(secondsText(f))") }
                if !turns[k].meta.isEmpty { parts.append(turns[k].meta) }
                if turns[k].memory == false { parts.append("memory off") }
                if let l = e.dict("learned") {
                    let on = shelves.first(where: { $0.name == l.str("shelf") })?.label
                    parts.append("learned" + (on.map { " on \($0)" } ?? ""))
                }
            }
            turns[k].meta = parts.joined(separator: " · ")
            Task { await loadChats() }
        default:
            break
        }
    }
}

struct ChatView: View {
    @ObservedObject var chat: ChatModel
    @ObservedObject var engine: Engine
    @FocusState private var focused: Bool

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 18) {
                        if chat.turns.isEmpty { empty }
                        ForEach(chat.turns) { t in TurnView(turn: t).id(t.id) }
                    }
                    .padding(.horizontal, 32)
                    .padding(.vertical, 28)
                    .frame(maxWidth: 820, alignment: .leading)
                    .frame(maxWidth: .infinity)
                }
                .onChange(of: chat.turns.count) { _, n in  // once per message: yours at the top, the answer below
                    guard n >= 2 else { return }
                    withAnimation(.easeOut(duration: 0.25)) { proxy.scrollTo(chat.turns[n - 2].id, anchor: .top) }
                }
            }
            composer
        }
        .background(Theme.ink)
        .dropDestination(for: URL.self) { urls, _ in  // drop a file to read it into memory
            urls.prefix(4).forEach { chat.attach($0) }
            return !urls.isEmpty
        }
    }

    private var empty: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Ask anything. It remembers.").font(Theme.ui(26, .semibold)).foregroundStyle(Theme.text)
            Text("It answers from its own knowledge, reaches into memory when a question is about your work or life, and keeps what you discuss on its shelves. Research looks things up online; drop a PDF, image or video to read it into memory.")
                .font(Theme.ui(14)).foregroundStyle(Theme.dim).frame(maxWidth: 520, alignment: .leading)
            VStack(alignment: .leading, spacing: 8) {
                suggestion("Who is the landlord of the Karen branch?", "from memory", .ask)
                suggestion("What is the square root of 56? Show your working.", "the model's own knowledge", .ask)
                suggestion("Who founded the Kenya Wildlife Service?", "researched online, then kept", .research)
            }
            .padding(.top, 12)
        }
        .padding(.top, 60)
    }

    private func suggestion(_ text: String, _ how: String, _ mode: ChatModel.Mode) -> some View {
        Button { Task { await chat.ask(text, mode) } } label: {
            HStack(spacing: 10) {
                Image(systemName: mode == .research ? "globe" : "arrow.up.right").font(.system(size: 11))
                    .foregroundStyle(mode == .research ? Theme.text : Theme.model)
                Text(text).font(Theme.ui(14)).foregroundStyle(Theme.text)
                Text(how).font(Theme.mono(10)).foregroundStyle(Theme.faint)
            }
            .padding(.horizontal, 14).padding(.vertical, 10)
            .background(RoundedRectangle(cornerRadius: 10).fill(Theme.panel))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.line))
        }
        .buttonStyle(.plain)
        .disabled(engine.phase != .ready)
    }

    private var composer: some View {
        VStack(spacing: 8) {
            HStack(alignment: .bottom, spacing: 8) {
                Button { chat.attach() } label: { Image(systemName: "paperclip").font(.system(size: 15, weight: .semibold)) }
                    .buttonStyle(.plain).foregroundStyle(Theme.dim).padding(.bottom, 12)
                    .help("Read a PDF, text or Markdown file into memory")
                TextField(engine.phase == .ready ? "Ask anything, remember something, or research it online…"
                          : "Loading the model…", text: $chat.draft, axis: .vertical)
                    .textFieldStyle(.plain)
                    .font(Theme.ui(15))
                    .foregroundStyle(Theme.text)
                    .lineLimit(1...6)
                    .focused($focused)
                    .onSubmit { Task { await chat.send(.ask) } }
                    .disabled(engine.phase != .ready)
                    .padding(12)
                    .background(RoundedRectangle(cornerRadius: 12).fill(Theme.panel))
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line))
                Button { Task { await chat.send(.research) } } label: { Image(systemName: "globe") }
                    .buttonStyle(Pill(color: Theme.text.opacity(0.85)))
                    .keyboardShortcut(.return, modifiers: [.command, .shift])
                    .help("Research it online, answer from the source, and keep it on the Research shelf (⇧⌘↩)")
                Button { Task { await chat.send(.remember) } } label: {
                    Label("Remember", systemImage: "pin").labelStyle(.titleAndIcon)
                }
                .buttonStyle(Pill(color: Theme.memory))
                .keyboardShortcut(.return, modifiers: .command)
                .help("Keep this in memory (⌘↩)")
                if chat.busy {
                    Button { Task { await chat.stop() } } label: {
                        Label("Stop", systemImage: "stop.fill").labelStyle(.titleAndIcon)
                    }
                    .buttonStyle(Pill(color: Theme.text))
                    .keyboardShortcut(".", modifiers: .command)
                    .help("Stop the answer (⌘.)")
                } else {
                    Button { Task { await chat.send(.ask) } } label: {
                        Label("Ask", systemImage: "arrow.up").labelStyle(.titleAndIcon)
                    }
                    .buttonStyle(Pill(color: Theme.model))
                    .help("Ask (↩)")
                    .disabled(engine.phase != .ready)
                }
            }
            HStack {
                Text("↩ ask · ⌘↩ remember · ⇧⌘↩ research online").font(Theme.mono(10)).foregroundStyle(Theme.faint)
                Spacer()
                if chat.thinks {
                    Toggle("Show reasoning", isOn: $chat.reasoning).toggleStyle(.checkbox).font(Theme.mono(10))
                        .foregroundStyle(Theme.dim)
                } else {
                    Text("this model answers without reasoning").font(Theme.mono(10)).foregroundStyle(Theme.faint)
                }
            }
        }
        .padding(.horizontal, 32)
        .padding(.vertical, 16)
        .frame(maxWidth: 860)
        .frame(maxWidth: .infinity)
        .background(Theme.ink)
        .onAppear { focused = true }
    }
}

struct TurnView: View {
    let turn: Turn

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Text(turn.who == .you ? "YOU" : "CAMR").font(Theme.mono(10, .semibold))
                    .foregroundStyle(turn.who == .you ? Theme.dim : (turn.route == "memory" ? Theme.memory : Theme.model))
                if turn.pending { ProgressView().controlSize(.mini) }
                if !turn.meta.isEmpty && turn.who == .you {
                    Text(turn.meta).font(Theme.mono(10)).foregroundStyle(Theme.memory.opacity(0.8))
                }
            }
            if !turn.thinking.isEmpty {
                if turn.pending && turn.text.isEmpty {  // thinking now: the newest lines in view, as Ollama shows it
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Thinking…").font(Theme.mono(11, .semibold)).foregroundStyle(Theme.model)
                        ScrollView { reasoning }
                            .defaultScrollAnchor(.bottom)
                            .frame(maxHeight: 160)
                            .mask(LinearGradient(colors: [.clear, .black, .black], startPoint: .top, endPoint: .init(x: 0.5, y: 0.25)))
                    }
                } else {
                    DisclosureGroup {
                        reasoning
                    } label: {
                        Text(thoughtFor).font(Theme.mono(11, .semibold)).foregroundStyle(Theme.model)
                    }
                    .tint(Theme.model)
                }
            }
            if !(turn.text.isEmpty && !turn.thinking.isEmpty) {
                let text = turn.text.isEmpty && turn.pending ? "…" : turn.text
                ForEach(Array(blocks(text).enumerated()), id: \.offset) { _, b in
                    if b.code {
                        CodeBlock(code: b.text)
                    } else {
                        Text(rendered(b.text))
                            .font(Theme.ui(15))
                            .foregroundStyle(turn.failed ? Theme.error : Theme.text)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
            if let s = turn.source, let url = URL(string: s.url) {
                Link(destination: url) {
                    Label("Source: \(s.title)", systemImage: "globe").font(Theme.mono(10))
                }
                .foregroundStyle(Theme.memory)
            }
            if turn.who == .camr, !turn.pending {
                HStack(spacing: 10) {
                    if !turn.meta.isEmpty { Text(turn.meta).font(Theme.mono(10)).foregroundStyle(Theme.faint) }
                    if !turn.model.isEmpty { Text(turn.model).font(Theme.mono(10)).foregroundStyle(Theme.faint) }
                    Button {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(turn.text, forType: .string)
                    } label: { Image(systemName: "doc.on.doc").font(.system(size: 10)) }
                    .buttonStyle(.plain).foregroundStyle(Theme.faint).help("Copy the answer")
                }
            }
        }
    }

    private var thoughtFor: String {
        guard let a = turn.thinkStart, let b = turn.thinkEnd else { return "Thought" }
        let s = b.timeIntervalSince(a)
        return s < 2 ? "Thought for a moment" : String(format: "Thought for %.1f seconds", s)
    }

    private var reasoning: some View {
        Text(turn.thinking).font(Theme.ui(13)).foregroundStyle(Theme.dim).textSelection(.enabled)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.leading, 10)
            .overlay(alignment: .leading) { Rectangle().fill(Theme.model.opacity(0.35)).frame(width: 2) }
    }

    /// LaTeX as the model writes maths, made readable: √, ×, ≈, ², fractions; $ and $$ fences dropped.
    private func mathText(_ text: String) -> String {
        var t = text
        let words: [(String, String)] = [("\\times", "×"), ("\\cdot", "·"), ("\\approx", "≈"), ("\\neq", "≠"),
                                         ("\\leq", "≤"), ("\\geq", "≥"), ("\\le ", "≤ "), ("\\ge ", "≥ "),
                                         ("\\pm", "±"), ("\\div", "÷"), ("\\pi", "π"), ("\\infty", "∞"),
                                         ("\\quad", "  "), ("\\,", " "), ("\\left", ""), ("\\right", ""),
                                         ("\\boxed", ""), ("\\displaystyle", "")]
        for (a, b) in words { t = t.replacingOccurrences(of: a, with: b) }
        let rules: [(String, String)] = [(#"\\sqrt\{([^{}]*)\}"#, "√($1)"), (#"\\frac\{([^{}]*)\}\{([^{}]*)\}"#, "($1)/($2)"),
                                         (#"\\text\{([^{}]*)\}"#, "$1"), (#"\\mathrm\{([^{}]*)\}"#, "$1"),
                                         (#"\^2(?![0-9])"#, "²"), (#"\^3(?![0-9])"#, "³"), (#"\^\{([^{}]*)\}"#, "^$1"),
                                         (#"√\(([0-9a-z.]+)\)"#, "√$1")]
        for (pattern, with) in rules {
            t = t.replacingOccurrences(of: pattern, with: with, options: .regularExpression)
        }
        t = t.replacingOccurrences(of: "$$", with: "").replacingOccurrences(of: "\\[", with: "")
            .replacingOccurrences(of: "\\]", with: "").replacingOccurrences(of: "\\(", with: "")
            .replacingOccurrences(of: "\\)", with: "")
        t = t.replacingOccurrences(of: #"\$([^$\n]+)\$"#, with: "$1", options: .regularExpression)
        return t.replacingOccurrences(of: #"\n{3,}"#, with: "\n\n", options: .regularExpression)
    }

    /// The answer split at its fenced code blocks: prose and code in turn.
    private func blocks(_ text: String) -> [(code: Bool, text: String)] {
        var out: [(Bool, String)] = []
        let parts = text.components(separatedBy: "```")
        for (i, part) in parts.enumerated() {
            if i % 2 == 1 {  // inside a fence: drop the language line
                let body = part.split(separator: "\n", maxSplits: 1, omittingEmptySubsequences: false)
                let code = body.count > 1 && !body[0].contains(" ") ? String(body[1]) : part
                out.append((true, code.trimmingCharacters(in: .newlines)))
            } else if !part.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                out.append((false, part.trimmingCharacters(in: .newlines)))
            }
        }
        return out.isEmpty ? [(false, text)] : out
    }

    /// Markdown as the model writes it (bold, code, links), line breaks kept.
    private func rendered(_ text: String) -> AttributedString {
        // headings and bullets, as the model writes them: a heading bold, a "- " item a bullet; maths readable
        let lines = mathText(text).components(separatedBy: "\n").map { line -> String in
            let t = line.trimmingCharacters(in: .whitespaces)
            if t.hasPrefix("#") {
                let h = t.drop(while: { $0 == "#" }).trimmingCharacters(in: .whitespaces)
                return h.isEmpty ? "" : "**\(h)**"
            }
            if t.hasPrefix("- ") || t.hasPrefix("* ") {
                let indent = String(line.prefix(while: { $0 == " " }))
                return indent + "• " + t.dropFirst(2)
            }
            return line
        }
        var out = (try? AttributedString(markdown: lines.joined(separator: "\n"),
                                         options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)))
            ?? AttributedString(text)
        for run in out.runs {  // a model's words may carry a page's links: only plain web links stay clickable
            if let url = run.link, !["http", "https"].contains(url.scheme?.lowercased() ?? "") {
                out[run.range].link = nil
            }
        }
        return out
    }
}

struct Pill: ButtonStyle {
    let color: Color

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Theme.ui(13, .semibold))
            .foregroundStyle(Color.black)
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(Capsule().fill(color.opacity(configuration.isPressed ? 0.7 : 1)))
            .glow(color, radius: 6, opacity: 0.35)
    }
}

/// A code block in an answer: monospaced, scrolling sideways, with its own Copy button.
struct CodeBlock: View {
    let code: String

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Spacer()
                Button {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(code, forType: .string)
                } label: { Label("Copy", systemImage: "doc.on.doc").font(Theme.mono(10)) }
                .buttonStyle(.plain).foregroundStyle(Theme.dim)
            }
            .padding(.horizontal, 10).padding(.top, 6)
            ScrollView(.horizontal) {
                Text(code).font(Theme.mono(12)).foregroundStyle(Theme.text).textSelection(.enabled)
                    .padding(.horizontal, 12).padding(.bottom, 10).padding(.top, 2)
            }
        }
        .background(RoundedRectangle(cornerRadius: 8).fill(Color.black))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line))
    }
}
