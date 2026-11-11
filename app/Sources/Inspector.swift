import BurrowCore
import SwiftUI

extension Vault.Neighbour {
    /// Unique across a whole list, so rows in different sections can't be mistaken for each other.
    var rowID: String { "\(forward)|\(kind.rawValue)|\(path)" }
}

struct InspectorPane: View {
    let workspace: Workspace

    var body: some View {
        switch workspace.currentTab?.content {
        case let .file(path): FileInspector(workspace: workspace, path: path, document: workspace.document(path))
        case .ask: AskInspector(workspace: workspace)
        case .library: LibraryInspector(workspace: workspace, path: workspace.librarySelection)
        default: OverviewInspector(workspace: workspace)
        }
    }
}

struct FileInspector: View {
    let workspace: Workspace
    let path: String
    let document: Document
    @State private var mentions: [FoundLine] = []
    @State private var neighbours: [Vault.Neighbour] = []

    private var outgoing: [Vault.Neighbour] { neighbours.filter(\.forward) }
    private var usedBy: [Vault.Neighbour] { neighbours.filter { !$0.forward && $0.kind != .about } }

    private var headings: [(id: String, line: Int, level: Int, text: String)] {
        guard path.isMarkdownPath else { return [] }
        return document.text.components(separatedBy: "\n").enumerated().compactMap { number, raw in
            let level = raw.prefix { $0 == "#" }.count
            guard (1...6).contains(level), raw.dropFirst(level).first == " " else { return nil }
            return ("heading-\(number)", number + 1, level, String(raw.dropFirst(level + 1)))
        }
    }

    private var fields: [(String, String)] {
        NoteFile.split(document.text).fields.sorted { $0.key < $1.key }.map { ($0.key, $0.value) }
    }

