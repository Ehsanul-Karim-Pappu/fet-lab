package io.github.ehsanulkarimpappu.fetlab

import android.content.Context
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.VectorConverter
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathFillType
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.res.imageResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import org.json.JSONObject

/** One destination the guided tour or the feature list can point at. */
class GuideStop(
    val id: String, val category: String, val title: String, val body: String,
    /** -1 leaves whatever tab is already open (used by the header steps); otherwise the
     *  index into [TABS] that this stop lives on. */
    val tab: Int,
    /** "tap" · "drag" · "pinch" · "none" — which glyph the tour card animates. */
    val gesture: String
)

/** A term the step text uses: its short form, what it stands for, and a plain definition.
 *  [match] are the phrases that count as the term appearing in a step's text. */
class GlossTerm(val term: String, val name: String, val text: String, match: List<String>) {
    // An acronym matches as a whole word, in capitals; a phrase at a word's start, any case.
    private val res = match.map { m ->
        if (m == m.uppercase()) Regex("\\b" + Regex.escape(m) + "\\b")
        else Regex("\\b" + Regex.escape(m), RegexOption.IGNORE_CASE)
    }
    fun inText(t: String) = res.any { it.containsMatchIn(t) }
}

/** One stop on the suggested learning path: a Device-mode scene key, or "process". */
class LearnStop(val key: String, val title: String, val body: String)

class GuideCatalog(val stops: List<GuideStop>, val tour: List<String>, val processTour: List<String>,
                   val glossary: List<GlossTerm>, val learn: List<LearnStop>) {
    fun stop(id: String) = stops.first { it.id == id }
    /** The glossary terms [text] uses, in glossary order. */
    fun termsIn(text: String) = glossary.filter { it.inText(text) }
    companion object {
        fun load(ctx: Context): GuideCatalog {
            val root = JSONObject(ctx.assets.open("guide.json").bufferedReader().use { it.readText() })
            val arr = root.getJSONArray("stops")
            val stops = List(arr.length()) { i ->
                val s = arr.getJSONObject(i)
                GuideStop(s.getString("id"), s.getString("category"), s.getString("title"),
                    s.getString("body"), s.optInt("tab", -1), s.optString("gesture", "none"))
            }
            fun ids(k: String) = root.optJSONArray(k)?.let { t -> List(t.length()) { t.getString(it) } }.orEmpty()
            val g = root.optJSONArray("glossary")
            val glossary = if (g == null) emptyList() else List(g.length()) { i ->
                val o = g.getJSONObject(i)
                val m = o.getJSONArray("match")
                GlossTerm(o.getString("term"), o.getString("name"), o.getString("text"),
                    List(m.length()) { m.getString(it) })
            }
            val l = root.optJSONArray("learn")
            val learn = if (l == null) emptyList() else List(l.length()) { i ->
                val o = l.getJSONObject(i)
                LearnStop(o.getString("key"), o.getString("title"), o.getString("body"))
            }
            return GuideCatalog(stops, ids("tour"), ids("process_tour"), glossary, learn)
        }
    }
}

private const val PREFS = "guide"
private const val KEY_TOUR_SEEN = "tour_seen_v1"

fun tourSeen(ctx: Context): Boolean =
    ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(KEY_TOUR_SEEN, false)

fun markTourSeen(ctx: Context) {
    ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(KEY_TOUR_SEEN, true).apply()
}

/* ============================================================ targets ==== */

/**
 * Where every control the tour can point at currently sits on screen, in root
 * coordinates. Controls register themselves with [tourTarget]; the map is snapshot
 * state, so the spotlight follows a control that moves or resizes (a sheet opening,
 * a list scrolling) instead of pointing at where it used to be.
 */
class TourTargets {
    private val map = mutableStateMapOf<String, Rect>()
    operator fun get(id: String): Rect? = map[id]
    fun put(id: String, r: Rect) { if (map[id] != r) map[id] = r }
    fun remove(id: String) { map.remove(id) }
}

