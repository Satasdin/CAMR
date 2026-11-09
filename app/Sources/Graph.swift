import AppKit
import BurrowCore
import SwiftUI

struct GraphFilter: Equatable {
    var showNotes = true
    var showFiles = true
    var showOrphans = true
    var query = ""
}

/// The living graph. Every star is a real file or note. Linked things pull together, everything else pushes apart,
/// and folders gather into their own clusters.
final class GraphSim: @unchecked Sendable {
    struct Node {
        let path: String
        let name: String
        let isNote: Bool
        let group: Int
        let degree: Int
    }

    private let lock = NSLock()
    private(set) var nodes: [Node] = []
    private(set) var edges: [(a: Int, b: Int)] = []
    private(set) var index: [String: Int] = [:]
    private(set) var neighbours: [[Int]] = []
    private(set) var groupNames: [String] = []
    var x: [CGFloat] = []
    var y: [CGFloat] = []
    private var vx: [CGFloat] = []
    private var vy: [CGFloat] = []
    private(set) var pinned: Int?
    private(set) var heat: CGFloat = 0

    var isMoving: Bool { heat > 0.015 }

    func colour(_ group: Int) -> Color {
        guard groupNames.indices.contains(group), group < Theme.clusters.count else { return Theme.otherCluster }
        return Theme.clusters[group]
    }

    /// Takes in a new map. Things already placed stay where they are.
    func load(_ map: ProjectMap) {
        lock.lock()
        defer { lock.unlock() }
        var old: [String: (CGFloat, CGFloat)] = [:]
        for (place, node) in nodes.enumerated() { old[node.path] = (x[place], y[place]) }

        var degree: [String: Int] = [:]
        for link in map.links {
            degree[link.from, default: 0] += 1
            degree[link.to, default: 0] += 1
        }
        func top(_ path: String) -> String { path.contains("/") ? String(path.split(separator: "/")[0]) : "" }
        var sizes: [String: Int] = [:]
        for file in map.files { sizes[top(file.path), default: 0] += 1 }
        let order = sizes.keys.sorted { (sizes[$0]!, $1) > (sizes[$1]!, $0) }
        let groupOf = Dictionary(uniqueKeysWithValues: order.enumerated().map { ($1, $0) })
        groupNames = order

        nodes = map.files.map { Node(path: $0.path, name: $0.path.title, isNote: $0.isNote, group: groupOf[top($0.path)] ?? 0, degree: degree[$0.path] ?? 0) }
        index = Dictionary(uniqueKeysWithValues: nodes.enumerated().map { ($1.path, $0) })
        var seen = Set<[Int]>()
        edges = []
        neighbours = Array(repeating: [], count: nodes.count)
        for link in map.links {
            guard let a = index[link.from], let b = index[link.to], a != b, seen.insert([min(a, b), max(a, b)]).inserted else { continue }
            edges.append((a, b))
            neighbours[a].append(b)
            neighbours[b].append(a)
        }

        x = Array(repeating: 0, count: nodes.count)
        y = x
        vx = x
        vy = x
        var anyNew = false
        var inGroup: [Int: Int] = [:]
        for (place, node) in nodes.enumerated() {
            if let known = old[node.path] {
                (x[place], y[place]) = known
                continue
            }
            anyNew = true
            // Each folder starts on its own arm of a spiral, so the first picture is already in clusters.
            let arm = Double(node.group) * 2.399963
            let reach = 160 * sqrt(Double(node.group))
            let turn = inGroup[node.group, default: 0]
            inGroup[node.group] = turn + 1
            let spread = 14 * sqrt(Double(turn) + 0.5)
            let spin = Double(turn) * 2.399963
            x[place] = CGFloat(reach * cos(arm) + spread * cos(spin))
            y[place] = CGFloat(reach * sin(arm) + spread * sin(spin))
        }
        if anyNew {
            // Settle before the first picture, so it opens calm instead of exploding outwards.
            heat = 1
            let rounds = nodes.count > 3000 ? 60 : 180
            for _ in 0..<rounds { stepLocked() }
            heat = 0
        }
    }

    func step() {
        lock.lock()
        defer { lock.unlock() }
        stepLocked()
    }

