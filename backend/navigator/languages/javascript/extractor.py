from typing import List
from backend.models.code_component import CodeComponent, Location, Parameter, ComponentType


def get_jsdoc(node, source):
    """
    Extract JSDoc comment from a function or class declaration.
    Fixed: Now skips over decorator/modifier nodes between JSDoc and declaration.

    Returns:
        tuple: (has_jsdoc: bool, jsdoc: str)
    """
    prev_sibling = node.prev_sibling

    while prev_sibling:
        node_type = prev_sibling.type

        if node_type in ("comment", "block_comment"):
            comment_text = prev_sibling.text.decode()
            if comment_text.startswith("/**") and comment_text.endswith("*/"):
                jsdoc_text = comment_text[3:-2].strip()
                lines = jsdoc_text.split('\n')
                cleaned_lines = []
                for line in lines:
                    line = line.strip()
                    if line.startswith('*'):
                        line = line[1:].strip()
                    cleaned_lines.append(line)
                return True, '\n'.join(cleaned_lines)
            else:
                break

        elif node_type == "decorator":
            # Skip decorators sitting between JSDoc and declaration
            prev_sibling = prev_sibling.prev_sibling
            continue

        else:
            break

        prev_sibling = prev_sibling.prev_sibling

    return False, ""


def extract_parameters(node):
    """
    Extract parameters with metadata including defaults.

    Handles:
    - Plain identifiers: foo(a, b)
    - Default values: foo(a = 1)
    - Rest params: foo(...rest)
    - Destructured objects: foo({ x, y })
    - Destructured arrays: foo([a, b])

    Returns:
        list: List of Parameter objects
    """
    parameters = []
    params = node.child_by_field_name("parameters")

    if params:
        for child in params.children:
            if child.type == "identifier":
                parameters.append(Parameter(
                    name=child.text.decode(),
                    type_hint=None,
                    default_value=None,
                    is_required=True
                ))

            elif child.type == "assignment_pattern":
                left = child.child_by_field_name("left")
                right = child.child_by_field_name("right")
                if left and left.type == "identifier":
                    parameters.append(Parameter(
                        name=left.text.decode(),
                        type_hint=None,
                        default_value=right.text.decode() if right else None,
                        is_required=False
                    ))

            elif child.type == "rest_pattern":
                for param_child in child.children:
                    if param_child.type == "identifier":
                        parameters.append(Parameter(
                            name=f"...{param_child.text.decode()}",
                            type_hint=None,
                            is_required=True
                        ))
                        break

            elif child.type == "object_pattern":
                parameters.append(Parameter(
                    name=child.text.decode(),
                    type_hint="object",
                    is_required=True
                ))

            elif child.type == "array_pattern":
                parameters.append(Parameter(
                    name=child.text.decode(),
                    type_hint="array",
                    is_required=True
                ))

    return parameters


def extract_signature(node, source):
    """Extract function signature (everything before the body)."""
    sig_start = node.start_byte
    sig_end = node.end_byte
    source_text = source[sig_start:sig_end]
    brace_pos = source_text.find('{')
    if brace_pos != -1:
        return source_text[:brace_pos].strip()
    return source_text.split('\n')[0]


def extract_imports_and_decorators(tree, source, module_path):
    """Extract all imports and decorators from the file."""
    imports = []
    decorators = []
    root = tree.root_node

    def walk(node):
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "string":
                    imports.append(child.text.decode().strip('\'"'))

        elif node.type == "import_from_statement":
            for child in node.children:
                if child.type == "string":
                    imports.append(child.text.decode().strip('\'"'))

        elif node.type == "decorator":
            decorators.append(node.text.decode())

        for child in node.children:
            walk(child)

    walk(root)
    return imports, decorators


def extract_function_calls(func_node, source):
    """Extract all function/method calls within a function."""
    calls = []

    def walk(node):
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")
            if fn:
                calls.append(fn.text.decode())
        for child in node.children:
            walk(child)

    walk(func_node)
    return calls


