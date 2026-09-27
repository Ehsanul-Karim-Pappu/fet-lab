"""The Process mode's "Why" tab: for each lesson, why its steps come in the order they do and
what each stage is for. Device, Inverter and Layout keep their own Story. Every claim here is
one the lesson's own steps make, with the same references."""

NS_COMMON = """
<h4>One crystal, two materials</h4>
<p>The flow starts by growing Si and SiGe layers in turn, as one crystal, on the wafer. Two
facts make that stack useful: the layers can be etched selectively, one kept while the other is
removed, and their Ge contents can differ, so even two SiGe layers etch differently. The patent's
stack has a SiGe base layer of about 50 % Ge and 25 %-Ge SiGe between the Si layers. [R13, R14]</p>
<h4>Why a dummy gate first</h4>
<p>The gate is made last. A placeholder, the dummy gate, holds its place while the spacers, the
source/drain epitaxy and the interlayer dielectric are formed around it. It is then pulled out
and the real gate stack goes into the trench it leaves. [R13]</p>
<h4>Inner spacers: keeping the gate off the source and drain</h4>
<p>Where the layers between the sheets are later replaced by gate metal, that metal would touch
the source/drain epitaxy. The layers are therefore indented sideways from the recess walls first,
and the pockets are filled with dielectric: the inner spacers. They separate the gate from the
source and drain at every sheet. [R13]</p>
<h4>Release, then wrap</h4>
<p>With the dummy gate gone, a selective etch removes the sacrificial layers inside the gate
trench. The sheets stay, held at their ends by the source and drain. An interfacial oxide, a
high-κ film and the work-function metal then go all round each sheet, and W fills the rest. [R13, R14]</p>
<h4>The cap that makes contacts self-aligned</h4>
<p>The W is recessed and capped with SiN: the self-aligned-contact (SAC) cap. The source/drain
contact trenches can then be etched right beside the gate, and the cap keeps them from shorting
to it. [R13]</p>
"""

