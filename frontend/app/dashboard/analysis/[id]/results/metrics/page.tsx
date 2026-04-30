"use client"

import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { useAnalysis } from "@/lib/analysis-context"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { useToast } from "@/hooks/use-toast"
import { ScrollArea } from "@/components/ui/scroll-area"
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
  FileText,
  CheckCircle2,
  AlertCircle,
  Info,
  ChevronRight,
  Lightbulb,
  BookOpen,
  Eye,
  Layers,
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
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null)
  const [isEvaluating, setIsEvaluating] = useState(false)
  const [isLoadingResults, setIsLoadingResults] = useState(true)
  const [evaluationStep, setEvaluationStep] = useState<EvaluationStep>("idle")
  const [evaluationResults, setEvaluationResults] = useState<any>(null)
  const [stageResults, setStageResults] = useState<Record<string, any>>({})
  const [rawEvaluationOutput, setRawEvaluationOutput] = useState<string>("")
  const [evaluationError, setEvaluationError] = useState<string | null>(null)
  const { toast } = useToast()
  
  const params = useParams()
  const analysisId = params.id as string
  const { getAnalysis } = useAnalysis()
  const analysis = getAnalysis(analysisId)

  const getRepoName = async (): Promise<string | null> => {
    if (analysis?.repoName) return analysis.repoName

    try {
      const res = await fetch(`/api/repos/${analysisId}`, { cache: "no-store" })
      if (!res.ok) return null
      const data = await res.json()
      return data?.repo?.repo_name || data?.repo_name || null
    } catch {
      return null
    }
  }

  // Fetch saved evaluation results on page load
  useEffect(() => {
    const fetchSavedResults = async () => {
      const repoName = await getRepoName()
      if (!repoName) {
        setIsLoadingResults(false)
        return
      }

      try {
        const response = await fetch(`/api/evaluate?repo_name=${encodeURIComponent(repoName)}`)
        if (response.ok) {
          const payload = await response.json()
          
          // Normalize the payload - scores come as percentages (0-100)
          const normalized = {
            overall_quality_score: (payload.overall_quality_score || 0) / 100,
            completeness: (payload.completeness?.score || 0) / 100,
            helpfulness: (payload.helpfulness?.score || 0) / 100,
            truthfulness: (payload.truthfulness?.score || 0) / 100,
            completeness_full: payload.completeness?.details || null,
            helpfulness_full: payload.helpfulness?.details || null,
            truthfulness_full: payload.truthfulness?.details || null,
            output_file: payload.output_file,
          }

          setEvaluationResults(normalized)
          setStageResults({
            completeness: normalized.completeness_full,
            helpfulness: normalized.helpfulness_full,
            truthfulness: normalized.truthfulness_full,
            overall: normalized,
          })
          setEvaluationStep("complete")
          console.log("✅ Loaded saved evaluation results:", normalized)
        }
      } catch (error) {
        console.log("No saved evaluation results found")
      } finally {
        setIsLoadingResults(false)
      }
    }

    fetchSavedResults()
  }, [analysisId])

  const normalizeEvaluationPayload = (payload: any) => {
    const completenessRaw = payload?.completeness
    const helpfulnessRaw = payload?.helpfulness
    const truthfulnessRaw = payload?.truthfulness

    const completenessScore =
      typeof completenessRaw === "number"
        ? completenessRaw
        : Number(completenessRaw?.summary?.overall_score || 0)
    const helpfulnessScore =
      typeof helpfulnessRaw === "number"
        ? helpfulnessRaw
        : Number(helpfulnessRaw?.summary?.average_score || 0) / 5
    const truthfulnessScore =
      typeof truthfulnessRaw === "number"
        ? truthfulnessRaw
        : Number(truthfulnessRaw?.summary?.overall_accuracy || 0)

    return {
      overall_quality_score: Number(payload?.overall_quality_score || 0),
      completeness: completenessScore,
      helpfulness: helpfulnessScore,
      truthfulness: truthfulnessScore,
      completeness_full: typeof completenessRaw === "object" ? completenessRaw : null,
      helpfulness_full: typeof helpfulnessRaw === "object" ? helpfulnessRaw : null,
      truthfulness_full: typeof truthfulnessRaw === "object" ? truthfulnessRaw : null,
      output_file: payload?.output_file,
      timestamp: payload?.timestamp,
      message: payload?.message,
    }
  }

  const handleEvaluate = async () => {
    const repoName = await getRepoName()
    if (!repoName) {
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
    setRawEvaluationOutput("")
    setEvaluationStep("completeness")
    
    try {
      console.log("🔍 Starting evaluation for:", repoName)

      const response = await fetch("/api/evaluate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ repo_name: repoName }),
      })

      if (!response.ok) {
        let errorMsg = `HTTP ${response.status}`
        try {
          const errorData = await response.json()
          errorMsg = errorData.detail || errorData.error || errorMsg
        } catch {
          const text = await response.text()
          errorMsg = text || errorMsg
        }
        throw new Error(errorMsg)
      }

      setEvaluationStep("helpfulness")
      const payload = await response.json()
      const normalized = normalizeEvaluationPayload(payload)

      setEvaluationStep("truthfulness")
      setEvaluationResults(normalized)
      setStageResults({
        completeness: normalized.completeness_full,
        helpfulness: normalized.helpfulness_full,
        truthfulness: normalized.truthfulness_full,
        overall: normalized,
      })
      setRawEvaluationOutput(JSON.stringify(payload, null, 2))
      setEvaluationStep("complete")

      toast({
        title: "Evaluation Complete",
        description: `Overall Score: ${Math.round(normalized.overall_quality_score * 100)}%`,
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

  const metricsUi = [
    {
      name: "Completeness",
      score: summaryMetrics.completeness,
      icon: FileText,
      color: "amber",
      description: "Measures the coverage of documentation across all code elements",
      formula: "C = (D_elements / T_elements) * 100",
      formulaExplanation: "Where D = documented elements and T = total elements",
      details: [
        { label: "Functions", value: `${analysis?.stats?.functions || 0}`, percent: Math.min(summaryMetrics.completeness, 100) },
        { label: "Classes", value: `${analysis?.stats?.classes || 0}`, percent: Math.min(summaryMetrics.completeness, 100) },
        { label: "Methods", value: `${analysis?.stats?.methods || 0}`, percent: Math.max(summaryMetrics.completeness - 4, 0) },
        { label: "Files Verified", value: `${summaryMetrics.filesVerified}/${summaryMetrics.totalFiles}`, percent: summaryMetrics.completeness },
      ],
    },
    {
      name: "Helpfulness",
      score: summaryMetrics.helpfulness,
      icon: Zap,
      color: "blue",
      description: "Evaluates the quality and usefulness of documentation content",
      formula: "H = (R_score + E_score + C_score) / 3",
      formulaExplanation: "R = readability, E = examples, C = clarity",
      details: [
        { label: "Average", value: `${(helpfulnessAverage || 0).toFixed(2)}/5`, percent: Math.round(((helpfulnessAverage || 0) / 5) * 100) },
        { label: "Min", value: helpfulnessMin !== undefined ? `${Number(helpfulnessMin).toFixed(2)}` : "-", percent: helpfulnessMin !== undefined ? Math.round((Number(helpfulnessMin) / 5) * 100) : 0 },
        { label: "Max", value: helpfulnessMax !== undefined ? `${Number(helpfulnessMax).toFixed(2)}` : "-", percent: helpfulnessMax !== undefined ? Math.round((Number(helpfulnessMax) / 5) * 100) : 0 },
        { label: "Components", value: `${helpfulnessComponents.length}`, percent: summaryMetrics.helpfulness },
      ],
    },
    {
      name: "Truthfulness",
      score: summaryMetrics.truthfulness,
      icon: Shield,
      color: "emerald",
      description: "Verifies correctness of documentation against actual code behavior",
      formula: "T = (V_correct / V_total) * 100",
      formulaExplanation: "V = verified items across components",
      details: [
        { label: "Overall Accuracy", value: `${summaryMetrics.truthfulness}%`, percent: summaryMetrics.truthfulness },
        { label: "Issue Types", value: `${Object.keys(stageResults.truthfulness?.summary?.issue_types || {}).length}`, percent: Math.max(summaryMetrics.truthfulness - 6, 0) },
        { label: "Total Components", value: `${stageResults.truthfulness?.summary?.total_components || summaryMetrics.totalFiles}`, percent: Math.max(summaryMetrics.truthfulness - 3, 0) },
        { label: "Verification", value: summaryMetrics.truthfulness > 80 ? "Strong" : "Needs review", percent: summaryMetrics.truthfulness },
      ],
    },
    {
      name: "Overall",
      score: summaryMetrics.overallScore,
      icon: Target,
      color: "purple",
      description: "Aggregated score combining completeness, helpfulness and truthfulness",
      formula: "Overall = (C + H + T) / 3",
      formulaExplanation: "All three dimensions are weighted equally",
      details: [
        { label: "Completeness", value: `${summaryMetrics.completeness}%`, percent: summaryMetrics.completeness },
        { label: "Helpfulness", value: `${summaryMetrics.helpfulness}%`, percent: summaryMetrics.helpfulness },
        { label: "Truthfulness", value: `${summaryMetrics.truthfulness}%`, percent: summaryMetrics.truthfulness },
        { label: "Total", value: `${summaryMetrics.overallScore}%`, percent: summaryMetrics.overallScore },
      ],
    },
  ]

  const selectedMetricData = metricsUi.find((m) => m.name === selectedMetric) || null

  const qualityDimensions = [
    { metric: "Readability", value: Math.max(summaryMetrics.helpfulness - 5, 0) },
    { metric: "Accuracy", value: summaryMetrics.truthfulness },
    { metric: "Coverage", value: summaryMetrics.completeness },
    { metric: "Style", value: Math.min(summaryMetrics.overallScore + 3, 100) },
    { metric: "Examples", value: Math.max(summaryMetrics.helpfulness - 10, 0) },
    { metric: "Consistency", value: Math.min(summaryMetrics.overallScore + 1, 100) },
  ]

  return (
    <div className="space-y-5">
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <TabsList className="bg-stone-100 p-1">
            <TabsTrigger value="overview" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">Overview</TabsTrigger>
            <TabsTrigger value="files" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">File-level Metrics</TabsTrigger>
            <TabsTrigger value="history" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">History</TabsTrigger>
          </TabsList>

          <div className="flex items-center gap-2 md:justify-end">
            <Button variant="outline" size="sm" className="gap-2 border-stone-200" onClick={handleEvaluate} disabled={isEvaluating}>
              <RefreshCw className={`w-4 h-4 ${isEvaluating ? "animate-spin" : ""}`} />
              {isEvaluating ? "Evaluating..." : "Re-evaluate"}
            </Button>
            <Button variant="outline" size="sm" className="gap-2 border-stone-200">
              <Download className="w-4 h-4" />
              Export Report
            </Button>
          </div>
        </div>

        <TabsContent value="overview" className="mt-5 space-y-5">
          {isEvaluating && (
            <Card className="border-stone-200 bg-white">
              <CardContent className="p-4 flex items-center gap-2 text-sm text-stone-600">
                <Loader className="w-4 h-4 animate-spin" />
                <span>
                  {evaluationStep === "completeness" && "Checking Completeness..."}
                  {evaluationStep === "helpfulness" && "Evaluating Helpfulness..."}
                  {evaluationStep === "truthfulness" && "Verifying Truthfulness..."}
                  {evaluationStep === "complete" && "Complete!"}
                </span>
              </CardContent>
            </Card>
          )}
        
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

          <div className="grid grid-cols-5 gap-4">
            <Card className="border-stone-200 bg-white">
            <CardContent className="p-6">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-7 h-7 rounded-lg bg-amber-100 flex items-center justify-center">
                  <Target className="w-4 h-4 text-amber-600" />
                </div>
                <span className="text-xs font-medium text-stone-500">Overall Score</span>
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-3xl font-bold text-stone-800">{summaryMetrics.overallScore}</span>
                <span className="text-sm text-stone-400">/100</span>
              </div>
              <div className="flex items-center gap-1 mt-1">
                <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
                <span className="text-xs text-emerald-600 font-medium">Live backend score</span>
              </div>
            </CardContent>
          </Card>

          {metricsUi.map((metric) => {
            const Icon = metric.icon
            const colorClasses = {
              amber: { bg: "bg-amber-100", text: "text-amber-600", bar: "bg-amber-400" },
              blue: { bg: "bg-blue-100", text: "text-blue-600", bar: "bg-blue-400" },
              emerald: { bg: "bg-emerald-100", text: "text-emerald-600", bar: "bg-emerald-400" },
              purple: { bg: "bg-purple-100", text: "text-purple-600", bar: "bg-purple-400" },
            }[metric.color]

            return (
              <Card
                key={metric.name}
                className={`border-stone-200 bg-white cursor-pointer transition-all hover:border-stone-300 hover:shadow-sm ${selectedMetric === metric.name ? "ring-2 ring-amber-400 ring-offset-1" : ""}`}
                onClick={() => setSelectedMetric(selectedMetric === metric.name ? null : metric.name)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className={`w-7 h-7 rounded-lg ${colorClasses?.bg} flex items-center justify-center`}>
                      <Icon className={`w-4 h-4 ${colorClasses?.text}`} />
                    </div>
                    <span className="text-xs font-medium text-stone-500">{metric.name}</span>
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-stone-800">{metric.score}%</span>
                  </div>
                  <div className="h-1.5 bg-stone-100 rounded-full mt-2 overflow-hidden">
                    <div className={`h-full ${colorClasses?.bar} rounded-full transition-all`} style={{ width: `${metric.score}%` }} />
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>

          {selectedMetricData && (
            <Card className="border-amber-200 bg-amber-50/50">
              <CardContent className="p-5">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-semibold text-stone-800">{selectedMetricData.name} Score Breakdown</h3>
                    <p className="text-sm text-stone-500">{selectedMetricData.description}</p>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => setSelectedMetric(null)} className="text-stone-400">
                    <XCircle className="w-4 h-4" />
                  </Button>
                </div>
                <div className="grid grid-cols-3 gap-6">
                  <div className="p-4 bg-white rounded-xl border border-stone-200">
                    <div className="flex items-center gap-2 mb-3">
                      <Lightbulb className="w-4 h-4 text-amber-500" />
                      <span className="text-xs font-semibold text-stone-500 uppercase">Formula Used</span>
                    </div>
                    <code className="block text-sm font-mono bg-stone-100 px-3 py-2 rounded-lg text-stone-700 mb-2">
                      {selectedMetricData.formula}
                    </code>
                    <p className="text-xs text-stone-500">{selectedMetricData.formulaExplanation}</p>
                  </div>

                  <div className="col-span-2 p-4 bg-white rounded-xl border border-stone-200">
                    <div className="grid grid-cols-2 gap-3">
                      {selectedMetricData.details.map((detail) => (
                        <div key={detail.label} className="flex items-center justify-between p-2 bg-stone-50 rounded-lg">
                          <span className="text-sm text-stone-600">{detail.label}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-stone-800">{detail.value}</span>
                            <div className="w-16 h-1.5 bg-stone-200 rounded-full overflow-hidden">
                              <div className="h-full bg-stone-600 rounded-full" style={{ width: `${Math.max(detail.percent, 0)}%` }} />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

            <div className="grid lg:grid-cols-2 gap-6">
              <Card className="border-stone-200 bg-white">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base font-semibold text-stone-700">Metric Breakdown</CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={metricBreakdownData} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" horizontal vertical={false} />
                        <XAxis type="number" domain={[0, 100]} />
                        <YAxis type="category" dataKey="name" width={100} />
                        <Tooltip />
                        <Bar dataKey="score" radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              <Card className="border-stone-200 bg-white">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base font-semibold text-stone-700">Quality Dimensions</CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart data={qualityDimensions}>
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
                        <Tooltip />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              <Card className="border-stone-200 bg-white lg:col-span-2">
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    <CardTitle className="text-base font-semibold text-stone-700">Verifier Findings</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-4 gap-4">
                    {verifierFindings.map((finding) => {
                      const colorClasses = {
                        "text-chart-3": { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-600" },
                        "text-chart-1": { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-600" },
                        "text-chart-2": { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-600" },
                        "text-destructive": { bg: "bg-red-50", border: "border-red-200", text: "text-red-600" },
                      }[finding.color as keyof Record<string, { bg: string; border: string; text: string }>]

                      return (
                        <div key={finding.type} className={`p-4 rounded-xl ${colorClasses?.bg || "bg-stone-50"} border ${colorClasses?.border || "border-stone-200"}`}>
                        <div className="flex items-center justify-between mb-2">
                            <span className={`text-3xl font-bold ${colorClasses?.text || "text-stone-600"}`}>{finding.count}</span>
                            <Badge className="bg-white/70 border-0 text-xs capitalize">{finding.type}</Badge>
                        </div>
                          <p className="text-xs text-stone-500">{finding.description}</p>
                        </div>
                      )
                    })}
                  </div>
                </CardContent>
              </Card>

              <Card className="border-stone-200 bg-white lg:col-span-2">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-blue-500" />
                <CardTitle className="text-base font-semibold text-stone-700">Evaluation Formulas Reference</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                {metricsUi.map((metric) => {
                  const Icon = metric.icon
                  return (
                    <div key={metric.name} className="p-4 bg-stone-50 rounded-xl border border-stone-100">
                      <div className="flex items-center gap-2 mb-2">
                        <Icon className="w-4 h-4 text-stone-500" />
                        <span className="font-medium text-stone-700">{metric.name}</span>
                      </div>
                      <code className="block text-sm font-mono bg-white px-3 py-2 rounded-lg text-stone-600 border border-stone-200 mb-2">
                        {metric.formula}
                      </code>
                      <p className="text-xs text-stone-500">{metric.formulaExplanation}</p>
                    </div>
                  )
                })}
              </div>
              <div className="mt-4 p-4 bg-blue-50 rounded-xl border border-blue-100">
                <div className="flex items-start gap-3">
                  <Info className="w-5 h-5 text-blue-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-blue-800 mb-1">Overall Score Calculation</p>
                    <code className="text-sm font-mono text-blue-700">Overall = (Completeness + Helpfulness + Truthfulness) / 3</code>
                    <p className="text-xs text-blue-600 mt-1">Each metric is weighted equally in the final score calculation.</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-stone-200 bg-white lg:col-span-2">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-stone-700">Export Options</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: "Full Report", format: "PDF", description: "Complete evaluation with all metrics", icon: FileText },
                  { label: "Metrics Data", format: "JSON", description: "Raw metrics data for integration", icon: BarChart3 },
                  { label: "Summary", format: "MD", description: "Markdown summary for documentation", icon: BookOpen },
                  { label: "Chart Images", format: "PNG", description: "Export visualizations as images", icon: Eye },
                ].map((option) => (
                  <Button
                    key={option.label}
                    variant="outline"
                    className="h-auto py-4 px-4 flex flex-col items-start gap-2 border-stone-200 bg-white hover:bg-stone-50"
                  >
                    <div className="flex items-center gap-2 w-full">
                      <option.icon className="w-4 h-4 text-stone-500" />
                      <span className="font-medium text-stone-700 text-sm">{option.label}</span>
                      <Badge variant="outline" className="ml-auto text-xs border-stone-300">{option.format}</Badge>
                    </div>
                    <p className="text-xs text-stone-400 text-left">{option.description}</p>
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
            </div>

            {Object.keys(stageResults).length > 0 && (
              <Card className="border-stone-200 bg-white">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-semibold text-stone-700">Evaluation Pipeline Output</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-stone-600">
                  {stageResults.completeness && <p>Completeness complete: {Math.round((stageResults.completeness.summary?.overall_score || 0) * 100)}%</p>}
                  {stageResults.helpfulness && <p>Helpfulness average: {(helpfulnessAverage || 0).toFixed(2)}/5</p>}
                  {stageResults.truthfulness && <p>Truthfulness accuracy: {Math.round((stageResults.truthfulness.summary?.overall_accuracy || 0) * 100)}%</p>}
                </CardContent>
              </Card>
            )}

            {rawEvaluationOutput && (
              <Card className="border-stone-200 bg-white">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-semibold text-stone-700">Terminal Evaluation Result</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="max-h-[380px] overflow-auto rounded-lg bg-stone-950 p-4 text-xs leading-relaxed text-stone-100">
                    {rawEvaluationOutput}
                  </pre>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="files">
            <Card className="border-stone-200 bg-white">
              <CardHeader>
                <CardTitle className="text-base">File-level Metrics</CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[500px]">
                  <div className="space-y-2">
                    {fileMetrics.map((file) => {
                      const helpfulness = Math.max(file.completeness - 6, 0)
                      const consistency = Math.min(file.completeness + 2, 100)
                      const accuracy = Math.max(file.completeness - 4, 0)
                      return (
                        <div key={file.file} className="flex items-center gap-4 p-3 bg-stone-50 rounded-lg hover:bg-stone-100 transition-colors">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-stone-700 font-mono truncate">{file.file}</p>
                          </div>
                          <div className="flex items-center gap-6">
                            <div className="text-center">
                              <p className="text-xs text-stone-400">Comp.</p>
                              <p className={`text-sm font-medium ${file.completeness >= 95 ? "text-emerald-600" : "text-amber-600"}`}>{file.completeness}%</p>
                            </div>
                            <div className="text-center">
                              <p className="text-xs text-stone-400">Help.</p>
                              <p className={`text-sm font-medium ${helpfulness >= 90 ? "text-emerald-600" : "text-amber-600"}`}>{helpfulness}%</p>
                            </div>
                            <div className="text-center">
                              <p className="text-xs text-stone-400">Cons.</p>
                              <p className={`text-sm font-medium ${consistency >= 95 ? "text-emerald-600" : "text-amber-600"}`}>{consistency}%</p>
                            </div>
                            <div className="text-center">
                              <p className="text-xs text-stone-400">Acc.</p>
                              <p className={`text-sm font-medium ${accuracy >= 90 ? "text-emerald-600" : "text-amber-600"}`}>{accuracy}%</p>
                            </div>
                            <Link href={`/dashboard/analysis/${analysisId}/results/documentation`}>
                              <ChevronRight className="w-4 h-4 text-stone-400" />
                            </Link>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </ScrollArea>
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

              <Card className="border-stone-200 bg-white">
                <CardHeader>
                  <CardTitle className="text-base">Run History</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {historyData.slice().reverse().map((run, idx) => {
                    const delta = idx === 0 ? "+4" : idx === 1 ? "+2" : "-"
                    return (
                      <div key={run.run} className="flex items-center gap-4 p-4 bg-stone-50 rounded-xl">
                        <div className="w-12 h-12 rounded-xl bg-amber-100 flex items-center justify-center">
                          <span className="text-lg font-bold text-amber-600">{run.score}</span>
                        </div>
                        <div className="flex-1">
                          <p className="font-medium text-stone-700">{run.date}</p>
                          <p className="text-sm text-stone-500">{run.run}</p>
                        </div>
                        {delta !== "-" && (
                          <Badge className="bg-emerald-100 text-emerald-700 border-0">
                            <TrendingUp className="w-3 h-3 mr-1" />
                            {delta}
                          </Badge>
                        )}
                        <Button variant="outline" size="sm" className="border-stone-200">
                          View Details
                        </Button>
                      </div>
                    )
                  })}
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
    </div>
  )
}
