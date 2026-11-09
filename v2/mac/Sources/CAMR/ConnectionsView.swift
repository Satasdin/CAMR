// Connections: MCP servers the model and its helpers may use. Ready-made ones from the engine's catalogue, and
// your own (a name and the command that starts it). Each shows its tools once connected, and whether its calls
// wait for your OK (the default) or run straight away.

import SwiftUI

@MainActor
final class ConnectionsStore: ObservableObject {
    struct Server: Identifiable {
        var id: String { name }
        var name: String
        var command: String
        var state: String
        var error: String
        var trusted: Bool
        var tools: [(name: String, about: String)]
        var calls: Int
    }

    struct Plugin: Identifiable {
        let id: String
        var name: String
        var about: String
        var added: Bool
    }

    @Published var servers: [Server] = []
    @Published var plugins: [Plugin] = []
    @Published var message = ""
    @Published var working = ""

    func load(_ engine: Engine) async {
        if let st = try? await engine.get("/api/code/state") { servers = (st["servers"] as? [JSON] ?? []).map(Self.server) }
        if let p = try? await engine.get("/api/code/plugins") {
            plugins = (p["plugins"] as? [JSON] ?? []).map {
                Plugin(id: $0["id"] as? String ?? "", name: $0["name"] as? String ?? "", about: $0["about"] as? String ?? "",
                       added: $0["added"] as? Bool ?? false)
            }
        }
    }

    static func server(_ j: JSON) -> Server {
        let args = (j["args"] as? [String] ?? []).joined(separator: " ")
        return Server(name: j["name"] as? String ?? "", command: ((j["command"] as? String ?? "") + " " + args).trimmingCharacters(in: .whitespaces),
                      state: j["state"] as? String ?? "idle", error: j["error"] as? String ?? "",
                      trusted: j["trusted"] as? Bool ?? false,
                      tools: (j["tools"] as? [JSON] ?? []).map { ($0["name"] as? String ?? "", $0["description"] as? String ?? "") },
                      calls: j["calls"] as? Int ?? 0)
    }

    func act(_ engine: Engine, _ path: String, _ body: JSON, busy: String) async {
        working = busy
        message = ""
        do {
            let r = try await engine.post(path, body)
            if let list = r["servers"] as? [JSON] { servers = list.map(Self.server) }
            if let list = r["plugins"] as? [JSON] {
                plugins = list.map { Plugin(id: $0["id"] as? String ?? "", name: $0["name"] as? String ?? "",
                                            about: $0["about"] as? String ?? "", added: $0["added"] as? Bool ?? false) }
            }
        } catch {
            message = error.localizedDescription
        }
        working = ""
        await load(engine)
    }
}

struct ConnectionsView: View {
    @ObservedObject var engine: Engine
    @StateObject private var store = ConnectionsStore()
    @State private var name = ""
    @State private var command = ""
    @State private var adding = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                Text("Tools from other apps and services, through MCP. Every call waits for your OK unless you allow a connection to run on its own.")
                    .foregroundStyle(.secondary)
                if !store.message.isEmpty {
                    Label(store.message, systemImage: "exclamationmark.triangle").foregroundStyle(Channel.ram)
                }

                section("Your connections") {
                    if store.servers.isEmpty {
                        Text("None yet. Add one from the list below or with its start command.")
                            .foregroundStyle(.secondary).padding(14)
                    }
                    ForEach(store.servers) { s in
                        ServerRow(server: s, busy: store.working == s.name,
                                  connect: { Task { await store.act(engine, s.state == "connected" ? "/api/code/mcp/disconnect" : "/api/code/mcp/connect", ["name": s.name], busy: s.name) } },
                                  trust: { on in Task { await store.act(engine, "/api/code/plugins/trust", ["id": s.name, "on": on], busy: s.name) } },
                                  remove: { Task { await store.act(engine, "/api/code/mcp/remove", ["name": s.name], busy: s.name) } })
                        Divider()
                    }
                }

                section("Ready to add") {
                    ForEach(store.plugins) { p in
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: "powerplug").frame(width: 28, height: 28)
                                .background(RoundedRectangle(cornerRadius: 7).fill(Color.accentColor.opacity(0.25)))
                            VStack(alignment: .leading, spacing: 3) {
                                Text(p.name).font(.body.weight(.semibold))
                                Text(p.about).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                            }
                            Spacer()
                            Button(p.added ? "Added" : "Add") {
                                Task { await store.act(engine, "/api/code/plugins/add", ["id": p.id], busy: p.id) }
                            }
                            .disabled(p.added || store.working == p.id)
                        }
                        .padding(14)
                        Divider()
                    }
                }

                section("Add your own") {
                    VStack(alignment: .leading, spacing: 10) {
                        TextField("Name, e.g. calendar", text: $name).textFieldStyle(.roundedBorder)
                        TextField("Command that starts it, e.g. npx -y @modelcontextprotocol/server-filesystem ~/Documents",
                                  text: $command).textFieldStyle(.roundedBorder)
                        HStack {
                            Text("It runs on this Mac only when you connect it.").font(.caption).foregroundStyle(.secondary)
                            Spacer()
                            Button("Add connection") {
                                Task {
                                    await store.act(engine, "/api/code/mcp/add", ["name": name, "command": command], busy: "add")
                                    if store.message.isEmpty { name = ""; command = "" }
                                }
                            }
                            .disabled(name.isEmpty || command.isEmpty)
                        }
                    }
                    .padding(14)
                }
            }
            .padding(24)
        }
        .navigationTitle("Connections")
        .navigationSubtitle("\(store.servers.filter { $0.state == "connected" }.count) connected")
        .task { await store.load(engine) }
    }

    private func section<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.headline)
            VStack(alignment: .leading, spacing: 0) { content() }
                .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.03)))
        }
    }
}

struct ServerRow: View {
    let server: ConnectionsStore.Server
    let busy: Bool
    let connect: () -> Void
    let trust: (Bool) -> Void
    let remove: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                Circle().fill(server.state == "connected" ? Channel.used : (server.error.isEmpty ? Color.white.opacity(0.3) : Channel.fault))
                    .frame(width: 8, height: 8)
                VStack(alignment: .leading, spacing: 2) {
                    Text(server.name).font(.body.weight(.semibold))
                    Text(server.command).font(.caption.monospaced()).foregroundStyle(.secondary).lineLimit(1)
                }
                Spacer()
                Picker("", selection: Binding(get: { server.trusted }, set: { trust($0) })) {
                    Text("Ask each time").tag(false)
                    Text("Always allow").tag(true)
                }
                .labelsHidden().frame(width: 140)
                Button(server.state == "connected" ? "Disconnect" : "Connect", action: connect).disabled(busy)
                Button(role: .destructive, action: remove) { Image(systemName: "trash") }.buttonStyle(.borderless).help("Remove")
            }
            if !server.error.isEmpty {
                Text(server.error).font(.caption).foregroundStyle(Channel.fault).textSelection(.enabled)
            }
            if !server.tools.isEmpty {
                Text("\(server.tools.count) tools · \(server.calls) calls so far").font(.caption).foregroundStyle(.secondary)
                ForEach(server.tools.prefix(8), id: \.name) { t in
                    HStack(alignment: .top, spacing: 8) {
                        Text(t.name).font(.caption.monospaced())
                        Text(t.about).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                    }
                }
            }
        }
        .padding(14)
    }
}
