---
name: deep-solve
description: Runs a long, multi-angle attack on one hard problem using a persistent goal, parallel subagents, an on-disk ./.deep-solve/ workspace, the continual harness, and adversarial verification with a red-team child. Use when the user says "hard problem", "deep research", "multiple approaches", "try different angles", "unsolved", "keep trying until it works", "long-running investigation", or "/deep-solve", or when one direct attempt has already failed and the problem needs several independent attempts and a written record.
---

# Deep-solve

A method for problems that will not fall to one attempt. Expect several failed attempts. Expect to change the frame of the problem more than once. Success means: a solution that passes an independent check, plus a written record of what was tried, what failed, and why.

## Freshness

Resolve the directory containing this `SKILL.md`, then run its updater exactly once at the start of the invocation. In prime-agent, run it through the Python REPL as `await bash("python3 <skill-directory>/scripts/update_check.py --apply")`. The shell form is:

```bash
python3 <skill-directory>/scripts/update_check.py --apply
```

Resolve that path relative to this `SKILL.md`, not the working repository.

- `UP_TO_DATE`: continue.
- `UPDATED`: reread the updated `SKILL.md` and references from disk completely, then continue without restarting or asking.
- `LOCAL_DIRTY`: preserve the local skill, do not force an overwrite, state the skipped update briefly, and continue with the installed skill.
- `UNMANAGED`: continue; this copy is not self-updated.
- `ERROR`: state that freshness could not be verified and continue with the installed skill.

Never use `--force` unless the user explicitly authorizes overwriting local skill changes.

Facts about the harness (goal re-prompts, depth limit, digest ranking, auto-refine, compaction) are in [references/harness-mechanics.md](references/harness-mechanics.md). Facts cited below as `[H#]` point to rows in that table.

Reference files:
- [references/workspace-layout.md](references/workspace-layout.md): the `./.deep-solve/` directory contract and a minimal `verify.sh`.
- [references/spawn-angle.py](references/spawn-angle.py): the `spawn_angle` wrapper. Paste it into the REPL once.
- [references/harness-mechanics.md](references/harness-mechanics.md): verified prime-agent 0.9.8 facts and their sources.

PROBLEM: the user's request. If it is empty or incomplete, the full statement is in the next user message or in `./.deep-solve/PROBLEM.md`. Read it before anything else.

## Decision flow

