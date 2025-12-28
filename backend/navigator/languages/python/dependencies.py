import builtins

BUILTIN_TYPES = set(dir(builtins))
EXCLUDED_NAMES = {"self", "cls"}

STANDARD_MODULES = {
    "abc", "argparse", "array", "asyncio", "base64", "collections", "copy",
    "csv", "datetime", "enum", "functools", "glob", "io", "itertools",
    "json", "logging", "math", "os", "pathlib", "random", "re", "shutil",
    "string", "sys", "time", "typing", "uuid", "warnings", "xml"
}


class ImportTracker:
    """
    Tracks imports in a Python file to resolve external dependencies.
    """
    def __init__(self):
        self.imports = set()  # Direct imports: import x
        self.from_imports = {}  # From imports: from x import y -> {x: [y]}
        self.wildcard_imports = set()  # Modules with wildcard imports
    
    def collect(self, tree):
        """Collect all imports from the tree"""
        root = tree.root_node
        
        def walk(node):
            # import statement: import os, sys
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        module_name = child.text.decode()
                        self.imports.add(module_name)
                    elif child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            module_name = name_node.text.decode()
                            self.imports.add(module_name)
            
            # from import statement: from x import y, z
            elif node.type == "import_from_statement":
                module_name = None
                has_wildcard = False
                
                # Get the module name
                for child in node.children:
                    if child.type == "dotted_name":
                        module_name = child.text.decode()
                    elif child.type == "wildcard_import":
                        has_wildcard = True
                
                if module_name:
                    if module_name not in self.from_imports:
                        self.from_imports[module_name] = []
                    
                    # Handle wildcard imports
                    if has_wildcard:
                        self.wildcard_imports.add(module_name)
                        # Add wildcard marker
                        if "*" not in self.from_imports[module_name]:
                            self.from_imports[module_name].append("*")
                    else:
                        # Get imported names
                        for child in node.children:
                            if child.type == "dotted_name" and child.text.decode() != module_name:
                                imported_name = child.text.decode()
                                if imported_name not in self.from_imports[module_name]:
                                    self.from_imports[module_name].append(imported_name)
                            elif child.type == "aliased_import":
                                name_node = child.child_by_field_name("name")
                                if name_node:
                                    imported_name = name_node.text.decode()
                                    if imported_name not in self.from_imports[module_name]:
                                        self.from_imports[module_name].append(imported_name)
            
            for c in node.children:
                walk(c)
        
        walk(root)


class GlobalVariableTracker:
    """
    Tracks module-level (global) variables, constants, and objects.
    This includes GUI widgets, constants, and other module-level definitions.
    """
    def __init__(self):
        self.global_vars = set()
    
    def collect(self, tree, source):
        """Collect all module-level variable assignments"""
        root = tree.root_node
        
        for child in root.children:
            # Only look at top-level assignments
            if child.type == "expression_statement":
                # Check if it contains an assignment
                for expr_child in child.children:
                    if expr_child.type == "assignment":
                        lhs = expr_child.child_by_field_name("left")
                        if lhs and lhs.type == "identifier":
                            var_name = lhs.text.decode()
                            self.global_vars.add(var_name)
            
            elif child.type == "assignment":
                lhs = child.child_by_field_name("left")
                if lhs and lhs.type == "identifier":
                    var_name = lhs.text.decode()
                    self.global_vars.add(var_name)


