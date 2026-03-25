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


def _extract_class_members(class_id, class_node, source, file_path, file_imports, components):
    """
    Extract all members from a class body:
    - method_definition     → METHOD or CONSTRUCTOR
    - field_definition      → FIELD / STATIC_FIELD / METHOD (arrow-in-field)
    - public_field_definition (same treatment as field_definition)

    Populates *components* in-place and returns (method_ids, attribute_dicts).
    """
    method_ids = []
    attributes = []

    body = class_node.child_by_field_name("body")
    if not body:
        return method_ids, attributes

    for child in body.children:
        # ----- method_definition (includes constructor) -----
        if child.type == "method_definition":
            key = child.child_by_field_name("name")
            if not key:
                continue

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

            is_static = any(c.type == "static" for c in child.children)

            # Detect getter / setter
            is_getter = any(c.type == "get" for c in child.children)
            is_setter = any(c.type == "set" for c in child.children)

            # Constructor gets its own ComponentType
            if method_name == "constructor":
                comp_type = ComponentType.CONSTRUCTOR
            else:
                comp_type = ComponentType.METHOD

            # Generator method: function* inside class
            body_text = source[child.start_byte:child.end_byte]
            is_gen = "*" in body_text.split("(")[0] if "(" in body_text else False

            components[method_id] = CodeComponent(
                id=method_id,
                name=method_name,
                type=comp_type,
                location=Location(file_path=file_path, start_line=method_start, end_line=method_end),
                source_code=body_text,
                signature=signature,
                parameters=parameters,
                existing_docstring=method_jsdoc if has_method_jsdoc else None,
                calls=calls,
                imports=file_imports,
                language="javascript",
                lines_of_code=method_end - method_start + 1,
                is_static=is_static,
                is_async='async' in body_text,
                is_generator=is_gen,
                metadata={
                    "inline_callbacks": inline_callbacks,
                    "promise_handlers": promise_handlers,
                    "middleware_calls": middleware,
                    "is_getter": is_getter,
                    "is_setter": is_setter,
                }
            )
            method_ids.append(method_id)

        # ----- field_definition / public_field_definition -----
        elif child.type in ("field_definition", "public_field_definition"):
            prop_node = child.child_by_field_name("property")
            value_node = child.child_by_field_name("value")
            if not prop_node:
                continue

            field_name = prop_node.text.decode()
            field_id = f"{class_id}.{field_name}"
            is_static = any(c.type == "static" for c in child.children)

            field_start = child.start_point[0] + 1
            field_end = child.end_point[0] + 1
            field_src = source[child.start_byte:child.end_byte]
            has_jsdoc, jsdoc = get_jsdoc(child, source)

            # Arrow function field  →  treat as METHOD
            if value_node and value_node.type == "arrow_function":
                parameters = extract_parameters(value_node)
                signature = extract_signature(value_node, source)
                calls = extract_function_calls(value_node, source)
                inline_callbacks = extract_inline_functions(value_node, source)
                promise_handlers = extract_promise_handlers(value_node)
                middleware = detect_middleware_calls(value_node)

                components[field_id] = CodeComponent(
                    id=field_id,
                    name=field_name,
                    type=ComponentType.METHOD,
                    location=Location(file_path=file_path, start_line=field_start, end_line=field_end),
                    source_code=field_src,
                    signature=signature,
                    parameters=parameters,
                    existing_docstring=jsdoc if has_jsdoc else None,
                    calls=calls,
                    imports=file_imports,
                    language="javascript",
                    lines_of_code=field_end - field_start + 1,
                    is_static=is_static,
                    is_async='async' in field_src,
                    metadata={
                        "inline_callbacks": inline_callbacks,
                        "promise_handlers": promise_handlers,
                        "middleware_calls": middleware,
                        "is_field_arrow": True,
                    }
                )
                method_ids.append(field_id)

            # Function expression field  →  treat as METHOD
            elif value_node and value_node.type in ("function_expression", "function"):
                parameters = extract_parameters(value_node)
                signature = extract_signature(value_node, source)
                calls = extract_function_calls(value_node, source)

                components[field_id] = CodeComponent(
                    id=field_id,
                    name=field_name,
                    type=ComponentType.METHOD,
                    location=Location(file_path=file_path, start_line=field_start, end_line=field_end),
                    source_code=field_src,
                    signature=signature,
                    parameters=parameters,
                    existing_docstring=jsdoc if has_jsdoc else None,
                    calls=calls,
                    imports=file_imports,
                    language="javascript",
                    lines_of_code=field_end - field_start + 1,
                    is_static=is_static,
                    is_async='async' in field_src,
                )
                method_ids.append(field_id)

            # Regular data field  →  FIELD or STATIC_FIELD
            else:
                comp_type = ComponentType.STATIC_FIELD if is_static else ComponentType.FIELD
                components[field_id] = CodeComponent(
                    id=field_id,
                    name=field_name,
                    type=comp_type,
                    location=Location(file_path=file_path, start_line=field_start, end_line=field_end),
                    source_code=field_src,
                    signature=field_src.strip(),
                    existing_docstring=jsdoc if has_jsdoc else None,
                    imports=file_imports,
                    language="javascript",
                    lines_of_code=field_end - field_start + 1,
                    is_static=is_static,
                )
                attributes.append({"name": field_name, "id": field_id, "static": is_static})

    return method_ids, attributes


