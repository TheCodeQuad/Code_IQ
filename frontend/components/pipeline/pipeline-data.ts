export type StepStatus = 'pending' | 'running' | 'completed' | 'error' | 'skipped';

export interface PipelineStep {
  id: string;
  name: string;
  description: string;
  status: StepStatus;
  progress: number;
  logs: string[];
}

// Navigator Module - runs once for entire repository
export interface NavigatorModule {
  id: 'navigator';
  name: string;
  description: string;
  status: StepStatus;
  progress: number;
  steps: PipelineStep[];
  extractedComponents: ExtractedComponent[];
}

// Component types extracted from repository
export type ComponentType = 'function' | 'class' | 'method';

export interface ExtractedComponent {
  id: string;
  name: string;
  type: ComponentType;
  filePath: string;
  parentClass?: string; // For methods, the parent class name
}

// Agentic Module - runs per component
export interface AgenticIteration {
  componentId: string;
  componentName: string;
  componentType: ComponentType;
  filePath: string;
  parentClass?: string;
  status: StepStatus;
  currentStep: string;
  retryCount: number;
  maxRetries: number;
  steps: {
    reader: PipelineStep;
    searcher: PipelineStep;
    readerWithContext: PipelineStep;
    writer: PipelineStep;
    verifier: PipelineStep;
    writerRefine: PipelineStep;
    extraction: PipelineStep;
    insertion: PipelineStep;
  };
  verifierFeedback?: 'accepted' | 'rejected-to-reader' | 'rejected-to-writer';
  traversedToReader?: boolean;
  traversedToWriter?: boolean;
}

export interface AgenticModule {
  id: 'agentic';
  name: string;
  description: string;
  status: StepStatus;
  progress: number;
  totalComponents: number;
  completedComponents: number;
  currentIteration: number;
  iterations: AgenticIteration[];
}

// Finalization Module
export interface FinalizationModule {
  id: 'finalization';
  name: string;
  description: string;
  status: StepStatus;
  progress: number;
  steps: PipelineStep[];
}

export interface PipelineState {
  navigator: NavigatorModule;
  agentic: AgenticModule;
  finalization: FinalizationModule;
  overallProgress: number;
  isRunning: boolean;
  isPaused: boolean;
  startTime?: Date;
  endTime?: Date;
}

// Initial Navigator Module steps
export const NAVIGATOR_STEPS: PipelineStep[] = [
  {
    id: 'extract-components',
    name: 'Parsing Repository',
    description: 'Parse repository files to extract structural information',
    status: 'pending',
    progress: 0,
    logs: [],
  },
  {
    id: 'generate-metadata',
    name: 'Extracting Code Components',
    description: 'Identify and extract functions, classes, and variables',
    status: 'pending',
    progress: 0,
    logs: [],
  },
  {
    id: 'build-dependency-graph',
    name: 'Dependency Resolution',
    description: 'Resolve relationships between extracted components',
    status: 'pending',
    progress: 0,
    logs: [],
  },
  {
    id: 'create-dag',
    name: 'IR generation',
    description: 'Generate intermediate representation of the project structure',
    status: 'pending',
    progress: 0,
    logs: [],
  },
  {
    id: 'init-llm-pipeline',
    name: 'Topological sort',
    description: 'Determine execution order of components based on dependencies',
    status: 'pending',
    progress: 0,
    logs: [],
  },
  {
    id: 'load-graph',
    name: 'Dependency Acyclic Graph Generation',
    description: 'Construct the final acyclic dependency graph for processing',
    status: 'pending',
    progress: 0,
    logs: [],
  },
];

// Finalization steps
export const FINALIZATION_STEPS: PipelineStep[] = [
  {
    id: 'save-outputs',
    name: 'Save Agent Outputs',
    description: 'Save agent outputs to storage',
    status: 'pending',
    progress: 0,
    logs: [],
  },
  {
    id: 'generate-summary',
    name: 'Generate Pipeline Summary',
    description: 'Generate pipeline execution summary',
    status: 'pending',
    progress: 0,
    logs: [],
  },
  {
    id: 'pipeline-completed',
    name: 'Pipeline Completed',
    description: 'Mark pipeline as completed',
    status: 'pending',
    progress: 0,
    logs: [],
  },
];

