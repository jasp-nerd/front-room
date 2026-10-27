# LensStrip

Always at the top of a fan's phone, on one line: what the shared TV shows now, how far behind live, and "Why this?".

## Props

| Prop | What |
|---|---|
| `label`, `onTv` | "On the TV" and the overlay's title, in the fan's language. |
| `behind`, `sync` | Seconds behind live, and the same as a sentence for screen readers. |
| `why`, `onWhy` | The button's label and handler. |

## Brand rules it enforces

- The one robin mark on a phone's chrome, because the TV's choice is what the room shares.
- "Why this?" is a 44 px target.

## Usage

```tsx
import { LensStrip } from "@frontroom/design";

<LensStrip label="On the TV" onTv="Where it started" behind={38}
  sync="Synced, 38 s behind live" why="Why this?" onWhy={openWhy} />
```
