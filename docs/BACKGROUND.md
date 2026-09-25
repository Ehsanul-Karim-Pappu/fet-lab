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
sheets with exaggerated vertical spacing, not a layer-for-layer copy of those technical scenes.


## fs

Bringing complementary devices closer
The classic inner-wall forksheet puts adjacent nFET and pFET stacks against a dielectric wall,
reducing the separation needed for gate integration. This model uses an 8nm silicon-nitride
wall; that is an illustrative dimension, not a universal recipe. [R1, R2]
What changes at the channel?
The wall-facing surface is not wrapped by gate metal here, leaving three gated faces.
Electrostatics, stress and parasitics differ from a fully wrapped sheet. Benefits must be
evaluated at comparable performance and design rules, not inferred from footprint alone. [R1]
Not the only forksheet design
Imec's later outer-wall design places the wall differently and addresses limitations of the
earlier design. It is not modeled here. Forksheet is a researched scaling option, not a
mandatory production step for every manufacturer. [R2]


## cfet

A complementary pair, stacked vertically
CFET stacks nFET and pFET instead of placing them side by side. Contacts, routing, isolation
and thermal constraints limit the resulting area benefit: there is no universal 2x density
gain. This model places pFET above nFET; other tier orders exist. Complementary refers to the
n/p pair, not a particular gate connection. [R3, R4]
Monolithic and sequential integration
Monolithic integration forms both tiers in a shared process flow, with demanding vertical
patterning and selective processing. Sequential integration forms the lower devices, transfers
a semiconductor layer using bonding, and processes the upper tier. Post-transfer processing
must protect the lower tier; thermal limits are process-dependent. [R3]
Our monolithic example uses continuous gate fill. The sequential example connects separate
gate conductors with a via to form an inverter input. Common-gate and split-gate CFET options
exist: the integration name alone does not specify the circuit. [R5]
Contacting the lower device
This model uses backside GND to ease lower-tier access. Frontside contacts are possible too:
imec demonstrated stacked contacts patterned from the frontside. Backside contacting can
reduce congestion, but is not a physical requirement defining CFET. [R4]
Two sheets per tier, the material palette and middle-tier isolation are model choices.
The rendering does not predict fabrication yield, self-heating or switching delay.


## model scope

How to read these models
These device architectures illustrate one possible scaling roadmap, not a required sequence
for every manufacturer. FinFET-to-GAA scaling improves gate control and sizing flexibility;
forksheet and CFET also address how complementary devices fit into a cell. [R1, R2, R3]
These are educational structures, not a foundry process or an electrical simulation.
Dimensions describe the drawn boxes in nanometres. Layout mode simplifies the layer stack and
exaggerates vertical spacing; it is not a mask layout or fabrication flow. Rail-to-rail span is
measured along z, a direction commonly called standard-cell height. Equal spans do not imply
equal drive current, delay or routability. [R10, R12]
Materials and electrical limits
Si, SiGe, SiO2, HfO2, Si3N4, TiN and an n-type work-function metal represent semiconductor,
dielectric and gate-stack materials. The work-function metal differs by polarity: TiN, a typical
p-type work-function metal, is drawn for pFETs, and nFETs get an Al-containing n-type metal (TiAl
or TiAlC over thin TiN, in practice). The Mo gate fill and the TiSix, Co and W contacts are an
illustrative palette, not a verified recipe for any node; Ti-based silicides replaced NiSi at
FinFET-era nodes. Real stacks depend on process and polarity. Work-function tuning, doping and strain
are not simulated. [R7, R8, R9, R11]
Layout colors identify Channel, MD, Po, VD, VG and Metal 0 roles rather than chemical
compositions. Middle-tier isolation has no specified chemistry here. SiO2 is an illustrative
bonding dielectric. [R3, R12]
Capacitance values are geometry-only estimates. They omit 3D fringe fields, quantum and
depletion corrections to gate capacitance, and calibrated junction behavior. Unfilled gaps
are treated as vacuum rather than realistic inter-layer dielectric. Both absolute values and
architecture ratios depend on these assumptions. Zero can mean that a coupling is absent from
the drawn geometry, not absent from a real device.
Technical references [R1–R12] are available in About (Android) and below the web viewer.
They support the concepts, not the numerical accuracy of this model.
