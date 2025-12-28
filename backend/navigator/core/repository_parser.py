import os
from languages.adapter_registry import AdapterRegistry
from core.doc_dependency_parser import apply_doc_dependency_rules
class RepositoryParser:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.registry = AdapterRegistry()

    def parse(self):
        all_components = {}

        # Store parsed file context for second pass
        parsed_files = []

        # ---------- PASS 1: parse + extract ----------
        for root, _, files in os.walk(self.repo_path):
            for file in files:
                file_path = os.path.join(root, file)

                adapter = self.registry.get_adapter_for_file(file_path)
                if not adapter:
                    continue  # unsupported file type

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    source = f.read()

                tree = adapter.parse(source)

                module_path = os.path.relpath(
                    file_path, self.repo_path
                ).replace(os.sep, ".").rsplit(".", 1)[0]

                raw_components = adapter.extract_components(
                    tree, source, file_path, module_path
                )

                # 🔥 NORMALIZATION STEP
                if isinstance(raw_components, dict):
                    components = raw_components
                else:
                    # assume iterable of CodeComponent
                    components = {c.id: c for c in raw_components}

                parsed_files.append((adapter, tree, source, components))
                all_components.update(components)


        # ---------- PASS 2: resolve dependencies ----------
        for adapter, tree, source, components in parsed_files:
            for component in components.values():
                deps = adapter.resolve_dependencies(
                    component, tree, source, all_components
                )
                component.depends_on.update(deps)
    
        # ---------- PASS 3: class → method ----------
        for cid, comp in all_components.items():
            if comp.type == "class":
                for other_id, other in all_components.items():
                    if other.type == "method" and other_id.startswith(cid + "."):
                        if not other_id.endswith(".__init__"):
                            comp.depends_on.add(other_id)



        apply_doc_dependency_rules(all_components)
        return all_components
    

    def _to_module_path(self, file_path):
        rel = os.path.relpath(file_path, self.repo_path)
        rel = rel.lstrip(os.sep)          # remove leading slash
        rel = rel.replace("\\", ".")      # Windows-safe
        rel = rel.replace("/", ".")       # Linux-safe
        if rel.endswith(".py"):
            rel = rel[:-3]
        return rel

