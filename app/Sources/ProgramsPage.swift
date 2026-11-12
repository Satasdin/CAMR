import AppKit
import BurrowTools
import Charts
import SwiftUI

// MARK: Programs

/// The programs that use the vault, each drawn as a line flowing into it. A line is bright when the program looked
/// things up today, carries moving light while it is doing so, and is dashed when the program isn't set up.
/// Hover a line to see what that program read; click it to open its conversations, or to set it up.
struct ProgramsPage: View {
    let workspace: Workspace
    @State private var hovered: Program?
    @State private var hoverVault = false
    @State private var pointer: CGPoint = .zero
    @State private var open: Set<Program> = []
    @State private var links: [Program: Connection] = [:]
    @State private var notice: String?

    private var programs: [Program] { Program.known + (workspace.sessions(for: .other).isEmpty ? [] : [.other]) }

    var body: some View {
        ScrollViewReader { scroller in
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    header
                    if !Connections.commandIsInstalled { commandMissing }
                    FlowMap(workspace: workspace, programs: programs, links: links, hovered: $hovered, hoverVault: $hoverVault, pointer: $pointer) { program in
                        if program == nil { workspace.go(.graph); return }
                        guard let program else { return }
                        if workspace.sessions(for: program).isEmpty {
                            open.insert(program)
                            withAnimation(.smooth) { scroller.scrollTo(program, anchor: .center) }
                        } else {
                            workspace.go(.conversations(program))
                        }
                    }
                    .frame(height: CGFloat(programs.count) * FlowMap.rowGap + 36)
                    traffic
                    VStack(spacing: 8) {
                        ForEach(programs) { program in
                            ProgramRow(workspace: workspace, program: program, link: links[program], highlighted: hovered == program,
                                       open: Binding(get: { open.contains(program) }, set: { if $0 { open.insert(program) } else { open.remove(program) } }),
                                       notice: $notice, refresh: refresh)
                                .id(program)
                                .onHover { inside in hovered = inside ? program : (hovered == program ? nil : hovered) }
                        }
                    }
                }
                .padding(.horizontal, 28).padding(.vertical, 22)
            }
        }
        .background(Night.ground)
        .environment(\.colorScheme, .dark)
        .task(id: workspace.sessions.count) { await refresh() }
        .overlay(alignment: .bottom) {
            if let notice {
                Text(notice).font(.system(size: 12.5, weight: .medium)).padding(.horizontal, 14).padding(.vertical, 8)
                    .background(.ultraThinMaterial, in: .capsule).padding(.bottom, 18)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .task { try? await Task.sleep(for: .seconds(4)); withAnimation { self.notice = nil } }
            }
        }
        .animation(.smooth(duration: 0.25), value: notice)
    }

    private func refresh() async {
        var read = await Connections.read(vault: workspace.folder)
        // A program that has used this vault was set up somewhere: most often a project's own settings file,
        // which Burrow can't know to look in. Say so rather than "Not set up".
        for program in programs where read[program]?.state == .notSetUp && !workspace.sessions(for: program).isEmpty {
            read[program] = Connection(state: .usedElsewhere)
        }
        links = read
        // For checking the hover card without a person at the screen: BURROW_PEEK=OpenCode, or BURROW_PEEK=vault.
        if let peek = ProcessInfo.processInfo.environment["BURROW_PEEK"], hovered == nil {
            if peek == "vault" { hoverVault = true } else { hovered = programs.first { $0.name == peek }; pointer = CGPoint(x: 420, y: 0) }
        }
    }

    private var header: some View {
        let connected = programs.filter { links[$0]?.isLinked == true }.count
        let active = programs.filter { FlowMap.active(workspace, $0) }.count
        return HStack(alignment: .firstTextBaseline, spacing: 14) {
            Text("Programs").font(.system(size: 28, weight: .bold)).tracking(-0.4)
            Text("\(connected) set up for this vault · \(active) active in the last 30 minutes").foregroundStyle(Night.dim).monospacedDigit()
            Spacer()
            Button { Task { await refresh() } } label: { Image(systemName: "arrow.clockwise") }
                .buttonStyle(.borderless).foregroundStyle(Night.dim).help("Check the programs' settings again")
        }
    }

    /// Without the `burrow` command on the Mac, no program can start the vault, so this comes first.
    private var commandMissing: some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Night.document)
            VStack(alignment: .leading, spacing: 2) {
                Text("The burrow command isn't installed").font(.system(size: 13, weight: .semibold))
                Text("Programs start the vault by running it. The setup lines below use its full path once it is installed.")
                    .font(.system(size: 12)).foregroundStyle(Night.dim)
            }
            Spacer()
            Button("Install Command") {
                do { notice = try CommandInstaller.install(); Task { await refresh() } } catch { notice = error.localizedDescription }
            }
            .controlSize(.small)
        }
        .padding(12).background(Night.document.opacity(0.08), in: .rect(cornerRadius: 12))
        .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder(Night.document.opacity(0.25)) }
    }

    private struct Hour: Identifiable { let id = UUID(); let hour: Date; let program: Program; let count: Int }

    /// Lookups per hour today, stacked by program in each program's colour.
    private var traffic: some View {
        let calendar = Calendar.current
        let hours: [Hour] = programs.flatMap { program -> [Hour] in
            Dictionary(grouping: FlowMap.today(workspace, program)) { calendar.dateInterval(of: .hour, for: $0.at)!.start }
                .map { Hour(hour: $0.key, program: program, count: $0.value.count) }
        }
        let used = programs.filter { program in hours.contains { $0.program == program } }
        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Lookups today").font(.system(size: 12, weight: .semibold)).foregroundStyle(Night.dim)
                Spacer()
                ForEach(used) { program in
                    HStack(spacing: 5) {
                        Circle().fill(program.colour).frame(width: 7, height: 7)
                        Text(program.name).font(.system(size: 11)).foregroundStyle(Night.dim)
                    }
                }
            }
            if hours.isEmpty {
                Text("No lookups yet today.").font(.system(size: 12)).foregroundStyle(Night.faint).frame(height: 60)
            } else {
                Chart(hours) { item in
                    BarMark(x: .value("Hour", item.hour, unit: .hour), y: .value("Lookups", item.count))
                        .foregroundStyle(item.program.colour.opacity(hovered == nil || hovered == item.program ? 0.9 : 0.2))
                        .cornerRadius(2)
                }
                .chartXScale(domain: calendar.startOfDay(for: Date())...calendar.date(byAdding: .day, value: 1, to: calendar.startOfDay(for: Date()))!)
                .chartXAxis { AxisMarks(values: .stride(by: .hour, count: 3)) { _ in AxisGridLine().foregroundStyle(Night.line); AxisValueLabel(format: .dateTime.hour()) } }
                .chartYAxis { AxisMarks(position: .leading, values: .automatic(desiredCount: 3)) { _ in AxisGridLine().foregroundStyle(Night.line); AxisValueLabel() } }
                .frame(height: 80)
            }
        }
        .padding(14).background(Night.card, in: .rect(cornerRadius: 12))
    }
}

