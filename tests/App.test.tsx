import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../frontend/src/App";

vi.mock("../frontend/src/components/DashboardPanel", () => ({ default: () => <div data-testid="panel-dashboard" /> }));
vi.mock("../frontend/src/components/DatabasePanel", () => ({ default: () => <div data-testid="panel-database" /> }));
vi.mock("../frontend/src/components/TheoriesPanel", () => ({ default: () => <div data-testid="panel-theories" /> }));
vi.mock("../frontend/src/components/settings/SettingsPanel", () => ({ default: () => <div data-testid="panel-settings" /> }));

describe("App", () => {
  it("renders brand title and subtitle", () => {
    render(<App />);
    expect(screen.getByText("OMNIVERSE 2")).toBeInTheDocument();
    expect(screen.getByText("LangGraph command center")).toBeInTheDocument();
  });

  it("shows all 4 nav buttons", () => {
    render(<App />);
    expect(screen.getByText("Command Center")).toBeInTheDocument();
    expect(screen.getByText("Tiers")).toBeInTheDocument();
    expect(screen.getByText("Theories")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("defaults to dashboard panel", () => {
    render(<App />);
    expect(screen.getByTestId("panel-dashboard")).toBeInTheDocument();
  });

  it("switches to database panel on Tiers click", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByText("Tiers"));
    expect(screen.getByTestId("panel-database")).toBeInTheDocument();
    expect(screen.queryByTestId("panel-dashboard")).not.toBeInTheDocument();
  });

  it("switches to settings panel on Settings click", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByText("Settings"));
    expect(screen.getByTestId("panel-settings")).toBeInTheDocument();
  });

  it("marks active nav button with active class", async () => {
    const user = userEvent.setup();
    render(<App />);
    const cmdBtn = screen.getByText("Command Center");
    expect(cmdBtn.closest("button")).toHaveClass("active");
    await user.click(screen.getByText("Theories"));
    expect(cmdBtn.closest("button")).not.toHaveClass("active");
    expect(screen.getByText("Theories").closest("button")).toHaveClass("active");
  });
});
