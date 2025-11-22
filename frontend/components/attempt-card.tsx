'use client';

import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { Attempt } from '@/lib/types';
import { CheckCircle2, XCircle, Clock, Eye } from 'lucide-react';

interface AttemptCardProps {
  attempt: Attempt;
  runId: number;
}

export function AttemptCard({ attempt, runId }: AttemptCardProps) {
  const getStatusBadge = () => {
    switch (attempt.status) {
      case 'completed':
        if (attempt.reward === 1.0) {
          return (
            <Badge className="bg-green-500 hover:bg-green-600">
              <CheckCircle2 className="mr-1 h-3 w-3" />
              AGENT PASSED
            </Badge>
          );
        }
        return (
          <Badge variant="destructive">
            <XCircle className="mr-1 h-3 w-3" />
            AGENT FAILED
          </Badge>
        );
      case 'running':
        return (
          <Badge variant="outline" className="border-blue-500 text-blue-500">
            <Clock className="mr-1 h-3 w-3 animate-spin" />
            running
          </Badge>
        );
      case 'queued':
        return <Badge variant="secondary">queued</Badge>;
      default:
        return <Badge variant="outline">{attempt.status}</Badge>;
    }
  };

  return (
    <Card className={`${
      attempt.reward === 1.0 ? 'border-green-200 bg-green-50/30' :
      attempt.status === 'completed' ? 'border-red-200 bg-red-50/30' : ''
    }`}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Attempt {attempt.attempt_number}</CardTitle>
          <div className="flex items-center gap-2">
            {getStatusBadge()}
            <Badge variant="outline">{attempt.status}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="flex justify-between items-center text-sm">
            <span className="text-muted-foreground">Test Pass Rate</span>
            {attempt.tests_total !== null && attempt.tests_passed !== null ? (
              <span className="font-mono font-semibold">
                {attempt.tests_passed}/{attempt.tests_total} passed
              </span>
            ) : (
              <span className="text-muted-foreground">-</span>
            )}
          </div>

          <div className="flex justify-between items-center text-sm">
            <span className="text-muted-foreground">Episodes</span>
            <span className="font-mono">
              {attempt.episode_count !== null ? `(${attempt.episode_count})` : '-'}
            </span>
          </div>

          {attempt.status === 'completed' && (
            <Link href={`/attempts/${attempt.id}`}>
              <Button variant="outline" className="w-full mt-2">
                <Eye className="mr-2 h-4 w-4" />
                View Details
              </Button>
            </Link>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
