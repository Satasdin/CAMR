import BurrowCore
import Foundation

struct DocSpan: Equatable {
    var text: String
    var style: Style
    /// Which link this piece of text belongs to, if any.
    var link: Int?
}

struct DocLine: Equatable {
    var spans: [DocSpan]
    /// The line of the source file this came from, counting from 1.
    var source: Int

    var plain: String { spans.map(\.text).joined() }
}

struct DocLink: Equatable {
    var label: String
    var target: String
    /// The vault path this leads to. Nil for a web address or a link to nothing.
    var resolved: String?
    var isExternal: Bool
}

struct RenderedDocument: Equatable {
    var lines: [DocLine] = []
    var links: [DocLink] = []
}

/// One character with how it should look.
private struct Glyph {
    var character: Character
    var style: Style
    var link: Int?
}

/// Turns a note or a code file into wrapped, styled lines. It knows nothing about the screen except its width.
struct DocumentRenderer {
    let width: Int
    let isNote: (String) -> Bool
    /// Finds the vault path a link means, as `[[name]]` or a relative path.
    let resolve: (_ target: String) -> String?

    private final class Builder {
        var document = RenderedDocument()
    }

    // MARK: Code

    func renderCode(_ text: String) -> RenderedDocument {
        var document = RenderedDocument()
        var lines = text.components(separatedBy: "\n")
        if lines.count > 1, lines.last == "" { lines.removeLast() }
        let gutter = max(3, String(lines.count).count)
        let room = max(8, width - gutter - 2)
        for (index, raw) in lines.enumerated() {
            let number = String(index + 1)
            let label = String(repeating: " ", count: gutter - number.count) + number + "  "
            var pieces = hardWrap(Self.expandTabs(raw), room)
            if pieces.isEmpty { pieces = [""] }
            for (position, piece) in pieces.enumerated() {
                let margin = position == 0 ? label : String(repeating: " ", count: gutter + 2)
                document.lines.append(DocLine(spans: [DocSpan(text: margin, style: .quiet), DocSpan(text: piece, style: .plain)], source: index + 1))
            }
        }
        return document
    }

    static func expandTabs(_ text: String) -> String { text.replacingOccurrences(of: "\t", with: "    ") }

    private func hardWrap(_ text: String, _ room: Int) -> [String] {
        var out: [String] = []
        var current = ""
        var used = 0
        for character in text {
            let cost = Cells.width(of: character)
            if cost == 0, character.isASCII { continue }
            if used + cost > room {
                out.append(current)
                current = ""
                used = 0
            }
            current.append(character)
            used += cost
        }
        if !current.isEmpty { out.append(current) }
        return out
    }

    // MARK: Notes

    /// Front matter as properties: `key: value`, `key: [a, b]`, and `- item` lines under a key.
    static func properties(_ yaml: [String]) -> [(key: String, items: [String])] {
        var out: [(key: String, items: [String])] = []
        func unquote(_ text: String) -> String {
            let trimmed = text.trimmingCharacters(in: .whitespaces)
            if trimmed.count >= 2, let first = trimmed.first, first == trimmed.last, first == "\"" || first == "'" { return String(trimmed.dropFirst().dropLast()) }
            return trimmed
        }
        for raw in yaml {
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line.isEmpty || line.hasPrefix("#") { continue }
            if line.hasPrefix("- "), !out.isEmpty {
                let item = unquote(String(line.dropFirst(2)))
                if out[out.count - 1].items == [""] { out[out.count - 1].items = [item] } else { out[out.count - 1].items.append(item) }
                continue
            }
            guard let colon = line.firstIndex(of: ":") else { continue }
            let key = String(line[..<colon]).trimmingCharacters(in: .whitespaces)
            let value = String(line[line.index(after: colon)...]).trimmingCharacters(in: .whitespaces)
            if value.hasPrefix("["), value.hasSuffix("]") {
                out.append((key, value.dropFirst().dropLast().split(separator: ",").map { unquote(String($0)) }.filter { !$0.isEmpty }))
            } else {
                out.append((key, [unquote(value)]))
            }
        }
        return out
    }

