from backend.models.code_component import CodeComponent, ComponentType, Location, Parameter
import ast
import re
from typing import List, Set, Tuple


# API route decorator HTTP methods
ROUTE_METHODS = {"get", "post", "put", "delete", "patch", "head", "options", "trace"}


def _detect_visibility(name):
    """Detect public/private/protected from Python naming conventions."""
    if name.startswith("__") and name.endswith("__"):
        return True, False, False  # Dunder methods are public
    elif name.startswith("__"):
        return False, True, False  # Name-mangled private
    elif name.startswith("_"):
        return False, False, True  # Convention protected
    return True, False, False


def _detect_api_endpoint(decorators):
    """
    Detect API endpoint from decorators.
    Returns (http_method, http_path, framework) or (None, None, None).
    """
    for dec in decorators:
        dec_lower = dec.lower()
        for method in ROUTE_METHODS:
            if re.search(rf'\.{method}\s*\(', dec_lower):
                path_match = re.search(r'\(["\']([^"\']*)["\']', dec)
                path = path_match.group(1) if path_match else None
                framework = None
                if "app." in dec_lower or "router." in dec_lower:
                    framework = "fastapi"
                elif "blueprint." in dec_lower:
                    framework = "flask"
                return method.upper(), path, framework
        if ".route(" in dec_lower:
            path_match = re.search(r'\.route\s*\(["\']([^"\']*)["\']', dec)
            path = path_match.group(1) if path_match else None
            framework = "flask" if "blueprint." in dec_lower else None
            return "GET", path, framework
    return None, None, None


def _has_decorator(decorators, name):
    """Check if decorators contain @name or @name(...)."""
    for dec in decorators:
        stripped = dec.strip()
        if stripped == f"@{name}" or stripped.startswith(f"@{name}("):
            return True
    return False


def _is_class_body_function(func_node):
    """Check if a function node is directly in a class body (i.e., a method)."""
    p = func_node.parent
    # Direct method: class_definition > block > function_definition
    if p and p.type == "block":
        gp = p.parent
        if gp and gp.type == "class_definition":
            return True
    # Decorated method: class_definition > block > decorated_definition > function_definition
    if p and p.type == "decorated_definition":
        gp = p.parent
        if gp and gp.type == "block":
            ggp = gp.parent
            if ggp and ggp.type == "class_definition":
                return True
    return False


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


def extract_parameters(node, source, skip_self_cls=True) -> List[Parameter]:
    """
    Extract function/method parameters with type hints and defaults.
    
    Args:
        node: tree-sitter function_definition or async_function_definition node
        source: full source code string
        skip_self_cls: whether to skip 'self' and 'cls' parameters
        
    Returns:
        List of Parameter objects
    """
    parameters = []
    params_node = node.child_by_field_name("parameters")
    
    if not params_node:
        return parameters
    
    for child in params_node.children:
        # Simple identifier: def foo(x)
        if child.type == "identifier":
            param_name = child.text.decode()
            # Skip self and cls if requested
            if skip_self_cls and param_name in ('self', 'cls'):
                continue
                
            parameters.append(Parameter(
                name=param_name,
                type_hint=None,
                default_value=None,
                is_required=True
            ))
        
        # Typed parameter: def foo(x: int)
        # Structure: identifier, :, type
        elif child.type == "typed_parameter":
            param_name = None
            type_hint = None
            
            # Get name from first identifier child
            for sub_child in child.children:
                if sub_child.type == "identifier" and not param_name:
                    param_name = sub_child.text.decode()
                elif sub_child.type == "type":
                    type_hint = sub_child.text.decode()
            
            if param_name:
                # Skip self and cls if requested
                if skip_self_cls and param_name in ('self', 'cls'):
                    continue
                
                parameters.append(Parameter(
                    name=param_name,
                    type_hint=type_hint,
                    default_value=None,
                    is_required=True
                ))
        
        # Default parameter: def foo(x=10)
        elif child.type == "default_parameter":
            param_name = None
            default_value = None
            
            # Get name and default value
            for sub_child in child.children:
                if sub_child.type == "identifier" and not param_name:
                    param_name = sub_child.text.decode()
                elif sub_child.type not in ("identifier", "="):
                    default_value = sub_child.text.decode()
            
            if param_name:
                # Skip self and cls if requested
                if skip_self_cls and param_name in ('self', 'cls'):
                    continue
                    
                parameters.append(Parameter(
                    name=param_name,
                    type_hint=None,
                    default_value=default_value,
                    is_required=False
                ))
        
        # Typed default parameter: def foo(x: int = 10)
        elif child.type == "typed_default_parameter":
            param_name = None
            type_hint = None
            default_value = None
            
            # Get name, type, and default value
            for sub_child in child.children:
                if sub_child.type == "identifier" and not param_name:
                    param_name = sub_child.text.decode()
                elif sub_child.type == "type":
                    type_hint = sub_child.text.decode()
                elif sub_child.type not in ("identifier", ":", "=", "type"):
                    default_value = sub_child.text.decode()
            
            if param_name:
                # Skip self and cls if requested
                if skip_self_cls and param_name in ('self', 'cls'):
                    continue
                
                parameters.append(Parameter(
                    name=param_name,
                    type_hint=type_hint,
                    default_value=default_value,
                    is_required=False
                ))
        
        # *args or **kwargs
        elif child.type in ("list_splat_pattern", "dictionary_splat_pattern"):
            for sub_child in child.children:
                if sub_child.type == "identifier":
                    param_name = sub_child.text.decode()
                    prefix = "*" if child.type == "list_splat_pattern" else "**"
                    parameters.append(Parameter(
                        name=f"{prefix}{param_name}",
                        type_hint=None,
                        default_value=None,
                        is_required=False
                    ))
    
    return parameters


