import { useState } from "react";

function SettingToggle({
	keyName,
	value,
	onSave,
}: {
	keyName: string;
	value: string;
	onSave: (key: string, value: string) => Promise<void>;
}) {
	const [checked, setChecked] = useState(value === "true");
	const [saving, setSaving] = useState(false);

	const handleToggle = async () => {
		const newValue = !checked;
		setChecked(newValue);
		setSaving(true);
		try {
			await onSave(keyName, newValue ? "true" : "false");
		} finally {
			setSaving(false);
		}
	};

	return (
		<div className="setting-item">
			<span className="setting-key">{keyName}</span>
			<div className="setting-toggle-container">
				<input
					type="checkbox"
					checked={checked}
					onChange={handleToggle}
					disabled={saving}
					className="setting-toggle"
				/>
				{saving && <span className="saving-indicator">...</span>}
			</div>
		</div>
	);
}

export default SettingToggle;
