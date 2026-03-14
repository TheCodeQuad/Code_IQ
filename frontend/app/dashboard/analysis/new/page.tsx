"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useSession } from "next-auth/react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import {
  Code2,
  Upload,
  FolderGit2,
  ArrowLeft,
  FileCode,
  BarChart3,
  GitBranch,
  Play,
  CheckCircle2,
  Plus,
  FileText,
  Activity,
  Settings,
  LogOut,
  Loader2,
  AlertCircle,
  Check,
  Globe,
} from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { uploadRepo } from "@/lib/api"

const LANGUAGE_EXTENSIONS: Record<string, string[]> = {
  python: [".py"],
  javascript: [".js", ".jsx"],
  typescript: [".ts", ".tsx"],
  java: [".java"],
}

const COMMON_LANGUAGE_PATTERNS: Record<string, string> = {
  "requirements.txt": "python",
  "package.json": "javascript",
  "tsconfig.json": "typescript",
  "pom.xml": "java",
  "gradle": "java",
  ".py": "python",
}

export default function NewAnalysisPage() {
  const router = useRouter()
  const { data: session } = useSession()
  const [uploadMethod, setUploadMethod] = useState<"upload" | "git">("git")
  const [repoUrl, setRepoUrl] = useState("")
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>(["python"])
  const [config, setConfig] = useState({
    enableGraphViz: true,
    enableEvaluation: true,
    docStyle: "google",
  })
  const [dragActive, setDragActive] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [repoValidating, setRepoValidating] = useState(false)
  const [repoValid, setRepoValid] = useState(false)
  const [extractedRepoName, setExtractedRepoName] = useState("")
  const [repoValidationMessage, setRepoValidationMessage] = useState("")

  const languages = [
    { id: "python", label: "Python" },
    { id: "javascript", label: "JavaScript" },
    { id: "typescript", label: "TypeScript" },
    { id: "java", label: "Java" },
  ]

  const validateAndExtractRepo = (url: string) => {
    if (!url.trim()) {
      setRepoValid(false)
      setRepoValidationMessage("")
      setExtractedRepoName("")
      return
    }

    setRepoValidating(true)
    setRepoValidationMessage("")

    // Basic URL validation
    const gitUrlPattern = /^(https?:\/\/)?(github\.com|gitlab\.com|bitbucket\.org|gitea|git)\/[\w\-\.]+\/[\w\-\.]+(\/.+)?(\.git)?\/?$/i
    const isValidUrl = gitUrlPattern.test(url) || url.includes("github.com") || url.includes("gitlab.com") || url.includes("bitbucket.org")

    if (isValidUrl) {
      // Extract repo name
      const cleanUrl = url.replace(/\/+$/, "").replace(/\.git$/, "")
      const name = cleanUrl.split("/").pop() || "unknown"
      setExtractedRepoName(name)
      setRepoValid(true)
      setRepoValidationMessage(`Repository: ${name}`)
      setRepoValidating(false)
    } else {
      setRepoValid(false)
      setRepoValidationMessage("Invalid Git URL format")
      setExtractedRepoName("")
      setRepoValidating(false)
    }
  }

  useEffect(() => {
    const timer = setTimeout(() => {
      if (repoUrl.trim()) {
        validateAndExtractRepo(repoUrl)
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [repoUrl])

  const toggleLanguage = (langId: string) => {
    setSelectedLanguages((prev) =>
      prev.includes(langId) ? prev.filter((l) => l !== langId) : [...prev, langId]
    )
  }

  const handleStartAnalysis = async () => {
    // Validate inputs
    if (uploadMethod === "git") {
      if (!repoUrl.trim()) {
        setAnalysisError("Please enter a repository URL")
        return
      }
      if (!repoValid) {
        setAnalysisError("Please enter a valid Git repository URL")
        return
      }
    }

    if (selectedLanguages.length === 0) {
      setAnalysisError("Please select at least one programming language")
      return
    }

    if (!session?.user?.id) {
      setAnalysisError("User session not found")
      return
    }

    setIsAnalyzing(true)
    setAnalysisError(null)

    try {
      // Step 1: Upload/clone the repository and persist metadata.
      const uploadResponse = await uploadRepo({
        repo_url: repoUrl,
        user_id: session.user.id,
      })

      // Step 2: Return to dashboard. User will start analysis explicitly there.
      router.push("/dashboard")
    } catch (err: any) {
      setAnalysisError(err.message || "Failed to upload repository. Please check the URL and try again.")
      setIsAnalyzing(false)
    }
  }

  return (
    <div className="min-h-screen bg-background">
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
            className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-all"
          >
            <FolderGit2 className="w-4 h-4" />
            <span>Projects</span>
          </Link>
          <Link
            href="/dashboard/analysis/new"
            className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm bg-secondary text-foreground font-medium"
          >
            <Plus className="w-4 h-4" />
            <span>New Analysis</span>
          </Link>
          
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 mt-5 px-2">Insights</p>
          <Link
            href="/dashboard/docs"
            className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-all"
          >
            <FileText className="w-4 h-4" />
            <span>Documentation</span>
          </Link>
          <Link
            href="/dashboard/metrics"
            className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-all"
          >
            <BarChart3 className="w-4 h-4" />
            <span>Metrics</span>
          </Link>
          <Link
            href="/dashboard/activity"
            className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-all"
          >
            <Activity className="w-4 h-4" />
            <span>Activity</span>
          </Link>
        </nav>

        <div className="border-t border-border pt-3 space-y-1">
          <button type="button" className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-all w-full">
            <Settings className="w-4 h-4" />
            <span>Settings</span>
          </button>
          <button type="button" className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-all w-full">
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="ml-56">
        {/* Header */}
        <header className="border-b border-border bg-card">
          <div className="px-6 py-3 flex items-center gap-3">
            <Link href="/dashboard">
              <Button variant="ghost" size="sm" className="h-8 px-2 text-muted-foreground hover:text-foreground">
                <ArrowLeft className="w-4 h-4 mr-1.5" />
                Back
              </Button>
            </Link>
            <div className="h-4 w-px bg-border" />
            <span className="text-sm font-medium text-foreground">New Analysis</span>
          </div>
        </header>

        <main className="p-6">
          <div className="mb-6">
            <h1 className="text-xl font-semibold text-foreground">Start New Analysis</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Upload your repository and configure the documentation pipeline
            </p>
          </div>

          <div className="grid lg:grid-cols-3 gap-6">
            {/* Main Configuration */}
            <div className="lg:col-span-2 space-y-4">
              {/* Upload Method */}
              <Card className="border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-medium">Repository Source</CardTitle>
                  <CardDescription className="text-xs">Choose how to provide your codebase</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <button
                      type="button"
                      onClick={() => setUploadMethod("upload")}
                      className={`p-3 rounded-lg border transition-all text-center ${
                        uploadMethod === "upload"
                          ? "border-foreground/30 bg-secondary"
                          : "border-border hover:border-foreground/20"
                      }`}
                    >
                      <Upload className="w-5 h-5 mx-auto mb-1.5 text-muted-foreground" />
                      <p className="text-sm font-medium text-foreground">Upload ZIP</p>
                      <p className="text-xs text-muted-foreground">Upload a ZIP file</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => setUploadMethod("git")}
                      className={`p-3 rounded-lg border transition-all text-center ${
                        uploadMethod === "git"
                          ? "border-foreground/30 bg-secondary"
                          : "border-border hover:border-foreground/20"
                      }`}
                    >
                      <GitBranch className="w-5 h-5 mx-auto mb-1.5 text-muted-foreground" />
                      <p className="text-sm font-medium text-foreground">Git Repository</p>
                      <p className="text-xs text-muted-foreground">Clone from URL</p>
                    </button>
                  </div>

                  {uploadMethod === "upload" ? (
                    <div
                      className={`border border-dashed rounded-lg p-6 text-center transition-colors ${
                        dragActive ? "border-foreground/30 bg-secondary" : "border-border"
                      }`}
                      onDragEnter={() => setDragActive(true)}
                      onDragLeave={() => setDragActive(false)}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={() => setDragActive(false)}
                    >
                      <Upload className="w-8 h-8 mx-auto mb-3 text-muted-foreground" />
                      <p className="text-sm text-foreground font-medium mb-0.5">
                        Drag and drop your ZIP file here
                      </p>
                      <p className="text-xs text-muted-foreground mb-3">or click to browse</p>
                      <Button variant="outline" size="sm" className="border-border bg-transparent h-8 text-xs">
                        Select File
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div>
                        <Label htmlFor="repo-url" className="text-sm text-foreground">Repository URL</Label>
                        <div className="mt-1.5 relative">
                          <Input
                            id="repo-url"
                            placeholder="https://github.com/username/repository"
                            className={`border-border h-10 text-sm pr-10 ${
                              repoUrl && (repoValid ? "border-emerald-500/50 focus:border-emerald-500" : "border-red-500/50 focus:border-red-500")
                            }`}
                            value={repoUrl}
                            onChange={(e) => setRepoUrl(e.target.value)}
                          />
                          {repoUrl && (
                            <div className="absolute right-3 top-1/2 -translate-y-1/2">
                              {repoValidating ? (
                                <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                              ) : repoValid ? (
                                <Check className="w-4 h-4 text-emerald-500" />
                              ) : (
                                <AlertCircle className="w-4 h-4 text-red-500" />
                              )}
                            </div>
                          )}
                        </div>
                        {repoValidationMessage && (
                          <p className={`text-xs mt-1.5 ${repoValid ? "text-emerald-600" : "text-red-600"}`}>
                            {repoValidationMessage}
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground mt-1">
                          Supports GitHub, GitLab, Bitbucket, and other Git hosting services
                        </p>
                      </div>
                      <div>
                        <Label htmlFor="branch" className="text-sm text-foreground">Branch</Label>
                        <Input
                          id="branch"
                          placeholder="main"
                          defaultValue="main"
                          className="mt-1.5 border-border h-10 text-sm"
                        />
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Configuration Options */}
              <Card className="border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-medium">Configuration</CardTitle>
                  <CardDescription className="text-xs">Customize the analysis pipeline</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-secondary flex items-center justify-center">
                        <GitBranch className="w-4 h-4 text-muted-foreground" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">Graph Visualization</p>
                        <p className="text-xs text-muted-foreground">
                          Generate CFG, PDG, and HPG visualizations
                        </p>
                      </div>
                    </div>
                    <Switch
                      checked={config.enableGraphViz}
                      onCheckedChange={(checked) =>
                        setConfig((prev) => ({ ...prev, enableGraphViz: checked }))
                      }
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-secondary flex items-center justify-center">
                        <BarChart3 className="w-4 h-4 text-muted-foreground" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">Evaluation Framework</p>
                        <p className="text-xs text-muted-foreground">
                          Calculate quality metrics and scores
                        </p>
                      </div>
                    </div>
                    <Switch
                      checked={config.enableEvaluation}
                      onCheckedChange={(checked) =>
                        setConfig((prev) => ({ ...prev, enableEvaluation: checked }))
                      }
                    />
                  </div>

                </CardContent>
              </Card>
            </div>

            {/* Summary Sidebar */}
            <div className="space-y-4">
              <Card className="border-border sticky top-6">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-medium">Analysis Summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center gap-2.5 p-2.5 bg-secondary rounded-lg">
                    <FolderGit2 className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="text-xs text-muted-foreground">Source</p>
                      <p className="text-sm font-medium text-foreground capitalize">{uploadMethod}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 p-2.5 bg-secondary rounded-lg">
                    <FileCode className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="text-xs text-muted-foreground">Languages</p>
                      <p className="text-sm font-medium text-foreground">
                        {selectedLanguages.length > 0
                          ? selectedLanguages
                              .map((l) => languages.find((lang) => lang.id === l)?.label)
                              .join(", ")
                          : "None selected"}
                      </p>
                    </div>
                  </div>

                  <div className="space-y-1.5 pt-2 border-t border-border">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Graph Visualization</span>
                      <span className="font-medium text-foreground">
                        {config.enableGraphViz ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Evaluation</span>
                      <span className="font-medium text-foreground">
                        {config.enableEvaluation ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                    
                  </div>

                  <Button
                    className="w-full bg-foreground text-background hover:bg-foreground/90 mt-3 h-9 text-sm"
                    onClick={handleStartAnalysis}
                    disabled={selectedLanguages.length === 0 || isAnalyzing || (uploadMethod === "git" && !repoUrl.trim())}
                  >
                    {isAnalyzing ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                        Analyzing...
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5 mr-1.5" />
                        Clone Repository
                      </>
                    )}
                  </Button>
                  {analysisError && (
                    <div className="flex items-center gap-2 mt-2 p-2 bg-red-500/10 border border-red-500/20 rounded-lg">
                      <AlertCircle className="w-3.5 h-3.5 text-red-500 shrink-0" />
                      <p className="text-xs text-red-500">{analysisError}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
