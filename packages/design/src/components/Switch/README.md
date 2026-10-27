# Switch

A settings row with a real switch: labelled, announced as on or off, with a 44 px touch target.

## Props

| Prop | What |
|---|---|
| `label`, `hint` | What it controls, and an optional line under it. |
| `defaultOn` | Starting state. |

## Brand rules it enforces

- Switches, never checkboxes, on phones.
- Pitch green when on (testers read robin as "off"); a setting is private, so never robin.

## Usage

```tsx
import { Switch } from "@frontroom/design";

<Switch label="Subtítulos en la tele" hint="En español, debajo del inglés" defaultOn />
```
