import SwiftUI

/// What the weights view draws, fed only by what the engine measured: the model's layers as they load, the shelves
/// of memory and the room an answer reads (and whether it came from RAM or the SSD), the chunks a RAG answer pasted
/// in as text, how many tokens each answer read as text and how many it found already read as notes, and, for every
/// word, how strongly each layer fired (32 numbers a layer, from camr_engine.live). Nothing here is made up: with no
/// events, nothing moves. (The engine calls a note a room.)
@MainActor
final class WeightsModel: ObservableObject {
    static let bins = 32
    static let laneTokens = 2048.0  // the text lane's full width, the same for every answer so they compare

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
    @Published var mode = "camr"  // how this answer reads memory: camr (notes), rag (text) or off
    var memoryOn: Bool {
        get { mode != "off" }
        set { if !newValue { mode = "off" } else if mode == "off" { mode = "camr" } }
    }
    @Published var rooms = 0
    @Published var room: Int?
    @Published var tier: String?
    @Published var asleep = false
    @Published var roomBytes: Double = 0
    @Published var readBytes: Double = 0
    var roomAt: Date?  // when the room was chosen: its notes then flow into every layer
    @Published var shelf: String?  // the shelf the chosen room is on
    var shelves: [ShelfInfo] = []  // from the chat's state, in order
    var warmed: [String: [(Int, Date)]] = [:]  // rooms read ahead, by shelf: (room, when)
    @Published var warmBytes: Double = 0
    var residentUntil: Date?  // the room's keys and values sit in every layer's attention until the answer ends
    var chunks: [(shelf: String?, room: Int, tokens: Int)] = []  // a RAG answer's chunks, pasted in as text
    var chunksAt: Date?

    // what the model reads for this answer
    @Published var prefillTokens = 0  // read as text now
    @Published var prefillMemory = 0  // of which memory, as words
    @Published var notesTokens = 0  // found already read, as notes on the desk
    var prefillAt: Date?
    var firstTokenAt: Date?
    var prefillT: Double?  // the engine's own clock (seconds into the job) when it began reading the text…
    @Published var readSeconds: Double?  // …and how long until its first word, by the same clock

    // the answer
    var act: [[Float]] = []  // layers × bins, 0...1, as shown now
    // Each cell is read against its own usual level: a few of the hidden state's channels carry values far above
    // the rest in every layer, and one scale for the whole layer would show only them. A cell lights up as far as
    // it fires above its running mean, in units of its running spread, so only what stands out is bright.
    private var mean: [[Float]] = []
    private var spread: [[Float]] = []
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
        mean = []
        spread = []
        room = nil
        roomAt = nil
        residentUntil = nil
        chunks = []
        chunksAt = nil
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

    func loadDone() {
        loadingDone = true
        settleSoon()
    }

    var loading: Bool { loadedLayers < layers || !loadingDone }

    /// Shows the next layer that arrived, no faster than one every 40 ms, so a load from a warm disk (a tenth of a
    /// second) can still be followed by eye. The order and the sizes are the engine's.
    /// Nothing is changing: the view stops drawing, so an idle window costs nothing. It wakes for an answer, a load,
    /// or a few seconds after either while the layers cool.
    @Published var settled = true
    var watched = false  // the view is on screen: only then does the engine measure each layer for each word
    var idle: Bool { !answering && !loading && settled && pending.isEmpty }

