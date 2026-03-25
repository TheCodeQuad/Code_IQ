import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function parseGithubFullName(value?: string | null): string | null {
  if (!value) return null;
  const raw = value.trim();
  if (!raw) return null;

  if (/^[\w.-]+\/[\w.-]+$/.test(raw)) return raw;

  const httpsMatch = raw.match(/github\.com\/([\w.-]+\/[\w.-]+?)(?:\.git)?(?:$|\/)/i);
  if (httpsMatch?.[1]) return httpsMatch[1];

  const sshMatch = raw.match(/github\.com:([\w.-]+\/[\w.-]+?)(?:\.git)?$/i);
  if (sshMatch?.[1]) return sshMatch[1];

  return null;
}

/**
 * POST /api/analysis/create-pr-safe — create a pull request with a new branch (safe workflow)
 *
 * This endpoint:
 * 1. Creates a new source branch from the base branch
 * 2. Optionally commits file changes to the new branch
 * 3. Opens a PR from source -> base
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    console.log(`[API Proxy] POST /api/analysis/create-pr-safe, body:`, {
      ...body,
      description: body.description?.substring(0, 100) + "...",
    });

    const res = await fetch(`${BACKEND}/api/analysis/create-pr-safe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    console.log(`[API Proxy] Backend response status: ${res.status}`);

    const responseText = await res.text();
    let data;

    try {
      data = JSON.parse(responseText);
    } catch {
      console.error(`[API Proxy] Failed to parse response as JSON:`, responseText);
      return NextResponse.json(
        { error: responseText || "Backend error" },
        { status: res.status }
      );
    }

    if (!res.ok) {
      // Fallback: backend analysis routes unavailable (404)
      if (res.status === 404) {
        console.log(`[API Proxy] Backend analysis route unavailable (404), attempting fallback...`);
        
        const session = await getServerSession(authOptions);
        const userId = (session?.user as any)?.id;

        if (!userId) {
          return NextResponse.json(
            { error: "User not authenticated", error_type: "not_authenticated" },
            { status: 401 }
          );
        }

        // Provide helpful guidance to restart the backend
        return NextResponse.json(
          {
            error:
              "The analysis PR endpoint is temporarily unavailable. This usually means the backend needs to be restarted. " +
              "Please refresh the page (Ctrl+F5) and try again. If the problem persists, the backend server may need to be restarted.",
            error_type: "service_unavailable",
            suggestion:
              "Run: python -m uvicorn backend.app:app --reload",
          },
          { status: 503 }
        );
      }

      console.error(`[API Proxy] Backend error:`, data);
      // Pass through the structured error from backend
      return NextResponse.json(
        {
          error: data.detail?.message || data.detail || data.error || "Failed to create PR",
          error_type: data.detail?.error_type || "unknown",
          details: data.detail,
        },
        { status: res.status }
      );
    }

    console.log(`[API Proxy] Success response:`, data);
    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    const errorMessage = err instanceof Error ? err.message : "Backend unreachable";
    console.error("[API Proxy] POST /api/analysis/create-pr-safe error:", err);
    return NextResponse.json(
      { error: errorMessage, error_type: "network_error" },
      { status: 502 }
    );
  }
}
