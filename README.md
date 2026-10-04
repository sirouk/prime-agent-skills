# prime-agent-skills: a curated set of prime-agent skills with a one-line installer and self-update

Skills for [prime-agent](https://github.com/PrimeIntellect-ai/prime-agent). Each skill is a markdown skill (`skills/<slug>/SKILL.md`), optionally with a thin `/slug` prompt template (`prompts/<slug>.md`). The installer pins the exact commit it installs and writes a manifest with a sha256 snapshot into each skill. Each skill ships `scripts/update_check.py`, so the agent can check for and apply updates at the start of a run.

## Skills

| Slug | Purpose | Trigger phrases |
|---|---|---|
| `deep-solve` | Long, multi-angle attack on one hard problem: persistent goal, `./.deep-solve/` workspace, parallel subagents, continual harness, `red-team` verification. Slash command: `/deep-solve <problem>`. | "hard problem", "deep research", "multiple approaches", "try different angles", "unsolved", "keep trying until it works", "long-running investigation", "/deep-solve" |

## Install

One-liner. It installs every skill and prompt into `~/.prime/agent/`. It needs `python3`, plus `curl` and `tar`. No sudo.

```bash
curl -fsSL https://raw.githubusercontent.com/sirouk/prime-agent-skills/main/install.sh | sh
```

Options go after `-s --`:

```bash
# pick skills
curl -fsSL https://raw.githubusercontent.com/sirouk/prime-agent-skills/main/install.sh | sh -s -- --skills deep-solve
# list skills in the snapshot
curl -fsSL https://raw.githubusercontent.com/sirouk/prime-agent-skills/main/install.sh | sh -s -- --list
# project scope: ./.prime/agent/ in the current directory
curl -fsSL https://raw.githubusercontent.com/sirouk/prime-agent-skills/main/install.sh | sh -s -- --project
# uninstall (only skills and prompts this installer manages; unrelated skills are never touched)
curl -fsSL https://raw.githubusercontent.com/sirouk/prime-agent-skills/main/install.sh | sh -s -- --uninstall
```

Alternative: install as a package. Prime Agent auto-discovers the top-level `skills/` and `prompts/` directories, and the package route can auto-update. Copies installed this way have no manifest, so `update_check.py` reports `UNMANAGED` for them.

```bash
prime-agent package install https://github.com/sirouk/prime-agent-skills
```

After installing, run `/reload` in open prime-agent sessions.

### What the installer does

1. `install.sh` (POSIX sh) resolves `main` to a full commit (`git ls-remote`, with a GitHub API fallback) and downloads that exact commit's tarball.
2. `scripts/install.py` (stdlib Python 3.9+) copies each skill to a staging directory, writes `.prime-agent-skills-install.json` (`schema`, `skill`, `source`, `ref`, `commit`, `source_dirty`, `installed_at`, `files`), verifies the staged files against the sha256 snapshot, and swaps it in with `os.replace` (with backup and rollback).
3. Same files and same commit: `unchanged`. A skill you edited locally is `skipped` unless you pass `--force`. A directory with the same slug but no manifest is yours, not ours: it is `skipped` too, unless it is byte-identical to what would be installed (then it is adopted by adding the manifest) or you pass `--force`.
5. The same rule holds for prompts: a `prompts/<slug>.md` you wrote yourself, or one of ours you edited, is never overwritten or removed without `--force`.
4. Prompts are copied to `~/.prime/agent/prompts/` and recorded in `~/.prime/agent/skills/.prime-agent-skills-prompts.json`, so `--uninstall` knows what to remove.

Environment: `PRIME_AGENT_DIR` (default `$HOME/.prime/agent`), `PRIME_AGENT_SKILLS_SOURCE` (default `https://github.com/sirouk/prime-agent-skills.git`), `PRIME_AGENT_SKILLS_REF` (default `main`), `PRIME_AGENT_SKILLS_COMMIT` (pin a commit), `PRIME_AGENT_SKILLS_SOURCE_DIR` (install from a local checkout), `PRIME_AGENT_SKILLS_DEST` (skills destination; default `$PRIME_AGENT_DIR/skills`), `PRIME_AGENT_SKILLS_FORCE=1`. The owner/repo default is set once, at the top of `install.sh`.

### What it will never do

- Write outside `$PRIME_AGENT_DIR/skills/`, `$PRIME_AGENT_DIR/prompts/`, and a temp dir it removes on exit. No sudo, no shell profile edits, no settings changes.
- Replace or delete a skill or prompt it did not install, or one you edited, without `--force`.
- Run anything from the network except the pinned commit's `scripts/install.py`. The entrypoint resolves `main` to a commit first and downloads that commit's tarball, so the manifest's `commit` is always the code you got.
- Follow symlinks in skill directories (it refuses them).

Requirements: `python3` 3.9 or newer, `sh`. Remote install also needs `curl` and `tar`. `git` is optional (used to resolve the commit; the GitHub API is the fallback). Tested on Linux (dash, bash) and macOS in CI.

## Self-update

Each skill's `SKILL.md` has a `## Freshness` section. At the start of a run the agent executes `await bash("python3 <skill-dir>/scripts/update_check.py --apply")` once. It prints one status line:

| Token | Meaning |
|---|---|
| `UP_TO_DATE skill=... commit=...` | Installed commit is the latest. Continue. |
| `UPDATE_AVAILABLE skill=... installed=... latest=...` | Newer commit exists (shown when `--apply` is not given). |
| `UPDATED skill=... commit=...` | Applied the update at the exact latest commit and verified the files. The agent rereads the skill. |
| `LOCAL_DIRTY skill=... installed=... latest=... payload_dirty=... source_dirty=...` | Local edits (or a dirty source checkout at install time). Kept as is. |
| `UNMANAGED skill=... update_check=skipped` | No manifest. Not self-updated. |
| `ERROR skill=... reason=...` (exit 2) | For example `latest_commit_unavailable` (offline; the network guard is 10 seconds). |

Flags: `--apply`, `--force` (only with explicit user consent), `--from-checkout PATH` (use a local checkout as "latest").

## Usage: deep-solve

- `/deep-solve <problem>`: the slash command. It sets `PROBLEM`, asks the agent to load the skill, and gives permission to create a goal.
- `/skill:deep-solve`: load the skill directly.
- Natural language: describe a hard problem ("this is unsolved, try different angles, keep trying until it works"). Without the slash command, the agent asks before it creates a goal.

What the agent does:

1. Creates a goal with domain vocabulary, checkable success criteria, and constraints.
2. Creates the `./.deep-solve/` workspace and an early `verify.sh`.
3. Runs one understand-first round: baseline, check the givens, prior art, at least 5 hypotheses.
4. Generates different angles (decompose, invert, simplify, borrow, attack the assumptions, change the representation).
5. Spawns 3-5 subagents per round with the `spawn_angle` wrapper, then ends the turn. Reads each `REPORT.md` from disk.
6. Logs the round, updates hypotheses, and changes the frame if two rounds add no new evidence.
7. Runs `verify.sh`, spawns a `red-team` child, audits every criterion, writes `SOLUTION.md`, and only then completes the goal.

The workspace:

| Path | Purpose |
|---|---|
| `PROBLEM.md` | Problem, success criteria, constraints, assumptions. |
| `HYPOTHESES.md` | Angles with prediction, cost, status, evidence. |
| `LOG.md` | Append-only, one entry per round. |
| `attempts/<angle>/REPORT.md` | One directory per child attempt. |
| `evidence/` | Raw outputs and reproductions. |
| `verify.sh` | Exits 0 only when the criteria are met. |
| `SOLUTION.md` | Written last. |

Details: [skills/deep-solve/references/workspace-layout.md](skills/deep-solve/references/workspace-layout.md).

Recommended launch:

```bash
prime-agent --thinking max
# optional: start with a goal already set
prime-agent --thinking max --goal "<objective>"
```

The default RLM max depth is 2: children can spawn helpers, grandchildren cannot. For deeper trees, run `/rlm-max-depth 3` in the session.

### How deep-solve uses the harness

Verified against prime-agent 0.9.8. The full table with source files is in [skills/deep-solve/references/harness-mechanics.md](skills/deep-solve/references/harness-mechanics.md).

- The goal re-prompts the agent at each natural turn end until `goal.complete()` is called.
- 3 consecutive no-output turns end the goal.
- Default RLM max depth is 2.
- The harness digest shows the top 3 entries per kind, at 140 characters, ranked by goal terms (weight 3.0) and then the last 4 messages. So the goal objective and memory titles reuse the problem's vocabulary.
- Auto-refine runs about every 25 turns and at compaction, with a 20 minute cooldown, at depth 0 only.
- Compaction drops REPL variables over 16 MiB, so state lives on disk.
- A child that ends a message with text and no tool call ends its session. Every spawn prompt carries the tool-call rule, a tool-call budget, and "reply even if partial".

## Adding a skill to this repo

1. Create `skills/<slug>/SKILL.md`. The frontmatter `name` must equal the directory name. Add a `description` (under 1024 chars) with trigger phrases, and a `## Freshness` section like the one in `skills/deep-solve/SKILL.md`.
2. Optional: add `prompts/<slug>.md` (frontmatter `description` and `argument-hint`; body uses `$ARGUMENTS`). Keep it thin and point to the skill.
3. Copy the updater into the skill: `python3 scripts/sync_skill_payloads.py`. This writes `skills/<slug>/scripts/update_check.py` (mode 0755) from `scripts/skill_update.py`. Never edit the copies by hand.
4. Add a row to the Skills table above.
5. Run the tests: `python3 -m unittest discover -s tests -v`.

## Customize

Edit `skills/<slug>/SKILL.md` in your fork and change the source default at the top of `install.sh`. An edited installed copy is kept by the installer and the updater (`LOCAL_DIRTY`) until you pass `--force`.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 scripts/sync_skill_payloads.py --check
```

The suite uses throwaway git repos in temp dirs and never touches the network or your real `~/.prime/agent`.

## License

MIT. See [LICENSE](LICENSE).