    private func settleSoon(after seconds: Double = 4) {
        settled = false
        let mark = Date().addingTimeInterval(seconds)
        settleAt = mark
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds + 0.05) { [weak self] in
            guard let self, self.settleAt == mark else { return }
            self.settled = true
        }
    }
    private var settleAt = Date.distantPast
    private var idleShown = false

    /// Called once a second while the view is on screen: what the timeline is paused by can change with nothing
    /// published (the last layers of a load drain inside ``tick``), and it only reads ``idle`` when redrawn.
    func recheckIdle() {
        guard idle != idleShown else { return }
        idleShown = idle
        objectWillChange.send()
    }

    func tick(_ now: Date) {
        let pace = loadingDone ? 0.006 : 0.04  // once the engine is ready, what is left is shown at once
        if loadingDone, !pending.isEmpty, now.timeIntervalSince(lastShown) > 0.5 {
            // nobody watched the load (the view was hidden): every layer is simply there
            for (i, _) in pending { loadedLayers = max(loadedLayers, i + 1) }
            pending = []
        }
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

    func beginAnswer(memory: Bool) { beginAnswer(mode: memory ? "camr" : "off") }

    func beginAnswer(mode m: String) {
        mode = m
        answering = true
        words = 0
        firstWord = nil
        tps = nil
        room = nil
        roomAt = nil
        tier = nil
        asleep = false
        readBytes = 0
        residentUntil = nil
        chunks = []
        chunksAt = nil
        prefillTokens = 0
        prefillMemory = 0
        notesTokens = 0
        prefillAt = nil
        firstTokenAt = nil
        prefillT = nil
        readSeconds = nil
        if act.count != layers { act = Array(repeating: Array(repeating: 0, count: Self.bins), count: layers) }
    }

    func warmEvent(_ e: [String: Any]) {
        if settled { settleSoon() }
        switch e.str("kind") {
        case "warm":
            if let s = e.str("shelf"), let r = e.num("room") { warmed[s, default: []].append((Int(r), Date())) }
            warmBytes += e.num("bytes") ?? 0
        case "token":
            layersEvent(e["layers"] as? [[Double]], learn: false)
        default:
            break
        }
    }

    private func shelfName(_ reach: String?) -> String? { shelves.first(where: { $0.reach == reach })?.name }

    func roomEvent(_ e: [String: Any]) {
        shelf = shelfName(e.str("reach"))
        if let s = shelf, let i = shelves.firstIndex(where: { $0.name == s }), let n = e.num("rooms") {
            shelves[i].notes = Int(n)
        }
        rooms = Int(e.num("rooms") ?? Double(rooms))
        room = e.num("room").map(Int.init)
        tier = e.str("tier")
        asleep = (e["asleep"] as? Bool) ?? false
        roomBytes = e.num("bytes") ?? 0
        readBytes = e.num("read_bytes") ?? 0
        roomAt = Date()
        residentUntil = asleep ? nil : .distantFuture
    }

    func chunksEvent(_ e: [String: Any]) {
        chunks = e.list("chunks").map { c in
            (shelf: c.str("shelf"), room: Int(c.num("room") ?? 0), tokens: Int(c.num("tokens") ?? 0))
        }
        chunksAt = Date()
    }

    func prefillEvent(_ e: [String: Any]) {
        prefillTokens = Int(e.num("tokens") ?? 0)
        prefillMemory = Int(e.num("memory") ?? 0)
        notesTokens = Int(e.num("notes") ?? 0)
        prefillAt = Date()
        prefillT = e.num("t")
    }

    func layersEvent(_ rows: [[Double]]?, learn: Bool = true) {
        guard let rows, !rows.isEmpty else { return }
        if rows.count != layers { layers = rows.count }
        let fresh = Array(repeating: Array(repeating: Float(0), count: Self.bins), count: layers)
        if act.count != layers { act = fresh }
        if mean.count != layers {  // the first reading: each cell's spread starts at its layer's spread across cells
            mean = rows.map { $0.prefix(Self.bins).map { Float($0) } }
            spread = mean.map { row in
                let m = row.reduce(0, +) / Float(max(1, row.count))
                let mad = row.reduce(0) { $0 + abs($1 - m) } / Float(max(1, row.count))
                return row.map { _ in max(mad, 1e-4) }
            }
        }
        for (i, row) in rows.enumerated() where i < mean.count {
            // each cell against its own usual level; then, within the layer, only the cells that stand out from
            // the rest of it light up (a shift of the whole layer, or one huge channel, saturates nothing)
            let zs = row.prefix(Self.bins).enumerated().map { j, d in
                j < mean[i].count ? (Float(d) - mean[i][j]) / spread[i][j] : 0
            }
            let sorted = zs.sorted()
            let mid = sorted[sorted.count / 2]
            let top = sorted[min(sorted.count - 1, Int(Float(sorted.count) * 0.9))]
            let scale = max(top - mid, 0.75)
            for (j, z) in zs.enumerated() where j < act[i].count {
                act[i][j] = pow(min(1, max(0, (z - mid) / scale)), 1.3)
            }
            for (j, d) in row.prefix(Self.bins).enumerated() where j < mean[i].count {
                let v = Float(d)
                if learn {  // the usual level and spread follow the words written, slowly
                    mean[i][j] += (v - mean[i][j]) * 0.1
                    spread[i][j] += (abs(v - mean[i][j]) - spread[i][j]) * 0.1
                    spread[i][j] = max(spread[i][j], 1e-4)
                }
            }
        }
        lastToken = Date()
    }

    func token(_ e: [String: Any]) {
        words += 1
        if firstTokenAt == nil {
            firstTokenAt = Date()
            if let a = prefillT, let b = e.num("t") { readSeconds = max(0, b - a) }
        }
        layersEvent(e["layers"] as? [[Double]])
    }

    func finish(_ metric: [String: Any]?) {
        answering = false
        settleSoon()
        firstWord = metric?.num("first_word_s") ?? firstWord
        tps = metric?.num("decode_tps") ?? metric?.num("gen_tps")
        if let r = metric?.num("read_bytes") { readBytes = r }
        if residentUntil != nil { residentUntil = Date().addingTimeInterval(1.2) }
    }
}

