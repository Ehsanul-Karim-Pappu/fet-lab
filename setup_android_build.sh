#!/usr/bin/env bash
# Install the minimum Linux toolchain needed to build and check an Android app.
#
# Usage:
#   bash setup_android_build.sh [project-directory]
#
# Optional overrides when automatic version detection is not possible:
#   ANDROID_API_LEVEL=35 BUILD_TOOLS_VERSION=35.0.0 \
#     bash setup_android_build.sh /path/to/project

set -Eeuo pipefail

PROJECT_DIR="${1:-$PWD}"
ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
CMDLINE_TOOLS_VERSION="${ANDROID_CMDLINE_TOOLS_VERSION:-15859902}"
CMDLINE_TOOLS_URL="https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_TOOLS_VERSION}_latest.zip"

log() {
    printf '\n\033[1;34m==> %s\033[0m\n' "$*"
}

warn() {
    printf '\n\033[1;33mWARNING: %s\033[0m\n' "$*" >&2
}

die() {
    printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2
    exit 1
}

on_error() {
    local status=$?
    printf '\n\033[1;31mSetup/build stopped at line %s (exit %s).\033[0m\n' "${BASH_LINENO[0]}" "$status" >&2
    exit "$status"
}
trap on_error ERR

[[ -d "$PROJECT_DIR" ]] || die "Project directory does not exist: $PROJECT_DIR"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

if [[ "$(uname -s)" != "Linux" ]]; then
    die "This script is for Linux. Detected: $(uname -s)"
fi

case "$(uname -m)" in
    x86_64|amd64) ;;
    *) warn "Google's Linux command-line package is primarily intended for x86_64. Detected $(uname -m)." ;;
esac

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    SUDO=()
elif command -v sudo >/dev/null 2>&1; then
    SUDO=(sudo)
else
    die "Root access is needed to install Java and utilities, but sudo is unavailable."
fi

log "Installing Java 17 and required utilities"
if command -v apt-get >/dev/null 2>&1; then
    "${SUDO[@]}" apt-get update
    "${SUDO[@]}" apt-get install -y openjdk-17-jdk curl unzip ca-certificates
elif command -v dnf >/dev/null 2>&1; then
    "${SUDO[@]}" dnf install -y java-17-openjdk-devel curl unzip ca-certificates
elif command -v yum >/dev/null 2>&1; then
    "${SUDO[@]}" yum install -y java-17-openjdk-devel curl unzip ca-certificates
else
    die "Supported package manager not found. Install JDK 17, curl, unzip, and CA certificates manually."
fi

command -v java >/dev/null 2>&1 || die "java was not found after installation."
command -v javac >/dev/null 2>&1 || die "javac was not found after installation."

JAVA_HOME="${JAVA_HOME:-$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")}" 
export JAVA_HOME
export ANDROID_HOME
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"

log "Java installation"
java -version
javac -version
printf 'JAVA_HOME=%s\n' "$JAVA_HOME"

SDKMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
if [[ ! -x "$SDKMANAGER" ]]; then
    if [[ -e "$ANDROID_HOME/cmdline-tools/latest" ]]; then
        die "$ANDROID_HOME/cmdline-tools/latest exists but sdkmanager is not executable. Move or repair that directory, then rerun."
    fi

    log "Installing Android command-line tools in $ANDROID_HOME"
    SDK_TMP="$(mktemp -d)"
    cleanup_tmp() {
        if [[ -n "${SDK_TMP:-}" && -d "$SDK_TMP" ]]; then
            rm -rf -- "$SDK_TMP"
        fi
    }
    trap cleanup_tmp EXIT

    curl -fL --retry 3 "$CMDLINE_TOOLS_URL" -o "$SDK_TMP/android-commandline-tools.zip"
    unzip -q "$SDK_TMP/android-commandline-tools.zip" -d "$SDK_TMP/unpacked"
    [[ -x "$SDK_TMP/unpacked/cmdline-tools/bin/sdkmanager" ]] || \
        die "The downloaded archive did not contain cmdline-tools/bin/sdkmanager."

    mkdir -p "$ANDROID_HOME/cmdline-tools"
    mv "$SDK_TMP/unpacked/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
fi

persist_android_environment() {
    local rc_file="$1"
    local marker="# Android SDK environment for local builds"

    touch "$rc_file"
    if ! grep -Fq "$marker" "$rc_file"; then
        {
            printf '\n%s\n' "$marker"
            printf 'export ANDROID_HOME=%q\n' "$ANDROID_HOME"
            printf 'export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools"\n'
        } >> "$rc_file"
    fi
}

persist_android_environment "$HOME/.profile"
case "${SHELL:-}" in
    */bash) persist_android_environment "$HOME/.bashrc" ;;
    */zsh)  persist_android_environment "$HOME/.zshrc" ;;
esac

log "Finding the Android versions required by the project"
mapfile -d '' PROJECT_CONFIG_FILES < <(
    find "$PROJECT_DIR" \
        \( -path '*/.git' -o -path '*/node_modules' -o -path '*/build' -o -path '*/.gradle' \) -prune -o \
        \( -name '*.gradle' -o -name '*.gradle.kts' -o -name 'libs.versions.toml' \) \
        -type f -print0
)

