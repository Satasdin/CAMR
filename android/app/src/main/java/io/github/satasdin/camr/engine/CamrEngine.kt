package io.github.satasdin.camr.engine

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate

/** A memory the model read for one answer. */
data class Recalled(val noteId: Long, val kind: String, val title: String, val text: String, val similarity: Float, val bridged: Boolean)

sealed interface ChatEvent {
    data class Recall(val sources: List<Recalled>, val abstained: Boolean, val ms: Double, val conversationId: Long) : ChatEvent
    data class Token(val text: String) : ChatEvent
    data class Done(val turnId: Long, val answer: String, val grounded: Double?, val generationMs: Double, val savedToMemory: Boolean) : ChatEvent
}

/**
 * The CAMR read and write paths, ported from camr/memory (Python) to run on the phone:
 * verbatim chunking, duplicate screening, exact cosine kNN, gating (abstain + relevance margin),
 * entity bridging, greedy token budgeting, chat-as-memory and learning from approved answers.
 */
class CamrEngine(
    private val store: MemoryStore,
    private val embedder: Embedder,
    var tokenBudget: Int = 384,
    var minSimilarity: Float = 0.30f,   // USE cosines run lower than BGE's; see docs/ANDROID_ASSISTANT.md
    var margin: Float = 0.15f,
    var historyTurns: Int = 6,
    var rememberChat: Boolean = true,
) {
    private val remember = Regex("^\\s*(?:/remember|remember(?: that)?|note:)\\s*[:,-]?\\s*(.+)$", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))

    fun teach(text: String, title: String = "", kind: String = "note", docId: String? = null): Int {
        val chunks = Tokens.chunk(text.trim()).filter { Tokens.count(it) >= 3 }
        if (chunks.isEmpty()) return 0
        val withTitle = chunks.map { if (title.isNotBlank()) "$title: $it" else it }
        return store.insert(kind, docId ?: "$kind-${System.nanoTime()}", title, withTitle.map { it to embedder.embed(it) })
    }

    fun recall(question: String): Triple<List<Recalled>, String, Boolean> {
        val q = embedder.embed(question)
        val notes = store.notes()
        if (notes.isEmpty()) return Triple(emptyList(), "", true)
        val scored = notes.map { it to dot(q, it.vector) }.sortedByDescending { it.second }.take(20)
        val best = scored.first().second
        if (best < minSimilarity) return Triple(emptyList(), "", true)   // gating: memory would not help
        val eligible = scored.filter { it.second >= best - margin }.toMutableList()
        // entity bridging: a strong note that names another stored entity pulls that entity in
        val titles = store.titleIndex()
        val have = eligible.map { it.first.sourceId }.toMutableSet()
        val bridged = HashSet<Long>()
        if (titles.isNotEmpty()) for ((note, _) in eligible.take(3).toList()) {
            val lower = note.text.lowercase()
            for ((title, sids) in titles) if (lower.contains(title)) for (sid in sids) if (sid !in have) {
                notes.filter { it.sourceId == sid }.map { it to dot(q, it.vector) }.sortedByDescending { it.second }.take(2)
                    .forEach { eligible += it; bridged += it.first.id }
                have += sid
            }
        }
        // greedy packing under the token budget
        val admitted = ArrayList<Pair<Note, Float>>()
        var used = 0
        for (p in eligible) {
            if (used + p.first.tokens > tokenBudget) break
            admitted += p; used += p.first.tokens
        }
        val meta = store.sourceMeta(admitted.map { it.first.sourceId }.toSet())
        val recalled = admitted.map { (n, s) ->
            val (kind, title) = meta[n.sourceId] ?: ("note" to "")
            Recalled(n.id, kind, title, n.text, s, n.id in bridged)
        }
        return Triple(recalled, admitted.joinToString("\n") { "- " + it.first.text }, false)
    }

    fun ask(question: String, conversationId: Long?, llm: Llm): Flow<ChatEvent> = flow {
        val conv = conversationId ?: store.newConversation(question.ifBlank { "New chat" })
        remember.matchEntire(question.trim())?.let { m ->
            val saved = teach(m.groupValues[1]) > 0
            val msg = if (saved) "Got it. I'll remember that." else "I already had that in memory."
            emit(ChatEvent.Recall(emptyList(), false, 0.0, conv))
            emit(ChatEvent.Token(msg))
            val id = store.logTurn(TurnRow(0, conv, question, msg, "[]", false, null, 0.0, 0.0, null))
            emit(ChatEvent.Done(id, msg, null, 0.0, saved))
            return@flow
        }
        val t0 = System.nanoTime()
        val (sources, context, abstained) = recall(question)
        val retrievalMs = (System.nanoTime() - t0) / 1e6
        emit(ChatEvent.Recall(sources, abstained, retrievalMs, conv))
        val history = store.transcript(conv, historyTurns).joinToString("\n") { "User: ${it.question}\nAssistant: ${it.answer}" }
        val prompt = PROMPT.format(context.ifBlank { "(no relevant notes)" }, history.ifBlank { "(none)" }, question)
        val g0 = System.nanoTime()
        val sb = StringBuilder()
        llm.stream(prompt).collect { piece -> sb.append(piece); emit(ChatEvent.Token(piece)) }
        val answer = sb.toString().trim()
        val grounded = groundedShare(answer, context)
        val genMs = (System.nanoTime() - g0) / 1e6
        val id = store.logTurn(TurnRow(0, conv, question, answer, toJson(sources), abstained, grounded, retrievalMs, genMs, null))
        val saved = rememberChat && teach("On ${LocalDate.now()} the user said: $question", kind = "chat", docId = "chat-$id") > 0
        emit(ChatEvent.Done(id, answer, grounded, genMs, saved))
    }.flowOn(Dispatchers.Default)

    /** Thumbs up: the approved answer becomes memory, so the model improves without changing weights. */
    fun feedback(turnId: Long, helpful: Boolean) {
        val qa = store.setFeedback(turnId, if (helpful) 1 else -1)
        if (helpful && qa != null) teach("Q: ${qa.first}\nA: ${qa.second}", kind = "learned", docId = "learned-$turnId")
    }

    companion object {
        const val PROMPT = """You are a personal assistant running privately on the user's own phone.
Below are notes from the user's personal memory that may be relevant, then the recent conversation.
Use the notes when they answer the question and prefer them over your own assumptions.
If the notes do not contain the answer and you are not sure, say you don't know rather than guessing.
Answer concisely.

### Notes from memory
%s

### Recent conversation
%s

### User
%s

### Assistant
"""
        private val stop = setOf("a", "an", "the", "and", "or", "of", "to", "in", "on", "at", "for", "is", "are", "was", "it",
            "this", "that", "i", "you", "my", "your", "what", "when", "where", "who", "how", "do", "does", "not", "be", "with")

        fun dot(a: FloatArray, b: FloatArray): Float {
            var s = 0f
            for (i in a.indices) s += a[i] * b[i]
            return s
        }

        fun groundedShare(answer: String, notes: String): Double? {
            val words = Regex("[A-Za-z0-9][A-Za-z0-9'\\-.,:]*").findAll(answer).map { it.value.trim('.', ',', ':').lowercase() }
                .filter { it.isNotEmpty() && it !in stop }.toList()
            if (words.isEmpty() || notes.isBlank()) return null
            val hay = notes.lowercase()
            return words.count { hay.contains(it) }.toDouble() / words.size
        }

        fun toJson(s: List<Recalled>): String = JSONArray(s.map {
            JSONObject().put("noteId", it.noteId).put("kind", it.kind).put("title", it.title).put("text", it.text)
                .put("similarity", it.similarity.toDouble()).put("bridged", it.bridged)
        }).toString()

        fun fromJson(json: String): List<Recalled> {
            val a = JSONArray(json)
            return (0 until a.length()).map { a.getJSONObject(it) }.map {
                Recalled(it.getLong("noteId"), it.getString("kind"), it.getString("title"), it.getString("text"),
                    it.getDouble("similarity").toFloat(), it.getBoolean("bridged"))
            }
        }
    }
}
