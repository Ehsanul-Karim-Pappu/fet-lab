# Content and capacitance audit

Reviewed 21 September 2026. Scope: the 16 shipped scenes, their geometry labels,
stories, material palette, capacitance calculation, Android About/Help, web/PWA,
legacy nanosheet viewer, privacy policy and user-facing documentation.

## What has—and has not—been validated

Primary references are catalogued with their supported claims in
[Technical references](TECHNICAL_REFERENCES.md), generated from
`data/references.json`. They are also accessible in Android About and below the
web/PWA viewer. The sources support architecture and integration concepts, not
the app's exact dimensions, complete material recipe or numerical capacitances.

This is an educational box model, not a foundry PDK, calibrated compact model,
process simulation or measured device dataset. A complete physical validation
would need doping profiles, material compositions, bias/temperature conditions,
realistic dielectric surroundings and a calibrated field/device solver or measurements.
Those inputs are absent. No claim of sign-off accuracy is made.

## Terminology and story corrections

- **Architecture** is appropriate for FinFET, nanosheet FET, forksheet and CFET.
  GAA describes gate coverage; nanosheets are one GAA channel shape. CFET describes
  vertical complementary-device integration, not one compulsory gate connection.
- The displayed path is one possible roadmap. FinFET does not universally stop
  at a particular node; forksheet is not a mandatory step before CFET. Example-node
  numbers are illustrative labels, not physical dimensions or process specifications.
- The forksheet model depicts the classic **inner-wall** concept. The newer
  outer-wall variant is explained but not drawn. The 8nm Si3N4 wall is a model choice.
- Monolithic and sequential CFET integration are distinguished without claiming
  that sequential devices are simply two completed chips glued together. Upper-tier
  processing after layer transfer must respect the lower tier's thermal budget.
- Common/split gates and frontside/backside contacts are integration options.
  The depicted backside GND and common inverter input are examples, not CFET definitions.
- Equal fin counts or a geometric p/n width ratio do not establish electrical
  balance. Mobility, threshold, strain, contacts and operating point also matter.
  The app displays ideal logic states, not simulated current or timing.
- Rail-to-rail span along z is identified explicitly; standard-cell convention
  commonly calls this cell height. Gate-stack span and device-pair span are different
  measurements. Percentage reductions of drawn spans are not equal-drive area gains.
- Layout simplifies the stack and exaggerates vertical dimensions. Its two-sheet
  nanosheet drawing is not a layer-for-layer rendering of the three-sheet Device/Inverter.
- Perspective camera presets are called **3D overview**, not geometrically exact
  isometric projections. Legacy nanosheet figure-letter prefixes were removed.

## Materials review

| Displayed material or role | Interpretation and limits |
| --- | --- |
| Si / SiGe | Plausible semiconductor/channel or epitaxy examples. Doping, Ge fraction and strain are unspecified; not every pFET uses the same recipe. |
| SiO2 + HfO2 | Plausible interfacial/high-k stack. Drawn thicknesses are 1nm + 2nm; relative permittivities 3.9 and 22 are model assumptions. |
| TiN | Conductive work-function region, not “n-doped/p-doped TiN.” Polarity-dependent tuning and interface effects are not modeled. |
| Mo, Ni, W, NiSi | Illustrative gate/contact palette. Individual uses are plausible; the complete combination is not verified as a manufacturing recipe for these scenes. Chemical labels no longer imply arbitrary routing levels M0–M4. |
| Si3N4 | Illustrative spacer/inner-wall dielectric. Actual spacer and wall compositions are process-dependent. |
| Middle-tier isolation / bonding oxide | Isolation is a role; MDI chemistry is unspecified. SiO2 bonding dielectric and the assumed MDI permittivity are example choices. |
| Channel, MD, Po, VD, VG, Metal 0 | Layout roles rather than a complete chemical specification. “Po” is a gate-region convention, not a claim of a polysilicon electrode. The internal legacy channel ID `nanowire` can also draw fins/sheets. |

## Do the capacitance values make sense?

They are internally checkable **first-order geometry estimates**, with magnitudes
consistent with their plate formulas. That does not establish realistic device
capacitance or a reliable architecture ranking. In particular, Cox is an oxide-stack
estimate, not terminal Cgg; Cgc/Cge are partial direct couplings, not a full capacitance
matrix. Adding these terms does not produce a characterized cell input capacitance.

### Corrections

1. **Oxide thickness:** volume divided by inner interface area included shell-corner
   volume and overstated thickness. Use the authored films' actual normal thickness:
   1nm SiO2 and 2nm HfO2, rejecting nonuniform-film inputs.
2. **Mixed dielectric gaps:** the old midpoint lookup assigned one material to the
   entire gap. Each sampled ray now integrates thickness/permittivity in series;
   intervening conductors block that direct ray coupling.
3. **Junction selection:** channel-to-body area was counted as source/drain junction
   area. Only explicitly drawn S/D-to-body contact area now enters the proxy.
   The FinFET proxy therefore becomes zero because this interface is not drawn,
   **not because a real FinFET has no junction capacitance**.
