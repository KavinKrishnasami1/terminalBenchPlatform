import type { Task, Run, RunCreate, Episode } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export async function uploadTask(file: File): Promise<Task> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/api/tasks`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to upload task: ${error}`);
  }

  return response.json();
}

export async function getTasks(): Promise<Task[]> {
  const response = await fetch(`${API_BASE}/api/tasks`);

  if (!response.ok) {
    throw new Error('Failed to fetch tasks');
  }

  return response.json();
}

export async function createRun(taskId: number, data: RunCreate): Promise<Run> {
  const response = await fetch(`${API_BASE}/api/tasks/${taskId}/runs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to create run: ${error}`);
  }

  return response.json();
}

export async function getRun(runId: number): Promise<Run> {
  const response = await fetch(`${API_BASE}/api/runs/${runId}`);

  if (!response.ok) {
    throw new Error('Failed to fetch run');
  }

  return response.json();
}

export async function getEpisodes(attemptId: number): Promise<Episode[]> {
  const response = await fetch(`${API_BASE}/api/attempts/${attemptId}/episodes`);

  if (!response.ok) {
    throw new Error('Failed to fetch episodes');
  }

  return response.json();
}
