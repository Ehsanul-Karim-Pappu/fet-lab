"""The Process mode's "Why" tab: for each lesson, why its steps come in the order they do and
what each stage is for. Device, Inverter and Layout keep their own Story. Every claim here is
one the lesson's own steps make, with the same references."""

NS_COMMON = """
<h4>One crystal, two materials</h4>
<p>The flow starts by growing Si and SiGe layers in turn on the wafer, as one crystal [R13].</p>
<p>Two facts make this stack useful. First, the layers can be etched selectively: one is
removed while the other stays [R14]. Second, their Ge contents can differ, so even two SiGe
layers etch differently [R13].</p>
<p>The patent's stack has a SiGe base layer of about 50 % Ge, with 25 %-Ge SiGe between the Si
layers [R13].</p>
<h4>Why a dummy gate first</h4>
<p>The gate is made last. A placeholder, the dummy gate, holds its place while the spacers, the
source/drain epitaxy (crystal grown for the source and drain) and the interlayer dielectric are
formed around it [R13].</p>
<p>The dummy gate is then pulled out. The real gate stack goes into the trench it leaves [R13].</p>
<h4>Inner spacers: keeping the gate off the source and drain</h4>
<p>The layers between the sheets are later replaced by gate metal. Left as it is, that metal
would touch the source/drain epitaxy [R13].</p>
<p>So the layers are first indented sideways from the recess walls, and the pockets are filled
with dielectric. These fillings are the inner spacers. They separate the gate from the source
and drain at every sheet [R13].</p>
<h4>Release, then wrap</h4>
<p>With the dummy gate gone, a selective etch removes the sacrificial layers inside the gate
trench [R13][R14]. The sheets stay, held at their ends by the source and drain [R13].</p>
<p>Then three films go all round each sheet: an interfacial oxide, a high-κ film (an insulator
with a higher permittivity than SiO₂) and the work-function metal. W fills the rest [R13].</p>
<h4>The cap that makes contacts self-aligned</h4>
<p>The W is recessed and capped with SiN. This is the self-aligned-contact (SAC) cap [R13].</p>
<p>With the cap in place, the source/drain contact trenches can be etched right beside the gate.
The cap keeps them from shorting to it [R13].</p>
"""

