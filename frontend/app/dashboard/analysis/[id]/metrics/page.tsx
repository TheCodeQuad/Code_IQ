"use client"

import { useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { useAnalysis } from "@/lib/analysis-context"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { useToast } from "@/hooks/use-toast"
import {
  Code2,
  ArrowLeft,
  BarChart3,
  TrendingUp,
  FileCheck,
  AlertTriangle,
  CheckCircle,
  XCircle,
  FileCode,
  Download,
  RefreshCw,
  Clock,
  Target,
  Zap,
  Shield,
  Loader,
} from "lucide-react"
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

// Summary metrics (mock fallback)
const mockSummaryMetrics = {
  overallScore: 92,
  completeness: 94,
  helpfulness: 91,
  truthfulness: 96,
  filesVerified: 42,
  totalFiles: 45,
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

// File-level metrics (mock fallback)
const mockFileMetrics = [
  { file: "api/gateway.py", lang: "Python", completeness: 98, verifier: "passed", issues: 0 },
  { file: "api/routes.py", lang: "Python", completeness: 95, verifier: "passed", issues: 0 },
  { file: "api/middleware.py", lang: "Python", completeness: 72, verifier: "warning", issues: 2 },
  { file: "auth/handler.py", lang: "Python", completeness: 100, verifier: "passed", issues: 0 },
  { file: "auth/token.py", lang: "Python", completeness: 94, verifier: "passed", issues: 0 },
  { file: "auth/utils.py", lang: "Python", completeness: 45, verifier: "pending", issues: 5 },
  { file: "models/user.py", lang: "Python", completeness: 100, verifier: "passed", issues: 0 },
  { file: "models/session.py", lang: "Python", completeness: 96, verifier: "passed", issues: 0 },
  { file: "config.py", lang: "Python", completeness: 88, verifier: "passed", issues: 1 },
  { file: "main.py", lang: "Python", completeness: 100, verifier: "passed", issues: 0 },
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

type EvaluationStep = "idle" | "completeness" | "helpfulness" | "truthfulness" | "complete"

export default function MetricsPage() {
  const [activeTab, setActiveTab] = useState<"overview" | "files" | "history">("overview")
  const [isEvaluating, setIsEvaluating] = useState(false)
  const [evaluationStep, setEvaluationStep] = useState<EvaluationStep>("idle")
  const [evaluationResults, setEvaluationResults] = useState<any>(null)
  const [stageResults, setStageResults] = useState<Record<string, any>>({})
  const [evaluationError, setEvaluationError] = useState<string | null>(null)
  const { toast } = useToast()
  
  const params = useParams()
  const analysisId = params.id as string
  const { getAnalysis } = useAnalysis()
  const analysis = getAnalysis(analysisId)

  const handleEvaluate = async () => {
    if (!analysis?.repoName) {
      toast({
        title: "Error",
        description: "Repository name not found",
        variant: "destructive",
      })
      return
    }

    setIsEvaluating(true)
    setEvaluationError(null)
    setEvaluationResults(null)
    setStageResults({})
    setEvaluationStep("completeness")
    
    try {
      console.log("🔍 Starting streaming evaluation for:", analysis.repoName)
      
      const response = await fetch(
        `http://localhost:8000/evaluate/stream?repo_name=${encodeURIComponent(analysis.repoName)}`,
        {
          method: "GET",
          headers: {
            Accept: "text/event-stream",
          },
        }
      )

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

      if (!response.body) {
        throw new Error("Streaming response body is not available")
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split("\n\n")
        buffer = events.pop() || ""

        for (const eventBlock of events) {
          if (!eventBlock.trim()) continue
          
          const lines = eventBlock.split("\n")
          let eventType = ""
          const dataLines: string[] = []

          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventType = line.slice(6).trim()
            } else if (line.startsWith("data:")) {
              dataLines.push(line.slice(5).trim())
            }
          }

          if (!dataLines.length || !eventType) continue

          try {
            const payload = JSON.parse(dataLines.join(""))

            if (eventType === "stage_started") {
              console.log(`📍 Started: ${payload.stage}`)
              setEvaluationStep(payload.stage)
            }

            if (eventType === "stage_complete") {
              console.log(`✅ Completed: ${payload.stage}`)
              setStageResults((prev) => ({
                ...prev,
                [payload.stage]: payload,
              }))

              setEvaluationResults((prev: any) => ({
                ...(prev || {}),
                [`${payload.stage}_score`]: payload.score,
                [`${payload.stage}_full`]: payload,
              }))
            }

            if (eventType === "overall_complete") {
              console.log("🎉 Overall complete")
              const results = payload.results
              setEvaluationResults(results)
              setStageResults((prev) => ({
                ...prev,
                overall: results,
              }))
              setEvaluationStep("complete")

              toast({
                title: "Evaluation Complete",
                description: `Overall Score: ${Math.round(results.overall_quality_score * 100)}%`,
              })
            }

            if (eventType === "error") {
              throw new Error(payload.message || "Stream error")
            }
          } catch (e) {
            console.error("Failed to parse event:", e, eventBlock)
          }
        }
      }
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

  // Use real analysis data when available, fall back to mock
  const summaryMetrics = evaluationResults ? {
    overallScore: Math.round((evaluationResults.overall_quality_score || 0) * 100),
    completeness: Math.round((evaluationResults.completeness || 0) * 100),
    helpfulness: Math.round((evaluationResults.helpfulness || 0) * 100),
    truthfulness: Math.round((evaluationResults.truthfulness || 0) * 100),
    filesVerified: analysis?.stats?.components_with_docstrings || 0,
    totalFiles: analysis?.stats?.total_components || 0,
  } : analysis?.stats ? {
    overallScore: Math.round((analysis.stats.components_with_docstrings / Math.max(analysis.stats.total_components, 1)) * 100),
    completeness: Math.round((analysis.stats.components_with_docstrings / Math.max(analysis.stats.total_components, 1)) * 100),
    helpfulness: 0,
    truthfulness: 0,
    filesVerified: analysis.stats.components_with_docstrings,
    totalFiles: analysis.stats.total_components,
  } : mockSummaryMetrics

  const metricBreakdownData = evaluationResults ? [
    { name: "Completeness", score: Math.round((evaluationResults.completeness || 0) * 100), fill: "var(--chart-1)" },
    { name: "Helpfulness", score: Math.round((evaluationResults.helpfulness || 0) * 100), fill: "var(--chart-2)" },
    { name: "Truthfulness", score: Math.round((evaluationResults.truthfulness || 0) * 100), fill: "var(--chart-3)" },
    { name: "Overall", score: Math.round((evaluationResults.overall_quality_score || 0) * 100), fill: "var(--chart-4)" },
  ] : metricBreakdown

  const fileMetrics = analysis?.components ? (() => {
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
      verifier: data.documented === data.total ? "passed" as const : data.documented > 0 ? "warning" as const : "pending" as const,
      issues: data.total - data.documented,
    }))
  })() : mockFileMetrics

  const verifierStatusConfig = {
    passed: { icon: CheckCircle, color: "text-chart-3", bg: "bg-chart-3/10" },
    warning: { icon: AlertTriangle, color: "text-chart-1", bg: "bg-chart-1/10" },
    pending: { icon: Clock, color: "text-muted-foreground", bg: "bg-muted" },
    failed: { icon: XCircle, color: "text-destructive", bg: "bg-destructive/10" },
  }

  const helpfulnessSummary = stageResults.helpfulness?.summary || {}
  const helpfulnessAverage = helpfulnessSummary.average_score ?? helpfulnessSummary.average ?? 0
  const helpfulnessMin = helpfulnessSummary.min_score ?? helpfulnessSummary.min
  const helpfulnessMax = helpfulnessSummary.max_score ?? helpfulnessSummary.max
  const helpfulnessSkipped = helpfulnessSummary.skipped_no_docstring ?? helpfulnessSummary.skipped
  const helpfulnessComponents = stageResults.helpfulness?.components || []

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
                <BarChart3 className="w-5 h-5 text-primary-foreground" />
              </div>
              <div>
                <span className="text-lg font-semibold text-foreground">Evaluation Metrics</span>
                <Badge className="ml-2 bg-chart-3/10 text-chart-3 border border-chart-3/20">{analysis?.repoName || "api-gateway"}</Badge>
              </div>
            </div>
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
            <Button variant="outline" size="sm" className="border-border bg-transparent">
              <Download className="w-4 h-4 mr-2" />
              Export Report
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Error Display */}
        {evaluationError && (
          <Card className="border-destructive/50 bg-destructive/5 mb-6">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <XCircle className="w-5 h-5 text-destructive mt-0.5" />
                <div className="flex-1">
                  <h4 className="font-semibold text-destructive mb-1">Evaluation Error</h4>
                  <p className="text-sm text-destructive/90 mb-3">{evaluationError}</p>
                  <div className="bg-destructive/10 rounded p-3 text-xs text-destructive/80 space-y-1 mb-3">
                    <p><strong>Troubleshooting:</strong></p>
                    <ul className="list-disc list-inside space-y-1">
                      <li>Check if backend is running: <code className="bg-black/20 px-1 rounded">python -m uvicorn backend.app:app --reload</code></li>
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
          <Card className="border-border/50 bg-secondary/30 mb-6">
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
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
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
              <div className="mt-3 flex items-center gap-1 text-chart-3 text-sm">
                <TrendingUp className="w-4 h-4" />
                <span>+4 from last run</span>
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

        {/* Evaluation Pipeline Output */}
        {Object.keys(stageResults).length > 0 && (
          <Card className="border-border mb-8 bg-secondary/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="w-5 h-5 text-chart-2" />
                Evaluation Pipeline Output
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Completeness Results */}
                {stageResults.completeness && (
                  <div className="border-l-4 border-chart-1 pl-6 py-4 bg-chart-1/5 rounded-r-lg">
                    <div className="flex items-center gap-2 mb-4">
                      <FileCheck className="w-5 h-5 text-chart-1" />
                      <h4 className="font-semibold text-foreground">Completeness Analysis</h4>
                      <Badge className="bg-chart-1/20 text-chart-1">{Math.round(stageResults.completeness.score * 100)}%</Badge>
                    </div>
                    {stageResults.completeness.summary && (
                      <div className="text-sm text-muted-foreground space-y-3 mb-4">
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="text-foreground font-medium">Total Components:</span>
                            <span className="ml-2">{stageResults.completeness.summary.total_components}</span>
                          </div>
                          <div>
                            <span className="text-foreground font-medium">Documented:</span>
                            <span className="ml-2">{stageResults.completeness.summary.components_with_docstrings}</span>
                          </div>
                        </div>
                      </div>
                    )}
                    {stageResults.completeness.summary?.criteria_percentages && (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-chart-1/20">
                              <th className="text-left py-2 px-2 font-medium">Criteria</th>
                              <th className="text-right py-2 px-2 font-medium">Coverage</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(stageResults.completeness.summary.criteria_percentages).map(([key, val]) => (
                              <tr key={key} className="border-b border-chart-1/10 hover:bg-chart-1/5">
                                <td className="py-2 px-2 capitalize">{key.replace(/_/g, " ")}</td>
                                <td className="py-2 px-2 text-right font-medium">{Math.round((val as number) * 100)}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {/* Helpfulness Results */}
                {stageResults.helpfulness && (
                  <div className="border-l-4 border-chart-2 pl-6 py-4 bg-chart-2/5 rounded-r-lg">
                    <div className="flex items-center gap-2 mb-4">
                      <Zap className="w-5 h-5 text-chart-2" />
                      <h4 className="font-semibold text-foreground">Helpfulness Evaluation</h4>
                      <Badge className="bg-chart-2/20 text-chart-2">{Math.round((helpfulnessAverage || 0) / 5 * 100)}%</Badge>
                    </div>
                    {helpfulnessSummary && (
                      <div className="text-sm text-muted-foreground space-y-3 mb-4">
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="text-foreground font-medium">Average Score:</span>
                            <span className="ml-2">{(helpfulnessAverage || 0).toFixed(2)}/5</span>
                          </div>
                          <div>
                            <span className="text-foreground font-medium">Normalized:</span>
                            <span className="ml-2">{Math.round((helpfulnessAverage || 0) / 5 * 100)}%</span>
                          </div>
                        </div>
                        {helpfulnessMin !== undefined && (
                          <div>
                            <span className="text-foreground font-medium">Range:</span>
                            <span className="ml-2">{helpfulnessMin?.toFixed(2)} - {helpfulnessMax?.toFixed(2)}</span>
                          </div>
                        )}
                        {helpfulnessSkipped !== undefined && (
                          <div>
                            <span className="text-foreground font-medium">Skipped:</span>
                            <span className="ml-2">{helpfulnessSkipped} components</span>
                          </div>
                        )}
                      </div>
                    )}

                    {helpfulnessComponents.length > 0 && (
                      <div className="mt-4 overflow-x-auto">
                        <div className="text-foreground font-medium text-sm mb-2">
                          Component-wise Helpfulness
                        </div>
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-chart-2/20">
                              <th className="text-left py-2 px-2 font-medium">Component</th>
                              <th className="text-left py-2 px-2 font-medium">Language</th>
                              <th className="text-left py-2 px-2 font-medium">Type</th>
                              <th className="text-right py-2 px-2 font-medium">Avg</th>
                              <th className="text-right py-2 px-2 font-medium">Summary</th>
                              <th className="text-right py-2 px-2 font-medium">Description</th>
                              <th className="text-right py-2 px-2 font-medium">Parameters</th>
                              <th className="text-right py-2 px-2 font-medium">Attributes</th>
                            </tr>
                          </thead>
                          <tbody>
                            {helpfulnessComponents.map((component: any) => (
                              <tr key={component.id} className="border-b border-chart-2/10 hover:bg-chart-2/5">
                                <td className="py-2 px-2 text-foreground">{component.name}</td>
                                <td className="py-2 px-2 capitalize">{component.language}</td>
                                <td className="py-2 px-2 capitalize">{component.type}</td>
                                <td className="py-2 px-2 text-right font-medium">{(component.average || 0).toFixed(2)}</td>
                                <td className="py-2 px-2 text-right">{component.aspects?.summary?.score ?? "-"}</td>
                                <td className="py-2 px-2 text-right">{component.aspects?.description?.score ?? "-"}</td>
                                <td className="py-2 px-2 text-right">{component.aspects?.parameters?.score ?? "-"}</td>
                                <td className="py-2 px-2 text-right">{component.aspects?.attributes?.score ?? "-"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {/* Truthfulness Results */}
                {stageResults.truthfulness && (
                  <div className="border-l-4 border-chart-3 pl-6 py-4 bg-chart-3/5 rounded-r-lg">
                    <div className="flex items-center gap-2 mb-4">
                      <Shield className="w-5 h-5 text-chart-3" />
                      <h4 className="font-semibold text-foreground">Truthfulness Verification</h4>
                      <Badge className="bg-chart-3/20 text-chart-3">{Math.round((stageResults.truthfulness.summary?.overall_accuracy || 0) * 100)}%</Badge>
                    </div>
                    {stageResults.truthfulness.summary && (
                      <div className="text-sm text-muted-foreground space-y-3 mb-4">
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="text-foreground font-medium">Overall Accuracy:</span>
                            <span className="ml-2">{Math.round((stageResults.truthfulness.summary.overall_accuracy || 0) * 100)}%</span>
                          </div>
                          <div>
                            <span className="text-foreground font-medium">Total Components:</span>
                            <span className="ml-2">{stageResults.truthfulness.summary.total_components}</span>
                          </div>
                        </div>
                        {stageResults.truthfulness.summary.issue_types && Object.keys(stageResults.truthfulness.summary.issue_types).length > 0 && (
                          <div className="mt-3">
                            <span className="text-foreground font-medium block mb-2">Issue Types:</span>
                            <div className="space-y-1">
                              {Object.entries(stageResults.truthfulness.summary.issue_types as Record<string, number>).map(([type, count]) => (
                                <div key={type} className="text-xs">
                                  <span className="capitalize">{type}:</span>
                                  <span className="ml-2 font-medium">{String(count)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

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
                      <div
                        key={finding.type}
                        className="p-4 bg-secondary/50 rounded-lg border border-border/50"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className={`text-3xl font-bold ${finding.color}`}>{finding.count}</span>
                          <Badge variant="outline" className="capitalize border-border">{finding.type}</Badge>
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
                  <Badge variant="outline" className="border-border">{fileMetrics.length} files</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">File</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Language</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Completeness</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Verifier</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Issues</th>
                        <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">Action</th>
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
                              <Badge variant="outline" className="border-border">{file.lang}</Badge>
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
                            <td className="py-3 px-4 text-right">
                              <Link href={`/dashboard/analysis/${analysisId}/documentation`}>
                                <Button variant="ghost" size="sm" className="text-xs">
                                  View
                                </Button>
                              </Link>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
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
                  {historyData.slice().reverse().map((run, idx) => (
                    <div
                      key={run.run}
                      className={`p-3 rounded-lg border ${idx === 0 ? "border-primary bg-primary/5" : "border-border/50 bg-secondary/30"}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Clock className="w-4 h-4 text-muted-foreground" />
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
      </main>
    </div>
  )
}
