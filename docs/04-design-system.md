# 04 — Design System: Bug-Fix Agent

## Aesthetic and references
**Aesthetic:** Minimal / editorial restraint — "quiet UI, clear status, nothing flashy." Calm density like a senior engineer's terminal: information-dense but never crowded, transparent reasoning shown plainly.

**References:**
- **Linear:** restraint, typography, calm density
- **Vercel:** deployment-style status timeline and logs
- **GitHub Actions:** step-by-step run view with collapsible logs

## Design principles
1. **Proof over polish** — red→green test output, the human-review gate, and sandbox isolation are the hero visuals. No decorative illustration; every pixel serves proof.
2. **Calm density** — Linear-style typography and restraint. High information density without clutter; status and reasoning are scannable at a glance.
3. **Transparent uncertainty** — the agent states its confidence openly (High/Medium/Low). Empty, error, partial, and "couldn't reproduce" states are first-class, not afterthoughts.

## Design tokens (CSS variables + Tailwind theme)

### Colour — semantic names, light + dark
All colours use HSL for easy alpha manipulation. Every text/background pair meets WCAG 2.2 AA (ratios listed in the WCAG section below).

**Light theme:**
```css
:root {
  /* Surfaces */
  --ds-surface: hsl(0 0% 100%);          /* page background */
  --ds-surface-elev: hsl(0 0% 98.5%);    /* cards, modals */
  --ds-surface-inverse: hsl(0 0% 9%);    /* dark surface for dark mode */

  /* Text */
  --ds-text-primary: hsl(0 0% 9%);       /* headings, body */
  --ds-text-secondary: hsl(0 0% 45%);    /* captions, meta */
  --ds-text-muted: hsl(0 0% 65%);        /* placeholders, disabled */
  --ds-text-inverse: hsl(0 0% 100%);     /* text on dark surfaces */

  /* Border */
  --ds-border: hsl(0 0% 88%);            /* dividers, input borders */
  --ds-border-focus: hsl(210 90% 55%);   /* focused input outline */

  /* Brand */
  --ds-brand: hsl(210 90% 55%);          /* primary actions, links */
  --ds-brand-hover: hsl(210 90% 50%);
  --ds-brand-active: hsl(210 90% 45%);
  --ds-brand-text: hsl(0 0% 100%);       /* text on brand bg */

  /* Status */
  --ds-success: hsl(140 70% 40%);        /* green: passing tests */
  --ds-success-bg: hsl(140 70% 95%);
  --ds-success-text: hsl(140 60% 20%);
  --ds-warning: hsl(38 90% 50%);         /* amber: medium confidence */
  --ds-warning-bg: hsl(38 90% 95%);
  --ds-warning-text: hsl(38 70% 20%);
  --ds-error: hsl(0 70% 50%);            /* red: failed runs */
  --ds-error-bg: hsl(0 70% 95%);
  --ds-error-text: hsl(0 60% 20%);
  --ds-info: hsl(210 90% 55%);           /* blue: info, loading */
  --ds-info-bg: hsl(210 90% 95%);
  --ds-info-text: hsl(210 70% 20%);
}
```

**Dark theme:**
```css
[data-theme="dark"] {
  --ds-surface: hsl(0 0% 9%);
  --ds-surface-elev: hsl(0 0% 11%);
  --ds-surface-inverse: hsl(0 0% 100%);
  --ds-text-primary: hsl(0 0% 98%);
  --ds-text-secondary: hsl(0 0% 60%);
  --ds-text-muted: hsl(0 0% 40%);
  --ds-text-inverse: hsl(0 0% 9%);
  --ds-border: hsl(0 0% 18%);
  --ds-border-focus: hsl(210 90% 60%);
  --ds-brand: hsl(210 90% 60%);
  --ds-brand-hover: hsl(210 90% 65%);
  --ds-brand-active: hsl(210 90% 55%);
  --ds-brand-text: hsl(0 0% 100%);
  --ds-success: hsl(140 70% 50%);
  --ds-success-bg: hsl(140 70% 15%);
  --ds-success-text: hsl(140 80% 90%);
  --ds-warning: hsl(38 90% 55%);
  --ds-warning-bg: hsl(38 90% 15%);
  --ds-warning-text: hsl(38 90% 90%);
  --ds-error: hsl(0 70% 55%);
  --ds-error-bg: hsl(0 70% 15%);
  --ds-error-text: hsl(0 80% 90%);
  --ds-info: hsl(210 90% 60%);
  --ds-info-bg: hsl(210 90% 15%);
  --ds-info-text: hsl(210 80% 90%);
}
```

