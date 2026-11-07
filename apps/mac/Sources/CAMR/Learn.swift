import SwiftUI

/// Learning from the web (camr_engine.learn through /api/learn): started on purpose with the Learn button or "learn
/// about …", never in everyday chat. While it reads, the card shows each step; then it asks where the new notes go.
@MainActor
final class LearnModel: ObservableObject {
    struct Note: Identifiable {
        let id: String
        let text: String
        let quote: String
        let url: String
        let title: String
        var keep: Bool
        let known: Bool
        let held: String?
    }

    @Published var topic = ""
    @Published var state = ""  // "" when nothing is being learnt
    @Published var log: [String] = []
    @Published var pages: [(title: String, url: String, notes: Int, error: String)] = []
    @Published var notes: [Note] = []
    @Published var card = ""
    @Published var shelf: String?  // the suggested shelf
    @Published var shelfLabel = ""
    @Published var newLabel = ""
    @Published var error = ""
    @Published var outcome = ""
    let engine: Engine
    private var polling: Task<Void, Never>?

    init(engine: Engine) { self.engine = engine }

    var active: Bool { !state.isEmpty }
    var deciding: Bool { state == "deciding" }

    /// "learn about X", "go and learn about X", "learn X from the web": the topic, or nil.
    static func topic(in text: String) -> String? {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        for lead in ["go and learn about ", "go learn about ", "learn about ", "research and learn about "] {
            if t.lowercased().hasPrefix(lead) {
                let rest = String(t.dropFirst(lead.count)).trimmingCharacters(in: .punctuationCharacters.union(.whitespaces))
                return rest.count >= 3 ? rest : nil
            }
        }
        return nil
    }

    func start(_ topic: String) async {
        error = ""
        outcome = ""
        do {
            let got = try await engine.post("/api/learn/start", ["topic": topic])
            take(got.dict("learning") ?? [:], card: nil)
            poll()
        } catch {
            self.error = "\(error.localizedDescription)"
        }
    }

    func stop() async {
        _ = try? await engine.post("/api/learn/stop", [:])
    }

    func decide(_ choice: String) async {
        var body: [String: Any] = ["choice": choice, "keep": notes.filter(\.keep).map(\.id)]
        if choice == "shelf", let shelf { body["shelf"] = shelf }
        if choice == "new" { body["label"] = newLabel }
        do {
            let got = try await engine.post("/api/learn/decide", body)
            let d = got.dict("learning")?.dict("decision") ?? [:]
            let kept = Int(d.num("kept") ?? 0)
            outcome = choice == "drop" ? "Dropped." : choice == "chat" ? "Kept \(kept) notes for this chat."
                : "Kept \(kept) notes on \(choice == "new" ? newLabel : shelfLabel)."
            state = ""
        } catch {
            self.error = "\(error.localizedDescription)"
        }
    }

    func close() { state = ""; outcome = ""; error = "" }

    private func poll() {
        polling?.cancel()
        polling = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 800_000_000)
                guard let self, let got = try? await self.engine.get("/api/learn") else { continue }
                self.take(got.dict("learning") ?? [:], card: got.str("card"))
                if ["deciding", "done", "failed"].contains(self.state) { return }
            }
        }
    }

    private func take(_ j: [String: Any], card: String?) {
        topic = j.str("topic") ?? topic
        state = j.str("state") ?? state
        log = (j["log"] as? [String]) ?? log
        error = j.str("error") ?? ""
        pages = j.list("pages").map { ($0.str("title") ?? "", $0.str("url") ?? "", Int($0.num("notes") ?? 0),
                                       $0.str("error") ?? "") }
        let old = Dictionary(uniqueKeysWithValues: notes.map { ($0.id, $0.keep) })
        notes = j.list("notes").map {
            let id = $0.str("id") ?? ""
            return Note(id: id, text: $0.str("text") ?? "", quote: $0.str("quote") ?? "", url: $0.str("url") ?? "",
                        title: $0.str("title") ?? "", keep: old[id] ?? (($0["keep"] as? Bool) ?? true),
                        known: ($0["known"] as? Bool) ?? false, held: $0.str("held"))
        }
        let s = j.dict("suggestion") ?? [:]
        shelf = s.str("shelf")
        shelfLabel = s.str("label") ?? shelfLabel
        if newLabel.isEmpty { newLabel = s.str("new_label") ?? "" }
        if let card { self.card = card }
        if state == "failed" { polling?.cancel() }
    }
}

/// The learning card: progress while it reads, then the decision.
struct LearnCard: View {
    @ObservedObject var model: LearnModel

