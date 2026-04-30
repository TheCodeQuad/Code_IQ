# Language Adapters: Comprehensive Working Guide

## Overview

The Navigator Module implements four language-specific adapters (Python, JavaScript, TypeScript, Java) following a common adapter pattern. Each adapter encapsulates language-specific parsing, component extraction, and dependency resolution while maintaining a unified interface. This document provides detailed methodology for each adapter's operation.

---

## Universal Adapter Interface

All language adapters implement three core methods:

```python
class BaseLanguageAdapter:
    def parse(self, source_code: str) -> ParseTree
    def extract_components(self, tree, source, file_path, module_path) -> Dict[component_id, CodeComponent]
    def resolve_dependencies(self, component, tree, source, all_components) -> Set[dependency_ids]
```

Each adapter operates through a consistent three-phase pipeline:
- **Phase 1 (Parse)**: Convert source code to parse tree using language parser
- **Phase 2 (Extract)**: Traverse parse tree to identify and extract components with metadata
- **Phase 3 (Resolve)**: Analyze each component's source code to identify dependencies

---

## Python Adapter

### Architecture and Parser Selection

The Python adapter implements intelligent fallback parsing: it first attempts to use Tree-sitter for comprehensive AST parsing—Tree-sitter provides faster parsing and consistent node naming across languages. When Tree-sitter is unavailable (installation issues, missing grammar), the adapter gracefully falls back to Python's native `ast` module for basic parsing. This dual-mode approach ensures robustness in diverse deployment environments.

```python
class PythonAdapter:
    def __init__(self):
        try:
            self.parser = get_ts_parser("python")  # Tree-sitter
            self.use_ast = False
        except Exception:
            self.parser = None
            self.use_ast = True  # Fallback to native AST
```

The distinction matters because Tree-sitter provides richer structural information (decorator nodes, type annotation nodes) while the native AST module provides only basic structure but guarantees availability in standard Python installations.

### Phase 1: Parse

When Tree-sitter is available, `parse()` returns a Tree-sitter Tree object:
```python
def parse(self, source):
    if self.use_ast or self.parser is None:
        return ast.parse(source)  # Python AST Module
    return self.parser.parse(bytes(source, "utf8"))  # Tree-sitter
```

The decision between Tree-sitter and AST is made once during initialization and cached (`self.use_ast`), avoiding repeated fallback checks.

### Phase 2: Component Extraction

Python component extraction varies between Tree-sitter and AST paths. The Tree-sitter path uses `extract_components()` which traverses the parse tree looking for specific node types representing code entities:

**Component Type Mapping**:
- `class_definition` → CLASS
- `function_definition` → FUNCTION or METHOD (distinguished by parent context)
- Module-level assignments → GLOBAL_VARIABLE
- Class-level assignments → CLASS_VARIABLE

For each identified component, the extractor collects:
- **Location**: Start and end line numbers from AST node
- **Signature**: Full function declaration including parameters and type hints
- **Docstring**: First string literal in function/class body (PEP 257 convention)
- **Parameters**: Name, type hint (from annotations), default value, required flag
- **Return type**: From return type annotation if present
- **Decorators**: All @decorator names and arguments
- **Visibility**: Computed from naming convention (leading underscore = private, double underscore = name-mangled)
- **Control flow**: Detection of async/await, loops, branches, exception handling
- **Metadata**: API endpoint information (FastAPI routes, Flask blueprints) via decorator inspection

**Docstring Extraction**:
```python
def get_docstring(node, source):
    body = node.child_by_field_name("body")
    for child in body.children:
        if child.type == "expression_statement":
            for expr_child in child.children:
                if expr_child.type == "string":
                    docstring_text = expr_child.text.decode()
                    if docstring_text.startswith('"""'):
                        return True, docstring_text[3:-3].strip()
    return False, ""
```

The extraction stops after finding the first statement in the body—if that first statement is a string literal (docstring), it's captured; otherwise, no docstring is recorded.

### Phase 3: Dependency Resolution

Python dependency resolution operates through two coordinating helper classes: **ImportTracker** and **GlobalVariableTracker**.

