import Foundation

/// One argument a tool takes.
public struct ToolParameter: Sendable {
    public enum Kind: String, Sendable { case string, integer }
    public let name: String
    public let kind: Kind
    public let description: String
    public let required: Bool
    public let choices: [String]

    init(_ name: String, _ kind: Kind, _ description: String, required: Bool = false, choices: [String] = []) {
        self.name = name
        self.kind = kind
        self.description = description
        self.required = required
        self.choices = choices
    }
}

/// One tool, described once. The MCP server and the terminal chat both read this list, so they can't drift apart.
public struct ToolDefinition: Sendable {
    public let name: String
    public let description: String
    public let parameters: [ToolParameter]
    /// False for the tools that write: a new note, or a turn added to a saved conversation.
    public let readOnly: Bool

    /// The JSON Schema for the arguments, which MCP and Ollama both use.
    public var inputSchema: [String: Any] {
        var properties: [String: Any] = [:]
        for parameter in parameters {
            var field: [String: Any] = ["type": parameter.kind.rawValue, "description": parameter.description]
            if !parameter.choices.isEmpty { field["enum"] = parameter.choices }
            properties[parameter.name] = field
        }
        return ["type": "object", "properties": properties, "required": parameters.filter(\.required).map(\.name)]
    }
}

extension VaultTools {
    public static let definitions: [ToolDefinition] = [
        ToolDefinition(
            name: "vault_search",
            description: "Search the user's private vault of notes and linked code by words and meaning. Use this first for any question about their projects or notes. Returns ranked excerpts with file names and line numbers, including notes and code linked to the best matches.",
            parameters: [
                ToolParameter("query", .string, "What to look for, in plain words or exact code names.", required: true),
                ToolParameter("folder", .string, "Only look inside this vault folder or linked folder. Leave it out to search everything."),
            ],
            readOnly: true),
        ToolDefinition(
            name: "vault_read",
            description: "Read a file or note from the vault, with line numbers. Use it when an excerpt from vault_search is not enough.",
            parameters: [
                ToolParameter("path", .string, "The vault path, exactly as vault_search or vault_list gave it.", required: true),
                ToolParameter("start_line", .integer, "First line to read. Defaults to 1."),
                ToolParameter("line_count", .integer, "How many lines to read. Defaults to 200, at most 400."),
            ],
            readOnly: true),
        ToolDefinition(
            name: "vault_links",
            description: "Show what a file or note links to and what links back to it.",
            parameters: [ToolParameter("path", .string, "The vault path of the file or note.", required: true)],
            readOnly: true),
        ToolDefinition(
            name: "vault_list",
            description: "List what is directly inside a vault folder: its subfolders and files. Leave the folder out for the top of the vault.",
            parameters: [ToolParameter("folder", .string, "The folder to list. Leave it out for the top of the vault.")],
            readOnly: true),
        ToolDefinition(
            name: "vault_folders",
            description: "List the folders in the vault and which of them are linked code folders. Use a name from here as the folder for vault_search or vault_ask.",
            parameters: [],
            readOnly: true),
        ToolDefinition(
            name: "vault_remember",
            description: "Keep a fact or decision as a new Markdown note in the vault. Only use it when the user asks you to remember a fact or states a decision worth keeping. It is not for saving the conversation: use vault_session_log for that. It only ever creates a new note.",
            parameters: [
                ToolParameter("text", .string, "What to keep, in full sentences. Name the files it is about.", required: true),
                ToolParameter("kind", .string, "What sort of note this is.", required: true, choices: ["decision", "rejected", "bug", "convention", "note"]),
            ],
            readOnly: false),
        ToolDefinition(
            name: "vault_ask",
            description: "Have the local model answer a question from the vault. Returns its answer and the files it read. It runs on this Mac and can take a while.",
            parameters: [
                ToolParameter("question", .string, "The question.", required: true),
                ToolParameter("folder", .string, "Only use this vault folder or linked folder. Leave it out to use everything."),
                ToolParameter("model", .string, "An installed Ollama model name. Leave it out for the default."),
            ],
            readOnly: true),
        ToolDefinition(
            name: "vault_prepare",
            description: "Get ready for a task in one call. Burrow decides whether the user's vault is needed, picks the excerpts worth reading, and returns a short method for this kind of task if it has one. Call this before starting any task about the user's notes, documents or code.",
            parameters: [
                ToolParameter("task", .string, "The task or question, in the user's words.", required: true),
                ToolParameter("folder", .string, "Only use this vault folder or linked folder. Leave it out to use everything."),
            ],
            readOnly: true),
        ToolDefinition(
            name: "vault_pack",
            description: "Read a whole folder or module of the vault at once, in parts that each fit your context: a map of the folder, its main notes, then every file with line numbers. Use it to go through a codebase or a set of documents end to end. The same folder always gives the same text, so a model server that saved it can load it instead of reading it again.",
            parameters: [
                ToolParameter("folder", .string, "The vault folder or linked folder, as vault_folders or vault_list gave it.", required: true),
                ToolParameter("part", .integer, "Which part to read, from 1. Defaults to 1; the text says how many parts there are."),
            ],
            readOnly: true),
        ToolDefinition(
            name: "vault_session_list",
            description: "List the saved conversations in this vault, newest first: their ids, which models answered, and how they began. Use it to find a conversation to pick up.",
            parameters: [],
            readOnly: true),
        ToolDefinition(
            name: "vault_session_resume",
            description: "Pick up a saved conversation that another model or program started. Returns what was asked and settled, the files already read, and the last turns. Call it when the user asks to continue, resume or carry on an earlier conversation.",
            parameters: [ToolParameter("session", .string, "The session id from vault_session_list, or last for the most recent one.", required: true)],
            readOnly: true),
        ToolDefinition(
            name: "vault_session_log",
            description: "Save this conversation: add one question and your answer to it, so another model or program can carry it on later. This is the tool for 'save', 'log' or 'keep' this conversation or this answer. Use new as the session the first time. Call it after each answer when the user wants the conversation kept.",
            parameters: [
                ToolParameter("session", .string, "The session id, or new to start one.", required: true),
                ToolParameter("question", .string, "What the user asked, in their words.", required: true),
                ToolParameter("answer", .string, "Your answer, in full or closely summarised.", required: true),
                ToolParameter("model", .string, "Your model name, so the next model knows who answered."),
                ToolParameter("files", .string, "Vault paths you read for this answer, separated by commas."),
            ],
            readOnly: false),
    ]

    /// The tools a chat model is offered: everything but the session tools, which the chat handles itself, and
    /// `vault_pack`, whose parts are sized for a whole window and would crowd out a chat's small search allowance.
    public static var forChat: [ToolDefinition] { definitions.filter { !$0.name.hasPrefix("vault_session") && $0.name != "vault_pack" } }
}
