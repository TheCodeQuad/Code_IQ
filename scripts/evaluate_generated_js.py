"""
Evaluate generated JS docstrings against original CodeSearchNet human comments.

Baseline:  scripts/data/validation/codesearchnet/codesearchnet_javascript.js
           (original human comments from CodeSearchNet)
Generated: data/input/repositories/Test/codesearchnet_javascript_no_comments.js
           (pipeline-generated docstrings)
Ground truth: scripts/data/validation/codesearchnet/javascript_code_comments.jsonl
"""

import json, re, math, os, sys
from pathlib import Path
from collections import Counter

os.chdir(Path(__file__).resolve().parent.parent)  # project root

# ── Load ground truth ────────────────────────────────────────────────
jsonl = Path("scripts/data/validation/codesearchnet/javascript_code_comments.jsonl")
samples = [json.loads(l) for l in open(jsonl, encoding="utf-8")]

# ── Load generated file ─────────────────────────────────────────────
gen_text = open(
    "data/input/repositories/Test/codesearchnet_javascript_no_comments.js",
    encoding="utf-8",
).read()


# ── Helpers ──────────────────────────────────────────────────────────
def clean_jsdoc(raw):
    """Strip JSDoc decoration, return plain text."""
    lines = raw.split("\n")
    out = []
    for l in lines:
        l = l.strip().lstrip("*").strip()
        if l in ("/**", "*/", ""):
            continue
        out.append(l)
    return " ".join(out)


def extract_tags(text):
    """Return set of JSDoc tag names present."""
    return set(re.findall(r"@(\w+)", text))


def get_summary(text):
    """First non-tag, non-empty line = summary."""
    for l in text.split("\n"):
        l = l.strip().lstrip("* ").strip()
        if l and not l.startswith("@") and l not in ("/**", "*/"):
            return l
    return ""


def word_tokens(text):
    """Lowercase word tokens."""
    return [w.lower() for w in re.findall(r"[A-Za-z_]\w*", text)]


def word_overlap(a_tokens, b_tokens):
    """Jaccard similarity of word sets."""
    sa, sb = set(a_tokens), set(b_tokens)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def bleu1(reference_tokens, candidate_tokens):
    """Unigram BLEU (precision-only)."""
    if not candidate_tokens or not reference_tokens:
        return 0.0
    ref_counts = Counter(reference_tokens)
    matches = 0
    for w in candidate_tokens:
        if ref_counts[w] > 0:
            matches += 1
            ref_counts[w] -= 1
    precision = matches / len(candidate_tokens)
    # brevity penalty
    bp = min(1.0, math.exp(1 - len(reference_tokens) / max(len(candidate_tokens), 1)))
    return precision * bp


GENERIC_OPENERS = [
    "this function",
    "this method",
    "a function that",
    "helper function",
    "utility function",
    "the following",
]

STRONG_VERBS = [
    "creates", "returns", "computes", "performs", "generates", "retrieves",
    "determines", "converts", "checks", "finds", "maps", "wraps", "pipes",
    "fixes", "bundles", "calculates", "updates", "applies", "removes",
    "splits", "joins", "reads", "writes", "initializes", "ensures",
    "appends", "strips", "schedules", "clears", "attaches", "binds",
]


# ── Match each sample ───────────────────────────────────────────────
results = []
for i, s in enumerate(samples):
    code_start = s["code"].strip()[:80]
    idx = gen_text.find(code_start)

    orig_comment = s.get("comment", "").strip()
    name = s.get("name", "unknown")

    if idx < 0:
        results.append(dict(i=i, name=name, orig=orig_comment, gen="", gen_raw="", found=False))
        continue

    before = gen_text[max(0, idx - 3000): idx]
    jsdoc_match = re.search(r"/\*\*(.*?)\*/\s*$", before, re.DOTALL)

    gen_raw = ""
    gen_clean = ""
    if jsdoc_match:
        gen_raw = jsdoc_match.group(0)
        gen_clean = clean_jsdoc(jsdoc_match.group(1))

    results.append(dict(i=i, name=name, orig=orig_comment, gen=gen_clean, gen_raw=gen_raw, found=True))


# ── Compute metrics ─────────────────────────────────────────────────
found = [r for r in results if r["found"]]
has_gen = [r for r in found if r["gen"]]

overlaps = []
bleu_scores = []
throws_correct = 0
throws_hallucinated = 0
throws_total_gen = 0
throws_total_orig = 0
generic_count = 0
strong_verb_count = 0
has_param_gen = 0
has_returns_gen = 0
has_param_orig = 0
has_returns_orig = 0
summary_better = 0
summary_worse = 0
summary_equal = 0
hallucination_count = 0

HALLUCINATION_WORDS = ["codesearchnet", "no_comments", "jsonl", "prototype."]

print("=" * 90)
print(f"{'#':>3}  {'Function':<35} {'Overlap':>7} {'BLEU-1':>7}  {'Tags':>12}  Notes")
print("=" * 90)

