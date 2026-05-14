/**
 * Maxxi CDN API Client
 * Base URL: https://mxcdn.vercel.app
 * Spec: OpenAPI 3.1.0
 */

import type { CdnFile, ListFilesResponse } from "@/types/cdn";

// In dev, use relative URLs so Vite's proxy handles CORS; in prod, use the full origin.
const BASE_URL = import.meta.env.DEV ? "" : "https://mxcdn.vercel.app";
const AUTH_TOKEN_KEY = "mxcdn-auth-token";

export type AuthToken = {
  access_token: string;
  token_type: string;
};

export type AuthUser = {
  id: string;
  email: string;
  full_name: string;
  role: string;
};

export type BucketPolicy = {
  bucket: string;
  access: "public" | "private";
  object_acl: boolean;
  disable_directory_listing: boolean;
  allowed_actions: string[];
  allowed_origins: string[];
  custom_domain?: string | null;
  additional_headers: Record<string, string>;
  cors_rules: Array<Record<string, unknown>>;
  iam_key_ids: string[];
  created_at?: string;
  updated_at?: string;
};

export type BucketPolicyUpdate = Omit<BucketPolicy, "bucket" | "created_at" | "updated_at">;

export type StorageSettings = {
  storage_backend: "telegram" | "github";
  quota_bytes: number;
  used_bytes: number;
  remaining_bytes: number;
};

export type IamKey = {
  id: string;
  name: string;
  access_key_id: string;
  status: "active" | "disabled";
  created_date: string;
  last_used_date?: string | null;
};

export type CreatedIamKey = IamKey & {
  secret_access_key: string;
};

