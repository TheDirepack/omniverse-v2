import { useState } from "react";
import { Layers, Lightbulb, Settings, Terminal } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Tab } from "./types";

import DashboardPanel from "./components/DashboardPanel";
import DatabasePanel from "./components/DatabasePanel";
import TheoriesPanel from "./components/TheoriesPanel";
import SettingsPanel from "./components/settings/SettingsPanel";

const navItems: Array<{ id: Tab; label: string; Icon: LucideIcon }> = [
  { id: "dashboard", label: "Command Center", Icon: Terminal },
  { id: "database", label: "Tiers", Icon: Layers },
  { id: "theories", label: "Theories", Icon: Lightbulb },
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
            <button key={id} className={tab === id ? "nav-item active" : "nav-item"} onClick={() => setTab(id)}>
              <Icon size={16} /> {label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main">
        {tab === "dashboard" && <DashboardPanel />}
        {tab === "database" && <DatabasePanel />}
        {tab === "theories" && <TheoriesPanel />}
        {tab === "settings" && <SettingsPanel />}
      </main>
    </div>
  );
}
