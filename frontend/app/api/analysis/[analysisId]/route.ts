import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * GET /api/analysis/[analysisId]/repo — fetch repository data for an analysis
 */
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ analysisId: string }> }
) {
  try {
    const { analysisId } = await params;

    console.log(`[API Proxy] GET /api/analysis/${analysisId}/repo -> ${BACKEND}/api/analysis/${analysisId}/repo`);

    const res = await fetch(
      `${BACKEND}/api/analysis/${analysisId}/repo`,
      { cache: "no-store" }
    );

    if (!res.ok) {
      const errorText = await res.text();
      console.error(`[API Proxy] Backend error: ${res.status}`, errorText);
      return NextResponse.json(
        { error: `Backend returned ${res.status}: ${errorText}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    console.log(`[API Proxy] Response:`, data);
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    console.error("[API Proxy] GET /api/analysis/[analysisId] error:", err);
    return NextResponse.json(
      { error: err.message || "Backend unreachable" },
      { status: 502 }
    );
  }
}
