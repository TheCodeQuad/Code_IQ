def resolve_dependencies(component, tree, source, all_components):
    deps = set()

    # Map function name → component id (JS + TS)
    name_map = {
        c.id.split(".")[-1]: c.id
        for c in all_components.values()
        if c.language in ("javascript", "typescript")
    }

    def walk(node):
        # function call: bar()
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")

            # bar()
            if fn and fn.type == "identifier":
                name = fn.text.decode()
                if name in name_map:
                    target = name_map[name]
                    if target != component.id:
                        deps.add(target)

        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return deps
