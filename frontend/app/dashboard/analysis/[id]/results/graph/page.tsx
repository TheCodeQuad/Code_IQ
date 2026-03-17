"use client"

import { useState, useCallback, useRef, useEffect } from "react"
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
} from "lucide-react"

type GraphType = "agents-flow" | "cfg" | "pdg" | "hpg" | "gfg"
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

const components: Component[] = [
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
  { id: "gfg", label: "GFG", fullName: "Graph Flow Graph", description: "Graph-based program analysis representation used for advanced static analysis techniques." },
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
  const [selectedComponent, setSelectedComponent] = useState<Component>(components[0])
  const [selectedGraphType, setSelectedGraphType] = useState<GraphType>("agents-flow")
  const [zoom, setZoom] = useState(100)

  const currentGraph = graphTypes.find((g) => g.id === selectedGraphType)

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
          <p className="text-xs text-stone-500 mt-1">{components.length} total components</p>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[calc(100vh-320px)] min-h-[550px]">
            <div className="p-2 space-y-1">
              {components.map((component) => (
                <button
                  key={component.id}
                  onClick={() => setSelectedComponent(component)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all ${
                    selectedComponent.id === component.id
                      ? "bg-amber-50 border border-amber-200"
                      : "hover:bg-stone-50 border border-transparent"
                  }`}
                >
                  <div
                    className={`w-8 h-8 rounded-md flex items-center justify-center ${
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
                    <p className={`font-medium text-sm truncate ${selectedComponent.id === component.id ? "text-amber-900" : "text-stone-700"}`}>
                      {component.name}
                    </p>
                    <p className="text-xs text-stone-400 truncate">
                      {component.parentClass ? `${component.parentClass}.` : ""}
                      {component.filePath}
                    </p>
                  </div>
                  {selectedComponent.id === component.id && (
                    <ChevronRight className="w-4 h-4 flex-shrink-0 text-amber-500" />
                  )}
                </button>
              ))}
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
            {selectedGraphType === "agents-flow" ? (
              <AgentsFlowGraph component={selectedComponent} />
            ) : (
              <DraggableGraph type={selectedGraphType} component={selectedComponent} />
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
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
                Selected Component
              </h4>
              <div className="p-3 bg-stone-50 rounded-lg border border-stone-100">
                <div className="flex items-center gap-2 mb-3">
                  <div
                    className={`w-8 h-8 rounded-md flex items-center justify-center ${
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

            {/* Repository Info */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
                Repository
              </h4>
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between py-1.5 border-b border-stone-100">
                  <span className="text-stone-400 text-xs">Name</span>
                  <span className="font-medium text-stone-700 text-xs">api-gateway</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-stone-100">
                  <span className="text-stone-400 text-xs">Language</span>
                  <Badge variant="outline" className="text-xs border-stone-200">Python</Badge>
                </div>
                <div className="flex items-center justify-between py-1.5">
                  <span className="text-stone-400 text-xs">Total Components</span>
                  <span className="font-medium text-stone-700 text-xs">{components.length}</span>
                </div>
              </div>
            </div>

            {/* Graph Stats */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
                Graph Statistics
              </h4>
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 bg-stone-50 rounded-lg text-center border border-stone-100">
                  <p className="text-lg font-semibold text-stone-800">5</p>
                  <p className="text-xs text-stone-400">Nodes</p>
                </div>
                <div className="p-2.5 bg-stone-50 rounded-lg text-center border border-stone-100">
                  <p className="text-lg font-semibold text-stone-800">8</p>
                  <p className="text-xs text-stone-400">Edges</p>
                </div>
                <div className="p-2.5 bg-stone-50 rounded-lg text-center border border-stone-100">
                  <p className="text-lg font-semibold text-stone-800">3</p>
                  <p className="text-xs text-stone-400">Depth</p>
                </div>
                <div className="p-2.5 bg-stone-50 rounded-lg text-center border border-stone-100">
                  <p className="text-lg font-semibold text-stone-800">2</p>
                  <p className="text-xs text-stone-400">Branches</p>
                </div>
              </div>
            </div>

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

// Agents Flow Graph (similar to pipeline visualization)
function AgentsFlowGraph({ component }: { component: Component }) {
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

        {/* Arrows */}
        <path d="M 140 60 L 300 60" fill="none" className="stroke-emerald-400" strokeWidth="2" markerEnd="url(#arrowhead-emerald)" />
        <text x="220" y="50" textAnchor="middle" className="text-[10px] font-medium fill-emerald-600">Need Context</text>

        <path d="M 400 80 Q 445 115, 400 155" fill="none" className="stroke-emerald-400" strokeWidth="2" markerEnd="url(#arrowhead-emerald)" />
        <text x="475" y="95" textAnchor="middle" className="text-[10px] font-medium fill-emerald-600">
          <tspan x="475" dy="0">Context</tspan>
          <tspan x="475" dy="13">Found</tspan>
        </text>

        <path d="M 95 82 C 95 130, 240 105, 305 160" fill="none" className="stroke-gray-300" strokeWidth="2" markerEnd="url(#arrowhead-gray)" />
        <text x="155" y="125" textAnchor="middle" className="text-[10px] font-medium fill-gray-400">
          <tspan x="155" dy="0">Context</tspan>
          <tspan x="155" dy="13">Not Needed</tspan>
        </text>

        <path d="M 355 195 L 355 220" fill="none" className="stroke-emerald-400" strokeWidth="2" markerEnd="url(#arrowhead-emerald)" />
        <text x="295" y="205" textAnchor="middle" className="text-[10px] font-medium fill-emerald-600">
          <tspan x="295" dy="0">Docstring</tspan>
          <tspan x="295" dy="13">Generated</tspan>
        </text>

        <path d="M 400 230 Q 455 195, 400 165" fill="none" className="stroke-gray-300" strokeWidth="2" markerEnd="url(#arrowhead-gray)" />
        <text x="478" y="195" textAnchor="middle" className="text-[10px] font-medium fill-gray-400">
          <tspan x="478" dy="0">Needs</tspan>
          <tspan x="478" dy="13">Revision</tspan>
        </text>

        <path d="M 305 255 C 170 290, 50 215, 50 120 C 50 75, 70 60, 95 60" fill="none" className="stroke-gray-300" strokeWidth="2" markerEnd="url(#arrowhead-gray)" />
        <text x="100" y="270" textAnchor="middle" className="text-[10px] font-medium fill-gray-400">
          <tspan x="100" dy="0">Needs More</tspan>
          <tspan x="100" dy="13">Context</tspan>
        </text>

        <path d="M 355 262 L 355 290" fill="none" className="stroke-emerald-400" strokeWidth="2" markerEnd="url(#arrowhead-emerald)" />
        <text x="400" y="280" textAnchor="middle" className="text-[10px] font-medium fill-emerald-600">Accepted</text>

        <path d="M 300 40 Q 220 15, 140 40" fill="none" className="stroke-gray-300" strokeWidth="2" markerEnd="url(#arrowhead-gray)" />
        <text x="220" y="8" textAnchor="middle" className="text-[10px] font-medium fill-gray-400">
          <tspan x="220" dy="0">Context</tspan>
          <tspan x="220" dy="13">Not Found</tspan>
        </text>

        {/* Agent Nodes */}
        <AgentNode label="Reader" x={95} y={60} status="completed" />
        <AgentNode label="Searcher" x={355} y={60} status="completed" />
        <AgentNode label="Writer" x={355} y={175} status="completed" />
        <AgentNode label="Verifier" x={355} y={240} status="completed" />
        <AgentNode label="Docstring Inserted" x={355} y={315} status="completed" isLarge />
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

  return (
    <g transform={`translate(${x}, ${y})`}>
      <ellipse cx="0" cy="0" rx={rx} ry={ry} className="fill-emerald-50 stroke-emerald-500 transition-all duration-300" strokeWidth="1.5" />
      <foreignObject x={-foreignWidth / 2} y="-14" width={foreignWidth} height="28">
        <div className="w-full h-full flex items-center justify-center gap-1.5">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span className="text-[11px] font-semibold leading-none text-emerald-700">{label}</span>
        </div>
      </foreignObject>
    </g>
  )
}

// Draggable Graph Component for CFG, PDG, HPG, GFG
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
        case "gfg":
          return [
            { id: "root", x: 250, y: 50, label: "Root", type: "root" },
            { id: "n1", x: 130, y: 130, label: "Node 1", type: "node" },
            { id: "n2", x: 370, y: 130, label: "Node 2", type: "node" },
            { id: "n3", x: 70, y: 220, label: "Node 3", type: "node" },
            { id: "n4", x: 190, y: 220, label: "Node 4", type: "node" },
            { id: "n5", x: 310, y: 220, label: "Node 5", type: "node" },
            { id: "n6", x: 430, y: 220, label: "Node 6", type: "node" },
            { id: "leaf1", x: 130, y: 310, label: "Leaf A", type: "leaf" },
            { id: "leaf2", x: 250, y: 310, label: "Leaf B", type: "leaf" },
            { id: "leaf3", x: 370, y: 310, label: "Leaf C", type: "leaf" },
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
      case "gfg":
        return [
          ["root", "n1"],
          ["root", "n2"],
          ["n1", "n3"],
          ["n1", "n4"],
          ["n2", "n5"],
          ["n2", "n6"],
          ["n3", "leaf1"],
          ["n4", "leaf1"],
          ["n4", "leaf2"],
          ["n5", "leaf2"],
          ["n5", "leaf3"],
          ["n6", "leaf3"],
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
