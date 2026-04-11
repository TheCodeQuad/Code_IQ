"use client"

import { useState, useEffect, useMemo } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useSession } from "next-auth/react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import CardNav from "@/components/ui/card-nav"
import RadialOrbitalTimeline from "@/components/RadialOrbitalTimeline"
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
  "function compile(src) {",
  "  const tokens = lex(src)",
  "  return parse(tokens)",
  "impl CodeGraph {",
  "  fn new() -> Self {",
  "    Self { nodes: vec![] }",
  "const pipeline = async () =>",
  "  await Promise.all(tasks)",
  "SELECT * FROM graphs",
]

function SpatialZoomCode() {
  // Seeded random for consistent positions (avoids hydration mismatch)
  const seededRandom = (seed: number) => {
    const x = Math.sin(seed * 9999) * 10000
    return x - Math.floor(x)
  }

  // Keep generated style values stable between SSR and client hydration.
  const items = useMemo(() => {
    const fmt = (n: number, digits = 3) => Number(n.toFixed(digits))

    return Array.from({ length: 25 }, (_, i) => {
      // Random angle for circular distribution (full 360 degrees)
      const angle = seededRandom(i * 7.3) * Math.PI * 2
      // Random distance from center (varying radius)
      const distance = 20 + seededRandom(i * 3.7) * 50 // 20-70 units from center
      // Convert polar to cartesian
      const x = fmt(Math.cos(angle) * distance)
      const y = fmt(Math.sin(angle) * distance * 0.6) // Slightly squashed vertically
      // Random delay spread across the animation duration
      const delay = fmt(seededRandom(i * 5.1) * 18)
      // Random duration for variety (slower)
      const duration = fmt(20 + seededRandom(i * 2.9) * 12) // 20-32s

      return {
        snippet: codeSnippets[i % codeSnippets.length],
        x,
        y,
        delay,
        duration,
      }
    })
  }, [])

  return (
    <div 
      className="absolute inset-0 overflow-hidden pointer-events-none"
      style={{ 
        perspective: '620px',
        perspectiveOrigin: '50% 50%',
      }}
    >
      <div 
        className="absolute inset-0"
        style={{ 
          transformStyle: 'preserve-3d',
        }}
      >
        {items.map((item, i) => (
          <div
            key={`code-${i}`}
            className="absolute left-1/2 top-1/2 text-[10px] md:text-xs font-mono text-foreground/30 whitespace-nowrap"
            style={{
              animationName: 'spatialZoom',
              animationDuration: `${item.duration}s`,
              animationTimingFunction: 'linear',
              animationIterationCount: 'infinite',
              animationDelay: `-${item.delay}s`,
              willChange: 'transform, opacity',
              backfaceVisibility: 'hidden',
              ['--tx' as string]: `${item.x}vw`,
              ['--ty' as string]: `${item.y}vh`,
            }}
          >
            {item.snippet}
          </div>
        ))}
      </div>
    </div>
  )
}

const heroTexts = [
  ["Structured docs", "from codebases"],
  ["Agentic AI", "Code Documentation"],
  ["AI that understands", "your codebase"],
  ["Turn complex code", "into clear docs"],
]

const LANDING_GRADIENT = `
  radial-gradient(ellipse 80% 60% at 20% 80%, rgba(245, 208, 200, 0.6) 0%, transparent 50%),
  radial-gradient(ellipse 70% 50% at 80% 30%, rgba(240, 200, 150, 0.5) 0%, transparent 50%),
  radial-gradient(ellipse 60% 40% at 10% 20%, rgba(235, 220, 230, 0.4) 0%, transparent 40%),
  radial-gradient(ellipse 90% 70% at 50% 50%, rgba(255, 250, 245, 0.8) 0%, transparent 60%),
  linear-gradient(to bottom right, #fdf8f5, #fef9f3, #fdf6f0)
`

