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
    val tgt: FloatArray, val clip: Array<Float?>?, val off: Set<String>,
    /** For process views: the scale they frame ("site" or "tile"). */
    val scale: String = "site"
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
    /** For a fabrication step: the flow it belongs to and where it sits in it. */
    var flow: ProcessFlow? = null
    var stepIndex = 0
    val step: ProcessStep? get() = flow?.steps?.getOrNull(stepIndex)
    /** First vertex of this scene in the renderer's shared buffers (renderer-owned). */
    var vbase = 0

    val centre get() = floatArrayOf((lo[0] + hi[0]) / 2f, (lo[1] + hi[1]) / 2f, (lo[2] + hi[2]) / 2f)
    val span get() = maxOf(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
}

class Material(val key: String, val label: String, val color: FloatArray, val note: String)

/** One stage of a fabrication flow: what happens, and the view that shows it best, with
 *  how it relates to its source: the source's figure identifiers, a match level (a key of
 *  [ProcessFlow.match]), the model's substitutions, and what this view leaves out. */
class ProcessStep(val id: String, val title: String, val body: String, val view: String,
                  val figs: List<String>, val match: String,
                  val subs: List<String>, val omitted: List<String>,
                  /** "core", or "op" for an operation substep leading into core step [of]. */
                  val level: String, val of: String, val label: String,
                  /** "site" for the single device, "tile" for the 2 x 2 patterning context,
                   *  "field" for the lines around the tile. */
                  val scale: String,
                  /** The patterning route this operation belongs to, or null if every route
                   *  passes through it; [labels] numbers a shared one along each route. */
                  val route: String?, val labels: Map<String, String>,
                  /** The references [figs] belong to, when a flow draws on more than one. */
                  val src: List<String> = emptyList(),
                  /** Films the viewer shows depositing on entering this step, in order. */
                  val deposit: List<String> = emptyList()) {
    val isOp get() = level == "op"
    fun labelIn(route: String) = labels[route] ?: label
    /** Shown on the header under the device's name. */
    fun tag(route: String) = when (scale) {
        "tile" -> "Process · 2 × 2 tile · step ${labelIn(route)}"
        "field" -> "Process · line field · step ${labelIn(route)}"
        else -> "Process · step ${labelIn(route)}"
    }
}

/** One way through a run of operations: the stack hard mask printed directly, or made by
 *  SADP or SAQP. Only the chosen route's operations are stepped through. */
class Route(val id: String, val name: String, val note: String, val isDefault: Boolean)

/** A device's fabrication flow. Every step is a scene of its own, keyed [keys]. [figures]
 *  and [branch] qualify every figure mapping and are shown with the steps. */
class ProcessFlow(val device: String, val scope: String, val figures: String, val branch: String,
                  val match: Map<String, String>, val refs: List<String>,
                  val steps: List<ProcessStep>, val keys: List<String>, val routes: List<Route>,
                  /** The route picker's heading, and the step every route rejoins at. */
                  val routeTitle: String, val routeJoin: String,
                  /** A match level's short badge for the stepper ("Source stage", "Teaching"...). */
                  val badge: Map<String, String> = emptyMap()) {
    val coreCount get() = steps.count { !it.isOp }
    /** The route shown until the user picks one: the one marked default, else the first. */
    val defaultRoute get() = (routes.firstOrNull { it.isDefault } ?: routes.firstOrNull())?.id ?: ""
    /** [route] if this flow has it, else its default. */
    fun routeOr(route: String) = if (routes.any { it.id == route }) route else defaultRoute
    /** Whether step [i] is on [route]: shared steps are on every route. */
    fun onRoute(i: Int, route: String): Boolean {
        val r = steps[i].route ?: return true
        return r == routeOr(route)
    }
    /** The next step from [from] in direction [dir] (+1 or -1) along [route], skipping
     *  operation substeps unless [ops]; null at either end. */
    fun next(from: Int, dir: Int, ops: Boolean, route: String): Int? {
        var i = from + dir
        while (i in steps.indices) { if ((ops || !steps[i].isOp) && onRoute(i, route)) return i; i += dir }
        return null
    }
}

