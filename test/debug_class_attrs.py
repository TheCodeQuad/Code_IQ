"""Debug class attribute type annotation detection"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.navigator.languages.python.adapter import PythonAdapter
from backend.navigator.languages.python.dependencies import resolve_dependencies

test_code = '''
from typing import List
from pydantic import BaseModel

class Answer(BaseModel):
    question_id: int
    alternative_id: int

class UserAnswer(BaseModel):
    user_id: int
    answers: List[Answer]
'''

adapter = PythonAdapter()
tree = adapter.parse(test_code)

# Extract components
components = adapter.extract_components(tree, test_code, "test.py", "test")

print("Components extracted:")
for cid, comp in components.items():
    print(f"  {cid}")

print("\n" + "="*60)
print("Testing dependency resolution for UserAnswer")
print("="*60)

user_answer = components.get("test.UserAnswer")
if user_answer:
    print(f"\nComponent: {user_answer.id}")
    print(f"Type: {user_answer.type.value}")
    print(f"Source code:\n{user_answer.source_code}\n")
    
    # Resolve dependencies
    deps = resolve_dependencies(user_answer, tree, test_code, components)
    print(f"Resolved dependencies: {deps}")
    
    if "test.Answer" in deps:
        print("✅ Correctly detected Answer dependency!")
    else:
        print("❌ Failed to detect Answer dependency")
        print(f"   Expected: test.Answer")
        print(f"   Got: {list(deps)}")

