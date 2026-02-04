"""
Comprehensive Python Code Extractor
Extracts components with full metadata: docstrings, parameters, 
exceptions, control flow, modifiers, and dependencies
"""

from typing import List, Dict, Set, Optional, Tuple, Any
from backend.models.code_component import CodeComponent, Location, Parameter, ComponentType
import builtins
import re

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

BUILTIN_TYPES = set(dir(builtins))
EXCLUDED_NAMES = {"self", "cls"}
STANDARD_MODULES = {
    "abc", "argparse", "array", "asyncio", "base64", "collections", "copy",
    "csv", "datetime", "enum", "functools", "glob", "io", "itertools",
    "json", "logging", "math", "os", "pathlib", "random", "re", "shutil",
    "string", "sys", "time", "typing", "uuid", "warnings", "xml"
}

# ============================================================================
# SECTION 1: BASIC EXTRACTION HELPERS
# ============================================================================

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
    
    for child in body.children:
        if child.type == "expression_statement":
            for expr_child in child.children:
                if expr_child.type == "string":
                    docstring_text = expr_child.text.decode()
                    if docstring_text.startswith('"""') or docstring_text.startswith("'''"):
                        docstring_text = docstring_text[3:-3]
                    elif docstring_text.startswith('"') or docstring_text.startswith("'"):
                        docstring_text = docstring_text[1:-1]
                    return True, docstring_text.strip()
        elif child.type not in ("comment",):
            break
    
    return False, ""


def extract_return_type(func_node) -> Optional[str]:
    """Extract return type hint from function definition"""
    return_type_node = func_node.child_by_field_name("return_type")
    if return_type_node:
        return return_type_node.text.decode().strip()
    return None

def extract_parameters(func_node) -> List[Parameter]:
    """
    Extract parameters with FULL metadata including defaults and annotations
    
    Args:
        func_node: tree-sitter function definition node
        
    Returns:
        list: List of Parameter objects
    """
    parameters = []
    params_node = func_node.child_by_field_name("parameters")
    
    if not params_node:
        return parameters
    
    for child in params_node.children:
        if child.type == "identifier":
            param_name = child.text.decode()
            parameters.append(Parameter(
                name=param_name,
                type_hint=None,
                default_value=None,
                is_required=True
            ))
            
        elif child.type == "typed_parameter":
            name_node = child.child_by_field_name("name")
            type_node = child.child_by_field_name("type")
            default_node = child.child_by_field_name("default_value")
            
            param_name = name_node.text.decode() if name_node else None
            param_type = type_node.text.decode() if type_node else None
            param_default = default_node.text.decode() if default_node else None
            
            if param_name:
                parameters.append(Parameter(
                    name=param_name,
                    type_hint=param_type,
                    default_value=param_default,
                    is_required=param_default is None
                ))
        
        elif child.type == "default_parameter":
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")
            
            param_name = name_node.text.decode() if name_node else None
            param_default = value_node.text.decode() if value_node else None
            
            if param_name:
                parameters.append(Parameter(
                    name=param_name,
                    type_hint=None,
                    default_value=param_default,
                    is_required=False
                ))
        
        elif child.type == "typed_default_parameter":
            name_node = child.child_by_field_name("name")
            type_node = child.child_by_field_name("type")
            value_node = child.child_by_field_name("value")
            
            param_name = name_node.text.decode() if name_node else None
            param_type = type_node.text.decode() if type_node else None
            param_default = value_node.text.decode() if value_node else None
            
            if param_name:
                parameters.append(Parameter(
                    name=param_name,
                    type_hint=param_type,
                    default_value=param_default,
                    is_required=False
                ))
    
    return parameters


def extract_signature(func_node, source) -> str:
    """Extract function signature from node"""
    sig_start = func_node.start_byte
    sig_end = func_node.end_byte
    
    source_text = source[sig_start:sig_end]
    colon_pos = source_text.find(':')
    if colon_pos != -1:
        return source_text[:colon_pos+1].strip()
    return source_text.split('\n')[0]


def extract_imports_and_decorators(tree, source, module_path) -> Tuple[List[str], List[str]]:
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


def extract_component_decorators(node, parent=None) -> List[str]:
    """Extract ALL decorators on a function/class"""
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
        
        elif child.type in ("comment", "newline"):
            i -= 1
        else:
            break
    
    return decorators


