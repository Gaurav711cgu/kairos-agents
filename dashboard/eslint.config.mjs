import js from "@eslint/js";
import tseslint from "typescript-eslint";
import hooks from "eslint-plugin-react-hooks";
import a11y from "eslint-plugin-jsx-a11y";
import react from "eslint-plugin-react";
export default tseslint.config(
  {
    ignores: [
      ".next*/**",
      ".next-build/**",
      ".next-identity/**",
      ".next-reviewer005/**",
      ".playwright-results-reviewer/**",
      ".playwright-results-real/**",
      "out/**",
      "build/**",
      "next-env.d.ts",
      ".playwright-results/**",
      "playwright-report/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: { "react-hooks": hooks, "jsx-a11y": a11y, react },
    settings: { react: { version: "detect" } },
    languageOptions: {
      globals: {
        console: "readonly",
        process: "readonly",
        fetch: "readonly",
        URL: "readonly",
        Response: "readonly",
        Request: "readonly",
        AbortSignal: "readonly",
        crypto: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        sessionStorage: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        window: "readonly",
        document: "readonly",
        HTMLElement: "readonly",
        HTMLInputElement: "readonly",
        HTMLSelectElement: "readonly",
        HTMLButtonElement: "readonly",
        KeyboardEvent: "readonly",
        navigator: "readonly",
      },
    },
    rules: {
      ...hooks.configs.recommended.rules,
      ...a11y.flatConfigs.recommended.rules,
      // Captured source/output regions need keyboard focus for horizontal scrolling.
      "jsx-a11y/no-noninteractive-tabindex": ["error", { tags: ["pre"] }],
      "react/jsx-key": "error",
      "react/jsx-no-target-blank": "error",
      "react/no-unknown-property": "error",
    },
  },
);
