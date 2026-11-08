// Agents: the helpers a lead can spin up, each on a model that fits its job, and whether this Mac has the memory
// to start it now. The rule (from the research, DECISIONS E-69): a helper starts only if its model plus its context
// fits in nine tenths of the free memory; otherwise it waits, or uses a smaller model, and says which. At most two
// helpers write at once, since a third would slow both.

import SwiftUI

struct Helper: Identifiable {
    let id: String
    let job: String
    let why: String
    var model: ModelsStore.Row?
    var status: String = ""
    var ready = false
    var waiting = false
}

struct AgentsView: View {
    @ObservedObject var engine: Engine
    @StateObject private var models = ModelsStore()

    private var freeGB: Double { max(0, models.ramGB - models.usedGB) }

    private var helpers: [Helper] {
        let local = models.rows.filter { $0.source == "mlx" && $0.role != "embedder" && !$0.name.lowercased().contains("embedding") }
        let loaded = local.first { $0.loaded }
        let small = local.filter { $0.params > 0 && $0.params < 2.0e9 }.min { $0.params < $1.params }
        let seer = local.first { $0.name.lowercased().contains("vl") }
        let coder = local.filter { !$0.loaded && $0.params > 5e9 && $0.verdict != "wont_run" && !$0.name.lowercased().contains("vl") }
            .min { $0.params < $1.params }
        var list = [
            Helper(id: "lead", job: "Lead", why: "plans the work and writes in your voice", model: loaded),
            Helper(id: "router", job: "Router", why: "sends each piece to the right helper; small and fast is enough", model: small),
            Helper(id: "seer", job: "Seer", why: "looks at photos and pages; needs a vision model", model: seer),
            Helper(id: "coder", job: "Coder", why: "code goes better on a bigger model", model: coder),
        ]
        for i in list.indices { decide(&list[i]) }
        return list
    }

    /// Start now, wait, or not on this Mac: the model's weights and some context must fit in 90% of what's free.
    private func decide(_ h: inout Helper) {
        guard let m = h.model else { h.status = "no suitable model on this Mac yet"; return }
        if m.loaded { h.status = "running"; h.ready = true; return }
        if m.verdict == "wont_run" { h.status = "too big for this Mac"; return }
        let need = m.diskGB * 1.05 + 0.5
        let usable = freeGB * 0.9
        if need <= usable {
            h.status = String(format: "can start now · needs %.1f GB", need)
            h.ready = true
        } else {
            h.status = String(format: "would wait · %.1f GB short", need - usable)
            h.waiting = true
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("A lead spins up helpers for bigger jobs, each on a model that suits it. Before starting one, CAMR checks this Mac has the memory; if not, the helper waits or uses a smaller model, and says so.")
                    .foregroundStyle(.secondary)
                HStack(spacing: 10) {
                    Image(systemName: "memorychip")
                    Text(String(format: "%.1f GB free of %.0f GB", freeGB, models.ramGB)).monospacedDigit()
                    Text("· pressure \(models.pressure)").foregroundStyle(.secondary)
                    Spacer()
                }
                .padding(12)
                .background(RoundedRectangle(cornerRadius: 10).fill(Color.white.opacity(0.04)))

                LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible())], spacing: 12) {
                    ForEach(helpers) { h in HelperCard(helper: h) }
                }

                Label("At most two helpers write at once: a third would slow both by about half.", systemImage: "clock")
                    .font(.callout).foregroundStyle(.secondary)
            }
            .padding(24)
        }
        .navigationTitle("Agents")
        .navigationSubtitle("helpers and the memory they need")
        .task { await models.load(engine) }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button { Task { await models.load(engine) } } label: { Label("Refresh", systemImage: "arrow.clockwise") }
            }
        }
    }
}

struct HelperCard: View {
    let helper: Helper

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                BreathingRing(on: helper.status == "running", color: helper.waiting ? Channel.ram : Channel.used)
                    .frame(width: 22, height: 22)
                Text(helper.job).font(.title3.weight(.semibold))
                Spacer()
                Text(helper.model?.name ?? "—").font(.caption)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(Capsule().fill(Color.white.opacity(0.08)))
            }
            Text(helper.why).font(.callout).foregroundStyle(.secondary)
            Text(helper.status).font(.caption.weight(.semibold))
                .foregroundStyle(helper.waiting ? Channel.ram : (helper.ready ? Channel.used : .secondary))
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.04)))
        .overlay(RoundedRectangle(cornerRadius: 12)
            .strokeBorder(helper.waiting ? Channel.ram.opacity(0.5) : Color.white.opacity(0.07),
                          style: StrokeStyle(lineWidth: 1, dash: helper.waiting ? [4, 3] : [])))
    }
}

/// A ring that breathes while its helper works, and rests when it doesn't.
struct BreathingRing: View {
    let on: Bool
    let color: Color

    var body: some View {
        TimelineView(.animation(paused: !on)) { t in
            let phase = on ? (sin(t.date.timeIntervalSinceReferenceDate * 2.8) + 1) / 2 : 0.3
            ZStack {
                Circle().stroke(color.opacity(0.35 + 0.65 * phase), lineWidth: 1.5).scaleEffect(0.82 + 0.18 * phase)
                Circle().fill(color.opacity(on ? 1 : 0.4)).frame(width: 6, height: 6)
            }
        }
    }
}