// MARK: The map

/// Programs on the left, the vault on the right, one curve each. Every curve ends on the vault's rim, aimed at its
/// centre, so they read as streams running into it rather than wires stopping near it.
struct FlowMap: View {
    let workspace: Workspace
    let programs: [Program]
    let links: [Program: Connection]
    @Binding var hovered: Program?
    @Binding var hoverVault: Bool
    @Binding var pointer: CGPoint
    /// nil is the vault itself.
    let choose: (Program?) -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    static let rowGap: CGFloat = 62
    static let vaultRadius: CGFloat = 14
    private static let portX: CGFloat = 214

    static func today(_ workspace: Workspace, _ program: Program) -> [TrailStep] {
        workspace.sessions(for: program).flatMap { $0.trail ?? [] }.filter { Calendar.current.isDateInToday($0.at) }
    }
    static func active(_ workspace: Workspace, _ program: Program) -> Bool {
        workspace.sessions(for: program).contains { Date().timeIntervalSince($0.updated) < 30 * 60 }
    }

    private func rowY(_ index: Int) -> CGFloat { 34 + CGFloat(index) * Self.rowGap }
    private func vault(in size: CGSize) -> CGPoint { CGPoint(x: size.width - 130, y: size.height / 2) }

    /// The curve for one program: leaves its port level, bends, and meets the vault's rim along a radius.
    private func curve(_ index: Int, in size: CGSize) -> (start: CGPoint, c1: CGPoint, c2: CGPoint, end: CGPoint) {
        let centre = vault(in: size)
        let start = CGPoint(x: Self.portX, y: rowY(index))
        let spread = programs.count > 1 ? (Double(index) / Double(programs.count - 1) - 0.5) : 0
        let angle = Double.pi - spread * 1.1   // fans over ±32° on the vault's left side, top line arriving highest
        let direction = CGPoint(x: cos(angle), y: sin(angle))
        let end = CGPoint(x: centre.x + direction.x * (Self.vaultRadius + 1), y: centre.y + direction.y * (Self.vaultRadius + 1))
        let reach = (end.x - start.x) * 0.5
        let approach = (end.x - start.x) * 0.3
        return (start, CGPoint(x: start.x + reach, y: start.y), CGPoint(x: end.x + direction.x * approach, y: end.y + direction.y * approach), end)
    }

