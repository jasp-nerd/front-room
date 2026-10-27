# QrCode

A scannable QR code drawn as one SVG path, for the TV's join screen.

## Props

| Prop | What |
|---|---|
| `text` | What it encodes, usually the join URL. |
| `size` | Pixels. |
| `label` | Accessible name. |

## Brand rules it enforces

- Dark modules on a light quiet zone: inverted codes fail on many phones.
- Error correction M, so a TV's glare doesn't break it.

## Usage

```tsx
import { QrCode } from "@frontroom/design";

<QrCode text={joinUrl} size={300} label="QR code to join this room" />
```
