"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { useSession, signOut } from "next-auth/react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Code2,
  Clock,
  CheckCircle2,
  AlertCircle,
  MoreVertical,
  Play,
  Eye,
  Trash2,
  FolderGit2,
  BarChart3,
  FileText,
  Settings,
  LogOut,
  Search,
  Sparkles,
  Activity,
  ChevronRight,
  Layers,
  UserPlus,
  ChevronUp,
  User,
  Wifi,
  WifiOff,
  Plus,
  Loader2,
} from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { isBackendOnline } from "@/lib/api"
import { useRepos } from "@/hooks/use-repos"
import { useAnalysis } from "@/lib/analysis-context"
import { useGitHub } from "@/hooks/use-github"
import type { RepoSummary } from "@/lib/repo-types"

// ── Status → visual config ──────────────────────────────────────────

const statusConfig: Record<
  string,
  { label: string; color: string; icon: typeof CheckCircle2 }
> = {
  completed: {
    label: "Completed",
    color: "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20",
    icon: CheckCircle2,
  },
  pending: {
    label: "Pending",
    color: "bg-muted text-muted-foreground border border-border",
    icon: AlertCircle,
  },
  parsing: {
    label: "Parsing",
    color: "bg-amber-500/10 text-amber-600 border border-amber-500/20",
    icon: Clock,
  },
  reading: {
    label: "Reading",
    color: "bg-amber-500/10 text-amber-600 border border-amber-500/20",
    icon: Clock,
  },
  searching: {
    label: "Searching",
    color: "bg-amber-500/10 text-amber-600 border border-amber-500/20",
    icon: Clock,
  },
  writing: {
    label: "Writing",
    color: "bg-amber-500/10 text-amber-600 border border-amber-500/20",
    icon: Clock,
  },
  verifying: {
    label: "Verifying",
    color: "bg-amber-500/10 text-amber-600 border border-amber-500/20",
    icon: Clock,
  },
  evaluating: {
    label: "Evaluating",
    color: "bg-amber-500/10 text-amber-600 border border-amber-500/20",
    icon: Clock,
  },
  failed: {
    label: "Failed",
    color: "bg-red-500/10 text-red-600 border border-red-500/20",
    icon: AlertCircle,
  },
}

const IN_PROGRESS_STATUSES = new Set<string>([
  "parsing",
  "reading",
  "searching",
  "writing",
  "verifying",
  "evaluating",
])

const languageColors: Record<string, string> = {
  typescript: "bg-blue-500",
  javascript: "bg-yellow-400",
  python: "bg-yellow-500",
  java: "bg-orange-500",
  go: "bg-cyan-500",
  rust: "bg-red-500",
  ruby: "bg-red-400",
  cpp: "bg-purple-500",
  csharp: "bg-green-600",
  php: "bg-indigo-500",
}

function langLabel(lang?: string) {
  if (!lang) return "Unknown"
  return lang.charAt(0).toUpperCase() + lang.slice(1)
}

