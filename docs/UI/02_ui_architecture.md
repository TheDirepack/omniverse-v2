# Omniverse V2 — UI Architecture
## Structure, Navigation & Shared Patterns

---

## 1. Workflow Model

Omniverse is organized into five primary workflows. Each is a distinct mode of interaction with a dedicated page:

| Workflow | Nav Label | Purpose |
|---|---|---|
| Research | 🔍 Research | Select worlds, set research focus, initiate runs |
| Knowledge | 🕸️ Knowledge | Browse, inspect, and act on research artifacts |
| Theory | ⚖️ Theory | Extrapolation theories (speculative reasoning) |
| Logs | 📜 Logs | Monitor active runs, view logs, abort |
| Settings | ⚙️ Settings | Configure providers, routes, and application globals |

Workflows are not nested. There are no sub-pages within a workflow — each workflow is a single page, optionally composed of multiple panels.

---

## 2. Application Shell

The shell is the persistent frame that surrounds every workflow. It does not change between pages.

```
┌────────────────────────────────────────────────────────┐
│ SIDEBAR (256px)  │  CONTENT AREA (flex: 1)             │
│                  │                                      │
│  [Wordmark]      │  [TOOLBAR (48px, fixed height)]      │
│  [Dark toggle]   │  ─────────────────────────────────  │
│  [Nav items]     │  [CONTENT (scrollable)]              │
│  [Version]       │                                      │
└────────────────────────────────────────────────────────┘
```

**Shell rules:**
- The shell is flush against all browser window edges. No outer margin, no border, no padding.
- `body` and the shell container: `margin: 0; padding: 0; height: 100vh; display: flex; overflow: hidden`
- The sidebar never scrolls (uses `no-scrollbar`).
- The content area scrolls independently via `overflow-y: auto`.
- The toolbar is fixed in height and never scrolls.
- Sidebar width: 256px (`w-64`). This was increased from 180px in earlier designs.

---

## 3. Sidebar Navigation

The sidebar is the persistent left panel visible in every workflow.

**Structure:**
- Wordmark bar (top): `OMNIVERSE V2` — `text-xs font-black tracking-tighter uppercase text-gray-400`
- Dark mode toggle button (top-right of wordmark bar)
- Nav items: one per workflow, in order: Home, Research, Validation, Knowledge, Theory, Flow, Logs, Settings
- Footer: version label `v2.0.0-stable` at bottom

**Active state:** `bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-semibold`

**Inactive state:** `text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-800`

**The sidebar is visually quiet.** It does not use icons as primary navigation — the emoji icons are decorative prefixes only. The nav label is the primary identifier. The sidebar never competes with the content area for visual weight.

---

## 4. Toolbar Pattern

Every content area has one toolbar: a fixed-height horizontal bar at the top, flush with the sidebar's right edge and the viewport's top edge.

**The toolbar is always divided into three zones by 1px dividers:**

```
[ LEFT: Context / Identity ] | [ CENTER: Search & Filter ] | [ RIGHT: Primary Actions ]
```

- **Left zone:** The current context — what world is active, what the global focus is, or what page section is active.
- **Center zone:** Search input + Filter trigger. These are always present in workflows with lists.
- **Right zone:** Primary CTA and secondary actions. CTAs are right-aligned and right-to-left ordered by importance.

**Height:** 48px standard. 44px in Settings (tab bar replaces standard toolbar).

**The toolbar never contains secondary navigation.** Tabs (Settings) are a special case and replace the toolbar entirely for that page.

---

## 5. Filter System

Filtering is a reusable, composable query mechanism available in Research and Execution. It is not a simple search box.

**Pattern:** A "⚙️ Filter" button in the toolbar center zone opens a popup Query Builder.

**Implementation:** The filter popup is generated client-side by the `toggleFilterPopup()` JavaScript function (defined inline in each page template). This function:
1. Creates a `<div>` with `role="dialog"`, `aria-modal="true"`, `aria-label="Filter query builder"`
2. Builds rule rows with Field → Operator → Value selects/inputs
3. Adds + Add Rule, Clear, and Apply buttons

