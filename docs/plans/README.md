# Plans

Specs for planned and in-progress work. One directory per feature, named after its
tracker issue:

```
docs/plans/
├── README.md
├── <issue>-<slug>/
│   ├── spec.md              ← the spec, with a Status: line near the top
│   └── issues/NN-<slug>.md  ← implementation tickets, if the spec is split up
└── archive/                 ← completed work, kept for its reasoning only
```

`Status:` values come from [../agents/triage-labels.md](../agents/triage-labels.md).
The vocabulary a spec uses is defined in [../../CONTEXT.md](../../CONTEXT.md), and
decisions worth preserving beyond a single spec live in [../adr/](../adr/).

These files are committed. They are tracked rather than kept in `.scratch/` so that a
spec survives, is reviewable in a pull request, and is present in a `git worktree` — a
gitignored spec is absent from every worktree you create.

## archive/

Completed work. **Nothing in `archive/` describes current intent**, and nothing there
should be executed. Each archived file carries a banner saying so, because the realistic
way an agent meets these documents is a grep landing mid-file, not a reader starting at
the top.

Be aware when searching: `archive/2026-03-27-v2-architecture-refactor-plan.md` is ~4,400
lines of embedded code listings, which makes it the largest source of false matches in
this repo. When searching for a symbol, prefer scoping to `OTCamera/` and `tests/`, or
exclude this directory:

```bash
rg 'is_low_battery' --glob '!docs/plans/archive/**'
```

When work completes, move its directory here and add a banner to the spec.
