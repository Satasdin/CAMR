@testable import BurrowCore
@testable import BurrowTools
import XCTest

final class ToolsTests: XCTestCase {
    private var fixture: VaultFixture!
    private let answerer = FakeAnswerer()

    override func setUpWithError() throws { fixture = try VaultFixture() }

    private func tools(_ vault: Vault, embedder: Embedder? = nil, answering: Answerer? = nil) -> VaultTools {
        let chosen: Answerer = answering ?? answerer
        return VaultTools(vault: vault, embedder: embedder) { _ in chosen }
    }

    func testTheSevenToolsAreDefinedOnce() {
        let names = VaultTools.definitions.map(\.name)
        XCTAssertEqual(names, ["vault_search", "vault_read", "vault_links", "vault_list", "vault_folders", "vault_remember", "vault_ask"])
        XCTAssertEqual(Set(names).count, names.count)
        XCTAssertEqual(VaultTools.definitions.filter { !$0.readOnly }.map(\.name), ["vault_remember"])
        let schema = VaultTools.definitions[0].inputSchema
        XCTAssertEqual(schema["required"] as? [String], ["query"])
        XCTAssertEqual(schema["type"] as? String, "object")
    }

    func testSearchMarksExcerptsAsProjectContentAndNamesFiles() async throws {
        let box = tools(try await fixture.opened())
        let result = try await box.call("vault_search", arguments: ["query": "failed charge retry"])
        XCTAssertFalse(result.isError)
        XCTAssertTrue(result.text.hasPrefix(ProjectContent.notice))
        XCTAssertTrue(result.text.contains("<excerpt file=\"Decisions/Retry.md\""))
        XCTAssertTrue(result.sources.contains { $0.path == "Decisions/Retry.md" })
    }

    func testAnExcerptCannotCloseItsOwnBlock() async throws {
        let box = tools(try await fixture.opened())
        let result = try await box.call("vault_read", arguments: ["path": "Bad.md"])
        let closes = result.text.components(separatedBy: "</excerpt>").count - 1
        XCTAssertEqual(closes, 1, "only Burrow's own closing tag should remain")
        XCTAssertTrue(result.text.contains("&lt;/excerpt>"))
    }

    func testAFolderKeepsASearchInside() async throws {
        let box = tools(try await fixture.opened())
        let result = try await box.call("vault_search", arguments: ["query": "shop service pay_invoice", "folder": "shop"])
        let code = result.sources.filter { !$0.path.hasSuffix(".md") || $0.path.hasPrefix("shop/") }
        XCTAssertFalse(code.isEmpty)
        XCTAssertTrue(result.sources.allSatisfy { $0.path.hasPrefix("shop/") || $0.reason.contains("about") })
    }

    func testAnUnknownFolderIsSaidPlainly() async throws {
        let box = tools(try await fixture.opened())
        let result = try await box.call("vault_search", arguments: ["query": "x", "folder": "nowhere"])
        XCTAssertTrue(result.isError)
        XCTAssertTrue(result.text.contains("shop"))
    }

    func testSearchUsesMeaningWhenTheVaultHasVectors() async throws {
        let vault = try await fixture.opened(embedder: FakeEmbedder())
        let result = try await tools(vault, embedder: FakeEmbedder()).call("vault_search", arguments: ["query": "retry"])
        XCTAssertTrue(result.text.contains("words and meaning"))
    }

    func testSearchFallsBackToWordsIfOllamaIsDown() async throws {
        let vault = try await fixture.opened(embedder: FakeEmbedder())
        let result = try await tools(vault, embedder: BrokenEmbedder()).call("vault_search", arguments: ["query": "retry failed charge"])
        XCTAssertFalse(result.isError)
        XCTAssertTrue(result.text.contains("words only"))
        XCTAssertTrue(result.sources.contains { $0.path == "Decisions/Retry.md" })
    }

