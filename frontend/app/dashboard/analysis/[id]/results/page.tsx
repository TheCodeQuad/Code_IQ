"use client"

import { useState, useEffect, useCallback } from "react"
import Link from "next/link"
import Image from "next/image"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
  Loader2,
  AlertCircle,
  Eye,
  EyeOff,
} from "lucide-react"

// ── Types ────────────────────────────────────────────────────────────

interface TreeNode {
  name: string
  type: "file" | "folder"
  path: string
  size?: number
  children?: TreeNode[]
}

interface RepoDetail {
  id: string
  repo_name: string
  repo_url?: string
  language?: string
  file_count: number
  total_lines: number
  status: string
  stats?: Record<string, any>
  evaluation?: {
    accuracy?: number
    completeness?: number
    clarity?: number
    consistency?: number
    overall_score?: number
  }
}

// ── Helper Functions ────────────────────────────────────────────────

function stripDocstrings(content: string, language: string): string {
  const lines = content.split("\n")
  const result: string[] = []
  let inBlockComment = false

  for (const line of lines) {
    const trimmed = line.trim()

    // If we're already in a block comment, look for the end
    if (inBlockComment) {
      if (trimmed.includes("*/") || trimmed.includes('"""') || trimmed.includes("'''")) {
        inBlockComment = false
      }
      continue // Skip all lines inside block comment
    }

    // Check for single-line comments
    if (trimmed.startsWith("//") || trimmed.startsWith("#")) {
      continue // Skip single-line comments
    }

    // Check for block comment start - JavaScript/TypeScript
    if (trimmed.startsWith("/*") || trimmed.startsWith("/**")) {
      if (trimmed.includes("*/")) {
        // Single-line block comment, skip it
        continue
      } else {
        // Multi-line block comment starts
        inBlockComment = true
        continue
      }
    }

    // Check for docstring start - Python
    if (language === "python" && (trimmed.startsWith('"""') || trimmed.startsWith("'''"))) {
      const quote = trimmed.startsWith('"""') ? '"""' : "'''"
      // Count occurrences of the quote
      const firstIndex = trimmed.indexOf(quote)
      const lastIndex = trimmed.lastIndexOf(quote)
      
      if (firstIndex !== lastIndex) {
        // Opens and closes on same line, skip it
        continue
      } else {
        // Multi-line docstring starts
        inBlockComment = true
        continue
      }
    }

    // Keep this line if not in a comment block
    result.push(line)
  }

  return result.join("\n")
}

// ── Page ─────────────────────────────────────────────────────────────

