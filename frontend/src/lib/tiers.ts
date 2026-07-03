export function groupWorldsByTier(worlds: any[]) {
  const groups: Record<number, any[]> = {};
  
  worlds.forEach(world => {
    const tier = world.tier ?? 11;
    if (!groups[tier]) groups[tier] = [];
    groups[tier].push(world);
  });

  return Object.entries(groups)
    .map(([tier, worlds]) => ({
      tier: parseInt(tier),
      worlds
    }))
    .sort((a, b) => a.tier - b.tier);
}
