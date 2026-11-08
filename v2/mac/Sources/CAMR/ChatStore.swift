// The chat: messages, the shelves (rooms) the engine keeps, and what happens to them while an answer is written.
//
// A message starts a job (POST /api/chat/message → {id}); the app follows it with GET /api/live?id&from, which
// returns the job's events in order: "room" when memory is read (which shelf, whether it was asleep, how many
// memories were taken), "prefill" when the model starts reading, "token" for each piece of the answer, and "done".

import Foundation
import SwiftUI

struct Message: Identifiable, Equatable {
    enum Role { case you, camr }
    let id = UUID()
    let role: Role
    var text: String
    var pending = false
    var note = ""      // e.g. "first word 0.35 s"
    var used: [String] = []  // shelves this answer took from
    var error = false
}

/// One shelf as the app draws it: a row of spines, one per memory (at most `Shelf.shown`).
struct Shelf: Identifiable, Equatable {
    static let shown = 40
    let id: String        // the engine's shelf name
    var label: String
    var reach: String
    var memories: Int
    var rooms: Int
    var asleep: Bool
    // what is happening to it during the current answer
    var waking = false
    var taken = 0
    var used = 0
    var takenAt: Date?

    var spineCount: Int { max(6, min(Shelf.shown, memories)) }
}

@MainActor
final class ChatStore: ObservableObject {
    @Published var messages: [Message] = []
    @Published var shelves: [Shelf] = []
    @Published var busy = false
    @Published var status = ""          // "Waking your Meetings shelf…"
    @Published var deskTokens = 0
    @Published var deskMemoryTokens = 0
    @Published var window = 32768
    @Published var title = "New chat"

    private let engine: Engine
    private var job: String?

    init(engine: Engine) { self.engine = engine }

    func refresh() async {
        guard let s = try? await engine.get("/api/chat/state") else { return }
        if let model = s["model"] as? JSON, let w = model["window"] as? Int { window = w }
        // what this chat has been told lives in its own reach ("session:…"); the named shelves after it
        var list: [JSON] = []
        if let session = (s["reaches"] as? [JSON])?.first(where: { $0["kind"] as? String == "session" }),
           let label = session["label"] as? String {
            list.append(["name": "this-chat", "label": "This chat", "reach": label,
                         "moments": session["moments"] as? Int ?? 0, "rooms": session["rooms"] as? Int ?? 0])
        }
        list += s["shelves"] as? [JSON] ?? []
        let old = Dictionary(uniqueKeysWithValues: shelves.map { ($0.id, $0) })
        shelves = list.map { j in
            let name = j["name"] as? String ?? "?"
            var sh = Shelf(id: name, label: j["label"] as? String ?? name, reach: j["reach"] as? String ?? "",
                           memories: j["moments"] as? Int ?? 0, rooms: j["rooms"] as? Int ?? 0,
                           asleep: (j["moments"] as? Int ?? 0) == 0)
            if let o = old[name] { sh.taken = o.taken; sh.used = o.used; sh.waking = o.waking; sh.takenAt = o.takenAt }
            return sh
        }
    }

    func newChat() async {
        _ = try? await engine.post("/api/chat/new")
        messages = []
        title = "New chat"
        clearDesk()
    }

    func send(_ raw: String) {
        let text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !busy else { return }
        if messages.isEmpty { title = String(text.prefix(48)) }
        messages.append(Message(role: .you, text: text))
        messages.append(Message(role: .camr, text: "", pending: true))
        busy = true
        status = "Looking through your memory…"
        clearDesk()
        Task {
            do {
                let r = try await engine.post("/api/chat/message", ["text": text, "intent": "chat", "layers": false])
                guard let id = r["id"] as? String else { throw EngineError.badReply }
                job = id
                await follow(id)
            } catch {
                finish(error: error.localizedDescription)
            }
        }
    }

    func stop() {
        guard let id = job else { return }
        Task { _ = try? await engine.post("/api/live/stop", ["id": id]) }
    }

    private func clearDesk() {
        deskTokens = 0
        deskMemoryTokens = 0
        for i in shelves.indices { shelves[i].taken = 0; shelves[i].used = 0; shelves[i].waking = false }
    }

    private func follow(_ id: String) async {
        var from = 0
        let started = Date()
        var firstWord: TimeInterval?
        while true {
            guard let r = try? await engine.get("/api/live", ["id": id, "from": String(from)]) else {
                finish(error: "Lost the engine while answering.")
                return
            }
            for e in r["events"] as? [JSON] ?? [] {
                switch e["kind"] as? String {
                case "room":
                    took(e)
                case "prefill":
                    deskTokens = e["tokens"] as? Int ?? deskTokens
                    deskMemoryTokens = e["memory"] as? Int ?? deskMemoryTokens
                    status = "Reading what it took…"
                case "token":
                    if firstWord == nil { firstWord = Date().timeIntervalSince(started) }
                    status = ""
                    if var last = messages.last, last.role == .camr {
                        last.text += e["text"] as? String ?? ""
                        messages[messages.count - 1] = last
                    }
                case "done":
                    if let err = e["error"] as? String { finish(error: err); return }
                    let reply = e["reply"] as? String
                    let note = firstWord.map { String(format: "first word %.2f s", $0) } ?? ""
                    finish(reply: reply, note: note)
                    return
                default:
                    break
                }
            }
            from = r["next"] as? Int ?? from
            if r["done"] as? Bool == true { finish(reply: nil, note: ""); return }
            try? await Task.sleep(nanoseconds: 120_000_000)
        }
    }

    /// A "room" event: memory was read from one shelf for this answer.
    private func took(_ e: JSON) {
        let reach = e["reach"] as? String ?? ""
        let asleep = e["asleep"] as? Bool ?? false
        let closest = e["closest"] as? Int ?? 0
        guard closest > 0 || e["room"] as? Int != nil else { return }  // nothing in memory yet: nothing taken
        guard let i = shelves.firstIndex(where: { $0.reach == reach }) else { return }
        shelves[i].waking = asleep
        shelves[i].taken = max(1, closest)
        shelves[i].takenAt = Date()
        let ms = (e["ms"] as? JSON)?.values.compactMap { $0 as? Double }.reduce(0, +)
        let when = ms.map { String(format: " · %.0f ms", $0) } ?? ""
        status = asleep ? "Waking your \(shelves[i].label) shelf\(when)…" : "Taking \(max(1, closest)) from \(shelves[i].label)\(when)…"
        if var last = messages.last, last.role == .camr, !last.used.contains(shelves[i].label) {
            last.used.append(shelves[i].label)
            messages[messages.count - 1] = last
        }
    }

    private func finish(reply: String? = nil, note: String = "", error: String? = nil) {
        busy = false
        status = ""
        job = nil
        guard var last = messages.last, last.role == .camr else { return }
        last.pending = false
        if let error {
            last.text = error
            last.error = true
        } else if let reply, !reply.isEmpty {
            last.text = reply  // the engine's final answer: the stream can hold a first draft it then replaced
        }
        last.note = note
        messages[messages.count - 1] = last
        Task { await refresh() }
    }
}
