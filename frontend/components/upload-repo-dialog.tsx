"use client";

import { useState, useRef, type FormEvent, type ChangeEvent } from "react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Plus, Loader2, Github, AlertCircle, Archive } from "lucide-react";
import { GitHubRepositorySelector } from "@/components/github-repository-selector";

interface UploadRepoDialogProps {
  /** Called with the GitHub URL when the user submits. Should return a promise. */
  onUpload: (repoUrl: string) => Promise<any>;
  /** Called when a ZIP file is uploaded. Should return a promise. */
  onZipUpload?: (file: File, userId: string) => Promise<any>;
  /** Current user ID for ZIP uploads */
  userId?: string;
}

export function UploadRepoDialog({ onUpload, onZipUpload, userId }: UploadRepoDialogProps) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [zipError, setZipError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [activeTab, setActiveTab] = useState("manual");

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

  async function handleZipSubmit(e: FormEvent) {
    e.preventDefault();
    setZipError(null);

    if (!zipFile) {
      setZipError("Please select a ZIP file");
      return;
    }

    if (!zipFile.name.toLowerCase().endsWith(".zip")) {
      setZipError("File must be a ZIP archive (.zip)");
      return;
    }

    if (!userId) {
      setZipError("User ID not available");
      return;
    }

    if (!onZipUpload) {
      setZipError("ZIP upload not configured");
      return;
    }

    try {
      setLoading(true);
      await onZipUpload(zipFile, userId);
      setZipFile(null);
      setOpen(false);
    } catch (err: any) {
      setZipError(err.message || "Failed to upload ZIP file");
    } finally {
      setLoading(false);
    }
  }

  function handleFileSelect(e: ChangeEvent<HTMLInputElement>) {
    const files = e.currentTarget.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (file.name.toLowerCase().endsWith(".zip")) {
        setZipFile(file);
        setZipError(null);
      } else {
        setZipFile(null);
        setZipError("Please select a valid ZIP file");
      }
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (v) {
          setError(null);
          setZipError(null);
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

      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Github className="w-5 h-5" />
            Add Repository
          </DialogTitle>
          <DialogDescription>
            Add a repository by pasting a GitHub URL, uploading a ZIP file, or selecting from your GitHub repositories.
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="manual">Manual URL</TabsTrigger>
            <TabsTrigger value="zip">ZIP Upload</TabsTrigger>
            <TabsTrigger value="github">GitHub Connected</TabsTrigger>
          </TabsList>

          <TabsContent value="manual" className="mt-4">
            <form onSubmit={handleSubmit} className="space-y-4">
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
          </TabsContent>

          <TabsContent value="zip" className="mt-4">
            <form onSubmit={handleZipSubmit} className="space-y-4">
              <div className="space-y-3">
                <div className="border-2 border-dashed border-stone-300 rounded-lg p-6 text-center hover:border-stone-400 transition-colors cursor-pointer"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Archive className="w-8 h-8 mx-auto mb-2 text-stone-400" />
                  <p className="text-sm font-medium text-stone-700">
                    {zipFile ? zipFile.name : "Click to select ZIP file or drag and drop"}
                  </p>
                  <p className="text-xs text-stone-500 mt-1">Maximum file size: 500 MB</p>
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".zip"
                  onChange={handleFileSelect}
                  className="hidden"
                />

                {zipError && (
                  <p className="flex items-center gap-1.5 text-sm text-red-500">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    {zipError}
                  </p>
                )}

                {zipFile && (
                  <p className="text-xs text-stone-600 bg-stone-50 p-2 rounded">
                    Selected: <span className="font-mono">{zipFile.name}</span>
                  </p>
                )}
              </div>

              <div className="flex justify-end gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setOpen(false);
                    setZipFile(null);
                  }}
                  disabled={loading}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={loading || !zipFile}>
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Uploading…
                    </>
                  ) : (
                    <>
                      <Archive className="w-4 h-4 mr-2" />
                      Upload ZIP
                    </>
                  )}
                </Button>
              </div>
            </form>
          </TabsContent>

          <TabsContent value="github" className="mt-4">
            <div className="py-4">
              <GitHubRepositorySelector
                onRepositorySelected={() => {
                  setOpen(false)
                  setActiveTab("manual")
                }}
                onRepositoryCloned={() => {
                  setOpen(false)
                }}
              />
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
