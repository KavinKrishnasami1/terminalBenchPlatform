'use client';

import { use, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { createRun } from '@/lib/api';
import { PlayCircle } from 'lucide-react';

export default function TaskPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [isCreating, setIsCreating] = useState(false);
  const [model, setModel] = useState('openrouter/anthropic/claude-sonnet-4.5');
  const [nAttempts, setNAttempts] = useState(10);
  const [error, setError] = useState<string | null>(null);

  const handleCreateRun = async () => {
    setIsCreating(true);
    setError(null);

    try {
      const run = await createRun(parseInt(id), { model, n_attempts: nAttempts });
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create run');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="container mx-auto py-8 px-4 max-w-4xl">
      <div className="mb-8">
        <Button
          variant="ghost"
          onClick={() => router.push('/')}
          className="mb-4"
        >
          ← Back to Tasks
        </Button>
        <h1 className="text-4xl font-bold tracking-tight mb-2">
          Create New Run
        </h1>
        <p className="text-muted-foreground">
          Configure and start a new Harbor execution
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Run Configuration</CardTitle>
          <CardDescription>
            Set up the model and number of attempts for this run
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="model">Model</Label>
            <Input
              id="model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="openrouter/anthropic/claude-sonnet-4.5"
            />
            <p className="text-sm text-muted-foreground">
              OpenRouter model identifier (e.g., openrouter/anthropic/claude-sonnet-4.5)
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="attempts">Number of Attempts</Label>
            <Input
              id="attempts"
              type="number"
              min={1}
              max={25}
              value={nAttempts}
              onChange={(e) => setNAttempts(parseInt(e.target.value))}
            />
            <p className="text-sm text-muted-foreground">
              How many times to run the agent (1-25)
            </p>
          </div>

          {error && (
            <div className="p-4 bg-destructive/10 text-destructive rounded-md">
              {error}
            </div>
          )}

          <Button
            onClick={handleCreateRun}
            disabled={isCreating}
            className="w-full"
            size="lg"
          >
            <PlayCircle className="mr-2 h-5 w-5" />
            {isCreating ? 'Starting Run...' : `Start Run (${nAttempts} attempts)`}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
