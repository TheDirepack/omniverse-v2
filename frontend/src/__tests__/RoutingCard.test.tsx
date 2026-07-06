import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RoutingCard from "../components/settings/RoutingCard";

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

  it("shows select provider option and hides model selector when provider_id is null", () => {
    const routesWithNull = [{ id: 1, task_type: "DEFAULT", provider_id: null, models: null, priority: 0 }];
    render(<RoutingCard agentName="DEFAULT" routes={routesWithNull} providers={mockProviders} onSave={mockOnSave} onDelete={mockOnDelete} />);
    const selects = screen.getAllByRole("combobox");
    expect(selects).toHaveLength(1); // Only provider select is rendered
    expect(selects[0]).toHaveValue(""); // Empty value / "Select Provider"
  });

  it("populates model selector with options from the selected provider models", async () => {
    const user = userEvent.setup();
    const routesWithNull = [{ id: 1, task_type: "DEFAULT", provider_id: null, models: null, priority: 0 }];
    render(<RoutingCard agentName="DEFAULT" routes={routesWithNull} providers={mockProviders} onSave={mockOnSave} onDelete={mockOnDelete} />);
    
    // Select first provider (OpenAI, which has gpt-4 and gpt-3.5-turbo)
    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "1");

    // Model select should be displayed
    await waitFor(() => expect(screen.getAllByRole("combobox")).toHaveLength(2));
    const modelSelect = screen.getAllByRole("combobox")[1];
    expect(modelSelect).toBeInTheDocument();
    
    // Check that models are in the options list
    const options = within(modelSelect).getAllByRole("option");
    const optionValues = options.map(opt => opt.getAttribute("value"));
    expect(optionValues).toContain("gpt-4");
    expect(optionValues).toContain("gpt-3.5-turbo");
  });

  it("calls onSave to add a new slot when + Add Provider Step is clicked", async () => {
    const user = userEvent.setup();
    mockOnSave.mockClear();
    mockOnSave.mockResolvedValue({ id: 100, task_type: "DEFAULT", provider_id: null, models: null, priority: 1 });
    render(<RoutingCard agentName="DEFAULT" routes={mockDefaultRoutes} providers={mockProviders} onSave={mockOnSave} onDelete={mockOnDelete} />);
    
    await user.click(screen.getByRole("button", { name: /\+ add provider step/i }));
    expect(mockOnSave).toHaveBeenCalledWith({ id: 0, task_type: "DEFAULT", provider_id: null, models: null, priority: 1 });
    // Verify slot list expands
    await waitFor(() => expect(screen.getAllByRole("combobox")).toHaveLength(3)); // 2 for slot 1 (provider+model), 1 for new slot (provider only)
  });
});
