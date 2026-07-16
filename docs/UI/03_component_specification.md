# Omniverse V2 — Component Specification
## Deterministic Implementation Reference

All values in this document are authoritative. Every component must match these specifications exactly.

---

## Design Tokens

These variables must be defined in `base.html` and referenced throughout all templates.

### Color

```css
--bg-app:         #f8fafc;   /* Page / default background */
--bg-surface:     #ffffff;   /* Cards, inputs, panel backgrounds */
--bg-sidebar:     #f1f5f9;   /* Sidebar */
--bg-header:      #e2e8f0;   /* Wordmark bar, table headers */
--bg-active:      #eff6ff;   /* Active nav item, active tab */

--border:         #cbd5e1;   /* Standard border */
--border-subtle:  #f1f5f9;   /* Table row separators */

--text-primary:   #1e293b;   /* Body copy, primary values */
--text-secondary: #64748b;   /* Labels, inactive nav, metadata */
--text-muted:     #94a3b8;   /* Timestamps, disabled states */

--accent:         #2563eb;   /* Active state, CTA, links, focus */
--accent-bg:      #eff6ff;   /* See bg-active — same token */
--accent-ring:    #bfdbfe;   /* Focus ring on accent surfaces */

--danger:         #ef4444;   /* Destructive actions */
--danger-muted:   #fca5a5;   /* Danger borders on white surface */

--status-ok:      #166534;   /* Verified, active, healthy */
--status-ok-bg:   #dcfce7;
--status-warn:    #854d0e;   /* Notebook, unconfirmed, stalled */
--status-warn-bg: #fef9c3;
--status-error:   #991b1b;   /* Failed, down */
--status-error-bg:#fee2e2;
```

### Spacing Scale

```
4px   — icon gaps, inline spacing
8px   — component internal padding, row gaps
12px  — content area padding, section gaps
16px  — panel padding, form field gaps
20px  — between major sections within a panel
```

No other values. Ad-hoc spacing breaks rhythm.

### Border Radius

```
4px  — buttons, inputs, badges, small elements
6px  — cards, panels
8px  — popups, overlays
0    — toolbar, sidebar, shell elements (flush)
```

---

## Component Catalog

---

### Button — Primary

The most important action on a given surface. Used once per toolbar or form.

```
height:       30px (28px in compact 48px toolbars)
background:   var(--accent)
color:        #ffffff
border:       none
border-radius: 4px
font-size:    0.8rem
font-weight:  600
padding:      0 12px
cursor:       pointer
```

**States:**
- `:hover` — background darkens (`#1d4ed8`)
- `:focus-visible` — `outline: 2px solid var(--accent); outline-offset: 2px;`
- `:disabled` — opacity 0.5, cursor not-allowed
- Loading — label changes to e.g. "Saving...", pointer-events: none

---

### Button — Secondary

Supporting action. Can appear multiple times per surface.

```
height:       30px (28px compact)
background:   var(--bg-surface)
color:        var(--text-primary)
border:       1px solid var(--border)
border-radius: 4px
font-size:    0.8rem
padding:      0 12px
cursor:       pointer
```

---

### Button — Danger Outline

For destructive actions in context (e.g., per-row abort, per-item delete within a list).

```
background:   transparent
border:       1px solid var(--danger)
color:        var(--danger)
font-size:    0.75rem
padding:      4px 8px
border-radius: 4px
```

### Button — Danger Filled

For global destructive actions (e.g., "ABORT ALL"). Used sparingly.

```
background:   var(--danger)
color:        #ffffff
border:       none
font-weight:  600
font-size:    0.8rem
padding:      0 12px
height:       30px
```

### Button — Ghost / Text

For low-priority actions like "Delete" within a table cell.

```
background:   none
border:       none
color:        var(--danger)   /* or var(--text-secondary) for neutral */
font-size:    0.7rem
cursor:       pointer
padding:      0
```

---

### Input — Text

```
height:       30px (28px compact)
border:       1px solid var(--border)
border-radius: 4px
font-size:    0.8rem
padding:      0 8px
background:   var(--bg-surface)
color:        var(--text-primary)
```

**States:**
- `:focus` — `outline: none; border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-ring);`
- `:disabled` — background `var(--bg-app)`, cursor not-allowed

Every input must have an associated `<label>`. If a visible label is undesirable, use `.sr-only`.

