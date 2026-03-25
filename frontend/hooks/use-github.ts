import { useState, useCallback, useEffect } from "react"
import { useSession } from "next-auth/react"
import { useRef } from "react"

interface GitHubRepository {
  github_repo_id: number
  owner: string
  name: string
  full_name: string
  description: string | null
  url: string
  clone_url: string
  private: boolean
  language?: string | null
  stars: number
  app_installed: boolean
  installation_id?: number | null
}

interface GitHubProfile {
  github_id: number
  github_login: string
  github_avatar_url?: string
}

const getBackendUrl = () => {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
}

export function useGitHub() {
  const { data: session } = useSession()
  const userId = session?.user?.id
  const [loading, setLoading] = useState(false)
  const [repoLoading, setRepoLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [repositories, setRepositories] = useState<GitHubRepository[]>([])
  const [profile, setProfile] = useState<GitHubProfile | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const isFetchingReposRef = useRef(false)
  const oauthCodeInFlightRef = useRef<string | null>(null)

  const getReposCacheKey = useCallback(() => {
    return userId ? `github_repos_${userId}` : null
  }, [userId])

  const getConnectionKey = useCallback(() => {
    return session?.user?.id ? `github_connected_${session.user.id}` : null
  }, [session?.user?.id])

  const persistConnection = useCallback((connected: boolean) => {
    const key = getConnectionKey()
    if (!key) return
    try {
      if (connected) {
        localStorage.setItem(key, "true")
      } else {
        localStorage.removeItem(key)
      }
    } catch {
      // ignore storage errors (private mode, etc.)
    }
  }, [getConnectionKey])

  // Restore cached connection status for instant cross-page UI update.
  useEffect(() => {
    const key = getConnectionKey()
    if (!key) return
    try {
      const cached = localStorage.getItem(key) === "true"
      if (cached) setIsConnected(true)
    } catch {
      // ignore storage errors
    }
  }, [getConnectionKey])

  // Restore cached repository list so modal can render immediately.
  useEffect(() => {
    const key = getReposCacheKey()
    if (!key) return
    try {
      const raw = localStorage.getItem(key)
      if (!raw) return
      const cached = JSON.parse(raw)
      if (Array.isArray(cached) && cached.length > 0) {
        setRepositories(cached)
      }
    } catch {
      // ignore bad cache
    }
  }, [getReposCacheKey])

  // Check if user is already connected to GitHub on mount
  useEffect(() => {
    if (!userId) return

    const checkConnection = async () => {
      try {
        const backendUrl = getBackendUrl()
        const response = await fetch(`${backendUrl}/api/github/repositories`, {
          method: "GET",
          headers: {
            "user-id": userId,
          },
        })

        if (response.ok) {
          const data = await response.json()
          // If backend reports connected, update local connection state immediately.
          const connected = Boolean(data.connected || data.profile)
          setIsConnected(connected)
          persistConnection(connected)

          if (Array.isArray(data.repositories) && data.repositories.length > 0) {
            setRepositories(data.repositories)
            const reposKey = getReposCacheKey()
            if (reposKey) {
              try {
                localStorage.setItem(reposKey, JSON.stringify(data.repositories))
              } catch {
                // ignore storage errors
              }
            }
          }

          if (data.profile) {
            setProfile({
              github_id: data.profile.github_id,
              github_login: data.profile.github_login,
            })
          } else if (!connected) {
            setProfile(null)
          }
        }
      } catch (err) {
        // User might not be connected yet, that's ok
        setIsConnected(false)
      }
    }

    checkConnection()
  }, [userId, persistConnection, getReposCacheKey])

  const initiateGitHubAuth = useCallback(() => {
    if (!userId) {
      setError("Please sign in before connecting GitHub")
      return
    }

    const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID
    if (!clientId) {
      setError("GitHub client ID not configured")
      return
    }

    const redirectUri = `${window.location.origin}${window.location.pathname}`
    const scope = "user repo"
    const state = `${Date.now()}`
    const authUrl = `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=${encodeURIComponent(scope)}&prompt=select_account&state=${encodeURIComponent(state)}`
    
    window.location.href = authUrl
  }, [userId])

  const authorizeGitHub = useCallback(async (code: string) => {
    if (!userId) {
      const msg = "User not authenticated"
      console.error("[authorizeGitHub]", msg)
      setError(msg)
      return false
    }

    if (!code || code.length < 10) {
      const msg = "Invalid authorization code"
      console.error("[authorizeGitHub]", msg)
      setError(msg)
      return false
    }

    setLoading(true)
    setError(null)

    try {
      const backendUrl = getBackendUrl()
      console.log("[authorizeGitHub] Backend URL:", backendUrl)
      console.log("[authorizeGitHub] Code length:", code.length)
      console.log("[authorizeGitHub] Sending code to backend...")
      const response = await fetch(`${backendUrl}/api/github/authorize`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "user-id": userId,
        },
        body: JSON.stringify({ code }),
      })

      console.log("[authorizeGitHub] Response status:", response.status)
      console.log("[authorizeGitHub] Response headers:", {
        contentType: response.headers.get("content-type"),
      })

      // Try to parse response text first
      const responseText = await response.text()
      console.log("[authorizeGitHub] Response body:", responseText.substring(0, 200))

      if (!response.ok) {
        // Try to parse as JSON, fall back to text
        let errorMsg = "Authorization failed"
        try {
          const data = JSON.parse(responseText)
          errorMsg = data.detail || data.message || errorMsg
        } catch {
          errorMsg = responseText || errorMsg
        }
        throw new Error(errorMsg)
      }

      // Parse JSON response
      const data = JSON.parse(responseText)
      console.log("[authorizeGitHub] Authorization successful:", data.github_login)
      setProfile({
        github_id: data.github_id,
        github_login: data.github_login,
      })
      setIsConnected(true)
      persistConnection(true)

      return true
    } catch (err: any) {
      const message = err.message || "Authorization failed"
      console.error("[authorizeGitHub] Error:", message)
      setError(message)
      setIsConnected(false)
      persistConnection(false)
      return false
    } finally {
      setLoading(false)
    }
  }, [userId, persistConnection])

  const fetchRepositories = useCallback(async (options?: { silent?: boolean }) => {
    if (!userId) {
      setError("User not authenticated")
      return
    }

    if (isFetchingReposRef.current) {
      return
    }

    isFetchingReposRef.current = true

    const silent = options?.silent === true
    if (!silent) {
      setRepoLoading(true)
      setError(null)
    }

    try {
      const backendUrl = getBackendUrl()
      const response = await fetch(`${backendUrl}/api/github/repositories`, {
        method: "GET",
        headers: {
          "user-id": userId,
        },
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Failed to fetch repositories")
      }

      const data = await response.json()
      setRepositories(data.repositories || [])
      const reposKey = getReposCacheKey()
      if (reposKey) {
        try {
          localStorage.setItem(reposKey, JSON.stringify(data.repositories || []))
        } catch {
          // ignore storage errors
        }
      }
      const connected = Boolean(data.connected || data.profile)
      setIsConnected(connected)
      persistConnection(connected)
      if (data.profile) {
        setProfile({
          github_id: data.profile.github_id,
          github_login: data.profile.github_login,
        })
      }
    } catch (err: any) {
      const message = err.message || "Failed to fetch repositories"
      if (!silent) {
        setError(message)
      }
    } finally {
      isFetchingReposRef.current = false
      if (!silent) {
        setRepoLoading(false)
      }
    }
  }, [userId, persistConnection, getReposCacheKey])

  // Handle OAuth callback on any page that uses this hook.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get("code")
    if (!code) return

    if (!userId) {
      setError("Please sign in first, then connect GitHub again")
      return
    }

    if (oauthCodeInFlightRef.current === code) {
      return
    }
    oauthCodeInFlightRef.current = code

    const processCode = async () => {
      try {
        const ok = await authorizeGitHub(code)

        if (ok) {
          await fetchRepositories({ silent: true })
        }
      } finally {
        // Remove one-time OAuth params from URL regardless of outcome.
        params.delete("code")
        params.delete("state")
        const nextQuery = params.toString()
        const cleanUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`
        window.history.replaceState({}, document.title, cleanUrl)
        oauthCodeInFlightRef.current = null
      }
    }

    processCode()
  }, [userId, authorizeGitHub, fetchRepositories])

  const getAppInstallUrl = useCallback(async (repositoryId?: number): Promise<string | null> => {
    if (!userId) {
      setError("User not authenticated")
      return null
    }

    setLoading(true)
    setError(null)

    try {
      const backendUrl = getBackendUrl()
      const response = await fetch(`${backendUrl}/api/github/app/install-url`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "user-id": userId,
        },
        body: JSON.stringify(repositoryId ? { repository_id: repositoryId } : {}),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Failed to get install URL")
      }

      const data = await response.json()
      return data.install_url
    } catch (err: any) {
      const message = err.message || "Failed to get install URL"
      setError(message)
      return null
    } finally {
      setLoading(false)
    }
  }, [userId])

  const disconnectGitHub = useCallback(async (): Promise<boolean> => {
    if (!userId) {
      setError("User not authenticated")
      return false
    }

    setLoading(true)
    setError(null)

    try {
      const backendUrl = getBackendUrl()
      const response = await fetch(`${backendUrl}/api/github/disconnect`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "user-id": userId,
        },
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Failed to disconnect GitHub")
      }

      setIsConnected(false)
      setProfile(null)
      setRepositories([])
      persistConnection(false)

      const reposKey = getReposCacheKey()
      if (reposKey) {
        try {
          localStorage.removeItem(reposKey)
        } catch {
          // ignore storage errors
        }
      }

      return true
    } catch (err: any) {
      const message = err.message || "Failed to disconnect GitHub"
      setError(message)
      return false
    } finally {
      setLoading(false)
    }
  }, [userId, persistConnection, getReposCacheKey])

  const createPR = useCallback(
    async (
      repoId: string,
      githubRepoFullName: string,
      installationId: number,
      commitMessage?: string,
      prTitle?: string,
      prBody?: string
    ) => {
      if (!userId) {
        setError("User not authenticated")
        return null
      }

      setLoading(true)
      setError(null)

      try {
        const backendUrl = getBackendUrl()
        const response = await fetch(`${backendUrl}/api/github/pr/create`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "user-id": userId,
          },
          body: JSON.stringify({
            repo_id: repoId,
            github_repo_full_name: githubRepoFullName,
            installation_id: installationId,
            commit_message:
              commitMessage || "docs: Add generated docstrings via CodeIQ",
            pr_title:
              prTitle || "docs: Add comprehensive docstrings",
            pr_body:
              prBody ||
              "This PR adds comprehensive docstrings generated by CodeIQ",
          }),
        })

        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "Failed to create PR")
        }

        const data = await response.json()
        return data
      } catch (err: any) {
        const message = err.message || "Failed to create PR"
        setError(message)
        return null
      } finally {
        setLoading(false)
      }
    },
    [userId]
  )

  return {
    loading,
    repoLoading,
    error,
    repositories,
    profile,
    initiateGitHubAuth,
    authorizeGitHub,
    fetchRepositories,
    getAppInstallUrl,
    disconnectGitHub,
    createPR,
    isConnected,
  }
}
