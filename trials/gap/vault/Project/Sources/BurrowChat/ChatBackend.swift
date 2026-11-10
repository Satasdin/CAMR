import BurrowCore
import BurrowTools
import Foundation

public struct ModelToolCall: @unchecked Sendable {
    public let name: String
    public let arguments: [String: Any]
    public init(name: String, arguments: [String: Any]) {
        self.name = name
        self.arguments = arguments
    }
}

public struct ModelReply: @unchecked Sendable {
    public let text: String
    public let toolCalls: [ModelToolCall]
    public let promptTokens: Int
    public init(text: String, toolCalls: [ModelToolCall], promptTokens: Int = 0) {
        self.text = text
        self.toolCalls = toolCalls
        self.promptTokens = promptTokens
    }
}

public struct ChatProblem: Error, CustomStringConvertible {
    public let description: String
}

/// Whatever can take messages and offer tools. Tests use a stand-in.
public protocol ChatBackend {
    var model: String { get }
    func reply(messages: [[String: Any]], tools: [[String: Any]]?, onWord: @escaping (String) -> Void) async throws -> ModelReply
}

/// Hides a model's private reasoning as it arrives. It keeps to the same rule as the rest of Burrow: nothing before `</think>` is shown.
public struct ThinkFilter {
    private var text = ""
    private var shown = ""
    public init() {}

    static func visible(_ text: String) -> String {
        if let end = text.range(of: "</think>", options: .backwards) { return String(text[end.upperBound...].drop { $0.isWhitespace }) }
        let start = String(text.drop { $0.isWhitespace })
        return start.hasPrefix("<think>") || "<think>".hasPrefix(start) ? "" : start
    }

    /// Takes the next piece from the model and returns the new text a person should see.
    public mutating func add(_ word: String) -> String {
        text += word
        let visible = Self.visible(text)
        guard visible.count > shown.count, visible.hasPrefix(shown) else { return "" }
        let fresh = String(visible.dropFirst(shown.count))
        shown = visible
        return fresh
    }
}

/// Ollama's `/api/chat` with its `tools` field.
public struct OllamaChat: ChatBackend {
    public let model: String
    public let contextWords: Int
    public let base: URL

    public init(model: String = Ollama.defaultModel, contextWords: Int = 16_384, base: URL = URL(string: "http://127.0.0.1:11434")!) {
        self.model = model
        self.contextWords = contextWords
        self.base = base
    }

    /// Ollama's form of a tool.
    public static func schema(of tool: ToolDefinition) -> [String: Any] {
        ["type": "function", "function": ["name": tool.name, "description": tool.description, "parameters": tool.inputSchema]]
    }

    public func reply(messages: [[String: Any]], tools: [[String: Any]]?, onWord: @escaping (String) -> Void) async throws -> ModelReply {
        var body: [String: Any] = [
            "model": model, "stream": true, "think": false, "messages": messages,
            "options": ["temperature": 0, "seed": 7, "num_ctx": contextWords, "num_predict": 2048],
        ]
        if let tools { body["tools"] = tools }
        var request = URLRequest(url: base.appendingPathComponent("api/chat"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        request.timeoutInterval = 900

        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        if let http = response as? HTTPURLResponse, http.statusCode != 200 {
            var said = ""
            for try await line in bytes.lines { said += line }
            throw ChatProblem(description: "Ollama answered \(http.statusCode) for \(model): \(said.prefix(200))")
        }
        var filter = ThinkFilter()
        var text = ""
        var calls: [ModelToolCall] = []
        var promptTokens = 0
        for try await line in bytes.lines {
            guard let data = line.data(using: .utf8), let part = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { continue }
            if let problem = part["error"] as? String { throw ChatProblem(description: problem) }
            if let message = part["message"] as? [String: Any] {
                if let word = message["content"] as? String, !word.isEmpty {
                    let fresh = filter.add(word)
                    if !fresh.isEmpty {
                        text += fresh
                        onWord(fresh)
                    }
                }
                for raw in message["tool_calls"] as? [[String: Any]] ?? [] {
                    guard let function = raw["function"] as? [String: Any], let name = function["name"] as? String else { continue }
                    calls.append(ModelToolCall(name: name, arguments: Self.arguments(function["arguments"])))
                }
            }
            if part["done"] as? Bool == true { promptTokens = part["prompt_eval_count"] as? Int ?? 0 }
        }
        return ModelReply(text: text, toolCalls: calls, promptTokens: promptTokens)
    }

    private static func arguments(_ value: Any?) -> [String: Any] {
        if let object = value as? [String: Any] { return object }
        if let text = value as? String, let data = text.data(using: .utf8), let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] { return object }
        return [:]
    }
}
