import { useState, useEffect } from "react";
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
  const [resolvedExpanded, setResolvedExpanded] = useState(false);
  const [localRoutes, setLocalRoutes] = useState(routes);
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);


  useEffect(() => {
    setLocalRoutes(routes);
  }, [routes]);


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

  // State for tag inputs per route
  const [modelDrafts, setModelDrafts] = useState<Record<number, string>>({});

  useEffect(() => {
    setModelDrafts(prev => {
      const next = { ...prev };
      let changed = false;
      localRoutes.forEach((_, idx) => {
        if (!(idx in next)) {
          next[idx] = "";
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [localRoutes]);

  const addModelTag = (idx: number, model: string) => {
    if (!model.trim()) return;
    const currentModels = (localRoutes[idx].models || "").split(",").map(m => m.trim()).filter(Boolean);
    if (!currentModels.includes(model.trim())) {
      const newModels = [...currentModels, model.trim()].join(",");
      updateRoute(idx, "models", newModels);
    }
    setModelDrafts(prev => ({ ...prev, [idx]: "" }));
  };

  const removeModelTag = (idx: number, model: string) => {
    const currentModels = (localRoutes[idx].models || "").split(",").map(m => m.trim()).filter(Boolean);
    const newModels = currentModels.filter(m => m !== model).join(",");
    updateRoute(idx, "models", newModels || null);
  };

  const handleDragStart = (idx: number) => {
    setDraggedIdx(idx);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = async (targetIdx: number) => {
    if (draggedIdx === null || draggedIdx === targetIdx) return;

    const newRoutes = [...localRoutes];
    const [movedRoute] = newRoutes.splice(draggedIdx, 1);
    newRoutes.splice(targetIdx, 0, movedRoute);

    setLocalRoutes(newRoutes);
    setDraggedIdx(null);

    // Persist new priority
    for (let i = 0; i < newRoutes.length; i++) {
      await onSave({ ...newRoutes[i], priority: i });
    }
  };

  // Compute resolved sequence
  const resolvedSequence: Array<{ provider: string; keyLabel: string; model: string }> = [];
  const routesToResolve = (localRoutes.length > 0 ? localRoutes : (defaultRoutes ?? [])).slice().sort((a, b) => (a.priority ?? 0) - (b.priority ?? 0));
  const seen = new Set<string>();

  routesToResolve.forEach(route => {
    if (!route) return;
    const provider = providers.find(p => p.id === route.provider_id);
    if (!provider) return;
    const models = (route.models || provider.models || "").split(",").map(m => m.trim()).filter(Boolean);
    
    const keys = provider.keys && provider.keys.length > 0 ? provider.keys : [{}];
    
    keys.forEach((_, kIdx) => {
      models.forEach(model => {
        const id = `${provider.id}:${kIdx}:${model}`;
        if (!seen.has(id)) {
          resolvedSequence.push({ 
            provider: provider.name, 
            keyLabel: provider.keys && provider.keys.length > 0 ? `Key ${kIdx + 1}` : "No Key", 
            model 
          });
          seen.add(id);
        }
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
          
          <div className="route-slots">
            {localRoutes.map((route, idx) => {
              const providerModels = providers.find(p => p.id === route.provider_id)?.models ?? "";
              return (
                <div 
                  key={route.id} 
                  className={`route-slot ${draggedIdx === idx ? "dragging" : ""}`}
                  draggable
                  onDragStart={() => handleDragStart(idx)}
                  onDragOver={handleDragOver}
                  onDrop={() => handleDrop(idx)}
                >
                  <span className="slot-num">#{idx + 1}</span>
                  <select
                    value={route.provider_id ?? ""}
                    onChange={e => updateRoute(idx, "provider_id", e.target.value ? Number(e.target.value) : null)}
                  >
                    <option value="">Select Provider</option>
                    {providers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                  
                    {route.provider_id && (
                       <div className="route-models-selector">
                         {(() => {
                           const provider = providers.find(p => p.id === route.provider_id);
                           const providerModels = provider?.models ?? "";
                           const modelList = providerModels ? providerModels.split(",").map(m => m.trim()).filter(Boolean) : [];
                           const selectedModels = (route.models || "").split(",").map(m => m.trim()).filter(Boolean);
                           return (
                             <div className="models-tags">
                               {selectedModels.map(m => (
                                 <span key={m} className="tag">
                                   {m}
                                   <button className="tag-remove" onClick={() => removeModelTag(idx, m)}>×</button>
                                 </span>
                               ))}
                               <div className="tag-input-wrap">
                                 <select
                                   value={modelDrafts[idx] || ""}
                                   onChange={e => setModelDrafts(prev => ({ ...prev, [idx]: e.target.value }))}
                                   className="tag-input"
                                   style={{ width: '160px' }}
                                 >
                                   <option value="">+ Add Model</option>
                                   {modelList.map(m => (
                                     <option key={m} value={m}>{m}</option>
                                   ))}
                                 </select>
                                 <button 
                                   className="chip" 
                                   onClick={() => addModelTag(idx, modelDrafts[idx] || "")}
                                   disabled={!modelDrafts[idx]}
                                 >
                                   Add
                                 </button>
                               </div>
                             </div>
                           );
                         })()}
                       </div>
                     )}

                   
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
          
          <hr className="routing-divider" />
          
          {resolvedSequence.length > 0 && (
            <div className="resolved-sequence-container">
              <div className="resolved-header" onClick={() => setResolvedExpanded(!resolvedExpanded)}>
                <h4>Resolved Fallback Order:</h4>
                <span className="expand-icon">{resolvedExpanded ? "▲" : "▼"}</span>
              </div>
              {resolvedExpanded && (
                <ol className="sequence-list">
                  {resolvedSequence.map((item, idx) => (
                    <li key={idx} className="sequence-item">{item.provider} → {item.keyLabel} → {item.model}</li>
                  ))}
                </ol>
              )}
            </div>
          )}
        </div>

      )}
    </div>
  );
}

export default RoutingCard;
