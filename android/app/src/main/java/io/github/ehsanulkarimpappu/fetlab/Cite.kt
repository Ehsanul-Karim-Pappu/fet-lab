package io.github.ehsanulkarimpappu.fetlab

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.buildAnnotatedString

/**
 * Citations ("[R13]", "[R1, R2]") anywhere in the app's text open the About screen at that
 * reference, as the web page's do. A tapped citation is left here as [pending]; the app
 * opens About on it and clears it.
 */
class RefNav { var pending by mutableStateOf<String?>(null) }

val LocalRefNav = staticCompositionLocalOf { RefNav() }

private val CITE = Regex("""\[(R\d+(?:,\s*R\d+)*)]""")

/** [s] with every citation in it made a link to its reference. */
@Composable
fun cited(s: String): AnnotatedString = cited(AnnotatedString(s))

/** [s], styles kept, with every citation in it made a link to its reference. A single
 *  citation is one link, brackets and all; in a list each reference is its own. */
@Composable
fun cited(s: AnnotatedString): AnnotatedString {
    val nav = LocalRefNav.current
    val color = MaterialTheme.colorScheme.primary
    return remember(s, nav, color) {
        if ("[R" !in s.text) s else buildAnnotatedString {
            append(s)
            val style = TextLinkStyles(SpanStyle(color = color))
            fun link(id: String, start: Int, end: Int) =
                addLink(LinkAnnotation.Clickable("ref:$id", style) { nav.pending = id }, start, end)
            for (m in CITE.findAll(s.text)) {
                val ids = m.groupValues[1].split(",").map { it.trim() }
                if (ids.size == 1) { link(ids[0], m.range.first, m.range.last + 1); continue }
                var from = m.range.first
                for (id in ids) {
                    val at = s.text.indexOf(id, from)
                    link(id, at, at + id.length)
                    from = at + id.length
                }
            }
        }
    }
}
