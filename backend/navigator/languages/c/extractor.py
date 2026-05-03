"""
C Language Component Extractor

Uses tree-sitter to extract code components from C source files (.c, .h):
  - Function definitions
  - Struct declarations (treated as CLASS)
  - Enum declarations (treated as CLASS)
  - Typedef declarations (treated as VARIABLE)
  - Global variable declarations (treated as GLOBAL_VARIABLE)
  - Macro definitions (treated as VARIABLE metadata)

Each component captures:
  - Parameters, return types, source code, location
  - Doxygen / block-comment docstrings
  - #include directives as imports
  - Function calls within bodies
  - Cyclomatic complexity estimate
"""

from typing import List, Dict, Optional
from backend.models.code_component import CodeComponent, Location, Parameter, ComponentType


# ---------------------------------------------------------------------------
# Docstring / comment extraction
# ---------------------------------------------------------------------------

def get_doc_comment(node, source: str):
    """
    Extract a Doxygen-style or multi-line /** ... */ comment immediately
    preceding *node*.

    Returns:
        (has_doc: bool, doc_text: str)
    """
    prev = node.prev_sibling
    while prev:
        if prev.type == "comment":
            text = source[prev.start_byte:prev.end_byte]
            # Doxygen block comment: /** ... */
            if text.startswith("/**") and text.endswith("*/"):
                inner = text[3:-2].strip()
                lines = inner.split("\n")
                cleaned = []
                for line in lines:
                    line = line.strip()
                    if line.startswith("*"):
                        line = line[1:].strip()
                    cleaned.append(line)
                return True, "\n".join(cleaned)
            # Doxygen triple-slash: /// ...
            if text.startswith("///"):
                # Collect consecutive /// lines
                doc_lines = [text.lstrip("/").strip()]
                p = prev.prev_sibling
                while p and p.type == "comment":
                    t = source[p.start_byte:p.end_byte]
                    if t.startswith("///"):
                        doc_lines.insert(0, t.lstrip("/").strip())
                        p = p.prev_sibling
                    else:
                        break
                return True, "\n".join(doc_lines)
            # Plain /* ... */ block right above
            if text.startswith("/*") and text.endswith("*/"):
                inner = text[2:-2].strip()
                lines = inner.split("\n")
                cleaned = []
                for line in lines:
                    line = line.strip()
                    if line.startswith("*"):
                        line = line[1:].strip()
                    cleaned.append(line)
                return True, "\n".join(cleaned)
            # Otherwise it's a // single-line comment, skip
            prev = prev.prev_sibling
            continue
        else:
            break
    return False, ""


# ---------------------------------------------------------------------------
# Parameter extraction
# ---------------------------------------------------------------------------

def extract_parameters(func_node, source: str) -> List[Parameter]:
    """Extract parameters from a function_definition or declaration_node."""
    parameters = []
    declarator = func_node.child_by_field_name("declarator")
    if not declarator:
        return parameters

    # Walk down to function_declarator
    fd = _find_function_declarator(declarator)
    if not fd:
        return parameters

    params_node = fd.child_by_field_name("parameters")
    if not params_node:
        return parameters

    for child in params_node.children:
        if child.type == "parameter_declaration":
            param_name = None
            param_type = None

            # Type
            type_node = child.child_by_field_name("type")
            if type_node:
                param_type = source[type_node.start_byte:type_node.end_byte]

            # Name (declarator field)
            decl = child.child_by_field_name("declarator")
            if decl:
                # Could be plain identifier, pointer_declarator, array_declarator, etc.
                param_name = _extract_declarator_name(decl, source)

            if param_name:
                parameters.append(Parameter(
                    name=param_name,
                    type_hint=param_type,
                    is_required=True,
                ))
        elif child.type == "variadic_parameter":
            parameters.append(Parameter(
                name="...",
                type_hint=None,
                is_required=False,
            ))
    return parameters


def _find_function_declarator(node):
    """Recursively find a function_declarator inside nested declarator nodes."""
    if node.type == "function_declarator":
        return node
    for child in node.children:
        result = _find_function_declarator(child)
        if result:
            return result
    return None


def _extract_declarator_name(node, source: str) -> Optional[str]:
    """Extract the identifier name from various declarator forms."""
    if node.type in ("identifier", "type_identifier", "field_identifier"):
        return node.text.decode()
    if node.type == "pointer_declarator":
        decl = node.child_by_field_name("declarator")
        if decl:
            return _extract_declarator_name(decl, source)
    if node.type == "array_declarator":
        decl = node.child_by_field_name("declarator")
        if decl:
            return _extract_declarator_name(decl, source)
    # Fallback: look for any identifier-like child
    for child in node.children:
        if child.type in ("identifier", "type_identifier", "field_identifier"):
            return child.text.decode()
    return None