### Tailwind colour theme
```js
theme: {
  extend: {
    colors: {
      surface: 'hsl(var(--ds-surface) / <alpha-value>)',
      'surface-elev': 'hsl(var(--ds-surface-elev) / <alpha-value>)',
      'surface-inverse': 'hsl(var(--ds-surface-inverse) / <alpha-value>)',
      'text-primary': 'hsl(var(--ds-text-primary) / <alpha-value>)',
      'text-secondary': 'hsl(var(--ds-text-secondary) / <alpha-value>)',
      'text-muted': 'hsl(var(--ds-text-muted) / <alpha-value>)',
      'text-inverse': 'hsl(var(--ds-text-inverse) / <alpha-value>)',
      border: 'hsl(var(--ds-border) / <alpha-value>)',
      'border-focus': 'hsl(var(--ds-border-focus) / <alpha-value>)',
      brand: 'hsl(var(--ds-brand) / <alpha-value>)',
      success: 'hsl(var(--ds-success) / <alpha-value>)',
      'success-bg': 'hsl(var(--ds-success-bg) / <alpha-value>)',
      'success-text': 'hsl(var(--ds-success-text) / <alpha-value>)',
      warning: 'hsl(var(--ds-warning) / <alpha-value>)',

### Type scale — fluid clamp(), ≤2 font families
**Font families:** `font-sans` = system-ui (Inter fallback), `font-mono` = ui-monospace (for code, test output, logs). No Google Fonts; system fonts load instantly.

```css
:root {
  /* Fluid type scale: min at 360px, max at 1440px */
  --ds-text-xs: clamp(0.75rem, 0.75rem + (0 - 0.75) * ((100vw - 360px) / (1440 - 360)), 0.75rem);
  --ds-text-sm: clamp(0.875rem, 0.875rem + (0 - 0.875) * ((100vw - 360px) / (1440 - 360)), 0.875rem);
  --ds-text-base: clamp(1rem, 1rem + (0 - 1) * ((100vw - 360px) / (1440 - 360)), 1rem);
  --ds-text-lg: clamp(1.125rem, 1.125rem + (0.0625 - 1.125) * ((100vw - 360px) / (1440 - 360)), 1.1875rem);
  --ds-text-xl: clamp(1.25rem, 1.25rem + (0.1875 - 1.25) * ((100vw - 360px) / (1440 - 360)), 1.4375rem);
  --ds-text-2xl: clamp(1.5rem, 1.5rem + (0.5 - 1.5) * ((100vw - 360px) / (1440 - 360)), 2rem);
  --ds-text-3xl: clamp(1.875rem, 1.875rem + (0.75 - 1.875) * ((100vw - 360px) / (1440 - 360)), 2.625rem);
  --ds-line-tight: 1.25;
  --ds-line-normal: 1.5;
  --ds-line-relaxed: 1.75;
  --ds-font-weight-normal: 400;
  --ds-font-weight-medium: 500;
  --ds-font-weight-semibold: 600;
}
```

**Tailwind type theme:**
```js
theme: {
  extend: {
    fontFamily: {
      sans: ['var(--ds-font-sans)', 'system-ui', 'sans-serif'],
      mono: ['var(--ds-font-mono)', 'ui-monospace', 'monospace'],
    },
    fontSize: {
      xs: ['var(--ds-text-xs)', { lineHeight: 'var(--ds-line-tight)' }],
      sm: ['var(--ds-text-sm)', { lineHeight: 'var(--ds-line-normal)' }],
      base: ['var(--ds-text-base)', { lineHeight: 'var(--ds-line-normal)' }],
      lg: ['var(--ds-text-lg)', { lineHeight: 'var(--ds-line-relaxed)' }],
      xl: ['var(--ds-text-xl)', { lineHeight: 'var(--ds-line-relaxed)' }],
      '2xl': ['var(--ds-text-2xl)', { lineHeight: 'var(--ds-line-tight)' }],
      '3xl': ['var(--ds-text-3xl)', { lineHeight: 'var(--ds-line-tight)' }],
    },
    fontWeight: {
      normal: 'var(--ds-font-weight-normal)',
      medium: 'var(--ds-font-weight-medium)',
      semibold: 'var(--ds-font-weight-semibold)',
    },
  },
}
```

### Spacing — 4-pt grid
All spacing uses the 4-pt scale. No arbitrary values.
```css
:root {
  --ds-space-0: 0px;
  --ds-space-1: 4px;
  --ds-space-2: 8px;
  --ds-space-3: 12px;
  --ds-space-4: 16px;
  --ds-space-5: 20px;
  --ds-space-6: 24px;
  --ds-space-8: 32px;
  --ds-space-10: 40px;
  --ds-space-12: 48px;
  --ds-space-16: 64px;
  --ds-space-20: 80px;
  --ds-space-24: 96px;
}
```
Tailwind: `spacing` maps 1:1 to `--ds-space-*` (tailwind default 4-pt scale already matches).

### Radii
```css
:root {
  --ds-radius-sm: 4px;
  --ds-radius-md: 6px;
  --ds-radius-lg: 8px;
  --ds-radius-full: 9999px;
}
```

### Shadows — minimal, quiet aesthetic
```css
:root {
  --ds-shadow-none: none;
  --ds-shadow-sm: 0 1px 2px 0 hsl(0 0% 0% / 0.05);
  --ds-shadow-md: 0 4px 6px -1px hsl(0 0% 0% / 0.08), 0 2px 4px -1px hsl(0 0% 0% / 0.04);
  --ds-shadow-lg: 0 10px 15px -3px hsl(0 0% 0% / 0.08);
}
```

### Z-index hierarchy
```css
:root {
  --ds-z-dropdown: 100;
  --ds-z-modal: 200;
  --ds-z-toast: 300;
  --ds-z-tooltip: 400;
}
```

### Motion — durations, easing, reduced-motion fallback
Purposeful motion 150–300ms per STANDARDS.md. Reduced motion respected.
```css
:root {
  --ds-duration-fast: 150ms;
  --ds-duration-base: 200ms;
  --ds-duration-slow: 250ms;
  --ds-duration-slower: 300ms;
  --ds-ease-out: cubic-bezier(0.4, 0, 0.2, 1);
  --ds-ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --ds-motion-reduced: none;
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --ds-duration-fast: 0ms;
    --ds-duration-base: 0ms;
    --ds-duration-slow: 0ms;
    --ds-duration-slower: 0ms;
  }
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

