'use client'

import React, { useRef, useEffect, useState } from 'react';
import Link from 'next/link';
import { Search, CheckCircle, Folder, PenTool, Check, ChevronRight, Loader2, ArrowRight } from "lucide-react";
import { Button } from '@/components/ui/button';
import type { PipelineState, AgenticIteration, StepStatus } from './pipeline-data';

/* ──────────────────────────────────────────────────────────────────────
 * Edge label badges on the SVG graph
 * ────────────────────────────────────────────────────────────────────── */
const LabelBadge = ({ x, y, text, colorClass }: { x: number; y: number; text: string; colorClass?: string }) => (
  <span 
    className={`absolute -translate-x-1/2 -translate-y-1/2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 px-3 py-1 rounded-full shadow-[2px_2px_4px_rgba(0,0,0,0.1),-2px_-2px_4px_rgba(255,255,255,0.9)] dark:shadow-[2px_2px_4px_rgba(0,0,0,0.3),-2px_-2px_4px_rgba(255,255,255,0.1)] font-sans text-[11px] font-bold whitespace-nowrap ${colorClass || "text-gray-600 dark:text-gray-300"}`}
    style={{ left: x, top: y, zIndex: 15 }}
  >
    {text}
  </span>
);

/* ──────────────────────────────────────────────────────────────────────
 * Video card for each agent node (Compact & widened per user request)
 * ────────────────────────────────────────────────────────────────────── */
interface AgentVideoCardProps {
  top: string;
  left: string;
  title: string;
  icon: any;
  tasks: string[];
  videoSrc: string;
  status?: StepStatus;
}

