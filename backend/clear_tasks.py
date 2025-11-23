"""Script to clear all tasks from the database"""
import sys
from pathlib import Path

# Add parent directory to path to import database module
sys.path.insert(0, str(Path(__file__).parent))

from database import SessionLocal, Task

def clear_all_tasks():
    """Delete all tasks from database (cascade deletes runs, attempts, episodes, test results)"""
    db = SessionLocal()
    try:
        # Count tasks before deletion
        task_count = db.query(Task).count()
        print(f"Found {task_count} tasks in database")

        if task_count == 0:
            print("No tasks to delete")
            return

        # Delete all tasks (cascade will handle related records)
        db.query(Task).delete()
        db.commit()

        # Verify deletion
        remaining = db.query(Task).count()
        print(f"✓ Deleted {task_count} tasks")
        print(f"✓ Remaining tasks: {remaining}")

    except Exception as e:
        print(f"Error deleting tasks: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 50)
    print("Clearing all tasks from database...")
    print("=" * 50)
    clear_all_tasks()
    print("=" * 50)
    print("Done! You can now re-upload tasks with S3 storage.")
    print("=" * 50)
