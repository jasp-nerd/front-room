# ProvenanceTokens

How the room decided, as anonymous dots: one per fan, robin for those who asked.

## Props

| Prop | What |
|---|---|
| `asked`, `inRoom` | How many asked, out of how many. |
| `size` | `tv` (18 px) or `phone` (14 px). |

## Brand rules it enforces

- Never names or clubs: the shared screen shows how many, not who.
- Decorative (`aria-hidden`); the sentence beside it carries the meaning.

## Usage

```tsx
import { ProvenanceTokens } from "@frontroom/design";

<ProvenanceTokens asked={3} inRoom={4} />
```
