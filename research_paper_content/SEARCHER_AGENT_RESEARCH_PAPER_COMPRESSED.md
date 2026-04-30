# Searcher Agent: Research Paper Methodology

## Overview

The Searcher Agent is a context retrieval component in the automated documentation generation pipeline responsible for gathering evidence from two primary sources: internal codebase through dependency graph traversal and external sources through LLM queries. Operating as the bridge between the Reader Agent's structured information requests and the Writer Agent's documentation generation, the Searcher Agent processes XML or object-based requests specifying what information is needed and returns comprehensive SearcherOutput containing dependency implementations, usage examples, and external knowledge. The agent's design emphasizes efficiency through pre-computed graph structures, O(1) component lookups, and selective external retrieval restricted to novel concepts.

## Architecture and Data Structures

The Searcher Agent's architecture rests on four critical components: a **component_map** dictionary providing O(1) lookup of any CodeComponent by ID, a **dependency_graph** (NetworkX DiGraph) representing forward dependencies, a pre-computed **reverse_graph** enabling O(1) reverse dependency lookups, and a **summary_cache** avoiding redundant LLM calls. Four specialized dataclasses organize retrieved information: **DependencyContext** encapsulates a dependency with its ID, name, summary, signature, docstring, and source code snippet; **ReferenceContext** represents component usage with caller information, call sites, and usage patterns; **ExternalContext** holds external knowledge including query, knowledge type, and detailed explanation; **SearcherOutput** aggregates these into a final result object.

The initialization phase via `set_repository_data()` accepts a complete list of CodeComponents and the dependency graph. The method constructs component_map as a dictionary mapping component IDs to CodeComponent objects. Critically, it uses NetworkX's native `reverse(copy=False)` method to efficiently compute the reverse graph without full duplication, enabling O(1) caller lookups without the expense of traditional graph inversion. This pre-computation at startup avoids repeated expensive calculations during processing.

## Request Parsing and Normalization

The Searcher Agent accepts requests in two formats and normalizes them to a standard internal structure. The `_parse_reader_request()` dispatcher detects input format—XML string or ReaderOutput object—and routes to the appropriate parser. The XML parser expects REQUEST elements containing INTERNAL (with CALLS sublists for CLASS, FUNCTION, METHOD and a CALLED_BY boolean) and EXTERNAL (with QUERY elements) sections. The parser validates each expected element and converts comma-separated text into structured lists. The object parser extracts similar information from ReaderOutput attributes. Both parsers produce normalized dictionaries with consistent structure: 'internal' containing 'calls' (with CLASS, FUNCTION, METHOD sublists) and 'called_by' (boolean), and 'external' containing 'queries' (list of strings). This normalization is critical for consistent downstream processing and provides a clean contract between agents.

## Graph Traversal and Dependency Retrieval

The Searcher Agent uses efficient graph operations for O(k) dependency and O(m) caller retrieval. The `_get_dependencies()` method calls NetworkX's `successors()` on the dependency graph, returning all components the focal component directly depends on. The `_get_callers()` method calls `successors()` on the pre-computed reverse_graph, returning all components that call the focal component. Both methods handle NetworkXError exceptions gracefully, returning empty lists if components are missing. The efficiency of these operations is critical: without the pre-computed reverse graph, finding callers would require O(n) iteration through all components.

## Intelligent Dependency Lookup Strategy

The `_build_dependency_lookup()` method creates a focused, multi-strategy lookup dictionary scoped to actual dependencies rather than the entire component_map. For each dependency component ID, the method creates three mappings: by full component ID (e.g., "src.component.Display.Display"), by component name only (e.g., "Display"), and by the last ID segment. This multi-strategy approach handles real-world naming ambiguities where different contexts reference the same component using different naming conventions. The Reader Agent's requests might use full IDs while code uses short names; this mapping strategy ensures lookups succeed regardless. The method logs mapping statistics for transparency, creating typically small lookup dictionaries (tens to hundreds of entries) rather than searching the full component_map (potentially thousands or tens of thousands of entries).

## Component Source Code Retrieval

The `_fetch_component_source()` method retrieves source code for requested dependencies. It attempts direct lookup in the dependency lookup using the provided name, returning None if not found. Upon finding a component, it performs type checking between the expected type ('class', 'function', 'method') and actual component type. Notably, the method includes flexible type matching: if types don't match, it logs a warning but still returns the source code rather than failing. This tolerance for type mismatches is intentional—it handles cases where the Reader Agent's type classification might be incorrect (e.g., React components misclassified as methods). By returning source anyway and logging warnings, the agent allows downstream agents to handle ambiguity rather than failing silently. The method returns component.source_code or an empty string, ensuring consistent string-type returns.

The `_fetch_caller_source()` method retrieves source code for components that call the focal component, using direct component_map lookups rather than the scoped dependency lookup (callers may be any repository component). Both retrieval methods are simple O(1) lookups, with logging providing visibility into missing components without interrupting processing.

## External Query Handling

The `_fetch_external_query()` method handles expensive external information retrieval via LLM queries. The method constructs a detailed prompt requesting structured explanations: brief definition (1-2 sentences), key characteristics (2-3 sentences), usage context (1 sentence). This structure ensures consistent, appropriately-detailed LLM responses. The method uses BaseAgent's `generate_with_llm()` with: temperature=0.5 (balancing consistency and variability), max_tokens=500 (limiting response length), and system prompt establishing technical expertise context. The method handles exceptions by returning error strings "[API Error: ...]" rather than propagating exceptions, allowing processing to continue despite external API failures. This error resilience is important since external calls are less reliable than local lookups.

