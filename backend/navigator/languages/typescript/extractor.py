from core.ir import CodeComponent

def extract_components(tree, source, file_path, module_path):
    comps = []
    for node in tree.root_node.children:
        if node.type == "function_declaration":
            name = node.child_by_field_name("name").text.decode()
            comps.append(CodeComponent(
                f"{module_path}.{name}", "javascript", "function",
                file_path, module_path,
                node.start_point[0]+1, node.end_point[0]+1,
                source
            ))
        elif node.type == "class_declaration":
            name = node.child_by_field_name("name").text.decode()
            comps.append(CodeComponent(
                f"{module_path}.{name}", "javascript", "class",
                file_path, module_path,
                node.start_point[0]+1, node.end_point[0]+1,
                source
            ))
    return comps
