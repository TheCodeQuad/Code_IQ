import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

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

    const response = await fetch(
      `${BACKEND_URL}/api/graphs/dag?${params.toString()}`,
      {
        headers: {
          "Content-Type": "application/json",
        },
      }
    )

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error("Error fetching DAG:", error)
    return NextResponse.json(
      { success: false, message: "Failed to fetch DAG" },
      { status: 500 }
    )
  }
}
