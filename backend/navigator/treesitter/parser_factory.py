from tree_sitter import Parser
from tree_sitter_languages import get_language

def get_ts_parser(language_name: str) -> Parser:
    language = get_language(language_name)
    parser = Parser()
    parser.set_language(language)
    return parser
