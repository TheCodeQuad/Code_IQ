"""
Main Orchestrator
Coordinates the multi-agent workflow with parallel processing support
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from xml.etree import ElementTree as ET

from backend.agents.base_agent import AgentContext, AgentResult, AgentStatus
from backend.agents.reader_agent import ReaderAgent
from backend.agents.searcher_agent import SearcherAgent
from backend.agents.writer_agent import WriterAgent
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
        
        # Verifier loop configuration
        self._max_verifier_rejections = self.config.get('agents.verifier_agent.max_rejections', 3)
        self._max_reader_search_attempts = self.config.get('system.pipeline.max_reader_search_attempts', 3)
        
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
            f"workers={self._max_workers}, insert_docstrings={self._insert_docstrings}, "
            f"max_verifier_rejections={self._max_verifier_rejections}, "
            f"max_reader_search_attempts={self._max_reader_search_attempts})"
        )
    
    # ─── Reader output parsing & normalization ───────────────────────────
    
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
    
    def _normalize_reader_output(self, reader_output) -> Dict[str, Any]:
        """
        Normalize reader output (XML string or ReaderOutput object) to a
        consistent dict format, eliminating isinstance checks elsewhere.
        
        Returns:
            Dict with keys: 'needs_context', 'internal_requests', 'external_requests'
        """
        if isinstance(reader_output, str):
            return self._parse_reader_xml_output(reader_output)
        
        # Object format (ReaderOutput dataclass)
        internal = []
        for r in getattr(reader_output, 'internal_requests', []):
            if isinstance(r, dict):
                internal.append(r)
            else:
                internal.append({
                    'type': getattr(r, 'request_type', 'unknown'),
                    'name': getattr(r, 'component_id', ''),
                    'category': getattr(r, 'category', ''),
                    'priority': getattr(r, 'priority', 5)
                })
        
        external = []
        for r in getattr(reader_output, 'external_requests', []):
            if isinstance(r, dict):
                external.append(r)
            else:
                external.append({
                    'type': getattr(r, 'request_type', 'novel_concept'),
                    'query': getattr(r, 'query', ''),
                    'priority': getattr(r, 'priority', 7)
                })
        
        return {
            'needs_context': getattr(reader_output, 'needs_additional_context', False),
            'internal_requests': internal,
            'external_requests': external
        }
    
    # ─── Convergence & circuit-breaker helpers ───────────────────────────
    
    @staticmethod
    def _reader_requests_key(parsed: Dict[str, Any]) -> Tuple:
        """Create a hashable key from parsed reader requests for convergence detection."""
        return (
            tuple(
                (r.get('type', ''), r.get('name', ''))
                for r in parsed['internal_requests']
            ),
            tuple(
                (r.get('type', ''), r.get('query', ''))
                for r in parsed['external_requests']
            )
        )
    
    @staticmethod
    def _is_context_exhausted(cal_hist: Dict[str, int]) -> bool:
        """Circuit-breaker: check if further context searching is futile."""
        return (
            cal_hist['empty_searcher_results'] >= 2
            or (cal_hist['total_searcher_calls'] >= 3
                and cal_hist['total_internal_found'] == 0
                and cal_hist['total_external_found'] == 0)
        )
    
    # ─── Searcher result accumulation ────────────────────────────────────
    
    def _accumulate_searcher_results(
        self,
        context: AgentContext,
        searcher_output,
        cal_hist: Dict[str, int]
    ) -> int:
        """
        Accumulate searcher results into context metadata.
        Updates calibration history stats.
        
        Returns:
            Total number of items found (0 means empty result).
        """
        n_dep = len(searcher_output.dependency_contexts)
        n_ref = len(searcher_output.reference_contexts)
        n_ext = len(searcher_output.external_contexts)
        total = n_dep + n_ref + n_ext
        
        cal_hist['total_internal_found'] += n_dep + n_ref
        cal_hist['total_external_found'] += n_ext
        
        if total == 0:
            cal_hist['empty_searcher_results'] += 1
            self.logger.info("Searcher found no new information.")
            return 0
        
        accumulated = context.metadata['accumulated_context']
        
        accumulated['internal'].extend([
            {
                'id': dc.component_id,
                'name': dc.component_name,
                'summary': dc.summary,
                'signature': dc.signature
            }
            for dc in searcher_output.dependency_contexts
        ])
        accumulated['internal'].extend([
            {
                'id': rc.component_id,
                'name': rc.component_name,
                'usage_examples': rc.usage_examples,
                'usage_summary': rc.usage_summary
            }
            for rc in searcher_output.reference_contexts
        ])
        accumulated['external'].extend([
            {
                'query': ec.query,
                'summary': ec.summary,
                'details': ec.details
            }
            for ec in searcher_output.external_contexts
        ])
        
        self.logger.info(
            f"Searcher provided: {n_dep} dependencies, {n_ref} references, {n_ext} external"
        )
        return total
    
    # ─── Reader-Searcher convergence loop ────────────────────────────────
    
    def _run_reader_searcher_convergence(
        self,
        context: AgentContext,
        cal_hist: Dict[str, int]
    ) -> bool:
        """
        Run the Reader-Searcher convergence loop until the Reader is satisfied
        or no new information can be found.
        
        If context already has a reader result (e.g. from batch processing),
        uses it on the first iteration instead of re-executing the reader.
        
        Returns:
            True if convergence succeeded, False if reader failed fatally.
        """
        max_iterations = 3
        last_key = None
        empty_count = 0
        
        for iteration in range(max_iterations):
            # Use pre-loaded reader result on first pass, execute otherwise
            if iteration == 0 and context.get_result('reader') is not None:
                pass  # Use existing reader result from batch or prior run
            else:
                reader_result = self.reader.execute(context)
                if not reader_result.is_success():
                    self.logger.error(f"Reader failed: {reader_result.error}")
                    return False
                context.add_result('reader', reader_result.output)
            
            parsed = self._normalize_reader_output(context.get_result('reader'))
            
            # Convergence check: same requests as last iteration?
            current_key = self._reader_requests_key(parsed)
            if current_key == last_key:
                self.logger.info("Reader requests unchanged; convergence reached.")
                break
            last_key = current_key
            
            if not parsed['needs_context']:
                self.logger.info(f"Reader satisfied after iteration {iteration + 1}")
                break
            
            # Run searcher
            searcher_result = self.searcher.execute(context)
            cal_hist['total_searcher_calls'] += 1
            if not searcher_result.is_success():
                self.logger.warning(f"Searcher failed: {searcher_result.error}")
                break
            
            context.add_result('searcher', searcher_result.output)
            found = self._accumulate_searcher_results(
                context, searcher_result.output, cal_hist
            )
            
            if found == 0:
                empty_count += 1
                if empty_count >= 2:
                    self.logger.info("Searcher returned empty results twice; stopping convergence.")
                    break
            else:
                empty_count = 0
            
            # Re-run reader with enriched context
            reader_result = self.reader.execute(context)
            if not reader_result.is_success():
                self.logger.warning(f"Reader re-evaluation failed: {reader_result.error}")
                break
            context.add_result('reader', reader_result.output)
        
        return True
    
    # ─── Verifier-triggered context gathering ────────────────────────────
    
    def _gather_additional_context(
        self,
        context: AgentContext,
        verification,
        cal_hist: Dict[str, int]
    ) -> None:
        """
        Gather additional context when verifier requests it.
        Runs searcher and re-runs reader with the enriched context.
        """
        ctx_suggestion = (
            getattr(verification, 'suggestion_context', None)
            or getattr(verification, 'suggestion', None)
            or ""
        )
        if ctx_suggestion:
            self.logger.info(f"Context reason: {ctx_suggestion}")
        
        searcher_result = self.searcher.execute(context)
        cal_hist['total_searcher_calls'] += 1
        
        if not searcher_result.is_success():
            self.logger.warning(
                f"Searcher failed when verifier requested context: {searcher_result.error}"
            )
            return
        
        searcher_output = searcher_result.output
        context.add_result('searcher', searcher_output)
        self._accumulate_searcher_results(context, searcher_output, cal_hist)
        
        # Re-run reader with new context to update its analysis
        reader_result = self.reader.execute(context)
        if reader_result.is_success():
            context.add_result('reader', reader_result.output)
            self.logger.info("Reader re-evaluated with new context")
        else:
            self.logger.warning(f"Reader re-evaluation failed: {reader_result.error}")
    
    # ─── Unified component pipeline ──────────────────────────────────────
    
    def _process_component_pipeline(
        self,
        component: CodeComponent,
        context: AgentContext,
        component_map: Dict[str, CodeComponent]
    ) -> Optional[Documentation]:
        """
        Unified processing pipeline for a single component.
        
        Outer loop: Reader-Searcher context gathering (up to max_reader_search_attempts)
        Inner loop: Writer-Verifier quality refinement (up to max_verifier_rejections)

        The Verifier can:
        - Accept the docstring  → return immediately
        - Reject needing context → break to outer loop (more Reader-Searcher)
        - Reject on content     → Writer refines with feedback (stay in inner loop)
        """
        verifier_rejection_count = 0
        documentation = None
        cal_hist = context.metadata['calibration_history']
        
        for reader_search_attempt in range(self._max_reader_search_attempts):
            # ── Phase 1: Reader-Searcher convergence ──
            if not self._run_reader_searcher_convergence(context, cal_hist):
                return self._create_fallback_documentation(component)
            
            self.logger.info(
                f"Reader-Searcher converged for {component.name} "
                f"(attempt {reader_search_attempt + 1}/{self._max_reader_search_attempts})"
            )
            
            # ── Phase 2: Writer generates documentation ──
            self.logger.info(f"Writer generating documentation for {component.name}")
            writer_result = self.writer.execute(context)
            if not writer_result.is_success():
                self.logger.error(f"Writer failed: {writer_result.error}")
                break
            documentation = writer_result.output
            context.add_result('writer', documentation)
            
            # Skip verification if not required
            if not self.workflow.is_stage_required(WorkflowStage.VERIFY):
                self._insert_docstring_for_component(component, documentation)
                return documentation
            
            # ── Phase 3: Writer-Verifier refinement loop ──
            broke_for_context = False
            cal_hist['rejection_count'] = verifier_rejection_count
            
            while verifier_rejection_count <= self._max_verifier_rejections:
                self.logger.info(f"Verifier validating documentation for {component.name}")
                verifier_result = self.verifier.execute(context)
                
                if not verifier_result.is_success():
                    self.logger.warning(f"Verifier failed: {verifier_result.error}")
                    break  # Accept writer output as-is
                
                verification = verifier_result.output
                context.add_result('verifier', verification)
                
                # Accepted or exhausted rejections → done
                if not verification.need_revision or verifier_rejection_count >= self._max_verifier_rejections:
                    if verifier_rejection_count >= self._max_verifier_rejections:
                        self.logger.info(
                            f"Max verifier rejections ({self._max_verifier_rejections}) "
                            f"reached for {component.name}, accepting current docstring"
                        )
                    else:
                        self.logger.info(f"Verifier accepted documentation for {component.name}")
                    self._insert_docstring_for_component(component, documentation)
                    return documentation
                
                # Rejected
                verifier_rejection_count += 1
                cal_hist['rejection_count'] = verifier_rejection_count
                self.verifier.clear_memory()
                
                # Decide: gather more context or refine content?
                wants_context = (
                    verification.more_context
                    and reader_search_attempt < self._max_reader_search_attempts - 1
                )
                
                if wants_context and not self._is_context_exhausted(cal_hist):
                    # Need more context → gather and break to outer loop
                    self.logger.info(
                        f"Verifier needs more context (rejection {verifier_rejection_count}/"
                        f"{self._max_verifier_rejections}), gathering additional context"
                    )
                    self._gather_additional_context(context, verification, cal_hist)
                    self.writer.clear_memory()
                    broke_for_context = True
                    break  # → next reader_search_attempt
                
                # Content fix (including circuit-breaker fallthrough)
                if wants_context and self._is_context_exhausted(cal_hist):
                    self.logger.info(
                        f"Circuit-breaker: context exhausted for {component.name}, "
                        "treating as content-only rejection"
                    )
                    suggestion = (
                        verification.suggestion_context
                        or verification.suggestion
                        or "Improve the docstring quality."
                    )
                else:
                    suggestion = verification.suggestion or "Improve the docstring quality."
                
                self.logger.info(
                    f"Verifier rejected (rejection {verifier_rejection_count}/"
                    f"{self._max_verifier_rejections}), refining with feedback: {suggestion}"
                )
                writer_result = self.writer.refine_documentation(context, suggestion)
                if writer_result.is_success():
                    documentation = writer_result.output
                    context.add_result('writer', documentation)
                # continue → verify the refined documentation
            
            if not broke_for_context:
                break  # Writer-Verifier loop ended (accepted/failed/exhausted)
        
        # Final result
        if documentation:
            self._insert_docstring_for_component(component, documentation)
        else:
            documentation = self._create_fallback_documentation(component)
        return documentation
    
    # ─── Main entry point ────────────────────────────────────────────────
    
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
        
        # Save consolidated verifier outputs
        try:
            if hasattr(self.verifier, 'save_consolidated_output'):
                verifier_consolidated_path = self.verifier.save_consolidated_output()
                if verifier_consolidated_path:
                    self.logger.info(f"Consolidated verifier outputs saved to: {verifier_consolidated_path}")
        except Exception as e:
            self.logger.warning(f"Failed to save consolidated verifier outputs: {e}")
        
        return documented_components
    
    # ─── Sequential processing ───────────────────────────────────────────
    
    def _process_sequential(
        self,
        components: List[CodeComponent],
        component_map: Dict[str, CodeComponent]
    ) -> List[Documentation]:
        """
        Process components sequentially with batch Reader Agent.
        Batches components in groups of 5 for Reader analysis,
        then processes each component individually through the unified pipeline.
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
            
            # Component types that have no valid Python docstring position.
            # Skipping them here prevents wasted writer+verifier LLM calls;
            # the inserter has identical guards as a safety net.
            _SKIP_COMPONENT_TYPES = {'global_variable', 'static_field', 'field'}

            # Process each component through the unified pipeline
            for idx, component in enumerate(batch):
                self.logger.info(
                    f"Processing component {batch_start + idx + 1}/{len(components)}: "
                    f"{component.name} ({component.type})"
                )

                # Resolve component type to a plain string regardless of whether
                # it's a ComponentType enum or already a string.
                _comp_type_str = component.type.value if hasattr(component.type, 'value') else str(component.type)
                if _comp_type_str in _SKIP_COMPONENT_TYPES:
                    self.logger.info(
                        f"Skipping {component.name} – type '{_comp_type_str}' "
                        f"has no valid Python docstring position"
                    )
                    with self._stats_lock:
                        self.docstrings_skipped += 1
                        self.total_components_processed += 1
                    continue

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
                    
                    # Create context with pre-loaded reader result
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
                            'project_dag': self.project_dag,
                            'calibration_history': {
                                'empty_searcher_results': 0,
                                'total_searcher_calls': 0,
                                'total_internal_found': 0,
                                'total_external_found': 0,
                                'rejection_count': 0,
                                'max_rejections': self._max_verifier_rejections,
                            },
                        }
                    )
                    
                    # Process through unified pipeline
                    doc = self._process_component_pipeline(
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
    
    # ─── Docstring insertion ─────────────────────────────────────────────
    
    def _insert_docstring_for_component(
        self,
        component: CodeComponent,
        raw_response
    ) -> None:
        """
        Insert the generated docstring into the source file for a component.
        Called immediately after the writer agent generates documentation.
        
        Args:
            component: The code component being documented
            raw_response: The raw LLM response string from writer agent,
                          or a Documentation object whose .docstring holds it
        """
        if not self._docstring_inserter:
            return

        # Accept both Documentation objects and plain strings
        if hasattr(raw_response, 'docstring'):
            raw_response = raw_response.docstring
        
        try:
            # Extract docstring from raw LLM response
            docstring = self._docstring_inserter.extract_docstring(raw_response)
            
            if not docstring:
                with self._stats_lock:
                    self.docstrings_failed += 1
                self.logger.warning(f"Failed to extract docstring for {component.name}")
                return
            
            # Clean the extracted docstring
            docstring = self._docstring_inserter._clean_docstring_artifacts(docstring)
            
            # Validate the docstring has meaningful content
            word_count = len(docstring.split())
            if word_count < 5:
                with self._stats_lock:
                    self.docstrings_failed += 1
                self.logger.warning(f"Docstring too short ({word_count} words) for {component.name}")
                return
            
            # Insert into source file
            doc_data = {'docstring': docstring}
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
    
    # ─── Parallel processing ─────────────────────────────────────────────
    
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
        Process a single component through the full agent pipeline.
        Used by parallel processing path where batch reader is not available.
        Delegates to the unified _process_component_pipeline.
        """
        # Skip component types that have no valid Python docstring position.
        _comp_type_str = component.type.value if hasattr(component.type, 'value') else str(component.type)
        if _comp_type_str in {'global_variable', 'static_field', 'field'}:
            self.logger.info(
                f"Skipping {component.name} – type '{_comp_type_str}' "
                f"has no valid Python docstring position"
            )
            with self._stats_lock:
                self.docstrings_skipped += 1
            return None

        # Use passed project_dag, with fallback to instance variable
        dag = project_dag or self.project_dag

        context = AgentContext(
            component=component,
            metadata={
                'previous_docs': previous_docs,
                'timestamp': datetime.now().isoformat(),
                'accumulated_context': {
                    'internal': [],
                    'external': []
                },
                'project_dag': dag,
                'calibration_history': {
                    'empty_searcher_results': 0,
                    'total_searcher_calls': 0,
                    'total_internal_found': 0,
                    'total_external_found': 0,
                    'rejection_count': 0,
                    'max_rejections': self._max_verifier_rejections,
                },
            }
        )
        
        return self._process_component_pipeline(component, context, component_map)

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