def extract_return_type(node, source) -> str:
    """
    Extract return type annotation from function.
    
    Args:
        node: tree-sitter function_definition node
        source: full source code string
        
    Returns:
        Return type as string or None
    """
    return_type_node = node.child_by_field_name("return_type")
    if return_type_node:
        return return_type_node.text.decode()
    return None


def extract_decorators(node, source) -> List[str]:
    """
    Extract decorators from a function or class.
    
    Args:
        node: tree-sitter node (can be decorated_definition or function/class)
        source: full source code string
        
    Returns:
        List of decorator strings
    """
    decorators = []
    
    # Check if parent is decorated_definition
    parent = node.parent
    if parent and parent.type == "decorated_definition":
        for child in parent.children:
            if child.type == "decorator":
                decorator_text = child.text.decode()
                decorators.append(decorator_text)
    
    return decorators


def extract_imports(tree, source) -> List[str]:
    """
    Extract all import statements from the module.
    
    Args:
        tree: parsed tree-sitter tree
        source: full source code string
        
    Returns:
        List of imported module names
    """
    imports = []
    root = tree.root_node
    
    def walk_imports(node):
        # import foo, bar
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    imports.append(child.text.decode())
                elif child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        imports.append(name_node.text.decode())
        
        # from foo import bar
        elif node.type == "import_from_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    imports.append(child.text.decode())
                    break  # Only get the module name once
        
        for child in node.children:
            walk_imports(child)
    
    walk_imports(root)
    return list(set(imports))  # Remove duplicates


def extract_calls(node, source) -> List[str]:
    """
    Extract function calls within a node.
    
    Args:
        node: tree-sitter node to search within
        source: full source code string
        
    Returns:
        List of function names called
    """
    calls = []
    
    def walk_calls(n):
        if n.type == "call":
            fn = n.child_by_field_name("function")
            if fn:
                # Simple call: foo()
                if fn.type == "identifier":
                    calls.append(fn.text.decode())
                # Method call: obj.method()
                elif fn.type == "attribute":
                    attr = fn.child_by_field_name("attribute")
                    if attr:
                        calls.append(attr.text.decode())
        
        for child in n.children:
            walk_calls(child)
    
    walk_calls(node)
    return list(set(calls))  # Remove duplicates


def extract_parent_classes(node, source) -> List[str]:
    """
    Extract parent classes from class definition.
    
    Args:
        node: tree-sitter class_definition node
        source: full source code string
        
    Returns:
        List of parent class names
    """
    parent_classes = []
    
    # Look for argument_list which contains base classes
    for child in node.children:
        if child.type == "argument_list":
            for arg in child.children:
                if arg.type == "identifier":
                    parent_classes.append(arg.text.decode())
                elif arg.type == "attribute":
                    # Handle: class Foo(module.BaseClass)
                    parent_classes.append(arg.text.decode())
    
    return parent_classes


