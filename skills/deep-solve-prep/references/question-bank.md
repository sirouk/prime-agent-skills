# Question bank

Pick, do not recite. At most 5 per turn, numbered, each one chosen because its answer changes what you would write. Skip any you can answer yourself by reading the repo or listing a directory, and say that you did.

## Phase 1: Saturate

| Question | Why it matters |
|---|---|
| Where is the code now (repo, branch), and may I read it? | Facts beat recollection. Read first, then ask about what the code cannot tell you. |
| Tell me the story: where did this start, what changed, what works today, what hurts most? | Separates facts, beliefs, wants, constraints. Reveals the real pain, which is usually not the stated one. |
| What was tried and abandoned, and why? | Those are refuted hypotheses. They must not be re-run by a child. |
| Which parts do you trust completely and which do you suspect? | Trusted parts are "do not modify" constraints and known-good references. |
| What words do you use for the key concepts? Any of them overloaded? | Vocabulary goes into goal objectives and memory titles. Collisions with tool terms must be renamed. |
| What are the numbers you look at to decide something is good? | These become criteria. If there are none, the next phase will be hard; say so. |

## Phase 2: Decompose

| Question | Why it matters |
|---|---|
| Here are the N distinct things I heard you want. Which are right, which are missing, which are the same thing? | The user confirms the decomposition before any brief is written. |
| For each: is the answer already known (then it is engineering), unknown (research), a thing only you can decide (decision), or something that must exist first (prerequisite)? | Only research questions become briefs. The rest go in PLAN.md. |
| If we could answer only one question first, which one unblocks the most? | Usually the validation or measurement method. Without it, later verifiers are unfounded. |
| Which of these must never run without you pressing a button? | Human gates. Money, production, deletion, third parties. |
| Which items would you cut if you had half the time? | Reveals priorities and what "out of scope" should say. |

## Phase 3: Sharpen

| Question | Why it matters |
|---|---|
| Name one input you know is bad (overfit, broken, wrong) that the verifier must reject. | Known-bad reference. A verifier that never rejects anything proves nothing. |
| Name one input you trust that the verifier must accept, and the data it must be judged on. | Known-good reference and held-out data. |
| What number would make you say "yes, that is <durable / fast / correct>"? Over what window? On how many of the cases? | Turns an adjective into a criterion. |
| Where exactly is the data? Run `ls -la <path>` and `du -sh <path>` and paste the output. | Proves presence, size, format. "On the old machine" means a prerequisite, not an input. |
| What must the run not touch? | "Do not modify" list. |
| What is tempting but belongs to a different brief? | "Out of scope" list. Prevents scope creep mid-run. |
| How many rounds or hours is this worth before we stop and reassess? | Budget and cap behavior. |
| If verify.sh ran these checks (list them) and passed, would you believe the answer? | The final test of the criteria. A "no" means keep sharpening. |
| Which existing code must be reused, and which may be rewritten? | Prevents the run from re-implementing trusted components. |

## Phase 4: Review. Red flags

| Red flag | What to do |
|---|---|
| Purpose words in the question or criteria ("sustainable", "intelligent", "fruitful", "self-aware", "bless", "history"). | Move to CHARTER.md. Keep the question technical. |
| "And" in the question. | Split into two briefs. |
| An adjective with no number. | Ask for the number. |
| A criterion the agent could pass by changing the measurement. | Pin the measurement: the metric's code path, data split, and parameters are "do not modify". |
| Data "on another machine" or "I can get it". | Prerequisite. Brief is blocked until a path exists here. |
| Two briefs editing the same component. | Serialize them, or merge into one brief if the question is truly one. |
| "Deploy", "put capital to use", "delete the old", "email the team" inside a brief. | Human gate. Remove from brief; put in PLAN.md with "manual step". |
| "Make no mistakes", "be perfect", "the most intelligent approach". | Replace with checkable commitments: "every claim is backed by a test in the repo", "every negative result is recorded in LOG.md". |
| Tool vocabulary collisions (prime-agent: kernel, skill, goal, harness, memory, compact, refine). | Rename the user's concept in the brief and note the rename in CHARTER.md. |
| A brief longer than one screen. | It is a charter, not a brief. Decompose again. |
| "Ask me questions" or "when I say GO" inside a brief. | Prep is the conversation. The brief is fired after it. Remove the phase gates from the brief. |

## Phase 5: Hand off

| Question | Why it matters |
|---|---|
| Which prerequisites will you do before firing brief 1, and when? | Makes the plan real. |
| Do you want me to store the durable facts from NOTES.md as harness memories now, so the deep-solve run starts with them? | Local memories ranked by vocabulary surface in the run's digest. Ask; do not do it silently. |
| Shall I raise `/rlm-max-depth` to 3 for the run? | Only if briefs expect children to use helpers. Default 2 means children cannot spawn. |