    private func point(_ c: (start: CGPoint, c1: CGPoint, c2: CGPoint, end: CGPoint), _ t: Double) -> CGPoint {
        let u = 1 - t
        let a = u * u * u, b = 3 * u * u * t, d = 3 * u * t * t, e = t * t * t
        return CGPoint(x: a * c.start.x + b * c.c1.x + d * c.c2.x + e * c.end.x, y: a * c.start.y + b * c.c1.y + d * c.c2.y + e * c.end.y)
    }

    private var busiest: Int { max(1, programs.map { Self.today(workspace, $0).count }.max() ?? 1) }

    var body: some View {
        GeometryReader { box in
            let size = box.size
            let centre = vault(in: size)
            ZStack(alignment: .topLeading) {
                TimelineView(.animation(minimumInterval: 1 / 30, paused: reduceMotion)) { time in
                    Canvas { context, _ in draw(&context, size: size, time: time.date.timeIntervalSinceReferenceDate) }
                }
                ForEach(Array(programs.enumerated()), id: \.element) { index, program in label(program).position(x: 104, y: rowY(index)) }
                vaultMark.position(x: centre.x, y: centre.y + 44)
                if let hovered, let index = programs.firstIndex(of: hovered) {
                    ProgramPeek(workspace: workspace, program: hovered, link: links[hovered])
                        .position(x: min(centre.x - 175, max(pointer.x + 150, 360)), y: min(max(rowY(index), 100), size.height - 100))
                        .allowsHitTesting(false)
                        .transition(.opacity)
                } else if hoverVault {
                    VaultPeek(workspace: workspace, programs: programs)
                        .position(x: centre.x - 170, y: min(max(centre.y, 80), size.height - 80))
                        .allowsHitTesting(false)
                        .transition(.opacity)
                }
            }
            .contentShape(.rect)
            .onContinuousHover { phase in
                switch phase {
                case let .active(location):
                    pointer = location
                    let target = hit(location, in: size)
                    hoverVault = target == .some(nil)
                    hovered = target ?? nil
                    if target == nil { NSCursor.arrow.set() } else { NSCursor.pointingHand.set() }
                case .ended:
                    hovered = nil
                    hoverVault = false
                    NSCursor.arrow.set()
                }
            }
            .onTapGesture(coordinateSpace: .local) { location in
                if let target = hit(location, in: size) { choose(target) }
            }
            .animation(.smooth(duration: 0.18), value: hovered)
            .animation(.smooth(duration: 0.18), value: hoverVault)
        }
        .background(
            RadialGradient(colors: [Night.conversation.opacity(0.07), .clear], center: UnitPoint(x: 0.85, y: 0.5), startRadius: 0, endRadius: 420),
            in: .rect(cornerRadius: 14)
        )
        .background(Night.card.opacity(0.55), in: .rect(cornerRadius: 14))
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Programs connected to the vault")
    }

