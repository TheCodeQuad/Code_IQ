const TOKEN_REGEX = /\[[^\]]+\]|\([^\)]+\)|[^\s]+/g

const wrapAt = (tokens: string[], maxChars: number): string[] => {
  const lines: string[] = []
  let current = ""

  tokens.forEach((token) => {
    if (!current) {
      current = token
      return
    }

    const candidate = `${current} ${token}`
    if (candidate.length <= maxChars) {
      current = candidate
    } else {
      lines.push(current)
      current = token
    }
  })

  if (current) {
    lines.push(current)
  }

  return lines
}

export const wrapSemanticLabel = (text: string, maxLines = 3): string => {
  const normalized = (text || "").replace(/\s+/g, " ").trim()
  if (!normalized) {
    return ""
  }

  if (normalized.includes("\n")) {
    return normalized
  }

  const tokens = normalized.match(TOKEN_REGEX) || [normalized]
  let best = [normalized]
  let bestScore = Number.POSITIVE_INFINITY

  for (let maxChars = 16; maxChars <= 24; maxChars += 1) {
    let lines = wrapAt(tokens, maxChars)

    while (lines.length > maxLines) {
      let bestIndex = 0
      let bestPair = Number.POSITIVE_INFINITY
      for (let i = 0; i < lines.length - 1; i += 1) {
        const score = lines[i].length + lines[i + 1].length
        if (score < bestPair) {
          bestPair = score
          bestIndex = i
        }
      }
      lines = [
        ...lines.slice(0, bestIndex),
        `${lines[bestIndex]} ${lines[bestIndex + 1]}`.trim(),
        ...lines.slice(bestIndex + 2),
      ]
    }

    if (lines.length > maxLines) {
      continue
    }

    const spread =
      lines.length > 1
        ? Math.max(...lines.map((line) => line.length)) - Math.min(...lines.map((line) => line.length))
        : 0
    const score = Math.abs(lines.length - 2) * 100 + spread * 10 + maxChars
    if (score < bestScore) {
      best = lines
      bestScore = score
    }
  }

  return best.join("\n")
}

export const getRawLabel = (label?: string, metadata?: Record<string, any>): string => {
  const fromMeta = metadata?.raw_label || metadata?.semantic_label_raw || metadata?.label
  const raw = (fromMeta || label || "").toString().trim()
  return raw
}

export const getWrappedLabel = (label?: string, metadata?: Record<string, any>, maxLines = 3): string => {
  const fromMeta = metadata?.wrapped_label
  if (typeof fromMeta === "string" && fromMeta.trim()) {
    return fromMeta.trim()
  }

  const raw = getRawLabel(label, metadata)
  if (!raw) {
    return ""
  }

  return wrapSemanticLabel(raw, maxLines)
}
