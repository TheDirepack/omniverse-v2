# Omniverse V2 — Design System
## Philosophy & Visual Language

---

## 1. What Omniverse Should Feel Like

Omniverse is a **power tool**, not a consumer product.

It should feel the way a well-calibrated instrument feels: precise, immediate, purposeful. A user opening Omniverse is an expert who needs to see a lot, understand it quickly, and act without ceremony. Every design decision serves that person.

The design direction selected was **"Precision Tooling"** — explicitly chosen over:

- **Modern Minimalist** (Linear/Vercel): too much negative space, feels lightweight when the domain is heavy
- **Immersive/Dark-First** (Sci-Fi): prioritizes atmosphere over cognition

Precision Tooling means: compact but polished, structured but not rigid, functional color rather than decorative color. It is the design language of expert workstations — the kind of interface where you know exactly what to do and where to look.

---

## 2. UX Principles

**Density over emptiness.** Information should fill the viewport. Whitespace is used purposefully for rhythm and grouping — not as a default filler. When two pieces of related data exist, they should be near each other.

**Structure is created by alignment, typography, spacing, and subtle separation — not decorative containers.** A border should exist because something needs to be bounded. A background change should exist because something needs to be grouped. Neither should be decorative.

**Color communicates state.** The accent color (`--accent`) is used for one purpose: "this is selected, active, or requires your attention." Status colors exist for one purpose each. Using accent color decoratively — on section headers, on icons — dilutes its signal.

**Progressive disclosure.** The interface shows what you need when you need it. Primary actions are immediately visible. Secondary actions appear in context (hover, selection). Advanced or destructive actions require intent.

**Consistency earns trust.** Every toolbar looks the same. Every inspector looks the same. Every button of the same class looks the same. Users learn the system once and apply it everywhere. Inconsistency forces relearning and signals chaos.

**Filtering is a first-class citizen, not an afterthought.** Filtering is a reusable query language embedded in every workflow. It is not a dropdown or a search box — it is a structured, composable mechanism that appears consistently and behaves identically in every context.

---

## 3. Visual Hierarchy

Hierarchy is created by exactly four tools, used in this order of preference:

1. **Typography weight and size.** Primary content is heavier. Labels are smaller and lighter. Titles are larger. The eye follows weight before it follows color.
2. **Spacing.** Related items are close. Separate categories are far. Sections are separated by consistent rhythm.
3. **Surface change.** A shift in background value (e.g., `#f8fafc` → `#ffffff`) groups elements without drawing a box around them.
4. **Borders.** Used only when surface change is insufficient to create the needed boundary.

Elevation (box-shadow, drop shadow) is **not used** for hierarchy. It carries spatial metaphor (floating above) that conflicts with the flat, data-first language of this tool.

---

## 4. Surface Philosophy

A surface is any region of the interface with a distinct background. These are the surfaces used in Omniverse and their rules:

| Surface | Background | When to Use |
|---|---|---|
| App background | `#f8fafc` | Default. The base layer. |
| Panel / Card | `#ffffff` | When content needs to be distinguished from the background. |
| Sidebar | `#f1f5f9` | Navigation region. Always cooler/more muted than the app background. |
| Header bar | `#e2e8f0` | Wordmark, section labels. One step darker than sidebar. |
| Input | `#ffffff` | Always white. Inputs are editable regions, not structural. |
| Active tab / nav | `#eff6ff` | Selected state only. Never decorative. |

**When is a border appropriate?**
- Between a sidebar and a main content area: always
- Between a list column and an inspector column: always
- Around an input: always (1px, `--border`)
- Around a card: only if it sits directly on the app background with no other separation mechanism
- Around a section within a panel: rarely — use spacing instead

**When should something be flush?**
The shell is always flush against the browser window. There are no outer margins, no border around the application, no padding between the window edge and the first pixel of UI. This enforces the "workstation" feeling — the tool fills the space it's given.

---

## 5. Semantic Color

Color communicates meaning. These are the only meanings colors carry in Omniverse:

**Accent (Blue)**
Used for: active navigation, selected items, focus rings, primary CTA buttons, hyperlinks, and interactive element highlights.
Never used for: decoration, non-interactive labels, section headers.

**Danger (Red)**
Used for: destructive actions only — delete, abort, remove.
Never used for: warnings, errors that are recoverable, or anything the user didn't initiate.

**Warning (Amber)**
Used for: states requiring attention but not failure — stalled progress, unconfirmed items, notebook entries.
Never used for: errors or destructive outcomes.

