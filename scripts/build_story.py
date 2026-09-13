"""
The written background behind each architecture, attached to every scene that shows it.

Runs last, over whatever devices.json already holds, so a scene added later picks its
story up automatically from its key. Prose lives here rather than in the geometry
builders because it is edited far more often than the models are.
"""
import json, os

COMMON = """
<h4>Why any of this happens</h4>
<p>Two things drive every step on this roadmap, and neither is about making a better
transistor for its own sake. The first is <b>cost per function</b>: a generation has to
put roughly twice the logic in the same area, or it does not pay for the fab. The second
is <b>power</b>. Dennard scaling — the rule that a smaller transistor also ran at a lower
voltage, so power density stayed flat — broke down around 2005. Supply voltage stopped
falling, and from then on every extra transistor per square millimetre arrived with its
own heat. Data-centre and mobile designs became power-limited rather than area-limited,
and they still are.</p>
<p>That is why the last four device generations are all, underneath, the same move:
<b>get the gate closer to more of the channel</b>. Better electrostatic control means the
device turns off harder at a given gate voltage, which means you can lower the supply
voltage, which is the only lever that reduces energy per operation quadratically. Density
follows separately, from the cell, not from the transistor.</p>
<p>Two other pressures shape the recent steps. <b>SRAM has almost stopped scaling</b> —
memory cells now shrink far slower than logic — so logic has to carry the whole density
gain. And <b>interconnect resistance</b> rises as wires get thinner, which is why power
delivery is moving to the back of the wafer: it frees the front-side metal for signals.</p>
"""