for r in found:
    orig_tokens = word_tokens(r["orig"])
    gen_tokens = word_tokens(r["gen"])

    ov = word_overlap(orig_tokens, gen_tokens)
    bl = bleu1(orig_tokens, gen_tokens)
    overlaps.append(ov)
    bleu_scores.append(bl)

    # Tags
    orig_tags = extract_tags(r["orig"])
    gen_tags = extract_tags(r["gen_raw"])

    notes = []

    # @throws check
    orig_has_throws = "throws" in orig_tags or "throw" in orig_tags
    gen_has_throws = "throws" in gen_tags or "throw" in gen_tags
    if orig_has_throws:
        throws_total_orig += 1
    if gen_has_throws:
        throws_total_gen += 1
        # Check if the FULL function body (in the generated file) has throw statements
        code_start = samples[r["i"]]["code"].strip()[:80]
        code_idx = gen_text.find(code_start)
        if code_idx >= 0:
            # Grab up to 5000 chars of the function body
            func_body = gen_text[code_idx:code_idx + 5000]
            has_throw = bool(re.search(r"\bthrow\s", func_body))
        else:
            has_throw = False
        if has_throw:
            throws_correct += 1
        else:
            throws_hallucinated += 1
            notes.append("@throws HALLUCINATED")

    # @param / @returns coverage
    if "param" in gen_tags:
        has_param_gen += 1
    if "returns" in gen_tags or "return" in gen_tags:
        has_returns_gen += 1
    if "param" in orig_tags:
        has_param_orig += 1
    if "returns" in orig_tags or "return" in orig_tags:
        has_returns_orig += 1

    # Summary quality
    gen_summary = get_summary(r["gen_raw"])
    orig_summary = r["orig"].split("\n")[0].strip() if r["orig"] else ""

    if gen_summary:
        low = gen_summary.lower()
        for gp in GENERIC_OPENERS:
            if low.startswith(gp):
                generic_count += 1
                notes.append("GENERIC")
                break

        for sv in STRONG_VERBS:
            if low.startswith(sv):
                strong_verb_count += 1
                break

    # Hallucination check
    gen_low = r["gen"].lower()
    for hw in HALLUCINATION_WORDS:
        if hw in gen_low:
            hallucination_count += 1
            notes.append(f"HALLUC({hw})")
            break

    # Is gen summary more informative than orig?
    orig_is_region = orig_summary.startswith("#region") or orig_summary.startswith("#endregion")
    orig_is_vague = len(orig_summary) < 15 or orig_summary.lower() in ("helpers", "functions - definitions")
    if orig_is_region or orig_is_vague:
        if gen_summary and len(gen_summary) > 20:
            summary_better += 1
            notes.append("BETTER")
        else:
            summary_equal += 1
    elif not r["gen"]:
        summary_worse += 1
        notes.append("MISSING")
    else:
        summary_equal += 1

    note_str = ", ".join(notes) if notes else ""
    tag_str = f"G:{len(gen_tags)} O:{len(orig_tags)}"
    print(f"{r['i']+1:3d}  {r['name']:<35} {ov:7.2f} {bl:7.2f}  {tag_str:>12}  {note_str}")


# ── Aggregate stats ─────────────────────────────────────────────────
print()
print("=" * 90)
print("AGGREGATE METRICS")
print("=" * 90)

n = len(found)
ng = len(has_gen)

print(f"\n--- Coverage ---")
print(f"  Functions matched in output:     {n}/100")
print(f"  Functions with docstrings:       {ng}/100  ({100*ng/100:.0f}%)")
print(f"  Functions without docstring:     {n - ng}/100")

print(f"\n--- Semantic Similarity (generated vs original human comment) ---")
avg_ov = sum(overlaps) / max(len(overlaps), 1)
avg_bl = sum(bleu_scores) / max(len(bleu_scores), 1)
print(f"  Avg word overlap (Jaccard):      {avg_ov:.3f}")
print(f"  Avg BLEU-1:                      {avg_bl:.3f}")

print(f"\n--- @throws Accuracy ---")
print(f"  Original has @throws:            {throws_total_orig}")
print(f"  Generated has @throws:           {throws_total_gen}")
print(f"  Correct (code has throw):        {throws_correct}")
print(f"  HALLUCINATED (no throw in code): {throws_hallucinated}")
print(f"  @throws precision:               {100*throws_correct/max(throws_total_gen,1):.0f}%")

print(f"\n--- Tag Coverage ---")
print(f"  @param  — Orig: {has_param_orig}  Gen: {has_param_gen}  (delta: {has_param_gen - has_param_orig:+d})")
print(f"  @returns — Orig: {has_returns_orig}  Gen: {has_returns_gen}  (delta: {has_returns_gen - has_returns_orig:+d})")

print(f"\n--- Summary Quality ---")
print(f"  Starts with strong action verb:  {strong_verb_count}/{ng}  ({100*strong_verb_count/max(ng,1):.0f}%)")
print(f"  Generic/weak openers:            {generic_count}/{ng}  ({100*generic_count/max(ng,1):.0f}%)")
print(f"  Generated BETTER than original:  {summary_better}  (orig was vague/#region)")
print(f"  Generated equal quality:         {summary_equal}")
print(f"  Generated worse/missing:         {summary_worse}")

print(f"\n--- Hallucinations ---")
print(f"  Filename/artifact leaks:         {hallucination_count}")

# Overall score (weighted, generation-appropriate — NOT reproduction)
# Low BLEU/overlap is expected: we generate NEW docs, not reproduce originals
coverage_score = 30 * (ng / 100)
throws_precision = throws_correct / max(throws_total_gen, 1) if throws_total_gen else 1.0
throws_score = 15 * throws_precision
verb_ratio = strong_verb_count / max(ng, 1)
verb_score = min(15, 15 * verb_ratio / 0.6)
tag_score = min(15, 15 * ((has_param_gen + has_returns_gen) / max(2 * ng, 1)) / 0.7)
# Bonus for improving vague originals
improvement_score = min(10, 10 * summary_better / max(summary_better + summary_worse + 1, 1))
# Penalties (moderate — missing docs for anon functions shouldn't count heavily)
penalty = 1 * hallucination_count + 1.5 * throws_hallucinated
score = coverage_score + throws_score + verb_score + tag_score + improvement_score - penalty
score = max(0, min(100, score))

print(f"\n{'='*90}")
print(f"  OVERALL QUALITY SCORE:  {score:.0f} / 100")
print(f"{'='*90}")
