# Device background

Generated from scripts/build_story.py. See TECHNICAL_REFERENCES.md.


## fin

From a planar channel to a fin
A thin fin lets the gate control more of a short channel than a flat (planar) top gate
can. [R1]
This model is a tri-gate FinFET: the gate covers the top and both sidewalls of each fin.
Not every FinFET made in the past used exactly this shape. [R1]
Materials and geometry solve different problems
A high-k dielectric can be physically thicker than an ultrathin SiO2 film and still couple
the gate just as strongly, with less direct tunnelling. [R7]
Intel introduced hafnium-based high-k/metal gates at 45nm in 2007. [R7]
Fin geometry addresses short-channel electrostatics. Neither change removes all
leakage. [R7]
Why move beyond fins?
Effective width changes only in whole-fin steps, because the design adds or removes fins.
Taller fins also add width, but bring fabrication and capacitance trade-offs. [R1]
Nanosheets offer another way to adjust width and gated perimeter. FinFETs are still used in
production technologies. [R1]
In this model, the effective width of one fin is twice the exposed height plus the top
width. It is a geometric measure, not a prediction of drive current. Bottom isolation, doping
and strain differ among real technologies.


## ns

Gate-all-around nanosheets
A nanosheet FET uses thin semiconductor sheets that lie flat, one above the other. The gate
stack wraps all the way around each sheet. [R1]
Stacking sheets adds gated perimeter without taking more floor area. Sheet width can be
changed without adding a whole fin, within design rules and manufacturing limits. [R1]
Gate-all-around (GAA) also covers other channel shapes, such as nanowires. [R1]
What the process requires
A common Si nanosheet flow grows alternating Si and SiGe layers. It then selectively
removes the SiGe, which is only a sacrificial (temporary) layer. [R1, R9]
Inner spacers separate the gate metal from the source/drain regions. [R1, R9]
Channel release (removing the SiGe), epitaxy, isolation and gate fill must be optimized
together. This model is not a process sequence. [R1, R9]
Trade-offs, not automatic gains
Better gate control can help lower the supply voltage. But contacts, capacitance, strain
and heat removal also matter. More sheets do not automatically make a faster cell.
Samsung announced initial 3nm GAA production in June 2022. That does not tie every
nanosheet technology to that node. [R6]
Device and Inverter show three sheets per device. Layout deliberately shows two
representative sheets, with simplified vertical spacing (not to scale). It is not a
layer-for-layer copy of those technical scenes.


## fs

Bringing complementary devices closer
In an inner-wall forksheet, the nFET and pFET stacks sit against either side of a
dielectric wall. This reduces the space needed between them. [R1, R2]
The Device follows imec's forksheet patent: [R31]

a silicon-nitride wall between the stacks;
one gate fill running over the wall;
a contact partition wall on top of it, which keeps the two devices' source/drain contacts
apart.

The 8 nm wall is an illustrative dimension, not a universal recipe. [R1, R2, R31, R32]
What changes at the channel?
The sheet face that touches the wall has no gate metal on it. So each sheet is gated on
three faces, not four. [R1]
Electrostatics, stress and parasitics therefore differ from a fully wrapped sheet. Any
benefit must be judged at comparable performance and design rules, not from footprint
alone. [R1]
Joining the two gates
The Inverter is the Device wired up. In both, the one gate fill over the wall is already
the inverter's input. [R31]
A TSMC forksheet patent joins the gates another way. There, the wall rises level with the
gates and splits them, and a gate bridge contact on the wall touches both. That variant is
not drawn. [R35]
Not the only forksheet design
Imec's later outer-wall design puts the wall at the cell boundary instead, and addresses
limitations of the earlier design. It is not modeled here. [R2]
Forksheet is a researched scaling option. It is not a required production step for every
manufacturer. [R2]


## cfet

