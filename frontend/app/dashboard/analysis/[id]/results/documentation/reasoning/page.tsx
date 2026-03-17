"use client"

import { useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  ArrowLeft,
  Eye,
  Search,
  PenTool,
  CheckCircle2,
  AlertTriangle,
  Lightbulb,
  Clock,
  Zap,
  Target,
  FileCode,
} from "lucide-react"

const agentOutputs = {
  reader: {
    title: "Reader Agent",
    icon: Eye,
    status: "completed",
    color: "bg-blue-500",
    summary: "Extracted semantic information from 234 functions across 89 files",
    processingTime: "1.8s",
    itemsProcessed: 234,
    confidence: 96.2,
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
    color: "bg-amber-500",
    summary: "Found 156 similar patterns and 34 relevant documentation examples",
    processingTime: "2.1s",
    itemsProcessed: 156,
    confidence: 94.8,
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
    color: "bg-emerald-500",
    summary: "Generated documentation for 234 functions and 45 classes",
    processingTime: "3.2s",
    itemsProcessed: 279,
    confidence: 95.1,
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
    color: "bg-purple-500",
    summary: "Verified 234 docstrings, found 12 issues and fixed 10 automatically",
    processingTime: "1.4s",
    itemsProcessed: 234,
    confidence: 98.7,
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
  const params = useParams()
  const [activeAgent, setActiveAgent] = useState<"reader" | "searcher" | "writer" | "verifier">("reader")
  const agent = agentOutputs[activeAgent]
  const AgentIcon = agent.icon

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href={`/dashboard/analysis/${params.id}/results/documentation`}>
              <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Documentation
              </Button>
            </Link>
            <div className="h-6 w-px bg-border" />
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-amber-500 flex items-center justify-center">
                <Zap className="w-4 h-4 text-white" />
              </div>
              <span className="text-lg font-semibold text-foreground">Agent Reasoning</span>
              <Badge variant="outline" className="ml-2 border-emerald-500/30 text-emerald-600 bg-emerald-500/10">
                Completed
              </Badge>
            </div>
          </div>
          <Link href={`/dashboard/analysis/${params.id}/results/documentation`}>
            <Button className="bg-foreground text-background hover:bg-foreground/90">
              <FileCode className="w-4 h-4 mr-2" />
              View Documentation
            </Button>
          </Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <Tabs value={activeAgent} onValueChange={(v) => setActiveAgent(v as typeof activeAgent)}>
          <TabsList className="mb-8 bg-secondary/50 p-1 rounded-lg">
            {Object.entries(agentOutputs).map(([key, value]) => {
              const Icon = value.icon
              return (
                <TabsTrigger 
                  key={key} 
                  value={key} 
                  className="flex items-center gap-2 data-[state=active]:bg-card data-[state=active]:shadow-sm rounded-md px-4 py-2"
                >
                  <Icon className="w-4 h-4" />
                  {value.title.split(" ")[0]}
                </TabsTrigger>
              )
            })}
          </TabsList>

          <TabsContent value={activeAgent}>
            <div className="grid lg:grid-cols-3 gap-6">
              {/* Main Content */}
              <div className="lg:col-span-2 space-y-6">
                {/* Agent Summary */}
                <Card className="border-border bg-card">
                  <CardHeader className="pb-3">
                    <div className="flex items-center gap-4">
                      <div className={`w-12 h-12 rounded-xl ${agent.color} flex items-center justify-center shadow-lg`}>
                        <AgentIcon className="w-6 h-6 text-white" />
                      </div>
                      <div className="flex-1">
                        <CardTitle className="text-xl">{agent.title}</CardTitle>
                        <p className="text-muted-foreground text-sm mt-1">{agent.summary}</p>
                      </div>
                      <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/30">
                        {agent.status}
                      </Badge>
                    </div>
                  </CardHeader>
                </Card>

                {/* Agent Outputs */}
                <Card className="border-border">
                  <CardHeader className="border-b border-border">
                    <CardTitle className="text-lg">Agent Output</CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    <ScrollArea className="h-[500px]">
                      <div className="p-6">
                      {activeAgent === "reader" && (
                        <div className="space-y-4">
                          {agent.outputs.map((output: any) => (
                            <div key={output.function} className="p-4 bg-secondary/50 rounded-xl border border-border">
                              <div className="flex items-center justify-between mb-3">
                                <code className="text-sm font-mono font-semibold text-foreground bg-foreground/5 px-2 py-1 rounded">{output.function}</code>
                                <Badge variant="outline" className="border-border font-mono text-xs">{output.file}</Badge>
                              </div>
                              <div className="space-y-3 text-sm">
                                <div>
                                  <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium">Purpose</span>
                                  <p className="text-foreground mt-1">{output.semantics.purpose}</p>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                  <div>
                                    <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium">Inputs</span>
                                    <ul className="mt-1 space-y-1">
                                      {output.semantics.inputs.map((input: string) => (
                                        <li key={input} className="text-foreground font-mono text-xs bg-card px-2 py-1 rounded">{input}</li>
                                      ))}
                                    </ul>
                                  </div>
                                  <div>
                                    <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium">Outputs</span>
                                    <p className="text-foreground font-mono text-xs bg-card px-2 py-1 rounded mt-1">{output.semantics.outputs}</p>
                                  </div>
                                </div>
                                <div className="flex items-center justify-between pt-3 border-t border-border">
                                  <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium">Complexity</span>
                                  <Badge className={
                                    output.semantics.complexity === "Low" ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/30" :
                                    output.semantics.complexity === "Medium" ? "bg-amber-500/10 text-amber-600 border-amber-500/30" :
                                    "bg-red-500/10 text-red-600 border-red-500/30"
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
                        <div className="space-y-4">
                          {agent.outputs.map((output: any) => (
                            <div key={output.query} className="p-4 bg-secondary/50 rounded-xl border border-border">
                              <div className="flex items-center gap-2 mb-4">
                                <Search className="w-4 h-4 text-muted-foreground" />
                                <code className="text-sm font-mono font-semibold text-foreground">{output.query}</code>
                              </div>
                              <div className="space-y-3">
                                {output.results.map((result: any) => (
                                  <div key={result.source} className="p-3 bg-card rounded-lg border border-border">
                                    <div className="flex items-center justify-between mb-2">
                                      <span className="font-medium text-foreground text-sm">{result.source}</span>
                                      <Badge variant="outline" className="border-emerald-500/30 text-emerald-600 text-xs">
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
                        <div className="space-y-4">
                          {agent.outputs.map((output: any) => (
                            <div key={output.function} className="p-4 bg-secondary/50 rounded-xl border border-border">
                              <div className="flex items-center justify-between mb-3">
                                <code className="text-sm font-mono font-semibold text-foreground bg-foreground/5 px-2 py-1 rounded">{output.function}</code>
                                <Badge variant="outline" className="border-border font-mono text-xs">{output.file}</Badge>
                              </div>
                              <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg text-xs overflow-x-auto font-mono leading-relaxed">
                                {output.docstring}
                              </pre>
                            </div>
                          ))}
                        </div>
                      )}

                      {activeAgent === "verifier" && (
                        <div className="space-y-4">
                          {agent.outputs.map((output: any) => (
                            <div key={output.function} className="p-4 bg-secondary/50 rounded-xl border border-border">
                              <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2">
                                  <code className="text-sm font-mono font-semibold text-foreground bg-foreground/5 px-2 py-1 rounded">{output.function}</code>
                                  <Badge className={
                                    output.status === "passed" ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/30" :
                                    output.status === "fixed" ? "bg-blue-500/10 text-blue-600 border-blue-500/30" :
                                    "bg-amber-500/10 text-amber-600 border-amber-500/30"
                                  }>
                                    {output.status}
                                  </Badge>
                                </div>
                                <Badge variant="outline" className="border-border font-mono text-xs">{output.file}</Badge>
                              </div>
                              <div className="space-y-2">
                                {output.checks.map((check: any, i: number) => (
                                  <div key={i} className="flex items-start gap-3 p-3 bg-card rounded-lg border border-border">
                                    {check.passed ? (
                                      <CheckCircle2 className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />
                                    ) : (
                                      <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
                                    )}
                                    <div className="flex-1">
                                      <p className="text-sm text-foreground">{check.check}</p>
                                      {check.fix && (
                                        <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1">
                                          <Lightbulb className="w-3 h-3" />
                                          {check.fix}
                                        </p>
                                      )}
                                      {check.warning && (
                                        <p className="text-xs text-amber-600 mt-1 flex items-center gap-1">
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
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              </div>

              {/* Side Panel */}
              <div className="space-y-6">
                {/* Agent Stats */}
                <Card className="border-border">
                  <CardHeader className="pb-3 border-b border-border">
                    <CardTitle className="text-base">Agent Statistics</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-4 space-y-3">
                    <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                          <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                        </div>
                        <span className="text-sm text-muted-foreground">Status</span>
                      </div>
                      <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/30">Completed</Badge>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                          <Clock className="w-4 h-4 text-blue-500" />
                        </div>
                        <span className="text-sm text-muted-foreground">Processing Time</span>
                      </div>
                      <span className="font-mono text-sm font-medium text-foreground">{agent.processingTime}</span>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
                          <Zap className="w-4 h-4 text-amber-500" />
                        </div>
                        <span className="text-sm text-muted-foreground">Items Processed</span>
                      </div>
                      <span className="font-mono text-sm font-medium text-foreground">{agent.itemsProcessed}</span>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
                          <Target className="w-4 h-4 text-purple-500" />
                        </div>
                        <span className="text-sm text-muted-foreground">Confidence</span>
                      </div>
                      <span className="font-mono text-sm font-medium text-foreground">{agent.confidence}%</span>
                    </div>
                  </CardContent>
                </Card>

                {/* Pipeline Overview */}
                <Card className="border-border">
                  <CardHeader className="pb-3 border-b border-border">
                    <CardTitle className="text-base">Pipeline Flow</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-4">
                    <div className="space-y-3">
                      {Object.entries(agentOutputs).map(([key, value], index) => {
                        const Icon = value.icon
                        const isActive = key === activeAgent
                        return (
                          <div key={key} className="relative">
                            <button
                              type="button"
                              onClick={() => setActiveAgent(key as typeof activeAgent)}
                              className={`w-full flex items-center gap-3 p-3 rounded-lg transition-all ${
                                isActive 
                                  ? "bg-foreground/5 border border-foreground/10" 
                                  : "hover:bg-secondary/50"
                              }`}
                            >
                              <div className={`w-8 h-8 rounded-lg ${value.color} flex items-center justify-center`}>
                                <Icon className="w-4 h-4 text-white" />
                              </div>
                              <div className="flex-1 text-left">
                                <p className={`text-sm font-medium ${isActive ? "text-foreground" : "text-muted-foreground"}`}>
                                  {value.title}
                                </p>
                              </div>
                              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                            </button>
                            {index < Object.entries(agentOutputs).length - 1 && (
                              <div className="absolute left-[19px] top-[44px] w-0.5 h-3 bg-border" />
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </CardContent>
                </Card>

                {/* Total Stats */}
                <Card className="border-border bg-gradient-to-br from-amber-500/5 to-amber-500/10">
                  <CardContent className="pt-6">
                    <div className="text-center">
                      <p className="text-xs uppercase tracking-wider text-muted-foreground font-medium mb-2">Total Processing Time</p>
                      <p className="text-3xl font-bold text-foreground">8.5s</p>
                      <p className="text-sm text-muted-foreground mt-2">All agents completed successfully</p>
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
