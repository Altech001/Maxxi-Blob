import { Copy, KeyRound, Terminal, UploadCloud } from 'lucide-react';
import { toast } from 'sonner';

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Button } from '@/components/ui/button';
import { MAXXI_PUBLIC_API_URL } from '@/lib/config';

const API_BASE_URL = MAXXI_PUBLIC_API_URL;
const API_INDEX_URL = `${API_BASE_URL}/api/v1`;
const API_DOCS_JSON_URL = `${API_BASE_URL}/api/v1/docs`;
const API_DOCS_HTML_URL = `${API_BASE_URL}/api/v1/docs.html`;
const OPENAPI_URL = `${API_BASE_URL}/api/v1/openapi.json`;

const curlUpload = `curl -X POST "${API_BASE_URL}/api/v1/files" \\
  -H "X-MAXXI-ACCESS-KEY: tid_your_access_key_id" \\
  -H "X-MAXXI-SECRET-KEY: tsec_your_secret_access_key" \\
  -F "file=@./photo.png"`;

const curlList = `curl "${API_BASE_URL}/api/v1/files?folder=images" \\
  -H "X-MAXXI-ACCESS-KEY: tid_your_access_key_id" \\
  -H "X-MAXXI-SECRET-KEY: tsec_your_secret_access_key"`;

const jsUpload = `const form = new FormData();
form.append("file", fileInput.files[0]);

const res = await fetch("${API_BASE_URL}/api/v1/files", {
  method: "POST",
  headers: {
    "X-MAXXI-ACCESS-KEY": process.env.MAXXI_ACCESS_KEY_ID,
    "X-MAXXI-SECRET-KEY": process.env.MAXXI_SECRET_ACCESS_KEY,
  },
  body: form,
});

const uploaded = await res.json();`;

const pythonUpload = `import requests

with open("photo.png", "rb") as file:
    response = requests.post(
        "${API_BASE_URL}/api/v1/files",
        headers={
            "X-MAXXI-ACCESS-KEY": "tid_your_access_key_id",
            "X-MAXXI-SECRET-KEY": "tsec_your_secret_access_key",
        },
        files={"file": file},
        timeout=120,
    )

response.raise_for_status()
print(response.json())`;

const basicAuth = `curl -u "tid_your_access_key_id:tsec_your_secret_access_key" \\
  "${API_BASE_URL}/api/v1/files"`;

function copyValue(value: string, label: string) {
  navigator.clipboard.writeText(value);
  toast.success(`${label} copied`);
}

function CodeBlock({ code, label }: { code: string; label: string }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-slate-950">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
        <span className="text-xs font-medium text-slate-300">{label}</span>
        <Button variant="ghost" size="icon" className="h-7 w-7 text-slate-300 hover:text-white" onClick={() => copyValue(code, label)}>
          <Copy className="h-3.5 w-3.5" />
        </Button>
      </div>
      <pre className="overflow-x-auto p-4 text-xs leading-6 text-slate-100">
        <code>{code}</code>
      </pre>
    </div>
  );
}

