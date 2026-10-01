package io.github.satasdin.camr.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.ThumbDown
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.satasdin.camr.engine.Recalled
import kotlinx.coroutines.launch
import kotlin.math.log10
import kotlin.math.min

// ---------------------------------------------------------------- design tokens (same as the desktop app)
val Bg = Color(0xFF0B0E14); val Bg2 = Color(0xFF0F131B); val Surface = Color(0xFF141A24); val Surface2 = Color(0xFF1B2331)
val Border = Color(0xFF253044); val TextC = Color(0xFFE8EBF1); val Muted = Color(0xFF8D95A8); val Faint = Color(0xFF5B6478)
val Accent = Color(0xFF2A78D6); val Accent2 = Color(0xFF5AA2F0); val Good = Color(0xFF1BAF7A); val Warn = Color(0xFFEB6834)
val Aurora = Brush.linearGradient(listOf(Accent, Good))

@Composable
fun CamrTheme(content: @Composable () -> Unit) = MaterialTheme(
    colorScheme = darkColorScheme(primary = Accent, secondary = Good, background = Bg, surface = Surface, onSurface = TextC,
        onBackground = TextC, surfaceVariant = Surface2, outline = Border),
    content = content,
)

/** The CAMR mark: a ring that fills as memory grows (log scale: 10 memories a quarter, 10,000 full). */
@Composable
fun MemoryRing(notes: Int, size: Int = 30, spin: Boolean = false) {
    val t = rememberInfiniteTransition(label = "ring")
    val angle by t.animateFloat(0f, 360f, infiniteRepeatable(tween(14000, easing = LinearEasing), RepeatMode.Restart), label = "a")
    val frac = min(1f, (log10(1.0 + notes) / 4.0).toFloat())
    Canvas(Modifier.size(size.dp).rotate(if (spin) angle else 0f)) {
        val sw = this.size.minDimension * 0.11f
        drawArc(Surface2, 0f, 360f, false, style = Stroke(sw))
        drawArc(Aurora, -90f, 360f * maxOf(frac, if (spin) 0.75f else 0.02f), false, style = Stroke(sw, cap = StrokeCap.Round))
        drawCircle(Aurora, radius = this.size.minDimension * 0.15f, center = Offset(this.size.width / 2, this.size.height / 2))
    }
}

private val KIND = mapOf("note" to "note", "file" to "file", "chat" to "said in chat", "learned" to "approved answer")

