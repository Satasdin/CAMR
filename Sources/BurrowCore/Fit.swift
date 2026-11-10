import Foundation

/// What the engine knows about the model it is serving. A model that reads slowly, or is small, is given less
/// to read: more excerpts than a model can use make its answers slower and no better.
public struct ModelProfile: Codable, Sendable, Equatable {
    public var model: String
    /// The longest prompt the model says it accepts, in tokens.
    public var contextTokens: Int
    public var billions: Double
    /// Tokens the model reads and writes each second on this machine. Zero until measured.
    public var readsPerSecond: Double
    public var writesPerSecond: Double
    public var charactersPerToken: Double
    /// How much of the vault to show it, in characters.
    public var budgetCharacters: Int
    /// The prompt size to ask the model runner for, in tokens.
    public var windowTokens: Int
    public var measured: Bool

    /// The share of the window kept back for the rules, a skill, the question and the answer.
    public static let reserveTokens = 2_600
    /// Characters per token for dense code, the least a vault's text is likely to give.
    public static let densest = 2.6

    /// The most a model of a given size is shown, however fast it reads.
    static func ceiling(billions: Double) -> Int {
        switch billions {
        case ..<3: return 8_000
        case ..<6: return 12_000
        case ..<20: return 24_000
        default: return 32_000
        }
    }

    /// Chooses the budget and the window from what was measured.
    /// - Parameter patience: how many seconds of reading are acceptable before the first word.
    public static func fitted(model: String, contextTokens: Int, billions: Double, readsPerSecond: Double, writesPerSecond: Double,
                              charactersPerToken: Double, patience: Double = 8) -> ModelProfile {
        let perToken = charactersPerToken > 1 ? charactersPerToken : 3.5
        var budget = ceiling(billions: billions)
        if readsPerSecond > 0 { budget = min(budget, Int(readsPerSecond * patience * perToken)) }
        // It must also fit in the prompt the model accepts.
        budget = min(budget, Int(Double(max(contextTokens - reserveTokens, 1_000)) * perToken))
        budget = max(budget, 4_000)
        // The window is sized as if everything shown were code, the densest case, so a prompt is never cut off.
        let needed = Int(Double(budget) / min(perToken, densest)) + reserveTokens
        let window = [4_096, 8_192, 16_384, 32_768].first { $0 >= needed } ?? 32_768
        return ModelProfile(model: model, contextTokens: contextTokens, billions: billions, readsPerSecond: readsPerSecond,
                            writesPerSecond: writesPerSecond, charactersPerToken: perToken, budgetCharacters: budget,
                            windowTokens: min(window, max(contextTokens, 4_096)), measured: readsPerSecond > 0)
    }

    /// What to assume about a model nobody has measured: the budget every model had before fitting existed.
    public static func unmeasured(_ model: String) -> ModelProfile {
        ModelProfile(model: model, contextTokens: 8_192, billions: 0, readsPerSecond: 0, writesPerSecond: 0, charactersPerToken: 3.5,
                     budgetCharacters: 12_000, windowTokens: 8_192, measured: false)
    }

    public var budget: Budget {
        var budget = Budget()
        budget.characters = budgetCharacters
        // A larger budget is spread over more starting files, not spent going deeper into four.
        budget.entryFiles = max(4, budgetCharacters / 3_000)
        return budget
    }
}

extension Ollama {
    /// Measures a model once: asks what it is, then times it reading a page and writing a line.
    public func measure(model: String, patience: Double = 8) async throws -> ModelProfile {
        let facts = try await describe(model: model)
        // Half prose and half code, because code takes more tokens for the same number of characters and a vault holds both.
        let prose = "The vault keeps notes, documents and code in plain files, and the index beside them can always be rebuilt. "
        let code = "func total(_ items: [Item], taxRate: Double = 0.16) -> Double { items.reduce(0) { $0 + $1.price * (1 + taxRate) } }\n"
        let page = String(repeating: prose, count: 30) + "\n" + String(repeating: code, count: 30)
        let probe = answerer(model: model, contextWords: 4_096, longestAnswer: 48)
        // The first call also loads the model, so it is thrown away.
        _ = try await probe.answer(system: "Reply with the single word: ready.", user: "Are you there?", onWord: { _ in })
        let result = try await probe.answer(system: "Reply with one short sentence saying what the text is about.", user: page, onWord: { _ in })
        let reads = result.promptSeconds > 0 ? Double(result.promptTokens) / result.promptSeconds : 0
        let writes = result.answerSeconds > 0 ? Double(result.answerTokens) / result.answerSeconds : 0
        let perToken = result.promptTokens > 0 ? Double(page.count) / Double(result.promptTokens) : 3.5
        return ModelProfile.fitted(model: model, contextTokens: facts.contextTokens, billions: facts.billions, readsPerSecond: reads,
                                   writesPerSecond: writes, charactersPerToken: perToken, patience: patience)
    }
}

extension Vault {
    private var profilesFile: URL { store.appendingPathComponent("models.json") }

    public func profiles() -> [String: ModelProfile] {
        guard let data = try? Data(contentsOf: profilesFile) else { return [:] }
        return (try? JSONDecoder().decode([String: ModelProfile].self, from: data)) ?? [:]
    }

    public func keep(_ profile: ModelProfile) throws {
        var known = profiles()
        known[profile.model] = profile
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        try encoder.encode(known).write(to: profilesFile, options: .atomic)
    }

    /// The profile for a model, measuring it the first time it is used with this vault.
    public func profile(for model: String, ollama: Ollama) async -> ModelProfile {
        if let known = profiles()[model] { return known }
        guard let measured = try? await ollama.measure(model: model) else { return .unmeasured(model) }
        try? keep(measured)
        return measured
    }
}