STORY = {
"fin": """
<h4>What it replaced</h4>
<p>The planar bulk MOSFET, essentially unchanged in form since the 1960s and scaled by
Dennard's rules for thirty years. The gate sat on top of the channel; the channel sat in
the substrate.</p>

<h4>What broke</h4>
<p>Two things, in sequence. First the gate dielectric: by the 65&nbsp;nm generation SiO₂
was down to about 1.2&nbsp;nm — five atomic layers — and electrons tunnelled straight
through it. Gate leakage stopped being negligible and became a first-order term in the
power budget. That was solved in 2007 by replacing SiO₂ with hafnium oxide and the
polysilicon gate with metal: a physically thicker film with the same effective
capacitance.</p>
<p>The deeper problem could not be solved by materials. With the gate on one side only,
the drain also has a say in what the channel does. As the channel got shorter, the drain's
field began to lower the barrier the gate was supposed to control — drain-induced barrier
lowering, threshold voltage falling with gate length, and a subthreshold slope drifting
well above the 60&nbsp;mV/decade room-temperature floor. Practically: the device would no
longer switch off. Off-state leakage rose to where it dominated the power of an idle chip,
and supply voltage could not be reduced any further without losing drive.</p>

<h4>Why the industry moved</h4>
<p>Stand the channel on its edge as a fin and wrap the gate over three of its faces. The
gate is now close to nearly all of the channel volume, so it wins back control from the
drain. Subthreshold slope returns to roughly 65–70&nbsp;mV/decade, threshold voltage stops
rolling off, and — the point of the exercise — supply voltage can fall again.</p>
<p>Intel shipped the first production FinFET at 22&nbsp;nm in 2011, calling it tri-gate.
TSMC and Samsung followed at 16 and 14&nbsp;nm in 2015. It held the industry for roughly a
decade.</p>

<h4>What it cost</h4>
<p><b>Width quantisation.</b> A planar device could be drawn any width you liked. A FinFET
comes in whole fins. Wanting a slightly stronger pull-up means adding an entire fin —
a large step in area, in capacitance, and in the cell's width. Standard-cell libraries are
built around this granularity, and it wastes area in every cell that does not want an
integer number of fins.</p>
<p><b>The bottom of the fin.</b> The gate never reaches it, so sub-fin leakage has to be
suppressed by doping — a punch-through stopper — which brings back random dopant
fluctuation and variability.</p>
<p><b>Height.</b> Drive per footprint comes from fin height, so fins grew taller and
thinner until the aspect ratio became a mechanical and patterning problem, and the
sidewall capacitance became a speed problem.</p>
""",

"ns": """
<h4>What it replaced</h4>
<p>The FinFET, after about ten years in production.</p>

<h4>What broke</h4>
<p>The FinFET stopped improving rather than suddenly failing. Fin height had reached the
limit of what could be patterned and kept standing, so drive per footprint plateaued.
Width quantisation had become expensive: with only a handful of fins per device, the
granularity was a large fraction of the design space, and cells carried area they did not
need. And the sub-fin leakage path was still being held shut by doping rather than by the
gate.</p>

<h4>Why the industry moved</h4>
<p>Lay the fin on its side and cut it into a stack of horizontal sheets, then let the gate
close all the way around each one. Three consequences follow:</p>
<ul>
<li><b>Best electrostatics available.</b> No face of the channel is out of the gate's
reach, so the subthreshold slope is as close to the 60&nbsp;mV/decade floor as a
thermally-limited device gets — which is what buys the next supply-voltage reduction.</li>
<li><b>Continuous width.</b> Sheet width is drawn, not quantised. A device can be made
exactly as strong as it needs to be, which recovers the area the FinFET's granularity was
wasting.</li>
<li><b>Effective width per footprint.</b> Stacking sheets multiplies the channel
perimeter without widening the cell.</li>
</ul>
<p>Samsung was first to production, starting 3&nbsp;nm GAA in June 2022; TSMC moved at
N2. Nanosheet is the architecture the industry is on now.</p>

<h4>What it cost</h4>
<p><b>Process complexity.</b> The sheets are grown as an alternating Si/SiGe superlattice
and then released by etching the SiGe away selectively, underneath a gate that is already
partly built. Inner spacers have to be formed in cavities you cannot see into. It is a
materially harder flow than a fin etch.</p>
<p><b>Capacitance.</b> Wrapping metal all the way around the channel puts gate metal close
to the source and drain on every sheet. Effective capacitance per unit drive went up,
which eats into the speed gain.</p>
<p><b>Stack height.</b> How many sheets you can stack is limited by whether the gate metal
can still be deposited into the gaps between them, and by the vertical space the cell
allows.</p>
""",

"fs": """
<h4>What it replaces</h4>
<p>The nanosheet — not because the nanosheet device is failing, but because the
<i>cell</i> is.</p>

<h4>What broke</h4>
<p>By the nanosheet generation the limit on standard-cell height is no longer the
transistor. It is the space <b>between</b> the n and p devices. That gap has to accommodate
gate patterning, two different work-function metals and their patterning margins, and it
stopped shrinking. Cell height stalled at around five tracks, and shrinking the sheets
further bought nothing because the separation between them did not shrink with them.</p>

<h4>Why the industry is moving</h4>
<p>Put a dielectric wall between n and p and build both devices against it. The wall is
defined early, before gate patterning, so the n-to-p distance becomes the thickness of a
deposited film rather than the resolution of a lithographic gap. Cell height drops toward
roughly 4.3 tracks, and within a cell of the same height the sheets can be made wider —
so the device gets stronger at the same time the cell gets smaller.</p>
<p>This is an imec-originated architecture and is a pathfinding device rather than a
production one: it is a candidate for the generations between nanosheet and CFET.</p>

<h4>What it costs</h4>
<p><b>One gate face.</b> The wall occupies the side the gate would otherwise wrap, so a
forksheet is a three-sided device. Some of the electrostatic control the nanosheet just
won is given back — the forksheet is a footprint trick, not a better channel.</p>
<p><b>Asymmetry.</b> The device is no longer symmetric about its channel, which shows up
in stress, in parasitics, and in modelling.</p>
<p><b>A new process module.</b> The wall has to be formed, survive the sheet release, and
not introduce its own leakage path or capacitance.</p>
""",

"cfet": """
<h4>What it replaces</h4>
<p>Every architecture before it, in one respect: the assumption that the n and the p
device sit side by side.</p>

<h4>What broke</h4>
<p>Even with a dielectric wall, a CMOS cell still pays for two rows of devices. The
forksheet narrows the gap between them; it does not remove it. As long as n and p are
side by side there is a floor under cell height, and the industry can see it from here.</p>

<h4>Why the industry needs it</h4>
<p>Stack them. The pMOS is built directly above the nMOS, sharing one footprint, and the
cell loses an entire device row — a step of roughly 2× in density at unchanged device
pitch, which no amount of further sheet shrinking would deliver. It is the last large
area gain visible on the roadmap.</p>
<p>Two ways to build it. <b>Monolithic</b> grows both tiers in one continuous flow:
fewer steps, perfect alignment, but everything the top tier needs must survive the thermal
budget of the bottom one, and the aspect ratios are extreme. <b>Sequential</b> builds the
bottom tier, bonds a second wafer on top, and builds the upper tier there: the thermal
budgets are decoupled and each tier can be optimised for its own polarity, at the cost of
wafer bonding, overlay accuracy between tiers, and a much longer flow.</p>

<h4>What it costs</h4>
<p><b>Power has to come from the back.</b> Nothing reaches the bottom tier from above once
the top tier is over it, so CFET arrives coupled to backside power delivery — a buried
rail network on the reverse of the wafer, reached through nano through-silicon vias. That
is a large independent change to the process, and it is why backside power is appearing
one generation <i>before</i> CFET rather than with it.</p>
<p><b>Contacting the bottom tier.</b> The middle-of-line has to reach down past the upper
device without shorting to it, through a tier isolation layer, in the same footprint.</p>
<p><b>Everything else.</b> Yield on a flow this long, test access to a buried device,
thermal paths out of a stacked structure, and an EDA and PDK ecosystem that assumes
devices live on a plane.</p>
""",
}
STORY["cmp"] = COMMON

def attach():
    G = json.load(open("devices.json"))
    for d in G["devices"]:
        k = d["key"].replace("show_", "").replace("inv_", "")
        arch = "cfet" if k.startswith("cfet") else k
        body = STORY.get(arch)
        d["story"] = (body + COMMON) if body and arch != "cmp" else (body or COMMON)
    json.dump(G, open("devices.json", "w"), separators=(",", ":"))
    return G

if __name__ == "__main__":
    G = attach()
    n = sum(1 for d in G["devices"] if d.get("story"))
    print(f"background attached to {n} of {len(G['devices'])} scenes")
    print("devices.json", os.path.getsize("devices.json") // 1024, "KB")
