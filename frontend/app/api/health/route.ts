import { NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * GET /api/health
 * Proxies health check to the Python backend.
 */
export async function GET() {
  try {
    const backendRes = await fetch(`${BACKEND_URL}/health`, {
      cache: "no-store",
    });

    if (!backendRes.ok) {
      return NextResponse.json(
        { status: "unhealthy", error: "Backend returned non-OK" },
        { status: backendRes.status }
      );
    }

    const data = await backendRes.json();
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json(
      { status: "unreachable", error: error.message || "Cannot connect to backend" },
      { status: 502 }
    );
  }
}
