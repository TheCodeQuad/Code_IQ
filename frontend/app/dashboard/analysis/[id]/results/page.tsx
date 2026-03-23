"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useAnalysis } from "@/lib/analysis-context"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  FileCode,
  FileText,
  GitBranch,
  GitPullRequest,
  ClipboardCheck,
  ArrowRight,
  Layers,
  CheckCircle2,
  Code2,
  BookOpen,
  BarChart3,
} from "lucide-react"

const pageDescriptions = [
  {
    href: "/documentation",
    title: "Documentation",
    icon: FileCode,
    description: "Browse and explore the generated documentation for your entire repository. View code with or without docstrings, copy snippets, and navigate through your file structure.",
    features: ["File tree navigation", "Code viewer with syntax highlighting", "Toggle docstrings on/off", "Copy code snippets"],
    stats: { label: "Files Documented", value: "156" },
    iconBg: "bg-blue-100",
    iconColor: "text-blue-600",
  },
  {
    href: "/readme",
    title: "README",
    icon: FileText,
    description: "View and download the AI-generated README.md file for your repository. Includes project overview, installation instructions, API reference, and usage examples.",
    features: ["Markdown preview", "Download as file", "Copy to clipboard", "Edit and customize"],
    stats: { label: "Sections Generated", value: "8" },
    iconBg: "bg-emerald-100",
    iconColor: "text-emerald-600",
  },
  {
    href: "/graph",
    title: "View Graphs",
    icon: GitBranch,
    description: "Visualize your code structure through multiple graph types including Agent Flow, Control Flow Graphs (CFG), Program Dependency Graphs (PDG), and more.",
    features: ["Multiple graph types", "Draggable nodes", "Zoom and pan controls", "Export graphs as images"],
    stats: { label: "Components Analyzed", value: "45" },
    iconBg: "bg-purple-100",
    iconColor: "text-purple-600",
  },
  {
    href: "/metrics",
    title: "Evaluation",
    icon: BarChart3,
    description: "Review the quality metrics and evaluation scores for the generated documentation. Check completeness, accuracy, consistency, and helpfulness ratings.",
    features: ["Quality scores", "Coverage statistics", "Verification results", "Export reports"],
    stats: { label: "Quality Score", value: "92%" },
    iconBg: "bg-amber-100",
    iconColor: "text-amber-600",
  },
  {
    href: "/pull-request",
    title: "Pull Request",
    icon: GitPullRequest,
    description: "Review generated changes, configure reviewers and merge strategy, then create a pull request from one place.",
    features: ["Diff preview", "Reviewer selection", "Labels and checklist", "Draft and merge options"],
    stats: { label: "Changed Files", value: "6" },
    iconBg: "bg-rose-100",
    iconColor: "text-rose-600",
  },
]

