# Pip

Pip, the robin who referees the room: the fair one who holds the remote, so everyone gets a turn. Drawn in a flat, mid-century cartoon style; the poses are cut from one generated sheet (illustration/source).

## Props

| Prop | What |
|---|---|
| `pose` | `neutral`, `wave`, `whistle`, `remote`, `cheer`, `think`, `phone` or `sleep`. |
| `size` | Height in pixels; the width follows the drawing. |
| `alt` | Empty by default: Pip decorates words that already say what is happening. |

## Brand rules it enforces

- One Pip per screen, on a colour field where possible: setup, the demo's story, empty states, kid mode.
- Pip wears the whistle and decides; the fans' helpers are robins in scarves (`Helper`), never Pip.
- Never on the TV during play, except the small whistle that signs the lower third.

## Usage

```tsx
import { Pip } from "@frontroom/design";

<Pip pose="whistle" size={140} />
```
