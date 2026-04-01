import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

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
    const response = await fetch(
      `${BACKEND_URL}/api/graphs/components?repo_path=${encodeURIComponent(repoPath)}`,
      {
        headers: {
          "Content-Type": "application/json",
        },
      }
    )

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error("Error fetching components:", error)
    return NextResponse.json(
      { success: false, message: "Failed to fetch components" },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    const response = await fetch(`${BACKEND_URL}/api/graphs/parse`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error("Error parsing repository:", error)
    return NextResponse.json(
      { success: false, message: "Failed to parse repository" },
      { status: 500 }
    )
  }
}
