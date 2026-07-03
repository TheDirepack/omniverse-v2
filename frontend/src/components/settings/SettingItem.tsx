import { useState } from "react";

function SettingItem({ keyName, value, onSave, onDelete }: {
  keyName: string;
  value: string;
  onSave: (key: string, value: string) => Promise<void>;
  onDelete: (key: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState(value);
  const [savingSetting, setSavingSetting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleSave = async () => {
    setSavingSetting(true);
    try {
      await onSave(keyName, draft);
    } finally {
      setSavingSetting(false);
    }
  };

  return (
    <div className="setting-item">
      <span className="setting-key">{keyName}</span>
      <input value={draft} onChange={e => setDraft(e.target.value)} className="setting-value" />
      <button className="chip" onClick={handleSave} disabled={savingSetting}>{savingSetting ? "..." : "Save"}</button>
      {confirmDelete ? (
        <span className="confirm-delete">
          <button className="chip delete" onClick={async () => { await onDelete(keyName); setConfirmDelete(false); }}>Confirm</button>
          <button className="chip" onClick={() => setConfirmDelete(false)}>Cancel</button>
        </span>
      ) : (
        <button className="chip delete" onClick={() => setConfirmDelete(true)}>×</button>
      )}
    </div>
  );
}

export default SettingItem;
