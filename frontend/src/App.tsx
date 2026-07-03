import { useEffect, useMemo, useState } from "react";
import { Layers, Lightbulb, Loader2, Play, Settings, Terminal } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { groupWorldsByTier } from "./lib/tiers";

type Tab = "dashboard" | "database" | "theories" | "settings";

type World = {
  id: number;
  name: string;
  summary: string | null;
  is_explored: boolean;
  tier: number | null;
  tier_justification: string | null;
  theory: string | null;
  theory_audit: string | null;
};

type Anomaly = {
  world_id: number | null;
  description: string;
  detected_at: string;
};

type LogEntry = {
  node_name: string;
  thought: string;
  status: string;
  created_at: string;
};

type ProviderRecord = {
  id: number;
  name: string;
  provider_type: string | null;
  base_url: string | null;
  models: string | null;
  keys: Array<{ id: number; api_key: string; priority: number }>;
};

type AgentRouteRecord = {
  id: number;
  task_type: string;
  provider_id: number | null;
  model_name: string | null;
  priority: number;
};

type WorldRecord = {
  id: number;
  name: string;
  summary: string | null;
  is_explored: boolean;
};

const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const taskTypes = ["RESEARCH", "AUDIT", "SYNTHESIS", "ARCHITECT", "THEORY", "MANAGER"];

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [worldsInput, setWorldsInput] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [worlds, setWorlds] = useState<World[]>([]);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [tierSystem, setTierSystem] = useState<string | null>(null);
  const [settings, setSettings] = useState<Record<string, string | null>>({});
  const [providers, setProviders] = useState<ProviderRecord[]>([]);
  const [agentRoutes, setAgentRoutes] = useState<AgentRouteRecord[]>([]);
  const [worldRegistry, setWorldRegistry] = useState<WorldRecord[]>([]);
  const [newWorldName, setNewWorldName] = useState("");
  const [focusedWorld, setFocusedWorld] = useState("");
  const [focusedFeature, setFocusedFeature] = useState("");
  const [selectedWorldId, setSelectedWorldId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    void refreshResults();
    void refreshSettings();
    void refreshProviders();
    void refreshAgentRoutes();
    void refreshWorldRegistry();
  }, []);

  useEffect(() => {
    if (!runId) return;
    setLogs([]);
    setRunning(true);
    const source = new EventSource(`${apiBase}/api/logs/${runId}`);
    source.onmessage = event => {
      const data = JSON.parse(event.data) as LogEntry & { finished?: boolean };
      if (data.finished) {
        source.close();
        setRunning(false);
        void refreshResults();
        return;
      }
      setLogs(prev => [...prev, data]);
    };
    source.onerror = () => {
      source.close();
      setRunning(false);
    };
    return () => source.close();
  }, [runId]);

  const selectedWorld = useMemo(
    () => worlds.find(world => world.id === selectedWorldId) ?? null,
    [worlds, selectedWorldId]
  );

  const navItems: Array<{ id: Tab; label: string; Icon: LucideIcon }> = [
    { id: "dashboard", label: "Command Center", Icon: Terminal },
    { id: "database", label: "Tiers", Icon: Layers },
    { id: "theories", label: "Theories", Icon: Lightbulb },
    { id: "settings", label: "Settings", Icon: Settings },
  ];

  async function refreshResults() {
    const res = await fetch(`${apiBase}/api/results`);
    if (!res.ok) return;
    const data = await res.json();
    setTierSystem(data.tier_system ?? null);
    setWorlds(data.worlds ?? []);
    setAnomalies(data.anomalies ?? []);
  }

  async function refreshSettings() {
    const res = await fetch(`${apiBase}/api/settings`);
    if (!res.ok) return;
    const data = await res.json();
    setSettings(data.general_settings ?? {});
  }

  async function refreshProviders() {
    const res = await fetch(`${apiBase}/api/providers`);
    if (!res.ok) return;
    const data = await res.json();
    setProviders(data ?? []);
  }

  async function refreshAgentRoutes() {
    const res = await fetch(`${apiBase}/api/agent-routes`);
    if (!res.ok) return;
    const data = await res.json();
    setAgentRoutes(data ?? []);
  }

  async function refreshWorldRegistry() {
    const res = await fetch(`${apiBase}/api/worlds`);
    if (!res.ok) return;
    const data = await res.json();
    setWorldRegistry(data ?? []);
  }

  async function startRun() {
    const payload = worldsInput.split(",").map(v => v.trim()).filter(Boolean);
    if (!payload.length) return;
    const res = await fetch(`${apiBase}/api/orchestrate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ worlds: payload }),
    });
    if (!res.ok) return;
    const data = await res.json();
    setRunId(data.run_id);
  }

  async function saveGeneralSetting(key: string, value: string) {
    setSaving(true);
    await fetch(`${apiBase}/api/settings/general`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, value: value || null }),
    });
    await refreshSettings();
    setSaving(false);
  }

  async function saveProvider(provider: any) {
    setSaving(true);
    await fetch(`${apiBase}/api/providers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(provider),
    });
    await refreshProviders();
    setSaving(false);
  }

  async function saveProviderKey(key: { id?: number; provider_id: number; api_key: string; priority: number }) {
    setSaving(true);
    await fetch(`${apiBase}/api/providers/keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(key),
    });
    await refreshProviders();
    setSaving(false);
  }

  async function deleteProviderKey(keyId: number) {
    setSaving(true);
    await fetch(`${apiBase}/api/providers/keys/${keyId}`, { method: "DELETE" });
    await refreshProviders();
    setSaving(false);
  }

  async function saveAgentRoute(route: any) {
    setSaving(true);
    await fetch(`${apiBase}/api/agent-routes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(route),
    });
    await refreshAgentRoutes();
    setSaving(false);
  }

  async function deleteAgentRoute(routeId: number) {
    setSaving(true);
    await fetch(`${apiBase}/api/agent-routes/${routeId}`, { method: "DELETE" });
    await refreshAgentRoutes();
    setSaving(false);
  }

  async function addWorld() {
    if (!newWorldName.trim()) return;
    setSaving(true);
    await fetch(`${apiBase}/api/worlds`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ world_name: newWorldName.trim(), auto_research: true }),
    });
    setNewWorldName("");
    await refreshWorldRegistry();
    setSaving(false);
  }

  async function resetDatabase() {
    await fetch(`${apiBase}/api/reset-database`, { method: "POST" });
    await refreshResults();
    await refreshWorldRegistry();
    await refreshProviders();
    await refreshAgentRoutes();
  }

  async function clearLogs() {
    await fetch(`${apiBase}/api/clear-logs`, { method: "POST" });
    setLogs([]);
  }

  async function researchUnexplored() {
    const res = await fetch(`${apiBase}/api/worlds/research-unexplored`, { method: "POST" });
    if (!res.ok) return;
    const data = await res.json();
    if (data.run_id) setRunId(data.run_id);
  }

  async function clearAllExplored() {
    await fetch(`${apiBase}/api/worlds/clear-explored`, { method: "POST" });
    await refreshWorldRegistry();
    await refreshResults();
  }

  async function clearWorldExplored(worldId: number) {
    await fetch(`${apiBase}/api/worlds/${worldId}/clear-explored`, { method: "POST" });
    await refreshWorldRegistry();
    await refreshResults();
  }

  async function runFocusedSearch() {
    if (!focusedWorld.trim() || !focusedFeature.trim()) return;
    const res = await fetch(`${apiBase}/api/focused-search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ world_name: focusedWorld.trim(), feature: focusedFeature.trim() }),
    });
    if (!res.ok) return;
    const data = await res.json();
    setRunId(data.run_id);
  }

  const grouped = groupWorldsByTier(worlds);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Layers />
          <div>
            <div className="brand-title">OMNIVERSE 2</div>
            <div className="brand-sub">LangGraph command center</div>
          </div>
        </div>
        <nav className="nav">
          {navItems.map(({ id, label, Icon }) => (
            <button key={id} className={tab === id ? "nav-item active" : "nav-item"} onClick={() => setTab(id)}>
              <Icon size={16} /> {label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main">
        {tab === "dashboard" && (
          <section className="panel-grid">
            <div className="panel">
              <h1>Orchestration</h1>
              <p>Add worlds, run research loop, stream agent execution.</p>
              <textarea
                value={worldsInput}
                onChange={e => setWorldsInput(e.target.value)}
                placeholder="Warhammer 40k, Star Wars, Harry Potter"
              />
              <button className="primary" onClick={startRun} disabled={running}>
                {running ? <Loader2 className="spin" size={16} /> : <Play size={16} />} Run
              </button>
              <button className="primary" onClick={researchUnexplored} disabled={running}>
                Research All Unexplored
              </button>
            </div>
            <div className="panel terminal">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h2>Live Logs</h2>
                <button className="chip" onClick={clearLogs}>Clear Logs</button>
              </div>
              {logs.length === 0 ? <p className="muted">No logs yet.</p> : logs.map((log, index) => <LogLine key={index} log={log} />)}
            </div>
          </section>
        )}

        {tab === "dashboard" && (
          <section className="panel-grid" style={{ marginTop: 20 }}>
            <div className="panel">
              <h2>World Registry</h2>
              <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                <input value={newWorldName} onChange={e => setNewWorldName(e.target.value)} placeholder="Add world to DB" />
                <button className="primary" onClick={addWorld} disabled={saving}>Add + Research</button>
              </div>
              <button className="chip" onClick={clearAllExplored}>Clear All Explored Flags</button>
              <div className="chips">
                {worldRegistry.slice(0, 24).map(world => <button key={world.id} className={world.is_explored ? "chip active" : "chip"} onClick={() => void clearWorldExplored(world.id)}>{world.name} {world.is_explored ? "✓" : ""}</button>)}
              </div>
            </div>
            <div className="panel">
              <h2>Focused Search</h2>
              <input value={focusedWorld} onChange={e => setFocusedWorld(e.target.value)} placeholder="World name" />
              <input value={focusedFeature} onChange={e => setFocusedFeature(e.target.value)} placeholder="Feature to prove/disprove" />
              <button className="primary" onClick={runFocusedSearch} disabled={running}>Focused Search</button>
              <h2>Database Controls</h2>
              <p className="muted">Reset data, keep settings and seeded worlds.</p>
              <button className="primary" onClick={resetDatabase}>Reset DB</button>
            </div>
          </section>
        )}

        {tab === "database" && (
          <section className="panel-grid tiers">
            <div className="panel list">
              <h1>Tier System</h1>
              <p>{tierSystem ?? "No tier system yet."}</p>
              {grouped.map(({ tier, worlds: tierWorlds }) => (
                <div key={tier} className="tier-row">
                  <div className="tier-label">Tier {tier}</div>
                  <div className="chips">
                    {tierWorlds.length ? tierWorlds.map(world => <button key={world.id} className={selectedWorldId === world.id ? "chip active" : "chip"} onClick={() => setSelectedWorldId(world.id)}>{world.name}</button>) : <span className="muted">Empty</span>}
                  </div>
                </div>
              ))}
            </div>
            <div className="panel detail">
              {selectedWorld ? <WorldDetail world={selectedWorld} /> : <p className="muted">Select world.</p>}
              {anomalies.length > 0 && <div className="anomaly-list">{anomalies.map((a, i) => <div key={i} className="anomaly">{a.description}</div>)}</div>}
            </div>
          </section>
        )}

        {tab === "theories" && (
          <section className="panel-grid single">
            <div className="panel">
              <h1>Ontological Theories</h1>
              <p className="muted" style={{ marginBottom: 20 }}>Speculative interactions grounded in canonical data.</p>
              {worlds.filter(world => world.theory).map(world => (
                <div key={world.id} className="theory-card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <h3>{world.name}</h3>
                    <div className="badge">Tier {world.tier ?? "null"}</div>
                  </div>
                  <div className="theory-body">
                    <pre>{world.theory}</pre>
                  </div>
                  {world.theory_audit && (
                    <div className="theory-audit">
                      <div className="audit-label">Auditor Verdict</div>
                      <div className="audit-text">{world.theory_audit}</div>
                    </div>
                  )}
                </div>
              ))}
              {worlds.filter(world => world.theory).length === 0 && <p className="muted">No theories generated yet. Run the full pipeline to extrapolate interactions.</p>}
            </div>
          </section>
        )}

         {tab === "settings" && (
           <section className="panel-grid settings-grid">
             <div className="panel">
               <h1>Provider Setup</h1>
               <p className="muted">Define LLM providers and their fallback API keys.</p>
               {providers.map(provider => (
                 <ProviderRow 
                   key={provider.id} 
                   provider={provider} 
                   onSave={saveProvider} 
                   onSaveKey={saveProviderKey}
                   onDeleteKey={deleteProviderKey}
                   saving={saving} 
                 />
               ))}
               <div className="provider-add-box">
                 <button className="primary" onClick={async () => {
                   await saveProvider({ id: 0, name: "New Provider", provider_type: null, base_url: null, models: null, keys: [] });
                   await refreshProviders();
                 }} disabled={saving}>Add New Provider</button>
               </div>
             </div>
             <div className="panel">
               <h1>Agent Routing</h1>
               <p className="muted">Define the provider $\rightarrow$ model fallback chain for each agent.</p>
               <div className="routes-list">
                 {agentRoutes.map((route, idx) => (
                   <RouteRow 
                     key={route.id} 
                     route={route} 
                     providers={providers} 
                     onSave={saveAgentRoute} 
                     onDelete={deleteAgentRoute}
                     saving={saving} 
                   />
                 ))}
                 <button className="chip" onClick={async () => {
                   await saveAgentRoute({ id: 0, task_type: "RESEARCH", provider_id: null, model_name: null, priority: agentRoutes.length });
                   await refreshAgentRoutes();
                 }} disabled={saving}>+ Add Fallback Step</button>
               </div>
             </div>
             <div className="panel">
               <h1>General Settings</h1>
               {Object.entries(settings).map(([key, value]) => (
                 <label key={key} className="field">
                   <span>{key}</span>
                   <input defaultValue={value ?? ""} onBlur={e => void saveGeneralSetting(key, e.target.value)} />
                 </label>
               ))}
             </div>
           </section>
         )}

      </main>
    </div>
  );
}

function LogLine({ log }: { log: LogEntry }) {
  return <div className="log-line"><span className="time">{log.created_at}</span> <b>{log.node_name}</b> [{log.status}] {log.thought}</div>;
}

function WorldDetail({ world }: { world: World }) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2>{world.name}</h2>
        <div className="badge" style={{ fontSize: "1.2rem", padding: "4px 12px" }}>Tier {world.tier ?? "null"}</div>
      </div>
      <div className="detail-box">
        <div className="detail-label">Tier Justification</div>
        <pre className="detail-content">{world.tier_justification ?? "No justification provided."}</pre>
      </div>
      {world.theory && (
        <div className="detail-box" style={{ marginTop: 16 }}>
          <div className="detail-label">Ontological Theory</div>
          <pre className="detail-content">{world.theory}</pre>
          {world.theory_audit && (
            <div className="audit-box">
              <div className="audit-label">Auditor Feedback</div>
              <div className="audit-content">{world.theory_audit}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ProviderRow({ provider, onSave, onSaveKey, onDeleteKey, saving }: { 
  provider: ProviderRecord; 
  onSave: (provider: any) => Promise<void>; 
  onSaveKey: (key: any) => Promise<void>;
  onDeleteKey: (id: number) => Promise<void>;
  saving: boolean 
}) {
  const [state, setState] = useState(provider);
  useEffect(() => setState(provider), [provider]);

  return (
    <div className="provider-card">
      <div className="provider-header">
        <div className="provider-main">
          <input 
            className="provider-name"
            value={state.name} 
            onChange={e => setState({ ...state, name: e.target.value })} 
            placeholder="Provider name" 
          />
          <select 
            value={state.provider_type ?? ""} 
            onChange={e => setState({ ...state, provider_type: e.target.value || null })}
          >
            <option value="">Select Type</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="gemini">Gemini</option>
            <option value="ollama">Ollama</option>
            <option value="groq">Groq</option>
            <option value="openrouter">OpenRouter</option>
          </select>
        </div>
        <button className="chip" onClick={() => void onSave(state)} disabled={saving || !state.name.trim()}>Save Provider</button>
      </div>

      <div className="provider-body">
        <div className="provider-config">
          <label className="field">
            <span>Base URL</span>
            <input value={state.base_url ?? ""} onChange={e => setState({ ...state, base_url: e.target.value || null })} placeholder="https://..." />
          </label>
          <label className="field">
            <span>Models (CSV)</span>
            <input value={state.models ?? ""} onChange={e => setState({ ...state, models: e.target.value || null })} placeholder="gpt-4o, gpt-3.5-turbo" />
          </label>
        </div>

        <div className="provider-keys">
          <h3>API Keys</h3>
          <div className="keys-list">
            {provider.keys.map((key, idx) => (
              <div key={key.id} className="key-row">
                <input 
                  value={key.api_key} 
                  onChange={async e => await onSaveKey({ ...key, api_key: e.target.value })} 
                  placeholder="API Key" 
                />
                <input 
                  type="number" 
                  value={key.priority} 
                  onChange={async e => await onSaveKey({ ...key, priority: parseInt(e.target.value) || 0 })} 
                  style={{ width: 60 }} 
                  placeholder="Pri" 
                />
                <button className="chip delete" onClick={() => void onDeleteKey(key.id)}>×</button>
              </div>
            ))}
            <button className="chip" onClick={async () => await onSaveKey({ provider_id: provider.id, api_key: "", priority: provider.keys.length })}>
              + Add Key
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function RouteRow({ route, providers, onSave, onDelete, saving }: { 
  route: AgentRouteRecord; 
  providers: ProviderRecord[]; 
  onSave: (route: any) => Promise<void>; 
  onDelete: (id: number) => Promise<void>;
  saving: boolean 
}) {
  const [state, setState] = useState(route);
  useEffect(() => setState(route), [route]);

  return (
    <div className="route-row">
      <div className="route-info">
        <span className="task-badge">{state.task_type}</span>
        <span className="priority-badge">Pri: {state.priority}</span>
      </div>
      <select 
        value={state.provider_id ?? ""} 
        onChange={e => setState({ ...state, provider_id: e.target.value ? Number(e.target.value) : null })}
      >
        <option value="">Select Provider</option>
        {providers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <input 
        value={state.model_name ?? ""} 
        onChange={e => setState({ ...state, model_name: e.target.value || null })} 
        placeholder="Model name" 
      />
      <div className="route-actions">
        <button className="chip" onClick={() => void onSave(state)} disabled={saving}>Save</button>
        <button className="chip delete" onClick={() => void onDelete(state.id)}>×</button>
      </div>
    </div>
  );
}
