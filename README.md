# prime-agent-deep-solve

A method for hard problems, packaged for [prime-agent](https://github.com/PrimeIntellect-ai/prime-agent). It has two parts: a `deep-solve` skill (the method) and a thin `/deep-solve` slash-command template that loads it. The agent starts a persistent goal, keeps its state in a `./.deep-solve/` workspace, attacks the problem from several different angles with parallel subagents, uses the continual harness to keep lessons, and checks its own answer with an adversarial `red-team` child before it calls the goal complete.

## Install

One-liner (copies the skill and the prompt into `~/.prime/agent/`; needs `curl` or `wget`, and `tar`; no sudo):

```bash
curl -fsSL https://raw.githubusercontent.com/sirouk/prime-agent-deep-solve/main/install.sh | bash
```

Alternative: install as a package. Prime Agent auto-discovers the top-level `skills/` and `prompts/` directories, and the package route can auto-update:

```bash
prime-agent package install https://github.com/sirouk/prime-agent-deep-solve
```

Project scope (installs into `./.prime/agent/` in the current directory):

```bash
curl -fsSL https://raw.githubusercontent.com/sirouk/prime-agent-deep-solve/main/install.sh | bash -s -- --project
```

Uninstall (removes `skills/deep-solve` and `prompts/deep-solve.md`; add `--project` for project scope):

```bash
curl -fsSL https://raw.githubusercontent.com/sirouk/prime-agent-deep-solve/main/install.sh | bash -s -- --uninstall
```

Installer settings (environment variables): `PRIME_AGENT_DIR` (default `$HOME/.prime/agent`), `DEEP_SOLVE_REPO` (default `sirouk/prime-agent-deep-solve`), `DEEP_SOLVE_REF` (default `main`), `DEEP_SOLVE_SOURCE_DIR` (install from a local checkout). To change the owner/repo for a fork, edit `DEEP_SOLVE_DEFAULT_REPO` at the top of `install.sh`.

After installing, run `/reload` in open prime-agent sessions.

## Usage

- `/deep-solve <problem>`: the slash command. It sets `PROBLEM`, asks the agent to load the skill, and gives permission to create a goal.
- `/skill:deep-solve`: load the skill directly.
- Natural language: describe a hard problem ("this is unsolved, try different angles, keep trying until it works"). The skill description routes the agent to it. Without the slash command, the agent asks before it creates a goal.

## What the agent does

1. Creates a goal with domain vocabulary, checkable success criteria, and constraints.
2. Creates the `./.deep-solve/` workspace and an early `verify.sh`.
3. Runs one understand-first round: baseline, check the givens, prior art, at least 5 hypotheses.
4. Generates different angles (decompose, invert, simplify, borrow, attack the assumptions, change the representation).
5. Spawns 3-5 subagents per round with the `spawn_angle` wrapper, then ends the turn. Reads each `REPORT.md` from disk.
6. Logs the round, updates hypotheses, and changes the frame if two rounds add no new evidence.
7. Runs `verify.sh`, spawns a `red-team` child, audits every criterion, writes `SOLUTION.md`, and only then completes the goal.

## The `./.deep-solve/` workspace

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

## Recommended launch

```bash
prime-agent --thinking max
# optional: start with a goal already set
prime-agent --thinking max --goal "<objective>"
```

The default RLM max depth is 2: children can spawn helpers, grandchildren cannot. For deeper trees, run `/rlm-max-depth 3` in the session.

## How it uses the harness

Verified against prime-agent 0.9.8. The full table with source files is in [skills/deep-solve/references/harness-mechanics.md](skills/deep-solve/references/harness-mechanics.md).

- The goal re-prompts the agent at each natural turn end until `goal.complete()` is called.
- 3 consecutive no-output turns end the goal.
- Default RLM max depth is 2.
- The harness digest shows the top 3 entries per kind, at 140 characters, ranked by goal terms (weight 3.0) and then the last 4 messages. So the goal objective and memory titles reuse the problem's vocabulary.
- Auto-refine runs about every 25 turns and at compaction, with a 20 minute cooldown, at depth 0 only.
- Compaction drops REPL variables over 16 MiB, so state lives on disk.
- A child that ends a message with text and no tool call ends its session. Every spawn prompt carries the tool-call rule, a tool-call budget, and "reply even if partial".

## Customize

Edit `skills/deep-solve/SKILL.md` (the method) or `prompts/deep-solve.md` (the launcher). The installer copies files, so re-run it after editing, or edit the installed copy in `~/.prime/agent/skills/deep-solve/`. The package route tracks the repo, so push your changes to your fork and install from it.