    func renderNote(_ text: String) -> RenderedDocument {
        let out = Builder()
        var lines = text.components(separatedBy: "\n")
        var index = 0
        if text.hasPrefix("---\n"), let close = lines.dropFirst().firstIndex(of: "---") {
            // Obsidian's properties: the front matter as named rows above the page, never as raw YAML.
            let properties = Self.properties(Array(lines[1..<close]))
            if !properties.isEmpty {
                let keyWidth = min(16, (properties.map { Cells.width(of: $0.key) }.max() ?? 4) + 2)
                for (number, property) in properties.enumerated() {
                    var spans = [DocSpan(text: Cells.pad(Cells.truncate(property.key, to: keyWidth - 2), to: keyWidth), style: .quiet)]
                    if property.items.count > 1 || property.key.lowercased().contains("tag") {
                        let tags = property.key.lowercased().contains("tag")
                        for (offset, item) in property.items.enumerated() {
                            if offset > 0 { spans.append(DocSpan(text: "  ", style: .plain)) }
                            spans.append(DocSpan(text: tags && !item.hasPrefix("#") ? "#" + item : item, style: Style(ink: tags ? .code : .plain)))
                        }
                    } else {
                        let value = property.items.first ?? ""
                        let ink: Ink = value.hasPrefix("http") || value.hasPrefix("[[") ? .code : .plain
                        spans.append(DocSpan(text: value.isEmpty ? "—" : value, style: value.isEmpty ? .quiet : Style(ink: ink)))
                    }
                    out.document.lines.append(DocLine(spans: spans, source: 2 + number))
                }
                out.document.lines.append(DocLine(spans: [], source: 1))
            }
            index = close + 1
            while index < lines.count, lines[index].trimmingCharacters(in: .whitespaces).isEmpty { index += 1 }
        }
        if lines.last == "" { lines.removeLast() }

        while index < lines.count {
            let line = Self.expandTabs(lines[index])
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            let source = index + 1

            if trimmed.hasPrefix("```") || trimmed.hasPrefix("~~~") {
                index = fence(lines, from: index, into: out)
            } else if isTable(lines, at: index) {
                index = table(lines, from: index, into: out)
            } else if trimmed.isEmpty {
                if out.document.lines.last?.spans.isEmpty == false { out.document.lines.append(DocLine(spans: [], source: source)) }
                index += 1
            } else if let (level, rest) = Self.heading(trimmed) {
                if !out.document.lines.isEmpty, out.document.lines.last?.spans.isEmpty == false { out.document.lines.append(DocLine(spans: [], source: source)) }
                let style = level == 1 ? Style(ink: .note, bold: true) : Style(bold: true, dim: level > 3)
                wrap(inline(rest, style, into: out), source: source, into: out)
                out.document.lines.append(DocLine(spans: [], source: source))
                index += 1
            } else if Self.isRule(trimmed) {
                out.document.lines.append(DocLine(spans: [DocSpan(text: String(repeating: "─", count: min(24, width)), style: .quiet)], source: source))
                index += 1
            } else if trimmed.hasPrefix(">") {
                let content = String(trimmed.drop { $0 == ">" }.drop { $0 == " " })
                let bar = [Glyph(character: "▎", style: Style(ink: .note, dim: true)), Glyph(character: " ", style: .plain)]
                wrap(inline(content, Style(italic: true), into: out), source: source, first: bar, rest: bar, into: out)
                index += 1
            } else if let item = Self.listItem(line) {
                let pad = String(repeating: " ", count: item.indent)
                var marker: [Glyph] = pad.map { Glyph(character: $0, style: .plain) }
                marker += item.marker.map { Glyph(character: $0, style: Style(ink: .note, dim: true)) }
                marker.append(Glyph(character: " ", style: .plain))
                let hanging = String(repeating: " ", count: item.indent + Cells.width(of: item.marker) + 1).map { Glyph(character: $0, style: .plain) }
                wrap(inline(item.text, item.done ? Style(dim: true) : .plain, into: out), source: source, first: marker, rest: hanging, into: out)
                index += 1
            } else {
                wrap(inline(trimmed, .plain, into: out), source: source, into: out)
                index += 1
            }
        }
        while out.document.lines.last?.spans.isEmpty == true { out.document.lines.removeLast() }
        return out.document
    }

