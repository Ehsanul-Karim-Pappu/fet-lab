package io.github.ehsanulkarimpappu.fetlab

import android.opengl.GLES20 as G
import android.opengl.GLSurfaceView
import android.opengl.Matrix
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import java.nio.ShortBuffer
import javax.microedition.khronos.egl.EGLConfig
import javax.microedition.khronos.opengles.GL10
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin

private const val VS = """
attribute vec3 aPos; attribute vec3 aNrm; attribute vec3 aCol; attribute vec3 aExp;
uniform mat4 uVP; uniform float uE;
varying vec3 vN, vC, vW;
void main() { vec3 p = aPos + aExp * uE; vW = p; vN = aNrm; vC = aCol;
  gl_Position = uVP * vec4(p, 1.0); }
"""

private const val FS = """
precision highp float;
varying vec3 vN, vC, vW;
uniform vec3 uHi, uAdd, uTex; uniform float uA, uTint, uClip, uFlat;
float h31(vec3 p){ return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }
float vn(vec3 p){ vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  float a = mix(h31(i), h31(i + vec3(1.,0.,0.)), f.x);
  float b = mix(h31(i + vec3(0.,1.,0.)), h31(i + vec3(1.,1.,0.)), f.x);
  float c = mix(h31(i + vec3(0.,0.,1.)), h31(i + vec3(1.,0.,1.)), f.x);
  float e = mix(h31(i + vec3(0.,1.,1.)), h31(i + vec3(1.,1.,1.)), f.x);
  return mix(mix(a, b, f.y), mix(c, e, f.y), f.z); }
void main() {
  if (uClip > 0.5) { if (vW.x > uHi.x + 0.001 || vW.y > uHi.y + 0.001 || vW.z > uHi.z + 0.001) discard; }
  vec3 n = normalize(vN); if (!gl_FrontFacing) n = -n;
  vec3 L1 = normalize(vec3(0.55, 0.78, 0.62)), L2 = normalize(vec3(-0.62, 0.22, -0.45));
  float d = max(dot(n, L1), 0.0) * 0.82 + max(dot(n, L2), 0.0) * 0.26 + 0.34;
  float df = max(dot(n, L1), 0.0) * 0.24 + max(dot(n, L2), 0.0) * 0.10 + 0.74;
  d = mix(d, df, uFlat);
  float rim = pow(1.0 - abs(n.z), 2.0) * 0.05 * (1.0 - uFlat);
  float g = 1.0;
  if (uTex.x > 0.0) {
    float nz = vn(vW * uTex.y);
    g = 1.0 + (nz - 0.5) * uTex.x;
    if (uTex.z > 0.5) g *= 1.0 + 0.055 * sin(vW.x * 0.55 + vW.z * 0.18 + nz * 2.2);
  }
  gl_FragColor = vec4(pow(clamp(vC * (d + rim) * uTint * g + uAdd, 0.0, 1.5), vec3(0.95)), uA);
}
"""

/** Cube faces as (normal, 4 corner signs) — same winding as the web build. */
private val FACES = arrayOf(
    floatArrayOf(0f, 0f, 1f, -1f, -1f, 1f, 1f, -1f, 1f, 1f, 1f, 1f, -1f, 1f, 1f),
    floatArrayOf(0f, 0f, -1f, 1f, -1f, -1f, -1f, -1f, -1f, -1f, 1f, -1f, 1f, 1f, -1f),
    floatArrayOf(1f, 0f, 0f, 1f, -1f, 1f, 1f, -1f, -1f, 1f, 1f, -1f, 1f, 1f, 1f),
    floatArrayOf(-1f, 0f, 0f, -1f, -1f, -1f, -1f, -1f, 1f, -1f, 1f, 1f, -1f, 1f, -1f),
    floatArrayOf(0f, 1f, 0f, -1f, 1f, 1f, 1f, 1f, 1f, 1f, 1f, -1f, -1f, 1f, -1f),
    floatArrayOf(0f, -1f, 0f, -1f, -1f, -1f, 1f, -1f, -1f, 1f, -1f, 1f, -1f, -1f, 1f)
)

class Renderer(private val lib: Library) : GLSurfaceView.Renderer {

