@testable import BurrowCore
import XCTest

final class SearchStandingTests: XCTestCase {
    private var top: URL!

    override func setUpWithError() throws {
        top = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let about = "the courier retries a failed delivery after a timeout and records the attempt"
        for (path, text) in [
            "src/courier.py": "def deliver(parcel):\n    # \(about)\n    return parcel\n",
            "tests/test_courier.py": "def test_deliver():\n    # \(about) \(about)\n    assert True\n",
            "results/run-07/summary.txt": "\(about) \(about) \(about)\nscore 4 of 9\n",
            "results/run-08/summary.txt": "nothing in common here\nscore 7 of 9\n",
        ] {
            let url = top.appendingPathComponent(path)
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try text.write(to: url, atomically: true, encoding: .utf8)
        }
    }

    override func tearDownWithError() throws { try? FileManager.default.removeItem(at: top) }

    private func firstFile(_ question: String) async throws -> String? {
        let vault = try Vault(project: top, store: top.appendingPathComponent("store"))
        try await vault.refresh()
        return try await vault.retrieve(question, mode: .search).paths.first
    }

    func testCodeComesBeforeItsTestsAndPastRuns() async throws {
        let first = try await firstFile("How does the courier retry a failed delivery?")
        XCTAssertEqual(first, "src/courier.py")
    }

    func testAskingAboutTestsStillFindsThem() async throws {
        let first = try await firstFile("Which test covers the courier retry after a failed delivery?")
        XCTAssertEqual(first, "tests/test_courier.py")
    }

    func testANamedFolderComesFirstEvenWhenTheWordsMissIt() async throws {
        let first = try await firstFile("What happened in run-08?")
        XCTAssertEqual(first, "results/run-08/summary.txt")
    }

    func testStandingOfFiles() {
        XCTAssertEqual(Standing.of("results/a/summary.txt"), .output)
        XCTAssertEqual(Standing.of("results/parser.py"), .main, "code in a folder called results is still code")
        XCTAssertEqual(Standing.of("Reports/Q3 review.md"), .main, "a note someone wrote is never demoted")
        XCTAssertEqual(Standing.of("Tests/CoreTests/Support.swift"), .test)
        XCTAssertEqual(Standing.of("src/ChatTests.swift"), .test)
        XCTAssertEqual(Standing.of("src/app.test.ts"), .test)
        XCTAssertEqual(Standing.of("src/latest.py"), .main)
        XCTAssertEqual(Standing.of("src/contest/rules.py"), .main)
    }

    func testLongProseIsCutSoEveryWordCanBeRead() {
        let paragraph = String(repeating: "word ", count: 200)
        let chunks = Chunker.chunks(of: (0..<20).map { "\($0) \(paragraph)" }.joined(separator: "\n\n"))
        XCTAssertGreaterThan(chunks.count, 3)
        for chunk in chunks { XCTAssertLessThanOrEqual(chunk.text.count, Chunker.mostCharacters) }
        XCTAssertEqual(chunks.last?.endLine, 39, "every line lands in a piece")
    }

    /// The app asks questions while the index rebuilds, and both use the one connection.
    func testQuestionsDuringARebuildAreSafe() async throws {
        for number in 0..<300 {
            let url = top.appendingPathComponent("src/module\(number).py")
            let body = (0..<120).map { "def courier_step_\($0)(parcel):\n    return parcel  # delivery \(number)\n" }.joined()
            try body.write(to: url, atomically: true, encoding: .utf8)
        }
        let vault = try Vault(project: top, store: top.appendingPathComponent("store"))
        try await vault.refresh()
        for _ in 0..<4 {
            try vault.database.execute("PRAGMA user_version = 1")
            try await withThrowingTaskGroup(of: Void.self) { group in
                group.addTask { try await vault.refresh() }
                for _ in 0..<8 {
                    group.addTask { for _ in 0..<12 { _ = try await vault.retrieve("courier delivery step", mode: .walk) } }
                }
                try await group.waitForAll()
            }
            XCTAssertEqual(try vault.database.rows("PRAGMA integrity_check").first?[0].text, "ok")
        }
    }

    func testAnIndexBuiltByAnOlderVersionRebuildsItself() async throws {
        let store = top.appendingPathComponent("store")
        var vault = try Vault(project: top, store: store)
        let first = try await vault.refresh()
        XCTAssertGreaterThan(first.filesChanged, 0)
        let unchanged = try await vault.refresh()
        XCTAssertEqual(unchanged.filesChanged, 0)
        try vault.database.execute("PRAGMA user_version = 1")
        vault = try Vault(project: top, store: store)
        let rebuilt = try await vault.refresh()
        XCTAssertEqual(rebuilt.filesChanged, first.filesChanged)
    }
}
