"""
Lightweight Gold Extractors - Direct AST walkers for validation.

These extract ONLY structural facts from tree-sitter AST (no normalization).
Output: JSON with {name, type, location, params, return_type, calls, modifiers}

Philosophy: Minimal code, no dependencies on adapter logic.
Used to validate that adapter extraction doesn't lose information.
"""

from typing import Dict, List, Any, Optional
from tree_sitter import Node


class GoldExtractor:
    """Base class for language-specific gold extractors."""
    
    def __init__(self, language: str):
        self.language = language
    
    def extract(self, tree: Node, source: str, file_path: str) -> Dict[str, Any]:
        """
        Extract raw structural facts from AST.
        
        Returns:
            {
                'file_path': str,
                'language': str,
                'components': [
                    {
                        'name': str,
                        'type': 'function|class|method|global_var',
                        'location': {'start_line': int, 'end_line': int},
                        'signature': str,
                        'parameters': [{'name': str, 'type': str|None}],
                        'return_type': str|None,
                        'modifiers': ['public', 'static', 'async', ...],
                        'calls': [{'name': str, 'line': int}],
                        'raw_json': {...}  # For debugging
                    }
                ]
            }
        """
        raise NotImplementedError


class PythonGoldExtractor(GoldExtractor):
    """Direct Python AST extraction."""
    
    def __init__(self):
        super().__init__('python')
    
    def extract(self, tree: Node, source: str, file_path: str) -> Dict[str, Any]:
        components = []
        source_lines = source.split('\n')
        
        def walk(node: Node, depth=0):
            # ============ FUNCTION DEFINITION ============
            if node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                params_node = node.child_by_field_name('parameters')
                
                name = name_node.text.decode() if name_node else '?'
                params = self._extract_params(params_node) if params_node else []
                
                # Check for decorator (e.g., @property, @staticmethod, @classmethod)
                modifiers = []
                parent = node.parent
                if parent and parent.type == 'decorated_definition':
                    for child in parent.children:
                        if child.type == 'decorator':
                            modifiers.append(child.text.decode().strip())
                
                # Extract calls (Call expressions in function body)
                calls = []
                for child in node.children:
                    calls.extend(self._extract_calls(child))
                
                components.append({
                    'name': name,
                    'type': 'function',
                    'location': {
                        'start_line': node.start_point[0] + 1,
                        'end_line': node.end_point[0] + 1
                    },
                    'signature': self._extract_signature(node, source_lines),
                    'parameters': params,
                    'return_type': None,  # Python type hints would be in signature
                    'modifiers': modifiers,
                    'calls': calls,
                })
            
            # ============ CLASS DEFINITION ============
            elif node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                name = name_node.text.decode() if name_node else '?'
                
                # Extract base classes (inheritance)
                parent_classes = []
                for child in node.children:
                    if child.type == 'argument_list':
                        for arg in child.children:
                            if arg.type not in ('(', ')', ','):
                                parent_classes.append(arg.text.decode())
                
                # Extract methods
                methods = []
                for child in node.children:
                    if child.type == 'block':
                        for stmt in child.children:
                            if stmt.type in ('function_definition', 'decorated_definition'):
                                method_name = stmt.child_by_field_name('name')
                                if method_name:
                                    methods.append(method_name.text.decode())
                
                components.append({
                    'name': name,
                    'type': 'class',
                    'location': {
                        'start_line': node.start_point[0] + 1,
                        'end_line': node.end_point[0] + 1
                    },
                    'signature': self._extract_signature(node, source_lines),
                    'parent_classes': parent_classes,
                    'methods': methods,
                    'parameters': [],
                    'return_type': None,
                    'modifiers': [],
                    'calls': [],
                })
            
            # ============ MODULE-LEVEL VARIABLES ============
            elif node.type == 'assignment' and depth == 1:
                lhs = node.child_by_field_name('left')
                if lhs and lhs.type == 'identifier':
                    name = lhs.text.decode()
                    components.append({
                        'name': name,
                        'type': 'global_var',
                        'location': {
                            'start_line': node.start_point[0] + 1,
                            'end_line': node.end_point[0] + 1
                        },
                        'signature': self._extract_signature(node, source_lines),
                        'parameters': [],
                        'return_type': None,
                        'modifiers': [],
                        'calls': [],
                    })
            
            # Continue walking
            for child in node.children:
                walk(child, depth + 1)
        
        walk(tree.root_node)
        
        return {
            'file_path': file_path,
            'language': self.language,
            'components': components
        }
    
    def _extract_params(self, params_node: Node) -> List[Dict[str, Any]]:
        """Extract parameters from parameter list."""
        params = []
        if not params_node:
            return params
        
        for child in params_node.children:
            if child.type == 'identifier':
                params.append({'name': child.text.decode(), 'type': None})
            elif child.type == 'typed_parameter':
                name = child.child_by_field_name('name')
                type_node = child.child_by_field_name('type')
                params.append({
                    'name': name.text.decode() if name else '?',
                    'type': type_node.text.decode() if type_node else None
                })
        
        return params
    
    def _extract_calls(self, node: Node) -> List[Dict[str, str]]:
        """Extract function calls from node."""
        calls = []
        
        def search(n):
            if n.type == 'call':
                func = n.child_by_field_name('function')
                if func:
                    calls.append({
                        'name': func.text.decode(),
                        'line': n.start_point[0] + 1
                    })
            for child in n.children:
                search(child)
        
        search(node)
        return calls
    
    def _extract_signature(self, node: Node, source_lines: List[str]) -> str:
        """Extract signature (first line)."""
        line_idx = node.start_point[0]
        if line_idx < len(source_lines):
            return source_lines[line_idx].strip()
        return ""