const AgentVideoCard = ({ top, left, title, icon: Icon, tasks, videoSrc, status }: AgentVideoCardProps) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const isRunning = status === 'running';
  const isCompleted = status === 'completed';

  useEffect(() => {
    if (isRunning && videoRef.current) {
      videoRef.current.currentTime = 0;
      videoRef.current.play().catch(() => {});
    } else if (!isRunning && videoRef.current) {
      videoRef.current.pause();
    }
  }, [isRunning]);

  return (
    <div 
      className={`absolute rounded-3xl w-[295px] overflow-hidden bg-[#fff8fc] dark:bg-gray-800 transition-all duration-500 flex flex-col ring-1 ring-black/5 dark:ring-white/10 ${isRunning ? 'shadow-[24px_24px_48px_rgba(0,0,0,0.18),-24px_-24px_48px_rgba(255,255,255,1)] dark:shadow-[24px_24px_48px_rgba(0,0,0,0.4),-24px_-24px_48px_rgba(255,255,255,0.15)] scale-[1.06] -translate-y-3 z-30' : 'shadow-[12px_12px_24px_rgba(0,0,0,0.1),-12px_-12px_24px_rgba(255,255,255,0.8)] dark:shadow-[12px_12px_24px_rgba(0,0,0,0.3),-12px_-12px_24px_rgba(255,255,255,0.1)] z-10'} ${isCompleted && !isRunning ? 'ring-2 ring-emerald-400/50 shadow-[0_0_20px_rgba(16,185,129,0.2)]' : ''}`}
      style={{ top, left }}
    >
      <div className={`absolute inset-0 rounded-3xl border-2 transition-colors duration-500 pointer-events-none z-20 ${isRunning ? 'border-[#e897c6] dark:border-[#e897c6]/80' : 'border-transparent'}`}></div>

      {/* Reduced height Video frame */}
      <div className="relative h-[95px] w-full bg-gradient-to-br from-pink-100 to-rose-200 dark:from-pink-900/40 dark:to-rose-900/40 p-1 flex-shrink-0">
        <div className="w-full h-full rounded-t-[1.5rem] overflow-hidden bg-[#fff0f7] dark:bg-gray-800 relative">
          <video 
            ref={videoRef}
            src={videoSrc}
            muted
            loop
            playsInline
            className={`w-full h-full object-cover object-center transition-transform duration-700 ${isRunning ? 'scale-[1.04]' : 'scale-100'}`}
          />
          {isRunning && (
            <div className="absolute top-2 right-2 flex items-center gap-1.5 bg-blue-500/90 text-white text-[9px] font-bold px-2 py-1 rounded-full shadow-lg">
              <Loader2 className="w-3 h-3 animate-spin" />
              Active
            </div>
          )}
          {isCompleted && (
            <div className="absolute top-2 right-2 flex items-center gap-1.5 bg-emerald-500/90 text-white text-[9px] font-bold px-2 py-1 rounded-full shadow-lg">
              <CheckCircle className="w-3 h-3" />
              Done
            </div>
          )}
        </div>
      </div>

      <div className="bg-[#fff0f7] dark:bg-gray-800/80 py-2 px-4 flex items-center justify-center gap-2.5 border-b border-pink-200/50 dark:border-gray-700 h-[46px] flex-shrink-0">
        <Icon className="h-[20px] w-[20px] text-[#e897c6] dark:text-pink-400" strokeWidth={2.5} />
        <h3 className="text-[1.05rem] font-semibold text-gray-800 dark:text-gray-100 tracking-tight">{title}</h3>
      </div>

      <div className="bg-[#fff8fc] dark:bg-gray-800 p-4 pt-3 pb-5 flex-1 relative bg-[radial-gradient(circle_at_center,_#fce7f3_1px,_transparent_1.5px)] dark:bg-[radial-gradient(circle_at_center,_#374151_1px,_transparent_1.5px)] [background-size:16px_16px]">
        <ul className="space-y-[12px] relative z-10 w-full">
          {tasks.map((task: string, idx: number) => (
            <li key={idx} className="flex items-start gap-2.5 text-[12.5px] leading-snug text-[#4a4a4a] dark:text-gray-300 w-full">
              <div className={`mt-[5px] h-[5px] w-[5px] rounded-full flex-shrink-0 ${isRunning ? 'bg-blue-500 shadow-[0_0_5px_rgba(59,130,246,0.8)] animate-pulse' : isCompleted ? 'bg-emerald-500 shadow-[0_0_5px_rgba(16,185,129,0.8)]' : 'bg-[#e897c6] shadow-[0_0_5px_rgba(232,151,198,0.8)]'}`}></div>
              <span className="font-medium break-words flex-1">{task}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

/* ──────────────────────────────────────────────────────────────────────
 * Terminal Logs implementation (retained logic inside matching UI)
 * ────────────────────────────────────────────────────────────────────── */
function TerminalLogs({ iteration, pipelineState, filePath }: { iteration: AgenticIteration | null; pipelineState: PipelineState; filePath: string }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const logLines: { prefix: string; prefixColor: string; text: string; textColor: string }[] = [];

  if (iteration) {
    const addLogs = (stepLabel: string, logs: string[], color: string) => {
      logs.forEach((msg) => {
        logLines.push({ prefix: `[${stepLabel}]`, prefixColor: color, text: msg, textColor: 'text-gray-300' });
      });
    };
    addLogs('Reader', iteration.steps.reader.logs, 'text-blue-300');
    addLogs('Searcher', iteration.steps.searcher.logs, 'text-purple-300');
    addLogs('Writer', iteration.steps.writer.logs, 'text-amber-300');
    addLogs('Verifier', iteration.steps.verifier.logs, 'text-cyan-300');
    addLogs('Insert', iteration.steps.insertion.logs, 'text-emerald-300');
  }

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [logLines.length]);

  return (
    <aside className="bg-[#0f111a] text-gray-300 p-6 rounded-3xl w-full text-[13px] relative overflow-hidden flex flex-col flex-1 border border-gray-800 hover:scale-[1.01] transition-transform duration-500 z-10" style={{ fontFamily: "Consolas, 'Courier New', monospace" }}>
      <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500 opacity-80"></div>
      
      <div className="flex justify-between items-center mb-5 shrink-0 opacity-80">
        <div className="flex space-x-2">
          <div className="w-3 h-3 rounded-full bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.8)]"></div>
          <div className="w-3 h-3 rounded-full bg-yellow-500 shadow-[0_0_6px_rgba(234,179,8,0.8)]"></div>
          <div className="w-3 h-3 rounded-full bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.8)]"></div>
        </div>
        <p className="text-xs text-gray-500 tracking-wider">bash</p>
      </div>
      
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-2 opacity-90 pr-2 scrollbar-hide [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] leading-relaxed">
        <div className="flex pl-1"><span className="text-green-400 mr-2 flex-shrink-0">$</span><span className="text-gray-100 font-medium whitespace-nowrap">start-analysis --path {filePath.split('/').pop()}</span></div>
        <div className="flex pl-1"><span className="text-gray-500 mr-2 flex-shrink-0">&gt;</span><span className="text-blue-300">Initializing pipeline...</span></div>
        
        <div className="mt-3 pt-2"></div>
        
        <div className="flex pl-1"><span className="text-green-400 mr-2 flex-shrink-0">$</span><span className="text-gray-100 font-medium">agent-trace stream --watch</span></div>
        <div className="flex pl-1"><span className="text-gray-500 mr-2 flex-shrink-0"></span><span className="text-gray-400">[info] Processing component {(pipelineState.agentic.completedComponents + (!isPipelineComplete(pipelineState) ? 1 : 0))}/{pipelineState.agentic.totalComponents}</span></div>
        
        {logLines.map((line, i) => (
          <div key={i} className="flex pl-1">
            <span className={`${line.prefixColor} mr-2 flex-shrink-0 w-[80px]`}>{line.prefix}</span>
            <span className={line.textColor}>{line.text}</span>
          </div>
        ))}
        {(pipelineState.agentic.status === 'running') && (
          <div className="flex pl-3">
            <span className="text-gray-100 animate-pulse mt-1 inline-block w-2 bg-gray-300 shadow-[0_0_8px_rgba(255,255,255,0.5)] leading-tight h-3.5">&nbsp;</span>
          </div>
        )}
      </div>
    </aside>
  );
}

function isPipelineComplete(state: PipelineState) {
  return state.finalization.status === 'completed';
}

/* ──────────────────────────────────────────────────────────────────────
 * Main Execution Graph Component (Merged structured look w/ auto-scaling)
 * ────────────────────────────────────────────────────────────────────── */
export interface AgentPipelineExecutionProps {
  pipelineState: PipelineState;
  repoId: string;
  selectedComponent: string | null;
}

export function AgentPipelineExecution({ pipelineState, repoId, selectedComponent }: AgentPipelineExecutionProps) {
  const iterations = pipelineState.agentic.iterations;
  const currentIteration = selectedComponent
    ? iterations.find((i) => i.componentId === selectedComponent) ?? null
    : [...iterations].reverse().find((i) => i.status === 'running' || i.steps.reader.status === 'running' || i.steps.searcher.status === 'running' || i.steps.writer.status === 'running' || i.steps.verifier.status === 'running' || i.steps.insertion.status === 'running') ?? iterations[iterations.length - 1] ?? null;
  const isFirstComponent = iterations.length > 0 && iterations[0].componentId === currentIteration?.componentId;
  let readerStatus = currentIteration?.steps.reader.status ?? 'pending';

  if (!isFirstComponent && readerStatus === 'pending' && currentIteration?.currentStep) {
    readerStatus = 'completed';
  }
  let searcherStatus = currentIteration?.steps.searcher.status ?? 'pending';
  let writerStatus = currentIteration?.steps.writer.status ?? 'pending';
  let verifierStatus = currentIteration?.steps.verifier.status ?? 'pending';
  let insertionStatus = currentIteration?.steps.insertion.status ?? 'pending';

  const trueActive = currentIteration?.currentStep;
  if (trueActive) {
    if (trueActive !== 'reader' && readerStatus === 'running') readerStatus = 'completed';
    if (trueActive !== 'searcher' && searcherStatus === 'running') searcherStatus = 'completed';
    if (trueActive !== 'writer' && writerStatus === 'running') writerStatus = 'completed';
    if (trueActive !== 'verifier' && verifierStatus === 'running') verifierStatus = 'completed';
    if (trueActive !== 'insertion' && insertionStatus === 'running') insertionStatus = 'completed';

    if (trueActive === 'writer') {
       verifierStatus = 'pending';
       insertionStatus = 'pending';
    } else if (trueActive === 'reader') {
       searcherStatus = 'pending';
       writerStatus = 'pending';
       verifierStatus = 'pending';
    }
  }

  const componentName = currentIteration?.componentName ?? '...';
  const componentType = currentIteration?.componentType ?? 'function';
  const filePath = currentIteration?.filePath ?? '...';
  const completedCount = pipelineState.agentic.completedComponents;
  const totalCount = pipelineState.agentic.totalComponents;
  const isPipelineCompleted = pipelineState.finalization.status === 'completed';
  const progressPct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  // Auto-scale wrapper for graph to flawlessly fit screen bounds
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const updateScale = () => {
      if (!wrapperRef.current) return;
      const { width, height } = wrapperRef.current.getBoundingClientRect();
      const scaleX = width / 1000;
      const scaleY = height / 740;
      setScale(Math.min(scaleX, scaleY, 1.05));
    };
    updateScale();
    window.addEventListener('resize', updateScale);
    return () => window.removeEventListener('resize', updateScale);
  }, []);

  // Computed path highlighting logic
  const searcherActive = searcherStatus === 'running';
  const searcherCompleted = searcherStatus === 'completed';
  const readerCompleted = readerStatus === 'completed';
  const writerActive = writerStatus === 'running';
  const writerCompleted = writerStatus === 'completed';
  const verifierCompleted = verifierStatus === 'completed';

  const needsContext = searcherActive || searcherCompleted;
  const contextNotNeeded = !needsContext && (writerActive || writerCompleted);

  const feedbackToReader = Boolean(currentIteration?.traversedToReader);
  const feedbackToWriter = Boolean(currentIteration?.traversedToWriter);
  
  const contextNotFound = currentIteration?.steps.searcher.logs.some(log => log.includes('context_not_found')) || (currentIteration?.verifierFeedback === 'rejected-to-reader' && searcherCompleted);
  const contextFound = currentIteration?.steps.searcher.logs.some(log => log.includes('context_found'));

  const pathNeedContext = readerCompleted && needsContext;
  const pathContextNotFound = contextNotFound;
  const pathContextFound = contextFound;
  const pathContextNotNeeded = readerCompleted && contextNotNeeded;
  const pathDocstringGenerated = writerCompleted;
  const pathNeedsRevision = feedbackToWriter;
  const pathNeedsMoreContext = feedbackToReader;
  const pathDocstringInserted = verifierCompleted && !feedbackToReader && !feedbackToWriter;

  return (
    <div className="w-full h-[calc(100vh-56px)] max-w-[1550px] mx-auto p-4 md:p-6 lg:p-8 bg-transparent overflow-hidden relative flex flex-col" style={{ fontFamily: "Arial, Helvetica, sans-serif" }}>

      <div className="relative z-10 flex flex-col h-full items-center">
        
        <div className="flex flex-col xl:flex-row gap-6 lg:gap-8 w-full items-start flex-1 min-h-0 pt-2">
          
          {/* LEFT COLUMN: Two stacked Info Cards (retains dynamic props) */}
          <div className="flex flex-col gap-6 w-full xl:w-[480px] shrink-0 z-20 h-full min-h-0 pl-10 md:pl-20 xl:pl-32">
             
             {/* Info Card 1: Details */}
             <div className="bg-[#faf0f7] dark:bg-gray-800 rounded-3xl p-6 ring-1 ring-black/5 dark:ring-white/10 relative overflow-hidden group hover:scale-[1.01] transition-transform duration-500 shrink-0 font-sans">
                <div className="absolute inset-0 bg-transparent pointer-events-none"></div>

                <p className="text-[11px] font-bold tracking-widest text-black uppercase mb-4 pl-1">Analyzing Target</p>
                
                <h3 className="font-extrabold text-xl text-black mb-6 flex items-center gap-3">
                  <span className="text-black truncate block" title={componentName}>{componentName}</span>
                </h3>

                <div className="space-y-4">
                  <div className="flex items-center justify-between border-b border-black/5 dark:border-gray-700/50 pb-3">
                    <span className="text-sm font-medium text-black/60 dark:text-gray-400">Component Type</span>
                    <div className="flex items-center gap-1.5 text-sm font-bold text-gray-600 dark:text-gray-200">
                      <div className="w-5 h-5 rounded bg-emerald-100 dark:bg-emerald-900/40 flex items-center justify-center text-emerald-600 dark:text-emerald-400 text-xs">
                        {componentType === 'class' ? 'C' : componentType === 'method' ? 'M' : 'ƒ'}
                      </div>
                      {componentType.charAt(0).toUpperCase() + componentType.slice(1)}
                    </div>
                  </div>

                  <div className="border-b border-black/5 dark:border-gray-700/50 pb-3">
                    <span className="text-sm font-medium text-black/60 dark:text-gray-400 block mb-2">File Path</span>
                    <span className="font-sans text-[11px] bg-black/5 dark:bg-gray-900 text-black/60 dark:text-gray-300 px-2 py-1.5 rounded-lg border border-black/5 dark:border-gray-700 w-full block break-all leading-relaxed" title={filePath}>
                      {filePath}
                    </span>
                  </div>

                  <div className="pt-2">
                    <div className="flex justify-between items-end mb-1.5">
                      <span className="text-xs font-semibold text-black/60 dark:text-gray-400">Total Progress</span>
                      <span className="text-xs font-bold text-emerald-600 dark:text-emerald-500 bg-emerald-100/50 dark:bg-emerald-900/30 px-2 py-0.5 rounded ">{completedCount}/{totalCount} components</span>
                    </div>
                    <div className="w-full bg-black/5 dark:bg-gray-700 rounded-full h-2">
                      <div className="bg-gradient-to-r from-[#6ee7b7] to-[#34d399] h-2 rounded-full transition-all duration-1000" style={{ width: `${progressPct}%` }}></div>
                    </div>
                  </div>
                </div>
             </div>

             {/* Info Card 2: Terminal */}
             <TerminalLogs iteration={currentIteration} pipelineState={pipelineState} filePath={filePath} />
          </div>
          
          {/*RIGHT COLUMN: The Pipeline Execution Graph */}
          <div ref={wrapperRef} className="flex-1 w-full relative h-[650px] xl:h-full bg-transparent overflow-hidden flex items-center justify-center min-h-[400px]">

            <div 
              className="origin-center transition-transform duration-300 relative shrink-0 flex items-center justify-center" 
              style={{ width: 1000, height: 740, transform: `scale(${scale})` }}
            >
              <div className="relative w-full h-full">
            
                {/* SVG Edge Connectors perfectly aligned */}
                <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 0 }}>
                  <defs>
                    <marker id="pe-arr" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                      <path d="M 0 0 L 10 5 L 0 10 z" className="fill-gray-400 dark:fill-gray-500" />
                    </marker>
                    <marker id="pe-arr-red" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                      <path d="M 0 0 L 10 5 L 0 10 z" className="fill-red-400 dark:fill-red-500" />
                    </marker>
                    <marker id="pe-arr-green" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                      <path d="M 0 0 L 10 5 L 0 10 z" className="fill-emerald-400 dark:fill-emerald-500" />
                    </marker>
                    <marker id="pe-arr-blue" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                      <path d="M 0 0 L 10 5 L 0 10 z" className="fill-blue-400 dark:fill-blue-500" />
                    </marker>
                    <marker id="pe-arr-amber" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                      <path d="M 0 0 L 10 5 L 0 10 z" className="fill-amber-400 dark:fill-amber-500" />
                    </marker>
                    <marker id="pe-arr-indigo" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                      <path d="M 0 0 L 10 5 L 0 10 z" className="fill-indigo-400 dark:fill-indigo-500" />
                    </marker>
                  </defs>
                  
                  <g strokeWidth="2" fill="none" strokeDasharray="6 6">
                    {/* Need context: Reader(320)->Searcher(680) */}
                    <path d="M 320 95 L 680 95" markerEnd={pathNeedContext ? "url(#pe-arr-blue)" : "url(#pe-arr)"} className={pathNeedContext ? "stroke-blue-400 dark:stroke-blue-500" : "stroke-gray-300 dark:stroke-gray-600"} />
                    {/* Context not found: Searcher(680)->Reader(320) */}
                    <path d="M 680 150 L 320 150" markerEnd={pathContextNotFound ? "url(#pe-arr-red)" : "url(#pe-arr)"} className={pathContextNotFound ? "stroke-red-400 dark:stroke-red-500" : "stroke-gray-300 dark:stroke-gray-600"} />
                    {/* Context found: Searcher(810, 265)->Writer(810, 370) */}
                    <path d="M 810 265 L 810 370" markerEnd={pathContextFound ? "url(#pe-arr-green)" : "url(#pe-arr)"} className={pathContextFound ? "stroke-emerald-400 dark:stroke-emerald-500" : "stroke-gray-300 dark:stroke-gray-600"} />
                    {/* Context not needed: Reader(right bot) -> Writer(top left) */}
                    <path d="M 320 240 L 680 420" markerEnd={pathContextNotNeeded ? "url(#pe-arr-blue)" : "url(#pe-arr)"} className={pathContextNotNeeded ? "stroke-blue-400 dark:stroke-blue-500" : "stroke-gray-300 dark:stroke-gray-600"} />
                    {/* Docstring generated: Writer(680)->Verifier(320) */}
                    <path d="M 680 420 L 320 420" markerEnd={pathDocstringGenerated ? "url(#pe-arr-blue)" : "url(#pe-arr)"} className={pathDocstringGenerated ? "stroke-blue-400 dark:stroke-blue-500" : "stroke-gray-300 dark:stroke-gray-600"} />
                    {/* Needs Revision: Verifier(320)->Writer(680) */}
                    <path d="M 320 480 L 680 480" markerEnd={pathNeedsRevision ? "url(#pe-arr-amber)" : "url(#pe-arr)"} className={pathNeedsRevision ? "stroke-amber-400 dark:stroke-amber-500" : "stroke-gray-300 dark:stroke-gray-600"} />
                    {/* Needs more context: Verifier(190, 370)->Reader(190, 265) */}
                    <path d="M 190 370 L 190 265" markerEnd={pathNeedsMoreContext ? "url(#pe-arr-indigo)" : "url(#pe-arr)"} className={pathNeedsMoreContext ? "stroke-indigo-400 dark:stroke-indigo-500" : "stroke-gray-300 dark:stroke-gray-600"} />
                    {/* Docstring Inserted: Verifier(280, 595)->Docstring(380, 660) */}
                    <path d="M 280 595 L 380 660" markerEnd={pathDocstringInserted ? "url(#pe-arr-green)" : "url(#pe-arr)"} className={pathDocstringInserted ? "stroke-emerald-400 dark:stroke-emerald-500" : "stroke-gray-300 dark:stroke-gray-600"} strokeWidth="2.5" strokeDasharray="8 8" />
                  </g>
                </svg>

                {/* Specific Labels mapping perfectly to the edge paths */}
                <div className="absolute inset-0 pointer-events-none z-10">
                  <LabelBadge x={500} y={80} text="Need context" colorClass={pathNeedContext ? "text-blue-500" : "text-gray-400 dark:text-gray-500 font-normal"} />
                  <LabelBadge x={500} y={135} text="Context not found" colorClass={pathContextNotFound ? "text-red-500" : "text-gray-400 dark:text-gray-500 font-normal"} />
                  <LabelBadge x={890} y={317} text="Context found" colorClass={pathContextFound ? "text-emerald-500" : "text-gray-400 dark:text-gray-500 font-normal"} />
                  <LabelBadge x={500} y={315} text="Context not needed" colorClass={pathContextNotNeeded ? "text-blue-500" : "text-gray-400 dark:text-gray-500 font-normal"} />
                  <LabelBadge x={500} y={405} text="Docstring generated" colorClass={pathDocstringGenerated ? "text-blue-500" : "text-gray-400 dark:text-gray-500 font-normal"} />
                  <LabelBadge x={500} y={465} text="Needs Revision" colorClass={pathNeedsRevision ? "text-amber-500" : "text-gray-400 dark:text-gray-500 font-normal"} />
                  <LabelBadge x={105} y={317} text="Needs more context" colorClass={pathNeedsMoreContext ? "text-indigo-500" : "text-gray-400 dark:text-gray-500 font-normal"} />
                  <LabelBadge x={300} y={625} text="Docstring Inserted" colorClass={pathDocstringInserted ? "text-emerald-500" : "text-gray-400 dark:text-gray-500 font-normal"} />
                </div>

                {/* Card 1: Reader Agent */}
                <AgentVideoCard 
                  top="40px" left="60px" 
                  title="Reader agent" icon={Search} status={readerStatus}
                  tasks={["Analyzing intent...", "Checking signatures", "Requesting context"]} 
                  videoSrc="/Robot_Reads_Codebase_Video_Generated.mp4" 
                />

                {/* Card 2: Searcher Agent */}
                <AgentVideoCard 
                  top="40px" left="680px" 
                  title="Searcher agent" icon={Folder} status={searcherStatus}
                  tasks={["Searching repo...", "Fetching context"]} 
                  videoSrc="/Robot_Searches_Codebase_for_Dependencies.mp4"
                />

                {/* Card 3: Verifier Agent */}
                <AgentVideoCard 
                  top="370px" left="60px" 
                  title="Verifier agent" icon={CheckCircle} status={verifierStatus}
                  tasks={["Reviewing output...", "Validating clarity..."]} 
                  videoSrc="/Robot_verifies_Codebase_Video_Generated.mp4" 
                />

                {/* Card 4: Writer Agent */}
                <AgentVideoCard 
                  top="370px" left="680px" 
                  title="Writer agent" icon={PenTool} status={writerStatus}
                  tasks={["Generating draft...", "Formatting output"]} 
                  videoSrc="/Robot_writes_Codebase_For_Dependencies.mp4" 
                />

                {/* Card 5: Docstring Inserted */}
                <div className="group absolute top-[650px] left-[360px] w-[280px] bg-[#f9dbed] dark:bg-gray-800 rounded-full py-4 px-6 border border-pink-300 transition-all duration-500 hover:scale-105 hover:-translate-y-2 z-20 flex items-center justify-center gap-3">
                  <div className={`absolute inset-0 rounded-full border opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none ${insertionStatus === 'completed' ? 'border-green-300' : 'border-gray-300'}`}></div>
                  <div className={`rounded-full p-2.5 shadow-[2px_2px_4px_rgba(0,0,0,0.1)] transition-all duration-300 group-hover:scale-110 group-hover:rotate-12 flex-shrink-0 ${insertionStatus === 'completed' ? 'bg-green-500 shadow-[0_0_15px_rgba(34,197,94,0.5)]' : insertionStatus === 'running' ? 'bg-blue-500 animate-pulse' : 'bg-gray-400'}`}>
                    <Check className="h-[22px] w-[22px] text-white" strokeWidth={3} />
                  </div>
                  <span className={`text-[1.1rem] font-bold transition-colors duration-300 ${insertionStatus === 'completed' ? 'text-green-600' : 'text-gray-800 dark:text-gray-200'}`}>Docstring Inserted</span>
                </div>

                {/* Final Pipeline Actions */}
                {isPipelineCompleted && (
                  <div className="absolute bottom-[20px] right-[-100px] flex gap-4 z-40 bg-white/95 dark:bg-gray-900/95 backdrop-blur-md px-6 py-4 rounded-full border border-gray-200 dark:border-gray-700">
                    <Link href={`/dashboard/analysis/${repoId}/results/graph`}>
                      <Button variant="outline" className="border-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-full px-6 py-5 text-[15px] font-semibold transition-all hover:scale-105">
                        View Graph
                        <ChevronRight className="w-5 h-5 ml-1.5" />
                      </Button>
                    </Link>
                    <Link href={`/dashboard/analysis/${repoId}/results`}>
                      <Button className="bg-gradient-to-r from-emerald-500 to-green-600 hover:from-emerald-600 hover:to-green-700 text-white rounded-full px-6 py-5 text-[15px] font-semibold transition-all hover:scale-105">
                        View Results
                        <ArrowRight className="w-5 h-5 ml-1.5" />
                      </Button>
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
