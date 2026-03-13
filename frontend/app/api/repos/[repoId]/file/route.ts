import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * GET /api/repos/[repoId]/file?path=src/index.ts — get a single file's content
 */
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ repoId: string }> }
) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { repoId } = await params;
    const filePath = req.nextUrl.searchParams.get("path");

    if (!filePath) {
      return NextResponse.json({ error: "Missing path parameter" }, { status: 400 });
    }

    const res = await fetch(
      `${BACKEND}/api/repos/${repoId}/file?path=${encodeURIComponent(filePath)}`,
      { cache: "no-store" }
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    console.error("GET /api/repos/[repoId]/file proxy error:", err);
    return NextResponse.json(
      { error: err.message || "Backend unreachable" },
      { status: 502 }
    );
  }
}
