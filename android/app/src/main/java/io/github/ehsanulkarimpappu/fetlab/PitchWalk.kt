package io.github.ehsanulkarimpappu.fetlab

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.roundToInt

/*
 * The SAQP pitch-walk lesson's controls: the first-core width and the two spacer
 * thicknesses, and the lines they make. The construction is the generator's own
 * (pw_geometry in scripts/build_process.py): first cores at the printed pitch, a first
 * spacer on each side (the second cores), a second spacer on each side of those (the final
 * lines). Every space is measured off the constructed lines and typed by where it came from.
 */

/** The lesson's fixed numbers, from the flow's "pitchwalk" block. */
class PitchWalk(val p1: Float, val cores: Int, val base: Map<String, Float>,
                val range: Map<String, Pair<Float, Float>>, val gmin: Float,
                val types: Map<String, Pair<String, String>>, val note: String)

/** One constructed image: spans across the lines (nm), and each space's type and width. */
class PwImage(val core1: List<Pair<Float, Float>>, val core2: List<Pair<Float, Float>>,
              val lines: List<Pair<Float, Float>>, val gaps: List<Pair<String, Float>>)

fun pwImage(pw: PitchWalk, w1: Float, s1: Float, s2: Float): PwImage {
    val cc = List(pw.cores) { pw.p1 * (it - (pw.cores - 1) / 2f) }
    val core1 = cc.map { (it - w1 / 2) to (it + w1 / 2) }
    val core2 = ArrayList<Pair<Pair<Float, Float>, Int>>()
    core1.forEachIndexed { i, (a, b) -> core2 += ((a - s1) to a) to i; core2 += (b to (b + s1)) to i }
    // Each final line with the second core and first core it came from.
    val lines = ArrayList<Triple<Pair<Float, Float>, Int, Int>>()
    core2.forEachIndexed { j, (s, i) ->
        lines += Triple((s.first - s2) to s.first, j, i); lines += Triple(s.second to (s.second + s2), j, i)
    }
    lines.sortBy { it.first.first }
    val gaps = lines.zipWithNext { l, r ->
        val t = if (l.second == r.second) "a" else if (l.third == r.third) "b" else "c"
        t to (r.first.first - l.first.second)
    }
    return PwImage(core1, core2.map { it.first }, lines.map { it.first }, gaps)
}

/** The range a control may take with the other two where they are: every width stays
 *  positive and no two spacers meet, with at least [PitchWalk.gmin] between them. */
private fun pwLimits(pw: PitchWalk, k: String, w1: Float, s1: Float, s2: Float): Pair<Float, Float> {
    val g = pw.gmin
    val (lo0, hi0) = pw.range[k] ?: (0f to 1f)
    val (lo, hi) = when (k) {
        "w1" -> (2 * s2 + g) to (pw.p1 - 2 * s1 - 2 * s2 - g)
        "s1" -> g to ((pw.p1 - w1 - 2 * s2 - g) / 2)
        else -> g to minOf((w1 - g) / 2, (pw.p1 - w1 - 2 * s1 - g) / 2)
    }
    val a = maxOf(lo0, lo); val b = minOf(hi0, hi)
    return a to maxOf(a, b)
}

private fun nm(x: Float): String {
    val r = (x * 10).roundToInt() / 10f
    return if (r == r.roundToInt().toFloat()) "${r.roundToInt()}" else "$r"
}

