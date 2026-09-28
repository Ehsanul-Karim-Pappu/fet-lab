# Patent alignment

Each technology in FET Lab follows the patent named for it below. Scene models (Device, Inverter)
and process lessons use that patent's materials and step order.

Other steps are allowed when they are factual or have another reference, and each is badged as
such: operations such as resist coat and exposure, concepts, teaching steps and reconstructions.
Where a patent lists several materials for one layer, the model draws one of them and names it.
Where a patent names none, the model's choice is labelled as the model's.

The PDFs are in `docs/<technology>/`. Links carry no tracking parameters.

| Technology | Patent | Ref | PDF |
|---|---|---|---|
| FinFET: Device, Inverter, Process | TSMC, *FinFET structures and methods of forming the same*, US 9,812,358 B1 | R29 | `docs/finfet/FinFET_US9812358B1.pdf` |
| FinFET fins, SAQP | GlobalFoundries, *Methods for fabricating integrated circuits using self-aligned quadruple patterning*, US 9,171,764 B2 | R30 | `docs/finfet/FinFET_SAQP_US9171764B2.pdf` |
| Nanosheet, Si/SiGe CMOS: Device, Inverter, Process | IBM, *Single stack dual channel gate-all-around nanosheet with strained PFET and bottom dielectric isolation NFET*, US 2023/0420457 A1 (granted as US 12,568,683 B2) | R13 | `docs/nsfet/` (full text; all figures) |
| Forksheet: Device, Inverter | imec, *A method for forming a semiconductor device and a semiconductor device*, EP 3 989 273 A1 | R31 | `docs/fsfet/Forksheet_Imec_EP3989273A1.pdf` |
| Forksheet: gate-bridge variant (text only) | TSMC, *Semiconductor device structure including forksheet transistors and methods of forming the same*, US 2024/0178128 A1 | R35 | `docs/fsfet/Forksheet_TSMC_US20240178128A1.pdf` |
| Forksheet: second example | TSMC, *Semiconductor device structure including forksheet transistors and methods of forming the same*, US 11,862,700 B2 | R32 | `docs/fsfet/Forksheet_TSMC_US11862700B2.pdf` |
| Monolithic CFET: Device, Inverter | IBM, *Stacked complementary field effect transistors*, US 11,869,812 B2 | R33 | `docs/cfet/CFET_Monolithic_IBM_US11869812B2.pdf` |
| Sequential CFET: Device | TSMC, *CFETs and the methods of forming the same*, US 2024/0413156 A1 | R34 | `docs/cfet/CFET_Sequential_TSMC_US20240413156A1.pdf` |

Outside this set:
- The Si/Si CMOS nanosheet design follows IBM's US 2023/0178617 A1 (R28),
  `docs/nsfet/Nanosheet_SiSi_IBM_US20230178617A1.pdf` (see its section below).
- The TSMC sequential CFET patent's Chinese family member, CN 118712136 A, is in
  `docs/cfet/CN118712136A.pdf`: the same disclosure as R34, with a text layer.
- SADP has no patent in the set and keeps its published references (R16, R19–R21).
- The pitch-walk lesson varies the SAQP dimensions of R30's route and keeps R22–R23 for pitch walk
  itself.

## FinFET: US 9,812,358 B1 (Figs. 2–22C)

The patent's figure views:
- Figs. 2–6: section A–A, across the channel, several fins.
- Figs. 7A–13B: A is A–A, B is B–B (along the fin).
- Figs. 14A–22C: A is 3D, B is B–B, C is C–C.

Its order:
1. **Fig. 2.** Substrate 50: region 50B for n-type, 50C for p-type.
2. **Fig. 3.** Fins 52: trenches etched in the substrate (RIE or NBE, anisotropic).
3. **Fig. 4.** Insulation material 54: silicon oxide by FCVD, then anneal and CMP.
4. **Fig. 5.**
   - STI 54 recessed: CERTAS, SICONI or dHF.
   - Wells: P well in 50B (boron or BF₂), N well in 50C (P or As), each ≤ 10¹⁸ cm⁻³, each
     implanted through a photoresist mask. Then an anneal.
5. **Fig. 6.**
   - Dummy dielectric 58: silicon oxide or nitride.
   - Dummy gate layer 60: polysilicon, from amorphous Si deposited and recrystallised; CMP.
   - Mask layer 62: SiN or SiON.
