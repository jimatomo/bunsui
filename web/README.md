# bunsui web

Bun workspace: Hono API (`apps/api`) + React UI (`apps/ui`).

```bash
cd web
bun install
bun run dev          # API :8787 + UI :5173
bun test             # API health/status tests
```

Point the API at a project SQLite DB:

```bash
export BUNSUI_PROJECT=/path/to/project   # reads .bunsui/control.sqlite
# or
export BUNSUI_SQLITE=/path/to/.bunsui/control.sqlite
bun run dev:api
```
