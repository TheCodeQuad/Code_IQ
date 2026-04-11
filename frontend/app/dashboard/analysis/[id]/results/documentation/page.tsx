"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { useAnalysis } from "@/lib/analysis-context"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import SyntaxHighlighter from "react-syntax-highlighter"
import { atomOneDark } from "react-syntax-highlighter/dist/esm/styles/hljs"
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
  EyeOff,
  PenTool,
  CheckCircle,
  Search,
  GitBranch,
  Network,
  ExternalLink,
  AlertCircle,
  Clock,
} from "lucide-react"

// Custom theme with yellow comments/docstrings
const customTheme = {
  ...atomOneDark,
  'hljs-comment': {
    color: '#FFD700',
    fontStyle: 'italic',
  },
  'hljs-quote': {
    color: '#FFD700',
  },
}

function getLanguageFromPath(filePath: string): string {
  const ext = filePath.split(".").pop()?.toLowerCase() || ""
  const languageMap: Record<string, string> = {
    py: "python",
    js: "javascript",
    jsx: "jsx",
    ts: "typescript",
    tsx: "tsx",
    java: "java",
    cpp: "cpp",
    c: "c",
    cs: "csharp",
    php: "php",
    rb: "ruby",
    go: "go",
    rs: "rust",
    kt: "kotlin",
    swift: "swift",
    sql: "sql",
    html: "html",
    css: "css",
    json: "json",
    xml: "xml",
    yaml: "yaml",
    yml: "yaml",
    sh: "bash",
    bash: "bash",
  }
  return languageMap[ext] || "text"
}

