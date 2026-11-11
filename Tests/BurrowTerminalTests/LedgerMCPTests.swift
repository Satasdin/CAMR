@testable import BurrowCore
@testable import BurrowMCP
@testable import BurrowTools
import XCTest

/// The Ledger through MCP: the four-tool door, the old names still answering, the trust line, and a handoff when a connection closes.
final class LedgerMCPTests: XCTestCase {
    private var fixture: VaultFixture!
    private var tools: VaultTools!
    private var server: MCPServer!

    override func setUp() async throws {
        fixture = try VaultFixture()
        let vault = try await fixture.opened()
        let answerer = FakeAnswerer()
        tools = VaultTools(vault: vault, embedder: nil) { _ in answerer }
        server = MCPServer(tools: tools, keepsSessions: true)
        server.toolSet = .door
        _ = await server.handle(#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"opencode","version":"1"}}}"#)
    }

    private func call(_ name: String, _ arguments: String) async throws -> String {
        let line = await server.handle(#"{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"\#(name)","arguments":\#(arguments)}}"#)
        let reply = try JSONSerialization.jsonObject(with: XCTUnwrap(line).data(using: .utf8)!) as! [String: Any]
        let content = (reply["result"] as? [String: Any])?["content"] as? [[String: Any]]
        return try XCTUnwrap(content?.first?["text"] as? String, "\(reply)")
    }

    func testTheDoorListsFourToolsAndOldNamesStillAnswer() async throws {
        let line = await server.handle(#"{"jsonrpc":"2.0","id":2,"method":"tools/list"}"#)
        let reply = try JSONSerialization.jsonObject(with: XCTUnwrap(line).data(using: .utf8)!) as! [String: Any]
        let names = ((reply["result"] as! [String: Any])["tools"] as! [[String: Any]]).compactMap { $0["name"] as? String }
        XCTAssertEqual(Set(names), ["burrow_find", "burrow_read", "burrow_resume", "burrow_commit"])
        let old = try await call("vault_search", #"{"query":"retry a failed charge"}"#)
        XCTAssertTrue(old.contains("\nTrust: "), old)
        XCTAssertTrue(old.contains("Retry"))
    }

    func testFindSaysWhenTheVaultDoesNotHoldIt() async throws {
        let text = try await call("burrow_find", #"{"query":"zzqx unheard of words"}"#)
        XCTAssertTrue(text.contains("the vault does not hold this"), text)
    }

    func testCommitResumeAndACorrectionOnTheTrustLine() async throws {
        let kept = try await call("burrow_commit", #"{"kind":"fact","message":"Charges retry five times","files":"Decisions/Retry.md","model":"qwen3:4b"}"#)
        XCTAssertTrue(kept.hasPrefix("Kept as fact "), kept)
        let id = String(kept.dropFirst("Kept as fact ".count).prefix { $0 != " " })
        _ = try await call("burrow_revert", #"{"commit":"\#(id)","right":"They retry three times, as Retry.md says.","model":"claude-opus"}"#)
        let head = try await call("burrow_resume", "{}")
        XCTAssertTrue(head.contains("MARKED WRONG"), head)
        XCTAssertTrue(head.contains("written by qwen3:4b in opencode"), head)
        let found = try await call("burrow_find", #"{"query":"retry a failed charge"}"#)
        XCTAssertTrue(found.contains("The Ledger holds a correction on these files"), found)
        XCTAssertFalse(found.contains("They retry three times"), found)
        let blame = try await call("burrow_blame", #"{"path":"Decisions/Retry.md"}"#)
        XCTAssertTrue(blame.hasPrefix("<ledger>"), blame)
    }

    func testMatchingLedgerNotesComeWithSearchAndCanBeTurnedOff() async throws {
        _ = try await call("burrow_commit", #"{"kind":"fact","message":"A failed charge is retried three times before the order is cancelled","files":"Decisions/Retry.md","model":"claude-opus"}"#)
        let found = try await call("burrow_find", #"{"query":"how many times is a failed charge retried"}"#)
        XCTAssertTrue(found.contains("Notes earlier sessions left in the Ledger"), found)
        XCTAssertTrue(found.contains("retried three times before the order is cancelled"), found)
        tools.ledgerNotesOn = false
        tools.trustLinesOn = false
        let plain = try await call("burrow_find", #"{"query":"how many times is a failed charge retried"}"#)
        XCTAssertFalse(plain.contains("Notes earlier sessions"), plain)
        XCTAssertFalse(plain.contains("Trust:"), plain)
    }

    func testWritesAreRefusedOutsideMCP() async throws {
        let chat = VaultTools(vault: tools.vault, embedder: nil) { _ in FakeAnswerer() }
        let result = try await chat.call("burrow_commit", arguments: ["kind": "fact", "message": "x"])
        XCTAssertTrue(result.isError)
        XCTAssertTrue(chat.ledger.log().isEmpty)
    }

    func testCitedPathsStayInsideTheVault() async throws {
        _ = try await call("burrow_commit", #"{"kind":"fact","message":"Paths","files":"/etc/passwd, ../outside.md, Decisions/Retry.md"}"#)
        XCTAssertEqual(tools.ledger.log().first?.cites.keys.sorted(), ["Decisions/Retry.md"])
    }

    func testAClosedConnectionLeavesAHandoff() async throws {
        _ = try await call("burrow_find", #"{"query":"retry a failed charge"}"#)
        await server.serve(readLine: { nil }, write: { _ in })
        let handoffs = tools.ledger.log().filter { $0.kind == .handoff }
        XCTAssertEqual(handoffs.count, 1)
        XCTAssertTrue(handoffs[0].message.hasPrefix("opencode stopped after 1 lookup"), handoffs[0].message)
    }
}