    private func stepLocked() {
        let count = nodes.count
        guard count > 1, heat > 0.005 else { return }
        var fx = [CGFloat](repeating: 0, count: count)
        var fy = fx

        // Near things push apart. A grid keeps this quick on a big vault.
        let cell: CGFloat = 90
        var grid: [Int64: [Int]] = [:]
        grid.reserveCapacity(count)
        func key(_ a: Int, _ b: Int) -> Int64 { Int64(a) << 32 ^ Int64(UInt32(truncatingIfNeeded: b)) }
        for i in 0..<count { grid[key(Int(floor(x[i] / cell)), Int(floor(y[i] / cell))), default: []].append(i) }
        for i in 0..<count {
            let cx = Int(floor(x[i] / cell))
            let cy = Int(floor(y[i] / cell))
            for gx in (cx - 1)...(cx + 1) {
                for gy in (cy - 1)...(cy + 1) {
                    guard let members = grid[key(gx, gy)] else { continue }
                    for j in members where j > i {
                        var dx = x[i] - x[j]
                        var dy = y[i] - y[j]
                        var d2 = dx * dx + dy * dy
                        if d2 < 1 {
                            dx = CGFloat(i % 7) - 3 + 0.5
                            dy = CGFloat(j % 5) - 2 + 0.5
                            d2 = dx * dx + dy * dy
                        }
                        let push = 900 / d2
                        fx[i] += dx * push; fy[i] += dy * push
                        fx[j] -= dx * push; fy[j] -= dy * push
                    }
                }
            }
        }

        // Links pull together.
        for edge in edges {
            let dx = x[edge.b] - x[edge.a]
            let dy = y[edge.b] - y[edge.a]
            let d = max(1, sqrt(dx * dx + dy * dy))
            let pull = (d - 46) / d * 0.035
            fx[edge.a] += dx * pull; fy[edge.a] += dy * pull
            fx[edge.b] -= dx * pull; fy[edge.b] -= dy * pull
        }

        // Each folder gathers around its middle, and the whole sky drifts gently to the centre.
        var sumX = [CGFloat](repeating: 0, count: groupNames.count)
        var sumY = sumX
        var total = sumX
        for i in 0..<count {
            sumX[nodes[i].group] += x[i]
            sumY[nodes[i].group] += y[i]
            total[nodes[i].group] += 1
        }
        for i in 0..<count {
            let g = nodes[i].group
            fx[i] += (sumX[g] / total[g] - x[i]) * 0.018 - x[i] * 0.0035
            fy[i] += (sumY[g] / total[g] - y[i]) * 0.018 - y[i] * 0.0035
        }

        for i in 0..<count where i != pinned {
            vx[i] = (vx[i] + fx[i] * heat) * 0.8
            vy[i] = (vy[i] + fy[i] * heat) * 0.8
            x[i] += min(30, max(-30, vx[i]))
            y[i] += min(30, max(-30, vy[i]))
        }
        heat *= 0.985
    }

    func pin(_ node: Int, x newX: CGFloat, y newY: CGFloat) {
        lock.lock()
        defer { lock.unlock() }
        guard x.indices.contains(node) else { return }
        pinned = node
        x[node] = newX
        y[node] = newY
        heat = max(heat, 0.35)
    }

    func release() {
        lock.lock()
        defer { lock.unlock() }
        pinned = nil
    }

    func withPositions<T>(_ body: () -> T) -> T {
        lock.lock()
        defer { lock.unlock() }
        return body()
    }

    /// The middle of each folder's stars, for its name.
    func groupCentres() -> [(name: String, x: CGFloat, y: CGFloat, top: CGFloat, count: Int, group: Int)] {
        var out: [Int: (x: CGFloat, y: CGFloat, top: CGFloat, n: Int)] = [:]
        for (place, node) in nodes.enumerated() {
            let old = out[node.group] ?? (0, 0, .greatestFiniteMagnitude, 0)
            out[node.group] = (old.x + x[place], old.y + y[place], min(old.top, y[place]), old.n + 1)
        }
        return out.compactMap { group, value in
            guard groupNames.indices.contains(group), !groupNames[group].isEmpty else { return nil }
            return (groupNames[group], value.x / CGFloat(value.n), value.y / CGFloat(value.n), value.top, value.n, group)
        }
    }
}

struct GraphPage: View {
    @Bindable var workspace: Workspace
    @State private var question = ""

    var body: some View {
        ZStack(alignment: .bottom) {
            GraphCanvas(workspace: workspace, compact: false)
            VStack(spacing: 10) {
                if !workspace.lit.isEmpty { ReadingStrip(workspace: workspace) }
                AskField(workspace: workspace, text: $question, prompt: "Ask your vault", wantsChange: nil, staysHere: true)
            }
            .frame(maxWidth: 620)
            .padding(18)
        }
        .overlay(alignment: .topLeading) { GraphControls(workspace: workspace).padding(12) }
        .background(Color.black)
    }
}

