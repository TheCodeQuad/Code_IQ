# Navigator Module: Research Paper Methodology

## Overview

The Navigator Module is the foundational code parsing and multi-language abstraction layer in the documentation pipeline, responsible for transforming raw source code from multiple programming languages into a unified Intermediate Repository (IR) containing complete component metadata and dependency graphs. Operating through a language-agnostic architecture, the Navigator executes a four-phase pipeline: (1) file discovery and adapter routing, (2) component extraction via Tree-sitter-based AST parsing, (3) dependency resolution through source code analysis, and (4) semantic abstraction and graph construction. The output is a complete mapping of all code components (classes, functions, methods, variables) with dependencies, control flow metadata, and semantic annotations, enabling downstream agents to reason about code without language-specific knowledge.

## Architecture: Language-Agnostic Design Pattern

The Navigator's core innovation is language agnosticism achieved through pluggable language adapters implementing a common interface. Each language adapter (PythonAdapter, JavaScriptAdapter, TypeScriptAdapter, JavaAdapter) encapsulates language-specific parsing details while the RepositoryParser orchestrates the unified parsing pipeline. The AdapterRegistry matches source files to adapters by extension, routing each file to the appropriate parser. This design enables supporting new languages by implementing a new adapter without modifying the core pipeline or downstream agents. All parsed output normalizes to the unified CodeComponent schema, enabling polymorphic processing across languages.

## Code Component Model

All code entities are represented using CodeComponent, capturing language-agnostic information: id (unique identifier like "src.utils.math:add"), name, type (CLASS, FUNCTION, METHOD, VARIABLE, GLOBAL_VARIABLE, etc.), language, location (file and line ranges), source_code, signature, docstring, parameters with type hints, return_type, complexity (cyclomatic or equivalent), lines_of_code, depends_on (set of component IDs), control_flow (detects async, loops, branches, exceptions), is_public (visibility), imports (for external retrieval), and metadata (language-specific annotations). This unified model allows Reader, Searcher, and Writer to operate identically across Python, JavaScript, Java, and TypeScript without language-specific processing.

## Phase 1: File Discovery and Routing

The Navigator walks the entire repository directory tree, identifying source files by extension. For each matched file, the adapter registry routes the file to the appropriate language adapter. Unsupported files (configuration, documentation, binaries) are silently skipped, allowing mixed repositories. This phase is O(F) where F is total files, dominated by filesystem operations rather than parsing.

## Phase 2: Component Extraction (PASS 1)

Each language adapter independently parses files using Tree-sitter (with Python AST fallback), then traverses the parse tree to extract components. The extraction identifies node types representing code entities (class declarations, function definitions, variable assignments) and extracts metadata: location from AST, signature from declaration, docstring from first string literal in body, parameters and types from declarations, visibility from naming conventions (e.g., leading underscore = private in Python), decorators for special properties (async, API endpoints), and control flow characteristics (loops, async operations, exception handling). Module paths are computed by converting file paths to dot-separated names (src/utils/math.py → src.utils.math), and component IDs combine module paths with component names. Adapters normalize to CodeComponent objects aggregated into the all_components dictionary. This phase is O(L) per file where L is line count (Tree-sitter is linear).

## Phase 3: Dependency Resolution (PASS 2)

Each adapter's `resolve_dependencies()` method analyzes component source code to identify dependencies through pattern detection: explicit function/method calls, type annotations, class instantiation, inheritance, attribute access, and imports. Dependency resolution uses regex pattern matching and AST traversal to identify these relationships, then performs lookup against all_components to map dependency names to component IDs. The strategy handles ambiguity when dependencies can't be resolved cleanly by applying heuristics (inferring owner class from method calls, searching for module names in imports). Dependencies are accumulated as sets, automatically handling duplicates. Circular dependencies are detected via Tarjan's Strongly Connected Components algorithm but not removed, allowing the pipeline to document circular relationships. This phase is O(C × D) where C = components and D = average dependency references.

## Phase 4: Semantic Abstraction (PASS 3)

Documentation-oriented dependency abstraction transforms low-level dependencies into high-level relationships suitable for documentation via rule-based transformations: (1) **Class-level abstraction**: Classes depend on other classes, not individual methods, simplifying class documentation; (2) **Method abstraction**: Methods depend on classes, not other methods, providing higher-level semantics; (3) **Self-reference elimination**: Components don't depend on themselves; (4) **Global variable preservation**: Shared mutable state is preserved as explicit dependencies; (5) **Circular dependency resolution**: Circular edges are detected and reported. These rules operate through four passes over all components, updating depends_on sets to reflect documentation-oriented relationships rather than implementation details.

## Dependency Graph Construction

