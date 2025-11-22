'use client';

import { useState, useCallback } from 'react';
import { Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { uploadTask } from '@/lib/api';

interface UploadTaskProps {
  onUploadComplete: () => void;
}

export function UploadTask({ onUploadComplete }: UploadTaskProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(async (file: File) => {
    if (!file.name.endsWith('.zip')) {
      setError('Please upload a .zip file');
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      await uploadTask(file);
      onUploadComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload task');
    } finally {
      setIsUploading(false);
    }
  }, [onUploadComplete]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (file) {
      handleFile(file);
    }
  }, [handleFile]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFile(file);
    }
  }, [handleFile]);

  return (
    <Card
      className={`p-8 border-2 border-dashed transition-colors ${
        isDragging ? 'border-primary bg-primary/5' : 'border-border'
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
    >
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="rounded-full bg-primary/10 p-4">
          <Upload className="h-8 w-8 text-primary" />
        </div>
        <div>
          <h3 className="font-semibold text-lg">Upload Terminal-Bench Task</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Drag and drop a .zip file or click to browse
          </p>
        </div>
        <Button
          variant="outline"
          disabled={isUploading}
          onClick={() => document.getElementById('file-input')?.click()}
        >
          {isUploading ? 'Uploading...' : 'Select File'}
        </Button>
        <input
          id="file-input"
          type="file"
          accept=".zip"
          className="hidden"
          onChange={handleFileInput}
          disabled={isUploading}
        />
        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}
      </div>
    </Card>
  );
}
