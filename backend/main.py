"""FastAPI application for Terminal-Bench platform"""
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import shutil
import os
from pathlib import Path
from datetime import datetime
import zipfile
from dotenv import load_dotenv

# Load environment variables from .env file (check parent directory too)
load_dotenv()  # Load from current directory first
load_dotenv(Path(__file__).parent.parent / '.env')  # Then load from project root

from database import get_db, init_db, Task, Run, Attempt, Episode, TestResult
from harbor_runner import execute_harbor

app = FastAPI(title="Terminal-Bench Platform")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories
UPLOAD_DIR = Path("./uploads")
OUTPUT_DIR = Path("./harbor_outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Initialize database
init_db()

# Pydantic models
class TaskResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    class Config:
        from_attributes = True

class RunCreate(BaseModel):
    model: str = "openrouter/anthropic/claude-sonnet-4.5"
    n_attempts: int = 10

class AttemptResponse(BaseModel):
    id: int
    attempt_number: int
    status: str
    reward: Optional[float]
    episode_count: Optional[int]
    tests_passed: Optional[int] = None
    tests_total: Optional[int] = None

class EpisodeResponse(BaseModel):
    id: int
    episode_number: int
    analysis: Optional[str]
    plan: Optional[str]
    commands: Optional[str]
    task_complete: Optional[bool]

class RunResponse(BaseModel):
    id: int
    task_id: int
    model: str
    status: str
    created_at: datetime
    attempts: List[AttemptResponse] = []

@app.get("/")
def read_root():
    return {"message": "Terminal-Bench Platform API"}

@app.post("/api/tasks", response_model=TaskResponse)
async def upload_task(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a Terminal-Bench task zip file"""

    # Validate file is a zip
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="File must be a .zip file")

    # Create unique task directory
    task_name = file.filename.replace('.zip', '')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_dir = UPLOAD_DIR / f"{task_name}_{timestamp}"
    task_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    zip_path = task_dir / file.filename
    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract zip
    extract_dir = task_dir / "extracted"
    extract_dir.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract zip: {str(e)}")

    # Find the actual task directory (zip might have nested structure)
    # Look for directory containing task.toml
    task_path = None
    for item in extract_dir.iterdir():
        if item.is_dir():
            if (item / "task.toml").exists():
                task_path = item
                break

    if not task_path:
        raise HTTPException(status_code=400, detail="Could not find task directory with task.toml in uploaded zip")

    # Create task in database
    task = Task(
        name=task_name,
        file_path=str(task_path)
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return task

@app.get("/api/tasks", response_model=List[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    """List all uploaded tasks"""
    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
    return tasks

@app.get("/api/tasks/{task_id}/runs", response_model=List[RunResponse])
def get_task_runs(task_id: int, db: Session = Depends(get_db)):
    """Get all runs for a specific task"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    runs = db.query(Run).filter(Run.task_id == task_id).order_by(Run.created_at.desc()).all()

    # Build response with attempt data
    runs_data = []
    for run in runs:
        attempts_data = []
        for attempt in run.attempts:
            tests_total = len(attempt.test_results)
            tests_passed = sum(1 for t in attempt.test_results if t.status == "passed")

            attempts_data.append(AttemptResponse(
                id=attempt.id,
                attempt_number=attempt.attempt_number,
                status=attempt.status,
                reward=attempt.reward,
                episode_count=attempt.episode_count,
                tests_passed=tests_passed if tests_total > 0 else None,
                tests_total=tests_total if tests_total > 0 else None
            ))

        runs_data.append(RunResponse(
            id=run.id,
            task_id=run.task_id,
            model=run.model,
            status=run.status,
            created_at=run.created_at,
            attempts=attempts_data
        ))

    return runs_data

@app.post("/api/tasks/{task_id}/runs", response_model=RunResponse)
async def create_run(
    task_id: int,
    run_data: RunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new run for a task"""

    # Get task
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Create run
    run = Run(
        task_id=task_id,
        model=run_data.model,
        status="queued"
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Create attempt records
    for i in range(run_data.n_attempts):
        attempt = Attempt(
            run_id=run.id,
            attempt_number=i + 1,
            status="queued"
        )
        db.add(attempt)

    db.commit()

    # Start execution in background
    background_tasks.add_task(
        execute_run,
        run.id,
        task.file_path,
        run_data.model,
        run_data.n_attempts
    )

    return run

@app.get("/api/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: int, db: Session = Depends(get_db)):
    """Get run details with attempts"""

    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Fetch attempts with test results count
    attempts_data = []
    for attempt in run.attempts:
        tests_total = len(attempt.test_results)
        tests_passed = sum(1 for t in attempt.test_results if t.status == "passed")

        attempts_data.append(AttemptResponse(
            id=attempt.id,
            attempt_number=attempt.attempt_number,
            status=attempt.status,
            reward=attempt.reward,
            episode_count=attempt.episode_count,
            tests_passed=tests_passed if tests_total > 0 else None,
            tests_total=tests_total if tests_total > 0 else None
        ))

    return RunResponse(
        id=run.id,
        task_id=run.task_id,
        model=run.model,
        status=run.status,
        created_at=run.created_at,
        attempts=attempts_data
    )

@app.get("/api/attempts/{attempt_id}/episodes", response_model=List[EpisodeResponse])
def get_episodes(attempt_id: int, db: Session = Depends(get_db)):
    """Get episodes for an attempt"""

    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    return attempt.episodes

class TestResultResponse(BaseModel):
    id: int
    test_name: str
    status: str
    duration_ms: Optional[float]
    error_message: Optional[str]

    class Config:
        from_attributes = True

@app.get("/api/attempts/{attempt_id}/test-results", response_model=List[TestResultResponse])
def get_test_results(attempt_id: int, db: Session = Depends(get_db)):
    """Get test results for an attempt"""

    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    return attempt.test_results

def execute_run(run_id: int, task_path: str, model: str, n_attempts: int):
    """Execute all attempts for a run (runs in background)"""

    # Get database session
    from database import SessionLocal
    db = SessionLocal()

    try:
        # Update run status
        run = db.query(Run).filter(Run.id == run_id).first()
        run.status = "running"
        db.commit()

        # Get OpenRouter API key
        openrouter_key = os.getenv('OPENROUTER_API_KEY')
        if not openrouter_key:
            raise Exception("OPENROUTER_API_KEY not found in environment")

        # Execute each attempt sequentially
        for i in range(n_attempts):
            attempt = db.query(Attempt).filter(
                Attempt.run_id == run_id,
                Attempt.attempt_number == i + 1
            ).first()

            # Update attempt status
            attempt.status = "running"
            db.commit()

            # Create output directory for this attempt
            output_dir = OUTPUT_DIR / f"run_{run_id}_attempt_{i+1}"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Execute Harbor
            result = execute_harbor(
                task_path=task_path,
                model=model,
                output_dir=str(output_dir),
                openrouter_api_key=openrouter_key
            )

            if result['success']:
                # Update attempt
                attempt.status = "completed"
                attempt.reward = result['reward']
                attempt.episode_count = len(result['episodes'])
                attempt.output_path = result['output_path']
                attempt.completed_at = datetime.utcnow()

                # Store episodes
                for ep_data in result['episodes']:
                    episode = Episode(
                        attempt_id=attempt.id,
                        **ep_data
                    )
                    db.add(episode)

                # Store test results
                for test_data in result['test_results']:
                    test_result = TestResult(
                        attempt_id=attempt.id,
                        **test_data
                    )
                    db.add(test_result)

            else:
                # Mark attempt as failed
                attempt.status = "failed"
                attempt.error_message = result['error']
                attempt.completed_at = datetime.utcnow()

            db.commit()

        # Mark run as completed
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        # Mark run as failed
        run.status = "failed"
        db.commit()
        print(f"Error executing run {run_id}: {str(e)}")

    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
