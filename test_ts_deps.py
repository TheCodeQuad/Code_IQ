from backend.navigator.core.repository_parser import RepositoryParser
import json
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

parser = RepositoryParser('ts-navigator-mini/src')
components = parser.parse()

print(f'\n=== EXTRACTION RESULTS ===')
print(f'Total components: {len(components)}')

# Filter functions and arrow functions
funcs = [c for c in components.values() if c.type in ('function', 'arrow_function', 'method')]
print(f'Functions/Methods: {len(funcs)}')

# Check for global variables
globals_vars = [c for c in components.values() if c.type == 'global_variable']
print(f'Global variables: {len(globals_vars)}')

print(f'\n=== GLOBAL VARIABLES ===')
for gv in globals_vars[:5]:
    print(f'  {gv.id}')

print(f'\n=== SAMPLE FUNCTIONS WITH DEPENDENCIES ===')
for func in funcs[:5]:
    print(f'\n{func.id} ({func.type}):')
    identifiers = getattr(func, 'identifiers', [])
    print(f'  Identifiers: {identifiers[:10]}')
    print(f'  Depends on: {list(func.depends_on)[:10]}')
    
    # Check if depends on globals
    has_globals = any('ENVIRONMENT' in d or 'API_URL' in d or 'PI' in d for d in func.depends_on)
    print(f'  Has global deps: {has_globals}')
