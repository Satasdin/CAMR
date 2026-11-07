import SwiftUI

/// One model step of the agent, as the reasoning raster draws it: a tick for each word it wrote, at the moment it was
/// written; a cyan mark when memory was laid on the desk first; and the tool its step ended in.
struct StepTrace: Identifiable, Equatable {
    let id: Int
    var role: String  // the part's specialist: Designer, Builder...
    var start: Double  // the run clock (seconds) at its first word
    var ticks: [Double] = []  // the run clock at each word
    var read = false  // memory was laid on the desk for this step
    var tool: String?  // what it ended in: Wrote style.css, Tested the page...
    var ok = true
    var done = false
}

extension AgentState {
    /// A word arrived (a live "token" event): a new step starts at its first word.
    mutating func tick(_ e: [String: Any], role: String) {
        let t = e.num("t") ?? 0
        let n = Int(e.num("n") ?? 0)
        if n <= 1 || traces.last?.done != false || (traces.last.map { t < $0.start } ?? true) {
            traces.append(StepTrace(id: (traces.last?.id ?? 0) + 1, role: role, start: t, read: readNext))
            readNext = false
            if traces.count > 40 { traces.removeFirst(traces.count - 40) }
        }
        traces[traces.count - 1].ticks.append(t)
    }

    /// The step ended in a tool call (or an answer).
    mutating func ended(_ tool: String, ok: Bool) {
        guard !traces.isEmpty, !traces[traces.count - 1].done else { return }
        traces[traces.count - 1].tool = tool
        traces[traces.count - 1].ok = ok
        traces[traces.count - 1].done = true
    }
}

/// The plan as a ribbon: each part a node, joined in order. Done parts are white, the working one is amber with a glow
/// travelling into it along the line, a failed one is red, the rest are outlines. A dot under a node says who decided
/// the part was needed: amber for the model, grey for a rule. New parts slide in as the lead adds them.
struct PlanFlow: View {
    let parts: [PlanPart]
    let live: Bool

    var body: some View {
        ScrollViewReader { scroll in
            ScrollView(.horizontal, showsIndicators: false) {
                TimelineView(.animation(minimumInterval: 1 / 30, paused: !live)) { tl in
                    let phase = tl.date.timeIntervalSinceReferenceDate
                    HStack(spacing: 0) {
                        ForEach(Array(parts.enumerated()), id: \.element.id) { i, p in
                            if i > 0 { link(into: p, phase: phase) }
                            node(p, phase: phase).id(p.id)
                                .transition(.asymmetric(insertion: .scale(scale: 0.6).combined(with: .opacity), removal: .opacity))
                        }
                    }
                    .padding(.vertical, 6).padding(.horizontal, 4)
                    .animation(.spring(response: 0.45, dampingFraction: 0.8), value: parts.map(\.id))
                    .animation(.easeInOut(duration: 0.35), value: parts.map(\.state))
                }
            }
            .onChange(of: parts.first(where: { $0.state == "running" })?.id) { _, id in
                if let id { withAnimation(.easeInOut(duration: 0.4)) { scroll.scrollTo(id, anchor: .center) } }
            }
        }
    }

    private func color(_ s: String) -> Color {
        switch s {
        case "done": return Theme.text
        case "running": return Theme.model
        case "failed": return Theme.error
        default: return Theme.faint
        }
    }

    private func node(_ p: PlanPart, phase: Double) -> some View {
        let running = p.state == "running"
        let pulse = running ? 0.55 + 0.45 * (0.5 + 0.5 * sin(phase * 4)) : 1
        return VStack(spacing: 4) {
            ZStack {
                Circle().stroke(color(p.state).opacity(p.state == "todo" ? 0.5 : 1), lineWidth: 1.5).frame(width: 22, height: 22)
                if p.state == "done" { Circle().fill(Theme.text).frame(width: 10, height: 10) }
                if p.state == "failed" { Image(systemName: "xmark").font(.system(size: 9, weight: .bold)).foregroundStyle(Theme.error) }
                if running {
                    Circle().fill(Theme.model).frame(width: 10, height: 10).opacity(pulse)
                    Circle().stroke(Theme.model.opacity(0.35 * pulse), lineWidth: 6).frame(width: 30, height: 30).blur(radius: 3)
                }
            }
            .frame(width: 34, height: 30)
            Text(p.role.uppercased()).font(Theme.mono(8, .semibold))
                .foregroundStyle(running ? Theme.model : p.state == "todo" ? Theme.faint : Theme.dim)
            Circle().fill(p.by == "model" ? Theme.model.opacity(0.8) : Theme.faint).frame(width: 4, height: 4)
                .help(p.by == "model" ? "the model decided this part was needed" : "a rule planned this part")
        }
        .frame(width: 66)
        .help("\(p.role): \(p.title)" + (p.note.isEmpty ? "" : " (\(p.note))"))
    }

