# Searcher Agent: Detailed Working Methodology

## Executive Summary

The Searcher Agent is a context retrieval component in the automated code documentation pipeline responsible for gathering evidence about code components from two primary sources: (1) the internal codebase through dependency graph traversal and component lookups, and (2) external sources through LLM-based knowledge queries. Operating as the bridge between the Reader Agent's information requests and the Writer Agent's documentation generation, the Searcher Agent consumes structured XML requests from the Reader Agent and returns comprehensive context including dependency implementations, usage examples, and external knowledge about algorithms and techniques. Its design emphasizes efficiency through graph-based lookups, intelligent caching, and selective external retrieval only when truly novel concepts are involved.

## Architecture and Core Components

The Searcher Agent is built on four critical architectural components that work together to provide complete contextual information. The **component_map** is a dictionary data structure that maps component IDs to their corresponding CodeComponent objects from the Navigator, enabling O(1) lookup time for any component in the repository. The **dependency_graph** is a NetworkX directed graph provided by the Navigator where nodes are components and directed edges represent "depends on" relationships. The **reverse_graph** is an efficiently-computed reverse of the dependency graph using NetworkX's native reverse() method, enabling O(1) lookup of all components that call or use a given component (reverse dependencies). The **summary_cache** is a dictionary that caches LLM-generated summaries for dependencies to avoid redundant API calls when the same component is analyzed multiple times. Additionally, the SearcherAgent maintains consolidated output storage and file persistence mechanisms for debugging and analysis.

## Data Flow: From Reader Request to Context Retrieval

The Searcher Agent's processing pipeline begins when it receives an AgentContext containing the focal component (the component being documented) and a previous result from the Reader Agent. The Reader Agent's output specifies exactly what information is needed: which internal dependencies should be retrieved, whether callers should be found, and what external knowledge should be fetched. The Searcher Agent's job is to fulfill these requests by traversing the codebase, looking up component implementations, and querying external sources as needed. The results are packaged into a SearcherOutput object containing structured information about dependencies, callers, and external knowledge that the downstream Writer Agent can use to generate comprehensive documentation.

## Data Structures for Context Organization

The Searcher Agent defines four specialized dataclasses that organize retrieved information with specific metadata. **DependencyContext** represents a single code component that the focal component depends on, containing the component ID, name, a text summary (first 200 characters), function/method signature, existing docstring if available, usage pattern information, and a source code snippet. This structure allows the Writer Agent to understand not just what the dependency is, but how it fits into the broader codebase. **ReferenceContext** represents a place where the focal component is used (a caller), containing the caller's ID and name, usage examples extracted from the calling code, detailed call sites with location information, and a usage summary explaining the context. This helps document how and where the component is actually used in practice. **ExternalContext** represents external knowledge retrieved about novel algorithms or techniques, containing the original query, classification of knowledge type, a summary of the knowledge, detailed explanation, and reference links. This separates external knowledge from internal codebase information, allowing the Writer Agent to distinguish between documented internal code and researched external concepts. **SearcherOutput** is the final aggregated output, containing the focal component ID, lists of dependency contexts, reference contexts, and external contexts, a search summary string, and metadata about the search including counts and error information.

## Phase 1: Repository Data Loading

The Searcher Agent initializes with repository metadata through the `set_repository_data()` method, which must be called before processing any components. This method accepts two critical inputs: a complete list of CodeComponent objects from the Navigator and the dependency graph (as a NetworkX DiGraph). The method constructs the component_map by creating a dictionary where each component ID maps to its CodeComponent object, enabling O(1) lookups. It also stores the dependency_graph directly for forward dependency traversal. Critically, it uses NetworkX's native `reverse(copy=False)` method to create the reverse_graph, which efficiently computes the inverse of the dependency graph without creating a full copy of the data structure. This reverse graph enables finding callers in O(1) time complexity. The initialization logs the total number of components and edges, providing visibility into the repository's scope and complexity. This setup phase is crucial because all subsequent lookups depend on these data structures being properly initialized and available.

## Phase 2: Parsing Reader Agent Requests

