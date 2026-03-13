"use client";
import { useState } from "react";
import { Search, GitBranch, FileCode, Download, CheckCircle, AlertCircle, BarChart3 } from "lucide-react";

export default function Home() {
  const [repoUrl, setRepoUrl] = useState("");
  const [result, setResult] = useState<any>(null);
  const [evalResult, setEvalResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("formatted");

  async function analyzeRepo() {
    if (!repoUrl.trim()) {
      setError("Please enter a repository URL");
      return;
    }

    setLoading(true);
    setResult(null);
    setEvalResult(null);
    setError("");

    try {
      const res = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl }),
      });

      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Failed to analyze repository");
    } finally {
      setLoading(false);
    }
  }

  function downloadJSON() {
    if (!result) return;
    
    const blob = new Blob([JSON.stringify(result.components, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `analysis-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function evaluateDocumentation() {
    if (!result) return;
    const repoName = repoUrl.split("/").pop()?.replace(".git", "") || "unknown";

    setEvaluating(true);
    setEvalResult(null);
    setError("");

    try {
      const res = await fetch("http://localhost:8000/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_name: repoName }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP error! status: ${res.status}`);
      }

      const data = await res.json();
      setEvalResult(data);
    } catch (err: any) {
      setError(err.message || "Evaluation failed");
    } finally {
      setEvaluating(false);
    }
  }
"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { useSession } from "next-auth/react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  ArrowRight,
  Code2,
  GitBranch,
  FileText,
  BarChart3,
  Zap,
  Shield,
  Brain,
  Network,
  Cpu,
  Eye,
  PenTool,
  CheckCircle,
  ChevronRight,
  Play,
  Terminal,
  User,
} from "lucide-react"

const codeSnippets = [
  "def analyze_code():",
  "  graph = build_cfg()",
  "  return extract_docs()",
  "async function parse() {",
  "  const ast = await read()",
  "  return transform(ast)",
  "class Navigator:",
  "  def traverse(self):",
  "    yield from self.nodes",
]

function FloatingCode() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {codeSnippets.map((snippet, i) => (
        <div
          key={snippet}
          className="absolute text-sm font-mono text-foreground/15 whitespace-nowrap"
          style={{
            left: `${5 + (i % 3) * 35}%`,
            top: `${15 + Math.floor(i / 3) * 30}%`,
            animation: `float ${6 + (i % 3)}s ease-in-out infinite`,
            animationDelay: `${i * 0.5}s`,
          }}
        >
          {snippet}
        </div>
      ))}
    </div>
  )
}



