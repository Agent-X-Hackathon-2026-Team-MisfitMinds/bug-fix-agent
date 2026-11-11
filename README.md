# bug-fix-agent

Bug fix agent for the Agent-X Hackathon 2026 - Team MisfitMinds

## Frontend setup (apps/web)

From the repository root:

```bash
cd apps/web
npm ci --workspaces=false
npx playwright install chromium webkit
npm run dev
```

Open http://localhost:3000. The demo workspace uses example data. Real GitHub sign-in and dashboard data require the backend setup and an `API_BACKEND_URL` supplied by the team. Do not commit credentials.

Run the frontend checks from `apps/web`:

```bash
npm run check
npm run test
npx playwright test --workers=1
```

The Playwright command runs both Chromium and WebKit. On Windows WebKit only, `keyboard can navigate the app shell with a visible focus indicator` is skipped: in our Windows Playwright WebKit diagnostic, Tab skipped ordinary links. It still runs in Chromium and Linux WebKit. Revisit this limitation when the browser or Playwright is updated.

The browser tests use mocked API responses and do not verify live backend integration. Playwright WebKit is not the same as testing Safari itself.
