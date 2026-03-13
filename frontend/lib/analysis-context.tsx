"use client";

import React, { createContext, useContext, useState, useCallback, ReactNode } from "react";
import type { AnalyzeResponse, AnalysisStats, ComponentInfo } from "@/lib/api";

// ── Stored analysis record ───────────────────────────────────────────
export interface AnalysisRecord {
  id: string; // unique id (timestamp-based)
  repoUrl: string;
  repoName: string;
  timestamp: string;
  status: "completed" | "in-progress" | "failed" | "not-analyzed";
  language: string;
  stats?: AnalysisStats;
  components?: Record<string, ComponentInfo>;
  topologicalOrder?: string[];
  dfsOrder?: string[];
  dag?: Record<string, string[]>;
  formattedOutput?: string;
  outputFile?: string;
  documentation?: any[];
  message?: string;
  error?: string;
}

interface AnalysisContextType {
  analyses: AnalysisRecord[];
  currentAnalysis: AnalysisRecord | null;
  addAnalysis: (record: AnalysisRecord) => void;
  updateAnalysis: (id: string, updates: Partial<AnalysisRecord>) => void;
  getAnalysis: (id: string) => AnalysisRecord | undefined;
  setCurrentAnalysis: (record: AnalysisRecord | null) => void;
  removeAnalysis: (id: string) => void;
}

const AnalysisContext = createContext<AnalysisContextType | null>(null);

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [analyses, setAnalyses] = useState<AnalysisRecord[]>(() => {
    // Load from localStorage on init
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem("codeiq_analyses");
        return stored ? JSON.parse(stored) : [];
      } catch {
        return [];
      }
    }
    return [];
  });
  const [currentAnalysis, setCurrentAnalysis] = useState<AnalysisRecord | null>(null);

  const persist = useCallback((records: AnalysisRecord[]) => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("codeiq_analyses", JSON.stringify(records));
      } catch {
        // ignore storage errors
      }
    }
  }, []);

  const addAnalysis = useCallback(
    (record: AnalysisRecord) => {
      setAnalyses((prev) => {
        const next = [record, ...prev];
        persist(next);
        return next;
      });
    },
    [persist]
  );

  const updateAnalysis = useCallback(
    (id: string, updates: Partial<AnalysisRecord>) => {
      setAnalyses((prev) => {
        const next = prev.map((a) => (a.id === id ? { ...a, ...updates } : a));
        persist(next);
        return next;
      });
    },
    [persist]
  );

  const getAnalysis = useCallback(
    (id: string) => analyses.find((a) => a.id === id),
    [analyses]
  );

  const removeAnalysis = useCallback(
    (id: string) => {
      setAnalyses((prev) => {
        const next = prev.filter((a) => a.id !== id);
        persist(next);
        return next;
      });
    },
    [persist]
  );

  return (
    <AnalysisContext.Provider
      value={{
        analyses,
        currentAnalysis,
        addAnalysis,
        updateAnalysis,
        getAnalysis,
        setCurrentAnalysis,
        removeAnalysis,
      }}
    >
      {children}
    </AnalysisContext.Provider>
  );
}

export function useAnalysis() {
  const ctx = useContext(AnalysisContext);
  if (!ctx) {
    throw new Error("useAnalysis must be used within an AnalysisProvider");
  }
  return ctx;
}

// ── Helper: convert backend response to AnalysisRecord ──────────────
export function responseToRecord(
  response: AnalyzeResponse,
  repoUrl: string
): AnalysisRecord {
  const repoName = extractRepoName(repoUrl);
  return {
    id: `analysis_${Date.now()}`,
    repoUrl,
    repoName,
    timestamp: response.timestamp,
    status: response.success ? "completed" : "failed",
    language: detectPrimaryLanguage(response.components),
    stats: response.stats,
    components: response.components,
    topologicalOrder: response.topological_order,
    dfsOrder: response.dfs_order,
    dag: response.dag,
    formattedOutput: response.formatted_output,
    outputFile: response.output_file,
    documentation: response.documentation,
    message: response.message,
  };
}

function extractRepoName(url: string): string {
  const cleaned = url.replace(/\/+$/, "").replace(/\.git$/, "");
  return cleaned.split("/").pop() || "unknown";
}

function detectPrimaryLanguage(
  components?: Record<string, ComponentInfo>
): string {
  if (!components) return "Unknown";
  const langs: Record<string, number> = {};
  for (const comp of Object.values(components)) {
    langs[comp.language] = (langs[comp.language] || 0) + 1;
  }
  const sorted = Object.entries(langs).sort((a, b) => b[1] - a[1]);
  return sorted[0]?.[0] || "Unknown";
}
