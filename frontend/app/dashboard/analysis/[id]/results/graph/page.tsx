"use client"

import { useState, useCallback, useRef, useEffect, useMemo } from "react"
import { useParams } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  ZoomIn,
  ZoomOut,
  Download,
  Maximize2,
  RotateCcw,
  Braces,
  Box,
  GitBranch,
  Network,
  ChevronRight,
  Brain,
  Search,
  FileText,
  CheckCheck,
  Save,
  CheckCircle2,
  Circle,
  GripVertical,
  AlertCircle,
  Loader,
} from "lucide-react"

type GraphType = "agents-flow" | "cfg" | "pdg" | "hpg" | "dag"
type ComponentType = "function" | "class" | "method"

interface Component {
  id: string
  name: string
  type: ComponentType
  filePath: string
  parentClass?: string
}

interface DraggableNode {
  id: string
  x: number
  y: number
  label: string
  type: string
}

interface AgentExecution {
  timestamp: string
  agent_name: string
  component_id?: string
  component_name?: string
  action: string
  message: string
  status: "success" | "failed"
  metadata: Record<string, any>
}

interface ComponentFlow {
  component_id: string
  executions: AgentExecution[]
  agents_involved: string[]
  total_executions: number
  status: string
}

interface DAGNode {
  id: string
  name?: string
  dependencies: string[]
}

const DEFAULT_COMPONENTS: Component[] = [
  { id: "comp-1", name: "authenticate_user", type: "function", filePath: "auth/login.py" },
  { id: "comp-2", name: "validate_credentials", type: "function", filePath: "auth/login.py" },
  { id: "comp-3", name: "UserModel", type: "class", filePath: "models/user.py" },
  { id: "comp-4", name: "save", type: "method", filePath: "models/user.py", parentClass: "UserModel" },
  { id: "comp-5", name: "delete", type: "method", filePath: "models/user.py", parentClass: "UserModel" },
  { id: "comp-6", name: "get_by_id", type: "method", filePath: "models/user.py", parentClass: "UserModel" },
  { id: "comp-7", name: "register_user", type: "function", filePath: "auth/register.py" },
  { id: "comp-8", name: "hash_password", type: "function", filePath: "utils/crypto.py" },
  { id: "comp-9", name: "EmailService", type: "class", filePath: "services/email.py" },
  { id: "comp-10", name: "send", type: "method", filePath: "services/email.py", parentClass: "EmailService" },
  { id: "comp-11", name: "validate_email", type: "function", filePath: "utils/validators.py" },
  { id: "comp-12", name: "APIRouter", type: "class", filePath: "api/routes.py" },
]

const graphTypes: { id: GraphType; label: string; description: string; fullName: string }[] = [
  { id: "agents-flow", label: "Agents Flow", fullName: "Agent Processing Flow", description: "Shows the flow of documentation agents processing the component through Reader, Searcher, Writer, and Verifier stages" },
  { id: "cfg", label: "CFG", fullName: "Control Flow Graph", description: "Represents all paths that might be traversed through a program during its execution. Each node represents a basic block of code." },
  { id: "pdg", label: "PDG", fullName: "Program Dependency Graph", description: "Shows data and control dependencies between statements. Useful for program slicing and understanding data flow." },
  { id: "hpg", label: "HPG", fullName: "Hybrid Program Graph", description: "Combines CFG and PDG information into a unified representation for comprehensive code analysis." },
  { id: "dag", label: "DAG", fullName: "Repository Dependency Graph", description: "Shows the dependency relationships between all components in the repository. Each node represents a code component (function, class, method) and edges show dependencies." },
]

const ComponentTypeIcon = ({ type }: { type: ComponentType }) => {
  switch (type) {
    case "function":
      return <Braces className="w-4 h-4" />
    case "class":
      return <Box className="w-4 h-4" />
    case "method":
      return <GitBranch className="w-4 h-4" />
  }
}

