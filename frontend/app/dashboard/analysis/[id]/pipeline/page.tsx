"use client"

import React from "react"

import { useState, useEffect } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  Code2,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Loader2,
  FileCode,
  GitBranch,
  Users,
  BarChart3,
  Eye,
  Play,
  Pause,
  Terminal,
  Sparkles,
  Zap,
  Brain,
  Network,
  PenTool,
  Shield,
  ChevronRight,
  Activity,
} from "lucide-react"
import { useAnalysis } from "@/lib/analysis-context"

type PipelineStage = {
  id: string
  name: string
  description: string
  status: "pending" | "running" | "completed" | "error"
  icon: React.ComponentType<{ className?: string }>
  progress: number
  logs: string[]
  color: string
}

const initialStages: PipelineStage[] = [
  {
    id: "parsing",
    name: "Code Parsing",
    description: "Analyzing source code structure and syntax",
    status: "completed",
    icon: FileCode,
    progress: 100,
    color: "emerald",
    logs: [
      "[00:00:01] Starting code parser...",
      "[00:00:03] Found 89 Python files",
      "[00:00:12] Parsing complete: 234 functions, 45 classes",
    ],
  },
  {
    id: "cfg",
    name: "CFG Generation",
    description: "Building Control Flow Graphs",
    status: "completed",
    icon: Network,
    progress: 100,
    color: "emerald",
    logs: [
      "[00:00:15] Generating Control Flow Graphs...",
      "[00:00:28] Processing function definitions...",
      "[00:00:45] CFG generation complete: 234 graphs created",
    ],
  },
  {
    id: "pdg",
    name: "PDG Generation",
    description: "Building Program Dependency Graphs",
    status: "completed",
    icon: GitBranch,
    progress: 100,
    color: "emerald",
    logs: [
      "[00:00:48] Analyzing data dependencies...",
      "[00:01:15] Building dependency edges...",
      "[00:01:42] PDG generation complete",
    ],
  },
  {
    id: "hpg",
    name: "HPG Integration",
    description: "Creating Hybrid Program Graphs",
    status: "running",
    icon: Brain,
    progress: 65,
    color: "amber",
    logs: [
      "[00:01:45] Integrating CFG and PDG structures...",
      "[00:02:10] Building cross-function dependencies...",
      "[00:02:38] Processing module-level connections...",
    ],
  },
  {
    id: "agents",
    name: "Agent Pipeline",
    description: "Running Reader, Writer, and Verifier agents",
    status: "pending",
    icon: Users,
    progress: 0,
    color: "slate",
    logs: [],
  },
  {
    id: "verification",
    name: "Verification",
    description: "Validating documentation accuracy",
    status: "pending",
    icon: Shield,
    progress: 0,
    color: "slate",
    logs: [],
  },
  {
    id: "evaluation",
    name: "Evaluation",
    description: "Calculating quality metrics",
    status: "pending",
    icon: BarChart3,
    progress: 0,
    color: "slate",
    logs: [],
  },
]

const agentStatus = [
  { name: "Reader", icon: Eye, status: "active", task: "Extracting semantics from HPG nodes", color: "emerald" },
  { name: "Searcher", icon: Network, status: "waiting", task: "Waiting for Reader output", color: "slate" },
  { name: "Writer", icon: PenTool, status: "waiting", task: "Pending semantic analysis", color: "slate" },
  { name: "Verifier", icon: CheckCircle2, status: "idle", task: "Standing by", color: "slate" },
]

function AnimatedPipelineConnector({ isActive }: { isActive: boolean }) {
  return (
    <div className="relative h-8 flex items-center justify-center">
      <div className="w-0.5 h-full bg-border" />
      {isActive && (
        <div className="absolute w-2 h-2 rounded-full bg-primary animate-bounce" />
      )}
    </div>
  )
}

function PulsingDot({ color, active }: { color: string; active: boolean }) {
  if (!active) return <div className={`w-2 h-2 rounded-full bg-muted-foreground`} />
  
  return (
    <span className="relative flex h-2 w-2">
      <span className={`animate-ping absolute inline-flex h-full w-full rounded-full bg-${color} opacity-75`} />
      <span className={`relative inline-flex rounded-full h-2 w-2 bg-${color}`} />
    </span>
  )
}

