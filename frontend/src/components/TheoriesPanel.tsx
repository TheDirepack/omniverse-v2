import { useState, useEffect } from "react";
import type { World } from "../types";
import * as api from "../api";

function TheoriesPanel() {
  const [worlds, setWorlds] = useState<World[]>([]);
  const [scope, setScope] = useState<"all" | "worlds" | "tier">("all");
  const [worldsInput, setWorldsInput] = useState("");
  const [tierInput, setTierInput] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void refresh();
  }, []);

  const refresh = async () => {
    try {
      const data = await api.fetchResults();
      setWorlds(data.worlds);
    } catch (e) {
      console.error(e);
    }
  };

  const handleExtrapolate = async () => {
    setLoading(true);
    try {
      const payload: { scope: "all" | "worlds" | "tier"; worlds?: string[]; tier?: number } = { scope };
      if (scope === "worlds") {
        payload.worlds = worldsInput.split(",").map(s => s.trim()).filter(Boolean);
      } else if (scope === "tier") {
        payload.tier = parseInt(tierInput, 10);
      }
      await api.extrapolate(payload);
      alert("Extrapolation started. Check logs for progress.");
    } catch (e) {
      alert("Error starting extrapolation: " + (e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const worldsWithTheories = worlds.filter(w => w.theory);

  return (
    <section className="panel-grid single">
      <div className="panel">
        <h1>Ontological Theories</h1>
        <p className="help-text">Speculative interaction projections grounded in verified research.</p>
        
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end", marginBottom: 24, padding: 16, background: "var(--bg-alt)", borderRadius: 8, border: "1px solid var(--border)" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: "0.8rem", opacity: 0.8 }}>Scope</label>
            <select value={scope} onChange={e => setScope(e.target.value as any)} style={{ padding: 4 }}>
              <option value="all">All Verified Worlds</option>
              <option value="worlds">Specific Worlds</option>
              <option value="tier">Specific Tier</option>
            </select>
          </div>

          {scope === "worlds" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label style={{ fontSize: "0.8rem", opacity: 0.8 }}>Worlds (comma separated)</label>
              <input value={worldsInput} onChange={e => setWorldsInput(e.target.value)} placeholder="Marvel, DC..." style={{ padding: 4 }} />
            </div>
          )}

          {scope === "tier" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label style={{ fontSize: "0.8rem", opacity: 0.8 }}>Tier Number</label>
              <input type="number" value={tierInput} onChange={e => setTierInput(e.target.value)} placeholder="5" style={{ padding: 4 }} />
            </div>
          )}

          <button onClick={handleExtrapolate} disabled={loading} style={{ padding: "4px 12px", cursor: loading ? "not-allowed" : "pointer" }}>
            {loading ? "Starting..." : "Trigger Extrapolation"}
          </button>
          <button onClick={refresh} style={{ padding: "4px 12px", opacity: 0.7 }}>Refresh</button>
        </div>

        {worldsWithTheories.map(world => (
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
        {worldsWithTheories.length === 0 && (
          <p className="muted">No theories generated yet. Use the trigger above to extrapolate interactions.</p>
        )}
      </div>
    </section>
  );
}

export default TheoriesPanel;
