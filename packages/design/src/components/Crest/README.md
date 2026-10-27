# Crest

The two fictional clubs' crests: Kestrel FC (a kestrel's head, red shield) and Ashvale Athletic (an ash leaf, sky-blue roundel).

## Props

| Prop | What |
|---|---|
| `club` | `kestrel` or `ashvale`. |
| `size` | Height in pixels; width follows the shape. |
| `labelled` | Gives it the club name as alt text. Decorative by default. |

## Brand rules it enforces

- Clubs are data: a crest marks a fan's own club, or both clubs equally. Never one club alone on a shared screen.
- Legible from 20 px.

## Usage

```tsx
import { Crest } from "@frontroom/design";

<Crest club="kestrel" size={32} />
```
