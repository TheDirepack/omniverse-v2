import { useState } from "react";

function SettingSlider({
	keyName,
	value,
	onSave,
	max = 20,
}: {
	keyName: string;
	value: string;
	onSave: (key: string, value: string) => Promise<void>;
	max?: number;
}) {
	const [draft, setDraft] = useState(parseInt(value, 10) || 5);
	const [savingSetting, setSavingSetting] = useState(false);

	const handleSave = async () => {
		setSavingSetting(true);
		try {
			await onSave(keyName, draft.toString());
		} finally {
			setSavingSetting(false);
		}
	};

	return (
		<div className="setting-item">
			<div
				className="setting-label"
				style={{
					display: "flex",
					justifyContent: "space-between",
					width: "100%",
					marginBottom: 8,
				}}
			>
				<span className="setting-key">{keyName}</span>
				<span className="setting-value-display">{draft}</span>
			</div>
			<div
				style={{
					display: "flex",
					alignItems: "center",
					gap: 12,
					width: "100%",
				}}
			>
				<input
					type="range"
					min="1"
					max={max}
					value={draft}
					onChange={(e) => setDraft(parseInt(e.target.value, 10))}
					style={{ flex: 1 }}
				/>

				<button
					type="button"
					className="chip"
					onClick={handleSave}
					disabled={savingSetting}
				>
					{savingSetting ? "..." : "Save"}
				</button>
			</div>
		</div>
	);
}

export default SettingSlider;
