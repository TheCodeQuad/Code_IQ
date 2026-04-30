import os
import json

# Define the directory structure and files
base_path = r'C:\BIA6\CodeIQ\Code_IQ\frontend\app\api\graphs\ckg'

# Create directories
directories = [
    base_path,
    os.path.join(base_path, 'stats'),
    os.path.join(base_path, 'subgraph')
]

for directory in directories:
    os.makedirs(directory, exist_ok=True)
    print(f"Created directory: {directory}")

# Define the files to create
files = {
    os.path.join(base_path, 'route.ts'): '''import { NextRequest, NextResponse } from "next/server"

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
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 120000)

    const response = await fetch(`$${BACKEND_URL}/api/graphs/ckg?$${params}`, {
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
}''',
    os.path.join(base_path, 'stats', 'route.ts'): '''import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const repoPath = searchParams.get("repo_path")

  if (!repoPath) {
    return NextResponse.json({ success: false, message: "repo_path is required" }, { status: 400 })
  }

  try {
    const params = new URLSearchParams({ repo_path: repoPath })
    const response = await fetch(`$${BACKEND_URL}/api/graphs/ckg/stats?$${params}`, {
      headers: { "Content-Type": "application/json" },
    })

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    return NextResponse.json({ success: false, message: "Failed to fetch CKG stats" }, { status: 502 })
  }
}''',
    os.path.join(base_path, 'subgraph', 'route.ts'): '''import { NextRequest, NextResponse } from "next/server"

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

    const response = await fetch(`$${BACKEND_URL}/api/graphs/ckg/subgraph?$${params}`, {
      headers: { "Content-Type": "application/json" },
    })

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    return NextResponse.json({ success: false, message: "Failed to fetch CKG subgraph" }, { status: 502 })
  }
}'''
}

# Create the files
for file_path, content in files.items():
    with open(file_path, 'w') as f:
        f.write(content)
    print(f"Created file: {file_path}")

print("\nAll directories and files created successfully!")

# Verify the files exist
print("\nVerification:")
for file_path in files.keys():
    if os.path.exists(file_path):
        file_size = os.path.getsize(file_path)
        print(f"✓ {file_path} ({file_size} bytes)")
    else:
        print(f"✗ {file_path} (NOT FOUND)")
