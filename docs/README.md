---
tags: [index]
---

# c0mpiled_hackathon_2026 — start here

This folder is an Obsidian vault and the project's documentation. Open it
with **Open folder as vault** → `c0mpiled_hackathon_2026/docs`.

## Map

- [[PRODUCT_VISION]] — what we're building and in what order; where new ideas meet the rules
- [[ENGINEERING_DESIGN]] — the design of record: architecture, data model, build sequence, decisions
- [[COMPLIANCE_REQUIREMENTS]] — legal, tax and licensing requirements (R1–R31)
- [[gotchas]] — footguns, blocked paths, things that surprised us
- [[deploy]] — deploy the database, API and Lambdas with CDK
- [[local-loop]] — run the widget, the API and the dashboard together on one machine
- [[git-workflow]] — branches, pull requests and who owns what, so five people don't collide
- `decisions/` — one note per decision, created from [[decision|the decision template]] (none yet; the Decisions table in [[ENGINEERING_DESIGN]] holds them all so far)

## Conventions

- Link notes with `[[wikilinks]]`, not relative markdown links.
- Every note starts with frontmatter; `tags` at minimum.
- One topic per note. Add new notes to the map above.
- A change that alters behavior described in a note updates the note in the
  same commit.