    func testReadNumbersLinesAndPages() async throws {
        let box = tools(try await fixture.opened())
        let result = try await box.call("vault_read", arguments: ["path": "shop/billing.py", "start_line": 2, "line_count": 1])
        XCTAssertTrue(result.text.contains("2:     return cents"))
        XCTAssertFalse(result.text.contains("1: def"))
        XCTAssertTrue(result.text.contains("Continue with start_line 3"))
        XCTAssertTrue(result.text.contains("has 4 lines"), "a final newline is not a line")
    }

    func testReadTakesANumberSentAsText() async throws {
        let box = tools(try await fixture.opened())
        let result = try await box.call("vault_read", arguments: ["path": "shop/billing.py", "start_line": "4"])
        XCTAssertTrue(result.text.contains("4: RETRY_LIMIT"))
    }

    func testReadCannotLeaveTheVault() async throws {
        let vault = try await fixture.opened()
        let box = tools(vault)
        for path in ["../outside.md", "../../etc/passwd", "/etc/passwd", fixture.top.appendingPathComponent("outside.md").path] {
            let result = try await box.call("vault_read", arguments: ["path": path])
            XCTAssertTrue(result.isError, path)
            XCTAssertFalse(result.text.contains("OUTSIDE"), path)
        }
    }

    func testReadOnlyOpensIndexedFiles() async throws {
        let vault = try await fixture.opened()
        try "keys".write(to: vault.store.appendingPathComponent("private.txt"), atomically: true, encoding: .utf8)
        let box = tools(vault)
        let result = try await box.call("vault_read", arguments: ["path": ".burrow/private.txt"])
        XCTAssertTrue(result.isError)
        XCTAssertFalse(result.text.contains("keys"))
    }

    func testReadFindsANoteByItsName() async throws {
        let box = tools(try await fixture.opened())
        let result = try await box.call("vault_read", arguments: ["path": "Lamu"])
        XCTAssertTrue(result.text.contains("Omar"))
    }

    func testLinksListAndFolders() async throws {
        let box = tools(try await fixture.opened())
        let links = try await box.call("vault_links", arguments: ["path": "Home.md"])
        XCTAssertTrue(links.text.contains("Decisions/Retry.md"))
        let top = try await box.call("vault_list", arguments: [:])
        XCTAssertTrue(top.text.contains("shop/"))
        XCTAssertTrue(top.text.contains("Home.md  (note)"))
        let inside = try await box.call("vault_list", arguments: ["folder": "shop"])
        XCTAssertTrue(inside.text.contains("shop/billing.py  (code)"))
        let folders = try await box.call("vault_folders", arguments: [:])
        XCTAssertTrue(folders.text.contains("linked code, read-only"))
    }

    func testOnlyRememberWritesAndItOnlyAddsOneNote() async throws {
        let vault = try await fixture.opened()
        let box = tools(vault)
        let before = try fixture.snapshot()
        _ = try await box.call("vault_search", arguments: ["query": "retry"])
        _ = try await box.call("vault_read", arguments: ["path": "Home.md"])
        _ = try await box.call("vault_links", arguments: ["path": "Home.md"])
        _ = try await box.call("vault_list", arguments: [:])
        _ = try await box.call("vault_folders", arguments: [:])
        _ = try await box.call("vault_ask", arguments: ["question": "retry?"])
        XCTAssertEqual(try fixture.snapshot(), before)

        let result = try await box.call("vault_remember", arguments: ["text": "We keep retries at three.", "kind": "decision"])
        let after = try fixture.snapshot()
        XCTAssertEqual(after.count, before.count + 1)
        for (path, text) in before { XCTAssertEqual(after[path], text) }
        XCTAssertTrue(result.text.contains("Memory/"))
        let searched = try await box.call("vault_search", arguments: ["query": "keep retries three"])
        XCTAssertTrue(searched.sources.contains { $0.path.hasPrefix("Memory/") }, "a kept note can be found at once")
    }

