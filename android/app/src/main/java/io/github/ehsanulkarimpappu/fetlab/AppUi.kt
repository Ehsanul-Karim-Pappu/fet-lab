package io.github.ehsanulkarimpappu.fetlab

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.widget.Toast
import android.net.Uri
import android.opengl.GLSurfaceView
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.Crossfade
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
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
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.clickable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListLayoutInfo
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.BiasAlignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset as GOffset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size as GSize
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
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
/** Process-mode chips name a technology; the flow behind each is looked up at runtime. */
private val PROC_KEYS = listOf("proc_fin" to "FinFET", "proc_ns" to "Nanosheet",
    "proc_fs" to "Forksheet", "proc_cfet" to "CFET", "proc_sadp" to "SADP", "proc_saqp" to "SAQP",
    "proc_pitchwalk" to "Pitch walk")
private val MODES = listOf("Device", "Inverter", "Layout", "Process")
private const val PROCESS = 3
private val TABS = listOf("Views", "Section", "Layers", "Specs", "Story")
/** In Process mode the Specs tab lists the fabrication steps instead. */
private val PROC_TABS = listOf("Views", "Section", "Layers", "Steps", "Story")

private fun keysFor(mode: Int) = when (mode) {
    0 -> DEV_KEYS; 1 -> INV_KEYS; 2 -> SHOW_KEYS; else -> PROC_KEYS
}
private fun firstOf(mode: Int) = keysFor(mode).first().first

/** The technology a scene shows, with the viewing mode stripped off. The two CFET
 *  scenes are one technology: only the device mode splits them into mono/sequential. */
private fun techOf(key: String): String {
    val k = key.removePrefix("inv_").removePrefix("show_").removePrefix("proc_").substringBefore('@')
        // A technology's pFET and both-sites flows (ns_p, ns_pair) are the same technology.
        .removeSuffix("_pair").removeSuffix("_p")
    return if (k.startsWith("cfet")) "cfet" else k
}

/** The scene that shows [tech] in [mode], or null when that mode has no equivalent. */
private fun sceneFor(mode: Int, tech: String): String? =
    keysFor(mode).firstOrNull { techOf(it.first) == tech }?.first

/* ============================================================== boot ===== */

