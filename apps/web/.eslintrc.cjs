module.exports = {
  root: true,
  env: { browser: true, node: true, es2022: true },
  parser: '@typescript-eslint/parser',
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module', ecmaFeatures: { jsx: true } },
  plugins: ['@typescript-eslint', 'react-hooks', '@next/next'],
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended', 'plugin:react-hooks/recommended', 'plugin:@next/next/core-web-vitals-legacy'],
  ignorePatterns: ['.next/', 'node_modules/', 'test-results/', 'playwright-report/', 'next-env.d.ts'],
  overrides: [{ files: ['*.ts', '*.tsx'], rules: { 'no-undef': 'off' } }]
};
