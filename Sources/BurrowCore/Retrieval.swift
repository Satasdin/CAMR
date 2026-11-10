import Foundation

/// The three ways of giving a model memory that the thesis compares.
public enum Mode: String, CaseIterable, Sendable {
    case none    // the model gets nothing
    case search  // the best matches by words and meaning, ignoring links
    case walk    // the same start, then follow links to what the matches depend on
}

public struct Budget: Sendable {
    /// Every mode gets the same amount of text, so a win cannot come from simply reading more.
    public var characters = 12_000
    public var entryFiles = 4
    public var hops = 2
    public var longestExcerpt = 3_000
    public init() {}
}

public enum Reason: Sendable, Equatable {
    case search
    case link(from: String, kind: LinkKind, via: String?)

    public var label: String {
        switch self {
        case .search: return "search"
        case let .link(from, kind, via):
            return "\(kind.rawValue) link from \(from)" + (via.map { " (\($0))" } ?? "")
        }
    }
}

public struct Excerpt: Sendable, Equatable {
    public let path: String
    public let startLine: Int
    public let endLine: Int
    public let text: String
    public let reason: Reason
    public let isNote: Bool
}

/// How well the vault matched a question, before anything is shown to a model.
public struct Signal: Sendable, Equatable {
    /// Closeness of the nearest piece by meaning, from -1 to 1. Nil when the vault has no vectors.
    public var nearest: Float?
    /// How many pieces share a word with the question.
    public var wordMatches = 0
    public init(nearest: Float? = nil, wordMatches: Int = 0) {
        self.nearest = nearest
        self.wordMatches = wordMatches
    }
}

public struct Retrieved: Sendable {
    public let mode: Mode
    public let excerpts: [Excerpt]
    public let seconds: Double
    public var signal = Signal()
    public var characters: Int { excerpts.reduce(0) { $0 + $1.text.count } }
    public var paths: [String] {
        var seen = Set<String>()
        return excerpts.map(\.path).filter { seen.insert($0).inserted }
    }
}

extension Vault {
    private struct Hit {
        let chunk: Int
        let path: String
        let isNote: Bool
    }

    /// One pass over the word index for a question: every matching piece with its score, best first.
    /// Both the ranking and the walk read from this, so the index is searched once per question.
    private struct WordMatches {
        var ranked: [Int] = []
        /// bm25 scores are negative, and the more negative the better.
        var score: [Int: Double] = [:]
    }

    /// Finds what to show the model. The vault walks; the model only reads the result.
    /// - Parameter scope: a folder to stay inside, such as one linked project. Nothing outside it is read.
    public func retrieve(_ question: String, mode: Mode, budget: Budget = Budget(), embedder: Embedder? = nil, scope: String? = nil) async throws -> Retrieved {
        let started = Date()
        guard mode != .none else { return Retrieved(mode: mode, excerpts: [], seconds: 0) }
        let queryVector = try await questionVector(question, embedder: embedder)
        let shelf = try catalogue()
        let words = try wordMatches(question)
        var signal = Signal(wordMatches: words.ranked.count)
        let hits = try fused(question, vector: queryVector, limit: 60, scope: scope, shelf: shelf, words: words, signal: &signal)
        let excerpts = mode == .search ? try searchOnly(hits, budget)
            : try walking(question, hits, budget, scope: scope, shelf: shelf, words: words)
        return Retrieved(mode: mode, excerpts: excerpts, seconds: Date().timeIntervalSince(started), signal: signal)
    }

    // MARK: Search

    private func wordMatches(_ question: String) throws -> WordMatches {
        guard let query = Words.query(from: question) else { return WordMatches() }
        var found = WordMatches()
        for row in try database.rows("""
            SELECT rowid, bm25(chunks_fts, 3.0, 1.0) AS score FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY score
            """, [.text(query)]) {
            guard let id = row[0].int, let score = row[1].real else { continue }
            found.ranked.append(id)
            found.score[id] = score
        }
        return found
    }

    private func matches(_ search: String, limit: Int) throws -> [Int] {
        try database.rows("""
            SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts, 3.0, 1.0) LIMIT ?
            """, [.text(search), .int(Int64(limit))]).compactMap { $0[0].int }
    }

