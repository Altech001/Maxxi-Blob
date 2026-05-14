import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, FileIcon, Upload, X } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { maxxiApi } from '@/lib/maxxiApi';

type UploadStatus = 'queued' | 'uploading' | 'done' | 'error';

type UploadQueueItem = {
  id: string;
  file: File;
  status: UploadStatus;
  progress: number;
  previewUrl?: string;
  error?: string;
};

function formatFileSize(bytes?: number): string {
  if (!bytes || bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`;
}

function createUploadId(file: File): string {
  const randomId = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);
  return `${file.name}-${file.size}-${file.lastModified}-${randomId}`;
}

function getBucketFromPath(pathname: string): string | null {
  if (!pathname.startsWith('/buckets/')) return null;
  return decodeURIComponent(pathname.split('/buckets/')[1] || '') || null;
}

export default function GlobalUploadDropzone() {
  const location = useLocation();
  const queryClient = useQueryClient();
  const bucket = getBucketFromPath(location.pathname);
  const targetLabel = bucket || 'All Files';
  const [isDraggingFiles, setIsDraggingFiles] = useState(false);
  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([]);
  const dragDepthRef = useRef(0);
  const queueStartedRef = useRef(new Set<string>());

  const { data: folderData } = useQuery({
    queryKey: ['api-files-folder', bucket],
    queryFn: () => maxxiApi.listFiles(bucket),
    enabled: !!bucket,
    staleTime: 30_000,
  });

  const detectedFolderId = folderData?.files?.find((file) => file.folder_id != null)?.folder_id ?? null;

  const uploadSummary = useMemo(() => {
    const total = uploadQueue.length;
    const completed = uploadQueue.filter((item) => item.status === 'done' || item.status === 'error').length;
    const failed = uploadQueue.filter((item) => item.status === 'error').length;
    const average = total ? Math.round(uploadQueue.reduce((acc, item) => acc + item.progress, 0) / total) : 0;
    return { total, completed, failed, average };
  }, [uploadQueue]);

  const refreshFiles = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['api-files'] });
    if (bucket) {
      queryClient.invalidateQueries({ queryKey: ['api-files-folder', bucket] });
    }
  }, [bucket, queryClient]);

  const enqueueUploads = useCallback((incomingFiles: File[]) => {
    if (incomingFiles.length === 0) return;

    const nextItems = incomingFiles.map((file) => ({
      id: createUploadId(file),
      file,
      status: 'queued' as const,
      progress: 0,
      previewUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
    }));

    setUploadQueue(prev => {
      const combined = [...nextItems, ...prev];
      combined.slice(24).forEach((item) => {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
        queueStartedRef.current.delete(item.id);
      });
      return combined.slice(0, 24);
    });

    toast.success(`${incomingFiles.length} file(s) queued for ${targetLabel}`);
  }, [targetLabel]);

  useEffect(() => {
    const next = uploadQueue.find((item) => item.status === 'queued' && !queueStartedRef.current.has(item.id));
    if (!next) return;

    queueStartedRef.current.add(next.id);
    let cancelled = false;

    const run = async () => {
      setUploadQueue(prev => prev.map((item) => item.id === next.id ? { ...item, status: 'uploading', progress: 12 } : item));
      const timer = window.setInterval(() => {
        setUploadQueue(prev => prev.map((item) => {
          if (item.id !== next.id || item.status !== 'uploading') return item;
          return { ...item, progress: Math.min(item.progress + 9, 88) };
        }));
      }, 350);

      try {
        await maxxiApi.uploadFile(next.file, bucket ? detectedFolderId : null);
        if (!cancelled) {
          setUploadQueue(prev => prev.map((item) => item.id === next.id ? { ...item, status: 'done', progress: 100 } : item));
          refreshFiles();
        }
      } catch (error) {
        if (!cancelled) {
          setUploadQueue(prev => prev.map((item) => item.id === next.id ? {
            ...item,
            status: 'error',
            progress: 100,
            error: error instanceof Error ? error.message : 'Upload failed',
          } : item));
        }
      } finally {
        window.clearInterval(timer);
      }
    };

    run();

    return () => {
      cancelled = true;
    };
  }, [bucket, detectedFolderId, refreshFiles, uploadQueue]);

  useEffect(() => {
    const hasFiles = (event: DragEvent) => Array.from(event.dataTransfer?.types ?? []).includes('Files');

    const handleDragEnter = (event: DragEvent) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      dragDepthRef.current += 1;
      setIsDraggingFiles(true);
    };

    const handleDragOver = (event: DragEvent) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
    };

    const handleDragLeave = (event: DragEvent) => {
      if (!hasFiles(event)) return;
      dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
      if (dragDepthRef.current === 0) setIsDraggingFiles(false);
    };

    const handleDrop = (event: DragEvent) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      dragDepthRef.current = 0;
      setIsDraggingFiles(false);
      enqueueUploads(Array.from(event.dataTransfer?.files ?? []));
    };

    window.addEventListener('dragenter', handleDragEnter);
    window.addEventListener('dragover', handleDragOver);
    window.addEventListener('dragleave', handleDragLeave);
    window.addEventListener('drop', handleDrop);

    return () => {
      window.removeEventListener('dragenter', handleDragEnter);
      window.removeEventListener('dragover', handleDragOver);
      window.removeEventListener('dragleave', handleDragLeave);
      window.removeEventListener('drop', handleDrop);
    };
  }, [enqueueUploads]);

  const clearFinishedUploads = () => {
    setUploadQueue(prev => {
      const finished = prev.filter((item) => item.status === 'done' || item.status === 'error');
      finished.forEach((item) => {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
        queueStartedRef.current.delete(item.id);
      });
      return prev.filter((item) => item.status !== 'done' && item.status !== 'error');
    });
  };

  const clearUploadQueue = () => {
    setUploadQueue(prev => {
      prev.forEach((item) => {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
        queueStartedRef.current.delete(item.id);
      });
      return [];
    });
  };

  return (
    <>
      {isDraggingFiles && (
        <div className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm">
          <div className="absolute inset-4 flex items-center justify-center rounded-2xl border-2 border-dashed border-primary bg-primary/10">
            <div className="text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg">
                <Upload className="h-7 w-7" />
              </div>
              <p className="text-lg font-semibold">Drop to upload into {targetLabel}</p>
              <p className="text-sm text-muted-foreground">
                {bucket ? 'The bucket target is detected from this page.' : 'Files will upload to the global/root CDN target.'}
              </p>
            </div>
          </div>
        </div>
      )}

      {uploadQueue.length > 0 && (
        <div className="fixed bottom-5 right-5 z-50 w-[min(420px,calc(100vw-2rem))] rounded-xl border border-border bg-background shadow-2xl">
          <div className="border-b border-border p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">Uploading to {targetLabel}</p>
                <p className="text-xs text-muted-foreground">
                  {uploadSummary.completed}/{uploadSummary.total} complete
                  {uploadSummary.failed > 0 ? ` · ${uploadSummary.failed} failed` : ''}
                </p>
              </div>
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" className="h-8 px-2" onClick={clearFinishedUploads}>
                  Clear
                </Button>
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={clearUploadQueue}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <Progress value={uploadSummary.average} className="mt-3 h-2" />
          </div>
          <div className="max-h-72 overflow-y-auto p-2">
            {uploadQueue.map((item) => (
              <div key={item.id} className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-muted/60">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-md border border-border bg-muted">
                  {item.previewUrl ? (
                    <img src={item.previewUrl} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <FileIcon className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-medium">{item.file.name}</p>
                    <span className="text-xs text-muted-foreground">{formatFileSize(item.file.size)}</span>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <Progress value={item.progress} className="h-1.5" />
                    {item.status === 'uploading' && <div className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />}
                    {item.status === 'done' && <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />}
                    {item.status === 'error' && <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />}
                  </div>
                  {item.error && <p className="mt-1 truncate text-xs text-destructive">{item.error}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
