"""
Prepare Multi-System Input for Truthfulness Evaluation

Converts writer output or evaluation results into the multi-system format
required by eval_truthfulness_multi_system.py

Usage:
    # From writer output (single system)
    python scripts/prepare_multi_system_input.py --writer-dir data/intermediate/agent_output/writer --system-name system_1
    
    # From completeness evaluation results (already multi-system)
    python scripts/prepare_multi_system_input.py --completeness data/validation/completeness_results.json
    
    # Combine multiple writer outputs (different systems)
    python scripts/prepare_multi_system_input.py --combine-dirs \\
        system_1=data/intermediate/agent_output/writer_v1 \\
        system_2=data/intermediate/agent_output/writer_v2 \\
        system_3=data/intermediate/agent_output/writer_v3
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def convert_writer_output(writer_dir: Path, system_name: str = "system_1") -> List[Dict[str, Any]]:
    """
    Convert writer agent output to multi-system format.
    
    Args:
        writer_dir: Directory containing writer output JSON files
        system_name: Name to assign to this system
        
    Returns:
        List of component dictionaries
    """
    components = []
    
    writer_files = list(writer_dir.glob("*.json"))
    print(f"Found {len(writer_files)} files in {writer_dir}")
    
    for writer_file in writer_files:
        try:
            with open(writer_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            component_id = data.get("component_id", writer_file.stem)
            docstring = data.get("docstring", data.get("generated_docstring", ""))
            language = data.get("language", "python")
            comp_type = data.get("type", data.get("component_type", "FUNCTION"))
            
            # Get file path
            file_path = data.get("file_path", "")
            if not file_path and "location" in data:
                location = data["location"]
                if isinstance(location, dict):
                    file_path = location.get("file_path", "")
            
            # Get name
            name = data.get("name", component_id.split(".")[-1])
            
            # Clean docstring (remove tags if present)
            import re
            docstring = re.sub(r'</?DOCSTRING>', '', docstring).strip()
            
            if docstring:
                component = {
                    "id": component_id,
                    "component_id": component_id,
                    "name": name,
                    "language": language,
                    "type": comp_type,
                    "file_path": file_path,
                    "docstring": docstring,
                    "system": system_name
                }
                
                # Add location if available
                if "location" in data:
                    component["location"] = data["location"]
                
                components.append(component)
        
        except Exception as e:
            print(f"Warning: Error processing {writer_file}: {e}")
    
    print(f"Converted {len(components)} components for {system_name}")
    return components


def convert_completeness_results(completeness_file: Path) -> Dict[str, List[Dict[str, Any]]]:
    """
    Convert completeness evaluation results to multi-system format.
    
    If the file already has system_1, system_2, etc., keep that structure.
    Otherwise, create system_1.
    """
    with open(completeness_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Check if already in multi-system format
    if isinstance(data, dict):
        system_keys = [k for k in data.keys() if k.startswith('system_')]
        if system_keys:
            print(f"File already in multi-system format with {len(system_keys)} systems")
            return data
    
    # Convert to system_1 format
    print("Converting to multi-system format as system_1")
    
    components = []
    
    if isinstance(data, dict) and "components" in data:
        components = data["components"]
    elif isinstance(data, list):
        components = data
    
    # Ensure required fields
    formatted_components = []
    for comp in components:
        if "docstring" in comp or "generated_docstring" in comp:
            formatted_comp = {
                "id": comp.get("id", comp.get("component_id", "unknown")),
                "component_id": comp.get("component_id", comp.get("id", "unknown")),
                "name": comp.get("name", "unknown"),
                "language": comp.get("language", "python"),
                "type": comp.get("type", comp.get("component_type", "FUNCTION")),
                "file_path": comp.get("file_path", ""),
                "docstring": comp.get("docstring", comp.get("generated_docstring", "")),
            }
            
            if "location" in comp:
                formatted_comp["location"] = comp["location"]
            
            formatted_components.append(formatted_comp)
    
    return {"system_1": formatted_components}


def combine_multiple_systems(system_dirs: Dict[str, Path]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Combine multiple writer output directories into multi-system format.
    
    Args:
        system_dirs: Dict mapping system_name to writer directory path
        
    Returns:
        Multi-system dictionary
    """
    result = {}
    
    for system_name, writer_dir in system_dirs.items():
        if not writer_dir.exists():
            print(f"Warning: Directory not found: {writer_dir}")
            continue
        
        components = convert_writer_output(writer_dir, system_name)
        result[system_name] = components
    
    return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Prepare multi-system input for truthfulness evaluation'
    )
    
    # Option 1: Single writer directory
    parser.add_argument(
        '--writer-dir',
        type=str,
        help='Directory containing writer output JSON files'
    )
    parser.add_argument(
        '--system-name',
        type=str,
        default='system_1',
        help='Name for this system (default: system_1)'
    )
    
    # Option 2: Completeness evaluation results
    parser.add_argument(
        '--completeness',
        type=str,
        help='Path to completeness evaluation results JSON'
    )
    
    # Option 3: Combine multiple directories
    parser.add_argument(
        '--combine-dirs',
        type=str,
        nargs='+',
        help='Combine multiple writer dirs: system_1=/path/to/writer1 system_2=/path/to/writer2'
    )
    
    # Output
    parser.add_argument(
        '--output',
        type=str,
        default='data/validation/completeness_evaluation_cleaned.json',
        help='Output file path'
    )
    
    args = parser.parse_args()
    
    output_path = project_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Determine which mode to use
    if args.writer_dir:
        # Single writer directory
        writer_dir = project_root / args.writer_dir
        if not writer_dir.exists():
            print(f"Error: Writer directory not found: {writer_dir}")
            return
        
        components = convert_writer_output(writer_dir, args.system_name)
        result = {args.system_name: components}
    
    elif args.completeness:
        # Completeness evaluation results
        completeness_file = project_root / args.completeness
        if not completeness_file.exists():
            print(f"Error: Completeness file not found: {completeness_file}")
            return
        
        result = convert_completeness_results(completeness_file)
    
    elif args.combine_dirs:
        # Multiple directories
        system_dirs = {}
        for entry in args.combine_dirs:
            if '=' in entry:
                system_name, dir_path = entry.split('=', 1)
                system_dirs[system_name] = project_root / dir_path
            else:
                print(f"Warning: Invalid format '{entry}'. Expected: system_name=/path/to/dir")
        
        if not system_dirs:
            print("Error: No valid system directories specified")
            return
        
        result = combine_multiple_systems(system_dirs)
    
    else:
        print("Error: Must specify --writer-dir, --completeness, or --combine-dirs")
        parser.print_help()
        return
    
    # Save result
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n✅ Created multi-system input file: {output_path}")
    print(f"\nSystems included:")
    for system_name, components in result.items():
        print(f"  - {system_name}: {len(components)} components")
    
    print(f"\nNow you can run:")
    print(f"python -m backend.eval_truthfulness_multi_system --input {args.output}")


if __name__ == "__main__":
    main()
