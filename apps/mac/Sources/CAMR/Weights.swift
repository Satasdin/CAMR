import SwiftUI

/// What the weights view draws, fed only by what the engine measured: the model's layers as they load, the shelves
/// of memory and the note an answer reads (and whether it came from RAM or the SSD), the notes warmed before the
/// first question, and, for every word, how strongly each layer fired (32 numbers a layer, from camr_engine.live).
/// Nothing here is made up: with no events, nothing moves. (The engine calls a note a room.)
@MainActor
final class WeightsModel: ObservableObject {
    static let bins = 32

    // the model
    @Published var modelName = ""
    @Published var layers = 28
    var loadedLayers = 0  // moved on by tick(), drawn every frame
    @Published var modelBytes: Double = 0
    @Published var loadSeconds: Double?
    var arrived: [Int: Date] = [:]  // when each layer's weights were shown arriving
    private var pending: [(Int, Double)] = []  // load events not yet shown: (layer, bytes)
    private var lastShown = Date.distantPast
    private var loadingDone = false

    // the memory
    @Published var memoryOn = true
    @Published var rooms = 0
    @Published var room: Int?
    @Published var tier: String?
    @Published var roomBytes: Double = 0
    @Published var readBytes: Double = 0
    var roomAt: Date?  // when the note was chosen: it then flows into every layer
    @Published var shelf: String?  // the shelf the chosen note is on
    var shelves: [ShelfInfo] = []  // from the chat's state, in order
    var warmed: [String: [(Int, Date)]] = [:]  // notes read ahead, by shelf: (note, when)
    @Published var warmBytes: Double = 0
    var residentUntil: Date?  // the room's keys and values sit in every layer's attention until the answer ends

    // the answer
    var act: [[Float]] = []  // layers × bins, 0...1, as shown now
    // Each cell is read on its own range: a few of the hidden state's channels carry values far above the rest
    // in every layer, and one scale for the whole layer would show only them.
    private var low: [[Float]] = []
    private var high: [[Float]] = []
    var lastToken: Date?
    @Published var words = 0
    @Published var firstWord: Double?
    @Published var tps: Double?
    @Published var answering = false

    func beginLoad(model: String) {
        modelName = model
        loadedLayers = 0
        modelBytes = 0
        loadSeconds = nil
        arrived = [:]
        pending = []
        loadingDone = false
        act = []
        room = nil
        roomAt = nil
        residentUntil = nil
        answering = false
    }

    func loadEvent(_ e: [String: Any]) {
        switch e.str("kind") {
        case "load":
            if let n = e.num("layers") { layers = Int(n) }
            if let i = e.num("layer") { pending.append((Int(i), e.num("bytes") ?? 0)) }
        case "loaded":
            if let n = e.num("layers") { layers = Int(n) }
            modelBytes = e.num("bytes") ?? modelBytes
            loadSeconds = e.num("s")
        default:
            break
        }
    }

    func loadDone() { loadingDone = true }

    var loading: Bool { loadedLayers < layers || !loadingDone }

    /// Shows the next layer that arrived, no faster than one every 40 ms, so a load from a warm disk (a tenth of a
    /// second) can still be followed by eye. The order and the sizes are the engine's.
    func tick(_ now: Date) {
        let pace = loadingDone ? 0.006 : 0.04  // once the engine is ready, what is left is shown at once
        if !pending.isEmpty, now.timeIntervalSince(lastShown) > pace {
            let (i, _) = pending.removeFirst()
            arrived[i] = now
            loadedLayers = max(loadedLayers, i + 1)
            lastShown = now
        }
        guard !act.isEmpty, let t = lastToken else { return }
        let idle = now.timeIntervalSince(t)
        if idle > 0.12 {  // between words and after the answer, the layers cool
            let k = Float(max(0.0, 1.0 - (idle - 0.12) * 0.9))
            for i in act.indices { for j in act[i].indices { act[i][j] *= (0.97 + 0.03 * k) } }
        }
    }

    func beginAnswer(memory: Bool) {
        memoryOn = memory
        answering = true
        words = 0
        firstWord = nil
        tps = nil
        room = nil
        roomAt = nil
        readBytes = 0
        if act.count != layers { act = Array(repeating: Array(repeating: 0, count: Self.bins), count: layers) }
    }

