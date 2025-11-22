'use client';

import { use, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { ScrollArea } from '@/components/ui/scroll-area';
import { getEpisodes } from '@/lib/api';
import type { Episode } from '@/lib/types';
import { CheckCircle2, XCircle } from 'lucide-react';

export default function AttemptPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadEpisodes = async () => {
      try {
        const data = await getEpisodes(parseInt(id));
        setEpisodes(data);
      } catch (error) {
        console.error('Failed to load episodes:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadEpisodes();
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
                      {episode.task_complete !== null && (
                        <Badge variant={episode.task_complete ? 'default' : 'secondary'}>
                          {episode.task_complete ? (
                            <>
                              <CheckCircle2 className="mr-1 h-3 w-3" />
                              Complete
                            </>
                          ) : (
                            'In Progress'
                          )}
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
                          <pre className="text-sm text-green-400 font-mono">
                            {episode.analysis ?
                              (() => {
                                try {
                                  const commands = JSON.parse(episode.analysis);
                                  return JSON.stringify(commands, null, 2);
                                } catch {
                                  return episode.analysis;
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
