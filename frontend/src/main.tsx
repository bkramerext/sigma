import { Component, createContext, createElement, forwardRef, lazy, Suspense, type Dispatch, type SetStateAction, useCallback, useContext, useEffect, useImperativeHandle, useLayoutEffect, useMemo, useRef, useState, type ErrorInfo, type FormEvent, type MouseEvent, type PointerEvent as ReactPointerEvent, type Ref, type ReactNode, type SyntheticEvent, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import SessionLogPage from './SessionLogPage';
import { adoptLatestWindowSignIn, windowAuthUrl } from './window-auth';
import SessionLogButton from './SessionLogButton';
import DialogDismissButton from './DialogDismissButton';
import ResumeAuthorizationDialog, { type ResumeAuthorization } from './ResumeAuthorizationDialog';
import { friendlyProviderError, isOpenAIProjectSpendLimit, openAIProjectSpendLimitCopy, providerInterruptionCopy, providerUsageLimitCopy, setSponsoredUsageConnection, type SponsoredInferenceProvider } from './provider-usage-guidance';
import { openReusableTab } from './reusable-tabs';
import ProjectDiagnosticsPanel, { type ProjectDiagnostic } from './ProjectDiagnosticsPanel';
import { reportProjectDiagnostic } from './project-diagnostic-report';
import { removeResearchSession } from './session-removal-request';
import { sourceMaterialOverflowCopy } from './source-material-error';
import { createRoot } from 'react-dom/client';
import './style.css';
import './workspace.css';
import './project-entry.css';
import './strategies.css';
import './project-settings.css';
import './recents.css';
import './copper-controls.css';
import './text-views.css';
import './papers-pane.css';
import './action-icons.css';
import { AIProvider, ConnectionStatus, ManageUsage, PlanWelcome, beginProviderRequest, watchResearchProviderActivity, useAI } from './ai-connection';
import { installRequestErrorToasts, reportRequestFailure, RequestErrorToasts } from './request-toast';
import { invitationWelcomePhrases } from './invitation-welcome-phrases';
import AboutProvenanceVision from './about-provenance';
import ChatPage from './ChatPage';
import ProjectTypesDialog, { type ProjectTypeRecord } from './ProjectTypesDialog';
import GlobalSettingsDialog from './GlobalSettingsDialog';
import SigmaSelect from './SigmaSelect';
import GlobalModelPill from './GlobalModelPill';
import ProjectDescriptionEditor, { type ProjectDescriptionDraft, type ProjectDescriptionEditorHandle } from './ProjectDescriptionEditor';
const RenderedMarkdown = lazy(() => import('./RenderedMarkdown'));

// A failure while presenting historical research must never unmount the app.
// This boundary does not write to projects, interrupt workers, or discard data.
class ResearchDisplayBoundary extends Component<
  { label: string; children: ReactNode },
  { message: string | null }
> {
  state: { message: string | null } = { message: null };

  static getDerivedStateFromError(error: unknown): { message: string } {
    return { message: error instanceof Error ? error.message : String(error) };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('SIGMA research display error:', this.props.label, error, info.componentStack);
  }

  render() {
    if (!this.state.message) return this.props.children;
    return <div className="workspace-state" role="alert">
      <strong>{this.props.label} could not be displayed.</strong>
      <p>The research is still available. This is a display error, not a session failure.</p>
      <p className="error">{this.state.message}</p>
      <button type="button" className="text-view-link" onClick={() => window.location.reload()}>Reload display</button>
      <a className="text-view-link" href="/">Return Home</a>
    </div>;
  }
}


// Prospective navigation rail; keep implementation available for later activation.
const ENABLE_WORKSPACE_SIDEBAR = false;
const SHOW_PROJECT_DETAILS_AND_HISTORY = false;
const MAX_STRATEGY_APPROACH = 50000;
const OPENAI_AGENT_CREDIT_ADJECTIVES = [
  'Intrepid', 'Plucky', 'Spirited', 'Tireless', 'Cheeky', 'Quirky', 'Scrappy', 'Whimsical', 'Spunky', 'Feisty',
  'Sassy', 'Saucy', 'Wacky', 'Goofy', 'Funky', 'Groovy', 'Jazzy', 'Snazzy', 'Dapper', 'Dashing',
  'Gallant', 'Valiant', 'Stellar', 'Bionic', 'Brainy', 'Canny', 'Crafty', 'Nimble', 'Spry', 'Astute',
  'Zealous', 'Fervent', 'Ardent', 'Stalwart', 'Dauntless', 'Audacious', 'Tenacious', 'Sparkly', 'Gleeful', 'Winsome',
  'Zany', 'Bubbly', 'Bouncy', 'Zesty', 'Zippy', 'Snappy', 'Peppy', 'Perky', 'Daring', 'Playful',
  'Nerdy', 'Witty', 'Fearless', 'Inventive', 'Mischievous', 'Eccentric', 'Impish', 'Rascally', 'Roguish', 'Jaunty',
  'Sprightly', 'Frisky', 'Perceptive', 'Ingenious', 'Wily', 'Sly', 'Cunning', 'Foxy', 'Kooky', 'Loopy',
  'Nutty', 'Dorky', 'Geeky', 'Dweeby', 'Zingy', 'Fizzy', 'Buzzy', 'Chirpy', 'Chipper', 'Perkyish',
  'Zazzy', 'Zappy', 'Zippyish', 'Squirrely', 'Ditsy', 'Daffy', 'Bonkers', 'Batty', 'Madcap', 'Zestyish',
  'Spiffy', 'Nifty', 'Swanky', 'Flashy', 'Glitzy', 'Glitzyish', 'Zappyish', 'Sparky', 'Snarky', 'Puckish',
  'Giddy', 'Gung-ho', 'Spunkyish',
] as const;

type Stage = 'draft' | 'ready' | 'exploring' | 'hold';
const stageLabels: Record<Stage, string> = { draft: 'Draft', ready: 'Ready to explore', exploring: 'Exploring', hold: 'On hold' };
type ResearchMode = string;
type ProjectDifficulty = 'easy' | 'medium' | 'hard';
const difficultyLabels: Record<ProjectDifficulty, string> = { easy: 'Easy', medium: 'Medium', hard: 'Hard' };
const difficultyLabel = (value: ProjectDifficulty | null): string => value ? difficultyLabels[value] : 'Not set';
const difficultyDescription = (value: ProjectDifficulty | null): string => value ? `${difficultyLabels[value]} difficulty` : 'Difficulty not set';
const researchTypes: { value: ResearchMode; label: string }[] = [
  { value: 'biology', label: 'Biology' },
  { value: 'chemistry', label: 'Chemistry' },
  { value: 'computer_science', label: 'Computer Science' },
  { value: 'economics', label: 'Economics' },
  { value: 'engineering', label: 'Engineering' },
  { value: 'law', label: 'Law' },
  { value: 'literature', label: 'Literature' },
  { value: 'mathematical', label: 'Mathematics' },
  { value: 'medical', label: 'Medical' },
  { value: 'military', label: 'Military' },
  { value: 'philosophy', label: 'Philosophy' },
  { value: 'physics', label: 'Physics' },
  { value: 'religion', label: 'Religion' },
];
let projectTypeCache: ProjectTypeRecord[] = [];
const researchTypeLabels: Record<string, string> = Object.fromEntries(researchTypes.map(item => [item.value, item.label]));
const researchTypeLabel = (value: string | null | undefined) => value ? projectTypeCache.find(item => item.id === value)?.name ?? researchTypeLabels[value] ?? `Unavailable · ${value}` : 'Unavailable';
type Strategy = {
  id: string;
  title: string;
  approach: string;
  stage: Stage;
  summary: string;
  provenance: { provider: string; model: string; reasoning_effort?: string | null } | null;
  author_kind: 'human';
  enabled: boolean;
  created_at: string;
  removed_at?: string | null;
};
type ProjectView = {
  path: string;
  project: {
    id: string;
    title: string;
    problem: string;
    desired_outcomes: string;
    paper_requirements: string;
    schema_version: number;
    backend_build_commit?: string | null;
    ai_model: string;
    reasoning_effort: string;
    difficulty: ProjectDifficulty | null;
    show_advanced_outcome_details: boolean;
    investigation_type: ResearchMode;
    project_type_snapshot?: ProjectTypeRecord | null;
    events: { sequence: number; kind: string; timestamp: string; strategy_id?: string | null;
      project_change?: { previous: Settings; current: Settings } | null;
      order?: string[] | null; stage_change?: { previous: Stage; stage: Stage } | null;
      change?: { previous_title: string; previous_approach: string; title: string; approach: string } | null }[];
    strategies: Strategy[];
    active_order: string[];
  };
};

type ResearchArtifact = { id: string; session_id?: string; strategy_id?: string; strategy_cycle?: number; sequence: number; claim_or_question: string; method: string; assumptions: string[]; evidence_status: string; skeptic_response: string; objections: string[]; open_obligations: string[]; coordinator_decision: string; next_question: string; note: string; investigator_output: Record<string, unknown>; skeptic_output: Record<string, unknown> };
type ResearchEvent = { sequence: number; timestamp: string; kind: string; role?: string | null; message: string };
type ContextManifest = { policy_version?: string; byte_limit?: number; assembled_context_bytes?: number; selected_count?: number; omitted_count?: number; note?: string; obligation_disposition_counts?: Record<string, number>; omitted_obligations?: { count: number; obligation_ids: string[]; reason: string }; omitted_peer_evidence?: { count: number; artifact_ids: string[]; reason: string }; omitted_project_strategies?: { count: number; strategy_ids: string[]; reason: string }; sources?: { source_ids?: string[]; category?: string; reason?: string; representation?: string; status?: string }[]; omitted_prior_session_findings?: { count: number; source_ids: string[]; reason: string }; omitted_prior_failures?: { count: number; attempt_ids: string[]; reason: string } };
type ResearchStep = { id: string; strategy_id?: string | null; cycle: number; role: string; status: string; started_at: string; finished_at?: string; call_number: number; failure_kind?: string | null; provider_http_status?: number | null; provider_response_channel?: 'http' | 'stream'; provider_stream_event?: 'response.failed' | 'error'; provider_error_code?: string; failure_message?: string; interruption_reason?: string | null; context_artifact_ids?: string[]; prior_session_artifact_ids?: string[]; peer_strategy_artifact_ids?: string[]; peer_handoff_artifact_ids?: string[]; peer_handoff_ids?: string[]; human_intervention_ids?: string[]; context_manifest?: ContextManifest; provider_input_audit?: { kind: string; status: string; headers_included: boolean; request_body: Record<string, unknown> }; potential_truncation_fields?: string[]; token_usage_status?: string; output?: Record<string, unknown> };
type InterventionDelivery = { strategy_id: string; role: 'investigator' | 'skeptic'; status: string; target_cycle?: number | 'next_eligible'; acknowledged_at?: string; uptake?: string; rationale?: string; attempts: { step_id: string; cycle?: number; status: string; delivered_at: string; acknowledged_at?: string; uptake?: string; rationale?: string }[] };
type ResearchIntervention = { id: string; kind: 'objection' | 'evidence' | 'priority'; text: string; status: string; submitted_at: string; target_strategy_ids: string[]; target_roles: ('investigator' | 'skeptic')[]; rejection_reason?: string; superseded_by?: string; deliveries: InterventionDelivery[] };
type PriorSessionFinding = { id: string; sequence: number; claim_or_question: string; method: string; assumptions?: string[]; evidence_status: string; objections: string[]; open_obligations: string[]; coordinator_decision: string; next_question: string; session_id: string; session_number: number; strategy_id: string; strategy_title: string; obligation_reviews?: { obligation_id: string; status: string; basis_artifact_ids: string[]; basis_step_ids: string[]; rationale: string; epistemic_status: string }[] };
type ResearchStrategyRun = { strategy_id: string; strategy_title: string; status: string; current_action: string; current_question: string; cycle: number; research_round?: number; paired_turn_in_round?: number; completed_pairs?: number; calls_used: number; artifacts: string[]; reason?: string | null };
type PortfolioStrategyAction = { strategy_id: string; strategy_title: string; action: string; rationale: string; basis_artifact_ids: string[]; next_question: string };
type PortfolioCombination = { strategy_ids: string[]; basis_artifact_ids: string[]; rationales: string[]; status: string };
type PortfolioRelation = { source_strategy_id: string; source_artifact_id: string; target_strategy_id: string; target_artifact_id: string; relation: string; rationale: string };
type PortfolioDecision = { status?: string; strategy_actions?: PortfolioStrategyAction[]; combination_candidates?: PortfolioCombination[]; conflict_candidates?: PortfolioRelation[]; overlap_warnings?: PortfolioRelation[]; limitations?: string[] };
type OutcomeMetric = { label: string; value: string; detail?: string };
type ResearchOutcomeMetrics = { operational: OutcomeMetric[]; research_quality: OutcomeMetric[]; sources: { session_id: string | null; step_ids: string[]; artifact_ids: string[]; execution_ids: string[]; strategy_ids: string[] } };
type OutcomeArgumentStep = { number: number; title: string; argument: string; epistemic_status: string; basis_artifact_ids: string[]; research_artifact_id?: string; review?: { disposition: string; rationale: string; objection?: string; basis_artifact_ids: string[] } };
type StrategyFinding = { strategy_id: string; strategy_title: string; status: string; execution_status?: string; failure_reason?: string; claim: string; research_artifact_id: string; research_artifact_ids?: string[]; reasoning_steps: OutcomeArgumentStep[]; skeptic_response: string; objections: string[]; open_obligations: string[] };
type ResearchMethodReference = { id: string; tier: 'general' | 'discipline' | 'branch'; title: string; url: string; notes: string; branch?: string };
type ResearchCompilationAttempt = { number: number; status: string; started_at?: string; finished_at?: string; failure_type?: string | null; provider_http_status?: number | null; provider_error_code?: string | null; provider_response_status?: string | null; validation_failure?: string | null; token_usage?: { input_tokens?: number; cached_input_tokens?: number; output_tokens?: number } | null; usage_status?: string; retry_decision?: string; retry_delay_seconds?: number | null; reason?: string };
type ResearchMethodCompilation = { version: string; status: string; source_count: number; guidance?: string; rationale?: string; selected_source_ids?: string[]; omitted_source_ids?: string[]; source_sha256?: string; guidance_sha256?: string; started_at?: string; finished_at?: string; reason?: string; token_usage?: { input_tokens?: number; cached_input_tokens?: number; output_tokens?: number }; attempts?: ResearchCompilationAttempt[]; failure_type?: string; validation_failure?: string; usage_status?: string; provider_http_status?: number; provider_error_code?: string };
type ResearchSourceMaterial = { version: string; status: string; mode: string; branch?: string | null; sources: ResearchMethodReference[]; compilation?: ResearchMethodCompilation; source_session_id?: string | null; selection_reason?: string; sha256?: string };
type ExecutionProvenance = { records: { id: string; runtime: string; statuses: string[]; artifact_ids: string[]; step_ids: string[]; source_recorded: boolean; output_recorded: boolean }[]; unidentified_count: number; completed_count: number; completed_without_recorded_io_count?: number; other_count: number; note: string };
type ResearchOutcome = { assessment: 'pending' | 'positive' | 'mixed' | 'negative'; label: string; verification_label?: string; argument_availability?: { status: 'structured' | 'narrative' | 'not_recorded'; label: string }; summary?: string; conclusion?: string; caveats?: string[]; basis_artifact_ids?: string[]; provisional: boolean; source_material?: ResearchSourceMaterial; execution_provenance?: ExecutionProvenance; metrics?: ResearchOutcomeMetrics; solution_review?: { status: string; claim?: string; claim_scope?: 'conditional' | 'unconditional' | 'disputed'; argument_summary?: string; skeptic_response?: string; skeptic_objections?: string[]; open_obligations?: string[]; argument_steps?: OutcomeArgumentStep[]; strategy_findings?: StrategyFinding[]; assumptions?: string[]; proof_obligations?: string[]; verification_status?: string; unresolved_objections?: string[]; resolved_objections?: string[]; basis_artifact_ids?: string[] } | null };
type StrategyAssessment = { strategy_id: string | null; strategy_title: string; assessment: 'contributed_to_solution' | 'productive' | 'unproductive' | 'not_used' | 'disabled' | 'unknown'; rationale: string; basis_artifact_ids: string[] };
type ResearchSession = { investigation_type?: string; provider_usage_limited?: boolean; cloud_sponsored?: boolean; research_method_sources?: { advisory?: string | null; sources?: unknown[] }; approved_continuations?: Record<string, { parent_strategy_id: string; question: string; packet_digest: string; sources: { artifact_id: string; source: EvidencePointer; status: string; verification: string; claim: string; strategy_title: string; artifact: Record<string, unknown> }[]; rejected_sources: { artifact_id: string; rationale: string }[] }>; id: string; project_id?: string; problem?: string; session_number: number; strategy_id: string; strategy_title: string; strategy_text?: string; strategy_ids?: string[]; strategy_snapshot?: Record<string, unknown>; strategy_runs?: ResearchStrategyRun[]; portfolio_decision?: PortfolioDecision | null; peer_handoffs_prompted?: unknown[]; interventions?: ResearchIntervention[]; status: 'queued' | 'running' | 'paused' | 'stopped' | 'completed' | 'ended' | 'failed'; backend_build_commit?: string | null; model: string; reasoning_effort: string; mode: string; calls_used: number; call_limit: number; cycle: number; cycle_limit?: number; scheduler_version?: number; turns_per_round?: number; research_round?: number; research_round_limit?: number; paired_turn_in_round?: number; configured_duration_limit_minutes?: number | null; duration_limit_minutes?: number | null; termination_reason_code?: string; current_question: string; current_action: string; message: string; next_step_guidance?: string; recoverable_clipped_response?: boolean; protocol_completed_calls?: number; protocol_target_calls?: number; provider_limit_continuation?: { eligible: boolean; missing_calls: number; reason?: string | null }; artifacts: ResearchArtifact[]; prior_session_findings?: PriorSessionFinding[]; strategy_assessments?: StrategyAssessment[]; steps: ResearchStep[]; events: ResearchEvent[]; created_at: string; updated_at: string; started_at?: string; elapsed_seconds?: number; output_token_limit?: number; tokens_used?: number | null; token_usage_status?: string; estimated_cost_usd?: number | null; cost_status?: string; outcome: ResearchOutcome };


/**
 * API/project snapshots can contain historical or partially persisted sessions.
 * Normalize render-only fields without modifying the saved research record.
 */
function sessionForDisplay(value: unknown): ResearchSession | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const raw = value as Partial<ResearchSession>;
  if (typeof raw.id !== 'string' || !raw.id) return null;
  const missing = ['steps', 'events', 'artifacts', 'outcome'].filter(key => !(key in raw));
  if (missing.length) console.warn('Research session has incomplete display fields', { id: raw.id, missing });
  const statuses = ['queued', 'running', 'paused', 'stopped', 'completed', 'ended', 'failed'] as const;
  const assessments = ['pending', 'positive', 'mixed', 'negative'] as const;
  const outcome = raw.outcome && typeof raw.outcome === 'object' && !Array.isArray(raw.outcome)
    ? raw.outcome : null;
  const branches = Array.isArray(raw.strategy_runs) ? raw.strategy_runs.filter(branch =>
    !!branch && typeof branch === 'object' && !Array.isArray(branch))
    .map(branch => ({ ...branch, artifacts: Array.isArray(branch.artifacts) ? branch.artifacts : [] })) : undefined;
  const priorFindings = Array.isArray(raw.prior_session_findings)
    ? raw.prior_session_findings.filter(finding =>
      !!finding && typeof finding === 'object' && !Array.isArray(finding))
      .map(finding => ({
        ...finding,
        assumptions: Array.isArray(finding.assumptions) ? finding.assumptions : [],
        objections: Array.isArray(finding.objections) ? finding.objections : [],
        open_obligations: Array.isArray(finding.open_obligations) ? finding.open_obligations : [],
        obligation_reviews: Array.isArray(finding.obligation_reviews) ? finding.obligation_reviews : [],
      }))
    : [];
  return {
    ...raw,
    session_number: typeof raw.session_number === 'number' && Number.isFinite(raw.session_number) ? raw.session_number : 0,
    strategy_id: typeof raw.strategy_id === 'string' ? raw.strategy_id : '',
    strategy_title: typeof raw.strategy_title === 'string' ? raw.strategy_title : 'Research session',
    status: statuses.includes(raw.status as typeof statuses[number]) ? raw.status as ResearchSession['status'] : 'failed',
    current_question: typeof raw.current_question === 'string' ? raw.current_question : '',
    current_action: typeof raw.current_action === 'string' ? raw.current_action : 'Activity unavailable',
    message: typeof raw.message === 'string' ? raw.message : '',
    calls_used: typeof raw.calls_used === 'number' && Number.isFinite(raw.calls_used) ? raw.calls_used : 0,
    call_limit: typeof raw.call_limit === 'number' && Number.isFinite(raw.call_limit) ? raw.call_limit : 0,
    cycle: typeof raw.cycle === 'number' && Number.isFinite(raw.cycle) ? raw.cycle : 0,
    steps: Array.isArray(raw.steps) ? raw.steps : [],
    events: Array.isArray(raw.events) ? raw.events : [],
    artifacts: Array.isArray(raw.artifacts) ? raw.artifacts : [],
    strategy_runs: branches,
    prior_session_findings: priorFindings,
    outcome: {
      ...(outcome ?? {}),
      assessment: assessments.includes(outcome?.assessment as typeof assessments[number])
        ? outcome?.assessment as ResearchOutcome['assessment'] : 'pending',
      label: typeof outcome?.label === 'string' ? outcome.label : 'Outcome unavailable',
      provisional: typeof outcome?.provisional === 'boolean' ? outcome.provisional : true,
    },
  } as ResearchSession;
}

/**
 * Historical sessions can finish every configured Investigator/Skeptic slot
 * while retaining a legacy round-limit termination code. Derive completion
 * from accepted role slots, not the attempt ceiling or an old status label.
 * This is display-only: it never rewrites saved research or usage accounting.
 */
function sessionHasAcceptedEveryConfiguredTurn(session: ResearchSession): boolean {
  const ids = session.strategy_ids;
  const branches = session.strategy_runs;
  const cycles = session.cycle_limit;
  if (!Array.isArray(ids) || ids.length === 0 || !Array.isArray(branches)
    || branches.length !== ids.length || typeof cycles !== 'number'
    || !Number.isInteger(cycles) || cycles < 1
    || ids.some(id => typeof id !== 'string' || !id)
    || new Set(ids).size !== ids.length
    || branches.some(branch => !ids.includes(branch.strategy_id))
    || new Set(branches.map(branch => branch.strategy_id)).size !== ids.length) return false;
  const accepted = new Set(session.steps
    .filter(step => step.status === 'completed'
      && (step.role === 'investigator' || step.role === 'skeptic')
      && typeof step.strategy_id === 'string' && ids.includes(step.strategy_id)
      && Number.isInteger(step.cycle) && step.cycle >= 1 && step.cycle <= cycles)
    .map(step => JSON.stringify([step.strategy_id, step.role, step.cycle])));
  return accepted.size === ids.length * cycles * 2;
}

function sessionOffersResume(session: ResearchSession): boolean {
  if (!['stopped', 'paused', 'failed', 'ended'].includes(session.status)) return false;
  if (['protocol_complete', 'research_completed_early'].includes(session.termination_reason_code ?? '')) return false;
  return !sessionHasAcceptedEveryConfiguredTurn(session);
}

function sessionEstimatedCostLabel(session: ResearchSession): string {
  const cost = session.estimated_cost_usd;
  // ChatGPT tokens are not billed to the operator's API account; show the
  // model-priced equivalent, never imply this was a paid API charge.
  const label = session.mode === 'chatgpt' ? 'API-rate equivalent' : 'Est. cost';
  if (session.cost_status !== 'available' || typeof cost !== 'number' || !Number.isFinite(cost) || cost < 0) {
    return `${label} unavailable`;
  }
  // This is the accumulated session estimate, not an API charge. Render in USD
  // with three decimal places; avoid rounding tiny positive amounts to $0.000.
  const amount = cost.toLocaleString('en-US', {
    style: 'currency', currency: 'USD', minimumFractionDigits: 3, maximumFractionDigits: 3,
  });
  return cost > 0 && cost < 0.001 ? `${label} <$0.001` : `${label} ${amount}`;
}

function compilationBarrierActive(session: ResearchSession): boolean {
  if (session.status !== 'queued' && session.status !== 'running') return false;
  const status = session.outcome.source_material?.compilation?.status;
  if (typeof status === 'string') return status === 'pending' || status === 'running';
  // A pre-compiler or partially migrated session may expose only its action.
  // Never let stale action text override a persisted completed/fallback state.
  return /compiling (?:research references|supplied evidence)/i.test(session.current_action);
}

function parallelSessionActivity(session: ResearchSession): string | null {
  if (session.status !== 'running' || compilationBarrierActive(session)) return null;
  if (!session.strategy_runs || session.strategy_runs.length <= 1) return null;
  const active = new Set((session.steps ?? []).filter(step => step.status === 'running').map(step => step.strategy_id));
  const waiting = session.strategy_runs.filter(branch =>
    (branch.status === 'queued' || branch.status === 'running') && !active.has(branch.strategy_id),
  ).length;
  return `${active.size} in flight · ${waiting} waiting`;
}

function strategyLiveStatusLines(session: ResearchSession): { id: string; label: string; detail: string }[] {
  // Compilation is the session-wide barrier before any strategy fanout.
  const compilation = session.outcome.source_material?.compilation;
  if (compilationBarrierActive(session)) {
    const supplied = /compiling source material/i.test(session.current_action);
    return [{
      id: supplied ? 'supplied-evidence-compilation' : 'reference-compilation',
      label: supplied ? 'Compiling source material' : compilation?.status === 'pending' ? 'Preparing research standards' : 'Compiling research standards',
      detail: supplied ? session.message : 'Preparing shared guidance for all strategies…',
    }];
  }
  if (!['running', 'queued'].includes(session.status) || !session.strategy_runs || session.strategy_runs.length <= 1) return [];
  const active = new Map(
    session.steps.filter(step => step.status === 'running' && step.strategy_id)
      .map(step => [step.strategy_id, step] as const),
  );
  return session.strategy_runs.map((branch, index) => {
    const step = active.get(branch.strategy_id);
    const action = branch.current_action || '';
    const role = step?.role === 'skeptic' || /skeptic/i.test(action) ? 'Skeptic'
      : step?.role === 'investigator' || /investigator/i.test(action) ? 'Investigator'
        : /coordinat/i.test(action) ? 'Coordinator'
          : branch.status === 'queued' ? 'Queued'
            : branch.status === 'paused' ? 'Paused'
              : branch.status === 'failed' ? 'Failed'
                : branch.status === 'ended' ? 'Ended' : 'Waiting';
    const detail = step
      ? branch.current_question || 'In progress'
      : branch.status === 'queued' && branch.current_question ? branch.current_question
        : branch.reason || (action && !['Investigator', 'Skeptic'].includes(action) ? action : 'In progress');
    // The label already identifies the activity. Do not echo it in the detail.
    const redundantPrefix = role === 'Coordinator' ? /^Coordinat(?:ing|or)\b[\s:·–—-]*/i
      : role === 'Waiting' ? /^Waiting(?: for)?\b[\s:·–—-]*/i
        : role === 'Paused' ? /^(?:Paused|Pausing)\b[\s:·–—-]*/i
          : role === 'Failed' ? /^Failed\b[\s:·–—-]*/i
            : role === 'Ended' ? /^Ended\b[\s:·–—-]*/i
              : role === 'Queued' ? /^Queued\b[\s:·–—-]*/i : null;
    const compact = (redundantPrefix ? detail.replace(redundantPrefix, '') : detail).replace(/\s+/g, ' ').trim() || 'In progress';
    return { id: branch.strategy_id, label: `S${index + 1}/${role}`, detail: compact.length > 150 ? `${compact.slice(0, 147)}…` : compact };
  });
}

function outcomeDisplayLabel(session: ResearchSession): string {
  return `${session.outcome.label}${session.outcome.provisional ? ' · provisional' : ''}`;
}

function stoppedSessionGuidance(session: ResearchSession): { cause: string; next: string } {
  // A deliberate stop takes precedence over stale funding or provider diagnostics.
  if (session.status === 'stopped' && (/stopped by user|stopped by you/i.test(session.message) || session.termination_reason_code === 'user_stop')) {
    return { cause: 'Stopped by user. A dispatched provider request may still consume allowance.', next: 'Resume when you are ready.' };
  }
  const action = session.current_action.toLowerCase();
  // Aggregate session messages can be replaced by later branch activity. Keep
  // the persisted typed guard diagnostic discoverable after a multi-strategy
  // stop, without guessing that an unrelated provider error was a byte guard.
  const rawMessage = session.message.trim();
  const guardDetails = /SIGMA's [\\d,]+-byte UTF-8 dispatch guard|SIGMA context manifest requires|Source Material contains/i;
  const branchGuard = session.strategy_runs
    ?.map(branch => branch.reason || '')
    .find(reason => guardDetails.test(reason));
  const message = guardDetails.test(rawMessage) ? rawMessage : (branchGuard || rawMessage);
  const typedReason = [...session.steps].reverse().find(step => step.failure_kind || step.interruption_reason);
  const recordedReason = [message, typedReason?.failure_kind, typedReason?.interruption_reason].filter(Boolean).join(' · ')
    .replace(/\bpaused\b/gi, 'stopped').replace(/\bpausing\b/gi, 'stopping').replace(/\bpause\b/gi, 'stop');
  const hasCompleteFinding = session.artifacts.some(artifact =>
    Object.keys(artifact.investigator_output).length > 0 && Object.keys(artifact.skeptic_output).length > 0);
  const evidence = `${action} ${recordedReason}`;
  // Provider error codes are not project-change diagnoses. In particular,
  // project_spend_limit_exceeded contains the word "project" and must never
  // be interpreted by the generic project/strategy guard below.
  const compilation = session.outcome.source_material?.compilation;
  const lastCompilerAttempt = compilation?.attempts?.at(-1);
  const providerErrorCode = lastCompilerAttempt?.provider_error_code ?? compilation?.provider_error_code ?? '';
  if (isOpenAIProjectSpendLimit(`${evidence} ${providerErrorCode}`)) {
    const copy = openAIProjectSpendLimitCopy();
    return { cause: copy.description, next: copy.next };
  }
  if (/required reference compilation/i.test(evidence))
    return {
      cause: recordedReason,
      next: 'Review Outcome → Research Standards. After correcting the compilation failure, Resume can make a new separately budgeted attempt when the safety limits permit it.',
    };
  // Preserve branch-local context diagnostics after aggregate messages change.
  // Ignore branches not currently paused/stopped/failed.
  const contextBranchReasons = /context/i.test(evidence)
    ? (session.strategy_runs ?? [])
      .filter(run => ['paused', 'stopped', 'failed'].includes(run.status)
        && typeof run.reason === 'string' && /context|dispatch guard/i.test(run.reason))
      .map(run => run.reason || '')
    : [];
  const contextDiagnosis = [message, ...contextBranchReasons].join(' · ');
  if (/clipped|output.token limit/.test(evidence))
    return { cause: 'The provider response was clipped before a complete research finding was saved.', next: 'Review provider allowance and session limits before resuming. Another provider call can consume allowance.' };
  // SIGMA's fixed UTF-8 safety guard is separate from a provider model's
  // token context window. Thinking level does not change this byte guard.
  const modelSelection = session.model || 'Unknown model';
  if (/SIGMA's [\d,]+-byte UTF-8 dispatch guard/i.test(contextDiagnosis) ||
      (/256 KB UTF-8 byte limit/i.test(contextDiagnosis) && /Context size:/i.test(contextDiagnosis))) {
    const match = /Context size:\s*(\d+)B\s*\/\s*limit\s*(\d+)B/i.exec(contextDiagnosis);
    const sizes = match
      ? `Required ${Number(match[1]).toLocaleString('en-US')} bytes; SIGMA limit ${Number(match[2]).toLocaleString('en-US')} bytes.`
      : 'SIGMA enforces an internal UTF-8 dispatch limit after non-destructive compaction.';
    return {
      cause: `SIGMA blocked the next research call because mandatory context exceeds its internal byte limit. ${sizes} Selected model: ${modelSelection}. This is not a model-specific context-window limit. Research is preserved.`,
      next: 'Review the context-size diagnostics. If this error was saved under an older SIGMA guard, updating and clicking Resume may permit the preserved context to proceed; a successful dispatch can consume allowance. If it still exceeds the current bound, narrow mandatory source material for a new session. Switching models alone does not change SIGMA’s guard.',
    };
  }
  if (/SIGMA context manifest requires|research context manifest exceeds its storage bound/i.test(contextDiagnosis)) {
    return {
      cause: `SIGMA blocked the next research call because the source-evidence manifest exceeded its separate storage bound. Selected model: ${modelSelection}. Research is preserved.`,
      next: 'Review the selected source material and start a narrower session. Changing models does not increase SIGMA’s manifest storage limit.',
    };
  }
  // A frozen Source Material overflow is not a model context failure. Use
  // the saved backend measurement (or its historical blocked event) so users
  // can see the size and reduce their source selection before a new session.
  if (/source material contains|source material exceeds context limit/i.test(evidence)) {
    return sourceMaterialOverflowCopy(
      session.message,
      session.events,
      session.strategy_runs?.map(branch => branch.reason || ''),
    );
  }
  if (/context|token limit/.test(evidence))
    return { cause: `Research stopped because a context limit was reached. Selected model: ${modelSelection}. Research is preserved; the exact limit source has not been established.`, next: session.next_step_guidance?.trim() || 'Inspect session diagnostics, including recorded strategy reasons and failed-attempt metadata, to identify whether SIGMA or the provider enforced the limit before choosing a recovery action.' };
  if (/duration|wall.clock/.test(evidence))
    return { cause: 'This session stopped after reaching its configured elapsed-time limit. Research is preserved.', next: 'Adjust the project time limit if appropriate, then resume the session.' };
  if (/stopped by user|stopped by you/i.test(recordedReason))
    return { cause: recordedReason, next: 'Resume when you are ready. A previously dispatched provider request may still consume allowance.' };
  if (/cost|budget|allowance|funding|spend ceiling/i.test(evidence))
    return { cause: recordedReason || 'A provider-call funding reservation was denied. Research is preserved.', next: 'Check the specific funding denial above before resuming. Retrying cannot bypass a depleted allowance.' };
  if (/model|connection|billing identity/.test(evidence))
    return { cause: 'The selected model or AI connection changed while this session was stopped. Research is preserved.', next: 'Check the AI connection and selected model before resuming.' };
  if (/project|strategy/.test(evidence))
    return { cause: 'The project or one of its strategies changed while this session was stopped. Research is preserved.', next: 'Review the current project and strategy before resuming.' };
  if (/restart|interrupted/.test(evidence))
    return { cause: 'The session was interrupted when its backend work stopped. Research is preserved.', next: 'Resume when you are ready; a previously dispatched provider request may already have used allowance.' };
  if (/stopped by user|stopped by you/i.test(recordedReason))
    return { cause: recordedReason, next: 'Resume when you are ready. A previously dispatched provider request may still consume allowance.' };
  if (recordedReason) return { cause: recordedReason, next: 'Review the stop details above, then resume when the project and AI connection are ready. Backend safeguards still apply.' };
  if (!hasCompleteFinding) return { cause: 'The session was stopped before completing a finding.', next: 'Resume when you are ready; backend safeguards still apply.' };
  return { cause: 'The session is stopped. Research is preserved.', next: 'Review the findings, then resume when the project and AI connection are ready. Backend safeguards still apply.' };
}

function StoppedSessionNotice({ session, dismissed, onDismiss }: {
  session: ResearchSession; dismissed: boolean; onDismiss: () => void;
}) {
  const cloud = useCloudIdentity();
  if (dismissed) return null;
  if (session.provider_usage_limited && ['paused', 'stopped', 'ended', 'failed'].includes(session.status)) {
    const sponsored = session.cloud_sponsored === true || cloud?.funding.selectedConnection === 'sponsored' || cloud?.target === 'hosted';
    const copy = providerUsageLimitCopy(sponsored, session.mode === 'chatgpt');
    return <SessionNotice number={session.session_number} onDismiss={onDismiss}
      title={copy.title}
      kind="stopped-session-guidance" ariaLabel={`Why session ${session.session_number} stopped and what to do next`}>
      <p>{copy.description}</p>
      <p><strong>Next:</strong> {sponsored ? 'Try Resume again in a few hours.' : copy.next}</p>
    </SessionNotice>;
  }
  const guidance = stoppedSessionGuidance(session);
  // Only the second Source Material mention (in the Next instruction) links
  // to the editable project sources; the cause remains plain explanation.
  const sourceLinkAt = guidance.cause.startsWith('Too much Source Material.')
    ? guidance.next.indexOf('Source Material') : -1;
  const nextGuidance = sourceLinkAt < 0 ? guidance.next : <>
    {guidance.next.slice(0, sourceLinkAt)}
    <a href="#sigma-supplied-evidence-heading" className="session-notice-source-link"
      onClick={event => {
        event.preventDefault();
        window.dispatchEvent(new Event('sigma-reveal-source-material'));
      }}>Source Material</a>
    {guidance.next.slice(sourceLinkAt + 'Source Material'.length)}
  </>;
  const hasCompleteFinding = session.artifacts.some(artifact =>
    Object.keys(artifact.investigator_output).length > 0 && Object.keys(artifact.skeptic_output).length > 0);
  const title = session.status === 'failed' ? 'Session failed' : 'Stopped';
  return <SessionNotice number={session.session_number} onDismiss={onDismiss} title={title} kind="stopped-session-guidance" ariaLabel={`Why session ${session.session_number} stopped and what to do next`}>
    <p><strong>Why it stopped:</strong> {guidance.cause}</p><p><strong>Next:</strong> {nextGuidance}</p>
    {!hasCompleteFinding && <p>The session is stopped and has not completed an Investigator/Skeptic finding. No answer to the project question is established yet.</p>}
  </SessionNotice>;
}
type EvidencePointer = { project_id: string; session_id: string; session_number: number; strategy_id: string; artifact_id: string; artifact_sequence: number; record_path: string; available: boolean };
type CurrentFinding = { id: string; text: string; investigated_claim: string; source: EvidencePointer; status: string; verification: string; strategy_title: string; objections: string[]; evidence_kind: string };
type CurrentQuestion = { id: string; text: string; status: string; actionable: boolean; sources: EvidencePointer[]; narrative_resolution_sources: EvidencePointer[]; note: string; dispositions: { source: EvidencePointer; valid: boolean; rationale: string }[] };
type CurrentUnderstanding = { version: number; project_id: string; session_count: number; project_status: string; scope_note: string; findings: CurrentFinding[]; current_finding_ids: string[]; obligations: CurrentQuestion[]; changes: { kind: string; text: string; source: EvidencePointer; earlier: EvidencePointer | null; caution: string }[]; next_investigations: { obligation_id: string; question: string; source: EvidencePointer; qualification: string }[]; failures: { session_id: string; session_number: number; status: string; note: string }[]; limitations: string[] };
type ResearchLimits = { research_rounds: number; turns_per_round: number; scheduler_version: number; model_calls: number; session_duration_minutes: number | null; output_tokens_per_call: number; maximum_estimated_cost_usd: number | null; maximum_input_tokens_per_session?: number | null; max_concurrent_sessions: string };
type DurationUnit = 'minutes' | 'hours' | 'days' | 'unlimited';
type ProjectSettingsTab = 'main' | 'limits' | 'preferences';
function savedProjectSettingsTab(): ProjectSettingsTab {
  try {
    const tab = window.localStorage.getItem('sigma.projectSettingsTab');
    if (tab === 'limits' || tab === 'preferences') return tab;
  } catch { /* Use the default tab when browser storage is unavailable. */ }
  return 'main';
}
function savedHomeGroupOpen(kind: 'sample' | 'recent', key: string): boolean {
  try { return window.localStorage.getItem(`sigma.home.${kind}Group:${key}`) === 'true'; }
  catch { return false; }
}
type ResearchLimitsDraft = { research_rounds: string; turns_per_round: string; session_duration_value: string; session_duration_unit: DurationUnit; output_tokens_per_call: string; maximum_estimated_cost_usd: string; maximum_input_tokens_per_session: string; max_concurrent_sessions: string };
function outcomeArtifactReferences(ids: string[] | undefined, session: ResearchSession): string {
  return ids?.map(id => `Artifact ${session.artifacts.find(artifact => artifact.id === id)?.sequence ?? '?'}`).join(', ') || 'No artifact references';
}

// Labels come from the shared Python research-epistemics projection, including exports.
function outcomeVerificationLabel(outcome: ResearchOutcome): string {
  return outcome.verification_label || 'Not recorded';
}
function outcomeArgumentLabel(outcome: ResearchOutcome): string {
  return outcome.argument_availability?.label || 'Argument availability was not recorded; inspect the research artifacts.';
}

function labeledStep(number: number, title: string): string {
  return `${number}. ${title.replace(/^\s*\d+[.)]\s+/, '').trim()}`;
}

function researchOutcomeMarkdown(session: ResearchSession): string {
  const outcome = session.outcome;
  const lines = [outcome.summary || 'No outcome summary was recorded.'];
  if (outcome.basis_artifact_ids?.length) lines.push('', `**Outcome evidence:** ${outcomeArtifactReferences(outcome.basis_artifact_ids, session)}`);
  const review = outcome.solution_review;
  if (review) {
    lines.push('', '### Solution review', '', `**Investigated:** ${session.problem || 'Project objective unavailable in this historical record.'}`, '', `**Bounded strategy:** ${session.strategy_text || session.strategy_title || 'Strategy details unavailable.'}`, '', `**Solution claim:** ${review.claim || 'No solution claim recorded.'}`, '', `**Argument:** ${review.argument_summary || 'No argument summary recorded.'}`, '', `**Skeptic response:** ${review.skeptic_response || 'No substantive Skeptic response recorded.'}`, '', `**Assumptions:** ${review.assumptions?.join(' · ') || 'None recorded'}`, '', `**Proof obligations considered:** ${review.proof_obligations?.join(' · ') || 'None recorded'}`, '', `**Still open:** ${review.open_obligations?.join(' · ') || 'None recorded'}`, '', `**Evidence:** ${outcomeArtifactReferences(review.basis_artifact_ids, session)}`);
    if (review.argument_steps?.length) lines.push('', '### Reviewed reasoning', '', ...review.argument_steps.flatMap(step => [`#### ${labeledStep(step.number, step.title)}`, '', `**Kind:** ${step.epistemic_status}`, '', step.argument, '', `**Skeptic review:** ${step.review?.disposition || 'Not recorded'} — ${step.review?.rationale || 'No rationale recorded'}`, ...(step.review?.objection ? ['', `**Objection:** ${step.review.objection}`] : []), '', `**Sources:** ${outcomeArtifactReferences([...(step.basis_artifact_ids || []), ...(step.research_artifact_id ? [step.research_artifact_id] : [])], session)}`, '']));
    else lines.push('', '### Reviewed reasoning', '', outcomeArgumentLabel(outcome));
    if ((review.strategy_findings?.length ?? 0) > 0) lines.push('', '### Findings by strategy', '', ...review.strategy_findings!.flatMap(item => [`#### ${item.strategy_title} · ${item.status}`, '', item.claim, ...(item.execution_status ? ['', `**Execution status:** ${item.execution_status}`] : []), ...(item.failure_reason ? [`**Failure detail:** ${item.failure_reason}`] : []), '', ...item.reasoning_steps.flatMap(step => [`**${labeledStep(step.number, step.title)} (${step.epistemic_status}):** ${step.argument}`, `**Review:** ${step.review?.disposition || 'Not recorded'} — ${step.review?.rationale || item.skeptic_response}`, '']), ...(item.objections.length ? [`**Objections:** ${item.objections.join(' · ')}`] : []), ...(item.open_obligations.length ? [`**Open obligations:** ${item.open_obligations.join(' · ')}`] : []), `**Sources:** ${outcomeArtifactReferences(item.research_artifact_ids?.length ? item.research_artifact_ids : (item.research_artifact_id ? [item.research_artifact_id] : []), session)}`, '']));
    if (review.unresolved_objections?.length) lines.push('', '### Unresolved objections', '', ...review.unresolved_objections.map(item => `- ${item}`));
    if (review.resolved_objections?.length) lines.push('', '### Objections addressed', '', ...review.resolved_objections.map(item => `- ${item}`));
    if (review.resolved_objections?.length) lines.push('', `**Resolved review notes:** ${review.resolved_objections.join(' · ')}`);
    if (review.unresolved_objections?.length) lines.push('', `**Unresolved objections:** ${review.unresolved_objections.join(' · ')}`);
    lines.push('', `**Verification:** ${outcomeVerificationLabel(outcome)}`);
  }
  if (outcome.caveats?.length) lines.push('', '### Caveats', '', ...outcome.caveats.map(caveat => `- ${caveat}`));
  return lines.join('\n');
}

function containsMathNotation(text: string): boolean {
  return /\\\[|\\\(|\$\$?[^$\n]+\$/.test(text)
    || /[\p{Script=Greek}A-Za-z][\p{L}\p{N}]*(?:\([^()\s]+\))?\s*[\^_]\s*\{?[+\-]?[\p{L}\p{N}]+\}?/u.test(text)
    || text.split('\n').some(line => {
    const expression = line.trim();
    return expression.length > 0 && expression.length <= 240
      && !/\s|[`$\\]/u.test(expression)
      && (/[\p{Script=Greek}∫∑√≤≥≠≈∞±×÷^_]/u.test(expression)
        || (/[=<>≤≥≠]/u.test(expression) && /[\d()[\]]/u.test(expression)))
      && /[=+*/^_∫∑√≤≥≠≈]/u.test(expression);
  });
}

function simpleOutcomeLead(session: ResearchSession): string {
  const saved = (session.outcome.conclusion || session.outcome.summary || 'No outcome summary was recorded.').trim();
  const firstSection = session.outcome.conclusion ? saved.split(/\n(?=#{2,6}\s)/, 2)[0] : saved;
  const lead = firstSection.replace(/^#{2,6}\s+[^\n]+\n+/, '').trim() || session.outcome.summary || saved;
  if (lead.length <= 900) return lead;
  const boundary = lead.lastIndexOf(' ', 900);
  return `${lead.slice(0, boundary >= 600 ? boundary : 900).trimEnd()}…`;
}

function researchReasoningMarkdown(session: ResearchSession): string {
  const review = session.outcome.solution_review;
  if (!review) return 'No structured reasoning or proof review is available for this session.';
  const lines = [
    '# Reasoning / proof', '',
    '## Investigated problem', '',
    session.problem || 'Project objective unavailable in this historical record.', '',
    '## Strategy', '',
    session.strategy_text || session.strategy_title || 'Strategy details unavailable.', '',
    '## Claim', '',
    review.claim || 'No claim recorded.', '',
    '## Argument summary', '',
    review.argument_summary || 'No argument summary recorded.', '',
    '## Skeptic response', '',
    review.skeptic_response || 'No substantive Skeptic response recorded.', '',
    '## Skeptic objections', '',
    ...(review.skeptic_objections?.length ? review.skeptic_objections.map(item => `- ${item}`) : ['None recorded']), '',
    '## Assumptions', '',
    ...(review.assumptions?.length ? review.assumptions.map(item => `- ${item}`) : ['None recorded']), '',
    '## Proof obligations', '',
    ...(review.proof_obligations?.length ? review.proof_obligations.map(item => `- ${item}`) : ['None recorded']), '',
    '## Open obligations', '',
    ...(review.open_obligations?.length ? review.open_obligations.map(item => `- ${item}`) : ['None recorded']), '',
    '## Unresolved objections', '',
    ...(review.unresolved_objections?.length ? review.unresolved_objections.map(item => `- ${item}`) : ['None recorded']), '',
    '## Resolved objections', '',
    ...(review.resolved_objections?.length ? review.resolved_objections.map(item => `- ${item}`) : ['None recorded']), '',
    '## Reviewed reasoning steps', '',
    ...(review.argument_steps?.length ? review.argument_steps.flatMap(step => [
      `### ${labeledStep(step.number, step.title)} · ${step.epistemic_status}`, '', step.argument, '',
      `**Skeptic review:** ${step.review?.disposition || 'Not recorded'} — ${step.review?.rationale || 'No rationale recorded'}`,
      ...(step.review?.objection ? ['', `**Objection:** ${step.review.objection}`] : []),
      `**Sources:** ${outcomeArtifactReferences([...(step.basis_artifact_ids || []), ...(step.research_artifact_id ? [step.research_artifact_id] : [])], session)}`, '',
    ]) : ['No step-by-step argument was preserved.']),
  ];
  for (const finding of review.strategy_findings ?? []) {
    lines.push(`## ${finding.strategy_title} · ${finding.status}`, '', finding.claim, '',
      `**Execution status:** ${finding.execution_status || 'Not recorded'}`,
      ...(finding.failure_reason ? [`**Failure detail:** ${finding.failure_reason}`] : []), '',
      ...(finding.reasoning_steps.length ? finding.reasoning_steps.flatMap(step => [
        `### ${labeledStep(step.number, step.title)} · ${step.epistemic_status}`, '', step.argument, '',
        `**Review:** ${step.review?.disposition || 'Not recorded'} — ${step.review?.rationale || finding.skeptic_response || 'No rationale recorded'}`,
        ...(step.review?.objection ? ['', `**Objection:** ${step.review.objection}`] : []), '',
      ]) : ['No structured reasoning steps were preserved for this finding.', '']),
      ...(finding.objections.length ? ['**Objections:**', ...finding.objections.map(item => `- ${item}`), ''] : []),
      ...(finding.open_obligations.length ? ['**Open obligations:**', ...finding.open_obligations.map(item => `- ${item}`), ''] : []),
      `**Sources:** ${outcomeArtifactReferences(finding.research_artifact_ids?.length ? finding.research_artifact_ids : finding.research_artifact_id ? [finding.research_artifact_id] : [], session)}`, '');
  }
  return lines.join('\n');
}

function researchPositionLabel(session: ResearchSession, cycle: number | undefined): string {
  if (cycle === undefined || !Number.isInteger(cycle) || cycle < 1) {
    return session.scheduler_version === 2 ? 'Round/turn not recorded' : 'Round unavailable';
  }
  if (session.scheduler_version !== 2) return `Round ${cycle}`;
  const perRound = Math.max(1, session.turns_per_round ?? 3);
  const slot = cycle - 1;
  return `Round ${Math.floor(slot / perRound) + 1} · Turn ${slot % perRound + 1} of ${perRound}`;
}

function researchArtifactPositionLabel(session: ResearchSession, artifact: ResearchArtifact): string {
  // In v2, artifact.sequence is a saved-artifact ordinal, not a paired-turn slot.
  const cycle = session.scheduler_version === 2
    ? artifact.strategy_cycle
    : (artifact.strategy_cycle ?? artifact.sequence);
  return researchPositionLabel(session, cycle);
}

function researchArtifactMarkdown(artifact: ResearchArtifact, session: ResearchSession): string {
  const lines = [
    `# ${researchArtifactPositionLabel(session, artifact)}: ${artifact.claim_or_question}`,
    '',
    `**Evidence status:** ${artifact.evidence_status}`,
    '',
    '## Method',
    '',
    artifact.method,
    '',
    '## Assumptions',
    '',
    ...(artifact.assumptions.length ? artifact.assumptions.map(item => `- ${item}`) : ['None stated']),
    '',
    '## Skeptic response',
    '',
    artifact.skeptic_response,
    '',
    '## Objections',
    '',
    ...(artifact.objections.length ? artifact.objections.map(item => `- ${item}`) : ['No concrete objection recorded']),
    '',
    '## Open obligations',
    '',
    ...(artifact.open_obligations.length ? artifact.open_obligations.map(item => `- ${item}`) : ['None recorded']),
    '',
    '## Coordinator decision',
    '',
    artifact.coordinator_decision,
    '',
    '## Next question',
    '',
    artifact.next_question || 'No further question; the session ended.',
    '',
    '## Full validated role outputs',
    '',
    '### Investigator',
    '',
    ...Object.entries(artifact.investigator_output).map(([key, value]) => `- **${key.replaceAll('_', ' ')}:** ${Array.isArray(value) ? value.join(' · ') : String(value)}`),
    '',
    '### Skeptic',
    '',
    ...Object.entries(artifact.skeptic_output).map(([key, value]) => `- **${key.replaceAll('_', ' ')}:** ${Array.isArray(value) ? value.join(' · ') : String(value)}`),
    '',
    `**Note:** ${artifact.note}`,
  ];
  return lines.join('\n');
}
const MAX_SESSION_DURATION_MINUTES = 7 * 24 * 60;
const durationUnitMinutes: Record<Exclude<DurationUnit, 'unlimited'>, number> = { minutes: 1, hours: 60, days: 1440 };
const limitBounds = {
  research_rounds: [1, 60], turns_per_round: [1, 20], output_tokens_per_call: [256, 20000],
} as const;
function draftLimits(value: ResearchLimits): ResearchLimitsDraft {
  const minutes = value.session_duration_minutes;
  const unit: DurationUnit = minutes === null ? 'unlimited' : minutes >= 1440 && minutes % 1440 === 0 ? 'days' : minutes >= 60 && minutes % 60 === 0 ? 'hours' : 'minutes';
  const duration = minutes === null ? '' : String(minutes / durationUnitMinutes[unit as Exclude<DurationUnit, 'unlimited'>]);
  return { research_rounds: String(value.research_rounds), turns_per_round: String(value.turns_per_round ?? 3), session_duration_value: duration, session_duration_unit: unit, output_tokens_per_call: String(value.output_tokens_per_call), maximum_estimated_cost_usd: value.maximum_estimated_cost_usd === null ? '' : String(value.maximum_estimated_cost_usd), maximum_input_tokens_per_session: value.maximum_input_tokens_per_session === null || value.maximum_input_tokens_per_session === undefined ? '' : String(value.maximum_input_tokens_per_session), max_concurrent_sessions: String(value.max_concurrent_sessions ?? '1') };
}
function validateLimitDraft(draft: ResearchLimitsDraft, requireSponsoredCost = false): { value: ResearchLimits | null; errors: Partial<Record<keyof ResearchLimitsDraft, string>> } {
  const errors: Partial<Record<keyof ResearchLimitsDraft, string>> = {};
  const value = {} as ResearchLimits;
  for (const key of Object.keys(limitBounds) as Array<keyof typeof limitBounds>) {
    const input = draft[key];
    const [minimum, maximum] = limitBounds[key];
    if (!/^\d+$/.test(input)) { errors[key] = 'Enter a whole number.'; continue; }
    const number = Number(input);
    if (!Number.isSafeInteger(number) || number < minimum || number > maximum) {
      errors[key] = `Enter a whole number from ${minimum} to ${maximum}.`; continue;
    }
    value[key] = number;
  }
  if (draft.session_duration_unit === 'unlimited') {
    value.session_duration_minutes = null;
  } else if (!/^\d+$/.test(draft.session_duration_value)) {
    errors.session_duration_value = 'Enter a whole number.';
  } else {
    const enteredDuration = Number(draft.session_duration_value);
    const durationMinutes = enteredDuration * durationUnitMinutes[draft.session_duration_unit];
    if (!Number.isSafeInteger(enteredDuration) || !Number.isSafeInteger(durationMinutes) || durationMinutes < 1 || durationMinutes > MAX_SESSION_DURATION_MINUTES) {
      errors.session_duration_value = 'Enter a duration from 1 minute to 7 days.';
    } else value.session_duration_minutes = durationMinutes;
  }
  const rawCost = draft.maximum_estimated_cost_usd.trim();
  const costText = rawCost.startsWith('$') ? rawCost.slice(1) : rawCost;
  if (costText === '' && requireSponsoredCost) errors.maximum_estimated_cost_usd = 'Set a maximum estimated session cost before saving limits for sponsored research.';
  else if (costText === '') value.maximum_estimated_cost_usd = null;
  else if (!/^(?:\d+(?:\.\d{1,2})?|\.\d{1,2})$/.test(costText)) {
    errors.maximum_estimated_cost_usd = 'Enter a USD amount from $0.01 to $100.00, or leave blank for unlimited.';
  } else {
    const cost = Number(costText);
    if (!Number.isFinite(cost) || cost < 0.01 || cost > 100) errors.maximum_estimated_cost_usd = 'Enter a USD amount from $0.01 to $100.00, or leave blank for unlimited.';
    else value.maximum_estimated_cost_usd = Math.round(cost * 100) / 100;
  }
  if (draft.maximum_input_tokens_per_session === '') value.maximum_input_tokens_per_session = null;
  else if (!/^\d+$/.test(draft.maximum_input_tokens_per_session)) errors.maximum_input_tokens_per_session = 'Enter a whole number or leave blank for unlimited.';
  else {
    const inputTokens = Number(draft.maximum_input_tokens_per_session);
    if (!Number.isSafeInteger(inputTokens) || inputTokens < 4096 || inputTokens > 1_000_000) errors.maximum_input_tokens_per_session = 'Enter 4,096 to 1,000,000 tokens, or leave blank for unlimited.';
    else value.maximum_input_tokens_per_session = inputTokens;
  }
  if (!/^[1-4]$/.test(draft.max_concurrent_sessions)) {
    errors.max_concurrent_sessions = 'Enter a whole number from 1 to 4.';
  } else value.max_concurrent_sessions = draft.max_concurrent_sessions;
  if (value.maximum_input_tokens_per_session !== null && value.maximum_input_tokens_per_session !== undefined && value.maximum_estimated_cost_usd === null) errors.maximum_input_tokens_per_session = 'Set a maximum estimated cost when using an input-token cap.';
  value.scheduler_version = 2;
  if (!errors.research_rounds && !errors.turns_per_round) {
    value.model_calls = value.research_rounds * value.turns_per_round * 2;
  }
  return { value: Object.keys(errors).length ? null : value, errors };
}

function displayStrategyTitle(strategy: Strategy | undefined): string {
  if (!strategy) return 'Strategy';
  if (typeof strategy.title === 'string' && strategy.title.trim()) return strategy.title;
  const firstLine = typeof strategy.approach === 'string' ? strategy.approach.split(/\r?\n/, 1)[0].trim() : '';
  return firstLine ? `${firstLine.slice(0, 72)}${firstLine.length > 72 ? '…' : ''}` : 'Untitled strategy';
}

type ProcessControls = { play: () => void; stop: () => void; playDisabled: boolean; stopDisabled: boolean; playLabel: string; confirming?: boolean; starting?: boolean; start?: () => void; cancel?: () => void; nextSessionNumber?: number; confirmationSummary?: string };

type SessionRenderBoundaryProps = { sessionId: string; sessionNumber: number; revision?: string; children: ReactNode; fallback?: ReactNode };
type SessionRenderBoundaryState = { error: Error | null };

/** A single corrupt historical record must not take down the project workspace. */
class SessionRenderBoundary extends Component<SessionRenderBoundaryProps, SessionRenderBoundaryState> {
  state: SessionRenderBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): SessionRenderBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unable to render saved research session', {
      sessionId: this.props.sessionId,
      sessionNumber: this.props.sessionNumber,
      error,
      componentStack: info.componentStack,
    });
  }

  componentDidUpdate(previous: SessionRenderBoundaryProps) {
    if ((previous.sessionId !== this.props.sessionId || previous.revision !== this.props.revision) && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) return this.props.fallback ?? <li className="session-row session-render-error" data-session-id={this.props.sessionId}>
      <p role="alert"><strong>Session {this.props.sessionNumber} could not be displayed.</strong> Its record remains available in the project export.</p>
    </li>;
    return this.props.children;
  }
}

function DisclosureChevron({ expanded }: { expanded: boolean }) {
  return <svg aria-hidden="true" className={`disclosure-chevron${expanded ? ' is-expanded' : ''}`} viewBox="0 0 12 12"><path d="m4 2 4 4-4 4"/></svg>;
}

function ContextManifestNotes({ manifest }: { manifest: ContextManifest }) {
  const notes = [
    manifest.omitted_peer_evidence?.count ? {
      key: 'peer',
      text: `${manifest.omitted_peer_evidence.count} peer artifacts omitted; source IDs: ${manifest.omitted_peer_evidence.artifact_ids.join(', ') || 'bounded pointer list unavailable'}. ${manifest.omitted_peer_evidence.reason}`,
    } : null,
    manifest.omitted_project_strategies?.count ? {
      key: 'strategies',
      text: `${manifest.omitted_project_strategies.count} project strategies omitted; source IDs: ${manifest.omitted_project_strategies.strategy_ids.join(', ') || 'bounded pointer list unavailable'}. ${manifest.omitted_project_strategies.reason}`,
    } : null,
    manifest.omitted_obligations?.count ? {
      key: 'obligations',
      text: `${manifest.omitted_obligations.count} lower-priority obligation details omitted; IDs: ${manifest.omitted_obligations.obligation_ids.join(', ') || 'bounded pointer list unavailable'}. ${manifest.omitted_obligations.reason}`,
    } : null,
  ].filter((item): item is { key: string; text: string } => item !== null);
  if (!notes.length) return null;
  return <ul className="context-omission-notes">{notes.map(item => <li key={item.key}>{item.text}</li>)}</ul>;
}

type OutcomeMarkdownSection = 'conclusion' | 'reasoning' | 'citations' | 'assessments';
type OutcomeMarkdownBlock = { field: string; source: string; section: OutcomeMarkdownSection };
type FormattedOutcomeBlock = { source: string; body: string };

function outcomeTextBlocks(session: ResearchSession): OutcomeMarkdownBlock[] {
  const blocks: OutcomeMarkdownBlock[] = [];
  const add = (section: OutcomeMarkdownSection, field: string, source?: string) => {
    if (source?.trim()) blocks.push({ section, field, source });
  };
  add('conclusion', session.outcome.conclusion ? 'outcome.conclusion' : 'outcome.summary',
    session.outcome.conclusion || session.outcome.summary);
  const review = session.outcome.solution_review;
  if (review) {
    for (const field of ['claim', 'argument_summary', 'skeptic_response'] as const)
      add('reasoning', 'outcome.solution_review.' + field, review[field]);
    review.argument_steps?.forEach((step, index) =>
      add('reasoning', `outcome.solution_review.argument_steps.${index}.argument`, step.argument));
    review.strategy_findings?.forEach((finding, index) => {
      add('reasoning', `outcome.solution_review.strategy_findings.${index}.claim`, finding.claim);
      finding.reasoning_steps.forEach((step, stepIndex) =>
        add('reasoning', `outcome.solution_review.strategy_findings.${index}.reasoning_steps.${stepIndex}.argument`, step.argument));
    });
  }
  session.artifacts.forEach((artifact, index) => {
    for (const field of ['claim_or_question', 'method', 'skeptic_response', 'coordinator_decision', 'next_question'] as const)
      add('citations', `artifacts.${index}.${field}`, artifact[field]);
  });
  session.strategy_assessments?.forEach((assessment, index) =>
    add('assessments', `strategy_assessments.${index}.rationale`, assessment.rationale));
  return blocks;
}

function formattedOutcomeSession(
  session: ResearchSession,
  selected: ReadonlySet<OutcomeMarkdownSection>,
  blocks: Record<string, FormattedOutcomeBlock>,
): ResearchSession {
  const resolve = (section: OutcomeMarkdownSection, field: string, text: string) =>
    selected.has(section) && blocks[field]?.source === text ? blocks[field].body : text;
  const review = session.outcome.solution_review;
  const newReview = review ? {
    ...review,
    claim: resolve('reasoning', 'outcome.solution_review.claim', review.claim || ''),
    argument_summary: resolve('reasoning', 'outcome.solution_review.argument_summary', review.argument_summary || ''),
    skeptic_response: resolve('reasoning', 'outcome.solution_review.skeptic_response', review.skeptic_response || ''),
    argument_steps: review.argument_steps?.map((step, index) => ({
      ...step, argument: resolve('reasoning', `outcome.solution_review.argument_steps.${index}.argument`, step.argument),
    })),
    strategy_findings: review.strategy_findings?.map((finding, index) => ({
      ...finding,
      claim: resolve('reasoning', `outcome.solution_review.strategy_findings.${index}.claim`, finding.claim),
      reasoning_steps: finding.reasoning_steps.map((step, stepIndex) => ({
        ...step, argument: resolve('reasoning', `outcome.solution_review.strategy_findings.${index}.reasoning_steps.${stepIndex}.argument`, step.argument),
      })),
    })),
  } : review;
  return {
    ...session,
    outcome: {
      ...session.outcome,
      conclusion: resolve('conclusion', 'outcome.conclusion', session.outcome.conclusion || ''),
      summary: resolve('conclusion', 'outcome.summary', session.outcome.summary || ''),
      solution_review: newReview,
    },
    artifacts: session.artifacts.map((artifact, index) => ({
      ...artifact,
      claim_or_question: resolve('citations', `artifacts.${index}.claim_or_question`, artifact.claim_or_question),
      method: resolve('citations', `artifacts.${index}.method`, artifact.method),
      skeptic_response: resolve('citations', `artifacts.${index}.skeptic_response`, artifact.skeptic_response),
      coordinator_decision: resolve('citations', `artifacts.${index}.coordinator_decision`, artifact.coordinator_decision),
      next_question: resolve('citations', `artifacts.${index}.next_question`, artifact.next_question),
    })),
    strategy_assessments: session.strategy_assessments?.map((assessment, index) => ({
      ...assessment,
      rationale: resolve('assessments', `strategy_assessments.${index}.rationale`, assessment.rationale),
    })),
  };
}

// Local presentation preference only; the session and research evidence are immutable.
// Include the current lifecycle and reason so a materially different stop reappears.
function sessionNoticeKey(session: ResearchSession): string {
  const source = [
    session.id, session.status, session.termination_reason_code ?? '',
    session.message ?? '', session.next_step_guidance ?? '', session.calls_used,
  ].join('|');
  let hash = 2166136261;
  for (let i = 0; i < source.length; i++) {
    hash = Math.imul(hash ^ source.charCodeAt(i), 16777619);
  }
  return `${session.id}:${(hash >>> 0).toString(16)}`;
}

function SessionNoticeDismiss({ number, onDismiss, label }: { number: number; onDismiss: () => void; label?: string }) {
  return <button type="button" className="session-notice-dismiss" aria-label={label ?? `Dismiss notices for Session ${number}`}
    data-tooltip={label ?? `Dismiss Session ${number} notices`} onClick={onDismiss}><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" aria-hidden="true"><path d="M8 8 16 16M16 8 8 16"/></svg></button>;
}

// An in-flow exit slot: the notice slides through its own bottom edge
// as that slot collapses, instead of flying toward the viewport footer.
// Dismissal is a presentation-only operation; saved research is unchanged.
function SessionNotice({ number, onDismiss, title, kind, ariaLabel, dismissLabel, children }: {
  number: number; onDismiss: () => void; title: string; kind: string; ariaLabel: string; dismissLabel?: string; children: ReactNode;
}) {
  const [exiting, setExiting] = useState(false);
  const timer = useRef<number | null>(null);
  useEffect(() => () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
  }, []);
  const dismiss = () => {
    if (timer.current !== null) return;
    setExiting(true);
    timer.current = window.setTimeout(onDismiss, 600);
  };
  return <div className={`session-notice-exit-slot${exiting ? ' is-exiting' : ''}`}>
    <div className="session-notice-exit-inner">
      <div className={kind} role={kind.includes('paper-contextual-error') ? 'alert' : kind === 'stopped-session-guidance' ? 'note' : 'complementary'} aria-label={ariaLabel}>
        <div className="session-notice-header">
          <strong className="session-notice-title">{title}</strong>
          {kind.includes('paper-contextual-error')
            ? <DialogDismissButton label={dismissLabel ?? 'Dismiss paper error'} onClick={dismiss}/>
            : <SessionNoticeDismiss number={number} onDismiss={dismiss} label={dismissLabel}/>}
        </div>
        {children}
      </div>
    </div>
  </div>;
}

function ProviderInputAuditDisclosure({ audit }: { audit: NonNullable<ResearchStep['provider_input_audit']> }) {
  const [open, setOpen] = useState(false);
  return <details className="context-used-disclosure" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Exact provider input · {audit.status}</summary>
    {open && <>
      <p>Request body recorded before dispatch; authorization headers and credentials are excluded.</p>
      <h5>Role instructions</h5>
      <pre>{String(audit.request_body.instructions ?? '')}</pre>
      <h5>Submitted input</h5>
      <pre>{JSON.stringify(audit.request_body.input, null, 2)}</pre>
    </>}
  </details>;
}

function ResearchSessionContents({ path, session, expanded, busy, guest, advancedOutcomeDetails, onEnableAdvancedOutcome, onViewStrategy, onViewPriorSession, onForkFromFindings, onInterventionSaved, dismissedStatusNotice, onDismissStatusNotice }: {
  path: string;
  session: ResearchSession; advancedOutcomeDetails: boolean; expanded: boolean; busy: boolean; guest: boolean;
  onEnableAdvancedOutcome: () => Promise<void>;
  onViewStrategy: (id: string) => void;
  onViewPriorSession: (id: string) => void;
  onForkFromFindings: (session: ResearchSession) => void;
  onInterventionSaved: (sessionId: string) => Promise<void>;
  dismissedStatusNotice: boolean; onDismissStatusNotice: () => void;
}) {
  const cloud = useCloudIdentity();
  const usageCopy = providerUsageLimitCopy(
    session.cloud_sponsored === true || cloud?.funding.selectedConnection === 'sponsored' || cloud?.target === 'hosted',
    session.mode === 'chatgpt',
  );
  const usageSponsored = session.cloud_sponsored === true || cloud?.funding.selectedConnection === 'sponsored' || cloud?.target === 'hosted';
  const [markdownSections, setMarkdownSections] = useState<OutcomeMarkdownSection[]>(() =>
    containsMathNotation(session.outcome.conclusion || '') ? ['conclusion'] : []);
  const [convertedBlocks, setConvertedBlocks] = useState<Record<string, FormattedOutcomeBlock>>({});
  const convertedBlocksRef = useRef<Record<string, FormattedOutcomeBlock>>({});
  const [conversionError, setConversionError] = useState('');
  const [conversionProgress, setConversionProgress] = useState('');
  const conversionQueue = useRef<OutcomeMarkdownBlock[]>([]);
  const conversionWorker = useRef(false);
  const conversionCurrent = useRef<OutcomeMarkdownBlock | null>(null);
  const conversionAbort = useRef<AbortController | null>(null);
  const completedConversions = useRef(0);
  const totalConversions = useRef(0);
  const [advancedOutcomeEnableError, setAdvancedOutcomeEnableError] = useState('');
  const [enablingAdvancedOutcome, setEnablingAdvancedOutcome] = useState(false);
  const blocks = useMemo(() => outcomeTextBlocks(session), [session]);
  const activeSections = useMemo(() => new Set(markdownSections), [markdownSections]);
  const renderSession = useMemo(() =>
    formattedOutcomeSession(session, activeSections, convertedBlocks),
    [session, activeSections, convertedBlocks]);
  const [activityExpanded, setActivityExpanded] = useState(session.status === 'queued' || session.status === 'running');
  const [interventionKind, setInterventionKind] = useState<ResearchIntervention['kind']>('priority');
  const [interventionText, setInterventionText] = useState('');
  const [interventionStrategy, setInterventionStrategy] = useState('*');
  const [targetAgentRole, setTargetAgentRole] = useState<'investigator' | 'skeptic'>('investigator');
  const [interventionBusy, setInterventionBusy] = useState(false);
  const [interventionError, setInterventionError] = useState('');
  useEffect(() => {
    setActivityExpanded(session.status === 'queued' || session.status === 'running');
  }, [session.status]);
  useEffect(() => () => {
    conversionQueue.current = [];
    conversionAbort.current?.abort();
  }, [session.id]);
  const lastActivity = session.events.at(-1);
  const lastStep = session.steps.at(-1);
  const approvedPackets = Object.values(session.approved_continuations ?? {});
  const approvedSourceIds = new Set(approvedPackets.flatMap(packet => packet.sources.map(source => source.artifact_id)));
  const otherPriorFindings = (session.prior_session_findings ?? []).filter(finding => !approvedSourceIds.has(finding.id));
  const review = session.outcome.solution_review;
  const primaryEvidenceIds = [...new Set([...(session.outcome.basis_artifact_ids ?? []), ...(review?.basis_artifact_ids ?? [])])];
  const hasEvidence = session.artifacts.length > 0 || primaryEvidenceIds.length > 0;
  const historicalSummary = !session.outcome.conclusion && !['queued', 'running', 'paused'].includes(session.status);
  const resultLabel = session.provider_usage_limited && ['paused', 'stopped', 'ended', 'failed'].includes(session.status)
    ? 'Research so far · incomplete'
    : session.outcome.conclusion ? 'Conclusion' : historicalSummary ? 'Historical session summary' : 'Session summary';
  const resultText = renderSession.outcome.conclusion || renderSession.outcome.summary || 'No outcome summary was recorded.';
  const simpleResult = simpleOutcomeLead(renderSession);
  const simpleOutcomeMarkdown = activeSections.has('conclusion');
  const verificationLabel = review?.verification_status === 'verified' ? 'Verified in the session record' : review?.verification_status === 'convincing_unverified' ? 'Convincing but unverified' : review?.verification_status === 'incomplete' ? 'Evidence incomplete' : 'Not independently verified';
  const qualificationItems = [...new Set([...(review?.open_obligations ?? []), ...(review?.unresolved_objections ?? []), ...(session.outcome.caveats ?? [])])];
  const simpleQualifications = session.outcome.conclusion ? qualificationItems.slice(0, 3) : qualificationItems;
  const provenance = session.outcome.execution_provenance;
  const runMetrics = session.outcome.metrics?.operational ?? [];
  const budgetDenied = session.steps.some(step => step.failure_kind === 'budget_denied');
  const budgetReason = session.strategy_runs?.find(branch =>
    /allowance|inference[- ]spend|cost reserve|cost limit|global spend|token budget|capacity|funding/i.test(branch.reason ?? '')
  )?.reason;
  const compilation = session.outcome.source_material?.compilation;
  const compilerAttempted = !!compilation?.started_at;
  const budgetNotice = budgetDenied
    ? session.calls_used === 0
      ? compilerAttempted
        ? 'No Investigator or Skeptic call was made. Reference compilation may have consumed AI usage; see Research Standards for its status.'
        : 'No Investigator or Skeptic call was dispatched. Check the funding denial below.'
      : 'Research stopped because another provider call could not be funded. Findings are preserved.'
    : '';
  const independentFailure = session.steps.some(step => step.status === 'failed'
    && !!step.failure_kind && !['provider_limited', 'provider_rate_limited'].includes(step.failure_kind));
  const accountUsageLimited = session.provider_usage_limited === true
    && ['failed', 'ended', 'paused', 'stopped'].includes(session.status);
  // Display one primary stop cause; leave per-strategy failures in the Session Log.
  // This also corrects historical sessions whose saved message used legacy v1
  // cycle terminology despite running under the v2 scheduler.
  const usageLimitStopMessage = usageCopy.description;
  const usageLimitImpact = `${session.protocol_completed_calls ?? 0} of ${session.protocol_target_calls ?? session.call_limit} research calls completed; ${session.artifacts.length} findings recorded.`;
  const separateFailureNote = independentFailure
    ? 'Other earlier research failures are recorded separately in the Session Log.'
    : '';
  const statusHeading = accountUsageLimited ? usageCopy.title : budgetDenied
    ? session.calls_used === 0 ? 'Insufficient research funds' : 'Research funding limit reached'
    : session.status === 'paused' ? 'Paused'
      : session.status === 'stopped' ? 'Stopped'
        : session.status === 'failed' ? 'Error' : 'Ended';
  const statusNextStep = accountUsageLimited
    ? (usageSponsored ? 'Try Resume again in a few hours.' : usageCopy.next)
    : session.next_step_guidance
    || (session.termination_reason_code === 'research_completed_early' ? 'Review the findings and rationale; the configured turn count was an upper limit, not a target.'
      : budgetDenied ? 'Review the available research allowance before starting another session.'
        : 'Review activity and provider usage before resuming. Resuming may start new provider work and can consume allowance or incur charges.');
  const zeroPythonRuns = runMetrics.some(item => item.label === 'Python runs by status' && item.value === '0 executions');
  const zeroSageRuns = runMetrics.some(item => item.label === 'SageMath runs by status' && item.value === '0 executions');
  const noSavedLocalComputations = (provenance && provenance.records.length === 0 && provenance.unidentified_count === 0)
    || (!provenance && zeroPythonRuns && zeroSageRuns);
  const showComputationProvenance = session.investigation_type !== 'literature'
    || !!provenance?.records.length || !!provenance?.unidentified_count;
  const provenancePrelude = <div className="outcome-evidence-prelude" aria-label="Recorded computation provenance">
    <strong>Recorded computations:</strong> {provenance
      ? `${provenance.completed_count} reported completed of ${provenance.records.length} identified execution${provenance.records.length === 1 ? '' : 's'}${provenance.unidentified_count ? ` · ${provenance.unidentified_count} missing IDs` : ''}`
      : 'Provenance projection unavailable for this historical Outcome.'}
    {noSavedLocalComputations && <p role="status"><strong>Evidence limitation:</strong> No local Python or Sage computation is recorded for this session. Computational claims in the agent-authored conclusion are not supported by recorded local execution evidence.</p>}
    {provenance && <p>{provenance.note}</p>}{!!provenance?.completed_without_recorded_io_count && <p>Warning: {provenance.completed_without_recorded_io_count} completed-status record(s) do not include recorded source and output.</p>}
    {!!provenance?.records.length && <details><summary>Execution IDs and statuses</summary><ul>{provenance.records.map(row => <li key={`${row.runtime}:${row.id}`}><strong>{row.runtime} · {row.id}</strong> · {row.statuses.join(' / ')} · {row.artifact_ids.length ? `artifacts ${row.artifact_ids.join(', ')}` : row.step_ids.length ? `steps ${row.step_ids.join(', ')}` : 'owner not recorded'} · source {row.source_recorded ? 'recorded' : 'unavailable'}, output {row.output_recorded ? 'recorded' : 'unavailable'}</li>)}</ul></details>}
  </div>;
  const metricSources = session.outcome.metrics?.sources;
  const artifactNumber = (id: string) => session.artifacts.find(artifact => artifact.id === id)?.sequence;
  const idList = (ids: string[] | undefined) => ids?.length ? ids.map(id => `Artifact ${artifactNumber(id) ?? '?'} · ${id}`).join(', ') : 'None recorded';
  const targetStrategies = session.strategy_runs ?? [{ strategy_id: session.strategy_id, strategy_title: session.strategy_title }];
  const supportsIntervention = !!session.strategy_runs?.length;
  const interventionCount = session.interventions ?? [];
  const interventionWindowOpen = ['queued', 'running', 'paused', 'stopped'].includes(session.status);
  const canIntervene = !guest && supportsIntervention && interventionWindowOpen
    && interventionCount.filter(item => item.status !== 'rejected').length < 24
    && interventionCount.length < 32;
  async function submitIntervention(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const agentRoles = [targetAgentRole];
    if (!interventionText.trim()) return;
    setInterventionBusy(true); setInterventionError('');
    try {
      await post<ResearchSession>(`research-sessions/${session.id}/interventions`, {
        path,
        kind: interventionKind,
        text: interventionText,
        strategy_ids: interventionStrategy === '*' ? targetStrategies.map(item => item.strategy_id) : [interventionStrategy],
        agent_roles: agentRoles,
      });
      setInterventionText('');
      await onInterventionSaved(session.id);
    } catch (cause) {
      setInterventionError(errorMessage(cause));
      reportRequestFailure(errorMessage(cause));
    } finally { setInterventionBusy(false); }
  }
  async function drainConversions() {
    if (conversionWorker.current) return;
    conversionWorker.current = true;
    try {
      while (conversionQueue.current.length) {
        const block = conversionQueue.current.shift()!;
        conversionCurrent.current = block;
        const controller = new AbortController();
        conversionAbort.current = controller;
        setConversionProgress(`Formatting ${completedConversions.current + 1} of ${totalConversions.current} text blocks…`);
        let finishProviderRequest = () => {};
        try {
          const expectedDigest = await sha256Text(block.source);
          if (controller.signal.aborted) continue;
          // Hosted inference requires a current account binding. Obtain it for
          // each queued block; never silently reuse a different account.
          const settingsResponse = await fetch(
            `/api/projects/proposals/config?${new URLSearchParams({ path, purpose: "markdown" })}`,
            { signal: controller.signal },
          );
          const settings = await settingsResponse.json();
          if (!settingsResponse.ok || !settings.available) {
            throw new Error(settings.message ?? settings.error ?? 'Connect AI in the header, then retry.');
          }
          finishProviderRequest = beginProviderRequest('text-conversion');
          const converted = await post<{ body: string; source_digest: string; warnings: string[] }>(
            'text/convert',
            {
              path, scope: 'research-block', session_id: session.id, field_path: block.field,
              target: 'markdown', expected_digest: expectedDigest,
              expected_binding: settings.binding, expected_project_id: session.project_id,
            },
            controller.signal, true,
          );
          if (converted.source_digest !== expectedDigest)
            throw new Error('Research text changed while formatting. The original source is unchanged.');
          const next = { ...convertedBlocksRef.current, [block.field]: { source: block.source, body: converted.body } };
          convertedBlocksRef.current = next;
          setConvertedBlocks(next);
        } catch (cause) {
          if (!controller.signal.aborted) {
            setConversionError(`Markdown formatting paused: ${friendlyProviderError(errorMessage(cause))}. Research remains unchanged; Markdown rendering stays available.`);
            conversionQueue.current = [];
          }
        } finally {
          finishProviderRequest();
          completedConversions.current++;
          if (conversionAbort.current === controller) conversionAbort.current = null;
          conversionCurrent.current = null;
        }
      }
    } finally {
      conversionWorker.current = false;
      setConversionProgress('');
    }
  }
  function enqueueConversions(target: OutcomeMarkdownSection[]) {
    const candidates = blocks.filter(block => target.includes(block.section) && block.source.trim().length >= 40
      && block.source.length <= 20000 && convertedBlocksRef.current[block.field]?.source !== block.source
      && !conversionQueue.current.some(item => item.field === block.field && item.source === block.source));
    if (!candidates.length) return;
    if (!conversionWorker.current) { completedConversions.current = 0; totalConversions.current = 0; }
    totalConversions.current += candidates.length;
    conversionQueue.current.push(...candidates);
    setConversionError('');
    void drainConversions();
  }
  function toggleAllMarkdown() {
    const all: OutcomeMarkdownSection[] = ['conclusion', 'reasoning', 'citations', 'assessments'];
    if (all.every(section => activeSections.has(section))) {
      setMarkdownSections([]);
      conversionQueue.current = [];
      conversionAbort.current?.abort();
    } else {
      setMarkdownSections(all);
      if (!guest) enqueueConversions(all);
    }
  }
  const markdownSymbol = <MarkdownGlyph/>;
  const markdownButton = (label: string, active: boolean, onClick: () => void) =>
    <button type="button" className="sigma-render-toggle" aria-label={active ? `Show original ${label} text` : `Format ${label} as Markdown`}
      aria-pressed={active}
      data-tooltip={active ? `Show original ${label} text` : `Format ${label} as Markdown`}
      onClick={onClick}>{markdownSymbol}</button>;
  const outcomeFormatToggle = markdownButton('all research sections', (['conclusion', 'reasoning', 'citations', 'assessments'] as OutcomeMarkdownSection[]).every(section => activeSections.has(section)), toggleAllMarkdown);
  const renderMetricGroup = (title: string, items: OutcomeMetric[] | undefined) => <div className="outcome-metric-group">
    <h5>{title}</h5>
    {items?.length ? <dl>{items.map((item, index) => <div className="outcome-label-value" key={`${item.label}:${index}`}><dt>{item.label}</dt><dd><span>{item.value}</span>{item.detail && <small>{item.detail}</small>}</dd></div>)}</dl> : <p className="outcome-unavailable">No {title.toLowerCase()} metrics are available for this session.</p>}
  </div>;
  const researchReferences = (
      <details className="outcome-subsection outcome-source-material">
        <summary><DisclosureChevron expanded={false}/>Research Standards</summary>
        <div className="outcome-subsection-content">
          <p>Research standards selected before the Investigator/Skeptic turns. These describe how to investigate; they are not independent evidence for the research findings.</p>
          {session.outcome.source_material?.compilation && <div className="outcome-reference-compilation">
            <p><strong>Initial step · Compile research standards:</strong> {session.outcome.source_material.compilation.status === 'completed' ? 'Completed' : session.outcome.source_material.compilation.status === 'not_needed' ? 'No standards selected' : session.outcome.source_material.compilation.status === 'pending' ? 'Queued' : session.outcome.source_material.compilation.status === 'running' ? 'Running' : 'Unavailable; frozen standards notes retained'}</p>
            {session.outcome.source_material.compilation.guidance && <p>{session.outcome.source_material.compilation.guidance}</p>}
            {session.outcome.source_material.compilation.status === 'completed' && <small>{session.outcome.source_material.compilation.selected_source_ids?.length ?? 0} standards retained · {session.outcome.source_material.compilation.omitted_source_ids?.length ?? 0} omitted as low value or irrelevant. Original standards records preserved in this session.</small>}
            {['fallback', 'interrupted'].includes(session.outcome.source_material.compilation.status) && <p className="reference-compilation-degraded" role="alert"><strong>Compiled guidance unavailable.</strong> {session.outcome.source_material.compilation.reason ?? 'Original frozen standards notes were used instead.'}</p>}
            {session.outcome.source_material.compilation.reason && !['completed', 'fallback', 'interrupted'].includes(session.outcome.source_material.compilation.status) && <small>{session.outcome.source_material.compilation.reason}</small>}
            {!!session.outcome.source_material.compilation.attempts?.length && <div className="reference-compilation-diagnostics">
              <strong>Compiler attempts · {session.outcome.source_material.compilation.attempts?.length} of 3 maximum</strong>
              <ol>{session.outcome.source_material.compilation.attempts?.map((attempt, index) => <li key={index}>
                <span>Attempt {attempt.number}: {attempt.status}</span>
                {attempt.failure_type && <span> · failure {attempt.failure_type}</span>}
                {attempt.provider_http_status != null && <span> · provider HTTP {attempt.provider_http_status}</span>}
                {attempt.provider_error_code && <span> · code {attempt.provider_error_code}</span>}
                {attempt.provider_response_status && <span> · response {attempt.provider_response_status}</span>}
                {attempt.validation_failure && <span> · validation {attempt.validation_failure}</span>}
                <span> · usage {attempt.usage_status ?? 'unavailable'}{attempt.token_usage ? ` ({attempt.token_usage.input_tokens ?? '?'} input / {attempt.token_usage.output_tokens ?? '?'} output tokens)` : ''}</span>
                <span> · retry {attempt.retry_decision ?? 'none'}</span>
                {attempt.reason && <small>{attempt.reason}</small>}
              </li>)}</ol>
            </div>}
          </div>}
          {session.outcome.source_material?.sources?.length ? <>
            <p><strong>Selection:</strong> {session.outcome.source_material.status === 'reused' ? 'Reused from a previous session' : 'Selected for this session'} · {session.outcome.source_material.mode}{session.outcome.source_material.branch ? ` · ${session.outcome.source_material.branch}` : ''}</p>
            <ul>{session.outcome.source_material.sources.map(source => <li key={source.id}>
              <strong>{source.tier}:</strong> <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a>
              <p>{source.notes}</p>
            </li>)}</ul>
            {session.outcome.source_material.source_session_id && <small>Previous session: {session.outcome.source_material.source_session_id}</small>}
          </> : <p>No methodology source material was recorded for this session.</p>}
        </div>
      </details>
  );
  return <div id={`session-content-${session.id}`} className="session-row-content" hidden={!expanded}>
    <section className={`session-outcome outcome-${session.outcome.assessment}`} aria-label="Research outcome">
      <div className="outcome-heading"><div className="outcome-heading-title"><h3>Outcome</h3>{outcomeFormatToggle}<span className={`outcome-label outcome-${session.outcome.assessment}`}>{outcomeDisplayLabel(session)}</span></div></div>
      {conversionProgress && <p className="outcome-markdown-progress" role="status">{conversionProgress}</p>}
      {conversionError && <p className="outcome-conclusion-format-error" role="alert">{conversionError}</p>}
      {showComputationProvenance && provenancePrelude}
      {!dismissedStatusNotice && (budgetDenied || session.status === 'paused' || session.status === 'stopped' || session.status === 'failed' || !!session.next_step_guidance || !!session.termination_reason_code) && <SessionNotice number={session.session_number} onDismiss={onDismissStatusNotice} title={statusHeading} kind="research-pause-guidance" ariaLabel="Session status and next steps">
        {accountUsageLimited ? <><p>{usageLimitStopMessage}</p><p>{usageLimitImpact}</p>{separateFailureNote && <p>{separateFailureNote}</p>}</>
          : budgetDenied ? <><p>{budgetNotice}</p>{(session.message || budgetReason) && <p>{session.message || budgetReason}</p>}</>
          : !!session.message && <p>{session.message}</p>}
        <p>{statusNextStep}</p>
      </SessionNotice>}
      {!advancedOutcomeDetails && <div className="outcome-simple">
        <div className="outcome-summary-text"><div className="outcome-summary-title"><span className="outcome-summary-kicker">{resultLabel}</span></div>
          {simpleOutcomeMarkdown ? <div className="outcome-markdown"><Suspense fallback={<p>{simpleResult}</p>}><RenderedMarkdown body={simpleResult}/></Suspense></div> : <p>{simpleResult}</p>}
          <p className="advanced-outcome-hint">Want more detail? Turn on <button type="button" className="advanced-outcome-link" disabled={enablingAdvancedOutcome} onClick={async () => {
            setEnablingAdvancedOutcome(true); setAdvancedOutcomeEnableError('');
            try { await onEnableAdvancedOutcome(); }
            catch (cause) { setAdvancedOutcomeEnableError(errorMessage(cause)); }
            finally { setEnablingAdvancedOutcome(false); }
          }}>{enablingAdvancedOutcome ? 'Advanced Outcome…' : 'Advanced Outcome'}</button> to see the full research findings and evidence.</p>
          {advancedOutcomeEnableError && <p className="advanced-outcome-hint-error" role="alert">{advancedOutcomeEnableError}</p>}
          {primaryEvidenceIds.length > 0 && <p className="outcome-primary-evidence"><strong>Supporting evidence:</strong> {outcomeArtifactReferences(primaryEvidenceIds, session)}</p>}
          <p className="outcome-confidence"><strong>Verification:</strong> {verificationLabel}{session.outcome.provisional ? ' · provisional assessment' : ''}</p>
        </div>
        {qualificationItems.length > 0 && <div className="outcome-qualifications"><strong>Qualifications and unresolved questions</strong><ul>{simpleQualifications.map((item, index) => <li key={index}>{item}</li>)}</ul>{qualificationItems.length > simpleQualifications.length && <small>{qualificationItems.length - simpleQualifications.length} more saved qualification{qualificationItems.length - simpleQualifications.length === 1 ? '' : 's'} in Advanced Outcome.</small>}</div>}
      </div>}
      {!advancedOutcomeDetails && researchReferences}
      {advancedOutcomeDetails && <div className="outcome-subsections outcome-advanced">
        <details className="outcome-subsection outcome-conclusion" open>
          <summary><DisclosureChevron expanded={false}/>Conclusion</summary>
          <div className="outcome-subsection-content outcome-conclusion-content">
            {!session.outcome.conclusion && <span className="outcome-summary-kicker">{resultLabel}</span>}
            {session.outcome.conclusion && activeSections.has('conclusion')
              ? <div className="outcome-markdown"><Suspense fallback={<p role="status">Preparing formatted Conclusion…</p>}><RenderedMarkdown body={renderSession.outcome.conclusion || session.outcome.conclusion}/></Suspense></div>
              : !session.outcome.conclusion && activeSections.has('conclusion') ? <div className="outcome-markdown"><Suspense fallback={<p>{resultText}</p>}><RenderedMarkdown body={researchOutcomeMarkdown(renderSession)}/></Suspense></div>
                : <div className="outcome-conclusion-source">{resultText}</div>}
            {primaryEvidenceIds.length > 0 && <p className="outcome-primary-evidence"><strong>Supporting evidence:</strong> {outcomeArtifactReferences(primaryEvidenceIds, session)}</p>}
            <p className="outcome-confidence"><strong>Verification:</strong> {verificationLabel}{session.outcome.provisional ? ' · provisional assessment' : ''}</p>
            {(session.outcome.caveats?.length || review?.open_obligations?.length || review?.unresolved_objections?.length) ? <div className="outcome-qualifications"><strong>Qualifications and unresolved questions</strong>{!!session.outcome.caveats?.length && <ul>{session.outcome.caveats.map((item, index) => <li key={`caveat-${index}`}>{item}</li>)}</ul>}{!!review?.open_obligations?.length && <ul>{review.open_obligations.map((item, index) => <li key={`obligation-${index}`}>{item}</li>)}</ul>}{!!review?.unresolved_objections?.length && <ul>{review.unresolved_objections.map((item, index) => <li key={`objection-${index}`}>{item}</li>)}</ul>}</div> : null}
          </div>
        </details>
        {researchReferences}
        {approvedPackets.length > 0 && <details className="outcome-subsection continuation-evidence">
          <summary><DisclosureChevron expanded={false}/>Researcher-approved inherited evidence · {approvedSourceIds.size} source{approvedSourceIds.size === 1 ? '' : 's'}</summary>
          <div className="outcome-subsection-content">
            <p>These frozen artifacts were explicitly approved for transfer. Other available project evidence was not approved by this action. Delivery is recorded in exact provider inputs; the model's interpretation remains unverified.</p>
            {approvedPackets.map(packet => <section key={packet.packet_digest}>
              <p><strong>Approved question:</strong> {packet.question}</p>
              <p><button type="button" className="text-view-link" onClick={() => onViewStrategy(packet.parent_strategy_id)}>Inspect parent strategy</button></p>
              <ul>{packet.sources.map(source => <li key={source.artifact_id}>
                <button type="button" className="text-view-link" onClick={() => onViewPriorSession(source.source.session_id)}>Approved source · Session {source.source.session_number} · {source.strategy_title}</button>
                <p>{source.claim}</p><p>{source.status} · {source.verification}</p>
                <details><summary>Frozen artifact {source.artifact_id}</summary><pre>{JSON.stringify(source.artifact, null, 2)}</pre></details>
              </li>)}</ul>
              {packet.rejected_sources.length > 0 && <details><summary>{packet.rejected_sources.length} explicitly rejected transfer{packet.rejected_sources.length === 1 ? '' : 's'}</summary><ul>{packet.rejected_sources.map(row => <li key={row.artifact_id}>{row.artifact_id} — {row.rationale}</li>)}</ul></details>}
            </section>)}
          </div>
        </details>}
        {review && <details className="outcome-subsection outcome-reasoning-subsection"><summary><DisclosureChevron expanded={false}/>Reasoning / proof</summary><div className="outcome-subsection-content">{activeSections.has('reasoning') ? <div className="outcome-markdown"><Suspense fallback={<p>{review.argument_summary || review.claim || 'No reasoning was saved.'}</p>}><RenderedMarkdown body={researchReasoningMarkdown(renderSession)}/></Suspense></div> : <div className="solution-review"><p><strong>Investigated:</strong> {session.problem || 'Project objective unavailable in this historical record.'}</p><p><strong>Bounded strategy:</strong> {session.strategy_text || session.strategy_title || 'Strategy details unavailable.'}</p><p><strong>Claim:</strong> {review.claim || 'No claim recorded.'}</p><p><strong>Skeptic response:</strong> {review.skeptic_response || 'No substantive Skeptic response recorded.'}</p>{!!review.skeptic_objections?.length && <p><strong>Skeptic objections:</strong> {review.skeptic_objections.join(' · ')}</p>}{review.argument_steps?.length ? <ol>{review.argument_steps.map(step => <li key={`${step.research_artifact_id ?? ''}:${step.number}`}><strong>{step.title}</strong> <span>({step.epistemic_status})</span><p>{step.argument}</p><p><strong>Skeptic review:</strong> {step.review?.disposition || 'Not recorded'} — {step.review?.rationale || 'No rationale recorded'}</p>{!!step.review?.objection && <p><strong>Objection:</strong> {step.review.objection}</p>}<p><strong>Sources:</strong> {outcomeArtifactReferences([...(step.basis_artifact_ids || []), ...(step.research_artifact_id ? [step.research_artifact_id] : [])], session)}</p></li>)}</ol> : <p>No step-by-step argument was preserved. See the saved research artifacts before relying on this claim.</p>}{(review.strategy_findings?.length ?? 0) > 0 && <div><h4>Findings by strategy</h4>{review.strategy_findings!.map(item => <section key={item.strategy_id}><h5>{item.strategy_title} · {item.status}</h5><p>{item.claim}</p>{!!item.execution_status && <p><strong>Execution status:</strong> {item.execution_status}</p>}{!!item.failure_reason && <p><strong>Failure detail:</strong> {item.failure_reason}</p>}{item.reasoning_steps.length ? <ol>{item.reasoning_steps.map(step => <li key={step.number}><strong>{step.title}</strong> ({step.epistemic_status})<p>{step.argument}</p><p><strong>Review:</strong> {step.review?.disposition || 'Not recorded'} — {step.review?.rationale || item.skeptic_response}</p>{!!step.review?.objection && <p><strong>Objection:</strong> {step.review.objection}</p>}</li>)}</ol> : <p>No structured reasoning steps were preserved for this finding.</p>}{!!item.objections.length && <p><strong>Objections:</strong> {item.objections.join(' · ')}</p>}{!!item.open_obligations.length && <p><strong>Open obligations:</strong> {item.open_obligations.join(' · ')}</p>}<p><strong>Sources:</strong> {outcomeArtifactReferences(item.research_artifact_ids?.length ? item.research_artifact_ids : (item.research_artifact_id ? [item.research_artifact_id] : []), session)}</p></section>)}</div>}<p><strong>Assumptions:</strong> {review.assumptions?.join(' · ') || 'None recorded'}</p><p><strong>Proof obligations considered:</strong> {review.proof_obligations?.join(' · ') || 'None recorded'}</p><p><strong>Still open:</strong> {review.open_obligations?.join(' · ') || 'None recorded'}</p>{!!review.unresolved_objections?.length && <p><strong>Unresolved objections:</strong> {review.unresolved_objections.join(' · ')}</p>}{!!review.resolved_objections?.length && <p><strong>Objections addressed:</strong> {review.resolved_objections.join(' · ')}</p>}</div>}</div></details>}
        {hasEvidence && <details className="outcome-subsection outcome-evidence-subsection">
          <summary><DisclosureChevron expanded={false}/>Citations, evidence &amp; obligations</summary>
          <div className="outcome-subsection-content">
            {!!session.artifacts.length && <section className="research-artifacts" aria-label="Research artifacts"><div className="research-artifacts-heading"><h4>Research artifacts</h4></div><ol>{session.artifacts.map(artifact => {
              const sage = !!artifact.investigator_output.sage_execution;
              const executionField = sage ? 'sage_execution' : 'python_execution';
              const toolName = sage ? 'SageMath' : 'Python';
              const execution = artifact.investigator_output[executionField] && typeof artifact.investigator_output[executionField] === 'object' ? artifact.investigator_output[executionField] as Record<string, unknown> : null;
              const captured = execution && Array.isArray(execution.artifacts) ? execution.artifacts as Record<string, unknown>[] : [];
              const reused = artifact.investigator_output[executionField + '_reuse_reason'];
              return <li key={artifact.id} id={`research-artifact-${session.id}-${artifact.id}`}>{activeSections.has('citations') ? <div className="research-artifact-content research-artifact-markdown"><Suspense fallback={<p>{artifact.method}</p>}><RenderedMarkdown body={researchArtifactMarkdown(renderSession.artifacts.find(item => item.id === artifact.id) ?? artifact, renderSession)}/></Suspense></div> : <details>
                <summary>{researchArtifactPositionLabel(session, artifact)} · {artifact.claim_or_question} <span>{artifact.evidence_status}</span></summary>
                <div className="research-artifact-content"><p><strong>Method:</strong> {artifact.method}</p><p><strong>Assumptions:</strong> {artifact.assumptions.join(' · ') || 'None stated'}</p><p><strong>Evidence status:</strong> {artifact.evidence_status}</p><p><strong>Skeptic response:</strong> {artifact.skeptic_response}</p><p><strong>Objections:</strong> {artifact.objections.join(' · ') || 'No concrete objection recorded'}</p><p><strong>Open obligations:</strong> {artifact.open_obligations.join(' · ') || 'None recorded'}</p>{Array.isArray(artifact.skeptic_output.obligation_reviews) && artifact.skeptic_output.obligation_reviews.length > 0 && <p><strong>Obligation dispositions:</strong> {(artifact.skeptic_output.obligation_reviews as Record<string, unknown>[]).map(review => `${String(review.status ?? 'unknown')} · ${String(review.rationale ?? '')} [${Array.isArray(review.basis_artifact_ids) ? review.basis_artifact_ids.join(', ') : 'no artifact source'}]`).join(' · ')}. Model-reported and unverified.</p>}<p><strong>Coordinator decision:</strong> {artifact.coordinator_decision}</p><p><strong>Next question:</strong> {artifact.next_question || 'No further question; the session ended.'}</p>
                  {execution && <section className="outcome-python-evidence"><h5>{toolName} execution · {String(execution.status ?? 'status unavailable')}</h5><details className="research-execution-record"><summary>Execution source and output</summary><pre>{JSON.stringify(execution, null, 2)}</pre></details><p><strong>Execution ID:</strong> {String(execution.id ?? 'Unavailable')}</p>{typeof execution.exit_code === 'number' && <p><strong>Exit code:</strong> {execution.exit_code}</p>}{typeof reused === 'string' && <p><strong>Reuse:</strong> {reused}</p>}<p>{typeof execution.source === 'string' ? 'Exact source is retained in the execution record.' : 'Source unavailable in this record.'} Computation status is not proof of a mathematical claim.</p>{!!captured.length && <div><strong>Captured files</strong><ul>{captured.map((file, index) => <li key={index}>{String(file.filename ?? 'Unnamed file')} · {typeof file.size_bytes === 'number' ? `${file.size_bytes} bytes` : 'size unavailable'} · SHA-256 {String(file.sha256 ?? 'unavailable')}</li>)}</ul></div>}</section>}
                  <details><summary>Full validated role outputs</summary><h5>Investigator</h5>{Object.entries(artifact.investigator_output).filter(([key]) => !['python_execution', 'sage_execution'].includes(key)).map(([key, value]) => <p key={key}><strong>{key.replaceAll('_', ' ')}:</strong> {Array.isArray(value) ? value.join(' · ') : typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)}</p>)}<h5>Skeptic</h5>{Object.entries(artifact.skeptic_output).map(([key, value]) => <p key={key}><strong>{key.replaceAll('_', ' ')}:</strong> {Array.isArray(value) ? value.join(' · ') : typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)}</p>)}</details><small>{artifact.note}</small>
                </div></details>}</li>;
            })}</ol></section>}
          </div>
        </details>}
        <section className="outcome-other-details" aria-label="Other Outcome details"><h4>Other Outcome details</h4>
        <details className="outcome-subsection">
          <summary><DisclosureChevron expanded={false}/>Metrics</summary>
          <div className="outcome-subsection-content">
            {session.outcome.metrics ? <div className="outcome-metrics-groups">{renderMetricGroup('Operational', session.outcome.metrics.operational)}{renderMetricGroup('Research quality', session.outcome.metrics.research_quality)}</div> : <p className="outcome-unavailable">Metrics are not available for this historical session.</p>}
          </div>
        </details>
          <details className="outcome-subsection">
          <summary><DisclosureChevron expanded={false}/>Status</summary>
          <div className="outcome-subsection-content">
            <div className="outcome-label-value"><dt>Session lifecycle</dt><dd>{session.status}</dd></div><div className="outcome-label-value"><dt>Token usage</dt><dd>{session.tokens_used == null ? `Unavailable (${session.token_usage_status ?? 'not reported'})` : `${session.tokens_used.toLocaleString()} tokens · ${session.token_usage_status ?? 'reported'}`}</dd></div>
            <div className="outcome-label-value"><dt>Research result</dt><dd>{outcomeDisplayLabel(session)}</dd></div>
            <div className="outcome-label-value"><dt>Verification</dt><dd>{review?.verification_status && review.verification_status !== 'unknown' ? review.verification_status === 'verified' ? 'Verified (session record)' : 'Convincing but unverified' : 'Not independently verified'}</dd></div>
            <p className="outcome-integrity-note">A completed session or successful computation does not establish a mathematical proof.</p>
            {!!session.strategy_runs && session.strategy_runs.length > 1 && <section className="research-strategy-activity" aria-label="Strategy activity"><h4>Strategy activity</h4><ul>{session.strategy_runs.map(branch => <li key={branch.strategy_id} className={`strategy-run-${branch.status}`}><p><strong>{branch.strategy_title}</strong> · {branch.status} · {branch.current_action}</p><p>{session.scheduler_version === 2 ? researchPositionLabel(session, branch.cycle) : `Round ${branch.cycle}`} · {branch.calls_used} agent calls · {branch.artifacts.length} saved findings</p>{!!branch.current_question && <p><strong>Current question:</strong> {branch.current_question}</p>}{!!branch.reason && <p><strong>Coordinator rationale:</strong> {branch.reason}</p>}</li>)}</ul></section>}
            {!!session.steps.filter(step => ['failed', 'interrupted', 'running'].includes(step.status)).length && <section className="outcome-provider-attempts" aria-label="Incomplete provider attempts"><h4>Incomplete or failed attempts</h4><ul>{session.steps.filter(step => ['failed', 'interrupted', 'running'].includes(step.status)).map(step => <li key={step.id}><strong>{step.status} · {step.role}</strong><span>{researchPositionLabel(session, step.cycle)}, provider call {step.call_number}{step.provider_http_status ? (step.provider_response_channel === 'stream' ? ` · HTTP ${step.provider_http_status} transport, ${step.provider_stream_event ?? 'stream'} rejected` : ` · HTTP ${step.provider_http_status}`) : ''}{step.provider_error_code ? ` · Provider code: ${step.provider_error_code}` : ''}{step.failure_kind ? ` · ${step.failure_kind}` : ''}</span>{step.interruption_reason && <p>{step.interruption_reason}</p>}{step.failure_message && <p>{step.failure_message}</p>}{step.status === 'interrupted' && <p>The provider may have completed or charged usage; SIGMA did not repeat this ambiguous attempt automatically.</p>}</li>)}</ul></section>}
            {lastStep && ['running', 'interrupted', 'failed'].includes(lastStep.status) && !session.steps.some(step => ['failed', 'interrupted', 'running'].includes(step.status)) && <section className="research-incomplete-step" aria-label="Current or incomplete step"><strong>{lastStep.status === 'running' ? 'In progress' : 'Incomplete step'} · {lastStep.role}</strong><p>{researchPositionLabel(session, lastStep.cycle)}, provider call {lastStep.call_number}. This attempt is not a completed research artifact.</p></section>}
            {!!session.current_question && <p><strong>Current focus:</strong> {session.current_question}</p>}
            <div className="research-session-actions"><a className="text-view-link" data-tooltip={`View strategy: ${session.strategy_title}`} href={`#strategy-${session.strategy_id}`} onClick={event => { event.preventDefault(); onViewStrategy(session.strategy_id); }}>Go to strategy: {session.strategy_title}</a></div>
          </div>
        </details>
          <details className="outcome-subsection">
          <summary><DisclosureChevron expanded={false}/>Strategy Assessments</summary>
          <div className="outcome-subsection-content">
            <p className="outcome-subsection-intro">Each assessment records a strategy’s contribution to the project objective in this session.</p>
            {session.strategy_assessments?.length ? <div className="outcome-assessment-list">{session.strategy_assessments.map((item, index) => {
              const label: Record<StrategyAssessment['assessment'], string> = { contributed_to_solution: 'Contributed to solution', productive: 'Productive', unproductive: 'Unproductive', not_used: 'Not used', disabled: 'Disabled', unknown: 'Unknown' };
              return <article className="outcome-assessment" key={item.strategy_id ?? index}><h4>{item.strategy_title}</h4><div className="outcome-label-value"><dt>Disposition</dt><dd>{label[item.assessment] ?? 'Unknown'}</dd></div><div className="outcome-label-value"><dt>Rationale</dt><dd>{activeSections.has('assessments') ? <Suspense fallback={item.rationale}><RenderedMarkdown body={renderSession.strategy_assessments?.[index]?.rationale || item.rationale || 'No rationale recorded'}/></Suspense> : item.rationale || 'No rationale recorded'}</dd></div><div className="outcome-label-value"><dt>Cited evidence</dt><dd>{idList(item.basis_artifact_ids)}</dd></div></article>;
            })}</div> : <p className="outcome-unavailable">No strategy assessments were recorded for this session.</p>}
            {session.portfolio_decision?.strategy_actions?.length ? <section className="coordinator-portfolio-review" aria-label="Coordinator portfolio recommendations"><h4>Coordinator recommendations</h4><p>Evidence-linked recommendations are model-reported and unverified. Existing strategies are never changed automatically.</p><ul>{session.portfolio_decision.strategy_actions.map(item => <li key={item.strategy_id}><p><strong>{item.strategy_title}:</strong> {item.action.replaceAll('_', ' ')}</p><p>{item.rationale}{item.basis_artifact_ids.length > 0 && <> · Evidence: {idList(item.basis_artifact_ids)}</>}</p>{!!item.next_question && <p><strong>Next question:</strong> {item.next_question}</p>}</li>)}</ul>
              {!!session.portfolio_decision.combination_candidates?.length && <div className="coordinator-combinations"><strong>Combination candidates for human review</strong><ul>{session.portfolio_decision.combination_candidates.map((item, index) => { const titles = item.strategy_ids.map(id => session.strategy_runs?.find(branch => branch.strategy_id === id)?.strategy_title ?? 'Strategy'); return <li key={`${item.strategy_ids.join(':')}-${index}`}><p>{titles.join(' + ')} · {idList(item.basis_artifact_ids)}</p>{item.rationales.map((rationale, rationaleIndex) => <p key={rationaleIndex}>{rationale}</p>)}</li>; })}</ul></div>}
              {!!session.portfolio_decision.conflict_candidates?.length && <div className="coordinator-conflicts"><strong>Cross-strategy contradictions to resolve</strong><ul>{session.portfolio_decision.conflict_candidates.map((item, index) => <li key={`${item.source_artifact_id}-${item.target_artifact_id}-${index}`}><p>{item.relation.replaceAll('_', ' ')} · {idList([item.source_artifact_id, item.target_artifact_id])}</p><p>{item.rationale}</p></li>)}</ul></div>}
              {!!session.portfolio_decision.overlap_warnings?.length && <div className="coordinator-overlaps"><strong>Potentially overlapping approaches</strong><ul>{session.portfolio_decision.overlap_warnings.map((item, index) => <li key={`${item.source_artifact_id}-${item.target_artifact_id}-${index}`}><p>{idList([item.source_artifact_id, item.target_artifact_id])} · {item.rationale}</p></li>)}</ul></div>}
              {!!session.portfolio_decision.limitations?.length && <p className="coordinator-review-limit">{session.portfolio_decision.limitations.join(' ')}</p>}
            </section> : null}
          </div>
        </details>
          <details className="outcome-subsection">
          <summary><DisclosureChevron expanded={false}/>Provenance</summary>
          <div className="outcome-subsection-content">
            <div className="outcome-provenance-group"><h4>Session and configuration</h4><div className="outcome-label-value"><dt>Session ID</dt><dd>{session.id}</dd></div>{session.project_id && <div className="outcome-label-value"><dt>Project ID</dt><dd>{session.project_id}</dd></div>}<div className="outcome-label-value"><dt>Selected strategy</dt><dd>{session.strategy_title || 'Strategy'} · {session.strategy_ids?.length ? session.strategy_ids.join(', ') : session.strategy_id || 'ID unavailable'}</dd></div>{session.strategy_snapshot && <div className="outcome-label-value"><dt>Strategy snapshot</dt><dd>{String(session.strategy_snapshot.title ?? session.strategy_title)}{typeof session.strategy_snapshot.approach === 'string' ? ` · ${session.strategy_snapshot.approach}` : ''}</dd></div>}<div className="outcome-label-value"><dt>Model and thinking</dt><dd>{session.model || 'Unavailable'} · {thinkingLabels[session.reasoning_effort] ?? session.reasoning_effort ?? 'Unavailable'} · configured at session level, not an independent provider receipt</dd></div><div className="outcome-label-value"><dt>Billing mode</dt><dd>{session.mode === 'api_key' ? 'API key billing' : session.mode === 'chatgpt' ? 'ChatGPT plan allowance; actual allowance consumption unavailable' : session.mode || 'Unavailable'}</dd></div><div className="outcome-label-value"><dt>Started / updated</dt><dd>{session.started_at ? dateLabel(session.started_at) : 'Start time unavailable'} · {session.updated_at ? dateLabel(session.updated_at) : 'Update time unavailable'}</dd></div></div>
            {metricSources && <div className="outcome-provenance-group"><h4>Metric source inventory</h4><p className="outcome-subsection-intro">These session-scoped IDs identify records used by the metrics projection; they are not a per-measurement source map.</p>{([['Steps', metricSources.step_ids], ['Artifacts', metricSources.artifact_ids], ['Computation executions', metricSources.execution_ids], ['Strategies', metricSources.strategy_ids]] as [string, string[]][]).map(([label, ids]) => <div className="outcome-label-value" key={label}><dt>{label}</dt><dd>{ids.length ? ids.join(', ') : 'None recorded'}</dd></div>)}</div>}
            {session.steps.length > 0 && <div className="outcome-provenance-group"><h4>Agent call attempts</h4><ol className="outcome-provenance-list">{session.steps.map(step => <li key={step.id}><div className="outcome-label-value"><dt>{step.role} · {step.status}</dt><dd>Step {step.id} · Cycle {step.cycle} · Call {step.call_number}{step.strategy_id ? ` · Strategy ${step.strategy_id}` : ''}</dd></div><p>{step.started_at ? dateLabel(step.started_at) : 'Start time unavailable'}{step.finished_at ? ` · ${dateLabel(step.finished_at)}` : ' · no finish time recorded'}{step.provider_http_status ? (step.provider_response_channel === 'stream' ? ` · HTTP ${step.provider_http_status} transport, ${step.provider_stream_event ?? 'stream'} rejected` : ` · HTTP ${step.provider_http_status}`) : ''}{step.provider_error_code ? ` · Provider code: ${step.provider_error_code}` : ''}{step.failure_kind ? ` · ${step.failure_kind}` : ''}{step.interruption_reason ? ` · ${step.interruption_reason}` : ''}</p>{!!(step.context_artifact_ids?.length || step.prior_session_artifact_ids?.length || step.peer_strategy_artifact_ids?.length || step.peer_handoff_artifact_ids?.length) && <p><strong>Context artifacts:</strong> {idList([...(step.context_artifact_ids ?? []), ...(step.prior_session_artifact_ids ?? []), ...(step.peer_strategy_artifact_ids ?? []), ...(step.peer_handoff_artifact_ids ?? [])])}</p>}{!!step.peer_handoff_ids?.length && <p><strong>Peer handoffs:</strong> {step.peer_handoff_ids.join(', ')}</p>}{step.context_manifest && <details className="context-used-disclosure"><summary>Context used · {step.context_manifest.selected_count ?? step.context_manifest.sources?.filter(source => source.status === 'selected').length ?? 0} current artifacts selected · {step.context_manifest.omitted_count ?? 0} omitted</summary><p>{step.context_manifest.note ?? 'Deterministic extracts from saved records; originals remain in session history.'}</p>{typeof step.context_manifest.assembled_context_bytes === 'number' && <p>Serialized context: {step.context_manifest.assembled_context_bytes.toLocaleString()} bytes of {step.context_manifest.byte_limit?.toLocaleString() ?? 'bounded'} UTF-8 input</p>}{step.context_manifest.sources?.length ? <ul>{step.context_manifest.sources.slice(0, 32).map((source, index) => <li key={`${source.source_ids?.[0] ?? 'source'}-${index}`}><strong>{source.category?.replaceAll('_', ' ') ?? 'Source'} · {source.status ?? 'recorded'}:</strong> {source.source_ids?.join(', ') ?? 'ID unavailable'} — {source.reason ?? source.representation ?? 'See saved source'}</li>)}</ul> : <p>No source-level manifest was recorded for this historical step.</p>}{(step.context_manifest.sources?.length ?? 0) > 32 && <p>{(step.context_manifest.sources?.length ?? 0) - 32} additional manifest entries omitted from this view.</p>}{step.context_manifest.omitted_prior_session_findings?.count ? <p>{step.context_manifest.omitted_prior_session_findings.count} older session findings omitted; source IDs: {step.context_manifest.omitted_prior_session_findings.source_ids.join(', ') || 'bounded pointer list unavailable'}.</p> : null}{step.context_manifest.omitted_prior_failures?.count ? <p>{step.context_manifest.omitted_prior_failures.count} older operational failures omitted; attempt IDs: {step.context_manifest.omitted_prior_failures.attempt_ids.join(', ') || 'bounded pointer list unavailable'}.</p> : null}<ContextManifestNotes manifest={step.context_manifest}/></details>}{step.potential_truncation_fields?.length ? <p className="research-output-warning" role="status"><strong>Potentially truncated output:</strong> {step.potential_truncation_fields.join(', ')} reached a structured output field limit. Review the saved source text before relying on it.</p> : null}{step.provider_input_audit && <ProviderInputAuditDisclosure audit={step.provider_input_audit}/>} </li>)}</ol></div>}
            {session.artifacts.length > 0 && <div className="outcome-provenance-group"><h4>Artifact origins</h4><ul className="outcome-provenance-list">{session.artifacts.map(artifact => <li key={artifact.id}><div className="outcome-label-value"><dt>Artifact {artifact.sequence}</dt><dd>{artifact.id}</dd></div><p>{artifact.session_id ? `Session ${artifact.session_id}` : 'Source session unavailable'} · {artifact.strategy_id ? `Strategy ${artifact.strategy_id}` : 'Strategy unavailable'} · {researchArtifactPositionLabel(session, artifact)}</p></li>)}</ul></div>}
            {otherPriorFindings.length > 0 && <div className="outcome-provenance-group"><h4>Other prior session sources</h4><p>Available history; these sources are not implied to be researcher-approved transfers.</p><ul className="outcome-provenance-list">{otherPriorFindings.map(finding => <li key={`${finding.session_id}:${finding.id}`}><p><button type="button" className="text-view-link" onClick={() => onViewPriorSession(finding.session_id)}>Session {finding.session_number} · {finding.strategy_title} · Artifact {finding.sequence}</button></p><p>{finding.id} · {finding.claim_or_question}</p><p><strong>Method:</strong> {finding.method}</p>{!!finding.assumptions?.length && <p><strong>Assumption/domain scope:</strong> {finding.assumptions.join(' · ')}</p>}<p><strong>Evidence status:</strong> {finding.evidence_status} · <strong>Coordinator:</strong> {finding.coordinator_decision}</p>{!!finding.objections.length && <p><strong>Objections:</strong> {finding.objections.join(' · ')}</p>}{!!finding.open_obligations.length && <p><strong>Open obligations:</strong> {finding.open_obligations.join(' · ')}</p>}{!!finding.obligation_reviews?.length && <ul>{finding.obligation_reviews.map(review => <li key={review.obligation_id}><strong>Prior obligation disposition ({review.status}, {review.epistemic_status}):</strong> {review.rationale} · Basis artifacts: {review.basis_artifact_ids.join(', ') || 'none recorded'}</li>)}</ul>}{!!finding.next_question && <p><strong>Next question:</strong> {finding.next_question}</p>}</li>)}</ul></div>}
            {!!session.peer_handoffs_prompted?.length && <div className="outcome-provenance-group"><h4>Peer handoffs prompted</h4><ul className="outcome-provenance-list">{session.peer_handoffs_prompted.map((handoff, index) => <li key={index}><pre>{JSON.stringify(handoff, null, 2)}</pre></li>)}</ul></div>}
            <div className="outcome-provenance-group"><h4>Session facts</h4><div className="outcome-label-value"><dt>Build at session start</dt><dd><code data-tooltip={session.backend_build_commit || 'Older session without build provenance'}>{session.backend_build_commit || 'Not recorded'}</code></dd></div><div className="outcome-label-value"><dt>Elapsed wall time</dt><dd>{typeof session.elapsed_seconds === 'number' ? formatDuration(session.elapsed_seconds) : 'Unavailable'}</dd></div>{(session.duration_limit_minutes === null || typeof session.duration_limit_minutes === 'number') && <div className="outcome-label-value"><dt>Effective time ceiling</dt><dd>{session.duration_limit_minutes === null ? 'Unlimited' : `${session.duration_limit_minutes} minutes`}{typeof session.configured_duration_limit_minutes === 'number' && session.configured_duration_limit_minutes !== session.duration_limit_minutes ? ` (project setting: ${session.configured_duration_limit_minutes} minutes)` : ''}</dd></div>}<div className="outcome-label-value"><dt>Current action</dt><dd>{session.current_action || 'Unavailable'}</dd></div>{lastActivity && <div className="outcome-label-value"><dt>Last activity</dt><dd><time dateTime={lastActivity.timestamp}>{dateLabel(lastActivity.timestamp)}</time> · {lastActivity.message}</dd></div>}</div>
            {!!session.events.length && <section className="research-activity" aria-label="Recent session activity"><h4><button type="button" data-tooltip={`${activityExpanded ? 'Collapse' : 'Expand'} recent activity`} aria-expanded={activityExpanded} aria-controls={`session-activity-${session.id}`} onClick={() => setActivityExpanded(value => !value)}><DisclosureChevron expanded={activityExpanded}/>Recent activity</button></h4><ol id={`session-activity-${session.id}`} hidden={!activityExpanded}>{session.events.slice(-8).map(event => <li key={event.sequence}><time dateTime={event.timestamp}>{dateLabel(event.timestamp)}</time><span>{event.message}</span></li>)}</ol></section>}
          </div>
        </details>
          {(canIntervene || !!session.interventions?.length || (interventionWindowOpen && !supportsIntervention)) && <details className="human-interventions outcome-subsection" aria-label="Human research feedback">
        <summary><DisclosureChevron expanded={false}/>Human feedback</summary>
        <div className="human-interventions-content">
        {!supportsIntervention && <p className="human-intervention-note">Feedback is unavailable for this legacy session because it has no strategy-bound execution steps.</p>}
        {supportsIntervention && interventionWindowOpen && interventionCount.filter(item => item.status !== 'rejected').length >= 24 && <p className="human-intervention-note">This session reached its 24-feedback limit.</p>}
        {canIntervene && <form className="human-intervention-form" onSubmit={submitIntervention}>
          <fieldset className="human-intervention-type" aria-label="Feedback type"><label><input type="radio" name={`feedback-type-${session.id}`} value="priority" checked={interventionKind === 'priority'} onChange={() => setInterventionKind('priority')}/> Priority</label><label><input type="radio" name={`feedback-type-${session.id}`} value="objection" checked={interventionKind === 'objection'} onChange={() => setInterventionKind('objection')}/> Objection</label><label><input type="radio" name={`feedback-type-${session.id}`} value="evidence" checked={interventionKind === 'evidence'} onChange={() => setInterventionKind('evidence')}/> New Evidence</label></fieldset>
          <fieldset className="human-intervention-target" aria-label="Feedback recipient"><label><input type="radio" name={`feedback-target-${session.id}`} value="investigator" checked={targetAgentRole === 'investigator'} onChange={() => setTargetAgentRole('investigator')}/> For investigator</label><label><input type="radio" name={`feedback-target-${session.id}`} value="skeptic" checked={targetAgentRole === 'skeptic'} onChange={() => setTargetAgentRole('skeptic')}/> For skeptic</label></fieldset>
          <div className="human-intervention-strategy"><SigmaSelect ariaLabel="Strategy" value={interventionStrategy}
            options={[{ value: '*', label: 'All strategies' }, ...targetStrategies.map(item => ({ value: item.strategy_id, label: item.strategy_title }))]}
            onChange={setInterventionStrategy}/></div>
          <label className="human-intervention-text">Feedback<textarea value={interventionText} rows={3} onChange={event => setInterventionText(event.target.value)} placeholder="Add a research instruction or evidence note."/></label>
          <div className="human-intervention-submit"><button type="submit" className="text-view-link" aria-describedby={`human-feedback-help-${session.id}`} disabled={interventionBusy || busy || !interventionText.trim()}>{interventionBusy ? 'Adding…' : 'Add'}</button><small id={`human-feedback-help-${session.id}`}>Applies on next resume.</small></div>
          {interventionError && <p className="error" role="alert">{interventionError}</p>}
        </form>}
        {!!session.interventions?.length && <ol className="human-intervention-history">{session.interventions.slice(-8).reverse().map(item => <li key={item.id}>
          <div><strong>{item.kind.replaceAll('_', ' ')}</strong>{item.status !== 'queued' && <span>{item.status.replaceAll('_', ' ')}</span>}</div>
          <p>{item.text}</p>
          {item.rejection_reason && <small>{item.rejection_reason}</small>}
          {!!item.deliveries.length && <ul>{item.deliveries.map((delivery, index) => <li key={`${delivery.strategy_id}:${delivery.role}:${index}`}><span>{targetStrategies.find(strategy => strategy.strategy_id === delivery.strategy_id)?.strategy_title ?? 'Strategy'} · {delivery.role}{delivery.target_cycle ? ` · cycle ${delivery.target_cycle === 'next_eligible' ? 'pending' : delivery.target_cycle}` : ''}</span>{delivery.status !== 'queued' && <span>{delivery.status}{delivery.uptake ? ` · ${delivery.uptake}` : ''}</span>}{delivery.rationale && <small>{delivery.rationale}</small>}{delivery.attempts.length > 1 && <small>{delivery.attempts.length} delivery attempts; interrupted attempts remain in the audit.</small>}</li>)}</ul>}
        </li>)}</ol>}
        </div>
      </details>}
        </section>
      </div>}
    </section>
  </div>;
}

function MarkdownGlyph() {
  return <svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z" fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg>;
}

function CurrentUnderstandingView({ state, path, projectId, nextOrdinal, onInferred, onEvidence, onSession, guest }: { state: CurrentUnderstanding; path: string; projectId: string; nextOrdinal: number; guest: boolean; onInferred: (view: ProjectView, strategyId: string) => void; onEvidence: (source: EvidencePointer) => void; onSession: (id: string) => void }) {
  const [expanded, setExpanded] = useState(() => window.localStorage.getItem(`sigma.currentUnderstanding:${projectId}`) !== 'false');
  const [suggestionBusy, setSuggestionBusy] = useState(false);
  const [suggestionError, setSuggestionError] = useState('');
  const [suggestionStatus, setSuggestionStatus] = useState('');
  const [markdownView, setMarkdownView] = useState(false);
  const [guestMarkdownPreview, setGuestMarkdownPreview] = useState(false);
  const [formattedBlocks, setFormattedBlocks] = useState<Record<string, { source: string; body: string }>>({});
  const [formatProgress, setFormatProgress] = useState('');
  const [formatError, setFormatError] = useState('');
  const formatAbort = useRef<AbortController | null>(null);
  const textBlocks = [
    { field: 'scope_note', source: state.scope_note },
    ...state.findings.map((row, index) => ({ field: `findings.${index}.text`, source: row.text })),
    ...state.changes.map((row, index) => ({ field: `changes.${index}.text`, source: row.text })),
    ...state.obligations.map((row, index) => ({ field: `obligations.${index}.text`, source: row.text })),
    ...state.next_investigations.map((row, index) => ({ field: `next_investigations.${index}.question`, source: row.question })),
    ...state.limitations.map((source, index) => ({ field: `limitations.${index}`, source })),
  ];
  const textFingerprint = JSON.stringify(textBlocks);
  useEffect(() => () => { formatAbort.current?.abort(); }, [projectId, path, textFingerprint]);
  async function toggleUnderstandingMarkdown() {
    if (guest) { setGuestMarkdownPreview(true); return; }
    if (markdownView) {
      formatAbort.current?.abort();
      setMarkdownView(false);
      setFormatProgress('');
      setFormatError('');
      return;
    }
    setMarkdownView(true);
    const queued = textBlocks.filter(item => item.source.trim().length >= 40
      && item.source.length <= 20000 && formattedBlocks[item.field]?.source !== item.source);
    if (!queued.length) return;
    const controller = new AbortController();
    formatAbort.current = controller;
    let finishProviderRequest = () => {};
    try {
      const settingsResponse = await fetch(
        `/api/projects/proposals/config?${new URLSearchParams({ path, purpose: 'markdown' })}`,
        { signal: controller.signal },
      );
      const settings = await settingsResponse.json();
      if (!settingsResponse.ok || !settings.available) throw new Error(settings.message ?? settings.error ?? 'Connect AI in the header, then retry.');
      finishProviderRequest = beginProviderRequest('text-conversion');
      for (let index = 0; index < queued.length; index++) {
        if (controller.signal.aborted) return;
        const item = queued[index];
        setFormatProgress(`Formatting Current Understanding ${index + 1} of ${queued.length} text blocks…`);
        const expectedDigest = await sha256Text(item.source);
        if (controller.signal.aborted) return;
        const result = await post<{ body: string; source_digest: string }>('text/convert', {
          path, scope: 'current-understanding', field_path: item.field,
          target: 'markdown', expected_digest: expectedDigest,
          expected_project_id: projectId, expected_binding: settings.binding,
        }, controller.signal, true);
        if (result.source_digest !== expectedDigest) throw new Error('Current Understanding changed while formatting.');
        if (controller.signal.aborted) return;
        setFormattedBlocks(current => ({ ...current, [item.field]: { source: item.source, body: result.body } }));
      }
    } catch (cause) {
      if (!controller.signal.aborted) {
        setFormatError(`Markdown formatting stopped: ${friendlyProviderError(errorMessage(cause))}. Research was not changed.`);
      }
    } finally {
      finishProviderRequest();
      if (formatAbort.current === controller) formatAbort.current = null;
      setFormatProgress('');
    }
  }
  const narrative = (source: string, field: string, fallback?: string) => markdownView
    ? <div className="current-understanding-rendered"><Suspense fallback={<p>{fallback ?? source}</p>}><RenderedMarkdown body={formattedBlocks[field]?.source === source ? formattedBlocks[field].body : (fallback ?? source)}/></Suspense></div>
    : <p>{fallback ?? source}</p>;
  const inferencePending = useRef(false);
  const inferenceRequestId = useRef<string | null>(null);
  const inferenceCancelled = useRef(false);
  const inferenceCancelRequested = useRef(false);
  const inferenceBinding = useRef<string | null>(null);
  const inferenceResolved = useRef(false);
  useEffect(() => { setSuggestionError(''); setSuggestionStatus(''); }, [path]);
  function applyInferenceStatus(result: { status?: string; strategy?: Strategy | null; project?: ProjectView }) {
    if (result.status === 'completed' && result.strategy && result.project) {
      if (!inferenceResolved.current) onInferred(result.project, result.strategy.id);
      inferenceResolved.current = true;
      setSuggestionStatus(`Strategy added: ${result.strategy.title}. You can review or remove it in Strategies.`);
    } else if (result.status === 'no_strategy' || result.status === 'completed' && !result.strategy) {
      inferenceResolved.current = true;
      setSuggestionStatus('No additional strategy was identified from the current research.');
    } else if (result.status === 'cancelled') {
      inferenceResolved.current = true;
      setSuggestionStatus('Inference cancelled before provider dispatch. No strategy was added.');
    } else if (result.status === 'uncertain' || result.status === 'dispatched') {
      setSuggestionStatus('Cancellation was requested, but the provider outcome is uncertain. This request will not be repeated; refresh Strategies to check for a result.');
    } else if (result.status === 'provider_completed') {
      setSuggestionStatus('The provider completed, but SIGMA cannot confirm that the strategy was added. Refresh Strategies to inspect the current project; this request will not be repeated.');
    } else if (result.status === 'failed') {
      setSuggestionError('Inference did not complete. This request will not be repeated; start a new inference to try again.');
    } else if (result.status === 'not_found') {
      setSuggestionStatus('Inference was cancelled before the server accepted a provider request.');
    }
  }
  async function refreshInferenceStatus(requestId: string) {
    const binding = inferenceBinding.current;
    if (!binding) {
      setSuggestionStatus('Cancellation status is unavailable. Refresh Strategies to inspect the current project.');
      return;
    }
    try {
      const query = new URLSearchParams({ path, expected_project_id: projectId, expected_binding: binding, request_id: requestId });
      const response = await fetch(`/api/projects/strategy-inference/status?${query}`, { cache: 'no-store' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Could not check inference status.');
      applyInferenceStatus(result);
    } catch {
      setSuggestionStatus('Cancellation status is unavailable. Refresh Strategies to inspect the current project; the request will not be repeated automatically.');
    }
  }
  async function inferStrategy() {
    if (inferencePending.current) return;
    inferencePending.current = true;
    inferenceCancelled.current = false;
    inferenceCancelRequested.current = false;
    inferenceResolved.current = false;
    inferenceBinding.current = null;
    inferenceRequestId.current = crypto.randomUUID();
    setSuggestionBusy(true); setSuggestionError(''); setSuggestionStatus('');
    let finishProviderRequest = () => {};
    try {
      const configResponse = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { cache: 'no-store' });
      const config = await configResponse.json();
      if (!configResponse.ok) throw new Error(config.error ?? 'Could not read AI settings.');
      if (config.project_id !== projectId) throw new Error('Project identity changed. Reopen it before suggesting a strategy.');
      if (!config.available) throw new Error(config.message ?? 'Connect the selected AI account before requesting a suggestion.');
      inferenceBinding.current = config.binding;
      if (inferenceCancelRequested.current) {
        inferenceResolved.current = true;
        setSuggestionStatus('Inference cancelled before provider dispatch. No strategy was added.');
        return;
      }
      finishProviderRequest = beginProviderRequest('strategy-inference');
      const result = await post<{ strategy: Strategy | null; project: ProjectView; inference_status?: string }>('strategy-inference', {
        path, expected_binding: config.binding, expected_mode: config.mode, expected_project_id: projectId, request_id: inferenceRequestId.current,
      });
      applyInferenceStatus({ ...result, status: result.inference_status ?? (result.strategy ? 'completed' : 'no_strategy') });
    } catch (cause) {
      if (inferenceCancelRequested.current) {
        await refreshInferenceStatus(inferenceRequestId.current ?? '');
        return;
      }
      const message = errorMessage(cause);
      setSuggestionError(message); reportRequestFailure(message);
    } finally { finishProviderRequest(); inferencePending.current = false; inferenceRequestId.current = null; setSuggestionBusy(false); }
  }
  async function cancelInference() {
    const requestId = inferenceRequestId.current;
    if (!requestId || inferenceCancelRequested.current) return;
    inferenceCancelRequested.current = true;
    inferenceCancelled.current = true;
    setSuggestionStatus('Cancellation requested. Checking whether a strategy was added…');
    try {
      if (!inferenceBinding.current) return;
      const result = await post<{ status: string; strategy?: Strategy | null; project?: ProjectView }>('proposals/cancel', {
        request_id: requestId, path, expected_project_id: projectId, expected_binding: inferenceBinding.current,
      });
      applyInferenceStatus(result);
    }
    catch (cause) {
      const message = errorMessage(cause); setSuggestionError(message); reportRequestFailure(message);
      await refreshInferenceStatus(requestId);
    }
  }
  const sourceButton = (source: EvidencePointer, context: string) => <button type="button" className="text-view-link" disabled={!source.available} aria-label={`${context}: Session ${source.session_number}, Artifact ${source.artifact_sequence || 'unnumbered'}`} onClick={() => onEvidence(source)}>Session {source.session_number} · {source.artifact_sequence ? `Artifact ${source.artifact_sequence}` : 'Saved evidence'}</button>;
  const excerpt = (text: string) => text.length > 360 ? `${text.slice(0, 360)}… (text continues)` : text;
  const findings = state.current_finding_ids.map(id => state.findings.find(row => row.id === id)).filter((row): row is CurrentFinding => !!row);
  const questions = [...state.obligations].sort((a, b) => (Number(b.actionable) * 4 + Number(b.status === 'historical_unreconciled') * 2) - (Number(a.actionable) * 4 + Number(a.status === 'historical_unreconciled') * 2));
  const suggested = state.next_investigations[0];
  const visibleQuestions = questions.filter(row => row.id !== suggested?.obligation_id && !['resolved_reported', 'superseded_reported', 'retracted_reported'].includes(row.status)).slice(0, 2);
  const remainingQuestions = questions.filter(row => row.id !== suggested?.obligation_id && !visibleQuestions.includes(row));
  const findingRow = (row: CurrentFinding) => <li key={row.id}><strong>{row.strategy_title || 'Historical strategy'}</strong>{narrative(row.text, `findings.${state.findings.indexOf(row)}.text`, markdownView ? undefined : excerpt(row.text))}<p className="hint">{row.status.replaceAll('_', ' ')} · {row.verification}</p><p>{sourceButton(row.source, 'Inspect finding')}</p></li>;
  const changeRow = (row: CurrentUnderstanding['changes'][number], index: number) => <li key={`${row.kind}-${row.source.session_id}-${row.source.artifact_id}-${index}`}><strong>{({ obligation_addressed: 'Resolution reported', obligation_superseded: 'Supersession reported', obligation_retracted: 'Retraction reported', local_refutation_reported: 'Local counterexample reported', later_finding_available: 'Later review saved', supersedes: 'Supersession reported', refutes: 'Refutation reported' } as Record<string, string>)[row.kind] || 'Saved assessment'}</strong>{narrative(row.text, `changes.${state.changes.indexOf(row)}.text`, markdownView ? undefined : excerpt(row.text))}<p className="hint">{row.caution}</p><p>{sourceButton(row.source, 'Inspect later evidence')}{row.earlier && <> · {sourceButton(row.earlier, 'Inspect earlier evidence')}</>}</p></li>;
  const questionRow = (row: CurrentQuestion) => <li key={row.id}>{narrative(row.text, `obligations.${state.obligations.indexOf(row)}.text`, markdownView ? undefined : excerpt(row.text))}<p className="hint">{row.status.replaceAll('_', ' ')} · {row.note}</p>{row.sources.length > 0 && <p>{sourceButton(row.sources.at(-1)!, 'Inspect obligation')}{row.narrative_resolution_sources.slice(-1).map(source => <span key={source.record_path}> · {sourceButton(source, 'Inspect narrative resolution')}</span>)}{row.dispositions.filter(item => item.valid).slice(-1).map(item => <span key={item.source.record_path}> · {sourceButton(item.source, 'Inspect disposition')}</span>)}</p>}</li>;
  return <details className="outcome-subsection current-understanding" open={expanded} onToggle={event => {
    const isOpen = event.currentTarget.open;
    setExpanded(isOpen);
    window.localStorage.setItem(`sigma.currentUnderstanding:${projectId}`, String(isOpen));
  }}>
    <summary aria-label="Current understanding"><DisclosureChevron expanded={false}/><span>Current understanding</span><button type="button" className="sigma-render-toggle current-understanding-markdown" aria-label={markdownView ? "Show original Current Understanding text" : "Format Current Understanding as Markdown"} aria-pressed={markdownView} data-tooltip={markdownView ? "Show original Current Understanding text" : "Format Current Understanding as Markdown"} onClick={event => { event.preventDefault(); event.stopPropagation(); void toggleUnderstandingMarkdown(); }}><MarkdownGlyph/></button>{suggestionBusy ? <span className="strategy-suggestion-progress" role="status" aria-live="polite"><span className="generating-hourglass" aria-hidden="true">⌛</span>{inferenceCancelRequested.current ? 'Checking cancellation…' : 'Inferring…'}<button type="button" className="text-view-link" data-tooltip="Request cancellation. If the provider has already received the request, SIGMA checks whether a strategy was added." onClick={event => { event.preventDefault(); event.stopPropagation(); void cancelInference(); }}>Cancel</button></span> : <button type="button" className="text-view-link strategy-suggestion-trigger" aria-label={`Infer strategy #${nextOrdinal}`} data-tooltip="Uses current findings and unresolved research questions to identify and save a new strategy automatically. You can review or remove it afterward. One bounded AI request uses the selected account and existing allowance protections." disabled={suggestionBusy || guest} onClick={event => { event.preventDefault(); event.stopPropagation(); void inferStrategy(); }}>Infer strategy #{nextOrdinal}</button>}</summary>
    {guestMarkdownPreview && createPortal(<GuestFeatureDialog title="Markdown for Current Understanding"
      message="With member access and ChatGPT, SIGMA can reformat the findings, questions and limitations as Markdown. This is a presentation change, not a scientific result. No text was sent or changed."
      onClose={() => setGuestMarkdownPreview(false)}/>, document.body)}
    <div className="hint current-understanding-scope">{markdownView ? narrative(state.scope_note, 'scope_note') : state.scope_note}</div>{formatProgress && <p className="outcome-markdown-progress" role="status">{formatProgress}</p>}{formatError && <p className="outcome-conclusion-format-error" role="alert">{formatError}</p>}
    <div className="current-understanding-columns">
      <section><h3>Current findings</h3>{findings.length ? <><ol>{findings.slice(0, 2).map(findingRow)}</ol>{findings.length > 2 && <details><summary>{findings.length - 2} more local findings</summary><ol>{findings.slice(2).map(findingRow)}</ol></details>}</> : <p>No reviewed finding is saved. An empty or failed run establishes no answer.</p>}</section>
      <section><h3>What changed / superseded</h3>{state.changes.length ? <><ol>{state.changes.slice(0, 2).map(changeRow)}</ol>{state.changes.length > 2 && <details><summary>{state.changes.length - 2} more recorded changes</summary><ol>{state.changes.slice(2).map(changeRow)}</ol></details>}</> : <p>No explicit change or supersession is recorded. Different wording is not a contradiction.</p>}{state.failures.length > 0 && <details><summary>Execution states and unsuccessful branches</summary><ul>{state.failures.map((row, index) => <li key={`${row.session_id}-${index}`}>{row.status}: {row.note} <button className="text-view-link" type="button" onClick={() => onSession(row.session_id)}>Session {row.session_number}</button></li>)}</ul></details>}</section>
      <section><h3>Open or not yet reconciled</h3>
        <h4>Possible next investigation</h4>{suggested ? <div>{narrative(suggested.question, `next_investigations.${state.next_investigations.indexOf(suggested)}.question`)}<p className="hint">{suggested.qualification}</p>{sourceButton(suggested.source, 'Inspect suggested question')}</div> : <p>No current evidence-linked next investigation is determined. Inspect unreconciled history before choosing a new run.</p>}
        {visibleQuestions.length ? <ol>{visibleQuestions.map(questionRow)}</ol> : !questions.length && <p>No explicit obligation is recorded; this does not mean the question is solved.</p>}
        {remainingQuestions.length > 0 && <details><summary>{remainingQuestions.length} more recorded questions / dispositions</summary><ol>{remainingQuestions.map(questionRow)}</ol></details>}
      </section>
    </div>
    <details className="current-understanding-limits"><summary>Scope, uncertainty and earlier findings</summary><ul>{state.limitations.map((note, index) => <li key={index}>{markdownView ? <div className="current-understanding-rendered"><Suspense fallback={note}><RenderedMarkdown body={formattedBlocks[`limitations.${index}`]?.source === note ? formattedBlocks[`limitations.${index}`].body : note}/></Suspense></div> : note}</li>)}</ul><p>All {state.findings.length} findings remain available in the session history below. No relationship or resolution is inferred from a change of wording.</p><ol>{state.findings.filter(row => !state.current_finding_ids.includes(row.id)).map(findingRow)}</ol></details>
    <div className="strategy-suggestion-feedback">{suggestionError && <p className="error" role="alert">{suggestionError}</p>}{suggestionStatus && <p role="status">{suggestionStatus}</p>}</div>
  </details>;
}

function ResearchWorkspace({ collaborationRevision, artifactAuthors, viewerEmail, projectOwnerEmail, path, projectId, strategies, nextStrategyOrdinal, onInferredStrategy, advancedOutcomeDetails, onEnableAdvancedOutcome, onViewStrategy, onForkFromFindings, onControlsChange, onRunningChange, onInitialActivity, onRevealNewSession, onSectionOpened, sessionControls, guest, onGuestPlay, playButtonRef, controlsDisabled, missingType, safeSavedTypeSettings, savedTypeName, onChooseReplacement }: { collaborationRevision?: number; artifactAuthors?: Record<string, string>; viewerEmail?: string; projectOwnerEmail?: string | null; path: string; projectId: string; strategies: Strategy[]; nextStrategyOrdinal: number; onInferredStrategy: (view: ProjectView, id: string) => void; advancedOutcomeDetails: boolean; onEnableAdvancedOutcome: () => Promise<void>; onViewStrategy: (id: string) => void; onForkFromFindings: (session: ResearchSession) => void; onControlsChange: (controls: ProcessControls) => void; onRunningChange: (running: boolean) => void; onInitialActivity: (status: 'running' | 'queued' | null) => void; onRevealNewSession: () => void; onSectionOpened: () => void; sessionControls: ProcessControls; guest: boolean; onGuestPlay: () => void; playButtonRef: React.RefObject<HTMLButtonElement | null>; controlsDisabled: boolean; missingType: boolean; safeSavedTypeSettings: boolean; savedTypeName: string; onChooseReplacement: () => void }) {
  const cloud = useCloudIdentity();
  const mockResearch = cloud?.mock_auth === true;
  const eligible = useMemo(() => strategies.filter(strategy => !strategy.removed_at && strategy.enabled), [strategies]);
  const [sessions, setSessions] = useState<ResearchSession[]>([]);
  const [invalidSessionCount, setInvalidSessionCount] = useState(0);
  const [maxConcurrentSessions, setMaxConcurrentSessions] = useState(1);
  const [currentUnderstanding, setCurrentUnderstanding] = useState<CurrentUnderstanding | null>(null);
  const selectedSessionId = useRef('');
  const sessionsLoaded = useRef(false);
  const initialRevealSessionId = useRef<string | null>(null);
  const [pendingStrategyIds, setPendingStrategyIds] = useState<string[]>([]);
  const [config, setConfig] = useState<{ available: boolean; model: string; reasoning_effort: string; mode: string; binding: string; message: string } | null>(null);
  const [limits, setLimits] = useState<ResearchLimits | null>(null);
  const [confirmStart, setConfirmStart] = useState(false);
  const [guestSessionCard, setGuestSessionCard] = useState(false);
  const [confirmMissingType, setConfirmMissingType] = useState(false);
  const continueWithSavedType = useRef(false);
  const missingTypeDialog = useRef<HTMLDialogElement>(null);
  const [confirmRemoveId, setConfirmRemoveId] = useState('');
  // Contextual failures belong to the affected session, not the global toast.
  // A dismissed failure remains suppressed until the user tries Resume again.
  const [sessionControlFailures, setSessionControlFailures] = useState<Record<string, { message: string; serial: number; dismissed: boolean }>>({});
  const sessionControlSerial = useRef(0);
  const [resumeAuthorization, setResumeAuthorization] = useState<ResumeAuthorization | null>(null);
  const resumeApprovalResolver = useRef<((approved: boolean) => void) | null>(null);
  const resumePlayAnchor = useRef<HTMLButtonElement | null>(null);
  useEffect(() => () => {
    const resolve = resumeApprovalResolver.current;
    resumeApprovalResolver.current = null;
    resolve?.(false);
  }, []);
  const requestResumeAuthorization = (request: ResumeAuthorization): Promise<boolean> =>
    new Promise(resolve => {
      if (resumeApprovalResolver.current) { resolve(false); return; }
      resumeApprovalResolver.current = resolve;
      setResumeAuthorization(request);
    });
  const answerResumeAuthorization = (approved: boolean) => {
    const resolve = resumeApprovalResolver.current;
    resumeApprovalResolver.current = null;
    setResumeAuthorization(null);
    resolve?.(approved);
  };
  const [busy, setBusy] = useState(false);
  // Presentation only: never manufacture a persisted running Session or run number.
  const [admittingSession, setAdmittingSession] = useState(false);
  const stopAfterStart = useRef(false);
  const [stoppingStartingSession, setStoppingStartingSession] = useState(false);
  const [pendingSessionAction, setPendingSessionAction] = useState<{ id: string; action: 'pause' | 'resume' | 'stop' } | null>(null);
  const stopAfterResume = useRef<Set<string>>(new Set());
  const [error, setError] = useState('');
  const [readError, setReadError] = useState('');
  const [announcement, setAnnouncement] = useState('');
  const [expanded, setExpanded] = useState(() => window.localStorage.getItem(`sigma.sessionsPane:${path}`) !== 'false');
  useEffect(() => {
    const opened = (event: Event) => {
      if ((event as CustomEvent<string>).detail !== 'sessions') {
        setExpanded(false);
        window.localStorage.setItem(`sigma.sessionsPane:${path}`, 'false');
      }
    };
    window.addEventListener('sigma-project-section-opened', opened);
    return () => window.removeEventListener('sigma-project-section-opened', opened);
  }, [path]);
  const [expandedSessionIds, setExpandedSessionIds] = useState<Set<string>>(() => new Set());
  useEffect(() => {
    const dialog = missingTypeDialog.current;
    if (!dialog) return;
    if (confirmMissingType && !dialog.open) dialog.showModal();
    else if (!confirmMissingType && dialog.open) dialog.close();
  }, [confirmMissingType]);
  const noticeStorageKey = `sigma.dismissedSessionNotices:${path}`;
  const [dismissedNoticeKeys, setDismissedNoticeKeys] = useState<Set<string>>(() => {
    try {
      const saved: unknown = JSON.parse(window.localStorage.getItem(noticeStorageKey) || '[]');
      return new Set(Array.isArray(saved) ? saved.filter((key): key is string => typeof key === 'string') : []);
    } catch { return new Set<string>(); }
  });
  useEffect(() => {
    try {
      const saved: unknown = JSON.parse(window.localStorage.getItem(noticeStorageKey) || '[]');
      setDismissedNoticeKeys(new Set(Array.isArray(saved) ? saved.filter((key): key is string => typeof key === 'string') : []));
    } catch { setDismissedNoticeKeys(new Set()); }
  }, [noticeStorageKey]);
  const dismissSessionNotice = (key: string) => {
    setDismissedNoticeKeys(current => {
      const next = new Set([...current, key].slice(-250));
      try { window.localStorage.setItem(noticeStorageKey, JSON.stringify([...next])); } catch { /* Local storage can be unavailable; in-memory dismissal still works. */ }
      return next;
    });
  };
  const readErrorReported = useRef(false);
  const lastAnnouncement = useRef('');
  const [projectDiagnostics, setProjectDiagnostics] = useState<ProjectDiagnostic[]>([]);
  const [diagnosticStatus, setDiagnosticStatus] = useState('');
  const reloadDiagnostics = useCallback(async () => {
    const response = await fetch(`/api/projects/diagnostics?${new URLSearchParams({ path })}`, { cache: 'no-store' });
    if (!response.ok) throw new Error('Project diagnostics could not be retrieved.');
    const result = await response.json() as { diagnostics: ProjectDiagnostic[] };
    setProjectDiagnostics(result.diagnostics);
  }, [path]);
  useEffect(() => { if (guest) return; void reloadDiagnostics().catch(() => setDiagnosticStatus('Project diagnostics unavailable; previous errors may not be shown.')); }, [guest, reloadDiagnostics]);
  const recordClientError = async (message: string, stage: string, sessionId?: string) => {
    if (guest) return;
    const result = await reportProjectDiagnostic(path, message, stage, crypto.randomUUID());
    setDiagnosticStatus(result.status);
    if (result.recorded) {
      // If the server redacted the message, render that same sanitized
      // diagnostic in the UI instead of showing a different raw value.
      const sanitizedMessage = result.message;
      if (sanitizedMessage && sanitizedMessage !== message) {
        if (stage === 'session_read') setReadError(sanitizedMessage);
        else if ((stage === 'session_control' || stage === 'session_failure') && sessionId) {
          setSessionControlFailures(current => {
            const prior = current[sessionId];
            if (!prior) return current;
            return { ...current, [sessionId]: { ...prior, message: sanitizedMessage } };
          });
        } else setError(sanitizedMessage);
      }
      void reloadDiagnostics().catch(() => {});
    }
  };
  const idempotencyKey = useRef<string | null>(null);
  const submittingStart = useRef(false);
  const activeSession = sessions.find(item => item.status === 'queued' || item.status === 'running');
  const runningSession = sessions.find(item => item.status === 'running');
  useEffect(() => { onRunningChange(Boolean(runningSession)); }, [runningSession?.id, onRunningChange]);

  useEffect(() => {
    const revealRunningSession = (event: Event) => {
      const requested = (event as CustomEvent<string>).detail;
      const active = (requested ? sessions.find(item => item.id === requested) : null)
        ?? sessions.find(item => item.status === 'running')
        ?? sessions.find(item => item.status === 'queued');
      // Expanding a shared run never requires being its starter.
      if (active) revealSession(active.id, true);
      else {
        onSectionOpened();
        setExpanded(true);
        window.localStorage.setItem(`sigma.sessionsPane:${path}`, 'true');
        requestAnimationFrame(() => document.getElementById('sessions-heading')?.scrollIntoView({ block: 'center' }));
      }
    };
    window.addEventListener('sigma-reveal-running-session', revealRunningSession);
    return () => window.removeEventListener('sigma-reveal-running-session', revealRunningSession);
  }, [sessions, path, onSectionOpened]);

  const load = useCallback(async (preferredId?: string, signal?: AbortSignal) => {
    const query = new URLSearchParams({ path });
    const response = await fetch(`/api/projects/research-sessions?${query}`, { signal, headers: { 'X-Sigma-Error-Handled': 'true' } });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error ?? 'Could not read research sessions');
    if (!Array.isArray(data.sessions)) throw new Error('Research sessions response is missing its sessions array');
    const rawSessions = data.sessions as unknown[];
    const nextSessions: ResearchSession[] = rawSessions
      .map(value => {
        try { return sessionForDisplay(value); }
        catch (cause) {
          console.warn('Saved research session could not be normalized for display', {
            id: value && typeof value === 'object' && 'id' in value ? value.id : undefined,
            error: errorMessage(cause),
          });
          return null;
        }
      })
      .filter((item: ResearchSession | null): item is ResearchSession => item !== null);
    setInvalidSessionCount(rawSessions.length - nextSessions.length);
    setSessions(nextSessions);
    // Keep UI admission in sync with the limits snapshot used by the server.
    setMaxConcurrentSessions(Number(data.max_concurrent_sessions) || 1);
    setCurrentUnderstanding(data.current_understanding?.project_id === projectId ? data.current_understanding as CurrentUnderstanding : null);
    readErrorReported.current = false;
    setReadError('');
    const requestedId = preferredId ?? selectedSessionId.current;
    const firstLoad = !sessionsLoaded.current;
    const chosen = (requestedId ? nextSessions.find(item => item.id === requestedId) : null)
      ?? (!sessionsLoaded.current && !selectedSessionId.current
        ? nextSessions.find(item => item.status === 'queued' || item.status === 'running' || item.status === 'paused') ?? nextSessions[0] ?? null
        : null);
    if (firstLoad) {
      const active = nextSessions.find(item => item.status === 'running')
        ?? nextSessions.find(item => item.status === 'queued');
      onInitialActivity(active?.status === 'running' || active?.status === 'queued' ? active.status : null);
      const requestedReveal = new URLSearchParams(window.location.search).get('reveal_session');
      initialRevealSessionId.current = requestedReveal && nextSessions.some(item => item.id === requestedReveal)
        ? requestedReveal : null;
      if (requestedReveal && nextSessions.some(item => item.id === requestedReveal)) {
        setExpanded(true); window.localStorage.setItem(`sigma.sessionsPane:${path}`, 'true');
        setExpandedSessionIds(new Set([requestedReveal]));
      }
    }
    sessionsLoaded.current = true;
    selectedSessionId.current = chosen?.id ?? '';
    if (firstLoad && chosen) setExpandedSessionIds(current => current.size ? current : new Set([chosen.id]));
    if (chosen) {
      const transition = `${chosen.id}:${chosen.status}:${chosen.current_action}`;
      if (chosen.status === 'failed' && lastAnnouncement.current.startsWith(`${chosen.id}:`) && /:(queued|running):/.test(lastAnnouncement.current)) {
        // The failed session's in-flow card is the sole visible notice.
        void recordClientError(chosen.message, 'session_failure', chosen.id);
      }
      if (lastAnnouncement.current && transition !== lastAnnouncement.current) {
        setAnnouncement(`Research session ${chosen.session_number}: ${chosen.status}. ${chosen.current_action}.`);
      }
      lastAnnouncement.current = transition;
    }
    return chosen;
  }, [path, projectId, onInitialActivity]);

  const reportReadFailure = useCallback((cause: unknown) => {
    const message = errorMessage(cause);
    setReadError(message);
    if (!readErrorReported.current) {
      void recordClientError(message, 'session_read');
    }
    readErrorReported.current = true;
  }, [path]);

  const lastResearchRevision = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (collaborationRevision === undefined) return;
    if (lastResearchRevision.current === undefined) {
      lastResearchRevision.current = collaborationRevision;
      return;
    }
    if (lastResearchRevision.current === collaborationRevision) return;
    lastResearchRevision.current = collaborationRevision;
    void load().catch(reportReadFailure);
  }, [collaborationRevision, load, reportReadFailure]);

  useEffect(() => {
    const controller = new AbortController();
    void load(undefined, controller.signal).catch(cause => { if (!controller.signal.aborted) reportReadFailure(cause); });
    return () => controller.abort();
  }, [load, reportReadFailure]);

  const sessionPollPending = useRef(false);
  useEffect(() => {
    if (!activeSession) return;
    const stopWatching = watchResearchProviderActivity(path, projectId);
    let alive = true;
    const poll = async () => {
      if (!alive || document.visibilityState !== 'visible' || sessionPollPending.current) return;
      sessionPollPending.current = true;
      try {
        // Read only the active session during frequent progress polling. The
        // full history and Current Understanding are rebuilt on meaningful
        // milestones, not every two seconds in every collaborator's browser.
        const response = await fetch(
          `/api/projects/research-sessions/${encodeURIComponent(activeSession.id)}?${new URLSearchParams({ path })}`,
          { cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } },
        );
        const data = await response.json();
        if (!response.ok) throw new Error(data.error ?? 'Could not read research progress');
        if (!alive) return;
        const current = sessionForDisplay(data);
        if (!current) throw new Error('Research progress response was invalid');
        setSessions(sessions => sessions.map(item => item.id === current.id ? current : item));
        if (current.status !== activeSession.status
          || current.steps.length !== activeSession.steps.length
          || current.artifacts.length !== activeSession.artifacts.length) {
          void load(current.id).catch(reportReadFailure);
        }
      } catch (cause) {
        if (alive) reportReadFailure(cause);
      } finally {
        sessionPollPending.current = false;
      }
    };
    const tick = () => { void poll(); };
    const timer = window.setInterval(tick, 2000);
    document.addEventListener('visibilitychange', tick);
    return () => { alive = false; window.clearInterval(timer); document.removeEventListener('visibilitychange', tick); stopWatching(); };
  }, [activeSession?.id, activeSession?.status, activeSession?.steps.length, activeSession?.artifacts.length, load, path, projectId, reportReadFailure]);

  const sponsoredSession = cloud?.target === 'hosted'
    || (cloud?.target === 'local' && cloud.funding.selectedConnection === 'sponsored');
  async function begin(onlyIds?: string[], continueUsingSavedTypeSettings = false) {
    continueWithSavedType.current = continueUsingSavedTypeSettings;
    const chosenIds = onlyIds || eligible.map(strategy => strategy.id);
    setBusy(true); setError('');
    try {
      if (guest) { setGuestSessionCard(true); return; }
      if (mockResearch) {
        if (!chosenIds.length || chosenIds.length > 12) throw new Error('Choose between one and twelve enabled strategies.');
        setPendingStrategyIds(chosenIds);
        setConfig({ available: true, model: 'mock-deterministic', reasoning_effort: 'none', mode: 'mock', binding: 'mock', message: 'Local simulation: no provider calls.' });
        setConfirmStart(true);
        return;
      }
      // Neither read depends on the other; avoid two serial network RTTs.
      const [response, limitResponse] = await Promise.all([
        fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`),
        fetch(`/api/projects/research-limits?${new URLSearchParams({ path })}`),
      ]);
      const [current, currentLimits] = await Promise.all([
        response.json(), limitResponse.json(),
      ]);
      if (!response.ok) throw new Error(current.error ?? 'Could not read AI configuration');
      if (!limitResponse.ok) throw new Error(currentLimits.error ?? 'Could not read research limits');
      const validation = validateLimitDraft(draftLimits(currentLimits));
      if (!validation.value) {
        throw new Error(validation.errors.maximum_estimated_cost_usd
          ?? 'Research limits need attention. Update them in Home Settings → Limits before starting a session.');
      }
      if (!current.available) throw new Error(current.message ?? 'Connect the selected AI account before investigating');
      if (chosenIds.length > 12) {
        throw new Error('A session can include at most 12 enabled strategies. Disable strategies before starting.');
      }
      setPendingStrategyIds(chosenIds);
      setConfig(current); setLimits(currentLimits);
      setConfirmStart(true);
    } catch (cause) {
      const message = errorMessage(cause);
      setError(message); reportRequestFailure(message);
      void recordClientError(message, 'admission_preflight');
    }
    finally { setBusy(false); }
  }

  async function start() {
    if (guest) { setConfirmStart(false); setGuestSessionCard(true); return; }
    if (submittingStart.current || !config || !pendingStrategyIds.length) return;
    submittingStart.current = true;
    stopAfterStart.current = false;
    setStoppingStartingSession(false);
    // On click, replace Start with the green pulse before any backend work.
    setAdmittingSession(true);
    setExpanded(true);
    window.localStorage.setItem(`sigma.sessionsPane:${path}`, 'true');
    setBusy(true); setError('');
    try {
      idempotencyKey.current ??= crypto.randomUUID();
      selectedSessionId.current = '';
      const next = mockResearch
        ? await post<ResearchSession>('research-sessions/mock', { path, strategy_id: pendingStrategyIds[0], expected_project_id: projectId, idempotency_key: idempotencyKey.current, continue_using_saved_type_settings: continueWithSavedType.current })
        : await post<ResearchSession>('research-sessions/start', { path, strategy_id: pendingStrategyIds[0], strategy_ids: pendingStrategyIds, expected_project_id: projectId, expected_binding: config.binding, expected_limits: limits, idempotency_key: idempotencyKey.current, browser_presence_required: true, continue_using_saved_type_settings: continueWithSavedType.current });
      idempotencyKey.current = null;
      setConfirmStart(false); selectedSessionId.current = next.id;
      // Start can be stopped before the first server response. Its identifier
      // exists now, so honor that intent before displaying the saved row.
      const accepted = stopAfterStart.current
        ? await post<ResearchSession>(`research-sessions/${next.id}/control`, { path, action: 'stop', request_only: true }, undefined, true)
        : next;
      lastAnnouncement.current = `${accepted.id}:${accepted.status}:${accepted.current_action}`;
      // The admission response is already a complete session snapshot. Display it
      // without blocking the controls on reloading every session and
      // rebuilding Current Understanding; reconcile the history asynchronously.
      const initialSnapshot = sessionForDisplay(accepted);
      if (initialSnapshot) setSessions(current => [initialSnapshot, ...current.filter(item => item.id !== next.id)]);
      void load(next.id).catch(reportReadFailure);
      if (next.research_method_sources?.advisory) {
        setAnnouncement(next.research_method_sources.advisory);
      }
      if (accepted.status === 'running' || accepted.status === 'queued') onRevealNewSession();
      revealSession(next.id, accepted.status === 'running' || accepted.status === 'queued');
    } catch (cause) {
      // Revert the speculative pulse and unlock Play immediately. A full
      // history reconciliation is not part of the failed admission's UI path.
      setConfirmStart(false);
      setAdmittingSession(false);
      void load().catch(reportReadFailure);
      const message = errorMessage(cause);
      setError(message);
      if (cause instanceof Error && (cause as Error & { diagnostic_recorded?: boolean }).diagnostic_recorded === true) {
        setDiagnosticStatus('Admission error recorded in Project diagnostics.');
        void reloadDiagnostics().catch(() => {});
      } else {
        void recordClientError(message, 'admission');
      }
    }
    finally { submittingStart.current = false; stopAfterStart.current = false; setStoppingStartingSession(false); setAdmittingSession(false); setBusy(false); }
  }

  async function control(action: 'pause' | 'resume' | 'stop', target: ResearchSession | null = null) {
    if (!target) return;
    if (action === 'stop' || action === 'pause')
      window.dispatchEvent(new CustomEvent('sigma-run-stop-intent', { detail: { kind: 'session', id: target.id } }));
    if (action === 'stop' && pendingSessionAction?.id === target.id && pendingSessionAction.action === 'resume') {
      // The user's Stop intent wins immediately. Wait to send it until
      // the in-flight Resume has an execution identity to stop.
      stopAfterResume.current.add(target.id);
      window.dispatchEvent(new CustomEvent('sigma-run-stop-intent', { detail: { kind: 'session', id: target.id } }));
      setPendingSessionAction({ id: target.id, action: 'stop' });
      if (resumeApprovalResolver.current) answerResumeAuthorization(false);
      return;
    }
    setPendingSessionAction({ id: target.id, action });
    setBusy(true); setError('');
    setSessionControlFailures(current => {
      if (!current[target.id]) return current;
      const next = { ...current };
      delete next[target.id];
      return next;
    });
    try {
      let recoveryAction: 'pause' | 'resume' | 'stop' | 'repair' = action;
      let authorizedCalls = 0;
      let releaseRetries = 0;
      for (;;) {
        try {
          // The backend's preflight authorization responses are handled by
          // the two confirmations below, not global Request Failed toasts.
          // Unexpected errors are still reported by the enclosing catch.
          const accepted = await post<ResearchSession>(`research-sessions/${target.id}/control`, { path, action: recoveryAction, additional_calls: authorizedCalls, browser_presence_required: action === "resume", request_only: action === 'stop' || action === 'pause' }, undefined, true);
          // A successful control response contains the authoritative new status.
          // Do not keep the button busy for an unrelated whole-project reload.
          const resolved = action === 'resume' && stopAfterResume.current.delete(target.id)
            ? await post<ResearchSession>(`research-sessions/${target.id}/control`, { path, action: 'stop', request_only: true }, undefined, true)
            : accepted;
          const acknowledged = sessionForDisplay(resolved);
          if (acknowledged) setSessions(current => current.map(item => item.id === target.id ? acknowledged : item));
          void load(target.id).catch(reportReadFailure);
          break;
        } catch (cause) {
          const message = errorMessage(cause);
          // Fast Stop acknowledges a durable fence before the old worker
          // finishes cleanup. Avoid surfacing a transient Resume race as a
          // failure or dispatching a replacement while that lock is held.
          if (action === 'resume' && message.includes('Session execution is still releasing resources')
            && releaseRetries++ < 12) {
            await new Promise<void>(resolve => window.setTimeout(resolve, 250));
            continue;
          }
          const attemptShortfall = message.match(/Resume with exactly (\d+) explicitly authorized additional attempts/);
          if (action === 'resume' && authorizedCalls === 0 && attemptShortfall) {
            const count = Number(attemptShortfall[1]);
            if (count < 1 || count > 12) throw cause;
            if (await requestResumeAuthorization({ kind: 'attempts', count, sessionNumber: target.session_number })) {
              authorizedCalls = count;
              continue;
            }
            setAnnouncement('Resume cancelled. Research and spending limits were preserved.');
            return;
          }
          const durationShortfall = message.match(/Resume requires explicit approval to extend the session duration for up to (\d+) additional minutes/);
          if (action === 'resume' && recoveryAction === 'resume' && durationShortfall) {
            const minutes = Number(durationShortfall[1]);
            if (!Number.isSafeInteger(minutes) || minutes < 1) throw cause;
            if (await requestResumeAuthorization({ kind: 'duration', count: minutes, sessionNumber: target.session_number })) {
              recoveryAction = 'repair';
              continue;
            }
            setAnnouncement('Resume cancelled. Research and duration limits were preserved.');
            return;
          }
          throw cause;
        }
      }
      if (action === 'resume') {
        // A new accepted Resume deserves a fresh saved-status notice if it
        // quickly stops again, even when the previous notice was dismissed.
        const key = sessionNoticeKey(target);
        setDismissedNoticeKeys(current => {
          if (!current.has(key)) return current;
          const next = new Set(current);
          next.delete(key);
          try { window.localStorage.setItem(noticeStorageKey, JSON.stringify([...next])); } catch { /* Presentation only. */ }
          return next;
        });
      }
    }
    catch (cause) {
      if (action === 'stop' || action === 'pause')
        window.dispatchEvent(new CustomEvent('sigma-run-stop-intent', { detail: { kind: 'session', id: target.id, clear: true } }));
      if (action === 'resume' && stopAfterResume.current.delete(target.id)) {
        // Resume may have been admitted before a network error reached the
        // browser. Stop is idempotent even if it never started.
        try {
          const stopped = await post<ResearchSession>(`research-sessions/${target.id}/control`, { path, action: 'stop', request_only: true }, undefined, true);
          const acknowledged = sessionForDisplay(stopped);
          if (acknowledged) setSessions(current => current.map(item => item.id === target.id ? acknowledged : item));
          void load(target.id).catch(reportReadFailure);
          return;
        } catch { /* Show the original failure and reconcile the saved state. */ }
      }
      // Restore the Resume control without waiting on full history hydration.
      setPendingSessionAction(null);
      void load(target.id).catch(reportReadFailure);
      const message = errorMessage(cause);
      setSessionControlFailures(current => ({
        ...current,
        [target.id]: { message, serial: ++sessionControlSerial.current, dismissed: false },
      }));
      void recordClientError(message, 'session_control', target.id);
    }
    finally { stopAfterResume.current.delete(target.id); setPendingSessionAction(null); setBusy(false); }
  }

  const interventionSaved = useCallback(async (sessionId: string) => {
    await load(sessionId);
    setAnnouncement('Human feedback added for a later agent step. No provider call was made.');
  }, [load]);

  function requestResume(target: ResearchSession, playButton: HTMLButtonElement) {
    // Anchor any explicit authorization prompt to the Play button that initiated it.
    resumePlayAnchor.current = playButton;
    void control('resume', target);
  }

  function revealSession(id: string, collapsePrevious = false, focusOutcome = false) {
    onSectionOpened();
    setExpanded(true);
    window.localStorage.setItem(`sigma.sessionsPane:${path}`, 'true');
    setExpandedSessionIds(current => collapsePrevious ? new Set([id]) : new Set(current).add(id));
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const row = document.querySelector<HTMLElement>(`[data-session-id="${CSS.escape(id)}"]`);
      if (row) {
        const heading = row.querySelector<HTMLElement>('.session-row-disclosure');
        // A Q/A session citation points into the saved Outcome, not the project
        // description or merely the session's collapsed header.
        const targetNode = (focusOutcome ? row.querySelector<HTMLElement>('.session-outcome') : null) ?? heading ?? row;
        // Scroll only the workspace reading pane; scrollIntoView can move the
        // outer viewport horizontally when the session content is wider.
        const viewport = row.closest<HTMLElement>('.workspace-content');
        if (viewport) {
          const target = targetNode.getBoundingClientRect();
          const frame = viewport.getBoundingClientRect();
          viewport.scrollTo({
            top: viewport.scrollTop + target.top - frame.top - (focusOutcome ? 20 : (viewport.clientHeight - target.height) / 2),
            behavior: 'smooth',
          });
        } else {
          targetNode.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' });
        }
        row.classList.add('citation-highlight');
        window.setTimeout(() => row.classList.remove('citation-highlight'), 2400);
      }
    }));
  }

  function revealEvidence(source: EvidencePointer) {
    if (source.project_id !== projectId || !source.available) return;
    revealSession(source.session_id);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const row = document.querySelector<HTMLElement>(`[data-session-id="${CSS.escape(source.session_id)}"]`);
      const evidence = row?.querySelector<HTMLDetailsElement>('.outcome-evidence-subsection');
      if (evidence) evidence.open = true;
      const artifact = document.getElementById(`research-artifact-${source.session_id}-${source.artifact_id}`);
      if (artifact) {
        const disclosure = artifact.querySelector<HTMLDetailsElement>('details');
        if (disclosure) disclosure.open = true;
        artifact.tabIndex = -1;
        artifact.focus({ preventScroll: true });
        artifact.scrollIntoView({ block: 'center', behavior: 'smooth' });
        setAnnouncement(`Opened evidence from Session ${source.session_number}.`);
      } else if (row) {
        row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        setAnnouncement('The owning session is open; inspect its evidence.');
      }
    }));
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('reveal_understanding') === '1') {
      requestAnimationFrame(() => requestAnimationFrame(() => {
        const understanding = document.querySelector<HTMLElement>('.current-understanding');
        if (understanding instanceof HTMLDetailsElement) understanding.open = true;
        if (understanding) { understanding.scrollIntoView({ block: 'center', behavior: 'smooth' }); understanding.classList.add('citation-highlight'); window.setTimeout(() => understanding.classList.remove('citation-highlight'), 2400); }
      }));
    }
    const sessionId = params.get('reveal_session');
    const artifactId = params.get('reveal_artifact');
    if (!sessionId || !artifactId || !expandedSessionIds.has(sessionId)) return;
    if (!advancedOutcomeDetails) {
      void onEnableAdvancedOutcome().catch(() => setAnnouncement('The owning session is open. Enable Advanced Outcome to inspect this artifact.'));
      return;
    }
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const row = document.querySelector<HTMLElement>(`[data-session-id="${CSS.escape(sessionId)}"]`);
      const evidence = row?.querySelector<HTMLDetailsElement>('.outcome-evidence-subsection');
      if (evidence) evidence.open = true;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const artifact = document.getElementById(`research-artifact-${sessionId}-${artifactId}`);
      if (!artifact) return;
      const disclosure = artifact.querySelector<HTMLDetailsElement>('details');
      if (disclosure) disclosure.open = true;
      artifact.tabIndex = -1; artifact.focus({ preventScroll: true }); artifact.scrollIntoView({ block: 'center', behavior: 'smooth' });
      artifact.classList.add('citation-highlight'); window.setTimeout(() => artifact.classList.remove('citation-highlight'), 2400);
    }));
    }));
  }, [advancedOutcomeDetails, expandedSessionIds, onEnableAdvancedOutcome, sessions]);

  async function removeSession(target: ResearchSession) {
    setBusy(true); setError('');
    try {
      const result = await removeResearchSession(path, target.id, target.updated_at);
      setConfirmRemoveId('');
      setExpandedSessionIds(current => { const next = new Set(current); next.delete(target.id); return next; });
      if (selectedSessionId.current === target.id) selectedSessionId.current = '';
      await load();
      setAnnouncement(`Session ${result.session_number} removed. Strategy and other sessions were kept.`);
    } catch (cause) {
      const message = errorMessage(cause);
      setError(message); reportRequestFailure(message);
      void recordClientError(message, 'session_delete');
    }
    finally { setBusy(false); }
  }

  const activeSessionCount = sessions.filter(session => session.status === 'queued' || session.status === 'running').length;
  const projectAtCapacity = activeSessionCount >= maxConcurrentSessions;
  const playLabel = projectAtCapacity
    ? `Maximum concurrent sessions reached (${activeSessionCount}/${maxConcurrentSessions})`
    : 'Start a new research session';
  const requiresSponsoredCost = cloud?.target === 'hosted'
    || (cloud?.target === 'local' && cloud.funding.selectedConnection === 'sponsored');
  const play = useCallback(() => {
    if (guest) { setGuestSessionCard(true); return; }
    if (busy || readError || projectAtCapacity) return;
    setExpanded(true); window.localStorage.setItem(`sigma.sessionsPane:${path}`, 'true');
    if (!eligible.length) return;
    if (missingType) { setConfirmMissingType(true); return; }
    setConfirmStart(false);
    void begin();
  }, [busy, eligible, readError, path, projectAtCapacity, missingType, guest]);
  const stop = useCallback(() => {
    if (runningSession && !busy && !readError) void control('stop', runningSession);
  }, [runningSession, busy, readError]);
  const effectiveDurationMinutes = limits?.session_duration_minutes ?? null;
  useEffect(() => {
    onControlsChange({
      play, stop, confirming: confirmStart, starting: admittingSession, start: () => void start(), cancel: () => setConfirmStart(false), nextSessionNumber: Math.max(0, ...sessions.map(item => item.session_number)) + 1,
      confirmationSummary: limits ? `${limits.research_rounds} ${limits.research_rounds === 1 ? "round" : "rounds"} × ${limits.turns_per_round ?? 3} paired ${limits.turns_per_round === 1 ? "turn" : "turns"} × 2 agents × ${confirmStart ? pendingStrategyIds.length : eligible.length} enabled ${(confirmStart ? pendingStrategyIds.length : eligible.length) === 1 ? "strategy" : "strategies"} = ${limits.research_rounds * (limits.turns_per_round ?? 3) * 2 * (confirmStart ? pendingStrategyIds.length : eligible.length)} maximum agent calls` : undefined,
      // Match the backend's queued/running slot count. The server remains
      // authoritative when another browser starts a session concurrently.
      playDisabled: busy || !!readError || confirmStart || !eligible.length || projectAtCapacity,
      stopDisabled: busy || !!readError || !runningSession,
      playLabel,
    });
  }, [busy, admittingSession, confirmStart, eligible.length, effectiveDurationMinutes, limits, onControlsChange, stop, play, playLabel, projectAtCapacity, readError, runningSession, sessions, sponsoredSession, pendingStrategyIds.length]);

  const orderedSessions = [...sessions].sort((left, right) => right.session_number - left.session_number);

  useEffect(() => {
    const revealId = initialRevealSessionId.current;
    if (!revealId) return;
    initialRevealSessionId.current = null;
    if (activeSession?.id === revealId) onRevealNewSession();
    revealSession(revealId, true, new URLSearchParams(window.location.search).get('reveal_session') === revealId);
  }, [activeSession?.id, onRevealNewSession, sessions.length]);

  const stoppingSessionId = pendingSessionAction?.action === 'stop' || pendingSessionAction?.action === 'pause'
    ? pendingSessionAction.id : null;
  const runningCount = activeSessionCount -
    (sessions.some(item => item.id === stoppingSessionId && ['queued', 'running'].includes(item.status)) ? 1 : 0);
  const pendingSessionName = 'Session';
  const pendingSessionMetadata = formatRunAttribution({
    kind: 'session', creator: viewerEmail, model: config?.model, thinking: config?.reasoning_effort,
  });
  return <section className={`sessions-pane workspace-pane${expanded ? '' : ' is-collapsed'}`} aria-labelledby="sessions-heading">
    <ResumeAuthorizationDialog request={resumeAuthorization} anchor={resumePlayAnchor.current} onAuthorize={() => answerResumeAuthorization(true)} onCancel={() => answerResumeAuthorization(false)}/>
    <dialog ref={missingTypeDialog} className="project-type-warning-dialog" role="alertdialog" aria-labelledby="missing-type-heading" onCancel={event => { event.preventDefault(); if (!busy) setConfirmMissingType(false); }}>
      <div className="sigma-dialog-heading"><h2 id="missing-type-heading">Project type unavailable</h2><DialogDismissButton label="Cancel project type selection" disabled={busy} onClick={() => { missingTypeDialog.current?.close(); setConfirmMissingType(false); }}/></div>
      {safeSavedTypeSettings
        ? <p>This project refers to “{savedTypeName}”, which is no longer available. You can continue with its complete existing settings or choose a replacement.</p>
        : <p>This project refers to “{savedTypeName}”, which is no longer available, and it does not have a complete type snapshot. Choose a replacement before starting a new research session.</p>}
      <div className="project-type-warning-actions">
        {safeSavedTypeSettings && <button type="button" autoFocus disabled={busy} onClick={() => { missingTypeDialog.current?.close(); setConfirmMissingType(false); setConfirmStart(false); void begin(undefined, true); }}>Continue with existing settings</button>}
        <button type="button" autoFocus={!safeSavedTypeSettings} disabled={busy} onClick={() => { missingTypeDialog.current?.close(); setConfirmMissingType(false); onChooseReplacement(); }}>Choose a replacement</button>
        </div>
    </dialog>
    <header className="workspace-pane-heading sessions-pane-heading">
      <h2 id="sessions-heading" tabIndex={-1}><button type="button" className="workspace-section-disclosure" data-tooltip={`${expanded ? 'Collapse' : 'Expand'} Sessions section`} aria-expanded={expanded} aria-controls="sessions-pane-content" onClick={() => { if (!expanded) onSectionOpened(); setExpanded(value => { window.localStorage.setItem(`sigma.sessionsPane:${path}`, String(!value)); return !value; }); }}><DisclosureChevron expanded={expanded}/>Sessions</button></h2>
      <div className="sessions-heading-actions strategy-heading-actions">
        {sessionControls.confirming ? sessionControls.starting
          ? null // The pending Session row owns the one visible green pulse.
          : <>
          <button type="button" className="text-view-link session-start-link" disabled={controlsDisabled} onClick={sessionControls.start}>Start Session</button>
          <button type="button" className="text-view-link session-start-link" disabled={controlsDisabled} onClick={sessionControls.cancel}>Cancel</button>
        </> : <button ref={playButtonRef} type="button" className="text-view-link sessions-new-action sigma-heading-icon-action" disabled={controlsDisabled || (!guest && sessionControls.playDisabled)} aria-label="New session" data-tooltip="New session" onClick={sessionControls.play}><CirclePlusIcon/></button>}
      </div>
      <p className="section-count">{sessions.length} {sessions.length === 1 ? 'session' : 'sessions'}, {runningCount} running{stoppingSessionId ? ' · 1 stopping' : ''}{admittingSession ? stoppingStartingSession ? ' · 1 stopping' : ' · 1 starting' : ''}</p>
    </header>

    {guest && guestSessionCard && <GuestFeatureCard title="Research sessions"
      message="SIGMA coordinates Investigator and Skeptic agents to investigate strategies, challenge findings, and record evidence."
      onClose={() => setGuestSessionCard(false)}/>}
    <div id="sessions-pane-content" hidden={!expanded}>
    {invalidSessionCount > 0 && <p className="error" role="alert">{invalidSessionCount} session {invalidSessionCount === 1 ? 'record has' : 'records have'} an invalid or missing identifier and cannot be displayed. The data remains in the project export.</p>}
    {currentUnderstanding && <ResearchDisplayBoundary key={projectId} label="Current Understanding"><CurrentUnderstandingView state={currentUnderstanding} path={path} projectId={projectId} nextOrdinal={nextStrategyOrdinal} guest={guest} onInferred={onInferredStrategy} onEvidence={revealEvidence} onSession={revealSession}/></ResearchDisplayBoundary>}
    <div className="session-table">
      {(sessions.length || admittingSession) ? <ol className="session-list" aria-label="Research sessions">
        {admittingSession && <li className="session-row session-admission-pending" aria-label="Session starting" role="status" aria-live="polite">
          <div className="session-row-heading">
            <div className="session-summary">
              <div className="session-title-line">
                <span className="session-row-disclosure"><DisclosureChevron expanded={false}/><span className="session-row-title">{pendingSessionName}</span></span>
                <div className="session-heading-actions" aria-label="Session actions">
                  <button type="button" className="text-view-link text-view-icon workspace-icon-button process-control session-mini-process-control" aria-label="Stop session" data-tooltip="Stop session" disabled={stoppingStartingSession} onClick={() => { stopAfterStart.current = true; setStoppingStartingSession(true); }}><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5h10v10H5z"/></svg></button>
                </div>
              </div>
              <span className={`session-status session-${stoppingStartingSession ? 'stopped' : 'running'}`} aria-label={stoppingStartingSession ? 'Session stopping' : 'Session starting'}>{stoppingStartingSession ? 'stopping' : <>starting<i aria-hidden="true"/></>}</span>
              <small className="session-run-metadata">{pendingSessionMetadata || 'Research session'} · {stoppingStartingSession ? 'Stopping' : 'Starting'}</small>
              <small className="session-progress-inline">{pendingStrategyIds.length} {pendingStrategyIds.length === 1 ? 'strategy' : 'strategies'} selected · 0 findings recorded</small>
            </div>
          </div>
        </li>}
        {orderedSessions.map(item => {
          const pendingAction = pendingSessionAction?.id === item.id ? pendingSessionAction.action : null;
          const statusLabel = pendingAction === 'resume' ? 'resuming'
            : pendingAction === 'stop' || pendingAction === 'pause' ? 'stopping'
            : item.status === 'paused' ? 'stopped' : item.status;
          const currentAction = pendingAction === 'resume' ? 'Resuming session…'
            : pendingAction === 'stop' || pendingAction === 'pause' ? 'Stopping session…'
            : (readError && activeSession?.id === item.id ? `State unknown · ${item.current_action}` : item.current_action)
              .replace(/\bpaused\b/gi, 'stopped').replace(/\bpausing\b/gi, 'stopping').replace(/\bpause\b/gi, 'stop');
          const sessionExpanded = expandedSessionIds.has(item.id);
          const creator = artifactAuthors?.[item.id];
          const attributionEnforced = Boolean(viewerEmail && projectOwnerEmail);
          const isOwner = attributionEnforced && viewerEmail === projectOwnerEmail;
          const canControl = !attributionEnforced || (creator ? creator === viewerEmail : isOwner);
          const canRemove = canControl || (isOwner && ['completed', 'ended'].includes(item.status));
          return <SessionRenderBoundary key={item.id} sessionId={item.id} sessionNumber={item.session_number} revision={item.updated_at}><li className="session-row" data-session-id={item.id}>
            <div className="session-row-heading">
              <div className="session-summary">
                <div className="session-title-line"><button type="button" className="session-row-disclosure" aria-expanded={sessionExpanded} aria-controls={`session-content-${item.id}`} onClick={() => setExpandedSessionIds(current => { const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next; })}><DisclosureChevron expanded={sessionExpanded}/><span className="session-row-title">Session {item.session_number}</span></button>
                <div className="session-heading-actions" aria-label={`Session ${item.session_number} actions`}>
                  {!guest && canControl && sessionOffersResume(item) && !(pendingSessionAction?.id === item.id && pendingSessionAction.action === 'resume') && <span className="session-resume-tooltip" data-tooltip={projectAtCapacity ? "Only one session at a time" : "Resume this session"}><button type="button" className="text-view-link text-view-icon workspace-icon-button process-control session-mini-process-control" aria-label={`Resume Session ${item.session_number}`} disabled={busy || !!readError || projectAtCapacity} onClick={event => requestResume(item, event.currentTarget)}><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M6 3.8v12.4L16 10 6 3.8Z"/></svg></button></span>}
                  {!guest && canControl && (pendingAction === 'resume' || pendingAction === 'stop' || pendingAction === 'pause' || (!pendingAction && ['queued', 'running'].includes(item.status))) && <button type="button" className="text-view-link text-view-icon workspace-icon-button process-control session-mini-process-control" aria-label={pendingAction === 'stop' || pendingAction === 'pause' ? `Stopping Session ${item.session_number}` : `Stop Session ${item.session_number}`} data-tooltip={`Stop Session ${item.session_number}`} disabled={pendingAction === 'stop' || pendingAction === 'pause' || (busy && pendingAction !== 'resume')} onClick={() => void control('stop', item)}><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5h10v10H5z"/></svg></button>}
                  {!guest && <SessionLogButton sessionId={item.id} sessionNumber={item.session_number} path={path}/>}
                  {!guest && canRemove && !pendingAction && !['queued', 'running'].includes(item.status) && <button type="button" className="text-view-link text-view-icon workspace-icon-button session-remove-link" aria-label={`Remove Session ${item.session_number}`} data-tooltip={`Remove Session ${item.session_number}`} disabled={busy} onClick={() => setConfirmRemoveId(item.id)}><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" aria-hidden="true"><path d="M8 8 16 16M16 8 8 16"/></svg></button>}
                  {!guest && canRemove && !pendingAction && !['queued', 'running'].includes(item.status) && confirmRemoveId === item.id && <div className="session-remove-actions"><div className="research-stop-confirm" role="group" aria-label={`Confirm remove Session ${item.session_number}`}><p>{['queued', 'running', 'paused'].includes(item.status) ? `Stop and remove session ${item.session_number}?` : `Remove session ${item.session_number} and its saved work?`}</p><div className="session-remove-confirm-actions"><button type="button" className="text-view-link" data-tooltip={`Confirm removal of Session ${item.session_number}`} disabled={busy} onClick={() => void removeSession(item)}>Confirm</button><button type="button" className="text-view-link" disabled={busy} onClick={() => setConfirmRemoveId('')}>Cancel</button></div></div></div>}
                </div></div>
                <span className={`session-status session-${pendingAction === 'resume' ? 'running' : pendingAction ? 'stopped' : statusLabel}`} aria-label={`Lifecycle status: ${statusLabel}`} data-tooltip={pendingAction ? statusLabel : formatRunAttribution({ kind: 'session', number: item.session_number, creator, model: item.model, thinking: item.reasoning_effort, mode: 'hover' })}>{(pendingAction === 'stop' || pendingAction === 'pause') ? statusLabel : statusLabel === 'running' || statusLabel === 'resuming' || statusLabel === 'stopped' ? <>{statusLabel}<i aria-hidden="true"/></> : <><i aria-hidden="true"/>{statusLabel}</>}</span>
                {sessionControlFailures[item.id]
                  ? (!sessionControlFailures[item.id].dismissed && <SessionNotice key={`${item.id}:control:${sessionControlFailures[item.id].serial}`}
                      number={item.session_number}
                      title={providerInterruptionCopy(sessionControlFailures[item.id].message, item.cloud_sponsored === true || sponsoredSession)?.title ?? 'Resume could not start'}
                      kind="stopped-session-guidance"
                      ariaLabel={`Session ${item.session_number} Resume feedback`}
                      onDismiss={() => setSessionControlFailures(current => ({
                        ...current, [item.id]: { ...current[item.id], dismissed: true },
                      }))}>
                      <p>{friendlyProviderError(sessionControlFailures[item.id].message, item.cloud_sponsored === true || sponsoredSession)}</p>
                    </SessionNotice>)
                  : (['paused', 'stopped', 'failed'].includes(item.status) || (item.provider_usage_limited && item.status === 'ended'))
                    && <SessionRenderBoundary key={`${item.id}:notice:${sessionNoticeKey(item)}`} sessionId={item.id} sessionNumber={item.session_number} revision={item.updated_at} fallback={<div role="alert" className="session-render-error">Session {item.session_number} status notice could not be displayed; its saved record remains in project export.</div>}><StoppedSessionNotice session={item} dismissed={dismissedNoticeKeys.has(sessionNoticeKey(item))} onDismiss={() => dismissSessionNotice(sessionNoticeKey(item))}/></SessionRenderBoundary>}
                <small className="session-run-metadata">{dateLabel(item.created_at)}{typeof item.elapsed_seconds === 'number' ? ` · Elapsed ${formatDuration(item.elapsed_seconds)}` : ''} · {formatRunAttribution({ kind: 'session', creator, model: item.model, thinking: item.reasoning_effort })}{pendingAction ? ` · ${statusLabel}` : (['ended', 'completed', 'failed'].includes(item.status)) ? ` · Outcome: ${outcomeDisplayLabel(item)}` : ''}</small>
                <small className="session-progress-inline">{pendingAction === 'stop' || pendingAction === 'pause'
                  ? 'Stopping · findings remain available'
                  : <>Round {item.scheduler_version === 2 ? (item.research_round ?? 0) : item.cycle} of {item.scheduler_version === 2 ? (item.research_round_limit ?? 3) : (item.cycle_limit ?? 3)}{item.scheduler_version === 2 && item.paired_turn_in_round ? ` · Turn ${item.paired_turn_in_round} of ${item.turns_per_round}` : ''} · {item.scheduler_version === 2 ? `${item.protocol_completed_calls ?? 0}/${item.protocol_target_calls ?? item.call_limit} completed agent calls` : `${item.calls_used}/${item.call_limit} agent calls`}{parallelSessionActivity(item) ? ` · ${parallelSessionActivity(item)}` : ''} · {item.artifacts.length} findings recorded · {sessionEstimatedCostLabel(item)}</>}</small>
                {!pendingAction && strategyLiveStatusLines(item).length > 0 && <ul className="session-strategy-live-status" aria-label={`Session ${item.session_number} strategy status`}>{strategyLiveStatusLines(item).slice(0, 5).map(line => <li key={line.id}><strong>{line.label}:</strong> {line.detail}</li>)}</ul>}
                {!pendingAction && strategyLiveStatusLines(item).length > 5 && <small className="session-progress-inline">and {strategyLiveStatusLines(item).length - 5} others</small>}
              </div>
            </div>
            {sessionExpanded ? <ResearchDisplayBoundary label={`Session ${item.session_number}`}><ResearchSessionContents path={path} session={{ ...item, current_action: currentAction }} expanded={sessionExpanded} guest={guest} advancedOutcomeDetails={advancedOutcomeDetails} busy={busy || !canControl} onEnableAdvancedOutcome={onEnableAdvancedOutcome} onViewStrategy={onViewStrategy} onViewPriorSession={revealSession} onForkFromFindings={onForkFromFindings} onInterventionSaved={interventionSaved} dismissedStatusNotice={Boolean(sessionControlFailures[item.id]) || dismissedNoticeKeys.has(sessionNoticeKey(item))} onDismissStatusNotice={() => dismissSessionNotice(sessionNoticeKey(item))}/></ResearchDisplayBoundary> : <div id={`session-content-${item.id}`} hidden/>}
          </li></SessionRenderBoundary>;
        })}
      </ol> : !confirmStart && <p className="sessions-empty">No sessions yet. Use <span className="sr-only">Play</span><svg className="sessions-empty-play-icon" viewBox="0 0 20 20" aria-hidden="true"><path d="M6 3.8v12.4L16 10 6 3.8Z"/></svg> in Strategies to start one.</p>}
    </div>
    <ProjectDiagnosticsPanel diagnostics={projectDiagnostics} status={diagnosticStatus}/>
    {readError && <p className="error" role="alert">Unable to confirm session state. Last confirmed information is shown: {readError}</p>}
    {error && <div className="error sigma-dismissible-error" role="alert">
      <span>{error}</span>
      <SessionNoticeDismiss number={0} label="Dismiss research error" onDismiss={() => setError('')}/>
    </div>}
    </div>
    <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
  </section>;
}

type TextFormat = 'plain' | 'markdown';
type TextDisplay = 'plain' | 'rendered';
type TextVersion = { body: string; kind: 'authored' | 'ai_derived'; current: boolean; source_digest: string; source_format: TextFormat; created_at: string; provenance: { provider: string; model: string; reasoning_effort: string | null } | null; warnings: string[] };
type TextRepresentations = { source_format: TextFormat; source_digest: string; plain: TextVersion | null; markdown: TextVersion | null };

async function post<T>(route: string, body: object = {}, signal?: AbortSignal, handleErrorLocally = false): Promise<T> {
  const response = await fetch(`/api/projects/${route}`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
      ...(handleErrorLocally ? { 'X-Sigma-Error-Handled': 'true' } : {}),
    },
    body: JSON.stringify(body), signal,
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error ?? JSON.stringify(data.detail) ?? 'Request failed') as Error & { diagnostic_recorded?: boolean };
    error.diagnostic_recorded = data.diagnostic_recorded === true;
    throw error;
  }
  return data;
}
const errorMessage = (error: unknown) => error instanceof Error ? error.message : String(error);
function CopyToClipboardButton({ name, copied, disabled = false, onCopy }: { name: string; copied: boolean; disabled?: boolean; onCopy: () => void }) {
  return <button type="button" className="text-view-link text-view-icon workspace-icon-button text-copy-button" aria-label={copied ? `Copied ${name} to clipboard` : `Copy ${name}`} data-tooltip={copied ? 'Copied' : `Copy ${name}`} disabled={disabled} onClick={onCopy}>{copied ? <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 4 4L19 6"/></svg> : <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>}</button>;
}
function SavedPaperTitle({ title, itemLabel, expanded, controls, onToggle, copyName, copied, onCopy, beforeCopy, actions, copyInTitle = true, inlineTitleActions = false, badge }: { title: string; itemLabel: string; expanded: boolean; controls: string; onToggle: () => void; copyName: string; copied: boolean; onCopy: () => void; beforeCopy?: ReactNode; actions?: ReactNode; copyInTitle?: boolean; inlineTitleActions?: boolean; badge?: ReactNode }) {
  const titleLabel = `${expanded ? 'Collapse' : 'Expand'} ${itemLabel}: ${title}`;
  const choose = () => onToggle();
  const onKey = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      choose();
    }
  };
  const disclosure = <button type="button" className="saved-paper-expand" aria-label={titleLabel} aria-expanded={expanded} aria-controls={controls} onClick={choose}><DisclosureChevron expanded={expanded}/></button>;
  const titleButton = <span className="saved-paper-title-toggle" role="button" tabIndex={0} aria-label={titleLabel} aria-expanded={expanded} aria-controls={controls} onClick={choose} onKeyDown={onKey}>{title}</span>;
  if (inlineTitleActions) return <div className="saved-paper-title-line">{disclosure}<h4 className="saved-paper-title">{badge}{titleButton}<span className="saved-paper-title-tools">{beforeCopy}{copyInTitle && <CopyToClipboardButton name={copyName} copied={copied} onCopy={onCopy}/>}{actions}</span></h4></div>;
  return <div className="saved-paper-title-line">
    {disclosure}
    <div className="saved-paper-title-content">
      <div className="saved-paper-title-first-line">
        <h4 className="saved-paper-title">{badge}{titleButton}</h4>
        <span className="saved-paper-title-tools">{copyInTitle && <CopyToClipboardButton name={copyName} copied={copied} onCopy={onCopy}/>}{actions}</span>
      </div>
      {beforeCopy && <div className="saved-paper-second-line">{beforeCopy}</div>}
    </div>
  </div>;
}
async function sha256Text(value: string): Promise<string> {
  const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)));
  return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
}
const projectUrl = (path: string) => `/project?${new URLSearchParams({ path })}`;
// A recipient hint affects navigation only; it never grants access to projects.
const SHARED_INVITE_KEY = 'sigma.pendingSharedCollaboratorWelcome';
type SharedInviteIntent = { path: string; email: string; title?: string };
function getPendingSharedInvite(): SharedInviteIntent | null {
  try {
    const raw = window.sessionStorage.getItem(SHARED_INVITE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      const value = parsed as Record<string, unknown>;
      if (typeof value.path === 'string' && value.path.length > 0 && value.path.length <= 2048
        && typeof value.email === 'string' && value.email.length <= 254
        && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.email))
        return { path: value.path, email: value.email.toLowerCase(), title: typeof value.title === 'string' ? value.title.slice(0, 200) : undefined };
    }
    window.sessionStorage.removeItem(SHARED_INVITE_KEY);
  } catch { /* Storage may be unavailable in private browsing. */ }
  return null;
}
function clearPendingSharedInvite() {
  try { window.sessionStorage.removeItem(SHARED_INVITE_KEY); } catch { /* no-op */ }
}
const dateLabel = (value: string) => new Date(value).toLocaleString();
function formatDuration(totalSeconds: number) {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function useDocumentScrollLock(enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    const root = document.documentElement;
    const body = document.body;
    const previous = {
      rootOverflow: root.style.overflow,
      rootOverscroll: root.style.overscrollBehavior,
      bodyOverflow: body.style.overflow,
      bodyOverscroll: body.style.overscrollBehavior,
    };
    root.style.overflow = 'hidden';
    root.style.overscrollBehavior = 'none';
    body.style.overflow = 'hidden';
    body.style.overscrollBehavior = 'none';
    return () => {
      root.style.overflow = previous.rootOverflow;
      root.style.overscrollBehavior = previous.rootOverscroll;
      body.style.overflow = previous.bodyOverflow;
      body.style.overscrollBehavior = previous.bodyOverscroll;
    };
  }, [enabled]);
}

function ProjectExportDialog({ path, title, onCancel, open = true, demo = false }: { path: string; title: string; onCancel: () => void; open?: boolean; demo?: boolean }) {
  useDocumentScrollLock(open);
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const defaultStem = `sigma-${(title || 'project').replace(/[^a-z0-9_-]+/gi, '-').replace(/^-|-$/g, '') || 'project'}`;
  const [exportType, setExportType] = useState<'text' | 'html' | 'bundle'>(demo ? 'text' : 'bundle');
  const isReport = exportType === 'text' || exportType === 'html';
  const reportFormat = exportType === 'text' ? 'txt' : 'html';
  const [filename, setFilename] = useState(defaultStem);
  const [openInTab, setOpenInTab] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!dialog.current) return;
    if (open && !dialog.current.open) {
      dialog.current.showModal();
      input.current?.focus();
      input.current?.select();
    } else if (!open && dialog.current.open) dialog.current.close();
  }, [open]);
  function cancel() { if (!submitting.current) onCancel(); }
  async function exportFile(event: FormEvent) {
    event.preventDefault();
    if (submitting.current) return;
    const chosen = filename.trim();
    const stem = chosen.replace(/\.(json|txt|html|tex|pdf)$/i, '');
    if (!stem || stem === '.' || stem === '..' || /[\/\\<>:"|?*\x00-\x1f]/.test(stem)) {
      setError('Enter a filename stem without path separators or reserved characters.');
      return;
    }
    const extension = exportType === 'bundle' ? 'json' : reportFormat;
    const downloadName = `${stem}.${extension}`;
    const opened = openInTab && exportType !== 'bundle' ? window.open('about:blank', '_blank') : null;
    if (opened) opened.opener = null;
    submitting.current = true; setBusy(true); setError('');
    try {
      const route = demo ? '/api/cloud-demo/report' : (exportType === 'bundle' ? '/api/projects/export' : '/api/projects/export/report');
      const query = new URLSearchParams({ ...(!demo ? { path } : {}), ...(isReport ? { format: reportFormat } : {}) });
      const suffix = query.toString();
      const response = await fetch(`${route}${suffix ? `?${suffix}` : ''}`, { cache: 'no-store' });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.error ?? detail?.detail ?? 'Project export failed');
      }
      let content: string;
      content = await response.text();
      if (opened && !opened.closed) {
        if (exportType === 'html') opened.document.open(), opened.document.write(content), opened.document.close();
        else {
          opened.document.title = `${title} — ${exportType === 'bundle' ? 'Project file' : 'Research Report'}`;
          const pre = opened.document.createElement('pre');
          pre.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 ui-monospace,monospace;padding:1rem';
          pre.textContent = content;
          opened.document.body.replaceChildren(pre);
        }
      }
      const mimeType = exportType === 'bundle' ? 'application/json;charset=utf-8' : exportType === 'html' ? 'text/html;charset=utf-8' : 'text/plain;charset=utf-8';
      const url = URL.createObjectURL(new Blob([content], { type: mimeType }));
      const link = document.createElement('a');
      link.href = url; link.download = downloadName;
      document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      if (openInTab && exportType !== 'bundle' && (!opened || opened.closed)) {
        setError('The browser blocked or closed the new tab. The file was still downloaded.');
      } else onCancel();
    } catch (cause) { if (opened && !opened.closed) opened.close(); setError(errorMessage(cause)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className="project-settings-dialog export-project-dialog" aria-labelledby="export-project-heading"
    onCancel={event => { event.preventDefault(); cancel(); }}>
    <form onSubmit={exportFile}>
      <header className="settings-header">
        <h2 id="export-project-heading">{demo ? 'Export Demo Project' : 'Export Project'}</h2>
        <div className="settings-actions">
          <button type="submit" className="settings-submit" disabled={busy || !filename.trim()}>{busy ? 'Downloading…' : 'Download'}</button>
          <DialogDismissButton label="Cancel export" disabled={busy} onClick={() => cancel()}/>
        </div>
      </header>
      <div className="settings-body">
        <fieldset className="export-type-options" disabled={busy}>
          <legend>File type</legend>
          {!demo && <label><input type="radio" name="export-type" value="bundle" checked={exportType === 'bundle'} onChange={() => setExportType('bundle')}/> Importable project bundle</label>}
          <label><input type="radio" name="export-type" value="text" checked={exportType === 'text'} onChange={() => setExportType('text')}/> Text report</label>
          <label><input type="radio" name="export-type" value="html" checked={exportType === 'html'} onChange={() => setExportType('html')}/> HTML report</label>
        </fieldset>
        <label htmlFor="export-project-filename">Filename</label>
        <div className="export-filename-field"><input ref={input} id="export-project-filename" value={filename} maxLength={260} disabled={busy} spellCheck={false}
          onChange={event => { setFilename(event.target.value.replace(/[\/\\<>:"|?*\x00-\x1f]/g, '-').replace(/\.(json|txt|html|tex|pdf)$/i, '')); setError(''); }}/>
          <span aria-hidden="true">.{exportType === 'bundle' ? 'json' : reportFormat}</span></div>
        {exportType !== 'bundle' && <label className="export-open-tab"><input type="checkbox" checked={openInTab} disabled={busy} onChange={event => setOpenInTab(event.target.checked)}/> Open in browser tab</label>}
        {error && <p className="error" role="alert">{error}</p>}
      </div>
    </form>
  </dialog>;
}

type ProjectEmailMode = 'project' | 'pdf' | 'pdf_tex';
type ProjectEmailPreferences = { recipients: string; body: string; mode: ProjectEmailMode; paperId: string };
const defaultEmailPreferences: ProjectEmailPreferences = { recipients: '', body: '', mode: 'project', paperId: '' };
function projectEmailPreferences(projectId: string): ProjectEmailPreferences {
  try {
    const saved = JSON.parse(window.localStorage.getItem('sigma.projectEmail:' + projectId) ?? '{}');
    return {
      recipients: typeof saved.recipients === 'string' ? saved.recipients : '',
      body: typeof saved.body === 'string' ? saved.body : '',
      mode: saved.mode === 'pdf' || saved.mode === 'pdf_tex' ? saved.mode : 'project',
      paperId: typeof saved.paperId === 'string' ? saved.paperId : '',
    };
  } catch { return { ...defaultEmailPreferences }; }
}

function ProjectEmailDialog({ path, projectId, title, onCancel, onSent }: {
  path: string; projectId: string; title: string; onCancel: () => void; onSent: (count: number) => void;
}) {
  useDocumentScrollLock();
  const dialog = useRef<HTMLDialogElement>(null);
  const addressInput = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  // An ambiguous SMTP outcome must not be retried with a new request ID.
  // Reopening the dialog is an explicit new send.
  const requestId = useRef<string | null>(null);
  const lastSendDefinitelyFailed = useRef(false);
  function payloadChanged() {
    if (lastSendDefinitelyFailed.current) {
      // After a confirmed no-send, edited content is a new request. Ambiguous
      // deliveries retain the original UUID to prevent silent duplication.
      requestId.current = null;
      lastSendDefinitelyFailed.current = false;
    }
  }
  const initial = useRef(projectEmailPreferences(projectId)).current;
  const [recipients, setRecipients] = useState(initial.recipients);
  const [body, setBody] = useState(initial.body);
  const [mode, setMode] = useState<ProjectEmailMode>(initial.mode);
  const [paperId, setPaperId] = useState(initial.paperId);
  const [availablePapers, setAvailablePapers] = useState<PaperSummary[]>([]);
  const [paperLoad, setPaperLoad] = useState<'loading' | 'ready' | 'error'>('loading');
  const [paperRetry, setPaperRetry] = useState(0);
  const loaded = paperLoad === 'ready';
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const papersByDate = [...availablePapers].sort((a, b) =>
    b.created_at.localeCompare(a.created_at) || b.paper_version - a.paper_version);
  const selectedPaperId = papersByDate.some(paper => paper.paper_id === paperId)
    ? paperId : (papersByDate.find(paper => (paper.score?.total ?? 0) >= 50) ?? papersByDate[0])?.paper_id ?? '';
  const effectiveMode = loaded && !papersByDate.length ? 'project' : mode;
  useEffect(() => {
    if (!dialog.current?.open) {
      dialog.current?.showModal();
      addressInput.current?.focus();
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setPaperLoad('loading');
    void (async () => {
      try {
        const response = await fetch('/api/projects/papers?' + new URLSearchParams({ path }), { cache: 'no-store', signal: controller.signal });
        const detail = await response.json();
        if (!response.ok) throw new Error(detail.error ?? detail.detail ?? 'Could not list papers');
        if (!controller.signal.aborted) {
          setAvailablePapers((detail.papers as PaperSummary[] ?? []).filter(paper => paper.pdf_available));
          setPaperLoad('ready');
          setError('');
        }
      } catch (cause) {
        if (!controller.signal.aborted) {
          setPaperLoad('error');
          setError('Could not load generated papers: ' + errorMessage(cause));
        }
      }
    })();
    return () => controller.abort();
  }, [path, paperRetry]);
  useEffect(() => {
    if (!loaded) return;
    if (selectedPaperId !== paperId) { payloadChanged(); setPaperId(selectedPaperId); }
    if (effectiveMode !== mode) { payloadChanged(); setMode(effectiveMode); }
  }, [loaded, paperId, selectedPaperId, mode, effectiveMode]);
  useEffect(() => {
    window.localStorage.setItem('sigma.projectEmail:' + projectId,
      JSON.stringify({ recipients, body, mode, paperId }));
  }, [projectId, recipients, body, mode, paperId]);
  function cancel() { if (!submitting.current) onCancel(); }
  async function send(event: FormEvent) {
    event.preventDefault();
    if (submitting.current || (!loaded && effectiveMode !== 'project')) return;
    const addresses = recipients.trim();
    if (!addresses) { setError('Enter at least one recipient email address.'); addressInput.current?.focus(); return; }
    submitting.current = true; setBusy(true); setError('');
    try {
      if (requestId.current === null) requestId.current = crypto.randomUUID();
      const response = await fetch('/api/projects/email', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id: requestId.current, path, recipients: addresses, body, mode: effectiveMode, paper_id: effectiveMode === 'project' ? null : selectedPaperId }),
      });
      const detail = await response.json().catch(() => null);
      if (!response.ok) {
        // The server reports uncertain/partial sends as 409. Only definitive
        // pre-dispatch or no-delivery responses permit changing the request.
        lastSendDefinitelyFailed.current = [422, 429, 503].includes(response.status);
        throw new Error(detail?.error ?? detail?.detail ?? 'Project email could not be delivered.');
      }
      onSent(detail.sent as number);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className="project-settings-dialog export-project-dialog email-project-dialog" aria-labelledby="email-project-heading"
    onCancel={event => { event.preventDefault(); cancel(); }}>
    <form onSubmit={send}>
      <header className="settings-header">
        <h2 id="email-project-heading">Email Project</h2>
        <div className="settings-actions"><button type="submit" className="settings-submit" disabled={busy || (!loaded && effectiveMode !== 'project') || !recipients.trim()}>{busy ? 'Sending…' : 'Send'}</button><DialogDismissButton label="Cancel email" disabled={busy} onClick={cancel}/></div>
      </header>
      <div className="settings-body">
        <p className="settings-hint">The current project, <strong>{title}</strong>, will be sent as an importable attachment to the email addresses you provide.</p>
        <label htmlFor="email-project-recipients">Email addresses</label>
        <input ref={addressInput} id="email-project-recipients" type="text" value={recipients} disabled={busy} required spellCheck={false}
          onChange={event => { payloadChanged(); setRecipients(event.target.value); setError(''); }} placeholder="name@example.com, other@example.com" />
        <label htmlFor="email-project-body">Message (optional)</label>
        <textarea id="email-project-body" rows={3} value={body} maxLength={10000} disabled={busy}
          onChange={event => { payloadChanged(); setBody(event.target.value); }} />
        <fieldset className="export-type-options" disabled={busy}>
          <legend>Attachments</legend>
          <label><input type="radio" name="email-project-mode" checked={effectiveMode === 'project'} onChange={() => { payloadChanged(); setMode('project'); }}/>Just attach project</label>
          <label><input type="radio" name="email-project-mode" checked={effectiveMode === 'pdf'} disabled={!loaded || papersByDate.length === 0} onChange={() => { payloadChanged(); setMode('pdf'); }}/>Also attach paper as PDF</label>
          <label><input type="radio" name="email-project-mode" checked={effectiveMode === 'pdf_tex'} disabled={!loaded || papersByDate.length === 0} onChange={() => { payloadChanged(); setMode('pdf_tex'); }}/>Also attach paper as PDF and its source LaTeX</label>
        </fieldset>
        {paperLoad === 'error' ? <p className="settings-hint" role="status">Paper list unavailable. Your attachment choice is unchanged. <button type="button" className="text-view-link" disabled={busy} onClick={() => setPaperRetry(value => value + 1)}>Retry</button></p> : loaded && !papersByDate.length ? <p className="email-no-papers">No papers generated.</p> : loaded && papersByDate.length > 0 ? <>
          <label htmlFor="email-project-paper">Generated paper</label>
          <select id="email-project-paper" value={selectedPaperId} disabled={busy || effectiveMode === 'project'} onChange={event => { payloadChanged(); setPaperId(event.target.value); }}>
            {papersByDate.map(paper => <option key={paper.paper_id} value={paper.paper_id}>{paper.title} (v{paper.paper_version}){(paper.score?.total ?? 0) >= 50 ? ' ★' : ''}</option>)}
          </select>
        </> : <p className="settings-hint" role="status">Loading generated papers…</p>}
        {error && <p className="error" role="alert">{error}</p>}
      </div>
    </form>
  </dialog>;
}

type PaperScore = {
  rubric_id: string;
  rubric_version: number;
  pdf_sha256: string;
  total: number;
  provisional: boolean;
  categories: Record<'tex_correctness' | 'readability' | 'sustained_answer' | 'research_rigor' | 'evidence' | 'visuals', { earned: number; max: 100; weight: number; explanation: string }>;
};
const HIGH_SCORING_PAPER_THRESHOLD = 70;
const HIGH_SCORING_PAPER_TOOLTIP = 'Marked as a high scoring paper (70 or higher)';
const paperScoreCategories: { key: keyof PaperScore['categories']; title: string; standard: string }[] = [
  { key: 'tex_correctness', title: 'TeX correctness', standard: 'Equations render correctly, without material compilation, clipping, or obscuration defects.' },
  { key: 'readability', title: 'Human readability, including layout', standard: 'A scientifically curious nonspecialist can follow the prose, definitions, equations, and page flow on a careful first read; full credit also requires a human cold read.' },
  { key: 'sustained_answer', title: 'Clear question and sustained answer', standard: 'A bounded research question is advanced consistently throughout the paper and answered with a supported conclusion.' },
  { key: 'research_rigor', title: 'Research rigor and correctness', standard: 'Sound derivations and logic; alternatives, counterexamples, uncertainty, and reproducibility are evaluated; established results are distinguished from conjectures.' },
  { key: 'evidence', title: 'Evidence and verification', standard: 'Inspect-able evidence and computations support material claims; assumptions, limitations, and unresolved gaps are explicit.' },
  { key: 'visuals', title: 'Useful visuals', standard: 'Accurate figures or tables clarify difficult relationships, with clear captions and provenance.' },
];

function PaperScoreDialog({ score, error, onClose }: { score: PaperScore; error: string; onClose: () => void }) {
  const element = useRef<HTMLDialogElement>(null);
  useEffect(() => { element.current?.showModal(); }, []);
  return <dialog ref={element} className="project-settings-dialog paper-score-dialog" aria-labelledby="paper-score-title"
    onCancel={event => { event.preventDefault(); onClose(); }}>
    <header className="settings-header paper-score-header">
      <h2 id="paper-score-title">Paper Score</h2>
      <div className="settings-actions"><DialogDismissButton label="Close paper score" onClick={onClose}/></div>
    </header>
    <div className="settings-body paper-score-body">
      <p className="settings-hint paper-score-rescore-instructions">To rescore, click the Scored step in the paper's progress sequence.</p>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="paper-score-overall" aria-label={`Weighted paper score ${score.total} out of 100`}>
        <strong>Weighted score</strong><strong className="paper-score-points">{score.total}/100</strong>
      </div>
      <p className="settings-hint">SIGMA’s research and paper-authoring capabilities are experimental; these provisional scores acknowledge known quality limitations and do not constitute independent scientific verification or human review.</p>
      <div className="paper-score-categories" aria-label="Paper scores">
        {paperScoreCategories.map(({ key, title, standard }) => <details className="paper-score-category" key={key}>
          <summary className="paper-score-category-heading">
            <span className="paper-score-category-label">{title} <span className="paper-score-weight">(weight {score.categories[key].weight.toFixed(2)})</span></span>
            <strong className="paper-score-points">{score.categories[key].earned}/100</strong>
          </summary>
          <div className="paper-score-category-detail">
            <p className="paper-score-standard"><strong>Rubric:</strong> {standard}</p>
            <p className="paper-score-assessment"><strong>Assessment:</strong> {score.categories[key].explanation}</p>
          </div>
        </details>)}
      </div>
    </div>
  </dialog>;
}

function modelThinkingLabel(model: string, effort: string): string {
  return `${model} (${thinkingLabels[effort] ?? effort})`;
}
type AttributionKind = 'session' | 'paper' | 'answer';
type RunAttribution = { kind: AttributionKind; status?: 'active' | 'queued'; creator?: string | null; model?: string | null; thinking?: string | null; number?: number | null; mode?: 'metadata' | 'hover' };
/** Single canonical renderer for all Session, Paper and Ask provenance. */
function formatRunAttribution({ kind, status, creator, model, thinking, number, mode = 'metadata' }: RunAttribution): string {
  const noun = kind === 'session' ? 'Session' : kind === 'paper' ? 'Paper' : 'Answer';
  const subject = mode === 'hover' ? `${noun}${number != null ? ` ${number}` : ''}` : '';
  // Green already indicates active work; retain "(queued)" because yellow
  // distinguishes queued work, and keep the saved-card metadata compact.
  const state = mode === 'hover' && status === 'queued' ? '(queued)' : '';
  const actor = creator ? `by ${creator}` : '';
  const modelInfo = model ? `using ${modelThinkingLabel(model, thinking ?? '')}` : '';
  return [subject, state, actor, modelInfo].filter(Boolean).join(' ');
}
function latestPaperModel(generation: PaperSummary['generation']): { model: string; thinking: string } {
  const history = generation.model_change_history ?? [];
  const last = history[history.length - 1];
  return last ? { model: last.to_model, thinking: last.to_effort } : { model: generation.model, thinking: generation.reasoning_effort };
}

type PaperSummary = { score?: PaperScore | null; paper_id: string; paper_version: number; download_basename: string; title: string; created_at: string; snapshot_sha256: string; validation_warnings: string[]; author_review_warnings?: string[]; pdf_available?: boolean; pdf_sha256?: string; created_by?: string; generation: { mode: string; model: string; reasoning_effort: string; model_change_history?: { from_model: string; to_model: string; from_effort: string; to_effort: string; call_index: number }[]; call_limit: number; publication_status?: 'needs_review' | 'proofreading_complete'; layout_status?: 'needs_review' | 'no_severe_box_warnings_reported'; proofreading?: { status?: string; verification_status?: string; review_reason?: string }; provider_calls_attempted?: number; provider_calls_prior_runs?: number; provider_calls_lifetime_total?: number; generation_elapsed_seconds?: number; long_form?: boolean; evidence_batch_count?: number; evidence_fields_omitted?: number; omitted_evidence?: { field_ref: string; source_ref: string; field: string; reason: string }[]; evidence_note_compaction_events?: number; reduction_source_refs_omitted?: string[]; evidence_conflict_note_count?: number; evidence_conflicts?: { statement: string; evidence_refs: string[] }[]; writing_source_selection?: string; writing_sources?: { title: string; url: string; tier: string; type: string; branch: string; sha256: string }[]; sigma_issues?: string[]; sigma_issues_included?: boolean } };
function paperModelThinkingLabel(generation: PaperSummary['generation']): string {
  const latest = latestPaperModel(generation);
  return modelThinkingLabel(latest.model, latest.thinking);
}

type PaperProgress = { status: 'queued' | 'active' | 'interrupted' | 'failed' | 'cancelled' | 'complete'; resume_stage?: PaperProgress['stage'] | null; stage: 'queued' | 'snapshot' | 'source_material' | 'publication_compilation' | 'writing' | 'evidence' | 'consolidation' | 'planning' | 'sections' | 'retry' | 'validation' | 'proofreading' | 'compile' | 'pdf_check' | 'scoring' | 'score_failed' | 'finishing' | 'complete'; current: number | null; total: number | null; started_at: string; elapsed_seconds: number; sections_total?: number; last_progress_at?: string | null; output_delta_count?: number; substep_started_at?: string | null; detail?: string; failure_reason?: string; activity_state?: 'active' | 'milestone' | 'complete'; model?: string; reasoning_effort?: string };
type PaperRun = { run_id: string; number: number; creator_email: string; model: string; thinking: string; created_at: number; status: PaperProgress['status']; progress: Partial<PaperProgress> | null; paper_id?: string | null; can_control: boolean; can_resume?: boolean; can_remove?: boolean; preflight_needed?: boolean };

type PaperRecord = PaperSummary & { eli5?: { version?: number; source_sha256: string; markdown: string }; pdf_sha256?: string; draft: { title: string; abstract: string; abstract_claim_ids: string[]; problem_framing: string[]; problem_framing_claim_ids: string[]; methods: string[]; methods_claim_ids: string[]; claims: { id: string; statement: string; status: string; evidence_refs: string[]; reasoning: string }[]; sections: { heading: string; paragraphs: string[]; claim_ids: string[] }[]; limitations: string[]; open_obligations: string[]; conclusions: string[]; conclusion_claim_ids: string[] }; obligation_reconciliation?: { text: string; source_refs: string[]; status: string }[]; publication_requirement_reconciliation?: { text: string; status: 'missing' | 'needs_review'; note: string }[]; editorial_overlap_warnings?: string[]; snapshot: { sources: { id: string; kind: string }[] } };

const PAPER_STAGES = [
  { label: 'Starting', stages: ['queued'] },
  { label: 'Review publication standards', stages: ['snapshot', 'source_material', 'publication_compilation'] },
  { label: 'Extract evidence', stages: ['evidence', 'consolidation'] },
  { label: 'Planning', stages: ['planning'] },
  { label: 'Write sections', stages: ['writing', 'sections'] },
  { label: 'Validate', stages: ['validation'] },
  { label: 'Proofread', stages: ['proofreading'] },
  { label: 'Generate PDF', stages: ['compile', 'pdf_check'] },
  { label: 'Score', stages: ['scoring', 'score_failed'] },
  { label: 'Finish', stages: ['finishing', 'complete'] },
] as const;

function paperStageLabel(step: number, active: number, progress: PaperProgress): string {
  const completed = step < active || (step === active && progress.status === 'complete' && progress.stage !== 'score_failed');
  const current = step === active && (progress.status === 'active' || progress.status === 'queued');
  const sectionsTotal = progress.sections_total ?? (progress.stage === 'sections' ? progress.total : null);
  if (step === 0) return completed ? 'Started' : 'Starting';
  if (step === 1) return completed ? 'Reviewed publication standards' : current ? 'Reviewing publication standards' : 'Review publication standards';
  if (step === 2) return completed ? 'Extracted evidence' : current ? 'Extracting evidence' : 'Extract evidence';
  if (step === 3) return completed ? 'Planned' : 'Planning';
  if (step === 4) {
    if (completed) return 'Wrote sections' + (sectionsTotal !== null && sectionsTotal > 0 ? ` (${sectionsTotal})` : '');
    if (current) {
      const count = progress.stage === 'sections' && progress.current !== null && sectionsTotal !== null && sectionsTotal > 0
        ? ` (${progress.current}/${sectionsTotal})` : '';
      return 'Writing sections' + count;
    }
    return 'Write sections';
  }
  if (step === 5) return completed ? 'Validated' : current ? 'Validating' : 'Validate';
  if (step === 6) return completed ? 'Proofread' : current ? 'Proofreading' : 'Proofread';
  if (step === 7) return completed ? 'Generated PDF' : current ? 'Generating PDF' : 'Generate PDF';
  if (step === 8) {
    if (progress.detail?.includes('scoring did not finish')) return 'Score unavailable';
    return completed ? 'Scored' : current ? 'Scoring' : 'Score';
  }
  return completed ? 'Finished' : current ? 'Finishing' : 'Finish';
}

// Previously persisted checkpoints sometimes used retry as a synthetic stage.
function paperDisplayProgress(progress: PaperProgress): PaperProgress {
  if (progress.stage !== 'retry') return progress;
  return progress.sections_total
    ? { ...progress, stage: 'sections', current: null, total: progress.sections_total }
    : { ...progress, stage: 'writing', current: null, total: null };
}

function paperProgressOperation(progress: PaperProgress): string {
  const display = paperDisplayProgress(progress);
  const index = PAPER_STAGES.findIndex(group => (group.stages as readonly string[]).includes(display.stage));
  return index < 0 ? 'Paper generation' : paperStageLabel(index, index, display);
}

// Server errors and persisted progress may use internal terminology.
// Translate those details only when showing them to the reader.
function paperUserMessage(message: string): string {
  if (!/checkpoint/i.test(message)) return message;
  if (/no (?:usable |verified |resumable |restart )?(?:paper )?checkpoint|no verified restart checkpoint|no restart checkpoint|checkpoint is unavailable/i.test(message))
    return 'This paper cannot restart from the selected step.';
  if (/checkpoint.*(?:changed|does not match|not durably restored)|restored checkpoint does not match/i.test(message))
    return 'The saved paper changed. Reopen it and try again.';
  return message.replace(/\bcheckpoints\b/gi, 'saved progress').replace(/\bcheckpoint\b/gi, 'saved progress');
}

function paperErrorSummary(message: string): string {
  const value = paperUserMessage(message.trim());
  if (friendlyProviderError(value) !== value) return friendlyProviderError(value);
  if (/Published Paper does not match its creator reservation/i.test(value)) {
    return 'The PDF was saved. Resume this paper to finish publication and scoring.';
  }
  if (/Tectonic could not compile|No PDF was downloaded|PDF compilation failed/i.test(value)) {
    return 'PDF compilation failed. The paper draft is preserved; use Resume to retry without rewriting it.';
  }
  const line = value.split(/\r?\n/, 1)[0];
  return line.length > 250 ? line.slice(0, 247) + '…' : line;
}

function paperActivityLabel(progress: PaperProgress, now: number): string {
  if (progress.stage === 'planning') {
    const start = Date.parse(progress.substep_started_at ?? progress.last_progress_at ?? progress.started_at);
    const elapsed = Number.isFinite(start) ? Math.max(0, Math.floor((now - start) / 1000)) : 0;
    const detail = progress.detail;
    const substep = detail === 'Waiting for AI response'
      ? ((progress.output_delta_count ?? 0) > 0 ? 'Receiving' : 'Waiting')
      : detail === 'Requesting paper plan' ? 'Requesting'
      : detail === 'Validating outline' ? 'Checking'
      : detail === 'Saving plan' ? 'Preparing'
      : detail === 'Recovering outline from research evidence' ? 'Recovering'
      : 'Preparing';
    // Minutes are sufficient for long waits; omit noisy per-token timestamps.
    const duration = elapsed < 60 ? `${elapsed}s` : `${Math.floor(elapsed / 60)}m`;
    return `${substep} · ${duration}`;
  }
  if (progress.stage === 'proofreading') {
    const pass = progress.detail?.match(/Pass (\d+) of up to (\d+)/i);
    return pass ? `${pass[1]} of up to ${pass[2]}` : '1 of up to 3';
  }
  if (progress.stage === 'retry' || progress.detail?.toLowerCase().startsWith('retrying')) {
    const attempt = progress.detail?.match(/attempt (\d+) of (\d+)/i);
    return attempt ? `Retrying · Attempt ${attempt[1]} of ${attempt[2]}` : 'Retrying…';
  }
  const timestamp = progress.last_progress_at ? Date.parse(progress.last_progress_at) : NaN;
  if (!Number.isFinite(timestamp)) return 'Starting…';
  const elapsed = Math.max(0, Math.floor((now - timestamp) / 1000));
  if (elapsed < 60) {
    const recent = elapsed < 5 ? 'Just now' : `${elapsed} sec ago`;
    return (progress.output_delta_count ?? 0) > 0
      ? `Receiving text · ${recent}`
      : `Writing in progress · ${recent}`;
  }
  const minutes = Math.floor(elapsed / 60);
  if (minutes >= 5) return `No recent writing activity for ${minutes} min`;
  return `Last writing activity · ${minutes} min ago`;
}

function PaperActivityLine({ progress }: { progress: PaperProgress }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (progress.status !== 'active') return;
    const clock = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(clock);
  }, [progress.status]);
  if (progress.status !== 'active' || !['planning', 'writing', 'sections', 'proofreading', 'retry'].includes(progress.stage)) return null;
  return <span className="paper-activity-line">{paperActivityLabel(progress, now)}</span>;
}

type SavedPaperRestartStage = 'started' | 'writing' | 'validation' | 'typesetting' | 'scoring';
type UnfinishedPaperRestartStage = 'started' | 'review' | 'evidence' | 'planning' | 'writing' | 'validation' | 'typesetting' | 'pdf';
type UnfinishedPaperRestartOptions = { snapshot_sha256: string; stages: UnfinishedPaperRestartStage[]; resume_stage: PaperProgress['stage']; published_paper_id?: string };
const PAPER_UNFINISHED_STAGES: readonly (UnfinishedPaperRestartStage | null)[] = [
  'started', 'review', 'evidence', 'planning', 'writing', 'validation', 'typesetting', 'pdf', null, null,
];
const paperUnfinishedStageLabel = (stage: UnfinishedPaperRestartStage): string =>
  stage === 'started' ? 'Started' : stage === 'review' ? 'Review publication standards'
    : stage === 'evidence' ? 'Extract evidence' : stage === 'planning' ? 'Planning'
    : stage === 'writing' ? 'Write sections' : stage === 'validation' ? 'Validate'
    : stage === 'typesetting' ? 'Proofread' : 'Generate PDF';
const paperUnfinishedProgressStage = (stage: UnfinishedPaperRestartStage): PaperProgress['stage'] =>
  stage === 'started' ? 'queued' : stage === 'review' ? 'publication_compilation'
    : stage === 'evidence' ? 'evidence' : stage === 'planning' ? 'planning'
    : stage === 'writing' ? 'writing' : stage === 'validation' ? 'validation'
    : stage === 'typesetting' ? 'proofreading' : 'compile';
const paperUnfinishedOptionsKey = (runId: string | null) => runId ?? 'legacy';
function rewindProgressStage(stage: SavedPaperRestartStage): PaperProgress['stage'] {
  return stage === 'started' ? 'queued'
    : stage === 'writing' ? 'writing'
    : stage === 'validation' ? 'validation'
    : stage === 'scoring' ? 'scoring' : 'proofreading';
}
function paperRestartStepName(stage: SavedPaperRestartStage): string {
  return stage === 'started' ? 'Started' : stage === 'writing' ? 'Write sections'
    : stage === 'validation' ? 'Validate'
    : stage === 'scoring' ? 'Score' : 'Proofread';
}
const paperUnfinishedCheckpointForStep = (
  step: number, available: readonly UnfinishedPaperRestartStage[],
): UnfinishedPaperRestartStage => {
  // Visible steps are navigation targets. Select the latest durable boundary
  // at or before the requested step; never invent intermediate checkpoints.
  for (let candidate = Math.min(step, 7); candidate >= 0; candidate--) {
    const stage = PAPER_UNFINISHED_STAGES[candidate];
    if (stage && available.includes(stage)) return stage;
  }
  return 'started';
};

function PaperStageSteps({ progress, onSelectStep }: {
  progress: PaperProgress;
  onSelectStep?: (step: number, anchor: HTMLButtonElement) => void;
}) {
  const display = paperDisplayProgress(progress);
  const index = PAPER_STAGES.findIndex(group => (group.stages as readonly string[]).includes(display.stage));
  return <ol className="session-strategy-live-status paper-stage-list" aria-label="Paper generation steps">
    {PAPER_STAGES.map((group, step) => {
      const next = step === index && ['interrupted', 'cancelled', 'failed'].includes(progress.status);
      const interactive = step < PAPER_STAGES.length - 1 && !!onSelectStep;
      return <li key={group.label} data-paper-step={group.label}
        className={next ? 'is-next' : step === index
          ? (display.stage === 'score_failed' ? 'is-upcoming' : progress.status === 'queued'
            ? 'is-queued' : progress.status === 'active' ? 'is-active'
            : progress.status === 'complete' ? 'is-past' : 'is-idle')
          : step < index ? 'is-past' : 'is-upcoming'}>
        {interactive
          ? <button type="button" className="paper-step-restart"
              aria-label={step === 8 && progress.status === 'complete'
                ? 'Rescore paper'
                : `Restart paper at step ${step === 0 ? 'Started' : group.label}`}
              onClick={event => onSelectStep?.(step, event.currentTarget)}>
              <strong>{paperStageLabel(step, index, display)}</strong>
            </button>
          : <strong>{paperStageLabel(step, index, display)}</strong>}
        {step === index && <PaperActivityLine progress={progress}/>}
      </li>;
    })}
  </ol>;
}

/** All papers use one view model: immutable attribution, authoritative resume
    target, and a single action bar. Disclosure hides the bar and all details. */
function PaperTimeline({ metadata, progress, expanded, onSelectStep, message, detail }: {
  metadata: ReactNode;
  progress: Partial<PaperProgress> | null;
  expanded: boolean;
  onSelectStep?: (step: number, anchor: HTMLButtonElement) => void;
  message?: ReactNode;
  detail?: string | null;
}) {
  const stopped = ['interrupted', 'failed', 'cancelled'].includes(progress?.status ?? '');
  const visible: PaperProgress = {
    status: progress?.status ?? 'interrupted',
    stage: stopped && progress?.resume_stage ? progress.resume_stage : progress?.stage ?? 'queued',
    current: progress?.current ?? null,
    total: progress?.total ?? null,
    started_at: progress?.started_at ?? '',
    elapsed_seconds: progress?.elapsed_seconds ?? 0,
    ...progress,
    // The execution stage and the last streamed activity are distinct.
    ...(stopped && progress?.resume_stage ? { stage: progress.resume_stage } : {}),
  };
  // Running state and elapsed time already appear in paper metadata. Reserve
  // this line for explicit action feedback, not a duplicate live timer.
  return <div className="paper-unified-timeline">
    <p className="saved-paper-meta">{metadata}</p>
    {(message != null && message !== '' || detail) &&
      <div className="ai-paper-status ai-paper-progress paper-timeline-message" role="status" aria-live="polite">
        {message}
        {detail && <span className="paper-progress-substep">{paperUserMessage(detail)}</span>}
      </div>}
    <div className="ai-paper-status ai-paper-progress" role="status" hidden={!expanded}>
      <PaperStageSteps progress={visible} onSelectStep={onSelectStep}/>
    </div>
  </div>;
}

function PaperStepFeedback({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  // Give short errors a compact footprint while allowing long explanations
  // two or three comfortable lines before wrapping further.
  const size = message.length <= 90 ? 'short' : message.length <= 190 ? 'medium' : 'long';
  return <div role="alert" className={`ai-paper-warning paper-inline-feedback paper-inline-feedback--${size}`}>
    <span>{paperUserMessage(message)}</span>
    <DialogDismissButton label="Dismiss paper notice" onClick={onDismiss}/>
  </div>;
}

function unfinishedPaperTarget(step: number): UnfinishedPaperRestartStage {
  return PAPER_UNFINISHED_STAGES[Math.min(step, 7)] ?? 'started';
}

function publishedPaperTarget(step: number): SavedPaperRestartStage {
  return step < 4 ? 'started' : step === 4 ? 'writing'
    : step === 5 ? 'validation' : 'typesetting';
}

function paperReviewLabel(generation: PaperSummary['generation']): string {
  return generation.layout_status === 'needs_review'
    ? 'Needs review · PDF layout warnings remain after three passes'
    : 'Needs review · TeX verification incomplete';
}

function savedPaperElapsed(seconds: number): string {
  const totalMinutes = Math.max(0, Math.ceil(seconds / 60));
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours ? `${hours}hr${minutes ? ` ${minutes}m` : ""}` : `${minutes}m`;
}

function paperElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return minutes ? `${minutes}m ${remaining}s` : `${remaining}s`;
}

function PapersPane({ collaborationRevision, artifactAuthors, viewerEmail, projectOwnerEmail, draftCreatorEmail, path, projectId, guest = false, onRunningChange, onQueuedChange, onInitialActivity, onSectionOpened }: { collaborationRevision?: number; artifactAuthors?: Record<string, string>; viewerEmail?: string; projectOwnerEmail?: string | null; draftCreatorEmail?: string; path: string; projectId: string; guest?: boolean; onRunningChange: (running: boolean, activeRunIds: string[]) => void; onQueuedChange: (queued: boolean) => void; onInitialActivity: (status: 'active' | 'queued' | null) => void; onSectionOpened: () => void }) {
  const ai = useAI();
  const initialPaperListing = useRef<InitialPaperListing | null>(takeInitialPaperListing(path, projectId));
  const [expanded, setExpanded] = useState(() => window.localStorage.getItem(`sigma.papersPane:${path}`) !== 'false');
  const [paperMenu, setPaperMenu] = useState<{ paperId: string; kind: 'download' | 'actions' } | null>(null);
  const [includeOptionsOpen, setIncludeOptionsOpen] = useState(false);
  const includePopupRef = useRef<HTMLDivElement>(null);
  const includeButtonRef = useRef<HTMLButtonElement>(null);
  const [includePopupOffset, setIncludePopupOffset] = useState(0);
  const [includePopupAbove, setIncludePopupAbove] = useState(false);
  const [includePopupMaxHeight, setIncludePopupMaxHeight] = useState(380);
  useLayoutEffect(() => {
    if (!includeOptionsOpen) return;
    const button = includeButtonRef.current;
    const popup = includePopupRef.current;
    if (!button || !popup) return;
    const bounds = button.getBoundingClientRect();
    const edge = 16;
    const popupGap = 9;
    const naturalHeight = popup.scrollHeight + 28; // Account for vertical padding.
    const below = Math.max(0, window.innerHeight - bounds.bottom - popupGap - edge);
    const above = Math.max(0, bounds.top - popupGap - edge);
    const placeAbove = below < Math.min(380, naturalHeight) && above > below;
    setIncludePopupAbove(placeAbove);
    setIncludePopupMaxHeight(Math.max(0, Math.min(380, placeAbove ? above : below)));
  }, [includeOptionsOpen]);
  function openIncludeOptions() {
    const button = includeButtonRef.current;
    if (!button) return;
    const bounds = button.getBoundingClientRect();
    const width = Math.min(340, window.innerWidth - 32);
    setIncludePopupOffset(Math.max(16, Math.min(bounds.left, window.innerWidth - width - 16)) - bounds.left);
    setIncludeOptionsOpen(true);
  }
  useEffect(() => {
    if (!includeOptionsOpen) return;
    const dismissOutside = (event: PointerEvent) => {
      if (event.target instanceof Node &&
          !includePopupRef.current?.contains(event.target) &&
          !includeButtonRef.current?.contains(event.target)) setIncludeOptionsOpen(false);
    };
    const dismissEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setIncludeOptionsOpen(false); includeButtonRef.current?.focus(); }
    };
    const dismissOnResize = () => setIncludeOptionsOpen(false);
    document.addEventListener('pointerdown', dismissOutside);
    document.addEventListener('keydown', dismissEscape);
    window.addEventListener('resize', dismissOnResize);
    return () => {
      document.removeEventListener('pointerdown', dismissOutside);
      document.removeEventListener('keydown', dismissEscape);
      window.removeEventListener('resize', dismissOnResize);
    };
  }, [includeOptionsOpen]);
  const [newPaperRequested, setNewPaperRequested] = useState(false);
  const [guestPaperPreview, setGuestPaperPreview] = useState(false);
  const [guestScorePreview, setGuestScorePreview] = useState(false);
  const [guestExplainPreview, setGuestExplainPreview] = useState(false);
  const [confirmNewPaper, setConfirmNewPaper] = useState(false);
  const [draftPaperExpanded, setDraftPaperExpanded] = useState(true);
  const [expandedOtherPaperRunIds, setExpandedOtherPaperRunIds] = useState<Set<string>>(() => new Set());
  useEffect(() => {
    const opened = (event: Event) => {
      if ((event as CustomEvent<string>).detail !== 'papers') {
        setExpanded(false);
        window.localStorage.setItem(`sigma.papersPane:${path}`, 'false');
      }
    };
    window.addEventListener('sigma-project-section-opened', opened);
    return () => window.removeEventListener('sigma-project-section-opened', opened);
  }, [path]);

  const request = useRef<AbortController | null>(null);
  const paperSubmissionDispatched = useRef(false);
  const deliberatePaperStop = useRef(false);
  const paperStopPending = useRef(false);
  const paperStopAwaitingCheckpoint = useRef<{ runId: string | null } | null>(null);
  // Newer user actions outrank older responses from refreshes and live streams.
  const paperActionEpoch = useRef(0);
  const paperRefreshSerial = useRef(0);
  const paperStopIntentRef = useRef<Set<string>>(new Set());
  const hasPaperStopIntent = (runId: string | null) =>
    paperStopIntentRef.current.has(runId ?? 'legacy');
  const clearPaperStopIntent = (runId: string | null) => {
    paperStopIntentRef.current.delete(runId ?? 'legacy');
    setOptimisticPaperStop(current => current?.runId === runId ? null : current);
  };
  // Visual-only Stop intent; the backend still owns durable cancellation.
  const [optimisticPaperStop, setOptimisticPaperStop] = useState<{ runId: string | null } | null>(null);
  const [paperPlayIntent, setPaperPlayIntent] = useState<'starting' | 'resuming'>('starting');
  const [paperStopReconciliation, setPaperStopReconciliation] = useState(false);
  const [papers, setPapers] = useState<PaperSummary[]>(() => initialPaperListing.current?.papers ?? []);
  const [paperRuns, setPaperRuns] = useState<PaperRun[]>(() => initialPaperListing.current?.runs ?? []);
  const selectedRunIdRef = useRef<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  useEffect(() => {
    const reveal = (event: Event) => {
      const id = (event as CustomEvent<string>).detail;
      onSectionOpened();
      setExpanded(true);
      window.localStorage.setItem(`sigma.papersPane:${path}`, 'true');
      if (id && paperRuns.some(run => run.run_id === id && run.run_id !== selectedRunIdRef.current)) {
        setExpandedOtherPaperRunIds(current => new Set(current).add(id));
      }
      if (id && selectedRunIdRef.current === id) setDraftPaperExpanded(true);
      requestAnimationFrame(() => requestAnimationFrame(() => {
        const item = id
          ? document.querySelector<HTMLElement>(`[data-paper-run="${CSS.escape(id)}"]`)
            ?? (selectedRunIdRef.current === id ? document.querySelector<HTMLElement>('.paper-draft-card') : null)
          : null;
        (item ?? document.getElementById('papers-heading'))?.scrollIntoView({ block: 'center' });
      }));
    };
    window.addEventListener('sigma-reveal-papers', reveal);
    return () => window.removeEventListener('sigma-reveal-papers', reveal);
  }, [path, onSectionOpened, paperRuns]);
  function selectPaperRun(runId: string | null) {
    selectedRunIdRef.current = runId;
    setSelectedRunId(runId);
  }
  const [nextPaperNumber, setNextPaperNumber] = useState<number | null>(() => initialPaperListing.current?.nextPaperNumber ?? null);
  const [scoringId, setScoringId] = useState('');
  // Per-paper optimistic tombstones prevent unrelated actions and polling
  // from blocking or resurrecting a paper awaiting deletion.
  const [hiddenRemovalIds, setHiddenRemovalIds] = useState<Set<string>>(() => new Set());
  const [removingLegacyDraft, setRemovingLegacyDraft] = useState(false);
  const pendingRemovals = useRef<Set<string>>(new Set());
  function beginPaperRemoval(id: string): boolean {
    if (pendingRemovals.current.has(id)) return false;
    pendingRemovals.current.add(id);
    setHiddenRemovalIds(current => new Set(current).add(id));
    return true;
  }
  function finishPaperRemoval(id: string, successful: boolean) {
    pendingRemovals.current.delete(id);
    if (!successful) setHiddenRemovalIds(current => {
      const next = new Set(current);
      next.delete(id);
      return next;
    });
  }
  const [paperRemovalErrors, setPaperRemovalErrors] = useState<Record<string, string>>({});
  const [scoreDialog, setScoreDialog] = useState<{ paperId: string; score: PaperScore } | null>(null);
  const [scoreError, setScoreError] = useState('');
  const [, setScoreConfig] = useState<{ available: boolean; binding: string; message: string } | null>(null);
  const scoringRef = useRef(false);
  const [selected, setSelected] = useState<PaperRecord | null>(null);
  const [copiedPaperId, setCopiedPaperId] = useState('');
  const [copiedExplanationId, setCopiedExplanationId] = useState('');
  const [copyError, setCopyError] = useState('');
  const [binding, setBinding] = useState('');
  const [model, setModel] = useState('');
  const [mode, setMode] = useState('');
  const [effort, setEffort] = useState('');
  const [includeClaimDetails, setIncludeClaimDetails] = useState(() => window.localStorage.getItem('sigma.paper.claims:' + projectId) !== 'false');
  const [includeValidationNotes, setIncludeValidationNotes] = useState(() => window.localStorage.getItem('sigma.paper.validation:' + projectId) === 'true');
  const [includeResearchExcerpts, setIncludeResearchExcerpts] = useState(() => window.localStorage.getItem('sigma.paper.excerpts:' + projectId) === 'true');
  const [includeSigmaIssues, setIncludeSigmaIssues] = useState(() => window.localStorage.getItem('sigma.paper.issues:' + projectId) === 'true');
  const [includeDiagramsAndTables, setIncludeDiagramsAndTables] = useState(() => window.localStorage.getItem('sigma.paper.diagrams:' + projectId) !== 'false');
  const [checkpointMismatch, setCheckpointMismatch] = useState<any>(null);
  const [restartableCheckpoint, setRestartableCheckpoint] = useState<any>(null);
  const [restartReady, setRestartReady] = useState(false);
  const [resetConfirm, setResetConfirm] = useState(false);
  const [confirmDiscardDraft, setConfirmDiscardDraft] = useState(false);
  const [confirmDiscardRun, setConfirmDiscardRun] = useState<{ runId: string; left: number; top: number } | null>(null);
  const discardRunPopup = useRef<HTMLDivElement>(null);
  const [confirmRestartDraft, setConfirmRestartDraft] = useState(false);
  const [confirmPlayRestartDraft, setConfirmPlayRestartDraft] = useState(false);
  const [continuationAvailable, setContinuationAvailable] = useState(false);
  const [resumeDetails, setResumeDetails] = useState<{ outline_complete: boolean; completed_sections: number; evidence_indexed: boolean; completed_batches: number; draft_recovery_available: boolean; planning_fallback_available?: boolean; recovery_sections?: number[]; proofreading_status?: string; publication_status?: string; restart_stages?: UnfinishedPaperRestartStage[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [restartingCheckpoint, setRestartingCheckpoint] = useState(false);
  const [phase, setPhase] = useState('');
  const [paperProgress, setPaperProgress] = useState<PaperProgress | null>(null);
  const [dismissedPaperNoticeKey, setDismissedPaperNoticeKey] = useState('');
  const initialPaperActivityReported = useRef(false);
  const [error, setError] = useState('');
  // A successful publication supersedes the earlier generation error,
  // even when the draft card has already been replaced by a saved paper.
  const generationErrorRunId = useRef<string | null>(null);
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(() => initialPaperListing.current === null);
  const [expandedPaperId, setExpandedPaperId] = useState('');
  const [paperStepRestart, setPaperStepRestart] = useState<{
    paper: PaperSummary; stage: SavedPaperRestartStage;
    options: { source_pdf_sha256: string; snapshot_sha256: string; include_diagrams: boolean } | null;
    checking: boolean; error: string;
  } | null>(null);
  const [paperStepRestartBusy, setPaperStepRestartBusy] = useState(false);
  const [unfinishedStepOptions, setUnfinishedStepOptions] = useState<Record<string, UnfinishedPaperRestartOptions>>({});
  const [unfinishedStepRestart, setUnfinishedStepRestart] = useState<{
    runId: string | null; number: number | null; stage: UnfinishedPaperRestartStage;
    snapshot_sha256: string; startFresh?: boolean;
    checking?: boolean; error?: string;
  } | null>(null);
  const unfinishedStepCheckAbort = useRef<AbortController | null>(null);
  const [unfinishedStepChecking, setUnfinishedStepChecking] = useState<{ key: string; stage: UnfinishedPaperRestartStage } | null>(null);
  const [unfinishedStepCheckError, setUnfinishedStepCheckError] = useState<{ key: string; message: string } | null>(null);
  const [unfinishedRestartBusy, setUnfinishedRestartBusy] = useState(false);
  const [resumeAfterActiveRewind, setResumeAfterActiveRewind] = useState<string | null>(null);
  const [newPaperToReveal, setNewPaperToReveal] = useState<string | null>(null);
  useEffect(() => {
    if (!newPaperToReveal || selectedRunId !== newPaperToReveal) return;
    const frame = requestAnimationFrame(() => {
      const card = document.querySelector<HTMLElement>('.papers-pane .paper-draft-card');
      if (!card) return;
      card.scrollIntoView({ block: 'center', behavior: 'smooth' });
      setNewPaperToReveal(null);
    });
    return () => cancelAnimationFrame(frame);
  }, [newPaperToReveal, selectedRunId, newPaperRequested]);
  const paperStepRestartAnchor = useRef<HTMLButtonElement | null>(null);
  const paperStepRestartPopup = useRef<HTMLDivElement | null>(null);
  const [paperStepRestartPlacement, setPaperStepRestartPlacement] = useState<{ left: number; top: number } | null>(null);
  const [providerChangePrompt, setProviderChangePrompt] = useState<{ savedModel: string; nextModel: string } | null>(null);
  const providerChangeResolver = useRef<((allowed: boolean) => void) | null>(null);
  const providerChangeAnchor = useRef<HTMLElement | null>(null);
  const providerChangePopup = useRef<HTMLDivElement>(null);
  const [providerChangePlacement, setProviderChangePlacement] = useState<{ left: number; top: number } | null>(null);
  const answerProviderChange = (allowed: boolean) => {
    const resolve = providerChangeResolver.current;
    providerChangeResolver.current = null;
    setProviderChangePrompt(null);
    resolve?.(allowed);
  };
  useEffect(() => () => { providerChangeResolver.current?.(false); providerChangeResolver.current = null; }, []);
  useLayoutEffect(() => {
    if (!providerChangePrompt) { setProviderChangePlacement(null); return; }
    const place = () => {
      const anchor = providerChangeAnchor.current?.isConnected
        ? providerChangeAnchor.current : document.querySelector<HTMLElement>('.papers-pane-heading');
      const popup = providerChangePopup.current;
      if (!anchor || !popup) return;
      const rect = anchor.getBoundingClientRect();
      const width = popup.offsetWidth, height = popup.offsetHeight;
      const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12));
      const top = Math.max(12, Math.min(
        window.innerHeight - rect.bottom >= height + 18 ? rect.bottom + 6 : rect.top - height - 6,
        window.innerHeight - height - 12,
      ));
      setProviderChangePlacement({ left, top });
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); answerProviderChange(false); }
    };
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    document.addEventListener('keydown', escape);
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
      document.removeEventListener('keydown', escape);
    };
  }, [providerChangePrompt]);
  const dismissPaperStepRestart = () => {
    paperStepCheckAbort.current?.abort();
    paperStepCheckAbort.current = null;
    setPaperStepChecking(null);
    setPaperStepRestart(null);
  };
  const dismissUnfinishedStepRestart = () => {
    unfinishedStepCheckAbort.current?.abort();
    unfinishedStepCheckAbort.current = null;
    setUnfinishedStepChecking(null);
    setUnfinishedStepRestart(null);
  };
  useLayoutEffect(() => {
    if (!paperStepRestart && !unfinishedStepRestart && !confirmRestartDraft) { setPaperStepRestartPlacement(null); return; }
    const place = () => {
      const anchor = paperStepRestartAnchor.current;
      const popup = paperStepRestartPopup.current;
      if (!anchor?.isConnected || !popup) {
        dismissPaperStepRestart();
        dismissUnfinishedStepRestart();
        setConfirmRestartDraft(false);
        return;
      }
      const rect = anchor.getBoundingClientRect();
      const width = popup.offsetWidth;
      const height = popup.offsetHeight;
      const margin = 12;
      const gap = 6;
      const left = Math.max(margin, Math.min(rect.left, window.innerWidth - width - margin));
      const below = window.innerHeight - rect.bottom;
      const above = rect.top;
      const desiredTop = below >= height + gap + margin || below >= above
        ? rect.bottom + gap : rect.top - height - gap;
      const top = Math.max(margin, Math.min(desiredTop, window.innerHeight - height - margin));
      setPaperStepRestartPlacement({ left, top });
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); dismissPaperStepRestart(); dismissUnfinishedStepRestart(); setConfirmRestartDraft(false); }
    };
    const closeOnOutside = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Node && !paperStepRestartPopup.current?.contains(target)
        && !paperStepRestartAnchor.current?.contains(target)) {
        dismissPaperStepRestart();
        dismissUnfinishedStepRestart();
        setConfirmRestartDraft(false);
      }
    };
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    document.addEventListener('keydown', closeOnEscape);
    document.addEventListener('pointerdown', closeOnOutside);
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
      document.removeEventListener('keydown', closeOnEscape);
      document.removeEventListener('pointerdown', closeOnOutside);
    };
  }, [paperStepRestart, unfinishedStepRestart, confirmRestartDraft]);
  const paperRewindAdmissionPending = useRef(false);
  const paperRewindStopAfterAdmission = useRef(false);
  const [paperStepChecking, setPaperStepChecking] = useState<{ id: string; stage: SavedPaperRestartStage } | null>(null);
  const paperStepCheckAbort = useRef<AbortController | null>(null);
  const [paperStepCheckError, setPaperStepCheckError] = useState<{ id: string; message: string } | null>(null);
  const [eli5Id, setEli5Id] = useState('');
  const [explainingIds, setExplainingIds] = useState<Set<string>>(() => new Set());
  const [eli5Error, setEli5Error] = useState('');
  const [eli5ErrorId, setEli5ErrorId] = useState('');
  const explainingRef = useRef<Set<string>>(new Set());
  const latestExplanationTarget = useRef('');
  const [confirmDeleteId, setConfirmDeleteId] = useState('');
  const [paperPopupPlacement, setPaperPopupPlacement] = useState({ left: 0, above: false });
  // One viewport-anchored confirmation for the target run. It cannot end up
  // underneath another paper card when the library reorders during a run.
  function showDiscardRunConfirmation(runId: string, button: HTMLElement) {
    const rect = button.getBoundingClientRect();
    const width = Math.min(280, window.innerWidth - 24);
    const height = 170;
    const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12));
    const top = Math.max(12, Math.min(
      window.innerHeight - rect.bottom >= height + 12 ? rect.bottom + 6 : rect.top - height - 6,
      window.innerHeight - height - 12,
    ));
    setConfirmDiscardRun({ runId, left, top });
  }
  useEffect(() => {
    if (!confirmDiscardRun) return;
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setConfirmDiscardRun(null); }
    };
    const onOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !discardRunPopup.current?.contains(event.target) &&
        !(event.target instanceof Element && event.target.closest('[data-paper-discard-trigger]'))) {
        setConfirmDiscardRun(null);
      }
    };
    document.addEventListener('keydown', onEscape);
    document.addEventListener('pointerdown', onOutside);
    return () => {
      document.removeEventListener('keydown', onEscape);
      document.removeEventListener('pointerdown', onOutside);
    };
  }, [confirmDiscardRun]);
  function positionPaperPopup(button: HTMLElement, width: number, height: number) {
    const bounds = button.getBoundingClientRect();
    const popupWidth = Math.min(width, window.innerWidth - 24);
    const left = Math.max(12, Math.min(bounds.left, window.innerWidth - popupWidth - 12));
    setPaperPopupPlacement({ left: left - bounds.left, above: window.innerHeight - bounds.bottom < height + 12 && bounds.top >= height + 12 });
  }
  const paperPopupStyle = {
    left: paperPopupPlacement.left,
    top: paperPopupPlacement.above ? 'auto' : 'calc(100% + 5px)',
    bottom: paperPopupPlacement.above ? 'calc(100% + 5px)' : 'auto',
  };
  useEffect(() => {
    if (!confirmDeleteId && !confirmDiscardDraft && !confirmRestartDraft && !confirmPlayRestartDraft) return;
    const cancelOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setConfirmDeleteId('');
        setConfirmDiscardDraft(false);
        setConfirmRestartDraft(false);
        setConfirmPlayRestartDraft(false);
      }
    };
    document.addEventListener('keydown', cancelOnEscape);
    return () => document.removeEventListener('keydown', cancelOnEscape);
  }, [confirmDeleteId, confirmDiscardDraft, confirmRestartDraft, confirmPlayRestartDraft]);
  useEffect(() => {
    if (!confirmRestartDraft && !confirmDiscardDraft && !confirmPlayRestartDraft) return;
    const dismissOutside = (event: PointerEvent) => {
      if (!(event.target instanceof Element)) return;
      const inStepPopup = paperStepRestartPopup.current?.contains(event.target);
      const inStepAnchor = paperStepRestartAnchor.current?.contains(event.target);
      if (!event.target.closest('.paper-remove-anchor') && !inStepPopup && !inStepAnchor) {
        setConfirmRestartDraft(false);
        setConfirmDiscardDraft(false);
      }
      // Play's confirmation closes when another paper action is chosen;
      // Start over's existing confirmation remains completely unchanged.
      if (!event.target.closest('.paper-play-tooltip')) {
        setConfirmPlayRestartDraft(false);
      }
    };
    document.addEventListener('pointerdown', dismissOutside);
    return () => document.removeEventListener('pointerdown', dismissOutside);
  }, [confirmRestartDraft, confirmDiscardDraft, confirmPlayRestartDraft]);
  useEffect(() => {
    if (guest) {
      const controller = new AbortController();
      void fetch(`/api/projects/papers?${new URLSearchParams({ path, include_runs: 'false' })}`, {
        signal: controller.signal, cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' },
      }).then(async response => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.error ?? 'Could not load papers.');
        if (!controller.signal.aborted) setPapers(Array.isArray(data.papers) ? data.papers : []);
      }).catch(cause => { if (!controller.signal.aborted) setError(errorMessage(cause)); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
      return () => controller.abort();
    }
    void refresh(undefined, initialPaperListing.current !== null);
    return () => request.current?.abort();
  }, [guest, path]);
  const lastPaperRevision = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (collaborationRevision === undefined || guest) return;
    if (lastPaperRevision.current === undefined) {
      lastPaperRevision.current = collaborationRevision;
      return;
    }
    if (lastPaperRevision.current === collaborationRevision) return;
    lastPaperRevision.current = collaborationRevision;
    void refresh(undefined, true);
  }, [collaborationRevision, guest, path]);
  useEffect(() => {
    if (!paperMenu) return;
    const dismiss = (event: PointerEvent) => { if (event.target instanceof Element && !event.target.closest('.paper-action-menu')) setPaperMenu(null); };
    document.addEventListener('pointerdown', dismiss);
    return () => document.removeEventListener('pointerdown', dismiss);
  }, [paperMenu]);
  useEffect(() => {
    // Contextual paper failures remain visible until Dismiss; lightweight
    // secondary feedback still expires automatically.
    if (!scoreError && !eli5Error && !copyError && !success) return;
    const timer = window.setTimeout(() => { setScoreError(''); setEli5Error(''); setCopyError(''); setSuccess(''); }, 8000);
    return () => window.clearTimeout(timer);
  }, [scoreError, eli5Error, copyError, success]);
  async function refresh(keepId?: string, silent = false) {
    const actionEpoch = paperActionEpoch.current;
    const refreshSerial = ++paperRefreshSerial.current;
    const obsolete = () => actionEpoch !== paperActionEpoch.current || refreshSerial !== paperRefreshSerial.current;
    // Preserve the open paper cards during a Start over refresh.
    if (!silent) setLoading(true);
    try {
      const query = new URLSearchParams({ path });
      // The library is independent of provider configuration, progress and
      // recovery. Show paper metadata immediately when its own request finishes.
      const listing = fetch(`/api/projects/papers?${new URLSearchParams({ path, include_runs: 'false' })}`, {
        cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' },
      }).then(async listResponse => {
        const list = await listResponse.json();
        if (!listResponse.ok) throw new Error(list.error ?? 'Could not load papers.');
        if (!obsolete()) {
          setPapers(Array.isArray(list.papers) ? list.papers as PaperSummary[] : []);
          setNextPaperNumber(typeof list.next_paper_number === 'number' ? list.next_paper_number : null);
          if (!silent) setLoading(false);
        }
        return list;
      });
      const [list, configResponse, progressResponse] = await Promise.all([
        listing,
        fetch(`/api/projects/proposals/config?${query}`, { cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } }),
        fetch(`/api/projects/papers/progress?${query}`, { cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } }),
      ]);
      const config = await configResponse.json();
      const savedProgress = progressResponse.ok ? await progressResponse.json() : null;
      if (obsolete()) return;
      const runs = (Array.isArray(savedProgress?.runs) ? savedProgress.runs
        : Array.isArray(list.runs) ? list.runs : []) as PaperRun[];
      setPaperRuns(runs);
      let currentId = selectedRunIdRef.current;
      const selectable = runs.filter(run => run.can_control && run.status !== 'complete' && !run.paper_id);
      if (!currentId && !newPaperRequested && selectable.length > 0) {
        currentId = selectable[selectable.length - 1].run_id;
        selectPaperRun(currentId);
      }
      const own = runs.find(run => run.run_id === currentId);
      if (own?.paper_id) {
        // Completed PDF lives in the published library, not as a second,
        // failed-looking unfinished card.
        selectPaperRun(null);
        setNewPaperRequested(false);
      }
      const ownedProgress = own?.progress ?? (runs.length ? null : savedProgress?.progress);
      const generationRunning = ['active', 'queued'].includes(ownedProgress?.status);
      if (!initialPaperActivityReported.current) {
        initialPaperActivityReported.current = true;
        const active = runs.some(run => run.status === 'active');
        const queued = runs.some(run => run.status === 'queued');
        const status = active ? 'active' : queued ? 'queued' : savedProgress?.progress?.status;
        onInitialActivity(status === 'active' || status === 'queued' ? status : null);
      }
      // A background collaborator refresh must not undo the newly selected
      // restart step's optimistic checkmark state before admission returns.
      if (!paperRewindAdmissionPending.current &&
          !(hasPaperStopIntent(currentId) && ['active', 'queued'].includes(ownedProgress?.status ?? '')))
        setPaperProgress(ownedProgress as PaperProgress | null);
      setPapers(list.papers as PaperSummary[]);
      setNextPaperNumber(typeof list.next_paper_number === 'number' ? list.next_paper_number : null);
      if (!configResponse.ok || !config.available) { setBinding(''); setModel(config.model ?? ''); setMode(config.mode ?? ''); setEffort(config.reasoning_effort ?? ''); setCheckpointMismatch(null); setRestartableCheckpoint(null); setRestartReady(false); setResetConfirm(false); setContinuationAvailable(false); setResumeDetails(null); }
      else {
        setBinding(config.binding); setModel(config.model); setMode(config.mode); setEffort(config.reasoning_effort);
        // An ordinary open has no pending paper work. Avoid rebuilding and
        // hashing the complete research snapshot until the user presses Play.
        // Keep the existing preflight for checkpoints, reset receipts, and
        // servers that do not advertise this optimization.
        if (progressResponse.ok && (own?.preflight_needed ?? savedProgress?.preflight_needed) === false) {
          setCheckpointMismatch(null);
          setRestartableCheckpoint(null);
          setRestartReady(false);
          setContinuationAvailable(false);
          setResumeDetails(null);
        } else {
        const params = new URLSearchParams({
          path, long_form: 'false', expected_project_id: projectId, expected_binding: config.binding,
          mode: config.mode, model: config.model, reasoning_effort: config.reasoning_effort,
          ...(currentId ? { run_id: currentId } : {}),
        });
        const preflightResponse = await fetch(`/api/projects/papers/preflight?${params}`, { cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } });
        const preflight = await preflightResponse.json();
        if (obsolete()) return;
        const resumable = Boolean(preflightResponse.ok && preflight.checkpoint_exists && preflight.resume_available);
        setRestartReady(Boolean(preflightResponse.ok && preflight.restart_ready && !generationRunning));
        setContinuationAvailable(resumable);
        setResumeDetails(resumable ? preflight : null);
        if (!generationRunning && preflightResponse.ok && preflight.checkpoint_exists && !preflight.resume_available && preflight.checkpoint_can_restart)
          setCheckpointMismatch(preflight);
        else setCheckpointMismatch(null);
        // A compatible checkpoint can be resumed OR deliberately restarted.
        // Never hide Start over merely because Continue is available.
        setRestartableCheckpoint(
          !generationRunning && preflightResponse.ok && preflight.checkpoint_exists &&
          preflight.checkpoint_can_restart ? preflight : null
        );
        }
      }
      // The cards render from summaries. Only fetch the full paper text when
      // its card is expanded, a deep link opens it, or an explicit operation
      // requests a particular saved paper. This avoids large paper payloads
      // during ordinary project navigation.
      const nextId = keepId ?? (expandedPaperId || undefined);
      if (nextId) {
        const response = await fetch(`/api/projects/papers/${encodeURIComponent(nextId)}?${query}`, { cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } });
        const record = await response.json();
        if (obsolete()) return;
        if (!response.ok) throw new Error(record.error ?? 'Could not open this paper version.');
        setSelected(record as PaperRecord);
      } else setSelected(null);
      if (!obsolete()) setError(!configResponse.ok || !config.available ? (config.message ?? 'Connect an eligible AI provider to author a paper.') : '');
    } catch (cause) { if (!obsolete()) setError(errorMessage(cause)); }
    finally {
      if (!initialPaperActivityReported.current) { initialPaperActivityReported.current = true; onInitialActivity(null); }
      if (!obsolete()) setLoading(false);
    }
  }
  useEffect(() => {
    // An immediate Stop can precede the first progress frame. Continue
    // polling its own durable run until cancellation is actually saved.
    if (!paperStopReconciliation && !['active', 'queued'].includes(paperProgress?.status ?? '')) return;
    let stopped = false;
    const poll = async () => {
      const actionEpoch = paperActionEpoch.current;
      try {
        const pending = paperStopAwaitingCheckpoint.current;
        const runId = pending ? pending.runId : selectedRunIdRef.current;
        const response = await fetch(`/api/projects/papers/progress?${new URLSearchParams({ path, ...(runId ? { run_id: runId } : {}) })}`, { cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } });
        const body = await response.json();
        if (!stopped && response.ok && actionEpoch === paperActionEpoch.current) {
          const runs = (body.runs ?? []) as PaperRun[];
          setPaperRuns(runs);
          const selected = runId ? runs.find(run => run.run_id === runId) : null;
          const next = (selected?.progress ?? body.progress ?? null) as PaperProgress | null;
          const isSelected = selectedRunIdRef.current === runId;
          if (isSelected && !(hasPaperStopIntent(runId) && ['active', 'queued'].includes(next?.status ?? '')))
            setPaperProgress(next);
          const stopping = paperStopAwaitingCheckpoint.current?.runId === runId
            && body.stop_pending === true;
          if (next && ['cancelled', 'interrupted', 'failed', 'complete'].includes(next.status) && !stopping) {
            if (isSelected) setPaperProgress(next);
            if (paperStopAwaitingCheckpoint.current?.runId === runId) {
              paperStopAwaitingCheckpoint.current = null;
              clearPaperStopIntent(runId);
              setPaperStopReconciliation(false);
              setPhase('');
              if (next?.status === 'cancelled')
                setSuccess('Paper generation stopped.');
            }
            if (next === null && isSelected) setNewPaperRequested(false);
            void refresh(undefined, true);
          }
        }
      } catch { /* Preserve persisted state until connectivity returns. */ }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 1000);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [path, paperProgress?.status, selectedRunId, paperStopReconciliation]);
  // Poll even when this collaborator is idle; another creator's Paper may
  // become active without changing the project's content revision.
  useEffect(() => {
    if (guest || collaborationRevision === undefined ||
        paperProgress?.status === 'active' || paperProgress?.status === 'queued') return;
    let stopped = false;
    const poll = async () => {
      const actionEpoch = paperActionEpoch.current;
      try {
        const runId = selectedRunIdRef.current;
        const response = await fetch(`/api/projects/papers/progress?${new URLSearchParams({ path, ...(runId ? { run_id: runId } : {}) })}`,
          { cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } });
        if (!response.ok || stopped) return;
        const body = await response.json();
        if (stopped || actionEpoch !== paperActionEpoch.current) return;
        const runs = (body.runs ?? []) as PaperRun[];
        setPaperRuns(runs);
        const chosen = runId ? runs.find(run => run.run_id === runId) : null;
        if (chosen) {
          const next = chosen.progress as PaperProgress | null;
          if (!(hasPaperStopIntent(runId) && ['active', 'queued'].includes(next?.status ?? '')))
            setPaperProgress(next);
          if (!hasPaperStopIntent(runId) && (next?.status === 'active' || next?.status === 'queued')) setDraftPaperExpanded(true);
        } else if (!runId && !newPaperRequested) {
          const own = runs.filter(run => run.can_control && run.status !== 'complete' && !run.paper_id);
          if (own.length) { selectPaperRun(own[own.length - 1].run_id); void refresh(undefined, true); }
        }
      } catch { /* Preserve the last known state during transient connectivity loss. */ }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 2000);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [guest, collaborationRevision, path, paperProgress?.status, selectedRunId, newPaperRequested]);
  // Notification deep links expand the exact saved paper (or the paused
  // draft) after initial hydration. Do not repeat this scroll on polling.
  const paperDeepLinkHandled = useRef(false);
  useEffect(() => {
    if (loading || paperDeepLinkHandled.current) return;
    const params = new URLSearchParams(window.location.search);
    const requested = params.get('reveal_paper');
    const requestedRun = params.get('reveal_paper_run');
    if (!requested && !requestedRun) return;
    if (requestedRun && !paperRuns.some(run => run.run_id === requestedRun)
      && selectedRunIdRef.current !== requestedRun) return;
    paperDeepLinkHandled.current = true;
    onSectionOpened();
    setExpanded(true);
    window.localStorage.setItem(`sigma.papersPane:${path}`, 'true');
    if (requestedRun) {
      if (selectedRunIdRef.current === requestedRun) setDraftPaperExpanded(true);
      else setExpandedOtherPaperRunIds(current => new Set(current).add(requestedRun));
    } else if (requested === 'draft') setDraftPaperExpanded(true);
    else if (requested && papers.some(paper => paper.paper_id === requested)) {
      setExpandedPaperId(requested);
      void openPaper(requested);
    }
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const element = requestedRun
        ? document.querySelector<HTMLElement>(`[data-paper-run="${CSS.escape(requestedRun)}"]`)
          ?? (selectedRunIdRef.current === requestedRun ? document.querySelector<HTMLElement>('.paper-draft-card') : null)
        : requested === 'draft'
        ? document.querySelector<HTMLElement>('.paper-draft-card')
        : Array.from(document.querySelectorAll<HTMLElement>('[data-paper-id]'))
            .find(item => item.dataset.paperId === requested);
      (element ?? document.getElementById('papers-heading'))?.scrollIntoView({ block: 'center' });
    }));
  }, [loading, papers, paperRuns, path, onSectionOpened]);
  async function fetchUnfinishedPaperSteps(runId: string | null, signal?: AbortSignal, allowActive = false): Promise<UnfinishedPaperRestartOptions> {
    const query = new URLSearchParams({ path });
    if (runId) query.set('run_id', runId);
    if (allowActive) query.set('allow_active', 'true');
    const response = await fetch(`/api/projects/papers/unfinished-checkpoints?${query}`,
      { cache: 'no-store', signal, headers: { 'X-Sigma-Error-Handled': 'true' } });
    const result = await readPaperResponse(response, 'Checking saved paper progress');
    if (!Array.isArray(result.stages) || typeof result.snapshot_sha256 !== 'string')
      throw new Error('The saved paper progress is unavailable.');
    const options = result as UnfinishedPaperRestartOptions;
    setUnfinishedStepOptions(previous => ({
      ...previous, [paperUnfinishedOptionsKey(runId)]: options,
    }));
    return options;
  }
  async function proposeUnfinishedPaperStepRestart(
    runId: string | null, number: number | null, stage: UnfinishedPaperRestartStage, anchor: HTMLButtonElement,
  ) {
    if (guest || unfinishedRestartBusy || unfinishedStepChecking || paperStepChecking) return;
    const key = paperUnfinishedOptionsKey(runId);
    if (!binding) {
      setUnfinishedStepCheckError({ key, message: 'Connect ChatGPT before restarting this paper.' });
      return;
    }
    paperStepRestartAnchor.current = anchor;
    setPaperStepRestart(null);
    setUnfinishedStepCheckError(null);
    // Like published papers, show the confirmation before a read-only lookup.
    setUnfinishedStepRestart({ runId, number, stage, snapshot_sha256: '', checking: true });
    setUnfinishedStepChecking({ key, stage });
    const controller = new AbortController();
    unfinishedStepCheckAbort.current = controller;
    try {
      const inFlight = paperRuns.some(run => run.run_id === runId && ['active', 'queued'].includes(run.status)) ||
        (selectedRunIdRef.current === runId && ['active', 'queued'].includes(paperProgress?.status ?? ''));
      const options = await fetchUnfinishedPaperSteps(runId, controller.signal, inFlight);
      if (controller.signal.aborted) return;
      const requestedStep = PAPER_UNFINISHED_STAGES.indexOf(stage);
      if (options.published_paper_id) {
        // Another window may have finished publication. Re-target the still
        // open confirmation to the durable published paper, not an old draft.
        let published = papers.find(item => item.paper_id === options.published_paper_id);
        if (!published) {
          const response = await fetch(`/api/projects/papers?${new URLSearchParams({ path, include_runs: 'false' })}`, {
            cache: 'no-store', signal: controller.signal, headers: { 'X-Sigma-Error-Handled': 'true' },
          });
          const latest = await readPaperResponse(response, 'Finding saved paper');
          if (controller.signal.aborted) return;
          setPapers(Array.isArray(latest.papers) ? latest.papers as PaperSummary[] : []);
          published = (latest.papers as PaperSummary[] | undefined)?.find(
            item => item.paper_id === options.published_paper_id,
          );
        }
        if (!published) throw new Error('Saved paper is unavailable; refresh this project.');
        setUnfinishedStepRestart(null);
        setUnfinishedStepChecking(null);
        if (requestedStep === 8 && published.pdf_available) proposePaperStepRescore(published, anchor);
        else void proposePaperStepRestart(published, publishedPaperTarget(requestedStep), anchor);
        void refresh(undefined, true);
        return;
      }
      const target = paperUnfinishedCheckpointForStep(requestedStep, options.stages);
      if (!options.stages.includes(target)) throw new Error('This paper has no verified restart checkpoint.');
      setUnfinishedStepRestart(current => current?.runId === runId && current.stage === stage
        ? { ...current, stage: target, snapshot_sha256: options.snapshot_sha256, checking: false } : current);
    } catch (cause) {
      if (controller.signal.aborted) return;
      const message = errorMessage(cause);
      if (runId && /no restart checkpoint|no usable restart checkpoint|no verified restart checkpoint/i.test(message)) {
        setUnfinishedStepRestart(current => current?.runId === runId
          ? { ...current, stage: 'started', snapshot_sha256: '', startFresh: true, checking: false } : current);
      } else setUnfinishedStepRestart(current => current?.runId === runId
        ? { ...current, checking: false, error: message } : current);
    } finally {
      if (unfinishedStepCheckAbort.current === controller) {
        unfinishedStepCheckAbort.current = null;
        setUnfinishedStepChecking(current => current?.key === key && current.stage === stage ? null : current);
      }
    }
  }
  async function confirmUnfinishedPaperStepRestart() {
    const proposed = unfinishedStepRestart;
    if (!proposed || proposed.checking || proposed.error || unfinishedRestartBusy || !binding) return;
    setUnfinishedStepRestart(null);
    setUnfinishedStepCheckError(null);
    setUnfinishedRestartBusy(true);
    const oldId = selectedRunIdRef.current;
    const oldProgress = paperProgress;
    const oldRequested = newPaperRequested;
    const nextStage = paperUnfinishedProgressStage(proposed.stage);
    const sourceProgress = oldId === proposed.runId ? paperProgress
      : paperRuns.find(run => run.run_id === proposed.runId)?.progress;
    const inFlight = paperRuns.some(run => run.run_id === proposed.runId &&
      ['active', 'queued'].includes(run.status)) ||
      (oldId === proposed.runId && ['active', 'queued'].includes(paperProgress?.status ?? ''));
    try {
      // Stop must be dispatched before the restart fence is armed, otherwise
      // cancelGeneration misinterprets it as a second Stop request.
      const stopAction = inFlight && proposed.runId ? stopPaperBeforeMutation(proposed.runId) : null;
      paperRewindAdmissionPending.current = true;
      paperRewindStopAfterAdmission.current = false;
      // Reuse the same unfinished run and show the requested stage immediately.
      // A saved paper instead creates a new attempt (see confirmPaperStepRestart).
      selectPaperRun(proposed.runId);
      setNewPaperRequested(true);
      setDraftPaperExpanded(true);
      setExpanded(true);
      onSectionOpened();
      setPaperProgress({
        ...sourceProgress, status: 'interrupted', stage: nextStage, resume_stage: nextStage,
        current: null, total: null,
        started_at: sourceProgress?.started_at ?? new Date().toISOString(),
        elapsed_seconds: sourceProgress?.elapsed_seconds ?? 0, detail: '',
      });
      if (stopAction) await stopAction;
      if (proposed.startFresh) {
        const stoppedDuringRestart = paperRewindStopAfterAdmission.current;
        paperRewindAdmissionPending.current = false;
        paperRewindStopAfterAdmission.current = false;
        setUnfinishedRestartBusy(false);
        if (stoppedDuringRestart) {
          setOptimisticPaperStop(null);
          void refresh(undefined, true);
          return;
        }
        if (proposed.runId) setResumeAfterActiveRewind(proposed.runId);
        else void generatePaper(false, null, true);
        return;
      }
      setContinuationAvailable(true);
      // Do not claim a checkpoint until the server has restored it.
      // A Stop receipt can become terminal a moment before its task releases
      // the operation lock. Retrying this provider-free request with the same
      // identity cannot replay or duplicate paid inference.
      const restartRequestId = crypto.randomUUID().replaceAll('-', '');
      let restored: any;
      for (let attempt = 0; attempt < 40; attempt++) {
        const response = await fetch('/api/projects/papers/unfinished-checkpoints', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
          body: JSON.stringify({
            path, run_id: proposed.runId, expected_project_id: projectId,
            expected_snapshot_sha256: proposed.snapshot_sha256,
            stage: proposed.stage, confirm_restart: true, request_id: restartRequestId,
          }),
        });
        try {
          restored = await readPaperResponse(response, 'Restarting unfinished paper');
          break;
        } catch (cause) {
          if (!inFlight || attempt === 39 ||
              !errorMessage(cause).includes('still releasing resources')) throw cause;
          await new Promise<void>(resolve => window.setTimeout(resolve, 250));
        }
      }
      if (restored.snapshot_sha256 !== proposed.snapshot_sha256 || restored.stage !== proposed.stage)
        throw new Error('The saved paper changed. Try restarting again.');
      if (restored.progress) setPaperProgress(restored.progress as PaperProgress);
      setUnfinishedStepOptions(current => {
        const next = { ...current };
        delete next[paperUnfinishedOptionsKey(proposed.runId)];
        return next;
      });
      setCheckpointMismatch(null);
      setRestartableCheckpoint(null);
      setResumeDetails(null);
      paperRewindAdmissionPending.current = false;
      if (paperRewindStopAfterAdmission.current) {
        paperRewindStopAfterAdmission.current = false;
        clearPaperStopIntent(proposed.runId);
        setPaperProgress(current => current ? {
          ...current, status: 'interrupted', stage: nextStage,
          detail: 'Ready to resume',
        } : current);
        void refresh(undefined, true);
        return;
      }
      // The confirmed action executes its step immediately. If this was an
      // active run, let its previous streaming request finish before the new
      // render dispatches Play; the current closure still has busy=true.
      setUnfinishedRestartBusy(false);
      if (proposed.runId) setResumeAfterActiveRewind(proposed.runId);
      else void generatePaper(false, null, true);
    } catch (cause) {
      paperRewindAdmissionPending.current = false;
      paperRewindStopAfterAdmission.current = false;
      clearPaperStopIntent(proposed.runId);
      selectPaperRun(oldId);
      setPaperProgress(oldProgress);
      setNewPaperRequested(oldRequested);
      setUnfinishedStepCheckError({
        key: paperUnfinishedOptionsKey(proposed.runId), message: errorMessage(cause),
      });
      void refresh(undefined, true);
    } finally {
      setUnfinishedRestartBusy(false);
    }
  }
  async function proposePaperStepRestart(paper: PaperSummary, stage: SavedPaperRestartStage, anchor: HTMLButtonElement) {
    if (guest || paperStepRestartBusy || paperStepChecking) return;
    paperStepRestartAnchor.current = anchor;
    setPaperStepCheckError(null);
    // Click first: show the truthful, requested step in the confirmation
    // immediately. A read-only checkpoint lookup can finish inside that dialog.
    // Never show "Restarting…" until the user actually confirms.
    setPaperStepRestart({ paper, stage, options: null, checking: true, error: '' });
    setPaperStepChecking({ id: paper.paper_id, stage });
    const controller = new AbortController();
    paperStepCheckAbort.current = controller;
    try {
      const response = await fetch(`/api/projects/papers/${encodeURIComponent(paper.paper_id)}/rewind?${new URLSearchParams({ path })}`,
        { cache: 'no-store', signal: controller.signal, headers: { 'X-Sigma-Error-Handled': 'true' } });
      const options = await readPaperResponse(response, 'Checking restart options');
      if (controller.signal.aborted) return;
      if (options.source_pdf_sha256 !== paper.pdf_sha256 || options.snapshot_sha256 !== paper.snapshot_sha256)
        throw new Error('The paper has changed. Reopen it before restarting.');
      const order: SavedPaperRestartStage[] = ['started', 'writing', 'validation', 'typesetting'];
      const available: SavedPaperRestartStage[] = Array.isArray(options.stages)
        ? options.stages.map((item: { id: SavedPaperRestartStage }) => item.id) : [];
      const selected = order.slice(0, order.indexOf(stage) + 1).reverse()
        .find(candidate => available.includes(candidate));
      if (!selected) throw new Error('This paper cannot restart from the selected step.');
      setPaperStepRestart(current => current?.paper.paper_id === paper.paper_id && current.stage === stage
        ? { ...current, stage: selected, options, checking: false, error: '' } : current);
    } catch (cause) {
      if (!controller.signal.aborted) setPaperStepRestart(current => current?.paper.paper_id === paper.paper_id
        ? { ...current, checking: false, error: errorMessage(cause) } : current);
    } finally {
      if (paperStepCheckAbort.current === controller) {
        paperStepCheckAbort.current = null;
        setPaperStepChecking(current => current?.id === paper.paper_id && current.stage === stage ? null : current);
      }
    }
  }
  function proposePaperStepRescore(paper: PaperSummary, anchor: HTMLButtonElement) {
    if (guest || scoringRef.current || paperStepRestartBusy || paperStepChecking) return;
    paperStepRestartAnchor.current = anchor;
    setPaperStepCheckError(null);
    // Scoring already validates the persisted PDF at execution time. Opening
    // the confirmation never requires a separate paper-list round trip.
    setPaperStepRestart({
      paper, stage: 'scoring',
      options: paper.pdf_available && paper.pdf_sha256 ? {
        source_pdf_sha256: paper.pdf_sha256,
        snapshot_sha256: paper.snapshot_sha256,
        include_diagrams: true,
      } : null,
      checking: false,
      error: paper.pdf_available && paper.pdf_sha256 ? '' : 'The saved PDF is unavailable. Reopen the paper before rescoring.',
    });
  }
  async function confirmPaperStepRestart() {
    const proposed = paperStepRestart;
    if (!proposed?.options || paperStepRestartBusy) return;
    paperActionEpoch.current++;
    if (proposed.stage === 'scoring') {
      setPaperStepRestart(null);
      setPaperStepCheckError(null);
      void scorePaper(proposed.paper, true);
      return;
    }
    if (!binding) {
      setPaperStepCheckError({ id: proposed.paper.paper_id, message: 'Connect an AI provider before restarting this paper.' });
      setPaperStepRestart(null);
      return;
    }
    // Confirm closes the card immediately; this NEW attempt has no
    // checkmarks at the selected step or later. The published bar is immutable.
    setPaperStepRestart(null);
    setPaperStepCheckError(null);
    setPaperStepRestartBusy(true);
    const runId = crypto.randomUUID().replaceAll('-', '');
    paperRewindAdmissionPending.current = true;
    paperRewindStopAfterAdmission.current = false;
    const priorRunId = selectedRunIdRef.current;
    const priorProgress = paperProgress;
    const priorNewPaperRequested = newPaperRequested;
    selectPaperRun(runId);
    setNewPaperRequested(true);
    setDraftPaperExpanded(true);
    setExpanded(true);
    onSectionOpened();
    setNewPaperToReveal(runId);
    setPaperProgress({
      status: 'interrupted', stage: rewindProgressStage(proposed.stage),
      current: null, total: null, started_at: new Date().toISOString(),
      elapsed_seconds: 0, detail: 'Preparing paper restart',
    });
    try {
      const response = await fetch(`/api/projects/papers/${encodeURIComponent(proposed.paper.paper_id)}/rewind`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
        body: JSON.stringify({
          path, expected_project_id: projectId, expected_binding: binding,
          source_pdf_sha256: proposed.options.source_pdf_sha256,
          expected_snapshot_sha256: proposed.options.snapshot_sha256,
          stage: proposed.stage, confirm_restart: true, run_id: runId,
        }),
      });
      const restored = await readPaperResponse(response, 'Preparing paper restart');
      if (restored.snapshot_sha256 !== proposed.options.snapshot_sha256)
        throw new Error('Restart evidence changed. Reopen the paper before trying again.');
      paperRewindAdmissionPending.current = false;
      selectPaperRun(restored.run_id ?? runId);
      if (paperRewindStopAfterAdmission.current) {
        // Stop was clicked during preparation. Do not make a provider call;
        // the newly persisted checkpoint is safe to Resume or Remove.
        paperRewindStopAfterAdmission.current = false;
        clearPaperStopIntent(runId);
        setPaperProgress(current => current ? {
          ...current, status: 'interrupted',
          detail: `Restored from Paper ${proposed.paper.paper_version} · ready to resume`,
        } : current);
        void refresh(undefined, true);
        return;
      }
      setNewPaperRequested(true);
      setDraftPaperExpanded(true);
      setCheckpointMismatch(null);
      setRestartableCheckpoint(null);
      setContinuationAvailable(false);
      setIncludeDiagramsAndTables(proposed.options.include_diagrams);
      window.localStorage.setItem('sigma.paper.diagrams:' + projectId, String(proposed.options.include_diagrams));
      // The restored attempt already has an authoritative run identity.
      // Skip the full list refresh here: it can reset selection before Play.
      setPaperStepRestartBusy(false);
      // React state is not synchronously updated by the setter above. Use
      // the archived rendering preference for this dispatch explicitly.
      setResumeAfterActiveRewind(restored.run_id ?? runId);
    } catch (cause) {
      paperRewindAdmissionPending.current = false;
      paperRewindStopAfterAdmission.current = false;
      clearPaperStopIntent(runId);
      selectPaperRun(priorRunId);
      setPaperProgress(priorProgress);
      setNewPaperRequested(priorNewPaperRequested);
      setPaperStepCheckError({ id: proposed.paper.paper_id, message: errorMessage(cause) });
      void refresh(undefined, true);
    } finally { setPaperStepRestartBusy(false); }
  }
  async function openPaper(id: string) {
    try {
      const response = await fetch(`/api/projects/papers/${encodeURIComponent(id)}?${new URLSearchParams({ path })}`, { cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } });
      const record = await response.json(); if (!response.ok) throw new Error(record.error ?? 'Could not open this paper version.');
      setSelected(record as PaperRecord); setError('');
    } catch (cause) { setError(errorMessage(cause)); }
  }
  async function readPaperResponse(response: Response, action: string): Promise<any> {
    const text = await response.text();
    let data: any;
    try { data = JSON.parse(text); } catch { data = null; }
    if (!response.ok) {
      const message = typeof data?.error === 'string' ? data.error
        : typeof data?.detail === 'string' ? data.detail
        : response.status >= 500
          ? `${action} failed because the server encountered an error (HTTP ${response.status}). Please retry.`
          : `${action} failed (HTTP ${response.status}).`;
      throw new Error(message);
    }
    if (!data || typeof data !== 'object') throw new Error(`${action} returned an invalid response.`);
    return data;
  }
  async function explainPaper(paper: PaperSummary) {
    if (explainingRef.current.has(paper.paper_id)) return;
    latestExplanationTarget.current = paper.paper_id;
    setEli5Error('');
    setEli5ErrorId('');
    // The currently open record already contains its archived explanation.
    // Reopening it should switch from balloon to Hooray in the same render.
    const cached = selected?.paper_id === paper.paper_id ? selected.eli5 : null;
    if (cached?.version === 2 && cached.source_sha256 === selected?.pdf_sha256
      && typeof cached.markdown === 'string' && cached.markdown.trim()) {
      setEli5Id(paper.paper_id);
      setExpandedPaperId(paper.paper_id);
      return;
    }
    // Acknowledge the balloon immediately, independently of other papers.
    explainingRef.current.add(paper.paper_id);
    setExplainingIds(current => new Set(current).add(paper.paper_id));
    try {
      const response = await fetch(`/api/projects/papers/${encodeURIComponent(paper.paper_id)}?${new URLSearchParams({ path })}`, { cache: 'no-store' });
      const record = await readPaperResponse(response, "Loading the paper");
      const saved = record.eli5;
      let markdown = saved?.version === 2 && saved?.source_sha256 === record.pdf_sha256 && typeof saved.markdown === 'string' ? saved.markdown.trim() : '';
      if (!markdown) {
        if (!binding) throw new Error('Connect an eligible AI provider to explain this paper.');
        // Fetching a paper is not generation. Show Explaining only while
        // the provider is actually asked to produce a missing explanation.
        const result = await fetch(`/api/projects/papers/${encodeURIComponent(paper.paper_id)}/eli5`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path, expected_project_id: projectId, expected_binding: binding }),
        });
        const data = await readPaperResponse(result, "Explaining this paper");
        if (typeof data.markdown !== "string" || !data.markdown.trim()) throw new Error("The explanation was empty.");
        markdown = data.markdown;
      }
      // Parallel balloon requests must not move the open card backward when
      // an older request completes after a newer click.
      if (latestExplanationTarget.current === paper.paper_id) {
        setSelected({ ...record, eli5: { version: 2, source_sha256: record.pdf_sha256, markdown } } as PaperRecord);
        setEli5Id(paper.paper_id);
        setExpandedPaperId(paper.paper_id);
      }
    } catch (cause) { setEli5ErrorId(paper.paper_id); setEli5Error(errorMessage(cause)); }
    finally {
      explainingRef.current.delete(paper.paper_id);
      setExplainingIds(current => {
        const next = new Set(current);
        next.delete(paper.paper_id);
        return next;
      });
    }
  }
  // Paper score access must be checked independently of the initial pane load:
  // reconnecting the AI account does not remount this pane.
  useEffect(() => {
    if (!scoreDialog) { setScoreConfig(null); return; }
    let active = true;
    const check = async () => {
      try {
        const response = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } });
        const config = await response.json();
        if (active) setScoreConfig({
          available: response.ok && config.available === true && !!config.binding,
          binding: response.ok && config.available === true ? (config.binding ?? '') : '',
          message: config.message ?? (response.ok ? 'Selected AI model is unavailable for scoring.' : 'Could not check scoring availability.'),
        });
      } catch (cause) {
        if (active) setScoreConfig({ available: false, binding: '', message: errorMessage(cause) });
      }
    };
    void check();
    window.addEventListener('focus', check);
    return () => { active = false; window.removeEventListener('focus', check); };
  }, [scoreDialog?.paperId, path, ai.info?.status, ai.info?.mode, ai.info?.active_account]);
  async function scorePaper(paper: PaperSummary, force = false) {
    setScoreError('');
    // Reading an existing score never depends on ongoing generation/scoring.
    if (paper.score && !force) { setScoreDialog({ paperId: paper.paper_id, score: paper.score }); return; }
    if (scoringRef.current) return;
    if (!paper.pdf_available) { setScoreError('A PDF is required before this paper can be scored.'); return; }
    scoringRef.current = true;
    setScoringId(paper.paper_id);
    try {
      const configResponse = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } });
      const config = await configResponse.json();
      if (!configResponse.ok || !config.available || !config.binding)
        throw new Error(config.message ?? 'Current AI model or connection is unavailable for scoring.');
      setBinding(config.binding);
      setScoreConfig({ available: true, binding: config.binding, message: config.message ?? '' });
      const response = await fetch(`/api/projects/papers/${encodeURIComponent(paper.paper_id)}/score`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, expected_project_id: projectId, expected_binding: config.binding, force }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Could not score the paper.');
      const score = result.score as PaperScore;
      setPapers(current => current.map(item => item.paper_id === paper.paper_id ? { ...item, score } : item));
      setScoreDialog({ paperId: paper.paper_id, score });
      setPaperProgress(current => current?.stage === 'score_failed'
        ? { ...current, stage: 'complete', status: 'complete' } : current);
      window.dispatchEvent(new Event('sigma-paper-scores-updated'));
    } catch (cause) {
      setScoreError(errorMessage(cause));
    } finally {
      scoringRef.current = false;
      setScoringId('');
    }
  }
  function confirmPaperRemoval(id: string, button: HTMLElement) { positionPaperPopup(button, 280, 180); setConfirmDeleteId(id); setPaperMenu(null); }

  async function removePaper(id: string) {
    if (!beginPaperRemoval(id)) return;
    setConfirmDeleteId('');
    setPaperRemovalErrors(current => ({ ...current, [id]: '' }));
    const wasExpanded = expandedPaperId === id;
    if (wasExpanded) setExpandedPaperId('');
    if (selected?.paper_id === id) setSelected(null);
    try {
      const response = await fetch(`/api/projects/papers/${encodeURIComponent(id)}?${new URLSearchParams({ path })}`, { method: 'DELETE' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Could not remove this paper version.');
      setPapers(current => current.filter(item => item.paper_id !== id));
      finishPaperRemoval(id, true);
    } catch (cause) {
      finishPaperRemoval(id, false);
      if (wasExpanded) setExpandedPaperId(id);
      setPaperRemovalErrors(current => ({ ...current, [id]: errorMessage(cause) }));
    }
  }
  async function copyPaper(id: string) {
    setCopyError('');
    try {
      const response = await fetch(`/api/projects/papers/${encodeURIComponent(id)}/txt?${new URLSearchParams({ path })}`, { cache: 'no-store' });
      if (!response.ok) throw new Error('Paper text could not be loaded.');
      await navigator.clipboard.writeText(await response.text());
      setCopiedPaperId(id); window.setTimeout(() => setCopiedPaperId(current => current === id ? '' : current), 1600);
    } catch { setCopyError('Could not copy the paper. Check browser clipboard permissions and try again.'); }
  }
  async function copyExplanation(id: string, markdown: string) {
    if (!markdown) return;
    setCopyError('');
    try {
      await navigator.clipboard.writeText(markdown);
      setCopiedExplanationId(id);
      window.setTimeout(() => setCopiedExplanationId(current => current === id ? '' : current), 1600);
    } catch {
      setCopyError('Could not copy the explanation. Check browser clipboard permissions and try again.');
    }
  }
  async function cancelGeneration(runId: string | null = selectedRunIdRef.current, throwOnFailure = false) {
    if (paperRewindAdmissionPending.current && runId === selectedRunIdRef.current) {
      paperActionEpoch.current++;
      paperStopIntentRef.current.add(runId ?? 'legacy');
      // A user can Stop before a restart receipt exists. Finish only the
      // provider-free checkpoint preparation, never auto-dispatch generation.
      paperRewindStopAfterAdmission.current = true;
      setOptimisticPaperStop({ runId });
      return;
    }
    const target = paperRuns.find(run => run.run_id === runId);
    if (paperStopPending.current || paperStopAwaitingCheckpoint.current?.runId === runId
      || hasPaperStopIntent(runId)
      || (!busy && !['active', 'queued'].includes(target?.status ?? paperProgress?.status ?? ''))) return;
    paperActionEpoch.current++;
    paperStopIntentRef.current.add(runId ?? 'legacy');
    window.dispatchEvent(new CustomEvent('sigma-run-stop-intent', { detail: { kind: 'paper', id: runId || 'pending' } }));
    if (runId === selectedRunIdRef.current && paperStartOptimistic && !paperSubmissionDispatched.current) {
      // Before dispatch, Stop simply cancels preparation. No run or provider
      // operation needs to be stopped, and no paid call is replayed.
      setOptimisticPaperStop({ runId });
      setPhase('Stopping paper…');
      deliberatePaperStop.current = true;
      request.current?.abort();
      return;
    }
    paperStopPending.current = true;
    deliberatePaperStop.current = true;
    // Stop intent hides the pulse, not the actual stage or durable run status.
    setOptimisticPaperStop({ runId });
    setPhase('Stopping paper…');
    setError('');
    try {
      let result: { stop_requested?: boolean; cancelled?: boolean } = {};
      for (let attempt = 0; attempt < 40; attempt++) {
        const response = await fetch('/api/projects/papers/cancel', {
          method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
          body: JSON.stringify({ path, run_id: runId, expected_project_id: projectId, expected_binding: binding || 'stop-only', request_only: true }),
        });
        result = await response.json();
        if (!response.ok) throw new Error('Could not cancel paper generation.');
        if (result.stop_requested || result.cancelled) break;
        // The paper was submitted but its worker has not yet been registered.
        // Preserve the Stop intent and retry without showing the Play button.
        await new Promise<void>(resolve => window.setTimeout(resolve, 250));
      }
      if (result.stop_requested) {
        // Stop is requested, not yet a completed cancellation. Keep the
        // progress pane polling until the backend saves its terminal status.
        paperStopAwaitingCheckpoint.current = { runId };
        setPaperStopReconciliation(true);
        if (runId === selectedRunIdRef.current) {
          deliberatePaperStop.current = true;
          request.current?.abort();
        }
      } else if (result.cancelled) {
        clearPaperStopIntent(runId);
        setPhase('');
        setSuccess('Paper generation stopped.');
        void refresh(selected?.paper_id, true);
      } else {
        // A missing stop receipt is not a successful Stop. Restore the
        // actual server state and surface the failure to the user.
        throw new Error('Stop did not reach the running paper. Try again.');
      }
    } catch (cause) {
      // Rejected Stop must restore the pulsing state and usable controls.
      clearPaperStopIntent(runId);
      window.dispatchEvent(new CustomEvent('sigma-run-stop-intent', { detail: { kind: 'paper', id: runId || 'pending', clear: true } }));
      setPhase('');
      setError(errorMessage(cause));
      void refresh(selected?.paper_id, true);
      if (throwOnFailure) throw cause;
    } finally {
      paperStopPending.current = false;
    }
  }

  async function stopPaperBeforeMutation(runId: string) {
    const run = paperRuns.find(item => item.run_id === runId);
    const running = run?.status === 'active' || run?.status === 'queued' ||
      (selectedRunIdRef.current === runId && ['active', 'queued'].includes(paperProgress?.status ?? ''));
    if (!running) return;
    if (run && !run.can_control) {
      throw new Error('Only the collaborator executing this paper can stop it.');
    }
    await cancelGeneration(runId, true);
    for (let attempt = 0; attempt < 120; attempt++) {
      const response = await fetch(`/api/projects/papers/progress?${new URLSearchParams({
        path, run_id: runId,
      })}`, { cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } });
      const latest = await readPaperResponse(response, 'Waiting for Paper to stop');
      if (['interrupted', 'cancelled', 'failed'].includes(latest.progress?.status)) return;
      await new Promise<void>(resolve => window.setTimeout(resolve, 250));
    }
    throw new Error('This paper is still stopping. Try again.');
  }

  async function discardDraft() {
    setConfirmDiscardDraft(false);
    const runId = selectedRunIdRef.current;
    if (runId) {
      await discardOtherRun(runId);
      return;
    }
    if (busy || request.current !== null || ['active', 'queued'].includes(paperProgress?.status ?? '')) return;
    if (!paperProgress && !restartableCheckpoint && !checkpointMismatch && !selectedRunIdRef.current) {
      setNewPaperRequested(false); setConfirmDiscardDraft(false); setResetConfirm(false);
      return;
    }
    setRemovingLegacyDraft(true);
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/projects/papers/discard', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
        body: JSON.stringify({ path, run_id: selectedRunIdRef.current, expected_project_id: projectId, expected_binding: binding || 'stop-only', confirm_discard: true }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Could not remove unfinished paper work.');
      selectPaperRun(null);
      setNewPaperRequested(false); setPaperProgress(null); setCheckpointMismatch(null);
      setRestartableCheckpoint(null); setContinuationAvailable(false); setResumeDetails(null);
      setResetConfirm(false); setConfirmDiscardDraft(false); setSuccess('');
      await refresh(selected?.paper_id);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); setRemovingLegacyDraft(false); }
  }

  async function discardOtherRun(runId: string) {
    if (!beginPaperRemoval(runId)) return;
    setConfirmDiscardRun(null);
    setConfirmDiscardDraft(false);
    setPaperRemovalErrors(current => ({ ...current, [runId]: '' }));
    const wasSelected = selectedRunIdRef.current === runId;
    const previousProgress = paperProgress;
    if (wasSelected) {
      selectPaperRun(null);
      setNewPaperRequested(false);
      setPaperProgress(null);
      setContinuationAvailable(false);
      setResumeDetails(null);
    }
    try {
      await stopPaperBeforeMutation(runId);
      const response = await fetch('/api/projects/papers/discard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
        body: JSON.stringify({
          path, run_id: runId, expected_project_id: projectId,
          expected_binding: binding || 'stop-only', confirm_discard: true,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Could not remove unfinished paper.');
      setPaperRuns(current => current.filter(run => run.run_id !== runId));
      finishPaperRemoval(runId, true);
      void refresh(undefined, true);
    } catch (cause) {
      finishPaperRemoval(runId, false);
      if (wasSelected && !selectedRunIdRef.current) {
        selectPaperRun(runId);
        setNewPaperRequested(true);
        setPaperProgress(previousProgress);
      }
      setPaperRemovalErrors(current => ({ ...current, [runId]: errorMessage(cause) }));
    }
  }

  async function restartCheckpoint() {
    const restartSource = checkpointMismatch ?? restartableCheckpoint;
    // Stopping a queued request can leave a terminal receipt without a
    // checkpoint. Start over must still clear that receipt without AI calls.
    const stoppedWithoutCheckpoint = !restartSource?.checkpoint_can_restart &&
      ['cancelled', 'failed', 'interrupted'].includes(paperProgress?.status ?? '');
    if (busy || !binding || (!restartSource?.checkpoint_can_restart && !stoppedWithoutCheckpoint)) return;
    const oldProgress = paperProgress;
    const oldRequested = newPaperRequested;
    // Confirmation closes before any request; leave a truthful, visible restart.
    setConfirmRestartDraft(false);
    setResetConfirm(false);
    paperRewindAdmissionPending.current = true;
    setBusy(true); setRestartingCheckpoint(true); setError(''); setSuccess(''); setPhase('');
    setNewPaperRequested(true);
    setDraftPaperExpanded(true);
    setPaperProgress({
      status: 'interrupted', stage: 'queued', resume_stage: 'queued',
      current: null, total: null, started_at: new Date().toISOString(),
      elapsed_seconds: 0, detail: '',
    });
    try {
      const restartingSavedWork = Boolean(restartSource?.checkpoint_can_restart);
      const response = await fetch(
        restartingSavedWork ? '/api/projects/papers/restart' : '/api/projects/papers/discard',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
          body: JSON.stringify(restartingSavedWork ? {
            path, run_id: selectedRunIdRef.current, expected_project_id: projectId, expected_binding: binding,
            expected_snapshot_sha256: restartSource.snapshot_sha256,
            // Match Generate's automatic long-form choice rather than
            // unconditionally forcing long-form on a restarted one-shot paper.
            long_form: false, confirm_restart: true,
          } : {
            path, run_id: selectedRunIdRef.current, expected_project_id: projectId, expected_binding: binding,
            confirm_discard: true,
          }),
        },
      );
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Could not restart this paper.');
      setCheckpointMismatch(null);
      setRestartableCheckpoint(null);
      setRestartReady(true);
      setResetConfirm(false);
      setConfirmRestartDraft(false);
      setContinuationAvailable(false);
      setResumeDetails(null);
      setPaperProgress(null);
      setNewPaperRequested(true);
      setDraftPaperExpanded(true);
      // The bar-and-arrow is a restart, not a reset requiring another Play.
      // Dispatch only after the provider-free checkpoint reset and refresh.
      await refresh(selected?.paper_id, true);
      const runId = selectedRunIdRef.current ?? crypto.randomUUID().replaceAll('-', '');
      selectPaperRun(runId);
      setNewPaperRequested(true);
      setPaperProgress({
        status: 'interrupted', stage: 'queued',
        current: null, total: null, started_at: new Date().toISOString(),
        elapsed_seconds: 0,
      });
      setResumeAfterActiveRewind(runId);
    } catch (cause) {
      setPaperProgress(oldProgress);
      setNewPaperRequested(oldRequested);
      setError(errorMessage(cause));
      void refresh(undefined, true);
    } finally {
      paperRewindAdmissionPending.current = false;
      setRestartingCheckpoint(false);
      setBusy(false);
    }
  }
  async function generatePaper(restartBeforePlay = false, recoverSection: number | null = null, resumeSelectedRun = false, explicitRunId?: string, includeDiagramsOverride?: boolean) {
    if (busy || !binding) {
      setUnfinishedStepCheckError({
        key: paperUnfinishedOptionsKey(explicitRunId ?? selectedRunIdRef.current),
        message: !binding
          ? 'Connect ChatGPT before starting this paper.'
          : 'Another paper action is finishing. Resume this paper when it becomes available.',
      });
      return;
    }
    const actionEpoch = ++paperActionEpoch.current;
    deliberatePaperStop.current = false;
    paperSubmissionDispatched.current = false;
    // Always resume the newly restored run, never a stale selected row.
    const runId = explicitRunId ?? selectedRunIdRef.current ?? crypto.randomUUID().replaceAll('-', '');
    selectPaperRun(runId);
    const controller = new AbortController(); request.current = controller;
    setPaperPlayIntent((continuationAvailable || resumeSelectedRun) && !restartBeforePlay ? 'resuming' : 'starting');
    generationErrorRunId.current = null;
    setBusy(true); setPhase('Compiling publication standards…'); setError(''); setSuccess(''); setDismissedPaperNoticeKey('');
    // Play's non-resumable checkpoint confirmation is a restart too.
    // Keep the same acknowledgment until live generation progress takes over.
    if (restartBeforePlay) setRestartingCheckpoint(true);
    let finishProvider = () => {};
    let requestDispatched = false;
    let providerCallsAttempted: number | undefined;
    try {
      if (restartBeforePlay) {
        // Play was explicitly confirmed on a non-resumable checkpoint. Do
        // not silently replay an uncertain paid one-shot request.
        const source = checkpointMismatch;
        if (!source?.checkpoint_can_restart) throw new Error('The stopped paper state changed; refresh before starting another attempt.');
        setPhase('Starting a new paper attempt…');
        const resetResponse = await fetch('/api/projects/papers/restart', {
          method: 'POST',
          signal: controller.signal,
          headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
          body: JSON.stringify({
            path, run_id: selectedRunIdRef.current, expected_project_id: projectId, expected_binding: binding,
            expected_snapshot_sha256: source.snapshot_sha256,
            long_form: false, confirm_restart: true,
          }),
        });
        const reset = await resetResponse.json();
        if (!resetResponse.ok) throw new Error(reset.error ?? 'Could not reset the stopped paper attempt.');
        setCheckpointMismatch(null);
        setRestartableCheckpoint(null);
        setRestartReady(true);
        setContinuationAvailable(false);
        setResumeDetails(null);
        setPaperProgress(null);
      }
      const preflightParams = new URLSearchParams({
        path, long_form: 'false', expected_project_id: projectId, expected_binding: binding,
        mode, model, reasoning_effort: effort, run_id: runId,
      });
      const preflightResponse = await fetch(`/api/projects/papers/preflight?${preflightParams}`, { cache: 'no-store', signal: controller.signal, headers: { 'X-Sigma-Error-Handled': 'true' } });
      const preflight = await preflightResponse.json();
      if (!preflightResponse.ok) throw new Error(preflight.error ?? 'Could not size the evidence snapshot.');
      setPaperPlayIntent(preflight.resume_available && !restartBeforePlay ? 'resuming' : 'starting');
      if (preflight.checkpoint_exists && !preflight.resume_available) {
        setCheckpointMismatch(preflight);
        throw new Error('Unfinished paper work belongs to different project evidence or AI settings. Review the message below before starting over.');
      }
      // A different account/billing connection must never silently take over
      // already-started paper work. Model/Thinking can change at the next call.
      let authorizedProviderChange = false;
      if (preflight.provider_change_requires_confirmation) {
        const savedModel = preflight.saved_provider_model ?? 'previous model';
        authorizedProviderChange = await new Promise<boolean>(resolve => {
          providerChangeResolver.current = resolve;
          setProviderChangePrompt({ savedModel, nextModel: model });
        });
        if (!authorizedProviderChange) throw new Error('Paper Resume cancelled. Work remains unchanged.');
      }
      if (preflight.resume_uses_saved_model && !authorizedProviderChange) {
        setPhase('Resuming work; the current Model/Thinking selection applies to the next AI call.');
      }
      const pendingRecovery: number[] = preflight.recovery_sections ?? [];
      if (recoverSection !== null &&
          (pendingRecovery.length !== 1 || pendingRecovery[0] !== recoverSection))
        throw new Error('The saved paper changed. Resume using its latest checkpoint.');
      finishProvider = beginProviderRequest('ai-paper');
      setPhase(preflight.draft_recovery_available
        ? 'Reusing the validated draft from the previous attempt; compiling its PDF…'
        : 'Compiling publication standards…');
      requestDispatched = true;
      paperSubmissionDispatched.current = true;
      const response = await fetch('/api/projects/papers', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' }, signal: controller.signal,
        body: JSON.stringify({ path, run_id: runId, expected_project_id: projectId, expected_binding: binding, expected_snapshot_sha256: preflight.snapshot_sha256, browser_presence_required: true, long_form: false, include_claim_details: includeClaimDetails, include_validation_notes: includeValidationNotes, include_research_excerpts: includeResearchExcerpts, include_sigma_issues: includeSigmaIssues, include_diagrams: includeDiagramsOverride ?? includeDiagramsAndTables,
          ...(pendingRecovery.length ? { authorized_recovery_sections: pendingRecovery } : {}),
          authorized_provider_change: authorizedProviderChange }) });
      if (!response.ok) {
        const failure = await response.json().catch(() => null);
        throw new Error(failure?.error ?? `Paper generation failed (${response.status}); no version was published.`);
      }
      if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body)
        throw new Error(`Paper generation failed with an invalid server response (${response.status}). No version was published.`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let result: { paper_id: string; generation?: PaperSummary['generation'] } | null = null;
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const frames = buffer.split('\n\n'); buffer = frames.pop() ?? '';
        for (const frame of frames) {
          const line = frame.split('\n').find(item => item.startsWith('data: '));
          if (!line) continue;
          const event = JSON.parse(line.slice(6));
          if (event.type === 'error') {
            if (Number.isInteger(event.provider_calls_attempted) && event.provider_calls_attempted >= 0)
              providerCallsAttempted = event.provider_calls_attempted;
            throw new Error(event.error ?? 'Paper generation failed.');
          }
          if (actionEpoch !== paperActionEpoch.current || hasPaperStopIntent(runId)) continue;
          if (event.type === 'complete') result = event.result as { paper_id: string };
          if (event.type === 'progress') {
            const nextProgress = { ...event, status: event.state === 'complete' ? 'complete' : 'active', activity_state: event.state } as PaperProgress;
            if (!paperRewindAdmissionPending.current) {
              if (restartBeforePlay) setRestartingCheckpoint(false);
              setPaperProgress(nextProgress);
              setPhase(paperProgressOperation(nextProgress));
            }
          }
          if (event.type === 'heartbeat') {
            if (event.progress && !paperRewindAdmissionPending.current) {
              if (restartBeforePlay) setRestartingCheckpoint(false);
              setPaperProgress(event.progress as PaperProgress);
            }
          }
        }
        if (done) break;
      }
      if (actionEpoch !== paperActionEpoch.current || hasPaperStopIntent(runId)) return;
      if (!result) throw new Error('Paper generation ended without a completed version. No version was published.');
      await refresh(result.paper_id);
      setNewPaperRequested(false);
      // Successful publication is already visible in the saved Paper list.
      // Avoid a redundant completion message; actionable review warnings stay
      // on the Paper itself.
      setSuccess('');
    } catch (cause) {
      if (controller.signal.aborted) {
        // An abort may also mean the dialog was unmounted. The server task
        // survives losing the stream; only the explicit Cancel action stops it.
        if (!deliberatePaperStop.current)
          setError('Paper stream disconnected. Check current progress and paper versions.');
      }
      // A deliberate Stop is still reconciling its checkpoint. The
      // progress poll will refresh at the terminal transition; an immediate
      // full preflight here can undo the fast acknowledgment.
      // A rejected preflight must restore Play without waiting for a full
      // Paper list/evidence refresh. Keep reconciliation best-effort.
      if (!deliberatePaperStop.current && actionEpoch === paperActionEpoch.current && !hasPaperStopIntent(runId))
        void refresh(selected?.paper_id, true);
      if (!controller.signal.aborted && actionEpoch === paperActionEpoch.current) {
        generationErrorRunId.current = runId;
        const message = errorMessage(cause);
        const disconnected = cause instanceof TypeError || message.includes('ended without a completed version');
        setError(disconnected && requestDispatched
          ? 'Connection interrupted. This paper may still be generating; check its status before trying again.'
          : requestDispatched && providerCallsAttempted === 0
            ? `${message} No provider request was made for this attempt. Paper versions and research evidence are unchanged; refresh the snapshot before retrying.`
            : requestDispatched
              ? `${message} Check My Work versions and your provider usage before generating again; a provider request may have completed or consumed allowance before the error.`
              : message);
      }
    } finally {
      if (deliberatePaperStop.current && !requestDispatched) {
        clearPaperStopIntent(runId);
        setPhase('');
        setNewPaperRequested(false);
        void refresh(undefined, true);
      }
      finishProvider();
      // An older response must not clear the control state of a newer run.
      if (request.current === controller) {
        request.current = null;
        paperSubmissionDispatched.current = false;
        deliberatePaperStop.current = false;
        setBusy(false);
      }
    }
  }
  const planningFallback = continuationAvailable && Boolean(resumeDetails?.planning_fallback_available);
  const planningRetry = continuationAvailable && resumeDetails !== null &&
    !resumeDetails.outline_complete && !resumeDetails.draft_recovery_available &&
    !planningFallback;
  const stoppingSelectedPaper = optimisticPaperStop !== null && optimisticPaperStop.runId === selectedRunId;
  // A pending Resume may still carry the checkpoint's interrupted or
  // cancelled status. The user's new Play intent takes precedence: show Stop
  // in the same position immediately, not the old disabled Play control.
  const paperStartOptimistic = !stoppingSelectedPaper && busy && request.current !== null && !deliberatePaperStop.current
    && !['active', 'queued'].includes(paperProgress?.status ?? '');
  const generationRunning = !stoppingSelectedPaper && (paperStepRestartBusy || paperStartOptimistic || (!deliberatePaperStop.current && (
    paperProgress?.status === 'active' || paperProgress?.status === 'queued' ||
    (request.current !== null && !['cancelled', 'interrupted', 'failed', 'complete'].includes(paperProgress?.status ?? ''))
  )));
  const generating = busy || generationRunning;
  // The brief transition after Stop is not a second-paper conflict. A Play
  // control can only advertise concurrency as its disabled reason when a
  // still-active job really blocks dispatch.
  const paperPlayBlocked = !generationRunning && !stoppingSelectedPaper &&
    ['active', 'queued'].includes(paperProgress?.status ?? '');
  const paperRestartPending = !!resumeAfterActiveRewind && resumeAfterActiveRewind === selectedRunId;
  const paperPlayDisabled = stoppingSelectedPaper || generating || paperRestartPending || loading || !binding || paperPlayBlocked;
  const paperPlayTooltip = stoppingSelectedPaper ? 'Finishing paper stop'
    : paperPlayBlocked
    ? 'This paper is already generating'
    : busy
      ? paperProgress?.status === 'cancelled' ? 'Finishing paper stop' :
        request.current ? 'Starting paper generation' : 'Paper action in progress'
      : loading ? 'Loading paper controls'
      : !binding ? 'Connect an AI provider to generate a paper'
      : checkpointMismatch ? 'Start a new paper attempt (confirmation required)'
      : continuationAvailable ? 'Resume paper generation' : 'Generate paper';
  const canStartOver = !restartReady && !generationRunning && !stoppingSelectedPaper &&
    (Boolean(checkpointMismatch?.checkpoint_can_restart || restartableCheckpoint?.checkpoint_can_restart) ||
     ['cancelled', 'failed', 'interrupted'].includes(paperProgress?.status ?? ''));
  // A completed paper does not reserve the next draft for its previous author.
  // Existing unfinished work remains creator-only; any collaborator may start
  // genuinely new work (the server reserves ownership before dispatch).
  const selectedRun = paperRuns.find(run => run.run_id === selectedRunId);
  const otherPaperRuns = paperRuns.filter(run =>
    run.run_id !== selectedRunId && run.status !== 'complete' && !run.paper_id &&
    !hiddenRemovalIds.has(run.run_id)
  );
  const unfinishedDraftPresent = continuationAvailable || Boolean(checkpointMismatch) ||
    Boolean(restartableCheckpoint) || (paperProgress != null && paperProgress.status !== 'complete');
  const canControlDraft = paperStepRestartBusy || (selectedRun ? selectedRun.can_control
    : !viewerEmail || !unfinishedDraftPresent || (draftCreatorEmail
      ? viewerEmail === draftCreatorEmail : viewerEmail === projectOwnerEmail));
  const canResumeDraft = selectedRun ? (selectedRun.can_resume ?? selectedRun.can_control) : canControlDraft;
  const canRemoveDraft = selectedRun ? (selectedRun.can_remove ?? selectedRun.can_control) : canControlDraft;
  const activeDraftCreator = selectedRun?.creator_email || draftCreatorEmail;
  const draftVersion = selectedRun?.number ?? nextPaperNumber ?? (Math.max(0, ...papers.map(paper => paper.paper_version)) + 1);
  // The unreserved next number can race other collaborators. Display a number
  // only once the server has allocated this run's authoritative number.
  const assignedPaperNumber = selectedRun?.number ?? null;
  const draftDisplayTitle = assignedPaperNumber !== null ? `Paper ${assignedPaperNumber}` : 'New paper';
  const orderedPapers = [...papers].filter(paper => !hiddenRemovalIds.has(paper.paper_id))
    .sort((a, b) => b.paper_version - a.paper_version);
  const paperProgressFailure = paperStepRestartBusy ? ''
    : paperProgress?.status === 'failed' ? paperProgress.failure_reason ?? '' : '';
  // A durable published paper supersedes the failed authoring receipt. Errors
  // for that run cannot remain in the project-wide contextual notice.
  const errorRunPublished = !!generationErrorRunId.current &&
    paperRuns.some(run => run.run_id === generationErrorRunId.current && !!run.paper_id);
  const rawPaperNotice = paperUserMessage(error || paperProgressFailure);
  const informationalPause = /browser disconnect|connection interrupted|connection (was )?lost|browser (was )?closed|work can be continued after reopening|unfinished section needs explicit recovery authorization/i.test(rawPaperNotice);
  const paperNoticeMessage = selectedRun?.paper_id || errorRunPublished || informationalPause
    ? '' : rawPaperNotice;
  const paperNoticeKey = [
    paperProgress?.started_at ?? '',
    paperProgress?.status ?? '',
    paperProgress?.failure_reason ?? '',
    paperProgress?.detail ?? '',
  ].join('|');
  const paperNoticeCopy = providerInterruptionCopy(paperNoticeMessage);
  const paperNoticeLength = (paperNoticeCopy?.title ?? 'Paper generation stopped').length
    + (paperNoticeCopy?.description ?? paperErrorSummary(paperNoticeMessage)).length
    + (paperNoticeCopy?.next?.length ?? 0);
  const paperNoticeSize = paperNoticeLength <= 90 ? 'short' : paperNoticeLength <= 190 ? 'medium' : 'long';
  const showPaperNotice = Boolean(paperNoticeMessage) && dismissedPaperNoticeKey !== paperNoticeKey && !generating;
  const showDraftPaper = !guest && !removingLegacyDraft && !selectedRun?.paper_id &&
    !hiddenRemovalIds.has(selectedRunId ?? '') && (
    newPaperRequested || generating || restartReady || continuationAvailable ||
    (paperProgress != null && paperProgress.status !== 'complete') ||
    (selectedRun != null && selectedRun.status !== 'complete')
  );
  const allPapersRunning = paperRuns.some(run => run.status === 'active' && !hasPaperStopIntent(run.run_id))
    || generationRunning && paperProgress?.status !== 'queued';
  const allPapersQueued = !allPapersRunning && paperRuns.some(run => run.status === 'queued' && !hasPaperStopIntent(run.run_id));
  const activePaperRunIds = [
    ...new Set([
      ...paperRuns.filter(run => run.status === 'active' && !hasPaperStopIntent(run.run_id)).map(run => run.run_id),
      ...(generationRunning && selectedRunId ? [selectedRunId] : []),
    ]),
  ];
  const activePaperRunIdsKey = activePaperRunIds.join('|');
  const selectedUnfinishedOptions = unfinishedStepOptions[paperUnfinishedOptionsKey(selectedRunId)];
  // Fetch checkpoint capabilities only when an unfinished bar is expanded.
  // Never hydrate large work records on every progress heartbeat.
  useEffect(() => {
    if (guest || !expanded || unfinishedRestartBusy) return;
    const controller = new AbortController();
    const requested: (string | null)[] = [];
    const stopped = (status?: string) => !!status && ['interrupted', 'cancelled', 'failed'].includes(status);
    if (showDraftPaper && draftPaperExpanded && canResumeDraft && stopped(paperProgress?.status)
      && !unfinishedStepOptions[paperUnfinishedOptionsKey(selectedRunId)])
      requested.push(selectedRunId);
    for (const run of otherPaperRuns) {
      if (expandedOtherPaperRunIds.has(run.run_id) && run.can_resume && stopped(run.status)
        && !unfinishedStepOptions[run.run_id]) requested.push(run.run_id);
    }
    for (const runId of requested) {
      void fetchUnfinishedPaperSteps(runId, controller.signal).catch(() => {
        // An older or incomplete checkpoint may have no restart boundaries.
        // Play/Resume and Remove remain available independently.
      });
    }
    return () => controller.abort();
  }, [
    path, guest, expanded, draftPaperExpanded, selectedRunId,
    paperProgress?.status, showDraftPaper, canResumeDraft, paperRuns,
    expandedOtherPaperRunIds, unfinishedStepOptions, unfinishedRestartBusy,
  ]);
  // Live collaborator statuses must refresh independently of revision
  // changes. Only lightweight progress sidecars are read, never saved PDFs.
  useEffect(() => {
    if (guest || !expanded) return;
    const controller = new AbortController();
    let pending = false;
    const pollRuns = async () => {
      if (pending || controller.signal.aborted) return;
      pending = true;
      try {
        const response = await fetch(`/api/projects/papers/progress?${new URLSearchParams({ path })}`, {
          signal: controller.signal, cache: 'no-store',
          headers: { 'X-Sigma-Error-Handled': 'true' },
        });
        if (!response.ok) return;
        const data = await response.json() as { runs?: PaperRun[] };
        if (!controller.signal.aborted && Array.isArray(data.runs)) setPaperRuns(data.runs);
      } catch { /* A transient poll failure must not hide known activity. */ }
      finally { pending = false; }
    };
    void pollRuns();
    const interval = window.setInterval(() => void pollRuns(), 3000);
    return () => { controller.abort(); window.clearInterval(interval); };
  }, [path, guest, expanded]);

  // The step-bar and icon controls share these actions, including every
  // confirmation and creator authorization check. Do not duplicate dispatch.
  const beginPaperFromControl = (anchor: HTMLButtonElement) => {
    providerChangeAnchor.current = anchor;
    setDraftPaperExpanded(true);
    if (checkpointMismatch) {
      positionPaperPopup(anchor, 280, 180);
      setConfirmRestartDraft(false); setConfirmDiscardDraft(false); setConfirmPlayRestartDraft(true);
    } else void generatePaper();
  };
  const startOverPaperFromControl = (anchor: HTMLButtonElement) => {
    paperStepRestartAnchor.current = anchor;
    setPaperStepRestart(null);
    setConfirmDiscardDraft(false);
    // Local, single-user projects do not have a reserved run ID. Their
    // established checkpoint reset remains valid; collaboration-backed
    // papers use the unified truthful step restart controller.
    if (!selectedRunIdRef.current || !paperRuns.some(run => run.run_id === selectedRunIdRef.current)) {
      setConfirmRestartDraft(true);
      return;
    }
    void proposeUnfinishedPaperStepRestart(
      selectedRunIdRef.current, assignedPaperNumber, 'started', anchor,
    );
  };
  // A single dispatcher performs every confirmed restart after React has
  // committed the restored run and current model settings. No silent busy exit.
  useEffect(() => {
    if (!resumeAfterActiveRewind || busy || unfinishedRestartBusy || paperStepRestartBusy) return;
    const runId = resumeAfterActiveRewind;
    setResumeAfterActiveRewind(null);
    if (!binding) {
      setUnfinishedStepCheckError({
        key: paperUnfinishedOptionsKey(runId),
        message: 'Connect ChatGPT to resume this paper.',
      });
      return;
    }
    void generatePaper(false, null, true, runId);
  }, [resumeAfterActiveRewind, busy, unfinishedRestartBusy, paperStepRestartBusy, binding]);

  const resumeOtherPaperRun = (run: PaperRun, anchor?: HTMLButtonElement) => {
    if (anchor) providerChangeAnchor.current = anchor;
    selectPaperRun(run.run_id);
    setPaperProgress(run.progress as PaperProgress | null);
    setNewPaperRequested(true);
    setDraftPaperExpanded(true);
    // Use the explicit run ID; the state setter above is asynchronous.
    void generatePaper(false, null, true, run.run_id);
  };
  useEffect(() => {
    onRunningChange(allPapersRunning, activePaperRunIds);
    return () => onRunningChange(false, []);
    // The joined IDs carry run identity without retriggering this effect for
    // unrelated rendering changes to the array.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allPapersRunning, activePaperRunIdsKey, onRunningChange]);
  useEffect(() => { onQueuedChange(allPapersQueued); return () => onQueuedChange(false); }, [allPapersQueued, onQueuedChange]);
  return <section className={`workspace-pane papers-pane ai-paper-dialog${expanded ? "" : " is-collapsed"}`} aria-labelledby="papers-heading">
    {providerChangePrompt && createPortal(
      <div ref={providerChangePopup} className="paper-step-restart-popup" role="dialog"
        aria-label="Confirm AI connection change" aria-modal="false"
        style={providerChangePlacement
          ? { left: providerChangePlacement.left, top: providerChangePlacement.top }
          : { left: 12, top: 12, visibility: 'hidden' }}>
        <p>Continue this paper with {providerChangePrompt.nextModel} and the current AI connection?</p>
        <div className="session-remove-confirm-actions">
          <button type="button" className="text-view-link" onClick={() => answerProviderChange(true)}>Confirm</button>
          <button type="button" className="text-view-link" onClick={() => answerProviderChange(false)}>Cancel</button>
        </div>
      </div>, document.body
    )}
    <header className="workspace-pane-heading papers-pane-heading">
      <h2 id="papers-heading" tabIndex={-1}><button type="button" className="workspace-section-disclosure" data-tooltip={`${expanded ? "Collapse" : "Expand"} Papers section`} aria-expanded={expanded} aria-controls="papers-pane-content" onClick={() => { if (!expanded) onSectionOpened(); setExpanded(value => { window.localStorage.setItem(`sigma.papersPane:${path}`, String(!value)); return !value; }); }}><DisclosureChevron expanded={expanded}/>Papers</button></h2>
      <div className="papers-heading-actions strategy-heading-actions">
        {confirmNewPaper ? <>
          <button type="button" className="text-view-link session-start-link" disabled={loading || busy} onClick={() => {
            if (guest) { setConfirmNewPaper(false); setGuestPaperPreview(true); return; }
            setConfirmNewPaper(false); selectPaperRun(crypto.randomUUID().replaceAll('-', ''));
            setPaperProgress(null); setNewPaperRequested(true); setDraftPaperExpanded(true);
            setCheckpointMismatch(null); setRestartableCheckpoint(null); setRestartReady(false);
            setContinuationAvailable(false); setResumeDetails(null); void generatePaper();
          }}>Start Paper</button>
          <button type="button" className="text-view-link session-start-link" disabled={loading} onClick={() => setConfirmNewPaper(false)}>Cancel</button>
        </> : <>
          <button type="button" className="text-view-link papers-header-action papers-new-action sigma-heading-icon-action" aria-label="New paper" data-tooltip="New paper" disabled={loading || busy} onClick={() => {
            if (guest) { setGuestPaperPreview(true); return; }
            if (!expanded) onSectionOpened(); setExpanded(true);
            window.localStorage.setItem(`sigma.papersPane:${path}`, 'true');
            setConfirmNewPaper(true);
          }}><CirclePlusIcon/></button>
        </>}
        <span className="paper-includes-anchor">
          <button ref={includeButtonRef} type="button" className="text-view-link papers-header-action papers-include-action sigma-heading-icon-action" aria-label="Include in paper" data-tooltip="Include in paper" aria-haspopup="dialog" aria-expanded={includeOptionsOpen} aria-controls="paper-include-options" disabled={loading || (!guest && confirmNewPaper) || busy} onClick={() => includeOptionsOpen ? setIncludeOptionsOpen(false) : openIncludeOptions()}><SlidersSettingsIcon/></button>
          {includeOptionsOpen && <div ref={includePopupRef} id="paper-include-options" className={`paper-includes-dialog${includePopupAbove ? ' paper-includes-dialog-above' : ''}`} role="dialog" aria-modal="false" aria-labelledby="paper-includes-title" style={{ left: includePopupOffset, maxHeight: includePopupMaxHeight }}>
      <div className="paper-includes-dialog-heading"><h3 id="paper-includes-title">Include in paper</h3><DialogDismissButton label="Close paper inclusion options" onClick={() => { setIncludeOptionsOpen(false); includeButtonRef.current?.focus(); }}/></div>
      <fieldset className="ai-paper-includes">

        <legend className="sr-only">Include</legend>
        <div className="ai-paper-options">
          <label className="ai-paper-details"><input type="checkbox" checked={includeDiagramsAndTables} disabled={generating} onChange={event => (window.localStorage.setItem('sigma.paper.diagrams:' + projectId, String(event.target.checked)), setIncludeDiagramsAndTables(event.target.checked))}/>Diagrams and tables</label>
          <label className="ai-paper-details"><input type="checkbox" checked={includeClaimDetails} disabled={generating} onChange={event => (window.localStorage.setItem('sigma.paper.claims:' + projectId, String(event.target.checked)), setIncludeClaimDetails(event.target.checked))}/>Claim details</label>
          <label className="ai-paper-details"><input type="checkbox" checked={includeValidationNotes} disabled={generating} onChange={event => (window.localStorage.setItem('sigma.paper.validation:' + projectId, String(event.target.checked)), setIncludeValidationNotes(event.target.checked))}/>Research issues and limitations</label>
          <label className="ai-paper-details"><input type="checkbox" checked={includeResearchExcerpts} disabled={generating} onChange={event => (window.localStorage.setItem('sigma.paper.excerpts:' + projectId, String(event.target.checked)), setIncludeResearchExcerpts(event.target.checked))}/>Research excerpts</label>
        </div>

      </fieldset>
          </div>}
        </span>
      </div>
      <p className="section-count">{papers.length + otherPaperRuns.length + (showDraftPaper ? 1 : 0)} {papers.length + otherPaperRuns.length + (showDraftPaper ? 1 : 0) === 1 ? "paper" : "papers"}</p>
    </header>

    {guestPaperPreview && <GuestFeatureCard title="Generate a research paper"
      message="SIGMA uses project research to gather evidence, draft and validate sections, proofread, produce a PDF, and score the result. Research findings still need human verification."
      onClose={() => setGuestPaperPreview(false)}/>}
    {guestExplainPreview && <GuestFeatureDialog title="Explain this paper"
      message="With member access and ChatGPT, SIGMA can summarize a paper in simpler language, explain its claims and limitations, and keep that explanation alongside the paper. An AI explanation is not an independent validation."
      onClose={() => setGuestExplainPreview(false)}/>}
    {guestScorePreview && <GuestFeatureDialog title="Score a research paper"
      message="With authorized SIGMA access and ChatGPT, SIGMA evaluates a PDF against its research, correctness, readability, evidence and visual-quality rubric. Scores are provisional and are not proof of scientific correctness."
      onClose={() => setGuestScorePreview(false)}/>}
    {showPaperNotice && <SessionNotice key={paperNoticeKey} number={draftVersion}
      title={paperNoticeCopy?.title ?? 'Paper generation stopped'}
      kind={`research-pause-guidance paper-contextual-error paper-contextual-error--${paperNoticeSize}`}
      ariaLabel="Paper generation feedback"
      dismissLabel="Dismiss paper generation notice"
      onDismiss={() => { setDismissedPaperNoticeKey(paperNoticeKey); setError(''); generationErrorRunId.current = null; }}>
      <p>{paperNoticeCopy ? paperNoticeCopy.description : paperErrorSummary(paperNoticeMessage)}</p>
      {paperNoticeCopy && <p><strong>Next:</strong> {paperNoticeCopy.next}</p>}
    </SessionNotice>}
    <div id="papers-pane-content" hidden={!expanded} className="papers-pane-content">
      <div className="ai-paper-body">
      <>

      {scoreError && <p role="alert" className="error paper-score-error-card">{scoreError} <DialogDismissButton label="Dismiss paper score error" onClick={() => setScoreError('')}/></p>}
      {loading && <p>Loading papers…</p>}

      {(showDraftPaper || otherPaperRuns.length > 0 || (!loading && papers.length > 0)) && <section className="saved-paper-library" aria-label="Papers">
        {showDraftPaper && <article className="saved-paper-card paper-draft-card" aria-label={draftDisplayTitle} data-paper-version={assignedPaperNumber ?? undefined}>
          <div className="saved-paper-row"><div className="saved-paper-heading">
            <SavedPaperTitle title={draftDisplayTitle} itemLabel="paper in progress" expanded={draftPaperExpanded} controls="paper-draft-content" onToggle={() => setDraftPaperExpanded(value => !value)} copyName="paper text" copied={false} onCopy={() => {}} copyInTitle={false}
              badge={!stoppingSelectedPaper && (paperRestartPending || paperStepRestartBusy || paperStartOptimistic || paperProgress?.status === 'active' || paperProgress?.status === 'queued') ? <span className={`research-running-indicator paper-title-activity${paperRestartPending || (!paperStartOptimistic && paperProgress?.status === 'queued') ? ' paper-queued-indicator' : ''}`} aria-label={paperStepRestartBusy ? 'Preparing paper restart' : paperStartOptimistic ? (paperPlayIntent === 'resuming' ? 'Paper resuming' : 'Paper starting') : paperProgress?.status === 'queued' ? 'Paper queued' : 'Paper generating'} data-tooltip={paperStepRestartBusy ? 'Preparing paper restart' : paperStartOptimistic ? (paperPlayIntent === 'resuming' ? 'Resuming paper' : 'Starting paper') : formatRunAttribution({ kind: 'paper', number: assignedPaperNumber, creator: activeDraftCreator, model: paperProgress?.model || model, thinking: paperProgress?.reasoning_effort || effort, mode: 'hover' })}/> : undefined}
              actions={<>
                {!generationRunning && canResumeDraft && <span className="paper-remove-anchor paper-play-tooltip" data-tooltip={paperPlayTooltip}><button type="button" className="text-view-link text-view-icon workspace-icon-button process-control session-mini-process-control paper-draft-process-control" aria-label={continuationAvailable ? (assignedPaperNumber !== null ? `Resume Paper ${assignedPaperNumber}` : 'Resume paper') : 'Generate paper'} disabled={paperPlayDisabled} onClick={event => beginPaperFromControl(event.currentTarget)}><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M6 3.8v12.4L16 10 6 3.8Z"/></svg></button>
                  {confirmPlayRestartDraft && <div className="paper-remove-actions" style={paperPopupStyle}><div className="research-stop-confirm" role="group" aria-label="Confirm new paper generation attempt">
                    <p>Start a new paper attempt?</p>
                    <div className="session-remove-confirm-actions">
                      <button type="button" className="text-view-link" disabled={busy} onClick={() => { setConfirmPlayRestartDraft(false); void generatePaper(true); }}>Confirm</button>
                      <button type="button" className="text-view-link" disabled={busy} onClick={() => setConfirmPlayRestartDraft(false)}>Cancel</button>
                    </div>
                  </div></div>}
                </span>}
                {generationRunning && canControlDraft && <button type="button" className="text-view-link text-view-icon workspace-icon-button process-control session-mini-process-control paper-draft-process-control" aria-label={assignedPaperNumber !== null ? `Stop Paper ${assignedPaperNumber}` : 'Stop paper generation'} data-tooltip={stoppingSelectedPaper ? 'Stopping paper' : 'Stop paper generation'} disabled={loading || stoppingSelectedPaper} onClick={() => void cancelGeneration()}><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5h10v10H5z"/></svg></button>}
                {canStartOver && canResumeDraft && <span className="paper-remove-anchor">
                  <button type="button" className="text-view-link text-view-icon workspace-icon-button paper-draft-restart" aria-label="Start over on paper generation" data-tooltip="Start over on paper generation" disabled={busy || loading || !binding} onClick={event => startOverPaperFromControl(event.currentTarget)}><svg viewBox="0 0 20 20" aria-hidden="true" fill="currentColor"><path d="M3 4h2v12H3zM16 4.25v11.5L7 10z"/></svg></button>

                </span>}
                {canRemoveDraft && (!generationRunning || canControlDraft) && <span className="paper-remove-anchor">
                  <button type="button" className="text-view-link text-view-icon workspace-icon-button paper-remove-button" aria-label={assignedPaperNumber !== null ? `Remove unfinished Paper ${assignedPaperNumber}` : 'Remove unfinished paper'} data-tooltip="Remove unfinished paper" disabled={loading} onClick={event => { positionPaperPopup(event.currentTarget, 280, 180); setConfirmRestartDraft(false); setConfirmDiscardDraft(true); }}><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" aria-hidden="true"><path d="M8 8 16 16M16 8 8 16"/></svg></button>
                  {confirmDiscardDraft && <div className="paper-remove-actions" style={paperPopupStyle}><div className="research-stop-confirm" role="group" aria-label="Confirm removal of unfinished paper">
                    <p>{generationRunning ? 'Stop and remove this paper?' : 'Remove this paper?'}</p>
                    {paperRemovalErrors[selectedRunId ?? 'legacy'] && <p role="alert" className="ai-paper-warning">{paperUserMessage(paperRemovalErrors[selectedRunId ?? 'legacy'])}</p>}
                    <div className="session-remove-confirm-actions">
                      <button type="button" className="text-view-link"  onClick={() => void discardDraft()}>Confirm</button>
                      <button type="button" className="text-view-link" onClick={() => setConfirmDiscardDraft(false)}>Cancel</button>
                    </div>
                  </div></div>}
                </span>}
              </>}/>
          </div></div>
          <PaperTimeline expanded={draftPaperExpanded}
            metadata={<>
              {formatRunAttribution({
                kind: 'paper', creator: activeDraftCreator || viewerEmail,
                model: paperProgress?.model || selectedRun?.model || model,
                thinking: paperProgress?.reasoning_effort || selectedRun?.thinking || effort,
              }) || 'Paper metadata unavailable'}
              {!paperRestartPending && ' · '}{paperRestartPending ? '' : stoppingSelectedPaper ? 'Stopping'
                : paperStartOptimistic ? (paperPlayIntent === 'resuming' ? 'Resuming' : 'Starting')
                : paperProgress?.status === 'active' ? 'Generating'
                : paperProgress?.status === 'queued' ? 'Queued'
                : paperProgress?.status === 'interrupted' ? 'Interrupted'
                : paperProgress?.status === 'cancelled' ? 'Stopped'
                : paperProgress?.status === 'failed' ? 'Failed'
                : 'Ready'}
              {' · Elapsed '}{savedPaperElapsed(Math.max(0, paperProgress?.elapsed_seconds ?? 0))}
            </>}
            message={stoppingSelectedPaper ? 'Stopping...'
              : paperRestartPending || paperStepRestartBusy || restartingCheckpoint ||
                unfinishedRestartBusy ? 'Restarting...'
              : paperProgress?.status === 'cancelled' ? 'Generation stopped'
              : paperStartOptimistic ? null
              : paperProgress?.status === 'failed' ? 'Generation failed'
              : paperProgress?.status === 'interrupted' && paperProgress.detail?.startsWith('Restored from Paper ')
                ? 'Ready to resume'
              : paperProgress?.status === 'interrupted' ? 'Generation interrupted' : undefined}
            progress={paperProgress && (paperProgress.status === 'active' || paperProgress.status === 'queued')
              ? paperProgress
              : { ...(paperProgress ?? selectedRun?.progress ?? {}),
                  resume_stage: paperProgress?.resume_stage ??
                    selectedUnfinishedOptions?.resume_stage ?? selectedRun?.progress?.resume_stage }}
            onSelectStep={!guest && (canResumeDraft || canControlDraft)
              ? (step, anchor) => {
                if (!paperProgress && !selectedRunId) beginPaperFromControl(anchor);
                else void proposeUnfinishedPaperStepRestart(
                  selectedRunId, assignedPaperNumber, unfinishedPaperTarget(step), anchor,
                );
              } : undefined}
          />
          {paperRemovalErrors[selectedRunId ?? 'legacy'] && <p role="alert" className="ai-paper-warning">{paperUserMessage(paperRemovalErrors[selectedRunId ?? 'legacy'])}</p>}
        
        {unfinishedStepCheckError?.key === paperUnfinishedOptionsKey(selectedRunId) &&
          <PaperStepFeedback message={unfinishedStepCheckError.message} onDismiss={() => setUnfinishedStepCheckError(null)}/>}
          <div id="paper-draft-content" className="paper-draft-content" hidden={!draftPaperExpanded}>
      {checkpointMismatch && !generating && <p className="ai-paper-restart-notice" role="status">{checkpointMismatch.incomplete_one_shot
        ? 'This paper cannot resume; use Play to start a new attempt.'
        : 'Research or AI settings changed; use Play to start a new attempt.'}</p>}



          </div>
        </article>}
        {otherPaperRuns.map(run => <article key={run.run_id} className="saved-paper-card paper-draft-card" data-paper-run={run.run_id} aria-label={`Paper ${run.number}`}>
          <div className="saved-paper-row">
            <div className="saved-paper-heading">
              <div className="saved-paper-title-line">
                <button type="button" className="saved-paper-expand" aria-label={`${expandedOtherPaperRunIds.has(run.run_id) ? 'Collapse' : 'Expand'} steps for Paper ${run.number}`}
                  aria-expanded={expandedOtherPaperRunIds.has(run.run_id)} aria-controls={`paper-run-steps-${run.run_id}`}
                  onClick={() => setExpandedOtherPaperRunIds(current => {
                    const next = new Set(current);
                    if (next.has(run.run_id)) next.delete(run.run_id); else next.add(run.run_id);
                    return next;
                  })}><DisclosureChevron expanded={expandedOtherPaperRunIds.has(run.run_id)}/></button>
                <div className="saved-paper-title-content">
                  <div className="saved-paper-title-first-line">
                    <h4 className="saved-paper-title">Paper {run.number}</h4>
                    <span className="saved-paper-title-tools">
              {!hasPaperStopIntent(run.run_id) && (run.status === 'active' || run.status === 'queued') && <span className={`research-running-indicator paper-title-activity${run.status === 'queued' ? ' paper-queued-indicator' : ''}`}
                aria-label={run.status === 'queued' ? 'Paper queued' : 'Paper generating'}
                data-tooltip={formatRunAttribution({ kind: 'paper', number: run.number, creator: run.creator_email, model: run.progress?.model || run.model, thinking: run.progress?.reasoning_effort || run.thinking, mode: 'hover' })}/>}
              {run.can_resume && (!['active', 'queued', 'complete'].includes(run.status) || hasPaperStopIntent(run.run_id)) && <button type="button"
                className="text-view-link text-view-icon workspace-icon-button process-control session-mini-process-control paper-draft-process-control"
                aria-label={`Resume Paper ${run.number}`} data-tooltip="Resume paper generation" disabled={busy || loading || !binding || hasPaperStopIntent(run.run_id)}
                onClick={event => resumeOtherPaperRun(run, event.currentTarget)}>
                <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M6 3.8v12.4L16 10 6 3.8Z"/></svg>
              </button>}
              {!guest && run.can_remove && (run.can_control || !['active', 'queued'].includes(run.status)) && <span className="paper-remove-anchor">
                <button type="button" className="text-view-link text-view-icon workspace-icon-button paper-remove-button"
                  aria-label={`Remove unfinished Paper ${run.number}`} data-tooltip="Remove unfinished paper" data-paper-discard-trigger="true" disabled={loading}
                  onClick={event => showDiscardRunConfirmation(run.run_id, event.currentTarget)}>
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" aria-hidden="true"><path d="M8 8 16 16M16 8 8 16"/></svg>
                </button>

              </span>}
              {run.can_control && !hasPaperStopIntent(run.run_id) && (run.status === 'active' || run.status === 'queued') && <button type="button"
                className="text-view-link text-view-icon workspace-icon-button process-control session-mini-process-control paper-draft-process-control"
                aria-label={`Stop Paper ${run.number}`} data-tooltip={optimisticPaperStop?.runId === run.run_id ? 'Stopping paper' : 'Stop paper generation'} disabled={optimisticPaperStop?.runId === run.run_id} onClick={() => void cancelGeneration(run.run_id)}>
                <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5h10v10H5z"/></svg>
              </button>}
                    </span>
                  </div>
                  {unfinishedStepChecking?.key === run.run_id && <span className="paper-real-title paper-draft-title" role="status">Finding checkpoint…</span>}
                </div>
              </div>
            </div>
            <PaperTimeline expanded={expandedOtherPaperRunIds.has(run.run_id)}
              detail={optimisticPaperStop?.runId === run.run_id ? null : run.progress?.detail}
              metadata={<>
                {formatRunAttribution({
                  kind: 'paper', creator: run.creator_email,
                  model: run.progress?.model || run.model,
                  thinking: run.progress?.reasoning_effort || run.thinking,
                }) || 'Paper metadata unavailable'}
                {' · '}{hasPaperStopIntent(run.run_id) ? 'Stopping' : run.status === 'active' ? 'Generating' : run.status === 'queued' ? 'Queued'
                  : run.status === 'interrupted' ? 'Interrupted'
                  : run.status === 'cancelled' ? 'Stopped' : run.status === 'failed' ? 'Failed' : 'Saved'}
                {' · Elapsed '}{savedPaperElapsed(Math.max(0, run.progress?.elapsed_seconds ?? 0))}
              </>}
              progress={run.progress}
              onSelectStep={!guest && (run.can_resume || run.can_control)
                ? (step, anchor) => void proposeUnfinishedPaperStepRestart(
                    run.run_id, run.number, unfinishedPaperTarget(step), anchor,
                  ) : undefined}
            />
            {paperRemovalErrors[run.run_id] && <p role="alert" className="ai-paper-warning">{paperRemovalErrors[run.run_id]}</p>}
              {unfinishedStepCheckError?.key === run.run_id &&
                <PaperStepFeedback message={unfinishedStepCheckError.message} onDismiss={() => setUnfinishedStepCheckError(null)}/>}
            <div id={`paper-run-steps-${run.run_id}`} hidden={!expandedOtherPaperRunIds.has(run.run_id)}/>
          </div>
        </article>)}
        {!loading && orderedPapers.map(paper => <article className="saved-paper-card" key={paper.paper_id} data-paper-id={paper.paper_id}>
        <div className="saved-paper-row">
          <div className="saved-paper-heading">
            <SavedPaperTitle title={`Paper ${paper.paper_version}`} itemLabel="paper" expanded={expandedPaperId === paper.paper_id} controls={`saved-paper-body-${paper.paper_id}`} onToggle={() => { if (expandedPaperId === paper.paper_id) setExpandedPaperId(''); else { setExpandedPaperId(paper.paper_id); if (selected?.paper_id !== paper.paper_id) void openPaper(paper.paper_id); } }} copyName="paper text" copied={copiedPaperId === paper.paper_id} onCopy={() => void copyPaper(paper.paper_id)} copyInTitle={false} badge={paper.score != null && paper.score.total >= HIGH_SCORING_PAPER_THRESHOLD ? <span className="recent-title-annotation recent-title-star paper-title-star" aria-label={HIGH_SCORING_PAPER_TOOLTIP} data-tooltip={HIGH_SCORING_PAPER_TOOLTIP} data-tooltip-follow-cursor="true">★</span> : undefined} beforeCopy={paper.pdf_available ? <a className="paper-real-title paper-title-open-link" data-tooltip-follow-cursor="true" href={`/api/projects/papers/${encodeURIComponent(paper.paper_id)}/pdf?${new URLSearchParams({ path, open_in_browser: 'true' })}`} target="_blank" rel="noopener noreferrer" onClick={event => openReusableTab(event, `sigma-paper:${path}:${paper.paper_id}`)} aria-label={`View paper: ${paper.title} in a browser tab`} data-tooltip="View paper in a new browser tab">{paper.title}</a> : <span className="paper-real-title">{paper.title}</span>}
              actions={<>
                {eli5Id === paper.paper_id
                  ? <button type="button" className="ai-paper-eli5-balloon ai-paper-eli5-thanks" aria-label="Thanks for the explanation" data-tooltip="Thanks for the explanation" onClick={() => setEli5Id('')}><svg className="ai-paper-eli5-hooray" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m3 21 4.7-12 7.3 7.3L3 21Z" fill="currentColor" fillOpacity=".2"/><path d="m3 21 4.7-12 7.3 7.3L3 21ZM7.7 9l7.3 7.3"/><path d="M12 3h.01M20 4h.01M21 14h.01M15 2v2m5 5 2-1m-6 4 2 2m-8-8 1-2M17 7c-2 1-3 3-3 5M7 4c2 0 3 1 4 3"/></svg></button>
                  : explainingIds.has(paper.paper_id)
                  ? <span className="ai-paper-explaining" role="status"><span aria-hidden="true">⌛</span> Explaining...</span>
                  : <button type="button" className="ai-paper-eli5-balloon" data-tooltip="Explain it to me like I'm 5" aria-label="Explain it to me like I'm 5" onClick={() => guest ? setGuestExplainPreview(true) : void explainPaper(paper)}><svg viewBox="0 0 24 30" width="20" height="26" fill="currentColor" aria-hidden="true"><path d="M12 1.6C6.5 1.6 3.4 5.7 3.4 11.7c0 5.5 3.6 10 8.6 10.6 5-.6 8.6-5.1 8.6-10.6 0-6-3.1-10.1-8.6-10.1Z"/><path d="m9.5 22.3 2.5 3 2.5-3Z"/><path d="M12 25c-2 1.2 3.1 2.5 0 4.5" fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round"/></svg></button>}
                {paper.pdf_available && <a className="paper-view-pdf-icon text-view-link text-view-icon workspace-icon-button" href={`/api/projects/papers/${encodeURIComponent(paper.paper_id)}/pdf?${new URLSearchParams({ path, open_in_browser: 'true' })}`} target="_blank" rel="noopener noreferrer" onClick={event => openReusableTab(event, `sigma-paper:${path}:${paper.paper_id}`)} aria-label="View paper in a new browser tab" data-tooltip="View paper in a new browser tab"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M13 3.5H6a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-7"/><path d="M14 3.5h6.5V10M20.5 3.5l-9 9"/></svg></a>}
                <span className="paper-action-menu">
                  <button type="button" className="text-view-link text-view-icon workspace-icon-button paper-download-button" aria-label={`Download ${paper.title}`} data-tooltip="Download paper" aria-haspopup="menu" aria-expanded={paperMenu?.paperId === paper.paper_id && paperMenu.kind === 'download'} onClick={event => { positionPaperPopup(event.currentTarget, 145, 100); setPaperMenu(current => current?.paperId === paper.paper_id && current.kind === 'download' ? null : { paperId: paper.paper_id, kind: 'download' }); }}><svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg></button>
                  {paperMenu?.paperId === paper.paper_id && paperMenu.kind === 'download' && <span className="paper-action-popover" style={paperPopupStyle} role="menu" aria-label={`Download ${paper.title}`} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); setPaperMenu(null); } }}>
                    {paper.pdf_available && <a role="menuitem" href={`/api/projects/papers/${encodeURIComponent(paper.paper_id)}/pdf?${new URLSearchParams({ path })}`} download={`${paper.download_basename}.pdf`} onClick={() => setPaperMenu(null)}>Download PDF paper</a>}
                    <a role="menuitem" href={`/api/projects/papers/${encodeURIComponent(paper.paper_id)}/tex?${new URLSearchParams({ path })}`} download={`${paper.download_basename}.tex`} onClick={() => setPaperMenu(null)}>Download LaTeX source</a>
                  </span>}
                </span>
                {!guest && (!viewerEmail || viewerEmail === projectOwnerEmail || artifactAuthors?.[paper.paper_id] === viewerEmail) && <span className="paper-remove-anchor">
                  <button type="button" className="text-view-link text-view-icon workspace-icon-button paper-remove-button" aria-label={`Remove Paper ${paper.paper_version}`} data-tooltip={`Remove Paper ${paper.paper_version}`}  onClick={event => confirmPaperRemoval(paper.paper_id, event.currentTarget)}><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" aria-hidden="true"><path d="M8 8 16 16M16 8 8 16"/></svg></button>
                  {confirmDeleteId === paper.paper_id && <div className="paper-remove-actions" style={paperPopupStyle}><div className="research-stop-confirm" role="group" aria-label={`Confirm removal of ${paper.title}`}>
                    <p>Remove paper {paper.paper_version} and its PDF?</p>
                    <div className="session-remove-confirm-actions">
                      <button type="button" className="text-view-link" data-tooltip={`Confirm removal of Paper ${paper.paper_version}`}  onClick={() => void removePaper(paper.paper_id)}>Confirm</button>
                      <button type="button" className="text-view-link" onClick={() => setConfirmDeleteId('')}>Cancel</button>
                    </div>
                  </div></div>}
                </span>}
              </>}/>
            <PaperTimeline expanded={expandedPaperId === paper.paper_id} message={scoringId === paper.paper_id ? null : undefined} metadata={<><span>{dateLabel(paper.created_at)}</span>{typeof paper.generation.generation_elapsed_seconds === 'number' && Number.isFinite(paper.generation.generation_elapsed_seconds) && paper.generation.generation_elapsed_seconds >= 0 && <><span className="paper-meta-dot" aria-hidden="true"> · </span><span>Elapsed {savedPaperElapsed(paper.generation.generation_elapsed_seconds)}</span></>}<span className="paper-meta-dot" aria-hidden="true"> · </span>{(artifactAuthors?.[paper.paper_id] || paper.created_by) ? <span className="artifact-attribution">{formatRunAttribution({ kind: 'paper', creator: artifactAuthors?.[paper.paper_id] || paper.created_by, ...(() => { const last = latestPaperModel(paper.generation); return { model: last.model, thinking: last.thinking }; })() })}</span> : <span>{paperModelThinkingLabel(paper.generation)}</span>}<span className="paper-meta-dot" aria-hidden="true"> · </span><button type="button" className="text-view-link paper-score-link paper-see-scoring-link paper-meta-score-action paper-inline-score" aria-busy={scoringId === paper.paper_id} disabled={!!scoringId} onClick={() => guest && !paper.score ? setGuestScorePreview(true) : void scorePaper(paper)}>{scoringId === paper.paper_id ? 'Scoring…' : paper.score ? `Score ${paper.score.total}/100` : 'Score'}</button></>}
              progress={{
                status: scoringId === paper.paper_id ? 'active' : paper.score ? 'complete' : 'interrupted',
                stage: scoringId === paper.paper_id ? 'scoring' : paper.score ? 'complete' : 'score_failed',
                current: null, total: null, started_at: paper.created_at,
                elapsed_seconds: paper.generation.generation_elapsed_seconds ?? 0,
              }}
              onSelectStep={!guest && !scoringId
                ? (step, anchor) => {
                  if (step === 8 && paper.pdf_available) void proposePaperStepRescore(paper, anchor);
                  else void proposePaperStepRestart(paper, publishedPaperTarget(step), anchor);
                } : undefined}/>
            {paperRemovalErrors[paper.paper_id] && <p role="alert" className="ai-paper-warning">{paperUserMessage(paperRemovalErrors[paper.paper_id])}</p>}
            {paper.generation.publication_status === 'needs_review' && <p className="ai-paper-warning" role="status">{paperReviewLabel(paper.generation)}</p>}
          </div>
          {copyError && <p className="error" role="alert">{copyError}</p>}
        </div>
        {eli5Error && eli5ErrorId === paper.paper_id && <p className="error" role="alert">{eli5Error}</p>}
          {paperStepCheckError?.id === paper.paper_id && <PaperStepFeedback message={paperStepCheckError.message} onDismiss={() => setPaperStepCheckError(null)}/>}
        <div id={`saved-paper-body-${paper.paper_id}`} hidden={expandedPaperId !== paper.paper_id}>
          {paperStepRestart?.paper.paper_id === paper.paper_id && createPortal(
            <div ref={paperStepRestartPopup} className="paper-step-restart-popup" role="dialog"
              aria-label="Confirm paper restart" aria-modal="false"
              style={paperStepRestartPlacement
                ? { left: paperStepRestartPlacement.left, top: paperStepRestartPlacement.top }
                : { left: 12, top: 12, visibility: 'hidden' }}>
              <p>{paperStepRestart.stage === 'scoring'
                ? `Rescore paper ${paper.paper_version}?`
                : paperStepRestart.stage === 'started'
                  ? 'Restart paper from beginning?'
                  : `Restart paper ${paper.paper_version} at ${paperRestartStepName(paperStepRestart.stage)}?`}</p>
              {paperStepRestart.error && <p role="alert" className="ai-paper-warning">{paperUserMessage(paperStepRestart.error)}</p>}
              <div className="session-remove-confirm-actions">
                <button type="button" className="text-view-link" disabled={!paperStepRestart.options || paperStepRestartBusy || (!binding && paperStepRestart.stage !== 'scoring')} onClick={() => void confirmPaperStepRestart()}>Confirm</button>
                <button type="button" className="text-view-link" onClick={dismissPaperStepRestart}>Cancel</button>
              </div>
            </div>, document.body
          )}
          {expandedPaperId === paper.paper_id && selected?.paper_id === paper.paper_id && <article className="ai-paper-preview">
        {eli5Id === paper.paper_id && selected.eli5?.source_sha256 === selected.pdf_sha256
          ? <div className="ai-paper-eli5-output"><Suspense fallback={<p>{selected.eli5?.markdown ?? ""}</p>}><RenderedMarkdown body={selected.eli5?.markdown ?? ""} questionHeadingAction={<CopyToClipboardButton name="explaination" copied={copiedExplanationId === paper.paper_id} onCopy={() => void copyExplanation(paper.paper_id, selected.eli5?.markdown ?? '')}/>}/></Suspense></div>
          : <><h3 className="ai-paper-preview-title">{selected.draft.title}<span className="ai-paper-preview-title-copy"><CopyToClipboardButton name="paper text" copied={copiedPaperId === paper.paper_id} onCopy={() => void copyPaper(paper.paper_id)}/></span></h3>
        {selected.generation.publication_status === 'needs_review' && <p role="status" className="ai-paper-warning"><strong>{paperReviewLabel(selected.generation)}.</strong> {selected.generation.proofreading?.review_reason ?? 'Inspect the archived TeX and PDF diagnostics.'}</p>}
        <p><strong>Abstract.</strong> {selected.draft.abstract}</p>
        <p className="settings-hint">Abstract claim links: {selected.draft.abstract_claim_ids.join(', ') || 'None'}</p>
        <section aria-label="Paper writing source material used"><h4>Paper writing source material used</h4>
          {selected.generation.writing_sources?.length ? <ul>{selected.generation.writing_sources.map(source => <li key={source.sha256}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a> <span className="settings-hint">({source.tier} · {source.branch})</span></li>)}</ul> : <p className="settings-hint">No external writing guidance recorded for this version.</p>}
          <p className="settings-hint">Writing methodology only, not evidence for research claims. Selection: {selected.generation.writing_source_selection || 'not recorded'}.</p>
        </section>
        <h4>Problem framing</h4>{selected.draft.problem_framing.map((text, index) => <p key={`framing-${index}`}>{text}</p>)}
        <p className="settings-hint">Claim links: {selected.draft.problem_framing_claim_ids.join(', ') || 'None'}</p>
        <h4>Methods and evidence</h4>{selected.draft.methods.map((text, index) => <p key={`method-${index}`}>{text}</p>)}
        <p className="settings-hint">Claim links: {selected.draft.methods_claim_ids.join(', ') || 'None'}</p>
        <p><strong>Snapshot.</strong> SHA-256 {selected.snapshot_sha256} · {selected.snapshot.sources.length} stable evidence sources</p>
         <p><strong>Generated.</strong> {selected.generation.model} ({selected.generation.mode}) · {dateLabel(selected.created_at)}{typeof selected.generation.generation_elapsed_seconds === 'number' && Number.isFinite(selected.generation.generation_elapsed_seconds) ? ` · Total elapsed: ${Math.floor(selected.generation.generation_elapsed_seconds / 60)}m ${String(Math.floor(selected.generation.generation_elapsed_seconds % 60)).padStart(2, '0')}s` : ''}{selected.generation.long_form ? ` · ${selected.generation.evidence_batch_count} evidence batches · ${selected.generation.provider_calls_attempted} calls this run · ${selected.generation.provider_calls_prior_runs} prior-run calls · ${selected.generation.provider_calls_lifetime_total} lifetime calls` : ''}</p>
        {!!selected.generation.omitted_evidence?.length && <details><summary>Evidence fields omitted from the generated index ({selected.generation.evidence_fields_omitted})</summary>{selected.generation.omitted_evidence.map(item => <p className="ai-paper-warning" key={item.field_ref}><code>{item.source_ref}{item.field}</code>: {item.reason}</p>)}</details>}
        {!!selected.generation.reduction_source_refs_omitted?.length && <details><summary>Sources omitted during index reduction ({selected.generation.reduction_source_refs_omitted.length})</summary>{selected.generation.reduction_source_refs_omitted.map(source => <p className="ai-paper-warning" key={source}><code>{source}</code></p>)}<p className="settings-hint">The complete original source records remain in the archived snapshot.</p></details>}
        {!!selected.generation.evidence_conflicts?.length && <details><summary>Potential conflicts and gaps identified by the evidence index ({selected.generation.evidence_conflict_note_count})</summary>{selected.generation.evidence_conflicts.map((conflict, index) => <p className="ai-paper-warning" key={`conflict-${index}`}>{conflict.statement} <strong>Sources:</strong> {conflict.evidence_refs.map(source => <code key={source}>{source} </code>)}</p>)}</details>}
        {selected.validation_warnings.map((warning, index) => <p className="ai-paper-warning" key={`system-${index}`}>Evidence validation: {warning}</p>)}
        {(selected.author_review_warnings ?? []).map((warning, index) => <p className="ai-paper-warning" key={`author-${index}`}>Author self-review (not independent): {warning}</p>)}
        {selected.draft.sections.map(section => <section key={section.heading}><h4>{section.heading}</h4>{section.paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}<p className="settings-hint">Claim links: {section.claim_ids.join(', ') || 'None'}</p></section>)}
        <h4>Claim register</h4>{selected.draft.claims.map(claim => <section key={claim.id}><p><strong>{claim.id} · {claim.status}:</strong> {claim.statement}</p><p>{claim.reasoning}</p><p className="settings-hint">Evidence: {claim.evidence_refs.join(', ') || 'No source reference'}</p></section>)}
        <h4>Limitations</h4><ul>{selected.draft.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>
        {selected.draft.open_obligations.length > 0 && <><h4>Open obligations</h4><ul>{selected.draft.open_obligations.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
        {!!selected.obligation_reconciliation?.length && <><h4>Frozen obligation reconciliation</h4><p className="settings-hint">Unlisted evidence obligations are not presumed resolved. References point to the research evidence source and field.</p><ul>{selected.obligation_reconciliation.map((item, index) => <li key={index}><strong>{item.status}.</strong> {item.text}<br/><span className="settings-hint">{item.source_refs.join(', ') || 'No exact frozen-record match'}</span></li>)}</ul></>}
        {!!selected.publication_requirement_reconciliation?.length && <section aria-label="Paper Requirements review">
          <h4>Paper Requirements review</h4>
          <p className="settings-hint">These checks flag missing structures. They do not certify scientific or editorial compliance.</p>
          <ul>{selected.publication_requirement_reconciliation.map((item, index) =>
            <li key={index}><strong>{item.status === 'missing' ? 'Missing structure' : 'Review required'}:</strong> {item.text} — {item.note}</li>
          )}</ul>
        </section>}
        {!!selected.editorial_overlap_warnings?.length && <section aria-label="Editorial repetition review">
          <h4>Editorial repetition review</h4>
          <ul>{selected.editorial_overlap_warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>
        </section>}
        <h4>Conclusions</h4>{selected.draft.conclusions.map((item, index) => <p key={`conclusion-${index}`}>{item}</p>)}
        <p className="settings-hint">Conclusion claim links: {selected.draft.conclusion_claim_ids.join(', ') || 'None'}</p>
        {!selected.pdf_available && <p role="status">The paper record exists, but its compiled PDF is unavailable. Regenerate to create a new version with a PDF.</p>}
        </>}
      </article>}      {selected?.paper_id === paper.paper_id && (selected.generation.sigma_issues?.length ?? 0) > 0 && <details className="outcome-subsection paper-diagnostics-disclosure">
        <summary><svg aria-hidden="true" className="disclosure-chevron" viewBox="0 0 12 12"><path d="m4 2 4 4-4 4"/></svg><span>Diagnostics ({selected.generation.sigma_issues?.length ?? 0})</span></summary>
        <div className="paper-diagnostics-content">
          <label className="ai-paper-details"><input type="checkbox" checked={includeSigmaIssues} disabled={generating} onChange={event => { window.localStorage.setItem('sigma.paper.issues:' + projectId, String(event.target.checked)); setIncludeSigmaIssues(event.target.checked); }}/>Include paper-generation diagnostics in the PDF</label>
          <p>Authoring, validation, and typesetting problems are kept in the paper record even when the optional diagnostic appendix is not included.</p>
          <ol>{selected.generation.sigma_issues?.map((issue, index) => <li key={index}>{issue}</li>)}</ol>
          {selected?.generation.sigma_issues_included && <p role="status">The PDF includes the optional diagnostics appendix.</p>}
          {paperProgress?.status === 'failed' && paperProgress.failure_reason && <p role="alert">{paperErrorSummary(paperProgress.failure_reason)}</p>}
        </div>
      </details>}</div>
      </article>)}
      </section>}
      {success && <p className="ai-paper-status" role="status">{success}</p>}

      </>
      {confirmRestartDraft && createPortal(
        <div ref={paperStepRestartPopup} className="paper-step-restart-popup" role="dialog"
          aria-label="Confirm start over on paper generation" aria-modal="false"
          style={paperStepRestartPlacement
            ? { left: paperStepRestartPlacement.left, top: paperStepRestartPlacement.top }
            : { left: 12, top: 12, visibility: 'hidden' }}>
          <p>Restart paper from beginning?</p>
          <div className="session-remove-confirm-actions">
            <button type="button" className="text-view-link" disabled={busy}
              onClick={() => { setConfirmRestartDraft(false); void restartCheckpoint(); }}>Confirm</button>
            <button type="button" className="text-view-link" onClick={() => setConfirmRestartDraft(false)}>Cancel</button>
          </div>
        </div>, document.body
      )}
      {confirmDiscardRun && (() => {
        const run = paperRuns.find(item => item.run_id === confirmDiscardRun.runId);
        return run ? createPortal(
          <div ref={discardRunPopup} className="paper-step-restart-popup" role="dialog"
            aria-label={`Confirm removing unfinished paper ${run.number}`}
            aria-modal="false" style={{ left: confirmDiscardRun.left, top: confirmDiscardRun.top, maxHeight: '55dvh', overflowY: 'auto' }}>
            <p>{['active', 'queued'].includes(run.status) ? 'Stop and remove' : 'Remove'} paper {run.number}?</p>
            {paperRemovalErrors[run.run_id] && <p role="alert" className="ai-paper-warning">{paperUserMessage(paperRemovalErrors[run.run_id])}</p>}
            <div className="session-remove-confirm-actions">
              <button type="button" className="text-view-link" 
                onClick={() => void discardOtherRun(run.run_id)}>Confirm</button>
              <button type="button" className="text-view-link" 
                onClick={() => setConfirmDiscardRun(null)}>Cancel</button>
            </div>
          </div>, document.body,
        ) : null;
      })()}
      {unfinishedStepRestart && createPortal(
        <div ref={paperStepRestartPopup} className="paper-step-restart-popup" role="dialog"
          aria-label="Confirm unfinished paper restart" aria-modal="false"
          style={paperStepRestartPlacement
            ? { left: paperStepRestartPlacement.left, top: paperStepRestartPlacement.top }
            : { left: 12, top: 12, visibility: 'hidden' }}>
          <p>{unfinishedStepRestart.startFresh
            ? `Restart paper from beginning?`
            : `${unfinishedStepRestart.stage === 'started' ? 'Restart paper from beginning?' : `${paperRuns.some(run => run.run_id === unfinishedStepRestart.runId && ['active', 'queued'].includes(run.status)) ? 'Stop and restart' : 'Restart'} paper ${unfinishedStepRestart.number ?? ''} at ${paperUnfinishedStageLabel(unfinishedStepRestart.stage)}?`}`}</p>
          {unfinishedStepRestart.error && <p role="alert" className="ai-paper-warning">{paperUserMessage(unfinishedStepRestart.error)}</p>}
          <div className="session-remove-confirm-actions">
            <button type="button" className="text-view-link" disabled={unfinishedStepRestart.checking || !!unfinishedStepRestart.error || unfinishedRestartBusy || !binding}
              onClick={() => void confirmUnfinishedPaperStepRestart()}>Confirm</button>
            <button type="button" className="text-view-link" onClick={dismissUnfinishedStepRestart}>Cancel</button>
          </div>
        </div>, document.body
      )}
      {scoreDialog && <PaperScoreDialog score={scoreDialog.score} onClose={() => { setScoreDialog(null); setScoreError(""); }} error={scoreError}/>} 
      </div>
    </div>
  </section>;
}

function FloatingTooltip() {
  const [active, setActive] = useState<{ element: HTMLElement; text: string } | null>(null);
  const tooltip = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLElement | null>(null);
  const pointerPosition = useRef({ x: 0, y: 0 });
  const tooltipPointerPosition = useRef({ x: 0, y: 0 });
  const suppressedAfterClick = useRef(new WeakSet<HTMLElement>());
  // A Play control can be replaced by Stop underneath an unmoved cursor.
  // The replacement is not a new hover: suppress both the tooltip and hover
  // decoration until the pointer actually leaves that control's footprint.
  const clickedControlRect = useRef<DOMRect | null>(null);
  const previousDescriptions = useRef(new WeakMap<HTMLElement, string | null>());
  const hoverTimer = useRef<number | null>(null);
  const clearHoverTimer = () => {
    if (hoverTimer.current !== null) window.clearTimeout(hoverTimer.current);
    hoverTimer.current = null;
  };
  const insideClickedControl = (x: number, y: number) => {
    const bounds = clickedControlRect.current;
    return !!bounds && x >= bounds.left && x < bounds.right
      && y >= bounds.top && y < bounds.bottom;
  };
  const clearClickedControl = () => {
    clickedControlRect.current = null;
    document.body.removeAttribute('data-sigma-control-hover-hold');
  };
  const position = useCallback(() => {
    const element = activeRef.current;
    const hint = tooltip.current;
    if (!element?.isConnected || !hint) return;
    const anchor = element.getBoundingClientRect();
    const box = hint.getBoundingClientRect();
    if (element.dataset.tooltipFollowCursor === 'true' && element.matches(':hover')) {
      const left = Math.max(8, Math.min(window.innerWidth - box.width - 8, tooltipPointerPosition.current.x + 14));
      const below = tooltipPointerPosition.current.y + 16;
      const top = below + box.height <= window.innerHeight - 8
        ? below
        : Math.max(8, tooltipPointerPosition.current.y - box.height - 12);
      hint.style.left = `${left}px`;
      hint.style.top = `${top}px`;
      return;
    }
    const left = Math.max(8, Math.min(window.innerWidth - box.width - 8, anchor.left + anchor.width / 2 - box.width / 2));
    const below = anchor.bottom + 8;
    const top = below + box.height <= window.innerHeight - 8
      ? below
      : Math.max(8, anchor.top - box.height - 8);
    hint.style.left = `${left}px`;
    hint.style.top = `${top}px`;
  }, []);
  const hide = useCallback((element?: HTMLElement | null) => {
    const current = activeRef.current;
    if (!current || element && element !== current) return;
    const previous = previousDescriptions.current.get(current);
    if (previous === undefined || previous === null) current.removeAttribute('aria-describedby');
    else current.setAttribute('aria-describedby', previous);
    previousDescriptions.current.delete(current);
    activeRef.current = null;
    setActive(null);
  }, []);
  const show = useCallback((element: HTMLElement | null) => {
    if (document.querySelector('.project-model-confirm-popover')) { hide(); return; }
    const text = element?.dataset.tooltip?.trim() || element?.getAttribute('aria-label')?.trim();
    if (!element || !text) return;
    if (activeRef.current === element) { setActive({ element, text }); return; }
    const previous = element.getAttribute('aria-describedby');
    if (element.dataset.tooltipFollowCursor === 'true' && element.matches(':hover')) {
      tooltipPointerPosition.current = { ...pointerPosition.current };
    }
    previousDescriptions.current.set(element, previous);
    element.setAttribute('aria-describedby', [previous, 'sigma-ui-tooltip'].filter(Boolean).join(' '));
    activeRef.current = element;
    setActive({ element, text });
  }, [hide]);
  useEffect(() => {
    const targetFor = (target: EventTarget | null) => target instanceof Element
      ? target.closest<HTMLElement>('[data-tooltip]:not([data-tooltip-disabled]), button[aria-label]:not([data-tooltip-disabled])')
      : null;
    const onPointerOver = (event: PointerEvent) => {
      pointerPosition.current = { x: event.clientX, y: event.clientY };
      const element = targetFor(event.target);
      if (document.querySelector('.project-model-confirm-popover')) { clearHoverTimer(); hide(); return; }
      if (insideClickedControl(event.clientX, event.clientY)) return;
      if (clickedControlRect.current) clearClickedControl();
      if (element && suppressedAfterClick.current.has(element)) return;
      if (element && element !== activeRef.current) {
        clearHoverTimer();
        hide();
        hoverTimer.current = window.setTimeout(() => {
          hoverTimer.current = null;
          if (element.matches(':hover') && !suppressedAfterClick.current.has(element)
            && !insideClickedControl(pointerPosition.current.x, pointerPosition.current.y)) show(element);
        }, 400);
      }
    };
    const onPointerOut = (event: PointerEvent) => {
      const element = targetFor(event.target);
      const related = targetFor(event.relatedTarget);
      if (element && related !== element) clearHoverTimer();
      if (element && related !== element) suppressedAfterClick.current.delete(element);
      if (element && element === activeRef.current && related !== element && !element.matches(':focus-visible')) hide(element);
    };
    const onClick = (event: Event) => {
      const element = targetFor(event.target);
      if (!element) return;
      clearHoverTimer();
      suppressedAfterClick.current.add(element);
      hide(element);
      const control = event.target instanceof Element
        ? event.target.closest<HTMLElement>('.workspace-page button.process-control') : null;
      if (control && event instanceof MouseEvent && event.detail > 0) {
        clickedControlRect.current = control.getBoundingClientRect();
        document.body.setAttribute('data-sigma-control-hover-hold', '');
      }
    };
    const onFocusIn = (event: FocusEvent) => {
      clearHoverTimer();
      const element = targetFor(event.target);
      if (element?.matches(':focus-visible')) show(element);
    };
    const onFocusOut = (event: FocusEvent) => {
      const element = targetFor(event.target);
      if (element && !element.matches(':hover') && !element.contains(event.relatedTarget as Node | null)) hide(element);
    };
    const onPointerMove = (event: PointerEvent) => {
      pointerPosition.current = { x: event.clientX, y: event.clientY };
      if (clickedControlRect.current && !insideClickedControl(event.clientX, event.clientY)) {
        clearClickedControl();
      }
      if (activeRef.current && targetFor(event.target) === activeRef.current
        && activeRef.current.dataset.tooltipFollowCursor !== 'true') position();
    };
    const onMove = () => position();
    document.addEventListener('pointerover', onPointerOver, true);
    document.addEventListener('pointerout', onPointerOut, true);
    document.addEventListener('pointermove', onPointerMove, true);
    document.addEventListener('click', onClick, true);
    document.addEventListener('focusin', onFocusIn, true);
    document.addEventListener('focusout', onFocusOut, true);
    window.addEventListener('scroll', onMove, true);
    window.addEventListener('resize', onMove);
    return () => {
      clearHoverTimer();
      document.removeEventListener('pointerover', onPointerOver, true);
      document.removeEventListener('pointerout', onPointerOut, true);
      document.removeEventListener('pointermove', onPointerMove, true);
      document.removeEventListener('click', onClick, true);
      document.removeEventListener('focusin', onFocusIn, true);
      document.removeEventListener('focusout', onFocusOut, true);
      window.removeEventListener('scroll', onMove, true);
      window.removeEventListener('resize', onMove);
      clearClickedControl();
      hide();
    };
  }, [hide, position, show]);
  useEffect(() => {
    if (!active) return;
    const observer = new MutationObserver(() => {
      const text = active.element.dataset.tooltip?.trim() || active.element.getAttribute('aria-label')?.trim();
      if (text) setActive(previous => previous?.element === active.element ? { element: active.element, text } : previous);
    });
    observer.observe(active.element, { attributes: true, attributeFilter: ['data-tooltip', 'aria-label'] });
    return () => observer.disconnect();
  }, [active]);
  useEffect(() => {
    if (!active) return;
    const observer = new MutationObserver(() => {
      if (!active.element.isConnected) hide(active.element);
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [active, hide]);
  useLayoutEffect(() => { if (active) position(); }, [active, position]);
  if (!active) return null;
  // Modal dialogs live in the browser's top layer, above body-level portals.
  // Mount the tooltip inside the active dialog so it is actually visible.
  const dialogTarget = active.element.closest<HTMLDialogElement>('dialog[open]');
  const activityEntries = active.element.dataset.tooltipActivity === 'true'
    ? active.text.split(/\r?\n/).filter(Boolean) : null;
  return createPortal(<div ref={tooltip} id="sigma-ui-tooltip" role="tooltip" className={`sigma-ui-tooltip${activityEntries ? ' sigma-ui-activity-tooltip' : ''}`}>
    {activityEntries ? activityEntries.map((entry, index) => <div className="sigma-ui-activity-entry" key={`${index}:${entry}`}>{entry}</div>) : active.text}
  </div>, dialogTarget ?? document.body);
}

function UsersRoundIcon() {
  return <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M16 20v-1.8a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4V20"/><circle cx="9.5" cy="7" r="3.5"/><path d="M21 20v-1.8a4 4 0 0 0-3-3.87M15.5 3.65a3.5 3.5 0 0 1 0 6.7"/></svg>;
}

function CirclePlusIcon() {
  return <svg className="sigma-action-glyph" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7.5v9M7.5 12h9"/></svg>;
}

function SparklesActionIcon() {
  return <svg className="sigma-action-glyph" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m10 3 1.9 5.9L18 11l-6.1 2.1L10 19l-1.9-5.9L2 11l6.1-2.1L10 3Z M19 2v6 M16 5h6 M19 18v4 M17 20h4"/></svg>;
}

function SlidersSettingsIcon() {
  return <svg className="sigma-action-glyph" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M3 5.5h4m4 0h10M3 12h11m4 0h3M3 18.5h6m4 0h8"/><circle cx="9" cy="5.5" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="11" cy="18.5" r="2"/></svg>;
}

function UploadProjectIcon() {
  return <svg className="sigma-action-glyph" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12 16V3m-4.5 4.5L12 3l4.5 4.5M3 16v4.5h18V16"/></svg>;
}

function LazyViewport({ children, fallback, force = false }: {
  children: ReactNode; fallback: ReactNode; force?: boolean;
}) {
  const target = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(force);
  useEffect(() => {
    if (mounted) return;
    if (force || typeof IntersectionObserver === 'undefined') {
      setMounted(true);
      return;
    }
    const node = target.current;
    if (!node) return;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) {
        setMounted(true);
        observer.disconnect();
      }
    }, { rootMargin: '600px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [mounted, force]);
  return <div ref={target}>{mounted ? children : fallback}</div>;
}

function TextViews({ path, scope, strategyId, source, projectTitle, contentClass, guest = false, aiGuest = false, onSaved, mathematical, onSettings, settingsDisabled, settingsButtonRef, hideProjectHeading, hideProjectActions = false, hideEditAction = false, modeDisabled = false, combinedEditMode = false, editSignal = 0, markdownSlotId, onCombinedDraftChange, onEnterMode, onExitMode }: {
  path: string; scope: 'project' | 'strategy'; strategyId?: string; source: string; projectTitle?: string;
  contentClass: string; onSaved: (view: ProjectView) => void; mathematical: boolean; guest?: boolean; aiGuest?: boolean; onSettings?: () => void; settingsDisabled?: boolean; settingsButtonRef?: React.RefObject<HTMLButtonElement | null>; hideProjectHeading?: boolean; hideProjectActions?: boolean; hideEditAction?: boolean; modeDisabled?: boolean; combinedEditMode?: boolean; editSignal?: number; markdownSlotId?: string; onCombinedDraftChange?: (draft: string) => void; onEnterMode?: () => boolean; onExitMode?: () => void;
}) {
  const [data, setData] = useState<TextRepresentations | null>(null);
  const preferenceKey = `sigma.markdownView:${path}:${scope}:${strategyId ?? ''}`;
  const [storedSelected, setSelected] = useState<TextDisplay>(() => window.localStorage.getItem(preferenceKey) === 'rendered' ? 'rendered' : 'plain');
  const selected: TextDisplay = storedSelected;
  const [rendering, setRendering] = useState(false);
  const [guestMarkdownPreview, setGuestMarkdownPreview] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editingFromRendered, setEditingFromRendered] = useState(false);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const exportTrigger = useRef<HTMLButtonElement>(null);
  const [error, setError] = useState('');
  const abort = useRef<AbortController | null>(null);
  const bodyTrigger = useRef<HTMLElement>(null);
  const editorForm = useRef<HTMLFormElement>(null);
  const editorArea = useRef<HTMLDivElement>(null);
  const [markdownPortalTarget, setMarkdownPortalTarget] = useState<HTMLElement | null>(null);
  const [copyPortalTarget, setCopyPortalTarget] = useState<HTMLElement | null>(null);
  const [copied, setCopied] = useState(false);
  const renderedContent = useRef<HTMLDivElement>(null);
  const copyTimer = useRef<number | null>(null);
  const handledEditSignal = useRef(0);
  useLayoutEffect(() => {
    setMarkdownPortalTarget(markdownSlotId ? document.getElementById(markdownSlotId) : null);
    setCopyPortalTarget(markdownSlotId ? document.getElementById(`${markdownSlotId}-copy`) : null);
  }, [markdownSlotId, modeDisabled, combinedEditMode, editSignal]);
  useEffect(() => () => { if (copyTimer.current !== null) window.clearTimeout(copyTimer.current); }, []);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError(''); setEditing(false);
    const query = new URLSearchParams({ path, scope, ...(strategyId ? { strategy_id: strategyId } : {}) });
    fetch(`/api/projects/text?${query}`, { signal: controller.signal }).then(async response => {
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Could not read text views');
      return result as TextRepresentations;
    }).then(result => { setData(result); if (!result.markdown?.current) setSelected('plain'); setDraft(result.markdown?.current ? result.markdown.body : result.plain?.body ?? ''); })
      .catch(cause => { if (!controller.signal.aborted) setError(errorMessage(cause)); });
    return () => { controller.abort(); abort.current?.abort(); };
  }, [path, scope, strategyId, source]);
  const format: TextFormat = selected === 'plain' ? 'plain' : 'markdown';
  function chooseView(view: TextDisplay) {
    setSelected(view);
    window.localStorage.setItem(preferenceKey, view);
  }
  const version = data?.[format];
  const current = version?.current ?? false;
  async function copyText() {
    if (!version || !current || editing) return;
    const text = selected === 'rendered'
      ? (renderedContent.current?.innerText ?? version.body).replace(/\n{3,}/g, '\n\n').trim()
      : version.body;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      if (copyTimer.current !== null) window.clearTimeout(copyTimer.current);
      copyTimer.current = window.setTimeout(() => setCopied(false), 1600);
    } catch (cause) { reportRequestFailure(`Could not copy ${name}: ${errorMessage(cause)}`); }
  }
  function beginBodyEdit(fromRendered = false, alreadyInMode = false) {
    if (guest || !version?.current || busy || (modeDisabled && !alreadyInMode) || (!alreadyInMode && onEnterMode && !onEnterMode())) return;
    setDraft(version.body); onCombinedDraftChange?.(version.body); setEditingFromRendered(fromRendered);
    if (fromRendered) chooseView('rendered');
    setEditing(true); setError('');
  }
  useEffect(() => {
    if (!editSignal || handledEditSignal.current === editSignal || !version?.current) return;
    handledEditSignal.current = editSignal;
    beginBodyEdit(selected === 'rendered', combinedEditMode);
  }, [editSignal, version?.current, combinedEditMode]);
  const wasCombinedEditMode = useRef(false);
  useEffect(() => {
    if (wasCombinedEditMode.current && !combinedEditMode) setEditing(false);
    wasCombinedEditMode.current = combinedEditMode;
  }, [combinedEditMode]);
  function cancelBodyEdit(restoreFocus = true) {
    setEditing(false);
    onExitMode?.();
    if (editingFromRendered) chooseView('rendered');
    if (restoreFocus) requestAnimationFrame(() => bodyTrigger.current?.focus());
  }
  async function convert(targetFormat: TextFormat = format) {
    if (guest || aiGuest) { setGuestMarkdownPreview(true); return; }
    if (!data || busy) return;
    const controller = new AbortController(); abort.current = controller; setBusy(true); setRendering(true); setError('');
    let finishProviderRequest = () => {};
    try {
      const settingsResponse = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path, purpose: "markdown" })}`, { signal: controller.signal });
      const settings = await settingsResponse.json();
      if (!settingsResponse.ok || !settings.available) { if (settingsResponse.ok) reportRequestFailure(settings.message ?? settings.error ?? 'Connect AI in the header, then retry.'); throw new Error(settings.message ?? settings.error ?? 'Connect AI in the header, then retry.'); }
      finishProviderRequest = beginProviderRequest('text-conversion');
      const response = await fetch('/api/projects/text/convert', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ path, scope, strategy_id: strategyId, target: targetFormat, expected_digest: data.source_digest, expected_binding: settings.binding }) });
      const next = await response.json();
      if (!response.ok) throw new Error(next.error ?? 'Conversion failed; source text was kept.');
      setData(next as TextRepresentations); setDraft(next[targetFormat]?.body ?? ''); chooseView(targetFormat === 'markdown' ? 'rendered' : 'plain');
    } catch (cause) { if (!controller.signal.aborted) { chooseView('plain'); setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); } }
    finally { finishProviderRequest(); if (abort.current === controller) { abort.current = null; setBusy(false); setRendering(false); } }
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (!data || busy) return;
    setBusy(true); setError('');
    try {
      const next = await post<ProjectView>('text/source', { path, scope, strategy_id: strategyId, body: draft, format, expected_digest: data.source_digest });
      setEditing(false); onExitMode?.(); onSaved(next);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  const name = scope === 'project' ? 'research problem' : 'strategy approach';
  const plainRecovery = data?.source_format === 'markdown' && !data.plain?.current;
  const renderTooltip = rendering ? (plainRecovery ? 'Converting to Plain' : 'Converting to markdown') : selected === 'rendered' ? 'Show plain text' : plainRecovery ? 'Convert to Plain' : 'Convert to markdown';
  function closeExport() {
    setExportOpen(false);
    requestAnimationFrame(() => exportTrigger.current?.focus());
  }
  const markdownToggle = <button type="button" className={`sigma-render-toggle${markdownSlotId ? '' : ' workspace-icon-button'}${selected === 'rendered' || rendering ? ' sigma-render-active' : ''}${rendering ? ' sigma-render-pending' : ''}`}
      aria-label={selected === 'rendered' ? `Show plain ${name}` : plainRecovery ? `Convert ${name} to Plain` : `Render ${name} as Markdown`}
      aria-pressed={selected === 'rendered' || rendering} data-tooltip={renderTooltip}
      aria-hidden={combinedEditMode || undefined} style={combinedEditMode ? { visibility: 'hidden' } : undefined}
      disabled={editing || busy || combinedEditMode} onClick={() => {
        if (selected === 'rendered') { chooseView('plain'); setError(''); }
        else if (data?.markdown?.current) { chooseView('rendered'); setError(''); }
        else { void convert(plainRecovery ? 'plain' : 'markdown'); }
      }}>{rendering ? <ProjectOpeningHourglass/> : <svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z" fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg>}</button>;
  const markdownControl = <span className="text-view-format-control">
    {markdownToggle}
    {rendering && <span className="text-view-format-status" role="status">Formatting with AI…</span>}
  </span>;
  const copyControl = <CopyToClipboardButton name={name} copied={copied} disabled={!current || editing || busy || combinedEditMode} onCopy={() => void copyText()}/>;
  const viewActions = <>
    {!markdownSlotId && markdownControl}

    {editing ? combinedEditMode ? null : <>
      <button type="submit" form={`text-form-${scope}-${strategyId ?? 'project'}`} className="text-view-link" data-tooltip={`Save ${name}`} disabled={busy || !draft.trim()}>Save</button>
      <button type="button" className="text-view-link" data-tooltip={`Cancel editing ${name}`} disabled={busy} onClick={() => cancelBodyEdit()}>Cancel</button>
      </> : data && version && !hideEditAction && <button type="button" className="text-view-link text-view-icon workspace-icon-button" aria-label={`Edit ${name}`} data-tooltip={`Edit ${name}`} disabled={guest || modeDisabled} onClick={() => beginBodyEdit(selected === 'rendered')}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg></button>}

    {!hideProjectActions && scope === 'project' && !editing && <button ref={exportTrigger} type="button" className="copper-button project-export-trigger workspace-icon-button" aria-label="Export project" data-tooltip="Export project" onClick={() => setExportOpen(true)}><svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg></button>}
    {!hideProjectActions && onSettings && !editing && <button ref={settingsButtonRef} type="button" className="text-view-link text-view-icon workspace-icon-button" aria-label="Project Settings" data-tooltip="Project Settings" disabled={settingsDisabled} onClick={onSettings}><SlidersSettingsIcon/></button>}
  </>;
  return <div ref={editorArea} className={`text-views${scope === 'project' ? ' project-text-views' : ''}${mathematical ? ' math-text-views' : ''}`}>
    {markdownPortalTarget && createPortal(markdownControl, markdownPortalTarget)}
    {guestMarkdownPreview && <GuestFeatureDialog title="AI Markdown formatting" message="With an authorized model, SIGMA can format this text as readable Markdown for your review before adopting it. Manual Markdown editing and rendering remain available without AI." onClose={() => setGuestMarkdownPreview(false)}/>}
    {copyPortalTarget && createPortal(copyControl, copyPortalTarget)}
    {scope === 'project' && exportOpen && <ProjectExportDialog path={path} title={projectTitle ?? 'project'} onCancel={closeExport}/>}
    <div className="text-view-controls">
      {scope === 'project' && !hideProjectHeading && <h2 className="investigation-heading">Project</h2>}
      {scope === 'project' ? <div className="project-text-actions">{viewActions}</div> : viewActions}
    </div>
    {editing ? <form ref={editorForm} id={`text-form-${scope}-${strategyId ?? 'project'}`} className="text-view-editor" onSubmit={save}>
      <textarea id={`text-editor-${scope}-${strategyId ?? 'project'}`} autoFocus value={draft} maxLength={scope === 'project' ? 20000 : MAX_STRATEGY_APPROACH} rows={8} required disabled={busy} onChange={event => { setDraft(event.target.value); onCombinedDraftChange?.(event.target.value); }} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); cancelBodyEdit(); } }}/>
    </form> : current && version ? selected === 'rendered'
      ? <div ref={renderedContent} className={`${contentClass} rendered-text`} aria-label={`Rendered ${name}`}><Suspense fallback={<p>Preparing preview…</p>}><RenderedMarkdown body={version.body}/></Suspense></div>
      : <p className={contentClass}>{version.body}</p>
      : !data ? <p className={contentClass}>{source}</p> : <div className="text-view-missing">
        <p>{version ? 'The previous conversion is out of date with the current source.' : `No ${format === 'markdown' ? 'Markdown' : 'Plain'} representation is stored yet.`}</p>
        {mathematical && plainRecovery && format === 'plain' && <button type="button" className="text-view-link" disabled={busy || modeDisabled} onClick={() => void convert('plain')}>Convert to Plain</button>}
        {version && <details><summary>Inspect previous {format === 'markdown' ? 'Markdown' : 'Plain'} text</summary><pre>{version.body}</pre></details>}
      </div>}
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

function ProjectPaneTitle({ view, onSaved, disabled, modeDisabled, descriptionDraft, onEnterMode, onExitMode, onEditDescription }: { view: ProjectView; onSaved: (view: ProjectView) => void; disabled: boolean; modeDisabled: boolean; descriptionDraft: string; onEnterMode: () => boolean; onExitMode: () => void; onEditDescription: () => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(view.project.title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => { if (!editing) setDraft(view.project.title); }, [view.project.title, editing]);
  useEffect(() => { if (editing) { input.current?.focus(); input.current?.select(); } }, [editing]);
  function cancel(restoreFocus = true) { setDraft(view.project.title); setError(''); setEditing(false); onExitMode(); if (restoreFocus) requestAnimationFrame(() => trigger.current?.focus()); }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!draft.trim()) { setError('Enter a project title.'); input.current?.focus(); return; }
    setBusy(true); setError('');
    try {
      const current = settingsOf(view);
      const next = await post<ProjectView>('update', { path: view.path, ...current, title: draft, problem: descriptionDraft, expected: current });
      setEditing(false); onExitMode(); onSaved(next); requestAnimationFrame(() => trigger.current?.focus());
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <div className={`project-pane-title-line${editing ? ' is-renaming' : ''}`}>
    {editing ? <form ref={form} className="project-title-edit-form" onSubmit={save}>
      <label className="sr-only" htmlFor="project-pane-title-input">Project title</label>
      <input ref={input} id="project-pane-title-input" aria-label="Project title" value={draft} size={Math.max(8, Math.min(50, draft.length + 1))} maxLength={200} required disabled={busy} onChange={event => { setDraft(event.target.value); setError(''); }} onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); cancel(); } }}/>
      <button type="submit" className="text-view-link" data-tooltip="Save project title" disabled={busy}>Save</button><button type="button" className="text-view-link" data-tooltip="Cancel editing the project title" disabled={busy} onClick={() => cancel()}>Cancel</button>
      {error && <p role="alert" className="project-title-error">{error}</p>}
    </form> : <><h3 className="current-project">{view.project.title}</h3>
      <button type="button" ref={trigger} className="text-view-link text-view-icon workspace-icon-button project-title-pencil" aria-label={`Edit project title and description: ${view.project.title}`} data-tooltip="Edit text and description" disabled={disabled || modeDisabled} onClick={() => { if (onEnterMode()) { setEditing(true); onEditDescription(); } }}>
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg>
      </button><span id="project-markdown-slot" className="project-markdown-slot"/><span id="project-markdown-slot-copy" className="project-copy-slot"/> </>}
  </div>;
}

function AboutArchitecture() {
  const descriptions = {
    project: 'A project holds the central research question and multiple persistent research directions. Results from a local investigation do not automatically settle the entire question.',
    strategies: 'Strategies are durable, bounded research ideas. They may be tested, revised or forked, and failed attempts retain their evidence and history.',
    strategyA: 'A strategy can investigate an observed pattern or relationship. Its objective is bounded: identify supporting evidence, find limits, or expose a useful unanswered question. It does not need to solve the entire project.',
    strategyB: 'The same problem may become clearer through a different model, formalism, or computational method. Its results can complement, challenge, or refine the evidence from other strategies, without being assumed equivalent.',
    strategyC: 'A strategy may deliberately stress-test an assumption or search for a counterexample. A negative result can rule out a local claim while leaving the wider research problem open and the strategy history intact.',
    session: 'When you press Play, SIGMA runs an investigation of your selected approaches. Each approach can be tried, challenged and revised over several rounds, within the limits you set.',
    orchestration: "SIGMA's session engine selects bounded evidence, dispatches Investigator and Skeptic calls, coordinates strategies and manages limits.",
    investigator: 'A role-specific AI agent that develops claims, arguments, testable hypotheses and code proposals, while identifying assumptions and what remains uncertain.',
    investigatorFollowup: 'A later Investigator call can take up the Skeptic’s critique, revise an approach, and explore what the session has learned so far.',
    tools: 'The Investigator can draw on tools such as SciPy and SageMath to explore ideas, test patterns, and carry out calculations.',
    workingEvidence: 'Claims, objections, code outputs, prior artifacts and source identifiers inform subsequent work. Relevant evidence is selected into bounded role contexts; this is not a global chat memory.',
    skeptic: "A separate role-specific AI agent that examines the Investigator's claims and assumptions, looks for counterexamples or gaps, and suggests next tests. Its review is model-reported, not independent proof certification.",
    investigatorRound2: 'The Investigator sees the Skeptic’s objections and can change the idea, the assumptions, or the experiment.',
    skepticRound2: 'The Skeptic checks the revised argument and searches for what is still missing.',
    investigatorRound3: 'The Investigator can pursue a promising result or try a new test based on the earlier exchange.',
    skepticRound3: 'The Skeptic challenges the latest claim, including its remaining assumptions and counterexamples.',
    decision: 'After a review, SIGMA applies the recorded assessment, next question and remaining work within resource limits. A strategy can remain available for later revision or another session.',
    savedEvidence: 'Persisted artifacts and outcomes expose findings, objections, test results, remaining obligations and uncertainty. Research can be reviewed and reused, but the outcome is not automatic proof certification.',
  } as const;
  type DiagramNode = keyof typeof descriptions;
  const [activeInfoNode, setActiveInfoNode] = useState<DiagramNode | null>(null);
  const [sessionExpanded, setSessionExpanded] = useState(false);
  const sessionToggle = useRef<HTMLButtonElement>(null);
  const sessionPanel = useRef<HTMLDivElement>(null);
  const hideTimer = useRef<number | null>(null);
  const pointerType = useRef('');
  const activeAnchor = useRef<HTMLElement | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ left: number; top: number; visibility: 'hidden' | 'visible' }>({ left: 0, top: 0, visibility: 'hidden' });
  const tooltipId = (key: DiagramNode) => 'about-diagram-tooltip-' + key;

  function cancelHide() {
    if (hideTimer.current !== null) window.clearTimeout(hideTimer.current);
    hideTimer.current = null;
  }
  function scheduleHide() {
    cancelHide();
    hideTimer.current = window.setTimeout(() => setActiveInfoNode(null), 130);
  }
  function positionTooltip(key = activeInfoNode, anchor = activeAnchor.current) {
    if (!key || !anchor) return;
    const dialog = anchor.closest('dialog');
    if (!dialog) return;
    const anchorRect = anchor.getBoundingClientRect();
    const dialogRect = dialog.getBoundingClientRect();
    const margin = 12;
    const tipWidth = Math.min(360, window.innerWidth - 62, dialogRect.width - 24);
    const lineWidth = Math.max(24, (tipWidth - 26) / 5.5);
    const lines = Math.ceil(descriptions[key].length / lineWidth);
    const tipHeight = Math.min(240, lines * 17 + 22);
    const left = Math.max(dialogRect.left + margin, Math.min(anchorRect.left + anchorRect.width / 2 - tipWidth / 2, dialogRect.right - tipWidth - margin));
    const preferredTop = anchorRect.bottom + 8;
    const lowerBound = dialogRect.top + margin;
    const upperBound = dialogRect.bottom - tipHeight - margin;
    const aboveTop = anchorRect.top - tipHeight - 8;
    const top = preferredTop <= upperBound || aboveTop < lowerBound
      ? Math.max(lowerBound, Math.min(preferredTop, upperBound))
      : Math.max(lowerBound, aboveTop);
    setTooltipPosition({ left, top, visibility: 'visible' });
  }
  function revealNode(key: DiagramNode, anchor: HTMLElement, revealToKeyboardOrTouch = false) {
    cancelHide();
    activeAnchor.current = anchor;
    positionTooltip(key, anchor);
    setActiveInfoNode(key);
    if (revealToKeyboardOrTouch) requestAnimationFrame(() => positionTooltip(key, anchor));
  }
  useLayoutEffect(() => {
    if (!activeInfoNode) return;
    positionTooltip(activeInfoNode);
    const pointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Element && target.closest('[data-about-info-node]')) return;
      setActiveInfoNode(null);
    };
    const keyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopImmediatePropagation();
        setActiveInfoNode(null);
      }
    };
    const repositionTooltip = () => positionTooltip();
    document.addEventListener('pointerdown', pointerDown, true);
    document.addEventListener('keydown', keyDown, true);
    document.addEventListener('scroll', repositionTooltip, true);
    window.addEventListener('resize', repositionTooltip);
    return () => {
      document.removeEventListener('pointerdown', pointerDown, true);
      document.removeEventListener('keydown', keyDown, true);
      document.removeEventListener('scroll', repositionTooltip, true);
      window.removeEventListener('resize', repositionTooltip);
    };
  }, [activeInfoNode]);
  useEffect(() => () => cancelHide(), []);

  function help(key: DiagramNode, label: string) {
    const active = activeInfoNode === key;
    return <button
      type="button"
      className="about-diagram-help"
      aria-label={"Explain " + label}
      aria-describedby={active ? tooltipId(key) : undefined}
      onPointerDown={event => { pointerType.current = event.pointerType; }}
      onFocus={event => revealNode(key, (event.currentTarget.closest('.about-info-region') as HTMLElement | null) ?? event.currentTarget, true)}
      onBlur={scheduleHide}
      onClick={event => {
        const touch = pointerType.current === 'touch' || window.matchMedia('(hover: none)').matches;
        if (touch) {
          // Touch generates focus before click; keep the newly revealed tip open.
          if (activeInfoNode !== key) revealNode(key, (event.currentTarget.closest('.about-info-region') as HTMLElement | null) ?? event.currentTarget, true);
        }
        pointerType.current = '';
      }}
    >i</button>;
  }
  function infoRegion(key: DiagramNode, content: ReactNode, tone: 'copper' | 'blue' = 'copper') {
    return <div
      className="about-info-region"
      data-about-info-node={key}
      onPointerEnter={event => { if (event.pointerType === 'mouse') revealNode(key, event.currentTarget); }}
      onPointerLeave={event => { if (event.pointerType === 'mouse') scheduleHide(); }}
    >
      {content}
      {activeInfoNode === key && <div id={tooltipId(key)} className="about-diagram-tooltip" data-tone={tone} role="tooltip" style={{ left: tooltipPosition.left, top: tooltipPosition.top, visibility: tooltipPosition.visibility }} onPointerEnter={cancelHide} onPointerLeave={scheduleHide}>{descriptions[key]}</div>}
    </div>;
  }
  function card(key: DiagramNode, title: string, subtitle: string, tone: 'copper' | 'blue' = 'copper') {
    return infoRegion(key, <div className={"about-diagram-node about-diagram-node--" + tone}>
      <span className="about-diagram-node-title">{title}</span>
      <span className="about-diagram-node-subtitle">{subtitle}</span>
      {help(key, title)}
    </div>, tone);
  }
  const strategyExamples = [
    { id: 'strategyA' as const, title: 'Strategy A', subtitle: 'Look for a pattern' },
    { id: 'strategyB' as const, title: 'Strategy B', subtitle: 'Try another method' },
    { id: 'strategyC' as const, title: 'Strategy C', subtitle: 'Look for a counterexample' },
  ];
  // Three illustrative paired turns (six individual calls) in one research round.
  const exampleTurns = [
    { turn: 1, title: 'Try an idea', investigator: 'Propose an approach', skeptic: 'Look for flaws', investigatorKey: 'investigator', skepticKey: 'skeptic' },
    { turn: 2, title: 'Improve it', investigator: 'Revise after critique', skeptic: 'Challenge the revision', investigatorKey: 'investigatorRound2', skepticKey: 'skepticRound2' },
    { turn: 3, title: 'Dig deeper', investigator: 'Test a stronger idea', skeptic: 'Check what remains uncertain', investigatorKey: 'investigatorRound3', skepticKey: 'skepticRound3' },
  ] as const;
  function toggleSession() {
    const next = !sessionExpanded;
    if (!next && activeInfoNode === 'session') setActiveInfoNode(null);
    if (!next && sessionPanel.current?.contains(document.activeElement)) {
      requestAnimationFrame(() => sessionToggle.current?.focus());
    }
    setSessionExpanded(next);
  }

  return <section className="about-architecture" aria-label="How SIGMA Works: Multi-Agentic Research">
    <div className="about-research-flow">
      <div className="about-flow-project">{card('project', 'Research Question', 'Start with a question you want to solve')}</div>
      <div className="about-flow-connector"><span>Try more than one way to answer it</span><i aria-hidden="true"/></div>
      <div className="about-strategy-group">
        {infoRegion('strategies', <div className="about-strategy-group-heading"><span>Strategies · Different Approaches</span>{help('strategies', 'Project Strategies')}</div>)}
        <div className="about-strategy-cards">
          {strategyExamples.map(strategy => {
            return infoRegion(strategy.id, <div className="about-strategy-card">
              <div className="about-strategy-node">
                <span className="about-diagram-node-title">{strategy.title}</span>
                <span className="about-diagram-node-subtitle">{strategy.subtitle}</span>
              </div>
              <div className="about-strategy-round" aria-label="Paired turn: Investigator call followed by Skeptic call">
                <span><strong>Investigator</strong></span><b aria-hidden="true">→</b><span><strong>Skeptic</strong></span>
              </div>
              {help(strategy.id, strategy.title)}
            </div>);
          })}
        </div>
        <p className="about-strategy-round-note">Each approach can be tried, challenged, and improved over several rounds.</p>
      </div>
      <div className="about-flow-connector about-strategy-parallel-note"><span>Press Play to investigate the selected approaches</span><i aria-hidden="true"/></div>
      <div className="about-session-frame">
        <div className="about-session-heading">{card('session', 'Research Session', 'A run where SIGMA investigates your selected approaches')}</div>
        <div className="about-agent-cycle-preview">
          <span className="about-agent-role"><strong>Investigator</strong><small>Tries an idea</small></span>
          <svg className="about-agent-review-arrow" viewBox="0 0 240 40" preserveAspectRatio="none" aria-hidden="true" focusable="false"><defs><linearGradient id="about-agent-arrow-metal" x1="0" x2="1"><stop stopColor="#4c83a8"/><stop offset=".5" stopColor="#acd9fa"/><stop offset="1" stopColor="#4c83a8"/></linearGradient></defs><path d="M4 20 H226 M212 6 L228 20 L212 34" fill="none" stroke="url(#about-agent-arrow-metal)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/></svg>
          <span className="about-agent-role"><strong>Skeptic</strong><small>Looks for flaws</small></span>
          <button ref={sessionToggle} type="button" className="about-session-toggle" aria-expanded={sessionExpanded} aria-controls="about-session-details" aria-label={(sessionExpanded ? 'Hide' : 'Show') + ' Investigator and Skeptic example'} onClick={toggleSession}>{sessionExpanded ? 'Hide' : 'Show'}</button>
        </div>
        <div id="about-session-details" ref={sessionPanel} className="about-session-detail" role="region" aria-labelledby="about-session-detail-heading" aria-hidden={!sessionExpanded} inert={!sessionExpanded} hidden={!sessionExpanded}>
          <div className="about-session-detail-inner">
            <h4 id="about-session-detail-heading">How one research round works</h4>
            <p className="about-multi-agent-intro">For <strong>one strategy</strong>, each turn pairs an Investigator call with a subsequent Skeptic review. Later turns can respond to criticism.</p>
            <p className="about-round-definition"><strong>One research round</strong> has up to three paired <strong>turns</strong> per strategy by default. Each turn contains two <strong>agent calls</strong>: Investigator → Skeptic.</p>
            <section className="about-agent-instantiation" aria-label="Example of one round with three paired turns and six agent calls within one strategy">
              <h5>One strategy · One round · Three turns</h5>
              <div className="about-agent-turns">
                {exampleTurns.map((turn, index) => <div className="about-agent-round" key={turn.turn}>
                  <div className="about-agent-round-heading"><strong>Turn {turn.turn} of 3</strong><span>{turn.title}</span></div>
                  <div className="about-agent-round-pair">
                    <div className="about-agent-turn">
                      <span className="about-turn-number">CALL {turn.turn * 2 - 1}</span>
                      {card(turn.investigatorKey, 'Investigator', turn.investigator, 'blue')}
                    </div>
                    <span className="about-turn-arrow" aria-hidden="true">→</span>
                    <div className="about-agent-turn">
                      <span className="about-turn-number">CALL {turn.turn * 2}</span>
                      {card(turn.skepticKey, 'Skeptic', turn.skeptic, 'blue')}
                    </div>
                  </div>
                  {index < exampleTurns.length - 1 && <div className="about-agent-return">
                    <svg viewBox="0 0 600 42" preserveAspectRatio="none" aria-hidden="true" focusable="false">
                      <path d="M505 3 V15 H155 V38 M147 30 L155 38 L163 30" fill="none" stroke="#75b7ef" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    <span>The Skeptic's feedback shapes the next attempt</span>
                    <b aria-hidden="true">↓</b>
                  </div>}
                </div>)}
              </div>
              <p className="about-agent-instantiation-note">These six calls illustrate one round. Other strategies may run concurrently or stop early; research evidence can inform later turns and rounds.</p>
            </section>
            <p className="about-shared-budget"><strong>Why more rounds?</strong> Later turns can test objections or revise claims. Progress is the goal, not a scheduler guarantee.</p>
            <div className="about-exploration-space" role="group" aria-label="Example of how much research fits into one session">
              <p className="about-exploration-title">How much can one session explore?</p>
              <p>With three enabled strategies and the default three rounds:</p>
              <div className="about-exploration-grid">
                {strategyExamples.map(strategy => <div className="about-exploration-row" key={strategy.id}>
                  <span className="about-exploration-strategy">{strategy.title}</span>
                  {[1, 2, 3].map(round => <span className="about-exploration-round" key={round}>Round {round}<small>3 turns</small></span>)}
                </div>)}
              </div>
              <p className="about-session-exploration-example"><strong>3 rounds × 3 turns × 3 strategies × 2 agent calls = 54 maximum calls.</strong> Strategies progress independently, but each Investigator call precedes its Skeptic. Limits or early stopping may reduce the total.</p>
            </div>
            <div className="about-working-evidence">{card('workingEvidence', 'A growing research record', 'Ideas · challenges · calculations · open questions')}</div>
            <p className="about-multiple-strategies-note">Research evidence is selected into bounded later contexts; there is no automatic round-end merge.</p>
            <p className="about-multiple-sessions-note">You can run another session later to revisit a strategy with new evidence or compare what changed.</p>
          </div>
        </div>
      </div>
      <div className="about-flow-connector"><span>Keep the ideas, tests, criticisms and unanswered questions</span><i aria-hidden="true"/></div>
      <div className="about-flow-evidence">{card('savedEvidence', 'Evidence & Outcome', 'Findings, objections, experiments and unresolved questions')}</div>
      <div className="about-evidence-report-note">Review what worked, what failed, and what still needs proof. Export the research or write a report.</div>
      <div className="about-history-return"><span aria-hidden="true">↶</span> Findings may inform later sessions or researcher-approved strategy revisions.</div>
    </div>
    <p className="about-architecture-caption">SIGMA can try several approaches, challenge each attempt, and try again. It saves the reasoning and evidence instead of giving only a one-shot answer. An AI critique is not a mathematical proof.</p>
  </section>;
}
function FeedbackForm({ signedInEmail }: { signedInEmail: string | null }) {
  const [message, setMessage] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [emailFailed, setEmailFailed] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/cloud-auth/feedback', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, contact_email: signedInEmail || contactEmail.trim() || null }),
      });
      if (!response.ok) throw await cloudFailure(response, 'Feedback could not be sent. Please try again.');
      const result = await response.json();
      setEmailFailed(result.email_notification_sent === false);
      setSent(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Feedback could not be sent. Please try again.');
    } finally { setBusy(false); }
  }
  return <>
      {sent ? <p role={emailFailed ? 'alert' : 'status'}>{emailFailed ? 'Feedback recorded for administrator review, but the email notification failed. Check local mail authorization.' : 'Thanks for your feedback. It has been sent for administrator review.'}</p> : <form className="about-feedback-form" onSubmit={event => void submit(event)}>
        <label>Feedback<textarea required minLength={10} maxLength={4000} rows={4} value={message} onChange={event => setMessage(event.target.value)} placeholder="Share a suggestion or describe a problem."/></label>
        <button type="submit" className="admin-text-action about-feedback-send" disabled={busy || message.trim().length < 10}>{busy ? 'Sending…' : 'Send Feedback'}</button>
        {signedInEmail ? <label><span className="about-contact-email-label">Contact email (Google account)</span><input type="email" value={signedInEmail} readOnly/></label> : <label><span className="about-contact-email-label">Contact email <span>(optional)</span></span><input type="email" maxLength={254} autoComplete="email" value={contactEmail} onChange={event => setContactEmail(event.target.value)} placeholder="you@example.org"/></label>}
        <p>Your feedback is stored for SIGMA administrator review and is not sent to an AI provider.</p>
        {error && <p role="alert">{error}</p>}
      </form>}
  </>;
}

function privacyNoticeHref(returnDialog: 'invitation' | 'about') {
  const returnTo = `${window.location.pathname}${window.location.search}`;
  return `/privacy?return_to=${encodeURIComponent(returnTo)}&return_dialog=${returnDialog}`;
}

const ABOUT_DISCLOSURE_KEY = 'sigma.aboutDisclosureState.v1';
const ABOUT_DISCLOSURE_DEFAULTS: Record<string, boolean> = {
  workflow: true,
  features: false,
  architecture: false,
  provenance: false,
  feedback: false,
};

function savedAboutDisclosureState(): Record<string, unknown> {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(ABOUT_DISCLOSURE_KEY) ?? '{}');
    return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
  } catch { return {}; }
}

function aboutDisclosureState(section: keyof typeof ABOUT_DISCLOSURE_DEFAULTS): boolean {
  try {
    const saved = savedAboutDisclosureState();
    return typeof saved[section] === 'boolean' ? saved[section] : ABOUT_DISCLOSURE_DEFAULTS[section];
  } catch { return ABOUT_DISCLOSURE_DEFAULTS[section]; }
}

function rememberAboutDisclosure(event: SyntheticEvent<HTMLDetailsElement>, section: keyof typeof ABOUT_DISCLOSURE_DEFAULTS) {
  try {
    const saved = savedAboutDisclosureState();
    saved[section] = event.currentTarget.open;
    window.localStorage.setItem(ABOUT_DISCLOSURE_KEY, JSON.stringify(saved));
  } catch { /* About remains usable when browser storage is unavailable. */ }
}

function AboutWorkflow() {
  const stages = [
    { title: 'Create a project', notes: ['Choose a subject or sample.', 'State the question you want to investigate.'] },
    { title: 'Explore strategies', notes: ['Develop several approaches to the question.', 'Choose which strategies to investigate.'] },
    { title: 'Run research', notes: ['Investigator and Skeptic examine selected strategies.', 'Sessions save evidence, objections, results, and open questions.'] },
    { title: 'Review and refine', notes: ['Inspect findings, the Outcome, and Current Understanding.', 'Revise strategies or run more sessions when useful.'] },
    { title: 'Draft a paper (optional)', notes: ['Synthesize research into an academic paper draft.', 'A draft is not proof or independent verification.'] },
    { title: 'Review and export', notes: ['Export research records and reports without a paper.', 'For a draft, review claims, evidence, citations, and limits before PDF or TeX export.'] },
  ];
  return <ol className="about-workflow" aria-label="SIGMA research workflow">{stages.map((stage, index) => <li className="about-workflow-stage" key={stage.title}>
    <div className="about-workflow-step"><span className="about-workflow-number" aria-hidden="true">{index + 1}</span><h3>{stage.title}</h3></div>
    <ul className="about-workflow-notes">{stage.notes.map(note => <li key={note}>{note}</li>)}</ul>
  </li>)}</ol>;
}

function AboutDialog({ onClose }: { onClose: () => void }) {
  const [legalView, setLegalView] = useState<'privacy' | 'terms' | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const cloud = useCloudIdentity();
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  useEffect(() => { closeButton.current?.focus(); }, [legalView]);
  const dismiss = () => { if (legalView) setLegalView(null); else onClose(); };
  return <div className="home-page about-dialog-style-scope"><dialog ref={dialog} className={`project-entry-dialog about-dialog${legalView ? ' about-legal-dialog' : ''}`} aria-labelledby={legalView ? 'about-legal-heading' : 'about-heading'} onCancel={event => { event.preventDefault(); dismiss(); }} onClick={event => { if (event.target === event.currentTarget) dismiss(); }}>
    {legalView ? <div className="about-legal-document"><div className="entry-dialog-header privacy-notice-heading"><h2 id="about-legal-heading">{legalView === 'privacy' ? 'SIGMA Privacy Notice' : 'Terms of Service'}</h2><DialogDismissButton ref={closeButton} label={legalView === 'privacy' ? 'Close privacy notice' : 'Close terms of service'} onClick={dismiss}/></div><div className="about-legal-document-body">{legalView === 'privacy' ? <PrivacyNoticeContent/> : <TermsOfServiceContent/>}</div></div> : <>
    <div className="entry-dialog-header"><h2 id="about-heading">About SIGMA</h2><DialogDismissButton ref={closeButton} label="Close About SIGMA" onClick={onClose}/></div>
    <div className="about-dialog-content">
      <p className="about-intro"><strong>SIGMA is a research workbench for exploring answers to hard questions from different angles.</strong></p>
      <details className="about-disclosure about-workflow-disclosure" data-about-section="workflow" open={aboutDisclosureState('workflow')} onToggle={event => rememberAboutDisclosure(event, 'workflow')}>
        <summary>Research Process</summary>
        <div className="about-disclosure-content"><AboutWorkflow/></div>
      </details>
      <details className="about-disclosure" data-about-section="features" open={aboutDisclosureState('features')} onToggle={event => rememberAboutDisclosure(event, 'features')}>
        <summary>Key Features</summary>
        <div className="about-disclosure-content">
      <section className="about-feature"><h4>Multi-Strategy Exploration</h4><p>Hard problems often need more than one approach. Each strategy explores a particular angle, rather than proposing an answer. Strategies can be tested, revised, or combined as the research develops. Even failed approaches can teach us something useful.</p></section>
      <section className="about-feature"><h4>Multiple Research Agents</h4><p>Different agents investigate ideas, challenge assumptions, and look for weaknesses in the reasoning.</p></section>
      <section className="about-feature"><h4>Research History</h4><p>SIGMA keeps a record of strategies, research sessions, experiments, and findings so earlier work isn't lost. Failed approaches remain available for review and further investigation.</p></section>
      <section className="about-feature"><h4>Research That Builds on Earlier Work</h4><p>Researchers can use earlier findings to guide later investigations, including findings that ruled out an approach. SIGMA does not automatically combine discoveries across strategies.</p></section>
      <section className="about-feature"><h4>Human Guidance</h4><p>Researchers can provide feedback, revise strategies, and choose which directions to pursue.</p></section>
      <section className="about-feature"><h4>Python and SageMath Execution</h4><p>Agents can write and run Python code to test ideas, perform calculations, and check results. The code and execution output are recorded with the research session. SageMath execution has not yet been independently verified.</p></section>
      <section className="about-feature"><h4>Evidence and Uncertainty</h4><p>Outcomes distinguish supported findings from unresolved questions and claims that still need verification. SIGMA records evidence and review status; it does not independently verify mathematical proofs.</p></section>
      <section className="about-feature"><h4>Readable Mathematical Text</h4><p>AI can reformat plain-text project descriptions and Conclusions as Markdown with typeset equations. The original text remains available; formatted mathematics still needs review.</p></section>
      <section className="about-feature"><h4>Reports and Exports</h4><p>Research records and reports can be exported for review, sharing, and further work.</p></section>
          <section className="about-feature"><h4>Experimental LaTeX Paper Generation</h4><p>SIGMA can generate a draft mathematical paper in LaTeX format with equations, arguments, and supporting evidence. This feature is experimental; the draft needs human review and may contain errors.</p></section>
        </div>
      </details>
      <details className="about-disclosure about-architecture-disclosure" data-about-section="architecture" open={aboutDisclosureState('architecture')} onToggle={event => rememberAboutDisclosure(event, 'architecture')}>
        <summary>How SIGMA Works: Multi-Agentic Research</summary>
        <div id="about-architecture-details" className="about-disclosure-content"><AboutArchitecture/></div>
      </details>
      <details className="about-disclosure about-provenance-disclosure" data-about-section="provenance" open={aboutDisclosureState('provenance')} onToggle={event => rememberAboutDisclosure(event, 'provenance')}>
        <summary>Vision for Investigation Provenance</summary>
        <div id="about-provenance-details" className="about-disclosure-content"><AboutProvenanceVision/></div>
      </details>
      {cloud?.enabled && cloud.ready && <details className="about-disclosure about-feedback-disclosure" data-about-section="feedback" open={aboutDisclosureState('feedback')} onToggle={event => rememberAboutDisclosure(event, 'feedback')}><summary>Send product feedback</summary><div className="about-disclosure-content"><FeedbackForm signedInEmail={cloud.authenticated ? cloud.user?.email || null : null}/></div></details>}
    </div>
    <footer className="about-dialog-footer"><nav className="about-legal-links" aria-label="Legal information"><button type="button" className="about-privacy-link sigma-text-action" onClick={() => setLegalView('privacy')}>Privacy Notice</button><button type="button" className="about-privacy-link sigma-text-action" onClick={() => setLegalView('terms')}>Terms of Service</button></nav><small className="about-build-commit">Version <code>{__SIGMA_VERSION__}</code> · Build <code>{__SIGMA_BUILD_COMMIT__}</code></small></footer>
  </>}
  </dialog></div>;
}

// Align the VISIBLE pill group rather than a padded wrapper. Home and Project
// have different containing blocks, so CSS right/margin guesses are unreliable.
// Translate only the entire group; never adjust gaps or individual pills.
function useEqualHeaderPillInsets() {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const group = ref.current;
    if (!group) return;
    let frame = 0;
    const measure = () => {
      group.style.translate = '0px 0px';
      const controls = group.querySelectorAll<HTMLElement>(
        '.administrator-settings-link, .home-about-button, .about-action, .home-settings-pill, ' +
        '.project-global-settings-pill, .project-google-signin, .global-model-pill, .api-connection > summary'
      );
      const bounds = Array.from(controls, control => control.getBoundingClientRect())
        .filter(rect => rect.width > 0 && rect.height > 0);
      if (!bounds.length) return;
      const top = Math.min(...bounds.map(rect => rect.top));
      const right = Math.max(...bounds.map(rect => rect.right));
      const rightInset = document.documentElement.clientWidth - right;
      group.style.translate = `${Math.round(rightInset - top)}px 0px`;
    };
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(measure);
    };
    measure();
    const observer = new ResizeObserver(schedule);
    observer.observe(group);
    window.addEventListener('resize', schedule);
    void document.fonts.ready.then(() => { if (group.isConnected) schedule(); });
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener('resize', schedule);
      group.style.translate = '';
    };
  }, []);
  return ref;
}

function Header({ goHome, close, projectTitle, projectType, projectDifficulty, projectView, onProjectUpdated, projectActions, projectArtwork = false, chatPage = false, connectionDisabled = false, researchRunning = false, paperRunning = false, paperQueued = false, askRunning = false, activeRunLabels = [], activityStatus, onIdleProjectTitleClick, onActivityClick }: { goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean }; projectTitle?: string; projectType?: ResearchMode; projectDifficulty?: ProjectDifficulty | null; projectView?: ProjectView; onProjectUpdated?: (view: ProjectView) => void; projectActions?: React.ReactNode; projectArtwork?: boolean; chatPage?: boolean; connectionDisabled?: boolean; researchRunning?: boolean; paperRunning?: boolean; paperQueued?: boolean; askRunning?: boolean; activeRunLabels?: string[]; activityStatus?: 'active' | 'queued' | null; onIdleProjectTitleClick?: () => void; onActivityClick?: () => void }) {
  const cloud = useCloudIdentity();
  const showConnectionStatus = !cloud?.enabled || (cloud.authenticated && cloud.user?.role !== 'guest');
  const [globalSettingsOpen, setGlobalSettingsOpen] = useState(false);
  const headerPillsRef = useEqualHeaderPillInsets();
  const idleTitleRef = useRef<HTMLButtonElement>(null);
  const activeTitleRef = useRef<HTMLButtonElement>(null);
  const hasActivity = activityStatus === undefined
    ? researchRunning || paperRunning || paperQueued || askRunning : activityStatus !== null;
  const queuedOnly = activityStatus === undefined
    ? paperQueued && !researchRunning && !paperRunning && !askRunning : activityStatus === 'queued';
  useLayoutEffect(() => {
    const button = activeTitleRef.current ?? idleTitleRef.current;
    const row = button?.parentElement;
    if (!button || !row) return;

    // Layout the title at the full available column width to find its actual
    // text fragments (one or two lines), then shrink the hit/highlight box to
    // the longest visible line. Measuring the natural max-content width would
    // incorrectly suppress wrapping for longer project titles.
    const measure = () => {
      if (!button.isConnected) return;
      button.style.width = '100%';
      const available = button.getBoundingClientRect();
      const label = button.querySelector('.project-header-title-label');
      const titleText = button.querySelector<HTMLElement>('.project-header-title-text');
      const pulse = button.querySelector<HTMLElement>('.research-running-indicator-frame');
      // The button shrinks to the longest text line, but the title must keep
      // the full wrapping width. Otherwise narrowing the button changes the
      // line breaks and invalidates the hover measurement.
      if (titleText) titleText.style.width = `${available.width}px`;
      const range = document.createRange();
      // The active title contains a block wrapper and a flasher. Neither
      // belongs in the hover hit box: measure only the rendered title text.
      range.selectNodeContents(label ?? button);
      const longest = Math.max(0, ...Array.from(range.getClientRects())
        .filter(rect => rect.width > 0 && rect.top < available.bottom + 1)
        .map(rect => rect.width));
      button.style.width = longest > 0
        ? `${Math.min(available.width, Math.ceil(longest + 4))}px`
        : '';
      // Keep the pulse beside the final glyph even when the title wraps.
      // Absolute positioning makes it visual only, not part of button width.
      if (pulse && label) {
        const fragments = Array.from(range.getClientRects()).filter(rect => rect.width > 0);
        const last = fragments.at(-1);
        if (last) {
          const box = button.getBoundingClientRect();
          const pulseHeight = pulse.getBoundingClientRect().height;
          pulse.style.left = `${Math.ceil(last.right - box.left + 4)}px`;
          pulse.style.top = `${Math.round(last.top - box.top + (last.height - pulseHeight) / 2)}px`;
        }
      }
    };
    measure();
    // Watch the enclosing track, not the button whose width we adjust.
    // Ignore height-only changes to avoid observer/reflow feedback loops.
    let lastWidth = row.getBoundingClientRect().width;
    const observer = new ResizeObserver(() => {
      const width = row.getBoundingClientRect().width;
      if (Math.abs(width - lastWidth) < 0.5) return;
      lastWidth = width;
      measure();
    });
    observer.observe(row);
    let disposed = false;
    void document.fonts.ready.then(() => { if (!disposed) measure(); });
    return () => { disposed = true; observer.disconnect(); };
  }, [projectTitle, hasActivity, projectArtwork]);
  return <header className={`${projectArtwork ? 'site-header project-art-header' : 'site-header'}${chatPage ? ' chat-site-header' : ''}`}>
    <div className="brand-block">
      <a href="/" className={projectArtwork ? 'brand project-header-art' : 'brand'} onClick={goHome} aria-label="Go back to home page" data-tooltip="Go back to home page" data-tooltip-follow-cursor="true"><img src={projectArtwork ? '/sigma-project-header.png' : '/sigma-workspace-logo.png'} alt="SIGMA" /></a>
      {projectArtwork ? close && <div className="project-title-line">{projectTitle && <><div className="project-header-title-row">{projectType && <ResearchTypeIcon type={projectType} snapshot={projectView?.project.project_type_snapshot}/>}{hasActivity
        ? <button type="button" ref={activeTitleRef} className="project-header-title project-header-title-action" data-tooltip-follow-cursor="true" aria-label={`${researchRunning ? 'Scroll to running session' : paperRunning || paperQueued ? 'Scroll to Papers' : 'Open Research Q/A'} in ${projectTitle}`} onClick={onActivityClick ?? (() => window.dispatchEvent(new Event(researchRunning ? 'sigma-reveal-running-session' : paperRunning || paperQueued ? 'sigma-reveal-papers' : 'sigma-reveal-qa')))}><span className="project-header-title-text"><span className="project-header-title-label">{projectTitle}</span><span className="research-running-indicator-frame" aria-hidden="true" data-tooltip={activeRunLabels.length ? activeRunLabels.join('\n') : researchRunning ? 'Session' : paperRunning || paperQueued ? 'Paper' : 'Answer'} data-tooltip-activity="true"><span className={`research-running-indicator${queuedOnly ? " paper-queued-indicator" : ""}`}/></span></span></button>
        : onIdleProjectTitleClick
          ? <button type="button" ref={idleTitleRef} className="project-header-title project-header-title-idle-action" data-tooltip-follow-cursor="true" aria-label="Toggle all project sections" onClick={onIdleProjectTitleClick}>{projectTitle}</button>
          : <span className="project-header-title">{projectTitle}</span>}</div>{projectActions}</>}</div>
        : <p className="expansion">Strategy Investigation, Generation, Measurement &amp; Assessment</p>}
    </div>
    {chatPage && <div className="chat-header-center-slot" aria-label="Chat model and thinking settings"/>}
    <div ref={headerPillsRef} className="header-controls">
    {!close && <span className="local">● Local workspace</span>}
    {close && projectView && onProjectUpdated ? <>

      <MockAuthSelector/><div className="identity-pill-stack project-identity-pill-stack sigma-header-account-column"><GoogleIdentityPill/>{showConnectionStatus && <ConnectionStatus projectHeader cloudFunding={cloudFundingFor(cloud)} zeroAllowanceAction={<ReloadMeAction connectionPill/>}/>}</div>
    </> : showConnectionStatus && <ConnectionStatus cloudFunding={cloudFundingFor(cloud)} zeroAllowanceAction={<ReloadMeAction connectionPill/>}/>}
    {close && projectView && <div className="sigma-header-model-column">
      <div className="sigma-header-secondary-row">
        {cloud?.user?.role === 'admin' && <a href="#administrator-settings" className="administrator-settings-link" aria-label="Administrator settings" onClick={event => { event.preventDefault(); cloud.openAccessManagement(); }}>Admin Settings</a>}
        <div className="sigma-header-about-model-anchor">
          <div className="sigma-header-first-row">
            <button type="button" className="about-action" aria-label="About SIGMA" data-tooltip-disabled onClick={() => window.dispatchEvent(new Event('sigma-open-about'))}>About SIGMA</button>
            {onProjectUpdated && showConnectionStatus && <button type="button" className="project-control-pill project-difficulty-badge project-global-settings-pill" aria-label="Settings" data-tooltip="SIGMA Settings" aria-haspopup="dialog" aria-expanded={globalSettingsOpen} onClick={() => setGlobalSettingsOpen(true)}><SlidersSettingsIcon/></button>}
          </div>
          <ConnectedModelPill enabled={showConnectionStatus}/>
        </div>
      </div>
    </div>}
    </div>
    {globalSettingsOpen && <GlobalSettingsDialog onClose={() => setGlobalSettingsOpen(false)}/>}
  </header>;
}

function WorkspaceIcon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    Strategies: 'M3 3h6v6H3z M15 3h6v6h-6z M3 15h6v6H3z M15 15h6v6h-6z',
    Renders: 'M5 3h10l4 4v14H5z M14 3v5h5 M8 12h8 M8 16h6',
    Analysis: 'M4 20h17 M6 16v-5 M11 16V4 M16 16V8 M21 16v-3',
    References: 'M12 5c-3-2-6-2-10-1v16c4-1 7-1 10 1 3-2 6-2 10-1V4c-4-1-7-1-10 1v16',
    Notes: 'M5 3h14v18H5z M8 8h8 M8 12h8 M8 16h5',
    Settings: 'M12 2.5v2.3 M12 19.2v2.3 M2.5 12h2.3 M19.2 12h2.3 M5.28 5.28l1.63 1.63 M17.09 17.09l1.63 1.63 M5.28 18.72l1.63-1.63 M17.09 6.91l1.63-1.63 M16.5 12a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0',
  };
  return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
    strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>;
}

function focusWorkspace(id: string) {
  const target = document.getElementById(id) ?? document.getElementById('workspace-content');
  target?.focus(); target?.scrollIntoView({ block: 'start' });
}

function WorkspaceFrame({ children, goHome, close, projectTitle, projectType, projectView, onProjectUpdated, projectActions, connectionDisabled = false, researchRunning = false, paperRunning = false, paperQueued = false, askRunning = false, activeRunLabels = [], activityStatus, onIdleProjectTitleClick, onActivityClick }: {
  children: React.ReactNode; goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean }; projectTitle?: string; projectType?: ResearchMode; projectView?: ProjectView; onProjectUpdated?: (view: ProjectView) => void; projectActions?: React.ReactNode; connectionDisabled?: boolean; researchRunning?: boolean; paperRunning?: boolean; paperQueued?: boolean; askRunning?: boolean; activeRunLabels?: string[]; activityStatus?: 'active' | 'queued' | null; onIdleProjectTitleClick?: () => void; onActivityClick?: () => void;
}) {
  const [collapsed, setCollapsed] = useState(() => window.localStorage.getItem('sigma.sidebarCollapsed') === 'true');
  function toggleSidebar() {
    setCollapsed(value => {
      window.localStorage.setItem('sigma.sidebarCollapsed', String(!value));
      return !value;
    });
  }
  return <>
    <a className="workspace-skip" href="#workspace-content" onClick={event => {
      event.preventDefault(); focusWorkspace('workspace-content');
    }}>Skip to project content</a>
    <Header goHome={goHome} close={close} projectTitle={projectTitle} projectType={projectType} projectView={projectView} onProjectUpdated={onProjectUpdated} projectActions={projectActions} projectArtwork connectionDisabled={connectionDisabled} researchRunning={researchRunning} paperRunning={paperRunning} paperQueued={paperQueued} askRunning={askRunning} activeRunLabels={activeRunLabels} activityStatus={activityStatus} onIdleProjectTitleClick={onIdleProjectTitleClick} onActivityClick={onActivityClick}/>
    <div className={`workspace-layout${!ENABLE_WORKSPACE_SIDEBAR ? ' sidebar-disabled' : collapsed ? ' nav-collapsed' : ''}`}>
      {ENABLE_WORKSPACE_SIDEBAR && <nav className="workspace-nav" aria-label="Project navigation">
        <button className="nav-collapse" type="button" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} data-tooltip={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} onClick={toggleSidebar}><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={collapsed ? 'm9 6 6 6-6 6' : 'm15 6-6 6 6 6'}/></svg></button>
        <a href="#project-pane-heading" aria-label="Project" data-tooltip={collapsed ? 'Project' : undefined} onClick={event => { event.preventDefault(); focusWorkspace('project-pane-heading'); }}><WorkspaceIcon name="Settings"/><span>Project</span></a>
        <a href="#sessions-heading" aria-label="Sessions" data-tooltip={collapsed ? 'Sessions' : undefined} onClick={event => { event.preventDefault(); focusWorkspace('sessions-heading'); }}><WorkspaceIcon name="Analysis"/><span>Sessions</span></a>
        <a href="#pool-heading" aria-current="page" aria-label="Strategies" data-tooltip={collapsed ? 'Strategies' : undefined} onClick={event => {
          event.preventDefault(); focusWorkspace('pool-heading');
        }}><WorkspaceIcon name="Strategies"/><span>Strategies</span></a>
        {['Renders', 'Analysis', 'References', 'Notes', 'Settings'].map(name =>
          <button key={name} disabled data-tooltip={collapsed ? `${name} · later` : 'Not available yet'} aria-label={name} aria-describedby="workspace-nav-help">
            <WorkspaceIcon name={name}/><span>{name}</span><small>Later</small>
          </button>)}
        <p id="workspace-nav-help">Other destinations are not available yet.</p>
      </nav>}
      <div id="workspace-content" className="workspace-content" tabIndex={-1}>{children}</div>
    </div>
  </>;
}

type Destination = { root: string; path: string | null; exists: boolean };

type ResearchQASource = { source_id: string; session_number: number | null; kind: string; label?: string; navigation_available?: boolean; navigation_url?: string; navigation_unavailable_reason?: string };
type ResearchQARecord = { qa_id: string; request_id: string; question: string; answer: string; author_email?: string; created_by?: string; markdown_answer?: string | null; sources: ResearchQASource[]; created_at: string; snapshot_sha256: string; generation: { model: string; reasoning_effort: string; generation_elapsed_seconds: number } };

function GuestFeatureCard({ title, message, onClose }: { title: string; message: string; onClose: () => void }) {
  return <section className="research-pause-guidance guest-feature-card" role="status" aria-label={title}>
    <div className="guest-feature-card-header"><strong>{title}</strong><DialogDismissButton label="Dismiss preview" onClick={onClose}/></div>
    <p>{message}</p>
    <p className="guest-feature-access-note">Member access and a connected ChatGPT account are required. No AI request was made.</p>
  </section>;
}

function GuestFeatureDialog({ title, message, onClose }: { title: string; message: string; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    ref.current?.showModal();
    return () => {
      if (ref.current?.open) ref.current.close();
      requestAnimationFrame(() => previousFocus.current?.isConnected && previousFocus.current.focus());
    };
  }, []);
  return <dialog ref={ref} className="project-settings-dialog guest-research-dialog" aria-label={title}
    onCancel={event => { event.preventDefault(); onClose(); }}>
    <header className="settings-header"><h2>{title}</h2><DialogDismissButton label="Close preview" onClick={onClose}/></header>
    <div className="settings-body"><p>{message}</p>
      <p className="settings-hint">This is a preview. No ChatGPT request was made and no research was changed.</p>
      <p className="settings-hint">AI execution requires authorized SIGMA access and an available ChatGPT connection or supported provider.</p>
      <button type="button" className="text-view-link" onClick={onClose}>Close</button>
    </div>
  </dialog>;
}

function LeanPlaceholderDialog({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  return <dialog ref={dialog} className="project-settings-dialog ai-paper-dialog lean-placeholder-dialog" aria-labelledby="lean-placeholder-heading" onCancel={event => { event.preventDefault(); onClose(); }}>
    <header className="settings-header"><h2 id="lean-placeholder-heading">Lean proof verification</h2><div className="settings-actions"><DialogDismissButton label="Close Lean dialog" onClick={onClose}/></div></header>
    <div className="settings-body ai-paper-body"><p>Yeah, I'd love to see this too.<br/>Still under consideration!</p></div>
  </dialog>;
}

function ResearchQADialog({ path, projectId, guest, viewerEmail, projectOwnerEmail, answerAuthors, onCancel }: { path: string; projectId: string; guest: boolean; viewerEmail?: string; projectOwnerEmail?: string | null; answerAuthors?: Record<string, string>; onCancel: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const request = useRef<AbortController | null>(null);
  const [question, setQuestion] = useState('');
  const [guestAskPreview, setGuestAskPreview] = useState(false);
  const [guestAnswerMarkdownPreview, setGuestAnswerMarkdownPreview] = useState(false);
  const [answers, setAnswers] = useState<ResearchQARecord[]>([]);
  const [pendingAnswers, setPendingAnswers] = useState<{ request_id: string; creator: string; model: string; thinking: string }[]>([]);
  const [binding, setBinding] = useState('');
  const [configError, setConfigError] = useState('');
  const [model, setModel] = useState('');
  const [effort, setEffort] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [expanded, setExpanded] = useState('');
  const [removeId, setRemoveId] = useState('');
  const [copiedId, setCopiedId] = useState('');
  const [renderedAnswerIds, setRenderedAnswerIds] = useState<Set<string>>(() => new Set());
  const [formattingAnswerId, setFormattingAnswerId] = useState('');
  const formattingRequest = useRef<AbortController | null>(null);
  const [recovery, setRecovery] = useState<{ question: string; id: string } | null>(null);
  // A pending question belongs to this tab and this account, not to the
  // project's shared storage. Only completed answers are shared.
  const qaIdentity = useCloudIdentity()?.user?.email ?? viewerEmail ?? 'local';
  const requestKey = `sigma.researchQaRequest:${projectId}:${qaIdentity.toLowerCase()}`;
  useEffect(() => {
    dialog.current?.showModal();
    setQuestion('');
    setRecovery(null);
    try {
      const saved = JSON.parse(window.sessionStorage.getItem(requestKey) ?? 'null') as { question?: string; id?: string } | null;
      if (saved?.question && saved.id) { setQuestion(saved.question); setRecovery({ question: saved.question, id: saved.id }); }
    } catch { window.sessionStorage.removeItem(requestKey); }
    void refresh();
    return () => { request.current?.abort(); formattingRequest.current?.abort(); };
  }, [guest, requestKey]);
  async function refresh(silent = false): Promise<{ answers: ResearchQARecord[]; archiveAvailable: boolean } | null> {
    if (!silent) setLoading(true);
    try {
      const q = new URLSearchParams({ path });
      const response = await fetch(`/api/projects/research-qa?${q}`, { cache: 'no-store' });
      const list = await response.json();
      if (!response.ok) throw new Error(list.error ?? 'Could not load Q/A answers.');
      const saved = (list.answers ?? []) as ResearchQARecord[];
      if (typeof list.archive_available !== 'boolean') throw new Error('Could not verify the Q/A archive.');
      setAnswers(saved);
      return { answers: saved, archiveAvailable: list.archive_available };
    } catch (cause) { setError(errorMessage(cause)); return null; }
    finally { if (!silent) setLoading(false); }
  }
  useEffect(() => {
    if (guest) return;
    const controller = new AbortController();
    let requesting = false;
    let retryTimer: number | undefined;
    const loadConfiguration = async () => {
      if (controller.signal.aborted || requesting) return;
      requesting = true;
      const attempt = new AbortController();
      const abortAttempt = () => attempt.abort();
      controller.signal.addEventListener('abort', abortAttempt, { once: true });
      // A hung configuration read must also be retried, not just a failed one.
      const timeout = window.setTimeout(abortAttempt, 8000);
      try {
        const response = await fetch(
          `/api/projects/proposals/config?${new URLSearchParams({ path })}`,
          { cache: 'no-store', signal: attempt.signal, headers: { 'X-Sigma-Error-Handled': 'true' } },
        );
        const current = await response.json();
        if (!response.ok || !current.available || typeof current.binding !== 'string' || !current.binding) {
          throw new Error(current.error ?? current.message ?? 'Model configuration is unavailable.');
        }
        if (controller.signal.aborted) return;
        setBinding(current.binding);
        setModel(current.model ?? '');
        setEffort(current.reasoning_effort ?? '');
        setConfigError('');
        if (retryTimer !== undefined) window.clearInterval(retryTimer);
      } catch (cause) {
        if (!controller.signal.aborted) {
          const detail = attempt.signal.aborted ? 'Request timed out' : errorMessage(cause);
          setConfigError(`Could not load model settings: ${detail}. Retrying…`);
        }
      } finally {
        window.clearTimeout(timeout);
        controller.signal.removeEventListener('abort', abortAttempt);
        requesting = false;
      }
    };
    // Never leave Ask permanently disabled after a transient configuration
    // failure. Retry only the read; never resubmit an answer/provider call.
    retryTimer = window.setInterval(() => void loadConfiguration(), 3500);
    void loadConfiguration();
    return () => { controller.abort(); if (retryTimer !== undefined) window.clearInterval(retryTimer); };
  }, [guest, path]);

  useEffect(() => {
    if (guest) return;
    let closed = false;
    const poll = async () => {
      try {
        const response = await fetch(`/api/projects/research-qa/activity?${new URLSearchParams({ path })}`,
          { cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } });
        if (!closed && response.ok) {
          const data = await response.json();
          if (!closed) setPendingAnswers(Array.isArray(data.active) ? data.active : []);
        }
        if (!closed) await refresh(true);
      } catch { /* Keep saved and pending answers visible through transient disconnects. */ }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 2000);
    return () => { closed = true; window.clearInterval(timer); };
  }, [guest, path]);
  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim() || busy) return;
    if (guest) { setGuestAskPreview(true); return; }
    if (!binding) return;
    if (recovery?.question === question) {
      // A response might have completed after its browser request failed.
      // Check for the durable result before an explicitly requested retry.
      const saved = await refresh();
      if (!saved) return;
      // An empty or not-yet-created archive is normal for a project with no
      // completed Q/A. A successful read is sufficient to proceed; keep the
      // explicit retry available even if no previous answer was found.
      const completed = saved.answers.find(record => record.request_id === recovery.id);
      if (completed) {
        window.sessionStorage.removeItem(requestKey);
        setRecovery(null); setQuestion(''); setExpanded(completed.qa_id); setError('');
        setSuccess('');
        return;
      }
    }
    await submitQuestion(crypto.randomUUID().replaceAll('-', ''));
  }
  async function submitQuestion(requestId: string) {
    if (!question.trim() || busy || !binding) return;
    const controller = new AbortController(); request.current = controller; setBusy(true); setError(''); setSuccess('');
    window.sessionStorage.setItem(requestKey, JSON.stringify({ question, id: requestId }));
    try {
      const response = await fetch('/api/projects/research-qa', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal, body: JSON.stringify({ path, question, expected_project_id: projectId, expected_binding: binding, request_id: requestId }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Research Q/A failed.');
      window.sessionStorage.removeItem(requestKey); setRecovery(null); setQuestion(''); setExpanded(result.qa_id); setSuccess(''); await refresh();
    } catch (cause) {
      // Cancel is silent, but retain the request ID because the provider
      // might finish after the browser stops listening.
      setRecovery({ question, id: requestId });
      if (!controller.signal.aborted) {
        setError(errorMessage(cause));
        await refresh();
      }
    } finally { request.current = null; setBusy(false); }
  }
  async function remove(id: string) {
    try {
      const response = await fetch(`/api/projects/research-qa/${encodeURIComponent(id)}?${new URLSearchParams({ path })}`, { method: 'DELETE' });
      const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Could not remove answer.');
      setRemoveId(''); setAnswers(current => current.filter(item => item.qa_id !== id)); setSuccess('Answer removed. Research sessions were unchanged.');
    } catch (cause) { setError(errorMessage(cause)); }
  }
  async function toggleAnswerMarkdown(record: ResearchQARecord) {
    if (formattingAnswerId || busy) return;
    if (renderedAnswerIds.has(record.qa_id)) {
      setRenderedAnswerIds(current => { const next = new Set(current); next.delete(record.qa_id); return next; });
      return;
    }
    if (record.markdown_answer) {
      setRenderedAnswerIds(current => new Set(current).add(record.qa_id));
      return;
    }
    if (guest) { setGuestAnswerMarkdownPreview(true); return; }
    const controller = new AbortController();
    formattingRequest.current = controller;
    setFormattingAnswerId(record.qa_id); setError('');
    const finishProviderRequest = beginProviderRequest('text-conversion');
    try {
      const expectedDigest = await sha256Text(record.answer);
      const markdownResponse = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path, purpose: 'markdown' })}`, { signal: controller.signal });
      const markdownSettings = await markdownResponse.json();
      if (!markdownResponse.ok || !markdownSettings.available) throw new Error(markdownSettings.message ?? 'Markdown formatting is unavailable.');
      const response = await fetch('/api/projects/text/convert', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ path, scope: 'research-qa', qa_id: record.qa_id, target: 'markdown',
          expected_digest: expectedDigest, expected_binding: markdownSettings.binding, expected_project_id: projectId }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? 'Markdown conversion failed; original answer was kept.');
      const converted = data.markdown?.body;
      if (typeof converted !== 'string' || !converted.trim()) throw new Error('Markdown conversion did not produce text.');
      setAnswers(current => current.map(item => item.qa_id === record.qa_id ? { ...item, markdown_answer: converted } : item));
      setRenderedAnswerIds(current => new Set(current).add(record.qa_id));
    } catch (cause) {
      if (!controller.signal.aborted) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    } finally {
      finishProviderRequest();
      formattingRequest.current = null; setFormattingAnswerId('');
    }
  }
  async function copy(record: ResearchQARecord) {
    try {
      const response = await fetch(`/api/projects/research-qa/${encodeURIComponent(record.qa_id)}/markdown?${new URLSearchParams({ path })}`, { cache: 'no-store' });
      if (!response.ok) throw new Error('Could not load the Markdown document.');
      const markdown = await response.text();
      try { await navigator.clipboard.writeText(markdown); }
      catch { throw new Error('Clipboard access failed. Check browser clipboard permissions and try again.'); }
      setCopiedId(record.qa_id); window.setTimeout(() => setCopiedId(current => current === record.qa_id ? '' : current), 1600);
    } catch (cause) { setError(errorMessage(cause)); }
  }

  return <dialog ref={dialog} className="project-settings-dialog ai-paper-dialog research-qa-dialog" aria-labelledby="research-qa-heading" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }} onKeyDownCapture={event => { if (event.key === 'Escape' && busy) { event.preventDefault(); event.stopPropagation(); } }}>
    <header className="settings-header"><h2 id="research-qa-heading">Research Q/A</h2><div className="settings-actions"><DialogDismissButton label="Close research Q/A" disabled={busy} onClick={onCancel}/></div></header>
    <div className="settings-body ai-paper-body">
      {guestAnswerMarkdownPreview && createPortal(<GuestFeatureDialog title="Format an answer as Markdown"
        message="With an authorized model, SIGMA can format an answer as readable Markdown for review. This does not re-evaluate the research or prove its findings."
        onClose={() => setGuestAnswerMarkdownPreview(false)}/>, document.body)}
      <>
        <p className="settings-hint">Ask a question about the research performed in this project. SIGMA will answer using project research sessions and cite supporting evidence.</p>
        {guest ? <p className="settings-hint ai-paper-model">Guest preview · no ChatGPT connection or model execution</p>
          : <p className="settings-hint ai-paper-model">Project model: <strong>{model || 'Loading…'}</strong> · thinking level: <strong>{effort || 'Loading…'}</strong></p>}
        {configError && <p role="alert" className="error">{configError}</p>}
        <form onSubmit={event => void ask(event)} className="research-qa-form"><div className="research-qa-question-heading"><label htmlFor="research-qa-question">Question</label><div className="ai-paper-controls">{busy ? <><span data-tooltip={formatRunAttribution({ kind: 'answer', creator: viewerEmail, model, thinking: effort, mode: 'hover' })}><button type="button" className="text-view-link" disabled aria-label="Answering">⌛ Answering…</button></span><button type="button" className="text-view-link" onClick={() => request.current?.abort()}>Cancel</button></> : <button type="submit" className="text-view-link" disabled={(!guest && !binding) || !question.trim()}>Ask</button>}</div></div><textarea id="research-qa-question" rows={4} maxLength={4000} value={question} disabled={busy} onChange={event => setQuestion(event.target.value)} placeholder="Ask about the research…"/></form>
        {guestAskPreview && <GuestFeatureCard title="Ask about your research" message="SIGMA answers questions using project research and cites supporting evidence. Answers require verification." onClose={() => setGuestAskPreview(false)}/>}
        {pendingAnswers.length > 0 && <section aria-label="Q/A in progress">
          {pendingAnswers.map(pending => <p className="ai-paper-status" role="status" key={pending.request_id}>
            <span className="research-running-indicator" aria-label="Answer in progress"
              data-tooltip={formatRunAttribution({ kind: 'answer', creator: pending.creator, model: pending.model, thinking: pending.thinking, mode: 'hover' })}/>
            {' Answering · '}{formatRunAttribution({ kind: 'answer', creator: pending.creator, model: pending.model, thinking: pending.thinking })}
          </p>)}
        </section>}
        {busy && <p role="status" className="ai-paper-status">Preparing evidence and asking the selected model…</p>}{success && <p role="status" className="ai-paper-status">{success}</p>}{error && <p role="alert" className="error">{error} <DialogDismissButton label="Dismiss error" onClick={() => setError('')}/></p>}
        {loading ? <p>Loading answers…</p> : answers.length > 0 && <section className="saved-paper-library research-qa-library" aria-label="Questions and answers"><h3>Answers</h3>{answers.map(record => <article className="saved-paper-card" key={record.qa_id}>
          <div className="saved-paper-row"><div className="saved-paper-heading"><SavedPaperTitle title={record.question} itemLabel="answer" expanded={expanded === record.qa_id} controls={`qa-body-${record.qa_id}`} onToggle={() => setExpanded(current => current === record.qa_id ? '' : record.qa_id)} copyName="Markdown answer" copied={copiedId === record.qa_id} onCopy={() => void copy(record)} inlineTitleActions beforeCopy={<span className="text-view-format-control qa-markdown-control"><button type="button" className={`qa-markdown-action sigma-render-toggle workspace-icon-button${renderedAnswerIds.has(record.qa_id) ? ' sigma-render-active' : ''}${formattingAnswerId === record.qa_id ? ' sigma-render-pending' : ''}`} aria-label={renderedAnswerIds.has(record.qa_id) ? 'Show plain answer' : 'Render answer as Markdown'} aria-pressed={renderedAnswerIds.has(record.qa_id) || formattingAnswerId === record.qa_id} data-tooltip={renderedAnswerIds.has(record.qa_id) ? 'Show plain text' : formattingAnswerId === record.qa_id ? 'Formatting with AI…' : 'Convert to Markdown'} disabled={busy || !!formattingAnswerId} onClick={() => void toggleAnswerMarkdown(record)}>{formattingAnswerId === record.qa_id ? <span aria-hidden="true">⌛</span> : <svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z" fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg>}</button>{formattingAnswerId === record.qa_id && <span className="text-view-format-status" role="status">Formatting with AI…</span>}</span>} actions={<>
            <button type="button" className="text-view-link text-view-icon workspace-icon-button paper-view-pdf-icon" aria-label="View answer in a new browser tab" data-tooltip="View answer in a new browser tab" onClick={() => window.open(`/project?${new URLSearchParams({ path, qa_browser: record.qa_id })}`, '_blank', 'noopener,noreferrer')}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M13 3.5H6a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-7"/><path d="M14 3.5h6.5V10M20.5 3.5l-9 9"/></svg></button>
            {!guest && (!viewerEmail || viewerEmail === projectOwnerEmail || answerAuthors?.[record.qa_id] === viewerEmail) && <button type="button" className="text-view-link text-view-icon workspace-icon-button paper-remove-button" aria-label="Remove answer" data-tooltip="Remove answer" onClick={() => setRemoveId(record.qa_id)}><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" aria-hidden="true"><path d="M8 8 16 16M16 8 8 16"/></svg></button>}
          </>}/><div className="saved-paper-meta"><p>{dateLabel(record.created_at)} · Elapsed {savedPaperElapsed(record.generation.generation_elapsed_seconds)} · {(record.author_email || (record.created_by && record.created_by !== 'Local user')) ? <span className="artifact-attribution">{formatRunAttribution({ kind: 'answer', creator: record.author_email || record.created_by, model: record.generation.model, thinking: record.generation.reasoning_effort })}</span> : modelThinkingLabel(record.generation.model, record.generation.reasoning_effort)}</p></div></div></div>
          {removeId === record.qa_id && <div className="saved-paper-confirm" role="group" aria-label="Confirm answer removal"><p>Remove this answer?</p><button type="button" className="text-view-link" onClick={() => void remove(record.qa_id)}>Confirm</button><DialogDismissButton label="Cancel answer removal" onClick={() => setRemoveId('')}/></div>}
          <div id={`qa-body-${record.qa_id}`} hidden={expanded !== record.qa_id}><article className="ai-paper-preview"><div className="research-qa-answer-heading"><h3>Answer</h3></div>{renderedAnswerIds.has(record.qa_id) && record.markdown_answer ? <div className="outcome-markdown"><Suspense fallback={<p>{record.answer}</p>}><RenderedMarkdown body={record.markdown_answer}/></Suspense></div> : <div className="research-qa-answer-plain">{record.answer}</div>}<h4>Sources</h4><ul>{record.sources.length ? record.sources.map((source, index) => <li key={`${source.source_id}-${index}`}>{source.navigation_available && source.navigation_url ? <a href={source.navigation_url}>{source.label || source.kind}</a> : <>{source.label || source.kind} · navigation unavailable{source.navigation_unavailable_reason ? `: ${source.navigation_unavailable_reason}` : ''}</>}</li>) : <li>No verified source links available.</li>}</ul></article></div>
        </article>)}</section>}
      </>
    </div>
  </dialog>;
}

function ImportProjectDialog({ onOpen, onCancel }: { onOpen: (view: ProjectView) => void; onCancel: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { dialog.current?.showModal(); }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true); setError('');
    try {
      const bundle = JSON.parse(await file.text());
      const response = await fetch('/api/projects/import', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bundle }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? result.detail ?? 'Project upload failed');
      onOpen(result as ProjectView);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }
  return <dialog ref={dialog} className="project-entry-dialog import-project-dialog" aria-labelledby="import-project-heading" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <header className="entry-dialog-header"><h2 id="import-project-heading">Upload Project</h2><button type="submit" form="import-project-form" className="entry-import" disabled={!file || busy}>{busy ? 'Uploading…' : 'Upload'}</button><DialogDismissButton label="Cancel upload" disabled={busy} onClick={onCancel}/></header>
    <p className="entry-help">Upload a complete SIGMA JSON project bundle. Existing projects are never replaced.</p>
    <form id="import-project-form" onSubmit={submit}><fieldset disabled={busy}><div className="import-project-label-row"><label htmlFor="import-project-file">Project file</label><button className="choose-project-file" type="button" onClick={() => fileInput.current?.click()}>Choose</button></div>
      <input ref={fileInput} className="sr-only" id="import-project-file" type="file" accept=".json,application/json" required onChange={event => setFile(event.target.files?.[0] ?? null)}/>
      <div className="import-project-file-row"><div className="import-project-selected-file" aria-live="polite">{file?.name ?? 'No file chosen'}</div></div>
      {error && <p className="error" role="alert">{error}</p>}
    </fieldset></form>
  </dialog>;
}

function ProjectEntryDialog({ initialPath, onOpen, onCancel }: {
  initialPath: string; onOpen: (view: ProjectView) => void; onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const first = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const [path, setPath] = useState(initialPath);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { dialog.current?.showModal(); first.current?.focus(); }, []);
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current) return; submitting.current = true; setBusy(true); setError('');
    try { onOpen(await post<ProjectView>('open', { path, compact: true })); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className="project-entry-dialog" aria-labelledby="project-entry-heading" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <header className="entry-dialog-header"><h2 id="project-entry-heading">Open Project</h2><DialogDismissButton label="Cancel opening project" disabled={busy} onClick={onCancel}/></header><p className="entry-help">Choose an existing local project by its directory path.</p>
    <form onSubmit={save}><fieldset disabled={busy}><label htmlFor="open-project-path">Project directory</label><div className="open-project-path-row"><input ref={first} id="open-project-path" required value={path} onChange={event => setPath(event.target.value)} aria-describedby="project-path-help"/><button className="open-project-submit" type="submit">{busy ? 'Opening…' : 'Open'}</button></div><p id="project-path-help" className="entry-hint">Try <code>projects/rh.sigma</code>, or an absolute path such as <code>/Users/you/projects/question.sigma</code>. Paths refer to this local server.</p>
    {error && <p className="error" role="alert">{error}</p>}</fieldset></form>
  </dialog>;
}

type Settings = { title: string; problem: string; desired_outcomes: string; paper_requirements: string; investigation_type: ResearchMode; ai_model: string; reasoning_effort: string; difficulty: ProjectDifficulty | null; show_advanced_outcome_details: boolean };
// Keep preference controls usable when account access cannot be checked.
const thinkingLabels: Record<string, string> = { low: 'Low', medium: 'Medium', high: 'High', xhigh: 'Extra high' };
const settingsOf = (view: ProjectView): Settings => ({ title: view.project.title, problem: view.project.problem, desired_outcomes: view.project.desired_outcomes ?? '', paper_requirements: view.project.paper_requirements ?? '', investigation_type: view.project.investigation_type, ai_model: view.project.ai_model, reasoning_effort: view.project.reasoning_effort, difficulty: view.project.difficulty, show_advanced_outcome_details: view.project.show_advanced_outcome_details });

function ResearchTypeIcon({ type, snapshot }: { type: ResearchMode; snapshot?: ProjectTypeRecord | null }) {
  const definition = snapshot?.id === type ? snapshot : projectTypeCache.find(item => item.id === type);
  const icon = definition?.icon;
  if (icon?.kind === 'data' && icon.data_uri) return <img className="research-type-icon research-type-icon-custom" src={icon.data_uri} alt=""/>;
  // Match the placeholder icon in builtin_project_types.json even before type metadata loads.
  if (icon?.kind !== 'builtin' || !Array.isArray(icon.elements)) return <svg className={`research-type-icon research-type-icon-${type}`} viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2.8 19.9 7.4v9.2L12 21.2 4.1 16.6V7.4L12 2.8Z"/></svg>;
  type IconNode = NonNullable<ProjectTypeRecord['icon']['elements']>[number];
  const render = (node: IconNode, key: string): ReactNode => {
    if (!['path', 'circle', 'ellipse', 'text', 'g'].includes(node.tag)) return null;
    const content = node.text ?? node.children?.map((child, index) => render(child, `${key}-${index}`));
    return createElement(node.tag, { key, ...(node.attrs ?? {}) }, content);
  };
  return <svg className={`research-type-icon research-type-icon-${type}`} viewBox={icon.view_box ?? '0 0 24 24'} aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    {icon.elements.map((node, index) => render(node, `${type}-${index}`))}
  </svg>;
}

function ResearchTypePicker({ value, onChange, fieldLabel = 'Research type' }: { value: ResearchMode; onChange: (value: ResearchMode) => void; fieldLabel?: string }) {
  const [open, setOpen] = useState(false);
  const [choices, setChoices] = useState(researchTypes);
  const [activeIndex, setActiveIndex] = useState(Math.max(0, researchTypes.findIndex(type => type.value === value)));
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const options = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedIndex = choices.findIndex(type => type.value === value);
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => {
      void fetch('/api/project-types', { cache: 'no-store', signal: controller.signal }).then(response => response.ok ? response.json() : Promise.reject()).then((data: { project_types: ProjectTypeRecord[] }) => {
        projectTypeCache = data.project_types;
        const next = data.project_types.map(item => ({ value: item.id, label: item.name })).sort((a, b) => a.label.localeCompare(b.label));
        setChoices(next);
      }).catch(() => undefined);
    };
    window.addEventListener('sigma-project-types-updated', refresh);
    refresh();
    return () => { controller.abort(); window.removeEventListener('sigma-project-types-updated', refresh); };
  }, []);
  useEffect(() => {
    const selected = choices.findIndex(item => item.value === value);
    if (selected >= 0) setActiveIndex(selected);
  }, [choices, value]);
  useEffect(() => {
    if (open) options.current[activeIndex]?.focus();
  }, [activeIndex, open]);
  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, [open]);
  function choose(next: ResearchMode) {
    onChange(next);
    setOpen(false);
    requestAnimationFrame(() => trigger.current?.focus());
  }
  function move(index: number) {
    if (!choices.length) return;
    setActiveIndex((index + choices.length) % choices.length);
  }
  const selected = choices[selectedIndex];
  const menu = useRef<HTMLDivElement>(null);
  const [menuStyle,setMenuStyle] = useState({top:-10000,left:-10000,width:0,maxHeight:256});
  useLayoutEffect(() => {
    if(!open||!menu.current) return;
    const panel=menu.current;
    panel.showPopover();
    const place=() => {
      const rect=trigger.current?.getBoundingClientRect();
      if(!rect) return;
      const below=window.innerHeight-rect.bottom-12,above=rect.top-12;
      const height=Math.min(256,Math.max(80,Math.max(below,above)));
      const top=below<180&&above>below?Math.max(8,rect.top-height-4):rect.bottom+4;
      setMenuStyle({top,left:Math.max(8,Math.min(rect.left,window.innerWidth-rect.width-8)),width:rect.width,maxHeight:height});
    };
    place();
    window.addEventListener('resize',place);
    window.addEventListener('scroll',place,true);
    return () => {
      window.removeEventListener('resize',place);
      window.removeEventListener('scroll',place,true);
      if(panel.matches(':popover-open')) panel.hidePopover();
    };
  },[open]);
  return <div className="research-type-picker" ref={root}>
    <button ref={trigger} id="project-mode" type="button" role="combobox" aria-labelledby="project-mode-label project-mode-value" aria-haspopup="listbox" aria-expanded={open} aria-controls="project-mode-options" data-tooltip-disabled="true" onClick={() => { setActiveIndex(Math.max(0, selectedIndex)); setOpen(current => !current); }} onKeyDown={event => {
      if (event.key === 'ArrowDown') { event.preventDefault(); setActiveIndex(Math.max(0, selectedIndex)); setOpen(true); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); setActiveIndex(choices.length - 1); setOpen(true); }
    }}>
      {selected && <ResearchTypeIcon type={selected.value}/>}<span id="project-mode-value">{selected?.label ?? (value ? `Project type no longer available · ${value}` : 'Choose a project type')}</span><svg className="research-type-chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="m2 4 4 4 4-4"/></svg>
    </button>
    {open && <div ref={menu} popover="manual" style={menuStyle} className="research-type-options" id="project-mode-options" role="listbox" aria-label={fieldLabel}>
      {choices.map((type, index) => <button ref={element => { options.current[index] = element; }} id={`project-mode-option-${type.value}`} key={type.value} type="button" role="option" aria-selected={value === type.value} tabIndex={activeIndex === index ? 0 : -1} onFocus={() => setActiveIndex(index)} onClick={() => choose(type.value)} onKeyDown={event => {
        if (event.key === 'ArrowDown') { event.preventDefault(); move(index + 1); }
        else if (event.key === 'ArrowUp') { event.preventDefault(); move(index - 1); }
        else if (event.key === 'Home') { event.preventDefault(); move(0); }
        else if (event.key === 'End') { event.preventDefault(); move(choices.length - 1); }
        else if (event.key === 'Escape') { event.preventDefault(); setOpen(false); trigger.current?.focus(); }
        else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(type.value); }
      }}><ResearchTypeIcon type={type.value}/><span>{type.label}</span></button>)}
    </div>}
  </div>;
}

function SigmaChoicePicker({ id, label, value, choices, onChange, disabled = false }: {
  id: string;
  label: string;
  value: string;
  choices: { value: string; label: string }[];
  onChange: (next: string) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const options = useRef<Array<HTMLButtonElement | null>>([]);
  const [menuStyle, setMenuStyle] = useState({ top: -10000, left: -10000, width: 0, maxHeight: 220 });
  const current = Math.max(0, choices.findIndex(item => item.value === value));
  useEffect(() => { if (open) options.current[active]?.focus(); }, [open, active]);
  useEffect(() => {
    if (!open || !disabled) return;
    setOpen(false);
  }, [disabled, open]);
  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node) && !menu.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, [open]);
  useLayoutEffect(() => {
    if (!open || !menu.current) return;
    const panel = menu.current;
    panel.showPopover();
    const place = () => {
      const rect = trigger.current?.getBoundingClientRect();
      if (!rect) return;
      const below = window.innerHeight - rect.bottom - 12;
      const above = rect.top - 12;
      const height = Math.min(220, Math.max(80, Math.max(below, above)));
      const menuHeight = Math.min(height, choices.length * 34 + 10);
      setMenuStyle({
        top: below < 130 && above > below ? Math.max(8, rect.top - menuHeight - 4) : rect.bottom + 4,
        left: Math.max(8, Math.min(rect.left, window.innerWidth - rect.width - 8)),
        width: rect.width, maxHeight: height,
      });
    };
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
      if (panel.matches(':popover-open')) panel.hidePopover();
    };
  }, [open, choices.length]);
  function choose(next: string) {
    onChange(next);
    setOpen(false);
    requestAnimationFrame(() => trigger.current?.focus());
  }
  return <div className="research-type-picker sigma-choice-picker" ref={root}>
    <button ref={trigger} id={id} type="button" role="combobox"
      aria-label={label} aria-haspopup="listbox" aria-expanded={open}
      aria-controls={`${id}-options`} disabled={disabled}
      onClick={() => { setActive(current); setOpen(previous => !previous); }}
      onKeyDown={event => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          setActive(event.key === 'ArrowDown' ? current : choices.length - 1);
          setOpen(true);
        }
      }}>
      <span>{choices[current]?.value === value ? choices[current].label : value}</span>
      <svg className="research-type-chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="m2 4 4 4 4-4"/></svg>
    </button>
    {open && <div ref={menu} popover="manual" style={menuStyle}
      className="research-type-options" id={`${id}-options`}
      role="listbox" aria-label={label}>
      {choices.map((item, index) => <button key={item.value}
        ref={element => { options.current[index] = element; }}
        type="button" role="option" aria-selected={item.value === value}
        tabIndex={active === index ? 0 : -1}
        onFocus={() => setActive(index)}
        onClick={() => choose(item.value)}
        onKeyDown={event => {
          if (event.key === 'ArrowDown') { event.preventDefault(); setActive((index + 1) % choices.length); }
          else if (event.key === 'ArrowUp') { event.preventDefault(); setActive((index - 1 + choices.length) % choices.length); }
          else if (event.key === 'Home') { event.preventDefault(); setActive(0); }
          else if (event.key === 'End') { event.preventDefault(); setActive(choices.length - 1); }
          else if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); setOpen(false); trigger.current?.focus(); }
          else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(item.value); }
        }}><span>{item.label}</span></button>)}
    </div>}
  </div>;
}

function DifficultyPicker({ value, onChange }: {
  value: ProjectDifficulty | null;
  onChange: (next: ProjectDifficulty | null) => void;
}) {
  const choices: { value: ProjectDifficulty | null; label: string }[] = [
    ...(value === null ? [{ value: null, label: 'Not set' }] : []),
    { value: 'easy', label: 'Easy' },
    { value: 'medium', label: 'Medium' },
    { value: 'hard', label: 'Hard' },
  ];
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const options = useRef<Array<HTMLButtonElement | null>>([]);
  const [menuStyle, setMenuStyle] = useState({ top: -10000, left: -10000, width: 0, maxHeight: 180 });
  const current = Math.max(0, choices.findIndex(item => item.value === value));
  useEffect(() => { if (open) options.current[active]?.focus(); }, [open, active]);
  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node) && !menu.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, [open]);
  useLayoutEffect(() => {
    if (!open || !menu.current) return;
    const panel = menu.current;
    panel.showPopover();
    const place = () => {
      const rect = trigger.current?.getBoundingClientRect();
      if (!rect) return;
      const below = window.innerHeight - rect.bottom - 12;
      const above = rect.top - 12;
      const height = Math.min(180, Math.max(80, Math.max(below, above)));
      const menuHeight = Math.min(height, choices.length * 34 + 10);
      setMenuStyle({
        top: below < 130 && above > below ? Math.max(8, rect.top - menuHeight - 4) : rect.bottom + 4,
        left: Math.max(8, Math.min(rect.left, window.innerWidth - rect.width - 8)),
        width: rect.width, maxHeight: height,
      });
    };
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
      if (panel.matches(':popover-open')) panel.hidePopover();
    };
  }, [open]);
  function choose(next: ProjectDifficulty | null) {
    onChange(next);
    setOpen(false);
    requestAnimationFrame(() => trigger.current?.focus());
  }
  return <div className="research-type-picker sigma-difficulty-picker" ref={root}>
    <button ref={trigger} id="sigma-project-difficulty" type="button" role="combobox"
      aria-label="Difficulty" aria-haspopup="listbox" aria-expanded={open}
      aria-controls="sigma-project-difficulty-options" data-tooltip-disabled="true"
      onClick={() => { setActive(current); setOpen(previous => !previous); }}
      onKeyDown={event => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          setActive(event.key === 'ArrowDown' ? current : choices.length - 1);
          setOpen(true);
        }
      }}>
      <span>{value ? difficultyLabels[value] : 'Not set'}</span>
      <svg className="research-type-chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="m2 4 4 4 4-4"/></svg>
    </button>
    {open && <div ref={menu} popover="manual" style={menuStyle}
      className="research-type-options" id="sigma-project-difficulty-options"
      role="listbox" aria-label="Difficulty">
      {choices.map((item, index) => <button key={item.value ?? 'unset'}
        ref={element => { options.current[index] = element; }}
        type="button" role="option" aria-selected={item.value === value}
        tabIndex={active === index ? 0 : -1}
        onFocus={() => setActive(index)}
        onClick={() => choose(item.value)}
        onKeyDown={event => {
          if (event.key === 'ArrowDown') { event.preventDefault(); setActive((index + 1) % choices.length); }
          else if (event.key === 'ArrowUp') { event.preventDefault(); setActive((index - 1 + choices.length) % choices.length); }
          else if (event.key === 'Home') { event.preventDefault(); setActive(0); }
          else if (event.key === 'End') { event.preventDefault(); setActive(choices.length - 1); }
          else if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); setOpen(false); trigger.current?.focus(); }
          else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(item.value); }
        }}><span>{item.label}</span></button>)}
    </div>}
  </div>;
}

type SharedProjectInfo = {
  artifact_authors?: Partial<Record<'strategy' | 'session' | 'paper' | 'paper_draft' | 'answer', Record<string, string>>>;
  owner: string | null;
  you?: string;
  collaborators: string[];
  removable_collaborators?: string[];
  revision: number;
  model: string;
  thinking: string;
  shared: boolean;
  failed_notifications: number;
  lease: { email: string; activity: string; expires_at: number } | null;
};

function plausibleCollaboratorEmail(input: string): string | null {
  const email = input.trim().toLowerCase();
  const match = /^([a-z0-9][a-z0-9._+%-]{0,63})@([a-z0-9][a-z0-9.-]*\.[a-z]{2,})$/.exec(email);
  if (!match || email.length > 254 || match[1].includes('..') || match[1].endsWith('.') || match[2].includes('..')) return null;
  if (match[2].split('.').some(part => !part || part.length > 63 || part.startsWith('-') || part.endsWith('-'))) return null;
  return email;
}

function ProjectClassificationDialog({ initial, collaborationRevision, onSaved, onCancel }: {
  initial: ProjectView; collaborationRevision?: number; onSaved: (next: ProjectView) => void; onCancel: () => void;
}) {
  useDocumentScrollLock();
  const dialog = useRef<HTMLDialogElement>(null);
  const cloudIdentity = useCloudIdentity();
  const [baseline, setBaseline] = useState(initial);
  const [projectType, setProjectType] = useState<ResearchMode>(initial.project.investigation_type);
  const [difficulty, setDifficulty] = useState<ProjectDifficulty | null>(initial.project.difficulty);
  // State initializers must be pure: StrictMode may invoke them twice.
  const [initialGroupSettings] = useState<SharedProjectInfo | null>(
    () => preloadedGroupSettings.get(initial.path) ?? null,
  );
  useEffect(() => {
    if (initialGroupSettings) preloadedGroupSettings.delete(initial.path);
  }, [initialGroupSettings, initial.path]);
  const [shared, setShared] = useState<SharedProjectInfo | null>(initialGroupSettings);
  const [collaborators, setCollaborators] = useState<string[]>(() => initialGroupSettings?.collaborators ?? []);
  const [adding, setAdding] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [retryingEmails, setRetryingEmails] = useState(false);
  const [loading, setLoading] = useState(!initialGroupSettings);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { dialog.current?.showModal(); }, []);
  // Keep an already-open Settings dialog synchronized with committed remote edits.
  // Never dismiss it or leave read-only classification values stale.
  useEffect(() => {
    setBaseline(initial);
    setProjectType(initial.project.investigation_type);
    setDifficulty(initial.project.difficulty);
    setError('');
  }, [initial]);
  useEffect(() => {
    // Home already supplied a valid collaboration snapshot. Do not initiate
    // another request just because the dialog mounted. A later revision
    // change still triggers the ordinary refresh path.
    if (initialGroupSettings && (collaborationRevision === undefined
      || collaborationRevision === initialGroupSettings.revision)) return;
    const controller = new AbortController();
    const json = async (url: string) => {
      const response = await fetch(url, { signal: controller.signal, headers: { 'X-Sigma-Error-Handled': 'true' } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? 'Project settings are unavailable.');
      return data;
    };
    // An unavailable collaboration endpoint must never trap the Settings
    // modal in Loading or disable its close button indefinitely.
    const timeout = window.setTimeout(() => {
      if (controller.signal.aborted) return;
      controller.abort();
      setError('Shared project settings could not be loaded.');
      setLoading(false);
    }, 8000);
    void json(`/api/projects/collaboration?${new URLSearchParams({ path: initial.path, include_authors: 'false' })}`)
      .then((saved: SharedProjectInfo) => {
        if (controller.signal.aborted) return;
        setShared(saved);
        setCollaborators(saved.collaborators);
        setLoading(false);
      }).catch(cause => {
        if (!controller.signal.aborted) { setError(errorMessage(cause)); setLoading(false); }
      }).finally(() => window.clearTimeout(timeout));
    return () => { window.clearTimeout(timeout); controller.abort(); };
  }, [initial.path, collaborationRevision]);
  const nonOwnerCollaborator = !!shared?.owner && shared.owner !== shared.you;
  const canEditClassification = !!shared && !nonOwnerCollaborator;
  const changed = (canEditClassification && (
    projectType !== baseline.project.investigation_type || difficulty !== baseline.project.difficulty
  )) || (!!shared?.owner && JSON.stringify(collaborators) !== JSON.stringify(shared.collaborators));
  function finishCollaboratorEntry(value: string) {
    if (!value.trim()) { setAdding(false); setNewEmail(''); setError(''); return; }
    const email = plausibleCollaboratorEmail(value);
    if (!email) { setError('Enter a Google account email address.'); return; }
    if (email === shared?.owner || collaborators.includes(email)) {
      setError('This account is already a collaborator.'); return;
    }
    setCollaborators(previous => [...previous, email].sort());
    setNewEmail(''); setAdding(false); setError('');
  }
  async function retryEmails() {
    if (retryingEmails || !shared?.owner) return;
    setRetryingEmails(true); setError('');
    try {
      await post('collaboration/notifications/retry', { path: initial.path }, undefined, true);
      setShared(previous => previous ? { ...previous, failed_notifications: 0 } : previous);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setRetryingEmails(false); }
  }
  async function save(): Promise<boolean> {
    if (busy || loading || !changed || !shared) return false;
    setBusy(true); setError('');
    try {
      const previous = settingsOf(baseline);
      const next = await post<ProjectView>('update', {
        path: initial.path, ...previous,
        investigation_type: canEditClassification ? projectType : baseline.project.investigation_type,
        difficulty: canEditClassification ? difficulty : baseline.project.difficulty,
        ai_model: baseline.project.ai_model, reasoning_effort: baseline.project.reasoning_effort,
        expected: previous,
        ...(shared.owner ? { expected_revision: shared.revision, collaborators } : {}),
      });
      const selfEmail = cloudIdentity?.user?.email?.toLowerCase();
      if (selfEmail && shared.collaborators.includes(selfEmail) && !collaborators.includes(selfEmail)) {
        // The saved change revoked our own membership; do not request inaccessible project state.
        window.location.assign('/');
        return true;
      }
      if (shared.owner) {
        const response = await fetch(`/api/projects/collaboration?${new URLSearchParams({ path: initial.path, verify_revision: 'true' })}`, {
          headers: { 'X-Sigma-Error-Handled': 'true' }, cache: 'no-store',
        });
        if (!response.ok) throw new Error('Project updated, but collaboration status could not be refreshed.');
        setShared(await response.json() as SharedProjectInfo);
      }
      setBaseline(next);
      onSaved(next);
      return true;
    } catch (cause) { setError(errorMessage(cause)); return false; }
    finally { setBusy(false); }
  }
  useEffect(() => {
    if (loading || busy || !changed || !shared || error) return;
    const timer = window.setTimeout(() => { void save(); }, 350);
    return () => window.clearTimeout(timer);
  }, [loading, busy, changed, shared, projectType, difficulty, collaborators, error]);
  async function close() {
    if (busy) return;
    if (loading) { onCancel(); return; }
    if (changed) {
      if (!await save()) return;
    }
    onCancel();
  }
  return <dialog ref={dialog} className="project-settings-dialog sigma-project-classification-dialog"
    aria-labelledby="sigma-project-classification-title"
    onCancel={event => { event.preventDefault(); void close(); }}>
    <form onSubmit={event => event.preventDefault()}>
      <header className="settings-header">
        <h2 id="sigma-project-classification-title">Project Settings</h2>
        <div className="settings-actions">
          <DialogDismissButton label="Close Project Settings" disabled={busy} onClick={() => void close()}/>
        </div>
      </header>
      <div className="settings-body">
        <fieldset disabled={busy || loading} className="project-settings-editable-fields">
          <div className="settings-classification-row">
            <div>
              <label id="project-mode-label">Research category</label>
              {canEditClassification
                ? <ResearchTypePicker fieldLabel="Research category" value={projectType} onChange={setProjectType}/>
                : <div className="research-type-picker"><div className="sigma-classification-readonly" aria-labelledby="project-mode-label">
                    <ResearchTypeIcon type={projectType} snapshot={initial.project.project_type_snapshot}/>
                    <span>{initial.project.project_type_snapshot?.id === projectType
                      ? initial.project.project_type_snapshot.name : researchTypeLabel(projectType)}</span>
                  </div></div>}
            </div>
            <div>
              <label id="sigma-project-difficulty-label">Difficulty</label>
              {canEditClassification
                ? <DifficultyPicker value={difficulty} onChange={setDifficulty}/>
                : <div className="research-type-picker sigma-difficulty-picker">
                    <div className="sigma-classification-readonly" aria-labelledby="sigma-project-difficulty-label">
                      <span>{difficultyLabel(difficulty)}</span>
                    </div>
                  </div>}
            </div>
          </div>
          {nonOwnerCollaborator && <p className="project-classification-readonly-note">
            Title, research category, difficulty, and user settings are inherited from the project owner.
          </p>}
          {!!shared?.owner && <>
            <section className="project-collaborators" aria-label="Collaborators">
              <div className="project-collaborators-heading">
                <h3>Collaborators</h3>
                <button type="button" className="text-view-link sigma-heading-icon-action" aria-label="Add collaborator" data-tooltip="Add collaborator" onClick={() => { setAdding(true); setError(''); }}><CirclePlusIcon/></button>
              </div>
              <div className="project-collaborator-row">
                <span>{shared.owner}</span><span className="project-collaborator-owner">Owner</span>
              </div>
              {collaborators.length > 0 && <p className="project-collaborator-standards-note">Title, research category, difficulty, and user settings are inherited from the project owner.</p>}
              {collaborators.map(email => <div className="project-collaborator-row" key={email}>
                <span>{email}</span>
                {(!shared.collaborators.includes(email) || shared.removable_collaborators?.includes(email)) && <button type="button" aria-label={`Remove ${email}`} data-tooltip="Remove collaborator" className="project-collaborator-remove text-view-icon workspace-icon-button" onClick={() => setCollaborators(previous => previous.filter(value => value !== email))}>
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" aria-hidden="true"><path d="M8 8 16 16M16 8 8 16"/></svg>
                </button>}
              </div>)}
              {adding && <div className="project-collaborator-add">
                <input type="email" autoFocus value={newEmail} placeholder="Google account email" aria-label="New collaborator email" onChange={event => { setNewEmail(event.target.value); if (error) setError(''); }}
                  onBlur={event => finishCollaboratorEntry(event.currentTarget.value)}
                  onKeyDown={event => {
                    if (event.key === 'Enter') { event.preventDefault(); event.currentTarget.blur(); }
                    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); setAdding(false); setNewEmail(''); setError(''); }
                  }}/>
              </div>}
              {shared.failed_notifications > 0 && <p className="project-collaborator-mail-failed" role="status">
                {shared.failed_notifications} collaboration {shared.failed_notifications === 1 ? 'email could' : 'emails could'} not be delivered.
                <button type="button" disabled={retryingEmails} onClick={() => void retryEmails()}>{retryingEmails ? 'Retrying…' : 'Retry emails'}</button>
              </p>}
            </section>
          </>}
          {shared && !shared.owner && <p className="project-collaborator-local-note">
            Collaboration requires individual Google sign-ins, locally or hosted.
            Sign in with an authorized account to share this project.
          </p>}
        </fieldset>
        {loading && <p className="settings-hint">Loading shared settings…</p>}
        {error && <p role="alert" className="error">{error}</p>}
      </div>
    </form>
  </dialog>;
}

function ProjectSettingsDialog({ initial, onSaved, onCancel }: { initial?: ProjectView; onSaved: (view: ProjectView) => void; onCancel: () => void }) {
  useDocumentScrollLock();
  const cloud = useCloudIdentity();
  const dialog = useRef<HTMLDialogElement>(null);
  const first = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const [userUnattended, setUserUnattended] = useState(false);
  const [savedUserUnattended, setSavedUserUnattended] = useState(false);
  const [userPreferenceLoaded, setUserPreferenceLoaded] = useState(false);
  const [progressEmail, setProgressEmail] = useState(false);
  const [savedProgressEmail, setSavedProgressEmail] = useState(false);
  const [progressEmailAvailable, setProgressEmailAvailable] = useState(false);
  const [progressEmailLoaded, setProgressEmailLoaded] = useState(false);
  const [exclusiveSections, setExclusiveSections] = useState(false);
  const [savedExclusiveSections, setSavedExclusiveSections] = useState(false);
  const [exclusiveSectionsLoaded, setExclusiveSectionsLoaded] = useState(false);
  const [sectionLayoutWarning, setSectionLayoutWarning] = useState('');
  const [values, setValues] = useState<Settings>(() => initial ? settingsOf(initial) : { title: '', problem: '', desired_outcomes: '', paper_requirements: '', investigation_type: '', ai_model: '', reasoning_effort: 'high', difficulty: 'medium', show_advanced_outcome_details: false });
  const [destination, setDestination] = useState<Destination | null>(null);
  const [locationError, setLocationError] = useState('');
  const [previewBusy, setPreviewBusy] = useState(!initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<ProjectSettingsTab>(savedProjectSettingsTab);
  function changeSettingsTab(tab: ProjectSettingsTab) {
    setActiveTab(tab);
    try { window.localStorage.setItem('sigma.projectSettingsTab', tab); } catch { /* Keep this dialog usable when storage is unavailable. */ }
  }
  const [limitDraft, setLimitDraft] = useState<ResearchLimitsDraft>(() => draftLimits({ research_rounds: 3, turns_per_round: 3, scheduler_version: 2, model_calls: 18, session_duration_minutes: 60, output_tokens_per_call: 4000, maximum_estimated_cost_usd: null, maximum_input_tokens_per_session: null, max_concurrent_sessions: '1' }));
  const [limitsLoaded, setLimitsLoaded] = useState(!initial);
  const [loadedLimitDraft, setLoadedLimitDraft] = useState<ResearchLimitsDraft | null>(null);
  const limitValidation = validateLimitDraft(
    limitDraft,
  );
  const researchRounds = Number(limitDraft.research_rounds) || 0;
  const turnsPerRound = Number(limitDraft.turns_per_round) || 0;
  const callsPerStrategy = researchRounds * turnsPerRound * 2;
  const enabledStrategyCount = initial?.project.strategies.filter(strategy => strategy.enabled && !strategy.removed_at).length ?? 0;
  useEffect(() => { dialog.current?.showModal(); first.current?.focus(); }, []);
  useEffect(() => {
    if (!initial) return;
    const controller = new AbortController();
    fetch("/api/user-preferences/unattended-execution", { signal: controller.signal })
      .then(async response => {
        const data = await response.json();
        if (!response.ok || typeof data.allow_unattended_background_execution !== "boolean")
          throw new Error("User background execution preference could not be loaded.");
        if (!controller.signal.aborted) {
          setUserUnattended(data.allow_unattended_background_execution);
          setSavedUserUnattended(data.allow_unattended_background_execution);
          setUserPreferenceLoaded(true);
        }
      }).catch(cause => { if (!controller.signal.aborted) setError(errorMessage(cause)); });
    return () => controller.abort();
  }, [initial?.path]);
  useEffect(() => {
    if (!initial) return;
    const controller = new AbortController();
    fetch("/api/user-preferences/progress-email", {
      signal: controller.signal, headers: { 'X-Sigma-Error-Handled': 'true' },
    }).then(async response => {
      const data = await response.json();
      if (!response.ok || typeof data.enabled !== 'boolean' || typeof data.available !== 'boolean')
        throw new Error('Progress email preference could not be loaded.');
      if (controller.signal.aborted) return;
      setProgressEmail(data.enabled);
      setSavedProgressEmail(data.enabled);
      setProgressEmailAvailable(data.available);
      setProgressEmailLoaded(true);
    }).catch(() => {
      if (!controller.signal.aborted) { setProgressEmailAvailable(false); setProgressEmailLoaded(true); }
    });
    return () => controller.abort();
  }, [initial?.path]);
  useEffect(() => {
    if (!initial) return;
    const controller = new AbortController();
    fetch("/api/user-preferences/section-layout", { signal: controller.signal, headers: { 'X-Sigma-Error-Handled': 'true' } })
      .then(async response => {
        const data = await response.json();
        if (!response.ok || typeof data.expand_one_project_section_at_a_time !== 'boolean')
          throw new Error("Section expansion preference could not be loaded.");
        if (!controller.signal.aborted) {
          setExclusiveSections(data.expand_one_project_section_at_a_time);
          setSavedExclusiveSections(data.expand_one_project_section_at_a_time);
          setExclusiveSectionsLoaded(true);
          setSectionLayoutWarning('');
        }
      }).catch(() => {
        if (!controller.signal.aborted) {
          setExclusiveSectionsLoaded(true);
          setSectionLayoutWarning('Section layout preference unavailable. You may still change it and retry saving.');
        }
      });
    return () => controller.abort();
  }, [initial?.path]);
  useEffect(() => {
    if (!initial) return;
    const controller = new AbortController();
    fetch(`/api/projects/research-limits?${new URLSearchParams({ path: initial.path })}`, { signal: controller.signal }).then(async response => {
      const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Research limits could not be read');
      const loaded = draftLimits(data); setLimitDraft(loaded); setLoadedLimitDraft(loaded); setLimitsLoaded(true);
    }).catch(cause => { if (!controller.signal.aborted) setError(errorMessage(cause)); });
    return () => controller.abort();
  }, [initial?.path]);
  useEffect(() => {
    if (initial) return;
    const controller = new AbortController(); setPreviewBusy(true); setDestination(null); setLocationError('');
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/projects/destination?${new URLSearchParams({ title: values.title })}`, { signal: controller.signal });
        const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Project location unavailable');
        setDestination(data);
      } catch (error) { if (!controller.signal.aborted) setLocationError(errorMessage(error)); }
      finally { if (!controller.signal.aborted) setPreviewBusy(false); }
    }, values.title ? 180 : 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [values.title]);
  function change<K extends keyof Settings,>(key: K, value: Settings[K]) { setValues(previous => ({ ...previous, [key]: value })); }
  const canCreate = !!values.title.trim() && !!values.problem.trim() && !!values.investigation_type.trim();
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current || (initial && !limitValidation.value) || (!initial && !canCreate)) return;
    submitting.current = true; setBusy(true); setError('');
    try {
      const createValues = {
        title: values.title,
        problem: values.problem.trim(),
        desired_outcomes: values.desired_outcomes,
        paper_requirements: values.paper_requirements,
        investigation_type: values.investigation_type,
        ai_model: values.ai_model,
        reasoning_effort: values.reasoning_effort,
        difficulty: values.difficulty,
        show_advanced_outcome_details: values.show_advanced_outcome_details,
      };
      const next = await post<ProjectView>(initial ? 'update' : 'create', initial ? { path: initial.path, ...values, expected: settingsOf(initial) } : createValues);
      // Unrelated settings changes must not rewrite historical v1 research limits.
      if (initial && loadedLimitDraft && JSON.stringify(limitDraft) !== JSON.stringify(loadedLimitDraft)) {
        const response = await fetch('/api/projects/research-limits', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: initial.path, ...limitValidation.value }) });
        const result = await response.json(); if (!response.ok) throw new Error(result.error ?? 'Research limits were not saved');
        const saved = draftLimits(result); setLimitDraft(saved); setLoadedLimitDraft(saved);
      }
      if (initial && userPreferenceLoaded && userUnattended !== savedUserUnattended) {
        const response = await fetch("/api/user-preferences/unattended-execution", {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ allow_unattended_background_execution: userUnattended }),
        });
        const data = await response.json();
        if (!response.ok || data.allow_unattended_background_execution !== userUnattended)
          throw new Error(data.error ?? "User background execution preference was not saved.");
        setSavedUserUnattended(userUnattended);
      }
      if (initial && progressEmailLoaded && (progressEmailAvailable || !progressEmail) && progressEmail !== savedProgressEmail) {
        const response = await fetch('/api/user-preferences/progress-email', {
          method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
          body: JSON.stringify({ enabled: progressEmail }),
        });
        const data = await response.json();
        if (!response.ok || data.enabled !== progressEmail)
          throw new Error(data.detail ?? data.error ?? 'Progress email preference was not saved.');
        setSavedProgressEmail(progressEmail);
      }
      if (initial && exclusiveSectionsLoaded && exclusiveSections !== savedExclusiveSections) {
        const response = await fetch("/api/user-preferences/section-layout", {
          method: "PUT", headers: { "Content-Type": "application/json", "X-Sigma-Error-Handled": "true" },
          body: JSON.stringify({ expand_one_project_section_at_a_time: exclusiveSections }),
        });
        const data = await response.json();
        if (!response.ok || data.expand_one_project_section_at_a_time !== exclusiveSections)
          throw new Error(data.error ?? "Section expansion preference was not saved.");
        setSavedExclusiveSections(exclusiveSections);
        window.dispatchEvent(new CustomEvent("sigma-section-layout-preference-changed", { detail: exclusiveSections }));
      }
      onSaved(next);
    }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className={`project-settings-dialog ${initial ? 'edit-project-dialog' : 'new-project-dialog'}`} aria-labelledby="project-settings-heading" aria-describedby={initial ? "project-settings-help" : undefined} onCancel={event => { event.preventDefault(); if (!submitting.current) onCancel(); }}>
    <form onSubmit={save}>
      <header className="settings-header"><h2 id="project-settings-heading">{initial ? 'Project Settings' : 'New Project'}</h2><div className="settings-actions">{initial ? <><button type="submit" disabled={busy || !limitsLoaded || !limitValidation.value}>{busy ? 'Saving…' : 'Save'}</button><DialogDismissButton label="Cancel project settings" disabled={busy} onClick={() => { if (!submitting.current) onCancel(); }}/></> : <><button type="submit" disabled={busy || !canCreate}>{busy ? 'Creating…' : 'Create'}</button><DialogDismissButton label="Cancel project settings" disabled={busy} onClick={() => { if (!submitting.current) onCancel(); }}/></>}</div></header>
      {!initial && <p className="settings-hint new-project-edit-note">Project name, Research category, and Research Subject are required. These can be edited later.</p>}
      {initial && <p className="settings-hint" id="project-settings-scope">Most changes take effect when a new research session starts. Existing sessions keep their research configuration; some limits can be adjusted when resuming.</p>}
      {initial && <div role="tablist" aria-label="Project settings" className="settings-tabs" onKeyDown={event => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) { event.preventDefault(); const tabs = ['main', 'limits', 'preferences'] as const; const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs[2] : tabs[(tabs.indexOf(activeTab) + (event.key === 'ArrowRight' ? 1 : 2)) % 3]; changeSettingsTab(next); dialog.current?.querySelector<HTMLButtonElement>(`[data-settings-tab="${next}"]`)?.focus(); } }}>
        <button type="button" role="tab" data-settings-tab="main" id="settings-tab-main" aria-selected={activeTab === 'main'} aria-controls="settings-panel-main" tabIndex={activeTab === 'main' ? 0 : -1} onClick={() => changeSettingsTab('main')}>Research</button>
        <button type="button" role="tab" data-settings-tab="limits" id="settings-tab-limits" aria-selected={activeTab === 'limits'} aria-controls="settings-panel-limits" tabIndex={activeTab === 'limits' ? 0 : -1} onClick={() => changeSettingsTab('limits')}>Limits</button>
        <button type="button" role="tab" data-settings-tab="preferences" id="settings-tab-preferences" aria-selected={activeTab === 'preferences'} aria-controls="settings-panel-preferences" tabIndex={activeTab === 'preferences' ? 0 : -1} onClick={() => changeSettingsTab('preferences')}>Preferences</button>
      </div>}
      <div className="settings-body" id={initial ? 'settings-panel-main' : undefined} role={initial ? 'tabpanel' : undefined} aria-labelledby={initial ? 'settings-tab-main' : undefined} hidden={!!initial && activeTab !== 'main'}>{initial && <p id="project-settings-help">Set this project’s research type and difficulty.</p>}
      <fieldset disabled={busy}>
      {!initial && <>
      <div className="new-project-field"><label htmlFor="project-name">Project name</label><input ref={first} id="project-name" required maxLength={200} value={values.title} onChange={event => change('title', event.target.value)}/></div>
      <div className="settings-classification-row"><div><label id="project-mode-label">Research category</label><ResearchTypePicker fieldLabel="Research category" value={values.investigation_type} onChange={value => change('investigation_type', value)}/></div>
      <div><label id="sigma-project-difficulty-label">Difficulty</label><DifficultyPicker value={values.difficulty} onChange={value => change('difficulty', value)}/></div></div>
      <div className="new-project-field"><label htmlFor="project-problem">Research Subject</label><p className="settings-hint">What are we investigating?</p><textarea id="project-problem" required maxLength={20000} rows={3} value={values.problem} onChange={event => change('problem', event.target.value)}/></div>
      <div className="new-project-field"><label htmlFor="project-desired-outcomes">Desired Outcomes</label><p className="settings-hint">What insights or advances are we hoping for?</p><textarea id="project-desired-outcomes" maxLength={20000} rows={4} value={values.desired_outcomes} onChange={event => change('desired_outcomes', event.target.value)}/></div>
      <div className="new-project-field"><label htmlFor="project-paper-requirements">Paper Requirements</label><p className="settings-hint">What should the finished publication contain?</p><textarea id="project-paper-requirements" maxLength={20000} rows={4} value={values.paper_requirements} onChange={event => change('paper_requirements', event.target.value)}/></div></>}
      {initial && <div className="settings-classification-row"><div><label id="project-mode-label">Research type</label><ResearchTypePicker fieldLabel="Research type" value={values.investigation_type} onChange={value => change('investigation_type', value)}/></div>
      <div><label id="sigma-project-difficulty-label">Difficulty</label><DifficultyPicker value={values.difficulty} onChange={value => change('difficulty', value)}/></div></div>}
      {initial && <p className="project-destination"><span>Project location</span><code>{initial.path}</code><small>Editing the display name never renames or moves this directory.</small></p>}
      {locationError && <p className="error" role="alert">{locationError}</p>}
      {destination?.exists && <p className="error" role="alert">That name is already used by another project, or the location is occupied. Choose another name.</p>}
      {error && <p className="error" role="alert">{error}</p>}
    </fieldset></div>
    {initial && <section id="settings-panel-limits" className="settings-body research-limits-panel" role="tabpanel" aria-labelledby="settings-tab-limits" hidden={activeTab !== 'limits'}>
      <p>Research rounds, turns, and duration are set when a session starts. Some limits are rechecked on Resume; findings and accepted calls are preserved.</p>
      {cloud?.target === 'hosted' && <p className="settings-hint">Hosted sponsorship is governed by account allowance; the project duration applies.</p>}
      {cloud?.target === 'local' && <p className="settings-hint">Sponsored research uses the project duration and is governed by the account allowance.</p>}
      <fieldset disabled={busy || !limitsLoaded}>
        <label htmlFor="research-concurrent-sessions">Maximum concurrent sessions</label><input id="research-concurrent-sessions" type="number" min={1} max={4} step={1} value={limitDraft.max_concurrent_sessions} aria-invalid={!!limitValidation.errors.max_concurrent_sessions} aria-describedby="research-concurrent-sessions-help research-concurrent-sessions-error" onChange={event => setLimitDraft(value => ({ ...value, max_concurrent_sessions: event.target.value }))}/><p id="research-concurrent-sessions-help" className="settings-hint">Up to 4 simultaneously active research sessions in this project (1–4). Default is 1.</p>{limitValidation.errors.max_concurrent_sessions && <p id="research-concurrent-sessions-error" className="limit-error" role="alert">{limitValidation.errors.max_concurrent_sessions}</p>}
        <label htmlFor="research-rounds">Research rounds</label><input id="research-rounds" type="number" min={1} max={60} step={1} value={limitDraft.research_rounds} aria-invalid={!!limitValidation.errors.research_rounds} aria-describedby="research-rounds-help research-rounds-error" onChange={event => setLimitDraft(value => ({ ...value, research_rounds: event.target.value }))}/><p id="research-rounds-help" className="settings-hint">Number of rounds per strategy.</p>{limitValidation.errors.research_rounds && <p id="research-rounds-error" className="limit-error" role="alert">{limitValidation.errors.research_rounds}</p>}
        <label htmlFor="research-turns-per-round">Turns per round</label><input id="research-turns-per-round" type="number" min={1} max={20} step={1} value={limitDraft.turns_per_round} aria-invalid={!!limitValidation.errors.turns_per_round} aria-describedby="research-turns-per-round-help research-turns-per-round-error" onChange={event => setLimitDraft(value => ({ ...value, turns_per_round: event.target.value }))}/><p id="research-turns-per-round-help" className="settings-hint">Each turn includes one Investigator and one Skeptic.</p>{limitValidation.errors.turns_per_round && <p id="research-turns-per-round-error" className="limit-error" role="alert">{limitValidation.errors.turns_per_round}</p>}
        <div className="research-call-calculation" aria-live="polite">
          <p>Total agent calls per strategy: {researchRounds} × {turnsPerRound} × 2 = {callsPerStrategy}</p>
          <p>Total across enabled strategies: {callsPerStrategy} × {enabledStrategyCount} enabled {enabledStrategyCount === 1 ? 'strategy' : 'strategies'} = {callsPerStrategy * enabledStrategyCount} agent calls</p>
          <p className="settings-hint">Maximum possible calls; strategies may stop early.</p>
        </div>
        <label htmlFor="research-duration-value">Maximum session duration</label><div className="research-duration-controls"><input id="research-duration-value" type="number" min={1} max={limitDraft.session_duration_unit === 'unlimited' ? undefined : Math.floor(MAX_SESSION_DURATION_MINUTES / durationUnitMinutes[limitDraft.session_duration_unit])} step={1} readOnly={limitDraft.session_duration_unit === 'unlimited'} placeholder={limitDraft.session_duration_unit === 'unlimited' ? '' : undefined} value={limitDraft.session_duration_value} aria-invalid={!!limitValidation.errors.session_duration_value} aria-describedby="research-duration-help research-duration-error" onChange={event => setLimitDraft(value => ({ ...value, session_duration_value: event.target.value }))}/><select id="research-duration-unit" aria-label="Maximum session duration unit" value={limitDraft.session_duration_unit} onChange={event => { const unit = event.target.value as DurationUnit; setLimitDraft(value => ({ ...value, session_duration_unit: unit, session_duration_value: unit === 'unlimited' ? '' : (value.session_duration_unit === 'unlimited' ? '1' : value.session_duration_value) })); }}><option value="minutes">Minutes</option><option value="hours">Hours</option><option value="days">Days</option><option value="unlimited">Unlimited</option></select></div><p id="research-duration-help" className="settings-hint">1 minute to 7 days, or Unlimited. Unlimited removes the session wall-clock deadline; call, round, spend and per-call timeouts still apply.</p>{limitValidation.errors.session_duration_value && <p id="research-duration-error" className="limit-error" role="alert">{limitValidation.errors.session_duration_value}</p>}
        {/* Per-call output budget is an internal safeguard, not a user-facing research setting. */}
        <label htmlFor="research-input-tokens">Maximum input tokens per session</label><input id="research-input-tokens" type="number" min={4096} max={1000000} step={1} placeholder="Unlimited" value={limitDraft.maximum_input_tokens_per_session} aria-invalid={!!limitValidation.errors.maximum_input_tokens_per_session} aria-describedby="research-input-help research-input-error" onChange={event => setLimitDraft(value => ({ ...value, maximum_input_tokens_per_session: event.target.value }))}/><p id="research-input-help" className="settings-hint">Optional cumulative cap. Before dispatch, SIGMA reserves the exact serialized request byte count plus an 8,192-token structural allowance as an upper bound; afterward, reported input usage must fit within that reservation. Unknown or in-flight calls retain their full reservation.</p>{limitValidation.errors.maximum_input_tokens_per_session && <p id="research-input-error" className="limit-error" role="alert">{limitValidation.errors.maximum_input_tokens_per_session}</p>}
        <>
          <label htmlFor="research-cost-limit">Maximum estimated session cost (USD)</label>
          <input id="research-cost-limit" type="text" inputMode="decimal" placeholder="Unlimited" value={limitDraft.maximum_estimated_cost_usd} aria-invalid={!!limitValidation.errors.maximum_estimated_cost_usd} aria-describedby="research-cost-help research-cost-error" onChange={event => setLimitDraft(value => ({ ...value, maximum_estimated_cost_usd: event.target.value }))}/>
          <p id="research-cost-help" className="settings-hint">Optional per-session cap. Without one, sponsored sessions remain subject to ChatGPT and SIGMA allowance limits. Set $0.01 to $100.00, or leave blank for no session cap. Estimates use published prices and reported tokens.</p>
          {limitValidation.errors.maximum_estimated_cost_usd && <p id="research-cost-error" className="limit-error" role="alert">{limitValidation.errors.maximum_estimated_cost_usd}</p>}
        </>
      </fieldset>
      {!limitsLoaded && <p role="status">Loading research limits…</p>}{error && <p role="alert" className="error">{error} <button type="button" className="text-view-link" onClick={async () => { setError(''); try { const response = await fetch(`/api/projects/research-limits?${new URLSearchParams({ path: initial.path })}`); const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Research limits could not be read'); setLimitDraft(draftLimits(data)); setLimitsLoaded(true); } catch (cause) { setError(errorMessage(cause)); } }}>Retry</button></p>}
    </section>}
    {initial && <section id="settings-panel-preferences" className="settings-body project-preferences-panel" role="tabpanel" aria-labelledby="settings-tab-preferences" hidden={activeTab !== 'preferences'}>
      <p>Project presentation and user-wide research execution preferences.</p>
      <fieldset disabled={busy}>
        <label className="project-preference-checkbox" htmlFor="show-advanced-outcome-details"><input id="show-advanced-outcome-details" type="checkbox" checked={values.show_advanced_outcome_details} onChange={event => change('show_advanced_outcome_details', event.target.checked)}/>Show advanced Outcome details</label>
        <p className="settings-hint">When enabled, each recorded outcome opens with its conclusion and provides expandable reasoning, evidence, metrics and session details. When disabled, SIGMA shows a concise result with its qualifications.</p>
        <label className="project-preference-checkbox" htmlFor="expand-one-project-section"><input id="expand-one-project-section" type="checkbox" checked={exclusiveSections} disabled={!exclusiveSectionsLoaded} onChange={event => setExclusiveSections(event.target.checked)}/>Expand one project section at a time</label>
        <p className="settings-hint">User-wide display preference for the Project, Strategies, Sessions and Papers sections. Opening one collapses the others.</p>
        {sectionLayoutWarning && <p className="settings-hint" role="status">{sectionLayoutWarning}</p>}
        <label className="project-preference-checkbox" htmlFor="notify-progress-email"><input id="notify-progress-email" type="checkbox" checked={progressEmail} disabled={!progressEmailLoaded || (!progressEmailAvailable && !progressEmail)} onChange={event => setProgressEmail(event.target.checked)}/>Notify me by email on progress</label>
        <p id="notify-progress-email-help" className="settings-hint">Receive emails when research sessions or paper generation finish, fail, or pause unexpectedly. Applies to all your projects.</p>
        {progressEmailLoaded && !progressEmailAvailable && <p className="settings-hint" role="status">Google sign-in and configured email delivery are required to enable notifications.</p>}
        <label className="project-preference-checkbox" htmlFor="allow-unattended-background-execution"><input id="allow-unattended-background-execution" type="checkbox" checked={userUnattended} disabled={!userPreferenceLoaded} onChange={event => setUserUnattended(event.target.checked)}/>Allow unattended background execution</label>
        <p id="allow-unattended-background-execution-help" className="settings-hint">This user-wide setting applies across all your projects. When enabled, the backend can keep research and paper generation running after you close the browser page, potentially incurring AI-provider costs. When disabled, SIGMA stops new AI stages after the last viewer disconnects and preserves completed research or paper checkpoints for explicit continuation.</p>
      </fieldset>
      {error && <p role="alert" className="error">{error}</p>}
    </section>}
    </form>
  </dialog>;
}

type ActivityRunTarget = { kind: AttributionKind; status: 'active' | 'queued'; id?: string; number?: number; creator?: string | null; model?: string; thinking?: string };
type RecentProject = { id: string; path: string; title: string; investigation_type: string | null; project_type_snapshot?: ProjectTypeRecord | null; strategy_count: number | null; paper_count?: number | null; best_paper_score?: number | null; difficulty: ProjectDifficulty | null; research_running: boolean; paper_generating?: boolean; paper_activity?: string | null; available: boolean; pinned: boolean; shared?: boolean; collaborator?: boolean; activity_author?: string | null; answer_active?: boolean; activity_runs?: ActivityRunTarget[]; error: string | null };
// Saved groups by title without the terminal version; versions sort numerically descending.
// Most Recent intentionally keeps last-accessed ordering.
const savedVersionSuffix = /\s+(?:v(?:ersion)?\s*(\d+(?:\.\d+)*)|\(\s*v(?:ersion)?\s*(\d+(?:\.\d+)*)\s*\))$/i;
function recentProjectFamilyKey(project: RecentProject): string {
  return project.title.replace(savedVersionSuffix, '').trim().toLocaleLowerCase();
}
function compareSavedVersions(a: RecentProject, b: RecentProject): number {
  const family = recentProjectFamilyKey(a).localeCompare(recentProjectFamilyKey(b), undefined, { sensitivity: 'base' });
  if (family) return family;
  const numbers = (entry: RecentProject) => (entry.title.match(savedVersionSuffix)?.slice(1).find(Boolean) ?? '0').split('.').map(Number);
  const left = numbers(a), right = numbers(b);
  for (let i = 0; i < Math.max(left.length, right.length); i++) {
    const delta = (right[i] ?? 0) - (left[i] ?? 0);
    if (delta) return delta;
  }
  return a.title.localeCompare(b.title, undefined, { sensitivity: 'base' });
}
type SampleProject = { id: string; title: string; problem: string; investigation_type: ResearchMode; difficulty: ProjectDifficulty | null; strategy_count: number; best_paper_score?: number | null; curated?: boolean; featured_paper_id?: string | null; paper_count?: number | null };
const strategyCount = (count: number) => `${count} ${count === 1 ? 'strategy' : 'strategies'}`;
const paperCount = (count: number) => `${count} ${count === 1 ? 'paper' : 'papers'}`;
function suggestedSaveAsName(title: string): string {
  const version = title.match(/^(.*\bv)(\d+)$/i);
  if (version) return version[1] + String(Number(version[2]) + 1);
  return title.slice(0, 193) + ' (copy)';
}

function ProjectSaveAsDialog({ entry, onCancel, onSaved }: {
  entry: RecentProject;
  onCancel: () => void;
  onSaved: (view: ProjectView) => void;
}) {
  useDocumentScrollLock();
  const dialog = useRef<HTMLDialogElement>(null);
  const nameInput = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const [title, setTitle] = useState(() => suggestedSaveAsName(entry.title));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (!element.open) element.showModal();
    nameInput.current?.focus();
    nameInput.current?.select();
    return () => { if (element.open) element.close(); };
  }, []);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (submitting.current || !title.trim()) return;
    submitting.current = true; setBusy(true); setError('');
    try {
      const copy = await post<ProjectView>('save-as', { path: entry.path, title: title.trim() }, undefined, true);
      onSaved(copy);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      submitting.current = false; setBusy(false);
    }
  }
  return <dialog ref={dialog} className="project-settings-dialog save-as-project-dialog"
    aria-labelledby="save-as-project-heading"
    onCancel={event => { event.preventDefault(); if (!submitting.current) onCancel(); }}>
    <form onSubmit={save}>
      <header className="settings-header">
        <h2 id="save-as-project-heading">Save Copy</h2>
        <div className="settings-actions">
          <button type="submit" className="settings-cancel" disabled={busy || !title.trim()}>{busy ? 'Saving…' : 'Save'}</button>
          <DialogDismissButton label="Cancel save copy" disabled={busy} onClick={onCancel}/>
        </div>
      </header>
      <div className="settings-body">
        <label htmlFor="save-as-project-title">New project name</label>
        <input ref={nameInput} id="save-as-project-title" type="text" value={title}
          required maxLength={200} disabled={busy} spellCheck={false}
          aria-invalid={!!error} aria-describedby={error ? 'save-as-project-error' : undefined}
          onChange={event => { setTitle(event.target.value); setError(''); }}/>
        {error && <p className="save-as-project-error" id="save-as-project-error" role="alert">{error}</p>}
      </div>
    </form>
  </dialog>;
}

// Home unmounts while a project is open. Retain lightweight list rows and the
// last opened project view within this browser tab so returning is immediate.
// Scope both caches to the authenticated workspace; never reuse another user's data.
const recentProjectListCache = new Map<string, RecentProject[]>();
// Paper counts and best scores are slow-changing decorations. Keep their
// hydration timestamp across Home/Project navigation to avoid rescanning a
// growing paper library every five seconds.
const recentPaperMetadataFetchedAt = new Map<string, number>();
const recentProjectViewCache = new Map<string, ProjectView>();
function projectCacheScope(cloud: CloudIdentityState | null): string {
  if (!cloud?.enabled) return 'local';
  if (!cloud.authenticated || cloud.user?.role === 'guest') return 'guest';
  return `member:${cloud.account?.workspace?.id ?? cloud.user?.email ?? ''}`;
}
function projectViewCacheKey(scope: string, path: string): string {
  return `${scope}\u0000${path}`;
}

// One-use metadata handoff lets Home keep its Opening indicator until the
// Papers list is ready, without retrieving a PDF, TeX, or full paper body.
type InitialPaperListing = {
  projectId: string;
  papers: PaperSummary[];
  runs: PaperRun[];
  nextPaperNumber: number | null;
};
const initialPaperListings = new Map<string, InitialPaperListing>();
// One-use Group settings snapshot. Avoid refetching the same collaboration
// summary while mounting Project Settings from Home.
const preloadedGroupSettings = new Map<string, SharedProjectInfo>();
async function preloadPaperListing(path: string, projectId: string): Promise<void> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(`/api/projects/papers?${new URLSearchParams({ path, include_runs: 'false' })}`, {
      signal: controller.signal, cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' },
    });
    if (!response.ok) return; // The Project pane will show its own retry/error.
    const data = await response.json();
    initialPaperListings.set(path, {
      projectId,
      papers: Array.isArray(data.papers) ? data.papers : [],
      runs: Array.isArray(data.runs) ? data.runs : [],
      nextPaperNumber: typeof data.next_paper_number === 'number' ? data.next_paper_number : null,
    });
  } catch { /* Navigation can proceed; the Project pane retries normally. */ }
  finally { window.clearTimeout(timeout); }
}
function takeInitialPaperListing(path: string, projectId: string): InitialPaperListing | null {
  const listing = initialPaperListings.get(path);
  initialPaperListings.delete(path);
  return listing?.projectId === projectId ? listing : null;
}

// The Project header renders this same PNG as an image and as a CSS
// background. Decode it before switching Home → Project so there is never a
// transient empty patch where the SIGMA waves belong.
let projectArtworkReady = false;
let projectArtworkPromise: Promise<void> | null = null;
function preloadProjectArtwork(): Promise<void> {
  if (projectArtworkReady) return Promise.resolve();
  if (!projectArtworkPromise) {
    projectArtworkPromise = new Promise<void>((resolve, reject) => {
      const image = new Image();
      image.onload = () => {
        const decoded = typeof image.decode === 'function' ? image.decode() : Promise.resolve();
        void decoded.then(() => { projectArtworkReady = true; resolve(); }, reject);
      };
      image.onerror = () => reject(new Error('SIGMA header artwork could not be loaded.'));
      image.src = '/sigma-project-header.png';
    }).catch(error => {
      projectArtworkPromise = null;
      throw error;
    });
  }
  return projectArtworkPromise;
}

function ProjectOpeningHourglass() {
  return <span className="project-opening-hourglass" aria-hidden="true">⌛</span>;
}

/** Avoid flashing an hourglass/message for operations that finish quickly. */
function useDelayedProjectProgress(operation: string): string {
  const [visible, setVisible] = useState('');
  useEffect(() => {
    setVisible('');
    if (!operation) return;
    const timer = window.setTimeout(() => setVisible(operation), 1000);
    return () => window.clearTimeout(timer);
  }, [operation]);
  return visible === operation ? visible : '';
}

function RecentProjects({ onOpen, getCachedView, onNavigateActivity, cacheScope, flat = false, active = false, projects, setProjects, loading, setLoading }: {
  cacheScope: string;
  onOpen: (view: ProjectView, openSettings?: boolean, fromCache?: boolean, revealPaperId?: string) => Promise<void> | void;
  getCachedView: (path: string) => ProjectView | undefined;
  onNavigateActivity: (entry: RecentProject, run: ActivityRunTarget | null) => void;
  flat?: boolean;
  active?: boolean;
  projects: RecentProject[];
  setProjects: Dispatch<SetStateAction<RecentProject[]>>;
  loading: boolean;
  setLoading: Dispatch<SetStateAction<boolean>>;
}) {
  const [opening, setOpening] = useState('');
  const [removing, setRemoving] = useState('');
  const visibleProgress = useDelayedProjectProgress(removing ? `remove:${removing}` : opening ? `open:${opening}` : '');
  const [confirmRemoveId, setConfirmRemoveId] = useState('');
  const [saveAsEntry, setSaveAsEntry] = useState<RecentProject | null>(null);
  const [confirmRemovePlacement, setConfirmRemovePlacement] = useState<'above' | 'below'>('below');
  const [error, setError] = useState('');
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const pending = useRef(false);
  // A polling response initiated before leaving a shared project must not
  // resurrect its row after membership revocation succeeds.
  const leftProjects = useRef(new Set<string>());
  const load = useCallback(async (signal?: AbortSignal, lightweight = false) => {
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort, { once: true });
    const timeout = window.setTimeout(abort, 15000);
    try {
      const response = await fetch(lightweight ? '/api/projects/recent?lightweight=true' : '/api/projects/recent', { signal: controller.signal });
      const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Recent Projects unavailable.');
      // A fast identity refresh must not erase paper/activity decorations from
      // cached rows while their slower hydration is still in flight.
      setProjects(current => {
        const next = (data.projects as RecentProject[]).filter(entry => !leftProjects.current.has(entry.id));
        if (!lightweight) return next;
        const prior = new Map(current.map(entry => [entry.id, entry]));
        return next.map(entry => {
          const previous = prior.get(entry.id);
          if (!previous || previous.path !== entry.path) return entry;
          return {
            ...entry,
            paper_count: previous.paper_count,
            best_paper_score: previous.best_paper_score,
            research_running: previous.research_running,
            paper_generating: previous.paper_generating,
            paper_activity: previous.paper_activity,
            answer_active: previous.answer_active,
            activity_runs: previous.activity_runs,
          };
        });
      });
      if (!lightweight) recentPaperMetadataFetchedAt.set(cacheScope, Date.now());
      setError(''); setLoading(false);
    } catch (cause) {
      if (controller.signal.aborted && !signal?.aborted) {
        throw new Error('My Work request timed out. Check the backend project-listing logs.');
      }
      throw cause;
    } finally {
      window.clearTimeout(timeout);
      signal?.removeEventListener('abort', abort);
    }
  }, [cacheScope]);
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    let requestPending = false;
    // Each Home mount starts with a shallow request, even when cached. Never
    // make the first paint of a returning list wait for a deep status scan.
    let firstLoad = true;
    const refresh = async () => {
      if (controller.signal.aborted || document.visibilityState !== 'visible' || requestPending) return;
      requestPending = true;
      try {
        const firstPaint = firstLoad;
        firstLoad = false;
        // Always refresh cheap identities so new/copied projects appear
        // promptly. Only the background hydration fetches paper scores.
        const paperMetadataDue =
          Date.now() - (recentPaperMetadataFetchedAt.get(cacheScope) ?? 0) >= 60_000;
        await load(controller.signal, firstPaint || !paperMetadataDue);
        if (!controller.signal.aborted) {
          setError('');
          // Render names first, then hydrate paper decorations asynchronously.
          if (firstPaint && paperMetadataDue) window.setTimeout(() => void refresh(), 250);
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setProjects(current => current.map(entry => ({ ...entry, research_running: false, paper_generating: false, paper_activity: null })));
          setError(errorMessage(error));
          setLoading(false);
        }
      } finally {
        requestPending = false;
      }
    };
    // Only the selected Home tab polls. The other tab remains mounted but
    // inactive, avoiding duplicate full-project scans and index-lock pressure.
    const interval = window.setInterval(() => void refresh(), 5000);
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    void refresh();
    return () => {
      controller.abort();
      window.clearInterval(interval);
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, [load, active, cacheScope]);
  async function open(entry: RecentProject, openSettings = false, revealBestPaper = false) {
    if (pending.current) return;
    pending.current = true; setOpening(entry.id); setError('');
    try {
      const cached = getCachedView(entry.path);
      // Group does not need paper metadata. The star selects its destination
      // concurrently with opening the project, then reuses the loaded listing.
      const settingsPromise: Promise<SharedProjectInfo | undefined> = openSettings
        ? fetch(`/api/projects/collaboration?${new URLSearchParams({ path: entry.path, include_authors: 'false' })}`, {
            cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' },
          }).then(async response => {
            const body = await response.json();
            if (!response.ok) throw new Error(body.error ?? 'Shared project settings are unavailable.');
            return body as SharedProjectInfo;
          })
        : Promise.resolve(undefined);
      const paperIdPromise: Promise<string | undefined> = revealBestPaper
        ? fetch(`/api/projects/papers?${new URLSearchParams({ path: entry.path })}`, {
            cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' },
          }).then(async response => {
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error ?? 'Could not load paper scores.');
            const papers = Array.isArray(payload.papers) ? payload.papers as PaperSummary[] : [];
            const scored = papers.filter(paper => paper.pdf_available && paper.score != null)
              .sort((left, right) => (right.score?.total ?? 0) - (left.score?.total ?? 0)
                || right.paper_version - left.paper_version);
            if (!scored.length) throw new Error('No scored paper with an available PDF was found.');
            initialPaperListings.set(entry.path, {
              projectId: entry.id, papers,
              runs: Array.isArray(payload.runs) ? payload.runs : [],
              nextPaperNumber: typeof payload.next_paper_number === 'number' ? payload.next_paper_number : null,
            });
            return scored[0].paper_id;
          })
        : Promise.resolve(undefined);
      const [view, paperId, groupSettings] = await Promise.all([
        cached?.project.id === entry.id
          ? Promise.resolve(cached)
          : post<ProjectView>('open', { path: entry.path, compact: true }),
        paperIdPromise,
        settingsPromise,
      ]);
      if (groupSettings) preloadedGroupSettings.set(view.path, groupSettings);
      await onOpen(view, openSettings, cached?.project.id === entry.id, paperId);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { pending.current = false; setOpening(''); }
  }
  async function forget(entry: RecentProject) {
    if (pending.current) return; pending.current = true; setRemoving(entry.id); setError('');
    try {
      if (entry.collaborator) {
        await post('collaboration/leave', { path: entry.path, project_id: entry.id });
        leftProjects.current.add(entry.id);
        setProjects(current => current.filter(project => project.id !== entry.id));
      } else {
        await post(`recent/forget?path=${encodeURIComponent(entry.path)}`, { project_id: entry.id });
      }
      setConfirmRemoveId('');
      await load();
    } catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setRemoving(''); }
  }
  const eligibleProjects = projects.filter(project => project.available && !researchTypeLabel(project.investigation_type).startsWith('Unavailable'));
  const visibleProjects = flat ? eligibleProjects : [...eligibleProjects].sort((a, b) =>
    researchTypeLabel(a.investigation_type).localeCompare(researchTypeLabel(b.investigation_type)) || compareSavedVersions(a, b));
  const recentRunLabels = (entry: RecentProject): string[] => {
    const runs = entry.activity_runs ?? [];
    return runs.map(run => formatRunAttribution({ ...run, mode: 'hover' }));
  };
  // Running work takes precedence over a queued paper on the same project.
  // The queue API exposes paper_activity when the queued-generation feature lands.
  const paperActivity = (entry: RecentProject): 'running' | 'queued' | null => {
    if (entry.activity_runs?.length) {
      return entry.activity_runs.some(run => run.status === 'active') ? 'running' : 'queued';
    }
    return entry.research_running || entry.answer_active || entry.paper_generating || entry.paper_activity === 'active'
      ? 'running' : entry.paper_activity === 'queued' ? 'queued' : null;
  };
  const activityDescription = (entry: RecentProject): string => {
    const status = paperActivity(entry);
    if (status === 'queued') {
      return entry.activity_runs?.length === 1 && entry.activity_runs[0].kind === 'paper'
        ? 'Paper queued'
        : entry.activity_runs?.length === 1 && entry.activity_runs[0].kind === 'session'
          ? 'Session queued' : 'Queued';
    }
    if (entry.activity_runs?.length === 1 && entry.activity_runs[0].kind === 'paper') return 'Generating paper';
    if (entry.activity_runs?.length === 1 && entry.activity_runs[0].kind === 'answer') return 'Answering';
    if (!entry.activity_runs?.length && entry.answer_active) return 'Answering';
    return 'Running';
  };
  // Keep the ten newest projects plus every older running or queued project.
  // Filtering in source order avoids duplicating an active project in the top ten.
  const mostRecentProjects = flat
    ? visibleProjects.filter((project, index) => index < 10 || paperActivity(project) !== null)
    : visibleProjects;
  const recentGroups = mostRecentProjects.reduce<Array<{ type: ResearchMode; projects: RecentProject[] }>>((groups, project) => {
    if (flat) { if (!groups.length) groups.push({ type: 'default', projects: [] }); groups[0].projects.push(project); return groups; }
    const type: ResearchMode = project.investigation_type || 'default';
    const group = groups.find(item => item.type === type);
    if (group) group.projects.push(project);
    else groups.push({ type, projects: [project] });
    return groups;
  }, []).sort((a, b) => flat ? 0 : researchTypeLabel(a.type).localeCompare(researchTypeLabel(b.type)));
  return <div className="empty home-empty home-recents" data-opening={!!opening || !!removing}>
    {loading ? <p role="status">{flat ? 'Loading recent projects...' : 'Loading My Work projects...'}</p> : !projects.length && <p>No projects are currently being worked on.</p>}
    {recentGroups.map(group => {
      const groupKey = group.type ?? 'other';
      const groupExpanded = expandedGroups[groupKey] ?? savedHomeGroupOpen('recent', groupKey);
      const hiddenGroupActivity = !groupExpanded
        ? (group.projects.some(entry => paperActivity(entry) === 'running') ? 'running'
          : group.projects.some(entry => paperActivity(entry) === 'queued') ? 'queued' : null)
        : null;
      return <details className={`recent-type-group${flat ? ' recent-flat-group' : ''}`} key={groupKey} open={flat || groupExpanded} onToggle={event => {
        if (flat) return;
        const isOpen = event.currentTarget.open;
        try { window.localStorage.setItem(`sigma.home.recentGroup:${groupKey}`, String(isOpen)); } catch { /* Preserve state when storage is available. */ }
        setExpandedGroups(current => current[groupKey] === isOpen ? current : { ...current, [groupKey]: isOpen });
      }}>
      <summary>{group.type && <ResearchTypeIcon type={group.type} snapshot={group.projects[0]?.project_type_snapshot}/>}<span>{researchTypeLabel(group.type)}</span><small>{group.projects.length} {group.projects.length === 1 ? 'project' : 'projects'}{hiddenGroupActivity && <><span className={`research-running-indicator${hiddenGroupActivity === 'queued' ? ' paper-queued-indicator' : ''}`} aria-hidden="true" data-tooltip-activity="true" data-tooltip={(() => {
        const active = group.projects.filter(project => paperActivity(project));
        const labels = active.flatMap(project => recentRunLabels(project).map(label => `${project.title}: ${label}`));
        return labels.join('\n') || undefined;
      })()}/><span className="sr-only">{hiddenGroupActivity === 'queued' ? 'Paper generation queued in this category' : 'Activity running in this category'}</span></>}</small></summary>
      <ul>{group.projects.map((entry, index) => <li key={entry.id}>
        <div className="recent-entry">
          <div className="recent-title-row">
            <button className="recent-open" disabled={!entry.available || !!opening} aria-busy={opening === entry.id || removing === entry.id} aria-label={opening === entry.id ? `Opening ${entry.title}` : removing === entry.id ? `Removing ${entry.title}` : undefined} onClick={() => void open(entry)}>{entry.title}{(visibleProgress === `open:${entry.id}` || visibleProgress === `remove:${entry.id}`) && <><ProjectOpeningHourglass/><span className="project-opening-label">{removing === entry.id ? 'Removing...' : 'Opening...'}</span></>}</button>
            {paperActivity(entry) && <button type="button" className="recent-activity-jump" aria-label={`Open active work in ${entry.title}`}
              data-tooltip={recentRunLabels(entry).join('\n') || activityDescription(entry)} data-tooltip-activity="true"
              disabled={!entry.available} onClick={() => onNavigateActivity(entry, entry.activity_runs?.find(run => run.status === 'active') ?? entry.activity_runs?.[0] ?? null)}>
              <span className={`research-running-indicator${paperActivity(entry) === 'queued' ? ' paper-queued-indicator' : ''}`} aria-hidden="true"/>
            </button>}
            {entry.best_paper_score != null && entry.best_paper_score >= HIGH_SCORING_PAPER_THRESHOLD && <button type="button" className="recent-title-annotation recent-title-star" disabled={!!opening} aria-label="View high scoring paper" data-tooltip={HIGH_SCORING_PAPER_TOOLTIP} data-tooltip-follow-cursor="true" onClick={() => void open(entry, false, true)}>★</button>}
            {entry.shared && <button type="button" className="recent-title-annotation recent-title-shared" disabled={!entry.available || !!opening} aria-label={`Manage collaborators for ${entry.title}`} data-tooltip="Shared project · Open Project Settings to manage collaborators" data-tooltip-follow-cursor="true" onClick={() => void open(entry, true)}><UsersRoundIcon/></button>}
            <button type="button" className="recent-save-as" disabled={!!opening || !entry.available}
            aria-label="Save project with a new name" data-tooltip="Save project with a new name"
            onClick={() => { setConfirmRemoveId(''); setSaveAsEntry(entry); }}>
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>
          </button><button className="recent-forget" disabled={!!opening} aria-label={entry.collaborator ? 'Stop collaborating on this project' : 'Remove this project'} aria-expanded={confirmRemoveId === entry.id} data-tooltip={entry.collaborator ? 'Stop collaborating on this project' : 'Remove this project'} onClick={event => {
            if (confirmRemoveId === entry.id) { setConfirmRemoveId(''); return; }
            const trigger = event.currentTarget.getBoundingClientRect();
            setConfirmRemovePlacement(window.innerHeight - trigger.bottom < 190 ? 'above' : 'below');
            setConfirmRemoveId(entry.id);
          }}><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" aria-hidden="true"><path d="M8 8 16 16M16 8 8 16"/></svg></button>{confirmRemoveId === entry.id && <div className={`recent-remove-actions recent-remove-${confirmRemovePlacement}`}><div className="recent-remove-confirm" role="group" aria-label={`Confirm remove ${entry.title}`}><p>{entry.collaborator ? `Stop collaborating on “${entry.title}”?` : `Remove “${entry.title}” from My Work?`}</p><div className="recent-remove-confirm-actions"><button type="button" className="text-view-link" disabled={!!opening} onClick={() => void forget(entry)}>Confirm</button><button type="button" className="text-view-link" disabled={!!opening} onClick={() => setConfirmRemoveId('')}>Cancel</button></div></div></div>}
          </div>
          <div className="recent-meta-row"><small><span>{difficultyDescription(entry.difficulty)}{entry.strategy_count !== null && <> · {strategyCount(entry.strategy_count)}</>}{entry.paper_count != null && <> · {paperCount(entry.paper_count)}</>}{entry.best_paper_score != null && <> · Best score {entry.best_paper_score}/100</>}</span></small></div>
        </div>
        {entry.error && <p className="recent-unavailable">{entry.error}</p>}
      </li>)}</ul>
    </details>;
    })}
    {error && <p role="alert" className="error">{error}</p>}
    {saveAsEntry && <ProjectSaveAsDialog key={saveAsEntry.id} entry={saveAsEntry}
      onCancel={() => setSaveAsEntry(null)} onSaved={view => { setSaveAsEntry(null); onOpen(view); }}/>} 
  </div>;
}

function SampleProjects({ onOpen, guest = false, active = false }: { onOpen: (view: ProjectView, openSettings?: boolean, fromCache?: boolean, revealPaperId?: string) => Promise<void> | void; guest?: boolean; active?: boolean }) {
  const [projects, setProjects] = useState<SampleProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [opening, setOpening] = useState('');
  const visibleOpening = useDelayedProjectProgress(opening);
  const pending = useRef(false);
  const loaded = useRef(false);
  useEffect(() => {
    // Loading My Work must not verify the entire sample-paper catalog.
    if (!active || loaded.current) return;
    const controller = new AbortController();
    void fetch('/api/projects/samples', { signal: controller.signal }).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? 'Samples unavailable.');
      if (controller.signal.aborted) return;
      setProjects([...data.projects].sort((a: SampleProject, b: SampleProject) => {
        const typeOrder = researchTypeLabel(a.investigation_type).localeCompare(researchTypeLabel(b.investigation_type), 'en', { sensitivity: 'base' });
        return typeOrder || a.title.localeCompare(b.title, 'en', { sensitivity: 'base' });
      }));
      loaded.current = true;
      setError(''); setLoading(false);
    }).catch(error => { if (!controller.signal.aborted) { setError(errorMessage(error)); setLoading(false); } });
    return () => controller.abort();
  }, [active]);
  async function open(sample: SampleProject, revealFeaturedPaper = false) {
    if (pending.current) return; pending.current = true; setOpening(sample.id); setError('');
    try {
      const copy = await post<ProjectView>('samples/open', { sample_id: sample.id });
      // A sample opens an independent working copy, never mutating the template.
      // The visitor may explore it without joining this guest path to a future
      // Google identity (including featured-paper deep links).
      if (guest) window.sessionStorage.setItem('sigma.guestSamplePath', copy.path);
      window.localStorage.setItem('sigma.homeCatalogTab', 'recent');
      if (revealFeaturedPaper) await preloadPaperListing(copy.path, copy.project.id);
      const papers = revealFeaturedPaper ? initialPaperListings.get(copy.path)?.papers ?? [] : [];
      const featured = revealFeaturedPaper && sample.curated
        ? papers.find(paper => paper.paper_id === sample.featured_paper_id && paper.pdf_available)
        : revealFeaturedPaper ? papers.filter(paper => paper.pdf_available && paper.score != null)
          .sort((left, right) => (right.score?.total ?? 0) - (left.score?.total ?? 0)
            || right.paper_version - left.paper_version)[0] : undefined;
      if (revealFeaturedPaper && !featured) throw new Error('The featured sample paper is unavailable.');
      await onOpen(copy, false, false, featured?.paper_id);
    }
    catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setOpening(''); }
  }
  const groups = projects.reduce<Array<{ type: ResearchMode; samples: SampleProject[] }>>((result, sample) => {
    const group = result.find(item => item.type === sample.investigation_type);
    if (group) group.samples.push(sample);
    else result.push({ type: sample.investigation_type, samples: [sample] });
    return result;
  }, []);
  return <div className="empty home-empty home-samples" data-opening={!!opening}>
    {loading ? <p role="status">Loading sample projects…</p> : !projects.length && !error && <p>No sample projects are available.</p>}
    {groups.map(group => <details className="sample-type-group" key={group.type} open={savedHomeGroupOpen('sample', group.type)} onToggle={event => { try { window.localStorage.setItem(`sigma.home.sampleGroup:${group.type}`, String(event.currentTarget.open)); } catch { /* Keep the disclosure usable when storage is unavailable. */ } }}>
      <summary><ResearchTypeIcon type={group.type}/><span>{researchTypeLabel(group.type)}</span><small>{group.samples.length} {group.samples.length === 1 ? 'sample' : 'samples'}</small></summary>
      <ul>{group.samples.map(sample => <li key={sample.id}>{sample.curated && sample.featured_paper_id && <button type="button" className="recent-title-annotation recent-title-star" disabled={!!opening} aria-label="Open curated sample paper" data-tooltip="Includes a sample paper" data-tooltip-follow-cursor="true" onClick={() => void open(sample, true)}>★</button>}<button className="sample-open" disabled={!!opening} aria-busy={opening === sample.id} onClick={() => void open(sample)} aria-label={opening === sample.id ? `Opening ${sample.title}` : `Open ${sample.title}`}><strong>{sample.title}{visibleOpening === sample.id && <><ProjectOpeningHourglass/><span className="project-opening-label">Opening...</span></>}</strong><small><span>{strategyCount(sample.strategy_count)} · {sample.best_paper_score != null && <>Best score {sample.best_paper_score}/100 · </>}{difficultyDescription(sample.difficulty)}</span></small></button></li>)}</ul>
    </details>)}
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

function HomeCatalog({ onOpen, getCachedView, onNavigateActivity, cacheScope, guest = false, onTabChange }: { onOpen: (view: ProjectView, openSettings?: boolean, fromCache?: boolean, revealPaperId?: string) => Promise<void> | void; getCachedView: (path: string) => ProjectView | undefined; onNavigateActivity: (entry: RecentProject, run: ActivityRunTarget | null) => void; cacheScope: string; guest?: boolean; onTabChange?: (tab: 'recent' | 'samples' | 'most-recent') => void }) {
  const savedTooltip = guest
    ? 'Your temporary private work in this browser (expires after inactivity or server restart).'
    : 'Show My Work. Click again to collapse or expand all.';
  const [tab, setTab] = useState<'recent' | 'samples' | 'most-recent'>(() => {
    if (guest) return 'samples';
    const saved = window.localStorage.getItem('sigma.homeCatalogTab');
    return saved === 'recent' || saved === 'most-recent' ? saved : 'samples';
  });
  // A signed-out visitor starts in Samples even if the previous member was
  // browsing My Work. This only changes the initial selection, not guest tabs.
  useEffect(() => {
    if (guest) setTab('samples');
  }, [guest]);
  // My Work and Most Recent are two views of one list, not two independent fetches.
  const [savedProjects, setSavedProjects] = useState<RecentProject[]>(() => recentProjectListCache.get(cacheScope) ?? []);
  const [savedLoading, setSavedLoading] = useState(() => !recentProjectListCache.has(cacheScope));
  useEffect(() => {
    // The favicon's 5-second activity poll already has these booleans.
    // Reuse them for Home badges instead of rereading every paper and session.
    const onActivity = (event: Event) => {
      const updates = (event as CustomEvent<RecentProject[]>).detail;
      if (!Array.isArray(updates)) return;
      const byId = new Map(updates.map(item => [item.id, item]));
      setSavedProjects(current => current.map(entry => {
        const next = byId.get(entry.id);
        if (!next) return entry;
        const changed = entry.research_running !== next.research_running
          || entry.paper_activity !== next.paper_activity
          || entry.paper_generating !== (next.paper_activity === 'active')
          || entry.answer_active !== next.answer_active;
        if (!changed) return entry;
        return {
          ...entry,
          research_running: next.research_running,
          paper_activity: next.paper_activity,
          paper_generating: next.paper_activity === 'active',
          answer_active: next.answer_active,
          activity_author: next.activity_author,
          // Do not navigate using a run ID from an earlier activity snapshot.
          activity_runs: [],
        };
      }));
    };
    window.addEventListener('sigma-saved-activity', onActivity);
    return () => window.removeEventListener('sigma-saved-activity', onActivity);
  }, []);
  useEffect(() => {
    if (savedLoading) return;
    recentProjectListCache.delete(cacheScope);
    recentProjectListCache.set(cacheScope, savedProjects);
    if (recentProjectListCache.size > 6) {
      const oldest = recentProjectListCache.keys().next().value;
      if (oldest !== undefined) recentProjectListCache.delete(oldest);
    }
  }, [cacheScope, savedProjects, savedLoading]);
  const recent = useRef<HTMLButtonElement>(null);
  const mostRecent = useRef<HTMLButtonElement>(null);
  const samples = useRef<HTMLButtonElement>(null);
  const recentPanel = useRef<HTMLDivElement>(null);
  const mostRecentPanel = useRef<HTMLDivElement>(null);
  const samplesPanel = useRef<HTMLDivElement>(null);
  useEffect(() => { window.localStorage.setItem('sigma.homeCatalogTab', tab); onTabChange?.(tab); }, [tab, onTabChange]);
  useEffect(() => {
    const toggle = () => { if (tab !== 'most-recent') switchTab(tab); };
    window.addEventListener('sigma-home-projects-toggle-groups', toggle);
    return () => window.removeEventListener('sigma-home-projects-toggle-groups', toggle);
  }, [tab]);
  function switchTab(next: 'recent' | 'samples' | 'most-recent') {
    if (next === tab) {
      const panel = next === 'samples' ? samplesPanel.current : next === 'recent' ? recentPanel.current : mostRecentPanel.current;
      if (panel) {
        const selector = next === 'samples' ? '.sample-type-group' : next === 'recent' ? '.recent-type-group' : '';
        const groups = selector ? Array.from(panel.querySelectorAll<HTMLDetailsElement>(selector)) : [];
        const expandAll = groups.length > 0 && groups.every(group => !group.open);
        groups.forEach(group => { group.open = expandAll; });
      }
      return;
    }
    setTab(next); (next === 'recent' ? recent : next === 'most-recent' ? mostRecent : samples).current?.focus();
  }
  return <div className="home-catalog"><div className="catalog-tabs" role="tablist" aria-label="Project lists" onKeyDown={event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); const tabs = ['samples', 'recent', 'most-recent'] as const; switchTab(tabs[(tabs.indexOf(tab) + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length]); }
    if (event.key === 'Home') { event.preventDefault(); switchTab('samples'); }
    if (event.key === 'End') { event.preventDefault(); switchTab('most-recent'); }
  }}>
    <button ref={samples} id="samples-tab" role="tab" aria-controls="samples-panel" aria-selected={tab === 'samples'} tabIndex={tab === 'samples' ? 0 : -1} data-tooltip="Selecting a sample copies into a new project." onClick={() => switchTab('samples')}>Samples</button>
    <button ref={recent} id="recent-tab" role="tab" aria-controls="recent-panel" aria-selected={tab === 'recent'} tabIndex={tab === 'recent' ? 0 : -1} data-tooltip={savedTooltip} onClick={() => switchTab('recent')}>My Work</button>
    <button ref={mostRecent} id="most-recent-tab" role="tab" aria-controls="most-recent-panel" aria-selected={tab === 'most-recent'} tabIndex={tab === 'most-recent' ? 0 : -1} onClick={() => switchTab('most-recent')}>Most Recent</button>
  </div>
    <div ref={recentPanel} id="recent-panel" role="tabpanel" aria-labelledby="recent-tab" hidden={tab !== 'recent'}><RecentProjects onOpen={onOpen} getCachedView={getCachedView} onNavigateActivity={onNavigateActivity} cacheScope={cacheScope} active={tab === 'recent'} projects={savedProjects} setProjects={setSavedProjects} loading={savedLoading} setLoading={setSavedLoading}/></div>
    <div ref={mostRecentPanel} id="most-recent-panel" role="tabpanel" aria-labelledby="most-recent-tab" hidden={tab !== 'most-recent'}><RecentProjects onOpen={onOpen} getCachedView={getCachedView} onNavigateActivity={onNavigateActivity} cacheScope={cacheScope} flat active={tab === 'most-recent'} projects={savedProjects} setProjects={setSavedProjects} loading={savedLoading} setLoading={setSavedLoading}/></div>
    <div ref={samplesPanel} id="samples-panel" role="tabpanel" aria-labelledby="samples-tab" hidden={tab !== 'samples'}><SampleProjects onOpen={onOpen} guest={guest} active={tab === 'samples'}/></div>
  </div>;
}

type CloudResearchBudget = {
  allowance_usd: number;
  estimated_usage_usd: number;
  held_usd: number;
  reserved_and_estimated_usd: number;
  remaining_usd: number | null;
  global_cap_exempt?: boolean;
  global_remaining_usd?: number;
  global_ceiling_usd?: number;
  global_spend_period?: 'cumulative' | 'calendar_month';
  global_reset_at?: string | null;
  unknown_provider_attempts: number;
};

function SharedCollaboratorWelcome({ invite, cloud, onDismiss }: {
  invite: SharedInviteIntent; cloud: CloudIdentityState | null; onDismiss: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const currentEmail = cloud?.authenticated ? cloud.user?.email : null;
  useEffect(() => {
    if (dialog.current && !dialog.current.open) { dialog.current.showModal(); dialog.current.focus(); }
    return () => { if (dialog.current?.open) dialog.current.close(); };
  }, []);
  return <dialog ref={dialog} tabIndex={-1} className="google-account-dialog invitation-welcome-dialog shared-collaborator-welcome"
    aria-labelledby="shared-project-invitation-heading"
    onCancel={event => { event.preventDefault(); onDismiss(); }}
    onClick={event => { if (event.target === event.currentTarget) onDismiss(); }}>
    <h2 id="shared-project-invitation-heading" style={{ fontSize: 25, lineHeight: 1.25 }}>Open shared project</h2>
    {invite.title && <p className="invitation-welcome-intro"><strong>{invite.title}</strong></p>}
    <p className="invitation-welcome-intro">Sign in with Google as <strong>{invite.email}</strong> to open the project.</p>
    {currentEmail && currentEmail.toLowerCase() !== invite.email &&
      <p className="invitation-welcome-current-account">Currently signed in as {currentEmail}.</p>}
    <div className="invitation-welcome-actions" style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 40 }}>
      <a className="invitation-welcome-link" style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", padding: 0, minHeight: 32, lineHeight: "32px" }} href="/api/cloud-auth/login">Sign in with Google</a>
      <button type="button" className="invitation-welcome-link" style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", padding: 0, minHeight: 32, lineHeight: "32px" }} onClick={onDismiss}>Not now</button>
    </div>
  </dialog>;
}

function Home({ initialPath, onOpen, getCachedView, onNavigateActivity, cacheScope }: {
  initialPath: string;
  onOpen: (view: ProjectView, openSettings?: boolean, fromCache?: boolean, revealPaperId?: string) => Promise<void> | void;
  getCachedView: (path: string) => ProjectView | undefined;
  onNavigateActivity: (entry: RecentProject, run: ActivityRunTarget | null) => void;
  cacheScope: string;
}) {
  const cloud = useCloudIdentity();
  const homePillsRef = useEqualHeaderPillInsets();
  const [sharedInvite, setSharedInvite] = useState(getPendingSharedInvite);
  useEffect(() => {
    if (!sharedInvite || !cloud?.enabled || !cloud.authenticated || cloud.user?.role === 'guest'
      || cloud.user?.email.toLowerCase() !== sharedInvite.email) return;
    clearPendingSharedInvite();
    window.location.replace(projectUrl(sharedInvite.path));
  }, [sharedInvite, cloud?.enabled, cloud?.authenticated, cloud?.user?.role, cloud?.user?.email]);
  const showConnectionStatus = !cloud?.enabled || (cloud.authenticated && cloud.user?.role !== 'guest');
  const [entry, setEntry] = useState<'open' | 'new' | 'import' | null>(null);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [projectTypesOpen, setProjectTypesOpen] = useState(false);
  const [catalogTab, setCatalogTab] = useState<'recent' | 'samples' | 'most-recent'>(() => {
    if (cloud?.enabled && !cloud.authenticated) return 'samples';
    const saved = window.localStorage.getItem('sigma.homeCatalogTab');
    return saved === 'recent' || saved === 'most-recent' ? saved : 'samples';
  });
  const settingsButton = useRef<HTMLButtonElement>(null);
  const [typeCatalogRevision, setTypeCatalogRevision] = useState(0);
  useEffect(() => {
    const openTypes = () => setProjectTypesOpen(true);
    const refreshTypes = () => {
      void fetch('/api/project-types', { cache: 'no-store' }).then(response => response.ok ? response.json() : Promise.reject()).then((data: { project_types: ProjectTypeRecord[] }) => { projectTypeCache = data.project_types; setTypeCatalogRevision(value => value + 1); }).catch(() => undefined);
    };
    window.addEventListener('sigma-open-project-types', openTypes);
    window.addEventListener('sigma-project-types-updated', refreshTypes);
    const controller = new AbortController();
    void fetch('/api/project-types', { signal: controller.signal }).then(response => response.ok ? response.json() : Promise.reject()).then((data: { project_types: ProjectTypeRecord[] }) => { projectTypeCache = data.project_types; setTypeCatalogRevision(value => value + 1); }).catch(() => undefined);
    return () => { controller.abort(); window.removeEventListener('sigma-open-project-types', openTypes); window.removeEventListener('sigma-project-types-updated', refreshTypes); };
  }, []);
  useEffect(() => {
    const openAbout = () => setAboutOpen(true);
    window.addEventListener('sigma-open-about', openAbout);
    const params = new URLSearchParams(window.location.search);
    if (params.get('show_about') === '1') {
      setAboutOpen(true);
      params.delete('show_about');
      const query = params.toString();
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`);
    }
    return () => window.removeEventListener('sigma-open-about', openAbout);
  }, []);
  const aboutButton = useRef<HTMLButtonElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  const shell = useRef<HTMLDivElement>(null);
  const nextCreditStreak = useRef(0);
  const nextCreditPlunk = useRef(0);
  const turbulenceAnimation = useRef<SVGAnimateElement>(null);
  const displacementAnimation = useRef<SVGAnimateElement>(null);
  const [creditStreaks, setCreditStreaks] = useState<Array<{ id: number; line: 'name' | 'models' }>>([]);
  const [creditPlunk, setCreditPlunk] = useState<number | null>(null);
  const [creditAdjective] = useState(() => OPENAI_AGENT_CREDIT_ADJECTIVES[Math.floor(Math.random() * OPENAI_AGENT_CREDIT_ADJECTIVES.length)].toLowerCase());
  useEffect(() => { document.title = 'SIGMA · Research workspace'; heading.current?.focus(); }, []);
  useEffect(() => {
    // CSS background-size: cover scales the source image by the larger of
    // viewport-width/image-width and viewport-height/image-height. Apply
    // that exact same factor to the beam overlay, anchored at image top/center.
    const background = new Image();
    const updateScale = () => {
      if (!background.naturalWidth || !background.naturalHeight) return;
      const scale = Math.max(
        window.innerWidth / background.naturalWidth,
        window.innerHeight / background.naturalHeight,
      );
      shell.current?.style.setProperty('--home-art-scale', String(scale));
    };
    background.addEventListener('load', updateScale);
    window.addEventListener('resize', updateScale);
    background.src = '/sigma-home-background-copper.png';
    if (background.complete) updateScale();
    return () => {
      background.removeEventListener('load', updateScale);
      window.removeEventListener('resize', updateScale);
    };
  }, []);
  function cancel() {
    setEntry(null); requestAnimationFrame(() => newButton.current?.focus());
  }
  function closeAbout() {
    setAboutOpen(false);
    requestAnimationFrame(() => aboutButton.current?.focus());
  }
  function launchCreditStreak() {
    const nameId = ++nextCreditStreak.current;
    const modelsId = ++nextCreditStreak.current;
    setCreditStreaks(current => [...current, { id: nameId, line: 'name' }, { id: modelsId, line: 'models' }]);
  }
  function removeCreditStreak(id: number) {
    setCreditStreaks(current => current.filter(streak => streak.id !== id));
  }
  function launchCreditPlunk() {
    const id = ++nextCreditPlunk.current;
    setCreditPlunk(id);
    requestAnimationFrame(() => {
      turbulenceAnimation.current?.beginElement();
      displacementAnimation.current?.beginElement();
    });
  }
  function finishCreditPlunk(id: number) {
    setCreditPlunk(current => current === id ? null : current);
  }
  return <div ref={shell} className={`home-shell${creditPlunk !== null ? ' home-credit-plunk-active' : ''}`}>
    <svg className="home-effect-definitions" aria-hidden="true" width="0" height="0" focusable="false"><defs><filter id="home-rubber-sheet-filter" x="-12%" y="-12%" width="124%" height="124%"><feTurbulence type="fractalNoise" baseFrequency="0.004 0.008" numOctaves="2" seed="4" result="rubber-wave"><animate ref={turbulenceAnimation} attributeName="baseFrequency" values="0.004 0.008;0.014 0.024;0.006 0.012" dur="900ms" begin="indefinite" fill="freeze"/></feTurbulence><feDisplacementMap in="SourceGraphic" in2="rubber-wave" scale="0" xChannelSelector="R" yChannelSelector="G"><animate ref={displacementAnimation} attributeName="scale" values="0;26;13;0" keyTimes="0;0.2;0.62;1" dur="900ms" begin="indefinite" fill="freeze"/></feDisplacementMap></filter></defs></svg>
    <div className="home-atmosphere" aria-hidden="true"/>
    <div className="home-content">
      <div className="home-topline">
        <div className="home-left-actions"/>
        <div className="home-right-actions"><div className="home-auth-pills"><MockAuthSelector/>
          <div ref={homePillsRef} className="home-account-grid">
            <div className="sigma-header-model-column">
              <div className="sigma-header-secondary-row">
                {cloud?.user?.role === 'admin' && <a href="#administrator-settings" className="administrator-settings-link" aria-label="Administrator settings" onClick={event => { event.preventDefault(); cloud.openAccessManagement(); }}>Admin Settings</a>}
                <div className="sigma-header-about-model-anchor">
                  <div className="sigma-header-first-row">
                    <button type="button" ref={aboutButton} className="home-about-button" aria-label="About SIGMA" data-tooltip-disabled aria-haspopup="dialog" aria-expanded={aboutOpen} onClick={() => setAboutOpen(true)}>About SIGMA</button>
                    {showConnectionStatus && <button type="button" ref={settingsButton} className="home-settings-pill" aria-label="Settings" data-tooltip="SIGMA Settings" aria-haspopup="dialog" aria-expanded={projectTypesOpen} onClick={() => setProjectTypesOpen(true)}><SlidersSettingsIcon/></button>}
                  </div>
                  <ConnectedModelPill enabled={showConnectionStatus}/>
                </div>
              </div>
            </div>
            <div className="identity-pill-stack project-identity-pill-stack sigma-header-account-column">
              <GoogleIdentityPill inviteInHeader/>
              {showConnectionStatus && <ConnectionStatus projectHeader cloudFunding={cloudFundingFor(cloud)} zeroAllowanceAction={<ReloadMeAction connectionPill/>}/>}
            </div>
          </div>
          <HomeInvitationAction/>
        </div></div>
      </div>
      <section className="home-projects" aria-labelledby="home-projects-heading">
        <div className="home-projects-heading">
          <h1 id="home-projects-heading" ref={heading} tabIndex={-1} aria-label="Projects">{catalogTab === 'most-recent' ? 'Projects' : <button type="button" className="home-projects-title-toggle" aria-label="Collapse or expand project type groups" data-tooltip="Collapse or expand project type groups" onClick={() => window.dispatchEvent(new Event('sigma-home-projects-toggle-groups'))}>Projects</button>}</h1>
          {(!cloud?.enabled || !cloud.authenticated || cloud.user?.role !== 'guest') && <>
            <button type="button" ref={newButton} className="home-project-action home-icon-action" aria-label="New project" data-tooltip="New project" onClick={() => setEntry('new')}><CirclePlusIcon/></button>
          {(!cloud?.enabled || cloud.authenticated) && <button type="button" className="home-project-action home-icon-action" aria-label="Upload project" data-tooltip="Upload project" onClick={() => setEntry('import')}><UploadProjectIcon/></button>}
          </>}
        </div>
        <HomeCatalog key={cacheScope} cacheScope={cacheScope} getCachedView={getCachedView} onOpen={onOpen} onNavigateActivity={onNavigateActivity} onTabChange={setCatalogTab} guest={!!cloud?.enabled && !cloud.authenticated}/>
      </section>
      <img className="home-slogan" src="/sigma-slogan-copper-approved.png" alt="Strategy · Investigation · Generation · Measurement · Assessment"/>
      <footer className="home-art-credit" aria-label={`Crafted by Brian Kramer and ${creditAdjective} OpenAI agents`} onPointerEnter={event => { if (!(event.relatedTarget instanceof Node) || !event.currentTarget.contains(event.relatedTarget)) launchCreditStreak(); }} onClick={launchCreditPlunk}><span>Crafted by Brian Kramer</span><span>and {creditAdjective} OpenAI agents.</span>{creditStreaks.map(({ id, line }) => <span key={id} className={`home-credit-streak home-credit-streak--${line}`} aria-hidden="true" onAnimationEnd={() => removeCreditStreak(id)}/>)}{creditPlunk !== null && <span key={creditPlunk} className="home-credit-plunk" aria-hidden="true" onAnimationEnd={() => finishCreditPlunk(creditPlunk)}/>}</footer>
      {entry === 'import' && <ImportProjectDialog onOpen={onOpen} onCancel={cancel}/>}
      {entry === 'open' && <ProjectEntryDialog initialPath={initialPath} onOpen={onOpen} onCancel={cancel}/>}
      {entry === 'new' && <ProjectSettingsDialog onSaved={onOpen} onCancel={cancel}/>}
      {aboutOpen && <AboutDialog onClose={closeAbout}/>}
      {projectTypesOpen && <GlobalSettingsDialog key={cloud?.user?.email ?? 'local'} onClose={() => { setProjectTypesOpen(false); requestAnimationFrame(() => settingsButton.current?.focus()); }}/>}
      {sharedInvite && <SharedCollaboratorWelcome invite={sharedInvite} cloud={cloud}
        onDismiss={() => { clearPendingSharedInvite(); setSharedInvite(null); }}/>}
    </div>
  </div>;
}

type PaneEditorHandle = { saveBeforeCollapse: () => Promise<boolean> };
type StrategyTitleEditorProps = {
  authorEmail?: string; strategy: Strategy; path: string; onSaved: (view: ProjectView) => void; modeDisabled: boolean; descriptionDraft: string; onEnterMode: () => boolean; onExitMode: () => void;
  onEditDescription: () => void; expanded: boolean; onToggle: () => void; commands: ReactNode;
};
const StrategyTitleEditor = forwardRef<PaneEditorHandle, StrategyTitleEditorProps>(function StrategyTitleEditor({ authorEmail, strategy, path, onSaved, modeDisabled, descriptionDraft, onEnterMode, onExitMode, onEditDescription, expanded, onToggle, commands }, ref) {
  const [editing, setEditing] = useState(false);
  const shownTitle = displayStrategyTitle(strategy);
  const [draft, setDraft] = useState(shownTitle);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const input = useRef<HTMLInputElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => { if (!editing) setDraft(shownTitle); }, [shownTitle, editing]);
  useEffect(() => { if (editing) { input.current?.focus(); input.current?.select(); } }, [editing]);
  function cancel(restoreFocus = true) {
    setEditing(false); onExitMode(); setDraft(shownTitle); setError('');
    if (restoreFocus) requestAnimationFrame(() => trigger.current?.focus());
  }
  const saving = useRef(false);
  async function saveDraft(): Promise<boolean> {
    if (busy || saving.current) return false;
    if (!draft.trim()) { setError('Enter a strategy title.'); input.current?.focus(); return false; }
    if (!descriptionDraft.trim()) { setError('Enter a strategy approach.'); return false; }
    if (draft === shownTitle && descriptionDraft === strategy.approach) {
      cancel(false);
      return true;
    }
    saving.current = true; setBusy(true); setError('');
    try {
      const next = await post<ProjectView>('strategies/edit', {
        path, strategy_id: strategy.id, title: draft, approach: descriptionDraft,
      });
      setEditing(false); onExitMode(); onSaved(next);
      requestAnimationFrame(() => trigger.current?.focus());
      return true;
    } catch (cause) {
      setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause));
      return false;
    } finally {
      saving.current = false; setBusy(false);
    }
  }
  useImperativeHandle(ref, () => ({ saveBeforeCollapse: saveDraft }));
  function save(event: FormEvent) {
    event.preventDefault(); event.stopPropagation();
    void saveDraft();
  }
  return <div className={`strategy-title-editor${editing ? ' is-renaming' : ''}`}>
    {editing ? <form ref={form} onSubmit={save} className="strategy-rename-form">
      <label className="sr-only" htmlFor={`strategy-title-${strategy.id}`}>Strategy title</label>
      <input ref={input} id={`strategy-title-${strategy.id}`} aria-label="Strategy title" value={draft} size={Math.max(8, Math.min(50, draft.length + 1))} maxLength={200} disabled={busy}
        required onChange={event => { setDraft(event.target.value); setError(''); }} onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); cancel(); } }}/>
      <button type="submit" className="text-view-link" data-tooltip="Save strategy title" disabled={busy}>Save</button>
      <button type="button" className="text-view-link" data-tooltip="Cancel editing the strategy title" disabled={busy} onClick={() => cancel()}>Cancel</button>
    </form> : <div className="strategy-title-line">
      <button type="button" id={`strategy-${strategy.id}`} className={`strategy-row-disclosure${strategy.enabled ? '' : ' is-disabled'}`} data-tooltip={`${expanded ? 'Collapse' : 'Expand'} strategy: ${shownTitle}`} aria-expanded={expanded} aria-controls={`strategy-content-${strategy.id}`} onClick={onToggle}><DisclosureChevron expanded={expanded}/><h3>{shownTitle}{authorEmail && <small className="artifact-attribution"> · By {authorEmail}</small>}</h3></button>
      <button type="button" ref={trigger} className="text-view-link text-view-icon workspace-icon-button strategy-title-pencil" aria-label={`Edit strategy title and approach: ${shownTitle}`} data-tooltip="Edit strategy title and approach" disabled={modeDisabled}
        onClick={() => { if (onEnterMode()) { setEditing(true); onEditDescription(); } }}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg></button><span id={`strategy-markdown-slot-${strategy.id}`} className="strategy-markdown-slot"/><span id={`strategy-markdown-slot-${strategy.id}-copy`} className="strategy-copy-slot"/>
      {commands}
    </div>}
    {error && <p className="error" role="alert">{error}</p>}
  </div>;
});

function StrategyCommands({ strategy, onCommand, disabled = false }: {
  strategy: Strategy; onCommand: (mode: 'remove' | 'fork' | 'toggle', strategy: Strategy) => void; disabled?: boolean;
}) {
  const [confirmingRemove, setConfirmingRemove] = useState(false);
  return <span className="strategy-inline-commands">
    <button type="button" className="text-view-link strategy-icon-action" disabled={disabled}
      aria-label={`${strategy.enabled ? 'Disable' : 'Enable'} strategy`} aria-pressed={strategy.enabled}
      data-tooltip={`${strategy.enabled ? 'Disable' : 'Enable'} strategy`} onClick={() => onCommand('toggle', strategy)}>
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="4" y="4" width="16" height="16" rx="2"/>{strategy.enabled && <path d="m8 12 3 3 5-6" strokeWidth="2.3"/>}
      </svg>
    </button>
    <button type="button" className="text-view-link strategy-icon-action" disabled={disabled}
      aria-label="Fork strategy" data-tooltip="Fork strategy" onClick={() => onCommand('fork', strategy)}>
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="6" cy="3.5" r="2"/><circle cx="18" cy="6.5" r="2"/><circle cx="6" cy="20.5" r="2"/>
        <path d="M6 5.5v13M18 8.5v2a6 6 0 0 1-6 6H6"/>
      </svg>
    </button>
    <span className="strategy-remove-anchor">
      <button type="button" id={`commands-${strategy.id}`} className="text-view-link strategy-icon-action" disabled={disabled}
        aria-label="Remove strategy" data-tooltip="Remove strategy" onClick={() => setConfirmingRemove(true)}>
        <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round"><path d="M8 8 16 16M16 8 8 16"/></svg>
      </button>
      {confirmingRemove && <div className="strategy-remove-popover"><div className="research-stop-confirm" role="group" aria-label={`Confirm remove strategy ${strategy.title}`}>
        <p>Remove “{strategy.title}” from Strategies?</p>
        <div className="session-remove-confirm-actions">
          <button type="button" className="text-view-link" disabled={disabled} onClick={() => { setConfirmingRemove(false); onCommand('remove', strategy); }}>Confirm</button>
          <DialogDismissButton label="Cancel strategy removal" onClick={() => setConfirmingRemove(false)}/>
        </div>
      </div></div>}
    </span>
  </span>;
}

type NewStrategyProps = {
  path: string; initialDraft?: { title: string; approach: string; summary?: string }; onSaved: (view: ProjectView) => void; onCancel: () => void;
};
const NewStrategy = forwardRef<PaneEditorHandle, NewStrategyProps>(function NewStrategy({ path, onSaved, onCancel, initialDraft }, ref) {
  const submitting = useRef(false);
  const [title, setTitle] = useState(initialDraft?.title ?? '');
  const [approach, setApproach] = useState(initialDraft?.approach ?? '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const titleInput = useRef<HTMLInputElement>(null);
  useEffect(() => { titleInput.current?.focus(); }, []);
  async function saveDraft(): Promise<boolean> {
    if (submitting.current) return false;
    if (!title.trim() || !approach.trim()) {
      setError('Enter both a strategy title and a hypothesis / approach before saving.');
      if (!title.trim()) titleInput.current?.focus();
      return false;
    }
    submitting.current = true; setBusy(true); setError('');
    try {
      onSaved(await post<ProjectView>('strategies', { path, title, approach, summary: initialDraft?.summary ?? '' }));
      return true;
    } catch (cause) {
      setError(errorMessage(cause));
      return false;
    } finally {
      submitting.current = false; setBusy(false);
    }
  }
  useImperativeHandle(ref, () => ({
    saveBeforeCollapse: () => {
      // Only an untouched, empty manual draft is disposable.
      if (!initialDraft && !title.trim() && !approach.trim()) {
        onCancel();
        return Promise.resolve(true);
      }
      return saveDraft();
    },
  }));
  function save(event: FormEvent) {
    event.preventDefault();
    void saveDraft();
  }
  return <form className="strategy-form" aria-labelledby="new-strategy-heading" onSubmit={save}
    onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); onCancel(); } }}>
    <div className="new-strategy-heading-row"><h3 id="new-strategy-heading">{initialDraft ? "Forked strategy" : "New strategy"}</h3><div className="new-strategy-heading-actions"><button type="submit" className="text-view-link" disabled={busy}>{busy ? "Saving…" : "Save"}</button><button type="button" className="text-view-link" disabled={busy} onClick={onCancel}>Cancel</button></div></div>
    <p className="hint">Capture an idea and the approach you want to investigate.</p>
    <fieldset disabled={busy}>
      <label htmlFor="strategy-title">Title</label>
      <input ref={titleInput} id="strategy-title" value={title} maxLength={200} required
        onChange={event => setTitle(event.target.value)} />
      <label htmlFor="strategy-approach">Hypothesis / approach</label>
      <textarea id="strategy-approach" value={approach} maxLength={MAX_STRATEGY_APPROACH} required rows={5}
        onChange={event => setApproach(event.target.value)} />
      {error && <p role="alert" className="error">{error}</p>}
    </fieldset>
  </form>;
});

function StrategyCreationActions({ buttonRef, disabled, hideNew = false, onManual, onAI }: {
  buttonRef: React.RefObject<HTMLButtonElement | null>; disabled: boolean; hideNew?: boolean; onManual: () => void; onAI: () => void;
}) {
  return <div className="strategy-heading-actions">
    {!hideNew && <button type="button" className="text-view-link sigma-heading-icon-action" ref={buttonRef} aria-label="New strategy" data-tooltip="New strategy" disabled={disabled} onClick={onManual}><CirclePlusIcon/></button>}
    <button type="button" className="text-view-link sigma-heading-icon-action" aria-label="Generate strategy" data-tooltip="Generate strategy with AI. Review before saving." disabled={disabled} onClick={onAI}><SparklesActionIcon/></button>
  </div>;
}

function ProcessControlsView({ controls, disabled, guest = false, onGuestPlay, playButtonRef, running = false }: { controls: ProcessControls; disabled: boolean; guest?: boolean; onGuestPlay?: () => void; playButtonRef?: React.RefObject<HTMLButtonElement | null>; running?: boolean }) {
  return <span className="strategy-process-controls" aria-label="Research process controls">
      {controls.confirming ? controls.starting
        ? <span className="research-running-indicator-frame" role="status" aria-label="Starting research session" data-tooltip="Starting session · awaiting server acceptance"><span className="research-running-indicator"/></span>
        : <>
        {controls.confirmationSummary && <span className="session-start-limits" aria-label={`Effective session limits: ${controls.confirmationSummary}`}>{controls.confirmationSummary}</span>}
        <button type="button" className="text-view-link session-start-link" data-tooltip="Start Session" aria-label="Start Session" disabled={disabled} onClick={controls.start}>Start Session</button>
        <button type="button" className="text-view-link session-start-link" data-tooltip="Cancel starting a research session" disabled={disabled} onClick={controls.cancel}>Cancel</button>
      </> : <>
      <button ref={playButtonRef} type="button" className="text-view-link text-view-icon workspace-icon-button process-control" aria-label={controls.playLabel} data-tooltip={controls.playLabel} disabled={disabled || controls.playDisabled} onClick={controls.play}>
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M6 3.8v12.4L16 10 6 3.8Z"/></svg>
      </button>
      <button type="button" className="text-view-link text-view-icon workspace-icon-button process-control" aria-label="Stop research session" data-tooltip="Stop research session" disabled={controls.stopDisabled || disabled} onClick={controls.stop}>
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5h10v10H5z"/></svg>
      </button>
      </>}
      {running && <span className="research-running-indicator-frame" aria-label="Research running" data-tooltip="Research running"><span className="research-running-indicator"/></span>}
  </span>;
}

type ProposalResult = { draft: { title: string; summary: string; approach: string; first_tests: string; assumptions: string; failure_modes: string }; provenance: { provider: string; model: string; reasoning_effort?: string | null }; receipt: string };
type AgenticEvent = { type: string; sequence: number; run_id: string; kind?: 'explore' | 'challenge' | 'revise' | null; attempt?: number | null; summary?: string | null; outcome?: 'revise' | 'retry' | 'present' | 'stop' | null; max_calls?: number | null; draft?: ProposalResult['draft'] | null; provenance?: ProposalResult['provenance'] | null; receipt?: string | null; assessment?: 'distinct' | 'overlapping' | 'unconvincing' | null; objections?: string[] | null; missing_obligations?: string | null; mechanism_comparison?: string | null };
const activityLabels = { explore: 'Exploring a candidate', challenge: 'Independent challenge', revise: 'Targeted revision' } as const;
async function readAgenticStream(response: Response, onEvent: (event: AgenticEvent) => void): Promise<AgenticEvent> {
  if (!response.ok) { let detail = `HTTP ${response.status}`; try { const body = await response.json(); detail = body.error ?? body.detail ?? detail; } catch {} throw new Error(String(detail)); }
  if (!response.body) throw new Error('The server returned no progress stream. No proposal was added.');
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''; let sequence = 0; let runId = ''; let terminal: AgenticEvent | null = null;
  const consume = (chunk: string) => {
    buffer += chunk; const records = buffer.split(/\r?\n\r?\n/); buffer = records.pop() ?? '';
    for (const record of records) {
      const data = record.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
      if (!data) continue;
      let event: AgenticEvent; try { event = JSON.parse(data) as AgenticEvent; } catch { throw new Error('The server sent malformed progress data. You can retry; no proposal was added.'); }
      if (!['run.started', 'activity.started', 'activity.completed', 'decision', 'run.completed', 'run.stopped', 'run.failed'].includes(event?.type)) throw new Error('The server sent an unknown progress event. You can retry; no proposal was added.');
      if (!event || typeof event.type !== 'string' || !Number.isInteger(event.sequence) || event.sequence !== sequence + 1 || typeof event.run_id !== 'string' || !/^[0-9a-f]{32}$/.test(event.run_id)) throw new Error('The progress stream was incomplete or out of order. You can retry; no proposal was added.');
      if (runId && event.run_id !== runId) throw new Error('The progress stream changed run identity. You can retry; no proposal was added.');
      if (terminal) throw new Error('The server sent progress after its terminal event. You can retry; no proposal was added.');
      sequence = event.sequence; runId = event.run_id;
      const activityKind = event.kind === 'explore' || event.kind === 'challenge' || event.kind === 'revise';
      if (event.type === 'run.started' && (!Number.isInteger(event.max_calls) || (event.max_calls ?? 0) < 2 || (event.max_calls ?? 0) > 120)) throw new Error('The server sent an invalid run limit. You can retry; no proposal was added.');
      if (event.type.startsWith('activity.') && (!activityKind || !Number.isInteger(event.attempt) || (event.attempt ?? 0) < 1 || (event.attempt ?? 0) > 15)) throw new Error('The server sent an invalid activity event. You can retry; no proposal was added.');
      if (event.type === 'activity.completed' && typeof event.summary !== 'string') throw new Error('The server sent an incomplete activity result. You can retry; no proposal was added.');
      if (event.type === 'activity.completed' && event.kind === 'challenge' && (!event.assessment || !Array.isArray(event.objections) || typeof event.missing_obligations !== 'string' || typeof event.mechanism_comparison !== 'string')) throw new Error('The server sent an incomplete reviewer summary. You can retry; no proposal was added.');
      if (event.type === 'decision' && (!['revise', 'retry', 'present', 'stop'].includes(event.outcome ?? '') || typeof event.summary !== 'string')) throw new Error('The server sent an invalid coordinator decision. You can retry; no proposal was added.');
      if (['run.stopped', 'run.failed'].includes(event.type) && typeof event.summary !== 'string') throw new Error('The server sent an incomplete terminal result. You can retry; no proposal was added.');
      if (event.type === 'run.completed') {
        const fields = ['title', 'summary', 'approach', 'first_tests', 'assumptions', 'failure_modes'];
        if (!event.draft || typeof event.receipt !== 'string' || !event.receipt || !event.provenance || typeof event.provenance.provider !== 'string' || typeof event.provenance.model !== 'string' || fields.some(key => typeof event.draft?.[key as keyof ProposalResult['draft']] !== 'string')) throw new Error('The completed stream did not include a complete draft and receipt. You can retry; no proposal was added.');
      }
      if (['run.completed', 'run.stopped', 'run.failed'].includes(event.type)) terminal = event;
      onEvent(event);
    }
  };
  try { while (true) { const { done, value } = await reader.read(); if (done) break; consume(decoder.decode(value, { stream: true })); } consume(decoder.decode()); }
  catch (error) { await reader.cancel().catch(() => {}); throw error; }
  if (buffer.trim()) consume('\n\n');
  if (!terminal) throw new Error('The progress stream ended without a final result. You can retry; no proposal was added.');
  return terminal;
}
function GenerateStrategy({ path, projectId, sourceGuard, onSaved, onCancel }: {
  path: string; projectId: string; sourceGuard: string; onSaved: (view: ProjectView) => void; onCancel: () => void;
}) {
  const composer = useRef<HTMLDivElement>(null);
  const request = useRef<AbortController | null>(null);
  const submitting = useRef(false);
  const [config, setConfig] = useState<{ available: boolean; provider: string; mode: string; binding: string; project_id: string; model: string; reasoning_effort: string; message: string } | null>(null);
  const [seed, setSeed] = useState('');
  const ai = useAI();
  const lifetime = useRef(new AbortController());
  const runGuard = useRef('');
  const [result, setResult] = useState<ProposalResult | null>(null);
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [approach, setApproach] = useState('');
  const [busy, setBusy] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [activities, setActivities] = useState<string[]>([]);
  const [currentActivity, setCurrentActivity] = useState('');
  const [review, setReview] = useState<AgenticEvent | null>(null);
  useEffect(() => {
    composer.current?.querySelector('textarea')?.focus();
    const controller = new AbortController();
    fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal }).then(async response => { if (!response.ok) throw new Error('Could not read AI configuration'); return response.json(); }).then(setConfig).catch(error => { if (!controller.signal.aborted) setError(errorMessage(error)); });
    return () => { controller.abort(); lifetime.current.abort(); request.current?.abort(); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal }).then(response => response.json()).then(setConfig).catch(() => {});
    return () => controller.abort();
  }, [ai.info?.mode, ai.info?.active_account, ai.info?.status]);
  const needsConnection = ai.info?.mode !== 'api_key' && ['disconnected', 'reauth_required', 'unauthorized', 'plan_not_permitted'].includes(ai.info?.status ?? 'disconnected');
  async function cancel() {
    if (saving || cancelling) return;
    if (busy) {
      setCancelling(true);
      if (ai.connecting) ai.cancelSignIn();
      request.current?.abort();
      return;
    }
    lifetime.current.abort(); onCancel();
  }
  async function generate() {
    if (submitting.current) return; submitting.current = true;
    runGuard.current = sourceGuard;
    const controller = new AbortController(); request.current = controller; setBusy(true); setError(''); setActivities([]); setCurrentActivity('Preparing run'); setReview(null);
    let finishProviderRequest = () => {};
    try {
      if (needsConnection) {
        const connected = await ai.signIn({ accountId: ai.info?.active_account, enablePlan: ai.info?.status === 'plan_not_permitted', signal: lifetime.current.signal });
        if (!connected || lifetime.current.signal.aborted) return;
      }
      const response = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal });
      if (!response.ok) throw new Error('Could not read current AI settings. Retry explicitly.');
      const latest = await response.json(); setConfig(latest);
      if (latest.project_id !== projectId) throw new Error('Project identity changed during sign-in. Reopen it before generating; your text is retained.');
      if (!latest.available) throw new Error(latest.message);
      if (lifetime.current.signal.aborted) return;
      finishProviderRequest = beginProviderRequest('strategy-generation');
      const stream = await fetch('/api/projects/proposals/agentic', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path, seed, expected_binding: latest.binding, expected_project_id: projectId }), signal: controller.signal });
      const terminal = await readAgenticStream(stream, event => {
        if (event.type === 'activity.started' && event.kind) setCurrentActivity(`${activityLabels[event.kind]}${event.attempt ? ` · attempt ${event.attempt}` : ''}`);
        if (event.type === 'activity.completed' && event.kind) {
          setActivities(previous => [...previous, `${activityLabels[event.kind!]}${event.attempt ? ` · attempt ${event.attempt}` : ''}: ${event.summary ?? 'completed'}`]);
          if (event.kind === 'challenge') setReview(event);
          setCurrentActivity('');
        }
        if (event.type === 'decision') { setActivities(previous => [...previous, `Decision · ${event.outcome}: ${event.summary}`]); setCurrentActivity(''); }
        if (event.type === 'run.started') setCurrentActivity(`Starting bounded run · up to ${event.max_calls ?? 'configured'} model calls`);
      });
      if (terminal.type === 'run.completed' && terminal.draft && terminal.receipt && terminal.provenance) {
        const next: ProposalResult = { draft: terminal.draft, receipt: terminal.receipt, provenance: terminal.provenance };
        setResult(next); setTitle(next.draft.title); setSummary(next.draft.summary); setApproach(next.draft.approach); setCurrentActivity('Ready for your review');
        requestAnimationFrame(() => document.getElementById('proposal-title')?.focus());
      } else if (terminal.type === 'run.stopped') { setCurrentActivity('Run stopped'); setError(`${terminal.summary ?? 'No viable candidate was found.'} No proposal was added. You can retry with different guidance.`); }
      else { setCurrentActivity('Run failed'); throw new Error(terminal.summary ?? 'The run failed. No strategy was added.'); }
    } catch (error) {
      if (controller.signal.aborted) { setCurrentActivity('Run cancelled'); setError('Run cancelled. No proposal was added. If generation had started, its evidence will be retained in project export. You can retry.'); }
      else { const message = errorMessage(error); setCurrentActivity('Run could not be completed'); setError(message); reportRequestFailure(message); }
    }
    finally { finishProviderRequest(); if (request.current === controller) {
      request.current = null;
      submitting.current = false; setBusy(false); setCancelling(false);
    } }
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current || !result) return; submitting.current = true; setSaving(true); setError('');
    try {
      if (runGuard.current !== sourceGuard) throw new Error('Project research inputs changed while this strategy was generating. Regenerate against the current project before accepting; this draft is still available for reference.');
      onSaved(await post<ProjectView>('strategies', { path, title, approach, summary, receipt: result.receipt }));
    }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setSaving(false); }
  }
  return <div ref={composer} className="strategy-form proposal-dialog inline-proposal" role="region" aria-labelledby="proposal-heading" aria-describedby="proposal-help" onKeyDown={event => { if (event.key === "Escape") { event.preventDefault(); cancel(); } }}>
    <div className="proposal-heading-row"><h2 id="proposal-heading">Generate a strategy</h2><button type="button" className="text-view-link proposal-heading-generate" disabled={(!config?.available && !needsConnection) || busy || saving || ai.connecting} onClick={() => void generate()}>{busy ? cancelling ? 'Cancelling…' : ai.connecting ? 'Connecting…' : 'Generating…' : result ? 'Regenerate' : 'Generate'}</button>{result && <button type="submit" form="proposal-save-form" className="copper-button proposal-heading-save" disabled={busy || saving}>{saving ? 'Accepting…' : 'Accept'}</button>}<button type="button" className="text-view-link proposal-heading-cancel" disabled={saving || cancelling} onClick={() => void cancel()}>{busy ? cancelling ? 'Cancelling…' : "Cancel request" : "Cancel"}</button></div>
    {!busy && <p id="proposal-help" className="hint">Explore and independently challenge a candidate, then review the editable, unsaved draft before accepting.</p>}
    <p className="provider-context">{config ? `${config.mode === 'api_key' ? 'OpenAI API · billed separately' : 'Using ChatGPT plan'} · ${config.model} · ${thinkingLabels[config.reasoning_effort] ?? config.reasoning_effort}` : 'Reading AI settings…'} · call limit from this project’s settings{config?.mode === 'chatgpt' && <ManageUsage/>}</p>
    {config && !config.available && <p role="status" className="hint">{config.message}</p>}
    <details className="proposal-context" open={!result}><summary>Generation context &amp; starting point (optional)</summary>
    <label htmlFor="proposal-seed" className="sr-only">Starting point (optional)</label>
    <textarea id="proposal-seed" rows={3} maxLength={4000} value={seed} disabled={busy || saving} onChange={event => setSeed(event.target.value)} aria-describedby="seed-help"/>
    <p id="seed-help" className="hint">An optional idea or mechanism to investigate, not an assumption to accept uncritically. Leave empty for an independent research direction.</p>
    <p className="hint">Generation sends this problem, mode, all strategy titles/approaches (including removed ones), and the starting point to OpenAI. Cancelling disconnects the active run; provider usage may already count toward the selected plan or billing mode.</p>
    </details>
    {(busy || activities.length > 0 || currentActivity) && <section className="agentic-activity" aria-label="Generation progress" aria-live="polite">
      {busy && <span className="agentic-filament" aria-hidden="true"/>}
      {currentActivity && <p className="agentic-current">{currentActivity}</p>}
      {activities.length > 0 && <ol>{activities.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ol>}
    </section>}
    {review && <section className="agentic-review" aria-label="Independent review"><strong>Independent review · {review.assessment}</strong><p>{review.summary}</p><p>{review.mechanism_comparison}</p><ul>{review.objections?.map((objection, index) => <li key={index}>{objection}</li>)}</ul><p><strong>Still to establish:</strong> {review.missing_obligations}</p></section>}
    <p className="sr-only" role="status" aria-live="polite">{busy ? currentActivity || 'Generating strategy…' : ''}</p>
    <PlanWelcome/>
    {ai.connecting && <button type="button" onClick={ai.cancelSignIn}>Cancel sign-in</button>}
    {ai.handoff && <a href={ai.handoff} target="_blank" rel="noreferrer">Open sign-in browser</a>}
    {ai.error && <p role="alert" className="error">{ai.error}</p>}
    {error && <p role="alert" className="error">{error}</p>}
    <form id="proposal-save-form" onSubmit={save}>
      {result && <fieldset disabled={busy || saving} className="proposal-review">
        <legend>Unsaved draft · Review before accepting</legend>
        <label htmlFor="proposal-title">Title</label><input id="proposal-title" required maxLength={200} value={title} onChange={event => setTitle(event.target.value)}/>
        <label htmlFor="proposal-summary">Description</label><input id="proposal-summary" required maxLength={300} value={summary} onChange={event => setSummary(event.target.value)}/>
        <label htmlFor="proposal-approach">Plan</label><textarea id="proposal-approach" required maxLength={MAX_STRATEGY_APPROACH} rows={12} value={approach} onChange={event => setApproach(event.target.value)}/>
        <p className="hint">AI-assisted suggestion · {result.provenance.provider} / {result.provenance.model}{result.provenance.reasoning_effort ? ` · ${thinkingLabels[result.provenance.reasoning_effort] ?? result.provenance.reasoning_effort} thinking` : ''}. Accepting saves your edits and records your acceptance; reviewer obligations remain open as shown above.</p>
      </fieldset>}
    </form>
  </div>;
}

/** Match the existing 1.25s double heartbeat used by .research-running-indicator. */
function runningFavicon(color: 'green' | 'yellow' = 'green'): () => void {
  const existing = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  const link = existing ?? document.createElement("link");
  link.rel = "icon";
  link.type = "image/svg+xml";
  if (!existing) document.head.appendChild(link);
  const fill = color === 'yellow' ? '#ffff00' : '#55bd70';
  const border = color === 'yellow' ? '#a89e00' : '#70c889';
  const keyframes = [[0, 1, 0], [.12, 1.32, 3], [.23, 1, 0], [.32, 1.2, 2], [.42, 1, 0], [1, 1, 0]];
  const started = performance.now();
  const motion = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const draw = () => {
    const at = motion ? ((performance.now() - started) % 1250) / 1250 : 0;
    const next = keyframes.findIndex(frame => frame[0] >= at);
    const right = Math.max(next, 1);
    const left = right - 1;
    const portion = (at - keyframes[left][0]) / (keyframes[right][0] - keyframes[left][0]);
    const eased = (1 - Math.cos(Math.PI * portion)) / 2;
    const size = keyframes[left][1] + (keyframes[right][1] - keyframes[left][1]) * eased;
    const halo = keyframes[left][2] + (keyframes[right][2] - keyframes[left][2]) * eased;
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="${(4.5 * size + halo).toFixed(2)}" fill="${fill}" fill-opacity=".19"/><circle cx="12" cy="12" r="${(4.5 * size).toFixed(2)}" fill="${fill}" stroke="${border}" stroke-width="1"/></svg>`;
    link.href = `data:image/svg+xml,${encodeURIComponent(svg)}`;
  };
  draw();
  const interval = motion ? window.setInterval(draw, 80) : undefined;
  return () => {
    if (interval !== undefined) window.clearInterval(interval);
    // Never restore a stale pulsing frame after paper generation stops.
    link.href = '/favicon.svg';
  };
}

function ProjectScreen({ path, initialView, revalidateCached = false, onViewChange, onClose, goHome }: {
  path: string; initialView?: ProjectView; revalidateCached?: boolean;
  onViewChange: (view: ProjectView) => void;
  onClose: () => void;
  goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const cloud = useCloudIdentity();
  const guest = !!cloud?.enabled && (!cloud.authenticated || cloud.user?.role === 'guest');
  // Anonymous visitors may edit their isolated, expiring sandbox.
  const readOnlyGuest = false;
  const [view, setView] = useState<ProjectView | null>(initialView ?? null);
  useEffect(() => { if (view) onViewChange(view); }, [view, onViewChange]);
  const [advancedOutcomeGlobal, setAdvancedOutcomeGlobal] = useState(false);
  const [guestAdvancedOutcome, setGuestAdvancedOutcome] = useState(false);
  useEffect(() => {
    if (guest) return;
    const controller = new AbortController();
    void fetch('/api/user-preferences/research-settings', { signal: controller.signal })
      .then(response => response.ok ? response.json() : Promise.reject(new Error('User research settings unavailable')))
      .then(data => { if (!controller.signal.aborted) setAdvancedOutcomeGlobal(data.show_advanced_outcome_details === true); })
      .catch(() => { /* Keep the compact default when disconnected. */ });
    return () => controller.abort();
  }, [guest]);
  const [error, setError] = useState('');
  const [closing, setClosing] = useState(false);
  const [researchRunning, setResearchRunning] = useState(false);
  const [paperRunning, setPaperRunning] = useState(false);
  const [paperActiveRunIds, setPaperActiveRunIds] = useState<string[]>([]);
  const onPaperRunningChange = useCallback((running: boolean, runIds: string[]) => {
    setPaperRunning(running);
    setPaperActiveRunIds(current => current.join('|') === runIds.join('|') ? current : runIds);
  }, []);
  const [paperQueued, setPaperQueued] = useState(false);
  const [sharedActivity, setSharedActivity] = useState<SharedProjectInfo | null>(null);
  const [activeRuns, setActiveRuns] = useState<Array<{ kind: AttributionKind; status: 'active' | 'queued'; number?: number; id?: string; creator?: string | null; model?: string; thinking?: string }>>([]);
  // A local Stop intent takes visual precedence until a server snapshot
  // no longer advertises that run. It never mutates the collaborative ledger.
  const [optimisticStoppedRuns, setOptimisticStoppedRuns] = useState<Set<string>>(() => new Set());
  useEffect(() => {
    const onIntent = (event: Event) => {
      const detail = (event as CustomEvent<{ kind: string; id: string; clear?: boolean }>).detail;
      if (!detail?.kind || !detail?.id) return;
      const key = `${detail.kind}:${detail.id}`;
      setOptimisticStoppedRuns(current => {
        const next = new Set(current);
        if (detail.clear) next.delete(key); else next.add(key);
        return next;
      });
    };
    window.addEventListener('sigma-run-stop-intent', onIntent);
    return () => window.removeEventListener('sigma-run-stop-intent', onIntent);
  }, []);
  const visibleActiveRuns = activeRuns.filter(run => !optimisticStoppedRuns.has(`${run.kind}:${run.id ?? ''}`));
  // Stop applies to ONE run. Another paper must keep its green pulse.
  const panePaperRunning = paperActiveRunIds.length
    ? paperActiveRunIds.some(id => !optimisticStoppedRuns.has(`paper:${id}`))
    : paperRunning && ![...optimisticStoppedRuns].some(key => key.startsWith('paper:'));
  const [activityLoaded, setActivityLoaded] = useState(false);
  useEffect(() => {
    if (guest || !view) return;
    const controller = new AbortController();
    let pending = false;
    const poll = async () => {
      if (pending || controller.signal.aborted) return;
      pending = true;
      try {
        const query = new URLSearchParams({ path });
        const response = await fetch(`/api/projects/activity-runs?${query}`, {
          signal: controller.signal, cache: 'no-store',
          headers: { 'X-Sigma-Error-Handled': 'true' },
        });
        if (!response.ok) return;
        const body = await response.json() as { runs?: Array<{ kind: AttributionKind; status: 'active' | 'queued'; number?: number; id?: string; creator?: string | null; model?: string; thinking?: string }> };
        if (!controller.signal.aborted) {
          const runs = body.runs ?? [];
          setActiveRuns(runs);
          setOptimisticStoppedRuns(current => {
            const currentIds = new Set(runs.map(run => `${run.kind}:${run.id ?? ''}`));
            return new Set([...current].filter(key => currentIds.has(key)));
          });
          setActivityLoaded(true);
        }
      } catch { /* Preserve last known activity during transient failures. */ }
      finally { pending = false; }
    };
    void poll();
    const interval = window.setInterval(() => void poll(), 5000);
    return () => { controller.abort(); window.clearInterval(interval); };
  }, [path, guest, view?.project.id]);

  // Green takes precedence for color, not for which runs are disclosed.
  const activeRunLabels = visibleActiveRuns.map(run => formatRunAttribution({
    ...run,
    creator: run.creator || (run.kind === 'session'
      ? sharedActivity?.artifact_authors?.session?.[run.id ?? '']
      : run.kind === 'paper' ? sharedActivity?.artifact_authors?.paper_draft?.[view?.project.id ?? ''] : null),
    mode: 'hover',
  }));
  const lastLoadedSharedRevision = useRef<number | null>(null);
  useEffect(() => {
    if (guest) return;
    const controller = new AbortController();
    let pending = false;
    const poll = async () => {
      if (controller.signal.aborted || pending) return;
      pending = true;
      try {
        const response = await fetch(`/api/projects/collaboration?${new URLSearchParams({ path })}`, {
          headers: { 'X-Sigma-Error-Handled': 'true' },
          cache: 'no-store',
          signal: controller.signal,
        });
        if (!response.ok) throw new Error('Collaboration state unavailable');
        const value = await response.json() as SharedProjectInfo;
        if (!controller.signal.aborted) setSharedActivity(value);
      } catch {
        if (!controller.signal.aborted) setSharedActivity(null);
      } finally { pending = false; }
    };
    void poll();
    const interval = window.setInterval(() => void poll(), 5000);
    document.addEventListener('visibilitychange', poll);
    return () => {
      controller.abort();
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', poll);
    };
  }, [path, guest]);
  const [initialResearchActivity, setInitialResearchActivity] = useState<'running' | 'queued' | null>();
  const [initialPaperActivity, setInitialPaperActivity] = useState<'active' | 'queued' | null>();
  const autoRevealed = useRef(false);
  useEffect(() => {
    if (!view || autoRevealed.current || initialResearchActivity === undefined || initialPaperActivity === undefined) return;
    autoRevealed.current = true;
    const params = new URLSearchParams(window.location.search);
    // A citation/deep link takes precedence over automatic activity navigation.
    if (params.has('reveal_session') || params.has('reveal_sessions') || params.has('reveal_paper') || params.has('reveal_paper_run') || params.has('reveal_qa') || params.has('reveal_strategy') || params.has('reveal_project')) return;
    const eventName = initialResearchActivity ? 'sigma-reveal-running-session'
      : initialPaperActivity ? 'sigma-reveal-papers' : null;
    if (!eventName) return;
    const frame = requestAnimationFrame(() => requestAnimationFrame(() => window.dispatchEvent(new Event(eventName))));
    return () => cancelAnimationFrame(frame);
  }, [view?.project.id, initialResearchActivity, initialPaperActivity]);
  // Global favicon is owned by App; this project only controls its header indicator.
  const [editing, setEditing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [manualDraft, setManualDraft] = useState<{ title: string; approach: string; summary?: string }>();
  const newStrategyEditor = useRef<PaneEditorHandle>(null);
  const strategyTitleEditors = useRef<Record<string, PaneEditorHandle | null>>({});
  const [projectEditing, setProjectEditing] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [emailOpen, setEmailOpen] = useState(false);
  const [qaOpen, setQaOpen] = useState(false);
  useEffect(() => {
    if (new URLSearchParams(window.location.search).has('reveal_qa')) setQaOpen(true);
    const revealAsk = () => setQaOpen(true);
    window.addEventListener('sigma-reveal-qa', revealAsk);
    return () => window.removeEventListener('sigma-reveal-qa', revealAsk);
  }, []);
  const [leanOpen, setLeanOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [typeCatalogRevision, setTypeCatalogRevision] = useState(0);
  useEffect(() => {
    const refreshTypes = () => {
      void fetch('/api/project-types', { cache: 'no-store' }).then(response => response.ok ? response.json() : Promise.reject()).then((data: { project_types: ProjectTypeRecord[] }) => { projectTypeCache = data.project_types; setTypeCatalogRevision(value => value + 1); }).catch(() => undefined);
    };
    window.addEventListener('sigma-project-types-updated', refreshTypes);
    const controller = new AbortController();
    void fetch('/api/project-types', { signal: controller.signal }).then(response => response.ok ? response.json() : Promise.reject()).then((data: { project_types: ProjectTypeRecord[] }) => { projectTypeCache = data.project_types; setTypeCatalogRevision(value => value + 1); }).catch(() => undefined);
    return () => { controller.abort(); window.removeEventListener('sigma-project-types-updated', refreshTypes); };
  }, []);
  const modeOwner = useRef<string | null>(null);
  const [activeMode, setActiveMode] = useState<string | null>(null);
  const enterMode = useCallback((owner: string) => {
    if (modeOwner.current !== null) return false;
    modeOwner.current = owner; setActiveMode(owner); return true;
  }, []);
  const settingsDeepLinkOpened = useRef(false);
  useEffect(() => {
    if (!view || settingsDeepLinkOpened.current) return;
    const currentUrl = new URL(window.location.href);
    if (currentUrl.searchParams.get('settings') !== 'collaborators') return;
    settingsDeepLinkOpened.current = true;
    // This deep link opens Settings exactly once; refreshing must not reopen it.
    currentUrl.searchParams.delete('settings');
    window.history.replaceState(window.history.state, '', currentUrl.pathname + currentUrl.search + currentUrl.hash);
    if (enterMode('project-settings')) setProjectEditing(true);
  }, [view?.project.id, enterMode]);
  const exitMode = useCallback((owner: string) => {
    if (modeOwner.current !== owner) return;
    modeOwner.current = null; setActiveMode(null);
  }, []);
  const editProjectButton = useRef<HTMLButtonElement>(null);
  const editDescriptionButton = useRef<HTMLButtonElement>(null);
  const [descriptionEditing, setDescriptionEditing] = useState(false);
  const [descriptionBusy, setDescriptionBusy] = useState(false);
  const [descriptionDirty, setDescriptionDirty] = useState(false);
  const projectDescriptionEditor = useRef<ProjectDescriptionEditorHandle>(null);
  const [ordering, setOrdering] = useState(false);
  const [previewOrder, setPreviewOrder] = useState<string[] | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const drag = useRef<{ id: string; order: string[]; pointer: number | null } | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const [guestAiNotice, setGuestAiNotice] = useState('');
  const [guestStrategyPreview, setGuestStrategyPreview] = useState(false);
  const markLocalSharedSave = () => {
    if (sharedActivity?.shared) {
      // A successful local save is already reflected in this window's view.
      // Do not interpret its next polling revision as a remote edit.
      lastLoadedSharedRevision.current = Math.max(
        lastLoadedSharedRevision.current ?? 0, sharedActivity.revision,
      ) + 1;
    }
  };
  // Collaborators keep an open project fresh without losing local drafts or focus.
  // The existing lightweight collaboration poll supplies the revision; only a
  // changed revision triggers the more expensive project-open request.
  useEffect(() => {
    if (!sharedActivity?.shared || !view || guest) return;
    const revision = sharedActivity.revision;
    // The project may have changed before this window's first poll completed.
    // Load the authoritative title and settings even on the first response.
    if (revision === lastLoadedSharedRevision.current) return;
    // Committed changes supersede unsaved drafts in other windows.
    // Avoid interrupting an in-flight write; the backend revision fence protects it.
    if (closing || descriptionBusy || ordering) return;
    const controller = new AbortController();
    void post<ProjectView>('open', { path, compact: true }, controller.signal)
      .then(next => {
        if (controller.signal.aborted) return;
        // The first collaboration response establishes the revision baseline.
        // Only interrupt an already-open editor when the persisted project
        // actually differs from what this window loaded.
        // Execution receipts and history events are not edits to the Project
        // description. Ignore them entirely rather than cancelling a draft.
        const { events: _oldEvents, backend_build_commit: _oldBuild, ...before } = view.project;
        const { events: _newEvents, backend_build_commit: _newBuild, ...after } = next.project;
        if (JSON.stringify(before) === JSON.stringify(after)) {
          lastLoadedSharedRevision.current = revision;
          return;
        }
        // Research fields are edited transactionally. An incoming change
        // must never discard keystrokes or close the editor; Save checks the
        // actual authored baseline and reports a genuine conflict instead.
        if (descriptionEditing) {
          lastLoadedSharedRevision.current = revision;
          setAnnouncement('The project changed while you were editing. Your draft is preserved; Save checks for conflicts.');
          return;
        }
        // Classification controls can refresh in place.
        if (!projectEditing) {
          modeOwner.current = null;
          setActiveMode(null);
          setDescriptionEditing(false);
          setDescriptionDirty(false);
          setEditing(false);
          setGenerating(false);
          setManualDraft(undefined);
          setCombinedTextDrafts({});
          setTextEditSignals({});
          setEditorVersion(value => value + 1);
        }
        setView(next);
        lastLoadedSharedRevision.current = revision;
        setAnnouncement(projectEditing
          ? 'Project Settings refreshed with collaborator changes.'
          : 'Project updated by a collaborator. Unsaved edits were discarded.');
      })
      .catch(() => { /* Retain the current view and retry on the next poll. */ });
    return () => controller.abort();
  }, [sharedActivity, view?.project.id, guest,
      activeMode, editing, generating, projectEditing, descriptionEditing,
      descriptionDirty, ordering, dragId, manualDraft, closing, path]);

  const [editorVersion, setEditorVersion] = useState(0);
  const [focusStrategy, setFocusStrategy] = useState('');
  const citationRevealHandled = useRef(false);
  const [strategiesExpanded, setStrategiesExpanded] = useState(() => window.localStorage.getItem(`sigma.strategiesPane:${path}`) !== 'false');
  const [collapsedStrategies, setCollapsedStrategies] = useState<Set<string>>(() => new Set());
  const [textEditSignals, setTextEditSignals] = useState<Record<string, number>>({});
  const [combinedTextDrafts, setCombinedTextDrafts] = useState<Record<string, string>>({});
  const requestTextEdit = (key: string) => setTextEditSignals(current => ({ ...current, [key]: (current[key] ?? 0) + 1 }));
  const updateCombinedTextDraft = (key: string, draft: string) => setCombinedTextDrafts(current => ({ ...current, [key]: draft }));
  const [projectExpanded, setProjectExpanded] = useState(() => window.localStorage.getItem(`sigma.projectPane:${path}`) !== 'false');
  const [exclusiveSections, setExclusiveSections] = useState(false);
  const sectionOpen = useCallback((section: 'project' | 'strategies' | 'sessions' | 'papers') => {
    if (exclusiveSections) window.dispatchEvent(new CustomEvent('sigma-project-section-opened', { detail: section }));
  }, [exclusiveSections]);
  // Collapse is a commit boundary for authored Project and Strategies fields.
  // Never hide a failing editor or leave its mode lock active behind a closed pane.
  async function collapseProjectPane(): Promise<boolean> {
    if (descriptionEditing && !(await projectDescriptionEditor.current?.saveBeforeCollapse())) return false;
    setProjectExpanded(false);
    window.localStorage.setItem(`sigma.projectPane:${path}`, 'false');
    return true;
  }
  async function collapseStrategiesPane(): Promise<boolean> {
    if (editing && !(await newStrategyEditor.current?.saveBeforeCollapse())) return false;
    const strategyTitleId = modeOwner.current?.startsWith('strategy-title-')
      ? modeOwner.current.slice('strategy-title-'.length) : null;
    if (strategyTitleId && !(await strategyTitleEditors.current[strategyTitleId]?.saveBeforeCollapse())) return false;
    setStrategiesExpanded(false);
    window.localStorage.setItem(`sigma.strategiesPane:${path}`, 'false');
    return true;
  }
  useEffect(() => {
    // Error-card Source Material links can originate from a collapsed Sessions
    // pane. Reveal Project even in the exclusive-one-section layout.
    const reveal = () => {
      sectionOpen('project');
      setProjectExpanded(true);
      window.localStorage.setItem(`sigma.projectPane:${path}`, 'true');
    };
    window.addEventListener('sigma-reveal-source-material', reveal);
    return () => window.removeEventListener('sigma-reveal-source-material', reveal);
  }, [path, sectionOpen]);
  useEffect(() => {
    const opened = (event: Event) => {
      const section = (event as CustomEvent<string>).detail;
      if (section !== 'project') void collapseProjectPane();
      if (section !== 'strategies') void collapseStrategiesPane();
    };
    window.addEventListener('sigma-project-section-opened', opened);
    return () => window.removeEventListener('sigma-project-section-opened', opened);
  }, [path, descriptionEditing, editing, activeMode]);
  useEffect(() => {
    if (guest) return;
    const controller = new AbortController();
    void fetch('/api/user-preferences/section-layout', { signal: controller.signal, headers: { 'X-Sigma-Error-Handled': 'true' } })
      .then(async response => {
        if (!response.ok) throw new Error('Section layout preferences could not be loaded.');
        const data = await response.json();
        if (typeof data.expand_one_project_section_at_a_time !== 'boolean') throw new Error('Invalid section layout preference.');
        if (controller.signal.aborted) return;
        setExclusiveSections(data.expand_one_project_section_at_a_time);
        if (data.expand_one_project_section_at_a_time) {
          const params = new URLSearchParams(window.location.search);
          const initialSection = params.has('reveal_session') || params.has('reveal_understanding') ? 'sessions' : params.has('reveal_paper') ? 'papers' : params.has('reveal_strategy') ? 'strategies' : 'project';
          window.dispatchEvent(new CustomEvent('sigma-project-section-opened', { detail: initialSection }));
        }
      }).catch(cause => { if (!controller.signal.aborted) console.warn('Section layout preference unavailable', errorMessage(cause)); });
    return () => controller.abort();
  }, [guest, path]);
  useEffect(() => {
    const changed = (event: Event) => {
      const enabled = (event as CustomEvent<boolean>).detail === true;
      setExclusiveSections(enabled);
      if (enabled) window.dispatchEvent(new CustomEvent('sigma-project-section-opened', { detail: 'project' }));
    };
    window.addEventListener('sigma-section-layout-preference-changed', changed);
    return () => window.removeEventListener('sigma-section-layout-preference-changed', changed);
  }, []);
  const [processControls, setProcessControls] = useState<ProcessControls>({ play: () => {}, stop: () => {}, playDisabled: true, stopDisabled: true, playLabel: 'Start a new research session' });
  const [guestPlayOpen, setGuestPlayOpen] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  const playButton = useRef<HTMLButtonElement>(null);
  const resumedPlay = useRef(false);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlPlayIntent = params.get('resume_play') === '1';
    // Following a progress email is view-only, even if another tab previously
    // left a guest Play intent in session storage.
    if (params.has('reveal_session') || params.has('reveal_paper')) return;
    if (
      resumedPlay.current
      || !view
      || !cloud?.authenticated
      || processControls.playDisabled
      || (!urlPlayIntent && window.sessionStorage.getItem('sigma.resumeGuestPlay') !== 'true')
    ) return;
    resumedPlay.current = true;
    window.sessionStorage.removeItem('sigma.resumeGuestPlay');
    if (urlPlayIntent) {
      params.delete('resume_play');
      const query = params.toString();
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`);
    }
    processControls.play();
  }, [cloud?.authenticated, processControls.play, processControls.playDisabled, view?.project.id]);
  useEffect(() => {
    const openAbout = () => setAboutOpen(true);
    window.addEventListener('sigma-open-about', openAbout);
    const params = new URLSearchParams(window.location.search);
    if (params.get('show_about') === '1') {
      setAboutOpen(true);
      params.delete('show_about');
      const query = params.toString();
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`);
    }
    return () => window.removeEventListener('sigma-open-about', openAbout);
  }, []);
  useEffect(() => {
    if (initialView) return;
    const controller = new AbortController();
    post<ProjectView>('open', { path, compact: true }, controller.signal).then(setView).catch(error => {
      if (!controller.signal.aborted) setError(errorMessage(error));
    });
    return () => controller.abort();
  }, [path, initialView]);
  useEffect(() => {
    if (!initialView || !revalidateCached) return;
    const controller = new AbortController();
    void post<ProjectView>('open', { path, compact: true }, controller.signal).then(fresh => {
      if (!controller.signal.aborted) {
        // Do not overwrite a user edit completed while refresh was in flight.
        setView(current => current === initialView ? fresh : current);
      }
    }).catch(cause => {
      if (!controller.signal.aborted) {
        // A revoked or missing project must not continue to use a stale view.
        setView(null);
        setError(errorMessage(cause));
      }
    });
    return () => controller.abort();
  }, [path, initialView, revalidateCached]);
  useEffect(() => {
    if (view) document.title = `${view.project.title} · SIGMA`;
    else if (error) document.title = 'Project unavailable · SIGMA';
    heading.current?.focus();
  }, [view?.project.id, !!error]);
  useEffect(() => {
    if (!focusStrategy || !strategiesExpanded) return;
    const target = document.getElementById(`strategy-${focusStrategy}`);
    requestAnimationFrame(() => { target?.scrollIntoView({ block: 'center', behavior: 'smooth' }); target?.focus(); });
  }, [focusStrategy, strategiesExpanded]);
  useEffect(() => {
    if (!dragId) return;
    function pointerMove(event: PointerEvent) {
      if (drag.current?.pointer !== event.pointerId) return;
      event.preventDefault();
      const activeId = drag.current.id;
      const rows = Array.from(document.querySelectorAll<HTMLElement>('.strategy-row'))
        .filter(row => row.dataset.strategyId !== activeId);
      const before = rows.find(row => {
        const rect = row.getBoundingClientRect();
        return event.clientY < rect.top + rect.height / 2;
      });
      moveBefore(before?.dataset.strategyId ?? null);
      if (event.clientY > window.innerHeight - 60) window.scrollBy(0, 16);
      if (event.clientY < 60) window.scrollBy(0, -16);
    }
    function pointerUp(event: PointerEvent) { if (drag.current?.pointer === event.pointerId) void drop(); }
    function pointerCancel(event: PointerEvent) { if (drag.current?.pointer === event.pointerId) cancelDrag(); }
    function escape(event: KeyboardEvent) { if (event.key === 'Escape') { event.preventDefault(); const id = drag.current?.id; cancelDrag(); if (id) document.getElementById(`grip-${id}`)?.focus(); } }
    // Document listeners survive DOM relocation of the captured grip during touch sorting.
    document.addEventListener('pointermove', pointerMove, { passive: false });
    document.addEventListener('pointerup', pointerUp);
    document.addEventListener('pointercancel', pointerCancel);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointermove', pointerMove); document.removeEventListener('pointerup', pointerUp); document.removeEventListener('pointercancel', pointerCancel); document.removeEventListener('keydown', escape); };
  }, [dragId, view]);
  async function close() {
    setClosing(true); setError('');
    try { await post('close'); onClose(); }
    catch (error) { setError(errorMessage(error)); setClosing(false); }
  }
  const frame = {
    goHome, close: { action: close, busy: closing }, connectionDisabled: activeMode !== null,
    // A queued Session still belongs to Sessions when clicking the activity title.
    // Color is decided separately from the authoritative active/queued run list.
    researchRunning: (researchRunning && ![...optimisticStoppedRuns].some(key => key.startsWith('session:'))) || visibleActiveRuns.some(run => run.kind === 'session'),
    paperRunning: panePaperRunning || visibleActiveRuns.some(run => run.kind === 'paper' && run.status === 'active'),
    paperQueued: (paperQueued && ![...optimisticStoppedRuns].some(key => key.startsWith('paper:'))) || visibleActiveRuns.some(run => run.kind === 'paper' && run.status === 'queued'),
    askRunning: visibleActiveRuns.some(run => run.kind === 'answer' && run.status === 'active'),
    activeRunLabels,
    // Local-only Papers or mock runs can be active without a shared reservation.
    // The ledger is authoritative when populated, but an empty ledger must
    // not conceal activity the underlying panes still report.
    activityStatus: !activityLoaded || (!activeRuns.length && !optimisticStoppedRuns.size) ? undefined
      : visibleActiveRuns.some(run => run.status === 'active') ||
        (panePaperRunning || (researchRunning && ![...optimisticStoppedRuns].some(key =>
          key.startsWith('session:')))) ? 'active' as const
      : visibleActiveRuns.some(run => run.status === 'queued') || paperQueued ? 'queued' as const : null,
    onIdleProjectTitleClick: toggleSectionsFromTitle,
    onActivityClick: () => {
      const run = visibleActiveRuns.find(item => item.status === 'active' && item.kind === 'session')
        ?? visibleActiveRuns.find(item => item.status === 'active' && item.kind === 'paper')
        ?? visibleActiveRuns.find(item => item.kind === 'session')
        ?? visibleActiveRuns.find(item => item.kind === 'paper')
        ?? visibleActiveRuns[0];
      if (run?.kind === 'session') window.dispatchEvent(new CustomEvent('sigma-reveal-running-session', { detail: run.id }));
      else if (run?.kind === 'paper') window.dispatchEvent(new CustomEvent('sigma-reveal-papers', { detail: run.id }));
      else if (run?.kind === 'answer') window.dispatchEvent(new Event('sigma-reveal-qa'));
      else window.dispatchEvent(new Event(researchRunning ? 'sigma-reveal-running-session' : paperRunning || paperQueued ? 'sigma-reveal-papers' : 'sigma-reveal-qa'));
    },
  };
  function toggleStrategiesPane() {
    if (strategiesExpanded) {
      void collapseStrategiesPane();
    } else {
      sectionOpen('strategies');
      setStrategiesExpanded(true);
      window.localStorage.setItem(`sigma.strategiesPane:${path}`, 'true');
    }
  }
  function showStrategy(id: string) {
    sectionOpen('strategies');
    setCollapsedStrategies(current => { const next = new Set(current); next.delete(id); return next; });
    if (!strategiesExpanded) {
      setStrategiesExpanded(true);
      window.localStorage.setItem(`sigma.strategiesPane:${path}`, 'true');
    }
    if (id) setFocusStrategy(id);
  }
  useEffect(() => {
    if (!view || citationRevealHandled.current) return;
    const params = new URLSearchParams(window.location.search);
    const strategyId = params.get('reveal_strategy');
    if (strategyId && view.project.strategies.some(strategy => strategy.id === strategyId && !strategy.removed_at)) {
      citationRevealHandled.current = true;
      showStrategy(strategyId);
      return;
    }
    if (params.get('reveal_project') === '1') {
      citationRevealHandled.current = true;
      sectionOpen('project');
      setProjectExpanded(true);
      window.localStorage.setItem(`sigma.projectPane:${path}`, 'true');
      requestAnimationFrame(() => requestAnimationFrame(() => {
        const target = document.querySelector<HTMLElement>('.project-overview-card');
        target?.scrollIntoView({ block: 'center', behavior: 'smooth' });
        target?.classList.add('citation-highlight');
        window.setTimeout(() => target?.classList.remove('citation-highlight'), 2400);
      }));
    }
  }, [view?.project.id, path]);
  function cancel() { setEditing(false); exitMode('new-strategy'); requestAnimationFrame(() => newButton.current?.focus()); }
  function toggleSectionsFromTitle() {
    const sections = ['project-pane-heading', 'pool-heading', 'sessions-heading', 'papers-heading'];
    const allCollapsed = sections.every(id => document.querySelector(`#${id} .workspace-section-disclosure`)?.getAttribute('aria-expanded') === 'false');
    if (!allCollapsed) {
      window.dispatchEvent(new CustomEvent('sigma-project-section-opened', { detail: 'all' }));
      return;
    }
    sectionOpen('project');
    setProjectExpanded(true);
    window.localStorage.setItem(`sigma.projectPane:${path}`, 'true');
    requestAnimationFrame(() => requestAnimationFrame(() => focusWorkspace('project-pane-heading')));
  }
  function expandStrategies() { sectionOpen('strategies'); setStrategiesExpanded(true); window.localStorage.setItem(`sigma.strategiesPane:${path}`, 'true'); }
  const collapseProjectAndStrategies = useCallback(() => {
    sectionOpen('sessions');
    setProjectExpanded(false);
    setStrategiesExpanded(false);
    window.localStorage.setItem(`sigma.projectPane:${path}`, 'false');
    window.localStorage.setItem(`sigma.strategiesPane:${path}`, 'false');
  }, [path, sectionOpen]);
  function startNewStrategy() {
    if (!enterMode('new-strategy')) return;
    expandStrategies(); setManualDraft(undefined); setEditing(true);
    requestAnimationFrame(() => document.getElementById('strategy-title')?.focus());
  }
  function startGeneration() {
    if (modeOwner.current !== null || generating) return;
    expandStrategies(); setGenerating(true);
    requestAnimationFrame(() => document.getElementById('proposal-seed')?.focus());
  }
  function closeAbout() {
    setAboutOpen(false);
    requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('button.about-action[aria-label="About SIGMA"]')?.focus());
  }
  const strategies = useMemo(() => {
    if (!view) return [];
    const project = view.project;
    const byId = new Map(project.strategies.map(strategy => [strategy.id, strategy]));
    return (previewOrder ?? project.active_order).map(id => byId.get(id)!);
  }, [view, previewOrder]);
  if (!view) return <WorkspaceFrame {...frame}><div className="workspace-state" aria-live="polite">{error ? <>
    <h1 ref={heading} tabIndex={-1}>Project unavailable</h1><p role="alert" className="error">{error}</p>
    <p>Close this project to choose another directory.</p>
  </> : <p className="intro">Opening project…</p>}</div></WorkspaceFrame>;
  const project = view.project;
  const headingStrategies = project.strategies.filter(strategy => !strategy.removed_at);
  const headingDisabledCount = headingStrategies.filter(strategy => !strategy.enabled).length;
  void typeCatalogRevision;
  const savedTypeSnapshot = project.project_type_snapshot;
  const missingProjectType = !projectTypeCache.some(item => item.id === project.investigation_type);
  const safeSavedTypeSettings = !!savedTypeSnapshot && savedTypeSnapshot.id === project.investigation_type && !!savedTypeSnapshot.name.trim() && !!savedTypeSnapshot.scope.trim() && ['builtin', 'data'].includes(savedTypeSnapshot.icon.kind);
  const byId = new Map(project.strategies.map(strategy => [strategy.id, strategy]));
  function forkFromFindings(session: ResearchSession) {
    if (!enterMode('new-strategy')) return;
    const parent = byId.get(session.strategy_id);
    const parentApproach = session.strategy_text ?? parent?.approach ?? '';
    const evidence = session.artifacts.slice(-3).map(artifact => [
      `Artifact ${artifact.sequence}: ${artifact.claim_or_question}`,
      `Skeptic objections: ${artifact.objections.join(' · ') || 'None recorded'}`,
      `Open obligations: ${artifact.open_obligations.join(' · ') || 'None recorded'}`,
      `Coordinator decision: ${artifact.coordinator_decision}`,
      `Next question: ${artifact.next_question || 'None recorded'}`,
    ].join('\n')).join('\n\n');
    const prefix = [
      `Fork rationale: derived from strategy “${session.strategy_title}” (ID ${session.strategy_id}) after Research Session ${session.session_number}.`,
      'Use the findings below to revise the approach. Preserve unresolved obligations as open work; treat model notes as unverified.',
      evidence ? `\nSaved findings and criticism:\n${evidence}` : '',
      '\nParent approach follows:',
    ].filter(Boolean).join('\n');
    const available = Math.max(0, MAX_STRATEGY_APPROACH - prefix.length - 120);
    const clippedParent = parentApproach.slice(0, available);
    const approach = `${prefix}\n${clippedParent}${parentApproach.length > clippedParent.length ? '\n[Parent approach shortened to fit; see the source session for the complete strategy.]' : ''}`.slice(0, MAX_STRATEGY_APPROACH);
    setManualDraft({
      title: `${session.strategy_title} (Session ${session.session_number} fork)`.slice(0, 200),
      summary: `Fork of ${session.strategy_title} informed by Session ${session.session_number}`.slice(0, 300),
      approach,
    });
    expandStrategies(); setEditing(true);
    requestAnimationFrame(() => document.getElementById('strategy-title')?.focus());
  }
  function pickup(id: string, pointer: number | null) {
    if (ordering || drag.current) return;
    drag.current = { id, order: [...project.active_order], pointer }; setDragId(id);
    setPreviewOrder([...project.active_order]);
    setAnnouncement(`Picked up ${byId.get(id)!.title}. Arrow keys move, Enter drops, Escape cancels.`);
  }
  function moveTo(index: number) {
    const active = drag.current; if (!active) return;
    const order = [...active.order]; const old = order.indexOf(active.id);
    const target = Math.max(0, Math.min(order.length - 1, index));
    order.splice(old, 1); order.splice(target, 0, active.id);
    if (order.every((id, position) => id === active.order[position])) return;
    active.order = order; setPreviewOrder(order);
    setAnnouncement(`Position ${target + 1} of ${order.length}.`);
  }
  function moveBefore(targetId: string | null) {
    const active = drag.current; if (!active) return;
    const order = active.order.filter(id => id !== active.id);
    const target = targetId ? order.indexOf(targetId) : order.length;
    order.splice(Math.max(0, target), 0, active.id);
    if (order.every((id, position) => id === active.order[position])) return;
    active.order = order; setPreviewOrder(order);
    setAnnouncement(`Position ${order.indexOf(active.id) + 1} of ${order.length}.`);
  }
  function cancelDrag() {
    drag.current = null; setDragId(null); setPreviewOrder(null); setAnnouncement('Reorder cancelled.');
  }
  async function drop() {
    const active = drag.current; if (!active) return;
    drag.current = null; setDragId(null);
    if (active.order.join() === project.active_order.join()) { setPreviewOrder(null); setAnnouncement('Order unchanged.'); return; }
    setOrdering(true); setError('');
    try {
      setView(await post<ProjectView>('strategies/reorder', { path: view!.path, order: active.order, expected_order: project.active_order }));
      setAnnouncement('Strategy order updated.');
    } catch (error) { setError(errorMessage(error)); setAnnouncement('Order save failed. Previous order restored.'); }
    finally { setOrdering(false); setPreviewOrder(null); requestAnimationFrame(() => document.getElementById(`grip-${active.id}`)?.focus()); }
  }
  const projectActionBar = <div className="project-primary-actions">
    <div className="project-pane-actions">
      {descriptionEditing ? <>
        <button type="submit" form="sigma-project-description-form"
          className="text-view-link sigma-description-toolbar-action" disabled={descriptionBusy || !descriptionDirty}>
          {descriptionBusy ? 'Saving…' : 'Save'}
        </button>
        <button type="button" className="text-view-link sigma-description-toolbar-action"
          disabled={descriptionBusy} onClick={() => {
            setDescriptionEditing(false);
            setDescriptionDirty(false);
            exitMode('project-title');
            requestAnimationFrame(() => editDescriptionButton.current?.focus());
          }}>Cancel</button>
      </> : <button ref={editDescriptionButton} type="button"
        className="text-view-link text-view-icon workspace-icon-button sigma-heading-icon-action project-description-toolbar-edit"
        aria-label="Edit project fields" data-tooltip="Edit project fields"
        disabled={readOnlyGuest || closing || ordering || !!dragId || activeMode !== null}
        onClick={() => {
          if (!enterMode('project-title')) return;
          sectionOpen('project');
          setProjectExpanded(true);
          window.localStorage.setItem(`sigma.projectPane:${path}`, 'true');
          setDescriptionDirty(false);
          setDescriptionEditing(true);
        }}>
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
          <path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/>
        </svg>
      </button>}
      <button type="button" className="text-view-link text-view-icon project-qa-button" aria-label="Research Q/A" data-tooltip="Ask about project research" disabled={closing || ordering || !!dragId || activeMode !== null} onClick={() => setQaOpen(true)}>Q/A</button>
      {project.investigation_type === 'mathematical' && <button type="button" className="text-view-link text-view-icon project-lean-button" aria-label="Lean proof verification" data-tooltip="Lean proof verification" disabled={closing || ordering || !!dragId || activeMode !== null} onClick={() => setLeanOpen(true)}><img src="/lean-logo.svg" alt="" aria-hidden="true"/></button>}
      <button type="button" className="text-view-link text-view-icon project-download-button" aria-label="Export project" data-tooltip="Export project" disabled={closing || ordering || !!dragId || activeMode !== null} onClick={() => setExportOpen(true)}>
        <svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>
      </button>
      <button type="button" className="text-view-link text-view-icon project-email-button" aria-label="Email project" data-tooltip="Email project with attachments" disabled={closing || ordering || !!dragId || guest || activeMode !== null} onClick={() => setEmailOpen(true)}>
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 5.5h13v11H3zM3.4 6l6.1 5 6.1-5"/>
          <path d="M18 8.5v7.25a2.75 2.75 0 0 1-5.5 0v-5a1.4 1.4 0 0 1 2.8 0v4.75"/>
        </svg>
      </button>
      <button ref={editProjectButton} type="button" className="text-view-link text-view-icon workspace-icon-button sigma-heading-icon-action project-classification-settings-button" aria-label="Project settings" data-tooltip="Project settings" disabled={readOnlyGuest || closing || ordering || !!dragId || activeMode !== null} onClick={() => { if (enterMode('project-settings')) setProjectEditing(true); }}>
        <SlidersSettingsIcon/>
      </button>

    </div>
  </div>;
  return <WorkspaceFrame {...frame} projectTitle={project.title} projectType={project.investigation_type} projectView={view!} onProjectUpdated={setView} >
    <section className="workspace-pane project-pane" aria-labelledby="project-pane-heading">
      <header className="workspace-pane-heading project-pane-heading">
        <h2 id="project-pane-heading" ref={heading} tabIndex={-1}>
          <button type="button" className="workspace-section-disclosure" aria-expanded={projectExpanded} aria-controls="project-pane-content" data-tooltip={`${projectExpanded ? 'Collapse' : 'Expand'} Project section`} onClick={() => { if (projectExpanded) void collapseProjectPane(); else { sectionOpen('project'); setProjectExpanded(true); window.localStorage.setItem(`sigma.projectPane:${path}`, 'true'); } }}>
            <DisclosureChevron expanded={projectExpanded}/>Project
          </button>
        </h2>
        {projectActionBar}
      </header>
      <div id="project-pane-content" hidden={!projectExpanded}>
      {missingProjectType && <div className="project-type-missing-warning" role="status"><strong>Project type unavailable</strong><p>This project was created with “{savedTypeSnapshot?.name ?? project.investigation_type}”, which is no longer available. Its existing settings and icon are preserved. Choose a replacement in Project Settings to use a current type.</p><button type="button" onClick={() => { if (enterMode('project-settings')) setProjectEditing(true); }}>Choose replacement</button></div>}
      <div className="project-overview-card">
      <div className="project-description-columns"><span>TITLE</span></div>
      <ProjectDescriptionEditor ref={projectDescriptionEditor} view={view} guest={guest} collaborationRevision={sharedActivity?.shared ? sharedActivity.revision : undefined}
        editing={descriptionEditing} busy={descriptionBusy}
        canEditTitle={!sharedActivity?.owner || sharedActivity.owner === sharedActivity.you}
        onBusyChange={setDescriptionBusy}
        onDirtyChange={setDescriptionDirty}
        onExitMode={() => {
          setDescriptionEditing(false);
          setDescriptionDirty(false);
          exitMode('project-title');
          requestAnimationFrame(() => editDescriptionButton.current?.focus());
        }}
        onSave={async (draft: ProjectDescriptionDraft) => {
          const current = settingsOf(view);
          // Authored fields have a short document transaction, independent of
          // the current Paper/Session lease. The backend checks the prior
          // field values, so genuine simultaneous edits are still rejected.
          const next = await post<ProjectView>('description', {
            path: view.path, ...current, ...draft, expected: current,
          });
          markLocalSharedSave();
          setView(next);
          // The parent owns the toolbar mode: a successful save must return
          // to the pencil even if the updated view re-renders the editor.
          setDescriptionEditing(false);
          setDescriptionDirty(false);
          exitMode('project-title');
          requestAnimationFrame(() => editDescriptionButton.current?.focus());
        }}/>
      </div>
      </div>
    </section>
    {error && <p role="alert" className="error">{error}</p>}
    <section className={`pool workspace-pane strategies-pane${strategiesExpanded ? '' : ' is-collapsed'}`} aria-labelledby="pool-heading">
      <header className="pool-heading workspace-pane-heading strategies-pane-heading">
        <h2 id="pool-heading" tabIndex={-1}><button type="button" className="workspace-section-disclosure" data-tooltip={`${strategiesExpanded ? 'Collapse' : 'Expand'} Strategies section`} aria-expanded={strategiesExpanded} aria-controls="strategies-pane-content" onClick={toggleStrategiesPane}><DisclosureChevron expanded={strategiesExpanded}/>Strategies</button></h2>
        <div className="strategies-heading-right">
          <StrategyCreationActions buttonRef={newButton} hideNew={generating} disabled={activeMode !== null || generating || closing || ordering || !!dragId || !!processControls.confirming} onManual={() => startNewStrategy()} onAI={() => { if (guest) setGuestStrategyPreview(true); else startGeneration(); }}/>
          <p className="section-count">{headingStrategies.length} strateg{headingStrategies.length === 1 ? 'y' : 'ies'}{headingDisabledCount > 0 ? `, ${headingDisabledCount} disabled` : ''}</p>
        </div>
      </header>
      {guestAiNotice && <p className="hint guest-ai-notice" role="status">{guestAiNotice}</p>}
      <div id="strategies-pane-content" hidden={!strategiesExpanded}>
      <p className="sr-only" role="status">{announcement}</p>
      <div id="strategy-composer">{editing && <NewStrategy ref={newStrategyEditor} initialDraft={manualDraft} path={view.path} onCancel={cancel} onSaved={next => {
        const strategy = next.project.strategies[next.project.strategies.length - 1];
        setView(next); setEditing(false); exitMode('new-strategy'); setAnnouncement(`Strategy added: ${strategy.title}`);
        setFocusStrategy(strategy.id);
      }}/>}
      {generating && <GenerateStrategy path={view.path} projectId={view.project.id} sourceGuard={JSON.stringify({ project_id: project.id, problem: project.problem, strategies: project.strategies.map(item => [item.id, item.title, item.approach, item.removed_at]) })} onCancel={() => { setGenerating(false); requestAnimationFrame(() => newButton.current?.focus()); }} onSaved={next => {
        const strategy = next.project.strategies.at(-1)!; setView(next); setGenerating(false); setFocusStrategy(strategy.id); setAnnouncement('AI-assisted strategy accepted.');
      }}/>}</div>
      {strategies.length ? <div className="strategies-table">
        <div className="strategy-columns" aria-hidden="true"><span>Strategy</span></div>
        <ol className="strategy-list" aria-label="Strategies" aria-busy={ordering}>
        {strategies.map(strategy => <li className={`strategy-row${strategies.length === 1 ? ' is-only-strategy' : ''}${!strategy.enabled ? ' is-disabled' : ''}${dragId === strategy.id ? ' is-lifted' : ''}`} key={strategy.id} data-strategy-id={strategy.id}>
          <div className="strategy-row-main">
            <StrategyTitleEditor ref={instance => { strategyTitleEditors.current[strategy.id] = instance; }} key={`${strategy.id}:${editorVersion}`} authorEmail={sharedActivity?.shared ? sharedActivity.artifact_authors?.strategy?.[strategy.id] : undefined} strategy={strategy} path={view.path} onSaved={setView} modeDisabled={readOnlyGuest || (activeMode !== null && activeMode !== `strategy-title-${strategy.id}`)} descriptionDraft={combinedTextDrafts[`strategy:${strategy.id}`] ?? strategy.approach} onEnterMode={() => enterMode(`strategy-title-${strategy.id}`)} onExitMode={() => exitMode(`strategy-title-${strategy.id}`)} onEditDescription={() => requestTextEdit(`strategy:${strategy.id}`)} expanded={!collapsedStrategies.has(strategy.id)} onToggle={() => setCollapsedStrategies(current => { const next = new Set(current); if (next.has(strategy.id)) next.delete(strategy.id); else next.add(strategy.id); return next; })} commands={<StrategyCommands strategy={strategy} disabled={readOnlyGuest || activeMode !== null || processControls.confirming} onCommand={(mode, strategy) => {
              if (readOnlyGuest || ordering || dragId || activeMode !== null || processControls.confirming) return;
              if (mode === 'toggle') {
                const owner = `strategy-toggle-${strategy.id}`;
                if (!enterMode(owner)) return;
                void post<ProjectView>('strategies/enabled', { path: view.path, strategy_id: strategy.id, enabled: !strategy.enabled })
                  .then(next => { setView(next); setAnnouncement(`${strategy.title} ${strategy.enabled ? 'disabled' : 'enabled'}.`); })
                  .catch(cause => { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); })
                  .finally(() => exitMode(owner));
                return;
              }
              if (mode === 'fork') {
                if (!enterMode('new-strategy')) return;
                expandStrategies(); setManualDraft({ title: `${strategy.title} (forked)`, approach: strategy.approach, summary: strategy.summary }); setEditing(true);
                requestAnimationFrame(() => document.getElementById('strategy-composer')?.scrollIntoView({ block: 'nearest' }));
                return;
              }
              const owner = `strategy-remove-${strategy.id}`;
              if (!enterMode(owner)) return;
              void post<ProjectView>('strategies/remove', { path: view.path, strategy_id: strategy.id })
                .then(next => {
                  setView(next); setAnnouncement(`Removed ${strategy.title} from Strategies. History retained.`);
                  requestAnimationFrame(() => document.getElementById('pool-heading')?.focus());
                })
                .catch(cause => { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); })
                .finally(() => exitMode(owner));
            }}/>} />
            <div id={`strategy-content-${strategy.id}`} className="strategy-expanded" hidden={collapsedStrategies.has(strategy.id)}><LazyViewport force={strategy.id === strategies[0]?.id || activeMode === `strategy-title-${strategy.id}` || (textEditSignals[`strategy:${strategy.id}`] ?? 0) > 0} fallback={<div className="strategy-approach" style={{ whiteSpace: 'pre-wrap' }}>{strategy.approach}</div>}><TextViews key={`${strategy.id}:${editorVersion}`} guest={readOnlyGuest} aiGuest={guest} mathematical={project.investigation_type === 'mathematical'} path={view.path} scope="strategy" strategyId={strategy.id} source={strategy.approach} contentClass="strategy-approach" onSaved={setView} hideEditAction markdownSlotId={`strategy-markdown-slot-${strategy.id}`} editSignal={textEditSignals[`strategy:${strategy.id}`] ?? 0} combinedEditMode={activeMode === `strategy-title-${strategy.id}`} onCombinedDraftChange={draft => updateCombinedTextDraft(`strategy:${strategy.id}`, draft)} modeDisabled={readOnlyGuest || (activeMode !== null && activeMode !== `text-strategy-${strategy.id}` && activeMode !== `strategy-title-${strategy.id}`)} onEnterMode={() => enterMode(`text-strategy-${strategy.id}`)} onExitMode={() => exitMode(`text-strategy-${strategy.id}`)}/></LazyViewport></div>
          </div>
          {strategies.length > 1 && <button id={`grip-${strategy.id}`} className="drag-grip" disabled={readOnlyGuest || ordering || closing}
            aria-label={`Reorder ${strategy.title}`} data-tooltip={`Drag to reorder ${strategy.title}`} aria-describedby="reorder-help" aria-pressed={dragId === strategy.id}
            onPointerDown={event => { if (event.button !== 0) return; event.preventDefault(); event.currentTarget.focus(); pickup(strategy.id, event.pointerId); event.currentTarget.setPointerCapture(event.pointerId); }}
            onKeyDown={event => { if (event.key === 'Escape' && drag.current) { event.preventDefault(); cancelDrag(); }
              else if (event.key === ' ' && !drag.current) { event.preventDefault(); pickup(strategy.id, null); }
              else if (drag.current?.id === strategy.id && ['ArrowUp', 'ArrowDown', 'Enter', ' '].includes(event.key)) { event.preventDefault();
                if (event.key === 'ArrowUp' || event.key === 'ArrowDown') moveTo(drag.current.order.indexOf(strategy.id) + (event.key === 'ArrowUp' ? -1 : 1)); else void drop();
              } }}><svg width="12" height="16" viewBox="0 0 12 16" fill="currentColor" aria-hidden="true">{[3,7,11].flatMap(y => [3,7].map(x => <circle key={`${x}-${y}`} cx={x} cy={y} r="1"/>))}</svg></button>}
        </li>)}
      </ol></div> : !editing && <p className="pool-empty">No strategies yet.</p>}
      {(dragId || ordering) && <p className="reorder-feedback">{ordering ? 'Saving order…' : 'Moving strategy · Release or press Enter to save · Escape cancels'}</p>}
      <p id="reorder-help" className="sr-only">Drag only the corner grip to reorder. Keyboard: Space picks up, arrows move, Enter drops, Escape cancels. Changes save on drop.</p>
      </div>
    </section>
    {guestStrategyPreview && <GuestFeatureDialog title="Generate a strategy"
      message="With member access and ChatGPT, SIGMA proposes candidate hypotheses and research approaches, challenges them for originality and weaknesses, and presents a draft for your review before saving. You can write and edit strategies manually without AI."
      onClose={() => setGuestStrategyPreview(false)}/>}
    {guestPlayOpen && <GuestFeatureDialog title="Research sessions"
      message="A session needs at least one enabled strategy, which you can write manually. With member access and ChatGPT, Sessions coordinate Investigator and Skeptic turns across selected strategies, recording findings, objections, evidence and unanswered questions. Example sessions can be explored without executing a model."
      onClose={() => setGuestPlayOpen(false)}/>}
    <ResearchWorkspace collaborationRevision={sharedActivity?.shared ? sharedActivity.revision : undefined} artifactAuthors={sharedActivity?.artifact_authors?.session} viewerEmail={sharedActivity?.you} projectOwnerEmail={sharedActivity?.owner} path={view.path} projectId={project.id} strategies={strategies} nextStrategyOrdinal={view.project.strategies.length + 1} missingType={missingProjectType} safeSavedTypeSettings={safeSavedTypeSettings} savedTypeName={savedTypeSnapshot?.name ?? project.investigation_type} onChooseReplacement={() => { if (enterMode('project-settings')) setProjectEditing(true); }} onInferredStrategy={(next, id) => { setView(next); showStrategy(id); setAnnouncement('Inferred strategy saved and added to Strategies.'); }} advancedOutcomeDetails={guest ? guestAdvancedOutcome : advancedOutcomeGlobal} onEnableAdvancedOutcome={async () => {
      if (guest) { setGuestAdvancedOutcome(true); return; }
      if (advancedOutcomeGlobal) return;
      const response = await fetch('/api/user-preferences/research-settings', {
        method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
        body: JSON.stringify({ show_advanced_outcome_details: true }),
      });
      if (!response.ok) throw new Error('Unable to enable the user-wide Outcome preference');
      setAdvancedOutcomeGlobal(true);
      setAnnouncement('Advanced Outcome enabled for your account.');
    }} onViewStrategy={showStrategy} onForkFromFindings={forkFromFindings} onControlsChange={setProcessControls} sessionControls={processControls} guest={guest} onGuestPlay={() => setGuestPlayOpen(true)} playButtonRef={playButton} controlsDisabled={activeMode !== null || closing || ordering || !!dragId} onRunningChange={setResearchRunning} onInitialActivity={setInitialResearchActivity} onRevealNewSession={collapseProjectAndStrategies} onSectionOpened={() => sectionOpen('sessions')}/>
    <PapersPane collaborationRevision={sharedActivity?.shared ? sharedActivity.revision : undefined} artifactAuthors={sharedActivity?.artifact_authors?.paper} viewerEmail={sharedActivity?.you} projectOwnerEmail={sharedActivity?.owner} draftCreatorEmail={sharedActivity?.artifact_authors?.paper_draft?.[project.id]} path={view.path} projectId={project.id} guest={guest} onRunningChange={onPaperRunningChange} onQueuedChange={setPaperQueued} onInitialActivity={setInitialPaperActivity} onSectionOpened={() => sectionOpen('papers')}/>
    {projectEditing && <ProjectClassificationDialog initial={view} collaborationRevision={sharedActivity?.shared ? sharedActivity.revision : undefined} onCancel={() => { setProjectEditing(false); exitMode('project-settings'); requestAnimationFrame(() => editProjectButton.current?.focus()); }} onSaved={next => { markLocalSharedSave(); setView(next); setAnnouncement('Project settings saved.'); }}/>}
    <ProjectExportDialog open={exportOpen} path={view.path} title={project.title} onCancel={() => { setExportOpen(false); requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.project-pane-actions [aria-label="Export project"]')?.focus()); }}/>
    {emailOpen && <ProjectEmailDialog path={view.path} projectId={project.id} title={project.title}
      onCancel={() => { setEmailOpen(false); requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.project-email-button')?.focus()); }}
      onSent={count => { setEmailOpen(false); setAnnouncement('Project emailed to ' + count + (count === 1 ? ' recipient.' : ' recipients.')); requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.project-email-button')?.focus()); }}/>}

    {aboutOpen && <AboutDialog onClose={closeAbout}/>}
    {qaOpen && <ResearchQADialog path={view.path} projectId={project.id} guest={guest} viewerEmail={sharedActivity?.you} projectOwnerEmail={sharedActivity?.owner} answerAuthors={sharedActivity?.artifact_authors?.answer} onCancel={() => { setQaOpen(false); requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.project-qa-button')?.focus()); }}/>}
    {leanOpen && <LeanPlaceholderDialog onClose={() => { setLeanOpen(false); requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.project-lean-button')?.focus()); }}/>}
    {SHOW_PROJECT_DETAILS_AND_HISTORY && <details className="project-details">
      <summary>Project details &amp; history</summary>
      <dl><dt>Identity</dt><dd>{project.id}</dd><dt>Directory</dt><dd>{view.path}</dd><dt>Format version</dt><dd>{project.schema_version}</dd><dt>Research type</dt><dd>{researchTypeLabel(project.investigation_type)}</dd>{project.difficulty && <><dt>Difficulty</dt><dd>{difficultyLabels[project.difficulty]}</dd></>}<dt>AI model</dt><dd>{project.ai_model}</dd><dt>Thinking level</dt><dd>{thinkingLabels[project.reasoning_effort] ?? project.reasoning_effort}</dd></dl>
      <h3>Event history</h3>
      <ol className="event-list">{project.events.map(event => <li key={event.sequence}>
        <span className="sequence">{String(event.sequence).padStart(2, '0')}</span>
        <div><span>{event.kind}</span><time dateTime={event.timestamp}>{dateLabel(event.timestamp)}</time>
          {event.project_change && <details className="edit-history"><summary>View project changes</summary><dl>{(Object.keys(event.project_change.current) as (keyof Settings)[]).filter(key => event.project_change!.previous[key] !== event.project_change!.current[key]).map(key => <div key={key}><dt>{({ title: 'Project name', problem: 'Research Subject', desired_outcomes: 'Desired Outcomes', paper_requirements: 'Paper Requirements', investigation_type: 'Research type', ai_model: 'AI model', reasoning_effort: 'Thinking level', difficulty: 'Difficulty', show_advanced_outcome_details: 'Advanced Outcome details' })[key]}</dt><dd>Before: {key === 'investigation_type' ? researchTypeLabel(String(event.project_change!.previous[key])) : key === 'difficulty' ? difficultyLabel(event.project_change!.previous[key] as ProjectDifficulty | null) : event.project_change!.previous[key]}<br/>After: {key === 'investigation_type' ? researchTypeLabel(String(event.project_change!.current[key])) : key === 'difficulty' ? difficultyLabel(event.project_change!.current[key] as ProjectDifficulty | null) : event.project_change!.current[key]}</dd></div>)}</dl></details>}
          {event.stage_change && <p>Manually tracked: {stageLabels[event.stage_change.previous]} → {stageLabels[event.stage_change.stage]}</p>}
          {event.order && <details><summary>Current order</summary><ol>{event.order.map(id => <li key={id}>{byId.get(id)?.title ?? id}</li>)}</ol></details>}
          {event.change && <details className="edit-history"><summary>View changes</summary>
            <dl><dt>Name before</dt><dd>{event.change.previous_title}</dd>
              <dt>Name after</dt><dd>{event.change.title}</dd>
              <dt>Description before</dt><dd>{event.change.previous_approach}</dd>
              <dt>Description after</dt><dd>{event.change.approach}</dd></dl>
          </details>}
        </div>
      </li>)}</ol>
      <p className="hint">Opening and inspecting a project leave its history unchanged.</p>
    </details>}
  </WorkspaceFrame>;
}

function ResearchQABrowserPage({ qaId, path }: { qaId: string; path: string }) {
  const [markdown, setMarkdown] = useState('');
  const [citationUrls, setCitationUrls] = useState<string[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    document.title = 'Research Q/A · SIGMA';
    const controller = new AbortController();
    const query = new URLSearchParams({ path });
    const url = `/api/projects/research-qa/${encodeURIComponent(qaId)}`;
    Promise.all([
      fetch(`${url}/markdown?${query}`, { cache: 'no-store', signal: controller.signal }),
      fetch(`${url}?${query}`, { cache: 'no-store', signal: controller.signal }),
    ]).then(async ([markdownResponse, recordResponse]) => {
      if (!markdownResponse.ok || !recordResponse.ok) throw new Error('This Q/A answer is unavailable.');
      const [document, record] = await Promise.all([markdownResponse.text(), recordResponse.json() as Promise<ResearchQARecord>]);
      setCitationUrls(record.sources.filter(source => source.navigation_available && source.navigation_url).map(source => source.navigation_url!));
      setMarkdown(document);
    }).catch(cause => { if (!controller.signal.aborted) setError(errorMessage(cause)); });
    return () => controller.abort();
  }, [qaId, path]);
  return <main className="workspace-page research-qa-browser-page"><article className="research-qa-browser-card" aria-label="Research Q/A answer">
    {error ? <p role="alert" className="error">{error}</p> : markdown ? <div className="outcome-markdown"><Suspense fallback={<p role="status">Preparing formatted answer…</p>}><RenderedMarkdown body={markdown} citationProjectPath={path} citationUrls={citationUrls}/></Suspense></div> : <p role="status">Loading answer…</p>}
  </article></main>;
}

function App() {
  const cloud = useCloudIdentity();
  const [openedView, setOpenedView] = useState<ProjectView | null>(null);
  const [openedFromCache, setOpenedFromCache] = useState(false);
  const [artworkDecoded, setArtworkDecoded] = useState(projectArtworkReady);
  const [artworkError, setArtworkError] = useState('');
  const cacheScope = projectCacheScope(cloud);
  const rememberProject = useCallback((view: ProjectView) => {
    const key = projectViewCacheKey(cacheScope, view.path);
    // Retain a small hot set of full views, not an unbounded history of large
    // research projects. Metadata listing remains cached independently.
    recentProjectViewCache.delete(key);
    recentProjectViewCache.set(key, view);
    if (recentProjectViewCache.size > 6) {
      const oldest = recentProjectViewCache.keys().next().value;
      if (oldest !== undefined) recentProjectViewCache.delete(oldest);
    }
  }, [cacheScope]);
  const getCachedProject = useCallback((path: string): ProjectView | undefined =>
    recentProjectViewCache.get(projectViewCacheKey(cacheScope, path)), [cacheScope]);
  const [location, setLocation] = useState(() => window.location.pathname + window.location.search);
  const route = new URL(location, window.location.origin);
  useEffect(() => {
    if (route.pathname !== '/project') return;
    let cancelled = false;
    void preloadProjectArtwork().then(
      () => { if (!cancelled) { setArtworkDecoded(true); setArtworkError(''); } },
      error => { if (!cancelled) setArtworkError(errorMessage(error)); },
    );
    return () => { cancelled = true; };
  }, [route.pathname]);
  const [globalActivity, setGlobalActivity] = useState<'active' | 'queued' | null>(null);
  useEffect(() => {
    // CSS animations begin on element insertion by default, leaving newly
    // mounted yellow/green pulses out of phase. Anchor every heartbeat to the
    // document timeline so their beats stay synchronized across projects.
    let frame: number | undefined;
    const alignPulsePhases = () => {
      frame = undefined;
      const nodes = document.querySelectorAll<HTMLElement>(
        '.research-running-indicator, .session-running i, .paper-stage-list li.is-active, .paper-stage-list li.is-queued'
      );
      for (const node of Array.from(nodes)) {
        for (const animation of node.getAnimations()) {
          if ('animationName' in animation &&
            animation.animationName === 'research-running-heartbeat' &&
            animation.startTime !== 0) {
            animation.startTime = 0;
          }
        }
      }
    };
    const schedule = () => {
      if (frame === undefined) frame = requestAnimationFrame(alignPulsePhases);
    };
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'hidden'] });
    schedule();
    return () => {
      observer.disconnect();
      if (frame !== undefined) cancelAnimationFrame(frame);
    };
  }, []);
  useEffect(() => {
    if (cloud?.enabled && (!cloud.authenticated || cloud.user?.role === 'guest')) {
      setGlobalActivity(null);
      return;
    }
    const controller = new AbortController();
    let pending = false;
    const poll = async () => {
      if (pending || controller.signal.aborted) return;
      pending = true;
      try {
        const response = await fetch('/api/projects/recent/activity', { cache: 'no-store', signal: controller.signal, headers: { 'X-Sigma-Error-Handled': 'true' } });
        if (!response.ok) throw new Error('Global activity unavailable');
        const body = await response.json() as { projects: RecentProject[] };
        if (controller.signal.aborted) return;
        const all = body.projects ?? [];
        // Home consumes this already-fetched activity summary. Never force a
        // paper-score or historical-paper scan just to refresh running icons.
        window.dispatchEvent(new CustomEvent('sigma-saved-activity', { detail: all }));
        setGlobalActivity(all.some(row => row.research_running || row.answer_active || row.paper_generating || row.paper_activity === 'active')
          ? 'active' : all.some(row => row.paper_activity === 'queued') ? 'queued' : null);
      } catch { /* Keep the last known activity; a transient error must not clear it. */ }
      finally { pending = false; }
    };
    // Defer activity scan until after the first Home list has painted.
    const firstPoll = window.setTimeout(() => void poll(), 1000);
    const timer = window.setInterval(() => void poll(), 5000);
    window.addEventListener("focus", poll);
    return () => { controller.abort(); window.clearTimeout(firstPoll); window.clearInterval(timer); window.removeEventListener("focus", poll); };
  // Page navigation does not change the workspace identity or running jobs.
  // Do not trigger an extra full Saved-project scan every time a project opens.
  }, [cloud?.enabled, cloud?.authenticated, cloud?.user?.role, cloud?.account?.workspace?.id]);
  useEffect(() => globalActivity === 'active' ? runningFavicon() : globalActivity === 'queued' ? runningFavicon('yellow') : undefined, [globalActivity]);
  useEffect(() => {
    if (cloud?.enabled && (!cloud.authenticated || cloud.user?.role === 'guest')) return;
    const controller = new AbortController();
    const viewerId = crypto.randomUUID();
    let pending = false;
    const heartbeat = async () => {
      if (pending || controller.signal.aborted) return;
      pending = true;
      try {
        await fetch('/api/projects/research-presence/workspace', {
          method: 'POST', credentials: 'same-origin', signal: controller.signal,
          headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
          body: JSON.stringify({ viewer_id: viewerId }),
        });
      } catch { /* Expired leases are handled by the backend's existing safety gate. */ }
      finally { pending = false; }
    };
    void heartbeat();
    const timer = window.setInterval(() => void heartbeat(), 15000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [cloud?.enabled, cloud?.authenticated, cloud?.user?.role, cloud?.account?.workspace?.id]);
  const presencePath = route.pathname === '/project' && !route.searchParams.has('qa_browser')
    ? route.searchParams.get('path') : null;
  useEffect(() => {
    // Server-side heartbeat tracks this project page, including background tabs.
    // Closing or navigating away releases only this page's lease.
    if (!presencePath || (cloud?.enabled && (!cloud.authenticated || cloud.user?.role === 'guest'))) return;
    const viewer = new EventSource(windowAuthUrl(`/api/projects/research-presence?${new URLSearchParams({ path: presencePath })}`));
    return () => viewer.close();
  }, [presencePath, cloud?.enabled, cloud?.authenticated, cloud?.user?.role, cloud?.account?.workspace?.id]);
  const [lastPath, setLastPath] = useState(() =>
    new URLSearchParams(window.location.search).get('path') || 'projects/rh.sigma');
  useEffect(() => {
    const pop = () => { setOpenedView(null); setLocation(window.location.pathname + window.location.search); };
    window.addEventListener('popstate', pop);
    return () => window.removeEventListener('popstate', pop);
  }, []);
  const navigate = useCallback((url: string) => {
    window.history.pushState(null, '', url); setLocation(url); window.scrollTo(0, 0);
  }, []);
  const closeProject = useCallback(() => {
    setOpenedView(null);
    const path = new URLSearchParams(window.location.search).get('path');
    if (path) { setLastPath(path); window.localStorage.setItem('sigma.currentProject', path); }
    navigate('/');
  }, [navigate]);
  function goHome(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      event.preventDefault(); setOpenedView(null); navigate('/');
    }
  }
  const url = new URL(location, window.location.origin);
  if (url.pathname === '/chat') {
    return <><Header goHome={goHome} chatPage/><ChatPage onHome={() => navigate('/')}/><FloatingTooltip/></>;
  }
  const qaBrowser = url.searchParams.get('qa_browser');
  if (qaBrowser) return <><ResearchQABrowserPage qaId={qaBrowser} path={url.searchParams.get('path') ?? ''}/><FloatingTooltip/></>;
  return <><main className={url.pathname === '/' ? 'home-page' : 'workspace-page'}>
    {url.pathname === '/' ? <Home initialPath={lastPath} cacheScope={cacheScope} getCachedView={getCachedProject} onOpen={async (view, openSettings, fromCache, revealPaperId) => {
      await preloadProjectArtwork();
      setArtworkDecoded(true);
      rememberProject(view); setOpenedFromCache(!!fromCache); setOpenedView(view);
      setLastPath(view.path); window.localStorage.setItem('sigma.currentProject', view.path);
      navigate(projectUrl(view.path)
        + (openSettings ? '&settings=collaborators' : revealPaperId ? `&reveal_paper=${encodeURIComponent(revealPaperId)}` : ''));
    }} onNavigateActivity={(entry, run) => {
      // Use the run ID already displayed on Home; no activity fetch blocks navigation.
      const target = new URL(projectUrl(entry.path), window.location.origin);
      if (run?.kind === 'session') {
        if (run.id) target.searchParams.set('reveal_session', run.id);
        else target.searchParams.set('reveal_sessions', '1');
      } else if (run?.kind === 'paper') {
        if (run.id) target.searchParams.set('reveal_paper_run', run.id);
        else target.searchParams.set('reveal_paper', 'draft');
      } else if (run?.kind === 'answer') target.searchParams.set('reveal_qa', '1');
      // Activity jumps are navigation-only; an already decoded image resolves
      // immediately. If this is the first visit, retain Home until it is ready.
      void preloadProjectArtwork().then(() => {
        setArtworkDecoded(true);
        const cached = getCachedProject(entry.path);
        setOpenedFromCache(!!cached); setOpenedView(cached ?? null); setLastPath(entry.path);
        window.localStorage.setItem('sigma.currentProject', entry.path);
        navigate(target.pathname + target.search);
      }).catch(error => reportRequestFailure(errorMessage(error)));
    }}/> : url.pathname === '/project' && !artworkDecoded
      ? <div className="project-artwork-loading" role="status">{artworkError ? artworkError : <>Opening project… <ProjectOpeningHourglass/></>}</div>
      : url.pathname === '/project' ? <ResearchDisplayBoundary key={location} label="Project workspace"><ProjectScreen
      initialView={openedView?.path === url.searchParams.get('path') ? openedView : undefined}
      revalidateCached={openedFromCache && openedView?.path === url.searchParams.get('path')}
      onViewChange={rememberProject} path={url.searchParams.get('path') ?? ''} onClose={closeProject} goHome={goHome}/></ResearchDisplayBoundary>
      : <><Header goHome={goHome}/><h1>Page not found</h1><a href="/" onClick={goHome}>Return Home</a></>}
  </main><FloatingTooltip/></>;
}

type CloudStatus = { mock_auth?: boolean; mock_identity?: boolean; sponsored_test_mode?: boolean; target?: 'local' | 'hosted'; enabled: boolean; ready: boolean; authenticated: boolean; user: { email: string; role: string } | null; account?: { identity: { email: string; verified: boolean }; access: { status: string; role: string }; workspace: { available: boolean; id: string | null }; model_access: { mode: string; connection: string }; sponsorship: { eligible: boolean; forced?: boolean }; invitation_welcome_pending?: boolean; invitation_status?: string | null } | null; admin_contact_email: string | null; local_setup_missing?: string[] };
type CloudGrant = { kind: string; value: string; role: string; active: number; updated_at: number; allowance_usd: number | null; effective_allowance_usd: number | null };
type CloudAccountSession = { email: string; role: string; authorized: boolean; status: string; expires_at: number | null; allowance_usd: number | null; spending?: { estimated_usage_usd: number; held_usd: number; reserved_and_estimated_usd: number; remaining_usd: number | null; reload_eligible?: boolean } };
type CloudFunding = { target: 'local' | 'hosted'; authenticationEnabled: boolean; googleAccount: string | null; budget: CloudResearchBudget | null; loading: boolean; error: string | null; authorized: boolean; sponsorshipEligible: boolean; sponsorshipUnlimited: boolean; provider: { provider?: SponsoredInferenceProvider; status: string; guidance: string } | null; providerLoading: boolean; providerError: string | null; retryProvider: () => Promise<void>; selectedConnection: 'personal' | 'sponsored'; forcedSponsored?: boolean; simulatedSponsored?: boolean; disconnectMockSponsored?: () => Promise<void>; selectConnection: (mode: 'personal' | 'sponsored') => Promise<void>; connectionError: string | null; selectingConnection: boolean };
type CloudIdentityState = CloudStatus & { deniedIdentityAvailable: boolean; deniedInvitationStatus: string | null; funding: CloudFunding; openAccessManagement: () => void };
const CloudIdentityContext = createContext<CloudIdentityState | null>(null);
function useCloudIdentity() { return useContext(CloudIdentityContext); }
function cloudFundingFor(cloud: CloudIdentityState | null): CloudFunding | undefined {
  return cloud?.funding;
}

/** Match ConnectionStatus's connected state, including sponsored sessions.
 * Google authentication alone is not sufficient to show the model selector. */
function ConnectedModelPill({ enabled }: { enabled: boolean }) {
  const ai = useAI();
  const cloud = useCloudIdentity();
  const funding = cloudFundingFor(cloud);
  const googleRequired = !!funding?.authenticationEnabled && !funding.authorized;
  // Match the *displayed* ChatGPT pill rather than the provider health check:
  // the sponsored pill is shown for an authorized sponsored connection even
  // when its provider status has not yet been fetched.
  const sponsoredSelected = funding?.selectedConnection === 'sponsored';
  const sponsoredPillVisible = !!funding?.authorized && sponsoredSelected
    && (funding.target === 'hosted' || funding.sponsorshipEligible);
  const personalConnected = !ai.connecting && !ai.initialLoading && !ai.healthError
    && ai.info?.status === 'connected';
  const visible = sponsoredPillVisible || (!sponsoredSelected && personalConnected);
  return enabled && visible && !googleRequired
    ? <GlobalModelPill enabled/>
    : null;
}

type CloudDemoAudit = { export_version: 2; project: ProjectView['project']; agentic_runs: Record<string, any>[]; research_sessions: Record<string, any>[] };
function CloudDemoExperience({ deniedIdentityAvailable, authenticated, user }: { deniedIdentityAvailable: boolean; authenticated: boolean; user: CloudStatus['user'] }) {
  const [audit, setAudit] = useState<CloudDemoAudit | null>(null);
  const [error, setError] = useState('');
  const [exportOpen, setExportOpen] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/cloud-demo/', { cache: 'no-store', signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('The curated Demo is temporarily unavailable.');
      const value = await response.json() as CloudDemoAudit;
      if (value.export_version !== 2 || !value.project || !Array.isArray(value.agentic_runs) || !Array.isArray(value.research_sessions)) throw new Error('The curated Demo data could not be verified.');
      setAudit(value);
    }).catch(cause => { if (!controller.signal.aborted) setError(errorMessage(cause)); });
    return () => controller.abort();
  }, []);
  const project = audit?.project;
  return <main className="cloud-demo-page">
    <header className="cloud-demo-header"><a className="cloud-demo-brand" href="/">SIGMA</a><nav aria-label="Demo navigation"><a href={deniedIdentityAvailable ? '/?access=denied' : '/'}>{deniedIdentityAvailable ? 'Invitation request' : 'Home'}</a>{authenticated ? <><span>{user?.email}</span><button onClick={async () => { await fetch('/api/cloud-auth/logout', { method: 'POST', credentials: 'same-origin' }); window.localStorage.removeItem('sigma.currentProject'); window.location.assign('/demo'); }}>Sign out</button></> : <a className="cloud-demo-signin" href="/api/cloud-auth/login">Sign in with Google</a>}</nav></header>
    <section className="cloud-demo-intro"><p className="cloud-auth-kicker">Public read-only preview</p><h1>Explore a SIGMA research project</h1><p>Inspect a curated project, its strategies, research sessions, outcomes, computational evidence and report exports. This shared Demo does not create a workspace or run agents.</p></section>
    {error && <section className="cloud-demo-state" role="alert"><h2>Demo unavailable</h2><p>{error}</p></section>}
    {!audit && !error && <p className="cloud-demo-state" role="status">Loading Demo data…</p>}
    {audit && project && <>
      <section className="cloud-demo-project"><div><p className="cloud-auth-kicker">{researchTypeLabel(project.investigation_type)} · {difficultyLabel(project.difficulty)}</p><h2>{project.title}</h2><div className="cloud-demo-markdown"><RenderedMarkdown body={project.problem}/></div></div><button className="cloud-demo-export" onClick={() => setExportOpen(true)}>Export project</button></section>
      <section className="cloud-demo-section"><h2>Strategies <span>{project.strategies.length}</span></h2><div className="cloud-demo-grid">{project.strategies.map(strategy => <details className="cloud-demo-card" key={strategy.id} open><summary><span>{strategy.title}</span><small>{strategy.stage} · {strategy.author_kind}</small></summary><p>{strategy.summary}</p><div className="cloud-demo-markdown"><RenderedMarkdown body={strategy.approach}/></div></details>)}</div></section>
      <section className="cloud-demo-section"><h2>Research sessions <span>{audit.research_sessions.length}</span></h2>{audit.research_sessions.map(session => <details className="cloud-demo-card cloud-demo-session" key={session.id}><summary><span>Session {session.session_number}: {session.strategy_title}</span><small>{session.status} · {session.started_at?.slice(0, 10)}</small></summary><div className="cloud-demo-columns"><div><h3>Outcome</h3><p>{session.outcome?.solution_review?.claim}</p><p>{session.outcome?.solution_review?.argument_summary}</p><h3>Strategy assessment</h3>{session.strategy_assessments?.map((item: any) => <p key={item.strategy_id}>{item.assessment}: {item.rationale}</p>)}</div><div><h3>Saved research artifacts</h3>{session.artifacts?.map((artifact: any) => <article className="cloud-demo-evidence" key={artifact.id}><strong>{artifact.claim}</strong><p>{artifact.method}</p><small>Evidence status: {artifact.evidence_status}</small><p>{artifact.skeptic_response}</p>{artifact.computational_evidence && <details><summary>Inspect saved computation</summary><p>{artifact.computational_evidence.interpretation}</p><pre>{artifact.computational_evidence.source}{'\n'}{artifact.computational_evidence.stdout}</pre>{artifact.computational_evidence.files?.map((file: any) => <details key={file.filename}><summary>Captured artifact: {file.filename}</summary><pre>{file.content}</pre><small>SHA-256: {file.sha256}</small></details>)}</details>}</article>)}</div></div></details>)}</section>
      <section className="cloud-demo-section"><h2>Research analysis <span>{audit.agentic_runs.length}</span></h2>{audit.agentic_runs.map(run => <details className="cloud-demo-card" key={run.run_id}><summary><span>Research run · {run.status}</span><small>{run.started_at?.slice(0, 10)}</small></summary><p>{run.timeline?.map((entry: any) => entry.message).join(' ')}</p>{run.steps?.map((step: any, index: number) => <article className="cloud-demo-evidence" key={index}><strong>{step.output?.title}</strong><p>{step.output?.approach}</p><small>{step.output?.evidence_boundary}</small></article>)}</details>)}</section>
      <footer className="cloud-demo-footer"><p>Read-only curated data · exports are generated from this project snapshot</p><button className="cloud-demo-export" onClick={() => setExportOpen(true)}>Export Project Audit or Research Report</button></footer>
      {exportOpen && <ProjectExportDialog demo path="" title={project.title} onCancel={() => setExportOpen(false)}/>}
    </>}
  </main>;
}


function MockAuthSelector() {
  const cloud = useCloudIdentity();
  const [busy, setBusy] = useState(false);
  const [funding, setFunding] = useState<{ mode: string; allowance: { scenario: string; remaining_usd: number }; provider: string } | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!cloud?.mock_auth || !cloud.authenticated) { setFunding(null); return; }
    let cancelled = false;
    fetch('/api/cloud-auth/mock/funding', { credentials: 'same-origin' })
      .then(async response => { if (!response.ok) throw new Error('Mock funding unavailable'); return response.json(); })
      .then(data => { if (!cancelled) setFunding(data); })
      .catch(err => { if (!cancelled) setError(errorMessage(err)); });
    return () => { cancelled = true; };
  }, [cloud?.mock_auth, cloud?.authenticated, cloud?.user?.email]);
  if (!cloud?.mock_auth) return null;
  async function select(identity: string) {
    setBusy(true);
    try {
      const response = await fetch('/api/cloud-auth/mock/select?identity=' + encodeURIComponent(identity), {
        method: 'POST', credentials: 'same-origin',
      });
      if (!response.ok) throw new Error('Mock identity switch failed: ' + response.status);
      window.localStorage.removeItem('sigma.currentProject');
      window.location.assign(identity === 'uninvited' ? '/?access=denied' : '/');
    } catch (err) {
      setError(errorMessage(err)); setBusy(false);
    }
  }
  async function update(kind: 'model-access' | 'allowance' | 'provider', value: string) {
    setBusy(true); setError('');
    try {
      const parameter = kind === 'model-access' ? 'mode' : 'scenario';
      const response = await fetch('/api/cloud-auth/mock/' + kind + '?' + parameter + '=' + encodeURIComponent(value), {
        method: 'POST', credentials: 'same-origin',
      });
      if (!response.ok) throw new Error('Mock scenario update failed: ' + response.status);
      const latest = await fetch('/api/cloud-auth/mock/funding', { credentials: 'same-origin' });
      if (!latest.ok) throw new Error('Mock funding refresh failed');
      setFunding(await latest.json());
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 12, flexWrap: 'wrap' }}>
    <strong>MOCK AUTH · LOCAL ONLY</strong>
    <select aria-label="Mock authentication identity" disabled={busy} defaultValue="" onChange={event => void select(event.target.value)}>
      <option value="" disabled>Switch identity…</option>
      <option value="guest">Guest</option>
      <option value="member-a">Member A</option>
      <option value="member-b">Member B</option>
      <option value="admin">Administrator</option>
      <option value="uninvited">Uninvited</option>
    </select>
    {funding && <>
      <select aria-label="Mock funding mode" disabled={busy} value={funding.mode} onChange={event => void update('model-access', event.target.value)}>
        <option value="personal">Personal</option><option value="sponsored">SIGMA-sponsored</option>
      </select>
      <select aria-label="Mock sponsorship allowance" disabled={busy} value={funding.allowance.scenario} onChange={event => void update('allowance', event.target.value)}>
        <option value="available">Available</option><option value="low">Low</option><option value="exhausted">Exhausted</option>
      </select>
      <select aria-label="Mock provider state" disabled={busy} value={funding.provider} onChange={event => void update('provider', event.target.value)}>
        <option value="connected">Provider connected</option><option value="unavailable">Provider unavailable</option><option value="error">Provider error</option>
      </select>
      <span aria-live="polite">Simulated allowance: ${funding.allowance.remaining_usd.toFixed(2)} remaining · Provider: {funding.provider} · Research execution disabled</span>
    </>}
    {error && <span role="alert">{error}</span>}
  </span>;
}

function hasOpenInvitationRequest(status?: string | null) {
  return status === 'pending' || status === 'sending' || status === 'notified';
}

function GoogleIdentityPill({ inviteInHeader = false }: { inviteInHeader?: boolean }) {
  const cloud = useCloudIdentity();
  const signedInAccountTooltip = cloud?.user?.email
    ? `Signed in as ${cloud.user.email}`
    : 'Signed in with Google';
  const dialog = useRef<HTMLDialogElement>(null);
  const [error, setError] = useState('');
  const [invitationRecorded, setInvitationRecorded] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const signOutInFlight = useRef(false);
  const deniedIdentityAvailable = cloud?.deniedIdentityAvailable ?? false;
  // A local Google guest is authenticated but has no member permissions.
  const authenticatedGuest = cloud?.authenticated && cloud.user?.role === 'guest';
  const invitationStatus = authenticatedGuest ? cloud?.account?.invitation_status : cloud?.deniedInvitationStatus;
  const invitationRequestOpen = hasOpenInvitationRequest(invitationStatus);
  const invitationIdentity = !!cloud?.enabled && (authenticatedGuest || (!cloud.authenticated && deniedIdentityAvailable));
  const canRequestInvitation = invitationIdentity
    && !invitationRequestOpen
    && !invitationRecorded;
  const currentProjectPath = new URLSearchParams(window.location.search).get('path');
  const notificationLink = new URLSearchParams(window.location.search);
  const fromProgressEmail = notificationLink.has('reveal_session') || notificationLink.has('reveal_paper');
  const isGuestSample = !!currentProjectPath
    && window.sessionStorage.getItem('sigma.guestSamplePath') === currentProjectPath;
  // Signing in from an ordinary project or guest sample starts at Home.
  // Explicit research-notification deep links still resume their target,
  // except when a guest opened a featured sample paper with reveal_paper.
  const projectReturn = window.location.pathname === '/project' && currentProjectPath
    && fromProgressEmail && !isGuestSample
    ? `/api/cloud-auth/login?${new URLSearchParams({ return_to: `/project?${notificationLink.toString()}` })}`
    : '/api/cloud-auth/login';
  useEffect(() => {
    setInvitationRecorded(invitationRequestOpen);
  }, [cloud?.deniedInvitationStatus, authenticatedGuest, invitationStatus]);
  useEffect(() => {
    // A newly signed-in non-member receives the shared welcome screen first.
    // Keep this invitation dialog available for explicit requests and retries.
    if (!invitationIdentity && dialog.current?.open) dialog.current.close();
  }, [invitationIdentity]);
  useEffect(() => {
    const open = () => {
      document
        .querySelector<HTMLAnchorElement>('.project-google-signin[href^="/api/cloud-auth/login"]')
        ?.click();
    };
    const openInvitation = () => { if (canRequestInvitation) dialog.current?.showModal(); };
    window.addEventListener('sigma-open-google-signin', open);
    window.addEventListener('sigma-open-invitation', openInvitation);
    const params = new URLSearchParams(window.location.search);
    if (params.get('show_invitation') === '1') {
      openInvitation();
      params.delete('show_invitation');
      const query = params.toString();
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`);
    }
    return () => {
      window.removeEventListener('sigma-open-google-signin', open);
      window.removeEventListener('sigma-open-invitation', openInvitation);
    };
  }, [canRequestInvitation]);
  useEffect(() => {
    if (!deniedIdentityAvailable || new URLSearchParams(window.location.search).get('invite') !== '1') return;
    let cancelled = false;
    function clearInviteIntent() {
      const params = new URLSearchParams(window.location.search);
      params.delete('invite');
      const query = params.toString();
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`);
    }
    async function submitInvitationRequest() {
      try {
        const response = await fetch('/api/cloud-auth/invitation-request', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        if (!response.ok) throw await cloudFailure(response, 'Your invitation request could not be sent.');
        if (cancelled) return;
        const result = await response.json() as { status?: string };
        if (result.status === 'approved') { window.location.reload(); return; }
        clearInviteIntent();
        setInvitationRecorded(true);
        window.dispatchEvent(new Event('sigma-invitation-recorded'));
        dialog.current?.close();
      } catch (cause) {
        if (cancelled) return;
        clearInviteIntent();
        setError(errorMessage(cause));
        dialog.current?.showModal();
      }
    }
    void submitInvitationRequest();
    return () => { cancelled = true; };
  }, [deniedIdentityAvailable]);
  async function signOut() {
    if (signOutInFlight.current) return;
    signOutInFlight.current = true;
    setSigningOut(true);
    setError('');
    try {
      // Identity changes must never carry an account-specific project route
      // (or a copied guest project) into the next Google sign-in.
      // Explicit reauthentication is distinct from the browser closing: keep
      // already admitted jobs alive during a bounded identity handoff.
      // Authenticated guests cannot run paid work and do not need a handoff.
      if (!authenticatedGuest) {
        try {
          await fetch('/api/projects/research-presence/auth-handoff', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'X-Sigma-Error-Handled': 'true' },
          });
        } catch {
          // The auxiliary work-preservation request must not veto explicit sign-out.
        }
      }
      const response = await fetch('/api/cloud-auth/logout', { method: 'POST', credentials: 'same-origin' });
      if (!response.ok) throw new Error('Google sign-out could not be completed.');
      // Signing out is not a first visit. Keep the post-logout guest view
      // quiet for this tab instead of presenting its introductory welcome.
      window.sessionStorage.setItem('sigma.guestWelcomeDismissed', 'true');
      window.sessionStorage.removeItem('sigma.nonMemberWelcomeDismissed');
      window.localStorage.removeItem('sigma.currentProject');
      window.sessionStorage.removeItem('sigma.guestSamplePath');
      window.location.assign('/');
    } catch (cause) {
      signOutInFlight.current = false;
      setSigningOut(false);
      const message = errorMessage(cause);
      setError(message);
      reportRequestFailure(message);
    }
  }
  return <>
    {cloud?.enabled && cloud.authenticated
      ? <button type="button" className="project-google-signin" onClick={() => void signOut()} disabled={signingOut} aria-busy={signingOut} aria-label={signingOut ? 'Signing out of Google' : 'Sign out of Google'} data-tooltip={signedInAccountTooltip}><span className="connection-dot connection-connected" aria-hidden="true"/>{signingOut ? 'Signing out of Google…' : 'Sign out of Google'}</button>
      : <>
        <a className="project-google-signin" href={projectReturn} onClick={() => window.sessionStorage.removeItem('sigma.nonMemberWelcomeDismissed')}><span className="connection-dot" aria-hidden="true"/>Sign in with Google</a>
        {canRequestInvitation && !inviteInHeader && <button type="button" className="project-google-signin project-invite-me" aria-haspopup="dialog" aria-controls="google-invitation-dialog" onClick={() => dialog.current?.showModal()}>Invite me!</button>}
      </>}
    {(!cloud?.authenticated || authenticatedGuest) && <dialog id="google-invitation-dialog" ref={dialog} className="google-account-dialog google-invitation-dialog" aria-labelledby="google-invitation-heading" onCancel={event => { if (deniedIdentityAvailable) event.preventDefault(); }}>
      <div className="privacy-notice-heading google-invitation-heading"><h2 id="google-invitation-heading">Request an invitation</h2><DialogDismissButton label="Close invitation request" onClick={() => dialog.current?.close()}/></div>
      {(deniedIdentityAvailable || authenticatedGuest)
        ? <p>We couldn’t find an active SIGMA invitation for this Google account. You can request access here.</p>
        : <p>Sign in with Google so SIGMA can verify your account before recording an invitation request.</p>}
      {(deniedIdentityAvailable || authenticatedGuest)
        ? invitationRecorded
          ? <p role="status">Your invitation request is recorded and awaiting administrator review.</p>
          : <InvitationRequestControls error={error} onError={setError} onRecorded={() => { setInvitationRecorded(true); if (authenticatedGuest) window.dispatchEvent(new Event('sigma-cloud-auth-refresh')); window.dispatchEvent(new Event('sigma-invitation-recorded')); }}/>
        : <a className="cloud-text-button google-invitation-signin" href="/api/cloud-auth/login?invite=1">Sign in with Google</a>}
      {error && !deniedIdentityAvailable && <p role="alert">{error}</p>}
      {deniedIdentityAvailable && !authenticatedGuest && <a className="cloud-text-button google-invitation-signin" href={projectReturn} onClick={() => window.sessionStorage.removeItem('sigma.nonMemberWelcomeDismissed')}>Use another Google account</a>}
      <footer className="about-dialog-footer google-invitation-footer"><nav className="about-legal-links" aria-label="Legal information"><a className="about-privacy-link" href={privacyNoticeHref('invitation')}>Privacy Notice</a></nav></footer>
    </dialog>}
  </>;
}

function HomeInvitationAction() {
  const cloud = useCloudIdentity();
  const [recorded, setRecorded] = useState(false);
  const [sending, setSending] = useState(false);
  const [requestError, setRequestError] = useState('');
  const [confirmationOpen, setConfirmationOpen] = useState(false);
  async function requestInvitation() {
    if (sending) return;
    setSending(true);
    setRequestError('');
    try {
      const response = await fetch('/api/cloud-auth/invitation-request', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: '{}',
      });
      if (!response.ok) throw await cloudFailure(response, 'Your invitation request could not be sent.');
      const result = await response.json() as { status?: string };
      if (result.status === 'approved') { window.location.reload(); return; }
      setRecorded(true);
      setConfirmationOpen(true);
      window.dispatchEvent(new Event('sigma-invitation-recorded'));
      window.dispatchEvent(new Event('sigma-cloud-auth-refresh'));
    } catch (cause) {
      setRequestError(errorMessage(cause));
    } finally {
      setSending(false);
    }
  }
  const uninvited = cloud?.user?.role === 'guest' || cloud?.deniedIdentityAvailable;
  const invitationStatus = cloud?.user?.role === 'guest'
    ? cloud.account?.invitation_status
    : cloud?.deniedInvitationStatus;
  useEffect(() => {
    setRecorded(hasOpenInvitationRequest(invitationStatus));
  }, [invitationStatus]);
  useEffect(() => {
    const onRecorded = () => setRecorded(true);
    window.addEventListener('sigma-invitation-recorded', onRecorded);
    return () => window.removeEventListener('sigma-invitation-recorded', onRecorded);
  }, []);
  if (!cloud?.enabled || !uninvited) return null;
  return <>
    {confirmationOpen && <InvitationWelcomeDialog
      audience="requested"
      allowance={null}
      allowanceUsed={0}
      allowanceLoading={false}
      onDismiss={async () => { setConfirmationOpen(false); }}
    />}
    {!hasOpenInvitationRequest(invitationStatus) && !recorded && <>
      <button type="button" className="project-google-signin project-invite-me" disabled={sending} aria-busy={sending} onClick={() => void requestInvitation()}>{sending ? 'Sending…' : 'Invite me!'}</button>
      {requestError && <span role="alert">{requestError} <button type="button" className="cloud-text-button sigma-text-action" onClick={() => void requestInvitation()}>Try again</button></span>}
    </>}
  </>;
}

function ReloadMeAction({ connectionPill = false }: { connectionPill?: boolean }) {
  const cloud = useCloudIdentity();
  const [state, setState] = useState<'idle' | 'sending' | 'requested' | 'error'>('idle');
  const budget = cloud?.funding.budget;
  if (!cloud?.authenticated || cloud.user?.role === 'admin' || !cloud.funding.sponsorshipEligible || !budget || budget.remaining_usd === null || budget.remaining_usd >= 0.05) return null;
  async function requestReload() {
    setState('sending');
    try {
      const response = await fetch('/api/cloud-auth/invitation-request', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_type: 'reload' }),
      });
      if (!response.ok) throw await cloudFailure(response, 'Your reload request could not be sent.');
      setState('requested');
    } catch { setState('error'); }
  }
  if (state === 'requested') return <span className={`administrator-settings-link reload-me-status${connectionPill ? ' reload-me-connection' : ''}`} role="status">Reload requested</span>;
  return <button type="button" className={`administrator-settings-link reload-me-pill${connectionPill ? ' reload-me-connection' : ''}`} disabled={state === 'sending'} onClick={() => void requestReload()}>{state === 'sending' ? 'Requesting…' : state === 'error' ? 'Try reload again' : 'Reload me!'}</button>;
}

function InvitationRequestControls({ error, onError, onRecorded, buttonLabel = 'Invite me', buttonClassName = 'cloud-text-button' }: {
  error: string; onError: (error: string) => void; onRecorded: () => void;
  buttonLabel?: string; buttonClassName?: string;
}) {
  const [busy, setBusy] = useState(false);
  async function requestInvitation() {
    setBusy(true); onError('');
    try {
      const response = await fetch('/api/cloud-auth/invitation-request', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      if (!response.ok) throw await cloudFailure(response, 'Your invitation request could not be sent.');
      const result = await response.json() as { status?: string };
      if (result.status === 'approved') { window.location.reload(); return; }
      onRecorded();
    } catch (cause) { onError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <div className="google-invitation-actions">
    {error
      ? <p role="alert">{error} <button type="button" className={buttonClassName} aria-busy={busy} disabled={busy} onClick={() => void requestInvitation()}>{busy ? 'Sending…' : 'Try again'}</button></p>
      : <button type="button" className={buttonClassName} aria-busy={busy} disabled={busy} onClick={() => void requestInvitation()}>{busy ? 'Sending…' : buttonLabel}</button>}
  </div>;
}

function allowanceInput(value: number | null) { return value === null ? '' : value.toFixed(2); }
type CloudInvitationRequest = { subject: string; email: string; requested_at: number; status: string; request_type?: 'invitation' | 'reload' };
type CloudFeedbackRequest = { id: string; account_email: string | null; contact_email: string | null; message: string; submitted_at: number; status: string };
/** Icon-only administrator actions use SIGMA hovertext, not native titles. */
function AdminActionIcon({ kind }: { kind: 'new' | 'add' | 'remove' | 'reload' }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    {kind === 'new' ? <><circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/></>
      : kind === 'add' ? <path d="M12 5v14M5 12h14"/>
      : kind === 'reload' ? <><path d="M20 11a8 8 0 1 0-2.5 6"/><path d="M20 4v7h-7"/></>
      : <path d="M8 8 16 16M16 8 8 16" strokeWidth="4"/>}
  </svg>;
}

function AccessManagementDialog({ bootstrapAdmin, grants, sessions, invitationRequests, feedbackRequests, error, busy, onClose, onAdd, onSave, onRevoke, onReload, onUpdateInvitation, onUpdateFeedback, onRemoveFeedback }: {
  bootstrapAdmin: string; grants: CloudGrant[]; sessions: CloudAccountSession[];
  invitationRequests: CloudInvitationRequest[];
  feedbackRequests: CloudFeedbackRequest[];
  error: string; busy: boolean; onClose: () => void;
  onAdd: (entry: { kind: 'email' | 'domain'; value: string; role: 'member' | 'admin'; allowance_usd: number | null }) => Promise<void>;
  onSave: (updates: { kind: 'email' | 'domain'; value: string; role: 'member' | 'admin'; allowance_usd: number | null }[]) => Promise<void>;
  onRevoke: (grant: CloudGrant) => Promise<void>;
  onReload: (grant: CloudGrant) => Promise<void>;
  onUpdateInvitation: (request: CloudInvitationRequest, status: 'reviewed' | 'declined') => Promise<void>;
  onUpdateFeedback: (request: CloudFeedbackRequest, status: 'new' | 'reviewed') => Promise<void>;
  onRemoveFeedback: (request: CloudFeedbackRequest) => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [drafts, setDrafts] = useState<Record<string, { role: string; allowance: string }>>({});
  const [addOpen, setAddOpen] = useState(false);
  const [authorizedUsersExpanded, setAuthorizedUsersExpanded] = useState(true);
  const [newKind, setNewKind] = useState<'email' | 'domain'>('email');
  const [newValue, setNewValue] = useState('');
  const [newRole, setNewRole] = useState<'member' | 'admin'>('member');
  const [newAllowance, setNewAllowance] = useState('');
  const addButton = useRef<HTMLButtonElement>(null);
  const newEntryPanel = useRef<HTMLDivElement>(null);
  const [newEntryPosition, setNewEntryPosition] = useState<{ left: number; top: number; maxHeight: number } | null>(null);
  const [confirmRemoveKey, setConfirmRemoveKey] = useState('');
  const [removeConfirmationPosition, setRemoveConfirmationPosition] = useState<{ left: number; top: number } | null>(null);
  const removeButtons = useRef(new Map<string, HTMLButtonElement>());
  const removeConfirmation = useRef<HTMLDivElement>(null);
  const removeConfirmButton = useRef<HTMLButtonElement>(null);
  const [message, setMessage] = useState('');
  useEffect(() => {
    setDrafts(Object.fromEntries(grants.map(grant => [`${grant.kind}:${grant.value}`, { role: grant.role, allowance: allowanceInput(grant.allowance_usd) }])));
  }, [grants]);
  useEffect(() => { if (!dialog.current?.open) dialog.current?.showModal(); }, []);
  useEffect(() => {
    if (!addOpen) {
      setNewEntryPosition(null);
      return;
    }
    const place = () => {
      const panel = newEntryPanel.current?.getBoundingClientRect();
      const parent = dialog.current?.getBoundingClientRect();
      if (!parent) return;
      const width = panel?.width ?? Math.min(340, parent.width - 24);
      const height = panel?.height ?? 300;
      const maxHeight = Math.max(140, Math.min(window.innerHeight - 16, parent.height - 24));
      const left = parent.left + (parent.width - width) / 2;
      const top = parent.top + (parent.height - Math.min(height, maxHeight)) / 2;
      setNewEntryPosition({ left, top, maxHeight });
    };
    const frame = requestAnimationFrame(() => {
      place();
      newEntryPanel.current?.querySelector<HTMLInputElement>('input')?.focus();
    });
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        cancelAdd();
      }
    };
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    document.addEventListener('keydown', escape, true);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
      document.removeEventListener('keydown', escape, true);
    };
  }, [addOpen]);
  useEffect(() => {
    if (!confirmRemoveKey) {
      setRemoveConfirmationPosition(null);
      return;
    }
    const place = () => {
      const anchor = removeButtons.current.get(confirmRemoveKey)?.getBoundingClientRect();
      const popover = removeConfirmation.current?.getBoundingClientRect();
      const parent = dialog.current?.getBoundingClientRect();
      if (!anchor || !parent) return;
      const width = popover?.width ?? Math.min(280, window.innerWidth - 24);
      const height = popover?.height ?? 100;
      const left = Math.max(parent.left + 12, Math.min(anchor.right - width, parent.right - width - 12));
      const belowSpace = Math.max(0, parent.bottom - anchor.bottom - 8);
      const aboveSpace = Math.max(0, anchor.top - parent.top - 8);
      const below = height <= belowSpace || belowSpace >= aboveSpace;
      const top = below ? Math.min(anchor.bottom + 8, parent.bottom - height - 8) : Math.max(parent.top + 8, anchor.top - height - 8);
      setRemoveConfirmationPosition({ left, top });
    };
    const frame = requestAnimationFrame(() => {
      place();
      removeConfirmButton.current?.focus();
    });
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setConfirmRemoveKey('');
      }
    };
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    document.addEventListener('keydown', escape, true);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
      document.removeEventListener('keydown', escape, true);
      requestAnimationFrame(() => removeButtons.current.get(confirmRemoveKey)?.focus());
    };
  }, [confirmRemoveKey]);
  const uniqueGrants = new Map<string, CloudGrant>();
  grants.forEach(grant => {
    const normalizedValue = grant.value.trim().toLowerCase().replace(/\.$/, '');
    const key = `${grant.kind}:${normalizedValue}`;
    const current = uniqueGrants.get(key);
    const currentIsCanonical = current ? current.value === current.value.trim().toLowerCase().replace(/\.$/, '') : false;
    const grantIsCanonical = grant.value === grant.value.trim().toLowerCase().replace(/\.$/, '');
    if (!current || grant.updated_at > current.updated_at || (grant.updated_at === current.updated_at && grantIsCanonical && !currentIsCanonical)) uniqueGrants.set(key, grant);
  });
  const ordered = [...uniqueGrants.values()].filter(grant => grant.active === 1).sort((a, b) => a.value.localeCompare(b.value, undefined, { sensitivity: 'base' }) || a.kind.localeCompare(b.kind));
  const changed = ordered.filter(grant => {
    const key = `${grant.kind}:${grant.value}`; const draft = drafts[key];
    return grant.active === 1 && draft && (draft.role !== grant.role
      || (draft.role !== 'admin' && draft.allowance.trim() !== allowanceInput(grant.allowance_usd)));
  });
  const validation = (value: string) => value.trim() === '' || /^\d+(?:\.\d{1,2})?$/.test(value.trim()) && Number(value) >= 0.01 && Number(value) <= 15;
  const draftsValid = changed.every(grant => {
    const draft = drafts[`${grant.kind}:${grant.value}`];
    return draft?.role === 'admin' || validation(draft?.allowance ?? '');
  });
  const hasDrafts = changed.length > 0;
  function requestClose() {
    if (hasDrafts && !window.confirm('Discard only the unsaved role or allowance edits? Completed Add, Remove, and Save actions remain in effect.')) return;
    dialog.current?.close(); onClose();
  }
  async function addEntry() {
    const value = newValue.trim();
    if (!value || (newRole !== 'admin' && !validation(newAllowance)) || value.includes('@') !== (newKind === 'email')) return;
    try {
      await onAdd({ kind: newKind, value, role: newKind === 'domain' ? 'member' : newRole, allowance_usd: newKind === 'email' && newRole === 'admin' ? null : newAllowance.trim() ? Number(newAllowance) : null });
      setNewValue(''); setNewAllowance(''); setAddOpen(false); setMessage('');
      setAuthorizedUsersExpanded(true);
      requestAnimationFrame(() => addButton.current?.focus());
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Authorization could not be added.'); }
  }
  function cancelAdd() {
    setNewValue(''); setNewAllowance(''); setNewKind('email'); setNewRole('member'); setAddOpen(false);
    requestAnimationFrame(() => addButton.current?.focus());
  }
  async function saveUpdates() {
    if (!hasDrafts || !draftsValid) return;
    const updates = changed.map(grant => {
      const draft = drafts[`${grant.kind}:${grant.value}`];
      return { kind: grant.kind as 'email' | 'domain', value: grant.value, role: draft.role as 'member' | 'admin', allowance_usd: draft.role === 'admin' ? null : draft.allowance.trim() ? Number(draft.allowance) : null };
    });
    try { await onSave(updates); setMessage(`Applied ${updates.length} authorization ${updates.length === 1 ? 'update' : 'updates'}.`); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Updates could not be saved.'); }
  }
  async function revoke(grant: CloudGrant) {
    try { await onRevoke(grant); setConfirmRemoveKey(''); setMessage(''); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Authorization could not be revoked.'); }
  }
  async function reload(grant: CloudGrant) {
    try {
      await onReload(grant);
      setMessage(`Restored ${grant.value}'s sponsored allowance to ${currency(grant.effective_allowance_usd)}.`);
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Sponsored allowance could not be reloaded.'); }
  }
  async function addInvitation(item: CloudInvitationRequest) {
    try {
      // An individual member approval inherits the matching domain allowance.
      const email = item.email.trim().toLowerCase();
      const domain = email.split('@')[1];
      const policy = grants.find(grant =>
        grant.kind === 'domain' && grant.active === 1 && grant.value.toLowerCase() === domain
      );
      await onAdd({ kind: 'email', value: item.email, role: 'member', allowance_usd: policy?.allowance_usd ?? null });
      await onUpdateInvitation(item, 'reviewed');
      setAuthorizedUsersExpanded(true);
      setMessage(`Added ${item.email} as an authorized member.`);
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Authorization could not be added.'); }
  }
  async function removeInvitation(item: CloudInvitationRequest) {
    try {
      await onUpdateInvitation(item, 'declined');
      setMessage('Removed the invitation request for ' + item.email + '.');
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Invitation request could not be removed.'); }
  }
  const currency = (value: number | null | undefined) => value === null || value === undefined ? '—' : `$${value.toFixed(2)}`;
  const visibleInvitationRequests = invitationRequests.filter(item => {
    const email = item.email.trim().toLowerCase();
    const domain = email.slice(email.lastIndexOf('@') + 1).replace(/\.$/, '');
    if (item.request_type === 'reload') return true;
    return !grants.some(grant => {
      if (grant.active !== 1) return false;
      const value = grant.value.trim().toLowerCase().replace(/\.$/, '');
      return (grant.kind === 'email' && value === email) || (grant.kind === 'domain' && value === domain);
    });
  });
  return <dialog ref={dialog} className="cloud-access-dialog" aria-labelledby="cloud-access-title" onCancel={event => { event.preventDefault(); requestClose(); }}>
    <div className="admin-dialog-heading"><h2 id="cloud-access-title">Administrator Settings</h2>{hasDrafts && <button type="button" className="admin-text-action" disabled={busy || !draftsValid} onClick={() => void saveUpdates()}>Save</button>}<DialogDismissButton label="Close administrator settings" onClick={requestClose}/></div>
    <section className="admin-access-panel">
      <p className="admin-access-note">Authorized email and domain rules. Domain allowances apply separately to each person; email rules take precedence.</p>
      <p className="cloud-access-bootstrap">Built-in administrator: {bootstrapAdmin || 'not configured'}</p>
      <details className="admin-collapsible-section admin-invitation-section" open><summary><h3>Invitation/reload requests</h3></summary>
      {visibleInvitationRequests.length ? <div className="admin-table-scroll admin-invitation-scroll"><table className="admin-grants-table admin-invitation-table"><colgroup><col style={{ width: '33.33%' }}/><col style={{ width: '33.33%' }}/><col style={{ width: '33.34%' }}/></colgroup><thead><tr><th scope="col">Verified Google account</th><th scope="col">Requested</th><th scope="col">Actions</th></tr></thead><tbody>{visibleInvitationRequests.map(item => {
        return <tr key={item.subject}><th scope="row">{item.email}{item.request_type === 'reload' && <small>Allowance reload request</small>}</th><td>{new Date(item.requested_at * 1000).toLocaleString()}</td><td><div className="admin-invitation-actions"><button type="button" className="admin-text-action admin-icon-action" aria-label={`Add user ${item.email}`} data-tooltip="Add user" disabled={busy} onClick={() => void addInvitation(item)}><AdminActionIcon kind="add"/></button><button type="button" className="admin-text-action admin-remove admin-icon-action" aria-label={`Remove invitation request for ${item.email}`} data-tooltip="Remove invitation request" disabled={busy} onClick={() => void removeInvitation(item)}><AdminActionIcon kind="remove"/></button></div></td></tr>;
      })}</tbody></table></div> : <p className="cloud-access-bootstrap">No invitation requests.</p>}
      </details>
      <details className="admin-collapsible-section admin-feedback-section" open><summary><h3>Product feedback</h3></summary>
      {feedbackRequests.length ? <div className="admin-table-scroll admin-feedback-scroll"><table className="admin-grants-table admin-feedback-table"><colgroup><col style={{ width: '33%' }}/><col style={{ width: '22%' }}/><col style={{ width: '15%' }}/><col style={{ width: '9%' }}/><col style={{ width: '21%' }}/></colgroup><thead><tr><th scope="col">Feedback</th><th scope="col">Google account</th><th scope="col">Submitted</th><th scope="col">Status</th><th scope="col">Actions</th></tr></thead><tbody>{feedbackRequests.map(item => <tr key={item.id}><th scope="row" className="admin-feedback-message">{item.message}</th><td className="admin-feedback-account">{item.account_email || 'Not signed in'}</td><td>{new Date(item.submitted_at * 1000).toLocaleString()}</td><td>{item.status}</td><td><div className="admin-feedback-actions"><button type="button" className="admin-text-action admin-icon-action" disabled={busy || item.status === 'closed'} aria-pressed={item.status === 'reviewed'} aria-label={item.status === 'reviewed' ? 'Mark feedback unreviewed' : 'Mark feedback reviewed'} data-tooltip={item.status === 'reviewed' ? 'Mark unreviewed' : 'Mark reviewed'} onClick={() => void onUpdateFeedback(item, item.status === 'reviewed' ? 'new' : 'reviewed')}><svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/>{item.status === 'reviewed' && <path d="m8 12 3 3 5-6" strokeWidth="2.3"/>}</svg></button><button type="button" className="admin-text-action admin-remove admin-icon-action" disabled={busy} aria-label="Remove feedback" data-tooltip="Remove feedback" onClick={() => void onRemoveFeedback(item)}><AdminActionIcon kind="remove"/></button></div></td></tr>)}</tbody></table></div> : <p className="cloud-access-bootstrap">No product feedback.</p>}
      </details>
      <details className="admin-collapsible-section admin-authorized-users-section" open={authorizedUsersExpanded} onToggle={event => setAuthorizedUsersExpanded(event.currentTarget.open)}><summary><h3>Authorized users</h3><button ref={addButton} type="button" className="admin-text-action admin-icon-action admin-authorized-add" aria-label="Add authorized user or domain" data-tooltip="Add authorized user or domain" aria-expanded={addOpen} onClick={event => { event.preventDefault(); event.stopPropagation(); setAuthorizedUsersExpanded(true); setAddOpen(true); }}><CirclePlusIcon/></button></summary>
      <div className="admin-table-scroll admin-authorized-table-scroll"><table className="admin-grants-table admin-authorized-table"><colgroup><col style={{ width: '35%' }}/><col style={{ width: '14%' }}/><col style={{ width: '32%' }}/><col style={{ width: '19%' }}/></colgroup><thead><tr><th scope="col">Email / Domain</th><th scope="col">Role</th><th scope="col" className="admin-allowance-heading">Sponsorship allowance</th><th scope="col">Actions</th></tr></thead><tbody>
        {ordered.map(grant => {
          const key = `${grant.kind}:${grant.value}`; const draft = drafts[key] ?? { role: grant.role, allowance: allowanceInput(grant.allowance_usd) };
          const isBootstrap = grant.kind === 'email' && grant.value.toLowerCase() === bootstrapAdmin.toLowerCase();
          const account = grant.kind === 'email' ? sessions.find(item => item.email.toLowerCase() === grant.value.toLowerCase()) : undefined;
          const reloadable = !!account && grant.active === 1 && grant.role === 'member'
            && !hasDrafts && (account.spending?.reload_eligible ?? (account.spending?.reserved_and_estimated_usd ?? 0) > 0);
          return <tr key={key} className={grant.active ? '' : 'is-revoked'}>
            <th scope="row"><span className="admin-entry-value">{grant.value}</span><small>{grant.kind === 'email' ? 'Email' : 'Domain'}</small></th>
            <td>{grant.kind === 'domain' ? <span>Member</span> : <select aria-label={`Role for ${grant.value}`} value={draft.role} disabled={!grant.active || isBootstrap || busy} onChange={event => setDrafts(value => ({ ...value, [key]: { ...draft, role: event.target.value } }))}><option value="member">Member</option><option value="admin">Admin</option></select>}</td>
            <td className="admin-allowance-cell">{draft.role === 'admin' ? <span>Unlimited</span> : <><label className="admin-allowance-input"><span className="sr-only">Sponsorship allowance for {grant.value}</span><span aria-hidden="true">$</span><input type="text" inputMode="decimal" value={draft.allowance} disabled={!grant.active || busy} aria-invalid={!validation(draft.allowance)} aria-describedby={`allowance-${grant.kind}-${grant.value}`} onChange={event => setDrafts(value => ({ ...value, [key]: { ...draft, allowance: event.target.value } }))}/></label><small id={`allowance-${grant.kind}-${grant.value}`}>{validation(draft.allowance) ? `Effective ${currency(grant.effective_allowance_usd)}` : 'Enter $0.01 to $15.00'}</small></>}</td>
            <td><div className="admin-authorized-actions">{reloadable && <button type="button" className="admin-text-action admin-icon-action" aria-label={`Reload allowance for ${grant.value}`} data-tooltip="Reload allowance" disabled={busy} onClick={() => void reload(grant)}><AdminActionIcon kind="reload"/></button>}{grant.active === 1 && !isBootstrap && <button ref={element => { if (element) removeButtons.current.set(key, element); else removeButtons.current.delete(key); }} type="button" className="admin-text-action admin-remove admin-icon-action" aria-label={`Remove access for ${grant.value}`} data-tooltip="Remove access rule" aria-expanded={confirmRemoveKey === key} disabled={busy} onClick={() => setConfirmRemoveKey(current => current === key ? '' : key)}><AdminActionIcon kind="remove"/></button>}{isBootstrap && <span className="admin-protected-entry">Protected</span>}</div></td>
          </tr>;
        })}
        {!ordered.length && <tr><td colSpan={4} className="admin-empty-row">No authorization entries yet.</td></tr>}
      </tbody></table></div></details>
      {hasDrafts && <div className="admin-save-row"><p>{draftsValid ? `${changed.length} unsaved change${changed.length === 1 ? '' : 's'}.` : 'Correct invalid allowance values before saving.'}</p></div>}
      {(message || error) && <p role={error || message.includes('could not') ? 'alert' : 'status'} className="admin-feedback">{error || message}</p>}
      <details className="admin-collapsible-section admin-account-usage-section" open><summary><h3>Account usage</h3></summary>
      {sessions.length ? <div className="admin-table-scroll admin-account-usage-scroll"><table className="admin-usage-table"><thead><tr><th scope="col">Email</th><th scope="col">Access</th><th scope="col">Allowance</th><th scope="col">Estimated</th><th scope="col">Held</th><th scope="col">Remaining</th></tr></thead><tbody>{sessions.map(session => <tr key={session.email}><th scope="row">{session.email}</th><td>{session.status} · {session.role}</td><td>{session.role === 'admin' ? 'Unlimited' : currency(session.allowance_usd)}</td><td>{currency(session.spending?.estimated_usage_usd)}</td><td>{currency(session.spending?.held_usd)}</td><td>{session.role === 'admin' ? 'Unlimited' : currency(session.spending?.remaining_usd)}</td></tr>)}</tbody></table></div> : <p className="cloud-access-bootstrap">No account usage has been recorded.</p>}
      </details>
    </section>
    {addOpen && createPortal(<div ref={newEntryPanel} className="admin-new-entry-panel" role="group" aria-label="Add authorized user" style={newEntryPosition ? { left: newEntryPosition.left, top: newEntryPosition.top, maxHeight: newEntryPosition.maxHeight } : { left: -10000, top: -10000 }}>
      <div className="admin-new-entry-heading"><h3>New Email or Domain</h3><div className="admin-new-entry-actions"><button type="button" className="admin-text-action" disabled={busy || !newValue.trim() || (newRole !== 'admin' && !validation(newAllowance)) || newValue.includes('@') !== (newKind === 'email')} onClick={() => void addEntry()}>Add</button><DialogDismissButton label="Cancel adding access rule" disabled={busy} onClick={cancelAdd}/></div></div>
      <div className="admin-new-entry-classification"><label>Entry type<select value={newKind} onChange={event => setNewKind(event.target.value as 'email' | 'domain')}><option value="email">Email</option><option value="domain">Domain</option></select></label>{newKind === 'email' && <label>Role<select aria-label="New authorization role" value={newRole} onChange={event => setNewRole(event.target.value as 'member' | 'admin')}><option value="member">Member</option><option value="admin">Admin</option></select></label>}</div>
      <label>{newKind === 'email' ? 'Email address' : 'Domain'}<input aria-label={newKind === 'email' ? 'New email address' : 'New domain'} value={newValue} placeholder={newKind === 'email' ? 'person@example.org' : 'example.org'} onChange={event => setNewValue(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); void addEntry(); } }}/></label>
      {newKind === 'email' && newRole === 'admin' ? <p>Administrator sponsorship: Unlimited</p> : <label>ChatGPT allowance<span className="admin-allowance-input"><span aria-hidden="true">$</span><input aria-label="New ChatGPT allowance" type="text" inputMode="decimal" value={newAllowance} placeholder="Default" aria-invalid={!validation(newAllowance)} onChange={event => setNewAllowance(event.target.value)}/></span><small>Blank uses the configured default</small></label>}
    </div>, dialog.current ?? document.body)}
    {confirmRemoveKey && createPortal(<div ref={removeConfirmation} className="admin-remove-confirm" role="group" aria-label={`Confirm remove access for ${confirmRemoveKey.slice(confirmRemoveKey.indexOf(':') + 1)}`} style={removeConfirmationPosition ? { left: removeConfirmationPosition.left, top: removeConfirmationPosition.top } : { left: -10000, top: -10000 }}>
      <p>Remove access for {confirmRemoveKey.slice(confirmRemoveKey.indexOf(':') + 1)}?</p>
      <div className="admin-remove-confirm-actions"><button ref={removeConfirmButton} type="button" className="admin-text-action admin-remove" disabled={busy} onClick={() => { const grant = grants.find(item => `${item.kind}:${item.value}` === confirmRemoveKey); if (grant) void revoke(grant); }}>Confirm</button><DialogDismissButton label="Cancel access removal" disabled={busy} onClick={() => setConfirmRemoveKey('')}/></div>
    </div>, dialog.current ?? document.body)}
  </dialog>;
}

async function cloudFailure(response: Response, fallback: string) {
  let body: { error?: string; detail?: string } = {};
  try { body = await response.json() as typeof body; } catch { /* use a stable generic error */ }
  return new Error(body.error || (typeof body.detail === 'string' ? body.detail : fallback));
}

function CloudAuthGate() {
  const [status, setStatus] = useState<CloudStatus | null>(null);
  const [failure, setFailure] = useState('');
  const [accessOpen, setAccessOpen] = useState(false);
  const [grants, setGrants] = useState<CloudGrant[]>([]);
  const [accountSessions, setAccountSessions] = useState<CloudAccountSession[]>([]);
  const [invitationRequests, setInvitationRequests] = useState<CloudInvitationRequest[]>([]);
  const [feedbackRequests, setFeedbackRequests] = useState<CloudFeedbackRequest[]>([]);
  const [bootstrapAdmin, setBootstrapAdmin] = useState('');
  const [busy, setBusy] = useState(false);
  const [deniedIdentityAvailable, setDeniedIdentityAvailable] = useState(false);
  const [deniedInvitationStatus, setDeniedInvitationStatus] = useState<string | null>(null);
  const [budget, setBudget] = useState<CloudResearchBudget | null>(null);
  const [budgetEmail, setBudgetEmail] = useState<string | null>(null);
  const [budgetLoading, setBudgetLoading] = useState(false);
  const [budgetError, setBudgetError] = useState<string | null>(null);
  const [providerStatus, setProviderStatus] = useState<{ status: string; guidance: string } | null>(null);
  const [providerLoading, setProviderLoading] = useState(false);
  const [providerError, setProviderError] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [selectingConnection, setSelectingConnection] = useState(false);
  const [welcomeDismissedForPage, setWelcomeDismissedForPage] = useState(false);
  const [playSignInReturn, setPlaySignInReturn] = useState(() =>
    window.sessionStorage.getItem('sigma.playSignInReturn') === 'true'
  );
  const sponsoredMockSelected = useRef(false);
  const refresh = useCallback(async () => {
    try {
      await adoptLatestWindowSignIn();
      const response = await fetch('/api/cloud-auth/status', { credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok) throw new Error('Google sign-in could not be checked.');
      let current = await response.json() as CloudStatus;
      if (
        current.sponsored_test_mode
        && current.mock_auth
        && (!current.authenticated || current.mock_identity)
        && !sponsoredMockSelected.current
      ) {
        sponsoredMockSelected.current = true;
        const selected = await fetch('/api/cloud-auth/mock/select?identity=member-a', {
          method: 'POST', credentials: 'same-origin',
        });
        if (!selected.ok) throw new Error('Local sponsored test identity could not be selected.');
        const refreshed = await fetch('/api/cloud-auth/status', { credentials: 'same-origin', cache: 'no-store' });
        if (!refreshed.ok) throw new Error('Local sponsored test identity could not be checked.');
        current = await refreshed.json() as CloudStatus;
      }
      if (current.enabled && !current.authenticated && new URLSearchParams(window.location.search).get('access') === 'denied') {
        const denied = await fetch('/api/cloud-auth/denied', { credentials: 'same-origin', cache: 'no-store' });
        if (denied.ok) {
          const identity = await denied.json() as { identity_available?: boolean; invitation_status?: string | null; retry_signin?: boolean };
          if (identity.retry_signin === true) {
            // Authorization changed since this verified Google identity was
            // denied. Return through Google's standard account chooser.
            window.location.replace(windowAuthUrl('/api/cloud-auth/login'));
            return;
          }
          setDeniedIdentityAvailable(identity.identity_available === true);
          setDeniedInvitationStatus(identity.invitation_status ?? null);
        } else { setDeniedIdentityAvailable(false); setDeniedInvitationStatus(null); window.history.replaceState(null, '', '/'); }
      } else { setDeniedIdentityAvailable(false); setDeniedInvitationStatus(null); }
      setStatus(current); setFailure(current.ready ? '' : 'Google sign-in is not configured correctly.');
    } catch { setFailure('SIGMA could not check Google sign-in. Refresh this page or contact the administrator.'); }
  }, []);
  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 30_000);
    window.addEventListener('focus', refresh);
    window.addEventListener('sigma-cloud-auth-refresh', refresh);
    return () => { window.clearInterval(interval); window.removeEventListener('focus', refresh); window.removeEventListener('sigma-cloud-auth-refresh', refresh); };
  }, [refresh]);
  useEffect(() => {
    if (!playSignInReturn) return;
    if (status?.authenticated || window.location.pathname !== '/project') {
      window.sessionStorage.removeItem('sigma.playSignInReturn');
      if (window.location.pathname !== '/project') {
        window.sessionStorage.removeItem('sigma.resumeGuestPlay');
        setPlaySignInReturn(false);
      }
    }
  }, [playSignInReturn, status?.authenticated]);
  const loadGrants = useCallback(async () => {
    const [response, requestsResponse, feedbackResponse] = await Promise.all([
      fetch('/api/cloud-auth/admin/grants', { credentials: 'same-origin', cache: 'no-store' }),
      fetch('/api/cloud-auth/admin/invitation-requests', { credentials: 'same-origin', cache: 'no-store' }),
      fetch('/api/cloud-auth/admin/feedback', { credentials: 'same-origin', cache: 'no-store' }),
    ]);
    if (!response.ok) throw await cloudFailure(response, 'Access rules could not be loaded.');
    if (!requestsResponse.ok) throw await cloudFailure(requestsResponse, 'Invitation requests could not be loaded.');
    if (!feedbackResponse.ok) throw await cloudFailure(feedbackResponse, 'Product feedback could not be loaded.');
    const result = await response.json() as { grants: CloudGrant[]; sessions: CloudAccountSession[]; bootstrap_admin: string };
    const requestResult = await requestsResponse.json() as { requests: CloudInvitationRequest[] };
    const feedbackResult = await feedbackResponse.json() as { feedback: CloudFeedbackRequest[] };
    setGrants(result.grants); setAccountSessions(result.sessions); setBootstrapAdmin(result.bootstrap_admin); setInvitationRequests(requestResult.requests); setFeedbackRequests(feedbackResult.feedback);
  }, []);
  useEffect(() => {
    const target = status?.target ?? 'hosted';
    const email = status?.user?.email ?? null;
    setBudget(null); setBudgetEmail(null); setBudgetError(null);
    const canViewAllowance = !!status?.account?.sponsorship.eligible
      && status?.account?.model_access.mode === 'sponsored';
    if (!status?.enabled || !status.authenticated || !canViewAllowance) {
      setBudget(null); setBudgetLoading(false); setBudgetError(null); return;
    }
    let active = true;
    const fetchBudget = async () => {
      setBudgetLoading(true);
      try {
        const fundingPath = status?.mock_identity
          ? '/api/cloud-auth/mock/funding'
          : status?.target === 'local'
            ? '/api/cloud-auth/local-sponsored-allowance'
            : '/api/cloud-research/budget';
        const response = await fetch(fundingPath, { credentials: 'same-origin', cache: 'no-store' });
        if (!response.ok) throw await cloudFailure(response, 'ChatGPT allowance is unavailable.');
        let result: CloudResearchBudget;
        if (status?.mock_identity) {
          const mock = await response.json() as { allowance: { remaining_usd: number }; provider: string };
          result = { allowance_usd: mock.allowance.remaining_usd, estimated_usage_usd: 0, held_usd: 0, reserved_and_estimated_usd: 0, remaining_usd: mock.allowance.remaining_usd, unknown_provider_attempts: 0 };
          if (active) setProviderStatus({ status: mock.provider, guidance: 'Simulated local provider status.' });
        } else result = await response.json() as CloudResearchBudget;
        if (active) { setBudget(result); setBudgetEmail(email); setBudgetError(null); }
      } catch (cause) { if (active) setBudgetError(cause instanceof Error ? cause.message : 'ChatGPT allowance is unavailable.'); }
      finally { if (active) setBudgetLoading(false); }
    };
    void fetchBudget();
    const interval = window.setInterval(fetchBudget, 30_000);
    window.addEventListener('focus', fetchBudget);
    window.addEventListener('sigma-sponsored-budget-refresh', fetchBudget);
    return () => { active = false; window.clearInterval(interval); window.removeEventListener('focus', fetchBudget); window.removeEventListener('sigma-sponsored-budget-refresh', fetchBudget); };
  }, [status?.enabled, status?.authenticated, status?.target, status?.user?.email, status?.mock_auth, status?.account?.sponsorship.eligible, status?.account?.model_access.mode]);
  const refreshSponsoredConnection = useCallback(async () => {
    if (!status?.enabled || !status.authenticated || status.target !== 'hosted') return;
    setProviderLoading(true);
    setProviderError(null);
    try {
      const response = await fetch('/api/cloud-research/connection', { credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok) throw await cloudFailure(response, 'SIGMA-sponsored model access could not be checked.');
      const current = await response.json() as { provider?: SponsoredInferenceProvider; status: string; guidance: string };
      setProviderStatus(current);
    } catch (cause) {
      setProviderError(cause instanceof Error ? cause.message : 'SIGMA-sponsored model access could not be checked.');
    } finally { setProviderLoading(false); }
  }, [status?.enabled, status?.authenticated, status?.target, status?.account?.sponsorship.eligible]);
  useEffect(() => {
    setProviderStatus(null);
    if (status?.authenticated && status.target === 'hosted') void refreshSponsoredConnection();
  }, [status?.authenticated, status?.target, refreshSponsoredConnection]);
  async function addGrant(entry: { kind: 'email' | 'domain'; value: string; role: 'member' | 'admin'; allowance_usd: number | null }) {
    setBusy(true);
    try {
      const response = await fetch('/api/cloud-auth/admin/grants', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(entry) });
      if (!response.ok) throw await cloudFailure(response, 'Authorization could not be added.');
      await loadGrants();
    } finally { setBusy(false); }
  }
  async function saveGrants(updates: { kind: 'email' | 'domain'; value: string; role: 'member' | 'admin'; allowance_usd: number | null }[]) {
    setBusy(true);
    try {
      const response = await fetch('/api/cloud-auth/admin/grants/updates', { method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ updates }) });
      if (!response.ok) throw await cloudFailure(response, 'Updates could not be saved.');
      await loadGrants();
    } finally { setBusy(false); }
  }
  async function revokeGrant(grant: CloudGrant) {
    setBusy(true);
    try {
      const response = await fetch(`/api/cloud-auth/admin/grants/${grant.kind}/${encodeURIComponent(grant.value)}`, { method: 'DELETE', credentials: 'same-origin' });
      if (!response.ok) throw await cloudFailure(response, 'Authorization could not be revoked.');
      await loadGrants();
    } finally { setBusy(false); }
  }
  async function reloadGrantAllowance(grant: CloudGrant) {
    if (grant.kind !== 'email' || grant.role !== 'member') throw new Error('Reload is available for member email accounts.');
    setBusy(true);
    try {
      const response = await fetch(`/api/cloud-auth/admin/grants/reload/${encodeURIComponent(grant.value)}`, { method: 'POST', credentials: 'same-origin' });
      if (!response.ok) throw await cloudFailure(response, 'Sponsored allowance could not be reloaded.');
      await loadGrants();
    } finally { setBusy(false); }
  }
  async function updateInvitation(item: CloudInvitationRequest, next: 'reviewed' | 'declined') {
    setBusy(true);
    try {
      const response = await fetch(`/api/cloud-auth/admin/invitation-requests/${encodeURIComponent(item.subject)}`, { method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: next }) });
      if (!response.ok) throw await cloudFailure(response, 'Invitation request could not be updated.');
      setInvitationRequests(current => current.filter(request => request.subject !== item.subject));
    } finally { setBusy(false); }
  }
  async function updateFeedback(item: CloudFeedbackRequest, next: 'new' | 'reviewed') {
    setBusy(true);
    try {
      const response = await fetch(`/api/cloud-auth/admin/feedback/${encodeURIComponent(item.id)}`, { method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: next }) });
      if (!response.ok) throw await cloudFailure(response, 'Feedback could not be updated.');
      await loadGrants();
    } finally { setBusy(false); }
  }
  async function removeFeedback(item: CloudFeedbackRequest) {
    setBusy(true);
    try {
      const response = await fetch(`/api/cloud-auth/admin/feedback/${encodeURIComponent(item.id)}`, { method: 'DELETE', credentials: 'same-origin' });
      if (!response.ok) throw await cloudFailure(response, 'Feedback could not be removed.');
      setFeedbackRequests(current => current.filter(request => request.id !== item.id));
    } finally { setBusy(false); }
  }
  const selectConnection = useCallback(async (mode: 'personal' | 'sponsored') => {
    if (selectingConnection) return;
    setSelectingConnection(true); setConnectionError(null);
    try {
      const response = status?.mock_auth
        ? await fetch(`/api/cloud-auth/mock/model-access?mode=${encodeURIComponent(mode)}`, { method: 'POST', credentials: 'same-origin' })
        : await fetch('/api/ai/mode', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }) });
      if (!response.ok) throw await cloudFailure(response, 'Connection choice could not be saved.');
      await refresh();
      if (mode === 'sponsored') await refreshSponsoredConnection();
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : 'Connection choice could not be saved.';
      setConnectionError(detail);
      reportRequestFailure(detail);
      throw cause;
    } finally { setSelectingConnection(false); }
  }, [refresh, refreshSponsoredConnection, selectingConnection, status?.mock_auth]);
  const disconnectMockSponsored = useCallback(async () => {
    const next = providerStatus?.status === 'connected' ? 'unavailable' : 'connected';
    const response = await fetch(`/api/cloud-auth/mock/provider?scenario=${next}`, { method: 'POST', credentials: 'same-origin' });
    if (!response.ok) throw await cloudFailure(response, 'The simulated provider connection could not be changed.');
    setProviderStatus({ status: next, guidance: 'Simulated local provider status.' });
  }, [providerStatus?.status]);
  const funding: CloudFunding = { target: status?.target ?? 'local', authenticationEnabled: !!status?.enabled, googleAccount: status?.user?.email ?? null, budget, loading: budgetLoading, error: budgetError, authorized: !!status?.authenticated, sponsorshipEligible: !!status?.account?.sponsorship.eligible, sponsorshipUnlimited: status?.user?.role === 'admin', provider: providerStatus, providerLoading, providerError, retryProvider: refreshSponsoredConnection, selectedConnection: status?.account?.model_access.mode === 'sponsored' ? 'sponsored' : 'personal', forcedSponsored: !!status?.account?.sponsorship.forced, simulatedSponsored: !!status?.sponsored_test_mode && !!status?.mock_identity, disconnectMockSponsored, selectConnection, connectionError, selectingConnection };
  useEffect(() => {
    setSponsoredUsageConnection(funding.target === 'hosted' || funding.selectedConnection === 'sponsored');
  }, [funding.target, funding.selectedConnection]);
  const context: CloudIdentityState | null = status ? { ...status, deniedIdentityAvailable, deniedInvitationStatus, funding, openAccessManagement: () => { setAccessOpen(true); setFailure(''); void loadGrants().catch(error => setFailure(error instanceof Error ? error.message : 'Access rules could not be loaded.')); } } : null;
  const sharedInviteParams = new URLSearchParams(window.location.search);
  const inviteeEmail = window.location.pathname === '/project'
    ? (sharedInviteParams.get('invited_email') ?? '').trim().toLowerCase() : '';
  const inviteePath = sharedInviteParams.get('path') ?? '';
  const inviteeTitle = (sharedInviteParams.get('project_title') ?? '').slice(0, 200);
  const redirectSharedInvite = !!status?.enabled && !!inviteePath && inviteePath.length <= 2048
    && inviteeEmail.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(inviteeEmail)
    && (!status.authenticated || status.user?.role === 'guest'
      || status.user?.email.toLowerCase() !== inviteeEmail);
  useEffect(() => {
    if (!redirectSharedInvite) return;
    try {
      window.sessionStorage.setItem(SHARED_INVITE_KEY, JSON.stringify({ path: inviteePath, email: inviteeEmail, title: inviteeTitle }));
    } catch { /* Continue to Home even when storage is restricted. */ }
    // Never mount the inaccessible project screen for the wrong Google account.
    window.location.replace('/');
  }, [redirectSharedInvite, inviteePath, inviteeEmail, inviteeTitle]);
  const pendingSharedInvite = redirectSharedInvite || !!getPendingSharedInvite();
  const navigationEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
  const showSponsorWelcome = !!status?.account?.invitation_welcome_pending
    && !welcomeDismissedForPage && !pendingSharedInvite;
  const nonMemberIdentity = !!status?.enabled
    && ((status.authenticated && status.user?.role === 'guest')
      || (!status.authenticated && deniedIdentityAvailable));
  const invitationStatus = status?.authenticated
    ? status.account?.invitation_status
    : deniedInvitationStatus;
  const inviteParams = new URLSearchParams(window.location.search);
  const showNonMemberWelcome = nonMemberIdentity && !showSponsorWelcome && !pendingSharedInvite
    && window.location.pathname !== '/demo'
    && navigationEntry?.type !== 'reload'
    && navigationEntry?.type !== 'back_forward'
    && inviteParams.get('invite') !== '1'
    && inviteParams.get('show_invitation') !== '1'
    && !welcomeDismissedForPage;
  const showGuestWelcome = !!status?.enabled && !status?.authenticated && !pendingSharedInvite
    && !deniedIdentityAvailable
    && window.location.pathname !== '/demo'
    && navigationEntry?.type !== 'reload'
    && navigationEntry?.type !== 'back_forward'
    && window.sessionStorage.getItem('sigma.guestWelcomeDismissed') !== 'true'
    && !welcomeDismissedForPage;
  if (!status) return <main className="cloud-auth-shell"><p role="status">Checking access…</p></main>;
  if (redirectSharedInvite) return <main className="cloud-auth-shell"><p role="status">Opening SIGMA Home…</p></main>;
  if (!status.enabled) return <CloudIdentityContext.Provider value={context}><AIProvider><App/></AIProvider></CloudIdentityContext.Provider>;
  if (window.location.pathname === '/demo') return <CloudDemoExperience deniedIdentityAvailable={deniedIdentityAvailable} authenticated={status.authenticated} user={status.user}/>;
  return <CloudIdentityContext.Provider value={context}>
    <AIProvider unavailable={!status.authenticated || status.user?.role === 'guest'}><App/>
    {status.authenticated && showSponsorWelcome && <InvitationWelcomeDialog
      audience={status.account?.sponsorship.eligible ? 'sponsored' : 'invited'}
      allowance={budgetEmail === status.user?.email ? budget?.remaining_usd ?? null : null}
      allowanceUsed={budgetEmail === status.user?.email && budget ? budget.estimated_usage_usd + budget.held_usd : 0}
      allowanceLoading={budgetLoading && budgetEmail !== status.user?.email}
      onDismiss={async () => { setWelcomeDismissedForPage(true); await refresh(); }}
    />}
    {showNonMemberWelcome && <InvitationWelcomeDialog
      audience={hasOpenInvitationRequest(invitationStatus) ? 'returning' : 'nonmember'}
      allowance={null}
      allowanceUsed={0}
      allowanceLoading={false}
      onDismiss={async () => { setWelcomeDismissedForPage(true); }}
    />}
    {showGuestWelcome && <InvitationWelcomeDialog
      audience="guest"
      allowance={null}
      allowanceUsed={0}
      allowanceLoading={false}
      onDismiss={async () => { window.sessionStorage.setItem('sigma.guestWelcomeDismissed', 'true'); setWelcomeDismissedForPage(true); }}
    />}
    {accessOpen && status.authenticated && status.user?.role === 'admin' && <AccessManagementDialog bootstrapAdmin={bootstrapAdmin} grants={grants} sessions={accountSessions} invitationRequests={invitationRequests} feedbackRequests={feedbackRequests} error={failure} busy={busy} onClose={() => setAccessOpen(false)} onAdd={addGrant} onSave={saveGrants} onRevoke={revokeGrant} onReload={reloadGrantAllowance} onUpdateInvitation={updateInvitation} onUpdateFeedback={updateFeedback} onRemoveFeedback={removeFeedback}/>}
    </AIProvider>
  </CloudIdentityContext.Provider>;
}

function InvitationWelcomeDialog({ audience, allowance, allowanceUsed, allowanceLoading, onDismiss }: {
  audience: 'guest' | 'nonmember' | 'returning' | 'requested' | 'invited' | 'sponsored';
  allowance: number | null; allowanceUsed: number; allowanceLoading: boolean;
  onDismiss: () => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [invitationRequested, setInvitationRequested] = useState(false);
  const [phrase] = useState(() => invitationWelcomePhrases[Math.floor(Math.random() * invitationWelcomePhrases.length)]);
  useEffect(() => {
    if (dialog.current && !dialog.current.open) dialog.current.showModal();
    return () => { if (dialog.current?.open) dialog.current.close(); };
  }, []);
  async function dismiss() {
    if (busy) return;
    setBusy(true); setError('');
    try {
      if (audience !== 'guest' && audience !== 'nonmember' && audience !== 'returning' && audience !== 'requested') {
        const response = await fetch('/api/cloud-auth/welcome', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        if (!response.ok) throw await cloudFailure(response, 'Your invitation welcome could not be saved.');
      }
      await onDismiss();
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  const heading = audience === 'requested' ? 'Your invitation request is in!' : audience === 'guest' || audience === 'nonmember' || audience === 'returning'
    ? 'Welcome to SIGMA!' : 'You have been invited!';
  const allowanceMessage = allowance === null || allowance > 1
    ? null
    : audience === 'sponsored'
      ? `You have $${allowance.toFixed(2)} remaining in your sponsored allowance.`
      : allowanceUsed > 0
        ? `We added $${allowance.toFixed(2)} to your account.`
        : `We will start you off with a $${allowance.toFixed(2)} allowance.`;
  return <dialog id="invitation-welcome-dialog" ref={dialog} className="google-account-dialog invitation-welcome-dialog" aria-labelledby="invitation-welcome-heading" aria-describedby="invitation-welcome-phrase" onClick={event => { if (event.target === event.currentTarget) void dismiss(); }} onCancel={event => { event.preventDefault(); void dismiss(); }}>
    <h2 id="invitation-welcome-heading">{heading}</h2>
    {allowanceMessage && <p className="invitation-welcome-allowance">{allowanceMessage}</p>}
    {allowanceLoading && <p className="invitation-welcome-allowance" role="status">Checking your sponsored allowance…</p>}
    {audience === 'guest' && <p className="invitation-welcome-intro">Welcome to SIGMA. Explore samples, create private temporary projects, edit strategies and inspect project research without signing in. Your drafts last only for this browser session and can be exported. Running AI research requires authorized membership and an available provider.</p>}
    {audience === 'nonmember' && <p className="invitation-welcome-intro">Your Google account does not yet have SIGMA membership. Request an invitation to join the research workspace, or explore as a guest while an administrator reviews your request.</p>}
    {audience === 'returning' && <p className="invitation-welcome-intro">Your invitation request is in! We're looking forward to welcoming you as a member. In the meantime, feel free to explore as a guest.</p>}
    {audience === 'requested' && <p className="invitation-welcome-intro">We've received your request and will get back to you soon. In the meantime, feel free to explore SIGMA as a guest.</p>}
    {audience === 'sponsored' && <p className="invitation-welcome-intro">SIGMA tracks your sponsored allowance as you use ChatGPT. When you’re ready, you can connect your own ChatGPT account from the Sponsored ChatGPT pill.</p>}
    {audience === 'invited' && <p className="invitation-welcome-intro">Welcome to SIGMA.</p>}
    <p className="invitation-welcome-about-hint">New to SIGMA? Open the About SIGMA pill for a quick guide to how it works.</p>
    <p id="invitation-welcome-phrase" className="invitation-welcome-phrase">{phrase}</p>
    {error && audience !== 'nonmember' && <p role="alert">{error}</p>}
    {audience === 'nonmember' && invitationRequested && <p className="invitation-welcome-requested" role="status">Your invitation request is recorded and awaiting administrator review.</p>}
    {audience === 'nonmember'
      ? <div className="invitation-welcome-actions">
          {!invitationRequested && <InvitationRequestControls
            error={error}
            onError={setError}
            onRecorded={() => {
              // The request is complete: close the welcome before refreshing
              // invitation status, rather than replacing it with another welcome.
              setInvitationRequested(true);
              window.dispatchEvent(new Event('sigma-invitation-recorded'));
              void dismiss().then(() => {
                window.dispatchEvent(new Event('sigma-cloud-auth-refresh'));
              });
            }}
            buttonLabel="Request invitation"
            buttonClassName="invitation-welcome-link"
          />}
          <button type="button" className="invitation-welcome-link" disabled={busy} onClick={() => void dismiss()}>{busy ? 'Saving…' : 'Explore as guest'}</button>
        </div>
      : <button type="button" className={audience === 'requested' ? 'invitation-welcome-link' : 'google-text-action invitation-welcome-dismiss'} disabled={busy} onClick={() => void dismiss()}>{busy ? 'Saving…' : audience === 'requested' ? 'Continue as guest' : "Let's get started"}</button>}
  </dialog>;
}

function PrivacyNoticeContent() {
  return <div className="privacy-notice-content">
    <p><strong>Prepared October 26, 2026 · Version 1.0</strong></p>
    <p>This notice describes the information SIGMA handles when you use the hosted research workspace.</p>
    <h2>Information SIGMA stores</h2>
    <p>When you sign in with Google, SIGMA receives your stable Google account identifier and verified email address. SIGMA stores them with your access role, whether access is active, assigned workspace, sponsored eligibility, selected model-access mode, and connection status. The hosted sign-in session is represented by a browser cookie and a hashed session token in SIGMA's authentication database. Sessions last up to eight hours. Sign-in flow data expires after five minutes; a temporary denied-sign-in record expires after ten minutes.</p>
    <p>If you request an invitation, SIGMA stores your Google account identifier, verified email, request time, and request/notification/review status. SIGMA sends your verified email and request time through its configured mail service to the SIGMA invitation administrator. If you send product feedback, SIGMA stores your message, submission time, status, and contact email. When signed in, the contact email is your verified Google sign-in email; signed-out visitors may provide an optional unverified contact email. The signed-in feedback record is associated with your account identifier and email. Feedback is reviewed in SIGMA's administrator interface; it is not sent to an AI or mail provider. Feedback submissions are limited to five per 24 hours per signed-in account or signed-out browser.</p>
    <p>Your account workspace can contain project titles and questions, project settings, strategies, research prompts and results, evidence, uploaded or imported project files, code and execution output, analyses, reports, and generated papers. SIGMA also stores research-session identifiers and sponsored-service accounting records, including reserved and estimated usage, call status, and token counts when the provider returns them. Usage estimates are used to enforce SIGMA spending limits and may differ from a provider's final bill.</p>
    <h2>How SIGMA uses and shares information</h2>
    <p>SIGMA uses your Google account information to sign you in, apply access rules, and keep your projects in your account workspace. SIGMA administrators can review invitation requests and product feedback, including any optional contact email.</p>
    <p>When you run an AI research feature, SIGMA sends the prompt and the project context required or selected for that action to the configured AI provider. In hosted sponsored mode, requests are sent to OpenAI using SIGMA's server-side service credential. The provider returns a response to SIGMA, and research results are retained in the project. Do not include information in a research request that you do not want sent to the selected provider.</p>
    <p>For an invitation request, SIGMA's configured mail service receives the verified email and request time so it can notify the invitation administrator. Product feedback is not included in invitation email. SIGMA does not send feedback messages to AI providers.</p>
    <h2>Where information is stored and how long it remains</h2>
    <p>In hosted SIGMA, authentication, access, invitation, and feedback records are kept in server-side SQLite databases. Each signed-in account has a separate server-side workspace for its projects and research files. Sponsored usage records are kept in a server-side accounting ledger. The service stores these in its configured persistent storage; the exact physical hosting location and backup schedule are set by the operator.</p>
    <p>SIGMA has no general time-based deletion schedule for account, invitation, feedback, research, or sponsored-usage records. Signing out ends your browser session but does not erase these records. Project controls can remove project data where available, but the hosted service does not currently offer a control that deletes all information associated with an account. If the operator makes backups, copies may remain according to the operator's backup schedule.</p>
    <h2>Cookies and account controls</h2>
    <p>Hosted sign-in uses Secure, HttpOnly, SameSite=Lax cookies for the sign-in flow and session. The session cookie expires after eight hours; the short-lived sign-in and denied-access cookies expire after five and ten minutes respectively. The feedback form uses a random, HttpOnly cookie to apply its five-per-day limit to signed-out browsers. Signing out removes the active session; it does not delete saved projects or records described above. For a request about your account data, contact the SIGMA administrator who invited you.</p>
  </div>;
}

function TermsOfServiceContent() {
  const [phrase] = useState(() => invitationWelcomePhrases[Math.floor(Math.random() * invitationWelcomePhrases.length)]);
  return <div className="terms-of-service-copy">
    <p>No terms except to discover something interesting, wonderous, or pioneering.</p>
    <p className="terms-welcome-phrase">{phrase}</p>
  </div>;
}

function PrivacyNoticePage() {
  useEffect(() => { document.title = 'Privacy notice · SIGMA'; }, []);
  function closeNotice() {
    const params = new URLSearchParams(window.location.search);
    const returnTo = params.get('return_to');
    if (returnTo && returnTo.startsWith('/') && !returnTo.startsWith('//')) {
      const destination = new URL(returnTo, window.location.origin);
      if (destination.origin === window.location.origin) {
        if (params.get('return_dialog') === 'invitation' && destination.searchParams.get('access') !== 'denied') {
          destination.searchParams.set('show_invitation', '1');
        } else if (params.get('return_dialog') === 'about') {
          destination.searchParams.set('show_about', '1');
        }
        window.location.assign(`${destination.pathname}${destination.search}${destination.hash}`);
        return;
      }
    }
    window.location.assign('/');
  }
  return <main className="cloud-auth-shell privacy-notice-shell"><article className="cloud-auth-card privacy-notice-card">
    <div className="privacy-notice-heading"><h1>SIGMA Privacy Notice</h1><DialogDismissButton label="Close privacy notice" onClick={closeNotice}/></div>
    <p><strong>Prepared October 26, 2026 · Version 1.0</strong></p>
    <p>This notice describes the information SIGMA handles when you use the hosted research workspace.</p>
    <h2>Information SIGMA stores</h2>
    <p>When you sign in with Google, SIGMA receives your stable Google account identifier and verified email address. SIGMA stores them with your access role, whether access is active, assigned workspace, sponsored eligibility, selected model-access mode, and connection status. The hosted sign-in session is represented by a browser cookie and a hashed session token in SIGMA's authentication database. Sessions last up to eight hours. Sign-in flow data expires after five minutes; a temporary denied-sign-in record expires after ten minutes.</p>
    <p>If you request an invitation, SIGMA stores your Google account identifier, verified email, request time, and request/notification/review status. SIGMA sends your verified email and request time through its configured mail service to the SIGMA invitation administrator. If you send product feedback, SIGMA stores your message, submission time, status, and contact email. When signed in, the contact email is your verified Google sign-in email; signed-out visitors may provide an optional unverified contact email. The signed-in feedback record is associated with your account identifier and email. Feedback is reviewed in SIGMA's administrator interface; it is not sent to an AI or mail provider. Feedback submissions are limited to five per 24 hours per signed-in account or signed-out browser.</p>
    <p>Your account workspace can contain project titles and questions, project settings, strategies, research prompts and results, evidence, uploaded or imported project files, code and execution output, analyses, reports, and generated papers. SIGMA also stores research-session identifiers and sponsored-service accounting records, including reserved and estimated usage, call status, and token counts when the provider returns them. Usage estimates are used to enforce SIGMA spending limits and may differ from a provider's final bill.</p>
    <h2>How SIGMA uses and shares information</h2>
    <p>SIGMA uses your Google account information to sign you in, apply access rules, and keep your projects in your account workspace. SIGMA administrators can review invitation requests and product feedback, including any optional contact email.</p>
    <p>When you run an AI research feature, SIGMA sends the prompt and the project context required or selected for that action to the configured AI provider. In hosted sponsored mode, requests are sent to OpenAI using SIGMA's server-side service credential. The provider returns a response to SIGMA, and research results are retained in the project. Do not include information in a research request that you do not want sent to the selected provider.</p>
    <p>For an invitation request, SIGMA's configured mail service receives the verified email and request time so it can notify the invitation administrator. Product feedback is not included in invitation email. SIGMA does not send feedback messages to AI providers.</p>
    <h2>Where information is stored and how long it remains</h2>
    <p>In hosted SIGMA, authentication, access, invitation, and feedback records are kept in server-side SQLite databases. Each signed-in account has a separate server-side workspace for its projects and research files. Sponsored usage records are kept in a server-side accounting ledger. The service stores these in its configured persistent storage; the exact physical hosting location and backup schedule are set by the operator.</p>
    <p>SIGMA has no general time-based deletion schedule for account, invitation, feedback, research, or sponsored-usage records. Signing out ends your browser session but does not erase these records. Project controls can remove project data where available, but the hosted service does not currently offer a control that deletes all information associated with an account. If the operator makes backups, copies may remain according to the operator's backup schedule.</p>
    <h2>Cookies and account controls</h2>
    <p>Hosted sign-in uses Secure, HttpOnly, SameSite=Lax cookies for the sign-in flow and session. The session cookie expires after eight hours; the short-lived sign-in and denied-access cookies expire after five and ten minutes respectively. The feedback form uses a random, HttpOnly cookie to apply its five-per-day limit to signed-out browsers. Signing out removes the active session; it does not delete saved projects or records described above. For a request about your account data, contact the SIGMA administrator who invited you.</p>
  </article></main>;
}

function TermsOfServicePage() {
  const [phrase] = useState(() => invitationWelcomePhrases[Math.floor(Math.random() * invitationWelcomePhrases.length)]);
  useEffect(() => { document.title = 'Terms of Service · SIGMA'; }, []);
  return <main className="cloud-auth-shell terms-of-service-shell" onClick={event => { if (event.target === event.currentTarget) window.location.assign('/'); }}><article className="cloud-auth-card privacy-notice-card terms-of-service-card">
    <div className="privacy-notice-heading"><h1>Terms of Service</h1><DialogDismissButton label="Close terms of service" onClick={() => { window.location.assign('/'); }}/></div>
    <div className="terms-of-service-copy">
      <p>No terms except to discover something interesting, wonderous, or pioneering.</p>
      <p className="terms-welcome-phrase">{phrase}</p>
    </div>
  </article></main>;
}


installRequestErrorToasts();
createRoot(document.getElementById('root')!).render(window.location.pathname === '/privacy' ? <PrivacyNoticePage/> : window.location.pathname === '/tos' ? <TermsOfServicePage/> : new URLSearchParams(window.location.search).has('session_log') ? <SessionLogPage/> : <><CloudAuthGate/><RequestErrorToasts/></>);
