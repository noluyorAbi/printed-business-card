import next from "eslint-config-next";

const config = [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "public/**",
      "data/**",
      "test-results/**",
      "playwright-report/**",
    ],
  },
  ...next,
];

export default config;
