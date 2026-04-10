'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Play,
  CheckCircle2,
  Loader2,
  Circle,
  Network,
  Brain,
  Search,
  FileText,
  CheckCheck,
  RefreshCw,
  Save,
  ChevronDown,
  ChevronRight,
  Braces,
  Box,
  GitBranch,
} from 'lucide-react'
import {
  createInitialPipelineState,
  createAgenticIteration,
  type PipelineState,
  type PipelineStep,
  type AgenticIteration,
  type StepStatus,
  type ComponentType,
} from './pipeline-data'

// Status icon component
function StatusIcon({ status, size = 'sm' }: { status: StepStatus; size?: 'sm' | 'md' | 'lg' }) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6',
  }

  switch (status) {
    case 'completed':
      return <CheckCircle2 className={`${sizeClasses[size]} text-emerald-600`} />
    case 'running':
      return <Loader2 className={`${sizeClasses[size]} text-emerald-600 animate-spin`} />
    case 'error':
      return <Circle className={`${sizeClasses[size]} text-red-500`} />
    case 'skipped':
      return <Circle className={`${sizeClasses[size]} text-gray-300`} />
    default:
      return <Circle className={`${sizeClasses[size]} text-amber-500`} />
  }
}

// Component type icon
function ComponentTypeIcon({ type }: { type: ComponentType }) {
  switch (type) {
    case 'function':
      return <Braces className="w-3.5 h-3.5" />
    case 'class':
      return <Box className="w-3.5 h-3.5" />
    case 'method':
      return <GitBranch className="w-3.5 h-3.5" />
  }
}

