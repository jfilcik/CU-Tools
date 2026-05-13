Here’s **`design-guidelines.md`**.

```markdown
## Emotional tone

Feels like a **precision engineering console—calm, transparent, and trustworthy.**  
Users should feel confident making infrastructure changes without fear of hidden consequences.

The UI must communicate **clarity, safety, and control**.

---

# Visual system

## Typography

The typography should support scanning and technical clarity.

### Typeface choice
Primary font: **Inter**

Reasons:
- widely used in developer tooling
- excellent readability in dense dashboards
- neutral tone (confident but not cold)

### Typographic scale

| Level | Size | Weight | Usage |
|-----|-----|-----|-----|
| H1 | 32px | 600 | Page titles |
| H2 | 24px | 600 | Section headers |
| H3 | 18px | 600 | Panel titles |
| H4 | 16px | 600 | Card headers |
| Body | 14px | 400 | Standard text |
| Caption | 12px | 400 | Metadata and hints |

Rules:
- Line height ≥ **1.6**
- Max line width **80 characters**
- Numbers aligned in tables for readability

---

# Color system

The color palette emphasizes **trust and operational clarity**.

### Primary

Deep blue signals reliability and engineering focus.

```

Primary Blue
HEX #2563EB
RGB 37, 99, 235

```

### Secondary

Neutral grays support dense operational UI.

```

Slate 900 #0F172A
Slate 700 #334155
Slate 500 #64748B
Slate 200 #E2E8F0

```

### Accent

Used sparingly for key actions.

```

Accent Cyan
HEX #06B6D4
RGB 6,182,212

```

### Semantic colors

Status colors must be **instantly recognizable**.

```

Success
#22C55E

Warning
#F59E0B

Error
#EF4444

Info
#3B82F6

```

Contrast rules:
- Text contrast ≥ **4.5:1**
- Status colors must remain distinguishable in dark mode

---

# Spacing & layout

Use an **8pt grid system**.

Spacing scale:

| Token | Pixels |
|-----|-----|
| xs | 4 |
| sm | 8 |
| md | 16 |
| lg | 24 |
| xl | 32 |
| xxl | 48 |

Layout principles:

- Left navigation + main content
- Max page width **1280px**
- Panels use **16–24px padding**
- Analyzer lists should support **dense row layout**

### Responsive breakpoints

| Device | Width |
|------|------|
| Mobile | 0–640px |
| Tablet | 640–1024px |
| Desktop | 1024–1440px |
| Wide | 1440px+ |

Mobile layout collapses inventory into stacked cards.

---

# Motion & interaction

Motion should feel **subtle and confident**.

Duration rules:

- Hover: **150ms**
- Panel expand: **200ms**
- Navigation transitions: **200–250ms**

Easing curve:
```

cubic-bezier(0.4, 0, 0.2, 1)

```

### Interaction behaviors

Hover:
- subtle background elevation
- slight border highlight

Expandable panels:
- smooth reveal
- never hide important warnings

Loading states:
- skeleton loaders for tables
- avoid blocking spinners

Empty states:
- explain what is missing
- suggest next action

Example:

**No analyzers found**

“Connect to a CU resource to begin inventory.”

---

# Voice & tone

The interface voice should be:

- clear
- calm
- operational
- non-judgmental

Avoid alarmist wording.

### Example microcopy

**Onboarding**

“Connect your Azure Content Understanding resource to begin analyzer discovery.”

**Success**

“Migration completed. 12 analyzers created.”

**Error**

“This analyzer requires manual review before migration.”

---

# System consistency

Use patterns inspired by:

- **Linear**
- **Azure Portal**
- **shadcn/ui dashboards**

Recurring components:

### Analyzer status badges

| Status | Label |
|------|------|
| Ready | Green badge |
| Review | Yellow badge |
| Blocked | Red badge |

### Diff panels

Always show:

Left side:
Preview analyzer

Right side:
GA analyzer proposal

### Migration findings

Use severity indicators:

```

Auto-fixed
Needs review
Unsupported in GA

```

---

# Accessibility

Accessibility must be built in.

### Semantic structure

Pages must include:

- header
- navigation
- main content
- footer landmarks

### Keyboard support

Users must be able to:

- navigate analyzer list
- open review panel
- confirm migration

### Focus indicators

All interactive elements show a visible focus ring.

### ARIA roles

Use for:

- expandable panels
- table navigation
- warning alerts

---

# Emotional audit checklist

Before shipping any UI change:

- Does the UI feel **safe for operational work?**
- Are warnings clear without causing panic?
- Can a user understand migration status in **under 3 seconds**?
- Do diff views make changes obvious?

---

# Technical QA checklist

Typography
- scale follows grid rhythm

Color
- contrast ≥ 4.5:1

Interaction
- hover and focus states visible

Motion
- durations stay within 150–300ms

Tables
- support keyboard navigation

---

# Design snapshot

## Emotional thesis

“A calm engineering console that makes risky migrations feel safe and understandable.”

---

## Color palette

```

Primary Blue  #2563EB
Accent Cyan   #06B6D4
Slate 900     #0F172A
Slate 700     #334155
Slate 500     #64748B
Slate 200     #E2E8F0

Success       #22C55E
Warning       #F59E0B
Error         #EF4444
Info          #3B82F6

```

---

## Typography scale

| Element | Size | Weight |
|------|------|------|
| H1 | 32px | 600 |
| H2 | 24px | 600 |
| H3 | 18px | 600 |
| H4 | 16px | 600 |
| Body | 14px | 400 |
| Caption | 12px | 400 |

Line height: **1.6**

---

## Spacing system

```

xs 4px
sm 8px
md 16px
lg 24px
xl 32px
xxl 48px

```

Grid: **8pt**

---

# Design Integrity Review

The design aligns well with the tool’s purpose: a calm, operational migration console where clarity and safety matter more than visual flair. Typography and layout prioritize scanning, while color semantics communicate migration status instantly.

One improvement opportunity: add **visual diff highlighting (field-level changes)** so engineers can spot schema transformations faster during analyzer review.
```
