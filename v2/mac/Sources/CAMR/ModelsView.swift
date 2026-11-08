// Models: this Mac (chip, memory in use, pressure) and every model on it, each with the engine's own verdict on
// whether it fits beside CAMR's memory, its measured speed, and a button to load it.

import SwiftUI

@MainActor
final class ModelsStore: ObservableObject {
    struct Row: Identifiable {
        let id: String
        var name: String
        var params: Double
        var active: Double
        var diskGB: Double
        var verdict: String
        var why: String
        var decodeTPS: Double?
        var firstWord: Double?
        var role: String
        var loaded: Bool
        var source: String
    }

    @Published var chip = ""
    @Published var ramGB = 0.0
    @Published var gpuCores = 0
    @Published var usedGB = 0.0
    @Published var weightsGB = 0.0
    @Published var pressure = ""
    @Published var rows: [Row] = []
    @Published var message = ""
    @Published var busy = ""

    func load(_ engine: Engine) async {
        guard let m = try? await engine.get("/api/models") else { message = "Couldn't read the models."; return }
        let hw = m["hardware"] as? JSON ?? [:]
        chip = hw["chip"] as? String ?? "This Mac"
        ramGB = Double(hw["ram_bytes"] as? Int ?? 0) / 1_073_741_824
        gpuCores = hw["gpu_cores"] as? Int ?? 0
        let now = m["now"] as? JSON ?? [:]
        usedGB = Double(now["used_bytes"] as? Int ?? 0) / 1_073_741_824
        pressure = now["pressure"] as? String ?? ""
        weightsGB = Double((m["ram"] as? JSON)?["weights_bytes"] as? Int ?? 0) / 1_073_741_824
        let list = (m["mlx"] as? [JSON] ?? []) + (m["ollama"] as? [JSON] ?? [])
        rows = list.map { j in
            let fit = j["fit"] as? JSON ?? [:]
            let measured = j["measured"] as? JSON
            return Row(id: j["id"] as? String ?? UUID().uuidString,
                       name: j["name"] as? String ?? j["repo"] as? String ?? "model",
                       params: j["params"] as? Double ?? 0, active: j["active_params"] as? Double ?? 0,
                       diskGB: Double(j["disk_bytes"] as? Int ?? j["weights_bytes"] as? Int ?? 0) / 1_073_741_824,
                       verdict: fit["verdict"] as? String ?? "", why: fit["why"] as? String ?? "",
                       decodeTPS: (fit["decode_tps"] as? Double) ?? (measured?["decode_tps"] as? Double),
                       firstWord: (fit["first_word_s"] as? Double) ?? (measured?["first_word_s"] as? Double),
                       role: j["role"] as? String ?? "", loaded: j["loaded"] as? Bool ?? false,
                       source: j["source"] as? String ?? "")
        }
        .sorted { ($0.loaded ? 0 : 1, $0.params) < ($1.loaded ? 0 : 1, $1.params) }
    }

    func use(_ row: Row, engine: Engine) async {
        busy = row.id
        message = ""
        do {
            _ = try await engine.post("/api/models/load", ["repo": row.id])
            message = "\(row.name) is loading."
        } catch {
            message = error.localizedDescription
        }
        busy = ""
        await load(engine)
    }
}

