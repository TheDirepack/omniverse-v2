import { useState, useEffect, useMemo } from "react";
import type { World, Anomaly } from "../types";
import * as api from "../api";
import { groupWorldsByTier } from "../lib/tiers";

function WorldDetail({ world, anomalies }: { world: World; anomalies: Anomaly[] }) {
  const worldAnomalies = anomalies.filter(a => a.world_id === world.id);
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
      {worldAnomalies.length > 0 && (
        <div className="detail-box" style={{ marginTop: 16, border: "1px solid #f59e0b" }}>
          <div className="detail-label">Anomalies</div>
          {worldAnomalies.map((a, i) => <pre key={i} className="detail-content">{a.description}</pre>)}
        </div>
      )}
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

function DatabasePanel() {
  const [worlds, setWorlds] = useState<World[]>([]);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [tierSystem, setTierSystem] = useState<string | null>(null);
  const [selectedWorldId, setSelectedWorldId] = useState<number | null>(null);

  useEffect(() => { void refresh(); }, []);

  const refresh = async () => {
    try {
      const data = await api.fetchResults();
      setTierSystem(data.tier_system);
      setWorlds(data.worlds);
      setAnomalies(data.anomalies);
    } catch (e) { console.error(e); }
  };

  const selectedWorld = useMemo(() => worlds.find(w => w.id === selectedWorldId) ?? null, [worlds, selectedWorldId]);
  const grouped = groupWorldsByTier(worlds);

  return (
    <section className="panel-grid tiers">
      <div className="panel list">
        <h1>Tier System</h1>
        <p className="help-text">Worlds grouped by assigned tier. Click a world to see details.</p>
        {tierSystem && (
          <div className="tier-system-block">
            <h3>System Definition</h3>
            <pre className="tier-system-text">{tierSystem}</pre>
          </div>
        )}
        {!tierSystem && <p className="muted">No tier system yet. Run the pipeline to generate one.</p>}
        {grouped.map(({ tier, worlds: tierWorlds }) => (
          <div key={tier} className="tier-row">
            <div className="tier-label">Tier {tier}</div>
            <div className="chips">
              {tierWorlds.length
                ? tierWorlds.map(world => (
                    <button key={world.id} className={selectedWorldId === world.id ? "chip active" : "chip"} onClick={() => setSelectedWorldId(world.id)}>
                      {world.name}
                    </button>
                  ))
                : <span className="muted">Empty</span>}
            </div>
          </div>
        ))}
      </div>
      <div className="panel detail">
        {selectedWorld ? <WorldDetail world={selectedWorld} anomalies={anomalies} /> : <p className="muted">Select a world to view details.</p>}
        {anomalies.filter(a => a.world_id === null).length > 0 && (
          <div className="anomaly-list" style={{ marginTop: 16 }}>
            <h4>Global Anomalies</h4>
            {anomalies.filter(a => a.world_id === null).map((a, i) => <div key={i} className="anomaly">{a.description}</div>)}
          </div>
        )}
      </div>
    </section>
  );
}

export default DatabasePanel;
