import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { FolderOpen } from 'lucide-react';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import type { Bucket } from '@/types/cdn';

type BucketsTableProps = {
  buckets: Bucket[];
  onDelete?: (bucket: Bucket) => void;
};

function formatFileSize(bytes: number): string {
  if (!bytes || bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`;
}

export default function BucketsTable({ buckets }: BucketsTableProps) {
  const pageSize = 4;
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(buckets.length / pageSize));

  useEffect(() => {
    setPage(1);
  }, [buckets.length]);

  const visibleBuckets = useMemo(() => {
    const start = (page - 1) * pageSize;
    return buckets.slice(start, start + pageSize);
  }, [buckets, page]);

  const goToPage = (nextPage: number) => {
    setPage(Math.min(Math.max(nextPage, 1), pageCount));
  };

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead className="font-medium text-xs uppercase tracking-wider text-muted-foreground">Folder / CDN Path</TableHead>
              <TableHead className="font-medium text-xs uppercase tracking-wider text-muted-foreground">Objects</TableHead>
              <TableHead className="font-medium text-xs uppercase tracking-wider text-muted-foreground">Total Size</TableHead>
              <TableHead className="font-medium text-xs uppercase tracking-wider text-muted-foreground">Access</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {buckets.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center py-12 text-muted-foreground">
                  No files found. Upload your first file to get started.
                </TableCell>
              </TableRow>
            )}
            {visibleBuckets.map((bucket) => {
              const totalSize = bucket.size_bytes || bucket.files.reduce((acc, f) => acc + (f.size_bytes || 0), 0);
              return (
                <TableRow key={bucket.id} className="group">
                  <TableCell>
                    <Link
                      to={`/buckets/${encodeURIComponent(bucket.name)}`}
                      className="flex items-center gap-2.5 hover:text-primary transition-colors"
                    >
                      <FolderOpen className="h-4 w-4 text-muted-foreground" strokeWidth={1.5} />
                      <span className="font-medium text-sm">{bucket.name}</span>
                    </Link>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {(bucket.files || []).length}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatFileSize(totalSize)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="font-normal text-xs">
                      {bucket.access || 'Public'}
                    </Badge>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {buckets.length > pageSize && (
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