val LocalTourTargets = staticCompositionLocalOf<TourTargets?> { null }

/** Registers this element's on-screen bounds under [id] so the tour can find it. */
fun Modifier.tourTarget(id: String): Modifier = composed {
    val targets = LocalTourTargets.current ?: return@composed Modifier
    DisposableEffect(targets, id) { onDispose { targets.remove(id) } }
    Modifier.onGloballyPositioned { targets.put(id, it.boundsInRoot()) }
}

/* ============================================================= player ==== */

class Ripple(val at: Offset) { val t = Animatable(0f) }

/**
 * Drives the tour's moving parts: one spotlight that glides between sections, and a
 * hand that travels to a control, presses it and leaves a ripple. Steps are written
 * as short suspend scripts against this, e.g. `spot("sheet"); tap("tab:1") { … }`,
 * and a step change cancels the running script.
 */
class TourPlayer(val targets: TourTargets, private val scope: CoroutineScope, private val px: Float) {
    /** The section currently lit; the overlay animates [spot] towards its bounds. */
    var spotId by mutableStateOf("")
    val spot = Animatable(Rect.Zero, Rect.VectorConverter)
    /** Root-space bounds of the overlay itself, to convert root rects into its frame. */
    var bounds by mutableStateOf(Rect.Zero)
    /** Set by [reset]: the next spotlight closes in from the whole screen again. */
    var fresh = true

    val hand = Animatable(Offset.Zero, Offset.VectorConverter)
    val handAlpha = Animatable(0f)
    val press = Animatable(0f)
    /** Two fingertips, while a pinch is being shown instead of the hand. */
    var pinch by mutableStateOf<Pair<Offset, Offset>?>(null)
    val ripples = mutableStateListOf<Ripple>()

    /** Waits (briefly) for a control to be laid out, since a tab may still be opening. */
    suspend fun rect(id: String): Rect? {
        repeat(90) {
            targets[id]?.let { if (it.width > 0f && it.height > 0f) return it }
            withFrameNanos { }
        }
        return null
    }

    suspend fun spot(id: String) {
        spotId = id
        rect(id)
        delay(520)
    }

    private suspend fun moveHand(to: Offset, ms: Int = 560) {
        if (handAlpha.value < 0.02f) hand.snapTo(Offset(to.x + 70f * px, to.y + 170f * px))
        coroutineScope {
            launch { handAlpha.animateTo(1f, tween(220)) }
            hand.animateTo(to, tween(ms, easing = FastOutSlowInEasing))
        }
    }

    fun ripple(at: Offset) {
        val r = Ripple(at)
        ripples.add(r)
        scope.launch { r.t.animateTo(1f, tween(650)); ripples.remove(r) }
    }

    /** Moves to [id], presses, fires [effect] at the moment of contact, releases. */
    suspend fun tap(id: String, effect: () -> Unit = {}) {
        val r = rect(id) ?: return
        moveHand(r.center)
        delay(120)
        press.animateTo(1f, tween(110))
        ripple(r.center)
        effect()
        press.animateTo(0f, tween(170))
        delay(650)
    }

    /** Presses at [from], slides to [to] over [ms], calling [onStep] with each progress delta. */
    suspend fun drag(from: Offset, to: Offset, ms: Int, onStep: (Float) -> Unit) {
        moveHand(from)
        delay(100)
        press.animateTo(1f, tween(110))
        ripple(from)
        val p = Animatable(0f)
        var last = 0f
        coroutineScope {
            launch { hand.animateTo(to, tween(ms, easing = FastOutSlowInEasing)) }
            p.animateTo(1f, tween(ms, easing = FastOutSlowInEasing)) { onStep(value - last); last = value }
        }
        press.animateTo(0f, tween(170))
        delay(350)
    }

