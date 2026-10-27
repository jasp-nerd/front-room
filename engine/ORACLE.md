# The origins oracle

For every goal in a set of simulated matches, the oracle measures how much each action in the scoring move really changed the chance, by replaying the match from that action with something else done instead. It reads the simulator's ground truth, so it is the answer key for any origins estimator that only sees the event feed.

```bash
uv run python -m frontroom_engine oracle --matches 35 --seed 1 --samples 8 --out data/generated/oracle
```

## Definition

The scoring move is every on-ball action of the scoring side in the possession that ended in the goal (passes, crosses, set-piece deliveries, carries, take-ons and the shot), plus the regain that started the possession if it was a tackle or an interception.

For an action backed by a decision, with options *i* offered at that moment with probabilities *p_i* by the decision model (the chosen option *c* included):

    tau = Q(c) - sum_i p_i Q(i)

where *Q(i)* is the expected outcome after forcing option *i*. The outcome *Y* is the physical xG (the simulator's own Monte Carlo shot probability) created by the scoring side minus the xG it conceded, over a fixed 15-second horizon from the decision. So *tau* is the action's advantage over what a typical player in the same spot, with the same view of the pitch, would have done. The baseline includes the chosen option because a typical player would sometimes have done the same thing. Options below 1 % probability are dropped, at most six are kept, and the weights are renormalised.

Each *Q* is the mean of K futures (`--samples`, default 8). Noise is resampled from the decision onwards; everything up to the moment of the decision stays exactly as it was. Future *k* uses the same noise for every option, so the K values of *Q(c) - sum p_i Q(i)* are paired samples of *tau*. The interval is a 95 % percentile bootstrap of their mean.

A regain is not a choice in this simulator (tackles and interceptions come from physics and hazard rates), so its *tau* is the difference between the futures where the player wins the ball and the same futures with that player kept off it for one second (`"intervention": "remove_regain"`). It answers a different question from the other rows and is labelled as such.

Verdict per goal: the action with the largest *tau* is **decisive** if *tau* >= 0.05 and its lower bound is above the upper bound of every other action; otherwise the goal is **shared**.

Actions with no decision behind them (first-time headers and volleys after a cross) cannot be swapped and are listed under `skipped` with the reason.

## Output

`oracle.jsonl` has one line per goal that stood; own goals and goals ruled out by VAR are excluded.

```json
{
  "matchId": "sl-cor-sto-1000",
  "matchDir": "data/generated/oracle/matches/sl-cor-sto-1000",
  "goalEventId": "ev-00872",
  "shotEventId": "ev-00871",
  "scoringSide": "home",
  "scorer": "cor-09-zielinski",
  "period": 1,
  "clockMs": 2484300,
  "actions": [
    {"eventId": "ev-00849", "type": "pass", "playerId": "cor-03-fairley", "intervention": "alternatives",
     "options": 6, "samples": 8, "tau": -0.0008, "low": -0.002, "high": 0.0}
  ],
  "skipped": [{"eventId": "ev-00869", "type": "cross", "reason": "..."}],
  "verdict": {"label": "shared", "decisiveEventId": null}
}
```

Event ids refer to `events.jsonl` in `matchDir`, which also holds `metadata.json` and `truth.json` (add `--tracking` for `tracking.parquet`). `summary.json` holds the counts and the wall time.

## Cost

A 15-second future takes about 50 to 80 ms. An action with six options at K = 8 needs 48 futures, about 3 s; a goal needs about 30 s. Each match is replayed once from kick-off to clone the state at every decision in its scoring moves. Matches run in parallel.

Measured with `--matches 35 --samples 8 --workers 7` (seed 1): 102 goals, 626 actions scored and 47 skipped, in 8.5 minutes wall time (about 35 CPU-seconds per goal including the match itself). Output is 112 MB without tracking.

In that run the median top *tau* per goal was 0.018 and 21 of 102 goals had a top action at 0.05 or more, but only 7 were decisive under the interval rule (4 tackles, 1 interception, 1 shot, 1 cross). The median interval width of the top action was 0.048, so K = 8 is the binding constraint: K = 24 would narrow intervals by about 1.7x for three times the cost.

## Limits

- The reference policy is the decision model itself, evaluated with the deciding player's own perception (scan radius, facing). It is a typical decision given what this player saw, not a league-average player in his boots.
- The fixed 15-second horizon credits early actions in a long move only through effects that show up within 15 seconds of them.
- With K = 8 the intervals are wide for actions near the shot, so most goals come out "shared". More samples narrow them linearly in cost.
- Off-ball work (runs, the press that forces a mistake without a tackle) is not an on-ball event and gets no row; the regain row is the closest proxy.
- The oracle uses the simulator's own physics and decision model, which is the point: it is ground truth for this generator, not a claim about real football.
