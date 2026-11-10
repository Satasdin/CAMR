import BurrowCore
import Foundation

public struct FileEdit: Equatable, Sendable {
    public let path: String
    public let content: String
    public init(path: String, content: String) {
        self.path = path
        self.content = content
    }
}

public struct ParsedReply: Equatable, Sendable {
    public var reads: [String] = []
    public var edits: [FileEdit] = []
    public var failures: [String] = []
    public init() {}
}

private func regex(_ pattern: String) -> NSRegularExpression { try! NSRegularExpression(pattern: pattern) }

/// Turns what a simulated developer agent wrote into files to open and files to replace.
public enum ReplyParser {
    private static let opening = regex(#"^\s*={3,}\s*FILE:\s*(.+?)\s*={3,}\s*$"#)
    private static let closing = regex(#"^\s*={3,}\s*END FILE\s*={3,}\s*$"#)
    private static let read = regex(#"^\s*READ:\s*(.+?)\s*$"#)
    private static let numbered = regex(#"^\d+:( |$)"#)

    private static func capture(_ pattern: NSRegularExpression, _ line: String) -> String? {
        let range = NSRange(line.startIndex..., in: line)
        guard let match = pattern.firstMatch(in: line, range: range), let found = Range(match.range(at: 1), in: line) else { return nil }
        return String(line[found])
    }

    private static func hits(_ pattern: NSRegularExpression, _ line: String) -> Bool {
        pattern.firstMatch(in: line, range: NSRange(line.startIndex..., in: line)) != nil
    }

    /// Nil for anything that could leave the project folder.
    public static func safePath(_ raw: String) -> String? {
        var path = raw.trimmingCharacters(in: CharacterSet(charactersIn: "`'\"[]<> \t"))
        while path.hasPrefix("./") { path = String(path.dropFirst(2)) }
        guard !path.isEmpty, !path.hasPrefix("/"), !path.hasPrefix("~"), !path.contains("\\"), !path.contains("\0") else { return nil }
        guard !path.split(separator: "/", omittingEmptySubsequences: false).contains(where: { $0 == ".." || $0.isEmpty }) else { return nil }
        return path
    }

    /// Search and walk show numbered lines and no memory shows none, so a copied number must not count against a mode.
    private static func withoutLineNumbers(_ lines: [String]) -> [String] {
        let filled = lines.filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
        guard !filled.isEmpty, filled.allSatisfy({ hits(numbered, $0) }) else { return lines }
        return lines.map { line in
            numbered.stringByReplacingMatches(in: line, range: NSRange(line.startIndex..., in: line), withTemplate: "")
        }
    }

    private static func content(_ lines: [String]) -> String {
        func blank(_ line: String) -> Bool { line.trimmingCharacters(in: .whitespaces).isEmpty }
        var body = lines
        while let first = body.first, blank(first) { body.removeFirst() }
        while let last = body.last, blank(last) { body.removeLast() }
        if let first = body.first, first.trimmingCharacters(in: .whitespaces).hasPrefix("```") { body.removeFirst() }
        if let last = body.last, last.trimmingCharacters(in: .whitespaces) == "```" { body.removeLast() }
        return withoutLineNumbers(body).joined(separator: "\n") + "\n"
    }

    /// - Parameter finished: true when the model stopped by itself. Then a missing END FILE line loses nothing, and the block is kept.
    ///   When the reply was cut off, an unclosed block is half a file, so it is dropped.
    public static func parse(_ text: String, finished: Bool = false) -> ParsedReply {
        var out = ParsedReply()
        var path: String?
        var body: [String] = []
        func closeUnfinished() {
            guard let current = path else { return }
            if finished { out.edits.append(FileEdit(path: current, content: content(body))) } else {
                out.failures.append("file block for \(current) was never closed")
            }
        }
        for raw in text.components(separatedBy: "\n") {
            let line = raw.hasSuffix("\r") ? String(raw.dropLast()) : raw
            if let name = capture(opening, line) {
                closeUnfinished()
                body = []
                if let safe = safePath(name) { path = safe } else {
                    path = nil
                    out.failures.append("refused path \(name)")
                }
            } else if hits(closing, line) {
                if let current = path { out.edits.append(FileEdit(path: current, content: content(body))) }
                path = nil
                body = []
            } else if path != nil {
                body.append(line)
            } else if let name = capture(read, line) {
                if let safe = safePath(name) { out.reads.append(safe) } else { out.failures.append("refused path \(name)") }
            }
        }
        closeUnfinished()
        return out
    }
}

public struct ProposedNote: Equatable, Sendable {
    public let kind: NoteKind
    public let text: String
    public init(kind: NoteKind, text: String) {
        self.kind = kind
        self.text = text
    }
}

public enum NoteParser {
    private static let line = try! NSRegularExpression(pattern: #"^[\s\-*]*(decision|rejected|bug)\s*:\s*(.+?)\s*$"#, options: .caseInsensitive)

    private static let about = try! NSRegularExpression(pattern: #"^[\s\-*]*(?:files?|function|functions|concerns)\s*:\s*(.+?)\s*$"#, options: .caseInsensitive)

    /// Models often name a note's file on the line after it. That line is part of the note, and it's what links the note to code.
    public static func parse(_ text: String) -> [ProposedNote] {
        var out: [ProposedNote] = []
        for raw in text.components(separatedBy: "\n") {
            let range = NSRange(raw.startIndex..., in: raw)
            if let match = line.firstMatch(in: raw, range: range),
               let kindRange = Range(match.range(at: 1), in: raw), let bodyRange = Range(match.range(at: 2), in: raw),
               let kind = NoteKind(rawValue: raw[kindRange].lowercased()) {
                out.append(ProposedNote(kind: kind, text: String(raw[bodyRange])))
            } else if let previous = out.last, let match = about.firstMatch(in: raw, range: range), let found = Range(match.range(at: 1), in: raw) {
                out[out.count - 1] = ProposedNote(kind: previous.kind, text: previous.text + " (" + raw[found] + ")")
            }
        }
        return out
    }
}

/// How an answer or a test run is judged. Nothing here calls a model.
public enum Grader {
    private static let dontKnow = try! NSRegularExpression(
        pattern: #"(don.t know|do not know|no record|not recorded|can.t tell|cannot tell|doesn.t say|does not say|isn.t stated|not stated|not documented|no information|don.t have (?:that|enough))"#,
        options: .caseInsensitive)

    public static func saidDontKnow(_ text: String) -> Bool {
        dontKnow.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)) != nil
    }

    private static func found(_ pattern: String, in text: String) throws -> Bool {
        let compiled = try NSRegularExpression(pattern: pattern)
        return compiled.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)) != nil
    }

    public static func ask(answer: String, mustContain: [String], mustNot: [String]) throws -> Bool {
        for pattern in mustContain where try !found(pattern, in: answer) { return false }
        for pattern in mustNot where try found(pattern, in: answer) { return false }
        return true
    }

    public static func outcome(output: String, exitCode: Int32, timedOut: Bool) -> TestOutcome {
        func number(_ pattern: String) -> Int {
            guard let compiled = try? NSRegularExpression(pattern: pattern),
                  let match = compiled.firstMatch(in: output, range: NSRange(output.startIndex..., in: output)),
                  let range = Range(match.range(at: 1), in: output) else { return 0 }
            return Int(output[range]) ?? 0
        }
        return TestOutcome(ran: number(#"Ran (\d+) tests?"#), failures: number(#"FAILED \([^)]*failures=(\d+)"#),
                           errors: number(#"FAILED \([^)]*errors=(\d+)"#), exitCode: exitCode, timedOut: timedOut)
    }
}

public struct TestOutcome: Equatable, Sendable {
    public let ran: Int
    public let failures: Int
    public let errors: Int
    public let exitCode: Int32
    public let timedOut: Bool
    /// A run with no tests in it has shown nothing, so it does not pass.
    public var passed: Bool { exitCode == 0 && !timedOut && ran > 0 }

    public init(ran: Int, failures: Int, errors: Int, exitCode: Int32, timedOut: Bool) {
        self.ran = ran
        self.failures = failures
        self.errors = errors
        self.exitCode = exitCode
        self.timedOut = timedOut
    }
}