// Horizontal Step item for Navigator and Finalization modules
function HorizontalStepItem({ step, isLast }: { step: PipelineStep; isLast: boolean }) {
  return (
    <div className="flex items-center">
      <div className="flex flex-col items-center">
        <div
          className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300 ${
            step.status === 'completed'
              ? 'bg-emerald-100 border-2 border-emerald-500'
              : step.status === 'running'
                ? 'bg-emerald-50 border-2 border-emerald-500'
                : 'bg-gray-50 border-2 border-gray-200'
          }`}
        >
          <StatusIcon status={step.status} />
        </div>
        <div className="mt-2 text-center max-w-22.5">
          <span className={`font-medium text-xs block ${step.status === 'running' ? 'text-emerald-700' : step.status === 'completed' ? 'text-emerald-700' : 'text-gray-700'}`}>
            {step.name}
          </span>
        </div>
      </div>
      {!isLast && (
        <div className={`w-12 h-0.5 mx-2 -mt-5 ${step.status === 'completed' ? 'bg-emerald-300' : 'bg-gray-200'}`} />
      )}
    </div>
  )
}

// Navigator Module Component
function NavigatorModuleCard({
  module,
  detectedTotal,
  isExpanded,
  onToggle,
}: {
  module: PipelineState['navigator']
  detectedTotal: number
  isExpanded: boolean
  onToggle: () => void
}) {
  const completedSteps = module.steps.filter((s) => s.status === 'completed').length
  const totalSteps = module.steps.length
  const shownTotal = module.extractedComponents.length > 0 ? module.extractedComponents.length : detectedTotal
  const shownFunctionCount = module.extractedComponents.length > 0 ? module.extractedComponents.filter(c => c.type === 'function').length : 0
  const shownClassCount = module.extractedComponents.length > 0 ? module.extractedComponents.filter(c => c.type === 'class').length : 0
  const shownMethodCount = module.extractedComponents.length > 0 ? module.extractedComponents.filter(c => c.type === 'method').length : 0

  return (
    <Card className="bg-white border-gray-200 shadow-sm overflow-hidden">
      <button onClick={onToggle} className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
        <div className="flex items-center gap-4">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 ${
              module.status === 'completed'
                ? 'bg-emerald-100 border border-emerald-300'
                : module.status === 'running'
                  ? 'bg-emerald-50 border border-emerald-300'
                  : 'bg-gray-100 border border-gray-200'
            }`}
          >
            <Network className={`w-6 h-6 ${module.status === 'completed' ? 'text-emerald-600' : module.status === 'running' ? 'text-emerald-600' : 'text-gray-400'}`} />
          </div>
          <div className="text-left">
            <h3 className="text-lg font-semibold text-gray-900">{module.name}</h3>
            <p className="text-sm text-gray-500">{module.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Badge variant="outline" className="text-xs text-gray-600 border-gray-300">
            {completedSteps}/{totalSteps} steps
          </Badge>
          {isExpanded ? <ChevronDown className="w-5 h-5 text-gray-400" /> : <ChevronRight className="w-5 h-5 text-gray-400" />}
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 pt-4 border-t border-gray-100">
          {/* Horizontal pipeline layout */}
          <div className="flex items-start justify-center gap-0 overflow-x-auto py-2">
            {module.steps.map((step, idx) => (
              <HorizontalStepItem key={step.id} step={step} isLast={idx === module.steps.length - 1} />
            ))}
          </div>
          
          {/* Show extracted components count after navigator completes */}
          {module.status === 'completed' && (
            <div className="mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
              <p className="text-sm text-emerald-800 font-medium">
                Extracted {shownTotal} components from repository
              </p>
              {module.extractedComponents.length > 0 ? (
                <p className="text-xs text-emerald-600 mt-1">
                  {shownFunctionCount} functions, {' '}
                  {shownClassCount} classes, {' '}
                  {shownMethodCount} methods
                </p>
              ) : (
                <p className="text-xs text-emerald-600 mt-1">Component type breakdown will appear as agentic processing starts.</p>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

// Notification badge for arrow conditions
function ConditionBadge({ 
  label, 
  isActive, 
  position 
}: { 
  label: string
  isActive: boolean
  position: { x: number; y: number }
}) {
  return (
    <div
      className={`absolute px-2 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-all duration-300 ${
        isActive 
          ? 'bg-emerald-100 text-emerald-700 border border-emerald-300 shadow-sm' 
          : 'bg-gray-100 text-gray-500 border border-gray-200'
      }`}
      style={{ left: position.x, top: position.y, transform: 'translate(-50%, -50%)' }}
    >
      {label}
    </div>
  )
}

// Color schemes for different agent types (before execution)
const agentColors: Record<string, { fill: string; stroke: string; text: string; icon: string }> = {
  reader: { fill: 'fill-blue-50', stroke: 'stroke-blue-400', text: 'text-blue-700', icon: 'text-blue-600' },
  searcher: { fill: 'fill-purple-50', stroke: 'stroke-purple-400', text: 'text-purple-700', icon: 'text-purple-600' },
  writer: { fill: 'fill-orange-50', stroke: 'stroke-orange-400', text: 'text-orange-700', icon: 'text-orange-600' },
  verifier: { fill: 'fill-cyan-50', stroke: 'stroke-cyan-400', text: 'text-cyan-700', icon: 'text-cyan-600' },
  insertion: { fill: 'fill-pink-50', stroke: 'stroke-pink-400', text: 'text-pink-700', icon: 'text-pink-600' },
}

// Agent node (ellipse shape)
function AgentNode({
  id,
  label,
  icon: Icon,
  status,
  x,
  y,
  isLarge = false,
}: {
  id: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  status: StepStatus
  x: number
  y: number
  isLarge?: boolean
}) {
  const isActive = status === 'running'
  const isCompleted = status === 'completed'
  const colors = agentColors[id] || agentColors.reader
  
  const rx = isLarge ? 80 : 52
  const ry = isLarge ? 26 : 20
  const foreignWidth = isLarge ? 156 : 100
  const foreignX = isLarge ? -78 : -50

  // Determine fill and stroke based on status
  const fillClass = isCompleted ? 'fill-emerald-50' : isActive ? 'fill-emerald-50' : colors.fill
  const strokeClass = isCompleted ? 'stroke-emerald-500' : isActive ? 'stroke-emerald-500' : colors.stroke
  const textClass = isCompleted ? 'text-emerald-700' : isActive ? 'text-emerald-700' : colors.text
  const iconClass = isCompleted ? 'text-emerald-600' : isActive ? 'text-emerald-600' : colors.icon

  return (
    <g transform={`translate(${x}, ${y})`}>
      {/* Ellipse shape */}
      <ellipse
        cx="0"
        cy="0"
        rx={rx}
        ry={ry}
        className={`transition-all duration-300 ${fillClass} ${strokeClass}`}
        strokeWidth="1.5"
      />
      {/* Pulse ring for active */}
      {isActive && (
        <ellipse
          cx="0"
          cy="0"
          rx={rx}
          ry={ry}
          className="fill-none stroke-emerald-400 animate-ping"
          strokeWidth="1"
          opacity="0.5"
        />
      )}
      {/* Icon and label */}
      <foreignObject x={foreignX} y="-14" width={foreignWidth} height="28">
        <div className="w-full h-full flex items-center justify-center gap-1.5">
          {isActive ? (
            <Loader2 className="w-4 h-4 text-emerald-600 animate-spin shrink-0" />
          ) : isCompleted ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          ) : (
            <Icon className={`w-4 h-4 ${iconClass} shrink-0`} />
          )}
          <span className={`text-[11px] font-semibold leading-none ${textClass}`}>
            {label}
          </span>
        </div>
      </foreignObject>
    </g>
  )
}

// SVG curved arrow with arrowhead
function CurvedArrow({
  path,
  isActive,
  isCompleted,
  markerId,
}: {
  path: string
  isActive: boolean
  isCompleted: boolean
  markerId: string
}) {
  return (
    <path
      d={path}
      fill="none"
      className={`transition-all duration-300 ${
        isCompleted 
          ? 'stroke-emerald-400' 
          : isActive 
            ? 'stroke-emerald-500' 
            : 'stroke-gray-300'
      }`}
      strokeWidth={isActive ? "2.5" : "2"}
      markerEnd={`url(#${markerId})`}
    />
  )
}

// Arrow label component with multiline support
function ArrowLabel({
  lines,
  x,
  y,
  isActive,
  isCompleted,
}: {
  lines: string[]
  x: number
  y: number
  isActive: boolean
  isCompleted: boolean
}) {
  const fillClass = isCompleted 
    ? 'fill-emerald-600' 
    : isActive 
      ? 'fill-emerald-700' 
      : 'fill-gray-400'
  
  return (
    <text
      x={x}
      y={y}
      textAnchor="middle"
      className={`text-[10px] font-medium transition-all duration-300 ${fillClass}`}
    >
      {lines.map((line, idx) => (
        <tspan key={idx} x={x} dy={idx === 0 ? 0 : 13}>
          {line}
        </tspan>
      ))}
    </text>
  )
}

// Graphical pipeline flow matching the hand-drawn diagram
function GraphicalPipelineFlow({ iteration }: { iteration: AgenticIteration }) {
  const steps = iteration.steps
  
  // Determine which paths are active based on current flow
  const readerActive = steps.reader.status === 'running'
  const readerCompleted = steps.reader.status === 'completed'
  const searcherActive = steps.searcher.status === 'running'
  const searcherCompleted = steps.searcher.status === 'completed'
  const writerActive = steps.writer.status === 'running'
  const writerCompleted = steps.writer.status === 'completed'
  const verifierActive = steps.verifier.status === 'running'
  const verifierCompleted = steps.verifier.status === 'completed'
  const insertionActive = steps.insertion.status === 'running'
  const insertionCompleted = steps.insertion.status === 'completed'

  // Check if we need context (went through searcher path)
  const needsContext = searcherActive || searcherCompleted
  const contextNotNeeded = !needsContext && (writerActive || writerCompleted)
  
  // Feedback states
  const feedbackToReader = Boolean(iteration.traversedToReader)
  const feedbackToWriter = Boolean(iteration.traversedToWriter)
  
  // Track if any retry is happening - arrows should stay orange during retry
  const isRetrying = feedbackToReader || feedbackToWriter

  // Searcher to Reader feedback (context not found)
  const contextNotFound = iteration.steps.searcher.logs.includes('context_not_found')
    || (iteration.verifierFeedback === 'rejected-to-reader' && searcherCompleted)
  const contextFound = iteration.steps.searcher.logs.includes('context_found')

  return (
    <div className="relative w-full flex items-center justify-center p-4">
      <svg 
        viewBox="0 0 520 350" 
        className="w-full max-w-140 h-auto"
        style={{ minHeight: '340px' }}
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Define arrowheads */}
        <defs>
          <marker
            id="arrowhead-gray"
            markerWidth="6"
            markerHeight="5"
            refX="5"
            refY="2.5"
            orient="auto"
          >
            <polygon points="0 0, 6 2.5, 0 5" fill="#d1d5db" />
          </marker>
          <marker
            id="arrowhead-emerald"
            markerWidth="6"
            markerHeight="5"
            refX="5"
            refY="2.5"
            orient="auto"
          >
            <polygon points="0 0, 6 2.5, 0 5" fill="#10b981" />
          </marker>
          <marker
            id="arrowhead-amber"
            markerWidth="6"
            markerHeight="5"
            refX="5"
            refY="2.5"
            orient="auto"
          >
            <polygon points="0 0, 6 2.5, 0 5" fill="#f59e0b" />
          </marker>
        </defs>

        {/* 1. Reader -> Searcher: "Need Context" - straight horizontal arrow */}
        <path
          d="M 140 60 L 300 60"
          fill="none"
          className={`transition-all duration-300 ${
            searcherCompleted 
              ? 'stroke-emerald-400' 
              : (readerCompleted && needsContext) 
                ? 'stroke-emerald-500' 
                : 'stroke-gray-300'
          }`}
          strokeWidth="2"
          markerEnd={(readerCompleted && needsContext) ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"}
        />
        <ArrowLabel 
          lines={["Need Context"]} 
          x={220} 
          y={50} 
          isActive={readerCompleted && needsContext} 
          isCompleted={searcherCompleted} 
        />

        {/* 4. Searcher -> Reader: "Context Not Found" - curved path above */}
        <path
          d="M 300 40 Q 220 15, 140 40"
          fill="none"
          className={`transition-all duration-300 ${
            contextNotFound 
              ? 'stroke-amber-500' 
              : 'stroke-gray-300'
          }`}
          strokeWidth="2"
          markerEnd={contextNotFound ? "url(#arrowhead-amber)" : "url(#arrowhead-gray)"}
        />
        <ArrowLabel 
          lines={["Context", "Not Found"]} 
          x={220} 
          y={8} 
          isActive={contextNotFound} 
          isCompleted={false} 
        />

        {/* 2. Searcher -> Writer: "Context Found" - right side curve */}
        <path
          d="M 400 80 Q 445 115, 400 155"
          fill="none"
          className={`transition-all duration-300 ${
            (writerCompleted && contextFound)
              ? 'stroke-emerald-400' 
              : contextFound
                ? 'stroke-emerald-500' 
                : 'stroke-gray-300'
          }`}
          strokeWidth="2"
          markerEnd={contextFound ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"}
        />
        <ArrowLabel 
          lines={["Context", "Found"]} 
          x={475} 
          y={95} 
          isActive={contextFound} 
          isCompleted={writerCompleted && contextFound} 
        />

        {/* 3. Reader -> Writer: "Context Not Needed" - nice S curve */}
        <path
          d="M 95 82 C 95 130, 240 105, 305 160"
          fill="none"
          className={`transition-all duration-300 ${
            (writerCompleted && contextNotNeeded) 
              ? 'stroke-emerald-400' 
              : (readerCompleted && contextNotNeeded) 
                ? 'stroke-emerald-500' 
                : 'stroke-gray-300'
          }`}
          strokeWidth="2"
          markerEnd={(readerCompleted && contextNotNeeded) ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"}
        />
        <ArrowLabel 
          lines={["Context", "Not Needed"]} 
          x={155} 
          y={125} 
          isActive={readerCompleted && contextNotNeeded} 
          isCompleted={writerCompleted && contextNotNeeded} 
        />

        {/* 5. Writer -> Verifier: "Docstring generated" - vertical arrow */}
        <path
          d="M 355 195 L 355 220"
          fill="none"
          className={`transition-all duration-300 ${
            isRetrying
              ? 'stroke-amber-500'
              : verifierCompleted 
                ? 'stroke-emerald-400' 
                : writerCompleted 
                  ? 'stroke-emerald-500' 
                  : 'stroke-gray-300'
          }`}
          strokeWidth="2"
          markerEnd={isRetrying ? "url(#arrowhead-amber)" : writerCompleted ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"}
        />
        <ArrowLabel 
          lines={["Docstring", "Generated"]} 
          x={295} 
          y={205} 
          isActive={writerCompleted || isRetrying} 
          isCompleted={verifierCompleted && !isRetrying} 
        />

        {/* 6. Verifier -> Writer: "Needs Revision" - right loop */}
        <path
          d="M 400 230 Q 455 195, 400 165"
          fill="none"
          className={`transition-all duration-300 ${
            feedbackToWriter 
              ? 'stroke-amber-500' 
              : 'stroke-gray-300'
          }`}
          strokeWidth="2"
          markerEnd={feedbackToWriter ? "url(#arrowhead-amber)" : "url(#arrowhead-gray)"}
        />
        <ArrowLabel 
          lines={["Needs", "Revision"]} 
          x={478} 
          y={195} 
          isActive={feedbackToWriter} 
          isCompleted={false} 
        />

        {/* 7. Verifier -> Reader: "Needs More Context" - single left curve */}
        <path
          d="M 305 255 C 170 290, 50 215, 50 120 C 50 75, 70 60, 95 60"
          fill="none"
          className={`transition-all duration-300 ${
            feedbackToReader 
              ? 'stroke-amber-500' 
              : 'stroke-gray-300'
          }`}
          strokeWidth="2"
          markerEnd={feedbackToReader ? "url(#arrowhead-amber)" : "url(#arrowhead-gray)"}
        />
        <ArrowLabel 
          lines={["Needs More", "Context"]} 
          x={100} 
          y={270} 
          isActive={feedbackToReader} 
          isCompleted={false} 
        />

        {/* 8. Verifier -> Docstring Inserted: "Accepted" - vertical arrow */}
        <path
          d="M 355 262 L 355 290"
          fill="none"
          className={`transition-all duration-300 ${
            isRetrying
              ? 'stroke-amber-500'
              : insertionCompleted 
                ? 'stroke-emerald-400' 
                : (verifierCompleted && !feedbackToReader && !feedbackToWriter) 
                  ? 'stroke-emerald-500' 
                  : 'stroke-gray-300'
          }`}
          strokeWidth="2"
          markerEnd={isRetrying ? "url(#arrowhead-amber)" : (verifierCompleted && !feedbackToReader && !feedbackToWriter) ? "url(#arrowhead-emerald)" : "url(#arrowhead-gray)"}
        />
        <ArrowLabel 
          lines={["Accepted"]} 
          x={400} 
          y={280} 
          isActive={(verifierCompleted && !feedbackToReader && !feedbackToWriter) || isRetrying} 
          isCompleted={insertionCompleted && !isRetrying} 
        />

        {/* Agent Nodes - Reader on left, others stacked on right - closer together */}
        <AgentNode id="reader" label="Reader" icon={Brain} status={steps.reader.status} x={95} y={60} />
        <AgentNode id="searcher" label="Searcher" icon={Search} status={steps.searcher.status} x={355} y={60} />
        <AgentNode id="writer" label="Writer" icon={FileText} status={steps.writer.status} x={355} y={170} />
        <AgentNode id="verifier" label="Verifier" icon={CheckCheck} status={steps.verifier.status} x={355} y={240} />
        <AgentNode id="insertion" label="Docstring Inserted" icon={Save} status={steps.insertion.status} x={355} y={315} isLarge />
      </svg>
    </div>
  )
}

// Component list item in sidebar
function ComponentListItem({
  iteration,
  isSelected,
  onSelect,
}: {
  iteration: AgenticIteration
  isSelected: boolean
  onSelect: () => void
}) {
  const isRunning = iteration.status === 'running'
  const isCompleted = iteration.status === 'completed'

  return (
    <button
      onClick={onSelect}
      className={`w-full text-left p-3 rounded-lg border transition-all duration-200 ${
        isSelected
          ? isCompleted
            ? 'bg-emerald-50 border-emerald-300 ring-1 ring-emerald-200'
            : isRunning
              ? 'bg-blue-50 border-blue-300 ring-1 ring-blue-200'
              : 'bg-white border-gray-300 ring-1 ring-gray-200'
          : isRunning
            ? 'bg-blue-50 border-blue-200'
            : isCompleted
              ? 'bg-emerald-50 border-emerald-200'
              : 'bg-white border-gray-200 hover:bg-gray-50'
      }`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`w-8 h-8 rounded-lg flex items-center justify-center ${
            isRunning
              ? 'bg-blue-100 text-blue-600'
              : isCompleted
                ? 'bg-emerald-100 text-emerald-600'
                : 'bg-amber-100 text-amber-600'
          }`}
        >
          <ComponentTypeIcon type={iteration.componentType} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-sm font-medium truncate ${isRunning ? 'text-blue-700' : isCompleted ? 'text-emerald-700' : 'text-gray-800'}`}>
              {iteration.parentClass ? `${iteration.parentClass}.` : ''}{iteration.componentName}
            </span>
            {isRunning && (
              <span className="shrink-0">
                <Loader2 className="w-3 h-3 text-blue-600 animate-spin" />
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 whitespace-normal break-all leading-relaxed mt-0.5">{iteration.filePath}</p>
        </div>
        <div className="shrink-0">
          {isCompleted ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
          ) : isRunning ? (
            <div className="w-5 h-5 rounded-full bg-blue-500 animate-pulse" />
          ) : (
            <Circle className="w-5 h-5 text-amber-400" />
          )}
        </div>
      </div>
      {iteration.retryCount > 0 && (
        <div className="mt-2 flex items-center gap-1 text-xs text-amber-600">
          <RefreshCw className="w-3 h-3" />
          <span>Retry {iteration.retryCount}</span>
        </div>
      )}
    </button>
  )
}

// Agentic Module Component with split layout
function AgenticModuleCard({
  module,
  isExpanded,
  onToggle,
  selectedComponent,
  onSelectComponent,
}: {
  module: PipelineState['agentic']
  isExpanded: boolean
  onToggle: () => void
  selectedComponent: string | null
  onSelectComponent: (id: string) => void
}) {
  const visibleIterations = module.iterations.filter(
    (i) =>
      !i.componentName.toLowerCase().startsWith('component-') &&
      !(i.componentName.toLowerCase() === 'unknown' && i.filePath.toLowerCase() === 'unknown')
  )
  const selectedIteration = visibleIterations.find((i) => i.componentId === selectedComponent)

  return (
    <Card className="bg-white border-gray-200 shadow-sm overflow-hidden">
      <button onClick={onToggle} className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
        <div className="flex items-center gap-4">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 ${
              module.status === 'completed'
                ? 'bg-emerald-100 border border-emerald-300'
                : module.status === 'running'
                  ? 'bg-emerald-50 border border-emerald-300'
                  : 'bg-gray-100 border border-gray-200'
            }`}
          >
            <Brain className={`w-6 h-6 ${module.status === 'completed' ? 'text-emerald-600' : module.status === 'running' ? 'text-emerald-600' : 'text-gray-400'}`} />
          </div>
          <div className="text-left">
            <h3 className="text-lg font-semibold text-gray-900">{module.name}</h3>
            <p className="text-sm text-gray-500">{module.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Badge variant="outline" className="text-xs text-gray-600 border-gray-300">
            {module.completedComponents}/{module.totalComponents} components
          </Badge>
          {module.status === 'running' && (
            <Badge className="bg-emerald-100 text-emerald-700 border-emerald-300">
              Processing #{module.currentIteration + 1}
            </Badge>
          )}
          {isExpanded ? <ChevronDown className="w-5 h-5 text-gray-400" /> : <ChevronRight className="w-5 h-5 text-gray-400" />}
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-gray-100">
          <div className="flex">
            {/* Left sidebar: Component list */}
            <div className="w-72 border-r border-gray-100 bg-gray-50/50">
              <div className="p-3 border-b border-gray-100">
                <h4 className="text-sm font-medium text-gray-700">Components ({visibleIterations.length})</h4>
                <p className="text-xs text-gray-500 mt-0.5">Click to view pipeline</p>
              </div>
              <ScrollArea className="h-120">
                <div className="p-2 space-y-2">
                  {visibleIterations.length === 0 ? (
                    <div className="h-full flex items-center justify-center py-16 text-gray-400">
                      <div className="text-center">
                        <Network className="w-10 h-10 mx-auto mb-2 opacity-40" />
                        <p className="text-sm font-medium">No components detected</p>
                        <p className="text-xs mt-1">Components will appear after Navigator module completes</p>
                      </div>
                    </div>
                  ) : (
                    visibleIterations.map((iteration) => (
                      <ComponentListItem
                        key={iteration.componentId}
                        iteration={iteration}
                        isSelected={selectedComponent === iteration.componentId}
                        onSelect={() => onSelectComponent(iteration.componentId)}
                      />
                    ))
                  )}
                </div>
              </ScrollArea>
            </div>

            {/* Right side: Graphical Pipeline visualization */}
            <div className="flex-1 p-6">
              {selectedIteration ? (
                <div className="flex flex-col h-105">
                  {/* Graphical pipeline flow */}
                  <div className="flex-1 border border-gray-200 rounded-lg bg-white">
                    <GraphicalPipelineFlow iteration={selectedIteration} />
                  </div>

                  {/* Status summary - neatly positioned under graph */}
                  {selectedIteration.status === 'completed' && (
                    <div className="mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                      <div className="flex items-center gap-2 text-emerald-700">
                        <CheckCircle2 className="w-4 h-4 shrink-0" />
                        <span className="text-sm font-medium">Docstring generated and inserted successfully</span>
                      </div>
                      {selectedIteration.retryCount > 0 && (
                        <p className="text-xs text-emerald-600 mt-1 ml-6">
                          Completed after {selectedIteration.retryCount} verification {selectedIteration.retryCount === 1 ? 'retry' : 'retries'}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="h-120 flex items-center justify-center text-gray-400">
                  <div className="text-center">
                    <Brain className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p className="text-sm">Select a component to view its pipeline</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}

// Finalization Module Component
function FinalizationModuleCard({ module, isExpanded, onToggle }: { module: PipelineState['finalization']; isExpanded: boolean; onToggle: () => void }) {
  const completedSteps = module.steps.filter((s) => s.status === 'completed').length
  const totalSteps = module.steps.length

  return (
    <Card className="bg-white border-gray-200 shadow-sm overflow-hidden">
      <button onClick={onToggle} className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
        <div className="flex items-center gap-4">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 ${
              module.status === 'completed'
                ? 'bg-emerald-100 border border-emerald-300'
                : module.status === 'running'
                  ? 'bg-emerald-50 border border-emerald-300'
                  : 'bg-gray-100 border border-gray-200'
            }`}
          >
            <Save className={`w-6 h-6 ${module.status === 'completed' ? 'text-emerald-600' : module.status === 'running' ? 'text-emerald-600' : 'text-gray-400'}`} />
          </div>
          <div className="text-left">
            <h3 className="text-lg font-semibold text-gray-900">{module.name}</h3>
            <p className="text-sm text-gray-500">{module.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Badge variant="outline" className="text-xs text-gray-600 border-gray-300">
            {completedSteps}/{totalSteps} steps
          </Badge>
          {isExpanded ? <ChevronDown className="w-5 h-5 text-gray-400" /> : <ChevronRight className="w-5 h-5 text-gray-400" />}
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 pt-4 border-t border-gray-100">
          {/* Horizontal pipeline layout */}
          <div className="flex items-start justify-center gap-0 overflow-x-auto py-2">
            {module.steps.map((step, idx) => (
              <HorizontalStepItem key={step.id} step={step} isLast={idx === module.steps.length - 1} />
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}

// Main Pipeline Visualization Component
type BackendPipelineEvent = {
  event_type?: string
  phase?: 'navigator' | 'agentic' | 'finalization'
  step_id?: string
  agent?: string
  status?: 'pending' | 'in_progress' | 'completed' | 'failed' | string
  progress_percent?: number
  message?: string
  component_id?: string
  component_name?: string
  component_type?: string
  file_path?: string
  component_count?: number
  components?: Array<{
    id: string
    name: string
    type: string
    file_path: string
  }>
  transition?: string
}

function toStepStatus(status?: string): StepStatus {
  if (status === 'completed') return 'completed'
  if (status === 'in_progress') return 'running'
  if (status === 'failed') return 'error'
  return 'pending'
}

function toComponentType(raw?: string): ComponentType {
  if (raw === 'class') return 'class'
  if (raw === 'method') return 'method'
  return 'function'
}

export function PipelineVisualization({ repoId, autoStart = false }: { repoId: string; autoStart?: boolean }) {
  const [pipelineState, setPipelineState] = useState<PipelineState>(createInitialPipelineState)
  const [isStarting, setIsStarting] = useState(false)
  const [streamState, setStreamState] = useState<'connecting' | 'live' | 'disconnected' | 'error'>('connecting')
  const [repoMeta, setRepoMeta] = useState<{ name?: string; fileCount?: number }>({})
  const [expandedModules, setExpandedModules] = useState<Record<string, boolean>>({
    navigator: true,
    agentic: true,
    finalization: true,
  })
  const [selectedComponent, setSelectedComponent] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const autoStartTriggeredRef = useRef(false)

  const resetPipelineViewState = useCallback(() => {
    setPipelineState(createInitialPipelineState())
    setSelectedComponent(null)
  }, [])

  const toggleModule = (module: string) => {
    setExpandedModules((prev) => ({ ...prev, [module]: !prev[module] }))
  }

  const applyBackendEvent = useCallback((evt: BackendPipelineEvent) => {
    if (evt.component_id) {
      setSelectedComponent((current) => current ?? evt.component_id ?? null)
    }

    setPipelineState((prev) => {
      const next = JSON.parse(JSON.stringify(prev)) as PipelineState

      if (evt.event_type === 'pipeline-completed') {
        next.navigator.status = 'completed'
        next.navigator.steps.forEach((s) => {
          s.status = 'completed'
          s.progress = 100
        })

        next.agentic.status = 'completed'
        next.agentic.iterations.forEach((iteration) => {
          iteration.status = 'completed'
          iteration.steps.reader.status = 'completed'
          iteration.steps.searcher.status = 'completed'
          iteration.steps.writer.status = 'completed'
          iteration.steps.verifier.status = 'completed'
          iteration.steps.insertion.status = 'completed'
          iteration.steps.reader.progress = 100
          iteration.steps.searcher.progress = 100
          iteration.steps.writer.progress = 100
          iteration.steps.verifier.progress = 100
          iteration.steps.insertion.progress = 100
        })
        next.agentic.completedComponents = next.agentic.iterations.length

        next.finalization.status = 'completed'
        next.finalization.steps.forEach((s) => {
          s.status = 'completed'
          s.progress = 100
        })
        return next
      }

      const stepStatus = toStepStatus(evt.status)
      const progress = stepStatus === 'completed' ? 100 : Math.max(10, evt.progress_percent ?? 0)

      if (evt.phase === 'navigator' && evt.step_id) {
        next.navigator.status = stepStatus === 'completed' && next.navigator.steps.every((s) => s.status === 'completed')
          ? 'completed'
          : 'running'

        const step = next.navigator.steps.find((s) => s.id === evt.step_id)
        if (step) {
          step.status = stepStatus
          step.progress = progress
          if (evt.message) step.logs = [...step.logs, evt.message]
        }

        if (typeof evt.component_count === 'number') {
          next.agentic.totalComponents = evt.component_count
        }

        if (Array.isArray(evt.components) && evt.components.length > 0) {
          evt.components.forEach((c) => {
            const extracted = {
              id: c.id,
              name: c.name,
              type: toComponentType(c.type),
              filePath: c.file_path || 'unknown',
            }

            if (!next.navigator.extractedComponents.some((item) => item.id === extracted.id)) {
              next.navigator.extractedComponents.push(extracted)
            }

            if (!next.agentic.iterations.some((it) => it.componentId === extracted.id)) {
              next.agentic.iterations.push(createAgenticIteration(extracted))
            }
          })
        }

        if (next.navigator.steps.every((s) => s.status === 'completed')) {
          next.navigator.status = 'completed'
        }
      }

      if (evt.phase === 'agentic' || evt.component_id) {
        next.agentic.status = next.agentic.status === 'completed' ? 'completed' : 'running'

        if (!evt.component_id) {
          return next
        }

        const componentId = evt.component_id
        let iteration = next.agentic.iterations.find((i) => i.componentId === componentId)

        if (!iteration) {
          const component = {
            id: componentId,
            name: evt.component_name ?? componentId,
            type: toComponentType(evt.component_type),
            filePath: evt.file_path ?? 'unknown',
          }
          iteration = createAgenticIteration(component)
          next.agentic.iterations.push(iteration)
          if (!next.navigator.extractedComponents.some((c) => c.id === component.id)) {
            next.navigator.extractedComponents.push(component)
          }
          if (!next.agentic.totalComponents || next.agentic.totalComponents < next.agentic.iterations.length) {
            next.agentic.totalComponents = next.agentic.iterations.length
          }
        }

        iteration.status = stepStatus === 'completed' && evt.step_id === 'insertion' ? 'completed' : 'running'

        const stepMap: Record<string, keyof AgenticIteration['steps']> = {
          reader: 'reader',
          searcher: 'searcher',
          writer: 'writer',
          verifier: 'verifier',
          insertion: 'insertion',
        }
        const stepKey = evt.step_id ? stepMap[evt.step_id] : undefined
        if (stepKey) {
          iteration.steps[stepKey].status = stepStatus
          iteration.steps[stepKey].progress = progress
          if (evt.message) {
            iteration.steps[stepKey].logs = [...iteration.steps[stepKey].logs, evt.message]
          }
        }

        if (evt.transition === 'reader_to_searcher') {
          iteration.steps.searcher.status = 'running'
        }
        if (evt.transition === 'searcher_to_reader_not_found') {
          iteration.steps.searcher.logs = [...iteration.steps.searcher.logs, 'context_not_found']
        }
        if (evt.transition === 'searcher_to_writer_found') {
          iteration.steps.searcher.logs = [...iteration.steps.searcher.logs, 'context_found']
        }
        if (evt.transition === 'verifier_to_reader_needs_context') {
          iteration.verifierFeedback = 'rejected-to-reader'
          iteration.retryCount += 1
          iteration.traversedToReader = true
          iteration.steps.readerWithContext.status = 'running'
        }
        if (evt.transition === 'verifier_to_writer_revision') {
          iteration.verifierFeedback = 'rejected-to-writer'
          iteration.retryCount += 1
          iteration.traversedToWriter = true
          iteration.steps.writerRefine.status = 'running'
        }
        if (evt.transition === 'verifier_to_inserted') {
          iteration.verifierFeedback = 'accepted'
        }
        if (evt.transition === 'inserted' || (evt.step_id === 'insertion' && stepStatus === 'completed')) {
          iteration.status = 'completed'
          iteration.steps.writer.status = 'completed'
          iteration.steps.verifier.status = 'completed'
          iteration.steps.insertion.status = 'completed'
          iteration.steps.writer.progress = 100
          iteration.steps.verifier.progress = 100
          iteration.steps.insertion.progress = 100
        }

        const completedComponents = next.agentic.iterations.filter((i) => i.status === 'completed').length
        next.agentic.completedComponents = completedComponents
        next.agentic.currentIteration = Math.min(completedComponents, Math.max(next.agentic.iterations.length - 1, 0))
        if (next.agentic.totalComponents > 0 && completedComponents >= next.agentic.totalComponents) {
          next.agentic.status = 'completed'
        }
      }

      if (evt.phase === 'finalization' && evt.step_id) {
        next.finalization.status = stepStatus === 'completed' && next.finalization.steps.every((s) => s.status === 'completed')
          ? 'completed'
          : 'running'
        const step = next.finalization.steps.find((s) => s.id === evt.step_id)
        if (step) {
          step.status = stepStatus
          step.progress = progress
          if (evt.message) step.logs = [...step.logs, evt.message]
        }
        if (next.finalization.steps.every((s) => s.status === 'completed')) {
          next.finalization.status = 'completed'
        }
      }

      return next
    })
  }, [])

  const connectEventStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    setStreamState('connecting')
    const source = new EventSource(`/api/repos/${repoId}/events`)
    eventSourceRef.current = source

    source.addEventListener('snapshot', (event) => {
      try {
        const data = JSON.parse((event as MessageEvent<string>).data) as BackendPipelineEvent
        applyBackendEvent(data)
      } catch {
        // Ignore malformed snapshot payloads.
      }
    })

    source.addEventListener('progress', (event) => {
      try {
        const data = JSON.parse((event as MessageEvent<string>).data) as BackendPipelineEvent
        applyBackendEvent(data)
      } catch {
        // Ignore malformed progress payloads.
      }
    })

    source.onopen = () => setStreamState('live')
    source.onerror = () => setStreamState('disconnected')
  }, [applyBackendEvent, repoId])

  const startPipeline = async () => {
    setIsStarting(true)
    try {
      resetPipelineViewState()
      const res = await fetch(`/api/repos/${repoId}/generate`, {
        method: 'POST',
      })
      if (!res.ok) {
        throw new Error(`Failed to start pipeline (HTTP ${res.status})`)
      }
      connectEventStream()
    } catch {
      setStreamState('error')
    } finally {
      setIsStarting(false)
    }
  }

  useEffect(() => {
    // Repo change must always start from a clean UI state.
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    autoStartTriggeredRef.current = false
    setRepoMeta({})
    setStreamState('connecting')
    resetPipelineViewState()
  }, [repoId, resetPipelineViewState])

  useEffect(() => {
    async function bootstrap() {
      try {
        const [repoRes, statusRes] = await Promise.all([
          fetch(`/api/repos/${repoId}`, { cache: 'no-store' }),
          fetch(`/api/repos/${repoId}/status`, { cache: 'no-store' }),
        ])

        if (repoRes.ok) {
          const repo = await repoRes.json()
          setRepoMeta({
            name: repo.repo_name,
            fileCount: repo.file_count,
          })
        }

        if (statusRes.ok) {
          const status = (await statusRes.json()) as BackendPipelineEvent
          applyBackendEvent({
            phase: 'navigator',
            step_id: 'extract-components',
            status: status.status,
            progress_percent: status.progress_percent,
            agent: status.agent,
          })
        }
      } catch {
        setStreamState('error')
      }

      connectEventStream()
    }

    bootstrap()

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [applyBackendEvent, connectEventStream, repoId])

  useEffect(() => {
    if (!autoStart || autoStartTriggeredRef.current) {
      return
    }

    const hasStarted =
      pipelineState.navigator.status === 'running' ||
      pipelineState.agentic.status === 'running' ||
      pipelineState.finalization.status === 'running' ||
      pipelineState.finalization.status === 'completed'

    if (hasStarted || isStarting) {
      autoStartTriggeredRef.current = true
      return
    }

    autoStartTriggeredRef.current = true
    void startPipeline()
  }, [autoStart, isStarting, pipelineState.agentic.status, pipelineState.finalization.status, pipelineState.navigator.status])

  useEffect(() => {
    if (selectedComponent) {
      return
    }

    const firstValid = pipelineState.agentic.iterations.find(
      (i) =>
        !i.componentName.toLowerCase().startsWith('component-') &&
        !(i.componentName.toLowerCase() === 'unknown' && i.filePath.toLowerCase() === 'unknown')
    )

    if (firstValid) {
      setSelectedComponent(firstValid.componentId)
    }
  }, [pipelineState.agentic.iterations, selectedComponent])

  // Calculate overall progress
  const totalSteps =
    pipelineState.navigator.steps.length +
    pipelineState.agentic.iterations.length +
    pipelineState.finalization.steps.length
  const completedSteps =
    pipelineState.navigator.steps.filter((s) => s.status === 'completed').length +
    pipelineState.agentic.completedComponents +
    pipelineState.finalization.steps.filter((s) => s.status === 'completed').length
  const overallProgress = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0
  const isPipelineCompleted = pipelineState.finalization.status === 'completed'

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
  <div>
    <h1 className="text-2xl font-bold text-gray-900">{repoMeta.name ?? 'Pipeline Execution'}</h1>
    <p className="text-sm text-gray-500 mt-1">
      Repo ID: {repoId}{typeof repoMeta.fileCount === 'number' ? ` • ${repoMeta.fileCount} files` : ''}
    </p>
  </div>
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="border-gray-300 text-gray-600">
              Stream: {streamState}
            </Badge>
            <Button onClick={connectEventStream} variant="outline" className="border-gray-300">
              Reconnect Stream
            </Button>
            <Button onClick={() => void startPipeline()} className="bg-emerald-600 hover:bg-emerald-700 text-white" disabled={isStarting}>
              {isStarting ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Play className="w-4 h-4 mr-2" />
              )}
              Run Analysis
            </Button>
          </div>
        </div>

        {/* Progress bar */}
        <Card className="bg-white border-gray-200 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Overall Progress</span>
            <span className="text-sm text-gray-600">{overallProgress}%</span>
          </div>
          <Progress value={overallProgress} className="h-2" />
          {isPipelineCompleted && (
            <div className="mt-3 flex items-center gap-2 text-emerald-600">
              <CheckCircle2 className="w-5 h-5" />
              <span className="font-medium">Pipeline completed successfully</span>
            </div>
          )}
        </Card>

        {/* Pipeline modules */}
        <div className="space-y-4">
          <NavigatorModuleCard
            module={pipelineState.navigator}
            detectedTotal={pipelineState.agentic.totalComponents}
            isExpanded={expandedModules.navigator}
            onToggle={() => toggleModule('navigator')}
          />

          <AgenticModuleCard
            module={pipelineState.agentic}
            isExpanded={expandedModules.agentic}
            onToggle={() => toggleModule('agentic')}
            selectedComponent={selectedComponent}
            onSelectComponent={setSelectedComponent}
          />

          <FinalizationModuleCard
            module={pipelineState.finalization}
            isExpanded={expandedModules.finalization}
            onToggle={() => toggleModule('finalization')}
          />
        </div>

        {isPipelineCompleted && (
          <div className="flex justify-end gap-2 pt-2">
            <Link href={`/dashboard/analysis/${repoId}/results/graph`}>
              <Button variant="outline" className="border-gray-300">
                View Graph
              </Button>
            </Link>
            <Link href={`/dashboard/analysis/${repoId}/results`}>
              <Button className="bg-emerald-600 hover:bg-emerald-700 text-white">
                View Results
              </Button>
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
