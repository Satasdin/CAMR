import SwiftUI

/// What the weights view draws, fed only by what the engine measured: the model's layers as they load, the room an
/// answer reads (and whether it came from RAM or the SSD), and, for every word, how strongly each layer fired (32
/// numbers a layer, from camr_engine.live). Nothing here is made up: with no events, nothing moves.
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
    var roomAt: Date?  // when the room was chosen: its notes then flow into every layer
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

    func roomEvent(_ e: [String: Any]) {
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
        var parts = ["\(w.rooms) rooms"]
        if let r = w.room { parts.append("room \(r)") }
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
        return parts.isEmpty ? " " : parts.joined(separator: " · ")
    }

    // MARK: drawing

    private let roomCols = 16, roomRows = 5

    private func draw(_ ctx: inout GraphicsContext, _ size: CGSize, _ now: Date) {
        ctx.fill(Path(roundedRect: CGRect(origin: .zero, size: size), cornerRadius: 10), with: .color(Theme.ink))
        let pad: CGFloat = 10
        let memH = size.height * 0.24
        let gap = size.height * 0.14
        let memRect = CGRect(x: pad, y: pad, width: size.width - 2 * pad, height: memH - pad)
        let modelRect = CGRect(x: pad, y: memH + gap, width: size.width - 2 * pad, height: size.height - memH - gap - pad)
        let tiles = roomTiles(memRect)
        let chosen = chosenTile(tiles.count)
        drawRooms(&ctx, tiles, chosen, now)
        let cols = columns(modelRect)
        drawLayers(&ctx, cols, modelRect, now)
        if w.memoryOn, let at = w.roomAt, let c = chosen {
            drawFlow(&ctx, from: tiles[c], to: cols, modelTop: modelRect.minY, since: now.timeIntervalSince(at))
        }
    }

    private func roomTiles(_ r: CGRect) -> [CGRect] {
        let cw = r.width / CGFloat(roomCols), ch = r.height / CGFloat(roomRows)
        var out: [CGRect] = []
        for row in 0..<roomRows {
            for col in 0..<roomCols {
                out.append(CGRect(x: r.minX + CGFloat(col) * cw + 1.5, y: r.minY + CGFloat(row) * ch + 1.5,
                                  width: cw - 3, height: ch - 3))
            }
        }
        return out
    }

    private func chosenTile(_ n: Int) -> Int? {
        guard let room = w.room, w.rooms > 0 else { return nil }
        return min(n - 1, room * n / max(w.rooms, n) + (w.rooms < n ? 0 : 0))
    }

    private func drawRooms(_ ctx: inout GraphicsContext, _ tiles: [CGRect], _ chosen: Int?, _ now: Date) {
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
        guard w.memoryOn, let c = chosen, let at = w.roomAt else { return }
        let age = now.timeIntervalSince(at)
        let heat = max(0.35, 1 - age / 2.5)
        let t = tiles[c].insetBy(dx: -1, dy: -1)
        ctx.drawLayer { g in
            g.addFilter(.blur(radius: 6))
            g.fill(Path(roundedRect: t.insetBy(dx: -3, dy: -3), cornerRadius: 3), with: .color(Theme.memory.opacity(heat)))
        }
        ctx.fill(Path(roundedRect: t, cornerRadius: 2), with: .color(Theme.memory.opacity(0.4 + 0.6 * heat)))
        if w.tier == "ssd" {  // read up from the SSD: a short beam down from the tile
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