@Composable
fun FetLabRoot() {
    val ctx = LocalContext.current
    var payload by remember { mutableStateOf<Pair<Library, Renderer>?>(null) }

    LaunchedEffect(Unit) {
        payload = withContext(Dispatchers.Default) {
            val lib = Library.load(ctx)
            lib to Renderer(lib)
        }
    }

    Crossfade(targetState = payload, animationSpec = tween(420), label = "boot") { p ->
        if (p == null) BootScreen() else FetLabApp(p.first, p.second)
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

/** What the guided tour found on screen, so it can put it back when it ends. */
private class TourReturn(val key: String, val seq: Boolean, val cam: Cam, val view: String,
                         val tab: Int, val sheet: Int, val par: String?, val selected: Part?,
                         val visible: Map<String, Boolean>, val see: Float)

/* How much of the stage shows through the floating control sheet, 0 (solid) to
 * [SEE_MAX]. Saved, since it suits a screen and a pair of eyes rather than a scene. */
private const val SEE_MAX = 0.6f
private const val SEE_DEFAULT = 0.15f
private fun loadSeeThrough(ctx: Context) =
    ctx.getSharedPreferences("ui", Context.MODE_PRIVATE).getFloat("sheet_see_through", SEE_DEFAULT)
        .coerceIn(0f, SEE_MAX)
private fun saveSeeThrough(ctx: Context, v: Float) =
    ctx.getSharedPreferences("ui", Context.MODE_PRIVATE).edit().putFloat("sheet_see_through", v).apply()

private class SceneMemo(val cam: Cam, val view: String, val visible: Map<String, Boolean>,
                        val explode: Float, val par: String?, val selected: Part?)

private class Cam(val az: Float, val el: Float, val r: Float,
                  val tx: Float, val ty: Float, val tz: Float,
                  val cx: Float, val cy: Float, val cz: Float)

private fun lerp(a: Float, b: Float, t: Float) = a + (b - a) * t

/**
 * Section-cut planes for the renderer, from each slider's 0..1 position. A slider at
 * its end means no cut on that axis: the plane goes to infinity rather than to the
 * scene's bounding box, which used to slice off any layer exploded past that box.
 */
private fun clipPlanes(sc: Scene, fx: Float, fy: Float, fz: Float): FloatArray {
    fun at(ax: Int, f: Float) = if (f >= 0.999f) 1e9f else sc.lo[ax] + (sc.hi[ax] - sc.lo[ax]) * f
    return floatArrayOf(at(0, fx), at(1, fy), at(2, fz))
}

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
fun FetLabApp(lib: Library, renderer: Renderer) {
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
    var showDims by rememberSaveable { mutableStateOf(false) }
    var texture by rememberSaveable { mutableStateOf(true) }
    var edges by rememberSaveable { mutableStateOf(true) }
    // The stage follows the system's light or dark setting, like the rest of the app.
    val lightBg = !isSystemInDarkTheme()
    LaunchedEffect(lightBg) { renderer.lightBg = lightBg; draw() }
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
    var seeThrough by remember { mutableFloatStateOf(loadSeeThrough(ctx)) }
    fun setSeeThrough(v: Float) { seeThrough = v.coerceIn(0f, SEE_MAX); saveSeeThrough(ctx, seeThrough) }
    // Only the phone layout's sheet floats over the model; the tablet's sits beside it.
    val sheetFloats = LocalConfiguration.current.screenWidthDp < 680

    // --- guided tour and feature list --------------------------------------
    val catalog = remember { GuideCatalog.load(ctx) }
    var showHelp by rememberSaveable { mutableStateOf(false) }
    // Not saveable: the snapshot the tour restores from does not survive recreation either.
    var tourStep by remember { mutableIntStateOf(-1) }
    var welcomeSeen by remember { mutableStateOf(tourSeen(ctx)) }
    val tourFocus = if (tourStep in catalog.tour.indices) catalog.tour[tourStep] else ""
    val tourTargets = remember { TourTargets() }
    val tourPlayer = remember { TourPlayer(tourTargets, scope, density.density) }
    var tourReturn by remember { mutableStateOf<TourReturn?>(null) }
    // Held here rather than in the tabs so the tour's finger can scroll them.
    val layersList = rememberLazyListState()
    val specsList = rememberLazyListState()
    val stepsList = rememberLazyListState()

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
        renderer.clip = clipPlanes(sc, c.cx, c.cy, c.cz)
        renderer.capsDirty = true
    }

    fun camOf(sc: Scene, v: ViewPreset): Cam {
        val c = v.clip
        return Cam(v.az, v.el, renderer.viewDist(sc, v.az, v.el, v.r), v.tgt[0], v.tgt[1], v.tgt[2],
            if (c?.get(0) != null) frac(c[0]!!, sc.lo[0], sc.hi[0]) else 1f,
            if (c?.get(1) != null) frac(c[1]!!, sc.lo[1], sc.hi[1]) else 1f,
            if (c?.get(2) != null) frac(c[2]!!, sc.lo[2], sc.hi[2]) else 1f)
    }

    // A section plane (see SectionPlane), and how it is shown: 0 3D only, 1 the 2D section, 2 both.
    var secPlane by rememberSaveable { mutableStateOf<String?>(null) }
    var secMode by rememberSaveable { mutableIntStateOf(0) }
    var stageH by remember { mutableIntStateOf(0) }
    /** The active plane's view at [sc]'s scale, if the plane exists there. */
    fun planeView(sc: Scene): ViewPreset? =
        sc.flow?.plane(secPlane)?.views?.get(sc.step?.scale ?: "site")?.let { k -> sc.views.firstOrNull { it.key == k } }

    /** [slow] for a change of scale (site, tile, line field), which moves the camera much
     *  farther and changes the whole scene: a longer flight keeps it readable. */
    fun goToView(sc: Scene, v: ViewPreset, animate: Boolean, slow: Boolean = false) {
        viewKey = v.key
        for (p in sc.parts) p.visible = !v.off.contains(p.id)
        layerTick++
        val to = camOf(sc, v)
        flight?.cancel()
        if (!animate) { applyCam(sc, to); draw(); return }
        val from = cameraNow()
        flight = scope.launch {
            var t0 = 0L
            val dur = if (slow) 1_100_000_000f else 520_000_000f
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

    /** Look at [scene] in section plane [pl], shown as [mode] (0 3D, 1 section, 2 both). */
    fun showPlane(pl: SectionPlane, mode: Int = secMode) {
        secPlane = pl.id; secMode = mode
        planeView(scene)?.let { goToView(scene, it, animate = true) }
    }
    /** Leave the section plane and go back to the step's own view. */
    fun clearPlane() {
        secPlane = null; secMode = 0
        (scene.views.firstOrNull { it.key == scene.step?.view } ?: scene.views.firstOrNull())
            ?.let { goToView(scene, it, animate = true) }
    }

    // What each scene looked like when it was left, so coming back finds it as it was:
    // camera and cuts, view, hidden layers, separation, the picked layer and capacitance.
    // Display switches (edges, texture, callouts...) stay app-wide.
    val memos = remember { mutableMapOf<String, SceneMemo>() }
    fun memoScene() {
        if (tourStep >= 0) return       // the tour's demo changes are not the user's
        val sc = lib.scene(sceneKey)
        memos[sceneKey] = SceneMemo(cameraNow(), viewKey, sc.parts.associate { it.id to it.visible },
            explodeF, parPick, selected)
    }

    fun openScene(key: String, animate: Boolean) {
        val sc = lib.scene(key)
        sceneKey = key
        mode = when {
            key.startsWith("inv_") -> 1; key.startsWith("show_") -> 2
            key.startsWith("proc_") -> PROCESS; else -> 0
        }
        renderer.scene = sc
        val m = memos[key]
        if (m == null) {
            selected = null; renderer.highlight = null
            parPick = null; renderer.par = null      // a highlight must not outlive its scene
            explodeF = 0f; renderer.explode = 0f
            // A fabrication step opens on the view it suggests; any other scene on its first.
            goToView(sc, sc.views.firstOrNull { it.key == sc.step?.view } ?: sc.views.first(),
                animate = false)
        } else {
            flight?.cancel()
            viewKey = m.view
            for (p in sc.parts) p.visible = m.visible[p.id] ?: true
            layerTick++
            applyCam(sc, m.cam)
            explodeF = m.explode; renderer.explode = m.explode * 16f
            parPick = m.par; renderer.par = sc.par?.terms?.firstOrNull { it.id == m.par }
            selected = m.selected; renderer.highlight = m.selected
            renderer.capsDirty = true
            draw()
        }
        if (animate) draw()
    }

    var sceneSwitch by remember { mutableStateOf<Job?>(null) }
    // A step's entrance: the area growing out when the view zooms out, then its films
    // depositing one after another.
    var growJob by remember { mutableStateOf<Job?>(null) }
    fun stopGrowth() {
        growJob?.cancel(); growJob = null
        renderer.growBox = null; renderer.deposit = emptyMap()
    }
    fun switchScene(key: String) {
        if (key == sceneKey) return
        flight?.cancel()
        stopGrowth()
        sceneSwitch?.cancel()
        memoScene()
        sceneSwitch = scope.launch {
            scrim = 1f
            kotlinx.coroutines.delay(140)
            openScene(key, animate = true)
            scrim = 0f
        }
    }

    LaunchedEffect(Unit) { openScene(sceneKey, animate = false) }

    /* ------------------------------------------------ actions ----------- */
    // One definition each, shared by the controls and the guided tour's hand.

    /* --- fabrication process ---------------------------------------------- */
    // The step each flow was last left on, so coming back resumes it.
    val procAt = remember { mutableStateMapOf<String, Int>() }
    var playing by remember { mutableStateOf(false) }
    // Operation substeps (litho, etch, fill...) between the core steps; on by default.
    var showOps by rememberSaveable { mutableStateOf(true) }
    // The patterning route picked in each flow ("direct", "sadp", "saqp"; see Route); a flow
    // the user has not touched shows its own default (SAQP for the FinFET's fins).
    val routeOf = remember { mutableStateMapOf<String, String>() }
    fun routeIn(f: ProcessFlow?) = f?.let { routeOf[it.device] ?: it.defaultRoute } ?: ""
    var glowJob by remember { mutableStateOf<Job?>(null) }
    /** The flow for [tech], if one has been written: the device key it is filed under. */
    fun flowFor(tech: String): String? =
        (if (tech == "cfet") (if (cfetSeq) "cfet_seq" else "cfet_mono") else tech).takeIf { it in lib.flows }
    fun openFlow(device: String) = switchScene(stepKey(device, procAt[device] ?: 0))
    /** Moves to the same technology's [key] flow (nFET, pFET or both sites) at the step that
     *  matches the current one: the same step if that flow has it, else the nearest earlier
     *  step it shares. */
    fun openSite(key: String) {
        val here = lib.scene(sceneKey)
        val f = here.flow ?: return
        val g = lib.flows[key] ?: return
        if (g === f) return
        val ids = g.steps.map { it.id }
        var i = here.stepIndex
        var to = -1
        while (i >= 0 && to < 0) { to = ids.indexOf(f.steps[i].id); i-- }
        playing = false
        switchScene(stepKey(key, to.coerceAtLeast(0)))
    }
    fun notWritten(label: String) = Toast.makeText(ctx,
        if (label.isEmpty()) "No process flow has been written yet."
        else "The $label process flow is still being written.", Toast.LENGTH_SHORT).show()

    /** Moves to step [i] of the flow on screen, keeping the camera, the cuts and any layers
     *  the user hid, unless the step suggests another view; then glows what it changed. */
    fun goStep(i: Int) {
        val old = lib.scene(sceneKey)
        val f = old.flow ?: return
        val n = i.coerceIn(0, f.steps.lastIndex)
        val key = f.keys[n]
        if (key == sceneKey) return
        flight?.cancel()
        stopGrowth()
        val sc = lib.scene(key)
        val hidden = old.parts.filter { !it.visible }.map { it.id }.toSet()
        val before = old.parts.associateBy { it.id }
        // Moving between the tile and the single site is a zoom, not a process change.
        val rescale = old.step?.scale != sc.step?.scale
        sceneKey = key; procAt[f.device] = n
        renderer.scene = sc
        selected = null; renderer.highlight = null
        // With a section plane active, every step is seen in that plane where it has one.
        val v = (if (secPlane != null) planeView(sc) else null) ?: sc.views.firstOrNull { it.key == sc.step?.view }
        if (v != null && (rescale || v.key != viewKey)) goToView(sc, v, animate = true, slow = rescale)
        else {
            for (p in sc.parts) p.visible = p.id !in hidden
            layerTick++
            renderer.clip = clipPlanes(sc, cx, cy, cz)
        }
        fun same(a: Part, b: Part) = a.boxes.size == b.boxes.size &&
            a.boxes.indices.all { a.boxes[it].contentEquals(b.boxes[it]) }
        val after = sc.parts.associateBy { it.id }
        // New parts, and old ones this step reshaped (the stack after the recess, say), glow;
        // what it removed or reshaped fades out where it was.
        renderer.fresh = if (rescale) emptySet()
            else sc.parts.filter { p -> before[p.id]?.let { same(it, p) } != true }.toSet()
        renderer.fadeScene = old
        renderer.fadeParts = if (rescale) emptyList()
            else old.parts.filter { q -> q.visible && after[q.id]?.let { same(q, it) } != true }
        // Zooming out (site to tile, tile to line field), the area grows from the last scene's
        // size to this one's while the camera pulls back; then the films this step deposits
        // rise one after another. Zooming back in simply flies.
        val size = { s: Scene -> (0..2).fold(1f) { a, k -> a * (s.hi[k] - s.lo[k]) } }
        val grows = rescale && size(sc) > size(old) * 1.05f
        val films = sc.step?.deposit.orEmpty().mapNotNull { id -> sc.parts.firstOrNull { it.id == id } }
        if (grows || films.isNotEmpty()) {
            val from = FloatArray(6) { k -> if (k < 3) maxOf(old.lo[k], sc.lo[k]) else minOf(old.hi[k - 3], sc.hi[k - 3]) }
            val to = FloatArray(6) { k -> if (k < 3) sc.lo[k] else sc.hi[k - 3] }
            renderer.deposit = films.associateWith { 0f }
            if (grows) renderer.growBox = from
            growJob = scope.launch {
                suspend fun run(ns: Float, frame: (Float) -> Unit) {
                    var t0 = 0L
                    while (true) {
                        val now = withFrameNanos { it }
                        if (t0 == 0L) t0 = now
                        val raw = ((now - t0) / ns).coerceIn(0f, 1f)
                        frame(raw * raw * (3f - 2f * raw)); draw()
                        if (raw >= 1f) break
                    }
                }
                if (grows) run(1_100_000_000f) { e ->
                    renderer.growBox = FloatArray(6) { k -> from[k] + (to[k] - from[k]) * e }
                }
                renderer.growBox = null
                for (p in films) run(650_000_000f) { e -> renderer.deposit = renderer.deposit + (p to e) }
                renderer.deposit = emptyMap(); draw()
            }
        }
        glowJob?.cancel()
        glowJob = scope.launch {
            var t0 = 0L
            while (true) {
                val now = withFrameNanos { it }
                if (t0 == 0L) t0 = now
                val t = ((now - t0) / 1_400_000_000f).coerceIn(0f, 1f)
                renderer.freshGlow = (1f - t) * (1f - t)
                renderer.fadeAlpha = (1f - t) * (1f - t)
                draw()
                if (t >= 1f) break
            }
        }
        renderer.capsDirty = true; draw()
    }

    fun selectMode(i: Int) {
        // Only the viewing mode changes: the technology on screen carries across.
        val tech = techOf(sceneKey)
        if (i == PROCESS) {
            val f = flowFor(tech) ?: lib.flows.keys.firstOrNull()
            if (f == null) notWritten("") else openFlow(f)
            return
        }
        val next = sceneFor(i, tech) ?: firstOf(i)
        switchScene(if (i == 0 && tech == "cfet" && cfetSeq) "cfet_seq" else next)
    }
    fun selectChip(k: String) {
        if (k.startsWith("proc_")) {
            val f = flowFor(techOf(k))
            if (f == null) notWritten(PROC_KEYS.firstOrNull { it.first == k }?.second ?: k) else openFlow(f)
            return
        }
        switchScene(if (k == "cfet_mono" && cfetSeq) "cfet_seq" else k)
    }
    // Play steps through the flow at reading pace, stopping on the last step.
    LaunchedEffect(playing, sceneKey) {
        if (!playing) return@LaunchedEffect
        val sc = lib.scene(sceneKey)
        val f = sc.flow
        val nxt = f?.next(sc.stepIndex, 1, showOps, routeIn(f))
        if (nxt == null) { playing = false; return@LaunchedEffect }
        delay(4200)
        goStep(nxt)
    }
    // Hiding the operations while on one jumps to the core step it leads into.
    LaunchedEffect(showOps) {
        val sc = lib.scene(sceneKey)
        val f = sc.flow ?: return@LaunchedEffect
        val st = sc.step ?: return@LaunchedEffect
        if (!showOps && st.isOp) goStep(f.steps.indexOfFirst { it.id == st.of }.coerceAtLeast(0))
    }
    fun openUrl(url: String) {
        try { ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
        catch (e: ActivityNotFoundException) { /* no browser */ }
    }
    // Story reads long-form, so give it the reading height; every other tab just needs
    // to be open. Either way this never *closes* a sheet the user opened wider by hand.
    fun selectTab(i: Int) {
        tab = i
        sheetLevel = if (i == 4) maxOf(sheetLevel, 2) else maxOf(sheetLevel, 1)
    }
    fun setClip(ax: Int, v: Float) {
        flight?.cancel()
        when (ax) { 0 -> cx = v; 1 -> cy = v; else -> cz = v }
        renderer.clip = clipPlanes(lib.scene(sceneKey), cx, cy, cz)
        renderer.capsDirty = true; draw()
    }
    fun setVisible(parts: List<Part>, visible: Boolean) {
        for (p in parts) p.visible = visible
        layerTick++
        renderer.capsDirty = true; draw()
    }
    fun pickPar(t: Parasitic?) {
        parPick = t?.id
        renderer.par = t
        renderer.capsDirty = true; draw()
    }

    /* ------------------------------------------------ guided tour ------- */

    fun startTour() {
        if (!welcomeSeen) { markTourSeen(ctx); welcomeSeen = true }
        showHelp = false
        // The tour really switches scenes, turns the camera and cuts the model, so
        // remember what was on screen and put it all back when it ends.
        if (tourReturn == null) tourReturn = TourReturn(sceneKey, cfetSeq, cameraNow(), viewKey,
            tab, sheetLevel, parPick, selected,
            lib.scene(sceneKey).parts.associate { it.id to it.visible }, seeThrough)
        tourStep = 0
    }
    fun exitTour() {
        tourStep = -1
        val r = tourReturn ?: return
        tourReturn = null
        flight?.cancel(); sceneSwitch?.cancel(); scrim = 0f
        if (sceneKey != r.key) openScene(r.key, animate = false)
        cfetSeq = r.seq
        val sc = lib.scene(r.key)
        for (p in sc.parts) p.visible = r.visible[p.id] ?: true
        layerTick++
        applyCam(sc, r.cam); viewKey = r.view
        pickPar(sc.par?.terms?.firstOrNull { it.id == r.par })
        selected = r.selected; renderer.highlight = r.selected
        tab = r.tab; sheetLevel = r.sheet
        setSeeThrough(r.see)
        draw()
    }
    fun tourNext() { if (tourStep >= catalog.tour.lastIndex) exitTour() else tourStep++ }
    fun tourBack() { if (tourStep > 0) tourStep-- }
    fun openFeature(s: GuideStop) {
        showHelp = false
        if (tourStep >= 0) exitTour()
        if (s.tab >= 0) selectTab(s.tab) else sheetLevel = 0
    }

    // Each step is a short script for the hand. It runs once per step; the stage step
    // loops, because orbiting and pinching back and forth leave the model where it was.
    LaunchedEffect(tourStep) {
        if (tourStep !in catalog.tour.indices) { tourPlayer.reset(); return@LaunchedEffect }
        tourPlayer.settle()       // the previous step may have been cut off mid-gesture
        val id = catalog.tour[tourStep]
        if (catalog.stop(id).tab < 0) sheetLevel = 0
        with(tourPlayer) {
            // Lights the model between the card and the sheet as well as the sheet, so a
            // change made in the sheet shows as it happens. Phone layout only, where the
            // sheet sits below the card.
            suspend fun spotSheetAndModel() {
                val card = rect("card"); val sheet = rect("sheet")
                if (card != null && sheet != null && sheet.top > card.bottom + 40f * density.density) {
                    tourTargets.put("sheet:lit", Rect(sheet.left, card.bottom + 12f * density.density,
                        sheet.right, sheet.bottom))
                    spot("sheet:lit")
                }
            }
            // One flick: the finger swipes up and lets go, and the list glides on at the
            // release speed until [left] (pixels still to go; null while the item is off
            // screen) can be measured, then eases to a stop exactly there.
            suspend fun swipe(list: LazyListState, area: String, left: (LazyListLayoutInfo) -> Float?) {
                val r = rect(area) ?: return
                val first = left(list.layoutInfo)
                if (first != null && first < 6f * density.density) return
                val len = minOf(first ?: Float.POSITIVE_INFINITY, r.height * 0.5f)
                val ms = 120
                val x = r.left + r.width * 0.75f
                val y = r.top + (r.height + len) / 2f
                flick(GOffset(x, y), GOffset(x, y - len), ms, onStep = { list.dispatchRawDelta(it * len) }) {
                    var v = len / ms * 1000f               // px/s, the finger's speed as it lets go
                    val slowest = 40f * density.density
                    var last = withFrameNanos { it }
                    val give = last + 6_000_000_000L       // never glide forever
                    while (true) {
                        val now = withFrameNanos { it }
                        val dt = (now - last) / 1e9f; last = now
                        val go = left(list.layoutInfo)
                        if (go != null && go < 0.5f) break
                        // Once the distance is known, slow so it is covered exactly.
                        if (go != null) v = minOf(v, maxOf(go * 7f, slowest))
                        val step = if (go != null) minOf(v * dt, go) else v * dt
                        if (list.dispatchRawDelta(step) < step * 0.5f || now > give) break   // hit the end
                    }
                }
            }
            when (id) {
                "modes" -> {
                    spot("modes")
                    // Switch to another mode and back, so the tap is visible from any mode.
                    val from = mode
                    val to = (from + 1) % MODES.size
                    tap("mode:$to") { selectMode(to) }
                    delay(900)
                    tap("mode:$from") { selectMode(from) }
                    hideHand()
                }
                "arch" -> {
                    spot("arch")
                    // The next architecture along from the one on screen, in whichever mode
                    // is open (chip keys differ per mode: "ns", "inv_ns", "show_ns").
                    val keys = keysFor(mode).map { it.first }.filter { !it.endsWith("cmp") }
                        .filter { mode != PROCESS || flowFor(techOf(it)) != null }
                    val here = keys.indexOfFirst { techOf(it) == techOf(sceneKey) }
                    if (keys.isNotEmpty()) {
                        val k = keys[(here + 1) % keys.size]
                        tap("chip:$k") { selectChip(k) }
                    }
                    hideHand()
                }
                "stage" -> {
                    spot("stage")
                    val r = rect("stage") ?: return@with
                    val y = r.top + r.height * 0.5f
                    val turn = 0.4f * 3.2f        // a 40%-of-width swipe, at the real gesture's rate
                    while (true) {
                        drag(GOffset(r.left + r.width * 0.3f, y), GOffset(r.left + r.width * 0.7f, y), 1100) {
                            renderer.az -= it * turn; draw()
                        }
                        drag(GOffset(r.left + r.width * 0.7f, y), GOffset(r.left + r.width * 0.3f, y), 1100) {
                            renderer.az += it * turn; draw()
                        }
                        val base = renderer.dist
                        pinch(r.center, 1500) { v -> renderer.dist = base * (1f - 0.3f * v); draw() }
                        renderer.dist = base
                        tap("stage") {
                            val hit = renderer.pick(renderer.viewW / 2f, renderer.viewH / 2f)
                            selected = hit; renderer.highlight = hit; draw()
                        }
                        delay(1300)
                    }
                }
                "views" -> {
                    spot("sheet")
                    tap("tab:0") { selectTab(0) }
                    val sc = lib.scene(sceneKey)
                    // A view other than the current one; the top two rows are always on screen.
                    val i = if (sc.views.indexOfFirst { it.key == viewKey } == 0) 1 else 0
                    if (sc.views.size > 1) tap("view:$i") { goToView(sc, sc.views[i], animate = true) }
                    hideHand()
                }
                "section" -> {
                    spot("sheet")
                    tap("tab:1") { selectTab(1) }
                    val r = rect("slider:x")
                    if (r != null) {
                        // Material's thumb travels inside the track, one thumb-radius in.
                        val inset = 10f * density.density
                        fun at(v: Float) = GOffset(r.left + inset + (r.width - 2 * inset) * v, r.center.y)
                        val start = cx
                        // Far enough from where the cut already is that the model visibly opens.
                        val to = if (start > 0.72f) 0.45f else 1f
                        drag(at(start), at(to), 1300) { setClip(0, (cx + it * (to - start)).coerceIn(0f, 1f)) }
                        delay(500)
                        drag(at(to), at(start), 1300) { setClip(0, (cx + it * (start - to)).coerceIn(0f, 1f)) }
                    }
                    // Then the sheet's see-through, with the sheet raised over the model so
                    // the model shows through as the sheet fades, and back again.
                    if (sheetFloats) {
                        sheetLevel = 2
                        delay(650)
                        val s = rect("slider:sheet")
                        if (s != null) {
                            val inset = 10f * density.density
                            fun at(v: Float) = GOffset(s.left + inset + (s.width - 2 * inset) * v, s.center.y)
                            val start = seeThrough / SEE_MAX
                            val to = if (start < 0.6f) 0.9f else 0.2f
                            drag(at(start), at(to), 1300) { setSeeThrough(seeThrough + it * (to - start) * SEE_MAX) }
                            delay(700)
                            drag(at(to), at(start), 1300) { setSeeThrough(seeThrough + it * (start - to) * SEE_MAX) }
                        }
                    }
                    hideHand()
                }
                "layers" -> {
                    spot("sheet")
                    tap("tab:2") { selectTab(2) }
                    val sc = lib.scene(sceneKey)
                    val groups = sc.groups.filter { g -> sc.parts.any { it.group == g } }
                    // Spacers, which every Device and Inverter scene has; the gate in Layout;
                    // in Compare, the second cell, since the last is thousands of rows down.
                    val gi = groups.indexOf("Spacers").takeIf { it >= 0 }
                        ?: groups.indexOfFirst { it.startsWith("Gate") }.takeIf { it >= 0 }
                        ?: minOf(1, groups.lastIndex)
                    if (gi >= 0) {
                        val g = groups[gi]
                        val parts = sc.parts.filter { it.group == g }
                        // Half open, so the group vanishing shows in the model above.
                        sheetLevel = 1
                        layersList.scrollToItem(0)
                        delay(400)
                        spotSheetAndModel()
                        // Until the group's header sits at the top, its layers in view below.
                        swipe(layersList, "list:layers") { info ->
                            info.visibleItemsInfo.firstOrNull { it.key == "h_$g" }?.let { it.offset - 4f * density.density }
                        }
                        tap("group:$gi") { setVisible(parts, !parts.any { it.visible }) }
                        delay(900)
                        tap("group:$gi") { setVisible(parts, !parts.any { it.visible }) }
                    }
                    hideHand()
                }
                "specs" -> {
                    spot("sheet")
                    tap("tab:3") { selectTab(3) }
                    val sc = lib.scene(sceneKey)
                    val terms = sc.par?.terms
                    if (!terms.isNullOrEmpty()) {
                        // Half open, so the coupling the row highlights shows in the model above.
                        sheetLevel = 1
                        specsList.scrollToItem(0)
                        delay(400)
                        spotSheetAndModel()
                        // Down past the blurb and the dimensions until the table's heading
                        // sits at the top, its rows in view below.
                        val head = 1 + sc.dims.size
                        swipe(specsList, "list:specs") { info ->
                            info.visibleItemsInfo.firstOrNull { it.index == head }?.let { it.offset.toFloat() }
                        }
                        val i = terms.indexOfFirst { it.id != parPick }.coerceAtLeast(0)
                        tap("par:$i") { pickPar(terms[i]) }
                    }
                    hideHand()
                }
                "story" -> {
                    spot("sheet")
                    tap("tab:4") { selectTab(4) }
                    delay(1600)
                    spot("about")
                    tap("about")          // only pointed at: opening About would cover the tour
                    hideHand()
                }
            }
        }
    }

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
                    FitTitle(scene.name, MaterialTheme.colorScheme.onBackground)
                    Text(scene.step?.tag(routeIn(scene.flow)) ?: scene.tag,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                Box(Modifier.size(42.dp).tourTarget("about").clip(CircleShape)
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
            Box(Modifier.padding(horizontal = 16.dp).tourTarget("modes")) {
                Segmented(MODES, mode, tag = "mode") { i ->
                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                    selectMode(i)
                }
            }
            Spacer(Modifier.height(10.dp))
            Column(Modifier.tourTarget("arch")) {
            LazyRow(contentPadding = PaddingValues(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(keysFor(mode)) { (k, label) ->
                    val active = if (mode == PROCESS) techOf(sceneKey) == techOf(k)
                                 else sceneKey == k || (k == "cfet_mono" && sceneKey == "cfet_seq")
                    // A flow not written yet stays visible, dimmed, so the roadmap shows.
                    val ready = mode != PROCESS || flowFor(techOf(k)) != null
                    Chip(if (ready) label else "$label · soon", active,
                        Modifier.tourTarget("chip:$k").graphicsLayer { alpha = if (ready) 1f else 0.55f }) {
                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        selectChip(k)
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
            Spacer(Modifier.height(12.dp))
        }
    }

    val stage = @Composable { mod: Modifier ->
        Box(mod.tourTarget("stage").onSizeChanged { stageH = it.height }.clip(RoundedCornerShape(20.dp)).background(stageBg)
            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(20.dp))) {

            val split = scene.flow?.plane(secPlane) != null && secMode == 2 &&
                scene.flow?.plane(secPlane)?.views?.containsKey(scene.step?.scale ?: "site") == true
            AndroidView(factory = { glView }, modifier = Modifier.fillMaxSize()
                .padding(top = if (split) with(density) { (stageH * 0.46f).toDp() } else 0.dp))

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

            // The 2D section, cut from this same scene: over the whole stage, or over its top part
            // with the 3D view resized below it (see the AndroidView's padding above).
            val activePlane = scene.flow?.plane(secPlane)?.takeIf { it.views.containsKey(scene.step?.scale ?: "site") }
            if (activePlane != null && secMode != 0) {
                val panel = if (secMode == 1) Modifier.fillMaxSize().padding(bottom = 86.dp)
                    else Modifier.fillMaxWidth().height(with(density) { (stageH * 0.46f).toDp() })
                Box(panel) {
                    key(layerTick, sceneKey) {
                        SectionPanel(lib, scene, activePlane, selected, onPick = { p ->
                            selected = p; renderer.highlight = p; draw()
                        }, modifier = Modifier.matchParentSize())
                    }
                    Locator(lib, scene, activePlane, Modifier.align(Alignment.TopEnd).padding(6.dp)
                        .size(width = 112.dp, height = 68.dp).clip(RoundedCornerShape(8.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.85f)))
                }
            }

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

            // On Inverter and Layout scenes the IN 0/1 bar owns the bottom edge, so the
            // selected-layer card sits just above it instead of on top of it.
            var logicBarH by remember { mutableStateOf(0.dp) }
            val cardLift by animateDpAsState(if (scene.logic || scene.flow != null) logicBarH else 0.dp,
                tween(220), label = "cardLift")
            AnimatedVisibility(visible = selected != null,
                enter = fadeIn(tween(180)) + slideInVertically(tween(220)) { it / 3 },
                exit = fadeOut(tween(140)) + slideOutVertically(tween(180)) { it / 3 },
                modifier = Modifier.align(Alignment.BottomStart).padding(bottom = stageInset + cardLift)) {
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
                modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = stageInset)
                    .onSizeChanged { logicBarH = with(density) { it.height.toDp() } }) {
                LogicBar(input, glass, line, ink, dim, lightBg) { v ->
                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                    input = v; renderer.input = v; renderer.capsDirty = true; draw()
                }
            }

            val flow = scene.flow
            AnimatedVisibility(visible = flow != null,
                enter = fadeIn() + slideInVertically { it }, exit = fadeOut() + slideOutVertically { it },
                modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = stageInset)
                    .onSizeChanged { logicBarH = with(density) { it.height.toDp() } }) {
                // Kept while it slides away, so the bar does not blank mid-exit.
                val shown = remember { mutableStateOf(scene) }
                if (flow != null) shown.value = scene
                val sc = shown.value
                val f = sc.flow
                val prev = f?.next(sc.stepIndex, -1, showOps, routeIn(f))
                val next = f?.next(sc.stepIndex, 1, showOps, routeIn(f))
                if (f != null) ProcessBar(sc.step?.labelIn(routeIn(f)) ?: "", f.coreCount, sc.step?.title ?: "",
                    sc.step?.isOp == true, sc.step?.let { f.badge[it.match] } ?: "",
                    sc.step?.let { it.match == "published" || it.match == "context" || it.match == "source" } == true, prev != null, next != null, playing,
                    glass, line, ink, dim,
                    onPrev = { playing = false; prev?.let { goStep(it) } },
                    onNext = { playing = false; next?.let { goStep(it) } },
                    onPlay = {
                        // From the last step, play starts again at the first.
                        if (!playing && next == null) goStep(0)
                        playing = !playing
                    },
                    onTitle = { selectTab(3) })
            }

            if (scrimA > 0.005f)
                Box(Modifier.matchParentSize().background(stageBg.copy(alpha = scrimA)))
        }
    }

    val sheetSpring = spring<Dp>(dampingRatio = 0.85f, stiffness = Spring.StiffnessMediumLow)

    val controlTabs = @Composable { mod: Modifier ->
        Box(mod) {
            Segmented(if (mode == PROCESS) PROC_TABS else TABS, tab, tag = "tab") { selectTab(it) }
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
                            edges, spin, seeThrough = if (sheetFloats) seeThrough / SEE_MAX else null,
                            onSeeThrough = { setSeeThrough(it * SEE_MAX) },
                            onClip = { ax, v -> setClip(ax, v) },
                            onExplode = { explodeF = it; renderer.explode = it * 16f
                                renderer.capsDirty = true; draw() },
                            onGhost = { ghost = it; renderer.ghost = it; draw() },
                            onDims = { showDims = it },
                            onTex = { texture = it; renderer.texture = it
                                renderer.capsDirty = true; draw() },
                            onEdges = { edges = it; renderer.edges = it; draw() },
                            onSpin = { spin = it },
                            onReset = {
                                for (p in scene.parts) p.visible = true
                                layerTick++
                                explodeF = 0f; renderer.explode = 0f
                                ghost = false; renderer.ghost = false
                                showDims = false
                                texture = true; renderer.texture = true
                                edges = true; renderer.edges = true
                                spin = false
                                goToView(scene, scene.views.first(), animate = true)
                            },
                            header = {
                                val here = scene.step?.scale ?: "site"
                                val planes = scene.flow?.sections.orEmpty().filter { it.views.containsKey(here) }
                                if (planes.isNotEmpty()) PlanesBlock(lib, scene, planes, secPlane, secMode,
                                    onPlane = { pl -> if (pl.id == secPlane) clearPlane() else showPlane(pl, maxOf(secMode, 2)) },
                                    onMode = { m -> secMode = m })
                            })
                        2 -> LayersTab(lib, scene, layerTick, layersList) { parts, visible -> setVisible(parts, visible) }
                        3 -> {
                            val f = scene.flow
                            if (f != null) StepsTab(lib, f, scene.stepIndex, stepsList, showOps, routeIn(f),
                                onOps = { showOps = it },
                                onRoute = { r ->
                                    // Off the new route (on another route's operation), start
                                    // the new route at its first operation.
                                    routeOf[f.device] = r
                                    if (!f.onRoute(scene.stepIndex, r)) {
                                        playing = false
                                        goStep(f.steps.indexOfFirst { it.route == f.routeOr(r) }.coerceAtLeast(0))
                                    }
                                },
                                onPick = { playing = false; goStep(it) }, onRef = { openUrl(it) },
                                onSite = { openSite(it) },
                                onCompare = { pl -> showPlane(pl, 2); sheetLevel = 1 })
                            else SpecsTab(scene, parPick, specsList) { t -> pickPar(t) }
                        }
                        else -> StoryTab(scene)
                    }
                }
            }
        }
    }

    /* ----------------------------------------------------------- layout -- */

    CompositionLocalProvider(LocalTourTargets provides tourTargets) {
    BoxWithConstraints(Modifier.fillMaxSize()
        .background(MaterialTheme.colorScheme.background).safeDrawingPadding()) {
        val wide = maxWidth >= 680.dp
        if (wide) {
            Row(Modifier.fillMaxSize()) {
                Column(Modifier.width(330.dp).fillMaxHeight()) {
                    header()
                    Column(Modifier.weight(1f).fillMaxWidth().tourTarget("sheet")) {
                        controlTabs(Modifier.fillMaxWidth().padding(horizontal = 16.dp))
                        Spacer(Modifier.height(10.dp))
                        controlBody(Modifier.weight(1f).fillMaxWidth().padding(bottom = 12.dp))
                    }
                }
                stage(Modifier.weight(1f).fillMaxHeight().padding(end = 14.dp, bottom = 14.dp, top = 12.dp))
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
                        1f - seeThrough - if (sheetLevel > 0) 0f else 0.05f, tween(200), label = "sheetAlpha")
                    // A shadow would show through a see-through sheet as a smudge, so it
                    // fades as the sheet does; the border still marks the edge.
                    val sheetShadow = 14.dp * (1f - seeThrough / SEE_MAX)

                    stage(Modifier.fillMaxSize().padding(horizontal = 12.dp, vertical = 10.dp))

                    var dragDistance by remember { mutableFloatStateOf(0f) }
                    Box(Modifier.align(Alignment.BottomCenter).fillMaxWidth()) {
                        Surface(color = MaterialTheme.colorScheme.surface.copy(alpha = sheetAlpha),
                            shape = RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp),
                            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                            modifier = Modifier.fillMaxWidth()
                                .shadow(sheetShadow, RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp))
                                .tourTarget("sheet")
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

        TourOverlay(tourPlayer, active = tourStep >= 0, tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.fillMaxSize())

        // The card sits in whichever half the spotlight is not, so it never covers what it
        // is teaching — and it follows the light when one step moves it (Story → About).
        val cardAtBottom by remember { derivedStateOf {
            val lit = tourPlayer.spot.value; val all = tourPlayer.bounds
            lit.isEmpty || all.isEmpty || lit.center.y < all.top + all.height * 0.55f
        } }
        // Glide across the screen between the two ends rather than jumping.
        val cardBias by animateFloatAsState(if (cardAtBottom) 1f else -1f,
            tween(480, easing = FastOutSlowInEasing), label = "tourCardBias")
        if (tourStep in catalog.tour.indices) {
            val stop = catalog.stop(tourFocus)
            TourCard(stop, tourStep, catalog.tour.size,
                modifier = Modifier
                    .align(BiasAlignment(0f, cardBias))
                    .padding(16.dp)
                    .then(if (wide) Modifier.width(380.dp) else Modifier.fillMaxWidth())
                    .tourTarget("card"),
                onBack = { tourBack() }, onNext = { tourNext() }, onExit = { exitTour() })
        }
        if (!welcomeSeen && tourStep < 0 && !showHelp)
            WelcomeGuide(onStart = { startTour() }, onSkip = { markTourSeen(ctx); welcomeSeen = true })
        if (showHelp)
            FeatureGuide(catalog, onOpen = { s -> openFeature(s) },
                onTour = { startTour() }, onClose = { showHelp = false })
    }
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
private fun Segmented(items: List<String>, selected: Int, tag: String? = null, onSelect: (Int) -> Unit) {
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
                Box(Modifier.width(w).height(36.dp)
                    .then(if (tag != null) Modifier.tourTarget("$tag:$i") else Modifier)
                    .clip(RoundedCornerShape(10.dp))
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
internal fun Chip(label: String, selected: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
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

/** The fabrication stepper on the stage: back, the step and its name, play, forward. */
@Composable
@OptIn(ExperimentalLayoutApi::class)
private fun ProcessBar(label: String, cores: Int, title: String, isOp: Boolean, badge: String, sourced: Boolean,
                       hasPrev: Boolean, hasNext: Boolean, playing: Boolean,
                       glass: Color, line: Color, ink: Color, dim: Color,
                       onPrev: () -> Unit, onNext: () -> Unit, onPlay: () -> Unit, onTitle: () -> Unit) {
    Surface(color = glass, shape = RoundedCornerShape(24.dp), border = BorderStroke(1.dp, line),
        modifier = Modifier.padding(start = 12.dp, end = 12.dp, bottom = 14.dp).widthIn(max = 520.dp)
            .fillMaxWidth().tourTarget("procbar")) {
        Row(Modifier.padding(4.dp), verticalAlignment = Alignment.CenterVertically) {
            BarIcon(BarGlyph.Back, hasPrev, ink, dim, "Previous step", onPrev)
            Column(Modifier.weight(1f).clip(RoundedCornerShape(14.dp)).clickable(onClick = onTitle)
                .padding(horizontal = 8.dp, vertical = 5.dp)) {
                // How this state stands against its source, at a glance: a published stage in the
                // accent colour, a teaching reconstruction or a concept in the muted one. The badge
                // wraps onto its own line when the step number and it do not fit side by side
                // (a narrow phone, a large font), rather than shrinking or crowding the controls.
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text((if (isOp) "OPERATION " else "STEP ") + "$label / $cores", color = dim,
                        fontFamily = Mono, fontSize = 10.sp, maxLines = 1)
                    if (badge.isNotEmpty()) {
                        val tone = if (sourced) MaterialTheme.colorScheme.primary else dim
                        Text(badge.uppercase(), color = tone, fontFamily = Mono, fontSize = 10.sp,
                            maxLines = 1, modifier = Modifier
                                .border(1.dp, tone.copy(alpha = 0.6f), RoundedCornerShape(6.dp))
                                .padding(horizontal = 5.dp, vertical = 1.dp))
                    }
                }
                AnimatedContent(targetState = title, label = "stepTitle",
                    transitionSpec = { fadeIn(tween(220)) togetherWith fadeOut(tween(160)) }) { t ->
                    Text(t, color = ink, fontFamily = PlexSans, fontSize = 13.5f.sp,
                        fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
            BarIcon(if (playing) BarGlyph.Pause else BarGlyph.Play, true, ink, dim,
                if (playing) "Pause" else "Play the steps", onPlay)
            BarIcon(BarGlyph.Next, hasNext, ink, dim, "Next step", onNext)
        }
    }
}

private enum class BarGlyph { Back, Next, Play, Pause }

/** Drawn rather than typed: the text arrows and play symbols can come out as emoji. */
@Composable
private fun BarIcon(glyph: BarGlyph, enabled: Boolean, ink: Color, dim: Color, label: String,
                    onClick: () -> Unit) {
    val col = if (enabled) ink else dim.copy(alpha = 0.45f)
    Box(Modifier.size(44.dp).clip(CircleShape)
        .clickable(enabled = enabled, onClickLabel = label, onClick = onClick),
        contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(18.dp)) {
            val w = size.width; val h = size.height; val sw = w * 0.14f
            when (glyph) {
                BarGlyph.Back -> {
                    drawLine(col, GOffset(w * 0.65f, h * 0.15f), GOffset(w * 0.3f, h * 0.5f), sw, StrokeCap.Round)
                    drawLine(col, GOffset(w * 0.3f, h * 0.5f), GOffset(w * 0.65f, h * 0.85f), sw, StrokeCap.Round)
                }
                BarGlyph.Next -> {
                    drawLine(col, GOffset(w * 0.35f, h * 0.15f), GOffset(w * 0.7f, h * 0.5f), sw, StrokeCap.Round)
                    drawLine(col, GOffset(w * 0.7f, h * 0.5f), GOffset(w * 0.35f, h * 0.85f), sw, StrokeCap.Round)
                }
                BarGlyph.Play -> drawPath(Path().apply {
                    moveTo(w * 0.25f, h * 0.12f); lineTo(w * 0.85f, h * 0.5f)
                    lineTo(w * 0.25f, h * 0.88f); close()
                }, col)
                BarGlyph.Pause -> {
                    drawRect(col, GOffset(w * 0.22f, h * 0.14f), GSize(w * 0.2f, h * 0.72f))
                    drawRect(col, GOffset(w * 0.58f, h * 0.14f), GSize(w * 0.2f, h * 0.72f))
                }
            }
        }
    }
}

/** How a step relates to its source: figure identifiers and match level, then the model's
 *  own choices and what this view leaves out. Nothing here claims to match a drawing. */
@Composable
private fun StepSource(flow: ProcessFlow, st: ProcessStep) {
    val label = flow.match[st.match] ?: st.match
    val src = if (st.src.isEmpty()) "" else st.src.joinToString("") { "[$it]" } + " "
    val figs = when {
        st.figs.isNotEmpty() -> src + "Fig. " + st.figs.joinToString(", ") + " · "
        src.isNotEmpty() -> "$src· "
        else -> ""
    }
    if (label.isNotEmpty() || figs.isNotEmpty())
        Text(figs + label, fontFamily = Mono, fontSize = 10.5f.sp, lineHeight = 15.sp,
            color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 8.dp))
    // What the stepper's badge means for this step, in words.
    flow.badge[st.match]?.let { flow.badgeNote[it] }?.let {
        Text(it, fontFamily = PlexSans, fontSize = 11.5f.sp, lineHeight = 16.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 4.dp))
    }
    @Composable
    fun notes(head: String, items: List<String>) {
        if (items.isEmpty()) return
        Text(head, style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp))
        for (t in items) Text("·  $t", fontFamily = PlexSans, fontSize = 12.sp, lineHeight = 17.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 2.dp))
    }
    notes("MODEL CHOICES", st.subs)
    notes("NOT SHOWN HERE", st.omitted)
}

/** The scene's name on one line: shrinks to fit (down to 14 sp) before it ellipsises, and
 *  stays invisible until it has settled so the size does not flicker. */
@Composable
private fun FitTitle(text: String, color: Color) {
    val base = MaterialTheme.typography.titleLarge
    var size by remember(text) { mutableStateOf(base.fontSize.value) }
    var ready by remember(text) { mutableStateOf(false) }
    Text(text, style = base.copy(fontSize = size.sp, lineHeight = (size * 1.2f).sp), color = color,
        maxLines = 1, softWrap = false, overflow = TextOverflow.Ellipsis,
        modifier = Modifier.drawWithContent { if (ready) drawContent() },
        onTextLayout = { r ->
            if ((r.hasVisualOverflow || r.isLineEllipsized(0)) && size > 14f) size = maxOf(14f, size - 1f)
            else ready = true
        })
}

/** nFET, pFET or both sites: the technology's three flows, one of them on screen. */
@Composable
private fun SitePicker(flow: ProcessFlow, onSite: (String) -> Unit) {
    Column(Modifier.fillMaxWidth().padding(bottom = 10.dp).tourTarget("sites")) {
        SectionLabel("DEVICE SITE")
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            for (s in flow.sites) Chip(s.name, s.id == flow.site, Modifier.weight(1f)) { onSite(s.flow) }
        }
        Text(when (flow.site) {
            "p" -> "Following the pFET. It shares the nFET's early stages, then has its own masked steps."
            "both" -> "One nFET and one pFET side by side, joined by their gate line: two devices, not a finished circuit."
            else -> "Following the nFET. Its pFET neighbour has a flow of its own, and Both sites shows the two together."
        }, fontFamily = PlexSans, fontSize = 11.5f.sp, lineHeight = 16.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 6.dp))
    }
}

/** What each region is doing at this step: processed, masked, or not yet reached. */
@Composable
private fun RegionLine(st: ProcessStep) {
    if (st.regions.isEmpty()) return
    Row(Modifier.fillMaxWidth().padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        for ((k, name) in listOf("n" to "nFET", "p" to "pFET")) {
            val v = st.regions[k] ?: continue
            val masked = v.startsWith("masked") || v.startsWith("protected")
            Surface(color = if (masked) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.primaryContainer,
                shape = RoundedCornerShape(8.dp), modifier = Modifier.weight(1f)) {
                Text("$name · $v", fontFamily = PlexSans, fontSize = 11.sp, lineHeight = 15.sp,
                    color = if (masked) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onPrimaryContainer,
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 5.dp))
            }
        }
    }
}

/** The choice of route through the operations that follow (how the hard mask is patterned),
 *  or between alternative endings (a gate cut or a shared gate). */
@Composable
private fun RoutePicker(flow: ProcessFlow, here: String, onRoute: (String) -> Unit) {
    Surface(color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f),
        shape = RoundedCornerShape(14.dp),
        modifier = Modifier.fillMaxWidth().padding(start = 14.dp, top = 6.dp, bottom = 6.dp).tourTarget("routes")) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
            Text(flow.routeTitle.uppercase(), style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(if (flow.routeKind == "terminal") "Two alternative endings, not one after the other: pick one to step through."
                 else "Pick a route: the substeps below change to match, then rejoin at ${flow.routeJoin}.",
                fontFamily = PlexSans, fontSize = 11.5f.sp, lineHeight = 16.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 2.dp, bottom = 8.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                for (r in flow.routes) Chip(r.name, r.id == here, Modifier.weight(1f)) { onRoute(r.id) }
            }
            flow.routes.firstOrNull { it.id == here }?.let {
                Text(it.note, fontFamily = PlexSans, fontSize = 11.5f.sp, lineHeight = 16.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp))
            }
        }
    }
}