    // ---- state written from the UI thread -------------------------------
    @Volatile var scene: Scene = lib.scenes[0]
    @Volatile var az = -0.8f
    @Volatile var el = 0.34f
    @Volatile var dist = 300f
    @Volatile var target = floatArrayOf(0f, 40f, 0f)
    @Volatile var clip = floatArrayOf(1e9f, 1e9f, 1e9f)
    @Volatile var explode = 0f
    @Volatile var ghost = false
    @Volatile var input = 0
    @Volatile var highlight: Part? = null
    @Volatile var capsDirty = true
    @Volatile var texture = true
    @Volatile var edges = true
    @Volatile var lightBg = false
    /** Latest view-projection matrix, for projecting callouts in the Compose overlay. */
    @Volatile var vpSnapshot = FloatArray(16)
    @Volatile var viewW = 1; @Volatile var viewH = 1

    private var prog = 0
    private var aPos = 0; private var aNrm = 0; private var aCol = 0; private var aExp = 0
    private var uVP = 0; private var uE = 0; private var uHi = 0; private var uA = 0
    private var uTint = 0; private var uClip = 0; private var uAdd = 0
    private var uFlat = 0; private var uTex = 0
    private val vbo = IntArray(5)      // pos, nrm, col, exp, index
    private val lbo = IntArray(2)      // edge outlines: pos, exp
    private val cbo = IntArray(4)      // cap pos, nrm, col, exp
    private val clbo = IntArray(2)     // outlines around the cut faces: pos, exp
    private var capVerts = 0
    private var capLineVerts = 0
    private var ready = false

    private val proj = FloatArray(16)
    private val view = FloatArray(16)
    private val vp = FloatArray(16)
    private val eye = FloatArray(3)

    // ---- CPU geometry ----------------------------------------------------
    private lateinit var posB: FloatBuffer
    private lateinit var nrmB: FloatBuffer
    private lateinit var colB: FloatBuffer
    private lateinit var expB: FloatBuffer
    private lateinit var idxB: ShortBuffer
    private lateinit var lposB: FloatBuffer
    private lateinit var lexpB: FloatBuffer
    private val capLinePos = alloc(60000)
    private val capLineExp = alloc(60000)
    private val capPos = alloc(60000)
    private val capNrm = alloc(60000)
    private val capCol = alloc(60000)
    private val capExp = alloc(60000)

    init { buildGeometry() }

    private fun buildGeometry() {
        var boxCount = 0
        for (s in lib.scenes) for (p in s.parts) boxCount += p.boxes.size
        val verts = boxCount * 24
        posB = alloc(verts * 3); nrmB = alloc(verts * 3); colB = alloc(verts * 3); expB = alloc(verts * 3)
        lposB = alloc(boxCount * 24 * 3); lexpB = alloc(boxCount * 24 * 3)
        var lv = 0
        val edgePairs = arrayOf(0 to 1, 2 to 3, 4 to 5, 6 to 7, 0 to 2, 1 to 3,
                                4 to 6, 5 to 7, 0 to 4, 1 to 5, 2 to 6, 3 to 7)
        val ib = ByteBuffer.allocateDirect(boxCount * 36 * 2).order(ByteOrder.nativeOrder()).asShortBuffer()
        var v = 0; var idx = 0
        for (s in lib.scenes) {
            val c = s.centre
            for (p in s.parts) {
                p.start = idx; p.lineStart = lv
                val col = lib.materials[p.material]?.color ?: floatArrayOf(1f, 0f, 1f)
                for (b in p.boxes) {
                    val cx = b[0]; val cy = b[1]; val cz = b[2]
                    val hx = b[3] / 2f; val hy = b[4] / 2f; val hz = b[5] / 2f
                    val ev = when {
                        p.radial != null -> {
                            val dy = cy - p.radial[0]; val dz = cz - p.radial[2]
                            val l = hypot(dy.toDouble(), dz.toDouble()).toFloat().let { if (it < 1e-6f) 1f else it }
                            floatArrayOf(0f, dy / l * p.radial[1], dz / l * p.radial[1])
                        }
                        p.explode != null -> p.explode
                        else -> {
                            val dx = cx - c[0]; val dy = cy - c[1]; val dz = cz - c[2]
                            val l = kotlin.math.sqrt(dx * dx + dy * dy + dz * dz).let { if (it < 1e-6f) 1f else it }
                            floatArrayOf(dx / l * 1.3f, dy / l * 1.3f, dz / l * 1.3f)
                        }
                    }
                    p.aabb.add(Aabb(floatArrayOf(cx - hx, cy - hy, cz - hz),
                        floatArrayOf(cx + hx, cy + hy, cz + hz), ev))
                    val corner = Array(8) { k ->
                        floatArrayOf(cx + (if (k and 1 != 0) hx else -hx),
                                     cy + (if (k and 2 != 0) hy else -hy),
                                     cz + (if (k and 4 != 0) hz else -hz))
                    }
                    for ((ea, eb) in edgePairs) {
                        for (c2 in intArrayOf(ea, eb)) {
                            lposB.put(corner[c2][0]).put(corner[c2][1]).put(corner[c2][2])
                            lexpB.put(ev[0]).put(ev[1]).put(ev[2])
                            lv++
                        }
                    }
                    for (f in FACES) {
                        val base = v
                        for (k in 0 until 4) {
                            val sx = f[3 + k * 3]; val sy = f[4 + k * 3]; val sz = f[5 + k * 3]
                            posB.put(cx + sx * hx).put(cy + sy * hy).put(cz + sz * hz)
                            nrmB.put(f[0]).put(f[1]).put(f[2])
                            colB.put(col[0]).put(col[1]).put(col[2])
                            expB.put(ev[0]).put(ev[1]).put(ev[2])
                            v++
                        }
                        ib.put(base.toShort()).put((base + 1).toShort()).put((base + 2).toShort())
                        ib.put(base.toShort()).put((base + 2).toShort()).put((base + 3).toShort())
                        idx += 6
                    }
                }
                p.count = idx - p.start; p.lineCount = lv - p.lineStart
            }
        }
        posB.position(0); nrmB.position(0); colB.position(0); expB.position(0); ib.position(0)
        lposB.position(0); lexpB.position(0)
        idxB = ib
    }

