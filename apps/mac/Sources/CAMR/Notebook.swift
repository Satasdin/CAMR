import AppKit
import SwiftUI

/// One output under a notebook cell: printed text, a value, a table, a chart, or an error (the only red).
struct NotebookOutput: Identifiable {
    let id = UUID()
    let kind: String  // text, table, image, error
    var text = ""
    var rows: [[String]] = []
    var image: NSImage?
}

struct NotebookCell: Identifiable {
    let id: String
    var index: Int
    var kind: String  // code or markdown
    var source: String
    var saved: String  // as the file holds it; source differs from it while the person edits
    var count: Int?
    var outputs: [NotebookOutput]
    var dirty: Bool { source != saved }
}

/// A notebook of the open project, as the engine reads it (/api/notebook): its cells, each editable, and its run.
@MainActor
final class NotebookModel: ObservableObject {
    @Published var path = ""
    @Published var cells: [NotebookCell] = []
    @Published var running = false
    @Published var runningCell: Int?
    @Published var state = "idle"
    @Published var problem: String?
    @Published var sandboxed = true
    private var polling = false

    private var engine: Engine? { ChatModel.current?.engine }
    var dirty: Bool { cells.contains { $0.dirty } }

    func load(_ path: String) async {
        self.path = path
        await refresh(keepEdits: false)
    }

    /// The notebook as the file holds it now; a cell the person is editing keeps what they typed.
    func refresh(keepEdits: Bool = true) async {
        guard let engine, !path.isEmpty else { return }
        let q = path.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? path
        do {
            let got = try await engine.get("/api/notebook?path=\(q)")
            take(got, keepEdits: keepEdits)
            problem = nil
        } catch {
            problem = error.localizedDescription
        }
    }

    private func take(_ got: [String: Any], keepEdits: Bool) {
        let mine = Dictionary(uniqueKeysWithValues: cells.map { ($0.id, $0) })
        cells = got.list("cells").map { c in
            let id = c.str("id") ?? UUID().uuidString
            let src = c.str("source") ?? ""
            var cell = NotebookCell(id: id, index: Int(c.num("index") ?? 0), kind: c.str("kind") ?? "code", source: src,
                                    saved: src, count: c.num("count").map { Int($0) },
                                    outputs: c.list("outputs").map(NotebookModel.output))
            if keepEdits, let old = mine[id], old.dirty { cell.source = old.source }
            return cell
        }
        sandboxed = (got["sandboxed"] as? Bool) ?? false
        if let run = got.dict("run") {
            state = run.str("state") ?? "idle"
            running = state == "running"
            runningCell = run.num("cell").map { Int($0) }
            if state == "failed" { problem = run.str("error") }
        }
    }

    static func output(_ o: [String: Any]) -> NotebookOutput {
        switch o.str("kind") ?? "text" {
        case "image":
            let img = (o.str("base64")).flatMap { Data(base64Encoded: $0) }.flatMap { NSImage(data: $0) }
            return NotebookOutput(kind: "image", image: img)
        case "table":
            let rows = (o["rows"] as? [[String]]) ?? []
            return NotebookOutput(kind: "table", text: o.str("text") ?? "", rows: rows)
        case "error":
            return NotebookOutput(kind: "error", text: o.str("text") ?? "\(o.str("ename") ?? "Error"): \(o.str("evalue") ?? "")")
        default:
            return NotebookOutput(kind: "text", text: o.str("text") ?? "")
        }
    }

    /// Every cell the person changed, written back into the file.
    func save() async {
        guard let engine else { return }
        for c in cells where c.dirty {
            do {
                let got = try await engine.post("/api/notebook/cell", ["path": path, "index": c.index, "source": c.source])
                if let i = cells.firstIndex(where: { $0.id == c.id }) {
                    cells[i].saved = c.source
                    cells[i].outputs = got.list("cells").first(where: { $0.str("id") == c.id })?.list("outputs").map(NotebookModel.output) ?? []
                }
            } catch {
                problem = error.localizedDescription
                return
            }
        }
    }

    /// Run one cell, or all of them from a fresh kernel (nil). What the person changed is saved first.
    func run(_ cell: Int?) async {
        guard let engine, !running else { return }
        await save()
        var body: [String: Any] = ["path": path]
        if let cell { body["cell"] = cell }
        do {
            _ = try await engine.post("/api/notebook/run", body)
            running = true
            state = "running"
            problem = nil
        } catch {
            problem = error.localizedDescription
            return
        }
        await follow()
    }

