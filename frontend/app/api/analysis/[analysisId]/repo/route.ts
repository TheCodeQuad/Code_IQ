import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function parseGithubFullName(value?: string | null): string | null {
  if (!value) return null;
  const raw = value.trim();
  if (!raw) return null;

  const ownerRepo = raw.match(/^[\w.-]+\/[\w.-]+$/);
  if (ownerRepo) return raw;

  const httpsMatch = raw.match(/github\.com\/([\w.-]+\/[\w.-]+?)(?:\.git)?(?:$|\/)/i);
  if (httpsMatch?.[1]) return httpsMatch[1];

  const sshMatch = raw.match(/github\.com:([\w.-]+\/[\w.-]+?)(?:\.git)?$/i);
  if (sshMatch?.[1]) return sshMatch[1];

  return null;
}

/**
 * GET /api/analysis/[analysisId]/repo — fetch repository data for an analysis
 */
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ analysisId: string }> }
) {
  try {
    const { analysisId } = await params;

    console.log(`[API Proxy] GET /api/analysis/${analysisId}/repo -> ${BACKEND}/api/analysis/${analysisId}/repo`);

    const res = await fetch(
      `${BACKEND}/api/analysis/${analysisId}/repo`,
      { cache: "no-store" }
    );

    if (!res.ok) {
      const errorText = await res.text();
      console.error(`[API Proxy] Backend error: ${res.status}`, errorText);

      if (res.status === 404) {
        console.warn(`[API Proxy] Falling back to /api/repos/${analysisId} for repo linkage`);
        const repoRes = await fetch(`${BACKEND}/api/repos/${analysisId}`, { cache: "no-store" });

        if (!repoRes.ok) {
          const repoErr = await repoRes.text();
          return NextResponse.json(
            { error: `Backend returned ${repoRes.status}: ${repoErr}` },
            { status: repoRes.status }
          );
        }

        const repoDoc = await repoRes.json();
        const repoUrl =
          repoDoc?.repo_url ||
          repoDoc?.github_url ||
          repoDoc?.url ||
          repoDoc?.github_repo_url ||
          repoDoc?.clone_url ||
          "";
        const fullName = parseGithubFullName(repoDoc?.github_repo_full_name || repoDoc?.full_name || repoUrl);

        if (!fullName) {
          return NextResponse.json(
            { error: "Repository exists but GitHub linkage fields are missing" },
            { status: 400 }
          );
        }

        const [owner, repoName] = fullName.split("/");
        const normalizedUrl = repoUrl || `https://github.com/${fullName}`;

        return NextResponse.json(
          {
            repo: {
              full_name: fullName,
              owner: { login: owner },
              default_branch: "main",
              url: normalizedUrl,
            },
            branches: ["main", "master", "develop"],
            fallback: true,
          },
          { status: 200 }
        );
      }

      return NextResponse.json(
        { error: `Backend returned ${res.status}: ${errorText}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    console.log(`[API Proxy] Response:`, data);
    console.log(`[API Proxy] Available branches:`, data.branches || []);
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    console.error("[API Proxy] GET /api/analysis/[analysisId]/repo error:", err);
    return NextResponse.json(
      { error: err.message || "Backend unreachable" },
      { status: 502 }
    );
  }
}
