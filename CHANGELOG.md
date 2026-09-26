# Changelog

All notable changes to FET Lab. Dates are the release date; versions follow
[semantic versioning](https://semver.org).

## Unreleased

### Nanosheet channel designs: Si/SiGe CMOS and Si/Si CMOS

The nanosheet scenes used to mix two different transistors: Device and Inverter showed Si
channels in both devices, while Process built the patent's SiGe-channel pFET. There are now two
named CMOS designs, and the app never switches between them silently.

- **Channel design selector.** A pill at the top of the stage on every nanosheet scene, with
  **Si/SiGe CMOS** and **Si/Si CMOS**. The choice is shared by Device, Inverter and Process, is
  kept across tabs, views, sections and lessons, and is saved. It starts on Si/SiGe, the design
  the Process lesson follows. The header's subtitle names the design too.
- **Si/SiGe CMOS**, the patent-based example (US 12,568,683 B2):
  - One alternating stack makes both devices: three Si nFET sheets and three SiGe pFET sheets,
    staggered half a pitch apart rather than level.
  - Bottom dielectric isolation is under the nFET only. The pFET's SiGe:B source/drain also
    grows from its recessed sub-fin.
  - Each device has its own work-function metal on one shared gate, with no gate cut.
  - These are the Process flows' own finished nFET and pFET, so the Process lesson's
    shared-gate ending is exactly the Device scene. A test checks this part for part.
- **Si/Si CMOS**, the full-bottom-isolation example (IBM application US 2023/0178617 A1,
  "Nanosheet epitaxy with full bottom isolation", Figs. 2–52, new reference R28):
  - Si sheets in both devices, at the same heights, on a Si seed layer, with bottom dielectric
    isolation under both where a Ge-rich sacrificial layer was.
  - An undoped Si growth region in each source/drain opening, under a SiGe:B (pFET) or SiC:P
    (nFET) source/drain; its own TiN pFET work-function metal.
  - **Its own 23-step fabrication lesson**, opened by the Process chip when Si/Si is chosen:
    - stack and lines, STI, sacrificial gates and spacers;
    - the source/drain recess to the seed, SiGe indent, inner spacers and undoped Si growth;
    - the Ge-rich layer removed and replaced by bottom isolation under both devices;
    - the pFET source/drain with the nFET protected, then the nFET's with the pFET protected;
    - ILD, gate removal, channel release in both devices, gate dielectric, separate
      work-function metals and the gate fill;
    - contacts, then inverter wiring as the lesson's educational completion.
    - Its last two frames are the Si/Si Device and Inverter scenes, part for part (tested).
    - None of the Si/SiGe route's isolation or channel-release steps are reused.
  - Choosing a design on a nanosheet Process scene opens that design's lesson.
- **Device mode** now shows the nanosheet as an nFET + pFET pair on a shared gate, like the
  forksheet and CFET. **Inverter mode** wires the same pair: IN on the shared gate, V_DD to the
  pFET source, V_SS to the nFET source, both drains to OUT (four nets, tested).
- **Exploded gate view** (Device and Inverter): a switch on the stage that enlarges the gaps
  between sheets and the gate films so each film can be seen and tapped. It is marked
  "Schematic enlargement; dimensions are not to scale". Materials, labels, sheet order and
  connections are identical with it on and off; capacitance estimates use the compact
  geometry only.
- **Dimensions stated honestly:**
  - The specs give sheet thickness, clear gap and vertical pitch, with pitch defined as
    thickness plus gap.
  - The 7 nm values are the model's illustrative choices, not the patent's.
  - No text claims how real gaps are filled.
- **Patterning lessons:** the SADP and SAQP lessons now say they pattern the stack lines and do
  not decide whether a pFET's channels are Si or SiGe.
- **Process lesson label:** the nanosheet lesson's Steps tab is headed "Si/SiGe CMOS ·
  Patent-based example: US 12,568,683 B2".
- **Web and PWA:** the web viewer lists both designs, in the exploded view.

### Audit of every scene: geometry and text fixes

A measured audit of all 16 scenes and 9 process flows (connectivity, overlaps, film fits,
callouts against geometry, text against geometry) found these, now fixed:

- **CFET (Device mode, both):** the bottom nFET's source and drain vias landed on one
  backside metal plate, shorting its source to its drain. The backside now has a GND line
  under the source and a separate drain line.
- **CFET inverter:** the output riser stopped 2 nm short of the drains, so the nMOS drain
  was floating and the circuit was not an inverter. The riser now contacts both drains.
- **Forksheet (Device and Inverter):** the source/drain epitaxy sat on bare substrate under
  a wall that stopped 10 nm above it, so the n and p source/drain faced each other with
  nothing between them. Bottom isolation now runs under the source/drain too, and the wall
  separates them all the way down. The forksheet's junction term is now 0, as the
  nanosheet's is. Its "t_TiN" callout measured the nFET's n-type metal and is now t_WFM.
- **Nanosheet inverter:** its source/drain also sat on bare substrate; it now sits on the
  bottom isolation, as in Device mode.
- **FinFET inverter:** the "Along the channel" view cut between the fins; it now cuts
  through one.
- **Layout scenes:**
  - The gate had a foot through the field oxide that touched the wells, shorting the P and
    N wells through the gate; it is gone.
  - The forksheet's gate never crossed the wall, so its n and p gates were joined only by
    that foot. The wall now stops below the gate, which bridges it.
  - The CFET's IN bar sat on the cell edge; it is now inside the cell.
  - The nanosheet cell uses the Inverter scene's 22 nm sheets that its span comes from.
  - The FinFET layout has its Metal 0 row.
  - The rail-to-rail row says it is measured rail centre to rail centre (the Inverter
    scenes measure to the rails' outer edges).
  - "Vertical dimensions exaggerated" now reads "simplified, not to scale": the fins and
    sheet spacing are compressed, not enlarged.
- **Both sites (FinFET and nanosheet):** after the dummy gate was pulled, the gate trench
  between the two sites was drawn full of oxide, and so was the etched gate-cut slot. Both
  are now open, as the text says.
- **Nanosheet contacts:** the ILD stopped at the gate cap, so the contacts stood as free
  pillars. It now rises around them, so they fill holes in it.
- **Region labels:** the FinFET pFET flow showed "pFET · protected" on its own SiGe:B
  epitaxy, and its copied masking steps showed the wrong regions; each step now shows its
  own state. The single-site flows no longer claim a gate cut they don't draw, and their
  branch texts now point to the pFET and Both sites flows.
- **Texts:**
  - The pitch-walk lesson's thicker-second-spacer case says which spaces shrink (the
    spaces between second cores, by twice the change) and which doesn't (the space inside
    a second core).
  - The forksheet inverter's note says the TiN gate cap bridges the wall.
  - The compare scene says "cell height" instead of "cell width".
  - The cell outline has its own marker material, instead of the forksheet wall's.
  - The nanosheet flow's finished-device text gives Device mode's real differences
    (5 nm sheets, a 21 nm pitch, thicker films).