1. Start a persistent goal (needs the user's explicit permission, see step 1).
2. Create the on-disk workspace.
3. Understand before you solve (one round, no solving).
4. Generate angles. Rank by information gain per cost.
5. Spawn one child per angle. End the turn.
6. Collect, read reports from disk, write one `LOG.md` entry, update `HYPOTHESES.md`.
7. Loop 4-6. Apply the anti-circling rules.
8. Verify adversarially. Only then `goal.complete()`.
9. Report.

## 1. Start a persistent goal

Only when the user explicitly asks for one. The `/deep-solve` template does ask ("I am asking for a persistent goal"). If the user only described a hard problem in natural language, do not create one silently: ask in one line ("Start a persistent goal for this so I keep going across turns? Reply yes, or run `/deep-solve <problem>`."), and in the same turn start steps 2 and 3, which need no goal. Create the goal when the answer arrives.

Create it with `await goal.create(objective)`. Write the objective yourself. It must contain:
- the problem in one or two sentences, using the exact technical vocabulary of the domain (distinctive terms, names, identifiers). The goal objective is the strongest signal the harness uses to rank which memories it shows you later (goal terms weight 3.0, see [H4]), so vocabulary matters;
- the concrete, checkable success criteria (what command, test, measurement, or proof decides "solved");
- the hard constraints (time, resources, what must not change).

Before creating it, run `await goal.get()`. If a goal already exists (`active`, `paused`, or `budget_limited`), `goal.create()` fails [H12]. Do not work around it: tell the user in one line to run `/goal clear` (or `/goal resume` if they want the old one), then wait. A `complete` or `error` goal is replaced automatically.

Rules for the goal:
- The harness re-prompts you at every natural turn end until `await goal.complete()` is called [H1]. That is the engine of this run. End turns freely while children work; the goal brings you back. Every continuation prompt tells you to audit the objective before completing; obey that literally.
- Three consecutive turns with no output (no text, no tool call) end the goal automatically [H2]. Every turn must do something observable.
- Call `goal.complete()` only after the audit in step 8 passes. Never because budget is low or you are tired of the problem.

After the goal exists, write one local memory immediately: `anchor = rlm.harness.create_memory("deep-solve: <problem's distinctive terms>", "<workspace path>; verify command; round 0", id="deep-solve-run", path="deep-solve/run")`. Its title shares vocabulary with the goal objective, so it ranks into the digest after every compaction and becomes your anchor. Update that same entry at each round boundary (`rlm.harness.update_memory("deep-solve-run", title, content)`) with the round number and the current best hypothesis; do not create a new one per round.

## 2. Set up the on-disk workspace first

Context will be compacted. REPL variables above 16 MiB are dropped at compaction [H7]. Children cannot see your context. So the problem state lives on disk, not in your head.

Create `./.deep-solve/` (or the directory the user names) as described in [references/workspace-layout.md](references/workspace-layout.md): `PROBLEM.md`, `HYPOTHESES.md`, `LOG.md`, `attempts/<angle-id>/REPORT.md`, `evidence/`, `verify.sh`, `SOLUTION.md`.

Write `verify.sh` as early as you can, even if it checks only part of the criteria. It exits 0 only when the success criteria are met. It is the single source of truth for completion.

Keep a small Python helper set in the REPL (`log(entry)`, `add_hypothesis(...)`, `read_reports()`) so bookkeeping costs one call.

## 3. Understand before you solve (one round, time-boxed)

- Restate the problem in your own words in `PROBLEM.md`. List every unknown and every assumption.
- Run the cheapest experiments that establish a baseline: reproduce the failure, measure the current state, confirm the inputs are what the problem says. Many hard problems are hard because one stated fact is false. Check the givens.
- Use `websearch` for prior art, known results, named techniques, and standard failure modes of this class of problem. Record sources in `evidence/`.
- Decide what counts as evidence for or against each hypothesis before you collect it.
- Do not start solving in this round. Produce `PROBLEM.md`, a first `verify.sh`, and at least five entries in `HYPOTHESES.md`.

Gate: do not spawn any angle child until all three exist on disk and `PROBLEM.md` has a "Success criteria" section with at least one criterion that `verify.sh` checks. Check this with Python, not by memory.

## 4. Generate angles, not just attempts

Before each exploration round, make sure `HYPOTHESES.md` contains approaches that are genuinely different, not variations of one idea. Use these lenses:

- decompose differently: by component, by data flow, by time, by failure boundary;
- invert: assume the solution exists and ask what must be true, then test those necessities;
- simplify: build the smallest version of the problem that still fails, solve that first;
- brute force or exhaustive search where the space is small enough; empirical probing where theory is unclear;
- borrow: name a solved problem with the same shape in another field and port its method;
- attack the assumptions: which "given" would, if false, make this easy? Test it;
- change the representation: different data structure, coordinates, encoding, or level of abstraction;
- ask what an expert from a different discipline would try first.

Rank hypotheses by expected information gain per unit cost. Run cheap, high-information probes first, even when they are unlikely to solve the problem outright. A refuted hypothesis is progress; record it as such.

Gate: before spawning a round, write one line in `LOG.md` per selected angle stating which lens produced it. If two selected angles share the same lens and the same inputs, replace one.

## 5. Explore in parallel with subagents

For each round, spawn one child per selected angle (usually 3 to 5). Children run as independent sessions with their own context. The default RLM max depth is 2 [H3]: your children can spawn their own helpers, but grandchildren cannot. For deeper trees the user can raise it with `/rlm-max-depth 3`.

Use the `spawn_angle` wrapper from [references/spawn-angle.py](references/spawn-angle.py) so every child gets the same contract. Pass `evidence_for` and `evidence_against` for every angle (decided in step 3), `budget`, and optionally `model` and `thinking` for diversity; set `can_spawn_helpers=True` only when the user raised `/rlm-max-depth` to 3 or more. The file also defines `spawn_red_team(...)` for step 8. The child contract is fixed. Every spawn prompt (wrapper or hand-written) MUST carry these lines verbatim:

> Every assistant message must include a tool call until you send your final reply via `await agent_message.send(<message>, receiver_role="parent")`. A text-only message ends your session and I receive nothing.
>
> Use at most {budget} tool calls. If you run out, stop and report what you have.
> Reply even if partial. A partial reply beats no reply.

Why: a child that ends a message with text and no tool call terminates its session, and the parent gets nothing.

Children do not see your context, this skill, or the harness facts. They get only their own system prompt plus your brief, labeled `[task from parent]`. So the brief must be complete on its own. The rest of the child brief: read `./.deep-solve/PROBLEM.md` and `./.deep-solve/HYPOTHESES.md` first (one child's refuted angle must not be another child's starting point); work only on the named angle; what counts as evidence for and against it (decided by you in step 3); the budget in tool calls; write method, commands, raw observations, result (supported / refuted / inconclusive), confidence, and the single best next step to `attempts/<angle-id>/REPORT.md` as you go (not at the end); keep raw outputs in that directory; post `rlm.progress_note(...)` at milestones; final reply 10 lines max. Children run in the same working directory as you, so relative paths under `./.deep-solve/` resolve for them.

Tell each child what it may spawn. At depth 1 a child can spawn its own helpers (depth 2) only if the user raised `/rlm-max-depth` to 3 or more; with the default of 2 it cannot [H3]. State that in the brief so the child does not plan around helpers it cannot get.

Orchestration rules:
- Spawn all children for a round in one REPL cell, then end your turn. Do not poll with sleeps. Replies arrive as messages; the goal continuation brings you back if nothing does.
- When you are back: `await rlm.collect(timeout_ms=0)` for a snapshot, then read each `REPORT.md` from disk. Never trust `status == "completed"` as proof of work. Check `replied_since_task` and the files.
- Recognize the harness rows for children. `[child-exited: no-reply child:<name>]` means the child ended with a text-only message; its last text (up to 160 characters) is attached, and its `REPORT.md` may still be complete. `[child-failed child:<name>]` carries the error. `[child-exited: cancelled child:<name>]` follows your own `delete_subagent`. On `no-reply`, read the report first; follow up with `agent_message.send(..., receiver_role="child", receiver_name=name)` only if the report is missing or incomplete (the message wakes the idle child in its own context) [H11].
- Use model diversity for diversity of thought: `await rlm.find_models("...")`, then pass an exact `selector` to one or two children. Different models fail differently.
- Spend reasoning where it matters. Children inherit your thinking level. Give the analysis-heavy angles (invert, attack-the-givens, change-the-representation) `thinking="high"` or `"max"`, and the mechanical ones (reproduce, brute-force, measure) `"medium"` or `"low"`, so the round finishes sooner without starving the hard angles. An unsupported level fails the spawn; catch the error and retry without `thinking`.
- Follow up with a child instead of respawning when its context is valuable: `await agent_message.send(msg, receiver_role="child", receiver_name=name)`.
- Delete children only when their context is no longer needed: `await rlm.delete_subagent(child)`.
- You do not need a heartbeat to be woken. While any child is running or any background `bash()` handle is live, the goal continuation is held; it is delivered automatically when the last one settles [H10]. Child replies and `[child-exited ...]` notices also wake you. Do not create a `steer` heartbeat during a run; it interrupts your own turn. A `follow_up` heartbeat is only useful for a periodic status report to the user on a very long run (`await rlm_heartbeat.create("summarize ./.deep-solve/LOG.md progress for the user", interval="30m", label="deep-solve-status", delivery_mode="follow_up")`); delete it when the run ends.

## 6. The round loop

Set a budget in `PROBLEM.md` at the start: a maximum number of rounds (default 6) and, if the user gave one, a token or time budget. Write the round counter in `LOG.md`. At the cap, stop exploring, write `SOLUTION.md` with the best supported result and the open questions, and report to the user; do not call `goal.complete()` unless the criteria are met. A run that ends with a clear negative result and a map of what was ruled out is a successful one-shot; a run that dies silently is not.

Each round ends with one `LOG.md` entry and an updated `HYPOTHESES.md`. Then decide:

- supported hypothesis: push it toward a full solution; spawn a verifier (step 8) early;
- refuted hypothesis: record why, park it, promote the next angle;
- inconclusive: decide whether a cheaper or sharper probe exists; if not, park it.

Hard rules to prevent going in circles:
- No two attempts with the same method and the same inputs. To retry, state in `LOG.md` what is different this time.
- If two consecutive rounds add no new evidence, stop and change the frame. Go up one level: re-read `PROBLEM.md`, attack a given, shrink the problem, or search for prior art again. Write the frame change in `LOG.md`.
- If one missing fact blocks the headline fix, ship everything that does not depend on it and state the blocker in one line, naming exactly what is needed and who can supply it. Do not re-derive settled conclusions.
- Prefer deleting a wrong premise over patching around it.
- Record negative results with the same care as positive ones. The next session, or the next child, must not repeat them.

## 7. Use the continual harness while you work

The harness persists prompt notes, memories, skills, and subagent specs across compaction and, for global entries, across sessions. The digest at the top of context shows only the top 3 entries per kind, truncated to 140 characters, ranked by overlap with the goal objective (weight 3.0) and then the last 4 messages [H4]. So:

- Write memories with distinctive titles and ids that reuse the problem's vocabulary, so they rank when relevant. Keep each short and current; update instead of duplicating. Local by default: `rlm.harness.create_memory(title, content, path="deep-solve/<topic>")`. Global (`global_=True`) only for lessons that matter in other sessions.
- Call `await rlm.harness.search("<terms>")` when you need the full text of an entry. The digest is a hint, not the record.
- Call `await refine.run("<what you observed>")` after: a repeated failure, a tactic that worked twice, a child role you spawned twice with the same shape (it should become a subagent spec), a procedure you ran twice (it should become a skill). It returns immediately and runs at turn end.
- Auto-refine also runs on its own about every 25 turns and at compaction, with a 20 minute cooldown, at depth 0 only [H5]. Do not wait for it. Children (depth 1+) do not get it; they should not rely on it.
- Compaction is automatic when about 16k tokens remain, and the summarizer writes a fixed structure: `## Goal`, `## Constraints & Preferences`, `## Progress` (Done / In Progress / Blocked), `## Key Decisions`, `## Next Steps`, `## Critical Context` [H14]. Trigger it yourself at a round boundary when `(await compact.status())["percent"]` is above about 70, so the cut lands between rounds, not inside one. Pass instructions in that vocabulary: `await compact.run("Critical Context must list: the path ./.deep-solve and each file's role; every hypothesis id with its status; the names of running and finished children; the exact verify command; the REPL helper names log, add_hypothesis, read_reports, spawn_angle. Next Steps must name the next round's angles.")`. REPL variables and helpers survive compaction except those over 16 MiB [H7], but the cells that defined them are gone from context, so helper names must appear in the summary or you will redefine them.
- After compaction or any kernel restart, run `await rlm.list_subagents()` to recover child handles, and re-read `LOG.md`.

## 8. Verify like an adversary before you claim success

A plausible answer is not a solution. Before `goal.complete()`:

Optional, strongest form: once `verify.sh` is trustworthy, the user can turn it into a harness gate: `/autonomous on --gate "./.deep-solve/verify.sh" --max-continuations unlimited --max-turns unlimited --max-tokens unlimited --timeout-ms unlimited`. The harness then runs the gate after every turn, feeds you the failing output (up to 6000 characters) when it fails, skips re-running an unchanged workspace, and stops only when the gate passes or you stop it [H13]. The goal still has priority over autonomous continuation, so both run together. Suggest this to the user once, in one line, when `verify.sh` exists; do not enable it yourself.

1. Run `./.deep-solve/verify.sh` yourself. It must exit 0. If the verifier is weak, strengthen it first.
2. Spawn one independent child named `red-team` that has not seen your reasoning, with `spawn_red_team(solution_summary)` from [references/spawn-angle.py](references/spawn-angle.py). It runs `verify.sh` itself, lists the criteria `verify.sh` does not check, and writes a reproduction for every failure into `attempts/red-team/`. Prefer a different model than yours (`rlm.find_models`) so it has different blind spots. If it reports `broken`, go back to step 6 with its reproduction as a new hypothesis; if it reports criteria not covered, strengthen `verify.sh` first.
3. Audit every success criterion in `PROBLEM.md` one by one and write the evidence path next to each in `SOLUTION.md`.
4. Only when all three pass: write `SOLUTION.md` (answer, how it was verified, what was tried and failed and why, remaining risks, how to reproduce), then `await goal.complete()`.

## 9. Reporting

Give short progress updates at round boundaries: what was tried, what was learned, what is running, what is blocked, and the next action. Lead with outcomes. Do not repeat unchanged status. If you need a decision or a fact from the user, ask one precise question and keep working on everything else.

Report every assumption you made and every constant you changed.

The final message of the run, whether the goal completed or the round cap stopped it, has a fixed shape: the answer (or the best supported result and why it fell short); how it was verified (`verify.sh` result, red-team verdict); the angles tried with one line each (supported / refuted / inconclusive); remaining risks and open questions; the path to `SOLUTION.md` and `LOG.md`; how to reproduce. Lead with the answer.