    func stop() async {
        _ = try? await engine?.post("/api/notebook/stop", ["path": path])
    }

    /// While it runs, the file is read again every moment: each cell's outputs appear as it ends.
    private func follow() async {
        guard !polling else { return }
        polling = true
        defer { polling = false }
        while running {
            try? await Task.sleep(nanoseconds: 400_000_000)
            await refresh()
        }
    }

    func addCell(after index: Int, kind: String = "code") async {
        guard let engine else { return }
        await save()
        if let got = try? await engine.post("/api/notebook/cell", ["path": path, "index": index + 1, "source": "", "kind": kind, "op": "insert"]) {
            take(got, keepEdits: true)
        }
    }

    func deleteCell(_ index: Int) async {
        guard let engine else { return }
        if let got = try? await engine.post("/api/notebook/cell", ["path": path, "index": index, "op": "delete"]) {
            take(got, keepEdits: true)
        }
    }
}

/// The Notebook tab: each cell an editor in monospace with its outputs under it; Run cell, Run all, Stop, Save.
struct NotebookPane: View {
    let path: String
    let version: Int
    @StateObject private var model = NotebookModel()

    var body: some View {
        VStack(spacing: 0) {
            bar
            Rectangle().fill(Theme.line).frame(height: 1)
            if let p = model.problem {
                Text(p).font(Theme.mono(10)).foregroundStyle(Theme.error).lineLimit(3)
                    .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 12).padding(.vertical, 6)
                    .background(Theme.panel)
            }
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 10) {
                    ForEach($model.cells) { $cell in
                        NotebookCellView(cell: $cell, running: model.runningCell == cell.index, busy: model.running,
                                         run: { Task { await model.run(cell.index) } },
                                         add: { Task { await model.addCell(after: cell.index) } },
                                         remove: { Task { await model.deleteCell(cell.index) } })
                    }
                    if model.cells.isEmpty {
                        Text("No cells yet.").font(Theme.mono(11)).foregroundStyle(Theme.faint).padding(12)
                    }
                }
                .padding(12)
            }
        }
        .background(Theme.ink)
        .task(id: "\(path)#\(version)") { await model.load(path) }
    }

    private var bar: some View {
        HStack(spacing: 10) {
            Text(URL(fileURLWithPath: path).lastPathComponent).font(Theme.mono(11, .semibold)).foregroundStyle(Theme.text)
            Button { Task { await model.run(nil) } } label: { Label("Run all", systemImage: "forward.end") }
                .disabled(model.running).help("Run every cell in order, from a fresh kernel")
            Button { Task { await model.stop() } } label: { Label("Stop", systemImage: "stop.fill") }
                .disabled(!model.running).help("Stop the cell that is running")
            Button { Task { await model.save() } } label: { Label("Save", systemImage: "square.and.arrow.down") }
                .disabled(!model.dirty).keyboardShortcut("s", modifiers: .command).help("Write your changes into the notebook")
            Spacer()
            if model.running {
                ProgressView().controlSize(.small)
                Text(model.runningCell.map { "running cell \($0)" } ?? "starting the kernel").font(Theme.mono(10)).foregroundStyle(Theme.dim)
            } else if model.state != "idle" {
                Text(model.state).font(Theme.mono(10))
                    .foregroundStyle(["error", "timeout", "failed"].contains(model.state) ? Theme.error : Theme.dim)
            }
            Image(systemName: model.sandboxed ? "lock.shield" : "lock.open")
                .foregroundStyle(Theme.faint)
                .help(model.sandboxed ? "Runs shut in: no network, and it writes only inside the project folder"
                      : "Not shut in here: only the time limits and the project folder apply")
        }
        .buttonStyle(.plain).font(Theme.mono(10)).foregroundStyle(Theme.dim)
        .padding(.horizontal, 12).padding(.vertical, 7)
        .background(Theme.panel)
    }
}

