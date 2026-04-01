import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function GET(
  request: NextRequest,
  { params }: { params: { componentId: string } }
) {
  const { searchParams } = new URL(request.url)
  const repoPath = searchParams.get("repo_path")
  const componentId = params.componentId

  if (!repoPath) {
    return NextResponse.json(
      { success: false, message: "repo_path is required" },
      { status: 400 }
    )
  }

  try {
    const response = await fetch(
      `${BACKEND_URL}/api/graphs/hpg/${encodeURIComponent(componentId)}?repo_path=${encodeURIComponent(repoPath)}`,
      {
        headers: {
          "Content-Type": "application/json",
        },
      }
    )

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error("Error fetching HPG:", error)
    return NextResponse.json(
      { success: false, message: "Failed to fetch HPG" },
      { status: 500 }
    )
  }
}
