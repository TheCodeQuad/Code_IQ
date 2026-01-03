import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, HttpUrl, Field

from navigator.core.repo_loader import clone_repo
from navigator.core.repository_parser import RepositoryParser
from navigator.core.topo import (
    build_graph_from_components,
    topological_sort,
    dependency_first_dfs,
    resolve_cycles
)
from agents.orchestrator.orchestrator import Orchestrator
from backend.pipeline.pipeline import run_pipeline
from backend.utils.file_handler import FileHandler
# ============================================================================
# FASTAPI APP SETUP
# ============================================================================

app = FastAPI(
    title="Code Dependency Analyzer API",
    description="Analyze code repositories and extract dependency graphs",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# OUTPUT DIRECTORY
# ============================================================================

def find_project_root(marker="requirements.txt"):
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / marker).exists():
            return parent
    # fallback: go up 3 levels (backend/app.py -> backend -> Code_IQ)
    return current.parents[2]

PROJECT_ROOT = find_project_root()
OUTPUT_DIR = PROJECT_ROOT / "data" / "intermediate" / "navigator_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AnalyzeRequest(BaseModel):
    repo_url: HttpUrl = Field(..., description="GitHub repository URL")
    save_json: bool = Field(default=True, description="Save results to JSON file")
    include_source: bool = Field(default=True, description="Include source code in response")

class ComponentInfo(BaseModel):
    id: str
    language: str
    type: str
    file_path: str
    module_path: str
    depends_on: List[str]
    start_line: int
    end_line: int
    has_docstring: bool
    docstring: str
    source_code: Optional[str] = None

class AnalysisStats(BaseModel):
    total_components: int
    functions: int
    classes: int
    methods: int
    global_variables: int
    components_with_docstrings: int
    components_without_docstrings: int
    total_dependencies: int
    max_dependencies: int
    avg_dependencies: float

class AnalyzeResponse(BaseModel):
    success: bool
    repo_url: str
    timestamp: str
    stats: AnalysisStats
    components: Dict[str, ComponentInfo]
    topological_order: List[str]
    dfs_order: List[str]
    dag: Dict[str, List[str]]
    formatted_output: Optional[str] = None
    output_file: Optional[str] = None
    message: Optional[str] = None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_stats(components: dict) -> AnalysisStats:
    """Calculate statistics from components"""
    stats = {
        "total_components": len(components),
        "functions": 0,
        "classes": 0,
        "methods": 0,
        "global_variables": 0,
        "components_with_docstrings": 0,
        "components_without_docstrings": 0,
        "total_dependencies": 0,
        "max_dependencies": 0,
        "avg_dependencies": 0.0
    }
    
    dep_counts = []
    
    for comp in components.values():
        # Count by type
        comp_type = comp.type
        if comp_type == "function":
            stats["functions"] += 1
        elif comp_type == "class":
            stats["classes"] += 1
        elif comp_type == "method":
            stats["methods"] += 1
        elif comp_type == "global_variable":
            stats["global_variables"] += 1
        
        # Count docstrings
        # if comp.has_docstring:
        #     stats["components_with_docstrings"] += 1
        # else:
        #     stats["components_without_docstrings"] += 1
        
        # Count dependencies
        dep_count = len(comp.depends_on)
        dep_counts.append(dep_count)
        stats["total_dependencies"] += dep_count
        
        if dep_count > stats["max_dependencies"]:
            stats["max_dependencies"] = dep_count
    
    # Calculate average
    if dep_counts:
        stats["avg_dependencies"] = round(sum(dep_counts) / len(dep_counts), 2)
    
    return AnalysisStats(**stats)

def save_analysis_to_json(components_dict: dict, repo_name: str) -> str:
    """Save analysis results to JSON file in the required format"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{repo_name}_{timestamp}.json"
    filepath = OUTPUT_DIR / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(components_dict, f, indent=2, ensure_ascii=False)
    
    return str(filepath)

def extract_repo_name(repo_url: str) -> str:
    """Extract repository name from URL"""
    # Handle different URL formats
    url = str(repo_url).rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url.split("/")[-1]

def format_analysis_output(components: dict, graph: dict, dfs_order: list, topo_order: list) -> str:
    """Format analysis output as a string for UI display"""
    output_lines = []
    
    # Components section
    output_lines.append("Components:")
    for comp_id in sorted(components.keys()):
        output_lines.append(f"  {comp_id}")
    
    # DAG section
    output_lines.append("DAG:")
    for comp_id, dependencies in sorted(graph.items()):
        if dependencies:  # Only show components that have dependencies
            deps_str = ", ".join([f"'{dep}'" for dep in sorted(dependencies)])
            output_lines.append(f"{comp_id} -> [{deps_str}]")
    
    # DFS Order section
    output_lines.append("Dependency-first DFS order:")
    for comp_id in dfs_order:
        output_lines.append(comp_id)
    
    # Topological Order section
    output_lines.append("Topological Order:")
    for comp_id in topo_order:
        output_lines.append(comp_id)
    
    return "\n".join(output_lines)

def print_analysis_summary(components: dict, graph: dict, dfs_order: list, topo_order: list):
    """Print formatted analysis summary to console"""
    print("\n" + "="*80)
    print("ANALYSIS SUMMARY")
    print("="*80)
    
    # Print Components
    print("\nComponents:")
    for comp_id in sorted(components.keys()):
        print(f"  {comp_id}")
    
    # Print DAG
    print("\nDAG:")
    for comp_id, dependencies in sorted(graph.items()):
        if dependencies:  # Only show components that have dependencies
            deps_str = ", ".join([f"'{dep}'" for dep in sorted(dependencies)])
            print(f"{comp_id} -> [{deps_str}]")
    
    # Print DFS Order
    print("\nDependency-first DFS order:")
    for comp_id in dfs_order:
        print(f"{comp_id}")
    
    # Print Topological Order
    print("\nTopological Order:")
    for comp_id in topo_order:
        print(f"{comp_id}")
    
    print("\n" + "="*80 + "\n")

def truncate_source_code(source_code: str, max_length: int = 500) -> str:
    """Truncate source code if it's too long"""
    if len(source_code) <= max_length:
        return source_code
    return source_code[:max_length] + "..."

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Code Dependency Analyzer",
        "version": "1.0.0",
        "endpoints": {
            "analyze": "/analyze",
            "health": "/health",
            "download": "/download/{filename}",
            "files": "/files"
        }
    }

