@testable import BurrowCore
import XCTest

/// Recency and importance break near-ties in the ranking (objective ii); relevance still comes first.
final class SalienceTests: XCTestCase {
    private var base: URL!

    override func setUp() async throws {
        base = FileManager.default.temporaryDirectory.appendingPathComponent("salience-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
    }

    override func tearDown() async throws { try? FileManager.default.removeItem(at: base) }

    private func write(_ path: String, _ text: String) throws {
        let url = base.appendingPathComponent(path)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try text.write(to: url, atomically: true, encoding: .utf8)
    }

    private func firstPath(_ question: String, _ budget: Budget = Budget()) async throws -> String? {
        let vault = try Vault(project: base, everything: true)
        _ = try await vault.refresh(embedder: nil)
        return try await vault.retrieve(question, mode: .search, budget: budget).excerpts.first?.path
    }

    func testTheNewerOfTwoEqualNotesComesFirst() async throws {
        try write("old.md", "---\ndate: 2024-01-10\n---\nThe refund window for orders is thirty days.\n")
        try write("new.md", "---\ndate: 2026-11-01\n---\nThe refund window for orders is thirty days.\n")
        let first = try await firstPath("refund window for orders")
        XCTAssertEqual(first, "new.md")
        var off = Budget()
        off.recencyWeight = 0
        off.importanceWeight = 0
        // Without the nudge the two tie, and the order falls back to the index's own.
        let tied = try await firstPath("refund window for orders", off)
        XCTAssertNotNil(tied)
    }

    func testAFileOthersLeanOnComesFirst() async throws {
        try write("a.md", "The courier hands parcels over at the gate.\n")
        try write("b.md", "The courier hands parcels over at the gate.\n")
        for name in ["one", "two", "three", "four"] { try write("\(name).md", "See [[b]] for how parcels are handed over.\n") }
        let first = try await firstPath("courier hands parcels over at the gate")
        XCTAssertEqual(first, "b.md")
    }

    func testRelevanceStillBeatsTheNudges() async throws {
        try write("exact.md", "---\ndate: 2020-01-01\n---\nThe Data Commissioner's term of office is six years, not renewable.\n")
        try write("loose.md", "---\ndate: 2026-11-01\nkind: decision\n---\nWe decided to read about the commissioner later.\n")
        for name in ["one", "two", "three"] { try write("\(name).md", "See [[loose]].\n") }
        let first = try await firstPath("Data Commissioner term of office six years renewable")
        XCTAssertEqual(first, "exact.md")
    }

    func testSalienceScores() throws {
        try write("decision.md", "---\nkind: decision\ndate: 2026-11-12\n---\nKeep it.\n")
        let vault = try Vault(project: base, everything: true)
        let now = Vault.day("2026-11-12")!
        let marks = vault.salience(of: ["decision.md"], now: now)
        XCTAssertEqual(marks["decision.md"]?.recency ?? 0, 1, accuracy: 0.001)
        XCTAssertEqual(marks["decision.md"]?.importance ?? 0, 0.5, accuracy: 0.001)
        let later = vault.salience(of: ["decision.md"], now: now.addingTimeInterval(90 * 86_400))
        XCTAssertEqual(later["decision.md"]?.recency ?? 0, 0.5, accuracy: 0.001)
    }
}
