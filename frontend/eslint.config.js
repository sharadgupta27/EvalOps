import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "src/api/schema.d.ts"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/no-explicit-any": "error",
      // Components must use the generated client via hooks, never ad-hoc fetch.
      "no-restricted-globals": ["error", { name: "fetch", message: "Use src/api hooks." }],
    },
  },
  {
    files: ["src/api/client.ts", "**/*.test.{ts,tsx}"],
    rules: { "no-restricted-globals": "off" },
  },
);
