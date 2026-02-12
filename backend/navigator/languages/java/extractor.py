from typing import List, Dict, Set
from backend.models.code_component import CodeComponent, Location, Parameter, ComponentType


def get_javadoc(node, source):
    """
    Extract Javadoc comment from a class, method, or field declaration.
    Returns (has_javadoc: bool, javadoc_text: str)
    """
    prev_sibling = node.prev_sibling
    
    while prev_sibling and prev_sibling.type in ("line_comment", "comment", "block_comment"):
        if prev_sibling.type in ("comment", "block_comment"):
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


def extract_type_info(type_node):
    """Extract type information from a type node"""
    if not type_node:
        return None
    
    type_text = type_node.text.decode()
    return type_text


def extract_parameters(method_node):
    """
    Extract parameters with full type information.
    Enhanced for DocAgent: includes types for better documentation context.
    """
    parameters = []
    params = method_node.child_by_field_name("parameters")
    
    if params:
        for child in params.children:
            if child.type == "formal_parameter":
                param_name = None
                param_type = None
                
                # Extract type
                type_node = child.child_by_field_name("type")
                if type_node:
                    param_type = extract_type_info(type_node)
                
                # Extract name
                name_node = child.child_by_field_name("name")
                if name_node:
                    param_name = name_node.text.decode()
                
                if param_name:
                    parameters.append(Parameter(
                        name=param_name,
                        type_hint=param_type,
                        is_required=True
                    ))
                    
            elif child.type == "spread_parameter":
                # Varargs: String... args
                type_node = child.child_by_field_name("type")
                name_node = child.child_by_field_name("name")
                
                param_type = extract_type_info(type_node) if type_node else None
                param_name = name_node.text.decode() if name_node else None
                
                if param_name:
                    parameters.append(Parameter(
                        name=f"...{param_name}",
                        type_hint=param_type,
                        is_required=True
                    ))
    
    return parameters


def extract_return_type(method_node):
    """Extract return type from method declaration"""
    return_type_node = method_node.child_by_field_name("type")
    if return_type_node:
        return extract_type_info(return_type_node)
    return None


def extract_signature(node, source):
    """
    Extract clean method/class signature.
    Enhanced: Removes body but keeps full signature with annotations.
    """
    sig_start = node.start_byte
    sig_end = node.end_byte
    source_text = source[sig_start:sig_end]
    
    brace_pos = source_text.find('{')
    if brace_pos != -1:
        return source_text[:brace_pos].strip()
    
    # For abstract methods or interfaces (no body)
    semicolon_pos = source_text.find(';')
    if semicolon_pos != -1:
        return source_text[:semicolon_pos].strip()
    
    return source_text.split('\n')[0]


def get_visibility(node):
    """
    Extract visibility modifiers.
    Returns: (is_public, is_private, is_protected)
    """
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
    
    # Default: package-private (treat as public for DocAgent)
    if not (is_public or is_private or is_protected):
        is_public = True
    
    return is_public, is_private, is_protected


def get_modifiers(node):
    """
    Extract all modifiers for enhanced context.
    Returns dict with: static, final, abstract, synchronized, etc.
    """
    modifiers = {
        'static': False,
        'final': False,
        'abstract': False,
        'synchronized': False,
        'native': False,
        'strictfp': False,
        'transient': False,
        'volatile': False,
    }
    
    for child in node.children:
        if child.type == "modifiers":
            mods_text = child.text.decode().lower()
            for key in modifiers.keys():
                if key in mods_text:
                    modifiers[key] = True
    
    return modifiers


def extract_imports(tree, source):
    """
    Extract all imports from the file.
    Enhanced: Returns structured import info for dependency resolution.
    """
    imports = []
    root = tree.root_node
    
    def walk(node):
        if node.type == "import_declaration":
            import_text = node.text.decode()
            imports.append(import_text)
        for child in node.children:
            walk(child)
    
    walk(root)
    return imports