def extract_function_calls(func_node, source) -> List[str]:
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


def extract_class_attributes(class_node, source) -> List[Dict[str, Any]]:
    """
    Extract class attributes from:
    1. Pydantic model fields (type hints in class body)
    2. Typed assignments in __init__
    3. Annotated assignments (Python 3.6+)
    
    Returns:
        list: List of dicts with 'name', 'type', 'description'
    """
    attributes = []
    body = class_node.child_by_field_name("body")
    
    if not body:
        return attributes
    
    # 1. Extract class-level annotations (PydanticModel fields)
    for stmt in body.children:
        # Handle: field_name: type = default
        if stmt.type == "expression_statement":
            for child in stmt.children:
                if child.type == "annotated_assignment":
                    name_node = child.child_by_field_name("name")
                    type_node = child.child_by_field_name("type")
                    
                    if name_node:
                        attr_name = name_node.text.decode()
                        attr_type = type_node.text.decode() if type_node else 'any'
                        
                        # Skip private/magic attributes
                        if not attr_name.startswith('_'):
                            attributes.append({
                                'name': attr_name,
                                'type': attr_type,
                                'description': f"Field of type {attr_type}"
                            })
    
    # 2. Extract from __init__ method assignments (self.x = ...)
    for stmt in body.children:
        if stmt.type in ("function_definition", "async_function_definition"):
            func_name = stmt.child_by_field_name("name")
            if func_name and func_name.text.decode() == "__init__":
                func_body = stmt.child_by_field_name("body")
                if func_body:
                    _extract_init_attributes(func_body, attributes, source)
        
        elif stmt.type == "decorated_definition":
            for child in stmt.children:
                if child.type in ("function_definition", "async_function_definition"):
                    func_name = child.child_by_field_name("name")
                    if func_name and func_name.text.decode() == "__init__":
                        func_body = child.child_by_field_name("body")
                        if func_body:
                            _extract_init_attributes(func_body, attributes, source)
    
    return attributes


def _extract_init_attributes(func_body, attributes: List[Dict[str, Any]], source: str) -> None:
    """Extract self.x = ... assignments from __init__ method"""
    
    for stmt in func_body.children:
        if stmt.type == "expression_statement":
            for child in stmt.children:
                if child.type == "assignment":
                    lhs = child.child_by_field_name("left")
                    rhs = child.child_by_field_name("right")
                    
                    if lhs and lhs.type == "attribute":
                        obj = lhs.child_by_field_name("object")
                        attr = lhs.child_by_field_name("attribute")
                        
                        if obj and attr and obj.type == "identifier" and obj.text.decode() == "self":
                            attr_name = attr.text.decode()
                            
                            # Skip private attributes
                            if attr_name.startswith('_'):
                                continue
                            
                            # Try to infer type from assignment
                            attr_type = 'any'
                            if rhs:
                                attr_type = _infer_type_from_expression(rhs, source)
                            
                            # Check if attribute already exists (from annotations)
                            existing = next((a for a in attributes if a['name'] == attr_name), None)
                            if existing:
                                # Update type if inferred
                                if attr_type != 'any':
                                    existing['type'] = attr_type
                            else:
                                # New attribute
                                attributes.append({
                                    'name': attr_name,
                                    'type': attr_type,
                                    'description': f"Instance attribute of type {attr_type}"
                                })


def _infer_type_from_expression(expr_node, source: str) -> str:
    """Infer type from right-hand side expression"""
    expr_text = expr_node.text.decode()
    
    # Check common patterns
    if expr_node.type == "string":
        return "str"
    elif expr_node.type == "integer":
        return "int"
    elif expr_node.type == "float":
        return "float"
    elif expr_node.type == "true" or expr_node.type == "false":
        return "bool"
    elif expr_node.type == "list":
        return "list"
    elif expr_node.type == "dictionary":
        return "dict"
    elif expr_node.type == "call":
        # Try to extract function name
        fn = expr_node.child_by_field_name("function")
        if fn:
            fn_name = fn.text.decode()
            if fn_name == "dict":
                return "dict"
            elif fn_name == "list":
                return "list"
            elif fn_name == "set":
                return "set"
            elif fn_name == "tuple":
                return "tuple"
            # Return the class name for custom types
            return fn_name.split('.')[-1]
    
    return "any"


