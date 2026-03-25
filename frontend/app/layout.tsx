import React from "react"
import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'
import AuthProvider from '@/components/auth-provider'
import { AnalysisProvider } from '@/lib/analysis-context'
import './globals.css'

const _geist = Geist({ subsets: ["latin"] });
const _geistMono = Geist_Mono({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: 'CodeIQ - Agentic AI for Code Documentation',
  description: 'Context-aware code documentation powered by multi-agent AI systems with graph-based understanding',
  generator: 'v0.app',
  icons: {
    icon: '/CODEIQ_light1.png',
    apple: '/CODEIQ_light1.png',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={`font-sans antialiased`}>
        <AuthProvider>
          <AnalysisProvider>
            {children}
          </AnalysisProvider>
        </AuthProvider>
        <Analytics />
      </body>
    </html>
  )
}
