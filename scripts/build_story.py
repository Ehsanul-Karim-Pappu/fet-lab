"""Reviewed background. Reference IDs resolve in data/references.json."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data/devices.json"

COMMON = """
<h4>How to read these models</h4>
<p>These architectures show one possible scaling roadmap. Not every manufacturer has to
follow it, or follow it in this order. [R1, R2, R3]</p>
<p>Moving from FinFET to gate-all-around (GAA) improves gate control and gives more freedom
in sizing. Forksheet and CFET also change how the complementary pair (one nFET and one pFET)
fits into a cell. [R1, R2, R3]</p>
<p>These are teaching structures. They are not a foundry process or an electrical simulation.
Dimensions describe the drawn boxes, in nanometres.</p>
<p>Layout mode simplifies the layer stack and the vertical dimensions (not to scale). It is not
a mask layout or a fabrication flow.</p>
<p>The rail-to-rail span is measured along z, the direction commonly called standard-cell
height. Equal spans do not mean equal drive current, delay or routability. [R10, R12]</p>
<h4>Materials and electrical limits</h4>
<p>Each Device and Inverter scene takes its materials from one patent example, wherever the
patent names them:</p>
<ul>
<li>Nanosheet: a W gate fill, SiN self-aligned-contact caps and SiBCN spacers. [R13]</li>
<li>FinFET: a Co gate fill under an AlOx hard mask. [R29]</li>
<li>Forksheet: a SiN wall. [R31, R35]</li>
<li>CFET: SiBCN between the tiers. [R33]</li>
</ul>
<p>Where a patent leaves a choice open, the model picks one, and the part's name says so.
The Si/Si nanosheet design keeps an illustrative Mo gate fill. [R11]</p>
<p>The work-function metal, which sets the threshold voltage, differs by polarity. pFETs get
TiN, a typical p-type work-function metal. nFETs get an Al-containing n-type metal (in
practice, TiAl or TiAlC over thin TiN). Ti-based silicides replaced NiSi at FinFET-era nodes (general background).
Work-function tuning, doping and strain are not simulated. [R7, R8, R9, R11]</p>
<p>Layout colors mark roles (Channel, MD, Po, VD, VG and Metal 0), not chemical compositions.
The sequential CFET's bonding layers are drawn as SiO2, one of the options its patent lists.
[R3, R12, R34]</p>
<p>Capacitance values are estimates from the geometry alone. They leave out 3D fringe fields,
quantum and depletion corrections to gate capacitance, and calibrated junction behavior.
Unfilled gaps are treated as vacuum, not as a realistic inter-layer dielectric.</p>
<p>Both the absolute values and the architecture ratios depend on these assumptions. A zero
can mean that a coupling is missing from the drawn geometry, not that it is missing from a
real device.</p>
<p>The technical references and the patents followed are listed in About (Android) and below
the web viewer. They support the concepts and the materials, not the numerical accuracy of
this model.</p>
"""
STORY = {
"fin": """
<h4>From a planar channel to a fin</h4>
<p>A thin fin lets the gate control more of a short channel than a flat (planar) top gate
can. [R1]</p>
<p>This model is a tri-gate FinFET: the gate covers the top and both sidewalls of each fin.
Not every FinFET made in the past used exactly this shape. [R1]</p>
<h4>Materials and geometry solve different problems</h4>
<p>A high-k dielectric can be physically thicker than an ultrathin SiO2 film and still couple
the gate just as strongly, with less direct tunnelling. [R7]</p>
<p>Intel introduced hafnium-based high-k/metal gates at 45nm in 2007. [R7]</p>
<p>Fin geometry addresses short-channel electrostatics. Neither change removes all
leakage. [R7]</p>
<h4>Why move beyond fins?</h4>
<p>Effective width changes only in whole-fin steps, because the design adds or removes fins.
Taller fins also add width, but bring fabrication and capacitance trade-offs. [R1]</p>
<p>Nanosheets offer another way to adjust width and gated perimeter. FinFETs are still used in
production technologies. [R1]</p>
<p>In this model, the effective width of one fin is twice the exposed height plus the top
width. It is a geometric measure, not a prediction of drive current. Bottom isolation, doping
and strain differ among real technologies.</p>
""",
"ns": """
<h4>Gate-all-around nanosheets</h4>
<p>A nanosheet FET uses thin semiconductor sheets that lie flat, one above the other. The gate
stack wraps all the way around each sheet. [R1]</p>
<p>Stacking sheets adds gated perimeter without taking more floor area. Sheet width can be
changed without adding a whole fin, within design rules and manufacturing limits. [R1]</p>
<p>Gate-all-around (GAA) also covers other channel shapes, such as nanowires. [R1]</p>
<h4>What the process requires</h4>
<p>A common Si nanosheet flow grows alternating Si and SiGe layers. It then selectively
removes the SiGe, which is only a sacrificial (temporary) layer. [R1, R9]</p>
<p>Inner spacers separate the gate metal from the source/drain regions. [R1, R9]</p>
<p>Channel release (removing the SiGe), epitaxy, isolation and gate fill must be optimized
together. This model is not a process sequence. [R1, R9]</p>
<h4>Trade-offs, not automatic gains</h4>
<p>Better gate control can help lower the supply voltage. But contacts, capacitance, strain
and heat removal also matter. More sheets do not automatically make a faster cell.</p>
<p>Samsung announced initial 3nm GAA production in June 2022. That does not tie every
nanosheet technology to that node. [R6]</p>
<p>Device and Inverter show three sheets per device. Layout deliberately shows two
representative sheets, with simplified vertical spacing (not to scale). It is not a
layer-for-layer copy of those technical scenes.</p>
""",
"fs": """
<h4>Bringing complementary devices closer</h4>
<p>In an inner-wall forksheet, the nFET and pFET stacks sit against either side of a
dielectric wall. This reduces the space needed between them. [R1, R2]</p>
<p>The Device follows imec's forksheet patent: [R31]</p>
<ul>
<li>a silicon-nitride wall between the stacks;</li>
<li>one gate fill running over the wall;</li>
<li>a contact partition wall on top of it, which keeps the two devices' source/drain contacts
apart.</li>
</ul>
<p>The 8 nm wall is an illustrative dimension, not a universal recipe. [R1, R2, R31, R32]</p>
<h4>What changes at the channel?</h4>
<p>The sheet face that touches the wall has no gate metal on it. So each sheet is gated on
three faces, not four. [R1]</p>
<p>Electrostatics, stress and parasitics therefore differ from a fully wrapped sheet. Any
benefit must be judged at comparable performance and design rules, not from footprint
alone. [R1]</p>
<h4>Joining the two gates</h4>
<p>The Inverter is the Device wired up. In both, the one gate fill over the wall is already
the inverter's input. [R31]</p>
<p>A TSMC forksheet patent joins the gates another way. There, the wall rises level with the
gates and splits them, and a gate bridge contact on the wall touches both. That variant is
not drawn. [R35]</p>
<h4>Not the only forksheet design</h4>
<p>Imec's later outer-wall design puts the wall at the cell boundary instead, and addresses
limitations of the earlier design. It is not modeled here. [R2]</p>
<p>Forksheet is a researched scaling option. It is not a required production step for every
manufacturer. [R2]</p>
""",
"cfet": """
<h4>A complementary pair, stacked vertically</h4>
<p>A CFET stacks the nFET and the pFET on top of each other instead of side by side.
[R3]</p>
<p>Contacts, routing, isolation and thermal constraints limit the area benefit. There is no
universal 2x density gain. [R3, R4]</p>
<p>Following the patents, these Device and Inverter scenes put the pFET in the lower tier and
the nFET above it. Other tier orders exist. [R33, R34]</p>
<p>"Complementary" refers to the n/p pair, not to a particular gate connection: CFET options
include a common gate for both tiers and split gates. [R5]</p>
<h4>Monolithic and sequential integration</h4>
<p>Monolithic integration forms both tiers from one stack, in one shared process flow. It
needs demanding vertical patterning and selective processing. [R3]</p>
<p>The monolithic Device follows an IBM patent. SiBCN fills the gap between the tiers, and one
W gate fill surrounds both. [R3, R33]</p>
<p>Sequential integration builds the lower devices first. A new semiconductor layer is then
bonded on top, and the upper tier is made in it. That later processing must protect the
finished lower tier. [R3]</p>
<p>The sequential Device follows a TSMC patent: [R3, R34]</p>
<ul>
<li>each tier has its own gate;</li>
<li>an inter-metal line joins the drains;</li>
<li>deep plugs reach lines on the back of the wafer.</li>
</ul>
<h4>Contacting the lower device</h4>
<p>The monolithic Device and the Inverter contact both tiers from the front. As in the IBM
patent, the lower source is reached through a space left beside the upper one. [R33]</p>
<p>imec has demonstrated stacked contacts patterned from the frontside. [R4]</p>
<p>The sequential Device reaches its lower tier from the back of the wafer. [R34] The Layout
puts both power rails there too, which is imec's direction for CFET. [R4, R12]</p>
<p>Backside contacts can reduce congestion, but they are not a physical requirement that
defines CFET. [R4]</p>
<p>Two sheets per tier and the contact metals are model choices. The rendering does not
predict fabrication yield, self-heating or switching delay.</p>
"""
}

def attach():
    data = json.loads(DATA.read_text())
    for d in data["devices"]:
        key = d["key"].replace("show_", "").replace("inv_", "").split("~")[0]
        arch = "cfet" if key.startswith("cfet") else key
        d["story"] = STORY.get(arch, "") + COMMON
    DATA.write_text(json.dumps(data, separators=(",", ":")))
    sections = ["# Device background\n\nGenerated from scripts/build_story.py. See TECHNICAL_REFERENCES.md.\n"]
    for key, body in {**STORY, "model scope": COMMON}.items():
        sections.append("\n## " + key + "\n\n" + re.sub(r"<[^>]+>", "", body).strip() + "\n")
    (ROOT / "docs/BACKGROUND.md").write_text("\n".join(sections))
    return data

if __name__ == "__main__":
    print("Reviewed background attached to", len(attach()["devices"]), "scenes")
