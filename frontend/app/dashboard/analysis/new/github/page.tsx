"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useState } from "react"
import { ArrowLeft, Github, Loader2, Unplug } from "lucide-react"
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
    <div className="h-screen bg-background flex flex-col overflow-hidden">
      <header className="border-b border-border bg-card">
        <div className="px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/dashboard/analysis/new">
              <Button variant="ghost" size="sm" className="h-8 px-2 text-muted-foreground hover:text-foreground">
                <ArrowLeft className="w-4 h-4 mr-1.5" />
                Back
              </Button>
            </Link>
            <div className="h-4 w-px bg-border" />
            <span className="text-sm font-medium text-foreground">GitHub Repositories</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
              <Github className="w-4 h-4 text-emerald-500" />
              <span className="text-xs font-medium text-emerald-600">Connected Workspace</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1.5"
              onClick={handleDisconnect}
              disabled={disconnecting}
            >
              {disconnecting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Unplug className="w-3.5 h-3.5" />}
              <span className="text-xs">Disconnect</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1 min-h-0 px-2 pb-2">
        <GitHubRepositorySelector
          embedded
          analysisMode={graphsOnly ? "graphs" : "full"}
          onClose={() => router.push("/dashboard/analysis/new")}
        />
      </main>
    </div>
  )
}
