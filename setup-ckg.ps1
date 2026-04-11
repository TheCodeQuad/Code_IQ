$ErrorActionPreference = "Stop"

# Define paths
$basePath = "frontend/app/api/graphs/ckg"
$directories = @(
    $basePath,
    "$basePath/stats",
    "$basePath/subgraph"
)

# Create directories
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created directory: $dir"
    } else {
        Write-Host "Directory already exists: $dir"
    }
}

# Define files
$files = @{
    "$basePath/route.ts" = @'
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
'@;
    "$basePath/stats/route.ts" = @'
import { NextRequest, NextResponse } from "next/server"

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
'@;
    "$basePath/subgraph/route.ts" = @'
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
'@
}

# Create files
foreach ($filePath in $files.Keys) {
    $content = $files[$filePath]
    $dir = Split-Path -Parent $filePath
    
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    
    Set-Content -Path $filePath -Value $content -Encoding UTF8
    $size = (Get-Item $filePath).Length
    Write-Host "Created file: $filePath ($size bytes)"
}

Write-Host "`n✓ All directories and files created successfully!"

# Verification
Write-Host "`nVerification:"
foreach ($dir in $directories) {
    if (Test-Path $dir) {
        Write-Host "✓ Directory exists: $dir"
    } else {
        Write-Host "✗ Directory NOT found: $dir"
    }
}

foreach ($filePath in $files.Keys) {
    if (Test-Path $filePath) {
        $size = (Get-Item $filePath).Length
        Write-Host "✓ File exists: $filePath ($size bytes)"
    } else {
        Write-Host "✗ File NOT found: $filePath"
    }
}