def build_signature(name: str, parameters: List[Parameter], return_type: str, is_async: bool, node_type: str) -> str:
    """
    Build function/method signature string.
    
    Args:
        name: function/method/class name
        parameters: list of Parameter objects
        return_type: return type annotation
        is_async: whether function is async
        node_type: 'function', 'method', or 'class'
        
    Returns:
        Signature string
    """
    if node_type == "class":
        return f"class {name}"
    
    # Build parameter string
    param_parts = []
    for p in parameters:
        if p.type_hint and p.default_value:
            param_parts.append(f"{p.name}: {p.type_hint} = {p.default_value}")
        elif p.type_hint:
            param_parts.append(f"{p.name}: {p.type_hint}")
        elif p.default_value:
            param_parts.append(f"{p.name}={p.default_value}")
        else:
            param_parts.append(p.name)
    
    params_str = ", ".join(param_parts)
    
    # Build signature
    prefix = "async def" if is_async else "def"
    ret_str = f" -> {return_type}" if return_type else ""
    
    return f"{prefix} {name}({params_str}){ret_str}"


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
    
    # Extract file-level imports once
    file_imports = extract_imports(tree, source)

    def walk(node, parent_type=None):

        # -------- TOP-LEVEL FUNCTIONS --------
        if node.type in ("function_definition", "async_function_definition") and parent_type == "module":
            name = node.child_by_field_name("name").text.decode()
            cid = f"{module_path}.{name}"

            # Extract all metadata
            has_docstring, docstring = get_docstring(node, source)
            parameters = extract_parameters(node, source, skip_self_cls=False)  # Top-level functions don't have self/cls
            return_type = extract_return_type(node, source)
            decorators = extract_decorators(node, source)
            calls = extract_calls(node, source)
            # Check if async by looking for 'async' keyword in children
            is_async = (node.type == "async_function_definition" or 
                       (len(node.children) > 0 and node.children[0].type == "async"))
            
            # Check if generator
            is_generator = False
            body = node.child_by_field_name("body")
            if body:
                body_text = body.text.decode()
                is_generator = "yield" in body_text
            
            # Build signature
            signature = build_signature(name, parameters, return_type, is_async, "function")
            
            # Calculate lines of code
            lines_of_code = node.end_point[0] - node.start_point[0] + 1

            # Detect visibility
            is_public, is_private, is_protected = _detect_visibility(name)

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
                signature=signature,
                parameters=parameters,
                return_type=return_type,
                decorators=decorators,
                calls=calls,
                imports=file_imports,
                language="python",
                is_async=is_async,
                is_generator=is_generator,
                lines_of_code=lines_of_code,
                existing_docstring=docstring if has_docstring else None,
                is_public=is_public,
                is_private=is_private,
                is_protected=is_protected,
                metadata={"module_path": module_path},
            )

        # -------- DECORATED TOP-LEVEL (functions, classes, API endpoints) --------
        elif node.type == "decorated_definition" and parent_type == "module":
            # Find the underlying definition (function or class)
            func_node = None
            class_node = None
            for c in node.children:
                if c.type in ("function_definition", "async_function_definition"):
                    func_node = c
                    break
                elif c.type == "class_definition":
                    class_node = c
                    break

            if func_node:
                name = func_node.child_by_field_name("name").text.decode()
                cid = f"{module_path}.{name}"

                # Extract all metadata
                has_docstring, docstring = get_docstring(func_node, source)
                parameters = extract_parameters(func_node, source, skip_self_cls=False)
                return_type = extract_return_type(func_node, source)
                decorators = extract_decorators(func_node, source)
                calls = extract_calls(func_node, source)
                is_async = (func_node.type == "async_function_definition" or 
                           (len(func_node.children) > 0 and func_node.children[0].type == "async"))
                
                is_generator = False
                body = func_node.child_by_field_name("body")
                if body:
                    body_text = body.text.decode()
                    is_generator = "yield" in body_text
                
                # Detect API endpoint
                http_method, http_path, framework = _detect_api_endpoint(decorators)
                is_endpoint = http_method is not None
                comp_type = ComponentType.API_ENDPOINT if is_endpoint else ComponentType.FUNCTION

                signature = build_signature(name, parameters, return_type, is_async, "function")
                lines_of_code = func_node.end_point[0] - func_node.start_point[0] + 1

                # Detect visibility
                is_public, is_private, is_protected = _detect_visibility(name)

                # Extract path parameters from http_path
                path_params = re.findall(r'\{(\w+)\}', http_path) if http_path else []

                components[cid] = CodeComponent(
                    id=cid,
                    name=name,
                    type=comp_type,
                    location=Location(
                        file_path=file_path,
                        start_line=func_node.start_point[0] + 1,
                        end_line=func_node.end_point[0] + 1
                    ),
                    source_code=source[func_node.start_byte:func_node.end_byte],
                    signature=signature,
                    parameters=parameters,
                    return_type=return_type,
                    decorators=decorators,
                    calls=calls,
                    imports=file_imports,
                    language="python",
                    is_async=is_async,
                    is_generator=is_generator,
                    lines_of_code=lines_of_code,
                    existing_docstring=docstring if has_docstring else None,
                    is_public=is_public,
                    is_private=is_private,
                    is_protected=is_protected,
                    http_method=http_method,
                    http_path=http_path,
                    framework=framework,
                    path_parameters=path_params,
                    metadata={"module_path": module_path},
                )

            elif class_node:
                # -------- DECORATED CLASS --------
                cname = class_node.child_by_field_name("name").text.decode()
                class_id = f"{module_path}.{cname}"

                has_docstring, docstring = get_docstring(class_node, source)
                decorators = extract_decorators(class_node, source)
                parent_classes = extract_parent_classes(class_node, source)

                signature = f"class {cname}"
                if parent_classes:
                    signature += f"({', '.join(parent_classes)})"

                lines_of_code = class_node.end_point[0] - class_node.start_point[0] + 1
                is_public, is_private, is_protected = _detect_visibility(cname)
                is_abstract_cls = any(
                    "ABC" in pc or "ABCMeta" in pc for pc in parent_classes
                )

                components[class_id] = CodeComponent(
                    id=class_id,
                    name=cname,
                    type=ComponentType.CLASS,
                    location=Location(
                        file_path=file_path,
                        start_line=class_node.start_point[0] + 1,
                        end_line=class_node.end_point[0] + 1
                    ),
                    source_code=source[class_node.start_byte:class_node.end_byte],
                    signature=signature,
                    decorators=decorators,
                    parent_classes=parent_classes,
                    imports=file_imports,
                    language="python",
                    lines_of_code=lines_of_code,
                    existing_docstring=docstring if has_docstring else None,
                    is_public=is_public,
                    is_private=is_private,
                    is_protected=is_protected,
                    is_abstract=is_abstract_cls,
                    metadata={"module_path": module_path},
                )

                # Extract methods, constructors, and static fields from decorated class
                _extract_class_body(class_node, class_id, source, file_path, module_path, file_imports, components)

        # -------- CLASSES --------
        elif node.type == "class_definition":
            cname = node.child_by_field_name("name").text.decode()
            class_id = f"{module_path}.{cname}"

            # Extract all metadata
            has_docstring, docstring = get_docstring(node, source)
            decorators = extract_decorators(node, source)
            parent_classes = extract_parent_classes(node, source)
            
            # Build signature
            signature = f"class {cname}"
            if parent_classes:
                signature += f"({', '.join(parent_classes)})"
            
            # Calculate lines of code
            lines_of_code = node.end_point[0] - node.start_point[0] + 1

            # Detect visibility and abstract status
            is_public, is_private, is_protected = _detect_visibility(cname)
            is_abstract_cls = any(
                "ABC" in pc or "ABCMeta" in pc for pc in parent_classes
            )

            components[class_id] = CodeComponent(
                id=class_id,
                name=cname,
                type=ComponentType.CLASS,
                location=Location(
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1
                ),
                source_code=source[node.start_byte:node.end_byte],
                signature=signature,
                decorators=decorators,
                parent_classes=parent_classes,
                imports=file_imports,
                language="python",
                lines_of_code=lines_of_code,
                existing_docstring=docstring if has_docstring else None,
                is_public=is_public,
                is_private=is_private,
                is_protected=is_protected,
                is_abstract=is_abstract_cls,
                metadata={"module_path": module_path},
            )

            # Extract methods, constructors, and static fields from class body
            _extract_class_body(node, class_id, source, file_path, module_path, file_imports, components)

        # -------- NESTED FUNCTIONS (closures / helpers inside functions) --------
        elif node.type in ("function_definition", "async_function_definition") and parent_type not in ("module", None):
            # Skip class body methods (already extracted by _extract_class_body)
            if not _is_class_body_function(node):
                name = node.child_by_field_name("name").text.decode()
                # Build ID relative to the enclosing function/module
                cid = f"{module_path}.{name}"
                # Avoid overwriting if already extracted with same ID
                if cid not in components:
                    has_docstring, docstring = get_docstring(node, source)
                    parameters = extract_parameters(node, source, skip_self_cls=False)
                    return_type = extract_return_type(node, source)
                    decorators = extract_decorators(node, source)
                    calls = extract_calls(node, source)
                    is_async = (node.type == "async_function_definition" or
                               (len(node.children) > 0 and node.children[0].type == "async"))

                    is_generator = False
                    func_body = node.child_by_field_name("body")
                    if func_body:
                        is_generator = "yield" in func_body.text.decode()

                    signature = build_signature(name, parameters, return_type, is_async, "function")
                    lines_of_code = node.end_point[0] - node.start_point[0] + 1
                    is_public, is_private, is_protected = _detect_visibility(name)

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
                        signature=signature,
                        parameters=parameters,
                        return_type=return_type,
                        decorators=decorators,
                        calls=calls,
                        imports=file_imports,
                        language="python",
                        is_async=is_async,
                        is_generator=is_generator,
                        lines_of_code=lines_of_code,
                        existing_docstring=docstring if has_docstring else None,
                        is_public=is_public,
                        is_private=is_private,
                        is_protected=is_protected,
                        metadata={"module_path": module_path, "is_nested": True},
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
                            
                            # Build a meaningful signature from the assignment
                            type_ann = expr_child.child_by_field_name("type")
                            rhs = expr_child.child_by_field_name("right")
                            if type_ann:
                                sig = f"{var_name}: {type_ann.text.decode()}"
                            elif rhs:
                                rhs_text = rhs.text.decode()
                                sig = f"{var_name} = {rhs_text[:60]}{'...' if len(rhs_text) > 60 else ''}"
                            else:
                                sig = var_name

                            # Don't duplicate if already extracted
                            if var_id not in components:
                                is_public, is_private, is_protected = _detect_visibility(var_name)
                                components[var_id] = CodeComponent(
                                    id=var_id,
                                    name=var_name,
                                    type=ComponentType.GLOBAL_VARIABLE,
                                    location=Location(
                                        file_path=file_path,
                                        start_line=expr_child.start_point[0] + 1,
                                        end_line=expr_child.end_point[0] + 1
                                    ),
                                    source_code=source[expr_child.start_byte:expr_child.end_byte],
                                    signature=sig,
                                    language="python",
                                    is_public=is_public,
                                    is_private=is_private,
                                    is_protected=is_protected,
                                    metadata={"module_path": module_path},
                                )
            
            # Top-level assignments (direct children of module)
            elif child.type == "assignment":
                lhs = child.child_by_field_name("left")
                if lhs and lhs.type == "identifier":
                    var_name = lhs.text.decode()
                    var_id = f"{module_path}.{var_name}"

                    # Build a meaningful signature
                    type_ann = child.child_by_field_name("type")
                    rhs = child.child_by_field_name("right")
                    if type_ann:
                        sig = f"{var_name}: {type_ann.text.decode()}"
                    elif rhs:
                        rhs_text = rhs.text.decode()
                        sig = f"{var_name} = {rhs_text[:60]}{'...' if len(rhs_text) > 60 else ''}"
                    else:
                        sig = var_name
                    
                    # Don't duplicate if already extracted
                    if var_id not in components:
                        is_public, is_private, is_protected = _detect_visibility(var_name)
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
                            signature=sig,
                            language="python",
                            is_public=is_public,
                            is_private=is_private,
                            is_protected=is_protected,
                            metadata={"module_path": module_path},
                        )

    # First extract classes, functions, and methods
    walk(root, "module")
    
    # Then extract global variables
    extract_globals()
    
    return components


