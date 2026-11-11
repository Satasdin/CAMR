import Foundation

/// One file or note as the graph and the file tree see it.
public struct MapFile: Sendable, Hashable {
    public let path: String
    public let isNote: Bool
    public let cluster: String
    public let chunks: Int
}

public struct MapLink: Sendable, Hashable {
    public let from: String
    public let to: String
    public let kind: LinkKind
}

public struct ProjectMap: Sendable {
    public let files: [MapFile]
    public let links: [MapLink]
    public init(files: [MapFile], links: [MapLink]) {
        self.files = files
        self.links = links
    }
}

public struct NoteSummary: Sendable, Hashable, Identifiable {
    public var id: String { path }
    public let path: String
    public let title: String
    public let kind: NoteKind
    public let date: String
}

public struct NoteProblem: Error, CustomStringConvertible {
    public let description: String
    public init(description: String) { self.description = description }
}

/// A folder from somewhere else on this Mac, read as part of the vault. It changes only when someone accepts a proposed change.
public struct LinkedFolder: Sendable, Hashable, Codable, Identifiable {
    public var id: String { name }
    public let name: String
    public let path: String
    public var url: URL { URL(fileURLWithPath: path) }
    public init(name: String, path: String) {
        self.name = name
        self.path = path
    }
}

public struct FoundLine: Sendable, Hashable, Identifiable {
    public var id: String { "\(path):\(line)" }
    public let path: String
    public let line: Int
    public let text: String

    public init(path: String, line: Int, text: String) {
        self.path = path
        self.line = line
        self.text = text
    }
}

/// What the app, the terminal and the MCP server need to show a vault and keep its notes.
extension Vault {
    public func projectMap() throws -> ProjectMap {
        let files = try database.rows("""
            SELECT f.path, f.is_note, f.cluster, count(c.id) FROM files f LEFT JOIN chunks c ON c.file_id = f.id
            GROUP BY f.id ORDER BY f.path
            """).map { MapFile(path: $0[0].text!, isNote: $0[1].int == 1, cluster: $0[2].text!, chunks: $0[3].int ?? 0) }
        let links = try database.rows("SELECT source, target, kind FROM links ORDER BY source, target, kind").compactMap { row -> MapLink? in
            guard let kind = LinkKind(rawValue: row[2].text!) else { return nil }
            return MapLink(from: row[0].text!, to: row[1].text!, kind: kind)
        }
        return ProjectMap(files: files, links: links)
    }

    // MARK: Linked folders

    private var linkedFile: URL { store.appendingPathComponent("folders.json") }

    public func linkedFolders() -> [LinkedFolder] {
        guard let data = try? Data(contentsOf: linkedFile) else { return [] }
        return (try? JSONDecoder().decode([LinkedFolder].self, from: data)) ?? []
    }

    /// Adds a folder to the vault under a name of its own. Burrow reads it and never changes it.
    @discardableResult
    public func linkFolder(_ url: URL) throws -> LinkedFolder {
        var folders = linkedFolders()
        let path = url.standardizedFileURL.path
        if let existing = folders.first(where: { $0.path == path }) { return existing }
        guard path != root.path, !path.hasPrefix(root.path + "/") else { throw NoteProblem(description: "That folder is already inside this vault.") }
        let base = url.lastPathComponent
        var name = base
        var attempt = 2
        let taken = Set(folders.map(\.name))
        while taken.contains(name) || FileManager.default.fileExists(atPath: root.appendingPathComponent(name).path) {
            name = "\(base) \(attempt)"
            attempt += 1
        }
        let folder = LinkedFolder(name: name, path: path)
        folders.append(folder)
        try JSONEncoder().encode(folders).write(to: linkedFile, options: .atomic)
        return folder
    }

    public func unlinkFolder(_ name: String) throws {
        try JSONEncoder().encode(linkedFolders().filter { $0.name != name }).write(to: linkedFile, options: .atomic)
    }

    // MARK: Reading

    /// Where a vault path really lives. Nil for anything that would leave the vault or a linked folder.
    private func location(of path: String) -> (url: URL, root: URL, relative: String, linked: Bool)? {
        guard !path.isEmpty, !path.hasPrefix("/"), !path.split(separator: "/", omittingEmptySubsequences: false).contains("..") else { return nil }
        if let first = path.split(separator: "/").first, let folder = linkedFolders().first(where: { $0.name == first }) {
            let relative = String(path.dropFirst(first.count + 1))
            return (folder.url.appendingPathComponent(relative), folder.url, relative, true)
        }
        return (root.appendingPathComponent(path), root, path, false)
    }

