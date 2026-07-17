# Omniverse V2 — Component Specification
## Deterministic Implementation Reference

All values in this document are authoritative. Every component must match these specifications exactly.

---

## Design Tokens

All design tokens are Tailwind CSS classes. There are no CSS custom properties (`--var`) in the application — every value is expressed as a Tailwind utility class. Colors, spacing, and sizing use Tailwind's built-in scale.

### Color Mapping

| Role | Light Class | Dark Class |
|---|---|---|
| App background | `bg-white` | `dark:bg-gray-950` |
| Surface / Card | `bg-white` | `dark:bg-gray-800` |
| Sidebar | `bg-gray-50` | `dark:bg-gray-900` |
| Wordmark bar | `bg-gray-200` (header area) | `dark:bg-gray-800` |
| Input | `bg-white` | `dark:bg-gray-800` |
| Active tab / nav | `bg-blue-100` | `dark:bg-blue-900/30` |
| Border | `border-gray-200` or `border-gray-300` | `dark:border-gray-700` or `dark:border-gray-800` |
| Text primary | `text-gray-900` | `dark:text-gray-100` |
| Text secondary | `text-gray-500` | `dark:text-gray-400` |
| Text muted | `text-gray-400` | `dark:text-gray-500` |
| Accent (CTA, links) | `text-blue-600` / `bg-blue-600` / `ring-blue-500` | `dark:text-blue-400` |
| Danger | `text-red-600` / `bg-red-600` | `dark:text-red-400` |
| Success / OK | `text-green-700` / `bg-green-100` | `dark:text-green-400` / `dark:bg-green-900/30` |
| Warning | `text-amber-600` / `bg-amber-100` | `dark:text-amber-400` / `dark:bg-amber-900/10` |

### Spacing Scale (Tailwind)

```
p-1  = 4px   — icon gaps, inline spacing
p-2  = 8px   — component internal padding, row gaps
p-3  = 12px  — content area padding, section gaps
p-4  = 16px  — panel padding, form field gaps
p-6  = 24px  — between major sections within a panel
gap-1, gap-2, gap-3, gap-4 — corresponding gaps
```

No other values. Ad-hoc spacing breaks rhythm.

### Border Radius

```
rounded-sm   = 2px  — buttons, inputs, badges, small elements (Tailwind default: 0.125rem)
rounded      = 4px  — cards, panels, popups (Tailwind default: 0.25rem)
rounded-lg   = 8px  — modals, overlays
rounded-none = 0    — toolbar, sidebar, shell elements (flush)
```

---

## Component Catalog

---

### Button — Primary

The most important action on a given surface. Used once per toolbar or form.

**Tailwind:**
```
h-7 px-3 text-xs font-semibold bg-blue-600 text-white rounded-sm hover:bg-blue-700 transition-colors
```

**Spécifications:**
- height: 28px (`h-7`) in compact 48px toolbars
- background: `bg-blue-600`, hover: `bg-blue-700`
- color: `text-white`
- border: none
- font-size: `text-xs` (0.75rem)
- font-weight: `font-semibold` (600)
- padding: `px-3` (12px horizontal)
- cursor: pointer

**States:**
- `:hover` — `hover:bg-blue-700`
- `:focus-visible` — Tailwind's default focus ring
- `:disabled` — opacity 0.5, cursor not-allowed (manual)
- Loading — label changes to e.g. "Saving...", `pointer-events: none`

---

### Button — Secondary

Supporting action. Can appear multiple times per surface.

**Tailwind:**
```
h-7 px-3 text-xs font-medium bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors
```

**Spécifications:**
- height: 28px (`h-7`)
- background: `bg-white` / `dark:bg-gray-800`
- color: `text-gray-700` / `dark:text-gray-300`
- border: `border border-gray-300` / `dark:border-gray-700`
- border-radius: `rounded-sm`
- font-size: `text-xs`
- padding: `px-3`

---

### Button — Danger

For destructive actions — delete, abort, remove.

**Danger Filled (global destructive, e.g., "Abort All"):**
```
h-7 px-3 text-xs font-semibold bg-red-600 text-white rounded-sm hover:bg-red-700 transition-colors
```

**Danger Ghost (per-row delete):**
```
p-1 text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors
```

