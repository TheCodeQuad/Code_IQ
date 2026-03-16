"use client"

import { useState, useEffect, useCallback } from "react"
import Link from "next/link"
import Image from "next/image"
import { useParams } from "next/navigation"
import { useAnalysis } from "@/lib/analysis-context"
import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  LineChart,
  Line,
  Legend,
} from "recharts"
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
  RefreshCw,
  Target,
  Zap,
  Shield,
  FileCheck,
  TrendingUp,
  XCircle,
  Loader,
  CheckCircle,
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
            <EvaluationDashboard repo={repo} repoId={repoId} />
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

// Summary metrics (mock fallback)
const mockSummaryMetrics = {
  overallScore: 92,
  completeness: 94,
  helpfulness: 91,
  truthfulness: 96,
}

// Bar chart data
const metricBreakdown = [
  { name: "Completeness", score: 94, fill: "var(--chart-1)" },
  { name: "Helpfulness", score: 91, fill: "var(--chart-2)" },
  { name: "Consistency", score: 96, fill: "var(--chart-3)" },
  { name: "Accuracy", score: 89, fill: "var(--chart-4)" },
]

// Radar chart data
const radarData = [
  { metric: "Readability", value: 92 },
  { metric: "Accuracy", value: 89 },
  { metric: "Coverage", value: 94 },
  { metric: "Style", value: 96 },
  { metric: "Examples", value: 78 },
  { metric: "Consistency", value: 96 },
]

// Verifier findings
const verifierFindings = [
  { type: "auto-fixed", count: 8, description: "Mismatches corrected automatically", color: "text-chart-3" },
  { type: "flagged", count: 3, description: "Missing parameter descriptions flagged", color: "text-chart-1" },
  { type: "suggestion", count: 5, description: "Style improvements suggested", color: "text-chart-2" },
  { type: "critical", count: 0, description: "Critical issues requiring manual review", color: "text-destructive" },
]

// History data
const historyData = [
  { run: "Run 1", date: "Jan 15", score: 78, completeness: 72 },
  { run: "Run 2", date: "Jan 18", score: 84, completeness: 81 },
  { run: "Run 3", date: "Jan 22", score: 88, completeness: 89 },
  { run: "Run 4", date: "Jan 25", score: 90, completeness: 92 },
  { run: "Run 5", date: "Jan 28", score: 92, completeness: 94 },
]

