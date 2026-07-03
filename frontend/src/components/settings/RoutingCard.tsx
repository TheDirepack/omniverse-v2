import { useState } from "react";
import type { AgentRouteRecord, ProviderRecord } from "../../types";

function RoutingCard({ agentName, routes, providers, onSave, onDelete, defaultRoutes }: {
  agentName: string;
  routes: AgentRouteRecord[];
  providers: ProviderRecord[];
  onSave: (route: any) => Promise<any>;
  onDelete: (id: number) => Promise<void>;
  defaultRoutes?: AgentRouteRecord[];
}) {
  const [expanded, setExpanded] = useState(agentName === "DEFAULT");
  const [localRoutes, setLocalRoutes] = useState(routes);

  const isDefault = agentName === "DEFAULT";
  const hasCustom = routes.length > 0;
  const defaultCount = defaultRoutes?.length ?? 0;
  const statusText = isDefault ? `${routes.length} step(s)` : hasCustom ? `${routes.length} custom step(s)` : `Using DEFAULT (${defaultCount} step(s))`;

  const updateRoute = (idx: number, field: string, value: any) => {
    const newRoutes = [...localRoutes];
    newRoutes[idx] = { ...newRoutes[idx], [field]: value };
    setLocalRoutes(newRoutes);
  };

  const handleSave = async (idx: number) => {
    await onSave(localRoutes[idx]);
  };

  // Compute resolved sequence
  const resolvedSequence: Array<{ provider: string; keyLabel: string; model: string }> = [];
  localRoutes.forEach(route => {
    const provider = providers.find(p => p.id === route.provider_id);
    if (!provider) return;
    const models = (route.models || provider.models || "").split(",").map(m => m.trim()).filter(Boolean);
    provider.keys.forEach((_, kIdx) => {
      models.forEach(model => {
        resolvedSequence.push({ provider: provider.name, keyLabel: `Key ${kIdx + 1}`, model });
      });
    });
  });

  const overrideFromDefault = async () => {
    if (!defaultRoutes) return;
    const savedRoutes: AgentRouteRecord[] = [];
    for (const dr of defaultRoutes) {
      const r = await onSave({ id: 0, task_type: agentName, provider_id: dr.provider_id, models: dr.models, priority: dr.priority });
      if (r) savedRoutes.push(r);
    }
    setLocalRoutes(prev => [...prev, ...savedRoutes]);
  };

  return (
    <div className={`routing-card ${expanded ? "expanded" : ""}`}>
      <div className="routing-card-header" onClick={() => setExpanded(!expanded)}>
        <div className="routing-card-title">
          <span className="agent-name">{isDefault ? "DEFAULT" : agentName}</span>
          <span className="agent-status">{statusText}</span>
        </div>
        <div className="routing-card-actions">
          {!isDefault && !hasCustom && defaultRoutes && (
            <button className="chip" onClick={e => { e.stopPropagation(); void overrideFromDefault(); }}>Override</button>
          )}
          <span className="expand-icon">{expanded ? "▲" : "▼"}</span>
        </div>
      </div>

      {expanded && (
        <div className="routing-card-body">
          <p className="help-text">Each agent tries its fallback chain top to bottom: provider → its keys in order → its models in order. If everything fails, the run fails that step. Agents without their own chain use the DEFAULT chain.</p>

          {resolvedSequence.length > 0 && (
            <div className="resolved-sequence">
              <h4>Resolved Fallback Order:</h4>
              <ol className="sequence-list">
                {resolvedSequence.map((item, idx) => (
                  <li key={idx} className="sequence-item">{item.provider} → {item.keyLabel} → {item.model}</li>
                ))}
              </ol>
            </div>
          )}

          <hr className="routing-divider" />

          <div className="route-slots">
            {localRoutes.map((route, idx) => {
              const providerModels = providers.find(p => p.id === route.provider_id)?.models ?? "";
              return (
                <div key={route.id} className="route-slot">
                  <span className="slot-num">#{idx + 1}</span>
                  <select
                    value={route.provider_id ?? ""}
                    onChange={e => updateRoute(idx, "provider_id", e.target.value ? Number(e.target.value) : null)}
                  >
                    <option value="">Select Provider</option>
                    {providers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                  <input
                    value={route.models ?? ""}
                    onChange={e => updateRoute(idx, "models", e.target.value || null)}
                    placeholder={`Models CSV (default: ${providerModels || "none"})`}
                    className="route-models-input"
                  />
                  <div className="slot-actions">
                    <button className="chip" onClick={() => void handleSave(idx)}>Save</button>
                    <button className="chip delete" onClick={async () => {
                      await onDelete(route.id);
                      setLocalRoutes(prev => prev.filter(r => r.id !== route.id));
                    }}>×</button>
                  </div>
                </div>
              );
            })}

            <button className="chip add-slot" onClick={async () => {
              const savedRoute = await onSave({ id: 0, task_type: agentName, provider_id: null, models: null, priority: localRoutes.length });
              if (savedRoute) setLocalRoutes(prev => [...prev, savedRoute]);
            }}>+ Add Provider Step</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default RoutingCard;
