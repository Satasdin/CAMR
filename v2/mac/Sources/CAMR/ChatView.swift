// The chat: your messages in blue on the right, CAMR's answers as plain text, the shelves each answer took from,
// a thinking ring while the model works, and the composer.

import SwiftUI

struct ChatView: View {
    @ObservedObject var chat: ChatStore
    var open: (URL) -> Void = { _ in }
    @State private var draft = ""
    @FocusState private var focused: Bool
    @Environment(\.accessibilityReduceMotion) private var still

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 18) {
                        if chat.messages.isEmpty { welcome }
                        ForEach(chat.messages) { m in
                            MessageRow(message: m, status: m.pending ? chat.status : "", stage: chat.stage,
                                       scanning: chat.stage == .photo && m.id == chat.messages.dropLast().last?.id,
                                       open: open)
                                .id(m.id)
                                .transition(.asymmetric(insertion: .opacity.combined(with: .offset(y: 10)), removal: .opacity))
                        }
                    }
                    .animation(still ? nil : .spring(response: 0.34, dampingFraction: 0.86), value: chat.messages.count)
                    .frame(maxWidth: 680)
                    .frame(maxWidth: .infinity)
                    .padding(.horizontal, 28)
                    .padding(.vertical, 20)
                }
                .scrollEdgeEffectStyle(.soft, for: .bottom)
                .safeAreaInset(edge: .bottom, spacing: 0) { composer }  // the conversation slides under the glass
                .onChange(of: chat.messages) { _, list in
                    if let last = list.last { withAnimation(.easeOut(duration: 0.2)) { proxy.scrollTo(last.id, anchor: .bottom) } }
                }
            }
        }
        // a link in an answer may come from a web page the model read: only http(s), and only in CAMR's own private
        // browser, never another app, a file or a custom scheme
        .environment(\.openURL, OpenURLAction { url in
            guard Links.allowed(url, sources: chat.messages.compactMap(\.sourceURL)) else { return .discarded }
            open(url)
            return .handled
        })
        .navigationTitle(chat.title)
        .navigationSubtitle(chat.busy ? "answering…" : "")
        .toolbar {
            ToolbarItem(placement: .navigation) {
                Button { Task { await chat.newChat() } } label: { Label("New chat", systemImage: "square.and.pencil") }
                    .help("Start a new chat. Memory keeps everything it learned.")
            }
        }
        .onAppear { focused = true }
    }

    private var welcome: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("What’s on your mind?").font(.title2.weight(.semibold))
            Text("Ask anything, plan your week, or tell me something to remember. Everything stays on this Mac.")
                .foregroundStyle(.secondary)
        }
        .padding(.top, 80)
    }

    private var composer: some View {
        GlassEffectContainer(spacing: 8) {
            HStack(alignment: .bottom, spacing: 8) {
                Button { if let url = Attach.pick() { chat.attach(url) } } label: {
                    Image(systemName: "plus").frame(width: 22, height: 22)
                }
                .buttonStyle(.glass)
                .buttonBorderShape(.circle)
                .help("Add a photo or a file")
                HStack(alignment: .bottom, spacing: 6) {
                    TextField("Message CAMR", text: $draft, axis: .vertical)
                        .textFieldStyle(.plain)
                        .lineLimit(1...6)
                        .focused($focused)
                        .onSubmit(send)
                        .padding(.vertical, 6)
                        .padding(.leading, 8)
                    if chat.busy {
                        Button(action: chat.stop) { Image(systemName: "stop.fill").frame(width: 20, height: 20) }
                            .buttonStyle(.glass)
                            .buttonBorderShape(.circle)
                            .help("Stop the answer")
                            .transition(.scale(scale: 0.6).combined(with: .opacity))
                    } else {
                        Button(action: send) { Image(systemName: "arrow.up").fontWeight(.bold).frame(width: 20, height: 20) }
                            .buttonStyle(.glassProminent)
                            .buttonBorderShape(.circle)
                            .keyboardShortcut(.return, modifiers: .command)
                            .disabled(draft.trimmingCharacters(in: .whitespaces).isEmpty)
                            .help("Send")
                            .transition(.scale(scale: 0.6).combined(with: .opacity))
                    }
                }
                .animation(.snappy(duration: 0.2), value: chat.busy)
                .padding(.horizontal, 6).padding(.vertical, 4)
                .glassEffect(.regular, in: .rect(cornerRadius: 20))
            }
        }
        .frame(maxWidth: 680)
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 28).padding(.bottom, 16).padding(.top, 6)
    }

    private func send() {
        chat.send(draft)
        draft = ""
    }
}

