@testable import BurrowChat
@testable import BurrowCore
import BurrowTools
import XCTest

/// Plays back a script of replies and records what it was sent.
final class ScriptedBackend: ChatBackend {
    let model: String
    var script: [ModelReply]
    private(set) var sent: [[[String: Any]]] = []
    private(set) var toolsOffered: [Bool] = []

    init(model: String = "stand-in", script: [ModelReply]) {
        self.model = model
        self.script = script
    }

    func reply(messages: [[String: Any]], tools: [[String: Any]]?, onWord: @escaping (String) -> Void) async throws -> ModelReply {
        sent.append(messages)
        toolsOffered.append(tools != nil)
        let reply = script.isEmpty ? ModelReply(text: "done", toolCalls: []) : script.removeFirst()
        if !reply.text.isEmpty { onWord(reply.text) }
        return reply
    }
}

final class ChatTests: XCTestCase {
    private var fixture: VaultFixture!
    private var tools: VaultTools!

    override func setUp() async throws {
        fixture = try VaultFixture()
        let vault = try await fixture.opened()
        let answerer = FakeAnswerer()
        tools = VaultTools(vault: vault, embedder: nil) { _ in answerer }
    }

    private func search(_ query: String) -> ModelReply {
        ModelReply(text: "", toolCalls: [ModelToolCall(name: "vault_search", arguments: ["query": query])])
    }

    func testToolsAreReallyCalledAndTheResultGoesBack() async throws {
        let backend = ScriptedBackend(script: [search("retry"), ModelReply(text: "Three times.", toolCalls: [])])
        let turn = try await ChatSession(tools: tools, backend: backend).ask("How often?")
        XCTAssertEqual(turn.answer, "Three times.")
        XCTAssertEqual(turn.rounds, 2)
        XCTAssertEqual(turn.modelCalls, 1)
        XCTAssertEqual(turn.events[0].name, "vault_search")
        let tool = backend.sent[1].first { $0["role"] as? String == "tool" }
        XCTAssertEqual(tool?["tool_name"] as? String, "vault_search")
        XCTAssertTrue((tool?["content"] as? String)?.contains("<excerpt") ?? false)
        XCTAssertFalse(turn.sources.isEmpty)
    }

    func testTheLoopStopsAtItsRoundLimitAndStillAnswers() async throws {
        let many = (0..<20).map { search("query \($0)") }
        let backend = ScriptedBackend(script: many + [ModelReply(text: "unused", toolCalls: [])])
        var settings = ChatSession.Settings()
        settings.mostRounds = 3
        let turn = try await ChatSession(tools: tools, backend: backend, settings: settings).ask("Loop?")
        XCTAssertEqual(turn.events.count, 3)
        XCTAssertTrue(turn.endedAtLimit)
        XCTAssertEqual(backend.toolsOffered.last, false, "the last round offers no tools, so the model has to answer")
    }

    func testAFailedCallIsToldToTheModelNotThrown() async throws {
        let bad = ModelReply(text: "", toolCalls: [ModelToolCall(name: "vault_read", arguments: [:])])
        let backend = ScriptedBackend(script: [bad, ModelReply(text: "ok", toolCalls: [])])
        let turn = try await ChatSession(tools: tools, backend: backend).ask("?")
        XCTAssertTrue(turn.events[0].failed)
        XCTAssertTrue((backend.sent[1].last?["content"] as? String)?.contains("did not work") ?? false)
    }

    func testAnIdenticalCallIsNotRunTwice() async throws {
        let backend = ScriptedBackend(script: [search("retry"), search("retry"), ModelReply(text: "ok", toolCalls: [])])
        let turn = try await ChatSession(tools: tools, backend: backend).ask("?")
        XCTAssertEqual(turn.events.count, 1)
    }

