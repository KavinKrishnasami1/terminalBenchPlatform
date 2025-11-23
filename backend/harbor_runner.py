"""Harbor execution and output parsing"""
import subprocess
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from storage import download_directory_from_s3, upload_directory_to_s3, USE_CLOUD_STORAGE

def execute_harbor(
    task_path: str,
    model: str,
    output_dir: str,
    openrouter_api_key: str
) -> Dict:
    """
    Execute Harbor for a single attempt

    Args:
        task_path: Local path or S3 prefix to task directory
        model: Model name (e.g., "openrouter/anthropic/claude-sonnet-4.5")
        output_dir: Local directory for Harbor output
        openrouter_api_key: OpenRouter API key

    Returns:
        Dict with keys: success, output_path, reward, episodes, test_results, error
    """
    temp_task_dir = None
    try:
        # Check if task_path is an S3 prefix (doesn't start with / or doesn't exist locally)
        is_s3_path = USE_CLOUD_STORAGE and (not task_path.startswith('/') or not Path(task_path).exists())

        if is_s3_path:
            # Download task from S3 to temporary directory
            temp_task_dir = tempfile.mkdtemp(prefix="harbor_task_")
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Downloading task from S3: {task_path} -> {temp_task_dir}")

            success = download_directory_from_s3(task_path, temp_task_dir)
            if not success:
                return {
                    'success': False,
                    'error': f"Failed to download task from S3: {task_path}",
                    'output_path': None,
                    'reward': 0.0,
                    'episodes': [],
                    'test_results': []
                }

            # Use the downloaded path for Harbor execution
            actual_task_path = temp_task_dir
        else:
            # Use local path directly
            actual_task_path = task_path
        # Get harbor executable from environment variable (production) or local path (dev)
        harbor_bin_env = os.getenv('HARBOR_BIN')

        if harbor_bin_env:
            # Production: use HARBOR_BIN env var set in Dockerfile
            harbor_bin = Path(harbor_bin_env)
        else:
            # Development: use local harbor-venv
            project_root = Path(__file__).parent.parent
            harbor_bin = project_root / 'harbor-venv' / 'bin' / 'harbor'

        if not harbor_bin.exists():
            return {
                'success': False,
                'error': f"Harbor executable not found at {harbor_bin}. Set HARBOR_BIN env var or install Harbor in harbor-venv/",
                'output_path': None,
                'reward': 0.0,
                'episodes': [],
                'test_results': []
            }

        # Build Harbor command
        # Use Docker for isolated execution (Fly.io supports Docker-in-Docker via Firecracker microVMs)
        cmd = [
            str(harbor_bin), 'run',
            '--path', actual_task_path,  # Use actual (possibly downloaded) task path
            '--agent', 'terminus-2',
            '--model', model,
            '--jobs-dir', output_dir,
            '--n-attempts', '1',
            '--n-concurrent', '1',
            '--env', 'docker'  # Use Docker for isolated task execution
        ]

        # Set environment
        # Ensure DOCKER_HOST is set for Docker communication
        env = {
            **os.environ,
            'OPENROUTER_API_KEY': openrouter_api_key,
            'DOCKER_HOST': os.environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock'),
        }

        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Harbor command: {' '.join(cmd)}")
        logger.info(f"Task path (original): {task_path}")
        logger.info(f"Task path (actual): {actual_task_path}")
        logger.info(f"Output dir: {output_dir}")
        logger.info(f"API key length: {len(openrouter_api_key) if openrouter_api_key else 0}")
        logger.info(f"DOCKER_HOST: {env.get('DOCKER_HOST')}")
        logger.info(f"Using S3 for task: {is_s3_path}")

        # Check Docker availability before running Harbor
        try:
            docker_check = subprocess.run(
                ['docker', 'info'],
                env=env,
                capture_output=True,
                text=True,
                timeout=5
            )
            if docker_check.returncode == 0:
                logger.info(f"Docker daemon is accessible and running")
                # Try to check if we can run a simple container
                docker_test = subprocess.run(
                    ['docker', 'run', '--rm', 'hello-world'],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if docker_test.returncode == 0:
                    logger.info("Docker can successfully run containers")
                else:
                    logger.warning(f"Docker test container failed: {docker_test.stderr[:500]}")
            else:
                logger.error(f"Docker daemon not accessible: {docker_check.stderr[:500]}")
        except Exception as e:
            logger.error(f"Failed to check Docker status: {str(e)}")

        # Execute Harbor
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes
        )

        # Log Harbor output for debugging (even on success)
        logger.info(f"Harbor execution completed with returncode: {result.returncode}")
        logger.info(f"Harbor STDOUT (first 1000 chars): {result.stdout[:1000] if result.stdout else 'No stdout'}")
        if result.stderr:
            logger.warning(f"Harbor STDERR (first 1000 chars): {result.stderr[:1000]}")

        if result.returncode != 0:
            # Capture both stdout and stderr for better debugging
            error_details = {
                'returncode': result.returncode,
                'stderr': result.stderr[:5000] if result.stderr else '',  # Limit to 5000 chars
                'stdout': result.stdout[:2000] if result.stdout else ''   # Capture some stdout too
            }
            return {
                'success': False,
                'error': f"Harbor execution failed (exit {result.returncode}):\n\nSTDERR:\n{error_details['stderr']}\n\nSTDOUT:\n{error_details['stdout']}",
                'output_path': None,
                'reward': 0.0,
                'episodes': [],
                'test_results': []
            }

        # Find trial directory
        trial_dir = find_trial_directory(output_dir)
        if not trial_dir:
            return {
                'success': False,
                'error': "Could not find trial directory in output",
                'output_path': None,
                'reward': 0.0,
                'episodes': [],
                'test_results': []
            }

        # Parse output
        episodes = parse_episodes(trial_dir)
        test_results = parse_test_results(trial_dir)
        reward = parse_reward(trial_dir)

        # Upload output to S3 if cloud storage is enabled
        if USE_CLOUD_STORAGE:
            # Generate S3 prefix from output_dir path
            # e.g., output_dir: /data/harbor_outputs/run_1_attempt_1
            # s3_prefix: outputs/run_1_attempt_1
            output_basename = Path(output_dir).name
            s3_output_prefix = f"outputs/{output_basename}"
            logger.info(f"Uploading Harbor output to S3: {output_dir} -> {s3_output_prefix}")
            upload_success = upload_directory_to_s3(output_dir, s3_output_prefix)
            if not upload_success:
                logger.warning(f"Failed to upload Harbor output to S3")

        return {
            'success': True,
            'output_path': trial_dir,
            'reward': reward,
            'episodes': episodes,
            'test_results': test_results,
            'error': None
        }

    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': "Harbor execution timed out after 30 minutes",
            'output_path': None,
            'reward': 0.0,
            'episodes': [],
            'test_results': []
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Unexpected error: {str(e)}",
            'output_path': None,
            'reward': 0.0,
            'episodes': [],
            'test_results': []
        }
    finally:
        # Clean up temporary task directory if it was created
        if temp_task_dir and Path(temp_task_dir).exists():
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Cleaning up temporary task directory: {temp_task_dir}")
            shutil.rmtree(temp_task_dir, ignore_errors=True)