    /// What the pointer is over: a program (its label or near its line), the vault (`.some(nil)`), or nothing (`nil`).
    private func hit(_ location: CGPoint, in size: CGSize) -> Program?? {
        let centre = vault(in: size)
        if hypot(location.x - centre.x, location.y - centre.y) < Self.vaultRadius + 16 || (abs(location.x - centre.x) < 60 && abs(location.y - centre.y - 44) < 18) {
            return .some(nil)
        }
        var best: (Program, CGFloat)?
        for (index, program) in programs.enumerated() {
            if location.x < Self.portX + 6, abs(location.y - rowY(index)) < Self.rowGap / 2 { return .some(program) }
            let c = curve(index, in: size)
            for step in 0...40 {
                let p = point(c, Double(step) / 40)
                let distance = hypot(p.x - location.x, p.y - location.y)
                if distance < (best?.1 ?? 12) { best = (program, distance) }
            }
        }
        return best.map { .some($0.0) }
    }

    private func draw(_ context: inout GraphicsContext, size: CGSize, time: Double) {
        let centre = vault(in: size)
        for (index, program) in programs.enumerated() {
            let c = curve(index, in: size)
            var path = Path()
            path.move(to: c.start)
            path.addCurve(to: c.end, control1: c.c1, control2: c.c2)
            let lookups = Self.today(workspace, program).count
            let linked = links[program]?.isLinked == true || links[program]?.state == .serving || !workspace.sessions(for: program).isEmpty
            let strength = Double(lookups) / Double(busiest)
            let focus = hovered == nil && !hoverVault ? 1 : (hovered == program || hoverVault ? 1 : 0.22)
            let colour = program.colour
            if !linked {
                context.stroke(path, with: .color(.white.opacity(0.13 * focus)), style: StrokeStyle(lineWidth: 1, dash: [3, 5]))
                continue
            }
            let width = lookups == 0 ? 1.2 : 1.6 + 2.6 * strength
            let alpha = (lookups == 0 ? 0.32 : 0.5 + 0.5 * strength) * focus
            if lookups > 0 || hovered == program {
                var glow = context
                glow.addFilter(.blur(radius: hovered == program ? 7 : 5))
                glow.stroke(path, with: .color(colour.opacity(0.45 * focus)), lineWidth: width + 3)
            }
            context.stroke(path, with: .linearGradient(Gradient(colors: [colour.opacity(alpha * 0.55), colour.opacity(alpha)]),
                                                       startPoint: c.start, endPoint: c.end),
                           style: StrokeStyle(lineWidth: width + (hovered == program ? 1 : 0), lineCap: .round))
            // Light running toward the vault: more and faster the more the program read today.
            if lookups > 0 && !reduceMotion {
                let beads = min(5, 1 + lookups / 3)
                let speed = Self.active(workspace, program) ? 0.33 : 0.14
                for bead in 0..<beads {
                    let t = (time * speed + Double(bead) / Double(beads)).truncatingRemainder(dividingBy: 1)
                    let p = point(c, t)
                    let fade = min(1, min(t, 1 - t) * 6) * focus
                    context.fill(Path(ellipseIn: CGRect(x: p.x - 2.2, y: p.y - 2.2, width: 4.4, height: 4.4)), with: .color(.white.opacity(0.9 * fade)))
                    var halo = context
                    halo.addFilter(.blur(radius: 3))
                    halo.fill(Path(ellipseIn: CGRect(x: p.x - 4, y: p.y - 4, width: 8, height: 8)), with: .color(colour.opacity(0.8 * fade)))
                }
            }
            // The port the line leaves from, beside the program's name.
            context.fill(Path(ellipseIn: CGRect(x: c.start.x - 3, y: c.start.y - 3, width: 6, height: 6)), with: .color(colour.opacity(max(alpha, 0.5 * focus))))
        }
        // The vault: a bright core in a soft ring that breathes while any program is working.
        let busy = programs.contains { Self.active(workspace, $0) }
        let breath = busy && !reduceMotion ? 0.5 + 0.5 * sin(time * 2.2) : 0.4
        let r = Self.vaultRadius
        var halo = context
        halo.addFilter(.blur(radius: 14))
        halo.fill(Path(ellipseIn: CGRect(x: centre.x - r * 1.6, y: centre.y - r * 1.6, width: r * 3.2, height: r * 3.2)),
                  with: .color(Night.conversation.opacity(0.25 + 0.3 * breath + (hoverVault ? 0.2 : 0))))
        context.stroke(Path(ellipseIn: CGRect(x: centre.x - r - 5, y: centre.y - r - 5, width: (r + 5) * 2, height: (r + 5) * 2)),
                       with: .color(.white.opacity(0.10 + 0.1 * breath)), lineWidth: 1)
        context.fill(Path(ellipseIn: CGRect(x: centre.x - r, y: centre.y - r, width: r * 2, height: r * 2)),
                     with: .radialGradient(Gradient(colors: [.white, Color(white: 0.82)]), center: CGPoint(x: centre.x - 3, y: centre.y - 4), startRadius: 0, endRadius: r * 1.2))
    }

