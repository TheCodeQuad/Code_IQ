'use client';

import { useState, useEffect } from 'react';
import { FolderGit2, CheckCircle2, Loader2 } from 'lucide-react';

export interface LogEntry {
  message: string;
  type: 'info' | 'process' | 'success' | string;
}

export interface RepositoryToDAGProps {
  isActive?: boolean;
  logs: LogEntry[];
  progress: number;
  isComplete: boolean;
  onComplete?: () => void;
}

export function RepositoryToDAG({
  isActive = true,
  logs = [],
  progress = 0,
  isComplete = false,
  onComplete,
}: RepositoryToDAGProps) {
  const [logFadeOut, setLogFadeOut] = useState(false);

  useEffect(() => {
    if (!isActive) {
      setLogFadeOut(false);
      return;
    }

    if (isComplete) {
      const timer1 = setTimeout(() => {
        setLogFadeOut(true);
        const timer2 = setTimeout(() => {
          if (onComplete) onComplete();
        }, 800);

        return () => clearTimeout(timer2);
      }, 600);

      return () => clearTimeout(timer1);
    }

    setLogFadeOut(false);
  }, [isComplete, isActive, onComplete]);

  if (!isActive) return null;

  return (
    <div className={`fixed inset-0 flex items-center justify-start bg-background overflow-hidden pipeline-grid pl-16 lg:pl-24 z-[100] transition-opacity duration-300 ${logFadeOut ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}>
      <div
        className={`relative z-10 w-full max-w-5xl flex items-center gap-12 transition-all duration-500 ease-out ${
          logFadeOut ? 'opacity-0 scale-95 -translate-y-4' : 'opacity-100 scale-100 translate-y-0'
        }`}
      >
        <div className="flex-1 max-w-2xl">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20 mb-4">
              <FolderGit2 className="w-7 h-7 text-primary" />
            </div>
            <h1 className="text-2xl font-semibold text-foreground mb-2">Architecture Ingestion</h1>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              Initializing analytical engine. Mapping your repository&apos;s logic structure.
            </p>
          </div>

          <div className="terminal-window overflow-hidden border border-border bg-card rounded-lg shadow-sm">
            <div className="terminal-header flex items-center px-4 py-2 border-b border-border bg-muted/50">
              <div className="w-3 h-3 rounded-full bg-[#ff5f57] mr-2" />
              <div className="w-3 h-3 rounded-full bg-[#febc2e] mr-2" />
              <div className="w-3 h-3 rounded-full bg-[#28c840]" />
              <span className="ml-3 text-xs text-muted-foreground font-mono">repository-scanner</span>
              <div className="ml-auto flex items-center gap-2">
                {!isComplete && <Loader2 className="w-3 h-3 text-muted-foreground animate-spin" />}
                <span className="text-xs text-muted-foreground font-mono">{logs.length} events</span>
              </div>
            </div>

            <div className="terminal-body space-y-2 p-4 h-72 max-h-72 overflow-y-auto bg-card">
              {logs.length > 0 ? (
                logs.map((log, index) => {
                  if (!log) return null;
                  const logType = log.type || 'info';
                  return (
                    <div
                      key={index}
                      className="flex items-start gap-2 animate-fade-slide-in"
                      style={{ animationDelay: '0ms' }}
                    >
                      <span
                        className={`mt-0.5 ${
                          logType === 'success' || (index === logs.length - 1 && isComplete)
                            ? 'text-emerald-500'
                            : logType === 'process'
                              ? 'text-primary'
                              : 'text-muted-foreground'
                        }`}
                      >
                        {logType === 'success' || (index === logs.length - 1 && isComplete) ? (
                          <CheckCircle2 className="w-3.5 h-3.5" />
                        ) : (
                          <span className="text-xs">{'>'}</span>
                        )}
                      </span>
                      <span
                        className={`text-sm font-mono ${
                          logType === 'success' || (index === logs.length - 1 && isComplete)
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : 'text-foreground/80'
                        }`}
                      >
                        {log.message || ''}
                      </span>
                    </div>
                  );
                })
              ) : (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span className="text-sm font-mono">Initializing...</span>
                </div>
              )}

              {!isComplete && logs.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground text-xs">{'>'}</span>
                  <span className="w-2 h-4 bg-primary animate-pulse" />
                </div>
              )}
            </div>
          </div>

          <div className="mt-4">
            <div className="h-1 bg-secondary rounded-full overflow-hidden">
              <div className="h-full bg-primary transition-all duration-300 ease-out" style={{ width: `${progress}%` }} />
            </div>
            <div className="flex justify-between mt-2">
              <span className="text-xs text-muted-foreground">{isComplete ? 'Complete' : 'Scanning repository...'}</span>
              <span className="text-xs text-muted-foreground font-mono">{Math.round(progress)}%</span>
            </div>
          </div>
        </div>

        <div className="hidden lg:flex flex-col items-end justify-center">
          <div className="text-right">
            <span className="text-[140px] font-bold leading-none text-primary/10 select-none" style={{ fontFamily: 'var(--font-mono)' }}>
              01
            </span>
            <p className="text-sm font-medium tracking-[0.3em] text-muted-foreground/60 uppercase mt-2">Analysis Phase</p>
          </div>
        </div>
      </div>
    </div>
  );
}
