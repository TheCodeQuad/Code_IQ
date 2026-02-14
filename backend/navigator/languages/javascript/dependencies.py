# languages/javascript/dependencies.py

JS_ASSET_EXTENSIONS = (".css", ".scss", ".sass", ".less", ".json")

EXTERNAL_MODULES = {
    "react", "react-dom", "prop-types",
    "chai", "mocha", "jest",
    "big.js"
}


def resolve_dependencies(component, tree, source, all_components):
    """
    FULL JS dependency resolver (Tree-sitter)
    - Symbol based
    - JSX aware
    - Import aware
    - Test-safe
    - Arrow function aware
    """

    deps = set()

    # --------------------------------------------------
    # Build symbol table: Name -> [component_ids]
    # --------------------------------------------------
    symbol_map = {}
    for cid, comp in all_components.items():
        if comp.language == "javascript":
            name = cid.split(".")[-1]
            symbol_map.setdefault(name, []).append(cid)

    # --------------------------------------------------
    # Collect imports: local_name -> module_path
    # --------------------------------------------------
    import_aliases = {}

    def collect_imports(node):
        if node.type == "import_statement":
            source_node = node.child_by_field_name("source")
            if not source_node:
                return

            module = source_node.text.decode().strip("\"'")

            # Ignore assets
            if module.endswith(JS_ASSET_EXTENSIONS):
                return

            # Ignore externals
            if not module.startswith(".") and module in EXTERNAL_MODULES:
                return

            for child in node.children:
                if child.type == "import_clause":
                    for spec in child.children:
                        # import { A as B }
                        if spec.type == "import_specifier":
                            local = spec.child_by_field_name("name")
                            if local:
                                import_aliases[local.text.decode()] = module

                        # import A from "./x"
                        elif spec.type == "identifier":
                            import_aliases[spec.text.decode()] = module

        for c in node.children:
            collect_imports(c)

    collect_imports(tree.root_node)

    # --------------------------------------------------
    # Resolve relative import → module_path
    # --------------------------------------------------
    def resolve_module(module):
        if not module.startswith("."):
            return None

        # Use getattr for safe access to module_path
        comp_module_path = getattr(component, 'module_path', '')
        if not comp_module_path:
            return None
            
        base = comp_module_path.split(".")[:-1]
        for part in module.split("/"):
            if part == "..":
                if base:
                    base.pop()
            elif part != ".":
                base.append(part)

        return ".".join(base)

    # --------------------------------------------------
    # Test module detection
    # --------------------------------------------------
    def is_test_module(path: str) -> bool:
        if not path:
            return False
        return (
            ".test" in path
            or path.endswith(".test")
            or "/test" in path
            or "\\test" in path
        )

    # --------------------------------------------------
    # Locate component AST node
    # --------------------------------------------------
    def find_component_node(node):
        comp_type = getattr(component, 'type', None)
        comp_id = getattr(component, 'id', '')
        
        if not comp_type or not comp_id:
            return None
        
        # Convert ComponentType enum to string if needed
        type_str = comp_type.value if hasattr(comp_type, 'value') else str(comp_type)
        
        # Regular function declaration
        if type_str == "function" and node.type == "function_declaration":
            name = node.child_by_field_name("name")
            if name and comp_id.endswith(name.text.decode()):
                return node
        
        # Arrow function: const foo = () => {}
        if type_str == "function" and node.type == "variable_declarator":
            name = node.child_by_field_name("name")
            value = node.child_by_field_name("value")
            if name and value and value.type == "arrow_function":
                if comp_id.endswith(name.text.decode()):
                    return value  # Return the arrow_function node

        # Class declaration
        if type_str == "class" and node.type == "class_declaration":
            name = node.child_by_field_name("name")
            if name and comp_id.endswith(name.text.decode()):
                return node

        # Method definition
        if type_str == "method" and node.type == "method_definition":
            name = node.child_by_field_name("name")
            if name and comp_id.endswith(name.text.decode()):
                return node

        # Recursively search children
        for c in node.children:
            found = find_component_node(c)
            if found:
                return found
        return None

    component_node = find_component_node(tree.root_node)
    if not component_node:
        return deps

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def is_local_identifier(node):
        parent = getattr(node, "parent", None)
        if not parent:
            return False

        return parent.type in {
            "formal_parameters",
            "variable_declarator",
            "property_identifier",
            "member_expression",
            "object_pattern",
            "array_pattern",
        }

    # --------------------------------------------------
    # Walk ONLY component body
    # --------------------------------------------------
    def walk(node):

        # -------- function calls: foo() --------
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")

            if fn and fn.type == "identifier":
                name = fn.text.decode()
                if name in symbol_map:
                    for cid in symbol_map[name]:
                        deps.add(cid)

            elif fn and fn.type == "member_expression":
                prop = fn.child_by_field_name("property")
                if prop:
                    name = prop.text.decode()
                    if name in symbol_map:
                        for cid in symbol_map[name]:
                            deps.add(cid)

        # -------- new Class() --------
        if node.type == "new_expression":
            ctor = node.child_by_field_name("constructor")
            if ctor and ctor.type == "identifier":
                name = ctor.text.decode()
                if name in symbol_map:
                    for cid in symbol_map[name]:
                        deps.add(cid)

        # -------- JSX: <Component /> --------
        if node.type == "jsx_opening_element":
            name_node = node.child_by_field_name("name")
            if name_node and name_node.type == "identifier":
                name = name_node.text.decode()
                if name in symbol_map:
                    for cid in symbol_map[name]:
                        deps.add(cid)

        # -------- imported symbol usage --------
        if node.type == "identifier" and not is_local_identifier(node):
            name = node.text.decode()
            if name in import_aliases:
                module = import_aliases[name]
                resolved = resolve_module(module)
                if resolved:
                    candidate = f"{resolved}.{name}"
                    if candidate in all_components:
                        deps.add(candidate)

        for c in node.children:
            walk(c)

    walk(component_node)

    # --------------------------------------------------
    # Final cleanup (DAG-safe)
    # --------------------------------------------------
    cleaned = set()
    comp_id = getattr(component, 'id', '')
    comp_module_path = getattr(component, 'module_path', '')
    
    for d in deps:
        if d == comp_id:
            continue

        # Prevent prod → test
        dep_comp = all_components.get(d)
        if dep_comp:
            dep_module_path = getattr(dep_comp, 'module_path', '')
            if (
                not is_test_module(comp_module_path)
                and is_test_module(dep_module_path)
            ):
                continue

        cleaned.add(d)

    return cleaned