---

### Input — Text

**Tailwind:**
```
h-7 px-3 text-xs bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-sm focus:outline-none focus:ring-1 focus:ring-blue-500
```

**States:**
- `:focus` — `focus:outline-none focus:ring-1 focus:ring-blue-500`
- `:disabled` — opacity reduction

Every input must have an associated `<label>`. If a visible label is undesirable, use `sr-only`.

---

### Select

**Tailwind:**
```
h-7 px-2 text-xs border border-gray-300 dark:border-gray-700 rounded-sm bg-white dark:bg-gray-800 focus:outline-none focus:ring-1 focus:ring-blue-500
```

---

### Label — Field

Appears above every input. Never replaces a `<label>` element.

**Tailwind:**
```
text-[10px] font-bold text-gray-400 uppercase tracking-widest
```

---

### Table

All tables share this structure. Column-specific overrides are defined per-workflow.

**Table element:**
```
w-full text-left border-collapse text-xs
```

**Header row (`<thead>`):**
```
bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 uppercase tracking-wider font-bold border-b border-gray-200 dark:border-gray-700
```

**Header cell (`<th>`):**
```
px-4 py-2
```

**Body row (`<tr>`):**
```
hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors
```

**Body cell (`<td>`):**
```
px-4 py-2.5
```

**Accessibility:** Tables that list selectable items should use `<thead>`/`<tbody>` with `<button>` or `<a>` inside cells for actions, not row-level click handlers.

---

### Badge — Status

Appears in list rows to show item state.

**Tailwind:**
```
px-1.5 py-0.5 text-[9px] font-bold uppercase rounded-sm
```

| State | Background | Text |
|---|---|---|
| Explored | `bg-green-100` / `dark:bg-green-900/30` | `text-green-700` / `dark:text-green-400` |
| Pending | `bg-gray-100` / `dark:bg-gray-800` | `text-gray-600` / `dark:text-gray-400` |
| Active | `bg-green-100` / `dark:bg-green-900/30` | `text-green-700` / `dark:text-green-400` |

---

### Progress Bar

Used in Execution workflow to show run progress inline in a table row.

```html
<div class="progress-track">
  <div class="progress-fill" style="width: 65%;"></div>
</div>
```

```css
.progress-track {
  width: 100%;
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  border: 1px solid var(--border, #cbd5e1);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 4px;
  background: #2563eb;         /* active run */
}
.progress-fill.stalled {
  background: #f59e0b;         /* stalled / slow run */
}
```

---

### Toolbar

One per page. Contains three zones.

```css
.toolbar {
  height: 48px;
  border-bottom: 1px solid border-gray-200;
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 12px;
  flex-shrink: 0;
}
```

**Implemented as Tailwind:**
```
h-12 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 flex items-center px-4 gap-3 shrink-0
```

**Three zones:**
- Left: `flex items-center gap-2 flex-1 min-w-0`
- Center: `flex items-center gap-2 flex-1 min-w-0`
- Right: `flex items-center gap-2 shrink-0`

**Dividers between zones:** `w-px h-6 bg-gray-200 dark:bg-gray-700`

---

### Filter Popup

Generated client-side by `toggleFilterPopup()` JS or server-rendered via `components/filter_popup.html`.

**CSS (inline in page `<style>` or in filter_popup.html):**
```css
.filter-popup {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  width: 320px;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.10);
  z-index: 100;
  font-size: 0.8rem;
}
.dark .filter-popup {
  background: #1e293b;
  border-color: #334155;
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
}
.filter-popup-header {
  font-weight: 700;
  border-bottom: 1px solid #f1f5f9;
  padding-bottom: 4px;
  margin-bottom: 8px;
  color: #1e293b;
}
.dark .filter-popup-header {
  color: #f1f5f9;
  border-bottom-color: #334155;
}
.filter-rule-row {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
}
```

**JS functions:**
- `toggleFilterPopup(btn, popupId, targetUrl, fields)` — creates/shows popup
- `closeFilterPopup(popupId)` — removes popup, resets `aria-expanded`
- Global `click` listener dismisses on outside click
- Global `keydown` listener dismisses on Escape

