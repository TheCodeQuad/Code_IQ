import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

function safeJsonParse(text: string): any | null {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const repoPath = searchParams.get("repo_path")
  const componentId = searchParams.get("component_id")
  const filePath = searchParams.get("file_path")
  const neighborhoodDepth = searchParams.get("neighborhood_depth") || "1"

  if (!repoPath) {
    return NextResponse.json(
      { success: false, message: "repo_path is required" },
      { status: 400 }
    )
  }

  try {
    const params = new URLSearchParams({
      repo_path: repoPath,
      neighborhood_depth: neighborhoodDepth,
    })

    if (componentId) {
      params.set("component_id", componentId)
    }
    if (filePath) {
      params.set("file_path", filePath)
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 60_000)

    try {
      const response = await fetch(
        `${BACKEND_URL}/api/graphs/dag?${params.toString()}`,
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
    console.error("Error fetching DAG:", error)
    const isAbort = error instanceof Error && error.name === "AbortError"
    return NextResponse.json(
      {
        success: false,
        message: isAbort
          ? "DAG request timed out (backend took too long)"
          : "Failed to fetch DAG from backend",
        backend_url: BACKEND_URL,
      },
      { status: isAbort ? 504 : 502 }
    )
  }
}
