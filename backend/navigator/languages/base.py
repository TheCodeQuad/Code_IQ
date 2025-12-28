class BaseLanguageAdapter:
    language: str
    extensions: list[str]

    def parse(self, source_code: str):
        raise NotImplementedError

    def extract_components(self, tree, source, file_path, module_path):
        """
        PASS 1: return List[CodeComponent]
        """
        raise NotImplementedError

    def resolve_dependencies(self, component, tree, source, all_components):
        """
        PASS 2: return Set[str]
        """
        raise NotImplementedError
