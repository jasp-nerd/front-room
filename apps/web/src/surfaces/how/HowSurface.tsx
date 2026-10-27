import { FanFace, Helper, Pip, Wordmark } from "@frontroom/design";
import camera from "@frontroom/design/illustration/spot-camera.webp";
import investigate from "@frontroom/design/illustration/spot-investigate.webp";
import { CODE_URL, VIDEO_URL } from "../../links";
import styles from "./HowSurface.module.css";

/** Who does what, from the fan's phone to the TV. */
const pieces = [
  {
    art: <Helper id="ana" size={110} />,
    name: "A helper for each fan",
    kind: "A personal agent for each fan",
    body: "Builds a private profile from one sentence (“Solo lo importante, en español”) and asks for the TV on its fan's behalf. Only the helper knows what its fan said: Pip sees what it asks for, never why.",
  },
  {
    art: <Pip pose="whistle" size={110} />,
    name: "Pip, the referee",
    kind: "Room Director, an A2A agent",
    body: "Applies the house rules, then weights each ask by how long its fan has waited. Deterministic and auditable: same asks, same result, every time.",
  },
  {
    art: <img src={investigate} alt="" height={110} />,
    name: "The goal investigators",
    kind: "A seven-step Agent Framework workflow",
    body: "When a goal goes in, they work out where it started and write the TV's words in English and Spanish. A fact check rejects anything the match feed doesn't support.",
  },
  {
    art: <img src={camera} alt="" height={110} />,
    name: "The studio",
    kind: "For the broadcaster, with MCP tools",
    body: "Premier League Studio arms each moment once, with its languages and checked facts. Every living room then decides for itself.",
  },
];

const workflow = [
  ["Extract", "Rules", "Finds the possession that led to the goal."],
  ["Hypothesise", "Agent", "Proposes which actions mattered."],
  ["Experiment", "Value model", "Measures each action with a model fitted on real Premier League data."],
  ["Scrutinise", "Agent", "A skeptic argues against the hypothesis."],
  ["Verify", "Rules", "Keeps only what the event feed proves."],
  ["Write", "Agent", "Drafts the TV's words, in English and Spanish."],
  [
    "Fact check",
    "Rules",
    "Rejects unsupported names, numbers and claims. One revision, then a safe fallback.",
  ],
];

const rules = [
  ["Fair to both clubs", "Nothing one-sided while both clubs are on the sofa."],
  ["No spoilers", "Nothing reaches a phone before the TV has shown it."],
  ["Wait for VAR", "Nothing about a goal while it is being checked."],
  ["One at a time", "One thing on the TV, with a short break between."],
  ["Waiting counts", "The longer a fan has waited, the more their helper's ask counts."],
];

const measured = [
  {
    what: "Fans whose own pick reached them, on the TV or on their phone, 10,000 simulated matches",
    ours: "Every time",
    other: "421,152 of 421,152",
  },
  {
    what: "One-sided pictures on the TV while both clubs were on the sofa, 10,000 simulated matches",
    ours: "0",
    other: "16,194 if the loudest ask always won",
  },
  {
    what: "Longest wait before a fan's pick reaches the TV (95th percentile)",
    ours: "5 moments",
    other: "8 if the loudest ask always won",
  },
  {
    what: "Planted errors in the TV's words caught by the fact check",
    ours: "1,649 of 1,649",
    other: "No correct words rejected",
  },
  {
    what: "Live writer drafts that pass the fact check, on gpt-5.6-luna (10 goals)",
    ours: "10 of 10",
    other: "gpt-5.4 managed 8 of 10, so we moved the writer to luna",
  },
  {
    what: "Groundedness of the TV's words over 21 goals in real rooms, scored with the Azure AI Evaluation SDK by a separate gpt-5.4 in our Foundry project",
    ours: "4.14 / 5",
    other: "Fairness, privacy, spoiler and fact-check rules held in 21 of 21",
  },
  {
    what: "Red team: injections through fans' words, adversarial fans, a poisoned event feed",
    ours: "10 of 10",
    other: "Held in what the room uses; one injection fooled the model and was stopped by a check",
  },
  {
    what: "The value model picks the action that truly mattered most (280 goals it had never seen)",
    ours: "28%",
    other: "Assist 26%, regain 23%, random 21%",
  },
  {
    what: "Its “this one action decided it” verdict, checked against the simulator's ground truth",
    ours: "1 in 20",
    other: "So the TV never says it. It states only what the feed proves.",
  },
];

