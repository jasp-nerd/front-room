/** Everything the phone says, per language. Spanish is neutral Latin American: "ustedes", never "vosotros". */

export type Lang = "en" | "es";

export const copy = {
  en: {
    onTv: "On the TV",
    synced: (seconds: number) => `Synced, ${seconds} s behind live`,
    why: "Why this?",
    tellAgent: "Tell your helper",
    tellPlaceholder: "More like this",
    told: "Your helper will keep that in mind.",
    send: "Send",
    fromHelper: "Your helper sent this instead",
    onTvYourWay: "On the TV, your way",
    waitingTitle: "You're in the room",
    waitingLine: "Your helper is watching with you. Things show up here once the TV has shown them.",
    candidates: {
      "where-it-started": "Where it started",
      "kestrel-pressing-map": "Kestrel's pressing map",
      "keepers-view": "How Ashvale's keeper saw it",
      "player-okafor": "Okafor in numbers",
    } as Record<string, string>,
    myNumber: "Your number",
    following: "You follow",
  },
  es: {
    onTv: "En la tele",
    synced: (seconds: number) => `Sincronizado, ${seconds} s tras el directo`,
    why: "¿Por qué?",
    tellAgent: "Dile a tu ayudante",
    tellPlaceholder: "Más como esto",
    told: "Tu ayudante lo tendrá en cuenta.",
    send: "Enviar",
    fromHelper: "Tu ayudante te mandó esto",
    onTvYourWay: "En la tele, a tu manera",
    waitingTitle: "Ya estás en la sala",
    waitingLine: "Tu ayudante mira el partido contigo. Verás cosas aquí cuando la tele ya las haya mostrado.",
    candidates: {
      "where-it-started": "Dónde empezó",
      "kestrel-pressing-map": "La presión de Kestrel",
      "keepers-view": "Cómo lo vio el portero de Ashvale",
      "player-okafor": "Okafor en cifras",
    } as Record<string, string>,
    myNumber: "Tu número",
    following: "Sigues a",
  },
} satisfies Record<Lang, unknown>;
