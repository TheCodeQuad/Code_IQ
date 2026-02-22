from backend.models.code_component import CodeComponent, ComponentType, Location
import logging

logger = logging.getLogger(__name__)


def get_tsdoc(node, source):
    """
    Extract TSDoc/JSDoc comment from a function, class, or method declaration.
    """
    prev = node.prev_sibling
    while prev:
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
        if prev.type not in ("comment", "whitespace"):
            break
        prev = prev.prev_sibling
    return False, ""


def extract_parameters(node):
    """
    Extract parameters from functions / methods / arrow functions.
    """
    params = []
    pnode = node.child_by_field_name("parameters")
    if not pnode:
        return params

    for child in pnode.children:
        if child.type == "identifier":
            params.append(child.text.decode())
        elif child.type in ("required_parameter", "optional_parameter"):
            for c in child.children:
                if c.type == "identifier":
                    params.append(c.text.decode())
                    break
        elif child.type == "rest_pattern":
            for c in child.children:
                if c.type == "identifier":
                    params.append(f"...{c.text.decode()}")
                    break
        elif child.type in ("object_pattern", "array_pattern"):
            params.append(child.text.decode())

    return params


def extract_imports(tree):
    """
    Extract TypeScript import sources and names.
    Returns a dict: { imported_name: source_path }
    """
    imports = {}
    root = tree.root_node

    def walk(node):
        if node.type == "import_statement":
            src = node.child_by_field_name("source")
            source_path = src.text.decode().strip("'\"") if src else None
            
            if not source_path:
                return
            
            # Extract import clause
            import_clause = node.child_by_field_name("import_clause")
            if not import_clause:
                return
            
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
        
        for c in node.children:
            walk(c)

    walk(root)
    return imports


def extract_function_calls(node):
    """
    Extract identifier-based function calls.
    """
    calls = []

    def walk(n):
        if n.type == "call_expression":
            fn = n.child_by_field_name("function")
            if fn and fn.type == "identifier":
                calls.append(fn.text.decode())
            elif fn and fn.type == "member_expression":
                # Handle obj.method() calls
                obj = fn.child_by_field_name("object")
                if obj and obj.type == "identifier":
                    calls.append(obj.text.decode())
        for c in n.children:
            walk(c)

    walk(node)
    return calls