[[ ${#PROJECT_CONFIG_FILES[@]} -gt 0 ]] || \
    die "No Gradle configuration files were found below $PROJECT_DIR"

API_LEVEL="${ANDROID_API_LEVEL:-}"
if [[ -z "$API_LEVEL" ]]; then
    API_LEVEL="$(
        grep -hEo "compileSdk(Version)?[[:space:]]*(=|[[:space:]])[[:space:]]*[\"']?[0-9]+" \
            "${PROJECT_CONFIG_FILES[@]}" 2>/dev/null \
        | grep -Eo '[0-9]+' \
        | head -n 1 || true
    )"
fi

if [[ -z "$API_LEVEL" ]]; then
    API_LEVEL="$(
        grep -hE '^[[:space:]]*compileSdk[[:space:]]*=' "${PROJECT_CONFIG_FILES[@]}" 2>/dev/null \
        | grep -Eo '[0-9]+' \
        | head -n 1 || true
    )"
fi

[[ "$API_LEVEL" =~ ^[0-9]+$ ]] || die \
    "Could not detect compileSdk. Rerun with an override, for example: ANDROID_API_LEVEL=35 bash $0 '$PROJECT_DIR'"

BUILD_TOOLS="${BUILD_TOOLS_VERSION:-}"
if [[ -z "$BUILD_TOOLS" ]]; then
    BUILD_TOOLS="$(
        grep -hEo "buildToolsVersion[[:space:]]*(=|[[:space:]])[[:space:]]*[\"'][0-9]+\.[0-9]+\.[0-9]+" \
            "${PROJECT_CONFIG_FILES[@]}" 2>/dev/null \
        | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' \
        | head -n 1 || true
    )"
fi
BUILD_TOOLS="${BUILD_TOOLS:-${API_LEVEL}.0.0}"

NDK_VERSION_FOUND="${ANDROID_NDK_VERSION:-}"
if [[ -z "$NDK_VERSION_FOUND" ]]; then
    NDK_VERSION_FOUND="$(
        grep -hEo "ndkVersion[[:space:]]*(=|[[:space:]])[[:space:]]*[\"'][0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z]+)*" \
            "${PROJECT_CONFIG_FILES[@]}" 2>/dev/null \
        | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z]+)*' \
        | head -n 1 || true
    )"
fi

printf 'compileSdk/API level: %s\n' "$API_LEVEL"
printf 'Build Tools:          %s\n' "$BUILD_TOOLS"
if [[ -n "$NDK_VERSION_FOUND" ]]; then
    printf 'NDK:                  %s\n' "$NDK_VERSION_FOUND"
else
    printf 'NDK:                  not requested by the project\n'
fi

if [[ -t 0 ]]; then
    printf '\nAndroid SDK packages require accepting Google Android SDK licenses.\n'
    read -r -p "Continue and accept the required licenses? [y/N] " ACCEPT_LICENSES
    case "$ACCEPT_LICENSES" in
        y|Y|yes|YES) ;;
        *) die "License acceptance was not confirmed." ;;
    esac
else
    die "License confirmation requires an interactive terminal. Run this script directly in your terminal."
fi

log "Accepting Android SDK licenses"
set +o pipefail
yes | "$SDKMANAGER" --sdk_root="$ANDROID_HOME" --licenses >/dev/null
set -o pipefail

SDK_PACKAGES=(
    "platform-tools"
    "platforms;android-${API_LEVEL}"
    "build-tools;${BUILD_TOOLS}"
)
if [[ -n "$NDK_VERSION_FOUND" ]]; then
    SDK_PACKAGES+=("ndk;${NDK_VERSION_FOUND}")
fi

log "Installing Android SDK packages"
set +o pipefail
yes | "$SDKMANAGER" --sdk_root="$ANDROID_HOME" "${SDK_PACKAGES[@]}"
set -o pipefail

GRADLEW="$(
    find "$PROJECT_DIR" \
        \( -path '*/node_modules' -o -path '*/.git' \) -prune -o \
        -type f -name gradlew -print \
        | head -n 1
)"

[[ -n "$GRADLEW" ]] || die \
    "No Gradle Wrapper (gradlew) was found. Restore it from the repository; do not install an arbitrary Gradle version."

GRADLE_DIR="$(dirname "$GRADLEW")"
log "Using Gradle Wrapper at $GRADLEW"
cd "$GRADLE_DIR"
bash "$GRADLEW" --version

log "Building the debug APK"
bash "$GRADLEW" assembleDebug --stacktrace

log "Running Android lint"
bash "$GRADLEW" lint --stacktrace

log "Running JVM unit tests"
bash "$GRADLEW" test --stacktrace

log "Generated APK files"
mapfile -t APK_FILES < <(find "$GRADLE_DIR" -type f -path '*/build/outputs/apk/*.apk' -print)
if [[ ${#APK_FILES[@]} -eq 0 ]]; then
    warn "The build completed, but no APK was found under a build/outputs/apk directory."
else
    printf '%s\n' "${APK_FILES[@]}"
fi

printf '\n\033[1;32mAndroid setup and build checks completed successfully.\033[0m\n'
printf 'Restart Codex CLI so it inherits ANDROID_HOME and the updated PATH.\n'
printf 'Chrome visual-test rendering is separate and is not fixed by this Android setup.\n'
