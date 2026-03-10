import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * GET /api/repos  — list repos for the authenticated user
 * POST /api/repos — upload (clone) a new repo
 */

export async function GET(req: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    // Use the user's email as a stable identifier to look up their Mongo _id
    const userId = (session.user as any).id;
    if (!userId) {
      return NextResponse.json(
        { error: "User ID missing from session" },
        { status: 400 }
      );
    }

    const res = await fetch(
      `${BACKEND}/api/repos?user_id=${encodeURIComponent(userId)}`,
      { cache: "no-store" }
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    console.error("GET /api/repos proxy error:", err);
    return NextResponse.json(
      { error: err.message || "Backend unreachable" },
      { status: 502 }
    );
  }
}

export async function POST(req: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const userId = (session.user as any).id;
    if (!userId) {
      return NextResponse.json(
        { error: "User ID missing from session" },
        { status: 400 }
      );
    }

    const body = await req.json();

    const res = await fetch(`${BACKEND}/api/repos/upload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: body.repo_url, user_id: userId }),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    console.error("POST /api/repos proxy error:", err);
    return NextResponse.json(
      { error: err.message || "Backend unreachable" },
      { status: 502 }
    );
  }
}
