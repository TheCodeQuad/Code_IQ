"""
Main Orchestrator
Coordinates the multi-agent workflow
"""
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.agents.base_agent import AgentContext, AgentResult, AgentStatus
from backend.agents.reader_agent import ReaderAgent
from backend.agents.searcher_agent import SearcherAgent
# from backend.agents.writer.writer_agent import WriterAgent
# from backend.agents.verifier_agent import VerifierAgent
from backend.agents.orchestrator.workflow import WorkflowManager
from backend.models.code_component import CodeComponent
from backend.models.documentation import Documentation
from backend.utils.logger import get_logger
from backend.utils.config_handler import get_config

logger = get_logger(__name__)

class Orchestrator:
    """
    Main orchestrator that coordinates all agents
    """
    
    def __init__(self, project_dag=None):
        self.config = get_config()
        self.logger = get_logger("orchestrator")
        
        # Initialize agents
        self.reader = ReaderAgent()
        self.searcher = SearcherAgent()
        
        # Workflow manager
        self.workflow = WorkflowManager()
        
        # Statistics
        self.total_components_processed = 0
        self.successful_docs = 0
        self.failed_docs = 0
        
        # Store project DAG for use in components
        self.project_dag = project_dag or set()
        
        self.logger.info("Orchestrator initialized")
    
    def process_components(
        self,
        components: List[CodeComponent]
    ) -> List[Documentation]:
        """
        Process all components through the agent pipeline
        """
        self.logger.info(f"Processing {len(components)} components")
        start_time = datetime.now()

        documented_components = []
        component_map = {c.id: c for c in components}  # For dependency lookup
        
        # FIX 1: Initialize searcher with repository data
        try:
            self.searcher.set_repository_data(components)
            self.logger.info("Searcher initialized with repository data")
        except Exception as e:
            self.logger.warning(f"Failed to initialize searcher with repository data: {e}")

        for idx, component in enumerate(components):
            self.logger.info(
                f"Processing component {idx + 1}/{len(components)}: "
                f"{component.name} ({component.type})"
            )

            try:
                doc = self.process_single_component(component, documented_components, component_map,self.project_dag)
                if doc:
                    documented_components.append(doc)
                    self.successful_docs += 1
                else:
                    self.failed_docs += 1
                    self.logger.warning(f"Failed to document {component.name}")
                    
            except Exception as e:
                self.logger.error(
                    f"Error processing {component.name}: {e}",
                    exc_info=True
                )
                self.failed_docs += 1
            
            self.total_components_processed += 1
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        self.logger.info(
            f"Documentation generation complete: "
            f"{self.successful_docs} succeeded, "
            f"{self.failed_docs} failed, "
            f"Time: {elapsed_time:.2f}s"
        )
        
        return documented_components
    

    def process_single_component(
        self,
        component: CodeComponent,
        previous_docs: List[Documentation],
        component_map: Dict[str, CodeComponent],
        project_dag
    ) -> Optional[Documentation]:
        """
        Process a single component through iterative Reader-Searcher loop,
        where Reader re-evaluates after Searcher provides context.
        """
        # Use passed project_dag, with fallback to instance variable
        dag = project_dag or self.project_dag
        
        context = AgentContext(
            component=component,
            metadata={
                'previous_docs': previous_docs,
                'timestamp': datetime.now().isoformat(),
                'accumulated_context': {  # Track what context we've gathered
                    'internal': [],
                    'external': []
                },
                'project_dag': dag  # Store DAG in metadata
            }
        )
        
        max_iterations = 3  # Reduced from 10
        last_internal_requests = None
        last_external_requests = None
        empty_results_count = 0

        for iteration in range(max_iterations):
            # 1. Reader agent - pass accumulated context
            reader_result = self.reader.execute(context)
            if not reader_result.is_success():
                self.logger.error(f"Reader failed: {reader_result.error}")
                return None
            
            reader_output = reader_result.output
            context.add_result('reader', reader_output)

            # Check for convergence: if requests are unchanged, break
            internal_requests = [(r.request_type, r.component_id) for r in reader_output.internal_requests]
            external_requests = [(r.request_type, r.query) for r in reader_output.external_requests]
            
            if (internal_requests == last_internal_requests and
                external_requests == last_external_requests):
                self.logger.info("No new information requested by Reader; stopping early.")
                break
            
            last_internal_requests = internal_requests
            last_external_requests = external_requests

            # If Reader doesn't need more context, stop
            if not getattr(reader_output, "needs_additional_context", False):
                self.logger.info(f"Reader satisfied after iteration {iteration + 1}")
                break

            # 2. Searcher agent
            searcher_result = self.searcher.execute(context)
            if not searcher_result.is_success():
                self.logger.warning(f"Searcher failed: {searcher_result.error}")
                break
            
            searcher_output = searcher_result.output
            context.add_result('searcher', searcher_output)
            
            # FIX 2: Check if Searcher returned nothing
            if (len(searcher_output.dependency_contexts) == 0 and
                len(searcher_output.reference_contexts) == 0 and
                len(searcher_output.external_contexts) == 0):
                empty_results_count += 1
                if empty_results_count >= 2:
                    self.logger.info("Searcher returned empty results twice; stopping.")
                    break
            else:
                empty_results_count = 0
    
            # 3. Add Searcher's findings to accumulated context for Reader's next iteration
            context.metadata['accumulated_context']['internal'].extend([
                {
                    'id': dc.component_id,
                    'name': dc.component_name,
                    'summary': dc.summary,
                    'signature': dc.signature
                }
                for dc in searcher_output.dependency_contexts
            ])
            
            context.metadata['accumulated_context']['internal'].extend([
                {
                    'id': rc.component_id,
                    'name': rc.component_name,
                    'usage_examples': rc.usage_examples,
                    'usage_summary': rc.usage_summary
                }
                for rc in searcher_output.reference_contexts
            ])
            
            context.metadata['accumulated_context']['external'].extend([
                {
                    'query': ec.query,
                    'summary': ec.summary,
                    'details': ec.details
                }
                for ec in searcher_output.external_contexts
            ])
            
            self.logger.info(
                f"Searcher provided: "
                f"{len(searcher_output.dependency_contexts)} dependencies, "
                f"{len(searcher_output.reference_contexts)} references, "
                f"{len(searcher_output.external_contexts)} external contexts"
            )

        print(f"ReaderOutput for {component.id}: {reader_output}")
        self.logger.info(f"Reader-Searcher loop completed for {component.name} after {iteration + 1} iterations")
        
        # Return reader output as documentation placeholder
        return reader_output

    
    def get_statistics(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        return {
            'total_components': self.total_components_processed,
            'successful': self.successful_docs,
            'failed': self.failed_docs,
            'success_rate': round(
                (self.successful_docs / max(self.total_components_processed, 1)) * 100,
                2
            ),
            'agent_stats': {
                'reader': self.reader.get_statistics(),
                'searcher': self.searcher.get_statistics(),
                'writer': self.writer.get_statistics(),
                'verifier': self.verifier.get_statistics()
            }
        }