# ============================================================
# NEW: Inline callback extraction
# Captures anonymous arrow functions and function expressions
# passed as arguments — without polluting the component graph
# ============================================================
def extract_inline_functions(node, source):
    """
    Extract inline/anonymous callbacks within a component body.
    These are NOT added as top-level components — stored as metadata only.

    Captures:
    - Arrow callbacks: foo(() => {})
    - Anonymous function callbacks: foo(function() {})
    """
    inline_fns = []

    def walk(n):
        if n.type == "arrow_function":
            # Only capture if inside a call_expression (i.e. it's a callback)
            parent = n.parent
            if parent and parent.type == "arguments":
                inline_fns.append({
                    "type": "arrow_callback",
                    "signature": extract_signature(n, source),
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "source": source[n.start_byte:n.end_byte]
                })

        elif n.type == "function_expression":
            name_node = n.child_by_field_name("name")
            if not name_node:  # Only truly anonymous ones
                parent = n.parent
                if parent and parent.type == "arguments":
                    inline_fns.append({
                        "type": "anon_callback",
                        "signature": extract_signature(n, source),
                        "start_line": n.start_point[0] + 1,
                        "end_line": n.end_point[0] + 1,
                        "source": source[n.start_byte:n.end_byte]
                    })

        for c in n.children:
            walk(c)

    walk(node)
    return inline_fns


# ============================================================
# NEW: Promise chain detection
# ============================================================
def extract_promise_handlers(node):
    """
    Detect .then() / .catch() / .finally() chains within a component.
    Stored as metadata for documentation context.
    """
    handlers = []

    def walk(n):
        if n.type == "call_expression":
            fn = n.child_by_field_name("function")
            if fn:
                text = fn.text.decode()
                if text.endswith((".then", ".catch", ".finally")):
                    handlers.append(text)
        for c in n.children:
            walk(c)

    walk(node)
    return handlers


# ============================================================
# NEW: Express/middleware pattern detection
# ============================================================
def detect_middleware_calls(node):
    """
    Detect Express/router middleware patterns:
    app.get(), app.use(), router.post(), etc.
    Stored as metadata — not a separate component.
    """
    middleware = []

    def walk(n):
        if n.type == "call_expression":
            fn = n.child_by_field_name("function")
            if fn:
                text = fn.text.decode()
                if any(text.startswith(p) for p in ["app.", "router.", "express."]):
                    middleware.append(text)
        for c in n.children:
            walk(c)

    walk(node)
    return middleware


# ============================================================
# NEW: IIFE detection
# ============================================================
def detect_iife(node):
    """
    Detect Immediately Invoked Function Expressions (IIFEs).
    Example: (function() { ... })() or (() => { ... })()
    Stored as a flag — not extracted as component.
    """
    if node.type != "call_expression":
        return False
    fn = node.child_by_field_name("function")
    return fn is not None and fn.type == "parenthesized_expression"


