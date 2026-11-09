import Foundation

public enum SessionKind: String, Codable, Sendable {
    case change  // the agent edits code and hidden tests judge it
    case ask     // the agent answers in words and fixed patterns judge it
}

public enum Category: String, Codable, Sendable {
    case setup    // establishes a decision; not scored for the later-task question
    case depends  // needs something decided in an earlier session
    case plain    // a control that needs no memory
    case unknown  // asks about something never recorded; the right answer is "I don't know"
}

public struct SessionSpec: Codable, Sendable {
    public let id: String
    public let kind: SessionKind
    public let category: Category
    public var mustContain: [String]?
    public var mustNot: [String]?
    public var referenceAnswer: String?
    public var wrongAnswer: String?

    enum CodingKeys: String, CodingKey {
        case id, kind, category
        case mustContain = "must_contain"
        case mustNot = "must_not"
        case referenceAnswer = "reference_answer"
        case wrongAnswer = "wrong_answer"
    }
}

public struct ProjectSpec: Codable, Sendable {
    public let name: String
    public let split: String
    public let sessions: [SessionSpec]
}

public struct TrialFailure: Error, CustomStringConvertible {
    public let description: String
    public init(_ description: String) { self.description = description }
}

/// One synthetic project on disk: its starting code, and each session's brief, hidden tests and correct solution.
public struct TrialProject: Sendable {
    public let root: URL
    public let spec: ProjectSpec

    public init(root: URL) throws {
        self.root = root.standardizedFileURL
        let data = try Data(contentsOf: self.root.appendingPathComponent("project.json"))
        spec = try JSONDecoder().decode(ProjectSpec.self, from: data)
        guard ["tune", "held"].contains(spec.split) else { throw TrialFailure("split must be tune or held, not \(spec.split)") }
    }

    public var base: URL { root.appendingPathComponent("base") }
    public func folder(_ session: SessionSpec) -> URL { root.appendingPathComponent("sessions").appendingPathComponent(session.id) }
    public func reference(_ session: SessionSpec) -> URL { folder(session).appendingPathComponent("reference") }
    public func trap(_ session: SessionSpec) -> URL { folder(session).appendingPathComponent("trap") }
    public func tests(_ session: SessionSpec) -> URL { folder(session).appendingPathComponent("tests") }

    public func brief(_ session: SessionSpec) throws -> String {
        try String(contentsOf: folder(session).appendingPathComponent("brief.md"), encoding: .utf8)
    }
}

/// A session's discussion is what the model is asked to file as notes afterwards.
public func holdsDiscussion(_ brief: String) -> Bool {
    brief.range(of: "## Discussion", options: .caseInsensitive) != nil
}