    // ---- lifecycle -------------------------------------------------------
    override fun onSurfaceCreated(gl: GL10?, config: EGLConfig?) {
        prog = link(VS, FS)
        G.glUseProgram(prog)
        aPos = G.glGetAttribLocation(prog, "aPos"); aNrm = G.glGetAttribLocation(prog, "aNrm")
        aCol = G.glGetAttribLocation(prog, "aCol"); aExp = G.glGetAttribLocation(prog, "aExp")
        uVP = G.glGetUniformLocation(prog, "uVP"); uE = G.glGetUniformLocation(prog, "uE")
        uHi = G.glGetUniformLocation(prog, "uHi"); uA = G.glGetUniformLocation(prog, "uA")
        uTint = G.glGetUniformLocation(prog, "uTint"); uClip = G.glGetUniformLocation(prog, "uClip")
        uAdd = G.glGetUniformLocation(prog, "uAdd")
        uFlat = G.glGetUniformLocation(prog, "uFlat"); uTex = G.glGetUniformLocation(prog, "uTex")
        G.glGenBuffers(5, vbo, 0); G.glGenBuffers(4, cbo, 0); G.glGenBuffers(2, lbo, 0)
        G.glGenBuffers(2, clbo, 0)
        upload(vbo[0], posB); upload(vbo[1], nrmB); upload(vbo[2], colB); upload(vbo[3], expB)
        upload(lbo[0], lposB); upload(lbo[1], lexpB)
        G.glBindBuffer(G.GL_ELEMENT_ARRAY_BUFFER, vbo[4])
        G.glBufferData(G.GL_ELEMENT_ARRAY_BUFFER, idxB.capacity() * 2, idxB, G.GL_STATIC_DRAW)
        G.glEnable(G.GL_DEPTH_TEST); G.glDisable(G.GL_CULL_FACE)
        ready = true; capsDirty = true
    }

    override fun onSurfaceChanged(gl: GL10?, w: Int, h: Int) {
        viewW = w; viewH = h; G.glViewport(0, 0, w, h)
    }

