import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, ChevronDown, Copy, KeyRound, Plus, Search, Settings2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { maxxiApi, type BucketPolicyUpdate, type CreatedIamKey } from '@/lib/maxxiApi';

type LocationState = {
  bucket?: string;
  policy?: string;
};

const S3_ENDPOINT = 'https://t3.storage.dev';
const IAM_ENDPOINT = 'https://iam.storage.dev';

function formatDate(value: string) {
  try {
    return new Intl.DateTimeFormat('en-US', {
      month: '2-digit',
      day: '2-digit',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, index)).toFixed(2)} ${units[index]}`;
}

function copyValue(value: string, label: string) {
  navigator.clipboard.writeText(value);
  toast.success(`${label} copied`);
}

export default function BucketPolicies() {
  const location = useLocation();
  const state = (location.state || {}) as LocationState;
  const bucketName = state.bucket || 'maxxi';

  const [accessMode, setAccessMode] = useState('public');
  const [objectAcl, setObjectAcl] = useState(false);
  const [disableDirectoryListing, setDisableDirectoryListing] = useState(true);
  const [customDomain, setCustomDomain] = useState('');
  const [additionalHeaders, setAdditionalHeaders] = useState(false);
  const [corsRule, setCorsRule] = useState('');
  const [search, setSearch] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [createdKey, setCreatedKey] = useState<CreatedIamKey | null>(null);
  const queryClient = useQueryClient();

  const { data: backendPolicy, isLoading: policyLoading } = useQuery({
    queryKey: ['bucket-policy', bucketName],
    queryFn: () => maxxiApi.getBucketPolicy(bucketName),
  });

  const savePolicyMutation = useMutation({
    mutationFn: (policyUpdate: BucketPolicyUpdate) => maxxiApi.saveBucketPolicy(bucketName, policyUpdate),
    onSuccess: (savedPolicy) => {
      queryClient.setQueryData(['bucket-policy', bucketName], savedPolicy);
      toast.success('Bucket policy saved');
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Could not save bucket policy');
    },
  });

  const { data: storageSettings } = useQuery({
    queryKey: ['storage-settings'],
    queryFn: () => maxxiApi.getStorageSettings(),
    enabled: !!maxxiApi.getAuthToken(),
  });

  const { data: keys = [] } = useQuery({
    queryKey: ['iam-keys'],
    queryFn: () => maxxiApi.listIamKeys(),
    enabled: !!maxxiApi.getAuthToken(),
  });

  const updateStorageMutation = useMutation({
    mutationFn: (backend: 'telegram' | 'github') => maxxiApi.updateStorageSettings(backend),
    onSuccess: (settings) => {
      queryClient.setQueryData(['storage-settings'], settings);
      toast.success('Storage settings updated');
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Could not update storage settings');
    },
  });

  const createKeyMutation = useMutation({
    mutationFn: (name: string) => maxxiApi.createIamKey(name),
    onSuccess: (key) => {
      queryClient.invalidateQueries({ queryKey: ['iam-keys'] });
      setCreatedKey(key);
      setNewKeyName('');
      setCreateOpen(false);
      toast.success(`${key.name} created`);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Could not create IAM key');
    },
  });

  const deleteKeyMutation = useMutation({
    mutationFn: (keyId: string) => maxxiApi.deleteIamKey(keyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['iam-keys'] });
      toast.success('IAM key deleted');
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Could not delete IAM key');
    },
  });

  useEffect(() => {
    if (!backendPolicy) return;
    setAccessMode(backendPolicy.access);
    setObjectAcl(backendPolicy.object_acl);
    setDisableDirectoryListing(backendPolicy.disable_directory_listing);
    setCustomDomain(backendPolicy.custom_domain || '');
    setAdditionalHeaders(Object.keys(backendPolicy.additional_headers || {}).length > 0);
    setCorsRule(String(backendPolicy.allowed_origins?.[0] || ''));
  }, [backendPolicy]);

  const policyPayload = useMemo<BucketPolicyUpdate>(() => ({
    access: accessMode as 'public' | 'private',
    object_acl: objectAcl,
    disable_directory_listing: disableDirectoryListing,
    allowed_actions: accessMode === 'public' ? ['files:read', 'files:list'] : ['files:read'],
    allowed_origins: corsRule.trim() ? [corsRule.trim()] : [],
    custom_domain: customDomain.trim() || null,
    additional_headers: additionalHeaders ? { 'X-Content-Type-Options': 'nosniff' } : {},
    cors_rules: corsRule.trim() ? [{
      allowed_origin: corsRule.trim(),
      allowed_methods: ['GET', 'HEAD', 'OPTIONS'],
      allowed_headers: ['*'],
    }] : [],
    iam_key_ids: keys.map((key) => key.access_key_id),
  }), [accessMode, additionalHeaders, corsRule, customDomain, disableDirectoryListing, keys, objectAcl]);

  const policy = useMemo(() => {
    const policyJson = {
      version: '2026-05-14',
      bucket: bucketName,
      ...policyPayload,
      actions: policyPayload.allowed_actions,
      resource: `/api/v1/files?folder=${bucketName}`,
      updated_at: backendPolicy?.updated_at,
    };

    return JSON.stringify(policyJson, null, 2);
  }, [backendPolicy?.updated_at, bucketName, policyPayload]);

  const filteredKeys = keys.filter((key) => {
    if (!search) return true;
    const query = search.toLowerCase();
    return key.name.toLowerCase().includes(query) || key.access_key_id.toLowerCase().includes(query);
  });

  const savePolicy = () => {
    savePolicyMutation.mutate(policyPayload);
  };

  const createKey = () => {
    const trimmedName = newKeyName.trim() || bucketName.toUpperCase();
    createKeyMutation.mutate(trimmedName);
  };

  const deleteKey = (keyId: string) => {
    deleteKeyMutation.mutate(keyId);
  };

  return (
    <main className="min-h-screen bg-background px-6 py-5">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex items-center justify-between gap-4">
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link to="/">Dashboard</Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link to={`/buckets/${encodeURIComponent(bucketName)}`}>{bucketName}</Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>Bucket Settings</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
          <button className="flex items-center gap-3 rounded-md bg-muted/60 px-4 py-2 text-left">
            <div className="h-7 w-7 rounded-full bg-gradient-to-br from-orange-200 to-purple-200" />
            <div>
              <p className="text-sm font-semibold">Abaasa Albert</p>
              <p className="text-xs text-muted-foreground">{maxxiApi.getAuthToken() ? 'authenticated' : 'not signed in'}</p>
            </div>
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>

        <section className="mb-6 rounded-lg border border-border bg-gradient-to-r from-white via-violet-50 to-sky-50 p-6">
          <div className="flex items-center gap-3">
            <Settings2 className="h-5 w-5" />
            <h1 className="text-lg font-bold">{bucketName}</h1>
          </div>
          <div className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700">
            <Check className="h-3 w-3" />
            Snapshot Enabled
          </div>
        </section>

        <Tabs defaultValue="access" className="space-y-8">
          <div>
            <h2 className="mb-5 text-lg font-semibold">Bucket Settings</h2>
            {policyLoading && <p className="mb-3 text-xs text-muted-foreground">Loading backend policy...</p>}
            <TabsList className="h-auto w-full justify-start gap-6 overflow-x-auto rounded-none border-b bg-transparent p-0">
              {[
                ['access', 'Access and Sharing'],
                ['storage', 'Storage Settings'],
                ['data', 'Data Management'],
                ['domains', 'Custom Domains'],
                ['cors', 'CORS and Headers'],
                ['notifications', 'Notifications'],
                ['deletion', 'Deletion Settings'],
                ['keys', 'IAM Access Keys'],
              ].map(([value, label]) => (
                <TabsTrigger
                  key={value}
                  value={value}
                  className="rounded-none border-b-2 border-transparent px-0 pb-3 text-xs text-muted-foreground shadow-none data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-primary data-[state=active]:shadow-none"
                >
                  {label}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>

          <TabsContent value="access" className="space-y-0">
            <SettingRow title="Sharing" description={`Manage who has access to your ${bucketName} bucket.`}>
              <Button size="sm">Manage Members</Button>
            </SettingRow>
            <SettingRow title="Public / Private Access" description="Set your bucket as public or private.">
              <Select value={accessMode} onValueChange={setAccessMode}>
                <SelectTrigger className="w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="public">Public</SelectItem>
                  <SelectItem value="private">Private</SelectItem>
                </SelectContent>
              </Select>
            </SettingRow>
            <SettingRow title="Object ACL" description="Use Object ACLs to manage permissions at the object level.">
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <Switch checked={objectAcl} onCheckedChange={setObjectAcl} />
                Allow Object ACL
              </div>
            </SettingRow>
            <SettingRow title="Disable Directory Listing" description="Hide the full contents of public buckets.">
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <Switch checked={disableDirectoryListing} onCheckedChange={setDisableDirectoryListing} />
                Disable Directory Listing
              </div>
            </SettingRow>
            <div className="grid gap-4 border-t pt-8 lg:grid-cols-[360px_1fr]">
              <div>
                <p className="text-sm font-semibold">Bucket Policy JSON</p>
                <p className="mt-1 text-xs text-muted-foreground">Copy this generated policy for your API gateway or backend.</p>
              </div>
              <div className="space-y-3">
                <Textarea value={policy} readOnly className="min-h-48 font-mono text-xs" />
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => copyValue(policy, 'Bucket policy')}>
                    <Copy className="mr-2 h-4 w-4" />
                    Copy Policy
                  </Button>
                  <Button size="sm" disabled={savePolicyMutation.isPending} onClick={savePolicy}>
                    {savePolicyMutation.isPending ? 'Saving...' : 'Save Policy'}
                  </Button>
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="domains">
            <SettingRow title="Custom Domains" description="Add a CNAME record that points to the bucket URL.">
              <div className="flex w-full max-w-md gap-3">
                <Input value={customDomain} onChange={(event) => setCustomDomain(event.target.value)} placeholder="Custom Domain" />
                <Button variant="secondary" disabled={savePolicyMutation.isPending} onClick={savePolicy}>Update</Button>
              </div>
            </SettingRow>
          </TabsContent>

          <TabsContent value="cors">
            <SettingRow title="Additional Headers" description="Enable additional headers and content types.">
              <div className="flex w-full max-w-md items-center gap-4">
                <Switch checked={additionalHeaders} onCheckedChange={setAdditionalHeaders} />
                <Input value="X-Content-Type-Options: nosniff" readOnly />
              </div>
            </SettingRow>
            <SettingRow title="CORS Configuration" description="Configure the CORS configurations.">
              <div className="flex w-full max-w-md gap-3">
                <Input value={corsRule} onChange={(event) => setCorsRule(event.target.value)} placeholder="https://example.com" />
                <Button variant="outline" disabled={savePolicyMutation.isPending} onClick={savePolicy}>Add New Rule</Button>
              </div>
            </SettingRow>
            <div className="border-t pt-6">
              <Button variant="secondary" disabled={savePolicyMutation.isPending} onClick={savePolicy}>Update</Button>
            </div>
          </TabsContent>

          <TabsContent value="storage">
            <SettingRow title="Storage Backend" description="Choose where new file bytes are stored for your account. Metadata remains managed by Maxxi.">
              <div className="flex flex-col gap-3">
                <Select
                  value={storageSettings?.storage_backend || 'telegram'}
                  onValueChange={(value) => updateStorageMutation.mutate(value as 'telegram' | 'github')}
                  disabled={!maxxiApi.getAuthToken() || updateStorageMutation.isPending}
                >
                  <SelectTrigger className="w-52">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="telegram">Telegram Storage</SelectItem>
                    <SelectItem value="github">GitHub Repo Storage</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  {storageSettings
                    ? `${formatBytes(storageSettings.used_bytes)} used of ${formatBytes(storageSettings.quota_bytes)}`
                    : 'Sign in to manage storage settings.'}
                </p>
              </div>
            </SettingRow>
          </TabsContent>

          <TabsContent value="keys">
            <section className="space-y-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <KeyRound className="h-5 w-5" />
                  <h2 className="text-lg font-semibold">Access Keys</h2>
                </div>
                <Button onClick={() => setCreateOpen(true)}>
                  Create New Access Key
                  <Plus className="ml-2 h-4 w-4" />
                </Button>
              </div>

              <div className="flex flex-wrap items-center gap-3 rounded-md border bg-sky-50/40 p-3">
                <span className="text-sm">Connect using a single global endpoint</span>
                <Select defaultValue="default">
                  <SelectTrigger className="w-28 bg-background">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">Default</SelectItem>
                  </SelectContent>
                </Select>
                <CopyField value={S3_ENDPOINT} label="S3 endpoint" className="w-64" />
              </div>

              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search access key ID by prefix..." />
              </div>

              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/40">
                      <TableHead>Name</TableHead>
                      <TableHead>Access Key Id</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created On</TableHead>
                      <TableHead>Created By</TableHead>
                      <TableHead className="w-12" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredKeys.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={6} className="py-10 text-center text-sm text-muted-foreground">No results found</TableCell>
                      </TableRow>
                    )}
                    {filteredKeys.map((key) => (
                      <TableRow key={key.id}>
                        <TableCell className="font-medium">{key.name}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className="max-w-md truncate font-mono text-xs">{key.access_key_id}</span>
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => copyValue(key.access_key_id, 'Access key ID')}>
                              <Copy className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </TableCell>
                        <TableCell className="text-emerald-600">✓ {key.status}</TableCell>
                        <TableCell>{formatDate(key.created_date)}</TableCell>
                        <TableCell>Current user</TableCell>
                        <TableCell>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" disabled={deleteKeyMutation.isPending} onClick={() => deleteKey(key.id)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </section>
          </TabsContent>

          {['data', 'notifications', 'deletion'].map((value) => (
            <TabsContent key={value} value={value}>
              <div className="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">
                Settings for this section are ready for backend integration.
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Access Key</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="key-name">Name</label>
            <Input id="key-name" value={newKeyName} onChange={(event) => setNewKeyName(event.target.value)} placeholder="HELLO" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={createKey}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!createdKey} onOpenChange={(open) => !open && setCreatedKey(null)}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>'{createdKey?.name}' Created</DialogTitle>
          </DialogHeader>
          {createdKey && (
            <div className="space-y-3">
              <KeyValueRow label="Access Key ID" value={createdKey.access_key_id} />
              <KeyValueRow label="Secret Access Key" value={createdKey.secret_access_key} />
              <KeyValueRow label="Endpoint URL S3" value={S3_ENDPOINT} withSelect />
              <KeyValueRow label="Endpoint URL IAM" value={IAM_ENDPOINT} withSelect />
              <KeyValueRow label="Region" value="auto" />
              <div className="flex items-center justify-between rounded-md bg-muted/60 p-4 text-sm">
                Environment Variables
                <Switch />
              </div>
              <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                You won't be able to retrieve the secret key again. Copy and keep it in a safe location.
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreatedKey(null)}>Close</Button>
            <Button onClick={() => toast.success('Key permission editor is ready for backend integration')}>Manage Key Permissions</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}

function SettingRow({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <div className="grid gap-4 border-t py-8 lg:grid-cols-[360px_1fr]">
      <div>
        <p className="text-sm font-semibold">{title}</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
      </div>
      <div className="flex items-center">{children}</div>
    </div>
  );
}

function CopyField({ value, label, className = '' }: { value: string; label: string; className?: string }) {
  return (
    <div className={`flex overflow-hidden rounded-md border bg-background ${className}`}>
      <Input value={value} readOnly className="h-9 rounded-none border-0 font-mono text-xs focus-visible:ring-0" />
      <Button variant="ghost" size="icon" className="h-9 w-9 rounded-none border-l" onClick={() => copyValue(value, label)}>
        <Copy className="h-4 w-4" />
      </Button>
    </div>
  );
}

function KeyValueRow({ label, value, withSelect = false }: { label: string; value: string; withSelect?: boolean }) {
  return (
    <div className="grid gap-3 sm:grid-cols-[160px_1fr] sm:items-center">
      <span className="text-sm">{label}</span>
      <div className="flex">
        {withSelect && (
          <Select defaultValue="default">
            <SelectTrigger className="w-28 rounded-r-none">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="default">Default</SelectItem>
            </SelectContent>
          </Select>
        )}
        <CopyField value={value} label={label} className={withSelect ? 'flex-1 rounded-l-none' : 'flex-1'} />
      </div>
    </div>
  );
}
