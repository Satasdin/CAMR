import AppKit
import SwiftUI

/// One thing the agent did, for its card in the conversation.
struct AgentStep: Identifiable {
    let id = UUID()
    let icon: String
    let title: String
    var detail = ""
    var ok = true
    var memory = false  // it read memory (shown in memory's colour)
}

/// Something the agent is waiting for from the person.
struct AgentAsk: Identifiable {
    let id: String
    let kind: String  // question or shell (the app answers a browser's by itself)
    let text: String
}

struct AgentState {
    var steps: [AgentStep] = []
    var writing = ""
    var asks: [AgentAsk] = []
    var state = "starting"
    var project = ""
    var files: [String] = []
    var seconds = 0.0
    var modelSteps = 0
    var lastRead = 0  // tokens the model read for its latest step
    var waited = 0  // times it stopped for the person
    var madeUp: [String] = []  // still on the page, and not in memory
    var untested: String?  // its last test failed, or it changed after it
}

extension ChatModel {
    private func slug(_ task: String) -> String {
        let drop: Set<String> = ["build", "make", "create", "develop", "design", "code", "a", "an", "the", "for", "our", "my", "me",
                                 "small", "simple", "website", "web", "site", "app", "page", "where", "please", "one", "with",
                                 "and", "of", "to", "that", "can", "customer", "application"]
        let words = task.lowercased().split(whereSeparator: { !$0.isLetter && !$0.isNumber }).map(String.init)
        let kept = words.filter { !drop.contains($0) }.prefix(3)
        return kept.isEmpty ? "project" : kept.joined(separator: "-")
    }

    private func openProject(for task: String) async throws -> String {
        if let root = projectRoot { return root }
        let fm = FileManager.default
        let home = ProcessInfo.processInfo.environment["CAMR_PROJECTS"].map { URL(fileURLWithPath: $0) }
            ?? fm.homeDirectoryForCurrentUser.appendingPathComponent("CAMR Projects")
        let base = slug(task)
        var folder = home.appendingPathComponent(base)
        var n = 1
        while fm.fileExists(atPath: folder.path) {
            n += 1
            folder = home.appendingPathComponent("\(base)-\(n)")
        }
        try fm.createDirectory(at: folder, withIntermediateDirectories: true)
        _ = try await engine.post("/api/code/workspace", ["path": folder.path])
        projectRoot = folder.path
        agentThread = nil
        return folder.path
    }

    func readProjectFile(_ path: String) async -> String? {
        let q = path.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? path
        return (try? await engine.get("/api/code/file?path=\(q)"))?.str("text")
    }

    private func loadedPage(_ path: String) async -> (page: String, missing: [String])? {
        guard let html = await readProjectFile(path) else { return nil }
        return await ProjectPage.inline(html) { [weak self] in await self?.readProjectFile($0) }
    }

    private func refreshFiles(at k: Int) async {
        guard let got = try? await engine.get("/api/code/files") else { return }
        let files = got.list("files").filter { ($0["dir"] as? Bool) != true }.compactMap { $0.str("path") }
        turns[k].agent?.files = files
        PreviewCenter.shared.files = files
    }

