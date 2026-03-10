"use client"

import React, { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { signIn } from "next-auth/react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import {
  Code2,
  Eye,
  EyeOff,
  ArrowRight,
  Github,
  Mail,
  Lock,
  User,
  Sparkles,
  Network,
  Brain,
  FileText,
} from "lucide-react"

const GoogleIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" xmlns="http://www.w3.org/2000/svg">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
)

function FloatingShape({ className, delay = 0 }: { className?: string; delay?: number }) {
  return (
    <div
      className={`absolute rounded-full blur-3xl animate-float ${className}`}
      style={{ animationDelay: `${delay}s` }}
    />
  )
}

function FeatureIcon({ icon: Icon, label, color }: { icon: React.ComponentType<{ className?: string }>; label: string; color: string }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-xl bg-background/50 backdrop-blur-sm">
      <div className={`w-10 h-10 rounded-lg bg-${color}/20 flex items-center justify-center`}>
        <Icon className={`w-5 h-5 text-${color}`} />
      </div>
      <span className="text-sm font-medium text-foreground">{label}</span>
    </div>
  )
}

export default function SignupPage() {
  const router = useRouter()
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState("")

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError("")

    const formData = new FormData(e.currentTarget as HTMLFormElement)
    const name = formData.get("name") as string
    const email = formData.get("email") as string
    const password = formData.get("password") as string

    if (!name || !email || !password) {
      setError("All fields are required")
      setIsLoading(false)
      return
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters")
      setIsLoading(false)
      return
    }

    try {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.error || "Something went wrong")
        setIsLoading(false)
        return
      }

      // Redirect to login page — user must sign in after creating account
      router.push("/login?registered=true")
    } catch (err) {
      setError("Something went wrong. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden bg-foreground">
        <FloatingShape className="w-96 h-96 bg-primary/20 top-10 -left-20" delay={0} />
        <FloatingShape className="w-64 h-64 bg-chart-2/20 bottom-20 right-10" delay={2} />
        <FloatingShape className="w-80 h-80 bg-chart-3/20 top-1/2 left-1/3" delay={4} />
        <div className="absolute inset-0 grid-pattern opacity-10" />

        <div className="relative z-10 flex flex-col justify-between p-12 text-background">
          <Link href="/" className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-background flex items-center justify-center">
              <Code2 className="w-7 h-7 text-foreground" />
            </div>
            <span className="text-3xl font-bold">CodeIQ</span>
          </Link>

          <div className="max-w-md">
            <h1 className="text-5xl font-bold leading-tight mb-6 text-balance">
              Start documenting your code intelligently
            </h1>
            <p className="text-xl text-background/70 mb-8">
              Join thousands of developers using AI to understand and document their codebases.
            </p>

            <div className="space-y-3">
              <FeatureIcon icon={Network} label="Graph-based code understanding" color="chart-1" />
              <FeatureIcon icon={Brain} label="4 specialized AI agents" color="chart-2" />
              <FeatureIcon icon={FileText} label="Context-aware documentation" color="chart-3" />
            </div>
          </div>

          <div className="flex items-center gap-2 text-background/50 text-sm">
            <Sparkles className="w-4 h-4" />
            <span>Trusted by 10,000+ developers</span>
          </div>
        </div>
      </div>

      {/* Right Panel - Signup Form */}
      <div className="flex-1 flex items-center justify-center p-8 relative">
        <div className="absolute inset-0 dot-pattern opacity-50" />
        <FloatingShape className="w-64 h-64 bg-primary/5 top-10 right-10" delay={1} />

        <div className="w-full max-w-md relative z-10">
          <Link href="/" className="flex lg:hidden items-center gap-3 mb-8 justify-center">
            <div className="w-12 h-12 rounded-xl bg-foreground flex items-center justify-center">
              <Code2 className="w-7 h-7 text-background" />
            </div>
            <span className="text-3xl font-bold text-foreground">CodeIQ</span>
          </Link>

          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-foreground mb-2">Create your account</h2>
            <p className="text-muted-foreground">Get started with CodeIQ for free</p>
          </div>

          <Card className="border-border bg-card/50 backdrop-blur-sm">
            <CardContent className="p-8">
              <form onSubmit={handleSignup} className="space-y-5">
                {error && (
                  <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-600 text-sm">
                    {error}
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="name" className="text-foreground">Full Name</Label>
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input
                      id="name"
                      name="name"
                      type="text"
                      placeholder="John Doe"
                      className="pl-12 h-12 bg-background border-border rounded-xl"
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="email" className="text-foreground">Email</Label>
                  <div className="relative">
                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input
                      id="email"
                      name="email"
                      type="email"
                      placeholder="you@example.com"
                      className="pl-12 h-12 bg-background border-border rounded-xl"
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password" className="text-foreground">Password</Label>
                  <div className="relative">
                    <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input
                      id="password"
                      name="password"
                      type={showPassword ? "text" : "password"}
                      placeholder="Min. 6 characters"
                      className="pl-12 pr-12 h-12 bg-background border-border rounded-xl"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                <Button
                  type="submit"
                  className="w-full h-12 bg-foreground text-background hover:bg-foreground/90 rounded-xl text-lg group"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <span className="flex items-center gap-2">
                      <span className="w-5 h-5 border-2 border-background/30 border-t-background rounded-full animate-spin" />
                      Creating account...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      Create Account
                      <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                    </span>
                  )}
                </Button>
              </form>

              <div className="relative my-8">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-border" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-4 bg-card text-muted-foreground">Or continue with</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Button
                  variant="outline"
                  className="h-12 border-border bg-transparent rounded-xl"
                  onClick={() => signIn("github", { callbackUrl: "/" })}
                >
                  <Github className="w-5 h-5 mr-2" />
                  GitHub
                </Button>
                <Button
                  variant="outline"
                  className="h-12 border-border bg-transparent rounded-xl"
                  onClick={() => signIn("google", { callbackUrl: "/" })}
                >
                  <GoogleIcon />
                  <span className="ml-2">Google</span>
                </Button>
              </div>
            </CardContent>
          </Card>

          <p className="text-center mt-8 text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="text-foreground font-medium hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