struct GraphControls: View {
    @Bindable var workspace: Workspace

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            TextField("Filter", text: $workspace.graphFilter.query).textFieldStyle(.plain).frame(width: 150)
            Divider()
            Toggle("Notes", isOn: $workspace.graphFilter.showNotes)
            Toggle("Code and files", isOn: $workspace.graphFilter.showFiles)
            Toggle("Unconnected", isOn: $workspace.graphFilter.showOrphans)
        }
        .toggleStyle(.checkbox).font(.callout).frame(width: 150).padding(10)
        .background(.regularMaterial, in: .rect(cornerRadius: 12))
        .environment(\.colorScheme, .dark)
    }
}

/// Draws the sky. The big one can be dragged, zoomed and clicked. The small one sits in the side panel.
struct GraphCanvas: View {
    let workspace: Workspace
    let compact: Bool
    @State private var scale: CGFloat = 1
    @State private var offset = CGSize.zero
    @State private var pinchStart: CGFloat?
    @State private var dragStart: CGSize?
    @State private var dragNode: Int?
    @State private var hover: Int?
    @State private var pointer: CGPoint?
    @State private var viewSize = CGSize.zero
    @State private var monitor: Any?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var sim: GraphSim { workspace.sim }

    private struct Camera {
        let centre: CGPoint
        let world: CGPoint
        let zoom: CGFloat
        let offset: CGSize
        func screen(_ px: CGFloat, _ py: CGFloat) -> CGPoint {
            CGPoint(x: centre.x + offset.width + (px - world.x) * zoom, y: centre.y + offset.height + (py - world.y) * zoom)
        }
        func world(from p: CGPoint) -> CGPoint {
            CGPoint(x: (p.x - centre.x - offset.width) / zoom + world.x, y: (p.y - centre.y - offset.height) / zoom + world.y)
        }
    }

    private func camera(_ size: CGSize) -> Camera {
        guard let left = sim.x.min(), let right = sim.x.max(), let top = sim.y.min(), let bottom = sim.y.max() else {
            return Camera(centre: CGPoint(x: size.width / 2, y: size.height / 2), world: .zero, zoom: 1, offset: offset)
        }
        let width = max(right - left, 160)
        let height = max(bottom - top, 160)
        let fit = min(2.4, min(size.width / width, size.height / height) * (compact ? 0.8 : 0.72))
        return Camera(centre: CGPoint(x: size.width / 2, y: size.height / 2), world: CGPoint(x: (left + right) / 2, y: (top + bottom) / 2), zoom: fit * scale, offset: offset)
    }

    var body: some View {
        // The sim isn't observable, so a new map has to say so here.
        let _ = workspace.simVersion
        return TimelineView(.animation(minimumInterval: 1 / 45, paused: !(workspace.isAsking || (sim.isMoving && !reduceMotion) || dragNode != nil))) { time in
            Canvas { context, size in
                if !compact { sim.step() }
                sim.withPositions { draw(&context, size, time: time.date.timeIntervalSinceReferenceDate) }
            }
        }
        .background(Color.black)
        .background(GeometryReader { geo in
            Color.clear.onAppear { viewSize = geo.size }.onChange(of: geo.size) { _, new in viewSize = new }
        })
        .contentShape(Rectangle())
        .gesture(DragGesture(minimumDistance: 0).onChanged(dragChanged).onEnded(dragEnded))
        .simultaneousGesture(MagnifyGesture().onChanged { value in
            guard !compact else { return }
            let start = pinchStart ?? scale
            pinchStart = start
            zoom(to: start * value.magnification, around: value.startLocation)
        }.onEnded { _ in pinchStart = nil })
        .onContinuousHover { phase in
            switch phase {
            case let .active(location):
                pointer = location
                hover = nearest(to: location, within: 14)
            case .ended:
                pointer = nil
                hover = nil
            }
        }
        .onAppear { if !compact { watchScrolling() } }
        .onDisappear { if let monitor { NSEvent.removeMonitor(monitor) } }
        .accessibilityElement()
        .accessibilityLabel("Graph of \(sim.nodes.count) notes and files")
    }

