"""
C Language Dependency Resolver

Resolves SEMANTIC dependencies between C components for documentation.

Rules (adapted from DocAgent philosophy):
1. Function calls → depend on the called function component
2. Type usage  → depend on the struct/enum/typedef component
3. #include    → used for context but not direct component deps
4. Local variables → IGNORED (not stable semantic dependencies)
5. Standard library calls (printf, malloc, etc.) → IGNORED
6. Self-references → IGNORED

The resolver walks the AST subtree of each component and matches
identifiers against the project-wide component map.
"""

import re

# Standard C library functions that should not create dependencies.
C_STDLIB_FUNCTIONS = {
    # stdio.h
    "printf", "fprintf", "sprintf", "snprintf", "scanf", "fscanf", "sscanf",
    "fopen", "fclose", "fread", "fwrite", "fgets", "fputs", "fseek", "ftell",
    "rewind", "feof", "ferror", "perror", "puts", "getchar", "putchar",
    "getc", "putc", "ungetc", "fflush", "remove", "rename", "tmpfile",
    "tmpnam", "setbuf", "setvbuf",
    # stdlib.h
    "malloc", "calloc", "realloc", "free", "exit", "abort", "atexit",
    "atoi", "atof", "atol", "strtol", "strtod", "strtoul",
    "rand", "srand", "abs", "labs", "div", "ldiv",
    "qsort", "bsearch", "system", "getenv",
    # string.h
    "memcpy", "memmove", "memset", "memcmp", "memchr",
    "strcpy", "strncpy", "strcat", "strncat", "strcmp", "strncmp",
    "strchr", "strrchr", "strstr", "strtok", "strlen", "strerror",
    # math.h
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "exp", "log", "log10", "pow", "sqrt", "ceil", "floor", "fabs", "fmod",
    # ctype.h
    "isalpha", "isdigit", "isalnum", "isspace", "isupper", "islower",
    "toupper", "tolower",
    # assert.h
    "assert",
    # errno / signal
    "signal", "raise",
    # stdarg.h
    "va_start", "va_end", "va_arg", "va_copy",
}

# C primitive types and keywords that should not be matched as dependencies.
C_PRIMITIVE_TYPES = {
    "int", "char", "float", "double", "void", "long", "short", "unsigned",
    "signed", "size_t", "ssize_t", "ptrdiff_t", "intptr_t", "uintptr_t",
    "int8_t", "int16_t", "int32_t", "int64_t",
    "uint8_t", "uint16_t", "uint32_t", "uint64_t",
    "bool", "true", "false", "NULL",
    "FILE", "errno",
}


def resolve_dependencies(component, tree, source, all_components):
    """
    Resolve SEMANTIC dependencies for a C component.

    Args:
        component:      CodeComponent to resolve
        tree:           tree-sitter Tree for the file
        source:         Full source code string
        all_components: Dict[str, CodeComponent] of all project components

    Returns:
        Set[str] of component IDs that *component* depends on
    """
    deps = set()

    # Build lookup tables
    # Name → list of component IDs (functions, structs, enums, typedefs)
    symbol_map = {}
    for cid, comp in all_components.items():
        if comp.language != "c":
            continue
        name = comp.name
        symbol_map.setdefault(name, []).append(cid)

    # Locate the AST node for this component
    component_node = _find_component_node(tree.root_node, component, source)
    if not component_node:
        return deps

    # Walk only the component body
    _walk_for_deps(component_node, symbol_map, deps, source)

    # --------------------------------------------------
    # Type-level dependencies from parameters + return type
    # --------------------------------------------------
    if hasattr(component, "parameters") and component.parameters:
        for param in component.parameters:
            if param.type_hint:
                _resolve_type_names(param.type_hint, symbol_map, deps)

    if hasattr(component, "return_type") and component.return_type:
        _resolve_type_names(component.return_type, symbol_map, deps)

    # --------------------------------------------------
    # Cleanup
    # --------------------------------------------------
    cleaned = set()
    comp_id = component.id

    for dep_id in deps:
        # Don't depend on self
        if dep_id == comp_id:
            continue
        # Only keep deps that actually exist
        if dep_id in all_components:
            cleaned.add(dep_id)

    return cleaned


def _resolve_type_names(type_text, symbol_map, deps):
    """Extract type identifiers from a type string and resolve to components."""
    # Strip pointer/array decorators
    clean = type_text.replace("*", " ").replace("[", " ").replace("]", " ")
    tokens = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", clean)
    for tok in tokens:
        if tok in C_PRIMITIVE_TYPES:
            continue
        if tok in symbol_map:
            deps.update(symbol_map[tok])


def _find_component_node(root, component, source):
    """Find the AST node corresponding to a component."""
    comp_type = getattr(component.type, "value", str(component.type))
    start_line = component.location.start_line - 1  # tree-sitter is 0-indexed
    end_line = component.location.end_line - 1

    def walk(node):
        # Match by type + line range
        if node.start_point[0] == start_line and node.end_point[0] == end_line:
            if comp_type == "function" and node.type == "function_definition":
                return node
            if comp_type == "class" and node.type in ("struct_specifier", "enum_specifier"):
                return node
        # For typedefs that map to CLASS
        if comp_type == "class" and node.type == "type_definition":
            if node.start_point[0] == start_line:
                return node

        for child in node.children:
            found = walk(child)
            if found:
                return found
        return None

    return walk(root)


def _walk_for_deps(node, symbol_map, deps, source):
    """Walk the AST subtree collecting dependencies."""

    # Function calls → resolve callee
    if node.type == "call_expression":
        fn = node.child_by_field_name("function")
        if fn:
            call_name = source[fn.start_byte:fn.end_byte]
            # Strip receiver for things like ptr->func()
            if "->" in call_name:
                call_name = call_name.split("->")[-1]
            if "." in call_name:
                call_name = call_name.split(".")[-1]

            if call_name not in C_STDLIB_FUNCTIONS and call_name not in C_PRIMITIVE_TYPES:
                if call_name in symbol_map:
                    deps.update(symbol_map[call_name])

    # Type identifiers in declarations (e.g. struct MyStruct var;)
    if node.type == "type_identifier":
        type_name = node.text.decode()
        if type_name not in C_PRIMITIVE_TYPES and type_name in symbol_map:
            deps.update(symbol_map[type_name])

    # Struct/enum specifiers used inline (e.g. struct Foo *ptr;)
    if node.type in ("struct_specifier", "enum_specifier"):
        name_node = node.child_by_field_name("name")
        if name_node:
            name = name_node.text.decode()
            if name in symbol_map:
                deps.update(symbol_map[name])

    # sizeof(TypeName)
    if node.type == "sizeof_expression":
        for child in node.children:
            if child.type == "type_descriptor":
                type_id = child.child_by_field_name("type")
                if type_id and type_id.type == "type_identifier":
                    name = type_id.text.decode()
                    if name not in C_PRIMITIVE_TYPES and name in symbol_map:
                        deps.update(symbol_map[name])

    # Cast expressions: (TypeName)expr
    if node.type == "cast_expression":
        type_desc = node.child_by_field_name("type")
        if type_desc:
            type_id = type_desc.child_by_field_name("type")
            if type_id and type_id.type == "type_identifier":
                name = type_id.text.decode()
                if name not in C_PRIMITIVE_TYPES and name in symbol_map:
                    deps.update(symbol_map[name])

    for child in node.children:
        _walk_for_deps(child, symbol_map, deps, source)
