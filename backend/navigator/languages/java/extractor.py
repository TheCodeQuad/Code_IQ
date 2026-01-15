from typing import Dict, List
from backend.models.code_component import CodeComponent, Location, Parameter, ComponentType
import re


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
    """
    Extract parameters with FULL metadata including type hints
    """
    parameters = []
    params = method_node.child_by_field_name("parameters")
    
    if params:
        for child in params.children:
            if child.type == "formal_parameter":
                # Extract name and type
                param_name = None
                param_type = None
                
                for param_child in child.children:
                    if param_child.type == "identifier":
                        param_name = param_child.text.decode()
                    elif param_child.type == "type_identifier":
                        param_type = param_child.text.decode()
                    elif param_child.type == "integral_type":
                        param_type = param_child.text.decode()
                    elif param_child.type == "floating_point_type":
                        param_type = param_child.text.decode()
                    elif param_child.type == "generic_type":
                        param_type = param_child.text.decode()
                
                if param_name:
                    parameters.append(Parameter(
                        name=param_name,
                        type_hint=param_type,
                        is_required=True
                    ))
                    
            elif child.type == "spread_parameter":
                # ... varargs
                param_name = None
                param_type = None
                
                for param_child in child.children:
                    if param_child.type == "identifier":
                        param_name = f"...{param_child.text.decode()}"
                    else:
                        param_type = param_child.text.decode()
                
                if param_name:
                    parameters.append(Parameter(
                        name=param_name,
                        type_hint=param_type,
                        is_required=True
                    ))
    
    return parameters


def extract_signature(method_node, source):
    """Extract method signature from node"""
    sig_start = method_node.start_byte
    sig_end = method_node.end_byte
    
    source_text = source[sig_start:sig_end]
    
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
        if child.type == "annotation" or child.type == "modifiers":
            annotations.append(child.text.decode())
    return annotations


def extract_return_type(method_node):
    """Extract return type from method"""
    return_type_node = method_node.child_by_field_name("type")
    if return_type_node:
        return return_type_node.text.decode()
    return None


def extract_function_calls(method_node, source):
    """Extract all method/function calls within a method"""
    calls = []
    
    def walk(node):
        if node.type == "method_invocation":
            obj = node.child_by_field_name("object")
            method = node.child_by_field_name("name")
            
            if method:
                if obj:
                    call_text = f"{obj.text.decode()}.{method.text.decode()}"
                else:
                    call_text = method.text.decode()
                calls.append(call_text)
        
        for child in node.children:
            walk(child)
    
    walk(method_node)
    return calls


def _extract_module_level_fields(root) -> List[str]:
    """Extract module-level (class-level static) variable names"""
    fields = []
    
    for child in root.children:
        if child.type == "class_declaration":
            for class_child in child.children:
                if class_child.type == "field_declaration":
                    for field_child in class_child.children:
                        if field_child.type == "variable_declarator":
                            var_node = field_child.child_by_field_name("name")
                            if var_node:
                                fields.append(var_node.text.decode())
    
    return fields