**ImportTracker** collects all imports from the file:
- Direct imports: `import os, sys`
- From imports: `from x import y, z`
- Relative imports: `from .module import X`
- Wildcard imports: `from x import *` (tracked separately)

The ImportTracker walks the parse tree identifying `import_statement` and `import_from_statement` nodes, extracting module names and imported symbols. For relative imports (starting with `.` or `..`), the tracker reconstructs the absolute module path based on the current module path.

**GlobalVariableTracker** identifies module-level variable assignments by examining top-level `assignment` nodes, tracking variable names for later reference. This is important because Python's module-level state is often a documentation concern.

**Dependency Detection Strategy**:
1. **Type annotations**: `x: SomeClass` → depends on SomeClass
2. **Function calls**: `foo(x)` → depends on foo (if in component map)
3. **Attribute access**: `obj.method()` → depends on obj's type (resolved from assignments)
4. **Class instantiation**: `Class()` → depends on Class
5. **Import resolution**: Names in imports are resolved to imported modules
6. **Constructor calls**: `Database(config)` → depends on Database class

**Example Resolution**:
```python
def process_data(config: Config, data: List):
    validator = DataValidator(config)  # depends on DataValidator (instantiation)
    result = transform(data)            # depends on transform (function call)
    return Database.save(result)        # depends on Database (method access)
```

Dependencies detected: Config (type annotation), DataValidator (instantiation), transform (function call), Database (method access).

### Fallback AST Mode

When Tree-sitter is unavailable, the adapter uses Python's native AST module. The AST path provides limited information—no decorator nodes, coarser type information—but guarantees operation. The AST fallback extracts components using `ast.walk()` to find ClassDef and FunctionDef nodes, building parameter lists and docstrings from the AST structure. Dependency resolution in AST mode is limited and often skipped because the AST module provides limited context.

---

## JavaScript Adapter

### Architecture and Enhanced Feature Detection

The JavaScript adapter uses Tree-sitter exclusively (no fallback) because JavaScript's syntax is complex and native parsing would be incomplete. The adapter extends basic component extraction with sophisticated feature detection including JSDoc comments, inline callbacks, promise chains, and Express middleware patterns.

```python
class JavaScriptAdapter:
    language = "javascript"
    extensions = [".js", ".jsx"]
    
    def __init__(self):
        self.parser = get_ts_parser("javascript")
```

### Phase 1: Parse

Simple Tree-sitter parsing:
```python
def parse(self, source):
    return self.parser.parse(bytes(source, "utf8"))
```

### Phase 2: Component Extraction

JavaScript extraction identifies components at three levels:

**Level 1: Component Declaration**
- `function_declaration` → FUNCTION
- `generator_function_declaration` → FUNCTION (async variant)
- `variable_declarator` with arrow_function → ARROW_FUNCTION
- `variable_declarator` with function_expression → FUNCTION
- `class_declaration` → CLASS
- `variable_declarator` with class_expression → CLASS
- `method_definition` (in class) → METHOD
- Object literal methods → METHOD

**Level 2: Metadata Extraction from JSDoc**:
```python
def get_jsdoc(node, source):
    prev_sibling = node.prev_sibling
    while prev_sibling:
        if prev_sibling.type in ("comment", "block_comment"):
            comment_text = prev_sibling.text.decode()
            if comment_text.startswith("/**") and comment_text.endswith("*/"):
                jsdoc_text = comment_text[3:-2].strip()
                lines = jsdoc_text.split('\n')
                cleaned_lines = [line.strip().lstrip('*').strip() for line in lines]
                return True, '\n'.join(cleaned_lines)
        elif prev_sibling.type in ("whitespace", "\n"):
            prev_sibling = prev_sibling.prev_sibling
            continue
        else:
            break
    return False, ""
```

JSDoc extraction walks backwards through previous siblings, skipping whitespace and decorators, until finding a JSDoc block comment (/** ... */). Single-line // comments are accumulated and concatenated.

**Level 3: Advanced Feature Extraction**:

1. **Inline callbacks**: Anonymous arrow functions and function expressions passed as arguments are captured but NOT added as top-level components. These are stored as metadata only in the component, reducing noise in the component graph:

```javascript
array.map(item => item.value)  // Arrow callback captured but not as component
fetch(url).then(res => res.json())  // Then callback captured
```

2. **Promise chains**: `.then()`, `.catch()`, `.finally()` chains are detected and stored as metadata showing asynchronous patterns.

3. **Express middleware patterns**: Routes like `app.get()`, `router.post()`, `app.use()` are detected and stored separately—not as components, but as metadata showing framework-specific patterns.

4. **Parameter extraction**: Handles JavaScript's flexible parameter syntax:
   - Plain identifiers: `foo(a, b)`
   - Default values: `foo(a = 1)`
   - Rest parameters: `foo(...rest)`
   - Destructured objects: `foo({ x, y })`
   - Destructured arrays: `foo([a, b])`

### Phase 3: Dependency Resolution

JavaScript dependency resolution uses **import tracking** and **symbol table mapping**:

```python
def resolve_dependencies(component, tree, source, all_components):
    deps = set()
    
    # Build symbol table: name -> component_ids
    symbol_map = {}
    for cid, comp in all_components.items():
        if comp.language == "javascript":
            name = cid.split(".")[-1]
            symbol_map.setdefault(name, []).append(cid)
    
    # Collect imports: local_name -> module_path
    import_aliases = {}
    def collect_imports(node):
        if node.type == "import_statement":
            module = node.child_by_field_name("source").text.decode().strip("\"'")
            for child in node.children:
                if child.type == "import_clause":
                    for spec in child.children:
                        if spec.type == "import_specifier":
                            local = spec.child_by_field_name("name")
                            import_aliases[local.text.decode()] = module
```

**Dependency Detection**:
1. **Function calls**: `foo()` and `obj.method()` → resolve name in symbol_map
2. **Imports**: Track which names came from imports to avoid external module dependencies
3. **Member expressions**: `.method()` calls on objects resolve the object's type first
4. **Test safety**: Components in test modules (containing ".test" or "/test/" in path) have reduced dependency expectations

The resolver implements a **priority scheme for ambiguity**: when a name matches multiple components, all matches are included, allowing the documentation pipeline to show the complete set of possible dependencies.

---

## TypeScript Adapter

### Architecture and JSX Support

The TypeScript adapter extends JavaScript's approach with support for TypeScript-specific syntax (type annotations, interfaces, generics) and JSX-in-TypeScript (.tsx files). The adapter uses two parsers: `typescript` for .ts files and `tsx` for .tsx files (falling back to typescript if tsx grammar unavailable).

```python
class TypeScriptAdapter:
    language = "typescript"
    extensions = [".ts", ".tsx"]
    
    def __init__(self):
        self.parser = get_ts_parser("typescript")
        try:
            self.tsx_parser = get_ts_parser("tsx")
        except Exception:
            self.tsx_parser = self.parser  # Fallback
    
    def parse(self, source, file_path=None):
        parser = self.parser
        if file_path and file_path.endswith(".tsx"):
            parser = self.tsx_parser
        return parser.parse(bytes(source, "utf8"))
```

### Phase 1: Parse

Parser selection based on file extension ensures correct grammar for JSX content in TypeScript files.

### Phase 2: Component Extraction

TypeScript extraction handles:

**Type Annotations**:
- Function parameters with type hints: `function foo(x: string, y: number)`
- Return type annotations: `function foo(): Promise<Data>`
- Variable type annotations: `const x: MyType = ...`
- Generic types: `List<Map<string, CustomClass>>`
- Union types: `string | number | null`
- Type predicates, conditional types, mapped types

**TypeScript-Specific Components**:
- `interface_declaration` → INTERFACE
- `type_alias_declaration` → TYPE_ALIAS
- `enum_declaration` → ENUM
- `namespace_declaration` → NAMESPACE

**Return Type Extraction**:
```python
def _extract_return_type(node):
    rt = node.child_by_field_name("return_type")
    if rt:
        text = rt.text.decode().lstrip(":").strip()
        return text if text else None
    return None
```

