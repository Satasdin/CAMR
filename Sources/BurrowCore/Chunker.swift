import Foundation

struct Chunk: Equatable {
    let startLine: Int  // 1-based, inclusive
    let endLine: Int
    let text: String
}

/// Cuts a file into pieces a small model can read. A cut prefers the start of a declaration, then a blank line,
/// so that a function usually stays whole.
enum Chunker {
    static let aim = 45
    static let most = 80

    private static let declaration = try! NSRegularExpression(
        pattern: #"^(?:export\s+|public\s+|private\s+|internal\s+|open\s+|final\s+|static\s+|async\s+|pub\s+|@\w+)*\s*(?:def|class|func|function|struct|enum|protocol|interface|trait|impl|extension|actor|fn|type)\b"#)

    static func startsDeclaration(_ line: String) -> Bool {
        let range = NSRange(line.startIndex..., in: line)
        return declaration.firstMatch(in: line, range: range) != nil
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
        let limit = min(start + most, lines.count)
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
