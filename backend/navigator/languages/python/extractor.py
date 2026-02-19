from backend.models.code_component import CodeComponent, ComponentType, Location, Parameter
import ast
from typing import List, Set, Tuple


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
                metadata={"module_path": module_path},
            )

        # -------- DECORATED TOP-LEVEL FUNCTIONS (e.g., FastAPI routes) --------
        elif node.type == "decorated_definition" and parent_type == "module":
            # Find the underlying function definition within the decorated node
            func_node = None
            for c in node.children:
                if c.type in ("function_definition", "async_function_definition"):
                    func_node = c
                    break
            if func_node:
                name = func_node.child_by_field_name("name").text.decode()
                cid = f"{module_path}.{name}"

                # Extract all metadata
                has_docstring, docstring = get_docstring(func_node, source)
                parameters = extract_parameters(func_node, source, skip_self_cls=False)  # Top-level decorated functions don't have self/cls
                return_type = extract_return_type(func_node, source)
                decorators = extract_decorators(func_node, source)
                calls = extract_calls(func_node, source)
                # Check if async by looking for 'async' keyword in children
                is_async = (func_node.type == "async_function_definition" or 
                           (len(func_node.children) > 0 and func_node.children[0].type == "async"))
                
                # Check if generator
                is_generator = False
                body = func_node.child_by_field_name("body")
                if body:
                    body_text = body.text.decode()
                    is_generator = "yield" in body_text
                
                # Build signature
                signature = build_signature(name, parameters, return_type, is_async, "function")
                
                # Calculate lines of code
                lines_of_code = func_node.end_point[0] - func_node.start_point[0] + 1

                components[cid] = CodeComponent(
                    id=cid,
                    name=name,
                    type=ComponentType.FUNCTION,
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
                    metadata={"module_path": module_path},
                )

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
                metadata={"module_path": module_path},
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

                    # Extract all metadata
                    method_has_docstring, method_docstring = get_docstring(func_node, source)
                    parameters = extract_parameters(func_node, source, skip_self_cls=True)  # Methods should skip self/cls
                    return_type = extract_return_type(func_node, source)
                    decorators = extract_decorators(func_node, source)
                    calls = extract_calls(func_node, source)
                    # Check if async by looking for 'async' keyword in children
                    is_async = (func_node.type == "async_function_definition" or 
                               (len(func_node.children) > 0 and func_node.children[0].type == "async"))
                    
                    # Check if generator
                    is_generator = False
                    body = func_node.child_by_field_name("body")
                    if body:
                        body_text = body.text.decode()
                        is_generator = "yield" in body_text
                    
                    # Build signature
                    signature = build_signature(method_name, parameters, return_type, is_async, "method")
                    
                    # Calculate lines of code
                    lines_of_code = func_node.end_point[0] - func_node.start_point[0] + 1

                    components[method_id] = CodeComponent(
                        id=method_id,
                        name=method_name,
                        type=ComponentType.METHOD,
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
                        existing_docstring=method_docstring if method_has_docstring else None,
                        metadata={"module_path": module_path},
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
                                    name=var_name,
                                    type=ComponentType.GLOBAL_VARIABLE,
                                    location=Location(
                                        file_path=file_path,
                                        start_line=expr_child.start_point[0] + 1,
                                        end_line=expr_child.end_point[0] + 1
                                    ),
                                    source_code=source[expr_child.start_byte:expr_child.end_byte],
                                    signature="",
                                    language="python",
                                    metadata={"module_path": module_path},
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
                            name=var_name,
                            type=ComponentType.GLOBAL_VARIABLE,
                            location=Location(
                                file_path=file_path,
                                start_line=child.start_point[0] + 1,
                                end_line=child.end_point[0] + 1
                            ),
                            source_code=source[child.start_byte:child.end_byte],
                            signature="",
                            language="python",
                            metadata={"module_path": module_path},
                        )

    # First extract classes, functions, and methods
    walk(root, "module")
    
    # Then extract global variables
    
    return components


def extract_components_ast(tree: ast.AST, source: str, file_path: str, module_path: str):
    """
    Fallback extractor using Python's built-in `ast` when tree-sitter isn't available.

    Extracts:
    - Classes
    - Functions
    - Methods
    - Module-level variables/constants
    """
    components = {}

    class ASTVisitor(ast.NodeVisitor):
        def __init__(self):
            super().__init__()
            self.current_class = None

        def add_component(self, cid, ctype, node, docstring, name):
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
                metadata={"module_path": module_path},
            )

        def visit_ClassDef(self, node: ast.ClassDef):
            cid = f"{module_path}.{node.name}"
            doc = ast.get_docstring(node)
            self.add_component(cid, ComponentType.CLASS, node, doc, node.name)

            prev = self.current_class
            self.current_class = cid
            self.generic_visit(node)
            self.current_class = prev

        def visit_FunctionDef(self, node: ast.FunctionDef):
            doc = ast.get_docstring(node)
            if self.current_class:
                cid = f"{self.current_class}.{node.name}"
                self.add_component(cid, ComponentType.METHOD, node, doc, node.name)
            else:
                cid = f"{module_path}.{node.name}"
                self.add_component(cid, ComponentType.FUNCTION, node, doc, node.name)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            self.visit_FunctionDef(node)  # treat similarly

        def visit_Assign(self, node: ast.Assign):
            # Module-level variables only (no class scope tracking needed here)
            if isinstance(getattr(node, "parent", None), ast.Module) or True:
                for target in node.targets:
                    if isinstance(target, ast.Name):
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