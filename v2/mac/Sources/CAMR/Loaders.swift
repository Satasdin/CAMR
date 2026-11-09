// The loaders. Each shows what is really happening, in one colour each (amber RAM, blue SSD, green the model at work)
// and moves only while that work runs. With Reduce Motion on, each holds still.

import SwiftUI

/// Where an answer has got to, from the engine's own events.
enum Stage: Equatable {
    case idle, finding, waking, taking, reading, writing, photo, filing
}

/// The loader for a stage of an answer.
struct StageLoader: View {
    let stage: Stage

    var body: some View {
        Group {
            switch stage {
            case .waking: WakeRoom()
            case .finding, .taking, .filing: FindSweep()
            default: ThinkingRing().frame(width: 24, height: 24)
            }
        }
        .transition(.opacity)
    }
}

/// Finding what you mean: a line passes over the memories, and the ones it matches flash.
struct FindSweep: View {
    @Environment(\.accessibilityReduceMotion) private var still
    private let rows = 4, columns = 16

    var body: some View {
        TimelineView(.animation(paused: still)) { t in
            Canvas { ctx, size in
                let cell = (size.width - CGFloat(columns - 1) * 2) / CGFloat(columns)
                let height = (size.height - CGFloat(rows - 1) * 2) / CGFloat(rows)
                let run = t.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: 1.4) / 1.4
                let line = still ? -1 : CGFloat(run) * (size.width + 24) - 12
                for r in 0..<rows {
                    for c in 0..<columns {
                        let x = CGFloat(c) * (cell + 2)
                        let hit = (c * 5 + r * 11) % 17 == 3
                        let lit = hit ? max(0, 1 - abs(x - line) / 22) : 0
                        let rect = CGRect(x: x, y: CGFloat(r) * (height + 2), width: cell, height: height)
                        ctx.fill(Path(roundedRect: rect, cornerRadius: 1), with: .color(Channel.ssdRest))
                        if lit > 0 { ctx.fill(Path(roundedRect: rect, cornerRadius: 1), with: .color(Channel.used.opacity(lit))) }
                    }
                }
                if !still {
                    ctx.fill(Path(CGRect(x: line, y: 0, width: 1.5, height: size.height)), with: .color(.white.opacity(0.85)))
                }
            }
        }
        .frame(width: 124, height: 26)
        .accessibilityLabel("Finding what you mean")
    }
}

/// Waking a shelf that was asleep on the SSD: a dashed outline turns solid and its cells fill blue.
struct WakeRoom: View {
    @Environment(\.accessibilityReduceMotion) private var still

    var body: some View {
        TimelineView(.animation(paused: still)) { t in
            let run = still ? 1 : t.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: 1.2) / 1.2
            ZStack {
                RoundedRectangle(cornerRadius: 3)
                    .strokeBorder(Channel.ssd.opacity(0.35 + 0.65 * run),
                                  style: StrokeStyle(lineWidth: 1.5, dash: run > 0.45 ? [] : [3, 2]))
                HStack(spacing: 2) {
                    ForEach(0..<10, id: \.self) { i in
                        RoundedRectangle(cornerRadius: 1)
                            .fill(Channel.ssd.opacity(run * 10 > Double(i) ? 1 : 0.1))
                    }
                }
                .padding(4)
            }
        }
        .frame(width: 112, height: 24)
        .shadow(color: Channel.ssd.opacity(0.35), radius: 5)
        .accessibilityLabel("Waking a shelf from the SSD")
    }
}

/// Seeing a photo: a line goes down it while this Mac reads it.
struct ScanLine: View {
    @Environment(\.accessibilityReduceMotion) private var still

    var body: some View {
        TimelineView(.animation(paused: still)) { t in
            GeometryReader { g in
                let run = t.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: 1.8) / 1.8
                if !still {
                    ZStack(alignment: .bottom) {
                        LinearGradient(colors: [.clear, Channel.used.opacity(0.28)], startPoint: .top, endPoint: .bottom)
                            .frame(height: 46)
                        Rectangle().fill(Channel.used).frame(height: 1.5).shadow(color: Channel.used, radius: 5)
                    }
                    .offset(y: g.size.height * run - 46)
                }
            }
        }
        .clipped()
        .allowsHitTesting(false)
        .accessibilityLabel("Reading the photo")
    }
}

/// A model going into memory, when the engine gives no count of layers: amber cells, a band of them travelling.
struct ModelCells: View {
    @Environment(\.accessibilityReduceMotion) private var still
    var count = 14

    var body: some View {
        TimelineView(.animation(paused: still)) { t in
            let head = t.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: 1.3) / 1.3 * Double(count + 4) - 2
            HStack(spacing: 2) {
                ForEach(0..<count, id: \.self) { i in
                    RoundedRectangle(cornerRadius: 1)
                        .fill(Channel.ram.opacity(still ? 0.7 : 0.14 + 0.86 * max(0, 1 - abs(Double(i) - head) / 3)))
                }
            }
        }
        .frame(width: 84, height: 12)
        .accessibilityLabel("Loading the model")
    }
}

/// Eight dots in a ring, lit in turn: the model is working.
struct ThinkingRing: View {
    @Environment(\.accessibilityReduceMotion) private var still

    var body: some View {
        TimelineView(.animation(paused: still)) { t in
            Canvas { ctx, size in
                let phase = t.date.timeIntervalSinceReferenceDate / 0.15
                let r = min(size.width, size.height) / 2 - 2
                for i in 0..<8 {
                    let a = Double(i) / 8 * 2 * .pi - .pi / 2
                    let p = CGPoint(x: size.width / 2 + r * cos(a), y: size.height / 2 + r * sin(a))
                    let age = (phase - Double(i)).truncatingRemainder(dividingBy: 8)
                    let glow = still ? 0.5 : max(0, 1 - (age < 0 ? age + 8 : age) / 4)
                    ctx.fill(Path(ellipseIn: CGRect(x: p.x - 2, y: p.y - 2, width: 4, height: 4)),
                             with: .color(Channel.used.opacity(0.18 + 0.82 * glow)))
                }
            }
        }
        .accessibilityLabel("Thinking")
    }
}
