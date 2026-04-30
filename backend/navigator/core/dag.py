from collections import defaultdict
import re
from typing import Dict

from backend.models.code_component import CodeComponent

def build_dag(components):
    """
    components: Dict[str, CodeComponent]
    returns: adjacency list {node: set(dependents)}
    """
    dag = defaultdict(set)
    for comp in components.values():
        for dep in comp.depends_on:
            dag[dep].add(comp.id)
    return dag

class DataFlowAnalyzer:
    """Analyze how state flows through components"""
    
    def __init__(self, components: Dict[str, CodeComponent]):
        self.components = components
    
    def analyze_global_variable_usage(self, var_id: str) -> Dict:
        """Analyze how a global variable is used"""
        var = self.components[var_id]
        usage = {
            'var_id': var_id,
            'var_name': var.name,
            'type': var.return_type,
            'written_by': [],
            'read_by': [],
            'deleted_by': [],
            'modification_pattern': None,
            'coordination_with': []  # Other globals it works with
        }
        
        # Scan all components
        for comp_id, comp in self.components.items():
            if var_id not in comp.depends_on:
                continue
            
            # Analyze the source code
            if self._is_writing_to(comp.source_code, var.name):
                usage['written_by'].append(comp_id)
            elif self._is_reading_from(comp.source_code, var.name):
                usage['read_by'].append(comp_id)
            elif self._is_deleting(comp.source_code, var.name):
                usage['deleted_by'].append(comp_id)
        
        # Detect pattern
        if usage['written_by'] and usage['read_by']:
            usage['modification_pattern'] = 'shared_state'
        elif len(usage['written_by']) == 1:
            usage['modification_pattern'] = 'producer_consumer'
        
        return usage
    
    def _is_writing_to(self, source: str, var_name: str) -> bool:
        """Check if code modifies the variable"""
        patterns = [
            rf'{var_name}\s*\[.*\]\s*=',  # dict[key] = value
            rf'{var_name}\s*\.add\(',      # set.add()
            rf'{var_name}\s*\.append\(',   # list.append()
            rf'{var_name}\s*\.pop\(',      # dict/list.pop()
        ]
        return any(re.search(p, source) for p in patterns)
    
    def _is_reading_from(self, source: str, var_name: str) -> bool:
        """Check if code reads the variable"""
        return f'in {var_name}' in source or f'{var_name}\[' in source
    
    def _is_deleting(self, source: str, var_name: str) -> bool:
        """Check if code deletes from the variable"""
        patterns = [
            rf'{var_name}\.discard\(',
            rf'{var_name}\.remove\(',
            rf'del\s+{var_name}\[',
            rf'{var_name}\.pop\(',
        ]
        return any(re.search(p, source) for p in patterns)