The Searcher Agent must parse requests from the Reader Agent, which can be provided in two formats: XML strings or ReaderOutput objects. The `_parse_reader_request()` method acts as a dispatcher that detects the input format and routes to the appropriate parser. The XML parser, `_parse_reader_xml()`, expects well-formed XML with specific structure: a REQUEST element containing INTERNAL and EXTERNAL sections. The INTERNAL section contains CALLS elements with comma-separated lists of CLASS, FUNCTION, and METHOD identifiers, and a CALLED_BY boolean flag. The EXTERNAL section contains QUERY elements with comma-separated queries. The parser validates each expected element, handles missing elements gracefully, and converts text content into structured dictionaries. For example, the string "func1,func2,func3" in a FUNCTION element is parsed into ["func1", "func2", "func3"]. The object parser, `_parse_reader_output_object()`, extracts similar information from ReaderOutput object attributes, handling the slightly different structure where requests are stored as lists of request objects rather than XML elements.

The resulting parsed request has a standardized structure regardless of input format: a dictionary with 'internal' and 'external' keys, where 'internal' contains 'calls' (with CLASS, FUNCTION, METHOD sublists) and 'called_by' (boolean), and 'external' contains 'queries' (list of strings). This normalization is critical because it allows the rest of the agent to work with a consistent data structure, and it provides a clear contract between the Reader Agent's output format and the Searcher Agent's processing logic.

## Phase 3: Dependency Graph Traversal

The Searcher Agent uses two key methods to traverse the dependency graph and identify which components to retrieve. The `_get_dependencies()` method takes a component ID and returns all component IDs that the focal component directly depends on by calling NetworkX's `successors()` method on the dependency graph. This returns an iterator of successor nodes (components that this component points to). The method handles the case where a component is not in the graph gracefully by catching NetworkXError exceptions and returning an empty list. The `_get_callers()` method performs the inverse operation by taking a component ID and returning all component IDs that call or use the focal component by calling `successors()` on the reverse_graph. This is efficient because the reverse graph is pre-computed, avoiding the need to iterate through all components to find callers.

These two methods are the foundation of the agent's graph-based lookup strategy. Together, they enable the agent to understand a component's full context within the codebase: what it depends on (its requirements) and what depends on it (its usage patterns). The O(1) lookup time for both forward and reverse dependencies is critical for processing large codebases efficiently.

## Phase 4: Intelligent Dependency Lookup

The `_build_dependency_lookup()` method creates a focused lookup dictionary scoped only to the components that are actual dependencies of the focal component. Rather than searching the entire component_map (which could be very large), this method builds a smaller, targeted lookup that maps multiple possible names to the same component. For each dependency component ID, the method creates three mappings: (1) by full component ID (e.g., "src.component.Display.Display"), (2) by component name only (e.g., "Display"), and (3) by the last segment of the ID (e.g., "Display" from "src.component.Display.Display"). This multi-strategy mapping handles the fact that Reader's requests might reference components in different ways—sometimes by full ID, sometimes by short name, sometimes by the final segment.

The insight behind this approach is that different parts of the codebase and different agents might reference the same component using different naming conventions. By creating multiple mappings to the same component object, the agent ensures that lookups succeed regardless of which naming convention is used. The method logs each mapping created and the total number of mappings, providing transparency into the lookup structure. This is a practical solution to the problem of ambiguous component naming across large codebases.

## Phase 5: Fetching Component Source Code

The `_fetch_component_source()` method retrieves the actual source code for a requested dependency. It takes three parameters: the component name (which may be a full ID or short name), the expected component type ('class', 'function', or 'method'), and the dependency lookup dictionary. The method first attempts direct lookup in the dependency lookup using the provided name, returning None if not found. If found, the method performs a type check between the expected type and the actual component type. This type check includes handling for ComponentType enum objects, normalizing them to lowercase strings for comparison. Notably, the method includes a flexible type matching strategy: if the types don't match exactly, it logs a warning but still returns the source code instead of failing. This tolerance for type mismatches is intentional—it handles cases where the Reader Agent's type classification might be incorrect (e.g., classifying a React component as a method when it should be a class). By returning the source anyway and logging a warning, the agent allows downstream agents to handle ambiguous cases rather than failing silently.

The method returns the component's source_code field if available, or an empty string if the source code is None. This ensures that the return value is always a string, allowing downstream processing to work uniformly whether the source exists or not.

## Phase 6: Fetching Caller Information

