"""
Tests for Reader Agent
"""
from multiprocessing import context
import pytest
from backend.agents.reader_agent import ReaderAgent, ReaderOutput
from backend.agents.base_agent import AgentContext
from backend.models.code_component import CodeComponent, ComponentType, Location, Parameter

@pytest.fixture
def reader_agent():
    """Create reader agent instance"""
    return ReaderAgent()

@pytest.fixture
def simple_component():
    """Create a simple test component"""
    return CodeComponent(
        id="test.py:add",
        name="add",
        type=ComponentType.FUNCTION,
        location=Location("test.py", 1, 3),
        source_code="def add(x, y):\n    return x + y",
        signature="def add(x, y)",
        parameters=[
            Parameter("x", type_hint="int"),
            Parameter("y", type_hint="int")
        ],
        return_type="int",
        complexity=1,
        lines_of_code=2
    )

@pytest.fixture
def complex_component():
    """Create a complex test component"""
    return CodeComponent(
        id="test.py:process_data",
        name="process_data",
        type=ComponentType.FUNCTION,
        location=Location("test.py", 10, 50),
        source_code="""
def process_data(data, config):
    import numpy as np
    import pandas as pd
    
    # Complex processing logic
    result = []
    for item in data:
        if item['status'] == 'active':
            processed = transform(item)
            result.append(processed)
    
    return pd.DataFrame(result)
""",
        signature="def process_data(data, config)",
        parameters=[
            Parameter("data", type_hint="List[Dict]"),
            Parameter("config", type_hint="Dict")
        ],
        return_type="DataFrame",
        depends_on=["test.py:transform"],
        calls=["transform"],
        # FIX: Use full import statements as in the code
        imports=[
            "import numpy as np",
            "import pandas as pd"
        ],
        complexity=8,
        lines_of_code=40
    )

def test_reader_simple_component(reader_agent, simple_component):
    """Test reader agent with simple component"""
    context = AgentContext(component=simple_component)
    result = reader_agent.execute(context)
    
    assert result.is_success()
    assert isinstance(result.output, ReaderOutput)
    
    output = result.output
    assert output.component_id == simple_component.id
    assert output.complexity_assessment['complexity_level'] == 'simple'
    # Simple component may not need additional context
    # Depends on whether it's public

def test_reader_complex_component(reader_agent, complex_component):
    """Test reader agent with complex component"""
    context = AgentContext(component=complex_component)
    result = reader_agent.execute(context)
    
    assert result.is_success()
    
    output = result.output
    assert output.complexity_assessment['complexity_level'] in ['moderate', 'complex']
    assert output.needs_additional_context
    
    # Should have dependency requests
    dep_requests = [r for r in output.internal_requests if r.request_type == 'dependency']
    assert len(dep_requests) > 0
    
    # Should have external requests for numpy/pandas
    lib_requests = [r for r in output.external_requests if r.request_type == 'library']
    assert len(lib_requests) > 0

def test_reader_public_function(reader_agent):
    """Test that public functions get reference requests"""
    public_func = CodeComponent(
        id="api.py:calculate_tax",
        name="calculate_tax",
        type=ComponentType.FUNCTION,
        location=Location("api.py", 1, 10),
        source_code="def calculate_tax(amount, rate):\n    return amount * rate",
        signature="def calculate_tax(amount, rate)",
        complexity=2,
        lines_of_code=2
    )
    
    context = AgentContext(component=public_func)
    result = reader_agent.execute(context)
    
    output = result.output
    ref_requests = [r for r in output.internal_requests if r.request_type == 'reference']
    # Public functions should have reference requests
    assert len(ref_requests) > 0

external_requests = self._generate_external_requests(
    component,
    context.metadata.get('project_dag')
    )