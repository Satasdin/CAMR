import Foundation

public enum LinkKind: String, Sendable {
    case imports  // this file imports that one
    case uses     // this file names something defined in that one
    case about    // this note is about that file
}

struct Link: Equatable {
    let from: String
    let to: String
    let kind: LinkKind
    let via: String?  // the symbol that made the link, so a walk can open the right part of the file
}

/// Works out how files connect, from the code itself. Nothing here calls a model.
enum LinkFinder {
    private static func regex(_ pattern: String) -> NSRegularExpression {
        try! NSRegularExpression(pattern: pattern, options: [.anchorsMatchLines])
    }

    private static let modifiers = #"(?:(?:export|default|public|private|fileprivate|internal|open|final|static|abstract|async|pub|override|indirect)\s+|@\w+\s+)*"#
    private static let declarations = regex(#"^\s*"# + modifiers + #"(?:def|class|func|function|struct|enum|protocol|interface|trait|type|fn|actor)\s+([A-Za-z_][A-Za-z0-9_]*)"#)
    private static let topLevelValues = regex(#"^"# + modifiers + #"(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)"#)
    private static let goMethods = regex(#"^func\s+\([^)]*\)\s+([A-Za-z_][A-Za-z0-9_]*)"#)
    private static let constants = regex(#"^([A-Z][A-Z0-9_]{3,})\s*(?::[^=\n]+)?=[^=]"#)

    private static let pythonFrom = regex(#"^\s*from\s+([.\w]+)\s+import\b"#)
    private static let pythonImport = regex(#"^\s*import\s+([.\w]+)"#)
    private static let scriptImport = regex(#"(?:from\s+|import\s+|require\(\s*)['"](\.{1,2}/[^'"]+)['"]"#)
    private static let cInclude = regex(#"^\s*#\s*include\s+"([^"]+)""#)
    private static let wikiLink = regex(#"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]"#)
    private static let markdownLink = regex(#"\]\(([^)\s]+)\)"#)
    private static let pathWord = regex(#"([\w.\-/]+\.\w+)"#)

    private static func captures(_ pattern: NSRegularExpression, in text: String) -> [String] {
        let range = NSRange(text.startIndex..., in: text)
        return pattern.matches(in: text, range: range).compactMap { match in
            Range(match.range(at: 1), in: text).map { String(text[$0]) }
        }
    }

    static func definedSymbols(in text: String) -> Set<String> {
        var out = Set(captures(declarations, in: text))
        out.formUnion(captures(topLevelValues, in: text))
        out.formUnion(captures(goMethods, in: text))
        out.formUnion(captures(constants, in: text))
        return out.filter { $0.count >= 4 && $0 != "init" }
    }

    /// Every link in the project. `notes` are the paths of Markdown notes kept by Burrow.
    static func links(files: [String: String], notes: Set<String>) -> [Link] {
        let paths = Array(files.keys).sorted()
        let known = Set(paths)
        var byName: [String: [String]] = [:]
        for path in paths { byName[(path as NSString).lastPathComponent, default: []].append(path) }

        var definedIn: [String: [String]] = [:]
        var names: [String: Set<String>] = [:]
        var usedBy: [String: Int] = [:]
        for path in paths {
            let text = files[path]!
            if !notes.contains(path) {
                for symbol in definedSymbols(in: text) { definedIn[symbol, default: []].append(path) }
            }
            let found = Set(Words.identifiers(in: text))
            names[path] = found
            found.forEach { usedBy[$0, default: 0] += 1 }
        }

        // A name that nearly every file mentions connects nothing.
        let commonAbove = max(5, paths.count / 10)
        var out: [Link] = []
        var seen = Set<String>()
        func add(_ from: String, _ to: String, _ kind: LinkKind, _ via: String?) {
            guard from != to, seen.insert("\(from)\u{0}\(to)\u{0}\(kind.rawValue)").inserted else { return }
            out.append(Link(from: from, to: to, kind: kind, via: via))
        }

        for path in paths {
            let text = files[path]!
            let isNote = notes.contains(path)
            let kindForNames: LinkKind = isNote ? .about : .uses
            if isNote {
                for target in captures(wikiLink, in: text) {
                    let clean = target.trimmingCharacters(in: .whitespaces)
                    for match in resolveNamed(clean, known: known, byName: byName) { add(path, match, .about, nil) }
                }
                let folder = (path as NSString).deletingLastPathComponent
                for target in captures(markdownLink, in: text) {
                    let clean = target.removingPercentEncoding ?? target
                    let local = normalise((folder as NSString).appendingPathComponent(clean))
                    for match in (known.contains(local) ? [local] : resolveNamed(clean, known: known, byName: byName)) { add(path, match, .about, nil) }
                }
                for word in Set(captures(pathWord, in: text)) where known.contains(word) { add(path, word, .about, nil) }
            } else {
                for target in importTargets(of: path, text: text, known: known) { add(path, target, .imports, nil) }
            }
            for name in names[path]!.sorted() {
                guard let homes = definedIn[name], homes.count <= 3, !homes.contains(path) else { continue }
                // A note may name a common symbol on purpose, but in a sentence "amount" or "text" is only a word.
                if isNote ? !namesCode(name, in: text) : (usedBy[name] ?? 0) > commonAbove { continue }
                homes.forEach { add(path, $0, kindForNames, name) }
            }
        }
        return out
    }

    /// Whether a note really means this name as code: its shape says so, or the way the note writes it does.
    private static func namesCode(_ name: String, in text: String) -> Bool {
        if name.contains("_") || name.first?.isUppercase == true || name.dropFirst().contains(where: \.isUppercase) { return true }
        return ["`\(name)`", "\(name)(", "function \(name)", "\(name) function"].contains { text.contains($0) }
    }

    private static func resolveNamed(_ target: String, known: Set<String>, byName: [String: [String]]) -> [String] {
        if known.contains(target) { return [target] }
        if known.contains(target + ".md") { return [target + ".md"] }
        if let direct = byName[target] { return direct }
        return byName[target + ".md"] ?? []
    }

    private static func importTargets(of path: String, text: String, known: Set<String>) -> [String] {
        let folder = (path as NSString).deletingLastPathComponent
        var out: [String] = []
        switch (path as NSString).pathExtension.lowercased() {
        case "py":
            let modules = captures(pythonFrom, in: text) + captures(pythonImport, in: text)
            for module in modules { out += resolvePython(module, folder: folder, known: known) }
        case "js", "jsx", "ts", "tsx", "mjs", "cjs", "vue", "svelte":
            for target in captures(scriptImport, in: text) {
                let base = normalise((folder as NSString).appendingPathComponent(target))
                let endings = ["", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".vue", ".svelte", "/index.ts", "/index.tsx", "/index.js"]
                if let hit = endings.map({ base + $0 }).first(where: known.contains) { out.append(hit) }
            }
        case "c", "h", "cc", "cpp", "hpp", "m", "mm":
            for target in captures(cInclude, in: text) {
                let local = normalise((folder as NSString).appendingPathComponent(target))
                if known.contains(local) { out.append(local) } else if let hit = known.sorted().first(where: { $0.hasSuffix("/" + target) }) { out.append(hit) }
            }
        default: break
        }
        return out
    }

    private static func resolvePython(_ module: String, folder: String, known: Set<String>) -> [String] {
        let dots = module.prefix { $0 == "." }.count
        let dotted = String(module.dropFirst(dots)).replacingOccurrences(of: ".", with: "/")
        var candidates: [String] = []
        if dots > 0 {
            var base = folder
            for _ in 1..<dots { base = (base as NSString).deletingLastPathComponent }
            candidates = [(base as NSString).appendingPathComponent(dotted)]
        } else {
            guard !dotted.isEmpty else { return [] }
            candidates = [dotted]
            // A package often lives under src/ or another top folder, so also accept a path that ends with the module.
            candidates += Set(known.compactMap { path -> String? in
                for ending in [".py", "/__init__.py"] where path.hasSuffix("/" + dotted + ending) {
                    return String(path.dropLast(ending.count))
                }
                return nil
            }).sorted()
        }
        for candidate in candidates {
            for ending in [".py", "/__init__.py"] where known.contains(candidate + ending) { return [candidate + ending] }
        }
        return []
    }

    private static func normalise(_ path: String) -> String {
        var parts: [Substring] = []
        for piece in path.split(separator: "/") {
            if piece == "." { continue }
            if piece == "..", !parts.isEmpty { parts.removeLast(); continue }
            parts.append(piece)
        }
        return parts.joined(separator: "/")
    }
}
