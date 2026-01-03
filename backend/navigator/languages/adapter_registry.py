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