WHY = {
"ns": """
<h4>What this lesson follows</h4>
<p>The nFET of a single-stack, dual-channel nanosheet CMOS patent. One Si/SiGe stack serves both
devices: Si sheets for the nFET, SiGe sheets for the pFET. The nFET also gets bottom dielectric
isolation [R13].</p>
<h4>Bottom dielectric isolation</h4>
<p>The 50 %-Ge base layer etches faster than the 25 %-Ge SiGe. So it can be removed on its own
from under the nFET's stack, while the pFET is sealed off [R13].</p>
<p>The spacer film then fills the cavity it leaves. The result is a dielectric under the sheets.
It cuts the nFET's path to the substrate below [R13][R15].</p>
""" + NS_COMMON,
"ns_p": """
<h4>What this lesson follows</h4>
<p>The pFET of the same single-stack patent. The stack is the nFET's, grown once for both.</p>
<p>Here the roles swap. The 25 %-Ge SiGe layers become the channels, and the Si layers and the
SiGe base are the ones removed [R13].</p>
<h4>Why the pFET keeps its base layer until late</h4>
<p>The pFET region is sealed while the nFET's base layer comes out. So the pFET gets no bottom
dielectric isolation. It relies instead on an n-type punch-through stopper under it: a doped
region that blocks leakage below the channel [R13].</p>
<p>Its source/drain grows as boron-doped SiGe, from both the SiGe sheet ends and the recessed
silicon below [R13].</p>
<p>The patent's title calls the pFET strained. That refers to this pairing of SiGe channels and
SiGe source/drain [R13]. No strain is calculated here.</p>
<h4>Indent in reverse</h4>
<p>The channels are SiGe here. So the pFET's indent recesses the Si layers and the base layer,
and leaves the SiGe ends in place. This is the reverse of the nFET's indent [R13].</p>
""" + NS_COMMON,
"ns_pair": """
<h4>Two devices, one flow</h4>
<p>The nFET and the pFET are made side by side, from one stack, on one gate line. Most steps
treat both at once [R13].</p>
<p>Where they differ, a liner or a mask covers one region while the other is processed. The
covered side does not change during those steps, so the order of the masks matters [R13].</p>
<h4>Why the pFET's source/drain comes first</h4>
<p>The patent etches the spacer film back over one region at a time [R13].</p>
<p>The pFET goes first. It is opened, recessed and grown while the nFET stays under its unetched
film. Then the nFET is opened, with the pFET under a protective liner. The nFET gets its own
recess, indent, inner spacers and epitaxy [R13].</p>
<h4>Cut or shared</h4>
<p>At the end there are two possible endings. The gate line can stay whole, giving one input for
an inverter. Or it can be cut between the devices and filled, so each device gets its own gate.
The cut and the SAC caps are filled in one deposition. The two endings are alternatives, not one
after the other [R13][R16].</p>
""",
"fin": """
<h4>What this lesson follows</h4>
<p>A bulk FinFET nFET, following a TSMC patent stage by stage. It is made gate last: the real gate
goes in near the end [R29].</p>
<p>Its fins are printed by self-aligned quadruple patterning (SAQP), after a GlobalFoundries
patent [R30].</p>
<h4>Fins cut from the wafer</h4>
<p>In a bulk FinFET, the fins are etched from the wafer itself. So the channel is the same
crystal as the substrate [R29].</p>
<p>Oxide fills the trenches and is recessed until the fins stand above it. Wells are implanted
one region at a time, through a mask [R29].</p>
<h4>Two sets of spacers</h4>
<p>Thin seal spacers go on the dummy gate first, for the light source/drain implants [R29].</p>
<p>Dummy spacers are then added, one region at a time. They set where that region's fins are
recessed and regrown as SiP. Afterwards they are removed, and the lasting SiN gate spacers take
their place [R29].</p>
<p>The seal spacers go when the dummy gate is pulled. So the gate films lie directly on the SiN
spacers [R29].</p>
<h4>Gate last, under a hard mask</h4>
<p>A dummy interlayer dielectric (ILD) is polished down to the dummy gates. The dummy gates are
then pulled out [R29].</p>
<p>The high-κ and the gate metal (an Al-containing layer and a Co fill) go into the trench. They
line its floor and walls as well as the fins [R29].</p>
<p>The gate is then recessed and capped with a hard mask, AlOₓ here. The cap protects the gate
through the contact steps [R29].</p>
<h4>Contacts where a dummy stood</h4>
<p>The contacts are not etched through the ILD. Instead, the dummy ILD is removed and spin-on
carbon fills the space. The carbon is patterned so it stays only over the source/drain regions to
be contacted [R29].</p>
<p>The lasting ILD fills in around it, and the carbon is removed. The contacts go where it was,
beside gates protected by their hard masks [R29].</p>
""",
"fin_p": """
<h4>What this lesson follows</h4>
<p>The pFET of the same TSMC FinFET patent, made in the p-type region beside the nFET. Its
geometry is the nFET's; its materials and doping differ [R29].</p>
<h4>What changes for the pFET</h4>
<p>The nFET region is masked while the pFET's fins are recessed and SiGeB is grown in the
recesses [R29].</p>
<p>On the silicon fin, the larger SiGe lattice squeezes the channel along its length. This
compressive strain helps holes. That is general background, not the patent's, and no strain is
calculated here.</p>
<p>The gate gets TiN as its work-function metal, formed with the nFET masked [R29].</p>
<h4>What stays the same</h4>
<p>Most steps are made on both regions at once. The wafer, the fins, the dummy gate, the
gate-last sequence, the hard mask and the spin-on-carbon replacement contacts are shared with
the nFET [R29].</p>
""",
"fin_pair": """
<h4>Two regions, masked in turn</h4>
<p>The patent names two wafer regions: 50B for n-type devices and 50C for p-type ones. The fins,
the dummy gate and the seal spacers are made on both at once [R29].</p>
<p>The wells are implanted one region at a time, the N well first, as in the patent's example
[R29].</p>
<p>The dummy spacers, the recess and the epitaxy are also done one region at a time. A mask
covers the p-type region while the nFET gets SiP. Then a mask covers the n-type region while the
pFET gets SiGeB [R29].</p>
<h4>One trench, two gates</h4>
<p>The dummy gate is removed along its whole length. Each region then gets its own gate materials
while the other is masked [R29].</p>
<p>Here one Co fill runs across both. That is the model's choice: the patent lets the two
regions' electrodes be the same or different [R29].</p>
<h4>The gate cut here is teaching</h4>
<p>The FinFET patent does not describe a gate cut. The cut route is a teaching reconstruction. It
is placed before the hard mask, so that the same deposition fills the cut. The shared-gate route
is the other ending [R16].</p>
""",
"sadp": """
<h4>Why pattern with spacers</h4>
<p>One exposure cannot print lines as closely spaced as the stacks need. Self-aligned double
patterning (SADP) gets there with a spacer film instead [R16][R20][R21].</p>
<p>First, cores are printed at twice the final pitch. They are made like any printed pattern:
resist coating, exposure, development, then an etch into the core film [R16][R17].</p>
<p>A conformal spacer film (one of even thickness on tops, sidewalls and floor) then coats the
cores. The film is etched back and the cores are removed. Each core leaves two spacer lines, so
the pitch halves. The film's thickness, not the exposure, sets the line width
[R16][R20][R21].</p>
<h4>Why a block mask after</h4>
<p>Spacer lines come in closed loops and in every position. A second, separately printed block
mask trims them to length. It also removes the lines the layout does not need [R16][R19].</p>
<h4>How it ends</h4>
<p>The spacer image goes into the hard mask, and the lesson returns to the tile. The stack etch
that follows is the nanosheet flow's own, as in the patent's Fig. 5A/B [R13].</p>
""",
"saqp": """
<h4>Doing it twice</h4>
<p>Self-aligned quadruple patterning (SAQP) repeats the spacer trick. The first spacer image is
transferred into a second core film. A second spacer on those cores halves the pitch again. The
result is sixteen lines from four printed cores, at a quarter of the printed pitch, from one
exposure [R19][R20].</p>
<h4>What sets each dimension</h4>
<p>The first spacer's thickness sets the second cores' width. The second spacer's thickness sets
the final line width [R20][R22].</p>
<p>The spaces between lines come from three different origins. So an error in any one film shows
up as uneven spacing. The pitch-walk lesson follows that further [R20][R22].</p>
<h4>The block mask</h4>
<p>As with SADP, a second exposure trims the lines to length and removes the edge lines. This
comes before the stack etch that follows [R16][R19].</p>
""",
"pitchwalk": """
<h4>What goes wrong</h4>
<p>SAQP should give evenly spaced lines, like the teeth of a comb. Pitch walk is when it does
not: the gaps alternate wide and narrow. It is measured as the largest gap minus the smallest
[R22][R20].</p>
<h4>Why it happens</h4>
<p>SAQP coats printed cores twice, and the gaps between the lines come from three different
places. Blue gaps are the first coating itself. Orange gaps are where a printed core stood.
Green gaps lie between neighbouring cores [R22].</p>
<p>Each kind depends on different films. So when one film comes out a few nanometres off, only
its own kinds of gap change, and the gaps no longer match.</p>
<h4>Why it matters</h4>
<p>A wide gap etches differently from a narrow one, so uneven gaps can leave fins of different
height [R22]. In practice, SAQP for 7 nm-class FinFET fins needs tight control of the core
size to keep pitch walk acceptable [R23].</p>
<h4>What it leaves out</h4>
<p>The walls here are vertical, and every etch copies its mask exactly. Real cores can taper,
so the coatings lean and the transferred widths depend on the etch. That is why in-line
metrology tracks these sizes [R20].</p>
""",
"ns~si": """
<h4>What this lesson follows</h4>
<p>A Si/Si nanosheet CMOS route from a patent application. Both devices have Si channels, and
both get bottom dielectric isolation. Their source/drains differ: SiGe:B for the pFET, an
n-doped epitaxy for the nFET [R28].</p>
<h4>An undoped layer under the source/drain</h4>
<p>After the recess, undoped Si grows from the seed layer and the sheet ends. This happens before
the Ge-rich bottom layer is removed [R28].</p>
<p>The cavity under the stacks is then filled with dielectric. So the later source/drain grows on
the undoped Si, over the bottom isolation [R28].</p>
<h4>One release for both</h4>
<p>Both devices have Si channels. So one selective etch removes the lower-Ge SiGe in both at
once [R28].</p>
<p>Each device then gets its own work-function metal, and one gate fill makes the shared input
[R28]. How the two metals are patterned is the model's choice.</p>
""",
}