def extract_annotations(node):
    """
    Extract annotations/decorators with arguments.
    Enhanced: Captures annotation values for better context.
    """
    annotations = []
    
    for child in node.children:
        if child.type == "modifiers":
            for mod_child in child.children:
                if mod_child.type in ("annotation", "marker_annotation"):
                    annotations.append(mod_child.text.decode())
    
    return annotations


def extract_throws_exceptions(method_node):
    """
    Extract declared exceptions from method signature.
    Critical for DocAgent's documentation generation.
    """
    exceptions = []
    
    for child in method_node.children:
        if child.type == "throws":
            for exc_child in child.children:
                if exc_child.type == "type_identifier":
                    exceptions.append(exc_child.text.decode())
    
    return exceptions


def extract_method_calls(method_node, source):
    """
    Extract all method invocations within a method.
    Enhanced: Captures both simple calls and chained calls.
    """
    calls = []
    
    def walk(node):
        if node.type == "method_invocation":
            # Get method name
            method_name_node = node.child_by_field_name("name")
            if method_name_node:
                call_name = method_name_node.text.decode()
                calls.append(call_name)
            
            # Also capture object context for chained calls
            object_node = node.child_by_field_name("object")
            if object_node:
                # This helps identify dependencies on other classes
                obj_text = object_node.text.decode()
                calls.append(f"{obj_text}.{call_name}" if method_name_node else obj_text)
        
        for child in node.children:
            walk(child)
    
    walk(method_node)
    return calls


def extract_field_type(field_node):
    """Extract type information from field declaration"""
    type_node = field_node.child_by_field_name("type")
    if type_node:
        return extract_type_info(type_node)
    return None


def extract_parent_classes(class_node):
    """
    Extract superclass and implemented interfaces.
    Critical for understanding inheritance hierarchy.
    """
    parent_classes = []
    
    # Superclass
    superclass_node = class_node.child_by_field_name("superclass")
    if superclass_node:
        for child in superclass_node.children:
            if child.type == "type_identifier":
                parent_classes.append(child.text.decode())
    
    # Interfaces
    interfaces_node = class_node.child_by_field_name("interfaces")
    if interfaces_node:
        for child in interfaces_node.children:
            if child.type == "type_identifier":
                parent_classes.append(child.text.decode())
    
    return parent_classes


def calculate_complexity(node):
    """
    Calculate approximate cyclomatic complexity.
    Useful for DocAgent to prioritize documentation effort.
    """
    complexity = 1  # Base complexity
    
    def walk(n):
        nonlocal complexity
        if n.type in (
            'if_statement', 'while_statement', 'for_statement', 
            'do_statement', 'catch_clause', 'switch_block_statement_group',
            'conditional_expression', 'enhanced_for_statement'
        ):
            complexity += 1
        
        for child in n.children:
            walk(child)
    
    walk(node)
    return complexity


