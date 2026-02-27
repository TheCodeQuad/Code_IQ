from backend.models.code_component import CodeComponent, ComponentType, Location, Parameter
import logging

logger = logging.getLogger(__name__)


def get_tsdoc(node, source):
    """
    Extract TSDoc/JSDoc comment from a function, class, or method declaration.
    Handles blank lines / whitespace nodes between the comment and the declaration.
    Also handles single-line // doc comments grouped above a declaration.
    """
    prev = node.prev_sibling

    while prev:
        # JSDoc / TSDoc block comment: /** ... */
        if prev.type == "comment":
            text = prev.text.decode()
            if text.startswith("/**") and text.endswith("*/"):
                body = text[3:-2]
                lines = []
                for line in body.split("\n"):
                    line = line.strip()
                    if line.startswith("*"):
                        line = line[1:].strip()
                    lines.append(line)
                return True, "\n".join(lines).strip()

            # Accumulated single-line // comments directly above
            if text.startswith("//"):
                doc_lines = []
                cur = prev
                while cur and cur.type == "comment":
                    t = cur.text.decode()
                    if t.startswith("//"):
                        doc_lines.insert(0, t[2:].strip())
                        cur = cur.prev_sibling
                        while cur and cur.type in ("whitespace", "\n"):
                            cur = cur.prev_sibling
                    else:
                        break
                if doc_lines:
                    return True, "\n".join(doc_lines).strip()

        # Allow skipping whitespace / newline nodes between doc and declaration
        elif prev.type in ("whitespace", "\n"):
            prev = prev.prev_sibling
            continue

        # Hit a real non-comment, non-whitespace node => no doc found
        else:
            break

    return False, ""


def _extract_return_type(node):
    """
    Extract the return type annotation from a function / method / arrow function.
    """
    rt = node.child_by_field_name("return_type")
    if rt:
        text = rt.text.decode().lstrip(":").strip()
        return text if text else None

    for child in node.children:
        if child.type == "type_annotation":
            params = node.child_by_field_name("parameters")
            if params and child.start_byte > params.end_byte:
                text = child.text.decode().lstrip(":").strip()
                return text if text else None
    return None


def _extract_decorators(node):
    """
    Extract decorator names from nodes preceding a class / method declaration.
    """
    decorators = []
    prev = node.prev_sibling
    while prev:
        if prev.type == "decorator":
            decorators.insert(0, prev.text.decode())
        elif prev.type in ("comment", "whitespace", "\n"):
            prev = prev.prev_sibling
            continue
        else:
            break
        prev = prev.prev_sibling
    return decorators


def _check_async(node):
    """
    Check if a function / method / arrow function is async.
    """
    for child in node.children:
        if child.type == "async":
            return True
        if child.type in ("function", "(", "formal_parameters", "identifier"):
            break
    return False


def _extract_heritage(node):
    """
    Extract parent classes / interfaces from a class or interface declaration.
    Handles extends, implements, and type_identifier nodes.
    """
    _heritage_types = (
        "identifier", "type_identifier", "generic_type", "nested_identifier",
        "nested_type_identifier",
    )
    parents = []
    for child in node.children:
        if child.type in ("class_heritage", "extends_clause", "implements_clause",
                          "extends_type_clause"):
            for sub in child.children:
                if sub.type in ("extends_clause", "implements_clause",
                                "extends_type_clause"):
                    for t in sub.children:
                        if t.type in _heritage_types:
                            parents.append(t.text.decode())
                elif sub.type in _heritage_types:
                    parents.append(sub.text.decode())
    return parents


