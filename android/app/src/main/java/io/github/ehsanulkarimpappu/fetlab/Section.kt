package io.github.ehsanulkarimpappu.fetlab

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/*
 * Section planes: a 2D section cut from the scene on screen, the same geometry the 3D view
 * draws, and a top-down locator that shows where the plane runs and which side is seen.
 * All of it is computed on the device from the scene's boxes, so it works offline.
 *
 * Frame: x runs along the channel, source to drain; z across neighbouring fins or stacks;
 * y up. A plane across x is seen from +x, so +z lies to the viewer's left; a plane across z
 * is seen from +z, so x (source to drain) runs left to right. The 3D section views use the
 * same cameras.
 */

/** One box of [part] cut by a plane, in the plane's own coordinates: [u] across the screen
 *  (left to right as seen), [v] up. */
class SecRect(val part: Part, val u0: Float, val u1: Float, val v0: Float, val v1: Float)

fun sectionOf(sc: Scene, pl: SectionPlane): List<SecRect> {
    val out = ArrayList<SecRect>()
    val pos = pl.posAt(sc.step?.scale)
    for (p in sc.parts) {
        if (!p.visible) continue
        for (b in p.boxes) {
            val cx = b[0]; val cy = b[1]; val cz = b[2]
            val hx = b[3] / 2f; val hy = b[4] / 2f; val hz = b[5] / 2f
            if (pl.axis == 'x') {
                if (cx - hx < pos && cx + hx > pos)
                    out.add(SecRect(p, -(cz + hz), -(cz - hz), cy - hy, cy + hy))
            } else {
                if (cz - hz < pos && cz + hz > pos)
                    out.add(SecRect(p, cx - hx, cx + hx, cy - hy, cy + hy))
            }
        }
    }
    return out
}

/** Screen placement of section coordinates: fit [rects] into [w] x [h] with a margin, y up. */
private class Fit(rects: List<SecRect>, w: Float, h: Float, margin: Float) {
    private val u0 = rects.minOfOrNull { it.u0 } ?: 0f
    private val u1 = rects.maxOfOrNull { it.u1 } ?: 1f
    private val v0 = rects.minOfOrNull { it.v0 } ?: 0f
    private val v1 = rects.maxOfOrNull { it.v1 } ?: 1f
    val s = minOf((w - 2 * margin) / maxOf(u1 - u0, 1e-3f), (h - 2 * margin) / maxOf(v1 - v0, 1e-3f))
    private val ox = (w - (u1 - u0) * s) / 2f
    private val oy = (h - (v1 - v0) * s) / 2f
    fun x(u: Float) = ox + (u - u0) * s
    fun y(v: Float) = oy + (v1 - v) * s
    fun u(x: Float) = u0 + (x - ox) / s
    fun v(y: Float) = v1 - (y - oy) / s
}

private fun rgb(c: FloatArray, a: Float = 1f) = Color(c[0], c[1], c[2], a)

