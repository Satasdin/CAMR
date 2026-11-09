import BurrowCore
import Foundation

public struct SessionRecord: Codable, Sendable {
    public var project: String
    public var split: String
    public var mode: String
    public var session: String
    public var category: String
    public var kind: String
    public var taskPassed: Bool
    public var decisionBroken: Bool
    public var decisionCheckErrored: Bool
    public var taskOutcome: String
    public var decisionOutcome: String
    public var editsApplied: [String]
    public var filesRead: [String]
    public var unreadEdits: [String]
    public var retrievedPaths: [String]
    public var retrievedCharacters: Int
    public var seconds: Double
    public var retrieveSeconds: Double
    public var modelCalls: Int
    public var promptTokens: Int
    public var answerTokens: Int
    public var parseFailures: [String]
    public var saidDontKnow: Bool
}

public struct TrialOptions: Sendable {
    public var modes: [Mode]
    public var runName: String
    public var scratch: URL
    public var results: URL
    public var settings = AgentSettings()
    public var overwrite = false

    public init(modes: [Mode], runName: String, scratch: URL, results: URL) {
        self.modes = modes
        self.runName = runName
        self.scratch = scratch
        self.results = results
    }
}

private func describe(_ outcome: TestOutcome?) -> String {
    guard let outcome else { return "no tests" }
    if outcome.timedOut { return "timed out" }
    return "ran \(outcome.ran), failures \(outcome.failures), errors \(outcome.errors), exit \(outcome.exitCode)"
}

private func hasTests(_ folder: URL, _ name: String) -> Bool {
    FileManager.default.fileExists(atPath: folder.appendingPathComponent(name).path)
}