    var body: some View {
        VStack(spacing: 0) {
            LocalGraph(workspace: workspace, path: path).frame(height: 210).clipped()
            List {
                if !fields.isEmpty {
                    Section("Properties") {
                        ForEach(fields, id: \.0) { LabeledContent($0.0, value: $0.1) }
                    }
                }
                if !headings.isEmpty {
                    Section("Outline") {
                        ForEach(headings, id: \.id) { heading in
                            Button { document.pendingLine = heading.line } label: {
                                Text(heading.text).lineLimit(1).padding(.leading, CGFloat(heading.level - 1) * 10).frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
                Section("Linked mentions") {
                    if mentions.isEmpty { Text("Nothing links here yet").foregroundStyle(.secondary) }
                    ForEach(mentions) { mention in
                        Button { workspace.go(.file(mention.path), line: mention.line) } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(mention.path.title).fontWeight(.medium).lineLimit(1)
                                Text(mention.text).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }
                }
                if !outgoing.isEmpty {
                    Section("Links to") { ForEach(outgoing.prefix(60), id: \.rowID) { row($0) } }
                }
                if !usedBy.isEmpty {
                    Section("Used by") { ForEach(usedBy.prefix(60), id: \.rowID) { row($0) } }
                }
            }
        }
        .task(id: "\(path)|\(workspace.stats?.links ?? 0)") {
            neighbours = await workspace.neighbours(of: path)
            mentions = await workspace.mentions(of: path)
        }
    }

    private func row(_ link: Vault.Neighbour) -> some View {
        Button { workspace.go(.file(link.path)) } label: {
            VStack(alignment: .leading, spacing: 1) {
                Text(link.path.title).lineLimit(1)
                if let via = link.via { Text(via).font(.caption).foregroundStyle(.secondary).lineLimit(1) }
            }
            .frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

/// This note and everything one step from it.
struct LocalGraph: View {
    let workspace: Workspace
    let path: String
    @State private var hover: Int?
    @State private var viewSize = CGSize.zero

    private var sim: GraphSim { workspace.sim }

    private func spots(_ size: CGSize) -> (centre: CGPoint, others: [(index: Int, spot: CGPoint)]) {
        let centre = CGPoint(x: size.width / 2, y: size.height / 2)
        guard let me = sim.index[path] else { return (centre, []) }
        let around = sim.neighbours[me].prefix(32)
        let reach = min(size.width, size.height) * 0.36
        return (centre, around.enumerated().map { place, other in
            let angle = Double(place) * 2 * .pi / Double(max(1, around.count)) - .pi / 2
            let stagger: CGFloat = around.count > 12 && place % 2 == 1 ? 0.68 : 1
            return (other, CGPoint(x: centre.x + reach * stagger * cos(angle), y: centre.y + reach * stagger * sin(angle)))
        })
    }

    var body: some View {
        Canvas { context, size in
            var glow = context
            glow.blendMode = .plusLighter
            let layout = spots(size)
            guard let me = sim.index[path] else { return }
            var lines = Path()
            for other in layout.others {
                lines.move(to: layout.centre)
                lines.addLine(to: other.spot)
            }
            glow.stroke(lines, with: .color(Theme.gold.opacity(0.32)), lineWidth: 0.9)
            func star(_ at: CGPoint, _ radius: CGFloat, _ colour: Color) {
                let halo = radius * 5
                glow.fill(Path(ellipseIn: CGRect(x: at.x - halo, y: at.y - halo, width: halo * 2, height: halo * 2)),
                          with: .radialGradient(Gradient(colors: [colour.opacity(0.55), colour.opacity(0.1), .clear]), center: at, startRadius: 0, endRadius: halo))
                glow.fill(Path(ellipseIn: CGRect(x: at.x - radius, y: at.y - radius, width: radius * 2, height: radius * 2)), with: .color(colour))
            }
            for other in layout.others {
                star(other.spot, other.index == hover ? 4.5 : 3, sim.colour(sim.nodes[other.index].group))
                if other.index == hover {
                    context.draw(Text(sim.nodes[other.index].name).font(.system(size: 10.5)).foregroundStyle(.white), at: CGPoint(x: other.spot.x, y: other.spot.y - 12))
                }
            }
            star(layout.centre, 5.5, Theme.gold)
            _ = me
        }
        .background(Color.black)
        .background(GeometryReader { geo in
            Color.clear.onAppear { viewSize = geo.size }.onChange(of: geo.size) { _, new in viewSize = new }
        })
        .contentShape(Rectangle())
        .onContinuousHover { phase in
            if case let .active(point) = phase {
                hover = spots(viewSize).others.first { hypot($0.spot.x - point.x, $0.spot.y - point.y) < 14 }?.index
            } else {
                hover = nil
            }
        }
        .onTapGesture { point in
            if let hit = spots(viewSize).others.first(where: { hypot($0.spot.x - point.x, $0.spot.y - point.y) < 14 }) {
                workspace.go(.file(sim.nodes[hit.index].path))
            }
        }
        .accessibilityLabel("Everything linked to \(path.title)")
    }
}

struct OverviewInspector: View {
    let workspace: Workspace

    var body: some View {
        List {
            if let turn = workspace.turns.last {
                Section("Latest answer") { AnswerView(workspace: workspace, turn: turn, showQuestion: true) }
            }
            Section("This vault") {
                if let stats = workspace.stats {
                    LabeledContent("Notes", value: "\(stats.notes)")
                    LabeledContent("Files", value: "\(stats.files)")
                    LabeledContent("Links", value: "\(stats.links)")
                    LabeledContent("Index", value: ByteCountFormatter.string(fromByteCount: Int64(stats.indexBytes), countStyle: .file))
                }
            }
            Section("Linked folders") {
                if workspace.linked.isEmpty { Text("None yet").foregroundStyle(.secondary) }
                ForEach(workspace.linked) { folder in
                    Button(folder.name) { workspace.go(.library(.all)) }
                    .buttonStyle(.plain).help(folder.path)
                }
                Button("Link a Folder…") { pickLinkedFolder(workspace) }
            }
        }
    }
}
