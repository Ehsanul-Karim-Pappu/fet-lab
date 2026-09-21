package io.github.ehsanulkarimpappu.fetlab

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.opengl.GLSurfaceView
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.Crossfade
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset as GOffset
import androidx.compose.ui.geometry.Size as GSize
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.roundToInt

/* ======================================================= scene catalogue == */

private val DEV_KEYS = listOf("fin" to "FinFET", "ns" to "Nanosheet", "fs" to "Forksheet",
    "cfet_mono" to "CFET", "cmp" to "Compare")
private val INV_KEYS = listOf("inv_fin" to "FinFET", "inv_ns" to "Nanosheet",
    "inv_fs" to "Forksheet", "inv_cfet" to "CFET", "inv_cmp" to "Compare")
private val SHOW_KEYS = listOf("show_fin" to "FinFET", "show_ns" to "Nanosheet",
    "show_fs" to "Forksheet", "show_cfet" to "CFET", "show_cmp" to "Compare")
private val MODES = listOf("Device", "Inverter", "Layout")
private val TABS = listOf("Views", "Section", "Layers", "Specs", "Story")
/** Guide stop ids that live on the tool sheet, as opposed to the header or the stage. */
private val TOOL_STOPS = setOf("views", "section", "layers", "specs", "story")

private fun keysFor(mode: Int) = when (mode) { 0 -> DEV_KEYS; 1 -> INV_KEYS; else -> SHOW_KEYS }
private fun firstOf(mode: Int) = keysFor(mode).first().first

/** The technology a scene shows, with the viewing mode stripped off. The two CFET
 *  scenes are one technology: only the device mode splits them into mono/sequential. */
private fun techOf(key: String): String {
    val k = key.removePrefix("inv_").removePrefix("show_")
    return if (k.startsWith("cfet")) "cfet" else k
}

/** The scene that shows [tech] in [mode], or null when that mode has no equivalent. */
private fun sceneFor(mode: Int, tech: String): String? =
    keysFor(mode).firstOrNull { techOf(it.first) == tech }?.first

/* ============================================================== boot ===== */

@Composable
fun FetLabRoot(dynamic: Boolean, onDynamic: (Boolean) -> Unit) {
    val ctx = LocalContext.current
    var payload by remember { mutableStateOf<Pair<Library, Renderer>?>(null) }

    LaunchedEffect(Unit) {
        payload = withContext(Dispatchers.Default) {
            val lib = Library.load(ctx)
            lib to Renderer(lib)
        }
    }

    Crossfade(targetState = payload, animationSpec = tween(420), label = "boot") { p ->
        if (p == null) BootScreen() else FetLabApp(p.first, p.second, dynamic, onDynamic)
    }
}

