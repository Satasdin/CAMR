import Foundation

struct Chunk: Equatable {
    let startLine: Int  // 1-based, inclusive
    let endLine: Int
    let text: String
    /// Where the chunk sits in its document: the title, then the headings above it. Empty for code.
    var section = ""
}

/// Cuts a file into pieces a small model can read. A cut prefers the start of a declaration, then a blank line,
/// so that a function usually stays whole.
enum Chunker {
    static let aim = 45
    static let most = 80
    /// Matches what one excerpt can show. Prose can have very long lines, and anything past this would never be read.
    static let mostCharacters = 3_000

    private static let declaration = try! NSRegularExpression(
        pattern: #"^(?:export\s+|public\s+|private\s+|internal\s+|open\s+|final\s+|static\s+|async\s+|pub\s+|@\w+)*\s*(?:def|class|func|function|struct|enum|protocol|interface|trait|impl|extension|actor|fn|type)\b"#)

    static func startsDeclaration(_ line: String) -> Bool {
        let range = NSRange(line.startIndex..., in: line)
        return declaration.firstMatch(in: line, range: range) != nil
    }

    // MARK: Markdown

    /// Sections smaller than this are joined to the next one, so a run of one-line clauses doesn't become a run of tiny pieces.
    static let sectionAim = 1_500
    private static let heading = try! NSRegularExpression(pattern: #"^(#{1,6})\s+(.+?)\s*#*\s*$"#)

    /// A Markdown file is cut at its headings, so a clause stays with the heading that names it, and each piece carries its
    /// heading path ("Title › Part II › 7. Qualifications"). The path is indexed with the piece, so a question about
    /// "term of office" finds the clause under that heading even when the clause itself never says it.
    static func markdownChunks(of text: String) -> [Chunk] {
        var lines = text.components(separatedBy: "\n")
        if lines.last == "" { lines.removeLast() }
        guard !lines.isEmpty else { return [] }
        var title = ""
        var bodyStart = 0
        if lines[0].trimmingCharacters(in: .whitespaces) == "---", let close = lines.dropFirst().firstIndex(where: { $0.trimmingCharacters(in: .whitespaces) == "---" }) {
            for line in lines[1..<close] where line.hasPrefix("title:") {
                title = line.dropFirst(6).trimmingCharacters(in: .whitespaces).trimmingCharacters(in: CharacterSet(charactersIn: "\"'"))
            }
            bodyStart = close + 1
        }
        // Headings outside code fences, with their level.
        var marks: [(line: Int, level: Int, text: String)] = []
        var fenced = false
        for index in bodyStart..<lines.count {
            let line = lines[index]
            if line.hasPrefix("```") || line.hasPrefix("~~~") { fenced.toggle(); continue }
            guard !fenced, line.hasPrefix("#") else { continue }
            let range = NSRange(line.startIndex..., in: line)
            if let match = heading.firstMatch(in: line, range: range), let level = Range(match.range(at: 1), in: line), let name = Range(match.range(at: 2), in: line) {
                marks.append((index, line[level].count, String(line[name])))
            }
        }
        if title.isEmpty, let first = marks.first(where: { $0.level == 1 }) { title = first.text }
        guard !marks.isEmpty else {
            return chunks(of: text).map { Chunk(startLine: $0.startLine, endLine: $0.endLine, text: $0.text, section: title) }
        }
        // Sections: from each heading to the next. Anything before the first heading (front matter, a lead) is its own.
        var bounds: [(start: Int, end: Int, path: String)] = []
        var stack: [(level: Int, text: String)] = []
        func path() -> String {
            let names = stack.map(\.text).filter { $0 != title }
            return ([title].filter { !$0.isEmpty } + names).joined(separator: " › ")
        }
        if marks[0].line > 0 { bounds.append((0, marks[0].line, title)) }
        for (n, mark) in marks.enumerated() {
            while let last = stack.last, last.level >= mark.level { stack.removeLast() }
            stack.append((mark.level, mark.text))
            bounds.append((mark.line, n + 1 < marks.count ? marks[n + 1].line : lines.count, path()))
        }
        // Join small neighbours, split big ones the usual way.
        var out: [Chunk] = []
        var pending: (start: Int, end: Int, paths: [String])?
        func size(_ a: Int, _ b: Int) -> Int { lines[a..<b].reduce(0) { $0 + $1.count + 1 } }
        func flush() {
            guard let open = pending else { return }
            pending = nil
            let body = lines[open.start..<open.end].joined(separator: "\n")
            guard !body.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
            var unique: [String] = []
            for path in open.paths where !unique.contains(path) { unique.append(path) }
            let section = unique.count == 1 ? unique[0] : unique[0] + "; " + unique.dropFirst().map { $0.components(separatedBy: " › ").last ?? $0 }.joined(separator: "; ")
            out.append(Chunk(startLine: open.start + 1, endLine: open.end, text: body, section: String(section.prefix(300))))
        }
        for bound in bounds where bound.end > bound.start {
            if size(bound.start, bound.end) > mostCharacters {
                flush()
                var start = bound.start
                while start < bound.end {
                    let end = min(cut(Array(lines[0..<bound.end]), from: start), bound.end)
                    let body = lines[start..<end].joined(separator: "\n")
                    if !body.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        out.append(Chunk(startLine: start + 1, endLine: end, text: body, section: bound.path))
                    }
                    start = end
                }
                continue
            }
            if let open = pending, size(open.start, bound.end) <= sectionAim {
                pending = (open.start, bound.end, open.paths + [bound.path])
            } else {
                flush()
                pending = (bound.start, bound.end, [bound.path])
            }
        }
        flush()
        return out
    }

    static func chunks(of text: String) -> [Chunk] {
        var lines = text.components(separatedBy: "\n")
        if lines.last == "" { lines.removeLast() }
        guard !lines.isEmpty else { return [] }
        var out: [Chunk] = []
        var start = 0
        while start < lines.count {
            let end = cut(lines, from: start)
            let body = lines[start..<end].joined(separator: "\n")
            if !body.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                out.append(Chunk(startLine: start + 1, endLine: end, text: body))
            }
            start = end
        }
        return out
    }

