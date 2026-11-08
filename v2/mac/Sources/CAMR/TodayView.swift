// Today: a greeting, your shelves drawn as shelves (no pictures: a shelf is its memories), and what you told
// CAMR in this session.

import SwiftUI

struct TodayView: View {
    @ObservedObject var chat: ChatStore
    let go: (Place) -> Void

    private var greeting: String {
        let h = Calendar.current.component(.hour, from: Date())
        let part = h < 5 ? "Good evening" : (h < 12 ? "Good morning" : (h < 17 ? "Good afternoon" : "Good evening"))
        // your name only once you've given it (a setting), never the Mac's account name
        let name = UserDefaults.standard.string(forKey: "name") ?? ProcessInfo.processInfo.environment["CAMR_USER_NAME"] ?? ""
        return name.isEmpty ? part : "\(part), \(name)"
    }

    private var told: [Message] { chat.messages.filter { !$0.keptOn.isEmpty } }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                hero
                HStack(alignment: .firstTextBaseline) {
                    Text("Shelves").font(.headline)
                    Spacer()
                    Text("each line is one memory · green: used just now · dashed shelf: empty")
                        .font(.caption).foregroundStyle(.secondary)
                }
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: 3), spacing: 12) {
                    ForEach(chat.shelves) { s in
                        Button { go(.chat) } label: { ShelfCard(shelf: s) }.buttonStyle(.plain)
                    }
                }
                if !told.isEmpty {
                    Text("Told today").font(.headline)
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(told) { m in
                            HStack(alignment: .top, spacing: 10) {
                                Circle().fill(Channel.ssd).frame(width: 7, height: 7).padding(.top, 6)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(previousUserText(before: m) ?? m.text)
                                    Text("kept on \(m.keptOn)").font(.caption).foregroundStyle(.secondary)
                                }
                            }
                            .padding(.vertical, 8)
                            Divider()
                        }
                    }
                }
            }
            .padding(24)
        }
        .navigationTitle("Today")
        .navigationSubtitle("\(chat.shelves.reduce(0) { $0 + $1.memories }) memories on \(chat.shelves.count) shelves")
    }

    private func previousUserText(before m: Message) -> String? {
        guard let i = chat.messages.firstIndex(of: m), i > 0, chat.messages[i - 1].role == .you else { return nil }
        return chat.messages[i - 1].text
    }

    private var hero: some View {
        ZStack(alignment: .bottomLeading) {
            if let url = Bundle.main.url(forResource: "today", withExtension: "jpg"), let img = NSImage(contentsOf: url) {
                Image(nsImage: img).resizable().aspectRatio(contentMode: .fill)
                    .frame(height: 260).frame(maxWidth: .infinity).clipped()
                    .accessibilityLabel("Nairobi at night")
            } else {
                Rectangle().fill(Color.white.opacity(0.04)).frame(height: 260)
            }
            LinearGradient(colors: [.clear, .black.opacity(0.75)], startPoint: .center, endPoint: .bottom)
            VStack(alignment: .leading, spacing: 6) {
                Text(Date.now.formatted(.dateTime.weekday(.wide).day().month(.wide)).uppercased())
                    .font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.7))
                Text(greeting).font(.largeTitle.weight(.bold)).foregroundStyle(.white)
                Text("Everything you tell me stays on this Mac, sorted onto shelves I read from when you ask.")
                    .foregroundStyle(.white.opacity(0.8))
            }
            .padding(22)
        }
        .frame(height: 260)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}

struct ShelfCard: View {
    let shelf: Shelf

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: "books.vertical").foregroundStyle(.secondary)
                Text(shelf.label).font(.body.weight(.semibold))
                Spacer()
                Text(state).font(.caption).foregroundStyle(shelf.used > 0 ? Channel.used : .secondary)
            }
            HStack(alignment: .bottom, spacing: 1.5) {
                ForEach(0..<shelf.spineCount, id: \.self) { i in
                    Spine(height: height(i), kind: i < shelf.used ? .used : .rest).frame(width: 5)
                }
                Spacer(minLength: 0)
            }
            .frame(height: 34, alignment: .bottom)
            .overlay(alignment: .bottom) {
                Rectangle()
                    .fill(shelf.memories > 0 ? Channel.ssd.opacity(0.5) : .clear)
                    .overlay(Rectangle().strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [3, 2]))
                        .foregroundStyle(shelf.memories > 0 ? .clear : Color.white.opacity(0.25)))
                    .frame(height: 1.5)
            }
            Text(shelf.rooms > 0 ? "\(shelf.rooms) room\(shelf.rooms == 1 ? "" : "s")" : "nothing here yet")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.04)))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.white.opacity(0.07)))
    }

    private var state: String {
        if shelf.used > 0 { return "\(shelf.used) used just now" }
        if shelf.memories == 0 { return "empty" }
        return shelf.memories == 1 ? "1 memory" : "\(shelf.memories) memories"
    }

    private func height(_ i: Int) -> CGFloat {
        var h: UInt64 = 1469598103934665603
        for b in "\(shelf.id)#\(i)".utf8 { h = (h ^ UInt64(b)) &* 1099511628211 }
        return 12 + CGFloat(h % 20)
    }
}
