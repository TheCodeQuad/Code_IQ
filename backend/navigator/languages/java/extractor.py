from typing import List
from backend.models.code_component import CodeComponent, Location, Parameter, ComponentType


def get_javadoc(node, source):
    """
    Extract Javadoc comment from a class or method declaration.
    """
    prev_sibling = node.prev_sibling
    
    while prev_sibling and prev_sibling.type in ("line_comment", "comment"):
        if prev_sibling.type == "comment":
            comment_text = prev_sibling.text.decode()
            if comment_text.startswith("/**") and comment_text.endswith("*/"):
                javadoc_text = comment_text[3:-2].strip()
                lines = javadoc_text.split('\n')
                cleaned_lines = []
                for line in lines:
                    line = line.strip()
                    if line.startswith('*'):
                        line = line[1:].strip()
                    cleaned_lines.append(line)
                return True, '\n'.join(cleaned_lines)
        prev_sibling = prev_sibling.prev_sibling
    
    return False, ""


def extract_parameters(method_node):
    """Extract parameters from a method declaration node."""
    parameters = []
    params = method_node.child_by_field_name("parameters")
    
    if params:
        for child in params.children:
            if child.type == "formal_parameter":
                for param_child in child.children:
                    if param_child.type == "identifier":
                        param_name = param_child.text.decode()
                        parameters.append(Parameter(name=param_name))
                        break
            elif child.type == "spread_parameter":
                for param_child in child.children:
                    if param_child.type == "identifier":
                        param_name = param_child.text.decode()
                        parameters.append(Parameter(name=param_name))
                        break
    
    return parameters


def extract_signature(method_node, source):
    """Extract method signature from node"""
    sig_start = method_node.start_byte
    sig_end = method_node.end_byte
    source_text = source[sig_start:sig_end]
    
    # Find the opening brace
    brace_pos = source_text.find('{')
    if brace_pos != -1:
        return source_text[:brace_pos].strip()
    return source_text.split('\n')[0]


def get_visibility(node):
    """Extracts visibility from a node's modifiers."""
    is_public = is_private = is_protected = False
    for child in node.children:
        if child.type == "modifiers":
            mods = child.text.decode()
            if "public" in mods:
                is_public = True
            elif "private" in mods:
                is_private = True
            elif "protected" in mods:
                is_protected = True
    if not (is_public or is_private or is_protected):
        is_public = True
    return is_public, is_private, is_protected


def extract_imports(tree, source):
    """Extract all imports from the file"""
    imports = []
    root = tree.root_node
    
    def walk(node):
        if node.type == "import_declaration":
            imports.append(node.text.decode())
        for child in node.children:
            walk(child)
    
    walk(root)
    return imports


def extract_annotations(node):
    """Extract annotations/decorators from a node"""
    annotations = []
    for child in node.children:
        if child.type == "modifiers":
            for mod_child in child.children:
                if mod_child.type == "annotation":
                    annotations.append(mod_child.text.decode())
    return annotations


def extract_function_calls(func_node, source):
    """Extract all function/method calls within a method"""
    calls = []
    
    def walk(node):
        if node.type == "method_invocation":
            # Get the method name part
            obj_node = node.child_by_field_name("object")
            method_node = node.child_by_field_name("name")
            if method_node:
                call_text = method_node.text.decode()
                calls.append(call_text)
        
        for child in node.children:
            walk(child)
    
    walk(func_node)
    return calls

def _extract_class_level_vars(class_node) -> List[str]:
    """Extract class-level (shared) variable names"""
    vars = []
    body = class_node.child_by_field_name("body")
    if body:
        for child in body.children:
            if child.type == "field_declaration":
                for var_child in child.children:
                    if var_child.type == "variable_declarator":
                        name_node = var_child.child_by_field_name("name")
                        if name_node:
                            vars.append(name_node.text.decode())
    return vars