    /// The line to stop before. Every line lands in exactly one chunk.
    private static func cut(_ lines: [String], from start: Int) -> Int {
        let lineLimit = min(start + most, lines.count)
        var limit = start + 1
        var size = lines[start].count + 1
        while limit < lineLimit, size + lines[limit].count + 1 <= mostCharacters {
            size += lines[limit].count + 1
            limit += 1
        }
        if limit < lineLimit {
            // Out of room before out of lines: end at the last blank line, so a paragraph stays whole.
            var index = limit
            while index > start + 1 {
                if lines[index - 1].trimmingCharacters(in: .whitespaces).isEmpty { return index }
                index -= 1
            }
            return limit
        }
        if limit == lines.count && limit - start <= aim { return limit }
        let earliest = min(start + aim, limit)
        var blank: Int?
        var index = earliest
        while index < limit {
            if startsDeclaration(lines[index]) { return index }
            if blank == nil, lines[index].trimmingCharacters(in: .whitespaces).isEmpty { blank = index + 1 }
            index += 1
        }
        return blank ?? limit
    }
}

/// Words a search should know about. `parseUserToken` also yields `parse`, `user` and `token`.
enum Words {
    private static let identifier = try! NSRegularExpression(pattern: #"[A-Za-z_][A-Za-z0-9_]*"#)
    static let ignored: Set<String> = [
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "from", "with", "by", "at", "as", "is", "are", "was", "were",
        "be", "been", "it", "its", "this", "that", "these", "those", "do", "does", "did", "how", "what", "why", "when", "where",
        "which", "who", "can", "could", "should", "would", "will", "i", "we", "you", "my", "our", "your", "me", "there", "if", "not",
    ]

    static func identifiers(in text: String) -> [String] {
        let range = NSRange(text.startIndex..., in: text)
        return identifier.matches(in: text, range: range).compactMap { Range($0.range, in: text).map { String(text[$0]) } }
    }

    static func parts(of name: String) -> [String] {
        var out: [String] = []
        for piece in name.split(separator: "_") {
            var current = ""
            let letters = Array(piece)
            for (index, letter) in letters.enumerated() {
                let nextIsLower = index + 1 < letters.count && letters[index + 1].isLowercase
                let previousIsUpper = index > 0 && letters[index - 1].isUppercase
                if letter.isUppercase, !current.isEmpty, !previousIsUpper || nextIsLower {
                    out.append(current)
                    current = ""
                }
                current.append(letter)
            }
            if !current.isEmpty { out.append(current) }
        }
        return out
    }

    /// The original text followed by the split-up form of every compound name, for the search index.
    static func expanded(_ text: String) -> String {
        var extra = Set<String>()
        for name in identifiers(in: text) {
            let split = parts(of: name)
            if split.count > 1 { split.forEach { extra.insert($0.lowercased()) } }
        }
        return extra.isEmpty ? text : text + "\n" + extra.sorted().joined(separator: " ")
    }

    /// A query for only the compound names in a question, such as `APP_MEMORY` or `parseUserToken`.
    /// Someone who types an exact name means that name, not its common parts.
    static func exactQuery(from question: String) -> String? {
        var seen = Set<String>()
        let names = identifiers(in: question).filter { parts(of: $0).count > 1 && seen.insert($0.lowercased()).inserted }
        return names.isEmpty ? nil : names.map { "\"\($0.lowercased())\"" }.joined(separator: " OR ")
    }

    /// Turns a question into an FTS5 query. Every term is quoted, so nothing typed can act as query syntax.
    static func query(from question: String) -> String? {
        var seen = Set<String>()
        var terms: [String] = []
        for name in identifiers(in: question) {
            for word in [name] + parts(of: name) {
                let lower = word.lowercased()
                guard lower.count > 1, !ignored.contains(lower), seen.insert(lower).inserted else { continue }
                terms.append("\"\(lower)\"")
            }
        }
        return terms.isEmpty ? nil : terms.joined(separator: " OR ")
    }
}
