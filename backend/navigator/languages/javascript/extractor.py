from typing import List
from backend.models.code_component import CodeComponent, Location, Parameter, ComponentType


def get_jsdoc(node, source):
    """
    Extract JSDoc comment from a function or class declaration.
    
    Args:
        node: tree-sitter node (function_declaration, class_declaration, method_definition)
        source: full source code string
        
    Returns:
        tuple: (has_jsdoc: bool, jsdoc: str)
    """
    prev_sibling = node.prev_sibling
    
    while prev_sibling and prev_sibling.type == "comment":
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
        prev_sibling = prev_sibling.prev_sibling
    
    return False, ""


def extract_parameters(node):
    """
    Extract parameters with metadata including defaults
    Extract parameters with metadata including defaults
    
    Args:
        node: tree-sitter function/method node
        
    Returns:
        list: List of Parameter objects
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
                
            elif child.type == "assignment_pattern":
                # Handles: param = defaultValue
                left = child.child_by_field_name("left")
                right = child.child_by_field_name("right")
                
                if left and left.type == "identifier":
                    param_name = left.text.decode()
                    param_default = right.text.decode() if right else None
                    
                    parameters.append(Parameter(
                        name=param_name,
                        type_hint=None,
                        default_value=param_default,
                        is_required=False
                    ))
                    
            elif child.type == "rest_pattern":
                # Handles: ...rest
                for param_child in child.children:
                    if param_child.type == "identifier":
                        param_name = f"...{param_child.text.decode()}"
                        parameters.append(Parameter(
                            name=param_name,
                            type_hint=None,
                            is_required=True
                        ))
                        break
                        
            elif child.type == "object_pattern":
                # Handles: { prop1, prop2 }
                parameters.append(Parameter(
                    name=child.text.decode(),
                    type_hint="object",
                    is_required=True
                ))
                
            elif child.type == "array_pattern":
                # Handles: [a, b, c]
                parameters.append(Parameter(
                    name=child.text.decode(),
                    type_hint="array",
                    is_required=True
                ))
    
    return parameters


def extract_signature(node, source):
    """Extract function signature from node."""
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
            # Handle: import x from 'module'
            for child in node.children:
                if child.type == "string":
                    import_path = child.text.decode().strip('\'"')
                    imports.append(import_path)
        
        elif node.type == "import_from_statement":
            # Handle: import { x } from 'module'
            for child in node.children:
                if child.type == "string":
                    import_path = child.text.decode().strip('\'"')
                    imports.append(import_path)
        
        elif node.type == "decorator":
            # TypeScript/Babel decorators
            decorators.append(node.text.decode())
        
        for child in node.children:
            walk(child)
    
    walk(root)
    return imports, decorators


def extract_function_calls(func_node, source):
    """Extract all function/method calls within a function"""
    calls = []
    
    def walk(node):
        # Call expressions: func(), obj.method()
        if node.type == "call_expression":
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
    Extract JavaScript code components:
    - functions (function foo() {})
    - arrow functions (const foo = () => {})
    - classes
    - class methods
    - module-level fallback (CRITICAL for Node/script repos)
    
    Enhanced with:
    - JSDoc extraction
    - Parameter extraction
    - Signature extraction
    - Function call tracking
    - Import tracking
    
    Returns: Dictionary mapping component_id -> CodeComponent
    """
    components = {}  # ✅ CHANGED: Dictionary instead of list
    root = tree.root_node
    
    found_symbol = False  # 🔥 IMPORTANT for module fallback
    
    # Extract file-level imports
    file_imports, _ = extract_imports_and_decorators(tree, source, module_path)

    def walk(node):
        nonlocal found_symbol

        # -----------------------------------
        # FUNCTION DECLARATION
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
                    existing_docstring=jsdoc if has_jsdoc else None,
                    calls=calls,
                    imports=file_imports,
                    language="javascript",
                    lines_of_code=end_line - start_line + 1,
                    is_async='async' in node.text.decode(),
                )

        # -----------------------------------
        # ARROW FUNCTION
        # const foo = () => {}
        # -----------------------------------
        elif node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")

            if (
                name_node
                and value_node
                and value_node.type == "arrow_function"
            ):
                found_symbol = True
                name = name_node.text.decode()
                cid = f"{module_path}.{name}"
                
                # Get JSDoc from the variable declaration parent
                var_decl = node.parent
                has_jsdoc, jsdoc = get_jsdoc(var_decl, source) if var_decl else (False, "")
                parameters = extract_parameters(value_node)
                signature = extract_signature(value_node, source)
                calls = extract_function_calls(value_node, source)
                
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
                    existing_docstring=jsdoc if has_jsdoc else None,
                    calls=calls,
                    imports=file_imports,
                    language="javascript",
                    lines_of_code=end_line - start_line + 1,
                    is_async='async' in source[node.start_byte:node.end_byte],
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
                
                # Extract parent classes
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
                    location=Location(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line
                    ),
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
                                
                                method_start = child.start_point[0] + 1
                                method_end = child.end_point[0] + 1
                                
                                # Check if static
                                is_static = False
                                for method_child in child.children:
                                    if method_child.type == "static":
                                        is_static = True
                                        break
                                
                                components[method_id] = CodeComponent(
                                    id=method_id,
                                    name=method_name,
                                    type=ComponentType.METHOD,
                                    location=Location(
                                        file_path=file_path,
                                        start_line=method_start,
                                        end_line=method_end
                                    ),
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
                                )

        for child in node.children:
            walk(child)

    walk(root)

    # =====================================================
    # 🔥 MODULE-LEVEL FALLBACK (MANDATORY FOR JS)
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
