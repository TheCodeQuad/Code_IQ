from typing import List
from backend.models.code_component import CodeComponent, Location, Parameter, ComponentType


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


def extract_parameters(func_node):
    """
    Extract parameters from a function definition node.
    
    Args:
        func_node: tree-sitter function definition node
        
    Returns:
        list: List of Parameter objects
    """
    parameters = []
    params = func_node.child_by_field_name("parameters")
    
    if params:
        for child in params.children:
            if child.type == "identifier":
                param_name = child.text.decode()
                parameters.append(Parameter(name=param_name))
            elif child.type == "typed_parameter":
                # Handle typed parameters like (x: int, y: str)
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                if name_node:
                    param_name = name_node.text.decode()
                    param_type = type_node.text.decode() if type_node else None
                    parameters.append(Parameter(name=param_name, type_hint=param_type))
    
    return parameters


def extract_signature(func_node, source):
    """
    Extract function signature from node
    
    Args:
        func_node: tree-sitter function definition node
        source: source code
        
    Returns:
        str: Function signature
    """
    # Extract from source code between def and : (or async def and :)
    sig_start = func_node.start_byte
    sig_end = func_node.end_byte
    
    # Find the colon that ends the signature
    source_text = source[sig_start:sig_end]
    colon_pos = source_text.find(':')
    if colon_pos != -1:
        return source_text[:colon_pos+1].strip()
    return source_text.split('\n')[0]  # Fallback to first line


def extract_imports_and_decorators(tree, source, module_path):
    """Extract all imports and decorators from the file"""
    imports = []
    decorators = []
    root = tree.root_node
    
    def walk(node):
        # Collect imports
        if node.type == "import_statement":
            for child in node.children:
                if child.type in ("dotted_name", "aliased_import"):
                    imports.append(child.text.decode())
        
        elif node.type == "import_from_statement":
            # Extract module name
            for child in node.children:
                if child.type == "dotted_name":
                    imports.append(child.text.decode())
        
        # Collect decorators
        elif node.type == "decorator":
            decorators.append(node.text.decode())
        
        for child in node.children:
            walk(child)
    
    walk(root)
    return imports, decorators


def extract_function_calls(func_node, source):
    """Extract all function/method calls within a function"""
    calls = []
    
    def walk(node):
        # Find call expressions
        if node.type == "call":
            fn = node.child_by_field_name("function")
            if fn:
                call_text = fn.text.decode()
                calls.append(call_text)
        
        for child in node.children:
            walk(child)
    
    walk(func_node)
    return calls

