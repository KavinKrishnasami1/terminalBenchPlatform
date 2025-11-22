'use client';

import { use, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { AttemptCard } from '@/components/attempt-card';
import { getRun } from '@/lib/api';
import type { Run } from '@/lib/types';
import { RefreshCw } from 'lucide-react';

export default function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [run, setRun] = useState<Run | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadRun = async () => {
    try {
      const data = await getRun(parseInt(id));
      setRun(data);

      // Stop auto-refresh if run is completed or failed
      if (data.status === 'completed' || data.status === 'failed') {
        setAutoRefresh(false);
      }
    } catch (error) {
      console.error('Failed to load run:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadRun();
  }, [id]);

  // Auto-refresh every 3 seconds when run is active
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      loadRun();
    }, 3000);

    return () => clearInterval(interval);
  }, [autoRefresh]);

  if (isLoading || !run) {
    return (
      <div className="container mx-auto py-8 px-4 max-w-7xl">
        <p className="text-muted-foreground">Loading run...</p>
      </div>
    );
  }

  const passedAttempts = run.attempts.filter(a => a.reward === 1.0).length;
  const completedAttempts = run.attempts.filter(a => a.status === 'completed').length;

  return (
    <div className="container mx-auto py-8 px-4 max-w-7xl">
      <div className="mb-8">
        <Button
          variant="ghost"
          onClick={() => router.push('/')}
          className="mb-4"
        >
          ← Back to Tasks
        </Button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold tracking-tight mb-2">
              Run #{run.id}
            </h1>
            <p className="text-muted-foreground">
              Model: {run.model}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={run.status === 'completed' ? 'default' : 'secondary'}>
              {run.status}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={loadRun}
              disabled={isLoading}
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </div>

      <div className="mb-6 p-4 bg-muted rounded-lg">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-2xl font-bold">{completedAttempts}/{run.attempts.length}</p>
            <p className="text-sm text-muted-foreground">Completed</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-green-600">{passedAttempts}</p>
            <p className="text-sm text-muted-foreground">Passed</p>
          </div>
          <div>
            <p className="text-2xl font-bold">
              {completedAttempts > 0 ? `${Math.round(passedAttempts / completedAttempts * 100)}%` : '-'}
            </p>
            <p className="text-sm text-muted-foreground">Success Rate</p>
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-2xl font-semibold mb-4">LLM Attempt Results</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {run.attempts.map((attempt) => (
            <AttemptCard key={attempt.id} attempt={attempt} runId={run.id} />
          ))}
        </div>
      </div>

      {autoRefresh && run.status === 'running' && (
        <div className="mt-4 text-center text-sm text-muted-foreground">
          Auto-refreshing every 3 seconds...
        </div>
      )}
    </div>
  );
}
