from core.ir import CodeComponent

def extract_components(tree, source, file_path, module_path):
    components = []
    root = tree.root_node

    def walk(node):

        # -------------------------------
        # FUNCTION
        # -------------------------------
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
                components.append(CodeComponent(
                    id=f"{module_path}.{name}",
                    language="javascript",
                    type="function",
                    file_path=file_path,
                    module_path=module_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    source_code=source
                ))

        # -------------------------------
        # CLASS
        # -------------------------------
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                class_name = name_node.text.decode()
                class_id = f"{module_path}.{class_name}"

                components.append(CodeComponent(
                    id=class_id,
                    language="javascript",
                    type="class",
                    file_path=file_path,
                    module_path=module_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    source_code=source
                ))

                # METHODS
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        if child.type == "method_definition":
                            key = child.child_by_field_name("name")
                            if key:
                                method_name = key.text.decode()
                                components.append(CodeComponent(
                                    id=f"{class_id}.{method_name}",
                                    language="javascript",
                                    type="method",
                                    file_path=file_path,
                                    module_path=module_path,
                                    start_line=child.start_point[0] + 1,
                                    end_line=child.end_point[0] + 1,
                                    source_code=source
                                ))

        for child in node.children:
            walk(child)

    walk(root)
    return components
