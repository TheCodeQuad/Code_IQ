import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * POST /api/repos/[repoId]/generate — kick off the documentation pipeline
 */
export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ repoId: string }> }
) {
  try {
    const session = await getServerSession();
    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { repoId } = await params;

    const res = await fetch(`${BACKEND}/api/repos/${repoId}/generate`, {
      method: "POST",
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
