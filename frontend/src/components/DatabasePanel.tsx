import { useState, useEffect, useMemo } from "react";
import type { World, Anomaly, Trait, Claim, UnconfirmedClaim } from "../types";
import * as api from "../api";
import { groupWorldsByTier } from "../lib/tiers";

function ClaimSection({ title, claims, isUnconfirmed = false }: { title: string; claims: Claim[] | UnconfirmedClaim[]; isUnconfirmed?: boolean }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <h4 style={{ color: "#94a3b8", fontSize: "0.9rem", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>{title}</h4>
      <div style={{ display: "grid", gap: 8 }}>
        {claims.map((c, i) => (
          <div key={c.id || i} style={{ display: "flex", justifyContent: "space-between", padding: "8px", background: isUnconfirmed ? "#2d2a2e" : "#1e293b", borderRadius: 4, border: `1px solid ${isUnconfirmed ? "#4a3f4e" : "#334155"}` }}>
            <span style={{ color: "#cbd5e1", fontSize: "0.9rem" }}>
              {typeof c === 'object' && 'subject' in c ? c.subject : 'Unknown'} 
              <span style={{ color: "#64748b", margin: "0 8px" }}>$\rightarrow$ {c.predicate} $\rightarrow$</span> 
              {typeof c === 'object' && 'object_val' in c ? c.object_val : (c as any).object_literal || 'Unknown'}
            </span>
            <span style={{ fontSize: "0.7rem", color: "#94a3b8", marginLeft: 8 }}>
              {isUnconfirmed ? (c as any).confidence : (c as any).support_count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TraitSection({ category, traits, isUnconfirmed = false }: { category: string; traits: Trait[] | any[]; isUnconfirmed?: boolean }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <h4 style={{ color: "#94a3b8", fontSize: "0.9rem", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>{category}</h4>
      <div style={{ display: "grid", gap: 8 }}>
        {traits.map((t, i) => (
          <div key={t.id || i} style={{ display: "flex", justifyContent: "space-between", padding: "8px", background: isUnconfirmed ? "#2d2a2e" : "#1e293b", borderRadius: 4, border: `1px solid ${isUnconfirmed ? "#4a3f4e" : "#334155"}` }}>
            <span style={{ fontWeight: 600, color: "#f1f5f9" }}>{t.name}</span>
            <span style={{ color: isUnconfirmed ? "#c084fc" : "#cbd5e1" }}>{t.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ComparisonMatrix({ selectedWorlds, allTraits }: { selectedWorlds: World[]; allTraits: Trait[] }) {
  const worldIds = selectedWorlds.map(w => w.id);
  const relevantTraits = allTraits.filter(t => worldIds.includes(t.universe_id));
  
  // Get unique trait names across all selected worlds
  const uniqueTraitNames = Array.from(new Set(relevantTraits.map(t => t.name))).sort();
  
  return (
    <div style={{ overflowX: "auto", marginTop: 20 }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", padding: "12px", borderBottom: "2px solid #334155", color: "#94a3b8" }}>Trait</th>
            {selectedWorlds.map(w => (
              <th key={w.id} style={{ textAlign: "left", padding: "12px", borderBottom: "2px solid #334155", color: "#f1f5f9" }}>{w.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {uniqueTraitNames.map(traitName => {
            return (
              <tr key={traitName} style={{ borderBottom: "1px solid #334155" }}>
                <td style={{ padding: "12px", fontWeight: 600, color: "#cbd5e1" }}>{traitName}</td>
                {selectedWorlds.map(w => {
                  const trait = relevantTraits.find(t => t.universe_id === w.id && t.name === traitName);
                  return (
                    <td key={w.id} style={{ padding: "12px", color: trait ? "#f1f5f9" : "#64748b" }}>
                      {trait ? trait.value : "N/A"}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function WorldDetail({ world, anomalies, traits, unconfirmedTraits, claims, unconfirmedClaims }: { world: World; anomalies: Anomaly[]; traits: Trait[]; unconfirmedTraits: any[]; claims: Claim[]; unconfirmedClaims: UnconfirmedClaim[] }) {
  const worldAnomalies = anomalies.filter(a => a.world_id === world.id);
  const worldTraits = traits.filter(t => t.universe_id === world.id);
  const worldUnconfirmed = unconfirmedTraits.filter(t => t.universe_name === world.name);
  const worldClaims = claims.filter(c => c.universe_scope === world.id);
  const worldUnconfirmedClaims = unconfirmedClaims.filter(c => c.universe_name === world.name);
  
  const groupedTraits = worldTraits.reduce((acc, t) => {
    const cat = t.category || "Other";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(t);
    return acc;
  }, {} as Record<string, Trait[]>);

  const groupedUnconfirmed = worldUnconfirmed.reduce((acc, t) => {
    const cat = t.category || "Other";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(t);
    return acc;
  }, {} as Record<string, any[]>);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2>{world.name}</h2>
        <div className="badge" style={{ fontSize: "1.2rem", padding: "4px 12px" }}>
          Tier {world.tier !== null && world.tier !== -1 ? world.tier : "Untiered"}
        </div>
      </div>
      <div className="detail-box">
        <div className="detail-label">Tier Justification</div>
        <pre className="detail-content">{world.tier_justification ?? "No tiering data yet."}</pre>
      </div>
      
      <div style={{ marginTop: 24 }}>
        <h3>Verified Knowledge Graph</h3>
        <ClaimSection title="Verified Claims" claims={worldClaims} />
        <div style={{ marginTop: 16 }}>
          <h4>Structured Traits</h4>
          {Object.entries(groupedTraits).map(([cat, ts]) => (
            <TraitSection key={cat} category={cat} traits={ts} />
          ))}
          {worldTraits.length === 0 && <p className="muted">No structured traits found in main DB.</p>}
        </div>
      </div>

      <div style={{ marginTop: 24 }}>
        <h3>Unverified Research Notes</h3>
        <ClaimSection title="Staging Claims" claims={worldUnconfirmedClaims} isUnconfirmed />
        <div style={{ marginTop: 16 }}>
          <h4>Staging Traits</h4>
          {Object.entries(groupedUnconfirmed).map(([cat, ts]) => (
            <TraitSection key={cat} category={cat} traits={ts} isUnconfirmed />
          ))}
          {worldUnconfirmed.length === 0 && <p className="muted">No unconfirmed traits found in staging DB.</p>}
        </div>
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
  const [traits, setTraits] = useState<Trait[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [unconfirmedTraits, setUnconfirmedTraits] = useState<any[]>([]);
  const [unconfirmedClaims, setUnconfirmedClaims] = useState<UnconfirmedClaim[]>([]);
  const [tierSystem, setTierSystem] = useState<string | null>(null);
  const [selectedWorldId, setSelectedWorldId] = useState<number | null>(null);
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [isCompareMode, setIsCompareMode] = useState(false);
  const [worldFilter, setWorldFilter] = useState("");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  useEffect(() => { void refresh(); }, []);

  const refresh = async () => {
    try {
      const data = await api.fetchResults();
      setTierSystem(data.tier_system);
      setWorlds(data.worlds);
      setAnomalies(data.anomalies);
      
      const [allTraits, allClaims, allUnconfirmedTraits, allUnconfirmedClaims] = await Promise.all([
        api.fetchTraits(),
        api.fetchClaims(),
        api.fetchUnconfirmedTraits(),
        api.fetchUnconfirmedClaims()
      ]);
      setTraits(allTraits);
      setClaims(allClaims);
      setUnconfirmedTraits(allUnconfirmedTraits);
      setUnconfirmedClaims(allUnconfirmedClaims);
    } catch (e) { console.error(e); }
  };

  const handleRunTiering = async () => {
    try {
      await api.runTiering();
      alert("Tiering pass started.");
      await refresh();
    } catch (e) { console.error(e); }
  };

  const toggleCompare = (id: number) => {
    setCompareIds(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
  };

  const selectedWorld = useMemo(() => worlds.find(w => w.id === selectedWorldId) ?? null, [worlds, selectedWorldId]);
  const compareWorlds = useMemo(() => worlds.filter(w => compareIds.includes(w.id)), [worlds, compareIds]);
  
  const processedGrouped = useMemo(() => {
    const filtered = worlds.filter(w => w.name.toLowerCase().includes(worldFilter.toLowerCase()));
    const grouped = groupWorldsByTier(filtered);
    
    // Sort worlds within each tier alphabetically
    grouped.forEach(g => {
      g.worlds.sort((a, b) => a.name.localeCompare(b.name));
    });

    // Sort tiers based on sortOrder
    return sortOrder === "asc" 
      ? grouped.sort((a, b) => a.tier - b.tier) 
      : grouped.sort((a, b) => b.tier - a.tier);
  }, [worlds, worldFilter, sortOrder]);

  return (
    <section className="panel-grid tiers">
      <div className="panel list">
        <h1>Tier System</h1>
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <button className="primary" onClick={handleRunTiering}>Run Tiering Pass</button>
          <button className={isCompareMode ? "primary" : ""} onClick={() => {
            setIsCompareMode(!isCompareMode);
            setSelectedWorldId(null);
          }}>
            {isCompareMode ? "View Details" : "Compare Worlds"}
          </button>
          <button className="chip" onClick={() => setSortOrder(prev => prev === "asc" ? "desc" : "asc")}>
            Sort Tiers: {sortOrder === "asc" ? "↑" : "↓"}
          </button>
        </div>
        <input 
          className="world-filter-input"
          placeholder="Filter worlds..." 
          value={worldFilter} 
          onChange={e => setWorldFilter(e.target.value)} 
        />
        <p className="help-text">
          {isCompareMode 
            ? "Select multiple worlds to compare traits." 
            : "Worlds grouped by assigned tier. Click a world to see details."}
        </p>
        {tierSystem && (
          <div className="tier-system-block">
            <h3>System Definition</h3>
            <pre className="tier-system-text">{tierSystem}</pre>
          </div>
        )}
        {!tierSystem && <p className="muted">No tier system yet. Run the pipeline to generate one.</p>}
        {processedGrouped.map(({ tier, worlds: tierWorlds }) => (
          <div key={tier} className="tier-row">
            <div className="tier-label">Tier {tier}</div>
            <div className="chips">
              {tierWorlds.length
                ? tierWorlds.map(world => (
                    <button 
                      key={world.id} 
                      className={`${isCompareMode ? (compareIds.includes(world.id) ? "chip active" : "chip") : (selectedWorldId === world.id ? "chip active" : "chip")}`} 
                      onClick={() => isCompareMode ? toggleCompare(world.id) : setSelectedWorldId(world.id)}
                    >
                      {world.name}
                    </button>
                  ))
                : <span className="muted">Empty</span>}
            </div>
          </div>
        ))}
        {isCompareMode && (
          <div style={{ marginTop: 16 }}>
            <button className="secondary" onClick={() => setCompareIds([])}>Clear Selection</button>
            <span style={{ marginLeft: 8, color: "#94a3b8" }}>{compareIds.length} selected</span>
          </div>
        )}
      </div>
      <div className="panel detail">
        {isCompareMode ? (
          compareWorlds.length > 1 ? (
            <ComparisonMatrix selectedWorlds={compareWorlds} allTraits={traits} />
          ) : (
            <p className="muted">Select at least two worlds to compare.</p>
          )
         ) : (
           selectedWorld ? <WorldDetail world={selectedWorld} anomalies={anomalies} traits={traits} unconfirmedTraits={unconfirmedTraits} claims={claims} unconfirmedClaims={unconfirmedClaims} /> : <p className="muted">Select a world to view details.</p>
         )}
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
