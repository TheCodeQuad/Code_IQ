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
  RefreshCw,
} from "lucide-react"

type GraphType = "agents-flow" | "cfg" | "pdg" | "hpg" | "dag"
type ComponentType = "function" | "class" | "method"

interface Component {
  id: string
  name: string
  type: ComponentType
  filePath: string
  parentClass?: string
  start_line?: number
  end_line?: number
}

interface GraphNode {
  id: string
  label: string
  type: string
  x?: number
  y?: number
  line?: number
  code?: string
  metadata?: Record<string, any>
}

interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
  label?: string
  metadata?: Record<string, any>
}

interface GraphData {
  id: string
  name: string
  type: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  node_count: number
  edge_count: number
  component_id?: string
  component_name?: string
  file_path?: string
  metadata?: Record<string, any>
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

// API base URL - use local Next.js API routes that proxy to backend
// This avoids CORS issues. The routes are in frontend/app/api/graphs/
const API_BASE = ""

export default function GraphsPage() {
  const params = useParams<{ id?: string | string[] }>()
  const routeId = Array.isArray(params?.id) ? params.id[0] : params?.id

  const [components, setComponents] = useState<Component[]>([])
  const [selectedComponent, setSelectedComponent] = useState<Component | null>(null)
  const [selectedGraphType, setSelectedGraphType] = useState<GraphType>("cfg")
  const [zoom, setZoom] = useState(100)

  // Graph data state
  const [cfgData, setCfgData] = useState<GraphData | null>(null)
  const [pdgData, setPdgData] = useState<GraphData | null>(null)
  const [hpgData, setHpgData] = useState<GraphData | null>(null)
  const [dagData, setDagData] = useState<GraphData | null>(null)

  // Loading and error states
  const [graphLoading, setGraphLoading] = useState(false)
  const [graphError, setGraphError] = useState<string | null>(null)
  const [componentsLoading, setComponentsLoading] = useState(false)

  // Agent flow data
  const [componentFlows, setComponentFlows] = useState<Record<string, ComponentFlow>>({})
  const [componentFlowLoading, setComponentFlowLoading] = useState(false)

  // Repository path (resolved from repo ID)
  const [repoPath, setRepoPath] = useState<string | null>(null)
  const [parseStatus, setParseStatus] = useState<{
    is_parsed: boolean
    function_count: number
    class_count: number
  } | null>(null)

  // Resolve repo path from ID
  useEffect(() => {
    const resolveRepoPath = async () => {
      if (!routeId) return

      try {
        // Try to get repo info
        const response = await fetch(`/api/repos/${routeId}`)
        if (response.ok) {
          const data = await response.json()
          // Use local_path if available, otherwise construct from repo_name
          const path = data.local_path || data.repo_path || `./repos/${data.repo_name}`
          setRepoPath(path)
        }
      } catch (err) {
        console.error("Error resolving repo path:", err)
        // Fallback: try using the ID as a path directly
        setRepoPath(routeId)
      }
    }

    resolveRepoPath()
  }, [routeId])

  // Parse repository and fetch components
  useEffect(() => {
    if (!repoPath) return

    const parseAndFetchComponents = async () => {
      setComponentsLoading(true)

      try {
        // First, trigger parse (if not already parsed)
        const parseResponse = await fetch(`${API_BASE}/api/graphs/parse`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ repo_path: repoPath, force: false })
        })

        if (parseResponse.ok) {
          const parseData = await parseResponse.json()
          setParseStatus({
            is_parsed: true,
            function_count: parseData.function_count,
            class_count: parseData.class_count
          })
        }

        // Fetch components list
        const componentsResponse = await fetch(
          `${API_BASE}/api/graphs/components?repo_path=${encodeURIComponent(repoPath)}`
        )

        if (componentsResponse.ok) {
          const data = await componentsResponse.json()
          if (data.components && data.components.length > 0) {
            const mappedComponents: Component[] = data.components.map((c: any) => ({
              id: c.id,
              name: c.name,
              type: c.type as ComponentType,
              filePath: c.file_path,
              parentClass: c.parent_class,
              start_line: c.start_line,
              end_line: c.end_line
            }))
            setComponents(mappedComponents)

            // Auto-select first component
            if (!selectedComponent && mappedComponents.length > 0) {
              setSelectedComponent(mappedComponents[0])
            }
          }
        }
      } catch (err) {
        console.error("Error fetching components:", err)
      } finally {
        setComponentsLoading(false)
      }
    }

