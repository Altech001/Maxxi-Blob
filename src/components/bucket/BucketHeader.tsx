import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Copy, Box } from 'lucide-react';
import { toast } from "sonner";
import type { Bucket, CdnFile } from '@/types/cdn';

type BucketHeaderProps = {
  bucket: Bucket;
  files: CdnFile[];
};

function formatTotalSize(bytes: number): string {
  if (!bytes || bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`;
}

export default function BucketHeader({ bucket, files }: BucketHeaderProps) {
  const totalSize = files.reduce((acc, f) => acc + (f.size_bytes || 0), 0);
  const totalVersions = files.length;
  const storageBreakdown = `Standard: ${formatTotalSize(totalSize)}`;

  const copyUrl = () => {
    navigator.clipboard.writeText(bucket.public_url || `https://${bucket.name}.t3.tigrisfiles.io`);
    toast.success('URL copied!');
  };

  return (
    <div className="rounded-xl border border-border bg-gradient-to-r from-violet-50/40 via-white to-white p-6 mb-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2.5 mb-2">
            <Box className="h-5 w-5 text-muted-foreground" strokeWidth={1.5} />
            <h1 className="text-xl font-bold text-foreground">{bucket.name}</h1>
          </div>
          {bucket.snapshot_enabled && (
            <Badge variant="secondary" className="text-xs bg-emerald-50 text-emerald-700 border-emerald-200 mb-2">
              Snapshot Enabled
            </Badge>
          )}
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground mb-3">
            <span>Public access URL:</span>
            <span className="text-foreground font-medium">
              {bucket.public_url || `https://${bucket.name}.t3.tigrisfiles.io`}
            </span>
            <button onClick={copyUrl} className="text-muted-foreground hover:text-foreground transition-colors">
              <Copy className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{totalVersions} all versions</span>
            <span>·</span>
            <span>{files.length} objects</span>
            <span>·</span>
            <span>{formatTotalSize(totalSize)}</span>
            <span>·</span>
            <span>{storageBreakdown}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm">Share</Button>
          <Button variant="outline" size="sm">Settings</Button>
        </div>
      </div>
    </div>
  );
}
