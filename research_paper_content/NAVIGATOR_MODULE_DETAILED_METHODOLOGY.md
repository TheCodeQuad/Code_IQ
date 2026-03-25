# Navigator Module: Detailed Working Methodology

## Executive Summary

The Navigator Module is the foundational code parsing and analysis component of the documentation pipeline, responsible for transforming raw source code from multiple programming languages (Python, JavaScript, TypeScript, Java) into a unified, structured intermediate representation called the Intermediate Repository (IR). The Navigator operates through a sophisticated multi-pass pipeline consisting of four major phases: (1) file scanning and language detection, (2) component extraction via abstract syntax tree (AST) parsing using Tree-sitter, (3) dependency resolution across the entire codebase, and (4) dependency abstraction and consolidation for documentation purposes. The output is a complete mapping of all code components (classes, functions, methods, variables) with their full dependency graphs, control flow characteristics, and semantic metadata, enabling downstream agents to understand code relationships without language-specific knowledge.

---

## Overall Architecture and Design Philosophy

The Navigator follows a **language-agnostic architecture** where language-specific parsing details are encapsulated in pluggable adapter classes, while the core parsing orchestration, dependency resolution, and graph analysis remain language-independent. This design allows the Navigator to support new languages (Rust, Go, C++, etc.) without modifying the core pipeline—only by implementing a new language adapter.

The architecture consists of five major layers:

### **Layer 1: File Scanner and Discovery**
Recursively walks the repository directory structure, identifying source files based on language-specific file extensions (.py, .js, .ts, .java, etc.) and routing each file to the appropriate language adapter.

### **Layer 2: Language Adapter Registration**
The AdapterRegistry maintains a registry of available language adapters, each implementing the BaseLanguageAdapter interface. When a file is discovered, the registry matches it to an adapter based on file extension.

### **Layer 3: Tree-Sitter Parsing Infrastructure**
Tree-sitter is a robust, language-agnostic parser generator providing parse trees for supported languages. The ParserFactory creates language-specific parsers using Tree-sitter's pre-built language grammars, with fallback to Python's native AST parser for Python code.

### **Layer 4: Language-Specific Adapters**
Each language adapter (PythonAdapter, JavaScriptAdapter, TypeScriptAdapter, JavaAdapter) implements three core methods: (1) `parse()` converts source code to a parse tree, (2) `extract_components()` traverses the parse tree to identify and extract code components, (3) `resolve_dependencies()` analyzes each component to identify what other components it depends on.

### **Layer 5: Dependency Graph Construction and Analysis**
After all components are extracted and dependencies are resolved, the Navigator constructs a directed acyclic graph (DAG) representing the dependency structure, performs cycle detection and resolution, applies documentation-oriented semantic rules, and exports the final component repository.

---

## Component Model: CodeComponent

All code entities are represented using the unified **CodeComponent** dataclass, which captures language-agnostic structural and semantic information:

```
CodeComponent:
  - id: str                          # Unique identifier (e.g., "src.utils.math.add")
  - name: str                        # Human-readable name
  - type: ComponentType enum         # CLASS, FUNCTION, METHOD, VARIABLE, GLOBAL_VARIABLE, etc.
  - language: str                    # "python", "javascript", "typescript", "java"
  - location: Location               # File path, start line, end line
  - source_code: str                 # Full source code text
  - signature: str                   # Function/method signature
  - docstring: Optional[str]         # Existing documentation if present
  - parameters: List[Parameter]      # For functions/methods: name, type hint
  - return_type: Optional[str]       # Return type annotation
  - complexity: int                  # Cyclomatic complexity or equivalent
  - lines_of_code: int               # Physical lines
  - depends_on: Set[str]             # IDs of components this depends on
  - control_flow: Dict               # Async, loops, branches, exceptions, etc.
  - is_public: bool                  # Public/private visibility
  - imports: List[str]               # External imports (for external retrieval)
  - metadata: Dict                   # Language-specific metadata
```

This unified model allows the downstream Reader, Searcher, and Writer agents to work with code without language-specific knowledge. A Python class, JavaScript class, Java class, and TypeScript class all become the same ComponentType.CLASS, enabling uniform processing.

---

## Phase 1: File Discovery and Adapter Selection

The Navigator begins by creating an **AdapterRegistry** containing instances of all supported language adapters. It then walks the entire repository directory tree recursively, examining each file's extension against the registered adapters' extension lists. When a match is found, the file's contents are read (with UTF-8 encoding and error-tolerance for robustness) and routed to the matched adapter. Files without matching adapters are silently skipped, allowing the Navigator to gracefully handle mixed repositories containing configuration files, documentation, and other non-code files.

