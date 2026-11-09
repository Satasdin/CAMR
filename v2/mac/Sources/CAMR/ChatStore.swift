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
    var keptOn = ""          // the shelf a told message was kept on
    var image: URL?          // a photo you added
    var sourceTitle = ""     // a web page the answer read first
    var sourceURL: URL?
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
    var kept = false      // a memory was just put on this shelf
    var takenIDs: Set<Int> = []  // exactly which memories (by place on the shelf), once the engine says
    var usedIDs: Set<Int> = []

    var spineCount: Int { min(Shelf.shown, memories) }
}

/// One answer's trip through memory, for the Memory view: what was asked, and each step with its measured time.
struct Run: Equatable {
    var question = ""
    var at = Date()
    var steps: [(name: String, value: String, detail: String)] = []
    var deskTokens = 0
    var memoryTokens = 0

    static func == (a: Run, b: Run) -> Bool { a.question == b.question && a.at == b.at && a.steps.count == b.steps.count }
}

@MainActor
final class ChatStore: ObservableObject {
    @Published var lastRun: Run?
    @Published var chats: [(id: String, title: String)] = []
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

    private var sorting = false

    func refresh() async {
        if !sorting {  // what you tell CAMR is sorted onto the shelf it belongs to (Personal, Projects, …)
            sorting = (try? await engine.post("/api/chat/settings", ["shelf": "auto"])) != nil
        }
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
            if let o = old[name] { sh.taken = o.taken; sh.used = o.used; sh.waking = o.waking; sh.takenAt = o.takenAt; sh.kept = o.kept }
            return sh
        }
    }

    /// A chat's title as a person would name it: "(attached 1794-matatu.jpg)" becomes "Photo: matatu".
    static func cleanTitle(_ raw: String) -> String {
        var t = raw.trimmingCharacters(in: .whitespaces)
        if t.hasPrefix("(attached") {
            t = t.replacingOccurrences(of: "(attached", with: "").trimmingCharacters(in: CharacterSet(charactersIn: " )"))
            t = t.replacingOccurrences(of: #"^\d+-"#, with: "", options: .regularExpression)
            t = "Photo: " + ((t as NSString).deletingPathExtension)
        }
        return t.isEmpty ? "Untitled chat" : t
    }

    func loadChats() async {
        guard let r = try? await engine.get("/api/chats") else { return }
        chats = (r["chats"] as? [JSON] ?? []).compactMap { c in
            guard let id = c["id"] as? String else { return nil }
            return (id, ChatStore.cleanTitle(c["title"] as? String ?? ""))
        }
    }

    /// Go back to a saved conversation: its turns come back into the chat and the model reads them again.
    func open(_ id: String) async {
        guard !busy, let r = try? await engine.post("/api/chats/open", ["id": id]) else { return }
        messages = (r["turns"] as? [JSON] ?? []).compactMap { t in
            let who = t["who"] as? String
            let text = (t["text"] as? String) ?? (t["reply"] as? String) ?? ""
            guard !text.isEmpty else { return nil }
            return Message(role: who == "you" ? .you : .camr, text: text)
        }
        title = chats.first { $0.id == id }?.title ?? "Chat"
        clearDesk()
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
        if messages.isEmpty { title = text }  // the toolbar shortens it to fit, with an ellipsis
        messages.append(Message(role: .you, text: text))
        messages.append(Message(role: .camr, text: "", pending: true))
        busy = true
        status = "Looking through your memory…"
        lastRun = Run(question: text)
        clearDesk()
        Task {
            do {
                let r = try await engine.post("/api/chat/message", ["text": text, "intent": "auto", "layers": false])
                guard let id = r["id"] as? String else { throw EngineError.badReply }
                job = id
                await follow(id)
            } catch {
                finish(error: error.localizedDescription)
            }
        }
    }

    /// Add a file to memory: copied into CAMR's inbox, an image read on this Mac, then sorted onto a shelf.
    func attach(_ url: URL) {
        guard !busy else { return }
        let isImage = Attach.isImage(url)
        if messages.isEmpty { title = url.deletingPathExtension().lastPathComponent }
        var mine = Message(role: .you, text: "Added \(url.lastPathComponent)")
        if isImage { mine.image = url }
        messages.append(mine)
        messages.append(Message(role: .camr, text: "", pending: true))
        busy = true
        status = isImage ? "Reading the photo on this Mac…" : "Reading the file…"
        clearDesk()
        Task {
            do {
                let copy = try Attach.intoInbox(url)
                var body: JSON = ["path": copy.path, "shelf": "auto"]
                if isImage {
                    let given = await Task.detached { Attach.read(image: copy) }.value
                    body["read"] = given
                }
                status = "Putting it on a shelf…"
                let r = try await engine.post("/api/chat/attach", body)
                let n = r["moments"] as? Int ?? 0
                let reach = r["reach"] as? String ?? ""
                let label = shelves.first { $0.reach == reach }?.label ?? (r["shelf"] as? String ?? "a shelf")
                if let i = shelves.firstIndex(where: { $0.reach == reach }) { shelves[i].kept = true }
                if var last = messages.last, last.role == .camr {
                    last.text = n == 0 ? "I couldn't find anything to keep in \(url.lastPathComponent)."
                        : "Kept \(n) \(n == 1 ? "piece" : "pieces") from \(url.lastPathComponent)."
                    last.keptOn = n > 0 ? label : ""
                    last.pending = false
                    messages[messages.count - 1] = last
                }
                busy = false
                status = ""
                await refresh()
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
        for i in shelves.indices { shelves[i].taken = 0; shelves[i].used = 0; shelves[i].waking = false; shelves[i].kept = false; shelves[i].takenIDs = []; shelves[i].usedIDs = [] }
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
                case "used":
                    usedUp(e)
                case "near":
                    nearBy(e)
                case "prefill":
                    deskTokens = e["tokens"] as? Int ?? deskTokens
                    deskMemoryTokens = e["memory"] as? Int ?? deskMemoryTokens
                    lastRun?.deskTokens = deskTokens
                    lastRun?.memoryTokens = deskMemoryTokens
                    lastRun?.steps.append(("Lay the desk", "\(deskTokens.formatted()) tokens",
                                           "\(deskMemoryTokens.formatted()) of them from memory; only what's needed, not whole shelves"))
                    status = "Reading what it took…"
                case "token":
                    if firstWord == nil {
                        firstWord = Date().timeIntervalSince(started)
                        lastRun?.steps.append(("Answer", String(format: "first word %.2f s", firstWord ?? 0),
                                               "the model starts writing"))
                    }
                    status = ""
                    if var last = messages.last, last.role == .camr {
                        last.text += e["text"] as? String ?? ""
                        messages[messages.count - 1] = last
                    }
                case "done":
                    if let err = e["error"] as? String { finish(error: err); return }
                    if e["intent"] as? String == "tell" { kept(e) }
                    if let src = e["source"] as? JSON, let u = src["url"] as? String, var last = messages.last, last.role == .camr {
                        last.sourceTitle = src["title"] as? String ?? u
                        last.sourceURL = URL(string: u)
                        messages[messages.count - 1] = last
                    }
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
        let parts = e["ms"] as? JSON ?? [:]
        let choose = parts["choose"] as? Double ?? 0
        lastRun?.steps.append(("Find", String(format: "%.0f ms", choose), "every memory searched, line by line"))
        if asleep {
            let fetch = parts["fetch"] as? Double ?? 0
            lastRun?.steps.append(fetch > 0.5
                ? ("Wake", String(format: "%.0f ms", fetch), "\(shelves[i].label) was asleep: its notes read back from the SSD")
                : ("Read asleep", "as words", "\(shelves[i].label) is asleep: its memories read as words, nothing loaded"))
        }
        let bytes = e["bytes"] as? Int ?? 0
        lastRun?.steps.append(("Take", "\(max(1, closest)) from \(shelves[i].label)",
                               bytes > 0 ? String(format: "%.1f MB of room read", Double(bytes) / 1e6) : "lifted onto the desk"))
        let when = ms.map { String(format: " · %.0f ms", $0) } ?? ""
        status = asleep ? "Waking your \(shelves[i].label) shelf\(when)…" : "Taking \(max(1, closest)) from \(shelves[i].label)\(when)…"
        if var last = messages.last, last.role == .camr, !last.used.contains(shelves[i].label) {
            last.used.append(shelves[i].label)
            messages[messages.count - 1] = last
        }
    }

    /// A "used" event: of what was taken from a shelf, what the answer actually drew on. The shelf is awake now.
    private func usedUp(_ e: JSON) {
        let reach = e["reach"] as? String ?? ""
        guard let i = shelves.firstIndex(where: { $0.reach == reach }) else { return }
        let taken = (e["closest"] as? [Any])?.count ?? shelves[i].taken
        shelves[i].waking = false
        shelves[i].taken = max(shelves[i].taken, taken)
        shelves[i].used = (e["used"] as? [Any])?.count ?? 0
        shelves[i].takenIDs = Set((e["closest"] as? [Int]) ?? [])
        shelves[i].usedIDs = Set((e["used"] as? [Int]) ?? [])
        lastRun?.steps.append(("Used", "\(shelves[i].used) of \(taken)",
                               "drew at least a tenth of the model's attention"))
    }

    /// A "near" event: the closest memory of each other shelf, when nearly as close, read as words too.
    private func nearBy(_ e: JSON) {
        for item in e["items"] as? [JSON] ?? [] {
            guard let reach = item["reach"] as? String, let mid = item["moment"] as? Int,
                  let i = shelves.firstIndex(where: { $0.reach == reach }) else { continue }
            shelves[i].takenIDs.insert(mid)
            shelves[i].taken = max(shelves[i].taken, shelves[i].takenIDs.count)
            if var last = messages.last, last.role == .camr, !last.used.contains(shelves[i].label) {
                last.used.append(shelves[i].label)
                messages[messages.count - 1] = last
            }
            lastRun?.steps.append(("Take", "1 from \(shelves[i].label)", "the closest memory on another shelf, read as words"))
        }
    }

    /// A told message was kept: its shelf gets a new spine, and the reply says where it went.
    private func kept(_ e: JSON) {
        let reach = e["reach"] as? String ?? ""
        guard e["kept"] as? Bool == true, let i = shelves.firstIndex(where: { $0.reach == reach }) else { return }
        shelves[i].kept = true
        shelves[i].memories += 1
        lastRun?.steps.append(("Keep", "on \(shelves[i].label)", "a new memory, sorted onto the shelf it belongs to"))
        if var last = messages.last, last.role == .camr {
            last.keptOn = shelves[i].label
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
        Task { await refresh(); await loadChats() }
    }
}