def _extract_object_methods(obj_name, obj_node, module_path, source, file_path, file_imports, components):
    """
    Extract methods from an object literal:
        const utils = {
            add(a, b) { ... },             // shorthand method
            subtract: function(a, b) {},    // property: function
            multiply: (a, b) => a * b,      // property: arrow
            VERSION: '1.0'                  // data property (skip)
        };

    Each function-valued property becomes a METHOD under <module_path>.<obj_name>.
    """
    obj_id = f"{module_path}.{obj_name}"
    method_ids = []

    for child in obj_node.children:
        # Shorthand method definition  →  { foo() {} }
        if child.type == "method_definition":
            key = child.child_by_field_name("name")
            if not key:
                continue
            method_name = key.text.decode()
            method_id = f"{obj_id}.{method_name}"

            has_jsdoc, jsdoc = get_jsdoc(child, source)
            parameters = extract_parameters(child)
            signature = extract_signature(child, source)
            calls = extract_function_calls(child, source)
            inline_callbacks = extract_inline_functions(child, source)
            promise_handlers = extract_promise_handlers(child)

            m_start = child.start_point[0] + 1
            m_end = child.end_point[0] + 1
            body_text = source[child.start_byte:child.end_byte]
            is_gen = "*" in body_text.split("(")[0] if "(" in body_text else False

            components[method_id] = CodeComponent(
                id=method_id,
                name=method_name,
                type=ComponentType.METHOD,
                location=Location(file_path=file_path, start_line=m_start, end_line=m_end),
                source_code=body_text,
                signature=signature,
                parameters=parameters,
                existing_docstring=jsdoc if has_jsdoc else None,
                calls=calls,
                imports=file_imports,
                language="javascript",
                lines_of_code=m_end - m_start + 1,
                is_async='async' in body_text,
                is_generator=is_gen,
                metadata={
                    "inline_callbacks": inline_callbacks,
                    "promise_handlers": promise_handlers,
                    "parent_object": obj_name,
                }
            )
            method_ids.append(method_id)

        # Pair: key: value
        elif child.type == "pair":
            key_node = child.child_by_field_name("key")
            val_node = child.child_by_field_name("value")
            if not key_node or not val_node:
                continue

            prop_name = key_node.text.decode().strip("'\"")

            # arrow / function expression  →  METHOD
            if val_node.type in ("arrow_function", "function_expression", "function"):
                method_id = f"{obj_id}.{prop_name}"

                has_jsdoc, jsdoc = get_jsdoc(child, source)
                parameters = extract_parameters(val_node)
                signature = extract_signature(val_node, source)
                calls = extract_function_calls(val_node, source)
                inline_callbacks = extract_inline_functions(val_node, source)
                promise_handlers = extract_promise_handlers(val_node)

                m_start = child.start_point[0] + 1
                m_end = child.end_point[0] + 1
                body_text = source[child.start_byte:child.end_byte]

                components[method_id] = CodeComponent(
                    id=method_id,
                    name=prop_name,
                    type=ComponentType.METHOD,
                    location=Location(file_path=file_path, start_line=m_start, end_line=m_end),
                    source_code=body_text,
                    signature=signature,
                    parameters=parameters,
                    existing_docstring=jsdoc if has_jsdoc else None,
                    calls=calls,
                    imports=file_imports,
                    language="javascript",
                    lines_of_code=m_end - m_start + 1,
                    is_async='async' in body_text,
                    metadata={
                        "inline_callbacks": inline_callbacks,
                        "promise_handlers": promise_handlers,
                        "parent_object": obj_name,
                    }
                )
                method_ids.append(method_id)

    return method_ids