struct ShelfInfo {
    let name: String
    let label: String
    let reach: String
    var notes: Int
}

/// The weights view, for a projector: the memory's shelves on top (each tile a share of a shelf's rooms), what this
/// answer reads in the middle (notes already read, against text read now, on one scale), and the model's layers
/// below (one column a layer, input on the left, 32 slices of its hidden state each). A CAMR answer's room flows
/// straight into every layer's attention; a RAG answer's chunks drop into the text lane and are read through the
/// layers from the first; with memory off, memory stays dark.
struct WeightsView: View {
    @ObservedObject var w: WeightsModel
    var large = false

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30, paused: w.idle)) { tl in
            let _ = w.tick(tl.date)
            panel(tl.date)
        }
        .onReceive(Timer.publish(every: 1, on: .main, in: .common).autoconnect()) { _ in w.recheckIdle() }
    }

    private var small: CGFloat { large ? 11 : 9.5 }

    private func panel(_ now: Date) -> some View {
        VStack(alignment: .leading, spacing: large ? 8 : 5) {
            HStack(spacing: 6) {
                Circle().fill(w.memoryOn ? Theme.memory : Theme.faint).frame(width: 7, height: 7)
                    .glow(Theme.memory, radius: w.memoryOn ? 4 : 0)
                Text("MEMORY · \(modeName)").font(Theme.mono(large ? 12 : 10, .semibold))
                    .foregroundStyle(w.memoryOn ? Theme.memory : Theme.faint)
                Spacer()
                Text(memoryLine).font(Theme.mono(small)).foregroundStyle(Theme.dim).lineLimit(1)
                    .minimumScaleFactor(0.7)
            }
            legend
            Canvas { ctx, size in draw(&ctx, size, now) }
                .frame(minHeight: large ? 420 : 260)
            HStack(spacing: 6) {
                Circle().fill(Theme.model).frame(width: 7, height: 7).glow(Theme.model, radius: 4)
                Text("MODEL").font(Theme.mono(large ? 12 : 10, .semibold)).foregroundStyle(Theme.model)
                Spacer()
                Text(modelLine).font(Theme.mono(small)).foregroundStyle(Theme.dim).lineLimit(1)
            }
            Text(statsLine).font(Theme.mono(small)).foregroundStyle(Theme.faint).lineLimit(1)
                .minimumScaleFactor(0.7)
        }
    }

    private var modeName: String {
        switch w.mode {
        case "rag": return "RAG"
        case "off": return "OFF"
        default: return "CAMR"
        }
    }

    private var legend: some View {
        let items: [(AnyView, String)] = [
            (AnyView(RoundedRectangle(cornerRadius: 2).fill(Theme.memory)), "memory as notes · already read"),
            (AnyView(RoundedRectangle(cornerRadius: 2).stroke(Theme.memory, lineWidth: 1.2)), "memory as text · read now"),
            (AnyView(RoundedRectangle(cornerRadius: 2).fill(Theme.model)), "layer activity · bright = stands out"),
        ]
        let row = ForEach(Array(items.enumerated()), id: \.offset) { _, it in
            HStack(spacing: 5) {
                it.0.frame(width: 10, height: 10)
                Text(it.1).font(Theme.mono(small)).foregroundStyle(Theme.dim).lineLimit(1)
            }
        }
        return Group {
            if large {
                HStack(spacing: 18) { row }
            } else {
                VStack(alignment: .leading, spacing: 3) { row }
            }
        }
    }

    var memoryLine: String {
        guard w.memoryOn else { return "the model alone · nothing read" }
        let total = w.shelves.isEmpty ? w.rooms : w.shelves.reduce(0) { $0 + $1.notes }
        var parts = [w.shelves.isEmpty ? "\(total) rooms" : "\(w.shelves.count) shelves · \(total) rooms"]
        if w.mode == "rag", !w.chunks.isEmpty {
            parts.append("\(w.chunks.count) chunks · \(w.chunks.reduce(0) { $0 + $1.tokens }) tokens as text")
        } else if let r = w.room {
            parts.append("room \(r)" + (shelfLabel(w.shelf).map { " on \($0)" } ?? "") + " · " + tierText)
        }
        return parts.joined(separator: " · ")
    }

    private var tierText: String {
        if w.asleep { return "asleep · read as words" }
        switch w.tier {
        case "ssd": return "read from SSD"
        case "ram": return "hot in RAM"
        case nil: return ""
        default: return "read as words"
        }
    }

    private func shelfLabel(_ name: String?) -> String? { w.shelves.first(where: { $0.name == name })?.label }

    var modelLine: String {
        var parts = [w.modelName, "\(w.layers) layers"]
        if w.modelBytes > 0 { parts.append(bytesText(w.modelBytes)) }
        if w.loading { parts.append("loading \(w.loadedLayers)/\(w.layers)") }
        return parts.filter { !$0.isEmpty }.joined(separator: " · ")
    }

    var statsLine: String {
        var parts: [String] = []
        if let f = w.firstWord { parts.append("first word \(secondsText(f))") }
        if w.prefillTokens > 0 { parts.append("\(w.prefillTokens) tokens read as text") }
        if w.notesTokens > 0 { parts.append("\(w.notesTokens) as notes") }
        if let t = w.tps { parts.append(String(format: "%.0f tok/s", t)) }
        if w.memoryOn, w.readBytes > 0 { parts.append("SSD \(bytesText(w.readBytes))") }
        if let s = w.loadSeconds, parts.isEmpty { parts.append("weights read in \(secondsText(s))") }
        if parts.isEmpty, w.warmBytes > 0 { parts.append("warmed \(bytesText(w.warmBytes)) of notes into RAM") }
        return parts.isEmpty ? " " : parts.joined(separator: " · ")
    }

    // MARK: drawing

    private func label(_ s: String, _ size: CGFloat, _ color: Color, _ weight: Font.Weight = .semibold) -> Text {
        Text(s).font(Theme.mono(size, weight)).foregroundColor(color)
    }

    private func draw(_ ctx: inout GraphicsContext, _ size: CGSize, _ now: Date) {
        ctx.fill(Path(roundedRect: CGRect(origin: .zero, size: size), cornerRadius: 10), with: .color(Theme.ink))
        let pad: CGFloat = large ? 14 : 8
        let f: CGFloat = large ? 11 : 8.5
        let memH = size.height * 0.27
        let laneH: CGFloat = large ? 54 : 40
        let gap = size.height * (large ? 0.11 : 0.09)
        let axisH: CGFloat = f + 18
        let memRect = CGRect(x: pad, y: pad, width: size.width - 2 * pad, height: memH - pad)
        let laneRect = CGRect(x: pad, y: memH + 8, width: size.width - 2 * pad, height: laneH)
        let modelTop = laneRect.maxY + gap
        let modelRect = CGRect(x: pad, y: modelTop, width: size.width - 2 * pad,
                               height: size.height - modelTop - pad - axisH)
        let tiles = w.shelves.isEmpty ? drawGrid(&ctx, memRect, now) : drawShelves(&ctx, memRect, now)
        let lane = drawLane(&ctx, laneRect, now, f)
        let cols = columns(modelRect)
        drawLayers(&ctx, cols, modelRect, now)
        drawAxis(&ctx, cols, CGRect(x: pad, y: modelRect.maxY + 4, width: modelRect.width, height: axisH), f)
        if w.mode == "camr", let at = w.roomAt, let c = tiles.room, !w.asleep {
            drawFlow(&ctx, from: c, to: cols, modelTop: modelRect.minY, since: now.timeIntervalSince(at))
        }
        if w.mode == "camr", let c = tiles.room { roomCallout(&ctx, c, memRect, f) }
        if w.mode == "rag", let at = w.chunksAt {
            drawDrops(&ctx, from: tiles.chunks, to: lane, since: now.timeIntervalSince(at))
        }
        drawReading(&ctx, lane: lane, cols: cols, modelTop: modelRect.minY, now)
    }

    /// One row a shelf: its name and size, then its rooms as tiles (each tile stands for an equal share of them).
    /// Returns the chosen room's tile and the tiles of a RAG answer's chunks.
    private func drawShelves(_ ctx: inout GraphicsContext, _ r: CGRect, _ now: Date) -> (room: CGRect?, chunks: [CGRect]) {
        let labelW: CGFloat = min(large ? 150 : 92, r.width * 0.3)
        let rowH = r.height / CGFloat(w.shelves.count)
        let cols = max(6, Int((r.width - labelW) / max(9, rowH * 0.9)))
        let cw = (r.width - labelW) / CGFloat(cols)
        var chosen: CGRect?
        var chunkTiles: [CGRect] = []
        func tileRect(_ i: Int, _ y: CGFloat) -> CGRect {
            CGRect(x: r.minX + labelW + CGFloat(i) * cw + 1.5, y: y + 2, width: cw - 3, height: rowH - 4)
        }
        for (k, sh) in w.shelves.enumerated() {
            let y = r.minY + CGFloat(k) * rowH
            let isChosen = w.mode == "camr" && sh.name == w.shelf && w.roomAt != nil
            let hasChunks = w.mode == "rag" && w.chunks.contains(where: { $0.shelf == sh.name })
            let color = !w.memoryOn ? Theme.faint : (isChosen || hasChunks) ? Theme.memory : Theme.dim
            ctx.draw(label("\(sh.label.uppercased())", large ? 11 : 8.5, color), at: CGPoint(x: r.minX, y: y + rowH / 2),
                     anchor: .leading)
            ctx.draw(label("\(sh.notes)", large ? 10 : 8, Theme.faint, .regular),
                     at: CGPoint(x: r.minX + labelW - 6, y: y + rowH / 2), anchor: .trailing)
            let filled = min(cols, sh.notes)
            let recentWarm = (w.warmed[sh.name] ?? []).filter { now.timeIntervalSince($0.1) < 1.6 }
            for i in 0..<cols {
                let p = Path(roundedRect: tileRect(i, y), cornerRadius: 2)
                if !w.memoryOn {
                    ctx.stroke(p, with: .color(.white.opacity(0.05)), lineWidth: 0.5)
                } else if i < filled {
                    ctx.fill(p, with: .color(Theme.memory.opacity(0.09)))
                    ctx.stroke(p, with: .color(Theme.memory.opacity(0.25)), lineWidth: 0.6)
                } else {
                    ctx.stroke(p, with: .color(.white.opacity(0.05)), lineWidth: 0.5)
                }
            }
            for (note, at) in recentWarm where w.memoryOn && sh.notes > 0 {  // read ahead off the SSD into RAM
                let a = max(0, 1 - now.timeIntervalSince(at) / 1.6) * 0.7
                ctx.fill(Path(roundedRect: tileRect(tile(note, of: sh.notes, cols: cols), y), cornerRadius: 2),
                         with: .color(Theme.memory.opacity(a)))
            }
            if isChosen, let note = w.room, sh.notes > 0 {
                chosen = tileRect(tile(note, of: sh.notes, cols: cols), y)
            }
            if hasChunks, sh.notes > 0 {
                for c in w.chunks where c.shelf == sh.name {
                    chunkTiles.append(tileRect(tile(c.room, of: sh.notes, cols: cols), y))
                }
            }
        }
        if let c = chosen { glow(&ctx, c, now) }
        for c in chunkTiles {  // pasted as text: outlined, not filled
            ctx.stroke(Path(roundedRect: c.insetBy(dx: -1, dy: -1), cornerRadius: 2),
                       with: .color(Theme.memory.opacity(0.95)), lineWidth: 1.4)
        }
        return (chosen, chunkTiles)
    }

    private func tile(_ note: Int, of n: Int, cols: Int) -> Int {
        n <= cols ? min(note, cols - 1) : min(cols - 1, note * cols / n)
    }

    /// One memory with no shelves: its rooms as one grid.
    private func drawGrid(_ ctx: inout GraphicsContext, _ r: CGRect, _ now: Date) -> (room: CGRect?, chunks: [CGRect]) {
        let roomCols = 16, roomRows = 5
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
            if w.memoryOn && i < filled {
                ctx.fill(p, with: .color(Theme.memory.opacity(0.09)))
                ctx.stroke(p, with: .color(Theme.memory.opacity(0.25)), lineWidth: 0.6)
            } else {
                ctx.stroke(p, with: .color(.white.opacity(0.05)), lineWidth: 0.5)
            }
        }
        var chunkTiles: [CGRect] = []
        if w.mode == "rag", w.rooms > 0 {
            for c in w.chunks { chunkTiles.append(tiles[tile(c.room, of: w.rooms, cols: tiles.count)]) }
            for c in chunkTiles {
                ctx.stroke(Path(roundedRect: c, cornerRadius: 2), with: .color(Theme.memory.opacity(0.95)), lineWidth: 1.4)
            }
        }
        guard w.mode == "camr", let note = w.room, w.rooms > 0, w.roomAt != nil else { return (nil, chunkTiles) }
        let c = tiles[tile(note, of: w.rooms, cols: tiles.count)]
        glow(&ctx, c, now)
        return (c, chunkTiles)
    }

    /// The chosen room: bright, with a short beam when it was read up from the SSD.
    private func glow(_ ctx: inout GraphicsContext, _ tile: CGRect, _ now: Date) {
        guard let at = w.roomAt else { return }
        let heat = max(0.45, 1 - now.timeIntervalSince(at) / 2.5)
        let t = tile.insetBy(dx: -1, dy: -1)
        ctx.drawLayer { g in
            g.addFilter(.blur(radius: 6))
            g.fill(Path(roundedRect: t.insetBy(dx: -3, dy: -3), cornerRadius: 3), with: .color(Theme.memory.opacity(heat)))
        }
        if w.asleep {  // asleep: its words are read, so it is outlined like text
            ctx.stroke(Path(roundedRect: t, cornerRadius: 2), with: .color(Theme.memory), lineWidth: 1.4)
        } else {
            ctx.fill(Path(roundedRect: t, cornerRadius: 2), with: .color(Theme.memory.opacity(0.5 + 0.5 * heat)))
        }
    }

    /// "room 412 · RAM", beside the chosen room, kept inside the memory's area.
    private func roomCallout(_ ctx: inout GraphicsContext, _ tile: CGRect, _ r: CGRect, _ f: CGFloat) {
        guard let room = w.room else { return }
        let tierShort = w.asleep ? "asleep · as words" : w.tier == "ssd" ? "SSD" : w.tier == "ram" ? "RAM" : "words"
        let text = label("room \(room) · \(tierShort)", f, Theme.memory)
        let right = tile.maxX + 150 < r.maxX
        let at = CGPoint(x: right ? tile.maxX + 6 : tile.minX - 6, y: tile.midY)
        var bg = ctx
        bg.opacity = 0.85
        let wEst = CGFloat(("room \(room) · \(tierShort)").count) * f * 0.62
        let box = CGRect(x: right ? at.x - 3 : at.x - wEst - 3, y: at.y - f * 0.8, width: wEst + 6, height: f * 1.6)
        bg.fill(Path(roundedRect: box, cornerRadius: 3), with: .color(Theme.ink))
        ctx.draw(text, at: at, anchor: right ? .leading : .trailing)
    }

    /// What this answer reads, on one scale for every answer: notes already read (filled cyan) and text read now
    /// (memory as words outlined in cyan, the instructions, conversation and question in white). Returns the text
    /// bar's rectangle.
    private func drawLane(_ ctx: inout GraphicsContext, _ r: CGRect, _ now: Date, _ f: CGFloat) -> CGRect {
        let labelW: CGFloat = large ? 150 : 92
        let barX = r.minX + labelW
        let barW = r.width - labelW
        let rowH = (r.height - 6) / 2
        let scale = barW / CGFloat(WeightsModel.laneTokens)
        let notesY = r.minY, textY = r.minY + rowH + 6
        ctx.draw(label("NOTES", f, w.notesTokens > 0 ? Theme.memory : Theme.faint),
                 at: CGPoint(x: r.minX, y: notesY + rowH / 2), anchor: .leading)
        ctx.draw(label("TEXT", f, w.prefillTokens > 0 ? Theme.text : Theme.faint),
                 at: CGPoint(x: r.minX, y: textY + rowH / 2), anchor: .leading)
        ctx.draw(label("already read", f - 1.5, Theme.faint, .regular),
                 at: CGPoint(x: barX - 6, y: notesY + rowH / 2), anchor: .trailing)
        ctx.draw(label("read now", f - 1.5, Theme.faint, .regular),
                 at: CGPoint(x: barX - 6, y: textY + rowH / 2), anchor: .trailing)
        for y in [notesY, textY] {  // the track
            ctx.fill(Path(roundedRect: CGRect(x: barX, y: y, width: barW, height: rowH), cornerRadius: 3),
                     with: .color(.white.opacity(0.03)))
        }
        if w.notesTokens > 0 {
            let nw = min(barW, CGFloat(w.notesTokens) * scale)
            let nr = CGRect(x: barX, y: notesY, width: nw, height: rowH)
            ctx.fill(Path(roundedRect: nr, cornerRadius: 3), with: .color(Theme.memory.opacity(0.85)))
            ctx.draw(label("\(w.notesTokens) tokens", f, Theme.memory), at: CGPoint(x: nr.maxX + 6, y: nr.midY),
                     anchor: .leading)
        }
        var textRect = CGRect(x: barX, y: textY, width: 2, height: rowH)
        if w.prefillTokens > 0 {
            let mw = min(barW, CGFloat(w.prefillMemory) * scale)
            let tw = min(barW, CGFloat(w.prefillTokens) * scale)
            textRect = CGRect(x: barX, y: textY, width: max(2, tw), height: rowH)
            // the text as tokens: one tick each few tokens
            let tick: CGFloat = 3
            var x = barX
            while x < barX + tw {
                let isMemory = x < barX + mw
                let t = CGRect(x: x, y: textY + 1, width: tick - 1, height: rowH - 2)
                if isMemory {
                    ctx.stroke(Path(t), with: .color(Theme.memory.opacity(0.9)), lineWidth: 0.8)
                } else {
                    ctx.fill(Path(t), with: .color(.white.opacity(0.55)))
                }
                x += tick
            }
            ctx.draw(label("\(w.prefillTokens) tokens" + (w.prefillMemory > 0 ? " · \(w.prefillMemory) of memory" : ""),
                           f, Theme.text), at: CGPoint(x: min(textRect.maxX + 6, r.maxX - 4), y: textRect.midY),
                     anchor: textRect.maxX + 160 < r.maxX ? .leading : .trailing)
        }
        return textRect
    }

    private func columns(_ r: CGRect) -> [CGRect] {
        let n = max(1, w.layers)
        let cw = r.width / CGFloat(n)
        return (0..<n).map { CGRect(x: r.minX + CGFloat($0) * cw, y: r.minY, width: cw, height: r.height) }
    }

    private func drawLayers(_ ctx: inout GraphicsContext, _ cols: [CGRect], _ r: CGRect, _ now: Date) {
        let bins = WeightsModel.bins
        let resident = w.mode == "camr" && (w.residentUntil.map { $0 > now } ?? false)
        var hot: [(CGRect, Double)] = []
        let barH = r.height * 0.14  // each layer's mean activity, a small bar under its cells
        let cellsH = r.height - barH - 6
        for (i, col) in cols.enumerated() {
            let loaded = i < w.loadedLayers
            let ch = cellsH / CGFloat(bins)
            let arrivedAge = w.arrived[i].map { now.timeIntervalSince($0) } ?? 99
            var sum = 0.0
            for j in 0..<bins {
                let cell = CGRect(x: col.minX + 1, y: col.minY + CGFloat(j) * ch + 0.5, width: col.width - 2,
                                  height: max(1, ch - 1))
                guard loaded else {
                    ctx.stroke(Path(cell), with: .color(.white.opacity(0.035)), lineWidth: 0.5)
                    continue
                }
                let a = i < w.act.count && j < w.act[i].count ? Double(w.act[i][j]) : 0
                sum += a
                var alpha = 0.06 + 0.84 * a
                if arrivedAge < 0.5 { alpha = max(alpha, 0.9 * (1 - arrivedAge / 0.5)) }  // the weights just arrived
                let color = arrivedAge < 0.25 ? Color.white : Theme.model
                ctx.fill(Path(cell), with: .color(color.opacity(alpha)))
                if a > 0.6 { hot.append((cell, a)) }
            }
            if loaded {
                let mean = sum / Double(bins)
                let h = max(1, barH * CGFloat(min(1, mean * 2.5)))
                let bar = CGRect(x: col.minX + 1, y: r.maxY - h, width: col.width - 2, height: h)
                ctx.fill(Path(bar), with: .color(Theme.model.opacity(0.35 + 0.5 * min(1, mean * 3))))
            }
            if resident {  // the room's keys and values are in this layer's attention
                let bar = CGRect(x: col.minX + 1, y: col.minY - 5, width: col.width - 2, height: 3)
                ctx.fill(Path(bar), with: .color(Theme.memory.opacity(0.9)))
            }
        }
        if !hot.isEmpty {
            ctx.drawLayer { g in
                g.addFilter(.blur(radius: 4))
                for (c, a) in hot { g.fill(Path(c.insetBy(dx: -1, dy: -1)), with: .color(Theme.model.opacity(0.5 * a))) }
            }
        }
    }

    private func drawAxis(_ ctx: inout GraphicsContext, _ cols: [CGRect], _ r: CGRect, _ f: CGFloat) {
        guard let first = cols.first, let last = cols.last else { return }
        ctx.draw(label("layer 1 · input", f, Theme.faint, .regular), at: CGPoint(x: first.minX, y: r.minY + f),
                 anchor: .leading)
        ctx.draw(label("layer \(cols.count) · output", f, Theme.faint, .regular), at: CGPoint(x: last.maxX, y: r.minY + f),
                 anchor: .trailing)
        ctx.draw(label("each column a layer · 32 slices of its hidden state · bar: mean", f - 1, Theme.faint, .regular),
                 at: CGPoint(x: (first.minX + last.maxX) / 2, y: r.minY + f), anchor: .center)
    }

    /// The room's notes travelling down into every layer at once: a stream of sparks per layer, each arriving where
    /// that layer's attention will read it.
    private func drawFlow(_ ctx: inout GraphicsContext, from tile: CGRect, to cols: [CGRect], modelTop: CGFloat,
                          since: Double) {
        let travel = 0.7
        guard since < 2.2 else { return }
        ctx.drawLayer { g in
            g.addFilter(.blur(radius: 2.5))
            for (i, col) in cols.enumerated() {
                for k in 0..<3 {  // a short trail
                    let t = (since - Double(i) * 0.012 - Double(k) * 0.05) / travel
                    guard t > 0, t < 1.2 else { continue }
                    let e = min(1, t)
                    let s = e * e * (3 - 2 * e)
                    let start = CGPoint(x: tile.midX, y: tile.maxY)
                    let end = CGPoint(x: col.midX, y: modelTop - 6)
                    let ctrl = CGPoint(x: (start.x + end.x) / 2, y: start.y + (end.y - start.y) * 0.1)
                    let p = point(start, ctrl, end, s)
                    let fade = (t > 1 ? max(0, 1 - (t - 1) / 0.2) : 1) * (1 - Double(k) * 0.3)
                    let d: CGFloat = k == 0 ? 5 : 3.5
                    g.fill(Path(ellipseIn: CGRect(x: p.x - d / 2, y: p.y - d / 2, width: d, height: d)),
                           with: .color(Theme.memory.opacity(0.95 * fade)))
                }
            }
        }
    }

    /// A RAG answer's chunks dropping from their shelves into the text lane, as text.
    private func drawDrops(_ ctx: inout GraphicsContext, from tiles: [CGRect], to lane: CGRect, since: Double) {
        let travel = 0.6
        guard since < 1.6, !tiles.isEmpty else { return }
        for (i, tile) in tiles.enumerated() {
            let t = (since - Double(i) * 0.05) / travel
            guard t > 0, t < 1.25 else { continue }
            let e = min(1, t)
            let s = e * e * (3 - 2 * e)
            let end = CGPoint(x: lane.minX + lane.width * CGFloat(Double(i) + 0.5) / CGFloat(tiles.count), y: lane.midY)
            let start = CGPoint(x: tile.midX, y: tile.maxY)
            let p = CGPoint(x: start.x + (end.x - start.x) * s, y: start.y + (end.y - start.y) * s)
            let fade = t > 1 ? max(0, 1 - (t - 1) / 0.25) : 1
            let r = CGRect(x: p.x - 6, y: p.y - 3, width: 12, height: 6)
            ctx.stroke(Path(roundedRect: r, cornerRadius: 1.5), with: .color(Theme.memory.opacity(fade)), lineWidth: 1.2)
        }
    }

    /// Text being read: from the moment the engine says what it will read until the first word arrives (both
    /// measured), a wave runs from the text lane through the layers, input to output. It stops at the first word.
    private func drawReading(_ ctx: inout GraphicsContext, lane: CGRect, cols: [CGRect], modelTop: CGFloat,
                             _ now: Date) {
        guard let at = w.prefillAt, w.prefillTokens > 0, !cols.isEmpty else { return }
        let end = w.firstTokenAt ?? now
        let elapsed = end.timeIntervalSince(at)
        let reading = w.firstTokenAt == nil
        let after = w.firstTokenAt.map { now.timeIntervalSince($0) } ?? 0
        guard reading || after < 0.6 else { return }
        let fade = reading ? 1.0 : max(0, 1 - after / 0.6)
        // the text enters at layer 1
        let first = cols[0]
        let entry = Path { p in
            p.move(to: CGPoint(x: lane.minX + 2, y: lane.maxY))
            p.addQuadCurve(to: CGPoint(x: first.midX, y: modelTop - 6),
                           control: CGPoint(x: lane.minX, y: (lane.maxY + modelTop) / 2))
        }
        ctx.stroke(entry, with: .color(.white.opacity(0.45 * fade)), style: StrokeStyle(lineWidth: 1.2, dash: [3, 3]))
        // a wave across the layers: each layer reads the whole text in turn
        let period = 0.45
        let pos = (elapsed.truncatingRemainder(dividingBy: period)) / period
        let x = cols[0].minX + (cols.last!.maxX - cols[0].minX) * CGFloat(reading ? pos : 1)
        let band = CGRect(x: x - 14, y: modelTop - 2, width: 28, height: cols[0].height + 4)
        ctx.drawLayer { g in
            g.addFilter(.blur(radius: 10))
            g.fill(Path(band), with: .color(.white.opacity(0.18 * fade)))
        }
        let said = reading ? "reading \(w.prefillTokens) tokens of text into layer 1…"
            : "read \(w.prefillTokens) tokens of text" + (w.readSeconds.map { String(format: " · first word %.2f s later", $0) } ?? "")
        let t = label(said, large ? 11 : 9, .white.opacity(0.85 * fade))
        ctx.draw(t, at: CGPoint(x: first.minX, y: modelTop - (large ? 16 : 13)), anchor: .leading)
    }

    private func point(_ a: CGPoint, _ c: CGPoint, _ b: CGPoint, _ t: Double) -> CGPoint {
        let u = 1 - t
        return CGPoint(x: u * u * a.x + 2 * u * t * c.x + t * t * b.x, y: u * u * a.y + 2 * u * t * c.y + t * t * b.y)
    }
}
