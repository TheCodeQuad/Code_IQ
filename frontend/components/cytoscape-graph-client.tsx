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

// Node colors based on type
const nodeColors: Record<string, { bg: string; border: string; text: string }> = {
  // Hierarchy types
  module: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" },
  class: { bg: "#f3e8ff", border: "#a855f7", text: "#6b21a8" },
  function: { bg: "#dbeafe", border: "#3b82f6", text: "#1e40af" },
  method: { bg: "#ccfbf1", border: "#14b8a6", text: "#0f766e" },
  statement: { bg: "#e0e7ff", border: "#6366f1", text: "#3730a3" },
  
  // CFG types
  entry: { bg: "#dcfce7", border: "#22c55e", text: "#166534" },
  exit: { bg: "#fee2e2", border: "#ef4444", text: "#991b1b" },
  branch: { bg: "#fef9c3", border: "#eab308", text: "#854d0e" },
  
  // Default
  default: { bg: "#f3f4f6", border: "#9ca3af", text: "#374151" },
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
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<any>(null)
  const [isReady, setIsReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Convert our graph data to Cytoscape elements
  const convertToElements = useCallback((data: GraphData): any[] => {
    const elements: any[] = []

    // Add nodes - DO NOT use backend positions, let force-directed layout compute positions
    data.nodes.forEach((node) => {
      const colors = nodeColors[node.type] || nodeColors.default
      elements.push({
        data: {
          id: node.id,
          label: node.label || node.id.split(":").pop() || node.id,
          type: node.type,
          line: node.line,
          code: node.code,
          ...node.metadata,
          // Store colors for styling
          bgColor: colors.bg,
          borderColor: colors.border,
          textColor: colors.text,
        },
        // IMPORTANT: Don't use backbone positions - let Cytoscape's force-directed layout compute them
        // position is intentionally undefined to enable physics-based layout
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

    const initCytoscape = async () => {
      try {
        // Dynamically import cytoscape only on client side
        const { default: cytoscape } = await import("cytoscape")

        // Import and register fcose layout (force-directed)
        try {
          const fcoseModule: any = await import("cytoscape-fcose")
          const fcose = fcoseModule.default ?? fcoseModule
          cytoscape.use(fcose)
        } catch (e) {
          console.error("fcose layout extension not available. Install 'cytoscape-fcose'.", e)
          setError("fcose layout not available. Please install 'cytoscape-fcose'.")
          return
        }

        const elements = convertToElements(graphData)

        // Destroy existing instance
        if (cyRef.current) {
          cyRef.current.destroy()
        }

        // Create new Cytoscape instance
        cyRef.current = cytoscape({
          container: containerRef.current,
          elements: elements,
          style: [
            // Node styling
            {
              selector: "node",
              style: {
                "background-color": "data(bgColor)",
                "border-color": "data(borderColor)",
                "border-width": 2,
                "label": "data(label)",
                "text-valign": "center",
                "text-halign": "center",
                "font-size": "10px",
                "color": "data(textColor)",
                "text-wrap": "ellipsis",
                "text-max-width": "80px",
                "width": "mapData(type, module, statement, 60, 30)",
                "height": "mapData(type, module, statement, 60, 30)",
                "shape": "roundrectangle",
                "text-outline-color": "#fff",
                "text-outline-width": 1,
              },
            },
            // Module nodes - larger hexagons
            {
              selector: "node[type='module']",
              style: {
                "shape": "hexagon",
                "width": 70,
                "height": 70,
                "font-size": "11px",
                "font-weight": "bold",
              },
            },
            // Class nodes - rectangles
            {
              selector: "node[type='class']",
              style: {
                "shape": "rectangle",
                "width": 60,
                "height": 40,
                "font-size": "10px",
                "font-weight": "bold",
              },
            },
            // Function nodes - ellipses
            {
              selector: "node[type='function'], node[type='method']",
              style: {
                "shape": "ellipse",
                "width": 50,
                "height": 35,
                "font-size": "9px",
              },
            },
            // Statement nodes - small circles
            {
              selector: "node[type='statement']",
              style: {
                "shape": "ellipse",
                "width": 25,
                "height": 25,
                "font-size": "7px",
                "text-max-width": "40px",
              },
            },
            // Edge styling
            {
              selector: "edge",
              style: {
                "width": 1.5,
                "line-color": "data(edgeColor)",
                "target-arrow-color": "data(edgeColor)",
                "target-arrow-shape": "triangle",
                "curve-style": "straight",
                "arrow-scale": 0.8,
                "opacity": 0.6,
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
                "opacity": 0.3,
                "width": 1,
              },
            },
            // Call edges - solid, more prominent
            {
              selector: "edge[type='calls']",
              style: {
                "width": 2.5,
                "opacity": 0.8,
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
                "width": 1.5,
                "line-style": "solid",
                "opacity": 0.6,
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
          layout: {
            // Use only fcose (force-directed) for layout
            name: "fcose",
            // Physics simulation
            animate: true,
            animationDuration: 2000,
            animationEasing: "ease-out",
            animationDelay: 0,
            // Layout parameters for organic network appearance
            fit: true,
            padding: 80,
            nodeDimensionsIncludeLabels: true,
            
            // Force parameters - aggressive physics for NetworkX-style spreading
            idealEdgeLength: 150,
            nodeRepulsion: 15000,        // Very high = maximum spreading
            edgeElasticity: 0.4,         // Lower = looser springs
            nestingFactor: 0.05,         // Low = minimal hierarchy bias
            gravity: 0.2,                // Low gravity = nodes spread freely
            numIter: 5000,               // Many iterations for convergence
            
            // Layout quality and performance
            tile: true,                  // Enable tiling for large graphs
            tilingPaddingVertical: 50,
            tilingPaddingHorizontal: 50,
            quality: "proof",            // Higher quality
            randomize: true,
          } as any,
          minZoom: 0.1,
          maxZoom: 3,
          wheelSensitivity: 0.3,
          boxSelectionEnabled: true,
          selectionType: "single",
        })

        // Event handlers
        cyRef.current.on("tap", "node", (evt: any) => {
          const node = evt.target
          if (onNodeClick) {
            onNodeClick(node.id(), node.data())
          }
        })

        // Double-click to zoom to node
        cyRef.current.on("dbltap", "node", (evt: any) => {
          const node = evt.target
          cyRef.current?.animate({
            center: { eles: node },
            zoom: 1.5,
          }, {
            duration: 300,
          })
        })

        // Hover effect
        cyRef.current.on("mouseover", "node", (evt: any) => {
          const node = evt.target
          node.style({
            "border-width": 3,
            "z-index": 999,
          })
          if (containerRef.current) {
            containerRef.current.style.cursor = "pointer"
          }
        })

        cyRef.current.on("mouseout", "node", (evt: any) => {
          const node = evt.target
          node.style({
            "border-width": 2,
            "z-index": 1,
          })
          if (containerRef.current) {
            containerRef.current.style.cursor = "default"
          }
        })

        // Ensure nodes are draggable/interactive
        cyRef.current.nodes().grabify()

        setIsReady(true)
      } catch (error) {
        console.error("Failed to initialize Cytoscape:", error)
        setError("Failed to load graph visualization. Check browser console for details.")
      }
    }

    initCytoscape()

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy()
        cyRef.current = null
      }
    }
  }, [graphData, convertToElements, onNodeClick])

  // Control functions
  const zoomIn = useCallback(() => {
    if (cyRef.current) {
      cyRef.current.zoom(cyRef.current.zoom() * 1.2)
    }
  }, [])

  const zoomOut = useCallback(() => {
    if (cyRef.current) {
      cyRef.current.zoom(cyRef.current.zoom() / 1.2)
    }
  }, [])

  const fitGraph = useCallback(() => {
    if (cyRef.current) {
      cyRef.current.fit(undefined, 50)
    }
  }, [])

  const exportPng = useCallback(() => {
    if (cyRef.current) {
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
  }, [graphData?.name])

  return (
    <div className={`relative w-full h-full ${className}`}>
      {/* Graph container */}
      <div 
        ref={containerRef} 
        className="w-full h-full bg-stone-50 rounded-lg"
        style={{ minHeight: "400px" }}
      />
      
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-red-50/80 rounded-lg">
          <div className="text-center">
            <p className="text-sm text-red-600">{error}</p>
            <p className="text-xs text-red-500 mt-2">Ensure cytoscape packages are installed: npm install cytoscape cytoscape-fcose</p>
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
            onClick={fitGraph}
            className="p-1.5 hover:bg-stone-100 rounded text-stone-600"
            title="Fit to View"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
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
        <div className="absolute bottom-3 left-3 bg-white/90 rounded-lg shadow-md p-2 text-xs">
          <div className="font-semibold mb-1 text-stone-700">Node Types</div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded" style={{ background: nodeColors.module.bg, border: `1px solid ${nodeColors.module.border}` }} />
              <span>Module</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded" style={{ background: nodeColors.class.bg, border: `1px solid ${nodeColors.class.border}` }} />
              <span>Class</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded" style={{ background: nodeColors.function.bg, border: `1px solid ${nodeColors.function.border}` }} />
              <span>Function</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded" style={{ background: nodeColors.method.bg, border: `1px solid ${nodeColors.method.border}` }} />
              <span>Method</span>
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
