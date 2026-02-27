import os
import logging
from backend.navigator.languages.adapter_registry import AdapterRegistry
from backend.navigator.core.doc_dependency_parser import apply_doc_dependency_rules

logger = logging.getLogger(__name__)


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
                # Debug: Log depends_on before resolve_dependencies
                before_deps = list(component.depends_on) if hasattr(component, 'depends_on') else []
                
                deps = adapter.resolve_dependencies(
                    component, tree, source, all_components
                )
                # Convert deps to list if it's a set, then extend
                if isinstance(deps, set):
                    deps = list(deps)
                elif not isinstance(deps, list):
                    deps = list(deps) if deps else []
                
                # Extend the depends_on list with new dependencies (avoiding duplicates)
                for dep in deps:
                    if dep not in component.depends_on:
                        component.depends_on.append(dep)
                
                # Debug: Log if dependencies changed for functions/methods
                if component.type in ("function", "arrow_function", "method") and before_deps:
                    after_deps = list(component.depends_on)
                    if before_deps != after_deps:
                        logger.debug(f"[Parser PASS 2] {component.id}: before={before_deps[:3]}, after={after_deps[:3]}, added={deps[:3]}")

        # 🔥 FIX: Remove Pass 3 (the problematic class → method dependency addition)
        # Pass 3 was adding all methods as dependencies of their parent class,
        # which is conceptually wrong (methods are PART of a class, not dependencies).
        # The doc_dependency_rules will handle proper class-level abstraction.

        # ---------- PASS 3: Apply documentation rules ----------
        apply_doc_dependency_rules(all_components)
        
        # Debug: Sample final dependencies for TypeScript components
        ts_comps = [c for c in all_components.values() if c.language == "typescript" and c.type in ("function", "arrow_function")]
        if ts_comps:
            sample = ts_comps[0]
            logger.debug(f"[Parser FINAL] {sample.id}: depends_on={list(sample.depends_on)[:5]}")
        
        return all_components

    def _to_module_path(self, file_path):
        rel = os.path.relpath(file_path, self.repo_path)
        rel = rel.lstrip(os.sep)          # remove leading slash
        rel = rel.replace("\\", ".")      # Windows-safe
        rel = rel.replace("/", ".")       # Linux-safe
        if rel.endswith(".py"):
            rel = rel[:-3]
        return rel