```
for each file in repository:
    if extension matches adapter:
        read file contents, create context, call adapter
```

---

## Phase 2: Component Extraction (PASS 1)

In the first pass, each language adapter independently extracts components from its files. The extraction process varies by language but follows a common pattern:

### **2.1 Parse Tree Generation**
The adapter's `parse()` method converts source code into a parse tree. For most languages, this uses Tree-sitter:

```python
# Tree-sitter parsing (most languages)
parser = get_ts_parser("language_name")
tree = parser.parse(bytes(source_code, "utf8"))
```

For Python, as a fallback when Tree-sitter is unavailable:

```python
# Python native AST fallback
import ast
tree = ast.parse(source_code)
```

The tree structure represents the complete syntactic structure of the code as nested nodes.

### **2.2 Component Extraction via AST Traversal**
The adapter traverses the parse tree recursively to identify and extract components. This traversal looks for specific node types that represent code entities:

**For Python**:
- ClassDef nodes → CLASS components
- FunctionDef nodes → FUNCTION or METHOD components (distinguished by parent context)
- Assignments at module level → GLOBAL_VARIABLE components
- Assignments within classes → CLASS_VARIABLE components

**For JavaScript/TypeScript**:
- ClassDeclaration nodes → CLASS components
- FunctionDeclaration nodes → FUNCTION components
- ArrowFunction nodes → ARROW_FUNCTION components
- VariableDeclaration at top level → GLOBAL_VARIABLE components

**For Java**:
- ClassDeclaration nodes → CLASS components
- MethodDeclaration nodes → METHOD components
- FieldDeclaration at class level → CLASS_VARIABLE components

### **2.3 Component Metadata Extraction**
For each identified component, the adapter extracts metadata:

- **Location**: Start and end line numbers from the AST
- **Signature**: The function/method declaration statement (parameter list)
- **Docstring**: The first string literal in the function/method body (documentation)
- **Parameters**: For functions/methods, extract parameter names and type hints if available
- **Return type**: Extract return type annotations if present
- **Visibility**: Detect public/private/protected using language conventions (e.g., leading underscore in Python means private)
- **Decorators**: Extract decorator metadata (used for API endpoint detection, async detection, etc.)
- **Control flow**: Initial detection of async/await, loops, branches, exceptions

### **2.4 Module Path Resolution**
The file path is converted to a module path by:
1. Computing relative path from repository root
2. Replacing directory separators with dots
3. Removing file extension
4. Result: `src/utils/math.py` → `src.utils.math`

Component IDs are constructed as: `{module_path}:{component_name}`
- Example: `src.utils.math:add` (if `add` function is in math.py)
- Example: `src.models.User:__init__` (if `__init__` method is in User class)

### **2.5 Normalization to CodeComponent**
Adapters may return components in different formats (list of components, dictionaries, custom objects). The RepositoryParser normalizes these to a standardized dictionary mapping component IDs to CodeComponent objects.

---

## Phase 2 (continued): Aggregation

As each file is processed, its components are aggregated into a `all_components` dictionary. This represents all code components extracted across the entire repository. The dictionary keys are component IDs, enabling O(1) lookup during later dependency resolution.

---

## Phase 3: Dependency Resolution (PASS 2)

After all components are extracted, the Navigator performs a second pass to identify dependencies. Each language adapter implements `resolve_dependencies()`, which analyzes a single component to determine what other components it depends on.

### **3.1 What Constitutes "Depends On"?**

A component A "depends on" component B if one of these conditions is true:

1. **Explicit call**: A directly calls a function/method provided by B
2. **Type usage**: A declares a variable with a type defined in B
3. **Class instantiation**: A creates an instance of a class defined in B
4. **Inheritance**: A's class inherits from B's class
5. **Attribute access**: A accesses an attribute/property of B
6. **Module import**: A explicitly imports from module B

### **3.2 Dependency Detection Strategy**

Each language adapter scans the component's source code for patterns indicating these relationships:

**Pattern 1: Direct calls**
```python
# Python example: function_name(...)
result = transform(data)  # depends on transform
```

**Pattern 2: Type annotations**
```python
# Python: data: SomeClass
def process(data: SomeClass):  # depends on SomeClass
```

**Pattern 3: Imports**
```python
# JavaScript: import X from './module'
import { Database } from './database';  # depends on Database module
```