class Reference(val id: String, val title: String, val publisher: String, val url: String)

/** The scene key of step [i] of the flow for device [device]. */
fun stepKey(device: String, i: Int) = "proc_$device@$i"

class Library(val materials: Map<String, Material>, val order: List<String>, val scenes: List<Scene>,
              val flows: Map<String, ProcessFlow>, val refs: Map<String, Reference>) {
    fun scene(key: String): Scene = scenes.first { it.key == key }
    companion object {
        fun load(ctx: Context): Library {
            fun asset(name: String) = ctx.assets.open(name).bufferedReader().use { it.readText() }
            val txt = asset("devices.json")
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
            val devJson = HashMap<String, JSONObject>()
            val darr = root.getJSONArray("devices")
            for (i in 0 until darr.length()) {
                val d = darr.getJSONObject(i)
                devJson[d.getString("key")] = d
                val b = d.getJSONObject("bounds")
                val lo = floatArrayOf(b.getJSONArray("x").getDouble(0).toFloat(),
                    b.getJSONArray("y").getDouble(0).toFloat(), b.getJSONArray("z").getDouble(0).toFloat())
                val hi = floatArrayOf(b.getJSONArray("x").getDouble(1).toFloat(),
                    b.getJSONArray("y").getDouble(1).toFloat(), b.getJSONArray("z").getDouble(1).toFloat())

                val parts = ArrayList<Part>()
                val pa = d.getJSONArray("parts")
                for (j in 0 until pa.length()) parts.add(parsePart(pa.getJSONObject(j)))

                val views = parseViews(d.getJSONObject("views"))

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

            val refs = HashMap<String, Reference>()
            runCatching {
                val ra = JSONObject(asset("references.json")).getJSONArray("sources")
                for (i in 0 until ra.length()) {
                    val r = ra.getJSONObject(i)
                    refs[r.getString("id")] = Reference(r.getString("id"), r.getString("title"),
                        r.getString("publisher"), r.getString("url"))
                }
            }

            // Each fabrication step becomes a scene of its own, with fresh Part objects, so
            // hiding a layer in a step never touches the finished device in Device mode.
            val flows = LinkedHashMap<String, ProcessFlow>()
            val proc = runCatching { JSONObject(asset("process.json")).getJSONObject("flows") }.getOrNull()
            if (proc != null) for (dk in proc.keys()) {
                val fj = proc.getJSONObject(dk)
                // A lesson (the SADP and SAQP chips) has no finished device behind it: its
                // name, bounds and views come with the flow, and every part is its own.
                val base = if (fj.optBoolean("lesson", false)) fj.getJSONObject("bounds").let { b ->
                    Scene(dk, fj.optString("name", dk), "", "", "", false, "",
                        floatArrayOf(b.getJSONArray("x").getDouble(0).toFloat(),
                            b.getJSONArray("y").getDouble(0).toFloat(), b.getJSONArray("z").getDouble(0).toFloat()),
                        floatArrayOf(b.getJSONArray("x").getDouble(1).toFloat(),
                            b.getJSONArray("y").getDouble(1).toFloat(), b.getJSONArray("z").getDouble(1).toFloat()),
                        emptyList(), emptyList(), emptyList(), emptyList()).also { it.story = fj.optString("scope", "") }
                } else scenes.firstOrNull { it.key == dk } ?: continue
                val finalParts = HashMap<String, JSONObject>()
                devJson[dk]?.getJSONArray("parts")?.let { for (j in 0 until it.length()) it.getJSONObject(j).let { p -> finalParts[p.getString("id")] = p } }
                val views = base.views + (fj.optJSONObject("views")?.let { parseViews(it) } ?: emptyList())
                val sa = fj.getJSONArray("steps")
                val steps = ArrayList<ProcessStep>()
                val stepScenes = ArrayList<Scene>()
                for (i in 0 until sa.length()) {
                    val sj = sa.getJSONObject(i)
                    fun list(k: String) = (sj.optJSONArray(k) ?: JSONArray()).toStringList()
                    val scale = sj.optString("scale", "site")
                    val labels = HashMap<String, String>()
                    sj.optJSONObject("labels")?.let { m -> for (k in m.keys()) labels[k] = m.getString(k) }
                    steps.add(ProcessStep(sj.getString("id"), sj.getString("title"), sj.getString("body"),
                        sj.optString("view", "iso"), list("figs"), sj.optString("match", ""),
                        list("subs"), list("omitted"), sj.optString("level", "core"), sj.optString("of", ""),
                        sj.optString("label", "${i + 1}"), scale,
                        sj.optString("route", "").ifEmpty { null }, labels, list("src"), list("deposit")))
                    val parts = ArrayList<Part>()
                    val pa = sj.getJSONArray("parts")
                    for (j in 0 until pa.length()) {
                        val ref = pa.get(j)
                        val pj = if (ref is String) finalParts[ref] ?: continue else ref as JSONObject
                        parts.add(parsePart(pj))
                    }
                    // The device's group order, then whatever this step adds, in order.
                    val present = parts.map { it.group }.toSet()
                    val groups = base.groups.filter { it in present } +
                        parts.map { it.group }.distinct().filter { it !in base.groups }
                    // A step carries its own bounds when it frames more than the one site.
                    val bj = sj.optJSONObject("bounds")
                    val lo = bj?.let { floatArrayOf(it.getJSONArray("x").getDouble(0).toFloat(),
                        it.getJSONArray("y").getDouble(0).toFloat(), it.getJSONArray("z").getDouble(0).toFloat()) } ?: base.lo
                    val hi = bj?.let { floatArrayOf(it.getJSONArray("x").getDouble(1).toFloat(),
                        it.getJSONArray("y").getDouble(1).toFloat(), it.getJSONArray("z").getDouble(1).toFloat()) } ?: base.hi
                    val tag = steps.last().tag(steps.last().route ?: "")     // the header re-reads it per route
                    val sc = Scene(stepKey(dk, i), base.name, tag,
                        sj.getString("title"), "", false, base.style, lo, hi, parts,
                        views.filter { it.scale == scale }, emptyList(), groups)
                    sc.story = base.story
                    sc.stepIndex = i
                    stepScenes.add(sc)
                }
                val match = HashMap<String, String>()
                fj.optJSONObject("match")?.let { m -> for (k in m.keys()) match[k] = m.getString(k) }
                val routes = ArrayList<Route>()
                fj.optJSONArray("routes")?.let { ra ->
                    for (k in 0 until ra.length()) ra.getJSONObject(k).let { r ->
                        routes.add(Route(r.getString("id"), r.getString("name"), r.optString("note", ""),
                            r.optBoolean("default", false))) }
                }
                val flow = ProcessFlow(dk, fj.optString("scope", ""), fj.optString("figures", ""),
                    fj.optString("branch", ""), match,
                    (fj.optJSONArray("refs") ?: JSONArray()).toStringList(), steps, stepScenes.map { it.key },
                    routes, fj.optString("route_title", "How this is patterned"), fj.optString("route_join", "the next step"),
                    HashMap<String, String>().also { m -> fj.optJSONObject("badge")?.let { b -> for (k in b.keys()) m[k] = b.getString(k) } })
                for (sc in stepScenes) sc.flow = flow
                scenes.addAll(stepScenes)
                flows[dk] = flow
            }
            return Library(mats, order, scenes, flows, refs)
        }

        private fun parsePart(p: JSONObject): Part {
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
            return Part(p.getString("id"), p.getString("name"), p.getString("material"),
                p.optString("group", "Other"), p.optString("net", "body"), boxes, fixed, radial)
        }

        private fun parseViews(vo: JSONObject): List<ViewPreset> {
            val views = ArrayList<ViewPreset>()
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
                    v.getJSONArray("tgt").toFloats(), clip, off, v.optString("scale", "site")))
            }
            return views
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
