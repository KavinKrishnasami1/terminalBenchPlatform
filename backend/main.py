"""FastAPI application for Terminal-Bench platform"""
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
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
from celery_worker import execute_harbor_task
from harbor_runner import execute_harbor
from storage import upload_directory_to_s3, download_directory_from_s3, USE_CLOUD_STORAGE
import threading

# Check if Redis/Celery is available
def is_redis_available():
    """Check if Redis is available for Celery"""
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url, socket_connect_timeout=1)
        r.ping()
        return True
    except Exception:
        return False

USE_CELERY = is_redis_available()

def update_run_status_if_complete_local(run_id: int, db):
    """Update run status to completed if all attempts are done (local version)"""
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return

        # Check if any attempts are still running
        running_attempts = [a for a in run.attempts if a.status == 'running']

        if len(running_attempts) == 0:
            # All attempts are done (completed or failed)
            run.status = 'completed'
            db.commit()
    except Exception:
        pass

def execute_attempt_locally(attempt_id: int, task_path: str, model: str, output_dir: str, openrouter_api_key: str):
    """Execute Harbor locally (without Celery) for development"""
    from database import SessionLocal
    db = SessionLocal()

    try:
        # Execute Harbor
        result = execute_harbor(
            task_path=task_path,
            model=model,
            output_dir=output_dir,
            openrouter_api_key=openrouter_api_key
        )

        # Get attempt record
        attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
        if not attempt:
            return

        # Process results
        if result['success']:
            attempt.status = "completed"
            attempt.reward = result['reward']
            attempt.episode_count = len(result['episodes'])
            attempt.output_path = result['output_path']
            attempt.error_message = None
            attempt.completed_at = datetime.utcnow()

            # Store episodes
            for ep_data in result['episodes']:
                episode = Episode(
                    attempt_id=attempt_id,
                    episode_number=ep_data['episode_number'],
                    analysis=ep_data['analysis'],
                    plan=ep_data['plan'],
                    commands=ep_data['commands'],
                    task_complete=ep_data['task_complete']
                )
                db.add(episode)

            # Store test results
            for test_data in result['test_results']:
                test_result = TestResult(
                    attempt_id=attempt_id,
                    test_name=test_data['test_name'],
                    status=test_data['status'],
                    duration_ms=test_data['duration_ms'],
                    error_message=test_data['error_message']
                )
                db.add(test_result)

            db.commit()

            # Update run status if all attempts are done
            update_run_status_if_complete_local(attempt.run_id, db)
        else:
            attempt.status = "failed"
            attempt.reward = 0.0
            attempt.error_message = result['error']
            attempt.completed_at = datetime.utcnow()
            db.commit()

            # Update run status if all attempts are done
            update_run_status_if_complete_local(attempt.run_id, db)

    except Exception as e:
        try:
            attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
            if attempt:
                attempt.status = "failed"
                attempt.error_message = f"Worker error: {str(e)}"
                attempt.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()

app = FastAPI(title="Terminal-Bench Platform")

# CORS middleware
# Allow both local development and Railway frontend
frontend_url = os.getenv("FRONTEND_URL", "https://frontend-production-a622.up.railway.app")
allowed_origins = [
    "http://localhost:3000",  # Local development
    frontend_url,  # Railway frontend from env var
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories
# Use /data volume on Fly.io (production), local dirs for development
if Path("/data").exists():
    # Production: Use Fly.io volume
    UPLOAD_DIR = Path("/data/uploads")
    OUTPUT_DIR = Path("/data/harbor_outputs")
else:
    # Development: Use local directories
    UPLOAD_DIR = Path("./uploads")
    OUTPUT_DIR = Path("./harbor_outputs")

UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

# Initialize database
init_db()

# Log execution mode
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
if USE_CELERY:
    logger.info("✓ Redis available - Using Celery for concurrent execution")
else:
    logger.warning("⚠ Redis unavailable - Using local threading (development mode)")
    logger.warning("  For production deployment with concurrent execution, ensure Redis is running")

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

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "terminal-bench-platform"}

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

    # Upload to S3 if cloud storage is enabled
    s3_prefix = None
    if USE_CLOUD_STORAGE:
        # S3 key: tasks/{task_name}_{timestamp}/
        s3_prefix = f"tasks/{task_name}_{timestamp}"
        success = upload_directory_to_s3(str(task_path), s3_prefix)
        if not success:
            logger.warning(f"Failed to upload task to S3, falling back to local storage")
            s3_prefix = None

    # Create task in database
    # If cloud storage is enabled and upload succeeded, store S3 prefix
    # Otherwise store local path
    task = Task(
        name=task_name,
        file_path=s3_prefix if s3_prefix else str(task_path)
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

@app.delete("/api/tasks")
def delete_all_tasks(db: Session = Depends(get_db)):
    """Delete all tasks (cascade deletes runs, attempts, episodes, test results)"""
    try:
        task_count = db.query(Task).count()

        # Manually cascade delete in correct order due to foreign key constraints
        # 1. Delete episodes and test results (children of attempts)
        db.query(Episode).delete()
        db.query(TestResult).delete()

        # 2. Delete attempts (children of runs)
        db.query(Attempt).delete()

        # 3. Delete runs (children of tasks)
        db.query(Run).delete()

        # 4. Finally delete tasks
        db.query(Task).delete()

        db.commit()
        return {
            "success": True,
            "message": f"Deleted {task_count} tasks and all related data",
            "deleted_count": task_count
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete tasks: {str(e)}")

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
    db: Session = Depends(get_db)
):
    """Create a new run for a task"""

    # Get task
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get OpenRouter API key
    openrouter_key = os.getenv('OPENROUTER_API_KEY')
    if not openrouter_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")

    # Create run
    run = Run(
        task_id=task_id,
        model=run_data.model,
        status="queued"
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Create attempt records and enqueue tasks
    for i in range(run_data.n_attempts):
        attempt = Attempt(
            run_id=run.id,
            attempt_number=i + 1,
            status="running"  # Mark as running immediately when enqueued
        )
        db.add(attempt)
        db.flush()  # Get attempt.id without committing

        # Create output directory for this attempt
        output_dir = OUTPUT_DIR / f"run_{run.id}_attempt_{i+1}"
        output_dir.mkdir(parents=True, exist_ok=True)

        if USE_CELERY:
            # Production: Enqueue Celery task for parallel execution
            execute_harbor_task.delay(
                attempt_id=attempt.id,
                task_path=task.file_path,
                model=run_data.model,
                output_dir=str(output_dir),
                openrouter_api_key=openrouter_key
            )
        else:
            # Development: Execute in background thread (no Redis needed)
            thread = threading.Thread(
                target=execute_attempt_locally,
                args=(attempt.id, task.file_path, run_data.model, str(output_dir), openrouter_key)
            )
            thread.daemon = True
            thread.start()

    db.commit()

    # Update run status to running (tasks are now enqueued)
    run.status = "running"
    db.commit()

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

@app.get("/api/attempts/{attempt_id}")
def get_attempt_details(attempt_id: int, db: Session = Depends(get_db)):
    """Get attempt details including error message"""

    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    return {
        "id": attempt.id,
        "attempt_number": attempt.attempt_number,
        "status": attempt.status,
        "reward": attempt.reward,
        "episode_count": attempt.episode_count,
        "error_message": attempt.error_message,
        "output_path": attempt.output_path,
        "created_at": attempt.created_at,
        "completed_at": attempt.completed_at
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
