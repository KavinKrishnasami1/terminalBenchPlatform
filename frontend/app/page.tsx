'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { UploadTask } from '@/components/upload-task';
import { BulkRunDialog } from '@/components/BulkRunDialog';
import { getTasks, getTaskRuns } from '@/lib/api';
import type { Task, Run } from '@/lib/types';
import { PlayCircle, ArrowRight, CheckCircle2, XCircle, Clock } from 'lucide-react';

export default function HomePage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskRuns, setTaskRuns] = useState<Record<number, Run[]>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [expandedTask, setExpandedTask] = useState<string | null>(null);

  const loadTasks = async () => {
    try {
      const data = await getTasks();
      setTasks(data);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadRunsForTask = async (taskId: number) => {
    if (taskRuns[taskId]) return; // Already loaded

    try {
      const runs = await getTaskRuns(taskId);
      setTaskRuns(prev => ({ ...prev, [taskId]: runs }));
    } catch (error) {
      console.error(`Failed to load runs for task ${taskId}:`, error);
    }
  };

  useEffect(() => {
    loadTasks();
  }, []);

  const getRunStatusBadge = (run: Run) => {
    if (run.status === 'completed') {
      const passedAttempts = run.attempts.filter(a => a.reward === 1.0).length;
      return (
        <Badge variant={passedAttempts > 0 ? 'default' : 'destructive'} className={passedAttempts > 0 ? 'bg-green-600' : ''}>
          {passedAttempts > 0 ? <CheckCircle2 className="mr-1 h-3 w-3" /> : <XCircle className="mr-1 h-3 w-3" />}
          {passedAttempts}/{run.attempts.length} Passed
        </Badge>
      );
    } else if (run.status === 'running') {
      return (
        <Badge variant="secondary">
          <Clock className="mr-1 h-3 w-3" />
          Running
        </Badge>
      );
    } else if (run.status === 'failed') {
      return <Badge variant="destructive">Failed</Badge>;
    } else {
      return <Badge variant="outline">Queued</Badge>;
    }
  };

  return (
    <div className="container mx-auto py-8 px-4 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-4xl font-bold tracking-tight mb-2">
          Terminal-Bench Platform
        </h1>
        <p className="text-muted-foreground">
          Upload tasks and run AI agents with Harbor
        </p>
      </div>

      <div className="mb-8">
        <UploadTask onUploadComplete={loadTasks} />
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-semibold">Your Tasks</h2>
          {tasks.length > 0 && (
            <BulkRunDialog tasks={tasks} onRunsCreated={loadTasks} />
          )}
        </div>
        {isLoading ? (
          <p className="text-muted-foreground">Loading tasks...</p>
        ) : tasks.length === 0 ? (
          <p className="text-muted-foreground">No tasks yet. Upload one to get started!</p>
        ) : (
          <Accordion
            type="single"
            collapsible
            className="space-y-4"
            value={expandedTask || undefined}
            onValueChange={(value) => {
              setExpandedTask(value);
              if (value) {
                const taskId = parseInt(value.replace('task-', ''));
                loadRunsForTask(taskId);
              }
            }}
          >
            {tasks.map((task) => (
              <AccordionItem key={task.id} value={`task-${task.id}`} className="border rounded-lg">
                <Card className="border-0">
                  <div className="px-6 py-4">
                    <div className="flex items-center justify-between">
                      <AccordionTrigger className="hover:no-underline flex-1 py-0">
                        <div className="flex flex-col items-start">
                          <h3 className="text-lg font-semibold">{task.name}</h3>
                          <p className="text-sm text-muted-foreground">
                            Uploaded {new Date(task.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </AccordionTrigger>
                      <Link
                        href={`/tasks/${task.id}`}
                        className="ml-4"
                      >
                        <Button variant="outline" size="sm">
                          <PlayCircle className="mr-2 h-4 w-4" />
                          New Run
                        </Button>
                      </Link>
                    </div>
                  </div>
                  <AccordionContent>
                    <CardContent className="pt-0 pb-4">
                      {!taskRuns[task.id] ? (
                        <p className="text-sm text-muted-foreground">Loading runs...</p>
                      ) : taskRuns[task.id].length === 0 ? (
                        <p className="text-sm text-muted-foreground">No runs yet. Create one to get started!</p>
                      ) : (
                        <div className="space-y-2">
                          <h4 className="text-sm font-semibold mb-2">Runs ({taskRuns[task.id].length})</h4>
                          {taskRuns[task.id].map((run) => (
                            <Link key={run.id} href={`/runs/${run.id}`}>
                              <div className="flex items-center justify-between p-3 rounded-md border hover:bg-accent transition-colors cursor-pointer">
                                <div className="flex items-center gap-3 flex-1">
                                  <div className="flex-1">
                                    <p className="font-medium text-sm">
                                      Run #{run.id}
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                      {run.model} • {new Date(run.created_at).toLocaleString()}
                                    </p>
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  {getRunStatusBadge(run)}
                                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                                </div>
                              </div>
                            </Link>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </AccordionContent>
                </Card>
              </AccordionItem>
            ))}
          </Accordion>
        )}
      </div>
    </div>
  );
}
