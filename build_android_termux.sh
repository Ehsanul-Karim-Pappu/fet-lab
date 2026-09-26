#!/data/data/com.termux/files/usr/bin/bash

# Build FET Lab's debug APK natively in Termux.
#
# Usage:
#   bash build_android_termux.sh [options] [output.apk]
#
# Options:
#   --install    open Android's installer on the APK when the build finishes
#   --clean      discard the saved build copy and build everything again
#   -h, --help   show this help
#   -- ARGS      pass the remaining arguments to Gradle, e.g. -- --offline
#
# The APK is named after what it was built from and goes next to this script
# unless an output path is given:
#   fet-lab-<branch>-<commit date>-<commit>[-modified]-debug.apk
#   e.g. fet-lab-finfet-process-20260926-6595236-debug.apk
# "-modified" means android/ had uncommitted changes, so the APK is not exactly
# that commit. The app shows the same commit under its version in About.
# The project is built in ~/.cache/fet-lab-build,
# because Gradle is slow and unreliable on shared storage; that copy is kept,
# so the next build only redoes what changed.
#
# Environment: GRADLE_WORKERS (default 1), WAKE_LOCK=0 to skip the wake lock.

set -Eeuo pipefail

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

step() {
    printf '\n==> %s\n' "$*"
}

usage() {
    awk 'NR > 2 && /^#/ { sub(/^# ?/, ""); print; next } NR > 2 { exit }' "${BASH_SOURCE[0]}"
}

INSTALL=0
CLEAN=0
OUTPUT_ARG=""
GRADLE_EXTRA=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --install) INSTALL=1 ;;
        --clean) CLEAN=1 ;;
        -h|--help) usage; exit 0 ;;
        --) shift; GRADLE_EXTRA=("$@"); break ;;
        -*) die "Unknown option: $1 (see --help)" ;;
        *)
            [[ -z "$OUTPUT_ARG" ]] || die "Only one output path can be given (see --help)"
            OUTPUT_ARG="$1"
            ;;
    esac
    shift
done

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
CALL_DIR="$PWD"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
TERMUX_HOME="${HOME:-/data/data/com.termux/files/home}"
JAVA_HOME="$PREFIX/lib/jvm/java-17-openjdk"
ANDROID_HOME="${ANDROID_HOME:-$TERMUX_HOME/android-sdk}"
ANDROID_SDK_ROOT="$ANDROID_HOME"
GRADLE_USER_HOME="${GRADLE_USER_HOME:-$TERMUX_HOME/.gradle}"
AAPT2="$PREFIX/bin/aapt2"
BUILD_ROOT="$TERMUX_HOME/.cache/fet-lab-build"
WORK_DIR="$BUILD_ROOT/android"
LOCK_DIR="$BUILD_ROOT.lock"
GRADLE_WORKERS="${GRADLE_WORKERS:-1}"
export JAVA_HOME ANDROID_HOME ANDROID_SDK_ROOT GRADLE_USER_HOME
export PATH="$JAVA_HOME/bin:$PREFIX/bin:$PATH"

[[ "$GRADLE_WORKERS" =~ ^[1-9][0-9]*$ ]] || die "GRADLE_WORKERS must be a positive number"
[[ -d "$REPO_DIR/android" ]] || die "Android project not found at $REPO_DIR/android"
[[ -f "$REPO_DIR/android/gradlew" ]] || die "Gradle wrapper is missing: android/gradlew"
[[ -f "$REPO_DIR/android/gradle/wrapper/gradle-wrapper.jar" ]] || \
    die "Gradle wrapper JAR is missing: android/gradle/wrapper/gradle-wrapper.jar"

# Name the APK after the commit it is built from.
BRANCH="$(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
[[ "$BRANCH" != "HEAD" ]] || BRANCH=""
COMMIT_ID="$(git -C "$REPO_DIR" log -1 --format='%h' 2>/dev/null || true)"
COMMIT_DATE="$(git -C "$REPO_DIR" log -1 --format='%cd' --date=format:'%Y%m%d' 2>/dev/null || true)"
COMMIT_DAY="$(git -C "$REPO_DIR" log -1 --format='%cs' 2>/dev/null || true)"
COMMIT_TITLE="$(git -C "$REPO_DIR" log -1 --format='%s' 2>/dev/null || true)"
MODIFIED=""
if [[ -n "$COMMIT_ID" && -n "$(git -C "$REPO_DIR" status --porcelain -- android 2>/dev/null || true)" ]]; then
    MODIFIED="modified"