def extract_identifier_usages(node):
    """
    Extract all identifier usages within a node.
    Returns a set of identifier names.
    """
    usages = set()

    def walk(n):
        if n.type == "identifier":
            usages.add(n.text.decode())
        for c in n.children:
            walk(c)

    walk(node)
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
    # --------------------------------------------------
    global_vars = set()
    
    for child in root.children:
        if child.type == "variable_declaration":
            for decl in child.children:
                if decl.type == "variable_declarator":
                    name = decl.child_by_field_name("name")
                    if name and name.type == "identifier":
                        var_name = name.text.decode()
                        var_id = f"{module_path}.{var_name}"
                        global_vars.add(var_name)
                        
                        components[var_id] = CodeComponent(
                            id=var_id,
                            name=var_name,
                            type=ComponentType.GLOBAL_VARIABLE,
                            location=Location(
                                file_path=file_path,
                                start_line=child.start_point[0] + 1,
                                end_line=child.end_point[0] + 1
                            ),
                            source_code=source[child.start_byte:child.end_byte],
                            signature=source[child.start_byte:child.end_byte].split("\n")[0],
                            existing_docstring=None,
                            language="typescript",
                            lines_of_code=1,
                        )

    # --------------------------------------------------
    # WALK AST FOR ALL OTHER COMPONENTS
    # --------------------------------------------------
    def walk(node, parent_id=None):

        # ---------- FUNCTION DECLARATION ----------
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
                cid = f"{module_path}.{name}"

                has_doc, doc = get_tsdoc(node, source)
                params = extract_parameters(node)
                calls = extract_function_calls(node)
                
                # Extract all identifiers and exclude locals
                all_identifiers = extract_identifier_usages(node)
                local_names = set(params)
                local_names.add(name)  # Exclude function name itself
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
                    imports=list(imports.keys()),
                    calls=calls,
                    language="typescript",
                    lines_of_code=node.end_point[0] - node.start_point[0] + 1,
                    metadata={'identifiers': list(identifiers)},
                )

        # ---------- ARROW FUNCTION ----------
        if node.type == "variable_declarator":
            name = node.child_by_field_name("name")
            value = node.child_by_field_name("value")
            if name and value and value.type == "arrow_function":
                fn_name = name.text.decode()
                cid = f"{module_path}.{fn_name}"
                params = extract_parameters(value)
                calls = extract_function_calls(value)
                
                # Extract all identifiers and exclude locals
                all_identifiers = extract_identifier_usages(value)
                local_names = set(params)
                local_names.add(fn_name)  # Exclude function name itself
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
                    existing_docstring=None,
                    imports=list(imports.keys()),
                    calls=calls,
                    language="typescript",
                    lines_of_code=node.end_point[0] - node.start_point[0] + 1,
                    metadata={'identifiers': list(identifiers), 'arrow_function': True},
                )

        # ---------- CLASS ----------
        if node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                cname = name_node.text.decode()
                cid = f"{module_path}.{cname}"

                has_doc, doc = get_tsdoc(node, source)

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
                    language="typescript",
                    lines_of_code=node.end_point[0] - node.start_point[0] + 1,
                )

                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        if child.type == "method_definition":
                            key = child.child_by_field_name("name")
                            if key:
                                mname = key.text.decode()
                                mid = f"{cid}.{mname}"

                                m_has_doc, m_doc = get_tsdoc(child, source)
                                m_params = extract_parameters(child)
                                m_calls = extract_function_calls(child)
                                
                                # Extract all identifiers and exclude locals
                                m_all_identifiers = extract_identifier_usages(child)
                                m_local_names = set(m_params)
                                m_local_names.add(mname)  # Exclude method name itself
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
                                    imports=list(imports.keys()),
                                    calls=m_calls,
                                    language="typescript",
                                    lines_of_code=child.end_point[0] - child.start_point[0] + 1,
                                    metadata={'identifiers': list(m_identifiers)},
                                )

        # ---------- INTERFACE ----------
        if node.type == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                iname = name_node.text.decode()
                iid = f"{module_path}.{iname}"

                has_doc, doc = get_tsdoc(node, source)

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
                    language="typescript",
                    lines_of_code=node.end_point[0] - node.start_point[0] + 1,
                    metadata={'interface': True},
                )

        # ---------- TYPE ALIAS ----------
        if node.type == "type_alias_declaration":
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
        if node.type == "enum_declaration":
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

        for c in node.children:
            walk(c, parent_id)

    walk(root)

    # --------------------------------------------------
    # DEPENDENCY RESOLUTION PASS
    # --------------------------------------------------
    name_map = {}
    for cid in components:
        short = cid.split(".")[-1]
        name_map.setdefault(short, []).append(cid)

    for comp in components.values():
        deps = set()
        
        # Get identifiers from metadata (where we stored them)
        identifiers = comp.metadata.get('identifiers', [])
        
        # Resolve dependencies using identifiers (includes calls, globals, imports)
        for ident in identifiers:
            # Check if it's a global variable
            if ident in global_vars:
                deps.add(f"{module_path}.{ident}")
            # Check if it's an imported name
            elif ident in import_names:
                # Mark as external dependency (will be resolved by dependency graph builder)
                deps.add(f"import:{ident}")
            # Check if it's another component in this module
            elif ident in name_map:
                deps.update(name_map[ident])
        
        comp.depends_on = sorted(deps)
        
        # Debug logging for key components
        if comp.type in (ComponentType.FUNCTION, ComponentType.METHOD) and deps:
            logger.debug(f"[TS Extractor] {comp.id}: identifiers={identifiers[:5]}, depends_on={list(deps)[:5]}")

    return components

    return components
