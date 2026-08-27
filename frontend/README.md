# Insight Orchestra - Frontend

This is the Next.js frontend for [Insight Orchestra](https://github.com/laban254/insight-orchestra), a self-hostable AI-powered data analysis platform.

## Overview

The frontend provides an interactive UI for:
- CSV file uploads and database connections
- Natural language queries against your data
- Interactive visualizations with Plotly
- Session management and history
- Export capabilities (CSV, JSON, PDF)

## Tech Stack

- Next.js 14 (App Router)
- React
- Tailwind CSS
- Plotly.js for visualizations
- shadcn/ui components

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

The frontend will be available at `http://localhost:8501`.

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
│   ├── layout.tsx     # Root layout
│   └── globals.css    # Global styles
├── components/
│   ├── agents/        # Agent pipeline components
│   ├── chat/          # Chat interface
│   ├── export/        # Export functionality
│   ├── upload/        # File upload & DB connections
│   └── viz/           # Visualization components
└── public/            # Static assets
```

## Learn More

- [Insight Orchestra Documentation](../docs/)
- [API Reference](../docs/API_REFERENCE.md)
- [Setup Guide](../docs/SETUP.md)
