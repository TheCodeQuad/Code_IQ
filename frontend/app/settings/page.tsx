"use client"

import { useState } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Code2,
  ArrowLeft,
  Settings,
  FileCode,
  Brain,
  Server,
  Save,
  RefreshCw,
  Trash2,
  AlertCircle,
  CheckCircle,
  Cpu,
  Zap,
} from "lucide-react"

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<"analysis" | "documentation" | "model" | "system">("analysis")
  
  // Analysis settings state
  const [languages, setLanguages] = useState(["python", "javascript"])
  const [enableGraphGen, setEnableGraphGen] = useState(true)
  const [enableEvaluation, setEnableEvaluation] = useState(true)
  const [parallelAgents, setParallelAgents] = useState(true)
  
  // Documentation settings state
  const [docStyle, setDocStyle] = useState("google")
  const [verbosity, setVerbosity] = useState("standard")
  const [includeExamples, setIncludeExamples] = useState(true)
  const [includeTypes, setIncludeTypes] = useState(true)
  
  // Model settings state
  const [modelProvider, setModelProvider] = useState("openai")
  const [temperature, setTemperature] = useState([0.3])
  const [maxTokens, setMaxTokens] = useState([2048])
  const [retryCount, setRetryCount] = useState([3])

  const languageOptions = [
    { value: "python", label: "Python", icon: "🐍" },
    { value: "javascript", label: "JavaScript", icon: "🟨" },
    { value: "typescript", label: "TypeScript", icon: "🟦" },
    { value: "java", label: "Java", icon: "☕" },
    { value: "go", label: "Go", icon: "🔵" },
    { value: "rust", label: "Rust", icon: "🦀" },
  ]

  const toggleLanguage = (lang: string) => {
    if (languages.includes(lang)) {
      setLanguages(languages.filter(l => l !== lang))
    } else {
      setLanguages([...languages, lang])
    }
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                <Settings className="w-5 h-5 text-primary-foreground" />
              </div>
              <span className="text-lg font-semibold text-foreground">Settings</span>
            </div>
          </div>
          <Button className="bg-foreground text-background hover:bg-foreground/90">
            <Save className="w-4 h-4 mr-2" />
            Save Changes
          </Button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
          <TabsList className="mb-8 bg-secondary">
            <TabsTrigger value="analysis" className="flex items-center gap-2">
              <Cpu className="w-4 h-4" />
              Analysis
            </TabsTrigger>
            <TabsTrigger value="documentation" className="flex items-center gap-2">
              <FileCode className="w-4 h-4" />
              Documentation
            </TabsTrigger>
            <TabsTrigger value="model" className="flex items-center gap-2">
              <Brain className="w-4 h-4" />
              Model & Agents
            </TabsTrigger>
            <TabsTrigger value="system" className="flex items-center gap-2">
              <Server className="w-4 h-4" />
              System
            </TabsTrigger>
          </TabsList>

          {/* Analysis Settings */}
          <TabsContent value="analysis">
            <div className="space-y-6">
              <Card className="border-border">
                <CardHeader>
                  <CardTitle>Language Support</CardTitle>
                  <CardDescription>Select which programming languages CodeIQ should analyze</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-3 gap-3">
                    {languageOptions.map((lang) => (
                      <button
                        type="button"
                        key={lang.value}
                        onClick={() => toggleLanguage(lang.value)}
                        className={`p-4 rounded-lg border transition-all ${
                          languages.includes(lang.value)
                            ? "border-primary bg-primary/5"
                            : "border-border hover:border-primary/50"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-2xl">{lang.icon}</span>
                          <span className="font-medium text-foreground">{lang.label}</span>
                          {languages.includes(lang.value) && (
                            <CheckCircle className="w-4 h-4 text-primary ml-auto" />
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card className="border-border">
                <CardHeader>
                  <CardTitle>Pipeline Configuration</CardTitle>
                  <CardDescription>Configure the analysis pipeline behavior</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <Label className="text-foreground">Enable Graph Generation</Label>
                      <p className="text-sm text-muted-foreground">Generate CFG, PDG, HPG, and GHG graphs for analysis</p>
                    </div>
                    <Switch checked={enableGraphGen} onCheckedChange={setEnableGraphGen} />
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <Label className="text-foreground">Enable Evaluation Framework</Label>
                      <p className="text-sm text-muted-foreground">Run quality metrics after documentation generation</p>
                    </div>
                    <Switch checked={enableEvaluation} onCheckedChange={setEnableEvaluation} />
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <Label className="text-foreground">Parallel Agent Execution</Label>
                      <p className="text-sm text-muted-foreground">Run agents concurrently for faster processing</p>
                    </div>
                    <Switch checked={parallelAgents} onCheckedChange={setParallelAgents} />
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Documentation Settings */}
          <TabsContent value="documentation">
            <div className="space-y-6">
              <Card className="border-border">
                <CardHeader>
                  <CardTitle>Documentation Style</CardTitle>
                  <CardDescription>Choose the default documentation format</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { value: "google", label: "Google Style", desc: "Python standard with Args, Returns, Raises" },
                      { value: "javadoc", label: "Javadoc", desc: "Java standard with @param, @return, @throws" },
                      { value: "jsdoc", label: "JSDoc", desc: "JavaScript standard with @param, @returns" },
                    ].map((style) => (
                      <button
                        type="button"
                        key={style.value}
                        onClick={() => setDocStyle(style.value)}
                        className={`p-4 rounded-lg border text-left transition-all ${
                          docStyle === style.value
                            ? "border-primary bg-primary/5"
                            : "border-border hover:border-primary/50"
                        }`}
                      >
                        <div className="font-medium text-foreground mb-1">{style.label}</div>
                        <div className="text-xs text-muted-foreground">{style.desc}</div>
                      </button>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card className="border-border">
                <CardHeader>
                  <CardTitle>Verbosity Level</CardTitle>
                  <CardDescription>Control the detail level of generated documentation</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { value: "short", label: "Short", desc: "Concise, one-line descriptions" },
                      { value: "standard", label: "Standard", desc: "Balanced detail with key information" },
                      { value: "detailed", label: "Detailed", desc: "Comprehensive with examples and notes" },
                    ].map((level) => (
                      <button
                        type="button"
                        key={level.value}
                        onClick={() => setVerbosity(level.value)}
                        className={`p-4 rounded-lg border text-left transition-all ${
                          verbosity === level.value
                            ? "border-primary bg-primary/5"
                            : "border-border hover:border-primary/50"
                        }`}
                      >
                        <div className="font-medium text-foreground mb-1">{level.label}</div>
                        <div className="text-xs text-muted-foreground">{level.desc}</div>
                      </button>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card className="border-border">
                <CardHeader>
                  <CardTitle>Additional Options</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <Label className="text-foreground">Include Usage Examples</Label>
                      <p className="text-sm text-muted-foreground">Generate example code snippets in docstrings</p>
                    </div>
                    <Switch checked={includeExamples} onCheckedChange={setIncludeExamples} />
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <Label className="text-foreground">Include Type Hints</Label>
                      <p className="text-sm text-muted-foreground">Add type annotations to parameters and returns</p>
                    </div>
                    <Switch checked={includeTypes} onCheckedChange={setIncludeTypes} />
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Model & Agent Settings */}
          <TabsContent value="model">
            <div className="space-y-6">
              <Card className="border-border">
                <CardHeader>
                  <CardTitle>LLM Provider</CardTitle>
                  <CardDescription>Select the language model provider for agent reasoning</CardDescription>
                </CardHeader>
                <CardContent>
                  <Select value={modelProvider} onValueChange={setModelProvider}>
                    <SelectTrigger className="w-full max-w-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai">
                        <div className="flex items-center gap-2">
                          <div className="w-4 h-4 rounded bg-chart-3 flex items-center justify-center">
                            <Zap className="w-2.5 h-2.5 text-white" />
                          </div>
                          OpenAI (GPT-4)
                        </div>
                      </SelectItem>
                      <SelectItem value="anthropic">
                        <div className="flex items-center gap-2">
                          <div className="w-4 h-4 rounded bg-chart-1 flex items-center justify-center">
                            <Brain className="w-2.5 h-2.5 text-white" />
                          </div>
                          Anthropic (Claude)
                        </div>
                      </SelectItem>
                      <SelectItem value="local">
                        <div className="flex items-center gap-2">
                          <div className="w-4 h-4 rounded bg-chart-2 flex items-center justify-center">
                            <Server className="w-2.5 h-2.5 text-white" />
                          </div>
                          Local Model (Ollama)
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </CardContent>
              </Card>

              <Card className="border-border">
                <CardHeader>
                  <CardTitle>Model Parameters</CardTitle>
                  <CardDescription>Fine-tune the LLM behavior</CardDescription>
                </CardHeader>
                <CardContent className="space-y-8">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <Label className="text-foreground">Temperature</Label>
                      <span className="text-sm text-muted-foreground font-mono">{temperature[0].toFixed(2)}</span>
                    </div>
                    <Slider
                      value={temperature}
                      onValueChange={setTemperature}
                      max={1}
                      step={0.05}
                      className="w-full"
                    />
                    <p className="text-xs text-muted-foreground">Lower values produce more deterministic outputs. Recommended: 0.2-0.4 for documentation.</p>
                  </div>

                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <Label className="text-foreground">Max Tokens</Label>
                      <span className="text-sm text-muted-foreground font-mono">{maxTokens[0]}</span>
                    </div>
                    <Slider
                      value={maxTokens}
                      onValueChange={setMaxTokens}
                      min={512}
                      max={4096}
                      step={256}
                      className="w-full"
                    />
                    <p className="text-xs text-muted-foreground">Maximum tokens per generation. Higher values allow longer documentation.</p>
                  </div>

                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <Label className="text-foreground">Agent Retry Count</Label>
                      <span className="text-sm text-muted-foreground font-mono">{retryCount[0]}</span>
                    </div>
                    <Slider
                      value={retryCount}
                      onValueChange={setRetryCount}
                      min={1}
                      max={5}
                      step={1}
                      className="w-full"
                    />
                    <p className="text-xs text-muted-foreground">Number of retry attempts if an agent fails.</p>
                  </div>
                </CardContent>
              </Card>

              <Card className="border-border">
                <CardHeader>
                  <CardTitle>API Configuration</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label className="text-foreground">API Key</Label>
                    <Input type="password" placeholder="sk-..." className="max-w-md" />
                    <p className="text-xs text-muted-foreground">Your API key is encrypted and stored securely.</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* System Settings */}
          <TabsContent value="system">
            <div className="space-y-6">
              <Card className="border-border">
                <CardHeader>
                  <CardTitle>System Status</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid md:grid-cols-2 gap-4">
                    {[
                      { name: "Pipeline Service", status: "healthy", latency: "23ms" },
                      { name: "Graph Database", status: "healthy", latency: "45ms" },
                      { name: "LLM Gateway", status: "healthy", latency: "120ms" },
                      { name: "Worker Pool", status: "healthy", latency: "8ms" },
                    ].map((service) => (
                      <div key={service.name} className="p-4 bg-secondary/50 rounded-lg border border-border/50">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-medium text-foreground">{service.name}</span>
                          <Badge className="bg-chart-3/10 text-chart-3 border border-chart-3/20">
                            <CheckCircle className="w-3 h-3 mr-1" />
                            {service.status}
                          </Badge>
                        </div>
                        <div className="text-sm text-muted-foreground">Latency: {service.latency}</div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card className="border-border">
                <CardHeader>
                  <CardTitle>Cache Management</CardTitle>
                  <CardDescription>Manage cached data and temporary files</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-lg">
                    <div>
                      <div className="font-medium text-foreground">Graph Cache</div>
                      <div className="text-sm text-muted-foreground">Cached graph representations: 234 MB</div>
                    </div>
                    <Button variant="outline" size="sm" className="border-border bg-transparent">
                      <Trash2 className="w-4 h-4 mr-2" />
                      Clear
                    </Button>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-lg">
                    <div>
                      <div className="font-medium text-foreground">LLM Response Cache</div>
                      <div className="text-sm text-muted-foreground">Cached model responses: 128 MB</div>
                    </div>
                    <Button variant="outline" size="sm" className="border-border bg-transparent">
                      <Trash2 className="w-4 h-4 mr-2" />
                      Clear
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card className="border-border border-destructive/20">
                <CardHeader>
                  <CardTitle className="text-destructive flex items-center gap-2">
                    <AlertCircle className="w-5 h-5" />
                    Danger Zone
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-destructive/5 rounded-lg border border-destructive/10">
                    <div>
                      <div className="font-medium text-foreground">Reset All Settings</div>
                      <div className="text-sm text-muted-foreground">Restore all settings to their default values</div>
                    </div>
                    <Button variant="outline" size="sm" className="border-destructive text-destructive hover:bg-destructive hover:text-white bg-transparent">
                      <RefreshCw className="w-4 h-4 mr-2" />
                      Reset
                    </Button>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-destructive/5 rounded-lg border border-destructive/10">
                    <div>
                      <div className="font-medium text-foreground">Delete All Projects</div>
                      <div className="text-sm text-muted-foreground">Permanently delete all projects and their data</div>
                    </div>
                    <Button variant="outline" size="sm" className="border-destructive text-destructive hover:bg-destructive hover:text-white bg-transparent">
                      <Trash2 className="w-4 h-4 mr-2" />
                      Delete
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
