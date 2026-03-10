"use client"

import { useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Code2,
  ArrowLeft,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Download,
  Info,
  Layers,
  GitBranch,
  Network,
} from "lucide-react"
import { useAnalysis } from "@/lib/analysis-context"

// Mock graph nodes for visualization
const mockGraphNodes = {
  cfg: [
    { id: "start", label: "Start", x: 50, y: 10, type: "entry" },
    { id: "init", label: "initialize()", x: 50, y: 25, type: "function" },
    { id: "condition", label: "if (config)", x: 50, y: 40, type: "condition" },
    { id: "load_true", label: "load_config()", x: 25, y: 55, type: "function" },
    { id: "load_false", label: "use_defaults()", x: 75, y: 55, type: "function" },
    { id: "process", label: "process_data()", x: 50, y: 70, type: "function" },
    { id: "end", label: "End", x: 50, y: 85, type: "exit" },
  ],
  pdg: [
    { id: "data1", label: "input_data", x: 20, y: 20, type: "data" },
    { id: "data2", label: "config", x: 80, y: 20, type: "data" },
    { id: "func1", label: "validate()", x: 20, y: 50, type: "function" },
    { id: "func2", label: "transform()", x: 50, y: 50, type: "function" },
    { id: "func3", label: "export()", x: 80, y: 50, type: "function" },
    { id: "output", label: "result", x: 50, y: 80, type: "data" },
  ],
  hpg: [
    { id: "module", label: "api_gateway", x: 50, y: 10, type: "module" },
    { id: "class1", label: "RequestHandler", x: 30, y: 30, type: "class" },
    { id: "class2", label: "ResponseBuilder", x: 70, y: 30, type: "class" },
    { id: "method1", label: "handle()", x: 20, y: 55, type: "function" },
    { id: "method2", label: "validate()", x: 40, y: 55, type: "function" },
    { id: "method3", label: "build()", x: 60, y: 55, type: "function" },
    { id: "method4", label: "serialize()", x: 80, y: 55, type: "function" },
    { id: "external", label: "database", x: 50, y: 80, type: "external" },
  ],
  ghg: [
    { id: "mod1", label: "api", x: 25, y: 15, type: "module" },
    { id: "mod2", label: "auth", x: 75, y: 15, type: "module" },
    { id: "mod3", label: "data", x: 25, y: 45, type: "module" },
    { id: "mod4", label: "utils", x: 75, y: 45, type: "module" },
    { id: "mod5", label: "config", x: 50, y: 75, type: "module" },
  ],
}

const mockEdges = {
  cfg: [
    ["start", "init"],
    ["init", "condition"],
    ["condition", "load_true"],
    ["condition", "load_false"],
    ["load_true", "process"],
    ["load_false", "process"],
    ["process", "end"],
  ],
  pdg: [
    ["data1", "func1"],
    ["data2", "func2"],
    ["func1", "func2"],
    ["func2", "func3"],
    ["func3", "output"],
    ["data2", "func3"],
  ],
  hpg: [
    ["module", "class1"],
    ["module", "class2"],
    ["class1", "method1"],
    ["class1", "method2"],
    ["class2", "method3"],
    ["class2", "method4"],
    ["method1", "external"],
    ["method3", "external"],
  ],
  ghg: [
    ["mod1", "mod2"],
    ["mod1", "mod3"],
    ["mod2", "mod4"],
    ["mod3", "mod4"],
    ["mod3", "mod5"],
    ["mod4", "mod5"],
  ],
}

const nodeColors = {
  entry: "fill-chart-3",
  exit: "fill-chart-5",
  function: "fill-chart-1",
  condition: "fill-chart-2",
  data: "fill-chart-4",
  module: "fill-chart-2",
  class: "fill-chart-1",
  external: "fill-muted-foreground",
}

const graphInfo = {
  cfg: {
    title: "Control Flow Graph",
    description: "Shows the execution paths and control structures in your code",
    stats: { nodes: 234, edges: 456, branches: 89 },
  },
  pdg: {
    title: "Program Dependency Graph",
    description: "Illustrates data and control dependencies between code elements",
    stats: { nodes: 189, edges: 312, dependencies: 67 },
  },
  hpg: {
    title: "Hybrid Program Graph",
    description: "Combines CFG and PDG for comprehensive semantic understanding",
    stats: { nodes: 423, edges: 768, components: 45 },
  },
  ghg: {
    title: "Global Hybrid Graph",
    description: "Module-level view showing cross-file relationships",
    stats: { modules: 12, connections: 34, depth: 4 },
  },
}