6. **Figs. 7A/B.**
   - Masks 72, then dummy gates 70.
   - Gate seal spacers 80: thermal oxidation, or deposition and anisotropic etch.
   - LDD implants, region by region (10¹⁵–10¹⁶ cm⁻³), then an anneal.
7. **Figs. 8A/B.** Epitaxial S/D 82, region by region:
   - Mask the other region; deposit a dummy spacer layer; anisotropic etch to dummy gate spacers.
   - Etch recesses in the fins; grow the epi.
   - nFET: Si, SiC, SiCP or SiP. pFET: SiGe, SiGeB, Ge or GeSn.
   - Dummy spacers and mask removed.
8. **Figs. 9A/B.** Gate spacers 86: SiN or SiCN, conformal deposition and anisotropic etch, on the
   gate seal spacers. S/D implant to 10¹⁹–10²¹ cm⁻³ is an option; the epi may be doped in situ.
9. **Figs. 10A/B.** Dummy ILD 88: PSG, BSG, BPSG or USG.
10. **Figs. 11A/B.** CMP to the dummy gate tops; masks 72 removed.
11. **Figs. 12A/B.** Dummy gates removed (anisotropic dry etch), opening recesses 94. The dummy
    dielectric (and the seal spacers) may then be removed.
12. **Figs. 13A/B.**
    - Gate dielectric 98/102, conformal on the fin tops and sidewalls, the spacer sidewalls and the
      dummy ILD top. Silicon oxide or nitride, or high-κ (a metal oxide or silicate of Hf, Al, Zr,
      La, Mg, Ba, Ti or Pb).
    - Gate electrodes 100/104: TiN, TaN, TaC, Co, Ru, Al, combinations or multilayers. Then CMP.
    - The n and p regions may use distinct processes and materials.
13. **Figs. 14A–C.** Gate dielectric and electrodes recessed (dry etch), forming recesses 110.
14. **Figs. 15A–C.** Hard mask 112 in the recesses: a metal, metal oxide, metal nitride or pure Si
    (TiO, HfO, AlO, ZrO, ZrN). CMP level with the spacers and dummy ILD. It protects the spacers
    during self-aligned contact etching.
15. **Figs. 16A–C.** Dummy ILD 88 removed, opening recesses 114 onto the epi.
16. **Figs. 17A–C.** Dummy contact material 116: spin-on carbon (SOC), about 50–95 % carbon.
    - An optional liner (Ti, TiN, Ta, TaN) goes first.
    - Baked: about 180 °C, then about 350 °C.
17. **Figs. 18A–C.** Optional furnace anneal, then CMP of the SOC to the spacer and hard-mask tops.
18. **Figs. 19A–C.**
    - Tri-layer lithography: BARC 118, Si-containing intermediate hard mask 120, photoresist 122.
    - Exposure: KrF, ArF or F₂, or immersion. Develop, then trim the resist.
    - Pattern the SOC by dry etch (O₂, SO₂, N₂, H₂): openings 124 over the gate electrodes, and over
      those S/D regions that will not be contacted.
19. **Figs. 20A–C.** ILD 126: PSG, BSG, BPSG or USG, filling openings 124, including between the
    p-type and n-type fin groups.
20. **Figs. 21A–C.** SOC removed by dry etch, opening openings 128 onto the epi.
21. **Figs. 22A–C.** Replacement contacts 130:
    - liner Ti, TiN, Ta or TaN; conductor Cu, W, Co, Al, Ni or others; CMP;
    - an anneal forms a silicide at the epi interface;
    - a gate contact is then formed through hard mask 112.

**Drawn:**
- Gate dielectric: SiO₂ interfacial layer and HfO₂.
- Gate electrodes, from the patent's list: pFET TiN; nFET an Al-containing layer (Al is on the
  list); Co fill.
- Hard mask 112: AlOₓ.
- Contacts: Ti-based silicide, TiN liner, Co.
- No contact etch-stop layer: the patent has none.
- Fin patterning follows R30 (SAQP).

## SAQP: US 9,171,764 B2 (Figs. 1–11)

1. **Fig. 1.** Mask stack 26 on the substrate 12, bottom to top:
   - hard mask 16: SiN, SiO₂, SiON, amorphous carbon or SiCOH; 25–50 nm, e.g. 40 nm;
   - lower mandrel layer 14: a-Si or poly-Si; 80–120 nm, e.g. 100 nm;
   - hard mask 22: the same materials and thickness as 16;
   - upper mandrel layer 20: a-Si or poly-Si; about 100 nm;
   - masking layer 24: photoresist.
