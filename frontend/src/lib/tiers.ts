import type { World } from "../types";

export function groupWorldsByTier(worlds: World[]) {
	const groups: Record<number, World[]> = {};

	worlds.forEach((world) => {
		const tier = world.tier ?? 11;
		if (!groups[tier]) groups[tier] = [];
		groups[tier].push(world);
	});

	return Object.entries(groups)
		.map(([tier, worlds]) => ({
			tier: parseInt(tier, 10),
			worlds,
		}))
		.sort((a, b) => a.tier - b.tier);
}