# ============================================================================
# SECTION 2: EXCEPTION EXTRACTION
# ============================================================================

def extract_exceptions(func_node) -> List[Dict]:
    """
    Extract all exceptions raised in a function using tree-sitter.
    
    Handles:
    - Direct raise statements: raise ValueError(...)
    - Conditional raises: if x: raise ValueError(...)
    - Exception messages
    
    Args:
        func_node: tree-sitter function definition node
        
    Returns:
        list: List of dicts with 'exception', 'condition', 'message'
    """
    exceptions = []
    
    def extract_exception_text(exc_node) -> Tuple[str, str]:
        """Extract exception name and message from raise statement"""
        if not exc_node:
            return 'Exception', ''
        
        exc_text = exc_node.text.decode()
        
        # Handle: raise ValueError("message")
        exc_type = exc_text.split('(')[0].strip() if '(' in exc_text else exc_text.strip()
        
        # Extract message
        message_match = re.search(r'\(\s*["\'](.+?)["\']\s*\)', exc_text)
        message = message_match.group(1) if message_match else ''
        
        return exc_type, message
    
    def walk(node, parent_type=None):
        """Walk AST to find raise statements"""
        
        if node.type == "raise_statement":
            exc_node = node.child_by_field_name("exception")
            exc_type, message = extract_exception_text(exc_node)
            
            # Try to find parent if statement for condition
            condition = None
            parent = node.parent
            while parent:
                if parent.type == "if_statement":
                    cond_node = parent.child_by_field_name("condition")
                    if cond_node:
                        condition = cond_node.text.decode().strip()
                    break
                parent = parent.parent
            
            exceptions.append({
                'exception': exc_type,
                'condition': condition or 'Unconditional',
                'message': message
            })
        
        for child in node.children:
            walk(child, node.type)
    
    walk(func_node)
    return exceptions


# ============================================================================
# SECTION 3: CONTROL FLOW ANALYSIS
# ============================================================================

def extract_control_flow(func_node) -> Dict:
    """
    Extract control flow information from a function
    
    Returns dict with:
    - has_loop: whether function has loops
    - loop_type: 'infinite', 'for', 'while', None
    - has_try_except: whether function has error handling
    - has_async_operations: whether function uses await/async
    - num_branches: number of if/elif branches
    - has_infinite_loop: whether it has while True
    """
    flow = {
        'has_loop': False,
        'loop_type': None,
        'has_try_except': False,
        'has_async_operations': False,
        'num_branches': 0,
        'has_infinite_loop': False
    }
    
    def walk(node):
        nonlocal flow
        
        # Detect loops
        if node.type == "for_statement":
            flow['has_loop'] = True
            flow['loop_type'] = 'for'
        
        elif node.type == "while_statement":
            flow['has_loop'] = True
            flow['loop_type'] = 'while'
            # Check if infinite loop (while True)
            cond = node.child_by_field_name("condition")
            if cond and cond.text.decode() == "True":
                flow['has_infinite_loop'] = True
                flow['loop_type'] = 'infinite'
        
        # Detect exception handling
        elif node.type == "try_statement":
            flow['has_try_except'] = True
        
        # Detect branching
        elif node.type == "if_statement":
            flow['num_branches'] += 1
        
        # Detect async operations
        elif node.type in ("await", "async_with", "async_for"):
            flow['has_async_operations'] = True
        
        for child in node.children:
            walk(child)
    
    walk(func_node)
    return flow


# ============================================================================
# SECTION 4: MODIFIER DETECTION
# ============================================================================

def extract_modifiers(func_node, component_decorators: List[str]) -> Dict[str, bool]:
    """
    Extract function modifiers from decorators
    
    Returns dict with:
    - is_static: whether it's a @staticmethod
    - is_class_method: whether it's a @classmethod
    - is_abstract: whether it's @abstractmethod
    - is_property: whether it's @property
    """
    return {
        'is_static': any('@staticmethod' in d for d in component_decorators),
        'is_class_method': any('@classmethod' in d for d in component_decorators),
        'is_abstract': any('@abstractmethod' in d for d in component_decorators),
        'is_property': any('@property' in d for d in component_decorators),
    }


# ============================================================================
# SECTION 5: MAIN COMPONENT EXTRACTION
# ============================================================================

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