    /// A request to make files, in the one conversation: the agent works in a project folder of its own, each step a
    /// line on its card, asking when it needs to, and its page opens beside the chat.
    func runAgent(_ task: String) async {
        turns.append(Turn(who: .you, text: task))
        var t = Turn(who: .camr, text: "", memory: memoryOn, pending: true, model: engine.model.name)
        t.agent = AgentState()
        turns.append(t)
        let k = turns.count - 1
        weights.beginAnswer(mode: mode)
        let started = Date()
        do {
            let root = try await openProject(for: task)
            turns[k].agent?.project = root
            bump(k)
            PreviewCenter.shared.readFile = { [weak self] in await self?.readProjectFile($0) }
            if agentThread == nil {
                agentThread = try await engine.post("/api/code/thread", ["title": String(task.prefix(60))]).str("id")
            }
            let earlier = turns[..<max(0, k - 1)].suffix(6).compactMap { x -> String? in
                x.who == .you ? "The user said: \(x.text.prefix(600))" : nil
            }
            let r = try await engine.post("/api/code/run", [
                "thread": agentThread ?? "", "task": task, "memory": mode != "off", "window": true, "max_steps": 30,
                "context": Array(earlier)])
            guard let id = r.str("id") else { throw Engine.Failure(message: "no run") }
            agentRun = id
            defer { agentRun = nil }
            var turnsSeen = 0
            var liveNext = 0
            var handled = Set<String>()
            var state = r.str("state") ?? ""
            while !["done", "stopped", "failed"].contains(state) {
                let s = try await engine.get("/api/code/run?id=\(id)&turns=\(turnsSeen)")
                state = s.str("state") ?? state
                turnsSeen = Int(s.num("turns_total") ?? Double(turnsSeen))
                takeAgent(s, at: k)
                if let live = try? await engine.get("/api/code/live?id=\(id)&from=\(liveNext)") {
                    for e in live.list("events") {
                        switch e.str("kind") {
                        case "room": weights.roomEvent(e)
                        case "token":
                            weights.token(e)
                            turns[k].agent?.writing += e.str("text") ?? ""
                        default: break
                        }
                    }
                    liveNext = Int(live.num("next") ?? Double(liveNext))
                }
                var asks: [AgentAsk] = []
                for w in s.list("waiting") {
                    guard let wid = w.str("id"), let kind = w.str("kind") else { continue }
                    if kind == "browser" {
                        if handled.insert(wid).inserted { await testPage(w, id: wid, at: k) }
                    } else if kind == "question" {
                        let q = w.dict("what")?.str("question") ?? ""
                        if handled.insert(wid).inserted { turns[k].agent?.waited += 1 }
                        asks.append(AgentAsk(id: wid, kind: kind, text: q))
                        if !scriptAnswers.isEmpty {
                            let a = scriptAnswers.removeFirst()
                            await answer(wid, a)
                            asks.removeLast()
                        }
                    } else {
                        if handled.insert(wid).inserted { turns[k].agent?.waited += 1 }
                        asks.append(AgentAsk(id: wid, kind: kind, text: ChatModel.exactly(kind, w.dict("what"))))
                    }
                }
                turns[k].agent?.asks = asks
                turns[k].agent?.state = state
                turns[k].agent?.seconds = Date().timeIntervalSince(started)
                bump(k)
                if !["done", "stopped", "failed"].contains(state) { try await Task.sleep(nanoseconds: 300_000_000) }
            }
            let end = try await engine.get("/api/code/run?id=\(id)&turns=\(turnsSeen)")
            takeAgent(end, at: k)
            turns[k].agent?.madeUp = (end["made_up"] as? [String]) ?? []
            if let last = end.dict("last_test"), (last["ok"] as? Bool) == false || (last["stale"] as? Bool) == true {
                turns[k].agent?.untested = (last["stale"] as? Bool) == true ? "The page changed after its last test, so this version is untested."
                    : (last.str("text") ?? "The page's last test found problems.")
            }
            turns[k].text = end.str("answer") ?? end.str("error") ?? ""
            turns[k].failed = state == "failed"
            turns[k].agent?.state = state
            turns[k].agent?.asks = []
            turns[k].agent?.writing = ""
            turns[k].agent?.seconds = Date().timeIntervalSince(started)
            await refreshFiles(at: k)
            if let page = await loadedPage("index.html") { PreviewCenter.shared.show(code: page.page, project: root) }
        } catch {
            turns[k].text = error.localizedDescription
            turns[k].failed = true
        }
        turns[k].pending = false
        bump(k)
        weights.finish(nil)
        await refresh()
    }

    private func bump(_ k: Int) { turns[k].agentRev += 1 }