fi
name="fet-lab"
for part in "${BRANCH//\//-}" "$COMMIT_DATE" "$COMMIT_ID" "$MODIFIED"; do
    [[ -z "$part" ]] || name="$name-$part"
done
DEFAULT_APK="$REPO_DIR/$name-debug.apk"
OUTPUT_APK="${OUTPUT_ARG:-$DEFAULT_APK}"
if [[ "$OUTPUT_APK" != /* ]]; then
    OUTPUT_APK="$CALL_DIR/$OUTPUT_APK"
fi
[[ "$OUTPUT_APK" == *.apk ]] || die "The output path must end in .apk: $OUTPUT_APK"

# The SDK packages this project needs: compileSdk from the app's build file,
# and the build tools that Android Gradle Plugin 8.7 uses by default.
GRADLE_FILE="$REPO_DIR/android/app/build.gradle.kts"
API_LEVEL="$(sed -n 's/^[[:space:]]*compileSdk[[:space:]]*=[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$GRADLE_FILE")"
API_LEVEL="${API_LEVEL%%$'\n'*}"
[[ -n "$API_LEVEL" ]] || die "Could not read compileSdk from $GRADLE_FILE"
BUILD_TOOLS="$(sed -n 's/^[[:space:]]*buildToolsVersion[[:space:]]*=[[:space:]]*"\([0-9.]*\)".*/\1/p' "$GRADLE_FILE")"
BUILD_TOOLS="${BUILD_TOOLS%%$'\n'*}"
BUILD_TOOLS="${BUILD_TOOLS:-34.0.0}"

missing=()
[[ -x "$JAVA_HOME/bin/javac" ]] || missing+=("JDK 17:  pkg install openjdk-17")
[[ -x "$AAPT2" ]] || missing+=("AAPT2:   pkg install aapt2")
sdk_packages=()
[[ -f "$ANDROID_HOME/platforms/android-$API_LEVEL/android.jar" ]] || \
    sdk_packages+=("\"platforms;android-$API_LEVEL\"")
[[ -f "$ANDROID_HOME/build-tools/$BUILD_TOOLS/source.properties" ]] || \
    sdk_packages+=("\"build-tools;$BUILD_TOOLS\"")
if [[ ${#sdk_packages[@]} -gt 0 ]]; then
    missing+=("Android SDK in $ANDROID_HOME:  sdkmanager --sdk_root=\"$ANDROID_HOME\" ${sdk_packages[*]}")
fi
if [[ ${#missing[@]} -gt 0 ]]; then
    printf 'Error: missing build requirements. Install them with:\n' >&2
    printf '  %s\n' "${missing[@]}" >&2
    exit 1
fi

# One build at a time: two Gradle runs in the same copy corrupt each other.
mkdir -p "$TERMUX_HOME/.cache" "$GRADLE_USER_HOME" "$(dirname -- "$OUTPUT_APK")"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    other="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    if [[ -n "$other" ]] && kill -0 "$other" 2>/dev/null; then
        die "Another build is running (process $other). Wait for it to finish."
    fi
    rm -rf -- "$LOCK_DIR"
    mkdir "$LOCK_DIR" || die "Could not create the lock $LOCK_DIR"
fi
printf '%s\n' "$$" > "$LOCK_DIR/pid"

WAKE_LOCKED=0
cleanup() {
    cd "$TERMUX_HOME" 2>/dev/null || true
    if [[ "$WAKE_LOCKED" == "1" ]]; then
        termux-wake-unlock >/dev/null 2>&1 || true
    fi
    rm -rf -- "$LOCK_DIR"
}
trap cleanup EXIT

# Keep the phone from sleeping mid-build. Needs the Termux app, not termux-api.
if [[ "${WAKE_LOCK:-1}" != "0" ]] && command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock >/dev/null 2>&1 && WAKE_LOCKED=1 || true
fi

if [[ -n "$COMMIT_ID" ]]; then
    printf 'Building %s: %s %s\n' "${BRANCH:-detached HEAD}" "$COMMIT_ID" "$COMMIT_TITLE"
    if [[ -n "$MODIFIED" ]]; then
        printf 'Note: android/ has uncommitted changes; they are included, so the name ends in -modified.\n'
    fi
else
    printf 'Note: git could not read %s, so the APK name has no commit.\n' "$REPO_DIR"
    printf 'If git reports "dubious ownership": git config --global --add safe.directory %s\n' "$REPO_DIR"
fi

if [[ "$CLEAN" == "1" ]]; then
    step "Removing the saved build copy"
    rm -rf -- "$BUILD_ROOT"
fi

step "Copying the Android project to private Termux storage"
mkdir -p "$WORK_DIR"
if command -v rsync >/dev/null 2>&1; then
    # Mirror the sources exactly (deleted files go too) but keep the build
    # outputs, so Gradle and Kotlin can build incrementally.
    rsync -rlt --delete \
        --exclude=/.gradle/ --exclude=/.kotlin/ --exclude=/build/ --exclude=/app/build/ \
        --exclude=/local.properties \
        "$REPO_DIR/android/" "$WORK_DIR/"
else
    printf 'rsync not found, so everything is rebuilt. For faster builds: pkg install rsync\n'
    rm -rf -- "$WORK_DIR"
    cp -a "$REPO_DIR/android" "$BUILD_ROOT/"
    rm -rf -- "$WORK_DIR/.gradle" "$WORK_DIR/.kotlin" "$WORK_DIR/build" "$WORK_DIR/app/build" \
        "$WORK_DIR/local.properties"
fi

BUILT_APK="$WORK_DIR/app/build/outputs/apk/debug/app-debug.apk"
rm -f -- "$BUILT_APK"

step "Building the debug APK with Gradle"
cd "$WORK_DIR"
status=0
bash ./gradlew \
    --no-daemon \
    --max-workers="$GRADLE_WORKERS" \
    --console=plain \
    -Pandroid.aapt2FromMavenOverride="$AAPT2" \
    -Pfetlab.commit="$COMMIT_ID" \
    -Pfetlab.commitDate="$COMMIT_DAY" \
    -Pfetlab.branch="$BRANCH" \
    -Pfetlab.modified="$([[ -n "$MODIFIED" ]] && echo true || echo false)" \
    "${GRADLE_EXTRA[@]}" \
    :app:assembleDebug || status=$?

if [[ "$status" -ne 0 ]]; then
    printf '\nBuild failed (exit %s).\n' "$status" >&2
    if [[ "$status" -eq 137 || "$status" -eq 9 ]]; then
        printf '%s\n' \
            'Android stopped the build: it ran out of memory, or hit the Android 12+' \
            'limit on background processes. Close other apps, keep Termux open, and' \
            'try again. On Android 14+, Developer options > "Disable child process' \
            'restrictions" removes the limit.' >&2
    else
        printf '%s\n' \
            'Look for the first line starting with "e:" or "* What went wrong" above.' \
            'If a download failed, run the script again once the network is back.' \
            'If the saved build copy looks broken, run it again with --clean.' >&2
    fi
    exit "$status"
fi

[[ -f "$BUILT_APK" ]] || die "Gradle completed without producing $BUILT_APK"
cp -- "$BUILT_APK" "$OUTPUT_APK"

step "Checking the APK"
BADGING="$("$AAPT2" dump badging "$OUTPUT_APK" 2>/dev/null | sed -n 's/^package: //p' || true)"
[[ -n "$BADGING" ]] || die "The APK could not be read back: $OUTPUT_APK"
printf 'Package: %s\n' "$BADGING"
if [[ -x "$PREFIX/bin/apksigner" ]]; then
    "$PREFIX/bin/apksigner" verify "$OUTPUT_APK" || die "APK signature verification failed"
    printf 'APK signature verified.\n'
else
    printf 'Signature not checked (for that: pkg install apksigner).\n'
fi

printf '\nAPK: %s\n' "$OUTPUT_APK"
printf 'SHA-256: '
sha256sum "$OUTPUT_APK" | awk '{print $1}'
printf 'Built in %dm %02ds.\n' "$((SECONDS / 60))" "$((SECONDS % 60))"

if [[ "$INSTALL" == "1" ]]; then
    SHOWN_APK="${OUTPUT_APK#/storage/emulated/0/}"
    if command -v termux-open >/dev/null 2>&1; then
        printf '\nOpening the installer.\n'
        printf '%s\n' \
            '- If Android asks, allow "Install unknown apps" for Termux, then run this again.' \
            '- "Conflicts with an existing package": uninstall the old FET Lab (debug) first.' \
            '- "Problem while parsing the package": install it from the Files app instead:' \
            "  $SHOWN_APK"
        # Hand the installer the private copy: Termux can always share files in
        # its own storage, and the type is given so no guessing is involved.
        termux-open --content-type application/vnd.android.package-archive "$BUILT_APK"
    else
        printf 'termux-open not found; install the APK from the Files app: %s\n' "$SHOWN_APK"
    fi
fi
