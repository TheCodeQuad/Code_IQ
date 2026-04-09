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

export default function CytoscapeGraph(props: CytoscapeGraphProps) {
  return <CytoscapeGraphClient {...props} />
}