@Composable
private fun BootScreen() {
    var on by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { on = true }
    val scale by animateFloatAsState(if (on) 1f else 0.86f,
        spring(dampingRatio = 0.6f, stiffness = Spring.StiffnessLow), label = "bootScale")
    val alpha by animateFloatAsState(if (on) 1f else 0f, tween(500), label = "bootAlpha")

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background),
        contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.graphicsLayer { scaleX = scale; scaleY = scale; this.alpha = alpha }) {
            Mark(Modifier.size(92.dp))
            Spacer(Modifier.height(22.dp))
            Text("FET Lab", style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onBackground)
            Spacer(Modifier.height(6.dp))
            Text("building geometry", style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/** The stacked-sheet mark, drawn rather than shipped as a bitmap. */
@Composable
private fun Mark(modifier: Modifier = Modifier) {
    // The launcher artwork, so the header, the boot screen and the home screen
    // all show the same thing.
    Image(painter = painterResource(R.drawable.brand_mark), contentDescription = null,
        modifier = modifier, contentScale = ContentScale.Crop)
}

/* ============================================================== camera === */

private class Cam(val az: Float, val el: Float, val r: Float,
                  val tx: Float, val ty: Float, val tz: Float,
                  val cx: Float, val cy: Float, val cz: Float)

private fun lerp(a: Float, b: Float, t: Float) = a + (b - a) * t

private fun lerpCam(a: Cam, b: Cam, t: Float): Cam {
    var dAz = b.az - a.az
    while (dAz > PI.toFloat()) dAz -= (2 * PI).toFloat()
    while (dAz < -PI.toFloat()) dAz += (2 * PI).toFloat()
    return Cam(a.az + dAz * t, lerp(a.el, b.el, t), lerp(a.r, b.r, t),
        lerp(a.tx, b.tx, t), lerp(a.ty, b.ty, t), lerp(a.tz, b.tz, t),
        lerp(a.cx, b.cx, t), lerp(a.cy, b.cy, t), lerp(a.cz, b.cz, t))
}

private fun frac(v: Float, lo: Float, hi: Float) = ((v - lo) / (hi - lo)).coerceIn(0f, 1f)

/* ================================================================ app ==== */

@Composable
fun FetLabApp(lib: Library, renderer: Renderer, dynamic: Boolean, onDynamic: (Boolean) -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val haptic = LocalHapticFeedback.current
    val density = LocalDensity.current

    val glView = remember {
        GLSurfaceView(ctx).apply {
            setEGLContextClientVersion(2)
            preserveEGLContextOnPause = true
            setRenderer(renderer)
            renderMode = GLSurfaceView.RENDERMODE_WHEN_DIRTY
        }
    }
    fun draw() = glView.requestRender()

    var mode by rememberSaveable { mutableStateOf(0) }
    var sceneKey by rememberSaveable { mutableStateOf("fin") }
    var cfetSeq by rememberSaveable { mutableStateOf(false) }
    var viewKey by rememberSaveable { mutableStateOf("") }
    var cx by rememberSaveable { mutableStateOf(1f) }
    var cy by rememberSaveable { mutableStateOf(1f) }
    var cz by rememberSaveable { mutableStateOf(1f) }
    var explodeF by rememberSaveable { mutableStateOf(0f) }
    var ghost by rememberSaveable { mutableStateOf(false) }
    var showDims by rememberSaveable { mutableStateOf(true) }
    var texture by rememberSaveable { mutableStateOf(true) }
    var edges by rememberSaveable { mutableStateOf(true) }
    var lightBg by rememberSaveable { mutableStateOf(false) }
    var spin by rememberSaveable { mutableStateOf(false) }
    var parPick by rememberSaveable { mutableStateOf<String?>(null) }

    // Hands-off rotation, for leaving the model turning on a desk or a projector.
    LaunchedEffect(spin) {
        while (spin) { withFrameNanos { }; renderer.az += 0.0032f; draw() }
    }
    var input by rememberSaveable { mutableStateOf(0) }
    var tab by rememberSaveable { mutableStateOf(0) }
    var selected by remember { mutableStateOf<Part?>(null) }
    var showAbout by rememberSaveable { mutableStateOf(false) }
    var layerTick by remember { mutableIntStateOf(0) }
    // Phone layout only: the control sheet floats over the stage instead of shrinking it.
    // 0 peek (handle only) · 1 open (normal working height) · 2 expanded (reading height).
    var sheetLevel by rememberSaveable { mutableIntStateOf(1) }
    var stageInset by remember { mutableStateOf(0.dp) }

    // --- guided tour and feature list --------------------------------------
    val catalog = remember { GuideCatalog.load(ctx) }
    var showHelp by rememberSaveable { mutableStateOf(false) }
    var tourStep by rememberSaveable { mutableIntStateOf(-1) }
    var welcomeSeen by remember { mutableStateOf(tourSeen(ctx)) }
    val tourFocus = if (tourStep in catalog.tour.indices) catalog.tour[tourStep] else ""
    fun applyTourStep(i: Int) {
        val stop = catalog.stop(catalog.tour[i])
        // Header steps want the full stage visible; tool steps open the tab they teach.
        if (stop.tab >= 0) { tab = stop.tab; sheetLevel = if (stop.id == "story") 2 else maxOf(sheetLevel, 1) }
        else sheetLevel = 0
    }
    fun startTour() {
        if (!welcomeSeen) { markTourSeen(ctx); welcomeSeen = true }
        showHelp = false
        tourStep = 0; applyTourStep(0)
    }
    fun exitTour() { tourStep = -1 }
    fun tourNext() {
        if (tourStep >= catalog.tour.lastIndex) exitTour() else { tourStep++; applyTourStep(tourStep) }
    }
    fun tourBack() { if (tourStep > 0) { tourStep--; applyTourStep(tourStep) } }
    fun openFeature(s: GuideStop) {
        showHelp = false; tourStep = -1
        if (s.tab >= 0) { tab = s.tab; sheetLevel = if (s.id == "story") 2 else maxOf(sheetLevel, 1) }
        else sheetLevel = 0
    }

    val scene = lib.scene(sceneKey)
    val stageBg = if (lightBg) Stage.light else Stage.dark
    val ink = if (lightBg) Stage.inkOnLight else Stage.inkOnDark
    val dim = if (lightBg) Stage.dimOnLight else Stage.dimOnDark
    val line = if (lightBg) Stage.lineOnLight else Stage.lineOnDark
    val glass = if (lightBg) Color.White.copy(alpha = .92f) else Stage.dark.copy(alpha = .88f)
    val nameInk = if (lightBg) Color(0xFF121820) else Color.White

    // --- scene transition scrim -------------------------------------------
    var scrim by remember { mutableFloatStateOf(0f) }
    val scrimA by animateFloatAsState(scrim, tween(if (scrim > .5f) 130 else 300), label = "scrim")

    // --- camera flight ------------------------------------------------------
    var flight by remember { mutableStateOf<Job?>(null) }
    fun cameraNow() = Cam(renderer.az, renderer.el, renderer.dist,
        renderer.target[0], renderer.target[1], renderer.target[2], cx, cy, cz)

    fun applyCam(sc: Scene, c: Cam) {
        renderer.az = c.az; renderer.el = c.el; renderer.dist = c.r
        renderer.target = floatArrayOf(c.tx, c.ty, c.tz)
        cx = c.cx; cy = c.cy; cz = c.cz
        renderer.clip = floatArrayOf(
            sc.lo[0] + (sc.hi[0] - sc.lo[0]) * c.cx,
            sc.lo[1] + (sc.hi[1] - sc.lo[1]) * c.cy,
            sc.lo[2] + (sc.hi[2] - sc.lo[2]) * c.cz)
        renderer.capsDirty = true
    }

    fun camOf(sc: Scene, v: ViewPreset): Cam {
        val c = v.clip
        return Cam(v.az, v.el, renderer.viewDist(sc, v.az, v.el, v.r), v.tgt[0], v.tgt[1], v.tgt[2],
            if (c?.get(0) != null) frac(c[0]!!, sc.lo[0], sc.hi[0]) else 1f,
            if (c?.get(1) != null) frac(c[1]!!, sc.lo[1], sc.hi[1]) else 1f,
            if (c?.get(2) != null) frac(c[2]!!, sc.lo[2], sc.hi[2]) else 1f)
    }

    fun goToView(sc: Scene, v: ViewPreset, animate: Boolean) {
        viewKey = v.key
        for (p in sc.parts) p.visible = !v.off.contains(p.id)
        layerTick++
        val to = camOf(sc, v)
        flight?.cancel()
        if (!animate) { applyCam(sc, to); draw(); return }
        val from = cameraNow()
        flight = scope.launch {
            var t0 = 0L
            val dur = 520_000_000f
            while (true) {
                val now = withFrameNanos { it }
                if (t0 == 0L) t0 = now
                val raw = ((now - t0).toFloat() / dur).coerceIn(0f, 1f)
                val e = raw * raw * (3f - 2f * raw)
                applyCam(sc, lerpCam(from, to, e))
                draw()
                if (raw >= 1f) break
            }
        }
    }

    fun openScene(key: String, animate: Boolean) {
        val sc = lib.scene(key)
        sceneKey = key
        mode = when { key.startsWith("inv_") -> 1; key.startsWith("show_") -> 2; else -> 0 }
        renderer.scene = sc
        selected = null; renderer.highlight = null
        parPick = null; renderer.par = null      // a highlight must not outlive its scene
        explodeF = 0f; renderer.explode = 0f
        renderer.lightBg = lightBg      // dark stage everywhere; the switch still works
        goToView(sc, sc.views.first(), animate = false)
        if (animate) draw()
    }

    fun switchScene(key: String) {
        if (key == sceneKey) return
        flight?.cancel()
        scope.launch {
            scrim = 1f
            kotlinx.coroutines.delay(140)
            openScene(key, animate = true)
            scrim = 0f
        }
    }

    LaunchedEffect(Unit) { openScene(sceneKey, animate = false) }

    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val obs = LifecycleEventObserver { _, e ->
            when (e) {
                Lifecycle.Event.ON_RESUME -> glView.onResume()
                Lifecycle.Event.ON_PAUSE -> glView.onPause()
                else -> {}
            }
        }
        lifecycleOwner.lifecycle.addObserver(obs)
        onDispose { lifecycleOwner.lifecycle.removeObserver(obs) }
    }

    /* --------------------------------------------------------- pieces --- */

    val header = @Composable {
        Column {
            Row(Modifier.fillMaxWidth().padding(start = 18.dp, end = 14.dp, top = 12.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Mark(Modifier.size(30.dp).clip(RoundedCornerShape(8.dp)))
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(scene.name, style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.onBackground,
                        maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(scene.tag, style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                Box(Modifier.size(42.dp).clip(CircleShape)
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .clickable { showAbout = true }, contentAlignment = Alignment.Center) {
                    Text("i", fontFamily = Mono, fontSize = 16.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(Modifier.width(8.dp))
                Box(Modifier.size(42.dp).clip(CircleShape)
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .clickable { showHelp = true }, contentAlignment = Alignment.Center) {
                    Text("?", fontFamily = Mono, fontSize = 16.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Spacer(Modifier.height(12.dp))
            Dimmable(tourStep >= 0 && tourFocus != "modes") {
                Box(Modifier.padding(horizontal = 16.dp)) {
                    Segmented(MODES, mode) { i ->
                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        // Only the viewing mode changes: the technology on screen carries across.
                        val tech = techOf(sceneKey)
                        val next = sceneFor(i, tech) ?: firstOf(i)
                        switchScene(if (i == 0 && tech == "cfet" && cfetSeq) "cfet_seq" else next)
                    }
                }
            }
            Spacer(Modifier.height(10.dp))
            Dimmable(tourStep >= 0 && tourFocus != "arch") {
            Column {
            LazyRow(contentPadding = PaddingValues(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(keysFor(mode)) { (k, label) ->
                    val active = sceneKey == k || (k == "cfet_mono" && sceneKey == "cfet_seq")
                    Chip(label, active) {
                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        switchScene(if (k == "cfet_mono" && cfetSeq) "cfet_seq" else k)
                    }
                }
            }
            AnimatedVisibility(visible = sceneKey.startsWith("cfet"),
                enter = fadeIn() + expandVertically(), exit = fadeOut() + shrinkVertically()) {
                Box(Modifier.padding(start = 16.dp, end = 16.dp, top = 10.dp)) {
                    Segmented(listOf("Monolithic", "Sequential"),
                        if (sceneKey == "cfet_seq") 1 else 0) { i ->
                        cfetSeq = i == 1
                        switchScene(if (i == 1) "cfet_seq" else "cfet_mono")
                    }
                }
            }
            }
            }
            Spacer(Modifier.height(12.dp))
        }
    }

    val stage = @Composable { mod: Modifier ->
        Box(mod.clip(RoundedCornerShape(20.dp)).background(stageBg)
            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(20.dp))) {

            AndroidView(factory = { glView }, modifier = Modifier.fillMaxSize())

            Box(Modifier.matchParentSize().pointerInput(sceneKey) {
                awaitEachGesture {
                    val down = awaitFirstDown(requireUnconsumed = false)
                    flight?.cancel()
                    var maxPointers = 1
                    var moved = 0f
                    var prevCentroid = down.position
                    var prevSpread = 0f
                    var prevCount = 1
                    while (true) {
                        val ev = awaitPointerEvent()
                        val pressed = ev.changes.filter { it.pressed }
                        if (pressed.isEmpty()) break
                        if (pressed.size > maxPointers) maxPointers = pressed.size
                        var sx = 0f; var sy = 0f
                        for (c in pressed) { sx += c.position.x; sy += c.position.y }
                        val centroid = androidx.compose.ui.geometry.Offset(sx / pressed.size, sy / pressed.size)
                        val spread = if (pressed.size >= 2)
                            (pressed[0].position - pressed[1].position).getDistance() else 0f
                        if (pressed.size != prevCount) {
                            // A finger arrived or left. The centroid and the spread both jump in
                            // that one frame, so re-base on the new gesture instead of treating
                            // the jump as movement — otherwise the model leaps across the screen.
                            prevCount = pressed.size
                            prevCentroid = centroid
                            prevSpread = spread
                            for (c in ev.changes) c.consume()
                            continue
                        }
                        val d = centroid - prevCentroid
                        moved += abs(d.x) + abs(d.y)
                        if (pressed.size == 1) {
                            // Viewport-relative, so the feel does not change with screen density:
                            // a full-width swipe is about 180 degrees.
                            val w = maxOf(renderer.viewW, 1); val h = maxOf(renderer.viewH, 1)
                            renderer.az -= d.x * (3.2f / w)
                            renderer.el = (renderer.el + d.y * (2.6f / h)).coerceIn(-1.45f, 1.45f)
                        } else {
                            // One pixel of finger travel moves the model one pixel: pan tracks
                            // the fingers instead of racing ahead of them.
                            val s = renderer.worldPerPixel()
                            renderer.panBy(-d.x * s, d.y * s)
                            if (prevSpread > 1f && spread > 1f)
                                renderer.dist = (renderer.dist * prevSpread / spread).coerceIn(40f, 3000f)
                        }
                        prevCentroid = centroid; prevSpread = spread
                        for (c in ev.changes) c.consume()
                        draw()
                    }
                    // Tap slop in physical pixels, so it is the same distance on any screen.
                    val slop = maxOf(renderer.viewW, renderer.viewH) * 0.012f
                    if (maxPointers == 1 && moved < slop) {
                        val hit = renderer.pick(down.position.x, down.position.y)
                        selected = hit; renderer.highlight = hit
                        if (hit != null) haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        draw()
                    }
                }
            })

            LaunchedEffect(showDims, viewKey) {
                renderer.callouts = showDims; renderer.viewKey = viewKey; draw()
            }
            if (showDims && scene.callouts.isNotEmpty())
                CalloutOverlay(renderer, scene, viewKey, lightBg, bottomInset = stageInset)

            Text(scene.views.firstOrNull { it.key == viewKey }?.label ?: "",
                style = MaterialTheme.typography.labelSmall, color = dim,
                modifier = Modifier.align(Alignment.TopStart).padding(14.dp))

            // Gestures are not discoverable, so say them once per scene and then get out of the way.
            var hint by remember(sceneKey) { mutableStateOf(true) }
            LaunchedEffect(sceneKey) { delay(4500); hint = false }
            AnimatedVisibility(visible = hint,
                enter = fadeIn(tween(500)), exit = fadeOut(tween(700)),
                modifier = Modifier.align(Alignment.TopEnd)) {
                Text("drag to orbit · two fingers to pan · pinch to zoom · tap a layer",
                    style = MaterialTheme.typography.labelSmall, color = dim,
                    textAlign = TextAlign.End, lineHeight = 14.sp,
                    modifier = Modifier.padding(14.dp).widthIn(max = 190.dp))
            }

            AnimatedVisibility(visible = selected != null,
                enter = fadeIn(tween(180)) + slideInVertically(tween(220)) { it / 3 },
                exit = fadeOut(tween(140)) + slideOutVertically(tween(180)) { it / 3 },
                modifier = Modifier.align(Alignment.BottomStart).padding(bottom = stageInset)) {
                val p = selected
                Surface(color = glass, shape = RoundedCornerShape(14.dp),
                    border = BorderStroke(1.dp, line),
                    modifier = Modifier.padding(12.dp).widthIn(max = 240.dp)) {
                    Column(Modifier.padding(horizontal = 13.dp, vertical = 10.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Box(Modifier.size(11.dp).clip(RoundedCornerShape(3.dp))
                                .background(matColor(lib, p?.material ?: "")))
                            Text(p?.name ?: "", color = nameInk, fontSize = 13.sp,
                                fontFamily = PlexSans, fontWeight = FontWeight.SemiBold,
                                maxLines = 2, overflow = TextOverflow.Ellipsis)
                        }
                        Spacer(Modifier.height(2.dp))
                        Text("${lib.materials[p?.material]?.label ?: ""} · ${p?.group ?: ""}",
                            color = dim, fontFamily = Mono, fontSize = 10.5f.sp,
                            maxLines = 2, overflow = TextOverflow.Ellipsis)
                    }
                }
            }

            AnimatedVisibility(visible = scene.logic,
                enter = fadeIn() + slideInVertically { it }, exit = fadeOut() + slideOutVertically { it },
                modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = stageInset)) {
                LogicBar(input, glass, line, ink, dim, lightBg) { v ->
                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                    input = v; renderer.input = v; renderer.capsDirty = true; draw()
                }
            }

            if (scrimA > 0.005f)
                Box(Modifier.matchParentSize().background(stageBg.copy(alpha = scrimA)))
        }
    }

    val sheetSpring = spring<Dp>(dampingRatio = 0.85f, stiffness = Spring.StiffnessMediumLow)
    // Story reads long-form, so give it the reading height; every other tab just needs
    // to be open. Either way this never *closes* a sheet the user opened wider by hand.
    fun openSheet() {
        sheetLevel = if (tab == 4) maxOf(sheetLevel, 2) else maxOf(sheetLevel, 1)
    }

    val controlTabs = @Composable { mod: Modifier ->
        Box(mod) {
            Segmented(TABS, tab) { tab = it; openSheet() }
        }
    }

    val controlBody = @Composable { mod: Modifier ->
        Box(mod) {
            Crossfade(targetState = tab, animationSpec = tween(220), label = "tab",
                modifier = Modifier.fillMaxSize()) { t ->
                Box(Modifier.fillMaxSize().padding(horizontal = 14.dp)) {
                    when (t) {
                        0 -> ViewsTab(scene, viewKey) { v ->
                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                            goToView(scene, v, animate = true)
                        }
                        1 -> SectionTab(scene, cx, cy, cz, explodeF, ghost, showDims, texture,
                            edges, lightBg, dynamic, spin,
                            onClip = { ax, v ->
                                flight?.cancel()
                                when (ax) { 0 -> cx = v; 1 -> cy = v; else -> cz = v }
                                renderer.clip = floatArrayOf(
                                    scene.lo[0] + (scene.hi[0] - scene.lo[0]) * cx,
                                    scene.lo[1] + (scene.hi[1] - scene.lo[1]) * cy,
                                    scene.lo[2] + (scene.hi[2] - scene.lo[2]) * cz)
                                renderer.capsDirty = true; draw()
                            },
                            onExplode = { explodeF = it; renderer.explode = it * 16f
                                renderer.capsDirty = true; draw() },
                            onGhost = { ghost = it; renderer.ghost = it; draw() },
                            onDims = { showDims = it },
                            onTex = { texture = it; renderer.texture = it
                                renderer.capsDirty = true; draw() },
                            onEdges = { edges = it; renderer.edges = it; draw() },
                            onLight = { lightBg = it; renderer.lightBg = it; draw() },
                            onDynamic = onDynamic,
                            onSpin = { spin = it },
                            onReset = {
                                for (p in scene.parts) p.visible = true
                                layerTick++
                                explodeF = 0f; renderer.explode = 0f
                                ghost = false; renderer.ghost = false
                                showDims = true
                                texture = true; renderer.texture = true
                                edges = true; renderer.edges = true
                                lightBg = false; renderer.lightBg = false
                                spin = false
                                goToView(scene, scene.views.first(), animate = true)
                            })
                        2 -> LayersTab(lib, scene, layerTick) { parts, visible ->
                            for (p in parts) p.visible = visible
                            layerTick++
                            renderer.capsDirty = true; draw()
                        }
                        3 -> SpecsTab(scene, parPick) { t ->
                            parPick = t?.id
                            renderer.par = t
                            renderer.capsDirty = true; draw()
                        }
                        else -> StoryTab(scene)
                    }
                }
            }
        }
    }

    /* ----------------------------------------------------------- layout -- */

    BoxWithConstraints(Modifier.fillMaxSize()
        .background(MaterialTheme.colorScheme.background).safeDrawingPadding()) {
        val wide = maxWidth >= 680.dp
        if (wide) {
            Row(Modifier.fillMaxSize()) {
                Column(Modifier.width(330.dp).fillMaxHeight()) {
                    header()
                    Dimmable(tourStep >= 0 && tourFocus !in TOOL_STOPS, Modifier.weight(1f).fillMaxWidth()) {
                        Column(Modifier.fillMaxSize()) {
                            controlTabs(Modifier.fillMaxWidth().padding(horizontal = 16.dp))
                            Spacer(Modifier.height(10.dp))
                            controlBody(Modifier.weight(1f).fillMaxWidth().padding(bottom = 12.dp))
                        }
                    }
                }
                Dimmable(tourStep >= 0 && tourFocus != "stage",
                    Modifier.weight(1f).fillMaxHeight().padding(end = 14.dp, bottom = 14.dp, top = 12.dp)) {
                    stage(Modifier.fillMaxSize())
                }
            }
        } else {
            Column(Modifier.fillMaxSize()) {
                header()
                // The stage keeps the full remaining height; the control sheet floats on
                // top of it instead of squeezing it, so the model never gets small just
                // because a tool is open.
                BoxWithConstraints(Modifier.weight(1f).fillMaxWidth()) {
                    val bodyHeight by animateDpAsState(
                        when (sheetLevel) { 0 -> 0.dp; 1 -> maxHeight * 0.36f; else -> maxHeight * 0.68f },
                        sheetSpring, label = "sheetHeight")
                    val sheetAlpha by animateFloatAsState(
                        if (sheetLevel > 0) 0.95f else 0.9f, tween(200), label = "sheetAlpha")

                    Dimmable(tourStep >= 0 && tourFocus != "stage",
                        Modifier.fillMaxSize().padding(horizontal = 12.dp, vertical = 10.dp)) {
                        stage(Modifier.fillMaxSize())
                    }

                    var dragDistance by remember { mutableFloatStateOf(0f) }
                    Dimmable(tourStep >= 0 && tourFocus !in TOOL_STOPS,
                        Modifier.align(Alignment.BottomCenter).fillMaxWidth()
                            .clip(RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp))) {
                        Surface(color = MaterialTheme.colorScheme.surface.copy(alpha = sheetAlpha),
                            shape = RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp),
                            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                            modifier = Modifier.fillMaxWidth()
                                .shadow(14.dp, RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp))
                                .onSizeChanged { stageInset = with(density) { it.height.toDp() } }) {
                            Column {
                                Box(Modifier.fillMaxWidth().height(26.dp).draggable(
                                    orientation = Orientation.Vertical,
                                    state = rememberDraggableState { d -> dragDistance += d },
                                    onDragStarted = { dragDistance = 0f },
                                    onDragStopped = {
                                        val step = with(density) { 28.dp.toPx() }
                                        if (dragDistance > step) sheetLevel = (sheetLevel - 1).coerceAtLeast(0)
                                        else if (dragDistance < -step) sheetLevel = (sheetLevel + 1).coerceAtMost(2)
                                    }
                                ).clickable {
                                    sheetLevel = if (sheetLevel == 0) 1 else 0
                                }, contentAlignment = Alignment.Center) {
                                    Box(Modifier.width(38.dp).height(4.dp).clip(CircleShape)
                                        .background(MaterialTheme.colorScheme.outline))
                                }
                                controlTabs(Modifier.fillMaxWidth().padding(horizontal = 14.dp))
                                Spacer(Modifier.height(6.dp))
                                controlBody(Modifier.fillMaxWidth().height(bodyHeight).padding(bottom = 8.dp))
                            }
                        }
                    }
                }
            }
        }

        AnimatedVisibility(visible = showAbout,
            enter = fadeIn(tween(200)) + slideInVertically(tween(280)) { it / 6 },
            exit = fadeOut(tween(160)) + slideOutVertically(tween(220)) { it / 6 }) {
            AboutScreen { showAbout = false }
        }

        if (tourStep in catalog.tour.indices) {
            val stop = catalog.stop(tourFocus)
            // The card sits opposite whatever it is teaching, so it never covers it:
            // header and stage steps point from the bottom, tool steps from the top.
            val atBottom = tourFocus !in TOOL_STOPS
            TourCard(stop, tourStep, catalog.tour.size,
                modifier = Modifier
                    .align(if (atBottom) Alignment.BottomCenter else Alignment.TopCenter)
                    .padding(16.dp)
                    .then(if (wide) Modifier.width(380.dp) else Modifier.fillMaxWidth()),
                onBack = { tourBack() }, onNext = { tourNext() }, onExit = { exitTour() })
        }
        if (!welcomeSeen && tourStep < 0 && !showHelp)
            WelcomeGuide(onStart = { startTour() }, onSkip = { markTourSeen(ctx); welcomeSeen = true })
        if (showHelp)
            FeatureGuide(catalog, onOpen = { s -> openFeature(s) },
                onTour = { startTour() }, onClose = { showHelp = false })
    }
}

/* ============================================================== about ==== */

@Composable
private fun AboutScreen(onClose: () -> Unit) {
    val ctx = LocalContext.current
    val references = remember {
        org.json.JSONObject(ctx.assets.open("references.json").bufferedReader().use { it.readText() })
    }
    fun open(intent: Intent) {
        try { ctx.startActivity(intent) } catch (e: ActivityNotFoundException) { /* no handler */ }
    }
    fun web(url: String) = open(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    fun mail() = open(Intent(Intent.ACTION_SENDTO).apply {
        data = Uri.parse("mailto:${AppInfo.EMAIL}")
        putExtra(Intent.EXTRA_SUBJECT, "${AppInfo.NAME} ${BuildConfig.VERSION_NAME}")
    })

    Surface(color = MaterialTheme.colorScheme.background, modifier = Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().safeDrawingPadding()) {
            Row(Modifier.fillMaxWidth().padding(start = 18.dp, end = 12.dp, top = 10.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Text("About", style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onBackground, modifier = Modifier.weight(1f))
                Box(Modifier.size(42.dp).clip(CircleShape)
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .clickable { onClose() }, contentAlignment = Alignment.Center) {
                    Text("✕", fontSize = 15.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            LazyColumn(Modifier.fillMaxSize(),
                contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = 14.dp, bottom = 36.dp)) {
                item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Mark(Modifier.size(64.dp).clip(RoundedCornerShape(16.dp)))
                        Spacer(Modifier.width(16.dp))
                        Column {
                            Text(AppInfo.NAME, style = MaterialTheme.typography.titleLarge,
                                color = MaterialTheme.colorScheme.onBackground)
                            Text(AppInfo.TAGLINE, fontFamily = PlexSans, fontSize = 13.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text("Version ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
                                fontFamily = Mono, fontSize = 11.5f.sp,
                                color = MaterialTheme.colorScheme.primary)
                        }
                    }
                    Spacer(Modifier.height(24.dp))
                }
                item {
                    AboutCard {
                        AboutLabel("Developed by")
                        Text(AppInfo.DEVELOPER, fontFamily = PlexSans, fontSize = 15.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.onSurface)
                        Spacer(Modifier.height(14.dp))
                        AboutAction("Email", AppInfo.EMAIL) { mail() }
                    }
                    Spacer(Modifier.height(14.dp))
                }
                item {
                    AboutCard {
                        AboutLabel("Source and support")
                        Text("Found a bug, or the geometry looks wrong? Open an issue on the " +
                             "repository — that is the fastest way to get it fixed, and it keeps " +
                             "the fix visible to everyone else.",
                            fontFamily = PlexSans, fontSize = 13.sp, lineHeight = 19.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(14.dp))
                        AboutAction("Repository", AppInfo.SLUG) { web(AppInfo.REPO) }
                        Spacer(Modifier.height(10.dp))
                        AboutAction("Report an issue", "Open a ticket") { web(AppInfo.ISSUES) }
                        Spacer(Modifier.height(10.dp))
                        AboutAction("More by this developer", "github.com/ehsanul-karim-pappu") {
                            web(AppInfo.PROFILE)
                        }
                        Spacer(Modifier.height(10.dp))
                        AboutAction("Privacy policy", "What this app collects") { web(AppInfo.PRIVACY) }
                    }
                    Spacer(Modifier.height(14.dp))
                }
                item {
                    AboutCard {
                        AboutLabel("Credits")
                        AppInfo.ATTRIBUTIONS.forEachIndexed { i, a ->
                            if (i > 0) Spacer(Modifier.height(9.dp))
                            Text("· $a", fontFamily = PlexSans, fontSize = 12.5f.sp,
                                lineHeight = 18.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Spacer(Modifier.height(14.dp))
                        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                        Spacer(Modifier.height(12.dp))
                        Text(AppInfo.LICENSE, fontFamily = Mono, fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                item {
                    AboutCard {
                        AboutLabel("Technical references")
                        Text(references.getString("scope"), fontFamily = PlexSans,
                            fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        val sources = references.getJSONArray("sources")
                        for (i in 0 until sources.length()) {
                            val ref = sources.getJSONObject(i)
                            Spacer(Modifier.height(12.dp))
                            AboutAction(ref.getString("id") + " · " + ref.getString("title"),
                                ref.getString("publisher") + " — " + ref.getString("supports")) {
                                web(ref.getString("url"))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun AboutCard(content: @Composable ColumnScope.() -> Unit) {
    Surface(color = MaterialTheme.colorScheme.surface, shape = RoundedCornerShape(18.dp),
        tonalElevation = 1.dp, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), content = content)
    }
}

@Composable
private fun AboutLabel(text: String) {
    Text(text, style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(bottom = 8.dp))
}

@Composable
private fun AboutAction(title: String, subtitle: String, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).clip(RoundedCornerShape(12.dp))
        .clickable { onClick() }, verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, fontFamily = PlexSans, fontSize = 14.sp, fontWeight = FontWeight.Medium,
                color = MaterialTheme.colorScheme.onSurface)
            Text(subtitle, fontFamily = Mono, fontSize = 11.5f.sp, maxLines = 1,
                overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.primary)
        }
        Text("↗", fontSize = 15.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/* ============================================================ widgets ==== */

private fun matColor(lib: Library, key: String): Color {
    val c = lib.materials[key]?.color ?: return Color.Magenta
    return Color(c[0], c[1], c[2], 1f)
}

@Composable
private fun Segmented(items: List<String>, selected: Int, onSelect: (Int) -> Unit) {
    val shape = RoundedCornerShape(13.dp)
    BoxWithConstraints(Modifier.fillMaxWidth().clip(shape)
        .background(MaterialTheme.colorScheme.surfaceVariant).padding(3.dp)) {
        val w = maxWidth / items.size
        val off by animateDpAsState(w * selected,
            spring(dampingRatio = 0.82f, stiffness = Spring.StiffnessMediumLow), label = "pill")
        Box(Modifier.offset(x = off).width(w).height(36.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(MaterialTheme.colorScheme.primaryContainer))
        Row {
            items.forEachIndexed { i, s ->
                val fg by animateColorAsState(
                    if (i == selected) MaterialTheme.colorScheme.onPrimaryContainer
                    else MaterialTheme.colorScheme.onSurfaceVariant, tween(220), label = "segfg")
                Box(Modifier.width(w).height(36.dp).clip(RoundedCornerShape(10.dp))
                    .clickable { onSelect(i) }, contentAlignment = Alignment.Center) {
                    Text(s, color = fg, fontFamily = PlexSans, fontSize = 12.5f.sp,
                        fontWeight = if (i == selected) FontWeight.SemiBold else FontWeight.Medium,
                        maxLines = 1)
                }
            }
        }
    }
}

@Composable
private fun Chip(label: String, selected: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val bg by animateColorAsState(
        if (selected) MaterialTheme.colorScheme.primaryContainer
        else MaterialTheme.colorScheme.surfaceVariant, tween(220), label = "chipBg")
    val fg by animateColorAsState(
        if (selected) MaterialTheme.colorScheme.onPrimaryContainer
        else MaterialTheme.colorScheme.onSurfaceVariant, tween(220), label = "chipFg")
    Box(modifier.heightIn(min = 40.dp).clip(CircleShape).background(bg)
        .clickable(onClick = onClick).padding(horizontal = 16.dp),
        contentAlignment = Alignment.Center) {
        Text(label, color = fg, fontFamily = PlexSans, fontSize = 13.sp,
            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal, maxLines = 1,
            textAlign = TextAlign.Center, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
private fun LogicBar(input: Int, glass: Color, line: Color, ink: Color, dim: Color,
                     light: Boolean, onInput: (Int) -> Unit) {
    val outCol by animateColorAsState(if (input == 1) Stage.low else Stage.high,
        tween(260), label = "outCol")
    Surface(color = glass, shape = CircleShape, border = BorderStroke(1.dp, line),
        modifier = Modifier.padding(bottom = 14.dp)) {
        Row(Modifier.padding(start = 16.dp, end = 18.dp, top = 7.dp, bottom = 7.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(11.dp)) {
            Text("IN", color = dim, fontFamily = Mono, fontSize = 10.sp)
            BoxWithConstraints(Modifier.width(88.dp).height(34.dp).clip(CircleShape)
                .background(if (light) Color(0x14000000) else Color(0x22FFFFFF))) {
                val w = maxWidth / 2
                val off by animateDpAsState(w * input,
                    spring(dampingRatio = 0.7f, stiffness = Spring.StiffnessMedium), label = "inPill")
                Box(Modifier.offset(x = off).width(w).fillMaxHeight().clip(CircleShape)
                    .background(if (light) Color(0xFF2B3442) else Color(0xFF33404F)))
                Row {
                    listOf(0, 1).forEach { v ->
                        Box(Modifier.width(w).fillMaxHeight().clickable { onInput(v) },
                            contentAlignment = Alignment.Center) {
                            Text(v.toString(), fontFamily = Mono, fontSize = 13.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = if (input == v) Color.White else dim)
                        }
                    }
                }
            }
            Text(if (input == 1) "nMOS on" else "pMOS on",
                color = ink, fontFamily = Mono, fontSize = 11.5f.sp)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("OUT ", color = dim, fontFamily = Mono, fontSize = 11.5f.sp)
                Text((1 - input).toString(), color = outCol, fontFamily = Mono,
                    fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
            }
        }
    }
}

/* =============================================================== tabs ==== */

@Composable
private fun ViewsTab(scene: Scene, viewKey: String, onPick: (ViewPreset) -> Unit) {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp),
        contentPadding = PaddingValues(bottom = 12.dp)) {
        items(scene.views) { v ->
            val on = v.key == viewKey
            val bg by animateColorAsState(
                if (on) MaterialTheme.colorScheme.primaryContainer
                else MaterialTheme.colorScheme.surfaceVariant, tween(220), label = "viewBg")
            Surface(color = bg, shape = RoundedCornerShape(14.dp),
                modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp).clickable { onPick(v) }) {
                Row(Modifier.padding(horizontal = 15.dp, vertical = 11.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(8.dp).clip(CircleShape).background(
                        if (on) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.outline))
                    Spacer(Modifier.width(13.dp))
                    Column {
                        Text(v.label, fontFamily = PlexSans, fontSize = 14.sp,
                            fontWeight = if (on) FontWeight.SemiBold else FontWeight.Medium,
                            color = if (on) MaterialTheme.colorScheme.onPrimaryContainer
                                    else MaterialTheme.colorScheme.onSurface)
                        Text(v.sub, fontFamily = PlexSans, fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

/** One Display switch in [SectionTab]'s compact toggle grid. */
private class Toggle(val label: String, val on: Boolean, val set: (Boolean) -> Unit)

@Composable
private fun SectionTab(scene: Scene, cx: Float, cy: Float, cz: Float, explode: Float,
                       ghost: Boolean, dims: Boolean, tex: Boolean, edges: Boolean,
                       light: Boolean, dynamic: Boolean, spin: Boolean,
                       onClip: (Int, Float) -> Unit, onExplode: (Float) -> Unit,
                       onGhost: (Boolean) -> Unit, onDims: (Boolean) -> Unit,
                       onTex: (Boolean) -> Unit, onEdges: (Boolean) -> Unit,
                       onLight: (Boolean) -> Unit, onDynamic: (Boolean) -> Unit,
                       onSpin: (Boolean) -> Unit, onReset: () -> Unit) {
    val haptic = LocalHapticFeedback.current
    fun toggle(t: Toggle) { haptic.performHapticFeedback(HapticFeedbackType.LongPress); t.set(!t.on) }

    Column(Modifier.verticalScroll(rememberScrollState())) {
        SliderRow("Cut along channel", "X", cx, scene.lo[0], scene.hi[0], true) { onClip(0, it) }
        SliderRow("Cut vertically", "Y", cy, scene.lo[1], scene.hi[1], true) { onClip(1, it) }
        SliderRow("Cut across channel", "Z", cz, scene.lo[2], scene.hi[2], true) { onClip(2, it) }
        SliderRow("Separate layers", "", explode, 0f, 16f, false) { onExplode(it) }
        Spacer(Modifier.height(4.dp))
        SectionLabel("Display")
        // Seven switches used to be seven full-width rows. As a wrapping grid of compact
        // toggle chips — the same pill used for picking a technology, repurposed as on/off —
        // they take about half the vertical room, which is the point on a phone screen.
        val toggles = listOf(
            Toggle("Edge outlines", edges, onEdges),
            Toggle("Surface texture", tex, onTex),
            Toggle("Dimension callouts", dims, onDims),
            Toggle("Ghost the gate fill", ghost, onGhost),
            Toggle("Slow rotate", spin, onSpin),
            Toggle("Light background", light, onLight),
            Toggle("Material You colours", dynamic, onDynamic))
        for (row in toggles.chunked(2)) {
            Row(Modifier.fillMaxWidth().padding(vertical = 3.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (t in row) Chip(t.label, t.on, Modifier.weight(1f)) { toggle(t) }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
        Spacer(Modifier.height(10.dp))
        OutlinedButton(onClick = onReset,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
            Text("Reset this scene", fontFamily = PlexSans, fontSize = 13.5f.sp)
        }
        Spacer(Modifier.height(14.dp))
    }
}

@Composable
private fun SectionLabel(text: String) {
    Text(text, style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 10.dp, bottom = 4.dp))
}

@Composable
private fun SliderRow(label: String, axis: String, frac: Float, lo: Float, hi: Float,
                      offAtMax: Boolean, onChange: (Float) -> Unit) {
    Column(Modifier.padding(vertical = 2.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(label, fontFamily = PlexSans, fontSize = 13.sp,
                color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.weight(1f))
            if (axis.isNotEmpty()) {
                Text(axis, fontFamily = Mono, fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(end = 8.dp))
            }
            val shown = lo + (hi - lo) * frac
            Text(if (offAtMax && frac >= 0.999f) "off" else "${(shown * 10).roundToInt() / 10f} nm",
                fontFamily = Mono, fontSize = 11.5f.sp,
                color = if (offAtMax && frac >= 0.999f) MaterialTheme.colorScheme.onSurfaceVariant
                        else MaterialTheme.colorScheme.primary)
        }
        Box(Modifier.fillMaxWidth().height(44.dp), contentAlignment = Alignment.Center) {
            Slider(value = frac, onValueChange = onChange, valueRange = 0f..1f)
        }
    }
}

@Composable
private fun LayersTab(lib: Library, scene: Scene, tick: Int, onSet: (List<Part>, Boolean) -> Unit) {
    val grouped = remember(tick, scene) {
        scene.groups.map { g -> g to scene.parts.filter { it.group == g } }
            .filter { it.second.isNotEmpty() }
    }
    val anyVisible = scene.parts.any { it.visible }
    LazyColumn(contentPadding = PaddingValues(bottom = 14.dp)) {
        // A master switch for the whole scene, and one per group below — the same
        // any-on-means-hide-all-else-show-all rule the web viewer already uses.
        item(key = "_all") {
            Row(Modifier.fillMaxWidth().heightIn(min = 44.dp)
                .clip(RoundedCornerShape(12.dp))
                .clickable { onSet(scene.parts, !anyVisible) }
                .padding(horizontal = 4.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Text("${scene.parts.count { it.visible }} of ${scene.parts.size} layers visible",
                    fontFamily = Mono, fontSize = 11.sp, modifier = Modifier.weight(1f),
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(if (anyVisible) "Hide all" else "Show all",
                    fontFamily = PlexSans, fontSize = 12.5f.sp, fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.primary)
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant,
                modifier = Modifier.padding(top = 6.dp))
        }
        for ((g, parts) in grouped) {
            item(key = "h_$g") {
                val groupOn = parts.any { it.visible }
                Row(Modifier.fillMaxWidth().heightIn(min = 36.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .clickable { onSet(parts, !groupOn) }
                    .padding(horizontal = 4.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Text(g, style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.weight(1f).padding(top = 12.dp, bottom = 2.dp))
                    Text(if (groupOn) "Hide" else "Show",
                        fontFamily = Mono, fontSize = 10.5f.sp,
                        color = MaterialTheme.colorScheme.primary)
                }
            }
            items(parts, key = { it.id }) { p ->
                val alpha by animateFloatAsState(if (p.visible) 1f else 0.42f,
                    tween(200), label = "layerAlpha")
                Row(Modifier.fillMaxWidth().heightIn(min = 48.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .clickable { onSet(listOf(p), !p.visible) }
                    .padding(horizontal = 4.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = p.visible, onCheckedChange = { onSet(listOf(p), it) })
                    Spacer(Modifier.width(4.dp))
                    Box(Modifier.size(13.dp).clip(RoundedCornerShape(4.dp))
                        .graphicsLayer { this.alpha = alpha }
                        .background(matColor(lib, p.material)))
                    Spacer(Modifier.width(11.dp))
                    Text(p.name, fontFamily = PlexSans, fontSize = 13.sp, maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.graphicsLayer { this.alpha = alpha },
                        color = MaterialTheme.colorScheme.onSurface)
                }
            }
        }
    }
}

@Composable
private fun StoryTab(scene: Scene) {
    val blocks = remember(scene) { storyBlocks(scene.story) }
    LazyColumn(contentPadding = PaddingValues(bottom = 24.dp)) {
        if (blocks.isEmpty()) item {
            Text("No background written for this scene yet.",
                fontFamily = PlexSans, fontSize = 13.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        items(blocks) { b ->
            when (b.kind) {
                "h4" -> Text(b.text, fontFamily = PlexSans, fontSize = 14.5f.sp,
                    fontWeight = FontWeight.SemiBold, lineHeight = 20.sp,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.padding(top = 18.dp, bottom = 6.dp))
                "li" -> Row(Modifier.padding(bottom = 7.dp)) {
                    Text("—", fontFamily = PlexSans, fontSize = 13.5f.sp,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.padding(end = 8.dp))
                    Text(b.text, fontFamily = PlexSans, fontSize = 13.5f.sp, lineHeight = 21.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                else -> Text(b.text, fontFamily = PlexSans, fontSize = 13.5f.sp, lineHeight = 21.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(bottom = 11.dp))
            }
        }
    }
}

/** A compact parasitics table, tacked onto Specs rather than earning a sixth tab. */
private fun LazyListScope.parasiticSection(
    scene: Scene, picked: String?, onPick: (Parasitic?) -> Unit
) {
    val P = scene.par ?: return
    item {
        Spacer(Modifier.height(18.dp))
        Text("Capacitance estimates", fontFamily = PlexSans, fontWeight = FontWeight.SemiBold,
            fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface)
        Text("From this model's own geometry — L_G ${P.lg.toInt()} nm, W_eff " +
             "${P.weff.toInt()} nm (total shown), gate-stack span ${P.foot.toInt()} nm. " +
             "C_gc + C_ge = ${P.gateParPct}% of C_ox in this approximation. Tap a row to highlight it; read the limitations below.",
            fontFamily = PlexSans, fontSize = 12.sp, lineHeight = 17.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 4.dp, bottom = 8.dp))
    }
    items(P.terms, key = { it.id }) { t ->
        val on = picked == t.id
        Surface(
            color = if (on) MaterialTheme.colorScheme.secondaryContainer else Color.Transparent,
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier.fillMaxWidth().padding(vertical = 1.dp)
                .clickable { onPick(if (on) null else t) }) {
            Column(Modifier.padding(horizontal = 8.dp, vertical = 7.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(t.sym, fontFamily = Mono, fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.width(52.dp))
                    Text(t.pair, fontFamily = PlexSans, fontSize = 12.5f.sp,
                        modifier = Modifier.weight(1f),
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("${t.aF} aF", fontFamily = Mono, fontSize = 11.5f.sp,
                        color = MaterialTheme.colorScheme.onSurface)
                    Text("${t.pct}%", fontFamily = Mono, fontSize = 11.sp,
                        textAlign = TextAlign.End,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.width(52.dp))
                }
                if (on) Text(t.desc, fontFamily = PlexSans, fontSize = 11.5f.sp,
                    lineHeight = 16.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 6.dp))
            }
        }
    }
    item {
        Surface(color = MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(10.dp),
            modifier = Modifier.fillMaxWidth().padding(top = 10.dp)) {
            Text(P.note, fontFamily = PlexSans, fontSize = 10.5f.sp, lineHeight = 15.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(10.dp))
        }
    }
}

@Composable
private fun SpecsTab(scene: Scene, picked: String?, onPick: (Parasitic?) -> Unit) {
    LazyColumn(contentPadding = PaddingValues(bottom = 16.dp)) {
        item {
            Text(scene.blurb, fontFamily = PlexSans, fontSize = 13.sp, lineHeight = 19.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 2.dp, bottom = 14.dp))
        }
        items(scene.dims) { (sym, name, value) ->
            Row(Modifier.fillMaxWidth().padding(vertical = 5.dp)) {
                Text(sym, fontFamily = Mono, fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.width(82.dp))
                Text(name, fontFamily = PlexSans, fontSize = 13.sp,
                    modifier = Modifier.weight(1f),
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(value, fontFamily = Mono, fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurface)
            }
        }
        parasiticSection(scene, picked, onPick)
        if (scene.note.isNotEmpty()) item {
            Surface(color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(14.dp),
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) {
                Text(strip(scene.note), fontFamily = PlexSans, fontSize = 13.sp, lineHeight = 19.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(14.dp))
            }
        }
    }
}

/* =========================================================== callouts ==== */

private fun strip(s: String) = s.replace(Regex("<[^>]*>"), "")

@Composable
private fun BoxScope.CalloutOverlay(renderer: Renderer, scene: Scene, viewKey: String, light: Boolean,
                                     bottomInset: Dp = 0.dp, topInset: Dp = 0.dp) {
    var frame by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) { while (true) { withFrameNanos { }; frame++ } }
    val density = LocalDensity.current

    val placed = remember(frame, viewKey, scene) {
        val shown = scene.callouts.filter {
            (it.views == null || it.views.contains(viewKey)) &&
                !(it.lead && it.pids.isNotEmpty())   // those are painted onto the layers now
        }
        val inv = renderer.pickInv()
        val sil = renderer.silhouette()
        val w = renderer.viewW.toFloat(); val h = renderer.viewH.toFloat()
        val cx = if (sil != null) (sil[0] + sil[2]) / 2f else w / 2f
        val out = ArrayList<Placed>()
        for (c in shown) {
            // Measure what actually gets drawn. A dimension chip is two lines of mono
            // inside a padded surface, not one line of body text, and estimating it as
            // the latter is why they used to pile up on top of each other.
            val tw: Float; val th: Float
            if (c.flat) {
                val fs = with(density) { (when (c.size) { "l" -> 16f; "s" -> 10f; else -> 13f }).sp.toPx() }
                tw = strip(c.label).length * fs * 0.6f
                th = fs * 1.35f
            } else {
                val f1 = with(density) { 10.5f.sp.toPx() }
                val f2 = with(density) { 8.5f.sp.toPx() }
                val padX = with(density) { 7.dp.toPx() } * 2f
                val padY = with(density) { 3.dp.toPx() } * 2f
                val head = if (c.value.isEmpty()) strip(c.label) else "${strip(c.label)} = ${c.value}"
                tw = maxOf(head.length * f1 * 0.6f, c.desc.length * f2 * 0.6f) + padX
                th = f1 * 1.3f + (if (c.desc.isNotEmpty()) f2 * 1.3f else 0f) + padY
            }
            var anchor = renderer.project(c.a)
            if (c.lead && c.pids.isNotEmpty()) {
                // anchor on a face of the named layer that the camera can actually see
                var best: FloatArray? = null; var bs = -Float.MAX_VALUE
                for (sm in renderer.faceSamples(c.pids)) {
                    val sp = renderer.project(renderer.samplePoint(sm)) ?: continue
                    if (sp[0] < 0f || sp[0] > w || sp[1] < 0f || sp[1] > h) continue
                    val hit = renderer.pick(sp[0], sp[1], inv) ?: continue
                    if (!c.pids.contains(hit.id)) continue
                    val score = if (c.sd != 0) c.sd * sp[0] else kotlin.math.abs(sp[0] - w / 2f)
                    if (score > bs) { bs = score; best = sp }
                }
                anchor = best        // null means none of it is in view: drop the label
            }
            val a = anchor ?: continue
            if (c.lead) {
                val side = if (c.sd != 0) c.sd else if (a[0] < cx) -1 else 1
                out.add(Placed(c, a[0], a[1], a[0], a[1], a[0], a[1], tw, th, side))
            } else {
                // a and b are the two ends of the dimension; lab is where the chip belongs,
                // parked off the model so it does not cover what it is measuring.
                val bp = renderer.project(c.b) ?: continue
                val lp = renderer.project(c.lab) ?: continue
                if (lp[0] < -70f || lp[0] > w + 70f || lp[1] < -70f || lp[1] > h + 70f) continue
                out.add(Placed(c, a[0], a[1], bp[0], bp[1], lp[0], lp[1], tw, th, 0))
            }
        }

        // leader labels form one tidy column per side, swept so none can overlap
        val pad = 8f
        val top = maxOf(34f, with(density) { topInset.toPx() } + 8f)
        val bot = with(density) { bottomInset.toPx() } + if (scene.logic) 64f else pad
        val gap = 20f
        for (sd in intArrayOf(-1, 1)) {
            val col = out.filter { it.c.lead && it.side == sd }.sortedBy { it.ay }
            if (col.isEmpty()) continue
            val wmax = col.maxOf { it.w }
            var x = if (sd < 0) (sil?.get(0) ?: 0f) - gap else (sil?.get(2) ?: w) + gap
            x = if (sd < 0) maxOf(x, wmax + pad) else minOf(x, w - wmax - pad)
            var y = top
            for (p in col) {
                p.tx = if (sd < 0) x - p.w / 2f else x + p.w / 2f
                y = maxOf(p.ay, y + p.h / 2f); p.ty = y; y += p.h / 2f + 6f
            }
            val last = col.last()
            val over = last.ty + last.h / 2f - (h - bot)
            if (over > 0f) {
                val head = col.first().ty - col.first().h / 2f - top
                val lift = minOf(over, maxOf(head, 0f))
                for (p in col) p.ty -= lift
            }
            for (p in col) {
                p.tx = p.tx.coerceIn(p.w / 2f + pad, maxOf(p.w / 2f + pad, w - p.w / 2f - pad))
                p.ty = p.ty.coerceIn(p.h / 2f + top, maxOf(p.h / 2f + top, h - p.h / 2f - bot))
            }
        }

        // dimension chips keep their own spot, nudged apart until none overlaps
        val rest = out.filter { !it.c.lead }
        for (p in rest) {
            p.tx = p.tx.coerceIn(p.w / 2f + pad, maxOf(p.w / 2f + pad, w - p.w / 2f - pad))
            p.ty = p.ty.coerceIn(p.h / 2f + top, maxOf(p.h / 2f + top, h - p.h / 2f - bot))
        }
        repeat(6) {
            val byY = rest.sortedBy { it.ty }
            for (i in 1 until byY.size) {
                val u = byY[i - 1]; val v = byY[i]
                if (u.c.flat || v.c.flat) continue
                val need = (u.h + v.h) / 2f + 8f
                if (kotlin.math.abs(v.tx - u.tx) < (u.w + v.w) / 2f + 4f && v.ty - u.ty < need)
                    v.ty = u.ty + need
            }
        }
        for (p in rest) p.ty = p.ty.coerceIn(p.h / 2f + top, maxOf(p.h / 2f + top, h - p.h / 2f - bot))
        out
    }

    val leadCol = if (light) Color(0xFF59636F) else Color(0xFF8A97A8)
    val dotCol = if (light) Color(0xFF454F5C) else Color(0xFFAEB9C8)
    Canvas(Modifier.matchParentSize()) {
        for (p in placed) {
            if (p.c.lead) {
                // stub out of the label, then a straight run to the dot on the layer
                val dir = if (p.side < 0) 1f else -1f
                val ix = p.tx + dir * (p.w / 2f + 4f)
                val kx = ix + dir * 11f
                drawLine(leadCol, GOffset(ix, p.ty), GOffset(kx, p.ty), strokeWidth = 1.2f)
                drawLine(leadCol, GOffset(kx, p.ty), GOffset(p.ax, p.ay), strokeWidth = 1.2f)
                drawCircle(dotCol, radius = 2.8f, center = GOffset(p.ax, p.ay))
            } else if (!p.c.flat) {
                // the measured span itself, then a leader from the chip to its midpoint
                drawLine(dotCol, GOffset(p.ax, p.ay), GOffset(p.bx, p.by), strokeWidth = 1.4f)
                val mx = (p.ax + p.bx) / 2f; val my = (p.ay + p.by) / 2f
                val dx = mx - p.tx; val dy = my - p.ty
                val len = kotlin.math.hypot(dx, dy).coerceAtLeast(1f)
                val sx = p.tx + dx / len * minOf(p.w / 2f + 4f, len)
                val sy = p.ty + dy / len * minOf(p.h / 2f + 4f, len)
                drawLine(leadCol, GOffset(sx, sy), GOffset(mx, my), strokeWidth = 1.2f)
            }
        }
    }
    Box(Modifier.matchParentSize()) {
        for (p in placed) {
            val c = p.c
            val place = Modifier
                .offset { IntOffset(p.tx.roundToInt(), p.ty.roundToInt()) }
                .graphicsLayer { translationX = -size.width / 2f; translationY = -size.height / 2f }
            if (c.flat) {
                Text(strip(c.label), modifier = place, fontFamily = Mono,
                    fontWeight = FontWeight.SemiBold, maxLines = 1,
                    fontSize = when (c.size) { "l" -> 16.sp; "s" -> 10.sp; else -> 13.sp },
                    color = when {
                        c.lead -> if (light) Color(0xFF232B36) else Color(0xFFE9EEF5)
                        c.tone == "light" || !light -> Color.White
                        else -> Color(0xFF232B36)
                    })
            } else Surface(
                color = if (light) Color.White.copy(alpha = .88f) else Stage.dark.copy(alpha = .80f),
                shape = RoundedCornerShape(7.dp),
                border = BorderStroke(1.dp, if (light) Stage.lineOnLight else Stage.lineOnDark),
                modifier = place) {
                Column(Modifier.padding(horizontal = 7.dp, vertical = 3.dp),
                    horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(if (c.value.isEmpty()) strip(c.label) else "${strip(c.label)} = ${c.value}",
                        color = if (light) Color(0xFF121820) else Color.White,
                        fontFamily = Mono, fontSize = 10.5f.sp,
                        fontWeight = FontWeight.SemiBold, maxLines = 1)
                    if (c.desc.isNotEmpty())
                        Text(c.desc, color = if (light) Stage.dimOnLight else Stage.dimOnDark,
                            fontFamily = Mono, fontSize = 8.5f.sp, maxLines = 1)
                }
            }
        }
    }
}

/** A callout after layout: where its dot sits, and where its text ended up. */
private class Placed(
    val c: Callout, val ax: Float, val ay: Float, val bx: Float, val by: Float,
    var tx: Float, var ty: Float, val w: Float, val h: Float, val side: Int
)