def extract_components(tree, source, file_path, module_path):
    """
    Extract all Java components optimized for DocAgent workflow.
    
    Returns: Dictionary mapping component_id -> CodeComponent
    
    Key enhancements for DocAgent:
    1. Full type information (parameters, returns, fields)
    2. Exception information (throws clauses)
    3. Modifier details (static, final, abstract, etc.)
    4. Complexity metrics
    5. Call graph data (method invocations)
    6. Inheritance information
    7. Annotation metadata
    """
    components = {}
    root = tree.root_node
    
    # Extract file-level imports once
    file_imports = extract_imports(tree, source)
    
    # Extract package name
    package_name = module_path.split('.')[0] if '.' in module_path else module_path

    def walk(node, parent_id=None):
        
        # ============================================================
        # CLASS DECLARATION
        # ============================================================
        if node.type == "class_declaration":
            class_name_node = node.child_by_field_name("name")
            if not class_name_node:
                return
            
            class_name = class_name_node.text.decode()
            
            if parent_id:
                class_id = f"{parent_id}.{class_name}"
            else:
                class_id = f"{module_path}.{class_name}"

            has_javadoc, javadoc = get_javadoc(node, source)
            annotations = extract_annotations(node)
            modifiers = get_modifiers(node)
            parent_classes = extract_parent_classes(node)
            
            # Extract parent classes
            parent_classes = []
            superclass_node = node.child_by_field_name("superclass")
            if superclass_node:
                parent_classes = [superclass_node.text.decode()]
            
            # Check for interfaces
            interfaces_types = []
            for child in node.children:
                if child.type == "super_interfaces":
                    for intf_child in child.children:
                        if intf_child.type == "type_list":
                            for type_node in intf_child.children:
                                if type_node.type != ",":
                                    interfaces_types.append(type_node.text.decode())
            
            parent_classes.extend(interfaces_types)
            
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            
            sig = extract_signature(node, source)
            is_public, is_private, is_protected = get_visibility(node)
            complexity = calculate_complexity(node)

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
                signature=f"class {name}",
                parent_classes=parent_classes,
                existing_docstring=javadoc if has_javadoc else None,
                decorators=annotations,
                parent_classes=parent_classes,
                imports=file_imports,
                language="java",
                lines_of_code=lines_of_code,
                complexity=complexity,
                is_public=is_public,
                is_private=is_private,
                is_protected=is_protected,
                is_abstract=modifiers['abstract'],
                is_static=modifiers['static'],
                metadata={
                    'modifiers': modifiers,
                    'package': package_name,
                }
            )

            # Extract nested components (methods, fields, inner classes)
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    walk(child, class_id)

        # ============================================================
        # METHOD DECLARATION
        # ============================================================
        elif node.type == "method_declaration" and parent_id:
            method_name_node = node.child_by_field_name("name")
            if not method_name_node:
                return
            
            method_name = method_name_node.text.decode()
            method_id = f"{parent_id}.{method_name}"

            has_javadoc, javadoc = get_javadoc(node, source)
            parameters = extract_parameters(node)
            return_type = extract_return_type(node)
            annotations = extract_annotations(node)
            modifiers = get_modifiers(node)
            exceptions = extract_throws_exceptions(node)
            method_calls = extract_method_calls(node, source)
            
            sig = extract_signature(node, source)
            is_public, is_private, is_protected = get_visibility(node)
            
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            lines_of_code = end_line - start_line + 1
            complexity = calculate_complexity(node)

            components[method_id] = CodeComponent(
                id=method_id,
                name=method_name,
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
                return_type=return_type,
                imports=file_imports,
                decorators=annotations,
                calls=method_calls,
                language="java",
                lines_of_code=lines_of_code,
                complexity=complexity,
                is_public=is_public,
                is_private=is_private,
                is_protected=is_protected,
                is_abstract=modifiers['abstract'],
                is_static=modifiers['static'],
                metadata={
                    'modifiers': modifiers,
                    'throws': exceptions,
                    'package': package_name,
                }
            )

        # ============================================================
        # FIELD DECLARATION
        # ============================================================
        elif node.type == "field_declaration" and parent_id:
            field_type = extract_field_type(node)
            
            for child in node.children:
                if child.type == "variable_declarator":
                    var_name_node = child.child_by_field_name("name")
                    if var_name_node:
                        var_name = var_name_node.text.decode()
                        field_id = f"{parent_id}.{var_name}"
                        
                        modifiers = get_modifiers(node)
                        is_public, is_private, is_protected = get_visibility(node)
                        annotations = extract_annotations(node)
                        has_javadoc, javadoc = get_javadoc(node, source)

                        comp_type = ComponentType.STATIC_FIELD if modifiers['static'] else ComponentType.FIELD

                        components[field_id] = CodeComponent(
                            id=field_id,
                            name=var_name,
                            type=comp_type,
                            location=Location(
                                file_path=file_path,
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1
                            ),
                            source_code=source[node.start_byte:node.end_byte],
                            signature=f"{field_type} {var_name}" if field_type else var_name,
                            existing_docstring=javadoc if has_javadoc else None,
                            parameters=[],
                            decorators=annotations,
                            imports=file_imports,
                            language="java",
                            lines_of_code=1,
                            return_type=field_type,
                            is_public=is_public,
                            is_private=is_private,
                            is_protected=is_protected,
                            is_static=modifiers['static'],
                            metadata={
                                'modifiers': modifiers,
                                'package': package_name,
                            }
                        )

        # ============================================================
        # CONSTRUCTOR DECLARATION
        # ============================================================
        elif node.type == "constructor_declaration" and parent_id:
            parameters = extract_parameters(node)
            has_javadoc, javadoc = get_javadoc(node, source)
            annotations = extract_annotations(node)
            modifiers = get_modifiers(node)
            exceptions = extract_throws_exceptions(node)
            method_calls = extract_method_calls(node, source)
            
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            lines_of_code = end_line - start_line + 1
            complexity = calculate_complexity(node)
            
            sig = extract_signature(node, source)
            is_public, is_private, is_protected = get_visibility(node)
            
            # Constructor naming: ClassName.<init>
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
                complexity=complexity,
                is_public=is_public,
                is_private=is_private,
                is_protected=is_protected,
                metadata={
                    'modifiers': modifiers,
                    'throws': exceptions,
                    'package': package_name,
                }
            )

        # ============================================================
        # INTERFACE DECLARATION (treat as CLASS)
        # ============================================================
        elif node.type == "interface_declaration":
            interface_name_node = node.child_by_field_name("name")
            if not interface_name_node:
                return
            
            interface_name = interface_name_node.text.decode()
            
            if parent_id:
                interface_id = f"{parent_id}.{interface_name}"
            else:
                interface_id = f"{module_path}.{interface_name}"

            has_javadoc, javadoc = get_javadoc(node, source)
            annotations = extract_annotations(node)
            
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            
            sig = extract_signature(node, source)
            is_public, _, _ = get_visibility(node)

            components[interface_id] = CodeComponent(
                id=interface_id,
                name=interface_name,
                type=ComponentType.CLASS,  # Treat interface as class type
                location=Location(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line
                ),
                source_code=source[node.start_byte:node.end_byte],
                signature=sig,
                existing_docstring=javadoc if has_javadoc else None,
                decorators=annotations,
                imports=file_imports,
                language="java",
                lines_of_code=end_line - start_line + 1,
                is_public=is_public,
                is_abstract=True,  # Interfaces are abstract
                metadata={
                    'is_interface': True,
                    'package': package_name,
                }
            )

            # Extract interface methods
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    walk(child, interface_id)

        # Continue walking for nested structures
        for child in node.children:
            walk(child, parent_id)

