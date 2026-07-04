import { useState } from "react";
import type { ProviderRecord, ProviderKey } from "../types";
import * as api from "../../api";

const API_KEY_MASK = "●●●●●●●●●●●●";

const PROVIDER_TYPES = [
  { value: "openai", label: "OpenAI", baseUrlConfigurable: false },
  { value: "anthropic", label: "Anthropic", baseUrlConfigurable: false },
  { value: "gemini", label: "Gemini", baseUrlConfigurable: false },
  { value: "ollama", label: "Ollama", baseUrlConfigurable: true },
  { value: "groq", label: "Groq", baseUrlConfigurable: false },
  { value: "openrouter", label: "OpenRouter", baseUrlConfigurable: false },
  { value: "custom", label: "Custom (OpenAI-compatible)", baseUrlConfigurable: true },
];

function resolveTypeInfo(type: string) {
  return PROVIDER_TYPES.find(t => t.value === type) ?? null;
}

function resolveLabel(type: string) {
  const info = resolveTypeInfo(type);
  return info?.label ?? type ?? "No type";
}

function isBaseUrlConfigurable(type: string) {
  const info = resolveTypeInfo(type);
  return info?.baseUrlConfigurable ?? false;
}

function ProviderCard({ provider, onSave, onSaveKey, onDeleteKey, onDeleteProvider }: {
  provider: ProviderRecord;
  onSave: (p: any) => Promise<void>;
  onSaveKey: (k: any) => Promise<void>;
  onDeleteKey: (id: number) => Promise<void>;
  onDeleteProvider?: (id: number) => Promise<void>;
}) {
  // Backward-compat: old DB stored 'openai' for custom providers that have a base_url
  const effectiveType = provider.provider_type === "openai" && provider.base_url
    ? "custom"
    : provider.provider_type;
  const [typeDraft, setTypeDraft] = useState(effectiveType ?? "");
  const typeInfo = resolveTypeInfo(typeDraft);
  const baseUrlConfigurable = isBaseUrlConfigurable(typeDraft);

  const [nameDraft, setNameDraft] = useState(provider.name);
  const [savingName, setSavingName] = useState(false);

  const [savingType, setSavingType] = useState(false);

  const [baseUrlDraft, setBaseUrlDraft] = useState(provider.base_url ?? "");
  const [savingBaseUrl, setSavingBaseUrl] = useState(false);

  const [modelsTags, setModelsTags] = useState<string[]>(
    (provider.models ?? "").split(",").map(m => m.trim()).filter(Boolean)
  );
  const [newModelTag, setNewModelTag] = useState("");
  const [savingModels, setSavingModels] = useState(false);
  const [fetchingModels, setFetchingModels] = useState(false);

  const [keysDraft, setKeysDraft] = useState<ProviderKey[]>(provider.keys);
  const [editingKeyId, setEditingKeyId] = useState<number | null>(null);
  const [savingKeyIds, setSavingKeyIds] = useState<Set<number>>(new Set());
  const [confirmDeleteKeyId, setConfirmDeleteKeyId] = useState<number | null>(null);

  const [confirmDeleteProvider, setConfirmDeleteProvider] = useState(false);

  const handleSaveName = async () => {
    if (!nameDraft.trim()) return;
    setSavingName(true);
    try {
      await onSave({ id: provider.id, name: nameDraft });
    } finally {
      setSavingName(false);
    }
  };

  const handleSaveType = async (newType: string) => {
    setSavingType(true);
    try {
      const providerType = newType;
      const newTypeInfo = PROVIDER_TYPES.find(t => t.value === newType);
      const payload: any = { id: provider.id, name: nameDraft, provider_type: providerType };
      if (newTypeInfo?.baseUrlConfigurable) {
        if (!provider.base_url) {
          const defaultUrl = newType === "custom" ? "https://api.openai.com/v1" : "http://localhost:11434";
          payload.base_url = defaultUrl;
          setBaseUrlDraft(defaultUrl);
        }
      } else if (baseUrlDraft) {
        payload.base_url = null;
      }
      await onSave(payload);
      setTypeDraft(newType);
    } finally {
      setSavingType(false);
    }
  };

  const handleSaveBaseUrl = async () => {
    setSavingBaseUrl(true);
    try {
      const payload: any = { id: provider.id, name: nameDraft, base_url: baseUrlDraft || null };
      // Backward-compat: correct provider_type for old records stored as 'openai' with custom base_url
      if (provider.provider_type === "openai" && baseUrlDraft) {
        payload.provider_type = "custom";
      }
      await onSave(payload);
    } finally {
      setSavingBaseUrl(false);
    }
  };

  const handleSaveModels = async () => {
    setSavingModels(true);
    try {
      const payload: any = { id: provider.id, name: nameDraft, models: modelsTags.join(",") || null };
      // Backward-compat: correct provider_type for old records stored as 'openai' with custom base_url
      if (provider.provider_type === "openai" && provider.base_url) {
        payload.provider_type = "custom";
      }
      await onSave(payload);
    } finally {
      setSavingModels(false);
    }
  };

  const fetchModels = async () => {
    setFetchingModels(true);
    try {
      const { models } = await api.fetchProviderModels(provider.id);
      const combined = Array.from(new Set([...modelsTags, ...models]));
      setModelsTags(combined);
    } catch (e) {
      console.error("Failed to fetch models:", e);
    } finally {
      setFetchingModels(false);
    }
  };

  const addModelTag = () => {
    const tag = newModelTag.trim();
    if (tag && !modelsTags.includes(tag)) {
      setModelsTags([...modelsTags, tag]);
    }
    setNewModelTag("");
  };

  const removeModelTag = (tag: string) => {
    setModelsTags(modelsTags.filter(t => t !== tag));
  };

  const handleSaveKey = async (key: ProviderKey) => {
    setSavingKeyIds(prev => new Set(prev).add(key.id));
    try {
      const savedKey = await onSaveKey({ id: key.id, provider_id: key.provider_id, api_key: key.api_key, priority: key.priority });
      setKeysDraft(prev => prev.map(k => k.id === key.id ? { ...k, id: savedKey?.id ?? key.id } : k));
    } finally {
      setSavingKeyIds(prev => {
        const next = new Set(prev);
        next.delete(key.id);
        return next;
      });
      setEditingKeyId(null);
    }
  };

  const handleDeleteKey = async (keyId: number) => {
    try {
      await onDeleteKey(keyId);
      setKeysDraft(prev => prev.filter(k => k.id !== keyId));
    } catch {
      console.error("Failed to delete key");
    } finally {
      setConfirmDeleteKeyId(null);
    }
  };

  const moveKey = (idx: number, direction: -1 | 1) => {
    const target = idx + direction;
    if (target < 0 || target >= keysDraft.length) return;
    const newKeys = [...keysDraft];
    [newKeys[idx], newKeys[target]] = [newKeys[target], newKeys[idx]];
    newKeys[idx] = { ...newKeys[idx], priority: idx };
    newKeys[target] = { ...newKeys[target], priority: target };
    setKeysDraft(newKeys);
  };

  const addingKey = async () => {
    const tempId = -(keysDraft.length + 1);
    const newKey = { id: tempId, provider_id: provider.id, api_key: "", priority: keysDraft.length };
    setKeysDraft([...keysDraft, newKey]);
    setEditingKeyId(tempId);
  };

  const showMoveKeys = keysDraft.length > 1;
  const keyCount = keysDraft.length;

  return (
    <div className="provider-card">
      <div className="provider-card-header">
        <div className="provider-identity-section">
          <input
            className="provider-name"
            value={nameDraft}
            onChange={e => setNameDraft(e.target.value)}
            placeholder="Provider name"
          />
          <select
            className="provider-type-select"
            value={typeDraft}
            onChange={e => {
              const newVal = e.target.value;
              setTypeDraft(newVal);
              void handleSaveType(newVal);
            }}
            disabled={savingType}
          >
            <option value="" disabled>Select type</option>
            {PROVIDER_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <span className="provider-type-badge">{resolveLabel(typeDraft)}</span>
          {savingType && <span className="saving-indicator">...</span>}
          <button className="chip" onClick={handleSaveName} disabled={savingName || !nameDraft.trim()}>
            {savingName ? "..." : "Save Name"}
          </button>
          {confirmDeleteProvider ? (
            <span className="confirm-delete">
              Delete provider?{" "}
              <button className="chip delete" onClick={async () => { await onDeleteProvider?.(provider.id); setConfirmDeleteProvider(false); }}>Yes</button>
              <button className="chip" onClick={() => setConfirmDeleteProvider(false)}>No</button>
            </span>
          ) : (
            <button className="chip delete" onClick={() => setConfirmDeleteProvider(true)} disabled={!onDeleteProvider}>Delete</button>
          )}
        </div>
        {keyCount === 0 && typeDraft !== "ollama" && typeDraft !== "custom" && <span className="badge-warning">⚠ 0 keys — routing steps using this provider will be skipped</span>}
      </div>

      <div className="provider-card-body">
        {baseUrlConfigurable && (
          <div className="provider-section">
            <h4>Base URL</h4>
            <label className="field">
              <span>Base URL</span>
              <input value={baseUrlDraft} onChange={e => setBaseUrlDraft(e.target.value)} placeholder={provider.provider_type === "ollama" ? "http://localhost:11434" : "https://api.openai.com/v1"} />
            </label>
            <button className="chip" onClick={handleSaveBaseUrl} disabled={savingBaseUrl}>{savingBaseUrl ? "..." : "Save"}</button>
          </div>
        )}

        {/* Models */}
        <div className="provider-section">
          <h4>Models this provider can serve</h4>
          <div className="models-tags">
            {modelsTags.map(tag => (
              <span key={tag} className="tag">
                {tag}
                <button className="tag-remove" onClick={() => removeModelTag(tag)}>×</button>
              </span>
            ))}
            <span className="tag-input-wrap">
              <input
                value={newModelTag}
                onChange={e => setNewModelTag(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addModelTag(); } }}
                placeholder="+ add model"
                className="tag-input"
              />
            </span>
          </div>
           <p className="help-text">These become the model choices when you build routing rules for this provider. Enter model names and press Enter to add.</p>
           <div className="provider-actions">
             <button className="chip" onClick={handleSaveModels} disabled={savingModels}>{savingModels ? "..." : "Save"}</button>
             <button className="chip" onClick={fetchModels} disabled={fetchingModels}>{fetchingModels ? "..." : "Sync Saved Models"}</button>
           </div>
         </div>

        {/* API Keys */}
        <div className="provider-section">
          <h4>API Keys (tried in order, top to bottom)</h4>
          <p className="help-text">If a key fails or hits a rate limit, the next one is tried automatically.</p>
          <div className="keys-list">
            {keysDraft.sort((a, b) => a.priority - b.priority).map((key, idx) => (
              <div key={key.id} className="key-row">
                <span className="key-index">{idx + 1}.</span>
                {editingKeyId === key.id ? (
                  <>
                    <input
                      type="password"
                      value={key.api_key}
                      onChange={e => {
                        const newKeys = [...keysDraft];
                        newKeys[idx] = { ...newKeys[idx], api_key: e.target.value };
                        setKeysDraft(newKeys);
                      }}
                      placeholder="API Key"
                      autoFocus
                    />
                    <button className="chip" onClick={() => handleSaveKey(key)} disabled={savingKeyIds.has(key.id)}>
                      {savingKeyIds.has(key.id) ? "..." : "Save"}
                    </button>
                    <button className="chip" onClick={() => setEditingKeyId(null)}>Cancel</button>
                  </>
                ) : (
                  <>
                    <span className="key-value">{key.api_key ? API_KEY_MASK + key.api_key.slice(-4) : "(empty)"}</span>
                    <button className="chip" onClick={() => setEditingKeyId(key.id)}>Edit</button>
                    {showMoveKeys && (
                      <>
                        <button className="chip" onClick={() => moveKey(idx, -1)} disabled={idx === 0}>↑</button>
                        <button className="chip" onClick={() => moveKey(idx, 1)} disabled={idx === keysDraft.length - 1}>↓</button>
                      </>
                    )}
                    {confirmDeleteKeyId === key.id ? (
                      <span className="confirm-delete">
                        <button className="chip delete" onClick={() => handleDeleteKey(key.id)}>Confirm</button>
                        <button className="chip" onClick={() => setConfirmDeleteKeyId(null)}>Cancel</button>
                      </span>
                    ) : (
                      <button className="chip delete" onClick={() => setConfirmDeleteKeyId(key.id)}>×</button>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
          <button className="chip" onClick={addingKey}>+ Add Fallback Key</button>
        </div>
      </div>
    </div>
  );
}

export default ProviderCard;