import { PullRequestPanel } from "@/components/pull-request-panel"

export default async function PullRequestPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return <PullRequestPanel analysisId={id} />
}