    func testAlwaysSearchRunsFirstAndIsMarkedAsNotTheModelsChoice() async throws {
        let backend = ScriptedBackend(script: [ModelReply(text: "Answer.", toolCalls: [])])
        var settings = ChatSession.Settings()
        settings.alwaysSearchFirst = true
        let turn = try await ChatSession(tools: tools, backend: backend, settings: settings).ask("retry failed charge")
        XCTAssertEqual(turn.events.count, 1)
        XCTAssertTrue(turn.events[0].forced)
        XCTAssertEqual(turn.modelCalls, 0)
        XCTAssertTrue(backend.sent[0].contains { $0["role"] as? String == "tool" })
    }

    func testAModelCannotKeepANoteUnlessSomeoneAgrees() async throws {
        let before = try fixture.snapshot()
        let remember = ModelReply(text: "", toolCalls: [ModelToolCall(name: "vault_remember", arguments: ["text": "evil", "kind": "note"])])
        let backend = ScriptedBackend(script: [remember, ModelReply(text: "ok", toolCalls: [])])
        let turn = try await ChatSession(tools: tools, backend: backend).ask("?")
        XCTAssertEqual(try fixture.snapshot(), before)
        XCTAssertTrue(turn.events[0].failed)
    }

    func testAgreeingKeepsTheNote() async throws {
        let remember = ModelReply(text: "", toolCalls: [ModelToolCall(name: "vault_remember", arguments: ["text": "We chose three", "kind": "decision"])])
        let backend = ScriptedBackend(script: [remember, ModelReply(text: "ok", toolCalls: [])])
        var observer = ChatSession.Observer()
        observer.mayRemember = { _, _ in true }
        let turn = try await ChatSession(tools: tools, backend: backend).ask("?", observer: observer)
        XCTAssertFalse(turn.events[0].failed)
        XCTAssertEqual(try fixture.snapshot().filter { $0.key.contains("/Memory/") }.count, 1)
    }

    func testOnlyQuestionsAndAnswersAreCarriedForward() async throws {
        let backend = ScriptedBackend(script: [search("retry"), ModelReply(text: "First.", toolCalls: []), ModelReply(text: "Second.", toolCalls: [])])
        let session = ChatSession(tools: tools, backend: backend)
        _ = try await session.ask("one")
        _ = try await session.ask("two")
        let last = backend.sent.last!
        XCTAssertFalse(last.contains { $0["role"] as? String == "tool" }, "old excerpts aren't resent")
        XCTAssertTrue(last.contains { $0["content"] as? String == "First." })
    }

    func testQwenGetsItsOffSwitch() async throws {
        let backend = ScriptedBackend(model: "qwen3:4b", script: [ModelReply(text: "ok", toolCalls: [])])
        _ = try await ChatSession(tools: tools, backend: backend).ask("hello")
        XCTAssertTrue((backend.sent[0].last?["content"] as? String)?.hasSuffix("/no_think") ?? false)
    }

    func testThinkingIsHiddenAsItStreams() {
        var filter = ThinkFilter()
        XCTAssertEqual(filter.add("<thi"), "")
        XCTAssertEqual(filter.add("nk>secret reasoning"), "")
        XCTAssertEqual(filter.add("</think>\n\nThe"), "The")
        XCTAssertEqual(filter.add(" answer"), " answer")
    }

    func testAnswersWithoutThinkingPassStraightThrough() {
        var filter = ThinkFilter()
        XCTAssertEqual(filter.add("Hello"), "Hello")
        XCTAssertEqual(filter.add(" there"), " there")
    }

    func testToolSchemaIsInOllamasShape() throws {
        let schema = OllamaChat.schema(of: VaultTools.definitions[0])
        XCTAssertEqual(schema["type"] as? String, "function")
        let function = try XCTUnwrap(schema["function"] as? [String: Any])
        XCTAssertEqual(function["name"] as? String, "vault_search")
        XCTAssertNotNil(function["parameters"] as? [String: Any])
    }
}