    parseAndFetchComponents()
  }, [repoPath])

  // Fetch graph data when component or graph type changes
  useEffect(() => {
    if (!selectedComponent || !repoPath) return
    if (selectedGraphType === "agents-flow") return // Agent flow uses different API

    const fetchGraphData = async () => {
      setGraphLoading(true)
      setGraphError(null)

      try {
        let endpoint = ""
        switch (selectedGraphType) {
          case "cfg":
            endpoint = `${API_BASE}/api/graphs/cfg/${selectedComponent.id}?repo_path=${encodeURIComponent(repoPath)}`
            break
          case "pdg":
            endpoint = `${API_BASE}/api/graphs/pdg/${selectedComponent.id}?repo_path=${encodeURIComponent(repoPath)}`
            break
          case "hpg":
            endpoint = `${API_BASE}/api/graphs/hpg/${selectedComponent.id}?repo_path=${encodeURIComponent(repoPath)}`
            break
          case "dag":
            endpoint = `${API_BASE}/api/graphs/dag?repo_path=${encodeURIComponent(repoPath)}&component_id=${selectedComponent.id}`
            break
        }

        const response = await fetch(endpoint)

        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(errorText || `Failed to fetch ${selectedGraphType.toUpperCase()}`)
        }

        const result = await response.json()

        if (result.success && result.data) {
          const graphData = result.data as GraphData

          // Store in appropriate state
          switch (selectedGraphType) {
            case "cfg":
              setCfgData(graphData)
              break
            case "pdg":
              setPdgData(graphData)
              break
            case "hpg":
              setHpgData(graphData)
              break
            case "dag":
              setDagData(graphData)
              break
          }
        } else {
          throw new Error(result.message || "Invalid response")
        }
      } catch (err: any) {
        console.error(`Error fetching ${selectedGraphType}:`, err)
        setGraphError(err.message || `Failed to load ${selectedGraphType.toUpperCase()}`)
      } finally {
        setGraphLoading(false)
      }
    }

    fetchGraphData()
  }, [selectedComponent, selectedGraphType, repoPath])

  // Fetch agent flow data
  useEffect(() => {
    if (!selectedComponent || selectedGraphType !== "agents-flow") return

    const fetchComponentFlow = async () => {
      setComponentFlowLoading(true)

      try {
        const response = await fetch(`/api/agents/component/${encodeURIComponent(selectedComponent.id)}/flow`)

        if (response.ok) {
          const data = await response.json()
          if (data.data) {
            setComponentFlows(prev => ({
              ...prev,
              [selectedComponent.id]: data.data
            }))
          }
        }
      } catch (err) {
        console.error("Error fetching component flow:", err)
      } finally {
        setComponentFlowLoading(false)
      }
    }

    fetchComponentFlow()
  }, [selectedComponent, selectedGraphType])

  // Get current graph data based on selected type
  const currentGraphData = useMemo(() => {
    switch (selectedGraphType) {
      case "cfg": return cfgData
      case "pdg": return pdgData
      case "hpg": return hpgData
      case "dag": return dagData
      default: return null
    }
  }, [selectedGraphType, cfgData, pdgData, hpgData, dagData])

  const currentGraph = graphTypes.find((g) => g.id === selectedGraphType)
  const selectedComponentFlow = selectedComponent ? componentFlows[selectedComponent.id] : null

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 25, 200))
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 25, 50))
  const handleReset = () => setZoom(100)

  const handleRefresh = async () => {
    if (!repoPath) return

    setGraphLoading(true)
    try {
      // Force re-parse
      await fetch(`${API_BASE}/api/graphs/parse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_path: repoPath, force: true })
      })

      // Clear cached data
      setCfgData(null)
      setPdgData(null)
      setHpgData(null)
      setDagData(null)

      // Re-fetch will happen automatically via useEffect
    } catch (err) {
      console.error("Error refreshing:", err)
    } finally {
      setGraphLoading(false)
    }
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-200px)] min-h-[700px]">
      {/* Left Panel - Component List */}
      <Card className="w-72 flex-shrink-0 border-stone-200 bg-white">
        <CardHeader className="pb-3 border-b border-stone-100">
          <CardTitle className="text-sm flex items-center gap-2 text-stone-700">
            <Network className="w-4 h-4" />
            Components
          </CardTitle>
          <p className="text-xs text-stone-500 mt-1">
            {componentsLoading ? "Loading..." : `${components.length} components`}
          </p>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[calc(100vh-320px)] min-h-[550px]">
            <div className="p-2 space-y-1">
              {componentsLoading ? (
                <div className="p-4 text-center">
                  <Loader className="w-5 h-5 animate-spin mx-auto mb-2 text-stone-400" />
                  <p className="text-xs text-stone-500">Loading components...</p>
                </div>
              ) : components.length > 0 ? (
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
                        {component.start_line ? `:${component.start_line}` : ""}
                      </p>
                    </div>
                    {selectedComponent?.id === component.id && (
                      <ChevronRight className="w-4 h-4 flex-shrink-0 text-amber-500" />
                    )}
                  </button>
                ))
              ) : (
                <div className="p-4 text-center">
                  <AlertCircle className="w-8 h-8 text-stone-300 mx-auto mb-2" />
                  <p className="text-xs text-stone-500">No components found</p>
                  <p className="text-xs text-stone-400 mt-1">Parse a repository first</p>
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
              <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={handleRefresh} disabled={graphLoading}>
                <RefreshCw className={`w-3.5 h-3.5 ${graphLoading ? "animate-spin" : ""}`} />
              </Button>
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
            ) : selectedComponent && currentGraphData ? (
              <RealGraphVisualization
                graphData={currentGraphData}
                graphType={selectedGraphType}
              />
            ) : graphLoading ? (
              <div className="flex flex-col items-center justify-center h-full gap-3">
                <Loader className="w-8 h-8 animate-spin text-amber-500" />
                <p className="text-sm text-stone-500">Loading {selectedGraphType.toUpperCase()}...</p>
              </div>
            ) : graphError ? (
              <div className="flex flex-col items-center justify-center h-full gap-3">
                <AlertCircle className="w-10 h-10 text-red-400" />
                <p className="text-sm text-red-600">{graphError}</p>
                <Button variant="outline" size="sm" onClick={handleRefresh}>
                  Try Again
                </Button>
              </div>
            ) : selectedComponent ? (
              <div className="flex flex-col items-center justify-center h-full gap-3">
                <Network className="w-10 h-10 text-stone-300" />
                <p className="text-sm text-stone-500">Select a graph type to view</p>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full">
                <p className="text-stone-400 text-sm">Select a component to view its graph</p>
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

            {/* Graph Statistics */}
            {currentGraphData && (
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
                  Graph Statistics
                </h4>
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 bg-blue-50 rounded-lg text-center border border-blue-100">
                    <p className="text-lg font-semibold text-blue-700">{currentGraphData.node_count}</p>
                    <p className="text-xs text-blue-600">Nodes</p>
                  </div>
                  <div className="p-2.5 bg-emerald-50 rounded-lg text-center border border-emerald-100">
                    <p className="text-lg font-semibold text-emerald-700">{currentGraphData.edge_count}</p>
                    <p className="text-xs text-emerald-600">Edges</p>
                  </div>
                </div>
                {currentGraphData.metadata && (
                  <div className="text-xs space-y-1 text-stone-500">
                    {currentGraphData.metadata.data_dependencies !== undefined && (
                      <div className="flex justify-between">
                        <span>Data Dependencies</span>
                        <span className="font-medium text-stone-700">{currentGraphData.metadata.data_dependencies}</span>
                      </div>
                    )}
                    {currentGraphData.metadata.control_dependencies !== undefined && (
                      <div className="flex justify-between">
                        <span>Control Dependencies</span>
                        <span className="font-medium text-stone-700">{currentGraphData.metadata.control_dependencies}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

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
                      <span className="font-mono text-stone-600 truncate max-w-[150px]">{selectedComponent.filePath}</span>
                    </div>
                    {selectedComponent.start_line && (
                      <div className="flex justify-between">
                        <span className="text-stone-400">Lines</span>
                        <span className="font-mono text-stone-600">
                          {selectedComponent.start_line}
                          {selectedComponent.end_line ? `-${selectedComponent.end_line}` : ""}
                        </span>
                      </div>
                    )}
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

            {/* Parse Status */}
            {parseStatus && (
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
                  Repository Status
                </h4>
                <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-100">
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span className="text-sm font-medium text-emerald-800">Parsed</span>
                  </div>
                  <div className="text-xs space-y-1 text-emerald-700">
                    <div className="flex justify-between">
                      <span>Functions</span>
                      <span className="font-semibold">{parseStatus.function_count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Classes</span>
                      <span className="font-semibold">{parseStatus.class_count}</span>
                    </div>
                  </div>
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

// Real Graph Visualization Component - renders actual graph data from backend
function RealGraphVisualization({
  graphData,
  graphType
}: {
  graphData: GraphData
  graphType: GraphType
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [dragging, setDragging] = useState<string | null>(null)
  const [offset, setOffset] = useState({ x: 0, y: 0 })

  // Initialize nodes with positions
  useEffect(() => {
    if (!graphData?.nodes) return

    // Use provided positions or calculate layout
    const positionedNodes = graphData.nodes.map((node, index) => {
      if (node.x !== undefined && node.y !== undefined) {
        return node
      }

      // Auto-layout if no positions provided
      const cols = Math.ceil(Math.sqrt(graphData.nodes.length))
      const row = Math.floor(index / cols)
      const col = index % cols

      return {
        ...node,
        x: 100 + col * 140,
        y: 60 + row * 80
      }
    })

    setNodes(positionedNodes)
  }, [graphData])

  const handleMouseDown = (e: React.MouseEvent, nodeId: string) => {
    const node = nodes.find((n) => n.id === nodeId)
    if (!node) return
    setDragging(nodeId)
    setOffset({
      x: e.clientX - (node.x || 0),
      y: e.clientY - (node.y || 0),
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

  // Color scheme based on node type
  const getNodeColor = (nodeType: string) => {
    const colors: Record<string, { bg: string; border: string; text: string }> = {
      // CFG node types
      entry: { bg: "#dcfce7", border: "#22c55e", text: "#166534" },
      exit: { bg: "#fee2e2", border: "#ef4444", text: "#991b1b" },
      branch: { bg: "#fef9c3", border: "#eab308", text: "#854d0e" },
      loop_header: { bg: "#fef9c3", border: "#eab308", text: "#854d0e" },
      loop_body: { bg: "#e0e7ff", border: "#6366f1", text: "#3730a3" },
      merge: { bg: "#f3e8ff", border: "#a855f7", text: "#6b21a8" },
      statement: { bg: "#e0e7ff", border: "#6366f1", text: "#3730a3" },
      block: { bg: "#e0e7ff", border: "#6366f1", text: "#3730a3" },
      return: { bg: "#dcfce7", border: "#22c55e", text: "#166534" },
      "if": { bg: "#fef9c3", border: "#eab308", text: "#854d0e" },
      "for": { bg: "#fef9c3", border: "#eab308", text: "#854d0e" },
      "while": { bg: "#fef9c3", border: "#eab308", text: "#854d0e" },
      try: { bg: "#fce7f3", border: "#ec4899", text: "#9d174d" },
      except: { bg: "#fee2e2", border: "#ef4444", text: "#991b1b" },
      finally: { bg: "#ccfbf1", border: "#14b8a6", text: "#0f766e" },

      // PDG node types
      parameter: { bg: "#fce7f3", border: "#ec4899", text: "#9d174d" },
      assignment: { bg: "#e0e7ff", border: "#6366f1", text: "#3730a3" },
      expression: { bg: "#f3f4f6", border: "#9ca3af", text: "#374151" },
      call: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" },

      // DAG node types
      function: { bg: "#dbeafe", border: "#3b82f6", text: "#1e40af" },
      method: { bg: "#ccfbf1", border: "#14b8a6", text: "#0f766e" },
      class: { bg: "#f3e8ff", border: "#a855f7", text: "#6b21a8" },
      module: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" },

      // Neighborhood DAG
      selected: { bg: "#dbeafe", border: "#2563eb", text: "#1e3a8a" },
      dependency: { bg: "#dcfce7", border: "#16a34a", text: "#166534" },
      dependent: { bg: "#fef3c7", border: "#d97706", text: "#92400e" },
    }
    return colors[nodeType] || { bg: "#f3f4f6", border: "#9ca3af", text: "#374151" }
  }

  // Edge color based on type
  const getEdgeColor = (edgeType: string) => {
    const colors: Record<string, string> = {
      flow: "#9ca3af",
      true: "#22c55e",
      false: "#ef4444",
      back: "#8b5cf6",
      data: "#3b82f6",
      control: "#f59e0b",
      call: "#ec4899",
      inherits: "#8b5cf6",
      imports: "#6366f1",
    }
    return colors[edgeType] || "#9ca3af"
  }

  // Calculate viewBox based on node positions
  const viewBox = useMemo(() => {
    if (nodes.length === 0) return "0 0 600 500"

    const xs = nodes.map(n => n.x || 0)
    const ys = nodes.map(n => n.y || 0)

    const minX = Math.min(...xs) - 80
    const maxX = Math.max(...xs) + 80
    const minY = Math.min(...ys) - 40
    const maxY = Math.max(...ys) + 60

    const width = Math.max(maxX - minX, 400)
    const height = Math.max(maxY - minY, 300)

    return `${minX} ${minY} ${width} ${height}`
  }, [nodes])

  if (!graphData || nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-stone-400">No graph data available</p>
      </div>
    )
  }

  return (
    <svg
      ref={svgRef}
      viewBox={viewBox}
      className="w-full h-full"
      style={{ minWidth: "500px", minHeight: "400px" }}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <defs>
        {/* Arrow markers for different edge types */}
        <marker id="arrow-default" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#9ca3af" />
        </marker>
        <marker id="arrow-true" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#22c55e" />
        </marker>
        <marker id="arrow-false" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#ef4444" />
        </marker>
        <marker id="arrow-data" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#3b82f6" />
        </marker>
        <marker id="arrow-control" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#f59e0b" />
        </marker>
        <marker id="arrow-call" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#ec4899" />
        </marker>
      </defs>

      {/* Background */}
      <rect width="100%" height="100%" fill="#fafafa" />

      {/* Edges */}
      {graphData.edges.map((edge) => {
        const fromNode = nodes.find((n) => n.id === edge.source)
        const toNode = nodes.find((n) => n.id === edge.target)
        if (!fromNode || !toNode) return null

        const x1 = fromNode.x || 0
        const y1 = (fromNode.y || 0) + 18
        const x2 = toNode.x || 0
        const y2 = (toNode.y || 0) - 18

        const edgeColor = getEdgeColor(edge.type)
        const markerId = `arrow-${edge.type === "true" || edge.type === "false" || edge.type === "data" || edge.type === "control" || edge.type === "call" ? edge.type : "default"}`

        // Use curved path for cleaner look
        const midY = (y1 + y2) / 2
        const path = `M ${x1} ${y1} Q ${(x1 + x2) / 2} ${midY} ${x2} ${y2}`

        return (
          <g key={edge.id}>
            <path
              d={path}
              fill="none"
              stroke={edgeColor}
              strokeWidth={edge.type === "data" ? 2.5 : 2}
              strokeDasharray={edge.type === "data" ? "5,3" : undefined}
              markerEnd={`url(#${markerId})`}
              opacity={0.8}
            />
            {edge.label && (
              <text
                x={(x1 + x2) / 2}
                y={midY - 8}
                textAnchor="middle"
                fontSize="9"
                fill={edgeColor}
                fontWeight="500"
              >
                {edge.label}
              </text>
            )}
          </g>
        )
      })}

      {/* Nodes */}
      {nodes.map((node) => {
        const colors = getNodeColor(node.type)
        const label = node.label.length > 20 ? `${node.label.substring(0, 18)}…` : node.label

        return (
          <g
            key={node.id}
            transform={`translate(${node.x || 0}, ${node.y || 0})`}
            onMouseDown={(e) => handleMouseDown(e, node.id)}
            style={{ cursor: dragging === node.id ? "grabbing" : "grab" }}
          >
            <rect
              x="-55"
              y="-18"
              width="110"
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
              pointerEvents="none"
            >
              {label}
            </text>
            {node.line && (
              <text
                textAnchor="middle"
                dy="18"
                fontSize="8"
                fill={colors.text}
                opacity="0.6"
                pointerEvents="none"
              >
                L{node.line}
              </text>
            )}
            <title>{node.code || node.label}</title>
          </g>
        )
      })}

      {/* Legend */}
      <g transform={`translate(10, 10)`}>
        <text fontSize="10" fill="#6b7280" fontWeight="600">
          {graphData.name}
        </text>
        <text fontSize="9" fill="#9ca3af" y="14">
          {graphData.node_count} nodes · {graphData.edge_count} edges
        </text>
      </g>
    </svg>
  )
}

