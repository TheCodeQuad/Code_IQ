"""
Java Dependency Resolver for DocAgent

Resolves SEMANTIC dependencies between Java components for documentation.

CRITICAL DocAgent Rules:
1. Local variables → IGNORED (not stable semantic dependencies)
2. Overloaded methods → Collapse to CLASS-level (ambiguous resolution)
3. this.method() → IGNORED (internal, not cross-component)
4. Static calls → CLASS-level (Utils.helper → depends on Utils class)
5. Constructor calls → CLASS-level dependency
6. Inheritance → CLASS-level
7. Imports → Used for type resolution only
8. Stdlib exclusion → Filter standard Java libraries
9. Field access → CLASS-level (not field-level for static/foreign classes)

Philosophy: Documentation dependencies are COARSER than compiler dependencies.
"""

import re

JAVA_STANDARD_LIBS = {
    "java.lang", "java.util", "java.io", "java.nio",
    "java.net", "java.sql", "java.math", "java.time",
    "java.concurrent", "java.security", "java.text",
    "javax", "org.w3c", "org.xml",
}


def resolve_dependencies(component, tree, source, all_components):
    """
    Resolve SEMANTIC dependencies for a Java component (DocAgent-compliant).
    
    Returns: Set of component IDs that this component depends on
    
    Key semantic rules:
    - Methods depend on OTHER CLASSES they use
    - Methods do NOT depend on methods in same class (that's internal)
    - Ambiguous resolution → collapse to class
    - Type-level dependencies only (no local variables)
    """
    
    deps = set()
    
    # --------------------------------------------------
    # Helper functions
    # --------------------------------------------------
    def get_package(comp_id):
        """Get package name from component ID"""
        parts = comp_id.split(".")
        if len(parts) > 2:
            return ".".join(parts[:-2])
        return parts[0] if parts else ""
    
    def extract_type_names(type_text):
        """
        Extract all type names from a type declaration, including generics.
        e.g., "List<Map<String, CustomClass>>" -> ["List", "Map", "String", "CustomClass"]
        """
        if not type_text:
            return []
        
        # Remove array brackets
        type_text = type_text.replace("[]", "")
        
        # Extract all identifiers (including generic parameters)
        pattern = r'\b([A-Z][a-zA-Z0-9_]*(?:\.[A-Z][a-zA-Z0-9_]*)*)\b'
        matches = re.findall(pattern, type_text)
        
        return matches
    
    def get_class_id_from_component_id(comp_id):
        """
        Extract the class ID from a component ID.
        e.g., "com.example.MyClass.myMethod" -> "com.example.MyClass"
        """
        parts = comp_id.split(".")
        if len(parts) >= 2:
            # Last part is method/field name, second-to-last is class name
            return ".".join(parts[:-1])
        return comp_id
    
    # --------------------------------------------------
    # Build symbol tables
    # --------------------------------------------------
    class_map = {}  # Maps simple class name -> class ID
    
    for cid, comp in all_components.items():
        if comp.language == "java":
            # Build class map
            if comp.type.value == "class":
                class_map[comp.name] = cid
    
    current_package = get_package(component.id)
    current_class_id = get_class_id_from_component_id(component.id)
    
    # --------------------------------------------------
    # Import resolution
    # --------------------------------------------------
    import_map = {}  # Simple name -> Full qualified name
    static_import_map = {}  # Simple name -> Full qualified name
    
    if hasattr(component, 'imports') and component.imports:
        for imp in component.imports:
            imp_clean = imp.strip().replace("import", "").replace("static", "").replace(";", "").strip()
            is_static = "static" in imp
            
            if "*" not in imp_clean:  # Skip wildcard imports
                parts = imp_clean.split(".")
                simple_name = parts[-1]
                
                if is_static:
                    # For static imports, the class is everything except the last part
                    class_name = ".".join(parts[:-1])
                    static_import_map[simple_name] = class_name
                else:
                    import_map[simple_name] = imp_clean
    
    # --------------------------------------------------
    # Locate component AST node
    # --------------------------------------------------
    def find_component_node(node, comp_id, comp_type):
        """Find the AST node for this component"""
        type_str = comp_type.value if hasattr(comp_type, 'value') else str(comp_type)
        
        if type_str == "class":
            if node.type in ("class_declaration", "interface_declaration", "enum_declaration"):
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
    
    def resolve_type_name(type_name):
        """Resolve a simple type name to a CLASS ID using imports"""
        # Check if already fully qualified
        if "." in type_name:
            # Try to find the class in our class_map
            for simple_name, class_id in class_map.items():
                if class_id == type_name or class_id.endswith("." + type_name):
                    return class_id
        
        # Check imports
        if type_name in import_map:
            full_name = import_map[type_name]
            # Find matching class
            for simple_name, class_id in class_map.items():
                if class_id == full_name or class_id.endswith("." + type_name):
                    return class_id
        
        # Check same package
        same_package_name = f"{current_package}.{type_name}"
        if same_package_name in class_map.values():
            return same_package_name
        
        # Check by simple name
        if type_name in class_map:
            return class_map[type_name]
        
        return None
    
    # --------------------------------------------------
    # Rule 1: Inheritance → CLASS-level dependencies
    # --------------------------------------------------
    if hasattr(component, 'parent_classes') and component.parent_classes:
        for parent_name in component.parent_classes:
            resolved_id = resolve_type_name(parent_name)
            if resolved_id:
                deps.add(resolved_id)
    
    # --------------------------------------------------
    # Rule 2: Method calls → CLASS-level dependencies ONLY
    # DocAgent rule: If ambiguous (overloading), use class. Always safer.
    # --------------------------------------------------
    def extract_method_invocations(node):
        """Extract all method calls and return the TARGET CLASSES"""
        target_classes = set()
        
        def walk(n):
            if n.type == "method_invocation":
                method_name_node = n.child_by_field_name("name")
                if not method_name_node:
                    for child in n.children:
                        walk(child)
                    return
                
                method_name = method_name_node.text.decode()
                object_node = n.child_by_field_name("object")
                
                if object_node:
                    obj_text = object_node.text.decode()
                    
                    # Ignore this.method() - internal behavior
                    if obj_text == "this":
                        for child in n.children:
                            walk(child)
                        return
                    
                    # super.method() → parent class dependency
                    if obj_text == "super":
                        if hasattr(component, 'parent_classes') and component.parent_classes:
                            for parent_name in component.parent_classes:
                                resolved_id = resolve_type_name(parent_name)
                                if resolved_id:
                                    target_classes.add(resolved_id)
                        for child in n.children:
                            walk(child)
                        return
                    
                    # Static call: ClassName.method() → CLASS dependency
                    if obj_text in class_map:
                        target_classes.add(class_map[obj_text])
                        for child in n.children:
                            walk(child)
                        return
                    
                    # Field/variable call: field.method() → resolve field type → CLASS
                    # Look for field in current class
                    parts = component.id.split(".")
                    if len(parts) >= 2:
                        current_class = ".".join(parts[:-1])
                        obj_parts = obj_text.split('.')
                        base_obj = obj_parts[0]
                        
                        # Check if there's a field with this name
                        field_id = f"{current_class}.{base_obj}"
                        if field_id in all_components:
                            field_comp = all_components[field_id]
                            if hasattr(field_comp, 'return_type') and field_comp.return_type:
                                field_type = field_comp.return_type.split("<")[0].strip()
                                resolved_id = resolve_type_name(field_type)
                                if resolved_id:
                                    target_classes.add(resolved_id)
                else:
                    # Unqualified call: method()
                    # Check if it's a static import
                    if method_name in static_import_map:
                        # Static import → CLASS dependency
                        class_name = static_import_map[method_name]
                        resolved_id = resolve_type_name(class_name)
                        if resolved_id:
                            target_classes.add(resolved_id)
                    # Otherwise it's a call to same class - IGNORE (internal)
            
            for child in n.children:
                walk(child)
        
        walk(node)
        return target_classes
    
    target_classes = extract_method_invocations(component_node)
    deps.update(target_classes)
    
    # --------------------------------------------------
    # Rule 3: Field access → CLASS-level dependencies
    # --------------------------------------------------
    def extract_field_access(node):
        """Extract field accesses and return TARGET CLASSES"""
        target_classes = set()
        
        def walk(n):
            if n.type == "field_access":
                field_node = n.child_by_field_name("field")
                object_node = n.child_by_field_name("object")
                
                if field_node and object_node:
                    obj_text = object_node.text.decode()
                    
                    # Ignore this.field - internal
                    if obj_text == "this":
                        for child in n.children:
                            walk(child)
                        return
                    
                    # super.field → parent class
                    if obj_text == "super":
                        if hasattr(component, 'parent_classes') and component.parent_classes:
                            for parent_name in component.parent_classes:
                                resolved_id = resolve_type_name(parent_name)
                                if resolved_id:
                                    target_classes.add(resolved_id)
                        for child in n.children:
                            walk(child)
                        return
                    
                    # Static field: ClassName.FIELD → CLASS dependency
                    if obj_text in class_map:
                        target_classes.add(class_map[obj_text])
            
            for child in n.children:
                walk(child)
        
        walk(node)
        return target_classes
    
    target_classes = extract_field_access(component_node)
    deps.update(target_classes)
    
    # --------------------------------------------------
    # Rule 4: Constructor calls → CLASS-level dependencies
    # --------------------------------------------------
    def extract_object_creation(node):
        """Extract 'new ClassName()' and return CLASS IDs"""
        target_classes = set()
        
        def walk(n):
            if n.type == "object_creation_expression":
                type_node = n.child_by_field_name("type")
                if type_node:
                    class_name = type_node.text.decode()
                    # Handle generics: new ArrayList<String>()
                    class_name = class_name.split("<")[0].strip()
                    resolved_id = resolve_type_name(class_name)
                    if resolved_id:
                        target_classes.add(resolved_id)
            
            for child in n.children:
                walk(child)
        
        walk(node)
        return target_classes
    
    target_classes = extract_object_creation(component_node)
    deps.update(target_classes)
    
    # --------------------------------------------------
    # Rule 5: Type usage (parameters, return types, fields)
    # NOTE: LOCAL VARIABLES EXCLUDED per DocAgent rule
    # --------------------------------------------------
    def extract_type_dependencies():
        """Extract dependencies from type declarations (NO local vars)"""
        type_deps = set()
        
        # From parameters
        if hasattr(component, 'parameters') and component.parameters:
            for param in component.parameters:
                if param.type_hint:
                    type_names = extract_type_names(param.type_hint)
                    for type_name in type_names:
                        resolved_id = resolve_type_name(type_name)
                        if resolved_id:
                            type_deps.add(resolved_id)
        
        # From return type
        if hasattr(component, 'return_type') and component.return_type:
            type_names = extract_type_names(component.return_type)
            for type_name in type_names:
                resolved_id = resolve_type_name(type_name)
                if resolved_id:
                    type_deps.add(resolved_id)
        
        # From field type (if this is a field component)
        if component.type.value in ("field", "static_field"):
            if hasattr(component, 'return_type') and component.return_type:
                type_names = extract_type_names(component.return_type)
                for type_name in type_names:
                    resolved_id = resolve_type_name(type_name)
                    if resolved_id:
                        type_deps.add(resolved_id)
        
        return type_deps
    
    deps.update(extract_type_dependencies())
    
    # --------------------------------------------------
    # Rule 6: Exception types (catch/throw)
    # --------------------------------------------------
    def extract_exception_types(node):
        """Extract exception type dependencies"""
        target_classes = set()
        
        def walk(n):
            # catch blocks
            if n.type == "catch_clause":
                type_node = n.child_by_field_name("type")
                if type_node:
                    exc_type = type_node.text.decode()
                    resolved_id = resolve_type_name(exc_type)
                    if resolved_id:
                        target_classes.add(resolved_id)
            
            # throws declarations
            if n.type == "throws":
                for child in n.children:
                    if child.type == "type_identifier":
                        exc_type = child.text.decode()
                        resolved_id = resolve_type_name(exc_type)
                        if resolved_id:
                            target_classes.add(resolved_id)
            
            # throw statements
            if n.type == "throw_statement":
                for child in n.children:
                    if child.type == "object_creation_expression":
                        type_node = child.child_by_field_name("type")
                        if type_node:
                            exc_type = type_node.text.decode()
                            resolved_id = resolve_type_name(exc_type)
                            if resolved_id:
                                target_classes.add(resolved_id)
            
            for child in n.children:
                walk(child)
        
        walk(node)
        return target_classes
    
    target_classes = extract_exception_types(component_node)
    deps.update(target_classes)
    
    # --------------------------------------------------
    # Rule 7: Annotations (custom annotations)
    # --------------------------------------------------
    if hasattr(component, 'decorators') and component.decorators:
        for annotation in component.decorators:
            # Parse @AnnotationName or @package.AnnotationName
            ann_text = annotation.strip("@").split("(")[0]
            
            # Skip standard Java annotations
            if not ann_text.startswith(("Override", "Deprecated", "SuppressWarnings", "FunctionalInterface")):
                resolved_id = resolve_type_name(ann_text)
                if resolved_id:
                    deps.add(resolved_id)
    
    # --------------------------------------------------
    # Rule 8: Cast expressions
    # --------------------------------------------------
    def extract_cast_types(node):
        """Extract types from cast expressions"""
        target_classes = set()
        
        def walk(n):
            if n.type == "cast_expression":
                type_node = n.child_by_field_name("type")
                if type_node:
                    cast_type = type_node.text.decode()
                    type_names = extract_type_names(cast_type)
                    for type_name in type_names:
                        resolved_id = resolve_type_name(type_name)
                        if resolved_id:
                            target_classes.add(resolved_id)
            
            for child in n.children:
                walk(child)
        
        walk(node)
        return target_classes
    
    target_classes = extract_cast_types(component_node)
    deps.update(target_classes)
    
    # --------------------------------------------------
    # Final cleanup
    # --------------------------------------------------
    cleaned = set()
    comp_id = component.id
    
    for dep_id in deps:
        # Don't depend on self
        if dep_id == comp_id:
            continue
        
        # Don't depend on same class (internal dependencies)
        if dep_id == current_class_id:
            continue
        
        # Don't depend on standard library
        dep_package = get_package(dep_id)
        if any(dep_package.startswith(std_lib) for std_lib in JAVA_STANDARD_LIBS):
            continue
        
        # Only class-level dependencies allowed
        # Make sure we're not accidentally adding method/field IDs
        if dep_id in all_components:
            dep_comp = all_components[dep_id]
            if dep_comp.type.value == "class":
                cleaned.add(dep_id)
    
    return cleaned