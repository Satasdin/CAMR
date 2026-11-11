import AppKit
import BurrowCore
import BurrowTools
import QuickLookThumbnailing
import SwiftUI

/// Night Library: one colour per kind of thing, and nothing else is coloured.
enum Night {
    static let ground = Color.black
    static let card = Color(white: 0.075)
    static let cardHover = Color(white: 0.11)
    static let line = Color.white.opacity(0.09)
    static let dim = Color.white.opacity(0.55)
    static let faint = Color.white.opacity(0.32)

    static let note = Color(white: 0.96)
    static let document = Color(red: 1.00, green: 0.70, blue: 0.25)
    static let conversation = Color(red: 0.39, green: 0.82, blue: 1.00)
    static let cache = Color(red: 0.75, green: 0.35, blue: 0.95)
    static let stale = Color(red: 1.00, green: 0.27, blue: 0.23)
}

/// What the Library shows. The kind of a file decides its colour edge and where it is counted.
enum LibraryKind: String, CaseIterable, Hashable {
    case all, notes, documents, images, code

    var title: String {
        switch self {
        case .all: return "All"
        case .notes: return "Notes"
        case .documents: return "Documents"
        case .images: return "Images"
        case .code: return "Code"
        }
    }

    var symbol: String {
        switch self {
        case .all: return "square.grid.2x2"
        case .notes: return "doc.text"
        case .documents: return "doc.richtext"
        case .images: return "photo"
        case .code: return "chevron.left.forwardslash.chevron.right"
        }
    }

    static let documentExtensions: Set<String> = ["pdf", "docx", "doc", "rtf", "odt", "wordml"]
    static let imageExtensions: Set<String> = ["png", "jpg", "jpeg", "heic", "tif", "tiff", "gif", "bmp", "webp"]

    static func of(_ path: String) -> LibraryKind {
        let ext = (path as NSString).pathExtension.lowercased()
        if ["md", "markdown"].contains(ext) { return .notes }
        if documentExtensions.contains(ext) { return .documents }
        if imageExtensions.contains(ext) { return .images }
        return .code
    }

    func holds(_ path: String) -> Bool { self == .all || Self.of(path) == self }

    /// The colour that answers "what kind of thing is this". Code has none: it is the plain case.
    static func colour(of path: String) -> Color? {
        switch of(path) {
        case .notes: return Night.note
        case .documents, .images: return Night.document
        default: return nil
        }
    }
}

/// The programs that reach the vault through `burrow mcp`, named the way a person knows them.
enum Program: String, CaseIterable, Hashable, Identifiable {
    case claudeCode, openCode, lmStudio, llamaCpp, ollama, other
    var id: String { rawValue }

    static let known: [Program] = [.claudeCode, .openCode, .lmStudio, .llamaCpp, .ollama]

    init(client: String?) {
        let name = (client ?? "").lowercased().replacingOccurrences(of: " ", with: "").replacingOccurrences(of: "-", with: "")
        if name.contains("claude") { self = .claudeCode }
        else if name.contains("opencode") { self = .openCode }
        else if name.contains("lmstudio") { self = .lmStudio }
        else if name.contains("ollama") { self = .ollama }   // before llama.cpp: "ollama" contains "llama"
        else if name.contains("llama") { self = .llamaCpp }
        else { self = .other }
    }

    var name: String {
        switch self {
        case .claudeCode: return "Claude Code"
        case .openCode: return "OpenCode"
        case .lmStudio: return "LM Studio"
        case .llamaCpp: return "llama.cpp"
        case .ollama: return "Ollama"
        case .other: return "Other programs"
        }
    }

    var symbol: String {
        switch self {
        case .claudeCode: return "asterisk"
        case .openCode: return "chevron.left.forwardslash.chevron.right"
        case .lmStudio: return "cpu"
        case .llamaCpp: return "hare"
        case .ollama: return "terminal"
        case .other: return "app.connected.to.app.below.fill"
        }
    }

    /// How a person wires this program to the vault. Matches docs/connect.md.
    var setup: String {
        switch self {
        case .claudeCode: return "claude mcp add burrow -- burrow mcp <vault>"
        case .openCode: return "opencode.json → \"mcp\": { \"burrow\": { \"type\": \"local\", \"command\": [\"burrow\", \"mcp\", \"<vault>\"] } }"
        case .lmStudio: return "~/.lmstudio/mcp.json → \"burrow\": { \"command\": \"burrow\", \"args\": [\"mcp\", \"<vault>\"] }"
        case .llamaCpp: return "llama-server -m model.gguf --jinja -c 32768 --slot-save-path <vault>/.burrow/kv, then OpenCode's llamacpp provider"
        case .ollama: return "ollama create qwen3-4b-16k -f Modelfile, then OpenCode's ollama provider (see docs/connect.md)"
        case .other: return "burrow mcp <vault>"
        }
    }
}

/// One saved working-memory cache, with the reason it can't be used any more, if there is one.
struct ShelfItem: Identifiable, Sendable {
    let entry: KVShelf.Entry
    let stale: String?
    var id: String { entry.key + entry.model }
    var files: [String] { entry.sources.keys.sorted() }
}

typealias VaultSession = BurrowTools.SessionRecord

extension VaultSession {
    var program: Program { Program(client: client) }
    /// Every lookup that touched the vault, from the trail Burrow keeps itself.
    var lookups: Int { (trail ?? []).count }
    var question: String? { turns.first?.question ?? trail?.first(where: { !$0.asked.isEmpty })?.asked }
}

