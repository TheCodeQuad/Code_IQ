from treesitter.parser_factory import get_ts_parser
from .extractor import extract_components
from .dependencies import resolve_dependencies

class PythonAdapter:
    language = "python"
    extensions = [".py"]

    def __init__(self):
        self.parser = get_ts_parser("python")

    def parse(self, source):
        return self.parser.parse(bytes(source, "utf8"))

    def extract_components(self, tree, source, file_path, module_path):
        return extract_components(tree, source, file_path, module_path)

    def resolve_dependencies(self, component, tree, source, all_components):
        return resolve_dependencies(component, tree, source, all_components)
