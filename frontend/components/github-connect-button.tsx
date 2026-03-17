"use client"

import { useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useSession } from "next-auth/react"
import { Button } from "@/components/ui/button"
import { Github, CheckCircle2, Loader2 } from "lucide-react"
import { useGitHub } from "@/hooks/use-github"

interface GitHubConnectButtonProps {
  onConnected?: () => void
  variant?: "default" | "outline" | "secondary"
  size?: "sm" | "md" | "lg"
  showStatus?: boolean
}

export function GitHubConnectButton({
  onConnected,
  variant = "default",
  size = "md",
  showStatus = true,
}: GitHubConnectButtonProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { data: session } = useSession()
  const { authorizeGitHub, loading, error, isConnected } = useGitHub()
  const [isProcessing, setIsProcessing] = useState(false)

  // Handle OAuth callback
  useEffect(() => {
    const code = searchParams.get("code")
    const state = searchParams.get("state")

    if (code && session?.user?.id) {
      const processAuth = async () => {
        setIsProcessing(true)
        const success = await authorizeGitHub(code)
        if (success) {
          // Clear the URL params
          router.replace(window.location.pathname)
          onConnected?.()
        }
        setIsProcessing(false)
      }
      processAuth()
    }
  }, [searchParams, session?.user?.id, authorizeGitHub, router, onConnected])

  const handleConnect = () => {
    if (!session?.user?.id) {
      alert("Please sign in first")
      router.push("/login")
      return
    }

    // Redirect to GitHub OAuth
    const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID
    if (!clientId) {
      alert("GitHub OAuth is not configured")
      return
    }

    const redirectUri = `${window.location.origin}/dashboard`
    const scope = "user repo"
    const state = session.user.id

    const authUrl = new URL("https://github.com/login/oauth/authorize")
    authUrl.searchParams.set("client_id", clientId)
    authUrl.searchParams.set("redirect_uri", redirectUri)
    authUrl.searchParams.set("scope", scope)
    authUrl.searchParams.set("state", state)

    window.location.href = authUrl.toString()
  }

  if (isConnected && showStatus) {
    return (
      <div className="flex items-center gap-2">
        <CheckCircle2 className="w-5 h-5 text-emerald-500" />
        <span className="text-sm font-medium text-emerald-600">
          GitHub Connected
        </span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <Button
        onClick={handleConnect}
        disabled={isProcessing || loading}
        className={`${
          variant === "default"
            ? "bg-black hover:bg-gray-800 text-white"
            : variant === "outline"
              ? "border border-gray-300 text-gray-900"
              : ""
        }`}
        size={size}
      >
        {isProcessing || loading ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            Connecting...
          </>
        ) : (
          <>
            <Github className="w-4 h-4 mr-2" />
            Connect GitHub
          </>
        )}
      </Button>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  )
}