export default function ResultsPage() {
  const params = useParams()
  const repoId = params.id as string

  const [repo, setRepo] = useState<RepoDetail | null>(null)
  const [tree, setTree] = useState<TreeNode[]>([])
  const [selectedFile, setSelectedFile] = useState("")
  const [fileContent, setFileContent] = useState("")
  const [originalContent, setOriginalContent] = useState("")
  const [showOriginal, setShowOriginal] = useState(false)
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState<"code" | "readme" | "metrics">("code")
  const [loading, setLoading] = useState(true)
  const [treeLoading, setTreeLoading] = useState(true)
  const [fileLoading, setFileLoading] = useState(false)
  const [error, setError] = useState("")

  // Fetch repo details
  useEffect(() => {
    async function fetchRepo() {
      try {
        const res = await fetch(`/api/repos/${repoId}`)
        if (!res.ok) throw new Error("Failed to load repository")
        const data = await res.json()
        setRepo(data)
      } catch (err: any) {
        setError(err.message || "Failed to load repository")
      } finally {
        setLoading(false)
      }
    }
    fetchRepo()
  }, [repoId])

  // Fetch file tree
  useEffect(() => {
    async function fetchTree() {
      try {
        const res = await fetch(`/api/repos/${repoId}/tree`)
        if (!res.ok) throw new Error("Failed to load file tree")
        const data = await res.json()
        setTree(data.tree || [])

        // Auto-select first file
        const first = findFirstFile(data.tree || [])
        if (first) {
          setSelectedFile(first.path)
        }
      } catch {
        // tree loading failed, leave empty
      } finally {
        setTreeLoading(false)
      }
    }
    fetchTree()
  }, [repoId])

  // Fetch file content when selection changes
  const fetchFileContent = useCallback(
    async (filePath: string) => {
      if (!filePath) return
      setFileLoading(true)
      try {
        // Get original file from disk
        const originalRes = await fetch(
          `/api/repos/${repoId}/file?path=${encodeURIComponent(filePath)}&documented=false`
        )
        if (!originalRes.ok) throw new Error("Failed to load file")
        const originalData = await originalRes.json()
        
        // Detect language from file extension
        const lang = filePath.split(".").pop()?.toLowerCase() || "text"
        
        // Original is the raw file with docstrings STRIPPED
        const originalWithoutDocs = stripDocstrings(originalData.content || "", lang)
        setOriginalContent(originalWithoutDocs)
        
        // Documented version is the full file with all docstrings
        setFileContent(originalData.content || "")
        
        setShowOriginal(false) // Default to showing documented version
      } catch {
        setFileContent("// Could not load file contents")
        setOriginalContent("")
      } finally {
        setFileLoading(false)
      }
    },
    [repoId]
  )

  useEffect(() => {
    if (selectedFile) {
      fetchFileContent(selectedFile)
    }
  }, [selectedFile, fetchFileContent])

  const handleCopy = () => {
    navigator.clipboard.writeText(fileContent)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleExport = () => {
    const blob = new Blob([fileContent], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = selectedFile.split("/").pop() || "file.txt"
    a.click()
    URL.revokeObjectURL(url)
  }

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading analysis results...</p>
        </div>
      </div>
    )
  }

  // Error state
  if (error || !repo) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-6">
        <Card className="border-border max-w-md">
          <CardContent className="p-8 text-center">
            <AlertCircle className="w-12 h-12 text-destructive mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-foreground mb-2">
              {error || "Repository Not Found"}
            </h2>
            <p className="text-muted-foreground mb-6">
              The requested repository could not be found.
            </p>
            <Link href="/dashboard">
              <Button>
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Dashboard
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
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
                <span className="text-lg font-semibold text-foreground">
                  {repo.repo_name}
                </span>
                <Badge className="ml-2 bg-chart-3 text-card">
                  {repo.status === "completed" ? "Completed" : repo.status}
                </Badge>
                {repo.language && (
                  <Badge variant="outline" className="ml-2">
                    {repo.language}
                  </Badge>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link href={`/dashboard/analysis/${repoId}/agents`}>
              <Button variant="outline" size="sm" className="border-border bg-transparent">
                View Agent Reasoning
              </Button>
            </Link>
            <Button
              className="bg-foreground text-background hover:bg-foreground/90"
              onClick={handleExport}
              disabled={!fileContent}
            >
              <Download className="w-4 h-4 mr-2" />
              Export File
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
          <TabsList className="mb-6 bg-secondary">
            <TabsTrigger value="code" className="flex items-center gap-2">
              <Image src="/COEIQ.png" alt="CodeIQ" width={16} height={16} />
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

          {/* ── Documentation Tab ── */}
          <TabsContent value="code">
            {treeLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
              </div>
            ) : tree.length === 0 ? (
              <Card className="border-border">
                <CardContent className="p-12 text-center">
                  <FolderOpen className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">
                    No files found in this repository
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid lg:grid-cols-4 gap-6">
                {/* File Tree */}
                <Card className="border-border lg:col-span-1">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <FolderOpen className="w-4 h-4" />
                      File Explorer
                      <Badge variant="outline" className="ml-auto text-xs">
                        {countFiles(tree)} files
                      </Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    <ScrollArea className="h-[600px]">
                      <div className="p-4 space-y-1">
                        {tree.map((item) => (
                          <FileTreeItem
                            key={item.path}
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
                      <CardTitle className="text-sm font-mono truncate max-w-md" title={selectedFile}>
                        {selectedFile || "No file selected"}
                      </CardTitle>
                    </div>
                    <div className="flex items-center gap-2">
                      {originalContent && (
                        <Button
                          variant={showOriginal ? "default" : "outline"}
                          size="sm"
                          className={showOriginal ? "bg-amber-600 hover:bg-amber-700" : "border-border bg-transparent"}
                          onClick={() => setShowOriginal(!showOriginal)}
                        >
                          {showOriginal ? (
                            <>
                              <Eye className="w-4 h-4 mr-2" />
                              Viewing Original
                            </>
                          ) : (
                            <>
                              <Eye className="w-4 h-4 mr-2" />
                              See Original
                            </>
                          )}
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-border bg-transparent"
                        onClick={handleCopy}
                        disabled={!fileContent && !originalContent}
                      >
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
                    {fileLoading ? (
                      <div className="flex items-center justify-center py-24">
                        <Loader2 className="w-6 h-6 animate-spin text-primary" />
                      </div>
                    ) : (
                      <ScrollArea className="h-[600px]">
                        <CodeViewer
                          content={showOriginal ? originalContent : fileContent}
                          isOriginal={showOriginal}
                          language={selectedFile.split(".").pop()?.toLowerCase() || "text"}
                          showOriginal={showOriginal}
                        />
                      </ScrollArea>
                    )}
                  </CardContent>
                </Card>
              </div>
            )}
          </TabsContent>

          {/* ── README Tab ── */}
          <TabsContent value="readme">
            <Card className="border-border">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  <FileText className="w-5 h-5" />
                  Generated README.md
                </CardTitle>
                <Button variant="outline" size="sm" className="border-border bg-transparent" disabled>
                  <Download className="w-4 h-4 mr-2" />
                  Download
                </Button>
              </CardHeader>
              <CardContent>
                <div className="bg-secondary/50 p-12 rounded-lg border border-border text-center">
                  <Book className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">README generation coming soon...</p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Evaluation Tab ── */}
          <TabsContent value="metrics">
            <EvaluationDashboard repo={repo} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}

// ── File Tree Item ───────────────────────────────────────────────────

function FileTreeItem({
  item,
  selectedFile,
  onSelect,
  depth = 0,
}: {
  item: TreeNode
  selectedFile: string
  onSelect: (path: string) => void
  depth?: number
}) {
  const [expanded, setExpanded] = useState(depth < 2)
  const isFolder = item.type === "folder"
  const isSelected = selectedFile === item.path

  return (
    <div style={{ paddingLeft: `${depth * 12}px` }}>
      <button
        type="button"
        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors ${
          isSelected
            ? "bg-primary/10 text-foreground font-medium"
            : "text-muted-foreground hover:bg-secondary hover:text-foreground"
        }`}
        onClick={() => {
          if (isFolder) {
            setExpanded(!expanded)
          } else {
            onSelect(item.path)
          }
        }}
      >
        {isFolder ? (
          <>
            <ChevronRight
              className={`w-4 h-4 transition-transform ${expanded ? "rotate-90" : ""}`}
            />
            <FolderOpen className="w-4 h-4 text-blue-500" />
          </>
        ) : (
          <>
            <span className="w-4" />
            <FileCode className="w-4 h-4 text-purple-500" />
          </>
        )}
        <span className="flex-1 text-left truncate" title={item.name}>
          {item.name}
        </span>
      </button>
      {isFolder && expanded && item.children && item.children.length > 0 && (
        <div className="mt-0.5">
          {item.children.map((child) => (
            <FileTreeItem
              key={child.path}
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

// ── Evaluation Dashboard ─────────────────────────────────────────────

function EvaluationDashboard({ repo }: { repo: RepoDetail }) {
  const evaluation = repo.evaluation
  const stats = repo.stats

  const metrics = [
    {
      name: "Completeness",
      score: evaluation?.completeness != null ? Math.round(evaluation.completeness) : null,
      description: "Coverage of all functions and classes",
    },
    {
      name: "Helpfulness",
      score: evaluation?.clarity != null ? Math.round(evaluation.clarity) : null,
      description: "Quality and usefulness of descriptions",
    },
    {
      name: "Consistency",
      score: evaluation?.consistency != null ? Math.round(evaluation.consistency) : null,
      description: "Uniform style across documentation",
    },
    {
      name: "Accuracy",
      score: evaluation?.accuracy != null ? Math.round(evaluation.accuracy) : null,
      description: "Correctness of parameter/return documentation",
    },
  ]

  const scoredMetrics = metrics.filter((m) => m.score !== null)
  const overallScore =
    evaluation?.overall_score != null
      ? Math.round(evaluation.overall_score)
      : scoredMetrics.length > 0
        ? Math.round(scoredMetrics.reduce((a, m) => a + (m.score || 0), 0) / scoredMetrics.length)
        : null

  return (
    <div className="space-y-6">
      {/* Overall Score */}
      <Card className="border-border">
        <CardContent className="p-8">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-foreground">
                Documentation Quality Score
              </h2>
              <p className="text-muted-foreground mt-1">
                {repo.file_count} files &middot; {repo.total_lines.toLocaleString()} lines analysed
              </p>
            </div>
            <div className="text-right">
              <div className="text-6xl font-bold text-primary">
                {overallScore ?? "\u2014"}
              </div>
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
                <span className="text-2xl font-bold text-foreground">
                  {metric.score != null ? `${metric.score}%` : "\u2014"}
                </span>
              </div>
              <div className="h-2 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all"
                  style={{ width: `${metric.score ?? 0}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground mt-3">
                {metric.description}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Coverage Statistics */}
      <div className="grid md:grid-cols-2 gap-6">
        <Card className="border-border">
          <CardHeader>
            <CardTitle className="text-lg">Coverage Statistics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {[
              { label: "Total Files", value: `${repo.file_count}` },
              { label: "Total Lines", value: repo.total_lines.toLocaleString() },
              { label: "Language", value: repo.language || "Unknown" },
              { label: "Status", value: repo.status },
            ].map((stat) => (
              <div key={stat.label} className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">{stat.label}</span>
                <span className="text-sm font-medium text-foreground">{stat.value}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardHeader>
            <CardTitle className="text-lg">Export Options</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: "Documentation Bundle", format: "ZIP", icon: FileCode },
                { label: "Evaluation Report", format: "PDF", icon: BarChart3 },
                { label: "README Files", format: "MD", icon: FileText },
                { label: "Full Export", format: "ZIP", icon: Download },
              ].map((option) => (
                <Button
                  key={option.label}
                  variant="outline"
                  className="h-auto py-4 px-4 flex flex-col items-center gap-2 border-border bg-transparent"
                >
                  <option.icon className="w-6 h-6 text-muted-foreground" />
                  <span className="font-medium text-foreground text-xs">
                    {option.label}
                  </span>
                  <Badge variant="outline" className="border-border">
                    {option.format}
                  </Badge>
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// ── Code Viewer Component ────────────────────────────────────────────

function CodeViewer({
  content,
  isOriginal,
  language,
  showOriginal,
}: {
  content: string
  isOriginal: boolean
  language: string
  showOriginal: boolean
}) {
  const lines = content.split("\n")

  // Python/JavaScript keywords for syntax highlighting
  const keywords = {
    python: ["def", "class", "if", "else", "elif", "for", "while", "return", "import", "from", "try", "except", "finally", "with", "as", "async", "await", "yield", "lambda", "pass", "break", "continue", "raise", "assert", "del", "global", "nonlocal", "is", "in", "not", "and", "or"],
    javascript: ["function", "const", "let", "var", "if", "else", "for", "while", "return", "import", "export", "class", "extends", "try", "catch", "finally", "async", "await", "yield", "new", "this", "super", "static", "throw", "break", "continue", "switch", "case", "default", "typeof", "instanceof", "delete", "void", "in", "of"],
  }

  const currentKeywords = language === "python" ? keywords.python : keywords.javascript

  const isDocstring = (line: string): boolean => {
    const trimmed = line.trim()
    return (
      trimmed.startsWith('"""') ||
      trimmed.startsWith("'''") ||
      trimmed.startsWith("/**") ||
      trimmed.startsWith("*")
    )
  }

  const isComment = (line: string): boolean => {
    const trimmed = line.trim()
    return trimmed.startsWith("//") || trimmed.startsWith("#")
  }

  const isDoc = (line: string): boolean => isDocstring(line) || isComment(line)

  // Tokenize a line for syntax highlighting
  const highlightLine = (line: string, isDocLine: boolean) => {
    // Check if this line is part of a docstring - if so, render it all in yellow
    const isDocstringLine = line.trim().startsWith("*") || line.trim().startsWith("/**") || line.trim().startsWith('"""') || line.trim().startsWith("'''")

    if (isDocstringLine) {
      return <span className="text-yellow-400">{line || "\u00A0"}</span>
    }

    const parts: React.ReactNode[] = []
    let lastIndex = 0

    // Match strings, comments, keywords, function calls, and identifiers
    const regex = /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`|\/\/.*|#.*|\/\*\*?.*?\*?\/?|\b\w+\b|\d+(?:\.\d+)?|[+\-*/%=<>!&|^~()[\]{}.,;:])/g
    let match

    while ((match = regex.exec(line)) !== null) {
      const token = match[0]
      const index = match.index

      // Add text before token
      if (index > lastIndex) {
        parts.push(
          <span key={`text-${lastIndex}`}>
            {line.substring(lastIndex, index)}
          </span>
        )
      }

      let color = ""

      // String literals
      if (token.startsWith('"') || token.startsWith("'") || token.startsWith("`")) {
        color = "text-orange-400"
      }
      // Comments
      else if (token.startsWith("//") || token.startsWith("#") || token.startsWith("/*") || token.startsWith("*")) {
        color = "text-green-400"
      }
      // Keywords
      else if (currentKeywords.includes(token.toLowerCase())) {
        color = "text-purple-400"
      }
      // Numbers
      else if (/^\d+(?:\.\d+)?$/.test(token)) {
        color = "text-yellow-400"
      }
      // Function calls (identifier followed by space and parenthesis)
      else if (/^\w+$/.test(token)) {
        // Check if next non-whitespace char is (
        const afterToken = line.substring(index + token.length).match(/^\s*[({]/)
        if (afterToken && afterToken[0].includes("(")) {
          color = "text-blue-400"
        } else {
          color = "text-gray-100"
        }
      }
      // Operators and punctuation
      else if (/^[+\-*/%=<>!&|^~()[\]{}.,;:]/.test(token)) {
        color = "text-gray-300"
      }

      if (color) {
        parts.push(
          <span key={`token-${index}`} className={color}>
            {token}
          </span>
        )
      } else {
        parts.push(
          <span key={`token-${index}`}>
            {token}
          </span>
        )
      }

      lastIndex = index + token.length
    }

    // Add remaining text
    if (lastIndex < line.length) {
      parts.push(
        <span key={`text-end`}>
          {line.substring(lastIndex)}
        </span>
      )
    }

    return parts.length > 0 ? parts : <span>{line || "\u00A0"}</span>
  }

  return (
    <div className="bg-foreground text-background p-6 rounded-lg text-sm font-mono leading-relaxed overflow-x-auto">
      {lines.length === 0 ? (
        <span className="text-muted-foreground">// Select a file to view its contents</span>
      ) : (
        <div className="space-y-0">
          {lines.map((line, idx) => {
            const isDocLine = isDoc(line)
            return (
              <div
                key={idx}
                className={`px-4 py-1 flex items-start gap-4 ${
                  isDocLine && !isOriginal ? "bg-slate-900/40" : ""
                }`}
              >
                <span className="inline-block w-12 text-right text-muted-foreground select-none shrink-0">
                  {idx + 1}
                </span>
                <span
                  className={`flex-1 ${
                    isDocLine && !isOriginal ? "text-amber-300" : ""
                  }`}
                >
                  {highlightLine(line, isDocLine)}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────

function findFirstFile(nodes: TreeNode[]): TreeNode | null {
  for (const node of nodes) {
    if (node.type === "file") return node
    if (node.type === "folder" && node.children) {
      const found = findFirstFile(node.children)
      if (found) return found
    }
  }
  return null
}

function countFiles(nodes: TreeNode[]): number {
  let n = 0
  for (const node of nodes) {
    if (node.type === "file") n++
    else if (node.children) n += countFiles(node.children)
  }
  return n
}
