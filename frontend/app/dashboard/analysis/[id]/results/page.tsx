"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Switch } from "@/components/ui/switch"
import {
  Code2,
  ArrowLeft,
  FileCode,
  FolderOpen,
  ChevronRight,
  Download,
  Copy,
  Check,
  FileText,
  Book,
  BarChart3,
} from "lucide-react"
import { useAnalysis, type AnalysisRecord } from "@/lib/analysis-context"

const fileTree = [
  {
    name: "api",
    type: "folder",
    children: [
      { name: "gateway.py", type: "file", documented: true },
      { name: "routes.py", type: "file", documented: true },
      { name: "middleware.py", type: "file", documented: true },
    ],
  },
  {
    name: "auth",
    type: "folder",
    children: [
      { name: "handler.py", type: "file", documented: true },
      { name: "token.py", type: "file", documented: true },
      { name: "utils.py", type: "file", documented: false },
    ],
  },
  {
    name: "utils",
    type: "folder",
    children: [
      { name: "validation.py", type: "file", documented: true },
      { name: "helpers.py", type: "file", documented: true },
    ],
  },
  { name: "config.py", type: "file", documented: true },
  { name: "main.py", type: "file", documented: true },
]

const codeExamples = {
  before: `def authenticate_user(username, password, remember_me=False):
    user = db.query(User).filter_by(username=username).first()
    if user and verify_password(password, user.password_hash):
        token = create_token(user.id, remember_me)
        user.last_login = datetime.now()
        db.commit()
        log_auth_attempt(username, True)
        return token
    log_auth_attempt(username, False)
    return None`,
  after: `def authenticate_user(username, password, remember_me=False):
    """Authenticate a user and return an authentication token.

    This function validates the provided credentials against the database,
    implementing secure password verification using bcrypt. Upon successful
    authentication, it generates a JWT token for subsequent API requests.

    Args:
        username: The user's unique identifier (email or username).
        password: The plaintext password to verify.
        remember_me: If True, extends token expiration to 30 days.
            Defaults to False.

    Returns:
        AuthToken: A valid authentication token if credentials are correct.
        None: If authentication fails due to invalid credentials.

    Raises:
        DatabaseConnectionError: If unable to connect to the user database.
        RateLimitExceeded: If too many authentication attempts from this IP.

    Example:
        >>> token = authenticate_user("john@example.com", "secret123")
        >>> if token:
        ...     print(f"Authenticated: {token.user_id}")
    """
    user = db.query(User).filter_by(username=username).first()
    if user and verify_password(password, user.password_hash):
        token = create_token(user.id, remember_me)
        user.last_login = datetime.now()
        db.commit()
        log_auth_attempt(username, True)
        return token
    log_auth_attempt(username, False)
    return None`,
}

const readmeContent = `# API Gateway

A high-performance API gateway service built with Python and FastAPI.

## Overview

This service provides a centralized entry point for all API requests, handling:
- Request routing and load balancing
- Authentication and authorization
- Rate limiting and throttling
- Request/response transformation
- Logging and monitoring

## Installation

\`\`\`bash
pip install -r requirements.txt
python main.py
\`\`\`

## Configuration

Configuration is managed through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| \`API_PORT\` | Server port | 8000 |
| \`DB_URL\` | Database connection string | - |
| \`JWT_SECRET\` | Secret key for JWT tokens | - |

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

## License

MIT License
`