def extract_components(tree, source, file_path, module_path) -> Dict[str, CodeComponent]:
    """
    Extract all code components (classes, functions, methods, globals) from a parsed tree.
    
    THIS IS THE MAIN ENTRY POINT. Returns components with enriched metadata.
    
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
    
    # Extract module context
    module_vars = _extract_module_level_vars(root)
    file_imports, _ = extract_imports_and_decorators(tree, source, module_path)

    def walk(node, parent_type=None, parent_node=None):

        # -------- TOP-LEVEL FUNCTIONS --------
        if node.type in ("function_definition", "async_function_definition") and parent_type == "module":
            name = node.child_by_field_name("name").text.decode()
            cid = f"{module_path}.{name}"

            # Extract all metadata
            has_docstring, docstring = get_docstring(node, source)
            parameters = extract_parameters(node)
            return_type = extract_return_type(node)  # NEW: Extract return type
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            lines_of_code = end_line - start_line + 1
            signature = extract_signature(node, source)
            func_calls = extract_function_calls(node, source)
            is_async = node.type == "async_function_definition"
            component_decorators = extract_component_decorators(node, parent_node)
            
            # NEW: Extract rich metadata
            exceptions = extract_exceptions(node)
            control_flow = extract_control_flow(node)
            modifiers = extract_modifiers(node, component_decorators)

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
                return_type=return_type,  # NEW: Pass return type
                decorators=component_decorators,
                calls=func_calls,
                imports=file_imports,
                language="python",
                lines_of_code=lines_of_code,
                is_async=is_async,
            )
            
            # Store rich metadata for downstream agents
            component_obj = components[cid]
            component_obj.metadata.update({
                'exceptions': exceptions,
                'control_flow': control_flow,
                'modifiers': modifiers,
                'shared_state_dependencies': [v for v in module_vars if v in component_obj.source_code]
            })

        # -------- CLASSES --------
        elif node.type == "class_definition":
            cname = node.child_by_field_name("name").text.decode()
            class_id = f"{module_path}.{cname}"

            has_docstring, docstring = get_docstring(node, source)
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            lines_of_code = end_line - start_line + 1
            signature = extract_signature(node, source)
            component_decorators = extract_component_decorators(node, parent_node)
            
            # NEW: Extract class attributes
            attributes = extract_class_attributes(node, source)

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
                decorators=component_decorators,
                imports=file_imports,
                language="python",
                lines_of_code=lines_of_code,
                attributes=attributes,  # NEW: Add extracted attributes
            )

            # Extract methods within the class
            body = node.child_by_field_name("body")
            if body:
                for stmt in body.children:

                    # HANDLE: normal or decorated methods
                    if stmt.type in ("function_definition", "async_function_definition"):
                        func_node = stmt
                        stmt_parent = body
                    elif stmt.type == "decorated_definition":
                        func_node = None
                        for c in stmt.children:
                            if c.type in ("function_definition", "async_function_definition"):
                                func_node = c
                                break
                        if not func_node:
                            continue
                        stmt_parent = stmt
                    else:
                        continue

                    # Extract method metadata
                    method_name = func_node.child_by_field_name("name").text.decode()
                    method_id = f"{class_id}.{method_name}"
                    
                    method_has_docstring, method_docstring = get_docstring(func_node, source)
                    method_parameters = extract_parameters(func_node)
                    method_return_type = extract_return_type(func_node)  # NEW: Extract return type for methods
                    method_start_line = func_node.start_point[0] + 1
                    method_end_line = func_node.end_point[0] + 1
                    method_lines_of_code = method_end_line - method_start_line + 1
                    method_signature = extract_signature(func_node, source)
                    method_calls = extract_function_calls(func_node, source)
                    is_async = func_node.type == "async_function_definition"
                    method_decorators = extract_component_decorators(func_node, stmt_parent)
                    
                    # NEW: Extract rich metadata for methods
                    method_exceptions = extract_exceptions(func_node)
                    method_control_flow = extract_control_flow(func_node)
                    method_modifiers = extract_modifiers(func_node, method_decorators)
                    
                    # Detect static/class methods from decorators
                    is_static = method_modifiers['is_static']
                    is_class_method = method_modifiers['is_class_method']

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
                        return_type=method_return_type,  # NEW: Pass return type for methods
                        decorators=method_decorators,
                        calls=method_calls,
                        imports=file_imports,
                        language="python",
                        lines_of_code=method_lines_of_code,
                        is_async=is_async,
                        is_static=is_static,
                        is_class_method=is_class_method,
                    )
                    
                    # Store rich metadata
                    method_obj = components[method_id]
                    method_obj.metadata.update({
                        'exceptions': method_exceptions,
                        'control_flow': method_control_flow,
                        'modifiers': method_modifiers,
                    })
                    
        for c in node.children:
            walk(c, node.type, node)

    # -------- EXTRACT GLOBALS --------
    def extract_globals():
        """Extract module-level variable assignments"""
        for child in root.children:
            if child.type == "expression_statement":
                for expr_child in child.children:
                    if expr_child.type == "assignment":
                        lhs = expr_child.child_by_field_name("left")
                        if lhs and lhs.type == "identifier":
                            var_name = lhs.text.decode()
                            var_id = f"{module_path}.{var_name}"
                            
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
            
            elif child.type == "assignment":
                lhs = child.child_by_field_name("left")
                if lhs and lhs.type == "identifier":
                    var_name = lhs.text.decode()
                    var_id = f"{module_path}.{var_name}"
                    
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

    walk(root, "module", root)
    extract_globals()
    
    # Set module_path for each component
    for comp_id, component in components.items():
        parts = component.id.split(".")
        if component.type.value == "method":
            module_path = ".".join(parts[:-2]) if len(parts) > 2 else parts[0]
        else:
            module_path = ".".join(parts[:-1]) if len(parts) > 1 else parts[0]
        component.module_path = module_path

    return components


# ============================================================================
# SECTION 6: DEPENDENCY RESOLUTION
# ============================================================================

class ImportTracker:
    """Tracks imports in a Python file to resolve external dependencies"""
    def __init__(self):
        self.imports = set()           # Direct imports: import x
        self.from_imports = {}         # From imports: from x import y -> {x: [y]}
        self.wildcard_imports = set()  # Modules with wildcard imports
    
    def collect(self, tree):
        """Collect all imports from the tree"""
        root = tree.root_node
        
        def walk(node):
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        self.imports.add(child.text.decode())
                    elif child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            self.imports.add(name_node.text.decode())
            
            elif node.type == "import_from_statement":
                module_name = None
                for child in node.children:
                    if child.type == "dotted_name":
                        module_name = child.text.decode()
                
                if module_name:
                    if module_name not in self.from_imports:
                        self.from_imports[module_name] = []
                    
                    for child in node.children:
                        if child.type == "wildcard_import":
                            self.wildcard_imports.add(module_name)
                            if "*" not in self.from_imports[module_name]:
                                self.from_imports[module_name].append("*")
                        elif child.type == "dotted_name" and child.text.decode() != module_name:
                            imported = child.text.decode()
                            if imported not in self.from_imports[module_name]:
                                self.from_imports[module_name].append(imported)
                        elif child.type == "aliased_import":
                            name_node = child.child_by_field_name("name")
                            if name_node:
                                imported = name_node.text.decode()
                                if imported not in self.from_imports[module_name]:
                                    self.from_imports[module_name].append(imported)
            
            for c in node.children:
                walk(c)
        
        walk(root)


class GlobalVariableTracker:
    """Tracks module-level (global) variables, constants, and objects"""
    def __init__(self):
        self.global_vars = set()
    
    def collect(self, tree, source):
        """Collect all module-level variable assignments"""
        root = tree.root_node
        
        for child in root.children:
            if child.type == "expression_statement":
                for expr_child in child.children:
                    if expr_child.type == "assignment":
                        lhs = expr_child.child_by_field_name("left")
                        if lhs and lhs.type == "identifier":
                            self.global_vars.add(lhs.text.decode())
            
            elif child.type == "assignment":
                lhs = child.child_by_field_name("left")
                if lhs and lhs.type == "identifier":
                    self.global_vars.add(lhs.text.decode())


def find_component_node(tree, component, comp_type):
    """Locate the tree-sitter node corresponding to a component"""
    root = tree.root_node

    def walk(node, parent_class=None):
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                cname = name_node.text.decode()
                if comp_type == "class" and component.id.endswith(f".{cname}"):
                    return node
                parent_class = cname

        if comp_type == "function" and node.type in ("function_definition", "async_function_definition"):
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
                if component.id.endswith(f".{name}"):
                    return node

        if comp_type == "method":
            if node.type == "decorated_definition":
                for child in node.children:
                    if child.type in ("function_definition", "async_function_definition"):
                        node = child
                        break

            if node.type in ("function_definition", "async_function_definition"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode()
                    if (
                        parent_class
                        and component.id.endswith(f".{name}")
                        and component.id.split(".")[-2] == parent_class
                    ):
                        return node

        for child in node.children:
            found = walk(child, parent_class)
            if found:
                return found
        return None

    return walk(root)


def resolve_dependencies(component, tree, source, all_components) -> Set[str]:
    """
    Resolve dependencies for a component by walking its AST.
    
    This function:
    1. Finds the component's node in the tree
    2. Walks all identifiers and calls in that node
    3. Resolves them to component IDs
    4. Returns the set of dependencies
    
    Args:
        component: CodeComponent to resolve
        tree: tree-sitter tree
        source: source code
        all_components: dict of all components
        
    Returns:
        set: Component IDs that this component depends on
    """
    deps = set()
    name_index = {cid.split(".")[-1]: cid for cid in all_components}
    local_vars = set()
    var_types = {}
    
    comp_type = component.type.value if hasattr(component.type, 'value') else str(component.type)
    class_name = component.id.split(".")[-2] if comp_type == "method" else None
    
    # Extract module context
    import_tracker = ImportTracker()
    import_tracker.collect(tree)
    
    global_tracker = GlobalVariableTracker()
    global_tracker.collect(tree, source)
    
    # Compute module_path
    parts = component.id.split(".")
    if comp_type == "method":
        module_path = ".".join(parts[:-2]) if len(parts) > 2 else parts[0]
    else:
        module_path = ".".join(parts[:-1]) if len(parts) > 1 else parts[0]
    
    repo_modules = set(cid.split(".")[0] for cid in all_components)

    # ---- HELPERS ----

    def extract_chain(node):
        """Extract identifier chain (e.g., obj.attr.method)"""
        if node.type == "identifier":
            return [node.text.decode()]
        if node.type == "attribute":
            obj = node.child_by_field_name("object")
            attr = node.child_by_field_name("attribute")
            if obj and attr:
                return extract_chain(obj) + [attr.text.decode()]
        return []

    def is_ignored_name(name):
        """Check if name should be ignored"""
        return (
            name in BUILTIN_TYPES
            or name in EXCLUDED_NAMES
            or name in STANDARD_MODULES
            or name in local_vars
        )

    def resolve_name(name):
        """Resolve a name to its component ID"""
        if name in global_tracker.global_vars:
            return f"{module_path}.{name}"
        
        for module, imported_names in import_tracker.from_imports.items():
            if module in repo_modules:
                if "*" in imported_names:
                    potential_id = f"{module}.{name}"
                    if potential_id in all_components:
                        return potential_id
                elif name in imported_names:
                    return f"{module}.{name}"
            else:
                if "*" in imported_names or name in imported_names:
                    return f"{module_path}.{name}"
        
        potential_id = f"{module_path}.{name}"
        if potential_id in all_components:
            return potential_id
        
        if name in name_index:
            return name_index[name]
        
        return None

    def process_attribute_chain(chain):
        """Process attribute chain to find dependencies"""
        if not chain:
            return
        
        root = chain[0]
        if is_ignored_name(root):
            return
        
        if root in import_tracker.imports:
            if root not in STANDARD_MODULES and root in repo_modules and len(chain) > 1:
                potential_id = f"{root}.{chain[1]}"
                if potential_id in all_components:
                    deps.add(potential_id)
            return
        
        if root in global_tracker.global_vars:
            potential_id = f"{module_path}.{root}"
            deps.add(potential_id)
            return
        
        resolved = resolve_name(root)
        if resolved:
            deps.add(resolved)

    # ---- WALKER ----

    def walk(node):
        """Recursively walk AST to find dependencies"""

        if comp_type == "class" and node.type == "argument_list":
            parent = node.parent
            if parent and parent.type == "class_definition":
                for child in node.children:
                    if child.type == "identifier":
                        name = child.text.decode()
                        resolved = resolve_name(name)
                        if resolved:
                            deps.add(resolved)
                    elif child.type == "attribute":
                        chain = extract_chain(child)
                        process_attribute_chain(chain)

        if node.type == "assignment":
            lhs = node.child_by_field_name("left")
            rhs = node.child_by_field_name("right")

            if rhs:
                walk(rhs)

            if lhs and rhs:
                var_name = None

                if lhs.type == "identifier":
                    var_name = lhs.text.decode()
                    local_vars.add(var_name)
                elif lhs.type == "attribute":
                    obj = lhs.child_by_field_name("object")
                    attr = lhs.child_by_field_name("attribute")
                    if obj and attr and obj.type == "identifier" and obj.text.decode() == "self":
                        var_name = f"self.{attr.text.decode()}"

                if var_name:
                    if rhs.type == "call":
                        fn = rhs.child_by_field_name("function")
                        if fn:
                            chain = extract_chain(fn)
                            if len(chain) == 1:
                                resolved = resolve_name(chain[0])
                                if resolved:
                                    var_types[var_name] = resolved
                                    deps.add(resolved)

                    elif rhs.type == "identifier":
                        name = rhs.text.decode()
                        resolved = resolve_name(name)
                        if resolved:
                            var_types[var_name] = resolved
                            deps.add(resolved)

            return

        if node.type == "keyword_argument":
            value = node.child_by_field_name("value")
            if value and value.type == "identifier":
                name = value.text.decode()
                if not is_ignored_name(name):
                    resolved = resolve_name(name)
                    if resolved:
                        deps.add(resolved)

        if node.type == "attribute":
            obj = node.child_by_field_name("object")
            if obj and obj.type == "identifier":
                var = obj.text.decode()

                if is_ignored_name(var):
                    pass
                elif var in var_types:
                    deps.add(var_types[var])
                elif f"self.{var}" in var_types:
                    deps.add(var_types[f"self.{var}"])
                elif var in global_tracker.global_vars:
                    potential_id = f"{module_path}.{var}"
                    deps.add(potential_id)
                else:
                    resolved = resolve_name(var)
                    if resolved:
                        deps.add(resolved)
                        return
                    
                    chain = extract_chain(node)
                    process_attribute_chain(chain)
                    return

        if node.type == "identifier":
            name = node.text.decode()
            parent = node.parent

            if parent and parent.type in ("function_definition", "class_definition", "parameter"):
                return

            if parent and parent.type == "attribute":
                attr = parent.child_by_field_name("attribute")
                if attr == node:
                    return

            if parent and parent.type == "keyword_argument":
                key = parent.child_by_field_name("name")
                if key == node:
                    return

            if name == component.id.split(".")[-1]:
                return

            if not is_ignored_name(name):
                resolved = resolve_name(name)
                if resolved:
                    deps.add(resolved)

        if node.type == "call":
            fn = node.child_by_field_name("function")
            if fn:
                chain = extract_chain(fn)
                if chain:
                    root = chain[0]

                    if not is_ignored_name(root):
                        if root == "self" and class_name and len(chain) > 1:
                            method_name = chain[1]
                            cid = f"{component.id.rsplit('.', 1)[0]}.{method_name}"
                            if cid in all_components:
                                deps.add(cid)

                        elif len(chain) == 1:
                            resolved = resolve_name(root)
                            if resolved:
                                deps.add(resolved)
                        
                        else:
                            process_attribute_chain(chain)

        for child in node.children:
            walk(child)

    # ---- MAIN ----

    component_node = find_component_node(tree, component, comp_type)
    if not component_node:
        return deps

    # Track parameters as local variables
    if comp_type in ("function", "method"):
        params = component_node.child_by_field_name("parameters")
        if params:
            for child in params.children:
                if child.type == "identifier":
                    local_vars.add(child.text.decode())
                elif child.type == "typed_parameter":
                    name_node = child.child_by_field_name("name")
                    if name_node and name_node.type == "identifier":
                        local_vars.add(name_node.text.decode())
                elif child.type == "default_parameter":
                    name_node = child.child_by_field_name("name")
                    if name_node and name_node.type == "identifier":
                        local_vars.add(name_node.text.decode())

    walk(component_node)

    # Keep valid dependencies
    valid_deps = set()
    for dep in deps:
        if dep in all_components or dep.split(".")[-1] in global_tracker.global_vars:
            valid_deps.add(dep)

    return valid_deps
