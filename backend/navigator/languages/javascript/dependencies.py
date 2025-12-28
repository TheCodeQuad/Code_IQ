def resolve_dependencies(component, tree, source, all_components):
    deps = set()

    # Map last-name → full-id (JS only)
    name_map = {
        c.id.split(".")[-1]: c.id
        for c in all_components.values()
        if c.language == "javascript"
    }

    def walk(node):

        # ---------------------------------
        # Function call: foo()
        # ---------------------------------
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")

            # foo()
            if fn and fn.type == "identifier":
                name = fn.text.decode()
                if name in name_map:
                    target = name_map[name]
                    if target != component.id:
                        deps.add(target)

            # obj.method()
            elif fn and fn.type == "member_expression":
                prop = fn.child_by_field_name("property")
                if prop:
                    name = prop.text.decode()
                    if name in name_map:
                        target = name_map[name]
                        if target != component.id:
                            deps.add(target)

        # ---------------------------------
        # Constructor call: new ClassName()
        # ---------------------------------
        if node.type == "new_expression":
            ctor = node.child_by_field_name("constructor")
            if ctor and ctor.type == "identifier":
                name = ctor.text.decode()
                if name in name_map:
                    target = name_map[name]
                    if target != component.id:
                        deps.add(target)

        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return deps
