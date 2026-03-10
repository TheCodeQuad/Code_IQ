"use client"

import { useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { useAnalysis } from "@/lib/analysis-context"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import {
  Code2,
  ArrowLeft,
  FileCode,
  FolderOpen,
  ChevronRight,
  ChevronDown,
  Copy,
  Check,
  Eye,
  PenTool,
  CheckCircle,
  Search,
  GitBranch,
  Network,
  ExternalLink,
  AlertCircle,
  Clock,
} from "lucide-react"

// File tree with documentation status (mock fallback)
const mockFileTree = [
  {
    name: "api",
    type: "folder",
    children: [
      { name: "gateway.py", type: "file", status: "documented", lang: "python" },
      { name: "routes.py", type: "file", status: "documented", lang: "python" },
      { name: "middleware.py", type: "file", status: "partial", lang: "python" },
    ],
  },
  {
    name: "auth",
    type: "folder",
    children: [
      { name: "handler.py", type: "file", status: "documented", lang: "python" },
      { name: "token.py", type: "file", status: "documented", lang: "python" },
      { name: "utils.py", type: "file", status: "pending", lang: "python" },
    ],
  },
  {
    name: "models",
    type: "folder",
    children: [
      { name: "user.py", type: "file", status: "documented", lang: "python" },
      { name: "session.py", type: "file", status: "documented", lang: "python" },
    ],
  },
  { name: "config.py", type: "file", status: "documented", lang: "python" },
  { name: "main.py", type: "file", status: "documented", lang: "python" },
]

const mockCodeExamples = {
  original: `def authenticate_user(username, password, remember_me=False):
    user = db.query(User).filter_by(username=username).first()
    if user and verify_password(password, user.password_hash):
        token = create_token(user.id, remember_me)
        user.last_login = datetime.now()
        db.commit()
        log_auth_attempt(username, True)
        return token
    log_auth_attempt(username, False)
    return None`,
  documented: `def authenticate_user(username, password, remember_me=False):
    """Authenticate a user and return an authentication token.

    This function validates the provided credentials against the database,
    implementing secure password verification using bcrypt. Upon successful
    authentication, it generates a JWT token for subsequent API requests.

    Args:
        username: The user's unique identifier (email or username).
        password: The plaintext password to verify.
        remember_me: If True, extends token expiration to 30 days.
            Defaults to False.

    Returns:
        AuthToken: A valid authentication token if credentials are correct.
        None: If authentication fails due to invalid credentials.

    Raises:
        DatabaseConnectionError: If unable to connect to the user database.
        RateLimitExceeded: If too many authentication attempts from this IP.

    Example:
        >>> token = authenticate_user("john@example.com", "secret123")
        >>> if token:
        ...     print(f"Authenticated: {token.user_id}")
    """
    user = db.query(User).filter_by(username=username).first()
    if user and verify_password(password, user.password_hash):
        token = create_token(user.id, remember_me)
        user.last_login = datetime.now()
        db.commit()
        log_auth_attempt(username, True)
        return token
    log_auth_attempt(username, False)
    return None`,
}

const mockDocstringParsed = {
  description: "Authenticate a user and return an authentication token. This function validates the provided credentials against the database, implementing secure password verification using bcrypt. Upon successful authentication, it generates a JWT token for subsequent API requests.",
  parameters: [
    { name: "username", type: "str", description: "The user's unique identifier (email or username)." },
    { name: "password", type: "str", description: "The plaintext password to verify." },
    { name: "remember_me", type: "bool", description: "If True, extends token expiration to 30 days. Defaults to False." },
  ],
  returns: { type: "AuthToken | None", description: "A valid authentication token if credentials are correct, None if authentication fails." },
  raises: [
    { exception: "DatabaseConnectionError", description: "If unable to connect to the user database." },
    { exception: "RateLimitExceeded", description: "If too many authentication attempts from this IP." },
  ],
}

const mockAgentSummary = {
  reader: {
    status: "completed",
    output: "Extracted function signature, control flow (2 branches), data dependencies (db, verify_password, create_token), and return semantics.",
  },
  searcher: {
    status: "completed",
    output: "Found related context: User model (models/user.py), token utilities (auth/token.py), password verification (auth/utils.py).",
  },
  writer: {
    status: "completed",
    output: "Generated Google-style docstring with Args, Returns, Raises, and Example sections.",
  },
  verifier: {
    status: "passed",
    output: "Consistency check passed. Parameter count matches (3/3). Return type inference verified. No hallucinations detected.",
  },
}

const mockGraphReferences = {
  cfg: ["node_12", "node_13", "node_14", "node_15"],
  pdg: ["dep_auth_01", "dep_auth_02", "dep_auth_03"],
  hpg: ["hpg_auth_handler_authenticate"],
}

export default function DocumentationPage() {
  const [selectedFile, setSelectedFile] = useState("auth/handler.py")
  const [activeTab, setActiveTab] = useState<"code" | "docstring" | "diff">("code")
  const [copied, setCopied] = useState(false)
  const params = useParams()
  const analysisId = params.id as string
  const { getAnalysis } = useAnalysis()
  const analysis = getAnalysis(analysisId)

  // Build real data from analysis when available
  const fileTree = analysis?.components ? buildDocFileTree(analysis.components) : mockFileTree

  const codeExamples = analysis?.components ? (() => {
    const comps = Object.values(analysis.components!).filter(
      (c: any) => c.file_path === selectedFile || c.file_path?.endsWith(selectedFile)
    )
    const comp = comps[0] || Object.values(analysis.components!)[0]
    if (!comp) return mockCodeExamples
    return {
      original: comp.source_code || "// No source code available",
      documented: comp.docstring
        ? `${comp.docstring}\n\n${comp.source_code || ""}`
        : comp.source_code || "// No source code available",
    }
  })() : mockCodeExamples

  const docstringParsed = analysis?.components ? (() => {
    const comps = Object.values(analysis.components!).filter(
      (c: any) => c.file_path === selectedFile || c.file_path?.endsWith(selectedFile)
    )
    const comp = comps[0] || Object.values(analysis.components!)[0]
    if (!comp?.docstring) return mockDocstringParsed
    return {
      description: comp.docstring.replace(/"""/g, "").trim().split("\n")[0] || "No description",
      parameters: comp.depends_on?.map((d: string) => ({
        name: d.split(".").pop() || d,
        type: "any",
        description: `Dependency: ${d}`,
      })) || [],
      returns: { type: comp.type, description: `Returns ${comp.type}` },
      raises: [] as { exception: string; description: string }[],
    }
  })() : mockDocstringParsed

  const agentSummary = analysis?.stats ? {
    reader: {
      status: "completed",
      output: `Extracted ${analysis.stats.functions + analysis.stats.methods} functions and ${analysis.stats.classes} classes from ${new Set(Object.values(analysis.components || {}).map(c => c.file_path)).size} files.`,
    },
    searcher: {
      status: "completed",
      output: `Found context across ${analysis.stats.total_dependencies} dependencies with avg ${analysis.stats.avg_dependencies.toFixed(1)} per component.`,
    },
    writer: {
      status: "completed",
      output: `Generated docstrings for ${analysis.stats.components_with_docstrings} of ${analysis.stats.total_components} components.`,
    },
    verifier: {
      status: "passed",
      output: `${analysis.stats.components_with_docstrings}/${analysis.stats.total_components} components documented. ${analysis.stats.components_without_docstrings} pending.`,
    },
  } : mockAgentSummary

  const graphReferences = analysis?.dag ? {
    cfg: Object.keys(analysis.dag).slice(0, 4),
    pdg: Object.keys(analysis.dag).slice(4, 7),
    hpg: Object.keys(analysis.dag).slice(7, 8),
  } : mockGraphReferences

  const handleCopy = () => {
    navigator.clipboard.writeText(codeExamples.documented)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const statusConfig = {
    documented: { label: "Documented", color: "bg-chart-3", textColor: "text-chart-3" },
    partial: { label: "Partial", color: "bg-chart-1", textColor: "text-chart-1" },
    pending: { label: "Pending", color: "bg-muted-foreground", textColor: "text-muted-foreground" },
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card sticky top-0 z-50">
        <div className="max-w-[1600px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                <Code2 className="w-5 h-5 text-primary-foreground" />
              </div>
              <div>
                <span className="text-lg font-semibold text-foreground">{analysis?.repoName || "api-gateway"}</span>
                <Badge className="ml-2 bg-chart-3/10 text-chart-3 border border-chart-3/20">{analysis?.status === "completed" ? "Documented" : "Pending"}</Badge>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link href={`/dashboard/analysis/${analysisId}/graphs`}>
              <Button variant="outline" size="sm" className="border-border bg-transparent">
                <Network className="w-4 h-4 mr-2" />
                View Graphs
              </Button>
            </Link>
            <Link href={`/dashboard/analysis/${analysisId}/metrics`}>
              <Button variant="outline" size="sm" className="border-border bg-transparent">
                View Metrics
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto">
        <div className="grid grid-cols-12 min-h-[calc(100vh-73px)]">
          {/* LEFT: Repository Tree */}
          <div className="col-span-2 border-r border-border bg-card/50">
            <div className="p-4 border-b border-border">
              <h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
                <FolderOpen className="w-4 h-4" />
                Repository Tree
              </h3>
            </div>
            <ScrollArea className="h-[calc(100vh-140px)]">
              <div className="p-3 space-y-1">
                {fileTree.map((item) => (
                  <FileTreeItem
                    key={item.name}
                    item={item}
                    selectedFile={selectedFile}
                    onSelect={setSelectedFile}
                    statusConfig={statusConfig}
                  />
                ))}
              </div>
            </ScrollArea>
          </div>

          {/* CENTER: Code + Doc View */}
          <div className="col-span-7 border-r border-border">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileCode className="w-5 h-5 text-muted-foreground" />
                <span className="font-mono text-sm text-foreground">{selectedFile}</span>
                <Badge className="bg-chart-3/10 text-chart-3 border border-chart-3/20">
                  <CheckCircle className="w-3 h-3 mr-1" />
                  Documented
                </Badge>
              </div>
              <Button variant="outline" size="sm" className="border-border bg-transparent" onClick={handleCopy}>
                {copied ? (
                  <>
                    <Check className="w-4 h-4 mr-2" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4 mr-2" />
                    Copy
                  </>
                )}
              </Button>
            </div>

            <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)} className="h-full">
              <div className="px-4 pt-4">
                <TabsList className="bg-secondary">
                  <TabsTrigger value="code">Code</TabsTrigger>
                  <TabsTrigger value="docstring">Docstring</TabsTrigger>
                  <TabsTrigger value="diff">Diff View</TabsTrigger>
                </TabsList>
              </div>

              <TabsContent value="code" className="p-4 mt-0">
                <div className="relative rounded-lg overflow-hidden">
                  <pre className="bg-foreground text-background p-6 text-sm overflow-x-auto font-mono leading-relaxed">
                    <code>{codeExamples.documented}</code>
                  </pre>
                  <Badge className="absolute top-4 right-4 bg-chart-3 text-white">AI Generated</Badge>
                </div>
              </TabsContent>

              <TabsContent value="docstring" className="p-4 mt-0">
                <Card className="border-border">
                  <CardContent className="p-6 space-y-6">
                    {/* Description */}
                    <div>
                      <h4 className="text-sm font-semibold text-foreground mb-2">Description</h4>
                      <p className="text-sm text-muted-foreground leading-relaxed">{docstringParsed.description}</p>
                    </div>

                    <Separator />

                    {/* Parameters */}
                    <div>
                      <h4 className="text-sm font-semibold text-foreground mb-3">Parameters</h4>
                      <div className="space-y-3">
                        {docstringParsed.parameters.map((param) => (
                          <div key={param.name} className="flex gap-4 p-3 bg-secondary/50 rounded-lg">
                            <div className="flex items-center gap-2">
                              <code className="text-sm font-mono text-primary font-medium">{param.name}</code>
                              <Badge variant="outline" className="text-xs border-border">{param.type}</Badge>
                            </div>
                            <p className="text-sm text-muted-foreground">{param.description}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    <Separator />

                    {/* Returns */}
                    <div>
                      <h4 className="text-sm font-semibold text-foreground mb-3">Returns</h4>
                      <div className="flex gap-4 p-3 bg-secondary/50 rounded-lg">
                        <Badge variant="outline" className="text-xs border-border">{docstringParsed.returns.type}</Badge>
                        <p className="text-sm text-muted-foreground">{docstringParsed.returns.description}</p>
                      </div>
                    </div>

                    <Separator />

                    {/* Raises */}
                    <div>
                      <h4 className="text-sm font-semibold text-foreground mb-3">Raises</h4>
                      <div className="space-y-2">
                        {docstringParsed.raises.map((item) => (
                          <div key={item.exception} className="flex gap-4 p-3 bg-destructive/5 rounded-lg border border-destructive/10">
                            <code className="text-sm font-mono text-destructive font-medium">{item.exception}</code>
                            <p className="text-sm text-muted-foreground">{item.description}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="diff" className="p-4 mt-0">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant="outline" className="border-destructive/30 text-destructive">Before</Badge>
                      <span className="text-xs text-muted-foreground">Original code</span>
                    </div>
                    <pre className="bg-destructive/5 border border-destructive/10 text-foreground p-4 rounded-lg text-xs overflow-x-auto font-mono leading-relaxed">
                      <code>{codeExamples.original}</code>
                    </pre>
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant="outline" className="border-chart-3/30 text-chart-3">After</Badge>
                      <span className="text-xs text-muted-foreground">With documentation</span>
                    </div>
                    <pre className="bg-chart-3/5 border border-chart-3/10 text-foreground p-4 rounded-lg text-xs overflow-x-auto font-mono leading-relaxed">
                      <code>{codeExamples.documented}</code>
                    </pre>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </div>

          {/* RIGHT: Context Panel */}
          <div className="col-span-3 bg-card/50">
            <div className="p-4 border-b border-border">
              <h3 className="font-semibold text-sm text-foreground">Context Panel</h3>
              <p className="text-xs text-muted-foreground mt-1">Agent reasoning and graph references</p>
            </div>
            <ScrollArea className="h-[calc(100vh-180px)]">
              <div className="p-4 space-y-6">
                {/* Agent Summary */}
                <div>
                  <h4 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                    Agent Summary
                  </h4>
                  <div className="space-y-3">
                    <AgentCard
                      icon={Eye}
                      name="Reader"
                      status={agentSummary.reader.status}
                      output={agentSummary.reader.output}
                      color="bg-chart-1"
                    />
                    <AgentCard
                      icon={Search}
                      name="Searcher"
                      status={agentSummary.searcher.status}
                      output={agentSummary.searcher.output}
                      color="bg-chart-4"
                    />
                    <AgentCard
                      icon={PenTool}
                      name="Writer"
                      status={agentSummary.writer.status}
                      output={agentSummary.writer.output}
                      color="bg-chart-2"
                    />
                    <AgentCard
                      icon={CheckCircle}
                      name="Verifier"
                      status={agentSummary.verifier.status}
                      output={agentSummary.verifier.output}
                      color="bg-chart-3"
                    />
                  </div>
                </div>

                <Separator />

                {/* Graph References */}
                <div>
                  <h4 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                    <GitBranch className="w-4 h-4" />
                    Graph References
                  </h4>
                  <div className="space-y-3">
                    <div className="p-3 bg-secondary/50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-foreground">CFG Nodes</span>
                        <Link href={`/dashboard/analysis/${analysisId}/graphs?type=cfg`}>
                          <Button variant="ghost" size="sm" className="h-6 text-xs">
                            <ExternalLink className="w-3 h-3 mr-1" />
                            Jump
                          </Button>
                        </Link>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {graphReferences.cfg.map((node) => (
                          <Badge key={node} variant="outline" className="text-xs font-mono border-border">{node}</Badge>
                        ))}
                      </div>
                    </div>
                    <div className="p-3 bg-secondary/50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-foreground">PDG Dependencies</span>
                        <Link href={`/dashboard/analysis/${analysisId}/graphs?type=pdg`}>
                          <Button variant="ghost" size="sm" className="h-6 text-xs">
                            <ExternalLink className="w-3 h-3 mr-1" />
                            Jump
                          </Button>
                        </Link>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {graphReferences.pdg.map((node) => (
                          <Badge key={node} variant="outline" className="text-xs font-mono border-border">{node}</Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                <Separator />

                {/* Confidence Score */}
                <div>
                  <h4 className="text-sm font-semibold text-foreground mb-3">Confidence Score</h4>
                  <div className="p-4 bg-chart-3/10 rounded-lg border border-chart-3/20">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-4xl font-bold text-chart-3">0.91</span>
                      <Badge className="bg-chart-3 text-white">High</Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">Based on semantic analysis, parameter matching, and verifier checks.</p>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </div>
        </div>
      </main>
    </div>
  )
}

function FileTreeItem({
  item,
  selectedFile,
  onSelect,
  statusConfig,
  depth = 0,
}: {
  item: any
  selectedFile: string
  onSelect: (file: string) => void
  statusConfig: any
  depth?: number
}) {
  const [expanded, setExpanded] = useState(true)
  const isFolder = item.type === "folder"
  const fullPath = item.name

  const langIcons: Record<string, string> = {
    python: "text-chart-1",
    javascript: "text-chart-4",
    typescript: "text-chart-2",
    java: "text-chart-5",
  }

  return (
    <div style={{ paddingLeft: `${depth * 12}px` }}>
      <button
        type="button"
        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors ${
          selectedFile === fullPath
            ? "bg-primary/10 text-foreground"
            : "text-muted-foreground hover:bg-secondary hover:text-foreground"
        }`}
        onClick={() => {
          if (isFolder) {
            setExpanded(!expanded)
          } else {
            onSelect(fullPath)
          }
        }}
      >
        {isFolder ? (
          <>
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            <FolderOpen className="w-4 h-4" />
          </>
        ) : (
          <>
            <span className="w-3" />
            <FileCode className={`w-4 h-4 ${langIcons[item.lang] || ""}`} />
          </>
        )}
        <span className="flex-1 text-left truncate">{item.name}</span>
        {!isFolder && item.status && (
          <div className={`w-2 h-2 rounded-full ${statusConfig[item.status]?.color}`} title={statusConfig[item.status]?.label} />
        )}
      </button>
      {isFolder && expanded && item.children && (
        <div>
          {item.children.map((child: any) => (
            <FileTreeItem
              key={child.name}
              item={child}
              selectedFile={selectedFile}
              onSelect={onSelect}
              statusConfig={statusConfig}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function AgentCard({
  icon: Icon,
  name,
  status,
  output,
  color,
}: {
  icon: any
  name: string
  status: string
  output: string
  color: string
}) {
  const statusIcon = status === "passed" || status === "completed" ? CheckCircle : status === "warning" ? AlertCircle : Clock

  return (
    <div className="p-3 bg-secondary/50 rounded-lg border border-border/50">
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-6 h-6 rounded-full ${color} flex items-center justify-center`}>
          <Icon className="w-3 h-3 text-white" />
        </div>
        <span className="text-sm font-medium text-foreground">{name}</span>
        <statusIcon className={`w-3 h-3 ml-auto ${status === "passed" || status === "completed" ? "text-chart-3" : "text-chart-1"}`} />
      </div>
      <p className="text-xs text-muted-foreground leading-relaxed">{output}</p>
    </div>
  )
}

function buildDocFileTree(components: Record<string, any>): any[] {
  const tree: Record<string, any> = {}

  // Group components by file to determine documentation status
  const fileMap = new Map<string, { lang: string; total: number; documented: number }>()
  for (const comp of Object.values(components)) {
    const fp = comp.file_path || ""
    const entry = fileMap.get(fp) || { lang: comp.language || "python", total: 0, documented: 0 }
    entry.total++
    if (comp.has_docstring) entry.documented++
    fileMap.set(fp, entry)
  }

  for (const [filePath, data] of fileMap.entries()) {
    const parts = filePath.replace(/\\/g, "/").split("/").filter(Boolean)
    let current = tree
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      if (i === parts.length - 1) {
        if (!current[part]) {
          current[part] = {
            name: part,
            type: "file",
            status: data.documented === data.total ? "documented" : data.documented > 0 ? "partial" : "pending",
            lang: data.lang,
          }
        }
      } else {
        if (!current[part]) {
          current[part] = { name: part, type: "folder", children: {} }
        }
        current = current[part].children || {}
      }
    }
  }

  function toArray(obj: Record<string, any>): any[] {
    return Object.values(obj).map((item: any) => {
      if (item.type === "folder" && item.children) {
        return { ...item, children: toArray(item.children) }
      }
      return item
    }).sort((a: any, b: any) => {
      if (a.type === "folder" && b.type !== "folder") return -1
      if (a.type !== "folder" && b.type === "folder") return 1
      return a.name.localeCompare(b.name)
    })
  }

  return toArray(tree)
}