    override fun onDrawFrame(gl: GL10?) {
        if (!ready) return
        if (capsDirty) { rebuildCaps(); capsDirty = false }
        val sc = scene
        val ce = cos(el)
        eye[0] = target[0] + dist * ce * sin(az)
        eye[1] = target[1] + dist * sin(el)
        eye[2] = target[2] + dist * ce * cos(az)
        val aspect = if (viewH == 0) 1f else viewW.toFloat() / viewH
        Matrix.perspectiveM(proj, 0, 36f, aspect, 8f, 8000f)
        Matrix.setLookAtM(view, 0, eye[0], eye[1], eye[2], target[0], target[1], target[2], 0f, 1f, 0f)
        Matrix.multiplyMM(vp, 0, proj, 0, view, 0)
        System.arraycopy(vp, 0, vpSnapshot, 0, 16)

        val sch = sc.style == "schematic"
        if (lightBg) G.glClearColor(0.855f, 0.859f, 0.866f, 1f)
        else G.glClearColor(0.051f, 0.063f, 0.082f, 1f)
        G.glClear(G.GL_COLOR_BUFFER_BIT or G.GL_DEPTH_BUFFER_BIT)
        G.glUseProgram(prog)
        G.glUniformMatrix4fv(uVP, 1, false, vp, 0)
        G.glUniform1f(uE, explode)
        G.glUniform3f(uHi, clip[0], clip[1], clip[2])
        G.glUniform1f(uClip, 1f)
        G.glUniform1f(uFlat, if (sch) 1f else 0f)
        bindMain()
        G.glBindBuffer(G.GL_ELEMENT_ARRAY_BUFFER, vbo[4])
        G.glEnable(G.GL_BLEND); G.glBlendFunc(G.GL_SRC_ALPHA, G.GL_ONE_MINUS_SRC_ALPHA)
        if (edges) { G.glEnable(G.GL_POLYGON_OFFSET_FILL); G.glPolygonOffset(1.2f, 1.2f) }

        val hot = highlight
        for (p in sc.parts) {
            if (!p.visible) continue
            if (ghost && p.material == "mo") continue
            val st = style(sc, p)
            val tx = texOf(p.material)
            G.glUniform3f(uTex, tx[0], tx[1], tx[2])
            G.glUniform1f(uA, 1f)
            G.glUniform1f(uTint, if (p === hot) st[0] * 1.28f else st[0])
            G.glUniform3f(uAdd, st[1], st[2], st[3])
            G.glDrawElements(G.GL_TRIANGLES, p.count, G.GL_UNSIGNED_SHORT, p.start * 2)
        }
        G.glUniform3f(uAdd, 0f, 0f, 0f)

        if (capVerts > 0) {
            G.glUniform1f(uClip, 0f); G.glUniform1f(uA, 1f); G.glUniform1f(uTint, 1.02f)
            G.glUniform3f(uTex, if (texture) 0.05f else 0f, 0.34f, 0f)
            bindCaps(); G.glDrawArrays(G.GL_TRIANGLES, 0, capVerts)
            bindMain(); G.glBindBuffer(G.GL_ELEMENT_ARRAY_BUFFER, vbo[4]); G.glUniform1f(uClip, 1f)
        }
        if (ghost) {
            G.glDepthMask(false); G.glUniform3f(uTex, 0f, 1f, 0f)
            for (p in sc.parts) {
                if (!p.visible || p.material != "mo") continue
                G.glUniform1f(uA, 0.16f); G.glUniform1f(uTint, 1.3f)
                G.glDrawElements(G.GL_TRIANGLES, p.count, G.GL_UNSIGNED_SHORT, p.start * 2)
            }
            G.glDepthMask(true)
        }
        if (edges) {
            G.glDisable(G.GL_POLYGON_OFFSET_FILL)
            val ec = if (lightBg) floatArrayOf(0.16f, 0.19f, 0.24f) else floatArrayOf(0.09f, 0.12f, 0.17f)
            attach(lbo[0], aPos); attach(lbo[1], aExp)
            G.glDisableVertexAttribArray(aNrm); G.glVertexAttrib3f(aNrm, 0f, 0f, 1f)
            G.glDisableVertexAttribArray(aCol); G.glVertexAttrib3f(aCol, 0f, 0f, 0f)
            G.glUniform1f(uClip, 1f); G.glUniform1f(uA, 1f); G.glUniform1f(uTint, 0f)
            G.glUniform3f(uTex, 0f, 1f, 0f)
            G.glUniform3f(uAdd, ec[0], ec[1], ec[2])
            for (p in sc.parts) {
                if (!p.visible || p.lineCount == 0) continue
                G.glDrawArrays(G.GL_LINES, p.lineStart, p.lineCount)
            }
            if (capLineVerts > 0) {   // and round every cut face, so a section reads as a drawing
                attach(clbo[0], aPos); attach(clbo[1], aExp)
                G.glUniform1f(uClip, 0f)
                G.glDrawArrays(G.GL_LINES, 0, capLineVerts)
                G.glUniform1f(uClip, 1f)
            }
            G.glEnableVertexAttribArray(aNrm); G.glEnableVertexAttribArray(aCol)
            G.glUniform3f(uAdd, 0f, 0f, 0f)
        }
        G.glDisable(G.GL_BLEND)
    }

