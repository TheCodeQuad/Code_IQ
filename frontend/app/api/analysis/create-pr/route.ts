import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * POST /api/analysis/create-pr — create a pull request on GitHub
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    console.log(`[API Proxy] POST /api/analysis/create-pr, body:`, body);

    const res = await fetch(`${BACKEND}/api/analysis/create-pr`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    console.log(`[API Proxy] Backend response status: ${res.status}`);

    if (!res.ok) {
      const errorText = await res.text();
      console.error(`[API Proxy] Backend error: ${res.status}`, errorText);
      return NextResponse.json(
        { error: `Backend error: ${errorText}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    console.log(`[API Proxy] Success response:`, data);
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    console.error("[API Proxy] POST /api/analysis/create-pr error:", err);
    return NextResponse.json(
      { error: err.message || "Backend unreachable" },
      { status: 502 }
    );
  }
}