export default function GraphsPage() {
  const params = useParams<{ id?: string | string[] }>()
  const routeId = Array.isArray(params?.id) ? params.id[0] : params?.id
  const [components, setComponents] = useState<Component[]>([])
  const [selectedComponent, setSelectedComponent] = useState<Component | null>(null)
  const [selectedGraphType, setSelectedGraphType] = useState<GraphType>("agents-flow")
  const [zoom, setZoom] = useState(100)
  const [componentFlows, setComponentFlows] = useState<Record<string, ComponentFlow>>({})
  const [stats, setStats] = useState<any>(null)
  const [dagData, setDagData] = useState<Record<string, string[]> | null>(null)
  const [dagLoading, setDagLoading] = useState(false)
  const [dagError, setDagError] = useState<string | null>(null)
  const [dagMeta, setDagMeta] = useState<{ file?: string; nodeCount: number; edgeCount: number } | null>(null)
  const [componentFlowLoading, setComponentFlowLoading] = useState(false)
  const [componentFlowError, setComponentFlowError] = useState<string | null>(null)
  const [resolvedRepoScope, setResolvedRepoScope] = useState<string | null>(routeId ?? null)

  // Fetch agent execution data (optional - won't block UI)
  useEffect(() => {
    const fetchData = async () => {
      try {
        let repoScope = routeId

        if (routeId && /^[a-f0-9]{24}$/i.test(routeId)) {
          try {
            const repoResponse = await fetch(`/api/repos/${routeId}`)
            if (repoResponse.ok) {
              const repoData = await repoResponse.json()
              repoScope = repoData.repo_name || routeId
            }
          } catch (repoErr) {
            console.error("Error resolving repo ID:", repoErr)
          }
        }

        setResolvedRepoScope(repoScope || null)

        // Try to fetch all component flows
        const query = new URLSearchParams({ limit: "100" })
        if (repoScope) {
          query.set("repo_id", repoScope)
        }

        const flowsResponse = await fetch(`/api/agents/component/all-flows?${query.toString()}`)
        if (flowsResponse.ok) {
          const flowsData = await flowsResponse.json()
          const flows: Record<string, ComponentFlow> = {}
          const fetchedComponents: Component[] = []
          
          if (flowsData.data && Array.isArray(flowsData.data)) {
            flowsData.data.forEach((flow: ComponentFlow) => {
              flows[flow.component_id] = flow
              
              // Extract component info from flow if available
              const component: Component = {
                id: flow.component_id,
                name: flow.component_id, // Use component_id as default, may be overridden by executions data
                type: "function",
                filePath: "",
              }
              
              // Try to get component details from executions
              if (flow.executions && flow.executions.length > 0) {
                const firstExecution = flow.executions[0]
                if (firstExecution.component_name) {
                  component.name = firstExecution.component_name
                }
                if (firstExecution.metadata?.type) {
                  component.type = firstExecution.metadata.type
                }
                if (firstExecution.metadata?.filePath) {
                  component.filePath = firstExecution.metadata.filePath
                }
              }
              
              fetchedComponents.push(component)
            })
            
            setComponentFlows(flows)
            
            // Use only fetched components from API, not defaults
            if (fetchedComponents.length > 0) {
              setComponents(fetchedComponents)
              // Auto-select first component
              if (selectedComponent === null) {
                setSelectedComponent(fetchedComponents[0])
              }
            }
          }
        }

        // Try to fetch statistics
        const statsQuery = new URLSearchParams()
        if (repoScope) {
          statsQuery.set("repo_id", repoScope)
        }

        const statsResponse = await fetch(
          statsQuery.toString() ? `/api/agents/statistics?${statsQuery.toString()}` : "/api/agents/statistics"
        )
        if (statsResponse.ok) {
          const statsData = await statsResponse.json()
          setStats(statsData.data)
        }

        setDagLoading(true)
        setDagError(null)
        setDagMeta(null)

        // Try to fetch DAG data scoped to the repo
        try {
          const dagQuery = new URLSearchParams()
          if (repoScope) {
            dagQuery.set("repo_id", repoScope)
          }
          const dagUrl = dagQuery.toString() ? `/api/navigator/dag?${dagQuery.toString()}` : "/api/navigator/dag"
          const dagResponse = await fetch(dagUrl)

          if (!dagResponse.ok) {
            const details = await dagResponse.text()
            throw new Error(details || `Unable to fetch DAG (${dagResponse.status})`)
          }

          const dagPayload = await dagResponse.json()
          const dagBody = dagPayload?.data

          if (!dagPayload?.success || !dagBody || typeof dagBody !== "object") {
            throw new Error(dagPayload?.message || "Invalid DAG response")
          }

          const normalized = Object.entries(dagBody).reduce<Record<string, string[]>>((acc, [key, deps]) => {
            acc[key] = Array.isArray(deps) ? deps.filter(Boolean) : []
            return acc
          }, {})

          const nodeCount = Object.keys(normalized).length
          const edgeCount = Object.values(normalized).reduce((sum, deps) => sum + deps.length, 0)

          setDagData(normalized)
          setDagMeta({ file: dagPayload.file, nodeCount, edgeCount })
        } catch (dagErr: any) {
          console.error("Error fetching DAG:", dagErr?.message || dagErr)
          setDagData(null)
          setDagError(dagErr instanceof Error ? dagErr.message : "Failed to load repository DAG")
        } finally {
          setDagLoading(false)
        }
      } catch (err) {
        console.error("Error fetching agent data:", err)
        // Show empty state - don't fallback to hardcoded defaults
      }
    }

    fetchData()
  }, [routeId])

  // Ensure a component is selected when components are fetched
  useEffect(() => {
    if (selectedComponent === null && components.length > 0) {
      setSelectedComponent(components[0])
    }
  }, [components, selectedComponent])

  useEffect(() => {
    if (!selectedComponent?.id) {
      setComponentFlowLoading(false)
      setComponentFlowError(null)
      return
    }

    let cancelled = false
    const componentId = selectedComponent.id

    const fetchComponentFlow = async () => {
      setComponentFlowLoading(true)
      setComponentFlowError(null)

      try {
        const scopeParam = resolvedRepoScope ? `?repo_id=${encodeURIComponent(resolvedRepoScope)}` : ""
        const response = await fetch(`/api/agents/component/${encodeURIComponent(componentId)}/flow${scopeParam}`)

        if (!response.ok) {
          throw new Error(`Unable to fetch execution data for ${componentId}`)
        }

        const payload = await response.json()
        const flowData = (payload?.data || payload) as ComponentFlow | { error: string }

        if ("error" in flowData) {
          throw new Error(flowData.error)
        }

        if (!cancelled) {
          setComponentFlows((prev) => ({
            ...prev,
            [componentId]: flowData as ComponentFlow,
          }))
        }
      } catch (error) {
        if (!cancelled) {
          console.error("Error fetching component flow:", error)
          setComponentFlowError(error instanceof Error ? error.message : "Failed to load component data")
        }
      } finally {
        if (!cancelled) {
          setComponentFlowLoading(false)
        }
      }
    }

    fetchComponentFlow()

    return () => {
      cancelled = true
    }
  }, [selectedComponent?.id, resolvedRepoScope])

  const currentGraph = graphTypes.find((g) => g.id === selectedGraphType)
  const selectedComponentFlow = selectedComponent ? componentFlows[selectedComponent.id] : null

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 25, 200))
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 25, 50))
  const handleReset = () => setZoom(100)

  return (
    <div className="flex gap-4 h-[calc(100vh-200px)] min-h-[700px]">
      {/* Left Panel - Component List */}
      <Card className="w-72 flex-shrink-0 border-stone-200 bg-white">
        <CardHeader className="pb-3 border-b border-stone-100">
          <CardTitle className="text-sm flex items-center gap-2 text-stone-700">
            <Network className="w-4 h-4" />
            Components
          </CardTitle>
          <p className="text-xs text-stone-500 mt-1">{components.length} executed components</p>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[calc(100vh-320px)] min-h-[550px]">
            <div className="p-2 space-y-1">
              {components.length > 0 ? (
                components.map((component) => (
                  <button
                    key={component.id}
                    onClick={() => setSelectedComponent(component)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all ${
                      selectedComponent?.id === component.id
                        ? "bg-amber-50 border border-amber-200"
                        : "hover:bg-stone-50 border border-transparent"
                    }`}
                  >
                    <div
                      className={`w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0 ${
                        component.type === "function"
                          ? "bg-blue-100 text-blue-600"
                          : component.type === "class"
                            ? "bg-purple-100 text-purple-600"
                            : "bg-amber-100 text-amber-600"
                      }`}
                    >
                      <ComponentTypeIcon type={component.type} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`font-medium text-sm truncate ${selectedComponent?.id === component.id ? "text-amber-900" : "text-stone-700"}`}>
                        {component.name}
                      </p>
                      <p className="text-xs text-stone-400 truncate">
                        {component.parentClass ? `${component.parentClass}.` : ""}
                        {component.filePath}
                      </p>
                    </div>
                    {selectedComponent?.id === component.id && (
                      <ChevronRight className="w-4 h-4 flex-shrink-0 text-amber-500" />
                    )}
                  </button>
                ))
              ) : (
                <div className="p-4 text-center">
                  <p className="text-xs text-stone-500">No executed components yet</p>
                </div>
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Center Panel - Graph Visualization */}
      <Card className="flex-1 border-stone-200 bg-white flex flex-col overflow-hidden">
        <CardHeader className="pb-3 border-b border-stone-100 flex-shrink-0">
          <div className="flex items-center justify-between">
            {/* Graph Type Tabs */}
            <Tabs value={selectedGraphType} onValueChange={(v) => setSelectedGraphType(v as GraphType)}>
              <TabsList className="bg-stone-100 p-1">
                {graphTypes.map((graph) => (
                  <TabsTrigger 
                    key={graph.id} 
                    value={graph.id} 
                    className="text-xs data-[state=active]:bg-white data-[state=active]:shadow-sm"
                  >
                    {graph.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>

            {/* Controls */}
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-1">
                <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={handleZoomOut}>
                  <ZoomOut className="w-3.5 h-3.5" />
                </Button>
                <span className="text-xs font-medium min-w-[2.5rem] text-center text-stone-600">{zoom}%</span>
                <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={handleZoomIn}>
                  <ZoomIn className="w-3.5 h-3.5" />
                </Button>
              </div>
              <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={handleReset}>
                <RotateCcw className="w-3.5 h-3.5" />
              </Button>
              <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                <Maximize2 className="w-3.5 h-3.5" />
              </Button>
              <Button variant="outline" size="sm" className="gap-1.5 h-7 text-xs border-stone-200">
                <Download className="w-3.5 h-3.5" />
                Export
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex-1 p-0 overflow-hidden">
          <div
            className="w-full h-full flex items-center justify-center bg-stone-50/50"
            style={{ transform: `scale(${zoom / 100})`, transformOrigin: "center center" }}
          >
            {selectedComponent && selectedGraphType === "agents-flow" ? (
              <AgentsFlowGraph 
                component={selectedComponent}
                componentFlow={selectedComponentFlow || undefined}
              />
            ) : selectedComponent && selectedGraphType === "dag" ? (
              <DAGGraph
                dagData={dagData}
                selectedComponentId={selectedComponent.id}
                isLoading={dagLoading}
                error={dagError}
                dagMeta={dagMeta}
              />
            ) : selectedComponent ? (
              <DraggableGraph type={selectedGraphType} component={selectedComponent} />
            ) : (
              <div className="flex items-center justify-center h-full">
                <p className="text-stone-400 text-sm">Select a component to view</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Right Panel - Details */}
      <Card className="w-80 flex-shrink-0 border-stone-200 bg-white flex flex-col overflow-hidden">
        <CardHeader className="pb-3 border-b border-stone-100 flex-shrink-0">
          <CardTitle className="text-sm text-stone-700">Graph Details</CardTitle>
        </CardHeader>
        <ScrollArea className="flex-1">
          <CardContent className="space-y-5 p-4">
            {/* Current View Info */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
                Current View
              </h4>
              <div className="p-3 bg-amber-50 rounded-lg border border-amber-100">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-stone-500">Graph Type</span>
                  <Badge className="bg-amber-400 text-white text-xs">{currentGraph?.label}</Badge>
                </div>
                <p className="text-sm font-medium text-stone-800 mb-1">{currentGraph?.fullName}</p>
                <p className="text-xs text-stone-500 leading-relaxed">
                  {currentGraph?.description}
                </p>
              </div>
            </div>

            {/* Component Info */}
            {selectedComponent && (
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
                  Selected Component
                </h4>
                <div className="p-3 bg-stone-50 rounded-lg border border-stone-100">
                  <div className="flex items-center gap-2 mb-3">
                    <div
                      className={`w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0 ${
                        selectedComponent.type === "function"
                          ? "bg-blue-100 text-blue-600"
                          : selectedComponent.type === "class"
                            ? "bg-purple-100 text-purple-600"
                            : "bg-amber-100 text-amber-600"
                      }`}
                    >
                      <ComponentTypeIcon type={selectedComponent.type} />
                    </div>
                    <div>
                      <p className="font-medium text-sm text-stone-800">{selectedComponent.name}</p>
                      <p className="text-xs text-stone-400 capitalize">{selectedComponent.type}</p>
                    </div>
                  </div>
                  <div className="text-xs space-y-2 pt-2 border-t border-stone-200">
                    <div className="flex justify-between">
                      <span className="text-stone-400">File</span>
                      <span className="font-mono text-stone-600">{selectedComponent.filePath}</span>
                    </div>
                    {selectedComponent.parentClass && (
                      <div className="flex justify-between">
                        <span className="text-stone-400">Parent Class</span>
                        <span className="font-mono text-stone-600">{selectedComponent.parentClass}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Execution Flow Info - Only show if data is available */}
            {selectedComponent && (
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
                  Execution Flow
                </h4>
                <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-100 min-h-[88px]">
                  {componentFlowLoading ? (
                    <div className="flex items-center gap-2 text-xs text-emerald-700">
                      <Loader className="w-3.5 h-3.5 animate-spin" />
                      <span>Fetching execution data...</span>
                    </div>
                  ) : componentFlowError ? (
                    <div className="flex items-center gap-2 text-xs text-red-600">
                      <AlertCircle className="w-3.5 h-3.5" />
                      <span>{componentFlowError}</span>
                    </div>
                  ) : selectedComponentFlow ? (
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between">
                        <span className="text-stone-600">Total Executions</span>
                        <span className="font-semibold text-emerald-700">{selectedComponentFlow.total_executions}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-stone-600">Agents Involved</span>
                        <span className="font-semibold text-emerald-700">{selectedComponentFlow.agents_involved.length}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-stone-600">Status</span>
                        <Badge
                          className={`text-[10px] px-2 py-0 ${selectedComponentFlow.status === "success" ? "bg-emerald-500" : "bg-red-500"} text-white border-transparent`}
                        >
                          {selectedComponentFlow.status === "success" ? "Success" : "Failed"}
                        </Badge>
                      </div>
                      <div className="flex flex-wrap gap-1 pt-2 border-t border-emerald-200">
                        {selectedComponentFlow.agents_involved.length > 0 ? (
                          selectedComponentFlow.agents_involved.map((agent) => (
                            <Badge key={agent} variant="outline" className="text-xs bg-emerald-100 border-emerald-200 text-emerald-700">
                              {agent}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-xs text-stone-500">No agents recorded</span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-stone-500">No execution data found for this component.</p>
                  )}
                </div>
              </div>
            )}

            {/* Statistics - Only show if available */}
            {stats && (
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
                  Overall Statistics
                </h4>
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 bg-stone-50 rounded-lg text-center border border-stone-100">
                    <p className="text-lg font-semibold text-stone-800">{stats.total_executions || 0}</p>
                    <p className="text-xs text-stone-400">Total Executions</p>
                  </div>
                  <div className="p-2.5 bg-stone-50 rounded-lg text-center border border-stone-100">
                    <p className="text-lg font-semibold text-emerald-600">{stats.success_rate || 0}%</p>
                    <p className="text-xs text-stone-400">Success Rate</p>
                  </div>
                  <div className="p-2.5 bg-stone-50 rounded-lg text-center border border-stone-100">
                    <p className="text-lg font-semibold text-stone-800">{stats.success_count || 0}</p>
                    <p className="text-xs text-stone-400">Successes</p>
                  </div>
                  <div className="p-2.5 bg-stone-50 rounded-lg text-center border border-stone-100">
                    <p className="text-lg font-semibold text-red-600">{stats.failure_count || 0}</p>
                    <p className="text-xs text-stone-400">Failures</p>
                  </div>
                </div>
              </div>
            )}

            {selectedGraphType === "dag" && (
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
                  Repository DAG Snapshot
                </h4>
                <div className="p-3 rounded-lg border border-stone-100 bg-stone-50">
                  {dagLoading ? (
                    <div className="flex items-center gap-2 text-xs text-stone-500">
                      <Loader className="w-3.5 h-3.5 animate-spin" />
                      <span>Loading dependency graph…</span>
                    </div>
                  ) : dagError ? (
                    <div className="flex items-center gap-2 text-xs text-red-600">
                      <AlertCircle className="w-3.5 h-3.5" />
                      <span>{dagError}</span>
                    </div>
                  ) : dagMeta ? (
                    <div className="text-xs text-stone-600 space-y-2">
                      <div className="flex justify-between">
                        <span>Components</span>
                        <span className="font-semibold text-stone-800">{dagMeta.nodeCount}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Dependencies</span>
                        <span className="font-semibold text-stone-800">{dagMeta.edgeCount}</span>
                      </div>
                      {dagMeta.file && (
                        <div className="flex justify-between">
                          <span>Source File</span>
                          <span className="font-mono text-[11px] text-stone-500 truncate max-w-[140px]">{dagMeta.file}</span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-stone-500">No DAG metadata available for this repository.</p>
                  )}
                </div>
              </div>
            )}

            {/* Agent Breakdown */}
            {stats?.by_agent && (
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
                  Agent Breakdown
                </h4>
                <div className="space-y-2">
                  {Object.entries(stats.by_agent).map(([agent, data]: [string, any]) => (
                    <div key={agent} className="p-2 bg-stone-50 rounded-lg border border-stone-100">
                      <div className="flex justify-between items-center mb-1">
                        <p className="text-xs font-semibold text-stone-700 capitalize">{agent}</p>
                        <Badge variant="outline" className="text-xs">{data.total}</Badge>
                      </div>
                      <div className="flex gap-2 text-xs text-stone-500">
                        <span>✓ {data.completed}</span>
                        <span>✗ {data.errors}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tips */}
            <div className="p-3 bg-blue-50 rounded-lg border border-blue-100">
              <div className="flex items-start gap-2">
                <GripVertical className="w-4 h-4 text-blue-500 mt-0.5" />
                <div>
                  <p className="text-xs font-medium text-blue-800">Tip: Drag Nodes</p>
                  <p className="text-xs text-blue-600 mt-0.5">Click and drag any node to reposition it in the graph view.</p>
                </div>
              </div>
            </div>
          </CardContent>
        </ScrollArea>
      </Card>
    </div>
  )
}

// Agents Flow Graph - Shows default agent flow with highlighting for executed agents
function AgentsFlowGraph({ component, componentFlow }: { component: Component; componentFlow?: ComponentFlow }) {
  // Determine which agents were involved in this component's execution
  const executedAgents = componentFlow?.agents_involved.map(a => a.toLowerCase()) || []
  const executionMessages = componentFlow?.executions?.map((e) => (e.message || "").toLowerCase()) || []

  const hasMessage = (patterns: RegExp[]) =>
    executionMessages.some((message) => patterns.some((pattern) => pattern.test(message)))

  const readerNeedsContext = hasMessage([
    /reader-searcher converged/,
    /need_context\s*=\s*true/,
    /need context/,
    /needs more context/,
  ])

  const readerContextNotNeeded = hasMessage([
    /context not needed/,
    /need_context\s*=\s*false/,
  ])

  const searcherContextFound = hasMessage([
    /reader-searcher converged/,
    /context found/,
  ])

  const searcherContextNotFound = hasMessage([
    /context not found/,
    /need_context\s*=\s*true.*more_context\s*=\s*true/,
  ])

  const verifierToWriterLoop = hasMessage([
    /verifier rejected/,
    /needs revision/,
    /writer refining with feedback/,
    /need_revision\s*=\s*true/,
  ])

  const verifierToReaderLoop = hasMessage([
    /verifier needs more context/,
    /returning to reader-searcher/,
    /more_context\s*=\s*true/,
    /needs more context/,
  ])

  const verifierAccepted = hasMessage([
    /verifier accepted/,
    /need_revision\s*=\s*false,?\s*more_context\s*=\s*false/,
  ]) || (componentFlow?.status === "success" && executedAgents.length > 0)
  
  // Only highlight if we have actual execution data
  const isAgentExecuted = (agentName: string) => {
    if (executedAgents.length === 0) return false // No data = don't highlight
    return executedAgents.includes(agentName.toLowerCase())
  }

  // Check if connection should be highlighted (both agents were executed)
  const isConnectionHighlighted = (agent1: string, agent2: string) => {
    return executedAgents.length > 0 && 
           executedAgents.includes(agent1.toLowerCase()) && 
           executedAgents.includes(agent2.toLowerCase())
  }

  return (
    <div className="relative w-full h-full flex items-center justify-center p-8">
      <svg
        viewBox="0 0 520 350"
        className="w-full max-w-[560px] h-auto"
        style={{ minHeight: "340px" }}
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Define arrowheads */}
        <defs>
          <marker id="arrowhead-gray" markerWidth="6" markerHeight="5" refX="5" refY="2.5" orient="auto">
            <polygon points="0 0, 6 2.5, 0 5" fill="#d1d5db" />
          </marker>
          <marker id="arrowhead-emerald" markerWidth="6" markerHeight="5" refX="5" refY="2.5" orient="auto">
            <polygon points="0 0, 6 2.5, 0 5" fill="#10b981" />
          </marker>
          <marker id="arrowhead-amber" markerWidth="6" markerHeight="5" refX="5" refY="2.5" orient="auto">
            <polygon points="0 0, 6 2.5, 0 5" fill="#f59e0b" />
          </marker>
        </defs>

        {/* Arrows - KEY EXECUTION PATH */}
        <path 
          d="M 140 60 L 300 60" 
          fill="none" 
          stroke={readerNeedsContext ? "#10b981" : "#d1d5db"} 
          strokeWidth="2" 
          markerEnd={readerNeedsContext ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} 
        />
        <text x="220" y="50" textAnchor="middle" className="text-[10px] font-medium" fill={readerNeedsContext ? "#059669" : "#9ca3af"}>Need Context</text>

        {/* Searcher to Writer arrow */}
        <path 
          d="M 400 80 Q 445 115, 400 155" 
          fill="none" 
          stroke={searcherContextFound ? "#10b981" : "#d1d5db"} 
          strokeWidth="2" 
          markerEnd={searcherContextFound ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} 
        />
        <text x="475" y="95" textAnchor="middle" className="text-[10px] font-medium" fill={searcherContextFound ? "#059669" : "#9ca3af"}>
          <tspan x="475" dy="0">Context</tspan>
          <tspan x="475" dy="13">Found</tspan>
        </text>

        {/* Alternative path - Reader bypass */}
        <path 
          d="M 95 82 C 95 130, 240 105, 305 160" 
          fill="none" 
          stroke={readerContextNotNeeded ? "#10b981" : "#d1d5db"} 
          strokeWidth="2" 
          markerEnd={readerContextNotNeeded ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} 
        />
        <text x="155" y="125" textAnchor="middle" className="text-[10px] font-medium" fill={readerContextNotNeeded ? "#059669" : "#9ca3af"}>
          <tspan x="155" dy="0">Context</tspan>
          <tspan x="155" dy="13">Not Needed</tspan>
        </text>

        {/* Writer to Verifier */}
        <path 
          d="M 355 195 L 355 220" 
          fill="none" 
          stroke={isConnectionHighlighted("writer", "verifier") ? "#10b981" : "#d1d5db"} 
          strokeWidth="2" 
          markerEnd={isConnectionHighlighted("writer", "verifier") ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} 
        />
        <text x="295" y="205" textAnchor="middle" className="text-[10px] font-medium" fill={isConnectionHighlighted("writer", "verifier") ? "#059669" : "#9ca3af"}>
          <tspan x="295" dy="0">Docstring</tspan>
          <tspan x="295" dy="13">Generated</tspan>
        </text>

        {/* Alternative path - Needs Revision */}
        <path d="M 400 230 Q 455 195, 400 165" fill="none" stroke={verifierToWriterLoop ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={verifierToWriterLoop ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />
        <text x="478" y="195" textAnchor="middle" className="text-[10px] font-medium" fill={verifierToWriterLoop ? "#059669" : "#9ca3af"}>
          <tspan x="478" dy="0">Needs</tspan>
          <tspan x="478" dy="13">Revision</tspan>
        </text>

        {/* Alternative path - Needs More Context */}
        <path d="M 305 255 C 170 290, 50 215, 50 120 C 50 75, 70 60, 95 60" fill="none" stroke={verifierToReaderLoop ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={verifierToReaderLoop ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />
        <text x="100" y="270" textAnchor="middle" className="text-[10px] font-medium" fill={verifierToReaderLoop ? "#059669" : "#9ca3af"}>
          <tspan x="100" dy="0">Needs More</tspan>
          <tspan x="100" dy="13">Context</tspan>
        </text>

        {/* Verifier to completion */}
        <path 
          d="M 355 262 L 355 290" 
          fill="none" 
          stroke={verifierAccepted ? "#10b981" : "#d1d5db"} 
          strokeWidth="2" 
          markerEnd={verifierAccepted ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} 
        />
        <text x="400" y="280" textAnchor="middle" className="text-[10px] font-medium" fill={verifierAccepted ? "#059669" : "#9ca3af"}>Accepted</text>

        {/* Alternative - Context Not Found */}
        <path d="M 300 40 Q 220 15, 140 40" fill="none" stroke={searcherContextNotFound ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={searcherContextNotFound ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />
        <text x="220" y="8" textAnchor="middle" className="text-[10px] font-medium" fill={searcherContextNotFound ? "#059669" : "#9ca3af"}>
          <tspan x="220" dy="0">Context</tspan>
          <tspan x="220" dy="13">Not Found</tspan>
        </text>

        {/* Agent Nodes */}
        <AgentNode 
          label="Reader" 
          x={95} 
          y={60} 
          status={isAgentExecuted("reader") ? "completed" : "pending"} 
        />
        <AgentNode 
          label="Searcher" 
          x={355} 
          y={60} 
          status={isAgentExecuted("searcher") ? "completed" : "pending"} 
        />
        <AgentNode 
          label="Writer" 
          x={355} 
          y={175} 
          status={isAgentExecuted("writer") ? "completed" : "pending"} 
        />
        <AgentNode 
          label="Verifier" 
          x={355} 
          y={240} 
          status={isAgentExecuted("verifier") ? "completed" : "pending"} 
        />
        <AgentNode 
          label="Docstring Inserted" 
          x={355} 
          y={315} 
          status={componentFlow?.status === "success" && executedAgents.length > 0 ? "completed" : "pending"} 
          isLarge 
        />
      </svg>
    </div>
  )
}

// Agent Node Component
function AgentNode({
  label,
  x,
  y,
  status,
  isLarge = false,
}: {
  label: string
  x: number
  y: number
  status: "pending" | "running" | "completed"
  isLarge?: boolean
}) {
  const rx = isLarge ? 80 : 52
  const ry = isLarge ? 26 : 20
  const foreignWidth = isLarge ? 156 : 100

  const getStatusStyles = () => {
    switch (status) {
      case "completed":
        return {
          fill: "#dcfce7",
          stroke: "#10b981",
          textColor: "#166534",
          iconColor: "#10b981",
        }
      case "running":
        return {
          fill: "#fef3c3",
          stroke: "#f59e0b",
          textColor: "#92400e",
          iconColor: "#f59e0b",
        }
      default: // pending
        return {
          fill: "#f3f4f6",
          stroke: "#9ca3af",
          textColor: "#4b5563",
          iconColor: "#9ca3af",
        }
    }
  }

  const styles = getStatusStyles()

  return (
    <g transform={`translate(${x}, ${y})`}>
      <ellipse cx="0" cy="0" rx={rx} ry={ry} fill={styles.fill} stroke={styles.stroke} strokeWidth="1.5" />
      <foreignObject x={-foreignWidth / 2} y="-14" width={foreignWidth} height="28">
        <div className="w-full h-full flex items-center justify-center gap-1.5">
          {status === "completed" ? (
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" style={{ color: styles.iconColor }} />
          ) : status === "running" ? (
            <Circle className="w-4 h-4 flex-shrink-0 animate-pulse" style={{ color: styles.iconColor }} />
          ) : (
            <Circle className="w-4 h-4 flex-shrink-0" style={{ color: styles.iconColor }} />
          )}
          <span className="text-[11px] font-semibold leading-none" style={{ color: styles.textColor }}>
            {label}
          </span>
        </div>
      </foreignObject>
    </g>
  )
}

// DAG Graph Component - Shows repository dependency graph
function DAGGraph({
  dagData,
  selectedComponentId,
  isLoading,
  error,
  dagMeta,
}: {
  dagData: Record<string, string[]> | null
  selectedComponentId: string
  isLoading: boolean
  error: string | null
  dagMeta: { file?: string; nodeCount: number; edgeCount: number } | null
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [nodes, setNodes] = useState<DraggableNode[]>([])
  const [dragging, setDragging] = useState<string | null>(null)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [scopeMode, setScopeMode] = useState<"component" | "repository">("component")

  useEffect(() => {
    if (!selectedComponentId) {
      setScopeMode("repository")
    }
  }, [selectedComponentId])

  const adjacency = useMemo(() => {
    const map = new Map<string, string[]>()
    if (!dagData) {
      return map
    }

    Object.entries(dagData).forEach(([node, deps]) => {
      map.set(node, Array.isArray(deps) ? deps.filter(Boolean) : [])
    })

    const missing = new Set<string>()
    map.forEach((deps) => {
      deps.forEach((dep) => {
        if (!map.has(dep)) {
          missing.add(dep)
        }
      })
    })
    missing.forEach((dep) => map.set(dep, []))

    return map
  }, [dagData])

  const reverseMap = useMemo(() => {
    const rev = new Map<string, Set<string>>()
    adjacency.forEach((_, node) => rev.set(node, new Set()))
    adjacency.forEach((deps, node) => {
      deps.forEach((dep) => {
        if (!rev.has(dep)) {
          rev.set(dep, new Set())
        }
        rev.get(dep)!.add(node)
      })
    })
    return rev
  }, [adjacency])

  const dependenciesOfSelected = useMemo(() => {
    if (!selectedComponentId || !adjacency.has(selectedComponentId)) {
      return new Set<string>()
    }
    return new Set(adjacency.get(selectedComponentId))
  }, [adjacency, selectedComponentId])

  const dependentsOfSelected = useMemo(() => {
    if (!selectedComponentId || !reverseMap.has(selectedComponentId)) {
      return new Set<string>()
    }
    return new Set(reverseMap.get(selectedComponentId))
  }, [reverseMap, selectedComponentId])

  const scopedNodeIds = useMemo(() => {
    if (!adjacency.size) return []
    if (
      scopeMode === "repository" ||
      !selectedComponentId ||
      !adjacency.has(selectedComponentId)
    ) {
      return Array.from(adjacency.keys())
    }

    const maxNodes = 80
    const queue: string[] = [selectedComponentId]
    const seen = new Set(queue)

    let idx = 0
    while (idx < queue.length && seen.size < maxNodes) {
      const current = queue[idx++]
      adjacency.get(current)?.forEach((dep) => {
        if (!seen.has(dep) && seen.size < maxNodes) {
          seen.add(dep)
          queue.push(dep)
        }
      })
      reverseMap.get(current)?.forEach((parent) => {
        if (!seen.has(parent) && seen.size < maxNodes) {
          seen.add(parent)
          queue.push(parent)
        }
      })
    }

    return Array.from(seen)
  }, [adjacency, reverseMap, scopeMode, selectedComponentId])

  const scopedEdges = useMemo(() => {
    const scopedSet = new Set(scopedNodeIds)
    const edges: [string, string][] = []
    scopedNodeIds.forEach((node) => {
      adjacency.get(node)?.forEach((dep) => {
        if (scopedSet.has(dep)) {
          edges.push([node, dep])
        }
      })
    })
    return edges
  }, [scopedNodeIds, adjacency])

  const layoutBlueprint = useMemo(() => {
    if (!scopedNodeIds.length) return []

    const scopedSet = new Set(scopedNodeIds)
    const reverseEdges = new Map<string, Set<string>>()
    scopedNodeIds.forEach((node) => reverseEdges.set(node, new Set()))
    scopedEdges.forEach(([from, to]) => {
      if (!reverseEdges.has(to)) {
        reverseEdges.set(to, new Set())
      }
      reverseEdges.get(to)!.add(from)
    })

    const dependencyCount = new Map<string, number>()
    scopedNodeIds.forEach((node) => {
      const count = (adjacency.get(node) || []).filter((dep) => scopedSet.has(dep)).length
      dependencyCount.set(node, count)
    })

    const seeds = scopedNodeIds.filter((node) => (dependencyCount.get(node) || 0) === 0)
    const seedSource = seeds.length
      ? seeds
      : scopedNodeIds.includes(selectedComponentId)
        ? [selectedComponentId]
        : [scopedNodeIds[0]]
    const queue: Array<[string, number]> = seedSource.map((node) => [node, 0])

    const levels = new Map<string, number>()
    const visited = new Set<string>()

    while (queue.length) {
      const [node, level] = queue.shift()!
      if (!node || visited.has(node) || !scopedSet.has(node)) continue
      visited.add(node)
      if (!levels.has(node)) {
        levels.set(node, level)
      }
      reverseEdges.get(node)?.forEach((dependent) => {
        if (!visited.has(dependent)) {
          queue.push([dependent, level + 1])
        }
      })
    }

    scopedNodeIds.forEach((node) => {
      if (!levels.has(node)) {
        const deps = adjacency.get(node)?.filter((dep) => scopedSet.has(dep)) ?? []
        const fallbackLevel = deps.reduce((max, dep) => Math.max(max, levels.get(dep) ?? 0), 0)
        levels.set(node, fallbackLevel)
      }
    })

    const levelBuckets = new Map<number, string[]>()
    levels.forEach((level, node) => {
      const bucket = levelBuckets.get(level) ?? []
      bucket.push(node)
      levelBuckets.set(level, bucket)
    })

    const sortedLevels = Array.from(levelBuckets.keys()).sort((a, b) => a - b)
    const levelIndexMap = new Map<number, number>()
    sortedLevels.forEach((level, idx) => levelIndexMap.set(level, idx))

    const canvasWidth = 820
    const canvasHeight = 560
    const horizontalPadding = 80
    const verticalPadding = 60
    const usableWidth = canvasWidth - horizontalPadding * 2
    const usableHeight = canvasHeight - verticalPadding * 2
    const verticalSteps = Math.max(sortedLevels.length - 1, 1)
    const verticalSpacing = usableHeight / verticalSteps

    return scopedNodeIds.map((node) => {
      const logicalLevel = levels.get(node) ?? 0
      const normalizedLevelIndex = levelIndexMap.get(logicalLevel) ?? 0
      const nodesInLevel = levelBuckets.get(logicalLevel) ?? [node]
      const indexInLevel = nodesInLevel.indexOf(node)

      const x =
        nodesInLevel.length <= 1
          ? canvasWidth / 2
          : horizontalPadding + (indexInLevel / (nodesInLevel.length - 1 || 1)) * usableWidth
      const y =
        sortedLevels.length <= 1
          ? canvasHeight / 2
          : verticalPadding + normalizedLevelIndex * verticalSpacing

      let type: string = "neutral"
      if (node === selectedComponentId) type = "selected"
      else if (dependenciesOfSelected.has(node)) type = "dependency"
      else if (dependentsOfSelected.has(node)) type = "dependent"

      return {
        id: node,
        x,
        y,
        label: node.split(".").pop() || node,
        type,
      }
    })
  }, [
    scopedNodeIds,
    scopedEdges,
    adjacency,
    selectedComponentId,
    dependenciesOfSelected,
    dependentsOfSelected,
  ])

  useEffect(() => {
    setNodes(layoutBlueprint)
  }, [layoutBlueprint])

  const highlightIds = useMemo(() => {
    const set = new Set<string>()
    if (selectedComponentId) {
      set.add(selectedComponentId)
      dependenciesOfSelected.forEach((id) => set.add(id))
      dependentsOfSelected.forEach((id) => set.add(id))
    }
    return set
  }, [selectedComponentId, dependenciesOfSelected, dependentsOfSelected])

  const handleMouseDown = (e: React.MouseEvent, nodeId: string) => {
    const node = nodes.find((n) => n.id === nodeId)
    if (!node) return
    setDragging(nodeId)
    setOffset({
      x: e.clientX - node.x,
      y: e.clientY - node.y,
    })
  }

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!dragging) return
      setNodes((prev) =>
        prev.map((node) =>
          node.id === dragging
            ? { ...node, x: e.clientX - offset.x, y: e.clientY - offset.y }
            : node
        )
      )
    },
    [dragging, offset]
  )

  const handleMouseUp = () => {
    setDragging(null)
  }

  const palette: Record<string, { fill: string; stroke: string; text: string }> = {
    selected: { fill: "#dbeafe", stroke: "#2563eb", text: "#1e3a8a" },
    dependency: { fill: "#dcfce7", stroke: "#16a34a", text: "#166534" },
    dependent: { fill: "#fef3c7", stroke: "#d97706", text: "#92400e" },
    neutral: { fill: "#f4f4f5", stroke: "#cbd5f5", text: "#475569" },
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center w-full h-full">
        <div className="flex items-center gap-2 text-sm text-stone-500">
          <Loader className="w-4 h-4 animate-spin" />
          <span>Loading dependency graph…</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center w-full h-full">
        <div className="flex items-center gap-2 text-sm text-red-600">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
        </div>
      </div>
    )
  }

  if (!dagData || Object.keys(dagData).length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <Network className="w-12 h-12 text-stone-300 mx-auto mb-2" />
          <p className="text-stone-400 text-sm">No DAG data available</p>
          <p className="text-xs text-stone-300 mt-1">Run the navigator to generate the dependency graph</p>
        </div>
      </div>
    )
  }

  if (!scopedNodeIds.length) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-stone-500">No nodes to display for this scope.</p>
      </div>
    )
  }

  const focusDisabled = !selectedComponentId || !adjacency.has(selectedComponentId)

  return (
    <div className="relative w-full h-full">
      <div className="absolute top-3 right-3 flex items-center gap-2 z-10">
        <div className="px-3 py-1.5 rounded-md bg-white/80 border border-stone-200 shadow-sm">
          <p className="text-[11px] font-semibold text-stone-700">
            {scopedNodeIds.length} nodes · {scopedEdges.length} edges
          </p>
          <p className="text-[10px] text-stone-400">
            {scopeMode === "repository" ? "Entire repository" : "Component neighborhood"}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="h-8 text-xs"
          onClick={() => setScopeMode((prev) => (prev === "component" ? "repository" : "component"))}
          disabled={focusDisabled}
        >
          {scopeMode === "component" ? "Show Full DAG" : "Focus on Component"}
        </Button>
      </div>

      {dagMeta?.file && (
        <div className="absolute top-3 left-3 z-10 px-3 py-1.5 bg-white/80 border border-stone-200 rounded-md shadow-sm text-[10px] text-stone-500">
          <span className="font-semibold text-stone-700">File:</span> {dagMeta.file}
        </div>
      )}

      <svg
        ref={svgRef}
        viewBox="0 0 820 560"
        className="w-full h-full"
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <defs>
          <marker id="arrow-dag-muted" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#cbd5f5" />
          </marker>
          <marker id="arrow-dag-active" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#2563eb" />
          </marker>
        </defs>

        <rect width="820" height="560" fill="#fafafa" />

        {scopedEdges.map(([from, to], idx) => {
          const fromNode = nodes.find((n) => n.id === from)
          const toNode = nodes.find((n) => n.id === to)
          if (!fromNode || !toNode) return null

          const isHighlighted = highlightIds.has(from) || highlightIds.has(to)

          return (
            <path
              key={`${from}-${to}-${idx}`}
              d={`M ${fromNode.x} ${fromNode.y + 18} Q ${(fromNode.x + toNode.x) / 2} ${(fromNode.y + toNode.y) / 2} ${toNode.x} ${toNode.y - 18}`}
              fill="none"
              stroke={isHighlighted ? "#2563eb" : "#cbd5f5"}
              strokeWidth={isHighlighted ? 2.4 : 1.4}
              markerEnd={isHighlighted ? "url(#arrow-dag-active)" : "url(#arrow-dag-muted)"}
              opacity={isHighlighted ? 0.95 : 0.7}
            />
          )
        })}

        {nodes.map((node) => {
          const colors = palette[node.type] || palette.neutral
          const label = node.label.length > 18 ? `${node.label.substring(0, 15)}…` : node.label

          return (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              onMouseDown={(e) => handleMouseDown(e, node.id)}
              style={{ cursor: dragging === node.id ? "grabbing" : "grab" }}
            >
              <rect
                x="-55"
                y="-20"
                width="110"
                height="40"
                rx="6"
                fill={colors.fill}
                stroke={colors.stroke}
                strokeWidth={node.type === "selected" ? 2.5 : 1.5}
              />
              <text
                textAnchor="middle"
                dy="4"
                fontSize="11"
                fontWeight={node.type === "selected" ? "600" : "500"}
                fill={colors.text}
                pointerEvents="none"
              >
                {label}
              </text>
              <title>{node.id}</title>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

// Draggable Graph Component for CFG, PDG, HPG
function DraggableGraph({ type, component }: { type: GraphType; component: Component }) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [nodes, setNodes] = useState<DraggableNode[]>([])
  const [dragging, setDragging] = useState<string | null>(null)
  const [offset, setOffset] = useState({ x: 0, y: 0 })

  // Generate different node layouts based on graph type
  useEffect(() => {
    const generateNodes = (): DraggableNode[] => {
      switch (type) {
        case "cfg":
          return [
            { id: "entry", x: 250, y: 40, label: "Entry", type: "entry" },
            { id: "cond1", x: 250, y: 110, label: "if cond", type: "condition" },
            { id: "block1", x: 120, y: 180, label: "Block A", type: "block" },
            { id: "block2", x: 380, y: 180, label: "Block B", type: "block" },
            { id: "cond2", x: 120, y: 250, label: "while loop", type: "condition" },
            { id: "block3", x: 120, y: 320, label: "Block C", type: "block" },
            { id: "merge", x: 250, y: 320, label: "Merge", type: "merge" },
            { id: "exit", x: 250, y: 390, label: "Exit", type: "exit" },
          ]
        case "pdg":
          return [
            { id: "func", x: 250, y: 50, label: component.name, type: "function" },
            { id: "param1", x: 100, y: 130, label: "param: user", type: "param" },
            { id: "param2", x: 250, y: 130, label: "param: data", type: "param" },
            { id: "param3", x: 400, y: 130, label: "param: opts", type: "param" },
            { id: "var1", x: 100, y: 210, label: "var: result", type: "variable" },
            { id: "var2", x: 250, y: 210, label: "var: temp", type: "variable" },
            { id: "var3", x: 400, y: 210, label: "var: cache", type: "variable" },
            { id: "dep1", x: 175, y: 290, label: "validate()", type: "dependency" },
            { id: "dep2", x: 325, y: 290, label: "process()", type: "dependency" },
            { id: "return", x: 250, y: 370, label: "return", type: "return" },
          ]
        case "hpg":
          return [
            { id: "start", x: 250, y: 40, label: "Start", type: "start" },
            { id: "read", x: 250, y: 110, label: "Read Input", type: "io" },
            { id: "validate", x: 250, y: 180, label: "Validate", type: "process" },
            { id: "branch", x: 250, y: 250, label: "Branch", type: "decision" },
            { id: "success", x: 120, y: 320, label: "Success Path", type: "process" },
            { id: "error", x: 380, y: 320, label: "Error Path", type: "error" },
            { id: "log", x: 120, y: 390, label: "Log Result", type: "io" },
            { id: "end", x: 250, y: 460, label: "End", type: "end" },
          ]
        default:
          return []
      }
    }
    setNodes(generateNodes())
  }, [type, component])

  const getEdges = () => {
    switch (type) {
      case "cfg":
        return [
          ["entry", "cond1"],
          ["cond1", "block1"],
          ["cond1", "block2"],
          ["block1", "cond2"],
          ["cond2", "block3"],
          ["block3", "cond2"],
          ["cond2", "merge"],
          ["block2", "merge"],
          ["merge", "exit"],
        ]
      case "pdg":
        return [
          ["func", "param1"],
          ["func", "param2"],
          ["func", "param3"],
          ["param1", "var1"],
          ["param2", "var2"],
          ["param3", "var3"],
          ["var1", "dep1"],
          ["var2", "dep1"],
          ["var2", "dep2"],
          ["var3", "dep2"],
          ["dep1", "return"],
          ["dep2", "return"],
        ]
      case "hpg":
        return [
          ["start", "read"],
          ["read", "validate"],
          ["validate", "branch"],
          ["branch", "success"],
          ["branch", "error"],
          ["success", "log"],
          ["log", "end"],
          ["error", "end"],
        ]
      default:
        return []
    }
  }

  const handleMouseDown = (e: React.MouseEvent, nodeId: string) => {
    const node = nodes.find((n) => n.id === nodeId)
    if (!node) return
    setDragging(nodeId)
    setOffset({
      x: e.clientX - node.x,
      y: e.clientY - node.y,
    })
  }

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!dragging) return
      setNodes((prev) =>
        prev.map((node) =>
          node.id === dragging
            ? { ...node, x: e.clientX - offset.x, y: e.clientY - offset.y }
            : node
        )
      )
    },
    [dragging, offset]
  )

  const handleMouseUp = () => {
    setDragging(null)
  }

  const getNodeColor = (nodeType: string) => {
    const colors: Record<string, { bg: string; border: string; text: string }> = {
      entry: { bg: "#dcfce7", border: "#22c55e", text: "#166534" },
      exit: { bg: "#fee2e2", border: "#ef4444", text: "#991b1b" },
      condition: { bg: "#fef9c3", border: "#eab308", text: "#854d0e" },
      block: { bg: "#e0e7ff", border: "#6366f1", text: "#3730a3" },
      merge: { bg: "#f3e8ff", border: "#a855f7", text: "#6b21a8" },
      function: { bg: "#dbeafe", border: "#3b82f6", text: "#1e40af" },
      param: { bg: "#fce7f3", border: "#ec4899", text: "#9d174d" },
      variable: { bg: "#ccfbf1", border: "#14b8a6", text: "#0f766e" },
      dependency: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" },
      return: { bg: "#dcfce7", border: "#22c55e", text: "#166534" },
      start: { bg: "#dcfce7", border: "#22c55e", text: "#166534" },
      end: { bg: "#fee2e2", border: "#ef4444", text: "#991b1b" },
      io: { bg: "#e0e7ff", border: "#6366f1", text: "#3730a3" },
      process: { bg: "#dbeafe", border: "#3b82f6", text: "#1e40af" },
      decision: { bg: "#fef9c3", border: "#eab308", text: "#854d0e" },
      error: { bg: "#fee2e2", border: "#ef4444", text: "#991b1b" },
      root: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" },
      node: { bg: "#e0e7ff", border: "#6366f1", text: "#3730a3" },
      leaf: { bg: "#dcfce7", border: "#22c55e", text: "#166534" },
    }
    return colors[nodeType] || { bg: "#f3f4f6", border: "#9ca3af", text: "#374151" }
  }

  const edges = getEdges()

  return (
    <svg
      ref={svgRef}
      viewBox="0 0 500 500"
      className="w-full h-full max-w-[600px] max-h-[600px]"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#9ca3af" />
        </marker>
      </defs>

      {/* Edges */}
      {edges.map(([from, to], i) => {
        const fromNode = nodes.find((n) => n.id === from)
        const toNode = nodes.find((n) => n.id === to)
        if (!fromNode || !toNode) return null
        return (
          <line
            key={i}
            x1={fromNode.x}
            y1={fromNode.y + 15}
            x2={toNode.x}
            y2={toNode.y - 15}
            stroke="#d1d5db"
            strokeWidth="2"
            markerEnd="url(#arrow)"
          />
        )
      })}

      {/* Nodes */}
      {nodes.map((node) => {
        const colors = getNodeColor(node.type)
        return (
          <g
            key={node.id}
            transform={`translate(${node.x}, ${node.y})`}
            onMouseDown={(e) => handleMouseDown(e, node.id)}
            style={{ cursor: dragging === node.id ? "grabbing" : "grab" }}
          >
            <rect
              x="-45"
              y="-18"
              width="90"
              height="36"
              rx="6"
              fill={colors.bg}
              stroke={colors.border}
              strokeWidth="2"
            />
            <text
              textAnchor="middle"
              dy="5"
              fontSize="11"
              fontWeight="500"
              fill={colors.text}
            >
              {node.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