    // ---- procedural surface texture ---------------------------------------
    private val texMetal = floatArrayOf(0.10f, 0.28f, 1f)
    private val texSemi = floatArrayOf(0.09f, 0.40f, 0f)
    private val texDiel = floatArrayOf(0.07f, 0.18f, 0f)
    private val texWell = floatArrayOf(0.055f, 0.10f, 0f)
    private val texNone = floatArrayOf(0f, 1f, 0f)
    private val metals = setOf("mo", "tin", "nickel", "tungsten", "nisi", "md", "po", "vd", "vg", "m0")
    private val semis = setOf("silicon", "sige", "nanowire")
    private val diels = setOf("sio2", "highk", "si3n4", "wall", "mdi", "bond", "fox")
    private val wells = setOf("pwell", "nwell")

    private fun texOf(mat: String): FloatArray {
        if (!texture) return texNone
        return when (mat) {
            in metals -> texMetal
            in semis -> texSemi
            in diels -> texDiel
            in wells -> texWell
            else -> texSemi
        }
    }

    // ---- logic shading ---------------------------------------------------
    private val hiC = floatArrayOf(0.32f, 0.19f, 0.03f)
    private val loC = floatArrayOf(0.02f, 0.18f, 0.23f)
    private val hiC2 = floatArrayOf(0.16f, 0.10f, 0.02f)
    private val loC2 = floatArrayOf(0.01f, 0.09f, 0.12f)

    /** returns [tint, addR, addG, addB] */
    private fun style(sc: Scene, p: Part): FloatArray {
        if (!sc.logic) return floatArrayOf(1f, 0f, 0f, 0f)
        val hi = input == 1
        val flat = sc.style == "schematic"
        val h = if (flat) hiC2 else hiC
        val l = if (flat) loC2 else loC
        if (flat) {
            when (p.net) {
                "chan_p" -> return if (hi) floatArrayOf(0.50f, 0f, 0f, 0f) else floatArrayOf(1.22f, 0f, 0f, 0f)
                "chan_n" -> return if (hi) floatArrayOf(1.22f, 0f, 0f, 0f) else floatArrayOf(0.50f, 0f, 0f, 0f)
            }
        }
        return when (p.net) {
            "vdd" -> floatArrayOf(1f, h[0], h[1], h[2])
            "gnd" -> floatArrayOf(1f, l[0], l[1], l[2])
            "in" -> if (hi) floatArrayOf(1f, h[0], h[1], h[2]) else floatArrayOf(1f, l[0], l[1], l[2])
            "out" -> if (hi) floatArrayOf(1f, l[0], l[1], l[2]) else floatArrayOf(1f, h[0], h[1], h[2])
            "chan_p" -> if (hi) floatArrayOf(0.38f, 0f, 0f, 0f) else floatArrayOf(1f, hiC[0], hiC[1], hiC[2])
            "chan_n" -> if (hi) floatArrayOf(1f, loC[0], loC[1], loC[2]) else floatArrayOf(0.38f, 0f, 0f, 0f)
            else -> floatArrayOf(1f, 0f, 0f, 0f)
        }
    }

    // ---- section caps ----------------------------------------------------
    fun offsetBox(p: Part, i: Int): Pair<FloatArray, FloatArray> {
        val a = p.aabb[i]; val e = explode
        return Pair(floatArrayOf(a.lo[0] + a.ev[0] * e, a.lo[1] + a.ev[1] * e, a.lo[2] + a.ev[2] * e),
            floatArrayOf(a.hi[0] + a.ev[0] * e, a.hi[1] + a.ev[1] * e, a.hi[2] + a.ev[2] * e))
    }