/// Runs a project from its first session to its last, in each mode, and saves what happened.
public func runTrial(project: TrialProject, options: TrialOptions, answerer: Answerer, embedder: Embedder,
                     log: @escaping (String) -> Void) async throws -> [SessionRecord] {
    let files = FileManager.default
    let results = options.results.appendingPathComponent(options.runName)
    if files.fileExists(atPath: results.path) {
        guard options.overwrite else { throw TrialFailure("\(results.path) exists. Results are saved once; pick another run name.") }
        try files.removeItem(at: results)
    }
    try files.createDirectory(at: results, withIntermediateDirectories: true)
    let sessionsFile = results.appendingPathComponent("sessions.jsonl")
    files.createFile(atPath: sessionsFile.path, contents: nil)
    let writer = try FileHandle(forWritingTo: sessionsFile)
    defer { try? writer.close() }
    let encoder = JSONEncoder()
    encoder.keyEncodingStrategy = .convertToSnakeCase
    encoder.outputFormatting = [.sortedKeys]

    var records: [SessionRecord] = []
    var writtenNotes: [String: String] = [:]

    for mode in options.modes {
        let home = options.scratch.appendingPathComponent(options.runName).appendingPathComponent(project.spec.name).appendingPathComponent(mode.rawValue)
        if files.fileExists(atPath: home.path) { try files.removeItem(at: home) }
        try files.createDirectory(at: home, withIntermediateDirectories: true)
        let sandbox = try PythonSandbox(scratch: home)
        let workspace = Workspace(url: sandbox.scratch.appendingPathComponent("workspace"))
        let store = sandbox.scratch.appendingPathComponent("store")
        let hidden = sandbox.scratch.appendingPathComponent("hidden")
        let transcripts = results.appendingPathComponent(project.spec.name).appendingPathComponent(mode.rawValue)
        try files.createDirectory(at: transcripts, withIntermediateDirectories: true)
        try workspace.reset(to: project, before: 0)
        let vault = mode == .none ? nil : try Vault(project: workspace.url, store: store)

        for (index, session) in project.spec.sessions.enumerated() {
            log("\(mode.rawValue) \(session.id) (\(session.category.rawValue))")
            try workspace.reset(to: project, before: index)
            let brief = try project.brief(session)

            var retrieved: Retrieved?
            if let vault {
                try await vault.refresh(embedder: embedder)
                retrieved = try await vault.retrieve(brief, mode: mode, embedder: embedder)
            }
            let agent = try await Agent.run(brief: brief, kind: session.kind, excerpts: retrieved?.excerpts ?? [], workspace: workspace,
                                            answerer: answerer, settings: options.settings)

            var taskPassed = false
            var decisionBroken = false
            var decisionErrored = false
            var taskOutcome = "not a change session"
            var decisionOutcome = "no tests"
            var testOutput = ""
            switch session.kind {
            case .ask:
                taskPassed = try Grader.ask(answer: agent.finalText, mustContain: session.mustContain ?? [], mustNot: session.mustNot ?? [])
                taskOutcome = taskPassed ? "answer accepted" : "answer rejected"
            case .change:
                try workspace.apply(agent.edits)
                let copied = hidden.appendingPathComponent(session.id)
                if files.fileExists(atPath: copied.path) { try files.removeItem(at: copied) }
                try files.createDirectory(at: hidden, withIntermediateDirectories: true)
                try files.copyItem(at: project.tests(session), to: copied)
                let task = try sandbox.run(tests: copied, pattern: "test_task.py", workspace: workspace.url)
                taskPassed = task.outcome.passed
                taskOutcome = describe(task.outcome)
                testOutput = task.output
                if hasTests(copied, "test_decisions.py") {
                    let decisions = try sandbox.run(tests: copied, pattern: "test_decisions.py", workspace: workspace.url)
                    // A crash says nothing about the decision. Only a failed assertion counts as breaking it.
                    decisionBroken = decisions.outcome.failures > 0
                    decisionErrored = decisions.outcome.errors > 0 || decisions.outcome.timedOut
                    decisionOutcome = describe(decisions.outcome)
                    testOutput += "\n--- decisions ---\n" + decisions.output
                }
            }

            let record = SessionRecord(
                project: project.spec.name, split: project.spec.split, mode: mode.rawValue, session: session.id,
                category: session.category.rawValue, kind: session.kind.rawValue, taskPassed: taskPassed, decisionBroken: decisionBroken,
                decisionCheckErrored: decisionErrored, taskOutcome: taskOutcome, decisionOutcome: decisionOutcome,
                editsApplied: agent.edits.map(\.path), filesRead: agent.filesRead, unreadEdits: agent.unreadEdits,
                retrievedPaths: retrieved?.paths ?? [], retrievedCharacters: retrieved?.characters ?? 0,
                seconds: agent.modelSeconds + (retrieved?.seconds ?? 0), retrieveSeconds: retrieved?.seconds ?? 0,
                modelCalls: agent.turns.count, promptTokens: agent.promptTokens, answerTokens: agent.answerTokens,
                parseFailures: agent.parseFailures, saidDontKnow: Grader.saidDontKnow(agent.finalText))
            records.append(record)
            writer.write(try encoder.encode(record))
            writer.write(Data("\n".utf8))

            var transcript = "SYSTEM\n\(Agent.system)\n"
            for (number, turn) in agent.turns.enumerated() {
                transcript += "\n===== TURN \(number + 1) PROMPT =====\n\(turn.prompt)\n\n===== TURN \(number + 1) REPLY =====\n\(turn.reply)\n"
            }
            transcript += "\n===== TESTS =====\n\(testOutput)\n"
            try transcript.write(to: transcripts.appendingPathComponent("\(session.id).txt"), atomically: true, encoding: .utf8)

            // Written from the brief alone, once per session, so search and walk file the very same notes.
            if let vault, holdsDiscussion(brief) {
                if writtenNotes[session.id] == nil {
                    let answer = try await answerer.answer(system: Agent.notesSystem, user: Agent.notesPrompt(brief: brief)) { _ in }
                    writtenNotes[session.id] = answer.text
                    let folder = results.appendingPathComponent(project.spec.name).appendingPathComponent("notes")
                    try files.createDirectory(at: folder, withIntermediateDirectories: true)
                    try answer.text.write(to: folder.appendingPathComponent("\(session.id).txt"), atomically: true, encoding: .utf8)
                }
                let day = Date(timeIntervalSince1970: 1_767_225_600 + Double(index) * 86_400)
                for note in NoteParser.parse(writtenNotes[session.id]!) { try vault.addNote(note.text, kind: note.kind, date: day) }
            }
        }
    }
    let table = summary(records)
    try table.write(to: results.appendingPathComponent("summary.txt"), atomically: true, encoding: .utf8)
    return records
}

