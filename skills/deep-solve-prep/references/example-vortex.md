# Worked example: a trading-system charter into briefs

The input was a one-page document the user called an "operating kernel" for a crypto trading system (QFL strategy, vectorbtpro + numba implementation, TradingView parity, ~40 coins). It had a MANDATE, SHAPE, MISSION, FLAWS, RISK SHAPE, NEED, seven listed purposes, and a two-phase instruction ("PRELOAD ... ask me questions" then "when I say GO ... maximum parallelism, make no mistakes"). The user asked: is this the right thing to feed `/deep-solve`?

## Why it was not fireable as written

| In the document | Conflict with `/deep-solve` |
|---|---|
| "Ask me questions" then "when I say GO" | The template says "do not ask clarifying questions up front; assume, record, start", and the goal re-prompts every turn. A human-gated two-phase flow and a continuous one-shot cannot both run. |
| Seven purposes: archaeology, audit, purge, data migration, redesign, deploy, trade | One question, one `verify.sh`. No script can verify "durable sustainable fruitful". Purge and migration are tasks, not hypotheses. |
| "Spin up the old machine with a TON of data, bring it over" | Children run experiments in round 1. Nothing is testable until the data is local. Prerequisite, needs the user. |
| "Deploy and put capital to use" | The template grants standing authorizations and says do not ask. Live capital must never sit behind "do not ask". Human gate. |
| "kernel" | In prime-agent, kernel means the Python REPL. Renamed to "Vortex core" in all briefs. |
| "Make no mistakes" | Not actionable. Replaced by "every claim is backed by a test in the repo". |

## Decomposition (Phase 2)

| Item from the document | Class | Where it went |
|---|---|---|
| Understand where Vortex came from; what was done over the years; where it ended up | Engineering (read-only survey) | PLAN.md phase 1: repo archaeology, feature inventory, test inventory, known bugs. One read-only child allowed. |
| Purge what is not needed | Engineering + decision | PLAN.md phase 3, after the ablation brief says what is needed. Deletion is a human gate. |
| Bring the data from the old machine | Prerequisite | PLAN.md phase 1, user does it. Blocks every brief. |
| Find a trusted set of out-of-sample tests (CPCV, walk-forward, perturbations) | Research | Brief DS-1. Runs first; everything else's verifier depends on it. |
| Which additions to base QFL (timeout, circuit breaker, stop loss, others) are necessary? | Research | Brief DS-2. Depends on DS-1. |
| 2 long + 2 short slots at 30-40% equity vs 2 slots at 20%? | Research | Brief DS-3. Depends on DS-1. |
| ROC / volatility regime filter to avoid crashes? | Research | Brief DS-4. Depends on DS-1. |
| Redesign a durable core architecture | Design | PLAN.md phase 3: proposer/critic pair on different models plus a reconciler. Not a `/deep-solve` brief: no `verify.sh` for an architecture. |
| Deploy, monitor, trade | Operations | PLAN.md phases 4-5. Paper trading first. Real capital behind a manual step, every time. |

## Brief DS-1 (sharpened; `<...>` are values only the user had)

````
/deep-solve Build the out-of-sample validation suite for the QFL strategy in Vortex (vectorbtpro + numba streaming implementation, TradingView-parity verified)

Context: read ./.deep-solve-prep/CHARTER.md and ./.deep-solve-prep/NOTES.md first. This brief is DS-1 of 4; it depends on nothing and every other brief depends on it.

Question: which combination of CPCV, walk-forward, PBO / deflated Sharpe, and perturbation tests (timeframe, leverage, safety-order ladder geometry) correctly separates durable QFL parameter sets from overfit ones across the 40-coin universe?

Success criteria (these become verify.sh):
1. Rejects the deliberately overfit set <name> (fit on <one coin>, <one window>) under CPCV and PBO at <threshold>.
2. Accepts the trusted set <name> on held-out <date range>.
3. Agreement with TradingView parity fixtures is unchanged (the strategy function's outputs on <fixture set> match to <tolerance>).
4. Every test has a unit test with a synthetic known-answer case (a planted-signal series the test must detect; a shuffled series it must not).
5. verify.sh completes in under <N> hours on this machine.

Inputs (all present on this machine now):
- <path>: OHLCV for <coins>, <timeframes>, <dates>, <format> (proved by: du -sh, ls)
- <repo> @ <commit>: trusted: the numba streaming strategy function and the TradingView parity fixtures.

Constraints:
- Do not modify the strategy function or the parity fixtures.
- Data is read-only.
- No exchange or network access.
- The metric definitions (Sharpe, drawdown, PBO) are pinned to <reference>; changing them is out of scope.

Out of scope: strategy changes, risk sizing, slot design, crash filters, deployment.

Known candidate hypotheses: CPCV with purging and embargo per De Prado; walk-forward with anchored vs rolling windows; PBO over the parameter grid; perturbation of timeframe (+/- one step), leverage (x0.5, x2), and ladder geometry.

Budget: 5 rounds. At the cap: write SOLUTION.md with the best supported suite and what was ruled out; report; do not call goal.complete() unless every criterion passes.

Human gates: none (read-only run).
````

## What the user had to answer before DS-1 was fireable

1. Repo location and branch; data location, format, size, and how to bring it here.
2. The one parameter set trusted most, and what it was fit on (becomes the known-good reference).
3. "Durable" as numbers: expectancy, max drawdown, window, how many of the 40 coins.
4. Exchange and whether a paper-trading path exists (for PLAN.md, not DS-1).
5. What must survive the purge no matter what (becomes "do not modify").
6. The rule for when real money is allowed, and whether it stays a manual step (recommended: yes, forever).

## Lessons this example teaches

- The user's most valuable material (vision, purpose, history) is also the material that must be kept out of the brief. CHARTER.md is where it lives; the brief cites it.
- The first brief is almost always "build the ruler". Nothing else can be verified until something trusted says good from bad.
- Prerequisites are not briefs. Data on another machine blocks everything and only the user can fix it.
- Anything touching money is a human gate, no matter how the user phrases the authorization.