export default function GraphsPage() {
  const params = useParams()
  const analysisId = params.id as string
  const { getAnalysis } = useAnalysis()
  const analysis = getAnalysis(analysisId)

  const [activeGraph, setActiveGraph] = useState<"cfg" | "pdg" | "hpg" | "ghg">("ghg")
  const [zoom, setZoom] = useState(1)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)

  // Build real DAG graph nodes from analysis data
  const realDagNodes = analysis?.dag ? buildDagNodes(analysis.dag, analysis.components) : null
  const realDagEdges = analysis?.dag ? buildDagEdges(analysis.dag) : null

  // Use real data for GHG tab, mock for others
  const nodes = activeGraph === "ghg" && realDagNodes ? realDagNodes : mockGraphNodes[activeGraph]
  const edges = activeGraph === "ghg" && realDagEdges ? realDagEdges : mockEdges[activeGraph]
  const info = activeGraph === "ghg" && analysis?.dag
    ? {
        title: "Dependency Graph (DAG)",
        description: "Real dependency graph from your repository analysis",
        stats: {
          modules: Object.keys(analysis.dag).length,
          connections: Object.values(analysis.dag).reduce((sum, deps) => sum + deps.length, 0),
          depth: analysis.topologicalOrder?.length || 0,
        },
      }
    : graphInfo[activeGraph]

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
              <span className="text-lg font-semibold text-foreground">Graph Visualization</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="border-border bg-transparent" onClick={() => setZoom(Math.max(0.5, zoom - 0.1))}>
              <ZoomOut className="w-4 h-4" />
            </Button>
            <span className="text-sm text-muted-foreground w-16 text-center">{Math.round(zoom * 100)}%</span>
            <Button variant="outline" size="sm" className="border-border bg-transparent" onClick={() => setZoom(Math.min(2, zoom + 0.1))}>
              <ZoomIn className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="sm" className="border-border bg-transparent">
              <Maximize2 className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="sm" className="border-border bg-transparent">
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid lg:grid-cols-4 gap-8">
          {/* Graph View */}
          <div className="lg:col-span-3">
            <Tabs value={activeGraph} onValueChange={(v) => setActiveGraph(v as typeof activeGraph)}>
              <TabsList className="mb-6 bg-secondary">
                <TabsTrigger value="cfg" className="flex items-center gap-2">
                  <GitBranch className="w-4 h-4" />
                  CFG
                </TabsTrigger>
                <TabsTrigger value="pdg" className="flex items-center gap-2">
                  <Network className="w-4 h-4" />
                  PDG
                </TabsTrigger>
                <TabsTrigger value="hpg" className="flex items-center gap-2">
                  <Layers className="w-4 h-4" />
                  HPG
                </TabsTrigger>
                <TabsTrigger value="ghg" className="flex items-center gap-2">
                  <Layers className="w-4 h-4" />
                  GHG
                </TabsTrigger>
              </TabsList>

              <TabsContent value={activeGraph}>
                <Card className="border-border">
                  <CardContent className="p-0">
                    <div className="relative bg-secondary/30 rounded-lg overflow-hidden" style={{ height: "500px" }}>
                      <svg
                        width="100%"
                        height="100%"
                        viewBox="0 0 100 100"
                        preserveAspectRatio="xMidYMid meet"
                        style={{ transform: `scale(${zoom})`, transformOrigin: "center" }}
                      >
                        {/* Edges */}
                        {edges.map(([from, to], i) => {
                          const fromNode = nodes.find((n) => n.id === from)
                          const toNode = nodes.find((n) => n.id === to)
                          if (!fromNode || !toNode) return null
                          return (
                            <line
                              key={`${activeGraph}-edge-${i}`}
                              x1={`${fromNode.x}%`}
                              y1={`${fromNode.y}%`}
                              x2={`${toNode.x}%`}
                              y2={`${toNode.y}%`}
                              stroke="currentColor"
                              strokeWidth="0.3"
                              className="text-muted-foreground"
                              markerEnd="url(#arrowhead)"
                            />
                          )
                        })}
                        
                        {/* Arrow marker */}
                        <defs>
                          <marker
                            id="arrowhead"
                            markerWidth="10"
                            markerHeight="7"
                            refX="9"
                            refY="3.5"
                            orient="auto"
                          >
                            <polygon
                              points="0 0, 10 3.5, 0 7"
                              className="fill-muted-foreground"
                            />
                          </marker>
                        </defs>

                        {/* Nodes */}
                        {nodes.map((node) => (
                          <g key={node.id}>
                            <circle
                              cx={`${node.x}%`}
                              cy={`${node.y}%`}
                              r="4"
                              className={`${nodeColors[node.type as keyof typeof nodeColors]} cursor-pointer transition-all ${
                                selectedNode === node.id ? "stroke-foreground stroke-[0.5]" : ""
                              }`}
                              onClick={() => setSelectedNode(node.id)}
                            />
                            <text
                              x={`${node.x}%`}
                              y={`${node.y + 7}%`}
                              textAnchor="middle"
                              className="fill-foreground text-[2.5px] font-medium"
                            >
                              {node.label}
                            </text>
                          </g>
                        ))}
                      </svg>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>

          {/* Info Panel */}
          <div className="space-y-6">
            <Card className="border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Info className="w-5 h-5" />
                  {info.title}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">{info.description}</p>
                <div className="space-y-2 pt-4 border-t border-border">
                  {Object.entries(info.stats).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground capitalize">{key}</span>
                      <Badge variant="outline" className="border-border">
                        {value}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Legend */}
            <Card className="border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Legend</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {[
                  { type: "function", label: "Function/Method", color: "bg-chart-1" },
                  { type: "condition", label: "Condition/Class", color: "bg-chart-2" },
                  { type: "entry", label: "Entry Point", color: "bg-chart-3" },
                  { type: "data", label: "Data Node", color: "bg-chart-4" },
                  { type: "exit", label: "Exit Point", color: "bg-chart-5" },
                ].map((item) => (
                  <div key={item.type} className="flex items-center gap-3">
                    <div className={`w-4 h-4 rounded-full ${item.color}`} />
                    <span className="text-sm text-foreground">{item.label}</span>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Selected Node Info */}
            {selectedNode && (
              <Card className="border-border border-primary/50">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">Selected Node</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">ID</span>
                      <span className="text-sm font-mono text-foreground">{selectedNode}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Label</span>
                      <span className="text-sm font-mono text-foreground">
                        {nodes.find((n) => n.id === selectedNode)?.label}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Type</span>
                      <Badge variant="outline" className="border-border capitalize">
                        {nodes.find((n) => n.id === selectedNode)?.type}
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
// ── Helpers to build real graph data from DAG ────────────────────────

function buildDagNodes(
  dag: Record<string, string[]>,
  components?: Record<string, any>
): { id: string; label: string; x: number; y: number; type: string }[] {
  const nodeIds = new Set<string>()
  for (const [source, targets] of Object.entries(dag)) {
    nodeIds.add(source)
    for (const t of targets) nodeIds.add(t)
  }

  const nodes = Array.from(nodeIds)
  const cols = Math.max(Math.ceil(Math.sqrt(nodes.length)), 3)

  return nodes.map((id, i) => {
    const comp = components?.[id]
    const compType = comp?.type || "function"
    const nodeType =
      compType === "class" ? "class" : compType === "module" ? "module" : "function"

    return {
      id,
      label: id.split("::").pop() || id,
      x: 10 + ((i % cols) / (cols - 1 || 1)) * 80,
      y: 10 + (Math.floor(i / cols) / Math.max(Math.floor(nodes.length / cols), 1)) * 80,
      type: nodeType,
    }
  })
}

function buildDagEdges(dag: Record<string, string[]>): [string, string][] {
  const edges: [string, string][] = []
  for (const [source, targets] of Object.entries(dag)) {
    for (const target of targets) {
      edges.push([source, target])
    }
  }
  return edges
}