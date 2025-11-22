# Terminal-Bench Platform Frontend

Next.js 14 frontend for the Terminal-Bench Platform.

## Quick Start

```bash
# Install dependencies (if not already done)
npm install

# Run development server
npm run dev
```

The frontend will be available at http://localhost:3000

## Environment Variables

Create a `.env.local` file with:

```
NEXT_PUBLIC_API_URL=http://localhost:8001
```

**Important**: The backend runs on port **8001** (not 8000).

## Features

### 1. Dashboard (/)
- Upload Terminal-Bench task zip files
- View all uploaded tasks
- Navigate to task detail to create runs

### 2. Task Detail (/tasks/[id])
- Configure run parameters (model, number of attempts)
- Start new Harbor execution run

### 3. Run Detail (/runs/[id])
- View all attempts for a run
- Auto-refresh every 3 seconds while running
- See pass/fail status for each attempt
- Navigate to individual attempt details

### 4. Attempt Detail (/attempts/[id])
- View episode-by-episode execution trace
- Expandable episodes with:
  - State Analysis
  - Explanation/Plan
  - Commands executed

## Architecture

- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS
- **Components**: shadcn/ui
- **Icons**: lucide-react
- **API**: Connects to FastAPI backend on port 8001

## Pages

- `/` - Dashboard with task list and upload
- `/tasks/[id]` - Create new run for task
- `/runs/[id]` - View run with all attempts (auto-refreshing)
- `/attempts/[id]` - View episode details for attempt

## Components

- `components/upload-task.tsx` - Drag-and-drop task uploader
- `components/attempt-card.tsx` - Attempt card with pass/fail status
- `lib/api.ts` - API client for backend communication
- `lib/types.ts` - TypeScript type definitions

## Development

```bash
# Run dev server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

## Backend Connection

The frontend connects to the FastAPI backend at `http://localhost:8001`.

Make sure the backend is running before starting the frontend:

```bash
cd ../backend
python main.py
```

## Key Features Implemented

1. **Task Upload**: Drag-and-drop interface for uploading Terminal-Bench task zips
2. **Run Creation**: Configure model and number of attempts (1-25)
3. **Real-time Updates**: Auto-refreshing run status every 3 seconds
4. **Attempt Cards**: Visual pass/fail indicators matching the UI mockup
5. **Episode Viewer**: Expandable accordion with state analysis, plans, and commands
6. **Responsive Design**: Works on desktop and mobile devices
