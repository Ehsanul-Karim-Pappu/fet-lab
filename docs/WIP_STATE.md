# Work state

Released as 1.4.0 on 2026-10-02. The patent work this note used to track is finished: every
model and Process lesson follows its patent, checked figure by figure and against the text, and
`docs/PATENT_ALIGNMENT.md` records what each one draws and where the model makes its own
choices.

## Open for a later release

- Process lessons for the forksheet and the CFET.
- A sequential-CFET inverter; the CFET Inverter and Layout scenes are built on the monolithic
  CFET.
- The Layout scenes' spans are schematic, not the Inverter scenes' numbers.
- R24–R27 name only "US patent" as their publisher; their assignees could be added. R7's Intel
  link is an old press-release archive and may have moved.

## Rules that hold throughout

- Never make the 3D/2D viewing window shorter than it is now.
- Commits carry no Co-Authored-By line and no model name. The user pushes from Termux.
- Every build bumps `pwa/sw.js`. Set it back to one above the version on the branch's remote
  before committing.
