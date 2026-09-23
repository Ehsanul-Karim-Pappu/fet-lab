package io.github.ehsanulkarimpappu.fetlab

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/* ---------------- type ---------------- */

val PlexSans = FontFamily(
    Font(R.font.ibm_plex_sans_regular, FontWeight.Normal),
    Font(R.font.ibm_plex_sans_medium, FontWeight.Medium),
    Font(R.font.ibm_plex_sans_semibold, FontWeight.SemiBold),
    Font(R.font.ibm_plex_sans_bold, FontWeight.Bold)
)

/** Mono carries every number, layer name and unit — same rule as the web viewer. */
val Mono = FontFamily(
    Font(R.font.ibm_plex_mono_regular, FontWeight.Normal),
    Font(R.font.ibm_plex_mono_medium, FontWeight.Medium),
    Font(R.font.ibm_plex_mono_semibold, FontWeight.SemiBold)
)

private val AppTypography = Typography(
    displaySmall = TextStyle(fontFamily = Mono, fontWeight = FontWeight.Medium,
        fontSize = 26.sp, lineHeight = 30.sp, letterSpacing = (-0.4).sp),
    titleLarge = TextStyle(fontFamily = Mono, fontWeight = FontWeight.Medium,
        fontSize = 20.sp, lineHeight = 24.sp, letterSpacing = (-0.2).sp),
    titleMedium = TextStyle(fontFamily = PlexSans, fontWeight = FontWeight.SemiBold,
        fontSize = 15.sp, lineHeight = 20.sp),
    bodyLarge = TextStyle(fontFamily = PlexSans, fontSize = 15.sp, lineHeight = 22.sp),
    bodyMedium = TextStyle(fontFamily = PlexSans, fontSize = 14.sp, lineHeight = 20.sp),
    bodySmall = TextStyle(fontFamily = PlexSans, fontSize = 12.5f.sp, lineHeight = 17.sp),
    labelLarge = TextStyle(fontFamily = PlexSans, fontWeight = FontWeight.Medium, fontSize = 13.sp),
    labelMedium = TextStyle(fontFamily = Mono, fontWeight = FontWeight.Medium,
        fontSize = 11.5f.sp, letterSpacing = 0.4f.sp),
    labelSmall = TextStyle(fontFamily = Mono, fontWeight = FontWeight.Medium,
        fontSize = 10.5f.sp, letterSpacing = 1.4f.sp)
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp),
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(14.dp),
    large = RoundedCornerShape(20.dp),
    extraLarge = RoundedCornerShape(28.dp)
)

/* ---------------- colour ---------------- */

private val Teal = Color(0xFF0E7C8C)
private val TealBright = Color(0xFF4FC7D8)

private val LightColors = lightColorScheme(
    primary = Teal, onPrimary = Color.White,
    primaryContainer = Color(0xFFD1EBF0), onPrimaryContainer = Color(0xFF063E48),
    secondary = Color(0xFF4B5462), onSecondary = Color.White,
    secondaryContainer = Color(0xFFE3E7EE), onSecondaryContainer = Color(0xFF2A313C),
    background = Color(0xFFE9ECF1), onBackground = Color(0xFF141821),
    surface = Color(0xFFFFFFFF), onSurface = Color(0xFF141821),
    surfaceVariant = Color(0xFFEDF0F5), onSurfaceVariant = Color(0xFF525C6A),
    outline = Color(0xFFC6CCD6), outlineVariant = Color(0xFFDDE2E9)
)

private val DarkColors = darkColorScheme(
    primary = TealBright, onPrimary = Color(0xFF04333C),
    primaryContainer = Color(0xFF15333B), onPrimaryContainer = Color(0xFF9BE6F1),
    secondary = Color(0xFFA3ACBA), onSecondary = Color(0xFF1B222B),
    secondaryContainer = Color(0xFF232A34), onSecondaryContainer = Color(0xFFC6CEDA),
    background = Color(0xFF0E1116), onBackground = Color(0xFFE7EBF1),
    surface = Color(0xFF161A21), onSurface = Color(0xFFE7EBF1),
    surfaceVariant = Color(0xFF1D222B), onSurfaceVariant = Color(0xFF9BA5B3),
    outline = Color(0xFF2E3641), outlineVariant = Color(0xFF232A33)
)

/** The 3D stage keeps its own palette — it is a viewport, not a surface. */
object Stage {
    val dark = Color(0xFF0D1015)
    val light = Color(0xFFDADBDD)
    val inkOnDark = Color(0xFFC7CEDA)
    val inkOnLight = Color(0xFF2A323E)
    val dimOnDark = Color(0xFF7D8798)
    val dimOnLight = Color(0xFF5E6875)
    val lineOnDark = Color(0xFF2C3441)
    val lineOnLight = Color(0xFFB7BEC8)
    val high = Color(0xFFFFC073)
    val low = Color(0xFF6FD8E6)
}

@Composable
fun FetLabTheme(content: @Composable () -> Unit) {
    // Light or dark follows the system setting; the app keeps its own palette.
    val scheme = if (isSystemInDarkTheme()) DarkColors else LightColors
    MaterialTheme(colorScheme = scheme, typography = AppTypography, shapes = AppShapes, content = content)
}
