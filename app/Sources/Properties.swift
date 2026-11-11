import AppKit
import BurrowCore
import SwiftUI

/// A note's front matter as Obsidian shows it: a panel of named properties above the page, not raw YAML.
struct NoteProperty: Identifiable, Equatable {
    enum Value: Equatable {
        case text(String)
        case list([String])
    }

    var id = UUID()
    var key: String
    var value: Value

    var textValue: String {
        switch value {
        case let .text(text): return text
        case let .list(items): return items.joined(separator: ", ")
        }
    }

    /// What kind of property this looks like, for its icon and how its value is drawn.
    var kind: Kind {
        let lower = key.lowercased()
        if case .list = value { return lower.contains("tag") ? .tags : .list }
        let text = textValue
        if lower.contains("tag") { return .tags }
        if text.range(of: #"^\d{4}-\d{2}-\d{2}"#, options: .regularExpression) != nil { return .date }
        if text.hasPrefix("http://") || text.hasPrefix("https://") { return .url }
        if text.hasPrefix("[[") { return .link }
        if Double(text) != nil { return .number }
        if ["true", "false"].contains(text.lowercased()) { return .check }
        return .text
    }

    enum Kind {
        case text, number, date, url, link, list, tags, check

        var symbol: String {
            switch self {
            case .text: return "text.alignleft"
            case .number: return "number"
            case .date: return "calendar"
            case .url: return "link"
            case .link: return "arrow.up.right.square"
            case .list: return "list.bullet"
            case .tags: return "tag"
            case .check: return "checkmark.square"
            }
        }
    }
}

/// Splits a note into its front matter and its body, and puts them back together without disturbing the body.
enum FrontMatter {
    struct Parts: Equatable {
        /// The front matter as written, through its closing "---" line; empty when the note has none.
        var header: String
        /// The blank lines between the front matter and the body, kept so a save changes nothing else.
        var gap: String
        var body: String
        var properties: [NoteProperty]

        static func == (a: Parts, b: Parts) -> Bool { a.header == b.header && a.gap == b.gap && a.body == b.body }
    }

    static func split(_ text: String) -> Parts {
        guard text.hasPrefix("---\n") else { return Parts(header: "", gap: "", body: text, properties: []) }
        let afterOpen = text.index(text.startIndex, offsetBy: 4)
        guard let close = text.range(of: "\n---", range: afterOpen..<text.endIndex) else { return Parts(header: "", gap: "", body: text, properties: []) }
        var end = close.upperBound
        // The closing line ends at its newline, or at the end of the file.
        if end < text.endIndex, text[end] == "\n" { end = text.index(after: end) }
        let header = String(text[..<end])
        let rest = String(text[end...])
        let gap = String(rest.prefix { $0 == "\n" })
        let yaml = String(text[afterOpen..<close.lowerBound])
        return Parts(header: header, gap: gap, body: String(rest.dropFirst(gap.count)), properties: parse(yaml))
    }

    /// Simple YAML as notes use it: `key: value`, `key: [a, b]`, and block lists of `- item` lines under a key.
    static func parse(_ yaml: String) -> [NoteProperty] {
        var out: [NoteProperty] = []
        for raw in yaml.components(separatedBy: "\n") {
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line.isEmpty || line.hasPrefix("#") { continue }
            if line.hasPrefix("- "), var last = out.popLast() {
                let item = unquote(String(line.dropFirst(2)))
                if case let .list(items) = last.value { last.value = .list(items + [item]) } else { last.value = .list(last.textValue.isEmpty ? [item] : [last.textValue, item]) }
                out.append(last)
                continue
            }
            guard let colon = line.firstIndex(of: ":") else { continue }
            let key = String(line[..<colon]).trimmingCharacters(in: .whitespaces)
            let value = String(line[line.index(after: colon)...]).trimmingCharacters(in: .whitespaces)
            if value.hasPrefix("["), value.hasSuffix("]") {
                let items = value.dropFirst().dropLast().split(separator: ",").map { unquote($0.trimmingCharacters(in: .whitespaces)) }.filter { !$0.isEmpty }
                out.append(NoteProperty(key: key, value: .list(items)))
            } else {
                out.append(NoteProperty(key: key, value: .text(unquote(value))))
            }
        }
        return out
    }

    static func unquote(_ text: String) -> String {
        if text.count >= 2, let first = text.first, let last = text.last, (first == "\"" && last == "\"") || (first == "'" && last == "'") {
            return String(text.dropFirst().dropLast())
        }
        return text
    }