    private func label(_ program: Program) -> some View {
        let used = !workspace.sessions(for: program).isEmpty
        let link = links[program]
        let lit = used || link?.isLinked == true || link?.state == .serving
        let focus = hovered == nil && !hoverVault ? true : hovered == program
        return HStack(spacing: 10) {
            Image(systemName: program.symbol).font(.system(size: 13)).frame(width: 22).foregroundStyle(lit ? program.colour : Night.faint)
            VStack(alignment: .leading, spacing: 1) {
                Text(program.name).font(.system(size: 13.5, weight: .semibold)).foregroundStyle(lit ? Night.note : Night.dim)
                Text(link?.label ?? " ").font(.system(size: 10.5)).foregroundStyle(link?.isLinked == true ? program.colour.opacity(0.9) : Night.faint)
            }
        }
        .frame(width: 176, alignment: .leading)
        .opacity(focus ? 1 : 0.4)
    }

    private var vaultMark: some View {
        let lookups = programs.map { Self.today(workspace, $0).count }.reduce(0, +)
        return VStack(spacing: 1) {
            Text(workspace.name).font(.system(size: 12.5, weight: .semibold)).lineLimit(1)
            Text(lookups == 0 ? "quiet today" : "\(lookups.counted("lookup")) today").font(.system(size: 10.5)).foregroundStyle(Night.dim).monospacedDigit()
        }
        .frame(width: 140)
    }
}

/// The card that follows the pointer over a program's line: what it is, whether it's connected, and what it read.
struct ProgramPeek: View {
    let workspace: Workspace
    let program: Program
    let link: Connection?

    var body: some View {
        let records = workspace.sessions(for: program)
        let today = FlowMap.today(workspace, program)
        let files = Self.mostRead(today.isEmpty ? records.flatMap { $0.trail ?? [] } : today)
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Circle().fill(program.colour).frame(width: 8, height: 8).shadow(color: program.colour, radius: 4)
                Text(program.name).font(.system(size: 13, weight: .semibold))
                Spacer()
                if let link { Text(link.label).font(.system(size: 10.5, weight: .medium)).foregroundStyle(link.isLinked ? program.colour : Night.dim) }
            }
            if records.isEmpty {
                Text(link?.detail ?? "Not used with this vault yet").font(.system(size: 11.5)).foregroundStyle(Night.dim).fixedSize(horizontal: false, vertical: true)
            } else {
                Text("\(records.count.counted("conversation")) · \(today.count.counted("lookup")) today · last used \(records.first!.updated.formatted(.relative(presentation: .named)))")
                    .font(.system(size: 11.5)).foregroundStyle(Night.dim).monospacedDigit()
                if let asked = (today.last ?? records.first?.trail?.last).map(\.asked), !asked.isEmpty {
                    Text("“\(asked)”").font(.system(size: 12)).lineLimit(2).foregroundStyle(Night.note.opacity(0.9))
                }
                if !files.isEmpty {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(today.isEmpty ? "Read most" : "Read most today").font(.system(size: 10, weight: .semibold)).foregroundStyle(Night.faint).textCase(.uppercase)
                        ForEach(files, id: \.path) { file in
                            HStack(spacing: 6) {
                                Image(systemName: "doc.text").font(.system(size: 9.5)).foregroundStyle(LibraryKind.colour(of: file.path) ?? Night.dim)
                                Text(file.path.title).font(.system(size: 11.5)).lineLimit(1)
                                Spacer(minLength: 4)
                                Text("×\(file.count)").font(.system(size: 10.5)).foregroundStyle(Night.faint).monospacedDigit()
                            }
                        }
                    }
                }
            }
            Divider().overlay(Night.line)
            Text(records.isEmpty ? "Click to set it up" : "Click to open its conversations").font(.system(size: 10.5)).foregroundStyle(Night.faint)
        }
        .padding(12)
        .frame(width: 270)
        .background(Color(white: 0.09).opacity(0.96), in: .rect(cornerRadius: 12))
        .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder(program.colour.opacity(0.35)) }
        .shadow(color: .black.opacity(0.6), radius: 18, y: 8)
    }

    static func mostRead(_ steps: [TrailStep], top: Int = 3) -> [(path: String, count: Int)] {
        var counts: [String: Int] = [:]
        for step in steps { for file in step.files { counts[String(file.split(separator: ":", maxSplits: 1).first ?? ""), default: 0] += 1 } }
        return counts.filter { !$0.key.isEmpty }.sorted { ($0.value, $1.key) > ($1.value, $0.key) }.prefix(top).map { ($0.key, $0.value) }
    }
}