def extract_components(tree, source, file_path, module_path):
    """
    Extract all Java components (classes, methods, fields, enums, interfaces)
    """
    components = {}
    root = tree.root_node
    
    file_imports = extract_imports(tree, source)
    module_fields = _extract_module_level_fields(root)
    
    def walk(node, parent_type=None, parent_node=None):
        """Recursively walk the AST tree"""
        
        # CLASSES
        if node.type == "class_declaration":
            class_name = node.child_by_field_name("name")
            if not class_name:
                return
            
            name = class_name.text.decode()
            cid = f"{module_path}.{name}"
            
            has_javadoc, javadoc = get_javadoc(node, source)
            annotations = extract_annotations(node)
            
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
            
            is_abstract = "abstract" in ' '.join(annotations)
            is_static = "static" in ' '.join(annotations)
            
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
                existing_docstring=javadoc if has_javadoc else None,
                decorators=annotations,
                imports=file_imports,
                language="java",
                lines_of_code=end_line - start_line + 1,
                is_abstract=is_abstract,
                is_static=is_static,
            )
            
            # Extract methods and fields from class body
            for child in node.children:
                if child.type == "class_body":
                    for body_child in child.children:
                        walk(body_child, "class", node)
            return
        
        # METHODS
        elif node.type == "method_declaration" and parent_type == "class":
            method_name = node.child_by_field_name("name")
            if not method_name:
                return
            
            name = method_name.text.decode()
            parent_class_node = parent_node
            if parent_class_node:
                parent_name = parent_class_node.child_by_field_name("name")
                if parent_name:
                    parent_class_name = parent_name.text.decode()
                    cid = f"{module_path}.{parent_class_name}.{name}"
                    
                    has_javadoc, javadoc = get_javadoc(node, source)
                    parameters = extract_parameters(node)
                    signature = extract_signature(node, source)
                    return_type = extract_return_type(node)
                    annotations = extract_annotations(node)
                    calls = extract_function_calls(node, source)
                    
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    is_public, is_private, is_protected = get_visibility(node)
                    is_static = "static" in ' '.join(annotations)
                    is_abstract = "abstract" in ' '.join(annotations)
                    
                    components[cid] = CodeComponent(
                        id=cid,
                        name=name,
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
                        existing_docstring=javadoc if has_javadoc else None,
                        decorators=annotations,
                        calls=calls,
                        imports=file_imports,
                        language="java",
                        lines_of_code=end_line - start_line + 1,
                        is_public=is_public,
                        is_private=is_private,
                        is_protected=is_protected,
                        is_static=is_static,
                        is_abstract=is_abstract,
                    )
            return
        
        # FIELDS
        elif node.type == "field_declaration" and parent_type == "class":
            for child in node.children:
                if child.type == "variable_declarator":
                    var_node = child.child_by_field_name("name")
                    if var_node:
                        var_name = var_node.text.decode()
                        parent_class_node = parent_node
                        if parent_class_node:
                            parent_name = parent_class_node.child_by_field_name("name")
                            if parent_name:
                                parent_class_name = parent_name.text.decode()
                                cid = f"{module_path}.{parent_class_name}.{var_name}"
                                
                                # Extract type
                                field_type = None
                                for field_child in node.children:
                                    if field_child.type in ("type_identifier", "integral_type", "floating_point_type", "generic_type"):
                                        field_type = field_child.text.decode()
                                        break
                                
                                annotations = extract_annotations(node)
                                is_static = "static" in ' '.join(annotations)
                                is_public, is_private, is_protected = get_visibility(node)
                                
                                start_line = node.start_point[0] + 1
                                end_line = node.end_point[0] + 1
                                
                                components[cid] = CodeComponent(
                                    id=cid,
                                    name=var_name,
                                    type=ComponentType.FIELD,
                                    location=Location(
                                        file_path=file_path,
                                        start_line=start_line,
                                        end_line=end_line
                                    ),
                                    source_code=source[node.start_byte:node.end_byte],
                                    signature=f"{field_type} {var_name}" if field_type else var_name,
                                    return_type=field_type,
                                    decorators=annotations,
                                    imports=file_imports,
                                    language="java",
                                    lines_of_code=1,
                                    is_static=is_static,
                                    is_public=is_public,
                                    is_private=is_private,
                                    is_protected=is_protected,
                                )
            return
        
        # ENUMS
        elif node.type == "enum_declaration":
            enum_name = node.child_by_field_name("name")
            if enum_name:
                name = enum_name.text.decode()
                cid = f"{module_path}.{name}"
                
                has_javadoc, javadoc = get_javadoc(node, source)
                annotations = extract_annotations(node)
                
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                
                components[cid] = CodeComponent(
                    id=cid,
                    name=name,
                    type=ComponentType.CLASS,  # Treat as class for now
                    location=Location(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line
                    ),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=f"enum {name}",
                    existing_docstring=javadoc if has_javadoc else None,
                    decorators=annotations,
                    imports=file_imports,
                    language="java",
                    lines_of_code=end_line - start_line + 1,
                )
                
                # Extract enum body items
                for child in node.children:
                    if child.type == "enum_body":
                        for body_child in child.children:
                            walk(body_child, "enum", node)
            return
        
        # INTERFACES
        elif node.type == "interface_declaration":
            intf_name = node.child_by_field_name("name")
            if intf_name:
                name = intf_name.text.decode()
                cid = f"{module_path}.{name}"
                
                has_javadoc, javadoc = get_javadoc(node, source)
                annotations = extract_annotations(node)
                
                # Extract parent interfaces
                parent_classes = []
                for child in node.children:
                    if child.type == "extends_interfaces":
                        for ext_child in child.children:
                            if ext_child.type != ",":
                                parent_classes.append(ext_child.text.decode())
                
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                
                components[cid] = CodeComponent(
                    id=cid,
                    name=name,
                    type=ComponentType.CLASS,  # Treat as class
                    location=Location(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line
                    ),
                    source_code=source[node.start_byte:node.end_byte],
                    signature=f"interface {name}",
                    parent_classes=parent_classes,
                    existing_docstring=javadoc if has_javadoc else None,
                    decorators=annotations,
                    imports=file_imports,
                    language="java",
                    lines_of_code=end_line - start_line + 1,
                    is_abstract=True,
                )
                
                # Extract interface body items
                for child in node.children:
                    if child.type == "interface_body":
                        for body_child in child.children:
                            walk(body_child, "interface", node)
            return
        
        # Continue walking for other node types
        for c in node.children:
            walk(c, node.type if node.type not in ("class_body", "enum_body", "interface_body") else parent_type, parent_node)
    
    # Start walking from root
    walk(root)
    
    # Add module_path metadata
    for comp in components.values():
        parts = comp.id.split('.')
        if comp.type == ComponentType.FIELD or comp.type == ComponentType.METHOD:
            # For methods/fields, module_path is everything except method/field and class name
            comp.module_path = '.'.join(parts[:-2]) if len(parts) > 2 else parts[0]
        else:
            # For classes, module_path is everything except class name
            comp.module_path = '.'.join(parts[:-1]) if len(parts) > 1 else parts[0]
    
    return components


