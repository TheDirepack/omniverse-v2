import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { Loader2, Play } from "lucide-react";
import type { WorldRecord, LogEntry } from "../types";
import * as api from "../api";

function LogLine({ log }: { log: LogEntry }) {
  return (
    <div className="log-line">
      <span className="time">{log.created_at}</span>
      <b>{log.node_name}</b> [{log.status}] {log.thought}
    </div>
  );
}

function DashboardPanel() {
  const [worldRegistry, setWorldRegistry] = useState<WorldRecord[]>([]);
  const [worldsInput, setWorldsInput] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [running, setRunning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [newWorldName, setNewWorldName] = useState("");
  const [focusedWorld, setFocusedWorld] = useState("");
  const [focusedFeature, setFocusedFeature] = useState("");
  const [worldSearch, setWorldSearch] = useState("");
  const [showAllWorlds, setShowAllWorlds] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [logs, scrollToBottom]);

  const refreshWorlds = useCallback(async () => {
    try { setWorldRegistry(await api.fetchWorlds()); } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { void refreshWorlds(); }, [refreshWorlds]);

  useEffect(() => {
    if (!runId) return;
    setLogs([]);
    setRunning(true);
    const source = api.createEventSource(runId);
    source.onmessage = event => {
      const data = JSON.parse(event.data) as LogEntry & { finished?: boolean };
      if (data.finished) {
        source.close();
        setRunning(false);
        return;
      }
      setLogs(prev => [...prev, data]);
    };
    source.onerror = () => { source.close(); setRunning(false); };
    return () => source.close();
  }, [runId]);

  const unexploredCount = useMemo(() => worldRegistry.filter(w => !w.is_explored).length, [worldRegistry]);
  const filteredWorlds = useMemo(() => {
    if (!worldSearch) return worldRegistry;
    return worldRegistry.filter(w => w.name.toLowerCase().includes(worldSearch.toLowerCase()));
  }, [worldRegistry, worldSearch]);
  const displayWorlds = showAllWorlds ? filteredWorlds : filteredWorlds.slice(0, 24);
  const hasMore = filteredWorlds.length > 24 && !showAllWorlds;

  const handleStartRun = async () => {
    const payload = worldsInput.split(",").map(v => v.trim()).filter(Boolean);
    if (!payload.length) return;
    try { setRunId((await api.startOrchestrate(payload)).run_id); } catch (e) { console.error(e); }
  };

  const handleResearchUnexplored = async () => {
    try {
      const data = await api.researchUnexplored();
      if (data.run_id) setRunId(data.run_id);
    } catch (e) { console.error(e); }
  };

  const handleAddWorld = async () => {
    if (!newWorldName.trim()) return;
    setSaving(true);
    try { await api.addWorld(newWorldName.trim()); setNewWorldName(""); await refreshWorlds(); }
    finally { setSaving(false); }
  };

  const handleResetAllExplored = async () => {
    try { await api.resetAllExplored(); await refreshWorlds(); } catch (e) { console.error(e); }
  };

  const handleResetWorldExplored = async (worldId: number) => {
    await api.resetWorldExplored(worldId); await refreshWorlds();
  };
 
  const handleSelectWorldForFocusedSearch = (name: string) => {
    setFocusedWorld(name);
  };
 
  const handleDeleteWorld = async (worldId: number) => {
    if (!confirm("Are you sure you want to delete this world? All associated data will be lost.")) return;
    try { await api.deleteWorld(worldId); await refreshWorlds(); } catch (e) { console.error(e); }
  };
 
  const handleFocusedSearch = async () => {

    if (!focusedWorld.trim() || !focusedFeature.trim()) return;
    try { setRunId((await api.runFocusedSearch(focusedWorld.trim(), focusedFeature.trim())).run_id); } catch (e) { console.error(e); }
  };

  const handleStopRun = async () => {
    if (!runId) return;
    try {
      await api.abortRun(runId);
      // The EventSource will eventually receive a 'finished' message with aborted: true
      // but we can set running to false immediately for better UI responsiveness
      setRunning(false);
    } catch (e) {
      console.error("Failed to stop run:", e);
    }
  };

  const handleClearLogs = async () => {
    await api.clearLogsApi(); setLogs([]);
  };

  return (
    <>
      <section className="panel-grid">
        <div className="panel">
          <h1>Orchestration</h1>
          <p>Add worlds, run research loop, stream agent execution.</p>
          <textarea
            value={worldsInput}
            onChange={e => setWorldsInput(e.target.value)}
            placeholder="Warhammer 40k, Star Wars, Harry Potter"
          />
          <p className="help-text">Comma-separated world names. Each one runs the full research → tier pipeline.</p>
           <div className="button-row">
             {running ? (
               <button className="chip delete" onClick={handleStopRun}>Stop Research</button>
             ) : (
               <>
                 <button className="primary" onClick={handleStartRun}>
                   <Play size={16} /> Run
                 </button>
                 <button className="primary" onClick={handleResearchUnexplored}>
                   Research All Unexplored ({unexploredCount} worlds)
                 </button>
               </>
             )}
           </div>

        </div>
          <div className="panel terminal">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <h2>Live Logs</h2>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span className={`status-pill ${running ? "running" : logs.length > 0 ? "idle" : "idle"}`}>
                  {running ? "Running" : logs.some(l => l.status === "FAILED") ? "Failed" : logs.length > 0 ? "Completed" : "Idle"}
                </span>
                <button className="chip" onClick={handleClearLogs}>Clear Logs</button>
              </div>
            </div>
            <div className="log-container">
              {logs.length === 0 ? <p className="muted">No logs yet.</p> : logs.map((log, index) => <LogLine key={index} log={log} />)}
              <div ref={logEndRef} />
            </div>
          </div>

      </section>

      <section className="panel-grid" style={{ marginTop: 20 }}>
        <div className="panel">
          <h2>World Registry</h2>
          <p className="help-text">Manage which worlds exist in the database. Click a world chip to toggle its explored flag.</p>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <input value={newWorldName} onChange={e => setNewWorldName(e.target.value)} placeholder="Add world to DB" />
            <button className="primary" onClick={handleAddWorld} disabled={saving}>Add + Research</button>
          </div>
          <input
            value={worldSearch}
            onChange={e => setWorldSearch(e.target.value)}
            placeholder="Search worlds..."
          />
          <button className="chip" onClick={handleResetAllExplored}>Reset All Explored Flags</button>
           <div className="chips">
             {displayWorlds.map(world => (
               <div key={world.id} style={{ display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                 <button className={world.is_explored ? "chip active" : "chip"} onClick={() => void handleResetWorldExplored(world.id)}>
                   {world.name} {world.is_explored ? "✓" : ""}
                 </button>
                 <button className="chip" style={{ padding: '0 4px', fontSize: '10px' }} title="Focused Search" onClick={() => handleSelectWorldForFocusedSearch(world.name)}>🔍</button>
                 <button className="chip delete" style={{ padding: '0 4px', fontSize: '10px' }} onClick={() => void handleDeleteWorld(world.id)}>×</button>
               </div>
             ))}
             {hasMore && <button className="chip" onClick={() => setShowAllWorlds(true)}>+{filteredWorlds.length - 24} more</button>}
           </div>

        </div>
        <div className="panel">
          <h2>Focused Search</h2>
          <p className="help-text">Prove or disprove a specific feature about a world.</p>
          <input value={focusedWorld} onChange={e => setFocusedWorld(e.target.value)} placeholder="World name" />
          <input value={focusedFeature} onChange={e => setFocusedFeature(e.target.value)} placeholder="Feature to prove/disprove" />
          <button className="primary" onClick={handleFocusedSearch} disabled={running}>Focused Search</button>
           <h2>Database Controls</h2>
           <p className="muted">Reset research data and flags, keep settings and worlds.</p>
           <button className="primary" onClick={handleResetDB}>Reset DB</button>

        </div>
      </section>
    </>
  );
}

export default DashboardPanel;
