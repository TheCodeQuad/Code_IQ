"""Quick test to verify the completeness fix."""
import sys
sys.path.insert(0, 'c:\\CODEIQ\\Code_IQ')

from backend.evaluator.multilang_completeness import MultiLangCompletenessEvaluator
from backend.analysis.models import ComponentType

class MockComponent:
    pass

# Test function - should NOT require description
func = MockComponent()
func.type = ComponentType.FUNCTION
func.name = 'test_read_user'
func.is_public = True
func.is_private = False
func.parameters = []
func.return_type = None
func.source_code = 'def test_read_user(): pass'
func.metadata = {}
func.attributes = []

# Test class - SHOULD require description
cls = MockComponent()
cls.type = ComponentType.CLASS
cls.name = 'User'
cls.is_public = True
cls.is_private = False
cls.parameters = []
cls.return_type = None
cls.source_code = 'class User: pass'
cls.metadata = {}
cls.attributes = []

evaluator = MultiLangCompletenessEvaluator()

print("="*60)
print("Testing: Function without parameters/returns")
print("="*60)
required_func = evaluator._get_required_sections(func, 'python')
print(f"Required sections: {required_func}")
print(f"Expected: ['summary'] (no description!)")
print(f"PASS" if required_func == ['summary'] else f"FAIL - got {required_func}")

print()
print("="*60)
print("Testing: Class without attributes")
print("="*60)
required_cls = evaluator._get_required_sections(cls, 'python')
print(f"Required sections: {required_cls}")
print(f"Expected: ['summary', 'description']")
print(f"PASS" if 'description' in required_cls else f"FAIL - got {required_cls}")

print()
print("="*60)
print("Testing: Function with parameters")
print("="*60)
func_params = MockComponent()
func_params.type = ComponentType.FUNCTION
func_params.name = 'add'
func_params.is_public = True
func_params.is_private = False
func_params.parameters = [{'name': 'a'}, {'name': 'b'}]
func_params.return_type = 'int'
func_params.source_code = 'def add(a, b): return a + b'
func_params.metadata = {}
func_params.attributes = []

required_func_params = evaluator._get_required_sections(func_params, 'python')
print(f"Required sections: {required_func_params}")
print(f"Expected: ['summary', 'args', 'returns'] (no description!)")
print(f"PASS" if 'description' not in required_func_params and 'args' in required_func_params else f"FAIL")

print()
print("="*60)
print("Summary: Functions no longer require 'description' section!")
print("="*60)
