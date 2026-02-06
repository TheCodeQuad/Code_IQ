"""
Docstring Inserter Utility

Inserts generated docstrings into source code files at the correct component locations.
Supports Python docstrings with Google, NumPy, and reStructuredText styles.
"""
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from backend.utils.logger import get_logger
from backend.utils.file_handler import FileHandler

logger = get_logger(__name__)


class DocstringStyle(Enum):
    """Supported docstring styles"""
    GOOGLE = "google"
    NUMPY = "numpy"
    RST = "rst"


@dataclass
class InsertionPoint:
    """Represents where a docstring should be inserted"""
    component_id: str
    file_path: str
    start_line: int  # Line where component starts (1-indexed)
    component_type: str  # class, function, method
    docstring: str
    has_existing_docstring: bool = False
    existing_docstring_lines: Tuple[int, int] = (0, 0)  # start, end lines if exists
    language: str = "python"  # Programming language detected from file extension


@dataclass
class InsertionResult:
    """Result of a docstring insertion"""
    component_id: str
    file_path: str
    success: bool
    action: str  # 'inserted', 'replaced', 'skipped'
    message: str = ""


class DocstringInserter:
    """
    Inserts generated docstrings into Python source files.
    
    Features:
    - Detects existing docstrings and can replace or skip them
    - Handles proper indentation based on component context
    - Supports classes, functions, and methods
    - Creates backups before modification
    - Supports both batch and continuous (single component) insertion
    """
    
    def __init__(
        self,
        writer_output_dir: Optional[Path] = None,
        component_data_file: Optional[Path] = None,
        backup: bool = True,
        replace_existing: bool = False
    ):
        """
        Initialize the docstring inserter.
        
        Args:
            writer_output_dir: Directory containing writer output JSON files (for batch mode)
            component_data_file: Path to component data JSON (reader output or IR)
            backup: Whether to create backups before modifying files
            replace_existing: Whether to replace existing docstrings
        """
        self.writer_output_dir = Path(writer_output_dir) if writer_output_dir else None
        self.component_data_file = Path(component_data_file) if component_data_file else None
        self.backup = backup
        self.replace_existing = replace_existing
        self.file_handler = FileHandler()
        
        # Component data (loaded from reader output or IR)
        self.component_data: Dict[str, Any] = {}
        if self.component_data_file:
            self._load_component_data()
        
        # Track which files have been backed up (avoid multiple backups)
        self.backed_up_files: set = set()
        
        # Track line offsets per file for continuous insertion mode
        # When we insert a docstring, subsequent component line numbers shift
        self.line_offsets: Dict[str, Dict[int, int]] = {}  # {file_path: {original_line: offset}}
        
        # Cache for file contents (to batch edits per file)
        self.file_cache: Dict[str, List[str]] = {}
        self.file_modifications: Dict[str, List[InsertionPoint]] = {}
    
    def _get_adjusted_line(self, file_path: str, original_line: int) -> int:
        """
        Get the adjusted line number accounting for previous insertions.
        
        When we insert docstrings, line numbers shift. This tracks the cumulative
        offset so subsequent insertions target the correct line.
        """
        if file_path not in self.line_offsets:
            return original_line
        
        # Sum up all offsets for lines before this one
        total_offset = sum(
            offset for line, offset in self.line_offsets[file_path].items()
            if line < original_line
        )
        
        return original_line + total_offset
    
    def _record_line_offset(self, file_path: str, at_line: int, offset: int):
        """Record that an insertion added 'offset' lines at 'at_line'"""
        if file_path not in self.line_offsets:
            self.line_offsets[file_path] = {}
        self.line_offsets[file_path][at_line] = offset
    
    def reset_line_tracking(self, file_path: Optional[str] = None):
        """Reset line offset tracking (call when starting a new file or session)"""
        if file_path:
            self.line_offsets.pop(file_path, None)
        else:
            self.line_offsets.clear()
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            str: Language identifier (python, javascript, java, cpp, csharp, etc.)
        """
        ext = Path(file_path).suffix.lower()
        
        # Map file extensions to language identifiers
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.c++': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.m': 'objective_c',
            '.mm': 'objective_cpp',
        }
        
        return language_map.get(ext, 'python')  # Default to Python if unknown
    
    def _load_component_data(self):
        """Load component data containing component locations"""
        if self.component_data_file and self.component_data_file.exists():
            self.component_data = self.file_handler.read_json(self.component_data_file)
            logger.info(f"Loaded component data with {len(self.component_data)} components")
        else:
            logger.warning(f"Component data file not found: {self.component_data_file}")
    
    # ========== CONTINUOUS INSERTION MODE ==========
    
    def insert_single_docstring(
        self,
        component_id: str,
        docstring: str,
        file_path: str,
        start_line: int,
        component_type: str = "function",
        has_existing_docstring: bool = False,
        language: Optional[str] = None
    ) -> InsertionResult:
        """
        Insert a single docstring for one component (for continuous pipeline mode).
        
        This method is called by the pipeline after each component is processed
        by the writer agent, allowing real-time docstring insertion.
        
        Args:
            component_id: Unique identifier for the component
            docstring: The generated docstring text
            file_path: Absolute path to the source file
            start_line: Line number where component definition starts (1-indexed)
            component_type: Type of component (class, function, method)
            has_existing_docstring: Whether the component already has a docstring
            
        Returns:
            InsertionResult with success status and action taken
        """
        if not docstring or not docstring.strip():
            return InsertionResult(
                component_id=component_id,
                file_path=file_path,
                success=False,
                action='skipped',
                message="Empty docstring provided"
            )
        
        full_path = Path(file_path)
        
        if not full_path.exists():
            return InsertionResult(
                component_id=component_id,
                file_path=file_path,
                success=False,
                action='skipped',
                message=f"File not found: {full_path}"
            )
        
        try:
            # Read current file content
            content = self.file_handler.read_file(full_path)
            lines = content.split('\n')
            
            # Create backup only once per file
            if self.backup and file_path not in self.backed_up_files:
                backup_path = full_path.with_suffix(full_path.suffix + '.bak')
                self.file_handler.write_file(backup_path, content)
                self.backed_up_files.add(file_path)
            
            # Adjust line number for previous insertions in this file
            adjusted_line = self._get_adjusted_line(file_path, start_line)
            
            # Find insertion position
            insert_idx, existing_end_idx, base_indent = self._find_docstring_insert_position(
                lines, adjusted_line, component_type
            )
            
            has_existing = existing_end_idx > insert_idx
            
            if has_existing and not self.replace_existing:
                return InsertionResult(
                    component_id=component_id,
                    file_path=file_path,
                    success=True,
                    action='skipped',
                    message="Existing docstring preserved"
                )
            
            # Detect language if not provided
            if not language:
                language = self._detect_language(file_path)
            
            # Format the new docstring with language-aware syntax
            docstring_lines = self._format_docstring(docstring, base_indent, component_type, language)
            
            # Calculate line offset for future insertions
            if has_existing:
                # Replace existing docstring
                old_docstring_lines = existing_end_idx - insert_idx
                new_docstring_lines = len(docstring_lines)
                line_offset = new_docstring_lines - old_docstring_lines
                lines = lines[:insert_idx] + docstring_lines + lines[existing_end_idx:]
                action = 'replaced'
            else:
                # Insert new docstring
                line_offset = len(docstring_lines)
                lines = lines[:insert_idx] + docstring_lines + lines[insert_idx:]
                action = 'inserted'
            
            # Record line offset for subsequent insertions in this file
            self._record_line_offset(file_path, start_line, line_offset)
            
            # Write modified content back immediately
            new_content = '\n'.join(lines)
            self.file_handler.write_file(full_path, new_content)
            
            logger.debug(f"Docstring {action} for {component_id} at line {insert_idx + 1}")
            
            return InsertionResult(
                component_id=component_id,
                file_path=file_path,
                success=True,
                action=action,
                message=f"Docstring {action} at line {insert_idx + 1}"
            )
            
        except Exception as e:
            logger.error(f"Error inserting docstring for {component_id}: {e}")
            return InsertionResult(
                component_id=component_id,
                file_path=file_path,
                success=False,
                action='error',
                message=str(e)
            )
    
    def insert_for_component(
        self,
        component: Any,
        docstring_data: Dict[str, Any]
    ) -> InsertionResult:
        """
        Insert docstring for a CodeComponent object (convenience method for pipeline).
        
        Args:
            component: CodeComponent object with location info
            docstring_data: Writer output dict containing 'docstring' key
            
        Returns:
            InsertionResult with success status
        """
        # Extract location from component
        if hasattr(component, 'location') and component.location:
            file_path = component.location.file_path
            start_line = component.location.start_line
        elif hasattr(component, 'file_path'):
            file_path = component.file_path
            start_line = getattr(component, 'start_line', 0)
        else:
            return InsertionResult(
                component_id=getattr(component, 'id', 'unknown'),
                file_path='unknown',
                success=False,
                action='skipped',
                message="Component missing location info"
            )
        
        # Get component type - handle both string and enum types
        comp_type = getattr(component, 'type', 'function')
        if hasattr(comp_type, 'value'):
            comp_type = comp_type.value
        
        return self.insert_single_docstring(
            component_id=getattr(component, 'id', 'unknown'),
            docstring=docstring_data.get('docstring', ''),
            file_path=file_path,
            start_line=start_line,
            component_type=comp_type,
            has_existing_docstring=bool(getattr(component, 'existing_docstring', None))
        )
    
    # ========== BATCH INSERTION MODE ==========
    
    def load_writer_outputs(self) -> Dict[str, Any]:
        """Load all writer output files and merge them"""
        all_docstrings = {}
        
        if not self.writer_output_dir.exists():
            logger.warning(f"Writer output directory not found: {self.writer_output_dir}")
            return all_docstrings
        
        for json_file in self.writer_output_dir.glob("*_writer_output.json"):
            try:
                data = self.file_handler.read_json(json_file)
                all_docstrings.update(data)
                logger.info(f"Loaded {len(data)} docstrings from {json_file.name}")
            except Exception as e:
                logger.warning(f"Failed to load {json_file}: {e}")
        
        return all_docstrings
    
    def prepare_insertions(
        self,
        docstrings: Dict[str, Any]
    ) -> List[InsertionPoint]:
        """
        Prepare insertion points by matching docstrings with component locations.
        
        Args:
            docstrings: Dictionary of component_id -> docstring data
            
        Returns:
            List of InsertionPoint objects sorted by file and line number
        """
        insertion_points = []
        
        for component_id, doc_data in docstrings.items():
            # Get component location from component data (reader output)
            if component_id not in self.component_data:
                logger.debug(f"Component not in data: {component_id}")
                continue
            
            component = self.component_data[component_id]
            component_type = component.get('type', 'function')
            
            # Skip global variables - they don't have docstrings
            if component_type == 'global_variable':
                continue
            
            # Get location info - support both reader output and IR formats
            location = component.get('location', {})
            if location:
                # Reader output format: location.file_path, location.start_line
                file_path = location.get('file_path', '')
                start_line = location.get('start_line', 0)
            else:
                # IR format: file_path, start_line at top level
                file_path = component.get('file_path', '')
                start_line = component.get('start_line', 0)
            
            has_docstring = component.get('has_docstring', False) or bool(component.get('existing_docstring'))
            
            if not file_path or start_line == 0:
                logger.debug(f"Missing location for: {component_id}")
                continue
            
            # Get the docstring text
            docstring = doc_data.get('docstring', '')
            if not docstring:
                continue
            
            insertion_points.append(InsertionPoint(
                component_id=component_id,
                file_path=file_path,
                start_line=start_line,
                component_type=component_type,
                docstring=docstring,
                has_existing_docstring=has_docstring,
                language=self._detect_language(file_path)
            ))
        
        # Sort by file path, then by line number (descending for bottom-up insertion)
        insertion_points.sort(key=lambda x: (x.file_path, -x.start_line))
        
        logger.info(f"Prepared {len(insertion_points)} insertion points")
        return insertion_points
    
    def _get_indentation(self, line: str) -> str:
        """Extract leading whitespace from a line"""
        return line[:len(line) - len(line.lstrip())]
    
    def _format_docstring(
        self,
        docstring: str,
        base_indent: str,
        component_type: str,
        language: str = "python"
    ) -> List[str]:
        """
        Format docstring with proper indentation and language-specific syntax.
        
        Supports multiple languages:
        - Python: Triple-quoted strings
        - JavaScript/TypeScript: JSDoc /** */ or line comments
        - Java: JavaDoc /** */
        - C/C++/C#: Multi-line /* */ or line comments //
        - Go: Line comments //
        - And others
        
        Args:
            docstring: Raw docstring text
            base_indent: Base indentation for the component body
            component_type: Type of component (class, function, method)
            language: Programming language (auto-detect if not provided)
            
        Returns:
            List of formatted docstring lines
        """
        # Add body indentation (one level deeper than definition)
        body_indent = base_indent + "    "
        
        lines = docstring.strip().split('\n')
        
        # Select comment style based on language
        if language in ['javascript', 'typescript', 'java', 'cpp', 'c', 'csharp']:
            # Use /** */ block comment style for C-like languages
            return self._format_block_comment(lines, body_indent)
        elif language in ['go', 'rust', 'ruby', 'swift']:
            # Use // or # line comments
            return self._format_line_comment(lines, body_indent, language)
        else:
            # Default to Python triple-quoted strings
            return self._format_python_docstring(lines, body_indent)
    
    def _format_python_docstring(self, lines: List[str], indent: str) -> List[str]:
        """Format docstring as Python triple-quoted string."""
        if len(lines) == 1:
            return [f'{indent}\"\"\"{lines[0]}\"\"\"']
        else:
            formatted = [f'{indent}"""']
            for line in lines:
                if line.strip():
                    formatted.append(f'{indent}{line}')
                else:
                    formatted.append('')
            formatted.append(f'{indent}"""')
            return formatted
    
    def _format_block_comment(self, lines: List[str], indent: str) -> List[str]:
        """Format docstring as /** */ block comment (JavaScript, Java, C-style)."""
        if len(lines) == 1:
            # Single-line block comment
            return [f'{indent}/** {lines[0]} */']
        else:
            # Multi-line block comment
            formatted = [f'{indent}/**']
            for line in lines:
                if line.strip():
                    formatted.append(f'{indent} * {line}')
                else:
                    formatted.append(f'{indent} *')
            formatted.append(f'{indent} */')
            return formatted
    
    def _format_line_comment(self, lines: List[str], indent: str, language: str) -> List[str]:
        """Format docstring as line comments (Go, Rust, Ruby, etc.)."""
        # Choose comment character based on language
        comment_char = '// ' if language in ['go', 'rust'] else '# '
        
        formatted = []
        for line in lines:
            if line.strip():
                formatted.append(f'{indent}{comment_char}{line}')
            else:
                formatted.append('')  # Preserve blank lines
        
        return formatted

    
    def _find_docstring_insert_position(
        self,
        lines: List[str],
        start_line: int,
        component_type: str
    ) -> Tuple[int, int, str]:
        """
        Find where to insert/replace docstring in source code.
        
        Args:
            lines: Source file lines
            start_line: Component start line (1-indexed)
            component_type: Type of component
            
        Returns:
            Tuple of (insert_line_index, existing_end_index, base_indentation)
            If existing_end_index > insert_line_index, there's an existing docstring to replace
        """
        start_idx = start_line - 1  # Convert to 0-indexed
        
        if start_idx >= len(lines):
            return start_idx, start_idx, ""
        
        # Find the definition line (def/class)
        def_line_idx = start_idx
        def_line = lines[def_line_idx]
        base_indent = self._get_indentation(def_line)
        
        # Handle multi-line definitions (find the closing colon)
        while def_line_idx < len(lines) and ':' not in lines[def_line_idx]:
            def_line_idx += 1
        
        # Insert position is right after the definition line
        insert_idx = def_line_idx + 1
        
        if insert_idx >= len(lines):
            return insert_idx, insert_idx, base_indent
        
        # Check for existing docstring
        next_line = lines[insert_idx].strip()
        existing_end_idx = insert_idx
        
        if next_line.startswith('"""') or next_line.startswith("'''"):
            quote = next_line[:3]
            
            if next_line.count(quote) >= 2 and len(next_line) > 6:
                # Single line docstring
                existing_end_idx = insert_idx + 1
            else:
                # Multi-line docstring - find the end
                existing_end_idx = insert_idx + 1
                while existing_end_idx < len(lines):
                    if quote in lines[existing_end_idx]:
                        existing_end_idx += 1
                        break
                    existing_end_idx += 1
        
        return insert_idx, existing_end_idx, base_indent
    
    def insert_docstrings(
        self,
        insertion_points: List[InsertionPoint]
    ) -> List[InsertionResult]:
        """
        Insert docstrings into source files.
        
        Args:
            insertion_points: List of prepared insertion points
            
        Returns:
            List of insertion results
        """
        results = []
        
        # Group insertions by file
        files_to_modify: Dict[str, List[InsertionPoint]] = {}
        for point in insertion_points:
            if point.file_path not in files_to_modify:
                files_to_modify[point.file_path] = []
            files_to_modify[point.file_path].append(point)
        
        for file_path, points in files_to_modify.items():
            file_results = self._process_file(file_path, points)
            results.extend(file_results)
        
        return results
    
    def _process_file(
        self,
        file_path_str: str,
        insertion_points: List[InsertionPoint]
    ) -> List[InsertionResult]:
        """Process a single file with multiple insertion points"""
        results = []
        
        # Handle both absolute and relative paths
        full_path = Path(file_path_str)
        
        if not full_path.exists():
            for point in insertion_points:
                results.append(InsertionResult(
                    component_id=point.component_id,
                    file_path=file_path_str,
                    success=False,
                    action='skipped',
                    message=f"File not found: {full_path}"
                ))
            return results
        
        try:
            # Read file content
            content = self.file_handler.read_file(full_path)
            lines = content.split('\n')
            
            # Create backup if enabled
            if self.backup:
                backup_path = full_path.with_suffix(full_path.suffix + '.bak')
                self.file_handler.write_file(backup_path, content)
            
            # Sort points by line number descending (process bottom-up)
            points_sorted = sorted(insertion_points, key=lambda x: -x.start_line)
            
            # Process each insertion point
            for point in points_sorted:
                insert_idx, existing_end_idx, base_indent = self._find_docstring_insert_position(
                    lines, point.start_line, point.component_type
                )
                
                has_existing = existing_end_idx > insert_idx
                
                if has_existing and not self.replace_existing:
                    results.append(InsertionResult(
                        component_id=point.component_id,
                        file_path=file_path_str,
                        success=True,
                        action='skipped',
                        message="Existing docstring preserved"
                    ))
                    continue
                
                # Format the new docstring with language-aware syntax
                docstring_lines = self._format_docstring(
                    point.docstring,
                    base_indent,
                    point.component_type,
                    point.language
                )
                
                if has_existing:
                    # Replace existing docstring
                    lines = lines[:insert_idx] + docstring_lines + lines[existing_end_idx:]
                    action = 'replaced'
                else:
                    # Insert new docstring
                    lines = lines[:insert_idx] + docstring_lines + lines[insert_idx:]
                    action = 'inserted'
                
                results.append(InsertionResult(
                    component_id=point.component_id,
                    file_path=file_path_str,
                    success=True,
                    action=action,
                    message=f"Docstring {action} at line {insert_idx + 1}"
                ))
            
            # Write modified content back
            new_content = '\n'.join(lines)
            self.file_handler.write_file(full_path, new_content)
            
            logger.info(f"Modified {full_path.name}: {len(points_sorted)} docstrings processed")
            
        except Exception as e:
            logger.error(f"Error processing {file_path_str}: {e}")
            for point in insertion_points:
                results.append(InsertionResult(
                    component_id=point.component_id,
                    file_path=file_path_str,
                    success=False,
                    action='error',
                    message=str(e)
                ))
        
        return results
    
    def run(self) -> Dict[str, Any]:
        """
        Execute the full docstring insertion process.
        
        Returns:
            Summary of insertion results
        """
        logger.info("Starting docstring insertion process")
        
        # Load all writer outputs
        docstrings = self.load_writer_outputs()
        
        if not docstrings:
            logger.warning("No docstrings found to insert")
            return {'success': False, 'message': 'No docstrings found'}
        
        # Prepare insertion points
        insertion_points = self.prepare_insertions(docstrings)
        
        if not insertion_points:
            logger.warning("No valid insertion points found")
            return {'success': False, 'message': 'No valid insertion points'}
        
        # Insert docstrings
        results = self.insert_docstrings(insertion_points)
        
        # Summarize results
        summary = {
            'total': len(results),
            'inserted': sum(1 for r in results if r.action == 'inserted'),
            'replaced': sum(1 for r in results if r.action == 'replaced'),
            'skipped': sum(1 for r in results if r.action == 'skipped'),
            'errors': sum(1 for r in results if r.action == 'error'),
            'files_modified': len(set(r.file_path for r in results if r.success)),
            'results': [
                {
                    'component_id': r.component_id,
                    'file': r.file_path,
                    'action': r.action,
                    'success': r.success,
                    'message': r.message
                }
                for r in results
            ]
        }
        
        logger.info(
            f"Docstring insertion complete: "
            f"{summary['inserted']} inserted, "
            f"{summary['replaced']} replaced, "
            f"{summary['skipped']} skipped, "
            f"{summary['errors']} errors"
        )
        
        return summary


def insert_docstrings_to_source(
    writer_output_dir: str,
    component_data_file: str,
    backup: bool = True,
    replace_existing: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to insert docstrings into source files.
    
    Args:
        writer_output_dir: Directory containing writer output JSON files
        component_data_file: Path to component data JSON (reader output)
        backup: Whether to create backups
        replace_existing: Whether to replace existing docstrings
        
    Returns:
        Summary of insertion results
    """
    inserter = DocstringInserter(
        writer_output_dir=Path(writer_output_dir),
        component_data_file=Path(component_data_file),
        backup=backup,
        replace_existing=replace_existing
    )
    
    return inserter.run()
