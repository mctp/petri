# Vendoring the `marimo-pair` skill

The [`marimo-pair`](https://github.com/marimo-team/marimo-pair) skill is **vendored
into this repo** as a plain tracked directory at `.pi/skills/marimo-pair/`, rather
than as a git submodule.

## Why this is vendored, not a submodule

A parent git repo records only a submodule's commit SHA, never local edits. Any
change you make inside a submodule is lost on the next `git submodule update` or
on a fresh clone, and pushing it upstream needs rights you may not have.

Vendored files are ordinary versioned files in `petri`. The cost is that you
refresh the copy by hand, as described below.

## Layout

```
.pi/skills/marimo-pair/
    SKILL.md
    reference/*.md
    scripts/*.sh
```

pi discovers skills in `.pi/skills/`, so the vendored copy loads with no extra
configuration.

## Local changes manifest

Authoring inside the vendored tree is expected, not forbidden — the skill is the
right home for content about driving marimo. But a refresh cannot distinguish
your files from upstream's, so track them here. Keep this table current whenever
you edit or add a file under `.pi/skills/marimo-pair/`.

| Path | Status |
|---|---|
| `reference/execution-context.md` | **petri-authored.** Server/session/kernel/scratchpad model, frozen-snapshot rules, and what the `done` SSE event returns. Claims cite `marimo` source paths so they can be re-verified after a marimo upgrade. |
| `reference/connection-troubleshooting.md` | **petri-renamed.** Upstream content that shipped as `execution-context.md` while holding connection troubleshooting; renamed to match its subject and free the original name. |
| everything else | upstream as of the vendored snapshot. |

Check two known divergences on the next refresh:

- The marimo package bundles its own copy of this skill at
  `marimo/_server/ai/skills/marimo-pair/`. It uses `references/` (plural) with
  three files; the vendored copy here uses `reference/` (singular) with more.
  Which direction that drift runs is unverified — compare all three trees
  (GitHub, bundled, vendored) before writing a patch against any of them.
- `execution-context.md` and `connection-troubleshooting.md` are the two files a
  refresh is most likely to clobber or duplicate, since upstream may still ship
  the old name.

Send the split upstream: a file named `execution-context.md` should describe the
execution context. A PR to `marimo-team/marimo-pair` is better than carrying
these edits here.

## Updating from upstream

Fetch the latest upstream skill and replace the local copy:

```bash
make skills-update
```

This clones `marimo-team/marimo-pair` (shallow), copies `skills/marimo-pair/`
over `.pi/skills/marimo-pair/`, deletes the temp clone, and prints the resulting
`git status` so you can review.

It is **`rm -rf` then `cp -R`**, not a merge. Note what that means beyond
overwriting: a petri-only file — one upstream has no counterpart for, such as
`reference/execution-context.md` in its current form — is **deleted outright**,
not overwritten. It leaves no conflict marker and no trace in the new tree; the
only evidence is a deletion line in `git status`. Read that output for `D` lines,
not just `M` lines.

The copy **discards your local customizations**, so:

1. **Review the diff first:**
   ```bash
   git diff .pi/skills/marimo-pair
   ```
2. **Re-apply any customizations** you still want, working from the Local
   changes manifest above — that table is the list of what a refresh destroys.
   Common case: upstream documentation landed, and you want to fold your earlier
   notes into it rather than keep a divergent block.
3. **Update the manifest** if the refresh changed which files are local.
4. **Commit when satisfied:**
   ```bash
   git add .pi/skills/marimo-pair
   git commit -am "chore: update marimo-pair skill"
   ```

## Keeping local customizations on refresh

`skills-update` replaces the whole directory, so keep long-lived customizations
recoverable:

- Keep a patch, e.g. `scripts/patches/marimo-pair.patch`, and re-apply it with
  `git apply` after `make skills-update`.
- Or put them in a separate skill under `.pi/skills/<name>/` that extends
  marimo-pair, leaving the vendored copy untouched.
