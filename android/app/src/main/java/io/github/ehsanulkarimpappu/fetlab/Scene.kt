package io.github.ehsanulkarimpappu.fetlab

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** One axis-aligned box, plus the direction it flies off in when the model is exploded. */
class Aabb(val lo: FloatArray, val hi: FloatArray, val ev: FloatArray)

class Part(
    val id: String,
    val name: String,
    val material: String,
    val group: String,
    val net: String,
    val boxes: List<FloatArray>,
    val explode: FloatArray?,      // fixed direction, or null when radial
    val radial: FloatArray?        // [yCentre, magnitude, zCentre]
) {
    var visible = true
    var start = 0                  // index-buffer offset
    var count = 0
    var lineStart = 0              // edge-outline vertex offset
    var lineCount = 0
    val aabb = ArrayList<Aabb>()
}

class ViewPreset(
    val key: String, val label: String, val sub: String,
    val az: Float, val el: Float, val r: Float,
    val tgt: FloatArray, val clip: Array<Float?>?, val off: Set<String>
)

/** One parasitic term, and the two conductor groups it couples. */
class Parasitic(
    val id: String, val sym: String, val pair: String, val desc: String,
    val aF: Float, val perUm: Float, val pct: Float,
    val a: List<String>, val b: List<String>, val via: List<String>
)

class Parasitics(
    val terms: List<Parasitic>, val weff: Float, val foot: Float, val lg: Float,
    val gatePar: Float, val gateParPct: Float, val note: String
)

class Callout(
    val label: String, val value: String, val desc: String,
    val a: FloatArray, val b: FloatArray, val lab: FloatArray, val views: Set<String>?,
    val flat: Boolean = false, val size: String = "m", val tone: String = "dark",
    /** Park the text in the margin and run a hairline back to the layer it names. */
    val lead: Boolean = false,
    /** Forced column: -1 left, +1 right, 0 to let the renderer choose. */
    val sd: Int = 0,
    /** Parts this label is for; the renderer anchors on whichever one it can see. */
    val pids: List<String> = emptyList()
)