// ---------------------------------------------------------------- root
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CamrApp(vm: CamrViewModel) {
    val drawer = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    var screen by remember { mutableStateOf("chat") }
    ModalNavigationDrawer(drawerState = drawer, drawerContent = {
        ModalDrawerSheet(drawerContainerColor = Bg2, modifier = Modifier.width(300.dp)) {
            Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                MemoryRing(vm.noteCount.value, 34)
                Column(Modifier.padding(start = 10.dp)) {
                    Text("CAMR", fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
                    Text("${vm.noteCount.value} memories", color = Muted, fontSize = 12.sp)
                }
            }
            DrawerButton("＋  New chat") { vm.newChat(); screen = "chat"; scope.launch { drawer.close() } }
            Text("CHATS", color = Faint, fontSize = 11.sp, modifier = Modifier.padding(start = 20.dp, top = 14.dp, bottom = 4.dp))
            LazyColumn(Modifier.weight(1f)) {
                items(vm.chats) { (id, title) ->
                    Row(Modifier.fillMaxWidth().clickable { vm.openChat(id); screen = "chat"; scope.launch { drawer.close() } }
                        .padding(horizontal = 20.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(title, color = if (id == vm.conversationId) TextC else Muted, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                        Icon(Icons.Default.Close, "Delete", tint = Faint, modifier = Modifier.size(16.dp).clickable { vm.deleteChat(id) })
                    }
                }
            }
            HorizontalDivider(color = Border)
            DrawerButton("✦  Memory") { screen = "memory"; scope.launch { drawer.close() } }
            DrawerButton("⚙  Settings") { screen = "settings"; scope.launch { drawer.close() } }
            Spacer(Modifier.height(12.dp))
        }
    }) {
        Column(Modifier.fillMaxSize().background(Bg).statusBarsPadding().navigationBarsPadding().imePadding()) {
            Row(Modifier.fillMaxWidth().padding(6.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton({ scope.launch { drawer.open() } }) { Icon(Icons.Default.Menu, "Menu", tint = Muted) }
                Text(when (screen) { "memory" -> "Memory"; "settings" -> "Settings"; else -> vm.status.value },
                    color = if (screen == "chat") Muted else TextC, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                if (screen != "chat") IconButton({ screen = "chat" }) { Icon(Icons.Default.Close, "Back", tint = Muted) }
                else IconButton({ screen = "settings" }) { Icon(Icons.Default.Settings, "Settings", tint = Muted) }
            }
            when (screen) {
                "memory" -> MemoryScreen(vm)
                "settings" -> SettingsScreen(vm)
                else -> ChatScreen(vm)
            }
        }
    }
}

@Composable
private fun DrawerButton(label: String, onClick: () -> Unit) =
    Text(label, color = TextC, modifier = Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 20.dp, vertical = 12.dp))

// ---------------------------------------------------------------- chat
@Composable
fun ChatScreen(vm: CamrViewModel) {
    var input by remember { mutableStateOf("") }
    var rememberMode by remember { mutableStateOf(false) }
    val list = rememberLazyListState()
    val pickFile = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { it?.let(vm::teachUri) }
    LaunchedEffect(vm.messages.size, vm.messages.lastOrNull()?.text?.length) { if (vm.messages.isNotEmpty()) list.animateScrollToItem(vm.messages.lastIndex) }

    Column(Modifier.fillMaxSize()) {
        Box(Modifier.weight(1f).fillMaxWidth()) {
            if (vm.messages.isEmpty()) {
                Column(Modifier.align(Alignment.Center).padding(28.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    MemoryRing(vm.noteCount.value, 64, spin = true)
                    Spacer(Modifier.height(18.dp))
                    Text(if (vm.noteCount.value > 0) "What do you want to know?" else "What should I remember?",
                        fontSize = 26.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
                    Text("Your model stays the same. What it knows grows with you.", color = Muted, textAlign = TextAlign.Center,
                        modifier = Modifier.padding(top = 6.dp))
                    Spacer(Modifier.height(18.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Pill("✦ Remember that…") { input = "remember that " }
                        Pill("＋ Teach a file") { pickFile.launch(arrayOf("text/*")) }
                    }
                }
            }
            LazyColumn(state = list, modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp)) {
                itemsIndexed(vm.messages) { i, m -> if (m.user) UserBubble(m.text) else AssistantMessage(m, { vm.feedback(i, true) }, { vm.feedback(i, false) }) }
            }
        }
        // composer
        Column(Modifier.padding(10.dp).clip(RoundedCornerShape(24.dp)).background(Surface)
            .border(1.dp, if (rememberMode) Good else Border, RoundedCornerShape(24.dp)).padding(horizontal = 10.dp, vertical = 6.dp)) {
            TextField(input, { input = it }, placeholder = { Text(if (rememberMode) "A fact to store in memory…" else "Ask anything, or “remember that …”", color = Faint) },
                colors = TextFieldDefaults.colors(focusedContainerColor = Color.Transparent, unfocusedContainerColor = Color.Transparent,
                    focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent),
                maxLines = 6, modifier = Modifier.fillMaxWidth())
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton({ pickFile.launch(arrayOf("text/*")) }) { Icon(Icons.Default.Add, "Teach a file", tint = Muted) }
                FilterChip(rememberMode, { rememberMode = !rememberMode }, label = { Text("✦ Remember") })
                Spacer(Modifier.weight(1f))
                Box(Modifier.size(40.dp).clip(CircleShape).background(if (vm.busy.value) Brush.linearGradient(listOf(TextC, TextC)) else Aurora)
                    .clickable { if (vm.busy.value) vm.stop() else { vm.send(input, rememberMode); input = "" } }, contentAlignment = Alignment.Center) {
                    Icon(if (vm.busy.value) Icons.Default.Stop else Icons.AutoMirrored.Filled.Send, "Send", tint = if (vm.busy.value) Bg else Color.White, modifier = Modifier.size(18.dp))
                }
            }
        }
        Text("Runs on your phone. Answers cite the memories they used.", color = Faint, fontSize = 11.sp,
            modifier = Modifier.fillMaxWidth().padding(bottom = 6.dp), textAlign = TextAlign.Center)
    }
}

@Composable
private fun Pill(text: String, onClick: () -> Unit) = Text(text, color = Muted, fontSize = 13.sp,
    modifier = Modifier.clip(RoundedCornerShape(50)).border(1.dp, Border, RoundedCornerShape(50)).clickable(onClick = onClick)
        .padding(horizontal = 14.dp, vertical = 8.dp))

@Composable
private fun UserBubble(text: String) = Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), horizontalArrangement = Arrangement.End) {
    Text(text, modifier = Modifier.widthIn(max = 300.dp).clip(RoundedCornerShape(20.dp, 20.dp, 6.dp, 20.dp)).background(Surface2)
        .padding(horizontal = 14.dp, vertical = 10.dp))
}

@Composable
private fun AssistantMessage(m: Message, up: () -> Unit, down: () -> Unit) {
    var open by remember { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
        Box(Modifier.size(26.dp).clip(CircleShape).background(Aurora), contentAlignment = Alignment.Center) {
            Box(Modifier.size(10.dp).clip(CircleShape).background(Bg))
        }
        Column(Modifier.padding(start = 10.dp).weight(1f)) {
            // recall card: what memory was read, shown before the answer
            val label = when {
                m.recalling -> "✦ Searching your memory…"
                m.sources.isNotEmpty() -> "✦ Recalled ${m.sources.size} ${if (m.sources.size == 1) "memory" else "memories"} · ${m.retrievalMs.toInt()} ms"
                m.abstained -> "✦ No matching memories, so the model answers alone"
                else -> "✦ Saved directly to memory"
            }
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).border(1.dp, Border, RoundedCornerShape(14.dp))
                .clickable(enabled = m.sources.isNotEmpty()) { open = !open }.padding(10.dp)) {
                Text(label + if (m.sources.isNotEmpty()) (if (open) "  ▴" else "  ▾") else "", color = Muted, fontSize = 13.sp)
                if (open) m.sources.forEach { MemoryCard(it) }
            }
            Spacer(Modifier.height(8.dp))
            Text(m.text + if (m.streaming && !m.recalling) " ▍" else "", lineHeight = 22.sp)
            if (!m.streaming && m.turnId != null) Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 4.dp)) {
                IconButton(up, Modifier.size(32.dp)) { Icon(Icons.Default.ThumbUp, "Teach this answer", tint = if (m.feedback == 1) Good else Faint, modifier = Modifier.size(16.dp)) }
                IconButton(down, Modifier.size(32.dp)) { Icon(Icons.Default.ThumbDown, "Not helpful", tint = if (m.feedback == -1) Warn else Faint, modifier = Modifier.size(16.dp)) }
                m.grounded?.let { g ->
                    Box(Modifier.width(44.dp).height(4.dp).clip(RoundedCornerShape(4.dp)).background(Surface2)) {
                        Box(Modifier.fillMaxWidth(g.toFloat().coerceIn(0.05f, 1f)).height(4.dp).background(if (g >= 0.6) Good else if (g >= 0.3) Color(0xFFE3B341) else Warn))
                    }
                    Text(" grounded ${(g * 100).toInt()}%", color = Faint, fontSize = 12.sp)
                }
                Spacer(Modifier.weight(1f))
                if (m.generationMs > 0) Text("${(m.generationMs / 1000).let { "%.1f".format(it) }} s", color = Faint, fontSize = 11.sp)
            }
            if (m.saved && m.sources.isEmpty() && !m.abstained) Text("✦ Stored in memory", color = Good, fontSize = 12.sp)
        }
    }
}

