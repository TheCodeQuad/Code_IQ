# languages/java/dependencies.py

"""
Java Dependency Resolver for DocAgent

Resolves dependencies between Java components:
1. Method calls (direct invocations)
2. Field usage
3. Type dependencies (parameters, return types, fields)
4. Inheritance relationships
5. Annotation usage
6. Inner class relationships

Optimized for documentation generation workflow.
"""

JAVA_STANDARD_LIBS = {
    "java.lang", "java.util", "java.io", "java.nio",
    "java.net", "java.sql", "java.math", "java.time",
    "java.concurrent", "java.security", "java.text",
    "javax", "org.w3c", "org.xml",
}


def resolve_dependencies(component, tree, source, all_components):
    """
    Resolve all dependencies for a Java component.
    
    Returns: Set of component IDs that this component depends on
    
    Dependency types detected:
    1. Method invocations (calls other methods)
    2. Field access (uses fields from other classes)
    3. Type usage (parameters, return types, field types)
    4. Inheritance (extends/implements)
    5. Constructor calls (new ClassName())
    6. Annotations (custom annotations)
    """
    
    deps = set()
    
    # --------------------------------------------------
    # Build symbol table: Name -> [component_ids]
    # --------------------------------------------------
    symbol_map = {}
    class_map = {}  # Maps class names to class IDs
    method_map = {}  # Maps method names to method IDs (with class context)
    
    for cid, comp in all_components.items():
        if comp.language == "java":
            name = cid.split(".")[-1]
            symbol_map.setdefault(name, []).append(cid)
            
            # Build class map
            if comp.type.value == "class":
                class_map[comp.name] = cid
            
            # Build method map with class context
            if comp.type.value in ("method", "constructor"):
                parts = cid.split(".")
                if len(parts) >= 2:
                    class_name = parts[-2]
                    method_map.setdefault(name, []).append((class_name, cid))
    
    # --------------------------------------------------
    # Extract package info
    # --------------------------------------------------
    def get_package(comp_id):
        """Get package name from component ID"""
        parts = comp_id.split(".")
        # Typically: com.example.package.ClassName.methodName
        # Package is everything except last 2 parts (class.method)
        if len(parts) > 2:
            return ".".join(parts[:-2])
        return parts[0] if parts else ""
    
    current_package = get_package(component.id)
    
    # --------------------------------------------------
    # Import resolution
    # --------------------------------------------------
    import_map = {}  # Simple name -> Full qualified name
    
    if hasattr(component, 'imports') and component.imports:
        for imp in component.imports:
            # Parse: import java.util.ArrayList;
            # or: import static com.example.Utils.helper;
            imp_clean = imp.strip().replace("import", "").replace("static", "").replace(";", "").strip()
            
            if "*" not in imp_clean:  # Skip wildcard imports
                parts = imp_clean.split(".")
                simple_name = parts[-1]
                import_map[simple_name] = imp_clean
    
    # --------------------------------------------------
    # Locate component AST node
    # --------------------------------------------------
    def find_component_node(node, comp_id, comp_type):
        """Find the AST node for this component"""
        type_str = comp_type.value if hasattr(comp_type, 'value') else str(comp_type)
        
        if type_str == "class":
            if node.type in ("class_declaration", "interface_declaration"):
                name_node = node.child_by_field_name("name")
                if name_node and comp_id.endswith(name_node.text.decode()):
                    return node
        
        elif type_str == "method":
            if node.type == "method_declaration":
                name_node = node.child_by_field_name("name")
                if name_node and comp_id.endswith(name_node.text.decode()):
                    return node
        
        elif type_str == "constructor":
            if node.type == "constructor_declaration":
                return node
        
        elif type_str in ("field", "static_field"):
            if node.type == "field_declaration":
                for child in node.children:
                    if child.type == "variable_declarator":
                        name_node = child.child_by_field_name("name")
                        if name_node and comp_id.endswith(name_node.text.decode()):
                            return node
        
        # Recursively search
        for child in node.children:
            found = find_component_node(child, comp_id, comp_type)
            if found:
                return found
        
        return None
    
    component_node = find_component_node(
        tree.root_node, 
        component.id, 
        component.type
    )
    
    if not component_node:
        return deps
    
    # --------------------------------------------------
    # Dependency Type 1: Inheritance (parent classes/interfaces)
    # --------------------------------------------------
    if hasattr(component, 'parent_classes') and component.parent_classes:
        for parent_name in component.parent_classes:
            # Try to resolve to a component
            if parent_name in class_map:
                deps.add(class_map[parent_name])
            elif parent_name in symbol_map:
                for cid in symbol_map[parent_name]:
                    if all_components[cid].type.value == "class":
                        deps.add(cid)
    
    # --------------------------------------------------
    # Dependency Type 2: Method calls
    # --------------------------------------------------
    def extract_method_invocations(node):
        """Extract all method calls within the component"""
        method_calls = set()
        
        def walk(n):
            if n.type == "method_invocation":
                # Get method name
                method_name_node = n.child_by_field_name("name")
                if method_name_node:
                    method_name = method_name_node.text.decode()
                    
                    # Get object (if present) for qualified calls
                    object_node = n.child_by_field_name("object")
                    
                    if object_node:
                        obj_text = object_node.text.decode()
                        
                        # Check if it's a field reference (e.g., servlet.doGet)
                        # The object could be 'servlet', 'this.servlet', etc.
                        obj_parts = obj_text.split('.')
                        base_obj = obj_parts[0]  # Get the base object name
                        
                        # Check if it's a class name (static call)
                        if obj_text in class_map:
                            target_class_id = class_map[obj_text]
                            method_calls.add((obj_text, method_name, target_class_id))
                        # Check if base object is a field in current class
                        else:
                            method_calls.add((base_obj, method_name, None))
                    else:
                        # Unqualified call: methodName() - same class
                        method_calls.add((None, method_name, None))
            
            for child in n.children:
                walk(child)
        
        walk(node)
        return method_calls
    
    method_invocations = extract_method_invocations(component_node)
    
    for class_context, method_name, class_id in method_invocations:
        if class_id:
            # We know the class - find the method in that class
            for cid in all_components.keys():
                if cid.startswith(class_id + ".") and cid.endswith("." + method_name):
                    deps.add(cid)
        elif class_context:
            # We have a field/object context - try to resolve its type
            # Look for a field with this name in the current class
            parts = component.id.split(".")
            if len(parts) >= 2:
                current_class = ".".join(parts[:-1])
                
                # Check if there's a field with this name in current class
                field_id = f"{current_class}.{class_context}"
                if field_id in all_components:
                    field_comp = all_components[field_id]
                    # Get the type of the field
                    if hasattr(field_comp, 'return_type') and field_comp.return_type:
                        field_type = field_comp.return_type
                        # Find the class for this type
                        if field_type in class_map:
                            target_class_id = class_map[field_type]
                            # Find the method in that class
                            for cid in all_components.keys():
                                if cid.startswith(target_class_id + ".") and cid.endswith("." + method_name):
                                    deps.add(cid)
                else:
                    # Fallback: search by method name in same package
                    for cid in all_components.keys():
                        if cid.endswith("." + method_name):
                            comp = all_components[cid]
                            if comp.type.value in ("method", "constructor"):
                                deps.add(cid)
        else:
            # Unqualified - search in current class
            parts = component.id.split(".")
            if len(parts) >= 2:
                current_class = ".".join(parts[:-1])
                # Check methods in same class
                for cid in all_components.keys():
                    if cid.startswith(current_class + ".") and cid.endswith("." + method_name):
                        comp = all_components[cid]
                        if comp.type.value in ("method", "constructor"):
                            deps.add(cid)
    
    # --------------------------------------------------
    # Dependency Type 3: Field access
    # --------------------------------------------------
    def extract_field_access(node):
        """Extract field accesses"""
        fields = set()
        
        def walk(n):
            if n.type == "field_access":
                field_node = n.child_by_field_name("field")
                object_node = n.child_by_field_name("object")
                
                if field_node:
                    field_name = field_node.text.decode()
                    
                    if object_node:
                        obj_text = object_node.text.decode()
                        if obj_text in class_map:
                            fields.add((obj_text, field_name, class_map[obj_text]))
                        else:
                            fields.add((None, field_name, None))
                    else:
                        fields.add((None, field_name, None))
            
            for child in n.children:
                walk(child)
        
        walk(node)
        return fields
    
    field_accesses = extract_field_access(component_node)
    
    for class_context, field_name, class_id in field_accesses:
        if class_id:
            # Find field in specific class
            for cid in all_components.keys():
                if cid.startswith(class_id + ".") and cid.endswith("." + field_name):
                    comp = all_components[cid]
                    if comp.type.value in ("field", "static_field"):
                        deps.add(cid)
        else:
            # Find field in current class or parent
            parts = component.id.split(".")
            if len(parts) >= 2:
                current_class = ".".join(parts[:-1])
                for cid in all_components.keys():
                    if cid.startswith(current_class + ".") and cid.endswith("." + field_name):
                        comp = all_components[cid]
                        if comp.type.value in ("field", "static_field"):
                            deps.add(cid)
    
    # --------------------------------------------------
    # Dependency Type 4: Constructor calls (new ClassName())
    # --------------------------------------------------
    def extract_object_creation(node):
        """Extract 'new ClassName()' expressions"""
        classes = set()
        
        def walk(n):
            if n.type == "object_creation_expression":
                type_node = n.child_by_field_name("type")
                if type_node:
                    class_name = type_node.text.decode()
                    classes.add(class_name)
            
            for child in n.children:
                walk(child)
        
        walk(node)
        return classes
    
    created_objects = extract_object_creation(component_node)
    
    for class_name in created_objects:
        if class_name in class_map:
            class_id = class_map[class_name]
            deps.add(class_id)
            
            # Also add dependency on constructor
            constructor_id = f"{class_id}.<init>"
            if constructor_id in all_components:
                deps.add(constructor_id)
    
    # --------------------------------------------------
    # Dependency Type 5: Type usage (parameters, return types, fields)
    # --------------------------------------------------
    def extract_type_dependencies():
        """Extract dependencies from type declarations"""
        type_deps = set()
        
        # From parameters
        if hasattr(component, 'parameters'):
            for param in component.parameters:
                if param.type_hint:
                    type_name = param.type_hint.split("<")[0].strip()  # Remove generics
                    if type_name in class_map:
                        type_deps.add(class_map[type_name])
        
        # From return type
        if hasattr(component, 'return_type') and component.return_type:
            type_name = component.return_type.split("<")[0].strip()
            if type_name in class_map:
                type_deps.add(class_map[type_name])
        
        return type_deps
    
    deps.update(extract_type_dependencies())
    
    # --------------------------------------------------
    # Dependency Type 6: Annotations (custom annotations)
    # --------------------------------------------------
    if hasattr(component, 'decorators') and component.decorators:
        for annotation in component.decorators:
            # Parse @AnnotationName or @package.AnnotationName
            ann_text = annotation.strip("@").split("(")[0]
            
            # Check if it's a custom annotation (not standard Java)
            if not ann_text.startswith(("Override", "Deprecated", "SuppressWarnings")):
                if ann_text in class_map:
                    deps.add(class_map[ann_text])
    
    # --------------------------------------------------
    # Final cleanup
    # --------------------------------------------------
    cleaned = set()
    comp_id = component.id
    
    for dep_id in deps:
        # Don't depend on self
        if dep_id == comp_id:
            continue
        
        # Don't depend on standard library
        dep_package = get_package(dep_id)
        if any(dep_package.startswith(std_lib) for std_lib in JAVA_STANDARD_LIBS):
            continue
        
        # Don't create circular dependencies (A.method -> A.field)
        # Methods/fields should not depend on their parent class
        parts = comp_id.split(".")
        dep_parts = dep_id.split(".")
        
        if len(parts) > 1 and len(dep_parts) > 1:
            # If this is a method/field and dep is its parent class, skip
            comp_class = ".".join(parts[:-1])
            if dep_id == comp_class:
                continue
        
        cleaned.add(dep_id)
    
    return cleaned