# Captions

Captions for everyone in the room, one line per language present. Never displaced by an overlay.

## Props

| Prop | What |
|---|---|
| `lines` | `{ lang, text }[]`, in the order to show them. |

## Brand rules it enforces

- Dark plate, white type: captions never glare in a dark room.
- All lines share one width; the second language steps back slightly.
- Each line carries its `lang` for screen readers.

## Usage

```tsx
import { Captions } from "@frontroom/design";

<Captions lines={[
  { lang: "en", text: "Replay of the build-up to Okafor's goal" },
  { lang: "es", text: "Repetición de la jugada del gol de Okafor" },
]} />
```
