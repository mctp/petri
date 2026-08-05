# The `marimo-pair` fork

`petri/skills/marimo-pair/` began as a copy of
[marimo-team/marimo-pair](https://github.com/marimo-team/marimo-pair) and is now
petri's own fork. It is plain tracked files, not a submodule and not a synced
copy.

## Why a fork, not a submodule

A parent git repo records only a submodule's commit SHA, never local edits. Any
change made inside a submodule is lost on the next `git submodule update` or on a
fresh clone, and pushing it upstream needs rights you may not have.

## Why a fork, not a tracked copy

There is deliberately no refresh target. A refresh would be `rm -rf` then `cp -R`,
which deletes petri's own edits without a conflict marker — the only evidence
would be a `D` line in `git status`. Keeping the copy in sync by hand cost more
than it returned.

Edit these files like any others. petri owns them.

## What petri changed

| Path | Change |
|---|---|
| `reference/execution-context.md` | Written for petri: the server/session/kernel/scratchpad model, frozen-snapshot rules, and what the `done` SSE event returns. Claims cite `marimo` source paths so they can be re-checked after a marimo upgrade. |
| `reference/connection-troubleshooting.md` | Upstream content that shipped under the name `execution-context.md` while holding connection troubleshooting. Renamed to match its subject. |
| `SKILL.md` | Cross-references updated for the rename above. The word "artifact" removed: upstream used it for the `.py` file, while in petri an artifact is a file written with a manifest. Scratchpad semantics moved into `reference/execution-context.md`, leaving the procedure here. |

## Comparing against upstream

The marimo package bundles its own copy at
`marimo/_server/ai/skills/marimo-pair/`, which uses `references/` (plural) with
fewer files than the fork's `reference/` (singular). To see what upstream has
changed since the fork:

```bash
tmp=$(mktemp -d)
git clone --depth 1 https://github.com/marimo-team/marimo-pair.git "$tmp/mp"
diff -ru "$tmp/mp/skills/marimo-pair" petri/skills/marimo-pair
rm -rf "$tmp"
```

Port anything worth having by hand.
