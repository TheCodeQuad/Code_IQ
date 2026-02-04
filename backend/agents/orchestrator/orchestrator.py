"""
Main Orchestrator
Coordinates the multi-agent workflow with parallel processing support
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from xml.etree import ElementTree as ET

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
from backend.utils.docstring_inserter import DocstringInserter

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
        
        # Continuous docstring insertion
        self._insert_docstrings = self.config.get('system.pipeline.insert_docstrings', True)
        self._docstring_inserter = None
        if self._insert_docstrings:
            self._docstring_inserter = DocstringInserter(
                backup=True,
                replace_existing=self.config.get('system.pipeline.replace_existing_docstrings', False)
            )
        
        # Track docstring insertion stats
        self.docstrings_inserted = 0
        self.docstrings_skipped = 0
        self.docstrings_failed = 0
        
        self.logger.info(
            f"Orchestrator initialized (parallel={self._parallel_enabled}, "
            f"workers={self._max_workers}, insert_docstrings={self._insert_docstrings})"
        )
    
    def _parse_reader_xml_output(self, xml_string: str) -> Dict[str, Any]:
        """
        Parse Reader Agent's XML output format and extract information needs and requests.
        
        Now works with the new XML format from refactored Reader Agent.
        
        Returns:
            Dict with keys: 'needs_context', 'internal_requests', 'external_requests'
        """
        try:
            root = ET.fromstring(xml_string)
            
            # Extract needs_context flag
            needs_context_elem = root.find('INFO_NEED')
            needs_context = needs_context_elem is not None and needs_context_elem.text.lower() == 'true'
            
            # Parse internal requests (now as Dicts, not dataclasses)
            internal_requests = []
            request_elem = root.find('REQUEST/INTERNAL')
            if request_elem is not None:
                # Parse CALLS
                calls_elem = request_elem.find('CALLS')
                if calls_elem is not None:
                    # Get classes
                    class_elem = calls_elem.find('CLASS')
                    if class_elem is not None and class_elem.text:
                        for class_name in class_elem.text.split(','):
                            internal_requests.append({
                                'type': 'dependency',
                                'name': class_name.strip(),
                                'category': 'CLASS',
                                'priority': 7
                            })
                    
                    # Get functions
                    func_elem = calls_elem.find('FUNCTION')
                    if func_elem is not None and func_elem.text:
                        for func_name in func_elem.text.split(','):
                            internal_requests.append({
                                'type': 'dependency',
                                'name': func_name.strip(),
                                'category': 'FUNCTION',
                                'priority': 6
                            })
                    
                    # Get methods
                    method_elem = calls_elem.find('METHOD')
                    if method_elem is not None and method_elem.text:
                        for method_name in method_elem.text.split(','):
                            internal_requests.append({
                                'type': 'dependency',
                                'name': method_name.strip(),
                                'category': 'METHOD',
                                'priority': 5
                            })
                
                # Parse CALLED_BY (should we find who calls this component?)
                called_by_elem = request_elem.find('CALLED_BY')
                if called_by_elem is not None and called_by_elem.text == 'true':
                    internal_requests.append({
                        'type': 'reference',
                        'name': 'self',
                        'category': 'CALLED_BY',
                        'priority': 8
                    })
            
            # Parse external requests (now as Dicts, not dataclasses)
            external_requests = []
            external_elem = root.find('REQUEST/EXTERNAL')
            if external_elem is not None:
                query_elem = external_elem.find('QUERY')
                if query_elem is not None and query_elem.text:
                    for query in query_elem.text.split(','):
                        external_requests.append({
                            'type': 'novel_concept',
                            'query': query.strip(),
                            'priority': 7
                        })
            
            return {
                'needs_context': needs_context,
                'internal_requests': internal_requests,
                'external_requests': external_requests
            }
        except Exception as e:
            self.logger.warning(f"Failed to parse Reader XML output: {e}, using defaults")
            return {
                'needs_context': False,
                'internal_requests': [],
                'external_requests': []
            }
    
    def process_components(
        self,
        components: List[CodeComponent]
    ) -> List[Documentation]:
        """
        Process all components through the agent pipeline.
        Supports parallel processing when enabled in config.
        
        NOTE: The searcher should already have repository data set via 
        searcher.set_repository_data() before calling this method.
        The reader also needs component map for accurate type classification.
        """
        self.logger.info(f"Processing {len(components)} components (parallel={self._parallel_enabled})")
        start_time = datetime.now()

        component_map = {c.id: c for c in components}  # For dependency lookup
        
        # Set component map in Reader for accurate type classification
        self.reader.set_component_map(components)
        self.logger.info("Reader initialized with component map")

        # Choose processing mode
        if self._parallel_enabled and len(components) > 1:
            documented_components = self._process_parallel(components, component_map)
        else:
            documented_components = self._process_sequential(components, component_map)
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        # Build completion message with docstring stats if enabled
        completion_msg = (
            f"Documentation generation complete: "
            f"{self.successful_docs} succeeded, "
            f"{self.failed_docs} failed, "
            f"Time: {elapsed_time:.2f}s"
        )
        
        if self._insert_docstrings:
            completion_msg += (
                f" | Docstrings inserted: {self.docstrings_inserted}, "
                f"failed: {self.docstrings_failed}"
            )
        
        self.logger.info(completion_msg)
        
        # Save consolidated reader outputs
        try:
            consolidated_path = self.reader.save_consolidated_output()
            if consolidated_path:
                self.logger.info(f"Consolidated reader outputs saved to: {consolidated_path}")
        except Exception as e:
            self.logger.warning(f"Failed to save consolidated reader outputs: {e}")
        
        # Save consolidated searcher outputs
        try:
            if hasattr(self.searcher, 'save_consolidated_output'):
                searcher_consolidated_path = self.searcher.save_consolidated_output()
                if searcher_consolidated_path:
                    self.logger.info(f"Consolidated searcher outputs saved to: {searcher_consolidated_path}")
        except Exception as e:
            self.logger.warning(f"Failed to save consolidated searcher outputs: {e}")
        
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
            reader_output_xml = context.get_result('reader')
            reader_metadata = context.metadata or {}
            
            # Parse XML if reader output is a string
            if isinstance(reader_output_xml, str):
                parsed_data = self._parse_reader_xml_output(reader_output_xml)
                internal_requests = parsed_data['internal_requests']
                external_requests = parsed_data['external_requests']
                needs_context = parsed_data['needs_context']
            else:
                # Fallback for old format (ReaderOutput object)
                internal_requests = reader_output_xml.internal_requests
                external_requests = reader_output_xml.external_requests
                needs_context = reader_output_xml.needs_additional_context
            
            # Check for convergence
            # Handle both dict (new format) and object (old format) for backward compatibility
            internal_requests_tuple = [
                (r.get('type') if isinstance(r, dict) else r.request_type,
                 r.get('name') if isinstance(r, dict) else r.component_id)
                for r in internal_requests
            ]
            external_requests_tuple = [
                (r.get('type') if isinstance(r, dict) else r.request_type,
                 r.get('query') if isinstance(r, dict) else r.query)
                for r in external_requests
            ]
            
            if (internal_requests_tuple == last_internal_requests and
                external_requests_tuple == last_external_requests):
                self.logger.info("No new information requested by Reader; stopping early.")
                break
            
            last_internal_requests = internal_requests_tuple
            last_external_requests = external_requests_tuple

            # If Reader doesn't need more context, stop
            if not needs_context:
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
        
        # Continuous docstring insertion - insert immediately after writer generates
        if self._insert_docstrings and self._docstring_inserter:
            self._insert_docstring_for_component(component, documentation)

        # Optional: Verifier agent
        use_verifier = self.config.get('agents.verifier.enabled', False)
        if use_verifier:
            verifier_result = self.verifier.execute(context)
            if verifier_result.is_success():
                verification_output = verifier_result.output
                context.add_result('verifier', verification_output)
                self.logger.info(f"Verifier passed for {component.name}")

        return documentation
    
    def _insert_docstring_for_component(
        self,
        component: CodeComponent,
        documentation: Documentation
    ) -> None:
        """
        Insert the generated docstring into the source file for a component.
        Called immediately after the writer agent generates documentation.
        
        Args:
            component: The code component being documented
            documentation: The generated documentation from writer agent
        """
        if not self._docstring_inserter:
            return
        
        try:
            # Convert Documentation to dict format expected by inserter
            doc_data = {
                'docstring': documentation.docstring if hasattr(documentation, 'docstring') else str(documentation)
            }
            
            # Use the component-aware insertion method
            result = self._docstring_inserter.insert_for_component(component, doc_data)
            
            # Track stats (thread-safe)
            with self._stats_lock:
                if result.success:
                    if result.action == 'inserted':
                        self.docstrings_inserted += 1
                        self.logger.debug(f"Docstring inserted for {component.name}")
                    elif result.action == 'replaced':
                        self.docstrings_inserted += 1
                        self.logger.debug(f"Docstring replaced for {component.name}")
                    elif result.action == 'skipped':
                        self.docstrings_skipped += 1
                        self.logger.debug(f"Docstring skipped for {component.name}: {result.message}")
                else:
                    self.docstrings_failed += 1
                    self.logger.warning(f"Docstring insertion failed for {component.name}: {result.message}")
                    
        except Exception as e:
            with self._stats_lock:
                self.docstrings_failed += 1
            self.logger.error(f"Error inserting docstring for {component.name}: {e}")
    
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

            # Parse Reader output (XML string or old ReaderOutput object)
            if isinstance(reader_output, str):
                # New format: XML string
                parsed_data = self._parse_reader_xml_output(reader_output)
                needs_context = parsed_data['needs_context']
                internal_requests = parsed_data['internal_requests']
                external_requests = parsed_data['external_requests']
            else:
                # Old format fallback: ReaderOutput object
                internal_requests = getattr(reader_output, 'internal_requests', [])
                external_requests = getattr(reader_output, 'external_requests', [])
                needs_context = getattr(reader_output, 'needs_additional_context', False)

            # Check for convergence: convert to tuples for comparison
            internal_requests_tuple = [
                (r.get('type') if isinstance(r, dict) else r.request_type,
                 r.get('name') if isinstance(r, dict) else r.component_id)
                for r in internal_requests
            ]
            external_requests_tuple = [
                (r.get('type') if isinstance(r, dict) else r.request_type,
                 r.get('query') if isinstance(r, dict) else r.query)
                for r in external_requests
            ]
            
            if (internal_requests_tuple == last_internal_requests and
                external_requests_tuple == last_external_requests):
                self.logger.info("No new information requested by Reader; stopping early.")
                break
            
            last_internal_requests = internal_requests_tuple
            last_external_requests = external_requests_tuple

            # If Reader doesn't need more context, stop
            if not needs_context:
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
        
        # 6. Insert docstring into source file (continuous integration)
        self._insert_docstring_for_component(component, writer_output)
        
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
        stats = {
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
        
        # Include docstring insertion stats if enabled
        if self._insert_docstrings:
            stats['docstring_insertion'] = {
                'enabled': True,
                'inserted': self.docstrings_inserted,
                'skipped': self.docstrings_skipped,
                'failed': self.docstrings_failed
            }
        
        return stats