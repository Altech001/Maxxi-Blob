import { useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Upload, FileIcon, X, CheckCircle2, AlertCircle, LucideUploadCloud } from 'lucide-react';
import { maxxiApi } from '@/lib/maxxiApi';
import { toast } from "sonner";
import type { UploadProgressState } from '@/types/cdn';

type UploadDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  folder?: string | null;
  folderId?: number | null;
  onUploadComplete: () => void;
};

type UploadProgress = Record<number, UploadProgressState>;

export default function UploadDialog({ open, onOpenChange, folder = null, folderId = null, onUploadComplete }: UploadDialogProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<UploadProgress>({});
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files);
    setFiles(prev => [...prev, ...dropped]);
  };

  const handleSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files ?? []);
    setFiles(prev => [...prev, ...selected]);
    e.target.value = '';
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    const newProgress: UploadProgress = {};

    for (let i = 0; i < files.length; i++) {
      newProgress[i] = 'uploading';
      setProgress({ ...newProgress });
      try {
        await maxxiApi.uploadFile(files[i], folderId);
        newProgress[i] = 'done';
      } catch (err) {
        newProgress[i] = 'error';
      }
      setProgress({ ...newProgress });
    }

    const doneCount = Object.values(newProgress).filter(v => v === 'done').length;
    const errorCount = Object.values(newProgress).filter(v => v === 'error').length;

    if (doneCount > 0) toast.success(`${doneCount} file(s) uploaded successfully`);
    if (errorCount > 0) toast.error(`${errorCount} file(s) failed to upload`);

    setUploading(false);
    setTimeout(() => {
      setFiles([]);
      setProgress({});
      onOpenChange(false);
      onUploadComplete();
    }, 800);
  };

  const handleClose = () => {
    if (!uploading) {
      setFiles([]);
      setProgress({});
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            <LucideUploadCloud className="inline-block mr-2 mb-1" />
            Upload Files</DialogTitle>
        </DialogHeader>

        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => !uploading && inputRef.current?.click()}
          className="border-2 border-dashed border-border rounded-xl p-10 text-center cursor-pointer hover:border-primary/40 hover:bg-primary/5 transition-all"
        >
          <Upload className="h-8 w-8 mx-auto text-muted-foreground mb-3" strokeWidth={1.5} />
          <p className="text-sm font-medium text-foreground">Drop files here or click to browse</p>
          <p className="text-xs text-muted-foreground mt-1">Target: {folder || 'All Files'}</p>
          <input
            ref={inputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleSelect}
          />
        </div>

        {files.length > 0 && (
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {files.map((file, i) => {
              const state = progress[i];
              return (
                <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-muted/50">
                  <FileIcon className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="text-sm flex-1 truncate">{file.name}</span>
                  <span className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</span>
                  {state === 'uploading' && (
                    <div className="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                  )}
                  {state === 'done' && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
                  {state === 'error' && <AlertCircle className="h-4 w-4 text-destructive" />}
                  {!state && (
                    <button onClick={() => removeFile(i)} className="text-muted-foreground hover:text-foreground">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={uploading}>
            Cancel
          </Button>
          <Button onClick={handleUpload} disabled={uploading || files.length === 0}>
            {uploading ? 'Uploading…' : `Upload ${files.length} file(s)`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
