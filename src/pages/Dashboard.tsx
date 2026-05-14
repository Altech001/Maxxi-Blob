/* eslint-disable react-hooks/exhaustive-deps */
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, HardDrive, Layers, Package, Plus, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { toast } from "sonner";

import { maxxiApi } from '@/lib/maxxiApi';
import type { Bucket, CdnFile } from '@/types/cdn';
import GoogleAuthPanel from '@/components/auth/GoogleAuthPanel';
import CreateBucketDialog from '../components/bucket/CreateBucketDialog';
import BucketsTable from '../components/dashboard/BucketsTable';
import MetricCard from '../components/dashboard/MetricCard';
import InfoBanner from "@/components/dashboard/InfoBanner";

function formatTotalSize(bytes: number): string {
  if (!bytes || bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`;
}

export default function Dashboard() {
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState('all');
  const [showCreate, setShowCreate] = useState(false);
  const queryClient = useQueryClient();

  // Fetch all files from the real API to compute metrics
  const { data: apiData, isLoading: filesLoading } = useQuery({
    queryKey: ['api-files'],
    queryFn: () => maxxiApi.listFiles(),
    retry: 1,
  });

  // API returns { success, total_files, total_size_bytes, folders: { name: {count, size_bytes} }, files[] }
  const allFiles = apiData?.files ?? [];
  const foldersMap = apiData?.folders ?? {};
  const totalStorage = apiData?.total_size_bytes ?? 0;
  const totalObjects = apiData?.total_files ?? 0;

  // Build buckets list from the top-level `folders` object + enrich with file list
  const buckets = useMemo<Bucket[]>(() => {
    const filesByFolder: Record<string, CdnFile[]> = {};
    allFiles.forEach((f) => {
      const key = f.cdn_folder || 'uncategorized';
      if (!filesByFolder[key]) filesByFolder[key] = [];
      filesByFolder[key].push(f);
    });

    // Use folders from API response as source of truth
    const folderNames = Object.keys(foldersMap).length > 0
      ? Object.keys(foldersMap)
      : [...new Set(allFiles.map((f) => f.cdn_folder || 'uncategorized'))];

    return folderNames.map((name) => ({
      id: name,
      name,
      access: 'Public',
      files: filesByFolder[name] ?? [],
      count: foldersMap[name]?.count ?? (filesByFolder[name]?.length ?? 0),
      size_bytes: foldersMap[name]?.size_bytes ?? 0,
    }));
  }, [allFiles, foldersMap]);

  const filteredBuckets = buckets.filter((b) => {
    return !search || b.name.toLowerCase().includes(search.toLowerCase());
  });

  return (
    <div className="min-h-screen bg-background">
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold">Maxxi CDN</h1>
            <p className="text-sm text-muted-foreground">Buckets, policies, and upload operations.</p>
          </div>
          <GoogleAuthPanel />
        </div>

        {/* Metrics */}
        <div className="mb-2">
          <p className="text-xs text-muted-foreground">
            Metrics{' '}
            {filesLoading && <span className="ml-1 opacity-60">loading…</span>}
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
          <MetricCard icon={HardDrive} label="Total Storage" value={filesLoading ? '…' : formatTotalSize(totalStorage)} color="purple" />
          <MetricCard icon={Layers} label="Total Folders" value={filesLoading ? '…' : buckets.length} color="blue" />
          <MetricCard icon={Package} label="Total Objects" value={filesLoading ? '…' : totalObjects} color="amber" />
        </div>

        {/* Files Section */}
        <h2 className="text-lg font-semibold mb-4">Files</h2>

        {/* Endpoint bar */}
        <div className="flex items-center gap-3 mb-5 flex-wrap">
          <span className="text-sm text-muted-foreground whitespace-nowrap">API endpoint</span>
          <div className="flex items-center gap-0">
            <div className="bg-muted rounded-l-md px-3 py-1.5 text-sm border border-border border-r-0 text-muted-foreground">
              Base URL
            </div>
            <div className="flex items-center gap-2 bg-card border border-border rounded-r-md px-3 py-1.5">
              <span className="text-sm text-muted-foreground">https://mxcdn.vercel.app</span>
              <button
                onClick={() => { navigator.clipboard.writeText('https://mxcdn.vercel.app'); toast.success('Copied!'); }}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <Copy className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex items-center justify-between gap-4 mb-4 flex-wrap">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="h-9">
              <TabsTrigger value="all" className="text-sm px-4">all</TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search folder by prefix..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 w-64 h-9"
              />
            </div>
            <Button onClick={() => setShowCreate(true)} className="h-9">
              <Plus className="h-4 w-4 mr-1.5" /> Upload File
            </Button>
          </div>
        </div>

        <InfoBanner
          message="Files are stored via Maxxi CDN — bytes in Telegram, metadata in GitHub."
          linkText="View API docs →"
          onLinkClick={() => window.open('https://mxcdn.vercel.app/docs', '_blank')}
        />

        <div className="mt-4">
          <BucketsTable buckets={filteredBuckets} onDelete={() => {}} />
        </div>
      </main>

      <CreateBucketDialog
        open={showCreate}
        onOpenChange={setShowCreate}
        onCreated={() => queryClient.invalidateQueries({ queryKey: ['api-files'] })}
      />
    </div>
  );
}