**Pattern 4: Object/array method access**
```javascript
// JavaScript: obj.method()
config.load()  // depends on config's component
```

The detection is typically implemented using:
- **Regex-based pattern matching** for simple cases
- **AST traversal** for complex cases (finding all function call nodes, import nodes, etc.)
- **Heuristic name matching** to identify what component a called function belongs to

### **3.3 Component Lookup and Resolution**

For each detected dependency, the adapter attempts to resolve it to a component ID using the `all_components` dictionary:

1. Look up the dependency name in all_components
2. If found directly, it's a component
3. If not found, apply heuristics:
   - If it's a method call, infer the owner class from context
   - If it's an imported module, search for that module's components
   - If it's a type name, search for a class with that name

### **3.4 Dependency De-duplication**

As dependencies are added to each component's `depends_on` set, duplicates are automatically eliminated (sets prevent duplicates). The parser also converts dependency sets to lists for consistency.

### **3.5 Example: Dependency Resolution**

Consider a Python function:
```python
def process_data(config: Config, data: List):
    validator = DataValidator(config)
    result = transform(data)
    return Database.save(result)
```

The parser identifies dependencies:
- `Config` class (type annotation)
- `DataValidator` class (instantiation)
- `transform` function (direct call)
- `Database` class (method access)

If these exist in all_components, they're added to process_data's depends_on set.

---

## Phase 4: Documentation-Oriented Dependency Abstraction (PASS 3)

The raw dependencies extracted in Pass 2 are often overly granular for documentation purposes. Pass 3 applies **semantic abstraction rules** via `apply_doc_dependency_rules()` to create a documentation-oriented dependency graph suitable for generating high-level documentation.

### **4.1 Class-Level Abstraction**

**Rule 1: Classes should depend on classes, not methods**