    /// Chunks holding a compound name the question typed exactly. Where the name is defined comes before where it is used.
    private func exactRanks(_ question: String, limit: Int) throws -> [Int] {
        guard let query = Words.exactQuery(from: question) else { return [] }
        let names = Set(Words.identifiers(in: question))
        var defining: [Int] = []
        var mentioning: [Int] = []
        for id in try matches(query, limit: 60) {
            let body = try database.rows("SELECT body FROM chunks WHERE id = ?", [.int(Int64(id))]).first?[0].text ?? ""
            if !LinkFinder.definedSymbols(in: body).isDisjoint(with: names) { defining.append(id) } else { mentioning.append(id) }
        }
        return Array((defining + mentioning).prefix(limit))
    }

    /// Merges the word and meaning rankings. Reciprocal rank fusion needs no tuning between two unlike scores.
    private func fused(_ question: String, vector: [Float]?, limit: Int, scope: String?, shelf: Catalogue, words: WordMatches,
                       signal: inout Signal) throws -> [Hit] {
        var score: [Int: Double] = [:]
        // A narrow folder can sit far down the whole vault's ranking, so look further before narrowing.
        let reach = scope == nil ? limit : max(limit, 4000)
        var byMeaning: [Int] = []
        if let vector {
            let index = try vectorIndex()
            byMeaning = index.nearest(to: vector, limit: reach)
            // Skills are in the index too, but how close one is says nothing about what the vault knows.
            if let first = byMeaning.first(where: { id in shelf.fileOf[id].map { !Skills.holds($0.path) && Self.inside(scope, $0.path) } ?? false }) {
                signal.nearest = index.similarity(of: first, to: vector)
            }
        }
        for ranking in [Array(words.ranked.prefix(reach)), byMeaning] {
            for (rank, id) in ranking.enumerated() { score[id, default: 0] += 1.0 / Double(60 + rank + 1) }
        }
        let asked = Asked(question)
        let fileOf = shelf.fileOf
        for id in Array(score.keys) { score[id]! *= asked.weight(of: fileOf[id]?.path ?? "") }

        // Someone who types an exact name means that name, so those chunks go ahead of the merged ranking.
        var seen = Set<Int>()
        let merged = score.keys.sorted { (score[$0]!, $1) > (score[$1]!, $0) }
        let front = scope == nil ? 6 : 60
        // The file or folder a question named may have missed both rankings, so its chunks are looked up directly.
        let named = asked.names.isEmpty ? [] : fileOf.keys.filter { asked.names(fileOf[$0]!.path) && Self.inside(scope, fileOf[$0]!.path) }
            .sorted { (score[$0] ?? 0, $1) > (score[$1] ?? 0, $0) }
        let ordered = (try exactRanks(question, limit: front) + named.prefix(front) + merged).filter { seen.insert($0).inserted }
        var hits: [Hit] = []
        for id in ordered where hits.count < limit {
            // A skill is a way of working, not a fact about the vault. It reaches the model by another road.
            guard let file = fileOf[id], Self.inside(scope, file.path), !Skills.holds(file.path) else { continue }
            hits.append(Hit(chunk: id, path: file.path, isNote: file.isNote))
        }
        return hits
    }

    static func inside(_ scope: String?, _ path: String) -> Bool {
        guard let scope, !scope.isEmpty else { return true }
        return path == scope || path.hasPrefix(scope + "/")
    }

    private func excerpt(chunk: Int, reason: Reason, budget: Budget) throws -> Excerpt? {
        guard let row = try database.rows("""
            SELECT f.path, c.start_line, c.end_line, c.body, f.is_note FROM chunks c JOIN files f ON f.id = c.file_id WHERE c.id = ?
            """, [.int(Int64(chunk))]).first else { return nil }
        return Excerpt(path: row[0].text!, startLine: row[1].int!, endLine: row[2].int!,
                       text: String(row[3].text!.prefix(budget.longestExcerpt)), reason: reason, isNote: row[4].int == 1)
    }

    private func searchOnly(_ hits: [Hit], _ budget: Budget) throws -> [Excerpt] {
        var out: [Excerpt] = []
        var used = 0
        for hit in hits {
            guard let piece = try excerpt(chunk: hit.chunk, reason: .search, budget: budget) else { continue }
            if used + piece.text.count > budget.characters { break }
            out.append(piece)
            used += piece.text.count
        }
        return out
    }

    // MARK: Walking

