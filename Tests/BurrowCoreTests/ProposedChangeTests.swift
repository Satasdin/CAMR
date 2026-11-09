@testable import BurrowCore
import XCTest

/// A model's change reaches a file only through `applyChange`, and only if the file is still what the model was shown.
final class ProposedChangeTests: XCTestCase {
    private var top: URL!
    private var vault: Vault!
    private var noteFile: URL { top.appendingPathComponent("vault/Plan.md") }
    private var codeFile: URL { top.appendingPathComponent("shop/billing.py") }

    override func setUpWithError() throws {
        top = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        for (url, text) in [(noteFile, "first draft\n"), (codeFile, "def pay():\n    return 1\n")] {
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try text.write(to: url, atomically: true, encoding: .utf8)
        }
        vault = try Vault(project: top.appendingPathComponent("vault"), everything: true)
        try vault.linkFolder(top.appendingPathComponent("shop"))
    }

    override func tearDownWithError() throws { try? FileManager.default.removeItem(at: top) }

    private func read(_ url: URL) throws -> String { try String(contentsOf: url, encoding: .utf8) }

    func testAnAcceptedChangeIsWrittenWhenTheFileIsUnchanged() throws {
        try vault.applyChange("Plan.md", expecting: "first draft\n", with: "second draft\n")
        XCTAssertEqual(try read(noteFile), "second draft\n")
    }

    func testAnAcceptedChangeReachesALinkedFolder() throws {
        try vault.applyChange("shop/billing.py", expecting: "def pay():\n    return 1\n", with: "def pay():\n    return 2\n")
        XCTAssertEqual(try read(codeFile), "def pay():\n    return 2\n")
    }

    func testNothingIsWrittenIfTheFileChangedSinceTheProposal() throws {
        try "the person kept typing\n".write(to: noteFile, atomically: true, encoding: .utf8)
        XCTAssertThrowsError(try vault.applyChange("Plan.md", expecting: "first draft\n", with: "second draft\n"))
        XCTAssertEqual(try read(noteFile), "the person kept typing\n")
    }

    func testAChangeCannotLeaveTheVault() throws {
        let outside = top.appendingPathComponent("outside.md")
        try "safe\n".write(to: outside, atomically: true, encoding: .utf8)
        XCTAssertThrowsError(try vault.applyChange("../outside.md", expecting: "safe\n", with: "overwritten\n"))
        XCTAssertEqual(try read(outside), "safe\n")
    }

    func testTheModelIsToldNotToInventReasons() {
        XCTAssertTrue(Asking.withMemory.contains(Asking.reasons))
    }
}