class JavaScriptGoldExtractor(GoldExtractor):
    """Direct JavaScript AST extraction."""
    
    def __init__(self):
        super().__init__('javascript')
    
    def extract(self, tree: Node, source: str, file_path: str) -> Dict[str, Any]:
        components = []
        source_lines = source.split('\n')
        
        def walk(node: Node):
            # ============ FUNCTION DECLARATION ============
            if node.type == 'function_declaration':
                name_node = node.child_by_field_name('name')
                params_node = node.child_by_field_name('parameters')
                
                name = name_node.text.decode() if name_node else '?'
                params = self._extract_params(params_node) if params_node else []
                
                # Check for async
                modifiers = ['async'] if self._is_async(node) else []
                
                calls = self._extract_calls(node)
                
                components.append({
                    'name': name,
                    'type': 'function',
                    'location': {
                        'start_line': node.start_point[0] + 1,
                        'end_line': node.end_point[0] + 1
                    },
                    'signature': self._extract_signature(node, source_lines),
                    'parameters': params,
                    'return_type': None,
                    'modifiers': modifiers,
                    'calls': calls,
                })
            
            # ============ ARROW FUNCTION (const foo = () => {}) ============
            elif node.type == 'variable_declarator':
                name_node = node.child_by_field_name('name')
                value_node = node.child_by_field_name('value')
                
                if value_node and value_node.type == 'arrow_function':
                    name = name_node.text.decode() if name_node else '?'
                    params = self._extract_arrow_params(value_node)
                    
                    modifiers = ['async'] if self._is_async(value_node) else []
                    calls = self._extract_calls(value_node)
                    
                    components.append({
                        'name': name,
                        'type': 'function',
                        'location': {
                            'start_line': node.start_point[0] + 1,
                            'end_line': node.end_point[0] + 1
                        },
                        'signature': self._extract_signature(node, source_lines),
                        'parameters': params,
                        'return_type': None,
                        'modifiers': modifiers,
                        'calls': calls,
                    })
            
            # ============ CLASS DECLARATION ============
            elif node.type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                name = name_node.text.decode() if name_node else '?'
                
                # Extract methods
                methods = []
                for child in node.children:
                    if child.type == 'class_body':
                        for stmt in child.children:
                            if stmt.type == 'method_definition':
                                method_name = stmt.child_by_field_name('name')
                                if method_name:
                                    methods.append(method_name.text.decode())
                
                components.append({
                    'name': name,
                    'type': 'class',
                    'location': {
                        'start_line': node.start_point[0] + 1,
                        'end_line': node.end_point[0] + 1
                    },
                    'signature': self._extract_signature(node, source_lines),
                    'methods': methods,
                    'parameters': [],
                    'return_type': None,
                    'modifiers': [],
                    'calls': [],
                })
            
            # Continue walking
            for child in node.children:
                walk(child)
        
        walk(tree.root_node)
        
        return {
            'file_path': file_path,
            'language': self.language,
            'components': components
        }
    
    def _extract_params(self, params_node: Node) -> List[Dict[str, Any]]:
        """Extract parameters from parameter list."""
        params = []
        for child in params_node.children:
            if child.type == 'identifier':
                params.append({'name': child.text.decode(), 'type': None})
        return params
    
    def _extract_arrow_params(self, arrow_node: Node) -> List[Dict[str, Any]]:
        """Extract parameters from arrow function."""
        params = []
        for child in arrow_node.children:
            if child.type == 'formal_parameters':
                for param in child.children:
                    if param.type == 'identifier':
                        params.append({'name': param.text.decode(), 'type': None})
            elif child.type == 'identifier':
                params.append({'name': child.text.decode(), 'type': None})
        return params
    
    def _is_async(self, node: Node) -> bool:
        """Check if function is async."""
        return any(child.type == 'async' for child in node.children)
    
    def _extract_calls(self, node: Node) -> List[Dict[str, str]]:
        """Extract function calls from node."""
        calls = []
        
        def search(n):
            if n.type == 'call_expression':
                func = n.child_by_field_name('function')
                if func:
                    calls.append({
                        'name': func.text.decode(),
                        'line': n.start_point[0] + 1
                    })
            for child in n.children:
                search(child)
        
        search(node)
        return calls
    
    def _extract_signature(self, node: Node, source_lines: List[str]) -> str:
        """Extract signature (first 2 lines)."""
        start = node.start_point[0]
        end = min(start + 2, len(source_lines))
        return '\n'.join(l.strip() for l in source_lines[start:end])