The `_fetch_caller_source()` method retrieves the source code for a component that calls the focal component (a caller or reference). Unlike dependency fetching, which looks up components in the dependency_lookup dictionary, this method looks up callers directly in the component_map. The method is straightforward: it looks up the caller component ID in the component_map, logs if the component is not found, and returns the source code if the component exists. The caller might not be in the dependency lookup because the lookup is scoped only to this component's dependencies—callers come from reverse graph traversal and may be any component in the repository.

## Phase 7: External Query Handling

The `_fetch_external_query()` method handles the most expensive type of information retrieval: querying external sources (typically via LLM) for knowledge about novel algorithms and techniques. The method takes a query string (e.g., "Dijkstra algorithm") and constructs a detailed prompt that asks the LLM to explain the concept in a way suitable for code documentation. The prompt explicitly requests a specific structure: a brief definition (1-2 sentences), key characteristics or how it works (2-3 sentences), and when/why it's used (1 sentence). This structured request ensures that the LLM-generated explanations are consistent in length and detail.

The method uses BaseAgent's `generate_with_llm()` method with specific parameters: temperature is set to 0.5 for a balance between consistency and some variability, max_tokens is set to 500 to limit response length, and a system prompt establishes that the LLM should act as a technical knowledge expert providing clear, concise explanations. The method handles exceptions by returning an error string "[API Error: ...]" rather than propagating the exception, allowing processing to continue even if external queries fail. This error resilience is important because external API calls are less reliable than local codebase lookups.

## Phase 8: Full Processing Pipeline

The main `process()` method orchestrates all the above components into a complete workflow. It begins by checking that the focal component is available and logging the component ID. It then retrieves the Reader Agent's output from the previous agent's results using `context.get_result('reader')`. The Reader output is parsed into a standardized request using `_parse_reader_request()`. If parsing fails, the agent returns an empty result rather than crashing.

The agent then walks through each type of requested information in sequence:

**For internal dependencies**, it retrieves the list of dependencies using `_get_dependencies()`, builds the dependency lookup using `_build_dependency_lookup()`, and then for each class, function, and method in the Reader's request, it fetches the component source using `_fetch_component_source()`. The agent checks before fetching whether the component has already been fetched to avoid duplicates.

**For caller information**, if the Reader requested CALLED_BY=true, the agent retrieves the list of callers using `_get_callers()` and then fetches each caller's source code using `_fetch_caller_source()`.

**For external information**, for each query in the Reader's EXTERNAL section, the agent first checks an accumulated_context (tracking information already retrieved earlier in the pipeline) to avoid duplicate external queries. If the information hasn't been fetched yet, it calls `_fetch_external_query()` to retrieve explanations from the LLM.

All retrieved information is organized into the output structure, with counts tracked for logging. The agent saves the individual output to a JSON file for debugging using `_save_output_to_file()` and adds the output to consolidated_outputs for later batch saving. Finally, the raw dictionary output is converted to a SearcherOutput object for consistency with downstream Agent expectations.

## Error Handling and Resilience

The Searcher Agent implements multiple layers of error handling ensuring graceful degradation. At the component level, missing components in lookups return None/empty strings rather than raising exceptions, allowing processing to continue with partial results. At the graph level, NetworkXError exceptions from graph operations are caught and logged, returning empty results for missing components. At the LLM level, external query failures return error strings rather than propagating exceptions. At the parsing level, missing XML elements are handled gracefully, with defaults applied when elements are absent. At the file I/O level, save failures log warnings but don't interrupt processing. This multi-layered approach ensures that failures in any subsystem don't cascade to others—the agent always produces output, even if some parts are incomplete.

## Caching and Performance Optimization

While the code includes a summary_cache data structure, the current implementation primarily benefits from the pre-computed reverse_graph in terms of performance. The reverse_graph avoids the need to do expensive reverse lookups by pre-computing the inverse relationship using NetworkX's efficient algorithms. For large graphs with thousands of components, computing the reverse graph once at startup is far more efficient than computing it repeatedly during queries. The component_map provides O(1) lookup for any component by ID, which is critical for fast processing. The dependency_lookup built per component narrows the search space, making subsequent lookups very fast even in small scopes. Together, these optimizations ensure that the agent can process large codebases efficiently without repeated expensive computations.

## Output Persistence and Consolidation

