import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

function safeJsonParse(text: string): any | null {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Record<string, string> }
) {
  const url = new URL(request.url)
  const { searchParams } = url
  const repoPath = searchParams.get("repo_path")

  const componentId =
    params?.componentId ??
    (params as any)?.componentid ??
    params?.[Object.keys(params || {})[0]] ??
    url.pathname.split("/").filter(Boolean).at(-1)

  if (!repoPath) {
    return NextResponse.json(
      { success: false, message: "repo_path is required" },
      { status: 400 }
    )
  }

  if (!componentId) {
    return NextResponse.json(
      { success: false, message: "componentId path param is required" },
      { status: 400 }
    )
  }

  try {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 60_000)

    try {
      const response = await fetch(
        `${BACKEND_URL}/api/graphs/cfg/${encodeURIComponent(componentId)}?repo_path=${encodeURIComponent(repoPath)}`,
        {
          headers: {
            "Content-Type": "application/json",
          },
          signal: controller.signal,
        }
      )

      const text = await response.text()
      const json = safeJsonParse(text)

      if (json !== null) {
        return NextResponse.json(json, { status: response.status })
      }

      return new NextResponse(text, {
        status: response.status,
        headers: {
          "Content-Type": response.headers.get("content-type") || "text/plain; charset=utf-8",
        },
      })
    } finally {
      clearTimeout(timeoutId)
    }
  } catch (error) {
    console.error("Error fetching CFG:", error)
    const isAbort = error instanceof Error && error.name === "AbortError"
    return NextResponse.json(
      {
        success: false,
        message: isAbort
          ? "CFG request timed out (backend took too long)"
          : "Failed to fetch CFG from backend",
        backend_url: BACKEND_URL,
      },
      { status: isAbort ? 504 : 502 }
    )
  }
}
