# Issue tracker: Local Markdown

Specs (you may know a spec as a PRD) and their implementation issues live as markdown
files in `docs/plans/`. They are **tracked and committed** — a spec should survive, be
reviewable in a pull request, and be present in any `git worktree` you create.

`.scratch/` is gitignored and remains available for genuinely throwaway working state.
Do not put specs there.

## Conventions

- One feature per directory: `docs/plans/<feature-slug>/`, where the slug matches the
  tracker issue and the branch name, e.g. `10125-low-battery-recognition-based-on-aggregated-voltage-thresholds`
- The spec is `docs/plans/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at
  `docs/plans/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01` — never a single
  combined tickets file
- Triage state is recorded as a `Status:` line near the top of each file (see
  `triage-labels.md` for the role strings)
- Comments and conversation history append to the bottom of the file under a
  `## Comments` heading
- When work completes, move the directory to `docs/plans/archive/` and add a banner to
  the spec marking it historical. See `docs/plans/README.md`.

## When a skill says "publish to the issue tracker"

Create a new file under `docs/plans/<feature-slug>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue
number directly.

## Searching

`docs/plans/archive/` holds completed plans containing large embedded code listings, and
is the biggest source of false matches in this repo. When searching for a code symbol,
scope to `OTCamera/` and `tests/`, or exclude the archive:

```bash
rg '<symbol>' --glob '!docs/plans/archive/**'
```

## Wayfinding operations

Used by `/wayfinder`. These are ephemeral coordination files, not specs, so they stay in
the gitignored `.scratch/`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` — the Notes / Decisions-so-far / Fog body.
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.