2. **Fig. 2.** Resist patterned. RIE forms upper mandrels 30 and 32, stopping on hard mask 22. The
   patent's point is that mandrel widths 42 and 44 and spacing 40 may differ, giving variably spaced
   fins. Uniform mandrels are also allowed.
3. **Fig. 3.** Spacer-forming layer 50: SiN or SiO₂, conformal (ALD, PECVD, LPCVD).
4. **Fig. 4.** Etch to upper spacers 52, about 14 nm (14–30 nm): RIE, CHF₃/O₂ for SiN, CHF₃ or CF₄
   for SiON or SiO₂. Then planarisation.
5. **Fig. 5.** Upper mandrels removed (RIE). Hard mask 22 and the lower mandrel layer are etched
   under spacers 52, forming lower mandrels 55.
6. **Fig. 6.** Spacer-forming layer 69 over the lower mandrels.
7. **Fig. 7.** Lower spacers 70, about 10–20 nm, then planarisation.
8. **Fig. 8.** Lower mandrels removed. Spacers 70 on hard mask 16 are mask 73.
9. **Fig. 9.** Hard mask 16 and the substrate are etched: fins 74 in pairs 76, 78, 80, 82. The
   distance within a pair equals the lower-mandrel CD.
10. **Figs. 10–11.** SRAM areas 93 and 94: mask 95, trenches 96, and one fin removed from pairs 78
    and 80 for the PMOS transistor.

**Drawn:** these films and materials, with uniform mandrels. The patent's variable spacing and SRAM
fin removal are named in the text, and the pitch-walk lesson varies the spacing.

## Nanosheet (Si/SiGe CMOS): US 2023/0420457 A1 (Figs. 1–19)

1. **Fig. 3.** PTS implants: n-type layer 302 under the pFET, p-type layer 304 under the nFET.
2. **Fig. 4.** Stack 400, in layer order: base 402 (SiGe, about 50 % Ge, 40–75 %), then 404, 406,
   408, 410, 412 and 414 alternating. 404, 408 and 412 are SiGe, about 25 % Ge (15–35 %); they are
   the pFET's channels. 406, 410 and 414 are Si; they are the nFET's.
3. **Fig. 5.** Hard mask: silicon oxide or nitride. RIE through the stack and the PTS into the
   substrate forms pFET fins 502 and nFET fins 504. STI 500 is low-κ or ultralow-κ dielectric, up to
   the bottom of 402.
4. **Fig. 6.** Dummy gates 602 (a-Si), hard mask 604 (SiN or SiO).
5. **Fig. 7.** Protective oxide liner 702 (SiO₂ or AlOₓ) and mask 704 (OPL). Both are etched back to
   open the nFET region.
6. **Fig. 8.** Vapor-phase HCl removes 402 from the nFET only, leaving gaps 802. Mask 704 and
   liner 702 are stripped.
7. **Fig. 9.** Gate spacer material 902 (SiOC, SiCN, SiOCN, SiBCN): one conformal film, which also
   fills the gaps as BDI 904.
8. **Fig. 10.** With the nFET and gate regions masked, 902 is etched back over the pFET only
   (fluorocarbon: CF₄, C₄F₈, CH₃F). The pFET fin is recessed through 402–414 and into PTS 302
   (Cl₂, HBr, CF₄).
9. **Fig. 11.**
   - Indents: Si layers with NH₄OH; the 50 % SiGe with HCl or ClF₃.
   - Conformal low-κ (or ultralow-κ) deposition and etch-back: inner spacers 1102.
   - S/D 1104: Si:B first, then SiGe:B, from the SiGe channel edges and PTS 302 (compressive
     strain).
10. **Fig. 12.**
    - Protective oxide liner 1202 (AlOₓ, 2–3 nm) and mask 1204 (OPL or ODL) over the pFET.
    - AlOₓ etch-back in the nFET region, then 902 etched back, stopping on the top of BDI 904.
    - The nFET fin is recessed, keeping the BDI.
11. **Fig. 13.**
    - Indent of the 25 % SiGe.
    - Low-κ inner spacers 1302.
    - n-type S/D 1304 from the Si channel edges. Mask 1204 removed, liner 1202 etched back.
    - The S/D 1304 top is higher than the S/D 1104 top by H, at least the BDI's thickness.
