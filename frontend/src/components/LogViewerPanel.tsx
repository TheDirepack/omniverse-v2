import { useState, useEffect } from "react";
import * as api from "../api";

export default function LogViewerPanel() {
  const [logs, setLogs] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);

  const refreshLogs = async () => {
    setLoading(true);
    try {
      const data = await api.fetchFileLogs(filter);
      setLogs(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshLogs();
  }, []);

  return (
    <section className="panel-grid single">
      <div className="panel">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <h1>System Agent Logs</h1>
          <div style={{ display: "flex", gap: 12 }}>
            <input 
              value={filter} 
              onChange={e => setFilter(e.target.value)} 
              placeholder="Filter logs..." 
              style={{ padding: 4 }}
            />
            <button className="primary" onClick={refreshLogs} disabled={loading}>
              {loading ? "..." : "Refresh"}
            </button>
          </div>
        </div>

        <div className="log-container" style={{ 
          fontFamily: "monospace", 
          fontSize: "0.85rem", 
          background: "#0f172a", 
          padding: 12, 
          borderRadius: 8, 
          border: "1px solid #334155",
          maxHeight: "80vh",
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
      </div>
    </section>
  );
}
