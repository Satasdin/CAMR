import Foundation
import SQLite3

/// A small wrapper over SQLite. The index is disposable: it can always be rebuilt from the files.
private let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

public struct DatabaseError: Error, CustomStringConvertible {
    public let description: String
}

enum Value: Equatable {
    case int(Int64), real(Double), text(String), blob(Data), null

    var int: Int? { if case let .int(v) = self { return Int(v) } else { return nil } }
    var real: Double? {
        switch self {
        case let .real(v): return v
        case let .int(v): return Double(v)
        default: return nil
        }
    }
    var text: String? { if case let .text(v) = self { return v } else { return nil } }
    var blob: Data? { if case let .blob(v) = self { return v } else { return nil } }
}

final class Database {
    private var handle: OpaquePointer?
    private var prepared: [String: OpaquePointer] = [:]
    /// An async call on `Vault` does not stay on its caller's actor, so one connection can be reached from several
    /// threads at once. Recursive so that a transaction can hold it while its own statements take it again.
    private let lock = NSRecursiveLock()

    /// Runs `work` with the connection to itself.
    func locked<T>(_ work: () throws -> T) rethrows -> T {
        lock.lock()
        defer { lock.unlock() }
        return try work()
    }

    init(path: String) throws {
        guard sqlite3_open(path, &handle) == SQLITE_OK else {
            throw DatabaseError(description: "cannot open \(path)")
        }
        // The app, the terminal and an MCP client can all have one vault open, so wait for a turn instead of failing.
        sqlite3_busy_timeout(handle, 8000)
        try execute("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;")
    }

    deinit {
        prepared.values.forEach { sqlite3_finalize($0) }
        sqlite3_close(handle)
    }

    private var lastError: String { String(cString: sqlite3_errmsg(handle)) }

    func execute(_ sql: String) throws {
        lock.lock()
        defer { lock.unlock() }
        guard sqlite3_exec(handle, sql, nil, nil, nil) == SQLITE_OK else {
            throw DatabaseError(description: "\(lastError) in: \(sql.prefix(120))")
        }
    }

    private func statement(_ sql: String, _ arguments: [Value]) throws -> OpaquePointer {
        var found = prepared[sql]
        if found == nil {
            guard sqlite3_prepare_v2(handle, sql, -1, &found, nil) == SQLITE_OK, found != nil else {
                throw DatabaseError(description: "\(lastError) in: \(sql.prefix(120))")
            }
            prepared[sql] = found
        }
        let statement = found!
        sqlite3_reset(statement)
        sqlite3_clear_bindings(statement)
        for (offset, value) in arguments.enumerated() {
            let place = Int32(offset + 1)
            switch value {
            case let .int(v): sqlite3_bind_int64(statement, place, v)
            case let .real(v): sqlite3_bind_double(statement, place, v)
            case let .text(v): sqlite3_bind_text(statement, place, v, -1, transient)
            case let .blob(v): _ = v.withUnsafeBytes { sqlite3_bind_blob(statement, place, $0.baseAddress, Int32(v.count), transient) }
            case .null: sqlite3_bind_null(statement, place)
            }
        }
        return statement
    }

    func run(_ sql: String, _ arguments: [Value] = []) throws {
        lock.lock()
        defer { lock.unlock() }
        let statement = try statement(sql, arguments)
        defer { sqlite3_reset(statement) }
        let code = sqlite3_step(statement)
        guard code == SQLITE_DONE || code == SQLITE_ROW else {
            throw DatabaseError(description: "\(lastError) in: \(sql.prefix(120))")
        }
    }

    func rows(_ sql: String, _ arguments: [Value] = []) throws -> [[Value]] {
        lock.lock()
        defer { lock.unlock() }
        let statement = try statement(sql, arguments)
        defer { sqlite3_reset(statement) }
        var out: [[Value]] = []
        while true {
            let code = sqlite3_step(statement)
            if code == SQLITE_DONE { return out }
            guard code == SQLITE_ROW else {
                throw DatabaseError(description: "\(lastError) in: \(sql.prefix(120))")
            }
            out.append((0..<sqlite3_column_count(statement)).map { column(statement, $0) })
        }
    }

    private func column(_ statement: OpaquePointer, _ index: Int32) -> Value {
        switch sqlite3_column_type(statement, index) {
        case SQLITE_INTEGER: return .int(sqlite3_column_int64(statement, index))
        case SQLITE_FLOAT: return .real(sqlite3_column_double(statement, index))
        case SQLITE_TEXT: return .text(String(cString: sqlite3_column_text(statement, index)))
        case SQLITE_BLOB:
            let size = Int(sqlite3_column_bytes(statement, index))
            guard size > 0, let bytes = sqlite3_column_blob(statement, index) else { return .blob(Data()) }
            return .blob(Data(bytes: bytes, count: size))
        default: return .null
        }
    }

    var lastInsertedRow: Int { Int(sqlite3_last_insert_rowid(handle)) }

    func transaction(_ work: () throws -> Void) throws {
        lock.lock()
        defer { lock.unlock() }
        try execute("BEGIN IMMEDIATE")
        do {
            try work()
            try execute("COMMIT")
        } catch {
            try? execute("ROLLBACK")
            throw error
        }
    }
}