    var body: some View {
        if model.active || !model.outcome.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 8) {
                    Image(systemName: "books.vertical").foregroundStyle(Theme.memory)
                    Text("Learning about \(model.topic)").font(Theme.ui(14, .semibold)).foregroundStyle(Theme.text)
                    Text(stateText).font(Theme.mono(10)).foregroundStyle(model.state == "failed" ? Theme.error : Theme.dim)
                    Spacer()
                    if model.active && !model.deciding && model.state != "failed" {
                        Button("Stop") { Task { await model.stop() } }.buttonStyle(.plain).foregroundStyle(Theme.dim)
                    } else {
                        Button { model.close() } label: { Image(systemName: "xmark") }.buttonStyle(.plain)
                            .foregroundStyle(Theme.faint)
                    }
                }
                if !model.outcome.isEmpty {
                    Text(model.outcome).font(Theme.ui(13)).foregroundStyle(Theme.memory)
                } else if model.deciding {
                    decision
                } else {
                    ForEach(Array(model.log.suffix(4).enumerated()), id: \.0) { _, line in
                        Text(line).font(Theme.mono(11)).foregroundStyle(Theme.dim).lineLimit(1)
                    }
                    if !model.error.isEmpty {
                        Text(model.error).font(Theme.mono(11)).foregroundStyle(Theme.error)
                    }
                }
            }
            .padding(14)
            .background(RoundedRectangle(cornerRadius: 12).fill(Theme.panel))
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.memory.opacity(0.35)))
            .padding(.horizontal, 32)
            .frame(maxWidth: 1100)
            .frame(maxWidth: .infinity)
        }
    }

    private var stateText: String {
        switch model.state {
        case "starting", "searching": return "searching"
        case "reading", "distilling": return "reading \(model.pages.count) pages"
        case "quizzing": return "quizzing itself"
        case "comparing": return "checking the shelves"
        case "deciding": return "your call"
        case "failed": return "stopped"
        default: return model.state
        }
    }

    private var decision: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(model.card).font(Theme.ui(13)).foregroundStyle(Theme.text).fixedSize(horizontal: false, vertical: true)
            ScrollView {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach($model.notes) { $n in
                        HStack(alignment: .top, spacing: 8) {
                            Toggle("", isOn: $n.keep).toggleStyle(.checkbox).labelsHidden()
                            VStack(alignment: .leading, spacing: 2) {
                                Text(n.text).font(Theme.ui(12.5)).foregroundStyle(n.keep ? Theme.text : Theme.dim)
                                HStack(spacing: 6) {
                                    if n.known { tag("already known", Theme.model) }
                                    if let h = n.held { tag("on \(h)", Theme.memory) }
                                    Text(n.title.isEmpty ? n.url : n.title).font(Theme.mono(9.5))
                                        .foregroundStyle(Theme.faint).lineLimit(1)
                                }
                                .help("“\(n.quote)” — \(n.url)")
                            }
                        }
                    }
                }
            }
            .frame(maxHeight: 220)
            HStack(spacing: 8) {
                if model.shelf != nil {
                    Button("Add to \(model.shelfLabel)") { Task { await model.decide("shelf") } }
                        .buttonStyle(Pill(color: Theme.memory))
                }
                TextField("New shelf", text: $model.newLabel).textFieldStyle(.plain).font(Theme.ui(13))
                    .padding(.horizontal, 10).padding(.vertical, 8).frame(width: 150)
                    .background(RoundedRectangle(cornerRadius: 8).fill(Theme.ink))
                Button("New shelf") { Task { await model.decide("new") } }
                    .buttonStyle(Pill(color: Theme.text.opacity(0.85)))
                    .disabled(model.newLabel.trimmingCharacters(in: .whitespaces).isEmpty)
                Button("This chat only") { Task { await model.decide("chat") } }
                    .buttonStyle(Pill(color: Theme.text.opacity(0.6)))
                Button("Drop") { Task { await model.decide("drop") } }.buttonStyle(.plain).foregroundStyle(Theme.dim)
                Spacer()
                Text("\(model.notes.filter(\.keep).count) of \(model.notes.count) ticked").font(Theme.mono(10))
                    .foregroundStyle(Theme.faint)
            }
        }
    }

    private func tag(_ s: String, _ c: Color) -> some View {
        Text(s).font(Theme.mono(9.5)).foregroundStyle(c)
            .padding(.horizontal, 5).padding(.vertical, 1)
            .background(Capsule().stroke(c.opacity(0.5)))
    }
}
