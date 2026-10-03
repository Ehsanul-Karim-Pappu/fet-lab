# Work state

Released as 1.5.1 on 2026-10-03. The patent work this note used to track is finished: every
model and Process lesson follows its patent, checked figure by figure and against the text, and
`docs/PATENT_ALIGNMENT.md` records what each one draws and where the model makes its own
choices.

## Open for a later release

- Process lessons for the forksheet and the CFET. The forksheet lesson is written (after
  EP 3 989 273 A1) but is kept off main, ready to apply: its builder, planes, Why text, tests
  and docs, and the Device's site-length sub-fins.
- The web tour's Layers stop: lighting the model while the hand hides a group, and picking the
  group that covers most of the view, went off main with the same commit.
- A sequential-CFET inverter; the CFET Inverter and Layout scenes are built on the monolithic
  CFET.
- The Layout scenes' spans are schematic, not the Inverter scenes' numbers.
- R7's Intel link is an old press-release archive; search still indexes it at the same address,
  but it could not be opened to confirm.

## Rules that hold throughout

- Never make the 3D/2D viewing window shorter than it is now.
- Commits carry no Co-Authored-By line and no model name. The user pushes from Termux.
- Every build bumps `pwa/sw.js`. Set it back to one above the version on the branch's remote
  before committing.
