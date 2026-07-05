import { useState, useEffect } from "react";
import type { InferenceRule } from "../types";
import * as api from "../api";

type RulesByStatus = {
  proposed: InferenceRule[];
  critiqued: InferenceRule[];
  approved: InferenceRule[];
  rejected: InferenceRule[];
};

const EMPTY_RULES: RulesByStatus = { proposed: [], critiqued: [], approved: [], rejected: [] };

function RuleCard({ rule, onApprove, onReject }: { rule: InferenceRule; onApprove?: (id: number) => void; onReject?: (id: number) => void }) {
  return (
    <div className="theory-card" style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ fontFamily: "monospace", fontSize: "1rem" }}>
          {rule.predicate_1} + {rule.predicate_2} → {rule.implied_predicate}
        </h3>
        <div className="badge">{rule.rule_type}</div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 12 }}>
        <div>
          <div className="audit-label">Proposer ({rule.proposer_model ?? "unknown"})</div>
          <div className="audit-text">{rule.proposer_rationale ?? "—"}</div>
        </div>
        <div>
          <div className="audit-label">
            Critic ({rule.critic_model ?? "unknown"})
            {rule.critic_verdict && <span style={{ marginLeft: 8, opacity: 0.8 }}>[{rule.critic_verdict}]</span>}
          </div>
          <div className="audit-text">{rule.critic_rationale ?? "— not yet critiqued —"}</div>
        </div>
      </div>

      {(onApprove || onReject) && (
        <div style={{ display: "flex", gap: 8 }}>
          {onApprove && (
            <button onClick={() => onApprove(rule.id)} style={{ padding: "4px 12px", cursor: "pointer" }}>
              Approve
            </button>
          )}
          {onReject && (
            <button onClick={() => onReject(rule.id)} style={{ padding: "4px 12px", cursor: "pointer", opacity: 0.7 }}>
              Reject
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function InferenceRulesPanel() {
  const [rules, setRules] = useState<RulesByStatus>(EMPTY_RULES);
  const [contradictions, setContradictions] = useState<any[]>([]);
  const [depth, setDepth] = useState<number>(2);
  const [depthInput, setDepthInput] = useState<string>("2");
  const [proposing, setProposing] = useState(false);
  const [materializing, setMaterializing] = useState(false);

  useEffect(() => {
    void refresh();
  }, []);

  const refresh = async () => {
    try {
      const [rulesData, depthData, contradictionsData] = await Promise.all([
        api.fetchInferenceRules(),
        api.fetchCompositionDepth(),
        api.fetchContradictions(),
      ]);
      setRules(rulesData);
      setDepth(depthData.max_composition_depth);
      setDepthInput(String(depthData.max_composition_depth));
      setContradictions(contradictionsData);
    } catch (e) {
      console.error(e);
    }
  };

  const handlePropose = async () => {
    // Manual trigger only, per design: a bad composition rule has
    // universe-wide blast radius, so this never runs automatically.
    setProposing(true);
    try {
      await api.triggerRuleProposal();
      alert("Rule proposal pass started. Refresh in a moment to see results — this calls two separate models (proposer + independent critic) per candidate pair.");
    } catch (e) {
      alert("Error starting rule proposal: " + (e as Error).message);
    } finally {
      setProposing(false);
    }
  };

  const handleMaterialize = async () => {
    setMaterializing(true);
    try {
      const result = await api.triggerMaterialization();
      alert(`Materialization complete. ${result.created_count} new inferred claim(s) created.`);
      await refresh();
    } catch (e) {
      alert("Error materializing: " + (e as Error).message);
    } finally {
      setMaterializing(false);
    }
  };

  const handleApprove = async (id: number) => {
    await api.approveInferenceRule(id);
    await refresh();
  };

  const handleReject = async (id: number) => {
    await api.rejectInferenceRule(id);
    await refresh();
  };

  const handleSaveDepth = async () => {
    const parsed = parseInt(depthInput, 10);
    if (!Number.isFinite(parsed) || parsed < 1) {
      alert("Depth must be a positive integer.");
      return;
    }
    await api.setCompositionDepth(parsed);
    await refresh();
  };

  return (
    <section className="panel-grid single">
      <div className="panel">
        <h1>Inference Rules</h1>
        <p className="help-text">
          Path-level composition rules, proposed by one model and independently critiqued by another. Nothing here is
          ever auto-approved — a bad composition rule silently corrupts every inference derived from it, so a human
          must approve before it's used. Nothing here runs automatically either; every pass below is manually triggered.
        </p>

        <div style={{ display: "flex", gap: 12, alignItems: "flex-end", marginBottom: 24, padding: 16, background: "var(--bg-alt)", borderRadius: 8, border: "1px solid var(--border)", flexWrap: "wrap" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: "0.8rem", opacity: 0.8 }}>Max composition depth</label>
            <div style={{ display: "flex", gap: 4 }}>
              <input
                type="number"
                min={1}
                value={depthInput}
                onChange={e => setDepthInput(e.target.value)}
                style={{ padding: 4, width: 60 }}
              />
              <button onClick={handleSaveDepth} style={{ padding: "4px 8px", cursor: "pointer" }}>Save</button>
            </div>
          </div>

          <button onClick={handlePropose} disabled={proposing} style={{ padding: "4px 12px", cursor: proposing ? "not-allowed" : "pointer" }}>
            {proposing ? "Proposing..." : "Propose New Rules"}
          </button>
          <button onClick={handleMaterialize} disabled={materializing} style={{ padding: "4px 12px", cursor: materializing ? "not-allowed" : "pointer" }}>
            {materializing ? "Materializing..." : `Materialize Paths (depth ${depth})`}
          </button>
          <button onClick={refresh} style={{ padding: "4px 12px", opacity: 0.7 }}>Refresh</button>
        </div>

        {contradictions.length > 0 && (
          <div style={{ marginBottom: 24, padding: 16, background: "var(--bg-alt)", borderRadius: 8, border: "1px solid #b45309" }}>
            <h3 style={{ color: "#b45309", marginBottom: 8 }}>
              {contradictions.length} Unreviewed Contradiction{contradictions.length === 1 ? "" : "s"}
            </h3>
            <p className="help-text" style={{ marginBottom: 8 }}>
              An inferred claim conflicts with a directly asserted one. This may mean the asserted claim is a legitimate
              exception, not an error — these are flagged for review, never auto-resolved.
            </p>
            {contradictions.map((c: any) => (
              <div key={c.id} style={{ fontFamily: "monospace", fontSize: "0.85rem", marginBottom: 4 }}>
                Inferred claim #{c.id}: {c.predicate} — conflicts with claim #{c.contradicts_claim_id}
              </div>
            ))}
          </div>
        )}

        <h2 style={{ fontSize: "1rem", marginBottom: 8 }}>Awaiting Human Approval</h2>
        {rules.critiqued.length === 0 && <p className="muted">Nothing awaiting review.</p>}
        {rules.critiqued.map(rule => (
          <RuleCard key={rule.id} rule={rule} onApprove={handleApprove} onReject={handleReject} />
        ))}

        {rules.proposed.length > 0 && (
          <>
            <h2 style={{ fontSize: "1rem", marginBottom: 8, marginTop: 24 }}>Proposed (critique in progress)</h2>
            {rules.proposed.map(rule => (
              <RuleCard key={rule.id} rule={rule} />
            ))}
          </>
        )}

        {rules.approved.length > 0 && (
          <>
            <h2 style={{ fontSize: "1rem", marginBottom: 8, marginTop: 24 }}>Approved</h2>
            {rules.approved.map(rule => (
              <RuleCard key={rule.id} rule={rule} />
            ))}
          </>
        )}

        {rules.rejected.length > 0 && (
          <>
            <h2 style={{ fontSize: "1rem", marginBottom: 8, marginTop: 24, opacity: 0.6 }}>Rejected</h2>
            {rules.rejected.map(rule => (
              <RuleCard key={rule.id} rule={rule} />
            ))}
          </>
        )}
      </div>
    </section>
  );
}

export default InferenceRulesPanel;