struct NotebookCellView: View {
    @Binding var cell: NotebookCell
    let running: Bool
    let busy: Bool
    let run: () -> Void
    let add: () -> Void
    let remove: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 8) {
                Text(cell.kind == "code" ? "[\(cell.count.map(String.init) ?? " ")]" : "md")
                    .font(Theme.mono(10)).foregroundStyle(Theme.faint).frame(width: 34, alignment: .leading)
                if cell.dirty { Text("edited").font(Theme.mono(9)).foregroundStyle(Theme.dim) }
                Spacer()
                if running { ProgressView().controlSize(.mini) }
                if cell.kind == "code" {
                    Button(action: run) { Image(systemName: "play.fill") }.disabled(busy).help("Run this cell")
                }
                Button(action: add) { Image(systemName: "plus") }.help("Add a cell under this one")
                Button(action: remove) { Image(systemName: "trash") }.disabled(busy).help("Remove this cell")
            }
            .buttonStyle(.plain).font(.system(size: 10)).foregroundStyle(Theme.dim)
            TextEditor(text: $cell.source)
                .font(cell.kind == "code" ? Theme.mono(12) : Theme.ui(13))
                .foregroundStyle(cell.kind == "code" ? Theme.text : Theme.dim)
                .scrollContentBackground(.hidden)
                .scrollDisabled(true)
                .frame(minHeight: CGFloat(max(1, cell.source.split(separator: "\n", omittingEmptySubsequences: false).count)) * 16 + 10)
                .padding(6)
                .background(RoundedRectangle(cornerRadius: 6).fill(Color.black.opacity(cell.kind == "code" ? 0.6 : 0.25)))
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(running ? Theme.text.opacity(0.5) : Theme.line))
                .glow(Theme.text, radius: running ? 6 : 0, opacity: running ? 0.25 : 0)
            ForEach(cell.outputs) { o in NotebookOutputView(output: o) }
        }
    }
}

struct NotebookOutputView: View {
    let output: NotebookOutput

    var body: some View {
        switch output.kind {
        case "image":
            if let img = output.image {
                Image(nsImage: img).resizable().interpolation(.high).aspectRatio(contentMode: .fit)
                    .frame(maxWidth: min(img.size.width, 560), alignment: .leading)
                    .background(Color.white).clipShape(RoundedRectangle(cornerRadius: 4))
            }
        case "table":
            ScrollView(.horizontal) {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(Array(output.rows.enumerated()), id: \.offset) { r, row in
                        HStack(spacing: 0) {
                            ForEach(Array(row.enumerated()), id: \.offset) { _, v in
                                Text(v).font(Theme.mono(11, r == 0 ? .semibold : .regular))
                                    .foregroundStyle(r == 0 ? Theme.dim : Theme.text).lineLimit(1)
                                    .frame(minWidth: 70, alignment: .leading).padding(.horizontal, 6).padding(.vertical, 3)
                            }
                        }
                        .background(r % 2 == 1 ? Color.white.opacity(0.03) : .clear)
                    }
                }
                .textSelection(.enabled)
            }
            .padding(.leading, 6)
        case "error":
            Text(output.text).font(Theme.mono(11)).foregroundStyle(Theme.error).textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading).padding(8)
                .background(RoundedRectangle(cornerRadius: 6).fill(Theme.error.opacity(0.08)))
        default:
            Text(output.text).font(Theme.mono(11)).foregroundStyle(Color.white.opacity(0.82)).textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 8).padding(.vertical, 2)
        }
    }
}

/// A .py file of the open project, its last run's output and the pictures it made (/api/script).
@MainActor
final class ScriptModel: ObservableObject {
    @Published var path = ""
    @Published var source = ""
    @Published var saved = ""
    @Published var output = ""
    @Published var state = "idle"
    @Published var code: Int?
    @Published var made: [String] = []
    @Published var images: [(path: String, image: NSImage)] = []
    @Published var problem: String?
    @Published var sandboxed = true

    private var engine: Engine? { ChatModel.current?.engine }
    var running: Bool { state == "running" }

    func load(_ path: String) async {
        self.path = path
        await refresh(reloadSource: true)
    }

    func refresh(reloadSource: Bool = false) async {
        guard let engine else { return }
        let q = path.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? path
        do {
            let got = try await engine.get("/api/script?path=\(q)")
            if reloadSource || self.source == saved {
                self.source = got.str("source") ?? ""
                saved = self.source
            }
            let run = got.dict("run") ?? [:]
            state = run.str("state") ?? "idle"
            output = run.str("output") ?? run.str("error") ?? ""
            code = run.num("code").map { Int($0) }
            made = (run["made"] as? [String]) ?? []
            images = got.list("images").compactMap { i in
                guard let p = i.str("path"), let d = i.str("base64").flatMap({ Data(base64Encoded: $0) }), let img = NSImage(data: d) else { return nil }
                return (p, img)
            }
            sandboxed = (got["sandboxed"] as? Bool) ?? false
            problem = nil
        } catch {
            problem = error.localizedDescription
        }
    }

