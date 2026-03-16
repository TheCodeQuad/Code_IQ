"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft, FileText, BookOpen, BarChart3, Code2 } from "lucide-react"

export default function AnalysisLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const params = useParams()
  const analysisId = params.id as string

  const tabs = [
    { name: "Documentation", href: `/dashboard/analysis/${analysisId}/documentation`, icon: FileText },
    { name: "README", href: `/dashboard/analysis/${analysisId}/results`, icon: BookOpen },
    { name: "Evaluation", href: `/dashboard/analysis/${analysisId}/metrics`, icon: BarChart3 },
  ]

  return (
    <div className="min-h-screen bg-background">
      {/* Header with navigation tabs */}
      <header className="border-b border-border bg-card sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-4">
          {/* Back button - place this in the actual page component if needed */}
          
          {/* Tab navigation */}
          <div className="flex gap-1 mt-4">
            {tabs.map((tab) => {
              const Icon = tab.icon
              const isActive = (
                typeof window !== "undefined" &&
                window.location.pathname === tab.href
              )
              
              return (
                <Link key={tab.name} href={tab.href}>
                  <Button
                    variant={isActive ? "default" : "ghost"}
                    size="sm"
                    className="gap-2"
                  >
                    <Icon className="w-4 h-4" />
                    {tab.name}
                  </Button>
                </Link>
              )
            })}
          </div>
        </div>
      </header>

      {/* Page content */}
      <main>{children}</main>
    </div>
  )
}