def _extract_field_declarations(self, source: str, class_node) -> List[Dict]:
    """Extract field declarations with visibility and types"""
    fields = []
    
    # Pattern: [visibility] [modifier] type name [= value];
    field_pattern = r'(public|private|protected)?\s*(static)?\s*(final)?\s*(\w+(?:<[^>]+>)?)\s+(\w+)'
    
    for match in re.finditer(field_pattern, source):
        visibility = match.group(1) or 'package'
        is_static = bool(match.group(2))
        is_final = bool(match.group(3))
        field_type = match.group(4)
        field_name = match.group(5)
        
        fields.append({
            'name': field_name,
            'type': field_type,
            'visibility': visibility,
            'is_static': is_static,
            'is_final': is_final,
            'initialized_in': self._find_initialization_point(source, field_name)
        })
    
    return fields


def _extract_java_modifiers(self, source: str, method_name: str) -> Dict:
    """Extract modifiers for Java methods"""
    # Find method definition line
    method_pattern = rf'(public|private|protected)?\s*(static)?\s*(abstract)?\s*\w+\s+{method_name}\s*\('
    match = re.search(method_pattern, source)
    
    if match:
        return {
            'visibility': match.group(1) or 'package',
            'is_static': bool(match.group(2)),
            'is_abstract': bool(match.group(3)),
            'is_synchronized': 'synchronized' in source[max(0, match.start()-100):match.start()]
        }
    
    return {'visibility': 'package', 'is_static': False}


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
    
    return exceptions