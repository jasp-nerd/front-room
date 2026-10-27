# LowerThird

The one overlay Front Room puts on the shared TV, chosen by the room: a headline, one supporting line and how the room decided.

## Props

| Prop | What |
|---|---|
| `headline`, `line` | The story, from verified facts only. |
| `asked`, `inRoom` | How many in the room asked for it, out of how many. Never who. |
| `neutral` | Adds "Kept neutral: both clubs are here". |
| `showProvenance` | Defaults to `true`. Households can switch the provenance row off. |

## Brand rules it enforces

- Opaque plate: nothing of the match shows through.
- A solid white card on a lip with a robin edge, signed by Pip's whistle: robin means what the room shares.
- Wipes in from its own edge in 240 ms; a cut under `prefers-reduced-motion`.
- Pip's face signs it as Front Room's, the way a graphics package signs its straps.

## Usage

```tsx
import { LowerThird } from "@frontroom/design";

<LowerThird
  headline="It started with Mensah's press"
  line="He won it back on halfway. Three passes later, Okafor scored."
  asked={3}
  inRoom={4}
  neutral
/>
```