**Accessibility:**
- Trigger button: `aria-haspopup="true"`, `aria-expanded`
- Popup container: `role="dialog"`, `aria-modal="true"`, `aria-label="Filter query builder"`
- Dismissible by Escape and clicking outside

---

### Section Header

Used inside panels to label groups of related fields.

**Tailwind:**
```
text-sm font-bold text-gray-900 dark:text-gray-100 mb-3
```

---

### Inspector Panel

Right-side detail panel. Used in Knowledge world detail and Settings.

**Knowledge inspector:** `w-80 bg-gray-50 dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 overflow-y-auto`

**Settings inspector:** Part of 3-panel layout, `flex: 1`.

**Internal field pattern:**
- Label: `text-[10px] font-bold text-gray-400 uppercase mb-1`
- Value: `text-sm text-gray-600 dark:text-gray-400`
- Inset: `p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-sm`

---

### Tab Bar (World Detail sub-tabs)

Used in Knowledge world detail for Overview | Artifacts | Notebook | Theory.

**Tailwind:**
```
h-11 border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 flex items-center px-4 gap-1 shrink-0
```

**Tab button — inactive:**
```
px-4 py-1 text-xs font-medium border-b-2 border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 rounded-t-sm transition-colors
```

**Tab button — active:**
```
px-4 py-1 text-xs font-semibold border-b-2 border-blue-600 text-blue-600 dark:text-blue-400 rounded-t-sm transition-colors
```

### Sidebar

**Tailwind:**
```
w-64 h-full bg-gray-50 border-r border-gray-200 dark:bg-gray-900 dark:border-gray-800 flex flex-col shrink-0
```

**Wordmark:**
```
p-4 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between
```
Inner label: `text-xs font-black tracking-tighter uppercase text-gray-400 dark:text-gray-500`

**Nav items:**
```
flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-sm transition-colors
```
Active: `bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-semibold`
Inactive: `text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-800`

---

### Toast Notification

```html
<div id="toast-container" role="alert" aria-live="polite" aria-atomic="true">
  <!-- Toasts injected here by JS -->
</div>
```

Implemented in `base.html` JS `showToast()`:
- Position: `fixed top-4 right-4`
- Classes: `px-4 py-3 rounded-sm shadow-lg text-white text-sm z-50 transition-opacity duration-300`
- Inline background color per type: success `#16a34a`, error `#dc2626`, info `#2563eb`
- Auto-dismiss after 3 seconds

---

### Artifact List Item (Knowledge artifact tab entry)

Each artifact in the Knowledge artifact list is a `<div>` with `onclick` to load inspector.

```
flex items-center justify-between p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-sm hover:border-blue-400 dark:hover:border-blue-600 transition-colors cursor-pointer
```

---

### Notebook Entry Item (Knowledge notebook tab)

```
p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-sm hover:border-blue-400 dark:hover:border-blue-600 transition-colors cursor-pointer
```

---

### World List Row (Knowledge phase 1)

```
flex items-center justify-between px-6 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors cursor-pointer border-l-4 border-l-transparent hover:border-l-blue-500
```

---

### Modal

Used in Research page for "Add World" / import.

```
fixed inset-0 bg-black/50 flex items-center justify-center hidden z-50
```

Inner panel:
```
bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto
```

---

## Accessibility Checklist (Per Component)

| Component | Requirement |
|---|---|
| All buttons | `<button>` element. Never `<div>` or `<span>`. |
| All inputs | Associated `<label>` via `for`/`id`. |
| Icon-only buttons | `aria-label` describing the action. |
| Tab bar (world detail) | `role="tablist"`, `role="tab"`, `aria-selected`. The click handler `switchWorldTab()` manages aria state. |
| Tab panels | `role="tabpanel"`, `aria-labelledby`. |
| Modal/popup | `role="dialog"`, `aria-modal="true"`, focus trap on open, Escape closes. |
| Filter popup | `aria-haspopup`, `aria-expanded`, `role="dialog"`, `aria-modal="true"`. |
| Toast container | `role="alert"` or `aria-live="polite"`. |
| HTMX swap targets | `aria-live="polite"` where content changes affect user task. |
| Status indicators | Text equivalent alongside any color or icon indicator. |
| Progress bars | `role="progressbar"`, `aria-valuenow`, `aria-valuemin`, `aria-valuemax`. |