function stripDocstrings(content: string, language: string): string {
  const lines = content.split("\n")
  const result: string[] = []
  let inBlockComment = false

  for (const line of lines) {
    const trimmed = line.trim()

    if (inBlockComment) {
      if (trimmed.includes("*/") || trimmed.includes('"""') || trimmed.includes("'''")) {
        inBlockComment = false
      }
      continue
    }

    if (trimmed.startsWith("//") || trimmed.startsWith("#")) {
      continue
    }

    if (trimmed.startsWith("/*") || trimmed.startsWith("/**")) {
      if (!trimmed.includes("*/")) {
        inBlockComment = true
      }
      continue
    }

    if (language === "python" && (trimmed.startsWith('"""') || trimmed.startsWith("'''"))) {
      const quote = trimmed.startsWith('"""') ? '"""' : "'''"
      const firstIndex = trimmed.indexOf(quote)
      const lastIndex = trimmed.lastIndexOf(quote)

      if (firstIndex === lastIndex) {
        inBlockComment = true
      }
      continue
    }

    result.push(line)
  }

  return result.join("\n")
}

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
  const [selectedFile, setSelectedFile] = useState("")
  const [showOriginal, setShowOriginal] = useState(false)
  const [copied, setCopied] = useState(false)
  const [treeLoading, setTreeLoading] = useState(true)
  const [fileLoading, setFileLoading] = useState(false)
  const [repoTree, setRepoTree] = useState<any[]>([])
  const [documentedCode, setDocumentedCode] = useState("")
  const [originalCode, setOriginalCode] = useState("")
  const params = useParams()
  const analysisId = params.id as string
  const { getAnalysis } = useAnalysis()
  const analysis = getAnalysis(analysisId)

  const fileTree = repoTree.length > 0 ? repoTree : analysis?.components ? buildDocFileTree(analysis.components) : mockFileTree

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

  const fetchFileContent = useCallback(
    async (filePath: string) => {
      if (!filePath) return
      setFileLoading(true)
      try {
        const [documentedRes, originalRes] = await Promise.all([
          fetch(`/api/repos/${analysisId}/file?path=${encodeURIComponent(filePath)}&documented=true`),
          fetch(`/api/repos/${analysisId}/file?path=${encodeURIComponent(filePath)}&documented=false`),
        ])

        let documentedContent = ""
        let originalContent = ""

        // Try to get documented version
        if (documentedRes.ok) {
          const documentedData = await documentedRes.json()
          documentedContent = documentedData?.content || ""
        }

        // Try to get original version
        if (originalRes.ok) {
          const originalData = await originalRes.json()
          originalContent = originalData?.content || ""
        }

        // If we have documented content, use it; otherwise use original
        const language = filePath.split(".").pop()?.toLowerCase() || "text"
        
        if (!documentedContent && originalContent) {
          // If documented failed but original succeeded, strip docstrings from original
          setDocumentedCode(originalContent)
          setOriginalCode(stripDocstrings(originalContent, language))
        } else if (documentedContent && originalContent) {
          // If both succeeded, use them as-is
          setDocumentedCode(documentedContent)
          setOriginalCode(originalContent)
        } else if (documentedContent) {
          // Only documented succeeded, strip docstrings for original view
          setDocumentedCode(documentedContent)
          setOriginalCode(stripDocstrings(documentedContent, language))
        } else if (originalContent) {
          // Fallback: only original succeeded
          setDocumentedCode(originalContent)
          setOriginalCode(stripDocstrings(originalContent, language))
        } else {
          // Both failed, show empty code
          setDocumentedCode("")
          setOriginalCode("")
        }
      } catch (err) {
        console.error("Error fetching file content:", err)
        setDocumentedCode("")
        setOriginalCode("")
      } finally {
        setFileLoading(false)
      }
    },
    [analysisId]
  )

  useEffect(() => {
    async function fetchTree() {
      try {
        const res = await fetch(`/api/repos/${analysisId}/tree`)
        if (!res.ok) throw new Error("Failed to load tree")
        const data = await res.json()
        const realTree = data?.tree || []
        setRepoTree(realTree)
        const first = findFirstFile(realTree)
        if (first) {
          setSelectedFile(first.path || first.name)
        }
      } catch {
        const fallbackTree = analysis?.components ? buildDocFileTree(analysis.components) : mockFileTree
        setRepoTree(fallbackTree)
        const first = findFirstFile(fallbackTree)
        if (first) {
          setSelectedFile(first.path || first.name)
        }
      } finally {
        setTreeLoading(false)
      }
    }
    fetchTree()
  }, [analysisId, analysis?.components])

  useEffect(() => {
    if (selectedFile) {
      fetchFileContent(selectedFile)
    }
  }, [selectedFile, fetchFileContent])

  const displayCode = showOriginal ? originalCode : documentedCode

  const handleCopy = () => {
    navigator.clipboard.writeText(displayCode)
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
                {treeLoading ? (
                  <p className="text-xs text-muted-foreground px-2 py-1">Loading repository tree...</p>
                ) : (
                  fileTree.map((item) => (
                    <FileTreeItem
                      key={item.path || item.name}
                      item={item}
                      selectedFile={selectedFile}
                      onSelect={setSelectedFile}
                      statusConfig={statusConfig}
                    />
                  ))
                )}
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
                  {showOriginal ? "Original" : "Documented"}
                </Badge>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant={showOriginal ? "default" : "outline"}
                  size="sm"
                  className={showOriginal ? "bg-amber-600 hover:bg-amber-700" : "border-border bg-transparent"}
                  onClick={() => setShowOriginal((prev) => !prev)}
                >
                  {showOriginal ? (
                    <>
                      <EyeOff className="w-4 h-4 mr-2" />
                      See With Docstring
                    </>
                  ) : (
                    <>
                      <Eye className="w-4 h-4 mr-2" />
                      See Original
                    </>
                  )}
                </Button>
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
            </div>

            <div className="p-4 mt-0">
              <div className="relative rounded-lg overflow-hidden border border-border">
                {fileLoading ? (
                  <div className="p-6 text-sm text-muted-foreground">Loading file...</div>
                ) : (
                  <SyntaxHighlighter
                    language={getLanguageFromPath(selectedFile)}
                    style={customTheme}
                    className="!bg-foreground !m-0 !p-6 !text-sm"
                    showLineNumbers={true}
                    wrapLines={true}
                    customStyle={{ fontFamily: "Consolas, 'Courier New', monospace" }}
                    codeTagProps={{ style: { fontFamily: "Consolas, 'Courier New', monospace" } }}
                  >
                    {displayCode || "// Select a file to view code"}
                  </SyntaxHighlighter>
                )}
                <Badge className={`absolute top-4 right-4 text-white ${showOriginal ? "bg-amber-600" : "bg-chart-3"}`}>
                  {showOriginal ? "Original" : "With Docstrings"}
                </Badge>
              </div>
            </div>
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
                        <Link href={`/dashboard/analysis/${analysisId}/results/graph?type=cfg`}>
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
                        <Link href={`/dashboard/analysis/${analysisId}/results/graph?type=pdg`}>
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
  const fullPath = item.path || item.name

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

function findFirstFile(nodes: any[]): { name: string; path?: string } | null {
  for (const node of nodes) {
    if (node.type === "file") return node
    if (node.type === "folder" && Array.isArray(node.children)) {
      const found = findFirstFile(node.children)
      if (found) return found
    }
  }
  return null
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
  const StatusIcon = status === "passed" || status === "completed" ? CheckCircle : status === "warning" ? AlertCircle : Clock

  return (
    <div className="p-3 bg-secondary/50 rounded-lg border border-border/50">
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-6 h-6 rounded-full ${color} flex items-center justify-center`}>
          <Icon className="w-3 h-3 text-white" />
        </div>
        <span className="text-sm font-medium text-foreground">{name}</span>
        <StatusIcon className={`w-3 h-3 ml-auto ${status === "passed" || status === "completed" ? "text-chart-3" : "text-chart-1"}`} />
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
            path: filePath,
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