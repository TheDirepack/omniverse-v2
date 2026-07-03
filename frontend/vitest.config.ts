import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");

export default defineConfig({
  plugins: [react()],
  root: projectRoot,
  resolve: {
    alias: {
      "react": resolve(projectRoot, "frontend/node_modules/react"),
      "react-dom": resolve(projectRoot, "frontend/node_modules/react-dom"),
      "@testing-library/react": resolve(projectRoot, "frontend/node_modules/@testing-library/react"),
      "@testing-library/user-event": resolve(projectRoot, "frontend/node_modules/@testing-library/user-event"),
      "@testing-library/jest-dom": resolve(projectRoot, "frontend/node_modules/@testing-library/jest-dom"),
    },
    modules: [resolve(projectRoot, "frontend/node_modules"), "node_modules"],
  },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    root: projectRoot,
    setupFiles: [resolve(projectRoot, "tests/setup.ts")],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      include: ["frontend/src/**/*.{ts,tsx}"],
      exclude: ["frontend/src/main.tsx", "frontend/src/**/*.d.ts"],
      thresholds: {
        lines: 60,
        branches: 55,
        functions: 60,
        statements: 60,
      },
    },
  },
  server: {
    fs: {
      strict: false,
      allow: [projectRoot],
    },
  },
});