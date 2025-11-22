'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { UploadTask } from '@/components/upload-task';
import { getTasks } from '@/lib/api';
import type { Task } from '@/lib/types';
import { PlayCircle } from 'lucide-react';

export default function HomePage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);

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

  useEffect(() => {
    loadTasks();
  }, []);

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
        <h2 className="text-2xl font-semibold mb-4">Your Tasks</h2>
        {isLoading ? (
          <p className="text-muted-foreground">Loading tasks...</p>
        ) : tasks.length === 0 ? (
          <p className="text-muted-foreground">No tasks yet. Upload one to get started!</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {tasks.map((task) => (
              <Card key={task.id} className="hover:shadow-lg transition-shadow">
                <CardHeader>
                  <CardTitle>{task.name}</CardTitle>
                  <CardDescription>
                    Uploaded {new Date(task.created_at).toLocaleDateString()}
                  </CardDescription>
                  <Link href={`/tasks/${task.id}`}>
                    <Button variant="outline" className="w-full mt-4">
                      <PlayCircle className="mr-2 h-4 w-4" />
                      Run Task
                    </Button>
                  </Link>
                </CardHeader>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
