import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SettingItem from "../frontend/src/components/settings/SettingItem";

describe("SettingItem", () => {
  const onSave = vi.fn().mockResolvedValue(undefined);
  const onDelete = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders key name and value input", () => {
    render(<SettingItem keyName="TEST_KEY" value="test_value" onSave={onSave} onDelete={onDelete} />);
    expect(screen.getByText("TEST_KEY")).toBeInTheDocument();
    expect(screen.getByDisplayValue("test_value")).toBeInTheDocument();
  });

  it("calls onSave with updated value when Save clicked", async () => {
    const user = userEvent.setup();
    render(<SettingItem keyName="TEST_KEY" value="old_value" onSave={onSave} onDelete={onDelete} />);
    const input = screen.getByDisplayValue("old_value");
    await user.clear(input);
    await user.type(input, "new_value");
    await user.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith("TEST_KEY", "new_value");
  });

  it("shows confirm delete and calls onDelete on Confirm", async () => {
    const user = userEvent.setup();
    render(<SettingItem keyName="TEST_KEY" value="v" onSave={onSave} onDelete={onDelete} />);
    await user.click(screen.getByRole("button", { name: "×" }));
    expect(screen.getByRole("button", { name: /confirm/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /confirm/i }));
    expect(onDelete).toHaveBeenCalledWith("TEST_KEY");
  });

  it("cancels delete when Cancel is clicked", async () => {
    const user = userEvent.setup();
    render(<SettingItem keyName="TEST_KEY" value="v" onSave={onSave} onDelete={onDelete} />);
    await user.click(screen.getByRole("button", { name: "×" }));
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /confirm/i })).not.toBeInTheDocument();
  });
});
