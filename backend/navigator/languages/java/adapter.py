from treesitter.parser_factory import get_ts_parser
from .extractor import extract_components

class JavaAdapter:
    language = "java"
    extensions = [".java"]

    def __init__(self):
        self.parser = get_ts_parser("java")

    def parse(self, source):
        return self.parser.parse(bytes(source, "utf8"))

    def extract_components(self, *args):
        return extract_components(*args)

    def resolve_dependencies(self, component, tree, source, all_components):
        return set()
