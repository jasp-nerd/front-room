# PhoneFrame

A plain 390 × 844 phone for showing the private lens in decks, the video and the demo board.

## Props

| Prop | What |
|---|---|
| `time` | Status bar time. |
| `lang` | The screen's language attribute. |
| `large` | Larger type for fans who asked for it. |
| `accent` | The fan's colour (`sky`, `sun`, `pitch`, `pink`), exposed to the screen as `--accent` and `--accent-wash`. |
| `children` | The screen. |

## Brand rules it enforces

- Drawn plainly so the screen is what you look at.
- `data-large` scales running text from 17 to 22 px.
- Each phone carries its owner's colour; robin stays for what the room shares.

## Usage

```tsx
import { PhoneFrame } from "@frontroom/design";

<PhoneFrame time="21:19" lang="es">
  <LensStrip … />
</PhoneFrame>
```
