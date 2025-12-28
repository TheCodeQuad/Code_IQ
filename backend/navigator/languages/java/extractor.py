from core.ir import CodeComponent

def extract_components(tree, source, file_path, module_path):
    comps = []
    for node in tree.root_node.children:
        if node.type == "class_declaration":
            cname = node.child_by_field_name("name").text.decode()
            cid = f"{module_path}.{cname}"
            comps.append(CodeComponent(
                cid, "java", "class",
                file_path, module_path,
                node.start_point[0]+1, node.end_point[0]+1,
                source
            ))

            for ch in node.children:
                if ch.type == "method_declaration":
                    mname = ch.child_by_field_name("name").text.decode()
                    comps.append(CodeComponent(
                        f"{cid}.{mname}", "java", "method",
                        file_path, module_path,
                        ch.start_point[0]+1, ch.end_point[0]+1,
                        source
                    ))
    return comps