12. **Fig. 14.** ILD 1402 (low-κ), CMP removing 604, dummy gates removed.
13. **Fig. 15.** Mask 1502 opens the pFET: vapor HCl removes 402, and vapor NH₄OH removes 406, 410
    and 414.
14. **Fig. 16.** Mask 1602 opens the nFET: ClF₃ removes 404, 408 and 412.
15. **Fig. 17.**
    - High-κ in both regions (Hf-based).
    - p-type WFM deposited in both regions and removed from the nFET: stack 1702.
    - n-type WFM on the nFET: stack 1704, taller than 1702 by H1.
    - Metal 1706 (W) deposited and recessed.
    - Gate cut 1720 through the W and both WFM stacks at the p/n boundary.
    - One insulating fill forms the cut and the SAC caps 1708 (SiN, SiNC, SiBCN).
16. **Fig. 18.** S/D trenches in ILD 1402 and gate trenches in the SAC cap. The conductive material
    (a metal, which may include a silicide) forms S/D contacts 1802 and 1804 and gate contacts 1812
    and 1814.
17. **Fig. 19.** No gate cut: metal 1706 touches both WFM stacks, giving a shared gate. Fig. 19B
    still draws gate contacts 1812 and 1814.

**Drawn:**
- Spacers and BDI: SiBCN. Inner spacers: low-κ, as the patent's inner-spacer step says.
- WFMs: TiN (p) and an Al-containing n-type metal (Ti and Al and their alloys are on the list).
- Fill W; SAC cap SiN.
- Contacts: TiSiₓ and Co, with a W gate contact; the patent names no metals here.
- Liners: SiO₂ (702) and AlOₓ (1202). Masks: OPL.

## Forksheet: EP 3 989 273 A1 (imec, Figs. 1–6), US 11,862,700 B2 and US 2024/0178128 A1 (TSMC)

The imec application is followed for the Device, and the Inverter is that Device wired up.
US 2024/0178128 A1's gate bridge is described in the story as another way to join the gates, not
drawn; US 11,862,700 B2 is a second example of the wall and its materials.

- **Stack:** Si channel layers 114 and SiGe second layers 116, with Ge at least 20 % higher.
  - The top second layer 116a is thicker, so the wall rises above the top channel.
  - Sheets 10–30 nm wide and 3–10 nm thick.
- **Insulating wall 120:**
  - SiN (or SiCO, SiCN, SiOCN), 5–20 nm wide (8–20 nm elsewhere in the text);
  - its base is embedded in the substrate;
  - its top is level with the top second layer.
- **STI 101:** silicon oxide around the pair.
- **Gate structure 126:**
  - sacrificial gate 128, amorphous Si;
  - gate cap 130, hard-mask material;
  - gate spacer 132, SiC or SiBCN by ALD.
- **Inner spacers 134:** SiN, SiCO or another low-κ ALD dielectric.
- **Source/drain:**
  - selective-area Si epitaxy, P-doped and N-doped;
  - each region is masked while the other is grown;
  - the wall confines them laterally.
- **Liner 133:** SiN by ALD, an etch stop.
- **Material layer 134:** ILD, flowable oxide CVD, then CMP.
- **Contact partition wall 142:**
  - the wall materials, etched in a trench above the wall (stopping on the wall or the liner) and
    filled;
  - 10–24 nm wide, wider than the wall; it may taper.
- **S/D contacts 150:** ALD TiN, then CVD W, etched in one merged opening that the partition wall
  splits. CMP, optional recess, ILD re-deposited.
- **RMG (S516):**
  - HCl-based dry etch releases the SiGe; the sheets stay attached to the wall.
  - HfO₂ (or HfSiO, LaO, AlO, ZrO).
  - pWFM TiN or TaN; nWFM TiAl or TiAlC.
  - Gate fill W, Al, Co or Ru, common above the wall.
- **S518:** the gate is recessed; a gate cut is optional.

**The TSMC patent, as a second example, told in the scene note:**
- A two-layer dielectric feature 130: high-κ layer 126 (HfO₂ and others, 0.5–10 nm) and low-κ
  layer 128 (SiO₂, SiN, SiCN, SiOC, SiOCN).
- Features 134 on the outer sides too, and a dielectric layer 140 of 10–30 nm on top.
- A SiGe cladding layer 132, and a sacrificial layer 107.
- Air gaps 187 between the sheets.
- Gate electrode layers: n-type 182 (TiAlC and others), p-type 184 (TiN and others); metal layer
  186 (W, Ru, Mo, Co).
