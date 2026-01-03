from backend.models.code_component import CodeComponent, Location, Parameter


def get_jsdoc(node, source):
    """
    Extract JSDoc comment from a function or class declaration.
    
    Args:
        node: tree-sitter node (function_declaration, class_declaration, method_definition)
        source: full source code string
        
    Returns:
        tuple: (has_jsdoc: bool, jsdoc: str)
    """
    # Look for a comment node immediately before this node
    prev_sibling = node.prev_sibling
    
    # Skip whitespace and look for comment
    while prev_sibling and prev_sibling.type == "comment":
        comment_text = prev_sibling.text.decode()
        # Check if it's a JSDoc comment (starts with /**)
        if comment_text.startswith("/**") and comment_text.endswith("*/"):
            # Remove /** and */ and clean up
            jsdoc_text = comment_text[3:-2].strip()
            # Remove leading * from each line
            lines = jsdoc_text.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line.startswith('*'):
                    line = line[1:].strip()
                cleaned_lines.append(line)
            return True, '\n'.join(cleaned_lines)
        prev_sibling = prev_sibling.prev_sibling
    
    return False, ""


def extract_parameters(node):
    """
    Extract parameters from a function/method declaration node.
    
    Args:
        node: tree-sitter function/method declaration node
        
    Returns:
        list: List of parameter names
    """
    parameters = []
    params = node.child_by_field_name("parameters")
    
    if params:
        for child in params.children:
            if child.type == "identifier":
                parameters.append(child.text.decode())
            elif child.type == "assignment_pattern":
                # Handle default parameters like (x = 5)
                left = child.child_by_field_name("left")
                if left and left.type == "identifier":
                    parameters.append(left.text.decode())
            elif child.type == "rest_pattern":
                # Handle rest parameters like (...args)
                for param_child in child.children:
                    if param_child.type == "identifier":
                        parameters.append(f"...{param_child.text.decode()}")
                        break
            elif child.type == "object_pattern" or child.type == "array_pattern":
                # Handle destructured parameters like ({a, b}) or ([x, y])
                parameters.append(child.text.decode())
    
    return parameters


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


