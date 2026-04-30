import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * POST /api/repos/[repoId]/generate — kick off the documentation pipeline
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ repoId: string }> }
) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { repoId } = await params;

    let payload: unknown = undefined;
    const contentType = req.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      payload = await req.json().catch(() => undefined);
    }

    const res = await fetch(`${BACKEND}/api/repos/${repoId}/generate`, {
      method: "POST",
      headers: payload ? { "Content-Type": "application/json" } : undefined,
      body: payload ? JSON.stringify(payload) : undefined,
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    console.error("POST /api/repos/[repoId]/generate proxy error:", err);
    return NextResponse.json(
      { error: err.message || "Backend unreachable" },
      { status: 502 }
    );
  }
}
