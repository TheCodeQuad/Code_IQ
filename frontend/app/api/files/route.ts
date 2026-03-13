import { NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * GET /api/files
 * Proxies file listing to the Python backend.
 */
export async function GET() {
  try {
    const backendRes = await fetch(`${BACKEND_URL}/files`, {
      cache: "no-store",
    });

    if (!backendRes.ok) {
      return NextResponse.json(
        { error: "Backend returned non-OK" },
        { status: backendRes.status }
      );
    }

    const data = await backendRes.json();
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Cannot connect to backend" },
      { status: 502 }
    );
  }
}
