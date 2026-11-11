import BurrowCore
import Foundation

/// The moments a coding AI loses its memory, handled by hooks so the model never has to pick the right tool for it.
/// Claude Code calls `burrow hook claude <vault>` with a JSON event on stdin; git calls `burrow hook git <vault>` after a commit.
public enum Hooks {
    /// Where the work happens, as the vault sees it: a linked folder (its name is the branch), or the vault itself.
    public struct Place: Sendable, Equatable {
        public let branch: String
        /// The folder on disk that vault paths under `prefix` live in.
        public let root: URL
        /// The vault path of `root`: the linked folder's name, or "" for the vault itself.
        public let prefix: String

        /// A file on disk as a vault path, or nil when it is outside this place.
        public func vaultPath(_ file: String) -> String? {
            let absolute = file.hasPrefix("/") ? file : root.appendingPathComponent(file).path
            let base = root.standardizedFileURL.path
            let standard = URL(fileURLWithPath: absolute).standardizedFileURL.path
            guard standard.hasPrefix(base + "/") else { return nil }
            let rest = String(standard.dropFirst(base.count + 1))
            return prefix.isEmpty ? rest : prefix + "/" + rest
        }
    }

    /// The place for a working folder: the linked folder that holds it, else the vault when it holds it, else nil.
    public static func place(for directory: URL, vaultRoot: URL, linked: [LinkedFolder]) -> Place? {
        let here = directory.standardizedFileURL.path
        for folder in linked {
            let base = folder.url.standardizedFileURL.path
            if here == base || here.hasPrefix(base + "/") {
                return Place(branch: (try? Ledger.branchName(folder.name)) ?? Ledger.defaultBranch, root: folder.url, prefix: folder.name)
            }
        }
        let base = vaultRoot.standardizedFileURL.path
        if here == base || here.hasPrefix(base + "/") { return Place(branch: Ledger.defaultBranch, root: vaultRoot, prefix: "") }
        return nil
    }

    /// What a Claude Code transcript says happened: the person's requests, the files edited, the plan's open items and the model.
    public struct Transcript: Sendable, Equatable {
        public var asked: [String] = []
        public var edited: [String] = []
        public var openTodos: [String] = []
        public var doneTodos: [String] = []
        public var model: String?
    }

    /// Reads Claude Code's JSON-lines transcript. Unknown lines are skipped, so a format change loses detail, never the hook.
    public static func readTranscript(_ text: String) -> Transcript {
        var out = Transcript()
        for line in text.split(separator: "\n") {
            guard let entry = try? JSONSerialization.jsonObject(with: Data(line.utf8)) as? [String: Any],
                  let message = entry["message"] as? [String: Any] else { continue }
            let role = message["role"] as? String ?? entry["type"] as? String
            let parts = message["content"] as? [[String: Any]] ?? []
            // Only what the person typed: not copies the program keeps of its requests, not tool results that ride in the user's turn.
            let typed = entry["type"] as? String == "user" && entry["isMeta"] as? Bool != true
                && !parts.contains { $0["type"] as? String == "tool_result" }
            if role == "user", typed {
                if let words = message["content"] as? String { remember(words, in: &out.asked) }
                for part in message["content"] as? [[String: Any]] ?? [] where part["type"] as? String == "text" {
                    if let words = part["text"] as? String { remember(words, in: &out.asked) }
                }
            }
            if role == "assistant" {
                if let model = message["model"] as? String, !model.hasPrefix("<") { out.model = model }
                for part in message["content"] as? [[String: Any]] ?? [] where part["type"] as? String == "tool_use" {
                    let input = part["input"] as? [String: Any] ?? [:]
                    switch part["name"] as? String {
                    case "Edit", "Write", "MultiEdit", "NotebookEdit":
                        if let path = (input["file_path"] ?? input["notebook_path"]) as? String, !out.edited.contains(path) { out.edited.append(path) }
                    case "TodoWrite":
                        let todos = input["todos"] as? [[String: Any]] ?? []
                        out.openTodos = todos.filter { $0["status"] as? String != "completed" }.compactMap { $0["content"] as? String }
                        out.doneTodos = todos.filter { $0["status"] as? String == "completed" }.compactMap { $0["content"] as? String }
                    default: break
                    }
                }
            }
        }
        return out
    }

