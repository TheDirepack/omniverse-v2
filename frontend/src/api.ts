import type { World, Anomaly, LogEntry, ProviderRecord, AgentRouteRecord, WorldRecord, Trait, UnconfirmedTrait } from "./types";

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
  return apiFetch("/api/research/results");
}

export async function fetchSettings(): Promise<{ general_settings: Record<string, string | null>; providers: ProviderRecord[]; agent_routes: AgentRouteRecord[] }> {
  return apiFetch("/api/settings");
}

export async function fetchProviders(): Promise<ProviderRecord[]> {
  return apiFetch("/api/providers");
}

export async function fetchAgentRoutes(): Promise<AgentRouteRecord[]> {
  return apiFetch("/api/settings/agent-routes");
}

export async function fetchAgentNames(): Promise<string[]> {
  return apiFetch("/api/settings/agent-names");
}

export async function fetchTraits(universeIds?: number[]): Promise<Trait[]> {
  const query = universeIds ? `?universe_ids=${universeIds.join(",")}` : "";
  return apiFetch(`/api/research/traits${query}`);
}

export async function fetchClaims(universeIds?: number[]): Promise<Claim[]> {
  const query = universeIds ? `?universe_ids=${universeIds.join(",")}` : "";
  return apiFetch(`/api/research/claims${query}`);
}

export async function fetchUnconfirmedTraits(universeNames?: string[]): Promise<UnconfirmedTrait[]> {
  const query = universeNames ? `?universe_ids=${universeNames.join(",")}` : "";
  return apiFetch(`/api/research/traits/unconfirmed${query}`);
}

export async function fetchUnconfirmedClaims(universeNames?: string[]): Promise<UnconfirmedClaim[]> {
  const query = universeNames ? `?universe_ids=${universeNames.join(",")}` : "";
  return apiFetch(`/api/research/claims/unconfirmed${query}`);
}

export async function fetchWorlds(): Promise<WorldRecord[]> {

  return apiFetch("/api/worlds");
}

export async function startOrchestrate(worlds: string[]): Promise<{ run_id: string }> {
  return apiFetch("/api/runs/orchestrate", {
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

export async function runFocusedSearch(worlds: string[], features: string[]): Promise<{ run_id: string }> {
  return apiFetch("/api/runs/focused-search", {
    method: "POST",
    body: JSON.stringify({ worlds, features }),
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
  return apiFetch("/api/settings/agent-routes", {
    method: "POST",
    body: JSON.stringify(route),
  });
}

export async function deleteAgentRoute(routeId: number): Promise<any> {
  return apiFetch(`/api/settings/agent-routes/${routeId}`, { method: "DELETE" });
}

export async function resetDatabase(): Promise<any> {
  return apiFetch("/api/worlds/reset-database", { method: "POST" });
}

export async function runTiering(): Promise<{ run_id: string }> {
  return apiFetch("/api/runs/tiering", { method: "POST" });
}

export async function clearLogsApi(): Promise<any> {
  return apiFetch("/api/worlds/clear-logs", { method: "POST" });
}

export async function resetCandidateHealth(): Promise<any> {
  return apiFetch("/api/settings/reset-health", { method: "POST" });
}

export async function fetchAgentActivity(): Promise<{ active_runs: string[]; logs: LogEntry[] }> {
  return apiFetch("/api/runs/agent-activity");
}

export async function abortRun(runId: string): Promise<any> {
  return apiFetch("/api/runs/abort", {
    method: "POST",
    body: JSON.stringify({ runId }),
  });
}

export async function extrapolate(payload: { scope: "all" | "worlds" | "tier"; worlds?: string[]; tier?: number }): Promise<{ run_id: string; worlds: string[] }> {
  return apiFetch("/api/runs/extrapolate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchFileLogs(filters: { 
  limit?: number; 
  offset?: number;
  filter?: string; 
  agent?: string; 
  world?: string; 
  model?: string; 
  event_type?: string; 
  tool?: string; 
}): Promise<{ logs: string[]; total: number; has_more: boolean }> {
  const params = new URLSearchParams();
  if (filters.limit) params.append("limit", filters.limit.toString());
  if (filters.offset !== undefined) params.append("offset", filters.offset.toString());
  if (filters.filter) params.append("filter", filters.filter);
  if (filters.agent) params.append("agent", filters.agent);
  if (filters.world) params.append("world", filters.world);
  if (filters.model) params.append("model", filters.model);
  if (filters.event_type) params.append("event_type", filters.event_type);
  if (filters.tool) params.append("tool", filters.tool);
  
  return apiFetch(`/api/runs/logs/file?${params.toString()}`);
}

export function createEventSource(runId: string): EventSource {
  return new EventSource(`${apiBase}/api/runs/logs/${runId}`);
}

// --- Inference rules / path materialization ---

export async function fetchInferenceRules(status?: string): Promise<any> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiFetch(`/api/inference/rules${query}`);
}

export async function triggerRuleProposal(): Promise<{ run_id: string; status: string }> {
  return apiFetch("/api/inference/rules/propose", { method: "POST" });
}

export async function approveInferenceRule(ruleId: number): Promise<any> {
  return apiFetch(`/api/inference/rules/${ruleId}/approve`, { method: "POST" });
}

export async function rejectInferenceRule(ruleId: number): Promise<any> {
  return apiFetch(`/api/inference/rules/${ruleId}/reject`, { method: "POST" });
}

export async function triggerMaterialization(): Promise<{ status: string; created_count: number }> {
  return apiFetch("/api/inference/materialize", { method: "POST" });
}

export async function fetchContradictions(): Promise<any[]> {
  return apiFetch("/api/inference/contradictions");
}

export async function fetchCompositionDepth(): Promise<{ max_composition_depth: number }> {
  return apiFetch("/api/inference/depth");
}

export async function setCompositionDepth(depth: number): Promise<{ max_composition_depth: number }> {
  return apiFetch("/api/inference/depth", {
    method: "PUT",
    body: JSON.stringify({ max_composition_depth: depth }),
  });
}
