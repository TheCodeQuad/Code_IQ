from typing import List
from backend.models.code_component import CodeComponent, Location, Parameter, ComponentType


def get_tsdoc(node, source):
    """Extract TSDoc/JSDoc comment from a function, class, or method declaration."""
    prev_sibling = node.prev_sibling
    
    while prev_sibling and prev_sibling.type == "comment":
        comment_text = prev_sibling.text.decode()
        if comment_text.startswith("/**") and comment_text.endswith("*/"):
            tsdoc_text = comment_text[3:-2].strip()
            lines = tsdoc_text.split('\n')
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
    """Extract parameters from a function/method declaration node. Handles TypeScript-specific features."""
    parameters = []
    params = node.child_by_field_name("parameters")
    
    if params:
        for child in params.children:
            if child.type == "identifier":
                parameters.append(Parameter(name=child.text.decode()))
            elif child.type == "required_parameter":
                for param_child in child.children:
                    if param_child.type == "identifier":
                        parameters.append(Parameter(name=param_child.text.decode()))
                        break
            elif child.type == "optional_parameter":
                for param_child in child.children:
                    if param_child.type == "identifier":
                        parameters.append(Parameter(name=f"{param_child.text.decode()}?"))
                        break
            elif child.type == "assignment_pattern":
                left = child.child_by_field_name("left")
                if left:
                    if left.type == "identifier":
                        parameters.append(Parameter(name=left.text.decode()))
                    elif left.type == "required_parameter":
                        for param_child in left.children:
                            if param_child.type == "identifier":
                                parameters.append(Parameter(name=param_child.text.decode()))
                                break
            elif child.type == "rest_pattern":
                for param_child in child.children:
                    if param_child.type == "identifier":
                        parameters.append(Parameter(name=f"...{param_child.text.decode()}"))
                        break
            elif child.type == "object_pattern" or child.type == "array_pattern":
                parameters.append(Parameter(name=child.text.decode()))
    
    return parameters


def extract_signature(node, source):
    """Extract function signature from node"""
    sig_start = node.start_byte
    sig_end = node.end_byte
    source_text = source[sig_start:sig_end]
    
    brace_pos = source_text.find('{')
    if brace_pos != -1:
        return source_text[:brace_pos].strip()
    return source_text.split('\n')[0]


def extract_imports_and_decorators(tree, source, module_path):
    """Extract all imports and decorators from the file"""
    imports = []
    decorators = []
    root = tree.root_node
    
    def walk(node):
        if node.type == "import_statement":
            for child in node.children:
                if child.type in ("dotted_name", "aliased_import"):
                    imports.append(child.text.decode())
        elif node.type == "import_from_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    imports.append(child.text.decode())
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
        if child.type == "variable_declaration":
            for declarator in child.children:
                if declarator.type == "variable_declarator":
                    name_node = declarator.child_by_field_name("name")
                    if name_node and name_node.type == "identifier":
                        vars.append(name_node.text.decode())
        elif child.type == "lexical_declaration":
            for declarator in child.children:
                if declarator.type == "variable_declarator":
                    name_node = declarator.child_by_field_name("name")
                    if name_node and name_node.type == "identifier":
                        vars.append(name_node.text.decode())
    return vars