**Query Builder popup:**
```
┌──────────────────────────────────┐
│ Query Builder                    │
├──────────────────────────────────┤
│ [Field ▾]  [is ▾]  [Value    ]  │
│ [+ Add Rule]                     │
├──────────────────────────────────┤
│ [Clear]              [Apply]     │
└──────────────────────────────────┘
```

- Fields vary by page: Research (World Name, Category, Status, Date), Execution (Status, World, Progress)
- Operators: `is`, `is not`, `contains`
- Multiple rules are ANDed together
- "Apply" triggers an HTMX GET request with filter params; "Clear" removes all rules and reloads default view
- The popup closes on Escape or clicking outside (handled by global `click` and `keydown` listeners)
- The "⚙️ Filter" button shows `aria-expanded` reflecting open state
- A server-rendered template also exists at `components/filter_popup.html` for cases where server-side rendering of the popup is preferred

---

## 6. Inspector Pattern

The Inspector is the right-side detail panel that appears in Knowledge (world detail phase) and Settings workflows. It is revealed by selecting an item from a list.

**Rules:**
- Width: fixed 320px (`w-80`) in Knowledge inspector
- Settings providers/routes use `flex: 1` in a list-inspector split
- Always a child of the content area, not an overlay
- Always visible when an item is selected; never shown empty
- Scrolls independently if content overflows
- Contains: title, structured fields, action buttons

The list + inspector split is a fundamental pattern. The list provides navigation; the inspector provides depth. They always appear side by side, never stacked.

---

## 7. HTMX Strategy

HTMX drives all dynamic content. These are the conventions:

- **Page navigation:** Full-page navigation via sidebar `<a>` links (standard navigation, not htmx-boosted)
- **Tab switching:** HTMX fragment swaps targeting the tab content panel (e.g., `/knowledge/world/{id}/tab/{tab_name}`)
- **Inspector loading:** HTMX `hx-get` on list items, swapping the inspector region
- **Filter application:** HTMX `hx-get` with filter query params, swapping the list region
- **Search:** HTMX `hx-get` with `keyup changed delay:300ms` trigger, swapping the list region
- **Form submission:** HTMX `hx-post` for all save/update/delete actions, returning updated fragment
- **Toasts:** Backend sends `HX-Trigger: {"showToast": ...}` response header; JS catches and renders
- **Polling:** Execution page refreshes run table via `hx-trigger="load, every 5s"`

**All HTMX swap targets are ARIA live regions** where the content change is meaningful to assistive technology users.

---

## 8. Backend Data Mapping

These are the backend relationships the UI must faithfully represent:

**Providers**
A Provider has: name, type (e.g., `openai`, `anthropic`, `ollama`), base URL, supported models (CSV string), and one or more API Keys.

**API Keys**
Each API Key belongs to exactly one Provider. Each Key has a `priority` integer. Higher priority = tried first during inference. The UI must allow adding, editing, and deleting keys on a per-provider basis.

**Routes**
A Route maps a task type (agent identifier) to an ordered list of Providers, each with a specified model. The Route defines fallback order — if Provider 1 fails, Provider 2 is tried. The UI must make this chain explicit.

**Sync Models**
The UI provides a "🔄 Sync" action on individual providers. This triggers a backend call to the provider's `/models` endpoint and populates the supported models field with the live result.

---

## 9. Template File Map

