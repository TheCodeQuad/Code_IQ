from core.ir import CodeComponent


def get_docstring(node, source):
    """
    Extract docstring from a function or class definition.
    
    Args:
        node: tree-sitter node (function_definition or class_definition)
        source: full source code string
        
    Returns:
        tuple: (has_docstring: bool, docstring: str)
    """
    body = node.child_by_field_name("body")
    if not body:
        return False, ""
    
    # Look for the first expression statement in the body
    for child in body.children:
        if child.type == "expression_statement":
            # Check if it's a string literal
            for expr_child in child.children:
                if expr_child.type == "string":
                    # Extract the string content
                    docstring_text = expr_child.text.decode()
                    # Remove quotes (handle """, ''', ", ')
                    if docstring_text.startswith('"""') or docstring_text.startswith("'''"):
                        docstring_text = docstring_text[3:-3]
                    elif docstring_text.startswith('"') or docstring_text.startswith("'"):
                        docstring_text = docstring_text[1:-1]
                    return True, docstring_text.strip()
        # Stop at the first non-comment, non-docstring statement
        elif child.type not in ("comment",):
            break
    
    return False, ""


def extract_components(tree, source, file_path, module_path):
    """
    Extract all code components (classes, functions, methods, globals) from a parsed tree.
    
    This now includes:
    - Classes
    - Functions  
    - Methods
    - Module-level variables/constants (like GUI widgets, constants, etc.)
    
    Args:
        tree: Parsed tree-sitter tree
        source: Source code as string
        file_path: Full file path
        module_path: Module path (e.g., "package.module")
        
    Returns:
        dict: Mapping of component IDs to CodeComponent objects
    """
    components = {}
    root = tree.root_node

    def walk(node, parent_type=None):

        # -------- TOP-LEVEL FUNCTIONS --------
        if node.type in ("function_definition", "async_function_definition") and parent_type == "module":
            name = node.child_by_field_name("name").text.decode()
            cid = f"{module_path}.{name}"

            # Extract docstring
            has_docstring, docstring = get_docstring(node, source)

            components[cid] = CodeComponent(
                id=cid,
                language="python",
                type="function",
                file_path=file_path,
                module_path=module_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source_code=source[node.start_byte:node.end_byte],
                has_docstring=has_docstring,
                docstring=docstring,
            )

        # -------- CLASSES --------
        elif node.type == "class_definition":
            cname = node.child_by_field_name("name").text.decode()
            class_id = f"{module_path}.{cname}"

            # Extract docstring
            has_docstring, docstring = get_docstring(node, source)

            components[class_id] = CodeComponent(
                id=class_id,
                language="python",
                type="class",
                file_path=file_path,
                module_path=module_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source_code=source[node.start_byte:node.end_byte],
                has_docstring=has_docstring,
                docstring=docstring,
            )

            # Extract methods within the class
            body = node.child_by_field_name("body")
            if body:
                for stmt in body.children:

                    # ---------------- NORMAL METHOD ----------------
                    if stmt.type in ("function_definition", "async_function_definition"):
                        func_node = stmt

                    # ---------------- DECORATED METHOD ----------------
                    elif stmt.type == "decorated_definition":
                        func_node = None
                        for c in stmt.children:
                            if c.type in ("function_definition", "async_function_definition"):
                                func_node = c
                                break
                        if not func_node:
                            continue

                    else:
                        continue

                    # ---------- COMMON METHOD HANDLING ----------
                    method_name = func_node.child_by_field_name("name").text.decode()
                    method_id = f"{class_id}.{method_name}"

                    # Extract method docstring
                    method_has_docstring, method_docstring = get_docstring(func_node, source)

                    components[method_id] = CodeComponent(
                        id=method_id,
                        language="python",
                        type="method",
                        file_path=file_path,
                        module_path=module_path,
                        start_line=func_node.start_point[0] + 1,
                        end_line=func_node.end_point[0] + 1,
                        source_code=source[func_node.start_byte:func_node.end_byte],
                        has_docstring=method_has_docstring,
                        docstring=method_docstring,
                    )

        for c in node.children:
            walk(c, node.type)

    # -------- EXTRACT MODULE-LEVEL VARIABLES (GLOBALS) --------
    def extract_globals():
        """
        Extract module-level variable assignments.
        These include GUI widgets, constants, configuration objects, etc.
        """
        for child in root.children:
            # Top-level expression statements
            if child.type == "expression_statement":
                for expr_child in child.children:
                    if expr_child.type == "assignment":
                        lhs = expr_child.child_by_field_name("left")
                        if lhs and lhs.type == "identifier":
                            var_name = lhs.text.decode()
                            var_id = f"{module_path}.{var_name}"
                            
                            # Don't duplicate if already extracted
                            if var_id not in components:
                                components[var_id] = CodeComponent(
                                    id=var_id,
                                    language="python",
                                    type="global_variable",
                                    file_path=file_path,
                                    module_path=module_path,
                                    start_line=expr_child.start_point[0] + 1,
                                    end_line=expr_child.end_point[0] + 1,
                                    source_code=source[expr_child.start_byte:expr_child.end_byte],
                                    has_docstring=False,
                                    docstring="",
                                )
            
            # Top-level assignments (direct children of module)
            elif child.type == "assignment":
                lhs = child.child_by_field_name("left")
                if lhs and lhs.type == "identifier":
                    var_name = lhs.text.decode()
                    var_id = f"{module_path}.{var_name}"
                    
                    # Don't duplicate if already extracted
                    if var_id not in components:
                        components[var_id] = CodeComponent(
                            id=var_id,
                            language="python",
                            type="global_variable",
                            file_path=file_path,
                            module_path=module_path,
                            start_line=child.start_point[0] + 1,
                            end_line=child.end_point[0] + 1,
                            source_code=source[child.start_byte:child.end_byte],
                            has_docstring=False,
                            docstring="",
                        )

    # First extract classes, functions, and methods
    walk(root, "module")
    
    # Then extract global variables
    
    return components