const stack = [
  [
    "Microsoft Foundry",
    "Our own Foundry project in Sweden Central: gpt-5.6-luna for the agents that reason and gpt-5.4-mini for the quick ones, both DataZoneStandard so prompts stay in the EU. The same resource screens fans' words with Content Safety and Prompt Shields and reads the story aloud with Speech. A separate gpt-5.4 deployment judges the evaluations. Every agent run is traced to Application Insights, which is connected to the Foundry project.",
  ],
  [
    "Microsoft Agent Framework",
    "The goal workflow, the personal helpers and their profilers, with structured outputs and OpenTelemetry traces. Checkpoints after every step, so an investigation cut off mid-way resumes where it stopped.",
  ],
  [
    "A2A",
    "Pip is an A2A agent at /a2a/director/, and the live room asks Pip over A2A. Helpers belong to fans and Pip belongs to the broadcaster: asks cross that line, profiles never do.",
  ],
  [
    "MCP",
    "Studio tools at /mcp/ (investigate a goal, read a room's ledger, a fairness report). Open the repository in VS Code and .vscode/mcp.json connects GitHub Copilot in agent mode to them.",
  ],
  [
    "Azure Cosmos DB",
    "Rooms, the fairness ledger of every decision, the as-run log of every cue and the workflow checkpoints. A restarted server picks up its rooms and their fairness clocks. Fans' words and profiles are never stored there.",
  ],
  [
    "Azure Event Hubs",
    "Ingestion for a live synthetic feed: a publisher streams the simulator's events in match time and the room server reacts to goals as they arrive. This public demo plays the packaged match instead, so a goal is ready when you click.",
  ],
  [
    "Azure Container Apps",
    "One container, deployed with Bicep (infra/) and always running, so nobody waits for it to wake up. Keys are Container App secrets, never in the repository.",
  ],
  [
    "GitHub Actions",
    "Every push runs the tests, the linters and two gates: no one-sided overlay in 10,000 simulated rooms, and every planted error caught by the fact check.",
  ],
];

const orchestration = [
  [
    "Distinct roles",
    "A helper per fan (a profiler and a personal agent), Pip the referee, and the goal investigation: hypothesis, skeptic and writer agents with a value model and a fact check.",
  ],
  [
    "Shared state",
    "Azure Cosmos DB holds each room, the ledger of every decision, the as-run log and the workflow checkpoints.",
  ],
  [
    "Handoffs",
    "Helpers send their asks to Pip over A2A. The investigation hands its checked story to the writer, and the writer's words go to the fact check before the TV.",
  ],
  [
    "Recovering from failures",
    "A helper that misses the 4-second deadline is left out and the room decides on time (see /room?dropped=sam). If Pip can't be reached within 2 seconds, the room applies the same rules itself. Every model step falls back to rules and says so in the trace, and an investigation cut off halfway resumes from its last checkpoint.",
  ],
];

const shipping = [
  [
    "One cue, many rooms",
    "Premier League Studio publishes each moment once, as a timed cue next to the world feed.",
  ],
  [
    "Drawn by the app",
    "Each broadcaster's streaming app, or Premier League+, draws the room's pick over the picture. Linear TV stays as it is.",
  ],
  [
    "Demand, not profiles",
    "The studio sees what rooms ask for, never what a fan said, and groups under 50 rooms stay hidden.",
  ],
  [
    "Back to the main feed",
    "The studio can clip an answer to a common question, or suggest it to the gallery for the world feed, so viewers without a helper benefit too.",
  ],
];

const screens = [
  ["/demo?live=1", "The live demo", "Every screen at once, following one real room."],
  ["/tv?state=join", "The TV before kick-off", "Scan to join."],
  ["/join?room=4821", "Joining on a phone", "One question at a time."],
  ["/phones", "Four phones", "What each of the four phones showed for the same goal."],
  ["/room", "The room's decision", "Who asked for what, and why one won."],
  ["/studio", "The studio", "What living rooms are asking to see, live, for the broadcaster."],
  ["/room?dropped=sam", "A late helper", "Sam's helper misses the deadline; the room still decides on time."],
  ["/phone?fan=rob&sheet=why", "Why this?", "How the room decided, as one fan's phone explains it."],
];

/** Real endpoints on the room server, for anyone who wants to talk to the agents directly. */
const endpoints = [
  ["/a2a/director/.well-known/agent-card.json", "The Room Director's A2A agent card"],
  ["/mcp/", "The studio's MCP server"],
  ["/health", "What this deployment runs on: Foundry models, Cosmos DB and Content Safety"],
];