    func warmEvent(_ e: [String: Any]) {
        switch e.str("kind") {
        case "warm":
            if let s = e.str("shelf"), let r = e.num("room") { warmed[s, default: []].append((Int(r), Date())) }
            warmBytes += e.num("bytes") ?? 0
        case "token":
            layersEvent(e["layers"] as? [[Double]])
        default:
            break
        }
    }

    func roomEvent(_ e: [String: Any]) {
        shelf = shelves.first(where: { $0.reach == e.str("reach") })?.name
        if let s = shelf, let i = shelves.firstIndex(where: { $0.name == s }), let n = e.num("rooms") {
            shelves[i].notes = Int(n)
        }
        rooms = Int(e.num("rooms") ?? Double(rooms))
        room = e.num("room").map(Int.init)
        tier = e.str("tier")
        roomBytes = e.num("bytes") ?? 0
        readBytes = e.num("read_bytes") ?? 0
        roomAt = Date()
        residentUntil = .distantFuture
    }

    func layersEvent(_ rows: [[Double]]?) {
        guard let rows, !rows.isEmpty else { return }
        if rows.count != layers { layers = rows.count }
        let fresh = Array(repeating: Array(repeating: Float(0), count: Self.bins), count: layers)
        if act.count != layers { act = fresh }
        if low.count != layers {
            low = rows.map { $0.prefix(Self.bins).map { Float($0) } }
            high = low.map { $0.map { $0 * 1.0001 + 1e-6 } }
        }
        for (i, row) in rows.enumerated() {
            for (j, d) in row.prefix(Self.bins).enumerated() {
                let v = Float(d)
                low[i][j] = min(low[i][j] + (v - low[i][j]) * 0.02, v)  // the range relaxes slowly toward now
                high[i][j] = max(high[i][j] + (v - high[i][j]) * 0.02, v)
                let span = max(high[i][j] - low[i][j], 1e-6)
                act[i][j] = pow((v - low[i][j]) / span, 1.4)
            }
        }
        lastToken = Date()
    }

    func token(_ e: [String: Any]) {
        words += 1
        layersEvent(e["layers"] as? [[Double]])
    }

    func finish(_ metric: [String: Any]?) {
        answering = false
        firstWord = metric?.num("first_word_s") ?? firstWord
        tps = metric?.num("decode_tps") ?? metric?.num("gen_tps")
        if let r = metric?.num("read_bytes") { readBytes = r }
        residentUntil = Date().addingTimeInterval(1.2)
    }
}

struct ShelfInfo {
    let name: String
    let label: String
    let reach: String
    var notes: Int
}

/// The weights view: the memory's rooms above, the model's layers below (one column a layer, 32 cells each), and
/// the chosen room's notes flowing into every layer when memory is on.
struct WeightsView: View {
    @ObservedObject var w: WeightsModel

    var body: some View {
        TimelineView(.animation) { tl in
            let _ = w.tick(tl.date)
            panel(tl.date)
        }
    }

