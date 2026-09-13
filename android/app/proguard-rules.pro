# FET Lab — R8 rules
#
# The app has no reflection-based serialisation: devices.json is parsed field by
# field through org.json, so nothing needs keeping by name. Compose, AndroidX and
# kotlinx-coroutines ship their own consumer rules.

# Keep the GLSurfaceView.Renderer entry points (called from the GL thread).
-keepclassmembers class * implements android.opengl.GLSurfaceView$Renderer {
    public void onSurfaceCreated(...);
    public void onSurfaceChanged(...);
    public void onDrawFrame(...);
}

# Strip verbose logging from release builds.
-assumenosideeffects class android.util.Log {
    public static int v(...);
    public static int d(...);
}

# Readable stack traces from Play Console crash reports.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
