import { useState, useEffect } from "react";
import type { SettingsTab, ProviderRecord, AgentRouteRecord } from "../../types";
import * as api from "../../api";
import ProviderCard from "./ProviderCard";
import RoutingCard from "./RoutingCard";
import SettingItem from "./SettingItem";
import SettingToggle from "./SettingToggle";
import SettingSlider from "./SettingSlider";


function SettingsPanel() {
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("providers");
  const [providers, setProviders] = useState<ProviderRecord[]>([]);
  const [agentRoutes, setAgentRoutes] = useState<AgentRouteRecord[]>([]);
  const [agentNames, setAgentNames] = useState<string[]>([]);
  const [settings, setSettings] = useState<Record<string, string | null>>({});
  const [newSettingKey, setNewSettingKey] = useState("");
  const [savingAddKey, setSavingAddKey] = useState(false);

  useEffect(() => {
    void refreshAll();
  }, []);

  const refreshAll = async () => {
    try {
      const [s, p, r, n] = await Promise.all([
        api.fetchSettings(),
        api.fetchProviders(),
        api.fetchAgentRoutes(),
        api.fetchAgentNames(),
      ]);
       setSettings({
         AGENT_LOGGING: "true",
         ...s.general_settings,
       });
      setProviders(p);
      setAgentRoutes(r);
      setAgentNames(n);
    } catch (e) {
      console.error("Failed to refresh settings:", e);
    }
  };

  const handleSaveProvider = async (provider: any) => {
    try {
      await api.saveProvider(provider);
      await refreshAll();
    } catch (e) {
      console.error("Failed to save provider:", e);
    }
  };

  const handleSaveKey = async (key: any): Promise<any> => {
    try {
      const result = await api.saveProviderKey(key);
      await refreshAll();
      return result;
    } catch (e) {
      console.error("Failed to save key:", e);
    }
  };

  const handleDeleteKey = async (keyId: number) => {
    try {
      await api.deleteProviderKey(keyId);
      await refreshAll();
    } catch (e) {
      console.error("Failed to delete key:", e);
    }
  };

  const handleDeleteProvider = async (providerId: number) => {
    try {
      await api.deleteProvider(providerId);
      await refreshAll();
    } catch (e) {
      console.error("Failed to delete provider:", e);
    }
  };

  const handleSaveRoute = async (route: any): Promise<any> => {
    try {
      const result = await api.saveAgentRoute(route);
      await refreshAll();
      return result;
    } catch (e) {
      console.error("Failed to save route:", e);
    }
  };

  const handleDeleteRoute = async (routeId: number) => {
    try {
      await api.deleteAgentRoute(routeId);
      await refreshAll();
    } catch (e) {
      console.error("Failed to delete route:", e);
    }
  };

  const handleSaveSetting = async (key: string, value: string) => {
    try {
      await api.saveGeneralSetting(key, value);
      setSettings(prev => ({ ...prev, [key]: value }));
    } catch (e) {
      console.error("Failed to save setting:", e);
    }
  };

  const handleDeleteSetting = async (key: string) => {
    try {
      await api.saveGeneralSetting(key, null);
      setSettings(prev => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    } catch (e) {
      console.error("Failed to delete setting:", e);
    }
  };

  const handleAddSetting = async () => {
    if (!newSettingKey.trim()) return;
    setSavingAddKey(true);
    try {
      await api.saveGeneralSetting(newSettingKey.trim(), null);
      setSettings(prev => ({ ...prev, [newSettingKey.trim()]: null }));
      setNewSettingKey("");
    } finally {
      setSavingAddKey(false);
    }
  };

  const handleAddProvider = async () => {
    try {
      await api.saveProvider({ id: 0, name: `New Provider ${Date.now()}`, provider_type: null, base_url: null, models: null });
      await refreshAll();
    } catch (e) {
      console.error("Failed to add provider:", e);
    }
  };

  const defaultRoutes = agentRoutes.filter(r => r.task_type === "DEFAULT").sort((a, b) => a.priority - b.priority);

  return (
    <section className="panel-grid settings-grid">
      <div className="settings-tabs">
        <button className={settingsTab === "providers" ? "tab active" : "tab"} onClick={() => setSettingsTab("providers")}>
          Providers & Keys
        </button>
        <button className={settingsTab === "routing" ? "tab active" : "tab"} onClick={() => setSettingsTab("routing")}>
          Agent Routing
        </button>
        <button className={settingsTab === "general" ? "tab active" : "tab"} onClick={() => setSettingsTab("general")}>
          General
        </button>
      </div>

      {settingsTab === "providers" && (
        <div className="settings-content">
          <h2>Providers & Keys</h2>
          <p className="muted">Define LLM providers and their fallback API keys.</p>
          <button className="primary" onClick={handleAddProvider}>+ Add Provider</button>
          <div className="provider-list">
            {providers.map(p => (
              <ProviderCard
                key={p.id}
                provider={p}
                onSave={handleSaveProvider}
                onSaveKey={handleSaveKey}
                onDeleteKey={handleDeleteKey}
                onDeleteProvider={handleDeleteProvider}
              />
            ))}
          </div>
        </div>
      )}

      {settingsTab === "routing" && (
        <div className="settings-content">
          <h2>Agent Routing</h2>
          <p className="muted">Each agent tries its fallback chain top to bottom: provider → its keys in order → its models in order. If everything fails, the run fails that step. Agents without their own chain use the DEFAULT chain below.</p>
          <div className="routing-list">
            <RoutingCard
              agentName="DEFAULT"
              routes={defaultRoutes}
              providers={providers}
              onSave={handleSaveRoute}
              onDelete={handleDeleteRoute}
            />
            <hr className="routing-divider" />
            {agentNames.map(name => {
              const agentRoutesForTask = agentRoutes
                .filter(r => r.task_type === name)
                .sort((a, b) => a.priority - b.priority);
              return (
                <RoutingCard
                  key={name}
                  agentName={name}
                  routes={agentRoutesForTask}
                  providers={providers}
                  onSave={handleSaveRoute}
                  onDelete={handleDeleteRoute}
                  defaultRoutes={defaultRoutes}
                />
              );
            })}
          </div>
        </div>
      )}

      {settingsTab === "general" && (
        <div className="settings-content">
          <h2>General Settings</h2>
          <p className="muted">Free-form key/value pairs used by custom agent prompts or integrations.</p>
          
          <div style={{ marginBottom: 24, padding: 16, background: "var(--bg-alt)", borderRadius: 8, border: "1px solid var(--border)" }}>
            <h4 style={{ marginBottom: 8 }}>Model Health & Performance</h4>
            <p className="muted" style={{ fontSize: "0.8rem", marginBottom: 12 }}>
              Models that fail repeatedly are temporarily disabled (circuit breaker).
            </p>
            <button 
              className="primary" 
              onClick={async () => {
                if (confirm("Reset all model timeouts and failure counts?")) {
                  try { await api.resetCandidateHealth(); alert("Model health reset successfully."); } 
                  catch (e) { console.error(e); }
                }
              }}
            >
              Reset Model Timeouts
            </button>
            
            <hr style={{ margin: "16px 0", border: "none", borderTop: "1px solid var(--border)" }} />
            
            <SettingSlider 
              keyName="MAX_PARALLEL_AGENTS" 
              value={settings["MAX_PARALLEL_AGENTS"] ?? "5"} 
              onSave={handleSaveSetting} 
            />
            <SettingSlider 
              keyName="MIN_RESEARCH_TURNS" 
              value={settings["MIN_RESEARCH_TURNS"] ?? "6"} 
              onSave={handleSaveSetting} 
              max={50}
            />
          </div>
 
           <div className="add-setting-row">
            <input
              value={newSettingKey}
              onChange={e => setNewSettingKey(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") void handleAddSetting(); }}
              placeholder="Setting Key (e.g. API_KEY)"
            />
            <button className="primary" onClick={handleAddSetting} disabled={savingAddKey || !newSettingKey.trim()}>
              {savingAddKey ? "..." : "Add Key"}
            </button>
          </div>
           <div className="settings-list">
             {Object.entries(settings).map(([key, value]) => {
               if (key === "AGENT_LOGGING") {
                 return (
                   <SettingToggle
                     key={key}
                     keyName={key}
                     value={value ?? "true"}
                     onSave={handleSaveSetting}
                   />
                 );
               }
               return (
                 <SettingItem
                   key={key}
                   keyName={key}
                   value={value ?? ""}
                   onSave={handleSaveSetting}
                   onDelete={handleDeleteSetting}
                 />
               );
             })}
           </div>
        </div>
      )}
    </section>
  );
}

export default SettingsPanel;
