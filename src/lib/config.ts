const DEFAULT_MAXXI_API_URL = "https://mxcdn.vercel.app";

function normalizeUrl(value: string | undefined): string {
  return (value || "").trim().replace(/\/+$/, "");
}

const configuredApiUrl = normalizeUrl(import.meta.env.VITE_MAXXI_API_URL);

export const MAXXI_API_URL =
  configuredApiUrl || (import.meta.env.DEV ? "" : DEFAULT_MAXXI_API_URL);

export const MAXXI_PUBLIC_API_URL = configuredApiUrl || DEFAULT_MAXXI_API_URL;

export function apiUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${MAXXI_API_URL}${path}`;
}

export function publicApiUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${MAXXI_PUBLIC_API_URL}${path}`;
}

export function withoutPublicApiUrl(value: string): string {
  return value.replace(MAXXI_PUBLIC_API_URL, "");
}
