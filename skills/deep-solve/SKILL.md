---
name: deep-solve
description: Runs a long, multi-angle attack on one hard problem using a persistent goal, parallel subagents, an on-disk ./.deep-solve/ workspace, the continual harness, and adversarial verification with a red-team child. Use when the user says "hard problem", "deep research", "multiple approaches", "try different angles", "unsolved", "keep trying until it works", "long-running investigation", or "/deep-solve", or when one direct attempt has already failed and the problem needs several independent attempts and a written record.
---

# Deep-solve

A method for problems that will not fall to one attempt. Expect several failed attempts. Expect to change the frame of the problem more than once. Success means: a solution that passes an independent check, plus a written record of what was tried, what failed, and why.

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

Only when the user explicitly asks for one. The `/deep-solve` template does ask ("I am asking for a persistent goal"). If the user only described a hard problem in natural language, ask once whether to start a goal; do not create one silently.

Create it with `await goal.create(objective)`. Write the objective yourself. It must contain:
- the problem in one or two sentences, using the exact technical vocabulary of the domain (distinctive terms, names, identifiers). The goal objective is the strongest signal the harness uses to rank which memories it shows you later (goal terms weight 3.0, see [H4]), so vocabulary matters;
- the concrete, checkable success criteria (what command, test, measurement, or proof decides "solved");
- the hard constraints (time, resources, what must not change).

Rules for the goal:
- The harness re-prompts you at every natural turn end until `await goal.complete()` is called [H1]. That is the engine of this run. End turns freely while children work; the goal brings you back.
- Three consecutive turns with no output (no text, no tool call) end the goal automatically [H2]. Every turn must do something observable.
- Call `goal.complete()` only after the audit in step 8 passes. Never because budget is low or you are tired of the problem.

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

## 5. Explore in parallel with subagents

For each round, spawn one child per selected angle (usually 3 to 5). Children run as independent sessions with their own context. The default RLM max depth is 2 [H3]: your children can spawn their own helpers, but grandchildren cannot. For deeper trees the user can raise it with `/rlm-max-depth 3`.

Use the `spawn_angle` wrapper from [references/spawn-angle.py](references/spawn-angle.py) so every child gets the same contract. The child contract is fixed. Every spawn prompt (wrapper or hand-written) MUST carry these lines verbatim:

> Every assistant message must include a tool call until you send your final reply via `await agent_message.send(<message>, receiver_role="parent")`. A text-only message ends your session and I receive nothing.
>
> Use at most {budget} tool calls. If you run out, stop and report what you have.
> Reply even if partial. A partial reply beats no reply.

Why: a child that ends a message with text and no tool call terminates its session, and the parent gets nothing.

The rest of the child brief: read `./.deep-solve/PROBLEM.md`; work only on the named angle; write method, commands, raw observations, result (supported / refuted / inconclusive), confidence, and next step to `attempts/<angle-id>/REPORT.md`; post `rlm.progress_note(...)` at milestones; final reply 10 lines max.

Orchestration rules:
- Spawn all children for a round in one REPL cell, then end your turn. Do not poll with sleeps. Replies arrive as messages; the goal continuation brings you back if nothing does.
- When you are back: `await rlm.collect(timeout_ms=0)` for a snapshot, then read each `REPORT.md` from disk. Never trust `status == "completed"` as proof of work. Check `replied_since_task` and the files.
- Use model diversity for diversity of thought: `await rlm.find_models("...")`, then pass an exact `selector` to one or two children. Different models fail differently.
- Follow up with a child instead of respawning when its context is valuable: `await agent_message.send(msg, receiver_role="child", receiver_name=name)`.
- Delete children only when their context is no longer needed: `await rlm.delete_subagent(child)`.
- If a round is long and nothing will wake you, set a heartbeat: `await rlm_heartbeat.create("check ./.deep-solve/attempts/*/REPORT.md, update LOG.md, launch the next round", interval="10m", label="deep-solve-round", delivery_mode="follow_up")`. Delete it when the run ends.

## 6. The round loop

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
- Before context runs low, at a natural boundary, call `await compact.run("keep: goal objective, current hypothesis statuses, paths under ./.deep-solve, child names, the verify command")`. REPL variables and helpers survive compaction except those over 16 MiB [H7]. Reload large data from disk.
- After compaction or any kernel restart, run `await rlm.list_subagents()` to recover child handles, and re-read `LOG.md`.

## 8. Verify like an adversary before you claim success

A plausible answer is not a solution. Before `goal.complete()`:

1. Run `./.deep-solve/verify.sh` yourself. It must exit 0. If the verifier is weak, strengthen it first.
2. Spawn one independent child named `red-team` that has not seen your reasoning. Brief: "Try to break this solution. Find inputs, cases, or assumptions under which it fails. Report any failure with a reproduction in `attempts/red-team/`." Same child contract as step 5 (verbatim tool-call rule, budget, reply even if partial).
3. Audit every success criterion in `PROBLEM.md` one by one and write the evidence path next to each in `SOLUTION.md`.
4. Only when all three pass: write `SOLUTION.md` (answer, how it was verified, what was tried and failed and why, remaining risks, how to reproduce), then `await goal.complete()`.

## 9. Reporting

Give short progress updates at round boundaries: what was tried, what was learned, what is running, what is blocked, and the next action. Lead with outcomes. Do not repeat unchanged status. If you need a decision or a fact from the user, ask one precise question and keep working on everything else.

Report every assumption you made and every constant you changed.