    fun rebuildCaps() {
        val sc = scene
        capPos.clear(); capNrm.clear(); capCol.clear(); capExp.clear()
        capLinePos.clear(); capLineExp.clear()
        var n = 0
        var ln = 0
        val on = booleanArrayOf(clip[0] < sc.hi[0] - 0.01f, clip[1] < sc.hi[1] - 0.01f, clip[2] < sc.hi[2] - 0.01f)
        if (on[0] || on[1] || on[2]) {
            for (p in sc.parts) {
                if (!p.visible) continue
                val st = style(sc, p)
                val c0 = lib.materials[p.material]?.color ?: floatArrayOf(1f, 0f, 1f)
                val col = floatArrayOf(
                    minOf(1.4f, c0[0] * st[0] + st[1]),
                    minOf(1.4f, c0[1] * st[0] + st[2]),
                    minOf(1.4f, c0[2] * st[0] + st[3]))
                for (i in p.aabb.indices) {
                    val (lo, rawHi) = offsetBox(p, i)
                    val hi = floatArrayOf(minOf(rawHi[0], clip[0]), minOf(rawHi[1], clip[1]), minOf(rawHi[2], clip[2]))
                    for (ax in 0 until 3) {
                        if (!on[ax]) continue
                        val v = clip[ax]
                        if (v <= lo[ax] || v >= rawHi[ax]) continue
                        val u = (ax + 1) % 3; val w = (ax + 2) % 3
                        if (hi[u] <= lo[u] || hi[w] <= lo[w]) continue
                        if (n + 6 > 19000) continue
                        val nrm = floatArrayOf(0f, 0f, 0f); nrm[ax] = 1f
                        fun corner(su: Boolean, sw: Boolean): FloatArray {
                            val q = FloatArray(3); q[ax] = v - 0.002f
                            q[u] = if (su) hi[u] else lo[u]; q[w] = if (sw) hi[w] else lo[w]; return q
                        }
                        val quad = if (ax == 1)
                            arrayOf(corner(false, false), corner(false, true), corner(true, true), corner(true, false))
                        else arrayOf(corner(false, false), corner(true, false), corner(true, true), corner(false, true))
                        for (k in intArrayOf(0, 1, 2, 0, 2, 3)) {
                            capPos.put(quad[k][0]).put(quad[k][1]).put(quad[k][2])
                            capNrm.put(nrm[0]).put(nrm[1]).put(nrm[2])
                            capCol.put(col[0]).put(col[1]).put(col[2])
                            capExp.put(0f).put(0f).put(0f)
                            n++
                        }
                        if (ln + 8 <= 19000) {     // border of this cross-section
                            for (k in 0 until 4) {
                                val q0 = quad[k]; val q1 = quad[(k + 1) % 4]
                                capLinePos.put(q0[0]).put(q0[1]).put(q0[2])
                                capLineExp.put(0f).put(0f).put(0f)
                                capLinePos.put(q1[0]).put(q1[1]).put(q1[2])
                                capLineExp.put(0f).put(0f).put(0f)
                                ln += 2
                            }
                        }
                    }
                }
            }
        }
        capVerts = n
        capLineVerts = ln
        capPos.position(0); capNrm.position(0); capCol.position(0); capExp.position(0)
        capLinePos.position(0); capLineExp.position(0)
        if (ready) {
            uploadDyn(cbo[0], capPos, n * 3); uploadDyn(cbo[1], capNrm, n * 3)
            uploadDyn(cbo[2], capCol, n * 3); uploadDyn(cbo[3], capExp, n * 3)
            uploadDyn(clbo[0], capLinePos, ln * 3); uploadDyn(clbo[1], capLineExp, ln * 3)
        }
    }

    /** Two-finger pan, in screen units, along the camera's right and up axes. */
    /**
     * Half the vertical field of view, as a tangent. The projection is 36 degrees, so
     * one screen pixel spans `2 * dist * TAN_HALF_FOV / viewH` world units at the target
     * plane — which is what makes a pan track the finger exactly instead of racing it.
     */
    private val tanHalfFov = 0.3249f

    /** World units per screen pixel at the target plane. */
    fun worldPerPixel(): Float = 2f * dist * tanHalfFov / maxOf(viewH, 1)