    /** A quick swipe from [from] to [to]: [onStep] gets progress deltas while the finger
     *  moves, and [coast] runs as it lifts off, like a flung list still gliding. */
    suspend fun flick(from: Offset, to: Offset, ms: Int, onStep: (Float) -> Unit, coast: suspend () -> Unit) {
        moveHand(from)
        delay(100)
        press.animateTo(1f, tween(110))
        ripple(from)
        val p = Animatable(0f)
        var last = 0f
        coroutineScope {
            launch { hand.animateTo(to, tween(ms, easing = LinearEasing)) }
            p.animateTo(1f, tween(ms, easing = LinearEasing)) { onStep(value - last); last = value }
        }
        coroutineScope {
            launch { press.animateTo(0f, tween(170)) }
            coast()
        }
        delay(250)
    }

    /** Two fingertips spreading apart and back at [centre]; [onSpread] gets 0 → 1 → 0. */
    suspend fun pinch(centre: Offset, ms: Int, onSpread: (Float) -> Unit) {
        handAlpha.animateTo(0f, tween(160))
        val s = Animatable(0f)
        val near = 22f * px; val far = 78f * px
        fun place(v: Float) {
            val d = near + (far - near) * v
            pinch = Offset(centre.x - d, centre.y + d * 0.55f) to Offset(centre.x + d, centre.y - d * 0.55f)
            onSpread(v)
        }
        try {
            place(0f)
            pinch?.let { ripple(it.first); ripple(it.second) }
            s.animateTo(1f, tween(ms / 2, easing = FastOutSlowInEasing)) { place(value) }
            s.animateTo(0f, tween(ms / 2, easing = FastOutSlowInEasing)) { place(value) }
        } finally {
            pinch = null          // even if Next interrupts it mid-pinch
        }
        delay(250)
    }

    suspend fun hideHand() { handAlpha.animateTo(0f, tween(260)) }

    /** Clears anything an interrupted step left mid-gesture: the pinch dots, a hand
     *  still pressed down. Run at the start of every step. */
    suspend fun settle() {
        pinch = null
        press.snapTo(0f)
    }

    /** Stops the hand. The spotlight hole is left where it was, so the veil can fade out
     *  around it instead of flashing the whole screen dark. */
    suspend fun reset() {
        spotId = ""; pinch = null; ripples.clear(); fresh = true
        handAlpha.snapTo(0f); press.snapTo(0f)
    }
}

/* =============================================================== hand ==== */

/** Where the fingertip's pad sits in `drawable-nodpi/tour_hand.png`, as fractions of
 *  its width and height: the point that lands on the control being tapped. */
private const val HAND_TIP_X = 0.1310f
private const val HAND_TIP_Y = 0.0917f

/* ============================================================ overlay ==== */

/**
 * The scrim with a hole where the current section is, a soft pulsing edge around the
 * hole, the ripples, and the hand. It never takes touches — everything underneath
 * stays live, and the tour card sits above it.
 */
