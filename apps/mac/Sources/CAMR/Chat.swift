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
    var pipe: Measured?  // how this answer read memory, as the engine measured it
    var runs: [Run] = []  // a comparison: the same question answered by CAMR, RAG and the model alone
    var checked = 0  // the fact check: how many facts it looked up in memory…
    var unbacked: [String] = []  // …and those memory does not hold
    var agent: AgentState?  // the agent's work, when this answer was a request to make something
    var agentRev = 0  // changes whenever the agent's card does
}

/// One answer's pipeline, as the engine measured it (camr_engine.app.routes.chat, ``pipeline``).
struct Measured {
    var mode = "camr"
    var route = ""
    var firstWord: Double?
    var retrievalMs: Double?
    var prefill = 0  // tokens read as text before the first word
    var memoryText = 0  // of which memory, as words
    var notes = 0  // tokens found already read, as notes
    var notesBytes = 0.0
    var readBytes = 0.0
    var answerTokens = 0
    var decodeTps: Double?
    var source = ""  // the room, or the chunks, it answered from

    init() {}

    init(_ d: [String: Any], shelves: [ShelfInfo]) {
        mode = d.str("mode") ?? "camr"
        route = d.str("route") ?? ""
        firstWord = d.num("first_word_s")
        retrievalMs = d.num("retrieval_ms")
        prefill = Int(d.num("prefill_tokens") ?? 0)
        memoryText = Int(d.num("memory_text_tokens") ?? 0)
        notes = Int(d.num("notes_tokens") ?? 0)
        notesBytes = d.num("notes_bytes") ?? 0
        readBytes = d.num("read_bytes") ?? 0
        answerTokens = Int(d.num("answer_tokens") ?? 0)
        decodeTps = d.num("decode_tps")
        func shelf(_ name: String?) -> String? { shelves.first(where: { $0.name == name })?.label }
        if let src = d.dict("source") {
            if let room = src.num("room") {
                let tier = (src["asleep"] as? Bool) == true ? "asleep, read as words"
                    : src.str("tier") == "ssd" ? "read from the SSD" : src.str("tier") == "ram" ? "hot in RAM" : "as words"
                source = "room \(Int(room))" + (shelf(src.str("shelf")).map { " on \($0)" } ?? "") + " · \(tier)"
                    + " · +\(Int(src.num("closest") ?? 0)) closest as words"
            } else {
                let chunks = src.list("chunks")
                var by: [String: Int] = [:]
                for c in chunks { by[shelf(c.str("shelf")) ?? "memory", default: 0] += 1 }
                let on = by.sorted { $0.value > $1.value }.map { "\($0.value) \($0.key)" }.joined(separator: ", ")
                source = "\(chunks.count) chunks pasted as text (\(on))"
            }
        } else {
            source = route == "general" && mode != "off" ? "routed to the model's own knowledge" : "no memory"
        }
    }
}

/// One of a comparison's three answers.
struct Run: Identifiable {
    let mode: String
    var id: String { mode }
    var text = ""
    var pending = true
    var started = false
    var failed = false
    var pipe: Measured?
}

/// One chat with the engine: each message is started at once and its live events are read as they come, so the
/// words (and a thinking model's reasoning) appear as they are written and the weights view moves with them.
@MainActor
final class ChatModel: ObservableObject {
    enum Mode { case ask, remember, research }

    @Published var turns: [Turn] = []
    @Published var memoryOn = true
    @Published var mode = "camr"  // how answers read memory: camr (notes), rag (text) or off
    @Published var busy = false
    /// What is being typed lives apart from the conversation, so a keystroke redraws the box and not every answer.
    final class Draft: ObservableObject { @Published var text = "" }
    let typing = Draft()
    var draft: String {
        get { typing.text }
        set { typing.text = newValue }
    }
    @Published var reach = ""
    @Published var shelf = "auto"  // where Remember puts a moment: a shelf, or auto (by meaning)
    @Published var shelves: [ShelfInfo] = []
    @Published var thinks = false  // the model is a thinking build
    @Published var reasoning = Prefs.shared.reasoning  // let a thinking model think aloud
    private var job: String?  // the answer being written now, for Stop
    @Published var chats: [(id: String, title: String)] = []

