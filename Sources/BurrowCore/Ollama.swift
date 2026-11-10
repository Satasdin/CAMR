import Foundation

public struct ChatResult: Sendable {
    public let text: String
    public let secondsToFirstWord: Double
    public let totalSeconds: Double
    public let promptTokens: Int
    public let answerTokens: Int
    /// How long the model spent reading the prompt and writing the answer, as the model runner reports them.
    public var promptSeconds: Double = 0
    public var answerSeconds: Double = 0

    public init(text: String, secondsToFirstWord: Double, totalSeconds: Double, promptTokens: Int, answerTokens: Int,
                promptSeconds: Double = 0, answerSeconds: Double = 0) {
        self.text = text
        self.secondsToFirstWord = secondsToFirstWord
        self.totalSeconds = totalSeconds
        self.promptTokens = promptTokens
        self.answerTokens = answerTokens
        self.promptSeconds = promptSeconds
        self.answerSeconds = answerSeconds
    }
}

public struct OllamaError: Error, CustomStringConvertible {
    public let description: String
}

/// Whatever can turn text into vectors. Tests use a stand-in.
public protocol Embedder: Sendable {
    func embed(_ texts: [String]) async throws -> [[Float]]
}

/// Whatever can answer. Tests use a stand-in.
public protocol Answerer: Sendable {
    func answer(system: String, user: String, onWord: @escaping @Sendable (String) -> Void) async throws -> ChatResult
}

/// Removes a model's private reasoning from what the developer sees.
enum Thinking {
    private static let opening = "<think>"
    private static let closing = "</think>"

    static func visible(_ text: String) -> String {
        if let end = text.range(of: closing, options: .backwards) {
            return String(text[end.upperBound...]).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        let start = String(text.drop { $0.isWhitespace })
        if start.hasPrefix(opening) || opening.hasPrefix(start) { return "" }
        return start
    }
}

/// The only way Burrow reaches a model: Ollama on this machine.
public struct Ollama: Sendable {
    public static let embeddingModel = "qwen3-embedding:0.6b"
    public static let defaultModel = "qwen3:4b-instruct-2507-q4_K_M"
    public let base: URL

    public init(base: URL = URL(string: "http://127.0.0.1:11434")!) { self.base = base }

    private static func session() -> URLSession {
        let setup = URLSessionConfiguration.ephemeral
        setup.timeoutIntervalForRequest = 900
        setup.timeoutIntervalForResource = 3600
        return URLSession(configuration: setup)
    }

