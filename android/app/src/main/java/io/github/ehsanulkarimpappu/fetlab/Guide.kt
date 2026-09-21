package io.github.ehsanulkarimpappu.fetlab

import android.content.Context
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
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

/* ============================================================== dimming == */

/**
 * Wraps [content] with its own darkening scrim. During the tour every region that
 * is not the current step's subject dims — a spotlight made of several honest
 * rectangles instead of one hole punched in a full-screen overlay, so it needs no
 * cross-composable coordinate math to stay correct as the layout changes underneath it.
 */
@Composable
fun Dimmable(dim: Boolean, modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Box(modifier) {
        content()
        val alpha by animateFloatAsState(if (dim) 0.72f else 0f, tween(280), label = "dim")
        if (alpha > 0.01f)
            Box(Modifier.matchParentSize().background(Color.Black.copy(alpha = alpha)))
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
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.Top) {
            GestureGlyph(stop.gesture, MaterialTheme.colorScheme.onPrimaryContainer,
                Modifier.padding(end = 12.dp, top = 2.dp))
            Column(Modifier.weight(1f)) {
                Text("${stop.category.uppercase()} · ${step + 1}/$total",
                    fontFamily = Mono, fontSize = 10.sp, letterSpacing = 1.2f.sp,
                    color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.7f))
                Text(stop.title, style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                    modifier = Modifier.padding(top = 2.dp, bottom = 4.dp))
                Text(stop.body, fontFamily = PlexSans, fontSize = 13.sp, lineHeight = 18.sp,
                    color = MaterialTheme.colorScheme.onPrimaryContainer)
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
