import { useEffect, useState, type SyntheticEvent } from 'react';
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Download, X, Copy, FileJson, ExternalLink,
  FileText, Image as ImageIcon, Film, Music, FileIcon
} from 'lucide-react';
import { toast } from "sonner";
import { format } from 'date-fns';
import { withoutPublicApiUrl } from '@/lib/config';
import type { CdnFile } from '@/types/cdn';

type PreviewContentType = 'image' | 'pdf' | 'video' | 'audio' | 'text' | 'other';

type FilePreviewModalProps = {
  file: CdnFile | null;
  open: boolean;
  onClose: () => void;
};

function formatFileSize(bytes?: number): string {
  if (!bytes || bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`;
}

function getContentType(file: CdnFile): PreviewContentType {
  const mime = file.mime_type || '';
  if (mime.startsWith('image/')) return 'image';
  if (mime === 'application/pdf') return 'pdf';
  if (mime.startsWith('video/')) return 'video';
  if (mime.startsWith('audio/')) return 'audio';
  if (
    mime.startsWith('text/') ||
    mime.includes('javascript') ||
    mime.includes('json') ||
    mime.includes('xml') ||
    mime.includes('yaml') ||
    ['js', 'ts', 'jsx', 'tsx', 'css', 'html', 'htm', 'json', 'xml', 'yaml', 'yml', 'md', 'txt', 'csv', 'sh', 'py', 'rb', 'go', 'rs', 'cpp', 'c', 'java', 'php'].includes(file.extension || '')
  ) return 'text';
  return 'other';
}

function ImagePreview({ url, filename }: { url: string; filename?: string }) {
  return (
    <div className="flex items-center justify-center min-h-[300px] bg-[url('data:image/svg+xml,%3Csvg width=%2220%22 height=%2220%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Crect width=%2210%22 height=%2210%22 fill=%22%23f0f0f0%22/%3E%3Crect x=%2210%22 y=%2210%22 width=%2210%22 height=%2210%22 fill=%22%23f0f0f0%22/%3E%3C/svg%3E')] rounded-lg overflow-hidden">
      <img
        src={url}
        alt={filename}
        className="max-w-full max-h-[60vh] object-contain bg-white"
        onError={(e: SyntheticEvent<HTMLImageElement>) => { e.currentTarget.style.display = 'none'; }}
      />
    </div>
  );
}

function PdfPreview({ url }: { url: string }) {
  return (
    <div className="rounded-lg overflow-hidden border border-border bg-muted/20" style={{ height: '65vh' }}>
      <iframe
        src={`${url}#toolbar=1&navpanes=1`}
        className="w-full h-full"
        title="PDF Preview"
      />
    </div>
  );
}

function VideoPreview({ url, mime }: { url: string; mime?: string }) {
  return (
    <div className="rounded-lg overflow-hidden bg-black flex items-center justify-center">
      <video controls className="max-w-full max-h-[60vh]" src={url}>
        <source src={url} type={mime} />
        Your browser does not support video.
      </video>
    </div>
  );
}

function AudioPreview({ url, mime }: { url: string; mime?: string }) {
  return (
    <div className="flex items-center justify-center py-12 bg-muted/20 rounded-lg border border-border">
      <div className="text-center space-y-4">
        <Music className="h-12 w-12 text-primary mx-auto" />
        <audio controls src={url} className="mt-2">
          <source src={url} type={mime} />
        </audio>
      </div>
    </div>
  );
}

function TextPreview({ url, extension }: { url: string; extension?: string }) {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(url)
      .then(r => r.text())
      .then(text => { setContent(text); setLoading(false); })
      .catch(() => { setContent('Failed to load content.'); setLoading(false); });
  }, [url]);

  if (loading) return (
    <div className="flex items-center justify-center py-16">
      <div className="w-5 h-5 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="rounded-lg border border-border overflow-hidden bg-slate-950" style={{ maxHeight: '60vh', overflow: 'auto' }}>
      <div className="flex items-center justify-between px-4 py-2 bg-slate-900 border-b border-slate-700">
        <span className="text-xs text-slate-400 font-mono">{extension?.toUpperCase() || 'TEXT'}</span>
        <button
          onClick={() => { navigator.clipboard.writeText(content); toast.success('Copied!'); }}
          className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
        >
          <Copy className="h-3 w-3" /> Copy
        </button>
      </div>
      <pre className="p-4 text-xs text-slate-200 font-mono whitespace-pre-wrap overflow-x-auto leading-relaxed">
        {content}
      </pre>
    </div>
  );
}

