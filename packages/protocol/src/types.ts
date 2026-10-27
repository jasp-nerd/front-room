// Generated from packages/protocol/schema by scripts/generate-types.mjs. Do not edit.

export interface Bid {
  roomId: string;
  agentId: string;
  candidateId: string;
  utility: number;
  /**
   * True when the rendition favours one club.
   */
  partisan: boolean;
  /**
   * Presentation timestamp on the room's TV, in milliseconds from kick-off of the stream. Everything shown is scheduled against it.
   */
  placedAtPts: number;
}

/**
 * The TV's playback position, published several times a second.
 */
export interface Clock {
  roomId: string;
  /**
   * Presentation timestamp on the room's TV, in milliseconds from kick-off of the stream. Everything shown is scheduled against it.
   */
  pts: number;
  period: 1 | 2;
  /**
   * Match clock in milliseconds since the start of the period.
   */
  clockMs: number;
  playing: boolean;
  behindLiveMs: number;
}

/**
 * A timed, machine-readable instruction to show something. The same shape feeds the studio's graphics engine, the TV in a room and each phone.
 */
export interface Cue {
  cueId: string;
  insightId: string;
  template:
    | "where-it-started"
    | "player-tag"
    | "milestone"
    | "control-shift"
    | "caption"
    | "explainer"
    | "described-play";
  destination: "studio" | "room-tv" | "phone";
  /**
   * For phone cues: whose phone.
   */
  agentId?: string;
  /**
   * Presentation timestamp on the room's TV, in milliseconds from kick-off of the stream. Everything shown is scheduled against it.
   */
  pts: number;
  /**
   * Match clock in milliseconds since the start of the period.
   */
  clockMs?: number;
  smpteTc?: string;
  dwellMs: number;
  lang: string;
  /**
   * Template fields, already written for this audience and language.
   */
  fields: {
    [k: string]: string | number | boolean;
  };
  /**
   * The Room Director decision that put it on a room's TV.
   */
  decisionId?: string;
  state: "proposed" | "armed" | "on-air" | "held" | "retracted";
  verified: boolean;
}

/**
 * One allocation of the shared screen, written to the room's ledger.
 */
export interface Decision {
  roomId: string;
  decisionId: string;
  /**
   * Presentation timestamp on the room's TV, in milliseconds from kick-off of the stream. Everything shown is scheduled against it.
   */
  pts: number;
  weights: {
    agentId: string;
    weight: number;
    secondsWithoutScreen: number;
  }[];
  candidates: {
    candidateId: string;
    rawScore: number;
    fairScore: number;
    struckBy?: "neutral-framing" | "captions-stay" | "one-overlay" | "min-gap" | "var-hold" | "spoiler-gate";
    won: boolean;
    /**
     * Fans whose agent wanted this at least half as much as their favourite.
     */
    askedBy?: string[];
  }[];
  deliveredPrivately: {
    agentId: string;
    candidateId: string;
  }[];
  decidedInMs: number;
}

/**
 * Something worth saying about a moment, with every fact traceable to feed events. Insights carry facts, not finished sentences: each surface writes its own words.
 */
export interface Insight {
  id: string;
  matchId: string;
  kind: "where_it_started" | "player_tag" | "milestone" | "control_shift" | "explainer" | "described_play";
  /**
   * Presentation timestamp on the room's TV, in milliseconds from kick-off of the stream. Everything shown is scheduled against it.
   */
  pts: number;
  /**
   * @minItems 1
   */
  eventIds: [string, ...string[]];
  facts: {
    key: string;
    value: string | number | boolean;
    unit?: string;
    eventIds?: string[];
  }[];
  /**
   * Present for where_it_started.
   */
  origin?: {
    eventId: string;
    playerId: string;
    verdict: "decisive" | "shared";
    /**
     * Change in possession value against a typical player in the same spot.
     */
    valueAdded: number;
    /**
     * @minItems 2
     * @maxItems 2
     */
    interval?: [number, number];
    ruledOut?: string[];
  };
  confidence: number;
  verified: boolean;
  /**
   * Trace id of the agent run that produced it.
   */
  trace?: string;
}

/**
 * One on-ball action or match state change from the synthetic feed. Action types follow SPADL so the same models run on open data.
 */
export interface MatchEvent {
  id: string;
  matchId: string;
  /**
   * Order in the feed. Amendments reuse the seq of the event they replace.
   */
  seq: number;
  period: 1 | 2;
  /**
   * Match clock in milliseconds since the start of the period.
   */
  clockMs: number;
  side: "home" | "away";
  playerId?: string;
  type:
    | "pass"
    | "cross"
    | "throw_in"
    | "corner"
    | "free_kick"
    | "goal_kick"
    | "dribble"
    | "take_on"
    | "shot"
    | "penalty"
    | "keeper_save"
    | "tackle"
    | "interception"
    | "clearance"
    | "press"
    | "foul"
    | "card"
    | "substitution"
    | "goal"
    | "var_check"
    | "var_decision";
  result: "success" | "fail" | "offside" | "own_goal" | "none";
  start: PitchPoint;
  end?: PitchPoint;
  bodyPart?: "foot" | "head" | "other";
  /**
   * Type-specific extras: card colour, the target of a press, the outcome of a VAR decision.
   */
  detail?: {
    [k: string]: string | number | boolean;
  };
  /**
   * Set when this event corrects an earlier one.
   */
  amends?: string;
}
/**
 * Metres on a 105 × 68 pitch. x runs towards the away goal for the home side in the first half.
 */
export interface PitchPoint {
  x: number;
  y: number;
}

/**
 * Positions of all players and the ball at one instant (25 Hz in the feed).
 */
export interface TrackingFrame {
  matchId: string;
  frame: number;
  period: 1 | 2;
  /**
   * Match clock in milliseconds since the start of the period.
   */
  clockMs: number;
  ball: {
    x: number;
    y: number;
    z: number;
  };
  /**
   * @maxItems 22
   */
  players: {
    playerId: string;
    side: "home" | "away";
    x: number;
    y: number;
    /**
     * Metres per second.
     */
    speed: number;
  }[];
}
