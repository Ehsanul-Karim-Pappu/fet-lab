# Work in progress: following the patents

Paused on 2026-09-27, at the user's request, after task 2 (align the models and flows to the
patents). This note says what is done and what comes next, so the work can resume from here.

## The request

Scene models and Process flows follow one patent per technology, using its materials and steps.
Extra concept, teaching and reconstruction steps are allowed if they are correct or have another
supporting reference. The patents are R13 and R29–R35 in `data/references.json`; the mapping is in
`docs/PATENT_ALIGNMENT.md`.

## Done

1. **The patents were read and mapped** (`docs/PATENT_ALIGNMENT.md`).
2. **Models and flows follow the patents.** All scenes and flows build with at most one solid per
   voxel. All checks pass: tests, verify and the Kotlin check.
   - **Materials** in `build_devices.py`: sibcn, lowk, alox, soc, barc, sihm, wfill, cofill and
     copper.
   - **Nanosheet** [R13]: W fill, SiN SAC cap, SiBCN spacers, low-κ STI and inner spacers, and
     the patent's spacer-etch order. The ns, ns_p and ns_pair flows are rebuilt.
   - **FinFET** [R29, R30]:
     - Co fill with an AlOₓ hard mask, seal spacers, and SOC replacement contacts.
     - The fin, fin_p and fin_pair flows are rebuilt on the patent's steps.
     - The fin_pair gate cut is labelled as teaching.
   - **Forksheet:**
     - The Device follows imec [R31]: a common fill over the wall and a contact partition wall.
     - The Inverter follows TSMC [R35]: a gate bridge contact on the wall.
   - **CFET:**
     - Monolithic [R33]: pFET below, SiBCN between the tiers, front contacts.
     - Sequential [R34]: separate gates, an M66 Cu line, backside plugs.
     - Inverter: R33.
   - **Other code** now knows the new materials and nets: parasitics (EPS_R, gate and metal
     selectors), build_cmos nets and bridge, the Renderer ghost and texture sets, the Section
     keep-set, the web viewers, and the export_all/export_meshes metal sets.
   - **Text:** the forksheet and CFET stories and the COMMON materials paragraph are rewritten,
     along with the CFET Layout note and the nanosheet lesson label.
   - **Tests** are updated for the new materials, the figure statements and 35 references.
3. **References:** the R13 link is updated and R29–R35 are added, with no tracking parameters.
   Still to check: that they render in About and on the web page.

## Also done since the pause

- **#40:** About and the web page list all 35 references, read from the data, with no tracking
  parameters.
- **#41:** the Steps tab keeps only a "Show cross section · <plane>" button per plane.
- **#42:** the 2D section (`Section.kt`) has no layer list. A tap names the layer over the
  drawing; pinch zooms, drag pans, and double-tap or "Reset zoom" restores the view.
- **#43:** in Process on nanosheet, the compact site pill is on the left and the compact design
  pill on the right (`splitPills` in `AppUi.kt`).
- **#44:** Process's fifth tab is "Why". Its text is in `scripts/process_why.py`, one entry per
  flow, stored as `why` in process.json and loaded in `Scene.kt`. The test is
  `test_process_why`.

- **#45:** the guided tour ends with the Process stops `p_stepper`, `p_sites`, `p_planes` and
  `p_lessons`.
  - The Process-only tour (`process_tour` in `data/guide.json`) runs `p_stepper`, `p_sites`,
    `p_planes`, `p_secmode`, `p_locator`, `p_show`, `p_badge` and `p_lessons`.
  - It starts once, the first time Process is opened (`processTourSeen` in `Guide.kt`,
    `autoProcessTour` in `AppUi.kt`).
  - The finger waits less after each tap (`TourPlayer.tap`, `spot`, `moveHand`).
  - Not compiled here, since this container has no Android SDK. Check it with the Termux build.

## Remaining, in order

1. **#46:** final delivery.
   - Build on the phone and run the tours once.
   - Update the README.

## Rules that hold throughout

- Never make the 3D/2D viewing window shorter than it is now.
- Commits carry no Co-Authored-By line and no model name. The user pushes from Termux.
- Every build bumps `pwa/sw.js`. Set it back to one above the version on
  origin/finfet-process before committing (v58 → `fetlab-v59`).

## Exact next step

Start #46: fix anything the Termux build reports, then update the README.