def extract_components(tree, source, file_path, module_path):
    """
    Extract all code components (classes, functions, methods, interfaces, types) from a parsed TypeScript tree.
    """
    components = {}
    root = tree.root_node
    
    # FIX: Extract module-level variables
    module_vars = _extract_module_level_vars(root)
    
    file_imports, file_decorators = extract_imports_and_decorators(tree, source, module_path)


    def walk(node, parent_id=None):

        # -------- TOP-LEVEL FUNCTIONS --------
        if node.type == "function_declaration" and not parent_id:
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
                func_id = f"{module_path}.{name}"
                
                has_tsdoc, tsdoc = get_tsdoc(node, source)
                parameters = extract_parameters(node)
                
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                lines_of_code = end_line - start_line + 1
                
                signature = extract_signature(node, source)
                func_calls = extract_function_calls(node, source)

                components[func_id] = CodeComponent(
                    id=func_id,
                    name=name,
                    type=ComponentType.FUNCTION,
                    location=Location(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line
                    ),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=signature,
                    existing_docstring=tsdoc if has_tsdoc else None,
                    parameters=parameters,
                    decorators=file_decorators,
                    calls=func_calls,
                    imports=file_imports,
                    language="typescript",
                    lines_of_code=lines_of_code,
                )

                # Detect shared state dependencies
                components[func_id].metadata['shared_state_dependencies'] = [
                    var for var in module_vars if var in source[node.start_byte:node.end_byte]
                ]

        # -------- CLASSES --------
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                class_name = name_node.text.decode()
                
                if parent_id:
                    class_id = f"{parent_id}.{class_name}"
                else:
                    class_id = f"{module_path}.{class_name}"

                has_tsdoc, tsdoc = get_tsdoc(node, source)
                
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                lines_of_code = end_line - start_line + 1
                
                signature = extract_signature(node, source)

                components[class_id] = CodeComponent(
                    id=class_id,
                    name=class_name,
                    type=ComponentType.CLASS,
                    location=Location(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line
                    ),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=signature,
                    existing_docstring=tsdoc if has_tsdoc else None,
                    parameters=[],
                    decorators=file_decorators,
                    imports=file_imports,
                    language="typescript",
                    lines_of_code=lines_of_code,
                )

                # Extract methods and properties within the class
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        if child.type == "method_definition":
                            key = child.child_by_field_name("name")
                            if key:
                                method_name = key.text.decode()
                                method_id = f"{class_id}.{method_name}"
                                
                                method_has_tsdoc, method_tsdoc = get_tsdoc(child, source)
                                method_parameters = extract_parameters(child)
                                
                                method_start_line = child.start_point[0] + 1
                                method_end_line = child.end_point[0] + 1
                                method_lines_of_code = method_end_line - method_start_line + 1
                                
                                method_signature = extract_signature(child, source)
                                method_calls = extract_function_calls(child, source)

                                components[method_id] = CodeComponent(
                                    id=method_id,
                                    name=method_name,
                                    type=ComponentType.METHOD,
                                    location=Location(
                                        file_path=file_path,
                                        start_line=method_start_line,
                                        end_line=method_end_line
                                    ),
                                    source_code=source[child.start_byte:child.end_byte],
                                    signature=method_signature,
                                    existing_docstring=method_tsdoc if method_has_tsdoc else None,
                                    parameters=method_parameters,
                                    decorators=file_decorators,
                                    calls=method_calls,
                                    imports=file_imports,
                                    language="typescript",
                                    lines_of_code=method_lines_of_code,
                                )
                        
                        # Handle property signatures and field definitions
                        elif child.type in ("public_field_definition", "property_signature"):
                            prop = child.child_by_field_name("name")
                            if prop and prop.type == "property_identifier":
                                prop_name = prop.text.decode()
                                field_id = f"{class_id}.{prop_name}"
                                
                                components[field_id] = CodeComponent(
                                    id=field_id,
                                    name=prop_name,
                                    type=ComponentType.FIELD,
                                    location=Location(
                                        file_path=file_path,
                                        start_line=child.start_point[0] + 1,
                                        end_line=child.end_point[0] + 1
                                    ),
                                    source_code=source[child.start_byte:child.end_byte],
                                    signature=f"{prop_name}: property",
                                    existing_docstring=None,
                                    parameters=[],
                                    decorators=file_decorators,
                                    imports=file_imports,
                                    language="typescript",
                                    lines_of_code=1,
                                )

        # -------- INTERFACE DECLARATION --------
        elif node.type == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                interface_name = name_node.text.decode()
                interface_id = f"{module_path}.{interface_name}"
                
                has_tsdoc, tsdoc = get_tsdoc(node, source)
                
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                lines_of_code = end_line - start_line + 1

                components[interface_id] = CodeComponent(
                    id=interface_id,
                    name=interface_name,
                    type=ComponentType.FUNCTION,  # Using FUNCTION as a placeholder, could create INTERFACE type
                    location=Location(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line
                    ),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=f"interface {interface_name}",
                    existing_docstring=tsdoc if has_tsdoc else None,
                    parameters=[],
                    decorators=file_decorators,
                    imports=file_imports,
                    language="typescript",
                    lines_of_code=lines_of_code,
                )

        # -------- TYPE ALIAS DECLARATION --------
        elif node.type == "type_alias_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                type_name = name_node.text.decode()
                type_id = f"{module_path}.{type_name}"
                
                has_tsdoc, tsdoc = get_tsdoc(node, source)
                
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                lines_of_code = end_line - start_line + 1

                components[type_id] = CodeComponent(
                    id=type_id,
                    name=type_name,
                    type=ComponentType.FUNCTION,  # Using FUNCTION as a placeholder, could create TYPE type
                    location=Location(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line
                    ),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=f"type {type_name}",
                    existing_docstring=tsdoc if has_tsdoc else None,
                    parameters=[],
                    decorators=file_decorators,
                    imports=file_imports,
                    language="typescript",
                    lines_of_code=lines_of_code,
                )

        # -------- ENUM DECLARATION --------
        elif node.type == "enum_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                enum_name = name_node.text.decode()
                enum_id = f"{module_path}.{enum_name}"
                
                has_tsdoc, tsdoc = get_tsdoc(node, source)
                
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                lines_of_code = end_line - start_line + 1

                components[enum_id] = CodeComponent(
                    id=enum_id,
                    name=enum_name,
                    type=ComponentType.FUNCTION,  # Using FUNCTION as a placeholder, could create ENUM type
                    location=Location(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line
                    ),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=f"enum {enum_name}",
                    existing_docstring=tsdoc if has_tsdoc else None,
                    parameters=[],
                    decorators=file_decorators,
                    imports=file_imports,
                    language="typescript",
                    lines_of_code=lines_of_code,
                )

        for c in node.children:
            walk(c, parent_id)

    # -------- EXTRACT MODULE-LEVEL VARIABLES (GLOBALS) --------
    def extract_globals():
        """Extract module-level variable declarations and arrow functions."""
        for child in root.children:
            if child.type == "variable_declaration":
                for declarator_child in child.children:
                    if declarator_child.type == "variable_declarator":
                        name_node = declarator_child.child_by_field_name("name")
                        if name_node and name_node.type == "identifier":
                            var_name = name_node.text.decode()
                            var_id = f"{module_path}.{var_name}"
                            
                            if var_id not in components:
                                kind = "variable"
                                for kind_node in child.children:
                                    if kind_node.type in ("const", "let", "var"):
                                        kind = kind_node.type
                                        break
                                
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
                                    language="typescript",
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
                            
                            if func_id not in components:
                                parameters = extract_parameters(value_node)
                                
                                start_line = child.start_point[0] + 1
                                end_line = child.end_point[0] + 1
                                lines_of_code = end_line - start_line + 1
                                
                                signature = extract_signature(value_node, source)
                                func_calls = extract_function_calls(value_node, source)
                                
                                components[func_id] = CodeComponent(
                                    id=func_id,
                                    name=func_name,
                                    type=ComponentType.FUNCTION,
                                    location=Location(
                                        file_path=file_path,
                                        start_line=start_line,
                                        end_line=end_line
                                    ),
                                    source_code=source[child.start_byte:child.end_byte],
                                    signature=signature,
                                    existing_docstring=None,
                                    parameters=parameters,
                                    decorators=[],
                                    calls=func_calls,
                                    imports=file_imports,
                                    language="typescript",
                                    lines_of_code=lines_of_code,
                                )

                                # Detect shared state dependencies
                                components[func_id].metadata['shared_state_dependencies'] = [
                                    var for var in module_vars if var in source[node.start_byte:node.end_byte]
                                ]

    # First extract classes, functions, interfaces, types, and enums
    walk(root, None)
    
    # Then extract global variables
    extract_globals()
    
    return components