def extract_components(tree, source, file_path, module_path):
    """
    Extract all code components (classes, functions, methods, variables) from a parsed JavaScript tree.
    
    This includes:
    - Functions (regular and arrow functions)
    - Classes
    - Methods
    - Module-level variables/constants
    
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

    def walk(node, parent_id=None):

        # -------------------------------
        # FUNCTION DECLARATION
        # -------------------------------
        if node.type == "function_declaration" and not parent_id:
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
                func_id = f"{module_path}.{name}"
                
                # Extract JSDoc
                has_jsdoc, jsdoc = get_jsdoc(node, source)
                
                # Extract parameters
                parameters = extract_parameters(node)
                
                # Calculate lines of code
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                lines_of_code = end_line - start_line + 1

                # Extract imports and decorators
                func_imports, func_decorators = extract_imports_and_decorators(tree, source, module_path)
                
                # Extract function calls
                func_calls = extract_function_calls(node, source)

                components[func_id] = CodeComponent(
                    id=func_id,
                    language="javascript",
                    type="function",
                    file_path=file_path,
                    module_path=module_path,
                    start_line=start_line,
                    end_line=end_line,
                    source_code=source[node.start_byte:node.end_byte],
                    has_docstring=has_jsdoc,
                    docstring=jsdoc,
                    imports=func_imports,
                    decorators=func_decorators,
                    calls=func_calls,  # This requires additional processing
                    parameters=parameters,
                    lines_of_code=lines_of_code,
                )

        # -------------------------------
        # CLASS DECLARATION
        # -------------------------------
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                class_name = name_node.text.decode()
                
                # Build class ID based on parent
                if parent_id:
                    class_id = f"{parent_id}.{class_name}"
                else:
                    class_id = f"{module_path}.{class_name}"

                # Extract JSDoc
                has_jsdoc, jsdoc = get_jsdoc(node, source)
                
                # Calculate lines of code
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                lines_of_code = end_line - start_line + 1

                components[class_id] = CodeComponent(
                    id=class_id,
                    language="javascript",
                    type="class",
                    file_path=file_path,
                    module_path=module_path,
                    start_line=start_line,
                    end_line=end_line,
                    source_code=source[node.start_byte:node.end_byte],
                    has_docstring=has_jsdoc,
                    docstring=jsdoc,
                    parameters=[],
                    lines_of_code=lines_of_code,
                )

                # Extract methods within the class
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        if child.type == "method_definition":
                            key = child.child_by_field_name("name")
                            if key:
                                method_name = key.text.decode()
                                method_id = f"{class_id}.{method_name}"
                                
                                # Extract JSDoc
                                method_has_jsdoc, method_jsdoc = get_jsdoc(child, source)
                                
                                # Extract parameters
                                method_parameters = extract_parameters(child)
                                
                                # Calculate lines of code
                                method_start_line = child.start_point[0] + 1
                                method_end_line = child.end_point[0] + 1
                                method_lines_of_code = method_end_line - method_start_line + 1

                                components[method_id] = CodeComponent(
                                    id=method_id,
                                    language="javascript",
                                    type="method",
                                    file_path=file_path,
                                    module_path=module_path,
                                    start_line=method_start_line,
                                    end_line=method_end_line,
                                    source_code=source[child.start_byte:child.end_byte],
                                    has_docstring=method_has_jsdoc,
                                    docstring=method_jsdoc,
                                    parameters=method_parameters,
                                    lines_of_code=method_lines_of_code,
                                )
                        
                        # Handle field definitions (class properties)
                        elif child.type == "field_definition":
                            prop = child.child_by_field_name("property")
                            if prop and prop.type == "property_identifier":
                                prop_name = prop.text.decode()
                                field_id = f"{class_id}.{prop_name}"
                                
                                components[field_id] = CodeComponent(
                                    id=field_id,
                                    language="javascript",
                                    type="field",
                                    file_path=file_path,
                                    module_path=module_path,
                                    start_line=child.start_point[0] + 1,
                                    end_line=child.end_point[0] + 1,
                                    source_code=source[child.start_byte:child.end_byte],
                                    has_docstring=False,
                                    docstring="",
                                    parameters=[],
                                    lines_of_code=1,
                                )

        # Continue walking
        for child in node.children:
            walk(child, parent_id)

    # Extract module-level variables (const, let, var declarations)
    def extract_globals():
        """
        Extract module-level variable declarations.
        These include constants, configurations, exports, etc.
        """
        for child in root.children:
            if child.type == "variable_declaration":
                # Extract all declarators in this statement
                for declarator_child in child.children:
                    if declarator_child.type == "variable_declarator":
                        name_node = declarator_child.child_by_field_name("name")
                        if name_node and name_node.type == "identifier":
                            var_name = name_node.text.decode()
                            var_id = f"{module_path}.{var_name}"
                            
                            # Don't duplicate if already extracted
                            if var_id not in components:
                                # Determine if it's const, let, or var
                                kind = "variable"
                                for kind_node in child.children:
                                    if kind_node.type in ("const", "let", "var"):
                                        kind = kind_node.type
                                        break
                                
                                components[var_id] = CodeComponent(
                                    id=var_id,
                                    language="javascript",
                                    type=f"{kind}_declaration",
                                    file_path=file_path,
                                    module_path=module_path,
                                    start_line=child.start_point[0] + 1,
                                    end_line=child.end_point[0] + 1,
                                    source_code=source[child.start_byte:child.end_byte],
                                    has_docstring=False,
                                    docstring="",
                                    parameters=[],
                                    lines_of_code=1,
                                )
            
            # Handle arrow functions assigned to variables
            elif child.type == "lexical_declaration":
                for declarator_child in child.children:
                    if declarator_child.type == "variable_declarator":
                        name_node = declarator_child.child_by_field_name("name")
                        value_node = declarator_child.child_by_field_name("value")
                        
                        if (name_node and name_node.type == "identifier" and 
                            value_node and value_node.type == "arrow_function"):
                            
                            func_name = name_node.text.decode()
                            func_id = f"{module_path}.{func_name}"
                            
                            # Don't duplicate
                            if func_id not in components:
                                # Extract parameters from arrow function
                                parameters = extract_parameters(value_node)
                                
                                start_line = child.start_point[0] + 1
                                end_line = child.end_point[0] + 1
                                lines_of_code = end_line - start_line + 1
                                
                                components[func_id] = CodeComponent(
                                    id=func_id,
                                    language="javascript",
                                    type="arrow_function",
                                    file_path=file_path,
                                    module_path=module_path,
                                    start_line=start_line,
                                    end_line=end_line,
                                    source_code=source[child.start_byte:child.end_byte],
                                    has_docstring=False,
                                    docstring="",
                                    parameters=parameters,
                                    lines_of_code=lines_of_code,
                                )

    # First extract classes and functions
    walk(root, None)
    
    # Then extract global variables
    extract_globals()
    
    return components