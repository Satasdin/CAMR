package io.github.satasdin.camr.engine

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.time.Instant

/** A stored note with its embedding (one SQLite file in app-private storage, like the desktop engine). */
data class Note(val id: Long, val sourceId: Long, val text: String, val tokens: Int, val vector: FloatArray)

data class SourceItem(val id: Long, val kind: String, val title: String, val added: String, val text: String)

data class TurnRow(
    val id: Long, val conversationId: Long, val question: String, val answer: String,
    val sourcesJson: String, val abstained: Boolean, val grounded: Double?, val retrievalMs: Double,
    val generationMs: Double, val feedback: Int?,
)

class MemoryStore(context: Context) : SQLiteOpenHelper(context, "camr-memory.sqlite", null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE source (source_id INTEGER PRIMARY KEY, kind TEXT NOT NULL, doc_id TEXT NOT NULL UNIQUE,
               title TEXT, added_at TEXT NOT NULL)"""
        )
        db.execSQL(
            """CREATE TABLE note (note_id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES source(source_id)
               ON DELETE CASCADE, text TEXT NOT NULL, tokens INTEGER NOT NULL, checksum TEXT NOT NULL UNIQUE,
               embedding BLOB NOT NULL)"""
        )
        db.execSQL("CREATE TABLE conversation (conversation_id INTEGER PRIMARY KEY, title TEXT NOT NULL, updated_at TEXT NOT NULL)")
        db.execSQL(
            """CREATE TABLE turn (turn_id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL, at TEXT NOT NULL,
               question TEXT NOT NULL, answer TEXT NOT NULL, sources_json TEXT NOT NULL, abstained INTEGER NOT NULL,
               grounded REAL, retrieval_ms REAL, generation_ms REAL, feedback INTEGER)"""
        )
        db.execSQL("CREATE INDEX idx_note_source ON note(source_id)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit

    override fun onConfigure(db: SQLiteDatabase) {
        db.setForeignKeyConstraintsEnabled(true)
    }

    @Volatile private var cache: List<Note>? = null
    @Volatile private var titleCache: Map<String, List<Long>>? = null

    /** All notes in memory, cached; exact cosine search over them is fast at personal scale (tens of thousands). */
    fun notes(): List<Note> = cache ?: synchronized(this) {
        val out = ArrayList<Note>()
        readableDatabase.rawQuery("SELECT note_id, source_id, text, tokens, embedding FROM note", null).use { c ->
            while (c.moveToNext()) out += Note(c.getLong(0), c.getLong(1), c.getString(2), c.getInt(3), fromBlob(c.getBlob(4)))
        }
        cache = out
        out
    }

    /** Source title -> source ids, for entity bridging (a note that names a title pulls in that source). */
    fun titleIndex(): Map<String, List<Long>> = titleCache ?: synchronized(this) {
        val m = HashMap<String, MutableList<Long>>()
        readableDatabase.rawQuery("SELECT source_id, title FROM source WHERE title IS NOT NULL AND length(title) >= 4", null).use { c ->
            while (c.moveToNext()) m.getOrPut(c.getString(1).lowercase()) { mutableListOf() } += c.getLong(0)
        }
        titleCache = m
        m
    }

    fun sourceMeta(ids: Collection<Long>): Map<Long, Pair<String, String>> {
        if (ids.isEmpty()) return emptyMap()
        val out = HashMap<Long, Pair<String, String>>()
        readableDatabase.rawQuery(
            "SELECT source_id, kind, coalesce(title,'') FROM source WHERE source_id IN (${ids.joinToString(",")})", null
        ).use { c -> while (c.moveToNext()) out[c.getLong(0)] = c.getString(1) to c.getString(2) }
        return out
    }

    /** Insert one source and its chunks in a single transaction. Returns notes accepted (duplicates are skipped). */
    fun insert(kind: String, docId: String, title: String, chunks: List<Pair<String, FloatArray>>): Int {
        val db = writableDatabase
        var accepted = 0
        db.beginTransaction()
        try {
            val sid = db.insertWithOnConflict("source", null, ContentValues().apply {
                put("kind", kind); put("doc_id", docId); put("title", title.ifBlank { null }); put("added_at", Instant.now().toString())
            }, SQLiteDatabase.CONFLICT_IGNORE)
            if (sid == -1L) return 0
            for ((text, vec) in chunks) {
                val id = db.insertWithOnConflict("note", null, ContentValues().apply {
                    put("source_id", sid); put("text", text); put("tokens", Tokens.count(text))
                    put("checksum", checksum(text)); put("embedding", toBlob(vec))
                }, SQLiteDatabase.CONFLICT_IGNORE)
                if (id != -1L) accepted++
            }
            if (accepted == 0) db.delete("source", "source_id=?", arrayOf(sid.toString()))  // all duplicates
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
            invalidate()
        }
        return accepted
    }

    fun forget(sourceId: Long): Int {
        val n = writableDatabase.delete("note", "source_id=?", arrayOf(sourceId.toString()))
        writableDatabase.delete("source", "source_id=?", arrayOf(sourceId.toString()))
        invalidate()
        return n
    }

    fun sources(kind: String? = null, query: String = ""): List<SourceItem> {
        val out = ArrayList<SourceItem>()
        val where = if (kind != null) "WHERE s.kind=?" else ""
        val args = if (kind != null) arrayOf(kind) else null
        readableDatabase.rawQuery(
            """SELECT s.source_id, s.kind, coalesce(s.title,''), s.added_at, group_concat(n.text, ' ')
               FROM source s LEFT JOIN note n USING(source_id) $where GROUP BY s.source_id ORDER BY s.source_id DESC""", args
        ).use { c ->
            while (c.moveToNext()) out += SourceItem(c.getLong(0), c.getString(1), c.getString(2), c.getString(3), c.getString(4) ?: "")
        }
        return if (query.isBlank()) out else out.filter { (it.title + " " + it.text).contains(query, ignoreCase = true) }
    }

    fun stats(): Map<String, Any> {
        val db = readableDatabase
        val byKind = LinkedHashMap<String, Int>()
        db.rawQuery("SELECT s.kind, count(n.note_id) FROM note n JOIN source s USING(source_id) GROUP BY s.kind", null).use { c ->
            while (c.moveToNext()) byKind[c.getString(0)] = c.getInt(1)
        }
        var turns = 0; var withMem = 0; var up = 0
        db.rawQuery("SELECT count(*), sum(sources_json != '[]'), sum(feedback = 1) FROM turn", null).use { c ->
            if (c.moveToFirst()) { turns = c.getInt(0); withMem = c.getInt(1); up = c.getInt(2) }
        }
        return mapOf("notes" to byKind.values.sum(), "byKind" to byKind, "turns" to turns, "withMemory" to withMem, "helpful" to up)
    }

    // ---------------------------------------------------------------- conversations
    fun newConversation(title: String): Long = writableDatabase.insert("conversation", null, ContentValues().apply {
        put("title", title.take(60)); put("updated_at", Instant.now().toString())
    })

    fun conversations(): List<Pair<Long, String>> {
        val out = ArrayList<Pair<Long, String>>()
        readableDatabase.rawQuery("SELECT conversation_id, title FROM conversation ORDER BY updated_at DESC", null).use { c ->
            while (c.moveToNext()) out += c.getLong(0) to c.getString(1)
        }
        return out
    }

    fun deleteConversation(id: Long) {
        writableDatabase.delete("turn", "conversation_id=?", arrayOf(id.toString()))
        writableDatabase.delete("conversation", "conversation_id=?", arrayOf(id.toString()))
    }

    fun logTurn(t: TurnRow): Long {
        val id = writableDatabase.insert("turn", null, ContentValues().apply {
            put("conversation_id", t.conversationId); put("at", Instant.now().toString()); put("question", t.question)
            put("answer", t.answer); put("sources_json", t.sourcesJson); put("abstained", if (t.abstained) 1 else 0)
            t.grounded?.let { put("grounded", it) }; put("retrieval_ms", t.retrievalMs); put("generation_ms", t.generationMs)
        })
        writableDatabase.execSQL("UPDATE conversation SET updated_at=? WHERE conversation_id=?", arrayOf(Instant.now().toString(), t.conversationId))
        return id
    }

    fun transcript(conversationId: Long, limit: Int = 1000): List<TurnRow> {
        val out = ArrayList<TurnRow>()
        readableDatabase.rawQuery(
            """SELECT turn_id, conversation_id, question, answer, sources_json, abstained, grounded, retrieval_ms,
               generation_ms, feedback FROM turn WHERE conversation_id=? ORDER BY turn_id DESC LIMIT ?""",
            arrayOf(conversationId.toString(), limit.toString())
        ).use { c ->
            while (c.moveToNext()) out += TurnRow(
                c.getLong(0), c.getLong(1), c.getString(2), c.getString(3), c.getString(4), c.getInt(5) == 1,
                if (c.isNull(6)) null else c.getDouble(6), c.getDouble(7), c.getDouble(8), if (c.isNull(9)) null else c.getInt(9)
            )
        }
        return out.reversed()
    }

    fun setFeedback(turnId: Long, value: Int): Pair<String, String>? {
        writableDatabase.execSQL("UPDATE turn SET feedback=? WHERE turn_id=?", arrayOf(value, turnId))
        readableDatabase.rawQuery("SELECT question, answer FROM turn WHERE turn_id=?", arrayOf(turnId.toString())).use { c ->
            return if (c.moveToFirst()) c.getString(0) to c.getString(1) else null
        }
    }

    private fun invalidate() { cache = null; titleCache = null }

    companion object {
        fun toBlob(v: FloatArray): ByteArray =
            ByteBuffer.allocate(v.size * 4).order(ByteOrder.LITTLE_ENDIAN).apply { asFloatBuffer().put(v) }.array()

        fun fromBlob(b: ByteArray): FloatArray {
            val fb = ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
            return FloatArray(fb.remaining()).also { fb.get(it) }
        }

        fun checksum(text: String): String = MessageDigest.getInstance("SHA-256")
            .digest(text.lowercase().replace(Regex("\\s+"), " ").trim().toByteArray())
            .joinToString("") { "%02x".format(it) }
    }
}

/** The same model-agnostic word/punctuation token count the desktop engine budgets with. */
object Tokens {
    private val re = Regex("\\w+|[^\\w\\s]")
    fun count(text: String): Int = re.findAll(text).count()

    /** Split text into chunks of about [size] tokens with [overlap] tokens of overlap (verbatim write policy). */
    fun chunk(text: String, size: Int = 120, overlap: Int = 16): List<String> {
        val words = text.split(Regex("\\s+")).filter { it.isNotBlank() }
        if (words.size <= size) return listOf(words.joinToString(" ")).filter { it.isNotBlank() }
        val out = ArrayList<String>()
        var i = 0
        while (i < words.size) {
            out += words.subList(i, minOf(words.size, i + size)).joinToString(" ")
            if (i + size >= words.size) break
            i += size - overlap
        }
        return out
    }
}
