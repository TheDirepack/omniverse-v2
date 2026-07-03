import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RoutingCard from "../frontend/src/components/settings/RoutingCard";

const mockOnSave = vi.fn().mockResolvedValue({ id: 99 });
const mockOnDelete = vi.fn().mockResolvedValue(undefined);

const mockProviders = [
  { id: 1, name: "OpenAI", provider_type: "openai", base_url: null, models: "gpt-4,gpt-3.5-turbo", keys: [{ id: 1, provider_id: 1, api_key: "sk-...", priority: 0 }] },
  { id: 2, name: "Anthropic", provider_type: "anthropic", base_url: null, models: "claude-3-opus,claude-3-sonnet", keys: [{ id: 2, provider_id: 2, api_key: "sk-ant-...", priority: 0 }] },
];

const mockDefaultRoutes = [
  { id: 1, task_type: "DEFAULT", provider_id: 1, models: "gpt-4", priority: 0 },
];

describe("RoutingCard", () => {
  it("renders agent name and status text (DEFAULT)", () => {
    render(<RoutingCard agentName="DEFAULT" routes={mockDefaultRoutes} providers={mockProviders} onSave={mockOnSave} onDelete={mockOnDelete} />);
    expect(screen.getByText("DEFAULT")).toBeInTheDocument();
    expect(screen.getByText("1 step(s)")).toBeInTheDocument();
  });

  it("renders agent name and status text for non-DEFAULT with no custom routes", () => {
    render(
      <RoutingCard agentName="Researcher" routes={[]} providers={mockProviders} onSave={mockOnSave} onDelete={mockOnDelete} defaultRoutes={mockDefaultRoutes} />
    );
    expect(screen.getByText("Researcher")).toBeInTheDocument();
    expect(screen.getByText(/Using DEFAULT \(1 step\(s\)\)/)).toBeInTheDocument();
  });

  it("expands and collapses on header click", async () => {
    const user = userEvent.setup();
    render(<RoutingCard agentName="DEFAULT" routes={mockDefaultRoutes} providers={mockProviders} onSave={mockOnSave} onDelete={mockOnDelete} />);
    expect(screen.getByText("Resolved Fallback Order:")).toBeInTheDocument();
    await user.click(screen.getByText("DEFAULT").closest("div")!);
    expect(screen.queryByText("Resolved Fallback Order:")).not.toBeInTheDocument();
  });

  it("shows resolved fallback order when expanded", () => {
    render(<RoutingCard agentName="DEFAULT" routes={mockDefaultRoutes} providers={mockProviders} onSave={mockOnSave} onDelete={mockOnDelete} />);
    expect(screen.getByText("Resolved Fallback Order:")).toBeInTheDocument();
    expect(screen.getByText(/OpenAI.*Key 1.*gpt-4/)).toBeInTheDocument();
  });

  it("shows provider select in route slot", () => {
    render(<RoutingCard agentName="DEFAULT" routes={mockDefaultRoutes} providers={mockProviders} onSave={mockOnSave} onDelete={mockOnDelete} />);
    expect(screen.getAllByRole("combobox")[0]).toBeInTheDocument();
  });

  it("calls onSave with updated route when Save is clicked", async () => {
    const user = userEvent.setup();
    render(<RoutingCard agentName="DEFAULT" routes={mockDefaultRoutes} providers={mockProviders} onSave={mockOnSave} onDelete={mockOnDelete} />);
    const saveBtn = screen.getByRole("button", { name: /save/i });
    await user.click(saveBtn);
    expect(mockOnSave).toHaveBeenCalledWith(mockDefaultRoutes[0]);
  });

  it("calls onDelete when delete button is clicked", async () => {
    const user = userEvent.setup();
    render(<RoutingCard agentName="DEFAULT" routes={mockDefaultRoutes} providers={mockProviders} onSave={mockOnSave} onDelete={mockOnDelete} />);
    const deleteBtn = screen.getByRole("button", { name: "×" });
    await user.click(deleteBtn);
    expect(mockOnDelete).toHaveBeenCalledWith(1);
  });

  it("shows Override button for non-DEFAULT agents without custom routes", () => {
    render(
      <RoutingCard agentName="Researcher" routes={[]} providers={mockProviders} onSave={mockOnSave} onDelete={mockOnDelete} defaultRoutes={mockDefaultRoutes} />
    );
    expect(screen.getByRole("button", { name: /override/i })).toBeInTheDocument();
  });

  it("calls onSave for each default route when Override is clicked", async () => {
    const user = userEvent.setup();
    mockOnSave.mockClear();
    render(
      <RoutingCard agentName="Researcher" routes={[]} providers={mockProviders} onSave={mockOnSave} onDelete={mockOnDelete} defaultRoutes={mockDefaultRoutes} />
    );
    await user.click(screen.getByRole("button", { name: /override/i }));
    expect(mockOnSave).toHaveBeenCalledWith(
      expect.objectContaining({ task_type: "Researcher", provider_id: 1, models: "gpt-4" })
    );
  });
});