/// The card over the vault: how much was read today, by whom, and the files read most.
struct VaultPeek: View {
    let workspace: Workspace
    let programs: [Program]

    var body: some View {
        let steps = programs.flatMap { FlowMap.today(workspace, $0) }
        let users = programs.filter { !FlowMap.today(workspace, $0).isEmpty }
        VStack(alignment: .leading, spacing: 8) {
            Text(workspace.name).font(.system(size: 13, weight: .semibold))
            Text("\(steps.count.counted("lookup")) today from \(users.count.counted("program"))").font(.system(size: 11.5)).foregroundStyle(Night.dim).monospacedDigit()
            ForEach(ProgramPeek.mostRead(steps), id: \.path) { file in
                HStack(spacing: 6) {
                    Image(systemName: "doc.text").font(.system(size: 9.5)).foregroundStyle(LibraryKind.colour(of: file.path) ?? Night.dim)
                    Text(file.path.title).font(.system(size: 11.5)).lineLimit(1)
                    Spacer(minLength: 4)
                    Text("×\(file.count)").font(.system(size: 10.5)).foregroundStyle(Night.faint).monospacedDigit()
                }
            }
            Divider().overlay(Night.line)
            Text("Click to open the map").font(.system(size: 10.5)).foregroundStyle(Night.faint)
        }
        .padding(12)
        .frame(width: 240)
        .background(Color(white: 0.09).opacity(0.96), in: .rect(cornerRadius: 12))
        .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder(Night.conversation.opacity(0.3)) }
        .shadow(color: .black.opacity(0.6), radius: 18, y: 8)
    }
}

// MARK: Rows

struct ProgramRow: View {
    let workspace: Workspace
    let program: Program
    let link: Connection?
    let highlighted: Bool
    @Binding var open: Bool
    @Binding var notice: String?
    let refresh: () async -> Void
    @State private var working = false

    private var canAdd: Bool { [.claudeCode, .openCode, .lmStudio].contains(program) && link?.state != .thisVault && link?.state != .missing }

