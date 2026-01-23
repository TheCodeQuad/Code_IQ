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
    """
    Extract parameters with FULL metadata including type hints and defaults
    Handles TypeScript-specific features like optional parameters, unions, generics
    """
    parameters = []
    params = node.child_by_field_name("parameters")
    
    if params:
        for child in params.children:
            if child.type == "identifier":
                param_name = child.text.decode()
                parameters.append(Parameter(
                    name=param_name,
                    type_hint=None,
                    default_value=None,
                    is_required=True
                ))
                
            elif child.type == "required_parameter":
                # TypeScript: name: Type
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                
                if name_node:
                    param_name = name_node.text.decode()
                    param_type = type_node.text.decode() if type_node else None
                    
                    parameters.append(Parameter(
                        name=param_name,
                        type_hint=param_type,
                        default_value=None,
                        is_required=True
                    ))
                    
            elif child.type == "optional_parameter":
                # TypeScript: name?: Type
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                
                if name_node:
                    param_name = name_node.text.decode()
                    param_type = type_node.text.decode() if type_node else None
                    
                    parameters.append(Parameter(
                        name=param_name,
                        type_hint=param_type,
                        default_value=None,
                        is_required=False
                    ))
                    
            elif child.type == "assignment_pattern":
                # name: Type = defaultValue
                left = child.child_by_field_name("left")
                right = child.child_by_field_name("right")
                
                if left:
                    param_name = left.text.decode()
                    param_type = None
                    
                    # Extract type if available
                    for left_child in left.children:
                        if left_child.type == "type_annotation":
                            param_type = left_child.text.decode()
                    
                    param_default = right.text.decode() if right else None
                    
                    parameters.append(Parameter(
                        name=param_name,
                        type_hint=param_type,
                        default_value=param_default,
                        is_required=False
                    ))
                    
            elif child.type == "rest_pattern":
                # ...rest: Type[]
                for param_child in child.children:
                    if param_child.type == "identifier":
                        param_name = f"...{param_child.text.decode()}"
                        parameters.append(Parameter(
                            name=param_name,
                            type_hint=None,
                            is_required=True
                        ))
                        break
                        
            elif child.type == "object_pattern" or child.type == "array_pattern":
                parameters.append(Parameter(
                    name=child.text.decode(),
                    type_hint="object" if child.type == "object_pattern" else "array",
                    is_required=True
                ))
    
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
                if child.type == "string":
                    import_path = child.text.decode().strip('\'"')
                    imports.append(import_path)
        
        elif node.type == "import_from_statement":
            for child in node.children:
                if child.type == "string":
                    import_path = child.text.decode().strip('\'"')
                    imports.append(import_path)
        
        elif node.type == "decorator":
            decorators.append(node.text.decode())
        
        for child in node.children:
            walk(child)
    
    walk(root)
    return imports, decorators


def extract_component_decorators(node, parent=None):
    """Extract ALL decorators for TypeScript components"""
    decorators = []
    
    if not node or not parent:
        return decorators
    
    node_index = None
    for i, child in enumerate(parent.children):
        if child == node:
            node_index = i
            break
    
    if node_index is None:
        return decorators
    
    i = node_index - 1
    while i >= 0:
        child = parent.children[i]
        
        if child.type == "decorator":
            dec_text = child.text.decode().strip()
            if dec_text.startswith('@'):
                dec_text = dec_text[1:]
            decorators.insert(0, dec_text)
            i -= 1
        elif child.type in ("comment", "newline", "line_break"):
            i -= 1
        else:
            break
    
    return decorators


def extract_function_calls(func_node, source):
    """Extract all function/method calls within a function"""
    calls = []
    
    def walk(node):
        if node.type == "call_expression":
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
            for decl_child in child.children:
                if decl_child.type == "variable_declarator":
                    name_node = decl_child.child_by_field_name("name")
                    if name_node and name_node.type == "identifier":
                        vars.append(name_node.text.decode())
    
    return vars