    /** Shift the camera target along its own right and up axes. */
    fun panBy(dx: Float, dy: Float) {
        // Derive the basis from az/el rather than the cached eye, which the GL thread owns.
        val ce = cos(el)
        val f = floatArrayOf(-ce * sin(az), -sin(el), -ce * cos(az))
        // right = f x worldUp; the old code had this negated, which inverted both axes
        val r = floatArrayOf(-f[2], 0f, f[0])
        val rl = hypot(r[0].toDouble(), r[2].toDouble()).toFloat().let { if (it < 1e-6f) 1f else it }
        r[0] /= rl; r[2] /= rl
        val u = floatArrayOf(r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0])
        val t = target.copyOf()
        t[0] += r[0] * dx + u[0] * dy; t[1] += r[1] * dx + u[1] * dy; t[2] += r[2] * dx + u[2] * dy
        target = t
    }

    // ---- picking ---------------------------------------------------------
    /** Inverted view-projection, so a batch of picks can share one inversion. */
    fun pickInv(): FloatArray? {
        val inv = FloatArray(16)
        return if (Matrix.invertM(inv, 0, vpSnapshot, 0)) inv else null
    }

    fun pick(px: Float, py: Float): Part? = pick(px, py, pickInv())

    fun pick(px: Float, py: Float, inv: FloatArray?): Part? {
        if (inv == null) return null
        val ndcX = px / viewW * 2f - 1f
        val ndcY = 1f - py / viewH * 2f
        val near = FloatArray(4); val far = FloatArray(4)
        Matrix.multiplyMV(near, 0, inv, 0, floatArrayOf(ndcX, ndcY, -1f, 1f), 0)
        Matrix.multiplyMV(far, 0, inv, 0, floatArrayOf(ndcX, ndcY, 1f, 1f), 0)
        for (k in 0 until 3) { near[k] /= near[3]; far[k] /= far[3] }
        val d = floatArrayOf(far[0] - near[0], far[1] - near[1], far[2] - near[2])
        val len = kotlin.math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])
        for (k in 0 until 3) d[k] /= len
        val o = floatArrayOf(near[0], near[1], near[2])
        var best: Part? = null; var bt = Float.MAX_VALUE
        for (p in scene.parts) {
            if (!p.visible) continue
            for (i in p.aabb.indices) {
                val (lo, rawHi) = offsetBox(p, i)
                val hi = floatArrayOf(minOf(rawHi[0], clip[0]), minOf(rawHi[1], clip[1]), minOf(rawHi[2], clip[2]))
                if (hi[0] <= lo[0] || hi[1] <= lo[1] || hi[2] <= lo[2]) continue
                var t0 = -1e9f; var t1 = 1e9f; var miss = false
                for (k in 0 until 3) {
                    if (abs(d[k]) < 1e-9f) { if (o[k] < lo[k] || o[k] > hi[k]) { miss = true; break }; continue }
                    var ta = (lo[k] - o[k]) / d[k]; var tb = (hi[k] - o[k]) / d[k]
                    if (ta > tb) { val s = ta; ta = tb; tb = s }
                    if (ta > t0) t0 = ta
                    if (tb < t1) t1 = tb
                    if (t0 > t1) { miss = true; break }
                }
                if (!miss && t0 > 0f && t0 < bt) { bt = t0; best = p }
            }
        }
        return best
    }

    /** One sampling point, held relative to a box so it follows an exploded part. */
    class Sample(val part: Part, val bi: Int, val d: FloatArray)

    /**
     * Points sitting just proud of a part's faces. A label anchors on whichever of these
     * the camera can actually see, so the dot never lands on a layer in front of it.
     */
    fun faceSamples(ids: List<String>): List<Sample> {
        val sc = scene
        val refs = ArrayList<Triple<Part, Int, FloatArray>>()
        for (id in ids) {
            val part = sc.parts.firstOrNull { it.id == id } ?: continue
            part.boxes.forEachIndexed { bi, b -> refs.add(Triple(part, bi, b)) }
        }
        if (refs.isEmpty()) return emptyList()
        refs.sortByDescending { it.third[3] * it.third[4] * it.third[5] }
        val out = ArrayList<Sample>()
        for ((part, bi, b) in refs.take(3)) {
            val h = floatArrayOf(b[3] / 2f, b[4] / 2f, b[5] / 2f)
            for (ax in 0 until 3) for (sg in intArrayOf(-1, 1)) {
                val u = (ax + 1) % 3; val v = (ax + 2) % 3
                val lng = if (h[u] >= h[v]) u else v
                for (t in floatArrayOf(0f, -0.55f, 0.55f)) {
                    val d = floatArrayOf(0f, 0f, 0f)
                    d[ax] = sg * (h[ax] + 0.35f)
                    d[lng] += t * h[lng]
                    out.add(Sample(part, bi, d))
                }
            }
        }
        return out
    }

    /** Where a sample sits right now, following the part if the model is exploded. */
    fun samplePoint(s: Sample): FloatArray {
        val (lo, hi) = offsetBox(s.part, s.bi)
        return floatArrayOf((lo[0] + hi[0]) / 2f + s.d[0],
                            (lo[1] + hi[1]) / 2f + s.d[1],
                            (lo[2] + hi[2]) / 2f + s.d[2])
    }

    /** Screen-space box the whole scene occupies: [x0, y0, x1, y1]. */
    fun silhouette(): FloatArray? {
        val sc = scene
        var x0 = Float.MAX_VALUE; var y0 = Float.MAX_VALUE
        var x1 = -Float.MAX_VALUE; var y1 = -Float.MAX_VALUE
        for (x in floatArrayOf(sc.lo[0], sc.hi[0]))
            for (y in floatArrayOf(sc.lo[1], sc.hi[1]))
                for (z in floatArrayOf(sc.lo[2], sc.hi[2])) {
                    val q = project(floatArrayOf(x, y, z)) ?: continue
                    if (q[0] < x0) x0 = q[0]; if (q[0] > x1) x1 = q[0]
                    if (q[1] < y0) y0 = q[1]; if (q[1] > y1) y1 = q[1]
                }
        return if (x1 < x0) null else floatArrayOf(x0, y0, x1, y1)
    }

    /** World point to view-space pixels, or null when behind the camera. */
    fun project(p: FloatArray): FloatArray? {
        val m = vpSnapshot
        val x = m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12]
        val y = m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13]
        val w = m[3] * p[0] + m[7] * p[1] + m[11] * p[2] + m[15]
        if (w <= 0f) return null
        return floatArrayOf((x / w * 0.5f + 0.5f) * viewW, (1f - (y / w * 0.5f + 0.5f)) * viewH)
    }

    // ---- gl helpers ------------------------------------------------------
    private fun bindMain() {
        attach(vbo[0], aPos); attach(vbo[1], aNrm); attach(vbo[2], aCol); attach(vbo[3], aExp)
    }
    private fun bindCaps() {
        attach(cbo[0], aPos); attach(cbo[1], aNrm); attach(cbo[2], aCol); attach(cbo[3], aExp)
    }
    private fun attach(buf: Int, loc: Int) {
        G.glBindBuffer(G.GL_ARRAY_BUFFER, buf)
        G.glEnableVertexAttribArray(loc)
        G.glVertexAttribPointer(loc, 3, G.GL_FLOAT, false, 0, 0)
    }
    private fun upload(buf: Int, data: FloatBuffer) {
        G.glBindBuffer(G.GL_ARRAY_BUFFER, buf)
        G.glBufferData(G.GL_ARRAY_BUFFER, data.capacity() * 4, data, G.GL_STATIC_DRAW)
    }
    private fun uploadDyn(buf: Int, data: FloatBuffer, floats: Int) {
        G.glBindBuffer(G.GL_ARRAY_BUFFER, buf)
        G.glBufferData(G.GL_ARRAY_BUFFER, maxOf(floats, 3) * 4, data, G.GL_DYNAMIC_DRAW)
    }
    private fun link(vs: String, fs: String): Int {
        val v = compile(G.GL_VERTEX_SHADER, vs); val f = compile(G.GL_FRAGMENT_SHADER, fs)
        val p = G.glCreateProgram(); G.glAttachShader(p, v); G.glAttachShader(p, f); G.glLinkProgram(p)
        return p
    }
    private fun compile(type: Int, src: String): Int {
        val s = G.glCreateShader(type); G.glShaderSource(s, src); G.glCompileShader(s)
        val ok = IntArray(1); G.glGetShaderiv(s, G.GL_COMPILE_STATUS, ok, 0)
        if (ok[0] == 0) android.util.Log.e("FetLab", G.glGetShaderInfoLog(s))
        return s
    }
    private fun alloc(floats: Int): FloatBuffer =
        ByteBuffer.allocateDirect(floats * 4).order(ByteOrder.nativeOrder()).asFloatBuffer()
}