def _extract_class_attributes(body_node, source):
    """
    Extract class property definitions (attributes / fields) from a class body.
    """
    attrs = []
    if not body_node:
        return attrs

    for child in body_node.children:
        if child.type in ("public_field_definition", "property_definition"):
            attr = {'name': '', 'type': None, 'is_static': False, 'visibility': 'public'}

            for sub in child.children:
                if sub.type == "property_identifier":
                    attr['name'] = sub.text.decode()
                elif sub.type == "identifier":
                    if not attr['name']:
                        attr['name'] = sub.text.decode()
                elif sub.type == "type_annotation":
                    attr['type'] = sub.text.decode().lstrip(":").strip()
                elif sub.type == "accessibility_modifier":
                    attr['visibility'] = sub.text.decode()
                elif sub.type == "static":
                    attr['is_static'] = True

            if attr['name']:
                attrs.append(attr)

    return attrs


def extract_parameters_typed(node):
    """
    Extract parameters from functions / methods / arrow functions.
    Returns a list of Parameter objects.
    """
    params = []
    pnode = node.child_by_field_name("parameters")
    if not pnode:
        return params

    for child in pnode.children:
        if child.type == "identifier":
            params.append(Parameter(name=child.text.decode()))

        elif child.type in ("required_parameter", "optional_parameter"):
            name = None
            type_hint = None
            default_val = None
            is_required = child.type == "required_parameter"

            for c in child.children:
                if c.type == "identifier" and name is None:
                    name = c.text.decode()
                elif c.type == "type_annotation":
                    type_hint = c.text.decode().lstrip(":").strip()

            val_node = child.child_by_field_name("value")
            if val_node:
                default_val = val_node.text.decode()

            if name:
                params.append(Parameter(
                    name=name,
                    type_hint=type_hint,
                    default_value=default_val,
                    is_required=is_required,
                ))

        elif child.type == "rest_pattern":
            name = None
            for c in child.children:
                if c.type == "identifier":
                    name = f"...{c.text.decode()}"
                    break
            if name:
                params.append(Parameter(name=name))

        elif child.type in ("object_pattern", "array_pattern"):
            params.append(Parameter(name=child.text.decode()))

    return params


def extract_parameters(node):
    """
    Extract parameter names as plain strings (for identifier filtering).
    """
    return [p.name.lstrip('.') for p in extract_parameters_typed(node)]


def extract_imports(tree):
    """
    Extract TypeScript import sources and names.
    Uses iterative traversal to avoid recursion limits on large files.
    Returns a dict: { imported_name: source_path }
    """
    imports = {}
    stack = [tree.root_node]

    while stack:
        node = stack.pop()
        if node.type == "import_statement":
            src = node.child_by_field_name("source")
            source_path = src.text.decode().strip("'\"") if src else None

            if not source_path:
                continue

            import_clause = node.child_by_field_name("import_clause")
            if not import_clause:
                continue

            # Handle default imports: import Foo from './foo'
            for child in import_clause.children:
                if child.type == "identifier":
                    imports[child.text.decode()] = source_path

            # Handle named imports: import { bar, baz } from './module'
            named_imports = import_clause.child_by_field_name("named_imports")
            if named_imports:
                for child in named_imports.children:
                    if child.type == "import_specifier":
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            imports[name_node.text.decode()] = source_path

            # Handle namespace imports: import * as utils from './utils'
            namespace_import = import_clause.child_by_field_name("namespace_import")
            if namespace_import:
                for child in namespace_import.children:
                    if child.type == "identifier":
                        imports[child.text.decode()] = source_path
        else:
            for c in node.children:
                stack.append(c)

    return imports


def extract_function_calls(node):
    """
    Extract function / method calls including this.method() and obj.method().
    Uses iterative traversal to avoid recursion limits on large files.
    """
    calls = []
    stack = [node]

    while stack:
        n = stack.pop()
        if n.type == "call_expression":
            fn = n.child_by_field_name("function")
            if fn:
                if fn.type == "identifier":
                    calls.append(fn.text.decode())
                elif fn.type == "member_expression":
                    obj = fn.child_by_field_name("object")
                    prop = fn.child_by_field_name("property")
                    if obj and prop:
                        obj_text = obj.text.decode()
                        prop_text = prop.text.decode()
                        if obj.type == "this":
                            calls.append(prop_text)
                        elif obj.type == "identifier":
                            calls.append(f"{obj_text}.{prop_text}")
                            calls.append(obj_text)
        for c in n.children:
            stack.append(c)

    return calls


