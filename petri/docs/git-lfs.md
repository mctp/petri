# Putting a data directory under git-lfs

By default git ignores everything under `data/`. Provenance is verified where the
data is, by `make check`, and no data is pushed. Git-lfs changes that for one
directory at a time.

Read this page before running the commands. Two of petri's own rules break
silently if you skip a step, and both failures appear as a hash mismatch rather
than as anything that names LFS.

There are two decisions here, not one: **which repository**, and **which
directory**. Take the repository first. It is what makes `data/preserved/` — the
results, the reason the project exists — worth tracking rather than out of the
question.

## Which repository

This template is boilerplate. Many projects clone it, and its history is shipped
to every one of them. One analysis's data does not belong in it: every clone
would download results it has no use for, and the template's LFS budget would be
spent by whoever pushed first.

A project that produces results wants a repository of its own. Two shapes, same
effect:

- **A fork of the template.** `origin` is the fork, `upstream` stays the
  template, so `git pull upstream main` still brings template improvements in.
- **A fresh repository with the template as an upstream remote.** No fork
  relationship on the host, otherwise identical.

Check before you track anything:

```bash
git remote -v
```

If `origin` is the template, stop and re-point it. Tracking data first and moving
the repository afterwards means the LFS objects were already pushed to the wrong
remote, and taking them out of a remote's history is a rewrite, not a delete.

## Which directory

| Directory | Size in one working project | Regenerable | Track with LFS |
|---|---|---|---|
| `data/external/` | 228 MB, 18 files | no — the inputs collaborators sent | yes |
| `data/preserved/` | 130 MB, 882 files | yes, but these are the results | yes |
| `data/shared/` | 7.3 MB, 14 files | yes, from external files and code | only to spare a collaborator a re-run |
| `data/cache/` | 38 MB, 135 files | yes | never |
| `data/notebook_htmls/` | 232 KB, 1 file | yes | never |

The two candidates are the two ends of the pipeline, and they are worth tracking
for opposite reasons. `data/external/` because petri cannot regenerate it:
regenerable is the wrong test for a file nobody can rebuild. `data/preserved/`
because it is the output people are here for — the figures that go into a draft
and the tables that get sent — and reproducing them from raw inputs costs a full
run of every notebook on a machine with the external data and a working `renv`.
A collaborator who wants to look at a figure should not need any of that.

The middle of the pipeline is the part to leave alone. `data/shared/` is cheap to
rebuild and only notebooks read it. `data/cache/` and `data/notebook_htmls/` are
build products.

Tracking `data/preserved/` does not change what it is for. It stays terminal: no
notebook reads another notebook's preserved artifact, under LFS or otherwise.
Promote a result with `save_shared()`.

## What tracking costs

LFS stores every version of every file it has seen. `git lfs prune` deletes local
copies only; the remote keeps all of them. So the cost of a tracked directory is
its size times the number of times its files **change** — not the number of times
a notebook runs.

That distinction is the whole case for `data/preserved/`. petri writes preserved
artifacts to be byte-stable across re-runs, on purpose:

- `_write_if_changed` hashes the payload and skips the write when it matches
  what is already on disk, so an unchanged artifact keeps its mtime.
- `preserve_figure` suppresses the timestamp matplotlib stamps into every
  format, and rejects a format it has no suppression key for.
- A manifest's `created` is copied forward from the previous manifest instead of
  being written again. Two fields that broke this rule — a `git_commit` of HEAD
  and a `tool` version — were removed for it.

Re-running a notebook that computed nothing new therefore produces no diff and no
new LFS object. What costs is a result that actually changed, which is the thing
you wanted versioned.

**The exception is a figure handed to `preserve_figure` as a `Path`.** That file
is copied byte for byte and keeps its renderer's timestamps; R's `pdf()` writes
both a CreationDate and a ModDate, so every run rewrites those bytes and every run
is a new LFS object. `preserve_figure`'s docstring already says to prefer PNG or
SVG from R. Under LFS the advice has a bill attached.

GitHub gives an account 1 GB of LFS storage and 1 GB of bandwidth per month before
charging. In the project tabulated above the two candidates were 228 MB and 130 MB,
so a first push of both is about a third of the storage, and each fresh clone
spends the same again out of the month's bandwidth.

## Setup

Once per machine:

```bash
git lfs install
```