4. **Nanosheet isolation (after the audit):** the nanosheet model now uses full bottom
   dielectric isolation (BDI), formed from the spacer dielectric, on a short Si sub-fin
   that carries a p-type punch-through stopper (drawn as a region of illustrative extent),
   with the STI recessed to the BDI's bottom and the gate and spacers reaching down beside
   it, as its fabrication-process steps require. The source/drain epitaxy sits on the BDI, so no S/D-to-substrate
   junction is drawn and the Cj* proxy, which counts only that junction contribution, is
   now 0.00aF (was 27.35aF). Zero junction contribution in this proxy does not imply zero
   total parasitic capacitance: S/D-to-substrate coupling through the dielectric and
   fringe fields remains and is not estimated. No other value changed.
   `CONTENT_AUDIT.pdf` is the audit as first published and still shows the old value.

### Equations and sanity checks

Lengths are nm, areas nm² and capacitances aF (1aF = 10^-18 F).

```
epsilon0 = 0.0088541878128 aF/nm
EOT = 1 + 2 × 3.9 / 22 = 1.354545... nm
Cox = epsilon0 × gated_area / (1/3.9 + 2/22)
Cgc, Cge = sum(epsilon0 × sample_area / sum(thickness_i / k_i))
Cj* = epsilon0 × 11.7 × drawn_SD_body_area / assumed_depletion_width
assumed_depletion_width = 5nm
```

Nanosheet: three 30nm × 5nm channels give total gated perimeter
`3 × 2 × (30+5) = 210nm`. At LG=15nm, the area is 3150nm² and
Cox=80.30aF, or 382.4aF/µm of gated perimeter. The previous 358aF/µm
was a thickness-extraction artifact, not a physical correction to the plate model.

| Scene | Cox before → after (aF) | Cgc before → after (aF) | Cge after (aF) | Cj* after (aF) |
| --- | ---: | ---: | ---: | ---: |
| FinFET | 85.88 → 88.10 | 15.46 → 15.46 | 17.61 | 0.00 |
| Nanosheet | 75.12 → 80.30 | 7.83 → 5.09 | 16.51 | 0.00 (27.35 before BDI; see 4.) |
| Forksheet | 107.08 → 112.42 | 10.60 → 6.95 | 24.21 | 40.11 |
| Monolithic CFET | 69.83 → 76.48 | 4.63 → 3.22 | 12.52 | 0.00 |
| Sequential CFET | 69.83 → 76.48 | 4.63 → 3.22 | 12.52 | 0.00 |

Identical CFET estimates here reflect the limited geometry estimator, not equivalence
of monolithic and sequential technologies. The unchanged Cge numbers do not imply
they are experimentally verified.

### Remaining assumptions visible in the app

- Unfilled gaps have k=1 (vacuum), not a realistic inter-layer dielectric environment.
- Only facing area along x is included for Cgc/Cge. No 3D fringing, corner fields,
  quantum capacitance, bias-dependent depletion or semiconductor screening is solved.
- S/D epitaxy is approximated as equipotential; doping and bias are unspecified.
- Cj* assumes 5nm depletion and Si permittivity, even where SiGe composition is
  unspecified. It omits missing junctions and calibrated sidewall behavior.
- W_eff is the total gated perimeter **in that scene**. FinFET/nanosheet show one
  polarity; forksheet/CFET show both. Normalization is not equal-drive matching.
- Both absolute values **and cross-architecture ratios** depend on these assumptions.

## Privacy and provenance

Android saves two preferences locally: the guided-tour completion flag and the control
sheet's see-through. Per-scene state is held in memory for the session only; other scene
controls are not durable profiles, although Android can restore temporary activity state. Android has no
INTERNET permission; reference/support links open external apps. Backup is disabled
and shared preferences are explicitly excluded in extraction rules.

The website/PWA makes hosting and Google Fonts requests and caches assets. The policy
now distinguishes those requests from the native app's behavior; it does not promise
that external providers receive no request information.

The old “S. Rathore et al., Semiconductor Science and Technology (2021)” credit lacks
a title, DOI and figure number. Its exact source remains **unverified**. It is retained
in the reference catalog for provenance, not advertised as a verified reference or
silently replaced by a related paper. The original paper/figure is needed to resolve it.

## Reproducible checks

From the repository root:

```bash
python3 -B scripts/build.py
python3 -B scripts/test_parasitics.py
python3 -B scripts/test_content.py
python3 -B scripts/verify.py
python3 scripts/ktcheck.py android/app/src/main/java/io/github/ehsanulkarimpappu/fetlab/*.kt
git diff --check
cd android
./gradlew --offline :app:assembleDebug --no-daemon
```

Capacitance tests include independent gated-perimeter calculations, units, layered
dielectrics, mirrored plates, conductor shielding, junction selection and 0.5/0.25/0.125nm
grid comparisons (within 3% for these scenes). Content tests check synchronized payloads,
reference IDs, model caveats and view naming. Sampled non-overlap checks do not prove
electrical connectivity or fabrication feasibility. APK compilation is not real-device
testing, and these checks are not TCAD/measurement validation.