---

### Input — Inline (table cell)

Used within editable table rows (e.g., API Key value, Priority number).

```
height:       24px
border:       1px solid var(--border)
border-radius: 4px
font-size:    0.75rem
padding:      0 4px
background:   var(--bg-surface)
width:        100%  /* for text fields */
width:        40px  /* for numeric priority fields */
text-align:   center  /* numeric only */
```

---

### Select

```
height:       30px
border:       1px solid var(--border)
border-radius: 4px
font-size:    0.8rem
padding:      0 8px
background:   var(--bg-surface)
```

---

### Label — Field

Appears above every input. Never replaces a `<label>` element.

```
display:       block
font-size:     0.7rem
font-weight:   700
color:         var(--text-secondary)
text-transform: uppercase
margin-bottom: 4px
```

---

### Table

All tables share this structure. Column-specific overrides are defined per-workflow.

**Table container:**
```
width:           100%
border-collapse: collapse
font-size:       0.8rem
text-align:      left
table-layout:    fixed
```

**Header row (`<thead>`):**
```
background:    var(--bg-header)
color:         var(--text-secondary)
font-weight:   600
```

**Header cell (`<th>`):**
```
padding:       6px 8px
border-bottom: 1px solid var(--border)
```

**Body row (`<tr>`):**
```
background:    var(--bg-surface)
border-bottom: 1px solid var(--border-subtle)
transition:    background 0.1s
```
`:hover` → `background: var(--bg-app)`

**Body cell (`<td>`):**
```
padding:       8px
overflow:      hidden
text-overflow: ellipsis
white-space:   nowrap
```

**Accessibility:** Tables that list selectable items should use `<tbody>` with `<button>` inside cells for actions, not row-level click handlers.

---

### Badge — Status

Appears in list rows and inspector panels to show item state.

```
display:       inline-block
font-size:     0.75rem
padding:       2px 6px
border-radius: 4px
font-weight:   500
```

