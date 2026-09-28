# Device background

Generated from scripts/build_story.py. See TECHNICAL_REFERENCES.md.


## fin

From a planar channel to a fin
A thin fin lets the gate control more of a short channel than a planar top gate.
This model is a tri-gate FinFET: the top and two sidewalls are gated. Historical FinFET
implementations need not all use this exact geometry. [R1]
Materials and geometry solve different problems
A physically thicker high-k dielectric can provide strong capacitive coupling with less
direct tunnelling than an equally capacitive ultrathin SiO2 film. Intel introduced hafnium-based
high-k/metal gates at 45nm in 2007. Fin geometry addresses short-channel electrostatics;
neither change eliminates all leakage. [R7]
Why move beyond fins?
Fin count changes effective width in discrete steps. Taller fins also increase width but
introduce fabrication and capacitance trade-offs. Nanosheets offer another way to adjust width
and gated perimeter. FinFETs remain useful in production technologies. [R1]
Here, effective width per fin is twice the exposed height plus the top width.
It is a geometric measure, not a drive-current prediction. Bottom isolation, doping and strain
differ among real technologies.


## ns

Gate-all-around nanosheets
A nanosheet FET uses thin horizontal semiconductor sheets surrounded by the gate stack.
Stacking sheets increases gated perimeter per lateral footprint. Sheet width can be adjusted
without adding a whole fin, subject to design rules and manufacturing limits. GAA also
includes other channel shapes, such as nanowires. [R1]
What the process requires
A common Si nanosheet flow grows alternating Si/SiGe layers and selectively removes the
sacrificial SiGe. Inner spacers separate gate metal from source/drain regions. Release,
epitaxy, isolation and gate fill must be co-optimized; this model is not a process sequence.
[R1, R9]
Trade-offs, not automatic gains
Better control can help voltage scaling, but contacts, capacitance, strain and heat removal
also matter. More sheets do not automatically make a faster cell. Samsung announced initial
3nm GAA production in June 2022; this does not assign every nanosheet technology to that node. [R6]
Device and Inverter show three sheets per device. Layout deliberately shows two representative
sheets with simplified vertical spacing (not to scale), not a layer-for-layer copy of those technical scenes.


## fs

Bringing complementary devices closer
The inner-wall forksheet puts adjacent nFET and pFET stacks against a dielectric wall,
reducing the separation needed between them. The Device follows imec's forksheet patent: a
silicon-nitride wall between the stacks, one gate fill running over the wall, and a contact
partition wall on it that keeps the two devices' source/drain contacts apart. The 8 nm wall is
an illustrative dimension, not a universal recipe. [R1, R2, R31, R32]
What changes at the channel?
The wall-facing surface is not wrapped by gate metal, leaving three gated faces.
Electrostatics, stress and parasitics differ from a fully wrapped sheet. Benefits must be
evaluated at comparable performance and design rules, not inferred from footprint alone. [R1]
Joining the two gates
In the Device and the Inverter, which is the Device wired up, the one gate fill over the wall
is already the inverter's input. A TSMC forksheet patent joins the gates another way: the wall
rises level with the gates, splitting them, and a gate bridge contact on the wall touches both.
That variant is not drawn. [R31, R35]
Not the only forksheet design
Imec's later outer-wall design places the wall at the cell boundary instead, and addresses
limitations of the earlier design. It is not modeled here. Forksheet is a researched scaling
option, not a mandatory production step for every manufacturer. [R2]


## cfet

A complementary pair, stacked vertically
CFET stacks nFET and pFET instead of placing them side by side. Contacts, routing, isolation
and thermal constraints limit the resulting area benefit: there is no universal 2x density
gain. Following the patents, these Device and Inverter scenes put the pFET in the lower tier and
the nFET above it; other tier orders exist. Complementary refers to the n/p pair, not a particular
gate connection. [R3, R4, R33, R34]
Monolithic and sequential integration
Monolithic integration forms both tiers from one stack in a shared process flow, with
demanding vertical patterning and selective processing. The monolithic Device follows an IBM
patent: SiBCN fills the gap between the tiers, and one W gate fill surrounds both. [R3, R33]
Sequential integration forms the lower devices, bonds a new semiconductor layer above them
and then processes the upper tier; post-transfer processing must protect the lower tier. The
sequential Device follows a TSMC patent: each tier has its own gate, an inter-metal line joins
the drains, and deep plugs reach lines on the back of the wafer. [R3, R34]
Contacting the lower device
The monolithic Device and the Inverter contact both tiers from the front: the lower source is
reached through a space left beside the upper one, as in the IBM patent. imec has demonstrated
stacked contacts patterned from the frontside. The sequential Device reaches its lower tier from
the back of the wafer, and the Layout puts both power rails there, imec's direction for CFET;
backside contacting can reduce congestion, but is not a physical requirement defining CFET.
[R4, R12, R33, R34]
Two sheets per tier and the contact metals are model choices. The rendering does not predict
fabrication yield, self-heating or switching delay.


## model scope

How to read these models
These device architectures illustrate one possible scaling roadmap, not a required sequence
for every manufacturer. FinFET-to-GAA scaling improves gate control and sizing flexibility;
forksheet and CFET also address how complementary devices fit into a cell. [R1, R2, R3]
These are educational structures, not a foundry process or an electrical simulation.
Dimensions describe the drawn boxes in nanometres. Layout mode simplifies the layer stack and
simplifies vertical dimensions (not to scale); it is not a mask layout or fabrication flow. Rail-to-rail span is
measured along z, a direction commonly called standard-cell height. Equal spans do not imply
equal drive current, delay or routability. [R10, R12]
Materials and electrical limits
Each Device and Inverter scene follows one patent example for its materials where the patent
names them: a W gate fill, SiN self-aligned-contact caps and SiBCN spacers on the nanosheet [R13],
a Co gate fill under an AlOx hard mask on the FinFET [R29], a SiN wall on the forksheet [R31, R35]
and SiBCN between the CFET tiers [R33]. Where a patent leaves a choice open, the model picks one
and the part's name says so; the Si/Si nanosheet design keeps an illustrative Mo gate fill. The
work-function metal differs by polarity: TiN, a typical p-type work-function metal, is drawn for
pFETs, and nFETs get an Al-containing n-type metal (TiAl or TiAlC over thin TiN, in practice).
Ti-based silicides replaced NiSi at FinFET-era nodes. Work-function tuning, doping and strain are
not simulated. [R7, R8, R9, R11]
Layout colors identify Channel, MD, Po, VD, VG and Metal 0 roles rather than chemical
compositions. The sequential CFET's bonding layers are drawn as SiO2, one of the options its patent lists. [R3, R12, R34]
Capacitance values are geometry-only estimates. They omit 3D fringe fields, quantum and
depletion corrections to gate capacitance, and calibrated junction behavior. Unfilled gaps
are treated as vacuum rather than realistic inter-layer dielectric. Both absolute values and
architecture ratios depend on these assumptions. Zero can mean that a coupling is absent from
the drawn geometry, not absent from a real device.
Technical references and the patents followed are listed in About (Android) and below the
web viewer. They support the concepts and the materials, not the numerical accuracy of this
model.
