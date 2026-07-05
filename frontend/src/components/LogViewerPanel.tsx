import { useState, useEffect } from "react";
import * as api from "../api";

export default function LogViewerPanel() {
  const [logs, setLogs] = useState<string[]>([]);
  const [options, setOptions] = useState({
    agents: [] as string[],
    models: [] as string[],
    worlds: [] as string[]
  });
  const [filters, setFilters] = useState({
    q: "",
    agent: "",
    world: "",
    model: "",
    event_type: "",
    tool: ""
  });
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  const refreshLogs = async (reset = true) => {
    setLoading(true);
    const currentOffset = reset ? 0 : offset;
    try {
      const data = await api.fetchFileLogs({
        limit: 100,
        offset: currentOffset,
        filter: filters.q,
        agent: filters.agent,
        world: filters.world,
        model: filters.model,
        event_type: filters.event_type,
        tool: filters.tool
      });
      
      setLogs(reset ? data.logs : [...logs, ...data.logs]);
      setHasMore(data.has_more);
      setOffset(currentOffset + 100);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const loadOptions = async () => {
      try {
        const [agentNames, worlds, settings] = await Promise.all([
          api.fetchAgentNames(),
          api.fetchWorlds(),
          api.fetchSettings()
        ]);
        
        const models = new Set<string>();
        
        // 1. Get models from Providers
        settings.providers.forEach(p => {
          if (p.models) {
            p.models.split(",").forEach(m => models.add(m.trim()));
          }
        });

        // 2. Get models from Agent Routes (in case some are specified there but not in provider)
        settings.agent_routes.forEach(route => {
          if (route.models) {
            route.models.split(",").forEach(m => models.add(m.trim()));
          }
        });

        setOptions({
          agents: agentNames,
          models: Array.from(models).filter(m => m).sort(),
          worlds: worlds.map(w => w.name)
        });
      } catch (e) {
        console.error("Error loading log options:", e);
      }
    };

    loadOptions();
    refreshLogs();
  }, []);

  const updateFilter = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setOffset(0); // Reset pagination on filter change
  };

  return (
    <section className="panel-grid single">
      <div className="panel" style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 80px)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <h1>System Agent Logs</h1>
          <div style={{ display: "flex", gap: 12 }}>
            <input 
              value={filters.q} 
              onChange={e => updateFilter("q", e.target.value)} 
              placeholder="Generic search..." 
              style={{ padding: 4 }}
            />
            <button className="primary" onClick={() => refreshLogs(true)} disabled={loading}>
              {loading ? "..." : "Refresh"}
            </button>
          </div>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 24 }}>
          <div className="filter-group" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label className="muted" style={{ fontSize: "0.7rem", textTransform: "uppercase" }}>Agent</label>
            <select 
              value={filters.agent} 
              onChange={e => updateFilter("agent", e.target.value)} 
              style={{ padding: 4 }}
            >
              <option value="">All Agents</option>
              {options.agents.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div className="filter-group" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label className="muted" style={{ fontSize: "0.7rem", textTransform: "uppercase" }}>World</label>
            <select 
              value={filters.world} 
              onChange={e => updateFilter("world", e.target.value)} 
              style={{ padding: 4 }}
            >
              <option value="">All Worlds</option>
              {options.worlds.map(w => <option key={w} value={w}>{w}</option>)}
            </select>
          </div>
          <div className="filter-group" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label className="muted" style={{ fontSize: "0.7rem", textTransform: "uppercase" }}>Model</label>
            <select 
              value={filters.model} 
              onChange={e => updateFilter("model", e.target.value)} 
              style={{ padding: 4 }}
            >
              <option value="">All Models</option>
              {options.models.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div className="filter-group" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label className="muted" style={{ fontSize: "0.7rem", textTransform: "uppercase" }}>Event</label>
            <select 
              value={filters.event_type} 
              onChange={e => updateFilter("event_type", e.target.value)}
              style={{ padding: 4 }}
            >
              <option value="">All Events</option>
              <option value="THOUGHT">Thought</option>
              <option value="TOOL_REQ">Tool Request</option>
              <option value="TOOL_RES">Tool Response</option>
            </select>
          </div>
          <div className="filter-group" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label className="muted" style={{ fontSize: "0.7rem", textTransform: "uppercase" }}>Tool</label>
            <input 
              value={filters.tool} 
              onChange={e => updateFilter("tool", e.target.value)} 
              placeholder="webSearch..." 
              style={{ padding: 4 }}
            />
          </div>
        </div>

        <div className="log-container" style={{ 
          fontFamily: "monospace", 
          fontSize: "0.85rem", 
          background: "#0f172a", 
          padding: 12, 
          borderRadius: 8, 
          border: "1px solid #334155",
          flex: 1,
          overflowY: "auto",
          whiteSpace: "pre-wrap"
        }}>
          {logs.length === 0 ? (
            <p className="muted">No logs found.</p>
          ) : (
            logs.map((line, i) => (
              <div key={i} style={{ borderBottom: "1px solid #1e293b", padding: "2px 0", color: "#cbd5e1" }}>
                {line}
              </div>
            ))
          )}
        </div>
        {hasMore && (
          <div style={{ textAlign: "center", marginTop: 12 }}>
            <button className="secondary" onClick={() => refreshLogs(false)} disabled={loading}>
              {loading ? "..." : "Load More"}
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