Raw dependencies might include:
- ClassA depends on ClassB.method_name (another class's specific method)

This is abstracted to:
- ClassA depends on ClassB

**Rationale**: When documenting ClassA, readers care that ClassA uses ClassB, not the implementation detail of which specific method. Users of ClassA would look up ClassB to understand ClassA's behavior.

### **4.2 Method-Level Abstraction**

**Rule 2: Methods should depend on classes, not other methods**

Raw dependencies might include:
- method_A depends on classB.method_name

This is abstracted to:
- method_A depends on classB

**Rationale**: When documenting method_A, mentioning it depends on classB is clearer than mentioning a specific internal method. The class-level dependency is more semantically important.

### **4.3 Self-Reference Elimination**

**Rule 3: Components should not depend on themselves**

Methods should not appear to depend on their own class. This is conceptually wrong—methods are *part* of a class, not dependencies.

Circular references (A→B→A) are detected and resolved.

### **4.4 Global Variable Preservation**

**Rule 4: Global variable dependencies are preserved as-is**

Global variables are kept as explicit dependencies because they represent shared mutable state that documentation must explain clearly.

### **4.5 Private Helper Removal (Optional)**

**Rule 5: Private helpers within the same class may be hidden**

If a public method calls multiple private helper methods within the same class, those method-level dependencies might be hidden from the documentation because they're implementation details. The class-level dependency already implies the "uses itself" relationship.

---

## Phase 5: Dependency Graph Analysis

### **5.1 DAG Construction**

From the abstracted dependencies, the Navigator builds a **Directed Acyclic Graph (DAG)** using the `build_graph_from_components()` function:

```
Graph representation:
  - Nodes: Component IDs
  - Directed edges: A → B means A depends on B
  - Adjacency list: {nodeA: {nodeB, nodeC}, ...}
```

### **5.2 Cycle Detection**

Real-world code sometimes contains circular dependencies (A depends on B, B depends on A). While these are often problematic, they can occur in Python with circular imports, in JavaScript with module systems, and in Java with type references.

The Navigator uses **Tarjan's Strongly Connected Components (SCC)** algorithm to detect all cycles:

1. Find all Strongly Connected Components (groups of nodes that depend on each other)
2. SCCs with multiple nodes are cycles
3. Report cycles for logging/debugging

### **5.3 Circular Dependency Resolution (Optional)**

If cycles are detected, the Navigator can apply resolution strategies:
1. **Remove lowest-priority edges**: Keep the most important dependencies, remove less important ones to break the cycle
2. **Collapse to module level**: Treat circular components as a single logical unit
3. **Report and accept**: Document the cycles but allow them (in dynamically-typed languages, circular imports may be resolvable at runtime)

Currently, the Navigator reports cycles but doesn't remove them, allowing the documentation pipeline to be aware of circular relationships.

---

## Component Type Hierarchy

The Navigator recognizes the following component types across all languages:

```
ComponentType:
  - CLASS: Class/record definition
  - FUNCTION: Top-level function
  - METHOD: Function within a class
  - ARROW_FUNCTION: Concise function syntax (JavaScript/TypeScript)
  - ASYNC_FUNCTION: Async function variant
  - VARIABLE: Local variable
  - GLOBAL_VARIABLE: Module-level variable
  - CLASS_VARIABLE: Variable within a class
  - INTERFACE: Interface/protocol definition (Java, TypeScript)
  - ENUM: Enumeration definition
  - MODULE: Module or namespace
  - OTHER: Unclassified components
```

This hierarchy is mapped consistently across languages (Python class → JavaScript class → Java class → TypeScript class → all become ComponentType.CLASS).

---

## Language-Specific Adapter Pattern

Each language adapter implements three methods on the BaseLanguageAdapter:

### **Method 1: parse(source_code)**
Converts source code to a parse tree using the language's parser.

**Python implementation**:
```python
def parse(self, source_code):
    if self.parser:
        return self.parser.parse(bytes(source_code, "utf8"))
    else:
        return ast.parse(source_code)  # Fallback to AST
```

**JavaScript/TypeScript implementation**:
```python
def parse(self, source_code):
    return self.parser.parse(bytes(source_code, "utf8"))
```

### **Method 2: extract_components(tree, source, file_path, module_path)**
Traverses the parse tree to extract components.

**Returns**: List of CodeComponent objects or Dict[id → CodeComponent]

**Implementation pattern**:
```python
def extract_components(self, tree, source, file_path, module_path):
    components = []
    for node in tree.root_node.children:  # tree-sitter
        if node.type == "class_declaration":
            components.append(self._extract_class(node, source, file_path, module_path))
        elif node.type == "function_declaration":
            components.append(self._extract_function(node, source, file_path, module_path))
    return components
```

### **Method 3: resolve_dependencies(component, tree, source, all_components)**
Analyzes a component to identify its dependencies.

**Returns**: Set[str] of component IDs this component depends on

**Implementation pattern**:
```python
def resolve_dependencies(self, component, tree, source, all_components):
    deps = set()
    # Scan source code for function calls, imports, type hints, etc.
    for match in CALL_PATTERN.finditer(source):
        called_name = match.group(1)
        # Look up in all_components
        if called_name in all_components:
            deps.add(called_name)
    return deps
```

---

## Data Flow Example: Python File Parsing

To illustrate the complete pipeline, consider parsing this Python file:

```python
# src/api.py
from src.database import Database
from src.validators import ValidateUser

class APIHandler:
    def __init__(self, db: Database):
        self.db = db
    
    def create_user(self, data: dict) -> bool:
        validator = ValidateUser()
        if validator.validate(data):
            return self.db.save(data)
        return False
```

**Phase 1: File discovery**
- Find `src/api.py`
- Match to PythonAdapter based on `.py` extension

**Phase 2: Component Extraction**
- Parse tree generated
- Identify CLASS node: APIHandler
  - Extract location, signature, methods
  - Create: CodeComponent(id="src.api:APIHandler", type=CLASS, ...)
- Identify METHOD node: __init__ within APIHandler class
  - Create: CodeComponent(id="src.api:APIHandler.__init__", type=METHOD, parameters=[db], ...)
- Identify METHOD node: create_user within APIHandler class
  - Create: CodeComponent(id="src.api:APIHandler.create_user", type=METHOD, parameters=[data], returns=bool, ...)

**Phase 3: Dependency Resolution (raw)**
- For APIHandler:
  - Type annotation `db: Database` → depends on Database
  - Result: depends_on = {"src.database:Database"}
- For __init__:
  - Parameter `db: Database` → depends on Database
  - Assignment `self.db = db` → self reference
  - Result: depends_on = {"src.database:Database"}
- For create_user:
  - Type annotation `data: dict` → dict is builtin, not a dependency
  - Variable `validator = ValidateUser()` → depends on ValidateUser
  - Call `validator.validate()` → depends on ValidateUser
  - Call `self.db.save()` → depends on Database (self.db is Database)
  - Return type `bool` → builtin, not a dependency
  - Result: depends_on = {"src.validators:ValidateUser", "src.database:Database"}

**Phase 4: Dependency Abstraction**
- APIHandler (class): depends_on existing methods are removed per rule 3 (self-reference)
  - Raw: {Database}
  - Abstracted: {Database}
- __init__ (method): abstracted per rule 2
  - Raw: {Database}
  - Abstracted: {Database}
- create_user (method): abstracted per rule 2
  - Raw: {ValidateUser, Database}
  - Abstracted: {ValidateUser, Database}

**Final output**:
```
CodeComponent(id="src.api:APIHandler", depends_on={"src.database:Database"})
CodeComponent(id="src.api:APIHandler.__init__", depends_on={"src.database:Database"})
CodeComponent(id="src.api:APIHandler.create_user", depends_on={"src.validators:ValidateUser", "src.database:Database"})
```

---

## Complexity Analysis

The Navigator's computational complexity is favorable:

- **File walking**: O(F) where F = total files in repository
- **Parsing each file**: O(L) where L = line count in file (Tree-sitter is linear)
- **Pass 2 dependency resolution**: O(C × D) where C = components, D = avg dependency references per component
- **Abstraction rules and DAG construction**: O(C + E) where E = total dependencies
- **Overall**: O(F × L) for parsing + O(C × D) for dependencies

For a typical codebase (10,000 files, average 100 lines, 50,000 components):
- Parsing: ~O(1,000,000) = fast (linear in source code size)
- Dependency resolution: ~O(100,000) = fast (linear in components × dependency density)
- Total: Completes in seconds to minutes on modern hardware

---

## Output: The Intermediate Repository (IR)

The Navigator's final output is a complete **CodeComponent repository** stored in memory (and optionally persisted to disk via IR export):

```python
all_components: Dict[str, CodeComponent]
  {
    "src.api:APIHandler": CodeComponent(...),
    "src.api:APIHandler.__init__": CodeComponent(...),
    "src.api:APIHandler.create_user": CodeComponent(...),
    "src.database:Database": CodeComponent(...),
    ...
  }

dependency_graph: Dict[str, Set[str]]
  {
    "src.api:APIHandler": {"src.database:Database"},
    "src.api:APIHandler.create_user": {"src.validators:ValidateUser", "src.database:Database"},
    ...
  }
```

This IR is the foundation for all downstream agents (Reader, Searcher, Verifier, Writer).

---

## Integration with Documentation Pipeline

The Navigator is the **upstream source** for the entire documentation pipeline:

1. **Reader Agent** consumes CodeComponent objects to assess complexity and determine information needs
2. **Searcher Agent** uses component_map and dependency_graph to retrieve context
3. **Writer Agent** uses component source code, signature, and metadata to generate documentation
4. **Verifier Agent** uses component type and complexity to build calibration profiles

Without the Navigator's accurate parsing, the entire downstream pipeline would fail. Errors in component extraction or dependency resolution propagate through all subsequent agents.

---

## Error Handling and Robustness

The Navigator implements defensive strategies:

1. **File encoding tolerance**: Uses UTF-8 with error="ignore" to skip unparseable bytes
2. **Adapter fallbacks**: Python uses native AST if Tree-sitter is unavailable
3. **Silent unsupported file skipping**: Files without matching adapters are ignored
4. **Dependency resolution graceful degradation**: Unknown dependencies are skipped rather than crashing
5. **Component normalization**: Handles adapters returning different formats
6. **Circular dependency tolerance**: Detects and logs but doesn't fail on circular dependencies

---

## Key Contributions to Documentation Pipeline

The Navigator contributes through:

1. **Language-agnostic parsing**: Support for multiple languages via pluggable adapters
2. **Complete code extraction**: Identifies all code entities (classes, functions, methods, variables)
3. **Accurate dependency resolution**: Maps code relationships across the repository
4. **Semantic abstraction**: Transforms low-level dependencies into documentation-oriented abstractions
5. **Robust parsing**: Handles edge cases, encoding issues, and missing dependencies gracefully
6. **Unified code representation**: All languages map to the same CodeComponent schema

---

## Conclusion

The Navigator Module is a sophisticated, multi-language code parsing and analysis engine that transforms raw source code into a structured intermediate representation suitable for documentation generation. Its language-agnostic architecture, multi-pass parsing strategy, semantic abstraction rules, and robust error handling make it a reliable foundation for the documentation pipeline. By accurately identifying all code components and their dependencies, the Navigator enables the Reader, Searcher, and Writer agents to generate high-quality documentation without language-specific knowledge.
