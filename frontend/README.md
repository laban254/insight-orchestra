# Insight Orchestra - Frontend

This is the Next.js frontend for [Insight Orchestra](https://github.com/laban254/insight-orchestra), a self-hostable AI-powered data analysis platform.

## Overview

The frontend provides an interactive UI for:
- File uploads (CSV/TSV/Excel/JSON/Parquet) and database connections
- Natural language queries against your data, including multi-table queries against a connected database
- Interactive visualizations with Plotly
- Workspaces (save/reopen an analysis), session history, and read-only share links
- Export as an interactive HTML report, PDF, Markdown summary, or Q&A CSV
- Optional login, role-based access control, and an admin panel when the backend has `AUTH_ENABLED=true`

## Tech Stack

- Next.js 14 (App Router)
- React
- Tailwind CSS
- Plotly.js for visualizations
- Hand-built UI primitives in `components/ui/` (not a shadcn/ui install)

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

```bash
# Install dependencies
npm install
# or
yarn install
```

### Development

```bash
# Run development server
npm run dev
```

The frontend will be available at `http://localhost:3000` (Next.js's default dev port —
different from the `8501` the Docker image binds to; see below).

### Environment Variables

Create a `.env.local` file:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Docker Deployment

The frontend is included in the main docker-compose.yml, which pulls a prebuilt
image from GHCR:

```bash
docker compose up -d
```

To build this directory from source instead:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build frontend
```

The backend URL is resolved at runtime, not baked into the image: the server
injects `PUBLIC_API_URL` into `window.__IO_ENV__` on each request (see
`lib/runtimeEnv.ts`), so the same published image works for every deployment.
`NEXT_PUBLIC_API_URL` still works as a fallback for `next dev`.

Because the *browser* makes these calls, the value has to be reachable from
wherever you open the UI — not from inside the container.

Access the frontend at: http://localhost:8501

## API Integration

The frontend communicates with the backend API at `NEXT_PUBLIC_API_URL`. The API provides:

- File upload endpoints
- Natural language query processing
- Database connectors (PostgreSQL, MySQL, SQLite, DuckDB)
- Session management
- Visualization rendering

## Project Structure

```
frontend/
├── app/                 # Next.js app router
│   ├── page.tsx       # Main dashboard
│   ├── login/         # Sign-in page (shown only when AUTH_ENABLED=true)
│   ├── layout.tsx     # Root layout
│   └── globals.css    # Global styles
├── components/
│   ├── workspace/      # Workspace, CanvasPane — the chat + canvas shell
│   ├── agents/         # AgentTimeline (SSE progress), AnalysisProgress (loading state)
│   ├── chat/           # MessageBubble, CodeBlock
│   ├── upload/          # FileUpload, DatabaseConnect
│   ├── viz/             # ChartRenderer, DataTable
│   ├── export/          # ExportMenu-driven export (HTML/PDF/Markdown/CSV)
│   ├── admin/           # Users, API keys, audit log — admin-only, auth on
│   ├── share/           # Read-only shared-session view
│   └── ui/              # Hand-built UI primitives
└── public/            # Static assets
```

## Learn More

- [Insight Orchestra Documentation](../docs/)
- [API Reference](../docs/API_REFERENCE.md)
- [Setup Guide](../docs/SETUP.md)