    /// The text of anything in the vault.
    public func text(of path: String) -> String? {
        if !everything, let note = try? noteURL(path) { return try? String(contentsOf: note, encoding: .utf8) }
        guard let place = location(of: path) else { return nil }
        return Scanner.read(place.relative, in: place.root)?.text
    }

    public func isLinked(_ path: String) -> Bool { location(of: path)?.linked ?? false }

    /// Whether Burrow may change this file. Only notes in the vault itself can be edited.
    public func canEdit(_ path: String) -> Bool {
        if !everything { return (try? noteURL(path)) != nil }
        return !isLinked(path) && Vault.isMarkdown(path)
    }

    public func readLines(_ path: String, from start: Int = 1, count: Int = 200) -> String? {
        guard let text = text(of: path) else { return nil }
        let lines = text.components(separatedBy: "\n")
        let first = max(1, start)
        guard first <= lines.count else { return "" }
        return lines[(first - 1)..<min(lines.count, first - 1 + max(1, count))].enumerated()
            .map { "\(first + $0.offset): \($0.element)" }.joined(separator: "\n")
    }

    /// Every folder in the vault, including empty ones, and the linked folders' names.
    public func folders() -> [String] {
        var out = Set(linkedFolders().map(\.name))
        if everything, let walker = FileManager.default.enumerator(at: root, includingPropertiesForKeys: [.isDirectoryKey], options: [.skipsHiddenFiles]) {
            for case let url as URL in walker where (try? url.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory == true {
                if Scanner.skippedFolders.contains(url.lastPathComponent) { walker.skipDescendants(); continue }
                out.insert(String(url.standardizedFileURL.path.dropFirst(root.path.count + 1)))
            }
        }
        return out.sorted()
    }

    /// Finds lines by their words, for the search panel. Every word has to be there, and the last may be half typed.
    public func searchLines(_ query: String, scope: String? = nil, limit: Int = 200) throws -> [FoundLine] {
        let words = query.split(whereSeparator: \.isWhitespace).map(String.init)
        guard let last = words.last else { return [] }
        let terms = words.dropLast().map { "\"\($0.replacingOccurrences(of: "\"", with: ""))\"" } + ["\"\(last.replacingOccurrences(of: "\"", with: ""))\"*"]
        let rows = try database.rows("""
            SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts, 3.0, 1.0) LIMIT ?
            """, [.text(terms.joined(separator: " ")), .int(Int64(limit * 4))])
        let lowered = words.map { $0.lowercased() }
        var out: [FoundLine] = []
        for row in rows where out.count < limit {
            guard let id = row[0].int, let hit = try database.rows("""
                SELECT f.path, c.start_line, c.body FROM chunks c JOIN files f ON f.id = c.file_id WHERE c.id = ?
                """, [.int(Int64(id))]).first, Self.inside(scope, hit[0].text!) else { continue }
            let lines = hit[2].text!.components(separatedBy: "\n")
            let place = lines.firstIndex { line in lowered.contains { line.lowercased().contains($0) } } ?? 0
            out.append(FoundLine(path: hit[0].text!, line: hit[1].int! + place, text: lines[place].trimmingCharacters(in: .whitespaces)))
        }
        return out
    }

    /// Each place another note mentions this one, with the line it's on.
    public func mentions(of path: String) throws -> [FoundLine] {
        let name = ((path as NSString).lastPathComponent as NSString).deletingPathExtension
        var out: [FoundLine] = []
        for neighbour in try neighbours(of: path) where neighbour.kind == .about && !neighbour.forward {
            guard let text = text(of: neighbour.path) else { continue }
            let lines = text.components(separatedBy: "\n")
            let withoutEnding = (path as NSString).deletingPathExtension
            let exact = lines.firstIndex { $0.contains("[[\(name)") || $0.contains("[[\(withoutEnding)") || $0.contains(path) || (neighbour.via.map($0.contains) ?? false) }
            // Failing that, the first line of the note itself, never its header.
            let bodyStart = NoteFile.split(text).header.components(separatedBy: "\n").count - 1
            let place = exact ?? lines.indices.first { $0 >= bodyStart && !lines[$0].trimmingCharacters(in: .whitespaces).isEmpty } ?? 0
            out.append(FoundLine(path: neighbour.path, line: place + 1, text: lines[place].trimmingCharacters(in: .whitespaces)))
        }
        return out
    }

    /// All tags in the notes, with the notes that use each.
    public func tags() throws -> [String: [String]] {
        let pattern = try NSRegularExpression(pattern: #"(?:^|\s)#([A-Za-z][\w/\-]*)"#, options: [.anchorsMatchLines])
        var out: [String: Set<String>] = [:]
        for row in try database.rows("SELECT f.path, c.body FROM chunks c JOIN files f ON f.id = c.file_id WHERE f.is_note = 1") {
            let body = row[1].text!
            for match in pattern.matches(in: body, range: NSRange(body.startIndex..., in: body)) {
                if let found = Range(match.range(at: 1), in: body) { out[String(body[found]), default: []].insert(row[0].text!) }
            }
        }
        return out.mapValues { $0.sorted() }
    }

    // MARK: Notes

    public func notes() -> [NoteSummary] {
        let found: [URL]
        if everything {
            found = ((try? database.rows("SELECT path FROM files WHERE is_note = 1 ORDER BY path")) ?? []).map { root.appendingPathComponent($0[0].text!) }
        } else {
            found = ((try? FileManager.default.contentsOfDirectory(at: notesFolder, includingPropertiesForKeys: nil)) ?? []).filter { $0.pathExtension == "md" }
        }
        return found.compactMap { url -> NoteSummary? in
            guard let text = try? String(contentsOf: url, encoding: .utf8) else { return nil }
            let parts = NoteFile.split(text)
            let kind = NoteKind(rawValue: parts.fields["kind"] ?? "") ?? .note
            let name = url.deletingPathExtension().lastPathComponent
            return NoteSummary(path: notePath(url), title: everything ? name : NoteFile.title(of: parts.body, fallback: name), kind: kind, date: parts.fields["date"] ?? "")
        }.sorted { ($0.date, $1.path) > ($1.date, $0.path) }
    }

    /// Replaces a note's words and keeps its header.
    public func saveNote(_ path: String, body: String) throws {
        let url = try noteURL(path)
        let old = try String(contentsOf: url, encoding: .utf8)
        try (NoteFile.split(old).header + body.trimmingCharacters(in: .whitespacesAndNewlines) + "\n").write(to: url, atomically: true, encoding: .utf8)
    }

    /// Writes a note exactly as typed, header and all.
    public func writeNote(_ path: String, text: String) throws {
        try text.write(to: try noteURL(path), atomically: true, encoding: .utf8)
    }

    /// Makes an empty note. A taken name gets a number.
    @discardableResult
    public func createNote(named name: String, in folder: String = "", text: String = "") throws -> String {
        guard everything else { throw NoteProblem(description: "New notes by name need a vault.") }
        let clean = Self.safeName(name)
        guard !clean.isEmpty else { throw NoteProblem(description: "A note needs a name.") }
        let base = folder.isEmpty ? root : try editableFolder(folder)
        try FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        var target = base.appendingPathComponent(clean + ".md")
        var attempt = 2
        while FileManager.default.fileExists(atPath: target.path) {
            target = base.appendingPathComponent("\(clean) \(attempt).md")
            attempt += 1
        }
        try text.write(to: target, atomically: true, encoding: .utf8)
        return notePath(target)
    }

    @discardableResult
    public func createFolder(named name: String, in folder: String = "") throws -> String {
        let clean = Self.safeName(name)
        guard !clean.isEmpty else { throw NoteProblem(description: "A folder needs a name.") }
        let target = (folder.isEmpty ? root : try editableFolder(folder)).appendingPathComponent(clean)
        guard !FileManager.default.fileExists(atPath: target.path) else { throw NoteProblem(description: "There is already a folder called \(clean).") }
        try FileManager.default.createDirectory(at: target, withIntermediateDirectories: true)
        return notePath(target)
    }

    @discardableResult
    public func renameNote(_ path: String, to name: String) throws -> String {
        let source = try noteURL(path)
        let clean = Self.safeName(name)
        guard !clean.isEmpty else { throw NoteProblem(description: "A note needs a name.") }
        let target = source.deletingLastPathComponent().appendingPathComponent(clean + ".md")
        guard !FileManager.default.fileExists(atPath: target.path) else { throw NoteProblem(description: "There is already a note called \(clean).") }
        try FileManager.default.moveItem(at: source, to: target)
        return notePath(target)
    }

    /// Renames a note or a folder in place.
    @discardableResult
    public func rename(_ path: String, to name: String) throws -> String {
        if Vault.isMarkdown(path) { return try renameNote(path, to: name) }
        guard let place = location(of: path), !place.linked else { throw NoteProblem(description: "Only things inside the vault can be renamed.") }
        let clean = Self.safeName(name)
        guard !clean.isEmpty else { throw NoteProblem(description: "A name can't be empty.") }
        let target = place.url.deletingLastPathComponent().appendingPathComponent(clean)
        guard !FileManager.default.fileExists(atPath: target.path) else { throw NoteProblem(description: "Something called \(clean) is already there.") }
        try FileManager.default.moveItem(at: place.url, to: target)
        return notePath(target)
    }

    /// Writes a proposed change someone accepted, only if the file is still what the change was made from.
    public func applyChange(_ path: String, expecting old: String, with new: String) throws {
        guard let place = location(of: path) else { throw NoteProblem(description: "\(path) is outside this vault.") }
        guard text(of: path) == old else { throw NoteProblem(description: "\((path as NSString).lastPathComponent) has changed since this was proposed, so it was left alone.") }
        try new.write(to: place.url, atomically: true, encoding: .utf8)
    }

    /// Moves a note or a folder into another folder of the vault. An empty folder name means the top of the vault.
    @discardableResult
    public func move(_ path: String, to folder: String) throws -> String {
        guard everything, let place = location(of: path), !place.linked else { throw NoteProblem(description: "Only things inside the vault can be moved.") }
        guard folder != path, !folder.hasPrefix(path + "/") else { throw NoteProblem(description: "A folder can't go inside itself.") }
        let base = folder.isEmpty ? root : try editableFolder(folder)
        let target = base.appendingPathComponent((path as NSString).lastPathComponent)
        guard !FileManager.default.fileExists(atPath: target.path) else { throw NoteProblem(description: "Something with that name is already there.") }
        try FileManager.default.moveItem(at: place.url, to: target)
        return notePath(target)
    }

    /// Moves a note or a folder to the Trash, so deleting one can be undone from Finder.
    public func trash(_ path: String) throws {
        if !everything { return try FileManager.default.trashItem(at: try noteURL(path), resultingItemURL: nil) }
        guard let place = location(of: path), !place.linked else { throw NoteProblem(description: "Burrow doesn't delete anything in a linked folder.") }
        try FileManager.default.trashItem(at: place.url, resultingItemURL: nil)
    }

    public func trashNote(_ path: String) throws { try trash(path) }

    private func editableFolder(_ folder: String) throws -> URL {
        guard let place = location(of: folder), !place.linked else { throw NoteProblem(description: "\(folder) can't be written to.") }
        return place.url
    }

    private static func safeName(_ name: String) -> String {
        name.components(separatedBy: CharacterSet(charactersIn: "/:\\\n\r\t\0")).joined(separator: " ")
            .trimmingCharacters(in: CharacterSet.whitespaces.union(CharacterSet(charactersIn: ".")))
    }

    private func noteURL(_ path: String) throws -> URL {
        if everything {
            guard let place = location(of: path), !place.linked, Vault.isMarkdown(path) else { throw NoteProblem(description: "\(path) is not a note in this vault.") }
            return place.url
        }
        let name = String(path.dropFirst("notes/".count))
        guard path.hasPrefix("notes/"), name.hasSuffix(".md"), !name.contains("/"), !name.hasPrefix(".") else {
            throw NoteProblem(description: "\(path) is not a note.")
        }
        return notesFolder.appendingPathComponent(name)
    }
}

/// The small header at the top of a note, and the words after it.
public enum NoteFile {
    public static func split(_ text: String) -> (header: String, fields: [String: String], body: String) {
        guard text.hasPrefix("---\n"), let end = text.range(of: "\n---\n", range: text.index(text.startIndex, offsetBy: 3)..<text.endIndex) else {
            return ("", [:], text)
        }
        var fields: [String: String] = [:]
        for line in text[text.index(text.startIndex, offsetBy: 4)..<end.lowerBound].split(separator: "\n") {
            guard let colon = line.firstIndex(of: ":") else { continue }
            fields[line[..<colon].trimmingCharacters(in: .whitespaces)] = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
        }
        let body = String(text[end.upperBound...]).trimmingCharacters(in: .whitespacesAndNewlines)
        return (String(text[..<end.upperBound]) + "\n", fields, body)
    }

    public static func title(of body: String, fallback: String) -> String {
        guard let first = body.split(separator: "\n").first(where: { !$0.trimmingCharacters(in: .whitespaces).isEmpty }) else { return fallback }
        let line = first.drop { $0 == "#" || $0 == " " }
        return line.count > 80 ? String(line.prefix(79)) + "…" : String(line)
    }
}