    private func panel(_ now: Date) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Circle().fill(w.memoryOn ? Theme.memory : Theme.faint).frame(width: 6, height: 6)
                    .glow(Theme.memory, radius: w.memoryOn ? 4 : 0)
                Text(w.memoryOn ? "MEMORY" : "MEMORY OFF").font(Theme.mono(10, .semibold))
                    .foregroundStyle(w.memoryOn ? Theme.memory : Theme.faint)
                Spacer()
                Text(memoryLine).font(Theme.mono(10)).foregroundStyle(Theme.dim)
            }
            Canvas { ctx, size in draw(&ctx, size, now) }
                .frame(minHeight: 260)
            HStack(spacing: 6) {
                Circle().fill(Theme.model).frame(width: 6, height: 6).glow(Theme.model, radius: 4)
                Text("MODEL").font(Theme.mono(10, .semibold)).foregroundStyle(Theme.model)
                Spacer()
                Text(modelLine).font(Theme.mono(10)).foregroundStyle(Theme.dim)
            }
            Text(statsLine).font(Theme.mono(10)).foregroundStyle(Theme.faint).lineLimit(1)
        }
    }

    var memoryLine: String {
        guard w.memoryOn else { return "the model alone" }
        let total = w.shelves.isEmpty ? w.rooms : w.shelves.reduce(0) { $0 + $1.notes }
        var parts = [w.shelves.isEmpty ? "\(total) notes" : "\(w.shelves.count) shelves · \(total) notes"]
        if let r = w.room {
            let on = w.shelves.first(where: { $0.name == w.shelf })?.label
            parts.append(on.map { "note \(r) on \($0)" } ?? "note \(r)")
        }
        if let t = w.tier { parts.append(t == "ssd" ? "read from SSD" : t == "ram" ? "hot in RAM" : "as words") }
        return parts.joined(separator: " · ")
    }

    var modelLine: String {
        var parts = [w.modelName, "\(w.layers) layers"]
        if w.modelBytes > 0 { parts.append(bytesText(w.modelBytes)) }
        if w.loading { parts.append("loading \(w.loadedLayers)/\(w.layers)") }
        return parts.filter { !$0.isEmpty }.joined(separator: " · ")
    }

    var statsLine: String {
        var parts: [String] = []
        if let f = w.firstWord { parts.append("first word \(secondsText(f))") }
        if let t = w.tps { parts.append(String(format: "%.0f tok/s", t)) }
        if w.memoryOn, w.readBytes > 0 { parts.append("read \(bytesText(w.readBytes))") }
        if w.words > 0 { parts.append("\(w.words) words") }
        if let s = w.loadSeconds, parts.isEmpty { parts.append("weights read in \(secondsText(s))") }
        if parts.isEmpty, w.warmBytes > 0 { parts.append("warmed \(bytesText(w.warmBytes)) of notes into RAM") }
        return parts.isEmpty ? " " : parts.joined(separator: " · ")
    }

    // MARK: drawing

    private let roomCols = 16, roomRows = 5

    private func draw(_ ctx: inout GraphicsContext, _ size: CGSize, _ now: Date) {
        ctx.fill(Path(roundedRect: CGRect(origin: .zero, size: size), cornerRadius: 10), with: .color(Theme.ink))
        let pad: CGFloat = 10
        let memH = size.height * (w.shelves.isEmpty ? 0.24 : 0.30)
        let gap = size.height * 0.12
        let memRect = CGRect(x: pad, y: pad, width: size.width - 2 * pad, height: memH - pad)
        let modelRect = CGRect(x: pad, y: memH + gap, width: size.width - 2 * pad, height: size.height - memH - gap - pad)
        let chosen = w.shelves.isEmpty ? drawGrid(&ctx, memRect, now) : drawShelves(&ctx, memRect, now)
        let cols = columns(modelRect)
        drawLayers(&ctx, cols, modelRect, now)
        if w.memoryOn, let at = w.roomAt, let c = chosen {
            drawFlow(&ctx, from: c, to: cols, modelTop: modelRect.minY, since: now.timeIntervalSince(at))
        }
    }

    /// One row a shelf: its name and size, then its notes as tiles (each tile stands for an equal share of them).
    /// Returns the chosen note's tile.
    private func drawShelves(_ ctx: inout GraphicsContext, _ r: CGRect, _ now: Date) -> CGRect? {
        let labelW: CGFloat = min(96, r.width * 0.28)
        let rowH = r.height / CGFloat(w.shelves.count)
        let cols = max(6, Int((r.width - labelW) / max(10, rowH * 0.95)))
        let cw = (r.width - labelW) / CGFloat(cols)
        var chosen: CGRect?
        for (k, sh) in w.shelves.enumerated() {
            let y = r.minY + CGFloat(k) * rowH
            let isChosen = w.memoryOn && sh.name == w.shelf && w.roomAt != nil
            let text = Text("\(sh.label.uppercased())  \(sh.notes)").font(Theme.mono(rowH > 22 ? 10 : 8, .semibold))
                .foregroundColor(!w.memoryOn ? Theme.faint : isChosen ? Theme.memory : Theme.dim)
            ctx.draw(text, at: CGPoint(x: r.minX, y: y + rowH / 2), anchor: .leading)
            let filled = min(cols, sh.notes)
            let recentWarm = (w.warmed[sh.name] ?? []).filter { now.timeIntervalSince($0.1) < 1.6 }
            for i in 0..<cols {
                let t = CGRect(x: r.minX + labelW + CGFloat(i) * cw + 1.5, y: y + 2, width: cw - 3, height: rowH - 4)
                let p = Path(roundedRect: t, cornerRadius: 2)
                if !w.memoryOn {
                    ctx.stroke(p, with: .color(.white.opacity(0.05)), lineWidth: 0.5)
                } else if i < filled {
                    ctx.fill(p, with: .color(Theme.memory.opacity(0.10)))
                    ctx.stroke(p, with: .color(Theme.memory.opacity(0.28)), lineWidth: 0.6)
                } else {
                    ctx.stroke(p, with: .color(.white.opacity(0.05)), lineWidth: 0.5)
                }
            }
            for (note, at) in recentWarm where w.memoryOn && sh.notes > 0 {  // read ahead off the SSD into RAM
                let i = tile(note, of: sh.notes, cols: cols)
                let t = CGRect(x: r.minX + labelW + CGFloat(i) * cw + 1.5, y: y + 2, width: cw - 3, height: rowH - 4)
                let a = max(0, 1 - now.timeIntervalSince(at) / 1.6) * 0.7
                ctx.fill(Path(roundedRect: t, cornerRadius: 2), with: .color(Theme.memory.opacity(a)))
            }
            if isChosen, let note = w.room, sh.notes > 0 {
                let i = tile(note, of: sh.notes, cols: cols)
                chosen = CGRect(x: r.minX + labelW + CGFloat(i) * cw + 1.5, y: y + 2, width: cw - 3, height: rowH - 4)
            }
        }
        if let c = chosen { glow(&ctx, c, now) }
        return chosen
    }

    private func tile(_ note: Int, of n: Int, cols: Int) -> Int {
        n <= cols ? min(note, cols - 1) : min(cols - 1, note * cols / n)
    }

    /// One memory with no shelves: its notes as one grid.
    private func drawGrid(_ ctx: inout GraphicsContext, _ r: CGRect, _ now: Date) -> CGRect? {
        let cw = r.width / CGFloat(roomCols), ch = r.height / CGFloat(roomRows)
        var tiles: [CGRect] = []
        for row in 0..<roomRows {
            for col in 0..<roomCols {
                tiles.append(CGRect(x: r.minX + CGFloat(col) * cw + 1.5, y: r.minY + CGFloat(row) * ch + 1.5,
                                    width: cw - 3, height: ch - 3))
            }
        }
        let filled = w.rooms == 0 ? 0 : min(tiles.count, max(1, w.rooms))
        for (i, t) in tiles.enumerated() {
            let p = Path(roundedRect: t, cornerRadius: 2)
            if !w.memoryOn {
                ctx.stroke(p, with: .color(.white.opacity(0.05)), lineWidth: 0.5)
            } else if i < filled {
                ctx.fill(p, with: .color(Theme.memory.opacity(0.10)))
                ctx.stroke(p, with: .color(Theme.memory.opacity(0.28)), lineWidth: 0.6)
            } else {
                ctx.stroke(p, with: .color(.white.opacity(0.06)), lineWidth: 0.5)
            }
        }
        guard w.memoryOn, let note = w.room, w.rooms > 0, w.roomAt != nil else { return nil }
        let c = tiles[tile(note, of: w.rooms, cols: tiles.count)]
        glow(&ctx, c, now)
        return c
    }

    /// The chosen note: bright, with a short beam when it was read up from the SSD.
    private func glow(_ ctx: inout GraphicsContext, _ tile: CGRect, _ now: Date) {
        guard let at = w.roomAt else { return }
        let heat = max(0.35, 1 - now.timeIntervalSince(at) / 2.5)
        let t = tile.insetBy(dx: -1, dy: -1)
        ctx.drawLayer { g in
            g.addFilter(.blur(radius: 6))
            g.fill(Path(roundedRect: t.insetBy(dx: -3, dy: -3), cornerRadius: 3), with: .color(Theme.memory.opacity(heat)))
        }
        ctx.fill(Path(roundedRect: t, cornerRadius: 2), with: .color(Theme.memory.opacity(0.4 + 0.6 * heat)))
        if w.tier == "ssd" {
            let p = Path { $0.move(to: CGPoint(x: t.midX, y: t.minY - 6)); $0.addLine(to: CGPoint(x: t.midX, y: t.minY)) }
            ctx.stroke(p, with: .color(Theme.memory.opacity(heat)), lineWidth: 1)
        }
    }

    private func columns(_ r: CGRect) -> [CGRect] {
        let n = max(1, w.layers)
        let cw = r.width / CGFloat(n)
        return (0..<n).map { CGRect(x: r.minX + CGFloat($0) * cw, y: r.minY, width: cw, height: r.height) }
    }

    private func drawLayers(_ ctx: inout GraphicsContext, _ cols: [CGRect], _ r: CGRect, _ now: Date) {
        let bins = WeightsModel.bins
        let resident = w.memoryOn && (w.residentUntil.map { $0 > now } ?? false)
        var hot: [(CGRect, Double)] = []
        for (i, col) in cols.enumerated() {
            let loaded = i < w.loadedLayers
            let ch = col.height / CGFloat(bins)
            let arrivedAge = w.arrived[i].map { now.timeIntervalSince($0) } ?? 99
            for j in 0..<bins {
                let cell = CGRect(x: col.minX + 1, y: col.minY + CGFloat(j) * ch + 0.75, width: col.width - 2,
                                  height: ch - 1.5)
                guard loaded else {
                    ctx.stroke(Path(cell), with: .color(.white.opacity(0.035)), lineWidth: 0.5)
                    continue
                }
                let a = i < w.act.count && j < w.act[i].count ? Double(w.act[i][j]) : 0
                var alpha = 0.07 + 0.88 * a
                if arrivedAge < 0.5 { alpha = max(alpha, 0.9 * (1 - arrivedAge / 0.5)) }  // the weights just arrived
                let color = arrivedAge < 0.25 ? Color.white : Theme.model
                ctx.fill(Path(cell), with: .color(color.opacity(alpha)))
                if a > 0.55 { hot.append((cell, a)) }
            }
            if resident {  // the room's keys and values are in this layer's attention
                let bar = CGRect(x: col.minX + 1, y: col.minY - 4, width: col.width - 2, height: 2)
                ctx.fill(Path(bar), with: .color(Theme.memory.opacity(0.85)))
            }
        }
        if !hot.isEmpty {
            ctx.drawLayer { g in
                g.addFilter(.blur(radius: 5))
                for (c, a) in hot { g.fill(Path(c.insetBy(dx: -1, dy: -1)), with: .color(Theme.model.opacity(0.7 * a))) }
            }
        }
    }

    /// The room's notes travelling down into every layer: one spark per layer, left to right, each arriving where
    /// that layer's attention will read it.
    private func drawFlow(_ ctx: inout GraphicsContext, from tile: CGRect, to cols: [CGRect], modelTop: CGFloat,
                          since: Double) {
        let travel = 0.55
        ctx.drawLayer { g in
            g.addFilter(.blur(radius: 3))
            for (i, col) in cols.enumerated() {
                let t = (since - Double(i) * 0.018) / travel
                guard t > 0, t < 1.15 else { continue }
                let e = min(1, t)
                let k = e * e * (3 - 2 * e)
                let start = CGPoint(x: tile.midX, y: tile.maxY)
                let end = CGPoint(x: col.midX, y: modelTop - 5)
                let ctrl = CGPoint(x: (start.x + end.x) / 2, y: start.y + (end.y - start.y) * 0.15)
                let p = point(start, ctrl, end, k)
                let fade = t > 1 ? max(0, 1 - (t - 1) / 0.15) : 1
                g.fill(Path(ellipseIn: CGRect(x: p.x - 2.5, y: p.y - 2.5, width: 5, height: 5)),
                       with: .color(Theme.memory.opacity(0.95 * fade)))
            }
        }
    }

    private func point(_ a: CGPoint, _ c: CGPoint, _ b: CGPoint, _ t: Double) -> CGPoint {
        let u = 1 - t
        return CGPoint(x: u * u * a.x + 2 * u * t * c.x + t * t * b.x, y: u * u * a.y + 2 * u * t * c.y + t * t * b.y)
    }
}