export default function DashboardPage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [view, setView] = useState<"grid" | "list">("grid")
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const [processedCode, setProcessedCode] = useState<string | null>(null)
  const { data: session } = useSession()
  const router = useRouter()
  const { repos, loading, error, fetchRepos, uploadRepo, deleteRepo, generateDocs } = useRepos()
  const { authorizeGitHub } = useGitHub()

  // Handle GitHub OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get("code")

    // Only process the code once to prevent duplicate requests
    if (code && processedCode !== code && session?.user?.id) {
      console.log("[GitHub OAuth] Processing authorization code:", code.substring(0, 10) + "...")
      setProcessedCode(code)
      // Remove the one-time code immediately so strict mode / refresh cannot reuse it.
      window.history.replaceState({}, document.title, "/dashboard")
      
      authorizeGitHub(code).then((success) => {
        console.log("[GitHub OAuth] Authorization result:", success)
        if (success) {
          // Already cleared above.
        } else {
          // OAuth codes are one-time use. User must start a fresh OAuth flow.
          console.warn("[GitHub OAuth] Authorization failed. Please click Connect GitHub again to generate a new code.")
        }
      }).catch((err) => {
        console.error("[GitHub OAuth] Authorization error:", err)
        // OAuth codes are one-time use. User must start a fresh OAuth flow.
      })
    } else if (code && !session?.user?.id) {
      console.log("[GitHub OAuth] Code present but waiting for session:", code.substring(0, 10) + "...")
    }
  }, [session?.user?.id, authorizeGitHub, processedCode])

  // Check backend health on mount
  useEffect(() => {
    isBackendOnline().then(setBackendOnline)
  }, [])

  // Auto-refresh repos that are in-progress every 5 s
  useEffect(() => {
    const hasRunning = repos.some((r) => IN_PROGRESS_STATUSES.has(r.status))
    if (!hasRunning) return
    const timer = setInterval(fetchRepos, 5000)
    return () => clearInterval(timer)
  }, [repos, fetchRepos])

  const userName = session?.user?.name || ""
  const userEmail = session?.user?.email || ""

  const filteredProjects = repos.filter((r) =>
    r.repo_name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const completedCount = repos.filter((r) => r.status === "completed").length
  const avgScore = (() => {
    const scored = repos.filter((r) => r.overall_score != null)
    if (!scored.length) return 0
    return Math.round(
      scored.reduce((s, r) => s + (r.overall_score ?? 0), 0) / scored.length
    )
  })()
  const totalFiles = repos.reduce((s, r) => s + r.file_count, 0)

  async function handleDelete(repoId: string) {
    if (!confirm("Delete this repository?")) return
    try {
      await deleteRepo(repoId)
    } catch (err: any) {
      alert(err.message)
    }
  }

  async function handleGenerate(repoId: string) {
    router.push(`/dashboard/analysis/${repoId}/pipeline`)
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 bottom-0 w-72 bg-card border-r border-border p-6 flex flex-col">
        <Link href="/" className="flex items-center gap-3 mb-10">
          <div className="w-10 h-10 rounded-xl bg-foreground flex items-center justify-center">
            <Code2 className="w-6 h-6 text-background" />
          </div>
          <span className="text-2xl font-bold text-foreground tracking-tight">CodeIQ</span>
        </Link>

        <nav className="flex-1 space-y-1">
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 px-3">
            Main
          </div>
          <Link
            href="/dashboard"
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-secondary text-foreground font-medium"
          >
            <FolderGit2 className="w-5 h-5" />
            <span>Projects</span>
            <Badge className="ml-auto bg-foreground/10 text-foreground hover:bg-foreground/10 font-normal">{repos.length}</Badge>
          </Link>
          
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 mt-6 px-3">
            Insights
          </div>
          <Link
            href="/dashboard/docs"
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-muted-foreground hover:bg-secondary hover:text-foreground transition-all"
          >
            <FileText className="w-5 h-5" />
            <span>Documentation</span>
          </Link>
          <Link
            href="/dashboard/metrics"
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-muted-foreground hover:bg-secondary hover:text-foreground transition-all"
          >
            <BarChart3 className="w-5 h-5" />
            <span>Metrics</span>
          </Link>
          <Link
            href="/dashboard/activity"
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-muted-foreground hover:bg-secondary hover:text-foreground transition-all"
          >
            <Activity className="w-5 h-5" />
            <span>Activity</span>
          </Link>
        </nav>

        {/* Backend Status */}
        <div className="px-3 py-2 mb-2">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-secondary text-sm">
            {backendOnline === null ? (
              <>
                <div className="w-2 h-2 rounded-full bg-muted-foreground animate-pulse" />
                <span className="text-muted-foreground">Checking backend...</span>
              </>
            ) : backendOnline ? (
              <>
                <Wifi className="w-4 h-4 text-emerald-500" />
                <span className="text-emerald-600 font-medium">Backend Online</span>
              </>
            ) : (
              <>
                <WifiOff className="w-4 h-4 text-red-500" />
                <span className="text-red-500 font-medium">Backend Offline</span>
              </>
            )}
          </div>
        </div>

        <div className="border-t border-border pt-4">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-secondary transition-all w-full text-left"
              >
                <div className="w-9 h-9 rounded-lg bg-foreground/10 flex items-center justify-center shrink-0">
                  <User className="w-5 h-5 text-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{userName}</p>
                  <p className="text-xs text-muted-foreground truncate">{userEmail}</p>
                </div>
                <ChevronUp className="w-4 h-4 text-muted-foreground shrink-0" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="start" className="w-[256px]">
              <DropdownMenuItem asChild>
                <Link href="/signup" className="flex items-center gap-2 cursor-pointer">
                  <UserPlus className="w-4 h-4" />
                  Sign Up
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href="/settings" className="flex items-center gap-2 cursor-pointer">
                  <Settings className="w-4 h-4" />
                  Settings
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-red-600 focus:text-red-600 cursor-pointer"
                onClick={() => signOut({ callbackUrl: "/login" })}
              >
                <LogOut className="w-4 h-4 mr-2" />
                Sign Out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* Main Content */}
      <main className="ml-72 p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Projects</h1>
            <p className="text-sm text-muted-foreground mt-0.5">Manage and analyze your repositories</p>
          </div>
          <Link href="/dashboard/analysis/new">
            <Button className="bg-foreground text-background hover:bg-foreground/90 h-10 px-5 text-sm">
              <Plus className="w-4 h-4 mr-2" />
              New Analysis
            </Button>
          </Link>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          {[
            { icon: FolderGit2, label: "Total Projects", value: repos.length, bgColor: "bg-slate-100", iconColor: "text-slate-600" },
            { icon: CheckCircle2, label: "Completed", value: completedCount, bgColor: "bg-emerald-50", iconColor: "text-emerald-600" },
            { icon: Sparkles, label: "Avg. Score", value: avgScore ? `${avgScore}%` : "–", bgColor: "bg-amber-50", iconColor: "text-amber-600" },
            { icon: Layers, label: "Total Files", value: totalFiles.toLocaleString(), bgColor: "bg-violet-50", iconColor: "text-violet-600" },
          ].map((stat) => (
            <Card key={stat.label} className="border-border bg-card hover:border-foreground/20 transition-all">
              <CardContent className="p-5">
                <div className="flex items-center gap-4">
                  <div className={`w-11 h-11 rounded-xl ${stat.bgColor} flex items-center justify-center`}>
                    <stat.icon className={`w-5 h-5 ${stat.iconColor}`} />
                  </div>
                  <div>
                    <p className="text-2xl font-semibold text-foreground">{stat.value}</p>
                    <p className="text-sm text-muted-foreground">{stat.label}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Search and filters */}
        <div className="flex items-center gap-4 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <Input
              placeholder="Search projects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-12 h-12 bg-card border-border rounded-xl"
            />
          </div>
          <div className="flex items-center gap-2 p-1 bg-secondary rounded-lg">
            <button
              type="button"
              onClick={() => setView("grid")}
              className={`p-2 rounded-md transition-colors ${view === "grid" ? "bg-card shadow-sm" : "hover:bg-card/50"}`}
            >
              <svg className="w-5 h-5 text-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="7" height="7" />
                <rect x="14" y="3" width="7" height="7" />
                <rect x="3" y="14" width="7" height="7" />
                <rect x="14" y="14" width="7" height="7" />
              </svg>
            </button>
            <button
              type="button"
              onClick={() => setView("list")}
              className={`p-2 rounded-md transition-colors ${view === "list" ? "bg-card shadow-sm" : "hover:bg-card/50"}`}
            >
              <svg className="w-5 h-5 text-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        {/* Loading state */}
        {loading && repos.length === 0 && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground mr-3" />
            <span className="text-muted-foreground">Loading repositories…</span>
          </div>
        )}

        {/* Error state */}
        {error && (
          <Card className="border-red-200 bg-red-50 mb-6">
            <CardContent className="p-4 flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
              <Button size="sm" variant="outline" onClick={fetchRepos} className="ml-auto">
                Retry
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Projects Grid / List */}
        {!loading && filteredProjects.length > 0 && (
          <div className={view === "grid" ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5" : "space-y-3"}>
            {filteredProjects.map((repo) => (
              <RepoCard
                key={repo.id}
                repo={repo}
                view={view}
                onDelete={handleDelete}
                onGenerate={handleGenerate}
              />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && repos.length === 0 && !error && (
          <Card className="border-border bg-card">
            <CardContent className="p-12 text-center">
              <div className="w-16 h-16 rounded-2xl bg-secondary flex items-center justify-center mx-auto mb-4">
                <FolderGit2 className="w-8 h-8 text-muted-foreground" />
              </div>
              <h3 className="text-xl font-semibold text-foreground mb-2">No projects yet</h3>
              <p className="text-muted-foreground mb-6">Add your first GitHub repository to get started</p>
              <Link href="/dashboard/analysis/new">
                <Button className="bg-foreground text-background hover:bg-foreground/90 h-10 px-5 text-sm">
                  <Plus className="w-4 h-4 mr-2" />
                  New Analysis
                </Button>
              </Link>
            </CardContent>
          </Card>
        )}

        {/* Search empty state */}
        {!loading && repos.length > 0 && filteredProjects.length === 0 && (
          <Card className="border-border bg-card">
            <CardContent className="p-12 text-center">
              <div className="w-16 h-16 rounded-2xl bg-secondary flex items-center justify-center mx-auto mb-4">
                <Search className="w-8 h-8 text-muted-foreground" />
              </div>
              <h3 className="text-xl font-semibold text-foreground mb-2">No projects found</h3>
              <p className="text-muted-foreground mb-6">Try adjusting your search query</p>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  )
}

// ── Repo card sub-component ─────────────────────────────────────────

function RepoCard({
  repo,
  view,
  onDelete,
  onGenerate,
}: {
  repo: RepoSummary
  view: "grid" | "list"
  onDelete: (id: string) => void
  onGenerate: (id: string) => void
}) {
  const status = statusConfig[repo.status] ?? statusConfig.pending
  const StatusIcon = status.icon
  const langColor = languageColors[repo.language?.toLowerCase() ?? ""] || "bg-gray-500"
  const isRunning = IN_PROGRESS_STATUSES.has(repo.status)
  const timeLabel = repo.completed_at
    ? new Date(repo.completed_at).toLocaleDateString()
    : repo.updated_at
    ? new Date(repo.updated_at).toLocaleDateString()
    : "–"

  if (view === "list") {
    return (
      <Card className="border-border bg-card hover:border-foreground/20 transition-all">
        <CardContent className="p-4">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center">
              <FolderGit2 className="w-5 h-5 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-medium text-foreground truncate">{repo.repo_name}</h3>
                <div className={`w-2 h-2 rounded-full ${langColor}`} />
                <span className="text-sm text-muted-foreground">{langLabel(repo.language)}</span>
              </div>
              <div className="flex items-center gap-4 mt-0.5">
                <span className="text-sm text-muted-foreground">{repo.file_count} files</span>
                <span className="text-sm text-muted-foreground">{timeLabel}</span>
              </div>
            </div>
            <Badge className={`${status.color} font-normal`}>
              <StatusIcon className="w-3 h-3 mr-1.5" />
              {status.label}
            </Badge>
            {repo.overall_score != null && (
              <div className="text-right">
                <div className="text-xl font-semibold text-foreground">{Math.round(repo.overall_score)}%</div>
                <div className="text-xs text-muted-foreground">Score</div>
              </div>
            )}
            <Link href={`/dashboard/analysis/${repo.id}/results`}>
              <Button variant="ghost" size="sm" className="h-9 w-9 p-0">
                <ChevronRight className="w-4 h-4" />
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Grid card
  return (
    <Card className="border-border bg-card hover:border-foreground/20 transition-all group">
      <CardContent className="p-5">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center">
              <FolderGit2 className="w-5 h-5 text-muted-foreground" />
            </div>
            <div>
              <h3 className="font-medium text-foreground flex items-center gap-2">
                {repo.repo_name}
                {isRunning && (
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-500 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
                  </span>
                )}
              </h3>
              <div className="flex items-center gap-1.5 mt-0.5">
                <div className={`w-2 h-2 rounded-full ${langColor}`} />
                <span className="text-sm text-muted-foreground">{langLabel(repo.language)}</span>
              </div>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0 opacity-0 group-hover:opacity-100 transition-opacity">
                <MoreVertical className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link href={`/dashboard/analysis/${repo.id}/results`} className="cursor-pointer">
                  <Eye className="w-4 h-4 mr-2" />
                  View Results
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onGenerate(repo.id)}>
                <Play className="w-4 h-4 mr-2" />
                Start Analysis
              </DropdownMenuItem>
              <DropdownMenuItem className="text-destructive" onClick={() => onDelete(repo.id)}>
                <Trash2 className="w-4 h-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="flex items-center justify-between mb-4">
          <Badge className={`${status.color} font-normal`}>
            <StatusIcon className="w-3 h-3 mr-1.5" />
            {status.label}
          </Badge>
          {repo.overall_score != null && (
            <div className="flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-amber-500" />
              <span className="text-lg font-semibold text-foreground">{Math.round(repo.overall_score)}%</span>
            </div>
          )}
        </div>

        {/* Progress bar */}
        <div className="mb-4">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-muted-foreground">
              {isRunning ? `Progress (${repo.current_agent ?? "…"})` : "Progress"}
            </span>
            <span className="font-medium text-foreground">{repo.progress_percent}%</span>
          </div>
          <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                repo.status === "failed" ? "bg-red-500" : "bg-emerald-500"
              }`}
              style={{ width: `${repo.progress_percent}%` }}
            />
          </div>
        </div>

        <div className="flex items-center justify-between text-sm text-muted-foreground mb-5">
          <span className="flex items-center gap-1.5">
            <Layers className="w-4 h-4" />
            {repo.file_count} files
          </span>
          <span>{timeLabel}</span>
        </div>

        {repo.status === "completed" && (
          <Link href={`/dashboard/analysis/${repo.id}/results`}>
            <Button variant="outline" className="w-full border-border bg-transparent hover:bg-secondary">
              View Results
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </Link>
        )}
        {isRunning && (
          <Link href={`/dashboard/analysis/${repo.id}/pipeline`}>
            <Button variant="outline" className="w-full border-amber-500/30 bg-amber-500/5 text-amber-600 hover:bg-amber-500/10">
              <Activity className="w-4 h-4 mr-2" />
              View Progress
            </Button>
          </Link>
        )}
        {(repo.status === "pending" || repo.status === "failed") && (
          <Button
            className="w-full bg-foreground text-background hover:bg-foreground/90"
            onClick={() => onGenerate(repo.id)}
          >
            <Play className="w-4 h-4 mr-2" />
            Start Analysis
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