    private static func remember(_ words: String, in list: inout [String]) {
        let text = words.trimmingCharacters(in: .whitespacesAndNewlines)
        // Skip what Claude Code itself puts in the user's turn: command output, reminders, interrupted markers.
        guard !text.isEmpty, !text.hasPrefix("<"), !text.hasPrefix("[Request interrupted") else { return }
        list.append(text)
    }

    /// Claude Code's session start: the Ledger's head for this place, as context the model sees before the first message.
    public static func sessionStart(ledger: Ledger, place: Place) -> String {
        let head = ledger.resume(branch: place.branch, characters: 2_400)
        let context = head + "\n\nThis comes from Burrow's Ledger. Before compaction and when the session ends, Burrow writes where you stopped. To keep a decision or fact, call burrow_commit."
        let reply: [String: Any] = ["hookSpecificOutput": ["hookEventName": "SessionStart", "additionalContext": context]]
        return String(data: (try? JSONSerialization.data(withJSONObject: reply)) ?? Data(), encoding: .utf8) ?? ""
    }

    /// Before compaction or at the end: a handoff commit, and the plan when the session kept one. Nothing when nothing happened.
    @discardableResult
    public static func checkpoint(ledger: Ledger, place: Place, transcript: Transcript, session: String, event: String) throws -> [LedgerCommit] {
        guard !transcript.asked.isEmpty || !transcript.edited.isEmpty else { return [] }
        let author = transcript.model ?? "claude-code"
        let files = transcript.edited.compactMap(place.vaultPath)
        let outside = transcript.edited.filter { place.vaultPath($0) == nil }
        var made: [LedgerCommit] = []
        if !transcript.openTodos.isEmpty {
            let plan = "Open: " + transcript.openTodos.prefix(6).joined(separator: "; ")
            let done = transcript.doneTodos.isEmpty ? "" : "Done: " + transcript.doneTodos.suffix(6).joined(separator: "; ")
            let latest = ledger.log(branch: place.branch, limit: 20).first { $0.kind == .plan }
            if latest?.message != String(plan.prefix(600)) {
                made.append(try ledger.commit(.plan, String(plan.prefix(600)), body: done, files: files, author: author,
                                              client: "claude-code", branch: place.branch, session: "claude-" + session))
            }
        }
        let when = event == "PreCompact" ? "before compacting" : "when the session ended"
        let last = transcript.asked.last.map { String($0.prefix(220)) } ?? "editing"
        var body = ["Asked: " + transcript.asked.suffix(4).map { String($0.prefix(160)) }.joined(separator: " | ")]
        if !files.isEmpty { body.append("Edited: " + files.suffix(10).joined(separator: ", ")) }
        if !outside.isEmpty { body.append("Outside the vault: \(outside.count) file\(outside.count == 1 ? "" : "s")") }
        made.append(try ledger.commit(.handoff, "Claude Code stopped \(when). Last asked: \(last)", body: body.joined(separator: "\n"),
                                      files: files, author: author, client: "claude-code", branch: place.branch, session: "claude-" + session))
        return made
    }

    /// After a git commit: a code commit in the Ledger, linked by git's id, citing the files it changed.
    @discardableResult
    public static func gitCommit(ledger: Ledger, place: Place, sha: String, subject: String, files: [String], author: String = "git") throws -> LedgerCommit? {
        guard !sha.isEmpty, !ledger.all().contains(where: { $0.sha == sha }) else { return nil }
        // Files come as absolute paths, or relative to the place's root.
        let paths = files.compactMap(place.vaultPath)
        return try ledger.commit(.code, String("\(sha.prefix(10)) \(subject)".prefix(600)), files: paths, author: author,
                                 client: "git", branch: place.branch, sha: sha)
    }
}