**Decorators**: Decorators are extracted via:
```python
def _extract_decorators(node):
    decorators = []
    prev = node.prev_sibling
    while prev:
        if prev.type == "decorator":
            decorators.insert(0, prev.text.decode())
        elif prev.type not in ("comment", "whitespace", "\n"):
            break
        prev = prev.prev_sibling
    return decorators
```

This is important for NestJS and other decorator-heavy frameworks.

**Class Features**:
```python
def _extract_class_attributes(body_node, source):
    """Extract class properties, fields, static attributes"""
    attrs = []
    for child in body_node.children:
        if child.type in ("public_field_definition", "property_definition"):
            attr = {'name': '', 'type': None, 'is_static': False}
            for sub in child.children:
                if sub.type == "property_identifier":
                    attr['name'] = sub.text.decode()
                elif sub.type == "type_annotation":
                    attr['type'] = sub.text.decode().lstrip(":").strip()
                elif sub.type == "static":
                    attr['is_static'] = True
            if attr['name']:
                attrs.append(attr)
    return attrs
```

**Generics and Inheritance**:
```python
def _extract_heritage(node):
    """Extract parent classes (extends) and interfaces (implements)"""
    parents = []
    for child in node.children:
        if child.type in ("class_heritage", "extends_clause", "implements_clause"):
            for sub in child.children:
                if sub.type in ("extends_clause", "implements_clause", ...):
                    for t in sub.children:
                        if t.type in ("identifier", "type_identifier", "generic_type"):
                            parents.append(t.text.decode())
    return parents
```

### Phase 3: Dependency Resolution

TypeScript dependency resolution is nearly identical to JavaScript but includes type-based dependencies:

```python
def resolve_dependencies(component, tree, source, all_components):
    deps = set()
    
    # Symbol table: name -> component_ids
    name_map = {}
    for c in all_components.values():
        if c.language in ("javascript", "typescript"):
            short_name = c.id.split(".")[-1]
            name_map.setdefault(short_name, []).append(c.id)
    
    # Traverse component AST
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        
        # Function calls
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")
            if fn and fn.type == "identifier":
                name = fn.text.decode()
                for target in name_map.get(name, []):
                    if target != component.id:
                        deps.add(target)
        
        # Type references in type annotations
        if node.type == "type_annotation":
            # Extract type names from annotation and resolve them
            ...
        
        for child in node.children:
            stack.append(child)
    
    return deps
```

Adding type annotations as dependencies ensures that changing a type definition is recognized as affecting components using that type.

---

## Java Adapter

### Architecture and Strict Typing

The Java adapter leverages Java's strict typing system to resolve dependencies reliably. Java's syntax provides complete type information—parameter types, return types, field types, inheritance—enabling deterministic dependency resolution without ambiguity.

```python
class JavaAdapter:
    language = "java"
    extensions = [".java"]
    
    def __init__(self):
        self.parser = get_ts_parser("java")
```

### Phase 1: Parse

Tree-sitter Java parsing:
```python
def parse(self, source):
    return self.parser.parse(bytes(source, "utf8"))
```

### Phase 2: Component Extraction

Java extraction identifies:

**Component Types**:
- `class_declaration` → CLASS
- `interface_declaration` → INTERFACE
- `enum_declaration` → ENUM
- `method_declaration` → METHOD
- `constructor_declaration` → CONSTRUCTOR
- `field_declaration` → FIELD or CLASS_VARIABLE

**Javadoc Extraction** (like JSDoc, but Maven-standard format):
```python
def get_javadoc(node, source):
    prev_sibling = node.prev_named_sibling
    while prev_sibling:
        if prev_sibling.type in ("comment", "block_comment"):
            comment_text = prev_sibling.text.decode()
            if comment_text.startswith("/**") and comment_text.endswith("*/"):
                javadoc_text = comment_text[3:-2].strip()
                lines = javadoc_text.split('\n')
                cleaned_lines = [line.strip().lstrip('*').strip() for line in lines]
                return True, '\n'.join(cleaned_lines)
            else:
                break
        elif prev_sibling.type in ("modifiers", "annotation", "marker_annotation"):
            # Skip modifiers and annotations
            prev_sibling = prev_sibling.prev_named_sibling
            continue
        else:
            break
    return False, ""
```

