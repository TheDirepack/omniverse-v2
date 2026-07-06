export type Tab =
	| "dashboard"
	| "database"
	| "traits"
	| "logs"
	| "theories"
	| "inference"
	| "settings";
export type SettingsTab = "providers" | "routing" | "general";

export type World = {
	id: number;
	slug: string | null;
	name: string;
	franchise: string | null;
	category: string | null;
	continuity: string | null;
	era: string | null;
	parent_id: number | null;
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

export type Claim = {
	id: number;
	subject_id: number;
	predicate: string;
	object_entity_id: number | null;
	object_literal: string | null;
	source_reference: string | null;
	source_wiki: string | null;
	support_count: number;
	contradiction_count: number;
	status: string;
	universe_scope: number | null;
};

export type UnconfirmedTrait = {
	id: number;
	universe_name: string;
	category: string | null;
	name: string;
	value: string;
	confidence: number;
	source: string | null;
};

export type UnconfirmedClaim = {
	id: number;
	universe_name: string;
	subject: string;
	predicate: string;
	object_val: string;
	reference: string | null;
	wiki_source: string | null;
	confidence: string | null;
};

export type WorldRecord = {
	id: number;
	name: string;
	summary: string | null;
	is_explored: boolean;
};

export type InferenceRule = {
	id: number;
	predicate_1: string;
	predicate_2: string;
	implied_predicate: string;
	rule_type: string;
	status: string;
	proposer_model: string | null;
	proposer_rationale: string | null;
	critic_model: string | null;
	critic_verdict: string | null;
	critic_rationale: string | null;
	human_approved: boolean;
	created_at: string;
};

export type Contradiction = {
	id: number;
	predicate: string;
	contradicts_claim_id: number;
};

export type RulesByStatus = {
	proposed: InferenceRule[];
	critiqued: InferenceRule[];
	approved: InferenceRule[];
	rejected: InferenceRule[];
};