From abstracted dependencies, the Navigator builds a directed acyclic graph (DAG) where nodes are components and edges A → B represent "A depends on B". The graph is represented as an adjacency list enabling O(1) neighbor lookups. Cycle detection uses Tarjan's algorithm to find all strongly connected components; SCCs with multiple nodes are cycles. Cycle resolution (if applied) removes lowest-priority edges to break cycles. The final DAG feeds into downstream agents for context retrieval and dependency analysis.

## Language-Specific Adapter Interface

Each adapter implements three methods: (1) **parse(source_code)** converts source to parse tree using language-specific parser (Tree-sitter for most languages, Python AST as fallback); (2) **extract_components(tree, source, file_path, module_path)** traverses parse tree identifying components, extracting metadata, normalizing to CodeComponent objects; (3) **resolve_dependencies(component, tree, source, all_components)** analyzes source code for dependency patterns, resolves names to component IDs, returns Set[str]. This interface enables new languages to be supported by implementing these three methods.

## Component Type Hierarchy

The Navigator recognizes component types consistently across languages: CLASS, FUNCTION, METHOD, ARROW_FUNCTION (JavaScript/TypeScript shorthand), ASYNC_FUNCTION, VARIABLE, GLOBAL_VARIABLE, CLASS_VARIABLE, INTERFACE, ENUM, MODULE, OTHER. Language-specific constructs (Python magic methods, JavaScript closures, Java inner classes) normalize to the common hierarchy, enabling polymorphic downstream processing.

## Practical Example: Multi-Language Dependency Resolution

Consider a JavaScript function calling a utility from a TypeScript module:

```javascript
// user-api.js
import { validateEmail } from './validators';
export function createUser(email: string) {
  if (validateEmail(email)) {
    return db.save({ email });
  }
}
```

Navigator's processing:
1. **Phase 1**: Route user-api.js to JavaScriptAdapter via .js extension
2. **Phase 2 (Extraction)**: Identify function createUser, extract parameters email with type string, identify return type inference from call context
3. **Phase 3 (Dependencies)**: Detect import statement → depends on validators module; detect call validateEmail() → depends on validateEmail function; detect db.save() call → depends on db (global or imported)
4. **Phase 4 (Abstraction)**: Import becomes Module dependency; function call remains function dependency; object method call abstracts if db is a class

Output: CodeComponent(id="user-api:createUser", depends_on={"validators:validateEmail", "db" or "models:Database"})

## Complexity Analysis and Scalability

Navigator complexity: O(F × L) for parsing phase where F = files, L = average lines; O(C × D) for dependency resolution where C = components, D = dependency density. Space complexity O(C + E) where E = edges (dependencies). For 10,000 files with 100 lines average, 50,000 components: parsing is O(1,000,000) = linear in source size, completes in seconds to minutes. No exponential or factorial operations; highly scalable to large codebases.

## Error Handling and Robustness

Navigator implements defensive strategies: UTF-8 encoding with error-ignore tolerance for unparseable files; fallback to Python AST if Tree-sitter unavailable; silent skipping of unsupported files; graceful degradation when dependencies can't be resolved; component format normalization handling different adapter returns; circular dependency detection and logging without failure. These strategies ensure partial results rather than crashes, enabling processing of diverse real-world repositories.

## Output: The Intermediate Repository (IR)

Final output integrates: component dictionary (component ID → CodeComponent with all metadata), dependency graph (component ID → Set[component IDs] it depends on), and optional exports (JSON for debugging, serialized graph for external tools). The IR is language-neutral, enabling downstream Python code to operate on Java/JavaScript/TypeScript components identically.

## Integration with Documentation Pipeline

Navigator feeds: Reader Agent (analyzes CodeComponent for complexity and information needs), Searcher Agent (traverses dependency_graph and component_map for context retrieval), Writer Agent (generates documentation from source_code and metadata), Verifier Agent (calibrates expectations from component type and complexity). Errors in Navigator parsing propagate through all downstream agents. The Navigator is the critical foundation: accurate parsing enables accurate documentation.

## Key Contributions

Navigator contributes through: (1) language-agnostic code parsing and transformation, (2) complete repository-wide component extraction, (3) accurate multi-pass dependency resolution, (4) semantic abstraction for documentation relevance, (5) robust handling of real-world code complexity, (6) unified code representation enabling polymorphic downstream processing. These enable the documentation pipeline to operate across multiple languages without language-specific implementations in downstream agents.

## Conclusion

The Navigator Module demonstrates how language-agnostic architecture combined with pluggable language adapters achieves multi-language support without duplicating parsing logic. By accurately extracting components and resolving dependencies through semantic abstraction suited to documentation, it provides the foundation for the entire automated documentation pipeline. Its language-independent output enables readers, searchers, and writers to generate high-quality documentation across Python, JavaScript, TypeScript, and Java codebases without modification.
