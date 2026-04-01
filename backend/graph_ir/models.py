"""
Intermediate Representation (IR) Models for Code Analysis

This module defines Pydantic models for representing parsed code structure,
control flow, data dependencies, and graph outputs.
"""

from __future__ import annotations
from typing import List, Dict, Optional, Set, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum


# =============================================================================
# Enums for Node Types
# =============================================================================

class StatementType(str, Enum):
    """Types of statements in the IR"""
    ENTRY = "entry"
    EXIT = "exit"
    ASSIGNMENT = "assignment"
    EXPRESSION = "expression"
    RETURN = "return"
    IF = "if"
    ELIF = "elif"
    ELSE = "else"
    FOR = "for"
    WHILE = "while"
    TRY = "try"
    EXCEPT = "except"
    FINALLY = "finally"
    WITH = "with"
    RAISE = "raise"
    ASSERT = "assert"
    PASS = "pass"
    BREAK = "break"
    CONTINUE = "continue"
    CALL = "call"
    IMPORT = "import"
    CLASS_DEF = "class_def"
    FUNCTION_DEF = "function_def"
    YIELD = "yield"
    AWAIT = "await"


class DependencyType(str, Enum):
    """Types of dependencies in PDG"""
    DATA = "data"           # Data dependency (def-use)
    CONTROL = "control"     # Control dependency
    CALL = "call"           # Function call dependency
    IMPORT = "import"       # Import dependency


class ComponentType(str, Enum):
    """Types of code components"""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"


# =============================================================================
# Basic IR Elements
# =============================================================================

class SourceLocation(BaseModel):
    """Location in source code"""
    line: int
    col: int
    end_line: Optional[int] = None
    end_col: Optional[int] = None


class Variable(BaseModel):
    """Represents a variable reference"""
    name: str
    scope: str = "local"  # local, global, nonlocal, parameter
    line: Optional[int] = None
    is_definition: bool = False
    is_use: bool = False


class FunctionCall(BaseModel):
    """Represents a function call"""
    name: str
    module: Optional[str] = None  # For qualified calls like os.path.join
    args: List[str] = Field(default_factory=list)
    kwargs: List[str] = Field(default_factory=list)
    line: int
    is_method: bool = False
    receiver: Optional[str] = None  # For method calls: obj.method()


class Import(BaseModel):
    """Represents an import statement"""
    module: str
    names: List[str] = Field(default_factory=list)  # from x import names
    alias: Optional[str] = None
    line: int
    is_from: bool = False


# =============================================================================
# IR Statement Node
# =============================================================================

class IRStatement(BaseModel):
    """
    Represents a single statement in the Intermediate Representation.
    This is the core building block for CFG and PDG construction.
    """
    id: str
    type: StatementType
    line: int
    end_line: Optional[int] = None
    code: str  # Original source code snippet

    # Variable information
    definitions: List[Variable] = Field(default_factory=list)  # Variables defined
    uses: List[Variable] = Field(default_factory=list)  # Variables used

    # Control flow information
    condition: Optional[str] = None  # For if/while/for conditions
    is_branch: bool = False
    branch_true: Optional[str] = None  # Next statement ID if true
    branch_false: Optional[str] = None  # Next statement ID if false

    # Function call information
    calls: List[FunctionCall] = Field(default_factory=list)

    # Loop-specific
    is_loop_header: bool = False
    loop_body_start: Optional[str] = None
    loop_exit: Optional[str] = None

    # Exception handling
    exception_handlers: List[str] = Field(default_factory=list)
    finally_block: Optional[str] = None


# =============================================================================
# Function/Method IR
# =============================================================================

class ParameterInfo(BaseModel):
    """Function parameter information"""
    name: str
    annotation: Optional[str] = None
    default: Optional[str] = None
    is_args: bool = False
    is_kwargs: bool = False


class FunctionIR(BaseModel):
    """
    Complete IR for a function or method.
    Contains all statements and metadata needed for CFG/PDG construction.
    """
    id: str
    name: str
    qualified_name: str  # module.ClassName.method_name
    type: ComponentType
    file_path: str

    # Location
    start_line: int
    end_line: int

    # Signature
    parameters: List[ParameterInfo] = Field(default_factory=list)
    return_annotation: Optional[str] = None
    decorators: List[str] = Field(default_factory=list)

    # Docstring
    docstring: Optional[str] = None

    # IR Statements (ordered)
    statements: List[IRStatement] = Field(default_factory=list)

    # Parent information (for methods)
    parent_class: Optional[str] = None
    is_static: bool = False
    is_classmethod: bool = False
    is_property: bool = False

    # Dependencies
    calls: List[FunctionCall] = Field(default_factory=list)
    imports_used: List[str] = Field(default_factory=list)

    # Variables summary
    local_variables: List[str] = Field(default_factory=list)
    global_variables: List[str] = Field(default_factory=list)
    closure_variables: List[str] = Field(default_factory=list)


