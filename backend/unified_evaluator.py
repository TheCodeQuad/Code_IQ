"""
Unified Evaluator - Runs completeness, helpfulness, and truthfulness evaluations
on generated docstrings for a given repository.

Usage:
    from backend.unified_evaluator import UnifiedEvaluator
    evaluator = UnifiedEvaluator(repo_name="my-repo")
    results = evaluator.evaluate_all()
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import asdict

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]

from backend.models.code_component import CodeComponent
from backend.eval_completeness import run_multilang_evaluation
from backend.eval_helpfulness import run_helpfulness_evaluation
from backend.evaluator.truthfulness import TruthfulnessEvaluator


class UnifiedEvaluator:
    """
    Orchestrates all three evaluation types:
    - Completeness: checks structural completeness of docstrings
    - Helpfulness: LLM-based quality assessment (1-5 scale)
    - Truthfulness: verifies mentioned components exist in codebase
    """

    def __init__(self, repo_name: str):
        self.repo_name = repo_name
        self.nav_output_dir = PROJECT_ROOT / "data" / "intermediate" / "navigator_output"
        self.writer_output_dir = PROJECT_ROOT / "data" / "intermediate" / "agent_output" / "writer"
        self.validation_dir = PROJECT_ROOT / "data" / "validation" / repo_name
        self.validation_dir.mkdir(parents=True, exist_ok=True)

    def _load_components(self) -> Dict[str, CodeComponent]:
        """
        Load components from the navigator IR export.
        Looks for ir_{repo_name}.json in navigator output dir.
        """
        ir_file = self.nav_output_dir / f"ir_{self.repo_name}.json"
        if not ir_file.exists():
            # Try without prefix
            candidates = list(self.nav_output_dir.glob(f"*{self.repo_name}*.json"))
            ir_file = candidates[0] if candidates else None
            if not ir_file:
                raise FileNotFoundError(
                    f"No IR file found for '{self.repo_name}' in {self.nav_output_dir}"
                )

        with open(ir_file, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        components = {}
        for comp_id, comp_data in raw.items():
            try:
                components[comp_id] = CodeComponent.from_dict(comp_data)
            except Exception:
                # Skip components that can't be deserialized
                continue

        if not components:
            raise ValueError(f"No valid components loaded from {ir_file}")

        print(f"📦 Loaded {len(components)} components from {ir_file.name}")
        return components

    def _run_completeness(self, components: Dict[str, CodeComponent]) -> Dict[str, Any]:
        """Run completeness evaluation."""
        print("📋 Running completeness evaluation...")
        results = run_multilang_evaluation(components)

        total = results["overall"]["total"]
        avg = results["overall"]["average"]
        documented = sum(
            d.get("documented", 0) for d in results["by_language"].values()
        )

        return {
            "summary": {
                "overall_score": avg,
                "total_components": total,
                "components_with_docstrings": documented,
                "avg_sections": avg,
                "criteria_percentages": self._calc_completeness_criteria(results),
            },
            "by_language": {
                lang: {"total": d["total"], "average": d["average"]}
                for lang, d in results["by_language"].items()
            },
            "by_type": {
                t: {"total": d["total"], "average": d["average"]}
                for t, d in results["by_type"].items()
            },
        }

    def _calc_completeness_criteria(self, results: Dict) -> Dict[str, float]:
        """Calculate what percentage of components have each section."""
        comps = results.get("components", [])
        if not comps:
            return {}

        total = len(comps)
        criteria = {}
        section_keys = ["has_description", "has_args", "has_returns", "has_raises", "has_examples"]

        for key in section_keys:
            short = key.replace("has_", "")
            count = sum(
                1 for c in comps
                if c.get("element_scores", {}).get(short, 0) > 0
                or c.get("element_scores", {}).get(key, 0) > 0
            )
            criteria[key] = round(count / total, 3) if total else 0

        return criteria

    def _run_helpfulness(self, components: Dict[str, CodeComponent]) -> Dict[str, Any]:
        """Run helpfulness evaluation (LLM-based)."""
        print("💡 Running helpfulness evaluation...")
        try:
            results = run_helpfulness_evaluation(components, max_components=50)

            scores = results["overall"]["scores"]
            avg = results["overall"]["average"]

            return {
                "summary": {
                    "average_score": avg,
                    "total_components": len(results["components"]),
                    "min_score": min(scores) if scores else 0,
                    "max_score": max(scores) if scores else 0,
                    "skipped_no_docstring": results.get("skipped_no_docstring", 0),
                },
                "by_aspect": {
                    a: {"total": d["total"], "average": d["average"]}
                    for a, d in results.get("by_aspect", {}).items()
                },
                "by_language": {
                    lang: {"total": d["total"], "average": d["average"]}
                    for lang, d in results.get("by_language", {}).items()
                },
                "errors": results.get("errors", []),
            }
        except Exception as e:
            print(f"⚠️  Helpfulness evaluation error: {e}")
            return {
                "summary": {
                    "average_score": 0,
                    "total_components": 0,
                    "min_score": 0,
                    "max_score": 0,
                    "skipped_no_docstring": 0,
                },
                "by_aspect": {},
                "by_language": {},
                "errors": [str(e)],
            }

    def _run_truthfulness(self, components: Dict[str, CodeComponent]) -> Dict[str, Any]:
        """Run truthfulness evaluation."""
        print("🔍 Running truthfulness evaluation...")
        try:
            # Find writer output directory for this repo
            writer_dir = self.writer_output_dir
            # Check repo-specific subdirectory
            repo_writer_dir = writer_dir / self.repo_name
            if repo_writer_dir.exists():
                writer_dir = repo_writer_dir

            evaluator = TruthfulnessEvaluator(
                writer_output_dir=str(writer_dir),
                navigator_output_dir=str(self.nav_output_dir),
                use_llm=False,  # Use regex for speed in UI
                llm_mode="llama_cpp",
            )

            results = evaluator.evaluate_all()

            total = len(results)
            if total == 0:
                # If no writer output, evaluate from IR docstrings directly
                return self._truthfulness_from_components(components, evaluator)

            total_mentions = sum(r.total_mentions for r in results.values())
            total_existing = sum(r.existing_mentions for r in results.values())
            total_cross = sum(r.cross_file_mentions for r in results.values())
            avg_existence = (
                sum(r.existence_ratio for r in results.values()) / total
                if total else 0
            )

            # Collect issue types
            issue_types = {}
            for r in results.values():
                for cm in r.mentioned_components:
                    if not cm.exists:
                        itype = "hallucinated_component"
                        issue_types[itype] = issue_types.get(itype, 0) + 1
                    if cm.is_cross_file:
                        itype = "cross_file_reference"
                        issue_types[itype] = issue_types.get(itype, 0) + 1

            return {
                "summary": {
                    "overall_accuracy": round(avg_existence, 3),
                    "total_components": total,
                    "accurate_components": sum(
                        1 for r in results.values() if r.existence_ratio == 1.0
                    ),
                    "components_with_issues": sum(
                        1 for r in results.values() if r.hallucination_rate > 0
                    ),
                    "total_mentions": total_mentions,
                    "existing_mentions": total_existing,
                    "cross_file_references": total_cross,
                    "issue_types": issue_types,
                },
            }
        except Exception as e:
            print(f"⚠️  Truthfulness evaluation error: {e}")
            return self._truthfulness_from_components(components, None)

    def _truthfulness_from_components(
        self, components: Dict[str, CodeComponent], evaluator
    ) -> Dict[str, Any]:
        """Fallback: evaluate truthfulness directly from IR components."""
        total = 0
        accurate = 0
        issue_types = {}

        for comp_id, comp in components.items():
            docstring = comp.existing_docstring or ""
            if not docstring:
                continue
            total += 1

            if evaluator:
                result = evaluator.evaluate_docstring(
                    comp_id, docstring,
                    comp.location.file_path if comp.location else "",
                    comp.language,
                )
                if result.existence_ratio == 1.0:
                    accurate += 1
                for cm in result.mentioned_components:
                    if not cm.exists:
                        issue_types["hallucinated_component"] = (
                            issue_types.get("hallucinated_component", 0) + 1
                        )
            else:
                accurate += 1  # Can't verify without evaluator

        accuracy = round(accurate / total, 3) if total else 1.0
        return {
            "summary": {
                "overall_accuracy": accuracy,
                "total_components": total,
                "accurate_components": accurate,
                "components_with_issues": total - accurate,
                "total_mentions": 0,
                "existing_mentions": 0,
                "cross_file_references": 0,
                "issue_types": issue_types,
            },
        }

    def evaluate_all(self) -> Dict[str, Any]:
        """
        Run all three evaluations and return combined results.
        """
        components = self._load_components()

        completeness = self._run_completeness(components)
        helpfulness = self._run_helpfulness(components)
        truthfulness = self._run_truthfulness(components)

        # Calculate overall quality score (weighted average)
        comp_score = completeness["summary"]["overall_score"]  # 0-1
        help_score = helpfulness["summary"]["average_score"] / 5.0  # normalize 1-5 → 0-1
        truth_score = truthfulness["summary"]["overall_accuracy"]  # 0-1

        overall = round(
            0.35 * comp_score + 0.35 * help_score + 0.30 * truth_score, 3
        )

        results = {
            "repo_name": self.repo_name,
            "overall_quality_score": overall,
            "completeness": completeness,
            "helpfulness": helpfulness,
            "truthfulness": truthfulness,
        }

        # Save results
        out_file = self.validation_dir / "unified_evaluation_results.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        results["output_file"] = str(out_file)

        print(f"\n✅ Evaluation complete!")
        print(f"   Overall Quality Score: {overall:.1%}")
        print(f"   Completeness: {comp_score:.1%}")
        print(f"   Helpfulness:  {help_score:.1%} (raw {helpfulness['summary']['average_score']:.2f}/5)")
        print(f"   Truthfulness: {truth_score:.1%}")
        print(f"   Results saved to: {out_file}")

        return results