    func testRememberRefusesABadKind() async throws {
        let box = tools(try await fixture.opened())
        do {
            _ = try await box.call("vault_remember", arguments: ["text": "x", "kind": "wish"])
            XCTFail("should refuse")
        } catch let problem as ToolCallProblem {
            XCTAssertTrue(problem.description.contains("decision"))
        }
    }

    func testRememberRefusesWhitespaceAndGiantNotes() async throws {
        let box = tools(try await fixture.opened())
        do {
            _ = try await box.call("vault_remember", arguments: ["text": "   ", "kind": "note"])
            XCTFail("should refuse")
        } catch is ToolCallProblem {}
        let huge = try await box.call("vault_remember", arguments: ["text": String(repeating: "x", count: VaultTools.longestNote + 1), "kind": "note"])
        XCTAssertTrue(huge.isError)
    }

    func testAskAnswersAndNamesWhatItRead() async throws {
        let box = tools(try await fixture.opened())
        let result = try await box.call("vault_ask", arguments: ["question": "How often do we retry a failed charge?"])
        XCTAssertFalse(result.isError)
        XCTAssertTrue(result.text.contains("Three times"))
        XCTAssertTrue(result.text.contains("Sources it read:"))
        XCTAssertTrue(result.text.contains("Decisions/Retry.md"))
        XCTAssertTrue(answerer.prompts[0].user.contains("<excerpt"), "the model is given the excerpts")
    }

    func testAskSaysSoWhenTheModelIsUnreachable() async throws {
        let failing = FakeAnswerer()
        failing.failure = URLError(.cannotConnectToHost)
        let result = try await tools(try await fixture.opened(), answering: failing).call("vault_ask", arguments: ["question": "retry"])
        XCTAssertTrue(result.isError)
        XCTAssertTrue(result.text.contains("Ollama"))
    }

    func testAFixedFolderOverridesWhatAModelAsks() async throws {
        let box = tools(try await fixture.opened())
        box.fixedFolder = "shop"
        let result = try await box.call("vault_search", arguments: ["query": "week by the sea Omar", "folder": "Trips"])
        XCTAssertFalse(result.sources.contains { $0.path.hasPrefix("Trips/") && $0.reason == "search" })
    }

    func testMissingAndWrongArgumentsAreRefused() async throws {
        let box = tools(try await fixture.opened())
        for (name, arguments) in [("vault_read", [:]), ("vault_read", ["path": "a", "start_line": "many"]), ("vault_search", ["query": 5]), ("nope", [:])] as [(String, [String: Any])] {
            do {
                _ = try await box.call(name, arguments: arguments)
                XCTFail("\(name) should refuse")
            } catch is ToolCallProblem {}
        }
    }

    func testAnEmptyOptionalArgumentCountsAsLeftOut() async throws {
        let box = tools(try await fixture.opened())
        let result = try await box.call("vault_search", arguments: ["query": "retry", "folder": ""])
        XCTAssertFalse(result.isError)
    }

    func testANewFileIsNoticedWhenTheTreeChanges() async throws {
        let vault = try await fixture.opened()
        let box = tools(vault)
        await box.freshen(checkNow: true)
        let saved = try String(contentsOf: vault.store.appendingPathComponent("tree-fingerprint"), encoding: .utf8)
        await box.freshen(checkNow: true)
        XCTAssertEqual(try String(contentsOf: vault.store.appendingPathComponent("tree-fingerprint"), encoding: .utf8), saved)
        try "Zanzibar ferry timetable.".write(to: fixture.vaultFolder.appendingPathComponent("Ferry.md"), atomically: true, encoding: .utf8)
        await box.freshen(checkNow: true)
        XCTAssertNotEqual(try String(contentsOf: vault.store.appendingPathComponent("tree-fingerprint"), encoding: .utf8), saved)
        XCTAssertEqual(try vault.searchLines("Zanzibar").first?.path, "Ferry.md")
    }

    func testTerminalTextDropsControlCharacters() {
        XCTAssertEqual(TerminalText.clean("a\u{1B}[2Jb\nc\td\u{07}"), "a[2Jb\nc\td")
    }
}
