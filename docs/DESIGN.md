# RepoMentor — Design System

> Midnight codebase with copper editorial signals.

## Product Adaptation

This document adapts the supplied Slash visual reference to RepoMentor.

RepoMentor keeps the reference's:
- dark midnight canvas
- editorial serif/sans contrast
- thin borders
- compact density
- restrained copper accent
- pill controls
- minimal elevation

But all product content must be developer-focused.

Do not use:
- financial balances
- transactions
- merchants
- spending limits
- banking language

Use:
- repositories
- modules
- files
- architecture
- code symbols
- analysis status
- AI answers
- source references

---

# Theme

Dark.

Primary page canvas:

`#08080a`

The UI should feel like a premium developer workspace: quiet, technical, editorial, and information-dense.

---

# Color Tokens

| Name | Value | Role |
|---|---|---|
| Obsidian | `#08080a` | Page canvas |
| Onyx | `#040406` | Card surface |
| Carbon | `#121317` | Panels and inputs |
| Graphite | `#1c1d22` | Hairline borders |
| Slate | `#2e3038` | Secondary borders |
| Smoke | `#464853` | Tertiary structure |
| Ash | `#5e616e` | Muted text |
| Steel | `#777a88` | Icons, secondary controls |
| Fog | `#9194a1` | Descriptions and helper text |
| Mist | `#acafb9` | Supplementary text |
| Silver | `#c7c9d1` | Medium-emphasis text |
| Bone | `#e2e3e9` | Default body text |
| Paper White | `#ffffff` | Primary headings/actions |
| Copper | `#cc9166` | Labels, links, code-analysis accents |

Use copper sparingly.

Do not introduce additional brand colors unless required for semantic status.

---

# Semantic Status Colors

Semantic colors are permitted only for status communication.

- Success: restrained sage/green
- Warning: muted amber
- Error: muted red
- Informational: muted steel/blue-gray

These must not become general brand accents.

---

# Typography

## Display

Use Ivy Presto if available.

Fallback:

- Playfair Display
- DM Serif Display
- Libre Caslon Display

Use only for headings ≥ 28px.

Token:

`--font-ivy-presto`

## UI

Use Inter.

Token:

`--font-inter`

Use Inter for:
- body
- navigation
- buttons
- labels
- code metadata
- forms
- source references

---

# Type Scale

| Role | Size | Line Height |
|---|---:|---:|
| eyebrow | 13px | 1 |
| body-xs | 16px | 1.5 |
| body-sm | 18px | 1.38 |
| body | 20px | 1.38 |
| subheading | 24px | 1 |
| heading-sm | 44px | 1.38 |
| heading | 52px | 1.13 |
| heading-lg | 64px | 1.13 |
| display | 88px | 1 |

---

# Layout

- Max width: `1216px`
- Desktop section gap: `160px`
- Card padding: `24px`
- Default element gap: `8px`
- Compact density

Responsive behavior must prioritize readability on laptop and tablet screens.

---

# Border Radius

- Navigation accents: `2px`
- Cards: `10px`
- Buttons: `9999px`
- Inputs: `9999px`
- Tags: `9999px`
- Status badges: `9999px`

---

# Elevation

Do not use heavy drop shadows.

Prefer:
- surface contrast
- 1px borders
- whitespace

---

# Core Components

## Primary Action Button

White fill.

Black text.

Pill shape.

Use for the single highest-priority action, such as:

`Analyze Repository`

Avoid using multiple primary buttons in the same viewport.

---

## Ghost Button

Transparent.

1px white/steel border.

Used for secondary actions such as:

- View Files
- Open Architecture
- Retry Analysis

---

## Repository Input

Large pill input.

Placeholder:

`Paste a public GitHub repository URL`

Primary action:

`Analyze Repository`

---

## Analysis Status

Use a compact status badge.

Examples:

- ANALYZING
- COMPLETED
- FAILED

---

## Repository Header

Show:

- repository name
- owner
- GitHub URL
- analysis status
- language/technology tags

