import Foundation

/// Recency and importance, the two ranking signals beside similarity that the design names (objective ii), after the
/// retrieval score of Park et al. (2023): relevance first, then how recent and how important a memory is.
///
/// They only nudge: each adds at most its weight to a candidate's score, as a share of that score, so a file that matches
/// the question better still comes first and these break near-ties. Both weights live in `Budget`, so an evaluation can
/// switch them off and measure what they add.
extension Vault {
    struct Salience: Equatable {
        /// 1 for a file changed today, halving every `recencyHalfLife` days.
        var recency: Double
        /// 0 to 1: how much of the vault leans on this file, and whether a note says it records a decision or rule.
        var importance: Double
    }

    static let recencyHalfLife: Double = 90
    /// Note kinds that record something people rely on (D-56's kinds).
    static let weightyKinds: Set<String> = ["decision", "convention", "rejected", "bug"]

    /// Recency and importance for a set of vault paths, read once per question for the candidates only.
    func salience(of paths: Set<String>, now: Date = Date()) -> [String: Salience] {
        guard !paths.isEmpty else { return [:] }
        // How many files link to each candidate: a note many others point at is one the vault leans on.
        var inbound: [String: Int] = [:]
        let list = Array(paths)
        let marks = Array(repeating: "?", count: list.count).joined(separator: ",")
        if let rows = try? database.rows("SELECT target, COUNT(DISTINCT source) FROM links WHERE target IN (\(marks)) GROUP BY target",
                                         list.map { .text($0) }) {
            for row in rows { if let target = row[0].text, let count = row[1].int { inbound[target] = count } }
        }
        var out: [String: Salience] = [:]
        for path in list {
            var written = modified(path)
            var kindWeight = 0.0
            if path.hasSuffix(".md") || path.hasSuffix(".markdown"), let text = text(of: path) {
                let fields = NoteFile.split(text).fields
                // A note's own date says when its content is from; the file's date may only be when it was copied.
                if let date = fields["date"].flatMap(Self.day) { written = date }
                if let kind = fields["kind"]?.lowercased(), Self.weightyKinds.contains(kind) { kindWeight = 0.5 }
            }
            let age = max(0, now.timeIntervalSince(written ?? now) / 86_400)
            let recency = written == nil ? 0 : pow(0.5, age / Self.recencyHalfLife)
            // Eight files pointing at one is plenty; more adds little.
            let links = min(1, log2(1 + Double(inbound[path] ?? 0)) / 3)
            out[path] = Salience(recency: recency, importance: min(1, 0.5 * links + kindWeight))
        }
        return out
    }

    /// Multiplies each candidate's score by 1 + its weighted recency and importance. Only the best `consider` are looked at,
    /// which is all a question ever reaches.
    func applySalience(to score: inout [Int: Double], fileOf: [Int: (path: String, isNote: Bool)], budget: Budget, consider: Int = 120) {
        guard budget.recencyWeight > 0 || budget.importanceWeight > 0 else { return }
        let top = score.keys.sorted { (score[$0]!, $1) > (score[$1]!, $0) }.prefix(consider)
        let paths = Set(top.compactMap { fileOf[$0]?.path })
        let found = salience(of: paths)
        for id in top {
            guard let path = fileOf[id]?.path, let mark = found[path] else { continue }
            score[id]! *= 1 + budget.recencyWeight * mark.recency + budget.importanceWeight * mark.importance
        }
    }

    private func modified(_ path: String) -> Date? {
        guard let place = locationForSalience(path) else { return nil }
        return (try? FileManager.default.attributesOfItem(atPath: place.path))?[.modificationDate] as? Date
    }

    static func day(_ text: String) -> Date? {
        let format = DateFormatter()
        format.locale = Locale(identifier: "en_US_POSIX")
        format.timeZone = TimeZone(identifier: "UTC")
        format.dateFormat = "yyyy-MM-dd"
        return format.date(from: String(text.trimmingCharacters(in: CharacterSet(charactersIn: " \"'")).prefix(10)))
    }
}
