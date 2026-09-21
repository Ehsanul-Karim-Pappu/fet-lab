"""Reviewed background. Reference IDs resolve in data/references.json."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data/devices.json"

COMMON = """
<h4>How to read these models</h4>
<p>These device architectures illustrate one possible scaling roadmap, not a required sequence
for every manufacturer. FinFET-to-GAA scaling improves gate control and sizing flexibility;
forksheet and CFET also address how complementary devices fit into a cell. [R1, R2, R3]</p>
<p>These are educational structures, not a foundry process or an electrical simulation.
Dimensions describe the drawn boxes in nanometres. Layout mode simplifies the layer stack and
exaggerates vertical spacing; it is not a mask layout or fabrication flow. Rail-to-rail span is
measured along z, a direction commonly called standard-cell height. Equal spans do not imply
equal drive current, delay or routability. [R10, R12]</p>
<h4>Materials and electrical limits</h4>
<p>Si, SiGe, SiO2, HfO2, Si3N4 and TiN represent semiconductor, dielectric and gate-stack
materials. The complete Mo/Ni/W/NiSi gate and contact palette is illustrative, not a verified
recipe for any node. Real stacks depend on process and polarity. TiN is a conductor: nFET/pFET
work-function labels do not mean n-doped/p-doped TiN. Work-function tuning, doping and strain
are not simulated. [R7, R8, R9, R11]</p>
<p>Layout colors identify Channel, MD, Po, VD, VG and Metal 0 roles rather than chemical
compositions. Middle-tier isolation has no specified chemistry here. SiO2 is an illustrative
bonding dielectric. [R3, R12]</p>
<p>Capacitance values are geometry-only estimates. They omit 3D fringe fields, quantum and
depletion corrections to gate capacitance, and calibrated junction behavior. Unfilled gaps
are treated as vacuum rather than realistic inter-layer dielectric. Both absolute values and
architecture ratios depend on these assumptions. Zero can mean that a coupling is absent from
the drawn geometry, not absent from a real device.</p>
<p>Technical references [R1–R12] are available in About (Android) and below the web viewer.
They support the concepts, not the numerical accuracy of this model.</p>
"""
STORY = {
"fin": """
<h4>From a planar channel to a fin</h4>
<p>A thin fin lets the gate control more of a short channel than a planar top gate.
This model is a tri-gate FinFET: the top and two sidewalls are gated. Historical FinFET
implementations need not all use this exact geometry. [R1]</p>
<h4>Materials and geometry solve different problems</h4>
<p>A physically thicker high-k dielectric can provide strong capacitive coupling with less
direct tunnelling than an equally capacitive ultrathin SiO2 film. Intel introduced hafnium-based
high-k/metal gates at 45nm in 2007. Fin geometry addresses short-channel electrostatics;
neither change eliminates all leakage. [R7]</p>
<h4>Why move beyond fins?</h4>
<p>Fin count changes effective width in discrete steps. Taller fins also increase width but
introduce fabrication and capacitance trade-offs. Nanosheets offer another way to adjust width
and gated perimeter. FinFETs remain useful in production technologies. [R1]</p>
<p>Here, effective width per fin is twice the exposed height plus the top width.
It is a geometric measure, not a drive-current prediction. Bottom isolation, doping and strain
differ among real technologies.</p>
""",
"ns": """
<h4>Gate-all-around nanosheets</h4>
<p>A nanosheet FET uses thin horizontal semiconductor sheets surrounded by the gate stack.
Stacking sheets increases gated perimeter per lateral footprint. Sheet width can be adjusted
without adding a whole fin, subject to design rules and manufacturing limits. GAA also
includes other channel shapes, such as nanowires. [R1]</p>
<h4>What the process requires</h4>
<p>A common Si nanosheet flow grows alternating Si/SiGe layers and selectively removes the
sacrificial SiGe. Inner spacers separate gate metal from source/drain regions. Release,
epitaxy, isolation and gate fill must be co-optimized; this model is not a process sequence.
[R1, R9]</p>
<h4>Trade-offs, not automatic gains</h4>
<p>Better control can help voltage scaling, but contacts, capacitance, strain and heat removal
also matter. More sheets do not automatically make a faster cell. Samsung announced initial
3nm GAA production in June 2022; this does not assign every nanosheet technology to that node. [R6]</p>
<p>Device and Inverter show three sheets per device. Layout deliberately shows two representative
sheets with exaggerated vertical spacing, not a layer-for-layer copy of those technical scenes.</p>
""",
"fs": """
<h4>Bringing complementary devices closer</h4>
<p>The classic inner-wall forksheet puts adjacent nFET and pFET stacks against a dielectric wall,
reducing the separation needed for gate integration. This model uses an 8nm silicon-nitride
wall; that is an illustrative dimension, not a universal recipe. [R1, R2]</p>
<h4>What changes at the channel?</h4>
<p>The wall-facing surface is not wrapped by gate metal here, leaving three gated faces.
Electrostatics, stress and parasitics differ from a fully wrapped sheet. Benefits must be
evaluated at comparable performance and design rules, not inferred from footprint alone. [R1]</p>
<h4>Not the only forksheet design</h4>
<p>Imec's later outer-wall design places the wall differently and addresses limitations of the
earlier design. It is not modeled here. Forksheet is a researched scaling option, not a
mandatory production step for every manufacturer. [R2]</p>
""",
"cfet": """
<h4>A complementary pair, stacked vertically</h4>
<p>CFET stacks nFET and pFET instead of placing them side by side. Contacts, routing, isolation
and thermal constraints limit the resulting area benefit: there is no universal 2x density
gain. This model places pFET above nFET; other tier orders exist. Complementary refers to the
n/p pair, not a particular gate connection. [R3, R4]</p>
<h4>Monolithic and sequential integration</h4>
<p>Monolithic integration forms both tiers in a shared process flow, with demanding vertical
patterning and selective processing. Sequential integration forms the lower devices, transfers
a semiconductor layer using bonding, and processes the upper tier. Post-transfer processing
must protect the lower tier; thermal limits are process-dependent. [R3]</p>
<p>Our monolithic example uses continuous gate fill. The sequential example connects separate
gate conductors with a via to form an inverter input. Common-gate and split-gate CFET options
exist: the integration name alone does not specify the circuit. [R5]</p>
<h4>Contacting the lower device</h4>
<p>This model uses backside GND to ease lower-tier access. Frontside contacts are possible too:
imec demonstrated stacked contacts patterned from the frontside. Backside contacting can
reduce congestion, but is not a physical requirement defining CFET. [R4]</p>
<p>Two sheets per tier, the material palette and middle-tier isolation are model choices.
The rendering does not predict fabrication yield, self-heating or switching delay.</p>
"""
}

def attach():
    data = json.loads(DATA.read_text())
    for d in data["devices"]:
        key = d["key"].replace("show_", "").replace("inv_", "")
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
