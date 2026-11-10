import Foundation

/// A skill is a Markdown file that says how to do one kind of task well. The engine hands the right one to the
/// model with the question, so a small model starts with a method instead of working one out.
public struct Skill: Sendable, Equatable {
    public let name: String
    /// One line saying when the skill applies. This is what a question is matched against.
    public let when: String
    public let body: String
    public let path: String
    /// True when the method only makes sense with excerpts from the vault in front of the model.
    public var needsVault = false
    /// "documents" or "code" when this is the method to fall back on for that kind of material.
    public var fallbackFor: String?

    /// Reads a skill file. Front matter may give `when:`; without it the first paragraph is used.
    static func parse(_ text: String, path: String) -> Skill? {
        var lines = text.components(separatedBy: "\n")
        var when = ""
        var needsVault = false
        var fallbackFor: String?
        if lines.first?.trimmingCharacters(in: .whitespaces) == "---",
           let end = lines.dropFirst().firstIndex(where: { $0.trimmingCharacters(in: .whitespaces) == "---" }) {
            for line in lines[1..<end] {
                let lowered = line.lowercased()
                func value(_ key: String) -> String? {
                    lowered.hasPrefix(key) ? String(line.dropFirst(key.count)).trimmingCharacters(in: .whitespaces) : nil
                }
                if let found = value("when:") { when = found }
                if let found = value("needs:") { needsVault = found.lowercased() == "vault" }
                if let found = value("fallback:") { fallbackFor = found.lowercased() }
            }
            lines = Array(lines[(end + 1)...])
        }
        let body = lines.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty else { return nil }
        let heading = lines.first { $0.hasPrefix("# ") }.map { String($0.dropFirst(2)).trimmingCharacters(in: .whitespaces) }
        let name = heading ?? ((path as NSString).lastPathComponent as NSString).deletingPathExtension
        if when.isEmpty {
            when = lines.first { !$0.trimmingCharacters(in: .whitespaces).isEmpty && !$0.hasPrefix("#") } ?? name
        }
        return Skill(name: name, when: when, body: String(body.prefix(Skills.longest)), path: path, needsVault: needsVault, fallbackFor: fallbackFor)
    }
}

public enum Skills {
    public static let folder = "Skills"
    /// A skill is a method, not a manual. Longer than this and it crowds out what the vault has to say.
    static let longest = 1_600
    static let instruction = "Instruct: Given a request, find the description of the kind of task it is\nQuery: "

    /// True for a file kept as a skill, in a vault or in a linked folder.
    static func holds(_ path: String) -> Bool {
        path.split(separator: "/").dropLast().contains { $0 == folder }
    }
}

extension Vault {
    public var skillsFolder: URL { everything ? root.appendingPathComponent(Skills.folder) : store.appendingPathComponent("skills") }

    /// Every skill this vault holds, in name order.
    public func skills() -> [Skill] {
        let files = (try? FileManager.default.contentsOfDirectory(at: skillsFolder, includingPropertiesForKeys: nil)) ?? []
        return files.filter { $0.pathExtension == "md" }.sorted { $0.lastPathComponent < $1.lastPathComponent }.compactMap { file in
            guard let text = try? String(contentsOf: file, encoding: .utf8) else { return nil }
            return Skill.parse(text, path: (everything ? Skills.folder : "skills") + "/" + file.lastPathComponent)
        }
    }

    /// Writes the starter skills that are not already there. A skill someone has edited is never overwritten.
    @discardableResult
    public func installStarterSkills() throws -> [String] {
        try FileManager.default.createDirectory(at: skillsFolder, withIntermediateDirectories: true)
        var written: [String] = []
        for (file, text) in StarterSkills.all.sorted(by: { $0.key < $1.key }) {
            let url = skillsFolder.appendingPathComponent(file)
            guard !FileManager.default.fileExists(atPath: url.path) else { continue }
            try text.write(to: url, atomically: true, encoding: .utf8)
            written.append(file)
        }
        return written
    }

    /// Every skill with how close its "when" line is to the question, closest first.
    /// The question is embedded as a request to be classified, which is a different thing from a search for its answer.
    func skillRanking(for question: String, embedder: Embedder?) async throws -> [(skill: Skill, closeness: Float)] {
        let known = skills()
        guard !known.isEmpty else { return [] }
        var ranked: [(skill: Skill, closeness: Float)] = []
        if let embedder {
            let asked = Skills.instruction + question
            let vector = try await questionVector(asked, embedder: embedder) ?? []
            let vectors = try await skillVectors(known, embedder: embedder)
            ranked = zip(known, vectors).map { ($0, Self.cosine(vector, $1)) }
        } else {
            // Without an embedding model, a skill fits by the share of its "when" words the question uses.
            let asked = Set(Words.identifiers(in: question).map { $0.lowercased() })
            for skill in known {
                let wanted = Set(Words.identifiers(in: skill.when).map { $0.lowercased() }.filter { $0.count > 3 })
                ranked.append((skill, wanted.isEmpty ? 0 : Float(wanted.intersection(asked).count) / Float(wanted.count)))
            }
        }
        return ranked.sorted { ($0.closeness, $1.skill.name) > ($1.closeness, $0.skill.name) }
    }

    private var skillVectorFile: URL { store.appendingPathComponent("skills.json") }

    /// Vectors for the skills' "when" lines. They are kept on disk, so a question never waits for skills to be embedded again.
    private func skillVectors(_ known: [Skill], embedder: Embedder) async throws -> [[Float]] {
        let texts = known.map { "\($0.name). \($0.when)" }
        database.locked {
            if skillVectorCache.isEmpty, let data = try? Data(contentsOf: skillVectorFile),
               let saved = try? JSONDecoder().decode([String: [Float]].self, from: data) { skillVectorCache = saved }
        }
        let missing = database.locked { texts.filter { skillVectorCache[$0] == nil } }
        if !missing.isEmpty {
            let fresh = try await embedder.embed(missing)
            database.locked {
                for (text, vector) in zip(missing, fresh) { skillVectorCache[text] = vector }
                let current = skillVectorCache.filter { texts.contains($0.key) }
                if let data = try? JSONEncoder().encode(current) { try? data.write(to: skillVectorFile, options: .atomic) }
            }
        }
        return database.locked { texts.map { skillVectorCache[$0] ?? [] } }
    }

    static func cosine(_ a: [Float], _ b: [Float]) -> Float {
        guard a.count == b.count, !a.isEmpty else { return -1 }
        var dot: Float = 0, lengthA: Float = 0, lengthB: Float = 0
        for index in a.indices {
            dot += a[index] * b[index]
            lengthA += a[index] * a[index]
            lengthB += b[index] * b[index]
        }
        guard lengthA > 0, lengthB > 0 else { return -1 }
        return dot / (lengthA.squareRoot() * lengthB.squareRoot())
    }
}