# ---------------------------------------------------------------------------
# Return type extraction
# ---------------------------------------------------------------------------

def extract_return_type(func_node, source: str) -> Optional[str]:
    """Extract the return type from a function_definition."""
    type_node = func_node.child_by_field_name("type")
    if type_node:
        return source[type_node.start_byte:type_node.end_byte]
    return None


# ---------------------------------------------------------------------------
# Function name extraction
# ---------------------------------------------------------------------------

def extract_function_name(func_node, source: str) -> Optional[str]:
    """Extract the function name from a function_definition."""
    declarator = func_node.child_by_field_name("declarator")
    if not declarator:
        return None
    fd = _find_function_declarator(declarator)
    if fd:
        name_node = fd.child_by_field_name("declarator")
        if name_node:
            return _extract_declarator_name(name_node, source)
    return None


# ---------------------------------------------------------------------------
# Signature extraction
# ---------------------------------------------------------------------------

def extract_signature(func_node, source: str) -> str:
    """Extract the function signature (everything before the body)."""
    body = func_node.child_by_field_name("body")
    if body:
        sig_text = source[func_node.start_byte:body.start_byte].strip()
        return sig_text
    # Fallback: first line
    full = source[func_node.start_byte:func_node.end_byte]
    return full.split("\n")[0].strip()


# ---------------------------------------------------------------------------
# Call extraction
# ---------------------------------------------------------------------------

def extract_function_calls(node, source: str) -> List[str]:
    """Extract all function call names within a node."""
    calls = []

    def walk(n):
        if n.type == "call_expression":
            fn = n.child_by_field_name("function")
            if fn:
                calls.append(source[fn.start_byte:fn.end_byte])
        for child in n.children:
            walk(child)

    walk(node)
    return calls


# ---------------------------------------------------------------------------
# #include extraction
# ---------------------------------------------------------------------------

def extract_includes(tree, source: str) -> List[str]:
    """Extract all #include directives from the file."""
    includes = []
    root = tree.root_node

    def walk(node):
        if node.type == "preproc_include":
            path_node = node.child_by_field_name("path")
            if path_node:
                includes.append(source[path_node.start_byte:path_node.end_byte].strip('"<>'))
        for child in node.children:
            walk(child)

    walk(root)
    return includes


# ---------------------------------------------------------------------------
# Complexity
# ---------------------------------------------------------------------------

def calculate_complexity(node) -> int:
    """Approximate cyclomatic complexity for a function body."""
    complexity = 1

    def walk(n):
        nonlocal complexity
        if n.type in (
            "if_statement", "while_statement", "for_statement",
            "do_statement", "case_statement", "conditional_expression",
        ):
            complexity += 1
        for child in n.children:
            walk(child)

    walk(node)
    return complexity


# ---------------------------------------------------------------------------
# Struct member extraction
# ---------------------------------------------------------------------------

def _extract_struct_members(struct_node, struct_id, source, file_path, file_imports, components):
    """Extract fields from a struct body and register as FIELD components."""
    attributes = []
    body = struct_node.child_by_field_name("body")
    if not body:
        return attributes

    for child in body.children:
        if child.type == "field_declaration":
            type_node = child.child_by_field_name("type")
            field_type = source[type_node.start_byte:type_node.end_byte] if type_node else None

            # The field name is in the "declarator" field of the field_declaration
            decl_node = child.child_by_field_name("declarator")
            if not decl_node:
                continue
            field_name = _extract_declarator_name(decl_node, source)
            if not field_name:
                continue

            field_id = f"{struct_id}.{field_name}"
            start_line = child.start_point[0] + 1
            end_line = child.end_point[0] + 1

            has_doc, doc = get_doc_comment(child, source)

            components[field_id] = CodeComponent(
                id=field_id,
                name=field_name,
                type=ComponentType.FIELD,
                location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                source_code=source[child.start_byte:child.end_byte],
                signature=f"{field_type} {field_name}" if field_type else field_name,
                existing_docstring=doc if has_doc else None,
                imports=file_imports,
                language="c",
                lines_of_code=1,
                return_type=field_type,
            )
            attributes.append({"name": field_name, "id": field_id, "type": field_type})

    return attributes


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------

