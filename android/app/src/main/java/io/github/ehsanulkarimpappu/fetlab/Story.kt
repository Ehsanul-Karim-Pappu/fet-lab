package io.github.ehsanulkarimpappu.fetlab

import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight

/**
 * The written background arrives as a small subset of HTML — h4, p, ul/li, and inline
 * b and i. Rather than pull in a WebView or HtmlCompat for five tags, it is split into
 * blocks here and rendered with ordinary Compose text.
 */
class Block(val kind: String, val text: AnnotatedString)

private val ENTITIES = listOf(
    "&nbsp;" to " ", "&amp;" to "&", "&lt;" to "<", "&gt;" to ">",
    "&mdash;" to "—", "&times;" to "×", "&quot;" to "\"")

private fun decode(s: String): String {
    var out = s
    for ((from, to) in ENTITIES) out = out.replace(from, to)
    return out
}

/** Inline b/i into spans; anything else is dropped rather than shown as a tag. */
private fun inline(raw: String): AnnotatedString = buildAnnotatedString {
    var i = 0
    var bold = 0
    var ital = 0
    while (i < raw.length) {
        val lt = raw.indexOf('<', i)
        if (lt < 0) { appendStyled(raw.substring(i), bold, ital); break }
        if (lt > i) appendStyled(raw.substring(i, lt), bold, ital)
        val gt = raw.indexOf('>', lt)
        if (gt < 0) break
        when (raw.substring(lt + 1, gt).trim().lowercase()) {
            "b", "strong" -> bold++
            "/b", "/strong" -> if (bold > 0) bold--
            "i", "em" -> ital++
            "/i", "/em" -> if (ital > 0) ital--
        }
        i = gt + 1
    }
}

private fun androidx.compose.ui.text.AnnotatedString.Builder.appendStyled(
    s: String, bold: Int, ital: Int
) {
    val text = decode(s).replace(Regex("\\s+"), " ")
    if (text.isEmpty()) return
    if (bold > 0 || ital > 0) {
        pushStyle(SpanStyle(
            fontWeight = if (bold > 0) FontWeight.SemiBold else null,
            fontStyle = if (ital > 0) FontStyle.Italic else null))
        append(text); pop()
    } else append(text)
}

/** Split the story into headings, paragraphs and bullets, in order. */
fun storyBlocks(html: String): List<Block> {
    if (html.isBlank()) return emptyList()
    val out = ArrayList<Block>()
    val re = Regex("<(h4|p|li)>(.*?)</\\1>", RegexOption.DOT_MATCHES_ALL)
    for (m in re.findAll(html)) {
        val kind = m.groupValues[1]
        val body = inline(m.groupValues[2])
        if (body.text.isNotBlank()) out.add(Block(kind, body))
    }
    return out
}
