import { describe, it, expect } from "vitest";
import { groupWorldsByTier } from "../lib/tiers";

describe("groupWorldsByTier", () => {
  it("returns empty array for empty input", () => {
    expect(groupWorldsByTier([])).toEqual([]);
  });

  it("groups null tier under 11", () => {
    const worlds = [{ id: 1, name: "A", tier: null }];
    const result = groupWorldsByTier(worlds);
    expect(result).toHaveLength(1);
    expect(result[0].tier).toBe(11);
    expect(result[0].worlds).toHaveLength(1);
  });

  it("groups undefined tier under 11", () => {
    const worlds = [{ id: 1, name: "A", tier: undefined }];
    const result = groupWorldsByTier(worlds);
    expect(result[0].tier).toBe(11);
  });

  it("groups multiple tiers and sorts ascending", () => {
    const worlds = [
      { id: 1, name: "C", tier: 3 },
      { id: 2, name: "A", tier: 1 },
      { id: 3, name: "B", tier: 3 },
    ];
    const result = groupWorldsByTier(worlds);
    expect(result).toHaveLength(2);
    expect(result[0].tier).toBe(1);
    expect(result[0].worlds).toHaveLength(1);
    expect(result[0].worlds[0].name).toBe("A");
    expect(result[1].tier).toBe(3);
    expect(result[1].worlds).toHaveLength(2);
  });

  it("handles negative tier", () => {
    const worlds = [{ id: 1, name: "Negative", tier: -1 }];
    const result = groupWorldsByTier(worlds);
    expect(result[0].tier).toBe(-1);
  });

  it("handles tier zero", () => {
    const worlds = [{ id: 1, name: "Zero", tier: 0 }];
    const result = groupWorldsByTier(worlds);
    expect(result[0].tier).toBe(0);
  });

  it("handles missing tier field", () => {
    const worlds = [{ id: 1, name: "NoTierField" }];
    const result = groupWorldsByTier(worlds);
    expect(result[0].tier).toBe(11);
  });
});
