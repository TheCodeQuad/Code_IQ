# Verifier Agent: Research Paper Methodology

## Overview

The Verifier Agent is a quality assurance component in the documentation pipeline responsible for evaluating generated docstrings and determining whether they meet component-specific quality standards. Operating from the perspective of a first-time code reader, the Verifier assesses whether documentation requires revision, distinguishes between content-based problems and context-based gaps, and provides actionable improvement suggestions. The agent's innovation is calibration-driven assessment: rather than applying uniform quality standards, it adapts expectations to component complexity using tier-specific criteria (TRIVIAL through COMPLEX) and documentation categories (MINIMAL through COMPREHENSIVE). The Verifier uses LLM-based evaluation with structured XML-tagged responses, applies deterministic calibration-based safety overrides to prevent unrealistic demands, and provides clear binary decisions that guide orchestration whether to loop documentation back to the Writer for content fixes or to the Searcher for additional context.

## Calibration Profile: Adaptive Quality Standards

The core innovation of the Verifier is the CalibrationProfile system, which tailors quality expectations to component characteristics. Profiles contain: complexity_tier (determined from Reader's analysis: TRIVIAL, SIMPLE, MODERATE, COMPLEX based on complexity_level and dependency_count), documentation_category (MINIMAL through COMPREHENSIVE based on component type), dependency_count (how many external components), and context_exhausted (whether all available context has been gathered). Tier-specific acceptance criteria define expectations: TRIVIAL tier requires only clear purpose statement; SIMPLE requires purpose+parameters+returns; MODERATE requires all of simple plus side effects and error handling; COMPLEX requires behavioral contracts with pre/post-conditions and edge cases. This approach prevents over-documenting trivial code while ensuring complex components receive appropriate detail. The `build_calibration_profile()` function constructs profiles by analyzing component metadata and orchestrator context history, while `build_calibration_prompt_section()` injects tier-specific expectations into the LLM prompt before evaluation.

## LLM-Based Verification with Calibration Priming

Verification uses BaseAgent's memory-based conversation API to maintain context and separate system instructions from task prompts. The process: (1) clears memory to isolate each verification, (2) adds system prompt establishing Verifier role and calibration guidelines, (3) constructs task prompt with calibration section first (priming LLM before seeing code), (4) generates LLM response, (5) parses structured XML tags. The system prompt is extensive (~400 lines), containing role definition, five critical calibration rules (e.g., "NEVER request context for zero-dependency components"), four-step analysis process, tier-specific verification criteria, and output format requirements. Presenting calibration before the task prompt is intentional—it prevents the LLM's natural bias toward over-documenting complex code by establishing appropriate expectations upfront.

The task prompt construction follows deliberate ordering: calibration section (what tier expectations are), context string (what information was available), component code (what the code does), generated docstring (what needs evaluation). The context string aggregates internal dependencies (from Searcher with summaries and signatures) and external knowledge (queries answered and findings). If no context was gathered, the prompt states this explicitly, helping the LLM understand whether poor documentation quality reflects insufficient information or poor writing.

## Verification Output Structure and Decision Logic

Verification produces a VerificationResult containing: **need_revision** (boolean: is improvement needed?), **more_context** (boolean: when revision needed, is the problem missing context or poor content?), **suggestion** (actionable content improvements when more_context=false), **suggestion_context** (explanation of missing dependencies when more_context=true), and **raw_response** (complete LLM output for debugging). The parsing extracts three types of XML tags: `<NEED_REVISION>true/false</NEED_REVISION>` (required), `<MORE_CONTEXT>true/false</MORE_CONTEXT>` (only if revision needed), and either `<SUGGESTION>...</SUGGESTION>` (content fixes) or `<SUGGESTION_CONTEXT>...</SUGGESTION_CONTEXT>` (context explanation). The distinction between content and context is critical: content problems trigger Writer Agent to rewrite docstrings within existing context; context problems trigger Searcher Agent to gather additional information.

## Calibration Overrides: Hard Constraints

After LLM parsing, the `_apply_calibration_overrides()` method applies deterministic safety constraints that catch cases where the LLM ignored calibration instructions. Three overrides enforce hard rules:

**Override 1 - Context exhausted**: If more_context=true but context_exhausted=true, force more_context=false. This prevents infinite loops requesting the same information repeatedly.

**Override 2 - Zero dependencies**: If more_context=true but dependency_count=0, force more_context=false. Components with zero dependencies cannot logically need context from other code.

**Override 3 - Trivial/minimal blocking**: If more_context=true and the component is TRIVIAL tier+MINIMAL category, force more_context=false. Trivial components by definition don't need extensive context.

These overrides use deterministic rules rather than LLM judgment, ensuring consistency and preventing unrealistic demands. Overrides are logged to identify when LLM deviates from calibration guidance.

## Context String Aggregation and Information Inheritance

The `_build_context_string()` method extracts from context.metadata['accumulated_context'], which the orchestrator populates during the pipeline. Two sections are aggregated: **Internal dependencies** (from Searcher) listing component names, summaries, and signatures showing what was learned about dependencies; **External knowledge** (from Searcher's LLM queries) listing queries and answers. If no context was gathered, the string states "No context was used", signaling that documentation quality limitations may be information-based rather than writing-based.

The aggregation is critical because it represents information inheritance from prior agents: the Verifier evaluates documentation quality knowing what information was actually available, not assuming infinite knowledge. This prevents unfair criticism of documentation limited by unavailable context.

## Full Processing Pipeline and Integration

The main `process()` method orchestrates verification: (1) validates inputs (component and Writer documentation present), (2) builds calibration profile, (3) aggregates context string, (4) calls `_verify_with_llm()` for evaluation, (5) applies calibration overrides for safety, (6) sets improved_documentation=None (improvement delegated downstream), (7) persists results, (8) returns AgentResult with VerificationResult and metadata. The orchestrator interprets results to branch: need_revision=false means accept documentation; need_revision=true && more_context=false means dispatch Writer for content improvement; need_revision=true && more_context=true means recall Searcher for additional information.

The integration contract is clean: Verifier consumes standard inputs (CodeComponent, Documentation) and produces well-defined output (VerificationResult) that orchestrator interprets with static logic, enabling extensible feedback loops. The agent doesn't implement improvements itself; it delegates to specialized agents (Writer for content, Searcher for context), enabling parallel development and component reuse.

## Verification Dimensions and Quality Criteria

Evaluation covers three primary dimensions: **Information Value** (documentation should provide insights beyond code, avoiding statements that merely restate what code does), **Appropriate Detail Level** (matching the component's tier—concise for trivial, comprehensive for complex), and **Completeness** (covering all required sections for the documentation_category). These dimensions are calibrated per tier: TRIVIAL requires only clear purpose, COMPLEX requires behavioral contracts and edge cases. The verification prompt guides LLM assessment using tier-specific criteria rather than universal standards.

## Output Persistence and Statistical Reporting

Individual verification results are saved as timestamped JSON files per component, enabling audit trails and post-analysis. The `save_consolidated_output()` method aggregates all verifications into a single JSON file containing: total verified count, count needing revision, count needing more context, count needing content fixes, timestamp, and complete results array. Consolidated output provides quick statistical overview: what percentage of components passed verification, what percentage need content fixes versus context, enabling process tuning and quality metrics.

## Error Handling and Robustness

Multi-layer error handling ensures resilience: input validation prevents processing without Writer output; LLM interaction wrapped in try-catch; tag extraction returns defaults if missing; override application never crashes on unexpected states; file I/O failures log warnings but don't interrupt processing. Memory isolation (fresh memory per verification) prevents context leakage. Configuration fallbacks apply defaults if settings missing. This defensive approach ensures the agent always produces output, enabling graceful degradation.

## Practical Example: MODERATE Tier Complex Function

Consider verifying a function with MODERATE complexity, 8 dependencies, context_exhausted=false. Calibration: tier=MODERATE, category=DETAILED (should include parameters, returns, side effects). Generated docstring: "Processes data with validation and transformation." LLM evaluation: information value = low ("Processes data" adds no insight), detail level = insufficient (MODERATE tier requires detailed parameters, side effects, error handling), completeness = missing error handling documentation. LLM response: `<NEED_REVISION>true</NEED_REVISION><MORE_CONTEXT>false</MORE_CONTEXT><SUGGESTION>Add parameter types and descriptions, document caching behavior, describe error handling...</SUGGESTION>`. Calibration overrides: none apply. Result: need_revision=true, more_context=false. Orchestrator action: dispatch Writer to improve docstring content with the suggestion.

## Scalability and Performance

Verification performs efficiently: LLM call dominates cost but is O(1) per component; memory operations are efficient; tag extraction via regex is O(n) in response length (typically ~500 tokens); override checking is O(1); persistence is O(1) per component. For 1000 components, total time dominated by 1000 LLM calls (parallelizable if needed). No graph traversals or global codebase searches are required.

## Configuration

Settings are minimal: validation_rules list from agent configuration, output_dir customizable, system prompt customizable in code. Calibration thresholds (what dependency count maps to which tier) are defined in verifier_calibration.py and tunable for different development contexts.

## Key Contributions

The Verifier Agent contributes through: (1) calibration-aware quality assessment adapting standards to complexity, (2) first-reader perspective evaluating from new developer's viewpoint, (3) binary decisions guiding orchestration logic, (4) content vs. context distinction enabling targeted improvement, (5) deterministic overrides preventing LLM against-calibration requests, (6) actionable feedback guiding Writer or Searcher, (7) audit trails enabling process improvement. Together, these enable cost-effective documentation without over-engineering or under-documenting.

## Conclusion

The Verifier Agent demonstrates how LLM-driven assessment combined with calibration-based constraints can provide principled quality assurance for automated documentation. By adapting evaluation to component complexity and establishing clear decision logic, it avoids the extremes of over-documenting trivial code and under-documenting complex systems. Its integration with the orchestration system enables iterative feedback loops: verification identifies problems, feedback loops improve documentation via Writer or Searcher, moving quality toward acceptance criteria. The agent's robustness, clear decision criteria, and comprehensive logging make it suitable for production documentation pipelines.
