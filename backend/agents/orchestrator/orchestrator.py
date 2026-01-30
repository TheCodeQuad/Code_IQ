"""
Main Orchestrator
Coordinates the multi-agent workflow with parallel processing support
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from backend.agents.base_agent import AgentContext, AgentResult, AgentStatus
from backend.agents.reader_agent import ReaderAgent
from backend.agents.searcher_agent import SearcherAgent
from backend.agents.writer.writer_agent import WriterAgent
from backend.agents.verifier_agent import VerifierAgent
from backend.agents.orchestrator.workflow import WorkflowManager, WorkflowStage
from backend.models.code_component import CodeComponent
from backend.models.documentation import Documentation
from backend.utils.logger import get_logger
from backend.utils.config_handler import get_config

logger = get_logger(__name__)

class Orchestrator:
    """
    Main orchestrator that coordinates all agents
    Supports parallel processing for better GPU utilization
    """
    
    def __init__(self, project_dag=None):
        self.config = get_config()
        self.logger = get_logger("orchestrator")
        
        # Initialize agents
        self.reader = ReaderAgent()
        self.searcher = SearcherAgent()
        self.writer = WriterAgent()
        self.verifier = VerifierAgent()
        
        # Workflow manager
        self.workflow = WorkflowManager()
        
        # Statistics
        self.total_components_processed = 0
        self.successful_docs = 0
        self.failed_docs = 0
        
        # Store project DAG for use in components
        self.project_dag = project_dag or set()
        
        # Thread safety for stats
        self._stats_lock = threading.Lock()
        
        # Parallel processing config
        self._max_workers = self.config.get('system.performance.max_workers', 4)
        self._parallel_enabled = self.config.get('system.pipeline.parallel_processing', False)
        
        self.logger.info(f"Orchestrator initialized (parallel={self._parallel_enabled}, workers={self._max_workers})")
    
    def process_components(
        self,
        components: List[CodeComponent]
    ) -> List[Documentation]:
        """
        Process all components through the agent pipeline.
        Supports parallel processing when enabled in config.
        """
        self.logger.info(f"Processing {len(components)} components (parallel={self._parallel_enabled})")
        start_time = datetime.now()

        component_map = {c.id: c for c in components}  # For dependency lookup
        
        # Initialize searcher with repository data
        try:
            self.searcher.set_repository_data(components)
            self.logger.info("Searcher initialized with repository data")
        except Exception as e:
            self.logger.warning(f"Failed to initialize searcher with repository data: {e}")

        # Choose processing mode
        if self._parallel_enabled and len(components) > 1:
            documented_components = self._process_parallel(components, component_map)
        else:
            documented_components = self._process_sequential(components, component_map)
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        self.logger.info(
            f"Documentation generation complete: "
            f"{self.successful_docs} succeeded, "
            f"{self.failed_docs} failed, "
            f"Time: {elapsed_time:.2f}s"
        )
        
        return documented_components
    
    def _process_sequential(
        self,
        components: List[CodeComponent],
        component_map: Dict[str, CodeComponent]
    ) -> List[Documentation]:
        """
        Process components sequentially with batch Reader Agent.
        Batches components in groups of 5 for Reader analysis,
        then processes each component individually with Searcher and Writer.
        """
        documented_components = []
        batch_size = 5  # Batch size for Reader Agent
        
        # Process components in Reader batches
        for batch_start in range(0, len(components), batch_size):
            batch = components[batch_start:batch_start + batch_size]
            batch_end = min(batch_start + batch_size, len(components))
            
            self.logger.info(
                f"Processing Reader batch {batch_start // batch_size + 1}/"
                f"{(len(components) + batch_size - 1) // batch_size}: "
                f"components {batch_start + 1}-{batch_end}"
            )
            
            # Create contexts for batch
            batch_contexts = [
                AgentContext(
                    component=comp,
                    metadata={
                        'previous_docs': documented_components.copy(),
                        'timestamp': datetime.now().isoformat(),
                        'accumulated_context': {
                            'internal': [],
                            'external': []
                        },
                        'project_dag': self.project_dag
                    }
                )
                for comp in batch
            ]
            
            # BATCH READER CALL (1 LLM call for entire batch)
            try:
                reader_batch_results = self.reader.process_batch(batch_contexts)
                self.logger.info(f"Reader batch completed successfully")
            except Exception as e:
                self.logger.error(f"Reader batch failed: {e}", exc_info=True)
                self.failed_docs += len(batch)
                self.total_components_processed += len(batch)
                continue
            
            # Now process each component individually with Searcher and Writer
            for idx, component in enumerate(batch):
                self.logger.info(
                    f"Processing component {batch_start + idx + 1}/{len(components)}: "
                    f"{component.name} ({component.type})"
                )
                
                try:
                    # Get Reader output from batch
                    reader_result = reader_batch_results[idx]
                    if not reader_result.is_success():
                        self.logger.error(
                            f"Reader failed for {component.name}: {reader_result.error}"
                        )
                        self.failed_docs += 1
                        self.total_components_processed += 1
                        continue
                    
                    # Create context with reader result for individual processing
                    context = AgentContext(
                        component=component,
                        previous_results={'reader': reader_result.output},
                        metadata={
                            'previous_docs': documented_components.copy(),
                            'timestamp': datetime.now().isoformat(),
                            'accumulated_context': {
                                'internal': [],
                                'external': []
                            },
                            'project_dag': self.project_dag
                        }
                    )
                    
                    # Process with Searcher-Writer iterative loop
                    doc = self._process_with_searcher_writer_loop(
                        component,
                        context,
                        component_map
                    )
                    
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
        
        return documented_components
    
    def _process_with_searcher_writer_loop(
        self,
        component: CodeComponent,
        context: AgentContext,
        component_map: Dict[str, CodeComponent]
    ) -> Optional[Documentation]:
        """
        Run the iterative Searcher-Writer loop for a component.
        Reader has already been executed and result is in context.
        """
        max_iterations = 3
        last_internal_requests = None
        last_external_requests = None

        for iteration in range(max_iterations):
            reader_output = context.get_result('reader')
            
            # Check for convergence
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

            # Searcher agent
            searcher_result = self.searcher.execute(context)
            if not searcher_result.is_success():
                self.logger.warning(f"Searcher failed: {searcher_result.error}")
                break
            
            searcher_output = searcher_result.output
            context.add_result('searcher', searcher_output)
            
            # Check if Searcher returned nothing
            if (len(searcher_output.dependency_contexts) == 0 and
                len(searcher_output.reference_contexts) == 0 and
                len(searcher_output.external_contexts) == 0):
                self.logger.info("Searcher found no new information; stopping iterations.")
                break
            
            # Update accumulated context for next Reader iteration
            accumulated = context.metadata['accumulated_context']
            accumulated['internal'].extend(searcher_output.dependency_contexts)
            accumulated['external'].extend(searcher_output.external_contexts)
            
            # Re-run Reader with accumulated context
            reader_result = self.reader.execute(context)
            if not reader_result.is_success():
                self.logger.warning(f"Reader re-evaluation failed: {reader_result.error}")
                break
            
            context.add_result('reader', reader_result.output)

        # Writer agent - generate documentation
        writer_result = self.writer.execute(context)
        if not writer_result.is_success():
            self.logger.error(f"Writer failed: {writer_result.error}")
            return None
        
        documentation = writer_result.output
        context.add_result('writer', documentation)

        # Optional: Verifier agent
        use_verifier = self.config.get('agents.verifier.enabled', False)
        if use_verifier:
            verifier_result = self.verifier.execute(context)
            if verifier_result.is_success():
                verification_output = verifier_result.output
                context.add_result('verifier', verification_output)
                self.logger.info(f"Verifier passed for {component.name}")

        return documentation
    
    def _process_parallel(
        self,
        components: List[CodeComponent],
        component_map: Dict[str, CodeComponent]
    ) -> List[Documentation]:
        """
        Process components in parallel batches for better GPU utilization.
        Uses ThreadPoolExecutor to submit multiple LLM requests concurrently.
        """
        documented_components = []
        batch_size = min(self._max_workers, 4)  # Limit batch size for GPU memory
        
        self.logger.info(f"Parallel processing with batch_size={batch_size}, max_workers={self._max_workers}")
        
        # Process in batches to avoid overwhelming the GPU
        for batch_start in range(0, len(components), batch_size):
            batch = components[batch_start:batch_start + batch_size]
            batch_docs = []
            
            self.logger.info(
                f"Processing batch {batch_start // batch_size + 1}/"
                f"{(len(components) + batch_size - 1) // batch_size}: "
                f"{len(batch)} components"
            )
            
            with ThreadPoolExecutor(max_workers=len(batch)) as executor:
                # Submit all components in batch
                future_to_component = {
                    executor.submit(
                        self._process_component_thread_safe,
                        component,
                        documented_components.copy(),  # Snapshot for thread safety
                        component_map
                    ): component
                    for component in batch
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_component):
                    component = future_to_component[future]
                    try:
                        doc = future.result()
                        if doc:
                            batch_docs.append(doc)
                            with self._stats_lock:
                                self.successful_docs += 1
                        else:
                            with self._stats_lock:
                                self.failed_docs += 1
                            self.logger.warning(f"Failed to document {component.name}")
                    except Exception as e:
                        self.logger.error(f"Error processing {component.name}: {e}", exc_info=True)
                        with self._stats_lock:
                            self.failed_docs += 1
                    
                    with self._stats_lock:
                        self.total_components_processed += 1
            
            # Add batch results to main list
            documented_components.extend(batch_docs)
        
        return documented_components
    
    def _process_component_thread_safe(
        self,
        component: CodeComponent,
        previous_docs: List[Documentation],
        component_map: Dict[str, CodeComponent]
    ) -> Optional[Documentation]:
        """Thread-safe wrapper for process_single_component"""
        try:
            return self.process_single_component(
                component, previous_docs, component_map, self.project_dag
            )
        except Exception as e:
            self.logger.error(f"Thread error for {component.name}: {e}")
            return None

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
        Then generates documentation with Writer and optionally verifies with Verifier.
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

        self.logger.info(f"Reader-Searcher loop completed for {component.name} after {iteration + 1} iterations")
        
        # 4. Writer agent - generates comprehensive documentation
        self.logger.info(f"Writer generating documentation for {component.name}")
        writer_result = self.writer.execute(context)
        if not writer_result.is_success():
            self.logger.warning(f"Writer failed: {writer_result.error}")
            # Create fallback Documentation instead of returning reader_output
            return self._create_fallback_documentation(component)
        
        writer_output = writer_result.output
        context.add_result('writer', writer_output)
        
        self.logger.info(f"Documentation generated: {len(writer_output.docstring)} chars")
        
        # 5. Verifier agent (optional) - validates and improves documentation
        if self.workflow.is_stage_required(WorkflowStage.VERIFY):
            self.logger.info(f"Verifier validating documentation for {component.name}")
            verifier_result = self.verifier.execute(context)
            if verifier_result.is_success():
                verifier_output = verifier_result.output
                context.add_result('verifier', verifier_output)
                # Use improved documentation if available
                if hasattr(verifier_output, 'improved_documentation') and verifier_output.improved_documentation:
                    writer_output = verifier_output.improved_documentation
                    self.logger.info(f"Using improved documentation from Verifier")
            else:
                self.logger.warning(f"Verifier failed: {verifier_result.error}")
        
        return writer_output

    def _create_fallback_documentation(self, component: CodeComponent) -> Documentation:
        """
        Create a fallback Documentation object in case of Writer failure
        """
        self.logger.info(f"Creating fallback documentation for {component.name}")
        return Documentation(
            id=f"fallback-{component.id}",
            name=f"Fallback Documentation for {component.name}",
            component_id=component.id,
            docstring="Fallback documentation due to Writer failure.",
            source="orchestrator",
            type=component.type,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
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