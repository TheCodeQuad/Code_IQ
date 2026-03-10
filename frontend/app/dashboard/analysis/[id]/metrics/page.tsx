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
  consistency: 96,
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

export default function MetricsPage() {
  const [activeTab, setActiveTab] = useState<"overview" | "files" | "history">("overview")
  const params = useParams()
  const analysisId = params.id as string
  const { getAnalysis } = useAnalysis()
  const analysis = getAnalysis(analysisId)

  // Use real analysis data when available, fall back to mock
  const summaryMetrics = analysis?.stats ? {
    overallScore: Math.round((analysis.stats.components_with_docstrings / Math.max(analysis.stats.total_components, 1)) * 100),
    completeness: Math.round((analysis.stats.components_with_docstrings / Math.max(analysis.stats.total_components, 1)) * 100),
    consistency: 96,
    filesVerified: analysis.stats.components_with_docstrings,
    totalFiles: analysis.stats.total_components,
  } : mockSummaryMetrics

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
            <Button variant="outline" size="sm" className="border-border bg-transparent">
              <RefreshCw className="w-4 h-4 mr-2" />
              Re-evaluate
            </Button>
            <Button variant="outline" size="sm" className="border-border bg-transparent">
              <Download className="w-4 h-4 mr-2" />
              Export Report
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
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
                <div className="w-10 h-10 rounded-lg bg-chart-2/10 flex items-center justify-center">
                  <Zap className="w-5 h-5 text-chart-2" />
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
                <div className="w-10 h-10 rounded-lg bg-chart-3/10 flex items-center justify-center">
                  <Shield className="w-5 h-5 text-chart-3" />
                </div>
                <span className="text-sm text-muted-foreground">Consistency</span>
              </div>
              <div className="flex items-end gap-2">
                <span className="text-4xl font-bold text-foreground">{summaryMetrics.consistency}%</span>
              </div>
              <Progress value={summaryMetrics.consistency} className="mt-3 h-2" />
            </CardContent>
          </Card>

          <Card className="border-border">
            <CardContent className="p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-lg bg-chart-1/10 flex items-center justify-center">
                  <FileCheck className="w-5 h-5 text-chart-1" />
                </div>
                <span className="text-sm text-muted-foreground">Files Verified</span>
              </div>
              <div className="flex items-end gap-2">
                <span className="text-4xl font-bold text-foreground">{summaryMetrics.filesVerified}</span>
                <span className="text-muted-foreground mb-1">/ {summaryMetrics.totalFiles}</span>
              </div>
              <Progress value={(summaryMetrics.filesVerified / summaryMetrics.totalFiles) * 100} className="mt-3 h-2" />
            </CardContent>
          </Card>
        </div>

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
                      <BarChart data={metricBreakdown} layout="vertical">
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
