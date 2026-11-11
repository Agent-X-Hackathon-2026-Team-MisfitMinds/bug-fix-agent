import type { Config } from 'tailwindcss';
export default { content: ['./src/app/**/*.{ts,tsx}', './src/components/**/*.{ts,tsx}'], theme: { extend: { colors: { brand: 'var(--ds-brand)', surface: 'var(--ds-surface)', ink: 'var(--ds-text-primary)' } } }, plugins: [] } satisfies Config;
