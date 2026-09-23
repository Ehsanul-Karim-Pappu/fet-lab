package io.github.ehsanulkarimpappu.fetlab

import android.content.Context
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathFillType
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
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

class GuideCatalog(val stops: List<GuideStop>, val tour: List<String>) {
    fun stop(id: String) = stops.first { it.id == id }
    companion object {
        fun load(ctx: Context): GuideCatalog {
            val root = JSONObject(ctx.assets.open("guide.json").bufferedReader().use { it.readText() })
            val arr = root.getJSONArray("stops")
            val stops = List(arr.length()) { i ->
                val s = arr.getJSONObject(i)
                GuideStop(s.getString("id"), s.getString("category"), s.getString("title"),
                    s.getString("body"), s.optInt("tab", -1), s.optString("gesture", "none"))
            }
            val t = root.getJSONArray("tour")
            return GuideCatalog(stops, List(t.length()) { t.getString(it) })
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
        place(0f)
        pinch?.let { ripple(it.first); ripple(it.second) }
        s.animateTo(1f, tween(ms / 2, easing = FastOutSlowInEasing)) { place(value) }
        s.animateTo(0f, tween(ms / 2, easing = FastOutSlowInEasing)) { place(value) }
        pinch = null
        delay(250)
    }

    suspend fun hideHand() { handAlpha.animateTo(0f, tween(260)) }

    /** Stops the hand. The spotlight hole is left where it was, so the veil can fade out
     *  around it instead of flashing the whole screen dark. */
    suspend fun reset() {
        spotId = ""; pinch = null; ripples.clear(); fresh = true
        handAlpha.snapTo(0f); press.snapTo(0f)
    }
}

/* =============================================================== hand ==== */

/** The hand of Material Design's "touch_app" icon (Apache License 2.0), in a 24-unit
 *  box with the fingertip at (11.5, 6). */
private const val HAND_PATH = "M18.84,15.87l-4.54,-2.26c-0.17,-0.07 -0.35,-0.11 -0.54,-0.11H13v-6" +
    "c0,-0.83 -0.67,-1.5 -1.5,-1.5S10,6.67 10,7.5v10.74l-3.43,-0.72c-0.08,-0.01 -0.15,-0.03 " +
    "-0.24,-0.03 -0.31,0 -0.59,0.13 -0.79,0.33l-0.79,0.8 4.94,4.94c0.27,0.27 0.65,0.44 1.06,0.44" +
    "h6.79c0.75,0 1.33,-0.55 1.44,-1.28l0.75,-5.27c0.01,-0.07 0.02,-0.14 0.02,-0.2 " +
    "0,-0.62 -0.38,-1.16 -0.91,-1.38z"

/**
 * The tour's pointing hand, drawn in its 24-unit space: a soft shadow that tucks in
 * under the finger as it [press]es (so it reads as touching the glass), light-to-shade
 * skin, a nail, knuckle and finger creases, an outline, and a cuff in the app's [tint].
 */
private fun DrawScope.drawHand(hand: Path, a: Float, press: Float, tint: Color) {
    val lift = 1f - 0.7f * press
    translate(0.9f * lift, 1.3f * lift) {
        drawPath(hand, Color.Black, alpha = 0.2f * a)
        for (w in floatArrayOf(0.5f, 1.0f, 1.6f))       // a cheap, version-proof blur
            drawPath(hand, Color.Black, alpha = 0.07f * a, style = Stroke(width = w, join = StrokeJoin.Round))
    }
    drawPath(hand, Brush.linearGradient(
        0f to Color(0xFFFFFFFF), 0.55f to Color(0xFFF1ECE4), 1f to Color(0xFFD5CCC0),
        start = Offset(6.25f, 6f), end = Offset(18.25f, 24f)), alpha = a)
    clipPath(hand) {
        // the far side of the finger turns away from the light, and the palm sits lower
        drawRect(Brush.horizontalGradient(0.55f to Color.Transparent, 1f to Color.Black.copy(alpha = 0.16f),
            startX = 10f, endX = 13f), topLeft = Offset(10f, 5f), size = Size(3f, 9f), alpha = a)
        drawPath(Path().apply { moveTo(13.2f, 13.3f); lineTo(20f, 16.6f); lineTo(20f, 25f); lineTo(13.2f, 25f); close() },
            Color.Black, alpha = 0.05f * a)
        val crease = Color(0xFF8E8173)
        val folds = Path().apply {
            moveTo(15.1f, 14.7f); quadraticBezierTo(15.6f, 15.8f, 15.3f, 17.0f)
            moveTo(16.7f, 15.5f); quadraticBezierTo(17.2f, 16.5f, 16.9f, 17.7f)
            moveTo(18.2f, 16.3f); quadraticBezierTo(18.6f, 17.2f, 18.4f, 18.2f)
        }
        drawPath(folds, crease, alpha = 0.65f * a, style = Stroke(width = 0.3f, cap = StrokeCap.Round))
        val knuckle = Path().apply { moveTo(10.45f, 10.9f); quadraticBezierTo(11.5f, 11.3f, 12.55f, 10.9f) }
        drawPath(knuckle, crease, alpha = 0.55f * a, style = Stroke(width = 0.26f, cap = StrokeCap.Round))
        val cuff = Path().apply { moveTo(9.2f, 22.35f); lineTo(19.6f, 21.25f); lineTo(20.4f, 26f); lineTo(9.6f, 27f); close() }
        drawPath(cuff, Brush.verticalGradient(listOf(tint, lerp(tint, Color.Black, 0.45f)), startY = 21.2f, endY = 24.5f), alpha = a)
        drawLine(lerp(tint, Color.White, 0.5f), Offset(9.2f, 22.35f), Offset(19.6f, 21.25f), strokeWidth = 0.32f, alpha = 0.8f * a)
    }
    drawRoundRect(Color(0xFFFBF6F1), topLeft = Offset(10.75f, 6.45f), size = Size(1.5f, 1.8f),
        cornerRadius = CornerRadius(0.72f), alpha = a)
    drawRoundRect(Color(0xFFCFC4B7), topLeft = Offset(10.75f, 6.45f), size = Size(1.5f, 1.8f),
        cornerRadius = CornerRadius(0.72f), alpha = a, style = Stroke(width = 0.14f))
    drawOval(Color.White, topLeft = Offset(10.85f, 6.6f), size = Size(0.4f, 0.9f), alpha = a)
    drawPath(hand, Color(0xFF6F655A), alpha = 0.85f * a, style = Stroke(width = 0.3f, join = StrokeJoin.Round))
}

/* ============================================================ overlay ==== */

/**
 * The scrim with a hole where the current section is, a soft pulsing edge around the
 * hole, the ripples, and the hand. It never takes touches — everything underneath
 * stays live, and the tour card sits above it.
 */
@Composable
fun TourOverlay(player: TourPlayer, active: Boolean, tint: Color, modifier: Modifier = Modifier) {
    val hand = remember { PathParser().parsePathString(HAND_PATH).toPath() }
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
        val hole = if (s.isEmpty) null
            else RoundRect(s.translate(-o.x, -o.y).inflate(8.dp.toPx()), CornerRadius(16.dp.toPx()))

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
            // Work in the icon's own 24-unit space, pivoting on the fingertip at (11.5, 6):
            // tilted a little, like a real pointing hand, and slightly smaller when pressed.
            val u = 64.dp.toPx() / 24f * (1f - 0.1f * press)
            translate(tip.x, tip.y) {
                rotate(-14f, pivot = Offset.Zero) {
                    scale(u, u, pivot = Offset.Zero) {
                        translate(-11.5f, -6f) { drawHand(hand, a, press, tint) }
                    }
                }
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

/** Searchable index of everything the app can do, each row jumping straight to it. */
@Composable
fun FeatureGuide(catalog: GuideCatalog, onOpen: (GuideStop) -> Unit, onTour: () -> Unit, onClose: () -> Unit) {
    var query by remember { mutableStateOf("") }
    val matches = remember(query) {
        catalog.stops.filter { "${it.title} ${it.body} ${it.category}".contains(query, ignoreCase = true) }
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
                OutlinedButton(onClick = onTour, modifier = Modifier.fillMaxWidth().padding(top = 10.dp)) {
                    Text("Replay the guided tour")
                }
                OutlinedTextField(query, { query = it }, label = { Text("Search features") },
                    singleLine = true, modifier = Modifier.fillMaxWidth().padding(top = 14.dp, bottom = 8.dp))
                if (matches.isEmpty())
                    Text("No matching feature. Try \"layers\", \"section\" or \"parasitics\".",
                        fontFamily = PlexSans, fontSize = 13.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 8.dp))
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
                }
            }
        }
    }
}