def _extract_java_exceptions(self, source: str) -> List[Dict]:
    """Extract throws declarations and actual throws in Java"""
    exceptions = []
    
    # throws declaration
    throws_pattern = r'throws\s+([\w\s.,]+)'
    for match in re.finditer(throws_pattern, source):
        exc_list = match.group(1).split(',')
        for exc in exc_list:
            exceptions.append({
                'exception_type': exc.strip(),
                'declared': True,
                'raised': False
            })
    
    # actual throw statements
    throw_pattern = r'throw\s+new\s+(\w+)'
    for match in re.finditer(throw_pattern, source):
        exc_type = match.group(1)
        # Check if already in list
        existing = next((e for e in exceptions if e['exception_type'] == exc_type), None)
        if existing:
            existing['raised'] = True
        else:
            exceptions.append({
                'exception_type': exc_type,
                'declared': False,
                'raised': True
            })
    
    # Add module_path to all components
    for comp in components.values():
        parts = comp.id.split('.')
        if comp.type == ComponentType.METHOD or comp.type == ComponentType.CONSTRUCTOR:
            comp.module_path = '.'.join(parts[:-2]) if len(parts) > 2 else parts[0]
        elif comp.type in (ComponentType.FIELD, ComponentType.STATIC_FIELD):
            comp.module_path = '.'.join(parts[:-2]) if len(parts) > 2 else parts[0]
        else:
            comp.module_path = '.'.join(parts[:-1]) if len(parts) > 1 else parts[0]
    
    return components