def find_trial_directory(output_dir: str) -> Optional[str]:
    """Find the trial directory in Harbor output"""
    import logging
    logger = logging.getLogger(__name__)

    output_path = Path(output_dir)
    logger.info(f"Looking for trial directory in: {output_dir}")

    if not output_path.exists():
        logger.error(f"Output directory does not exist: {output_dir}")
        return None

    # Harbor creates a timestamped directory, then trial directories inside
    # e.g., output/2025-11-21__14-31-23/adaptive-rejection-sampler__R9TeUzR/

    # Find first timestamped directory
    date_dirs = list(output_path.iterdir())
    logger.info(f"Found {len(date_dirs)} items in output_dir: {[d.name for d in date_dirs]}")

    for date_dir in date_dirs:
        if date_dir.is_dir():
            logger.info(f"Checking timestamped directory: {date_dir.name}")
            trial_dirs = list(date_dir.iterdir())
            logger.info(f"Found {len(trial_dirs)} items in date_dir: {[t.name for t in trial_dirs]}")

            # Find first trial directory
            for trial_dir in trial_dirs:
                if trial_dir.is_dir():
                    agent_dir = trial_dir / 'agent'
                    logger.info(f"Checking trial directory: {trial_dir.name}, agent exists: {agent_dir.exists()}")
                    if agent_dir.exists():
                        logger.info(f"Found valid trial directory: {trial_dir}")
                        return str(trial_dir)

    logger.warning(f"No valid trial directory found in {output_dir}")
    return None

def parse_episodes(trial_dir: str) -> List[Dict]:
    """Parse episode files from Harbor output"""
    import logging
    logger = logging.getLogger(__name__)

    episodes = []
    agent_dir = Path(trial_dir) / 'agent'

    logger.info(f"Parsing episodes from trial_dir: {trial_dir}")
    logger.info(f"Agent directory path: {agent_dir}")
    logger.info(f"Agent directory exists: {agent_dir.exists()}")

    if not agent_dir.exists():
        logger.warning(f"Agent directory does not exist: {agent_dir}")
        return episodes

    # Find all episode directories
    all_items = list(agent_dir.iterdir())
    logger.info(f"Items in agent directory: {[item.name for item in all_items]}")

    episode_dirs = sorted([d for d in agent_dir.iterdir() if d.is_dir() and d.name.startswith('episode-')])
    logger.info(f"Found {len(episode_dirs)} episode directories: {[d.name for d in episode_dirs]}")

    for episode_dir in episode_dirs:
        episode_num = int(episode_dir.name.split('-')[1])
        response_file = episode_dir / 'response.txt'

        if response_file.exists():
            try:
                with open(response_file) as f:
                    response_data = json.load(f)
                    episodes.append({
                        'episode_number': episode_num,
                        'analysis': response_data.get('analysis', ''),
                        'plan': response_data.get('plan', ''),
                        'commands': json.dumps(response_data.get('commands', [])),
                        'task_complete': response_data.get('task_complete', False)
                    })
            except json.JSONDecodeError:
                # Skip malformed episode
                continue
            except Exception:
                # Skip any other errors
                continue

    return episodes

def parse_test_results(trial_dir: str) -> List[Dict]:
    """Parse test results from ctrf.json"""
    ctrf_file = Path(trial_dir) / 'verifier' / 'ctrf.json'

    if not ctrf_file.exists():
        return []

    try:
        with open(ctrf_file) as f:
            ctrf_data = json.load(f)
            tests = ctrf_data.get('results', {}).get('tests', [])

            return [{
                'test_name': test.get('name', ''),
                'status': test.get('status', 'unknown'),
                'duration_ms': test.get('duration', 0),
                'error_message': test.get('message', '') if test.get('status') == 'failed' else None
            } for test in tests]
    except Exception:
        return []

def parse_reward(trial_dir: str) -> float:
    """Parse reward from reward.txt"""
    reward_file = Path(trial_dir) / 'verifier' / 'reward.txt'

    if not reward_file.exists():
        return 0.0

    try:
        with open(reward_file) as f:
            reward_str = f.read().strip()
            return float(reward_str)
    except Exception:
        return 0.0