The Searcher Agent saves results in two tiers for different purposes. Individual component results are saved to timestamped JSON files in data/intermediate/agent_output/searcher/, creating files like "src_component_Display_Display_20260310_102030.json". These individual files contain the component ID, timestamp, and complete output for debugging and analysis. The `save_consolidated_output()` method collects all processed components into a single JSON file containing overall metadata (timestamp and total component count) and all component outputs. This consolidated output enables batch analysis, validation across the entire run, and tracking of overall coverage and statistics. The format is JSON rather than XML (unlike Reader Agent) to match the downstream Writer Agent's expected input format.

## Integration Points

The Searcher Agent integrates with three other components: **Upstream from Reader Agent**, receiving XML or object-based requests specifying which information to retrieve. **Downstream to Writer Agent**, providing structured SearcherOutput containing dependency contexts, reference contexts, and external contexts. **Lateral with Navigator's Repository**, accessing the component_map and dependency_graph to understand the codebase structure. The integration is clean: the Reader Agent's request format is standardized (either XML or object), the SearcherOutput is a well-defined dataclass, and the repository data is accepted in standard form (list of components and NetworkX graph).

## Practical Example: Processing a Complex Function

Consider retrieving context for a function `process_data` that internally calls `transform`. The Reader Agent's request specifies: INTERNAL CALLS FUNCTION=[transform], CALLED_BY=true, EXTERNAL CLASSIFICATION=standard_library (no external query). 

The Searcher Agent's process:

1. Gets dependencies of process_data, finding transform is a direct dependency
2. Builds a dependency lookup including transform's CodeComponent
3. Fetches the source code for transform from the dependency lookup via `_fetch_component_source()`
4. Gets all callers of process_data using the reverse graph
5. For each caller (say analyze_dataset and pipeline_runner), fetches their source code
6. Skips external query retrieval since classification is standard_library
7. Returns SearcherOutput with:
   - dependency_contexts: [DependencyContext for transform with its source code]
   - reference_contexts: [ReferenceContext for analyze_dataset, ReferenceContext for pipeline_runner]
   - external_contexts: [] (empty because standard library)
   - search_summary: "Found 1 dependency, 2 references, 0 external"

The Writer Agent receives this SearcherOutput and uses it to generate documentation that includes what process_data depends on, where it's used, and what it does.

## Scalability Characteristics

The Searcher Agent scales well to large codebases:
- **Component lookups**: O(1) using component_map
- **Dependency retrieval**: O(k) where k is the number of direct dependencies (typically small)
- **Caller retrieval**: O(m) where m is the number of direct callers (typically small)
- **Full processing**: O(k + m + q) where q is the number of external queries
- **Memory**: O(n) for the component_map and graphs where n is total components

For a codebase with 10,000 components where each has ~5 dependencies and ~3 callers, total processing is O(10000) in setup and O(80) per component in processing—very efficient. The pre-computed reverse graph is key to this scalability; without it, finding callers would be O(n) per component.

## Configuration and Customization

The Searcher Agent has few configuration points because most behavior is determined by Reader's requests:
- **component_map and dependency_graph**: Set via set_repository_data()
- **summary_cache**: Can be cleared between runs to force fresh LLM calls
- **output_dir**: Can be customized in __init__ to persist outputs elsewhere
- **LLM parameters**: temperature and max_tokens in _fetch_external_query() can be adjusted

The agent is largely configuration-free by design—it responds to Reader's requests rather than having built-in policies about what to retrieve.

## Key Contributions

The Searcher Agent contributes to the documentation pipeline through: (1) efficient graph-based lookups enabling fast dependency and caller retrieval, (2) flexible parsing supporting multiple input formats, (3) graceful error handling ensuring partial results rather than failure, (4) intelligent scope limitation through dependency lookup focusing on relevant components, (5) type-tolerant component matching handling real-world naming ambiguities, and (6) selective external retrieval avoiding expensive queries except when requested. Together, these enable reliable, efficient context retrieval from complex codebases.

## Conclusion

The Searcher Agent represents a pragmatic approach to context retrieval in documentation generation. By leveraging efficient graph structures from the Navigator, parsing structured requests from the Reader, and providing flexible lookup strategies, it enables the Writer Agent to access all necessary information for comprehensive documentation generation. Its error handling, caching strategies, and output persistence make it suitable for production use on large codebases. The clear separation between internal codebase retrieval and expensive external retrieval ensures cost-effective operation while maintaining documentation quality.
