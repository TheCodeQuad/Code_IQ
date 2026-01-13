"""
Global API Endpoint Extractor
Extracts REST API endpoints from any language (Python, JavaScript, TypeScript, Java)
Works with: FastAPI, Flask, Django, Express, Spring, etc.
"""
import re
from typing import Dict, List, Optional, Tuple, Set
from backend.models.code_component import CodeComponent, Location, Parameter, ComponentType


class GlobalAPIExtractor:
    """Language-agnostic API endpoint extractor"""
    
    # Framework detection patterns
    FRAMEWORK_PATTERNS = {
        'fastapi': {
            'decorators': [r'@app\.(get|post|put|delete|patch)', r'@router\.(get|post|put|delete|patch)'],
            'imports': [r'fastapi', r'FastAPI'],
            'path_extract': r'@app\.\w+\(["\']([^"\']+)["\']',
        },
        'flask': {
            'decorators': [r'@app\.route', r'@blueprint\.route'],
            'imports': [r'flask', r'Flask'],
            'path_extract': r'@.*?\.route\(["\']([^"\']+)["\']',
        },
        'express': {
            'decorators': [r'app\.(get|post|put|delete|patch)\(', r'router\.(get|post|put|delete|patch)\('],
            'imports': [r'express', r'require.*express'],
            'path_extract': r'app\.\w+\(["\']([^"\']+)["\']',
        },
        'spring': {
            'decorators': [r'@GetMapping', r'@PostMapping', r'@PutMapping', r'@DeleteMapping', r'@RequestMapping'],
            'imports': [r'springframework'],
            'path_extract': r'@.*?Mapping\(["\']([^"\']+)["\']',
        },
        'django': {
            'decorators': [r'@csrf_exempt', r'@require_http_methods'],
            'imports': [r'django'],
            'path_extract': None,  # Django uses url patterns, harder to extract
        },
    }
    
    HTTP_METHOD_MAP = {
        'get': 'GET',
        'post': 'POST',
        'put': 'PUT',
        'delete': 'DELETE',
        'patch': 'PATCH',
        'GetMapping': 'GET',
        'PostMapping': 'POST',
        'PutMapping': 'PUT',
        'DeleteMapping': 'DELETE',
        'PatchMapping': 'PATCH',
        'RequestMapping': 'GET',  # Default
    }
    
    def __init__(self, source: str, file_path: str, module_path: str, 
                 language: str, file_imports: List[str]):
        self.source = source
        self.file_path = file_path
        self.module_path = module_path
        self.language = language
        self.file_imports = file_imports
        self.framework = self._detect_framework()
        self.lines = source.split('\n')
    
    def _detect_framework(self) -> Optional[str]:
        """Detect which web framework is being used"""
        source_lower = self.source.lower()
        imports_lower = ' '.join(self.file_imports).lower()
        
        for framework, patterns in self.FRAMEWORK_PATTERNS.items():
            for import_pattern in patterns['imports']:
                if re.search(import_pattern, imports_lower, re.IGNORECASE):
                    return framework
            for decorator_pattern in patterns['decorators']:
                if re.search(decorator_pattern, source_lower):
                    return framework
        
        return None
    
    def extract(self) -> Dict[str, CodeComponent]:
        """Extract all API endpoints as CodeComponents"""
        if not self.framework:
            return {}
        
        endpoints = {}
        
        if self.framework == 'fastapi':
            endpoints = self._extract_fastapi_endpoints()
        elif self.framework == 'flask':
            endpoints = self._extract_flask_endpoints()
        elif self.framework == 'express':
            endpoints = self._extract_express_endpoints()
        elif self.framework == 'spring':
            endpoints = self._extract_spring_endpoints()
        elif self.framework == 'django':
            endpoints = self._extract_django_endpoints()
        
        return endpoints
    
    def _extract_fastapi_endpoints(self) -> Dict[str, CodeComponent]:
        """Extract FastAPI/Python endpoints"""
        endpoints = {}
        
        for i, line in enumerate(self.lines):
            # Match decorator
            if not (re.search(r'@app\.(get|post|put|delete|patch)', line) or 
                    re.search(r'@router\.(get|post|put|delete|patch)', line)):
                continue
            
            # Extract HTTP method
            method_match = re.search(r'@(?:app|router)\.(\w+)\(', line)
            if not method_match:
                continue
            http_method = self.HTTP_METHOD_MAP.get(method_match.group(1), 'GET')
            
            # Extract path
            path_match = re.search(r'["\']([^"\']+)["\']', line)
            if not path_match:
                continue
            http_path = path_match.group(1)
            
            # Extract status code
            status_code_match = re.search(r'status_code\s*=\s*(\d+)', line)
            status_code = int(status_code_match.group(1)) if status_code_match else 200
            
            # Find function definition
            func_def_line = self._find_next_function_def(i)
            if func_def_line is None:
                continue
            
            func_line = self.lines[func_def_line]
            func_match = re.search(r'(?:async\s+)?def\s+(\w+)\s*\((.*?)\)', func_line)
            if not func_match:
                continue
            
            func_name = func_match.group(1)
            params_str = func_match.group(2)
            
            # Extract path/query parameters
            path_params = re.findall(r'\{(\w+)\}', http_path)
            query_params = self._extract_query_params(params_str, path_params)
            
            # Get function source
            end_line = self._find_function_end(func_def_line)
            func_source = '\n'.join(self.lines[func_def_line:end_line + 1])
            
            # Create component ID
            endpoint_id = f"{self.module_path}.{http_method.lower()}_{http_path.replace('/', '_').replace('{', '').replace('}', '')}"
            
            # Build parameters
            parameters = [Parameter(name=p, type_hint='str', is_required=p in path_params) 
                         for p in query_params]
            
            # Create component
            component = CodeComponent(
                id=endpoint_id,
                name=f"{http_method} {http_path}",
                type=ComponentType.API_ENDPOINT,
                location=Location(
                    file_path=self.file_path,
                    start_line=i + 1,
                    end_line=end_line + 1
                ),
                source_code=func_source,
                signature=f"{http_method} {http_path}",
                http_method=http_method,
                http_path=http_path,
                framework=self.framework,
                path_parameters=path_params,
                query_parameters=query_params,
                parameters=parameters,
                decorators=[line.strip()],
                imports=self.file_imports,
                language=self.language,
                lines_of_code=end_line - func_def_line + 1,
                is_async='async def' in func_line,
                status_codes=[status_code],
            )
            
            endpoints[endpoint_id] = component
        
        return endpoints
    
    def _extract_flask_endpoints(self) -> Dict[str, CodeComponent]:
        """Extract Flask Python endpoints"""
        endpoints = {}
        
        for i, line in enumerate(self.lines):
            if '@app.route' not in line and '@blueprint.route' not in line:
                continue
            
            # Extract path
            path_match = re.search(r'["\']([^"\']+)["\']', line)
            if not path_match:
                continue
            http_path = path_match.group(1)
            
            # Extract methods
            methods_match = re.search(r'methods\s*=\s*\[(.*?)\]', line)
            methods = ['GET']
            if methods_match:
                methods = re.findall(r'["\'](\w+)["\']', methods_match.group(1))
            
            # Find function
            func_def_line = self._find_next_function_def(i)
            if func_def_line is None:
                continue
            
            func_line = self.lines[func_def_line]
            func_match = re.search(r'def\s+(\w+)\s*\((.*?)\)', func_line)
            if not func_match:
                continue
            
            # Path parameters in Flask are <param_name>
            path_params = re.findall(r'<(\w+)>', http_path)
            
            end_line = self._find_function_end(func_def_line)
            func_source = '\n'.join(self.lines[func_def_line:end_line + 1])
            
            for method in methods:
                endpoint_id = f"{self.module_path}.{method.lower()}_{http_path.replace('/', '_').replace('<', '').replace('>', '')}"
                
                component = CodeComponent(
                    id=endpoint_id,
                    name=f"{method} {http_path}",
                    type=ComponentType.API_ENDPOINT,
                    location=Location(
                        file_path=self.file_path,
                        start_line=i + 1,
                        end_line=end_line + 1
                    ),
                    source_code=func_source,
                    signature=f"{method} {http_path}",
                    http_method=method,
                    http_path=http_path,
                    framework=self.framework,
                    path_parameters=path_params,
                    parameters=[Parameter(name=p, type_hint='str', is_required=True) for p in path_params],
                    decorators=[line.strip()],
                    imports=self.file_imports,
                    language=self.language,
                    lines_of_code=end_line - func_def_line + 1,
                    status_codes=[200],
                )
                
                endpoints[endpoint_id] = component
        
        return endpoints
    
    def _extract_express_endpoints(self) -> Dict[str, CodeComponent]:
        """Extract Express.js endpoints"""
        endpoints = {}
        
        for i, line in enumerate(self.lines):
            # Match app.get/post/etc or router.get/post/etc
            method_match = re.search(r'(?:app|router)\.(get|post|put|delete|patch)\(', line)
            if not method_match:
                continue
            
            http_method = self.HTTP_METHOD_MAP.get(method_match.group(1), 'GET')
            
            # Extract path - first quoted string
            path_match = re.search(r'["\']([^"\']+)["\']', line)
            if not path_match:
                continue
            http_path = path_match.group(1)
            
            # Find the handler function/callback
            path_params = re.findall(r':(\w+)', http_path)
            
            # Extract handler - usually arrow function or function name
            handler_match = (re.search(r',\s*(?:async\s+)?\(.*?\)\s*=>', line)
            or re.search(r',\s*function', line)
            or re.search(r',\s*(\w+)\s*[,\)]', line))
            
            endpoint_id = f"{self.module_path}.{http_method.lower()}_{http_path.replace('/', '_').replace(':', '')}"
            
            component = CodeComponent(
                id=endpoint_id,
                name=f"{http_method} {http_path}",
                type=ComponentType.API_ENDPOINT,
                location=Location(
                    file_path=self.file_path,
                    start_line=i + 1,
                    end_line=i + 1
                ),
                source_code=line,
                signature=f"{http_method} {http_path}",
                http_method=http_method,
                http_path=http_path,
                framework=self.framework,
                path_parameters=path_params,
                parameters=[Parameter(name=p, type_hint='any', is_required=True) for p in path_params],
                decorators=[],
                imports=self.file_imports,
                language=self.language,
                lines_of_code=1,
                status_codes=[200],
            )
            
            endpoints[endpoint_id] = component
        
        return endpoints
    
    def _extract_spring_endpoints(self) -> Dict[str, CodeComponent]:
        """Extract Spring Java endpoints"""
        endpoints = {}
        
        for i, line in enumerate(self.lines):
            # Match @GetMapping, @PostMapping, etc
            mapping_match = re.search(r'@(\w+Mapping)\(', line)
            if not mapping_match:
                continue
            
            mapping_type = mapping_match.group(1)
            http_method = self.HTTP_METHOD_MAP.get(mapping_type, 'GET')
            
            # Extract path
            path_match = re.search(r'value\s*=\s*["\']([^"\']+)["\']|["\']([^"\']+)["\']', line)
            http_path = path_match.group(1) or path_match.group(2) if path_match else "/"
            
            # Find method definition
            func_def_line = self._find_next_function_def(i, language='java')
            if func_def_line is None:
                continue
            
            func_line = self.lines[func_def_line]
            func_match = re.search(r'(?:public|private)\s+\w+\s+(\w+)\s*\((.*?)\)', func_line)
            if not func_match:
                continue
            
            # Path parameters in Spring are {param_name}
            path_params = re.findall(r'\{(\w+)\}', http_path)
            
            end_line = self._find_function_end(func_def_line, language='java')
            func_source = '\n'.join(self.lines[func_def_line:end_line + 1])
            
            endpoint_id = f"{self.module_path}.{http_method.lower()}_{http_path.replace('/', '_').replace('{', '').replace('}', '')}"
            
            component = CodeComponent(
                id=endpoint_id,
                name=f"{http_method} {http_path}",
                type=ComponentType.API_ENDPOINT,
                location=Location(
                    file_path=self.file_path,
                    start_line=i + 1,
                    end_line=end_line + 1
                ),
                source_code=func_source,
                signature=f"{http_method} {http_path}",
                http_method=http_method,
                http_path=http_path,
                framework=self.framework,
                path_parameters=path_params,
                parameters=[Parameter(name=p, type_hint='String', is_required=True) for p in path_params],
                decorators=[line.strip()],
                imports=self.file_imports,
                language=self.language,
                lines_of_code=end_line - func_def_line + 1,
                status_codes=[200],
            )
            
            endpoints[endpoint_id] = component
        
        return endpoints
    
    def _extract_django_endpoints(self) -> Dict[str, CodeComponent]:
        """Extract Django endpoints (limited support)"""
        # Django uses url patterns, harder to extract statically
        return {}
    
    def _find_next_function_def(self, start_line: int, language: str = 'python') -> Optional[int]:
        """Find next function definition"""
        patterns = {
            'python': [r'^\s*def\s+\w+', r'^\s*async\s+def\s+\w+'],
            'javascript': [r'^\s*(?:async\s+)?function\s+\w+', r'^\s*(?:async\s+)?\w+\s*\('],
            'typescript': [r'^\s*(?:async\s+)?(?:public|private)?\s*\w+\s*\('],
            'java': [r'^\s*(?:public|private)\s+\w+\s+\w+\s*\('],
        }
        
        lang_patterns = patterns.get(language, patterns['python'])
        
        for i in range(start_line + 1, min(start_line + 10, len(self.lines))):
            for pattern in lang_patterns:
                if re.match(pattern, self.lines[i]):
                    return i
        
        return None
    
    def _find_function_end(self, start_line: int, language: str = 'python') -> int:
        """Find end of function definition"""
        if start_line >= len(self.lines):
            return start_line
        
        start_indent = len(self.lines[start_line]) - len(self.lines[start_line].lstrip())
        
        # For single-line functions (Express)
        if '{' in self.lines[start_line] and '}' in self.lines[start_line]:
            return start_line
        
        for i in range(start_line + 1, len(self.lines)):
            line = self.lines[i]
            if line.strip() == '':
                continue
            
            current_indent = len(line) - len(line.lstrip())
            
            # End when we hit less-indented code
            if current_indent <= start_indent and line.strip() and not line.strip().startswith('#'):
                return i - 1
        
        return len(self.lines) - 1
    
    def _extract_query_params(self, params_str: str, path_params: List[str]) -> List[str]:
        """Extract query parameters from function signature"""
        params = re.findall(r'(\w+)\s*(?::|=|,)', params_str)
        return [p for p in params if p not in path_params and p not in ['self', 'cls', 'request', 'response']]


def extract_api_endpoints(source: str, file_path: str, module_path: str, 
                          language: str, file_imports: List[str]) -> Dict[str, CodeComponent]:
    """Global function to extract API endpoints from any language"""
    extractor = GlobalAPIExtractor(source, file_path, module_path, language, file_imports)
    return extractor.extract()