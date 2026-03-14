import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * GET /api/repos/[repoId]/events
 * Proxies backend Server-Sent Events for live pipeline progress updates.
 */
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ repoId: string }> }
) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { repoId } = await params;

    const upstream = await fetch(`${BACKEND}/api/repos/${repoId}/events`, {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "text/event-stream",
      },
    });

    if (!upstream.ok || !upstream.body) {
      let detail = `HTTP ${upstream.status}`;
      try {
        const data = await upstream.json();
        detail = data?.detail || data?.error || detail;
      } catch {
        // best-effort error parsing
      }
      return NextResponse.json({ error: detail }, { status: upstream.status || 502 });
    }

    return new Response(upstream.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  } catch (err: any) {
    console.error("GET /api/repos/[repoId]/events proxy error:", err);
    return NextResponse.json(
      { error: err.message || "Backend unreachable" },
      { status: 502 }
    );
  }
}
