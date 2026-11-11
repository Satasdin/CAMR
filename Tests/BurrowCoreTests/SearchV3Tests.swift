@testable import BurrowCore
import XCTest

final class SearchV3Tests: XCTestCase {
    func testAClauseStaysWithTheHeadingThatNamesIt() {
        let filler = (1...40).map { "(\($0)) A long clause about something else entirely, repeated to fill the section." }.joined(separator: "\n\n")
        let text = "---\ntitle: The Act\n---\n\n# Part II\n\n## 6. Appointment\n\n\(filler)\n\n## 7. Term of office\n\n(1) Qualifications.\n\n(2) A single term of six years.\n\n## 8. Functions\n\nThe office shall act.\n"
        let pieces = Chunker.markdownChunks(of: text)
        let holding = try! XCTUnwrap(pieces.first { $0.text.contains("six years") })
        XCTAssertTrue(holding.text.contains("## 7. Term of office"), "the clause is cut with its heading")
        XCTAssertTrue(holding.section.hasPrefix("The Act › Part II › 7. Term of office"))
        XCTAssertEqual(pieces.map(\.startLine).sorted(), pieces.map(\.startLine), "pieces are in order")
        let lines = text.components(separatedBy: "\n").count - 1
        XCTAssertEqual(pieces.last?.endLine, lines, "every line lands somewhere")
    }

    func testCodeFencesAreNotHeadings() {
        let text = "# Notes\n\n```sh\n# not a heading\necho hi\n```\n\n## Real\n\nText.\n"
        let pieces = Chunker.markdownChunks(of: text)
        XCTAssertFalse(pieces.contains { $0.section.contains("not a heading") })
    }

    func testFocusKeepsTheDensestRun() {
        let body = (1...60).map { $0 == 45 ? "The breach must be notified within seventy-two hours." : "Unrelated line number \($0) about other duties." }.joined(separator: "\n")
        let (offset, kept) = Vault.focus(body, on: ["breach", "notified", "hours"], most: 400)
        XCTAssertTrue(kept.contains { $0.contains("seventy-two") })
        XCTAssertLessThanOrEqual(kept.joined(separator: "\n").count, 400)
        XCTAssertTrue(offset <= 44 && offset + kept.count > 44)
    }
}
