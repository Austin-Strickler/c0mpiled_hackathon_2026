---
tags: [howto, team]
---

# Git workflow for the team

Five people commit to one repo during the hackathon, and every push to `main`
deploys both front ends on Amplify ([[deploy]]). These rules keep us from
overwriting each other's work and keep `main` deployable.

## The short version

1. `main` is what's deployed. Nobody pushes to it directly; everything lands through a pull request.
2. One branch per person per task, named `<your-name>/<topic>`, made from an up-to-date `main`.
3. Pull `main` into your branch often (at least every hour) and before you open a PR.
4. Small PRs, merged quickly. A branch that lives all day turns into a merge conflict.
5. Say in the team chat which area you're in (see "Who owns what") before you start.

## Starting a task

```bash
git switch main
git pull --ff-only            # fails instead of making a merge commit if your main has drifted
git switch -c austin/widget-photo-upload
```

Never branch from someone else's open branch (CLAUDE.md: "Never stack a branch
on another open branch"). If you need their change, wait for it to merge, then
pull `main`.

## While you work

```bash
git add -p                    # stage what you meant, not every file you touched
git commit -m "widget: let the homeowner upload yard photos"
git fetch origin
git rebase origin/main        # or: git merge origin/main, if you'd rather not rebase
git push -u origin HEAD       # first push; later pushes are just `git push`
```

- Only rebase a branch that only you push to. If two people share a branch, merge, don't rebase.
- After a rebase you need `git push --force-with-lease`, never a plain `--force`. It refuses to push if someone else pushed in the meantime.
- Never force-push `main`.

## Opening and merging a pull request

- Open the PR against `main` as soon as something works; mark it draft if it's not done.
- CI (`.github/workflows/ci.yml`) runs typecheck, migrations and tests. Don't merge on red.
- Use **Squash and merge**, so each task is one commit on `main` and easy to revert.
- Delete the branch after merging.
- Anyone can merge their own PR during the hackathon. Get a second pair of eyes on anything that touches `packages/db/migrations`, `packages/pricing`, `infra/` or `amplify.yml`.

## Who owns what

Two people editing the same files is where conflicts come from. Claim an area
in chat before starting; if you need to change something in another person's
area, tell them first.

| Area | Paths | Conflict risk |
| --- | --- | --- |
| Homeowner widget | `apps/widget` | Medium: `screens.tsx` and `YardScreen.tsx` are large |
| Contractor dashboard | `apps/dashboard` | Medium |
| API contract | `packages/api-contract` | **High**: everything imports it. Change it in its own small PR, merge it first, then build on it |
| Lambdas | `services/lambdas` | Medium |
| Database | `packages/db` | **High**: see migrations below |
| Pricing | `packages/pricing` | Low, but it's the money; get a review |
| Infrastructure | `infra/`, `amplify.yml` | **High**: one person deploys at a time |
| Docs | `docs/`, `CLAUDE.md` | Low |

## Files that always conflict, and what to do

**Migration numbers.** Migrations are append-only and numbered
(`packages/db/migrations/0014_zip_centroid.sql` is the latest at the time of
writing). If two people both add `0015_...`, both merge cleanly and then one
never runs. Before adding a migration, pull `main`, take the next number, and
say it in chat ("I'm taking 0015"). If `main` gained that number while your PR
was open, rename yours to the next free one before merging. Never edit a
migration that's already on `main`.

**`package-lock.json`.** Don't fix its conflicts by hand. Take `main`'s copy
and regenerate:

```bash
git checkout origin/main -- package-lock.json
npm install
git add package-lock.json
```

**`packages/api-contract`.** A shape change breaks the widget, the dashboard and
the Lambdas together. Make the contract change in its own PR, merge it, and
let everyone pull before building on it.

## Deploys

- Amplify builds both front ends from `main` on every merge, so a broken merge is a broken live site. Run `npm run typecheck` and the relevant tests before you merge.
- Backend deploys (`cdk deploy`, the migrate Lambda) are by hand ([[deploy]]). Only one person deploys at a time: say "deploying" in chat, then "done".

## Claude Code and other agents

- Have an agent work on its own branch, the same as a person. Claude Code worktrees go under `.claude/worktrees/` (already in `.gitignore`), and `.worktreeinclude` copies `.env.local` into each one.
- Don't let an agent push to `main`, force-push, or edit a migration that's already merged. Review its diff before you open the PR.

## Machine setup

- **Windows:** keep Git's default `core.autocrlf=true`. The repo stores LF line endings and Git converts on checkout. If a diff shows every line of a file changed, it's line endings: stop and ask before committing.
- **Mac / Linux:** `core.autocrlf` should be `input` or unset.
- **Don't keep the repo in OneDrive, Dropbox or iCloud.** Sync clients lock and rewrite files inside `.git` and can corrupt it or leave `index.lock` files behind. Clone into a plain folder, e.g. `C:\dev\c0mpiled_hackathon_2026`.
- Set your name once so commits are attributable: `git config user.name "Your Name"` and `git config user.email you@example.com`.

## If something goes wrong

| Symptom | Fix |
| --- | --- |
| `fatal: Unable to create '.git/index.lock': File exists` | No other git is running? Delete `.git/index.lock` |
| Push rejected: "fetch first" / non-fast-forward | `git fetch origin && git rebase origin/main`, then push again |
| Push to `main` rejected (protected branch) | Working as intended: push a branch and open a PR |
| You committed to `main` locally by mistake | `git switch -c <name>/<topic>` (keeps the commit on a new branch), then `git switch main && git reset --hard origin/main` |
| Merge conflict you don't understand | `git merge --abort` or `git rebase --abort` gets you back to where you were. Then ask the person who owns that area |