export default function ResultsPage() {
  const params = useParams()
  const analysisId = params.id as string
  const { getAnalysis } = useAnalysis()
  const analysis = getAnalysis(analysisId)

  const [selectedFile, setSelectedFile] = useState("")
  const [showBefore, setShowBefore] = useState(false)
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState<"code" | "readme" | "metrics">("code")

  // Build real file tree from analysis components
  const realFileTree = analysis?.components ? buildFileTree(analysis.components) : fileTree
  const repoName = analysis?.repoName || "api-gateway"
  const analysisStatus = analysis?.status || "completed"

  // Build code examples from real components
  const realCodeExamples = analysis?.components ? buildCodeExamples(analysis.components, selectedFile) : codeExamples

  // Set default selected file
  useEffect(() => {
    if (analysis?.components) {
      const firstFile = Object.values(analysis.components)[0]?.file_path
      if (firstFile && !selectedFile) {
        setSelectedFile(firstFile)
      }
    } else if (!selectedFile) {
      setSelectedFile("auth/handler.py")
    }
  }, [analysis, selectedFile])

  const handleCopy = () => {
    navigator.clipboard.writeText(showBefore ? realCodeExamples.before : realCodeExamples.after)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleExportAll = () => {
    if (!analysis?.components) return
    const blob = new Blob([JSON.stringify(analysis.components, null, 2)], {
      type: "application/json",
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${repoName}-analysis-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                <Code2 className="w-5 h-5 text-primary-foreground" />
              </div>
              <div>
                <span className="text-lg font-semibold text-foreground">{repoName}</span>
                <Badge className="ml-2 bg-chart-3 text-card">{analysisStatus === "completed" ? "Completed" : analysisStatus}</Badge>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link href={`/dashboard/analysis/${analysisId}/agents`}>
              <Button variant="outline" size="sm" className="border-border bg-transparent">
                View Agent Reasoning
              </Button>
            </Link>
            <Button className="bg-foreground text-background hover:bg-foreground/90" onClick={handleExportAll}>
              <Download className="w-4 h-4 mr-2" />
              Export All
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
          <TabsList className="mb-6 bg-secondary">
            <TabsTrigger value="code" className="flex items-center gap-2">
              <FileCode className="w-4 h-4" />
              Documentation
            </TabsTrigger>
            <TabsTrigger value="readme" className="flex items-center gap-2">
              <Book className="w-4 h-4" />
              README
            </TabsTrigger>
            <TabsTrigger value="metrics" className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Evaluation
            </TabsTrigger>
          </TabsList>

          <TabsContent value="code">
            <div className="grid lg:grid-cols-4 gap-6">
              {/* File Tree */}
              <Card className="border-border lg:col-span-1">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <FolderOpen className="w-4 h-4" />
                    File Explorer
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <ScrollArea className="h-[500px]">
                    <div className="p-4 space-y-1">
                      {realFileTree.map((item: any) => (
                        <FileTreeItem
                          key={item.name}
                          item={item}
                          selectedFile={selectedFile}
                          onSelect={setSelectedFile}
                        />
                      ))}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>

              {/* Code View */}
              <Card className="border-border lg:col-span-3">
                <CardHeader className="pb-3 flex flex-row items-center justify-between">
                  <div className="flex items-center gap-3">
                    <CardTitle className="text-sm font-mono">{selectedFile}</CardTitle>
                    <Badge variant="outline" className="border-chart-3 text-chart-3">
                      Documented
                    </Badge>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">Show original</span>
                      <Switch checked={showBefore} onCheckedChange={setShowBefore} />
                    </div>
                    <Button variant="outline" size="sm" className="border-border bg-transparent" onClick={handleCopy}>
                      {copied ? (
                        <>
                          <Check className="w-4 h-4 mr-2" />
                          Copied
                        </>
                      ) : (
                        <>
                          <Copy className="w-4 h-4 mr-2" />
                          Copy
                        </>
                      )}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="relative">
                    <pre className="bg-foreground text-background p-6 rounded-lg text-sm overflow-x-auto font-mono leading-relaxed">
                      <code>{showBefore ? realCodeExamples.before : realCodeExamples.after}</code>
                    </pre>
                    {!showBefore && (
                      <div className="absolute top-4 right-4">
                        <Badge className="bg-chart-3 text-card">AI Generated</Badge>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="readme">
            <Card className="border-border">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  <FileText className="w-5 h-5" />
                  Generated README.md
                </CardTitle>
                <Button variant="outline" size="sm" className="border-border bg-transparent">
                  <Download className="w-4 h-4 mr-2" />
                  Download
                </Button>
              </CardHeader>
              <CardContent>
                <div className="prose prose-sm max-w-none bg-card p-6 rounded-lg border border-border">
                  <pre className="whitespace-pre-wrap font-mono text-sm text-foreground">{readmeContent}</pre>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="metrics">
            <EvaluationDashboard />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}

function FileTreeItem({
  item,
  selectedFile,
  onSelect,
  depth = 0,
}: {
  item: any
  selectedFile: string
  onSelect: (file: string) => void
  depth?: number
}) {
  const [expanded, setExpanded] = useState(true)
  const isFolder = item.type === "folder"
  const fullPath = item.name

  return (
    <div style={{ paddingLeft: `${depth * 12}px` }}>
      <button
        type="button"
        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors ${
          selectedFile === fullPath
            ? "bg-primary/10 text-foreground"
            : "text-muted-foreground hover:bg-secondary hover:text-foreground"
        }`}
        onClick={() => {
          if (isFolder) {
            setExpanded(!expanded)
          } else {
            onSelect(fullPath)
          }
        }}
      >
        {isFolder ? (
          <>
            <ChevronRight className={`w-4 h-4 transition-transform ${expanded ? "rotate-90" : ""}`} />
            <FolderOpen className="w-4 h-4" />
          </>
        ) : (
          <>
            <span className="w-4" />
            <FileCode className="w-4 h-4" />
          </>
        )}
        <span className="flex-1 text-left">{item.name}</span>
        {!isFolder && item.documented && (
          <div className="w-2 h-2 rounded-full bg-chart-3" />
        )}
      </button>
      {isFolder && expanded && item.children && (
        <div>
          {item.children.map((child: any) => (
            <FileTreeItem
              key={child.name}
              item={child}
              selectedFile={selectedFile}
              onSelect={onSelect}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function EvaluationDashboard() {
  const metrics = [
    { name: "Completeness", score: 94, description: "Coverage of all functions and classes" },
    { name: "Helpfulness", score: 91, description: "Quality and usefulness of descriptions" },
    { name: "Consistency", score: 96, description: "Uniform style across documentation" },
    { name: "Accuracy", score: 89, description: "Correctness of parameter/return documentation" },
  ]

  const overallScore = Math.round(metrics.reduce((acc, m) => acc + m.score, 0) / metrics.length)

  return (
    <div className="space-y-6">
      {/* Overall Score */}
      <Card className="border-border">
        <CardContent className="p-8">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-foreground">Documentation Quality Score</h2>
              <p className="text-muted-foreground mt-1">Based on completeness, helpfulness, consistency, and accuracy</p>
            </div>
            <div className="text-right">
              <div className="text-6xl font-bold text-primary">{overallScore}</div>
              <p className="text-muted-foreground">out of 100</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Metric Cards */}
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((metric) => (
          <Card key={metric.name} className="border-border">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <span className="font-medium text-foreground">{metric.name}</span>
                <span className="text-2xl font-bold text-foreground">{metric.score}%</span>
              </div>
              <div className="h-2 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all"
                  style={{ width: `${metric.score}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground mt-3">{metric.description}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Detailed Stats */}
      <div className="grid md:grid-cols-2 gap-6">
        <Card className="border-border">
          <CardHeader>
            <CardTitle className="text-lg">Coverage Statistics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {[
              { label: "Functions Documented", value: "234 / 234", percentage: 100 },
              { label: "Classes Documented", value: "45 / 45", percentage: 100 },
              { label: "Modules with README", value: "12 / 12", percentage: 100 },
              { label: "Parameters Described", value: "512 / 534", percentage: 96 },
            ].map((stat) => (
              <div key={stat.label} className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">{stat.label}</span>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-foreground">{stat.value}</span>
                  <Badge variant="outline" className="border-chart-3 text-chart-3">
                    {stat.percentage}%
                  </Badge>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardHeader>
            <CardTitle className="text-lg">Verification Results</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {[
              { label: "Passed Verification", value: 222, color: "bg-chart-3" },
              { label: "Auto-fixed Issues", value: 10, color: "bg-chart-1" },
              { label: "Manual Review Needed", value: 2, color: "bg-chart-4" },
              { label: "Failed Checks", value: 0, color: "bg-destructive" },
            ].map((stat) => (
              <div key={stat.label} className="flex items-center justify-between p-3 bg-secondary rounded-lg">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${stat.color}`} />
                  <span className="text-sm text-foreground">{stat.label}</span>
                </div>
                <span className="text-lg font-bold text-foreground">{stat.value}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Export Options */}
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="text-lg">Export Options</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-4 gap-4">
            {[
              { label: "Documentation Bundle", format: "ZIP", icon: FileCode },
              { label: "Evaluation Report", format: "PDF", icon: BarChart3 },
              { label: "README Files", format: "MD", icon: FileText },
              { label: "Full Export", format: "ZIP", icon: Download },
            ].map((option) => (
              <Button key={option.label} variant="outline" className="h-auto py-4 px-4 flex flex-col items-center gap-2 border-border bg-transparent">
                <option.icon className="w-6 h-6 text-muted-foreground" />
                <span className="font-medium text-foreground">{option.label}</span>
                <Badge variant="outline" className="border-border">{option.format}</Badge>
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
// ── Helpers to build real data from analysis components ──────────────

function buildFileTree(components: Record<string, any>): any[] {
  const tree: Record<string, any> = {}
  
  for (const comp of Object.values(components)) {
    const filePath = comp.file_path || ""
    const parts = filePath.replace(/\\/g, "/").split("/").filter(Boolean)
    
    let current = tree
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      if (i === parts.length - 1) {
        // File
        if (!current[part]) {
          current[part] = {
            name: part,
            type: "file",
            documented: comp.has_docstring,
            fullPath: filePath,
          }
        }
      } else {
        // Folder
        if (!current[part]) {
          current[part] = {
            name: part,
            type: "folder",
            children: {},
          }
        }
        current = current[part].children || {}
      }
    }
  }
  
  function toArray(obj: Record<string, any>): any[] {
    return Object.values(obj).map((item: any) => {
      if (item.type === "folder" && item.children) {
        return { ...item, children: toArray(item.children) }
      }
      return item
    }).sort((a: any, b: any) => {
      if (a.type === "folder" && b.type !== "folder") return -1
      if (a.type !== "folder" && b.type === "folder") return 1
      return a.name.localeCompare(b.name)
    })
  }
  
  return toArray(tree)
}

function buildCodeExamples(components: Record<string, any>, selectedFile: string): { before: string; after: string } {
  const matchingComps = Object.values(components).filter(
    (c: any) => c.file_path === selectedFile || c.file_path?.endsWith(selectedFile)
  )
  
  if (matchingComps.length === 0) {
    const first = Object.values(components)[0]
    return {
      before: first?.source_code || "// No source code available",
      after: first?.docstring ? `${first.docstring}\n\n${first.source_code || ""}` : first?.source_code || "// No source code available",
    }
  }
  
  const code = matchingComps.map((c: any) => c.source_code || "").join("\n\n")
  const documented = matchingComps.map((c: any) => {
    if (c.docstring) {
      return `${c.docstring}\n\n${c.source_code || ""}`
    }
    return c.source_code || ""
  }).join("\n\n")
  
  return { before: code, after: documented }
}