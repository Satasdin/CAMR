import Foundation

/// The copy of a project a simulated developer agent works in. Nothing hidden from the agent lives inside it.
public struct Workspace: Sendable {
    public let url: URL
    public init(url: URL) { self.url = url }

    /// Copies every file of `source` over `destination`, replacing what is there.
    public static func overlay(from source: URL, onto destination: URL) throws {
        let files = FileManager.default
        guard files.fileExists(atPath: source.path) else { return }
        guard let walker = files.enumerator(at: source, includingPropertiesForKeys: [.isRegularFileKey]) else { return }
        let base = source.standardizedFileURL.path + "/"
        for case let item as URL in walker where (try? item.resourceValues(forKeys: [.isRegularFileKey]))?.isRegularFile == true {
            let full = item.standardizedFileURL.path
            guard full.hasPrefix(base) else { continue }
            let target = destination.appendingPathComponent(String(full.dropFirst(base.count)))
            try files.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
            if files.fileExists(atPath: target.path) { try files.removeItem(at: target) }
            try files.copyItem(at: item, to: target)
        }
    }

    /// Starting code plus the correct solution of every earlier session, so one failure cannot cascade into the next.
    public func reset(to project: TrialProject, before index: Int) throws {
        let files = FileManager.default
        if files.fileExists(atPath: url.path) { try files.removeItem(at: url) }
        try files.createDirectory(at: url, withIntermediateDirectories: true)
        try Self.overlay(from: project.base, onto: url)
        for session in project.spec.sessions.prefix(index) {
            try Self.overlay(from: project.reference(session), onto: url)
        }
    }

    public func files() -> [String] {
        let manager = FileManager.default
        guard let walker = manager.enumerator(at: url, includingPropertiesForKeys: [.isRegularFileKey]) else { return [] }
        let base = url.standardizedFileURL.path + "/"
        var out: [String] = []
        for case let item as URL in walker {
            if item.lastPathComponent == "__pycache__" {
                walker.skipDescendants()
                continue
            }
            guard (try? item.resourceValues(forKeys: [.isRegularFileKey]))?.isRegularFile == true else { continue }
            let full = item.standardizedFileURL.path
            if full.hasPrefix(base), !item.lastPathComponent.hasPrefix(".") { out.append(String(full.dropFirst(base.count))) }
        }
        return out.sorted()
    }

    public func read(_ path: String) -> String? {
        try? String(contentsOf: url.appendingPathComponent(path), encoding: .utf8)
    }

    public func apply(_ edits: [FileEdit]) throws {
        for edit in edits {
            let target = url.appendingPathComponent(edit.path)
            try FileManager.default.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
            try edit.content.write(to: target, atomically: true, encoding: .utf8)
        }
    }
}

/// Runs hidden tests against code a model wrote: no network, and nothing written outside this run's scratch folder.
public struct PythonSandbox: Sendable {
    public let scratch: URL
    public let timeout: TimeInterval

    public init(scratch: URL, timeout: TimeInterval = 20) throws {
        try FileManager.default.createDirectory(at: scratch, withIntermediateDirectories: true)
        guard let real = realpath(scratch.path, nil) else { throw TrialFailure("cannot resolve \(scratch.path)") }
        defer { free(real) }
        let path = String(cString: real)
        guard !path.contains("\"") else { throw TrialFailure("scratch path may not contain a quote") }
        self.scratch = URL(fileURLWithPath: path)
        self.timeout = timeout
    }

    var profile: String {
        """
        (version 1)
        (allow default)
        (deny network*)
        (deny file-write*)
        (allow file-write* (subpath "\(scratch.path)") (subpath "/private/var/folders") (literal "/dev/null"))
        """
    }

    private final class Flag: @unchecked Sendable { var raised = false }

    public func run(tests: URL, pattern: String, workspace: URL) throws -> (outcome: TestOutcome, output: String) {
        let temporary = scratch.appendingPathComponent("tmp")
        try FileManager.default.createDirectory(at: temporary, withIntermediateDirectories: true)
        let log = temporary.appendingPathComponent(UUID().uuidString + ".log")
        guard FileManager.default.createFile(atPath: log.path, contents: nil) else { throw TrialFailure("cannot write \(log.path)") }
        defer { try? FileManager.default.removeItem(at: log) }
        let handle = try FileHandle(forWritingTo: log)
        defer { try? handle.close() }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/sandbox-exec")
        process.arguments = ["-p", profile, "/usr/bin/python3", "-B", "-m", "unittest", "discover", "-s", tests.path, "-p", pattern]
        process.currentDirectoryURL = workspace
        process.environment = ["PYTHONPATH": workspace.path, "PYTHONDONTWRITEBYTECODE": "1", "HOME": scratch.path,
                               "TMPDIR": temporary.path, "PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"]
        process.standardInput = FileHandle.nullDevice
        process.standardOutput = handle
        process.standardError = handle
        try process.run()

        let timedOut = Flag()
        let stop = DispatchWorkItem {
            timedOut.raised = true
            process.terminate()
            DispatchQueue.global().asyncAfter(deadline: .now() + 1) { kill(process.processIdentifier, SIGKILL) }
        }
        DispatchQueue.global().asyncAfter(deadline: .now() + timeout, execute: stop)
        process.waitUntilExit()
        stop.cancel()

        let output = (try? String(contentsOf: log, encoding: .utf8)) ?? ""
        return (Grader.outcome(output: output, exitCode: process.terminationStatus, timedOut: timedOut.raised), output)
    }
}