def _extract_module_level_vars(root) -> List[str]:
    """Extract module-level variable names"""
    vars = []
    for child in root.children:
        if child.type == "assignment":
            lhs = child.child_by_field_name("left")
            if lhs and lhs.type == "identifier":
                vars.append(lhs.text.decode())
        elif child.type == "expression_statement":
            for expr_child in child.children:
                if expr_child.type == "assignment":
                    lhs = expr_child.child_by_field_name("left")
                    if lhs and lhs.type == "identifier":
                        vars.append(lhs.text.decode())
    return vars

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
    
    # FIX: Extract module-level variables for shared state detection
    module_vars = _extract_module_level_vars(root)
    
    file_imports, file_decorators = extract_imports_and_decorators(tree, source, module_path)

    def walk(node, parent_type=None):

        # -------- TOP-LEVEL FUNCTIONS --------
        if node.type in ("function_definition", "async_function_definition") and parent_type == "module":
            name = node.child_by_field_name("name").text.decode()
            cid = f"{module_path}.{name}"

            # Extract docstring
            has_docstring, docstring = get_docstring(node, source)
            
            # Extract parameters
            parameters = extract_parameters(node)
            
            # Calculate lines of code
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            lines_of_code = end_line - start_line + 1
            
            # Extract signature
            signature = extract_signature(node, source)
            
            # Extract calls
            func_calls = extract_function_calls(node, source)
            
            # Detect if async
            is_async = node.type == "async_function_definition"

            components[cid] = CodeComponent(
                id=cid,
                name=name,
                type=ComponentType.FUNCTION,
                location=Location(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line
                ),
                source_code=source[node.start_byte:node.end_byte],
                signature=signature,
                existing_docstring=docstring if has_docstring else None,
                parameters=parameters,
                decorators=file_decorators,
                calls=func_calls,
                imports=file_imports,
                language="python",
                lines_of_code=lines_of_code,
                is_async=is_async,
            )

            # NEW: Detect shared state dependencies
            component_obj = components[cid]
            component_obj.metadata['shared_state_dependencies'] = [
                var for var in module_vars if var in component_obj.source_code
            ]

        # -------- CLASSES --------
        elif node.type == "class_definition":
            cname = node.child_by_field_name("name").text.decode()
            class_id = f"{module_path}.{cname}"

            # Extract docstring
            has_docstring, docstring = get_docstring(node, source)
            
            # Calculate lines of code
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            lines_of_code = end_line - start_line + 1
            
            # Extract signature
            signature = extract_signature(node, source)

            components[class_id] = CodeComponent(
                id=class_id,
                name=cname,
                type=ComponentType.CLASS,
                location=Location(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line
                ),
                source_code=source[node.start_byte:node.end_byte],
                signature=signature,
                existing_docstring=docstring if has_docstring else None,
                parameters=[],
                decorators=file_decorators,
                imports=file_imports,
                language="python",
                lines_of_code=lines_of_code,
            )

            # # NEW: Detect shared state dependencies
            # component_obj = components[class_id]
            # component_obj.metadata['shared_state_dependencies'] = [
            #     var for var in module_vars if var in component_obj.source_code
            # ]

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

                    # Extract parameters
                    method_parameters = extract_parameters(func_node)

                    # Calculate lines of code
                    method_start_line = func_node.start_point[0] + 1
                    method_end_line = func_node.end_point[0] + 1
                    method_lines_of_code = method_end_line - method_start_line + 1
                    
                    # Extract signature
                    method_signature = extract_signature(func_node, source)
                    
                    # Extract calls
                    method_calls = extract_function_calls(func_node, source)
                    
                    # Detect if async
                    is_async = func_node.type == "async_function_definition"
                    
                    # Detect if static/class method
                    is_static = method_name in ("__new__", "__init_subclass__")
                    is_class_method = False
                    
                    # Check for @classmethod or @staticmethod decorators
                    if stmt.type == "decorated_definition":
                        for decorator in stmt.children:
                            if decorator.type == "decorator":
                                deco_text = decorator.text.decode().lower()
                                if "@staticmethod" in deco_text:
                                    is_static = True
                                elif "@classmethod" in deco_text:
                                    is_class_method = True

                    components[method_id] = CodeComponent(
                        id=method_id,
                        name=method_name,
                        type=ComponentType.METHOD,
                        location=Location(
                            file_path=file_path,
                            start_line=method_start_line,
                            end_line=method_end_line
                        ),
                        source_code=source[func_node.start_byte:func_node.end_byte],
                        signature=method_signature,
                        existing_docstring=method_docstring if method_has_docstring else None,
                        parameters=method_parameters,
                        decorators=file_decorators,
                        calls=method_calls,
                        imports=file_imports,
                        language="python",
                        lines_of_code=method_lines_of_code,
                        is_async=is_async,
                        is_static=is_static,
                        is_class_method=is_class_method,
                    )
                    
                    # NEW: Detect shared state dependencies
                    # component_obj = components[method_id]
                    # component_obj.metadata['shared_state_dependencies'] = [
                    #     var for var in module_vars if var in component_obj.source_code
                    # ]
                    
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
                                start_line = expr_child.start_point[0] + 1
                                end_line = expr_child.end_point[0] + 1
                                
                                components[var_id] = CodeComponent(
                                    id=var_id,
                                    name=var_name,
                                    type=ComponentType.GLOBAL_VARIABLE,
                                    location=Location(
                                        file_path=file_path,
                                        start_line=start_line,
                                        end_line=end_line
                                    ),
                                    source_code=source[expr_child.start_byte:expr_child.end_byte],
                                    signature=f"{var_name} = ...",
                                    existing_docstring=None,
                                    parameters=[],
                                    decorators=[],
                                    imports=file_imports,
                                    language="python",
                                    lines_of_code=1,
                                )

                                # NEW: Detect shared state dependencies
                                # component_obj = components[var_id]
                                # component_obj.metadata['shared_state_dependencies'] = [
                                #     var for var in module_vars if var in component_obj.source_code
                                # ]
            
            # Top-level assignments (direct children of module)
            elif child.type == "assignment":
                lhs = child.child_by_field_name("left")
                if lhs and lhs.type == "identifier":
                    var_name = lhs.text.decode()
                    var_id = f"{module_path}.{var_name}"
                    
                    # Don't duplicate if already extracted
                    if var_id not in components:
                        start_line = child.start_point[0] + 1
                        end_line = child.end_point[0] + 1
                        
                        components[var_id] = CodeComponent(
                            id=var_id,
                            name=var_name,
                            type=ComponentType.GLOBAL_VARIABLE,
                            location=Location(
                                file_path=file_path,
                                start_line=start_line,
                                end_line=end_line
                            ),
                            source_code=source[child.start_byte:child.end_byte],
                            signature=f"{var_name} = ...",
                            existing_docstring=None,
                            parameters=[],
                            decorators=[],
                            imports=file_imports,
                            language="python",
                            lines_of_code=1,
                        )

                         # NEW: Detect shared state dependencies
                        # component_obj = components[var_id]
                        # component_obj.metadata['shared_state_dependencies'] = [
                        #     var for var in module_vars if var in component_obj.source_code
                        # ]

    # First extract classes, functions, and methods
    walk(root, "module")
    
    # Then extract global variables
    extract_globals()
    
    # Extract module_path from component ID
    # ID format: module.path.ClassName or module.path.function_name
    # For functions: module_path = everything before the last dot
    # For classes: module_path = everything before the last dot
    # For methods: module_path = everything before the last two dots
    for comp_id, component in components.items():
        parts = component.id.split(".")
        if component.type.value == "method":
            # For methods: module_path is everything except class name and method name
            module_path = ".".join(parts[:-2]) if len(parts) > 2 else parts[0]
        else:
            # For functions, classes, globals: module_path is everything except the component name
            module_path = ".".join(parts[:-1]) if len(parts) > 1 else parts[0]
        # Update the component's module_path
        component.module_path = module_path

    return components
