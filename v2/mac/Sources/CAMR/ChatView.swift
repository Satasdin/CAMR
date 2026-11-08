// The chat: your messages in blue on the right, CAMR's answers as plain text, the shelves each answer took from,
// a thinking ring while the model works, and the composer.

import SwiftUI

struct ChatView: View {
    @ObservedObject var chat: ChatStore
    @StateObject private var draft = Box("")
    @FocusState private var focused: Bool

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 18) {
                        if chat.messages.isEmpty { welcome }
                        ForEach(chat.messages) { m in
                            MessageRow(message: m, status: m.pending ? chat.status : "")
                                .id(m.id)
                        }
                    }
                    .frame(maxWidth: 680)
                    .frame(maxWidth: .infinity)
                    .padding(.horizontal, 28)
                    .padding(.vertical, 20)
                }
                .onChange(of: chat.messages) { _, list in
                    if let last = list.last { withAnimation(.easeOut(duration: 0.2)) { proxy.scrollTo(last.id, anchor: .bottom) } }
                }
            }
            composer
        }
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
        HStack(spacing: 6) {
            Button {} label: { Image(systemName: "plus") }
                .buttonStyle(.borderless)
                .frame(width: 28, height: 28)
                .background(Circle().fill(Color.white.opacity(0.1)))
                .help("Add a photo or a file")
            TextField("Message CAMR", text: $draft.value, axis: .vertical)
                .textFieldStyle(.plain)
                .lineLimit(1...6)
                .focused($focused)
                .onSubmit(send)
                .padding(.vertical, 6)
            if chat.busy {
                Button(action: chat.stop) { Image(systemName: "stop.fill") }
                    .buttonStyle(.borderless)
                    .frame(width: 28, height: 28)
                    .background(Circle().fill(Color.white.opacity(0.15)))
                    .help("Stop the answer")
            } else {
                Button(action: send) { Image(systemName: "arrow.up").fontWeight(.bold) }
                    .buttonStyle(.borderless)
                    .foregroundStyle(.white)
                    .frame(width: 28, height: 28)
                    .background(Circle().fill(draft.value.isEmpty ? Color.white.opacity(0.15) : Color.accentColor))
                    .keyboardShortcut(.return, modifiers: .command)
                    .disabled(draft.value.trimmingCharacters(in: .whitespaces).isEmpty)
                    .help("Send")
            }
        }
        .padding(.horizontal, 8).padding(.vertical, 5)
        .background(RoundedRectangle(cornerRadius: 20).fill(Color.white.opacity(0.07)))
        .overlay(RoundedRectangle(cornerRadius: 20).strokeBorder(Color.white.opacity(0.1)))
        .frame(maxWidth: 680)
        .padding(.horizontal, 28).padding(.bottom, 16).padding(.top, 6)
    }

    private func send() {
        chat.send(draft.value)
        draft.value = ""
    }
}

struct MessageRow: View {
    let message: Message
    let status: String

    var body: some View {
        switch message.role {
        case .you:
            HStack {
                Spacer(minLength: 80)
                Text(message.text)
                    .textSelection(.enabled)
                    .padding(.horizontal, 14).padding(.vertical, 9)
                    .background(RoundedRectangle(cornerRadius: 18).fill(Color.accentColor))
                    .foregroundStyle(.white)
            }
        case .camr:
            VStack(alignment: .leading, spacing: 8) {
                if message.pending && message.text.isEmpty {
                    HStack(spacing: 10) {
                        ThinkingRing().frame(width: 20, height: 20)
                        Text(status.isEmpty ? "Thinking…" : status).foregroundStyle(.secondary)
                    }
                } else {
                    Text(message.text)
                        .textSelection(.enabled)
                        .foregroundStyle(message.error ? Channel.fault : .primary)
                        .lineSpacing(3)
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

/// Eight dots in a ring, lit in turn: the model is working.
struct ThinkingRing: View {
    var body: some View {
        TimelineView(.animation) { t in
            Canvas { ctx, size in
                let phase = t.date.timeIntervalSinceReferenceDate / 0.15
                let r = min(size.width, size.height) / 2 - 2
                for i in 0..<8 {
                    let a = Double(i) / 8 * 2 * .pi - .pi / 2
                    let p = CGPoint(x: size.width / 2 + r * cos(a), y: size.height / 2 + r * sin(a))
                    let age = (phase - Double(i)).truncatingRemainder(dividingBy: 8)
                    let glow = max(0, 1 - (age < 0 ? age + 8 : age) / 4)
                    ctx.fill(Path(ellipseIn: CGRect(x: p.x - 2, y: p.y - 2, width: 4, height: 4)),
                             with: .color(Channel.used.opacity(0.18 + 0.82 * glow)))
                }
            }
        }
        .accessibilityLabel("Thinking")
    }
}
