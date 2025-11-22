export interface Task {
  id: number;
  name: string;
  created_at: string;
}

export interface Attempt {
  id: number;
  attempt_number: number;
  status: string;
  reward: number | null;
  episode_count: number | null;
  tests_passed: number | null;
  tests_total: number | null;
}

export interface Run {
  id: number;
  task_id: number;
  model: string;
  status: string;
  created_at: string;
  attempts: Attempt[];
}

export interface Episode {
  id: number;
  episode_number: number;
  analysis: string | null;
  plan: string | null;
  task_complete: boolean | null;
}

export interface TestResult {
  id: number;
  test_name: string;
  status: string;
  duration_ms: number | null;
  error_message: string | null;
}

export interface RunCreate {
  model: string;
  n_attempts: number;
}