```
backend/app/templates/
├── base.html                              # Shell, sidebar (256px), global JS, toast system, Tailwind CDN, dark mode
├── layout/
│   ├── 3_panel.html                       # 3-panel layout (left | center | right) — extends base.html
│   └── 3_panel_macro.html                 # Jinja2 macro for 3_panel blocks
├── pages/
│   ├── research.html                      # extends base.html — toolbar + world table (HTMX-loaded)
│   ├── research_results.html              # Research results display
│   ├── knowledge.html                     # extends base.html — two-phase (world list → world detail with tabs)
│   ├── logs.html                          # extends base.html — toolbar + execution run table
│   └── settings.html                      # Settings shell (uses 3_panel layout)
└── components/
    ├── filter_popup.html                  # Server-rendered Query Builder popup widget
    ├── world_row.html                     # Single world tree row (3-panel hierarchy view)
    ├── database_worlds.html               # Research world table fragment (checkbox + name + status + actions)
    ├── knowledge_world_list.html          # Phase 1: world list for Knowledge page
    ├── knowledge_world_detail.html        # Phase 2: world detail with 4 sub-tabs
    ├── knowledge_overview_tab.html        # Overview: stats grid, recent artifacts, raw data, theory
    ├── knowledge_notebook_tab.html        # Notebook entries + claims list
    ├── knowledge_theory_tab.html          # Theory display or "Generate Theory" prompt
    ├── artifact_list.html                 # Artifacts tab content
    ├── artifact_detail.html               # Artifact inspector detail fragment
    ├── notebook_artifact_card.html        # Single notebook artifact card
    ├── notebook_claim_card.html           # Single notebook claim card
    ├── research_notebook.html             # Research notebook panel
    ├── research_notebook_entry.html       # Single notebook entry
    ├── research_sources.html              # Research sources panel
    ├── research_timeline.html             # Research timeline
    ├── research_history.html              # Research history
    ├── research_queue.html                # Research queue
    ├── active_runs_table.html             # Execution runs table fragment
    ├── log_list.html                      # Log list fragment
    ├── settings_general.html              # Settings General tab content
    ├── settings_providers.html            # Settings Providers tab (list + inspector)
    ├── settings_routes.html               # Settings Routes tab (list + inspector)
    ├── settings_health.html               # Settings Health tab (status matrix)
    ├── provider_form.html                 # Provider edit form
    ├── route_form.html                    # Route edit form
    ├── _route_slot.html                   # Route chain row partial
    ├── world_list.html                    # World hierarchy tree
    ├── world_detail.html                  # World detail in 3-panel
    ├── world_hierarchy.html               # World hierarchy fragment
    ├── world_snapshots.html               # World snapshot list
    ├── world_create_form.html             # Create world form
    ├── world_import_list.html             # World import list
    ├── world_neighborhood.html            # World neighborhood graph
    ├── entity_detail.html                 # Entity detail inspector
    ├── theory_card.html                   # Theory card component
    ├── rule_item.html                     # Tier rule item
    ├── all_rules_updated.html             # Rules updated notification
    ├── flow_step.html                     # Flow step component
    ├── run_phase_details.html             # Run phase detail
    ├── provenance_trace.html              # Provenance trace display
    ├── acquisition_panel.html             # Acquisition cache panel
    ├── focused_search_panel.html          # Focused search panel
    ├── database_worlds.html               # Research world database list
    └── ... (additional support components)
└── workflow/
    └── tiering/
        └── tiering.html                   # extends base.html via 3_panel.html
```

**Template inheritance:**
- `Research`, `Knowledge`, `Execution` (`logs.html`) extend `base.html` directly (no `3_panel.html`)
- `Settings` extends `3_panel.html` (list + inspector split requires the 3-panel layout)
- `Tiering` extends `base.html` via `3_panel.html`
- `fragments/` directory exists but is empty; all components live in `components/`

---

## 10. Knowledge Page — Two-Phase Design

The Knowledge page implements a two-phase flow:

**Phase 1 (World Selection)** — `?world_id` not set:
- Full-width, scrollable world list
- Each row shows: world name, franchise, last researched date, artifact count, explored/pending badge
- Clicking a world navigates to `/knowledge?world_id={uuid}`

**Phase 2 (World Detail)** — `?world_id={uuid}` set:
- Toolbar shows "← Back to worlds" button + world name
- 4 sub-tabs in a tab bar: Overview | Artifacts | Notebook | Theory
- Right-side inspector (`w-80`) for artifact/notebook entry detail
- "Start Focused Research" button in tab bar
- Tab content loaded via `GET /knowledge/world/{id}/tab/{tab_name}`
- Inspector loaded via `GET /knowledge/notebook/entry/{id}`

`base.html` is used directly — no `3_panel.html` is involved.
