export type Tab = "dashboard" | "database" | "theories" | "settings";
export type SettingsTab = "providers" | "routing" | "general";

export type World = {
  id: number;
  name: string;
  summary: string | null;
  is_explored: boolean;
  tier: number | null;
  tier_justification: string | null;
  theory: string | null;
  theory_audit: string | null;
};

export type Anomaly = {
  world_id: number | null;
  description: string;
  detected_at: string;
};

export type LogEntry = {
  id: number;
  node_name: string;
  thought: string;
  status: string;
  created_at: string;
};

export type ProviderKey = {
  id: number;
  provider_id: number;
  api_key: string;
  priority: number;
};

export type ProviderRecord = {
  id: number;
  name: string;
  provider_type: string | null;
  base_url: string | null;
  models: string | null;
  keys: ProviderKey[];
};

export type AgentRouteRecord = {
  id: number;
  task_type: string;
  provider_id: number | null;
  models: string | null;
  priority: number;
};

export type Trait = {
  id: number;
  universe_id: number;
  category: string | null;
  name: string;
  value: string;
  canon_status: string | null;
  reference: string | null;
  wiki_source: string | null;
};

export type WorldRecord = {
  id: number;
  name: string;
  summary: string | null;
  is_explored: boolean;
};
