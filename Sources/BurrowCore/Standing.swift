import Foundation

/// What a file is to the project. Tests and the output of past runs repeat the words of the code they are about,
/// so left alone they beat it in a search while explaining less. They stay findable; they just stop coming first.
enum Standing: Equatable {
    case main
    case test
    case output

    private static let outputFolders: Set<String> = [
        "results", "result", "output", "outputs", "logs", "log", "runs", "reports", "report", "artifacts", "snapshots", "__snapshots__", "fixtures",
    ]
    private static let testFolders: Set<String> = ["test", "tests", "__tests__", "spec", "specs"]

    static func of(_ path: String) -> Standing {
        let parts = path.split(separator: "/").map(String.init)
        guard let name = parts.last else { return .main }
        let kind = (name as NSString).pathExtension.lowercased()
        // Markdown is something a person wrote, whatever folder it sits in.
        if kind == "md" || kind == "markdown" { return .main }
        let folders = parts.dropLast()
        if Scanner.dataExtensions.contains(kind), folders.contains(where: { outputFolders.contains($0.lowercased()) }) { return .output }
        if folders.contains(where: { testFolders.contains($0.lowercased()) || $0.hasSuffix("Tests") }) { return .test }
        let stem = (name as NSString).deletingPathExtension
        // Capital T on purpose: `latest.py` is not a test.
        if stem.hasSuffix("Tests") || stem.hasSuffix("Test") || stem.hasPrefix("test_") || stem.hasSuffix("_test")
            || stem.hasSuffix(".test") || stem.hasSuffix(".spec") { return .test }
        return .main
    }
}

/// What a question shows about where its answer lives.
struct Asked {
    private static let aboutTests: Set<String> = ["test", "tests", "testing", "spec", "specs"]
    private static let aboutOutput: Set<String> = ["result", "results", "score", "scores", "log", "logs", "output", "outputs", "report", "reports"]
    private static let dashedOrDotted = try! NSRegularExpression(pattern: #"[A-Za-z0-9_]+(?:[-.][A-Za-z0-9_]+)+"#)

    let wantsTests: Bool
    let wantsOutput: Bool
    /// Names like `tune-03` or `Scanner.swift`, which the word search would otherwise split into common pieces.
    let names: Set<String>

    init(_ question: String) {
        let words = Set(Words.identifiers(in: question).map { $0.lowercased() })
        wantsTests = !words.isDisjoint(with: Self.aboutTests)
        wantsOutput = !words.isDisjoint(with: Self.aboutOutput)
        let range = NSRange(question.startIndex..., in: question)
        names = Set(Self.dashedOrDotted.matches(in: question, range: range).compactMap {
            Range($0.range, in: question).map { question[$0].lowercased() }
        })
    }

    /// True when the question typed the name of one of this path's folders or its file.
    func names(_ path: String) -> Bool {
        guard !names.isEmpty else { return false }
        return path.split(separator: "/").contains {
            let part = $0.lowercased()
            return names.contains(part) || names.contains((part as NSString).deletingPathExtension)
        }
    }

    /// How much of its search score a file keeps for this question.
    func weight(of path: String) -> Double {
        if names(path) { return 1 }
        switch Standing.of(path) {
        case .main: return 1
        case .test: return wantsTests ? 1 : 0.7
        case .output: return wantsOutput ? 1 : 0.4
        }
    }
}