The crucial difference from JSDoc: Java uses `prev_named_sibling` (which skips whitespace nodes), making extraction more robust.

**Parameter Extraction with Generics**:
```python
def extract_parameters(method_node, source):
    """Handle formal_parameter and spread_parameter (varargs)"""
    parameters = []
    params = method_node.child_by_field_name("parameters")
    
    if params:
        for child in params.children:
            if child.type == "formal_parameter":
                type_node = child.child_by_field_name("type")
                param_type = source[type_node.start_byte:type_node.end_byte] if type_node else None
                
                name_node = child.child_by_field_name("name")
                if name_node:
                    param_name = name_node.text.decode()
                    parameters.append(Parameter(
                        name=param_name,
                        type_hint=param_type,
                        is_required=True
                    ))
            
            elif child.type == "spread_parameter":  # Varargs: String... args
                type_node = child.child_by_field_name("type")
                param_type = source[type_node.start_byte:type_node.end_byte] if type_node else None
                name_node = child.child_by_field_name("name")
                if name_node:
                    parameters.append(Parameter(
                        name=f"...{name_node.text.decode()}",
                        type_hint=param_type,
                        is_required=True
                    ))
    return parameters
```

Use of source slicing (`source[type_node.start_byte:type_node.end_byte]`) preserves generic type information like `List<Map<String, CustomClass>>` without manual reconstruction.

**Visibility and Modifiers**:
```python
def get_visibility(node):
    """Extract public, private, protected modifiers"""
    is_public = is_private = is_protected = False
    for child in node.children:
        if child.type == "modifiers":
            mods = child.text.decode()
            if "public" in mods: is_public = True
            elif "private" in mods: is_private = True
            elif "protected" in mods: is_protected = True
    if not (is_public or is_private or is_protected):
        is_public = True  # Default: package-private
    return is_public, is_private, is_protected
```

**Annotations and Metadata**:
```python
def extract_annotations(node, source):
    """Capture @Annotation(args) including Spring, JUnit metadata"""
    annotations = []
    def walk(n):
        if n.type in ("annotation", "marker_annotation"):
            annotations.append(source[n.start_byte:n.end_byte])
    for child in node.children:
        walk(child)
    return annotations
```

This captures framework-specific annotations (e.g., `@RestController`, `@Autowired`, `@Test`) for enhanced documentation context.

### Phase 3: Dependency Resolution

Java dependency resolution is the most sophisticated because of strict typing. The resolver implements **DocAgent-specific semantic rules**:

**Core Semantic Rules**:

1. **Ignore local variables**: Local variables are implementation details, not dependencies.
2. **Collapse overloaded methods**: When method overloading exists, collapse to class-level dependency (ambiguous to distinguish at documentation level).
3. **Ignore `this.method()`**: Internal method calls within the same class are not cross-component dependencies.
4. **Static calls as class dependencies**: `Utils.helper()` → depends on Utils class, not the method.
5. **Constructor calls as class dependencies**: `new CustomClass()` → depends on CustomClass.
6. **Type-based resolution**: Use parameter types, return types, field types to find dependencies.
7. **Import-based resolution**: Use import statements to resolve fully-qualified class names.
8. **Filter standard library**: Exclude `java.lang`, `java.util`, `javax`, etc.

