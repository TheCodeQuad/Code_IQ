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

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-zinc-900 to-black">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center gap-3 mb-4">
            <GitBranch className="w-12 h-12 text-purple-400" />
            <h1 className="text-5xl font-bold text-white">CodeIQ</h1>
          </div>
          <p className="text-xl text-purple-200">
            AI-Powered Repository Dependency Analyzer
          </p>
        </div>

        {/* Input Section */}
        <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 mb-8 shadow-2xl border border-white/20">
          <div className="flex flex-col gap-4">
            <div className="flex gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-purple-300 w-5 h-5" />
                <input
                  type="text"
                  placeholder="Enter GitHub Repository URL (e.g., https://github.com/user/repo)"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  onKeyPress={(e) => e.key === "Enter" && analyzeRepo()}
                  className="w-full pl-12 pr-4 py-4 bg-white/20 border border-purple-300/30 rounded-xl text-white placeholder-purple-200/50 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition"
                />
              </div>
              <button
                onClick={analyzeRepo}
                disabled={loading}
                className="px-8 py-4 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold rounded-xl hover:from-purple-700 hover:to-pink-700 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg hover:shadow-xl transform hover:scale-105"
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
            )}
          </div>
        </div>

        {/* Results Section */}
        {result && (
          <div className="space-y-6">
            {/* Stats Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-gradient-to-br from-purple-500/20 to-pink-500/20 backdrop-blur-lg rounded-xl p-6 border border-white/20">
                <div className="text-3xl font-bold text-white mb-1">
                  {result.stats.total_components}
                </div>
                <div className="text-purple-200 text-sm">Total Components</div>
              </div>
              <div className="bg-gradient-to-br from-blue-500/20 to-cyan-500/20 backdrop-blur-lg rounded-xl p-6 border border-white/20">
                <div className="text-3xl font-bold text-white mb-1">
                  {result.stats.functions}
                </div>
                <div className="text-blue-200 text-sm">Functions</div>
              </div>
              <div className="bg-gradient-to-br from-green-500/20 to-emerald-500/20 backdrop-blur-lg rounded-xl p-6 border border-white/20">
                <div className="text-3xl font-bold text-white mb-1">
                  {result.stats.classes}
                </div>
                <div className="text-green-200 text-sm">Classes</div>
              </div>
              <div className="bg-gradient-to-br from-orange-500/20 to-red-500/20 backdrop-blur-lg rounded-xl p-6 border border-white/20">
                <div className="text-3xl font-bold text-white mb-1">
                  {result.stats.methods}
                </div>
                <div className="text-orange-200 text-sm">Methods</div>
              </div>
            </div>

            {/* Success Message */}
            <div className="flex items-center justify-between bg-green-500/20 border border-green-500/50 rounded-xl p-4">
              <div className="flex items-center gap-2 text-green-200">
                <CheckCircle className="w-5 h-5" />
                <span>{result.message}</span>
              </div>
              <button
                onClick={downloadJSON}
                className="flex items-center gap-2 px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-white transition"
              >
                <Download className="w-4 h-4" />
                Download JSON
              </button>
            </div>

            {/* Tabs */}
            <div className="bg-white/10 backdrop-blur-lg rounded-2xl overflow-hidden border border-white/20 shadow-2xl">
              <div className="flex border-b border-white/20">
                <button
                  onClick={() => setActiveTab("formatted")}
                  className={`flex-1 px-6 py-4 font-semibold transition ${
                    activeTab === "formatted"
                      ? "bg-purple-600 text-white"
                      : "text-purple-200 hover:bg-white/5"
                  }`}
                >
                  <FileCode className="inline w-5 h-5 mr-2" />
                  Formatted Output
                </button>
                <button
                  onClick={() => setActiveTab("components")}
                  className={`flex-1 px-6 py-4 font-semibold transition ${
                    activeTab === "components"
                      ? "bg-purple-600 text-white"
                      : "text-purple-200 hover:bg-white/5"
                  }`}
                >
                  Components
                </button>
                <button
                  onClick={() => setActiveTab("dag")}
                  className={`flex-1 px-6 py-4 font-semibold transition ${
                    activeTab === "dag"
                      ? "bg-purple-600 text-white"
                      : "text-purple-200 hover:bg-white/5"
                  }`}
                >
                  DAG
                </button>
                <button
                  onClick={() => setActiveTab("stats")}
                  className={`flex-1 px-6 py-4 font-semibold transition ${
                    activeTab === "stats"
                      ? "bg-purple-600 text-white"
                      : "text-purple-200 hover:bg-white/5"
                  }`}
                >
                  Statistics
                </button>
              </div>

              <div className="p-6 max-h-[600px] overflow-y-auto">
                {activeTab === "formatted" && (
                  <pre className="text-purple-100 text-sm font-mono whitespace-pre-wrap">
                    {result.formatted_output}
                  </pre>
                )}

                {activeTab === "components" && (
                  <div className="space-y-4">
                    {Object.entries(result.components).map(([id, comp]: [string, any]) => (
                      <div
                        key={id}
                        className="bg-white/5 rounded-lg p-4 border border-white/10 hover:border-purple-500/50 transition"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="font-mono text-purple-300 font-semibold">
                            {id}
                          </div>
                          <span className="px-3 py-1 bg-purple-500/30 rounded-full text-xs text-purple-200">
                            {comp.type}
                          </span>
                        </div>
                        <div className="text-sm text-purple-200/70 mb-2">
                          {comp.file_path}
                        </div>
                        {comp.depends_on && comp.depends_on.length > 0 && (
                          <div className="mt-3">
                            <div className="text-xs text-purple-300 mb-1">Dependencies:</div>
                            <div className="flex flex-wrap gap-2">
                              {comp.depends_on.map((dep: string) => (
                                <span
                                  key={dep}
                                  className="px-2 py-1 bg-purple-600/30 rounded text-xs text-purple-200"
                                >
                                  {dep}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {activeTab === "dag" && (
                  <div className="space-y-3">
                    {Object.entries(result.dag)
                      .filter(([_, deps]) => (deps as any[]).length > 0)
                      .map(([id, deps]) => (
                        <div
                          key={id}
                          className="bg-white/5 rounded-lg p-4 border border-white/10"
                        >
                          <div className="font-mono text-purple-300 mb-2">{id}</div>
                          <div className="flex items-center gap-2 text-purple-200/70">
                            <span>→</span>
                            <div className="flex flex-wrap gap-2">
                              {(deps as string[]).map((dep) => (
                                <span
                                  key={dep}
                                  className="px-2 py-1 bg-purple-600/30 rounded text-xs"
                                >
                                  {dep}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                      ))}
                  </div>
                )}

                {activeTab === "stats" && (
                  <div className="grid grid-cols-2 gap-4">
                    {Object.entries(result.stats).map(([key, value]) => (
                      <div
                        key={key}
                        className="bg-white/5 rounded-lg p-4 border border-white/10"
                      >
                        <div className="text-2xl font-bold text-white mb-1">
                          {typeof value === "number" ? value.toLocaleString() : value}
                        </div>
                        <div className="text-purple-200 text-sm capitalize">
                          {key.replace(/_/g, " ")}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
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
  );
}