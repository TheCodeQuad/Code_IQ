import os
import sys

# Change to script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Define paths
base_path = 'frontend/app/api/graphs/ckg'

# Create directories
try:
    os.makedirs(os.path.join(base_path, 'stats'), exist_ok=True)
    os.makedirs(os.path.join(base_path, 'subgraph'), exist_ok=True)
    print(f"Created: {base_path}")
    print(f"Created: {os.path.join(base_path, 'stats')}")
    print(f"Created: {os.path.join(base_path, 'subgraph')}")
except Exception as e:
    print(f"Error creating directories: {e}")
    sys.exit(1)

# File contents
files = {
    'frontend/app/api/graphs/ckg/route.ts': '''import { NextRequest, NextResponse } from "next/server"

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
''',
    'frontend/app/api/graphs/ckg/stats/route.ts': '''import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const repoPath = searchParams.get("repo_path")

  if (!repoPath) {
    return NextResponse.json({ success: false, message: "repo_path is required" }, { status: 400 })
  }

  try {
    const params = new URLSearchParams({ repo_path: repoPath })
    const response = await fetch(`${BACKEND_URL}/api/graphs/ckg/stats?${params}`, {
      headers: { "Content-Type": "application/json" },
    })

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    return NextResponse.json({ success: false, message: "Failed to fetch CKG stats" }, { status: 502 })
  }
}
''',
    'frontend/app/api/graphs/ckg/subgraph/route.ts': '''import { NextRequest, NextResponse } from "next/server"

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
'''
}

# Create files
for file_path, content in files.items():
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        size = os.path.getsize(file_path)
        print(f"Created: {file_path} ({size} bytes)")
    except Exception as e:
        print(f"Error creating {file_path}: {e}")
        sys.exit(1)

print("\n✓ All directories and files created successfully!")
print("\nRestart your frontend server (npm run dev) to load the new routes.")
