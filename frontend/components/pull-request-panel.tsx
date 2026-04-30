"use client"

import { useState, useEffect, useMemo } from "react"
import type { CSSProperties, ReactNode } from "react"
import { useSession } from "next-auth/react"
import { useGitHub } from "@/hooks/use-github"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  GitPullRequest,
  GitBranch,
  FileCode,
  Check,
  Loader2,
  User,
  Tag,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  GitMerge,
  GitCommit,
  Copy,
  FileText,
  Settings2,
  ListChecks,
  Eye,
  AlertTriangle,
  RefreshCw,
  ExternalLink,
  Edit3,
  Download,
  XCircle,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"

// Error types matching backend
type PRErrorType =
  | "branch_exists"
  | "no_write_access"
  | "protected_branch"
  | "merge_conflict"
  | "same_branch"
  | "token_expired"
  | "repo_not_found"
  | "rate_limited"
  | "invalid_branch_name"
  | "base_branch_not_found"
  | "network_error"
  | "no_changes"
  | "commit_failed"
  | "unknown"

interface PRError {
  type: PRErrorType
  message: string
  availableBranches?: string[]
}

const changedFiles = [
  {
    path: "api/gateway.py",
    additions: 47,
    deletions: 1,
    status: "modified" as const,
    diff: [
      { old: null, new: 1, type: "context" as const, content: "def handle_request(request):" },
      { old: 2, new: null, type: "removed" as const, content: '    """Handle incoming API request."""' },
      { old: null, new: 2, type: "added" as const, content: '    """Handle incoming API request.' },
      { old: null, new: 3, type: "added" as const, content: "" },
      { old: null, new: 4, type: "added" as const, content: "    Routes the request through authentication, rate limiting," },
      { old: null, new: 5, type: "added" as const, content: "    and to the appropriate downstream service." },
      { old: null, new: 6, type: "added" as const, content: "" },
      { old: null, new: 7, type: "added" as const, content: "    Args:" },
      { old: null, new: 8, type: "added" as const, content: "        request: The incoming HTTP request object." },
      { old: null, new: 9, type: "added" as const, content: "" },
      { old: null, new: 10, type: "added" as const, content: "    Returns:" },
      { old: null, new: 11, type: "added" as const, content: "        Response: The processed response from the downstream service." },
      { old: null, new: 12, type: "added" as const, content: '    """' },
      { old: null, new: 13, type: "context" as const, content: "    return route_to_service(request)" },
    ],
  },
  {
    path: "auth/handler.py",
    additions: 52,
    deletions: 1,
    status: "modified" as const,
    diff: [
      { old: null, new: 1, type: "context" as const, content: "def authenticate(token):" },
      { old: 2, new: null, type: "removed" as const, content: '    """Authenticate user."""' },
      { old: null, new: 2, type: "added" as const, content: '    """Authenticate user with provided token.' },
      { old: null, new: 3, type: "added" as const, content: "" },
      { old: null, new: 4, type: "added" as const, content: "    Validates the JWT token and returns user information." },
      { old: null, new: 5, type: "added" as const, content: '    """' },
      { old: null, new: 6, type: "context" as const, content: "    return validate_token(token)" },
    ],
  },
  {
    path: "auth/token.py",
    additions: 31,
    deletions: 0,
    status: "modified" as const,
    diff: [
      { old: null, new: 1, type: "context" as const, content: "def generate_token(user_id):" },
      { old: null, new: 2, type: "added" as const, content: '    """Generate a new JWT token for user.' },
      { old: null, new: 3, type: "added" as const, content: "" },
      { old: null, new: 4, type: "added" as const, content: "    Creates a signed JWT with user claims." },
      { old: null, new: 5, type: "added" as const, content: '    """' },
      { old: null, new: 6, type: "context" as const, content: "    return jwt.encode(payload, secret)" },
    ],
  },
  {
    path: "utils/validation.py",
    additions: 28,
    deletions: 0,
    status: "modified" as const,
    diff: [
      { old: null, new: 1, type: "context" as const, content: "def validate_input(data):" },
      { old: null, new: 2, type: "added" as const, content: '    """Validate input data against schema."""' },
      { old: null, new: 3, type: "context" as const, content: "    return schema.validate(data)" },
    ],
  },
  {
    path: "README.md",
    additions: 89,
    deletions: 0,
    status: "added" as const,
    diff: [
      { old: null, new: 1, type: "added" as const, content: "# API Gateway" },
      { old: null, new: 2, type: "added" as const, content: "" },
      { old: null, new: 3, type: "added" as const, content: "A high-performance API gateway service." },
      { old: null, new: 4, type: "added" as const, content: "" },
      { old: null, new: 5, type: "added" as const, content: "## Features" },
      { old: null, new: 6, type: "added" as const, content: "" },
      { old: null, new: 7, type: "added" as const, content: "- Authentication and authorization" },
      { old: null, new: 8, type: "added" as const, content: "- Rate limiting" },
      { old: null, new: 9, type: "added" as const, content: "- Request routing" },
    ],
  },
  {
    path: "config/settings.py",
    additions: 18,
    deletions: 0,
    status: "modified" as const,
    diff: [
      { old: null, new: 1, type: "context" as const, content: "class Settings:" },
      { old: null, new: 2, type: "added" as const, content: '    """Application settings configuration."""' },
      { old: null, new: 3, type: "context" as const, content: "    debug = False" },
    ],
  },
]

const availableReviewers = [
  { id: "1", name: "Sarah Chen", initials: "SC", color: "bg-violet-500/35 text-violet-400" },
  { id: "2", name: "Marcus Lee", initials: "ML", color: "bg-blue-500/35 text-blue-400" },
  { id: "3", name: "Alex Rivera", initials: "AR", color: "bg-emerald-500/35 text-emerald-400" },
  { id: "4", name: "Jordan Kim", initials: "JK", color: "bg-amber-500/35 text-amber-400" },
]

const availableLabels = [
  { id: "docs", name: "documentation", color: "bg-blue-500/25 text-blue-400 border-blue-500/60" },
  { id: "ai", name: "ai-generated", color: "bg-violet-500/25 text-violet-400 border-violet-500/60" },
  { id: "enhancement", name: "enhancement", color: "bg-emerald-500/25 text-emerald-400 border-emerald-500/60" },
  { id: "automated", name: "automated", color: "bg-amber-500/25 text-amber-400 border-amber-500/60" },
  { id: "chore", name: "chore", color: "bg-zinc-500/25 text-zinc-300 border-zinc-500/60" },
  { id: "breaking", name: "breaking-change", color: "bg-red-500/25 text-red-400 border-red-500/60" },
]

const checklistItems = [
  { id: "tests", label: "Tests pass or are not required for this change" },
  { id: "docs", label: "Documentation has been updated" },
  { id: "review", label: "Self-reviewed the code" },
  { id: "lint", label: "No lint errors introduced" },
]

const ACCENT = "oklch(0.72 0.22 80)"
const ACCENT_BG = "oklch(0.62 0.22 80)"

