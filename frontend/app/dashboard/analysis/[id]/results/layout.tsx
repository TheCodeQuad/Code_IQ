"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams, usePathname } from "next/navigation"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  ArrowLeft,
  Code2,
  FileCode,
  FileText,
  GitBranch,
  ClipboardCheck,
  GitPullRequest,
  Download,
} from "lucide-react"

const statusConfig = {
  pending: { label: "Pending", color: "bg-amber-500 text-white" },
  completed: { label: "Completed", color: "bg-emerald-500 text-white" },
  incomplete: { label: "Incomplete", color: "bg-red-500 text-white" },
}

const navItems = [
  { href: "/documentation", label: "Documentation", icon: FileCode },
  { href: "/readme", label: "README", icon: FileText },
  { href: "/graph", label: "View Graphs", icon: GitBranch },
  { href: "/metrics", label: "Evaluation Metrics", icon: ClipboardCheck },
  { href: "/pull-request", label: "Pull Request", icon: GitPullRequest },
]

export default function ResultsLayout({ children }: { children: React.ReactNode }) {
  const params = useParams()
  const pathname = usePathname()
  const router = useRouter()
  const id = params.id as string

  const [repoName, setRepoName] = useState<string>("Loading...")
  const [repoStatus, setRepoStatus] = useState<"pending" | "completed" | "incomplete">("pending")
  const [repoLanguage, setRepoLanguage] = useState<string>("-")

  useEffect(() => {
    let isMounted = true

    async function loadRepo() {
      try {
        const res = await fetch(`/api/repos/${id}`)
        if (!res.ok) throw new Error("Failed to load repository")
        const data = await res.json()
        if (!isMounted) return

        if (typeof data?.repo_name === "string" && data.repo_name.trim()) {
          setRepoName(data.repo_name)
        }

        const statusValue = typeof data?.status === "string" ? data.status : "pending"
        if (statusValue === "completed" || statusValue === "pending" || statusValue === "incomplete") {
          setRepoStatus(statusValue)
        }

        if (typeof data?.language === "string" && data.language.trim()) {
          setRepoLanguage(data.language)
        }
      } catch {
        if (!isMounted) return
        setRepoName(`Repo ${id}`)
      }
    }

    loadRepo()

    return () => {
      isMounted = false
    }
  }, [id])

  const status = useMemo(() => statusConfig[repoStatus], [repoStatus])
  
  // Determine current page for nav highlighting
  const basePath = `/dashboard/analysis/${id}/results`
  const currentPath = pathname.replace(basePath, "") || ""
  
  return (
    <div className="min-h-screen bg-transparent">
      {/* Header/Navbar */}
      <header className="border-b border-stone-200/50 bg-background/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-[1600px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Left section */}
            <div className="flex items-center gap-4">
              <Link href="/dashboard">
                <Button variant="ghost" size="sm" className="gap-2 text-stone-600 hover:text-stone-900">
                  <ArrowLeft className="w-4 h-4" />
                  Back
                </Button>
              </Link>
              
              <div className="h-6 w-px bg-stone-200" />
              
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-amber-400 flex items-center justify-center">
                  <Code2 className="w-5 h-5 text-white" />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold text-stone-900">
                    {repoName}
                  </span>
                  <Badge className={`${status.color} text-xs font-medium px-2.5 py-0.5 rounded-full`}>
                    {status.label}
                  </Badge>
                  <Badge variant="outline" className="text-xs text-stone-500 border-stone-300">
                    {repoLanguage}
                  </Badge>
                </div>
              </div>
            </div>
            
            {/* Right section */}
            <Button className="bg-stone-900 text-white hover:bg-stone-800">
              <Download className="w-4 h-4 mr-2" />
              Export File
            </Button>
          </div>
        </div>
      </header>

      {/* Sub Navigation - Pill Style */}
      <div className="border-b border-stone-200/50 bg-background/50">
        <div className="max-w-[1600px] mx-auto px-6 py-3">
          <nav className="inline-flex items-center gap-1 p-1 bg-stone-200/50 rounded-lg">
            {navItems.map((item) => {
              const isActive = currentPath === item.href
              const Icon = item.icon
              return (
                <Link
                  key={item.href}
                  href={`${basePath}${item.href}`}
                  className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-all ${
                    isActive
                      ? "bg-white text-stone-900 shadow-sm"
                      : "text-stone-600 hover:text-stone-900"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                </Link>
              )
            })}
          </nav>
        </div>
      </div>

      {/* Main content */}
      <main className="max-w-[1600px] mx-auto px-6 py-6">
        {children}
      </main>
    </div>
  )
}