extension Workspace {
    /// Where a vault path lives on disk: inside the vault, or inside a linked folder.
    func fileURL(_ path: String) -> URL {
        for folder in linked where path == folder.name || path.hasPrefix(folder.name + "/") {
            let rest = String(path.dropFirst(folder.name.count)).trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            return rest.isEmpty ? folder.url : folder.url.appendingPathComponent(rest)
        }
        return folder.appendingPathComponent(path)
    }

    func count(_ kind: LibraryKind) -> Int { map.files.filter { kind.holds($0.path) }.count }

    func sessions(reading path: String) -> [VaultSession] {
        sessions.filter { $0.filesInPlay.contains { $0 == path || $0.hasPrefix(path + ":") } }
    }

    func sessions(for program: Program?) -> [VaultSession] {
        guard let program else { return sessions }
        return sessions.filter { $0.program == program }
    }
}

/// Real thumbnails from Quick Look: the first page of a PDF or Word file, the picture itself, or the first picture in a note.
@MainActor
final class Covers {
    static let shared = Covers()
    private var made: [String: NSImage] = [:]
    private var missing: Set<String> = []

    func cached(_ key: String) -> NSImage? { made[key] }
    func known(missing key: String) -> Bool { missing.contains(key) }

    func cover(for url: URL, size: CGSize) async -> NSImage? {
        let key = url.path + "@\(Int(size.width))"
        if let image = made[key] { return image }
        if missing.contains(key) { return nil }
        let scale = NSScreen.main?.backingScaleFactor ?? 2
        let request = QLThumbnailGenerator.Request(fileAt: url, size: size, scale: scale, representationTypes: .thumbnail)
        let image = try? await QLThumbnailGenerator.shared.generateBestRepresentation(for: request).nsImage
        if let image { made[key] = image } else { missing.insert(key) }
        return image
    }
}

enum NoteText {
    /// The first picture a note shows, as a vault path, so its cover can be a photo rather than words.
    static func firstPicture(in text: String, notePath: String, files: [MapFile]) -> String? {
        let patterns = [#"!\[\[([^\]|#]+)"#, #"!\[[^\]]*\]\(([^)\s]+)"#]
        for pattern in patterns {
            guard let regex = try? NSRegularExpression(pattern: pattern),
                  let match = regex.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
                  let range = Range(match.range(at: 1), in: text) else { continue }
            let target = String(text[range]).removingPercentEncoding ?? String(text[range])
            guard LibraryKind.imageExtensions.contains((target as NSString).pathExtension.lowercased()) else { continue }
            let beside = (notePath.folderPath as NSString).appendingPathComponent(target)
            if files.contains(where: { $0.path == beside }) { return beside }
            if let named = files.first(where: { $0.path == target || $0.path.hasSuffix("/" + target) }) { return named.path }
        }
        return nil
    }

    /// A Markdown line as a person would read it: no heading marks, bullets, emphasis or link brackets.
    static func plain(_ line: String) -> String {
        var text = line
        while let first = text.first, "#>-*+".contains(first) { text = String(text.dropFirst()).trimmingCharacters(in: .whitespaces) }
        for mark in ["**", "__", "[[", "]]", "`"] { text = text.replacingOccurrences(of: mark, with: "") }
        return text.replacingOccurrences(of: #"\[([^\]]*)\]\([^)]*\)"#, with: "$1", options: .regularExpression)
    }

    /// The words a card shows when a note has no picture: the body without front matter, headings marks or links.
    static func opening(_ text: String, lines: Int = 7) -> (title: String?, body: String) {
        var rows = text.components(separatedBy: "\n")
        if rows.first == "---", let end = rows.dropFirst().firstIndex(of: "---") { rows = Array(rows[(end + 1)...]) }
        rows = rows.map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty && !$0.hasPrefix("![") }
        var title: String?
        if let first = rows.first, first.hasPrefix("#") {
            title = plain(first)
            rows.removeFirst()
        }
        let body = rows.prefix(lines).map(plain).joined(separator: "\n")
        return (title, body)
    }
}

extension Int {
    /// "1 lookup", "3 lookups".
    func counted(_ word: String, _ plural: String? = nil) -> String { "\(formatted()) \(self == 1 ? word : plural ?? word + "s")" }
    var bytesText: String { ByteCountFormatter.string(fromByteCount: Int64(self), countStyle: .file) }
}

extension Date {
    var dayTitle: String {
        let calendar = Calendar.current
        if calendar.isDateInToday(self) { return "Today" }
        if calendar.isDateInYesterday(self) { return "Yesterday" }
        return formatted(.dateTime.weekday(.wide).day().month(.wide))
    }
}

/// A model as a person names it. llama.cpp reports the file it loaded; when that file is one of Ollama's blobs,
/// Ollama's own manifests say which model it is.
enum ModelName {
    private static var known: [String: String] = [:]

    static func display(_ reported: String) -> String {
        if let name = known[reported] { return name }
        var name = (reported as NSString).lastPathComponent
        if name.hasPrefix("sha256-") {
            let digest = "sha256:" + name.dropFirst("sha256-".count)
            let manifests = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".ollama/models/manifests/registry.ollama.ai/library")
            if let models = try? FileManager.default.contentsOfDirectory(atPath: manifests.path) {
                search: for model in models {
                    let folder = manifests.appendingPathComponent(model)
                    for tag in (try? FileManager.default.contentsOfDirectory(atPath: folder.path)) ?? [] {
                        if let text = try? String(contentsOf: folder.appendingPathComponent(tag), encoding: .utf8), text.contains(digest) {
                            name = "\(model):\(tag)"
                            break search
                        }
                    }
                }
            }
            if name.hasPrefix("sha256-") { name = "Model " + name.dropFirst(7).prefix(8) }
        } else if name.hasSuffix(".gguf") {
            name = (name as NSString).deletingPathExtension
        }
        known[reported] = name
        return name
    }
}
