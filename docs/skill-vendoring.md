# Vendoring the `marimo-pair` skill

The [`marimo-pair`](https://github.com/marimo-team/marimo-pair) skill is **vendored
into this repo** as a plain tracked directory at `.pi/skills/marimo-pair/`, rather
than as a git submodule.

## Why this is vendored, not a submodule

A parent git repo records only a submodule's **commit SHA** — never local edits.
That means:

- Any customization you make inside a submodule (e.g. your additions to
  `SKILL.md`) is invisible to the parent repo and **lost** on the next
  `git submodule update` or on a fresh clone.
- Pushing those customizations upstream requires push rights you may not have.

Vendoring the files instead:

- Keeps your edits as **ordinary versioned files** in `marimo-pi` — no push
  rights, nothing dangles, and the template is self-contained for anyone who
  clones it.
- The only cost is that you must **manually refresh** the copy when you want
  upstream changes. That workflow is documented below.

## Layout

```
.pi/skills/marimo-pair/
    SKILL.md
    reference/*.md
    scripts/*.sh
```

pi discovers skills in `.pi/skills/`, so the vendored copy loads with no extra
configuration.

## Updating from upstream

Fetch the latest upstream skill and replace the local copy:

```bash
make skills-update
```

This clones `marimo-team/marimo-pair` (shallow), copies `skills/marimo-pair/`
over `.pi/skills/marimo-pair/`, deletes the temp clone, and prints the resulting
`git status` so you can review.

The copy **overwrites** your local customizations, so:

1. **Review the diff first:**
   ```bash
   git diff .pi/skills/marimo-pair
   ```
2. **Re-apply any customizations** you still want (they are lost on overwrite).
   Common case: upstream documentation landed, and you want to fold your earlier
   notes into it rather than keep a divergent block.
3. **Commit when satisfied:**
   ```bash
   git add .pi/skills/marimo-pair
   git commit -am "chore: update marimo-pair skill"
   ```

## Manual refresh (equivalent, without make)

```bash
tmp=$(mktemp -d)
git clone --depth 1 https://github.com/marimo-team/marimo-pair.git "$tmp/mp"
rm -rf .pi/skills/marimo-pair
cp -R "$tmp/mp/skills/marimo-pair" .pi/skills/marimo-pair
rm -rf "$tmp"
git status .pi/skills/marimo-pair
```

## Keeping local customizations on refresh

Because `skills-update` overwrites the whole directory, store any long-lived
customizations somewhere durable or re-apply them deliberately after each sync.
Options:

- Keep a patch of your additions, e.g. `scripts/patches/marimo-pair.patch`, and
  re-apply with `git apply` after `make skills-update`.
- Or maintain customizations as a separate skill in `.pi/skills/<name>/` that
  wraps/extends marimo-pair, leaving the vendored copy pristine.

Choose whichever fits; the important part is that customizations are never only
inside a submodule's working tree.
