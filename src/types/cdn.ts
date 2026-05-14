export type FileCategory = "image" | "video" | "document" | "audio" | "archive" | string;

export type UploadProgressState = "uploading" | "done" | "error";

export type CdnFile = {
  id: string;
  filename?: string;
  original_filename?: string;
  mime_type?: string;
  category?: FileCategory;
  extension?: string;
  size_bytes?: number;
  cdn_folder?: string;
  uploaded_at?: string;
  folder_id?: number | null;
  cdn_url?: string;
  raw_url?: string;
  download_url?: string;
  api_inline_url?: string;
  api_attachment_url?: string;
  api_download_url?: string;
  api_preview_url?: string;
  metadata_url?: string;
  telegram?: {
    storage?: string;
    [key: string]: unknown;
  };
  github?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
};

export type FolderSummary = {
  count?: number;
  size_bytes?: number;
};

export type ListFilesResponse = {
  success?: boolean;
  total_files?: number;
  total_size_bytes?: number;
  folders?: Record<string, FolderSummary>;
  files?: CdnFile[];
};

export type Bucket = {
  id: string;
  name: string;
  access?: string;
  files: CdnFile[];
  count?: number;
  size_bytes?: number;
  public_url?: string;
  snapshot_enabled?: boolean;
};
