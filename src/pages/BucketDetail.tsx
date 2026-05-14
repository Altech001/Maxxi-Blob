import { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, Settings, Trash2 } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { toast } from "sonner";


import FileTable from '../components/bucket/FileTable';
import UploadDialog from '../components/bucket/UploadDialog';
import FilePreviewModal from '@/components/bucket/FilePreviewModal';
import { maxxiApi } from '@/lib/maxxiApi';
import { publicApiUrl } from '@/lib/config';
import type { CdnFile } from '@/types/cdn';

type PendingDelete =
  | { type: 'single'; fileId: string; folderId?: number | null; label: string }
  | { type: 'bulk'; files: CdnFile[] };

function formatTotalSize(bytes: number): string {
  if (!bytes || bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`;
}

function getFileLabel(file: CdnFile): string {
  return file.filename || file.original_filename || file.id;
}

export default function BucketDetail() {
  // The "folder" name is the last segment of the path: /buckets/:folder
  const folder = decodeURIComponent(window.location.pathname.split('/buckets/')[1] || '');

  const [search, setSearch] = useState('');
  const [showUpload, setShowUpload] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [previewFile, setPreviewFile] = useState<CdnFile | null>(null);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [policyPublicRead, setPolicyPublicRead] = useState(true);
  const [policyAllowList, setPolicyAllowList] = useState(true);
  const [policyAllowUploads, setPolicyAllowUploads] = useState(false);
  const queryClient = useQueryClient();

  const { data: apiData, isLoading } = useQuery({
    queryKey: ['api-files-folder', folder],
    queryFn: () => maxxiApi.listFiles(folder || null),
    enabled: true,
  });

  const files = apiData?.files ?? [];
  const detectedFolderId = files.find((file) => file.folder_id != null)?.folder_id ?? null;

  const filteredFiles = files.filter((f) => {
    if (!search) return true;
    return (f.filename || f.original_filename || '').toLowerCase().includes(search.toLowerCase());
  });

  const totalSize = files.reduce((acc, f) => acc + (f.size_bytes || 0), 0);
  const selectedFileRecords = files.filter((file) => selectedFiles.includes(file.id));

  const bucketPolicy = useMemo(() => {
    const bucketName = folder || '*';
    const actions = [
      policyPublicRead && 'files:read',
      policyAllowList && 'files:list',
      policyAllowUploads && 'files:write',
    ].filter(Boolean);

    return JSON.stringify({
      version: '2026-05-14',
      bucket: bucketName,
      effect: 'allow',
      principal: policyPublicRead ? '*' : 'authenticated',
      actions,
      resource: folder ? `/api/v1/files?folder=${folder}` : '/api/v1/files',
      conditions: {
        maxUploadSize: 'backend-default',
        cdnBaseUrl: maxxiApi.PUBLIC_BASE_URL,
      },
    }, null, 2);
  }, [folder, policyAllowList, policyAllowUploads, policyPublicRead]);

  const handleSelectFile = (id: string) => {
    setSelectedFiles(prev =>
      prev.includes(id) ? prev.filter(fid => fid !== id) : [...prev, id]
    );
  };

  const handleSelectAll = (fileIds: string[]) => {
    const allSelected = fileIds.length > 0 && fileIds.every((id) => selectedFiles.includes(id));
    if (allSelected) {
      setSelectedFiles(prev => prev.filter((id) => !fileIds.includes(id)));
    } else {
      setSelectedFiles(prev => Array.from(new Set([...prev, ...fileIds])));
    }
  };

  const refreshFiles = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['api-files-folder', folder] });
    queryClient.invalidateQueries({ queryKey: ['api-files'] });
  }, [folder, queryClient]);

  const handleCopyUrl = (file: CdnFile, type: 'cdn' | 'presigned') => {
    let url = '';
    if (type === 'cdn') {
      url = file.cdn_url || file.raw_url || file.download_url || '';
    } else {
      url = file.api_attachment_url || file.api_download_url || file.cdn_url || '';
    }
    navigator.clipboard.writeText(url);
    toast.success('URL copied to clipboard');
  };

  const handleDownload = (file: CdnFile) => {
    const url = maxxiApi.getDownloadUrl(file.id, 'attachment', file.folder_id ?? null);
    window.open(url, '_blank');
  };

  const handlePreview = (file: CdnFile) => {
    const url = maxxiApi.getPreviewUrl(file.id, file.folder_id ?? null);
    window.open(url, '_blank');
  };

  const handleDelete = (fileId: string, folderId?: number | null) => {
    const file = files.find((item) => item.id === fileId);
    setPendingDelete({ type: 'single', fileId, folderId, label: file ? getFileLabel(file) : 'this file' });
  };

  const handleConfirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);

    try {
      if (pendingDelete.type === 'single') {
        await maxxiApi.deleteFile(pendingDelete.fileId, pendingDelete.folderId ?? null);
        setSelectedFiles(prev => prev.filter((id) => id !== pendingDelete.fileId));
        toast.success('File deleted');
      } else {
        let failed = 0;
        for (const file of pendingDelete.files) {
          try {
            await maxxiApi.deleteFile(file.id, file.folder_id ?? null);
          } catch {
            failed += 1;
          }
        }
        setSelectedFiles([]);
        const deleted = pendingDelete.files.length - failed;
        if (deleted > 0) toast.success(`${deleted} file(s) deleted`);
        if (failed > 0) toast.error(`${failed} file(s) could not be deleted`);
      }
      refreshFiles();
      setPendingDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <main className="max-w-7xl mx-auto px-6 py-6">
        <Breadcrumb className="mb-6">
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link to="/">Dashboard</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>{folder || 'All Files'}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>

        {/* Folder header */}
        <div className="rounded-xl border border-border bg-gradient-to-r from-violet-50/40 via-white to-white p-6 mb-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">
                {folder || 'All Files'}
              </h1>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span className='text-lime-950'>{files.length} objects</span>
                <span>·</span>
                <span className='text-rose-400'>{formatTotalSize(totalSize)}</span>
                <span>·</span>
                <span className="text-emerald-600 font-medium">Public · Global</span>
              </div>
              <p className="text-xs text-muted-foreground mt-2 font-mono">
                {publicApiUrl(`/api/v1/files?folder=${encodeURIComponent(folder)}`)}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-4">
              {/* <Badge variant="outline" className="gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5" />
                {detectedFolderId ? `Folder ID ${detectedFolderId}` : 'Auto target root'}
                </Badge> */}
              <Button variant="outline" className='bg-transparent' size="sm" onClick={() => window.open(publicApiUrl(`/api/v1/files?folder=${encodeURIComponent(folder)}`), '_blank')}>
                View JSON
              </Button>
                <Link to="/policies/bucket" state={{ bucket: folder, policy: bucketPolicy }}>
                  <Button variant="destructive" size="sm">
                    <Settings className="h-4 w-4 cursor-alias" />
                    Policies
                  </Button>
                </Link>
            </div>
          </div>
        </div>

        {/* Files heading */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
          <h2 className="text-lg font-semibold">Files</h2>
          <div className="flex items-center gap-2">
            {selectedFiles.length > 0 && (
              <Button
                variant="destructive"
                className="h-9"
                onClick={() => setPendingDelete({ type: 'bulk', files: selectedFileRecords })}
              >
                <Trash2 className="h-4 w-4 mr-1.5" />
                Delete {selectedFiles.length}
              </Button>
            )}
            <Button onClick={() => setShowUpload(true)} className="h-9">
              <Plus className="h-4 w-4 mr-1.5" /> Upload
            </Button>
          </div>
        </div>

        {/* Search */}
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by filename..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9"
          />
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-6 h-6 border-2 border-muted-foreground/30 border-t-primary rounded-full animate-spin" />
          </div>
        ) : (
          <FileTable
            files={filteredFiles}
            selectedFiles={selectedFiles}
            onSelectFile={handleSelectFile}
            onSelectAll={handleSelectAll}
            onCopyUrl={handleCopyUrl}
            onDownload={handleDownload}
            onPreview={handlePreview}
            onDelete={handleDelete}
            onOpenPreviewModal={setPreviewFile}
          />
        )}
      </main>

      <FilePreviewModal
        file={previewFile}
        open={!!previewFile}
        onClose={() => setPreviewFile(null)}
      />

      <UploadDialog
        open={showUpload}
        onOpenChange={setShowUpload}
        folder={folder || null}
        folderId={detectedFolderId}
        onUploadComplete={() => {
          refreshFiles();
        }}
      />

      <AlertDialog open={!!pendingDelete} onOpenChange={(open) => !open && !deleting && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {pendingDelete?.type === 'bulk' ? `Delete ${pendingDelete.files.length} files?` : 'Delete file?'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pendingDelete?.type === 'bulk'
                ? 'This will permanently delete the selected files from the CDN.'
                : `This will permanently delete ${pendingDelete?.label ?? 'this file'} from the CDN.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(event) => {
                event.preventDefault();
                handleConfirmDelete();
              }}
            >
              {deleting ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
