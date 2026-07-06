import type { LucideIcon } from "lucide-react";
import { GitBranch, Layers, Lightbulb, Settings, Terminal } from "lucide-react";
import { useState } from "react";
import DashboardPanel from "./components/DashboardPanel";
import DatabasePanel from "./components/DatabasePanel";
import InferenceRulesPanel from "./components/InferenceRulesPanel";
import LogViewerPanel from "./components/LogViewerPanel";
import SettingsPanel from "./components/settings/SettingsPanel";
import TheoriesPanel from "./components/TheoriesPanel";
import TraitViewerPanel from "./components/TraitViewerPanel";
import type { Tab } from "./types";

const navItems: Array<{ id: Tab; label: string; Icon: LucideIcon }> = [
	{ id: "dashboard", label: "Command Center", Icon: Terminal },
	{ id: "database", label: "Tiers", Icon: Layers },
	{ id: "traits", label: "Main DB", Icon: Layers },
	{ id: "logs", label: "System Logs", Icon: Terminal },
	{ id: "theories", label: "Theories", Icon: Lightbulb },
	{ id: "inference", label: "Inference Rules", Icon: GitBranch },
	{ id: "settings", label: "Settings", Icon: Settings },
];

export default function App() {
	const [tab, setTab] = useState<Tab>("dashboard");

	return (
		<div className="app-shell">
			<aside className="sidebar">
				<div className="brand">
					<Layers />
					<div>
						<div className="brand-title">OMNIVERSE 2</div>
						<div className="brand-sub">LangGraph command center</div>
					</div>
				</div>
				<nav className="nav">
					{navItems.map(({ id, label, Icon }) => (
						<button
							key={id}
							className={tab === id ? "nav-item active" : "nav-item"}
							onClick={() => setTab(id)}
							type="button"
						>
							<Icon size={16} /> {label}
						</button>
					))}
				</nav>
			</aside>

			<main className="main">
				{tab === "dashboard" && <DashboardPanel />}
				{tab === "database" && <DatabasePanel />}
				{tab === "traits" && <TraitViewerPanel />}
				{tab === "logs" && <LogViewerPanel />}
				{tab === "theories" && <TheoriesPanel />}
				{tab === "inference" && <InferenceRulesPanel />}
				{tab === "settings" && <SettingsPanel />}
			</main>
		</div>
	);
}
