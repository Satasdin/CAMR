import XCTest
@testable import BurrowCore

final class EngineTests: XCTestCase {
    private var root: URL!

    override func setUpWithError() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent("burrow-engine-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws { try? FileManager.default.removeItem(at: root) }

    private func write(_ path: String, _ text: String) throws {
        let url = root.appendingPathComponent(path)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try text.write(to: url, atomically: true, encoding: .utf8)
    }

    /// Words decide the direction, so a test can say exactly how close two texts are.
    private struct Axes: Embedder {
        func embed(_ texts: [String]) async throws -> [[Float]] {
            texts.map { text in
                let lowered = text.lowercased()
                return [lowered.contains("rent") ? 1 : 0, lowered.contains("eggs") || lowered.contains("arithmetic") ? 1 : 0,
                        lowered.contains("haiku") ? 1 : 0, 0.05]
            }
        }
    }

    private final class Script: Answerer, @unchecked Sendable {
        var replies: [String]
        var systems: [String] = []
        var users: [String] = []
        init(_ replies: [String]) { self.replies = replies }
        func answer(system: String, user: String, onWord: @escaping @Sendable (String) -> Void) async throws -> ChatResult {
            systems.append(system)
            users.append(user)
            let text = replies.isEmpty ? "" : replies.removeFirst()
            return ChatResult(text: text, secondsToFirstWord: 0, totalSeconds: 1, promptTokens: 10, answerTokens: 5)
        }
    }

    // MARK: The vector block

    func testNearestAgreesWithComparingEveryVectorByHand() {
        var generator = SystemRandomNumberGenerator()
        let vectors = (0..<300).map { _ in (0..<16).map { _ in Float.random(in: -1...1, using: &generator) } }
        let ids = Array(100..<400)
        let index = VectorIndex(VectorIndex.encode(ids: ids, vectors: vectors, generation: 3), generation: 3)!
        let query = (0..<16).map { _ in Float.random(in: -1...1, using: &generator) }
        var scored: [(id: Int, score: Float)] = []
        for (id, vector) in zip(ids, vectors) { scored.append((id, Vault.cosine(query, vector))) }
        scored.sort { (a: (id: Int, score: Float), b: (id: Int, score: Float)) -> Bool in a.score == b.score ? a.id < b.id : a.score > b.score }
        let byHand: [Int] = scored.map { $0.id }
        XCTAssertEqual(index.nearest(to: query, limit: 10), Array(byHand.prefix(10)))
        XCTAssertEqual(index.nearest(to: query, limit: 300), byHand)
        XCTAssertEqual(index.similarity(of: scored[0].id, to: query)!, scored[0].score, accuracy: 0.0001)
    }

    func testABlockFromAnotherStateOfTheVaultIsRefused() {
        let data = VectorIndex.encode(ids: [1, 2], vectors: [[1, 0], [0, 1]], generation: 4)
        XCTAssertNotNil(VectorIndex(data, generation: 4))
        XCTAssertNil(VectorIndex(data, generation: 5))
        XCTAssertNil(VectorIndex(data.dropLast(3), generation: 4))
    }

    func testVectorsOfAnotherWidthOrOfNoLengthAreLeftOut() {
        let index = VectorIndex(VectorIndex.encode(ids: [1, 2, 3], vectors: [[1, 0], [0, 0], [1, 2, 3]], generation: 0), generation: 0)!
        XCTAssertEqual(index.ids, [1])
    }

    func testAChangedFileIsFoundByMeaningWithoutReopeningTheVault() async throws {
        try write("notes.md", "The rent is due on the first.")
        let vault = try Vault(project: root, everything: true)
        try await vault.refresh(embedder: Axes())
        var found = try await vault.retrieve("rent", mode: .search, embedder: Axes())
        XCTAssertEqual(found.paths, ["notes.md"])
        XCTAssertTrue(FileManager.default.fileExists(atPath: vault.store.appendingPathComponent("vectors.bin").path))
        try write("poem.md", "A haiku about the long rains.")
        try await vault.refresh(embedder: Axes())
        found = try await vault.retrieve("haiku", mode: .search, embedder: Axes())
        XCTAssertEqual(found.paths.first, "poem.md")
    }

    // MARK: Deciding

    func testTheVaultStaysOutOfAQuestionItKnowsNothingAbout() async throws {
        try write("notes.md", "The rent is due on the first.")
        let vault = try Vault(project: root, everything: true)
        try await vault.refresh(embedder: Axes())
        let near = try await vault.brief("When is the rent due?", embedder: Axes())
        XCTAssertEqual(near.route.mode, .search)
        XCTAssertFalse(near.retrieved.excerpts.isEmpty)
        let far = try await vault.brief("Write a haiku", embedder: Axes())
        XCTAssertEqual(far.route.mode, .none)
        XCTAssertTrue(far.retrieved.excerpts.isEmpty)
        XCTAssertEqual(far.system, Asking.withoutMemory)
    }

    func testCodeIsWalkedAndDocumentsAreSearched() async throws {
        try write("app/billing.py", "from app import ledger\n\ndef rent_total():\n    return ledger.sum('rent')\n")
        try write("app/ledger.py", "def sum(kind):\n    return 0\n")
        let vault = try Vault(project: root, everything: true)
        try await vault.refresh(embedder: Axes())
        let brief = try await vault.brief("How is the rent total worked out?", embedder: Axes())
        XCTAssertEqual(brief.route.mode, .walk)
        XCTAssertTrue(brief.retrieved.paths.contains("app/ledger.py"))
    }

    // MARK: Skills

    func testASkillIsReadFromItsFile() {
        let skill = Skill.parse("---\nkind: skill\nwhen: sums and arithmetic\nneeds: vault\nfallback: documents\n---\n# Add up\n\n1. Add.\n", path: "Skills/Add up.md")!
        XCTAssertEqual(skill.name, "Add up")
        XCTAssertEqual(skill.when, "sums and arithmetic")
        XCTAssertTrue(skill.needsVault)
        XCTAssertEqual(skill.fallbackFor, "documents")
        XCTAssertTrue(skill.body.hasPrefix("# Add up"))
        XCTAssertNil(Skill.parse("---\nwhen: x\n---\n", path: "Skills/empty.md"))
    }

    func testStarterSkillsAreAddedOnceAndNeverOverwritten() throws {
        let vault = try Vault(project: root, everything: true)
        XCTAssertEqual(try vault.installStarterSkills().count, StarterSkills.all.count)
        let edited = vault.skillsFolder.appendingPathComponent("Summarise.md")
        try "---\nwhen: mine\n---\n# Mine\n\nMy own way.\n".write(to: edited, atomically: true, encoding: .utf8)
        XCTAssertEqual(try vault.installStarterSkills(), [])
        XCTAssertTrue(vault.skills().contains { $0.name == "Mine" })
        XCTAssertEqual(vault.skills().count, StarterSkills.all.count)
    }

    func testEveryStarterSkillParsesAndSaysWhenItApplies() {
        for (file, text) in StarterSkills.all {
            let skill = Skill.parse(text, path: "Skills/" + file)
            XCTAssertNotNil(skill, file)
            XCTAssertTrue(skill!.when.contains("Examples:"), file)
            XCTAssertLessThan(skill!.body.count, Skills.longest, file)
        }
        XCTAssertEqual(Set(StarterSkills.all.values.compactMap { Skill.parse($0, path: "x.md")?.fallbackFor }), ["documents", "code"])
    }

    func testSkillsAreNeverShownAsFactsAboutTheVault() async throws {
        try write("notes.md", "The rent is due on the first.")
        try write("Skills/Rent.md", "---\nwhen: anything about rent\n---\n# Rent\n\nAlways mention the rent.\n")
        let vault = try Vault(project: root, everything: true)
        try await vault.refresh(embedder: Axes())
        let found = try await vault.retrieve("rent", mode: .walk, embedder: Axes())
        XCTAssertEqual(found.paths, ["notes.md"])
    }

    func testATaskThatNeedsNoVaultGetsItsSkillAndNoExcerpts() async throws {
        try write("notes.md", "The rent is due on the first.")
        try write("Skills/Sums.md", "---\nwhen: arithmetic with eggs\n---\n# Sums\n\nShow each step.\n")
        try write("Skills/Papers.md", "---\nwhen: what the rent note says\nneeds: vault\nfallback: documents\n---\n# Papers\n\nQuote the line.\n")
        let vault = try Vault(project: root, everything: true)
        try await vault.refresh(embedder: Axes())
        let sum = try await vault.brief("How many eggs are left?", embedder: Axes())
        XCTAssertEqual(sum.route.mode, .none)
        XCTAssertEqual(sum.skill?.name, "Sums")
        XCTAssertTrue(sum.system.contains("Show each step."))
        let paper = try await vault.brief("When is the rent due?", embedder: Axes())
        XCTAssertEqual(paper.skill?.name, "Papers")
        var off = EngineSettings()
        off.useSkills = false
        let plain = try await vault.brief("When is the rent due?", embedder: Axes(), settings: off)
        XCTAssertNil(plain.skill)
        XCTAssertEqual(plain.system, Asking.memoryRules)
    }

    // MARK: Checking

    private let shown = [Excerpt(path: "app/billing.py", startLine: 1, endLine: 20, text: "", reason: .search, isNote: false)]

    func testCitationsAreReadInBothTheirForms() {
        let found = Engine.citations(in: "It is set in app/billing.py:12 and again in billing.py at line 14. See ledger.py, lines 3.", shown: shown)
        XCTAssertEqual(found.map(\.line), [12, 14, 3])
        XCTAssertEqual(found.map(\.shown), [true, true, false])
        XCTAssertEqual(found[2].path, "ledger.py")
    }

    func testAPathInQuotesOrBackticksIsStillRead() {
        let found = Engine.citations(in: "From `app/billing.py` at line 5, and (app/billing.py):7.", shown: shown)
        XCTAssertEqual(found.map(\.line), [5, 7])
        XCTAssertTrue(found.allSatisfy(\.shown))
    }

    func testTheRuleOnReasonsIsGivenOnlyWhenWhyIsAsked() {
        XCTAssertTrue(Asking.asksWhy("Why is the retry limit three?"))
        XCTAssertTrue(Asking.asksWhy("What was the reason for dropping the cache?"))
        XCTAssertFalse(Asking.asksWhy("Which table stores the links?"))
        XCTAssertFalse(Asking.asksWhy("What does the whyte function return?"))
        XCTAssertTrue(Asking.rules(for: "Why three?").contains(Asking.reasons))
        XCTAssertFalse(Asking.rules(for: "Which table?").contains(Asking.reasons))
    }

    func testALineOutsideWhatWasShownIsNotVerified() {
        XCTAssertEqual(Engine.citations(in: "See app/billing.py:40.", shown: shown).map(\.shown), [false])
        XCTAssertTrue(Engine.citations(in: "The ratio is 3:2 and version 1.2:3 is fine.", shown: shown).allSatisfy { !$0.shown })
    }

    func testAnAnswerThatCitesWhatItWasNotShownIsAskedAgain() async throws {
        try write("app/billing.py", "def rent_total():\n    return 3\n")
        let vault = try Vault(project: root, everything: true)
        try await vault.refresh(embedder: Axes())
        let model = Script(["The rent is set in app/secret.py:9.", "The rent total is 3, in app/billing.py:2."])
        let reply = try await vault.engage("What is the rent total?", profile: .unmeasured("test"), embedder: Axes(), answerer: model)
        XCTAssertTrue(reply.retried)
        XCTAssertEqual(reply.result.text, "The rent total is 3, in app/billing.py:2.")
        XCTAssertTrue(reply.unverified.isEmpty)
        XCTAssertTrue(model.users[1].contains("app/secret.py:9"))
        XCTAssertEqual(reply.result.promptTokens, 20)
    }

    func testTheFirstAnswerIsKeptWhenTheSecondIsNoBetter() async throws {
        try write("app/billing.py", "def rent_total():\n    return 3\n")
        let vault = try Vault(project: root, everything: true)
        try await vault.refresh(embedder: Axes())
        let model = Script(["First, from app/secret.py:9.", "Second, from app/other.py:1 and app/more.py:2."])
        let reply = try await vault.engage("What is the rent total?", profile: .unmeasured("test"), embedder: Axes(), answerer: model)
        XCTAssertTrue(reply.retried)
        XCTAssertEqual(reply.result.text, "First, from app/secret.py:9.")
        XCTAssertEqual(reply.unverified.count, 1)
    }

    func testAGroundedAnswerIsNotAskedAgain() async throws {
        try write("app/billing.py", "def rent_total():\n    return 3\n")
        let vault = try Vault(project: root, everything: true)
        try await vault.refresh(embedder: Axes())
        let model = Script(["It returns 3, app/billing.py:2."])
        let reply = try await vault.engage("What is the rent total?", profile: .unmeasured("test"), embedder: Axes(), answerer: model)
        XCTAssertFalse(reply.retried)
        XCTAssertEqual(model.users.count, 1)
    }

    // MARK: Fitting

    func testASlowOrSmallModelIsShownLess() {
        let small = ModelProfile.fitted(model: "s", contextTokens: 32_768, billions: 1.7, readsPerSecond: 3_000, writesPerSecond: 90, charactersPerToken: 4)
        let large = ModelProfile.fitted(model: "l", contextTokens: 32_768, billions: 12, readsPerSecond: 3_000, writesPerSecond: 40, charactersPerToken: 4)
        let slow = ModelProfile.fitted(model: "x", contextTokens: 32_768, billions: 12, readsPerSecond: 200, writesPerSecond: 10, charactersPerToken: 4)
        XCTAssertEqual(small.budgetCharacters, 8_000)
        XCTAssertEqual(large.budgetCharacters, 24_000)
        XCTAssertEqual(slow.budgetCharacters, 6_400)
        XCTAssertLessThanOrEqual(large.budgetCharacters / 4 + ModelProfile.reserveTokens, large.windowTokens)
        XCTAssertGreaterThan(large.budget.entryFiles, small.budget.entryFiles)
    }

    func testTheBudgetNeverExceedsWhatTheModelAccepts() {
        let tight = ModelProfile.fitted(model: "t", contextTokens: 4_096, billions: 30, readsPerSecond: 9_000, writesPerSecond: 50, charactersPerToken: 4)
        XCTAssertLessThanOrEqual(tight.budgetCharacters, (4_096 - ModelProfile.reserveTokens) * 4)
        XCTAssertEqual(tight.windowTokens, 4_096)
        XCTAssertEqual(ModelProfile.unmeasured("u").budgetCharacters, Budget().characters)
    }

    func testAProfileIsKeptWithTheVault() throws {
        let vault = try Vault(project: root, everything: true)
        let profile = ModelProfile.fitted(model: "m", contextTokens: 8_192, billions: 4, readsPerSecond: 1_000, writesPerSecond: 80, charactersPerToken: 4)
        try vault.keep(profile)
        XCTAssertEqual(try Vault(project: root, everything: true).profiles()["m"], profile)
    }

    // MARK: Learning

    func testOnlyWhatThePersonSaidIsKept() {
        let reply = """
        {"kind": "decision", "text": "Receipts are numbered per branch, not globally.", "quote": "number receipts per branch"}
        {"kind": "convention", "text": "All money is stored in cents.", "quote": "the assistant thinks cents are best"}
        not json at all
        {"kind": "strange", "text": "The nightly job must not run before two in the morning.", "quote": "never before 2am"}
        """
        let lessons = Learning.lessons(from: reply, said: ["Let's number   receipts per branch from now on.", "And the nightly job: never before 2am."])
        XCTAssertEqual(lessons.map(\.kind), [.decision, .note])
        XCTAssertEqual(lessons.first?.text, "Receipts are numbered per branch, not globally.")
        XCTAssertEqual(Learning.lessons(from: "NONE", said: ["hello"]), [])
    }

    func testLearningWritesANoteThatTheNextQuestionFinds() async throws {
        try write("notes.md", "Nothing yet.")
        let vault = try Vault(project: root, everything: true)
        try await vault.refresh(embedder: Axes())
        let model = Script(["{\"kind\": \"decision\", \"text\": \"The rent is collected weekly, not monthly.\", \"quote\": \"collect the rent weekly\"}"])
        let written = try await vault.learn(from: [(question: "From now on collect the rent weekly.", answer: "Understood.")], answerer: model, embedder: Axes())
        XCTAssertEqual(written.count, 1)
        let found = try await vault.retrieve("How often is the rent collected?", mode: .search, embedder: Axes())
        XCTAssertTrue(found.excerpts.contains { $0.text.contains("collected weekly") })
        let text = try String(contentsOf: root.appendingPathComponent(written[0]), encoding: .utf8)
        XCTAssertTrue(text.contains("kind: decision"))
        // Told the same thing again, it does not write it twice.
        let again = Script(["{\"kind\": \"decision\", \"text\": \"The rent is collected weekly, not monthly.\", \"quote\": \"collect the rent weekly\"}"])
        let second = try await vault.learn(from: [(question: "Remember: collect the rent weekly.", answer: "Yes.")], answerer: again, embedder: Axes())
        XCTAssertEqual(second, [])
    }
}
