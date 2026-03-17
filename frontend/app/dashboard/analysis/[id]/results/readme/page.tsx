"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  FileText,
  Download,
  Copy,
  Check,
  Eye,
  Code2,
  Sparkles,
  RefreshCw,
  BookOpen,
  List,
  Settings,
  Loader2,
  CheckCircle2,
  Hash,
  Table,
  Code,
} from "lucide-react"

const readmeContent = `# API Gateway

A high-performance API gateway service built with Python and FastAPI.

## Overview

This service provides a centralized entry point for all API requests, handling:
- Request routing and load balancing
- Authentication and authorization
- Rate limiting and throttling
- Request/response transformation
- Logging and monitoring

## Features

- **High Performance**: Built with FastAPI for maximum throughput
- **Scalable**: Designed for horizontal scaling with stateless architecture
- **Secure**: JWT-based authentication with refresh token support
- **Observable**: Built-in metrics and distributed tracing support

## Installation

\`\`\`bash
# Clone the repository
git clone https://github.com/example/api-gateway.git
cd api-gateway

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
\`\`\`

## Configuration

Configuration is managed through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| \`API_PORT\` | Server port | 8000 |
| \`DB_URL\` | Database connection string | - |
| \`JWT_SECRET\` | Secret key for JWT tokens | - |
| \`REDIS_URL\` | Redis connection for caching | - |
| \`LOG_LEVEL\` | Logging level | INFO |

## API Reference

### Authentication

#### POST /auth/login

Authenticate a user and return an access token.

**Request Body:**
\`\`\`json
{
  "username": "string",
  "password": "string",
  "remember_me": false
}
\`\`\`

**Response:**
\`\`\`json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600
}
\`\`\`

#### POST /auth/refresh

Refresh an expired access token.

**Headers:**
\`\`\`
Authorization: Bearer <refresh_token>
\`\`\`

**Response:**
\`\`\`json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600
}
\`\`\`

### Users

#### GET /users/me

Get the current authenticated user's profile.

**Headers:**
\`\`\`
Authorization: Bearer <access_token>
\`\`\`

**Response:**
\`\`\`json
{
  "id": "uuid",
  "username": "string",
  "email": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
\`\`\`

## Architecture

\`\`\`
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  API Gateway │────▶│  Services   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
               ┌────▼────┐  ┌────▼────┐
               │  Redis  │  │   DB    │
               └─────────┘  └─────────┘
\`\`\`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details.
`

const tableOfContents = [
  { id: "overview", title: "Overview", level: 1 },
  { id: "features", title: "Features", level: 1 },
  { id: "installation", title: "Installation", level: 1 },
  { id: "configuration", title: "Configuration", level: 1 },
  { id: "api-reference", title: "API Reference", level: 1 },
  { id: "authentication", title: "Authentication", level: 2 },
  { id: "users", title: "Users", level: 2 },
  { id: "architecture", title: "Architecture", level: 1 },
  { id: "contributing", title: "Contributing", level: 1 },
  { id: "license", title: "License", level: 1 },
]

