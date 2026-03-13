"use client";

import { useState, useRef, type FormEvent } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Loader2, Github, AlertCircle } from "lucide-react";

interface UploadRepoDialogProps {
  /** Called with the GitHub URL when the user submits. Should return a promise. */
  onUpload: (repoUrl: string) => Promise<any>;
}

export function UploadRepoDialog({ onUpload }: UploadRepoDialogProps) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const GITHUB_RE = /^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+(\.git)?$/;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    const trimmed = url.trim();
    if (!trimmed) {
      setError("Please enter a repository URL");
      return;
    }
    if (!GITHUB_RE.test(trimmed)) {
      setError("Enter a valid GitHub repository URL (e.g. https://github.com/owner/repo)");
      return;
    }

    try {
      setLoading(true);
      await onUpload(trimmed);
      setUrl("");
      setOpen(false);
    } catch (err: any) {
      setError(err.message || "Failed to upload repository");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (v) {
          setError(null);
          setTimeout(() => inputRef.current?.focus(), 100);
        }
      }}
    >
      <DialogTrigger asChild>
        <Button className="bg-foreground text-background hover:bg-foreground/90 h-10 px-5 text-sm">
          <Plus className="w-4 h-4 mr-2" />
          New Project
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Github className="w-5 h-5" />
            Add Repository
          </DialogTitle>
          <DialogDescription>
            Paste a public GitHub repository URL. We&apos;ll clone it and you can
            then run the documentation pipeline.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="mt-2 space-y-4">
          <div className="space-y-2">
            <Input
              ref={inputRef}
              placeholder="https://github.com/owner/repo"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={loading}
              className="h-11"
            />
            {error && (
              <p className="flex items-center gap-1.5 text-sm text-red-500">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </p>
            )}
          </div>

          <div className="flex justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Cloning…
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4 mr-2" />
                  Add Project
                </>
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