    /// The line into a part: lit up to a working part, with a glow travelling along it into the part.
    private func link(into p: PlanPart, phase: Double) -> some View {
        let lit = p.state != "todo"
        return Canvas { ctx, size in
            let y = 15.0
            var line = Path()
            line.move(to: CGPoint(x: 0, y: y))
            line.addLine(to: CGPoint(x: size.width, y: y))
            ctx.stroke(line, with: .color((lit ? Theme.text : Theme.faint).opacity(lit ? 0.5 : 0.35)), lineWidth: 1)
            if p.state == "running" {
                let x = (phase.truncatingRemainder(dividingBy: 1.2) / 1.2) * size.width
                let glow = Path(ellipseIn: CGRect(x: x - 5, y: y - 2.5, width: 10, height: 5))
                ctx.addFilter(.blur(radius: 2))
                ctx.fill(glow, with: .color(Theme.model))
            }
        }
        .frame(width: 22, height: 30)
        .offset(y: -12)
    }
}

/// The agent's reasoning as stacked traces: one row per model step, newest at the bottom, a tick per word written at
/// the moment it was written. The step writing now is amber and its newest words glow; finished steps fade. A cyan
/// mark at a row's start: memory was laid on the desk before that step. At its end: the tool the step called.
struct ReasoningRaster: View {
    let traces: [StepTrace]
    let live: Bool
    let rows = 7

    var body: some View {
        let shown = Array(traces.suffix(rows))
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("REASONING").font(Theme.mono(10, .semibold)).foregroundStyle(Theme.faint)
                Spacer()
                if let last = traces.last, last.ticks.count > 1, let a = last.ticks.first, let b = last.ticks.last, b > a {
                    Text(String(format: "step %d · %.0f words/s", last.id, Double(last.ticks.count - 1) / (b - a)))
                        .font(Theme.mono(10)).foregroundStyle(Theme.faint).monospacedDigit()
                }
            }
            TimelineView(.animation(minimumInterval: 1 / 30, paused: !live)) { tl in
                let now = tl.date
                VStack(alignment: .leading, spacing: 3) {
                    ForEach(Array(shown.enumerated()), id: \.element.id) { i, s in
                        row(s, age: shown.count - 1 - i, now: now)
                    }
                }
            }
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color.black.opacity(0.45)))
    }

    private func row(_ s: StepTrace, age: Int, now: Date) -> some View {
        let current = !s.done && age == 0
        let fade = current ? 1.0 : max(0.25, 0.85 - Double(age) * 0.1)
        return HStack(spacing: 6) {
            Text(s.role).font(Theme.mono(9)).foregroundStyle(current ? Theme.model : Theme.faint).frame(width: 64, alignment: .leading)
                .lineLimit(1)
            Circle().fill(s.read ? Theme.memory : Color.clear).frame(width: 5, height: 5)
                .shadow(color: Theme.memory.opacity(s.read ? 0.8 : 0), radius: 3)
            Canvas { ctx, size in
                guard let first = s.ticks.first else { return }
                let span = max((s.ticks.last ?? first) - first, 1)
                let scale = min(size.width / span, size.width / 30)  // 30 s fill a row; a faster step is shorter
                let n = s.ticks.count
                for (k, t) in s.ticks.enumerated() {
                    let x = (t - first) * scale
                    let newest = current && k >= n - 6
                    let tick = Path(CGRect(x: x, y: newest ? 1 : 3, width: 1, height: newest ? size.height - 2 : size.height - 6))
                    ctx.fill(tick, with: .color((current ? Theme.model : Theme.text).opacity(newest ? 1 : 0.55 * fade)))
                }
                if current, let t = s.ticks.last {  // the pen: a soft glow at the newest word
                    let x = (t - first) * scale
                    ctx.addFilter(.blur(radius: 3))
                    ctx.fill(Path(ellipseIn: CGRect(x: x - 4, y: 0, width: 8, height: size.height)), with: .color(Theme.model.opacity(0.8)))
                }
            }
            .frame(height: 12)
            Text(s.tool ?? (current ? "writing…" : "")).font(Theme.mono(9))
                .foregroundStyle(!s.ok ? Theme.error : current ? Theme.model.opacity(0.8) : Theme.dim.opacity(fade))
                .lineLimit(1).frame(width: 150, alignment: .leading)
        }
        .opacity(fade)
    }
}

