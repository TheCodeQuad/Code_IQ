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

  if (!repoPath) {
    return NextResponse.json(
      { success: false, message: "repo_path is required" },
      { status: 400 }
    )
  }

  try {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 60_000)

    try {
      const response = await fetch(
        `${BACKEND_URL}/api/graphs/components?repo_path=${encodeURIComponent(repoPath)}`,
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
    console.error("Error fetching components:", error)
    const isAbort = error instanceof Error && error.name === "AbortError"
    return NextResponse.json(
      {
        success: false,
        message: isAbort
          ? "Components request timed out (backend took too long)"
          : "Failed to fetch components from backend",
        backend_url: BACKEND_URL,
      },
      { status: isAbort ? 504 : 502 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 60_000)

    try {
      const response = await fetch(`${BACKEND_URL}/api/graphs/parse`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

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
    console.error("Error parsing repository:", error)
    const isAbort = error instanceof Error && error.name === "AbortError"
    return NextResponse.json(
      {
        success: false,
        message: isAbort
          ? "Parse request timed out (backend took too long)"
          : "Failed to parse repository via backend",
        backend_url: BACKEND_URL,
      },
      { status: isAbort ? 504 : 502 }
    )
  }
}
