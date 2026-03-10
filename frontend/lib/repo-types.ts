/**
 * Types for repository data flowing between the Next.js frontend
 * and the FastAPI backend via the proxy API routes.
 */

// ── Status values ────────────────────────────────────────────────────

export type RepoStatus =
  | "pending"
  | "parsing"
  | "reading"
  | "searching"
  | "writing"
  | "verifying"
  | "evaluating"
  | "completed"
  | "failed";

// ── Sub-documents ────────────────────────────────────────────────────

export interface AgentLog {
  agent: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  started_at?: string;
  finished_at?: string;
  message?: string;
}

export interface EvaluationScores {
  accuracy?: number;
  completeness?: number;
  clarity?: number;
  consistency?: number;
  overall_score?: number;
}

// ── API shapes ───────────────────────────────────────────────────────

/** Lightweight row returned by GET /api/repos */
export interface RepoSummary {
  id: string;
  repo_name: string;
  repo_url?: string;
  language?: string;
  file_count: number;
  status: RepoStatus;
  progress_percent: number;
  current_agent?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  overall_score?: number;
}

/** Full document returned by GET /api/repos/[id] */
export interface RepoDetail extends RepoSummary {
  repo_local_path?: string;
  total_lines: number;
  agent_logs: AgentLog[];
  stats?: Record<string, any>;
  documentation?: any[];
  evaluation?: EvaluationScores;
  error_message?: string;
}

/** Payload for POST /api/repos (upload) */
export interface RepoUploadPayload {
  repo_url: string;
}

/** Response from POST /api/repos */
export interface RepoUploadResponse {
  success: boolean;
  repo_id: string;
  repo_name: string;
  language: string;
  file_count: number;
  total_lines: number;
}

/** Response from GET /api/repos */
export interface RepoListResponse {
  repos: RepoSummary[];
  total: number;
}

/** Response from POST /api/repos/[id]/generate */
export interface GenerateResponse {
  success: boolean;
  repo_id: string;
  message: string;
}

/** Response from GET /api/repos/[id]/status */
export interface RepoStatusResponse {
  repo_id: string;
  status: RepoStatus;
  progress_percent: number;
  current_agent?: string;
  agent_logs: AgentLog[];
  error_message?: string;
  stats?: Record<string, any>;
  completed_at?: string;
  updated_at?: string;
}