type PRStatus = "idle" | "loading" | "success" | "error"

interface GithubRepo {
  full_name: string
  owner: {
    login: string
  }
  default_branch: string
}

// Generate a short unique ID for branch names
function generateShortId(): string {
  return Math.random().toString(36).substring(2, 8)
}

// Generate a safe branch name from repo name
function generateBranchName(repoName: string, analysisId: string): string {
  const repoSlug = repoName
    .split("/")
    .pop()
    ?.replace(/[^a-zA-Z0-9-]/g, "-")
    .toLowerCase() || "repo"
  const shortId = analysisId.substring(0, 6) || generateShortId()
  return `codeiq/docs-${repoSlug}-${shortId}`
}

// Validate branch name
function validateBranchName(name: string): { valid: boolean; message?: string } {
  if (!name || name.trim() === "") {
    return { valid: false, message: "Branch name is required" }
  }
  if (name.startsWith("/") || name.endsWith("/")) {
    return { valid: false, message: "Branch name cannot start or end with /" }
  }
  if (name.includes("..")) {
    return { valid: false, message: "Branch name cannot contain .." }
  }
  if (!/^[a-zA-Z0-9/_.-]+$/.test(name)) {
    return { valid: false, message: "Branch name contains invalid characters" }
  }
  if (name.length > 100) {
    return { valid: false, message: "Branch name is too long (max 100 chars)" }
  }
  return { valid: true }
}

// Get error icon and color based on error type
function getErrorStyle(errorType: PRErrorType): { icon: typeof AlertTriangle; color: string; bgColor: string } {
  switch (errorType) {
    case "branch_exists":
      return { icon: GitBranch, color: "text-amber-400", bgColor: "bg-amber-500/10 border-amber-500/30" }
    case "no_write_access":
    case "protected_branch":
      return { icon: XCircle, color: "text-red-400", bgColor: "bg-red-500/10 border-red-500/30" }
    case "token_expired":
      return { icon: RefreshCw, color: "text-orange-400", bgColor: "bg-orange-500/10 border-orange-500/30" }
    case "rate_limited":
      return { icon: AlertTriangle, color: "text-yellow-400", bgColor: "bg-yellow-500/10 border-yellow-500/30" }
    default:
      return { icon: AlertTriangle, color: "text-red-400", bgColor: "bg-red-500/10 border-red-500/30" }
  }
}

