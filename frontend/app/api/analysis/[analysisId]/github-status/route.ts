import { NextRequest, NextResponse } from "next/server"

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ analysisId: string }> }
) {
  try {
    const { analysisId } = await params
    console.log(`[API Proxy] GET /api/analysis/${analysisId}/github-status`)

    const res = await fetch(`${BACKEND}/api/analysis/${analysisId}/github-status`)

    console.log(`[API Proxy] Backend response status: ${res.status}`)

    if (!res.ok) {
      const errorText = await res.text()
      console.error(`[API Proxy] Backend error: ${res.status}`, errorText)
      return NextResponse.json(
        { error: `Backend error: ${errorText}` },
        { status: res.status }
      )
    }

    const data = await res.json()
    console.log(`[API Proxy] GitHub status response:`, data)
    return NextResponse.json(data, { status: res.status })
  } catch (err: any) {
    console.error("[API Proxy] GET github-status error:", err)
    return NextResponse.json(
      { error: err.message || "Backend unreachable" },
      { status: 502 }
    )
  }
}