class JavaGoldExtractor(GoldExtractor):
    """Direct Java AST extraction."""
    
    def __init__(self):
        super().__init__('java')
    
    def extract(self, tree: Node, source: str, file_path: str) -> Dict[str, Any]:
        components = []
        source_lines = source.split('\n')
        
        def walk(node: Node):
            # ============ CLASS DECLARATION ============
            if node.type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                name = name_node.text.decode() if name_node else '?'
                
                modifiers = self._extract_modifiers(node)
                
                # Extract methods
                methods = []
                for child in node.children:
                    if child.type == 'class_body':
                        for stmt in child.children:
                            if stmt.type == 'method_declaration':
                                method_name = stmt.child_by_field_name('name')
                                if method_name:
                                    methods.append(method_name.text.decode())
                
                components.append({
                    'name': name,
                    'type': 'class',
                    'location': {
                        'start_line': node.start_point[0] + 1,
                        'end_line': node.end_point[0] + 1
                    },
                    'signature': self._extract_signature(node, source_lines),
                    'methods': methods,
                    'parameters': [],
                    'return_type': None,
                    'modifiers': modifiers,
                    'calls': [],
                })
            
            # ============ METHOD DECLARATION ============
            elif node.type == 'method_declaration':
                name_node = node.child_by_field_name('name')
                params_node = node.child_by_field_name('parameters')
                
                name = name_node.text.decode() if name_node else '?'
                params = self._extract_params(params_node) if params_node else []
                
                modifiers = self._extract_modifiers(node)
                calls = self._extract_calls(node)
                
                components.append({
                    'name': name,
                    'type': 'method',
                    'location': {
                        'start_line': node.start_point[0] + 1,
                        'end_line': node.end_point[0] + 1
                    },
                    'signature': self._extract_signature(node, source_lines),
                    'parameters': params,
                    'return_type': None,
                    'modifiers': modifiers,
                    'calls': calls,
                })
            
            for child in node.children:
                walk(child)
        
        walk(tree.root_node)
        
        return {
            'file_path': file_path,
            'language': self.language,
            'components': components
        }
    
    def _extract_modifiers(self, node: Node) -> List[str]:
        """Extract modifiers (public, static, abstract, etc.)."""
        modifiers = []
        for child in node.children:
            if child.type in ('public', 'private', 'protected', 'static', 'abstract', 'final'):
                modifiers.append(child.text.decode())
        return modifiers
    
    def _extract_params(self, params_node: Node) -> List[Dict[str, Any]]:
        """Extract parameters."""
        params = []
        for child in params_node.children:
            if child.type == 'formal_parameter':
                name = child.child_by_field_name('name')
                type_node = child.child_by_field_name('type')
                params.append({
                    'name': name.text.decode() if name else '?',
                    'type': type_node.text.decode() if type_node else None
                })
        return params
    
    def _extract_calls(self, node: Node) -> List[Dict[str, str]]:
        """Extract method calls."""
        calls = []
        
        def search(n):
            if n.type == 'method_invocation':
                name = n.child_by_field_name('name')
                if name:
                    calls.append({
                        'name': name.text.decode(),
                        'line': n.start_point[0] + 1
                    })
            for child in n.children:
                search(child)
        
        search(node)
        return calls
    
    def _extract_signature(self, node: Node, source_lines: List[str]) -> str:
        """Extract signature."""
        start = node.start_point[0]
        end = min(start + 2, len(source_lines))
        return '\n'.join(l.strip() for l in source_lines[start:end])


def get_gold_extractor(language: str) -> GoldExtractor:
    """Factory for gold extractors."""
    extractors = {
        'python': PythonGoldExtractor,
        'javascript': JavaScriptGoldExtractor,
        'java': JavaGoldExtractor,
        'typescript': JavaScriptGoldExtractor,  # Reuse JS for now
    }
    extractor_class = extractors.get(language)
    if not extractor_class:
        raise ValueError(f"No gold extractor for language: {language}")
    return extractor_class()