/// The lead's latest decision, lit briefly when it is made (it fades over 2.4 s from ``at``): amber when the model
/// decided, white for a rule.
struct DecisionFlash: View {
    let decision: (by: String, text: String)?
    let at: Date

    var body: some View {
        if let d = decision {
            let fresh = Date().timeIntervalSince(at) < 2.5
            TimelineView(.animation(minimumInterval: 1 / 30, paused: !fresh)) { tl in
                let lit = max(0, 1 - tl.date.timeIntervalSince(at) / 2.4)
                let tint = d.by == "model" ? Theme.model : Theme.text
                HStack(alignment: .top, spacing: 8) {
                    Text(d.by == "model" ? "MODEL" : "RULE").font(Theme.mono(8, .semibold))
                        .padding(.horizontal, 5).padding(.vertical, 1)
                        .background(Capsule().stroke(d.by == "model" ? Theme.model : Theme.dim))
                        .foregroundStyle(d.by == "model" ? Theme.model : Theme.dim)
                    Text(d.text).font(Theme.mono(10)).foregroundStyle(Theme.text.opacity(0.6 + 0.4 * lit))
                        .lineLimit(2).fixedSize(horizontal: false, vertical: true)
                }
                .padding(.horizontal, 10).padding(.vertical, 6)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 7).fill(tint.opacity(0.08 * lit)))
                .overlay(RoundedRectangle(cornerRadius: 7).stroke(tint.opacity(0.12 + 0.45 * lit)))
            }
        }
    }
}

extension ChatModel {
    /// For a test script only (CAMR_SCRIPT "demo-agent"): the agent card driven by a made-up build, with no model, so
    /// the animations can be checked while the model is busy elsewhere. Never reachable from the app itself.
    func demoAgent(seconds: Double) async {
        turns.append(Turn(who: .you, text: "Make a website for Riverbank Physio (demo of the agent card, no model)"))
        var t = Turn(who: .camr, text: "", memory: true, pending: true, model: "demo")
        t.agent = AgentState()
        turns.append(t)
        let k = turns.count - 1
        let roles = [("Researcher", "Write the brief (BRIEF.md)", "rule"), ("Architect", "Decide the files and structure", "rule"),
                     ("Designer", "Write style.css", "model"), ("Builder", "Write index.html", "model"),
                     ("Behaviour", "Write app.js", "model"), ("Reviewer", "Test the page and fix it", "rule")]
        func plan(_ running: Int) -> [PlanPart] {
            roles.enumerated().map { i, r in
                PlanPart(id: "p\(i + 1)", role: r.0, title: r.1, state: i < running ? "done" : i == running ? "running" : "todo",
                         by: r.2, seconds: 0, note: "")
            }
        }
        let start = Date()
        var clock = 0.0
        var part = 0
        var n = 0
        while Date().timeIntervalSince(start) < seconds && part < roles.count {
            turns[k].agent?.plan = plan(part)
            if n == 0 {
                turns[k].agent?.readNext = part % 2 == 0
                if part == 2 {
                    turns[k].agent?.decisions.append(("model", "The architect named the files: style.css, index.html, app.js."))
                    turns[k].agent?.decidedAt = Date()
                }
            }
            n += 1
            clock += 1.0 / 30 * Double.random(in: 0.6...1.4)
            turns[k].agent?.tick(["t": clock, "n": Double(n)], role: roles[part].0)
            if n > 40 + part * 12 {
                turns[k].agent?.ended(["Wrote BRIEF.md", "Wrote ARCHITECTURE.md", "Wrote style.css", "Wrote index.html",
                                       "Wrote app.js", "Tested index.html"][part], ok: true)
                n = 0
                part += 1
                clock += 0.8
            }
            turns[k].agentRev += 1
            try? await Task.sleep(nanoseconds: 33_000_000)
        }
    }
}