/** The page for people who want the working: what each agent does, the rules, what we measured, the stack. */
export function HowSurface() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <a href="/" aria-label="Front Room, home">
          <Wordmark variant="lockup" height={24} />
        </a>
        <nav className={styles.headerNav} aria-label="More">
          <a href={VIDEO_URL} target="_blank" rel="noopener">
            Video
          </a>
          <a href={CODE_URL} target="_blank" rel="noopener">
            Code
          </a>
          <a className={styles.button} href="/demo?live=1">
            Watch a goal
          </a>
        </nav>
      </header>

      <main>
        <section className={styles.intro}>
          <h1 className={styles.headline}>How it works</h1>
          <p className={styles.lede}>
            A small team of AI agents in every living room, and a referee that keeps them fair. Here is what
            each one does, and how we checked them.
          </p>
          <div className={styles.faces} aria-hidden="true">
            {(["rob", "ana", "leo", "sam"] as const).map((id) => (
              <FanFace key={id} id={id} size={72} />
            ))}
          </div>
        </section>

        <section className={styles.section} aria-labelledby="pieces">
          <h2 id="pieces" className={styles.title}>
            Who does what
          </h2>
          <ul className={styles.pieces}>
            {pieces.map((piece) => (
              <li key={piece.name} className={styles.piece}>
                <div className={styles.pieceArt}>{piece.art}</div>
                <h3 className={styles.pieceName}>{piece.name}</h3>
                <p className={styles.kind}>{piece.kind}</p>
                <p>{piece.body}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className={styles.section} aria-labelledby="goal">
          <h2 id="goal" className={styles.title}>
            When a goal goes in
          </h2>
          <ol className={styles.workflow}>
            {workflow.map(([name, kind, what]) => (
              <li key={name} data-kind={kind}>
                <strong>{name}</strong>
                <span className={styles.badge}>{kind}</span>
                <span>{what}</span>
              </li>
            ))}
          </ol>
          <p className={styles.note}>
            Every model step has a rule-based fallback, so a room never waits on a model, and the trace says
            when one was used.
          </p>
        </section>

        <section className={styles.rulesField} aria-labelledby="rules">
          <Pip pose="whistle" size={140} className={styles.rulesPip} />
          <div>
            <h2 id="rules" className={styles.title}>
              Pip's house rules
            </h2>
            <dl className={styles.rules}>
              {rules.map(([name, what]) => (
                <div key={name}>
                  <dt>{name}</dt>
                  <dd>{what}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section className={styles.section} aria-labelledby="orchestration">
          <h2 id="orchestration" className={styles.title}>
            How the agents work together
          </h2>
          <dl className={styles.stack}>
            {orchestration.map(([name, what]) => (
              <div key={name}>
                <dt>{name}</dt>
                <dd>{what}</dd>
              </div>
            ))}
          </dl>
          <p className={styles.note}>
            The helpers, the investigators and the writer run on models. Pip's rules and the fact check are
            code, on purpose: the same asks always get the same answer.
          </p>
        </section>

        <section className={styles.section} aria-labelledby="measured">
          <h2 id="measured" className={styles.title}>
            Measured, not claimed
          </h2>
          <ul className={styles.measured}>
            {measured.map((m) => (
              <li key={m.what} className={styles.stat}>
                <strong className={styles.figure}>{m.ours}</strong>
                <span className={styles.what}>{m.what}</span>
                <span className={styles.other}>{m.other}</span>
              </li>
            ))}
          </ul>
          <p className={styles.note}>
            The ground truth comes from our simulator: it replays any moment with one choice changed. The
            evaluations are in agents/frontroom_agents/evals, and the README says how to rerun them.
          </p>
        </section>

        <section className={styles.section} aria-labelledby="stack">
          <h2 id="stack" className={styles.title}>
            Built on Microsoft
          </h2>
          <dl className={styles.stack}>
            {stack.map(([name, what]) => (
              <div key={name}>
                <dt>{name}</dt>
                <dd>{what}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className={styles.section} aria-labelledby="shipping">
          <h2 id="shipping" className={styles.title}>
            How a broadcaster would ship it
          </h2>
          <dl className={styles.stack}>
            {shipping.map(([name, what]) => (
              <div key={name}>
                <dt>{name}</dt>
                <dd>{what}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className={styles.section} aria-labelledby="screens">
          <h2 id="screens" className={styles.title}>
            Every screen
          </h2>
          <ul className={styles.screens}>
            {screens.map(([href, name, what]) => (
              <li key={href} className={styles.screen}>
                <a href={href}>{name}</a>
                <span>{what}</span>
              </li>
            ))}
          </ul>
          <ul className={styles.endpoints}>
            {endpoints.map(([path, what]) => (
              <li key={path} className={styles.endpoint}>
                <a href={path}>
                  <code>{path}</code>
                </a>
                <span>{what}</span>
              </li>
            ))}
          </ul>
          <p className={styles.note}>The code and the README are in the project's repository.</p>
        </section>
      </main>

      <footer className={styles.footer}>
        <p>
          The match data is synthetic: Kestrel FC, Ashvale Athletic and every player come from our simulator,
          SynthLeague. The value model is fitted on the Wyscout public dataset (Pappalardo et al., 2019, CC BY
          4.0), which calibrates and is never shown as match data. No league or club marks are used.
        </p>
      </footer>
    </div>
  );
}