def extract_identifier_usages(node):
    """
    Extract all identifier usages within a node.
    Uses iterative traversal to avoid recursion limits on large files.
    Returns a set of identifier names.
    """
    usages = set()
    stack = [node]

    while stack:
        n = stack.pop()
        if n.type == "identifier":
            usages.add(n.text.decode())
        for c in n.children:
            stack.append(c)

    return usages


def extract_components(tree, source, file_path, module_path):
    """
    Extract all code components from a TypeScript file.
    """
    components = {}
    root = tree.root_node
    lines = source.splitlines()

    # --------------------------------------------------
    # MODULE COMPONENT
    # --------------------------------------------------
    components[module_path] = CodeComponent(
        id=module_path,
        name=module_path.split(".")[-1],
        type=ComponentType.MODULE,
        location=Location(
            file_path=file_path,
            start_line=1,
            end_line=len(lines)
        ),
        source_code=source,
        signature="",
        existing_docstring=None,
        language="typescript",
        lines_of_code=len(lines),
    )

    imports = extract_imports(tree)
    import_names = set(imports.keys())

    # --------------------------------------------------
    # GLOBAL VARIABLES (FIRST PASS)
    # Handles both bare `const x = ...` and `export const x = ...`
    # --------------------------------------------------
    global_vars = set()

    def _register_global_var(var_decl_node, parent_node):
        """Register a variable_declarator as a global variable component."""
        name_node = var_decl_node.child_by_field_name("name")
        if name_node and name_node.type == "identifier":
            var_name = name_node.text.decode()
            var_id = f"{module_path}.{var_name}"
            global_vars.add(var_name)

            components[var_id] = CodeComponent(
                id=var_id,
                name=var_name,
                type=ComponentType.GLOBAL_VARIABLE,
                location=Location(
                    file_path=file_path,
                    start_line=parent_node.start_point[0] + 1,
                    end_line=parent_node.end_point[0] + 1
                ),
                source_code=source[parent_node.start_byte:parent_node.end_byte],
                signature=source[parent_node.start_byte:parent_node.end_byte].split("\n")[0],
                existing_docstring=None,
                language="typescript",
                lines_of_code=parent_node.end_point[0] - parent_node.start_point[0] + 1,
            )

    for child in root.children:
        # Bare: const x = ... / let x = ... / var x = ...
        if child.type in ("variable_declaration", "lexical_declaration"):
            for decl in child.children:
                if decl.type == "variable_declarator":
                    _register_global_var(decl, child)

        # Exported: export const x = ...
        elif child.type == "export_statement":
            for sub in child.children:
                if sub.type in ("variable_declaration", "lexical_declaration"):
                    for decl in sub.children:
                        if decl.type == "variable_declarator":
                            _register_global_var(decl, child)

    # --------------------------------------------------
    # WALK AST FOR ALL OTHER COMPONENTS (iterative)
    # --------------------------------------------------
    ast_stack = list(root.children)

    while ast_stack:
        node = ast_stack.pop()

        # ---------- FUNCTION DECLARATION ----------
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
                cid = f"{module_path}.{name}"

                has_doc, doc = get_tsdoc(node, source)
                params_typed = extract_parameters_typed(node)
                params_names = [p.name.lstrip('.') for p in params_typed]
                calls = extract_function_calls(node)
                return_type = _extract_return_type(node)
                decorators = _extract_decorators(node)
                is_async = _check_async(node)

                # Extract all identifiers and exclude locals
                all_identifiers = extract_identifier_usages(node)
                local_names = set(params_names)
                local_names.add(name)
                identifiers = all_identifiers - local_names

                components[cid] = CodeComponent(
                    id=cid,
                    name=name,
                    type=ComponentType.FUNCTION,
                    location=Location(
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=source[node.start_byte:node.end_byte].split("\n")[0],
                    existing_docstring=doc if has_doc else None,
                    parameters=params_typed,
                    return_type=return_type,
                    decorators=decorators,
                    imports=list(imports.keys()),
                    calls=calls,
                    is_async=is_async,
                    language="typescript",
                    lines_of_code=node.end_point[0] - node.start_point[0] + 1,
                    metadata={'identifiers': list(identifiers)},
                )

        # ---------- ARROW FUNCTION (module-level) ----------
        elif node.type == "variable_declarator":
            name_n = node.child_by_field_name("name")
            value = node.child_by_field_name("value")
            if name_n and value and value.type == "arrow_function":
                fn_name = name_n.text.decode()
                cid = f"{module_path}.{fn_name}"

                # Upgrade: if already registered as global variable, replace with function
                if cid in components and components[cid].type == ComponentType.GLOBAL_VARIABLE:
                    del components[cid]
                    global_vars.discard(fn_name)

                has_doc, doc = get_tsdoc(node.parent if node.parent else node, source)
                params_typed = extract_parameters_typed(value)
                params_names = [p.name.lstrip('.') for p in params_typed]
                calls = extract_function_calls(value)
                return_type = _extract_return_type(value)
                is_async = _check_async(value)

                all_identifiers = extract_identifier_usages(value)
                local_names = set(params_names)
                local_names.add(fn_name)
                identifiers = all_identifiers - local_names

                components[cid] = CodeComponent(
                    id=cid,
                    name=fn_name,
                    type=ComponentType.FUNCTION,
                    location=Location(
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=source[node.start_byte:node.end_byte].split("\n")[0],
                    existing_docstring=doc if has_doc else None,
                    parameters=params_typed,
                    return_type=return_type,
                    imports=list(imports.keys()),
                    calls=calls,
                    is_async=is_async,
                    language="typescript",
                    lines_of_code=node.end_point[0] - node.start_point[0] + 1,
                    metadata={'identifiers': list(identifiers), 'arrow_function': True},
                )

        # ---------- CLASS / ABSTRACT CLASS ----------
        elif node.type in ("class_declaration", "abstract_class_declaration"):
            name_node = node.child_by_field_name("name")
            if name_node:
                cname = name_node.text.decode()
                cid = f"{module_path}.{cname}"

                has_doc, doc = get_tsdoc(node, source)
                decorators = _extract_decorators(node)
                parent_classes = _extract_heritage(node)

                body = node.child_by_field_name("body")
                attributes = _extract_class_attributes(body, source)
                method_ids = []
                is_abstract = (node.type == "abstract_class_declaration")

                class_meta = {}
                if is_abstract:
                    class_meta['abstract'] = True

                components[cid] = CodeComponent(
                    id=cid,
                    name=cname,
                    type=ComponentType.CLASS,
                    location=Location(
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=source[node.start_byte:node.end_byte].split("\n")[0],
                    existing_docstring=doc if has_doc else None,
                    decorators=decorators,
                    parent_classes=parent_classes,
                    attributes=attributes,
                    language="typescript",
                    lines_of_code=node.end_point[0] - node.start_point[0] + 1,
                    metadata=class_meta,
                )

                if body:
                    for child in body.children:
                        # Regular methods and abstract method definitions
                        if child.type in ("method_definition", "abstract_method_definition"):
                            key = child.child_by_field_name("name")
                            if key:
                                mname = key.text.decode()
                                mid = f"{cid}.{mname}"
                                method_ids.append(mid)

                                m_has_doc, m_doc = get_tsdoc(child, source)
                                m_params_typed = extract_parameters_typed(child)
                                m_params_names = [p.name.lstrip('.') for p in m_params_typed]
                                m_calls = extract_function_calls(child)
                                m_return_type = _extract_return_type(child)
                                m_decorators = _extract_decorators(child)
                                m_is_async = _check_async(child)

                                m_all_identifiers = extract_identifier_usages(child)
                                m_local_names = set(m_params_names)
                                m_local_names.add(mname)
                                m_identifiers = m_all_identifiers - m_local_names

                                comp_type = ComponentType.CONSTRUCTOR if mname == "constructor" else ComponentType.METHOD

                                m_meta = {'identifiers': list(m_identifiers)}
                                if child.type == "abstract_method_definition":
                                    m_meta['abstract'] = True

                                components[mid] = CodeComponent(
                                    id=mid,
                                    name=mname,
                                    type=comp_type,
                                    location=Location(
                                        file_path=file_path,
                                        start_line=child.start_point[0] + 1,
                                        end_line=child.end_point[0] + 1
                                    ),
                                    source_code=source[child.start_byte:child.end_byte],
                                    signature=source[child.start_byte:child.end_byte].split("\n")[0],
                                    existing_docstring=m_doc if m_has_doc else None,
                                    parameters=m_params_typed,
                                    return_type=m_return_type,
                                    decorators=m_decorators,
                                    imports=list(imports.keys()),
                                    calls=m_calls,
                                    is_async=m_is_async,
                                    language="typescript",
                                    lines_of_code=child.end_point[0] - child.start_point[0] + 1,
                                    metadata=m_meta,
                                )

                        # Arrow function class properties: bar = () => {}
                        elif child.type in ("public_field_definition", "property_definition"):
                            prop_name_node = None
                            prop_value_node = None
                            for sub in child.children:
                                if sub.type in ("property_identifier", "identifier") and prop_name_node is None:
                                    prop_name_node = sub
                                if sub.type == "arrow_function":
                                    prop_value_node = sub

                            if prop_name_node and prop_value_node:
                                mname = prop_name_node.text.decode()
                                mid = f"{cid}.{mname}"
                                method_ids.append(mid)

                                m_has_doc, m_doc = get_tsdoc(child, source)
                                m_params_typed = extract_parameters_typed(prop_value_node)
                                m_params_names = [p.name.lstrip('.') for p in m_params_typed]
                                m_calls = extract_function_calls(prop_value_node)
                                m_return_type = _extract_return_type(prop_value_node)
                                m_is_async = _check_async(prop_value_node)
                                m_decorators = _extract_decorators(child)

                                m_all_identifiers = extract_identifier_usages(prop_value_node)
                                m_local_names = set(m_params_names)
                                m_local_names.add(mname)
                                m_identifiers = m_all_identifiers - m_local_names

                                components[mid] = CodeComponent(
                                    id=mid,
                                    name=mname,
                                    type=ComponentType.METHOD,
                                    location=Location(
                                        file_path=file_path,
                                        start_line=child.start_point[0] + 1,
                                        end_line=child.end_point[0] + 1
                                    ),
                                    source_code=source[child.start_byte:child.end_byte],
                                    signature=source[child.start_byte:child.end_byte].split("\n")[0],
                                    existing_docstring=m_doc if m_has_doc else None,
                                    parameters=m_params_typed,
                                    return_type=m_return_type,
                                    decorators=m_decorators,
                                    imports=list(imports.keys()),
                                    calls=m_calls,
                                    is_async=m_is_async,
                                    language="typescript",
                                    lines_of_code=child.end_point[0] - child.start_point[0] + 1,
                                    metadata={'identifiers': list(m_identifiers), 'arrow_function': True},
                                )

                # Update class component with method IDs
                components[cid].methods = method_ids

        # ---------- INTERFACE ----------
        elif node.type == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                iname = name_node.text.decode()
                iid = f"{module_path}.{iname}"

                has_doc, doc = get_tsdoc(node, source)
                parent_classes = _extract_heritage(node)

                # Walk interface body for method/property signatures
                method_ids = []
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        if child.type in ("method_signature", "property_signature"):
                            sig_name_node = child.child_by_field_name("name")
                            if sig_name_node:
                                sname = sig_name_node.text.decode()
                                sid = f"{iid}.{sname}"
                                method_ids.append(sid)

                                s_has_doc, s_doc = get_tsdoc(child, source)
                                s_params_typed = extract_parameters_typed(child)
                                s_return_type = _extract_return_type(child)

                                components[sid] = CodeComponent(
                                    id=sid,
                                    name=sname,
                                    type=ComponentType.METHOD,
                                    location=Location(
                                        file_path=file_path,
                                        start_line=child.start_point[0] + 1,
                                        end_line=child.end_point[0] + 1
                                    ),
                                    source_code=source[child.start_byte:child.end_byte],
                                    signature=source[child.start_byte:child.end_byte].split("\n")[0],
                                    existing_docstring=s_doc if s_has_doc else None,
                                    parameters=s_params_typed,
                                    return_type=s_return_type,
                                    imports=list(imports.keys()),
                                    language="typescript",
                                    lines_of_code=child.end_point[0] - child.start_point[0] + 1,
                                    metadata={'interface_member': True},
                                )

                components[iid] = CodeComponent(
                    id=iid,
                    name=iname,
                    type=ComponentType.CLASS,
                    location=Location(
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=source[node.start_byte:node.end_byte].split("\n")[0],
                    existing_docstring=doc if has_doc else None,
                    parent_classes=parent_classes,
                    methods=method_ids,
                    language="typescript",
                    lines_of_code=node.end_point[0] - node.start_point[0] + 1,
                    metadata={'interface': True},
                )

        # ---------- TYPE ALIAS ----------
        elif node.type == "type_alias_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                tname = name_node.text.decode()
                tid = f"{module_path}.{tname}"

                has_doc, doc = get_tsdoc(node, source)

                components[tid] = CodeComponent(
                    id=tid,
                    name=tname,
                    type=ComponentType.CLASS,
                    location=Location(
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=source[node.start_byte:node.end_byte].split("\n")[0],
                    existing_docstring=doc if has_doc else None,
                    language="typescript",
                    lines_of_code=node.end_point[0] - node.start_point[0] + 1,
                    metadata={'type_alias': True},
                )

        # ---------- ENUM ----------
        elif node.type == "enum_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                ename = name_node.text.decode()
                eid = f"{module_path}.{ename}"

                has_doc, doc = get_tsdoc(node, source)

                components[eid] = CodeComponent(
                    id=eid,
                    name=ename,
                    type=ComponentType.CLASS,
                    location=Location(
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=source[node.start_byte:node.end_byte].split("\n")[0],
                    existing_docstring=doc if has_doc else None,
                    language="typescript",
                    lines_of_code=node.end_point[0] - node.start_point[0] + 1,
                    metadata={'enum': True},
                )

        # Push children onto the stack for iterative traversal
        for c in node.children:
            ast_stack.append(c)

    # --------------------------------------------------
    # DEPENDENCY RESOLUTION PASS
    # --------------------------------------------------
    name_map = {}
    for cid in components:
        short = cid.split(".")[-1]
        name_map.setdefault(short, []).append(cid)

    for comp in components.values():
        deps = set()

        # Get identifiers from metadata
        identifiers = comp.metadata.get('identifiers', [])

        # Also use calls list for dependency resolution (catches this.method(), obj.method())
        call_names = set()
        for call in (comp.calls or []):
            if "." in call:
                parts = call.split(".")
                call_names.add(parts[-1])  # method name
                call_names.add(parts[0])   # object name
            else:
                call_names.add(call)

        all_refs = set(identifiers) | call_names

        # Resolve dependencies
        for ident in all_refs:
            if ident in global_vars:
                deps.add(f"{module_path}.{ident}")
            elif ident in import_names:
                deps.add(f"import:{ident}")
            elif ident in name_map:
                for target_cid in name_map[ident]:
                    if target_cid != comp.id:
                        deps.add(target_cid)

        # Remove self-reference
        deps.discard(comp.id)

        comp.depends_on = sorted(deps)

        if comp.type in (ComponentType.FUNCTION, ComponentType.METHOD) and deps:
            logger.debug(f"[TS Extractor] {comp.id}: identifiers={identifiers[:5]}, depends_on={list(deps)[:5]}")

    return components