# =============================================================================
# Class IR
# =============================================================================

class ClassIR(BaseModel):
    """IR representation of a class"""
    id: str
    name: str
    qualified_name: str
    file_path: str

    start_line: int
    end_line: int

    bases: List[str] = Field(default_factory=list)
    decorators: List[str] = Field(default_factory=list)
    docstring: Optional[str] = None

    # Methods
    methods: List[str] = Field(default_factory=list)  # FunctionIR IDs

    # Class-level attributes
    class_variables: List[Variable] = Field(default_factory=list)

    # Instance attributes (found in __init__)
    instance_attributes: List[str] = Field(default_factory=list)


# =============================================================================
# Module IR
# =============================================================================

class ModuleIR(BaseModel):
    """IR representation of a Python module (file)"""
    id: str
    file_path: str
    module_name: str

    # Imports
    imports: List[Import] = Field(default_factory=list)

    # Top-level definitions
    functions: List[str] = Field(default_factory=list)  # FunctionIR IDs
    classes: List[str] = Field(default_factory=list)  # ClassIR IDs

    # Module-level variables
    module_variables: List[Variable] = Field(default_factory=list)

    # Module-level statements
    statements: List[IRStatement] = Field(default_factory=list)


# =============================================================================
# Repository IR
# =============================================================================

class RepositoryIR(BaseModel):
    """Complete IR for an entire repository"""
    root_path: str

    # All IR components indexed by ID
    modules: Dict[str, ModuleIR] = Field(default_factory=dict)
    functions: Dict[str, FunctionIR] = Field(default_factory=dict)
    classes: Dict[str, ClassIR] = Field(default_factory=dict)

    # Cross-reference maps
    file_to_module: Dict[str, str] = Field(default_factory=dict)
    function_to_file: Dict[str, str] = Field(default_factory=dict)
    class_to_file: Dict[str, str] = Field(default_factory=dict)


# =============================================================================
# Graph Output Models (for API responses)
# =============================================================================

class GraphNode(BaseModel):
    """Node in a graph (CFG, PDG, DAG)"""
    id: str
    label: str
    type: str

    # Position hints for layout (optional, frontend can override)
    x: Optional[float] = None
    y: Optional[float] = None

    # Metadata
    line: Optional[int] = None
    code: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Edge in a graph"""
    id: str
    source: str  # Node ID
    target: str  # Node ID
    type: str    # Edge type (e.g., "control", "data", "true", "false")
    label: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Graph(BaseModel):
    """Generic graph structure for API responses"""
    id: str
    name: str
    type: Literal["cfg", "pdg", "dag", "hpg"]

    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)

    # Graph metadata
    component_id: Optional[str] = None
    component_name: Optional[str] = None
    file_path: Optional[str] = None

    # Statistics
    node_count: int = 0
    edge_count: int = 0

    metadata: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context):
        self.node_count = len(self.nodes)
        self.edge_count = len(self.edges)


# =============================================================================
# API Response Models
# =============================================================================

class ComponentInfo(BaseModel):
    """Brief info about a code component"""
    id: str
    name: str
    type: ComponentType
    file_path: str
    start_line: int
    end_line: int
    parent_class: Optional[str] = None


class GraphListResponse(BaseModel):
    """Response for listing available graphs"""
    success: bool = True
    components: List[ComponentInfo] = Field(default_factory=list)
    total: int = 0


class GraphResponse(BaseModel):
    """Response containing a single graph"""
    success: bool = True
    data: Optional[Graph] = None
    message: Optional[str] = None


class MultiGraphResponse(BaseModel):
    """Response containing multiple graphs"""
    success: bool = True
    data: Dict[str, Graph] = Field(default_factory=dict)
    message: Optional[str] = None


class ParseStatusResponse(BaseModel):
    """Response for repository parse status"""
    success: bool = True
    is_parsed: bool = False
    file_count: int = 0
    function_count: int = 0
    class_count: int = 0
    last_parsed: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
