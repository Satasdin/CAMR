@testable import BurrowCore
import BurrowTrial
import XCTest

final class Scripted: Answerer, @unchecked Sendable {
    var replies: [String]
    var prompts: [String] = []
    init(_ replies: [String]) { self.replies = replies }
    func answer(system: String, user: String, onWord: @escaping @Sendable (String) -> Void) async throws -> ChatResult {
        prompts.append(user)
        return ChatResult(text: replies.removeFirst(), secondsToFirstWord: 0, totalSeconds: 1, promptTokens: 10, answerTokens: 5)
    }
}

final class BurrowTrialTests: XCTestCase {
    private var folder: URL!

    override func setUpWithError() throws {
        folder = FileManager.default.temporaryDirectory.appendingPathComponent("burrow-trial-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws { try? FileManager.default.removeItem(at: folder) }

    private func write(_ text: String, _ path: String, in base: URL? = nil) throws {
        let url = (base ?? folder!).appendingPathComponent(path)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try text.write(to: url, atomically: true, encoding: .utf8)
    }

    // MARK: Reading replies

    func testParsesFilesAndReads() {
        let parsed = ReplyParser.parse("READ: a/b.py\nREAD: `c.py`\n=== FILE: d.py ===\nx = 1\n=== END FILE ===\n")
        XCTAssertEqual(parsed.reads, ["a/b.py", "c.py"])
        XCTAssertEqual(parsed.edits, [FileEdit(path: "d.py", content: "x = 1\n")])
        XCTAssertEqual(parsed.failures, [])
    }

    func testStripsCodeFences() {
        let parsed = ReplyParser.parse("=== FILE: a.py ===\n```python\nx = 1\n```\n=== END FILE ===")
        XCTAssertEqual(parsed.edits.first?.content, "x = 1\n")
    }

    func testStripsCopiedLineNumbersOnlyWhenEveryLineHasOne() {
        XCTAssertEqual(ReplyParser.parse("=== FILE: a.py ===\n1: x = 1\n2: y = 2\n=== END FILE ===").edits.first?.content, "x = 1\ny = 2\n")
        XCTAssertEqual(ReplyParser.parse("=== FILE: a.py ===\n1: x\nplain\n=== END FILE ===").edits.first?.content, "1: x\nplain\n")
    }

    func testRefusesPathsOutsideTheProject() {
        for bad in ["../evil.py", "/etc/passwd", "a/../../b.py", "~/x.py"] {
            let parsed = ReplyParser.parse("=== FILE: \(bad) ===\nx\n=== END FILE ===\nREAD: \(bad)")
            XCTAssertEqual(parsed.edits, [], bad)
            XCTAssertEqual(parsed.reads, [], bad)
            XCTAssertEqual(parsed.failures.count, 2, bad)
        }
    }

    func testAnUnclosedFileIsNotApplied() {
        let parsed = ReplyParser.parse("=== FILE: a.py ===\nx = 1\n")
        XCTAssertEqual(parsed.edits, [])
        XCTAssertEqual(parsed.failures.count, 1)
    }

    func testAnUnclosedFileIsKeptWhenTheModelStoppedByItself() {
        let parsed = ReplyParser.parse("=== FILE: a.py ===\nx = 1\n=== FILE: b.py ===\ny = 2\n", finished: true)
        XCTAssertEqual(parsed.edits, [FileEdit(path: "a.py", content: "x = 1\n"), FileEdit(path: "b.py", content: "y = 2\n")])
        XCTAssertEqual(parsed.failures, [])
    }

    func testReadsNotes() {
        let notes = NoteParser.parse("decision: keep it\n- rejected: retries\nBug: broke\nsomething else")
        XCTAssertEqual(notes.map(\.kind), [.decision, .rejected, .bug])
        XCTAssertEqual(notes[1].text, "retries")
    }

    func testAFileNamedOnTheNextLineStaysWithItsNote() {
        let notes = NoteParser.parse("decision: keep it\n\nfile: a/b.py\n\nrejected: retries\n- function: pay")
        XCTAssertEqual(notes.map(\.text), ["keep it (a/b.py)", "retries (pay)"])
        XCTAssertEqual(NoteParser.parse("file: orphan.py"), [])
    }

    // MARK: Grading

    func testGradesAnswers() throws {
        XCTAssertTrue(try Grader.ask(answer: "I don't know", mustContain: ["know"], mustNot: ["because"]))
        XCTAssertFalse(try Grader.ask(answer: "because reasons", mustContain: [], mustNot: ["because"]))
        XCTAssertFalse(try Grader.ask(answer: "x", mustContain: ["y"], mustNot: []))
        XCTAssertTrue(Grader.saidDontKnow("I do not know why"))
        XCTAssertFalse(Grader.saidDontKnow("It is 30 kg"))
    }

    func testReadsUnittestOutput() {
        let failed = Grader.outcome(output: "Ran 3 tests in 0.1s\n\nFAILED (failures=1, errors=2)\n", exitCode: 1, timedOut: false)
        XCTAssertEqual(failed.ran, 3)
        XCTAssertEqual(failed.failures, 1)
        XCTAssertEqual(failed.errors, 2)
        XCTAssertFalse(failed.passed)
        XCTAssertTrue(Grader.outcome(output: "Ran 2 tests in 0s\n\nOK\n", exitCode: 0, timedOut: false).passed)
        XCTAssertFalse(Grader.outcome(output: "Ran 0 tests in 0s\n\nOK\n", exitCode: 0, timedOut: false).passed, "no tests shows nothing")
    }

    // MARK: The agent loop

    private func workspace() throws -> Workspace {
        let root = folder.appendingPathComponent("work")
        try write("a = 1\nb = 2\n", "pkg/a.py", in: root)
        try write("long\n", "pkg/b.py", in: root)
        return Workspace(url: root)
    }

    func testOpensFilesThenApplies() async throws {
        let answerer = Scripted(["READ: pkg/a.py\nREAD: nope.py", "=== FILE: pkg/a.py ===\na = 2\n=== END FILE ==="])
        let result = try await Agent.run(brief: "change a", kind: .change, excerpts: [], workspace: try workspace(), answerer: answerer)
        XCTAssertEqual(result.filesRead, ["pkg/a.py"])
        XCTAssertEqual(result.edits.map(\.path), ["pkg/a.py"])
        XCTAssertEqual(result.turns.count, 2)
        XCTAssertTrue(answerer.prompts[1].contains("<opened file=\"pkg/a.py\">"))
        XCTAssertTrue(answerer.prompts[1].contains("nope.py does not exist."))
    }

    func testReplacingAnUnopenedFileOpensItFirst() async throws {
        let edit = "=== FILE: pkg/a.py ===\na = 2\n=== END FILE ==="
        let answerer = Scripted([edit, edit])
        let result = try await Agent.run(brief: "change a", kind: .change, excerpts: [], workspace: try workspace(), answerer: answerer)
        XCTAssertEqual(result.filesRead, ["pkg/a.py"])
        XCTAssertEqual(result.turns.count, 2)
        XCTAssertEqual(result.unreadEdits, [])
    }

    func testANewFileNeedsNoOpening() async throws {
        let answerer = Scripted(["=== FILE: pkg/new.py ===\nz = 1\n=== END FILE ==="])
        let result = try await Agent.run(brief: "add", kind: .change, excerpts: [], workspace: try workspace(), answerer: answerer)
        XCTAssertEqual(result.turns.count, 1)
        XCTAssertEqual(result.edits.map(\.path), ["pkg/new.py"])
    }

    func testRoundsAreLimited() async throws {
        var settings = AgentSettings()
        settings.readRounds = 1
        let answerer = Scripted(["READ: pkg/a.py", "READ: pkg/b.py"])
        let result = try await Agent.run(brief: "x", kind: .change, excerpts: [], workspace: try workspace(), answerer: answerer, settings: settings)
        XCTAssertEqual(result.filesRead, ["pkg/a.py"])
        XCTAssertEqual(result.turns.count, 2)
        XCTAssertEqual(result.parseFailures, ["no usable FILE blocks in the final reply"])
    }

    func testAllowanceIsEnforced() async throws {
        var settings = AgentSettings()
        settings.readAllowance = 3
        let answerer = Scripted(["READ: pkg/a.py", "I give up"])
        let result = try await Agent.run(brief: "x", kind: .change, excerpts: [], workspace: try workspace(), answerer: answerer, settings: settings)
        XCTAssertEqual(result.filesRead, [])
        XCTAssertTrue(answerer.prompts[1].contains("was not opened"))
    }

    func testAskSessionsEndOnAnAnswer() async throws {
        let answerer = Scripted(["I don't know."])
        let result = try await Agent.run(brief: "why?", kind: .ask, excerpts: [], workspace: try workspace(), answerer: answerer)
        XCTAssertEqual(result.finalText, "I don't know.")
        XCTAssertEqual(result.edits, [])
    }

    // MARK: A whole project

    private func tinyProject() throws -> TrialProject {
        let root = folder.appendingPathComponent("project")
        try write(#"{"name":"tiny","split":"tune","sessions":[{"id":"01","kind":"change","category":"setup"},{"id":"02","kind":"ask","category":"unknown","must_contain":["know"],"reference_answer":"I don't know","wrong_answer":"It is blue"}]}"#, "project.json", in: root)
        try write("def add(a, b):\n    return 0\n", "base/calc.py", in: root)
        try write("## Discussion\nWe tried subtracting and rejected it.\n\nFix add.\n", "sessions/01/brief.md", in: root)
        try write("def add(a, b):\n    return a + b\n", "sessions/01/reference/calc.py", in: root)
        try write("def add(a, b):\n    return a - b\n", "sessions/01/trap/calc.py", in: root)
        let task = "import unittest\nfrom calc import add\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 2), 4)\n"
        let decisions = "import unittest\nfrom calc import add\nclass D(unittest.TestCase):\n    def test_not_subtracting(self):\n        self.assertNotEqual(add(5, 1), 4)\n"
        try write(task, "sessions/01/tests/test_task.py", in: root)
        try write(decisions, "sessions/01/tests/test_decisions.py", in: root)
        try write("Why?\n", "sessions/02/brief.md", in: root)
        return try TrialProject(root: root)
    }

    func testVerifyAcceptsASoundProject() throws {
        let report = try verify(project: try tinyProject(), scratch: folder.appendingPathComponent("scratch"))
        XCTAssertEqual(report.failures, 0, report.lines.joined(separator: "\n"))
    }

    func testVerifyCatchesATrapThatIsNotCaught() throws {
        let project = try tinyProject()
        try write("def add(a, b):\n    return a + b\n", "sessions/01/trap/calc.py", in: project.root)
        let report = try verify(project: project, scratch: folder.appendingPathComponent("scratch"))
        XCTAssertEqual(report.failures, 1, report.lines.joined(separator: "\n"))
    }

    func testTheSandboxBlocksWritesOutsideTheRun() throws {
        let sandbox = try PythonSandbox(scratch: folder.appendingPathComponent("box"))
        let tests = sandbox.scratch.appendingPathComponent("t")
        let target = NSHomeDirectory() + "/burrow-trial-escape-\(UUID().uuidString)"
        try write("import unittest\nclass T(unittest.TestCase):\n    def test_w(self):\n        open(\(String(reflecting: target)), 'w').write('x')\n", "test_w.py", in: tests)
        let outcome = try sandbox.run(tests: tests, pattern: "test_w.py", workspace: tests).outcome
        XCTAssertFalse(outcome.passed)
        XCTAssertFalse(FileManager.default.fileExists(atPath: target))
    }
}