## Processing Pipeline Orchestration

The main `process()` method orchestrates complete processing. It begins by retrieving the focal component and Reader Agent's output, then parses the request into normalized structure. The agent then walks through requested information sequentially: (1) For internal dependencies, it gets dependencies via `_get_dependencies()`, builds dependency lookup via `_build_dependency_lookup()`, and fetches source code for each requested class, function, and method, checking for duplicates to avoid redundant fetIches; (2) For caller information, if CALLED_BY=true, it gets callers via `_get_callers()` and fetches each caller's source; (3) For external queries, it first checks accumulated_context to avoid duplicates, then calls `_fetch_external_query()` for new queries. Results are organized into output structure with counts tracked for logging, saved to timestamped JSON files, and converted to SearcherOutput object. The method returns AgentResult with complete metadata including dependency counts and result summaries.

## Error Handling and Graceful Degradation

The Searcher Agent implements multi-layer error handling ensuring partial results rather than failures: at component level, missing lookups return None/empty strings; at graph level, NetworkXError exceptions are caught and logged with empty returns; at LLM level, API failures return error strings; at parsing level, missing XML elements apply defaults; at file I/O level, save failures log warnings without interrupting processing. This layered approach ensures failures in any subsystem don't cascade—the agent always produces output, potentially incomplete but present.

## Performance Optimization

The agent achieves efficient processing through three key optimizations: (1) **Pre-computed reverse graph**: Computed once at startup using NetworkX's efficient reverse() algorithm, avoiding repeated expensive inversion during queries; (2) **component_map O(1) lookups**: All components accessible in constant time by ID; (3) **Scoped dependency lookup**: Each component's lookup focuses only on direct dependencies, typically 5-10 entries, not the full repository. For large codebases (10,000+ components), setup is O(n) but per-component processing is O(k+m+q) where k = direct dependencies, m = callers, q = external queries. This is dramatically more efficient than O(n) per component without graph-based lookups.

## Output Persistence and Integration

The agent persists results in two tiers: individual timestamped JSON files per component in data/intermediate/agent_output/searcher/ for debugging, and consolidated JSON files for batch analysis. JsonFormat (rather than XML) matches downstream Writer Agent expectations. Integration upstream with Reader Agent (receives XML/object requests) and downstream with Writer Agent (provides SearcherOutput) is clean through standardized data structures. The agent accesses Navigator's component_map and dependency_graph laterally to understand codebase structure.

## Practical Example

Consider retrieving context for function `process_data` calling `transform`. Reader's request specifies: INTERNAL CALLS FUNCTION=[transform], CALLED_BY=true, EXTERNAL CLASSIFICATION=standard_library (no query). Searcher Agent's workflow: (1) Gets dependencies of process_data, finding transform; (2) Builds lookup with transform's CodeComponent; (3) Fetches transform's source via `_fetch_component_source()`; (4) Gets callers via reverse graph (assume analyze_dataset, pipeline_runner); (5) Fetches source for each caller; (6) Skips external retrieval (standard library). Returns SearcherOutput with: dependency_contexts=[DependencyContext for transform], reference_contexts=[ReferenceContext for analyze_dataset, pipeline_runner], external_contexts=[], summary="Found 1 dependency, 2 references, 0 external". Writer Agent uses this to generate documentation including dependencies, usage examples, and behavior.

## Scalability Analysis

Scalability characteristics are excellent for large codebases: component lookups O(1), dependency retrieval O(k) where k is typically 2-10, caller retrieval O(m) where m is typically 1-5, full processing O(k+m+q) where q = external queries. Space complexity O(n) for component_map and graphs. For 10,000 components with average 5 dependencies and 3 callers each: setup is O(10,000) but per-component processing is O(80)—very efficient. Pre-computed reverse graph is critical; without it, caller finding would degrade to O(n) per component.

## Configuration and Flexibility

The agent is configuration-minimal by design, responding to Reader's requests rather than enforcing built-in policies: component_map/dependency_graph set via `set_repository_data()`, summary_cache clearable between runs, output_dir customizable, LLM parameters (temperature, max_tokens) adjustable in `_fetch_external_query()`. This design allows adaptation to different codebases and workflows without code changes.

## Key Contributions

The Searcher Agent contributes to the documentation pipeline through: (1) efficient graph-based lookups reducing lookup time from O(n) to O(k+m); (2) flexible multi-format parsing supporting XML and object inputs; (3) graceful error handling ensuring partial results; (4) intelligent dependency scoping reducing search space; (5) type-tolerant matching handling real-world classification ambiguities; (6) selective external retrieval avoiding expensive queries except when requested; (7) clear internal/external distinction enabling cost-effective operation. Together, these enable reliable, efficient context retrieval enabling high-quality documentation generation.

## Conclusion

The Searcher Agent represents a pragmatic approach to context retrieval in automated documentation systems. By leveraging efficient graph algorithms from the Navigator, parsing structured requests from the Reader, and implementing multi-layer error handling, it reliably retrieves comprehensive context for documentation generation. Its pre-computed graph structures and O(1) lookups enable processing of large codebases without performance degradation. The clear separation between internal (fast, free) and external (slow, expensive) retrieval ensures cost-effective operation. Integration as a bridge agent between Reader and Writer creates a coherent documentation pipeline balancing accuracy, efficiency, and cost-effectiveness.