@app.get("/health")
def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "output_dir": str(OUTPUT_DIR),
        "output_dir_exists": OUTPUT_DIR.exists()
    }

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_repo(req: AnalyzeRequest):
    """
    Analyze a Git repository and extract dependency graph and documentation
    """
    try:
        # Extract repo name for naming
        repo_name = extract_repo_name(str(req.repo_url))
        
        # Step 1: Clone repository
        print(f"📥 Cloning repository: {req.repo_url}")
        repo_path = clone_repo(str(req.repo_url))
        
        # Use the pipeline function
        print(f"🚀 Running documentation pipeline for: {repo_path}")
        result = run_pipeline(repo_path)
        components = result["components"]
        # print(components)
        # print("Reader output (components):", result["components"]) 
        reader_output_path = PROJECT_ROOT / "data" / "intermediate" / "agent_output" / "reader" / f"{repo_name}_reader_output.json"
        FileHandler.write_json(reader_output_path,{k: FileHandler.serialize_component(v) for k, v in components.items()})

        
        # Print reader output like in main.py
        # for idx, component in enumerate(components.values()):
        #     print(f"Component {idx}: type={type(component)}, value={component}")
        graph = result["graph"]
        topo_order = result["topological_order"]
        dfs_order = result["dfs_order"]
        docs = result["documentation"]

        # Prepare component data for response
        components_dict = {}
        for comp_id, comp in components.items():
            comp_info = {
                "id": comp.id,
                "language": comp.language,
                "type": comp.type.value if hasattr(comp.type, "value") else comp.type,
                "file_path": getattr(comp, "file_path", ""),
                "module_path": getattr(comp, "module_path", ""),
                "depends_on": list(getattr(comp, "depends_on", [])),
                "start_line": getattr(comp, "start_line", 0),
                "end_line": getattr(comp, "end_line", 0),
                "has_docstring": getattr(comp, "has_docstring", False),
                "docstring": getattr(comp, "docstring", ""),
            }
            if req.include_source and getattr(comp, "source_code", None):
                comp_info["source_code"] = truncate_source_code(comp.source_code)
            components_dict[comp_id] = comp_info

        formatted_output = format_analysis_output(components, graph, dfs_order, topo_order)
        stats = calculate_stats(components)

        return AnalyzeResponse(
            success=True,
            repo_url=str(req.repo_url),
            timestamp=datetime.now().isoformat(),
            stats=stats,
            components=components_dict,
            topological_order=topo_order,
            dfs_order=dfs_order,
            dag={k: list(v) for k, v in graph.items()},
            formatted_output=formatted_output,
            output_file=None,
            message="Analysis and documentation complete.",
            documentation=[doc.dict() if hasattr(doc, "dict") else str(doc) for doc in docs]
        )
        
    except Exception as e:
        print(f"❌ Error during analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )

@app.get("/download/{filename}")
def download_file(filename: str):
    """Download a previously generated JSON file"""
    filepath = OUTPUT_DIR / filename
    
    if not filepath.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File {filename} not found"
        )
    
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/json"
    )

@app.get("/files")
def list_files():
    """List all available output files"""
    files = []
    for filepath in OUTPUT_DIR.glob("*.json"):
        stat = filepath.stat()
        files.append({
            "filename": filepath.name,
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    
    return {
        "output_dir": str(OUTPUT_DIR),
        "total_files": len(files),
        "files": sorted(files, key=lambda x: x["modified"], reverse=True)
    }

@app.delete("/files/{filename}")
def delete_file(filename: str):
    """Delete a specific output file"""
    filepath = OUTPUT_DIR / filename
    
    if not filepath.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File {filename} not found"
        )
    
    filepath.unlink()
    return {
        "success": True,
        "message": f"File {filename} deleted successfully"
    }

# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)