/// Counts per mode. Setup sessions only establish decisions, so they are left out of the scored rows.
public func summary(_ records: [SessionRecord]) -> String {
    var lines = ["mode    scored  passed  decisions broken  decision check errored  no edit  avg files read  avg seconds"]
    for mode in ["none", "search", "walk"] {
        let scored = records.filter { $0.mode == mode && $0.category != Category.setup.rawValue }
        guard !scored.isEmpty else { continue }
        let changes = scored.filter { $0.kind == SessionKind.change.rawValue }
        let reads = Double(scored.map(\.filesRead.count).reduce(0, +)) / Double(scored.count)
        let seconds = scored.map(\.seconds).reduce(0, +) / Double(scored.count)
        lines.append(String(format: "%-7@ %6d  %6d  %16d  %22d  %7d  %14.1f  %11.1f", mode as NSString, scored.count,
                            scored.filter(\.taskPassed).count, scored.filter(\.decisionBroken).count,
                            scored.filter(\.decisionCheckErrored).count, changes.filter(\.editsApplied.isEmpty).count, reads, seconds))
    }
    lines.append("")
    lines.append("session by session (task passed / decision broken / files read / seconds)")
    for record in records {
        lines.append(String(format: "%-7@ %@ %-8@ %@ %@ %d %.1f", record.mode as NSString, record.session as NSString, record.category as NSString,
                            (record.taskPassed ? "pass" : "FAIL") as NSString, (record.decisionBroken ? "BROKE" : "kept ") as NSString,
                            record.filesRead.count, record.seconds))
    }
    return lines.joined(separator: "\n") + "\n"
}

public struct VerifyReport: Sendable {
    public var lines: [String] = []
    public var failures = 0
    mutating func check(_ ok: Bool, _ line: String) {
        lines.append((ok ? "ok    " : "WRONG ") + line)
        if !ok { failures += 1 }
    }
}

/// Proves a project can measure anything: the correct solution passes, the starting code doesn't, and each trap is caught.
public func verify(project: TrialProject, scratch: URL) throws -> VerifyReport {
    var report = VerifyReport()
    let files = FileManager.default
    let home = scratch.appendingPathComponent("verify-\(project.spec.name)")
    if files.fileExists(atPath: home.path) { try files.removeItem(at: home) }
    let sandbox = try PythonSandbox(scratch: home)
    let workspace = Workspace(url: sandbox.scratch.appendingPathComponent("workspace"))
    let hidden = sandbox.scratch.appendingPathComponent("hidden")
    try files.createDirectory(at: hidden, withIntermediateDirectories: true)

    func copied(_ session: SessionSpec) throws -> URL {
        let target = hidden.appendingPathComponent(session.id)
        if !files.fileExists(atPath: target.path) { try files.copyItem(at: project.tests(session), to: target) }
        return target
    }
    func run(_ session: SessionSpec, _ name: String) throws -> TestOutcome {
        try sandbox.run(tests: try copied(session), pattern: name, workspace: workspace.url).outcome
    }

    for (index, session) in project.spec.sessions.enumerated() {
        guard files.fileExists(atPath: project.folder(session).appendingPathComponent("brief.md").path) else {
            report.check(false, "\(session.id) has no brief.md")
            continue
        }
        switch session.kind {
        case .ask:
            let good = try Grader.ask(answer: session.referenceAnswer ?? "", mustContain: session.mustContain ?? [], mustNot: session.mustNot ?? [])
            report.check(good, "\(session.id) reference answer is accepted")
            if let wrong = session.wrongAnswer {
                let accepted = try Grader.ask(answer: wrong, mustContain: session.mustContain ?? [], mustNot: session.mustNot ?? [])
                report.check(!accepted, "\(session.id) wrong answer is rejected")
            }
        case .change:
            try workspace.reset(to: project, before: index)
            let before = try run(session, "test_task.py")
            report.check(!before.passed && before.ran > 0, "\(session.id) code before the task fails its task tests (\(describe(before)))")

            try workspace.reset(to: project, before: index + 1)
            let after = try run(session, "test_task.py")
            report.check(after.passed, "\(session.id) reference passes its task tests (\(describe(after)))")
            if hasTests(project.tests(session), "test_decisions.py") {
                let kept = try run(session, "test_decisions.py")
                report.check(kept.passed, "\(session.id) reference keeps the decisions (\(describe(kept)))")
            }
            if files.fileExists(atPath: project.trap(session).path) {
                try workspace.reset(to: project, before: index)
                try Workspace.overlay(from: project.trap(session), onto: workspace.url)
                let caught = try run(session, "test_decisions.py")
                report.check(caught.failures > 0, "\(session.id) trap is caught by a failed assertion (\(describe(caught)))")
            }
        }
    }

    try workspace.reset(to: project, before: project.spec.sessions.count)
    for session in project.spec.sessions where session.kind == .change {
        let task = try run(session, "test_task.py")
        report.check(task.passed, "\(session.id) task tests still pass on the final code (\(describe(task)))")
        if hasTests(project.tests(session), "test_decisions.py") {
            let kept = try run(session, "test_decisions.py")
            report.check(kept.passed, "\(session.id) decisions still hold on the final code (\(describe(kept)))")
        }
    }
    return report
}
