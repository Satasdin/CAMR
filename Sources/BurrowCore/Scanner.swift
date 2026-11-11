import CryptoKit
import Foundation

/// Finds the text files of a project. Inside a git repository it asks git, so `.gitignore` is respected.
struct Scanner {
    static let skippedFolders: Set<String> = [
        ".git", ".burrow", ".obsidian", ".trash", ".Trash", ".build", ".swiftpm", "node_modules", "DerivedData", "build", "dist", "out", "target",
        "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache", ".idea", ".vscode", "vendor", "Pods", ".next",
    ]
    static let textExtensions: Set<String> = [
        "swift", "py", "js", "jsx", "ts", "tsx", "mjs", "cjs", "go", "rs", "java", "kt", "kts", "c", "h", "cc", "cpp", "hpp",
        "m", "mm", "rb", "php", "cs", "scala", "dart", "lua", "sh", "zsh", "bash", "sql", "html", "css", "scss", "vue",
        "svelte", "json", "yaml", "yml", "toml", "md", "markdown", "txt", "rst", "tex", "xml", "gradle", "cmake", "proto",
    ]
    static let namedTextFiles: Set<String> = ["Makefile", "Dockerfile", "README", "LICENSE", "Gemfile", "Rakefile"]
    static let largestFile = 1_000_000
    /// A small package.json is configuration worth reading. A large JSON file is data, and would drown the code.
    static let dataExtensions: Set<String> = ["json", "xml", "yaml", "yml", "txt"]
    static let largestDataFile = 32_000

    struct Found {
        let path: String
        let text: String
        let hash: String
    }

    static func wanted(_ path: String) -> Bool {
        let parts = path.split(separator: "/").map(String.init)
        guard let name = parts.last else { return false }
        if parts.dropLast().contains(where: { skippedFolders.contains($0) || $0.hasPrefix(".") }) { return false }
        if namedTextFiles.contains(name) { return true }
        return textExtensions.contains((name as NSString).pathExtension.lowercased()) || Extractor.handles(name)
    }

    /// Relative paths of every candidate file, sorted so that an index built twice comes out the same.
    static func paths(in root: URL) -> [String] {
        let fromGit = gitPaths(in: root)
        let all = fromGit ?? walk(root)
        return Array(Set(all.filter(wanted))).sorted()
    }

    private static func gitPaths(in root: URL) -> [String]? {
        guard FileManager.default.fileExists(atPath: root.appendingPathComponent(".git").path) else { return nil }
        let git = Process()
        git.executableURL = URL(fileURLWithPath: "/usr/bin/git")
        git.arguments = ["-C", root.path, "ls-files", "-co", "--exclude-standard", "-z"]
        let pipe = Pipe()
        git.standardOutput = pipe
        git.standardError = Pipe()
        guard (try? git.run()) != nil else { return nil }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        git.waitUntilExit()
        guard git.terminationStatus == 0 else { return nil }
        return data.split(separator: 0).map { String(decoding: $0, as: UTF8.self) }
    }

    private static func walk(_ given: URL) -> [String] {
        // The enumerator treats a starting folder that is a symbolic link as the link itself and finds nothing inside,
        // so a vault opened through a link (or a link to a code folder) is walked at its real location.
        let root = given.resolvingSymlinksInPath()
        let base = root.standardizedFileURL.path + "/"
        guard let walker = FileManager.default.enumerator(at: root, includingPropertiesForKeys: [.isDirectoryKey]) else { return [] }
        var out: [String] = []
        for case let url as URL in walker {
            if skippedFolders.contains(url.lastPathComponent),
               (try? url.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory == true {
                walker.skipDescendants()
                continue
            }
            let full = url.standardizedFileURL.path
            if full.hasPrefix(base) { out.append(String(full.dropFirst(base.count))) }
        }
        return out
    }

    /// Reads one file. Returns nil for anything too large, not UTF-8, or binary.
    static func read(_ path: String, in root: URL) -> Found? {
        let url = root.appendingPathComponent(path)
        // A shortcut inside the folder must not be a way to read something outside it.
        let home = root.resolvingSymlinksInPath().path + "/"
        guard url.resolvingSymlinksInPath().path.hasPrefix(home) else { return nil }
        if Extractor.handles(path) {
            guard let data = try? Data(contentsOf: url), data.count <= Extractor.largest else { return nil }
            let hash = digest(data)
            guard let text = Extractor.markdown(of: data, path: path, hash: hash) else { return nil }
            return Found(path: path, text: text, hash: hash)
        }
        let limit = dataExtensions.contains(url.pathExtension.lowercased()) ? largestDataFile : largestFile
        guard let data = try? Data(contentsOf: url), data.count <= limit, !data.contains(0),
              let text = String(data: data, encoding: .utf8) else { return nil }
        return Found(path: path, text: text, hash: digest(data))
    }

    static func digest(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }
}

/// A cluster is the folder a file lives in, limited to two levels so a deep tree stays readable on the Map.
func clusterName(of path: String) -> String {
    let folders = path.split(separator: "/").dropLast().prefix(2)
    return folders.isEmpty ? "(top level)" : folders.joined(separator: "/")
}
