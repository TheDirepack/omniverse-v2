import { useState, useEffect, useMemo } from "react";
import type { World, Trait } from "../types";
import * as api from "../api";

function TraitRow({ world, traits }: { world: World; traits: Trait[] }) {
  return (
    <div style={{ 
      display: "flex", 
      gap: 16, 
      padding: "12px", 
      background: "#1e293b", 
      borderRadius: 8, 
      border: "1px solid #334155", 
      marginBottom: 12,
      alignItems: "center"
    }}>
      <div style={{ minWidth: 150, fontWeight: 600, color: "#f1f5f9" }}>{world.name}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {traits.map(t => (
          <div key={t.id} style={{ 
            padding: "2px 8px", 
            background: "#0f172a", 
            borderRadius: 4, 
            border: "1px solid #475569", 
            fontSize: "0.8rem",
            display: "flex",
            gap: 6
          }}>
            <span style={{ color: "#94a3b8" }}>{t.name}:</span>
            <span style={{ color: "#cbd5e1" }}>{t.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TraitViewerPanel() {
  const [worlds, setWorlds] = useState<World[]>([]);
  const [traits, setTraits] = useState<Trait[]>([]);
  const [filterOnlyWithTraits, setFilterOnlyWithTraits] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [results, allTraits] = await Promise.all([
          api.fetchResults(),
          api.fetchTraits()
        ]);
        setWorlds(results.worlds);
        setTraits(allTraits);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const worldsWithTraits = useMemo(() => {
    return worlds.map(w => ({
      world: w,
      worldTraits: traits.filter(t => t.universe_id === w.id)
    })).filter(item => {
      if (!filterOnlyWithTraits) return true;
      return item.worldTraits.length > 0;
    });
  }, [worlds, traits, filterOnlyWithTraits]);

  if (loading) return <div className="muted" style={{ padding: 24 }}>Loading traits...</div>;

  return (
    <section className="panel-grid single">
      <div className="panel">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <h1>Main Database Traits</h1>
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: "0.9rem", color: "#94a3b8" }}>
            <input 
              type="checkbox" 
              checked={filterOnlyWithTraits} 
              onChange={e => setFilterOnlyWithTraits(e.target.checked)} 
            />
            Only worlds with traits
          </label>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          {worldsWithTraits.length > 0 ? (
            worldsWithTraits.map(({ world, worldTraits }) => (
              <TraitRow key={world.id} world={world} traits={worldTraits} />
            ))
          ) : (
            <p className="muted">No worlds found matching the current filter.</p>
          )}
        </div>
      </div>
    </section>
  );
}
