# Technical references

Generated from data/references.json. Reviewed 2026-09-21.

References support device concepts, not this model's exact dimensions, complete material recipe or calculated capacitances. Geometry and colors are illustrative; no foundry PDK or measured device dataset is reproduced.

- **R1** [Entering the nanosheet transistor era](https://www.imec-int.com/en/articles/entering-nanosheet-transistor-era-0) — imec. FinFET, GAA nanosheet, inner-wall forksheet and process modules.

- **R2** [Outer wall forksheet to bridge nanosheet and CFET device architectures in the logic technology roadmap](https://www.imec-int.com/en/articles/outer-wall-forksheet-bridge-nanosheet-and-cfet-device-architectures-logic-technology) — imec. Inner-wall versus outer-wall forksheet; non-universal roadmap.

- **R3** [Imec puts complementary FET (CFET) on the logic technology roadmap](https://www.imec-int.com/en/articles/imec-puts-complementary-fet-cfet-logic-technology-roadmap) — imec. Monolithic/sequential integration and post-transfer thermal constraints.

- **R4** [Imec demonstrates functional monolithic CFET devices with stacked bottom and top contacts](https://www.imec-int.com/en/press/imec-demonstrates-functional-monolithic-cfet-devices-stacked-bottom-and-top-contacts) — imec. Frontside contacts and advantages of backside contact formation.

- **R5** [Advancing the CFET-based device roadmap: novel integration modules and standard-cell configurations](https://www.imec-int.com/en/articles/advancing-cfet-based-device-roadmap-novel-integration-modules-and-standard-cell) — imec. Common-gate and split-gate CFET options.

- **R6** [Samsung Begins Chip Production Using 3nm Process Technology With GAA Architecture](https://news.samsung.com/global/samsung-begins-chip-production-using-3nm-process-technology-with-gaa-architecture) — Samsung Electronics, 30 June 2022. Initial 3nm GAA production announcement.

- **R7** [Intel's Transistor Technology Breakthrough Represents Biggest Change to Computer Chips In 40 Years](https://www.intel.com/pressroom/archive/releases/2007/20070128comp.htm) — Intel, 28 January 2007. Hafnium-based high-k/metal gates at 45nm.

- **R8** [Ab initio calculation of Effective Work Functions for a TiN/HfO2/SiO2/Si transistor stack](https://arxiv.org/abs/1112.2163) — Research paper, arXiv:1112.2163 (2011). Example gate stack; effective work function depends on the stack.

- **R9** [Epi Source/Drain Damage Mitigation with Inner Spacer and Buffer Optimization in Stacked Nanosheet Gate-All-Around Transistors](https://research.ibm.com/publications/epi-sourcedrain-damage-mitigation-with-inner-spacer-and-buffer-optimization-in-stacked-nanosheet-gate-all-around-transistors) — IBM Research, SSDM 2023. SiGe pFET source/drain epitaxy and inner-spacer integration.

- **R10** [Analysis and Design of Digital Integrated Circuits: Problem Set 1 Solutions](https://ocw.mit.edu/courses/6-374-analysis-and-design-of-digital-integrated-circuits-fall-2003/151adc5717d8b3c7e34e2761972124f8_ps1_03_sol.pdf) — MIT OpenCourseWare, 6.374 (2003). Electrical inverter balance is not determined by width alone.

- **R11** [Work Function Engineering with Molybdenum and Molybdenum-Nitride Gate Electrodes](https://repository.rit.edu/ritamec/vol14/iss1/6/) — Rochester Institute of Technology repository. Molybdenum as a researched gate material, not validation of this model's complete stack.

- **R12** [A view on the logic technology roadmap](https://www.imec-int.com/en/articles/view-logic-technology-roadmap) — imec. FEOL/MOL/BEOL, routing and standard-cell track height.

- **R13** [Single stack dual channel gate-all-around nanosheet with strained PFET and bottom dielectric isolation NFET (US 12,568,683 B2)](https://patents.google.com/patent/US12568683B2/en) — IBM (assignee), US patent. nFET process, Figs. 5A–9B and 12A–13B (10A–11B are pFET steps). One early bottom-dielectric-isolation route for stacked nanosheets: STI at the bottom of a high-Ge sacrificial layer, its selective removal after dummy-gate formation, a conformal spacer dielectric that also fills the bottom cavity, a source/drain recess that preserves the isolation, and epitaxy from the exposed channel ends. A disclosed integration option, not evidence of any foundry's manufacturing flow.

- **R14** [A Novel Dry Selective Etch of SiGe for the Enablement of High Performance Logic Stacked Gate-All-Around NanoSheet Devices](https://research.ibm.com/publications/a-novel-dry-selective-etch-of-sige-for-the-enablement-of-high-performance-logic-stacked-gate-all-around-nanosheet-devices) — IBM Research (Loubet et al.), IEDM 2019. Two distinct uses of selective SiGe etch: a partial lateral recess at the exposed ends before inner-spacer fill, and the later channel release in the gate cavity. Its selectivity and device results belong to the studied process, not to this model.

- **R15** [Full Bottom Dielectric Isolation to Enable Stacked Nanosheet Transistor for Low Power and High Performance Applications](https://research.ibm.com/publications/full-bottom-dielectric-isolation-to-enable-stacked-nanosheet-transistor-for-low-power-and-high-performance-applications) — IBM Research (Zhang et al.), IEDM 2019. Why bottom isolation matters: compares full BDI with a punch-through-stopper scheme for sub-channel leakage and effective capacitance. Not evidence that its sequence matches R13's.

- **R16** [Lithography principles](https://www.asml.com/en/technology/lithography-principles) — ASML. A mask or reticle pattern is projected into photoresist; exposure changes the resist's solubility, development leaves protected and open regions, and a separate etch transfers the pattern into the film below.

- **R17** [Six crucial steps in semiconductor manufacturing](https://www.asml.com/en/company/stories/2021/semiconductor-manufacturing-process-steps) — ASML. Deposition, resist coating, lithography, development, etch and ion implantation as the repeating steps that build a chip.

- **R18** [Nanosheet technology for the computing era of AI and 5G](https://research.ibm.com/blog/nanosheet-technology-ai-5g) — IBM Research. Conceptual support for adjustable sheet width, growth-controlled sheet thickness, full BDI under gate and source/drain, and tight selective-etch control.

- **R19** [First EUV lithography high-volume manufacturing solution for N5 BEOL](https://www.imec-int.com/en/imec-magazine/imec-magazine-march-2017/first-euv-lithography-high-volume-manufacturing-solution-for-n5-beol) — imec. A back-end metal-line example of SAQP mechanics: core lines, first spacer and etch, core removal, reuse as the second core, second spacer and core removal, transfer to a hard mask, then a separate block pattern. An illustration of SAQP, not evidence of how R13 patterns its layers.

- **R20** [Advanced in-line metrology strategy for self-aligned quadruple patterning](https://research.ibm.com/publications/advanced-in-line-metrology-strategy-for-self-aligned-quadruple-patterning) — IBM Research. Repeated sidewall-spacer image transfers give roughly a quarter of the original pitch in a periodic array, with accumulated variation such as pitch walk and CD variation.

- **R21** [Spacer defined double patterning for sub-72 nm pitch logic technology](https://research.ibm.com/publications/spacer-defined-double-patterning-for-sub-72-nm-pitch-logic-technology) — IBM Research. Mandrels and a single spacer-defined pitch split (SADP).

- **R22** [N7 FinFET Self-Aligned Quadruple Patterning Modeling](https://semiengineering.com/n7-finfet-self-aligned-quadruple-patterning-modeling/) — SISPAD 2018 paper, listed by Semiconductor Engineering. Advanced FinFET technologies use self-aligned quadruple patterning to define fins below the resolution of a single 193 nm immersion exposure; SAQP pitch variation (pitch walk) at an N7-class fin pitch.

- **R23** [SAQP Specs for 7nm finFETs](https://www.semiconductor-digest.com/saqp-specs-for-7nm-finfets/) — Semiconductor Digest. SAQP for fin patterning at a 7 nm-class FinFET node, and the core-dimension control it needs to keep pitch walk acceptable.

## Unverified historical credit

Earlier versions cited S. Rathore et al., Semiconductor Science and Technology (2021), without a title, DOI or figure number. The exact source has not been established. Retained here for provenance, not presented as a verified reference or silently replaced with a different paper.
