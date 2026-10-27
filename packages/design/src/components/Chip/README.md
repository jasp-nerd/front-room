# Chip

The state chip for a cue on its way to the rooms, used in the studio rundown.

## Props

| Prop | What |
|---|---|
| `state` | `drafted`, `checked`, `armed`, `on-tvs` or `done`. |
| `children` | The label. |

## Brand rules it enforces

- One shape and size for every state, louder as the cue gets closer to the rooms.
- Only "On TVs" is robin: that is what the rooms share. Nothing airs on its own; cues are armed.

## Usage

```tsx
import { Chip } from "@frontroom/design";

<Chip state="armed">Armed</Chip>
```
