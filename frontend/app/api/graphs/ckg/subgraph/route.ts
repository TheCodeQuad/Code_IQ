import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const repoPath = searchParams.get("repo_path")
  const componentId = searchParams.get("component_id")
  const kHops = searchParams.get("k_hops") || "1"
  const edgeTypes = searchParams.get("edge_types")
  const direction = searchParams.get("direction") || "both"

  if (!repoPath || !componentId) {
    return NextResponse.json({ success: false, message: "repo_path and component_id required" }, { status: 400 })
  }

  try {
    const params = new URLSearchParams({ repo_path: repoPath, component_id: componentId, k_hops: kHops, direction })
    if (edgeTypes) params.set("edge_types", edgeTypes)

    const response = await fetch(`${BACKEND_URL}/api/graphs/ckg/subgraph?${params}`, {
      headers: { "Content-Type": "application/json" },
    })

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    return NextResponse.json({ success: false, message: "Failed to fetch CKG subgraph" }, { status: 502 })
  }
}