def extract_components(tree, source, file_path, module_path):
    """
    Extract JavaScript code components:
    - Function declarations (incl. generator: function* foo() {})
    - Arrow functions (const foo = () => {})
    - Function expressions (const foo = function() {}, module.exports = function() {})
    - Generator function expressions (const g = function*() {})
    - Class declarations and class expressions (const Foo = class {})
    - Class methods, constructors, fields (data + arrow), static fields
    - Object literal methods (const obj = { add() {}, sub: () => {} })
    - Export default anonymous functions / arrow functions
    - Global variables / constants (const X = 5, let config = {})
    - Module-level fallback for truly empty files

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

    # Track variable names already extracted as functions/classes
    # so we don't re-extract them as GLOBAL_VARIABLE
    _extracted_var_names = set()

    # ------------------------------------------------------------------
    # Helper: register a class (declaration or expression) and its body
    # ------------------------------------------------------------------
    def _register_class(class_node, class_name, jsdoc_node=None):
        nonlocal found_symbol
        found_symbol = True
        class_id = f"{module_path}.{class_name}"

        has_jsdoc, jsdoc = get_jsdoc(jsdoc_node or class_node, source)

        parent_classes = []
        super_node = class_node.child_by_field_name("superclass")
        if super_node:
            parent_classes = [super_node.text.decode()]

        start_line = class_node.start_point[0] + 1
        end_line = class_node.end_point[0] + 1

        method_ids, attrs = _extract_class_members(
            class_id, class_node, source, file_path, file_imports, components
        )

        components[class_id] = CodeComponent(
            id=class_id,
            name=class_name,
            type=ComponentType.CLASS,
            location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
            source_code=source[class_node.start_byte:class_node.end_byte],
            signature=f"class {class_name}",
            parent_classes=parent_classes,
            methods=method_ids,
            attributes=attrs,
            existing_docstring=jsdoc if has_jsdoc else None,
            imports=file_imports,
            language="javascript",
            lines_of_code=end_line - start_line + 1,
        )

    # ------------------------------------------------------------------
    # Helper: register a function-like node
    # ------------------------------------------------------------------
    def _register_function(func_node, name, *, jsdoc_node=None, is_generator=False, is_iife=False):
        nonlocal found_symbol
        found_symbol = True
        cid = f"{module_path}.{name}"

        has_jsdoc, jsdoc = get_jsdoc(jsdoc_node or func_node, source)
        parameters = extract_parameters(func_node)
        signature = extract_signature(func_node, source)
        calls = extract_function_calls(func_node, source)
        inline_callbacks = extract_inline_functions(func_node, source)
        promise_handlers = extract_promise_handlers(func_node)
        middleware = detect_middleware_calls(func_node)

        start_line = func_node.start_point[0] + 1
        end_line = func_node.end_point[0] + 1
        src = source[func_node.start_byte:func_node.end_byte]

        meta = {
            "inline_callbacks": inline_callbacks,
            "promise_handlers": promise_handlers,
            "middleware_calls": middleware,
        }
        if is_iife:
            meta["is_iife"] = True

        components[cid] = CodeComponent(
            id=cid,
            name=name,
            type=ComponentType.FUNCTION,
            location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
            source_code=src,
            signature=signature,
            parameters=parameters,
            existing_docstring=jsdoc if has_jsdoc else None,
            calls=calls,
            imports=file_imports,
            language="javascript",
            lines_of_code=end_line - start_line + 1,
            is_async='async' in src,
            is_generator=is_generator,
            metadata=meta,
        )

    # ------------------------------------------------------------------
    # Main AST walk
    # ------------------------------------------------------------------
    def walk(node):
        nonlocal found_symbol

        # -----------------------------------
        # SKIP: Import statements and comments
        # These are metadata, not components
        # import React from 'react'
        # /* JSDoc */
        # -----------------------------------
        if node.type in ("import_statement", "import_from_statement", "comment", "block_comment"):
            # Don't create components for imports/comments
            # But recursively process children (if any)
            for child in node.children:
                walk(child)
            return

        # -----------------------------------
        # FUNCTION DECLARATION
        # function foo() {}
        # -----------------------------------
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                _register_function(node, name_node.text.decode())

        # -----------------------------------
        # GENERATOR FUNCTION DECLARATION
        # function* gen() {}
        # -----------------------------------
        elif node.type == "generator_function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                _register_function(node, name_node.text.decode(), is_generator=True)

        # -----------------------------------
        # VARIABLE DECLARATOR
        #   const foo = () => {}           → FUNCTION
        #   const foo = function() {}      → FUNCTION  (handled here too)
        #   const foo = function*() {}     → FUNCTION + generator
        #   const Foo = class { ... }      → CLASS
        #   const obj = { m() {} }         → obj as VARIABLE + methods
        #   const X = 5 / "str" / [...]    → GLOBAL_VARIABLE
        # -----------------------------------
        elif node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")

            if not name_node or name_node.type != "identifier":
                # Destructuring patterns handled elsewhere
                for child in node.children:
                    walk(child)
                return

            name = name_node.text.decode()
            var_decl = node.parent  # lexical_declaration / variable_declaration

            if value_node:
                # ---- Arrow function ----
                if value_node.type == "arrow_function":
                    _extracted_var_names.add(name)
                    _register_function(
                        value_node, name,
                        jsdoc_node=var_decl,
                    )

                # ---- Function expression (incl. named) ----
                elif value_node.type in ("function_expression", "function"):
                    _extracted_var_names.add(name)
                    _register_function(
                        value_node, name,
                        jsdoc_node=var_decl,
                    )

                # ---- Generator function expression ----
                elif value_node.type in ("generator_function", "generator_function_expression"):
                    _extracted_var_names.add(name)
                    _register_function(
                        value_node, name,
                        jsdoc_node=var_decl,
                        is_generator=True,
                    )

                # ---- Class expression: const Foo = class {} ----
                elif value_node.type in ("class", "class_expression"):
                    _extracted_var_names.add(name)
                    _register_class(value_node, name, jsdoc_node=var_decl)
                    return  # don't recurse into class body again

                # ---- Object literal with methods ----
                elif value_node.type == "object":
                    has_methods = any(
                        c.type == "method_definition"
                        or (
                            c.type == "pair"
                            and c.child_by_field_name("value")
                            and c.child_by_field_name("value").type
                            in ("arrow_function", "function_expression", "function")
                        )
                        for c in value_node.children
                    )
                    if has_methods:
                        _extracted_var_names.add(name)
                        found_symbol = True
                        obj_id = f"{module_path}.{name}"
                        method_ids = _extract_object_methods(
                            name, value_node, module_path,
                            source, file_path, file_imports, components,
                        )
                        # Register the object itself as a VARIABLE that owns methods
                        start_line = node.start_point[0] + 1
                        end_line = node.end_point[0] + 1
                        has_jsdoc, jsdoc = get_jsdoc(var_decl, source) if var_decl else (False, "")
                        components[obj_id] = CodeComponent(
                            id=obj_id,
                            name=name,
                            type=ComponentType.VARIABLE,
                            location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                            source_code=source[node.start_byte:node.end_byte],
                            signature=f"const {name} = {{...}}",
                            methods=method_ids,
                            existing_docstring=jsdoc if has_jsdoc else None,
                            imports=file_imports,
                            language="javascript",
                            lines_of_code=end_line - start_line + 1,
                        )
                        return  # don't recurse into object body

                # ---- Any other value → GLOBAL_VARIABLE ----
                else:
                    # Only top-level variables (parent is program or export)
                    if _is_top_level(node):
                        _extracted_var_names.add(name)
                        found_symbol = True
                        cid = f"{module_path}.{name}"
                        start_line = node.start_point[0] + 1
                        end_line = node.end_point[0] + 1
                        has_jsdoc, jsdoc = get_jsdoc(var_decl, source) if var_decl else (False, "")
                        components[cid] = CodeComponent(
                            id=cid,
                            name=name,
                            type=ComponentType.GLOBAL_VARIABLE,
                            location=Location(file_path=file_path, start_line=start_line, end_line=end_line),
                            source_code=source[node.start_byte:node.end_byte],
                            signature=source[node.start_byte:node.end_byte].split('\n')[0].strip(),
                            existing_docstring=jsdoc if has_jsdoc else None,
                            imports=file_imports,
                            language="javascript",
                            lines_of_code=end_line - start_line + 1,
                        )

            # Value-less declarator with no initializer (e.g. `let x;`) — skip
            # Fall through to recurse children
            for child in node.children:
                walk(child)
            return

        # -----------------------------------
        # FUNCTION EXPRESSION  (standalone — not inside variable_declarator)
        # module.exports = function() {}
        # function(params) { ... }   (bare anonymous snippet)
        # -----------------------------------
        elif node.type in ("function_expression", "function"):
            # Skip if already handled by variable_declarator branch
            parent = node.parent
            if parent and parent.type == "variable_declarator":
                return

            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
            else:
                if parent and parent.type == "assignment_expression":
                    left = parent.child_by_field_name("left")
                    if left:
                        # module.exports → module_exports
                        # exports.foo → foo
                        left_text = left.text.decode()
                        if left.type == "member_expression":
                            prop = left.child_by_field_name("property")
                            obj = left.child_by_field_name("object")
                            if prop:
                                prop_name = prop.text.decode()
                                obj_name = obj.text.decode() if obj else ""
                                # module.exports / exports → use "default" as name
                                if prop_name == "exports" or obj_name == "exports":
                                    name = prop_name if obj_name == "exports" else "default"
                                else:
                                    name = prop_name
                            else:
                                name = left_text.replace(".", "_")
                        else:
                            name = left_text.replace(".", "_")
                    else:
                        name = None
                elif parent and parent.type == "expression_statement":
                    # Bare anonymous function at program root: function(x) { ... }
                    # Auto-name from params or position
                    params = extract_parameters(node)
                    if params:
                        name = "anonymous"
                    else:
                        name = "anonymous"
                else:
                    name = None

            if name:
                jsdoc_node = node if name_node else (node.parent or node)
                is_iife = False
                if parent and parent.type == "parenthesized_expression":
                    grandparent = parent.parent
                    if grandparent:
                        is_iife = detect_iife(grandparent)

                _register_function(
                    node, name,
                    jsdoc_node=jsdoc_node,
                    is_iife=is_iife,
                )

        # -----------------------------------
        # GENERATOR FUNCTION EXPRESSION (standalone)
        # module.exports = function*() {}
        # -----------------------------------
        elif node.type in ("generator_function", "generator_function_expression"):
            parent = node.parent
            if parent and parent.type == "variable_declarator":
                return  # handled above

            name_node = node.child_by_field_name("name")
            name = name_node.text.decode() if name_node else None

            if not name and parent:
                if parent.type == "assignment_expression":
                    left = parent.child_by_field_name("left")
                    if left and left.type == "member_expression":
                        prop = left.child_by_field_name("property")
                        name = prop.text.decode() if prop else left.text.decode().replace(".", "_")
                    elif left:
                        name = left.text.decode().replace(".", "_")
                elif parent.type == "expression_statement":
                    name = "anonymous"

            if name:
                _register_function(node, name, is_generator=True)

        # -----------------------------------
        # CLASS DECLARATION
        # class Foo { ... }
        # -----------------------------------
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                _register_class(node, name_node.text.decode())
                return  # don't recurse into class body

        # -----------------------------------
        # EXPORT DEFAULT anonymous function / arrow / class
        # export default function() {}
        # export default () => {}
        # export default class { ... }
        # -----------------------------------
        elif node.type == "export_statement":
            for child in node.children:
                # Named declarations inside export are handled by recursion
                if child.type in ("function_declaration", "generator_function_declaration",
                                  "class_declaration", "lexical_declaration",
                                  "variable_declaration"):
                    walk(child)
                    continue

                # Anonymous default arrow
                if child.type == "arrow_function":
                    _register_function(child, "default", jsdoc_node=node)
                    continue

                # Anonymous default function expression
                if child.type in ("function_expression", "function"):
                    name_node = child.child_by_field_name("name")
                    name = name_node.text.decode() if name_node else "default"
                    _register_function(child, name, jsdoc_node=node)
                    continue

                # Anonymous default generator
                if child.type in ("generator_function", "generator_function_expression"):
                    name_node = child.child_by_field_name("name")
                    name = name_node.text.decode() if name_node else "default"
                    _register_function(child, name, jsdoc_node=node, is_generator=True)
                    continue

                # Anonymous default class expression
                if child.type in ("class", "class_expression"):
                    name_node = child.child_by_field_name("name")
                    name = name_node.text.decode() if name_node else "default"
                    _register_class(child, name, jsdoc_node=node)
                    continue

                # For anything else inside export, recurse normally
                walk(child)
            return  # already iterated children

        for child in node.children:
            walk(child)

    # Helper: determine if a node sits at program / export top-level
    def _is_top_level(var_declarator_node):
        """Return True when the variable declarator lives at module scope."""
        parent = var_declarator_node.parent          # lexical_declaration / variable_declaration
        if not parent:
            return False
        grandparent = parent.parent
        if not grandparent:
            return False
        if grandparent.type == "program":
            return True
        # export const X = ...  →  grandparent is export_statement whose parent is program
        if grandparent.type == "export_statement":
            ggp = grandparent.parent
            return ggp is not None and ggp.type == "program"
        return False

    walk(root)

    # =====================================================
    # MODULE-LEVEL FALLBACK
    # Only for files with truly no extractable symbols
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
        if comp.type in (ComponentType.METHOD, ComponentType.CONSTRUCTOR,
                         ComponentType.FIELD, ComponentType.STATIC_FIELD):
            comp.module_path = '.'.join(parts[:-2]) if len(parts) > 2 else parts[0]
        else:
            comp.module_path = '.'.join(parts[:-1]) if len(parts) > 1 else parts[0]

    return components