struct ModelsView: View {
    @ObservedObject var engine: Engine
    @StateObject private var store = ModelsStore()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                mac
                if !store.message.isEmpty {
                    Text(store.message).font(.callout).foregroundStyle(.secondary)
                }
                Text("Models on this Mac").font(.headline)
                VStack(spacing: 0) {
                    ForEach(store.rows) { r in
                        ModelRow(row: r, busy: store.busy == r.id) { Task { await store.use(r, engine: engine) } }
                        Divider()
                    }
                }
                .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.03)))
                streaming
            }
            .padding(24)
        }
        .navigationTitle("Models")
        .navigationSubtitle("\(store.rows.count) on this Mac")
        .task { await store.load(engine) }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button { Task { await store.load(engine) } } label: { Label("Refresh", systemImage: "arrow.clockwise") }
            }
        }
    }

    private var mac: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(store.chip).font(.title2.weight(.semibold))
                Text(String(format: "%.0f GB memory · %d-core GPU", store.ramGB, store.gpuCores)).foregroundStyle(.secondary)
                Spacer()
                Text("pressure \(store.pressure)").font(.caption)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(Capsule().fill((store.pressure == "normal" ? Channel.used : Channel.ram).opacity(0.18)))
                    .foregroundStyle(store.pressure == "normal" ? Channel.used : Channel.ram)
            }
            GeometryReader { g in
                let total = max(store.ramGB, 1)
                let other = max(0, store.usedGB - store.weightsGB)
                HStack(spacing: 2) {
                    RoundedRectangle(cornerRadius: 3).fill(Color.white.opacity(0.22)).frame(width: g.size.width * other / total)
                    RoundedRectangle(cornerRadius: 3).fill(Color.white.opacity(0.75)).frame(width: g.size.width * store.weightsGB / total)
                    RoundedRectangle(cornerRadius: 3).strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [3, 2]))
                        .foregroundStyle(Color.white.opacity(0.3))
                }
            }
            .frame(height: 16)
            HStack(spacing: 16) {
                Text(String(format: "other apps %.1f GB", max(0, store.usedGB - store.weightsGB)))
                Text(String(format: "CAMR's model %.1f GB", store.weightsGB))
                Text(String(format: "free %.1f GB", max(0, store.ramGB - store.usedGB)))
            }
            .font(.caption).foregroundStyle(.secondary).monospacedDigit()
        }
        .padding(16)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.04)))
    }

    private var streaming: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("Models bigger than this Mac’s memory", systemImage: "externaldrive.badge.icloud")
                .font(.headline)
            Text("Mixture-of-experts models keep most of their experts on the SSD and bring only the ones a word needs into memory. CAMR will run them this way next; their speeds will be measured here before they are claimed.")
                .font(.callout).foregroundStyle(.secondary)
        }
        .padding(16)
        .background(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.white.opacity(0.12), style: StrokeStyle(lineWidth: 1, dash: [4, 3])))
    }
}

struct ModelRow: View {
    let row: ModelsStore.Row
    let busy: Bool
    let use: () -> Void

    var body: some View {
        HStack(spacing: 14) {
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(row.name).font(.body.weight(.semibold))
                    if row.loaded {
                        Text("in use").font(.caption2.weight(.semibold))
                            .padding(.horizontal, 6).padding(.vertical, 2)
                            .background(Capsule().fill(Channel.used.opacity(0.2))).foregroundStyle(Channel.used)
                    }
                }
                Text(detail).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Text(speed).font(.caption).foregroundStyle(.secondary).monospacedDigit()
            verdictChip
            Button(row.loaded ? "In use" : "Use") { use() }
                .disabled(row.loaded || busy || row.verdict == "wont_run" || row.source != "mlx")
                .frame(width: 70)
        }
        .padding(.horizontal, 14).padding(.vertical, 11)
    }

    private var detail: String {
        var parts: [String] = []
        if row.params > 0 { parts.append(String(format: "%.1fB parameters", row.params / 1e9)) }
        if row.active > 0 && row.active < row.params * 0.9 { parts.append(String(format: "%.1fB at work per word", row.active / 1e9)) }
        if row.diskGB > 0 { parts.append(String(format: "%.1f GB", row.diskGB)) }
        if !row.role.isEmpty { parts.append(row.role == "embedder" ? "finds your memories" : (row.role == "reader" ? "reads and answers" : row.role)) }
        if row.source == "ollama" { parts.append("Ollama") }
        return parts.joined(separator: " · ")
    }

    private var speed: String {
        guard let t = row.decodeTPS else { return "" }
        let fw = row.firstWord.map { String(format: " · first word %.2f s", $0) } ?? ""
        return String(format: "%.0f tok/s", t) + fw
    }

    private var verdictChip: some View {
        let (text, color): (String, Color) = {
            switch row.verdict {
            case "fits": return ("Fits", Channel.used)
            case "tight": return ("Tight", Channel.ram)
            case "wont_run": return ("Too big", Channel.fault)
            default: return (row.verdict.isEmpty ? "—" : row.verdict, .secondary)
            }
        }()
        return Text(text).font(.caption.weight(.semibold))
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(Capsule().fill(color.opacity(0.16))).foregroundStyle(color)
            .help(row.why)
    }
}
