# Reader Agent: Methodology for Research Paper

## Overview

The Reader Agent is a language-agnostic component in the automated code documentation pipeline that analyzes code components to assess their complexity and determine what additional information is needed for generating high-quality documentation. Operating on the CodeComponent abstraction provided by the Navigator, the Reader Agent employs a three-phase systematic approach: (1) structural code analysis, (2) LLM-based context sufficiency assessment, and (3) generation of structured XML requests for the downstream Searcher Agent. This design enables cost-effective decision-making about information retrieval while maintaining accuracy across multiple programming languages.

## Phase 1: Language-Agnostic Code Analysis

The Reader Agent analyzes components without language-specific parsing, instead leveraging pre-extracted metadata from the Navigator. It first extracts and classifies function calls into three categories: CLASS (class instantiations), FUNCTION (function calls), and METHOD (method invocations). Classification uses a component_map dictionary for accurate type lookup, with name-based heuristics as fallback when components are not mapped.

Complexity assessment employs a hybrid approach combining three independent metrics. *Cognitive complexity* estimates human cognitive load by analyzing cyclomatic complexity (1.5× multiplier), control flow branches (+2 each), nested loops with branches (+5 interaction penalty), exception handling (+3), async operations (+4), and infinite loops (+8). *Nesting depth* analyzes source code indentation levels (4 spaces or 1 tab = 1 level) with special compression for depths exceeding 6 to prevent exponential penalties. *Coupling score* accounts for external dependencies and parameter count, recognizing that high coupling hinders understanding.

These metrics are combined using weighted coefficients: cognitive complexity (0.5 weight, 50%), nesting depth (2.0 multiplier), and coupling score (0.3 weight, 30%). The cognitive complexity receives the highest weight because human readability is the most predictive factor for documentation need. Final complexity classification thresholds are simple (score ≤ 5), moderate (5 < score ≤ 15), and complex (score > 15). This hybrid approach provides more nuanced complexity assessment than single metrics while remaining computationally efficient at O(C) complexity for source code length C.

Additional analysis includes visibility detection (public/private status) using Navigator's is_public field with name-based fallbacks (leading underscore or hash symbol), and extraction of control flow characteristics (async operations, loops, concurrency, branching, exception handling) that inform downstream LLM reasoning.

## Phase 2: Context Sufficiency Assessment

This phase uses LLM-based decision-making to determine whether additional context is necessary, informed by Phase 1 analysis. To optimize costs, the agent implements a smart skip strategy: components with simple complexity and no function calls bypass LLM analysis entirely, as they are typically self-explanatory. For components requiring LLM analysis, the agent constructs focused prompts containing complexity assessment, function calls, control flow characteristics, and source code snippets.

The LLM applies clear decision criteria: context is needed when algorithms are non-obvious, concurrency patterns are unusual, critical dependencies influence behavior, or domain-specific knowledge is required. Conversely, context is not needed when code is straightforward and component naming clearly describes behavior. Critically, the LLM is instructed that external information retrieval is expensive and should only be used for novel algorithms or state-of-the-art techniques (custom loss functions, recently proposed metrics), while avoiding external retrieval for standard libraries (React, numpy, pandas, TensorFlow) and common patterns (CRUD, authentication, state management).

To minimize API costs, the agent implements batch processing: it identifies which components need LLM analysis, creates a single prompt containing all components, makes one consolidated LLM call, and parses responses to extract individual decisions. This reduces LLM API costs from O(N) to O(1), achieving 95%+ cost reduction for large codebases. The batch response format is simple ("COMPONENT 1: YES/NO - reason"), enabling straightforward parsing. If batch processing fails, the system gracefully degrades by reverting affected components to complexity-based decisions while continuing processing.

LLM response parsing is robust, extracting INFO_NEED (binary context decision), CLASSIFICATION (novel_algorithm, novel_technique, standard_library, standard_pattern), and QUERY (only for novel concepts). Malformed responses trigger fallback logic using component complexity to make reasonable decisions.

## Phase 3: Structured XML Output

The Reader Agent generates machine-readable XML for the Searcher Agent specifying required information. The XML structure contains: (1) INFO_NEED tag indicating whether context is needed, (2) COMPLEXITY tag with the calculated complexity level, and (3) REQUEST section divided into INTERNAL and EXTERNAL parts.