def _extract_class_body(class_node, class_id, source, file_path, module_path, file_imports, components):
    """
    Extract methods, constructors, static fields, and nested classes from a class body.
    
    Distinguishes:
    - __init__ → CONSTRUCTOR
    - @staticmethod → is_static=True
    - @classmethod → is_class_method=True
    - @abstractmethod → is_abstract=True
    - @property → metadata["is_property"]=True
    - Class-level assignments → STATIC_FIELD
    - Visibility from naming conventions
    """
    body = class_node.child_by_field_name("body")
    if not body:
        return

    method_ids = []

    for stmt in body.children:
        func_node = None

        # ---- Methods (normal and decorated) ----
        if stmt.type in ("function_definition", "async_function_definition"):
            func_node = stmt

        elif stmt.type == "decorated_definition":
            for c in stmt.children:
                if c.type in ("function_definition", "async_function_definition"):
                    func_node = c
                    break
            if not func_node:
                continue

        # ---- Static fields: class-level assignments ----
        elif stmt.type == "expression_statement":
            for expr_child in stmt.children:
                if expr_child.type == "assignment":
                    _extract_static_field(expr_child, class_id, source, file_path, module_path, components)
            continue

        elif stmt.type == "assignment":
            _extract_static_field(stmt, class_id, source, file_path, module_path, components)
            continue

        else:
            continue

        # ---- Common method / constructor handling ----
        method_name = func_node.child_by_field_name("name").text.decode()
        method_id = f"{class_id}.{method_name}"

        # Extract metadata
        method_has_docstring, method_docstring = get_docstring(func_node, source)
        parameters = extract_parameters(func_node, source, skip_self_cls=True)
        return_type = extract_return_type(func_node, source)
        decorators = extract_decorators(func_node, source)
        calls = extract_calls(func_node, source)
        is_async = (func_node.type == "async_function_definition" or
                   (len(func_node.children) > 0 and func_node.children[0].type == "async"))

        is_generator = False
        func_body = func_node.child_by_field_name("body")
        if func_body:
            body_text = func_body.text.decode()
            is_generator = "yield" in body_text

        # Determine component type
        if method_name == "__init__":
            comp_type = ComponentType.CONSTRUCTOR
        else:
            comp_type = ComponentType.METHOD

        # Detect flags from decorators
        is_static = _has_decorator(decorators, "staticmethod")
        is_class_method = _has_decorator(decorators, "classmethod")
        is_abstract = _has_decorator(decorators, "abstractmethod")
        is_property = _has_decorator(decorators, "property")

        # Detect visibility
        is_public, is_private, is_protected = _detect_visibility(method_name)

        signature = build_signature(method_name, parameters, return_type, is_async, "method")
        lines_of_code = func_node.end_point[0] - func_node.start_point[0] + 1

        method_meta = {"module_path": module_path}
        if is_property:
            method_meta["is_property"] = True

        components[method_id] = CodeComponent(
            id=method_id,
            name=method_name,
            type=comp_type,
            location=Location(
                file_path=file_path,
                start_line=func_node.start_point[0] + 1,
                end_line=func_node.end_point[0] + 1
            ),
            source_code=source[func_node.start_byte:func_node.end_byte],
            signature=signature,
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            calls=calls,
            imports=file_imports,
            language="python",
            is_async=is_async,
            is_generator=is_generator,
            is_static=is_static,
            is_class_method=is_class_method,
            is_abstract=is_abstract,
            is_public=is_public,
            is_private=is_private,
            is_protected=is_protected,
            lines_of_code=lines_of_code,
            existing_docstring=method_docstring if method_has_docstring else None,
            metadata=method_meta,
        )

        method_ids.append(method_id)

    # Update parent class with method IDs and instance attributes
    if class_id in components:
        components[class_id].methods = method_ids
        components[class_id].attributes = _extract_instance_attributes(class_node, source)


