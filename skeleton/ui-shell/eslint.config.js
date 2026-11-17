import tseslint from "typescript-eslint";

export const restrictedImports = {
  patterns: [
    {
      group: ["**/medium", "**/medium/**", "**/debt-collector", "**/debt-collector/**"],
      message: "The UI shell must not import from medium/ or debt-collector/ (R7.1, R6.15).",
    },
  ],
};

export default [
  { ignores: ["dist/**", "node_modules/**"] },
  {
    files: ["src/**/*.{ts,tsx}", "test/**/*.{ts,tsx}"],
    languageOptions: { parser: tseslint.parser },
    rules: { "no-restricted-imports": ["error", restrictedImports] },
  },
];