@Composable
fun PitchWalkPanel(lib: Library, pw: PitchWalk) {
    var w1 by rememberSaveable { mutableFloatStateOf(pw.base["w1"] ?: 33f) }
    var s1 by rememberSaveable { mutableFloatStateOf(pw.base["s1"] ?: 21f) }
    var s2 by rememberSaveable { mutableFloatStateOf(pw.base["s2"] ?: 6f) }
    val img = pwImage(pw, w1, s1, s2)
    val widths = img.gaps.map { it.second }
    val gmax = widths.maxOrNull() ?: 0f
    val gmin = widths.minOrNull() ?: 0f
    val tcol = mapOf("a" to Color(0xFF2E8BC0), "b" to Color(0xFFE08A1E), "c" to Color(0xFF8E5CC7))
    fun mat(k: String) = lib.materials[k]?.color?.let { Color(it[0], it[1], it[2]) } ?: Color.Gray
    val onV = MaterialTheme.colorScheme.onSurfaceVariant

    Surface(color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f), shape = RoundedCornerShape(12.dp),
        modifier = Modifier.fillMaxWidth().padding(bottom = 10.dp)) {
        Column(Modifier.padding(10.dp)) {
            Text("TRY IT · THE SAME ROUTE, DIMENSIONS LET GO", fontFamily = Mono, fontSize = 10.sp, color = onV)
            // Before (first cores and first spacers), between (second cores and spacers) and
            // after (the lines), stacked as cross-sections on one scale; then the lines from above.
            val lo = img.core1.first().first - s1 - s2 - 6f
            val hi = img.core1.last().second + s1 + s2 + 6f
            Canvas(Modifier.fillMaxWidth().height(150.dp).padding(top = 6.dp).semantics {
                contentDescription = "Cross-sections of the ${img.lines.size} lines: first cores and first spacers, " +
                    "second cores and second spacers, the lines, and the lines from above. " +
                    "Spaces range from ${nm(gmin)} to ${nm(gmax)} nm."
            }) {
                val sx = size.width / (hi - lo)
                fun x(u: Float) = (u - lo) * sx
                val row = size.height / 4f
                fun bar(spans: List<Pair<Float, Float>>, r: Int, h: Float, c: Color) {
                    for ((a, b) in spans) drawRect(c, Offset(x(a), r * row + row - h), Size((b - a) * sx, h))
                }
                val base = row * 0.18f
                for (r in 0..2) drawRect(mat("si3n4").copy(alpha = 0.5f), Offset(0f, r * row + row - base), Size(size.width, base))
                bar(img.core1, 0, row * 0.7f, mat("mandrel"))
                bar(img.core2, 0, row * 0.7f, mat("patspacer"))
                bar(img.core2, 1, row * 0.55f, mat("mandrel2"))
                bar(img.lines, 1, row * 0.55f, mat("patspacer"))
                bar(img.lines, 2, row * 0.75f, mat("silicon"))
                // Each space marked by its type under the lines, and the lines from above.
                img.lines.zipWithNext().forEachIndexed { i, (l, r) ->
                    val c = tcol[img.gaps[i].first] ?: Color.Gray
                    drawRect(c, Offset(x(l.second), 3 * row - base), Size((r.first - l.second) * sx, base))
                }
                bar(img.lines, 3, row * 0.8f, mat("silicon"))
            }
            Row(Modifier.fillMaxWidth()) {
                for (label in listOf("First cores + first spacers", "Second cores + second spacers", "Lines · from above"))
                    Text(label, fontFamily = PlexSans, fontSize = 10.5f.sp, color = onV, modifier = Modifier.weight(1f))
            }
            for ((k, name) in listOf("w1" to "First-core width", "s1" to "First-spacer thickness",
                                     "s2" to "Second-spacer thickness")) {
                val v = when (k) { "w1" -> w1; "s1" -> s1; else -> s2 }
                val (a, b) = pwLimits(pw, k, w1, s1, s2)
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 4.dp)) {
                    Text(name, fontFamily = PlexSans, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.weight(1f))
                    Text("${nm(v)} nm", fontFamily = Mono, fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
                }
                Slider(value = v.coerceIn(a, b), valueRange = a..b, steps = maxOf(0, ((b - a) * 2).roundToInt() - 1),
                    onValueChange = { nv ->
                        val r = (nv * 2).roundToInt() / 2f
                        when (k) { "w1" -> w1 = r; "s1" -> s1 = r; else -> s2 = r }
                    }, modifier = Modifier.height(28.dp).semantics { contentDescription = name })
            }
            for (t in listOf("a", "b", "c")) {
                val ws = img.gaps.filter { it.first == t }.map { it.second }.distinct()
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 2.dp)) {
                    Canvas(Modifier.width(10.dp).height(10.dp)) { drawRect(tcol[t] ?: Color.Gray) }
                    Text("  Space ${pw.types[t]?.first ?: t}: ${ws.joinToString(" / ") { nm(it) }} nm",
                        fontFamily = PlexSans, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface)
                }
            }
            Text("Largest ${nm(gmax)} nm · smallest ${nm(gmin)} nm · pitch walk = ${nm(gmax)} − ${nm(gmin)} = ${nm(gmax - gmin)} nm" +
                 " · line width ${nm(s2)} nm", fontFamily = Mono, fontSize = 11.sp, fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 6.dp))
            Text(pw.note, fontFamily = PlexSans, fontSize = 11.sp, lineHeight = 15.sp, color = onV,
                modifier = Modifier.padding(top = 4.dp))
            TextButton(onClick = { w1 = pw.base["w1"] ?: w1; s1 = pw.base["s1"] ?: s1; s2 = pw.base["s2"] ?: s2 }) {
                Text("Back to the ideal case", fontFamily = PlexSans, fontSize = 12.sp)
            }
        }
    }
}