def extract_components(tree, source, file_path, module_path):
    """
    Extract JavaScript code components:
    - Function declarations
    - Arrow functions (const foo = () => {})
    - Function expressions (const foo = function() {}, module.exports = function() {})
    - Classes and class methods
    - Module-level fallback for script/utility files

    Each component also captures:
    - Inline callbacks (stored as metadata, not top-level components)
    - Promise chain handlers (.then/.catch/.finally)
    - Express/middleware call patterns
    - IIFE flags

    Returns: Dictionary mapping component_id -> CodeComponent
    """
    components = {}
    root = tree.root_node
    found_symbol = False

    file_imports, _ = extract_imports_and_decorators(tree, source, module_path)

    def walk(node):
        nonlocal found_symbol

        # -----------------------------------
        # FUNCTION DECLARATION
        # function foo() {}
        # -----------------------------------
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                found_symbol = True
                name = name_node.text.decode()
                cid = f"{module_path}.{name}"

                has_jsdoc, jsdoc = get_jsdoc(node, source)
                parameters = extract_parameters(node)
                signature = extract_signature(node, source)
                calls = extract_function_calls(node, source)
                inline_callbacks = extract_inline_functions(node, source)
                promise_handlers = extract_promise_handlers(node)
                middleware = detect_middleware_calls(node)

                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1

                components[cid] = CodeComponent(
                    id=cid,
                    name=name,
                    type=ComponentType.FUNCTION,
                    location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=signature,
                    parameters=parameters,
                    existing_docstring=jsdoc if has_jsdoc else None,
                    calls=calls,
                    imports=file_imports,
                    language="javascript",
                    lines_of_code=end_line - start_line + 1,
                    is_async='async' in node.text.decode(),
                    metadata={
                        "inline_callbacks": inline_callbacks,
                        "promise_handlers": promise_handlers,
                        "middleware_calls": middleware,
                    }
                )

        # -----------------------------------
        # ARROW FUNCTION
        # const foo = () => {}
        # -----------------------------------
        elif node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")

            if name_node and value_node and value_node.type == "arrow_function":
                found_symbol = True
                name = name_node.text.decode()
                cid = f"{module_path}.{name}"

                var_decl = node.parent
                has_jsdoc, jsdoc = get_jsdoc(var_decl, source) if var_decl else (False, "")
                parameters = extract_parameters(value_node)
                signature = extract_signature(value_node, source)
                calls = extract_function_calls(value_node, source)
                inline_callbacks = extract_inline_functions(value_node, source)
                promise_handlers = extract_promise_handlers(value_node)
                middleware = detect_middleware_calls(value_node)

                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1

                components[cid] = CodeComponent(
                    id=cid,
                    name=name,
                    type=ComponentType.FUNCTION,
                    location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=signature,
                    parameters=parameters,
                    existing_docstring=jsdoc if has_jsdoc else None,
                    calls=calls,
                    imports=file_imports,
                    language="javascript",
                    lines_of_code=end_line - start_line + 1,
                    is_async='async' in source[node.start_byte:node.end_byte],
                    metadata={
                        "inline_callbacks": inline_callbacks,
                        "promise_handlers": promise_handlers,
                        "middleware_calls": middleware,
                    }
                )

        # -----------------------------------
        # FUNCTION EXPRESSION
        # const foo = function() {}
        # module.exports = function() {}
        # -----------------------------------
        elif node.type == "function_expression":
            name_node = node.child_by_field_name("name")

            if name_node:
                name = name_node.text.decode()
            else:
                parent = node.parent
                if parent and parent.type == "variable_declarator":
                    pname = parent.child_by_field_name("name")
                    name = pname.text.decode() if pname else None
                elif parent and parent.type == "assignment_expression":
                    left = parent.child_by_field_name("left")
                    name = left.text.decode().replace(".", "_") if left else None
                else:
                    name = None

            if name:
                found_symbol = True
                cid = f"{module_path}.{name}"

                jsdoc_node = node if name_node else (node.parent or node)
                has_jsdoc, jsdoc = get_jsdoc(jsdoc_node, source)
                parameters = extract_parameters(node)
                signature = extract_signature(node, source)
                calls = extract_function_calls(node, source)
                inline_callbacks = extract_inline_functions(node, source)
                promise_handlers = extract_promise_handlers(node)
                middleware = detect_middleware_calls(node)

                # Detect IIFE on parent call expression
                is_iife = False
                parent = node.parent
                if parent and parent.type == "parenthesized_expression":
                    grandparent = parent.parent
                    if grandparent:
                        is_iife = detect_iife(grandparent)

                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1

                components[cid] = CodeComponent(
                    id=cid,
                    name=name,
                    type=ComponentType.FUNCTION,
                    location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=signature,
                    parameters=parameters,
                    existing_docstring=jsdoc if has_jsdoc else None,
                    calls=calls,
                    imports=file_imports,
                    language="javascript",
                    lines_of_code=end_line - start_line + 1,
                    is_async='async' in node.text.decode(),
                    metadata={
                        "inline_callbacks": inline_callbacks,
                        "promise_handlers": promise_handlers,
                        "middleware_calls": middleware,
                        "is_iife": is_iife,
                    }
                )

        # -----------------------------------
        # CLASS DECLARATION
        # -----------------------------------
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                found_symbol = True
                class_name = name_node.text.decode()
                class_id = f"{module_path}.{class_name}"

                has_jsdoc, jsdoc = get_jsdoc(node, source)

                parent_classes = []
                parent_class_node = node.child_by_field_name("superclass")
                if parent_class_node:
                    parent_classes = [parent_class_node.text.decode()]

                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1

                components[class_id] = CodeComponent(
                    id=class_id,
                    name=class_name,
                    type=ComponentType.CLASS,
                    location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=f"class {class_name}",
                    parent_classes=parent_classes,
                    existing_docstring=jsdoc if has_jsdoc else None,
                    imports=file_imports,
                    language="javascript",
                    lines_of_code=end_line - start_line + 1,
                )

                # -------- METHODS --------
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        if child.type == "method_definition":
                            key = child.child_by_field_name("name")
                            if key:
                                method_name = key.text.decode()
                                method_id = f"{class_id}.{method_name}"

                                has_method_jsdoc, method_jsdoc = get_jsdoc(child, source)
                                parameters = extract_parameters(child)
                                signature = extract_signature(child, source)
                                calls = extract_function_calls(child, source)
                                inline_callbacks = extract_inline_functions(child, source)
                                promise_handlers = extract_promise_handlers(child)
                                middleware = detect_middleware_calls(child)

                                method_start = child.start_point[0] + 1
                                method_end = child.end_point[0] + 1

                                is_static = any(
                                    c.type == "static" for c in child.children
                                )

                                components[method_id] = CodeComponent(
                                    id=method_id,
                                    name=method_name,
                                    type=ComponentType.METHOD,
                                    location=Location(file_path=file_path, start_line=method_start, end_line=method_end),
                                    source_code=source[child.start_byte:child.end_byte],
                                    signature=signature,
                                    parameters=parameters,
                                    existing_docstring=method_jsdoc if has_method_jsdoc else None,
                                    calls=calls,
                                    imports=file_imports,
                                    language="javascript",
                                    lines_of_code=method_end - method_start + 1,
                                    is_static=is_static,
                                    is_async='async' in child.text.decode(),
                                    metadata={
                                        "inline_callbacks": inline_callbacks,
                                        "promise_handlers": promise_handlers,
                                        "middleware_calls": middleware,
                                    }
                                )

                # Don't recurse into class body again
                return

        for child in node.children:
            walk(child)

    walk(root)

    # =====================================================
    # MODULE-LEVEL FALLBACK
    # For files with no extractable named symbols
    # =====================================================
    if not found_symbol:
        components[module_path] = CodeComponent(
            id=module_path,
            name=module_path.split('.')[-1],
            type=ComponentType.MODULE,
            location=Location(
                file_path=file_path,
                start_line=1,
                end_line=source.count("\n") + 1
            ),
            source_code=source,
            signature=f"module {module_path}",
            imports=file_imports,
            language="javascript",
            lines_of_code=source.count("\n") + 1,
        )

    # Add module_path metadata to all components
    for comp in components.values():
        parts = comp.id.split('.')
        if comp.type == ComponentType.METHOD:
            comp.module_path = '.'.join(parts[:-2]) if len(parts) > 2 else parts[0]
        else:
            comp.module_path = '.'.join(parts[:-1]) if len(parts) > 1 else parts[0]

    return components