    let engine: Engine
    let weights: WeightsModel
    let tester = PageTester()
    var projectRoot: String?  // the folder the agent works in, for this conversation
    var agentThread: String?
    var agentRun: String?
    var scriptAnswers: [String] = []  // a rehearsal's answers to the agent's questions, in order
    static weak var current: ChatModel?

    init(engine: Engine, weights: WeightsModel) {
        self.engine = engine
        self.weights = weights
        ChatModel.current = self
    }

    func refresh() async {
        guard let st = try? await engine.get("/api/chat/state") else { return }
        if let on = st["on"] as? Bool {
            memoryOn = on
            if !on { mode = "off" } else if mode == "off" { mode = "camr" }
            if !weights.answering { weights.mode = mode }
        }
        thinks = (st.dict("model")?["thinks"] as? Bool) ?? false
        let reaches = st.list("reaches")
        let rooms = reaches.compactMap { $0.num("rooms") }.reduce(0, +)
        if rooms > 0 { weights.rooms = Int(rooms) }
        reach = reaches.first(where: { ($0["written"] as? Bool) == true })?.str("label") ?? ""
        shelves = st.list("shelves").map {
            ShelfInfo(name: $0.str("name") ?? "", label: $0.str("label") ?? "", reach: $0.str("reach") ?? "",
                      notes: Int($0.num("rooms") ?? 0), moments: Int($0.num("moments") ?? 0))
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

    // -- the shelves are the user's: make, rename, empty and remove them

    enum ShelfAsk: Identifiable {
        case add, rename(ShelfInfo), empty(ShelfInfo), remove(ShelfInfo)
        var id: String {
            switch self {
            case .add: return "add"
            case .rename(let s): return "rename-" + s.name
            case .empty(let s): return "empty-" + s.name
            case .remove(let s): return "remove-" + s.name
            }
        }
    }
    @Published var shelfAsk: ShelfAsk?
    @Published var shelfName = ""
    @Published var shelfNotice: String?

    private func changeShelves(_ path: String, _ body: [String: Any], _ done: (([String: Any]) -> String?)? = nil) async {
        guard !busy else { shelfNotice = "Wait for the answer to finish first."; return }
        busy = true
        defer { busy = false }
        do {
            let got = try await engine.post(path, body)
            shelfNotice = done?(got.dict("changed") ?? [:])
            await refresh()
        } catch {
            shelfNotice = error.localizedDescription
        }
    }

    func addShelf(_ label: String) async {
        await changeShelves("/api/shelves/add", ["label": label]) { _ in "Shelf \(label) made." }
    }

    func renameShelf(_ name: String, _ label: String) async {
        await changeShelves("/api/shelves/rename", ["name": name, "label": label]) { _ in "Renamed to \(label)." }
    }

    func emptyShelf(_ name: String) async {
        await changeShelves("/api/shelves/empty", ["name": name]) { got in
            got.str("put_away") == nil ? "That shelf had nothing on it." : "Shelf emptied. Its notes were moved to the removed folder, not deleted."
        }
    }

    func removeShelf(_ name: String) async {
        await changeShelves("/api/shelves/remove", ["name": name]) { got in
            got.str("put_away") == nil ? "Shelf removed." : "Shelf removed. Its notes were moved to the removed folder, not deleted."
        }
    }

    func pick(shelf name: String) async {
        shelf = name
        _ = try? await engine.post("/api/chat/settings", ["shelf": name])
    }

    func setMemory(_ on: Bool) async { await setMode(on ? "camr" : "off") }

    /// CAMR, RAG or Off: how every answer reads memory from now on. Off also keeps nothing new.
    func setMode(_ m: String) async {
        mode = m
        memoryOn = m != "off"
        weights.mode = m
        _ = try? await engine.post("/api/chat/settings", ["on": m != "off"])
        await refresh()
    }

    static func modeName(_ m: String) -> String { m == "rag" ? "RAG" : m == "off" ? "Off" : "CAMR" }

    /// Old callers: remember, or ask.
    func send(remember: Bool) async { await send(remember ? .remember : .ask) }

    func send(_ mode: Mode) async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !busy else { return }
        draft = ""
        busy = true
        defer { busy = false }
        if mode == .ask, let got = try? await engine.post("/api/chat/intent", ["text": text, "project_open": projectRoot != nil]),
           (got["agent"] as? Bool) == true {
            await runAgent(text)
            return
        }
        let label = mode == .remember ? "remember" : mode == .research ? "research online" : ""
        turns.append(Turn(who: .you, text: text, meta: label))
        turns.append(Turn(who: .camr, text: "", memory: memoryOn, pending: true, model: engine.model.name))
        let k = turns.count - 1
        let intent = mode == .remember ? "tell" : mode == .research ? "research" : "chat"
        weights.beginAnswer(mode: intent == "chat" ? self.mode : (memoryOn ? "camr" : "off"))
        do {
            let prefs = Prefs.shared
            var body: [String: Any] = ["text": text, "intent": intent, "shelf": shelf, "thinking": thinks && reasoning,
                                       "turns": prefs.turns, "max_tokens": prefs.maxTokens, "layers": weights.watched]
            if intent == "chat" { body["memory"] = self.mode }
            let job = try await engine.post("/api/chat/message", body)
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
                if !done { try await Task.sleep(nanoseconds: 80_000_000) }
            }
        } catch {
            turns[k].text = error.localizedDescription
            turns[k].failed = true
            turns[k].pending = false
            weights.finish(nil)
        }
        await refresh()
    }