    private func dragChanged(_ value: DragGesture.Value) {
        let moved = hypot(value.translation.width, value.translation.height)
        if dragStart == nil, dragNode == nil {
            if let hit = nearest(to: value.startLocation, within: 14), !compact {
                dragNode = hit
            } else {
                dragStart = offset
            }
        }
        guard moved > 3, !compact else { return }
        if let dragNode {
            let place = camera(viewSize).world(from: value.location)
            sim.pin(dragNode, x: place.x, y: place.y)
        } else if let dragStart {
            offset = CGSize(width: dragStart.width + value.translation.width, height: dragStart.height + value.translation.height)
        }
    }

    private func dragEnded(_ value: DragGesture.Value) {
        defer {
            dragNode = nil
            dragStart = nil
            sim.release()
        }
        guard hypot(value.translation.width, value.translation.height) <= 3 else { return }
        if let hit = nearest(to: value.location, within: 16) {
            workspace.go(.file(sim.nodes[hit].path), newTab: NSEvent.modifierFlags.contains(.command))
        }
    }

    private func zoom(to wanted: CGFloat, around point: CGPoint) {
        let next = min(20, max(0.35, wanted))
        let from = CGPoint(x: point.x - viewSize.width / 2, y: point.y - viewSize.height / 2)
        let ratio = next / scale
        offset = CGSize(width: from.x - (from.x - offset.width) * ratio, height: from.y - (from.y - offset.height) * ratio)
        scale = next
    }

    private func watchScrolling() {
        monitor = NSEvent.addLocalMonitorForEvents(matching: .scrollWheel) { event in
            guard let pointer else { return event }
            if event.hasPreciseScrollingDeltas, !event.modifierFlags.contains(.command) {
                offset = CGSize(width: offset.width + event.scrollingDeltaX, height: offset.height + event.scrollingDeltaY)
            } else {
                zoom(to: scale * (1 + event.scrollingDeltaY * (event.hasPreciseScrollingDeltas ? 0.01 : 0.04)), around: pointer)
            }
            return nil
        }
    }

    private func nearest(to point: CGPoint, within limit: CGFloat) -> Int? {
        sim.withPositions {
            let view = camera(viewSize)
            var best: (index: Int, distance: CGFloat)?
            for i in sim.nodes.indices where visible(i) {
                let spot = view.screen(sim.x[i], sim.y[i])
                let distance = hypot(spot.x - point.x, spot.y - point.y)
                if distance <= limit, distance < (best?.distance ?? .infinity) { best = (i, distance) }
            }
            return best?.index
        }
    }

    private func visible(_ i: Int) -> Bool {
        let filter = workspace.graphFilter
        let node = sim.nodes[i]
        if node.isNote ? !filter.showNotes : !filter.showFiles { return false }
        if !filter.showOrphans, node.degree == 0 { return false }
        if !filter.query.isEmpty, !node.path.localizedCaseInsensitiveContains(filter.query) { return false }
        return true
    }

