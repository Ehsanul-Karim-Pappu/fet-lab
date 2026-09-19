package io.github.ehsanulkarimpappu.fetlab

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import androidx.datastore.preferences.core.emptyPreferences
import org.json.JSONObject
import java.io.IOException

private val Context.guideStore by preferencesDataStore(name = "guide")
private val tourVersionKey = intPreferencesKey("tour_version")

class GuidePreferences(private val ctx: Context) {
    val version = ctx.guideStore.data.catch { e ->
        if (e is IOException) emit(emptyPreferences()) else throw e
    }.map { it[tourVersionKey] ?: 0 }

    suspend fun dismiss(version: Int) {
        try { ctx.guideStore.edit { it[tourVersionKey] = version } }
        catch (_: IOException) { /* The explorer remains usable if local storage is full. */ }
    }
}

data class FeatureDestination(
    val id: String, val category: String, val title: String, val description: String,
    val scene: String, val view: String, val tab: String, val target: String, val peek: Boolean
)

class GuideCatalog(val version: Int, val features: List<FeatureDestination>, val tour: List<String>) {
    fun feature(id: String) = features.first { it.id == id }
    companion object {
        fun load(ctx: Context): GuideCatalog {
            val root = JSONObject(ctx.assets.open("guide.json").bufferedReader().use { it.readText() })
            val list = root.getJSONArray("features")
            val steps = root.getJSONArray("tour")
            return GuideCatalog(root.getInt("version"), List(list.length()) { i ->
                val f = list.getJSONObject(i)
                FeatureDestination(f.getString("id"), f.getString("category"), f.getString("title"),
                    f.getString("description"), f.getString("scene"), f.getString("view"),
                    f.getString("tab"), f.getString("target"), f.optBoolean("peek", false))
            }, List(steps.length()) { steps.getString(it) })
        }
    }
}

val LocalGuideFocus = compositionLocalOf { "" }

/** Highlight and reveal the real control, using its layout rather than screen coordinates. */
@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
fun Modifier.guideTarget(id: String): Modifier = composed {
    val focus = LocalGuideFocus.current
    val requester = remember { BringIntoViewRequester() }
    LaunchedEffect(focus) {
        if (focus == id) {
            withFrameNanos { }
            requester.bringIntoView()
        }
    }
    this.bringIntoViewRequester(requester).then(
        if (focus == id) Modifier.border(2.dp, MaterialTheme.colorScheme.primary, RoundedCornerShape(12.dp))
        else Modifier
    )
}

@Composable
fun WelcomeGuide(onStart: () -> Unit, onSkip: () -> Unit) {
    AlertDialog(onDismissRequest = onSkip,
        title = { Text("Explore logic devices in 3D") },
        text = { Text("Take a short guided tour of views, sections, layers and inverter logic. You can skip it now and replay it anytime from Help.") },
        confirmButton = { TextButton(onClick = onStart) { Text("Start tour") } },
        dismissButton = { TextButton(onClick = onSkip) { Text("Explore myself") } })
}

@Composable
fun FeatureGuide(catalog: GuideCatalog, onOpen: (FeatureDestination) -> Unit,
                 onTour: () -> Unit, onAbout: () -> Unit, onClose: () -> Unit) {
    var query by remember { mutableStateOf("") }
    val matches = catalog.features.filter {
        "${it.title} ${it.description} ${it.category}".contains(query, ignoreCase = true)
    }
    Dialog(onDismissRequest = onClose, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxWidth().widthIn(max = 640.dp).fillMaxHeight(.92f).padding(12.dp),
            shape = RoundedCornerShape(24.dp)) {
            Column(Modifier.padding(18.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Help & features", style = MaterialTheme.typography.titleLarge)
                    TextButton(onClick = onClose) { Text("Close") }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = onTour) { Text("Guided tour") }
                    OutlinedButton(onClick = onAbout) { Text("About") }
                }
                OutlinedTextField(query, { query = it }, label = { Text("Find a feature") },
                    singleLine = true, modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp))
                if (matches.isEmpty()) Text("No matching features. Try views, layers or logic.")
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(matches, key = { it.id }) { f ->
                        Surface(onClick = { onOpen(f) }, shape = RoundedCornerShape(14.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant) {
                            Column(Modifier.fillMaxWidth().padding(14.dp)) {
                                Text(f.category, style = MaterialTheme.typography.labelSmall)
                                Text(f.title, style = MaterialTheme.typography.titleMedium)
                                Text(f.description, style = MaterialTheme.typography.bodySmall)
                                Text("Open feature →", color = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.padding(top = 8.dp))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun TourCard(feature: FeatureDestination, step: Int, total: Int, modifier: Modifier = Modifier,
             onBack: () -> Unit, onNext: () -> Unit, onExit: () -> Unit) {
    BackHandler(onBack = onExit)
    Surface(modifier.semantics { liveRegion = LiveRegionMode.Polite },
        color = MaterialTheme.colorScheme.surface.copy(alpha = .97f),
        shape = RoundedCornerShape(16.dp), border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary)) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 8.dp)) {
            Text("Guided tour · ${step + 1} / $total · ${feature.title}",
                style = MaterialTheme.typography.titleSmall)
            Text(feature.description, style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 4.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                TextButton(onClick = onExit) { Text("Skip tour") }
                Row {
                    TextButton(onClick = onBack, enabled = step > 0) { Text("Back") }
                    TextButton(onClick = onNext) { Text(if (step == total - 1) "Finish" else "Next") }
                }
            }
        }
    }
}
