"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import type {
  RepoSummary,
  RepoListResponse,
  RepoUploadResponse,
  GenerateResponse,
} from "@/lib/repo-types";

/**
 * React hook that manages the user's repository list.
 * Talks to the Next.js proxy routes (which forward to the FastAPI backend).
 */
export function useRepos() {
  const [repos, setRepos] = useState<RepoSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  // ── Fetch all repos for this user ──────────────────────────────────

  const fetchRepos = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch("/api/repos", { cache: "no-store" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      const data: RepoListResponse = await res.json();
      if (mountedRef.current) {
        setRepos(data.repos ?? []);
      }
    } catch (err: any) {
      if (mountedRef.current) {
        setError(err.message || "Failed to load repos");
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchRepos();
    return () => {
      mountedRef.current = false;
    };
  }, [fetchRepos]);

  // ── Upload (clone) a new repo ──────────────────────────────────────

  const uploadRepo = useCallback(
    async (repoUrl: string): Promise<RepoUploadResponse> => {
      const res = await fetch("/api/repos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || body.detail || `HTTP ${res.status}`);
      }
      const data: RepoUploadResponse = await res.json();
      // Refresh the list so the new repo shows up immediately
      await fetchRepos();
      return data;
    },
    [fetchRepos]
  );

  // ── Delete a repo ──────────────────────────────────────────────────

  const deleteRepo = useCallback(
    async (repoId: string) => {
      const res = await fetch(`/api/repos/${repoId}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || body.detail || `HTTP ${res.status}`);
      }
      // Optimistic remove
      setRepos((prev) => prev.filter((r) => r.id !== repoId));
    },
    []
  );

  // ── Start pipeline for a repo ──────────────────────────────────────

  const generateDocs = useCallback(
    async (repoId: string): Promise<GenerateResponse> => {
      const res = await fetch(`/api/repos/${repoId}/generate`, {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || body.detail || `HTTP ${res.status}`);
      }
      const data: GenerateResponse = await res.json();
      // Refresh to update status
      await fetchRepos();
      return data;
    },
    [fetchRepos]
  );

  return {
    repos,
    loading,
    error,
    fetchRepos,
    uploadRepo,
    deleteRepo,
    generateDocs,
  };
}