def extract_components(tree, source, file_path, module_path):
    """Extract all TypeScript components"""
    components = {}
    root = tree.root_node
    
    module_vars = _extract_module_level_vars(root)
    file_imports, _ = extract_imports_and_decorators(tree, source, module_path)
    
    def walk(node, parent_type=None, parent=None):
        
        # FUNCTIONS
        if node.type == "function_declaration" and parent_type == "program":
            func_name = node.child_by_field_name("name")
            if not func_name:
                return
            
            name = func_name.text.decode()
            cid = f"{module_path}.{name}"
            
            has_tsdoc, tsdoc = get_tsdoc(node, source)
            parameters = extract_parameters(node)
            signature = extract_signature(node, source)
            
            # Extract return type
            return_type_node = node.child_by_field_name("return_type")
            return_type = return_type_node.text.decode() if return_type_node else None
            
            decorators = extract_component_decorators(node, parent) if parent else []
            calls = extract_function_calls(node, source)
            
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            
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
                parameters=parameters,
                return_type=return_type,
                existing_docstring=tsdoc if has_tsdoc else None,
                decorators=decorators,
                calls=calls,
                imports=file_imports,
                language="typescript",
                lines_of_code=end_line - start_line + 1,
                is_async='async' in node.text.decode(),
            )
        
        # ARROW FUNCTIONS (const f = () => {})
        elif node.type == "variable_declaration" and parent_type == "program":
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    value_node = child.child_by_field_name("value")
                    
                    if name_node and value_node and value_node.type == "arrow_function":
                        var_name = name_node.text.decode()
                        cid = f"{module_path}.{var_name}"
                        
                        has_tsdoc, tsdoc = get_tsdoc(node, source)
                        parameters = extract_parameters(value_node)
                        signature = extract_signature(value_node, source)
                        calls = extract_function_calls(value_node, source)
                        
                        start_line = node.start_point[0] + 1
                        end_line = node.end_point[0] + 1
                        
                        components[cid] = CodeComponent(
                            id=cid,
                            name=var_name,
                            type=ComponentType.FUNCTION,
                            location=Location(
                                file_path=file_path,
                                start_line=start_line,
                                end_line=end_line
                            ),
                            source_code=source[node.start_byte:node.end_byte],
                            signature=signature,
                            parameters=parameters,
                            existing_docstring=tsdoc if has_tsdoc else None,
                            calls=calls,
                            imports=file_imports,
                            language="typescript",
                            lines_of_code=end_line - start_line + 1,
                            is_async='async' in source[node.start_byte:node.end_byte],
                        )
        
        # CLASSES
        elif node.type == "class_declaration":
            class_name = node.child_by_field_name("name")
            if not class_name:
                return
            
            name = class_name.text.decode()
            cid = f"{module_path}.{name}"
            
            has_tsdoc, tsdoc = get_tsdoc(node, source)
            decorators = extract_component_decorators(node, parent) if parent else []
            
            parent_classes = []
            parent_class_node = node.child_by_field_name("superclass")
            if parent_class_node:
                parent_classes = [parent_class_node.text.decode()]
            
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            
            components[cid] = CodeComponent(
                id=cid,
                name=name,
                type=ComponentType.CLASS,
                location=Location(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line
                ),
                source_code=source[node.start_byte:node.end_byte],
                signature=f"class {name}",
                parent_classes=parent_classes,
                existing_docstring=tsdoc if has_tsdoc else None,
                decorators=decorators,
                imports=file_imports,
                language="typescript",
                lines_of_code=end_line - start_line + 1,
            )
            
            walk(node, "class", node)
            return
        
        # METHODS & CLASS PROPERTIES
        elif node.type == "method_definition" and parent_type == "class":
            key = node.child_by_field_name("key")
            if not key:
                return
            
            method_name = key.text.decode()
            parent_class_node = parent
            if parent_class_node:
                parent_name = parent_class_node.child_by_field_name("name")
                if parent_name:
                    parent_class_name = parent_name.text.decode()
                    cid = f"{module_path}.{parent_class_name}.{method_name}"
                    
                    has_tsdoc, tsdoc = get_tsdoc(node, source)
                    parameters = extract_parameters(node)
                    signature = extract_signature(node, source)
                    
                    return_type_node = node.child_by_field_name("return_type")
                    return_type = return_type_node.text.decode() if return_type_node else None
                    
                    decorators = extract_component_decorators(node, parent)
                    calls = extract_function_calls(node, source)
                    
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    is_static = False
                    is_abstract = False
                    for child in node.children:
                        if child.type == "static":
                            is_static = True
                        if child.type == "abstract":
                            is_abstract = True
                    
                    components[cid] = CodeComponent(
                        id=cid,
                        name=method_name,
                        type=ComponentType.METHOD,
                        location=Location(
                            file_path=file_path,
                            start_line=start_line,
                            end_line=end_line
                        ),
                        source_code=source[node.start_byte:node.end_byte],
                        signature=signature,
                        parameters=parameters,
                        return_type=return_type,
                        existing_docstring=tsdoc if has_tsdoc else None,
                        decorators=decorators,
                        calls=calls,
                        imports=file_imports,
                        language="typescript",
                        lines_of_code=end_line - start_line + 1,
                        is_static=is_static,
                        is_abstract=is_abstract,
                        is_async='async' in node.text.decode(),
                    )
        
        elif node.type == "property_signature" and parent_type == "class":
            prop_name = node.child_by_field_name("name")
            if prop_name:
                name = prop_name.text.decode()
                parent_class_node = parent
                if parent_class_node:
                    parent_name = parent_class_node.child_by_field_name("name")
                    if parent_name:
                        parent_class_name = parent_name.text.decode()
                        cid = f"{module_path}.{parent_class_name}.{name}"
                        
                        type_node = node.child_by_field_name("type")
                        prop_type = type_node.text.decode() if type_node else None
                        
                        start_line = node.start_point[0] + 1
                        end_line = node.end_point[0] + 1
                        
                        components[cid] = CodeComponent(
                            id=cid,
                            name=name,
                            type=ComponentType.FIELD,
                            location=Location(
                                file_path=file_path,
                                start_line=start_line,
                                end_line=end_line
                            ),
                            source_code=source[node.start_byte:node.end_byte],
                            signature=f"{name}: {prop_type}" if prop_type else name,
                            return_type=prop_type,
                            imports=file_imports,
                            language="typescript",
                            lines_of_code=1,
                        )
        
        # GLOBAL VARIABLES
        elif node.type == "variable_declaration" and parent_type == "program":
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    if name_node and name_node.type == "identifier":
                        var_name = name_node.text.decode()
                        if f"{module_path}.{var_name}" not in components:
                            cid = f"{module_path}.{var_name}"
                            
                            start_line = node.start_point[0] + 1
                            end_line = node.end_point[0] + 1
                            
                            components[cid] = CodeComponent(
                                id=cid,
                                name=var_name,
                                type=ComponentType.GLOBAL_VARIABLE,
                                location=Location(
                                    file_path=file_path,
                                    start_line=start_line,
                                    end_line=end_line
                                ),
                                source_code=source[node.start_byte:node.end_byte],
                                signature=f"const {var_name}",
                                imports=file_imports,
                                language="typescript",
                                lines_of_code=1,
                            )
        
        for c in node.children:
            walk(c, node.type, node)
    
    walk(root, "program", root)
    
    # Add module_path metadata
    for comp in components.values():
        parts = comp.id.split('.')
        if comp.type == ComponentType.METHOD:
            comp.module_path = '.'.join(parts[:-2]) if len(parts) > 2 else parts[0]
        else:
            comp.module_path = '.'.join(parts[:-1]) if len(parts) > 1 else parts[0]
    
    return components