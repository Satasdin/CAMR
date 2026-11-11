@testable import BurrowCore
@testable import BurrowMCP
@testable import BurrowTools
import XCTest

final class PackToolTests: XCTestCase {
    func testAPackIsTheFolderWholeAndTheWarmerHearsOfItAfterTheReply() async throws {
        let fixture = try VaultFixture()
        let vault = try await fixture.opened()
        let answerer = FakeAnswerer()
        let tools = VaultTools(vault: vault, embedder: nil) { _ in answerer }
        let server = MCPServer(tools: tools)
        var heard: [(String, [String])] = []
        server.afterCall = { name, _, result in heard.append((name, result.sources.map(\.path))) }
        _ = await server.handle(#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}"#)

        let reply = await server.handle(#"{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"vault_pack","arguments":{"folder":"Trips"}}}"#)
        let result = try XCTUnwrap(try JSONSerialization.jsonObject(with: XCTUnwrap(reply?.data(using: .utf8))) as? [String: Any])["result"] as? [String: Any]
        XCTAssertEqual(result?["isError"] as? Bool, false)
        let text = try XCTUnwrap(((result?["content"] as? [[String: Any]])?.first)?["text"] as? String)
        XCTAssertTrue(text.hasPrefix("The user's files from their Burrow vault follow: Trips"))
        XCTAssertTrue(text.contains("<excerpt file=\"Trips/Lamu.md\""))

        // The text is exactly the pack's, so a program can open a conversation with it and match the saved cache.
        let shelf = KVShelf(vault: vault)
        let plan = try shelf.plan(scope: "Trips", budgetCharacters: KVShelf.packCharacters(windowTokens: tools.packWindow))
        XCTAssertEqual(text, shelf.text(of: plan.packs[0], in: plan))
        XCTAssertEqual(heard.first?.0, "vault_pack")
        XCTAssertTrue(heard.first?.1.contains("Trips/Lamu.md") ?? false)

        let missing = await server.handle(#"{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"vault_pack","arguments":{"folder":"Trips","part":9}}}"#)
        XCTAssertTrue(missing?.contains("\"isError\":true") ?? false, "a part that doesn't exist is a readable failure")
        XCTAssertEqual(heard.count, 1, "a failed call is not passed on")
    }

    func testWithNoServerTheWarmerTurnsItselfOffAndLookupsAreUntouched() async throws {
        let fixture = try VaultFixture()
        let vault = try await fixture.opened()
        let warmer = KVWarmer(settings: KVWarmer.Settings(server: URL(string: "http://127.0.0.1:9")!), open: { vault })
        guard case .off = await warmer.connect() else { return XCTFail("nothing listens on port 9") }
        warmer.noticed(["Trips/Lamu.md"])
        warmer.asked(scope: "Trips", part: 1)
        await warmer.settle()
        let history = await warmer.history
        XCTAssertEqual(history, [])
    }
}