@Composable
fun TourOverlay(player: TourPlayer, active: Boolean, tint: Color, modifier: Modifier = Modifier) {
    val hand = ImageBitmap.imageResource(R.drawable.tour_hand)
    val scrim by animateFloatAsState(if (active) 0.72f else 0f, tween(320), label = "tourScrim")
    val glow by rememberInfiniteTransition(label = "spotGlow").animateFloat(
        initialValue = 0.35f, targetValue = 0.95f,
        animationSpec = infiniteRepeatable(tween(950, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "spotGlowT")

    // Follow the lit section: a long glide when it changes, short catch-ups while it moves.
    LaunchedEffect(player.spotId) {
        val id = player.spotId
        if (id.isEmpty()) return@LaunchedEffect
        var first = true
        snapshotFlow { player.targets[id] }.collectLatest { r ->
            if (r == null || r.isEmpty) return@collectLatest
            // The first spotlight of the tour closes in from the whole screen.
            if (player.fresh || player.spot.value.isEmpty) { player.spot.snapTo(player.bounds); player.fresh = false }
            player.spot.animateTo(r, tween(if (first) 520 else 160, easing = FastOutSlowInEasing))
            first = false
        }
    }

    Canvas(modifier.onGloballyPositioned { player.bounds = it.boundsInRoot() }) {
        if (scrim < 0.01f) return@Canvas
        val o = player.bounds.topLeft
        val s = player.spot.value
        // Keep the lit hole a little inside the screen: full-width sections (the mode bar,
        // the chip row, the tool sheet) would otherwise push the glowing edge off the sides
        // and leave it looking cut.
        val lit = if (s.isEmpty) Rect.Zero
            else s.translate(-o.x, -o.y).inflate(8.dp.toPx()).intersect(Rect(Offset.Zero, size).deflate(10.dp.toPx()))
        val hole = if (lit.isEmpty) null else RoundRect(lit, CornerRadius(16.dp.toPx()))

        val veil = Path().apply {
            fillType = PathFillType.EvenOdd
            addRect(Rect(Offset.Zero, size))
            if (hole != null) addRoundRect(hole)
        }
        drawPath(veil, Color.Black.copy(alpha = scrim))

        val on = scrim / 0.72f
        if (hole != null) for (i in 0..2) {
            val grow = (i * 3).dp.toPx()
            drawRoundRect(tint.copy(alpha = glow * (0.55f - i * 0.17f) * on),
                topLeft = Offset(hole.left - grow, hole.top - grow),
                size = Size(hole.width + 2 * grow, hole.height + 2 * grow),
                cornerRadius = CornerRadius(16.dp.toPx() + grow),
                style = Stroke(width = (2 + i * 2).dp.toPx()))
        }

        for (r in player.ripples) {
            val t = r.t.value
            val c = r.at - o
            drawCircle(tint.copy(alpha = (1f - t) * 0.28f * on), radius = (8 + 30 * t).dp.toPx(), center = c)
            drawCircle(tint.copy(alpha = (1f - t) * 0.9f * on), radius = (10 + 34 * t).dp.toPx(), center = c,
                style = Stroke(width = (3f * (1f - t) + 1f).dp.toPx()))
        }

        player.pinch?.let { (a, b) ->
            for (p in listOf(a - o, b - o)) {
                drawCircle(Color.White.copy(alpha = 0.25f * on), radius = 20.dp.toPx(), center = p)
                drawCircle(Color.White.copy(alpha = 0.95f * on), radius = 11.dp.toPx(), center = p)
            }
        }

        val a = player.handAlpha.value * on
        if (a > 0.01f) {
            val tip = player.hand.value - o
            val press = player.press.value
            // The image already points up and to the left; scale it so the hand is about
            // 140 dp across, slightly smaller while pressed, with the finger pad on the tap.
            val k = 140.dp.toPx() / hand.width * (1f - 0.08f * press)
            translate(tip.x - hand.width * HAND_TIP_X * k, tip.y - hand.height * HAND_TIP_Y * k) {
                scale(k, k, pivot = Offset.Zero) { drawImage(hand, alpha = a) }
            }
        }
    }
}

/* ============================================================ gestures === */

/** A small looping illustration of the gesture a tour step is teaching. */
@Composable
private fun GestureGlyph(kind: String, tint: Color, modifier: Modifier = Modifier) {
    if (kind == "none") return
    val t by rememberInfiniteTransition(label = "glyph").animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1100, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "glyphT")
    Canvas(modifier.size(40.dp)) {
        val c = Offset(size.width / 2f, size.height / 2f)
        val r = size.minDimension / 2f
        when (kind) {
            "tap" -> {
                drawCircle(tint, radius = r * 0.26f, center = c)
                drawCircle(tint.copy(alpha = (1f - t).coerceIn(0f, 1f)),
                    radius = r * (0.35f + 0.55f * t), center = c, style = Stroke(width = 3f))
            }
            "drag" -> {
                val dx = (t - 0.5f) * size.width * 0.55f
                drawLine(tint.copy(alpha = 0.35f), Offset(c.x - size.width * 0.32f, c.y),
                    Offset(c.x + size.width * 0.32f, c.y), strokeWidth = 3f)
                drawCircle(tint, radius = r * 0.26f, center = Offset(c.x + dx, c.y))
            }
            "pinch" -> {
                val d = r * (0.22f + 0.5f * t)
                drawLine(tint.copy(alpha = 0.3f), Offset(c.x - d, c.y - d * 0.4f),
                    Offset(c.x + d, c.y + d * 0.4f), strokeWidth = 2.5f)
                drawCircle(tint, radius = r * 0.2f, center = Offset(c.x - d, c.y - d * 0.4f))
                drawCircle(tint, radius = r * 0.2f, center = Offset(c.x + d, c.y + d * 0.4f))
            }
        }
    }
}

/* ============================================================ dialogs ==== */

@Composable
fun WelcomeGuide(onStart: () -> Unit, onSkip: () -> Unit) {
    Dialog(onDismissRequest = onSkip) {
        Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surface) {
            Column(Modifier.padding(22.dp).widthIn(max = 340.dp)) {
                Text("New here?", style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onSurface)
                Spacer(Modifier.height(8.dp))
                Text("A minute-long tour of the model, the tools around it, and how they " +
                     "connect. You can skip it now and replay it any time from Help.",
                    fontFamily = PlexSans, fontSize = 13.5f.sp, lineHeight = 19.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(18.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = onSkip) { Text("Explore myself") }
                    Spacer(Modifier.width(4.dp))
                    Button(onClick = onStart) { Text("Start tour") }
                }
            }
        }
    }
}

