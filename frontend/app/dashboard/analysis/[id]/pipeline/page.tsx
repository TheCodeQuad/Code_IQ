import { PipelineVisualization } from "@/components/pipeline/PipelineVisualization"
import { ArrowLeft, GitBranch } from "lucide-react"
import Link from "next/link"
import { Button } from "@/components/ui/button"

export default async function PipelinePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>
  searchParams: Promise<{ autostart?: string }>
}) {
  const { id } = await params
  const { autostart } = await searchParams
  const autoStart = autostart === "1"

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Dashboard
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                <GitBranch className="w-5 h-5 text-primary-foreground" />
              </div>
              <div>
                <span className="text-lg font-semibold text-foreground">Pipeline Execution</span>
                <p className="text-sm text-muted-foreground">Live updates for repository {id}</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <PipelineVisualization repoId={id} autoStart={autoStart} />
      </main>
    </div>
  )
}
