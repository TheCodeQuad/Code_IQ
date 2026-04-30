from .python.adapter import PythonAdapter
from .javascript.adapter import JavaScriptAdapter
from .typescript.adapter import TypeScriptAdapter
from .java.adapter import JavaAdapter


class AdapterRegistry:
    def __init__(self):
        self.adapters = [
            PythonAdapter(),
            JavaScriptAdapter(),
            TypeScriptAdapter(),
            JavaAdapter(),
        ]

    def get_adapter_for_file(self, file_path: str):
        for adapter in self.adapters:
            for ext in adapter.extensions:
                if file_path.endswith(ext):
                    return adapter
        return None  # unsupported file
    
    def get_adapter(self, language: str):
        """Get adapter by language name (e.g., 'javascript', 'python')."""
        language_lower = language.lower()
        for adapter in self.adapters:
            adapter_lang = adapter.language.lower()
            if adapter_lang == language_lower:
                return adapter
        return None  # unsupported language