    private func walking(_ question: String, _ hits: [Hit], _ budget: Budget, scope: String?, shelf: Catalogue, words: WordMatches) throws -> [Excerpt] {
        var taken: [Excerpt] = []
        var takenChunks = Set<Int>()
        var used = 0
        var entries: [String] = []
        // Nothing useful is shorter than this, so once less is left the walk stops looking.
        let smallest = 200

        func take(_ chunk: Int, _ reason: Reason) throws -> Bool {
            guard !takenChunks.contains(chunk), let piece = try excerpt(chunk: chunk, reason: reason, budget: budget),
                  used + piece.text.count <= budget.characters else { return false }
            taken.append(piece)
            takenChunks.insert(chunk)
            used += piece.text.count
            return true
        }

        // Start from the best chunk of the best few files, spending at most 60% of the budget there.
        for hit in hits where entries.count < budget.entryFiles && !entries.contains(hit.path) {
            if used > budget.characters * 6 / 10 { break }
            if try take(hit.chunk, .search) { entries.append(hit.path) }
        }

        // Then spread out. Candidates are ranked: a note about a file first, then what the question's words support.
        var visited = Set(entries)
        var frontier = entries
        let wordMatches = wordScores(words, shelf: shelf)
        let asked = Asked(question)
        for hop in 1...max(1, budget.hops) where !frontier.isEmpty && budget.characters - used >= smallest {
            var candidates: [(score: Double, path: String, neighbour: Vault.Neighbour, from: String)] = []
            for source in frontier {
                for neighbour in try neighbours(of: source) where !visited.contains(neighbour.path)
                    && Self.inside(scope, neighbour.path) && !Skills.holds(neighbour.path) {
                    var score = (wordMatches[neighbour.path] ?? 0) / Double(hop)
                    switch neighbour.kind {
                    case .about: score += 3
                    case .imports: score += neighbour.forward ? 1 : 0.5
                    case .uses: score += neighbour.forward ? 0.75 : 0.25
                    }
                    candidates.append((score * asked.weight(of: neighbour.path), neighbour.path, neighbour, source))
                }
            }
            candidates.sort { ($0.score, $1.path, $1.from) > ($1.score, $0.path, $0.from) }
            var next: [String] = []
            for candidate in candidates where !visited.contains(candidate.path) {
                visited.insert(candidate.path)
                guard let chunk = try bestChunk(of: candidate.path, via: candidate.neighbour.via, shelf: shelf, words: words) else { continue }
                let reason = Reason.link(from: candidate.from, kind: candidate.neighbour.kind, via: candidate.neighbour.via)
                if try take(chunk, reason) { next.append(candidate.path) }
                if budget.characters - used < smallest { break }
            }
            frontier = next
        }

        // Links ran out before the budget did: use the rest on further search results, so no mode reads less.
        for hit in hits where budget.characters - used >= smallest { _ = try take(hit.chunk, .search) }
        return taken
    }

    /// How strongly each file matches the question's words, scaled so the best file scores 1.
    private func wordScores(_ words: WordMatches, shelf: Catalogue) -> [String: Double] {
        var strongest: [String: Double] = [:]
        for (id, score) in words.score {
            guard let path = shelf.fileOf[id]?.path else { continue }
            strongest[path] = min(strongest[path] ?? 0, score)
        }
        guard let best = strongest.values.min(), best < 0 else { return [:] }
        return strongest.mapValues { $0 / best }
    }

    /// The part of a linked file worth opening: where the linking symbol is defined, or else the best word match.
    private func bestChunk(of path: String, via: String?, shelf: Catalogue, words: WordMatches) throws -> Int? {
        guard let chunks = shelf.chunksOf[path], !chunks.isEmpty else { return nil }
        if let via {
            let bodies = try database.rows("""
                SELECT c.id, c.body FROM chunks c JOIN files f ON f.id = c.file_id WHERE f.path = ? ORDER BY c.start_line
                """, [.text(path)])
            let found = bodies.first { row in
                row[1].text.map { LinkFinder.definedSymbols(in: $0).contains(via) } ?? false
            } ?? bodies.first { $0[1].text?.contains(via) ?? false }
            if let found { return found[0].int }
        }
        let matched = chunks.filter { words.score[$0] != nil }
        if let best = matched.min(by: { (words.score[$0]!, $0) < (words.score[$1]!, $1) }) { return best }
        return chunks.first
    }
}
