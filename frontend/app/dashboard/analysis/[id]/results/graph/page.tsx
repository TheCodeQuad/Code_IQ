"use client"

import { useState, useCallback, useRef, useEffect, useMemo } from "react"
import { useParams } from "next/navigation"
import dynamic from "next/dynamic"
import JSZip from "jszip"
import { saveAs } from "file-saver"
import { getRawLabel, getWrappedLabel } from "@/lib/graph-labels"
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
  Minimize2,
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
  FileJson,
  ImageIcon,
  Archive,
  Layers,
  Lock,
  Unlock,
} from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu"

// Import Cytoscape component with dynamic import (already handles SSR)
import CytoscapeGraph, { type CytoscapeRef } from "@/components/cytoscape-graph"

type GraphType = "agents-flow" | "cfg" | "pdg" | "hpg" | "dag" | "ckg"
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
  { id: "ckg", label: "PKG", fullName: "Program Knowledge Graph", description: "Complete unified graph combining all graph types: hierarchy (module→class→function→statement), calls, imports, inheritance, control flow, and data flow. Shows the full repository structure." },
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
const API_BASE = ""

const isValidComponentId = (id: unknown): id is string => {
  if (typeof id !== "string") return false
  const trimmed = id.trim()
  if (!trimmed) return false
  const lowered = trimmed.toLowerCase()
  return lowered !== "undefined" && lowered !== "null"
}