    /// The same question answered three ways, one after another, on the same memory and the same model: CAMR (a
    /// room's notes already read), RAG (the closest moments pasted in as text) and the model alone. Each answer's
    /// numbers are the engine's own measurements. Nothing is learned from them.
    func compare() async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !busy else { return }
        draft = ""
        busy = true
        defer { busy = false }
        turns.append(Turn(who: .you, text: text, meta: "compare · CAMR · RAG · Off"))
        var t = Turn(who: .camr, text: "", pending: true, model: engine.model.name)
        t.runs = ["camr", "rag", "off"].map { Run(mode: $0) }
        turns.append(t)
        let k = turns.count - 1
        let prefs = Prefs.shared
        for i in 0..<3 {
            let m = turns[k].runs[i].mode
            turns[k].runs[i].started = true
            weights.beginAnswer(mode: m)
            do {
                let job = try await engine.post("/api/chat/message", [
                    "text": text, "intent": "chat", "shelf": shelf, "thinking": false, "turns": prefs.turns,
                    "max_tokens": prefs.maxTokens, "memory": m, "compare": true, "layers": weights.watched])
                guard let id = job.str("id") else { throw Engine.Failure(message: "no job id") }
                self.job = id
                var next = 0
                var done = false
                while !done {
                    let got = try await engine.get("/api/live?id=\(id)&from=\(next)")
                    for e in got.list("events") { handleRun(e, at: k, i) }
                    next = Int(got.num("next") ?? Double(next))
                    done = (got["done"] as? Bool) ?? false
                    if !done { try await Task.sleep(nanoseconds: 80_000_000) }
                }
                self.job = nil
            } catch {
                self.job = nil
                turns[k].runs[i].text = error.localizedDescription
                turns[k].runs[i].failed = true
                turns[k].runs[i].pending = false
                weights.finish(nil)
            }
            try? await Task.sleep(nanoseconds: 400_000_000)  // the weights view settles between answers
        }
        turns[k].pending = false
        await refresh()
        await loadChats()
    }

    private func handleRun(_ e: [String: Any], at k: Int, _ i: Int) {
        switch e.str("kind") {
        case "room": weights.roomEvent(e)
        case "chunks": weights.chunksEvent(e)
        case "prefill": weights.prefillEvent(e)
        case "token":
            turns[k].runs[i].text += e.str("text") ?? ""
            weights.token(e)
        case "read": weights.layersEvent(e["layers"] as? [[Double]], learn: false)
        case "done":
            turns[k].runs[i].pending = false
            if let err = e.str("error") {
                turns[k].runs[i].text = err
                turns[k].runs[i].failed = true
                weights.finish(nil)
                return
            }
            turns[k].runs[i].text = (e.str("reply") ?? turns[k].runs[i].text).trimmingCharacters(in: .whitespacesAndNewlines)
            if let p = e.dict("pipeline") { turns[k].runs[i].pipe = Measured(p, shelves: shelves) }
            weights.finish(e.dict("metric"))
        default:
            break
        }
    }

    /// Stop the answer being written: the model ends at its next word.
    func stop() async {
        if let run = agentRun {
            _ = try? await engine.post("/api/code/stop", ["run": run])
            return
        }
        guard let id = job else { return }
        _ = try? await engine.post("/api/live/stop", ["id": id])
    }

    /// A new conversation: the turns start again; memory keeps all it learned.
    func newChat() async {
        guard !busy else { return }
        turns = []
        projectRoot = nil
        agentThread = nil
        PreviewCenter.shared.close()
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
                // an image, a video's frames or a scanned page: read here with the Mac's own text recognition, off
                // the main thread; the engine is sent the words (it loads no vision model)
                let t0 = Date()
                let read = await Task.detached(priority: .userInitiated) { await OCR.read(url) }.value
                let ocr = Date().timeIntervalSince(t0)
                var body: [String: Any] = ["path": url.path, "shelf": shelf]
                if let read { body["read"] = read }
                let got = try await engine.post("/api/chat/attach", body)
                let n = Int(got.num("moments") ?? 0)
                let on = shelves.first(where: { $0.name == got.str("shelf") })?.label
                turns[k].text = "Read \(url.lastPathComponent): \(n) piece\(n == 1 ? "" : "s") kept" + (on.map { " on the \($0) shelf." } ?? ".")
                if read != nil {
                    turns[k].meta = String(format: "read on this Mac with on-device OCR in %.2f s", ocr)
                }
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
        case "chunks":
            weights.chunksEvent(e)
        case "prefill":
            weights.prefillEvent(e)
        case "token":
            stream(e.str("text") ?? "", at: k)
            weights.token(e)
        case "read":
            weights.layersEvent(e["layers"] as? [[Double]], learn: false)
        case "done":
            turns[k].pending = false
            if let p = e.dict("pipeline") { turns[k].pipe = Measured(p, shelves: shelves) }
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
            if let c = e.dict("check") {
                turns[k].checked = Int(c.num("checked") ?? 0)
                turns[k].unbacked = (c["invented"] as? [String]) ?? []
            }
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
                let how = turns[k].pipe.map { ChatModel.modeName($0.mode) } ?? ""
                switch turns[k].route {
                case "memory": parts.append("from memory · \(how)")
                case "web": parts.append("from the web")
                case "general": parts.append("from the model")
                default: break
                }
                if let f = m?.num("first_word_s") ?? e.num("wait_s") { parts.append("first word \(secondsText(f))") }
                if let p = turns[k].pipe {
                    parts.append("\(p.prefill) tokens read as text")
                    if p.notes > 0 { parts.append("\(p.notes) as notes") }
                    if p.mode == "rag", turns[k].route == "memory" { parts.append(p.source) }
                }
                if !turns[k].meta.isEmpty, turns[k].pipe?.mode != "rag" { parts.append(turns[k].meta) }
                if turns[k].pipe?.mode == "off" || turns[k].memory == false { parts.append("memory off") }
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

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 18) {
                        if chat.turns.isEmpty { empty }
                        ForEach(chat.turns) { t in TurnView(turn: t).equatable().id(t.id) }
                    }
                    .padding(.horizontal, 32)
                    .padding(.vertical, 28)
                    .frame(maxWidth: 1100, alignment: .leading)
                    .frame(maxWidth: .infinity)
                }
                .onChange(of: chat.turns.count) { _, n in  // once per message: yours at the top, the answer below
                    guard n >= 2 else { return }
                    withAnimation(.easeOut(duration: 0.25)) { proxy.scrollTo(chat.turns[n - 2].id, anchor: .top) }
                }
            }
            Composer(chat: chat, typing: chat.typing, engine: engine)
            ModelBand(w: chat.weights)
                .padding(.horizontal, 32).padding(.bottom, 10)
                .frame(maxWidth: 1100)
                .frame(maxWidth: .infinity)
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
            Text("Memory questions are answered from a room of notes the model has already read. Compare asks the same question three ways: CAMR, a conventional RAG pipeline over the same memory, and the model alone.")
                .font(Theme.ui(14)).foregroundStyle(Theme.dim).frame(maxWidth: 560, alignment: .leading)
            VStack(alignment: .leading, spacing: 8) {
                suggestion("Who is the landlord of the Karen branch?", "compare CAMR · RAG · Off", compare: true)
                suggestion("What is the number plate of Kitengela Ventures' delivery truck?", "from memory")
                suggestion("Write a Python function that groups orders by customer and totals them.", "code, in the chat")
                suggestion("Build a one-page café website in HTML and CSS.", "code, in the chat")
            }
            .padding(.top, 12)
        }
        .padding(.top, 60)
    }

    private func suggestion(_ text: String, _ how: String, compare: Bool = false) -> some View {
        Button {
            chat.draft = text
            Task { if compare { await chat.compare() } else { await chat.send(.ask) } }
        } label: {
            HStack(spacing: 10) {
                Image(systemName: compare ? "rectangle.split.3x1" : "arrow.up.right").font(.system(size: 11))
                    .foregroundStyle(compare ? Theme.memory : Theme.model)
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

}

/// The box you type in, on its own: typing here redraws this and nothing else.
struct Composer: View {
    @ObservedObject var chat: ChatModel
    @ObservedObject var typing: ChatModel.Draft
    @ObservedObject var engine: Engine
    @FocusState private var focused: Bool

    var body: some View {
        VStack(spacing: 8) {
            TextField(engine.phase == .ready ? "Ask anything, or tell it to build something…"
                          : "Loading the model…", text: $typing.text, axis: .vertical)
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
            HStack(spacing: 8) {
                Button { chat.attach() } label: { Image(systemName: "paperclip").font(.system(size: 15, weight: .semibold)) }
                    .buttonStyle(.plain).foregroundStyle(Theme.dim)
                    .help("Read a PDF, image, video, text or Markdown file into memory (images on this Mac, with on-device OCR)")
                Spacer()
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
                Button { Task { await chat.compare() } } label: {
                    Label("Compare", systemImage: "rectangle.split.3x1").labelStyle(.titleAndIcon)
                }
                .buttonStyle(Pill(color: Theme.text.opacity(0.85)))
                .keyboardShortcut(.return, modifiers: .option)
                .help("Ask with CAMR, RAG and no memory, one after another, and show them side by side (⌥↩)")
                .disabled(engine.phase != .ready || chat.busy)
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
                Text("↩ ask · ⌥↩ compare · ⌘↩ remember · ⇧⌘↩ research · memory: \(ChatModel.modeName(chat.mode))")
                    .font(Theme.mono(10)).foregroundStyle(Theme.faint)
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
        .frame(maxWidth: 1100)
        .frame(maxWidth: .infinity)
        .background(Theme.ink)
        .onAppear { focused = true }
    }
}

struct TurnView: View, Equatable {
    let turn: Turn

    /// An answer already written is not parsed again when another one changes.
    static func == (a: TurnView, b: TurnView) -> Bool {
        let x = a.turn, y = b.turn
        return x.id == y.id && x.pending == y.pending && x.failed == y.failed && x.text == y.text
            && x.thinking == y.thinking && x.meta == y.meta && x.route == y.route && x.model == y.model
            && x.source?.url == y.source?.url && x.thinkEnd == y.thinkEnd && x.runs.count == y.runs.count && x.unbacked == y.unbacked && x.checked == y.checked && x.agentRev == y.agentRev
            && zip(x.runs, y.runs).allSatisfy {
                $0.text == $1.text && $0.pending == $1.pending && $0.started == $1.started && $0.failed == $1.failed
                    && $0.pipe?.firstWord == $1.pipe?.firstWord && $0.pipe?.prefill == $1.pipe?.prefill
            }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Text(turn.who == .you ? "YOU" : turn.runs.isEmpty ? "CAMR" : "SAME QUESTION · SAME MODEL · SAME MEMORY")
                    .font(Theme.mono(10, .semibold))
                    .foregroundStyle(turn.who == .you || !turn.runs.isEmpty ? Theme.dim : (turn.route == "memory" ? Theme.memory : Theme.model))
                if turn.pending && turn.runs.isEmpty { ProgressView().controlSize(.mini) }
                if !turn.meta.isEmpty && turn.who == .you {
                    Text(turn.meta).font(Theme.mono(10)).foregroundStyle(Theme.memory.opacity(0.8))
                }
            }
            if !turn.runs.isEmpty {
                CompareView(runs: turn.runs)
            } else if let agent = turn.agent {
                AgentCard(agent: agent, pending: turn.pending)
                if !turn.text.isEmpty { AnswerText(text: turn.text, failed: turn.failed) }
                if !turn.pending, !agent.files.isEmpty {
                    Text("Made: " + agent.files.joined(separator: ", ")).font(Theme.mono(10)).foregroundStyle(Theme.faint)
                }
            } else {
                answer
            }
        }
    }

    @ViewBuilder private var answer: some View {
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
            AnswerText(text: turn.text.isEmpty && turn.pending ? "…" : turn.text, failed: turn.failed)
        }
        if let s = turn.source, let url = URL(string: s.url) {
            Link(destination: url) {
                Label("Source: \(s.title)", systemImage: "globe").font(Theme.mono(10))
            }
            .foregroundStyle(Theme.memory)
        }
        if turn.who == .camr, !turn.pending, turn.checked > 0 {
            if turn.unbacked.isEmpty {
                Label("\(turn.checked) fact\(turn.checked == 1 ? "" : "s") found in your memory", systemImage: "checkmark.seal")
                    .font(Theme.mono(10)).foregroundStyle(Theme.memory)
            } else {
                Label("Not in your memory, so the model may have made these up: " + turn.unbacked.joined(separator: " · "),
                      systemImage: "exclamationmark.triangle")
                    .font(Theme.mono(10)).foregroundStyle(Theme.error)
                    .fixedSize(horizontal: false, vertical: true)
            }
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
}

/// The three answers of a comparison, side by side, each with what the engine measured for it, and bars on one
/// scale so the difference is seen at a glance.
struct CompareView: View {
    let runs: [Run]

    var body: some View {
        let maxFirst = max(0.05, runs.compactMap { $0.pipe?.firstWord }.max() ?? 0)
        let maxText = max(1, runs.compactMap { $0.pipe?.prefill }.max() ?? 0)
        HStack(alignment: .top, spacing: 12) {
            ForEach(runs) { r in card(r, maxFirst, Double(maxText)) }
        }
    }

    private func color(_ m: String) -> Color { m == "off" ? Theme.faint : Theme.memory }

    private func title(_ m: String) -> String {
        switch m {
        case "camr": return "CAMR · notes"
        case "rag": return "RAG · text"
        default: return "OFF · no memory"
        }
    }

    private func subtitle(_ m: String) -> String {
        switch m {
        case "camr": return "one room laid on the desk already read, its closest moments as words"
        case "rag": return "the 8 closest moments pasted in as text, read again every question"
        default: return "the model alone"
        }
    }

    private func card(_ r: Run, _ maxFirst: Double, _ maxText: Double) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 7) {
                Group {
                    if r.mode == "camr" {
                        RoundedRectangle(cornerRadius: 2).fill(Theme.memory)
                    } else if r.mode == "rag" {
                        RoundedRectangle(cornerRadius: 2).stroke(Theme.memory, lineWidth: 1.5)
                    } else {
                        RoundedRectangle(cornerRadius: 2).fill(Theme.faint)
                    }
                }
                .frame(width: 11, height: 11)
                Text(title(r.mode)).font(Theme.mono(13, .bold)).foregroundStyle(color(r.mode))
                Spacer()
                if r.pending && r.started { ProgressView().controlSize(.mini) }
            }
            Text(subtitle(r.mode)).font(Theme.ui(11)).foregroundStyle(Theme.faint)
                .fixedSize(horizontal: false, vertical: true)
            VStack(alignment: .leading, spacing: 7) {
                bar("first word", r.pipe?.firstWord.map { secondsText($0) } ?? "—",
                    (r.pipe?.firstWord ?? 0) / maxFirst, filled: true, r.mode)
                bar("read as text", r.pipe.map { "\($0.prefill) tokens" } ?? "—",
                    Double(r.pipe?.prefill ?? 0) / maxText, filled: false, r.mode)
                stat("memory as text", r.pipe.map { "\($0.memoryText) tokens" } ?? "—")
                stat("notes already read", r.pipe.map { $0.notes > 0 ? "\($0.notes) tokens · \(bytesText($0.notesBytes))" : "none" } ?? "—")
                stat("memory in view", r.pipe.map { $0.notes + $0.memoryText > 0 ? "\($0.notes + $0.memoryText) tokens" : "none" } ?? "—")
                stat("retrieval", r.pipe?.retrievalMs.map { String(format: "%.0f ms", $0) } ?? "—")
                if let p = r.pipe {
                    Text(p.source).font(Theme.mono(10)).foregroundStyle(r.mode == "off" ? Theme.faint : Theme.memory.opacity(0.85))
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(10)
            .background(RoundedRectangle(cornerRadius: 8).fill(Color.black.opacity(0.55)))
            if r.started || !r.text.isEmpty {
                AnswerText(text: r.text.isEmpty ? (r.pending ? "…" : "") : r.text, failed: r.failed, size: 14)
            } else {
                Text("waits its turn").font(Theme.mono(10)).foregroundStyle(Theme.faint)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .background(RoundedRectangle(cornerRadius: 12).fill(Theme.panel))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(r.mode == "off" ? Theme.line : Theme.memory.opacity(0.3)))
    }

    private func bar(_ name: String, _ value: String, _ share: Double, filled: Bool, _ mode: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text(name).font(Theme.mono(10)).foregroundStyle(Theme.dim)
                Spacer()
                Text(value).font(Theme.mono(13, .semibold)).foregroundStyle(Theme.text)
            }
            GeometryReader { g in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.white.opacity(0.06))
                    Capsule().fill(filled ? (mode == "off" ? Theme.faint : Theme.memory) : Color.white.opacity(0.7))
                        .frame(width: max(2, g.size.width * CGFloat(min(1, max(0, share)))))
                }
            }
            .frame(height: 6)
        }
    }

    private func stat(_ name: String, _ value: String) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(name).font(Theme.mono(10)).foregroundStyle(Theme.dim)
            Spacer(minLength: 8)
            Text(value).font(Theme.mono(10)).foregroundStyle(Theme.text).multilineTextAlignment(.trailing)
        }
    }
}