- **Enlarged spacing now noted everywhere it's drawn:** the forksheet, CFET and inverter
  notes say their sheets are drawn about 20 nm apart so each film shows, where real stacks
  are 7–12 nm apart. The Process tile notes that its 84 nm stack pitch is enlarged.

### Nanosheet Process stack: realistic for both devices

The Process nanosheet flows (nFET, pFET and Both sites) used Device mode's stack: 5 nm Si
sheets 21 nm apart, so 16 nm of SiGe between them. The pFET keeps those SiGe layers as its
channels, so its sheets came out 12–16 nm thick, about three times a real sheet, and nothing
said so. The shared stack is now 7 nm Si and 7 nm SiGe, so both devices' sheets are 7 nm. The
gate films are 0.5 nm SiO₂, 1.5 nm HfO₂ and 1.5 nm work-function metal on each sheet for both
devices, and they fill each 7 nm gap between sheets with no fill metal, as in real stacks. The
pFET no longer needs thinner films than the nFET. The superlattice, gate-stack and
finished-device steps say what the stack is, and why it differs from Device mode. Device
mode's nanosheet is unchanged, with its sheets spaced out so each film shows; its note now
points to Process mode's tighter stack. A new test checks that every layer of the shared stack
is channel-thin in every step.

The legacy web nanosheet page's note now names the n-type work-function metal (not TiN),
counts ten materials, and says real sheets sit 7–12 nm apart with the work-function metal
filling the gap, instead of calling the model's enlarged spacing "the real scaling wall".

