from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse


router = APIRouter(prefix="/api/v1", tags=["api-docs"])


def api_docs_payload(request: Request) -> dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    api_base = f"{base_url}/api/v1"
    return {
        "name": "Maxxi CDN API",
        "version": "1.0.0",
        "base_url": base_url,
        "api_base_url": api_base,
        "authentication": {
            "type": "IAM API key or dashboard bearer token",
            "headers": {
                "X-MAXXI-ACCESS-KEY": "tid_your_access_key_id",
                "X-MAXXI-SECRET-KEY": "tsec_your_secret_access_key",
            },
            "basic_auth": "access_key_id:secret_access_key",
        },
        "browser_docs": {
            "endpoint_index": f"{api_base}/docs",
            "openapi_json": f"{api_base}/openapi.json",
            "swagger_ui": f"{base_url}/docs",
        },
        "endpoints": [
            {
                "method": "POST",
                "path": "/api/v1/files",
                "auth": "required",
                "description": "Upload one file with multipart/form-data field name file.",
            },
            {
                "method": "GET",
                "path": "/api/v1/files",
                "auth": "required",
                "description": "List files. Optional query params: folder, category.",
            },
            {
                "method": "GET",
                "path": "/api/v1/files/{file_id}/metadata",
                "auth": "required",
                "description": "Read one file record and generated CDN URLs.",
            },
            {
                "method": "GET",
                "path": "/api/v1/files/{file_id}/download",
                "auth": "public for object bytes",
                "description": "Stream the object. Query disposition=inline or attachment.",
            },
            {
                "method": "DELETE",
                "path": "/api/v1/files/{file_id}",
                "auth": "required",
                "description": "Delete one object and its metadata.",
            },
            {
                "method": "GET",
                "path": "/api/v1/me/iam-keys",
                "auth": "required",
                "description": "List IAM access keys for the current user.",
            },
            {
                "method": "POST",
                "path": "/api/v1/me/iam-keys",
                "auth": "required",
                "description": "Create an IAM access key. The secret is shown once.",
            },
        ],
    }


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
def api_index(payload: dict[str, Any] = Depends(api_docs_payload)) -> dict[str, Any]:
    return payload


@router.get("/docs", include_in_schema=False)
def api_docs(payload: dict[str, Any] = Depends(api_docs_payload)) -> dict[str, Any]:
    return payload


@router.get("/docs.html", response_class=HTMLResponse, include_in_schema=False)
def api_docs_html(payload: dict[str, Any] = Depends(api_docs_payload)) -> str:
    endpoint_rows = "\n".join(
        f"""
        <tr>
          <td><code>{endpoint["method"]}</code></td>
          <td><code>{endpoint["path"]}</code></td>
          <td>{endpoint["auth"]}</td>
          <td>{endpoint["description"]}</td>
        </tr>
        """
        for endpoint in payload["endpoints"]
    )
    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{payload["name"]}</title>
        <style>
          body {{ font-family: Inter, system-ui, sans-serif; margin: 0; color: #111827; background: #f8fafc; }}
          main {{ max-width: 980px; margin: 0 auto; padding: 40px 20px; }}
          .panel {{ background: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: 20px; margin-top: 18px; }}
          h1 {{ margin: 0; font-size: 28px; }}
          p {{ color: #4b5563; line-height: 1.6; }}
          code {{ background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 5px; padding: 2px 6px; }}
          table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
          th, td {{ border-top: 1px solid #e5e7eb; padding: 12px; text-align: left; vertical-align: top; }}
          th {{ color: #475569; font-size: 13px; }}
          a {{ color: #4f46e5; }}
        </style>
      </head>
      <body>
        <main>
          <h1>{payload["name"]}</h1>
          <p>Browser-readable endpoint index for Maxxi integrations.</p>
          <div class="panel">
            <p><strong>Base URL:</strong> <code>{payload["base_url"]}</code></p>
            <p><strong>API Base URL:</strong> <code>{payload["api_base_url"]}</code></p>
            <p><strong>Swagger UI:</strong> <a href="{payload["browser_docs"]["swagger_ui"]}">{payload["browser_docs"]["swagger_ui"]}</a></p>
            <p><strong>OpenAPI JSON:</strong> <a href="{payload["browser_docs"]["openapi_json"]}">{payload["browser_docs"]["openapi_json"]}</a></p>
          </div>
          <div class="panel">
            <h2>Authentication</h2>
            <p>Use <code>X-MAXXI-ACCESS-KEY</code> and <code>X-MAXXI-SECRET-KEY</code>, or HTTP Basic auth with access key ID as username and secret key as password.</p>
          </div>
          <div class="panel">
            <h2>Endpoints</h2>
            <table>
              <thead>
                <tr><th>Method</th><th>Path</th><th>Auth</th><th>Description</th></tr>
              </thead>
              <tbody>{endpoint_rows}</tbody>
            </table>
          </div>
        </main>
      </body>
    </html>
    """