export default function PipelinePage() {
  const params = useParams()
  const analysisId = params.id as string
  const { getAnalysis } = useAnalysis()
  const analysis = getAnalysis(analysisId)

  const repoName = analysis?.repoName || "api-gateway"
  const analysisStatus = analysis?.status || "in-progress"
  const fileCount = analysis?.stats?.total_components || 89
  const language = analysis?.language || "Python"

  // If analysis is completed, show all stages as completed
  const resolvedInitialStages = analysisStatus === "completed"
    ? initialStages.map(s => ({ ...s, status: "completed" as const, progress: 100 }))
    : analysisStatus === "failed"
    ? initialStages.map((s, i) => {
        if (i < 3) return { ...s, status: "completed" as const, progress: 100 }
        if (i === 3) return { ...s, status: "error" as const, progress: s.progress, logs: [...s.logs, `Error: ${analysis?.error || "Unknown error"}`] }
        return s
      })
    : initialStages

  const [stages, setStages] = useState<PipelineStage[]>(resolvedInitialStages)
  const [selectedStage, setSelectedStage] = useState<string>(analysisStatus === "completed" ? "evaluation" : "hpg")
  const [isPaused, setIsPaused] = useState(analysisStatus === "completed" || analysisStatus === "failed")
  const [overallProgress, setOverallProgress] = useState(analysisStatus === "completed" ? 100 : 0)
  const [elapsedTime, setElapsedTime] = useState(analysisStatus === "completed" ? 0 : 158)

  useEffect(() => {
    const completed = stages.filter((s) => s.status === "completed").length
    const running = stages.find((s) => s.status === "running")
    const runningProgress = running ? running.progress / 100 : 0
    setOverallProgress(((completed + runningProgress) / stages.length) * 100)
  }, [stages])

  useEffect(() => {
    if (isPaused) return

    const timer = setInterval(() => {
      setElapsedTime((prev) => prev + 1)
    }, 1000)

    return () => clearInterval(timer)
  }, [isPaused])

  useEffect(() => {
    if (isPaused) return

    const interval = setInterval(() => {
      setStages((prev) => {
        const newStages = [...prev]
        const runningIndex = newStages.findIndex((s) => s.status === "running")

        if (runningIndex !== -1) {
          const stage = newStages[runningIndex]
          if (stage.progress < 100) {
            stage.progress = Math.min(stage.progress + 3, 100)
            if (stage.progress === 100) {
              stage.status = "completed"
              if (runningIndex < newStages.length - 1) {
                newStages[runningIndex + 1].status = "running"
                newStages[runningIndex + 1].logs.push(`[${formatTime(elapsedTime)}] Starting stage...`)
              }
            }
          }
        }
        return newStages
      })
    }, 300)

    return () => clearInterval(interval)
  }, [isPaused, elapsedTime])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
  }

  const currentStage = stages.find((s) => s.id === selectedStage)
  const runningStageIndex = stages.findIndex((s) => s.status === "running")

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard">
              <Button variant="ghost" size="sm" className="gap-2">
                <ArrowLeft className="w-4 h-4" />
                Back
              </Button>
            </Link>
            <div className="h-6 w-px bg-border" />
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-foreground flex items-center justify-center">
                <Code2 className="w-5 h-5 text-background" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-foreground">{repoName}</span>
                  <Badge className={`font-normal ${
                    analysisStatus === "completed"
                      ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
                      : analysisStatus === "failed"
                      ? "bg-red-500/10 text-red-600 border border-red-500/20"
                      : "bg-amber-500/10 text-amber-600 border border-amber-500/20"
                  }`}>
                    <Activity className="w-3 h-3 mr-1" />
                    {analysisStatus === "completed" ? "Completed" : analysisStatus === "failed" ? "Failed" : "Running"}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">{language} - {fileCount} components</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right mr-2">
              <div className="text-xs text-muted-foreground">Elapsed</div>
              <div className="text-lg font-mono font-medium text-foreground">{formatTime(elapsedTime)}</div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="border-border bg-transparent h-9 px-3 text-sm"
              onClick={() => setIsPaused(!isPaused)}
            >
              {isPaused ? (
                <>
                  <Play className="w-3.5 h-3.5 mr-1.5" />
                  Resume
                </>
              ) : (
                <>
                  <Pause className="w-3.5 h-3.5 mr-1.5" />
                  Pause
                </>
              )}
            </Button>
            <Link href={`/dashboard/analysis/${analysisId}/graphs`}>
              <Button variant="outline" size="sm" className="border-border bg-transparent h-9 px-3 text-sm">
                <Network className="w-3.5 h-3.5 mr-1.5" />
                Graphs
              </Button>
            </Link>
            <Link href={`/dashboard/analysis/${analysisId}/agents`}>
              <Button size="sm" className="bg-foreground text-background hover:bg-foreground/90 h-9 px-3 text-sm">
                <Users className="w-3.5 h-3.5 mr-1.5" />
                Agents
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Overall Progress Card */}
        <Card className="border-border mb-8">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center">
                  <Zap className="w-6 h-6 text-slate-600" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-foreground">Pipeline Execution</h2>
                  <p className="text-sm text-muted-foreground">Processing 89 files through 7 intelligent stages</p>
                </div>
              </div>
              <div className="text-right">
                <div className="text-4xl font-semibold text-foreground">{Math.round(overallProgress)}%</div>
                <div className="text-sm text-muted-foreground">Complete</div>
              </div>
            </div>
            
            {/* Mini progress indicators */}
            <div className="flex items-center gap-1.5">
              {stages.map((stage) => (
                <div key={stage.id} className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                  <div 
                    className={`h-full rounded-full transition-all duration-300 ${
                      stage.status === "completed" 
                        ? "bg-emerald-500" 
                        : stage.status === "running"
                          ? "bg-amber-500"
                          : "bg-transparent"
                    }`}
                    style={{ 
                      width: stage.status === "pending" ? "0%" : `${stage.progress}%` 
                    }}
                  />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Pipeline Stages - Left Column */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-semibold text-foreground">Pipeline Stages</h3>
              <Badge className="bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 font-normal">
                {stages.filter(s => s.status === "completed").length}/{stages.length} Complete
              </Badge>
            </div>
            
            <div className="space-y-3">
              {stages.map((stage, index) => {
                const Icon = stage.icon
                const isSelected = stage.id === selectedStage
                const isRunning = stage.status === "running"
                const isCompleted = stage.status === "completed"

                return (
                  <div key={stage.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedStage(stage.id)}
                      className={`w-full text-left p-4 rounded-xl border transition-all group ${
                        isSelected
                          ? "border-foreground/20 bg-secondary"
                          : "border-border bg-card hover:border-foreground/20"
                      }`}
                    >
                      <div className="flex items-center gap-4">
                        {/* Status indicator */}
                        <div className={`relative w-11 h-11 rounded-lg flex items-center justify-center transition-all ${
                          isCompleted
                            ? "bg-emerald-50"
                            : isRunning
                              ? "bg-amber-50"
                              : "bg-secondary"
                        }`}>
                          {isCompleted ? (
                            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                          ) : isRunning ? (
                            <>
                              <Icon className="w-5 h-5 text-amber-600" />
                            </>
                          ) : (
                            <Icon className="w-5 h-5 text-muted-foreground" />
                          )}
                          
                          {/* Stage number */}
                          <div className={`absolute -top-1.5 -left-1.5 w-5 h-5 rounded-full flex items-center justify-center text-xs font-medium ${
                            isCompleted
                              ? "bg-emerald-500 text-white"
                              : isRunning
                                ? "bg-amber-500 text-white"
                                : "bg-muted text-muted-foreground"
                          }`}>
                            {index + 1}
                          </div>
                        </div>

                        {/* Stage info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-foreground">{stage.name}</p>
                            {isRunning && (
                              <Loader2 className="w-3.5 h-3.5 text-amber-600 animate-spin" />
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground">{stage.description}</p>
                          
                          {isRunning && (
                            <div className="mt-2">
                              <div className="flex items-center justify-between text-xs mb-1">
                                <span className="text-muted-foreground">Progress</span>
                                <span className="font-medium text-amber-600">{stage.progress}%</span>
                              </div>
                              <div className="h-1 bg-secondary rounded-full overflow-hidden">
                                <div className="h-full bg-amber-500 rounded-full transition-all" style={{ width: `${stage.progress}%` }} />
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Status badge */}
                        <div className="flex items-center gap-2">
                          <Badge
                            className={`font-normal ${
                              isCompleted
                                ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
                                : isRunning
                                  ? "bg-amber-500/10 text-amber-600 border border-amber-500/20"
                                  : "bg-muted text-muted-foreground border border-border"
                            }`}
                          >
                            {isCompleted ? "Complete" : isRunning ? "Running" : "Pending"}
                          </Badge>
                          <ChevronRight className={`w-4 h-4 transition-transform ${
                            isSelected ? "text-foreground rotate-90" : "text-muted-foreground"
                          }`} />
                        </div>
                      </div>
                    </button>
                    
                    {index < stages.length - 1 && (
                      <AnimatedPipelineConnector isActive={stage.status === "completed" && stages[index + 1]?.status === "running"} />
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Right Column - Agent Status & Logs */}
          <div className="space-y-6">
            {/* Agent Status */}
            <Card className="border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold flex items-center gap-2">
                  <Brain className="w-4 h-4 text-muted-foreground" />
                  Agent Orchestra
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {agentStatus.map((agent) => {
                  const Icon = agent.icon
                  const isActive = agent.status === "active"
                  
                  return (
                    <div 
                      key={agent.name} 
                      className={`p-3 rounded-lg transition-all ${
                        isActive 
                          ? "bg-emerald-50 border border-emerald-500/20" 
                          : "bg-secondary"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                          isActive ? "bg-emerald-100" : "bg-muted"
                        }`}>
                          <Icon className={`w-4 h-4 ${isActive ? "text-emerald-600" : "text-muted-foreground"}`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-foreground">{agent.name}</p>
                            {isActive && (
                              <span className="relative flex h-1.5 w-1.5">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-75" />
                                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground truncate">{agent.task}</p>
                        </div>
                        <Badge
                          className={`font-normal text-xs ${
                            isActive
                              ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
                              : agent.status === "waiting"
                                ? "bg-amber-500/10 text-amber-600 border border-amber-500/20"
                                : "bg-muted text-muted-foreground border border-border"
                          }`}
                        >
                          {agent.status}
                        </Badge>
                      </div>
                    </div>
                  )
                })}
              </CardContent>
            </Card>

            {/* Stage Logs */}
            {currentStage && (
              <Card className="border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-muted-foreground" />
                    {currentStage.name} Logs
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="bg-slate-900 rounded-lg p-4 font-mono text-xs max-h-64 overflow-y-auto">
                    {currentStage.logs.length > 0 ? (
                      currentStage.logs.map((log, i) => (
                        <div key={`${currentStage.id}-${i}`} className="text-slate-300 mb-1.5 flex items-start gap-2">
                          <span className="text-emerald-400 shrink-0">$</span>
                          <span>{log}</span>
                        </div>
                      ))
                    ) : (
                      <div className="text-slate-500 flex items-center gap-2">
                        <Clock className="w-3.5 h-3.5" />
                        Waiting to start...
                      </div>
                    )}
                    {currentStage.status === "running" && (
                      <div className="text-amber-400 flex items-center gap-2 mt-2">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Processing...</span>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Quick Actions */}
            <Card className="border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-muted-foreground" />
                  Quick Actions
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Link href={`/dashboard/analysis/${analysisId}/graphs`} className="block">
                  <Button variant="ghost" className="w-full justify-start h-10 hover:bg-secondary">
                    <Network className="w-4 h-4 mr-2 text-muted-foreground" />
                    Explore Graph Visualizations
                    <ChevronRight className="w-4 h-4 ml-auto text-muted-foreground" />
                  </Button>
                </Link>
                <Link href={`/dashboard/analysis/${analysisId}/agents`} className="block">
                  <Button variant="ghost" className="w-full justify-start h-10 hover:bg-secondary">
                    <Brain className="w-4 h-4 mr-2 text-muted-foreground" />
                    View Agent Reasoning
                    <ChevronRight className="w-4 h-4 ml-auto text-muted-foreground" />
                  </Button>
                </Link>
                <Link href={`/dashboard/analysis/${analysisId}/results`} className="block">
                  <Button variant="ghost" className="w-full justify-start h-10 hover:bg-secondary">
                    <BarChart3 className="w-4 h-4 mr-2 text-muted-foreground" />
                    Preview Documentation
                    <ChevronRight className="w-4 h-4 ml-auto text-muted-foreground" />
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  )
}
