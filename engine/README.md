# frontroom-engine

The synthetic data engine behind Front Room. It holds SynthLeague, a fictional 20-club league, and a physical match simulator that plays a full 90 minutes and writes what a real data provider would deliver: a 25 Hz tracking feed, an event feed with realistic labelling noise, and match metadata. It also writes what no provider can deliver: the latent truth behind every action, so analytics built on top can be graded rather than just shown.

Everything is seeded. The same seed gives byte-identical files.

## Running it

From the repository root, once:

```bash
uv sync --all-packages
```

Then:

```bash
uv run python -m frontroom_engine generate --seed 7 --out data/generated/seed-7
uv run python -m frontroom_engine generate --seed 7 --home KES --away ASH --out data/generated/kes-ash
uv run python -m frontroom_engine demo                      # Kestrel FC v Ashvale Athletic, the demo story
uv run python -m frontroom_engine scorecard --matches 50    # realism scorecard -> data/generated/scorecard
uv run python -m frontroom_engine calibrate --raw data/raw  # recompute reference stats (needs the raw data)
uv run python -m frontroom_engine oracle --matches 35         # ground-truth origins of every goal, see ORACLE.md
uv run pytest engine/tests
```

A match takes roughly 15 to 25 seconds on a laptop. The scorecard runs matches in parallel.

## Output

Each match directory holds four files.

- `metadata.json`: clubs, squads, formations, score, period lengths, attribution.
- `events.jsonl`: one `match-event` record per line (see `packages/protocol/schema`). A disallowed goal stays in the feed and is corrected by a later record with `amends`, the way live feeds work.
- `tracking.parquet`: one row per 25 Hz frame with list columns for the players on the pitch. `frontroom_engine.io.tracking_frame` turns a row into a `tracking-frame` record.
- `truth.json`: for every decision, the options the player weighed, their utilities and probabilities; for every shot, its physical xG; every offside margin and whether it was flagged; possessions and how they started; the planted player traits and team styles; and, for a steered match, the storyline and how it was steered.

## How the simulator works

SynthLeague gives every player physical and perceptual primitives instead of abstract ratings: top speed, acceleration, reaction time, scan radius, release time, pass-execution noise, first touch, finishing spread and a few duel skills. Every club has a style vector (directness, tempo, width, line height, press, risk) and a formation. Two clubs, Kestrel FC and Ashvale Athletic, and four of their players are fixed for the demo; the rest is drawn from the league seed.

The match runs at 10 Hz. Players are point masses steering towards targets with capped acceleration and top speed, and they respond to the ball as it was a reaction time ago. Off the ball, targets come from formation anchors that stretch and slide with the ball, from marking (goal-side and ball-side of the nearest opponent, with occasional lapses), from pressing (the nearest defender engages high up the pitch or after a trigger such as a heavy touch or a receiver facing his own goal, and otherwise contains; two players trap a carrier pinned near his own goal; a holding midfielder steps out to a carrier driving at him through the middle) and from timed runs in behind and into the box. The ball has its own physics: quadratic air drag, bounces and rolling resistance. One integrator moves it and also predicts it, so what players anticipate and what happens agree.

On the ball, the carrier chooses among about a dozen options: passes to the teammates he can see, long balls, crosses, a shot, carries, a take-on, holding the ball or a clearance. Each option's utility is perceived success times the value of the outcome minus perceived failure times the cost of losing the ball there. Values come from a hand-built pitch potential, never from xT or VAEP. Perceived pass success comes from time-to-intercept margins against the opponents in his field of view. The choice is a softmax over utilities, sampled with Gumbel noise from the noise tape.

Outcomes are physical. A pass is not decided when it is struck; the ball travels, the receiver and the opponents who can get there run to their earliest reachable point, and whoever is within reach gets a chance to control it, which falls with ball speed and rises with first-touch skill. Opponents need a reaction time before they can touch a fresh pass. Tackles happen when a defender is within reach of the ball, with fouls, cards, free kicks and penalties following from them. Shots get placement noise that grows with distance and pressure, can be blocked, and face a goalkeeper agent with reach, reaction time and handling. The latent xG of a shot is the Monte Carlo probability of a goal under that same physics. Offsides are judged by a noisy assistant referee, which is what lets VAR rule out a goal later in the same move.

All randomness comes from a keyed noise tape. Each value is addressed by purpose, tick and player instead of being drawn in call order, so a counterfactual replay that changes one action sees the same noise everywhere else. A branch can replace the noise from a given tick onwards, which is what storyline steering uses.