@Composable
private fun MemoryCard(r: Recalled) = Column(Modifier.padding(top = 8.dp).fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(Surface).padding(10.dp)) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(KIND[r.kind] ?: r.kind, color = Accent2, fontSize = 11.sp, modifier = Modifier.clip(RoundedCornerShape(50)).background(Surface2).padding(horizontal = 8.dp, vertical = 1.dp))
        if (r.title.isNotBlank()) Text("  ${r.title}", color = Muted, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
        else Spacer(Modifier.weight(1f))
        if (r.bridged) Text("↳ linked ", color = Faint, fontSize = 11.sp)
        Box(Modifier.width(40.dp).height(4.dp).clip(RoundedCornerShape(4.dp)).background(Surface2)) {
            Box(Modifier.fillMaxWidth(r.similarity.coerceIn(0.08f, 1f)).height(4.dp).background(Aurora))
        }
    }
    Text(r.text, fontSize = 13.sp, maxLines = 4, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 4.dp))
}

// ---------------------------------------------------------------- memory
@Composable
fun MemoryScreen(vm: CamrViewModel) {
    var q by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf<String?>(null) }
    var title by remember { mutableStateOf("") }
    var note by remember { mutableStateOf("") }
    var tick by remember { mutableStateOf(0) }
    val items = remember(q, kind, tick, vm.noteCount.value) { vm.memory(q, kind) }
    val stats = remember(tick, vm.noteCount.value) { vm.stats() }
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Stat("Memories", "${stats["notes"]}", Modifier.weight(1f))
                val turns = stats["turns"] as Int
                Stat("From memory", if (turns > 0) "${100 * (stats["withMemory"] as Int) / turns}%" else "–", Modifier.weight(1f))
                Stat("👍 learned", "${stats["helpful"]}", Modifier.weight(1f))
            }
        }
        item {
            Column(Modifier.clip(RoundedCornerShape(16.dp)).background(Surface).padding(12.dp)) {
                Text("Teach", fontWeight = FontWeight.SemiBold)
                OutlinedTextField(title, { title = it }, label = { Text("Title (optional)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(note, { note = it }, label = { Text("Note") }, minLines = 3, modifier = Modifier.fillMaxWidth())
                TextButton({ vm.teach(note, title); note = ""; title = ""; tick++ }) { Text("Save to memory") }
            }
        }
        item {
            OutlinedTextField(q, { q = it }, placeholder = { Text("Search memory") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.padding(top = 6.dp)) {
                listOf(null to "All", "note" to "Notes", "file" to "Files", "chat" to "Chat", "learned" to "Approved").forEach { (k, l) ->
                    FilterChip(kind == k, { kind = k }, label = { Text(l, fontSize = 12.sp) })
                }
            }
        }
        items(items, key = { it.id }) { s ->
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(Surface).padding(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(KIND[s.kind] ?: s.kind, color = Accent2, fontSize = 11.sp)
                    Text("  ${s.title}", fontWeight = FontWeight.SemiBold, fontSize = 13.sp, maxLines = 1, modifier = Modifier.weight(1f))
                    Text("Forget", color = Faint, fontSize = 12.sp, modifier = Modifier.clickable { vm.forget(s.id); tick++ })
                }
                Text(s.text.take(280), fontSize = 13.sp, color = TextC.copy(alpha = .9f))
            }
        }
    }
}

@Composable
private fun Stat(k: String, v: String, modifier: Modifier) = Column(modifier.clip(RoundedCornerShape(14.dp)).background(Surface).padding(12.dp)) {
    Text(k.uppercase(), color = Muted, fontSize = 10.sp, letterSpacing = 1.sp)
    Text(v, fontSize = 20.sp, fontWeight = FontWeight.Bold)
}

// ---------------------------------------------------------------- settings
@Composable
fun SettingsScreen(vm: CamrViewModel) {
    val pickModel = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { it?.let(vm::importModel) }
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Text("Model", fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp)) {
                FilterChip(vm.backend.value == "device", { vm.backend.value = "device"; vm.save(); vm.connect() }, label = { Text("On this phone") })
                FilterChip(vm.backend.value == "ollama", { vm.backend.value = "ollama"; vm.save(); vm.connect() }, label = { Text("Ollama on my computer") })
            }
        }
        if (vm.backend.value == "device") item {
            Column(Modifier.clip(RoundedCornerShape(16.dp)).background(Surface).padding(14.dp)) {
                Text(if (vm.modelFile.value.isBlank()) "No model file yet" else vm.modelFile.value.substringAfterLast('/'), fontWeight = FontWeight.SemiBold)
                Text("Download a LiteRT/MediaPipe model (.task) such as Gemma 3 1B or Qwen2.5 1.5B from huggingface.co/litert-community, then pick the file. It runs fully on the phone; nothing is sent anywhere.",
                    color = Muted, fontSize = 13.sp)
                TextButton({ pickModel.launch(arrayOf("*/*")) }) { Text("Pick model file") }
            }
        } else item {
            Column(Modifier.clip(RoundedCornerShape(16.dp)).background(Surface).padding(14.dp)) {
                Text("Start Ollama on your computer with OLLAMA_HOST=0.0.0.0, then enter its address. Memory stays on the phone; only each question's prompt goes to your computer.",
                    color = Muted, fontSize = 13.sp)
                OutlinedTextField(vm.ollamaUrl.value, { vm.ollamaUrl.value = it }, label = { Text("Ollama address") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                TextButton({ vm.save(); vm.refreshOllamaModels() }) { Text("Find models") }
                vm.ollamaModels.forEach { m ->
                    Text((if (m == vm.ollamaModel.value) "● " else "○ ") + m, modifier = Modifier.fillMaxWidth()
                        .clickable { vm.ollamaModel.value = m; vm.save(); vm.connect() }.padding(vertical = 8.dp))
                }
            }
        }
        item {
            Text("Memory read per question: ${vm.budget.value} tokens", fontWeight = FontWeight.SemiBold)
            Slider(vm.budget.value.toFloat(), { vm.budget.value = (it / 64).toInt() * 64 }, valueRange = 64f..1024f, onValueChangeFinished = { vm.save() })
            Text("Measured: about 128 tokens is best for single facts on tiny models, about 512 for multi-step questions.", color = Muted, fontSize = 12.sp)
        }
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Remember what I say in chat", modifier = Modifier.weight(1f))
                Switch(vm.rememberChat.value, { vm.rememberChat.value = it; vm.save() })
            }
        }
        item { Text("CAMR 0.2 · memory: on-device Universal Sentence Encoder · MIT licence · github.com/Satasdin/CAMR", color = Faint, fontSize = 12.sp) }
    }
}
