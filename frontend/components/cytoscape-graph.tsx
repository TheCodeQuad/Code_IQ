"use client"

import dynamic from "next/dynamic"
import { Loader } from "lucide-react"

// GraphData interface for type safety
interface GraphData {
  id: string
  name: string
  type: string
  nodes: any[]
  edges: any[]
  node_count: number
  edge_count: number
  metadata?: Record<string, any>
}

interface CytoscapeGraphProps {
  graphData: GraphData
  onNodeClick?: (nodeId: string, nodeData: any) => void
  className?: string
}

import React, { forwardRef, useImperativeHandle, useRef } from "react"

// Dynamically import the client component with SSR disabled
const CytoscapeGraphClient = dynamic(
  () => import("./cytoscape-graph-client").then((mod) => ({ default: mod.default })),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex items-center justify-center bg-stone-50 rounded-lg">
        <div className="flex flex-col items-center gap-2">
          <Loader className="w-6 h-6 animate-spin text-amber-500" />
          <p className="text-sm text-stone-500">Loading interactive graph...</p>
        </div>
      </div>
    ),
  }
)

export interface CytoscapeRef {
  exportImage: () => void
  getPNG: () => Promise<Blob | null>
  zoomIn: () => void
  zoomOut: () => void
  toggleFullscreen: () => void
}

const CytoscapeGraph = forwardRef<CytoscapeRef, CytoscapeGraphProps>((props, ref) => {
  const clientRef = useRef<any>(null)
  
  useImperativeHandle(ref, () => ({
    exportImage: () => clientRef.current?.exportImage(),
    getPNG: () => clientRef.current?.getPNG(),
    zoomIn: () => clientRef.current?.zoomIn(),
    zoomOut: () => clientRef.current?.zoomOut(),
    toggleFullscreen: () => clientRef.current?.toggleFullscreen(),
  }))

  return <CytoscapeGraphClient {...props} ref={clientRef} />
})

CytoscapeGraph.displayName = "CytoscapeGraph"

export default CytoscapeGraph