### Learning path and Process mode structure

- **Learn in order.** Help opens with a suggested path: FinFET → nanosheet → forksheet → CFET →
  Process. Each entry opens that scene.
- **Glossary.** Help has a searchable glossary of the terms the steps use: BDI, CESL, CMP, CPP,
  EOT, epitaxy, FEOL/MOL/BEOL, gate cut, high-κ/HKMG, IL, ILD, inner spacer, mandrel, PTS,
  pitch walk, channel release, RMG, SADP/SAQP, silicide, STI, WFM and W_eff. Each step in the
  Steps tab shows the terms it uses as chips; tap one to read its definition in place.
- **Process tour.** A second guided tour, started from Help, walks through the step navigator,
  the badge and its explanation, the site selector and section planes on the nanosheet flow.
- **Site selector on the stage.** In Process mode an nFET · pFET · Both sites pill sits at the
  top of the 3D view, so switching sites no longer needs the Steps tab. The Steps tab's
  selector stays.
- **Process chips reordered:** FinFET and Nanosheet first, then the SADP, SAQP and Pitch walk
  lessons under a "Lessons" label, then Forksheet and CFET, still marked "soon".
- **Stepper label:** "STEP 6/18 · OP 5" instead of "OPERATION 6.5 / 18": it says which core
  step the operation leads into, and is shorter than before, so the stepper never grows
  taller over the model. TalkBack reads "Step 6 of 18, operation 5".
- **One badge vocabulary.** Every flow's match descriptions now use the same four words as
  the badges: Source stage, Reconstruction, Teaching and Concept. The FinFET's finished device
  is a Source stage (R24, Fig. 21A), as the nanosheet's is.
- **Open in Device mode.** The finished-device step has a button that opens the same
  technology in Device mode.
- **Material key.** The Layers tab has a collapsible key of the materials in the scene; tap a
  material to read its note.
- The web and PWA pages say that Process mode is in the Android app.

### More content notes from the app review

- **Cell height.** The inverter and Layout compare notes give imec's roadmap values for scale:
  about 115 nm for A14 nanosheets, 98 nm for A10 forksheets and under 80 nm for A7 CFETs.
- **EOT and the interfacial layer.** The EOT row is labelled as the drawn films' value, and the
  nanosheet note says the 1 nm interfacial layer is thicker than today's 0.5–0.8 nm, so the
  model's EOT is above the sub-1 nm EOT of advanced-node gate stacks.
- **Tile gate pitch.** The Process tile notes give the tile's gate pitch (about 73 nm for the
  nanosheet, 76 nm for the FinFET) against a real contacted gate pitch of about 45–48 nm.
- The FinFET silicide step said nickel reacts to form TiSiₓ; it is titanium.

### Screen-reader support

TalkBack now has something to read throughout the Android app:
- The header's **i** and **?** buttons are named (About; Help, features and tour).
- The step navigator's back, play and next buttons are named, and its step number, badge and
  title are read as one item and announced when the step changes.
- The mode and tab bars are tabs with a selected state; chips, views and the IN 0/1 control
  announce which one is selected.
- The 3D view says what it shows and which part is selected.
- The controls sheet's handle says whether it is closed, half open or fully open.
- Sliders carry their names.
- The 2D section lists the materials it cuts, the locator explains itself, and the pitch-walk
  drawing gives its range of spaces.

The two smallest text sizes (9.5 sp captions in the section panel and the pitch-walk lesson)
are raised to 10.5 sp. Touch areas already reach 48 dp: Compose enlarges any control smaller
than that for touch, without changing the layout.

