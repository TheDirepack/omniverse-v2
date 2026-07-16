# Omniverse V2 — Workflow Specification
## Page Compositions

Each workflow is a composition of the components defined in `03_component_specification.md`. This document specifies only what is unique to each page — layouts, column definitions, and workflow-specific interactions. All styling values come from the component spec.

---

## 1. Research Hub — `/research`

**Job:** Select fictional worlds to research, define a global research focus, and initiate research runs.

### Layout

```
┌────────────────────────────────────────────────────────────┐
│ TOOLBAR                                                     │
│ [Focus: ________________] | [Search] [Filter] | [+ Add World] [Start Research] │
├────────────────────────────────────────────────────────────┤
│ WORLD TABLE                                                 │
│ [✓] World Name          │ Category │ Last Researched │ [Explore] │
│ [✓] The Elder Scrolls   │ High Fantasy │ 2026-07-10 │ [Explore] │
│ [✓] Warhammer 40k       │ Grimdark │ 2026-07-12     │ [Explore] │
└────────────────────────────────────────────────────────────┘
```

### Toolbar Zones

| Zone | Contents |
|---|---|
| Left | Label `FOCUS:` (field label style) + text input (`flex: 1`, placeholder "Overall research objective...") |
| Center | Text input (200px, placeholder "Search worlds...") + "⚙️ Filter" button |
| Right | "Add World" (secondary) + "Start Research" (primary) |

**Global Focus** is the research objective that will be passed to all research runs initiated from this page. It persists for the session.

### World Table

Column spec:

| Column | Width | Notes |
|---|---|---|
| Checkbox | 40px | `<th>` has a "select all" checkbox. Each `<td>` has a row checkbox. |
| World Name | flex | `font-weight: 600`, `text-overflow: ellipsis` |
| Category | 150px | |
| Last Researched | 120px | Date string |
| Action | 100px | "Explore" secondary button, right-aligned |

**"Explore"** navigates to the Knowledge Hub filtered to that world.

**"Start Research"** initiates a research run for all checked worlds, using the current Global Focus value.

**Multi-select behavior:** Checking/unchecking individual rows or the "select all" header checkbox updates the selection state. The "Start Research" button text reflects the count when more than one is selected (e.g., "Start Research (3)").

### Filter — Research

Available fields: Category, Status (Researched / Not Started / In Progress), Last Researched (date range).

---

## 2. Knowledge Hub — `/knowledge`

**Job:** Browse and inspect research artifacts (claims, entries, entities) for a selected world.

### Layout

```
┌────────────────────────────────────────────────────────┐
│ TOOLBAR                                                 │
│ [World: Elder Scrolls ▾] | [Search] [Filter] | [Start Focused Research] │
├──────────────────────────┬─────────────────────────────┤
│ ARTIFACT LIST            │ INSPECTOR                   │
│ (flex: 1)                │ (350px)                     │
│                          │                             │
│ [Artifact card]          │ [Field: Artifact Name]      │
│ [Artifact card]          │ [Field: Full Description]   │
│  ← selected →            │ [Section: Evidence]         │
│ [Artifact card]          │ [Edit Artifact button]      │
└──────────────────────────┴─────────────────────────────┘
```

### Toolbar Zones

| Zone | Contents |
|---|---|
| Left | "World:" label + world name (styled as a link/dropdown to switch world) |
| Center | Search input + "⚙️ Filter" button |
| Right | "Start Focused Research" (primary button) |

**"Start Focused Research"** initiates a research run specifically targeting the selected artifact or the current world + search/filter context.

### Artifact List

- Contains a scrollable list of `.artifact-card` components
- Each card is a `<button>` element
- Cards show: title (type + name), 2-line preview, timestamp, status badge
- Clicking a card loads the inspector via HTMX (swaps the inspector region)
- Selected card gets `.selected` class

### Inspector

Fields displayed for selected artifact:

| Field | Notes |
|---|---|
| Artifact Name | `font-weight: 600`, `font-size: 1rem` |
| Full Description | `.inspector-field-value` in `.inspector-inset` |
| Evidence & Provenance | List of source links in `.inspector-inset`. Each source: link text (color: `--accent`, underline) + confidence label (right-aligned, muted, e.g., "High") |

Bottom of inspector: "Edit Artifact" — primary button, full-width.

### Filter — Knowledge

Available fields: Type (Artifact / Claim / Entity), Status (Verified / Notebook / Draft), World.

---

## 3. Execution Hub — `/logs`

**Job:** Monitor active and recent research runs. View logs. Abort individual runs or all runs.

### Layout

```
┌────────────────────────────────────────────────────────┐
│ TOOLBAR                                                 │
│ [Filter runs...] [⚙️ Filter]       [VIEW ALL LOGS] [ABORT ALL] │
├────────────────────────────────────────────────────────┤
│ RUN TABLE                                               │
│ World │ Focus │ Progress ████░░ │ % │ [Logs] [Abort]   │
│ Elder Scrolls │ Divine Artifacts │ ████░░░ │ 65% │ ...  │
└────────────────────────────────────────────────────────┘
```

### Toolbar Zones

| Zone | Contents |
|---|---|
| Left | Search input ("Filter runs...") + "⚙️ Filter" button |
| Center | (empty) |
| Right | "VIEW ALL LOGS" (secondary) + "ABORT ALL" (danger filled) |

### Run Table

Column spec:

| Column | Width | Notes |
|---|---|---|
| World | flex | `font-weight: 600` |
| Focus | flex | `color: var(--text-secondary)` |
| Progress | 150px | Inline progress bar component |
| % | 50px | Centered, `font-weight: 600` |
| Actions | auto | "Logs" (secondary, 0.75rem) + "Abort" (danger outline, 0.75rem), right-aligned, gap 4px |

