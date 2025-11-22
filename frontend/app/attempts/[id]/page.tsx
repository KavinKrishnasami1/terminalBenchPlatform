'use client';

import { use, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { ScrollArea } from '@/components/ui/scroll-area';
import { getEpisodes, getTestResults } from '@/lib/api';
import type { Episode, TestResult } from '@/lib/types';
import { CheckCircle2, XCircle } from 'lucide-react';

export default function AttemptPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [episodesData, testsData] = await Promise.all([
          getEpisodes(parseInt(id)),
          getTestResults(parseInt(id))
        ]);

        // Sort episodes numerically by episode_number
        const sortedEpisodes = episodesData.sort((a, b) => a.episode_number - b.episode_number);
        setEpisodes(sortedEpisodes);
        setTestResults(testsData);
      } catch (error) {
        console.error('Failed to load data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [id]);

  if (isLoading) {
    return (
      <div className="container mx-auto py-8 px-4 max-w-6xl">
        <p className="text-muted-foreground">Loading episodes...</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 px-4 max-w-6xl">
      <div className="mb-8">
        <Button
          variant="ghost"
          onClick={() => router.back()}
          className="mb-4"
        >
          ← Back to Run
        </Button>
        <h1 className="text-4xl font-bold tracking-tight mb-2">
          Attempt Details
        </h1>
        <p className="text-muted-foreground">
          View episode-by-episode execution trace
        </p>
      </div>

      {testResults.length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>
              Test Results ({testResults.filter(t => t.status === 'passed').length}/{testResults.length} passed)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {testResults.map((test) => (
                <div
                  key={test.id}
                  className={`flex items-center justify-between p-3 rounded-md border ${
                    test.status === 'passed'
                      ? 'bg-green-50 border-green-200'
                      : test.status === 'failed'
                      ? 'bg-red-50 border-red-200'
                      : 'bg-gray-50 border-gray-200'
                  }`}
                >
                  <div className="flex items-center gap-3 flex-1">
                    {test.status === 'passed' ? (
                      <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="font-mono text-sm font-medium truncate">
                        {test.test_name}
                      </p>
                      {test.error_message && (
                        <p className="text-xs text-red-600 mt-1 truncate">
                          {test.error_message}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {test.duration_ms && (
                      <span className="text-xs text-muted-foreground">
                        {Math.round(test.duration_ms * 1000)}ms
                      </span>
                    )}
                    <Badge
                      variant={test.status === 'passed' ? 'default' : 'destructive'}
                      className={test.status === 'passed' ? 'bg-green-600' : ''}
                    >
                      {test.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Episodes ({episodes.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {episodes.length === 0 ? (
            <p className="text-muted-foreground">No episodes found</p>
          ) : (
            <Accordion type="single" collapsible className="w-full">
              {episodes.map((episode) => (
                <AccordionItem key={episode.id} value={`episode-${episode.id}`}>
                  <AccordionTrigger className="hover:no-underline">
                    <div className="flex items-center justify-between w-full pr-4">
                      <span className="font-semibold">Episode {episode.episode_number}</span>
                      {episode.task_complete === true && (
                        <Badge variant="default" className="bg-green-600">
                          <CheckCircle2 className="mr-1 h-3 w-3" />
                          Task Complete
                        </Badge>
                      )}
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-4 pt-4">
                      {episode.analysis && (
                        <div>
                          <h4 className="font-semibold mb-2">State Analysis:</h4>
                          <ScrollArea className="h-[200px] rounded-md border p-4">
                            <p className="text-sm whitespace-pre-wrap">{episode.analysis}</p>
                          </ScrollArea>
                        </div>
                      )}

                      {episode.plan && (
                        <div>
                          <h4 className="font-semibold mb-2">Explanation:</h4>
                          <ScrollArea className="h-[200px] rounded-md border p-4">
                            <p className="text-sm whitespace-pre-wrap">{episode.plan}</p>
                          </ScrollArea>
                        </div>
                      )}

                      <div>
                        <h4 className="font-semibold mb-2">Commands:</h4>
                        <ScrollArea className="h-[300px] rounded-md border bg-slate-950 p-4">
                          <pre className="text-sm text-green-400 font-mono whitespace-pre-wrap break-words">
                            {episode.commands ?
                              (() => {
                                try {
                                  const commands = JSON.parse(episode.commands);
                                  return JSON.stringify(commands, null, 2);
                                } catch {
                                  return episode.commands;
                                }
                              })() :
                              'No commands'
                            }
                          </pre>
                        </ScrollArea>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
