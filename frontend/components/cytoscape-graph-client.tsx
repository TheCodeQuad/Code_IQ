"use client"

import { useEffect, useRef, useCallback, useState } from "react"

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
  metadata?: Record<string, any>
}

interface CytoscapeGraphClientProps {
  graphData: GraphData
  onNodeClick?: (nodeId: string, nodeData: any) => void
  className?: string
}

function getReadableNodeLabel(node: GraphNode): string {
  const rawName = (node as any)?.name
  const metaName = node.metadata?.name
  const explicitLabel = node.label
  const rawId = (node.id || "").split(":").pop() || node.id || ""
  const isStatementLike =
    node.type === "statement" ||
    /^(stmt|statement)_/i.test(rawId) ||
    (typeof explicitLabel === "string" && /^(stmt|statement)_/i.test(explicitLabel.trim()))

  const preferred = [rawName, metaName, explicitLabel]
    .map((v) => (typeof v === "string" ? v.trim() : ""))
    .find((v) => v.length > 0)

  if (isStatementLike) {
    if (preferred) {
      return preferred.length > 14 ? `${preferred.slice(0, 14)}...` : preferred
    }
    const stmtId = rawId.replace(/^(stmt|statement)_/i, "")
    return stmtId ? `stmt ${stmtId.slice(0, 8)}` : "stmt"
  }

  const cleanGeneratedPrefix = (value: string) =>
    value.replace(/^(func|function|class|method|module|node)_\d+_?/i, "").trim()

  const compactSymbol = (value: string) => {
    const tail = value.split(/[.:/\\]/).pop() || value
    const noPrefix = cleanGeneratedPrefix(tail)
    const noNumericLead = noPrefix.replace(/^\d+[_-]*/, "").trim()
    return (noNumericLead || noPrefix || tail).trim()
  }

  const isMeaningful = (value: string) => {
    const v = value.trim()
    return v.length > 0 && !/^\d+$/.test(v) && !/^(func|function|method)_?\d*$/i.test(v)
  }

  if (preferred) {
    const cleanedPreferred = compactSymbol(preferred)
    if (node.type === "function" || node.type === "method") {
      if (isMeaningful(cleanedPreferred)) return cleanedPreferred
      const byId = compactSymbol(rawId)
      return isMeaningful(byId) ? byId : (node.type === "method" ? "method" : "function")
    }
    return cleanedPreferred || preferred
  }

  const cleanedId = compactSymbol(rawId)
  if (node.type === "function" || node.type === "method") {
    return isMeaningful(cleanedId) ? cleanedId : (node.type === "method" ? "method" : "function")
  }
  return cleanedId || rawId
}

// Solid node colors based on type
const nodeColors: Record<string, { bg: string; border: string; text: string }> = {
  // Hierarchy types
  module: { bg: "#2563eb", border: "#1d4ed8", text: "#ffffff" },
  class: { bg: "#7c3aed", border: "#6d28d9", text: "#ffffff" },
  function: { bg: "#0ea5e9", border: "#0284c7", text: "#ffffff" },
  method: { bg: "#14b8a6", border: "#0f766e", text: "#ffffff" },
  statement: { bg: "#f97316", border: "#ea580c", text: "#ffffff" },
  
  // CFG types
  entry: { bg: "#16a34a", border: "#15803d", text: "#ffffff" },
  exit: { bg: "#dc2626", border: "#b91c1c", text: "#ffffff" },
  branch: { bg: "#d97706", border: "#b45309", text: "#ffffff" },
  
  // Default
  default: { bg: "#334155", border: "#1e293b", text: "#ffffff" },
}

// Edge colors based on type
const edgeColors: Record<string, string> = {
  hierarchy: "#94a3b8",
  calls: "#ec4899",
  imports: "#6366f1",
  extends: "#8b5cf6",
  control_flow: "#f59e0b",
  data_flow: "#3b82f6",
  default: "#9ca3af",
}

