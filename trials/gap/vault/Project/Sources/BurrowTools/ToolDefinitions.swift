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
    /// False only for the one tool that adds to the vault.
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
            description: "Keep something as a new Markdown note in the vault. Only use it when the user asks to remember something or states a decision worth keeping. It only ever creates a new note.",
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
    ]
}
