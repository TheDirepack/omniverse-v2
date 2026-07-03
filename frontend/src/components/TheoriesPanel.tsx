import { useState, useEffect } from "react";
import type { World } from "../types";
import * as api from "../api";

function TheoriesPanel() {
  const [worlds, setWorlds] = useState<World[]>([]);

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

  const worldsWithTheories = worlds.filter(w => w.theory);

  return (
    <section className="panel-grid single">
      <div className="panel">
        <h1>Ontological Theories</h1>
        <p className="help-text">Generated after tiering completes — extrapolated interactions grounded in verified research, each with an auditor verdict.</p>
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
          <p className="muted">No theories generated yet. Run the full pipeline to extrapolate interactions.</p>
        )}
      </div>
    </section>
  );
}

export default TheoriesPanel;