function EndpointRow({ method, path, description }: { method: string; path: string; description: string }) {
  return (
    <div className="grid gap-2 border-t border-border py-3 sm:grid-cols-[110px_1fr]">
      <div className="flex items-center gap-2">
        <span className="rounded border border-border px-2 py-1 font-mono text-xs font-semibold">{method}</span>
      </div>
      <div>
        <p className="font-mono text-sm">{path}</p>
        <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

export default function Docs() {
  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Terminal className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">Maxxi API Docs</h2>
          </div>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Use IAM access keys for server-to-server uploads, listing, metadata reads, and deletes. Google sign-in is for the dashboard; API keys are for applications.
          </p>
        </div>
        <div className="rounded-md border border-border px-3 py-2">
          <p className="text-xs text-muted-foreground">Base URL</p>
          <button className="font-mono text-sm text-primary" onClick={() => copyValue(API_BASE_URL, 'Base URL')}>
            {API_BASE_URL}
          </button>
        </div>
      </div>

      <Accordion type="multiple" defaultValue={['auth', 'curl']} className="rounded-lg border border-border bg-background">
        <AccordionItem value="browser-docs" className="px-5">
          <AccordionTrigger className="hover:no-underline">Open Docs In Browser</AccordionTrigger>
          <AccordionContent>
            <p className="mb-4 text-sm leading-6 text-muted-foreground">
              These are Maxxi API documentation endpoints. They are safe to open directly in a browser and return Maxxi endpoint data instead of storage-provider XML errors.
            </p>
            <div className="grid gap-3 md:grid-cols-2">
              {[
                ['API endpoint index', API_INDEX_URL],
                ['Docs JSON', API_DOCS_JSON_URL],
                ['Docs HTML', API_DOCS_HTML_URL],
                ['OpenAPI JSON', OPENAPI_URL],
              ].map(([label, value]) => (
                <div key={value} className="flex overflow-hidden rounded-md border bg-card">
                  <a href={value} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate px-3 py-2 font-mono text-xs text-primary hover:underline">
                    {value}
                  </a>
                  <Button variant="ghost" size="icon" className="h-9 w-9 rounded-none border-l" onClick={() => copyValue(value, label)}>
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="auth" className="px-5">
          <AccordionTrigger className="hover:no-underline">
            <span className="flex items-center gap-2">
              <KeyRound className="h-4 w-4 text-primary" />
              Authentication
            </span>
          </AccordionTrigger>
          <AccordionContent>
            <p className="text-sm leading-6 text-muted-foreground">
              Create an IAM key from Bucket Settings, then send the access key and secret key on every protected request.
            </p>
            <div className="mt-4 space-y-2 rounded-md bg-muted/40 p-3 font-mono text-xs">
              <p>X-MAXXI-ACCESS-KEY: tid_...</p>
              <p>X-MAXXI-SECRET-KEY: tsec_...</p>
            </div>
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              HTTP Basic auth also works, using the access key as the username and the secret key as the password.
            </p>
            <div className="mt-4">
              <CodeBlock label="Basic auth alternative" code={basicAuth} />
            </div>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="endpoints" className="px-5">
          <AccordionTrigger className="hover:no-underline">
            <span className="flex items-center gap-2">
              <UploadCloud className="h-4 w-4 text-primary" />
              Core Endpoints
            </span>
          </AccordionTrigger>
          <AccordionContent>
            <EndpointRow method="POST" path="/api/v1/files" description="Upload one file using multipart/form-data field name file." />
            <EndpointRow method="GET" path="/api/v1/files" description="List files. Optional query params: folder, category." />
            <EndpointRow method="GET" path="/api/v1/files/{file_id}/metadata" description="Read one file record and generated CDN URLs." />
            <EndpointRow method="GET" path="/api/v1/files/{file_id}/download" description="Stream the object. Query disposition=inline or attachment." />
            <EndpointRow method="DELETE" path="/api/v1/files/{file_id}" description="Delete one object and its metadata." />
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="curl" className="px-5">
          <AccordionTrigger className="hover:no-underline">curl Examples</AccordionTrigger>
          <AccordionContent className="space-y-4">
          <CodeBlock label="Upload with curl" code={curlUpload} />
          <CodeBlock label="List files with curl" code={curlList} />
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="javascript" className="px-5">
          <AccordionTrigger className="hover:no-underline">JavaScript Integration</AccordionTrigger>
          <AccordionContent>
          <CodeBlock label="Upload with JavaScript" code={jsUpload} />
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="python" className="px-5">
          <AccordionTrigger className="hover:no-underline">Python Integration</AccordionTrigger>
          <AccordionContent>
          <CodeBlock label="Upload with Python requests" code={pythonUpload} />
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="boto3" className="px-5">
          <AccordionTrigger className="hover:no-underline">Boto3 / S3 SDK Compatibility</AccordionTrigger>
          <AccordionContent>
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-950">
              <p className="text-sm leading-6">
                Maxxi IAM keys are shaped like cloud access keys, but the current API is a REST CDN API, not an S3-compatible XML/SigV4 API. Use the HTTP examples above for now. A boto3-compatible layer would need S3 routes such as ListBuckets, PutObject, GetObject, DeleteObject, and AWS Signature V4 validation.
              </p>
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </section>
  );
}