    private static func heading(_ line: String) -> (Int, String)? {
        let level = line.prefix { $0 == "#" }.count
        guard (1...6).contains(level), line.dropFirst(level).first == " " else { return nil }
        return (level, line.dropFirst(level + 1).trimmingCharacters(in: CharacterSet(charactersIn: " #")))
    }

    private static func isRule(_ line: String) -> Bool {
        guard line.count >= 3, let first = line.first, "-*_".contains(first) else { return false }
        return line.allSatisfy { $0 == first || $0 == " " }
    }

    private static func listItem(_ line: String) -> (indent: Int, marker: String, text: String, done: Bool)? {
        let leading = line.prefix { $0 == " " }.count
        let body = line.dropFirst(leading)
        var marker: String
        var rest: Substring
        if let first = body.first, "-*+".contains(first), body.dropFirst().first == " " {
            marker = "•"
            rest = body.dropFirst(2)
        } else {
            let digits = body.prefix { $0.isNumber }
            let after = body.dropFirst(digits.count)
            guard !digits.isEmpty, let dot = after.first, ".)".contains(dot), after.dropFirst().first == " " else { return nil }
            marker = digits + "."
            rest = after.dropFirst(2)
        }
        var done = false
        if rest.hasPrefix("[ ] ") {
            marker = "☐"
            rest = rest.dropFirst(4)
        } else if rest.lowercased().hasPrefix("[x] ") {
            marker = "☑"
            rest = rest.dropFirst(4)
            done = true
        }
        return (min(leading, 12), marker, String(rest), done)
    }

    // MARK: Blocks

    private func fence(_ lines: [String], from start: Int, into out: Builder) -> Int {
        let opener = lines[start].trimmingCharacters(in: .whitespaces)
        let mark = String(opener.prefix(3))
        let language = opener.dropFirst(3).trimmingCharacters(in: .whitespaces)
        if !language.isEmpty { out.document.lines.append(DocLine(spans: [DocSpan(text: language, style: Style(ink: .code, dim: true))], source: start + 1)) }
        var index = start + 1
        while index < lines.count, !lines[index].trimmingCharacters(in: .whitespaces).hasPrefix(mark) {
            let pieces = hardWrap(Self.expandTabs(lines[index]), max(8, width - 2))
            for piece in pieces.isEmpty ? [""] : pieces {
                out.document.lines.append(DocLine(spans: [DocSpan(text: "  ", style: .plain), DocSpan(text: piece, style: .code)], source: index + 1))
            }
            index += 1
        }
        out.document.lines.append(DocLine(spans: [], source: min(index + 1, lines.count)))
        return index + 1
    }

    private func isTable(_ lines: [String], at index: Int) -> Bool {
        guard index + 1 < lines.count, lines[index].contains("|") else { return false }
        let rule = lines[index + 1].trimmingCharacters(in: .whitespaces)
        return rule.contains("-") && rule.contains("|") && rule.allSatisfy { "-:| ".contains($0) }
    }

    private static func cells(_ line: String) -> [String] {
        var trimmed = line.trimmingCharacters(in: .whitespaces)
        if trimmed.hasPrefix("|") { trimmed.removeFirst() }
        if trimmed.hasSuffix("|") { trimmed.removeLast() }
        return trimmed.components(separatedBy: "|").map { $0.trimmingCharacters(in: .whitespaces) }
    }

