"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Github,
  ExternalLink,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Download,
  Star,
  Search,
  RefreshCw,
  Lock,
  Globe,
  Code2,
} from "lucide-react"
import { useGitHub } from "@/hooks/use-github"

interface GitHubRepositorySelectorProps {
  onRepositorySelected?: (repo: any) => void
  onRepositoryCloned?: (repoPath: string) => void
  embedded?: boolean
  onClose?: () => void
  analysisMode?: "full" | "graphs"
}

export function GitHubRepositorySelector({
  onRepositorySelected,
  onRepositoryCloned,
  embedded = false,
  onClose,
  analysisMode = "full",
}: GitHubRepositorySelectorProps) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedRepo, setSelectedRepo] = useState<any | null>(null)
  const [isCloning, setIsCloning] = useState(false)
  const [cloningRepoId, setCloningRepoId] = useState<number | null>(null)
  const [installingRepoId, setInstallingRepoId] = useState<number | null>(null)
  const lastRefreshRef = useRef(0)

  const {
    repositories,
    repoLoading: gitHubLoading,
    error: gitHubError,
    isConnected,
    profile,
    initiateGitHubAuth,
    fetchRepositories,
    getAppInstallUrl,
  } = useGitHub()

  const isViewOpen = embedded || open

  const refreshRepositories = useCallback(async () => {
    const now = Date.now()
    // Throttle refetches to avoid spinner loops from rapid focus/visibility events.
    if (now - lastRefreshRef.current < 2000) return
    lastRefreshRef.current = now
    await fetchRepositories({ silent: true })
  }, [fetchRepositories])

  // Fetch repos when view opens and user is connected.
  useEffect(() => {
    if (isViewOpen && isConnected) {
      if (repositories.length === 0) {
        fetchRepositories()
      } else {
        refreshRepositories()
      }
    }
  }, [isViewOpen, isConnected, repositories.length, fetchRepositories, refreshRepositories])

  // Refresh installation status when user returns from GitHub install flow.
  useEffect(() => {
    if (!isViewOpen || !isConnected) return

    const onFocus = () => {
      refreshRepositories()
    }

    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        refreshRepositories()
      }
    }

    window.addEventListener("focus", onFocus)
    document.addEventListener("visibilitychange", onVisibilityChange)

    return () => {
      window.removeEventListener("focus", onFocus)
      document.removeEventListener("visibilitychange", onVisibilityChange)
    }
  }, [isViewOpen, isConnected, refreshRepositories])

  const filteredRepos = repositories.filter((repo) =>
    repo.full_name.toLowerCase().includes(searchQuery.toLowerCase())
  )
  const installedCount = repositories.filter((repo) => repo.app_installed).length

  useEffect(() => {
    if (filteredRepos.length === 0) {
      setSelectedRepo(null)
      return
    }

    if (!selectedRepo) {
      setSelectedRepo(filteredRepos[0])
      return
    }

    const stillVisible = filteredRepos.some(
      (repo) => repo.github_repo_id === selectedRepo.github_repo_id
    )
    if (!stillVisible) {
      setSelectedRepo(filteredRepos[0])
    }
  }, [filteredRepos, selectedRepo])

  const handleInstallApp = async (repo: any) => {
    const popup = window.open("about:blank", "_blank")
    try {
      setInstallingRepoId(repo.github_repo_id)
      const url = await getAppInstallUrl(repo.github_repo_id)
      if (url) {
        if (popup) {
          popup.location.href = url
        } else {
          window.location.href = url
        }

        // Quick refresh in case user installs rapidly and returns.
        setTimeout(() => {
          refreshRepositories()
        }, 1500)
      } else {
        if (popup) popup.close()
        alert("Could not generate install URL. Please try again.")
      }
    } catch (err) {
      if (popup) popup.close()
      console.error("Failed to get install URL:", err)
      alert("Install flow failed. Please check GitHub connection and try again.")
    } finally {
      setInstallingRepoId(null)
    }
  }

  const handleCloneRepository = async (repo: any) => {
    try {
      setIsCloning(true)
      setCloningRepoId(repo.github_repo_id)

      // Use the frontend repos proxy route; session user id is injected server-side.
      const response = await fetch("/api/repos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: repo.clone_url,
        }),
      })

      if (!response.ok) {
        let errorMessage = "Failed to clone repository"
        try {
          const err = await response.json()
          errorMessage = err.detail || err.error || errorMessage
        } catch {
          // keep default message
        }
        throw new Error(errorMessage)
      }

      const data = await response.json()

      onRepositoryCloned?.(data.repo_path)
      onRepositorySelected?.(repo)

      // Navigate to analysis page
      const modeParam = analysisMode === "graphs" ? "?mode=graphs" : ""
      router.push(`/dashboard/analysis/${data.repo_id}/pipeline${modeParam}`)
      if (!embedded) {
        setOpen(false)
      }
    } catch (err) {
      console.error("Clone failed:", err)
      alert(err instanceof Error ? err.message : "Failed to clone repository. Please try again.")
    } finally {
      setIsCloning(false)
      setCloningRepoId(null)
    }
  }

  const handleClose = () => {
    if (embedded) {
      onClose?.()
      return
    }
    setOpen(false)
  }

  const selectorPanel = (
    <>
      <div className="px-4 py-2 bg-transparent">
        <div className="flex items-center justify-between gap-3">
          <h2 className="flex items-center gap-2 text-xl font-semibold text-[#24292f]">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[#24292f] text-white">
              <Github className="w-3 h-3" />
            </span>
            Select GitHub Repository
          </h2>
          {isConnected && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-black px-3 py-1 text-xs font-medium text-white">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Connected
            </span>
          )}
        </div>
        <p className="text-xs text-[#57606a] mt-1.5">
          {isConnected
            ? `Connected as ${profile?.github_login || "user"}`
            : "Connect your GitHub account to browse and clone repositories"}
        </p>
        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center rounded-full bg-white border border-[#d0d7de] px-2.5 py-1 text-xs font-medium text-[#24292f]">
            {repositories.length} total repos
          </span>
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
            {installedCount} app installed
          </span>
          <button
            type="button"
            onClick={refreshRepositories}
            className="inline-flex items-center gap-1.5 rounded-full border border-[#d0d7de] bg-white px-2.5 py-1 text-xs font-medium text-[#57606a] hover:text-[#24292f]"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
        </div>
      </div>

      <div className="h-full min-h-0">
        {!isConnected ? (
          <div className="h-full flex flex-col items-center justify-center gap-4 px-6">
            <AlertCircle className="w-12 h-12 text-amber-500" />
            <p className="text-center max-w-md text-slate-700">
              You need to connect your GitHub account before selecting repositories.
            </p>
            <Button
              onClick={initiateGitHubAuth}
              className="gap-2"
            >
              <Github className="w-4 h-4" />
              Connect GitHub
            </Button>
          </div>
        ) : gitHubLoading && repositories.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-emerald-600" />
          </div>
        ) : gitHubError ? (
          <div className="p-6">
            <div className="bg-[#ffebe9] border border-[#ff818266] rounded-xl p-4">
              <p className="text-sm text-red-700">{gitHubError}</p>
            </div>
          </div>
        ) : (
          <div className="h-full grid grid-cols-1 xl:grid-cols-[360px_minmax(0,1fr)]">
            <aside className="border-r border-[#f3e8f2] bg-transparent min-h-0 flex flex-col">
              <div className="p-2.5 border-b border-[#d8dee4] space-y-2">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#6e7781]" />
                  <Input
                    placeholder="Search repositories..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-8 h-8 text-xs bg-white border-[#d0d7de] focus-visible:ring-[#0969da]/30"
                  />
                </div>
                <div className="text-xs text-[#57606a] font-medium">
                  {filteredRepos.length} repositories
                </div>
                {gitHubLoading && repositories.length > 0 && (
                  <div className="flex items-center gap-2 text-xs text-[#57606a]">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Refreshing repository list...
                  </div>
                )}
              </div>

              <div className="min-h-0 overflow-y-auto p-3 space-y-3">
                {filteredRepos.length === 0 ? (
                  <p className="text-center text-sm text-muted-foreground py-8">
                    No repositories found
                  </p>
                ) : (
                  filteredRepos.map((repo) => {
                    const isActive =
                      selectedRepo?.github_repo_id === repo.github_repo_id
                    return (
                      <button
                        key={repo.github_repo_id}
                        type="button"
                        onClick={() => setSelectedRepo(repo)}
                        className={`w-full text-left rounded-xl border-2 p-3 transition-all ${
                          isActive
                            ? "border-slate-900 bg-white shadow-lg -translate-y-0.5"
                            : "border-slate-200 bg-white hover:border-slate-400"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="font-medium text-[#24292f] truncate text-sm">
                            {repo.full_name}
                          </p>
                          <span className="text-[#57606a]">
                            {repo.private ? <Lock className="w-3.5 h-3.5" /> : <Globe className="w-3.5 h-3.5" />}
                          </span>
                        </div>
                        <p className="text-xs text-[#57606a] mt-1 line-clamp-2">
                          {repo.description || "No description"}
                        </p>
                        <div className="mt-2 flex items-center gap-2 flex-wrap">
                          {repo.language && (
                            <Badge 
                              variant="secondary" 
                              className={`text-[10px] border-none ${
                                repo.language.toLowerCase() === 'python' ? 'bg-yellow-100 text-yellow-800' :
                                repo.language.toLowerCase() === 'javascript' ? 'bg-orange-100 text-orange-700' :
                                repo.language.toLowerCase() === 'typescript' ? 'bg-red-100 text-red-700' :
                                repo.language.toLowerCase() === 'java' ? 'bg-blue-100 text-blue-700' :
                                repo.language.toLowerCase() === 'go' ? 'bg-cyan-100 text-cyan-700' :
                                repo.language.toLowerCase() === 'rust' ? 'bg-rose-100 text-rose-700' :
                                repo.language.toLowerCase() === 'c++' ? 'bg-indigo-100 text-indigo-700' :
                                repo.language.toLowerCase() === 'c' ? 'bg-slate-100 text-slate-700' :
                                repo.language.toLowerCase() === 'ruby' ? 'bg-pink-100 text-pink-700' :
                                repo.language.toLowerCase() === 'php' ? 'bg-violet-100 text-violet-700' :
                                repo.language.toLowerCase() === 'swift' ? 'bg-orange-100 text-orange-800' :
                                repo.language.toLowerCase() === 'kotlin' ? 'bg-purple-100 text-purple-700' :
                                'bg-slate-100 text-slate-700'
                              }`}
                            >
                              {repo.language}
                            </Badge>
                          )}
                          {repo.stars > 0 && (
                            <span className="inline-flex items-center gap-1 text-[11px] text-[#57606a]">
                              <Star className="w-3 h-3 fill-current" />
                              {repo.stars}
                            </span>
                          )}
                          <span
                            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                              repo.app_installed
                                ? "bg-slate-100 text-slate-700"
                                : "bg-[#fff8c5] text-[#9a6700]"
                            }`}
                          >
                            {repo.app_installed ? "App installed" : "Needs app"}
                          </span>
                        </div>
                      </button>
                    )
                  })
                )}
              </div>
            </aside>

            <section className="min-h-0 overflow-y-auto bg-transparent p-4 pb-20">
              {!selectedRepo ? (
                <div className="h-full flex items-center justify-center px-8">
                  <p className="text-slate-500">
                    Select a repository from the left to see details.
                  </p>
                </div>
              ) : (
                  <div className="h-auto flex flex-col p-6 max-w-3xl mx-auto w-full bg-white rounded-xl border border-slate-200 shadow-sm">
                    <div className="flex items-start justify-between gap-6">
                      <div className="space-y-2">
                        <h3 className="text-2xl font-bold text-[#24292f] tracking-tight">
                          {selectedRepo.full_name.split('/')[1]}
                        </h3>
                        <p className="text-xs text-muted-foreground flex items-center gap-2">
                          <Github className="w-3.5 h-3.5" />
                          {selectedRepo.full_name}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${selectedRepo.private ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
                          {selectedRepo.private ? 'Private' : 'Public'}
                        </span>
                        <a
                          href={selectedRepo.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs font-medium text-blue-600 hover:underline flex items-center gap-1.5"
                        >
                          View on GitHub <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      </div>
                    </div>

                    <p className="mt-4 text-slate-600 leading-relaxed text-xs max-w-2xl">
                      {selectedRepo.description || "No description provided for this repository."}
                    </p>

                    <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div className="bg-blue-50/50 rounded-lg border border-blue-100 p-3.5 shadow-sm transition-all hover:bg-blue-50">
                        <div className="flex items-center gap-2.5 mb-1.5 text-blue-600">
                          <Code2 className="w-3.5 h-3.5" />
                          <span className="text-[10px] font-bold uppercase tracking-wider">Language</span>
                        </div>
                        <p className="text-base font-medium text-slate-900">
                          {selectedRepo.language || "Not specified"}
                        </p>
                      </div>
                      <div className="bg-amber-50/50 rounded-lg border border-amber-100 p-3.5 shadow-sm transition-all hover:bg-amber-50">
                        <div className="flex items-center gap-2.5 mb-1.5 text-amber-600">
                          <Star className="w-3.5 h-3.5 fill-amber-600/20" />
                          <span className="text-[10px] font-bold uppercase tracking-wider">Stars</span>
                        </div>
                        <p className="text-base font-medium text-slate-900">
                          {selectedRepo.stars ?? 0}
                        </p>
                      </div>
                      <div className="bg-slate-50 rounded-lg border border-slate-200 p-3.5 shadow-sm transition-all hover:bg-slate-100">
                        <div className="flex items-center gap-2.5 mb-1.5 text-slate-600">
                          <Globe className="w-3.5 h-3.5" />
                          <span className="text-[10px] font-bold uppercase tracking-wider">Visibility</span>
                        </div>
                        <p className="text-base font-medium text-slate-900">
                          {selectedRepo.private ? "Private" : "Public"}
                        </p>
                      </div>
                    </div>

                    <div className="mt-6 bg-white/60 rounded-xl border border-border p-5 backdrop-blur-sm shadow-sm">
                      {selectedRepo.app_installed ? (
                        <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
                          <div className="space-y-1.5">
                            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-900 text-white text-[10px] font-bold uppercase tracking-wide">
                              <CheckCircle2 className="w-3 h-3" />
                              App Ready
                            </div>
                            <p className="text-xs text-slate-600">
                              Repository access confirmed.
                            </p>
                          </div>
                          <Button
                            size="lg"
                            onClick={() => handleCloneRepository(selectedRepo)}
                            disabled={isCloning}
                            className="bg-[#dc2d98] hover:bg-[#c61f83] text-white px-7 py-5 h-11 rounded-lg font-medium shadow-md shadow-pink-500/10 transition-all hover:scale-105 active:scale-95 text-sm"
                          >
                            {isCloning && cloningRepoId === selectedRepo.github_repo_id ? (
                              <>
                                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                Cloning...
                              </>
                            ) : (
                              <>
                                <Download className="w-4 h-4 mr-2" />
                                Clone & Analyze
                              </>
                            )}
                          </Button>
                        </div>
                      ) : (
                        <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
                          <div className="space-y-1.5">
                            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-amber-500 text-white text-[10px] font-bold uppercase tracking-wide">
                              <AlertCircle className="w-3 h-3" />
                              Action Required
                            </div>
                            <p className="text-xs text-slate-600">
                              Install the GitHub App.
                            </p>
                          </div>
                          <Button
                            size="lg"
                            variant="outline"
                            onClick={() => handleInstallApp(selectedRepo)}
                            disabled={installingRepoId === selectedRepo.github_repo_id}
                            className="border-2 border-slate-900 text-slate-900 font-bold hover:bg-slate-900 hover:text-white rounded-lg transition-all text-sm h-11 px-6"
                          >
                            {installingRepoId === selectedRepo.github_repo_id ? (
                              <>
                                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                Opening...
                              </>
                            ) : (
                              <>
                                <Github className="w-4 h-4 mr-2" />
                                Install App
                              </>
                            )}
                          </Button>
                        </div>
                      )}
                    </div>


                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </>
  )

  return (
    embedded ? (
      <div className="w-full h-full min-h-0 overflow-hidden bg-transparent">
        {selectorPanel}
      </div>
    ) : (
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <Button variant="outline" className="gap-2">
            <Github className="w-4 h-4" />
            Clone from GitHub
          </Button>
        </DialogTrigger>
        <DialogContent
          showCloseButton={false}
          className="!w-[98vw] !max-w-[98vw] sm:!max-w-[98vw] !h-[95vh] p-0 overflow-hidden border-slate-200/80 shadow-2xl"
        >
          {selectorPanel}
        </DialogContent>
      </Dialog>
    )
  )
}
