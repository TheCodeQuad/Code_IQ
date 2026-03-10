"use client"

import { useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { useAnalysis } from "@/lib/analysis-context"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Code2,
  ArrowLeft,
  Eye,
  BookOpen,
  Search,
  PenTool,
  CheckCircle2,
  ChevronRight,
  AlertTriangle,
  Lightbulb,
  MessageSquare,
} from "lucide-react"

const mockAgentOutputs = {
  reader: {
    title: "Reader Agent",
    icon: Eye,
    status: "completed",
    color: "bg-chart-1",
    summary: "Extracted semantic information from 234 functions across 89 files",
    outputs: [
      {
        function: "authenticate_user()",
        file: "auth/handler.py",
        semantics: {
          purpose: "Validates user credentials against the database and returns authentication token",
          inputs: ["username: str", "password: str", "remember_me: bool = False"],
          outputs: ["AuthToken | None"],
          sideEffects: ["Updates last_login timestamp", "Logs authentication attempt"],
          complexity: "Medium",
        },
      },
      {
        function: "process_request()",
        file: "api/gateway.py",
        semantics: {
          purpose: "Routes incoming HTTP requests to appropriate handlers based on endpoint mapping",
          inputs: ["request: Request", "context: Context"],
          outputs: ["Response"],
          sideEffects: ["Increments request counter", "Records latency metrics"],
          complexity: "High",
        },
      },
      {
        function: "validate_schema()",
        file: "utils/validation.py",
        semantics: {
          purpose: "Validates JSON payload against predefined schema definitions",
          inputs: ["data: dict", "schema_name: str"],
          outputs: ["ValidationResult"],
          sideEffects: ["None"],
          complexity: "Low",
        },
      },
    ],
  },
  searcher: {
    title: "Searcher Agent",
    icon: Search,
    status: "completed",
    color: "bg-chart-2",
    summary: "Found 156 similar patterns and 34 relevant documentation examples",
    outputs: [
      {
        query: "authenticate_user pattern",
        results: [
          { source: "Flask-Login documentation", relevance: 0.92, snippet: "User authentication pattern with session management..." },
          { source: "Django Auth docs", relevance: 0.87, snippet: "Token-based authentication implementation..." },
          { source: "OWASP Guidelines", relevance: 0.85, snippet: "Secure authentication best practices..." },
        ],
      },
      {
        query: "API gateway routing",
        results: [
          { source: "FastAPI routing docs", relevance: 0.94, snippet: "Request routing and middleware patterns..." },
          { source: "Kong Gateway patterns", relevance: 0.88, snippet: "Enterprise API gateway architecture..." },
        ],
      },
    ],
  },
  writer: {
    title: "Writer Agent",
    icon: PenTool,
    status: "completed",
    color: "bg-chart-3",
    summary: "Generated documentation for 234 functions and 45 classes",
    outputs: [
      {
        function: "authenticate_user()",
        file: "auth/handler.py",
        docstring: `"""Authenticate a user and return an authentication token.

This function validates the provided credentials against the database,
implementing secure password verification using bcrypt. Upon successful
authentication, it generates a JWT token for subsequent API requests.

Args:
    username: The user's unique identifier (email or username).
    password: The plaintext password to verify.
    remember_me: If True, extends token expiration to 30 days. Defaults to False.

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
"""`,
      },
      {
        function: "process_request()",
        file: "api/gateway.py",
        docstring: `"""Route and process incoming HTTP requests.

This is the main entry point for all API requests. It handles request
routing based on endpoint mapping, applies middleware transformations,
and tracks performance metrics for monitoring.

Args:
    request: The incoming HTTP request object containing headers, body, and metadata.
    context: The request context with authentication and tracing information.

Returns:
    Response: The processed HTTP response with appropriate status code and body.

Note:
    This function automatically applies rate limiting and authentication
    middleware before routing to specific handlers.
"""`,
      },
    ],
  },
  verifier: {
    title: "Verifier Agent",
    icon: CheckCircle2,
    status: "completed",
    color: "bg-chart-4",
    summary: "Verified 234 docstrings, found 12 issues and fixed 10 automatically",
    outputs: [
      {
        function: "authenticate_user()",
        file: "auth/handler.py",
        status: "passed",
        checks: [
          { check: "Parameter documentation matches signature", passed: true },
          { check: "Return type correctly documented", passed: true },
          { check: "All exceptions documented", passed: true },
          { check: "Example code is valid", passed: true },
        ],
      },
      {
        function: "calculate_metrics()",
        file: "analytics/processor.py",
        status: "fixed",
        checks: [
          { check: "Parameter documentation matches signature", passed: true },
          { check: "Return type correctly documented", passed: false, fix: "Updated return type from 'dict' to 'MetricsReport'" },
          { check: "All exceptions documented", passed: true },
        ],
      },
      {
        function: "send_notification()",
        file: "notifications/sender.py",
        status: "warning",
        checks: [
          { check: "Parameter documentation matches signature", passed: true },
          { check: "Return type correctly documented", passed: true },
          { check: "All exceptions documented", passed: false, warning: "Missing documentation for NetworkError exception" },
        ],
      },
    ],
  },
}