/// An answer as the model wrote it: prose with Markdown (bold, inline code, links, headings, bullets, readable
/// maths) and fenced code blocks shown as code, never run through Markdown.
struct AnswerText: View {
    let text: String
    var failed = false
    var size: CGFloat = 15

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(Array(AnswerText.blocks(text).enumerated()), id: \.offset) { _, b in
                if b.code {
                    CodeBlock(code: b.text, language: b.language)
                } else {
                    Text(rendered(b.text))
                        .font(Theme.ui(size))
                        .foregroundStyle(failed ? Theme.error : Theme.text)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }

    /// The answer split at its fenced code blocks: prose and code in turn. A fence still open (the answer is being
    /// written) is code up to the end. A fence's first line names its language.
    static func blocks(_ text: String) -> [(code: Bool, language: String, text: String)] {
        var out: [(Bool, String, String)] = []
        var prose: [Substring] = []
        var code: [Substring] = []
        var language = ""
        var inside = false
        func flushProse() {
            let p = prose.joined(separator: "\n").trimmingCharacters(in: .newlines)
            if !p.trimmingCharacters(in: .whitespaces).isEmpty { out.append((false, "", p)) }
            prose = []
        }
        for line in text.split(separator: "\n", omittingEmptySubsequences: false) {
            let t = line.trimmingCharacters(in: .whitespaces)
            if t.hasPrefix("```") {
                if inside {
                    out.append((true, language, code.joined(separator: "\n")))
                    code = []
                    inside = false
                } else {
                    flushProse()
                    language = String(t.dropFirst(3)).trimmingCharacters(in: .whitespaces)
                    inside = true
                }
            } else if inside {
                code.append(line)
            } else {
                prose.append(line)
            }
        }
        if inside { out.append((true, language, code.joined(separator: "\n"))) }
        flushProse()
        return out.isEmpty ? [(false, "", text)] : out
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
            if run.inlinePresentationIntent?.contains(.code) == true {  // `inline code`: monospaced, amber-tinted
                out[run.range].font = Theme.mono(13)
                out[run.range].foregroundColor = Color(red: 1.0, green: 0.82, blue: 0.6)
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

/// A code block in an answer: its language named, monospaced on its own dark panel, scrolling sideways (never
/// wrapped), with a Copy button that says when it copied.
struct CodeBlock: View {
    let code: String
    var language = ""
    @StateObject private var copied = Flag()

    final class Flag: ObservableObject { @Published var on = false }

    private var isPage: Bool {
        language.lowercased().hasPrefix("htm") || code.lowercased().contains("<html") || code.lowercased().contains("<!doctype html")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 8) {
                Text(language.isEmpty ? "code" : language.lowercased()).font(Theme.mono(11, .semibold))
                    .foregroundStyle(Theme.dim)
                Text("\(code.split(separator: "\n", omittingEmptySubsequences: false).count) lines")
                    .font(Theme.mono(10)).foregroundStyle(Theme.faint)
                Spacer()
                if isPage {
                    Button { PreviewCenter.shared.show(code: code) } label: {
                        Label("Preview", systemImage: "play.rectangle").font(Theme.mono(11))
                    }
                    .buttonStyle(.plain).foregroundStyle(Theme.memory)
                    .help("Open this page in the built-in browser")
                }
                Button {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(code, forType: .string)
                    copied.on = true
                    let flag = copied
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { flag.on = false }
                } label: {
                    Label(copied.on ? "Copied" : "Copy", systemImage: copied.on ? "checkmark" : "doc.on.doc")
                        .font(Theme.mono(11))
                }
                .buttonStyle(.plain).foregroundStyle(copied.on ? Theme.memory : Theme.dim)
            }
            .padding(.horizontal, 12).padding(.vertical, 7)
            .background(Color.white.opacity(0.045))
            Rectangle().fill(Theme.line).frame(height: 1)
            ScrollView(.horizontal, showsIndicators: true) {
                Text(code.isEmpty ? " " : code).font(Theme.mono(12.5)).foregroundStyle(Color.white.opacity(0.88))
                    .lineSpacing(2)
                    .textSelection(.enabled)
                    .fixedSize(horizontal: true, vertical: true)
                    .padding(.horizontal, 14).padding(.vertical, 12)
            }
        }
        .background(RoundedRectangle(cornerRadius: 9).fill(Color(red: 0.035, green: 0.04, blue: 0.055)))
        .clipShape(RoundedRectangle(cornerRadius: 9))
        .overlay(RoundedRectangle(cornerRadius: 9).stroke(Color.white.opacity(0.1)))
    }
}
