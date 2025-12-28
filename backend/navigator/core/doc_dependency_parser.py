def apply_doc_dependency_rules(components):
    """
    Apply documentation-oriented dependency abstraction rules.
    
    This simplifies dependencies for documentation purposes by:
    1. Rolling up method-level deps to class-level for external dependencies
    2. Removing redundant internal dependencies
    3. Hiding orchestrator methods that only coordinate class-level collaborators
    4. Handling global variables appropriately
    
    Args:
        components: Dict[str, CodeComponent] mapping component IDs to components
    """

    # ==================================================
    # PASS 1: CLEAN CLASS-LEVEL DEPENDENCIES
    # ==================================================
    # Classes should depend on other classes, not individual methods
    for comp in components.values():
        if comp.type != "class":
            continue

        new_deps = set()

        for dep in comp.depends_on:
            # Skip self-dependency
            if dep == comp.id:
                continue

            # Keep own methods (these are contained within the class)
            if dep.startswith(comp.id + "."):
                new_deps.add(dep)
                continue

            # Keep global variables as-is
            dep_comp = components.get(dep)
            if dep_comp and dep_comp.type == "global_variable":
                new_deps.add(dep)
                continue

            # For external class methods, depend on the class instead
            dep_parts = dep.split(".")
            if len(dep_parts) >= 2:
                owner = ".".join(dep_parts[:-1])
                if owner in components and components[owner].type == "class":
                    # This is a method of another class -> depend on the class
                    new_deps.add(owner)
                    continue

            # Keep other dependencies as-is
            new_deps.add(dep)

        comp.depends_on = new_deps

    # ==================================================
    # PASS 2: CLEAN METHOD / FUNCTION DEPENDENCIES
    # ==================================================
    # Methods and functions should depend on classes, not individual methods
    # BUT they should keep global variable dependencies
    for comp in components.values():
        if comp.type not in ("method", "function"):
            continue

        # Determine parent class for methods
        self_class = None
        if comp.type == "method":
            comp_parts = comp.id.split(".")
            if len(comp_parts) >= 2:
                self_class = ".".join(comp_parts[:-1])

        new_deps = set()

        for dep in comp.depends_on:
            # Skip self-class dependency (methods don't need to depend on their own class)
            if self_class and dep == self_class:
                continue

            # Skip private helper methods within same class
            if self_class and dep.startswith(self_class + "._"):
                continue

            # Keep global variables as-is
            dep_comp = components.get(dep)
            if dep_comp and dep_comp.type == "global_variable":
                new_deps.add(dep)
                continue

            # Keep direct class dependencies
            if dep in components and components[dep].type == "class":
                new_deps.add(dep)
                continue

            # For external class methods, depend on the class instead
            dep_parts = dep.split(".")
            if len(dep_parts) >= 2:
                owner = ".".join(dep_parts[:-1])
                if owner in components and components[owner].type == "class":
                    # This is a method of another class -> depend on the class
                    new_deps.add(owner)
                    continue

            # Keep module-level functions and other dependencies
            new_deps.add(dep)

        comp.depends_on = new_deps

    # ==================================================
    # PASS 3: ORCHESTRATOR METHOD COLLAPSE (OPTIONAL)
    # ==================================================
    # If a method only uses dependencies that are already declared at the class level,
    # we can hide the method's dependencies (they're redundant with the class)
    # 
    # HOWEVER: We DO NOT collapse global variable dependencies
    
    for comp in components.values():
        if comp.type != "method":
            continue

        comp_parts = comp.id.split(".")
        if len(comp_parts) < 2:
            continue

        class_id = ".".join(comp_parts[:-1])
        class_comp = components.get(class_id)

        if not class_comp:
            continue

        # Separate global variables from other dependencies
        method_globals = {dep for dep in comp.depends_on 
                         if dep in components and components[dep].type == "global_variable"}
        method_non_globals = comp.depends_on - method_globals
        
        class_globals = {dep for dep in class_comp.depends_on 
                        if dep in components and components[dep].type == "global_variable"}
        class_non_globals = class_comp.depends_on - class_globals

        # If non-global method dependencies are subset of non-global class dependencies,
        # we can hide them (but keep global dependencies visible)
        if method_non_globals and method_non_globals.issubset(class_non_globals):
            # Keep only global variable dependencies
            # For true hiding of non-globals, uncomment:
            # comp.depends_on = method_globals
            pass

    # ==================================================
    # PASS 4: REMOVE CIRCULAR SELF-REFERENCES (SAFETY)
    # ==================================================
    # Final safety pass to ensure no component depends on itself
    for comp in components.values():
        comp.depends_on.discard(comp.id)


def get_dependency_summary(components):
    """
    Generate a summary of dependencies for debugging/documentation.
    
    Returns:
        dict: Summary statistics about the dependency graph
    """
    summary = {
        "total_components": len(components),
        "classes": 0,
        "methods": 0,
        "functions": 0,
        "global_variables": 0,
        "total_dependencies": 0,
        "components_with_no_deps": 0,
        "max_dependencies": 0,
        "avg_dependencies": 0.0,
    }

    dep_counts = []

    for comp in components.values():
        comp_type = comp.type
        if comp_type == "class":
            summary["classes"] += 1
        elif comp_type == "method":
            summary["methods"] += 1
        elif comp_type == "function":
            summary["functions"] += 1
        elif comp_type == "global_variable":
            summary["global_variables"] += 1
        
        dep_count = len(comp.depends_on)
        dep_counts.append(dep_count)
        summary["total_dependencies"] += dep_count
        
        if dep_count == 0:
            summary["components_with_no_deps"] += 1
        
        if dep_count > summary["max_dependencies"]:
            summary["max_dependencies"] = dep_count

    if dep_counts:
        summary["avg_dependencies"] = sum(dep_counts) / len(dep_counts)

    return summary