export default function ReadmePage() {
  const [copied, setCopied] = useState(false)
  const [view, setView] = useState<"preview" | "raw">("preview")
  const [isGenerating, setIsGenerating] = useState(false)
  const [showToc, setShowToc] = useState(true)

  const handleCopy = () => {
    navigator.clipboard.writeText(readmeContent)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const blob = new Blob([readmeContent], { type: "text/markdown" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "README.md"
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleGenerate = () => {
    setIsGenerating(true)
    setTimeout(() => setIsGenerating(false), 2000)
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-400 to-amber-500 flex items-center justify-center shadow-lg shadow-amber-200">
            <FileText className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-stone-800">README.md</h2>
            <p className="text-sm text-stone-500">
              Auto-generated documentation for your repository
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleGenerate}
            disabled={isGenerating}
            className="gap-2 border-amber-200 text-amber-700 hover:bg-amber-50"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                Generate README
              </>
            )}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowToc(!showToc)}
            className={`gap-2 border-stone-200 ${showToc ? "bg-stone-100" : ""}`}
          >
            <List className="w-4 h-4" />
            TOC
          </Button>
          <Button variant="outline" size="sm" onClick={handleCopy} className="gap-2 border-stone-200">
            {copied ? (
              <>
                <Check className="w-4 h-4 text-emerald-500" />
                Copied
              </>
            ) : (
              <>
                <Copy className="w-4 h-4" />
                Copy
              </>
            )}
          </Button>
          <Button variant="outline" size="sm" onClick={handleDownload} className="gap-2 border-stone-200">
            <Download className="w-4 h-4" />
            Download
          </Button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="flex items-center gap-6 p-4 bg-white rounded-xl border border-stone-200">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
            <Hash className="w-4 h-4 text-blue-600" />
          </div>
          <div>
            <p className="text-lg font-semibold text-stone-800">8</p>
            <p className="text-xs text-stone-500">Sections</p>
          </div>
        </div>
        <div className="h-8 w-px bg-stone-200" />
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center">
            <Code className="w-4 h-4 text-purple-600" />
          </div>
          <div>
            <p className="text-lg font-semibold text-stone-800">6</p>
            <p className="text-xs text-stone-500">Code Blocks</p>
          </div>
        </div>
        <div className="h-8 w-px bg-stone-200" />
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center">
            <Table className="w-4 h-4 text-emerald-600" />
          </div>
          <div>
            <p className="text-lg font-semibold text-stone-800">1</p>
            <p className="text-xs text-stone-500">Tables</p>
          </div>
        </div>
        <div className="h-8 w-px bg-stone-200" />
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center">
            <Settings className="w-4 h-4 text-amber-600" />
          </div>
          <div>
            <p className="text-lg font-semibold text-stone-800">4</p>
            <p className="text-xs text-stone-500">API Endpoints</p>
          </div>
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-500" />
          <span className="text-sm font-medium text-emerald-700">Complete</span>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex gap-5">
        {/* Table of Contents */}
        {showToc && (
          <Card className="w-64 flex-shrink-0 border-stone-200 bg-white">
            <CardHeader className="pb-3 border-b border-stone-100">
              <div className="flex items-center gap-2 text-sm font-medium text-stone-700">
                <BookOpen className="w-4 h-4" />
                Table of Contents
              </div>
            </CardHeader>
            <CardContent className="p-3">
              <nav className="space-y-1">
                {tableOfContents.map((item) => (
                  <a
                    key={item.id}
                    href={`#${item.id}`}
                    className={`block py-1.5 px-2 text-sm rounded-md transition-colors hover:bg-stone-100 ${
                      item.level === 1 ? "text-stone-700 font-medium" : "text-stone-500 pl-4"
                    }`}
                  >
                    {item.title}
                  </a>
                ))}
              </nav>
            </CardContent>
          </Card>
        )}

        {/* README Content */}
        <Card className="flex-1 border-stone-200 bg-white overflow-hidden">
          <CardHeader className="pb-0 border-b border-stone-100">
            <div className="flex items-center justify-between pb-3">
              <div className="flex items-center gap-3">
                <Badge className="bg-emerald-100 text-emerald-700 border-0">
                  <CheckCircle2 className="w-3 h-3 mr-1" />
                  Generated
                </Badge>
                <span className="text-xs text-stone-400">Last updated: 2 minutes ago</span>
              </div>
              <Tabs value={view} onValueChange={(v) => setView(v as typeof view)}>
                <TabsList className="bg-stone-100 p-0.5">
                  <TabsTrigger value="preview" className="gap-1.5 text-xs data-[state=active]:bg-white">
                    <Eye className="w-3.5 h-3.5" />
                    Preview
                  </TabsTrigger>
                  <TabsTrigger value="raw" className="gap-1.5 text-xs data-[state=active]:bg-white">
                    <Code2 className="w-3.5 h-3.5" />
                    Markdown
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {view === "preview" ? (
              <ScrollArea className="h-[calc(100vh-380px)] min-h-[500px]">
                <div className="p-6">
                  <MarkdownPreview content={readmeContent} />
                </div>
              </ScrollArea>
            ) : (
              <ScrollArea className="h-[calc(100vh-380px)] min-h-[500px]">
                <div className="p-4">
                  <pre className="bg-stone-900 text-stone-100 p-6 rounded-xl text-sm overflow-x-auto font-mono leading-relaxed">
                    <code>{readmeContent}</code>
                  </pre>
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// Enhanced markdown preview component
function MarkdownPreview({ content }: { content: string }) {
  const lines = content.split("\n")
  const elements: React.ReactNode[] = []
  let inCodeBlock = false
  let codeContent: string[] = []
  let codeLanguage = ""
  let inTable = false
  let tableRows: string[][] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // Code blocks
    if (line.startsWith("```")) {
      if (inCodeBlock) {
        elements.push(
          <div key={i} className="my-4 rounded-xl overflow-hidden border border-stone-200">
            <div className="bg-stone-100 px-4 py-2 flex items-center justify-between border-b border-stone-200">
              <span className="text-xs font-medium text-stone-500 uppercase">{codeLanguage || "code"}</span>
              <Button variant="ghost" size="sm" className="h-6 px-2 text-xs">
                <Copy className="w-3 h-3 mr-1" />
                Copy
              </Button>
            </div>
            <pre className="bg-stone-900 text-stone-100 p-4 text-sm overflow-x-auto">
              <code>{codeContent.join("\n")}</code>
            </pre>
          </div>
        )
        codeContent = []
        inCodeBlock = false
      } else {
        inCodeBlock = true
        codeLanguage = line.slice(3)
      }
      continue
    }

    if (inCodeBlock) {
      codeContent.push(line)
      continue
    }

    // Tables
    if (line.startsWith("|")) {
      if (!inTable) {
        inTable = true
        tableRows = []
      }
      const cells = line.split("|").filter((c) => c.trim() !== "")
      if (!line.includes("---")) {
        tableRows.push(cells.map((c) => c.trim()))
      }
      continue
    } else if (inTable) {
      elements.push(
        <div key={i} className="my-4 rounded-xl overflow-hidden border border-stone-200">
          <table className="w-full">
            <thead>
              <tr className="bg-stone-50">
                {tableRows[0]?.map((cell, j) => (
                  <th key={j} className="px-4 py-3 text-left text-xs font-semibold text-stone-600 border-b border-stone-200">
                    {cell}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.slice(1).map((row, j) => (
                <tr key={j} className="border-b border-stone-100 last:border-0">
                  {row.map((cell, k) => (
                    <td key={k} className="px-4 py-3 text-sm">
                      {cell.startsWith("`") && cell.endsWith("`") ? (
                        <code className="bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded text-xs font-mono">
                          {cell.slice(1, -1)}
                        </code>
                      ) : (
                        <span className="text-stone-600">{cell}</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
      inTable = false
      tableRows = []
    }

    // Headers
    if (line.startsWith("# ")) {
      elements.push(
        <h1 key={i} className="text-3xl font-bold text-stone-900 mt-8 mb-4 flex items-center gap-3">
          {line.slice(2)}
        </h1>
      )
      continue
    }
    if (line.startsWith("## ")) {
      elements.push(
        <h2 key={i} id={line.slice(3).toLowerCase().replace(/\s+/g, "-")} className="text-xl font-semibold text-stone-800 mt-8 mb-3 pb-2 border-b border-stone-200 scroll-mt-4">
          {line.slice(3)}
        </h2>
      )
      continue
    }
    if (line.startsWith("### ")) {
      elements.push(
        <h3 key={i} className="text-lg font-medium text-stone-700 mt-6 mb-2">
          {line.slice(4)}
        </h3>
      )
      continue
    }
    if (line.startsWith("#### ")) {
      elements.push(
        <h4 key={i} className="text-base font-medium text-stone-700 mt-5 mb-2 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-400" />
          {line.slice(5)}
        </h4>
      )
      continue
    }

    // Lists
    if (line.startsWith("- ")) {
      const content = line.slice(2)
      const boldMatch = content.match(/\*\*(.+?)\*\*(.*)/)
      elements.push(
        <li key={i} className="text-stone-600 ml-4 my-1.5 flex items-start gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-stone-400 mt-2 flex-shrink-0" />
          <span>
            {boldMatch ? (
              <>
                <strong className="text-stone-800 font-medium">{boldMatch[1]}</strong>
                <span className="text-stone-500">{boldMatch[2]}</span>
              </>
            ) : (
              content
            )}
          </span>
        </li>
      )
      continue
    }

    // Numbered lists
    const numberedMatch = line.match(/^(\d+)\. (.+)$/)
    if (numberedMatch) {
      elements.push(
        <li key={i} className="text-stone-600 ml-4 my-1.5 flex items-start gap-3">
          <span className="w-6 h-6 rounded-full bg-stone-100 flex items-center justify-center text-xs font-medium text-stone-500 flex-shrink-0">
            {numberedMatch[1]}
          </span>
          <span className="pt-0.5">{numberedMatch[2]}</span>
        </li>
      )
      continue
    }

    // Empty lines
    if (line.trim() === "") {
      continue
    }

    // Paragraphs with inline code
    const formattedLine = line.replace(
      /`([^`]+)`/g,
      '<code class="bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded text-sm font-mono">$1</code>'
    )
    elements.push(
      <p
        key={i}
        className="text-stone-600 my-3 leading-relaxed"
        dangerouslySetInnerHTML={{ __html: formattedLine }}
      />
    )
  }

  return <div className="space-y-1">{elements}</div>
}