    /// Front matter written back from properties: inline lists, and quotes only where YAML needs them.
    static func render(_ properties: [NoteProperty]) -> String {
        guard !properties.isEmpty else { return "" }
        func quoted(_ text: String) -> String {
            let risky = text.contains(": ") || text.hasPrefix("[") || text.hasPrefix("{") || text.hasPrefix("#")
            return risky || text.hasPrefix("'") || text.hasPrefix("\"") ? "\"" + text.replacingOccurrences(of: "\"", with: "\\\"") + "\"" : text
        }
        var lines = ["---"]
        for property in properties where !property.key.trimmingCharacters(in: .whitespaces).isEmpty {
            switch property.value {
            case let .text(text): lines.append("\(property.key): \(quoted(text))")
            case let .list(items): lines.append("\(property.key): [\(items.map { $0.contains(",") ? "\"\($0)\"" : $0 }.joined(separator: ", "))]")
            }
        }
        lines.append("---")
        return lines.joined(separator: "\n") + "\n"
    }

    static func join(_ parts: Parts) -> String {
        guard !parts.header.isEmpty else { return parts.body }
        // A header that does not end its line (a file that ends at its closing "---") gets one only when a body follows.
        let header = parts.header.hasSuffix("\n") || parts.body.isEmpty ? parts.header : parts.header + "\n"
        return header + parts.gap + parts.body
    }
}

/// The panel itself: a row per property, Obsidian's icons for each kind, editable where the note is.
struct PropertiesPanel: View {
    let workspace: Workspace
    @Bindable var document: Document
    let editable: Bool
    @State private var open = true
    @State private var adding = false
    @State private var newKey = ""

    private var parts: FrontMatter.Parts { FrontMatter.split(document.text) }

    var body: some View {
        let properties = parts.properties
        VStack(alignment: .leading, spacing: 6) {
            Button { withAnimation(.easeOut(duration: 0.15)) { open.toggle() } } label: {
                HStack(spacing: 6) {
                    Image(systemName: "chevron.right").font(.system(size: 9, weight: .semibold)).rotationEffect(.degrees(open ? 90 : 0))
                    Text("Properties").font(.system(size: 13, weight: .semibold))
                    Text("\(properties.count)").font(.system(size: 12)).foregroundStyle(Theme.inkSoft).monospacedDigit()
                }
                .foregroundStyle(Theme.ink).contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            if open {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(properties) { property in
                        PropertyRow(workspace: workspace, property: property, editable: editable,
                                    change: { replace(property, with: $0) }, remove: { remove(property) })
                    }
                }
                if editable {
                    if adding {
                        HStack(spacing: 8) {
                            Image(systemName: "plus").foregroundStyle(Theme.inkSoft).frame(width: 18)
                            TextField("Property name", text: $newKey).textFieldStyle(.plain).frame(width: 160)
                                .onSubmit { add() }
                            Button("Add") { add() }.controlSize(.small).disabled(newKey.trimmingCharacters(in: .whitespaces).isEmpty)
                            Button("Cancel") { adding = false; newKey = "" }.controlSize(.small)
                        }
                        .padding(.vertical, 4)
                    } else {
                        Button { adding = true } label: { Label("Add property", systemImage: "plus").font(.system(size: 12.5)) }
                            .buttonStyle(.plain).foregroundStyle(Theme.inkSoft).padding(.top, 2)
                    }
                }
            }
        }
        .frame(maxWidth: 720, alignment: .leading)
        .padding(.horizontal, 4).padding(.top, 28).padding(.bottom, 10)
        .overlay(alignment: .bottom) { Rectangle().fill(Theme.inkSoft.opacity(0.18)).frame(height: 1).frame(maxWidth: 720) }
    }

    private func write(_ properties: [NoteProperty]) {
        var next = parts
        next.header = FrontMatter.render(properties)
        workspace.edited(document, to: FrontMatter.join(next))
    }

    private func replace(_ old: NoteProperty, with new: NoteProperty) {
        write(parts.properties.map { $0.key == old.key ? new : $0 })
    }

    private func remove(_ property: NoteProperty) {
        write(parts.properties.filter { $0.key != property.key })
    }

    private func add() {
        let key = newKey.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ":", with: "")
        guard !key.isEmpty, !parts.properties.contains(where: { $0.key == key }) else { return }
        write(parts.properties + [NoteProperty(key: key, value: .text(""))])
        newKey = ""
        adding = false
    }
}

