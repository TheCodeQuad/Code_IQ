import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * POST /api/repos/upload-zip — upload a ZIP file containing source code
 */

export async function POST(req: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const userId = (session.user as any).id;
    if (!userId) {
      return NextResponse.json(
        { error: "User ID missing from session" },
        { status: 400 }
      );
    }

    // Read the form data
    const formData = await req.formData();
    const file = formData.get("file") as File;

    if (!file) {
      return NextResponse.json(
        { error: "No file provided" },
        { status: 400 }
      );
    }

    // Forward to backend with the file
    const backendFormData = new FormData();
    backendFormData.append("file", file);

    const res = await fetch(
      `${BACKEND}/api/repos/upload-zip?user_id=${encodeURIComponent(userId)}`,
      {
        method: "POST",
        body: backendFormData,
        // Don't set Content-Type header - let the browser set it with boundary
      }
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    console.error("POST /api/repos/upload-zip proxy error:", err);
    return NextResponse.json(
      { error: err.message || "Backend unreachable" },
      { status: 502 }
    );
  }
}
