import json
import re
from pathlib import Path

sources = [
    r"C:\BIA6\CodeIQ\data\benchmark_results\7b_calculatorjs\benchmark_summary.json",
    r"C:\BIA6\CodeIQ\data\benchmark_results\14b-leetcode-py\benchmark_summary.json",
    r"C:\BIA6\CodeIQ\data\benchmark_results\codellama_testrepo\benchmark_summary.json",
    r"C:\BIA6\CodeIQ\data\benchmark_results\storehub_java\benchmark_summary.json",
    r"C:\BIA6\CodeIQ\data\benchmark_results\testrepo\benchmark_summary.json",
    r"C:\BIA6\CodeIQ\data\benchmark_results\resumeredirect_ts\benchmark_summary.json",
    r"C:\BIA6\CodeIQ\data\benchmark_results\resumeredirect-7b\benchmark_summary.json",
    r"C:\BIA6\CodeIQ\data\benchmark_results\javabig\benchmark_summary.json",
    r"C:\BIA6\CodeIQ\data\benchmark_results\javabig-7b\benchmark_summary.json",
    r"C:\BIA6\CodeIQ\data\benchmark_results\20260408_152558\models\qwen2.5-coder-7b-instruct-q4_k_m\benchmark_result.json",
]

rows = []
for src in sources:
    data = json.loads(Path(src).read_text(encoding="utf-8"))
    if src.endswith("benchmark_result.json"):
        results = [data]
    else:
        results = data.get("model_benchmarks", {}).get("results", [])
    for result in results:
        rows.append(
            {
                "path": src,
                "repo": result.get("repo_name"),
                "model": result.get("config_name"),
                "scores": result.get("evaluation_scores", {}),
            }
        )


def infer_language(path: str, repo: str | None) -> str:
    text = (path + " " + (repo or "")).lower()
    if "typescript" in text or "resumeredirect" in text or re.search(r"\bts\b", text):
        return "TypeScript"
    if "python" in text or "leetcode" in text or re.search(r"\bpy\b", text):
        return "Python"
    if "java" in text and "javascript" not in text:
        return "Java"
    if "javascript" in text or "calculatorjs" in text or re.search(r"\bjs\b", text):
        return "JavaScript"
    return "Unknown"


lang_scores: dict[str, list[float]] = {}
model_scores: dict[str, dict[str, list[float]]] = {}

for row in rows:
    scores = row["scores"]
    if not isinstance(scores, dict):
        continue
    overall_quality = scores.get("overall_quality")
    completeness = scores.get("completeness")
    helpfulness = scores.get("helpfulness")
    truthfulness = scores.get("truthfulness")

    if not isinstance(overall_quality, (int, float)):
        continue

    language = infer_language(row["path"], row["repo"])
    lang_scores.setdefault(language, []).append(float(overall_quality))

    model_name = row["model"] or "unknown"
    if all(isinstance(value, (int, float)) for value in (completeness, helpfulness, truthfulness)):
        model_scores.setdefault(
            model_name, {"completeness": [], "helpfulness": [], "truthfulness": []}
        )
        model_scores[model_name]["completeness"].append(float(completeness))
        model_scores[model_name]["helpfulness"].append(float(helpfulness))
        model_scores[model_name]["truthfulness"].append(float(truthfulness))

print("LANGUAGE_AVG")
for language, values in lang_scores.items():
    avg = sum(values) / len(values) if values else 0.0
    print(f"{language}\t{avg:.4f}\t{len(values)}")

print("MODEL_AVG")
for model, values in model_scores.items():
    comp_avg = sum(values["completeness"]) / len(values["completeness"])
    help_avg = sum(values["helpfulness"]) / len(values["helpfulness"])
    truth_avg = sum(values["truthfulness"]) / len(values["truthfulness"])
    print(f"{model}\t{comp_avg:.4f}\t{help_avg:.4f}\t{truth_avg:.4f}\t{len(values['completeness'])}")