Then, in the repository, in this order.

**1. Track the paths.** This writes `.gitattributes`, which is a tracked file:

```bash
git lfs track "data/external/**"
git lfs track "data/preserved/**"
```

Add `-text` to each line it writes:

```
data/external/**  filter=lfs diff=lfs merge=lfs -text
data/preserved/** filter=lfs diff=lfs merge=lfs -text
```

Without `-text`, git may normalize line endings on checkout. That changes the
bytes of the file, so every manifest that recorded its sha256 fails `make check`
on the machine that checked it out.

Keep the manifests out of LFS. They are ~1 KB of JSON each and the whole point of
committing them is that a reviewer can read the diff; through LFS every change
shows up as one opaque pointer line. Add a second line after the first — later
lines win per attribute, and the `-text` above still carries:

```
data/preserved/**/manifest.json !filter !diff !merge
```

`git check-attr filter -- <path>` confirms which files resolve to `lfs`.

**2. Un-ignore the paths.** `.gitignore` ignores the contents of each `data/`
directory, and git never tracks an ignored file. After the matching `data/<dir>/*`
line, add a negation:

```
!data/external/**
!data/preserved/**
```

The `**` is load-bearing for `data/preserved/`, which is nested — a directory per
notebook, a directory per cell. `data/preserved/*` excludes those per-notebook
directories, and git does not descend into an excluded directory, so the negation
has to re-include the directories as well as the files. `!data/preserved/**` does;
a narrower `!data/preserved/**/*.png` does not, and silently tracks nothing. To
track only some files under a nested directory, ignore with `**` and re-include
the directories on their own line first:

```
data/preserved/**
!data/preserved/**/
!data/preserved/**/*.png
```

**3. Stop the formatting hooks from rewriting the files.**
`.pre-commit-config.yaml` has a top-level `exclude:` that already covers
`data/preserved/` and `data/shared/`, keeping `end-of-file-fixer`,
`trailing-whitespace` and `mixed-line-ending` off them. `data/external/` is not in
that list. Add it:

```
(petri/examples/)?data/(preserved|shared|external)/
```

One of those hooks appended a newline to a preserved file once and broke the
sha256 its own manifest recorded. On an input file the damage is worse, because
petri cannot regenerate it.

`check-added-large-files` needs no change. It drops LFS-tracked files from its own
list before applying `--maxkb`, so the 1 MB cap never fires on anything under LFS.

**4. Commit those three files first,** in one commit, before adding any data. A
file committed before its attribute exists is stored as an ordinary git blob, and
only `git lfs migrate import` moves it afterwards.

**5. Add the data:**

```bash
git add data/external data/preserved
git lfs ls-files            # what LFS will store
git commit -m "data: track the inputs and the preserved results with LFS"
```

## When to commit preserved results

`data/preserved/` is the one tracked directory that changes as a consequence of
your own work rather than someone else's, so it is the one that needs a habit
rather than a rule.

Commit it when a result is worth keeping — a figure that went into a draft, a
table someone was sent — not reflexively after every run. The byte-stability
above means an unremarkable run costs nothing at all, but a run that legitimately
rewrites most of the directory and gets committed out of habit costs its full
size again. `git lfs ls-files` before the commit shows what is about to be
stored, and `git status` shows how much of the directory the run actually
touched.

## After a clone

`git clone` fetches LFS content when LFS is installed. When it is not, each
tracked file arrives as a text pointer of about 130 bytes. petri then fails in a
way that does not mention LFS:

- `load_external()` raises a parse error, or returns one row of nonsense.
- `make check` reports a content mismatch for every artifact built from that
  file, and for every preserved artifact that is itself a pointer.
- A preserved PNG or PDF simply will not open.

The fix is `git lfs install && git lfs pull`. On a good checkout `git lfs ls-files`
lists the tracked files; `git lfs status` shows which are still pointers.

## Tracking a few files instead

For one file or two, skip steps 2 and 3 and force-add:

```bash
git add -f data/external/<file>
git add -f data/preserved/<notebook>/<cell>/
```

Attributes apply on `git add` whether or not the path is ignored, so the file
still goes to LFS. This keeps the default in place — nothing under `data/` is
tracked unless someone names it — and it is the smaller change when one
collaborator needs one input, or when one figure is the deliverable and the
several hundred other files are not.