def extract_components(tree, source: str, file_path: str, module_path: str) -> Dict[str, CodeComponent]:
    """
    Extract all C components from a parsed tree.

    Handles:
      - function_definition → FUNCTION
      - struct_specifier (named) → CLASS
      - enum_specifier (named) → CLASS
      - typedef declarations → VARIABLE
      - top-level variable declarations → GLOBAL_VARIABLE
      - preproc_function_def (#define macros) → VARIABLE (metadata)

    Returns:
        Dictionary mapping component_id → CodeComponent
    """
    components: Dict[str, CodeComponent] = {}
    root = tree.root_node

    file_imports = extract_includes(tree, source)

    def walk(node):
        # ===============================================================
        # FUNCTION DEFINITION
        # ===============================================================
        if node.type == "function_definition":
            func_name = extract_function_name(node, source)
            if not func_name:
                for child in node.children:
                    walk(child)
                return

            func_id = f"{module_path}.{func_name}"
            has_doc, doc = get_doc_comment(node, source)
            parameters = extract_parameters(node, source)
            return_type = extract_return_type(node, source)
            signature = extract_signature(node, source)
            calls = extract_function_calls(node, source)
            complexity = calculate_complexity(node)

            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            # Detect static functions
            is_static = False
            storage_class = node.child_by_field_name("storage_class_specifier")
            if storage_class:
                is_static = source[storage_class.start_byte:storage_class.end_byte] == "static"
            # Also check for 'static' in sibling/preceding specifiers
            for child in node.children:
                if child.type == "storage_class_specifier" and child.text.decode() == "static":
                    is_static = True

            components[func_id] = CodeComponent(
                id=func_id,
                name=func_name,
                type=ComponentType.FUNCTION,
                location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                source_code=source[node.start_byte:node.end_byte],
                signature=signature,
                parameters=parameters,
                return_type=return_type,
                existing_docstring=doc if has_doc else None,
                calls=calls,
                imports=file_imports,
                language="c",
                lines_of_code=end_line - start_line + 1,
                complexity=complexity,
                is_static=is_static,
                is_public=not is_static,
                is_private=is_static,
                metadata={},
            )
            return  # Don't recurse into function body for nested functions

        # ===============================================================
        # STRUCT SPECIFIER (named struct)
        # ===============================================================
        if node.type == "struct_specifier":
            name_node = node.child_by_field_name("name")
            if not name_node:
                for child in node.children:
                    walk(child)
                return

            struct_name = name_node.text.decode()
            struct_id = f"{module_path}.{struct_name}"

            has_doc, doc = get_doc_comment(node, source)
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            attributes = _extract_struct_members(
                node, struct_id, source, file_path, file_imports, components
            )
            field_ids = [a["id"] for a in attributes]

            components[struct_id] = CodeComponent(
                id=struct_id,
                name=struct_name,
                type=ComponentType.CLASS,
                location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                source_code=source[node.start_byte:node.end_byte],
                signature=f"struct {struct_name}",
                existing_docstring=doc if has_doc else None,
                imports=file_imports,
                language="c",
                lines_of_code=end_line - start_line + 1,
                methods=[],
                attributes=attributes,
                metadata={"is_struct": True},
            )
            return

        # ===============================================================
        # ENUM SPECIFIER (named enum)
        # ===============================================================
        if node.type == "enum_specifier":
            name_node = node.child_by_field_name("name")
            if not name_node:
                for child in node.children:
                    walk(child)
                return

            enum_name = name_node.text.decode()
            enum_id = f"{module_path}.{enum_name}"

            has_doc, doc = get_doc_comment(node, source)
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            # Extract enum values
            enumerators = []
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type == "enumerator":
                        name_n = child.child_by_field_name("name")
                        if name_n:
                            enumerators.append(name_n.text.decode())

            components[enum_id] = CodeComponent(
                id=enum_id,
                name=enum_name,
                type=ComponentType.CLASS,
                location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                source_code=source[node.start_byte:node.end_byte],
                signature=f"enum {enum_name}",
                existing_docstring=doc if has_doc else None,
                imports=file_imports,
                language="c",
                lines_of_code=end_line - start_line + 1,
                metadata={"is_enum": True, "enumerators": enumerators},
            )
            return

        # ===============================================================
        # TYPE DEFINITION (typedef)
        # ===============================================================
        if node.type == "type_definition":
            # typedef struct {...} Name;  or  typedef int MyInt;
            # The last identifier-like declarator is the name
            decl = node.child_by_field_name("declarator")
            if decl:
                typedef_name = _extract_declarator_name(decl, source)
                if typedef_name:
                    typedef_id = f"{module_path}.{typedef_name}"
                    has_doc, doc = get_doc_comment(node, source)
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1

                    # Check if this typedef wraps a struct
                    type_node = node.child_by_field_name("type")
                    is_struct_typedef = type_node and type_node.type == "struct_specifier"

                    if is_struct_typedef:
                        # Extract the struct members
                        attributes = _extract_struct_members(
                            type_node, typedef_id, source, file_path, file_imports, components
                        )

                        components[typedef_id] = CodeComponent(
                            id=typedef_id,
                            name=typedef_name,
                            type=ComponentType.CLASS,
                            location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                            source_code=source[node.start_byte:node.end_byte],
                            signature=f"typedef struct {{ ... }} {typedef_name}",
                            existing_docstring=doc if has_doc else None,
                            imports=file_imports,
                            language="c",
                            lines_of_code=end_line - start_line + 1,
                            methods=[],
                            attributes=attributes,
                            metadata={"is_typedef_struct": True},
                        )
                    else:
                        components[typedef_id] = CodeComponent(
                            id=typedef_id,
                            name=typedef_name,
                            type=ComponentType.VARIABLE,
                            location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                            source_code=source[node.start_byte:node.end_byte],
                            signature=source[node.start_byte:node.end_byte].strip().rstrip(";"),
                            existing_docstring=doc if has_doc else None,
                            imports=file_imports,
                            language="c",
                            lines_of_code=end_line - start_line + 1,
                            metadata={"is_typedef": True},
                        )
                    return

        # ===============================================================
        # DECLARATION (global variables at file scope)
        # ===============================================================
        if node.type == "declaration" and node.parent and node.parent.type == "translation_unit":
            # Only extract global declarations at the top level
            type_node = node.child_by_field_name("type")
            if type_node:
                var_type = source[type_node.start_byte:type_node.end_byte]
                for child in node.children:
                    if child.type in ("init_declarator", "declarator"):
                        decl_node = child.child_by_field_name("declarator") if child.type == "init_declarator" else child
                        var_name = _extract_declarator_name(decl_node, source)
                        if var_name:
                            var_id = f"{module_path}.{var_name}"
                            has_doc, doc = get_doc_comment(node, source)
                            start_line = node.start_point[0] + 1
                            end_line = node.end_point[0] + 1

                            components[var_id] = CodeComponent(
                                id=var_id,
                                name=var_name,
                                type=ComponentType.GLOBAL_VARIABLE,
                                location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                                source_code=source[node.start_byte:node.end_byte],
                                signature=f"{var_type} {var_name}",
                                existing_docstring=doc if has_doc else None,
                                imports=file_imports,
                                language="c",
                                lines_of_code=1,
                                return_type=var_type,
                                metadata={},
                            )

        # ===============================================================
        # PREPROC_FUNCTION_DEF (#define macro with params)
        # ===============================================================
        if node.type == "preproc_function_def":
            name_node = node.child_by_field_name("name")
            if name_node:
                macro_name = name_node.text.decode()
                macro_id = f"{module_path}.{macro_name}"
                has_doc, doc = get_doc_comment(node, source)
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1

                components[macro_id] = CodeComponent(
                    id=macro_id,
                    name=macro_name,
                    type=ComponentType.VARIABLE,
                    location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=source[node.start_byte:node.end_byte].strip(),
                    existing_docstring=doc if has_doc else None,
                    imports=file_imports,
                    language="c",
                    lines_of_code=end_line - start_line + 1,
                    metadata={"is_macro": True},
                )
            return

        # ===============================================================
        # PREPROC_DEF (#define constant)
        # ===============================================================
        if node.type == "preproc_def":
            name_node = node.child_by_field_name("name")
            if name_node:
                macro_name = name_node.text.decode()
                macro_id = f"{module_path}.{macro_name}"
                has_doc, doc = get_doc_comment(node, source)
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1

                components[macro_id] = CodeComponent(
                    id=macro_id,
                    name=macro_name,
                    type=ComponentType.GLOBAL_VARIABLE,
                    location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=source[node.start_byte:node.end_byte].strip(),
                    existing_docstring=doc if has_doc else None,
                    imports=file_imports,
                    language="c",
                    lines_of_code=1,
                    metadata={"is_macro": True},
                )
            return

        # Recurse into children for everything else
        for child in node.children:
            walk(child)

    # Start walking from root
    for child in root.children:
        walk(child)

    return components