export default function GraphsPage() {
  const params = useParams<{ id?: string | string[] }>()
  const routeId = Array.isArray(params?.id) ? params.id[0] : params?.id

  const [components, setComponents] = useState<Component[]>([])
  const [selectedComponent, setSelectedComponent] = useState<Component | null>(null)
  const [selectedGraphType, setSelectedGraphType] = useState<GraphType>("cfg")
  const [zoom, setZoom] = useState(100)
  const [isGraphFullscreen, setIsGraphFullscreen] = useState(false)
  const [fullscreenZoom, setFullscreenZoom] = useState(1)
  const [fullscreenPan, setFullscreenPan] = useState({ x: 0, y: 0 })
  const [isDraggingFullscreen, setIsDraggingFullscreen] = useState(false)
  const [lastMousePos, setLastMousePos] = useState({ x: 0, y: 0 })
  const [isBackgroundLocked, setIsBackgroundLocked] = useState(false)

  // Graph data state
  const [cfgData, setCfgData] = useState<GraphData | null>(null)
  const [pdgData, setPdgData] = useState<GraphData | null>(null)
  const [hpgData, setHpgData] = useState<GraphData | null>(null)
  const [dagData, setDagData] = useState<GraphData | null>(null)
  const [ckgData, setCkgData] = useState<GraphData | null>(null)
  const cyRef = useRef<CytoscapeRef | null>(null)
  const [isExporting, setIsExporting] = useState(false)
  const [exportProgress, setExportProgress] = useState({ current: 0, total: 0, label: "" })

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
  const [lastError, setLastError] = useState<string | null>(null)
  const [manualRepoPath, setManualRepoPath] = useState("")
  const [showPathInput, setShowPathInput] = useState(false)

  // Resolve repo path from analysis ID
  useEffect(() => {
    const resolveRepoPath = async () => {
      if (!routeId) return

      try {
        const analysisResponse = await fetch(`/api/analysis/${routeId}/repo`)
        if (analysisResponse.ok) {
          const analysisData = await analysisResponse.json()
          console.log("[Graph] Analysis repo data:", analysisData)

          let path =
            analysisData.repo_path ||
            analysisData.local_path ||
            analysisData.repository_path ||
            analysisData.repo_local_path ||
            analysisData.path

          if (path && typeof path === 'string') {
            path = path.replace(/\\/g, '/')
            const invalidPatterns = ['/backend', '/frontend', '/node_modules', 'Code_IQ/backend', 'Code_IQ/frontend']
            const isInvalidPath = invalidPatterns.some(pattern => path.toLowerCase().includes(pattern.toLowerCase()))
            if (!isInvalidPath) {
              console.log("[Graph] Resolved repo path from analysis:", path)
              setRepoPath(path)
              return
            } else {
              console.warn("[Graph] Resolved path appears to be a system folder, ignoring:", path)
            }
          }
        } else {
          console.log("[Graph] Analysis endpoint not available or returned error:", analysisResponse.status)
        }

        try {
          const response = await fetch(`/api/repos/${routeId}`)
          if (response.ok) {
            const data = await response.json()
            console.log("[Graph] Repo data:", data)
            let path = data.local_path || data.repo_local_path || data.repo_path || `./repos/${data.repo_name}`
            if (typeof path === 'string') {
              path = path.replace(/\\/g, '/')
              const invalidPatterns = ['/backend', '/frontend', '/node_modules', 'Code_IQ/backend', 'Code_IQ/frontend']
              const isInvalidPath = invalidPatterns.some(pattern => path.toLowerCase().includes(pattern.toLowerCase()))
              if (!isInvalidPath) {
                console.log("[Graph] Resolved repo path from repos endpoint:", path)
                setRepoPath(path)
                return
              }
            }
          }
        } catch (err) {
          console.error("Error fetching repo by ID:", err)
        }

        console.log("[Graph] Could not resolve repository path from analysis metadata")
        setRepoPath(null)
        setLastError("Repository path not found. Please manually enter the path or ensure the analysis was created with a valid repository.")
      } catch (err) {
        console.error("Error resolving repo path:", err)
        setRepoPath(null)
        setLastError("Error resolving repository path. Please manually enter it below.")
      }
    }

    resolveRepoPath()
  }, [routeId])

  // Parse repository and fetch components
  useEffect(() => {
    if (!repoPath) {
      console.log("[Graph] No repoPath set yet")
      return
    }

    const parseAndFetchComponents = async () => {
      console.log("[Graph] Starting parse and fetch with repoPath:", repoPath)
      setComponentsLoading(true)

      if (!repoPath || repoPath.trim() === "") {
        setLastError("Repository path is not set. Please manually enter a valid repository path in the sidebar.")
        setComponentsLoading(false)
        return
      }

      setComponents([])
      setSelectedComponent(null)
      setCfgData(null)
      setPdgData(null)
      setHpgData(null)
      setDagData(null)
      setGraphError(null)

      try {
        console.log("[Graph] Calling parse endpoint with repo_path:", repoPath)
        const parseResponse = await fetch(`${API_BASE}/api/graphs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ repo_path: repoPath, force: false })
        })

        console.log("[Graph] Parse response status:", parseResponse.status)
        let parseError: string | null = null

        if (parseResponse.ok) {
          const parseData = await parseResponse.json()
          console.log("[Graph] Parse data:", parseData)
          setParseStatus({
            is_parsed: true,
            function_count: parseData.function_count || 0,
            class_count: parseData.class_count || 0
          })
        } else {
          const errText = await parseResponse.text()
          parseError = `Parse failed: ${parseResponse.status} - ${errText}`
          console.error("[Graph]", parseError)
          if (parseResponse.status === 400 && errText.includes("Invalid repository path")) {
            setLastError(`❌ Invalid repository path: "${repoPath}"\n\nMake sure to:\n• Enter the root directory of a code repository (not backend/frontend folders)\n• Use a path that exists on the server\n• Verify the path contains source code files`)
          } else {
            setLastError(`Repository parse error: ${errText.substring(0, 200)}`)
          }
        }

        console.log("[Graph] Fetching components with repo_path:", repoPath)
        const componentsResponse = await fetch(
          `${API_BASE}/api/graphs?repo_path=${encodeURIComponent(repoPath)}`
        )

        console.log("[Graph] Components response status:", componentsResponse.status)
        if (componentsResponse.ok) {
          const data = await componentsResponse.json()
          console.log("[Graph] Components data received:", data)
          if (data.components && data.components.length > 0) {
            const mappedComponents: Component[] = data.components
              .map((c: any) => ({
                id: c?.id,
                name: c?.name,
                type: c?.type as ComponentType,
                filePath: c?.file_path,
                parentClass: c?.parent_class,
                start_line: c?.start_line,
                end_line: c?.end_line,
              }))
              .filter((c: Component) => isValidComponentId(c.id) && Boolean(c.name))
            console.log("[Graph] Mapped", mappedComponents.length, "components")
            setComponents(mappedComponents)
            setLastError(null)
            if (mappedComponents.length > 0) {
              setSelectedComponent(mappedComponents[0])
              console.log("[Graph] Auto-selected first component:", mappedComponents[0].name)
            }
          } else {
            console.warn("[Graph] No components in response or empty array")
            setLastError(`No components found in repository. Repository may be empty or invalid.`)
          }
        } else {
          const errText = await componentsResponse.text()
          const errorMsg = `Components fetch failed: ${componentsResponse.status} - ${errText.substring(0, 150)}`
          if (componentsResponse.status === 400 && errText.includes("Invalid repository path")) {
            setLastError(`❌ Repository path is invalid: "${repoPath}"\n\nPlease verify:\n• The path exists on the server\n• The path points to a code repository (not backend/frontend folders)\n• You have permission to access it`)
          } else {
            setLastError(errorMsg)
          }
          console.error("[Graph]", errorMsg)
          setLastError(errorMsg)
        }
      } catch (err: any) {
        const errorMsg = err?.message || String(err)
        console.error("Error fetching components:", err)
        setLastError(`Network error: ${errorMsg}`)
      } finally {
        setComponentsLoading(false)
      }
    }

    parseAndFetchComponents()
  }, [repoPath])

  // Fetch graph data when graph type changes
  useEffect(() => {
    if (!repoPath) return
    if (selectedGraphType !== "ckg" && !selectedComponent?.id) return
    if (selectedGraphType === "agents-flow") return

    if (selectedComponent?.type === "class" && !["dag", "ckg"].includes(selectedGraphType)) {
      setGraphLoading(false)
      setGraphError("CFG/PDG/HPG are only available for functions/methods")
      return
    }

    const fetchGraphData = async () => {
      setGraphLoading(true)
      setGraphError(null)

      try {
        let endpoint = ""
        switch (selectedGraphType) {
          case "cfg":
            endpoint = `${API_BASE}/api/graphs/cfg/${encodeURIComponent(selectedComponent.id)}?repo_path=${encodeURIComponent(repoPath)}`
            break
          case "pdg":
            endpoint = `${API_BASE}/api/graphs/pdg/${encodeURIComponent(selectedComponent.id)}?repo_path=${encodeURIComponent(repoPath)}`
            break
          case "hpg":
            endpoint = `${API_BASE}/api/graphs/hpg/${encodeURIComponent(selectedComponent.id)}?repo_path=${encodeURIComponent(repoPath)}`
            break
          case "dag":
            endpoint = `${API_BASE}/api/graphs/dag?repo_path=${encodeURIComponent(repoPath)}&component_id=${encodeURIComponent(selectedComponent.id)}`
            break
          case "ckg":
            endpoint = `${API_BASE}/api/graphs/ckg?repo_path=${encodeURIComponent(repoPath)}&force=true`
            break
        }

        const timeoutMap: Record<GraphType, number> = {
          "agents-flow": 30_000,
          "cfg": 60_000,
          "pdg": 60_000,
          "hpg": 90_000,
          "dag": 300_000,
          "ckg": 300_000,
        }

        const timeoutMs = timeoutMap[selectedGraphType] || 120_000
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

        const response = await fetch(endpoint, { signal: controller.signal }).finally(() => {
          clearTimeout(timeoutId)
        })

        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(errorText || `Failed to fetch ${selectedGraphType.toUpperCase()}`)
        }

        const result = await response.json()

        if (result.success && result.data) {
          let graphData: GraphData
          if (selectedGraphType === "ckg") {
            const nodes = result.data.nodes || []
            const edges = result.data.edges || []
            const stats = result.data.stats || {}

            graphData = {
              id: "ckg",
              name: "Program Knowledge Graph",
              type: "ckg",
              nodes: nodes,
              edges: edges,
              node_count: stats?.node_count || nodes.length,
              edge_count: stats?.edge_count || edges.length,
              metadata: stats
            }

            console.log("[Graph] PKG data received:", {
              node_count: graphData.node_count,
              edge_count: graphData.edge_count,
              node_types: stats?.node_types,
              edge_types: stats?.edge_types,
              has_nodes: nodes.length > 0,
              has_edges: edges.length > 0,
              repo_path: stats?.repo_path,
              warning: result.warning
            })

            if (nodes.length === 0 || edges.length === 0) {
              const warningMsg = result.warning || "No code components found in repository"
              console.warn("[Graph] PKG graph is empty:", {
                repo_path: repoPath,
                nodes_count: nodes.length,
                edges_count: edges.length,
                warning: warningMsg
              })
              if (nodes.length === 0) {
                setGraphError(`📊 Program Knowledge Graph is empty\n\n${warningMsg}\n\nMake sure your repository:\n• Contains Python files (.py)\n• Has functions or classes defined\n• Is not in an excluded folder (e.g., __pycache__, .git, venv)`)
              }
            }
          } else {
            graphData = result.data as GraphData
          }

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
            case "ckg":
              setCkgData(graphData)
              break
          }
        } else {
          throw new Error(result.message || "Invalid response")
        }
      } catch (err: any) {
        console.error(`Error fetching ${selectedGraphType}:`, err)
        const isAbort = err instanceof Error && err.name === "AbortError"

        let errorMessage = ""
        if (isAbort) {
          const timeoutSeconds = selectedGraphType === "dag" || selectedGraphType === "ckg" ? 300 : 60
          errorMessage = `${selectedGraphType.toUpperCase()} request timed out after ${timeoutSeconds}s. `
          if (selectedGraphType === "dag" || selectedGraphType === "ckg") {
            errorMessage += "These are expensive operations on large repositories. Try:\n"
            errorMessage += "• Check if the repository is very large\n"
            errorMessage += "• Analyze a smaller subset of the code\n"
            errorMessage += "• Check backend logs for performance issues"
          } else {
            errorMessage += "The backend may be slow or unresponsive."
          }
        } else {
          errorMessage = err.message || `Failed to load ${selectedGraphType.toUpperCase()}`
        }

        setGraphError(errorMessage)
      } finally {
        setGraphLoading(false)
      }
    }

    fetchGraphData()
  }, [selectedGraphType, repoPath, selectedComponent?.id])

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
      case "ckg": return ckgData
      default: return null
    }
  }, [selectedGraphType, cfgData, pdgData, hpgData, dagData, ckgData])

  const currentGraph = graphTypes.find((g) => g.id === selectedGraphType)
  const selectedComponentFlow = selectedComponent ? componentFlows[selectedComponent.id] : null
  const isPkgView = selectedGraphType === "ckg"

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 25, 200))
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 25, 50))
  const handleReset = () => setZoom(100)

  const handleFullscreenZoomIn = () => setFullscreenZoom((prev) => Math.min(prev * 1.25, 5))
  const handleFullscreenZoomOut = () => setFullscreenZoom((prev) => Math.max(prev / 1.25, 0.25))
  const handleFullscreenReset = () => {
    setFullscreenZoom(1)
    setFullscreenPan({ x: 0, y: 0 })
  }

  const handleFullscreenMouseDown = (e: React.MouseEvent) => {
    if (isBackgroundLocked) return
    setIsDraggingFullscreen(true)
    setLastMousePos({ x: e.clientX, y: e.clientY })
  }

  const handleFullscreenMouseMove = (e: React.MouseEvent) => {
    if (!isDraggingFullscreen || isBackgroundLocked) return
    const dx = e.clientX - lastMousePos.x
    const dy = e.clientY - lastMousePos.y
    setFullscreenPan((prev) => ({ x: prev.x + dx, y: prev.y + dy }))
    setLastMousePos({ x: e.clientX, y: e.clientY })
  }

  const handleFullscreenMouseUp = () => {
    setIsDraggingFullscreen(false)
  }

  const handleFullscreenWheel = (e: React.WheelEvent) => {
    e.preventDefault()
    if (e.deltaY < 0) {
      handleFullscreenZoomIn()
    } else {
      handleFullscreenZoomOut()
    }
  }

  const exportAllAsZip = useCallback(async (scope: "all" | "component") => {
    if (!repoPath || isExporting) return
    setIsExporting(true)
    const zip = new JSZip()

    const targets = scope === "component" && selectedComponent
      ? [selectedComponent]
      : components

    setExportProgress({ current: 0, total: targets.length * 4 + 1, label: "Initializing export..." })

    try {
      let completed = 0
      const total = targets.length * 4 + 1

      for (const comp of targets) {
        const folder = zip.folder(comp.name.replace(/[^a-z0-9]/gi, '_'))

        const types: GraphType[] = ["cfg", "pdg", "hpg", "dag"]
        for (const type of types) {
          setExportProgress({
            current: completed++,
            total,
            label: `Fetching ${type.toUpperCase()} for ${comp.name}...`
          })

          try {
            let endpoint = ""
            if (type === "dag") {
              endpoint = `${API_BASE}/api/graphs/dag?repo_path=${encodeURIComponent(repoPath)}&component_id=${encodeURIComponent(comp.id)}`
            } else {
              endpoint = `${API_BASE}/api/graphs/${type}/${encodeURIComponent(comp.id)}?repo_path=${encodeURIComponent(repoPath)}`
            }

            const res = await fetch(endpoint)
            if (res.ok) {
              const result = await res.json()
              if (result.success && result.data) {
                folder?.file(`${type}.json`, JSON.stringify(result.data, null, 2))
              }
            }
          } catch (err) {
            console.error(`Failed to fetch ${type} for ${comp.name}:`, err)
          }
        }
      }

      setExportProgress({ current: completed++, total, label: "Fetching Program Knowledge Graph..." })
      try {
        const ckgRes = await fetch(`${API_BASE}/api/graphs/ckg?repo_path=${encodeURIComponent(repoPath)}&force=false`)
        if (ckgRes.ok) {
          const result = await ckgRes.json()
          if (result.success && result.data) {
            zip.file("program_knowledge_graph.json", JSON.stringify(result.data, null, 2))
          }
        }
      } catch (err) {
        console.error("Failed to fetch CKG for ZIP:", err)
      }

      setExportProgress({ current: total, total, label: "Generating ZIP archive..." })
      const content = await zip.generateAsync({ type: "blob" })
      saveAs(content, `CodeIQ_Export_${new Date().toISOString().split('T')[0]}.zip`)
    } catch (err) {
      console.error("Export all failed:", err)
    } finally {
      setIsExporting(false)
      setExportProgress({ current: 0, total: 0, label: "" })
    }
  }, [repoPath, components, selectedComponent, isExporting])

  const handleExport = useCallback((format: "svg" | "png" | "json" | "zip" | "zip-component") => {
    if (format === "zip") {
      exportAllAsZip("all")
      return
    }
    if (format === "zip-component") {
      exportAllAsZip("component")
      return
    }

    const fileName = `${selectedComponent?.name || "repository"}_${selectedGraphType}`

    if (format === "json") {
      try {
        const dataStr = JSON.stringify(currentGraphData, null, 2)
        const blob = new Blob([dataStr], { type: "application/json" })
        const url = URL.createObjectURL(blob)
        const link = document.createElement("a")
        link.href = url
        link.download = `${fileName}.json`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
      } catch (e) {
        console.error("JSON Export failed:", e)
      }
      return
    }

    if (selectedGraphType === "ckg") {
      if (cyRef.current) {
        cyRef.current.exportImage()
      }
      return
    }

    const svgElement = document.querySelector(".center-panel-svg") as SVGSVGElement
    if (!svgElement) {
      console.error("SVG element not found for export")
      return
    }

    try {
      const serializer = new XMLSerializer()
      let source = serializer.serializeToString(svgElement)

      if (!source.match(/^<svg[^>]+xmlns="http\:\/\/www\.w3\.org\/2000\/svg"/)) {
        source = source.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
      }
      if (!source.match(/^<svg[^>]+xmlns\:xlink="http\:\/\/www\.w3\.org\/1999\/xlink"/)) {
        source = source.replace(/^<svg/, '<svg xmlns:xlink="http://www.w3.org/1999/xlink"');
      }

      const xmlDeclaration = '<?xml version="1.0" standalone="no"?>\r\n';
      const svgBlob = new Blob([xmlDeclaration, source], { type: "image/svg+xml;charset=utf-8" })
      const url = URL.createObjectURL(svgBlob)

      if (format === "svg") {
        const link = document.createElement("a")
        link.href = url
        link.download = `${fileName}.svg`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
      } else if (format === "png") {
        const img = new Image()
        const bbox = svgElement.getBBox()
        const padding = 80
        const scale = 2
        const contentWidth = bbox.width + padding * 2
        const contentHeight = bbox.height + padding * 2
        const clone = svgElement.cloneNode(true) as SVGSVGElement
        clone.setAttribute("viewBox", `${bbox.x - padding} ${bbox.y - padding} ${contentWidth} ${contentHeight}`)
        clone.setAttribute("width", contentWidth.toString())
        clone.setAttribute("height", contentHeight.toString())

        const serializer = new XMLSerializer()
        let svgStr = serializer.serializeToString(clone)

        if (!svgStr.includes("http://www.w3.org/2000/svg")) {
          svgStr = svgStr.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
        }

        const blob = new Blob([svgStr], { type: "image/svg+xml;charset=utf-8" })
        const blobUrl = URL.createObjectURL(blob)

        img.onload = () => {
          const canvas = document.createElement("canvas")
          canvas.width = contentWidth * scale
          canvas.height = contentHeight * scale
          const ctx = canvas.getContext("2d")
          if (ctx) {
            ctx.fillStyle = "white"
            ctx.fillRect(0, 0, canvas.width, canvas.height)
            ctx.scale(scale, scale)
            ctx.drawImage(img, 0, 0)
            const pngUrl = canvas.toDataURL("image/png", 1.0)
            const link = document.createElement("a")
            link.href = pngUrl
            link.download = `${fileName}.png`
            link.click()
          }
          URL.revokeObjectURL(blobUrl)
        }
        img.src = blobUrl
      }
    } catch (e) {
      console.error("Export failed:", e)
    }
  }, [selectedGraphType, selectedComponent?.name, currentGraphData, cyRef, exportAllAsZip])

  useEffect(() => {
    const handleGlobalExport = (e: any) => {
      if (e.detail?.scope === "all") {
        exportAllAsZip("all")
      }
    }
    window.addEventListener("codeiq:export-all", handleGlobalExport)
    return () => window.removeEventListener("codeiq:export-all", handleGlobalExport)
  }, [exportAllAsZip])

  const handleRefresh = async () => {
    if (!repoPath) return

    setGraphLoading(true)
    try {
      await fetch(`${API_BASE}/api/graphs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_path: repoPath, force: true })
      })

      setCfgData(null)
      setPdgData(null)
      setHpgData(null)
      setDagData(null)

      const componentsResponse = await fetch(
        `${API_BASE}/api/graphs?repo_path=${encodeURIComponent(repoPath)}`
      )
      if (componentsResponse.ok) {
        const data = await componentsResponse.json()
        if (data.components && data.components.length > 0) {
          const mapped: Component[] = data.components
            .map((c: any) => ({
              id: c?.id,
              name: c?.name,
              type: c?.type,
              filePath: c?.file_path,
              parentClass: c?.parent_class,
              start_line: c?.start_line,
              end_line: c?.end_line,
            }))
            .filter((c: Component) => isValidComponentId(c.id) && Boolean(c.name))
          setComponents(mapped)
          if (mapped.length > 0) setSelectedComponent(mapped[0])
        }
      }
    } catch (err) {
      console.error("Error refreshing:", err)
    } finally {
      setGraphLoading(false)
    }
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-200px)] min-h-[700px]">
      {/* Left Panel - Component List */}
      <Card className={`w-72 flex-shrink-0 border-stone-200 bg-white ${isPkgView ? "hidden" : ""}`}>
        <CardHeader className="pb-3 border-b border-stone-100">
          <CardTitle className="text-sm flex items-center gap-2 text-stone-700">
            <Network className="w-4 h-4" />
            Components
          </CardTitle>
          <p className="text-xs text-stone-500 mt-1">
            {componentsLoading ? "Loading..." : `${components.length} components`}
          </p>
          {components.length === 0 && !componentsLoading && repoPath && (
            <Button
              size="sm"
              variant="outline"
              className="mt-2 h-7 text-xs w-full"
              onClick={async () => {
                setComponentsLoading(true)
                try {
                  const response = await fetch(`${API_BASE}/api/graphs`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ repo_path: repoPath, force: true })
                  })
                  const data = await response.json()
                  console.log("[Graph] Manual parse result:", data)
                  if (data.success) {
                    const compResponse = await fetch(
                      `${API_BASE}/api/graphs?repo_path=${encodeURIComponent(repoPath)}`
                    )
                    const compData = await compResponse.json()
                    if (compData.components) {
                      const mapped = compData.components.map((c: any) => ({
                        id: c?.id,
                        name: c?.name,
                        type: c?.type,
                        filePath: c?.file_path,
                        parentClass: c?.parent_class,
                        start_line: c?.start_line,
                        end_line: c?.end_line,
                      })).filter((c: Component) => isValidComponentId(c.id) && Boolean(c.name))
                      setComponents(mapped)
                      if (mapped.length > 0) setSelectedComponent(mapped[0])
                    }
                  }
                } catch (err) {
                  console.error("[Graph] Manual parse error:", err)
                } finally {
                  setComponentsLoading(false)
                }
              }}
            >
              Parse Repository
            </Button>
          )}
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
                    onClick={() => {
                      if (selectedGraphType !== "ckg") {
                        setSelectedComponent(component)
                      }
                    }}
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
                    {selectedGraphType !== "ckg" && selectedComponent?.id === component.id && (
                      <ChevronRight className="w-4 h-4 flex-shrink-0 text-amber-500" />
                    )}
                  </button>
                ))
              ) : (
                <div className="p-4 space-y-3">
                  {lastError && (
                    <div className="p-3 bg-red-50 rounded-lg border border-red-200">
                      <p className="text-xs font-medium text-red-700 mb-1">⚠️ Error</p>
                      <p className="text-xs text-red-600 break-words">{lastError}</p>
                    </div>
                  )}

                  <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
                    <p className="text-xs font-medium text-amber-700 mb-1">Repository Path</p>
                    {repoPath ? (
                      <p className="text-xs text-amber-600 break-all font-mono bg-white p-2 rounded border border-amber-100">{repoPath}</p>
                    ) : (
                      <p className="text-xs text-amber-600">Not resolved yet...</p>
                    )}
                  </div>

                  <div>
                    <p className="text-xs font-medium text-stone-600 mb-2">Manual Repository Path</p>
                    <div className="flex gap-1">
                      <input
                        type="text"
                        placeholder="e.g., /path/to/repo or c:/repos/myproject"
                        value={manualRepoPath}
                        onChange={(e) => setManualRepoPath(e.target.value)}
                        className="flex-1 px-2 py-1.5 text-xs border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                      />
                      <Button
                        size="sm"
                        className="h-7 text-xs px-2"
                        onClick={() => {
                          if (manualRepoPath.trim()) {
                            const normalizedPath = manualRepoPath.trim().replace(/\\/g, '/')
                            setRepoPath(normalizedPath)
                            console.log("[Graph] Manual repo path set to:", normalizedPath)
                          }
                        }}
                      >
                        Use
                      </Button>
                    </div>
                  </div>

                  {repoPath && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="w-full h-8 text-xs"
                      onClick={async () => {
                        setComponentsLoading(true)
                        try {
                          console.log("[Graph] Force parsing repository:", repoPath)
                          const response = await fetch(`${API_BASE}/api/graphs`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ repo_path: repoPath, force: true })
                          })
                          const data = await response.json()
                          console.log("[Graph] Force parse result:", data)
                          if (data.success) {
                            setLastError(null)
                            const compResponse = await fetch(
                              `${API_BASE}/api/graphs?repo_path=${encodeURIComponent(repoPath)}`
                            )
                            const compData = await compResponse.json()
                            if (compData.components) {
                              const mapped = compData.components
                                .map((c: any) => ({
                                  id: c?.id,
                                  name: c?.name,
                                  type: c?.type,
                                  filePath: c?.file_path,
                                  parentClass: c?.parent_class,
                                  start_line: c?.start_line,
                                  end_line: c?.end_line,
                                }))
                                .filter((c: Component) => isValidComponentId(c.id) && Boolean(c.name))
                              setComponents(mapped)
                              if (mapped.length > 0) {
                                setSelectedComponent(mapped[0])
                                console.log("[Graph] Force parse succeeded, loaded", mapped.length, "components")
                              } else {
                                setLastError("Parse succeeded but no components found. Repository may be empty.")
                              }
                            }
                          } else {
                            setLastError(`Parse failed: ${data.message}`)
                          }
                        } catch (err: any) {
                          setLastError(`Error during parse: ${err?.message || String(err)}`)
                          console.error("[Graph] Force parse error:", err)
                        } finally {
                          setComponentsLoading(false)
                        }
                      }}
                      disabled={componentsLoading}
                    >
                      {componentsLoading ? "Parsing..." : "Force Parse Repository"}
                    </Button>
                  )}

                  <div className="pt-2 border-t border-stone-200">
                    <p className="text-xs text-stone-500">
                      <strong>Troubleshooting:</strong><br/>
                      • Check that the repository path exists<br/>
                      • Verify the backend is running<br/>
                      • Check browser console (F12) for detailed errors
                    </p>
                  </div>
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
              {selectedGraphType !== "ckg" && (
                <>
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
                </>
              )}
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                onClick={() => setIsGraphFullscreen((prev) => !prev)}
                title={isGraphFullscreen ? "Exit fullscreen" : "Fullscreen graph"}
              >
                {isGraphFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="gap-1.5 h-7 text-xs border-stone-200" disabled={isExporting}>
                    {isExporting ? (
                      <Loader className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Download className="w-3.5 h-3.5" />
                    )}
                    {isExporting ? "Exporting..." : "Export"}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuLabel>Export Graph</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => handleExport("svg")} disabled={selectedGraphType === "ckg"}>
                    <FileText className="mr-2 h-4 w-4" />
                    <span>SVG (Vector)</span>
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleExport("png")}>
                    <ImageIcon className="mr-2 h-4 w-4" />
                    <span>PNG (Image)</span>
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleExport("json")}>
                    <FileJson className="mr-2 h-4 w-4" />
                    <span>JSON (Raw Data)</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuLabel>Batch Export</DropdownMenuLabel>
                  <DropdownMenuItem onClick={() => handleExport("zip-component")}>
                    <Layers className="mr-2 h-4 w-4" />
                    <span>Export Component (ZIP)</span>
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleExport("zip")}>
                    <Archive className="mr-2 h-4 w-4" />
                    <span>Export All (ZIP)</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex-1 p-0 overflow-hidden relative">
          {isExporting && (
            <div className="absolute inset-0 z-50 bg-white/80 backdrop-blur-sm flex items-center justify-center">
              <div className="bg-white p-6 rounded-2xl shadow-2xl border border-stone-200 max-w-sm w-full flex flex-col items-center gap-4 animate-in fade-in zoom-in duration-300">
                <div className="w-16 h-16 rounded-full bg-amber-50 flex items-center justify-center">
                  <Archive className="w-8 h-8 text-amber-500 animate-bounce" />
                </div>
                <div className="text-center space-y-1">
                  <h3 className="font-bold text-stone-900 text-lg">Preparing Export</h3>
                  <p className="text-stone-500 text-sm">{exportProgress.label}</p>
                </div>
                <div className="w-full bg-stone-100 h-2 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-amber-500 transition-all duration-300 ease-out"
                    style={{ width: `${(exportProgress.current / exportProgress.total) * 100}%` }}
                  />
                </div>
                <p className="text-xs text-stone-400 font-medium">
                  Step {exportProgress.current} of {exportProgress.total}
                </p>
              </div>
            </div>
          )}
          <div
            className="w-full h-full flex items-center justify-center bg-stone-50/50"
            style={selectedGraphType !== "ckg" ? { transform: `scale(${zoom / 100})`, transformOrigin: "center center" } : undefined}
          >
            {selectedComponent && selectedGraphType === "agents-flow" ? (
              <AgentsFlowGraph
                component={selectedComponent}
                componentFlow={selectedComponentFlow || undefined}
              />
            ) : selectedGraphType === "ckg" && currentGraphData ? (
              currentGraphData.node_count === 0 || currentGraphData.edge_count === 0 ? (
                <div className="flex flex-col items-center justify-center h-full gap-3 p-8">
                  <AlertCircle className="w-12 h-12 text-amber-400" />
                  <p className="text-sm font-semibold text-stone-700">Program Knowledge Graph is Empty</p>
                  <p className="text-xs text-stone-600 text-center max-w-md leading-relaxed">
                    No code components were found in the repository. This typically means:
                  </p>
                  <ul className="text-xs text-stone-600 space-y-1 text-left bg-amber-50 p-3 rounded-lg border border-amber-200 max-w-md">
                    <li>❌ The repository path doesn't contain Python files</li>
                    <li>❌ All Python files are in excluded folders (<code>__pycache__</code>, <code>.git</code>, <code>venv</code>, etc.)</li>
                    <li>❌ Python files only contain comments/docstrings, no actual code</li>
                    <li>❌ The repository hasn't been parsed yet</li>
                  </ul>
                  <div className="flex gap-2 pt-2">
                    <Button variant="outline" size="sm" onClick={handleRefresh}>
                      Refresh
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => {
                      if (repoPath) {
                        setComponentsLoading(true)
                        fetch(`${API_BASE}/api/graphs`, {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ repo_path: repoPath, force: true })
                        })
                          .then(() => handleRefresh())
                          .finally(() => setComponentsLoading(false))
                      }
                    }}>
                      Force Parse
                    </Button>
                  </div>
                </div>
              ) : (
                <CytoscapeGraph
                  graphData={currentGraphData}
                  onNodeClick={(nodeId, nodeData) => {
                    console.log("Node clicked:", nodeId, nodeData)
                  }}
                  className="w-full h-full"
                  ref={cyRef}
                />
              )
            ) : (selectedComponent || selectedGraphType === "ckg") && currentGraphData ? (
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
            ) : selectedGraphType === "ckg" ? (
              <div className="flex flex-col items-center justify-center h-full gap-3">
                <Network className="w-10 h-10 text-amber-400" />
                <p className="text-sm text-stone-500">Loading Program Knowledge Graph...</p>
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
      <Card className={`w-80 flex-shrink-0 border-stone-200 bg-white flex flex-col overflow-hidden ${isPkgView ? "hidden" : ""}`}>
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

      {/* ============================================================
          FULLSCREEN OVERLAY
      ============================================================ */}
      {isGraphFullscreen && (
        <div className="fixed inset-0 z-50 bg-white">
          <div className="relative h-full w-full flex flex-col">

            {/* ── Top Bar ── */}
            <div className="h-14 border-b border-stone-200 px-6 flex items-center justify-between bg-white flex-shrink-0">
              {/* Left: badge + title */}
              <div className="flex items-center gap-3">
                <Badge className="bg-amber-400 text-white text-sm px-3 py-1">{currentGraph?.label}</Badge>
                <span className="text-base font-semibold text-stone-700">{currentGraph?.fullName}</span>
              </div>

              {/* Right: zoom controls + exit */}
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 bg-stone-100 rounded-lg p-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0 hover:bg-stone-200"
                    onClick={handleFullscreenZoomOut}
                  >
                    <ZoomOut className="w-5 h-5 text-stone-600" />
                  </Button>
                  <span className="text-sm font-bold min-w-[3.5rem] text-center text-stone-700">
                    {Math.round(fullscreenZoom * 100)}%
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0 hover:bg-stone-200"
                    onClick={handleFullscreenZoomIn}
                  >
                    <ZoomIn className="w-5 h-5 text-stone-600" />
                  </Button>
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0 hover:bg-stone-100"
                  onClick={handleFullscreenReset}
                  title="Reset zoom and pan"
                >
                  <RotateCcw className="w-5 h-5 text-stone-600" />
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  className="h-9 px-4 gap-2 text-sm font-semibold border-stone-300 hover:bg-stone-100"
                  onClick={() => setIsGraphFullscreen(false)}
                >
                  <Minimize2 className="w-4 h-4" />
                  Exit
                </Button>
              </div>
            </div>

            {/* ── Pan / Nodes toggle — floats below the top bar, right-aligned ── */}
            <div className="absolute top-14 right-6 z-20 pt-3">
              <button
                onClick={() => setIsBackgroundLocked(!isBackgroundLocked)}
               className={[
  "flex items-center gap-3 px-6 py-3 rounded-xl text-base font-semibold",
  "border transition-all duration-200 select-none",
  "focus:outline-none focus:ring-2 focus:ring-stone-300",
  isBackgroundLocked
    ? "bg-stone-900 text-white border-stone-900 shadow-md"
    : "bg-white text-stone-700 border-stone-300 hover:bg-stone-100 shadow-sm",
].join(" ")}
                title={isBackgroundLocked ? "Switch to pan background mode" : "Switch to drag nodes mode"}
              >
                {isBackgroundLocked ? (
                  <>
                    <Lock className="w-5 h-5" />
                    Drag Nodes
                  </>
                ) : (
                  <>
                    <Unlock className="w-5 h-5" />
                    Pan Background
                  </>
                )}
              </button>
            </div>

            {/* ── Canvas ── */}
            <div
              className={[
                "flex-1 bg-white overflow-hidden",
                isBackgroundLocked ? "cursor-default" : "cursor-grab active:cursor-grabbing",
              ].join(" ")}
              onMouseDown={handleFullscreenMouseDown}
              onMouseMove={handleFullscreenMouseMove}
              onMouseUp={handleFullscreenMouseUp}
              onMouseLeave={handleFullscreenMouseUp}
              onWheel={handleFullscreenWheel}
            >
              <div
                className="w-full h-full flex items-center justify-center transition-transform duration-75 ease-out"
                style={{
                  transform: `translate(${fullscreenPan.x}px, ${fullscreenPan.y}px) scale(${fullscreenZoom})`,
                  transformOrigin: "center center",
                }}
              >
                {selectedComponent && selectedGraphType === "agents-flow" ? (
                  <AgentsFlowGraph
                    component={selectedComponent}
                    componentFlow={selectedComponentFlow || undefined}
                  />
                ) : selectedGraphType === "ckg" && currentGraphData ? (
                  currentGraphData.node_count === 0 || currentGraphData.edge_count === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full gap-3 p-8">
                      <AlertCircle className="w-12 h-12 text-amber-400" />
                      <p className="text-sm font-semibold text-stone-700">Program Knowledge Graph is Empty</p>
                      <p className="text-xs text-stone-600 text-center max-w-md leading-relaxed">
                        No code components were found in the repository. This typically means:
                      </p>
                      <ul className="text-xs text-stone-600 space-y-1 text-left bg-amber-50 p-3 rounded-lg border border-amber-200 max-w-md">
                        <li>❌ The repository path doesn't contain Python files</li>
                        <li>❌ All Python files are in excluded folders (<code>__pycache__</code>, <code>.git</code>, <code>venv</code>, etc.)</li>
                        <li>❌ Python files only contain comments/docstrings, no actual code</li>
                        <li>❌ The repository hasn't been parsed yet</li>
                      </ul>
                    </div>
                  ) : (
                    <CytoscapeGraph
                      graphData={currentGraphData}
                      onNodeClick={(nodeId, nodeData) => {
                        console.log("Node clicked:", nodeId, nodeData)
                      }}
                      className="w-full h-full"
                    />
                  )
                ) : (selectedComponent || selectedGraphType === "ckg") && currentGraphData ? (
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
                  </div>
                ) : selectedGraphType === "ckg" ? (
                  <div className="flex flex-col items-center justify-center h-full gap-3">
                    <Network className="w-10 h-10 text-amber-400" />
                    <p className="text-sm text-stone-500">Loading Program Knowledge Graph...</p>
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
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Real Graph Visualization Component
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

  useEffect(() => {
    if (!graphData?.nodes) return

    const isHybrid = graphType === "hpg"
    const columnSpacing = 200
    const rowSpacing = 110
    const baseX = 120
    const baseY = 80

    const getSortKey = (node: GraphNode) => {
      if (typeof node.y === "number") return node.y
      if (typeof node.line === "number") return node.line
      return 0
    }

    const orderedNodes = isHybrid
      ? [...graphData.nodes].sort((a, b) => {
          const delta = getSortKey(a) - getSortKey(b)
          if (delta !== 0) return delta
          return (a.x || 0) - (b.x || 0) || a.id.localeCompare(b.id)
        })
      : graphData.nodes

    const cols = Math.max(1, Math.ceil(Math.sqrt(orderedNodes.length)))

    const positionedNodes = orderedNodes.map((node, index) => {
      if (!isHybrid && node.x !== undefined && node.y !== undefined) {
        return node
      }

      const row = Math.floor(index / cols)
      const col = index % cols

      return {
        ...node,
        x: baseX + col * columnSpacing,
        y: baseY + row * rowSpacing
      }
    })

    setNodes(positionedNodes)
  }, [graphData, graphType])

  const nodeMetrics = useMemo(() => {
    const metrics: Record<string, { width: number; height: number; lines: string[]; rawLabel: string }> = {}
    const nodeWidth = 176
    const lineHeight = 14
    const paddingY = 18

    nodes.forEach((node) => {
      const rawLabel = getRawLabel(node.label, node.metadata)
      const wrappedLabel = getWrappedLabel(node.label, node.metadata)
      const fallbackLabel = rawLabel || node.label || ""
      const lines = (wrappedLabel || fallbackLabel).split("\n").filter(Boolean)
      const height = Math.max(40, lines.length * lineHeight + paddingY)
      metrics[node.id] = {
        width: nodeWidth,
        height,
        lines: lines.length ? lines : [fallbackLabel],
        rawLabel: fallbackLabel,
      }
    })

    return metrics
  }, [nodes])

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

  const getNodeColor = (nodeType: string) => {
    const colors: Record<string, { bg: string; border: string; text: string }> = {
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
      parameter: { bg: "#fce7f3", border: "#ec4899", text: "#9d174d" },
      assignment: { bg: "#e0e7ff", border: "#6366f1", text: "#3730a3" },
      expression: { bg: "#f3f4f6", border: "#9ca3af", text: "#374151" },
      call: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" },
      function: { bg: "#dbeafe", border: "#3b82f6", text: "#1e40af" },
      method: { bg: "#ccfbf1", border: "#14b8a6", text: "#0f766e" },
      class: { bg: "#f3e8ff", border: "#a855f7", text: "#6b21a8" },
      module: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" },
      selected: { bg: "#dbeafe", border: "#2563eb", text: "#1e3a8a" },
      dependency: { bg: "#dcfce7", border: "#16a34a", text: "#166534" },
      dependent: { bg: "#fef3c7", border: "#d97706", text: "#92400e" },
    }
    return colors[nodeType] || { bg: "#f3f4f6", border: "#9ca3af", text: "#374151" }
  }

  const getEdgeColor = (edgeType: string) => {
    const colors: Record<string, string> = {
      flow: "#9ca3af",
      true: "#22c55e",
      false: "#ef4444",
      back: "#8b5cf6",
      data: "#f59e0b",
      control: "#3b82f6",
      call: "#ec4899",
      inherits: "#8b5cf6",
      imports: "#6366f1",
      hierarchy: "#94a3b8",
      calls: "#ec4899",
      extends: "#8b5cf6",
      control_flow: "#3b82f6",
      data_flow: "#f59e0b",
    }
    return colors[edgeType] || "#9ca3af"
  }

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

  const edgeBendById = useMemo(() => {
    const bends: Record<string, number> = {}
    if (!graphData?.edges) return bends

    const groups = new Map<string, string[]>()
    for (const edge of graphData.edges) {
      const key = `${edge.source}→${edge.target}`
      const ids = groups.get(key) ?? []
      ids.push(edge.id)
      groups.set(key, ids)
    }

    for (const ids of groups.values()) {
      if (ids.length <= 1) {
        if (ids[0]) bends[ids[0]] = 0
        continue
      }
      const spacing = 18
      const start = -((ids.length - 1) / 2) * spacing
      ids.forEach((id, index) => {
        bends[id] = start + index * spacing
      })
    }

    return bends
  }, [graphData?.edges])

  const edgesToRender = useMemo(() => {
    if (!graphData?.edges) return []
    if (graphType !== "hpg") return graphData.edges

    const overlayTypes = new Set(["data_flow", "control_flow"])
    return [...graphData.edges].sort((a, b) => {
      return Number(overlayTypes.has(a.type)) - Number(overlayTypes.has(b.type))
    })
  }, [graphData?.edges, graphType])

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
      className="w-full h-full center-panel-svg"
      style={{ minWidth: "500px", minHeight: "400px" }}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <defs>
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
          <polygon points="0 0, 8 3, 0 6" fill="#f59e0b" />
        </marker>
        <marker id="arrow-control" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#3b82f6" />
        </marker>
        <marker id="arrow-call" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#ec4899" />
        </marker>
      </defs>

      <rect width="100%" height="100%" fill="#fafafa" />

      {edgesToRender.map((edge) => {
        const fromNode = nodes.find((n) => n.id === edge.source)
        const toNode = nodes.find((n) => n.id === edge.target)
        if (!fromNode || !toNode) return null

        const x1 = fromNode.x || 0
        const fromMetrics = nodeMetrics[fromNode.id]
        const toMetrics = nodeMetrics[toNode.id]
        const y1 = (fromNode.y || 0) + (fromMetrics?.height ?? 36) / 2
        const x2 = toNode.x || 0
        const y2 = (toNode.y || 0) - (toMetrics?.height ?? 36) / 2

        const edgeColor = getEdgeColor(edge.type)
        const markerType =
          edge.type === "data_flow"
            ? "data"
            : edge.type === "control_flow"
              ? "control"
              : edge.type
        const markerId = `arrow-${markerType === "true" || markerType === "false" || markerType === "data" || markerType === "control" || markerType === "call" ? markerType : "default"}`

        const isControlEdge = edge.type === "control" || edge.type === "control_flow"
        const isDataEdge = edge.type === "data" || edge.type === "data_flow"
        const isDependencyEdge = isControlEdge || isDataEdge
        const overlayBend =
          graphType === "hpg" && isDependencyEdge ? (x2 >= x1 ? 1 : -1) * 36 : 0

        const midY = (y1 + y2) / 2
        const bend = (edgeBendById[edge.id] ?? 0) + overlayBend
        const midX = (x1 + x2) / 2
        const path = `M ${x1} ${y1} Q ${midX + bend} ${midY} ${x2} ${y2}`

        const strokeWidth = isDependencyEdge ? (graphType === "hpg" ? 2.6 : 2.4) : 2
        const strokeDasharray = isControlEdge ? "6,4" : undefined
        const opacity = graphType === "hpg" ? (isDependencyEdge ? 0.95 : 0.55) : 0.8

        return (
          <g key={edge.id}>
            <path
              d={path}
              fill="none"
              stroke={edgeColor}
              strokeWidth={strokeWidth}
              strokeDasharray={strokeDasharray}
              markerEnd={`url(#${markerId})`}
              opacity={opacity}
            />
            {edge.label && (
              <text
                x={midX + bend * 0.6}
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

      {nodes.map((node) => {
        const colors = getNodeColor(node.type)
        const metrics = nodeMetrics[node.id]
        const nodeWidth = metrics?.width ?? 176
        const nodeHeight = metrics?.height ?? 36
        const rawLabel = metrics?.rawLabel || node.label || ""
        const labelLines = metrics?.lines || [rawLabel]
        const lineHeight = 14
        const startDy = -((labelLines.length - 1) * lineHeight) / 2
        const showLineNumber = Boolean(node.line) && !/\[L\d+\]/.test(rawLabel)
        const tooltip = (node.code || "").trim() || rawLabel

        return (
          <g
            key={node.id}
            transform={`translate(${node.x || 0}, ${node.y || 0})`}
            onMouseDown={(e) => handleMouseDown(e, node.id)}
            style={{ cursor: dragging === node.id ? "grabbing" : "grab" }}
          >
            <rect
              x={-nodeWidth / 2}
              y={-nodeHeight / 2}
              width={nodeWidth}
              height={nodeHeight}
              rx="6"
              fill={colors.bg}
              stroke={colors.border}
              strokeWidth="2"
            />
            <text
              textAnchor="middle"
              fontSize="11"
              fontWeight="500"
              fill={colors.text}
              pointerEvents="none"
              dominantBaseline="middle"
            >
              {labelLines.map((line, index) => (
                <tspan key={`${node.id}-line-${index}`} x="0" dy={index === 0 ? startDy : lineHeight}>
                  {line}
                </tspan>
              ))}
            </text>
            {showLineNumber && (
              <text
                textAnchor="middle"
                y={nodeHeight / 2 - 6}
                fontSize="8"
                fill={colors.text}
                opacity="0.6"
                pointerEvents="none"
              >
                L{node.line}
              </text>
            )}
            <title>{tooltip}</title>
          </g>
        )
      })}

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

// Agents Flow Graph
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
        className="w-full max-w-[560px] h-auto center-panel-svg"
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

        <path d="M 140 60 L 300 60" fill="none" stroke={readerNeedsContext ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={readerNeedsContext ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />
        <text x="220" y="50" textAnchor="middle" className="text-[10px] font-medium" fill={readerNeedsContext ? "#059669" : "#9ca3af"}>Need Context</text>

        <path d="M 400 80 Q 445 115, 400 155" fill="none" stroke={searcherContextFound ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={searcherContextFound ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />
        <text x="475" y="95" textAnchor="middle" className="text-[10px] font-medium" fill={searcherContextFound ? "#059669" : "#9ca3af"}>
          <tspan x="475" dy="0">Context</tspan>
          <tspan x="475" dy="13">Found</tspan>
        </text>

        <path d="M 95 82 C 95 130, 240 105, 305 160" fill="none" stroke={readerContextNotNeeded ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={readerContextNotNeeded ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />
        <text x="155" y="125" textAnchor="middle" className="text-[10px] font-medium" fill={readerContextNotNeeded ? "#059669" : "#9ca3af"}>
          <tspan x="155" dy="0">Context</tspan>
          <tspan x="155" dy="13">Not Needed</tspan>
        </text>

        <path d="M 355 195 L 355 220" fill="none" stroke={isConnectionHighlighted("writer", "verifier") ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={isConnectionHighlighted("writer", "verifier") ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />

        <path d="M 400 230 Q 455 195, 400 165" fill="none" stroke={verifierToWriterLoop ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={verifierToWriterLoop ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />
        <text x="478" y="195" textAnchor="middle" className="text-[10px] font-medium" fill={verifierToWriterLoop ? "#059669" : "#9ca3af"}>
          <tspan x="478" dy="0">Needs</tspan>
          <tspan x="478" dy="13">Revision</tspan>
        </text>

        <path d="M 305 255 C 170 290, 50 215, 50 120 C 50 75, 70 60, 95 60" fill="none" stroke={verifierToReaderLoop ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={verifierToReaderLoop ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />

        <path d="M 355 262 L 355 290" fill="none" stroke={verifierAccepted ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={verifierAccepted ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />
        <text x="400" y="280" textAnchor="middle" className="text-[10px] font-medium" fill={verifierAccepted ? "#059669" : "#9ca3af"}>Accepted</text>

        <path d="M 300 40 Q 220 15, 140 40" fill="none" stroke={searcherContextNotFound ? "#10b981" : "#d1d5db"} strokeWidth="2" markerEnd={searcherContextNotFound ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"} />

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