- SAC layer 188; S/D contacts 190 on silicide 139 (TiSi for n-type, NiSi and others for p-type).

**Drawn:**
- Si channels; a SiN wall and SiN contact partition wall.
- Spacers: SiBCN. Inner spacers: SiN, the first of the patent's options.
- Si:B and Si:P source/drain. The SiN liner 133 is not drawn.
- HfO₂, TiN (p), TiAlC (n); W fill over the wall.
- TiN and W contacts; a SiN gate cap. The imec text names the cap only as hard-mask material, so
  SiN is the model's choice.

## Monolithic CFET: US 11,869,812 B2 (IBM, Figs. 1A–18)

1. **Fig. 1B.**
   - Substrate 110. Insulating layer 120: a BOX (SiO₂) or a bottom dielectric isolation (SiN,
     SiBCN, SiOCN, SiOC).
   - Stack: the lower device has three SiGe 140 and two Si 130 layers. SiGe 150 (50–70 % Ge)
     separates the tiers. The upper device has two SiGe 140 and two Si 130 layers. SiGe 140 is
     20–40 % Ge.
2. **Fig. 2.** Dummy gates 210: thin oxide and poly- or amorphous Si. Hard mask 220: Si₃N₄.
3. **Fig. 3.** Layer 150 removed selectively.
4. **Fig. 4.** Spacer material 410 (Si₃N₄, SiBCN, SiNC, SiN, SiCO, SiO₂, SiNOC) fills the void and
   forms the sidewall spacers.
5. **Fig. 5.** Protective cap 510 (SiC or SiO₂), via OPL; spacers 410 removed from the stack
   sidewalls.
6. **Fig. 6.** Stack recessed; inner spacers 610 from the same list, by conformal deposition and
   isotropic etch-back.
7. **Fig. 7.** Lower S/D 710: SiGe:B from the exposed lower channels. The upper channels are
   covered by OPL and a thin SiO₂ or SiN spacer during growth. The lower device is the pFET.
8. **Fig. 8.** Sacrificial spacer layer 810, TiOₓ: conformal pinch-off, CMP, recessed to expose the
   S/D top.
9. **Fig. 9.** Notches recessed into the top of the lower S/D.
10. **Fig. 10.** OPL 1010 masks one side; 810 is removed on the other.
11. **Fig. 11.** Isolation layer 1110 (SiO₂, SiN, SiOC): deposited, CMP, recessed, above the lower S/D
    and 810.
12. **Fig. 12.** Upper S/D 1210: Si:P, for the nFET, from the upper Si channels.
13. **Fig. 13.** ILD 1310 (SiO₂, SiN, SiOC), CMP removing caps 510 and hard masks 220.
14. **Fig. 14.**
    - Dummy gate and SiGe 140 removed. HKMG 1410:
      - dielectric HfO₂ and others;
      - WFM TiN, TiAlN, TiAlC, TiAlCN or TaN;
      - metal W, Co, Ta, Al, Ru or Cu.
    - Optional recess, then gate dielectric cap 1420.
15. **Fig. 15.** Vias 1510: to the upper S/D and to 810 on one side; a common via to the upper and
    lower S/D on the other.
16. **Fig. 16.** Sacrificial 810 removed, exposing the lower S/D.
17. **Fig. 17.** Contact 1710: a silicide liner (Ti, Ni, Co or NiPt), a thin TiN layer, then Cu, Ag,
    Au, W, Co or Ru.

**Drawn:**
- Lower pFET (SiGe:B), upper nFET (Si:P), two Si sheets per tier, on a BOX.
- SiBCN spacer material between the tiers in the gate region, and as spacers and inner spacers.
- SiO₂ isolation layer in the notch above the lower S/D.
- One common gate: HfO₂, TiN around the lower sheets, TiAlC around the upper, W fill. Gate cap SiN.
- Front-side contacts only: TiSiₓ, TiN, W.
  - Drain side: one common contact reaches both drains, which is the inverter's output.
  - Source side: the upper source is contacted from above, and the lower source through the space
    where the TiOₓ was.

## Sequential CFET: US 2024/0413156 A1 (TSMC, Figs. 1A–1N)

The face-to-back process of Figs. 1A–1N is followed.

- **Lower transistor 10L, in wafer 2:**
  - GAA; Si channels 26L; SiGe dummy layers 24L.
  - Inner spacers 48: SiOCN, SiOC or SiON.
  - S/D 50L.
  - CESL 52L: SiN. ILD 54L: PSG or SiO₂.
  - Gate stack 60L: IL and high-κ 56L; electrodes 58L, n-type TiAl, TiAlN; p-type TiN; a filling
    metal.