def _extract_static_field(assignment_node, class_id, source, file_path, module_path, components):
    """Extract a class-level assignment as a STATIC_FIELD component."""
    lhs = assignment_node.child_by_field_name("left")
    if not lhs or lhs.type != "identifier":
        return

    var_name = lhs.text.decode()
    var_id = f"{class_id}.{var_name}"

    if var_id in components:
        return  # Already extracted

    # Get type annotation if present
    type_node = assignment_node.child_by_field_name("type")
    type_hint = type_node.text.decode() if type_node else None

    is_public, is_private, is_protected = _detect_visibility(var_name)

    components[var_id] = CodeComponent(
        id=var_id,
        name=var_name,
        type=ComponentType.STATIC_FIELD,
        location=Location(
            file_path=file_path,
            start_line=assignment_node.start_point[0] + 1,
            end_line=assignment_node.end_point[0] + 1
        ),
        source_code=source[assignment_node.start_byte:assignment_node.end_byte],
        signature=f"{var_name}: {type_hint}" if type_hint else var_name,
        language="python",
        is_public=is_public,
        is_private=is_private,
        is_protected=is_protected,
        metadata={"module_path": module_path, "class_id": class_id},
    )


def _extract_instance_attributes(class_node, source):
    """
    Extract instance attributes (self.x = ...) from the __init__ method body.

    Scans __init__ for self.<attr> assignments, including typed variants
    like ``self.x: int = 0``.

    Returns:
        List[Dict[str, Any]]: Each dict has 'name' and optionally 'type_hint'.
    """
    attributes = []
    seen = set()

    body = class_node.child_by_field_name("body")
    if not body:
        return attributes

    # Locate __init__
    init_node = None
    for stmt in body.children:
        func_node = None
        if stmt.type in ("function_definition", "async_function_definition"):
            func_node = stmt
        elif stmt.type == "decorated_definition":
            for c in stmt.children:
                if c.type in ("function_definition", "async_function_definition"):
                    func_node = c
                    break
        if func_node:
            name_node = func_node.child_by_field_name("name")
            if name_node and name_node.text.decode() == "__init__":
                init_node = func_node
                break

    if not init_node:
        return attributes

    init_body = init_node.child_by_field_name("body")
    if not init_body:
        return attributes

    def _scan(node):
        if node.type == "assignment":
            lhs = node.child_by_field_name("left")
            if lhs and lhs.type == "attribute":
                obj = lhs.child_by_field_name("object")
                attr = lhs.child_by_field_name("attribute")
                if (obj and attr
                        and obj.type == "identifier"
                        and obj.text.decode() == "self"):
                    attr_name = attr.text.decode()
                    if attr_name not in seen:
                        seen.add(attr_name)
                        type_node = node.child_by_field_name("type")
                        type_hint = type_node.text.decode() if type_node else None
                        attributes.append({"name": attr_name, "type_hint": type_hint})
        for child in node.children:
            _scan(child)

    _scan(init_body)
    return attributes


