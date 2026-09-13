package io.github.ehsanulkarimpappu.fetlab

/**
 * Everything that identifies this build in one place.
 *
 * [ISSUES], [RELEASES] and [PRIVACY] are all derived from [REPO], so a repository
 * rename only needs changing here.
 */
object AppInfo {
    const val NAME = "FET Lab"
    const val TAGLINE = "Logic device architectures in 3D"

    const val DEVELOPER = "Khandaker Ehsanul Karim"
    const val EMAIL = "ehsan.pappu.99@gmail.com"

    /** Public repository — issues, releases and the privacy notice all hang off this. */
    const val REPO = "https://github.com/ehsanul-karim-pappu/fet-lab"
    const val PROFILE = "https://github.com/ehsanul-karim-pappu"
    const val ISSUES = "$REPO/issues"
    const val RELEASES = "$REPO/releases"
    const val SLUG = "ehsanul-karim-pappu/fet-lab"

    const val LICENSE = "MIT License"
    const val PRIVACY = "$REPO/blob/main/PRIVACY.md"

    val ATTRIBUTIONS = listOf(
        "Nanosheet geometry after S. Rathore et al., Semiconductor Science and Technology (2021)",
        "FinFET, forksheet and CFET after imec's published device structures",
        "IBM Plex Sans and IBM Plex Mono — SIL Open Font License 1.1",
        "Models are representative teaching geometry, not any foundry's process data"
    )
}