/** Process mode's fourth tab: the scope, every step (the current one open), the sources. */
@Composable
private fun StepsTab(lib: Library, flow: ProcessFlow, index: Int, list: LazyListState,
                     showOps: Boolean, route: String, onOps: (Boolean) -> Unit, onRoute: (String) -> Unit,
                     onPick: (Int) -> Unit, onRef: (String) -> Unit, onCompare: (SectionPlane) -> Unit,
                     onSite: (String) -> Unit) {
    val here = flow.routeOr(route)
    // Keep the current step in view as the stepper or play moves it.
    LaunchedEffect(index) { list.animateScrollToItem(index + 1, scrollOffset = -24) }
    LazyColumn(state = list, contentPadding = PaddingValues(bottom = 16.dp),
        modifier = Modifier.tourTarget("list:steps")) {
        item {
            Column(Modifier.padding(top = 2.dp, bottom = 10.dp)) {
                flow.pitchWalk?.let { PitchWalkPanel(lib, it) }
                if (flow.sites.isNotEmpty()) SitePicker(flow, onSite)
                for (t in listOf(flow.scope, flow.branch, flow.figures)) if (t.isNotEmpty())
                    Text(t, fontFamily = PlexSans, fontSize = 12.sp, lineHeight = 17.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(bottom = 6.dp))
                // A flow with no operation substeps (the SADP and SAQP lessons) needs no switch.
                if (flow.steps.any { it.isOp }) Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp))
                    .toggleable(value = showOps, role = Role.Switch, onValueChange = onOps)
                    .padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Show every operation", fontFamily = PlexSans, fontSize = 13.sp,
                            color = MaterialTheme.colorScheme.onSurface)
                        Text("Resist, exposure, etch and fill between the main steps, some on a 2 × 2 tile",
                            fontFamily = PlexSans, fontSize = 11.5f.sp, lineHeight = 16.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Switch(checked = showOps, onCheckedChange = null)
                }
            }
        }
        // Where the routes part: the choice sits in the list at that point, so it is in view
        // whenever the steps around it are.
        val fork = flow.steps.indexOfFirst { it.route != null }
        itemsIndexed(flow.steps, key = { _, st -> st.id }) { i, st ->
            // Alternative endings (gate cut or shared gate) are core steps: their picker always shows.
            if (i == fork && (showOps || flow.routeKind == "terminal") && flow.routes.isNotEmpty())
                RoutePicker(flow, here, onRoute)
            if (st.isOp && !showOps || !flow.onRoute(i, here)) return@itemsIndexed
            val on = i == index
            Surface(color = if (on) MaterialTheme.colorScheme.secondaryContainer else Color.Transparent,
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth().padding(vertical = 1.dp)
                    .padding(start = if (st.isOp) 14.dp else 0.dp).tourTarget("step:$i")) {
                Column(Modifier.clip(RoundedCornerShape(12.dp)).clickable { onPick(i) }
                    .padding(horizontal = 10.dp, vertical = 9.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(st.labelIn(here), fontFamily = Mono, fontSize = if (st.isOp) 11.sp else 12.sp,
                            color = MaterialTheme.colorScheme.primary, modifier = Modifier.width(34.dp))
                        Text(st.title, fontFamily = PlexSans, fontSize = if (st.isOp) 12.5f.sp else 13.5f.sp,
                            fontWeight = if (on) FontWeight.SemiBold else FontWeight.Normal,
                            color = MaterialTheme.colorScheme.onSurface)
                    }
                    AnimatedVisibility(visible = on) {
                        Column(Modifier.padding(start = 34.dp, top = 5.dp)) {
                            Text(st.body, fontFamily = PlexSans, fontSize = 12.5f.sp, lineHeight = 18.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                            RegionLine(st)
                            StepSource(flow, st)
                            CompareBlock(flow, st, onCompare)
                        }
                    }
                }
            }
        }
        val refs = flow.refs.mapNotNull { lib.refs[it] }
        if (refs.isNotEmpty()) item {
            SectionLabel("Sources cited")
            for (r in refs) {
                Text("[${r.id}] ${r.title} — ${r.publisher}", fontFamily = PlexSans, fontSize = 12.sp,
                    lineHeight = 17.sp, color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp))
                        .clickable { onRef(r.url) }.padding(vertical = 6.dp))
            }
        }
    }
}