    private func table(_ lines: [String], from start: Int, into out: Builder) -> Int {
        var end = start
        while end < lines.count, lines[end].contains("|"), !lines[end].trimmingCharacters(in: .whitespaces).isEmpty { end += 1 }
        let rows = ([start] + Array((start + 2)..<max(start + 2, end))).map { (Self.cells(lines[$0]), $0) }
        let columns = rows.map(\.0.count).max() ?? 0
        var widths = Array(repeating: 0, count: columns)
        for row in rows.map(\.0) { for (column, cell) in row.enumerated() { widths[column] = max(widths[column], Cells.width(of: cell)) } }
        let needed = widths.reduce(0, +) + max(0, columns - 1) * 3
        if needed > width {
            // Too wide to line up here, so each row becomes a plain wrapped line.
            for (row, source) in rows { wrap(inline(row.joined(separator: "  ·  "), .plain, into: out), source: source + 1, into: out) }
        } else {
            for (position, (row, source)) in rows.enumerated() {
                var spans: [DocSpan] = []
                for column in 0..<columns {
                    let cell = column < row.count ? row[column] : ""
                    spans.append(DocSpan(text: Cells.pad(cell, to: widths[column]), style: position == 0 ? .strong : .plain))
                    if column < columns - 1 { spans.append(DocSpan(text: " │ ", style: .quiet)) }
                }
                out.document.lines.append(DocLine(spans: spans, source: source + 1))
            }
        }
        out.document.lines.append(DocLine(spans: [], source: end))
        return end
    }

    // MARK: Inline text

    private func addLink(_ label: String, target: String, into out: Builder) -> (Int, Style) {
        let external = target.contains("://") || target.hasPrefix("mailto:")
        let resolved = external ? nil : resolve(target)
        out.document.links.append(DocLink(label: label, target: target, resolved: resolved, isExternal: external))
        var style = Style(underline: true)
        if let resolved { style.ink = isNote(resolved) ? .note : .code } else if !external { style.dim = true }
        return (out.document.links.count - 1, style)
    }

    private func inline(_ text: String, _ base: Style, into out: Builder) -> [Glyph] {
        let chars = Array(text)
        var glyphs: [Glyph] = []
        var i = 0

        func find(_ needle: [Character], from start: Int) -> Int? {
            guard start + needle.count <= chars.count else { return nil }
            return (start...(chars.count - needle.count)).first { Array(chars[$0..<($0 + needle.count)]) == needle }
        }
        func literal(_ range: Range<Int>, _ style: Style, link: Int? = nil) {
            for index in range { glyphs.append(Glyph(character: chars[index], style: style, link: link)) }
        }
        func merged(_ extra: (inout Style) -> Void) -> Style {
            var style = base
            extra(&style)
            return style
        }
        func wordEdge(_ index: Int) -> Bool { index < 0 || index >= chars.count || !(chars[index].isLetter || chars[index].isNumber) }

        while i < chars.count {
            let c = chars[i]
            if c == "<", let end = find(Array("-->"), from: i), Array(chars[i..<min(i + 4, chars.count)]) == Array("<!--") {
                i = end + 3
            } else if c == "`", let end = find(["`"], from: i + 1), end > i + 1 {
                let content = String(chars[(i + 1)..<end])
                if content.contains("/") || content.contains("."), let resolved = resolve(content), !resolved.isEmpty {
                    let (index, style) = addLink(content, target: content, into: out)
                    for character in content { glyphs.append(Glyph(character: character, style: style, link: index)) }
                } else {
                    for character in content { glyphs.append(Glyph(character: character, style: merged { $0.ink = .code })) }
                }
                i = end + 1
            } else if c == "[" || c == "!", let wiki = wikiLink(chars, at: c == "!" ? i + 1 : i) {
                let (index, style) = addLink(wiki.label, target: wiki.target, into: out)
                for character in wiki.label { glyphs.append(Glyph(character: character, style: style, link: index)) }
                i = wiki.end
            } else if c == "[" || c == "!", let plain = markdownLink(chars, at: c == "!" ? i + 1 : i) {
                let target = plain.target.removingPercentEncoding ?? plain.target
                let (index, style) = addLink(plain.label, target: target, into: out)
                for character in plain.label { glyphs.append(Glyph(character: character, style: style, link: index)) }
                i = plain.end
            } else if (c == "*" || c == "_"), i + 1 < chars.count, chars[i + 1] == c, let end = find([c, c], from: i + 2), end > i + 2,
                      c == "*" || (wordEdge(i - 1) && wordEdge(end + 2)) {
                glyphs += inline(String(chars[(i + 2)..<end]), merged { $0.bold = true }, into: out)
                i = end + 2
            } else if (c == "*" || c == "_"), i + 1 < chars.count, chars[i + 1] != " ", let end = find([c], from: i + 1), end > i + 1,
                      c == "*" || (wordEdge(i - 1) && wordEdge(end + 1)) {
                glyphs += inline(String(chars[(i + 1)..<end]), merged { $0.italic = true }, into: out)
                i = end + 1
            } else if c == "#", i + 1 < chars.count, chars[i + 1].isLetter, i == 0 || chars[i - 1] == " " {
                var end = i + 1
                while end < chars.count, chars[end].isLetter || chars[end].isNumber || "_-/".contains(chars[end]) { end += 1 }
                literal(i..<end, Style(ink: .note, dim: true))
                i = end
            } else {
                glyphs.append(Glyph(character: c, style: base))
                i += 1
            }
        }
        return glyphs
    }