class Scene(
    val key: String, val name: String, val tag: String, val blurb: String,
    val note: String, val logic: Boolean, val style: String,
    val lo: FloatArray, val hi: FloatArray,
    val parts: List<Part>, val views: List<ViewPreset>,
    val dims: List<Triple<String, String, String>>, val groups: List<String>
) {
    var callouts: List<Callout> = emptyList()
    /** Written background for this architecture, as a small subset of HTML. */
    var story: String = ""
    /** Parasitic capacitances derived from this scene's geometry. Device scenes only. */
    var par: Parasitics? = null

    val centre get() = floatArrayOf((lo[0] + hi[0]) / 2f, (lo[1] + hi[1]) / 2f, (lo[2] + hi[2]) / 2f)
    val span get() = maxOf(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
}

class Material(val key: String, val label: String, val color: FloatArray, val note: String)

class Library(val materials: Map<String, Material>, val order: List<String>, val scenes: List<Scene>, val guide: GuideCatalog) {
    fun scene(key: String): Scene = scenes.first { it.key == key }
    companion object {
        fun load(ctx: Context): Library {
            val txt = ctx.assets.open("devices.json").bufferedReader().use { it.readText() }
            val root = JSONObject(txt)

            val mats = HashMap<String, Material>()
            val mo = root.getJSONObject("materials")
            for (k in mo.keys()) {
                val m = mo.getJSONObject(k)
                mats[k] = Material(k, m.getString("label"), hexToRgb(m.getString("color")),
                    m.optString("note", ""))
            }
            val order = root.getJSONArray("order").toStringList()

            val scenes = ArrayList<Scene>()
            val darr = root.getJSONArray("devices")
            for (i in 0 until darr.length()) {
                val d = darr.getJSONObject(i)
                val b = d.getJSONObject("bounds")
                val lo = floatArrayOf(b.getJSONArray("x").getDouble(0).toFloat(),
                    b.getJSONArray("y").getDouble(0).toFloat(), b.getJSONArray("z").getDouble(0).toFloat())
                val hi = floatArrayOf(b.getJSONArray("x").getDouble(1).toFloat(),
                    b.getJSONArray("y").getDouble(1).toFloat(), b.getJSONArray("z").getDouble(1).toFloat())

                val parts = ArrayList<Part>()
                val pa = d.getJSONArray("parts")
                for (j in 0 until pa.length()) {
                    val p = pa.getJSONObject(j)
                    val boxes = ArrayList<FloatArray>()
                    val ba = p.getJSONArray("boxes")
                    for (k in 0 until ba.length()) boxes.add(ba.getJSONArray(k).toFloats())
                    var fixed: FloatArray? = null
                    var radial: FloatArray? = null
                    val e = p.opt("explode")
                    if (e is JSONArray && e.length() > 0) {
                        if (e.get(0) is String) {
                            radial = floatArrayOf(
                                e.getDouble(1).toFloat(), e.getDouble(2).toFloat(),
                                if (e.length() > 3) e.getDouble(3).toFloat() else 0f)
                        } else fixed = e.toFloats()
                    }
                    parts.add(Part(p.getString("id"), p.getString("name"), p.getString("material"),
                        p.optString("group", "Other"), p.optString("net", "body"), boxes, fixed, radial))
                }

                val views = ArrayList<ViewPreset>()
                val vo = d.getJSONObject("views")
                for (vk in vo.keys()) {
                    val v = vo.getJSONObject(vk)
                    val clipArr = v.opt("clip")
                    var clip: Array<Float?>? = null
                    if (clipArr is JSONArray) {
                        clip = arrayOfNulls(3)
                        for (c in 0 until 3) if (!clipArr.isNull(c)) clip[c] = clipArr.getDouble(c).toFloat()
                    }
                    val off = HashSet<String>()
                    (v.opt("off") as? JSONArray)?.let { for (c in 0 until it.length()) off.add(it.getString(c)) }
                    views.add(ViewPreset(vk, v.getString("n"), v.getString("s"),
                        v.getDouble("az").toFloat(), v.getDouble("el").toFloat(), v.getDouble("r").toFloat(),
                        v.getJSONArray("tgt").toFloats(), clip, off))
                }

                val cal = ArrayList<Callout>()
                (d.opt("callouts") as? JSONArray)?.let {
                    for (c in 0 until it.length()) {
                        val q = it.getJSONObject(c)
                        val vs = (q.opt("v") as? JSONArray)?.toStringList()?.toSet()
                        val pids = when (val pd = q.opt("pid")) {
                            is String -> listOf(pd)
                            is JSONArray -> pd.toStringList()
                            else -> emptyList()
                        }
                        cal.add(Callout(q.getString("label"), q.optString("value", ""), q.optString("desc", ""),
                            q.getJSONArray("a").toFloats(), q.getJSONArray("b").toFloats(),
                            q.getJSONArray("lab").toFloats(), vs,
                            q.optBoolean("flat", false), q.optString("size", "m"), q.optString("tone", "dark"),
                            q.optBoolean("lead", false), q.optInt("sd", 0), pids))
                    }
                }

                val story = d.optString("story", "")

                val dims = ArrayList<Triple<String, String, String>>()
                (d.opt("dims") as? JSONArray)?.let {
                    for (c in 0 until it.length()) {
                        val row = it.getJSONArray(c)
                        dims.add(Triple(row.getString(0), row.getString(1), row.getString(2)))
                    }
                }
                val sc = Scene(d.getString("key"), d.getString("name"), d.optString("tag", ""),
                    d.optString("blurb", ""), d.optString("note", ""), d.optBoolean("logic", false),
                    d.optString("style", ""), lo, hi, parts, views, dims,
                    d.getJSONArray("groups").toStringList())
                sc.callouts = cal
                sc.story = story
                (d.opt("parasitics") as? JSONObject)?.let { pj ->
                    val terms = ArrayList<Parasitic>()
                    val ta = pj.getJSONArray("terms")
                    for (c in 0 until ta.length()) {
                        val t = ta.getJSONObject(c)
                        terms.add(Parasitic(
                            t.getString("id"), strip(t.getString("sym")), t.getString("pair"),
                            strip(t.getString("desc")),
                            t.getDouble("aF").toFloat(), t.getDouble("per_um").toFloat(),
                            t.getDouble("pct").toFloat(),
                            t.getJSONArray("a").toStringList(), t.getJSONArray("b").toStringList(),
                            t.getJSONArray("via").toStringList()))
                    }
                    sc.par = Parasitics(terms, pj.getDouble("weff").toFloat(),
                        pj.getDouble("foot").toFloat(), pj.getDouble("lg").toFloat(),
                        pj.getDouble("gate_par").toFloat(),
                        pj.getDouble("gate_par_pct").toFloat(), strip(pj.getString("note")))
                }
                scenes.add(sc)
            }
            return Library(mats, order, scenes, GuideCatalog.load(ctx))
        }

        /** The data carries a little HTML for the web build; the app wants plain text. */
        private fun strip(t: String) = t
            .replace(Regex("<[^>]+>"), "")
            .replace("&kappa;", "κ").replace("&mu;", "µ").replace("&amp;", "&")

        private fun hexToRgb(h: String) = floatArrayOf(
            h.substring(1, 3).toInt(16) / 255f,
            h.substring(3, 5).toInt(16) / 255f,
            h.substring(5, 7).toInt(16) / 255f)
    }
}

private fun JSONArray.toFloats(): FloatArray =
    FloatArray(length()) { getDouble(it).toFloat() }

private fun JSONArray.toStringList(): List<String> =
    List(length()) { getString(it) }