- **Between the tiers:**
  - Etch stop 62: AlN, AlO or SiOC, or AlO/SiOC/AlO.
  - Dielectric 64: SiO₂.
  - Inter-metal line 66: Cu with Ti or TiN adhesion.
  - Bond layers 68L and 68U: SiO₂, fusion-bonded (Si–O–Si).
- **Upper transistor 10U, in wafer 102:** built after bonding; opposite type; its own CESL 52U, ILD
  54U and gate stack 60U.
- **Deep contact plug 70:** W, Co, Cu, Ti or TiN; through the upper S/D to line 66. Plug 71 goes to
  the other upper S/D.
- **Front-side interconnect:**
  - low-κ dielectric 72; etch stop 74 (AlN, AlO or SiOC); vias 76;
  - Cu lines 80 in dielectric 78.
- **Carrier:** bond 82 to carrier 88, flip.
- **Backside:**
  - substrate 20 removed;
  - deep plug 90 through the lower S/D to line 66, and plug 91;
  - dielectrics 92–94; vias 96; lines 110; dielectric 98.
- **Polarity:** p-type prefers (110), n-type (100); the patent allows either on either tier.

**Drawn:**
- Lower pFET (SiGe:B), upper nFET (Si:P).
- W is the gate fill metal. The patent names none, so this is the model's choice.
- Separate gates; the patent joins them nowhere. The Inverter follows R33 instead, so no
  sequential-CFET inverter is drawn.
- The finished die sits flipped on a carrier. Device mode shows it upright, with the carrier not
  drawn.

- **Checked against CN 118712136 A (same disclosure, text-searchable):**
  - The upper stack sits directly on bond layer 68U. 68U is formed on stack 22U [0041], and
    substrate 120 and the top SiGe layer are removed after bonding [0043]–[0044].
  - Plug 91 lands on a lower source/drain, with an optional silicide under it [0059]. Deep plug
    90 is etched through 50L [0056].
  - Backside dielectric 93 is an etch stop and a low-κ layer [0059]; 92 is low-κ [0060]. With
    substrate 20 removed [0055], it meets the lower stack directly. STI 32 (FCVD oxide) stays
    beside the stack.

## Forksheet gate-bridge variant: US 2024/0178128 A1 (TSMC)

- **Gates:** the n and p gate electrodes are separated by the dielectric wall and planarised level
  with it; the gate rises 15 nm or less above the top channel.
- **Gate bridge contact:** a barrier (TiN) and a fill (W, among others), wider than the wall, on
  the wall and in contact with both gates. It joins them into the inverter input.
- **Gate via:** lands on the bridge contact.
- **Etch stops:** SiN etch-stop layers and a CESL.
- **S/D contacts:** silicided, with a TiN barrier.
- **Not drawn.** The Inverter is the imec Device wired up, whose one gate fill over the wall
  already joins the gates; this patent is cited for the alternative.

## Si/Si nanosheet: US 2023/0178617 A1 (IBM)

- **Stack:** sacrificial layer 112, SiGe with 45–70 % Ge, 5–15 nm; seed layer 113, the channel
  material (Si), 2–5 nm; then SiGe 114 (15–35 % Ge) and Si 116 in turn, 5–12 nm each.
- **Seed layer:** undoped Si 140 grows from it and from the channel ends in the S/D trenches
  [0079–0080]. At channel release a controlled oxidation and etch thin the channels and remove
  the exposed seed [0117–0119]; it remains only below the inner spacers and the undoped Si, above
  the bottom isolation 146. The gate stack sits on the bottom isolation [0121–0123].
- **Spacers:** gate spacer 130 SiON, SiOCN, SiOC or SiBCN; inner spacers 138 SiN; BDI 146 SiN.
- **S/D:** pFET SiGe, boron-doped; nFET SiC doped with phosphorus.
- **Gate:** high-κ about 2 nm; pFET TiN (or TaN, TiC, TiAlC), nFET TiAlC. No fill metal, gate cap
  or contact metal is named; the Mo fill, SiN cap and Co contacts are the model's.
- **ILD 170:** silicon nitride.
- **Drawn:** the seed only under the inner spacers and the undoped Si; SiBCN outer spacers; SiN
  inner spacers and BDI; the gate's high-κ and work-function metal on the BDI below the sheets.
