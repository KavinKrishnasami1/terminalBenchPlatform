'use client';

import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { PlayCircle, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { Task } from '@/lib/types';
import { createRun } from '@/lib/api';

interface TaskConfig {
  task: Task;
  enabled: boolean;
  nAttempts: number;
}

interface BulkRunDialogProps {
  tasks: Task[];
  onRunsCreated?: () => void;
}

export function BulkRunDialog({ tasks, onRunsCreated }: BulkRunDialogProps) {
  const [open, setOpen] = useState(false);
  const [model, setModel] = useState('openrouter/anthropic/claude-sonnet-4.5');
  const [taskConfigs, setTaskConfigs] = useState<TaskConfig[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionStatus, setExecutionStatus] = useState<Record<number, 'pending' | 'running' | 'success' | 'error'>>({});
  const [error, setError] = useState<string | null>(null);

  // Initialize task configs when dialog opens
  useEffect(() => {
    if (open) {
      setTaskConfigs(
        tasks.map(task => ({
          task,
          enabled: false,
          nAttempts: 10
        }))
      );
      setExecutionStatus({});
      setError(null);
    }
  }, [open, tasks]);

  const toggleTask = (taskId: number) => {
    setTaskConfigs(prev =>
      prev.map(config =>
        config.task.id === taskId
          ? { ...config, enabled: !config.enabled }
          : config
      )
    );
  };

  const updateAttempts = (taskId: number, attempts: number) => {
    setTaskConfigs(prev =>
      prev.map(config =>
        config.task.id === taskId
          ? { ...config, nAttempts: Math.max(1, Math.min(25, attempts)) }
          : config
      )
    );
  };

  const selectedTasks = taskConfigs.filter(config => config.enabled);
  const totalAttempts = selectedTasks.reduce((sum, config) => sum + config.nAttempts, 0);

  const handleExecute = async () => {
    if (selectedTasks.length === 0) {
      setError('Please select at least one task');
      return;
    }

    setIsExecuting(true);
    setError(null);

    // Initialize all tasks as pending
    const initialStatus: Record<number, 'pending' | 'running' | 'success' | 'error'> = {};
    selectedTasks.forEach(config => {
      initialStatus[config.task.id] = 'pending';
    });
    setExecutionStatus(initialStatus);

    try {
      // Create runs concurrently
      const runPromises = selectedTasks.map(async (config) => {
        setExecutionStatus(prev => ({ ...prev, [config.task.id]: 'running' }));

        try {
          await createRun(config.task.id, {
            model,
            n_attempts: config.nAttempts
          });
          setExecutionStatus(prev => ({ ...prev, [config.task.id]: 'success' }));
        } catch (err) {
          setExecutionStatus(prev => ({ ...prev, [config.task.id]: 'error' }));
          throw err;
        }
      });

      await Promise.all(runPromises);

      // Success - wait a moment then close and refresh
      setTimeout(() => {
        setOpen(false);
        onRunsCreated?.();
      }, 1500);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create runs');
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="lg" className="gap-2">
          <PlayCircle className="h-5 w-5" />
          Run Multiple Tasks
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-3xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle>Bulk Concurrent Execution</DialogTitle>
          <DialogDescription>
            Select tasks and configure concurrent execution. All runs will be executed in parallel.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Model Configuration */}
          <div className="space-y-2">
            <Label htmlFor="bulk-model">Model</Label>
            <Input
              id="bulk-model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="openrouter/anthropic/claude-sonnet-4.5"
              disabled={isExecuting}
            />
            <p className="text-sm text-muted-foreground">
              OpenRouter model identifier (applies to all tasks)
            </p>
          </div>

          {/* Task Selection */}
          <div className="space-y-2">
            <Label>Select Tasks</Label>
            <ScrollArea className="h-[300px] border rounded-md p-4">
              <div className="space-y-3">
                {taskConfigs.map((config) => (
                  <Card
                    key={config.task.id}
                    className={`transition-colors ${
                      config.enabled ? 'border-primary bg-primary/5' : ''
                    }`}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-start gap-4">
                        <input
                          type="checkbox"
                          checked={config.enabled}
                          onChange={() => toggleTask(config.task.id)}
                          disabled={isExecuting}
                          className="mt-1 h-4 w-4 rounded border-gray-300"
                        />

                        <div className="flex-1 space-y-3">
                          <div>
                            <div className="font-medium">{config.task.name}</div>
                            <div className="text-sm text-muted-foreground">
                              ID: {config.task.id} • Created: {new Date(config.task.created_at).toLocaleDateString()}
                            </div>
                          </div>

                          {config.enabled && (
                            <div className="flex items-center gap-3">
                              <Label htmlFor={`attempts-${config.task.id}`} className="text-sm">
                                Attempts:
                              </Label>
                              <Input
                                id={`attempts-${config.task.id}`}
                                type="number"
                                min={1}
                                max={25}
                                value={config.nAttempts}
                                onChange={(e) => updateAttempts(config.task.id, parseInt(e.target.value) || 1)}
                                disabled={isExecuting}
                                className="w-20"
                              />
                            </div>
                          )}

                          {/* Execution Status */}
                          {executionStatus[config.task.id] && (
                            <div className="flex items-center gap-2">
                              {executionStatus[config.task.id] === 'pending' && (
                                <Badge variant="secondary">Pending</Badge>
                              )}
                              {executionStatus[config.task.id] === 'running' && (
                                <>
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                  <Badge>Creating run...</Badge>
                                </>
                              )}
                              {executionStatus[config.task.id] === 'success' && (
                                <>
                                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                                  <Badge variant="outline" className="border-green-600 text-green-600">
                                    Run created
                                  </Badge>
                                </>
                              )}
                              {executionStatus[config.task.id] === 'error' && (
                                <>
                                  <XCircle className="h-4 w-4 text-red-600" />
                                  <Badge variant="destructive">Failed</Badge>
                                </>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          </div>

          {/* Summary */}
          {selectedTasks.length > 0 && (
            <div className="bg-muted p-4 rounded-md space-y-1">
              <div className="font-medium">Execution Summary</div>
              <div className="text-sm text-muted-foreground">
                {selectedTasks.length} task{selectedTasks.length !== 1 ? 's' : ''} selected •{' '}
                {totalAttempts} total concurrent attempt{totalAttempts !== 1 ? 's' : ''}
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="p-4 bg-destructive/10 text-destructive rounded-md text-sm">
              {error}
            </div>
          )}

          {/* Action Button */}
          <Button
            onClick={handleExecute}
            disabled={isExecuting || selectedTasks.length === 0}
            className="w-full"
            size="lg"
          >
            {isExecuting ? (
              <>
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                Creating Runs...
              </>
            ) : (
              <>
                <PlayCircle className="mr-2 h-5 w-5" />
                Execute {selectedTasks.length > 0 && `(${totalAttempts} concurrent attempts)`}
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
