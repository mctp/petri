# Putting a data directory under git-lfs

By default git ignores everything under `data/`. Provenance is verified where the
data is, by `make check`, and no data is pushed. Git-lfs changes that for one
directory at a time.

Read this page before running the commands. Two of petri's own rules break
silently if you skip a step, and both failures appear as a hash mismatch rather
than as anything that names LFS.

## Which directory

| Directory | Size here | Regenerable | Track with LFS |
|---|---|---|---|
| `data/external/` | 228 MB, 19 files | no — the inputs collaborators sent | yes, the candidate |
| `data/shared/` | 7.3 MB, 15 files | yes, from external files and code | only to spare a collaborator a re-run |
| `data/preserved/` | 128 MB, 865 files | yes, from external files and code | no |
| `data/cache/` | 35 MB | yes | never |
| `data/notebook_htmls/` | 232 KB | yes | never |

LFS stores every version of every file it has seen. `git lfs prune` deletes local
copies only; the remote keeps all of them. So the cost of tracking a directory is
its size times the number of times its files change.

That is what rules `data/preserved/` out. Every notebook run rewrites it, so each
run would add its full size to the remote. `data/external/` changes only when
someone sends a new file, and petri cannot regenerate it, which is why it is the
one worth tracking. GitHub gives an account 1 GB of LFS storage and 1 GB of
bandwidth per month before charging. The largest input in this project is 100 MB,
so one version of it is a tenth of that.

## Setup

Once per machine:

```bash
git lfs install
```

Then, in the repository, in this order.

**1. Track the paths.** This writes `.gitattributes`, which is a tracked file:

```bash
git lfs track "data/external/**"
```

Add `-text` to each line it writes:

```
data/external/** filter=lfs diff=lfs merge=lfs -text
```

Without `-text`, git may normalize line endings on checkout. That changes the
bytes of the file, so every manifest that recorded its sha256 fails `make check`
on the machine that checked it out.

**2. Un-ignore the paths.** `.gitignore` ignores the contents of each `data/`
directory, and git never tracks an ignored file. After the `data/external/*`
line, add:

```
!data/external/**
```

`data/external/` is flat, which is what makes this work. A negation cannot
re-include a file inside a subdirectory that the `*` rule already excluded. If
you add subdirectories, ignore with `data/external/**` and re-include the exact
paths you want.

**3. Stop the formatting hooks from rewriting the files.**
`.pre-commit-config.yaml` excludes `data/preserved/` and `data/shared/` from
`end-of-file-fixer`, `trailing-whitespace` and `mixed-line-ending`.
`data/external/` is not in that list. Add it:

```
(petri/examples/)?data/(preserved|shared|external)/
```

One of those hooks appended a newline to a preserved file once and broke the
sha256 its own manifest recorded. On an input file the damage is worse, because
petri cannot regenerate it.

**4. Commit those three files first,** in one commit, before adding any data. A
file committed before its attribute exists is stored as an ordinary git blob, and
only `git lfs migrate import` moves it afterwards.

**5. Add the data:**

```bash
git add data/external
git lfs ls-files            # what LFS will store
git commit -m "data: track the external inputs with LFS"
```

## After a clone

`git clone` fetches LFS content when LFS is installed. When it is not, each
tracked file arrives as a text pointer of about 130 bytes. petri then fails in a
way that does not mention LFS:

- `load_external()` raises a parse error, or returns one row of nonsense.
- `make check` reports a content mismatch for every artifact built from that file.

The fix is `git lfs install && git lfs pull`. On a good checkout `git lfs ls-files`
lists the tracked files; `git lfs status` shows which are still pointers.

## Tracking a few files instead

For one file or two, skip steps 2 and 3 and force-add:

```bash
git add -f data/external/<file>
```

Attributes apply on `git add` whether or not the path is ignored, so the file
still goes to LFS. This keeps the default in place — nothing under `data/` is
tracked unless someone names it — and it is the smaller change when one
collaborator needs one input.
