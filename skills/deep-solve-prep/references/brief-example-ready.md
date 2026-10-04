# DS-1

```
/deep-solve Build the out-of-sample validation suite for the QFL strategy in Vortex (vectorbtpro + numba streaming implementation, TradingView-parity verified)

Context: read ./.deep-solve-prep/CHARTER.md and ./.deep-solve-prep/NOTES.md first. This brief is DS-1 of 4; it depends on nothing.

Question: which combination of CPCV, walk-forward, PBO / deflated Sharpe, and perturbation tests correctly separates durable (positive out-of-sample expectancy on at least 30 of 40 coins over 24 months) QFL parameter sets from overfit ones?

Success criteria (these become verify.sh):
1. Rejects the deliberately overfit set qfl-sol-2021q4 (fit on SOL, 2021-10..2021-12) under CPCV with PBO above 0.5.
2. Accepts the trusted set qfl-v7 on held-out 2024-01..2025-06 with out-of-sample Sharpe above 1.0.
3. Agreement with the TradingView parity fixtures is unchanged: outputs match fixtures/tv-parity to 1e-9.
4. Every test has a unit test with a synthetic known-answer case.
5. verify.sh completes in under 4 hours on this machine.

Inputs (all present on this machine now):
- /data/vortex/ohlcv: 40 coins, 1h and 4h, 2019-01..2025-09, parquet, 38 GB (proved by: du -sh /data/vortex/ohlcv -> 38G)
- /root/vortex @ main 9f3c2a1: trusted: the numba streaming strategy function and fixtures/tv-parity (proved by: git -C /root/vortex log -1)

Constraints:
- Do not modify the strategy function or the parity fixtures.
- Data is read-only.
- No exchange or network access.
- Metric definitions are pinned to vortex/metrics.py at 9f3c2a1.

Out of scope: strategy changes, risk sizing, slot design, crash filters, deployment.

Known candidate hypotheses: CPCV with purging and embargo; anchored vs rolling walk-forward; PBO over the grid; timeframe and leverage perturbation.

Budget: 5 rounds. At the cap: write SOLUTION.md with the best supported suite and what was ruled out; report; do not call goal.complete() unless every criterion passes.

Human gates: none (read-only run).
```
