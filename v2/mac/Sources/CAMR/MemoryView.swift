// Memory: every shelf, large, with what the last answer did to it. When a new answer comes in, a line sweeps
// across the shelves (the search), the memories it took lift in amber, and the ones the model used turn green.
// Beside it, the steps with the times the engine measured.

import SwiftUI

struct MemoryView: View {
    @ObservedObject var chat: ChatStore

    var body: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 18) {
                if let run = chat.lastRun, !run.question.isEmpty {
                    HStack(spacing: 10) {
                        Text("Asked").font(.caption.weight(.semibold))
                            .padding(.horizontal, 8).padding(.vertical, 3)
                            .background(Capsule().fill(Color.accentColor)).foregroundStyle(.white)
                        Text(run.question).lineLimit(2)
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.05)))
                } else {
                    Text("Ask something in Chat and watch it travel through your shelves here.")
                        .foregroundStyle(.secondary)
                }

                ZStack(alignment: .topLeading) {
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 36), GridItem(.flexible())], spacing: 26) {
                        ForEach(chat.shelves) { s in BigShelf(shelf: s) }
                    }
                    Sweep(at: chat.lastRun?.at)
                }

                Spacer(minLength: 0)
                BigDesk(total: chat.deskTokens, memory: chat.deskMemoryTokens)
            }
            .padding(24)
            .frame(maxWidth: .infinity)

            Divider()

            VStack(alignment: .leading, spacing: 0) {
                Text("Step by step").font(.headline).padding(.bottom, 10)
                if let steps = chat.lastRun?.steps, !steps.isEmpty {
                    ForEach(Array(steps.enumerated()), id: \.offset) { _, step in
                        HStack(alignment: .top, spacing: 10) {
                            Circle().fill(color(step.name)).frame(width: 8, height: 8).padding(.top, 5)
                            VStack(alignment: .leading, spacing: 2) {
                                HStack {
                                    Text(step.name)
                                    Spacer()
                                    Text(step.value).foregroundStyle(.secondary).monospacedDigit()
                                }
                                Text(step.detail).font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        .padding(.vertical, 9)
                        Divider()
                    }
                } else {
                    Text("Nothing yet.").foregroundStyle(.secondary)
                }
                Spacer()
                Legend()
            }
            .padding(18)
            .frame(width: 300)
        }
        .navigationTitle("Memory")
        .navigationSubtitle("\(chat.shelves.count) shelves · \(chat.shelves.reduce(0) { $0 + $1.memories }) memories")
    }

    private func color(_ step: String) -> Color {
        switch step {
        case "Wake", "Keep", "Read asleep": return Channel.ssd
        case "Take", "Lay the desk": return Channel.ram
        case "Answer", "Used": return Channel.used
        default: return .white
        }
    }
}

struct BigShelf: View {
    let shelf: Shelf

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(shelf.label).font(.callout.weight(.semibold))
                Spacer()
                Text(note).font(.caption).foregroundStyle(.secondary)
            }
            HStack(alignment: .bottom, spacing: 2) {
                ForEach(0..<shelf.spineCount, id: \.self) { i in
                    Spine(height: height(i), kind: kind(i)).frame(width: 9)
                }
                Spacer(minLength: 0)
            }
            .frame(height: 50, alignment: .bottom)
            .overlay(alignment: .bottom) {
                Rectangle().fill(shelf.taken > 0 ? Channel.ssd.opacity(0.7) : Color.white.opacity(0.2)).frame(height: 2)
            }
        }
    }

    private var note: String {
        if shelf.waking { return "asleep → waking" }
        if shelf.memories == 0 { return "empty" }
        return shelf.memories == 1 ? "1 memory" : "\(shelf.memories) memories"
    }

    private func height(_ i: Int) -> CGFloat {
        var h: UInt64 = 1469598103934665603
        for b in "\(shelf.id)#\(i)".utf8 { h = (h ^ UInt64(b)) &* 1099511628211 }
        return 18 + CGFloat(h % 28)
    }

    private func kind(_ i: Int) -> Spine.Kind {
        if shelf.kept && i == shelf.spineCount - 1 { return .waking }
        if !shelf.takenIDs.isEmpty {  // the engine named them: light exactly those
            if shelf.usedIDs.contains(i) { return .used }
            if shelf.takenIDs.contains(i) { return .taken }
            return shelf.waking ? .waking : .rest
        }
        let n = shelf.spineCount
        let taken = Array(Set((0..<min(shelf.taken, n)).map { ($0 * 7 + 5) % n })).sorted()
        if let k = taken.firstIndex(of: i) { return k < shelf.used ? .used : .taken }
        return shelf.waking ? .waking : .rest
    }
}

/// The search, drawn as a line that crosses every shelf once when a new question arrives.
struct Sweep: View {
    let at: Date?

    var body: some View {
        TimelineView(.animation) { t in
            GeometryReader { g in
                let age = at.map { t.date.timeIntervalSince($0) } ?? 99
                if age < 0.9 {
                    Rectangle()
                        .fill(LinearGradient(colors: [.clear, .white.opacity(0.9), .clear], startPoint: .top, endPoint: .bottom))
                        .frame(width: 2)
                        .shadow(color: .white.opacity(0.6), radius: 6)
                        .offset(x: g.size.width * age / 0.9)
                }
            }
        }
        .allowsHitTesting(false)
    }
}

struct BigDesk: View {
    let total: Int
    let memory: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("The desk: what the model reads for this answer").font(.callout.weight(.semibold))
                Spacer()
                Text(total == 0 ? "—" : "\(total.formatted()) tokens").font(.caption).foregroundStyle(.secondary).monospacedDigit()
            }
            GeometryReader { g in
                let mem = total > 0 ? CGFloat(memory) / CGFloat(total) : 0
                HStack(spacing: 3) {
                    RoundedRectangle(cornerRadius: 3).fill(Color.white.opacity(0.16)).frame(width: max(0, g.size.width * (1 - mem) - 3))
                    RoundedRectangle(cornerRadius: 3).fill(Channel.ram).frame(width: max(0, g.size.width * mem))
                }
                .animation(.easeOut(duration: 0.4), value: total)
            }
            .frame(height: 24)
            HStack {
                Text("instructions and your message")
                Spacer()
                Text("taken from memory").foregroundStyle(Channel.ram)
            }
            .font(.caption).foregroundStyle(.secondary)
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.04)))
    }
}

struct Legend: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            row(Channel.ssdRest, "a memory on its shelf")
            row(Channel.ssd, "waking from the SSD, or just kept")
            row(Channel.ram, "taken to the desk")
            row(Channel.used, "the model used it")
        }
        .font(.caption).foregroundStyle(.secondary)
    }

    private func row(_ c: Color, _ text: String) -> some View {
        HStack(spacing: 8) {
            RoundedRectangle(cornerRadius: 1.5).fill(c).frame(width: 8, height: 12)
            Text(text)
        }
    }
}
