// "Taking from memory": each shelf as a row of spines, one per memory. When an answer takes from a shelf, that
// many spines lift and turn amber (taken to the desk); an asleep shelf shows dashed until it wakes. At the bottom,
// the desk: how much of the model's reading is memory and how much is your message and its instructions.

import SwiftUI

struct MemoryPanel: View {
    @ObservedObject var chat: ChatStore

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Taking from memory").font(.headline)
            if chat.shelves.isEmpty {
                Text("No shelves yet. Tell CAMR something and it starts a shelf for it.")
                    .font(.callout).foregroundStyle(.secondary)
            }
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    ForEach(chat.shelves) { s in ShelfRow(shelf: s) }
                }
            }
            Spacer(minLength: 0)
            Desk(total: chat.deskTokens, memory: chat.deskMemoryTokens, window: chat.window)
        }
        .padding(16)
    }
}

struct ShelfRow: View {
    let shelf: Shelf

    private var state: (String, Color) {
        if shelf.kept { return ("1 new memory", Channel.ssd) }
        if shelf.waking { return ("waking · taking \(shelf.taken)", Channel.ssd) }
        if shelf.used > 0 { return ("\(shelf.used) of \(shelf.taken) used", Channel.used) }
        if shelf.taken > 0 { return ("\(shelf.taken) taken", Channel.ram) }
        if shelf.memories == 0 { return ("empty", .secondary) }
        return (shelf.memories == 1 ? "1 memory" : "\(shelf.memories) memories", .secondary)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(shelf.label).font(.callout.weight(.semibold))
                Spacer()
                Text(state.0).font(.caption).foregroundStyle(state.1)
            }
            HStack(alignment: .bottom, spacing: 2) {
                ForEach(0..<shelf.spineCount, id: \.self) { i in
                    Spine(height: spineHeight(i), kind: kind(i)).frame(width: 6)
                }
                Spacer(minLength: 0)
            }
            .frame(height: 30, alignment: .bottom)
            .overlay(alignment: .bottom) {
                Rectangle().fill(shelf.taken > 0 ? Channel.ssd.opacity(0.6) : Color.white.opacity(0.22)).frame(height: 1.5)
            }
        }
    }

    /// Each memory's spine has a steady height from its shelf and place, so shelves look the same every time.
    private func spineHeight(_ i: Int) -> CGFloat {
        var h: UInt64 = 1469598103934665603
        for b in "\(shelf.id)#\(i)".utf8 { h = (h ^ UInt64(b)) &* 1099511628211 }
        return 12 + CGFloat(h % 17)
    }

    /// Which spines are taken: spread along the shelf, not bunched at the start.
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

struct Spine: View {
    enum Kind { case rest, taken, used, waking, empty }
    let height: CGFloat
    let kind: Kind

    var body: some View {
        RoundedRectangle(cornerRadius: 1.5)
            .fill(fill)
            .overlay(RoundedRectangle(cornerRadius: 1.5)
                .strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [2, 1.5]))
                .foregroundStyle(kind == .empty ? Color.white.opacity(0.28) : .clear))
            .frame(height: height)
            .shadow(color: glow, radius: 3)
            .offset(y: kind == .taken || kind == .used ? -7 : 0)
            .animation(.spring(response: 0.35, dampingFraction: 0.8), value: kind)
    }

    private var fill: Color {
        switch kind {
        case .rest: return Channel.ssdRest
        case .taken: return Channel.ram
        case .used: return Channel.used
        case .waking: return Channel.ssd
        case .empty: return .clear
        }
    }

    private var glow: Color {
        switch kind {
        case .used: return Channel.used.opacity(0.6)
        case .waking: return Channel.ssd.opacity(0.5)
        default: return .clear
        }
    }
}

/// The desk: what the model reads for this answer, memory amber, the rest grey.
struct Desk: View {
    let total: Int
    let memory: Int
    let window: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("On the desk").font(.callout.weight(.semibold))
                Spacer()
                Text(total == 0 ? "—" : "\(total.formatted()) of \(window.formatted()) tokens")
                    .font(.caption).foregroundStyle(.secondary).monospacedDigit()
            }
            GeometryReader { g in
                let w = g.size.width
                let mem = total > 0 ? CGFloat(memory) / CGFloat(total) : 0
                HStack(spacing: 2) {
                    RoundedRectangle(cornerRadius: 2).fill(Color.white.opacity(0.18)).frame(width: max(0, w * (1 - mem) - 2))
                    RoundedRectangle(cornerRadius: 2).fill(Channel.ram).frame(width: max(0, w * mem))
                }
                .animation(.easeOut(duration: 0.3), value: total)
            }
            .frame(height: 12)
            HStack {
                Text("your message and instructions")
                Spacer()
                Text("from memory").foregroundStyle(Channel.ram)
            }
            .font(.caption2).foregroundStyle(.secondary)
        }
        .padding(.top, 12)
        .overlay(alignment: .top) { Divider() }
    }
}
