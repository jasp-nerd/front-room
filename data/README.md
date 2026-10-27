# data/: open reference datasets for calibrating SynthLeague

These two datasets are used **only** to calibrate and validate the synthetic data generator
(G_A event model, G_B tracking simulation, the realism scorecard and TSTR checks; see
`IDEA.md` §7 and `research/synthetic_data.md` §1.3, §2.1 and §8). They are **never runtime match data**.
Nothing derived from them that ships may contain real player or club names.

`data/raw/` is git-ignored (`data/.gitignore`). Raw files must never be committed. Re-download them
with the script below.

| Dataset | What it is | Source (DOI) | Licence | On disk |
|---|---|---|---|---|
| `raw/wyscout/` | Wyscout public event dataset. 1,941 matches in 7 competitions, season 2017/18 (Premier League, La Liga, Serie A, Bundesliga, Ligue 1, World Cup 2018, Euro 2016), plus players, teams, coaches, referees and PlayeRank scores | Collection [10.6084/m9.figshare.c.4415000](https://doi.org/10.6084/m9.figshare.c.4415000); paper [10.1038/s41597-019-0247-7](https://doi.org/10.1038/s41597-019-0247-7) | CC BY 4.0 | 82 MB downloaded, 1.0 GB after unzip |
| `raw/idsse/` | Sportec Solutions / DFL "IDSSE" integrated dataset. 7 German matches from 2022/23 (2 Bundesliga, 5 2. Bundesliga): match information, official event data and **25 Hz** tracking (players and ball, with ball Z, speed, acceleration, ball status and possession), in DFL `PutDataRequest` XML | [10.6084/m9.figshare.28196177.v1](https://doi.org/10.6084/m9.figshare.28196177.v1); paper [10.1038/s41597-025-04505-y](https://doi.org/10.1038/s41597-025-04505-y) | CC BY 4.0 | 2.5 GB |

## Required attribution

Include this in any README, data card, parameter file (`params/*.json`) or publication that uses
anything derived from these files:

> Contains information derived from the Wyscout public dataset: Pappalardo, L., Cintia, P., Rossi, A.,
> Massucco, E., Ferragina, P., Pedreschi, D. & Giannotti, F. (2019). *A public data set of
> spatio-temporal match events in soccer competitions.* Scientific Data 6, 236.
> https://doi.org/10.1038/s41597-019-0247-7. Data: https://doi.org/10.6084/m9.figshare.c.4415000,
> licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
>
> Contains information derived from the IDSSE dataset: Bassek, M., Rein, R., Weber, H. & Memmert, D.
> (2025). *An integrated dataset of spatiotemporal and event data in elite soccer.* Scientific Data 12, 195.
> https://doi.org/10.1038/s41597-025-04505-y. Data: https://doi.org/10.6084/m9.figshare.28196177.v1,
> licensed CC BY 4.0. Official match data provided by Deutsche Fußball Liga (DFL) / Sportec Solutions.

CC BY 4.0 also requires stating that changes were made. Our derived artefacts are aggregate
statistics and fitted parameters, not the data itself. Say so in the data card.

## Files downloaded (2026-10-27, all MD5-verified against figshare `computed_md5`)

### Wyscout (`raw/wyscout/`)

| File | figshare article (DOI suffix) | Size | Notes |
|---|---|---|---|
| `events.zip` → `events/events_<Competition>.json` | Events, 7770599.v1 | 73.7 MB zip / 912 MB unzipped | `events_England.json` (180 MB) is the Premier League 2017/18 |
| `matches.zip` → `matches/matches_<Competition>.json` | Matches, 7770422.v1 | 630 KB / 8.8 MB | |
| `players.json` | Players, 7765196.v3 | 1.7 MB | |
| `teams.json` | Teams, 7765310.v3 | 27 KB | |
| `competitions.json` | Competitions, 7765316.v4 | 1.2 KB | |
| `coaches.json` | Coaches, 8082650.v1 | 69 KB | |
| `referees.json` | Referees, 8082665.v1 | 192 KB | **Truncated upstream.** The figshare file ends mid-record and is not valid JSON (MD5 matches figshare, so this is not a download error). About 627 records are present. We don't need it. |
| `playerank.json` | PlayeRanks, 9361148.v1 | 6.0 MB | |
| `eventid2name.csv`, `tags2name.csv` | 11743836.v1, 11743818.v1 | 1–2 KB | ID-to-name lookups for event types and tags |

Not downloaded: the data-paper PDF (11473374) and the plotting replication code (11473365). We never run third-party code.

### IDSSE (`raw/idsse/`)

Per match ID (`DFL-MAT-J03WMX`, `J03WN1` are Bundesliga, `DFL-COM-000001`; `J03WOH`, `J03WOY`, `J03WPY`, `J03WQQ`, `J03WR9` are 2. Bundesliga, `DFL-COM-000002`):

| File pattern | Count | Size |
|---|---|---|
| `DFL_02_01_matchinformation_<COM>_<MAT>.xml` (teams, line-ups, pitch size, result) | 7 | ~12 KB each |
| `DFL_03_02_events_raw_<COM>_<MAT>.xml` (official events, postmatch) | 7 | 0.6–0.76 MB each (4.6 MB total) |
| `DFL_04_03_positions_raw_observed_<COM>_<MAT>.xml` (25 Hz tracking) | 7 | 333–399 MB each (2.5 GB total) |

No file is larger than 3 GB, so nothing was skipped.

## Re-downloading

```bash
python3 -I data/download.py --dry-run                 # print the plan and sizes
python3 -I data/download.py                           # everything (~2.5 GB)
python3 -I data/download.py --dataset wyscout         # events only (82 MB)
python3 -I data/download.py --dataset idsse --no-tracking   # IDSSE without the 25 Hz XML
python3 -I data/download.py --verify                  # re-hash everything on disk
```

`download.py` uses only the standard library and a pinned manifest of figshare file IDs, sizes and MD5s.
It downloads from `https://ndownloader.figshare.com/files/<file_id>` to `*.part`, checks size and MD5,
then renames the file. Files already on disk with the right size are skipped (`--verify` also re-checks
their MD5). It refuses any file over 3 GB and unzips the Wyscout archives with a path-traversal guard.
The manifest came from `https://api.figshare.com/v2/articles/<article_id>`. If figshare publishes a new
version, update the manifest from that endpoint.

**Alternative for IDSSE:** kloppy (BSD-3) can fetch and parse the same files:
`kloppy.sportec.load_open_tracking_data(match_id="J03WMX")` and `load_open_event_data(...)`. kloppy is not
installed in this environment. Treat everything in `raw/` as untrusted data. Read it with `python3 -I` and
never execute anything from it.

## Sanity check

`python3 -I data/sanity_check.py` (stdlib, ~40 s; add `--skip-tracking` for ~5 s). Output on 2026-10-27:

| Wyscout competition | Matches | Events |
|---|---:|---:|
| **England (Premier League 2017/18, seasonId 181150)** | **380** | **643,150** (1,692/match; 328,657 passes, 8,451 shots, 1,018 goals = 2.68/match) |
| France | 380 | 632,807 |
| Germany | 306 | 519,407 |
| Italy | 380 | 647,372 |
| Spain | 380 | 628,659 |
| World Cup 2018 | 64 | 101,759 |
| Euro 2016 | 51 | 78,140 |
| **Total** | **1,941** | **3,251,294** |

The Wyscout reference files hold 142 teams, 3,603 players, 208 coaches and 46,897 PlayeRank rows.

| IDSSE match | Competition | Result | Events | 25 Hz frames (ball) |
|---|---|---|---:|---:|
| J03WMX | Bundesliga MD34 | 1. FC Köln 1:2 FC Bayern München | 1,715 | 145,967 |
| J03WN1 | Bundesliga MD34 | VfL Bochum 3:0 Bayer 04 Leverkusen | 1,363 | 141,561 |
| J03WOH | 2. Bundesliga MD6 | Fortuna Düsseldorf 4:0 Jahn Regensburg | 1,389 | 137,214 |
| J03WOY | 2. Bundesliga MD8 | Fortuna Düsseldorf 3:1 Hansa Rostock | 1,489 | 142,536 |
| J03WPY | 2. Bundesliga MD12 | Fortuna Düsseldorf 0:1 1. FC Nürnberg | 1,504 | 146,211 |
| J03WQQ | 2. Bundesliga MD15 | Fortuna Düsseldorf 1:0 FC St. Pauli | 1,586 | 142,345 |
| J03WR9 | 2. Bundesliga MD17 | Fortuna Düsseldorf 1:2 1. FC Kaiserslautern | 1,452 | 146,810 |
| **Total** | | | **10,498** | **1,002,644** (~11.1 h) |

Tracking holds 25 to 27 player objects per match, split across the halves. Referees are tracked only in
the two Bundesliga matches.

The scripts that computed the reference marginals in `research/synthetic_data.md` §1.4 and §2.4 are
`research/scripts/wy_marginals.py <raw/wyscout dir with events_England.json + matches_England.json>` and
`research/scripts/dfl_tracking.py <positions xml>`. Note that `wy_marginals.py` expects the England files
in one directory, but they now sit in `raw/wyscout/events/` and `raw/wyscout/matches/`.