function SliceSlider() {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [showFirst, setShowFirst] = useState(true)
  const [showSecond, setShowSecond] = useState(true)

  useEffect(() => {
    const interval = setInterval(() => {
      // Hide current lines
      setShowFirst(false)
      setTimeout(() => setShowSecond(false), 100)
      
      // Change index and show new lines
      setTimeout(() => {
        setCurrentIndex((prev) => (prev + 1) % heroTexts.length)
        setShowFirst(true)
        setTimeout(() => setShowSecond(true), 150)
      }, 500)
    }, 3500)
    
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex flex-col items-center">
      {/* First line */}
      <div className="h-[40px] md:h-[60px] lg:h-[72px] overflow-hidden">
        <div
          className={`transition-transform duration-400 ease-[cubic-bezier(0.77,0,0.175,1)] ${
            showFirst ? "translate-y-0" : "translate-y-full"
          }`}
        >
          <span className="block text-foreground font-extrabold tracking-tighter" style={{ textShadow: '0 2px 10px rgba(0,0,0,0.05)' }}>{heroTexts[currentIndex][0]}</span>
        </div>
      </div>
      
      {/* Second line */}
      <div className="h-[44px] md:h-[64px] lg:h-[76px] overflow-hidden -mt-1">
        <div
          className={`transition-transform duration-400 ease-[cubic-bezier(0.77,0,0.175,1)] ${
            showSecond ? "translate-y-0" : "translate-y-full"
          }`}
        >
          <span className="block font-extrabold tracking-tighter bg-gradient-to-r from-[#e81cff] via-[#9d4edd] to-[#8b5cf6] bg-clip-text text-transparent pb-3">
            {heroTexts[currentIndex][1]}
          </span>
        </div>
      </div>
    </div>
  )
}

function HeroVideoCircle() {
  const codeLines = [
    "useEffect(() => {",
    "  const interval = setInterval(() => {",
    "  // Hide current lines",
    "  setShowFirst(false)",
    "  setTimeout(() => setShowSecond(false), 100)",
    "",
    "  // Change index and show new lines",
    "  setTimeout(() => {",
    "    setCurrentIndex((prev) => (prev + 1) % heroTexts.length)",
    "    setShowFirst(true)",
    "    setTimeout(() => setShowSecond(true), 150)",
    "  }, 500)",
    "}, 3500)",
    "",
    "return () => clearInterval(interval)",
    "}, [])"
  ];

  const [visibleLines, setVisibleLines] = useState(0);

  useEffect(() => {
    // Typewriter effect logic
    const inter = setInterval(() => {
      setVisibleLines(v => {
        if (v >= codeLines.length + 5) return 0;
        return v + 1;
      });
    }, 300);
    return () => clearInterval(inter);
  }, []);

  return (
    <div className="relative w-[280px] h-[280px] md:w-[400px] md:h-[400px] mx-auto -mb-20 md:-mb-28 z-10 bg-transparent">
      {/* Circular video mask */}
      <div className="absolute inset-0 rounded-full overflow-hidden">
        {/* 
          NOTE FOR USER: 
          Place your video file here: "frontend/public/hero-video.mp4" 
        */}
        <video 
          src="/hero-video.mp4" 
          autoPlay loop muted playsInline
          className="absolute inset-0 w-full h-full object-cover scale-[1.02]"
        />
      </div>
      
      {/* Glowing text overlay - sibling to video so it can escape the clipped bounds */}
      <div className="absolute inset-0 p-4 md:-ml-8 md:pr-12 flex flex-col justify-center pointer-events-none z-30">
        <div className="text-[10px] md:text-xs text-white font-semibold leading-tight text-right scale-x-[-1] origin-center w-[120%]" style={{ fontFamily: "Consolas, 'Courier New', monospace", opacity: 0.7, textShadow: '0 0 10px rgba(255,255,255,0.8), 0 0 20px rgba(255,255,255,0.6), 0 0 30px rgba(255,255,255,0.4)' }}>
          {codeLines.slice(0, Math.min(visibleLines, codeLines.length)).map((line, i) => (
            <div key={i} className="animate-in fade-in zoom-in slide-in-from-bottom-1 duration-300">
              {line}
            </div>
          ))}
          {/* Blinking cursor */}
          {visibleLines < codeLines.length && (
            <div className="inline-block w-1.5 h-3 bg-white ml-1 animate-pulse shadow-[0_0_8px_rgba(255,255,255,1)]" />
          )}
        </div>
      </div>
    </div>
  );
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

  const timelineData = [
    {
      id: 1,
      title: "Upload Source Code",
      date: "Phase 1",
      content: "Upload your repository, and let CodeIQ establish the foundational structure for analysis.",
      category: "Ingestion",
      icon: Terminal,
      relatedIds: [2],
      status: "completed" as const,
      energy: 20
    },
    {
      id: 2,
      title: "Build Graphs",
      date: "Phase 2",
      content: "CodeIQ navigates the codebase and constructs CFG and PDG graphs for deep structural understanding.",
      category: "Processing",
      icon: Network,
      relatedIds: [1, 3],
      status: "in-progress" as const,
      energy: 40
    },
    {
      id: 3,
      title: "Agent Pipeline",
      date: "Phase 3",
      content: "Agents reason over the generated graphs, extracting deep context to formulate comprehensive insights.",
      category: "Reasoning",
      icon: Brain,
      relatedIds: [2, 4],
      status: "pending" as const,
      energy: 60
    },
    {
      id: 4,
      title: "Generate Docs",
      date: "Phase 4",
      content: "Our writing agents compile the gathered insights into detailed, intelligent, and context-aware documentation.",
      category: "Output",
      icon: FileText,
      relatedIds: [3, 5],
      status: "pending" as const,
      energy: 80
    },
    {
      id: 5,
      title: "Quality Metrics",
      date: "Phase 5",
      content: "The final step evaluates the generated output against truthfulness and helpfulness metrics.",
      category: "Verification",
      icon: BarChart3,
      relatedIds: [4],
      status: "pending" as const,
      energy: 100
    }
  ];

  const router = useRouter();

  return (
    <div className="min-h-screen relative overflow-hidden bg-gradient-to-b from-[#e897c6] via-[#fff8fc] to-[#f1b9ff]">
      {/* Background */}
      <div className="fixed inset-0 grid-pattern pointer-events-none opacity-50" />

      {/* Navigation */}
      <CardNav
        logo={
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-foreground flex items-center justify-center">
              <Code2 className="w-4 h-4 text-background" />
            </div>
            <span className="text-xl font-bold text-foreground">CodeIQ</span>
          </div>
        }
        middleContent={
          <>
            {["Features", "Pipeline", "Agents", "Docs"].map((item) => (
              <Link
                key={item}
                href={`#${item.toLowerCase()}`}
                className="px-4 py-2 rounded-md text-base text-stone-600 hover:text-stone-900 transition-all font-medium"
              >
                {item}
              </Link>
            ))}
          </>
        }
        rightContent={
          <>
            {isSignedIn ? (
              <div className="flex items-center gap-2 px-4 py-2 rounded-md bg-secondary text-base text-muted-foreground mr-1">
                <User className="w-5 h-5" />
                <span className="max-w-[160px] truncate">{session?.user?.email}</span>
              </div>
            ) : (
              <Link href="/login">
                <Button variant="ghost" className="text-stone-600 hover:text-stone-900 h-10 px-4 text-base mr-1 font-medium">Sign In</Button>
              </Link>
            )}
          </>
        }
        baseColor="#ffffff99"
        buttonBgColor="#111827"
        buttonTextColor="#ffffff"
        className="backdrop-blur-md border border-black/5"
        buttonText={isSignedIn ? "Dashboard" : "Get Started"}
        onButtonClick={() => router.push(getStartedHref)}
      />

      {/* Hero Section - Full Screen */}
      <section 
        className="min-h-screen pt-24 pb-10 px-6 relative flex flex-col items-center justify-center overflow-hidden"
      >
        {/* BIG background text */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-0">
          <h1 className="text-[20vw] md:text-[24vw] font-bold text-white opacity-50 whitespace-nowrap select-none tracking-tighter mix-blend-overlay" style={{ fontFamily: "Arial, Helvetica, sans-serif" }}>
            CODEIQ
          </h1>
        </div>

        <div className="max-w-4xl mx-auto text-center relative z-10 w-full mt-2">
          
          {/* New Circular Video Component! */}
          <HeroVideoCircle />

          <div className="text-6xl md:text-7xl lg:text-8xl font-bold text-foreground leading-[1.1] tracking-tight relative z-20 pointer-events-none -mt-16 md:-mt-24 flex flex-col items-center">
            <span className="block text-foreground font-bold tracking-tighter" style={{ fontFamily: "Arial, Helvetica, sans-serif", textShadow: '0 2px 10px rgba(0,0,0,0.05)' }}>Structured docs</span>
            <span className="block font-bold tracking-tighter text-[#dc2d98] pb-3 -mt-1 md:-mt-2" style={{ fontFamily: "Arial, Helvetica, sans-serif" }}>
              from codebases
            </span>
          </div>
          
        
          
          <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-4 relative z-30">
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
          
        </div>
      </section>

      {/* Pipeline Section replaced by Orbital Timeline */}
      <section id="pipeline" className="min-h-screen py-20 px-6 relative flex items-center justify-center">
        <RadialOrbitalTimeline timelineData={timelineData} />
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
        </div>
      </footer>
    </div>
  )
}