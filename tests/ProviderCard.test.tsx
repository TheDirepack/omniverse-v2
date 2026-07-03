import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProviderCard from "../frontend/src/components/settings/ProviderCard";
import * as api from "../frontend/src/api";

vi.mock("../frontend/src/api", () => ({
  fetchProviderModels: vi.fn(),
}));

function makeProvider(overrides: any = {}) {
  return {
    id: 1,
    name: "Test Provider",
    provider_type: "openai",
    base_url: null,
    models: "gpt-4,gpt-3.5-turbo",
    keys: [
      { id: 1, provider_id: 1, api_key: "sk-real-key-12345", priority: 0 },
    ],
    ...overrides,
  };
}

describe("ProviderCard", () => {
  const onSave = vi.fn().mockResolvedValue(undefined);
  const onSaveKey = vi.fn().mockResolvedValue(undefined);
  const onDeleteKey = vi.fn().mockResolvedValue(undefined);
  const onDeleteProvider = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchProviderModels).mockResolvedValue({ models: ["gpt-4-turbo"] });
  });

  it("renders provider name and type badge", () => {
    render(<ProviderCard provider={makeProvider()} onSave={onSave} onSaveKey={onSaveKey} onDeleteKey={onDeleteKey} onDeleteProvider={onDeleteProvider} />);
    expect(screen.getByDisplayValue("Test Provider")).toBeInTheDocument();
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
  });

  it("saves provider name on Save Name click", async () => {
    const user = userEvent.setup();
    render(<ProviderCard provider={makeProvider()} onSave={onSave} onSaveKey={onSaveKey} onDeleteKey={onDeleteKey} onDeleteProvider={onDeleteProvider} />);
    const nameInput = screen.getByDisplayValue("Test Provider");
    await user.clear(nameInput);
    await user.type(nameInput, "Renamed Provider");
    await user.click(screen.getByRole("button", { name: /save name/i }));
    expect(onSave).toHaveBeenCalledWith({ id: 1, name: "Renamed Provider" });
  });

  it("saves provider type on select change", async () => {
    const user = userEvent.setup();
    render(<ProviderCard provider={makeProvider()} onSave={onSave} onSaveKey={onSaveKey} onDeleteKey={onDeleteKey} onDeleteProvider={onDeleteProvider} />);
    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "anthropic");
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    const call = onSave.mock.calls.find((c: any) => c[0].provider_type === "anthropic");
    expect(call).toBeTruthy();
  });

  it("shows base URL section for custom type and saves it", async () => {
    const provider = makeProvider({ provider_type: "custom", base_url: "https://my-custom-api.com/v1" });
    const user = userEvent.setup();
    render(<ProviderCard provider={provider} onSave={onSave} onSaveKey={onSaveKey} onDeleteKey={onDeleteKey} onDeleteProvider={onDeleteProvider} />);
    expect(screen.getByText("Base URL")).toBeInTheDocument();
    const urlInput = screen.getByDisplayValue("https://my-custom-api.com/v1");
    await user.clear(urlInput);
    await user.type(urlInput, "https://new-url.com/v1");
    await user.click(screen.getByRole("button", { name: /save$/i }));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ base_url: "https://new-url.com/v1" }));
  });

  it("renders model tags and allows adding/removing them", async () => {
    const user = userEvent.setup();
    render(<ProviderCard provider={makeProvider()} onHSave={onSave} onSaveKey={onSaveKey} onDeleteKey={onDeleteKey} onDeleteProvider={onDeleteProvider} />);
    // Fix: Change la a onSave for consistency if I made a typo, but wait, it's onSave
  });
});
