# Button

Buttons for phones and tools: 48 px tall, 44 px minimum target.

## Props

| Prop | What |
|---|---|
| `variant` | `primary` (robin on a lip), `secondary` (white on a grey lip) or `join` (the big robin button). |
| `block` | Full width, for actions pinned to the bottom of a phone. |
| `…rest` | Any button attribute; `type` defaults to `button`. |

## Brand rules it enforces

- Amber only for joining a room, the one action everyone on the sofa shares.
- Sentence case labels.

## Usage

```tsx
import { Button } from "@frontroom/design";

<Button variant="join" block>Join the room</Button>
```
