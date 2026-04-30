#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

// Define the target directory structure
const baseDir = path.join(__dirname, 'frontend', 'app', 'api', 'graphs', 'ckg');

const directories = [
  baseDir,
  path.join(baseDir, 'stats'),
  path.join(baseDir, 'subgraph')
];

// Create directories
directories.forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`Created: ${dir}`);
  } else {
    console.log(`Already exists: ${dir}`);
  }
});

// File contents
const files = {
  'route.ts': `import { NextRequest, NextResponse } from "next/server"

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

    const response = await fetch(\`\${BACKEND_URL}/api/graphs/ckg?\${params}\`, {
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
}`,
  'stats/route.ts': `import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const repoPath = searchParams.get("repo_path")

  if (!repoPath) {
    return NextResponse.json({ success: false, message: "repo_path is required" }, { status: 400 })
  }

  try {
    const params = new URLSearchParams({ repo_path: repoPath })
    const response = await fetch(\`\${BACKEND_URL}/api/graphs/ckg/stats?\${params}\`, {
      headers: { "Content-Type": "application/json" },
    })

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    return NextResponse.json({ success: false, message: "Failed to fetch CKG stats" }, { status: 502 })
  }
}`,
  'subgraph/route.ts': `import { NextRequest, NextResponse } from "next/server"

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

    const response = await fetch(\`\${BACKEND_URL}/api/graphs/ckg/subgraph?\${params}\`, {
      headers: { "Content-Type": "application/json" },
    })

    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    return NextResponse.json({ success: false, message: "Failed to fetch CKG subgraph" }, { status: 502 })
  }
}`
};

// Create files
Object.entries(files).forEach(([filePath, content]) => {
  const fullPath = path.join(baseDir, filePath);
  const dir = path.dirname(fullPath);
  
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  
  fs.writeFileSync(fullPath, content, 'utf-8');
  const size = fs.statSync(fullPath).size;
  console.log(`Created: ${fullPath} (${size} bytes)`);
});

console.log('\n✓ All directories and files created successfully!');

// Verification
console.log('\nVerification:');
directories.forEach(dir => {
  if (fs.existsSync(dir)) {
    console.log(`✓ Directory exists: ${dir}`);
  } else {
    console.log(`✗ Directory NOT found: ${dir}`);
  }
});

Object.keys(files).forEach(filePath => {
  const fullPath = path.join(baseDir, filePath);
  if (fs.existsSync(fullPath)) {
    const size = fs.statSync(fullPath).size;
    console.log(`✓ File exists: ${fullPath} (${size} bytes)`);
  } else {
    console.log(`✗ File NOT found: ${fullPath}`);
  }
});
