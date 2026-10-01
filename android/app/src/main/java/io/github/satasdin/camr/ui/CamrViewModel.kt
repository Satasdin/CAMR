package io.github.satasdin.camr.ui

import android.app.Application
import android.content.Context
import android.net.Uri
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.github.satasdin.camr.engine.CamrEngine
import io.github.satasdin.camr.engine.ChatEvent
import io.github.satasdin.camr.engine.Llm
import io.github.satasdin.camr.engine.MemoryStore
import io.github.satasdin.camr.engine.OllamaLlm
import io.github.satasdin.camr.engine.OnDeviceEmbedder
import io.github.satasdin.camr.engine.OnDeviceLlm
import io.github.satasdin.camr.engine.Recalled
import io.github.satasdin.camr.engine.SourceItem
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

data class Message(
    val user: Boolean,
    val text: String,
    val sources: List<Recalled> = emptyList(),
    val abstained: Boolean = false,
    val recalling: Boolean = false,
    val streaming: Boolean = false,
    val turnId: Long? = null,
    val grounded: Double? = null,
    val retrievalMs: Double = 0.0,
    val generationMs: Double = 0.0,
    val feedback: Int? = null,
    val saved: Boolean = false,
)

class CamrViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("camr", Context.MODE_PRIVATE)
    val store = MemoryStore(app)
    private var engine: CamrEngine? = null
    private var llm: Llm? = null

    val messages = mutableStateListOf<Message>()
    val chats = mutableStateListOf<Pair<Long, String>>()
    val status = mutableStateOf("Starting…")
    val ready = mutableStateOf(false)
    val busy = mutableStateOf(false)
    val noteCount = mutableStateOf(0)
    val backend = mutableStateOf(prefs.getString("backend", "device") ?: "device")
    val ollamaUrl = mutableStateOf(prefs.getString("ollama_url", "http://192.168.1.10:11434") ?: "")
    val ollamaModel = mutableStateOf(prefs.getString("ollama_model", "") ?: "")
    val ollamaModels = mutableStateListOf<String>()
    val modelFile = mutableStateOf(prefs.getString("model_file", "") ?: "")
    val budget = mutableStateOf(prefs.getInt("budget", 384))
    val rememberChat = mutableStateOf(prefs.getBoolean("remember_chat", true))
    var conversationId: Long? = null
        private set
    private var job: Job? = null

    init {
        viewModelScope.launch(Dispatchers.Default) {
            try {
                engine = CamrEngine(store, OnDeviceEmbedder(getApplication()), tokenBudget = budget.value, rememberChat = rememberChat.value)
                refreshCounts()
                connect()
            } catch (e: Throwable) {
                status.value = "Could not start the memory engine: ${e.message}"
            }
        }
    }

    /** Load the chosen model backend (on-device model file, or Ollama on the user's computer). */
    fun connect() = viewModelScope.launch(Dispatchers.Default) {
        ready.value = false
        llm = try {
            if (backend.value == "device") {
                val f = File(modelFile.value)
                if (!f.exists()) { status.value = "Pick a model file in Settings to start."; null }
                else { status.value = "Loading ${f.nameWithoutExtension}…"; OnDeviceLlm(getApplication(), f) }
            } else {
                if (ollamaModel.value.isBlank()) { status.value = "Choose an Ollama model in Settings."; null }
                else OllamaLlm(ollamaUrl.value, ollamaModel.value)
            }
        } catch (e: Throwable) { status.value = "Model failed to load: ${e.message}"; null }
        llm?.let { status.value = it.label; ready.value = true }
    }

    private fun refreshCounts() {
        noteCount.value = (store.stats()["notes"] as Int)
        val c = store.conversations()
        viewModelScope.launch(Dispatchers.Main) { chats.clear(); chats.addAll(c) }
    }

    fun newChat() { conversationId = null; messages.clear() }

    fun openChat(id: Long) = viewModelScope.launch(Dispatchers.Default) {
        val turns = store.transcript(id)
        withContext(Dispatchers.Main) {
            conversationId = id
            messages.clear()
            for (t in turns) {
                messages += Message(true, t.question)
                messages += Message(false, t.answer, CamrEngine.fromJson(t.sourcesJson), t.abstained, turnId = t.id,
                    grounded = t.grounded, retrievalMs = t.retrievalMs, generationMs = t.generationMs, feedback = t.feedback)
            }
        }
    }

    fun deleteChat(id: Long) = viewModelScope.launch(Dispatchers.Default) {
        store.deleteConversation(id); if (conversationId == id) withContext(Dispatchers.Main) { newChat() }; refreshCounts()
    }

    fun send(text: String, rememberMode: Boolean) {
        val e = engine ?: return
        val model = llm
        var q = text.trim()
        if (q.isEmpty() || busy.value) return
        if (rememberMode && !q.lowercase().startsWith("remember")) q = "remember that $q"
        if (model == null && !q.lowercase().startsWith("remember")) { status.value = "No model yet: open Settings."; return }
        messages += Message(true, q)
        messages += Message(false, "", recalling = true, streaming = true)
        val idx = messages.lastIndex
        busy.value = true
        job = viewModelScope.launch {
            try {
                e.ask(q, conversationId, model ?: NoModel).collect { ev ->
                    when (ev) {
                        is ChatEvent.Recall -> { conversationId = ev.conversationId
                            messages[idx] = messages[idx].copy(recalling = false, sources = ev.sources, abstained = ev.abstained, retrievalMs = ev.ms) }
                        is ChatEvent.Token -> messages[idx] = messages[idx].copy(text = messages[idx].text + ev.text)
                        is ChatEvent.Done -> messages[idx] = messages[idx].copy(text = ev.answer, streaming = false, turnId = ev.turnId,
                            grounded = ev.grounded, generationMs = ev.generationMs, saved = ev.savedToMemory)
                    }
                }
            } catch (t: Throwable) {
                messages[idx] = messages[idx].copy(text = "⚠ ${t.message}", streaming = false, recalling = false)
            } finally {
                busy.value = false
                withContext(Dispatchers.Default) { refreshCounts() }
            }
        }
    }

    fun stop() { job?.cancel() }

    fun feedback(index: Int, helpful: Boolean) {
        val m = messages[index]; val id = m.turnId ?: return
        messages[index] = m.copy(feedback = if (helpful) 1 else -1)
        viewModelScope.launch(Dispatchers.Default) { engine?.feedback(id, helpful); refreshCounts() }
    }

    fun teach(text: String, title: String, kind: String = "note") = viewModelScope.launch(Dispatchers.Default) {
        val n = engine?.teach(text, title, kind) ?: 0
        status.value = if (n > 0) "✦ Saved $n memor${if (n == 1) "y" else "ies"}" else "Already in memory"
        refreshCounts()
    }

    fun teachUri(uri: Uri) = viewModelScope.launch(Dispatchers.IO) {
        val cr = getApplication<Application>().contentResolver
        val name = uri.lastPathSegment?.substringAfterLast('/') ?: "file"
        val text = cr.openInputStream(uri)?.bufferedReader()?.readText() ?: return@launch
        val n = engine?.teach(text, name.substringBeforeLast('.'), "file", "file-$name") ?: 0
        status.value = "✦ Learned $n memories from $name"
        refreshCounts()
    }

    fun memory(query: String, kind: String?): List<SourceItem> = store.sources(kind, query)
    fun forget(id: Long) = viewModelScope.launch(Dispatchers.Default) { store.forget(id); refreshCounts() }
    fun stats(): Map<String, Any> = store.stats()

    // ---------------------------------------------------------------- settings
    fun importModel(uri: Uri) = viewModelScope.launch(Dispatchers.IO) {
        val ctx = getApplication<Application>()
        val name = uri.lastPathSegment?.substringAfterLast('/')?.ifBlank { null } ?: "model.task"
        status.value = "Copying $name into the app…"
        val dest = File(ctx.filesDir, "models").apply { mkdirs() }.resolve(name)
        ctx.contentResolver.openInputStream(uri)?.use { input -> dest.outputStream().use { input.copyTo(it) } }
        modelFile.value = dest.absolutePath
        backend.value = "device"
        save(); connect()
    }

    fun refreshOllamaModels() = viewModelScope.launch(Dispatchers.IO) {
        try {
            val m = OllamaLlm.models(ollamaUrl.value)
            withContext(Dispatchers.Main) { ollamaModels.clear(); ollamaModels.addAll(m) }
            status.value = "Found ${m.size} models on your computer"
        } catch (e: Throwable) { status.value = "Can't reach Ollama at ${ollamaUrl.value}: ${e.message}" }
    }

    fun save() {
        prefs.edit().putString("backend", backend.value).putString("ollama_url", ollamaUrl.value)
            .putString("ollama_model", ollamaModel.value).putString("model_file", modelFile.value)
            .putInt("budget", budget.value).putBoolean("remember_chat", rememberChat.value).apply()
        engine?.tokenBudget = budget.value
        engine?.rememberChat = rememberChat.value
    }
}

/** Used only for "remember that …" before any model is set up: never called. */
private object NoModel : Llm {
    override val label = "none"
    override fun stream(prompt: String) = kotlinx.coroutines.flow.emptyFlow<String>()
}
