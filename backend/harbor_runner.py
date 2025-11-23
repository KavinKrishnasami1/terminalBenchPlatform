"""Harbor execution and output parsing"""
import subprocess
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

def execute_harbor(
    task_path: str,
    model: str,
    output_dir: str,
    openrouter_api_key: str
) -> Dict:
    """
    Execute Harbor for a single attempt

    Returns:
        Dict with keys: success, output_path, reward, episodes, test_results, error
    """
    try:
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
        # Use Docker environment (requires Docker daemon - works on Fly.io)
        cmd = [
            str(harbor_bin), 'run',
            '--path', task_path,
            '--agent', 'terminus-2',
            '--model', model,
            '--jobs-dir', output_dir,
            '--n-attempts', '1',
            '--n-concurrent', '1',
            '--env', 'docker'  # Use Docker environment
        ]

        # Set environment
        env = {
            **os.environ,
            'OPENROUTER_API_KEY': openrouter_api_key,
            'DOCKER_HOST': 'unix:///var/run/docker.sock'  # Ensure Harbor can find Docker
        }

        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Harbor command: {' '.join(cmd)}")
        logger.info(f"Task path: {task_path}")
        logger.info(f"Output dir: {output_dir}")
        logger.info(f"API key length: {len(openrouter_api_key) if openrouter_api_key else 0}")
        logger.info(f"DOCKER_HOST: {env.get('DOCKER_HOST')}")

        # Execute Harbor
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes
        )

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

def find_trial_directory(output_dir: str) -> Optional[str]:
    """Find the trial directory in Harbor output"""
    output_path = Path(output_dir)

    # Harbor creates a timestamped directory, then trial directories inside
    # e.g., output/2025-11-21__14-31-23/adaptive-rejection-sampler__R9TeUzR/

    # Find first timestamped directory
    for date_dir in output_path.iterdir():
        if date_dir.is_dir():
            # Find first trial directory
            for trial_dir in date_dir.iterdir():
                if trial_dir.is_dir() and (trial_dir / 'agent').exists():
                    return str(trial_dir)

    return None

def parse_episodes(trial_dir: str) -> List[Dict]:
    """Parse episode files from Harbor output"""
    episodes = []
    agent_dir = Path(trial_dir) / 'agent'

    if not agent_dir.exists():
        return episodes

    # Find all episode directories
    episode_dirs = sorted([d for d in agent_dir.iterdir() if d.is_dir() and d.name.startswith('episode-')])

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
