/**
 * Backend API client for CodeIQ Python FastAPI backend.
 * All communication with the backend goes through this module.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ────────────────────────────────────────────────────────────

export interface AnalyzeRequest {
  repo_url: string;
  save_json?: boolean;
  include_source?: boolean;
}

export interface ComponentInfo {
  id: string;
  language: string;
  type: string;
  file_path: string;
  module_path: string;
  depends_on: string[];
  start_line: number;
  end_line: number;
  has_docstring: boolean;
  docstring: string;
  source_code?: string;
}

export interface AnalysisStats {
  total_components: number;
  functions: number;
  classes: number;
  methods: number;
  global_variables: number;
  components_with_docstrings: number;
  components_without_docstrings: number;
  total_dependencies: number;
  max_dependencies: number;
  avg_dependencies: number;
}

export interface AnalyzeResponse {
  success: boolean;
  repo_url: string;
  timestamp: string;
  stats: AnalysisStats;
  components: Record<string, ComponentInfo>;
  topological_order: string[];
  dfs_order: string[];
  dag: Record<string, string[]>;
  formatted_output?: string;
  output_file?: string;
  message?: string;
  documentation?: any[];
}

export interface RepoUploadRequest {
  repo_url: string;
  user_id: string;
}

export interface RepoUploadResponse {
  success: boolean;
  repo_id: string;
  repo_name: string;
  language: string;
  file_count: number;
  total_lines: number;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  output_dir: string;
  output_dir_exists: boolean;
}

export interface FileInfo {
  filename: string;
  size: number;
  created: string;
  modified: string;
}

export interface FilesResponse {
  output_dir: string;
  total_files: number;
  files: FileInfo[];
}

// ── API Functions ────────────────────────────────────────────────────

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.name = "ApiError";
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || body.error || detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

/** Health-check the backend */
export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`, {
    cache: "no-store",
  });
  return handleResponse<HealthResponse>(res);
}

/** Check if backend is reachable (returns true/false) */
export async function isBackendOnline(): Promise<boolean> {
  try {
    const health = await checkHealth();
    return health.status === "healthy";
  } catch {
    return false;
  }
}

/** Analyze a repository */
export async function analyzeRepo(
  request: AnalyzeRequest
): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return handleResponse<AnalyzeResponse>(res);
}

export async function uploadRepo(
  request: RepoUploadRequest
): Promise<RepoUploadResponse> {
  const res = await fetch(`${API_BASE}/api/repos/upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return handleResponse<RepoUploadResponse>(res);
}

/** Upload a ZIP file containing source code */
export async function uploadZipRepo(
  file: File,
  userId: string
): Promise<RepoUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch("/api/repos/upload-zip", {
    method: "POST",
    body: formData,
    // Don't set Content-Type header - browser will set it with boundary
  });
  return handleResponse<RepoUploadResponse>(res);
}

/** List all saved analysis files */
export async function listFiles(): Promise<FilesResponse> {
  const res = await fetch(`${API_BASE}/files`, {
    cache: "no-store",
  });
  return handleResponse<FilesResponse>(res);
}

/** Download a specific analysis file */
export async function downloadFile(filename: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/download/${encodeURIComponent(filename)}`);
  if (!res.ok) {
    throw new ApiError(res.status, `Failed to download ${filename}`);
  }
  return res.blob();
}

/** Delete a specific analysis file */
export async function deleteFile(
  filename: string
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/files/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
  return handleResponse(res);
}

/** Get backend root info */
export async function getBackendInfo(): Promise<any> {
  const res = await fetch(`${API_BASE}/`, {
    cache: "no-store",
  });
  return handleResponse(res);
}

export { ApiError, API_BASE };