export function PullRequestPanel({ analysisId }: { analysisId: string }) {
  const { data: session } = useSession()
  const { isConnected: githubConnectedFromHook } = useGitHub()
  const [prStatus, setPrStatus] = useState<PRStatus>("idle")
  const [prUrl, setPrUrl] = useState("")
  const [prError, setPrError] = useState<PRError | null>(null)
  const [repoData, setRepoData] = useState<GithubRepo | null>(null)
  const [branches, setBranches] = useState<string[]>(["main", "develop", "staging"])
  const [loadingRepo, setLoadingRepo] = useState(true)
  const [githubConnected, setGithubConnected] = useState<boolean | null>(null)
  const [title, setTitle] = useState("docs: add AI-generated documentation")
  const [description, setDescription] = useState(
"## Summary\nThis PR adds comprehensive documentation to enhance code readability, consistency, and maintainability across the codebase.\n\n## Changes\n- Added structured docstrings to functions, classes, and modules\n- Documented parameters, return values, and expected behavior\n- Enhanced inline documentation for better code understanding"  )
  const [baseBranch, setBaseBranch] = useState("main")
  const [sourceBranch, setSourceBranch] = useState("")
  const [isEditingBranch, setIsEditingBranch] = useState(false)
  const [mergeStrategy, setMergeStrategy] = useState("squash")
  const [linkedIssue, setLinkedIssue] = useState("")
  const [isDraft, setIsDraft] = useState(false)
  const [allowMaintainers, setAllowMaintainers] = useState(true)
  const [deleteOnMerge, setDeleteOnMerge] = useState(true)
  const [selectedReviewers, setSelectedReviewers] = useState<string[]>([])
  const [selectedLabels, setSelectedLabels] = useState<string[]>(["docs", "ai"])
  const [checklist, setChecklist] = useState<string[]>(["tests", "review"])
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set(["auth/handler.py"]))
  const [copied, setCopied] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [commitMessage, setCommitMessage] = useState("docs: Add AI-generated documentation via CodeIQ")
  const [prContentPreview, setPrContentPreview] = useState(false)

  // Branch validation
  const branchValidation = useMemo(() => validateBranchName(sourceBranch), [sourceBranch])
  const isSameBranch = sourceBranch === baseBranch
  const canSubmit = !loadingRepo && !!repoData && !!sourceBranch && !!baseBranch && !!title && !!description && branchValidation.valid && !isSameBranch

  // Fetch repository data on mount
  useEffect(() => {
    const fetchRepoData = async () => {
      setLoadingRepo(true)
      if (!analysisId) {
        console.error("No analysisId provided to PullRequestPanel")
        setLoadingRepo(false)
        return
      }

      try {
        console.log(`Fetching repo data for analysisId: ${analysisId}`)
        
        // Get user's token from session if available
        let headers: Record<string, string> = {}
        if (session?.user) {
          // Try to get GitHub token from the session or user data
          try {
            const sessionResponse = await fetch("/api/auth/session")
            if (sessionResponse.ok) {
              const sessionData = await sessionResponse.json()
              if (sessionData.github_token) {
                headers["Authorization"] = `token ${sessionData.github_token}`
                console.log("[RepoFetch] Using GitHub token from session")
              }
            }
          } catch (e) {
            console.warn("[RepoFetch] Could not retrieve token from session:", e)
          }
        }
        
        const response = await fetch(`/api/analysis/${analysisId}/repo`, {
          headers
        })

        if (!response.ok) {
          const errorText = await response.text()
          console.error(`Failed to fetch repo data: ${response.status} ${response.statusText}`, errorText)
          setLoadingRepo(false)
          return
        }

        const data = await response.json()
        console.log("Repo data fetched successfully:", data)
        setRepoData(data.repo)
        const fetchedBranches = data.branches || ["main", "develop", "staging", "master"]
        setBranches(fetchedBranches)

        // Set the base branch to the repo's default branch
        const actualDefaultBranch = data.repo?.default_branch || fetchedBranches[0] || "main"
        console.log(`[RepoFetch] Setting base branch to: ${actualDefaultBranch}`)
        setBaseBranch(actualDefaultBranch)

        // Auto-generate the source branch name
        const repoName = data.repo?.full_name || "repo"
        const generatedBranch = generateBranchName(repoName, analysisId)
        console.log(`[RepoFetch] Auto-generated source branch: ${generatedBranch}`)
        setSourceBranch(generatedBranch)

        // Update title with repo name
        const repoSlug = repoName.split("/").pop() || "repository"
        setTitle(`docs: add AI-generated documentation for ${repoSlug}`)
      } catch (error) {
        console.error("Failed to fetch repo data:", error)
      } finally {
        setLoadingRepo(false)
      }
    }
    
    fetchRepoData()
  }, [analysisId, session])

  // Check GitHub connection status using the hook
  useEffect(() => {
    setGithubConnected(githubConnectedFromHook)
  }, [githubConnectedFromHook])

  // Debug: Log all PR details when they change
  useEffect(() => {
    console.log("%c📋 PR PANEL DEBUG INFO", "font-size: 14px; font-weight: bold; color: #00aa00;")
    console.table({
      "analysisId": { status: analysisId ? "✓ SET" : "✗ MISSING", value: analysisId },
      "repoData": { status: repoData ? "✓ LOADED" : "✗ LOADING", value: repoData?.full_name },
      "title": { status: title ? "✓ SET" : "✗ EMPTY", length: title.length },
      "sourceBranch (new)": { status: sourceBranch ? "✓ SET" : "✗ EMPTY", value: sourceBranch, valid: branchValidation.valid },
      "baseBranch": { status: baseBranch ? "✓ SET" : "✗ EMPTY", value: baseBranch },
      "sameBranch": { status: isSameBranch ? "✗ ERROR" : "✓ OK", value: isSameBranch ? "Same branch!" : "Different" },
      "canSubmit": { status: canSubmit ? "✓ YES" : "✗ NO", value: canSubmit },
    })
  }, [analysisId, repoData, title, sourceBranch, baseBranch, branchValidation, isSameBranch, canSubmit])

  const totalAdditions = changedFiles.reduce((a, f) => a + f.additions, 0)
  const totalDeletions = changedFiles.reduce((a, f) => a + f.deletions, 0)

  const toggleReviewer = (id: string) => setSelectedReviewers((p) => (p.includes(id) ? p.filter((r) => r !== id) : [...p, id]))
  const toggleLabel = (id: string) => setSelectedLabels((p) => (p.includes(id) ? p.filter((l) => l !== id) : [...p, id]))
  const toggleCheck = (id: string) => setChecklist((p) => (p.includes(id) ? p.filter((c) => c !== id) : [...p, id]))
  const toggleFile = (path: string) =>
    setExpandedFiles((p) => {
      const next = new Set(p)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })

  // Regenerate branch name with a new unique ID
  const regenerateBranchName = () => {
    if (repoData) {
      const newBranch = `codeiq/docs-${repoData.full_name.split("/").pop()?.toLowerCase() || "repo"}-${generateShortId()}`
      setSourceBranch(newBranch)
    }
  }

  const handleSubmit = async () => {
    // Clear previous error
    setPrError(null)

    // Validation
    if (!canSubmit) {
      console.error("Form validation failed")
      return
    }

    if (isSameBranch) {
      setPrError({
        type: "same_branch",
        message: "Source and base branch cannot be the same. The PR would have no changes.",
      })
      setPrStatus("error")
      return
    }

    if (!branchValidation.valid) {
      setPrError({
        type: "invalid_branch_name",
        message: branchValidation.message || "Invalid branch name",
      })
      setPrStatus("error")
      return
    }

    if (!repoData) {
      setPrError({
        type: "repo_not_found",
        message: "Repository data could not be loaded. Please refresh and try again.",
      })
      setPrStatus("error")
      return
    }

    // Show preview instead of immediately submitting
    setShowPreview(true)
  }

  const handleConfirmAndSubmit = async () => {
    console.log("%c🚀 SUBMITTING SAFE PR REQUEST", "font-size: 14px; font-weight: bold; color: #00ff00;")

    // Safety check
    if (!repoData) {
      setPrError({
        type: "repo_not_found",
        message: "Repository data not found. Please try again.",
      })
      setPrStatus("error")
      setShowPreview(false)
      return
    }

    const prPayload = {
      analysisId,
      repo: repoData.full_name,
      title,
      description,
      sourceBranch,
      baseBranch,
      draft: isDraft,
      userId: session?.user?.id,
      commitMessage,
      linkedIssue: linkedIssue || undefined,
      reviewers: selectedReviewers,
      labels: selectedLabels,
      mergeStrategy,
      allowMaintainers,
      deleteOnMerge,
      // Note: files would be added here if we have actual documentation changes
    }

    console.log("%c📤 PAYLOAD BEING SENT TO BACKEND:", "font-weight: bold; color: #0099ff;")
    console.table(prPayload)

    setShowPreview(false)
    setPrStatus("loading")
    try {
      const response = await fetch("/api/analysis/create-pr-safe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(prPayload),
      })

      const data = await response.json()

      if (response.ok && data.success) {
        console.log("%c✅ PR CREATED SUCCESSFULLY", "font-weight: bold; color: #00ff00;")
        console.log("PR Details:", data)
        setPrUrl(data.html_url || data.pr_url)
        setPrStatus("success")
      } else {
        // Extract error details from response
        const errorType = data.error_type || data.details?.error_type || "unknown"
        const errorMessage = data.error || data.details?.message || "Failed to create pull request"
        const availableBranches = data.details?.available_branches || data.available_branches

        // Set error state for UI display instead of logging to console
        setPrError({
          type: errorType as PRErrorType,
          message: errorMessage,
          availableBranches: availableBranches,
        })
        setPrStatus("error")
      }
    } catch (error) {
      // Network or parsing error - show user-friendly message
      setPrError({
        type: "network_error",
        message: error instanceof Error ? error.message : "Unable to reach the server. Please check your connection and try again.",
      })
      setPrStatus("error")
    }
  }

  const handleCopyUrl = () => {
    navigator.clipboard.writeText(prUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleRetry = () => {
    setPrError(null)
    setPrStatus("idle")
  }

  if (prStatus === "success") {
    return <SuccessView prUrl={prUrl} onCopy={handleCopyUrl} copied={copied} onReset={() => setPrStatus("idle")} />
  }

  if (prStatus === "loading") {
    return <LoadingView />
  }

  if (prStatus === "error" && prError) {
    return (
      <ErrorView
        error={prError}
        onRetry={handleRetry}
        onRegenerateBranch={prError.type === "branch_exists" ? regenerateBranchName : undefined}
      />
    )
  }

  if (loadingRepo) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">Loading repository data...</p>
        </div>
      </div>
    )
  }

  if (!repoData) {
    return (
      <div className="flex items-center justify-center py-12">
        <Card className="border-destructive/50 max-w-md w-full">
          <CardContent className="pt-6 text-center">
            <p className="text-sm text-muted-foreground mb-2">Cannot create pull request</p>
            <p className="text-xs text-muted-foreground/70 mb-4">
              This analysis is not linked to a GitHub repository. 
            </p>
            <ul className="text-xs text-muted-foreground/70 text-left space-y-2 mb-4 bg-secondary/30 p-3 rounded">
              <li>✓ Go to Dashboard {"→"} New Analysis</li>
              <li>✓ Click "Connect GitHub"</li>
              <li>✓ Select a repository from your GitHub</li>
              <li>✓ Run the analysis</li>
              <li>✓ Then create pull requests from the results</li>
            </ul>
            <Button onClick={() => window.location.href = "/dashboard/analysis/new/github"} variant="default">
              Create New Analysis
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-0">
      <div className="flex items-start justify-between pb-4">
        <div className="flex items-center gap-3">
          <div
            className="w-11 h-11 rounded-xl flex items-center justify-center border"
            style={{ background: `${ACCENT_BG}18`, borderColor: `${ACCENT_BG}33` }}
          >
            <GitPullRequest className="w-5 h-5" style={{ color: ACCENT }} />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-foreground leading-tight">Open a Pull Request</h2>
            <p className="text-xs text-muted-foreground mt-0">Push AI-generated documentation back to your repository</p>
          </div>
        </div>
        <div className="flex items-center gap-2 pt-0.5">
          <div className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-green-500/20 border border-green-500/40">
            <span className="text-xs font-mono font-bold text-green-500">+{totalAdditions}</span>
          </div>
          <div className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-red-500/20 border border-red-500/40">
            <span className="text-xs font-mono font-bold text-red-500">-{totalDeletions}</span>
          </div>
          <Badge variant="outline" className="border-border text-muted-foreground font-normal">
            {changedFiles.length} files changed
          </Badge>
          {isDraft && (
            <Badge variant="outline" className="border-zinc-500/40 text-zinc-400 bg-zinc-500/10 font-normal">
              Draft
            </Badge>
          )}
          {githubConnected !== null && (
            <Badge 
              variant="outline" 
              className={githubConnected ? "border-green-500/40 text-green-400 bg-green-500/10 font-normal" : "border-red-500/40 text-red-400 bg-red-500/10 font-normal"}
            >
              {githubConnected ? "✓ GitHub Connected" : "✗ GitHub Not Connected"}
            </Badge>
          )}
        </div>
      </div>

      {githubConnected === false && (
        <div className="mb-4 p-4 rounded-xl border border-red-500/20 bg-red-500/5 flex items-start gap-3">
          <div className="mt-0.5 shrink-0">
            <div className="w-5 h-5 rounded-full bg-red-500/20 flex items-center justify-center">
              <span className="text-xs font-bold text-red-400">!</span>
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-red-400 mb-1">GitHub Not Connected</p>
            <p className="text-xs text-red-400/70 mb-3">
              You need to connect your GitHub account to create pull requests.
            </p>
            <Button 
              size="sm" 
              variant="outline" 
              className="border-red-500/40 text-red-400 hover:bg-red-500/10"
              onClick={() => window.location.href = "/dashboard"}
            >
              Go to Dashboard
            </Button>
          </div>
        </div>
      )}

      {/* Branch validation warning */}
      {isSameBranch && (
        <div className="mb-4 p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span className="text-sm text-amber-400">Source and base branch cannot be the same</span>
        </div>
      )}

      {!branchValidation.valid && sourceBranch && (
        <div className="mb-4 p-3 rounded-lg border border-red-500/30 bg-red-500/10 flex items-center gap-2">
          <XCircle className="w-4 h-4 text-red-400 shrink-0" />
          <span className="text-sm text-red-400">{branchValidation.message}</span>
        </div>
      )}

      <div className="mb-4 flex items-center gap-3 px-4 py-3 rounded-xl border border-border bg-card">
        {/* Source branch (NEW - will be created) */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 min-w-0">
          <GitBranch className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          {isEditingBranch ? (
            <Input
              value={sourceBranch}
              onChange={(e) => setSourceBranch(e.target.value)}
              onBlur={() => setIsEditingBranch(false)}
              onKeyDown={(e) => e.key === "Enter" && setIsEditingBranch(false)}
              className="h-6 text-sm font-mono bg-transparent border-none p-0 focus-visible:ring-0 w-[200px]"
              autoFocus
            />
          ) : (
            <span className="text-sm font-mono text-foreground truncate max-w-[200px]">{sourceBranch}</span>
          )}
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide bg-emerald-500/20 text-emerald-400">
            new
          </span>
          <button
            onClick={() => setIsEditingBranch(!isEditingBranch)}
            className="p-0.5 rounded hover:bg-emerald-500/20 transition-colors"
            title="Edit branch name"
          >
            <Edit3 className="w-3 h-3 text-emerald-400" />
          </button>
        </div>
        <div className="flex items-center gap-2 text-muted-foreground">
          <div className="h-px w-4 bg-border" />
          <GitMerge className="w-4 h-4 shrink-0" style={{ color: ACCENT }} />
          <div className="h-px w-4 bg-border" />
        </div>
        {/* Base branch */}
        <div
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border"
          style={{ background: `${ACCENT_BG}0f`, borderColor: `${ACCENT_BG}33` }}
        >
          <GitBranch className="w-3.5 h-3.5 shrink-0" style={{ color: ACCENT }} />
          <span className="text-sm font-mono text-foreground">{baseBranch}</span>
          <span
            className="text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide"
            style={{ background: `${ACCENT_BG}20`, color: ACCENT }}
          >
            base
          </span>
        </div>
        <div className="ml-auto flex items-center gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <GitCommit className="w-3.5 h-3.5" />6 commits ahead
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />No conflicts
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <ConfigSection 
            icon={<FileText className="w-3.5 h-3.5" />} 
            title="Pull Request Details"
            showToggle={true}
            isPreview={prContentPreview}
            onToggle={() => setPrContentPreview(!prContentPreview)}
          >
            {!prContentPreview ? (
              <div className="space-y-4 -mx-3 -mb-2.5 -mt-2.5">
                <div className="px-3 py-3 space-y-4">
                  <div>
                    <label className="text-xs font-semibold text-foreground/70 uppercase tracking-wider block mb-1.5">Title</label>
                    <Input
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      className="h-8 text-sm bg-yellow-400/5 border border-yellow-700/25 focus-visible:ring-1 font-medium focus:bg-yellow-400/8"
                      style={{ "--ring": ACCENT } as CSSProperties}
                      disabled={prStatus === "loading"}
                      placeholder="Describe your changes..."
                    />
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-foreground/70 uppercase tracking-wider block mb-1.5">Description</label>
                    <Textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      rows={10}
                      className="text-xs font-mono bg-zinc-950 border border-zinc-800/60 text-zinc-100 resize-none leading-relaxed focus-visible:ring-1 focus:border-zinc-700/60"
                      disabled={prStatus === "loading"}
                      placeholder="## Summary\n\nDescribe what this PR does..."
                    />
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-foreground/70 uppercase tracking-wider block mb-1.5">Commit Message</label>
                    <Input
                      value={commitMessage}
                      onChange={(e) => setCommitMessage(e.target.value)}
                      className="h-8 text-sm bg-yellow-400/5 border border-yellow-700/25 focus-visible:ring-1 font-mono focus:bg-yellow-400/8"
                      disabled={prStatus === "loading"}
                      placeholder="docs: Add AI-generated documentation"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-foreground/70 uppercase tracking-wider block mb-1.5">Link Issue (optional)</label>
                    <Input
                      value={linkedIssue}
                      onChange={(e) => setLinkedIssue(e.target.value)}
                      className="h-8 text-sm bg-yellow-400/5 border border-yellow-700/25 focus-visible:ring-1 font-mono focus:bg-yellow-400/8"
                      disabled={prStatus === "loading"}
                      placeholder="123 or owner/repo#123"
                    />
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-4 -mx-3 -mb-2.5 -mt-2.5">
                <div className="px-3 py-3 space-y-4">
                  <div>
                    <div className="text-xs font-semibold text-foreground/70 uppercase tracking-wider mb-2">Title</div>
                    <div className="p-2 rounded-lg bg-secondary/40 border border-border/50 flex items-center min-h-8">
                      <p className="text-sm font-medium text-foreground whitespace-pre-wrap break-words">{title || <span className="text-muted-foreground/50 italic">No title</span>}</p>
                    </div>
                  </div>

                  <div>
                    <div className="text-xs font-semibold text-foreground/70 uppercase tracking-wider mb-2">Description</div>
                    <div className="p-4 rounded-lg bg-background/50 border border-border/50 max-h-96 overflow-y-auto">
                      <div className="text-base text-foreground leading-relaxed break-words font-medium">
                        {description ? (
                          description.split('\n').map((line, i) => {
                            if (line.startsWith('## ')) {
                              return <h3 key={i} className="text-lg font-bold mt-4 mb-3">{line.replace('## ', '')}</h3>
                            } else if (line.startsWith('# ')) {
                              return <h2 key={i} className="text-2xl font-bold mt-4 mb-3">{line.replace('# ', '')}</h2>
                            } else if (line.startsWith('- ')) {
                              return <li key={i} className="ml-6 text-base font-medium">{line.replace('- ', '')}</li>
                            } else if (line.trim() === '') {
                              return <div key={i} className="h-3"></div>
                            } else {
                              return <p key={i} className="text-foreground text-base font-medium">{line}</p>
                            }
                          })
                        ) : (
                          <span className="text-muted-foreground/50 italic">No description</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div>
                    <div className="text-xs font-semibold text-foreground/70 uppercase tracking-wider mb-2">Commit Message</div>
                    <div className="p-2 rounded-lg bg-secondary/40 border border-border/50 flex items-center min-h-8">
                      <p className="text-sm font-mono text-foreground">{commitMessage}</p>
                    </div>
                  </div>

                  <div>
                    <div className="text-xs font-semibold text-foreground/70 uppercase tracking-wider mb-2">Link Issue</div>
                    <div className="p-2 rounded-lg bg-secondary/40 border border-border/50 flex items-center min-h-8">
                      <p className="text-sm font-mono text-foreground">{linkedIssue || <span className="text-muted-foreground/50 italic">Not set</span>}</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </ConfigSection>
        </div>

        <div className="lg:col-span-1">
          <Card className="border-border">
            <CardContent className="p-3 space-y-3">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    <FileCode className="w-3.5 h-3.5" />Files Changed
                  </div>
                  <Dialog>
                    <DialogTrigger asChild>
                      <Button variant="ghost" size="sm" className="h-6 px-2 text-[10px] text-muted-foreground hover:text-foreground">
                        <Eye className="w-3 h-3 mr-1" />View
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="overflow-hidden flex flex-col bg-background border-border max-h-[85vh]" style={{ maxWidth: '600px', width: '90vw' }}>
                      <DialogTitle className="sr-only">File Changes</DialogTitle>
                      <div className="px-6 py-4 border-b border-border shrink-0 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <h2 className="text-base font-semibold text-foreground">FILE CHANGES</h2>
                          <Badge variant="outline" className="text-xs font-normal">{changedFiles.length} files</Badge>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className="text-sm font-mono text-green-500 font-semibold">+{totalAdditions}</span>
                          <span className="text-sm font-mono text-red-500 font-semibold">-{totalDeletions}</span>
                        </div>
                      </div>
                      <ScrollArea className="flex-1 pr-4">
                        <div className="space-y-2 py-4">
                          {changedFiles.map((file) => (
                            <div key={file.path} className="rounded-lg border border-border overflow-hidden">
                              <button
                                onClick={() => toggleFile(file.path)}
                                className="w-full flex items-center justify-between px-4 py-3 bg-card hover:bg-secondary/30 transition-colors"
                              >
                                <div className="flex items-center gap-3">
                                  {expandedFiles.has(file.path) ? (
                                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                                  ) : (
                                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                                  )}
                                  <FileCode className="w-4 h-4 text-muted-foreground" />
                                  <span className="text-sm font-mono text-foreground">{file.path}</span>
                                </div>
                                <div className="flex items-center gap-3">
                                  <span className="text-sm font-mono text-green-500 font-semibold">+{file.additions}</span>
                                  {file.deletions > 0 && <span className="text-sm font-mono text-red-500 font-semibold">-{file.deletions}</span>}
                                  <Badge
                                    variant="outline"
                                    className={cn(
                                      "text-[10px] font-medium",
                                      file.status === "added" && "border-green-500/50 text-green-500 bg-green-500/10",
                                      file.status === "modified" && "border-zinc-500/50 text-zinc-400"
                                    )}
                                  >
                                    {file.status}
                                  </Badge>
                                </div>
                              </button>

                              {expandedFiles.has(file.path) && (
                                <div className="border-t border-border bg-zinc-950">
                                  <div className="font-mono text-xs">
                                    {file.diff.map((line, idx) => (
                                      <div
                                        key={idx}
                                        className={cn("flex", line.type === "added" && "bg-green-900/40", line.type === "removed" && "bg-red-900/40")}
                                      >
                                        <span
                                          className={cn(
                                            "w-12 text-right pr-2 select-none border-r border-zinc-800 shrink-0 py-0.5",
                                            line.type === "added" && "text-green-500 bg-green-900/20",
                                            line.type === "removed" && "text-red-500 bg-red-900/20",
                                            line.type === "context" && "text-zinc-600"
                                          )}
                                        >
                                          {line.type === "added" ? "+" : line.type === "removed" ? "-" : " "}
                                        </span>
                                        <span
                                          className={cn(
                                            "flex-1 px-4 py-0.5",
                                            line.type === "added" && "text-green-400",
                                            line.type === "removed" && "text-red-400",
                                            line.type === "context" && "text-zinc-400"
                                          )}
                                        >
                                          {line.content || " "}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </ScrollArea>
                    </DialogContent>
                  </Dialog>
                </div>
                <div className="space-y-1">
                  {changedFiles.slice(0, 3).map((file) => (
                    <div key={file.path} className="flex items-center justify-between p-2 rounded-md bg-secondary/30 hover:bg-secondary/50 transition-colors">
                      <div className="flex items-center gap-2 min-w-0">
                        <FileCode className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                        <span className="text-xs font-mono text-foreground truncate">{file.path}</span>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className="text-xs font-mono text-green-500 font-semibold">+{file.additions}</span>
                        <span className="text-xs font-mono text-red-500 font-semibold">-{file.deletions}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <Separator className="bg-border" />

              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    <GitBranch className="w-3.5 h-3.5" />Branches
                  </div>
                  <button
                    onClick={regenerateBranchName}
                    className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1"
                    title="Generate new branch name"
                  >
                    <RefreshCw className="w-3 h-3" />
                    Regenerate
                  </button>
                </div>
                <div className="space-y-2">
                  <div>
                    <label className="text-[10px] text-muted-foreground block mb-1">
                      Source Branch <span className="text-emerald-400">(new)</span>
                    </label>
                    <Input
                      value={sourceBranch}
                      onChange={(e) => setSourceBranch(e.target.value)}
                      className={cn(
                        "h-7 text-xs font-mono bg-background border-border",
                        !branchValidation.valid && sourceBranch && "border-red-500/50",
                        isSameBranch && "border-amber-500/50"
                      )}
                      disabled={prStatus === "loading"}
                      placeholder="codeiq/docs-repo-abc123"
                    />
                    {!branchValidation.valid && sourceBranch && (
                      <span className="text-[10px] text-red-400 mt-0.5 block">{branchValidation.message}</span>
                    )}
                  </div>
                  <div>
                    <label className="text-[10px] text-muted-foreground block mb-1">Base Branch</label>
                    <Select value={baseBranch} onValueChange={setBaseBranch} disabled={prStatus === "loading"}>
                      <SelectTrigger className="h-7 text-xs bg-background border-border">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {branches.map((branch) => (
                          <SelectItem key={branch} value={branch}>{branch}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>

              <Separator className="bg-border" />

              <div>
                <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  <GitMerge className="w-3.5 h-3.5" />Merge Strategy
                </div>
                <Select value={mergeStrategy} onValueChange={setMergeStrategy} disabled={prStatus === "loading"}>
                  <SelectTrigger className="h-7 text-xs bg-background border-border">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="merge" className="text-xs">Merge commit</SelectItem>
                    <SelectItem value="squash" className="text-xs">Squash and merge</SelectItem>
                    <SelectItem value="rebase" className="text-xs">Rebase and merge</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Separator className="bg-border" />

              <div>
                <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  <User className="w-3.5 h-3.5" />Reviewers
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {availableReviewers.map((reviewer) => (
                    <button
                      key={reviewer.id}
                      onClick={() => toggleReviewer(reviewer.id)}
                      className={cn(
                        "px-2 py-1 rounded text-[11px] font-medium transition-colors border",
                        selectedReviewers.includes(reviewer.id)
                          ? `${reviewer.color} border-current`
                          : "bg-secondary border-border text-muted-foreground hover:border-foreground/20"
                      )}
                    >
                      {reviewer.name.split(" ")[0]}
                    </button>
                  ))}
                </div>
              </div>

              <Separator className="bg-border" />

              <div>
                <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  <Tag className="w-3.5 h-3.5" />Labels
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {availableLabels.map((label) => (
                    <button
                      key={label.id}
                      onClick={() => toggleLabel(label.id)}
                      className={cn(
                        "px-2 py-1 rounded text-[11px] font-medium transition-colors border",
                        selectedLabels.includes(label.id)
                          ? `${label.color} border-current`
                          : "bg-secondary border-border text-muted-foreground hover:border-foreground/20"
                      )}
                    >
                      {label.name}
                    </button>
                  ))}
                </div>
              </div>

              <Separator className="bg-border" />

              <div>
                <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  <Settings2 className="w-3.5 h-3.5" />Options
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between py-1">
                    <label className="text-xs text-foreground">Draft PR</label>
                    <Switch checked={isDraft} onCheckedChange={setIsDraft} disabled={prStatus === "loading"} />
                  </div>
                  <div className="flex items-center justify-between py-1">
                    <label className="text-xs text-foreground">Allow maintainers</label>
                    <Switch checked={allowMaintainers} onCheckedChange={setAllowMaintainers} disabled={prStatus === "loading"} />
                  </div>
                  <div className="flex items-center justify-between py-1">
                    <label className="text-xs text-foreground">Delete on merge</label>
                    <Switch checked={deleteOnMerge} onCheckedChange={setDeleteOnMerge} disabled={prStatus === "loading"} />
                  </div>
                </div>
              </div>


            </CardContent>
          </Card>
        </div>
      </div>

      <div className="flex gap-2 pt-4 mt-4 w-full">
        <Button
          onClick={handleSubmit}
          disabled={prStatus === "loading" || githubConnected === false || !canSubmit}
          size="lg"
          className={cn(
            "flex-1 h-12 px-6 rounded-lg font-semibold transition-all duration-300 flex items-center justify-center gap-2",
            canSubmit && githubConnected !== false
              ? "bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white shadow-lg shadow-emerald-600/40 hover:shadow-emerald-600/60 hover:scale-[1.02] active:scale-95"
              : "bg-gradient-to-r from-zinc-700 to-zinc-600 text-zinc-400 shadow-none cursor-not-allowed opacity-60"
          )}
        >
          {prStatus === "loading" ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Creating PR...</span>
            </>
          ) : (
            <>
              <GitPullRequest className="w-5 h-5" />
              <span>Create Pull Request</span>
            </>
          )}
        </Button>
      </div>

      {/* Validation summary */}
      {!canSubmit && (
        <div className="mt-2 text-xs text-muted-foreground">
          {isSameBranch && <span className="text-amber-400">Source and base branches must be different. </span>}
          {!branchValidation.valid && sourceBranch && <span className="text-red-400">{branchValidation.message}. </span>}
          {!sourceBranch && <span>Enter a source branch name. </span>}
        </div>
      )}

      {/* Preview Dialog */}
      <Dialog open={showPreview} onOpenChange={setShowPreview}>
        <DialogContent className="overflow-hidden flex flex-col bg-background border-border max-h-[95vh]" style={{ maxWidth: '65vw', width: '65vw' }}>
          <DialogHeader className="border-b border-border pb-2 shrink-0">
            <DialogTitle className="text-base font-bold flex items-center gap-2">
              <Eye className="w-4 h-4 text-emerald-400" />
              Review Pull Request Summary
            </DialogTitle>
          </DialogHeader>

          <ScrollArea className="flex-1 pr-4 pb-0">
            <div className="grid grid-cols-2 gap-3 py-3 pb-4 px-3">
              {/* LEFT COLUMN */}
              <div className="space-y-1.5">
                {/* Repository Info */}
                <div>
                  <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-0.5">Repository</h3>
                  <div className="flex items-center gap-1 p-2 bg-card/90 rounded-lg border border-border/80 hover:border-foreground/30 transition-colors">
                    <span className="text-xs font-mono text-foreground font-semibold">{repoData?.full_name}</span>
                  </div>
                </div>

                {/* Branch Info */}
                <div>
                  <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-0.5">Branches</h3>
                  <div className="flex items-center gap-1 p-2 bg-card/90 rounded-lg border border-border/80 hover:border-foreground/30 transition-colors">
                    <span className="text-xs font-mono text-foreground font-semibold">{sourceBranch}</span>
                    <span className="text-border/60">→</span>
                    <span className="text-xs font-mono text-foreground">{baseBranch}</span>
                    <span className="text-xs text-foreground/70 bg-amber-500/10 px-1 py-0.5 rounded font-semibold">{mergeStrategy}</span>
                  </div>
                </div>

                {/* Commit Message */}
                <div>
                  <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-0.5">Commit</h3>
                  <div className="p-2 bg-card/90 rounded-lg border border-border/80 hover:border-foreground/30 transition-colors font-mono text-xs text-foreground break-words">
                    {commitMessage}
                  </div>
                </div>

                {/* Files & Changes */}
                <div>
                  <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-0.5">Changes</h3>
                  <div className="p-2 bg-card/90 rounded-lg border border-border/80 hover:border-foreground/30 transition-colors">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-foreground font-semibold">{changedFiles.length} files changed</span>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-mono text-green-400 font-semibold">+{totalAdditions}</span>
                        <span className="text-xs font-mono text-red-400 font-semibold">-{totalDeletions}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* RIGHT COLUMN - PR CONTENT */}
              <div>
                <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-0.5">PR Content</h3>
                <div className="space-y-1.5 p-2.5 bg-card rounded-lg border border-border/80 hover:border-foreground/30 transition-colors sticky top-0">
                  <div>
                    <p className="text-xs text-muted-foreground mb-0.5 font-semibold">Title</p>
                    <p className="text-xs font-semibold text-foreground leading-snug">{title}</p>
                  </div>
                  <Separator className="bg-border/20" />
                  <div>
                    <p className="text-xs text-muted-foreground mb-0.5 font-semibold">Description</p>
                    <div className="text-xs text-foreground/80 whitespace-pre-wrap font-mono bg-card/90 p-1.5 rounded max-h-48 overflow-y-auto border border-border/60">
                      {description}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </ScrollArea>

          <div className="border-t border-border pt-4 pb-4 px-4 flex gap-3 shrink-0 bg-gradient-to-t from-background/98 to-background/90 backdrop-blur-md sticky bottom-0">
            <Button
              onClick={() => setShowPreview(false)}
              variant="outline"
              size="lg"
              className="flex-1 h-11 px-4 rounded-lg border-border/80 bg-zinc-500/10 hover:bg-zinc-500/20 text-foreground font-medium transition-all duration-200 hover:border-border/60"
            >
              ← Back to Edit
            </Button>
            <Button
              onClick={handleConfirmAndSubmit}
              disabled={prStatus === "loading"}
              size="lg"
              className="flex-1 h-11 px-4 rounded-lg bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white shadow-lg shadow-emerald-600/40 hover:shadow-emerald-600/60 font-semibold transition-all duration-300 hover:scale-[1.02] active:scale-95 disabled:opacity-70 disabled:cursor-wait disabled:hover:scale-100"
            >
              {prStatus === "loading" ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Creating PR...</span>
                </>
              ) : (
                <>
                  <GitPullRequest className="w-5 h-5" />
                  <span>Confirm & Create</span>
                </>
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function SuccessView({
  prUrl,
  onCopy,
  copied,
  onReset,
}: {

  prUrl: string
  onCopy: () => void
  copied: boolean
  onReset: () => void
}) {
  return (
    <div className="w-full bg-gradient-to-br from-emerald-50/5 via-background to-emerald-50/5 flex flex-col items-center justify-start px-4 pt-4 pb-8 min-h-screen">
      {/* Background accent elements */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-64 bg-emerald-500/5 rounded-full blur-3xl -z-10" />
      <div className="absolute bottom-0 right-0 w-64 h-64 bg-emerald-500/3 rounded-full blur-3xl -z-10" />

      <div className="w-full max-w-xl">
        {/* Success icon */}
        <div className="flex justify-center mb-6">
          <div className="relative w-16 h-16">
            <div className="absolute inset-0 bg-emerald-500/20 rounded-full blur-lg animate-pulse" />
            <div className="relative flex items-center justify-center w-full h-full rounded-full bg-gradient-to-br from-emerald-500/25 to-emerald-600/15 border border-emerald-500/30 shadow-lg shadow-emerald-500/20">
              <CheckCircle2 className="w-8 h-8 text-emerald-500" />
            </div>
          </div>
        </div>

        {/* Main heading */}
        <h1 className="text-3xl font-bold text-center text-foreground mb-2">
          Pull Request Created!
        </h1>

        {/* Subheading */}
        <p className="text-sm text-center text-muted-foreground mb-8 max-w-lg mx-auto">
          Your AI-generated documentation has been successfully pushed to your repository. The pull request is ready for review.
        </p>

        {/* PR URL Card */}
        <div className="bg-card border border-emerald-500/20 rounded-xl p-5 mb-8 shadow-lg shadow-emerald-500/5">
          <div className="mb-2 flex items-center gap-2">
            <GitPullRequest className="w-4 h-4 text-emerald-500" />
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Pull Request URL</span>
          </div>
          <div className="bg-secondary/40 rounded-lg p-3 border border-border/50 mb-3">
            <code className="text-xs font-mono text-foreground break-all">{prUrl}</code>
          </div>
          <p className="text-xs text-muted-foreground">
            Click "Copy URL" to copy this link, or visit it directly.
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex flex-col sm:flex-row gap-2 justify-center">
          <Button 
            onClick={onCopy} 
            className="sm:flex-1 h-10 font-semibold text-sm bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/30 transition-all"
          >
            {copied ? (
              <>
                <Check className="w-4 h-4 mr-2" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="w-4 h-4 mr-2" />
                Copy URL
              </>
            )}
          </Button>
          <Button 
            onClick={onReset} 
            variant="outline"
            className="sm:flex-1 h-10 font-semibold text-sm border-primary/40 hover:bg-primary/10 hover:border-primary/60"
          >
            <GitPullRequest className="w-4 h-4 mr-2" />
            Create Another
          </Button>
        </div>

        {/* Footer info */}
        <div className="mt-8 pt-6 border-t border-border/50 flex flex-col sm:flex-row gap-4 justify-center text-center sm:text-left">
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-0.5">Next steps</p>
            <p className="text-xs text-muted-foreground">Review the changes and merge when ready.</p>
          </div>
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-0.5">Need help?</p>
            <p className="text-xs text-muted-foreground">Check GitHub for collaboration tools.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

function ErrorView({
  error,
  onRetry,
  onRegenerateBranch,
}: {
  error: PRError
  onRetry: () => void
  onRegenerateBranch?: () => void
}) {
  const errorStyle = getErrorStyle(error.type)
  const ErrorIcon = errorStyle.icon

  return (
    <div className="flex items-center justify-center py-12">
      <Card className={cn("max-w-md w-full shadow-lg border", errorStyle.bgColor)}>
        <CardContent className="pt-8 text-center">
          <div className={cn("mx-auto w-14 h-14 rounded-full flex items-center justify-center mb-4", errorStyle.bgColor)}>
            <ErrorIcon className={cn("w-7 h-7", errorStyle.color)} />
          </div>
          <h3 className="text-xl font-bold text-foreground mb-2">Failed to create PR</h3>
          <p className={cn("text-sm mb-6 font-medium", errorStyle.color)}>{error.message}</p>

          {/* Contextual help based on error type */}
          {error.type === "branch_exists" && (
            <div className="bg-secondary/50 rounded-lg p-3 mb-6 text-left text-xs text-muted-foreground">
              <p className="mb-2">The branch name you chose already exists in the repository.</p>
              <p>You can:</p>
              <ul className="list-disc list-inside mt-1 space-y-0.5">
                <li>Click "Regenerate Branch" to generate a new unique name</li>
                <li>Or go back and manually edit the branch name</li>
              </ul>
            </div>
          )}

          {error.type === "no_write_access" && (
            <div className="bg-secondary/50 rounded-lg p-3 mb-6 text-left text-xs text-muted-foreground">
              <p>You don't have write access to this repository. Please:</p>
              <ul className="list-disc list-inside mt-1 space-y-0.5">
                <li>Ask the repository owner for write access</li>
                <li>Or fork the repository and create the PR from your fork</li>
              </ul>
            </div>
          )}

          {error.type === "token_expired" && (
            <div className="bg-secondary/50 rounded-lg p-3 mb-6 text-left text-xs text-muted-foreground">
              <p>Your GitHub session has expired. Please reconnect your GitHub account from the dashboard.</p>
            </div>
          )}

          {error.type === "base_branch_not_found" && (
            <div className="bg-secondary/50 rounded-lg p-3 mb-6 text-left text-xs text-muted-foreground">
              <p className="mb-2">The base branch doesn't exist in this repository.</p>
              {error.availableBranches && error.availableBranches.length > 0 ? (
                <>
                  <p className="mb-1 font-medium">Available branches:</p>
                  <ul className="list-disc list-inside space-y-0.5">
                    {error.availableBranches.map((branch) => (
                      <li key={branch}>{branch}</li>
                    ))}
                  </ul>
                  <p className="mt-2">Please go back and select a valid branch from the dropdown.</p>
                </>
              ) : (
                <p>Please go back and select a valid base branch from the dropdown.</p>
              )}
            </div>
          )}

          <div className="flex gap-2 flex-wrap">
            {error.type === "branch_exists" && onRegenerateBranch && (
              <Button
                onClick={() => {
                  onRegenerateBranch()
                  onRetry()
                }}
                variant="outline"
                size="sm"
                className="flex-1 min-w-[140px] border-amber-500/40 hover:bg-amber-500/10 hover:border-amber-500/60 font-medium text-xs sm:text-sm"
              >
                <RefreshCw className="w-3.5 h-3.5 mr-1.5 shrink-0" />
                <span className="truncate">Regenerate</span>
              </Button>
            )}
            {error.type === "token_expired" && (
              <Button
                onClick={() => window.location.href = "/dashboard"}
                variant="outline"
                size="sm"
                className="flex-1 min-w-[120px] border-orange-500/40 hover:bg-orange-500/10 hover:border-orange-500/60 font-medium text-xs sm:text-sm"
              >
                <ExternalLink className="w-3.5 h-3.5 mr-1.5 shrink-0" />
                <span className="truncate">Dashboard</span>
              </Button>
            )}
            <Button
              onClick={onRetry}
              variant="outline"
              size="sm"
              className="flex-1 min-w-[100px] border-primary/40 hover:bg-primary/10 hover:border-primary/60 font-medium text-xs sm:text-sm"
            >
              Try Again
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function LoadingView() {
  return (
    <div className="flex items-center justify-center py-24">
      <div className="text-center">
        {/* Clean animated circle loader */}
        <div className="mx-auto mb-8 relative w-24 h-24">
          {/* Outer rotating ring */}
          <div className="absolute inset-0 rounded-full" style={{
            border: '3px solid transparent',
            borderTop: `3px solid oklch(0.72 0.22 80)`,
            animation: 'spin 1.5s linear infinite',
          }} />
          
          {/* Inner pulsing circle */}
          <div className="absolute inset-4 rounded-full" style={{
            background: `oklch(0.72 0.22 80)`,
            opacity: 0.2,
            animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
          }} />
          
          {/* Center circle */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-8 h-8 rounded-full" style={{
              background: `oklch(0.72 0.22 80)`,
              opacity: 0.15,
            }} />
          </div>
        </div>

        <style>{`
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
          @keyframes pulse {
            0%, 100% { transform: scale(1); opacity: 0.2; }
            50% { transform: scale(1.1); opacity: 0.3; }
          }
        `}</style>

        <h3 className="text-2xl font-bold text-foreground mb-2">Creating pull request</h3>
        <p className="text-sm text-muted-foreground max-w-sm">
          Setting up your branch, preparing changes, and creating the pull request on GitHub...
        </p>
      </div>
    </div>
  )
}

function ConfigSection({
  icon,
  title,
  optional,
  children,
  showToggle,
  isPreview,
  onToggle,
}: {
  icon: ReactNode
  title: string
  optional?: boolean
  children: ReactNode
  showToggle?: boolean
  isPreview?: boolean
  onToggle?: () => void
}) {
  return (
    <Card className="border-border/80 bg-card/70 backdrop-blur-sm shadow-sm">
      <CardHeader className="pb-0 pt-0 px-3 border-b border-border/50 -my-1">
        <div className="flex items-center justify-between">
          <CardTitle className="text-2xl font-semibold text-foreground flex items-center gap-2">
            {title}
            {optional && <span className="font-normal normal-case tracking-normal opacity-50 ml-0.5 text-muted-foreground">- optional</span>}
          </CardTitle>
          {showToggle && onToggle && (
            <div className="flex items-center gap-2 bg-secondary/40 p-1.5 rounded-full">
              <Button
                variant="ghost"
                size="sm"
                onClick={onToggle}
                className={cn(
                  "h-7 px-3 text-sm font-medium rounded-full transition-colors",
                  !isPreview 
                    ? "bg-background/90 text-foreground border border-border/50 shadow-sm" 
                    : "text-foreground/60 hover:text-foreground"
                )}
              >
                <Edit3 className="w-4 h-4 mr-1.5" />
                Edit
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={onToggle}
                className={cn(
                  "h-7 px-3 text-sm font-medium rounded-full transition-colors",
                  isPreview 
                    ? "bg-background/90 text-foreground border border-border/50 shadow-sm" 
                    : "text-foreground/60 hover:text-foreground"
                )}
              >
                <Eye className="w-4 h-4 mr-1.5" />
                Preview
              </Button>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent className="pb-2.5 px-3 pt-0 -mt-1">{children}</CardContent>
    </Card>
  )
}