export default function AgentReasoningPage() {
  const [activeAgent, setActiveAgent] = useState<"reader" | "searcher" | "writer" | "verifier">("reader")
  const params = useParams()
  const analysisId = params.id as string
  const { getAnalysis } = useAnalysis()
  const analysis = getAnalysis(analysisId)

  // Use real analysis stats for agent summaries when available
  const agentOutputs = analysis?.stats ? {
    ...mockAgentOutputs,
    reader: {
      ...mockAgentOutputs.reader,
      summary: `Extracted semantic information from ${analysis.stats.functions + analysis.stats.methods} functions across ${new Set(Object.values(analysis.components || {}).map(c => c.file_path)).size} files`,
    },
    writer: {
      ...mockAgentOutputs.writer,
      summary: `Generated documentation for ${analysis.stats.functions + analysis.stats.methods} functions and ${analysis.stats.classes} classes`,
    },
    verifier: {
      ...mockAgentOutputs.verifier,
      summary: `Verified ${analysis.stats.total_components} components, ${analysis.stats.components_with_docstrings} with docstrings, ${analysis.stats.components_without_docstrings} without`,
    },
  } : mockAgentOutputs

  const agent = agentOutputs[activeAgent]
  const AgentIcon = agent.icon

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href={`/dashboard/analysis/${analysisId}/pipeline`}>
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Pipeline
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                <Code2 className="w-5 h-5 text-primary-foreground" />
              </div>
              <span className="text-lg font-semibold text-foreground">Agent Reasoning</span>
            </div>
          </div>
          <Link href={`/dashboard/analysis/${analysisId}/results`}>
            <Button className="bg-foreground text-background hover:bg-foreground/90">
              View Documentation
              <ChevronRight className="w-4 h-4 ml-2" />
            </Button>
          </Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <Tabs value={activeAgent} onValueChange={(v) => setActiveAgent(v as typeof activeAgent)}>
          <TabsList className="mb-8 bg-secondary">
            {Object.entries(agentOutputs).map(([key, value]) => {
              const Icon = value.icon
              return (
                <TabsTrigger key={key} value={key} className="flex items-center gap-2">
                  <Icon className="w-4 h-4" />
                  {value.title.split(" ")[0]}
                </TabsTrigger>
              )
            })}
          </TabsList>

          <TabsContent value={activeAgent}>
            <div className="grid lg:grid-cols-3 gap-8">
              {/* Main Content */}
              <div className="lg:col-span-2 space-y-6">
                {/* Agent Summary */}
                <Card className="border-border">
                  <CardHeader className="pb-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-12 h-12 rounded-xl ${agent.color} flex items-center justify-center`}>
                        <AgentIcon className="w-6 h-6 text-card" />
                      </div>
                      <div>
                        <CardTitle className="text-xl">{agent.title}</CardTitle>
                        <p className="text-muted-foreground">{agent.summary}</p>
                      </div>
                    </div>
                  </CardHeader>
                </Card>

                {/* Agent Outputs */}
                <Card className="border-border">
                  <CardHeader>
                    <CardTitle className="text-lg">Agent Output</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[500px] pr-4">
                      {activeAgent === "reader" && (
                        <div className="space-y-6">
                          {agent.outputs.map((output: any) => (
                            <div key={output.function} className="p-4 bg-secondary rounded-lg">
                              <div className="flex items-center justify-between mb-3">
                                <code className="text-sm font-mono font-semibold text-foreground">{output.function}</code>
                                <Badge variant="outline" className="border-border">{output.file}</Badge>
                              </div>
                              <div className="space-y-3 text-sm">
                                <div>
                                  <span className="text-muted-foreground">Purpose:</span>
                                  <p className="text-foreground mt-1">{output.semantics.purpose}</p>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                  <div>
                                    <span className="text-muted-foreground">Inputs:</span>
                                    <ul className="mt-1 space-y-1">
                                      {output.semantics.inputs.map((input: string) => (
                                        <li key={input} className="text-foreground font-mono text-xs">{input}</li>
                                      ))}
                                    </ul>
                                  </div>
                                  <div>
                                    <span className="text-muted-foreground">Outputs:</span>
                                    <p className="text-foreground font-mono text-xs mt-1">{output.semantics.outputs}</p>
                                  </div>
                                </div>
                                <div className="flex items-center justify-between pt-2 border-t border-border">
                                  <span className="text-muted-foreground">Complexity:</span>
                                  <Badge className={
                                    output.semantics.complexity === "Low" ? "bg-chart-3 text-card" :
                                    output.semantics.complexity === "Medium" ? "bg-chart-1 text-card" :
                                    "bg-chart-5 text-card"
                                  }>
                                    {output.semantics.complexity}
                                  </Badge>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {activeAgent === "searcher" && (
                        <div className="space-y-6">
                          {agent.outputs.map((output: any) => (
                            <div key={output.query} className="p-4 bg-secondary rounded-lg">
                              <div className="flex items-center gap-2 mb-4">
                                <Search className="w-4 h-4 text-muted-foreground" />
                                <code className="text-sm font-mono font-semibold text-foreground">{output.query}</code>
                              </div>
                              <div className="space-y-3">
                                {output.results.map((result: any) => (
                                  <div key={result.source} className="p-3 bg-card rounded-lg border border-border">
                                    <div className="flex items-center justify-between mb-2">
                                      <span className="font-medium text-foreground">{result.source}</span>
                                      <Badge variant="outline" className="border-chart-3 text-chart-3">
                                        {Math.round(result.relevance * 100)}% match
                                      </Badge>
                                    </div>
                                    <p className="text-sm text-muted-foreground">{result.snippet}</p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {activeAgent === "writer" && (
                        <div className="space-y-6">
                          {agent.outputs.map((output: any) => (
                            <div key={output.function} className="p-4 bg-secondary rounded-lg">
                              <div className="flex items-center justify-between mb-3">
                                <code className="text-sm font-mono font-semibold text-foreground">{output.function}</code>
                                <Badge variant="outline" className="border-border">{output.file}</Badge>
                              </div>
                              <pre className="bg-foreground text-background p-4 rounded-lg text-xs overflow-x-auto font-mono">
                                {output.docstring}
                              </pre>
                            </div>
                          ))}
                        </div>
                      )}

                      {activeAgent === "verifier" && (
                        <div className="space-y-6">
                          {agent.outputs.map((output: any) => (
                            <div key={output.function} className="p-4 bg-secondary rounded-lg">
                              <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2">
                                  <code className="text-sm font-mono font-semibold text-foreground">{output.function}</code>
                                  <Badge className={
                                    output.status === "passed" ? "bg-chart-3 text-card" :
                                    output.status === "fixed" ? "bg-chart-1 text-card" :
                                    "bg-chart-4 text-card"
                                  }>
                                    {output.status}
                                  </Badge>
                                </div>
                                <Badge variant="outline" className="border-border">{output.file}</Badge>
                              </div>
                              <div className="space-y-2">
                                {output.checks.map((check: any, i: number) => (
                                  <div key={i} className="flex items-start gap-3 p-2 bg-card rounded-lg border border-border">
                                    {check.passed ? (
                                      <CheckCircle2 className="w-4 h-4 text-chart-3 mt-0.5 shrink-0" />
                                    ) : (
                                      <AlertTriangle className="w-4 h-4 text-chart-4 mt-0.5 shrink-0" />
                                    )}
                                    <div className="flex-1">
                                      <p className="text-sm text-foreground">{check.check}</p>
                                      {check.fix && (
                                        <p className="text-xs text-chart-3 mt-1 flex items-center gap-1">
                                          <Lightbulb className="w-3 h-3" />
                                          {check.fix}
                                        </p>
                                      )}
                                      {check.warning && (
                                        <p className="text-xs text-chart-4 mt-1 flex items-center gap-1">
                                          <AlertTriangle className="w-3 h-3" />
                                          {check.warning}
                                        </p>
                                      )}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </ScrollArea>
                  </CardContent>
                </Card>
              </div>

              {/* Side Panel */}
              <div className="space-y-6">
                {/* Agent Stats */}
                <Card className="border-border">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">Agent Statistics</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between p-3 bg-secondary rounded-lg">
                      <span className="text-sm text-muted-foreground">Status</span>
                      <Badge className="bg-chart-3 text-card">Completed</Badge>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-secondary rounded-lg">
                      <span className="text-sm text-muted-foreground">Processing Time</span>
                      <span className="font-mono text-sm text-foreground">2.4s</span>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-secondary rounded-lg">
                      <span className="text-sm text-muted-foreground">Items Processed</span>
                      <span className="font-mono text-sm text-foreground">234</span>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-secondary rounded-lg">
                      <span className="text-sm text-muted-foreground">Confidence</span>
                      <span className="font-mono text-sm text-foreground">94.2%</span>
                    </div>
                  </CardContent>
                </Card>

                {/* Agent Communication */}
                <Card className="border-border">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <MessageSquare className="w-5 h-5" />
                      Inter-Agent Messages
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="p-3 bg-secondary rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge className="bg-chart-1 text-card text-xs">Reader</Badge>
                        <ChevronRight className="w-3 h-3 text-muted-foreground" />
                        <Badge className="bg-chart-3 text-card text-xs">Writer</Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">Semantic context for 234 functions transferred</p>
                    </div>
                    <div className="p-3 bg-secondary rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge className="bg-chart-2 text-card text-xs">Searcher</Badge>
                        <ChevronRight className="w-3 h-3 text-muted-foreground" />
                        <Badge className="bg-chart-3 text-card text-xs">Writer</Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">156 relevant patterns shared</p>
                    </div>
                    <div className="p-3 bg-secondary rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge className="bg-chart-4 text-card text-xs">Verifier</Badge>
                        <ChevronRight className="w-3 h-3 text-muted-foreground" />
                        <Badge className="bg-chart-3 text-card text-xs">Writer</Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">12 corrections requested</p>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