function AgentOrbit() {
  const agents = [
    { icon: Eye, name: "Reader", angle: 0, bgColor: "bg-violet-100", iconColor: "text-violet-600" },
    { icon: PenTool, name: "Writer", angle: 90, bgColor: "bg-amber-100", iconColor: "text-amber-600" },
    { icon: CheckCircle, name: "Verifier", angle: 180, bgColor: "bg-emerald-100", iconColor: "text-emerald-600" },
    { icon: Network, name: "Searcher", angle: 270, bgColor: "bg-sky-100", iconColor: "text-sky-600" },
  ]
  
  const radius = 60
  
  return (
    <div className="relative w-44 h-44">
      {/* Rotating container */}
      <div className="absolute inset-0 animate-spin" style={{ animationDuration: '30s' }}>
        {/* Orbit ring */}
        <div className="absolute inset-3 rounded-full border border-dashed border-border" />
        
        {/* Rotating agents */}
        {agents.map((agent) => {
          const angleRad = (agent.angle * Math.PI) / 180
          const x = Math.cos(angleRad) * radius
          const y = Math.sin(angleRad) * radius
          
          return (
            <div
              key={agent.name}
              className="absolute left-1/2 top-1/2"
              style={{
                transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))`,
              }}
            >
              {/* Counter-rotate to keep icons upright */}
              <div className="animate-spin" style={{ animationDuration: '30s', animationDirection: 'reverse' }}>
                <div className={`w-9 h-9 rounded-full ${agent.bgColor} flex items-center justify-center shadow-sm`}>
                  <agent.icon className={`w-4 h-4 ${agent.iconColor}`} />
                </div>
              </div>
            </div>
          )
        })}
      </div>
      
      {/* Center brain - static */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="w-11 h-11 rounded-full bg-slate-100 flex items-center justify-center">
          <Brain className="w-5 h-5 text-slate-600" />
        </div>
      </div>
    </div>
  )
}

export default function LandingPage() {
  const [activeStep, setActiveStep] = useState(0)
  const { data: session, status } = useSession()
  const isSignedIn = status === "authenticated"
  const getStartedHref = isSignedIn ? "/dashboard" : "/login"
  
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % 5)
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  const pipelineSteps = [
    { icon: Terminal, label: "Upload", desc: "Source Code" },
    { icon: Network, label: "Navigate", desc: "Build Graphs" },
    { icon: Brain, label: "Reason", desc: "Agent Pipeline" },
    { icon: FileText, label: "Generate", desc: "Documentation" },
    { icon: BarChart3, label: "Evaluate", desc: "Quality Metrics" },
  ]

  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      {/* Background */}
      <div className="fixed inset-0 grid-pattern pointer-events-none opacity-50" />

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 glass">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-foreground flex items-center justify-center">
              <Code2 className="w-4 h-4 text-background" />
            </div>
            <span className="text-lg font-semibold text-foreground">CodeIQ</span>
          </div>
          <div className="hidden md:flex items-center gap-1">
            {["Features", "Pipeline", "Agents", "Docs"].map((item) => (
              <Link
                key={item}
                href={`#${item.toLowerCase()}`}
                className="px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Analyzing...
                  </span>
                ) : (
                  "Analyze"
                )}
              </button>
              {result && (
                <button
                  onClick={evaluateDocumentation}
                  disabled={evaluating}
                  className="px-8 py-4 bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-semibold rounded-xl hover:from-blue-700 hover:to-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg hover:shadow-xl transform hover:scale-105"
                >
                  {evaluating ? (
                    <span className="flex items-center gap-2">
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Evaluating...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <BarChart3 className="w-5 h-5" />
                      Evaluate
                    </span>
                  )}
                </button>
              )}
            </div>

            {error && (
              <div className="flex items-center gap-2 bg-red-500/20 border border-red-500/50 rounded-lg p-4 text-red-200">
                <AlertCircle className="w-5 h-5" />
                <span>{error}</span>
              </div>
                {item}
              </Link>
            ))}
          </div>
          <div className="flex items-center gap-2">
            {isSignedIn ? (
              <>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-secondary text-sm text-muted-foreground">
                  <User className="w-4 h-4" />
                  <span className="max-w-[160px] truncate">{session?.user?.email}</span>
                </div>
                <Link href="/dashboard">
                  <Button className="bg-foreground text-background hover:bg-foreground/90 h-9 px-4 text-sm">
                    Dashboard
                  </Button>
                </Link>
              </>
            ) : (
              <>
                <Link href="/login">
                  <Button variant="ghost" className="text-muted-foreground hover:text-foreground h-9 px-3 text-sm">Sign In</Button>
                </Link>
                <Link href="/login">
                  <Button className="bg-foreground text-background hover:bg-foreground/90 h-9 px-4 text-sm">
                    Get Started
                  </Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section - Full Screen */}
      <section className="min-h-screen flex items-center justify-center px-6 relative">
        <FloatingCode />
        
        <div className="max-w-4xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-foreground/5 border border-foreground/10 mb-8">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-75" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
            </span>
            <span className="text-xs font-medium text-muted-foreground">Agentic AI Documentation</span>
          </div>
          
          <h1 className="text-6xl md:text-7xl lg:text-8xl font-semibold text-foreground leading-[1.1] tracking-tight">
            Code that{" "}
            <span className="relative inline-block">
              <span className="relative z-10">documents</span>
              <svg className="absolute -bottom-2 md:-bottom-3 left-0 w-full h-4 md:h-5 overflow-visible" viewBox="0 0 200 20" preserveAspectRatio="none">
                <path
                  d="M0 10 Q50 2, 100 10 T200 10"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="3"
                  strokeLinecap="round"
                  className="text-primary"
                />
              </svg>
            </span>{" "}
            itself
          </h1>
          
          <p className="mt-8 text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            Transform your codebase with AI that understands context, reasons like developers, 
            and generates documentation that actually helps.
          </p>
          
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href={getStartedHref}>
              <Button className="bg-foreground text-background hover:bg-foreground/90 h-11 px-6 text-base font-medium group">
                Get Started
                <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </Button>
            </Link>
            <Link href="#pipeline">
              <Button variant="outline" className="h-11 px-6 text-base font-medium border-border bg-transparent hover:bg-secondary group">
                <Play className="w-4 h-4 mr-2" />
                Watch Demo
              </Button>
            </Link>
          </div>
          
          {/* Quick stats - centered */}
          <div className="mt-16 flex items-center justify-center gap-12 md:gap-16">
            {[
              { value: "10x", label: "Faster docs" },
              { value: "97%", label: "Accuracy" },
              { value: "4", label: "AI Agents" },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <div className="text-3xl md:text-4xl font-semibold text-foreground">{stat.value}</div>
                <div className="text-sm text-muted-foreground mt-1">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pipeline Section */}
      <section id="pipeline" className="py-20 px-6 relative">
        <div className="absolute inset-0 bg-secondary/30" />
        
        <div className="max-w-6xl mx-auto relative">
          <div className="text-center mb-12">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">How it works</p>
            <h2 className="text-2xl md:text-3xl font-semibold text-foreground">From Code to Docs</h2>
            <p className="mt-2 text-sm text-muted-foreground max-w-lg mx-auto">
              Watch your code transform through our five-stage agentic pipeline
            </p>
          </div>

          {/* Animated pipeline */}
          <div className="relative">
            {/* Connection line */}
            <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-border -translate-y-1/2 hidden lg:block" />
            <div 
              className="absolute top-1/2 left-0 h-0.5 bg-emerald-500 -translate-y-1/2 transition-all duration-500 hidden lg:block"
              style={{ width: `${(activeStep + 1) * 20}%` }}
            />
            
            <div className="grid lg:grid-cols-5 gap-4">
              {pipelineSteps.map((step, i) => (
                <div
                  key={step.label}
                  className={`relative transition-all duration-300 ${
                    i <= activeStep ? "opacity-100" : "opacity-40"
                  }`}
                >
                  <Card className={`border-border bg-card ${
                    i === activeStep ? "border-foreground/20 shadow-sm" : ""
                  }`}>
                    <CardContent className="p-5 text-center">
                      <div className={`w-11 h-11 rounded-lg mx-auto mb-3 flex items-center justify-center transition-colors ${
                        i <= activeStep ? "bg-emerald-50" : "bg-secondary"
                      }`}>
                        <step.icon className={`w-5 h-5 ${
                          i <= activeStep ? "text-emerald-600" : "text-muted-foreground"
                        }`} />
                      </div>
                      <h3 className="text-sm font-medium text-foreground mb-0.5">{step.label}</h3>
                      <p className="text-xs text-muted-foreground">{step.desc}</p>
                    </CardContent>
                  </Card>
                  
                  {/* Step number */}
                  <div className={`absolute -top-2 left-1/2 -translate-x-1/2 w-5 h-5 rounded-full flex items-center justify-center text-xs font-medium ${
                    i <= activeStep ? "bg-emerald-500 text-white" : "bg-muted text-muted-foreground"
                  }`}>
                    {i + 1}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Features Bento Grid */}
      <section id="features" className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Features</p>
            <h2 className="text-2xl md:text-3xl font-semibold text-foreground">Why CodeIQ?</h2>
            <p className="mt-2 text-sm text-muted-foreground max-w-lg mx-auto">
              Built for developers who value accurate, maintainable documentation
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Large feature card */}
            <Card className="lg:col-span-2 border-border bg-card hover:border-foreground/20 transition-all">
              <CardContent className="p-6 h-full">
                <div className="flex flex-col h-full">
                  <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center mb-4">
                    <Network className="w-5 h-5 text-slate-600" />
                  </div>
                  <h3 className="text-base font-medium text-foreground mb-2">Graph-Based Understanding</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Control Flow Graphs, Program Dependency Graphs, and Hybrid Program Graphs 
                    provide deep semantic understanding of your code structure.
                  </p>
                  <div className="mt-auto flex flex-wrap gap-1.5">
                    {["CFG", "PDG", "HPG", "GHG"].map((tag) => (
                      <span key={tag} className="px-2 py-1 rounded bg-secondary text-xs font-medium text-muted-foreground">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Tall feature card */}
            <Card className="lg:row-span-2 border-border bg-card hover:border-foreground/20 transition-all">
              <CardContent className="p-6 h-full flex flex-col">
                <div className="w-10 h-10 rounded-lg bg-violet-50 flex items-center justify-center mb-4">
                  <Brain className="w-5 h-5 text-violet-600" />
                </div>
                <h3 className="text-base font-medium text-foreground mb-2">Multi-Agent Architecture</h3>
                <p className="text-sm text-muted-foreground mb-6">
                  Four specialized agents collaborate with human-like reasoning patterns.
                </p>
                <div className="flex-1 flex items-center justify-center">
                  <AgentOrbit />
                </div>
              </CardContent>
            </Card>

            {/* Small cards */}
            {[
              { icon: Zap, title: "Real-time Pipeline", desc: "Watch documentation unfold live", bgColor: "bg-amber-50", iconColor: "text-amber-600" },
              { icon: Shield, title: "Verification Layer", desc: "Built-in accuracy checks", bgColor: "bg-emerald-50", iconColor: "text-emerald-600" },
              { icon: BarChart3, title: "Quality Metrics", desc: "Completeness & consistency scores", bgColor: "bg-sky-50", iconColor: "text-sky-600" },
              { icon: GitBranch, title: "Version Tracking", desc: "Docs evolve with your code", bgColor: "bg-rose-50", iconColor: "text-rose-600" },
            ].map((feature) => (
              <Card key={feature.title} className="border-border bg-card hover:border-foreground/20 transition-all">
                <CardContent className="p-5">
                  <div className={`w-9 h-9 rounded-lg ${feature.bgColor} flex items-center justify-center mb-3`}>
                    <feature.icon className={`w-4 h-4 ${feature.iconColor}`} />
                  </div>
                  <h3 className="text-sm font-medium text-foreground mb-1">{feature.title}</h3>
                  <p className="text-xs text-muted-foreground">{feature.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Agents Section */}
      <section id="agents" className="py-20 px-6 relative">
        <div className="absolute inset-0 bg-secondary/20" />
        
        <div className="max-w-6xl mx-auto relative">
          <div className="text-center mb-12">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">AI Agents</p>
            <h2 className="text-2xl md:text-3xl font-semibold text-foreground">Meet the Agents</h2>
            <p className="mt-2 text-sm text-muted-foreground max-w-lg mx-auto">
              Specialized AI agents that collaborate like a human team
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              {
                icon: Eye,
                name: "Reader",
                role: "Semantic Extraction",
                tasks: ["Parse code structure", "Extract semantics", "Summarize patterns"],
                bgColor: "bg-violet-50",
                iconColor: "text-violet-600",
              },
              {
                icon: Network,
                name: "Searcher",
                role: "Context Discovery",
                tasks: ["Navigate graphs", "Find dependencies", "Link references"],
                bgColor: "bg-amber-50",
                iconColor: "text-amber-600",
              },
              {
                icon: PenTool,
                name: "Writer",
                role: "Documentation",
                tasks: ["Generate docstrings", "Create READMEs", "Format output"],
                bgColor: "bg-emerald-50",
                iconColor: "text-emerald-600",
              },
              {
                icon: CheckCircle,
                name: "Verifier",
                role: "Quality Assurance",
                tasks: ["Validate accuracy", "Check consistency", "Score quality"],
                bgColor: "bg-sky-50",
                iconColor: "text-sky-600",
              },
            ].map((agent) => (
              <Card key={agent.name} className="border-border bg-card hover:border-foreground/20 transition-all">
                <CardContent className="p-5">
                  <div className={`w-10 h-10 rounded-lg ${agent.bgColor} flex items-center justify-center mb-3`}>
                    <agent.icon className={`w-5 h-5 ${agent.iconColor}`} />
                  </div>
                  <h3 className="text-sm font-medium text-foreground">{agent.name}</h3>
                  <p className="text-xs text-muted-foreground mb-3">{agent.role}</p>
                  <ul className="space-y-1.5">
                    {agent.tasks.map((task) => (
                      <li key={task} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <ChevronRight className="w-3 h-3 text-muted-foreground/50" />
                        {task}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Simple CTA */}
      <section className="py-16 px-6 border-t border-border">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-xl font-semibold text-foreground mb-2">
            Ready to improve your documentation?
          </h2>
          <p className="text-sm text-muted-foreground mb-6">
            Start analyzing your codebase with CodeIQ today.
          </p>
          <Link href={getStartedHref}>
            <Button className="bg-foreground text-background hover:bg-foreground/90 h-10 px-5 text-sm font-medium">
              Get Started
              <ArrowRight className="ml-2 w-4 h-4" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-12 px-6 bg-card">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-foreground flex items-center justify-center">
              <Code2 className="w-6 h-6 text-background" />
            </div>
            <span className="text-xl font-bold text-foreground">CodeIQ</span>
          </div>
          <p className="text-sm text-muted-foreground">
            Agentic AI for Context-Aware Code Documentation
          </p>
          <div className="flex items-center gap-6">
            <Link href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Docs</Link>
            <Link href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">GitHub</Link>
            <Link href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Twitter</Link>
          </div>
        )}

        {/* ==================== EVALUATION RESULTS ==================== */}
        {evalResult && (
          <div className="space-y-6 mt-8">
            {/* Overall Quality Score */}
            <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 border border-white/20 shadow-2xl text-center">
              <div className="text-sm uppercase tracking-widest text-purple-300 mb-2">Overall Quality Score</div>
              <div className="text-6xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-400">
                {(evalResult.overall_quality_score * 100).toFixed(1)}%
              </div>
              <div className="text-purple-200/60 mt-2 text-sm">Weighted: 35% Completeness + 35% Helpfulness + 30% Truthfulness</div>
            </div>

            {/* Three Metric Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Completeness */}
              <div className="bg-gradient-to-br from-purple-500/20 to-pink-500/20 backdrop-blur-lg rounded-xl p-6 border border-white/20">
                <h3 className="text-lg font-bold text-white mb-1">Completeness</h3>
                <p className="text-purple-200/60 text-xs mb-4">Are all docstring sections present?</p>
                <div className="text-4xl font-bold text-purple-300 mb-4">
                  {(evalResult.completeness.summary.overall_score * 100).toFixed(1)}%
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between text-purple-200">
                    <span>Components</span>
                    <span className="font-semibold">{evalResult.completeness.summary.total_components}</span>
                  </div>
                  <div className="flex justify-between text-purple-200">
                    <span>With Docstrings</span>
                    <span className="font-semibold">{evalResult.completeness.summary.components_with_docstrings}</span>
                  </div>
                  {evalResult.completeness.summary.criteria_percentages && (
                    <>
                      {Object.entries(evalResult.completeness.summary.criteria_percentages).map(([key, val]: [string, any]) => (
                        <div key={key} className="flex justify-between text-purple-200/70">
                          <span className="capitalize">{key.replace(/has_/g, "")}</span>
                          <span>{(val * 100).toFixed(0)}%</span>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              </div>

              {/* Helpfulness */}
              <div className="bg-gradient-to-br from-blue-500/20 to-cyan-500/20 backdrop-blur-lg rounded-xl p-6 border border-white/20">
                <h3 className="text-lg font-bold text-white mb-1">Helpfulness</h3>
                <p className="text-blue-200/60 text-xs mb-4">How useful are the docstrings? (LLM-judged)</p>
                <div className="text-4xl font-bold text-blue-300 mb-4">
                  {evalResult.helpfulness.summary.average_score.toFixed(2)}<span className="text-xl text-blue-200/50">/5</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between text-blue-200">
                    <span>Evaluated</span>
                    <span className="font-semibold">{evalResult.helpfulness.summary.total_components}</span>
                  </div>
                  <div className="flex justify-between text-blue-200">
                    <span>Min Score</span>
                    <span className="font-semibold">{evalResult.helpfulness.summary.min_score}</span>
                  </div>
                  <div className="flex justify-between text-blue-200">
                    <span>Max Score</span>
                    <span className="font-semibold">{evalResult.helpfulness.summary.max_score}</span>
                  </div>
                  <div className="flex justify-between text-blue-200">
                    <span>Skipped (no doc)</span>
                    <span className="font-semibold">{evalResult.helpfulness.summary.skipped_no_docstring}</span>
                  </div>
                  {evalResult.helpfulness.by_aspect && Object.keys(evalResult.helpfulness.by_aspect).length > 0 && (
                    <>
                      <div className="border-t border-white/10 mt-2 pt-2 text-xs text-blue-200/50 uppercase">By Aspect</div>
                      {Object.entries(evalResult.helpfulness.by_aspect).map(([aspect, data]: [string, any]) => (
                        <div key={aspect} className="flex justify-between text-blue-200/70">
                          <span className="capitalize">{aspect}</span>
                          <span>{data.average.toFixed(2)}/5</span>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              </div>

              {/* Truthfulness */}
              <div className="bg-gradient-to-br from-green-500/20 to-emerald-500/20 backdrop-blur-lg rounded-xl p-6 border border-white/20">
                <h3 className="text-lg font-bold text-white mb-1">Truthfulness</h3>
                <p className="text-green-200/60 text-xs mb-4">Do mentioned components actually exist?</p>
                <div className="text-4xl font-bold text-green-300 mb-4">
                  {(evalResult.truthfulness.summary.overall_accuracy * 100).toFixed(1)}%
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between text-green-200">
                    <span>Components Checked</span>
                    <span className="font-semibold">{evalResult.truthfulness.summary.total_components}</span>
                  </div>
                  <div className="flex justify-between text-green-200">
                    <span>Accurate</span>
                    <span className="font-semibold">{evalResult.truthfulness.summary.accurate_components}</span>
                  </div>
                  <div className="flex justify-between text-green-200">
                    <span>With Issues</span>
                    <span className="font-semibold">{evalResult.truthfulness.summary.components_with_issues}</span>
                  </div>
                  <div className="flex justify-between text-green-200">
                    <span>Total Mentions</span>
                    <span className="font-semibold">{evalResult.truthfulness.summary.total_mentions}</span>
                  </div>
                  <div className="flex justify-between text-green-200">
                    <span>Existing</span>
                    <span className="font-semibold">{evalResult.truthfulness.summary.existing_mentions}</span>
                  </div>
                  {evalResult.truthfulness.summary.issue_types && Object.keys(evalResult.truthfulness.summary.issue_types).length > 0 && (
                    <>
                      <div className="border-t border-white/10 mt-2 pt-2 text-xs text-green-200/50 uppercase">Issue Types</div>
                      {Object.entries(evalResult.truthfulness.summary.issue_types).map(([type, count]: [string, any]) => (
                        <div key={type} className="flex justify-between text-green-200/70">
                          <span className="capitalize">{type.replace(/_/g, " ")}</span>
                          <span className="px-2 py-0.5 bg-red-500/30 rounded-full text-xs text-red-200">{count}</span>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Language Breakdown */}
            {evalResult.completeness.by_language && Object.keys(evalResult.completeness.by_language).length > 0 && (
              <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 shadow-2xl">
                <h3 className="text-lg font-bold text-white mb-4">Scores by Language</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(evalResult.completeness.by_language).map(([lang, data]: [string, any]) => (
                    <div key={lang} className="bg-white/5 rounded-lg p-4 border border-white/10 text-center">
                      <div className="text-purple-300 font-semibold capitalize mb-1">{lang}</div>
                      <div className="text-2xl font-bold text-white">{(data.average * 100).toFixed(0)}%</div>
                      <div className="text-purple-200/50 text-xs">{data.total} components</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
        </div>
      </footer>
    </div>
  )
}