    var body: some View {
        let records = workspace.sessions(for: program)
        let lookups = FlowMap.today(workspace, program).count
        let active = FlowMap.active(workspace, program)
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 12) {
                Image(systemName: program.symbol).font(.system(size: 15)).frame(width: 30, height: 30)
                    .foregroundStyle(records.isEmpty && link?.isLinked != true ? Night.faint : program.colour)
                    .background(program.colour.opacity(records.isEmpty ? 0.04 : 0.12), in: .rect(cornerRadius: 8))
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 8) {
                        Text(program.name).font(.system(size: 14, weight: .semibold))
                        if let link { chip(link) }
                        if active {
                            Text("Active").font(.system(size: 10.5, weight: .semibold)).foregroundStyle(.black)
                                .padding(.horizontal, 6).padding(.vertical, 1).background(program.colour, in: .capsule)
                        }
                    }
                    Text(records.isEmpty ? (link?.detail ?? "Not used yet") : "\(records.count.counted("conversation")) · \(lookups.counted("lookup")) today · last used \(records.first!.updated.formatted(.relative(presentation: .named)))")
                        .font(.system(size: 12)).foregroundStyle(Night.dim).monospacedDigit().lineLimit(1)
                }
                Spacer()
                if !records.isEmpty { Button("Conversations") { workspace.go(.conversations(program)) }.controlSize(.small) }
                Button { withAnimation(.smooth(duration: 0.2)) { open.toggle() } } label: {
                    Label(link?.isLinked == true ? "Setup" : "Connect", systemImage: open ? "chevron.up" : "chevron.down").labelStyle(.titleAndIcon)
                }
                .controlSize(.small)
            }
            if open { setup }
        }
        .padding(12)
        .background(highlighted ? Night.cardHover : Night.card, in: .rect(cornerRadius: 12))
        .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder(program.colour.opacity(highlighted ? 0.4 : 0)) }
        .animation(.smooth(duration: 0.15), value: highlighted)
    }

    private func chip(_ link: Connection) -> some View {
        let on = link.isLinked || link.state == .serving
        return Text(link.label).font(.system(size: 10.5, weight: .medium))
            .foregroundStyle(on ? program.colour : Night.dim)
            .padding(.horizontal, 6).padding(.vertical, 1)
            .overlay { Capsule().strokeBorder(on ? program.colour.opacity(0.5) : Night.line) }
            .help(link.detail)
    }

    private var setup: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let link { Text(link.detail).font(.system(size: 11.5)).foregroundStyle(Night.dim) }
            HStack(alignment: .top) {
                Text(program.setup(vault: workspace.folder.path))
                    .font(.system(size: 11.5, design: .monospaced)).textSelection(.enabled).foregroundStyle(Night.note.opacity(0.85))
                    .fixedSize(horizontal: false, vertical: true)
                Spacer()
                Button {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(program.setup(vault: workspace.folder.path), forType: .string)
                    notice = "Copied the \(program.name) setup"
                } label: { Label("Copy", systemImage: "doc.on.doc") }
                    .controlSize(.small)
                if canAdd {
                    Button(working ? "Adding…" : "Add for Me") { Task { await add() } }
                        .controlSize(.small).buttonStyle(.borderedProminent).tint(program.colour.opacity(0.85)).disabled(working)
                        .help("Writes this into \(program.name)'s settings; the old file is kept beside it as .before-burrow")
                }
            }
            .padding(10).background(Color.white.opacity(0.05), in: .rect(cornerRadius: 8))
        }
    }

    private func add() async {
        working = true
        defer { working = false }
        do {
            switch program {
            case .claudeCode: notice = try await Connections.addToClaudeCode(vault: workspace.folder)
            case .openCode: notice = try Connections.addToOpenCode(vault: workspace.folder)
            case .lmStudio: notice = try Connections.addToLMStudio(vault: workspace.folder)
            default: return
            }
            await refresh()
        } catch {
            notice = error.localizedDescription
        }
    }
}

/// Puts the `burrow` command where programs and the shell can find it: a link in ~/.local/bin to the copy inside the app.
enum CommandInstaller {
    static func install() throws -> String {
        let bundled = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/bin/burrow")
        guard FileManager.default.isExecutableFile(atPath: bundled.path) else {
            throw Connections.SetupError("This copy of Burrow has no command inside it. Build it with app/build.sh, or run swift build in the repository.")
        }
        let bin = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".local/bin")
        try FileManager.default.createDirectory(at: bin, withIntermediateDirectories: true)
        let link = bin.appendingPathComponent("burrow")
        if (try? link.checkResourceIsReachable()) == true || (try? FileManager.default.destinationOfSymbolicLink(atPath: link.path)) != nil {
            try FileManager.default.removeItem(at: link)
        }
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: bundled)
        return "Installed burrow in ~/.local/bin"
    }
}