type ApiErrorBody = {
  detail?: Array<{ msg?: string }> | { msg?: string } | string;
  message?: string;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = path.startsWith('http') ? path : `${BASE_URL}${path}`;
  const res = await fetch(url, options);
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as ApiErrorBody;
    const detail = Array.isArray(err.detail) ? err.detail[0]?.msg : typeof err.detail === "object" ? err.detail?.msg : err.detail;
    throw new Error(detail || err.message || `API error ${res.status}`);
  }
  return res.json() as Promise<T>;
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function authorizedRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  return request<T>(path, {
    ...options,
    headers: {
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
}

export function setAuthToken(token: string): void {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function getAuthToken(): string | null {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function clearAuthToken(): void {
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

// ─── Files ────────────────────────────────────────────────────────────────────

/**
 * POST /api/v1/files
 * Upload a file (multipart/form-data).
 * @param {File} file - The File object to upload
 * @param {number|null} folderId - Optional folder ID
 * @returns {Promise<CDNFileRecord>}
 */
export async function uploadFile(file: File, folderId: number | null = null): Promise<CdnFile> {
  const form = new FormData();
  form.append('file', file);
  if (folderId != null) form.append('folder_id', String(folderId));

  return authorizedRequest<CdnFile>('/api/v1/files', {
    method: 'POST',
    body: form,
  });
}

/**
 * GET /api/v1/files
 * Returns { success, total_files, total_size_bytes, folders, files[] }
 * @param {string|null} folder
 * @param {string|null} category
 * @returns {Promise<{ files: CDNFileRecord[], total_files: number, total_size_bytes: number, folders: object }>}
 */
export async function listFiles(folder: string | null = null, category: string | null = null): Promise<ListFilesResponse> {
  const params = new URLSearchParams();
  if (folder) params.set('folder', folder);
  if (category) params.set('category', category);
  const qs = params.toString();
  return authorizedRequest<ListFilesResponse>(`/api/v1/files${qs ? `?${qs}` : ''}`);
}

/**
 * GET /api/v1/files/{file_id}/metadata
 * Get metadata for a specific file.
 * @param {string} fileId
 * @returns {Promise<object>}
 */
export async function getFileMetadata(fileId: string): Promise<Record<string, unknown>> {
  return authorizedRequest<Record<string, unknown>>(`/api/v1/files/${fileId}/metadata`);
}

/**
 * GET /api/v1/files/{file_id}/download
 * Download a file (returns redirect / binary).
 * @param {string} fileId
 * @param {'inline'|'attachment'} disposition
 * @param {number|null} folderId
 * @returns {string} Direct URL to use in window.open()
 */
export function getDownloadUrl(
  fileId: string,
  disposition: "inline" | "attachment" = "attachment",
  folderId: number | null = null,
): string {
  const params = new URLSearchParams({ disposition });
  if (folderId != null) params.set('folder_id', String(folderId));
  return `${BASE_URL}/api/v1/files/${fileId}/download?${params.toString()}`;
}

/**
 * GET /api/v1/files/{file_id}/preview
 * Get a preview URL for a file.
 * @param {string} fileId
 * @param {number|null} folderId
 * @returns {string} Direct preview URL
 */
export function getPreviewUrl(fileId: string, folderId: number | null = null): string {
  const params = new URLSearchParams();
  if (folderId != null) params.set('folder_id', String(folderId));
  const qs = params.toString();
  return `${BASE_URL}/api/v1/files/${fileId}/preview${qs ? `?${qs}` : ''}`;
}

/**
 * DELETE /api/v1/files/{file_id}
 * Delete a file.
 * @param {string} fileId
 * @param {number|null} folderId
 * @returns {Promise<{message: string}>}
 */
export async function deleteFile(fileId: string, folderId: number | null = null): Promise<{ message?: string }> {
  const params = new URLSearchParams();
  if (folderId != null) params.set('folder_id', String(folderId));
  const qs = params.toString();
  return authorizedRequest<{ message?: string }>(`/api/v1/files/${fileId}${qs ? `?${qs}` : ''}`, {
    method: 'DELETE',
  });
}

/**
 * POST /api/v1/repo/files
 * Upload a file to the repo/CDN route.
 * @param {File} file
 * @returns {Promise<object>}
 */
export async function uploadRepoFile(file: File): Promise<Record<string, unknown>> {
  const form = new FormData();
  form.append('file', file);
  return request<Record<string, unknown>>('https://cdn.pitbox.fun/api/v1/repo/files', {
    method: 'POST',
    headers: { accept: 'application/json' },
    body: form,
  });
}

export async function googleLogin(token: string): Promise<AuthToken> {
  const authToken = await request<AuthToken>('/api/auth/google', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  setAuthToken(authToken.access_token);
  return authToken;
}

export async function getCurrentUser(): Promise<AuthUser> {
  return authorizedRequest<AuthUser>('/api/auth/me');
}

export async function getBucketPolicy(bucket: string): Promise<BucketPolicy> {
  return request<BucketPolicy>(`/api/v1/bucket-policies/${encodeURIComponent(bucket)}`);
}

export async function listBucketPolicies(): Promise<BucketPolicy[]> {
  return request<BucketPolicy[]>('/api/v1/bucket-policies');
}

export async function saveBucketPolicy(bucket: string, policy: BucketPolicyUpdate): Promise<BucketPolicy> {
  return authorizedRequest<BucketPolicy>(`/api/v1/bucket-policies/${encodeURIComponent(bucket)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(policy),
  });
}

export async function deleteBucketPolicy(bucket: string): Promise<{ message: string }> {
  return authorizedRequest<{ message: string }>(`/api/v1/bucket-policies/${encodeURIComponent(bucket)}`, {
    method: 'DELETE',
  });
}

export async function getStorageSettings(): Promise<StorageSettings> {
  return authorizedRequest<StorageSettings>('/api/v1/me/storage');
}

export async function updateStorageSettings(storage_backend: "telegram" | "github"): Promise<StorageSettings> {
  return authorizedRequest<StorageSettings>('/api/v1/me/storage', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ storage_backend }),
  });
}

export async function listIamKeys(): Promise<IamKey[]> {
  return authorizedRequest<IamKey[]>('/api/v1/me/iam-keys');
}

export async function createIamKey(name: string): Promise<CreatedIamKey> {
  return authorizedRequest<CreatedIamKey>('/api/v1/me/iam-keys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
}

export async function deleteIamKey(keyId: string): Promise<{ message: string }> {
  return authorizedRequest<{ message: string }>(`/api/v1/me/iam-keys/${encodeURIComponent(keyId)}`, {
    method: 'DELETE',
  });
}

export const maxxiApi = {
  googleLogin,
  getCurrentUser,
  setAuthToken,
  getAuthToken,
  clearAuthToken,
  getBucketPolicy,
  listBucketPolicies,
  saveBucketPolicy,
  deleteBucketPolicy,
  getStorageSettings,
  updateStorageSettings,
  listIamKeys,
  createIamKey,
  deleteIamKey,
  uploadFile,
  listFiles,
  getFileMetadata,
  getDownloadUrl,
  getPreviewUrl,
  deleteFile,
  uploadRepoFile,
  BASE_URL,
};