/** The floating step card the tour shows — sits in normal layout flow above the stage,
 *  never overlapping the thing it is pointing at. */
@Composable
fun TourCard(stop: GuideStop, step: Int, total: Int, modifier: Modifier = Modifier,
             onBack: () -> Unit, onNext: () -> Unit, onExit: () -> Unit) {
    Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(18.dp),
        modifier = modifier) {
        Column(Modifier.padding(16.dp)) {
            // The words cross-fade and the card eases to its new height, instead of snapping.
            AnimatedContent(targetState = step to stop, label = "tourCard",
                transitionSpec = {
                    (fadeIn(tween(240, delayMillis = 90)) togetherWith fadeOut(tween(120)))
                        .using(SizeTransform(clip = false) { _, _ -> tween(320, easing = FastOutSlowInEasing) })
                }) { (i, s) ->
                Row(verticalAlignment = Alignment.Top) {
                    GestureGlyph(s.gesture, MaterialTheme.colorScheme.onPrimaryContainer,
                        Modifier.padding(end = 12.dp, top = 2.dp))
                    Column(Modifier.weight(1f)) {
                        Text("${s.category.uppercase()} · ${i + 1}/$total",
                            fontFamily = Mono, fontSize = 10.sp, letterSpacing = 1.2f.sp,
                            color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.7f))
                        Text(s.title, style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onPrimaryContainer,
                            modifier = Modifier.padding(top = 2.dp, bottom = 4.dp))
                        Text(s.body, fontFamily = PlexSans, fontSize = 13.sp, lineHeight = 18.sp,
                            color = MaterialTheme.colorScheme.onPrimaryContainer)
                    }
                }
            }
            Spacer(Modifier.height(10.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                TextButton(onClick = onExit) { Text("Skip") }
                Row {
                    if (step > 0) TextButton(onClick = onBack) { Text("Back") }
                    TextButton(onClick = onNext) { Text(if (step == total - 1) "Done" else "Next") }
                }
            }
        }
    }
}

/** Searchable index of everything the app can do, each row jumping straight to it; a
 *  suggested order to learn the devices in, and a glossary of the terms the steps use. */
