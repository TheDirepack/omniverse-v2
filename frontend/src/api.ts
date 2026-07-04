import type { World, Anomaly, LogEntry, ProviderRecord, AgentRouteRecord, WorldRecord } from "./types";

const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}

export async function fetchResults(): Promise<{ tier_system: string | null; worlds: World[]; anomalies: Anomaly[] }> {
  return apiFetch("/api/results");
}

export async function fetchSettings(): Promise<{ general_settings: Record<string, string | null>; providers: ProviderRecord[]; agent_routes: AgentRouteRecord[] }> {
  return apiFetch("/api/settings");
}

export async function fetchProviders(): Promise<ProviderRecord[]> {
  return apiFetch("/api/providers");
}

export async function fetchAgentRoutes(): Promise<AgentRouteRecord[]> {
  return apiFetch("/api/agent-routes");
}

export async function fetchAgentNames(): Promise<string[]> {
  return apiFetch("/api/agent-names");
}

export async function fetchWorlds(): Promise<WorldRecord[]> {
  return apiFetch("/api/worlds");
}

export async function startOrchestrate(worlds: string[]): Promise<{ run_id: string }> {
  return apiFetch("/api/orchestrate", {
    method: "POST",
    body: JSON.stringify({ worlds }),
  });
}

export async function researchUnexplored(): Promise<{ run_id: string | null; worlds: string[]; status: string }> {
  return apiFetch("/api/worlds/research-unexplored", { method: "POST" });
}

export async function addWorld(world_name: string, auto_research = true): Promise<any> {
  return apiFetch("/api/worlds", {
    method: "POST",
    body: JSON.stringify({ world_name, auto_research }),
  });
}

export async function resetAllExplored(): Promise<any> {
  return apiFetch("/api/worlds/reset-all-explored", { method: "POST" });
}

export async function resetWorldExplored(worldId: number): Promise<any> {
  return apiFetch(`/api/worlds/${worldId}/reset-explored`, { method: "POST" });
}

export async function deleteWorld(worldId: number): Promise<any> {
  return apiFetch(`/api/worlds/${worldId}`, { method: "DELETE" });
}

export async function runFocusedSearch(world_name: string, feature: string): Promise<{ run_id: string }> {
  return apiFetch("/api/focused-search", {
    method: "POST",
    body: JSON.stringify({ world_name, feature }),
  });
}

export async function fetchProviderModels(providerId: number): Promise<{ models: string[] }> {
  return apiFetch(`/api/providers/${providerId}/models`);
}

export async function saveGeneralSetting(key: string, value: string | null): Promise<any> {
  return apiFetch("/api/settings/general", {
    method: "POST",
    body: JSON.stringify({ key, value }),
  });
}

export async function saveProvider(provider: any): Promise<any> {
  return apiFetch("/api/providers", {
    method: "POST",
    body: JSON.stringify(provider),
  });
}

export async function saveProviderKey(key: { id?: number; provider_id: number; api_key: string; priority: number }): Promise<any> {
  return apiFetch("/api/providers/keys", {
    method: "POST",
    body: JSON.stringify(key),
  });
}

export async function deleteProviderKey(keyId: number): Promise<any> {
  return apiFetch(`/api/providers/keys/${keyId}`, { method: "DELETE" });
}

export async function deleteProvider(providerId: number): Promise<any> {
  return apiFetch(`/api/providers/${providerId}`, { method: "DELETE" });
}

export async function saveAgentRoute(route: any): Promise<any> {
  return apiFetch("/api/agent-routes", {
    method: "POST",
    body: JSON.stringify(route),
  });
}

export async function deleteAgentRoute(routeId: number): Promise<any> {
  return apiFetch(`/api/agent-routes/${routeId}`, { method: "DELETE" });
}

export async function resetDatabase(): Promise<any> {
  return apiFetch("/api/reset-database", { method: "POST" });
}

export async function resetCandidateHealth(): Promise<any> {
  return apiFetch("/api/settings/reset-health", { method: "POST" });
}

export async function clearLogsApi(): Promise<any> {
  return apiFetch("/api/clear-logs", { method: "POST" });
}

export async function abortRun(runId: string): Promise<any> {
  return apiFetch("/api/abort", {
    method: "POST",
    body: JSON.stringify({ runId }),
  });
}

export function createEventSource(runId: string): EventSource {
  return new EventSource(`${apiBase}/api/logs/${runId}`);
}