// Agents Flow Graph - Shows default agent flow with highlighting for executed agents
function AgentsFlowGraph({ component, componentFlow }: { component: Component; componentFlow?: ComponentFlow }) {
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

  const isAgentExecuted = (agentName: string) => {
    if (executedAgents.length === 0) return false
    return executedAgents.includes(agentName.toLowerCase())
  }

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
        <defs>
          <marker id="arrowhead-gray" markerWidth="6" markerHeight="5" refX="5" refY="2.5" orient="auto">
            <polygon points="0 0, 6 2.5, 0 5" fill="#d1d5db" />
          </marker>
          <marker id="arrowhead-emerald" markerWidth="6" markerHeight="5" refX="5" refY="2.5" orient="auto">
            <polygon points="0 0, 6 2.5, 0 5" fill="#10b981" />
          </marker>
        </defs>

        {/* Main flow arrows */}
        <path
          d="M 140 60 L 300 60"
          fill="none"
          stroke={readerNeedsContext ? "#10b981" : "#d1d5db"}
          strokeWidth="2"
          markerEnd={readerNeedsContext ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"}
        />
        <text x="220" y="50" textAnchor="middle" className="text-[10px] font-medium" fill={readerNeedsContext ? "#059669" : "#9ca3af"}>Need Context</text>

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

        <path
          d="M 355 195 L 355 220"
          fill="none"
          stroke={isConnectionHighlighted("writer", "verifier") ? "#10b981" : "#d1d5db"}
          strokeWidth="2"
          markerEnd={isConnectionHighlighted("writer", "verifier") ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"}
        />

        <path d="M 400 230 Q 455 195, 400 165" fill="none" stroke={verifierToWriterLoop ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={verifierToWriterLoop ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />
        <text x="478" y="195" textAnchor="middle" className="text-[10px] font-medium" fill={verifierToWriterLoop ? "#059669" : "#9ca3af"}>
          <tspan x="478" dy="0">Needs</tspan>
          <tspan x="478" dy="13">Revision</tspan>
        </text>

        <path d="M 305 255 C 170 290, 50 215, 50 120 C 50 75, 70 60, 95 60" fill="none" stroke={verifierToReaderLoop ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={verifierToReaderLoop ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />

        <path
          d="M 355 262 L 355 290"
          fill="none"
          stroke={verifierAccepted ? "#10b981" : "#d1d5db"}
          strokeWidth="2"
          markerEnd={verifierAccepted ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"}
        />
        <text x="400" y="280" textAnchor="middle" className="text-[10px] font-medium" fill={verifierAccepted ? "#059669" : "#9ca3af"}>Accepted</text>

        <path d="M 300 40 Q 220 15, 140 40" fill="none" stroke={searcherContextNotFound ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={searcherContextNotFound ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />

        {/* Agent Nodes */}
        <AgentNode label="Reader" x={95} y={60} status={isAgentExecuted("reader") ? "completed" : "pending"} />
        <AgentNode label="Searcher" x={355} y={60} status={isAgentExecuted("searcher") ? "completed" : "pending"} />
        <AgentNode label="Writer" x={355} y={175} status={isAgentExecuted("writer") ? "completed" : "pending"} />
        <AgentNode label="Verifier" x={355} y={240} status={isAgentExecuted("verifier") ? "completed" : "pending"} />
        <AgentNode label="Docstring Inserted" x={355} y={315} status={componentFlow?.status === "success" && executedAgents.length > 0 ? "completed" : "pending"} isLarge />
      </svg>
    </div>
  )
}

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
        return { fill: "#dcfce7", stroke: "#10b981", textColor: "#166534", iconColor: "#10b981" }
      case "running":
        return { fill: "#fef3c3", stroke: "#f59e0b", textColor: "#92400e", iconColor: "#f59e0b" }
      default:
        return { fill: "#f3f4f6", stroke: "#9ca3af", textColor: "#4b5563", iconColor: "#9ca3af" }
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