**Progress color rules:**
- 0–100% active run: `var(--accent)` (blue)
- Stalled or very slow: amber (`#f59e0b`)
- Completed: `var(--status-ok)` (green) — row may be styled differently or removed

**"Logs"** expands or navigates to a log view for that run.

**"Abort"** sends abort signal to that specific run. Shows confirmation state inline (the button changes to "Confirm Abort?" with a short timeout) before sending.

**"ABORT ALL"** aborts all active runs. Same inline confirmation pattern.

**"VIEW ALL LOGS"** opens or reveals the full log stream, either as a panel below the table or a separate view.

### Filter — Execution

Available fields: Status (Running / Stalled / Completed / Aborted), World, Progress (> / <).

---

## 4. Settings Hub — `/settings`

**Job:** Configure AI providers, routing, application globals, and view system health.

### Layout

```
┌───────────────────────────────────────────────────────┐
│ TAB BAR                                               │
│ [General] [Providers*] [Routes] [Health]              │
├─────────────────────────┬─────────────────────────────┤
│  (tab-specific content) │  (tab-specific content)     │
└─────────────────────────┴─────────────────────────────┘
```

The Settings page replaces the standard toolbar with a tab bar. All content is loaded via HTMX fragment swaps targeting the tab panel region.

---

### 4.1 General Tab

**Layout:** Single scrollable form panel with section headers.

**Sections:**

**General Configuration**
2-column grid layout:

| Field | Type | Notes |
|---|---|---|
| Application Name | text input | |
| Database URL | text input | |
| Default Research Model | select | Options from available provider models |

**Quick Provider Access** (read-only summary table)

| Column | Notes |
|---|---|
| Provider | Provider name |
| Model | Primary model |
| Status | "● Active" in `--status-ok` or "● Error" in `--status-error` |

**Footer action bar** (fixed to bottom of panel):
- Height: 52px, `background: var(--bg-surface)`, `border-top: 1px solid var(--border)`
- Right-aligned: "Cancel" (secondary) + "Save Changes" (primary)

---

### 4.2 Providers Tab

**Layout:** List (300px) + Inspector (flex: 1) split.

**Provider List:**

Header row: "PROVIDERS" label (field label style) + "+ New" button.

Each list item:
- Name: `font-weight: 600`, `font-size: 0.8rem`
- Subtitle: `provider_type / first two models...`, `font-size: 0.7rem`, `color: var(--text-secondary)`
- Active item: `background: var(--bg-active)`, `border-left: 3px solid var(--accent)`

**Provider Inspector:**

Title row: Provider name (`font-weight: 800`, `1.1rem`) + "Delete" (secondary) + "Save Provider" (primary), right-aligned.

Form fields:

| Field | Layout | Notes |
|---|---|---|
| Provider Type | 2-column grid (left) | e.g., `openai`, `anthropic`, `ollama` |
| Base URL | 2-column grid (right) | e.g., `https://api.openai.com/v1` |
| Supported Models | Full width, with inline button | CSV string + "🔄 Sync" button |

**🔄 Sync button:**
- Appears inline to the right of the Supported Models input
- Secondary style, `height: 30px`, `padding: 0 12px`
- `title="Fetch models from provider API"`
- On click: button shows loading state ("Syncing..."), sends `POST /settings/providers/{id}/sync-models`, updates the input with returned model list
- This backend endpoint does not currently exist and must be created

**API Keys table:**

Preceded by: "API KEYS & PRIORITY" label (field label style) + "+ Add Key" button (right-aligned).

| Column | Width | Notes |
|---|---|---|
| Key | flex | Inline text input, value masked as `sk-proj-...` |
| Priority | 80px | Inline numeric input, centered |
| Action | 60px | "Delete" ghost button in `--danger` |

---

### 4.3 Routes Tab

**Layout:** List (300px) + Inspector (flex: 1) split.

**Route List:**

Each item represents a task type (agent identifier).
- Name: task type label, `font-weight: 600`
- Subtitle: summary of provider chain (e.g., "OpenAI-Main → Anthropic-Pro")

**Route Inspector:**

Title: Task type name.

**Provider Chain** (the core UI element of this tab):

Each row in the chain:

| Column | Notes |
|---|---|
| Priority | Number input (order in chain) |
| Provider | Select from configured providers |
| Model | Select from that provider's supported models |
| Action | "Remove" ghost button |

"+ Add Provider to Chain" — secondary button below the table.

**Override Default Routes** — checkbox at bottom. When checked, this route config replaces the global default.

---

### 4.4 Health Tab

**Layout:** Single scrollable panel.

**Model Status Matrix:**

A table where rows = providers and columns = models. Each cell shows the live status of that provider/model combination.

| Provider | gpt-4o | gpt-4-turbo | claude-3-5 |
|---|---|---|---|
| OpenAI-Main | ✅ Active | ✅ Active | — |
| Anthropic-Pro | — | — | ✅ Active |
| Local-Ollama | — | — | — |

Status cell values: "✅ Active" (`--status-ok`), "⚠️ Degraded" (`--status-warn`), "❌ Down" (`--status-error`), "—" (not configured).

**Snapshot Manager:**
- Shows: "Last checked: [timestamp]"
- "Refresh" button (secondary) — triggers a new health check against all configured providers

---

## 5. Tiering — `/tiering` (Forthcoming)

This workflow is listed in navigation with a "Soon" badge on the nav item. The page itself is a placeholder stating the feature is forthcoming. The nav item is visible and labeled but clicking it navigates to a placeholder page rather than being disabled.

Badge style on nav item: `background: var(--bg-header); color: var(--text-secondary); font-size: 0.7rem; padding: 2px 4px; border-radius: 4px; margin-left: 8px;`