A complementary pair, stacked vertically
A CFET stacks the nFET and the pFET on top of each other instead of side by side.
[R3]
Contacts, routing, isolation and thermal constraints limit the area benefit. There is no
universal 2x density gain. [R3, R4]
Following the patents, these Device and Inverter scenes put the pFET in the lower tier and
the nFET above it. Other tier orders exist. [R33, R34]
"Complementary" refers to the n/p pair, not to a particular gate connection: CFET options
include a common gate for both tiers and split gates. [R5]
Monolithic and sequential integration
Monolithic integration forms both tiers from one stack, in one shared process flow. It
needs demanding vertical patterning and selective processing. [R3]
The monolithic Device follows an IBM patent. SiBCN fills the gap between the tiers, and one
W gate fill surrounds both. [R3, R33]
Sequential integration builds the lower devices first. A new semiconductor layer is then
bonded on top, and the upper tier is made in it. That later processing must protect the
finished lower tier. [R3]
The sequential Device follows a TSMC patent: [R3, R34]

each tier has its own gate;
an inter-metal line joins the drains;
deep plugs reach lines on the back of the wafer.

Contacting the lower device
The monolithic Device and the Inverter contact both tiers from the front. As in the IBM
patent, the lower source is reached through a space left beside the upper one. [R33]
imec has demonstrated stacked contacts patterned from the frontside. [R4]
The sequential Device reaches its lower tier from the back of the wafer. [R34] The Layout
puts both power rails there too, which is imec's direction for CFET. [R4, R12]
Backside contacts can reduce congestion, but they are not a physical requirement that
defines CFET. [R4]
Two sheets per tier and the contact metals are model choices. The rendering does not
predict fabrication yield, self-heating or switching delay.


## model scope

How to read these models
These architectures show one possible scaling roadmap. Not every manufacturer has to
follow it, or follow it in this order. [R1, R2, R3]
Moving from FinFET to gate-all-around (GAA) improves gate control and gives more freedom
in sizing. Forksheet and CFET also change how the complementary pair (one nFET and one pFET)
fits into a cell. [R1, R2, R3]
These are teaching structures. They are not a foundry process or an electrical simulation.
Dimensions describe the drawn boxes, in nanometres.
Layout mode simplifies the layer stack and the vertical dimensions (not to scale). It is not
a mask layout or a fabrication flow.
The rail-to-rail span is measured along z, the direction commonly called standard-cell
height. Equal spans do not mean equal drive current, delay or routability. [R10, R12]
Materials and electrical limits
Each Device and Inverter scene takes its materials from one patent example, wherever the
patent names them:

Nanosheet: a W gate fill, SiN self-aligned-contact caps and SiBCN spacers. [R13]
FinFET: a Co gate fill under an AlOx hard mask. [R29]
Forksheet: a SiN wall. [R31, R35]
CFET: SiBCN between the tiers. [R33]

Where a patent leaves a choice open, the model picks one, and the part's name says so.
The Si/Si nanosheet design keeps an illustrative Mo gate fill. [R11]
The work-function metal, which sets the threshold voltage, differs by polarity. pFETs get
TiN, a typical p-type work-function metal. nFETs get an Al-containing n-type metal (in
practice, TiAl or TiAlC over thin TiN). Ti-based silicides replaced NiSi at FinFET-era nodes (general background).
Work-function tuning, doping and strain are not simulated. [R7, R8, R9, R11]
Layout colors mark roles (Channel, MD, Po, VD, VG and Metal 0), not chemical compositions.
The sequential CFET's bonding layers are drawn as SiO2, one of the options its patent lists.
[R3, R12, R34]
Capacitance values are estimates from the geometry alone. They leave out 3D fringe fields,
quantum and depletion corrections to gate capacitance, and calibrated junction behavior.
Unfilled gaps are treated as vacuum, not as a realistic inter-layer dielectric.
Both the absolute values and the architecture ratios depend on these assumptions. A zero
can mean that a coupling is missing from the drawn geometry, not that it is missing from a
real device.
The technical references and the patents followed are listed in About (Android) and below
the web viewer. They support the concepts and the materials, not the numerical accuracy of
this model.