    /// What will run, in full, as the person must see it to allow it. Empty for anything this window cannot show, which
    /// is then only ever denied.
    static func exactly(_ kind: String, _ what: [String: Any]?) -> String {
        guard let what else { return "" }
        if kind == "shell", let c = what.str("command") {
            return c + "\n\nin " + (what.str("cwd") ?? "the project folder")
        }
        if kind == "mcp", let server = what.str("server"), let tool = what.str("tool") {
            let args = what["arguments"].flatMap { try? JSONSerialization.data(withJSONObject: $0, options: [.prettyPrinted, .sortedKeys]) }
            return "\(server) · \(tool)\n" + (args.map { String(decoding: $0, as: UTF8.self) } ?? "{}")
        }
        return ""
    }

    private func testPage(_ w: [String: Any], id: String, at k: Int) async {
        let path = w.dict("what")?.str("path") ?? "index.html"
        guard let page = await loadedPage(path) else {
            await answer(id, "{\"errors\":[\"could not read \(path)\"]}")
            return
        }
        let center = PreviewCenter.shared
        await refreshFiles(at: k)
        center.show(code: page.page, project: turns[k].agent?.project)
        var got = await tester.test(html: page.page, scripts: center.scripts)
        if !page.missing.isEmpty {
            got["errors"] = ((got["errors"] as? [String]) ?? []) + page.missing.map { "the page links to \($0), which does not exist" }
        }
        let data = (try? JSONSerialization.data(withJSONObject: got)) ?? Data("{}".utf8)
        await answer(id, String(decoding: data, as: UTF8.self))
    }

    func answer(_ id: String, _ text: String) async {
        _ = try? await engine.post("/api/code/answer", ["id": id, "text": text])
    }

    func decide(_ id: String, allow: Bool) async {
        _ = try? await engine.post("/api/code/approve", ["id": id, "allow": allow])
    }

    private func takeAgent(_ s: [String: Any], at k: Int) {
        guard !s.list("turns").isEmpty else { return }
        turns[k].agent?.writing = ""
        for t in s.list("turns") {
            switch t.str("kind") {
            case "model":
                turns[k].agent?.modelSteps = Int(t.num("step") ?? 0)
                turns[k].agent?.lastRead = Int(t.num("prompt_tokens") ?? 0)
            case "call":
                if let step = agentStep(t) { turns[k].agent?.steps.append(step) }
            case "error":
                turns[k].agent?.steps.append(AgentStep(icon: "exclamationmark.triangle", title: t.str("text") ?? "error", ok: false))
            default:
                break
            }
        }
    }

    private func agentStep(_ t: [String: Any]) -> AgentStep? {
        let tool = t.str("tool") ?? ""
        let args = t.dict("args") ?? [:]
        let ok = (t["ok"] as? Bool) ?? true
        let text = t.str("text") ?? ""
        let path = args.str("path") ?? t.str("path") ?? ""
        switch tool {
        case "write_file": return AgentStep(icon: "doc.badge.plus", title: "Wrote \(path)", detail: text, ok: ok)
        case "edit_file": return AgentStep(icon: "pencil", title: "Changed \(path)", detail: ok ? "" : text, ok: ok)
        case "read_file": return AgentStep(icon: "doc.text", title: "Read \(path)", ok: ok)
        case "list_files": return AgentStep(icon: "folder", title: "Looked at the folder", ok: ok)
        case "search": return AgentStep(icon: "magnifyingglass", title: "Searched for \(args.str("pattern") ?? "")", ok: ok)
        case "open_page": return AgentStep(icon: "safari", title: "Tested \(path) in the browser", detail: text, ok: ok)
        case "ask_user": return AgentStep(icon: "questionmark.bubble", title: "Asked: \(args.str("question") ?? "")", detail: text, ok: ok)
        case "read_shelf":
            return AgentStep(icon: "books.vertical", title: "Called the \(args.str("shelf") ?? "") shelf", detail: args.str("question") ?? "", ok: ok, memory: true)
        case "run_shell": return AgentStep(icon: "terminal", title: "Ran \(args.str("command") ?? "")", detail: ok ? "" : text, ok: ok)
        default: return AgentStep(icon: "wrench", title: tool, detail: text, ok: ok)
        }
    }
}

