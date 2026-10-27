# Wordmark

The Front Room logo: Pip's head beside "Front Room" in Gabarito ExtraBold, set as outlines.

## Props

| Prop | What |
|---|---|
| `variant` | `wordmark` (the word alone) or `lockup` (Pip's head, then the word). |
| `reversed` | White letters, for the navy field and the video. |
| `height` | Height of the letters in pixels; the wordmark is never narrower than 96 px. |

## Brand rules it enforces

- The lockup heads every page and the TV's join screen. Never beside a score, never on the TV during play.
- Never recoloured, outlined, stretched or set in another face.
- Clear space: the height of Pip's head on every side.

## Usage

```tsx
import { Wordmark } from "@frontroom/design";

<Wordmark variant="lockup" height={24} />
```
