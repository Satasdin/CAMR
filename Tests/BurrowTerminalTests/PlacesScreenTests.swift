@testable import BurrowCore
@testable import BurrowTUI
@testable import BurrowTools
import XCTest

/// The places across the top of the terminal view, as in the Mac app.
final class PlacesScreenTests: XCTestCase {
    private var fixture: VaultFixture!
    private var model: Model!

    override func setUp() async throws {
        fixture = try VaultFixture()
        let vault = try await fixture.opened()
        var record = SessionRecord(id: "s1")
        record.client = "opencode"
        record.trail = [TrailStep(tool: "vault_search", asked: "retry a failed charge", files: ["Decisions/Retry.md:3-3"])]
        try SessionStore(vault: vault).save(record)
        model = Model(vault: vault, modelName: "stand-in")
        model.resize(width: 120, height: 34)
        model.reload()
    }

    private func press(_ keys: Key...) { for key in keys { _ = model.handle(key) } }
    private func screen() -> String { View.render(model).plainText }

    func testNumberKeysMoveBetweenPlacesAndTheRowShowsWhatEachHolds() {
        XCTAssertTrue(screen().contains("1 Library"))
        XCTAssertTrue(screen().contains("2 Conversations  1"))
        press(.character("2"))
        XCTAssertEqual(model.page, .conversations)
        press(.character("4"))
        XCTAssertEqual(model.page, .shelf)
        XCTAssertTrue(screen().contains("The shelf is empty"))
        press(.character("5"))
        XCTAssertEqual(model.page, .programs)
        press(.character("1"))
        XCTAssertEqual(model.page, .vault)
    }

    func testAConversationShowsItsTrailAndOpensWhatItRead() {
        press(.character("2"))
        let text = screen()
        XCTAssertTrue(text.contains("OpenCode"), text)
        XCTAssertTrue(text.contains("↗ search retry a failed charge"), text)
        XCTAssertTrue(text.contains("Decisions/Retry.md"), text)
        press(.enter)
        XCTAssertEqual(model.page, .vault)
        XCTAssertEqual(model.document?.path, "Decisions/Retry.md")
    }

    func testProgramsListEveryClientAndOpenTheirConversations() {
        press(.character("5"))
        let text = screen()
        for name in ["Claude Code", "OpenCode", "LM Studio", "llama.cpp", "Ollama"] { XCTAssertTrue(text.contains(name), name) }
        XCTAssertTrue(text.contains("connect: claude mcp add burrow"))
        press(.down, .enter)
        XCTAssertEqual(model.page, .conversations)
        XCTAssertEqual(model.places.conversationFilter, .openCode)
    }

    func testTheLibraryGlanceCountsKindsAndWhatProgramsRead() {
        let text = screen()
        XCTAssertTrue(text.contains("What this vault holds"), text)
        XCTAssertTrue(text.contains("1×   Decisions/Retry.md"), text)
    }

    func testClientNamesAreMatchedOllamaBeforeLlama() {
        XCTAssertEqual(Client("ollama"), .ollama)
        XCTAssertEqual(Client("llama.cpp"), .llamaCpp)
        XCTAssertEqual(Client("LM Studio"), .lmStudio)
        XCTAssertEqual(Client("claude-code"), .claudeCode)
    }
}