@Composable
fun FeatureGuide(catalog: GuideCatalog, onOpen: (GuideStop) -> Unit, onTour: () -> Unit,
                 onProcessTour: () -> Unit, onLearn: (LearnStop) -> Unit, onClose: () -> Unit) {
    var query by remember { mutableStateOf("") }
    val matches = remember(query) {
        catalog.stops.filter { "${it.title} ${it.body} ${it.category}".contains(query, ignoreCase = true) }
    }
    val terms = remember(query) {
        catalog.glossary.filter { "${it.term} ${it.name} ${it.text}".contains(query, ignoreCase = true) }
    }
    Dialog(onDismissRequest = onClose, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(shape = RoundedCornerShape(24.dp), color = MaterialTheme.colorScheme.surface,
            modifier = Modifier.fillMaxWidth(0.94f).fillMaxHeight(0.88f)) {
            Column(Modifier.padding(20.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically) {
                    Text("Help & features", style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.onSurface)
                    TextButton(onClick = onClose) { Text("Close") }
                }
                Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = onTour, modifier = Modifier.weight(1f)) { Text("Guided tour") }
                    if (catalog.processTour.isNotEmpty())
                        OutlinedButton(onClick = onProcessTour, modifier = Modifier.weight(1f)) { Text("Process tour") }
                }
                OutlinedTextField(query, { query = it }, label = { Text("Search features and terms") },
                    singleLine = true, modifier = Modifier.fillMaxWidth().padding(top = 14.dp, bottom = 8.dp))
                if (matches.isEmpty() && terms.isEmpty())
                    Text("Nothing matches. Try \"layers\", \"section\" or \"BDI\".",
                        fontFamily = PlexSans, fontSize = 13.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 8.dp))
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (query.isEmpty() && catalog.learn.isNotEmpty()) {
                        item(key = "_learn") { GuideHeading("LEARN IN ORDER") }
                        items(catalog.learn, key = { "learn_" + it.key }) { l ->
                            Surface(onClick = { onLearn(l) }, shape = RoundedCornerShape(14.dp),
                                color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f)) {
                                Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp)) {
                                    Text(l.title, style = MaterialTheme.typography.titleSmall,
                                        color = MaterialTheme.colorScheme.onSurface)
                                    Text(l.body, fontFamily = PlexSans, fontSize = 12.5f.sp, lineHeight = 17.sp,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.padding(top = 2.dp))
                                }
                            }
                        }
                        item(key = "_features") { GuideHeading("FEATURES") }
                    }
                    items(matches, key = { it.id }) { s ->
                        Surface(onClick = { onOpen(s) }, shape = RoundedCornerShape(14.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant) {
                            Column(Modifier.fillMaxWidth().padding(14.dp)) {
                                Text(s.category, style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text(s.title, style = MaterialTheme.typography.titleMedium,
                                    color = MaterialTheme.colorScheme.onSurface,
                                    modifier = Modifier.padding(top = 2.dp))
                                Text(s.body, fontFamily = PlexSans, fontSize = 12.5f.sp, lineHeight = 17.sp,
                                    maxLines = 2, overflow = TextOverflow.Ellipsis,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.padding(top = 3.dp))
                            }
                        }
                    }
                    if (terms.isNotEmpty()) {
                        item(key = "_gloss") { GuideHeading("GLOSSARY") }
                        items(terms, key = { "g_" + it.term }) { t -> GlossRow(t) }
                    }
                }
            }
        }
    }
}

@Composable
private fun GuideHeading(text: String) {
    Text(text, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 6.dp).semantics { heading() })
}

/** A glossary entry: the term and what it stands for, then its definition. */
@Composable
fun GlossRow(t: GlossTerm, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 2.dp)) {
        Text(if (t.name == t.term) t.term else "${t.term} · ${t.name}", fontFamily = PlexSans,
            fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
        Text(t.text, fontFamily = PlexSans, fontSize = 12.5f.sp, lineHeight = 17.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 1.dp))
    }
}