### Content corrections from the app review

- **Work-function metals by polarity.** nFETs now have an Al-containing n-type work-function
  metal (TiAl or TiAlC over thin TiN, in practice) and pFETs have TiN, the usual p-type metal.
  Every nFET used to be drawn with TiN, the reverse of common practice. This covers all device,
  inverter, compare and process scenes; the TiN gate cap is unchanged.
- **Contacts.** Source/drain contacts use a Ti-based silicide (TiSiₓ) and cobalt plugs instead of
  NiSi and nickel: Ti-based silicides replaced NiSi at FinFET-era nodes, and nickel is not a plug
  metal. The inverters' local interconnect is cobalt too. No capacitance value changed.
- **Example node labels** follow imec's roadmap: FinFET "3 nm-class", nanosheet "2 nm to A14",
  forksheet "A10" (imec's A10 forksheet is outer-wall; this model is inner-wall), CFET "A7 and
  beyond". The forksheet and CFET used to read "1.2 nm" and "1 nm".
- **Layout's Metal 0 row** is now "Drawn Metal 0 bar spacing", with a note that real M0 pitch is
  about 20–24 nm; the 35–45 nm values are the spacing of four schematic bars, not a track pitch.
- **Nanosheet note:** the 21 nm sheet pitch is enlarged so every film is visible; real sheets are
  about 7–12 nm apart, and the work-function metal fills the gap between them with no fill metal.
- The exported GLB/OBJ/STL models are regenerated (the FinFET's were older than its S/D recess).

### Process mode: pFETs, both sites, and the gate cut

Each process technology now has a **site selector** at the top of the Steps tab: **nFET**
(the flow as it was), **pFET**, and **Both sites**. Every step says what each region is doing
at that point: processed, masked, or not yet reached.

- **Nanosheet pFET**, in the order of the patent's text (US 12,568,683 B2): an n-type
  stopper; the high-Ge base kept while the nFET's is removed (bottom dielectric isolation is
  nFET-only); with the nFET masked, a recess through the base into the implanted sub-fin;
  the Si layers and base indented and inner spacers formed, so the lower-Ge SiGe stays as the
  channels; Si:B then SiGe:B epitaxy from the SiGe ends and the sub-fin, with a note on
  compressive strain; after the shared ILD and dummy removal, the base and Si removed from its
  gate with the nFET masked; its own high-κ and p-type work-function metal; contacts. The
  shared stack's 5 nm Si gaps are narrow for a pFET gate, so its films are drawn thinner, and
  the step says so.
- **FinFET pFET**: the nFET's geometry with an n-well, SiGe:B source/drain grown with the nFET
  masked, and a separate p-type work-function metal.
- The pFET flows reuse the nFET flows' tile and field operations, including the direct,
  SADP and SAQP routes, state for state.
- **Both sites** puts the two flows' own models side by side, one stack pitch apart, joined by
  their gate line, with each region mask drawn. It ends in two **alternative** routes, never
  one after the other: a **gate cut** (resist, exposure, opening, an etch through the gate
  fill, dielectric fill: two gates, two gate contacts) or a **shared gate** (one gate, one
  contact, as an inverter's input needs; the patent's Fig. 19 arrangement). Tests check that
  the cut leaves no conductive path and cuts no sheet, fin or source/drain, and that the shared
  gate stays connected.

### Process mode: section planes and figure comparison

The Section tab lists named **section planes** for the flow on screen, with a top-down
locator showing where the plane runs, which side is seen and the axes (along the channel,
across neighbouring fins or stacks, vertical). **3D**, **Section** and **Both** show the 3D
cut, a flat 2D section drawn from the same model state, or the two together; tapping a
material in the section selects it in 3D too. The nanosheet planes follow the patent's
X1–X1, X2–X2, Y1–Y1 and Y2–Y2 directions as its text describes them. The FinFET planes are
the app's own and are not labelled as the patent's A, B or C lines: its Fig. 1, which
defines them, is an outstanding visual check.

Steps that cite a figure show **Compare with the source**: the source and figure, what its
text describes, what the model cuts in that plane, and what is left out or different. Every
mapping is marked **text-verified**, meaning the drawing has not been compared; the audit lists
them one by one so each can be upgraded separately.

The stepper's step number and badge now wrap onto their own line when space is short, rather
than crowding the controls, and each badge's meaning is shown with the step's source (tap the
step title).

### Process mode: SAQP pitch walk

A **Pitch walk** chip: the FinFET's SAQP fin patterning with the first-core width and the two
spacer thicknesses let go. Sixteen lines are built from those three numbers; every space is
measured off the built lines, typed by where it came from (inside a second core, where a
first core was, between first-core spacer pairs), and reported with the largest, the smallest
and **pitch walk = largest − smallest**. Three sliders, constrained so no space closes, redraw
the cross-sections and a plan strip. The ideal case is checked to match the FinFET flow's own
lines, and that flow stays ideal. Taper, etch bias and fin-height effects are described, not
simulated, and the dimensions are illustrative (the paper's example is 96 → 48 → 24 nm).

### Process mode: the FinFET

The FinFET chip in Process mode now has a flow: 15 steps from the bare wafer to the finished
device, gate last, following the stages of one disclosed FinFET route (US 10,505,021 B2)
where it describes them, each step naming its own source and figure (source-described,
artwork not compared). Fins are cut from the wafer through a hard mask on a 2 × 2 tile of an
nFET pair in a p-well and a pFET pair in an n-well, shown as context only; the trenches are
filled, polished and recessed (57 nm etched, 45 nm exposed above the STI). Gate lithography
has its own states (resist, exposure, hard-mask etch, dummy-gate etch). Then gate spacers,
by a conventional deposition and etch-back that the audit marks as differing from the
patent's selective spacers; a **source/drain fin recess** with the channel kept whole under
the gate; Si:P epitaxy grown from the recess; an etch-stop layer, ILD and CMP; dummy-gate
removal; the interfacial layer and HfO₂; the TiN work-function metal, Mo fill and cap; a
second ILD with separate source/drain and gate openings; silicide; and the contact fill.

Fin patterning defaults to **SAQP**, following a published N7 fin-patterning example
(96 → 48 → 24 nm; this model's 108 → 54 → 27 nm is an adaptation); SADP and a hypothetical
single-exposure direct print stay selectable, and the spacer routes' cut removes the extra
mask line between the two fin groups before the fin etch. The hard mask is deposited at the
tile before the routes part, and the zoom-outs are continuous: stepping from the site to the
tile, or from the tile to the fin field, the wafer and its films spread out from the old
view's size to the new one while the camera pulls back, and only then do the step's new films
(the hard mask, the resist, the mandrel and core films) deposit, each rising from its bottom
face in turn. The nanosheet works the same way: its hard mask is now one step at the tile
before the routes part, its blanket multilayer, hard mask and resist span the whole tile,
and its patterning route defaults to **SADP** (a teaching choice; the sources do not say
the stack is patterned that way). The SADP and SAQP chips start from that hard-mask step.

Every patterning step now shows its lithography the way the gate exposure does: a resist
coat, then an exposure with the reticle's chrome drawn above the wafer (not to scale) over
unexposed and exposed resist, then development. That covers the SADP and SAQP core
lithography and their cut and block masks in both flows, the nanosheet's gate patterning
and nFET-open block mask, and the FinFET's contact openings, whose dark-field reticle is
open only over the three contacts. These resist steps are labelled as lithography concepts
[R16], not as figures of the sources.

The stepper now carries a badge for each state: **Source stage** (in the accent colour) for a
stage its source describes, or **Reconstruction**, **Teaching** or **Concept**, so the
difference is visible at every step, not only in the Steps tab. The tile's steps and the
flows' notes say plainly that the 2 × 2 tile is context: only the selected nFET is carried to
a finished device, and without the gate cut, which is not drawn, each gate line would be
shared by an nFET and a pFET site. The SADP and SAQP lessons now say the nanosheet flow
defaults to SADP. Sub-fin leakage, wells' doping,
the pFET's own steps and the gate cut are named where they are left out. The route picker
remembers a choice per flow, uses each flow's wording, and each step shows which reference
its figures belong to. Five FinFET references are added (R24–R27, and R22 now points at the
SAQP paper's authors' copy).

### FinFET model: source/drain grown from a recess

To match its fabrication steps, the FinFET model's fins are now recessed outside the spacers
and the Si:P source/drain grows from the recess, instead of cladding a full-height fin. The
gate-to-epitaxy estimate changes from 17.61 aF to 15.79 aF (total gate parasitic 31.24 aF,
35% of C_ox); no other value changed. See the [audit](docs/CONTENT_AUDIT.md).

## 1.3.0 — 2026-09-24

Process mode: how a nanosheet FET is made, step by step, with a choice of how its stack
lines are printed and SADP and SAQP lessons of their own. Process mode is in the Android
app; the web version follows.

### Process mode: how the transistor is made

A fourth mode, Process, steps through a representative fabrication flow as real
geometry, starting with the nanosheet: 18 steps following the nFET branch of one
disclosed integration route, from the punch-through-stopper implant and the Si/SiGe
multilayer through the dummy gate, bottom dielectric isolation (the conformal spacer
deposition that fills the cavity, then its etch-back), inner spacers, source/drain epitaxy,
channel release and the high-κ/metal gate to middle-of-line contacts. Each step names the
source figures it corresponds to and how closely (published stage, intermediate teaching
reconstruction or concept only), the model's material substitutions and what it leaves
out; none claims to reproduce a drawing. [docs/PROCESS_AUDIT.md](docs/PROCESS_AUDIT.md),
generated from the same data, audits every step.

Operation substeps (on by default, one switch in the Steps tab) zoom out to a 2 × 2 tile,
two stack lines (nFET and pFET) crossed by two gate lines, to show how the pattern is made:
hard mask, resist coat, exposure through the reticle (positive tone, drawn above the wafer
and not to scale), development, hard-mask etch, resist strip, stack etch, STI fill, CMP and
recess; then dummy-gate patterning across both lines; then the protective liner and the
mask that keeps the pFET sealed while the nFET's base layer is removed. The flow then zooms
back to the selected site, which the build checks against the tile. Removed material
fades out where it was instead of vanishing. Every tool works on every
step: orbit, section, hide layers, tap to identify. A stepper on the stage moves back and
forward or plays the flow, parts a step adds or reshapes glow briefly, and the Steps tab
lists every step with its explanation, the flow's scope and the sources it cites. FinFET,
forksheet and CFET flows are shown as coming. The flow is a teaching sequence with
illustrative materials, not a foundry recipe.

The Steps tab can switch how the stack hard mask is patterned: **Direct print** (the
default), **SADP** or **SAQP**, from a picker in the step list where the routes part, between
step 3 and operation 4.1. The spacer routes replace operations 4.1–4.6 with their own
steps on the field of lines around the tile, a patterning concept applied to an illustrative
layer. SADP prints four cores at twice the final pitch, coats them with a conformal spacer,
etches it back and removes the cores, leaving eight lines at P/2. SAQP starts from cores at
four times the pitch, transfers the first spacer image into a second set of cores (shown as
its own step) and repeats, leaving sixteen lines at P/4 from one exposure. The spacer image
goes into the hard mask, a cut pattern trims it, and the flow zooms back to the tile, where
the build checks that the hard mask holds the same two lines as the direct route, so all
three continue with the same stack etch. Each route numbers its own operations. Patterning
spacers are a pale grey distinct from the transistor's gate spacers, and the cores have
their own colours. P, P/2 and P/4 are ideal; pitch walk is described, not modelled. Nothing
claims that this stack is patterned by SADP or SAQP. Each spacer route also has a Process
chip of its own, **SADP** and **SAQP**: the same steps, generated from the route, taken out
of the flow and ending with the stack etch.

Long scene names in the header shrink to fit on one line instead of being cut off. The
feature list under Help describes Process mode and its Steps tab.

The renderer's depth range now fits the scene on screen, which removes a sawtooth along
thin layers' edges when zoomed far out.

### Nanosheet model: full bottom dielectric isolation

The nanosheet now sits on a full bottom dielectric isolation (BDI) layer under both the
channel and the source/drain, on a short Si sub-fin that carries a p-type punch-through
stopper, with STI along the stack recessed to the BDI's bottom and the gate and spacers
reaching down beside it. The BDI is the spacer dielectric, since one conformal deposition
forms both in the route followed. That is one consistent
isolation scheme for the fabrication steps being added. Its source/drain epitaxy no longer
touches the substrate, so the Specs table's C_j* proxy, which counts only a direct
S/D-to-substrate junction, is now 0 aF for the nanosheet, as it already was for the FinFET.
Zero junction contribution in this proxy does not mean zero total parasitic capacitance.
No other value changed; see the [audit](docs/CONTENT_AUDIT.md).

## 1.2.0 — 2026-09-23

A guided tour and a full-size model on phones. Scenes now remember how you left them,
and the app follows the system's light or dark setting.

### Guided tour and feature list

A first-launch tour walks through the app in eight steps: modes, architectures, the 3D
view's gestures, then the Views, Section, Layers, Specs and Story tabs. A spotlight moves
from section to section and an animated hand really does each thing: it switches
architecture, orbits and pinches the model, drags a section cut and the sheet's
see-through, scrolls down to Spacers and turns them off and on, and scrolls to the
capacitance table and highlights a row. Every step changes something from what is on
screen, and the tour puts the scene, camera, layers and sheet back as they were when it
ends. Replay it from ? › Help & features, which also lists every feature and jumps
straight to it.

### Full-size stage on phones

The control sheet floats over the model instead of shrinking it, and can be dragged
between peek, open and expanded heights.

### Layers tab

Every layer group has its own Hide / Show switch, and a master switch hides or shows the
whole scene. Layers are listed two to a row on phones, with names wrapping to two lines.

### Scenes remember where you left them

Switching architecture or mode and coming back now finds each scene as you left it: the
camera and cuts, the view, hidden layers, layer separation, the picked layer and the
highlighted capacitance. Display switches still apply to every scene. Memory lasts for
the session; Reset this scene still returns a scene to its defaults.

### See-through control sheet

On phones the control sheet is a little more see-through by default, and Section ›
Display has a Sheet see-through slider (0–60%) to set how much of the model shows through
it. The setting is kept between launches, and the guided tour's Section step shows it.

### Follows the system theme

The stage background now follows the system's light or dark setting, so the Light
background switch is gone, and so is the Material You colours switch. Dimension callouts
start off; turn them on under Section › Display.

### Consistent view order

Device scenes now use the same view sequence for every architecture: 3D overview, Along
channel, Across channel, then the architecture-specific view. CFET no longer opens in
section, and the nanosheet view names no longer carry figure letters.

### Technology stays put when you change view

Switching between Device, Inverter and Layout used to drop you back on FinFET. It now
keeps the architecture you were looking at: Device › Forksheet to Inverter opens the
forksheet inverter, on to Layout opens the forksheet cell. Compare carries across the
same way, and a CFET left on Sequential comes back as Sequential rather than Monolithic.
Only the viewing mode changes.

### Content and capacitance audit

Reviewed architecture, materials and integration descriptions against primary sources.
Added a shared reference catalog to web/PWA and Android About; exact dimensions and the
complete material palette are explicitly illustrative. Corrected CFET gate/contact
options, inverter sizing language, layout axis labels, and privacy/local-storage wording.
The former perspective preset named Isometric is now accurately called 3D overview.

Capacitance estimates are geometry-only educational approximations, not measured or
TCAD-validated values. Fixed oxide film thickness extraction, integrated dielectric
layers in series across each gap, and excluded channel/body area from the source/drain
junction-area proxy. Removed claims that architecture ratios or a monotonic ranking
are validated. A zero junction proxy does not mean a real device has zero junction
capacitance. Added analytic and grid-convergence tests. See
[the audit](docs/CONTENT_AUDIT.md) for assumptions and before/after values.

### Fixed

- Separating the layers far enough cut the outer ones off: the section plane that stood
  for "no cut" sat at the model's edge, so exploded layers past it were clipped.
- On Inverter and Layout scenes the IN 0/1 switch covered the selected layer's card.

## 1.1.0 — 2026-09-13

The layout figures are now drawn to scale, and the numbers the app prints are checked
against the geometry on every build.

### Layout figures redrawn to scale

Everything in the plane of the wafer now comes from the device cross-sections, so one
nanometre means the same thing in the Device, Inverter and Layout scenes.

- Gate drawn at its physical length (18 nm FinFET, 15 nm elsewhere) instead of 14 nm;
  MD drawn at the contacted length of 22 nm instead of 14 nm. The MD-to-gate ratio was
  1.00 as drawn where it should have been 1.22.
- Metal 0 on one uniform track pitch with the rails on the cell boundary. The tracks
  previously sat at three different pitches — 15, 29 and 22 nm — in the same cell.
- Each cell at its real rail-to-rail width: 156 / 136 / 106 / 74 nm. The Layout compare
  scene had drawn FinFET, nanosheet and forksheet all at 116 nm — identical — while
  telling the reader to watch the cell narrow. It now agrees with the Inverter compare.
- MD columns run the full cell height, rail edge to rail edge, and are cut only where the
  net changes. At a cut each piece overhangs its channel by 3 nm rather than sitting flush
  with the end of the channel it contacts.
- Wells, field oxide and gate extend under the far edge of the rail, because a rail
  straddles the cell boundary and is shared with the row above or below.

### Fixed

- **Forksheet output was not connected.** The dielectric wall splits the drain contact in
  two, and the n-side via went nowhere — the OUT track runs on the p side of the wall. A
  transverse Metal 0 jog over the drain now ties the two halves together.
- **Dimension callouts on Android** were dropped onto the geometry with no leader line and
  no reference to what they measured, and piled on top of each other. They now sit at their
  own label point, draw the measured span and a leader to it, and are spaced apart. The
  collision code had been estimating each chip as one line of body text when it is two
  lines of mono inside a padded surface — about half the real height.
- **Layer names on top faces** ran vertically. The axis is now chosen by how the name comes
  out on screen rather than by which in-plane axis is longer.
- **EOT callout** printed 1.35 nm against an arrow spanning the 3 nm physical stack. It now
  reads `t_ox = 3 nm` with `1 SiO₂ + 2 HfO₂ · EOT 1.35 nm` beneath, and on the FinFET the
  arrow no longer runs diagonally across a corner.
- FinFET `W_eff` row said "2H+W per fin" against a value covering both fins.
- Section views framed the cell by its largest extent, which ignored perspective and let
  deep cells overflow the frame by up to 150 px. Framing now solves each bounding-box
  corner exactly, and the aspect correction is no longer defeated by the framing cap.
- Reset restored a light background on layout scenes, against the dark default.
- `build_devices.py`, `build_geometry.py` and `export_meshes.py` wrote to hardcoded
  `/home/claude/...` paths, so the documented "regenerate the geometry" steps could not
  work from a clone.

### Added

- **Slow rotate** toggle on Android, under Section → Display.
- `scripts/build_web.py` — assembles `roadmap.html` and `pwa/index.html` from the template
  and bumps the service-worker cache, a step that had been manual.
- `scripts/verify.py` now checks every callout's printed value against the length of the
  span it draws, and the declared gate length against the high-κ film that defines it.
- `scripts/ktcheck.py` now catches Compose state used above its own declaration — the
  error that broke the previous Android build.

## 1.0.0 — 2026-09-13

First stable build: web viewer, installable PWA and Android app all working from one
geometry file. Sixteen scenes — six device, five inverter, five layout — across FinFET,
nanosheet, forksheet and CFET.