export default function ResultsOverviewPage() {
  const params = useParams()
  const id = params.id as string
  const basePath = `/dashboard/analysis/${id}/results`
  const { getAnalysis } = useAnalysis()
  const analysis = getAnalysis(id)

  const [repoName, setRepoName] = useState<string>(analysis?.repoName || "Repository")
  const [repoStatus, setRepoStatus] = useState<string>(analysis?.status || "pending")
  const [fileCount, setFileCount] = useState<number>(0)
  const [componentCount, setComponentCount] = useState<number>(analysis?.stats?.total_components || 0)

  const documentedPct = useMemo(() => {
    const total = analysis?.stats?.total_components || componentCount
    const documented = analysis?.stats?.components_with_docstrings || 0
    if (!total) return 0
    return Math.round((documented / total) * 100)
  }, [analysis?.stats, componentCount])

  useEffect(() => {
    async function loadCounts() {
      try {
        const [repoRes, treeRes] = await Promise.all([
          fetch(`/api/repos/${id}`),
          fetch(`/api/repos/${id}/tree`),
        ])

        if (repoRes.ok) {
          const repoData = await repoRes.json()
          if (typeof repoData?.repo_name === "string" && repoData.repo_name.trim()) {
            setRepoName(repoData.repo_name)
          }
          if (typeof repoData?.status === "string" && repoData.status.trim()) {
            setRepoStatus(repoData.status)
          }
          let hasRepoFileCount = false
          if (typeof repoData.file_count === "number") {
            setFileCount(repoData.file_count)
            hasRepoFileCount = true
          }
          const repoComponents = repoData?.stats?.total_components
          if (typeof repoComponents === "number") {
            setComponentCount(repoComponents)
          }

          if (treeRes.ok && !hasRepoFileCount) {
            const treeData = await treeRes.json()
            const countFiles = (nodes: any[]): number =>
              nodes.reduce((total, node) => {
                if (node.type === "file") return total + 1
                if (node.type === "folder" && Array.isArray(node.children)) {
                  return total + countFiles(node.children)
                }
                return total
              }, 0)

            setFileCount(countFiles(treeData.tree || []))
          }
        }
      } catch {
        // Keep fallbacks from analysis context
      }
    }

    loadCounts()
  }, [id])

  useEffect(() => {
    if (analysis?.stats?.total_components) {
      setComponentCount(analysis.stats.total_components)
    }
    if (analysis?.repoName) {
      setRepoName(analysis.repoName)
    }
    if (analysis?.status) {
      setRepoStatus(analysis.status)
    }
  }, [analysis])

  return (
    <div className="space-y-6">
      

      {/* Overview Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-stone-800">Results Overview</h1>
          
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="gap-1.5 py-1.5 border-stone-200 text-stone-600">
            <Layers className="w-3.5 h-3.5" />
            {fileCount || "-"} files
          </Badge>
          <Badge variant="outline" className="gap-1.5 py-1.5 border-stone-200 text-stone-600">
            <Code2 className="w-3.5 h-3.5" />
            {componentCount || "-"} components
          </Badge>
          <Badge className="gap-1.5 py-1.5 bg-emerald-100 text-emerald-700 border-0">
            <CheckCircle2 className="w-3.5 h-3.5" />
            {documentedPct}% documented
          </Badge>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { icon: FileCode, label: "Total Files", value: String(fileCount || "-"), bg: "bg-blue-100", color: "text-blue-600" },
          { icon: BookOpen, label: "Components", value: String(componentCount || "-"), bg: "bg-emerald-100", color: "text-emerald-600" },
          { icon: GitBranch, label: "Graphs Generated", value: "5 types", bg: "bg-purple-100", color: "text-purple-600" },
          { icon: CheckCircle2, label: "Documentation", value: `${documentedPct}%`, bg: "bg-amber-100", color: "text-amber-600" },
        ].map((stat) => (
          <Card key={stat.label} className="border-stone-200 bg-white">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl ${stat.bg} flex items-center justify-center`}>
                  <stat.icon className={`w-5 h-5 ${stat.color}`} />
                </div>
                <div>
                  <p className="text-xl font-semibold text-stone-800">{stat.value}</p>
                  <p className="text-xs text-stone-500">{stat.label}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Page Navigation Cards */}
      <div className="grid md:grid-cols-2 gap-4">
        {pageDescriptions.map((page) => {
          const Icon = page.icon
          const statValue =
            page.href === "/documentation"
              ? String(fileCount || "-")
              : page.href === "/graph"
                ? String(componentCount || "-")
                : page.stats.value
          return (
            <Card key={page.href} className="border-stone-200 bg-white hover:border-stone-300 transition-all group">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className={`w-11 h-11 rounded-xl ${page.iconBg} flex items-center justify-center`}>
                    <Icon className={`w-5 h-5 ${page.iconColor}`} />
                  </div>
                  <Badge variant="outline" className="text-xs border-stone-200 text-stone-500">
                    {page.stats.label}: {statValue}
                  </Badge>
                </div>
                <CardTitle className="text-lg mt-3 text-stone-800">{page.title}</CardTitle>
                <CardDescription className="text-sm leading-relaxed text-stone-500">
                  {page.description}
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex flex-wrap gap-1.5 mb-4">
                  {page.features.map((feature) => (
                    <Badge key={feature} className="text-xs font-normal bg-stone-100 text-stone-600 border-0 hover:bg-stone-100">
                      {feature}
                    </Badge>
                  ))}
                </div>
                <Link href={`${basePath}${page.href}`}>
                  <Button variant="outline" className="w-full border-stone-200 bg-white hover:bg-stone-50 text-stone-700 group-hover:border-stone-300">
                    Open {page.title}
                    <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                  </Button>
                </Link>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