WHY = {
"ns": """
<h4>What this lesson follows</h4>
<p>The nFET of a single-stack, dual-channel nanosheet CMOS patent. One Si/SiGe stack serves both
devices: Si sheets for the nFET, SiGe sheets for the pFET. The nFET also gets bottom dielectric
isolation. [R13]</p>
<h4>Bottom dielectric isolation</h4>
<p>The 50 %-Ge base layer etches faster than the 25 %-Ge SiGe, so it can be removed alone from
under the nFET's stack, with the pFET sealed off. The spacer film then fills the cavity it
leaves: a dielectric under the sheets, which cuts the nFET's path to the substrate below.
[R13, R15]</p>
""" + NS_COMMON,
"ns_p": """
<h4>What this lesson follows</h4>
<p>The pFET of the same single-stack patent. The stack is the nFET's, grown once for both, but
here the roles swap: the 25 %-Ge SiGe layers become the channels, and the Si layers and the
SiGe base are the ones removed. [R13]</p>
<h4>Why the pFET keeps its base layer until late</h4>
<p>The pFET region is sealed while the nFET's base layer comes out, so the pFET gets no bottom
dielectric isolation. It relies on an n-type punch-through stopper under it instead. Its
source/drain grows from both the SiGe sheet ends and the recessed silicon below, as boron-doped
SiGe; the title's strained pFET refers to this pairing of SiGe channels and SiGe source/drain.
No strain is calculated here. [R13]</p>
<h4>Indent in reverse</h4>
<p>Because the channels are SiGe here, the pFET's indent recesses the Si layers and the base
layer and leaves the SiGe ends in place: the reverse of the nFET's. [R13]</p>
""" + NS_COMMON,
"ns_pair": """
<h4>Two devices, one flow</h4>
<p>The nFET and the pFET are made side by side from one stack, on one gate line. Most steps treat
both at once. Where they differ, one region is covered by a liner or a mask while the other is
processed. The masked side does not change during those steps, so the order of the masks
matters. [R13]</p>
<h4>Why the pFET's source/drain comes first</h4>
<p>The patent etches the spacer film back over one region at a time. The pFET is opened, recessed
and grown first, with the nFET still under its unetched film. Then the nFET is opened and gets
its own recess, indent, inner spacers and epitaxy under a protective liner. [R13]</p>
<h4>Cut or shared</h4>
<p>At the end the gate line either stays whole, one input for an inverter, or is cut between the
devices and filled, so each gets its own gate. The cut and the SAC caps are filled in one
deposition. The two endings are alternatives, not one after the other. [R13, R16]</p>
""",
"fin": """
<h4>What this lesson follows</h4>
<p>A bulk FinFET nFET, gate last, following a TSMC patent stage by stage. Its fins are printed by
self-aligned quadruple patterning, after a GlobalFoundries patent. [R29, R30]</p>
<h4>Fins cut from the wafer</h4>
<p>In a bulk FinFET the fins are etched from the wafer itself, so the channel is the same crystal
as the substrate. Oxide fills the trenches and is recessed until the fins stand above it. Wells
are implanted one region at a time, through a mask. [R29]</p>
<h4>Two sets of spacers</h4>
<p>Thin seal spacers go on the dummy gate first, for the light source/drain implants. Dummy
spacers are then added in one region at a time, to set where that region's fins are recessed and
regrown as SiP. They are removed afterwards, and the lasting SiN gate spacers take their place.
[R29]</p>
<h4>Gate last, under a hard mask</h4>
<p>A dummy ILD is polished down to the dummy gates, and the dummy gates are pulled out. The
high-κ and the gate metal (an Al-containing layer and a Co fill) go into the trench. The gate is
then recessed and capped with a hard mask, AlOₓ here, which protects it through the contact
steps. [R29]</p>
<h4>Contacts where a dummy stood</h4>
<p>The contacts are not etched through the ILD. The dummy ILD is removed, and spin-on carbon
fills the space and is patterned so it stays only over the source/drain regions to be contacted.
The lasting ILD fills in around it, and the carbon is then removed. The contacts go where it
was, beside gates protected by their hard masks. [R29]</p>
""",
"fin_p": """
<h4>What this lesson follows</h4>
<p>The pFET of the same TSMC FinFET patent, made in the p-type region beside the nFET. Its
geometry is the nFET's; its materials and doping differ. [R29]</p>
<h4>What changes for the pFET</h4>
<p>The nFET region is masked while the pFET's fins are recessed and SiGeB is grown in the
recesses. On the silicon fin, the larger SiGe lattice squeezes the channel along its length:
compressive strain, which helps holes. The gate gets TiN as its work-function metal, formed with
the nFET masked. No strain is calculated here. [R29]</p>
<h4>What stays the same</h4>
<p>The wafer, the fins, the dummy gate, the gate-last sequence, the hard mask and the
spin-on-carbon replacement contacts are shared with the nFET: most steps are made on both
regions at once. [R29]</p>
""",
"fin_pair": """
<h4>Two regions, masked in turn</h4>
<p>The patent names two wafer regions, 50B for n-type devices and 50C for p-type ones. The fins,
the dummy gate and the seal spacers are made on both at once. The dummy spacers, the recess and
the epitaxy are done one region at a time: a mask covers the p-type region while the nFET gets
SiP, then the n-type region while the pFET gets SiGeB. [R29]</p>
<h4>One trench, two gates</h4>
<p>The dummy gate is removed along its whole length. Each region then gets its own gate materials
while the other is masked, and one Co fill runs across both. [R29]</p>
<h4>The gate cut here is teaching</h4>
<p>The FinFET patent does not describe a gate cut. The cut route is a teaching reconstruction,
placed before the hard mask so that the same deposition fills the cut. The shared-gate route is
the other ending. [R16]</p>
""",
"sadp": """
<h4>Why pattern with spacers</h4>
<p>One exposure cannot print lines as closely spaced as the stacks need. Self-aligned double
patterning prints cores at twice the final pitch and coats them with a conformal spacer film,
then etches the film back and removes the cores. Each core leaves two spacer lines, so the pitch
halves. The line width is set by the film's thickness, not by the exposure. [R16, R20, R21]</p>
<h4>Why a block mask after</h4>
<p>Spacer lines come in closed loops and in every position. A second, separately printed block
mask trims them to length and removes the ones the layout does not need. [R16, R19]</p>
<h4>How it ends</h4>
<p>The spacer image goes into the hard mask, and the lesson returns to the tile. The stack etch
that follows is the nanosheet flow's own, as in the patent's Fig. 5A/B. [R13]</p>
""",
"saqp": """
<h4>Doing it twice</h4>
<p>Self-aligned quadruple patterning repeats the spacer trick. The first spacer image is
transferred into a second core film, and a second spacer on those cores halves the pitch again:
sixteen lines from four printed cores, at a quarter of the printed pitch, from one exposure.
[R19, R20]</p>
<h4>What sets each dimension</h4>
<p>The first spacer's thickness sets the second cores' width, and the second spacer's thickness
sets the final line width. The spaces between lines come from three different origins, so an
error in any one film shows up as uneven spacing. The pitch-walk lesson follows that further.
[R20, R22]</p>
<h4>The block mask</h4>
<p>As with SADP, a second exposure trims the lines to length and removes the edge lines, before
the stack etch that follows. [R16, R19]</p>
""",
"pitchwalk": """
<h4>Why the spaces can differ</h4>
<p>In SAQP each space between neighbouring lines has one of three origins: inside a second core,
where a first core was, or between the spacer pairs of neighbouring first cores. Each depends on
different dimensions. When all are on target, the spaces match. [R22]</p>
<h4>One dimension off at a time</h4>
<p>The lesson changes one input at a time: the first-core width, the first-spacer thickness or
the second-spacer thickness. It measures the spaces off the resulting lines. The difference
between the largest and the smallest space is the pitch walk. [R22, R20]</p>
<h4>What it leaves out</h4>
<p>Walls here are vertical and every etch copies its mask exactly. Real cores can taper, so
spacers lean and the transferred widths depend on the etch. That is why in-line metrology
tracks these dimensions. [R20]</p>
""",
"ns~si": """
<h4>What this lesson follows</h4>
<p>A Si/Si nanosheet CMOS route from a patent application. Both devices have Si channels and
both get bottom dielectric isolation; only the source/drain differs, SiGe:B for the pFET and an
n-doped epitaxy for the nFET. [R28]</p>
<h4>An undoped layer under the source/drain</h4>
<p>After the recess, undoped Si grows from the seed layer and the sheet ends before the Ge-rich
bottom layer is removed. The cavity under the stacks is then filled with dielectric, so the later
source/drain grows on the undoped Si, over the bottom isolation. [R28]</p>
<h4>One release for both</h4>
<p>With Si channels in both devices, one selective etch removes the lower-Ge SiGe in both at
once. Each device then gets its own work-function metal under a mask, and one gate fill makes
the shared input. [R28]</p>
""",
}