function EvaluationDashboard({ repo, repoId }: { repo: RepoDetail; repoId: string }) {
  const [isEvaluating, setIsEvaluating] = useState(false)
  const [evaluationStep, setEvaluationStep] = useState<"idle" | "completeness" | "helpfulness" | "truthfulness" | "complete">("idle")
  const [evaluationResults, setEvaluationResults] = useState<any>(null)
  const [evaluationError, setEvaluationError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<"overview" | "files" | "history">("overview")
  const { toast } = useToast()
  const { getAnalysis } = useAnalysis()
  const analysis = getAnalysis(repoId)

  const handleEvaluate = async () => {
    if (!repo.repo_name && !analysis?.repoName) {
      toast({
        title: "Error",
        description: "Repository name not found",
        variant: "destructive",
      })
      return
    }

    setIsEvaluating(true)
    setEvaluationError(null)
    setEvaluationStep("completeness")

    try {
      const repoName = repo.repo_name || analysis?.repoName
      console.log("🔍 Starting evaluation for:", repoName)

      const requestBody = { repo_name: repoName }
      console.log("📤 Sending request:", requestBody)

      const response = await fetch("http://localhost:8000/evaluate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      })

      console.log("📥 Response status:", response.status, response.statusText)

      if (!response.ok) {
        let errorMsg = `HTTP ${response.status}`
        try {
          const errorData = await response.json()
          errorMsg = errorData.detail || errorMsg
        } catch {
          const text = await response.text()
          errorMsg = text || errorMsg
        }
        throw new Error(errorMsg)
      }

      const data = await response.json()
      console.log("✅ Evaluation results:", data)

      // Simulate step progression for UX
      setEvaluationStep("helpfulness")
      await new Promise((r) => setTimeout(r, 500))

      setEvaluationStep("truthfulness")
      await new Promise((r) => setTimeout(r, 500))

      setEvaluationResults(data)
      setEvaluationStep("complete")

      toast({
        title: "Evaluation Complete",
        description: `Overall Score: ${Math.round(data.overall_quality_score * 100)}%`,
      })
    } catch (error: any) {
      const errorMsg = error.message || "An error occurred during evaluation"
      console.error("❌ Evaluation error:", error)
      setEvaluationError(errorMsg)

      toast({
        title: "Evaluation Failed",
        description: errorMsg,
        variant: "destructive",
      })
    } finally {
      setIsEvaluating(false)
      setTimeout(() => setEvaluationStep("idle"), 2000)
    }
  }

  const summaryMetrics = evaluationResults
    ? {
        overallScore: Math.round((evaluationResults.overall_quality_score || 0) * 100),
        completeness: Math.round((evaluationResults.completeness || 0) * 100),
        helpfulness: Math.round((evaluationResults.helpfulness || 0) * 100),
        truthfulness: Math.round((evaluationResults.truthfulness || 0) * 100),
      }
    : analysis?.stats
      ? {
          overallScore: Math.round(
            ((analysis.stats.components_with_docstrings || 0) / Math.max(analysis.stats.total_components || 1, 1)) * 100
          ),
          completeness: Math.round(
            ((analysis.stats.components_with_docstrings || 0) / Math.max(analysis.stats.total_components || 1, 1)) * 100
          ),
          helpfulness: 0,
          truthfulness: 0,
        }
      : mockSummaryMetrics

  const metricBreakdownData = evaluationResults
    ? [
        { name: "Completeness", score: Math.round((evaluationResults.completeness || 0) * 100), fill: "var(--chart-1)" },
        { name: "Helpfulness", score: Math.round((evaluationResults.helpfulness || 0) * 100), fill: "var(--chart-2)" },
        { name: "Truthfulness", score: Math.round((evaluationResults.truthfulness || 0) * 100), fill: "var(--chart-3)" },
        { name: "Overall", score: Math.round((evaluationResults.overall_quality_score || 0) * 100), fill: "var(--chart-4)" },
      ]
    : metricBreakdown

  const fileMetrics = analysis?.components
    ? (() => {
        const fileMap = new Map<string, { lang: string; total: number; documented: number }>()
        for (const comp of Object.values(analysis.components!)) {
          const entry = fileMap.get(comp.file_path) || { lang: comp.language, total: 0, documented: 0 }
          entry.total++
          if (comp.has_docstring) entry.documented++
          fileMap.set(comp.file_path, entry)
        }
        return Array.from(fileMap.entries()).map(([file, data]) => ({
          file,
          lang: data.lang.charAt(0).toUpperCase() + data.lang.slice(1),
          completeness: Math.round((data.documented / data.total) * 100),
          verifier: (data.documented === data.total ? "passed" : data.documented > 0 ? "warning" : "pending") as const,
          issues: data.total - data.documented,
        }))
      })()
    : []

  const verifierStatusConfig = {
    passed: { icon: CheckCircle, color: "text-chart-3", bg: "bg-chart-3/10" },
    warning: { icon: AlertCircle, color: "text-chart-1", bg: "bg-chart-1/10" },
    pending: { icon: Loader2, color: "text-muted-foreground", bg: "bg-muted" },
    failed: { icon: XCircle, color: "text-destructive", bg: "bg-destructive/10" },
  }

  return (
    <div className="space-y-6">
      {/* Action Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-primary" />
          <h3 className="text-lg font-semibold text-foreground">Evaluation Dashboard</h3>
        </div>
        <div className="flex items-center gap-3">
          {isEvaluating && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader className="w-4 h-4 animate-spin" />
              <span>
                {evaluationStep === "completeness" && "Checking Completeness..."}
                {evaluationStep === "helpfulness" && "Evaluating Helpfulness..."}
                {evaluationStep === "truthfulness" && "Verifying Truthfulness..."}
                {evaluationStep === "complete" && "Complete!"}
              </span>
            </div>
          )}
          <Button
            variant="outline"
            size="sm"
            className="border-border bg-transparent"
            onClick={handleEvaluate}
            disabled={isEvaluating}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isEvaluating ? "animate-spin" : ""}`} />
            {isEvaluating ? "Evaluating..." : "Re-evaluate"}
          </Button>
        </div>
      </div>

      {/* Error Display */}
      {evaluationError && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <XCircle className="w-5 h-5 text-destructive mt-0.5" />
              <div className="flex-1">
                <h4 className="font-semibold text-destructive mb-1">Evaluation Error</h4>
                <p className="text-sm text-destructive/90 mb-3">{evaluationError}</p>
                <div className="bg-destructive/10 rounded p-3 text-xs text-destructive/80 space-y-1">
                  <p>
                    <strong>Troubleshooting:</strong>
                  </p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>
                      Check if backend is running:{" "}
                      <code className="bg-black/20 px-1 rounded">python -m uvicorn backend.app:app --reload</code>
                    </li>
                    <li>Verify backend is on http://localhost:8000</li>
                    <li>Check browser console (F12) for more details</li>
                    <li>Ensure repo has been analyzed first</li>
                  </ul>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* No Results Message */}
      {!evaluationResults && !isEvaluating && (
        <Card className="border-border/50 bg-secondary/30">
          <CardContent className="p-6 text-center">
            <BarChart3 className="w-12 h-12 text-muted-foreground mx-auto mb-3 opacity-50" />
            <h3 className="text-lg font-semibold text-foreground mb-2">No Evaluation Data Yet</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Click the "Re-evaluate" button above to run completeness, helpfulness, and truthfulness evaluations.
            </p>
            <Button onClick={handleEvaluate} disabled={isEvaluating}>
              <BarChart3 className="w-4 h-4 mr-2" />
              Run Evaluation Now
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="border-border">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <Target className="w-5 h-5 text-primary" />
              </div>
              <span className="text-sm text-muted-foreground">Overall Score</span>
            </div>
            <div className="flex items-end gap-2">
              <span className="text-4xl font-bold text-foreground">{summaryMetrics.overallScore}</span>
              <span className="text-muted-foreground mb-1">/100</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-lg bg-chart-1/10 flex items-center justify-center">
                <FileCheck className="w-5 h-5 text-chart-1" />
              </div>
              <span className="text-sm text-muted-foreground">Completeness</span>
            </div>
            <div className="flex items-end gap-2">
              <span className="text-4xl font-bold text-foreground">{summaryMetrics.completeness}%</span>
            </div>
            <Progress value={summaryMetrics.completeness} className="mt-3 h-2" />
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-lg bg-chart-2/10 flex items-center justify-center">
                <Zap className="w-5 h-5 text-chart-2" />
              </div>
              <span className="text-sm text-muted-foreground">Helpfulness</span>
            </div>
            <div className="flex items-end gap-2">
              <span className="text-4xl font-bold text-foreground">{summaryMetrics.helpfulness}%</span>
            </div>
            <Progress value={summaryMetrics.helpfulness} className="mt-3 h-2" />
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-lg bg-chart-3/10 flex items-center justify-center">
                <Shield className="w-5 h-5 text-chart-3" />
              </div>
              <span className="text-sm text-muted-foreground">Truthfulness</span>
            </div>
            <div className="flex items-end gap-2">
              <span className="text-4xl font-bold text-foreground">{summaryMetrics.truthfulness}%</span>
            </div>
            <Progress value={summaryMetrics.truthfulness} className="mt-3 h-2" />
          </CardContent>
        </Card>
      </div>

      {/* Detailed Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
        <TabsList className="mb-6 bg-secondary">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="files">File-level Metrics</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid lg:grid-cols-2 gap-6">
            {/* Bar Chart */}
            <Card className="border-border">
              <CardHeader>
                <CardTitle className="text-lg">Metric Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={metricBreakdownData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
                      <XAxis type="number" domain={[0, 100]} />
                      <YAxis type="category" dataKey="name" width={100} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "var(--card)",
                          border: "1px solid var(--border)",
                          borderRadius: "8px",
                        }}
                      />
                      <Bar dataKey="score" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Radar Chart */}
            <Card className="border-border">
              <CardHeader>
                <CardTitle className="text-lg">Quality Dimensions</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart data={radarData}>
                      <PolarGrid />
                      <PolarAngleAxis dataKey="metric" className="text-xs" />
                      <PolarRadiusAxis angle={30} domain={[0, 100]} />
                      <Radar
                        name="Score"
                        dataKey="value"
                        stroke="var(--primary)"
                        fill="var(--primary)"
                        fillOpacity={0.3}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "var(--card)",
                          border: "1px solid var(--border)",
                          borderRadius: "8px",
                        }}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Verifier Findings */}
            <Card className="border-border lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <CheckCircle className="w-5 h-5 text-chart-3" />
                  Verifier Findings
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-4 gap-4">
                  {verifierFindings.map((finding) => (
                    <div key={finding.type} className="p-4 bg-secondary/50 rounded-lg border border-border/50">
                      <div className="flex items-center justify-between mb-2">
                        <span className={`text-3xl font-bold ${finding.color}`}>{finding.count}</span>
                        <Badge variant="outline" className="capitalize border-border">
                          {finding.type}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">{finding.description}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="files">
          <Card className="border-border">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">File-level Metrics</CardTitle>
                <Badge variant="outline" className="border-border">
                  {fileMetrics.length} files
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              {fileMetrics.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <FileCode className="w-12 h-12 mx-auto mb-2 opacity-30" />
                  <p>No file metrics available. Run analysis first.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">File</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Language</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Completeness</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Verifier</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Issues</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fileMetrics.map((file) => {
                        const statusCfg = verifierStatusConfig[file.verifier as keyof typeof verifierStatusConfig]
                        const StatusIcon = statusCfg.icon
                        return (
                          <tr key={file.file} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2">
                                <FileCode className="w-4 h-4 text-muted-foreground" />
                                <span className="font-mono text-sm text-foreground">{file.file}</span>
                              </div>
                            </td>
                            <td className="py-3 px-4">
                              <Badge variant="outline" className="border-border">
                                {file.lang}
                              </Badge>
                            </td>
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-3">
                                <Progress value={file.completeness} className="w-24 h-2" />
                                <span className="text-sm text-foreground">{file.completeness}%</span>
                              </div>
                            </td>
                            <td className="py-3 px-4">
                              <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md ${statusCfg.bg}`}>
                                <StatusIcon className={`w-3.5 h-3.5 ${statusCfg.color}`} />
                                <span className={`text-xs font-medium capitalize ${statusCfg.color}`}>{file.verifier}</span>
                              </div>
                            </td>
                            <td className="py-3 px-4">
                              {file.issues > 0 ? (
                                <Badge className="bg-chart-1/10 text-chart-1 border border-chart-1/20">{file.issues} issues</Badge>
                              ) : (
                                <span className="text-sm text-muted-foreground">None</span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history">
          <div className="grid lg:grid-cols-3 gap-6">
            {/* Trend Chart */}
            <Card className="border-border lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-lg">Score Trend</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[350px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={historyData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis domain={[60, 100]} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "var(--card)",
                          border: "1px solid var(--border)",
                          borderRadius: "8px",
                        }}
                      />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="score"
                        name="Overall Score"
                        stroke="var(--primary)"
                        strokeWidth={2}
                        dot={{ fill: "var(--primary)" }}
                      />
                      <Line
                        type="monotone"
                        dataKey="completeness"
                        name="Completeness"
                        stroke="var(--chart-2)"
                        strokeWidth={2}
                        dot={{ fill: "var(--chart-2)" }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Run History */}
            <Card className="border-border">
              <CardHeader>
                <CardTitle className="text-lg">Run History</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {historyData
                  .slice()
                  .reverse()
                  .map((run, idx) => (
                    <div
                      key={run.run}
                      className={`p-3 rounded-lg border ${
                        idx === 0 ? "border-primary bg-primary/5" : "border-border/50 bg-secondary/30"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Loader2 className="w-4 h-4 text-muted-foreground" />
                          <span className="text-sm font-medium text-foreground">{run.run}</span>
                          {idx === 0 && <Badge className="bg-primary text-primary-foreground text-xs">Latest</Badge>}
                        </div>
                        <span className="text-xs text-muted-foreground">{run.date}</span>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-muted-foreground">Score:</span>
                          <span className="text-sm font-semibold text-foreground">{run.score}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-muted-foreground">Complete:</span>
                          <span className="text-sm font-semibold text-foreground">{run.completeness}%</span>
                        </div>
                      </div>
                    </div>
                  ))}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
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
