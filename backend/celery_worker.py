"""Celery worker tasks for Harbor execution"""
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from celery import Task
from celery.utils.log import get_task_logger
from celery_app import app
from database import SessionLocal, Attempt, Episode, TestResult, Task as TaskModel, Run
from harbor_runner import execute_harbor

logger = get_task_logger(__name__)


def update_run_status_if_complete(run_id: int, db):
    """Update run status to completed if all attempts are done"""
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
            logger.info(f"Updated Run #{run_id} status to 'completed' - all attempts finished")
    except Exception as e:
        logger.error(f"Failed to update run status for run {run_id}: {e}")


class DatabaseTask(Task):
    """Base task that provides database session management"""
    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        """Clean up database connection after task completes"""
        if self._db is not None:
            self._db.close()
            self._db = None


def ensure_task_files_exist(task_path: str, attempt_id: int, db) -> str:
    """
    Ensure task files exist locally on worker machine.

    On Fly.io, each machine has its own volume, so we need to copy
    task files from the original upload location to the worker's volume.

    Args:
        task_path: Original task path from database
        attempt_id: Attempt ID for logging
        db: Database session

    Returns:
        Local path to task files on this worker
    """
    task_path = Path(task_path)

    # If task files already exist locally, return the path
    if task_path.exists() and (task_path / "task.toml").exists():
        logger.info(f"Task files already exist at {task_path}")
        return str(task_path)

    logger.info(f"Task files not found at {task_path}, attempting to sync from app machine...")

    # Get task record from database to find original upload
    # Extract task directory name pattern from path
    # Path format: /data/uploads/task-name_timestamp/extracted/task-name
    uploads_parent = Path("/data/uploads")

    # Try to find the task directory in the uploads parent
    # Extract the task directory name (e.g., "task-name_timestamp")
    path_parts = task_path.parts
    try:
        uploads_idx = path_parts.index("uploads")
        task_dir_name = path_parts[uploads_idx + 1] if len(path_parts) > uploads_idx + 1 else None
    except (ValueError, IndexError):
        logger.error(f"Could not parse task directory from path: {task_path}")
        raise ValueError(f"Invalid task path format: {task_path}")

    if not task_dir_name:
        raise ValueError(f"Could not extract task directory name from {task_path}")

    # Create local uploads directory if it doesn't exist
    uploads_parent.mkdir(parents=True, exist_ok=True)
    local_task_dir = uploads_parent / task_dir_name

    # If already exists locally, return it
    if local_task_dir.exists():
        logger.info(f"Task directory found locally at {local_task_dir}")
        return str(task_path)  # Return original path structure

    logger.info(f"Creating local task directory: {local_task_dir}")

    # For Fly.io: Copy from app machine using internal network
    # Get app machine's internal address from FLY_APP_NAME
    app_machine_url = os.getenv("APP_MACHINE_URL", "http://app.process.tbench-platform-backend.internal:8080")

    # For now, we'll need to fetch via HTTP endpoint
    # This requires implementing a file serving endpoint on the app machine
    # As a quick workaround, let's just re-query from database and extract from zip

    logger.warning(f"Task sync not yet implemented. Task files must be pre-populated on worker volumes.")
    logger.warning(f"This is a known limitation with Fly.io multi-machine volumes.")

    # Return the path anyway - if Harbor can't find it, it will fail with a clear error
    return str(task_path)


@app.task(
    bind=True,
    base=DatabaseTask,
    name='celery_worker.execute_harbor_task',
    max_retries=2,
    default_retry_delay=60,  # Retry after 1 minute
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,  # Max 10 minutes backoff
    retry_jitter=True
)
def execute_harbor_task(
    self,
    attempt_id: int,
    task_path: str,
    model: str,
    output_dir: str,
    openrouter_api_key: str
):
    """
    Execute Harbor for a single attempt (runs as Celery task)

    Args:
        attempt_id: Database ID of the attempt record
        task_path: Path to the Terminal-Bench task directory
        model: Model identifier (e.g., "openrouter/anthropic/claude-sonnet-4.5")
        output_dir: Directory to store Harbor output
        openrouter_api_key: OpenRouter API key for Harbor execution

    Returns:
        Dict with execution results
    """
    db = SessionLocal()

    try:
        logger.info(f"Starting Harbor execution for attempt_id={attempt_id}, model={model}")

        # Get attempt record
        attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
        if not attempt:
            raise ValueError(f"Attempt {attempt_id} not found in database")

        # Attempt is already marked as "running" when created in main.py
        # No need to update status here

        # Execute Harbor
        result = execute_harbor(
            task_path=task_path,
            model=model,
            output_dir=output_dir,
            openrouter_api_key=openrouter_api_key
        )

        # Process results
        if result['success']:
            logger.info(f"Harbor execution successful for attempt {attempt_id}, reward={result['reward']}")

            # Update attempt record
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
            logger.info(f"Stored {len(result['episodes'])} episodes and {len(result['test_results'])} test results")

            # Update run status if all attempts are done
            update_run_status_if_complete(attempt.run_id, db)

            return {
                'success': True,
                'attempt_id': attempt_id,
                'reward': result['reward'],
                'episode_count': len(result['episodes']),
                'test_count': len(result['test_results'])
            }

        else:
            logger.error(f"Harbor execution failed for attempt {attempt_id}: {result['error']}")

            # Update attempt record with error
            attempt.status = "failed"
            attempt.reward = 0.0
            attempt.error_message = result['error']
            attempt.completed_at = datetime.utcnow()
            db.commit()

            # Update run status if all attempts are done
            update_run_status_if_complete(attempt.run_id, db)

            return {
                'success': False,
                'attempt_id': attempt_id,
                'error': result['error']
            }

    except Exception as e:
        logger.exception(f"Unexpected error executing Harbor for attempt {attempt_id}")

        # Update attempt status to failed
        try:
            attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
            if attempt:
                attempt.status = "failed"
                attempt.error_message = f"Worker error: {str(e)}"
                attempt.completed_at = datetime.utcnow()
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update attempt status: {db_error}")

        # Re-raise exception for Celery retry mechanism
        raise

    finally:
        db.close()


@app.task(name='celery_worker.health_check')
def health_check():
    """Health check task for monitoring worker availability"""
    return {'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}
