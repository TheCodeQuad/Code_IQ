import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * GET /api/analysis/[analysisId]/export — download documentation as ZIP
 */
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ analysisId: string }> }
) {
  try {
    const { analysisId } = await params;

    console.log(`[API Proxy] GET /api/analysis/${analysisId}/export`);

    const res = await fetch(
      `${BACKEND}/api/analysis/${analysisId}/export`,
      { cache: "no-store" }
    );

    if (!res.ok) {
      const errorText = await res.text();
      console.error(`[API Proxy] Backend error: ${res.status}`, errorText);
      return NextResponse.json(
        { error: `Export failed: ${errorText}` },
        { status: res.status }
      );
    }

    // Stream the ZIP file back to client
    const blob = await res.blob();

    // Get filename from Content-Disposition header or use default
    const contentDisposition = res.headers.get("Content-Disposition");
    const filenameMatch = contentDisposition?.match(/filename="(.+)"/);
    const filename = filenameMatch ? filenameMatch[1] : "documentation.zip";

    return new NextResponse(blob, {
      status: 200,
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="${filename}"`,
      },
    });
  } catch (err: unknown) {
    const errorMessage = err instanceof Error ? err.message : "Backend unreachable";
    console.error("[API Proxy] GET /api/analysis/[analysisId]/export error:", err);
    return NextResponse.json(
      { error: errorMessage },
      { status: 502 }
    );
  }
}
