import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, HttpUrl, Field

from .navigator.core.repo_loader import clone_repo, extract_repo_name as _extract_repo_name
from .navigator.core.repository_parser import RepositoryParser
from .navigator.core.topo import (
    build_graph_from_components,
    topological_sort,
    dependency_first_dfs,
    resolve_cycles
)

from .navigator.core.ir_export import export_ir
from .navigator.core.dag_export import export_dag
from backend.utils.file_handler import FileHandler
from backend.unified_evaluator import UnifiedEvaluator
from backend.utils.db import close_connection, ping as db_ping
from backend.utils.paths import DATA_ROOT
from backend.routes.repos import router as repos_router
from backend.routes.github_routes import router as github_router
from backend.routes.analysis_routes import router as analysis_router
from backend.routes.graphs import router as graphs_router

# ============================================================================
# APP LIFESPAN (startup / shutdown)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify MongoDB is reachable
    if await db_ping():
        print("[OK] MongoDB connected")
    else:
        print("[WARN] MongoDB not reachable - repo endpoints will fail")
    yield
    # Shutdown: close MongoDB connection pool
    await close_connection()
    print("[STOP] MongoDB connection closed")
# ============================================================================
# FASTAPI APP SETUP
# ============================================================================

app = FastAPI(
    title="Code Dependency Analyzer API",
    description="Analyze code repositories and extract dependency graphs",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Configuration – allows codeiq_ui (Next.js) frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(repos_router)
app.include_router(github_router)
app.include_router(analysis_router)
app.include_router(graphs_router, prefix="/api")

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
OUTPUT_DIR = DATA_ROOT / "intermediate" / "navigator_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/api/navigator/dag")
def get_dag(repo_id: Optional[str] = None):
    """Get a repository DAG from navigator output files."""
    navigator_output_dir = DATA_ROOT / "intermediate" / "navigator_output"

    if not navigator_output_dir.exists():
        return {
            "success": False,
            "message": "Navigator output directory not found",
            "data": None,
        }

    dag_path: Optional[Path] = None
    if repo_id:
        candidate = navigator_output_dir / f"dag_{repo_id}.json"
        if candidate.exists():
            dag_path = candidate

    if not dag_path:
        dag_files = sorted(
            navigator_output_dir.glob("dag_*.json"),
            key=lambda file_path: file_path.stat().st_mtime,
            reverse=True,
        )
        if dag_files:
            dag_path = dag_files[0]

    if not dag_path or not dag_path.exists():
        return {
            "success": False,
            "message": "No DAG file found",
            "data": None,
        }

    try:
        with open(dag_path, "r", encoding="utf-8") as file_handle:
            dag_data = json.load(file_handle)

        return {
            "success": True,
            "message": "DAG retrieved successfully",
            "data": dag_data,
            "file": dag_path.name,
        }
    except Exception as exc:
        return {
            "success": False,
            "message": f"Error reading DAG file: {str(exc)}",
            "data": None,
        }

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
    documentation: Optional[List] = None

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
async def health_check():
    """Detailed health check"""
    mongo_ok = await db_ping()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "output_dir": str(OUTPUT_DIR),
        "output_dir_exists": OUTPUT_DIR.exists(),
        "mongodb": "connected" if mongo_ok else "disconnected",
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
        print(f"[CLONE] Cloning repository: {req.repo_url}")
        repo_path = clone_repo(str(req.repo_url))
        print(f"[PARSE] Parsing repository at: {repo_path}")
        parser = RepositoryParser(repo_path)
        components = parser.parse()
        
        if not components:
            raise HTTPException(
                status_code=400,
                detail="No components found in repository. Make sure it contains Python files."
            )
        
        # Step 3: Build dependency graph
        print(f"[GRAPH] Building dependency graph...")
        graph = build_graph_from_components(components)
        graph = resolve_cycles(graph)
        
        # Step 4: Calculate ordering
        print(f"[TOPO] Calculating topological order...")
        topo_order = topological_sort(graph)
        dfs_order = dependency_first_dfs(graph)
        
        # Step 5: Calculate statistics
        stats = calculate_stats(components)
        
        # Step 6: Prepare component data in the required format
        components_dict = {}
        for comp_id, comp in components.items():
            # Get source code, truncated if needed
            source_code = ""
            if comp.source_code:
                source_code = truncate_source_code(comp.source_code) if req.include_source else comp.source_code
            
            comp_info = {
                "id": comp.id,
                "language": comp.language,
                "type": str(comp.type.value) if hasattr(comp.type, 'value') else str(comp.type),
                "file_path": comp.location.file_path if hasattr(comp, 'location') else "",
                "module_path": getattr(comp, 'module_path', ""),
                "depends_on": list(comp.depends_on) if hasattr(comp, 'depends_on') else [],
                "start_line": comp.location.start_line if hasattr(comp, 'location') else 0,
                "end_line": comp.location.end_line if hasattr(comp, 'location') else 0,
                "has_docstring": bool(comp.existing_docstring),
                "docstring": comp.existing_docstring or "",
                "source_code": source_code,
            }
            
            components_dict[comp_id] = comp_info
        
        # Step 7: Format output for UI display
        formatted_output = format_analysis_output(components, graph, dfs_order, topo_order)
        
        # Step 8: Print summary to console
        print_analysis_summary(components, graph, dfs_order, topo_order)
        
        # Step 9: Export IR and DAG
        print(f"[EXPORT] Exporting IR and DAG...")
        export_ir(components, repo_name)
        export_dag(graph, repo_id=repo_name)
        print(f"[OK] IR and DAG exported for '{repo_name}'")
        
        # Step 10: Save components to JSON file (in the required format)
        output_file = None
        if req.save_json:
            print(f"[SAVE] Saving components to JSON...")
            output_file = save_analysis_to_json(components_dict, repo_name)
            print(f"[OK] Results saved to: {output_file}")
        
        print(f"[OK] Analysis complete!")
        print(f"   Total components: {stats.total_components}")
        print(f"   Functions: {stats.functions}")
        print(f"   Classes: {stats.classes}")
        print(f"   Methods: {stats.methods}")
        print(f"   Global Variables: {stats.global_variables}")
        
        # Step 11: Try running the documentation pipeline (optional - requires LLM)
        docs = []
        try:
            from backend.pipeline import run_pipeline
            print(f"[PIPELINE] Running documentation pipeline for: {repo_path}")
            result = run_pipeline(repo_path)
            docs = result.get("documentation", [])
            
            # Save reader output
            reader_output_path = DATA_ROOT / "intermediate" / "agent_output" / "reader" / f"{repo_name}_reader_output.json"
            reader_output_path.parent.mkdir(parents=True, exist_ok=True)
            pipeline_components = result.get("components", {})
            FileHandler.write_json(reader_output_path, {k: FileHandler.serialize_component(v) for k, v in pipeline_components.items()})
            print(f"[OK] Documentation pipeline complete.")
        except Exception as pipeline_err:
            print(f"[WARN] Documentation pipeline skipped: {pipeline_err}")
            print(f"   Navigator results will be returned without LLM-generated docs.")

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
            output_file=output_file,
            message="Analysis and documentation complete." if docs else "Analysis complete (documentation pipeline unavailable).",
            documentation=[doc.dict() if hasattr(doc, "dict") else str(doc) for doc in docs] if docs else None
        )
        
    except Exception as e:
        print(f"[ERROR] Error during analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )
        

class EvaluationRequest(BaseModel):
    repo_name: str = Field(..., description="Name of the analyzed repository")

@app.post("/evaluate")
def evaluate_documentation(req: EvaluationRequest):
    """
    Evaluate generated documentation quality across three dimensions:
    - Completeness: structural completeness of docstrings
    - Helpfulness: LLM-based quality assessment (1-5)
    - Truthfulness: verifies mentioned components actually exist
    """
    try:
        print(f"[EVAL] Starting evaluation for: {req.repo_name}")

        evaluator = UnifiedEvaluator(repo_name=req.repo_name)
        results = evaluator.evaluate_all()

        return JSONResponse(content={
            "success": True,
            "repo_name": req.repo_name,
            "timestamp": datetime.now().isoformat(),
            "overall_quality_score": results["overall_quality_score"],
            "completeness": results["completeness"],
            "helpfulness": results["helpfulness"],
            "truthfulness": results["truthfulness"],
            "output_file": results.get("output_file"),
            "message": "Evaluation completed successfully",
        })

    except FileNotFoundError as e:
        print(f"[ERROR] File not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Evaluation error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@app.get("/evaluate/{repo_name}")
def get_evaluation_results(repo_name: str):
    """
    Fetch previously saved evaluation results for a repository.
    Returns scores as percentages (0-100).
    """
    # Look for saved results file
    validation_dir = DATA_ROOT / "validation" / repo_name
    results_file = validation_dir / "unified_evaluation_results.json"
    
    if not results_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No evaluation results found for repository '{repo_name}'. Run evaluation first."
        )
    
    try:
        with open(results_file, "r", encoding="utf-8") as f:
            results = json.load(f)
        
        # Convert scores to percentages (0-100)
        def to_percentage(score):
            if score is None:
                return None
            return round(score * 100, 1)
        
        # Extract scores from the correct paths in the JSON
        completeness_score = results.get("completeness", {}).get("summary", {}).get("overall_score")
        helpfulness_raw = results.get("helpfulness", {}).get("summary", {}).get("average_score")
        # Helpfulness is on 1-5 scale, convert to 0-1
        helpfulness_score = helpfulness_raw / 5.0 if helpfulness_raw else None
        truthfulness_score = results.get("truthfulness", {}).get("summary", {}).get("overall_accuracy")
        
        return JSONResponse(content={
            "success": True,
            "repo_name": repo_name,
            "overall_quality_score": to_percentage(results.get("overall_quality_score")),
            "completeness": {
                "score": to_percentage(completeness_score),
                "details": results.get("completeness", {})
            },
            "helpfulness": {
                "score": to_percentage(helpfulness_score),
                "details": results.get("helpfulness", {})
            },
            "truthfulness": {
                "score": to_percentage(truthfulness_score),
                "details": results.get("truthfulness", {})
            },
            "output_file": str(results_file),
        })
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid evaluation results file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading results: {str(e)}")


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
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
