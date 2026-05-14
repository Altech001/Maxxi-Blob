import { useEffect, useMemo, useState } from 'react';
import { MoreHorizontal, FileIcon, Image, Film, FileText, Music, Archive, Eye, Trash2, Download, Link2, type LucideIcon } from 'lucide-react';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from "@/components/ui/table";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { format } from 'date-fns';
import type { CdnFile } from '@/types/cdn';

type FileTableProps = {
  files: CdnFile[];
  selectedFiles: string[];
  onSelectFile: (id: string) => void;
  onSelectAll: (fileIds: string[]) => void;
  onCopyUrl: (file: CdnFile, type: 'cdn' | 'presigned') => void;
  onDownload: (file: CdnFile) => void;
  onPreview?: (file: CdnFile) => void;
  onDelete: (fileId: string, folderId?: number | null) => void | Promise<void>;
  onOpenPreviewModal?: (file: CdnFile) => void;
};

function formatFileSize(bytes?: number): string {
  if (!bytes || bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`;
}

function getCategoryIcon(category?: string): LucideIcon {
  const icons: Record<string, LucideIcon> = {
    image: Image,
    video: Film,
    document: FileText,
    audio: Music,
    archive: Archive,
  };
  return icons[category] || FileIcon;
}

export default function FileTable({
  files, selectedFiles, onSelectFile, onSelectAll,
  onCopyUrl, onDownload, onPreview, onDelete, onOpenPreviewModal
}: FileTableProps) {
  const pageSize = 4;
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(files.length / pageSize));

  useEffect(() => {
    setPage(1);
  }, [files.length]);

  const visibleFiles = useMemo(() => {
    const start = (page - 1) * pageSize;
    return files.slice(start, start + pageSize);
  }, [files, page]);

  const selectedVisibleCount = visibleFiles.filter((file) => selectedFiles.includes(file.id)).length;
  const allSelected = visibleFiles.length > 0 && selectedVisibleCount === visibleFiles.length;
  const someSelected = selectedVisibleCount > 0 && !allSelected;

  const goToPage = (nextPage: number) => {
    setPage(Math.min(Math.max(nextPage, 1), pageCount));
  };

  const formatDate = (str?: string) => {
    if (!str) return '—';
    try { return format(new Date(str), 'MM/dd/yyyy hh:mma'); } catch { return str; }
  };

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead className="w-10">
                <Checkbox checked={allSelected ? true : someSelected ? 'indeterminate' : false} onCheckedChange={() => onSelectAll(visibleFiles.map((file) => file.id))} />
              </TableHead>
              <TableHead className="font-medium text-xs uppercase tracking-wider text-muted-foreground">Name</TableHead>
              <TableHead className="font-medium text-xs uppercase tracking-wider text-muted-foreground">Category</TableHead>
              <TableHead className="font-medium text-xs uppercase tracking-wider text-muted-foreground">Uploaded</TableHead>
              <TableHead className="font-medium text-xs uppercase tracking-wider text-muted-foreground">Size</TableHead>
              <TableHead className="font-medium text-xs uppercase tracking-wider text-muted-foreground">Folder</TableHead>
              <TableHead className="font-medium text-xs uppercase tracking-wider text-muted-foreground text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {files.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-16 text-muted-foreground">
                  No files found.
                </TableCell>
              </TableRow>
            )}
            {visibleFiles.map((file) => {
              const Icon = getCategoryIcon(file.category);
              const isSelected = selectedFiles.includes(file.id);

              return (
                <TableRow key={file.id} className="group">
                  <TableCell>
                    <Checkbox checked={isSelected} onCheckedChange={() => onSelectFile(file.id)} />
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2.5">
                      <Icon className="h-4 w-4 text-muted-foreground shrink-0" strokeWidth={1.5} />
                      <div>
                        <p className="text-sm font-medium leading-tight">{file.filename || file.original_filename}</p>
                        {file.cdn_url && (
                          <p className="text-xs text-muted-foreground truncate max-w-xs">{file.cdn_url}</p>
                        )}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground capitalize">{file.category || '—'}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{formatDate(file.uploaded_at)}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{formatFileSize(file.size_bytes)}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{file.cdn_folder || '—'}</TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-52">
                        <DropdownMenuItem onClick={() => onOpenPreviewModal ? onOpenPreviewModal(file) : onPreview && onPreview(file)}>
                          <Eye className="h-4 w-4 mr-2" />
                          Preview
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => onCopyUrl(file, 'cdn')}>
                          <Link2 className="h-4 w-4 mr-2" />
                          Copy CDN URL
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => onCopyUrl(file, 'presigned')}>
                          <Link2 className="h-4 w-4 mr-2" />
                          Copy Download URL
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => onDownload(file)}>
                          <Download className="h-4 w-4 mr-2" />
                          Download
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() => onDelete(file.id, file.folder_id)}
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {files.length > pageSize && (
        <Pagination>
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                href="#"
                aria-disabled={page === 1}
                className={page === 1 ? "pointer-events-none opacity-50" : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  goToPage(page - 1);
                }}
              />
            </PaginationItem>
            {Array.from({ length: pageCount }, (_, index) => index + 1).map((pageNumber) => (
              <PaginationItem key={pageNumber}>
                <PaginationLink
                  href="#"
                  isActive={pageNumber === page}
                  onClick={(event) => {
                    event.preventDefault();
                    goToPage(pageNumber);
                  }}
                >
                  {pageNumber}
                </PaginationLink>
              </PaginationItem>
            ))}
            <PaginationItem>
              <PaginationNext
                href="#"
                aria-disabled={page === pageCount}
                className={page === pageCount ? "pointer-events-none opacity-50" : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  goToPage(page + 1);
                }}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      )}
    </div>
  );
}
