# ScoreBug

The broadcaster's score bug, top left of the TV. It is part of the feed, not Front Room's: we never draw over it, replace it or put our logo beside it.

## Props

| Prop | What |
|---|---|
| `home`, `away` | `{ short, colour, ink, goals }`: three-letter name, club colour block, the ink that reads on it, goals. |
| `clock` | Match clock, e.g. `63:31`. |

## Brand rules it enforces

- Club colours appear as equal identification blocks for both clubs, never as one club's framing.
- Tabular figures, so the score and clock never jump.
- Inside the 90% title-safe area when placed at 96 px, 54 px on a 1080p frame.

## Usage

```tsx
import { ScoreBug } from "@frontroom/design";

<ScoreBug
  home={{ short: "KES", colour: "var(--club-kestrel)", ink: "var(--on-club-kestrel)", goals: 1 }}
  away={{ short: "ASH", colour: "var(--club-ashvale)", ink: "var(--on-club-ashvale)", goals: 0 }}
  clock="63:31"
/>
```
