package io.github.satasdin.camr.engine

import android.content.Context
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.genai.llminference.LlmInference
import com.google.mediapipe.tasks.text.textembedder.TextEmbedder
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.Dispatchers
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit
import kotlin.math.sqrt

/** Turns text into unit vectors. On the phone this is always on-device, so memory never leaves it. */
interface Embedder {
    val name: String
    fun embed(text: String): FloatArray
}

/** Universal Sentence Encoder (MediaPipe Text Embedder, 6 MB, bundled in the APK). */
class OnDeviceEmbedder(context: Context) : Embedder {
    override val name = "mediapipe:universal_sentence_encoder"
    private val embedder: TextEmbedder = TextEmbedder.createFromOptions(
        context,
        TextEmbedder.TextEmbedderOptions.builder()
            .setBaseOptions(BaseOptions.builder().setModelAssetPath("universal_sentence_encoder.tflite").build())
            .setL2Normalize(true)
            .build(),
    )

    @Synchronized
    override fun embed(text: String): FloatArray {
        val v = embedder.embed(text).embeddingResult().embeddings()[0].floatEmbedding()
        return normalise(v)
    }
}

fun normalise(v: FloatArray): FloatArray {
    var s = 0.0
    for (x in v) s += x * x
    val n = sqrt(s).toFloat()
    return if (n == 0f) v else FloatArray(v.size) { v[it] / n }
}

/** A language model that streams its answer. */
interface Llm {
    val label: String
    fun stream(prompt: String): Flow<String>
}

/**
 * Fully on-device generation with a MediaPipe/LiteRT model file the user picked
 * (e.g. Gemma 3 1B or Qwen2.5 1.5B in .task format from huggingface.co/litert-community).
 */
class OnDeviceLlm(context: Context, modelFile: File, maxTokens: Int = 1280) : Llm {
    override val label = modelFile.nameWithoutExtension
    private val llm: LlmInference = LlmInference.createFromOptions(
        context,
        LlmInference.LlmInferenceOptions.builder()
            .setModelPath(modelFile.absolutePath)
            .setMaxTokens(maxTokens)
            .build(),
    )

    override fun stream(prompt: String): Flow<String> = callbackFlow {
        val future = llm.generateResponseAsync(prompt) { partial, done ->
            if (partial.isNotEmpty()) trySend(partial)
            if (done) close()
        }
        awaitClose { if (!future.isDone) future.cancel(true) }
    }
}

/**
 * Generation by Ollama running on the user's own computer on the same Wi-Fi
 * (start it with OLLAMA_HOST=0.0.0.0). Memory and embeddings still stay on the phone;
 * only the prompt for one answer is sent to the user's computer.
 */
class OllamaLlm(private val baseUrl: String, private val model: String) : Llm {
    override val label = model
    private val http = OkHttpClient.Builder().readTimeout(10, TimeUnit.MINUTES).build()

    override fun stream(prompt: String): Flow<String> = flow {
        val body = JSONObject().put("model", model).put("prompt", prompt).put("stream", true)
            .put("options", JSONObject().put("temperature", 0).put("num_predict", 768)).toString()
        val req = Request.Builder().url("${baseUrl.trimEnd('/')}/api/generate")
            .post(body.toRequestBody("application/json".toMediaType())).build()
        http.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) error("Ollama replied ${resp.code}")
            val src = resp.body!!.source()
            while (!src.exhausted()) {
                val line = src.readUtf8Line() ?: break
                if (line.isBlank()) continue
                val j = JSONObject(line)
                if (j.has("error")) error(j.getString("error"))
                val piece = j.optString("response")
                if (piece.isNotEmpty()) emit(piece)
                if (j.optBoolean("done")) break
            }
        }
    }.flowOn(Dispatchers.IO)

    companion object {
        fun models(baseUrl: String): List<String> {
            val http = OkHttpClient.Builder().callTimeout(4, TimeUnit.SECONDS).build()
            http.newCall(Request.Builder().url("${baseUrl.trimEnd('/')}/api/tags").build()).execute().use { r ->
                val arr = JSONObject(r.body!!.string()).getJSONArray("models")
                return (0 until arr.length()).map { arr.getJSONObject(it).getString("name") }
                    .filterNot { it.contains("embed") }
            }
        }
    }
}