def resolve_dependencies(component, tree, source, all_components):
    """
    Resolve dependencies for a given component by walking its AST node.
    Enhanced to match AST parser capabilities including global variable tracking.
    
    Returns:
        set: Component IDs that this component depends on
    """
    deps = set()
    name_index = {cid.split(".")[-1]: cid for cid in all_components}
    local_vars = set()
    var_types = {}  # Maps variable names to their component IDs
    class_name = component.id.split(".")[-2] if component.type == "method" else None
    
    # Collect imports from the file
    import_tracker = ImportTracker()
    import_tracker.collect(tree)
    
    # Collect global variables from the file
    global_tracker = GlobalVariableTracker()
    global_tracker.collect(tree, source)
    
    # Get module path for this component
    module_path = component.module_path
    
    # Get all modules in the repository
    repo_modules = set()
    for cid in all_components:
        module = cid.split(".")[0]
        repo_modules.add(module)

    # ---------------- HELPERS ----------------

    def extract_chain(node):
        """Extract identifier chain from attribute/call (e.g., obj.attr.method)"""
        if node.type == "identifier":
            return [node.text.decode()]
        if node.type == "attribute":
            obj = node.child_by_field_name("object")
            attr = node.child_by_field_name("attribute")
            if obj and attr:
                return extract_chain(obj) + [attr.text.decode()]
        return []

    def is_ignored_name(name):
        """Check if a name should be ignored in dependency tracking"""
        return (
            name in BUILTIN_TYPES
            or name in EXCLUDED_NAMES
            or name in STANDARD_MODULES
            or name in local_vars
        )

    def is_from_wildcard_import(name):
        """
        Check if a name is from a wildcard import of standard library.
        For documentation purposes, we still TRACK these as dependencies,
        but mark them as wildcard imports so they can be handled specially.
        
        Returns True only to identify them, not to filter them out.
        """
        # This function is now mainly for identification, not filtering
        return False  # Don't filter anything based on wildcard status

    def resolve_name(name):
        """
        Resolve a name to its full component ID.
        This handles:
        1. Global variables in the same module
        2. Imported names (creates virtual dependencies for imports)
        3. Local component references
        
        Returns the resolved ID or None.
        """
        # Check if it's a global variable/constant in the same module
        if name in global_tracker.global_vars:
            potential_id = f"{module_path}.{name}"
            return potential_id
        
        # Check if it's imported from any module (including wildcard)
        for module, imported_names in import_tracker.from_imports.items():
            # Skip repo modules - those are handled separately
            if module in repo_modules:
                if "*" in imported_names:
                    # Wildcard from repo module - check if component exists
                    potential_id = f"{module}.{name}"
                    if potential_id in all_components:
                        return potential_id
                elif name in imported_names:
                    # Explicit import from repo module
                    potential_id = f"{module}.{name}"
                    return potential_id
            else:
                # For non-repo modules (like tkinter, standard library)
                # Create virtual dependencies as module_path.name
                if "*" in imported_names or name in imported_names:
                    # This is imported from external module
                    # Track it as a virtual dependency in current module
                    potential_id = f"{module_path}.{name}"
                    return potential_id
        
        # Check if it's in the current module
        potential_id = f"{module_path}.{name}"
        if potential_id in all_components:
            return potential_id
        
        # Check name_index
        if name in name_index:
            return name_index[name]
        
        return None

    def process_attribute_chain(chain):
        """
        Process an attribute chain to find dependencies.
        Handles cases like: module.Class, obj.method, widget.config, etc.
        """
        if not chain:
            return
        
        root = chain[0]
        
        # Skip ignored names
        if is_ignored_name(root):
            return
        
        # Check if root is a direct import
        if root in import_tracker.imports:
            if root in STANDARD_MODULES:
                return
            if root in repo_modules and len(chain) > 1:
                # module.Class or module.function
                potential_id = f"{root}.{chain[1]}"
                if potential_id in all_components:
                    deps.add(potential_id)
            return
        
        # Check if root is a global variable (like GUI widgets)
        if root in global_tracker.global_vars:
            potential_id = f"{module_path}.{root}"
            deps.add(potential_id)
            return
        
        # Try to resolve the root name
        resolved = resolve_name(root)
        if resolved:
            deps.add(resolved)

    # ---------------- WALKER ----------------

    def walk(node):
        """Recursively walk the AST to find dependencies"""

        # ---- Handle base classes (inheritance) ----
        if component.type == "class" and node.type == "argument_list":
            parent = node.parent
            if parent and parent.type == "class_definition":
                # This is the base class list
                for child in node.children:
                    if child.type == "identifier":
                        name = child.text.decode()
                        resolved = resolve_name(name)
                        if resolved:
                            deps.add(resolved)
                    elif child.type == "attribute":
                        chain = extract_chain(child)
                        process_attribute_chain(chain)

        # ---- Handle assignments: process RHS first, then LHS ----
        if node.type == "assignment":
            lhs = node.child_by_field_name("left")
            rhs = node.child_by_field_name("right")

            # Process right-hand side first to find dependencies
            if rhs:
                walk(rhs)

            # Track variable types from assignments
            if lhs and rhs:
                var_name = None

                # Simple identifier: var = ...
                if lhs.type == "identifier":
                    var_name = lhs.text.decode()
                    local_vars.add(var_name)

                # Attribute assignment: self.var = ...
                elif lhs.type == "attribute":
                    obj = lhs.child_by_field_name("object")
                    attr = lhs.child_by_field_name("attribute")
                    if obj and attr and obj.type == "identifier" and obj.text.decode() == "self":
                        var_name = f"self.{attr.text.decode()}"

                # Track type if RHS is a class instantiation or reference
                if var_name:
                    # Case 1: var = Class() - instantiation
                    if rhs.type == "call":
                        fn = rhs.child_by_field_name("function")
                        if fn:
                            chain = extract_chain(fn)
                            if len(chain) == 1:
                                resolved = resolve_name(chain[0])
                                if resolved:
                                    var_types[var_name] = resolved
                                    deps.add(resolved)

                    # Case 2: var = Class - class reference without call
                    elif rhs.type == "identifier":
                        name = rhs.text.decode()
                        resolved = resolve_name(name)
                        if resolved:
                            var_types[var_name] = resolved
                            deps.add(resolved)

            return  # Don't walk children, we handled them manually

        # ---- Handle keyword arguments (like command=actionPlus) ----
        if node.type == "keyword_argument":
            value = node.child_by_field_name("value")
            if value and value.type == "identifier":
                name = value.text.decode()
                if not is_ignored_name(name):
                    resolved = resolve_name(name)
                    if resolved:
                        deps.add(resolved)

        # ---- Handle attribute access: var.method() or widget.config() ----
        if node.type == "attribute":
            obj = node.child_by_field_name("object")
            if obj and obj.type == "identifier":
                var = obj.text.decode()

                if is_ignored_name(var):
                    pass  # Still need to check children
                elif var in var_types:
                    deps.add(var_types[var])
                elif f"self.{var}" in var_types:
                    deps.add(var_types[f"self.{var}"])
                elif var in global_tracker.global_vars:
                    # Reference to global variable
                    potential_id = f"{module_path}.{var}"
                    deps.add(potential_id)
                else:
                    # Check if this is an imported name (like messagebox.showinfo)
                    resolved = resolve_name(var)
                    if resolved:
                        deps.add(resolved)
                        return  # Don't recurse
                    
                    # Check if this is an imported module/class
                    chain = extract_chain(node)
                    process_attribute_chain(chain)
                    return  # Don't recurse, we handled it

        # ---- Handle identifier references ----
        if node.type == "identifier":
            name = node.text.decode()
            parent = node.parent

            # Skip if this is a definition, not a usage
            if parent and parent.type in ("function_definition", "class_definition", "parameter"):
                return

            # Skip if this is the attribute name (not the object)
            if parent and parent.type == "attribute":
                attr = parent.child_by_field_name("attribute")
                if attr == node:
                    return

            # Skip if this is a keyword argument name
            if parent and parent.type == "keyword_argument":
                key = parent.child_by_field_name("name")
                if key == node:
                    return

            # Skip self-reference
            if name == component.id.split(".")[-1]:
                return

            # Try to resolve via global variables, imports, or local components
            if not is_ignored_name(name):
                resolved = resolve_name(name)
                if resolved:
                    deps.add(resolved)

        # ---- Handle function/method calls ----
        if node.type == "call":
            fn = node.child_by_field_name("function")
            if fn:
                chain = extract_chain(fn)
                if chain:
                    root = chain[0]

                    if not is_ignored_name(root):
                        # Case 1: self.method() - method call on same class
                        if root == "self" and class_name and len(chain) > 1:
                            method_name = chain[1]
                            cid = f"{component.id.rsplit('.', 1)[0]}.{method_name}"
                            if cid in all_components:
                                deps.add(cid)

                        # Case 2: Simple function call or global variable
                        elif len(chain) == 1:
                            resolved = resolve_name(root)
                            if resolved:
                                deps.add(resolved)
                        
                        # Case 3: module.Class() or Class.method() or widget.method()
                        else:
                            process_attribute_chain(chain)

        # Recurse into children
        for child in node.children:
            walk(child)

    # ---------------- FIND AND WALK COMPONENT NODE ----------------

    component_node = find_component_node(tree, component)
    if not component_node:
        return deps

    # Track function/method parameters as local variables
    if component.type in ("function", "method"):
        params = component_node.child_by_field_name("parameters")
        if params:
            for child in params.children:
                if child.type == "identifier":
                    local_vars.add(child.text.decode())
                elif child.type == "typed_parameter":
                    # Handle typed parameters: name: type
                    name_node = child.child_by_field_name("name")
                    if name_node and name_node.type == "identifier":
                        local_vars.add(name_node.text.decode())
                elif child.type == "default_parameter":
                    # Handle default parameters: name=value
                    name_node = child.child_by_field_name("name")
                    if name_node and name_node.type == "identifier":
                        local_vars.add(name_node.text.decode())

    walk(component_node)

    # ---- POST-PROCESSING: Keep valid dependencies ----
    # ---- POST-PROCESSING: Keep valid dependencies ----
    valid_deps = set()
    for dep in deps:
        # Keep if it exists as a component OR is a global variable
        if dep in all_components or dep.split(".")[-1] in global_tracker.global_vars:
            valid_deps.add(dep)

    return valid_deps

def find_component_node(tree, component):
    """
    Locate the tree-sitter node corresponding to a component.
    """
    root = tree.root_node

    def walk(node, parent_class=None):
        # Handle class definitions
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                cname = name_node.text.decode()
                if component.type == "class" and component.id.endswith(f".{cname}"):
                    return node
                parent_class = cname

        # Handle function definitions (top-level functions)
        if component.type == "function" and node.type in ("function_definition", "async_function_definition"):
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
                if component.id.endswith(f".{name}"):
                    return node

        # Handle method definitions (inside classes)
        if component.type == "method":
            # Handle decorated methods
            if node.type == "decorated_definition":
                for child in node.children:
                    if child.type in ("function_definition", "async_function_definition"):
                        node = child
                        break

            # Check if this is our target method
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

        # Recurse into children
        for child in node.children:
            found = walk(child, parent_class)
            if found:
                return found
        return None

    return walk(root)