The simulation is then turned into feeds. Positions are interpolated to 25 Hz. Actions become SPADL-style events with labelling noise: coordinates on a coarse grid with jitter, timestamps that wobble, about one press in eight not logged, and the odd cross called a pass.

## Steering a storyline

`scenario.steer` makes a story happen without touching the physics. From a checkpoint it simulates several short futures (5 seconds each) on different branches of the noise tape, keeps the one that scores best on a progress function, and repeats until the beat's test passes. If it runs out of time it restarts with fresh branches, and a later beat that keeps failing backtracks into the earlier one. The demo story uses four beats: an unflagged Ashvale offside in the final third, the resulting goal ruled out by VAR, Mensah winning the ball from Lund near halfway after a press, and Okafor scoring from that possession after three to six passes.

The cost is honest but real. The kept match is a draw conditioned on the story, so the steered minutes are less typical than unsteered ones; the report gives the simulated time per kept minute and an upper bound on the information injected by selection (log of candidates per kept segment, in nats). The rest of the match is untouched. A found story is saved as a recipe (`demo_recipe.json`: seed plus branch points) and replays exactly; if the engine changes and the replay no longer contains the story, `demo` searches again and rewrites the recipe. Four players are kept on the pitch for the whole demo match, which is a direct intervention, not a selection.

## Calibration and the scorecard

`calibration/` computes reference statistics from open data and compares simulated matches against them. Event statistics come from the Wyscout public Premier League 2017/18 events (380 matches); physical statistics come from the seven DFL/IDSSE matches with 25 Hz tracking. The raw data stays in `data/raw` and is never committed; the aggregates are cached in `calibration/reference_stats.json`, so tests and the scorecard run without it. The open data is used only for these aggregate targets; nothing from it is used at runtime.

The scorecard checks about forty statistics with tolerances fixed in `calibration/scorecard.py`: event counts, pass accuracy by length band, pass and shot distances, conversion, results, inter-event timing, set pieces, distance covered, speed bands, sprints, team shape, ball-in-play share and ball speed. Wyscout counts duels twice and logs no carries or pressures, so "on-ball actions" leaves those out on both sides.

On 50 matches (seed 1) 33 of 39 checks pass. The six that fail: pass accuracy for passes of 30-40 m, 40-60 m and over 60 m (0.47, 0.41 and 0.19 against 0.76, 0.61 and 0.42), shots per match (32.3 against 22.2, though conversion and goals per match are in range at 8.7 % and 3.1), offsides (1.8 against 4.1) and sprints per player (11.4 against 8.8). Run `scorecard` to reproduce the full table.

## Known limits

- Players are points with no body orientation, so shielding, turning and blind-side runs are approximations, and there is no collision model beyond a carrier slowing when a defender stands in his path.
- Set pieces are simple: corners and free kicks use fixed box zones, there are no rehearsed routines, and throw-ins are short.
- Long-pass accuracy is below the reference. Part of it is how a failed pass is measured (to where the ball ended up, which for a mis-controlled pass can be far beyond the target), and part is that receivers mis-control fast balls too often. Making reception cleaner fixes the bands but removes too many throw-ins and shortens possessions, so it was left as is.
- Defenders see too little of the ball: the utility values progress more than retention, so centre-backs make a handful of passes a match where real ones make fifty. Adding an explicit value of possession fixed that but broke five other checks, so it was reverted.
- Offsides are rarer than in the Premier League reference (about 2 a match against 4), and teams shoot too often from poor positions (about 32 shots a match against 22).
- Team styles were chosen by hand and drawn from a simple distribution; they have not been fitted to real team aggregates, and they are not yet checked to be disjoint from the event-level generator (G_A) that does not exist yet.
- Physical targets come from seven German matches, event targets from one Premier League season, so the two are not from the same competition.
- Goalkeepers are the weakest agents: they position, sweep their box, catch, parry and punch, but they do not distribute with much intelligence.

## Attribution

Contains information derived from the Wyscout public dataset (Pappalardo et al., 2019, Scientific Data 6, 236, doi:10.1038/s41597-019-0247-7, CC BY 4.0) and the IDSSE dataset (Bassek et al., 2025, Scientific Data 12, 195, doi:10.1038/s41597-025-04505-y, CC BY 4.0; official match data provided by DFL / Sportec Solutions). Only aggregate statistics derived from them are stored here, and changes were made. All club and player names are fictional.
