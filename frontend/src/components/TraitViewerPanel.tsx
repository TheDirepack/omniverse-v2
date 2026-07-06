import { useEffect, useMemo, useState } from "react";
import * as api from "../api";
import type { Claim, Trait, World } from "../types";

function TraitRow({ world, traits }: { world: World; traits: Trait[] }) {
	return (
		<div
			style={{
				display: "flex",
				gap: 16,
				padding: "12px",
				background: "#1e293b",
				borderRadius: 8,
				border: "1px solid #334155",
				marginBottom: 12,
				alignItems: "center",
			}}
		>
			<div style={{ minWidth: 150, fontWeight: 600, color: "#f1f5f9" }}>
				{world.name}
			</div>
			<div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
				{traits.map((t) => (
					<div
						key={t.id}
						style={{
							padding: "2px 8px",
							background: "#0f172a",
							borderRadius: 4,
							border: "1px solid #475569",
							fontSize: "0.8rem",
							display: "flex",
							gap: 6,
						}}
					>
						<span style={{ color: "#94a3b8" }}>{t.name}:</span>
						<span style={{ color: "#cbd5e1" }}>{t.value}</span>
					</div>
				))}
			</div>
		</div>
	);
}

function ClaimRow({ world, claims }: { world: World; claims: Claim[] }) {
	return (
		<div
			style={{
				display: "flex",
				flexDirection: "column",
				gap: 8,
				padding: "12px",
				background: "#1e293b",
				borderRadius: 8,
				border: "1px solid #334155",
				marginBottom: 12,
			}}
		>
			<div style={{ fontWeight: 600, color: "#f1f5f9", marginBottom: 4 }}>
				{world.name}
			</div>
			<div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
				{claims.map((c) => (
					<div
						key={c.id}
						style={{
							padding: "4px 8px",
							background: "#0f172a",
							borderRadius: 4,
							border: "1px solid #475569",
							fontSize: "0.8rem",
							display: "flex",
							alignItems: "center",
							gap: 6,
						}}
					>
						<span style={{ color: "#94a3b8" }}>{c.predicate}</span>
						<span style={{ color: "#64748b" }}>→</span>
						<span style={{ color: "#cbd5e1" }}>
							{c.object_literal ?? "Entity ID: " + c.object_entity_id}
						</span>

						<span
							style={{
								fontSize: "0.7rem",
								padding: "0 4px",
								background: "#334155",
								borderRadius: 3,
								color: "#94a3b8",
							}}
						>
							{c.support_count}
						</span>
					</div>
				))}
			</div>
		</div>
	);
}

export default function TraitViewerPanel() {
	const [worlds, setWorlds] = useState<World[]>([]);
	const [traits, setTraits] = useState<Trait[]>([]);
	const [claims, setClaims] = useState<Claim[]>([]);
	const [viewMode, setViewMode] = useState<"traits" | "claims">("traits");
	const [filterOnlyWithData, setFilterOnlyWithData] = useState(false);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		async function load() {
			try {
				const [results, allTraits, allClaims] = await Promise.all([
					api.fetchResults(),
					api.fetchTraits(),
					api.fetchClaims(),
				]);
				setWorlds(results.worlds);
				setTraits(allTraits);
				setClaims(allClaims);
			} catch (e) {
				console.error(e);
			} finally {
				setLoading(false);
			}
		}
		load();
	}, []);

	const worldsWithData = useMemo(() => {
		return worlds
			.map((w) => ({
				world: w,
				worldTraits: traits.filter((t) => t.universe_id === w.id),
				worldClaims: claims.filter((c) => c.universe_scope === w.id),
			}))
			.filter((item) => {
				if (!filterOnlyWithData) return true;
				return item.worldTraits.length > 0 || item.worldClaims.length > 0;
			});
	}, [worlds, traits, claims, filterOnlyWithData]);

	if (loading)
		return (
			<div className="muted" style={{ padding: 24 }}>
				Loading database...
			</div>
		);

	return (
		<section className="panel-grid single">
			<div className="panel">
				<div
					style={{
						display: "flex",
						justifyContent: "space-between",
						alignItems: "center",
						marginBottom: 24,
					}}
				>
					<div style={{ display: "flex", gap: 12, alignItems: "center" }}>
						<h1>Main Database</h1>
						<div
							style={{
								display: "flex",
								background: "#0f172a",
								padding: 4,
								borderRadius: 6,
								border: "1px solid #334155",
							}}
						>
							<button
								className={viewMode === "traits" ? "chip active" : "chip"}
								onClick={() => setViewMode("traits")}
								style={{
									border: "none",
									background: "none",
									cursor: "pointer",
								}}
							>
								Traits
							</button>
							<button
								className={viewMode === "claims" ? "chip active" : "chip"}
								onClick={() => setViewMode("claims")}
								style={{
									border: "none",
									background: "none",
									cursor: "pointer",
								}}
							>
								Claims
							</button>
						</div>
					</div>
					<label
						style={{
							display: "flex",
							alignItems: "center",
							gap: 8,
							cursor: "pointer",
							fontSize: "0.9rem",
							color: "#94a3b8",
						}}
					>
						<input
							type="checkbox"
							checked={filterOnlyWithData}
							onChange={(e) => setFilterOnlyWithData(e.target.checked)}
						/>
						Only worlds with data
					</label>
				</div>

				<div style={{ display: "flex", flexDirection: "column" }}>
					{worldsWithData.length > 0 ? (
						worldsWithData.map(({ world, worldTraits, worldClaims }) =>
							viewMode === "traits" ? (
								<TraitRow key={world.id} world={world} traits={worldTraits} />
							) : (
								<ClaimRow key={world.id} world={world} claims={worldClaims} />
							),
						)
					) : (
						<p className="muted">
							No worlds found matching the current filter.
						</p>
					)}
				</div>
			</div>
		</section>
	);
}