// Sample extracted components (functions, classes, methods)
export const SAMPLE_EXTRACTED_COMPONENTS: ExtractedComponent[] = [
  { id: 'comp-1', name: 'authenticate_user', type: 'function', filePath: 'auth/login.py' },
  { id: 'comp-2', name: 'validate_credentials', type: 'function', filePath: 'auth/login.py' },
  { id: 'comp-3', name: 'UserModel', type: 'class', filePath: 'models/user.py' },
  { id: 'comp-4', name: 'save', type: 'method', filePath: 'models/user.py', parentClass: 'UserModel' },
  { id: 'comp-5', name: 'delete', type: 'method', filePath: 'models/user.py', parentClass: 'UserModel' },
  { id: 'comp-6', name: 'get_by_id', type: 'method', filePath: 'models/user.py', parentClass: 'UserModel' },
  { id: 'comp-7', name: 'register_user', type: 'function', filePath: 'auth/register.py' },
  { id: 'comp-8', name: 'hash_password', type: 'function', filePath: 'utils/crypto.py' },
  { id: 'comp-9', name: 'EmailService', type: 'class', filePath: 'services/email.py' },
  { id: 'comp-10', name: 'send', type: 'method', filePath: 'services/email.py', parentClass: 'EmailService' },
  { id: 'comp-11', name: 'validate_email', type: 'function', filePath: 'utils/validators.py' },
  { id: 'comp-12', name: 'APIRouter', type: 'class', filePath: 'api/routes.py' },
  { id: 'comp-13', name: 'handle_request', type: 'method', filePath: 'api/routes.py', parentClass: 'APIRouter' },
  { id: 'comp-14', name: 'AuthMiddleware', type: 'class', filePath: 'middleware/auth.py' },
  { id: 'comp-15', name: 'process', type: 'method', filePath: 'middleware/auth.py', parentClass: 'AuthMiddleware' },
  { id: 'comp-16', name: 'load_config', type: 'function', filePath: 'config/settings.py' },
];

export function createAgenticIteration(component: ExtractedComponent): AgenticIteration {
  return {
    componentId: component.id,
    componentName: component.name,
    componentType: component.type,
    filePath: component.filePath,
    parentClass: component.parentClass,
    status: 'pending',
    currentStep: '',
    retryCount: 0,
    maxRetries: 3,
    steps: {
      reader: {
        id: 'reader',
        name: 'Reader Analyzes',
        description: 'Reader analyzes component',
        status: 'pending',
        progress: 0,
        logs: [],
      },
      searcher: {
        id: 'searcher',
        name: 'Searcher Retrieves',
        description: 'Searcher retrieves dependencies/context',
        status: 'pending',
        progress: 0,
        logs: [],
      },
      readerWithContext: {
        id: 'reader-context',
        name: 'Reader Re-evaluates',
        description: 'Reader re-evaluates with context',
        status: 'pending',
        progress: 0,
        logs: [],
      },
      writer: {
        id: 'writer',
        name: 'Writer Generates',
        description: 'Writer generates docstring',
        status: 'pending',
        progress: 0,
        logs: [],
      },
      verifier: {
        id: 'verifier',
        name: 'Verifier Validates',
        description: 'Verifier validates docstring',
        status: 'pending',
        progress: 0,
        logs: [],
      },
      writerRefine: {
        id: 'writer-refine',
        name: 'Writer Refines',
        description: 'Writer refines docstring if rejected',
        status: 'pending',
        progress: 0,
        logs: [],
      },
      extraction: {
        id: 'extraction',
        name: 'Extract Docstring',
        description: 'Extract docstring from LLM response',
        status: 'pending',
        progress: 0,
        logs: [],
      },
      insertion: {
        id: 'insertion',
        name: 'Insert Docstring',
        description: 'Insert docstring into source code',
        status: 'pending',
        progress: 0,
        logs: [],
      },
    },
    traversedToReader: false,
    traversedToWriter: false,
  };
}

export function createInitialPipelineState(): PipelineState {
  return {
    navigator: {
      id: 'navigator',
      name: 'Navigator Module',
      description: 'Repository-level analysis and setup (runs once)',
      status: 'pending',
      progress: 0,
      steps: JSON.parse(JSON.stringify(NAVIGATOR_STEPS)),
      extractedComponents: [],
    },
    agentic: {
      id: 'agentic',
      name: 'Agentic Module',
      description: 'Per-component docstring generation',
      status: 'pending',
      progress: 0,
      totalComponents: 0,
      completedComponents: 0,
      currentIteration: 0,
      iterations: [], // Initially empty - populated after Navigator detects components
    },
    finalization: {
      id: 'finalization',
      name: 'Finalization',
      description: 'Save outputs and generate summary',
      status: 'pending',
      progress: 0,
      steps: JSON.parse(JSON.stringify(FINALIZATION_STEPS)),
    },
    overallProgress: 0,
    isRunning: false,
    isPaused: false,
  };
}
