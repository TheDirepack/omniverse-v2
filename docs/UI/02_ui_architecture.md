# Omniverse V2 — UI Architecture
## Structure, Navigation & Shared Patterns

---

## 1. Workflow Model

Omniverse is organized into five primary workflows. Each is a distinct mode of interaction with a dedicated page:

| Workflow | Nav Label | Purpose |
|---|---|---|
| Research | 🔍 Research | Select worlds, set research focus, initiate runs |
| Knowledge | 📚 Knowledge | Browse, inspect, and act on research artifacts |
| Tiering | ⚖️ Tiering | (Forthcoming) Tier and rank entities |
| Execution | ⚙️ Execution | Monitor active runs, view logs, abort |
| Settings | 🛠️ Settings | Configure providers, routes, and application globals |

Workflows are not nested. There are no sub-pages within a workflow — each workflow is a single page, optionally composed of multiple panels.

---

## 2. Application Shell

The shell is the persistent frame that surrounds every workflow. It does not change between pages.

```
┌────────────────────────────────────────────────────────┐
│ SIDEBAR (180px)  │  CONTENT AREA (flex: 1)             │
│                  │                                      │
│  [Wordmark]      │  [TOOLBAR (48px, fixed height)]      │
│  [Nav items]     │  ─────────────────────────────────  │
│                  │  [CONTENT (scrollable)]              │
│                  │                                      │
└────────────────────────────────────────────────────────┘
```

**Shell rules:**
- The shell is flush against all browser window edges. No outer margin, no border, no padding.
- `body` and the shell container: `margin: 0; padding: 0; height: 100vh; display: flex; overflow: hidden`
- The sidebar never scrolls.
- The content area scrolls independently via `overflow-y: auto`.
- The toolbar is fixed in height and never scrolls.

---

## 3. Sidebar Navigation

The sidebar is the persistent left panel visible in every workflow.

**Structure:**
- Wordmark bar (top, fixed): app name `OMNIVERSE_V2`
- Nav items: one per workflow, in order
- No footer or user section visible (removed in v8 onward as non-essential chrome)

**Active state:** `background: white`, `border-left: 3px solid --accent`, `color: --accent`, `font-weight: 600`

**Inactive state:** transparent background, `color: --text-secondary`

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
- **Right zone:** Primary CTA (e.g., "Start Research", "Start Focused Research") and secondary actions (e.g., "Add World"). CTAs are right-aligned and right-to-left ordered by importance.

**Height:** 48px standard. 44px in Settings (tab bar replaces standard toolbar).

**The toolbar never contains secondary navigation.** Tabs (Settings) are a special case and replace the toolbar entirely for that page.

---

## 5. Filter System

Filtering is a reusable, composable query mechanism available in Research, Knowledge, and Execution. It is not a simple search box.

**Pattern:** A "⚙️ Filter" button in the toolbar center zone opens a popup Query Builder.

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

- Fields vary by workflow (Research: Category, Status, Date; Knowledge: Type, Status, World; Execution: Status, World, Progress)
- Operators: `is`, `is not`, `contains`, `>`, `<` (available set depends on field type)
- Multiple rules are ANDed together
- "Apply" triggers an HTMX request with filter params; "Clear" removes all rules and reloads the default view
- The popup closes on Escape or clicking outside
- The "⚙️ Filter" button shows an active indicator (filled dot or badge count) when filters are applied

---

## 6. Inspector Pattern

The Inspector is the right-side detail panel that appears in Knowledge and Settings workflows. It is revealed by selecting an item from a list.

**Rules:**
- Width: fixed (350px in Knowledge, flex: 1 in Settings)
- Always a child of the content area, not an overlay
- Always visible when an item is selected; never shown empty
- Scrolls independently if content overflows
- Contains: title, structured fields, action buttons

The list + inspector split is a fundamental pattern. The list provides navigation; the inspector provides depth. They always appear side by side, never stacked.

---

## 7. HTMX Strategy

HTMX drives all dynamic content. These are the conventions:

- **Page navigation:** Full-page HTMX swaps via sidebar nav links (`hx-boost` or `hx-get` on the shell content region)
- **Tab switching:** HTMX fragment swaps targeting the tab content panel
- **Inspector loading:** HTMX `hx-get` on list items, swapping the inspector region
- **Filter application:** HTMX `hx-post` with filter params, swapping the list region
- **Form submission:** HTMX `hx-post` for all save/update/delete actions, returning updated fragment
- **Toasts:** Backend sends `HX-Trigger: {"showToast": ...}` response header; JS catches and renders

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
The UI provides a "🔄 Sync" action on individual providers. This triggers a backend call to the provider's `/models` endpoint and populates the supported models field with the live result. This requires a new backend endpoint: `POST /settings/providers/{id}/sync-models`.

---

## 9. Template File Map

```
backend/app/templates/
├── base.html                              # Shell, sidebar, global JS, toast system
└── pages/
    ├── research.html                      # Research Hub (toolbar + world table)
    ├── knowledge.html                     # Knowledge Hub (toolbar + list + inspector)
    ├── logs.html                          # Execution Hub (toolbar + run table)
    └── settings.html                      # Settings shell + tab bar
└── fragments/
    ├── filter_popup.html                  # Query Builder popup (reusable)
    ├── world_row.html                     # Single world table row
    ├── research_notebook.html             # Artifact list panel
    ├── research_notebook_entry.html       # Single artifact card
    ├── settings_general.html              # General tab content
    ├── settings_providers.html            # Providers tab (list + inspector)
    ├── settings_routes.html               # Routes tab (list + inspector)
    └── settings_health.html              # Health tab (status matrix)
```