---

## Stat Display

Use for:

- files analyzed
- languages detected
- modules found
- entry points found

Large number:

28–44px Ivy Presto.

Caption:

14px Inter muted.

---

## Module Card

10px radius.

Show:

- module name
- purpose
- important files
- symbol count

---

## Architecture Card

Dark surface.

Contains React Flow visualization.

Keep graph readable and avoid unnecessary decoration.

---

## Data Flow Card

Show a clear vertical or horizontal flow:

```text
Frontend
   ↓
API Route
   ↓
Controller
   ↓
Service
   ↓
Database
```

---

## File Explorer

Dense table/tree.

Columns where useful:

- File
- Language
- Purpose
- Symbols

Use hairline separators.

---

## Source Reference

A compact developer-oriented source block.

Example:

```text
backend/services/auth_service.py
lines 24–58
authenticate_user()
```

Use Copper only as a subtle link/label accent.

---

## AI Answer Card

Show:

1. Answer
2. Explanation
3. Relevant files
4. Symbols
5. Confidence/grounding metadata when available

Do not make the UI look like a generic chatbot.

The repository evidence should be visually prominent.

---

## Setup Guide

Use compact sections:

- Prerequisites
- Install
- Environment
- Database
- Run
- Common issues

Commands must use monospace styling.

---

# Navigation

Recommended top navigation:

- Overview
- Architecture
- Modules
- Files
- Data Flow
- Setup
- Ask

Use active white text.

Inactive text uses Fog.

---

# Hero

The landing page should have:

Left:
- copper eyebrow
- large serif RepoMentor headline
- concise explanation
- repository URL input
- primary Analyze Repository action

Right:
- product preview showing a repository analysis dashboard
- architecture/data-flow preview
- AI source references

Do not use financial dashboard imagery from the original reference.

---

# Visual Language

Use:

- thin borders
- dark surfaces
- generous whitespace
- compact data tables
- editorial headings
- subtle copper labels
- restrained status colors
- developer-oriented icons

Avoid:

- excessive gradients
- glassmorphism
- neon cyberpunk styling
- excessive animation
- colorful SaaS gradients
- stock illustrations
- generic AI robot imagery

---

# Accessibility

- Maintain readable contrast.
- Keyboard-accessible controls.
- Visible focus states.
- Do not rely on color alone for status.
- Provide labels for inputs.
- Make architecture/data-flow content understandable without hover-only information.

---

# CSS Tokens

```css
:root {
  --color-obsidian: #08080a;
  --color-onyx: #040406;
  --color-carbon: #121317;
  --color-graphite: #1c1d22;
  --color-slate: #2e3038;
  --color-smoke: #464853;
  --color-ash: #5e616e;
  --color-steel: #777a88;
  --color-fog: #9194a1;
  --color-mist: #acafb9;
  --color-silver: #c7c9d1;
  --color-bone: #e2e3e9;
  --color-paper-white: #ffffff;
  --color-copper: #cc9166;

  --font-ivy-presto: 'Ivy Presto', 'Playfair Display', serif;
  --font-inter: 'Inter', ui-sans-serif, system-ui, sans-serif;

  --page-max-width: 1216px;
  --section-gap: 160px;
  --card-padding: 24px;
  --element-gap: 8px;

  --radius-nav: 2px;
  --radius-card: 10px;
  --radius-pill: 9999px;

  --border-hairline: #1c1d22;
  --border-secondary: #2e3038;
}
```

---

# Do

- Use the supplied dark editorial system consistently.
- Use serif headings for major product statements.
- Use Inter for functional UI.
- Use copper for small labels and source accents.
- Use surface contrast instead of shadows.
- Keep the interface information-dense but readable.
- Make repository evidence easy to scan.

# Don't

- Do not retain Slash's finance-specific copy.
- Do not use balances, merchants, transactions, or spending terminology.
- Do not introduce a new primary color system.
- Do not use heavy shadows.
- Do not turn RepoMentor into a generic chatbot UI.
