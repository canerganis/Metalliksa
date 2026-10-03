import tseslint from "typescript-eslint";

const warningConfigs = tseslint.configs.recommended.map((config) => ({
  ...config,
  rules: Object.fromEntries(
    Object.entries(config.rules ?? {}).map(([rule, setting]) => [
      rule,
      Array.isArray(setting) ? ["warn", ...setting.slice(1)] : "warn",
    ]),
  ),
}));

export default tseslint.config(
  { ignores: ["node_modules/**", "dist/**", "graft/**"] },
  ...warningConfigs,
  {
    files: ["src/**/*.{ts,tsx}", "server.ts", "routes/**/*.ts", "server/**/*.ts", "tests/**/*.{ts,tsx}"],
    rules: {
      "no-undef": "off",
      "no-unused-vars": "off",
    },
  },
);
