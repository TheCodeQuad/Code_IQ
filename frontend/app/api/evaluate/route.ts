import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function normalizeBackendBase(url: string): string {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

function buildEvaluateUrls(base: string): string[] {
  const normalizedBase = normalizeBackendBase(base);
  const urls = [`${normalizedBase}/evaluate`];

  // If localhost resolution is flaky in runtime (IPv6/IPv4 mismatch), retry with explicit IPv4.
  if (normalizedBase.includes("localhost")) {
    urls.push(`${normalizedBase.replace("localhost", "127.0.0.1")}/evaluate`);
  }

  return urls;
}

/**
 * GET /api/evaluate?repo_name=xxx
 * Fetches saved evaluation results from backend.
 * Returns scores as percentages (0-100).
 */
export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const repoName = searchParams.get("repo_name");
    
    if (!repoName) {
      return NextResponse.json(
        { error: "repo_name query parameter is required" },
        { status: 400 }
      );
    }

    const base = normalizeBackendBase(BACKEND_URL);
    const url = `${base}/evaluate/${encodeURIComponent(repoName)}`;

    const backendRes = await fetch(url, {
      method: "GET",
      cache: "no-store",
    });

    const raw = await backendRes.text();
    let data: any = null;
    try {
      data = raw ? JSON.parse(raw) : null;
    } catch {
      data = null;
    }

    if (!backendRes.ok) {
      return NextResponse.json(
        {
          error:
            data?.detail ||
            data?.error ||
            raw ||
            `No evaluation results found (HTTP ${backendRes.status})`,
        },
        { status: backendRes.status }
      );
    }

    return NextResponse.json(data ?? { success: false });
  } catch (error: any) {
    console.error("Evaluate GET proxy error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to fetch evaluation results" },
      { status: 502 }
    );
  }
}

/**
 * POST /api/evaluate
 * Proxies evaluation request to backend /evaluate endpoint.
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const evaluateUrls = buildEvaluateUrls(BACKEND_URL);
    let lastConnectionError: unknown = null;

    for (const url of evaluateUrls) {
      try {
        const backendRes = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          cache: "no-store",
        });

        const raw = await backendRes.text();
        let data: any = null;
        try {
          data = raw ? JSON.parse(raw) : null;
        } catch {
          data = null;
        }

        if (!backendRes.ok) {
          return NextResponse.json(
            {
              error:
                data?.detail ||
                data?.error ||
                raw ||
                `Backend evaluation failed (HTTP ${backendRes.status})`,
            },
            { status: backendRes.status }
          );
        }

        return NextResponse.json(data ?? { success: true, message: raw || "Evaluation completed" });
      } catch (err) {
        lastConnectionError = err;
      }
    }

    throw lastConnectionError || new Error("Failed to connect to backend evaluate endpoint");
  } catch (error: any) {
    console.error("Evaluate proxy error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to connect to backend" },
      { status: 502 }
    );
  }
}
