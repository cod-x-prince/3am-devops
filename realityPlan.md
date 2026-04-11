# Reality Mode Plan

1. Replace synthetic incident generation with replayed incident traces.

- Build scenario inputs from real logs, metrics, and tickets from past incidents.
- Use timeline-based events, not only fixed severity overlays.

2. Add production constraints to action selection.

- Enforce cooldowns, blast-radius limits, dependency checks, and approval gates per action.
- Require the policy to justify each action against live symptoms and rollback risk.

3. Move scoring from visual/demo metrics to operational outcomes.

- Compute MTTR from real timestamps.
- Define false positives as actions without measurable recovery.
- Include SLO recovery and customer-impact minutes.

4. Validate on historical incident backtests.

- Replay 50-100 historical incidents.
- Compare against human runbooks for recovery time, wrong actions, and escalation rate.

5. Keep simulation, but split execution modes.

- Benchmark mode: synthetic incidents for fast iteration.
- Reality mode: trace replay + policy safety rails + full audit logs.