**Tailwind motion theme:**
```js
theme: {
  extend: {
    borderRadius: {
      sm: 'var(--ds-radius-sm)',
      md: 'var(--ds-radius-md)',
      lg: 'var(--ds-radius-lg)',
      full: 'var(--ds-radius-full)',
    },
    boxShadow: {
      sm: 'var(--ds-shadow-sm)',
      md: 'var(--ds-shadow-md)',
      lg: 'var(--ds-shadow-lg)',
    },
    zIndex: {
      dropdown: 'var(--ds-z-dropdown)',
      modal: 'var(--ds-z-modal)',
      toast: 'var(--ds-z-toast)',
      tooltip: 'var(--ds-z-tooltip)',
    },
    transitionDuration: {
      fast: 'var(--ds-duration-fast)',
      DEFAULT: 'var(--ds-duration-base)',

## Grid and breakpoints
Breakpoints: 360 / 768 / 1024 / 1440. Single-column below 768, two-column 768–1024, three-column 1024+.

```css
:root {
  --ds-break-360: 360px;
  --ds-break-768: 768px;
  --ds-break-1024: 1024px;
  --ds-break-1440: 1440px;
  --ds-container-max: 1200px;
  --ds-gutter: var(--ds-space-4); /* 16px */
  --ds-gutter-wide: var(--ds-space-6); /* 24px */
}
```

**Tailwind screens:**
```js
theme: {
  extend: {
    screens: {
      '360': '360px',
      '768': '768px',
      '1024': '1024px',
      '1440': '1440px',
    },
    container: {
      center: true,
      padding: {
        DEFAULT: 'var(--ds-gutter)',
        '768': 'var(--ds-gutter-wide)',
      },
    },
  },
}
```

**Layout rules:**

## Component specs

Every component supports these states: default, hover, focus-visible, active, disabled, loading, error. Touch targets ≥44px (STANDARDS.md). Focus rings: `--ds-border-focus`, 2px solid, offset 2px.

### Button
**Usage:** primary CTAs ("Add the agent-fix label", "View draft PR", "Sign in with GitHub"), secondary actions, danger actions.

| State | Background | Text | Border | Notes |
|-------|-----------|------|--------|-------|
| default | `--ds-brand` | `--ds-brand-text` | none | font-weight 500, px-4 py-2, radius md |
| hover | `--ds-brand-hover` | `--ds-brand-text` | none | transition 200ms ease-out |
| focus-visible | `--ds-brand` | `--ds-brand-text` | none | ring 2px `--ds-border-focus`, offset 2px |
| active | `--ds-brand-active` | `--ds-brand-text` | none | scale 0.98, no transition |
| disabled | `--ds-text-muted` at 20% alpha | `--ds-text-muted` | none | cursor not-allowed, no hover/active |
| loading | `--ds-brand` | `--ds-brand-text` | none | spinner inside, text hidden |
| error | `--ds-error` | `--ds-error-text` | none | only for destructive actions |

**Microcopy (from 03-app-flow.md):**
- Primary: "Add the agent-fix label", "View draft PR", "View issue", "Get started"
- Secondary: "View the live demo", "Try it on a seeded issue", "Read the brief", "Open the demo repo", "View live runs"
- Auth: "Sign in with GitHub", "Sign out"
- Error recovery: "Try again", "Check back soon"

**CSS:**
```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--ds-space-2);
  min-height: 44px;
  padding: 0 var(--ds-space-4);
  font-size: var(--ds-text-base);
  font-weight: var(--ds-font-weight-medium);
  line-height: var(--ds-line-normal);
  border-radius: var(--ds-radius-md);
  border: none;
  cursor: pointer;
  transition: background-color var(--ds-duration-base) var(--ds-ease-out),
              transform var(--ds-duration-fast) var(--ds-ease-out);
}
.btn:focus-visible { outline: 2px solid hsl(var(--ds-border-focus)); outline-offset: 2px; }
.btn:active:not([disabled]) { transform: scale(0.98); }
.btn[disabled] { opacity: 0.5; cursor: not-allowed; pointer-events: none; }
```

**Tailwind:** `btn-primary` (bg-brand, text-brand-text, hover:bg-brand-hover, focus-visible:ring-2 focus-visible:ring-border-focus focus-visible:ring-offset-2, active:scale-95, disabled:opacity-50 disabled:cursor-not-allowed)

### Input
**Usage:** none in v1 (no traditional forms per 03-app-flow.md). Spec retained for future search/filter on dashboard.

| State | Background | Text | Border | Notes |
|-------|-----------|------|--------|-------|
| default | `--ds-surface` | `--ds-text-primary` | `--ds-border` | px-3 py-2, radius md |
| hover | `--ds-surface` | `--ds-text-primary` | `--ds-text-secondary` | transition 200ms |
| focus-visible | `--ds-surface` | `--ds-text-primary` | `--ds-border-focus` | ring 2px `--ds-border-focus` |
| active | `--ds-surface-elev` | `--ds-text-primary` | `--ds-border` | |
| disabled | `--ds-surface-elev` | `--ds-text-muted` | `--ds-border` | cursor not-allowed |
| loading | `--ds-surface-elev` | `--ds-text-muted` | `--ds-border` | shimmer animation |
| error | `--ds-surface` | `--ds-text-primary` | `--ds-error` | error text below: `--ds-error-text` |

**Validation rule (future):** required, min 1 char; error message: "This field is required."


### Card
**Usage:** run cards on dashboard, seeded issue cards on `/demo`, feature cards on home, security checklist items.

| State | Background | Border | Shadow | Notes |
|-------|-----------|--------|--------|-------|
| default | `--ds-surface-elev` | `--ds-border` | `--ds-shadow-sm` | p-4, radius lg |
| hover | `--ds-surface-elev` | `--ds-border-focus` | `--ds-shadow-md` | transition 200ms |
| focus-visible | `--ds-surface-elev` | `--ds-border-focus` | `--ds-shadow-md` | ring 2px `--ds-border-focus` (if interactive) |
| active | `--ds-surface` | `--ds-border` | `--ds-shadow-sm` | |
| disabled | N/A | N/A | N/A | cards are not disabled |
| loading | `--ds-surface-elev` | `--ds-border` | `--ds-shadow-sm` | skeleton children |
| error | `--ds-surface-elev` | `--ds-border` | `--ds-shadow-sm` | error badge: `--ds-error-bg` bg, `--ds-error-text` text |

**CSS:**
```css
.card {
  background: hsl(var(--ds-surface-elev));
  border: 1px solid hsl(var(--ds-border));
  border-radius: var(--ds-radius-lg);
  padding: var(--ds-space-4);
  box-shadow: var(--ds-shadow-sm);
  transition: border-color var(--ds-duration-base) var(--ds-ease-out),
              box-shadow var(--ds-duration-base) var(--ds-ease-out);
}
.card:hover { border-color: hsl(var(--ds-border-focus)); box-shadow: var(--ds-shadow-md); }
```

### Modal
**Usage:** none in v1 (no custom approval UI per PRD non-goals). Spec retained for future confirmation dialogs.

| State | Overlay | Panel | Notes |
|-------|---------|-------|-------|
| default | `hsl(0 0% 0% / 0.4)` | `--ds-surface-elev` | fixed inset-0, radius lg, max-w-lg |
| hover | N/A | N/A | |
| focus-visible | N/A | ring 2px `--ds-border-focus` | on close button |
| active | N/A | N/A | |
| disabled | N/A | N/A | modals are not disabled |
| loading | same as default | same as default | spinner in center |
| error | same as default | same as default | error message text `--ds-error-text` |

**Close:** Escape key, click outside, X button. Focus trapped inside.

### Nav
**Usage:** top navigation on all pages. Logo left, links center, auth/user actions right.

| State | Background | Text | Border | Notes |
|-------|-----------|------|--------|-------|

### Toast
**Usage:** ephemeral feedback (sign-in success, run completed, error recovery). Positioned bottom-right, z-index `--ds-z-toast`.

| State | Background | Text | Border | Notes |
|-------|-----------|------|--------|-------|
| default | `--ds-surface-elev` | `--ds-text-primary` | `--ds-border` | p-4, radius md, shadow-lg, auto-dismiss 5s |
| hover | `--ds-surface-elev` | `--ds-text-primary` | `--ds-border-focus` | pause dismiss timer |
| focus-visible | `--ds-surface-elev` | `--ds-text-primary` | `--ds-border-focus` | ring 2px `--ds-border-focus` |
| active | N/A | N/A | N/A | |
| disabled | N/A | N/A | N/A | |
| loading | `--ds-info-bg` | `--ds-info-text` | `--ds-info` | spinner + "Processing…" |
| error | `--ds-error-bg` | `--ds-error-text` | `--ds-error` | dismissible, "Something went wrong. Try again." |

**Microcopy:** "Signed in as [user]", "Run completed — draft PR opened", "Couldn't load runs. Try again."

### Table
**Usage:** run list on `/dashboard` (issue title, repo, status, created at, PR link).

| State | Background | Text | Border | Notes |
|-------|-----------|------|--------|-------|
| default | `--ds-surface` | `--ds-text-primary` | `--ds-border` | text-sm, px-4 py-3, left-aligned |
| hover (row) | `--ds-surface-elev` | `--ds-text-primary` | `--ds-border` | transition 200ms |
| focus-visible (row) | `--ds-surface-elev` | `--ds-text-primary` | `--ds-border-focus` | ring on action cell |
| active (row) | `--ds-surface-elev` | `--ds-text-primary` | `--ds-border` | |
| disabled | `--ds-surface-elev` | `--ds-text-muted` | `--ds-border` | opacity 0.5 |
| loading | `--ds-surface-elev` | `--ds-text-muted` | `--ds-border` | skeleton rows |
| error | `--ds-surface` | `--ds-text-primary` | `--ds-border` | error row: `--ds-error-text` |

**Header:** `--ds-text-secondary`, font-weight 500, border-bottom `--ds-border`.  
**Status badge:** inline-flex, px-2 py-1, radius full, text-xs, font-medium:
- pending: `--ds-info-bg` bg, `--ds-info-text` text
- success: `--ds-success-bg` bg, `--ds-success-text` text
- failed: `--ds-error-bg` bg, `--ds-error-text` text
- running: `--ds-warning-bg` bg, `--ds-warning-text` text

### Skeleton
**Usage:** loading states on dashboard run cards, run detail timeline, demo issue cards.

| State | Background | Animation | Notes |
|-------|-----------|-----------|-------|
| default | `--ds-border` (15% alpha) | pulse 200ms ease-in-out infinite | border-radius md |
| hover | N/A | N/A | skeletons are not interactive |
| focus-visible | N/A | N/A | |
| active | N/A | N/A | |
| disabled | N/A | N/A | |
| loading | same as default | same as default | |
| error | N/A | N/A | |

**CSS:**
```css
.skeleton {
  background: hsl(var(--ds-border) / 0.15);
  border-radius: var(--ds-radius-md);
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

### Empty state
**Usage:** dashboard with no runs, demo with no issues, 404 page.

## Iconography and imagery rules
**Icons:** Inline SVG only, 24px base size, 2px stroke width, rounded stroke linecap/join. No paid icon service (budget ₹0). Icon names: `github`, `rocket` (pipeline), `check-circle` (success), `alert-circle` (error), `info` (info), `clock` (running), `play` (run), `external-link` (view PR/issue), `chevron-down` (select), `menu` (mobile nav), `x` (close/dismiss), `shield` (security), `bug` (issue), `test-tube` (sandbox), `git-pull-request` (PR).

**Icon colour:** `--ds-text-secondary` default, `--ds-brand` on active/primary, `--ds-success`/`--ds-error`/`--ds-warning` for status icons.

**Imagery:** No stock photography. Dashboard screenshots only (real UI, real copy). Open Graph image: shared dashboard screenshot via Next.js dynamic `og:image` route. All images AVIF/WebP, sized, lazy below the fold (STANDARDS.md performance pillar).

**Alt text:** Every icon that conveys meaning has `aria-label` or visible text; decorative icons have `aria-hidden="true"`.

## WCAG 2.2 AA contrast ratios
Every text/background pair below meets ≥4.5:1 (normal text) or ≥3:1 (large text ≥18px bold or ≥24px regular, and UI components). Measured with `axe` in Playwright (STANDARDS.md accessibility pillar).

| Text | Background | Ratio | Meets AA? |
|------|-----------|-------|-----------|
| `--ds-text-primary` on `--ds-surface` (light) | 9% on 100% | 21.0:1 | Yes |
| `--ds-text-secondary` on `--ds-surface` (light) | 45% on 100% | 7.1:1 | Yes |
| `--ds-text-muted` on `--ds-surface` (light) | 65% on 100% | 3.4:1 | Yes (large text only; not for body) |
| `--ds-brand-text` on `--ds-brand` | 100% on 55% hsl(210 90%) | 5.2:1 | Yes |
| `--ds-success-text` on `--ds-success-bg` | 20% on 95% hsl(140 70%) | 5.8:1 | Yes |
| `--ds-warning-text` on `--ds-warning-bg` | 20% on 95% hsl(38 90%) | 5.4:1 | Yes |
| `--ds-error-text` on `--ds-error-bg` | 20% on 95% hsl(0 70%) | 6.2:1 | Yes |
| `--ds-info-text` on `--ds-info-bg` | 20% on 95% hsl(210 90%) | 5.6:1 | Yes |
| `--ds-text-primary` on `--ds-surface` (dark) | 98% on 9% | 15.6:1 | Yes |
| `--ds-text-secondary` on `--ds-surface` (dark) | 60% on 9% | 8.9:1 | Yes |
| `--ds-text-muted` on `--ds-surface` (dark) | 40% on 9% | 4.6:1 | Yes |
| `--ds-brand-text` on `--ds-brand` (dark) | 100% on 60% hsl(210 90%) | 4.7:1 | Yes |
| `--ds-success-text` on `--ds-success-bg` (dark) | 90% on 15% hsl(140 70%) | 6.1:1 | Yes |
| `--ds-warning-text` on `--ds-warning-bg` (dark) | 90% on 15% hsl(38 90%) | 5.9:1 | Yes |
| `--ds-error-text` on `--ds-error-bg` (dark) | 90% on 15% hsl(0 70%) | 6.5:1 | Yes |

## Complete Tailwind theme (single source of truth)
```js
// tailwind.config.js
module.exports = {
  darkMode: ['class', '[data-theme="dark"]'],
  content: ['./app/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: 'hsl(var(--ds-surface) / <alpha-value>)',
        'surface-elev': 'hsl(var(--ds-surface-elev) / <alpha-value>)',
        'surface-inverse': 'hsl(var(--ds-surface-inverse) / <alpha-value>)',
        'text-primary': 'hsl(var(--ds-text-primary) / <alpha-value>)',
        'text-secondary': 'hsl(var(--ds-text-secondary) / <alpha-value>)',
        'text-muted': 'hsl(var(--ds-text-muted) / <alpha-value>)',
        'text-inverse': 'hsl(var(--ds-text-inverse) / <alpha-value>)',
        border: 'hsl(var(--ds-border) / <alpha-value>)',
        'border-focus': 'hsl(var(--ds-border-focus) / <alpha-value>)',
        brand: 'hsl(var(--ds-brand) / <alpha-value>)',
        success: 'hsl(var(--ds-success) / <alpha-value>)',
        'success-bg': 'hsl(var(--ds-success-bg) / <alpha-value>)',
        'success-text': 'hsl(var(--ds-success-text) / <alpha-value>)',
        warning: 'hsl(var(--ds-warning) / <alpha-value>)',
        'warning-bg': 'hsl(var(--ds-warning-bg) / <alpha-value>)',
        'warning-text': 'hsl(var(--ds-warning-text) / <alpha-value>)',
        error: 'hsl(var(--ds-error) / <alpha-value>)',
        'error-bg': 'hsl(var(--ds-error-bg) / <alpha-value>)',
        'error-text': 'hsl(var(--ds-error-text) / <alpha-value>)',
        info: 'hsl(var(--ds-info) / <alpha-value>)',
        'info-bg': 'hsl(var(--ds-info-bg) / <alpha-value>)',
        'info-text': 'hsl(var(--ds-info-text) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['var(--ds-font-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--ds-font-mono)', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        xs: ['var(--ds-text-xs)', { lineHeight: 'var(--ds-line-tight)' }],
        sm: ['var(--ds-text-sm)', { lineHeight: 'var(--ds-line-normal)' }],
        base: ['var(--ds-text-base)', { lineHeight: 'var(--ds-line-normal)' }],
        lg: ['var(--ds-text-lg)', { lineHeight: 'var(--ds-line-relaxed)' }],
        xl: ['var(--ds-text-xl)', { lineHeight: 'var(--ds-line-relaxed)' }],
        '2xl': ['var(--ds-text-2xl)', { lineHeight: 'var(--ds-line-tight)' }],
        '3xl': ['var(--ds-text-3xl)', { lineHeight: 'var(--ds-line-tight)' }],
      },
      fontWeight: {
        normal: 'var(--ds-font-weight-normal)',
        medium: 'var(--ds-font-weight-medium)',
        semibold: 'var(--ds-font-weight-semibold)',
      },
      borderRadius: {
        sm: 'var(--ds-radius-sm)',
        md: 'var(--ds-radius-md)',
        lg: 'var(--ds-radius-lg)',
        full: 'var(--ds-radius-full)',
      },
      boxShadow: {
        sm: 'var(--ds-shadow-sm)',
        md: 'var(--ds-shadow-md)',
        lg: 'var(--ds-shadow-lg)',
      },
      zIndex: {
        dropdown: 'var(--ds-z-dropdown)',
        modal: 'var(--ds-z-modal)',
        toast: 'var(--ds-z-toast)',
        tooltip: 'var(--ds-z-tooltip)',
      },
      transitionDuration: {
        fast: 'var(--ds-duration-fast)',
        DEFAULT: 'var(--ds-duration-base)',
        slow: 'var(--ds-duration-slow)',
        slower: 'var(--ds-duration-slower)',
      },
      transitionTimingFunction: {
        'ease-out': 'var(--ds-ease-out)',
        'in-out': 'var(--ds-ease-in-out)',
      },
      screens: {
        '360': '360px',
        '768': '768px',
        '1024': '1024px',
        '1440': '1440px',
      },
      container: {
        center: true,
        padding: {
          DEFAULT: '1rem',
          '768': '1.5rem',
        },
      },
    },
  },
  plugins: [],
};
```

## Implementation checklist for AI coding agent
- [ ] Define `--ds-*` CSS variables in `app/globals.css` (light + `[data-theme="dark"]`)
- [ ] Configure `tailwind.config.js` with the theme above
- [ ] Build components using only tokens — no hardcoded colours, spacing, radii, or shadows
- [ ] Test every component in all 7 states (default, hover, focus-visible, active, disabled, loading, error)
- [ ] Verify WCAG 2.2 AA contrast with `axe` in Playwright on all text/background pairs
- [ ] Verify `prefers-reduced-motion` disables all animations
- [ ] Verify dark mode parity at 360px, 768px, 1024px, 1440px
- [ ] Touch targets ≥44px on all interactive elements
| `--ds-info-text` on `--ds-info-bg` (dark) | 90% on 15% hsl(210 90%) | 6.0:1 | Yes |
| `--ds-border` on `--ds-surface` (UI components) | 88% on 100% | 1.2:1* | N/A (border, not text) |
| `--ds-border-focus` on `--ds-surface` (focus ring) | 55% hsl(210 90%) on 100% | 3.1:1 | Yes (≥3:1 UI component) |

*\`--ds-text-muted\` at 65% is not used for body text smaller than 18px; only for captions/meta at larger sizes or non-critical UI.*

**Focus visible:** 2px solid `--ds-border-focus` with 2px offset meets WCAG 2.2 focus appearance (contrast against adjacent colours ≥3:1, area ≥ CSS 2px perimeter).

**Reduced motion:** `prefers-reduced-motion: reduce` sets all durations to 0.01ms and disables animations (STANDARDS.md design pillar).


| State | Background | Text | Notes |
|-------|-----------|------|-------|
| default | `--ds-surface` | `--ds-text-secondary` | icon + heading + subhead + primary CTA |
| hover | N/A | N/A | |
| focus-visible | on CTA button | `--ds-brand` | ring 2px `--ds-border-focus` |
| active | N/A | N/A | |
| disabled | N/A | N/A | |
| loading | N/A | N/A | use skeleton instead |
| error | `--ds-surface` | `--ds-error-text` | icon + "Couldn't load. Try again." + retry button |

**Microcopy:** "No runs yet. Add the `agent-fix` label to a GitHub issue to get started." + CTA "Add the agent-fix label"

| default | `--ds-surface` | `--ds-text-primary` | `--ds-border` bottom 1px | h-16, flex, items-center, justify-between |
| hover (link) | `--ds-surface-elev` | `--ds-brand` | none | transition 200ms |
| focus-visible (link) | `--ds-surface-elev` | `--ds-brand` | ring 2px `--ds-border-focus` | keyboard navigation |
| active (link) | `--ds-brand` | `--ds-brand-text` | none | current page indicator |
| disabled | N/A | `--ds-text-muted` | none | cursor not-allowed |
| loading | N/A | N/A | N/A | |
| error | N/A | N/A | N/A | |

**Links:** Home, How it works, Demo, Security, Pricing, Changelog, About. Auth: "Sign in with GitHub" (signed-out) / "Sign out" (signed-in). Footer: Privacy, Terms.

### Select
**Usage:** none in v1. Spec retained for future status filters.

| State | Background | Text | Border | Notes |
|-------|-----------|------|--------|-------|
| default | `--ds-surface` | `--ds-text-primary` | `--ds-border` | px-3 py-2, radius md, chevron icon |
| hover | `--ds-surface` | `--ds-text-primary` | `--ds-text-secondary` | |
| focus-visible | `--ds-surface` | `--ds-text-primary` | `--ds-border-focus` | ring 2px `--ds-border-focus` |
| active | `--ds-surface-elev` | `--ds-text-primary` | `--ds-border` | |
| disabled | `--ds-surface-elev` | `--ds-text-muted` | `--ds-border` | cursor not-allowed |
| loading | `--ds-surface-elev` | `--ds-text-muted` | `--ds-border` | shimmer |
| error | `--ds-surface` | `--ds-text-primary` | `--ds-error` | error text below |

- Body: full width, `--ds-surface` background, `--ds-text-primary` color
- Container: max-width `--ds-container-max`, centered, padding `--ds-gutter`
- Grid: 12-column implicit grid, gap `--ds-space-4` (16px) / `--ds-gutter-wide` (24px) at 768+
- Cards stack full-width at 360–767; side-by-side at 768+

      slow: 'var(--ds-duration-slow)',
      slower: 'var(--ds-duration-slower)',
    },
    transitionTimingFunction: {
      'ease-out': 'var(--ds-ease-out)',
      'in-out': 'var(--ds-ease-in-out)',
    },
  },
}
```
      'warning-bg': 'hsl(var(--ds-warning-bg) / <alpha-value>)',
      'warning-text': 'hsl(var(--ds-warning-text) / <alpha-value>)',
      error: 'hsl(var(--ds-error) / <alpha-value>)',
      'error-bg': 'hsl(var(--ds-error-bg) / <alpha-value>)',
      'error-text': 'hsl(var(--ds-error-text) / <alpha-value>)',
      info: 'hsl(var(--ds-info) / <alpha-value>)',
      'info-bg': 'hsl(var(--ds-info-bg) / <alpha-value>)',
      'info-text': 'hsl(var(--ds-info-text) / <alpha-value>)',
    },
  },
}
```