| State | Background | Text |
|---|---|---|
| Verified | `var(--status-ok-bg)` | `var(--status-ok)` |
| Notebook | `var(--status-warn-bg)` | `var(--status-warn)` |
| Draft | `var(--bg-header)` | `var(--text-secondary)` |
| Active | `var(--status-ok-bg)` | `var(--status-ok)` |
| Degraded | `var(--status-warn-bg)` | `var(--status-warn)` |
| Down / Error | `var(--status-error-bg)` | `var(--status-error)` |
| Soon (future feature) | `var(--bg-header)` | `var(--text-secondary)` |

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
  border: 1px solid var(--border);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 4px;
  background: var(--accent);         /* active run */
}
.progress-fill.stalled {
  background: #f59e0b;               /* stalled / slow run */
}
```

---

### Toolbar

One per page. Contains three zones.

```css
.toolbar {
  height: 48px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 12px;
  flex-shrink: 0;
}
.toolbar-divider {
  width: 1px;
  height: 24px;
  background: var(--border);
}
.toolbar-zone-left   { flex: 1; display: flex; align-items: center; gap: 8px; min-width: 0; }
.toolbar-zone-center { flex: 1; display: flex; align-items: center; gap: 8px; min-width: 0; }
.toolbar-zone-right  { display: flex; gap: 8px; flex-shrink: 0; }
```

---

### Filter Popup

```css
.filter-popup {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  width: 280px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.10);
  z-index: 100;
  font-size: 0.8rem;
}
.filter-popup-header {
  font-weight: 700;
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 4px;
  margin-bottom: 8px;
}
.filter-rule-row {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
}
```

**Accessibility:** The filter trigger button must have `aria-haspopup="true"` and `aria-expanded` reflecting open state. The popup must be dismissible by Escape (returns focus to trigger) and by clicking outside.

---

### Section Header

Used inside panels to label groups of related fields.

```css
.section-header {
  font-size: 0.9rem;
  font-weight: 700;
  color: #475569;
  border-bottom: 1px solid var(--border);
  padding-bottom: 4px;
  margin-bottom: 12px;
}
```

---

### Inspector Panel

Right-side detail panel. Used in Knowledge and Settings.

```css
.inspector {
  background: var(--bg-app);
  border-left: 1px solid var(--border);
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.inspector-field-label {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  margin-bottom: 4px;
}
.inspector-field-value {
  font-size: 0.875rem;
  color: var(--text-primary);
  line-height: 1.6;
}
.inspector-inset {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  padding: 10px 12px;
  border-radius: 6px;
}
```

---

### Tab Bar (Settings only)

Replaces the standard toolbar on the Settings page.

```css
.tab-bar {
  height: 44px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 4px;
}
```

**Tab button — inactive:**
```css
height: 36px;
padding: 0 16px;
background: transparent;
border: 1px solid transparent;
border-bottom: 1px solid transparent;
border-radius: 4px 4px 0 0;
font-size: 0.8rem;
color: var(--text-secondary);
cursor: pointer;
```

**Tab button — active:**
```css
background: var(--bg-active);
border: 1px solid var(--border);
border-bottom: 1px solid var(--bg-surface);   /* overlap trick */
color: var(--accent);
font-weight: 600;
```

**Required ARIA attributes on tab container:** `role="tablist"`
**Required ARIA attributes on each tab:** `role="tab"`, `aria-selected="true|false"`, `aria-controls="{panelId}"`
**Required ARIA attributes on panel:** `role="tabpanel"`, `id="{panelId}"`, `aria-labelledby="{tabId}"`

---

### Sidebar

```css
.sidebar {
  width: 180px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.sidebar-wordmark {
  padding: 12px 8px;
  background: var(--bg-header);
  border-bottom: 1px solid var(--border);
  font-weight: 800;
  font-size: 0.85rem;
  color: var(--accent);
  text-transform: uppercase;
}
.sidebar-nav-item {
  padding: 6px 12px;
  font-size: 0.8rem;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.1s;
}
.sidebar-nav-item:hover {
  background: rgba(0,0,0,0.04);
}
.sidebar-nav-item.active {
  background: var(--bg-surface);
  border-left: 3px solid var(--accent);
  padding-left: 9px;   /* compensate for 3px border */
  color: var(--accent);
  font-weight: 600;
}
```

---

### Toast Notification

```html
<div id="toast-container" role="alert" aria-live="polite" aria-atomic="true">
  <!-- Toasts injected here by JS -->
</div>
```

`role="alert"` ensures screen readers announce toast content immediately.

---

### Artifact Card (Knowledge list item)

Each artifact in the Knowledge list is a `<button>` element.

```css
.artifact-card {
  display: block;
  width: 100%;
  text-align: left;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  cursor: pointer;
  transition: border-color 0.1s, box-shadow 0.1s;
}
.artifact-card:hover {
  border-color: var(--accent);
}
.artifact-card.selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-ring);
}
.artifact-card-title {
  font-weight: 600;
  font-size: 0.85rem;
  margin-bottom: 4px;
}
.artifact-card-preview {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.artifact-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}
```

---

### List Column with Inspector Split

Pattern for any page with a list panel on the left and an inspector on the right.

```css
.list-inspector-split {
  flex: 1;
  display: flex;
  overflow: hidden;
}
.list-panel {
  width: 300px;       /* Settings */
  /* or flex: 1 for Knowledge list */
  border-right: 1px solid var(--border);
  overflow-y: auto;
  background: var(--bg-surface);
}
.inspector-panel {
  flex: 1;
  /* or width: 350px for Knowledge */
  overflow-y: auto;
}
```

---

## Accessibility Checklist (Per Component)

| Component | Requirement |
|---|---|
| All buttons | `<button>` element. Never `<div>` or `<span>`. |
| All inputs | Associated `<label>` via `for`/`id`. |
| Icon-only buttons | `aria-label` describing the action. |
| List items (artifact cards) | `<button>` or `<a>`. `role="listitem"` if in a `<ul>`. |
| Tab bar | `role="tablist"`, `role="tab"`, `aria-selected`. |
| Tab panels | `role="tabpanel"`, `aria-labelledby`. |
| Modal/popup | `role="dialog"`, `aria-modal="true"`, focus trap on open, Escape closes. |
| Filter popup | `aria-haspopup`, `aria-expanded`. |
| Toast container | `role="alert"` or `aria-live="polite"`. |
| HTMX swap targets | `aria-live="polite"` where content changes affect user task. |
| Status indicators | Text equivalent alongside any color or icon indicator. |
| Progress bars | `role="progressbar"`, `aria-valuenow`, `aria-valuemin`, `aria-valuemax`. |
