# """
# Script to insert generated docstrings into source files.

# Usage:
#     python scripts/insert_docstrings.py [--replace] [--no-backup]
    
# Options:
#     --replace    Replace existing docstrings (default: skip)
#     --no-backup  Don't create backup files (default: create backups)
# """
# import sys
# import argparse
# from pathlib import Path

# # Add project root to path
# project_root = Path(__file__).parent.parent
# sys.path.insert(0, str(project_root))

# from backend.utils.docstring_inserter import insert_docstrings_to_source
# from backend.utils.logger import get_logger

# logger = get_logger(__name__)


# def main():
#     parser = argparse.ArgumentParser(
#         description='Insert generated docstrings into source files'
#     )
#     parser.add_argument(
#         '--writer-dir',
#         type=str,
#         default='data/intermediate/agent_output/writer',
#         help='Directory containing writer output JSON files'
#     )
#     parser.add_argument(
#         '--component-data',
#         type=str,
#         default='data/intermediate/agent_output/reader/Token_Orchestrator_reader_output.json',
#         help='Path to component data JSON (reader output with file locations)'
#     )
#     parser.add_argument(
#         '--replace',
#         action='store_true',
#         help='Replace existing docstrings (default: skip)'
#     )
#     parser.add_argument(
#         '--no-backup',
#         action='store_true',
#         help='Skip creating backup files'
#     )
    
#     args = parser.parse_args()
    
#     # Resolve paths relative to project root
#     writer_dir = project_root / args.writer_dir
#     component_data = project_root / args.component_data
    
#     print(f"Docstring Insertion Tool")
#     print(f"========================")
#     print(f"Writer output dir: {writer_dir}")
#     print(f"Component data: {component_data}")
#     print(f"Replace existing: {args.replace}")
#     print(f"Create backups: {not args.no_backup}")
#     print()
    
#     # Run insertion
#     result = insert_docstrings_to_source(
#         writer_output_dir=str(writer_dir),
#         component_data_file=str(component_data),
#         backup=not args.no_backup,
#         replace_existing=args.replace
#     )
    
#     # Print results
#     print(f"\nResults:")
#     print(f"  Total components: {result.get('total', 0)}")
#     print(f"  Inserted: {result.get('inserted', 0)}")
#     print(f"  Replaced: {result.get('replaced', 0)}")
#     print(f"  Skipped: {result.get('skipped', 0)}")
#     print(f"  Errors: {result.get('errors', 0)}")
#     print(f"  Files modified: {result.get('files_modified', 0)}")
    
#     # Print detailed results if any errors
#     if result.get('errors', 0) > 0:
#         print(f"\nErrors:")
#         for r in result.get('results', []):
#             if r['action'] == 'error':
#                 print(f"  - {r['component_id']}: {r['message']}")
    
#     return 0 if result.get('errors', 0) == 0 else 1


# if __name__ == '__main__':
#     sys.exit(main())