/// The agent's work in the conversation: each step a line, what it is writing now, and what it needs from you.
struct AgentCard: View {
    let agent: AgentState
    let pending: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(agent.steps) { s in row(s) }
            if pending, !agent.writing.isEmpty {
                Text(tail).font(Theme.mono(11)).foregroundStyle(Theme.dim).lineLimit(4)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(8).background(RoundedRectangle(cornerRadius: 6).fill(Color.black.opacity(0.5)))
            }
            ForEach(agent.asks) { a in AskRow(ask: a) }
            if let u = agent.untested, !pending {
                Label(u, systemImage: "exclamationmark.triangle").font(Theme.mono(11, .semibold)).foregroundStyle(Theme.error)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if !agent.madeUp.isEmpty {
                Label("Not finished. Still on the page and not in your memory: " + agent.madeUp.joined(separator: " · "),
                      systemImage: "exclamationmark.triangle")
                    .font(Theme.mono(11, .semibold)).foregroundStyle(Theme.error)
            }
            Text(footer).font(Theme.mono(10)).foregroundStyle(Theme.faint)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 10).fill(Theme.panel))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.line))
    }

    private var tail: String {
        let lines = agent.writing.split(separator: "\n", omittingEmptySubsequences: false)
        return lines.suffix(4).joined(separator: "\n")
    }

    private var footer: String {
        var parts = [pending ? "working" : agent.state, "\(agent.modelSteps) steps", String(format: "%.0f s", agent.seconds)]
        if agent.lastRead > 0 { parts.append("read \(agent.lastRead) tokens last step") }
        parts.append(agent.waited == 0 ? "no stops for you" : "stopped for you \(agent.waited) time\(agent.waited == 1 ? "" : "s")")
        if !agent.project.isEmpty { parts.append(URL(fileURLWithPath: agent.project).lastPathComponent) }
        return parts.joined(separator: " · ")
    }

    private func row(_ s: AgentStep) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Label(s.title, systemImage: s.icon).font(Theme.mono(11))
                .foregroundStyle(!s.ok ? Theme.error : s.memory ? Theme.memory : Theme.text)
            if !s.detail.isEmpty {
                Text(s.detail).font(Theme.mono(10)).foregroundStyle(s.ok ? Theme.faint : Theme.error.opacity(0.8))
                    .lineLimit(6).padding(.leading, 20)
            }
        }
    }
}

struct AskRow: View {
    let ask: AgentAsk
    @StateObject private var typing = ChatModel.Draft()

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if ask.kind == "question" {
                Text(ask.text).font(Theme.ui(14, .semibold)).foregroundStyle(Theme.memory)
                HStack {
                    TextField("Your answer", text: $typing.text).textFieldStyle(.roundedBorder)
                        .onSubmit { send(typing.text) }
                    Button("Answer") { send(typing.text) }.buttonStyle(Pill(color: Theme.memory))
                    Button("Leave it out") { send("") }.buttonStyle(.plain).foregroundStyle(Theme.dim).font(Theme.mono(11))
                }
            } else {
                Text(ask.kind == "shell" ? "Run this command?" : ask.kind == "mcp" ? "Let this tool run with these arguments?"
                     : "The agent wants to do something this window cannot show.")
                    .font(Theme.mono(11, .semibold)).foregroundStyle(Theme.model)
                Text(ask.text).font(Theme.mono(12)).foregroundStyle(Theme.text).textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
                HStack {
                    if !ask.text.isEmpty { Button("Allow") { decide(true) }.buttonStyle(Pill(color: Theme.model)) }
                    Button("Deny") { decide(false) }.buttonStyle(.plain).foregroundStyle(Theme.dim).font(Theme.mono(11))
                }
            }
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color.black.opacity(0.5)))
    }

    private func send(_ text: String) {
        let id = ask.id
        Task { await ChatModel.current?.answer(id, text) }
    }

    private func decide(_ allow: Bool) {
        let id = ask.id
        Task { await ChatModel.current?.decide(id, allow: allow) }
    }
}