/** The section drawn flat: every cut box in its material's colour, the [selected] part
 *  outlined in both this and the 3D view; a tap picks the part under the finger. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SectionPanel(lib: Library, sc: Scene, pl: SectionPlane, selected: Part?, onPick: (Part?) -> Unit,
                 modifier: Modifier = Modifier, corner: @Composable () -> Unit = {}) {
    val rects = sectionOf(sc, pl)
    val accent = MaterialTheme.colorScheme.primary
    val edge = MaterialTheme.colorScheme.outline
    Column(modifier.background(MaterialTheme.colorScheme.surface)) {
        // The heading, with the locator beside it rather than over the drawing.
        Row(Modifier.fillMaxWidth().padding(start = 12.dp, top = 8.dp, end = 8.dp),
            verticalAlignment = Alignment.Top) {
            Text("SECTION · ${pl.name}".uppercase(), fontFamily = Mono, fontSize = 10.sp, lineHeight = 13.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f).padding(end = 8.dp))
            corner()
        }
        Box(Modifier.weight(1f).fillMaxWidth()) {
            // Read aloud: which plane, and what it cuts, since the drawing itself is not.
            val said = rects.map { it.part.material }.distinct().mapNotNull { lib.materials[it]?.label }
            Canvas(Modifier.matchParentSize().semantics {
                contentDescription = "2D section, ${pl.name}. " + if (said.isEmpty()) "It cuts nothing in this step."
                    else "It cuts: " + said.joinToString(", ") + ". Tap a material to select it in 3D."
            }.pointerInput(rects) {
                detectTapGestures { off ->
                    val f = Fit(rects, size.width.toFloat(), size.height.toFloat(), 18f)
                    val u = f.u(off.x); val v = f.v(off.y)
                    // The smallest box under the finger, so a thin film beats the block behind it.
                    onPick(rects.filter { u in it.u0..it.u1 && v in it.v0..it.v1 }
                        .minByOrNull { (it.u1 - it.u0) * (it.v1 - it.v0) }?.part)
                }
            }) {
                if (rects.isEmpty()) return@Canvas
                val f = Fit(rects, size.width, size.height, 18f)
                for (r in rects) {
                    val m = lib.materials[r.part.material]?.color ?: floatArrayOf(.6f, .6f, .6f)
                    val tl = Offset(f.x(r.u0), f.y(r.v1)); val sz = Size((r.u1 - r.u0) * f.s, (r.v1 - r.v0) * f.s)
                    drawRect(rgb(m), tl, sz)
                    drawRect(edge.copy(alpha = 0.55f), tl, sz, style = Stroke(1f))
                }
                for (r in rects) if (r.part === selected) {
                    drawRect(accent, Offset(f.x(r.u0), f.y(r.v1)),
                        Size((r.u1 - r.u0) * f.s, (r.v1 - r.v0) * f.s), style = Stroke(3.5f))
                }
            }
            if (rects.isEmpty())
                Text("This plane does not cut anything in this step.", fontFamily = PlexSans, fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.align(Alignment.Center))
        }
        // Which way the page runs, so a student can hold it against a figure.
        Text(if (pl.axis == 'x') "← +z across the ${sc.acrossWord()}   ·   up: y   ·   seen from +x (drain side)"
             else "x: source → drain   ·   up: y   ·   seen from +z",
            fontFamily = Mono, fontSize = 10.5f.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 12.dp))
        FlowRow(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            for (mk in rects.map { it.part.material }.distinct()) {
                val m = lib.materials[mk] ?: continue
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(9.dp).clip(RoundedCornerShape(2.dp)).background(rgb(m.color)))
                    Text(" " + m.label, fontFamily = PlexSans, fontSize = 10.5f.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        selected?.let {
            Text("Selected: ${it.name}", fontFamily = PlexSans, fontSize = 11.sp, fontWeight = FontWeight.SemiBold,
                color = accent, modifier = Modifier.padding(start = 12.dp, end = 12.dp, bottom = 8.dp))
        }
    }
}

/** What neighbouring lines are called in this scene, for the axis caption. */
private fun Scene.acrossWord() = if (parts.any { it.group == "Fins" }) "fins" else "stacks"

/** Top-down locator: the scene's footprint (x across, z up the page), the section plane as
 *  a dashed line, and an arrow for the side the section is seen from. */
@Composable
fun Locator(lib: Library, sc: Scene, pl: SectionPlane?, modifier: Modifier = Modifier) {
    val accent = MaterialTheme.colorScheme.primary
    val ink = MaterialTheme.colorScheme.onSurfaceVariant
    Canvas(modifier.semantics {
        contentDescription = if (pl == null) "Locator, seen from above: choose a section plane to place it"
            else "Locator, seen from above: the dashed line is the plane ${pl.name}, the arrow the side it is seen from"
    }) {
        val x0 = sc.lo[0]; val x1 = sc.hi[0]; val z0 = sc.lo[2]; val z1 = sc.hi[2]
        val m = 10f
        val s = minOf((size.width - 2 * m) / (x1 - x0), (size.height - 2 * m) / (z1 - z0))
        val ox = (size.width - (x1 - x0) * s) / 2f; val oy = (size.height - (z1 - z0) * s) / 2f
        fun px(x: Float) = ox + (x - x0) * s
        fun pz(z: Float) = oy + (z1 - z) * s          // +z up the page
        drawRect(ink.copy(alpha = 0.35f), Offset(px(x0), pz(z1)), Size((x1 - x0) * s, (z1 - z0) * s), style = Stroke(1f))
        // Footprints of the lines and gates, the parts a student orients by.
        for (p in sc.parts) {
            if (!p.visible) continue
            val keep = p.group in setOf("Fins", "Superlattice", "Channel", "Dummy gate", "Gate electrode") ||
                p.material in setOf("poly", "mo")
            if (!keep) continue
            val c = lib.materials[p.material]?.color ?: continue
            for (b in p.boxes) {
                val bx0 = b[0] - b[3] / 2; val bx1 = b[0] + b[3] / 2; val bz0 = b[2] - b[5] / 2; val bz1 = b[2] + b[5] / 2
                drawRect(rgb(c, 0.55f), Offset(px(bx0), pz(bz1)), Size((bx1 - bx0) * s, (bz1 - bz0) * s))
            }
        }
        if (pl == null) return@Canvas
        val dash = PathEffect.dashPathEffect(floatArrayOf(10f, 7f))
        if (pl.axis == 'x') {
            val x = px(pl.posAt(sc.step?.scale))
            drawLine(accent, Offset(x, pz(z1)), Offset(x, pz(z0)), strokeWidth = 3f, pathEffect = dash)
            // Seen from +x: the eye is on the drain side, looking back toward the source.
            val y = pz((z0 + z1) / 2)
            drawLine(accent, Offset(x + 34f, y), Offset(x + 6f, y), strokeWidth = 3f)
            drawLine(accent, Offset(x + 6f, y), Offset(x + 16f, y - 8f), strokeWidth = 3f)
            drawLine(accent, Offset(x + 6f, y), Offset(x + 16f, y + 8f), strokeWidth = 3f)
        } else {
            val y = pz(pl.posAt(sc.step?.scale))
            drawLine(accent, Offset(px(x0), y), Offset(px(x1), y), strokeWidth = 3f, pathEffect = dash)
            val x = px((x0 + x1) / 2)
            drawLine(accent, Offset(x, y - 34f), Offset(x, y - 6f), strokeWidth = 3f)
            drawLine(accent, Offset(x, y - 6f), Offset(x - 8f, y - 16f), strokeWidth = 3f)
            drawLine(accent, Offset(x, y - 6f), Offset(x + 8f, y - 16f), strokeWidth = 3f)
        }
    }
}

