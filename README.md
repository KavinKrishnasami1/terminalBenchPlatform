# Terminal-Bench Platform

A local platform for running Terminal-Bench tasks with Harbor and viewing detailed execution results.

## Project Structure

```
terminalBenchPlatform/
├── backend/           # FastAPI backend
│   ├── main.py       # Main FastAPI application
│   ├── database.py    # SQLite database models
│   ├── harbor_runner.py  # Harbor execution logic
│   └── requirements.txt  # Python dependencies
├── frontend/          # Next.js frontend (to be created)
├── venv/             # Python virtual environment
└── ARCHITECTURE.md   # System architecture documentation
```

## Backend Setup

### Prerequisites
- Python 3.12+
- Harbor CLI installed (`pip install git+https://github.com/laude-institute/harbor.git`)
- OpenRouter API key

### Installation

1. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Set environment variable:**
   ```bash
   export OPENROUTER_API_KEY='your-api-key-here'
   ```

### Running the Backend

```bash
cd backend
python main.py
```

The FastAPI server will start at `http://localhost:8000`

**API Documentation:**
Visit `http://localhost:8000/docs` for interactive Swagger UI documentation

## API Endpoints

### Upload Task
```
POST /api/tasks
Body: multipart/form-data with 'file' (zip file)
Response: Task object with ID
```

### List Tasks
```
GET /api/tasks
Response: List of uploaded tasks
```

### Create Run
```
POST /api/tasks/{task_id}/runs
Body: {
  "model": "openrouter/anthropic/claude-sonnet-4.5",
  "n_attempts": 10
}
Response: Run object with ID
```

### Get Run Details
```
GET /api/runs/{run_id}
Response: Run with all attempts and test results
```

### Get Episodes
```
GET /api/attempts/{attempt_id}/episodes
Response: List of episodes for an attempt
```

## Database

- **Type**: SQLite
- **Location**: `backend/tbench.db` (created automatically)
- **Tables**: tasks, runs, attempts, episodes, test_results

## Current Status

### ✅ Completed
- FastAPI backend with file upload
- SQLite database schema
- Harbor integration and execution
- Episode and test result parsing
- Background task execution (sequential)

### 🚧 In Progress
- Next.js frontend (next step)

### 📋 Planned
- Real-time progress updates (WebSockets)
- Celery/Redis queue for concurrent execution
- Cloud storage (S3/R2)
- Deploy to production

## Testing the Backend

You can test the backend using curl or the Swagger UI at `http://localhost:8000/docs`:

```bash
# Upload a task
curl -X POST "http://localhost:8000/api/tasks" \
  -F "file=@path/to/your/task.zip"

# Create a run (replace {task_id} with actual ID)
curl -X POST "http://localhost:8000/api/tasks/1/runs" \
  -H "Content-Type: application/json" \
  -d '{"model": "openrouter/anthropic/claude-sonnet-4.5", "n_attempts": 10}'

# Check run status (replace {run_id} with actual ID)
curl "http://localhost:8000/api/runs/1"
```

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed system architecture, including:
- FastAPI vs Node.js decision
- Database schema
- Queue architecture (Celery + Redis)
- Scalability considerations (750 concurrent runs)
- Infrastructure options (Railway, Modal, Fly.io)

## Next Steps

1. ✅ Backend API complete
2. **Create Next.js frontend** (current)
3. Add real-time updates
4. Implement queue system for scale
5. Deploy to production