    private func wikiLink(_ chars: [Character], at start: Int) -> (target: String, label: String, end: Int)? {
        guard start + 3 < chars.count, chars[start] == "[", chars[start + 1] == "[" else { return nil }
        var end = start + 2
        while end + 1 < chars.count, !(chars[end] == "]" && chars[end + 1] == "]") { end += 1 }
        guard end + 1 < chars.count, end > start + 2 else { return nil }
        let inner = String(chars[(start + 2)..<end])
        let parts = inner.split(separator: "|", maxSplits: 1).map(String.init)
        let target = (parts[0].components(separatedBy: "#").first ?? parts[0]).trimmingCharacters(in: .whitespaces)
        let shown = parts.count > 1 ? parts[1] : ((parts[0] as NSString).lastPathComponent as String)
        return (target, shown, end + 2)
    }

    private func markdownLink(_ chars: [Character], at start: Int) -> (label: String, target: String, end: Int)? {
        guard start < chars.count, chars[start] == "[" else { return nil }
        var close = start + 1
        while close < chars.count, chars[close] != "]" { close += 1 }
        guard close + 1 < chars.count, chars[close + 1] == "(" else { return nil }
        var end = close + 2
        while end < chars.count, chars[end] != ")" { end += 1 }
        guard end < chars.count, end > close + 2 else { return nil }
        return (String(chars[(start + 1)..<close]), String(chars[(close + 2)..<end]).trimmingCharacters(in: .whitespaces), end + 1)
    }

    // MARK: Wrapping

    private func wrap(_ glyphs: [Glyph], source: Int, first: [Glyph] = [], rest: [Glyph] = [], into out: Builder) {
        let firstWidth = first.reduce(0) { $0 + Cells.width(of: $1.character) }
        let restWidth = rest.reduce(0) { $0 + Cells.width(of: $1.character) }
        var lines: [[Glyph]] = []
        var current: [Glyph] = []
        var used = 0
        var lastSpace: Int?

        func limit() -> Int { max(4, width - (lines.isEmpty ? firstWidth : restWidth)) }
        for glyph in glyphs {
            let cost = Cells.width(of: glyph.character)
            if used + cost > limit() {
                if let space = lastSpace {
                    let tail = Array(current[(space + 1)...])
                    lines.append(Array(current[..<space]))
                    current = tail
                    used = tail.reduce(0) { $0 + Cells.width(of: $1.character) }
                } else {
                    lines.append(current)
                    current = []
                    used = 0
                }
                lastSpace = nil
            }
            if glyph.character == " " { lastSpace = current.count }
            current.append(glyph)
            used += cost
        }
        lines.append(current)

        for (index, line) in lines.enumerated() {
            let whole = (index == 0 ? first : rest) + line
            var spans: [DocSpan] = []
            for glyph in whole {
                if let last = spans.indices.last, spans[last].style == glyph.style, spans[last].link == glyph.link {
                    spans[last].text.append(glyph.character)
                } else {
                    spans.append(DocSpan(text: String(glyph.character), style: glyph.style, link: glyph.link))
                }
            }
            out.document.lines.append(DocLine(spans: spans, source: source))
        }
    }
}
