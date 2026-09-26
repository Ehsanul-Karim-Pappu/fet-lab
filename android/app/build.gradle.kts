import java.io.FileInputStream
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Release signing is read from keystore.properties in the project root.
// That file is git-ignored — see PLAY_STORE.md for how to create it.
val keystorePropsFile = rootProject.file("keystore.properties")
val keystoreProps = Properties().apply {
    if (keystorePropsFile.exists()) FileInputStream(keystorePropsFile).use { load(it) }
}
val hasSigning = keystorePropsFile.exists()

// Which commit this APK was built from, shown under the version in About.
// build_android_termux.sh passes it in (-Pfetlab.commit=... and so on), because it
// builds in a copy without .git; any other build reads it from git.
fun git(vararg args: String): String = runCatching {
    providers.exec {
        commandLine("git", "-C", rootProject.projectDir.path, *args)
        isIgnoreExitValue = true
    }.standardOutput.asText.get().trim()
}.getOrDefault("")
fun buildInfo(name: String, fromGit: () -> String): String =
    ((findProperty("fetlab.$name") as String?) ?: fromGit())
        .filter { it.isLetterOrDigit() || it in "._/-" }
val gitCommit = buildInfo("commit") { git("log", "-1", "--format=%h") }
val gitDate = buildInfo("commitDate") { git("log", "-1", "--format=%cs") }
val gitBranch = buildInfo("branch") {
    git("rev-parse", "--abbrev-ref", "HEAD").takeIf { it != "HEAD" }.orEmpty()
}
val gitModified = buildInfo("modified") {
    if (gitCommit.isNotEmpty() && git("status", "--porcelain", "--", ".").isNotEmpty()) "true" else "false"
} == "true"

android {
    namespace = "io.github.ehsanulkarimpappu.fetlab"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.ehsanulkarimpappu.fetlab"
        minSdk = 26
        targetSdk = 35
        versionCode = 4
        versionName = "1.3.0"
        resourceConfigurations += listOf("en")
        buildConfigField("String", "GIT_COMMIT", "\"$gitCommit\"")
        buildConfigField("String", "GIT_DATE", "\"$gitDate\"")
        buildConfigField("String", "GIT_BRANCH", "\"$gitBranch\"")
        buildConfigField("boolean", "GIT_MODIFIED", "$gitModified")
    }

    signingConfigs {
        if (hasSigning) {
            create("release") {
                storeFile = rootProject.file(keystoreProps.getProperty("storeFile"))
                storePassword = keystoreProps.getProperty("storePassword")
                keyAlias = keystoreProps.getProperty("keyAlias")
                keyPassword = keystoreProps.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            if (hasSigning) signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging {
        resources.excludes += setOf("/META-INF/{AL2.0,LGPL2.1}", "/META-INF/DEPENDENCIES")
    }
    androidResources {
        // devices.json and the fonts are already compact; do not let AAPT re-compress them badly
        noCompress += listOf("json")
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.10.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