def _extract_instance_attributes_ast(class_node):
    """
    Extract instance attributes (self.x = ...) from __init__ using the
    built-in ``ast`` module (fallback path).
    """
    attributes = []
    seen = set()

    for item in class_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__":
            for stmt in ast.walk(item):
                # self.x = value
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if (isinstance(target, ast.Attribute)
                                and isinstance(target.value, ast.Name)
                                and target.value.id == "self"):
                            attr_name = target.attr
                            if attr_name not in seen:
                                seen.add(attr_name)
                                attributes.append({"name": attr_name, "type_hint": None})
                # self.x: Type = value  /  self.x: Type
                elif isinstance(stmt, ast.AnnAssign):
                    target = stmt.target
                    if (isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"):
                        attr_name = target.attr
                        if attr_name not in seen:
                            seen.add(attr_name)
                            type_hint = None
                            if stmt.annotation:
                                try:
                                    type_hint = ast.unparse(stmt.annotation)
                                except Exception:
                                    pass
                            attributes.append({"name": attr_name, "type_hint": type_hint})
            break  # only process the first __init__

    return attributes


def extract_components_ast(tree: ast.AST, source: str, file_path: str, module_path: str):
    """
    Fallback extractor using Python's built-in `ast` when tree-sitter isn't available.

    Extracts:
    - Classes (with abstract detection)
    - Functions (with visibility)
    - Methods / Constructors (with decorator flags)
    - Static fields (class-level assignments)
    - Module-level variables/constants
    """
    components = {}

    class ASTVisitor(ast.NodeVisitor):
        def __init__(self):
            super().__init__()
            self.current_class = None

        def add_component(self, cid, ctype, node, docstring, name, **kwargs):
            is_public, is_private, is_protected = _detect_visibility(name)
            components[cid] = CodeComponent(
                id=cid,
                name=name,
                type=ctype,
                location=Location(
                    file_path=file_path,
                    start_line=getattr(node, "lineno", 1),
                    end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1))
                ),
                source_code=source[node.col_offset if hasattr(node, "col_offset") else 0 : node.end_col_offset if hasattr(node, "end_col_offset") else len(source)],
                signature="",
                language="python",
                existing_docstring=docstring.strip() if docstring else None,
                is_public=is_public,
                is_private=is_private,
                is_protected=is_protected,
                metadata={"module_path": module_path},
                **kwargs,
            )

        def visit_ClassDef(self, node: ast.ClassDef):
            cid = f"{module_path}.{node.name}"
            doc = ast.get_docstring(node)
            parent_classes = [
                (b.id if isinstance(b, ast.Name) else ast.dump(b))
                for b in node.bases
            ]
            is_abstract_cls = any("ABC" in pc for pc in parent_classes)
            self.add_component(
                cid, ComponentType.CLASS, node, doc, node.name,
                parent_classes=parent_classes,
                is_abstract=is_abstract_cls,
                decorators=[f"@{ast.dump(d)}" for d in node.decorator_list] if hasattr(node, 'decorator_list') else [],
            )

            # Extract instance attributes from __init__
            components[cid].attributes = _extract_instance_attributes_ast(node)

            prev = self.current_class
            self.current_class = cid
            self.generic_visit(node)
            self.current_class = prev

        def _handle_function(self, node):
            doc = ast.get_docstring(node)
            decorators = []
            if hasattr(node, 'decorator_list'):
                for d in node.decorator_list:
                    if isinstance(d, ast.Name):
                        decorators.append(f"@{d.id}")
                    elif isinstance(d, ast.Attribute):
                        decorators.append(f"@{ast.dump(d)}")
                    else:
                        decorators.append(f"@{ast.dump(d)}")

            is_async = isinstance(node, ast.AsyncFunctionDef)

            if self.current_class:
                cid = f"{self.current_class}.{node.name}"
                # Determine type: CONSTRUCTOR vs METHOD
                if node.name == "__init__":
                    comp_type = ComponentType.CONSTRUCTOR
                else:
                    comp_type = ComponentType.METHOD

                is_static = _has_decorator(decorators, "staticmethod")
                is_class_method = _has_decorator(decorators, "classmethod")
                is_abstract = _has_decorator(decorators, "abstractmethod")

                self.add_component(
                    cid, comp_type, node, doc, node.name,
                    decorators=decorators,
                    is_async=is_async,
                    is_static=is_static,
                    is_class_method=is_class_method,
                    is_abstract=is_abstract,
                )
            else:
                cid = f"{module_path}.{node.name}"
                # Check for API endpoints
                http_method, http_path, framework = _detect_api_endpoint(decorators)
                if http_method:
                    self.add_component(
                        cid, ComponentType.API_ENDPOINT, node, doc, node.name,
                        decorators=decorators,
                        is_async=is_async,
                        http_method=http_method,
                        http_path=http_path,
                        framework=framework,
                    )
                else:
                    self.add_component(
                        cid, ComponentType.FUNCTION, node, doc, node.name,
                        decorators=decorators,
                        is_async=is_async,
                    )
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef):
            self._handle_function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            self._handle_function(node)

        def visit_Assign(self, node: ast.Assign):
            parent_node = getattr(node, "parent", None)
            is_module_level = isinstance(parent_node, ast.Module)
            is_class_level = isinstance(parent_node, ast.ClassDef)

            for target in node.targets:
                if isinstance(target, ast.Name):
                    if is_class_level and self.current_class:
                        # Class-level assignment → STATIC_FIELD
                        cid = f"{self.current_class}.{target.id}"
                        if cid not in components:
                            is_public, is_private, is_protected = _detect_visibility(target.id)
                            components[cid] = CodeComponent(
                                id=cid,
                                name=target.id,
                                type=ComponentType.STATIC_FIELD,
                                location=Location(
                                    file_path=file_path,
                                    start_line=getattr(node, "lineno", 1),
                                    end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1))
                                ),
                                source_code=source[node.col_offset if hasattr(node, "col_offset") else 0 : node.end_col_offset if hasattr(node, "end_col_offset") else len(source)],
                                signature=target.id,
                                language="python",
                                is_public=is_public,
                                is_private=is_private,
                                is_protected=is_protected,
                                metadata={"module_path": module_path, "class_id": self.current_class},
                            )
                    elif is_module_level:
                        # Module-level assignment → GLOBAL_VARIABLE
                        cid = f"{module_path}.{target.id}"
                        if cid not in components:
                            components[cid] = CodeComponent(
                                id=cid,
                                name=target.id,
                                type=ComponentType.GLOBAL_VARIABLE,
                                location=Location(
                                    file_path=file_path,
                                    start_line=getattr(node, "lineno", 1),
                                    end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1))
                                ),
                                source_code=source[node.col_offset if hasattr(node, "col_offset") else 0 : node.end_col_offset if hasattr(node, "end_col_offset") else len(source)],
                                signature="",
                                language="python",
                                metadata={"module_path": module_path},
                            )
            self.generic_visit(node)

    # Attach parents to nodes to help identify module-level assigns
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "parent", parent)

    ASTVisitor().visit(tree)
    return components