struct PropertyRow: View {
    let workspace: Workspace
    let property: NoteProperty
    let editable: Bool
    let change: (NoteProperty) -> Void
    let remove: () -> Void
    @State private var editing = false
    @State private var draft = ""
    @State private var hovering = false

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Image(systemName: property.kind.symbol).font(.system(size: 11.5)).foregroundStyle(Theme.inkSoft).frame(width: 18)
            Text(property.key).font(.system(size: 13)).foregroundStyle(Theme.inkSoft).lineLimit(1).frame(width: 130, alignment: .leading)
            if editing {
                TextField(property.key, text: $draft).textFieldStyle(.plain).font(.system(size: 13))
                    .onSubmit { commit() }
                    .onExitCommand { editing = false }
            } else {
                value.frame(maxWidth: .infinity, alignment: .leading)
                    .contentShape(Rectangle())
                    .onTapGesture { if editable, property.kind != .check { draft = property.textValue; editing = true } }
            }
            if editable, hovering, !editing {
                Button(action: remove) { Image(systemName: "xmark").font(.system(size: 9, weight: .bold)) }
                    .buttonStyle(.plain).foregroundStyle(Theme.inkSoft).help("Remove \(property.key)")
            }
        }
        .padding(.vertical, 4).padding(.horizontal, 6)
        .background(hovering ? Theme.inkSoft.opacity(0.07) : .clear, in: .rect(cornerRadius: 6))
        .onHover { hovering = $0 }
    }

    @ViewBuilder private var value: some View {
        switch property.value {
        case let .list(items):
            let isTags = property.kind == .tags
            FlowChips(items: items.map { isTags && !$0.hasPrefix("#") ? "#" + $0 : $0 }, accent: isTags)
        case let .text(text):
            if text.isEmpty {
                Text(editable ? "Empty" : "—").font(.system(size: 13)).foregroundStyle(Theme.inkSoft.opacity(0.7))
            } else {
                switch property.kind {
                case .url:
                    Button(text) { if let url = URL(string: text) { NSWorkspace.shared.open(url) } }
                        .buttonStyle(.link).font(.system(size: 13)).lineLimit(1).truncationMode(.middle)
                case .link:
                    let target = text.trimmingCharacters(in: CharacterSet(charactersIn: "[]")).components(separatedBy: "|").first ?? text
                    Button(target) { open(target) }.buttonStyle(.link).font(.system(size: 13))
                case .check:
                    // A checkbox toggles with one click, as in Obsidian.
                    Button {
                        var next = property
                        next.value = .text(text.lowercased() == "true" ? "false" : "true")
                        change(next)
                    } label: {
                        Image(systemName: text.lowercased() == "true" ? "checkmark.square.fill" : "square").foregroundStyle(Theme.ink)
                    }
                    .buttonStyle(.plain).disabled(!editable)
                default:
                    Text(text).font(.system(size: 13)).foregroundStyle(Theme.ink).textSelection(.enabled).lineLimit(3)
                }
            }
        }
    }

    private func open(_ name: String) {
        let lower = name.lowercased()
        if let file = workspace.map.files.first(where: { $0.path.title.lowercased() == lower || $0.path.lowercased() == lower }) {
            workspace.go(.file(file.path))
        }
    }

    private func commit() {
        editing = false
        var next = property
        // A value written as "a, b" stays a list when it was one.
        if case .list = property.value {
            next.value = .list(draft.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces).trimmingCharacters(in: CharacterSet(charactersIn: "#")) }.filter { !$0.isEmpty })
        } else {
            next.value = .text(draft.trimmingCharacters(in: .whitespaces))
        }
        if next != property { change(next) }
    }
}

/// Values of a list as small chips that wrap.
struct FlowChips: View {
    let items: [String]
    let accent: Bool

    var body: some View {
        WrapLayout(spacing: 5) {
            ForEach(items, id: \.self) { item in
                Text(item).font(.system(size: 12))
                    .padding(.horizontal, 8).padding(.vertical, 2)
                    .foregroundStyle(accent ? Color.accentColor : Theme.ink)
                    .background((accent ? Color.accentColor : Theme.inkSoft).opacity(0.13), in: .capsule)
            }
        }
    }
}

/// Lays children out left to right, wrapping onto new lines.
struct WrapLayout: Layout {
    var spacing: CGFloat = 6

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 400
        var x: CGFloat = 0, y: CGFloat = 0, line: CGFloat = 0, widest: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > 0, x + size.width > width { x = 0; y += line + spacing; line = 0 }
            x += size.width + spacing
            widest = max(widest, x)
            line = max(line, size.height)
        }
        return CGSize(width: min(widest, width), height: y + line)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, line: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > bounds.minX, x + size.width > bounds.maxX { x = bounds.minX; y += line + spacing; line = 0 }
            view.place(at: CGPoint(x: x, y: y), proposal: .unspecified)
            x += size.width + spacing
            line = max(line, size.height)
        }
    }
}