    private func draw(_ context: inout GraphicsContext, _ size: CGSize, time: Double) {
        guard !sim.nodes.isEmpty else { return }
        let view = camera(size)
        let shown = sim.nodes.indices.filter(visible)
        let reached = Set(workspace.lit.prefix(workspace.litCount).compactMap { sim.index[$0] })
        let reading = workspace.readingNow.flatMap { sim.index[$0] }
        let here = workspace.currentPath.flatMap { sim.index[$0] }
        let focus = compact ? here : (dragNode ?? hover)
        let beside = focus.map { Set(sim.neighbours[$0]) } ?? []
        let quiet = focus != nil || !reached.isEmpty
        let area = CGRect(origin: .zero, size: size).insetBy(dx: -30, dy: -30)
        let shownSet = Set(shown)
        var glow = context
        glow.blendMode = .plusLighter

        var faint = Path()
        for edge in sim.edges.prefix(9000) where shownSet.contains(edge.a) && shownSet.contains(edge.b) {
            faint.move(to: view.screen(sim.x[edge.a], sim.y[edge.a]))
            faint.addLine(to: view.screen(sim.x[edge.b], sim.y[edge.b]))
        }
        glow.stroke(faint, with: .color(.white.opacity(quiet ? 0.03 : 0.1)), lineWidth: 0.7)

        if let focus {
            var bright = Path()
            for other in beside where shownSet.contains(other) {
                bright.move(to: view.screen(sim.x[focus], sim.y[focus]))
                bright.addLine(to: view.screen(sim.x[other], sim.y[other]))
            }
            glow.stroke(bright, with: .color(sim.colour(sim.nodes[focus].group).opacity(0.8)), lineWidth: 1.1)
        }
        var trail = Path()
        for link in workspace.litLinks {
            guard let a = sim.index[link.from], let b = sim.index[link.to], reached.contains(a), reached.contains(b) else { continue }
            trail.move(to: view.screen(sim.x[a], sim.y[a]))
            trail.addLine(to: view.screen(sim.x[b], sim.y[b]))
        }
        glow.stroke(trail, with: .color(Theme.gold.opacity(0.9)), lineWidth: 1.4)

        let growth = max(0.75, min(1.9, sqrt(scale)))
        let halos = shown.count < 2500
        for i in shown {
            let spot = view.screen(sim.x[i], sim.y[i])
            guard area.contains(spot) else { continue }
            let node = sim.nodes[i]
            let isLit = reached.contains(i) || i == focus || i == here
            let strength: Double = !quiet || isLit ? 1 : beside.contains(i) ? 0.85 : 0.22
            var radius = (1.8 + min(5.5, sqrt(CGFloat(node.degree)) * 0.8)) * growth * (compact ? 0.72 : 1)
            var colour = sim.colour(node.group)
            if reached.contains(i) || (i == here && !compact) { colour = Theme.gold; radius += 1.4 }
            if i == reading { radius += 1.8 * (1 + sin(time * 9)) }
            if halos {
                let halo = radius * (isLit ? 7 : 4)
                glow.fill(Path(ellipseIn: CGRect(x: spot.x - halo, y: spot.y - halo, width: halo * 2, height: halo * 2)),
                          with: .radialGradient(Gradient(colors: [colour.opacity(0.5 * strength), colour.opacity(0.1 * strength), .clear]), center: spot, startRadius: 0, endRadius: halo))
            }
            glow.fill(Path(ellipseIn: CGRect(x: spot.x - radius, y: spot.y - radius, width: radius * 2, height: radius * 2)), with: .color(colour.opacity(0.95 * strength)))
            let heart = radius * 0.42
            glow.fill(Path(ellipseIn: CGRect(x: spot.x - heart, y: spot.y - heart, width: heart * 2, height: heart * 2)), with: .color(.white.opacity(0.9 * strength)))
        }

        guard !compact else { return }
        var named = reached
        if let focus { named.insert(focus); named.formUnion(beside) }
        if let here { named.insert(here) }
        if view.zoom > 2 || shown.count < 40 { named.formUnion(shown.filter { area.contains(view.screen(sim.x[$0], sim.y[$0])) }) }
        func matters(_ i: Int) -> Bool { reached.contains(i) || i == focus || i == here }
        var taken: [CGRect] = []
        let ranked = named.filter(shownSet.contains).sorted { (matters($0) ? 1 : 0, sim.nodes[$0].degree, $1) > (matters($1) ? 1 : 0, sim.nodes[$1].degree, $0) }
        for i in ranked.prefix(260) {
            let spot = view.screen(sim.x[i], sim.y[i])
            guard area.contains(spot) else { continue }
            let name = sim.nodes[i].name.count > 34 ? String(sim.nodes[i].name.prefix(33)) + "…" : sim.nodes[i].name
            let start = CGPoint(x: spot.x + 11, y: spot.y)
            let room = CGRect(x: start.x, y: start.y - 8, width: CGFloat(name.count) * 6.3, height: 16)
            guard i == hover || !taken.contains(where: { $0.intersects(room) }) else { continue }
            taken.append(room)
            context.draw(Text(name).font(.system(size: 11, weight: matters(i) ? .medium : .regular)).foregroundStyle(matters(i) ? Color.white : Color.white.opacity(0.65)), at: start, anchor: .leading)
        }
        for centre in sim.groupCentres() where centre.count >= 2 {
            let spot = view.screen(centre.x, centre.top)
            let label = CGPoint(x: spot.x, y: spot.y - 18)
            let width = CGFloat(centre.name.count) * 8.4
            let room = CGRect(x: label.x - width / 2, y: label.y - 8, width: width, height: 16)
            guard area.contains(label), !taken.contains(where: { $0.intersects(room) }) else { continue }
            taken.append(room)
            context.draw(Text(centre.name.uppercased()).font(.system(size: 10.5, weight: .semibold)).kerning(1.4).foregroundStyle(sim.colour(centre.group).opacity(quiet ? 0.4 : 0.9)), at: label)
        }
    }
}
