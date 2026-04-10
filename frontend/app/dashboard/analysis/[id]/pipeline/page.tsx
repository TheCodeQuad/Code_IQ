import { PipelineVisualization } from "@/components/pipeline/PipelineVisualization"
import { ArrowLeft, GitBranch } from "lucide-react"
import Link from "next/link"
import { Button } from "@/components/ui/button"

export default async function PipelinePage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  return (
    <div className="h-screen overflow-hidden bg-background flex flex-col">
      {/* Slim Header */}
      <header className="border-b border-border bg-card shrink-0 z-50 h-14">
        <div className="px-4 h-full flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/dashboard">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4 mr-1.5" />
                Back
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
                <GitBranch className="w-4 h-4 text-primary-foreground" />
              </div>
              <span className="text-sm font-semibold text-foreground">Pipeline Execution</span>
            </div>
          </div>
        </div>
      </header>

      {/* Full-bleed pipeline visualization */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <PipelineVisualization repoId={id} autoStart={true} />
      </div>
    </div>
  )
}
