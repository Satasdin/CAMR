import SwiftUI

/// The session meters: a thin strip at the top of the chat with what the last answer cost, as the engine measured
/// it (camr_engine.app.routes.chat ``_pipe``): prompt processing and writing speed, the first word, the memory in
/// view and the memory held, and the SSD. Tap it for the same numbers for every answer in this chat.
struct MetersStrip: View {
    let turns: [Turn]
    @StateObject private var open = Open()
    final class Open: ObservableObject { @Published var on = false }

    private var answers: [(Int, Measured)] {
        turns.enumerated().compactMap { i, t in t.pipe.map { (i, $0) } }
    }

    var body: some View {
        if let last = answers.last?.1 {
            VStack(alignment: .leading, spacing: 0) {
                Button { withAnimation(.easeOut(duration: 0.2)) { open.on.toggle() } } label: {
                    HStack(spacing: 18) {
                        cell("prompt", tps(last.prefillTps), Theme.model)
                        cell("writing", tps(last.decodeTps), Theme.model)
                        cell("first word", secondsText(last.firstWord), Theme.text)
                        cell("in view", "\(grouped(last.context)) tok", Theme.memory)
                        cell("notes laid", last.notes > 0 ? "\(grouped(last.notes)) tok" : "—", Theme.memory)
                        cell("memory held", last.held.map { "\(short($0)) tok" } ?? "—", Theme.memory)
                        cell("on SSD", bytesText(last.diskBytes), Theme.memory)
                        cell("SSD read", last.gbps.map { String(format: "%.1f GB/s", $0) } ?? "—", Theme.memory)
                        Spacer(minLength: 0)
                        Image(systemName: open.on ? "chevron.up" : "chevron.down")
                            .font(.system(size: 9)).foregroundStyle(Theme.faint)
                    }
                    .padding(.horizontal, 32).padding(.vertical, 8)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .help("What the last answer cost. Tap for every answer in this chat.")
                if open.on { table }
                Rectangle().fill(Theme.line).frame(height: 1)
            }
            .background(Theme.panel.opacity(0.6))
        }
    }

    private var table: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 4) {
                row(["#", "mode", "prompt", "writing", "first word", "read as text", "in view", "notes laid", "held"],
                    header: true)
                ForEach(answers.reversed(), id: \.0) { i, m in
                    row(["\(i + 1)", m.mode, tps(m.prefillTps), tps(m.decodeTps), secondsText(m.firstWord),
                         "\(grouped(m.prefill))", "\(grouped(m.context))", m.notes > 0 ? grouped(m.notes) : "—",
                         m.held.map { short($0) } ?? "—"], header: false)
                }
            }
            .padding(.horizontal, 32).padding(.bottom, 10)
        }
        .frame(maxHeight: 180)
    }

    private func row(_ cols: [String], header: Bool) -> some View {
        HStack(spacing: 0) {
            ForEach(Array(cols.enumerated()), id: \.0) { k, c in
                Text(c).font(Theme.mono(10.5, header ? .semibold : .regular))
                    .foregroundStyle(header ? Theme.faint : Theme.dim)
                    .frame(width: k == 0 ? 34 : 96, alignment: .leading)
            }
        }
    }

    private func cell(_ label: String, _ value: String, _ tint: Color) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(label.uppercased()).font(Theme.mono(8.5)).foregroundStyle(Theme.faint)
            Text(value).font(Theme.mono(11.5, .medium)).foregroundStyle(tint.opacity(0.9))
        }
    }

    private func tps(_ v: Double?) -> String {
        guard let v, v > 0 else { return "—" }
        return v >= 1000 ? String(format: "%.1fk tok/s", v / 1000) : String(format: "%.0f tok/s", v)
    }

    private func grouped(_ n: Int) -> String { n.formatted(.number.grouping(.automatic)) }

    private func short(_ n: Int) -> String {
        n >= 1_000_000 ? String(format: "%.1fM", Double(n) / 1e6)
            : n >= 1000 ? String(format: "%.0fK", Double(n) / 1e3) : "\(n)"
    }
}