function OtherPreview({ file }: { file: CdnFile }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4 bg-white rounded-lg border border-dashed border-border">
      <FileIcon className="h-16 w-16 text-muted-foreground/40" />
      <div className="text-center">
        <p className="font-medium text-foreground">{file.filename}</p>
        <p className="text-sm text-muted-foreground mt-1">{file.mime_type || 'Unknown type'}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{formatFileSize(file.size_bytes)}</p>
      </div>
      <p className="text-sm text-muted-foreground">Preview not available for this file type.</p>
    </div>
  );
}

export default function FilePreviewModal({ file, open, onClose }: FilePreviewModalProps) {
  if (!file) return null;

  const contentType = getContentType(file);
  const previewUrl = file.api_inline_url || file.cdn_url || file.raw_url || '';
  const downloadUrl = file.api_attachment_url || file.api_download_url || file.cdn_url || '';

  const handleDownload = () => window.open(downloadUrl, '_blank');

  const handleExportMetadata = () => {
    const meta = {
      id: file.id,
      filename: file.filename,
      original_filename: file.original_filename,
      mime_type: file.mime_type,
      category: file.category,
      extension: file.extension,
      size_bytes: file.size_bytes,
      cdn_folder: file.cdn_folder,
      uploaded_at: file.uploaded_at,
      cdn_url: file.cdn_url,
      raw_url: file.raw_url,
      download_url: file.download_url,
      api_download_url: file.api_download_url,
      api_preview_url: file.api_preview_url,
      metadata_url: file.metadata_url,
      telegram: file.telegram,
      github: file.github,
      metadata: file.metadata,
    };
    const blob = new Blob([JSON.stringify(meta, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${file.filename || file.id}_metadata.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success('Metadata exported');
  };

  const handleCopyCdnUrl = () => {
    navigator.clipboard.writeText(file.cdn_url || '');
    toast.success('CDN URL copied');
  };

  const formatDate = (str?: string) => {
    if (!str) return '—';
    try { return format(new Date(str), 'MMM d, yyyy hh:mm a'); } catch { return str; }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent hideClose className="max-w-4xl w-full p-0 gap-0 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-card">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-sm truncate">{file.filename || file.original_filename}</p>
              <div className="flex items-center gap-2 mt-0.5">
                <Badge variant="secondary" className="text-xs capitalize">{file.category || file.extension || '—'}</Badge>
                <span className="text-xs text-muted-foreground">{formatFileSize(file.size_bytes)}</span>
                {file.cdn_folder && <span className="text-xs text-muted-foreground">· {file.cdn_folder}</span>}
                <span className="text-xs text-muted-foreground">· {formatDate(file.uploaded_at)}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 ml-4 shrink-0">
            <Button size="sm" variant="outline" onClick={handleCopyCdnUrl} className="h-8 text-xs gap-1.5">
              <Copy className="h-3.5 w-3.5" /> CDN URL
            </Button>
            <Button size="sm" variant="outline" onClick={handleExportMetadata} className="h-8 text-xs gap-1.5">
              <FileJson className="h-3.5 w-3.5" /> Export JSON
            </Button>
            <Button size="sm" variant="outline" onClick={() => window.open(previewUrl, '_blank')} className="h-8 text-xs gap-1.5">
              <ExternalLink className="h-3.5 w-3.5" /> Open
            </Button>
            <Button size="sm" onClick={handleDownload} className="h-8 text-xs gap-1.5">
              <Download className="h-3.5 w-3.5" /> Download
            </Button>
            <Button size="icon" variant="ghost" className="h-8 w-8" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Preview area */}
        <div className="p-5 bg-background overflow-auto" style={{ maxHeight: '75vh' }}>
          {contentType === 'image' && <ImagePreview url={previewUrl} filename={file.filename} />}
          {contentType === 'pdf' && <PdfPreview url={previewUrl} />}
          {contentType === 'video' && <VideoPreview url={previewUrl} mime={file.mime_type} />}
          {contentType === 'audio' && <AudioPreview url={previewUrl} mime={file.mime_type} />}
          {contentType === 'text' && <TextPreview url={previewUrl} extension={file.extension} />}
          {contentType === 'other' && <OtherPreview file={file} />}
        </div>

        {/* Metadata footer */}
        <div className="border-t border-border bg-white px-5 py-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div>
              <p className="text-muted-foreground">MIME Type</p>
              <p className="font-mono font-medium truncate">{file.mime_type || '—'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">File ID</p>
              <p className="font-mono font-medium truncate">{file.id || '—'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Storage</p>
              <p className="font-medium capitalize">{file.github ? 'GitHub' : 'telegram'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">CDN URL</p>
              <p className="font-mono truncate text-primary cursor-pointer" onClick={handleCopyCdnUrl} title={file.cdn_url}>
                {file.cdn_url ? withoutPublicApiUrl(file.cdn_url) : '—'}
              </p>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
