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
}

/// One chat with the engine: each message is started at once and its live events are read as they come, so the
/// words appear as they are written and the weights view moves with them.
@MainActor
final class ChatModel: ObservableObject {
    @Published var turns: [Turn] = []
    @Published var memoryOn = true
    @Published var busy = false
    @Published var draft = ""
    @Published var reach = ""

    let engine: Engine
    let weights: WeightsModel

    init(engine: Engine, weights: WeightsModel) {
        self.engine = engine
        self.weights = weights
    }

    func refresh() async {
        guard let st = try? await engine.get("/api/chat/state") else { return }
        if let on = st["on"] as? Bool { memoryOn = on; weights.memoryOn = on }
        let reaches = st.list("reaches")
        let rooms = reaches.compactMap { $0.num("rooms") }.reduce(0, +)
        if rooms > 0 { weights.rooms = Int(rooms) }
        reach = reaches.first(where: { ($0["written"] as? Bool) == true })?.str("label") ?? ""
    }

    func setMemory(_ on: Bool) async {
        memoryOn = on
        weights.memoryOn = on
        _ = try? await engine.post("/api/chat/settings", ["on": on])
        await refresh()
    }

    /// Ask (the model answers from memory) or remember (the moment is kept in memory).
    func send(remember: Bool) async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !busy else { return }
        draft = ""
        busy = true
        defer { busy = false }
        turns.append(Turn(who: .you, text: text, meta: remember ? "remember" : ""))
        turns.append(Turn(who: .camr, text: "", memory: memoryOn, pending: true))
        let k = turns.count - 1
        weights.beginAnswer(memory: memoryOn)
        do {
            let job = try await engine.post("/api/chat/message", ["text": text, "intent": remember ? "tell" : "ask"])
            guard let id = job.str("id") else { throw Engine.Failure(message: "no job id") }
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

    private func handle(_ e: [String: Any], at k: Int) {
        switch e.str("kind") {
        case "room":
            weights.roomEvent(e)
            if let r = e.num("room") {
                let tier = e.str("tier") ?? ""
                turns[k].meta = "room \(Int(r)) · " + (tier == "ssd" ? "read from the SSD" : tier == "ram" ? "hot in RAM" : "read as words")
            }
        case "token":
            turns[k].text += e.str("text") ?? ""
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
            let m = e.dict("metric")
            weights.finish(m)
            var parts: [String] = []
            if e.str("intent") == "tell" {
                parts.append((e["kept"] as? Bool) == true ? "kept in \(e.str("reach") ?? "memory")" : "not kept")
            } else {
                if let f = m?.num("first_word_s") ?? e.num("wait_s") { parts.append("first word \(secondsText(f))") }
                if !turns[k].meta.isEmpty { parts.append(turns[k].meta) }
                if turns[k].memory == false { parts.append("memory off") }
            }
            turns[k].meta = parts.joined(separator: " · ")
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
                .onChange(of: chat.turns.last?.text) { _, _ in
                    if let id = chat.turns.last?.id { proxy.scrollTo(id, anchor: .bottom) }
                }
            }
            composer
        }
        .background(Theme.ink)
    }

    private var empty: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Tell it things. Ask about them later.").font(Theme.ui(26, .semibold)).foregroundStyle(Theme.text)
            Text("Whatever you remember goes into memory on this Mac. Ask with memory on and watch the room it reads flow into the model; switch memory off and the model answers alone.")
                .font(Theme.ui(14)).foregroundStyle(Theme.dim).frame(maxWidth: 520, alignment: .leading)
        }
        .padding(.top, 60)
    }

    private var composer: some View {
        VStack(spacing: 8) {
            HStack(alignment: .bottom, spacing: 10) {
                TextField(engine.phase == .ready ? "Ask, or remember something…" : "Loading the model…",
                          text: $chat.draft, axis: .vertical)
                    .textFieldStyle(.plain)
                    .font(Theme.ui(15))
                    .foregroundStyle(Theme.text)
                    .lineLimit(1...6)
                    .focused($focused)
                    .onSubmit { Task { await chat.send(remember: false) } }
                    .padding(12)
                    .background(RoundedRectangle(cornerRadius: 12).fill(Theme.panel))
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line))
                Button { Task { await chat.send(remember: true) } } label: {
                    Label("Remember", systemImage: "pin").labelStyle(.titleAndIcon)
                }
                .buttonStyle(Pill(color: Theme.memory))
                .keyboardShortcut(.return, modifiers: .command)
                .help("Keep this in memory (⌘↩)")
                Button { Task { await chat.send(remember: false) } } label: {
                    Label("Ask", systemImage: "arrow.up").labelStyle(.titleAndIcon)
                }
                .buttonStyle(Pill(color: Theme.model))
                .help("Ask (↩)")
            }
            .disabled(engine.phase != .ready || chat.busy)
            HStack {
                Text("↩ ask · ⌘↩ remember").font(Theme.mono(10)).foregroundStyle(Theme.faint)
                Spacer()
                if !chat.reach.isEmpty {
                    Text("writes to \(chat.reach)").font(Theme.mono(10)).foregroundStyle(Theme.faint)
                }
            }
        }
        .padding(.horizontal, 32)
        .padding(.vertical, 16)
        .frame(maxWidth: 820)
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
                    .foregroundStyle(turn.who == .you ? Theme.dim : (turn.memory == false ? Theme.model : Theme.memory))
                if turn.pending { ProgressView().controlSize(.mini) }
                if !turn.meta.isEmpty && turn.who == .you {
                    Text(turn.meta).font(Theme.mono(10)).foregroundStyle(Theme.memory.opacity(0.8))
                }
            }
            Text(turn.text.isEmpty && turn.pending ? "…" : turn.text)
                .font(Theme.ui(15))
                .foregroundStyle(turn.failed ? Theme.error : Theme.text)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
            if turn.who == .camr, !turn.meta.isEmpty, !turn.pending {
                Text(turn.meta).font(Theme.mono(10)).foregroundStyle(Theme.faint)
            }
        }
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
