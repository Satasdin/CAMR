@testable import BurrowCore
@testable import BurrowMCP
import BurrowTools
import XCTest

final class MCPTests: XCTestCase {
    private var fixture: VaultFixture!
    private var server: MCPServer!

    override func setUp() async throws {
        fixture = try VaultFixture()
        let vault = try await fixture.opened()
        let answerer = FakeAnswerer()
        server = MCPServer(tools: VaultTools(vault: vault, embedder: nil) { _ in answerer })
    }

    private func json(_ line: String?) throws -> [String: Any] {
        try JSONSerialization.jsonObject(with: XCTUnwrap(line).data(using: .utf8)!) as! [String: Any]
    }

    private func start() async throws {
        _ = await server.handle(#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}"#)
    }

    private func errorCode(_ line: String?) throws -> Int? { (try json(line)["error"] as? [String: Any])?["code"] as? Int }

    func testInitializeAgreesAVersionAndOffersTools() async throws {
        let reply = try json(await server.handle(#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}"#))
        let result = reply["result"] as! [String: Any]
        XCTAssertEqual(result["protocolVersion"] as? String, "2025-06-18")
        XCTAssertNotNil((result["capabilities"] as? [String: Any])?["tools"])
        XCTAssertEqual((result["serverInfo"] as? [String: Any])?["name"] as? String, "burrow")
        XCTAssertEqual(reply["id"] as? Int, 1)
    }

    func testAnUnknownVersionGetsTheNewestOne() async throws {
        let reply = try json(await server.handle(#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"1999-01-01"}}"#))
        XCTAssertEqual((reply["result"] as? [String: Any])?["protocolVersion"] as? String, MCPServer.protocolVersions[0])
    }

    func testPingWorksEvenBeforeInitialize() async throws {
        let reply = try json(await server.handle(#"{"jsonrpc":"2.0","id":"a","method":"ping"}"#))
        XCTAssertEqual(reply["id"] as? String, "a")
        XCTAssertEqual((reply["result"] as? [String: Any])?.count, 0)
    }

    func testToolsNeedInitializeFirst() async throws {
        let reply = await server.handle(#"{"jsonrpc":"2.0","id":2,"method":"tools/list"}"#)
        XCTAssertEqual(try errorCode(reply), MCPServer.Code.notInitialized)
    }

    func testToolsListCarriesEverySchema() async throws {
        try await start()
        let reply = try json(await server.handle(#"{"jsonrpc":"2.0","id":2,"method":"tools/list"}"#))
        let tools = (reply["result"] as! [String: Any])["tools"] as! [[String: Any]]
        XCTAssertEqual(tools.count, 12)
        XCTAssertTrue(tools.allSatisfy { ($0["inputSchema"] as? [String: Any])?["type"] as? String == "object" })
        XCTAssertEqual((tools.first { $0["name"] as? String == "vault_remember" }?["annotations"] as? [String: Any])?["readOnlyHint"] as? Bool, false)
    }

    func testNotificationsGetNoReply() async throws {
        let silent = await server.handle(#"{"jsonrpc":"2.0","method":"notifications/initialized"}"#)
        XCTAssertNil(silent)
        let unknown = await server.handle(#"{"jsonrpc":"2.0","method":"made/up"}"#)
        XCTAssertNil(unknown)
    }

    func testAToolCallReturnsTextContent() async throws {
        try await start()
        let reply = try json(await server.handle(#"{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"vault_read","arguments":{"path":"Trips/Lamu.md"}}}"#))
        let result = reply["result"] as! [String: Any]
        XCTAssertEqual(result["isError"] as? Bool, false)
        let content = result["content"] as! [[String: Any]]
        XCTAssertEqual(content[0]["type"] as? String, "text")
        XCTAssertTrue((content[0]["text"] as! String).contains("Omar"))
    }

    func testAToolThatCantDoItsJobIsAResultNotAProtocolError() async throws {
        try await start()
        let reply = try json(await server.handle(#"{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"vault_read","arguments":{"path":"nope.md"}}}"#))
        XCTAssertEqual((reply["result"] as? [String: Any])?["isError"] as? Bool, true)
        XCTAssertNil(reply["error"])
    }

    func testErrorCodes() async throws {
        try await start()
        let cases: [(String, Int)] = [
            ("not json", MCPServer.Code.parse),
            ("[1,2]", MCPServer.Code.invalidRequest),
            ("42", MCPServer.Code.invalidRequest),
            (#"{"jsonrpc":"1.0","id":1,"method":"ping"}"#, MCPServer.Code.invalidRequest),
            (#"{"jsonrpc":"2.0","id":true,"method":"ping"}"#, MCPServer.Code.invalidRequest),
            (#"{"jsonrpc":"2.0","id":1}"#, MCPServer.Code.invalidRequest),
            (#"{"jsonrpc":"2.0","id":1,"method":"resources/list"}"#, MCPServer.Code.methodNotFound),
            (#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":[1]}"#, MCPServer.Code.invalidParams),
            (#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{}}"#, MCPServer.Code.invalidParams),
            (#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"nope"}}"#, MCPServer.Code.invalidParams),
            (#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"vault_read","arguments":5}}"#, MCPServer.Code.invalidParams),
            (#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"vault_read","arguments":{}}}"#, MCPServer.Code.invalidParams),
            (#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}"#, MCPServer.Code.invalidParams),
        ]
        for (line, code) in cases {
            let reply = await server.handle(line)
            XCTAssertEqual(try errorCode(reply), code, line)
        }
    }

    func testBlankLinesAreIgnored() async throws {
        let reply = await server.handle("   ")
        XCTAssertNil(reply)
    }

    func testAnOutsideModelCanAskBurrowToPrepareATask() async throws {
        try await start()
        let line = await server.handle(#"{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"vault_prepare","arguments":{"task":"retry a failed charge"}}}"#)
        let result = try XCTUnwrap(try json(line)["result"] as? [String: Any])
        let text = ((result["content"] as? [[String: Any]])?.first?["text"] as? String) ?? ""
        XCTAssertTrue(text.contains("Decided: "))
        XCTAssertNotEqual(result["isError"] as? Bool, true)
    }

    func testRepliesCarryTheRequestsIDAndAreOneLine() async throws {
        try await start()
        let line = await server.handle(#"{"jsonrpc":"2.0","id":99,"method":"tools/call","params":{"name":"vault_search","arguments":{"query":"retry"}}}"#)
        XCTAssertFalse(try XCTUnwrap(line).contains("\n"))
        XCTAssertEqual(try json(line)["id"] as? Int, 99)
    }

    func testServeAnswersEverythingAndStopsAtTheEndOfInput() async throws {
        var input = [
            #"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}"#,
            #"{"jsonrpc":"2.0","method":"notifications/initialized"}"#,
            #"{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"vault_folders"}}"#,
            #"{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"vault_list"}}"#,
            #"{"jsonrpc":"2.0","id":4,"method":"ping"}"#,
        ]
        input.reverse()
        let lock = NSLock()
        var written: [String] = []
        await server.serve(readLine: {
            lock.lock()
            defer { lock.unlock() }
            return input.popLast()
        }, write: { line in
            lock.lock()
            written.append(line)
            lock.unlock()
        })
        let ids = try written.map { try json($0)["id"] as! Int }
        XCTAssertEqual(ids.count, 4)
        XCTAssertLessThan(ids.firstIndex(of: 2)!, ids.firstIndex(of: 3)!, "tool calls run in order")
    }
}