    private func request(_ path: String, _ body: [String: Any]) throws -> URLRequest {
        var request = URLRequest(url: base.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return request
    }

    public func models() async throws -> [String] {
        let (data, _) = try await Self.session().data(from: base.appendingPathComponent("api/tags"))
        let root = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        return (root?["models"] as? [[String: Any]] ?? []).compactMap { $0["name"] as? String }
    }

    public func embedder(model: String = Ollama.embeddingModel) -> some Embedder { OllamaEmbedder(ollama: self, model: model) }
    public func answerer(model: String = Ollama.defaultModel, contextWords: Int = 8192, longestAnswer: Int = 2048) -> some Answerer {
        OllamaAnswerer(ollama: self, model: model, contextWords: contextWords, longestAnswer: longestAnswer)
    }

    /// What a model says about itself: the longest prompt it accepts, and its size in billions of parameters.
    public func describe(model: String) async throws -> (contextTokens: Int, billions: Double) {
        let call = try request("api/show", ["model": model])
        let (data, response) = try await Self.session().data(for: call)
        try check(response, data)
        let root = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        let info = root["model_info"] as? [String: Any] ?? [:]
        let context = info.first { $0.key.hasSuffix(".context_length") }?.value as? Int ?? 8192
        var billions = (info["general.parameter_count"] as? Double).map { $0 / 1e9 } ?? 0
        if billions == 0, let size = (root["details"] as? [String: Any])?["parameter_size"] as? String {
            let number = Double(size.filter { $0.isNumber || $0 == "." }) ?? 0
            billions = size.uppercased().contains("M") ? number / 1000 : number
        }
        return (context, billions)
    }

    fileprivate func embed(model: String, inputs: [String]) async throws -> [[Float]] {
        // Every question needs the embedding model and it is small, so it is kept loaded between questions.
        let call = try request("api/embed", ["model": model, "input": inputs, "keep_alive": "30m"])
        let (data, response) = try await Self.session().data(for: call)
        try check(response, data)
        let root = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        guard let lists = root?["embeddings"] as? [[Double]], lists.count == inputs.count else {
            throw OllamaError(description: "Ollama returned no embeddings for \(model)")
        }
        return lists.map { $0.map(Float.init) }
    }

    fileprivate func chat(model: String, contextWords: Int, longestAnswer: Int = 2048, system: String, user: String,
                          onWord: @escaping @Sendable (String) -> Void) async throws -> ChatResult {
        // Qwen3 can ignore "think": false, and then reasons at length before answering. This is its own off switch.
        let content = model.lowercased().contains("qwen3") ? user + "\n\n/no_think" : user
        let call = try request("api/chat", [
            "model": model, "stream": true, "think": false,
            "messages": [["role": "system", "content": system], ["role": "user", "content": content]],
            "options": ["temperature": 0, "seed": 7, "num_ctx": contextWords, "num_predict": longestAnswer],
        ])
        let started = Date()
        var firstWord: Double?
        var text = ""
        var shown = ""
        var promptTokens = 0
        var answerTokens = 0
        var promptSeconds = 0.0
        var answerSeconds = 0.0
        let (bytes, response) = try await Self.session().bytes(for: call)
        if let http = response as? HTTPURLResponse, http.statusCode != 200 {
            throw OllamaError(description: "Ollama answered \(http.statusCode) for model \(model). Is it installed?")
        }
        for try await line in bytes.lines {
            guard let data = line.data(using: .utf8),
                  let part = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { continue }
            if let problem = part["error"] as? String { throw OllamaError(description: problem) }
            if let word = (part["message"] as? [String: Any])?["content"] as? String, !word.isEmpty {
                text += word
                let visible = Thinking.visible(text)
                if visible.count > shown.count, visible.hasPrefix(shown) {
                    if firstWord == nil { firstWord = Date().timeIntervalSince(started) }
                    onWord(String(visible.dropFirst(shown.count)))
                    shown = visible
                }
            }
            if part["done"] as? Bool == true {
                promptTokens = part["prompt_eval_count"] as? Int ?? 0
                answerTokens = part["eval_count"] as? Int ?? 0
                promptSeconds = (part["prompt_eval_duration"] as? Double ?? 0) / 1e9
                answerSeconds = (part["eval_duration"] as? Double ?? 0) / 1e9
            }
        }
        let total = Date().timeIntervalSince(started)
        return ChatResult(text: Thinking.visible(text), secondsToFirstWord: firstWord ?? total, totalSeconds: total,
                          promptTokens: promptTokens, answerTokens: answerTokens, promptSeconds: promptSeconds, answerSeconds: answerSeconds)
    }

    private func check(_ response: URLResponse, _ data: Data) throws {
        guard let http = response as? HTTPURLResponse, http.statusCode != 200 else { return }
        throw OllamaError(description: "Ollama answered \(http.statusCode): \(String(decoding: data.prefix(200), as: UTF8.self))")
    }
}

private struct OllamaEmbedder: Embedder {
    let ollama: Ollama
    let model: String
    func embed(_ texts: [String]) async throws -> [[Float]] { try await ollama.embed(model: model, inputs: texts) }
}

private struct OllamaAnswerer: Answerer {
    let ollama: Ollama
    let model: String
    let contextWords: Int
    let longestAnswer: Int
    func answer(system: String, user: String, onWord: @escaping @Sendable (String) -> Void) async throws -> ChatResult {
        try await ollama.chat(model: model, contextWords: contextWords, longestAnswer: longestAnswer, system: system, user: user, onWord: onWord)
    }
}