def extract_components(tree, source, file_path, module_path):
    """
    Extract all code components (classes, methods, fields) from a parsed Java tree.
    """
    components = {}
    root = tree.root_node
    
    # Extract file-level imports and annotations once
    file_imports = extract_imports(tree, source)

    def walk(node, parent_id=None):
        
        # -------- CLASS DECLARATION --------
        if node.type == "class_declaration":
            cname = node.child_by_field_name("name").text.decode()
            
            if parent_id:
                class_id = f"{parent_id}.{cname}"
            else:
                class_id = f"{module_path}.{cname}"

            has_javadoc, javadoc = get_javadoc(node, source)
            annotations = extract_annotations(node)
            
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            lines_of_code = end_line - start_line + 1
            
            sig = extract_signature(node, source)
            is_public, is_private, is_protected = get_visibility(node)

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
                signature=sig,
                existing_docstring=javadoc if has_javadoc else None,
                parameters=[],
                decorators=annotations,
                imports=file_imports,
                language="java",
                lines_of_code=lines_of_code,
                is_public=is_public,
                is_private=is_private,
                is_protected=is_protected,
            )

            # FIX: Extract class-level shared state
            class_vars = _extract_class_level_vars(node)
            for method_id in components:
                if method_id.startswith(class_id):
                    components[method_id].metadata['shared_state_dependencies'] = [
                        var for var in class_vars if var in components[method_id].source_code
                    ]
                    
            # Extract methods and nested classes within the class body
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    walk(child, class_id)

        # -------- METHOD DECLARATION --------
        elif node.type == "method_declaration" and parent_id:
            mname = node.child_by_field_name("name").text.decode()
            method_id = f"{parent_id}.{mname}"

            has_javadoc, javadoc = get_javadoc(node, source)
            parameters = extract_parameters(node)
            annotations = extract_annotations(node)
            method_calls = extract_function_calls(node, source)
            sig = extract_signature(node, source)
            is_public, is_private, is_protected = get_visibility(node)
            
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            lines_of_code = end_line - start_line + 1

            components[method_id] = CodeComponent(
                id=method_id,
                name=mname,
                type=ComponentType.METHOD,
                location=Location(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line
                ),
                source_code=source[node.start_byte:node.end_byte],
                signature=sig,
                existing_docstring=javadoc if has_javadoc else None,
                parameters=parameters,
                imports=file_imports,
                decorators=annotations,
                calls=method_calls,
                language="java",
                lines_of_code=lines_of_code,
                is_public=is_public,
                is_private=is_private,
                is_protected=is_protected,
            )

        # -------- FIELD DECLARATION --------
        elif node.type == "field_declaration" and parent_id:
            for child in node.children:
                if child.type == "variable_declarator":
                    var_name_node = child.child_by_field_name("name")
                    if var_name_node:
                        var_name = var_name_node.text.decode()
                        field_id = f"{parent_id}.{var_name}"
                        
                        is_static = False
                        for mod_child in node.children:
                            if mod_child.type == "modifiers":
                                mods = mod_child.text.decode()
                                if "static" in mods:
                                    is_static = True
                                    break

                        is_public, is_private, is_protected = get_visibility(node)
                        annotations = extract_annotations(node)

                        field_type = ComponentType.STATIC_FIELD if is_static else ComponentType.FIELD

                        components[field_id] = CodeComponent(
                            id=field_id,
                            name=var_name,
                            type=field_type,
                            location=Location(
                                file_path=file_path,
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1
                            ),
                            source_code=source[node.start_byte:node.end_byte],
                            signature=f"{var_name}: field",
                            existing_docstring=None,
                            parameters=[],
                            decorators=annotations,
                            imports=file_imports,
                            language="java",
                            lines_of_code=1,
                            is_public=is_public,
                            is_private=is_private,
                            is_protected=is_protected,
                            is_static=is_static,
                        )

        # -------- CONSTRUCTOR DECLARATION --------
        elif node.type == "constructor_declaration" and parent_id:
            parameters = extract_parameters(node)
            has_javadoc, javadoc = get_javadoc(node, source)
            annotations = extract_annotations(node)
            method_calls = extract_function_calls(node, source)
            
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            lines_of_code = end_line - start_line + 1
            
            sig = extract_signature(node, source)
            is_public, is_private, is_protected = get_visibility(node)
            
            # Use special naming for constructor
            constructor_id = f"{parent_id}.<init>"

            components[constructor_id] = CodeComponent(
                id=constructor_id,
                name="<init>",
                type=ComponentType.CONSTRUCTOR,
                location=Location(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line
                ),
                source_code=source[node.start_byte:node.end_byte],
                signature=sig,
                existing_docstring=javadoc if has_javadoc else None,
                parameters=parameters,
                decorators=annotations,
                imports=file_imports,
                calls=method_calls,
                language="java",
                lines_of_code=lines_of_code,
                is_public=is_public,
                is_private=is_private,
                is_protected=is_protected,
            )

        # Continue walking for nested structures
        for child in node.children:
            walk(child, parent_id)

    # Start walking from root
    for child in root.children:
        walk(child, None)
    
    return components