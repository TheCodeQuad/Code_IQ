def resolve_dependencies(component, tree, source, all_components):
    deps = set()

    # Map function/method name -> component id (JS + TS)
    name_map = {}
    for c in all_components.values():
        if c.language in ("javascript", "typescript"):
            short_name = c.id.split(".")[-1]
            name_map.setdefault(short_name, []).append(c.id)

    stack = [tree.root_node]

    while stack:
        node = stack.pop()

        # function call: bar(), this.bar(), obj.bar()
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")

            if fn:
                # bar()
                if fn.type == "identifier":
                    name = fn.text.decode()
                    for target in name_map.get(name, []):
                        if target != component.id:
                            deps.add(target)

                # this.bar() or obj.bar()
                elif fn.type == "member_expression":
                    prop = fn.child_by_field_name("property")
                    if prop:
                        method_name = prop.text.decode()
                        for target in name_map.get(method_name, []):
                            if target != component.id:
                                deps.add(target)

                    obj = fn.child_by_field_name("object")
                    if obj and obj.type == "identifier":
                        obj_name = obj.text.decode()
                        for target in name_map.get(obj_name, []):
                            if target != component.id:
                                deps.add(target)

        for child in node.children:
            stack.append(child)
    return deps