export default function CytoscapeGraphClient({ 
  graphData, 
  onNodeClick, 
  className = "" 
}: CytoscapeGraphClientProps) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<any>(null)
  const [isReady, setIsReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)

  const isCyAlive = useCallback(() => {
    return Boolean(cyRef.current) && !cyRef.current.destroyed()
  }, [])

  // Convert our graph data to Cytoscape elements
  const convertToElements = useCallback((data: GraphData): any[] => {
    const elements: any[] = []

    // Add all nodes for full detail.
    data.nodes.forEach((node) => {
      const colors = nodeColors[node.type] || nodeColors.default
      const displayLabel = getReadableNodeLabel(node)
      elements.push({
        data: {
          ...node.metadata,
          id: node.id,
          label: node.label || "",
          name: (node as any)?.name || node.metadata?.name || "",
          displayLabel,
          type: node.type,
          line: node.line,
          code: node.code,
          // Store colors for styling
          bgColor: colors.bg,
          borderColor: colors.border,
          textColor: colors.text,
        },
        // position intentionally undefined so Cytoscape layout computes it
      })
    })

    // Add edges
    data.edges.forEach((edge, index) => {
      const edgeColor = edgeColors[edge.type] || edgeColors.default
      elements.push({
        data: {
          id: edge.id || `edge-${index}`,
          source: edge.source,
          target: edge.target,
          type: edge.type,
          label: edge.label || "",
          edgeColor: edgeColor,
          ...edge.metadata,
        },
      })
    })

    return elements
  }, [])

  // Initialize Cytoscape
  useEffect(() => {
    if (!containerRef.current || !graphData?.nodes?.length) return

    let disposed = false

    const initCytoscape = async () => {
      try {
        // Dynamically import cytoscape only on client side
        const { default: cytoscape } = await import("cytoscape")

        if (disposed || !containerRef.current) {
          return
        }

        const elements = convertToElements(graphData)
        const layoutConfig = graphData.type === "dag"
          ? {
              name: "breadthfirst",
              directed: true,
              fit: true,
              padding: 26,
              spacingFactor: 0.9,
              animate: true,
              animationDuration: 600,
            }
          : {
              name: "cose",
              fit: true,
              padding: 22,
              nodeDimensionsIncludeLabels: true,
              randomize: true,
              animate: true,
              animationDuration: 700,
            }

        // Destroy existing instance
        if (cyRef.current && !cyRef.current.destroyed()) {
          cyRef.current.destroy()
          cyRef.current = null
        }

        // Create new Cytoscape instance
        const cy = cytoscape({
          container: containerRef.current,
          elements: elements,
          style: [
            // Node styling
            {
              selector: "node",
              style: {
                "background-color": "data(bgColor)",
                "border-color": "data(borderColor)",
                "border-width": 2.5,
                "label": "data(displayLabel)",
                "text-valign": "center",
                "text-halign": "center",
                "font-size": "10px",
                "color": "data(textColor)",
                "text-wrap": "wrap",
                "text-max-width": "110px",
                "width": 56,
                "height": 56,
                "shape": "roundrectangle",
                "text-outline-color": "#0f172a",
                "text-outline-width": 0.6,
              },
            },
            // Module nodes - larger hexagons
            {
              selector: "node[type='module']",
              style: {
                "shape": "hexagon",
                "width": 86,
                "height": 86,
                "font-size": "12px",
                "font-weight": "bold",
              },
            },
            // Class nodes - rectangles
            {
              selector: "node[type='class']",
              style: {
                "shape": "rectangle",
                "width": 74,
                "height": 54,
                "font-size": "11px",
                "font-weight": "bold",
              },
            },
            // Function nodes - ellipses
            {
              selector: "node[type='function'], node[type='method']",
              style: {
                "shape": "ellipse",
                "width": 66,
                "height": 46,
                "font-size": "10px",
              },
            },
            // Statement nodes - small circles
            {
              selector: "node[type='statement']",
              style: {
                "shape": "ellipse",
                "width": 30,
                "height": 30,
                "font-size": "7px",
                "text-max-width": "56px",
                "opacity": 0.95,
                "border-width": 1.5,
                "text-opacity": 1,
              },
            },
            {
              selector: "node[id ^= 'stmt_'], node[id ^= 'statement_']",
              style: {
                "opacity": 0.95,
                "text-opacity": 1,
                "width": 26,
                "height": 26,
                "border-width": 1.5,
              },
            },
            // Edge styling
            {
              selector: "edge",
              style: {
                "width": 2,
                "line-color": "data(edgeColor)",
                "target-arrow-color": "data(edgeColor)",
                "target-arrow-shape": "triangle",
                "curve-style": "bezier",
                "arrow-scale": 1,
                "opacity": 0.75,
                "text-background-color": "#fff",
                "text-background-opacity": 0.9,
                "text-background-padding": "2px",
              },
            },
            // Hierarchy edges - dashed, low opacity
            {
              selector: "edge[type='hierarchy']",
              style: {
                "line-style": "dashed",
                "opacity": 0.45,
                "width": 1,
              },
            },
            // Call edges - solid, more prominent
            {
              selector: "edge[type='calls']",
              style: {
                "width": 2.5,
                "opacity": 0.9,
                "line-style": "solid",
              },
            },
            // Data flow edges - blue dotted with label
            {
              selector: "edge[type='data_flow']",
              style: {
                "width": 2,
                "line-style": "dotted",
                "label": "data(label)",
                "font-size": "8px",
                "text-rotation": "autorotate",
                "text-margin-y": -8,
                "opacity": 0.7,
              },
            },
            // Control flow edges
            {
              selector: "edge[type='control_flow']",
              style: {
                "width": 1.8,
                "line-style": "solid",
                "opacity": 0.75,
              },
            },
            {
              selector: "edge[source ^= 'stmt_'], edge[target ^= 'stmt_'], edge[source ^= 'statement_'], edge[target ^= 'statement_']",
              style: {
                "opacity": 0.6,
                "width": 1.4,
                "target-arrow-shape": "triangle",
              },
            },
            // Hover states
            {
              selector: "node:active",
              style: {
                "overlay-color": "#3b82f6",
                "overlay-padding": 8,
                "overlay-opacity": 0.2,
              },
            },
            // Selected state
            {
              selector: "node:selected",
              style: {
                "border-width": 4,
                "border-color": "#2563eb",
              },
            },
          ],
          layout: layoutConfig as any,
          minZoom: 0.1,
          maxZoom: 3,
          wheelSensitivity: 0.3,
          boxSelectionEnabled: true,
          selectionType: "single",
        })

        if (disposed) {
          cy.destroy()
          return
        }

        cyRef.current = cy

        // Event handlers
        cy.on("tap", "node", (evt: any) => {
          if (!isCyAlive()) return
          const node = evt.target
          if (onNodeClick) {
            onNodeClick(node.id(), node.data())
          }
        })

        // Double-click to zoom to node
        cy.on("dbltap", "node", (evt: any) => {
          if (!isCyAlive()) return
          const node = evt.target
          cy.animate({
            center: { eles: node },
            zoom: 1.5,
          }, {
            duration: 300,
          })
        })

        // Hover effect
        cy.on("mouseover", "node", () => {
          if (!isCyAlive()) return
          if (containerRef.current) {
            containerRef.current.style.cursor = "pointer"
          }
        })

        cy.on("mouseout", "node", () => {
          if (!isCyAlive()) return
          if (containerRef.current) {
            containerRef.current.style.cursor = "default"
          }
        })

        // Ensure nodes are draggable/interactive
        cy.nodes().grabify()

        setIsReady(true)
      } catch (error) {
        console.error("Failed to initialize Cytoscape:", error)
        setError("Failed to load graph visualization. Check browser console for details.")
      }
    }

    initCytoscape()

    return () => {
      disposed = true
      if (containerRef.current) {
        containerRef.current.style.cursor = "default"
      }
      if (cyRef.current && !cyRef.current.destroyed()) {
        cyRef.current.destroy()
      }
      cyRef.current = null
    }
  }, [graphData, convertToElements, onNodeClick, isCyAlive])

  // Control functions
  const zoomIn = useCallback(() => {
    if (isCyAlive()) {
      cyRef.current.zoom(cyRef.current.zoom() * 1.2)
    }
  }, [isCyAlive])

  const zoomOut = useCallback(() => {
    if (isCyAlive()) {
      cyRef.current.zoom(cyRef.current.zoom() / 1.2)
    }
  }, [isCyAlive])

  const toggleFullscreen = useCallback(async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen()
        return
      }

      if (wrapperRef.current) {
        await wrapperRef.current.requestFullscreen()
      }
    } catch (fsError) {
      console.error("Failed to toggle fullscreen:", fsError)
    }
  }, [])

  useEffect(() => {
    const onFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement))
      if (isCyAlive()) {
        // Refit graph after fullscreen transition.
        setTimeout(() => {
          if (isCyAlive()) {
            cyRef.current.resize()
            cyRef.current.fit(undefined, 50)
          }
        }, 120)
      }
    }

    document.addEventListener("fullscreenchange", onFullscreenChange)
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange)
  }, [isCyAlive])

  const exportPng = useCallback(() => {
    if (isCyAlive()) {
      const png = cyRef.current.png({
        output: "blob",
        bg: "#ffffff",
        full: true,
        scale: 2,
      })
      const link = document.createElement("a")
      link.href = URL.createObjectURL(png as Blob)
      link.download = `${graphData.name || "graph"}.png`
      link.click()
    }
  }, [graphData?.name, isCyAlive])

  return (
    <div ref={wrapperRef} className={`relative w-full h-full ${className} ${isFullscreen ? "bg-white" : ""}`}>
      {/* Graph container */}
      <div 
        ref={containerRef} 
        className="w-full h-full bg-stone-50 rounded-lg"
        style={{ minHeight: isFullscreen ? "100vh" : "400px" }}
      />
      
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-red-50/80 rounded-lg">
          <div className="text-center">
            <p className="text-sm text-red-600">{error}</p>
            <p className="text-xs text-red-500 mt-2">Ensure Cytoscape is installed: npm install cytoscape</p>
          </div>
        </div>
      )}
      
      {/* Control buttons - only show if ready */}
      {isReady && !error && (
        <div className="absolute top-3 right-3 flex flex-col gap-1 bg-white/90 rounded-lg shadow-md p-1">
          <button
            onClick={zoomIn}
            className="p-1.5 hover:bg-stone-100 rounded text-stone-600"
            title="Zoom In"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
            </svg>
          </button>
          <button
            onClick={zoomOut}
            className="p-1.5 hover:bg-stone-100 rounded text-stone-600"
            title="Zoom Out"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7" />
            </svg>
          </button>
          <button
            onClick={() => void toggleFullscreen()}
            className="p-1.5 hover:bg-stone-100 rounded text-stone-600"
            title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {isFullscreen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 9V5m0 0H5m4 0L4 10m11-5h4m0 0v4m0-4l-5 5M9 15v4m0 0H5m4 0l-5-5m11 5h4m0 0v-4m0 4l-5-5" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              )}
            </svg>
          </button>
          <div className="border-t border-stone-200 my-1" />
          
          <button
            onClick={exportPng}
            className="p-1.5 hover:bg-stone-100 rounded text-stone-600"
            title="Export as PNG"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
        </div>
      )}

      {/* Legend */}
      {isReady && !error && (
        <div className="absolute top-3 left-3 z-20 bg-white/95 rounded-2xl shadow-xl border-2 border-stone-300 px-5 py-4 text-base min-w-56">
          <div className="font-extrabold mb-4 text-stone-900 tracking-wide">Node Types</div>
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded-sm" style={{ background: nodeColors.module.bg, border: `2px solid ${nodeColors.module.border}` }} />
              <span>Module</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded-sm" style={{ background: nodeColors.class.bg, border: `2px solid ${nodeColors.class.border}` }} />
              <span>Class</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded-sm" style={{ background: nodeColors.function.bg, border: `2px solid ${nodeColors.function.border}` }} />
              <span>Function</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded-sm" style={{ background: nodeColors.method.bg, border: `2px solid ${nodeColors.method.border}` }} />
              <span>Method</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded-sm" style={{ background: nodeColors.statement.bg, border: `2px solid ${nodeColors.statement.border}` }} />
              <span>Statement</span>
            </div>
          </div>
        </div>
      )}

      {/* Stats overlay */}
      {isReady && !error && (
        <div className="absolute top-3 left-3 bg-white/90 rounded-lg shadow-md px-2 py-1 text-xs text-stone-600">
          <span className="font-medium">{graphData.node_count}</span> nodes · 
          <span className="font-medium ml-1">{graphData.edge_count}</span> edges
        </div>
      )}
    </div>
  )
}
