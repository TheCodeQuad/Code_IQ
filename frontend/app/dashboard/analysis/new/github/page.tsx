"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useState } from "react"
import { 
  ArrowLeft, 
  Github, 
  Loader2, 
  Unplug, 
  Code2, 
  FolderGit2, 
  Plus, 
  FileText, 
  BarChart3, 
  Activity, 
  Settings, 
  LogOut 
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { GitHubRepositorySelector } from "@/components/github-repository-selector"
import { useGitHub } from "@/hooks/use-github"

export default function NewAnalysisGitHubPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const graphsOnly = searchParams.get("mode") === "graphs"
  const { disconnectGitHub } = useGitHub()
  const [disconnecting, setDisconnecting] = useState(false)

  const handleDisconnect = async () => {
    const confirmed = window.confirm("Disconnect GitHub and clear this account's GitHub connection?")
    if (!confirmed) return

    setDisconnecting(true)
    const ok = await disconnectGitHub()
    setDisconnecting(false)

    if (!ok) {
      alert("Failed to disconnect GitHub. Please try again.")
      return
    }

    router.push("/dashboard/analysis/new")
  }

  return (
    <div className="min-h-screen bg-[#fef5fb]">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 bottom-0 w-56 bg-card border-r border-border p-4 flex flex-col">
        <Link href="/" className="flex items-center gap-2 mb-8">
          <div className="w-8 h-8 rounded-lg bg-foreground flex items-center justify-center">
            <Code2 className="w-4 h-4 text-background" />
          </div>
          <span className="text-lg font-semibold text-foreground">CodeIQ</span>
        </Link>

        <nav className="flex-1 space-y-1">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 px-2">Main</p>
          <Link
            href="/dashboard"
            className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm text-muted-foreground hover:bg-purple-100 hover:text-black transition-all"
          >
            <FolderGit2 className="w-4 h-4 text-black" />
            <span>Projects</span>
          </Link>
          <Link
            href="/dashboard/analysis/new"
            className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm bg-secondary text-foreground font-medium"
          >
            <Plus className="w-4 h-4 text-black" />
            <span>New Analysis</span>
          </Link>
          
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 mt-5 px-2">Insights</p>
          <Link
            href="/dashboard/docs"
            className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm text-muted-foreground hover:bg-purple-100 hover:text-black transition-all"
          >
            <FileText className="w-4 h-4 text-black" />
            <span>Documentation</span>
          </Link>
          <Link
            href="/dashboard/metrics"
            className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm text-muted-foreground hover:bg-purple-100 hover:text-black transition-all"
          >
            <BarChart3 className="w-4 h-4 text-black" />
            <span>Metrics</span>
          </Link>
          <Link
            href="/dashboard/activity"
            className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm text-muted-foreground hover:bg-purple-100 hover:text-black transition-all"
          >
            <Activity className="w-4 h-4 text-black" />
            <span>Activity</span>
          </Link>
        </nav>

        <div className="border-t border-border pt-3 space-y-1">
          <button type="button" className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm text-muted-foreground hover:bg-purple-100 hover:text-black transition-all w-full">
            <Settings className="w-4 h-4 text-black" />
            <span>Settings</span>
          </button>
          <button type="button" className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm text-muted-foreground hover:bg-purple-100 hover:text-black transition-all w-full">
            <LogOut className="w-4 h-4 text-black" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="ml-56 flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <header className="border-b border-border bg-card">
          <div className="px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Link href="/dashboard/analysis/new">
                <Button variant="ghost" size="sm" className="h-8 px-2 text-muted-foreground hover:text-foreground">
                  <ArrowLeft className="w-4 h-4 mr-1.5 text-black" />
                  Back
                </Button>
              </Link>
              <div className="h-4 w-px bg-border" />
              <span className="text-sm font-medium text-foreground">GitHub Repositories</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-black text-white border border-black">
                <Github className="w-4 h-4" />
                <span className="text-xs font-medium">Connected Workspace</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-1.5 border-black text-black hover:bg-purple-900 hover:text-white hover:border-purple-900"
                onClick={handleDisconnect}
                disabled={disconnecting}
              >
                {disconnecting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Unplug className="w-3.5 h-3.5" />}
                <span className="text-xs">Disconnect</span>
              </Button>
            </div>
          </div>
        </header>

        <main className="flex-1 min-h-0 bg-[#fef5fb] pt-4 pl-4 pr-6 pb-6">
          <GitHubRepositorySelector
            embedded
            analysisMode={graphsOnly ? "graphs" : "full"}
            onClose={() => router.push("/dashboard/analysis/new")}
          />
        </main>
      </div>
    </div>
  )
}