The INTERNAL section specifies available codebase information: CALLS element lists dependencies by type (CLASS, FUNCTION, METHOD), and CALLED_BY flag indicates whether to search for component usage. CALLED_BY is set to true only when the component needs context, is public, is not trivially simple, and is a callable type (function, method, class).

The EXTERNAL section specifies external information needs: CLASSIFICATION categorizes the concept (novel_algorithm, novel_technique, standard_library, standard_pattern), and QUERY contains a natural language question for external retrieval (populated only for novel classifications). The agent includes novel concept detection via comment analysis (scanning for "novel", "paper", "SOTA") and custom implementation detection (loss functions and metrics not using standard libraries).

XML serialization uses ElementTree with proper character escaping, pretty-printing with two-space indentation, and removal of XML declarations. Individual outputs are saved to data/intermediate/agent_output/reader/ for debugging, with consolidated outputs saved for batch analysis.

## Integration and Cost Optimization

The Reader Agent receives CodeComponent objects from Navigator (containing pre-extracted metadata: function calls, dependencies, complexity scores, control flow characteristics, source code, and signatures) and outputs XML documents for the Searcher Agent.

Performance characteristics are favorable: single component analysis operates in O(C) time where C is source code length; LLM calls represent the dominant cost but are optimized through batching; XML generation takes O(C) time. Space complexity is reasonable at O(B) for batch processing and O(D) for dependency tracking. The critical optimization is batch processing, reducing API costs by 95%+ for large codebases by consolidating N individual calls into 1.

## Error Handling and Robustness

The agent implements layered fallback strategies ensuring graceful degradation: LLM failures trigger complexity-based decisions; batch processing failures revert affected components to complexity-based analysis while continuing; missing component_map entries use name-based heuristics; XML parsing failures write raw output and continue; malformed LLM responses apply reasonable defaults. These strategies ensure failures in individual components do not cascade to others.

## Configuration

Tunable parameters include thresholds (SIMPLE_THRESHOLD = 5, COMPLEX_THRESHOLD = 15) and weighting coefficients (cognitive_weight = 0.5, nesting_weight = 2.0, coupling_weight = 0.3). Adjusting thresholds trades off accuracy versus cost; adjusting weights reflects empirical analysis of factors predicting documentation quality.

## Key Contributions

The Reader Agent contributes to automated documentation generation through: (1) language-agnostic analysis via CodeComponent abstraction, eliminating language-specific implementations; (2) hybrid complexity measurement combining cognitive, structural, and coupling metrics for more accurate predictions; (3) batch LLM processing achieving 95% cost reduction; (4) cost-aware framework distinguishing between internal and expensive external retrieval; and (5) deterministic downstream processing enabled by structured XML output. These contributions collectively advance the state of practice in automated documentation systems by balancing accuracy, efficiency, and cost-effectiveness.

## Practical Example

Consider a function process_data with parameters data and config, containing a loop with an inner if-condition that calls a transform function. Phase 1 analysis yields: cognitive complexity = 5.5 (base 1.5 + branch 2 + loop 2), nesting depth = 2, coupling score = 2.8. Final score = 5.5 × 0.5 + 2 × 2.0 + 2.8 × 0.3 ≈ 7.6, classified as moderate. Phase 2 LLM analysis determines context is needed due to nested control flow, classifying it as standard_library (pandas/numpy are well-known). Phase 3 XML output specifies INFO_NEED=true, COMPLEXITY=moderate, lists transform as a FUNCTION dependency, sets CALLED_BY=true, and sets EXTERNAL CLASSIFICATION=standard_library with no query. This guides the Searcher Agent to retrieve transform implementation and find calling locations, but skip expensive web searches.

## Conclusion

The Reader Agent represents an effective balance between sophisticated code understanding and efficient processing. By combining static analysis with LLM-based reasoning, implementing cost-conscious filtering, and producing deterministic structured output, it enables scalable automated documentation generation across multiple programming languages. Its application in production systems demonstrates the feasibility of language-agnostic, cost-optimized approaches to code analysis.
