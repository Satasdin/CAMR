@testable import BurrowCore
@testable import BurrowTUI
@testable import BurrowTools
import XCTest

/// The Ledger page of the full-screen terminal view.
final class LedgerScreenTests: XCTestCase {
    private var fixture: VaultFixture!
    private var model: Model!

    override func setUp() async throws {
        fixture = try VaultFixture()
        let vault = try await fixture.opened()
        model = Model(vault: vault, modelName: "stand-in")
        model.resize(width: 120, height: 34)
        model.reload()
    }

    private func press(_ keys: Key...) { for key in keys { _ = model.handle(key) } }
    private func screen() -> String { View.render(model).plainText }

    func testAnEmptyLedgerSaysHowToStart() {
        press(.character("L"))
        XCTAssertEqual(model.page, .ledger)
        XCTAssertTrue(screen().contains("Nothing kept yet"))
        press(.escape)
        XCTAssertEqual(model.page, .vault)
    }

    func testCommitsShowWithTheirDetailAndWrongOnesAreMarked() throws {
        let ledger = Ledger(vault: model.vault)
        let wrong = try ledger.commit(.fact, "Charges retry five times", files: ["Decisions/Retry.md"], author: "qwen3:4b",
                                      client: "opencode", at: Date(timeIntervalSince1970: 1_000))
        try ledger.revert(wrong.id, why: "Three times, as Retry.md says.", author: "claude-opus")
        try ledger.commit(.plan, "Next: the shop's refunds", author: "claude-opus", branch: "shop", at: Date(timeIntervalSince1970: 500))
        press(.character("L"))
        var text = screen()
        XCTAssertTrue(text.contains("3 commits on every branch"), text)
        XCTAssertTrue(text.contains("1 to check"), text)
        XCTAssertTrue(text.contains("Rests on"), text)
        // The correction is newest; the wrong fact is next.
        press(.down)
        text = screen()
        XCTAssertTrue(text.contains("Marked wrong"), text)
        XCTAssertTrue(text.contains("Written by qwen3:4b in opencode"), text)
        press(.tab)
        XCTAssertEqual(model.ledgerView.branch, "main")
        press(.tab)
        XCTAssertEqual(model.ledgerView.branch, "shop")
        XCTAssertTrue(screen().contains("Next: the shop's refunds"))
        press(.character("r"))
        XCTAssertTrue(screen().contains("What the next model is handed"))
        XCTAssertTrue(screen().contains("Plan: Next: the shop's refunds"))
    }

    func testEnterOpensTheFileACommitRestsOn() throws {
        try Ledger(vault: model.vault).commit(.decision, "Retry three times", files: ["Decisions/Retry.md"], author: "a")
        press(.character("L"), .enter)
        XCTAssertEqual(model.page, .vault)
        XCTAssertEqual(model.document?.path, "Decisions/Retry.md")
    }

    func testANarrowWindowStacksTheDetailUnderTheList() throws {
        try Ledger(vault: model.vault).commit(.decision, "Retry three times", files: ["Decisions/Retry.md"], author: "a")
        model.resize(width: 70, height: 30)
        press(.character("L"))
        let text = screen()
        XCTAssertTrue(text.contains("Retry three times"))
        XCTAssertTrue(text.contains("Rests on"))
    }
}