/** The Section tab's head in Process mode: pick a plane, and 3D, section or both. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun PlanesBlock(lib: Library, sc: Scene, planes: List<SectionPlane>, planeId: String?, mode: Int,
                onPlane: (SectionPlane) -> Unit, onMode: (Int) -> Unit) {
    SectionLabel("SECTION PLANES")
    FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(5.dp),
        verticalArrangement = Arrangement.spacedBy(5.dp)) {
        for ((i, p) in planes.withIndex()) Chip(p.short, p.id == planeId, Modifier.tourTarget("plane:$i")) { onPlane(p) }
    }
    val pl = planes.firstOrNull { it.id == planeId }
    Row(Modifier.fillMaxWidth().padding(top = 5.dp), horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        for ((i, name) in listOf("3D", "Section", "Both").withIndex())
            Chip(name, mode == i && pl != null, Modifier.weight(1f)) { if (pl != null) onMode(i) }
    }
    Surface(color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f), shape = RoundedCornerShape(12.dp),
        modifier = Modifier.fillMaxWidth().padding(top = 5.dp)) {
        // The locator beside its explanation, so the block stays short.
        Row(Modifier.padding(8.dp), verticalAlignment = Alignment.Top) {
            Locator(lib, sc, pl, Modifier.size(width = 104.dp, height = 68.dp))
            Column(Modifier.weight(1f).padding(start = 8.dp)) {
                Text("From above: x runs source → drain, z across the ${sc.acrossWord()}; dashed: the plane, " +
                        "arrow: the side seen.",
                    fontFamily = PlexSans, fontSize = 10.5f.sp, lineHeight = 14.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (pl != null) Text(pl.text, fontFamily = PlexSans, fontSize = 10.5f.sp, lineHeight = 14.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 3.dp))
            }
        }
    }
}

/** Under a step in the Steps tab: the step set against its source, plane by plane. */
@Composable
fun CompareBlock(flow: ProcessFlow, st: ProcessStep, onShow: (SectionPlane) -> Unit) {
    for (c in st.compare) {
        val pl = flow.plane(c.plane) ?: continue
        Surface(color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f), shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
            Column(Modifier.padding(10.dp)) {
                Text("COMPARE WITH THE SOURCE · ${pl.short.uppercase()}", fontFamily = Mono, fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                @Composable fun line(head: String, body: String) {
                    if (body.isEmpty()) return
                    Text(head, fontFamily = PlexSans, fontSize = 11.sp, fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.padding(top = 6.dp))
                    Text(body, fontFamily = PlexSans, fontSize = 11.5f.sp, lineHeight = 16.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                line("Source", "[${c.src}] Fig. " + c.figs.joinToString(", "))
                line("What the source's text describes", c.described)
                line("What the app shows in this plane (${pl.name.lowercase()})", c.visible.joinToString(", "))
                line("Left out or different", c.omitted.joinToString("; "))
                line(if (c.status == "visual") "Checked against the drawing" else "Not yet checked against the drawing",
                    c.statusText + ". " + pl.text)
                Text("Show this section", fontFamily = PlexSans, fontSize = 12.5f.sp, fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(top = 8.dp).clip(RoundedCornerShape(8.dp))
                        .border(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.6f), RoundedCornerShape(8.dp))
                        .clickable { onShow(pl) }.padding(horizontal = 10.dp, vertical = 6.dp))
            }
        }
    }
}