    func save() async {
        guard let engine, source != saved else { return }
        do {
            _ = try await engine.post("/api/code/file", ["path": path, "text": source])
            saved = source
        } catch {
            problem = error.localizedDescription
        }
    }

    func run() async {
        guard let engine, !running else { return }
        await save()
        do {
            _ = try await engine.post("/api/script/run", ["path": path])
            state = "running"
        } catch {
            problem = error.localizedDescription
            return
        }
        while running {
            try? await Task.sleep(nanoseconds: 400_000_000)
            await refresh()
        }
    }

    func stop() async { _ = try? await engine?.post("/api/script/stop", ["path": path]) }
}

/// The Script tab: the .py file (editable), Run and Stop, then what it printed and the pictures it made.
struct ScriptPane: View {
    let path: String
    let version: Int
    @StateObject private var model = ScriptModel()

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                Text(URL(fileURLWithPath: path).lastPathComponent).font(Theme.mono(11, .semibold)).foregroundStyle(Theme.text)
                Button { Task { await model.run() } } label: { Label("Run", systemImage: "play.fill") }.disabled(model.running)
                Button { Task { await model.stop() } } label: { Label("Stop", systemImage: "stop.fill") }.disabled(!model.running)
                Button { Task { await model.save() } } label: { Label("Save", systemImage: "square.and.arrow.down") }
                    .disabled(model.source == model.saved)
                Spacer()
                if model.running { ProgressView().controlSize(.small) }
                Text(status).font(Theme.mono(10)).foregroundStyle(["error", "timeout", "failed"].contains(model.state) ? Theme.error : Theme.dim)
                Image(systemName: model.sandboxed ? "lock.shield" : "lock.open").foregroundStyle(Theme.faint)
                    .help(model.sandboxed ? "Runs shut in: no network, and it writes only inside the project folder"
                          : "Not shut in here: only the time limit and the project folder apply")
            }
            .buttonStyle(.plain).font(Theme.mono(10)).foregroundStyle(Theme.dim)
            .padding(.horizontal, 12).padding(.vertical, 7).background(Theme.panel)
            Rectangle().fill(Theme.line).frame(height: 1)
            if let p = model.problem {
                Text(p).font(Theme.mono(10)).foregroundStyle(Theme.error).padding(8).frame(maxWidth: .infinity, alignment: .leading)
            }
            TextEditor(text: $model.source)
                .font(Theme.mono(12)).foregroundStyle(Theme.text)
                .scrollContentBackground(.hidden).padding(8)
                .background(Color.black.opacity(0.6))
                .frame(maxHeight: .infinity)
            Rectangle().fill(Theme.line).frame(height: 1)
            ScrollView {
                VStack(alignment: .leading, spacing: 8) {
                    Text(model.output.isEmpty ? (model.state == "idle" ? "Press Run to run it." : "(no output)") : model.output)
                        .font(Theme.mono(11)).foregroundStyle(model.state == "error" ? Theme.error : Color.white.opacity(0.82))
                        .textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                    if !model.made.isEmpty {
                        Text("Wrote " + model.made.joined(separator: ", ")).font(Theme.mono(10)).foregroundStyle(Theme.dim)
                    }
                    ForEach(model.images, id: \.path) { i in
                        Image(nsImage: i.image).resizable().aspectRatio(contentMode: .fit)
                            .frame(maxWidth: min(i.image.size.width, 560), alignment: .leading)
                            .background(Color.white).clipShape(RoundedRectangle(cornerRadius: 4))
                    }
                }
                .padding(12)
            }
            .frame(maxHeight: .infinity)
        }
        .background(Theme.ink)
        .task(id: "\(path)#\(version)") { await model.load(path) }
    }

    private var status: String {
        switch model.state {
        case "idle": return ""
        case "running": return "running"
        case "done": return "exit 0"
        case "error": return "exit \(model.code ?? 1)"
        default: return model.state
        }
    }
}