**Success (Green)**
Used for: verified states, active/healthy status, completed items.
Never used for: anything that isn't confirming a positive state.

**Neutral (Gray scale)**
Used for: everything that isn't communicating a semantic state. Labels, borders, background values, body text, muted text.

The color system is deliberately narrow. The more colors in a UI, the less any individual color means.

---

## 6. Typography

Typography is the primary tool of information hierarchy.

**Font family:** System UI stack — `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`. This is a deliberate choice: Omniverse is a tool that should feel native to the operating system, not branded with a web font.

**Type scale — from most to least prominent:**

| Role | Size | Weight | Transform | Use |
|---|---|---|---|---|
| Wordmark | 0.85rem | 800 | Uppercase | App name only |
| Inspector title | 1.1rem | 800 | None | Selected item name in inspector |
| Section header | 0.9rem | 700 | None | Named sections within panels |
| Body / table content | 0.8rem | 400–600 | None | Primary readable content |
| Field label | 0.7rem | 700 | Uppercase | Form labels, column headers |
| Micro / timestamp | 0.75rem | 400 | None | Metadata, timestamps, muted info |

**Weight carries meaning.** Bold text is a primary value. Regular text is supporting content. This must be applied consistently — if a world name is bold, all world names are bold, and nothing else in that row is.

---

## 7. Rhythm and Alignment

**Rhythm** is the regularity of spacing throughout the interface. It creates the sense that the UI is designed rather than assembled.

The spacing scale: 4px, 8px, 12px, 16px, 20px. These are the only inter-element gaps used. Mixing ad-hoc values (e.g., 10px, 14px, 22px) breaks rhythm.

**Alignment** is the axis along which the eye travels. In Omniverse:

- Content left-aligns to its container
- Toolbars have three zones: left (context/identity), center (search/filter), right (actions). This is consistent across every workflow.
- Table columns have fixed alignment: text left, numbers and status badges right or centered
- Labels align to their input's left edge, not to each other across columns

The grid should feel inevitable. When a designer has done their job, the user never notices the grid — they just find the information.

---

## 8. Component Philosophy

Components are tools, not decorations. Each component class has one job:

**Buttons** initiate actions. Their visual weight communicates the consequence of the action. Primary buttons are visually heavy (filled) and used for the most important action on a surface. Secondary buttons are light (outlined). Danger buttons are reserved for destructive actions.

**Tables** display lists of comparable items where the user needs to scan, compare, and act on individual rows. Tables are not used for configuration or prose.

**Inspectors** display the full detail of a single selected item. They appear to the right of list components and are revealed by selection, not by a separate navigation step.

**Forms** collect structured input. Every input has a label. Forms are laid out in grids to allow visual comparison of related fields.

**Filters** are composable query builders. They are not simple search boxes. A filter is a structured expression: Field → Operator → Value. Filters appear in a consistent popup pattern triggered from the toolbar.

**Badges** display state at a glance. They appear in list rows and are always right-aligned. They never replace text — they augment it.

**Toolbars** are the single consistent horizontal bar at the top of every content area. They contain search, filter, and primary actions. They never contain secondary navigation.

---

## 9. Accessibility Philosophy

Accessibility is a structural property of the UI, not a feature or a checklist item. It is inseparable from good component design.

The central principle: **the interface must be completely operable without a mouse.** Every interactive element must be reachable by keyboard in logical order. Every state change must be announced to assistive technology.

This produces specific structural rules:
- All clickable things are `<button>` or `<a>` — never styled `<div>` elements
- All inputs are labeled — never relying on placeholder text alone
- All complex widgets (tabs, modals, dropdowns) implement their ARIA pattern
- All dynamic content regions are live regions
- Focus is managed at the application level — modals trap focus, and focus returns to the trigger when a modal closes

High contrast is a consequence of the semantic color system, not a separate concern. When color communicates meaning semantically, the contrast ratios naturally fall within WCAG AA because the meanings require readability.

---

## 10. Interaction Principles

**Instant feedback.** Actions that complete immediately should show instant visual change. Actions that require a network call should show a loading state — not a full spinner, but an inline change on the triggering element (e.g., button label changes to "Syncing...").

**Non-destructive by default.** Nothing is deleted without confirmation. The confirmation mechanism is inline (an "Are you sure?" secondary button appearing next to the action), not a modal, for speed.

**State is visible.** The current selection, the active world, the active tab, the active filter — all are visible at all times without requiring the user to open a panel or hover over something.

**Escape always works.** Any modal, popup, or overlay is dismissible by pressing Escape. Focus returns to the trigger element.