struct MessageRow: View {
    let message: Message
    let status: String
    var stage = Stage.idle
    var scanning = false
    var open: (URL) -> Void = { _ in }

    var body: some View {
        switch message.role {
        case .you:
            HStack {
                Spacer(minLength: 80)
                VStack(alignment: .trailing, spacing: 6) {
                    if let url = message.image, let img = NSImage(contentsOf: url) {
                        Image(nsImage: img).resizable().aspectRatio(contentMode: .fill)
                            .frame(width: 260, height: 180)
                            .overlay { if scanning { ScanLine() } }
                            .clipShape(RoundedRectangle(cornerRadius: 14))
                    }
                    Text(message.text)
                        .textSelection(.enabled)
                        .padding(.horizontal, 14).padding(.vertical, 9)
                        .background(RoundedRectangle(cornerRadius: 18).fill(Color.accentColor))
                        .foregroundStyle(.white)
                }
            }
        case .camr:
            VStack(alignment: .leading, spacing: 8) {
                if message.pending && message.text.isEmpty {
                    HStack(spacing: 12) {
                        StageLoader(stage: stage)
                            .frame(width: 124, height: 26, alignment: .leading)  // the words stay put as loaders change
                            .animation(.easeOut(duration: 0.15), value: stage)
                        Text(status.isEmpty ? "Thinking…" : status).foregroundStyle(.secondary)
                    }
                } else {
                    Text(rendered(message.text))
                        .textSelection(.enabled)
                        .foregroundStyle(message.error ? Channel.fault : .primary)
                        .lineSpacing(3)
                }
                if let url = message.sourceURL {
                    Button { open(url) } label: {
                        Label("Read first: \(message.sourceTitle)", systemImage: "globe")
                            .font(.caption)
                            .padding(.horizontal, 8).padding(.vertical, 3)
                            .background(Capsule().fill(Color.white.opacity(0.07)))
                    }
                    .buttonStyle(.plain)
                    .help("Open in CAMR's browser")
                }
                if !message.used.isEmpty || !message.note.isEmpty || !message.keptOn.isEmpty {
                    HStack(spacing: 6) {
                        if !message.keptOn.isEmpty {
                            HStack(spacing: 5) {
                                Circle().fill(Channel.ssd).frame(width: 6, height: 6)
                                Text("Kept on \(message.keptOn)")
                            }
                            .font(.caption)
                            .padding(.horizontal, 8).padding(.vertical, 3)
                            .background(Capsule().fill(Color.white.opacity(0.07)))
                        }
                        ForEach(message.used, id: \.self) { s in
                            HStack(spacing: 5) {
                                Circle().fill(Channel.ram).frame(width: 6, height: 6)
                                Text(s)
                            }
                            .font(.caption)
                            .padding(.horizontal, 8).padding(.vertical, 3)
                            .background(Capsule().fill(Color.white.opacity(0.07)))
                        }
                        if !message.note.isEmpty {
                            Text(message.note).font(.caption).foregroundStyle(.tertiary).monospacedDigit()
                        }
                    }
                }
            }
        }
    }
}

/// An answer's Markdown (bold, italics, code, links) drawn as such, its lines and lists kept as written.
func rendered(_ text: String) -> AttributedString {
    (try? AttributedString(markdown: text, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)))
        ?? AttributedString(text)
}

/// Which links in an answer may open. An answer's text can carry links from a page the model read, so a link opens
/// only on the same site as a page CAMR itself read for the chat (its "Read first" source), only over http(s), and
/// never to this Mac or the local network. Anything else does nothing.
enum Links {
    static func allowed(_ url: URL, sources: [URL]) -> Bool {
        guard let scheme = url.scheme?.lowercased(), scheme == "http" || scheme == "https",
              let host = url.host?.lowercased(), !isLocal(host) else { return false }
        return sources.contains { $0.host?.lowercased() == host }
    }

    static func isLocal(_ host: String) -> Bool {
        if host == "localhost" || host.hasSuffix(".local") || host.hasSuffix(".localhost") || host == "::1" { return true }
        let parts = host.split(separator: ".").compactMap { Int($0) }
        guard parts.count == 4 else { return false }
        return parts[0] == 127 || parts[0] == 10 || parts[0] == 0 || (parts[0] == 169 && parts[1] == 254)
            || (parts[0] == 192 && parts[1] == 168) || (parts[0] == 172 && (16...31).contains(parts[1]))
    }
}