**Implementation**:
```python
def resolve_dependencies(component, tree, source, all_components):
    deps = set()
    
    # Build class map: simple_name -> fullqualified_id
    class_map = {}
    for cid, comp in all_components.items():
        if comp.language == "java" and comp.type.value == "class":
            class_map[comp.name] = cid
    
    # Extract imports from component metadata
    import_map = {}  # simple_name -> fully_qualified_name
    if hasattr(component, 'imports') and component.imports:
        for imp in component.imports:
            imp_clean = imp.replace("import", "").replace(";", "").strip()
            if "*" not in imp_clean:
                parts = imp_clean.split(".")
                simple_name = parts[-1]
                import_map[simple_name] = imp_clean
    
    # Find component's AST node
    component_node = find_component_node(tree.root_node, component.id, component.type)
    
    # Rule 1: Extract dependencies from type annotations (parameters, return type)
    if hasattr(component, 'parameters') and component.parameters:
        for param in component.parameters:
            if param.type_hint:
                for type_name in extract_type_names(param.type_hint):
                    resolved_id = resolve_type_name(type_name)
                    if resolved_id:
                        deps.add(resolved_id)
    
    if hasattr(component, 'return_type') and component.return_type:
        for type_name in extract_type_names(component.return_type):
            resolved_id = resolve_type_name(type_name)
            if resolved_id:
                deps.add(resolved_id)
    
    # Rule 2: Extract inheritance dependencies
    if hasattr(component, 'parent_classes') and component.parent_classes:
        for parent_name in component.parent_classes:
            resolved_id = resolve_type_name(parent_name)
            if resolved_id:
                deps.add(resolved_id)
    
    # Rule 3: Extract method invocation dependencies
    # Static calls (Utils.method()) and constructor calls (new Class())
    # ignore this.method() calls (internal)
    
    return deps
```

---

## Comparison: Parsing Strategies

| Feature | Python | JavaScript | TypeScript | Java |
|---------|--------|-----------|-----------|------|
| Parser | Tree-sitter + AST fallback | Tree-sitter only | Tree-sitter (ts + tsx) | Tree-sitter only |
| Docstring format | PEP 257 (""" """) | JSDoc (/** */) | TSDoc/JSDoc (/** */) | Javadoc (/** */) |
| Type annotations | Optional, hints only | None (dynamic) | Mandatory & comprehensive | Mandatory & strict |
| Generics support | Limited | None | Full (`<T>`, `<K, V>`) | Full (`<T>`, `<K, V>`) |
| Access modifiers | Conventions (`_`, `__`) | None | explicit keywords | explicit keywords |
| Decorators | Via @decorator syntax | Via @decorator syntax | Via @decorator syntax | Via @Annotation syntax |
| Dependency ambiguity | Sometimes (imports) | Often (JS is dynamic) | Less (types help) | None (types are mandatory) |
| Component extraction | Good | Good | Excellent | Excellent |
| Dependency resolution | Good | Moderate | Good | Excellent |

---

## Key Insights Across All Adapters

1. **Parser consistency**: All adapters use Tree-sitter except Python's fallback, providing consistent AST structure across languages.

2. **Language-driven extraction**: Component extraction varies significantly by language (Python's underscore conventions, Java's modifiers, JavaScript's flexible syntax) but all normalize to CodeComponent.

3. **Documentation metadata**: Each adapter captures language-specific documentation metadata (Javadoc, JSDoc, docstrings) for inclusion in generated documentation.

4. **Type-driven dependency resolution**: Languages with strict typing (Java, TypeScript) resolve dependencies more accurately than dynamic languages (JavaScript, Python).

5. **Fallback strategies**: Each adapter implements defensive strategies—Python's AST fallback, graceful handling of missing imports, skipping of unparseable content.

6. **Metadata enrichment**: Adapters capture framework-specific metadata (Spring annotations, FastAPI decorators, Express middleware) beyond basic code structure.

---

## Integration with Navigator Pipeline

The four adapters work in concert within the Navigator Module:

1. **File discovery** routes `.py` files to PythonAdapter, `.js` to JavaScriptAdapter, etc.
2. **Each adapter independently extracts components** from its assigned files, creating a unified IR.
3. **Dependency resolution** executes identically for all languages using the ComponenType abstraction.
4. **Semantic abstraction** (class rollup, method hiding) applies uniformly to all language-specific dependencies.
5. **Output**: Four languages unified into a single dependency graph suitable for documentation.

This adapter pattern achieves language-agnostic code analysis while respecting language-specific idioms and conventions.

