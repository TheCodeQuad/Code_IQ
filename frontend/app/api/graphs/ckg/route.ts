import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const repoPath = searchParams.get("repo_path")
  const force = searchParams.get("force") || "false"

  if (!repoPath) {
    return NextResponse.json({ success: false, message: "repo_path is required" }, { status: 400 })
  }

  try {
    const params = new URLSearchParams({ repo_path: repoPath, force: force })

    // Allow long-running CKG builds by using a generous timeout (default 10 minutes).
    const timeoutMs = Number(process.env.CKG_TIMEOUT_MS ?? "600000")
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

    const response = await fetch(`${BACKEND_URL}/api/graphs/ckg?${params}`, {
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    })

    clearTimeout(timeoutId)

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error: any) {
    const isAbort = error?.name === "AbortError"
    return NextResponse.json(
      { success: false, message: isAbort ? "CKG request timed out" : "Failed to fetch CKG" },
      { status: isAbort ? 504 : 502 }
    )
  }
}