/* =============================================================== tabs ==== */

@Composable
private fun ViewsTab(scene: Scene, viewKey: String, onPick: (ViewPreset) -> Unit) {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp),
        contentPadding = PaddingValues(bottom = 12.dp)) {
        itemsIndexed(scene.views) { i, v ->
            val on = v.key == viewKey
            val bg by animateColorAsState(
                if (on) MaterialTheme.colorScheme.primaryContainer
                else MaterialTheme.colorScheme.surfaceVariant, tween(220), label = "viewBg")
            Surface(color = bg, shape = RoundedCornerShape(14.dp),
                modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp).tourTarget("view:$i")
                    .clickable { onPick(v) }) {
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
                       spin: Boolean, seeThrough: Float?, onSeeThrough: (Float) -> Unit,
                       onClip: (Int, Float) -> Unit, onExplode: (Float) -> Unit,
                       onGhost: (Boolean) -> Unit, onDims: (Boolean) -> Unit,
                       onTex: (Boolean) -> Unit, onEdges: (Boolean) -> Unit,
                       onSpin: (Boolean) -> Unit, onReset: () -> Unit, header: @Composable () -> Unit = {}) {
    val haptic = LocalHapticFeedback.current
    fun toggle(t: Toggle) { haptic.performHapticFeedback(HapticFeedbackType.LongPress); t.set(!t.on) }

    Column(Modifier.verticalScroll(rememberScrollState())) {
        header()
        SliderRow("Cut along channel", "X", cx, scene.lo[0], scene.hi[0], true) { onClip(0, it) }
        SliderRow("Cut vertically", "Y", cy, scene.lo[1], scene.hi[1], true) { onClip(1, it) }
        SliderRow("Cut across channel", "Z", cz, scene.lo[2], scene.hi[2], true) { onClip(2, it) }
        SliderRow("Separate layers", "", explode, 0f, 16f, false) { onExplode(it) }
        Spacer(Modifier.height(4.dp))
        SectionLabel("Display")
        // The floating sheet only (null on the tablet, whose panel covers nothing).
        if (seeThrough != null)
            SliderRow("Sheet see-through", "", seeThrough, 0f, 1f, false,
                shown = "${(seeThrough * SEE_MAX * 100).roundToInt()}%", tag = "slider:sheet") { onSeeThrough(it) }
        // The display switches used to be full-width rows. As a wrapping grid of compact
        // toggle chips — the same pill used for picking a technology, repurposed as on/off —
        // they take about half the vertical room, which is the point on a phone screen.
        val toggles = listOf(
            Toggle("Edge outlines", edges, onEdges),
            Toggle("Surface texture", tex, onTex),
            Toggle("Dimension callouts", dims, onDims),
            Toggle("Ghost the gate fill", ghost, onGhost),
            Toggle("Slow rotate", spin, onSpin))
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
internal fun SectionLabel(text: String) {
    Text(text, style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 10.dp, bottom = 4.dp))
}

@Composable
private fun SliderRow(label: String, axis: String, frac: Float, lo: Float, hi: Float,
                      offAtMax: Boolean, shown: String? = null, tag: String? = null,
                      onChange: (Float) -> Unit) {
    Column(Modifier.padding(vertical = 2.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(label, fontFamily = PlexSans, fontSize = 13.sp,
                color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.weight(1f))
            if (axis.isNotEmpty()) {
                Text(axis, fontFamily = Mono, fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(end = 8.dp))
            }
            val nm = lo + (hi - lo) * frac
            Text(shown ?: if (offAtMax && frac >= 0.999f) "off" else "${(nm * 10).roundToInt() / 10f} nm",
                fontFamily = Mono, fontSize = 11.5f.sp,
                color = if (offAtMax && frac >= 0.999f) MaterialTheme.colorScheme.onSurfaceVariant
                        else MaterialTheme.colorScheme.primary)
        }
        Box(Modifier.fillMaxWidth().height(44.dp)
            .then(when {
                tag != null -> Modifier.tourTarget(tag)
                axis.isNotEmpty() -> Modifier.tourTarget("slider:${axis.lowercase()}")
                else -> Modifier
            }),
            contentAlignment = Alignment.Center) {
            Slider(value = frac, onValueChange = onChange, valueRange = 0f..1f)
        }
    }
}

@Composable
private fun LayersTab(lib: Library, scene: Scene, tick: Int, list: LazyListState,
                      onSet: (List<Part>, Boolean) -> Unit) {
    val grouped = remember(tick, scene) {
        scene.groups.map { g -> g to scene.parts.filter { it.group == g } }
            .filter { it.second.isNotEmpty() }
    }
    val anyVisible = scene.parts.any { it.visible }
    // Two columns of layers wherever a half-width cell still fits a name; one on narrow
    // screens and the tablet side panel.
    BoxWithConstraints {
        val cols = if (maxWidth >= 300.dp) 2 else 1
        LazyColumn(state = list, contentPadding = PaddingValues(bottom = 14.dp),
            modifier = Modifier.tourTarget("list:layers")) {
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
            grouped.forEachIndexed { gi, (g, parts) ->
                item(key = "h_$g") {
                    val groupOn = parts.any { it.visible }
                    Row(Modifier.fillMaxWidth().heightIn(min = 36.dp).tourTarget("group:$gi")
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
                items(parts.chunked(cols), key = { it.first().id }) { row ->
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        for (p in row) LayerCell(lib, p, p.visible, Modifier.weight(1f)) { onSet(listOf(p), it) }
                        repeat(cols - row.size) { Spacer(Modifier.weight(1f)) }
                    }
                }
            }
        }
    }
}

/** One layer: the whole cell toggles it. Names get two lines, since a half-width
 *  cell would cut most of them off at one. [visible] is passed rather than read off
 *  [p], which is not snapshot state, so a toggle always redraws the cell. */
@Composable
private fun LayerCell(lib: Library, p: Part, visible: Boolean, modifier: Modifier, onSet: (Boolean) -> Unit) {
    val alpha by animateFloatAsState(if (visible) 1f else 0.42f, tween(200), label = "layerAlpha")
    Row(modifier.heightIn(min = 48.dp)
        .clip(RoundedCornerShape(12.dp))
        .toggleable(value = visible, role = Role.Checkbox, onValueChange = onSet)
        .padding(horizontal = 4.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically) {
        // Drawn only: the cell is the touch target, so the box needs no 48dp of its own.
        Checkbox(checked = visible, onCheckedChange = null)
        Spacer(Modifier.width(8.dp))
        Box(Modifier.size(11.dp).clip(RoundedCornerShape(3.dp))
            .graphicsLayer { this.alpha = alpha }
            .background(matColor(lib, p.material)))
        Spacer(Modifier.width(8.dp))
        Text(p.name, fontFamily = PlexSans, fontSize = 12.5f.sp, lineHeight = 15.sp, maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.graphicsLayer { this.alpha = alpha },
            color = MaterialTheme.colorScheme.onSurface)
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
    itemsIndexed(P.terms, key = { _, t -> t.id }) { i, t ->
        val on = picked == t.id
        Surface(
            color = if (on) MaterialTheme.colorScheme.secondaryContainer else Color.Transparent,
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier.fillMaxWidth().padding(vertical = 1.dp).tourTarget("par:$i")
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
private fun SpecsTab(scene: Scene, picked: String?, list: LazyListState, onPick: (Parasitic?) -> Unit) {
    LazyColumn(state = list, contentPadding = PaddingValues(bottom = 16.dp),
        modifier = Modifier.tourTarget("list:specs")) {
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
