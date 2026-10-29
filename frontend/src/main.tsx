import { createContext, lazy, Suspense, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type FormEvent, type MouseEvent, type PointerEvent as ReactPointerEvent, type Ref, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import SessionLogPage from './SessionLogPage';
import SessionLogButton from './SessionLogButton';
import { createRoot } from 'react-dom/client';
import './style.css';
import './workspace.css';
import './project-entry.css';
import './strategies.css';
import './project-settings.css';
import './recents.css';
import './copper-controls.css';
import './text-views.css';
import { AIProvider, ConnectionStatus, ManageUsage, PlanWelcome, beginProviderRequest, watchResearchProviderActivity, useAI } from './ai-connection';
import { installRequestErrorToasts, reportRequestFailure, RequestErrorToasts } from './request-toast';
import { invitationWelcomePhrases } from './invitation-welcome-phrases';
import AboutProvenanceVision from './about-provenance';
const RenderedMarkdown = lazy(() => import('./RenderedMarkdown'));

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
type ResearchMode = 'biology' | 'chemistry' | 'computer_science' | 'economics' | 'engineering' | 'law' | 'mathematical' | 'military' | 'philosophy' | 'physics' | 'religion' | 'default';
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
  { value: 'mathematical', label: 'Mathematics' },
  { value: 'military', label: 'Military' },
  { value: 'philosophy', label: 'Philosophy' },
  { value: 'physics', label: 'Physics' },
  { value: 'religion', label: 'Religion' },
  { value: 'default', label: 'Other' },
];
const researchTypeLabels = Object.fromEntries(researchTypes.map(item => [item.value, item.label])) as Record<ResearchMode, string>;
const researchTypeLabel = (value: string | null | undefined) => value && value in researchTypeLabels ? researchTypeLabels[value as ResearchMode] : 'Unavailable';
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
    schema_version: number;
    ai_model: string;
    reasoning_effort: string;
    difficulty: ProjectDifficulty | null;
    show_advanced_outcome_details: boolean;
    investigation_type: ResearchMode;
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
type ResearchStrategyRun = { strategy_id: string; strategy_title: string; status: string; current_action: string; current_question: string; cycle: number; calls_used: number; artifacts: string[]; reason?: string | null };
type PortfolioStrategyAction = { strategy_id: string; strategy_title: string; action: string; rationale: string; basis_artifact_ids: string[]; next_question: string };
type PortfolioCombination = { strategy_ids: string[]; basis_artifact_ids: string[]; rationales: string[]; status: string };
type PortfolioRelation = { source_strategy_id: string; source_artifact_id: string; target_strategy_id: string; target_artifact_id: string; relation: string; rationale: string };
type PortfolioDecision = { status?: string; strategy_actions?: PortfolioStrategyAction[]; combination_candidates?: PortfolioCombination[]; conflict_candidates?: PortfolioRelation[]; overlap_warnings?: PortfolioRelation[]; limitations?: string[] };
type OutcomeMetric = { label: string; value: string; detail?: string };
type ResearchOutcomeMetrics = { operational: OutcomeMetric[]; research_quality: OutcomeMetric[]; sources: { session_id: string | null; step_ids: string[]; artifact_ids: string[]; execution_ids: string[]; strategy_ids: string[] } };
type OutcomeArgumentStep = { number: number; title: string; argument: string; epistemic_status: string; basis_artifact_ids: string[]; research_artifact_id?: string; review?: { disposition: string; rationale: string; objection?: string; basis_artifact_ids: string[] } };
type StrategyFinding = { strategy_id: string; strategy_title: string; status: string; execution_status?: string; failure_reason?: string; claim: string; research_artifact_id: string; research_artifact_ids?: string[]; reasoning_steps: OutcomeArgumentStep[]; skeptic_response: string; objections: string[]; open_obligations: string[] };
type ExecutionProvenance = { records: { id: string; runtime: string; statuses: string[]; artifact_ids: string[]; step_ids: string[]; source_recorded: boolean; output_recorded: boolean }[]; unidentified_count: number; completed_count: number; completed_without_recorded_io_count?: number; other_count: number; note: string };
type ResearchOutcome = { assessment: 'pending' | 'positive' | 'mixed' | 'negative'; label: string; verification_label?: string; argument_availability?: { status: 'structured' | 'narrative' | 'not_recorded'; label: string }; summary?: string; conclusion?: string; caveats?: string[]; basis_artifact_ids?: string[]; provisional: boolean; execution_provenance?: ExecutionProvenance; metrics?: ResearchOutcomeMetrics; solution_review?: { status: string; claim?: string; claim_scope?: 'conditional' | 'unconditional' | 'disputed'; argument_summary?: string; skeptic_response?: string; skeptic_objections?: string[]; open_obligations?: string[]; argument_steps?: OutcomeArgumentStep[]; strategy_findings?: StrategyFinding[]; assumptions?: string[]; proof_obligations?: string[]; verification_status?: string; unresolved_objections?: string[]; resolved_objections?: string[]; basis_artifact_ids?: string[] } | null };
type StrategyAssessment = { strategy_id: string | null; strategy_title: string; assessment: 'contributed_to_solution' | 'productive' | 'unproductive' | 'not_used' | 'disabled' | 'unknown'; rationale: string; basis_artifact_ids: string[] };
type ResearchSession = { approved_continuations?: Record<string, { parent_strategy_id: string; question: string; packet_digest: string; sources: { artifact_id: string; source: EvidencePointer; status: string; verification: string; claim: string; strategy_title: string; artifact: Record<string, unknown> }[]; rejected_sources: { artifact_id: string; rationale: string }[] }>; id: string; project_id?: string; problem?: string; session_number: number; strategy_id: string; strategy_title: string; strategy_text?: string; strategy_ids?: string[]; strategy_snapshot?: Record<string, unknown>; strategy_runs?: ResearchStrategyRun[]; portfolio_decision?: PortfolioDecision | null; peer_handoffs_prompted?: unknown[]; interventions?: ResearchIntervention[]; status: 'queued' | 'running' | 'paused' | 'stopped' | 'completed' | 'ended' | 'failed'; model: string; reasoning_effort: string; mode: string; calls_used: number; call_limit: number; cycle: number; cycle_limit?: number; current_question: string; current_action: string; message: string; next_step_guidance?: string; artifacts: ResearchArtifact[]; prior_session_findings?: PriorSessionFinding[]; strategy_assessments?: StrategyAssessment[]; steps: ResearchStep[]; events: ResearchEvent[]; created_at: string; updated_at: string; started_at?: string; elapsed_seconds?: number; output_token_limit?: number; tokens_used?: number | null; token_usage_status?: string; estimated_cost_usd?: number | null; cost_status?: string; outcome: ResearchOutcome };

function sessionEstimatedCostLabel(session: ResearchSession): string {
  const cost = session.estimated_cost_usd;
  // ChatGPT tokens are not billed to the operator's API account; show the
  // model-priced equivalent, never imply this was a paid API charge.
  const label = session.mode === 'chatgpt' ? 'API-rate equivalent' : 'Est. cost';
  if (session.cost_status !== 'available' || typeof cost !== 'number' || !Number.isFinite(cost) || cost < 0) {
    return `${label} unavailable`;
  }
  // Avoid reporting nonzero usage as $0.00 after rounding.
  return cost > 0 && cost < 0.01 ? `${label} <$0.01` : `${label} $${cost.toFixed(2)}`;
}

function liveResearchSummary(session: ResearchSession): string | null {
  if (session.status !== 'running') return null;
  const action = session.current_action?.trim();
  const question = session.current_question?.trim();
  const source = [action, question].filter(Boolean).join(': ');
  if (!source) return null;
  const words = source.replace(/\s+/g, ' ').split(' ');
  return words.length > 50 ? `${words.slice(0, 50).join(' ')}…` : source.replace(/\s+/g, ' ');
}

function outcomeDisplayLabel(session: ResearchSession): string {
  const liveSummary = liveResearchSummary(session);
  return liveSummary ?? `${session.outcome.label}${session.outcome.provisional ? ' · provisional' : ''}`;
}

function stoppedSessionGuidance(session: ResearchSession): { cause: string; next: string } {
  const action = session.current_action.toLowerCase();
  const message = session.message.trim();
  const typedReason = [...session.steps].reverse().find(step => step.failure_kind || step.interruption_reason);
  const recordedReason = [message, typedReason?.failure_kind, typedReason?.interruption_reason].filter(Boolean).join(' · ')
    .replace(/\bpaused\b/gi, 'stopped').replace(/\bpausing\b/gi, 'stopping').replace(/\bpause\b/gi, 'stop');
  const hasCompleteFinding = session.artifacts.some(artifact =>
    Object.keys(artifact.investigator_output).length > 0 && Object.keys(artifact.skeptic_output).length > 0);
  const evidence = `${action} ${recordedReason}`;
  if (/context|token limit/.test(evidence))
    return { cause: 'This session stopped because its required context exceeded the available context limit. Saved research is preserved.', next: 'Review the saved evidence and context limits before resuming. Resume will remain subject to the backend context guard.' };
  if (/duration|wall.clock/.test(evidence))
    return { cause: 'This session stopped after reaching its configured elapsed-time limit. Saved research is preserved.', next: 'Adjust the project time limit if appropriate, then resume the session.' };
  if (/cost|budget/.test(evidence))
    return { cause: 'This session stopped after reaching a configured cost or call budget limit. Saved research is preserved.', next: 'Review the project limits and usage before resuming.' };
  if (/model|connection|billing identity/.test(evidence))
    return { cause: 'The selected model or AI connection changed while this session was stopped. Saved research is preserved.', next: 'Check the AI connection and selected model before resuming.' };
  if (/project|strategy/.test(evidence))
    return { cause: 'The project or one of its strategies changed while this session was stopped. Saved research is preserved.', next: 'Review the current project and strategy before resuming.' };
  if (/restart|interrupted/.test(evidence))
    return { cause: 'The session was interrupted when its backend work stopped. Saved research is preserved.', next: 'Resume when you are ready; a previously dispatched provider request may already have used allowance.' };
  if (/stopped by user|stopped by you/i.test(recordedReason))
    return { cause: recordedReason, next: 'Resume when you are ready. A previously dispatched provider request may still consume allowance.' };
  if (recordedReason) return { cause: recordedReason, next: 'Review the stop details above, then resume when the project and AI connection are ready. Backend safeguards still apply.' };
  if (!hasCompleteFinding) return { cause: 'The session was stopped before it saved a complete finding.', next: 'Resume when you are ready; backend safeguards still apply.' };
  return { cause: 'The session is stopped. Saved research is preserved.', next: 'Review the saved findings, then resume when the project and AI connection are ready. Backend safeguards still apply.' };
}
type EvidencePointer = { project_id: string; session_id: string; session_number: number; strategy_id: string; artifact_id: string; artifact_sequence: number; record_path: string; available: boolean };
type CurrentFinding = { id: string; text: string; investigated_claim: string; source: EvidencePointer; status: string; verification: string; strategy_title: string; objections: string[]; evidence_kind: string };
type CurrentQuestion = { id: string; text: string; status: string; actionable: boolean; sources: EvidencePointer[]; narrative_resolution_sources: EvidencePointer[]; note: string; dispositions: { source: EvidencePointer; valid: boolean; rationale: string }[] };
type CurrentUnderstanding = { version: number; project_id: string; session_count: number; project_status: string; scope_note: string; findings: CurrentFinding[]; current_finding_ids: string[]; obligations: CurrentQuestion[]; changes: { kind: string; text: string; source: EvidencePointer; earlier: EvidencePointer | null; caution: string }[]; next_investigations: { obligation_id: string; question: string; source: EvidencePointer; qualification: string }[]; failures: { session_id: string; session_number: number; status: string; note: string }[]; limitations: string[] };
type ResearchLimits = { research_rounds: number; model_calls: number; session_duration_minutes: number; output_tokens_per_call: number; maximum_estimated_cost_usd: number | null; maximum_input_tokens_per_session?: number | null; max_concurrent_sessions: string };
type DurationUnit = 'minutes' | 'hours' | 'days';
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
type ResearchLimitsDraft = { research_rounds: string; model_calls: string; session_duration_value: string; session_duration_unit: DurationUnit; output_tokens_per_call: string; maximum_estimated_cost_usd: string; maximum_input_tokens_per_session: string; max_concurrent_sessions: string };
function outcomeArtifactReferences(ids: string[] | undefined, session: ResearchSession): string {
  return ids?.map(id => `Artifact ${session.artifacts.find(artifact => artifact.id === id)?.sequence ?? '?'}`).join(', ') || 'No artifact references';
}

// Labels come from the shared Python research-epistemics projection, including exports.
function outcomeVerificationLabel(outcome: ResearchOutcome): string {
  return outcome.verification_label || 'Not recorded';
}
function outcomeArgumentLabel(outcome: ResearchOutcome): string {
  return outcome.argument_availability?.label || 'Argument availability was not recorded; inspect the saved research artifacts.';
}

function researchOutcomeMarkdown(session: ResearchSession): string {
  const outcome = session.outcome;
  const lines = [outcome.summary || 'No outcome summary was recorded.'];
  if (outcome.basis_artifact_ids?.length) lines.push('', `**Outcome evidence:** ${outcomeArtifactReferences(outcome.basis_artifact_ids, session)}`);
  const review = outcome.solution_review;
  if (review) {
    lines.push('', '### Solution review', '', `**Investigated:** ${session.problem || 'Project objective unavailable in this historical record.'}`, '', `**Bounded strategy:** ${session.strategy_text || session.strategy_title || 'Strategy details unavailable.'}`, '', `**Solution claim:** ${review.claim || 'No solution claim recorded.'}`, '', `**Argument:** ${review.argument_summary || 'No argument summary recorded.'}`, '', `**Skeptic response:** ${review.skeptic_response || 'No substantive Skeptic response recorded.'}`, '', `**Assumptions:** ${review.assumptions?.join(' · ') || 'None recorded'}`, '', `**Proof obligations considered:** ${review.proof_obligations?.join(' · ') || 'None recorded'}`, '', `**Still open:** ${review.open_obligations?.join(' · ') || 'None recorded'}`, '', `**Evidence:** ${outcomeArtifactReferences(review.basis_artifact_ids, session)}`);
    if (review.argument_steps?.length) lines.push('', '### Reviewed reasoning', '', ...review.argument_steps.flatMap(step => [`#### ${step.number}. ${step.title}`, '', `**Kind:** ${step.epistemic_status}`, '', step.argument, '', `**Skeptic review:** ${step.review?.disposition || 'Not recorded'} — ${step.review?.rationale || 'No rationale recorded'}`, ...(step.review?.objection ? ['', `**Objection:** ${step.review.objection}`] : []), '', `**Sources:** ${outcomeArtifactReferences([...(step.basis_artifact_ids || []), ...(step.research_artifact_id ? [step.research_artifact_id] : [])], session)}`, '']));
    else lines.push('', '### Reviewed reasoning', '', outcomeArgumentLabel(outcome));
    if ((review.strategy_findings?.length ?? 0) > 0) lines.push('', '### Findings by strategy', '', ...review.strategy_findings!.flatMap(item => [`#### ${item.strategy_title} · ${item.status}`, '', item.claim, ...(item.execution_status ? ['', `**Execution status:** ${item.execution_status}`] : []), ...(item.failure_reason ? [`**Failure detail:** ${item.failure_reason}`] : []), '', ...item.reasoning_steps.flatMap(step => [`**${step.number}. ${step.title} (${step.epistemic_status}):** ${step.argument}`, `**Review:** ${step.review?.disposition || 'Not recorded'} — ${step.review?.rationale || item.skeptic_response}`, '']), ...(item.objections.length ? [`**Objections:** ${item.objections.join(' · ')}`] : []), ...(item.open_obligations.length ? [`**Open obligations:** ${item.open_obligations.join(' · ')}`] : []), `**Sources:** ${outcomeArtifactReferences(item.research_artifact_ids?.length ? item.research_artifact_ids : (item.research_artifact_id ? [item.research_artifact_id] : []), session)}`, '']));
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
  if (!review) return 'No structured reasoning or proof review was saved for this session.';
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
      `### ${step.number}. ${step.title} · ${step.epistemic_status}`, '', step.argument, '',
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
        `### ${step.number}. ${step.title} · ${step.epistemic_status}`, '', step.argument, '',
        `**Review:** ${step.review?.disposition || 'Not recorded'} — ${step.review?.rationale || finding.skeptic_response || 'No rationale recorded'}`,
        ...(step.review?.objection ? ['', `**Objection:** ${step.review.objection}`] : []), '',
      ]) : ['No structured reasoning steps were preserved for this finding.', '']),
      ...(finding.objections.length ? ['**Objections:**', ...finding.objections.map(item => `- ${item}`), ''] : []),
      ...(finding.open_obligations.length ? ['**Open obligations:**', ...finding.open_obligations.map(item => `- ${item}`), ''] : []),
      `**Sources:** ${outcomeArtifactReferences(finding.research_artifact_ids?.length ? finding.research_artifact_ids : finding.research_artifact_id ? [finding.research_artifact_id] : [], session)}`, '');
  }
  return lines.join('\n');
}

function researchArtifactMarkdown(artifact: ResearchArtifact): string {
  const lines = [
    `# Round ${artifact.sequence}: ${artifact.claim_or_question}`,
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
const durationUnitMinutes: Record<DurationUnit, number> = { minutes: 1, hours: 60, days: 1440 };
const limitBounds = {
  research_rounds: [1, 5], model_calls: [2, 120], output_tokens_per_call: [256, 20000],
} as const;
function draftLimits(value: ResearchLimits): ResearchLimitsDraft {
  const unit: DurationUnit = value.session_duration_minutes >= 1440 && value.session_duration_minutes % 1440 === 0 ? 'days' : value.session_duration_minutes >= 60 && value.session_duration_minutes % 60 === 0 ? 'hours' : 'minutes';
  const duration = value.session_duration_minutes / durationUnitMinutes[unit];
  return { research_rounds: String(value.research_rounds), model_calls: String(value.model_calls), session_duration_value: String(duration), session_duration_unit: unit, output_tokens_per_call: String(value.output_tokens_per_call), maximum_estimated_cost_usd: value.maximum_estimated_cost_usd === null ? '' : String(value.maximum_estimated_cost_usd), maximum_input_tokens_per_session: value.maximum_input_tokens_per_session === null || value.maximum_input_tokens_per_session === undefined ? '' : String(value.maximum_input_tokens_per_session), max_concurrent_sessions: String(value.max_concurrent_sessions ?? '1') };
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
  if (!/^\d+$/.test(draft.session_duration_value)) {
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
  if (!/^\d+$/.test(draft.max_concurrent_sessions) || BigInt(draft.max_concurrent_sessions || '0') < 1n) {
    errors.max_concurrent_sessions = 'Enter a positive whole number.';
  } else value.max_concurrent_sessions = draft.max_concurrent_sessions;
  if (value.maximum_input_tokens_per_session !== null && value.maximum_input_tokens_per_session !== undefined && value.maximum_estimated_cost_usd === null) errors.maximum_input_tokens_per_session = 'Set a maximum estimated cost when using an input-token cap.';
  if (!errors.model_calls && value.model_calls < 2) {
    errors.model_calls = 'Allow at least two agent turns for one Investigator/Skeptic pair.';
  }
  return { value: Object.keys(errors).length ? null : value, errors };
}

function displayStrategyTitle(strategy: Strategy | undefined): string {
  if (!strategy) return 'Strategy';
  if (typeof strategy.title === 'string' && strategy.title.trim()) return strategy.title;
  const firstLine = typeof strategy.approach === 'string' ? strategy.approach.split(/\r?\n/, 1)[0].trim() : '';
  return firstLine ? `${firstLine.slice(0, 72)}${firstLine.length > 72 ? '…' : ''}` : 'Untitled strategy';
}

type ProcessControls = { play: () => void; stop: () => void; playDisabled: boolean; stopDisabled: boolean; playLabel: string; confirming?: boolean; start?: () => void; cancel?: () => void; nextSessionNumber?: number; confirmationSummary?: string };

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

function ResearchSessionContents({ path, session, expanded, busy, advancedOutcomeDetails, onEnableAdvancedOutcome, onViewStrategy, onViewPriorSession, onForkFromFindings, onInterventionSaved }: {
  path: string;
  session: ResearchSession; advancedOutcomeDetails: boolean; expanded: boolean; busy: boolean;
  onEnableAdvancedOutcome: () => Promise<void>;
  onViewStrategy: (id: string) => void;
  onViewPriorSession: (id: string) => void;
  onForkFromFindings: (session: ResearchSession) => void;
  onInterventionSaved: (sessionId: string) => Promise<void>;
}) {
  const savedConclusionHasMath = containsMathNotation(session.outcome.conclusion || '');
  const startsWithRenderedMath = containsMathNotation(
    `${session.outcome.conclusion || ''}\n${session.outcome.summary || ''}`,
  );
  const [outcomeMarkdown, setOutcomeMarkdown] = useState(startsWithRenderedMath);
  const [conclusionMarkdown, setConclusionMarkdown] = useState(savedConclusionHasMath);
  const [convertedConclusion, setConvertedConclusion] = useState<string | null>(null);
  const [conclusionFormatWarnings, setConclusionFormatWarnings] = useState<string[]>([]);
  const [conclusionRendering, setConclusionRendering] = useState(false);
  const [conclusionFormatError, setConclusionFormatError] = useState('');
  const [advancedOutcomeEnableError, setAdvancedOutcomeEnableError] = useState('');
  const [enablingAdvancedOutcome, setEnablingAdvancedOutcome] = useState(false);
  const conclusionConversionAbort = useRef<AbortController | null>(null);
  const [reasoningMarkdown, setReasoningMarkdown] = useState(false);
  const [artifactsMarkdown, setArtifactsMarkdown] = useState(false);
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
  useEffect(() => () => conclusionConversionAbort.current?.abort(), []);
  const lastActivity = session.events.at(-1);
  const lastStep = session.steps.at(-1);
  const approvedPackets = Object.values(session.approved_continuations ?? {});
  const approvedSourceIds = new Set(approvedPackets.flatMap(packet => packet.sources.map(source => source.artifact_id)));
  const otherPriorFindings = (session.prior_session_findings ?? []).filter(finding => !approvedSourceIds.has(finding.id));
  const review = session.outcome.solution_review;
  const primaryEvidenceIds = [...new Set([...(session.outcome.basis_artifact_ids ?? []), ...(review?.basis_artifact_ids ?? [])])];
  const hasEvidence = session.artifacts.length > 0 || primaryEvidenceIds.length > 0;
  const historicalSummary = !session.outcome.conclusion && !['queued', 'running', 'paused'].includes(session.status);
  const resultLabel = session.outcome.conclusion ? 'Conclusion' : historicalSummary ? 'Historical session summary' : 'Session summary';
  const resultText = session.outcome.conclusion || session.outcome.summary || 'No outcome summary was recorded.';
  const simpleDisplaySession = convertedConclusion !== null && outcomeMarkdown
    ? { ...session, outcome: { ...session.outcome, conclusion: convertedConclusion } }
    : session;
  const simpleResult = simpleOutcomeLead(simpleDisplaySession);
  const simpleOutcomeMarkdown = outcomeMarkdown;
  const verificationLabel = review?.verification_status === 'verified' ? 'Verified in the session record' : review?.verification_status === 'convincing_unverified' ? 'Convincing but unverified' : review?.verification_status === 'incomplete' ? 'Evidence incomplete' : 'Not independently verified';
  const qualificationItems = [...new Set([...(review?.open_obligations ?? []), ...(review?.unresolved_objections ?? []), ...(session.outcome.caveats ?? [])])];
  const simpleQualifications = session.outcome.conclusion ? qualificationItems.slice(0, 3) : qualificationItems;
  const provenance = session.outcome.execution_provenance;
  const runMetrics = session.outcome.metrics?.operational ?? [];
  const budgetDenied = session.steps.some(step => step.failure_kind === 'budget_denied');
  const budgetReason = session.strategy_runs?.find(branch => /allowance|inference[- ]spend|cost reserve|cost limit/i.test(branch.reason ?? ''))?.reason;
  const budgetNotice = budgetDenied
    ? session.calls_used === 0
      ? 'The available research funds could not cover a provider call. No provider calls were made.'
      : 'Research stopped because the remaining research funds could not cover another provider call. Saved findings are preserved.'
    : '';
  const statusHeading = budgetDenied
    ? session.calls_used === 0 ? 'Insufficient research funds' : 'Research funding limit reached'
    : session.status === 'paused' ? 'Session paused'
      : session.status === 'stopped' ? 'Session stopped'
        : session.status === 'failed' ? 'Session failed' : 'Session ended';
  const statusNextStep = session.next_step_guidance
    || (budgetDenied ? 'Review the available research allowance before starting another session.'
      : 'Review saved activity and provider usage before resuming. Resuming may start new provider work and can consume allowance or incur charges.');
  const zeroPythonRuns = runMetrics.some(item => item.label === 'Python runs by status' && item.value === '0 executions');
  const zeroSageRuns = runMetrics.some(item => item.label === 'SageMath runs by status' && item.value === '0 executions');
  const noSavedLocalComputations = (provenance && provenance.records.length === 0 && provenance.unidentified_count === 0)
    || (!provenance && zeroPythonRuns && zeroSageRuns);
  const provenancePrelude = <div className="outcome-evidence-prelude" aria-label="Recorded computation provenance">
    <strong>Recorded computations:</strong> {provenance
      ? `${provenance.completed_count} reported completed of ${provenance.records.length} identified saved execution${provenance.records.length === 1 ? '' : 's'}${provenance.unidentified_count ? ` · ${provenance.unidentified_count} missing IDs` : ''}`
      : 'Provenance projection unavailable for this historical Outcome.'}
    {noSavedLocalComputations && <p role="status"><strong>Evidence limitation:</strong> No local Python or Sage computation is recorded for this session. Computational claims in the agent-authored conclusion are not supported by saved local execution evidence.</p>}
    {provenance && <p>{provenance.note}</p>}{!!provenance?.completed_without_recorded_io_count && <p>Warning: {provenance.completed_without_recorded_io_count} completed-status record(s) do not include saved source and output.</p>}
    {!!provenance?.records.length && <details><summary>Execution IDs and saved statuses</summary><ul>{provenance.records.map(row => <li key={`${row.runtime}:${row.id}`}><strong>{row.runtime} · {row.id}</strong> · {row.statuses.join(' / ')} · {row.artifact_ids.length ? `artifacts ${row.artifact_ids.join(', ')}` : row.step_ids.length ? `steps ${row.step_ids.join(', ')}` : 'owner not recorded'} · source {row.source_recorded ? 'saved' : 'unavailable'}, output {row.output_recorded ? 'saved' : 'unavailable'}</li>)}</ul></details>}
  </div>;
  const metricSources = session.outcome.metrics?.sources;
  const artifactNumber = (id: string) => session.artifacts.find(artifact => artifact.id === id)?.sequence;
  const idList = (ids: string[] | undefined) => ids?.length ? ids.map(id => `Artifact ${artifactNumber(id) ?? '?'} · ${id}`).join(', ') : 'None recorded';
  const targetStrategies = session.strategy_runs ?? [{ strategy_id: session.strategy_id, strategy_title: session.strategy_title }];
  const supportsIntervention = !!session.strategy_runs?.length;
  const interventionCount = session.interventions ?? [];
  const interventionWindowOpen = ['queued', 'running', 'paused', 'stopped'].includes(session.status);
  const canIntervene = supportsIntervention && interventionWindowOpen
    && interventionCount.filter(item => item.status !== 'rejected').length < 24
    && interventionCount.length < 32;
  const interventionHelp = session.status === 'paused' || session.status === 'stopped'
    ? 'Applies after resume; no call starts now.'
    : 'Applies on a later call; no call starts now.';
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
  async function toggleConclusionMarkdown() {
    if (conclusionMarkdown) {
      setConclusionMarkdown(false);
      setOutcomeMarkdown(false);
      return;
    }
    if (convertedConclusion !== null) {
      setConclusionMarkdown(true);
      setOutcomeMarkdown(true);
      return;
    }
    if (savedConclusionHasMath) {
      setConclusionMarkdown(true);
      setOutcomeMarkdown(true);
      return;
    }
    const source = session.outcome.conclusion;
    if (!source || conclusionRendering) return;
    const controller = new AbortController();
    conclusionConversionAbort.current = controller;
    setConclusionRendering(true);
    setConclusionFormatError('');
    let finishProviderRequest = () => {};
    try {
      const settingsResponse = await fetch(
        `/api/projects/proposals/config?${new URLSearchParams({ path })}`,
        { signal: controller.signal },
      );
      const settings = await settingsResponse.json();
      if (!settingsResponse.ok || !settings.available) {
        throw new Error(settings.message ?? settings.error ?? 'Connect AI in the header, then retry.');
      }
      finishProviderRequest = beginProviderRequest('text-conversion');
      const sourceDigest = await sha256Text(source);
      const converted = await post<{ body: string; warnings: string[]; source_digest: string }>(
        'text/convert',
        {
          path,
          scope: 'research-conclusion',
          session_id: session.id,
          target: 'markdown',
          expected_digest: sourceDigest,
          expected_binding: settings.binding,
        },
        controller.signal,
      );
      if (converted.source_digest !== sourceDigest) {
        throw new Error('The saved Conclusion changed during formatting. Reopen the session and retry.');
      }
      setConvertedConclusion(converted.body);
      setConclusionFormatWarnings(converted.warnings ?? []);
      setConclusionMarkdown(true);
      setOutcomeMarkdown(true);
    } catch (cause) {
      if (!controller.signal.aborted) {
        const message = errorMessage(cause);
        setConclusionFormatError(message);
        reportRequestFailure(message);
      }
    } finally {
      finishProviderRequest();
      if (conclusionConversionAbort.current === controller) {
        conclusionConversionAbort.current = null;
        setConclusionRendering(false);
      }
    }
  }
  const outcomeFormatToggle = <button type="button" className="sigma-render-toggle" aria-label={outcomeMarkdown ? 'Show plain outcome text' : 'Render outcome as Markdown'} aria-pressed={outcomeMarkdown} data-tooltip={outcomeMarkdown ? 'Show plain outcome text' : 'Render outcome as Markdown'} title={outcomeMarkdown ? 'Show plain outcome text' : 'Render outcome as Markdown'} onClick={() => setOutcomeMarkdown(value => !value)}><svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z" fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg></button>;
  const conclusionToggleLabel = conclusionMarkdown
    ? 'Show saved Conclusion'
    : convertedConclusion !== null || savedConclusionHasMath ? 'Render Conclusion as Markdown' : 'Format Conclusion with AI';
  const conclusionFormatToggle = <button type="button" className={`sigma-render-toggle${conclusionMarkdown ? ' sigma-render-active' : ''}${conclusionRendering ? ' sigma-render-pending' : ''}`} aria-label={conclusionToggleLabel} aria-pressed={conclusionMarkdown} aria-busy={conclusionRendering} data-tooltip={conclusionRendering ? 'Formatting Conclusion' : conclusionToggleLabel} title={conclusionRendering ? 'Formatting Conclusion' : conclusionToggleLabel} disabled={conclusionRendering} onClick={() => void toggleConclusionMarkdown()}>{conclusionRendering ? <span aria-hidden="true">⌛</span> : <svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z" fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg>}</button>;
  const reasoningFormatToggle = <button type="button" className="sigma-render-toggle" aria-label={reasoningMarkdown ? 'Show reasoning Markdown source' : 'Render reasoning as Markdown'} aria-pressed={reasoningMarkdown} data-tooltip={reasoningMarkdown ? 'Show reasoning Markdown source' : 'Render reasoning as Markdown'} title={reasoningMarkdown ? 'Show reasoning Markdown source' : 'Render reasoning as Markdown'} onClick={() => setReasoningMarkdown(value => !value)}><svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z" fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg></button>;
  const renderMetricGroup = (title: string, items: OutcomeMetric[] | undefined) => <div className="outcome-metric-group">
    <h5>{title}</h5>
    {items?.length ? <dl>{items.map((item, index) => <div className="outcome-label-value" key={`${item.label}:${index}`}><dt>{item.label}</dt><dd><span>{item.value}</span>{item.detail && <small>{item.detail}</small>}</dd></div>)}</dl> : <p className="outcome-unavailable">No {title.toLowerCase()} metrics are available for this session.</p>}
  </div>;
  return <div id={`session-content-${session.id}`} className="session-row-content" hidden={!expanded}>
    <section className={`session-outcome outcome-${session.outcome.assessment}`} aria-label="Research outcome">
      <div className="outcome-heading"><div className="outcome-heading-title"><h3>Outcome</h3>{outcomeFormatToggle}<span className={`outcome-label outcome-${session.outcome.assessment}`}>{outcomeDisplayLabel(session)}</span></div></div>
      {provenancePrelude}
      {(budgetDenied || session.status === 'paused' || session.status === 'stopped' || session.status === 'failed' || !!session.next_step_guidance) && <aside className="research-pause-guidance" aria-label="Session status and next steps">
        <strong>{statusHeading}</strong>
        {budgetDenied ? <><p>{budgetNotice}</p>{budgetReason && <p>{budgetReason}</p>}</> : !!session.message && <p>{session.message}</p>}
        <p>{statusNextStep}</p>
      </aside>}
      {!advancedOutcomeDetails && <div className="outcome-simple">
        <div className="outcome-summary-text"><span className="outcome-summary-kicker">{resultLabel}</span>
          {simpleOutcomeMarkdown ? <div className="outcome-markdown"><Suspense fallback={<p>{simpleResult}</p>}><RenderedMarkdown body={simpleResult}/></Suspense></div> : <p>{simpleResult}</p>}
          {session.outcome.conclusion && <div className="outcome-conclusion-actions">{conclusionFormatToggle}{conclusionRendering && <span className="text-view-format-status" role="status">Formatting with AI…</span>}</div>}
          {convertedConclusion !== null && outcomeMarkdown && <div className="outcome-conclusion-format-note"><p>AI formatted this reading view; the saved Conclusion is unchanged. Compare the saved text before relying on changed notation. Formatting does not verify the mathematics.</p>{!!conclusionFormatWarnings.length && <ul>{conclusionFormatWarnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}</div>}
          {conclusionFormatError && <p role="alert" className="outcome-conclusion-format-error">{conclusionFormatError}</p>}
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
      {advancedOutcomeDetails && <div className="outcome-subsections outcome-advanced">
        <details className="outcome-subsection outcome-conclusion" open>
          <summary><DisclosureChevron expanded={false}/>Conclusion</summary>
          <div className="outcome-subsection-content outcome-conclusion-content">
            {!session.outcome.conclusion && <span className="outcome-summary-kicker">{resultLabel}</span>}
            {session.outcome.conclusion && <div className="outcome-conclusion-actions">{conclusionFormatToggle}{conclusionRendering && <span className="text-view-format-status" role="status">Formatting with AI…</span>}</div>}
            {convertedConclusion !== null && conclusionMarkdown && <div className="outcome-conclusion-format-note"><p>AI formatted this reading view; the saved Conclusion is unchanged. Compare the saved text before relying on changed notation. Formatting does not verify the mathematics.</p>{!!conclusionFormatWarnings.length && <ul>{conclusionFormatWarnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}</div>}
            {conclusionFormatError && <p role="alert" className="outcome-conclusion-format-error">{conclusionFormatError}</p>}
            {session.outcome.conclusion && conclusionMarkdown
              ? <div className="outcome-markdown"><Suspense fallback={<p role="status">Preparing formatted Conclusion…</p>}><RenderedMarkdown body={convertedConclusion ?? session.outcome.conclusion}/></Suspense></div>
              : !session.outcome.conclusion && outcomeMarkdown ? <div className="outcome-markdown"><Suspense fallback={<p>{resultText}</p>}><RenderedMarkdown body={researchOutcomeMarkdown(session)}/></Suspense></div>
                : <div className="outcome-conclusion-source">{resultText}</div>}
            {primaryEvidenceIds.length > 0 && <p className="outcome-primary-evidence"><strong>Supporting evidence:</strong> {outcomeArtifactReferences(primaryEvidenceIds, session)}</p>}
            <p className="outcome-confidence"><strong>Verification:</strong> {verificationLabel}{session.outcome.provisional ? ' · provisional assessment' : ''}</p>
            {(session.outcome.caveats?.length || review?.open_obligations?.length || review?.unresolved_objections?.length) ? <div className="outcome-qualifications"><strong>Qualifications and unresolved questions</strong>{!!session.outcome.caveats?.length && <ul>{session.outcome.caveats.map((item, index) => <li key={`caveat-${index}`}>{item}</li>)}</ul>}{!!review?.open_obligations?.length && <ul>{review.open_obligations.map((item, index) => <li key={`obligation-${index}`}>{item}</li>)}</ul>}{!!review?.unresolved_objections?.length && <ul>{review.unresolved_objections.map((item, index) => <li key={`objection-${index}`}>{item}</li>)}</ul>}</div> : null}
          </div>
        </details>
        {approvedPackets.length > 0 && <details className="outcome-subsection continuation-evidence">
          <summary><DisclosureChevron expanded={false}/>Researcher-approved inherited evidence · {approvedSourceIds.size} source{approvedSourceIds.size === 1 ? '' : 's'}</summary>
          <div className="outcome-subsection-content">
            <p>These frozen artifacts were explicitly approved for transfer. Other available project evidence was not approved by this action. Delivery is recorded in exact provider inputs; the model's interpretation remains unverified.</p>
            {approvedPackets.map(packet => <section key={packet.packet_digest}>
              <p><strong>Approved question:</strong> {packet.question}</p>
              <p><button type="button" className="text-view-link" onClick={() => onViewStrategy(packet.parent_strategy_id)}>Inspect parent strategy</button></p>
              <ul>{packet.sources.map(source => <li key={source.artifact_id}>
                <button type="button" className="text-view-link" onClick={() => onViewPriorSession(source.source.session_id)}>Approved source · Session #{source.source.session_number} · {source.strategy_title}</button>
                <p>{source.claim}</p><p>{source.status} · {source.verification}</p>
                <details><summary>Frozen artifact {source.artifact_id}</summary><pre>{JSON.stringify(source.artifact, null, 2)}</pre></details>
              </li>)}</ul>
              {packet.rejected_sources.length > 0 && <details><summary>{packet.rejected_sources.length} explicitly rejected transfer{packet.rejected_sources.length === 1 ? '' : 's'}</summary><ul>{packet.rejected_sources.map(row => <li key={row.artifact_id}>{row.artifact_id} — {row.rationale}</li>)}</ul></details>}
            </section>)}
          </div>
        </details>}
        {review && <details className="outcome-subsection outcome-reasoning-subsection"><summary><DisclosureChevron expanded={false}/>Reasoning / proof</summary><div className="outcome-subsection-content"><div className="outcome-reasoning-actions"><h4>Reasoning / proof</h4>{reasoningFormatToggle}</div>{reasoningMarkdown ? <div className="outcome-markdown"><Suspense fallback={<p>{review.argument_summary || review.claim || 'No reasoning was saved.'}</p>}><RenderedMarkdown body={researchReasoningMarkdown(session)}/></Suspense></div> : <div className="solution-review"><p><strong>Investigated:</strong> {session.problem || 'Project objective unavailable in this historical record.'}</p><p><strong>Bounded strategy:</strong> {session.strategy_text || session.strategy_title || 'Strategy details unavailable.'}</p><p><strong>Claim:</strong> {review.claim || 'No claim recorded.'}</p><p><strong>Skeptic response:</strong> {review.skeptic_response || 'No substantive Skeptic response recorded.'}</p>{!!review.skeptic_objections?.length && <p><strong>Skeptic objections:</strong> {review.skeptic_objections.join(' · ')}</p>}{review.argument_steps?.length ? <ol>{review.argument_steps.map(step => <li key={`${step.research_artifact_id ?? ''}:${step.number}`}><strong>{step.title}</strong> <span>({step.epistemic_status})</span><p>{step.argument}</p><p><strong>Skeptic review:</strong> {step.review?.disposition || 'Not recorded'} — {step.review?.rationale || 'No rationale recorded'}</p>{!!step.review?.objection && <p><strong>Objection:</strong> {step.review.objection}</p>}<p><strong>Sources:</strong> {outcomeArtifactReferences([...(step.basis_artifact_ids || []), ...(step.research_artifact_id ? [step.research_artifact_id] : [])], session)}</p></li>)}</ol> : <p>No step-by-step argument was preserved. See the saved research artifacts before relying on this claim.</p>}{(review.strategy_findings?.length ?? 0) > 0 && <div><h4>Findings by strategy</h4>{review.strategy_findings!.map(item => <section key={item.strategy_id}><h5>{item.strategy_title} · {item.status}</h5><p>{item.claim}</p>{!!item.execution_status && <p><strong>Execution status:</strong> {item.execution_status}</p>}{!!item.failure_reason && <p><strong>Failure detail:</strong> {item.failure_reason}</p>}{item.reasoning_steps.length ? <ol>{item.reasoning_steps.map(step => <li key={step.number}><strong>{step.title}</strong> ({step.epistemic_status})<p>{step.argument}</p><p><strong>Review:</strong> {step.review?.disposition || 'Not recorded'} — {step.review?.rationale || item.skeptic_response}</p>{!!step.review?.objection && <p><strong>Objection:</strong> {step.review.objection}</p>}</li>)}</ol> : <p>No structured reasoning steps were preserved for this finding.</p>}{!!item.objections.length && <p><strong>Objections:</strong> {item.objections.join(' · ')}</p>}{!!item.open_obligations.length && <p><strong>Open obligations:</strong> {item.open_obligations.join(' · ')}</p>}<p><strong>Sources:</strong> {outcomeArtifactReferences(item.research_artifact_ids?.length ? item.research_artifact_ids : (item.research_artifact_id ? [item.research_artifact_id] : []), session)}</p></section>)}</div>}<p><strong>Assumptions:</strong> {review.assumptions?.join(' · ') || 'None recorded'}</p><p><strong>Proof obligations considered:</strong> {review.proof_obligations?.join(' · ') || 'None recorded'}</p><p><strong>Still open:</strong> {review.open_obligations?.join(' · ') || 'None recorded'}</p>{!!review.unresolved_objections?.length && <p><strong>Unresolved objections:</strong> {review.unresolved_objections.join(' · ')}</p>}{!!review.resolved_objections?.length && <p><strong>Objections addressed:</strong> {review.resolved_objections.join(' · ')}</p>}</div>}</div></details>}
        {hasEvidence && <details className="outcome-subsection outcome-evidence-subsection">
          <summary><DisclosureChevron expanded={false}/>Citations, evidence &amp; obligations</summary>
          <div className="outcome-subsection-content">
            {!!session.artifacts.length && <section className="research-artifacts" aria-label="Research artifacts"><div className="research-artifacts-heading"><h4>Research artifacts</h4><button type="button" className="sigma-render-toggle" aria-label={artifactsMarkdown ? 'Show plain research artifacts' : 'Render research artifacts as Markdown'} aria-pressed={artifactsMarkdown} data-tooltip={artifactsMarkdown ? 'Show plain research artifacts' : 'Render research artifacts as Markdown'} title={artifactsMarkdown ? 'Show plain research artifacts' : 'Render research artifacts as Markdown'} onClick={() => setArtifactsMarkdown(value => !value)}><svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z" fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg></button></div><ol>{session.artifacts.map(artifact => {
              const sage = !!artifact.investigator_output.sage_execution;
              const executionField = sage ? 'sage_execution' : 'python_execution';
              const toolName = sage ? 'SageMath' : 'Python';
              const execution = artifact.investigator_output[executionField] && typeof artifact.investigator_output[executionField] === 'object' ? artifact.investigator_output[executionField] as Record<string, unknown> : null;
              const captured = execution && Array.isArray(execution.artifacts) ? execution.artifacts as Record<string, unknown>[] : [];
              const reused = artifact.investigator_output[executionField + '_reuse_reason'];
              return <li key={artifact.id} id={`research-artifact-${session.id}-${artifact.id}`}>{artifactsMarkdown ? <div className="research-artifact-content research-artifact-markdown"><Suspense fallback={<p>{artifact.method}</p>}><RenderedMarkdown body={researchArtifactMarkdown(artifact)}/></Suspense></div> : <details>
                <summary>Round {artifact.strategy_cycle ?? artifact.sequence} · {artifact.claim_or_question} <span>{artifact.evidence_status}</span></summary>
                <div className="research-artifact-content"><p><strong>Method:</strong> {artifact.method}</p><p><strong>Assumptions:</strong> {artifact.assumptions.join(' · ') || 'None stated'}</p><p><strong>Evidence status:</strong> {artifact.evidence_status}</p><p><strong>Skeptic response:</strong> {artifact.skeptic_response}</p><p><strong>Objections:</strong> {artifact.objections.join(' · ') || 'No concrete objection recorded'}</p><p><strong>Open obligations:</strong> {artifact.open_obligations.join(' · ') || 'None recorded'}</p>{Array.isArray(artifact.skeptic_output.obligation_reviews) && artifact.skeptic_output.obligation_reviews.length > 0 && <p><strong>Obligation dispositions:</strong> {(artifact.skeptic_output.obligation_reviews as Record<string, unknown>[]).map(review => `${String(review.status ?? 'unknown')} · ${String(review.rationale ?? '')} [${Array.isArray(review.basis_artifact_ids) ? review.basis_artifact_ids.join(', ') : 'no artifact source'}]`).join(' · ')}. Model-reported and unverified.</p>}<p><strong>Coordinator decision:</strong> {artifact.coordinator_decision}</p><p><strong>Next question:</strong> {artifact.next_question || 'No further question; the session ended.'}</p>
                  {execution && <section className="outcome-python-evidence"><h5>{toolName} execution · {String(execution.status ?? 'status unavailable')}</h5><details className="research-execution-record"><summary>Execution source and output</summary><pre>{JSON.stringify(execution, null, 2)}</pre></details><p><strong>Execution ID:</strong> {String(execution.id ?? 'Unavailable')}</p>{typeof execution.exit_code === 'number' && <p><strong>Exit code:</strong> {execution.exit_code}</p>}{typeof reused === 'string' && <p><strong>Reuse:</strong> {reused}</p>}<p>{typeof execution.source === 'string' ? 'Exact source is retained in the execution record.' : 'Source unavailable in this record.'} Computation status is not proof of a mathematical claim.</p>{!!captured.length && <div><strong>Captured files</strong><ul>{captured.map((file, index) => <li key={index}>{String(file.filename ?? 'Unnamed file')} · {typeof file.size_bytes === 'number' ? `${file.size_bytes} bytes` : 'size unavailable'} · SHA-256 {String(file.sha256 ?? 'unavailable')}</li>)}</ul></div>}</section>}
                  <details><summary>Full validated role outputs</summary><h5>Investigator</h5>{Object.entries(artifact.investigator_output).filter(([key]) => !['python_execution', 'sage_execution'].includes(key)).map(([key, value]) => <p key={key}><strong>{key.replaceAll('_', ' ')}:</strong> {Array.isArray(value) ? value.join(' · ') : typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)}</p>)}<h5>Skeptic</h5>{Object.entries(artifact.skeptic_output).map(([key, value]) => <p key={key}><strong>{key.replaceAll('_', ' ')}:</strong> {Array.isArray(value) ? value.join(' · ') : typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)}</p>)}</details><small>{artifact.note}</small>
                </div></details>}</li>;
            })}</ol></section>}
          </div>
        </details>}
        <details className="outcome-subsection">
          <summary><DisclosureChevron expanded={false}/>Metrics</summary>
          <div className="outcome-subsection-content">
            {session.outcome.metrics ? <div className="outcome-metrics-groups">{renderMetricGroup('Operational', session.outcome.metrics.operational)}{renderMetricGroup('Research quality', session.outcome.metrics.research_quality)}</div> : <p className="outcome-unavailable">Metrics are not available for this historical session.</p>}
          </div>
        </details>
        <section className="outcome-other-details" aria-label="Other Outcome details"><h4>Other Outcome details</h4>
          <details className="outcome-subsection">
          <summary><DisclosureChevron expanded={false}/>Status</summary>
          <div className="outcome-subsection-content">
            <div className="outcome-label-value"><dt>Session lifecycle</dt><dd>{session.status}</dd></div><div className="outcome-label-value"><dt>Token usage</dt><dd>{session.tokens_used == null ? `Unavailable (${session.token_usage_status ?? 'not reported'})` : `${session.tokens_used.toLocaleString()} tokens · ${session.token_usage_status ?? 'reported'}`}</dd></div>
            <div className="outcome-label-value"><dt>Research result</dt><dd>{outcomeDisplayLabel(session)}</dd></div>
            <div className="outcome-label-value"><dt>Verification</dt><dd>{review?.verification_status && review.verification_status !== 'unknown' ? review.verification_status === 'verified' ? 'Verified (session record)' : 'Convincing but unverified' : 'Not independently verified'}</dd></div>
            <p className="outcome-integrity-note">A completed session or successful computation does not establish a mathematical proof.</p>
            {!!session.strategy_runs && session.strategy_runs.length > 1 && <section className="research-strategy-activity" aria-label="Strategy activity"><h4>Strategy activity</h4><ul>{session.strategy_runs.map(branch => <li key={branch.strategy_id} className={`strategy-run-${branch.status}`}><p><strong>{branch.strategy_title}</strong> · {branch.status} · {branch.current_action}</p><p>Round {branch.cycle} · {branch.calls_used} agent turns · {branch.artifacts.length} saved findings</p>{!!branch.current_question && <p><strong>Current question:</strong> {branch.current_question}</p>}{!!branch.reason && <p><strong>Coordinator rationale:</strong> {branch.reason}</p>}</li>)}</ul></section>}
            {!!session.steps.filter(step => ['failed', 'interrupted', 'running'].includes(step.status)).length && <section className="outcome-provider-attempts" aria-label="Incomplete provider attempts"><h4>Incomplete or failed attempts</h4><ul>{session.steps.filter(step => ['failed', 'interrupted', 'running'].includes(step.status)).map(step => <li key={step.id}><strong>{step.status} · {step.role}</strong><span>Round {step.cycle}, provider call {step.call_number}{step.provider_http_status ? (step.provider_response_channel === 'stream' ? ` · HTTP ${step.provider_http_status} transport, ${step.provider_stream_event ?? 'stream'} rejected` : ` · HTTP ${step.provider_http_status}`) : ''}{step.provider_error_code ? ` · Provider code: ${step.provider_error_code}` : ''}{step.failure_kind ? ` · ${step.failure_kind}` : ''}</span>{step.interruption_reason && <p>{step.interruption_reason}</p>}{step.failure_message && <p>{step.failure_message}</p>}{step.status === 'interrupted' && <p>The provider may have completed or charged usage; SIGMA did not repeat this ambiguous attempt automatically.</p>}</li>)}</ul></section>}
            {lastStep && ['running', 'interrupted', 'failed'].includes(lastStep.status) && !session.steps.some(step => ['failed', 'interrupted', 'running'].includes(step.status)) && <section className="research-incomplete-step" aria-label="Current or incomplete step"><strong>{lastStep.status === 'running' ? 'In progress' : 'Incomplete step'} · {lastStep.role}</strong><p>Round {lastStep.cycle}, provider call {lastStep.call_number}. This attempt is not a completed research artifact.</p></section>}
            {!!session.current_question && <p><strong>Current focus:</strong> {session.current_question}</p>}
            <div className="research-session-actions"><a className="text-view-link" title={`View strategy: ${session.strategy_title}`} href={`#strategy-${session.strategy_id}`} onClick={event => { event.preventDefault(); onViewStrategy(session.strategy_id); }}>Go to strategy: {session.strategy_title}</a></div>
          </div>
        </details>
          <details className="outcome-subsection">
          <summary><DisclosureChevron expanded={false}/>Strategy Assessments</summary>
          <div className="outcome-subsection-content">
            <p className="outcome-subsection-intro">Each assessment records a strategy’s contribution to the project objective in this session.</p>
            {session.strategy_assessments?.length ? <div className="outcome-assessment-list">{session.strategy_assessments.map((item, index) => {
              const label: Record<StrategyAssessment['assessment'], string> = { contributed_to_solution: 'Contributed to solution', productive: 'Productive', unproductive: 'Unproductive', not_used: 'Not used', disabled: 'Disabled', unknown: 'Unknown' };
              return <article className="outcome-assessment" key={item.strategy_id ?? index}><h4>{item.strategy_title}</h4><div className="outcome-label-value"><dt>Disposition</dt><dd>{label[item.assessment] ?? 'Unknown'}</dd></div><div className="outcome-label-value"><dt>Rationale</dt><dd>{item.rationale || 'No rationale recorded'}</dd></div><div className="outcome-label-value"><dt>Cited evidence</dt><dd>{idList(item.basis_artifact_ids)}</dd></div></article>;
            })}</div> : <p className="outcome-unavailable">No strategy assessments were recorded for this session.</p>}
            {session.portfolio_decision?.strategy_actions?.length ? <section className="coordinator-portfolio-review" aria-label="Coordinator portfolio recommendations"><h4>Coordinator recommendations</h4><p>Evidence-linked recommendations are model-reported and unverified. Saved strategies are never changed automatically.</p><ul>{session.portfolio_decision.strategy_actions.map(item => <li key={item.strategy_id}><p><strong>{item.strategy_title}:</strong> {item.action.replaceAll('_', ' ')}</p><p>{item.rationale}{item.basis_artifact_ids.length > 0 && <> · Evidence: {idList(item.basis_artifact_ids)}</>}</p>{!!item.next_question && <p><strong>Next question:</strong> {item.next_question}</p>}</li>)}</ul>
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
            {session.steps.length > 0 && <div className="outcome-provenance-group"><h4>Agent turn attempts</h4><ol className="outcome-provenance-list">{session.steps.map(step => <li key={step.id}><div className="outcome-label-value"><dt>{step.role} · {step.status}</dt><dd>Step {step.id} · Cycle {step.cycle} · Call {step.call_number}{step.strategy_id ? ` · Strategy ${step.strategy_id}` : ''}</dd></div><p>{step.started_at ? dateLabel(step.started_at) : 'Start time unavailable'}{step.finished_at ? ` · ${dateLabel(step.finished_at)}` : ' · no finish time recorded'}{step.provider_http_status ? (step.provider_response_channel === 'stream' ? ` · HTTP ${step.provider_http_status} transport, ${step.provider_stream_event ?? 'stream'} rejected` : ` · HTTP ${step.provider_http_status}`) : ''}{step.provider_error_code ? ` · Provider code: ${step.provider_error_code}` : ''}{step.failure_kind ? ` · ${step.failure_kind}` : ''}{step.interruption_reason ? ` · ${step.interruption_reason}` : ''}</p>{!!(step.context_artifact_ids?.length || step.prior_session_artifact_ids?.length || step.peer_strategy_artifact_ids?.length || step.peer_handoff_artifact_ids?.length) && <p><strong>Context artifacts:</strong> {idList([...(step.context_artifact_ids ?? []), ...(step.prior_session_artifact_ids ?? []), ...(step.peer_strategy_artifact_ids ?? []), ...(step.peer_handoff_artifact_ids ?? [])])}</p>}{!!step.peer_handoff_ids?.length && <p><strong>Peer handoffs:</strong> {step.peer_handoff_ids.join(', ')}</p>}{step.context_manifest && <details className="context-used-disclosure"><summary>Context used · {step.context_manifest.selected_count ?? step.context_manifest.sources?.filter(source => source.status === 'selected').length ?? 0} current artifacts selected · {step.context_manifest.omitted_count ?? 0} omitted</summary><p>{step.context_manifest.note ?? 'Deterministic extracts from saved records; originals remain in session history.'}</p>{typeof step.context_manifest.assembled_context_bytes === 'number' && <p>Serialized context: {step.context_manifest.assembled_context_bytes.toLocaleString()} bytes of {step.context_manifest.byte_limit?.toLocaleString() ?? 'bounded'} UTF-8 input</p>}{step.context_manifest.sources?.length ? <ul>{step.context_manifest.sources.slice(0, 32).map((source, index) => <li key={`${source.source_ids?.[0] ?? 'source'}-${index}`}><strong>{source.category?.replaceAll('_', ' ') ?? 'Source'} · {source.status ?? 'recorded'}:</strong> {source.source_ids?.join(', ') ?? 'ID unavailable'} — {source.reason ?? source.representation ?? 'See saved source'}</li>)}</ul> : <p>No source-level manifest was recorded for this historical step.</p>}{(step.context_manifest.sources?.length ?? 0) > 32 && <p>{(step.context_manifest.sources?.length ?? 0) - 32} additional manifest entries omitted from this view.</p>}{step.context_manifest.omitted_prior_session_findings?.count ? <p>{step.context_manifest.omitted_prior_session_findings.count} older session findings omitted; source IDs: {step.context_manifest.omitted_prior_session_findings.source_ids.join(', ') || 'bounded pointer list unavailable'}.</p> : null}{step.context_manifest.omitted_prior_failures?.count ? <p>{step.context_manifest.omitted_prior_failures.count} older operational failures omitted; attempt IDs: {step.context_manifest.omitted_prior_failures.attempt_ids.join(', ') || 'bounded pointer list unavailable'}.</p> : null}<ContextManifestNotes manifest={step.context_manifest}/></details>}{step.potential_truncation_fields?.length ? <p className="research-output-warning" role="status"><strong>Potentially truncated output:</strong> {step.potential_truncation_fields.join(', ')} reached a structured output field limit. Review the saved source text before relying on it.</p> : null}{step.provider_input_audit && <details className="context-used-disclosure"><summary>Exact provider input · {step.provider_input_audit.status}</summary><p>Saved request body before dispatch; authorization headers and credentials are excluded.</p><h5>Role instructions</h5><pre>{String(step.provider_input_audit.request_body.instructions ?? '')}</pre><h5>Submitted input</h5><pre>{JSON.stringify(step.provider_input_audit.request_body.input, null, 2)}</pre></details>}</li>)}</ol></div>}
            {session.artifacts.length > 0 && <div className="outcome-provenance-group"><h4>Saved artifact origins</h4><ul className="outcome-provenance-list">{session.artifacts.map(artifact => <li key={artifact.id}><div className="outcome-label-value"><dt>Artifact {artifact.sequence}</dt><dd>{artifact.id}</dd></div><p>{artifact.session_id ? `Session ${artifact.session_id}` : 'Source session unavailable'} · {artifact.strategy_id ? `Strategy ${artifact.strategy_id}` : 'Strategy unavailable'} · {typeof artifact.strategy_cycle === 'number' ? `Round ${artifact.strategy_cycle}` : 'Round unavailable'}</p></li>)}</ul></div>}
            {otherPriorFindings.length > 0 && <div className="outcome-provenance-group"><h4>Other prior session sources</h4><p>Available history; these sources are not implied to be researcher-approved transfers.</p><ul className="outcome-provenance-list">{otherPriorFindings.map(finding => <li key={`${finding.session_id}:${finding.id}`}><p><button type="button" className="text-view-link" onClick={() => onViewPriorSession(finding.session_id)}>Session #{finding.session_number} · {finding.strategy_title} · Artifact {finding.sequence}</button></p><p>{finding.id} · {finding.claim_or_question}</p><p><strong>Method:</strong> {finding.method}</p>{!!finding.assumptions?.length && <p><strong>Assumption/domain scope:</strong> {finding.assumptions.join(' · ')}</p>}<p><strong>Evidence status:</strong> {finding.evidence_status} · <strong>Coordinator:</strong> {finding.coordinator_decision}</p>{!!finding.objections.length && <p><strong>Objections:</strong> {finding.objections.join(' · ')}</p>}{!!finding.open_obligations.length && <p><strong>Open obligations:</strong> {finding.open_obligations.join(' · ')}</p>}{!!finding.obligation_reviews?.length && <ul>{finding.obligation_reviews.map(review => <li key={review.obligation_id}><strong>Prior obligation disposition ({review.status}, {review.epistemic_status}):</strong> {review.rationale} · Basis artifacts: {review.basis_artifact_ids.join(', ') || 'none recorded'}</li>)}</ul>}{!!finding.next_question && <p><strong>Next question:</strong> {finding.next_question}</p>}</li>)}</ul></div>}
            {!!session.peer_handoffs_prompted?.length && <div className="outcome-provenance-group"><h4>Peer handoffs prompted</h4><ul className="outcome-provenance-list">{session.peer_handoffs_prompted.map((handoff, index) => <li key={index}><pre>{JSON.stringify(handoff, null, 2)}</pre></li>)}</ul></div>}
            <div className="outcome-provenance-group"><h4>Session facts</h4><div className="outcome-label-value"><dt>Elapsed wall time</dt><dd>{typeof session.elapsed_seconds === 'number' ? formatDuration(session.elapsed_seconds) : 'Unavailable'}</dd></div><div className="outcome-label-value"><dt>Output limit</dt><dd>{typeof session.output_token_limit === 'number' ? `${session.output_token_limit} tokens per call` : 'Unavailable'}</dd></div><div className="outcome-label-value"><dt>Current action</dt><dd>{session.current_action || 'Unavailable'}</dd></div>{lastActivity && <div className="outcome-label-value"><dt>Last activity</dt><dd><time dateTime={lastActivity.timestamp}>{dateLabel(lastActivity.timestamp)}</time> · {lastActivity.message}</dd></div>}</div>
            {!!session.events.length && <section className="research-activity" aria-label="Recent session activity"><h4><button type="button" title={`${activityExpanded ? 'Collapse' : 'Expand'} recent activity`} aria-expanded={activityExpanded} aria-controls={`session-activity-${session.id}`} onClick={() => setActivityExpanded(value => !value)}><DisclosureChevron expanded={activityExpanded}/>Recent activity</button></h4><ol id={`session-activity-${session.id}`} hidden={!activityExpanded}>{session.events.slice(-8).map(event => <li key={event.sequence}><time dateTime={event.timestamp}>{dateLabel(event.timestamp)}</time><span>{event.message}</span></li>)}</ol></section>}
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
          <label className="human-intervention-strategy"><span className="sr-only">Strategy</span><select aria-label="Strategy" value={interventionStrategy} onChange={event => setInterventionStrategy(event.target.value)}><option value="*">All strategies</option>{targetStrategies.map(item => <option key={item.strategy_id} value={item.strategy_id}>{item.strategy_title}</option>)}</select></label>
          <label className="human-intervention-text">Feedback<textarea value={interventionText} maxLength={1200} rows={3} onChange={event => setInterventionText(event.target.value)} placeholder="Add a research instruction or evidence note."/></label>
          <div className="human-intervention-submit"><button type="submit" className="text-view-link" aria-describedby={`human-feedback-help-${session.id}`} disabled={interventionBusy || busy || !interventionText.trim()}>{interventionBusy ? 'Adding…' : 'Add'}</button><small id={`human-feedback-help-${session.id}`}>{interventionText.length}/1,200 · {interventionHelp}</small></div>
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

function CurrentUnderstandingView({ state, path, projectId, onEvidence, onSession }: { state: CurrentUnderstanding; path: string; projectId: string; onEvidence: (source: EvidencePointer) => void; onSession: (id: string) => void }) {
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [hasSuggestedResult, setHasSuggestedResult] = useState(false);
  const [suggestionBusy, setSuggestionBusy] = useState(false);
  const [suggestionError, setSuggestionError] = useState('');
  const [copied, setCopied] = useState(false);
  useEffect(() => { setSuggestion(null); setHasSuggestedResult(false); setSuggestionError(''); }, [path]);
  async function suggestStrategy() {
    if (suggestionBusy) return;
    setSuggestionBusy(true); setSuggestionError(''); setCopied(false); setSuggestion(null); setHasSuggestedResult(false);
    let finishProviderRequest = () => {};
    try {
      const configResponse = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { cache: 'no-store' });
      const config = await configResponse.json();
      if (!configResponse.ok) throw new Error(config.error ?? 'Could not read AI settings.');
      if (config.project_id !== projectId) throw new Error('Project identity changed. Reopen it before suggesting a strategy.');
      if (!config.available) throw new Error(config.message ?? 'Connect the selected AI account before requesting a suggestion.');
      finishProviderRequest = beginProviderRequest('strategy-suggestion');
      const result = await post<{ markdown: string | null }>('strategy-suggestions', {
        path, expected_binding: config.binding, expected_project_id: projectId,
      });
      setSuggestion(result.markdown?.trim() || null);
      setHasSuggestedResult(true);
    } catch (cause) {
      const message = errorMessage(cause);
      setSuggestionError(message); reportRequestFailure(message);
    } finally { finishProviderRequest(); setSuggestionBusy(false); }
  }
  async function copySuggestion() {
    if (!suggestion) return;
    try { await navigator.clipboard.writeText(suggestion); setCopied(true); }
    catch { setSuggestionError('Clipboard access failed. Select and copy the Markdown text.'); }
  }
  const sourceButton = (source: EvidencePointer, context: string) => <button type="button" className="text-view-link" disabled={!source.available} aria-label={`${context}: Session ${source.session_number}, Artifact ${source.artifact_sequence || 'unnumbered'}`} onClick={() => onEvidence(source)}>Session #{source.session_number} · {source.artifact_sequence ? `Artifact ${source.artifact_sequence}` : 'Saved evidence'}</button>;
  const excerpt = (text: string) => text.length > 360 ? `${text.slice(0, 360)}… (saved text continues)` : text;
  const findings = state.current_finding_ids.map(id => state.findings.find(row => row.id === id)).filter((row): row is CurrentFinding => !!row);
  const questions = [...state.obligations].sort((a, b) => (Number(b.actionable) * 4 + Number(b.status === 'historical_unreconciled') * 2) - (Number(a.actionable) * 4 + Number(a.status === 'historical_unreconciled') * 2));
  const suggested = state.next_investigations[0];
  const visibleQuestions = questions.filter(row => row.id !== suggested?.obligation_id && !['resolved_reported', 'superseded_reported', 'retracted_reported'].includes(row.status)).slice(0, 2);
  const remainingQuestions = questions.filter(row => row.id !== suggested?.obligation_id && !visibleQuestions.includes(row));
  const findingRow = (row: CurrentFinding) => <li key={row.id}><strong>{row.strategy_title || 'Historical strategy'}</strong><p>{excerpt(row.text)}</p><p className="hint">{row.status.replaceAll('_', ' ')} · {row.verification}</p><p>{sourceButton(row.source, 'Inspect finding')}</p></li>;
  const changeRow = (row: CurrentUnderstanding['changes'][number], index: number) => <li key={`${row.kind}-${row.source.session_id}-${row.source.artifact_id}-${index}`}><strong>{({ obligation_addressed: 'Resolution reported', obligation_superseded: 'Supersession reported', obligation_retracted: 'Retraction reported', local_refutation_reported: 'Local counterexample reported', later_finding_available: 'Later review saved', supersedes: 'Supersession reported', refutes: 'Refutation reported' } as Record<string, string>)[row.kind] || 'Saved assessment'}</strong><p>{excerpt(row.text)}</p><p className="hint">{row.caution}</p><p>{sourceButton(row.source, 'Inspect later evidence')}{row.earlier && <> · {sourceButton(row.earlier, 'Inspect earlier evidence')}</>}</p></li>;
  const questionRow = (row: CurrentQuestion) => <li key={row.id}><p>{excerpt(row.text)}</p><p className="hint">{row.status.replaceAll('_', ' ')} · {row.note}</p>{row.sources.length > 0 && <p>{sourceButton(row.sources.at(-1)!, 'Inspect obligation')}{row.narrative_resolution_sources.slice(-1).map(source => <span key={source.record_path}> · {sourceButton(source, 'Inspect narrative resolution')}</span>)}{row.dispositions.filter(item => item.valid).slice(-1).map(item => <span key={item.source.record_path}> · {sourceButton(item.source, 'Inspect disposition')}</span>)}</p>}</li>;
  return <details className="outcome-subsection current-understanding" open>
    <summary aria-label="Current understanding"><DisclosureChevron expanded={false}/><span>Current understanding</span>{suggestionBusy ? <span className="strategy-suggestion-progress" role="status" aria-live="polite"><span className="generating-hourglass" aria-hidden="true">⌛</span>Suggesting…</span> : <button type="button" className="text-view-link strategy-suggestion-trigger" onClick={event => { event.preventDefault(); event.stopPropagation(); void suggestStrategy(); }}>{hasSuggestedResult ? 'Suggest another strategy' : 'Suggest a strategy'}</button>}</summary>
    <p className="hint current-understanding-scope">{state.scope_note}</p>
    <div className="current-understanding-columns">
      <section><h3>Current findings</h3>{findings.length ? <><ol>{findings.slice(0, 2).map(findingRow)}</ol>{findings.length > 2 && <details><summary>{findings.length - 2} more local findings</summary><ol>{findings.slice(2).map(findingRow)}</ol></details>}</> : <p>No reviewed finding is saved. An empty or failed run establishes no answer.</p>}</section>
      <section><h3>What changed / superseded</h3>{state.changes.length ? <><ol>{state.changes.slice(0, 2).map(changeRow)}</ol>{state.changes.length > 2 && <details><summary>{state.changes.length - 2} more recorded changes</summary><ol>{state.changes.slice(2).map(changeRow)}</ol></details>}</> : <p>No explicit change or supersession is recorded. Different wording is not a contradiction.</p>}{state.failures.length > 0 && <details><summary>Execution states and unsuccessful branches</summary><ul>{state.failures.map((row, index) => <li key={`${row.session_id}-${index}`}>{row.status}: {row.note} <button className="text-view-link" type="button" onClick={() => onSession(row.session_id)}>Session #{row.session_number}</button></li>)}</ul></details>}</section>
      <section><h3>Open or not yet reconciled</h3>
        <h4>Possible next investigation</h4>{suggested ? <div><p>{suggested.question}</p><p className="hint">{suggested.qualification}</p>{sourceButton(suggested.source, 'Inspect suggested question')}</div> : <p>No current evidence-linked next investigation is determined. Inspect unreconciled history before choosing a new run.</p>}
        {visibleQuestions.length ? <ol>{visibleQuestions.map(questionRow)}</ol> : !questions.length && <p>No explicit obligation is recorded; this does not mean the question is solved.</p>}
        {remainingQuestions.length > 0 && <details><summary>{remainingQuestions.length} more recorded questions / dispositions</summary><ol>{remainingQuestions.map(questionRow)}</ol></details>}
      </section>
    </div>
    <details className="current-understanding-limits"><summary>Scope, uncertainty and earlier findings</summary><ul>{state.limitations.map(note => <li key={note}>{note}</li>)}</ul><p>All {state.findings.length} saved findings remain available in the session history below. No relationship or resolution is inferred from a change of wording.</p><ol>{state.findings.filter(row => !state.current_finding_ids.includes(row.id)).map(findingRow)}</ol></details>
    <div className="strategy-suggestion-feedback">
      {suggestionError && <p className="error" role="alert">{suggestionError}</p>}
      {hasSuggestedResult && !suggestion && !suggestionError && <p role="status">No additional strategy is warranted by the available evidence.</p>}
      {suggestion && <details className="strategy-suggestion-result">
        <summary>Suggested strategy</summary>
        <div className="strategy-suggestion-heading"><span>AI-authored Markdown · ephemeral suggestion</span><CopyToClipboardButton name="suggested strategy" copied={copied} onCopy={() => void copySuggestion()}/></div>
        <div className="outcome-markdown"><Suspense fallback={<p role="status">Preparing formatted suggestion…</p>}><RenderedMarkdown body={suggestion}/></Suspense></div>
      </details>}
    </div>
  </details>;
}

function ResearchWorkspace({ path, projectId, strategies, advancedOutcomeDetails, onEnableAdvancedOutcome, onViewStrategy, onForkFromFindings, onControlsChange, onRunningChange, onRevealNewSession }: { path: string; projectId: string; strategies: Strategy[]; advancedOutcomeDetails: boolean; onEnableAdvancedOutcome: () => Promise<void>; onViewStrategy: (id: string) => void; onForkFromFindings: (session: ResearchSession) => void; onControlsChange: (controls: ProcessControls) => void; onRunningChange: (running: boolean) => void; onRevealNewSession: () => void }) {
  const cloud = useCloudIdentity();
  const mockResearch = cloud?.mock_auth === true;
  const eligible = useMemo(() => strategies.filter(strategy => !strategy.removed_at && strategy.enabled), [strategies]);
  const [sessions, setSessions] = useState<ResearchSession[]>([]);
  const [currentUnderstanding, setCurrentUnderstanding] = useState<CurrentUnderstanding | null>(null);
  const selectedSessionId = useRef('');
  const sessionsLoaded = useRef(false);
  const initialRevealSessionId = useRef<string | null>(null);
  const [pendingStrategyIds, setPendingStrategyIds] = useState<string[]>([]);
  const [config, setConfig] = useState<{ available: boolean; model: string; reasoning_effort: string; mode: string; binding: string; message: string } | null>(null);
  const [limits, setLimits] = useState<ResearchLimits | null>(null);
  const [confirmStart, setConfirmStart] = useState(false);
  const [confirmRemoveId, setConfirmRemoveId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [readError, setReadError] = useState('');
  const [announcement, setAnnouncement] = useState('');
  const [expanded, setExpanded] = useState(() => window.localStorage.getItem(`sigma.sessionsPane:${path}`) !== 'false');
  const [expandedSessionIds, setExpandedSessionIds] = useState<Set<string>>(() => new Set());
  const readErrorReported = useRef(false);
  const lastAnnouncement = useRef('');
  const idempotencyKey = useRef<string | null>(null);
  const submittingStart = useRef(false);
  const activeSession = sessions.find(item => item.status === 'queued' || item.status === 'running');
  useEffect(() => { onRunningChange(activeSession?.status === 'running'); }, [activeSession?.id, activeSession?.status, onRunningChange]);

  useEffect(() => {
    const revealRunningSession = () => {
      const running = sessions.find(item => item.status === 'running');
      if (running) {
        onRevealNewSession();
        revealSession(running.id, true);
      }
    };
    window.addEventListener('sigma-reveal-running-session', revealRunningSession);
    return () => window.removeEventListener('sigma-reveal-running-session', revealRunningSession);
  }, [sessions, onRevealNewSession]);

  const load = useCallback(async (preferredId?: string, signal?: AbortSignal) => {
    const query = new URLSearchParams({ path });
    const response = await fetch(`/api/projects/research-sessions?${query}`, { signal });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error ?? 'Could not read research sessions');
    const nextSessions = data.sessions as ResearchSession[];
    setSessions(nextSessions);
    setCurrentUnderstanding(data.current_understanding?.project_id === projectId ? data.current_understanding as CurrentUnderstanding : null);
    readErrorReported.current = false;
    setReadError('');
    const requestedId = preferredId ?? selectedSessionId.current;
    const firstLoad = !sessionsLoaded.current;
    const chosen = (requestedId ? nextSessions.find(item => item.id === requestedId) : null)
      ?? (!sessionsLoaded.current && !selectedSessionId.current
        ? nextSessions.find(item => item.status === 'queued' || item.status === 'running' || item.status === 'paused') ?? nextSessions[0] ?? null
        : null);
    if (firstLoad) initialRevealSessionId.current = chosen?.status === 'running' ? chosen.id : null;
    sessionsLoaded.current = true;
    selectedSessionId.current = chosen?.id ?? '';
    if (firstLoad && chosen) setExpandedSessionIds(current => current.size ? current : new Set([chosen.id]));
    if (chosen) {
      const transition = `${chosen.id}:${chosen.status}:${chosen.current_action}`;
      if (chosen.status === 'failed' && lastAnnouncement.current.startsWith(`${chosen.id}:`) && /:(queued|running):/.test(lastAnnouncement.current)) {
        setError(chosen.message);
        reportRequestFailure(chosen.message);
      }
      if (lastAnnouncement.current && transition !== lastAnnouncement.current) {
        setAnnouncement(`Research session ${chosen.session_number}: ${chosen.status}. ${chosen.current_action}.`);
      }
      lastAnnouncement.current = transition;
    }
    return chosen;
  }, [path, projectId]);

  const reportReadFailure = useCallback((cause: unknown) => {
    const message = errorMessage(cause);
    setReadError(message);
    if (!readErrorReported.current) reportRequestFailure(message);
    readErrorReported.current = true;
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(undefined, controller.signal).catch(cause => { if (!controller.signal.aborted) reportReadFailure(cause); });
    return () => controller.abort();
  }, [load, reportReadFailure]);

  useEffect(() => {
    if (!activeSession) return;
    const stopWatching = watchResearchProviderActivity(path, projectId);
    const poll = () => {
      if (document.visibilityState === 'visible') void load().catch(reportReadFailure);
    };
    const timer = window.setInterval(poll, 2000);
    document.addEventListener('visibilitychange', poll);
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', poll); stopWatching(); };
  }, [activeSession?.id, activeSession?.status, load, path, projectId, reportReadFailure]);

  const sponsoredSession = cloud?.target === 'hosted'
    || (cloud?.target === 'local' && cloud.funding.selectedConnection === 'sponsored');
  async function begin(onlyIds?: string[]) {
    const chosenIds = onlyIds || eligible.map(strategy => strategy.id);
    setBusy(true); setError('');
    try {
      if (mockResearch) {
        if (!chosenIds.length || chosenIds.length > 12) throw new Error('Choose between one and twelve enabled strategies.');
        setPendingStrategyIds(chosenIds);
        setConfig({ available: true, model: 'mock-deterministic', reasoning_effort: 'none', mode: 'mock', binding: 'mock', message: 'Local simulation: no provider calls.' });
        setConfirmStart(true);
        return;
      }
      const response = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`);
      const current = await response.json();
      if (!response.ok) throw new Error(current.error ?? 'Could not read AI configuration');
      const limitResponse = await fetch(`/api/projects/research-limits?${new URLSearchParams({ path })}`);
      const currentLimits = await limitResponse.json();
      if (!limitResponse.ok) throw new Error(currentLimits.error ?? 'Could not read research limits');
      const validation = validateLimitDraft(draftLimits(currentLimits));
      if (!validation.value) {
        throw new Error(validation.errors.maximum_estimated_cost_usd
          ?? 'Saved research limits need attention. Update them in Project Settings → Limits before starting a session.');
      }
      if (!current.available) throw new Error(current.message ?? 'Connect the selected AI account before investigating');
      if (chosenIds.length > 12) {
        throw new Error('A session can include at most 12 enabled strategies. Disable strategies before starting.');
      }
      setPendingStrategyIds(chosenIds);
      setConfig(current); setLimits(currentLimits);
      setConfirmStart(true);
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  async function start() {
    if (submittingStart.current || !config || !pendingStrategyIds.length) return;
    submittingStart.current = true;
    setBusy(true); setError('');
    try {
      idempotencyKey.current ??= crypto.randomUUID();
      selectedSessionId.current = '';
      const next = mockResearch
        ? await post<ResearchSession>('research-sessions/mock', { path, strategy_id: pendingStrategyIds[0], expected_project_id: projectId, idempotency_key: idempotencyKey.current })
        : await post<ResearchSession>('research-sessions/start', { path, strategy_id: pendingStrategyIds[0], strategy_ids: pendingStrategyIds, expected_project_id: projectId, expected_binding: config.binding, expected_limits: limits, idempotency_key: idempotencyKey.current });
      idempotencyKey.current = null;
      setConfirmStart(false); selectedSessionId.current = next.id;
      lastAnnouncement.current = `${next.id}:${next.status}:${next.current_action}`;
      await load(next.id);
      if (next.status === 'running' || next.status === 'queued') onRevealNewSession();
      revealSession(next.id, next.status === 'running' || next.status === 'queued');
    } catch (cause) { setConfirmStart(false); await load().catch(() => {}); setError(errorMessage(cause)); }
    finally { submittingStart.current = false; setBusy(false); }
  }

  async function control(action: 'pause' | 'resume' | 'stop', target: ResearchSession | null = null) {
    if (!target) return;
    setBusy(true); setError('');
    try { await post<ResearchSession>(`research-sessions/${target.id}/control`, { path, action }); await load(target.id); }
    catch (cause) { await load(target.id).catch(() => {}); setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  const interventionSaved = useCallback(async (sessionId: string) => {
    await load(sessionId);
    setAnnouncement('Human feedback added for a later agent step. No provider call was made.');
  }, [load]);

  function requestResume(target: ResearchSession) {
    void control('resume', target);
  }

  function revealSession(id: string, collapsePrevious = false) {
    setExpanded(true);
    window.localStorage.setItem(`sigma.sessionsPane:${path}`, 'true');
    setExpandedSessionIds(current => collapsePrevious ? new Set([id]) : new Set(current).add(id));
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const row = document.querySelector<HTMLElement>(`[data-session-id="${CSS.escape(id)}"]`);
      row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
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
        setAnnouncement(`Opened saved evidence from Session #${source.session_number}.`);
      } else if (row) {
        row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        setAnnouncement('The owning session is open; inspect its saved evidence.');
      }
    }));
  }

  async function removeSession(target: ResearchSession) {
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/projects/research-sessions/${encodeURIComponent(target.id)}`, {
        method: 'DELETE', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, expected_updated_at: target.updated_at }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Session removal failed');
      setConfirmRemoveId('');
      setExpandedSessionIds(current => { const next = new Set(current); next.delete(target.id); return next; });
      if (selectedSessionId.current === target.id) selectedSessionId.current = '';
      await load();
      setAnnouncement(`Session #${result.session_number} removed. Strategy and other sessions were kept.`);
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  const playLabel = 'Start a new research session';
  const requiresSponsoredCost = cloud?.target === 'hosted'
    || (cloud?.target === 'local' && cloud.funding.selectedConnection === 'sponsored');
  const play = useCallback(() => {
    if (busy || readError) return;
    setExpanded(true); window.localStorage.setItem(`sigma.sessionsPane:${path}`, 'true');
    if (activeSession || !eligible.length) return;
    setConfirmStart(false);
    void begin();
  }, [activeSession, busy, eligible, readError, path]);
  const stop = useCallback(() => {
    if (activeSession?.status === 'running' && !busy && !readError) void control('stop', activeSession);
  }, [activeSession, busy, readError]);
  useEffect(() => {
    onControlsChange({
      play, stop, confirming: confirmStart, start: () => void start(), cancel: () => setConfirmStart(false), nextSessionNumber: Math.max(0, ...sessions.map(item => item.session_number)) + 1,
      confirmationSummary: limits ? `up to ${limits.model_calls} agent turns · ${limits.research_rounds} rounds per strategy · shared across selected strategies · ${limits.maximum_estimated_cost_usd === null ? 'no session cost cap' : `up to $${limits.maximum_estimated_cost_usd.toFixed(2)}`} · ${Math.min(limits.session_duration_minutes, sponsoredSession ? 15 : limits.session_duration_minutes)} min` : undefined,
      playDisabled: busy || !!readError || confirmStart || (activeSession
        ? true
        : !eligible.length),
      stopDisabled: busy || !!readError || activeSession?.status !== 'running',
      playLabel,
    });
  }, [activeSession, busy, confirmStart, eligible.length, limits, onControlsChange, stop, play, playLabel, readError, sessions, sponsoredSession]);

  const orderedSessions = [...sessions].sort((left, right) => left.session_number - right.session_number);

  useEffect(() => {
    const revealId = initialRevealSessionId.current;
    if (!revealId || activeSession?.id !== revealId) return;
    initialRevealSessionId.current = null;
    onRevealNewSession();
    revealSession(revealId, true);
  }, [activeSession?.id, onRevealNewSession]);

  const runningCount = sessions.filter(item => item.status === 'running' || item.status === 'queued').length;
  return <section className={`sessions-pane workspace-pane${expanded ? '' : ' is-collapsed'}`} aria-labelledby="sessions-heading">
    <header className="workspace-pane-heading sessions-pane-heading">
      <h2 id="sessions-heading" tabIndex={-1}><button type="button" className="workspace-section-disclosure" title={`${expanded ? 'Collapse' : 'Expand'} Sessions section`} aria-expanded={expanded} aria-controls="sessions-pane-content" onClick={() => setExpanded(value => { window.localStorage.setItem(`sigma.sessionsPane:${path}`, String(!value)); return !value; })}><DisclosureChevron expanded={expanded}/>Sessions</button></h2>
      <p className="section-count">{sessions.length} {sessions.length === 1 ? 'session' : 'sessions'}, {runningCount} running</p>
    </header>

    <div id="sessions-pane-content" hidden={!expanded}>
    {currentUnderstanding && <CurrentUnderstandingView state={currentUnderstanding} path={path} projectId={projectId} onEvidence={revealEvidence} onSession={revealSession}/>}
    <div className="session-table">
      {sessions.length ? <ol className="session-list" aria-label="Research sessions">
        {orderedSessions.map(item => {
          const currentAction = (readError && activeSession?.id === item.id ? `State unknown · ${item.current_action}` : item.current_action)
            .replace(/\bpaused\b/gi, 'stopped').replace(/\bpausing\b/gi, 'stopping').replace(/\bpause\b/gi, 'stop');
          const sessionExpanded = expandedSessionIds.has(item.id);
          return <li className="session-row" key={item.id} data-session-id={item.id}>
            <div className="session-row-heading">
              <div className="session-summary">
                <div className="session-title-line"><button type="button" className="session-row-disclosure" title={`${sessionExpanded ? 'Collapse' : 'Expand'} Session ${item.session_number} details`} aria-expanded={sessionExpanded} aria-controls={`session-content-${item.id}`} onClick={() => setExpandedSessionIds(current => { const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next; })}><DisclosureChevron expanded={sessionExpanded}/><span className="session-row-title">Session #{item.session_number}</span></button>
                <div className="session-heading-actions" aria-label={`Session ${item.session_number} actions`}>
                  {(item.status === 'stopped' || item.status === 'paused') && <button type="button" className="text-view-link text-view-icon workspace-icon-button process-control session-mini-process-control" aria-label={`Resume Session ${item.session_number}`} title={`Resume session #${item.session_number}`} data-tooltip={`Resume session #${item.session_number}`} disabled={busy || !!readError || (!!activeSession && activeSession.id !== item.id)} onClick={() => requestResume(item)}><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M6 3.8v12.4L16 10 6 3.8Z"/></svg></button>}
                  {['queued', 'running'].includes(item.status) && <button type="button" className="text-view-link text-view-icon workspace-icon-button process-control session-mini-process-control" aria-label={`Stop Session ${item.session_number}`} title={`Stop Session ${item.session_number}; it can be resumed later`} data-tooltip={`Stop Session ${item.session_number}`} disabled={busy} onClick={() => void control('stop', item)}><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5h10v10H5z"/></svg></button>}
                  <SessionLogButton sessionId={item.id} sessionNumber={item.session_number} path={path}/>
                  <button type="button" className="text-view-link destructive-action session-remove-link" title={`Remove Session ${item.session_number} and its saved research`} disabled={busy} onClick={() => setConfirmRemoveId(item.id)}>Remove</button>
                  {confirmRemoveId === item.id && <div className="session-remove-actions"><div className="research-stop-confirm" role="group" aria-label={`Confirm remove Session ${item.session_number}`}><p>{['queued', 'running', 'paused'].includes(item.status) ? `Stop and remove Session #${item.session_number}, including its saved research record and artifacts?` : `Remove Session #${item.session_number} and its saved research record and artifacts?`}</p><div className="session-remove-confirm-actions"><button type="button" className="text-view-link destructive-action" title={`Confirm removal of Session ${item.session_number}`} disabled={busy} onClick={() => void removeSession(item)}>Confirm</button><button type="button" className="text-view-link" title={`Keep Session ${item.session_number}`} disabled={busy} onClick={() => setConfirmRemoveId('')}>Cancel</button></div></div></div>}
                </div></div>
                <span className={`session-status session-${item.status === 'paused' ? 'stopped' : item.status}`} aria-label={`Lifecycle status: ${item.status === 'paused' ? 'stopped' : item.status}`}>{item.status === 'running' || item.status === 'stopped' || item.status === 'paused' ? <>{item.status === 'paused' ? 'stopped' : item.status}<i aria-hidden="true"/></> : <><i aria-hidden="true"/>{item.status}</>}</span>
                {(item.status === 'paused' || item.status === 'stopped') && (() => { const guidance = stoppedSessionGuidance(item); const hasCompleteFinding = item.artifacts.some(artifact => Object.keys(artifact.investigator_output).length > 0 && Object.keys(artifact.skeptic_output).length > 0); return <div className="stopped-session-guidance" role="note" aria-label={`Why session ${item.session_number} stopped and what to do next`}><p><strong>Why it stopped:</strong> {guidance.cause}</p><p><strong>Next:</strong> {guidance.next}</p>{!hasCompleteFinding && <p>The session is stopped and has not saved a complete Investigator/Skeptic finding. No answer to the project question is established yet.</p>}</div>; })()}
                <small className={`session-strategy-name session-outcome-inline outcome-${item.outcome.assessment}`}><span>{outcomeDisplayLabel(item)}</span></small>
                <small className="session-progress-inline">Round {item.cycle} of {item.cycle_limit ?? 3} · {item.calls_used}/{item.call_limit} agent turns · {sessionEstimatedCostLabel(item)}</small>
              </div>
            </div>
            <ResearchSessionContents path={path} session={{ ...item, current_action: currentAction }} expanded={sessionExpanded} advancedOutcomeDetails={advancedOutcomeDetails} busy={busy} onEnableAdvancedOutcome={onEnableAdvancedOutcome} onViewStrategy={onViewStrategy} onViewPriorSession={revealSession} onForkFromFindings={onForkFromFindings} onInterventionSaved={interventionSaved}/>
          </li>;
        })}
      </ol> : !confirmStart && <p className="sessions-empty">No sessions yet. Use <span className="sr-only">Play</span><svg className="sessions-empty-play-icon" viewBox="0 0 20 20" aria-hidden="true"><path d="M6 3.8v12.4L16 10 6 3.8Z"/></svg> in Strategies to start one.</p>}
    </div>
    {readError && <p className="error" role="alert">Unable to confirm session state. Last confirmed information is shown: {readError}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    </div>
    <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
  </section>;
}

type TextFormat = 'plain' | 'markdown';
type TextDisplay = 'plain' | 'rendered';
type TextVersion = { body: string; kind: 'authored' | 'ai_derived'; current: boolean; source_digest: string; source_format: TextFormat; created_at: string; provenance: { provider: string; model: string; reasoning_effort: string | null } | null; warnings: string[] };
type TextRepresentations = { source_format: TextFormat; source_digest: string; plain: TextVersion | null; markdown: TextVersion | null };

async function post<T>(route: string, body: object = {}, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/projects/${route}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error ?? JSON.stringify(data.detail) ?? 'Request failed');
  return data;
}
const errorMessage = (error: unknown) => error instanceof Error ? error.message : String(error);
function CopyToClipboardButton({ name, copied, disabled = false, onCopy }: { name: string; copied: boolean; disabled?: boolean; onCopy: () => void }) {
  return <button type="button" className="text-view-link text-view-icon workspace-icon-button text-copy-button" aria-label={copied ? `Copied ${name} to clipboard` : `Copy ${name}`} title={copied ? 'Copied' : `Copy ${name}`} data-tooltip={copied ? 'Copied' : `Copy ${name}`} disabled={disabled} onClick={onCopy}>{copied ? <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M8 4H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/><path d="m8 12 3 3 10-10"/></svg> : <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>}</button>;
}
async function sha256Text(value: string): Promise<string> {
  const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)));
  return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
}
const projectUrl = (path: string) => `/project?${new URLSearchParams({ path })}`;
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
          <button type="button" className="settings-cancel" title="Close without downloading" disabled={busy} onClick={() => cancel()}>Cancel</button>
        </div>
      </header>
      <div className="settings-body">
        <fieldset className="export-type-options" disabled={busy}>
          <legend>File type</legend>
          {!demo && <label><input type="radio" name="export-type" value="bundle" checked={exportType === 'bundle'} onChange={() => setExportType('bundle')}/> Importable project</label>}
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
      <footer className="export-footer">
        <button type="submit" className="settings-submit" title="Download the selected project export" disabled={busy}>{busy ? 'Downloading…' : 'Download'}</button>
      </footer>
    </form>
  </dialog>;
}

type PaperSummary = { paper_id: string; title: string; created_at: string; snapshot_sha256: string; validation_warnings: string[]; author_review_warnings?: string[]; pdf_available?: boolean; generation: { mode: string; model: string; reasoning_effort: string; call_limit: number; provider_calls_attempted?: number; provider_calls_prior_runs?: number; provider_calls_lifetime_total?: number; long_form?: boolean; evidence_batch_count?: number; evidence_fields_omitted?: number; omitted_evidence?: { field_ref: string; source_ref: string; field: string; reason: string }[]; evidence_note_compaction_events?: number; reduction_source_refs_omitted?: string[]; evidence_conflict_note_count?: number; evidence_conflicts?: { statement: string; evidence_refs: string[] }[] } };
type PaperProgress = { status: 'active' | 'interrupted' | 'failed' | 'cancelled' | 'complete'; stage: 'snapshot' | 'writing' | 'evidence' | 'consolidation' | 'planning' | 'sections' | 'retry' | 'validation' | 'compile' | 'complete'; current: number | null; total: number | null; started_at: string; elapsed_seconds: number; activity_state?: 'active' | 'milestone' | 'complete' };
type PaperRecord = PaperSummary & { draft: { title: string; abstract: string; abstract_claim_ids: string[]; problem_framing: string[]; problem_framing_claim_ids: string[]; methods: string[]; methods_claim_ids: string[]; claims: { id: string; statement: string; status: string; evidence_refs: string[]; reasoning: string }[]; sections: { heading: string; paragraphs: string[]; claim_ids: string[] }[]; limitations: string[]; open_obligations: string[]; conclusions: string[]; conclusion_claim_ids: string[] }; obligation_reconciliation?: { text: string; source_refs: string[]; status: string }[]; snapshot: { sources: { id: string; kind: string }[] } };

function paperProgressOperation(progress: PaperProgress): string {
  const count = progress.current !== null && progress.total !== null ? ` (${progress.current} of ${progress.total})` : '';
  const milestone = progress.activity_state === 'milestone';
  switch (progress.stage) {
    case 'snapshot': return 'Preparing research evidence';
    case 'writing': return 'Writing the paper';
    case 'evidence': return `${milestone ? 'Evidence extracted' : 'Extracting evidence'}${count}`;
    case 'consolidation': return 'Consolidating findings';
    case 'planning': return milestone ? 'Paper plan ready' : 'Planning the paper';
    case 'sections': return `${milestone ? 'Section written' : 'Writing sections'}${count}`;
    case 'validation': return milestone ? 'Paper validated' : 'Validating the paper';
    case 'compile': return 'Compiling PDF';
    case 'retry': return `Retrying provider connection${count}`;
    case 'complete': return 'Complete';
  }
}

function paperElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return minutes ? `${minutes}m ${remaining}s` : `${remaining}s`;
}

function AIPaperDialog({ path, projectId, onCancel, guest = false }: { path: string; projectId: string; onCancel: () => void; guest?: boolean }) {
  const ai = useAI();
  const dialog = useRef<HTMLDialogElement>(null);
  const request = useRef<AbortController | null>(null);
  const [papers, setPapers] = useState<PaperSummary[]>([]);
  const [selected, setSelected] = useState<PaperRecord | null>(null);
  const [binding, setBinding] = useState('');
  const [model, setModel] = useState('');
  const [mode, setMode] = useState('');
  const [effort, setEffort] = useState('');
  const [checkpointMismatch, setCheckpointMismatch] = useState<any>(null);
  const [continuationAvailable, setContinuationAvailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState('');
  const [paperProgress, setPaperProgress] = useState<PaperProgress | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(true);
  const [expandedPaperId, setExpandedPaperId] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState('');
  useEffect(() => { dialog.current?.showModal(); if (guest) setLoading(false); else void refresh(); return () => request.current?.abort(); }, [guest]);
  async function refresh(keepId?: string) {
    setLoading(true);
    try {
      const query = new URLSearchParams({ path });
      const [listResponse, configResponse, progressResponse] = await Promise.all([
        fetch(`/api/projects/papers?${query}`, { cache: 'no-store' }),
        fetch(`/api/projects/proposals/config?${query}`, { cache: 'no-store' }),
        fetch(`/api/projects/papers/progress?${query}`, { cache: 'no-store' }),
      ]);
      const list = await listResponse.json(); const config = await configResponse.json();
      const savedProgress = progressResponse.ok ? await progressResponse.json() : null;
      setPaperProgress(savedProgress?.progress ?? null);
      if (!listResponse.ok) throw new Error(list.error ?? 'Could not load saved AI papers.');
      setPapers(list.papers as PaperSummary[]);
      if (!configResponse.ok || !config.available) { setBinding(''); setModel(config.model ?? ''); setMode(config.mode ?? ''); setEffort(config.reasoning_effort ?? ''); setCheckpointMismatch(null); setContinuationAvailable(false); }
      else {
        setBinding(config.binding); setModel(config.model); setMode(config.mode); setEffort(config.reasoning_effort);
        const params = new URLSearchParams({
          path, long_form: 'false', expected_project_id: projectId, expected_binding: config.binding,
          mode: config.mode, model: config.model, reasoning_effort: config.reasoning_effort,
        });
        const preflightResponse = await fetch(`/api/projects/papers/preflight?${params}`, { cache: 'no-store' });
        const preflight = await preflightResponse.json();
        setContinuationAvailable(Boolean(
          preflightResponse.ok && preflight.checkpoint_exists && preflight.resume_available &&
          (preflight.completed_batches > 0 || preflight.evidence_indexed || preflight.outline_complete ||
           preflight.completed_sections > 0 || preflight.provider_calls_attempted > 0)
        ));
        if (preflightResponse.ok && preflight.checkpoint_exists && !preflight.resume_available && preflight.checkpoint_can_restart)
          setCheckpointMismatch(preflight);
        else setCheckpointMismatch(null);
      }
      const nextId = keepId ?? selected?.paper_id ?? list.papers?.[0]?.paper_id;
      if (nextId) {
        const response = await fetch(`/api/projects/papers/${encodeURIComponent(nextId)}?${query}`, { cache: 'no-store' });
        const record = await response.json(); if (!response.ok) throw new Error(record.error ?? 'Could not open this paper version.');
        setSelected(record as PaperRecord);
      } else setSelected(null);
      setError(!configResponse.ok || !config.available ? (config.message ?? 'Connect an eligible AI provider to author a paper.') : '');
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    if (paperProgress?.status !== 'active') return;
    let stopped = false;
    const poll = async () => {
      try {
        const response = await fetch(`/api/projects/papers/progress?${new URLSearchParams({ path })}`, { cache: 'no-store' });
        const body = await response.json();
        if (!stopped && response.ok) setPaperProgress(body.progress ?? null);
      } catch { /* Keep the last saved operation visible until connectivity returns. */ }
    };
    const timer = window.setInterval(() => void poll(), 1000);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [path, paperProgress?.status]);
  async function openPaper(id: string) {
    try {
      const response = await fetch(`/api/projects/papers/${encodeURIComponent(id)}?${new URLSearchParams({ path })}`, { cache: 'no-store' });
      const record = await response.json(); if (!response.ok) throw new Error(record.error ?? 'Could not open this paper version.');
      setSelected(record as PaperRecord); setError('');
    } catch (cause) { setError(errorMessage(cause)); }
  }
  async function removePaper(id: string) {
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/projects/papers/${encodeURIComponent(id)}?${new URLSearchParams({ path })}`, { method: 'DELETE' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Could not remove this paper version.');
      const remaining = papers.filter(item => item.paper_id !== id);
      setPapers(remaining); setConfirmDeleteId(''); setExpandedPaperId('');
      if (selected?.paper_id === id) setSelected(null);
      if (remaining.length) await openPaper(remaining[0].paper_id);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  async function restartCheckpoint() {
    if (busy || !checkpointMismatch?.checkpoint_can_restart || !binding) return;
    setBusy(true); setError(''); setSuccess(''); setPhase('Clearing unfinished paper work…');
    try {
      const response = await fetch('/api/projects/papers/restart', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path, expected_project_id: projectId, expected_binding: binding,
          expected_snapshot_sha256: checkpointMismatch.snapshot_sha256, confirm_restart: true,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Could not reset the long-form checkpoint.');
      setCheckpointMismatch(null);
      setContinuationAvailable(false);
      setPaperProgress(null);
      setSuccess(result.evidence_updated_since_preflight
        ? 'Unfinished paper work cleared using the latest research evidence. No generation has started. Saved versions remain unchanged; choose Generate to start.'
        : 'Unfinished paper work cleared. No generation has started. Saved versions remain unchanged; choose Generate to start.');
      await refresh(selected?.paper_id);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  async function generatePaper() {
    if (busy || !binding) return;
    const controller = new AbortController(); request.current = controller;
    setBusy(true); setPhase('Preparing research evidence…'); setError(''); setSuccess('');
    let finishProvider = () => {};
    let requestDispatched = false;
    let providerCallsAttempted: number | undefined;
    try {
      const preflightParams = new URLSearchParams({
        path, long_form: 'false', expected_project_id: projectId, expected_binding: binding,
        mode, model, reasoning_effort: effort,
      });
      const preflightResponse = await fetch(`/api/projects/papers/preflight?${preflightParams}`, { cache: 'no-store', signal: controller.signal });
      const preflight = await preflightResponse.json();
      if (!preflightResponse.ok) throw new Error(preflight.error ?? 'Could not size the evidence snapshot.');
      if (preflight.checkpoint_exists && !preflight.resume_available) {
        setCheckpointMismatch(preflight);
        throw new Error('Unfinished paper work belongs to different project evidence or AI settings. Review the message below before starting over.');
      }
      finishProvider = beginProviderRequest('ai-paper');
      setPhase(preflight.draft_recovery_available
        ? 'Reusing the validated draft from the previous attempt; compiling its PDF…'
        : 'Generating paper…');
      requestDispatched = true;
      const response = await fetch('/api/projects/papers', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ path, expected_project_id: projectId, expected_binding: binding, expected_snapshot_sha256: preflight.snapshot_sha256, long_form: false }) });
      if (!response.ok) {
        const failure = await response.json().catch(() => null);
        throw new Error(failure?.error ?? `Paper generation failed (${response.status}); no version was published.`);
      }
      if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body)
        throw new Error(`Paper generation failed with an invalid server response (${response.status}). No version was published.`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let result: { paper_id: string } | null = null;
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
          if (event.type === 'complete') result = event.result as { paper_id: string };
          if (event.type === 'progress') {
            const nextProgress = { ...event, status: event.state === 'complete' ? 'complete' : 'active', activity_state: event.state } as PaperProgress;
            setPaperProgress(nextProgress);
            setPhase(`${paperProgressOperation(nextProgress)} · Elapsed ${paperElapsed(nextProgress.elapsed_seconds)}`);
          }
          if (event.type === 'heartbeat' && event.progress) setPaperProgress(event.progress as PaperProgress);
        }
        if (done) break;
      }
      if (!result) throw new Error('Paper generation ended without a completed version. No version was published.');
      await refresh(result.paper_id);
      setSuccess('Paper saved in Saved versions.');
    } catch (cause) {
      if (controller.signal.aborted) {
        const message = requestDispatched
          ? 'Generation cancelled. Provider completion or usage may be unknown. Check Saved versions and your provider usage before trying again.'
          : 'Generation cancelled before a provider request was started.';
        setError(message);
      }
      else reportRequestFailure(errorMessage(cause));
      await refresh(selected?.paper_id);
      if (!controller.signal.aborted) {
        const message = errorMessage(cause);
        setError(requestDispatched && providerCallsAttempted === 0
          ? `${message} No provider request was made for this attempt. Saved versions and research evidence are unchanged; refresh the snapshot before retrying.`
          : requestDispatched
            ? `${message} Check Saved versions and your provider usage before generating again; a provider request may have completed or consumed allowance before the error.`
          : message);
      }
    } finally { finishProvider(); request.current = null; setBusy(false); }
  }
  return <dialog ref={dialog} className="project-settings-dialog ai-paper-dialog" aria-labelledby="ai-paper-heading" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <header className="settings-header"><h2 id="ai-paper-heading">Academic paper using LaTeX</h2><div className="settings-actions"><button type="button" className="settings-cancel" disabled={busy} onClick={onCancel}>Close</button></div></header>
    <div className="settings-body ai-paper-body">
      {guest ? <p className="settings-hint" role="status">Sign in to export your research as TeX.</p> : <>
      <p className="settings-hint">Create a LaTeX paper from this project’s saved research, including supporting evidence, unsuccessful approaches, contradictions, and unanswered questions.</p>
      <p className="settings-hint">The paper is AI-generated and has not been independently verified. Generation uses your selected provider and may consume allowance or incur charges. It does not start a research session.</p>
      <p className="settings-hint ai-paper-model">Selected model: <strong>{model || 'Loading…'}</strong></p>
      {checkpointMismatch && <div className="research-stop-confirm ai-paper-restart-notice" role="group" aria-label="Unfinished paper work needs a fresh start">
        <p>Unfinished paper work belongs to different project evidence or AI settings and cannot continue. Starting over clears that unfinished work; saved versions stay available. A new generation may use provider allowance or incur charges.</p>
        <button type="button" className="text-view-link" disabled={busy || loading || !binding} onClick={() => void restartCheckpoint()}>Start over</button>
      </div>}
      <div className="ai-paper-controls">{!busy && <button type="button" className="text-view-link" disabled={loading || !binding || !!checkpointMismatch} onClick={() => void generatePaper()}>{continuationAvailable ? 'Continue' : 'Generate'}</button>}{busy && <button type="button" className="text-view-link" onClick={() => request.current?.abort()}>Cancel</button>}</div>
      {busy && !paperProgress && <p className="ai-paper-status" role="status" aria-live="polite"><span>{phase}</span></p>}
      {paperProgress && <p className="ai-paper-status ai-paper-progress" role="status" aria-live="polite"><strong>{paperProgress.status === 'active' ? 'Generating paper' : paperProgress.status === 'failed' ? 'Generation failed' : paperProgress.status === 'cancelled' ? 'Generation cancelled' : paperProgress.status === 'interrupted' ? 'Generation interrupted' : 'Paper complete'}</strong><span>{paperProgressOperation(paperProgress)} · Elapsed {paperElapsed(paperProgress.elapsed_seconds)}</span>{['failed', 'cancelled', 'interrupted'].includes(paperProgress.status) && <span>{continuationAvailable ? 'Saved work is available. Choose Continue to resume without repeating completed stages.' : 'Review the error, then refresh to check whether work can be resumed.'}</span>}</p>}
      {success && <p className="ai-paper-status" role="status">{success}</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {loading && <p>Loading saved versions…</p>}
      {!loading && papers.length > 0 && <section className="saved-paper-library" aria-label="Saved AI papers"><h3>Saved versions</h3>{papers.map((paper, index) => <article className="saved-paper-card" key={paper.paper_id} data-paper-id={paper.paper_id}>
        <div className="saved-paper-row">
          <div className="saved-paper-heading">
            <button type="button" className="saved-paper-expand" aria-label={`${expandedPaperId === paper.paper_id ? 'Collapse' : 'Expand'} saved paper: ${paper.title}`} title={`${expandedPaperId === paper.paper_id ? 'Collapse' : 'Expand'} saved paper: ${paper.title}`} aria-expanded={expandedPaperId === paper.paper_id} aria-controls={`saved-paper-body-${paper.paper_id}`} onClick={() => { if (expandedPaperId === paper.paper_id) setExpandedPaperId(''); else { setExpandedPaperId(paper.paper_id); if (selected?.paper_id !== paper.paper_id) void openPaper(paper.paper_id); } }}><DisclosureChevron expanded={expandedPaperId === paper.paper_id}/><h4>{paper.title}</h4></button>
            <div className="saved-paper-meta"><p>{dateLabel(paper.created_at)} · Version {papers.length - index}</p><button type="button" className="text-view-link destructive-action" disabled={busy} onClick={() => setConfirmDeleteId(paper.paper_id)}>Remove</button></div>
          </div>
          <div className="saved-paper-actions"><a className="text-view-link" href={`/api/projects/papers/${encodeURIComponent(paper.paper_id)}/txt?${new URLSearchParams({ path })}`} download={`sigma-ai-paper-${paper.paper_id}.txt`}>Download text file</a><a className="text-view-link" href={`/api/projects/papers/${encodeURIComponent(paper.paper_id)}/tex?${new URLSearchParams({ path })}`} download={`sigma-ai-paper-${paper.paper_id}.tex`}>Download TeX file</a>{paper.pdf_available && <><a className="text-view-link" href={`/api/projects/papers/${encodeURIComponent(paper.paper_id)}/pdf?${new URLSearchParams({ path })}`} download={`sigma-ai-paper-${paper.paper_id}.pdf`}>Download PDF</a><a className="text-view-link" href={`/api/projects/papers/${encodeURIComponent(paper.paper_id)}/pdf?${new URLSearchParams({ path, open_in_browser: 'true' })}`} target="_blank" rel="noopener noreferrer">Open PDF in browser</a></>}</div>
        </div>
        {confirmDeleteId === paper.paper_id && <div className="saved-paper-confirm" role="group" aria-label={`Confirm removal of ${paper.title}`}><p>Remove this saved paper version and its PDF? Other versions and research history will remain.</p><button type="button" className="text-view-link destructive-action" disabled={busy} onClick={() => void removePaper(paper.paper_id)}>Confirm remove</button><button type="button" className="text-view-link" disabled={busy} onClick={() => setConfirmDeleteId('')}>Cancel</button></div>}
        <div id={`saved-paper-body-${paper.paper_id}`} hidden={expandedPaperId !== paper.paper_id || selected?.paper_id !== paper.paper_id}>{expandedPaperId === paper.paper_id && selected?.paper_id === paper.paper_id && <article className="ai-paper-preview">
        <h3>{selected.draft.title}</h3>
        <p><strong>Abstract.</strong> {selected.draft.abstract}</p>
        <p className="settings-hint">Abstract claim links: {selected.draft.abstract_claim_ids.join(', ') || 'None'}</p>
        <h4>Problem framing</h4>{selected.draft.problem_framing.map((text, index) => <p key={`framing-${index}`}>{text}</p>)}
        <p className="settings-hint">Claim links: {selected.draft.problem_framing_claim_ids.join(', ') || 'None'}</p>
        <h4>Methods and evidence</h4>{selected.draft.methods.map((text, index) => <p key={`method-${index}`}>{text}</p>)}
        <p className="settings-hint">Claim links: {selected.draft.methods_claim_ids.join(', ') || 'None'}</p>
        <p><strong>Snapshot.</strong> SHA-256 {selected.snapshot_sha256} · {selected.snapshot.sources.length} stable evidence sources</p>
        <p><strong>Generated.</strong> {selected.generation.model} ({selected.generation.mode}) · {dateLabel(selected.created_at)}{selected.generation.long_form ? ` · ${selected.generation.evidence_batch_count} evidence batches · ${selected.generation.provider_calls_attempted} calls this run · ${selected.generation.provider_calls_prior_runs} prior-run calls · ${selected.generation.provider_calls_lifetime_total} lifetime calls` : ''}</p>
        {!!selected.generation.omitted_evidence?.length && <details><summary>Evidence fields omitted from the generated index ({selected.generation.evidence_fields_omitted})</summary>{selected.generation.omitted_evidence.map(item => <p className="ai-paper-warning" key={item.field_ref}><code>{item.source_ref}{item.field}</code>: {item.reason}</p>)}</details>}
        {!!selected.generation.reduction_source_refs_omitted?.length && <details><summary>Sources omitted during index reduction ({selected.generation.reduction_source_refs_omitted.length})</summary>{selected.generation.reduction_source_refs_omitted.map(source => <p className="ai-paper-warning" key={source}><code>{source}</code></p>)}<p className="settings-hint">The complete original source records remain in the archived snapshot.</p></details>}
        {!!selected.generation.evidence_conflicts?.length && <details><summary>Potential conflicts and gaps identified by the evidence index ({selected.generation.evidence_conflict_note_count})</summary>{selected.generation.evidence_conflicts.map((conflict, index) => <p className="ai-paper-warning" key={`conflict-${index}`}>{conflict.statement} <strong>Sources:</strong> {conflict.evidence_refs.map(source => <code key={source}>{source} </code>)}</p>)}</details>}
        {selected.validation_warnings.map((warning, index) => <p className="ai-paper-warning" key={`system-${index}`}>Evidence validation: {warning}</p>)}
        {(selected.author_review_warnings ?? []).map((warning, index) => <p className="ai-paper-warning" key={`author-${index}`}>Author self-review (not independent): {warning}</p>)}
        {selected.draft.sections.map(section => <section key={section.heading}><h4>{section.heading}</h4>{section.paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}<p className="settings-hint">Claim links: {section.claim_ids.join(', ') || 'None'}</p></section>)}
        <h4>Claim register</h4>{selected.draft.claims.map(claim => <section key={claim.id}><p><strong>{claim.id} · {claim.status}:</strong> {claim.statement}</p><p>{claim.reasoning}</p><p className="settings-hint">Evidence: {claim.evidence_refs.join(', ') || 'No source reference'}</p></section>)}
        <h4>Limitations</h4><ul>{selected.draft.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>
        {selected.draft.open_obligations.length > 0 && <><h4>Open obligations</h4><ul>{selected.draft.open_obligations.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
        {!!selected.obligation_reconciliation?.length && <><h4>Frozen obligation reconciliation</h4><p className="settings-hint">Unlisted evidence obligations are not presumed resolved. References point to the saved evidence source and field.</p><ul>{selected.obligation_reconciliation.map((item, index) => <li key={index}><strong>{item.status}.</strong> {item.text}<br/><span className="settings-hint">{item.source_refs.join(', ') || 'No exact frozen-record match'}</span></li>)}</ul></>}
        <h4>Conclusions</h4>{selected.draft.conclusions.map((item, index) => <p key={`conclusion-${index}`}>{item}</p>)}
        <p className="settings-hint">Conclusion claim links: {selected.draft.conclusion_claim_ids.join(', ') || 'None'}</p>
        {!selected.pdf_available && <p role="status">The paper record is saved, but its compiled PDF is unavailable. Regenerate to create a new version with a PDF.</p>}
      </article>}</div>
      </article>)}</section>}
      </>}
    </div>
  </dialog>;
}

function FloatingTooltip() {
  const [active, setActive] = useState<{ element: HTMLElement; text: string } | null>(null);
  const tooltip = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLElement | null>(null);
  const pointerPosition = useRef({ x: 0, y: 0 });
  const tooltipPointerPosition = useRef({ x: 0, y: 0 });
  const suppressedAfterClick = useRef(new WeakSet<HTMLElement>());
  const previousDescriptions = useRef(new WeakMap<HTMLElement, string | null>());
  const hoverTimer = useRef<number | null>(null);
  const clearHoverTimer = () => {
    if (hoverTimer.current !== null) window.clearTimeout(hoverTimer.current);
    hoverTimer.current = null;
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
      if (element && suppressedAfterClick.current.has(element)) return;
      if (element && element !== activeRef.current) {
        clearHoverTimer();
        hide();
        hoverTimer.current = window.setTimeout(() => {
          hoverTimer.current = null;
          if (element.matches(':hover') && !suppressedAfterClick.current.has(element)) show(element);
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
  return createPortal(<div ref={tooltip} id="sigma-ui-tooltip" role="tooltip" className="sigma-ui-tooltip">{active.text}</div>, document.body);
}

function SettingsGearIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 1.72l-.08.54a2 2 0 0 1-1 1.44l-.47.27a2 2 0 0 1-1.74 0l-.44-.22a2 2 0 0 0-2.72.73l-.22.38a2 2 0 0 0 .73 2.73l.44.25a2 2 0 0 1 1 1.73v.54a2 2 0 0 1-1 1.73l-.44.25a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.72.73l.44-.22a2 2 0 0 1 1.74 0l.47.27a2 2 0 0 1 1 1.44l.08.54a2 2 0 0 0 2 1.72h.44a2 2 0 0 0 2-1.72l.08-.54a2 2 0 0 1 1-1.44l.47-.27a2 2 0 0 1 1.74 0l.44.22a2 2 0 0 0 2.72-.73l.22-.38a2 2 0 0 0-.73-2.73l-.44-.25a2 2 0 0 1-1-1.73v-.54a2 2 0 0 1 1-1.73l.44-.25a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.72-.73l-.44.22a2 2 0 0 1-1.74 0l-.47-.27a2 2 0 0 1-1-1.44l-.08-.54A2 2 0 0 0 12.22 2z"/><circle cx="12" cy="12" r="3"/></svg>;
}

const NEW_PROJECT_VALUES_KEY = 'sigma.newProjectValues';
function savedNewProjectValues(): Settings | null {
  try {
    const raw = window.localStorage.getItem(NEW_PROJECT_VALUES_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<Settings>;
    if (typeof value.title !== 'string' || typeof value.problem !== 'string' ||
        typeof value.investigation_type !== 'string' || typeof value.ai_model !== 'string' ||
        typeof value.reasoning_effort !== 'string' ||
        !(value.difficulty === null || value.difficulty === 'easy' || value.difficulty === 'medium' || value.difficulty === 'hard') ||
        typeof value.show_advanced_outcome_details !== 'boolean') return null;
    return value as Settings;
  } catch { return null; }
}

function TextViews({ path, scope, strategyId, source, projectTitle, contentClass, onSaved, mathematical, onSettings, settingsDisabled, settingsButtonRef, hideProjectHeading, hideProjectActions = false, hideEditAction = false, modeDisabled = false, combinedEditMode = false, editSignal = 0, markdownSlotId, onCombinedDraftChange, onEnterMode, onExitMode }: {
  path: string; scope: 'project' | 'strategy'; strategyId?: string; source: string; projectTitle?: string;
  contentClass: string; onSaved: (view: ProjectView) => void; mathematical: boolean; onSettings?: () => void; settingsDisabled?: boolean; settingsButtonRef?: React.RefObject<HTMLButtonElement | null>; hideProjectHeading?: boolean; hideProjectActions?: boolean; hideEditAction?: boolean; modeDisabled?: boolean; combinedEditMode?: boolean; editSignal?: number; markdownSlotId?: string; onCombinedDraftChange?: (draft: string) => void; onEnterMode?: () => boolean; onExitMode?: () => void;
}) {
  const [data, setData] = useState<TextRepresentations | null>(null);
  const preferenceKey = `sigma.markdownView:${path}:${scope}:${strategyId ?? ''}`;
  const [storedSelected, setSelected] = useState<TextDisplay>(() => window.localStorage.getItem(preferenceKey) === 'rendered' ? 'rendered' : 'plain');
  const selected: TextDisplay = storedSelected;
  const [rendering, setRendering] = useState(false);
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
    if (!version?.current || busy || (modeDisabled && !alreadyInMode) || (!alreadyInMode && onEnterMode && !onEnterMode())) return;
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
    if (!data || busy) return;
    const controller = new AbortController(); abort.current = controller; setBusy(true); setRendering(true); setError('');
    let finishProviderRequest = () => {};
    try {
      const settingsResponse = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal });
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
      }} title={renderTooltip}>{rendering ? <span aria-hidden="true">⌛</span> : <svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z" fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg>}</button>;
  const markdownControl = <span className="text-view-format-control">
    {markdownToggle}
    {rendering && <span className="text-view-format-status" role="status">Formatting with AI…</span>}
  </span>;
  const copyControl = <CopyToClipboardButton name={name} copied={copied} disabled={!current || editing || busy || combinedEditMode} onCopy={() => void copyText()}/>;
  const viewActions = <>
    {!markdownSlotId && markdownControl}

    {editing ? combinedEditMode ? null : <>
      <button type="submit" form={`text-form-${scope}-${strategyId ?? 'project'}`} className="text-view-link" title={`Save ${name}`} disabled={busy || !draft.trim()}>Save</button>
      <button type="button" className="text-view-link" title={`Cancel editing ${name}`} disabled={busy} onClick={() => cancelBodyEdit()}>Cancel</button>
      </> : data && version && !hideEditAction && <button type="button" className="text-view-link text-view-icon workspace-icon-button" aria-label={`Edit ${name}`} title={`Edit ${name}`} data-tooltip={`Edit ${name}`} disabled={modeDisabled} onClick={() => beginBodyEdit(selected === 'rendered')}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg></button>}

    {!hideProjectActions && scope === 'project' && !editing && <button ref={exportTrigger} type="button" className="copper-button project-export-trigger workspace-icon-button" aria-label="Export project" title="Export project" data-tooltip="Export project" onClick={() => setExportOpen(true)}><svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg></button>}
    {!hideProjectActions && onSettings && !editing && <button ref={settingsButtonRef} type="button" className="text-view-link text-view-icon workspace-icon-button" aria-label="Project settings" title="Project settings" data-tooltip="Project settings" disabled={settingsDisabled} onClick={onSettings}><SettingsGearIcon /></button>}
  </>;
  return <div ref={editorArea} className={`text-views${scope === 'project' ? ' project-text-views' : ''}${mathematical ? ' math-text-views' : ''}`}>
    {markdownPortalTarget && createPortal(markdownControl, markdownPortalTarget)}
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
      <button type="submit" className="text-view-link" title="Save project title" disabled={busy}>Save</button><button type="button" className="text-view-link" title="Cancel editing the project title" disabled={busy} onClick={() => cancel()}>Cancel</button>
      {error && <p role="alert" className="project-title-error">{error}</p>}
    </form> : <><h3 className="current-project">{view.project.title}</h3>
      <span id="project-markdown-slot" className="project-markdown-slot"/><button type="button" ref={trigger} className="text-view-link text-view-icon workspace-icon-button project-title-pencil" aria-label={`Edit project title and description: ${view.project.title}`} data-tooltip-disabled disabled={disabled || modeDisabled} onClick={() => { if (onEnterMode()) { setEditing(true); onEditDescription(); } }}>
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg>
      </button><span id="project-markdown-slot-copy" className="project-copy-slot"/> </>}
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
    orchestration: "SIGMA's session engine assembles bounded context, dispatches Investigator and Skeptic work, schedules eligible branches, manages budgets and decides whether another cycle can run.",
    investigator: 'A role-specific AI agent that develops claims, arguments, testable hypotheses and code proposals, while identifying assumptions and what remains uncertain.',
    investigatorFollowup: 'A later Investigator turn can take up the Skeptic’s critique, revise an approach, and explore what the session has learned so far.',
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
  // A single strategy's illustrative six turns. These are successive calls
  // using two agent roles, not six persistent agents or a scheduling promise.
  const exampleRounds = [
    { round: 1, title: 'Try an idea', investigator: 'Propose an approach', skeptic: 'Look for flaws', investigatorKey: 'investigator', skepticKey: 'skeptic' },
    { round: 2, title: 'Improve it', investigator: 'Revise after critique', skeptic: 'Challenge the revision', investigatorKey: 'investigatorRound2', skepticKey: 'skepticRound2' },
    { round: 3, title: 'Dig deeper', investigator: 'Test a stronger idea', skeptic: 'Check what remains uncertain', investigatorKey: 'investigatorRound3', skepticKey: 'skepticRound3' },
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
              <div className="about-strategy-round" aria-label="Research round: Investigator turn followed by Skeptic turn">
                <span>Investigator</span><b aria-hidden="true">→</b><span>Skeptic</span>
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
          <span className="about-agent-role">Investigator<small>Tries an idea</small></span>
          <svg className="about-agent-review-arrow" viewBox="0 0 240 40" preserveAspectRatio="none" aria-hidden="true" focusable="false"><defs><linearGradient id="about-agent-arrow-metal" x1="0" x2="1"><stop stopColor="#4c83a8"/><stop offset=".5" stopColor="#acd9fa"/><stop offset="1" stopColor="#4c83a8"/></linearGradient></defs><path d="M4 20 H226 M212 6 L228 20 L212 34" fill="none" stroke="url(#about-agent-arrow-metal)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/></svg>
          <span className="about-agent-role">Skeptic<small>Looks for flaws</small></span>
          <button ref={sessionToggle} type="button" className="about-session-toggle" aria-expanded={sessionExpanded} aria-controls="about-session-details" aria-label={(sessionExpanded ? 'Hide' : 'Show') + ' Investigator and Skeptic example'} onClick={toggleSession}>{sessionExpanded ? 'Hide' : 'Show'}</button>
        </div>
        <div id="about-session-details" ref={sessionPanel} className="about-session-detail" role="region" aria-labelledby="about-session-detail-heading" aria-hidden={!sessionExpanded} inert={!sessionExpanded} hidden={!sessionExpanded}>
          <div className="about-session-detail-inner">
            <h4 id="about-session-detail-heading">How an idea grows over six agent turns</h4>
            <p className="about-multi-agent-intro">Here is one possible path for <strong>one strategy</strong>. The Investigator makes an attempt; the Skeptic tests it; then the Investigator can build on what was learned. The process can repeat instead of ending after the first answer.</p>
            <p className="about-round-definition"><strong>One research round</strong> is an Investigator → Skeptic exchange within a strategy. <strong>One agent turn</strong> is a single contribution from either role.</p>
            <section className="about-agent-instantiation" aria-label="Example of three research rounds and six agent turns within one strategy">
              <h5>One strategy · Three rounds · Six turns</h5>
              <div className="about-agent-turns">
                {exampleRounds.map((round, index) => <div className="about-agent-round" key={round.round}>
                  <div className="about-agent-round-heading"><strong>Round {round.round}</strong><span>{round.title}</span></div>
                  <div className="about-agent-round-pair">
                    <div className="about-agent-turn">
                      <span className="about-turn-number">TURN {round.round * 2 - 1}</span>
                      {card(round.investigatorKey, 'Investigator', round.investigator, 'blue')}
                    </div>
                    <span className="about-turn-arrow" aria-hidden="true">→</span>
                    <div className="about-agent-turn">
                      <span className="about-turn-number">TURN {round.round * 2}</span>
                      {card(round.skepticKey, 'Skeptic', round.skeptic, 'blue')}
                    </div>
                  </div>
                  {index < exampleRounds.length - 1 && <div className="about-agent-return">
                    <svg viewBox="0 0 600 42" preserveAspectRatio="none" aria-hidden="true" focusable="false">
                      <path d="M505 3 V15 H155 V38 M147 30 L155 38 L163 30" fill="none" stroke="#75b7ef" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    <span>The Skeptic's feedback shapes the next attempt</span>
                    <b aria-hidden="true">↓</b>
                  </div>}
                </div>)}
              </div>
              <p className="about-agent-instantiation-note">These six turns show how <strong>one strategy</strong> can develop. Another strategy may take a different path—or stop early. Python and SageMath experiments may help when available. SIGMA saves the arguments, challenges, and results for review.</p>
            </section>
            <p className="about-shared-budget"><strong>Why repeat?</strong> A Skeptic may find a flaw the Investigator can fix or a question worth testing. Each new attempt can build on the last one.</p>
            <div className="about-exploration-space" role="group" aria-label="Example of how much research fits into one session">
              <p className="about-exploration-title">How much can one session explore?</p>
              <p>Suppose you select all three strategies and allow <strong>three rounds per strategy</strong>:</p>
              <div className="about-exploration-grid">
                {strategyExamples.map(strategy => <div className="about-exploration-row" key={strategy.id}>
                  <span className="about-exploration-strategy">{strategy.title}</span>
                  {[1, 2, 3].map(round => <span className="about-exploration-round" key={round}>Round {round}<small>2 turns</small></span>)}
                </div>)}
              </div>
              <p className="about-session-exploration-example">That's <strong>9 possible rounds, or 18 agent turns</strong>. You also choose a <strong>maximum number of turns for the whole session</strong>. With a 12-turn limit, SIGMA could run at most 6 complete rounds across the three strategies. Some strategies might stop early or never start.</p>
            </div>
            <div className="about-working-evidence">{card('workingEvidence', 'A growing research record', 'Ideas · challenges · calculations · open questions')}</div>
            <p className="about-multiple-strategies-note">Each selected strategy has its own sequence of attempts. All strategies draw from the same session-wide turn limit.</p>
            <p className="about-multiple-sessions-note">You can run another session later to revisit a strategy with new evidence or compare what changed.</p>
          </div>
        </div>
      </div>
      <div className="about-flow-connector"><span>Keep the ideas, tests, criticisms and unanswered questions</span><i aria-hidden="true"/></div>
      <div className="about-flow-evidence">{card('savedEvidence', 'Saved Evidence & Outcome', 'Findings, objections, experiments and unresolved questions')}</div>
      <div className="about-evidence-report-note">Review what worked, what failed, and what still needs proof. Export the research or write a report.</div>
      <div className="about-history-return"><span aria-hidden="true">↶</span> Findings may inform later sessions or researcher-approved strategy revisions.</div>
    </div>
    <p className="about-architecture-caption">SIGMA can try several approaches, challenge each attempt, and try again. It saves the reasoning and evidence instead of giving only a one-shot answer. An AI critique is not a mathematical proof.</p>
  </section>;
}
function FeedbackForm() {
  const [message, setMessage] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/cloud-auth/feedback', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, contact_email: contactEmail.trim() || null }),
      });
      if (!response.ok) throw await cloudFailure(response, 'Feedback could not be sent. Please try again.');
      setSent(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Feedback could not be sent. Please try again.');
    } finally { setBusy(false); }
  }
  return <details className="about-disclosure about-feedback-disclosure">
    <summary>Send product feedback</summary>
    <div className="about-disclosure-content">
      {sent ? <p role="status">Thanks for your feedback. It has been sent for administrator review.</p> : <form className="about-feedback-form" onSubmit={event => void submit(event)}>
        <label>Feedback<textarea required minLength={10} maxLength={4000} rows={4} value={message} onChange={event => setMessage(event.target.value)} placeholder="Share a suggestion or describe a problem."/></label>
        <button type="submit" className="admin-text-action about-feedback-send" disabled={busy || message.trim().length < 10}>{busy ? 'Sending…' : 'Send Feedback'}</button>
        <label>Contact email <span>(optional)</span><input type="email" maxLength={254} autoComplete="email" value={contactEmail} onChange={event => setContactEmail(event.target.value)} placeholder="you@example.org"/></label>
        <p>Your feedback is stored for SIGMA administrator review and is not sent to an AI provider. Read the <a href={privacyNoticeHref('about')}>Privacy Notice</a>.</p>
        {error && <p role="alert">{error}</p>}
      </form>}
    </div>
  </details>;
}

function privacyNoticeHref(returnDialog: 'invitation' | 'about') {
  const returnTo = `${window.location.pathname}${window.location.search}`;
  return `/privacy?return_to=${encodeURIComponent(returnTo)}&return_dialog=${returnDialog}`;
}

function AboutDialog({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const cloud = useCloudIdentity();
  useEffect(() => {
    dialog.current?.showModal();
    closeButton.current?.focus();
  }, []);
  return <div className="home-page about-dialog-style-scope"><dialog ref={dialog} className="project-entry-dialog about-dialog" aria-labelledby="about-heading" onCancel={event => { event.preventDefault(); onClose(); }} onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="entry-dialog-header"><h2 id="about-heading">About SIGMA</h2><button ref={closeButton} type="button" className="entry-cancel" onClick={onClose}>Close</button></div>
    <div className="about-dialog-content">
      <p className="about-intro"><strong>SIGMA is a research workbench for exploring answers to hard questions from different angles.</strong></p>
      <details className="about-disclosure">
        <summary>Key Features</summary>
        <div className="about-disclosure-content">
      <section className="about-feature"><h4>Multi-Strategy Exploration</h4><p>Hard problems often need more than one approach. Each strategy explores a particular angle, rather than proposing an answer. Strategies can be tested, revised, or combined as the research develops. Even failed approaches can teach us something useful.</p></section>
      <section className="about-feature"><h4>Multiple Research Agents</h4><p>Different agents investigate ideas, challenge assumptions, and look for weaknesses in the reasoning.</p></section>
      <section className="about-feature"><h4>Research History</h4><p>SIGMA keeps a record of strategies, research sessions, experiments, and findings so earlier work isn't lost. Failed approaches remain available for review and further investigation.</p></section>
      <section className="about-feature"><h4>Research That Builds on Earlier Work</h4><p>Researchers can use earlier findings to guide later investigations, including findings that ruled out an approach. SIGMA does not automatically combine discoveries across strategies.</p></section>
      <section className="about-feature"><h4>Human Guidance</h4><p>Researchers can provide feedback, revise strategies, and choose which directions to pursue.</p></section>
      <section className="about-feature"><h4>Python and SageMath Execution</h4><p>Agents can write and run Python code to test ideas, perform calculations, and check results. The code and execution output are saved with the research session. SageMath execution has not yet been independently verified.</p></section>
      <section className="about-feature"><h4>Evidence and Uncertainty</h4><p>Outcomes distinguish supported findings from unresolved questions and claims that still need verification. SIGMA records evidence and review status; it does not independently verify mathematical proofs.</p></section>
      <section className="about-feature"><h4>Readable Mathematical Text</h4><p>AI can reformat plain-text project descriptions and saved Conclusions as Markdown with typeset equations. The saved text remains available; formatted mathematics still needs review.</p></section>
      <section className="about-feature"><h4>Reports and Exports</h4><p>Research records and reports can be exported for review, sharing, and further work.</p></section>
          <section className="about-feature"><h4>Experimental LaTeX Paper Generation</h4><p>SIGMA can generate a draft mathematical paper in LaTeX format with equations, arguments, and supporting evidence. This feature is experimental; the draft needs human review and may contain errors.</p></section>
        </div>
      </details>
      <details className="about-disclosure about-architecture-disclosure">
        <summary>How SIGMA Works: Multi-Agentic Research</summary>
        <div id="about-architecture-details" className="about-disclosure-content"><AboutArchitecture/></div>
      </details>
      <details className="about-disclosure about-provenance-disclosure">
        <summary>Vision for Investigation Provenance</summary>
        <div id="about-provenance-details" className="about-disclosure-content"><AboutProvenanceVision/></div>
      </details>
      {cloud?.enabled && cloud.ready && <FeedbackForm/>}
    </div>
    <footer className="about-dialog-footer"><nav className="about-legal-links" aria-label="Legal information"><a className="about-privacy-link" href={privacyNoticeHref('about')}>Privacy Notice</a><a className="about-privacy-link" href="/tos">Terms of Service</a></nav><small className="about-build-commit">Version <code>{__SIGMA_VERSION__}</code> · Build <code>{__SIGMA_BUILD_COMMIT__}</code></small></footer>
  </dialog></div>;
}

function Header({ goHome, close, projectTitle, projectType, projectDifficulty, projectView, onProjectUpdated, projectActions, projectArtwork = false, connectionDisabled = false, researchRunning = false }: { goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean }; projectTitle?: string; projectType?: ResearchMode; projectDifficulty?: ProjectDifficulty | null; projectView?: ProjectView; onProjectUpdated?: (view: ProjectView) => void; projectActions?: React.ReactNode; projectArtwork?: boolean; connectionDisabled?: boolean; researchRunning?: boolean }) {
  const cloud = useCloudIdentity();
  const showConnectionStatus = !cloud?.enabled || (cloud.authenticated && cloud.user?.role !== 'guest');
  return <header className={projectArtwork ? 'site-header project-art-header' : 'site-header'}>
    <div className="brand-block">
      <a href="/" className={projectArtwork ? 'brand project-header-art' : 'brand'} onClick={goHome} aria-label="Go back to home page" data-tooltip="Go back to home page" data-tooltip-follow-cursor="true"><img src={projectArtwork ? '/sigma-project-header.png' : '/sigma-workspace-logo.png'} alt="SIGMA" /></a>
      {projectArtwork ? close && <div className="project-title-line">{projectTitle && <><div className="project-header-title-row">{projectType && <ResearchTypeIcon type={projectType}/>}{researchRunning
        ? <button type="button" className="project-header-title project-header-title-action" aria-label={`Scroll to running session in ${projectTitle}`} title="Scroll to running session" data-tooltip="Scroll to running session" onClick={() => window.dispatchEvent(new Event('sigma-reveal-running-session'))}>{projectTitle}<span className="research-running-indicator" aria-hidden="true"/></button>
        : <span className="project-header-title" title={projectTitle}>{projectTitle}</span>}</div>{projectActions}</>}</div>
        : <p className="expansion">Strategy Investigation, Generation, Measurement &amp; Assessment</p>}
    </div>
    <div className="header-controls">
    {!close && <span className="local">● Local workspace</span>}
    {close && projectView && onProjectUpdated ? <>
      <ProjectHeaderControls view={projectView} onSaved={onProjectUpdated} disabled={connectionDisabled || close.busy}/>
      <MockAuthSelector/><div className="identity-pill-stack project-identity-pill-stack"><GoogleIdentityPill/>{showConnectionStatus && <ConnectionStatus projectHeader cloudFunding={cloudFundingFor(cloud)} zeroAllowanceAction={<ReloadMeAction connectionPill/>}/>}</div>
    </> : showConnectionStatus && <ConnectionStatus cloudFunding={cloudFundingFor(cloud)} zeroAllowanceAction={<ReloadMeAction connectionPill/>}/>}
    <button type="button" className="about-action" aria-label="About SIGMA" title="About SIGMA" data-tooltip="About SIGMA" onClick={() => window.dispatchEvent(new Event('sigma-open-about'))}>About SIGMA</button>
    </div>
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

function WorkspaceFrame({ children, goHome, close, projectTitle, projectType, projectView, onProjectUpdated, projectActions, connectionDisabled = false, researchRunning = false }: {
  children: React.ReactNode; goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean }; projectTitle?: string; projectType?: ResearchMode; projectView?: ProjectView; onProjectUpdated?: (view: ProjectView) => void; projectActions?: React.ReactNode; connectionDisabled?: boolean; researchRunning?: boolean;
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
    <Header goHome={goHome} close={close} projectTitle={projectTitle} projectType={projectType} projectView={projectView} onProjectUpdated={onProjectUpdated} projectActions={projectActions} projectArtwork connectionDisabled={connectionDisabled} researchRunning={researchRunning}/>
    <div className={`workspace-layout${!ENABLE_WORKSPACE_SIDEBAR ? ' sidebar-disabled' : collapsed ? ' nav-collapsed' : ''}`}>
      {ENABLE_WORKSPACE_SIDEBAR && <nav className="workspace-nav" aria-label="Project navigation">
        <button className="nav-collapse" type="button" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} data-tooltip={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} onClick={toggleSidebar}><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={collapsed ? 'm9 6 6 6-6 6' : 'm15 6-6 6 6 6'}/></svg></button>
        <a href="#project-pane-heading" aria-label="Project" title={collapsed ? 'Project' : undefined} onClick={event => { event.preventDefault(); focusWorkspace('project-pane-heading'); }}><WorkspaceIcon name="Settings"/><span>Project</span></a>
        <a href="#sessions-heading" aria-label="Sessions" title={collapsed ? 'Sessions' : undefined} onClick={event => { event.preventDefault(); focusWorkspace('sessions-heading'); }}><WorkspaceIcon name="Analysis"/><span>Sessions</span></a>
        <a href="#pool-heading" aria-current="page" aria-label="Strategies" title={collapsed ? 'Strategies' : undefined} onClick={event => {
          event.preventDefault(); focusWorkspace('pool-heading');
        }}><WorkspaceIcon name="Strategies"/><span>Strategies</span></a>
        {['Renders', 'Analysis', 'References', 'Notes', 'Settings'].map(name =>
          <button key={name} disabled title={collapsed ? `${name} · later` : 'Not available yet'} aria-label={name} aria-describedby="workspace-nav-help">
            <WorkspaceIcon name={name}/><span>{name}</span><small>Later</small>
          </button>)}
        <p id="workspace-nav-help">Other destinations are not available yet.</p>
      </nav>}
      <div id="workspace-content" className="workspace-content" tabIndex={-1}>{children}</div>
    </div>
  </>;
}

type Destination = { root: string; path: string | null; exists: boolean };

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
      if (!response.ok) throw new Error(result.error ?? result.detail ?? 'Project import failed');
      onOpen(result as ProjectView);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }
  return <dialog ref={dialog} className="project-entry-dialog import-project-dialog" aria-labelledby="import-project-heading" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <header className="entry-dialog-header"><h2 id="import-project-heading">Import Project</h2><button type="button" className="entry-cancel" disabled={busy} onClick={onCancel}>Cancel</button></header>
    <p className="entry-help">Import a complete SIGMA JSON project bundle. Existing projects are never replaced.</p>
    <form id="import-project-form" onSubmit={submit}><fieldset disabled={busy}><div className="import-project-label-row"><label htmlFor="import-project-file">Project file</label><button className="choose-project-file" type="button" onClick={() => fileInput.current?.click()}>Choose</button></div>
      <input ref={fileInput} className="sr-only" id="import-project-file" type="file" accept=".json,application/json" required onChange={event => setFile(event.target.files?.[0] ?? null)}/>
      <div className="import-project-file-row"><div className="import-project-selected-file" aria-live="polite">{file?.name ?? 'No file chosen'}</div></div>
      {error && <p className="error" role="alert">{error}</p>}
    </fieldset></form>
    <footer className="import-project-footer"><button type="submit" form="import-project-form" className="entry-import" disabled={!file || busy}>{busy ? 'Importing…' : 'Import'}</button></footer>
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
    try { onOpen(await post<ProjectView>('open', { path })); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className="project-entry-dialog" aria-labelledby="project-entry-heading" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <header className="entry-dialog-header"><h2 id="project-entry-heading">Open Project</h2><button type="button" className="entry-cancel" disabled={busy} onClick={onCancel}>Cancel</button></header><p className="entry-help">Choose an existing local project by its directory path.</p>
    <form onSubmit={save}><fieldset disabled={busy}><label htmlFor="open-project-path">Project directory</label><div className="open-project-path-row"><input ref={first} id="open-project-path" required value={path} onChange={event => setPath(event.target.value)} aria-describedby="project-path-help"/><button className="open-project-submit" type="submit">{busy ? 'Opening…' : 'Open'}</button></div><p id="project-path-help" className="entry-hint">Try <code>projects/rh.sigma</code>, or an absolute path such as <code>/Users/you/projects/question.sigma</code>. Paths refer to this local server.</p>
    {error && <p className="error" role="alert">{error}</p>}</fieldset></form>
  </dialog>;
}

type Settings = { title: string; problem: string; investigation_type: ResearchMode; ai_model: string; reasoning_effort: string; difficulty: ProjectDifficulty | null; show_advanced_outcome_details: boolean };
type CatalogChoice = { id: string; label: string; description: string; efforts: string[]; relative_cost: '$' | '$$' | '$$$'; availability: 'available' | 'unavailable' | 'unverified' };
// Keep preference controls usable when account access cannot be checked.
const reviewedModelPreferences: CatalogChoice[] = [
  { id: 'gpt-6.1-sol', label: 'Sol · Balanced ($$)', description: 'Balance research capability and cost.', efforts: ['low', 'medium', 'high', 'xhigh'], relative_cost: '$$', availability: 'unverified' },
  { id: 'gpt-6-luna', label: 'Luna · Economy ($)', description: 'Lower-cost exploration of focused questions.', efforts: ['low', 'medium', 'high', 'xhigh'], relative_cost: '$', availability: 'unverified' },
  { id: 'gpt-6-astra', label: 'Astra · Advanced ($$$)', description: 'For the most demanding research reasoning; higher cost.', efforts: ['low', 'medium', 'high', 'xhigh'], relative_cost: '$$$', availability: 'unverified' },
];
const thinkingLabels: Record<string, string> = { low: 'Low', medium: 'Medium', high: 'High', xhigh: 'Extra high' };
const settingsOf = (view: ProjectView): Settings => ({ title: view.project.title, problem: view.project.problem, investigation_type: view.project.investigation_type, ai_model: view.project.ai_model, reasoning_effort: view.project.reasoning_effort, difficulty: view.project.difficulty, show_advanced_outcome_details: view.project.show_advanced_outcome_details });

function ProjectHeaderControls({ view, onSaved, disabled }: { view: ProjectView; onSaved: (view: ProjectView) => void; disabled: boolean }) {
  const ai = useAI();
  const cloud = useCloudIdentity();
  const [models, setModels] = useState<CatalogChoice[]>([]);
  const [catalogReady, setCatalogReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [pendingModel, setPendingModel] = useState<CatalogChoice | null>(null);
  const [confirmationPosition, setConfirmationPosition] = useState<{ left: number; top: number } | null>(null);
  const saving = useRef(false);
  const modelButton = useRef<HTMLButtonElement>(null);
  const confirmButton = useRef<HTMLButtonElement>(null);
  const confirmationPopover = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (pendingModel) {
      const place = () => {
        const anchor = modelButton.current?.getBoundingClientRect();
        const popover = confirmationPopover.current?.getBoundingClientRect();
        if (!anchor) return;
        const width = popover?.width ?? Math.min(320, window.innerWidth - 16);
        const height = popover?.height ?? 110;
        const left = Math.max(8, Math.min(anchor.left, window.innerWidth - width - 8));
        const below = anchor.bottom + height + 8 <= window.innerHeight - 8;
        setConfirmationPosition({ left, top: below ? anchor.bottom + 8 : Math.max(8, anchor.top - height - 8) });
      };
      const frame = requestAnimationFrame(() => {
        place();
        confirmButton.current?.focus();
      });
      const escape = (event: KeyboardEvent) => {
        if (event.key === 'Escape') {
          event.preventDefault();
          setPendingModel(null);
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
    } else {
      setConfirmationPosition(null);
      modelButton.current?.focus();
    }
  }, [pendingModel]);

  useEffect(() => {
    const controller = new AbortController();
    setCatalogReady(false);
    if (cloud?.enabled && !cloud.authenticated) {
      setModels(reviewedModelPreferences); setMessage('Model access is checked when connected.'); setCatalogReady(true);
      return () => controller.abort();
    }
    fetch('/api/ai/models', { signal: controller.signal }).then(async response => {
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          if (!controller.signal.aborted) { setModels([]); setMessage('Model availability requires an authorized session. Saved settings are unchanged.'); }
          return null;
        }
        throw new Error(`Model availability check failed (HTTP ${response.status}). Retry after connectivity is restored. Saved settings are unchanged.`);
      }
      return response.json();
    }).then(data => {
      if (!controller.signal.aborted && data) setModels(Array.isArray(data.models) ? data.models : []);
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) {
        setModels(reviewedModelPreferences);
        setMessage(error instanceof Error ? `${error.message} Preferences remain configurable; access is checked when connected.` : 'Model availability could not be verified. Preferences remain configurable; access is checked when connected.');
      }
    }).finally(() => { if (!controller.signal.aborted) setCatalogReady(true); });
    return () => controller.abort();
  }, [ai.info?.mode, ai.info?.active_account, ai.info?.status, cloud?.enabled, cloud?.authenticated]);

  const current = models.find(model => model.id === view.project.ai_model);
  const costOrder: Record<CatalogChoice['relative_cost'], number> = { '$': 1, '$$': 2, '$$$': 3 };
  const selectableModels = models.filter(model => model.availability !== 'unavailable').sort((a, b) => costOrder[b.relative_cost] - costOrder[a.relative_cost] || a.label.localeCompare(b.label));
  const currentSelectableIndex = selectableModels.findIndex(model => model.id === view.project.ai_model);
  const nextModel = selectableModels.length > 1
    ? selectableModels[(currentSelectableIndex + 1 + selectableModels.length) % selectableModels.length]
    : selectableModels.length === 1 && currentSelectableIndex < 0 ? selectableModels[0] : undefined;
  const efforts = current && current.availability !== 'unavailable' ? current.efforts : [];
  const currentEffortIndex = efforts.indexOf(view.project.reasoning_effort);
  const nextEffort = efforts.length > 1
    ? efforts[(currentEffortIndex + 1 + efforts.length) % efforts.length]
    : undefined;
  const effortOrder = ['low', 'medium', 'high', 'xhigh'];
  const reconciledEffort = (model: CatalogChoice | undefined) => {
    if (!model?.efforts.length) return undefined;
    if (model.efforts.includes(view.project.reasoning_effort)) return view.project.reasoning_effort;
    const oldIndex = effortOrder.indexOf(view.project.reasoning_effort);
    return [...model.efforts].sort((a, b) => {
      const distance = Math.abs(effortOrder.indexOf(a) - oldIndex) - Math.abs(effortOrder.indexOf(b) - oldIndex);
      return distance || effortOrder.indexOf(a) - effortOrder.indexOf(b);
    })[0];
  };
  const nextModelEffort = reconciledEffort(nextModel);
  const effortWillChange = Boolean(nextModel && nextModelEffort !== view.project.reasoning_effort);
  const nextModelCostsMore = Boolean(current && nextModel && costOrder[nextModel.relative_cost] > costOrder[current.relative_cost]);
  const difficultyOrder: ProjectDifficulty[] = ['easy', 'medium', 'hard'];
  const currentDifficultyIndex = view.project.difficulty ? difficultyOrder.indexOf(view.project.difficulty) : -1;
  const nextDifficulty = difficultyOrder[(currentDifficultyIndex + 1) % difficultyOrder.length];
  const difficultyText = view.project.difficulty ? difficultyLabels[view.project.difficulty].toLowerCase() : 'not set';
  const costHelpId = `project-model-cost-help-${view.project.id}`;

  async function update(changes: Partial<Settings>) {
    if (saving.current || disabled || busy) return;
    saving.current = true; setBusy(true); setMessage('');
    const expected = settingsOf(view);
    try {
      const saved = await post<ProjectView>('update', {
        path: view.path, ...expected, ...changes, expected,
      });
      onSaved(saved);
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      saving.current = false; setBusy(false);
    }
  }

  const modelLabel = current ? `${current.label.split(' · ')[0]} ${current.relative_cost}` : view.project.ai_model;
  const modelDisabled = !catalogReady || busy || disabled || !nextModel || !nextModelEffort;
  const thinkingDisabled = !catalogReady || busy || disabled || !nextEffort;
  const statusMessage = message || !catalogReady ? message || 'Checking model availability…' : '';
  const nextEffortNotice = effortWillChange
    ? ` Switching to ${nextModel?.label.split(' · ')[0]} will also change Thinking from ${thinkingLabels[view.project.reasoning_effort] ?? view.project.reasoning_effort} to ${thinkingLabels[nextModelEffort!]}.`
    : '';
  const visibleEffortNotice = effortWillChange ? `Next model uses ${thinkingLabels[nextModelEffort!]}.` : '';
  const pendingModelName = pendingModel?.label.split(' · ')[0] ?? 'this model';
  function requestModelChange() {
    if (!nextModel || !nextModelEffort) return;
    if (nextModelCostsMore) setPendingModel(nextModel);
    else void update({ ai_model: nextModel.id, reasoning_effort: nextModelEffort });
  }
  function confirmModelChange() {
    if (!pendingModel) return;
    const confirmed = pendingModel;
    setPendingModel(null);
    const effort = reconciledEffort(confirmed);
    if (effort) void update({ ai_model: confirmed.id, reasoning_effort: effort });
  }
  function cycleDifficulty() {
    void update({ difficulty: nextDifficulty });
  }
  return <div className="project-header-controls" aria-label="Project model, thinking, and difficulty controls">
    <button type="button" className={`project-control-pill project-difficulty-badge difficulty-${view.project.difficulty ?? 'unset'}`} aria-label={`Project difficulty ${view.project.difficulty ? difficultyLabels[view.project.difficulty] : 'not set'}`} title={`This project is considered ${difficultyText}. Click to cycle through easy, medium, and hard.`} data-tooltip={`This project is considered ${difficultyText}. Click to cycle through easy, medium, and hard.`} disabled={disabled || busy || !!pendingModel} onClick={cycleDifficulty}>Difficulty · {view.project.difficulty ? difficultyLabels[view.project.difficulty] : 'Not set'}</button>
    <button ref={modelButton} type="button" className="project-control-pill project-model-pill" aria-label={`Model ${modelLabel}. Relative published API token cost ${current?.relative_cost ?? 'unknown'}.${nextEffortNotice}`} aria-describedby={costHelpId} title={`The selected model is ${modelLabel}. Its relative published API token cost is ${current?.relative_cost ?? 'unknown'}. Availability is checked when connected. Click to cycle through reviewed model options.${nextEffortNotice}`} data-tooltip={`The selected model is ${modelLabel}. Its relative published API token cost is ${current?.relative_cost ?? 'unknown'}. Availability is checked when connected. Click to cycle through reviewed model options.${nextEffortNotice}`} disabled={modelDisabled || !!pendingModel} onClick={requestModelChange}>Model · {modelLabel}</button>
    <button type="button" className="project-control-pill project-thinking-pill" aria-label={`Thinking level ${thinkingLabels[view.project.reasoning_effort] ?? view.project.reasoning_effort}`} title={`The thinking level is set to ${(thinkingLabels[view.project.reasoning_effort] ?? view.project.reasoning_effort).toLowerCase()}. Click to cycle through levels supported by this model.`} data-tooltip={`The thinking level is set to ${(thinkingLabels[view.project.reasoning_effort] ?? view.project.reasoning_effort).toLowerCase()}. Click to cycle through levels supported by this model.`} disabled={thinkingDisabled || !!pendingModel} onClick={() => nextEffort && void update({ ai_model: view.project.ai_model, reasoning_effort: nextEffort })}>Thinking · {thinkingLabels[view.project.reasoning_effort] ?? view.project.reasoning_effort}</button>
    <span id={costHelpId} className="sr-only">Dollar signs show relative published API token price tiers. They are not actual research session charges.</span>
    {visibleEffortNotice && <span className="project-controls-message" role="status">{visibleEffortNotice}</span>}
    {statusMessage && <span className="project-controls-message" role="status">{statusMessage}</span>}
    {pendingModel && createPortal(<div ref={confirmationPopover} className="project-model-confirm-popover" role="group" aria-label={`Confirm switch to ${pendingModelName}`} style={confirmationPosition ? { left: confirmationPosition.left, top: confirmationPosition.top } : { left: -10000, top: -10000 }}>
      <p><strong>Switch to {pendingModelName}?</strong> {pendingModelName} has a higher relative published API token cost tier ({pendingModel.relative_cost} versus {current?.relative_cost}). Continue to save this model?</p>
      <div className="project-model-confirm-actions"><button ref={confirmButton} type="button" className="text-view-link" onClick={confirmModelChange}>Confirm</button><button type="button" className="text-view-link" onClick={() => setPendingModel(null)}>Cancel</button></div>
    </div>, document.body)}
  </div>;
}

function ResearchTypeIcon({ type }: { type: ResearchMode }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  return <svg className={`research-type-icon research-type-icon-${type}`} viewBox="0 0 24 24" aria-hidden="true">
    {type === 'mathematical' ? <text x="12" y="18" textAnchor="middle" fill="currentColor" fontFamily="Georgia,serif" fontSize="21">Σ</text>
      : type === 'religion' ? <path {...common} d="M12 3v18M7 8h10M9 21h6M12 3 9.5 6M12 3l2.5 3"/>
        : type === 'law' ? <path {...common} d="M12 4v15M7 20h10M5 7h14M12 7 7 15m0 0H3l2-4 2 4Zm5-8 5 8m0 0h-4l2-4 2 4Z"/>
          : type === 'chemistry' ? <path {...common} d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3M7 16h10M9 13h6"/>
            : type === 'biology' ? <g {...common}>
              <path d="M5 2C5 7 19 7 19 12s-14 5-14 10"/>
              <path d="M19 2c0 5-14 5-14 10s14 5 14 10"/>
              <path d="M7 4.5h10M6 12h12M7 19.5h10"/>
            </g>
              : type === 'computer_science' ? <path {...common} d="m8 7-5 5 5 5m8-10 5 5-5 5m-1-14-6 18"/>
                : type === 'economics' ? <text x="12" y="19" textAnchor="middle" fill="currentColor" fontFamily="Georgia,serif" fontSize="20">$</text>
                  : type === 'engineering' ? <><circle {...common} cx="12" cy="12" r="6.7"/><circle {...common} cx="12" cy="12" r="3.1"/><path {...common} d="M12 1.8v3.5m0 13.4v3.5M1.8 12h3.5m13.4 0h3.5M4.8 4.8l2.5 2.5m9.4 9.4 2.5 2.5m0-14.4-2.5 2.5m-9.4 9.4-2.5 2.5"/></>
            : type === 'physics' ? <><ellipse {...common} cx="12" cy="12" rx="9" ry="3.8"/><ellipse {...common} cx="12" cy="12" rx="9" ry="3.8" transform="rotate(60 12 12)"/><ellipse {...common} cx="12" cy="12" rx="9" ry="3.8" transform="rotate(120 12 12)"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></>
              : type === 'military' ? <><path {...common} d="M12 3 20 6v5c0 5-3.3 8-8 10-4.7-2-8-5-8-10V6l8-3Z"/><path {...common} d="m8 13 4-4 4 4M12 9v6"/></>
                : type === 'philosophy' ? <><path {...common} d="M4 6c3-1 5 0 8 2 3-2 5-3 8-2v12c-3-1-5 0-8 2-3-2-5-3-8-2V6Z"/><path {...common} d="M12 8v12M8 10h1M15 10h1"/></>
                  : <><circle {...common} cx="12" cy="12" r="8.5"/><circle cx="7" cy="8" r="1.5" fill="currentColor"/><circle cx="16.5" cy="7" r="1.5" fill="currentColor"/><circle cx="9" cy="16.5" r="1.5" fill="currentColor"/><path {...common} d="m8.5 9 6.5-1m-6 7 1-5m1 6 4-7"/></>}
  </svg>;
}

function ResearchTypePicker({ value, onChange, fieldLabel = 'Research type' }: { value: ResearchMode; onChange: (value: ResearchMode) => void; fieldLabel?: string }) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(Math.max(0, researchTypes.findIndex(type => type.value === value)));
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const options = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedIndex = Math.max(0, researchTypes.findIndex(type => type.value === value));
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
    setActiveIndex((index + researchTypes.length) % researchTypes.length);
  }
  const selected = researchTypes[selectedIndex];
  return <div className="research-type-picker" ref={root}>
    <button ref={trigger} id="project-mode" type="button" role="combobox" aria-labelledby="project-mode-label project-mode-value" aria-haspopup="listbox" aria-expanded={open} aria-controls="project-mode-options" onClick={() => { setActiveIndex(selectedIndex); setOpen(current => !current); }} onKeyDown={event => {
      if (event.key === 'ArrowDown') { event.preventDefault(); setActiveIndex(selectedIndex); setOpen(true); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); setActiveIndex(researchTypes.length - 1); setOpen(true); }
    }}>
      <ResearchTypeIcon type={selected.value}/><span id="project-mode-value">{selected.label}</span><svg className="research-type-chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="m2 4 4 4 4-4"/></svg>
    </button>
    {open && <div className="research-type-options" id="project-mode-options" role="listbox" aria-label={fieldLabel}>
      {researchTypes.map((type, index) => <button ref={element => { options.current[index] = element; }} id={`project-mode-option-${type.value}`} key={type.value} type="button" role="option" aria-selected={value === type.value} tabIndex={activeIndex === index ? 0 : -1} onFocus={() => setActiveIndex(index)} onClick={() => choose(type.value)} onKeyDown={event => {
        if (event.key === 'ArrowDown') { event.preventDefault(); move(index + 1); }
        else if (event.key === 'ArrowUp') { event.preventDefault(); move(index - 1); }
        else if (event.key === 'Home') { event.preventDefault(); move(0); }
        else if (event.key === 'End') { event.preventDefault(); move(researchTypes.length - 1); }
        else if (event.key === 'Escape') { event.preventDefault(); setOpen(false); trigger.current?.focus(); }
        else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(type.value); }
      }}><ResearchTypeIcon type={type.value}/><span>{type.label}</span></button>)}
    </div>}
  </div>;
}

function ProjectSettingsDialog({ initial, onSaved, onCancel }: { initial?: ProjectView; onSaved: (view: ProjectView) => void; onCancel: () => void }) {
  useDocumentScrollLock();
  const ai = useAI();
  const cloud = useCloudIdentity();
  const dialog = useRef<HTMLDialogElement>(null);
  const first = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const [values, setValues] = useState<Settings>(() => initial ? settingsOf(initial) : savedNewProjectValues() ?? { title: '', problem: '', investigation_type: 'default', ai_model: '', reasoning_effort: 'high', difficulty: 'medium', show_advanced_outcome_details: false });
  const [catalog, setCatalog] = useState<CatalogChoice[]>([]);
  const [catalogMessage, setCatalogMessage] = useState('Checking model availability…');
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
  const [limitDraft, setLimitDraft] = useState<ResearchLimitsDraft>(() => draftLimits({ research_rounds: 2, model_calls: 12, session_duration_minutes: 30, output_tokens_per_call: 4000, maximum_estimated_cost_usd: null, maximum_input_tokens_per_session: null, max_concurrent_sessions: '1' }));
  const [limitsLoaded, setLimitsLoaded] = useState(!initial);
  const limitValidation = validateLimitDraft(
    limitDraft,
  );
  useEffect(() => { dialog.current?.showModal(); first.current?.focus(); }, []);
  useEffect(() => {
    if (!initial) return;
    const controller = new AbortController();
    fetch(`/api/projects/research-limits?${new URLSearchParams({ path: initial.path })}`, { signal: controller.signal }).then(async response => {
      const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Research limits could not be read');
      setLimitDraft(draftLimits(data)); setLimitsLoaded(true);
    }).catch(cause => { if (!controller.signal.aborted) setError(errorMessage(cause)); });
    return () => controller.abort();
  }, [initial?.path]);
  useEffect(() => {
    const controller = new AbortController();
    if (cloud?.enabled && !cloud.authenticated) {
      setCatalog([]); setCatalogMessage('Model availability is unavailable in Guest mode.');
      return () => controller.abort();
    }
    fetch('/api/ai/models', { signal: controller.signal }).then(async response => { if (!response.ok) throw new Error('Model catalog unavailable. Check the local server; existing settings are retained.'); return response.json(); }).then(data => {
      setCatalog(data.models); setCatalogMessage(data.message);
      if (!initial) setValues(previous => previous.ai_model ? previous : { ...previous, ai_model: data.default_model, reasoning_effort: data.default_effort });
    }).catch(error => { if (!controller.signal.aborted) setCatalogMessage(errorMessage(error)); });
    return () => controller.abort();
  }, [ai.info?.mode, ai.info?.active_account, cloud?.enabled, cloud?.authenticated]);
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
  const selected = catalog.find(model => model.id === values.ai_model);
  const costOrder: Record<CatalogChoice['relative_cost'], number> = { '$': 1, '$$': 2, '$$$': 3 };
  const orderedCatalog = [...catalog].sort((a, b) => costOrder[a.relative_cost] - costOrder[b.relative_cost] || a.label.localeCompare(b.label));
  const samePair = !!initial && values.ai_model === initial.project.ai_model && values.reasoning_effort === initial.project.reasoning_effort;
  const compatible = selected?.efforts.includes(values.reasoning_effort) || samePair;
  const pairError = selected && !selected.efforts.includes(values.reasoning_effort) && !samePair ? 'This model does not support the selected Thinking level. Choose a supported level explicitly.' : '';
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current || !compatible || (initial && !limitValidation.value) || (!initial && (!destination?.path || destination.exists || previewBusy))) return;
    submitting.current = true; setBusy(true); setError('');
    try {
      const createValues = {
        title: values.title,
        problem: values.problem,
        investigation_type: values.investigation_type,
        ai_model: values.ai_model,
        reasoning_effort: values.reasoning_effort,
        difficulty: values.difficulty,
        show_advanced_outcome_details: values.show_advanced_outcome_details,
      };
      const next = await post<ProjectView>(initial ? 'update' : 'create', initial ? { path: initial.path, ...values, expected: settingsOf(initial) } : createValues);
      if (!initial) {
        try { window.localStorage.setItem(NEW_PROJECT_VALUES_KEY, JSON.stringify(values)); } catch { /* Project creation must not depend on browser storage availability. */ }
      }
      if (initial) {
        const response = await fetch('/api/projects/research-limits', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: initial.path, ...limitValidation.value }) });
        const result = await response.json(); if (!response.ok) throw new Error(result.error ?? 'Research limits were not saved');
        setLimitDraft(draftLimits(result));
      }
      onSaved(next);
    }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className={`project-settings-dialog ${initial ? 'edit-project-dialog' : 'new-project-dialog'}`} aria-labelledby="project-settings-heading" aria-describedby="project-settings-help" onCancel={event => { event.preventDefault(); if (!submitting.current) onCancel(); }}>
    <form onSubmit={save}>
      <header className="settings-header"><h2 id="project-settings-heading">{initial ? 'Project Settings' : 'New Project'}</h2><div className="settings-actions">{initial ? <><button type="submit" disabled={busy || !values.ai_model || !compatible || !!pairError || !limitsLoaded || !limitValidation.value}>{busy ? 'Saving…' : 'Save'}</button><button className="settings-cancel" type="button" disabled={busy} onClick={() => { if (!submitting.current) onCancel(); }}>Cancel</button></> : <><button type="submit" disabled={busy || !values.ai_model || !compatible || !!pairError || !values.problem.trim() || previewBusy || !destination?.path || destination.exists}>{busy ? 'Creating…' : 'Create'}</button><button className="settings-cancel" type="button" disabled={busy} onClick={() => { if (!submitting.current) onCancel(); }}>Cancel</button></>}</div></header>
      {initial && <div role="tablist" aria-label="Project settings" className="settings-tabs" onKeyDown={event => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) { event.preventDefault(); const tabs = ['main', 'limits', 'preferences'] as const; const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs[2] : tabs[(tabs.indexOf(activeTab) + (event.key === 'ArrowRight' ? 1 : 2)) % 3]; changeSettingsTab(next); dialog.current?.querySelector<HTMLButtonElement>(`[data-settings-tab="${next}"]`)?.focus(); } }}>
        <button type="button" role="tab" data-settings-tab="main" id="settings-tab-main" aria-selected={activeTab === 'main'} aria-controls="settings-panel-main" tabIndex={activeTab === 'main' ? 0 : -1} onClick={() => changeSettingsTab('main')}>Research</button>
        <button type="button" role="tab" data-settings-tab="limits" id="settings-tab-limits" aria-selected={activeTab === 'limits'} aria-controls="settings-panel-limits" tabIndex={activeTab === 'limits' ? 0 : -1} onClick={() => changeSettingsTab('limits')}>Limits</button>
        <button type="button" role="tab" data-settings-tab="preferences" id="settings-tab-preferences" aria-selected={activeTab === 'preferences'} aria-controls="settings-panel-preferences" tabIndex={activeTab === 'preferences' ? 0 : -1} onClick={() => changeSettingsTab('preferences')}>Preferences</button>
      </div>}
      <div className="settings-body" id={initial ? 'settings-panel-main' : undefined} role={initial ? 'tabpanel' : undefined} aria-labelledby={initial ? 'settings-tab-main' : undefined} hidden={!!initial && activeTab !== 'main'}><p id="project-settings-help">{initial ? 'Set this project’s research type and AI options.' : 'Name a project and choose its research category.'}</p>
      <fieldset disabled={busy}>
      {!initial && <><label htmlFor="project-name">Project name</label><input ref={first} id="project-name" required maxLength={200} value={values.title} onChange={event => change('title', event.target.value)}/>
      <label htmlFor="project-problem">Research problem</label><textarea id="project-problem" required maxLength={20000} rows={4} value={values.problem} onChange={event => change('problem', event.target.value)}/></>}
      <div className="settings-classification-row"><div><label id="project-mode-label">{initial ? 'Research type' : 'Research category'}</label><ResearchTypePicker fieldLabel={initial ? 'Research type' : 'Research category'} value={values.investigation_type} onChange={value => change('investigation_type', value)}/></div>
      <div><label htmlFor="project-difficulty">Difficulty</label><select id="project-difficulty" value={values.difficulty ?? ''} onChange={event => change('difficulty', (event.target.value || null) as ProjectDifficulty | null)}>{values.difficulty === null && <option value="">Not set</option>}<option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select></div></div>
      <div className="settings-model-row">
      <div><label htmlFor="project-model">Model</label><select id="project-model" required value={values.ai_model} onChange={event => change('ai_model', event.target.value)} aria-describedby="project-model-help">
        {!values.ai_model && <option value="" disabled>Loading reviewed choices…</option>}
        {values.ai_model && !selected && <option value={values.ai_model}>{values.ai_model} · unavailable/unreviewed</option>}
        {orderedCatalog.map(model => <option key={model.id} value={model.id}>{model.label.replace(/\s*\([^)]*\)$/, '').trim()} · {model.relative_cost}{model.availability === 'available' ? '' : model.availability === 'unavailable' ? ' · unavailable' : ' · access unverified'}</option>)}
      </select>
      <p id="project-model-help" className="settings-hint">{ai.info?.mode === 'api_key' ? 'OpenAI API · billed separately.' : 'ChatGPT plan or credits.'}{catalogMessage}{selected?.availability === 'unavailable' ? ' Model unavailable; it will not be replaced.' : ''}</p></div>
      <div><label htmlFor="project-thinking">Thinking level</label><select id="project-thinking" value={values.reasoning_effort} onChange={event => change('reasoning_effort', event.target.value)}>
        {!selected?.efforts.includes(values.reasoning_effort) && <option value={values.reasoning_effort}>{thinkingLabels[values.reasoning_effort] ?? values.reasoning_effort} · {selected ? 'unsupported' : 'preserved'}</option>}
        {(selected?.efforts ?? []).map(effort => <option key={effort} value={effort}>{thinkingLabels[effort] ?? effort}</option>)}
      </select>
      <p className="settings-hint">Used for future AI proposals. Higher levels use more time and usage.</p></div>
      </div>
      {pairError && <p className="error" role="alert">{pairError}</p>}
      <p className="project-destination"><span>Project location</span><code>{initial ? initial.path : previewBusy ? 'Checking location…' : destination?.path ?? destination?.root ?? 'Location unavailable'}</code><small>{initial ? 'Editing the display name never renames or moves this directory.' : 'The project name determines its directory; existing files are never overwritten.'}</small></p>
      {locationError && <p className="error" role="alert">{locationError}</p>}
      {destination?.exists && <p className="error" role="alert">That name is already used by another project, or the location is occupied. Choose another name.</p>}
      {error && <p className="error" role="alert">{error}</p>}
    </fieldset></div>
    {initial && <section id="settings-panel-limits" className="settings-body research-limits-panel" role="tabpanel" aria-labelledby="settings-tab-limits" hidden={activeTab !== 'limits'}>
      <p>Research limits apply to future sessions. For local strategy generation, the model-call limit also sets the call budget. Existing sessions keep the limits captured when they started.</p>
      {cloud?.target === 'hosted' && <p className="settings-hint">Hosted research may apply service-side caps to saved session limits.</p>}
      {cloud?.target === 'local' && <p className="settings-hint">Sponsored research is subject to the account allowance and service-side caps.</p>}
      <fieldset disabled={busy || !limitsLoaded}>
        <label htmlFor="research-concurrent-sessions">Maximum concurrent sessions</label><input id="research-concurrent-sessions" type="text" inputMode="numeric" value={limitDraft.max_concurrent_sessions} aria-invalid={!!limitValidation.errors.max_concurrent_sessions} aria-describedby="research-concurrent-sessions-help research-concurrent-sessions-error" onChange={event => setLimitDraft(value => ({ ...value, max_concurrent_sessions: event.target.value }))}/><p id="research-concurrent-sessions-help" className="settings-hint">Queued or running sessions allowed in this project. Any positive whole number; default is 1.</p>{limitValidation.errors.max_concurrent_sessions && <p id="research-concurrent-sessions-error" className="limit-error" role="alert">{limitValidation.errors.max_concurrent_sessions}</p>}
        <label htmlFor="research-rounds">Research rounds</label><input id="research-rounds" type="number" min={1} max={5} step={1} value={limitDraft.research_rounds} aria-invalid={!!limitValidation.errors.research_rounds} aria-describedby="research-rounds-help research-rounds-error" onChange={event => setLimitDraft(value => ({ ...value, research_rounds: event.target.value }))}/><p id="research-rounds-help" className="settings-hint">One round is one Investigator→Skeptic exchange per strategy. Strategies can stop early; 1–5 rounds is a ceiling, not a target.</p>{limitValidation.errors.research_rounds && <p id="research-rounds-error" className="limit-error" role="alert">{limitValidation.errors.research_rounds}</p>}
        <label htmlFor="research-calls">Maximum agent turns</label><input id="research-calls" type="number" min={2} max={120} step={1} value={limitDraft.model_calls} aria-invalid={!!limitValidation.errors.model_calls} aria-describedby="research-calls-help research-calls-error" onChange={event => setLimitDraft(value => ({ ...value, model_calls: event.target.value }))}/><p id="research-calls-help" className="settings-hint">Shared ceiling across all selected strategies. One turn is one Investigator or Skeptic provider call. Example: 5 strategies × 3 rounds × 2 turns = up to 30 turns. A 3-turn ceiling remains valid with 1, 3, or 5 strategies; SIGMA schedules complete pairs fairly and reports branches it could not serve. Local strategy generation also uses this ceiling.</p>{limitValidation.errors.model_calls && <p id="research-calls-error" className="limit-error" role="alert">{limitValidation.errors.model_calls}</p>}
        <label htmlFor="research-duration-value">Maximum session duration</label><div className="research-duration-controls"><input id="research-duration-value" type="number" min={1} max={Math.floor(MAX_SESSION_DURATION_MINUTES / durationUnitMinutes[limitDraft.session_duration_unit])} step={1} value={limitDraft.session_duration_value} aria-invalid={!!limitValidation.errors.session_duration_value} aria-describedby="research-duration-help research-duration-error" onChange={event => setLimitDraft(value => ({ ...value, session_duration_value: event.target.value }))}/><select id="research-duration-unit" aria-label="Maximum session duration unit" value={limitDraft.session_duration_unit} onChange={event => setLimitDraft(value => ({ ...value, session_duration_unit: event.target.value as DurationUnit }))}><option value="minutes">Minutes</option><option value="hours">Hours</option><option value="days">Days</option></select></div><p id="research-duration-help" className="settings-hint">Elapsed wall time from start, 1 minute to 7 days. Time spent stopped counts.</p>{limitValidation.errors.session_duration_value && <p id="research-duration-error" className="limit-error" role="alert">{limitValidation.errors.session_duration_value}</p>}
        <label htmlFor="research-output-tokens">Maximum output tokens per call</label><input id="research-output-tokens" type="number" min={256} max={20000} step={1} value={limitDraft.output_tokens_per_call} aria-invalid={!!limitValidation.errors.output_tokens_per_call} aria-describedby="research-output-help research-output-error" onChange={event => setLimitDraft(value => ({ ...value, output_tokens_per_call: event.target.value }))}/><p id="research-output-help" className="settings-hint">Higher limits allow longer answers but increase the worst-case spend reserve. Sponsored calls may be stopped if that reserve exceeds the session allowance.</p>{limitValidation.errors.output_tokens_per_call && <p id="research-output-error" className="limit-error" role="alert">{limitValidation.errors.output_tokens_per_call}</p>}
        <label htmlFor="research-input-tokens">Maximum input tokens per session</label><input id="research-input-tokens" type="number" min={4096} max={1000000} step={1} placeholder="Unlimited" value={limitDraft.maximum_input_tokens_per_session} aria-invalid={!!limitValidation.errors.maximum_input_tokens_per_session} aria-describedby="research-input-help research-input-error" onChange={event => setLimitDraft(value => ({ ...value, maximum_input_tokens_per_session: event.target.value }))}/><p id="research-input-help" className="settings-hint">Optional cumulative cap. Before dispatch, SIGMA reserves the exact serialized request byte count plus an 8,192-token structural allowance as an upper bound; afterward, reported input usage must fit within that reservation. Unknown or in-flight calls retain their full reservation.</p>{limitValidation.errors.maximum_input_tokens_per_session && <p id="research-input-error" className="limit-error" role="alert">{limitValidation.errors.maximum_input_tokens_per_session}</p>}
        <>
          <label htmlFor="research-cost-limit">Maximum estimated session cost (USD)</label>
          <input id="research-cost-limit" type="text" inputMode="decimal" placeholder="Unlimited" value={limitDraft.maximum_estimated_cost_usd} aria-invalid={!!limitValidation.errors.maximum_estimated_cost_usd} aria-describedby="research-cost-help research-cost-error" onChange={event => setLimitDraft(value => ({ ...value, maximum_estimated_cost_usd: event.target.value }))}/>
          <p id="research-cost-help" className="settings-hint">Optional per-session cap. Without one, sponsored sessions remain subject to ChatGPT and SIGMA allowance limits. Set $0.01 to $100.00, or leave blank for no session cap. Estimates use published prices and reported tokens.</p>
          {limitValidation.errors.maximum_estimated_cost_usd && <p id="research-cost-error" className="limit-error" role="alert">{limitValidation.errors.maximum_estimated_cost_usd}</p>}
        </>
      </fieldset>
      {!limitsLoaded && <p role="status">Loading saved research limits…</p>}{error && <p role="alert" className="error">{error} <button type="button" className="text-view-link" onClick={async () => { setError(''); try { const response = await fetch(`/api/projects/research-limits?${new URLSearchParams({ path: initial.path })}`); const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Research limits could not be read'); setLimitDraft(draftLimits(data)); setLimitsLoaded(true); } catch (cause) { setError(errorMessage(cause)); } }}>Retry</button></p>}
    </section>}
    {initial && <section id="settings-panel-preferences" className="settings-body project-preferences-panel" role="tabpanel" aria-labelledby="settings-tab-preferences" hidden={activeTab !== 'preferences'}>
      <p>Choose how research outcomes are presented for this project. This preference does not change saved sessions or their evidence.</p>
      <fieldset disabled={busy}>
        <label className="project-preference-checkbox" htmlFor="show-advanced-outcome-details"><input id="show-advanced-outcome-details" type="checkbox" checked={values.show_advanced_outcome_details} onChange={event => change('show_advanced_outcome_details', event.target.checked)}/>Show advanced Outcome details</label>
        <p className="settings-hint">When enabled, each saved outcome opens with its conclusion and provides expandable reasoning, evidence, metrics and session details. When disabled, SIGMA shows a concise result with its qualifications.</p>
      </fieldset>
      {error && <p role="alert" className="error">{error}</p>}
    </section>}
    </form>
  </dialog>;
}

type RecentProject = { id: string; path: string; title: string; investigation_type: string | null; strategy_count: number | null; difficulty: ProjectDifficulty | null; research_running: boolean; available: boolean; error: string | null };
type SampleProject = { id: string; title: string; problem: string; investigation_type: ResearchMode; difficulty: ProjectDifficulty | null; strategy_count: number };
const strategyCount = (count: number) => `${count} ${count === 1 ? 'strategy' : 'strategies'}`;
function RecentProjects({ onOpen }: { onOpen: (view: ProjectView) => void }) {
  const [projects, setProjects] = useState<RecentProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [opening, setOpening] = useState('');
  const [confirmRemoveId, setConfirmRemoveId] = useState('');
  const [confirmRemovePlacement, setConfirmRemovePlacement] = useState<'above' | 'below'>('below');
  const [error, setError] = useState('');
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const pending = useRef(false);
  const load = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch('/api/projects/recent', { signal });
    const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Recent Projects unavailable.');
    setProjects(data.projects); setError(''); setLoading(false);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let requestPending = false;
    const refresh = async () => {
      if (controller.signal.aborted || document.visibilityState !== 'visible' || requestPending) return;
      requestPending = true;
      try {
        await load(controller.signal);
        if (!controller.signal.aborted) setError('');
      } catch (error) {
        if (!controller.signal.aborted) {
          setProjects(current => current.map(entry => ({ ...entry, research_running: false })));
          setError(errorMessage(error));
          setLoading(false);
        }
      } finally {
        requestPending = false;
      }
    };
    const interval = window.setInterval(() => void refresh(), 2000);
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    void refresh();
    return () => {
      controller.abort();
      window.clearInterval(interval);
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, [load]);
  async function open(entry: RecentProject) {
    if (pending.current) return; pending.current = true; setOpening(entry.id); setError('');
    try { onOpen(await post<ProjectView>('open', { path: entry.path })); }
    catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setOpening(''); }
  }
  async function forget(entry: RecentProject) {
    if (pending.current) return; pending.current = true; setOpening(entry.id); setError('');
    try { await post(`recent/forget?path=${encodeURIComponent(entry.path)}`, { project_id: entry.id }); setConfirmRemoveId(''); await load(); }
    catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setOpening(''); }
  }
  const recentGroups = projects.reduce<Array<{ type: ResearchMode; projects: RecentProject[] }>>((groups, project) => {
    const type: ResearchMode = project.investigation_type && Object.hasOwn(researchTypeLabels, project.investigation_type)
      ? project.investigation_type as ResearchMode
      : 'default';
    const group = groups.find(item => item.type === type);
    if (group) group.projects.push(project);
    else groups.push({ type, projects: [project] });
    return groups;
  }, []).sort((a, b) => researchTypeLabel(a.type).localeCompare(researchTypeLabel(b.type)));
  return <div className="empty home-empty home-recents">
    {loading ? <p role="status">Loading recent projects…</p> : !projects.length && <p>No recent projects yet. Import a project or begin a new project.</p>}
    {recentGroups.map(group => {
      const groupKey = group.type ?? 'other';
      const groupExpanded = expandedGroups[groupKey] ?? savedHomeGroupOpen('recent', groupKey);
      const hiddenRunningProject = !groupExpanded && group.projects.some(entry => entry.research_running);
      return <details className="recent-type-group" key={groupKey} open={groupExpanded} onToggle={event => {
        const isOpen = event.currentTarget.open;
        try { window.localStorage.setItem(`sigma.home.recentGroup:${groupKey}`, String(isOpen)); } catch { /* Preserve state when storage is available. */ }
        setExpandedGroups(current => current[groupKey] === isOpen ? current : { ...current, [groupKey]: isOpen });
      }}>
      <summary>{group.type && group.type in researchTypeLabels && <ResearchTypeIcon type={group.type as ResearchMode}/>}<span>{researchTypeLabel(group.type)}{hiddenRunningProject && <><span className="research-running-indicator" aria-hidden="true"/><span className="sr-only">Research running in this category</span></>}</span><small>{group.projects.length} {group.projects.length === 1 ? 'project' : 'projects'}</small></summary>
      <ul>{group.projects.map((entry, index) => <li key={entry.id}>
        <div className="recent-entry">
          <div className="recent-title-row">
            <button className="recent-open" disabled={!entry.available || !!opening} onClick={() => void open(entry)}>{index === 0 || entry.path === window.localStorage.getItem('sigma.currentProject') ? <strong className={`${index === 0 ? 'is-most-recent-project' : ''} ${entry.path === window.localStorage.getItem('sigma.currentProject') ? 'is-current-project' : ''}`.trim()}>{entry.title}</strong> : entry.title}{entry.research_running && <span className="research-running-indicator" aria-hidden="true"/>}</button>
          </div>
          <div className="recent-meta-row"><small><span>{entry.strategy_count === null ? difficultyDescription(entry.difficulty) : <>{strategyCount(entry.strategy_count)} · {entry.research_running && <><span className="recent-running">Running</span> · </>}{difficultyDescription(entry.difficulty)}</>}</span></small><button className="recent-forget" disabled={!!opening} aria-label={`Remove ${entry.title} from Saved Projects`} aria-expanded={confirmRemoveId === entry.id} data-tooltip="Remove from Saved Projects; keep all research" onClick={event => {
            if (confirmRemoveId === entry.id) { setConfirmRemoveId(''); return; }
            const trigger = event.currentTarget.getBoundingClientRect();
            setConfirmRemovePlacement(window.innerHeight - trigger.bottom < 190 ? 'above' : 'below');
            setConfirmRemoveId(entry.id);
          }}>Remove</button>{confirmRemoveId === entry.id && <div className={`recent-remove-actions recent-remove-${confirmRemovePlacement}`}><div className="recent-remove-confirm" role="group" aria-label={`Confirm remove ${entry.title}`}><p>Remove “{entry.title}” from Saved Projects? The project and its research will be kept in storage.</p><div className="recent-remove-confirm-actions"><button type="button" className="destructive-action" disabled={!!opening} onClick={() => void forget(entry)}>Confirm</button><button type="button" disabled={!!opening} onClick={() => setConfirmRemoveId('')}>Cancel</button></div></div></div>}</div>
          <span title={entry.path}>{entry.path}</span>
        </div>
        {entry.error && <p className="recent-unavailable">{entry.error}</p>}
      </li>)}</ul>
    </details>;
    })}
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

function SampleProjects({ onOpen, guest = false }: { onOpen: (view: ProjectView) => void; guest?: boolean }) {
  const [projects, setProjects] = useState<SampleProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [opening, setOpening] = useState('');
  const pending = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    void fetch('/api/projects/samples', { signal: controller.signal }).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? 'Samples unavailable.');
      setProjects([...data.projects].sort((a: SampleProject, b: SampleProject) => {
        const typeOrder = researchTypeLabel(a.investigation_type).localeCompare(researchTypeLabel(b.investigation_type), 'en', { sensitivity: 'base' });
        return typeOrder || a.title.localeCompare(b.title, 'en', { sensitivity: 'base' });
      })); setLoading(false);
    }).catch(error => { if (!controller.signal.aborted) { setError(errorMessage(error)); setLoading(false); } });
    return () => controller.abort();
  }, []);
  async function open(sample: SampleProject) {
    if (pending.current) return; pending.current = true; setOpening(sample.id); setError('');
    try {
      const copy = await post<ProjectView>('samples/open', { sample_id: sample.id });
      // Guest copies live only in the temporary guest workspace.
      if (!guest) window.localStorage.setItem('sigma.homeCatalogTab', 'recent');
      onOpen(copy);
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
  return <div className="empty home-empty home-samples">
    {loading ? <p role="status">Loading sample projects…</p> : !projects.length && !error && <p>No sample projects are available.</p>}
    {groups.map(group => <details className="sample-type-group" key={group.type} open={savedHomeGroupOpen('sample', group.type)} onToggle={event => { try { window.localStorage.setItem(`sigma.home.sampleGroup:${group.type}`, String(event.currentTarget.open)); } catch { /* Keep the disclosure usable when storage is unavailable. */ } }}>
      <summary><ResearchTypeIcon type={group.type}/><span>{researchTypeLabel(group.type)}</span><small>{group.samples.length} {group.samples.length === 1 ? 'sample' : 'samples'}</small></summary>
      <ul>{group.samples.map(sample => <li key={sample.id}><button className="sample-open" disabled={!!opening} onClick={() => void open(sample)} aria-label={`Open ${sample.title}`}><strong>{sample.title}</strong><small><span>{strategyCount(sample.strategy_count)} · {difficultyDescription(sample.difficulty)}</span></small></button></li>)}</ul>
    </details>)}
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

function HomeCatalog({ onOpen, guest = false }: { onOpen: (view: ProjectView) => void; guest?: boolean }) {
  const cloud = useCloudIdentity();
  const savedTooltip = guest
    ? 'Sign in to view your saved projects.'
    : !cloud?.target || cloud.target === 'local'
      ? 'In local mode, all signed-in accounts share this project list.'
      : 'Show saved projects. Click again to collapse or expand all.';
  const [tab, setTab] = useState<'recent' | 'samples'>(() =>
    guest ? 'samples' : window.localStorage.getItem('sigma.homeCatalogTab') === 'recent' ? 'recent' : 'samples');
  const recent = useRef<HTMLButtonElement>(null);
  const samples = useRef<HTMLButtonElement>(null);
  const recentPanel = useRef<HTMLDivElement>(null);
  const samplesPanel = useRef<HTMLDivElement>(null);
  useEffect(() => { if (!guest) window.localStorage.setItem('sigma.homeCatalogTab', tab); }, [guest, tab]);
  function switchTab(next: 'recent' | 'samples') {
    if (next === tab) {
      const panel = next === 'samples' ? samplesPanel.current : recentPanel.current;
      if (panel) {
        const selector = next === 'samples' ? '.sample-type-group' : '.recent-type-group';
        const groups = Array.from(panel.querySelectorAll<HTMLDetailsElement>(selector));
        const expandAll = groups.length > 0 && groups.every(group => !group.open);
        groups.forEach(group => { group.open = expandAll; });
      }
      return;
    }
    setTab(next); (next === 'recent' ? recent : samples).current?.focus();
  }
  return <div className="home-catalog"><div className="catalog-tabs" role="tablist" aria-label="Project lists" onKeyDown={event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); switchTab(tab === 'samples' ? 'recent' : 'samples'); }
    if (event.key === 'Home') { event.preventDefault(); switchTab('samples'); }
    if (event.key === 'End') { event.preventDefault(); switchTab('recent'); }
  }}>
    <button ref={samples} id="samples-tab" role="tab" aria-controls="samples-panel" aria-selected={tab === 'samples'} tabIndex={tab === 'samples' ? 0 : -1} data-tooltip="Selecting a sample copies into a new project." onClick={() => switchTab('samples')}>Samples</button>
    <button ref={recent} id="recent-tab" role="tab" aria-controls="recent-panel" aria-selected={tab === 'recent'} tabIndex={tab === 'recent' ? 0 : -1} data-tooltip={savedTooltip} onClick={() => switchTab('recent')}>Saved</button>
  </div>
    <div ref={recentPanel} id="recent-panel" role="tabpanel" aria-labelledby="recent-tab" hidden={tab !== 'recent'}>{guest ? <p className="guest-recent-message"><span>Sign in to create and</span><span>save your own projects.</span></p> : <RecentProjects onOpen={onOpen}/>}</div>
    <div ref={samplesPanel} id="samples-panel" role="tabpanel" aria-labelledby="samples-tab" hidden={tab !== 'samples'}><SampleProjects onOpen={onOpen} guest={guest}/></div>
  </div>;
}

type CloudResearchBudget = {
  allowance_usd: number;
  estimated_usage_usd: number;
  held_usd: number;
  reserved_and_estimated_usd: number;
  remaining_usd: number;
  global_remaining_usd?: number;
  global_ceiling_usd?: number;
  global_spend_period?: 'cumulative' | 'calendar_month';
  global_reset_at?: string | null;
  unknown_provider_attempts: number;
};

function Home({ initialPath, onOpen }: {
  initialPath: string; onOpen: (view: ProjectView) => void;
}) {
  const cloud = useCloudIdentity();
  const showConnectionStatus = !cloud?.enabled || (cloud.authenticated && cloud.user?.role !== 'guest');
  const [entry, setEntry] = useState<'open' | 'new' | 'import' | null>(null);
  const [aboutOpen, setAboutOpen] = useState(false);
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
      <div className="home-topline"><div className="home-auth-pills"><MockAuthSelector/><div className="identity-pill-stack"><GoogleIdentityPill inviteInHeader/><HomeInvitationAction/>{showConnectionStatus && <ConnectionStatus projectHeader cloudFunding={cloudFundingFor(cloud)} zeroAllowanceAction={<ReloadMeAction connectionPill/>}/>}</div></div><div className="home-header-actions"><button type="button" ref={aboutButton} className="home-about-button" aria-haspopup="dialog" aria-expanded={aboutOpen} onClick={() => setAboutOpen(true)}>About SIGMA</button>{cloud?.user?.role === 'admin' && <a href="#administrator-settings" className="administrator-settings-link" aria-label="Administrator settings" onClick={event => { event.preventDefault(); cloud.openAccessManagement(); }}>Admin Settings</a>}</div></div>
      <section className="home-projects" aria-labelledby="home-projects-heading">
        <div className="home-projects-heading">
          <h1 id="home-projects-heading" ref={heading} tabIndex={-1}>Projects</h1>
          {(!cloud?.enabled || (cloud.authenticated && cloud.user?.role !== 'guest')) && <>
            <button type="button" ref={newButton} className="home-project-action" data-tooltip="Create a project" onClick={() => setEntry('new')}>New</button>
          <button type="button" className="home-project-action" data-tooltip="Import a portable JSON project" onClick={() => setEntry('import')}>Import</button>
          </>}
        </div>
        <HomeCatalog onOpen={onOpen} guest={!!cloud?.enabled && (!cloud.authenticated || cloud.user?.role === 'guest')}/>
      </section>
      <img className="home-slogan" src="/sigma-slogan-copper-approved.png" alt="Strategy · Investigation · Generation · Measurement · Assessment"/>
      <footer className="home-art-credit" aria-label={`Crafted by Brian Kramer and ${creditAdjective} OpenAI agents`} onPointerEnter={event => { if (!(event.relatedTarget instanceof Node) || !event.currentTarget.contains(event.relatedTarget)) launchCreditStreak(); }} onClick={launchCreditPlunk}><span>Crafted by Brian Kramer</span><span>and {creditAdjective} OpenAI agents.</span>{creditStreaks.map(({ id, line }) => <span key={id} className={`home-credit-streak home-credit-streak--${line}`} aria-hidden="true" onAnimationEnd={() => removeCreditStreak(id)}/>)}{creditPlunk !== null && <span key={creditPlunk} className="home-credit-plunk" aria-hidden="true" onAnimationEnd={() => finishCreditPlunk(creditPlunk)}/>}</footer>
      {entry === 'import' && <ImportProjectDialog onOpen={onOpen} onCancel={cancel}/>}
      {entry === 'open' && <ProjectEntryDialog initialPath={initialPath} onOpen={onOpen} onCancel={cancel}/>}
      {entry === 'new' && <ProjectSettingsDialog onSaved={onOpen} onCancel={cancel}/>}
      {aboutOpen && <AboutDialog onClose={closeAbout}/>}
    </div>
  </div>;
}

function StrategyTitleEditor({ strategy, path, onSaved, modeDisabled, descriptionDraft, onEnterMode, onExitMode, onEditDescription, expanded, onToggle, commands }: {
  strategy: Strategy; path: string; onSaved: (view: ProjectView) => void; modeDisabled: boolean; descriptionDraft: string; onEnterMode: () => boolean; onExitMode: () => void;
  onEditDescription: () => void; expanded: boolean; onToggle: () => void; commands: ReactNode;
}) {
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
  async function save(event: FormEvent) {
    event.preventDefault(); event.stopPropagation();
    if (busy) return;
    if (!draft.trim()) { setError('Enter a strategy title.'); input.current?.focus(); return; }
    setBusy(true); setError('');
    try {
      const next = await post<ProjectView>('strategies/edit', {
        path, strategy_id: strategy.id, title: draft, approach: descriptionDraft,
      });
      setEditing(false); onExitMode(); onSaved(next);
      requestAnimationFrame(() => trigger.current?.focus());
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <div className={`strategy-title-editor${editing ? ' is-renaming' : ''}`}>
    {editing ? <form ref={form} onSubmit={save} className="strategy-rename-form">
      <label className="sr-only" htmlFor={`strategy-title-${strategy.id}`}>Strategy title</label>
      <input ref={input} id={`strategy-title-${strategy.id}`} aria-label="Strategy title" value={draft} size={Math.max(8, Math.min(50, draft.length + 1))} maxLength={200} disabled={busy}
        required onChange={event => { setDraft(event.target.value); setError(''); }} onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); cancel(); } }}/>
      <button type="submit" className="text-view-link" title="Save strategy title" disabled={busy}>Save</button>
      <button type="button" className="text-view-link" title="Cancel editing the strategy title" disabled={busy} onClick={() => cancel()}>Cancel</button>
    </form> : <div className="strategy-title-line">
      <button type="button" id={`strategy-${strategy.id}`} className={`strategy-row-disclosure${strategy.enabled ? '' : ' is-disabled'}`} title={`${expanded ? 'Collapse' : 'Expand'} strategy: ${shownTitle}`} aria-expanded={expanded} aria-controls={`strategy-content-${strategy.id}`} onClick={onToggle}><DisclosureChevron expanded={expanded}/><h3>{shownTitle}</h3></button>
      <span id={`strategy-markdown-slot-${strategy.id}`} className="strategy-markdown-slot"/><button type="button" ref={trigger} className="text-view-link text-view-icon workspace-icon-button strategy-title-pencil" aria-label={`Edit strategy title and description: ${shownTitle}`} data-tooltip-disabled disabled={modeDisabled}
        onClick={() => { if (onEnterMode()) { setEditing(true); onEditDescription(); } }}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg></button><span id={`strategy-markdown-slot-${strategy.id}-copy`} className="strategy-copy-slot"/>
      {commands}
    </div>}
    {error && <p className="error" role="alert">{error}</p>}
  </div>;
}

function StrategyCommands({ strategy, onCommand, disabled = false }: {
  strategy: Strategy; onCommand: (mode: 'remove' | 'fork' | 'toggle', strategy: Strategy) => void; disabled?: boolean;
}) {
  const [confirmingRemove, setConfirmingRemove] = useState(false);
  return <span className="strategy-inline-commands">
    <button type="button" className="text-view-link" disabled={disabled}
      title={`${strategy.enabled ? 'Disable' : 'Enable'} strategy`} onClick={() => onCommand('toggle', strategy)}>{strategy.enabled ? 'Disable' : 'Enable'}</button>
    <button type="button" className="text-view-link" disabled={disabled}
      title="Fork strategy" onClick={() => onCommand('fork', strategy)}>Fork</button>
    <span className="strategy-remove-anchor">
      <button type="button" id={`commands-${strategy.id}`} className="text-view-link" disabled={disabled}
        title="Remove strategy" onClick={() => setConfirmingRemove(true)}>Remove</button>
      {confirmingRemove && <div className="strategy-remove-popover"><div className="research-stop-confirm" role="group" aria-label={`Confirm remove strategy ${strategy.title}`}>
        <p>Remove “{strategy.title}” from Strategies? Its research and history will be kept in the project.</p>
        <div className="session-remove-confirm-actions">
          <button type="button" className="text-view-link destructive-action" disabled={disabled} onClick={() => { setConfirmingRemove(false); onCommand('remove', strategy); }}>Confirm</button>
          <button type="button" className="text-view-link" disabled={disabled} onClick={() => setConfirmingRemove(false)}>Cancel</button>
        </div>
      </div></div>}
    </span>
  </span>;
}

function NewStrategy({ path, onSaved, onCancel, initialDraft }: {
  path: string; initialDraft?: { title: string; approach: string; summary?: string }; onSaved: (view: ProjectView) => void; onCancel: () => void;
}) {
  const submitting = useRef(false);
  const [title, setTitle] = useState(initialDraft?.title ?? '');
  const [approach, setApproach] = useState(initialDraft?.approach ?? '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const titleInput = useRef<HTMLInputElement>(null);
  useEffect(() => { titleInput.current?.focus(); }, []);
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current) return; submitting.current = true; setBusy(true); setError('');
    try { onSaved(await post<ProjectView>('strategies', { path, title, approach, summary: initialDraft?.summary ?? '' })); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
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
}

function StrategyCreationActions({ buttonRef, disabled, hideNew = false, onManual, onAI }: {
  buttonRef: React.RefObject<HTMLButtonElement | null>; disabled: boolean; hideNew?: boolean; onManual: () => void; onAI: () => void;
}) {
  return <div className="strategy-heading-actions">
    {!hideNew && <button type="button" className="text-view-link" ref={buttonRef} title="Create a new strategy" disabled={disabled} onClick={onManual}>New</button>}
    <button type="button" className="text-view-link" title="Generate a strategy with AI" disabled={disabled} onClick={onAI}>Generate</button>
  </div>;
}

function ProcessControlsView({ controls, disabled, guest = false, onGuestPlay, playButtonRef }: { controls: ProcessControls; disabled: boolean; guest?: boolean; onGuestPlay?: () => void; playButtonRef?: React.RefObject<HTMLButtonElement | null> }) {
  return <span className="strategy-process-controls" aria-label="Research process controls">
      {controls.confirming ? <>
        {controls.confirmationSummary && <span className="session-start-limits" aria-label={`Effective session limits: ${controls.confirmationSummary}`}>{controls.confirmationSummary}</span>}
        <button type="button" className="text-view-link session-start-link" title={`Confirm start new Session ${controls.nextSessionNumber}`} disabled={disabled} onClick={controls.start}>Start new session #{controls.nextSessionNumber}</button>
        <button type="button" className="text-view-link session-start-link" title="Cancel starting a research session" disabled={disabled} onClick={controls.cancel}>Cancel</button>
      </> : <>
      <button ref={playButtonRef} type="button" className="text-view-link text-view-icon workspace-icon-button process-control" aria-label={controls.playLabel} title={controls.playLabel} data-tooltip={controls.playLabel} disabled={disabled || (!guest && controls.playDisabled)} onClick={guest ? onGuestPlay : controls.play}>
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M6 3.8v12.4L16 10 6 3.8Z"/></svg>
      </button>
      <button type="button" className="text-view-link text-view-icon workspace-icon-button process-control" aria-label="Stop research session" title="Stop research session" data-tooltip="Stop research session" disabled={controls.stopDisabled || disabled} onClick={controls.stop}>
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5h10v10H5z"/></svg>
      </button>
      </>}
  </span>;
}

function GuestPlayDialog({ onClose, onSignIn, playButtonRef }: { onClose: () => void; onSignIn: () => void; playButtonRef: React.RefObject<HTMLButtonElement | null> }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const signIn = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    dialog.current?.showModal();
    signIn.current?.focus();
  }, []);
  function dismiss() {
    if (dialog.current?.open) dialog.current.close();
    onClose();
    requestAnimationFrame(() => playButtonRef.current?.focus());
  }
  function startSignIn() {
    if (dialog.current?.open) dialog.current.close();
    onSignIn();
  }
  return <dialog ref={dialog} className="project-settings-dialog guest-research-dialog" aria-labelledby="guest-research-heading" aria-describedby="guest-research-message" onCancel={event => { event.preventDefault(); dismiss(); }}>
    <header className="settings-header"><h2 id="guest-research-heading">Ready to investigate?</h2></header>
    <div className="settings-body">
      <p id="guest-research-message">Sign in to run a research session.</p>
      <div className="settings-actions session-remove-confirm-actions">
        <button ref={signIn} type="button" className="text-view-link guest-play-signin" onClick={startSignIn}>Sign in with Google</button>
        <button type="button" className="text-view-link" onClick={dismiss}>Cancel</button>
      </div>
    </div>
  </dialog>;
}

type ProposalResult = { draft: { title: string; summary: string; approach: string; first_tests: string; assumptions: string; failure_modes: string }; provenance: { provider: string; model: string; reasoning_effort?: string | null }; receipt: string };
type AgenticEvent = { type: string; sequence: number; run_id: string; kind?: 'explore' | 'challenge' | 'revise' | null; attempt?: number | null; summary?: string | null; outcome?: 'revise' | 'retry' | 'present' | 'stop' | null; max_calls?: number | null; draft?: ProposalResult['draft'] | null; provenance?: ProposalResult['provenance'] | null; receipt?: string | null; assessment?: 'distinct' | 'overlapping' | 'unconvincing' | null; objections?: string[] | null; missing_obligations?: string | null; mechanism_comparison?: string | null };
const activityLabels = { explore: 'Exploring a candidate', challenge: 'Independent challenge', revise: 'Targeted revision' } as const;
async function readAgenticStream(response: Response, onEvent: (event: AgenticEvent) => void): Promise<AgenticEvent> {
  if (!response.ok) { let detail = `HTTP ${response.status}`; try { const body = await response.json(); detail = body.error ?? body.detail ?? detail; } catch {} throw new Error(String(detail)); }
  if (!response.body) throw new Error('The server returned no progress stream. Nothing was saved.');
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''; let sequence = 0; let runId = ''; let terminal: AgenticEvent | null = null;
  const consume = (chunk: string) => {
    buffer += chunk; const records = buffer.split(/\r?\n\r?\n/); buffer = records.pop() ?? '';
    for (const record of records) {
      const data = record.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
      if (!data) continue;
      let event: AgenticEvent; try { event = JSON.parse(data) as AgenticEvent; } catch { throw new Error('The server sent malformed progress data. You can retry; nothing was saved.'); }
      if (!['run.started', 'activity.started', 'activity.completed', 'decision', 'run.completed', 'run.stopped', 'run.failed'].includes(event?.type)) throw new Error('The server sent an unknown progress event. You can retry; nothing was saved.');
      if (!event || typeof event.type !== 'string' || !Number.isInteger(event.sequence) || event.sequence !== sequence + 1 || typeof event.run_id !== 'string' || !/^[0-9a-f]{32}$/.test(event.run_id)) throw new Error('The progress stream was incomplete or out of order. You can retry; nothing was saved.');
      if (runId && event.run_id !== runId) throw new Error('The progress stream changed run identity. You can retry; nothing was saved.');
      if (terminal) throw new Error('The server sent progress after its terminal event. You can retry; nothing was saved.');
      sequence = event.sequence; runId = event.run_id;
      const activityKind = event.kind === 'explore' || event.kind === 'challenge' || event.kind === 'revise';
      if (event.type === 'run.started' && (!Number.isInteger(event.max_calls) || (event.max_calls ?? 0) < 2 || (event.max_calls ?? 0) > 120)) throw new Error('The server sent an invalid run limit. You can retry; nothing was saved.');
      if (event.type.startsWith('activity.') && (!activityKind || !Number.isInteger(event.attempt) || (event.attempt ?? 0) < 1 || (event.attempt ?? 0) > 15)) throw new Error('The server sent an invalid activity event. You can retry; nothing was saved.');
      if (event.type === 'activity.completed' && typeof event.summary !== 'string') throw new Error('The server sent an incomplete activity result. You can retry; nothing was saved.');
      if (event.type === 'activity.completed' && event.kind === 'challenge' && (!event.assessment || !Array.isArray(event.objections) || typeof event.missing_obligations !== 'string' || typeof event.mechanism_comparison !== 'string')) throw new Error('The server sent an incomplete reviewer summary. You can retry; nothing was saved.');
      if (event.type === 'decision' && (!['revise', 'retry', 'present', 'stop'].includes(event.outcome ?? '') || typeof event.summary !== 'string')) throw new Error('The server sent an invalid coordinator decision. You can retry; nothing was saved.');
      if (['run.stopped', 'run.failed'].includes(event.type) && typeof event.summary !== 'string') throw new Error('The server sent an incomplete terminal result. You can retry; nothing was saved.');
      if (event.type === 'run.completed') {
        const fields = ['title', 'summary', 'approach', 'first_tests', 'assumptions', 'failure_modes'];
        if (!event.draft || typeof event.receipt !== 'string' || !event.receipt || !event.provenance || typeof event.provenance.provider !== 'string' || typeof event.provenance.model !== 'string' || fields.some(key => typeof event.draft?.[key as keyof ProposalResult['draft']] !== 'string')) throw new Error('The completed stream did not include a complete draft and receipt. You can retry; nothing was saved.');
      }
      if (['run.completed', 'run.stopped', 'run.failed'].includes(event.type)) terminal = event;
      onEvent(event);
    }
  };
  try { while (true) { const { done, value } = await reader.read(); if (done) break; consume(decoder.decode(value, { stream: true })); } consume(decoder.decode()); }
  catch (error) { await reader.cancel().catch(() => {}); throw error; }
  if (buffer.trim()) consume('\n\n');
  if (!terminal) throw new Error('The progress stream ended without a final result. You can retry; nothing was saved.');
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
      } else if (terminal.type === 'run.stopped') { setCurrentActivity('Run stopped'); setError(`${terminal.summary ?? 'No viable candidate was found.'} Nothing was saved. You can retry with different guidance.`); }
      else { setCurrentActivity('Run failed'); throw new Error(terminal.summary ?? 'The run failed. No strategy was saved.'); }
    } catch (error) {
      if (controller.signal.aborted) { setCurrentActivity('Run cancelled'); setError('Run cancelled. Nothing was saved. If generation had started, its evidence will be retained in project export. You can retry.'); }
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

function ProjectScreen({ path, initialView, onClose, goHome }: {
  path: string; initialView?: ProjectView; onClose: () => void;
  goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const cloud = useCloudIdentity();
  const guest = !!cloud?.enabled && (!cloud.authenticated || cloud.user?.role === 'guest');
  const [view, setView] = useState<ProjectView | null>(initialView ?? null);
  const [error, setError] = useState('');
  const [closing, setClosing] = useState(false);
  const [researchRunning, setResearchRunning] = useState(false);
  const [editing, setEditing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [manualDraft, setManualDraft] = useState<{ title: string; approach: string; summary?: string }>();
  const [projectEditing, setProjectEditing] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [paperOpen, setPaperOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const modeOwner = useRef<string | null>(null);
  const [activeMode, setActiveMode] = useState<string | null>(null);
  const enterMode = useCallback((owner: string) => {
    if (modeOwner.current !== null) return false;
    modeOwner.current = owner; setActiveMode(owner); return true;
  }, []);
  const exitMode = useCallback((owner: string) => {
    if (modeOwner.current !== owner) return;
    modeOwner.current = null; setActiveMode(null);
  }, []);
  const editProjectButton = useRef<HTMLButtonElement>(null);
  const [ordering, setOrdering] = useState(false);
  const [previewOrder, setPreviewOrder] = useState<string[] | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const drag = useRef<{ id: string; order: string[]; pointer: number | null } | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const [guestAiNotice, setGuestAiNotice] = useState('');
  const [focusStrategy, setFocusStrategy] = useState('');
  const [strategiesExpanded, setStrategiesExpanded] = useState(() => window.localStorage.getItem(`sigma.strategiesPane:${path}`) !== 'false');
  const [collapsedStrategies, setCollapsedStrategies] = useState<Set<string>>(() => new Set());
  const [textEditSignals, setTextEditSignals] = useState<Record<string, number>>({});
  const [combinedTextDrafts, setCombinedTextDrafts] = useState<Record<string, string>>({});
  const requestTextEdit = (key: string) => setTextEditSignals(current => ({ ...current, [key]: (current[key] ?? 0) + 1 }));
  const updateCombinedTextDraft = (key: string, draft: string) => setCombinedTextDrafts(current => ({ ...current, [key]: draft }));
  const [projectExpanded, setProjectExpanded] = useState(() => window.localStorage.getItem(`sigma.projectPane:${path}`) !== 'false');
  const [processControls, setProcessControls] = useState<ProcessControls>({ play: () => {}, stop: () => {}, playDisabled: true, stopDisabled: true, playLabel: 'Start a new research session' });
  const [guestPlayOpen, setGuestPlayOpen] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  const playButton = useRef<HTMLButtonElement>(null);
  const resumedPlay = useRef(false);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlPlayIntent = params.get('resume_play') === '1';
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
    post<ProjectView>('open', { path }, controller.signal).then(setView).catch(error => {
      if (!controller.signal.aborted) setError(errorMessage(error));
    });
    return () => controller.abort();
  }, [path]);
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
  const frame = { goHome, close: { action: close, busy: closing }, connectionDisabled: activeMode !== null, researchRunning };
  function toggleStrategiesPane() {
    setStrategiesExpanded(open => { window.localStorage.setItem(`sigma.strategiesPane:${path}`, String(!open)); return !open; });
  }
  function showStrategy(id: string) {
    setCollapsedStrategies(current => { const next = new Set(current); next.delete(id); return next; });
    if (!strategiesExpanded) {
      setStrategiesExpanded(true);
      window.localStorage.setItem(`sigma.strategiesPane:${path}`, 'true');
    }
    if (id) setFocusStrategy(id);
  }
  function cancel() { setEditing(false); exitMode('new-strategy'); requestAnimationFrame(() => newButton.current?.focus()); }
  function expandStrategies() { setStrategiesExpanded(true); window.localStorage.setItem(`sigma.strategiesPane:${path}`, 'true'); }
  const collapseProjectAndStrategies = useCallback(() => {
    setProjectExpanded(false);
    setStrategiesExpanded(false);
    window.localStorage.setItem(`sigma.projectPane:${path}`, 'false');
    window.localStorage.setItem(`sigma.strategiesPane:${path}`, 'false');
  }, [path]);
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
    requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.about-action')?.focus());
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
      `Fork rationale: derived from strategy “${session.strategy_title}” (ID ${session.strategy_id}) after Research Session #${session.session_number}.`,
      'Use the saved findings below to revise the approach. Preserve unresolved obligations as open work; treat model notes as unverified.',
      evidence ? `\nSaved findings and criticism:\n${evidence}` : '',
      '\nParent approach follows:',
    ].filter(Boolean).join('\n');
    const available = Math.max(0, MAX_STRATEGY_APPROACH - prefix.length - 120);
    const clippedParent = parentApproach.slice(0, available);
    const approach = `${prefix}\n${clippedParent}${parentApproach.length > clippedParent.length ? '\n[Parent approach shortened to fit; see the source session for the complete saved strategy.]' : ''}`.slice(0, MAX_STRATEGY_APPROACH);
    setManualDraft({
      title: `${session.strategy_title} (Session ${session.session_number} fork)`.slice(0, 200),
      summary: `Fork of ${session.strategy_title} informed by Session #${session.session_number}`.slice(0, 300),
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
      setAnnouncement('Strategy order saved.');
    } catch (error) { setError(errorMessage(error)); setAnnouncement('Order save failed. Previous order restored.'); }
    finally { setOrdering(false); setPreviewOrder(null); requestAnimationFrame(() => document.getElementById(`grip-${active.id}`)?.focus()); }
  }
  const projectActionBar = <div className="project-primary-actions">
    <div className="project-pane-actions">
      <button type="button" className="text-view-link text-view-icon project-latex-button" aria-label="LaTeX research paper" title="Generate a LaTeX research paper" data-tooltip="Generate a LaTeX research paper" disabled={closing || ordering || !!dragId || activeMode !== null} onClick={() => setPaperOpen(true)}>
        <span className="latex-wordmark" aria-hidden="true">T<span className="latex-lowered-e">E</span>X</span>
      </button>
      <button type="button" className="text-view-link text-view-icon project-lean-button" aria-label="Generate Lean proof (coming soon)" title="Generate Lean proof (coming soon)" data-tooltip="Generate Lean proof (coming soon)" disabled>
        <img src="/lean-logo.svg" alt="" aria-hidden="true"/>
      </button>
      <button type="button" className="text-view-link text-view-icon" aria-label="Export project" title="Export project" data-tooltip="Export project" disabled={closing || ordering || !!dragId} onClick={() => setExportOpen(true)}>
        <svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>
      </button>
      <button ref={editProjectButton} type="button" className="text-view-link text-view-icon" aria-label="Project settings" title="Settings" disabled={closing || ordering || !!dragId || activeMode !== null} onClick={() => { if (enterMode('project-settings')) setProjectEditing(true); }}>
        <SettingsGearIcon />
      </button>
    </div>
    <ProcessControlsView controls={processControls} disabled={activeMode !== null || closing || ordering || !!dragId} guest={guest} onGuestPlay={() => setGuestPlayOpen(true)} playButtonRef={playButton}/>
  </div>;
  return <WorkspaceFrame {...frame} projectTitle={project.title} projectType={project.investigation_type} projectView={view!} onProjectUpdated={setView} projectActions={projectActionBar}>
    <section className="workspace-pane project-pane" aria-labelledby="project-pane-heading">
      <header className="workspace-pane-heading project-pane-heading">
        <h2 id="project-pane-heading" ref={heading} tabIndex={-1}>
          <button type="button" className="workspace-section-disclosure" aria-expanded={projectExpanded} aria-controls="project-pane-content" title={`${projectExpanded ? 'Collapse' : 'Expand'} Project section`} onClick={() => setProjectExpanded(value => { window.localStorage.setItem(`sigma.projectPane:${path}`, String(!value)); return !value; })}>
            <DisclosureChevron expanded={projectExpanded}/>Project
          </button>
        </h2>
      </header>
      <div id="project-pane-content" hidden={!projectExpanded}>
      <div className="project-overview-card">
      <ProjectPaneTitle view={view} onSaved={setView} disabled={closing || ordering || !!dragId} modeDisabled={activeMode !== null && activeMode !== 'project-title'} descriptionDraft={combinedTextDrafts.project ?? project.problem} onEnterMode={() => enterMode('project-title')} onExitMode={() => exitMode('project-title')} onEditDescription={() => requestTextEdit('project')}/>
      <div className="project-pane-content">
        <div className="project-intro">
          <TextViews mathematical={project.investigation_type === 'mathematical'} path={view.path} scope="project" source={project.problem} projectTitle={project.title} contentClass="objective" onSaved={setView} hideProjectActions hideProjectHeading hideEditAction markdownSlotId="project-markdown-slot" editSignal={textEditSignals.project ?? 0} combinedEditMode={activeMode === 'project-title'} onCombinedDraftChange={draft => updateCombinedTextDraft('project', draft)} modeDisabled={activeMode !== null && activeMode !== 'text-project' && activeMode !== 'project-title'} onEnterMode={() => enterMode('text-project')} onExitMode={() => exitMode('text-project')}/>
        </div>
      </div>
      </div>
      </div>
    </section>
    {error && <p role="alert" className="error">{error}</p>}
    <section className={`pool workspace-pane strategies-pane${strategiesExpanded ? '' : ' is-collapsed'}`} aria-labelledby="pool-heading">
      <header className="pool-heading workspace-pane-heading strategies-pane-heading">
        <h2 id="pool-heading" tabIndex={-1}><button type="button" className="workspace-section-disclosure" title={`${strategiesExpanded ? 'Collapse' : 'Expand'} Strategies section`} aria-expanded={strategiesExpanded} aria-controls="strategies-pane-content" onClick={toggleStrategiesPane}><DisclosureChevron expanded={strategiesExpanded}/>Strategies</button></h2>
        <div className="strategies-heading-right">
          <StrategyCreationActions buttonRef={newButton} hideNew={generating} disabled={activeMode !== null || generating || closing || ordering || !!dragId || !!processControls.confirming} onManual={startNewStrategy} onAI={() => { if (guest) setGuestAiNotice('AI features require a signed-in account. Your guest project remains available.'); else startGeneration(); }}/>
          <p className="section-count">{strategies.length} strateg{strategies.length === 1 ? 'y' : 'ies'}</p>
        </div>
      </header>
      {guestAiNotice && <p className="hint guest-ai-notice" role="status">{guestAiNotice}</p>}
      <div id="strategies-pane-content" hidden={!strategiesExpanded}>
      <p className="sr-only" role="status">{announcement}</p>
      <div id="strategy-composer">{editing && <NewStrategy initialDraft={manualDraft} path={view.path} onCancel={cancel} onSaved={next => {
        const strategy = next.project.strategies[next.project.strategies.length - 1];
        setView(next); setEditing(false); exitMode('new-strategy'); setAnnouncement(`Strategy saved: ${strategy.title}`);
        setFocusStrategy(strategy.id);
      }}/>}
      {generating && <GenerateStrategy path={view.path} projectId={view.project.id} sourceGuard={JSON.stringify({ project_id: project.id, problem: project.problem, strategies: project.strategies.map(item => [item.id, item.title, item.approach, item.removed_at]) })} onCancel={() => { setGenerating(false); requestAnimationFrame(() => newButton.current?.focus()); }} onSaved={next => {
        const strategy = next.project.strategies.at(-1)!; setView(next); setGenerating(false); setFocusStrategy(strategy.id); setAnnouncement('AI-assisted strategy accepted and saved.');
      }}/>}</div>
      {strategies.length ? <div className="strategies-table">
        <div className="strategy-columns" aria-hidden="true"><span>Strategy</span></div>
        <ol className="strategy-list" aria-label="Strategies" aria-busy={ordering}>
        {strategies.map(strategy => <li className={`strategy-row${strategies.length === 1 ? ' is-only-strategy' : ''}${!strategy.enabled ? ' is-disabled' : ''}${dragId === strategy.id ? ' is-lifted' : ''}`} key={strategy.id} data-strategy-id={strategy.id}>
          <div className="strategy-row-main">
            <StrategyTitleEditor strategy={strategy} path={view.path} onSaved={setView} modeDisabled={activeMode !== null && activeMode !== `strategy-title-${strategy.id}`} descriptionDraft={combinedTextDrafts[`strategy:${strategy.id}`] ?? strategy.approach} onEnterMode={() => enterMode(`strategy-title-${strategy.id}`)} onExitMode={() => exitMode(`strategy-title-${strategy.id}`)} onEditDescription={() => requestTextEdit(`strategy:${strategy.id}`)} expanded={!collapsedStrategies.has(strategy.id)} onToggle={() => setCollapsedStrategies(current => { const next = new Set(current); if (next.has(strategy.id)) next.delete(strategy.id); else next.add(strategy.id); return next; })} commands={<StrategyCommands strategy={strategy} disabled={activeMode !== null || processControls.confirming} onCommand={(mode, strategy) => {
              if (ordering || dragId || activeMode !== null || processControls.confirming) return;
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
            <div id={`strategy-content-${strategy.id}`} className="strategy-expanded" hidden={collapsedStrategies.has(strategy.id)}><TextViews mathematical={project.investigation_type === 'mathematical'} path={view.path} scope="strategy" strategyId={strategy.id} source={strategy.approach} contentClass="strategy-approach" onSaved={setView} hideEditAction markdownSlotId={`strategy-markdown-slot-${strategy.id}`} editSignal={textEditSignals[`strategy:${strategy.id}`] ?? 0} combinedEditMode={activeMode === `strategy-title-${strategy.id}`} onCombinedDraftChange={draft => updateCombinedTextDraft(`strategy:${strategy.id}`, draft)} modeDisabled={activeMode !== null && activeMode !== `text-strategy-${strategy.id}` && activeMode !== `strategy-title-${strategy.id}`} onEnterMode={() => enterMode(`text-strategy-${strategy.id}`)} onExitMode={() => exitMode(`text-strategy-${strategy.id}`)}/></div>
          </div>
          {strategies.length > 1 && <button id={`grip-${strategy.id}`} className="drag-grip" disabled={ordering || closing}
            aria-label={`Reorder ${strategy.title}`} title={`Drag to reorder ${strategy.title}`} aria-describedby="reorder-help" aria-pressed={dragId === strategy.id}
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
    {guestPlayOpen && <GuestPlayDialog onClose={() => setGuestPlayOpen(false)} onSignIn={() => {
      window.sessionStorage.setItem('sigma.playSignInReturn', 'true');
      window.sessionStorage.setItem('sigma.resumeGuestPlay', 'true');
      setGuestPlayOpen(false);
      requestAnimationFrame(() => requestAnimationFrame(() => window.dispatchEvent(new Event('sigma-open-google-signin'))));
    }} playButtonRef={playButton}/>}
    <ResearchWorkspace path={view.path} projectId={project.id} strategies={strategies} advancedOutcomeDetails={view.project.show_advanced_outcome_details} onEnableAdvancedOutcome={async () => {
      const current = settingsOf(view);
      if (current.show_advanced_outcome_details) return;
      const next = await post<ProjectView>('update', { path: view.path, ...current, show_advanced_outcome_details: true, expected: current });
      setView(next);
      setAnnouncement('Advanced Outcome enabled.');
    }} onViewStrategy={showStrategy} onForkFromFindings={forkFromFindings} onControlsChange={setProcessControls} onRunningChange={setResearchRunning} onRevealNewSession={collapseProjectAndStrategies}/>
    {projectEditing && <ProjectSettingsDialog initial={view} onCancel={() => { setProjectEditing(false); exitMode('project-settings'); requestAnimationFrame(() => editProjectButton.current?.focus()); }} onSaved={next => { setView(next); setProjectEditing(false); exitMode('project-settings'); setAnnouncement('Project settings saved.'); requestAnimationFrame(() => editProjectButton.current?.focus()); }}/>}
    <ProjectExportDialog open={exportOpen} path={view.path} title={project.title} onCancel={() => { setExportOpen(false); requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.project-pane-actions [aria-label="Export project"]')?.focus()); }}/>
    {aboutOpen && <AboutDialog onClose={closeAbout}/>}
    {paperOpen && (
      <AIPaperDialog path={view.path} projectId={project.id} guest={guest} onCancel={() => {
        setPaperOpen(false);
        requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.project-latex-button')?.focus());
      }} />
    )}
    {SHOW_PROJECT_DETAILS_AND_HISTORY && <details className="project-details">
      <summary>Project details &amp; history</summary>
      <dl><dt>Identity</dt><dd>{project.id}</dd><dt>Directory</dt><dd>{view.path}</dd><dt>Format version</dt><dd>{project.schema_version}</dd><dt>Research type</dt><dd>{researchTypeLabel(project.investigation_type)}</dd>{project.difficulty && <><dt>Difficulty</dt><dd>{difficultyLabels[project.difficulty]}</dd></>}<dt>AI model</dt><dd>{project.ai_model}</dd><dt>Thinking level</dt><dd>{thinkingLabels[project.reasoning_effort] ?? project.reasoning_effort}</dd></dl>
      <h3>Event history</h3>
      <ol className="event-list">{project.events.map(event => <li key={event.sequence}>
        <span className="sequence">{String(event.sequence).padStart(2, '0')}</span>
        <div><span>{event.kind}</span><time dateTime={event.timestamp}>{dateLabel(event.timestamp)}</time>
          {event.project_change && <details className="edit-history"><summary>View project changes</summary><dl>{(Object.keys(event.project_change.current) as (keyof Settings)[]).filter(key => event.project_change!.previous[key] !== event.project_change!.current[key]).map(key => <div key={key}><dt>{({ title: 'Project name', problem: 'Research problem', investigation_type: 'Research type', ai_model: 'AI model', reasoning_effort: 'Thinking level', difficulty: 'Difficulty', show_advanced_outcome_details: 'Advanced Outcome details' })[key]}</dt><dd>Before: {key === 'investigation_type' ? researchTypeLabel(String(event.project_change!.previous[key])) : key === 'difficulty' ? difficultyLabel(event.project_change!.previous[key] as ProjectDifficulty | null) : event.project_change!.previous[key]}<br/>After: {key === 'investigation_type' ? researchTypeLabel(String(event.project_change!.current[key])) : key === 'difficulty' ? difficultyLabel(event.project_change!.current[key] as ProjectDifficulty | null) : event.project_change!.current[key]}</dd></div>)}</dl></details>}
          {event.stage_change && <p>Manually tracked: {stageLabels[event.stage_change.previous]} → {stageLabels[event.stage_change.stage]}</p>}
          {event.order && <details><summary>Saved order</summary><ol>{event.order.map(id => <li key={id}>{byId.get(id)?.title ?? id}</li>)}</ol></details>}
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

function App() {
  const [openedView, setOpenedView] = useState<ProjectView | null>(null);
  const [location, setLocation] = useState(() => window.location.pathname + window.location.search);
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
  return <><main className={url.pathname === '/' ? 'home-page' : 'workspace-page'}>
    {url.pathname === '/' ? <Home initialPath={lastPath} onOpen={view => {
      setOpenedView(view); setLastPath(view.path); window.localStorage.setItem('sigma.currentProject', view.path); navigate(projectUrl(view.path));
    }}/> : url.pathname === '/project' ? <ProjectScreen key={location}
      initialView={openedView?.path === url.searchParams.get('path') ? openedView : undefined} path={url.searchParams.get('path') ?? ''} onClose={closeProject} goHome={goHome}/>
      : <><Header goHome={goHome}/><h1>Page not found</h1><a href="/" onClick={goHome}>Return Home</a></>}
  </main><FloatingTooltip/></>;
}

type CloudStatus = { mock_auth?: boolean; mock_identity?: boolean; sponsored_test_mode?: boolean; target?: 'local' | 'hosted'; enabled: boolean; ready: boolean; authenticated: boolean; user: { email: string; role: string } | null; account?: { identity: { email: string; verified: boolean }; access: { status: string; role: string }; workspace: { available: boolean; id: string | null }; model_access: { mode: string; connection: string }; sponsorship: { eligible: boolean; forced?: boolean }; invitation_welcome_pending?: boolean; invitation_status?: string | null } | null; admin_contact_email: string | null; local_setup_missing?: string[] };
type CloudGrant = { kind: string; value: string; role: string; active: number; updated_at: number; allowance_usd: number | null; effective_allowance_usd: number | null };
type CloudAccountSession = { email: string; role: string; authorized: boolean; status: string; expires_at: number | null; allowance_usd: number | null; spending?: { estimated_usage_usd: number; held_usd: number; reserved_and_estimated_usd: number; remaining_usd: number | null; reload_eligible?: boolean } };
type CloudFunding = { target: 'local' | 'hosted'; authenticationEnabled: boolean; googleAccount: string | null; budget: CloudResearchBudget | null; loading: boolean; error: string | null; authorized: boolean; sponsorshipEligible: boolean; sponsorshipUnlimited: boolean; provider: { status: string; guidance: string } | null; providerLoading: boolean; providerError: string | null; retryProvider: () => Promise<void>; selectedConnection: 'personal' | 'sponsored'; forcedSponsored?: boolean; simulatedSponsored?: boolean; disconnectMockSponsored?: () => Promise<void>; selectConnection: (mode: 'personal' | 'sponsored') => Promise<void>; connectionError: string | null; selectingConnection: boolean };
type CloudIdentityState = CloudStatus & { deniedIdentityAvailable: boolean; deniedInvitationStatus: string | null; funding: CloudFunding; openAccessManagement: () => void };
const CloudIdentityContext = createContext<CloudIdentityState | null>(null);
function useCloudIdentity() { return useContext(CloudIdentityContext); }
function cloudFundingFor(cloud: CloudIdentityState | null): CloudFunding | undefined {
  return cloud?.funding;
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
    <section className="cloud-demo-intro"><p className="cloud-auth-kicker">Public read-only preview</p><h1>Explore a SIGMA research project</h1><p>Inspect a curated saved project, its strategies, research sessions, outcomes, computational evidence and report exports. This shared Demo does not create a workspace or run agents.</p></section>
    {error && <section className="cloud-demo-state" role="alert"><h2>Demo unavailable</h2><p>{error}</p></section>}
    {!audit && !error && <p className="cloud-demo-state" role="status">Loading saved Demo data…</p>}
    {audit && project && <>
      <section className="cloud-demo-project"><div><p className="cloud-auth-kicker">{researchTypeLabel(project.investigation_type)} · {difficultyLabel(project.difficulty)}</p><h2>{project.title}</h2><div className="cloud-demo-markdown"><RenderedMarkdown body={project.problem}/></div></div><button className="cloud-demo-export" onClick={() => setExportOpen(true)}>Export project</button></section>
      <section className="cloud-demo-section"><h2>Strategies <span>{project.strategies.length}</span></h2><div className="cloud-demo-grid">{project.strategies.map(strategy => <details className="cloud-demo-card" key={strategy.id} open><summary><span>{strategy.title}</span><small>{strategy.stage} · {strategy.author_kind}</small></summary><p>{strategy.summary}</p><div className="cloud-demo-markdown"><RenderedMarkdown body={strategy.approach}/></div></details>)}</div></section>
      <section className="cloud-demo-section"><h2>Research sessions <span>{audit.research_sessions.length}</span></h2>{audit.research_sessions.map(session => <details className="cloud-demo-card cloud-demo-session" key={session.id}><summary><span>Session #{session.session_number}: {session.strategy_title}</span><small>{session.status} · {session.started_at?.slice(0, 10)}</small></summary><div className="cloud-demo-columns"><div><h3>Outcome</h3><p>{session.outcome?.solution_review?.claim}</p><p>{session.outcome?.solution_review?.argument_summary}</p><h3>Strategy assessment</h3>{session.strategy_assessments?.map((item: any) => <p key={item.strategy_id}>{item.assessment}: {item.rationale}</p>)}</div><div><h3>Saved research artifacts</h3>{session.artifacts?.map((artifact: any) => <article className="cloud-demo-evidence" key={artifact.id}><strong>{artifact.claim}</strong><p>{artifact.method}</p><small>Evidence status: {artifact.evidence_status}</small><p>{artifact.skeptic_response}</p>{artifact.computational_evidence && <details><summary>Inspect saved computation</summary><p>{artifact.computational_evidence.interpretation}</p><pre>{artifact.computational_evidence.source}{'\n'}{artifact.computational_evidence.stdout}</pre>{artifact.computational_evidence.files?.map((file: any) => <details key={file.filename}><summary>Captured artifact: {file.filename}</summary><pre>{file.content}</pre><small>SHA-256: {file.sha256}</small></details>)}</details>}</article>)}</div></div></details>)}</section>
      <section className="cloud-demo-section"><h2>Saved analysis <span>{audit.agentic_runs.length}</span></h2>{audit.agentic_runs.map(run => <details className="cloud-demo-card" key={run.run_id}><summary><span>Research run · {run.status}</span><small>{run.started_at?.slice(0, 10)}</small></summary><p>{run.timeline?.map((entry: any) => entry.message).join(' ')}</p>{run.steps?.map((step: any, index: number) => <article className="cloud-demo-evidence" key={index}><strong>{step.output?.title}</strong><p>{step.output?.approach}</p><small>{step.output?.evidence_boundary}</small></article>)}</details>)}</section>
      <footer className="cloud-demo-footer"><p>Read-only curated data · exports are generated from this saved snapshot</p><button className="cloud-demo-export" onClick={() => setExportOpen(true)}>Export Project Audit or Research Report</button></footer>
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
  const projectReturn = window.location.pathname === '/project' && currentProjectPath
    ? `/api/cloud-auth/login?${new URLSearchParams({ return_to: `/project?path=${currentProjectPath}&resume_play=1` })}`
    : '/api/cloud-auth/login';
  useEffect(() => {
    setInvitationRecorded(invitationRequestOpen);
  }, [cloud?.deniedInvitationStatus, authenticatedGuest, invitationStatus]);
  useEffect(() => {
    const inviteIntent = new URLSearchParams(window.location.search).get('invite') === '1';
    if (canRequestInvitation && deniedIdentityAvailable && !inviteIntent && dialog.current && !dialog.current.open) dialog.current.showModal();
    if (!invitationIdentity && dialog.current?.open) dialog.current.close();
  }, [canRequestInvitation, invitationIdentity]);
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
    setError('');
    try {
      let currentProjectPath = window.location.pathname === '/project'
        ? new URLSearchParams(window.location.search).get('path')
        : null;
      let destination = '/';
      if (currentProjectPath && !authenticatedGuest) {
        const copied = await fetch('/api/projects/guest-copy', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: currentProjectPath }),
        });
        if (!copied.ok) throw await cloudFailure(copied, 'The project could not be kept open after sign-out.');
        const result = await copied.json() as { path: string };
        destination = projectUrl(result.path);
        currentProjectPath = result.path;
      } else if (currentProjectPath) {
        destination = projectUrl(currentProjectPath);
      }
      const response = await fetch('/api/cloud-auth/logout', { method: 'POST', credentials: 'same-origin' });
      if (!response.ok) throw new Error('Google sign-out could not be completed.');
      // Signing out is not a first visit. Keep the post-logout guest view
      // quiet for this tab instead of presenting its introductory welcome.
      window.sessionStorage.setItem('sigma.guestWelcomeDismissed', 'true');
      if (currentProjectPath) window.localStorage.setItem('sigma.currentProject', currentProjectPath);
      window.location.assign(destination);
    } catch (cause) {
      const message = errorMessage(cause);
      setError(message);
      reportRequestFailure(message);
    }
  }
  return <>
    {cloud?.enabled && cloud.authenticated
      ? <button type="button" className="project-google-signin" onClick={() => void signOut()} aria-label="Sign out of Google" title={signedInAccountTooltip} data-tooltip={signedInAccountTooltip}><span className="connection-dot connection-connected" aria-hidden="true"/>Sign out of Google</button>
      : <>
        <a className="project-google-signin" href={projectReturn}><span className="connection-dot" aria-hidden="true"/>Sign in with Google</a>
        {canRequestInvitation && !inviteInHeader && <button type="button" className="project-google-signin project-invite-me" aria-haspopup="dialog" aria-controls="google-invitation-dialog" onClick={() => dialog.current?.showModal()}>Invite me!</button>}
      </>}
    {(!cloud?.authenticated || authenticatedGuest) && <dialog id="google-invitation-dialog" ref={dialog} className="google-account-dialog google-invitation-dialog" aria-labelledby="google-invitation-heading" onCancel={event => { if (deniedIdentityAvailable) event.preventDefault(); }}>
      <div className="privacy-notice-heading google-invitation-heading"><h2 id="google-invitation-heading">Request an invitation</h2><button type="button" className="privacy-close-button" onClick={() => dialog.current?.close()}>Close</button></div>
      {(deniedIdentityAvailable || authenticatedGuest)
        ? <p>We couldn’t find an active SIGMA invitation for this Google account. You can request access here.</p>
        : <p>Sign in with Google so SIGMA can verify your account before recording an invitation request.</p>}
      {(deniedIdentityAvailable || authenticatedGuest)
        ? invitationRecorded
          ? <p role="status">Your invitation request is recorded and awaiting administrator review.</p>
          : <InvitationRequestControls error={error} onError={setError} onRecorded={() => { setInvitationRecorded(true); if (authenticatedGuest) window.dispatchEvent(new Event('sigma-cloud-auth-refresh')); window.dispatchEvent(new Event('sigma-invitation-recorded')); }}/>
        : <a className="cloud-text-button google-invitation-signin" href="/api/cloud-auth/login?invite=1">Sign in with Google</a>}
      {error && !deniedIdentityAvailable && <p role="alert">{error}</p>}
      {deniedIdentityAvailable && !authenticatedGuest && <a className="cloud-text-button google-invitation-signin" href={projectReturn}>Use another Google account</a>}
      <footer className="about-dialog-footer google-invitation-footer"><nav className="about-legal-links" aria-label="Legal information"><a className="about-privacy-link" href={privacyNoticeHref('invitation')}>Privacy Notice</a></nav></footer>
    </dialog>}
  </>;
}

function HomeInvitationAction() {
  const cloud = useCloudIdentity();
  const [recorded, setRecorded] = useState(false);
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
  if (!cloud?.enabled || !uninvited
    || hasOpenInvitationRequest(invitationStatus) || recorded) return null;
  return <button type="button" className="project-google-signin project-invite-me" aria-haspopup="dialog" aria-controls="google-invitation-dialog" onClick={() => window.dispatchEvent(new Event('sigma-open-invitation'))}>Invite me!</button>;
}

function ReloadMeAction({ connectionPill = false }: { connectionPill?: boolean }) {
  const cloud = useCloudIdentity();
  const [state, setState] = useState<'idle' | 'sending' | 'requested' | 'error'>('idle');
  const budget = cloud?.funding.budget;
  if (!cloud?.authenticated || cloud.user?.role === 'admin' || !cloud.funding.sponsorshipEligible || !budget || budget.remaining_usd >= 0.05) return null;
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

function InvitationRequestControls({ error, onError, onRecorded }: { error: string; onError: (error: string) => void; onRecorded: () => void }) {
  const [busy, setBusy] = useState(false);
  async function requestInvitation() {
    setBusy(true); onError('');
    try {
      const response = await fetch('/api/cloud-auth/invitation-request', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      if (!response.ok) throw await cloudFailure(response, 'Your invitation request could not be sent.');
      onRecorded();
    } catch (cause) { onError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <div className="google-invitation-actions">
    {error
      ? <p role="alert">{error} <button type="button" className="cloud-text-button google-invitation-retry" aria-busy={busy} disabled={busy} onClick={() => void requestInvitation()}>{busy ? 'Sending…' : 'Try again'}</button></p>
      : <button type="button" className="cloud-text-button" aria-busy={busy} disabled={busy} onClick={() => void requestInvitation()}>{busy ? 'Sending…' : 'Invite me'}</button>}
  </div>;
}

function allowanceInput(value: number | null) { return value === null ? '' : value.toFixed(2); }
type CloudInvitationRequest = { subject: string; email: string; requested_at: number; status: string; request_type?: 'invitation' | 'reload' };
type CloudFeedbackRequest = { id: string; account_email: string | null; contact_email: string | null; message: string; submitted_at: number; status: string };
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
  onUpdateFeedback: (request: CloudFeedbackRequest, status: 'reviewed' | 'closed') => Promise<void>;
  onRemoveFeedback: (request: CloudFeedbackRequest) => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [drafts, setDrafts] = useState<Record<string, { role: string; allowance: string }>>({});
  const [addOpen, setAddOpen] = useState(false);
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
    try { await onSave(updates); setMessage(`Saved ${updates.length} authorization ${updates.length === 1 ? 'update' : 'updates'}.`); }
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
      await onAdd({ kind: 'email', value: item.email, role: 'member', allowance_usd: null });
      await onUpdateInvitation(item, 'reviewed');
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
    <div className="admin-dialog-heading"><h2 id="cloud-access-title">Administrator Settings</h2>{hasDrafts && <button type="button" className="admin-text-action" disabled={busy || !draftsValid} onClick={() => void saveUpdates()}>Save</button>}<button type="button" className="admin-text-action" onClick={requestClose}>Close</button></div>
    <section className="admin-access-panel">
      <p className="admin-access-note">Authorized email and domain rules. Domain allowances apply separately to each person; email rules take precedence.</p>
      <p className="cloud-access-bootstrap">Built-in administrator: {bootstrapAdmin || 'not configured'}</p>
      <details className="admin-collapsible-section admin-invitation-section" open><summary><h3>Invitation/reload requests</h3></summary>
      {visibleInvitationRequests.length ? <div className="admin-table-scroll admin-invitation-scroll"><table className="admin-grants-table admin-invitation-table"><colgroup><col style={{ width: '33.33%' }}/><col style={{ width: '33.33%' }}/><col style={{ width: '33.34%' }}/></colgroup><thead><tr><th scope="col">Verified Google account</th><th scope="col">Requested</th><th scope="col">Actions</th></tr></thead><tbody>{visibleInvitationRequests.map(item => {
        return <tr key={item.subject}><th scope="row">{item.email}{item.request_type === 'reload' && <small>Allowance reload request</small>}</th><td>{new Date(item.requested_at * 1000).toLocaleString()}</td><td><div className="admin-invitation-actions"><button type="button" className="admin-text-action admin-remove" disabled={busy} onClick={() => void addInvitation(item)}>Add</button><button type="button" className="admin-text-action admin-remove" disabled={busy} onClick={() => void removeInvitation(item)}>Remove</button></div></td></tr>;
      })}</tbody></table></div> : <p className="cloud-access-bootstrap">No invitation requests.</p>}
      </details>
      <details className="admin-collapsible-section admin-feedback-section" open><summary><h3>Product feedback</h3></summary>
      {feedbackRequests.length ? <div className="admin-table-scroll admin-feedback-scroll"><table className="admin-grants-table admin-feedback-table"><colgroup><col style={{ width: '33%' }}/><col style={{ width: '22%' }}/><col style={{ width: '15%' }}/><col style={{ width: '9%' }}/><col style={{ width: '21%' }}/></colgroup><thead><tr><th scope="col">Feedback</th><th scope="col">Google account</th><th scope="col">Submitted</th><th scope="col">Status</th><th scope="col">Actions</th></tr></thead><tbody>{feedbackRequests.map(item => <tr key={item.id}><th scope="row" className="admin-feedback-message">{item.message}</th><td className="admin-feedback-account">{item.account_email || 'Not signed in'}</td><td>{new Date(item.submitted_at * 1000).toLocaleString()}</td><td>{item.status}</td><td><div className="admin-feedback-actions">{item.status !== 'closed' && <><button type="button" className="admin-text-action" disabled={busy || item.status === 'reviewed'} onClick={() => void onUpdateFeedback(item, 'reviewed')}>Mark reviewed</button><button type="button" className="admin-text-action admin-remove" disabled={busy} onClick={() => void onUpdateFeedback(item, 'closed')}>Close</button></>}<button type="button" className="admin-text-action admin-remove" disabled={busy} onClick={() => void onRemoveFeedback(item)}>Remove</button></div></td></tr>)}</tbody></table></div> : <p className="cloud-access-bootstrap">No product feedback.</p>}
      </details>
      <details className="admin-collapsible-section admin-authorized-users-section" open><summary><h3>Authorized users</h3></summary>
      <div className="admin-table-scroll admin-authorized-table-scroll"><table className="admin-grants-table admin-authorized-table"><colgroup><col style={{ width: '35%' }}/><col style={{ width: '14%' }}/><col style={{ width: '32%' }}/><col style={{ width: '19%' }}/></colgroup><thead><tr><th scope="col">Email / Domain</th><th scope="col">Role</th><th scope="col" className="admin-allowance-heading">Sponsorship allowance</th><th scope="col">Actions</th></tr></thead><tbody>
        {ordered.map(grant => {
          const key = `${grant.kind}:${grant.value}`; const draft = drafts[key] ?? { role: grant.role, allowance: allowanceInput(grant.allowance_usd) };
          const isBootstrap = grant.kind === 'email' && grant.value.toLowerCase() === bootstrapAdmin.toLowerCase();
          const account = grant.kind === 'email' ? sessions.find(item => item.email.toLowerCase() === grant.value.toLowerCase()) : undefined;
          const reloadable = !!account && grant.active === 1 && grant.role === 'member'
            && !hasDrafts && (account.spending?.reload_eligible ?? (account.spending?.reserved_and_estimated_usd ?? 0) > 0);
          return <tr key={key} className={grant.active ? '' : 'is-revoked'}>
            <th scope="row"><span className="admin-entry-value">{grant.value}</span><small>{grant.kind === 'email' ? 'Email' : 'Domain'}{grant.active ? '' : ' · Removed'}</small></th>
            <td>{grant.kind === 'domain' ? <span>Member</span> : <select aria-label={`Role for ${grant.value}`} value={draft.role} disabled={!grant.active || isBootstrap || busy} onChange={event => setDrafts(value => ({ ...value, [key]: { ...draft, role: event.target.value } }))}><option value="member">Member</option><option value="admin">Admin</option></select>}</td>
            <td className="admin-allowance-cell">{draft.role === 'admin' ? <span>Unlimited</span> : <><label className="admin-allowance-input"><span className="sr-only">Sponsorship allowance for {grant.value}</span><span aria-hidden="true">$</span><input type="text" inputMode="decimal" value={draft.allowance} disabled={!grant.active || busy} aria-invalid={!validation(draft.allowance)} aria-describedby={`allowance-${grant.kind}-${grant.value}`} onChange={event => setDrafts(value => ({ ...value, [key]: { ...draft, allowance: event.target.value } }))}/></label><small id={`allowance-${grant.kind}-${grant.value}`}>{validation(draft.allowance) ? `Effective ${currency(grant.effective_allowance_usd)}` : 'Enter $0.01 to $15.00'}</small></>}</td>
            <td><div className="admin-authorized-actions">{reloadable && <button type="button" className="admin-text-action admin-remove" disabled={busy} onClick={() => void reload(grant)}>Reload</button>}{grant.active === 1 && !isBootstrap && <button ref={element => { if (element) removeButtons.current.set(key, element); else removeButtons.current.delete(key); }} type="button" className="admin-text-action admin-remove" aria-expanded={confirmRemoveKey === key} disabled={busy} onClick={() => setConfirmRemoveKey(current => current === key ? '' : key)}>Remove</button>}{isBootstrap && <span className="admin-protected-entry">Protected</span>}</div></td>
          </tr>;
        })}
        {!ordered.length && <tr><td colSpan={4} className="admin-empty-row">No authorization entries yet.</td></tr>}
        <tr className="admin-add-row"><td/><td/><td/><td><button ref={addButton} type="button" className="admin-text-action admin-remove" aria-expanded={addOpen} onClick={() => setAddOpen(true)}>New</button></td></tr>
      </tbody></table></div></details>
      {hasDrafts && <div className="admin-save-row"><p>{draftsValid ? `${changed.length} unsaved change${changed.length === 1 ? '' : 's'}.` : 'Correct invalid allowance values before saving.'}</p></div>}
      {(message || error) && <p role={error || message.includes('could not') ? 'alert' : 'status'} className="admin-feedback">{error || message}</p>}
      <details className="admin-collapsible-section admin-account-usage-section" open><summary><h3>Account usage</h3></summary>
      {sessions.length ? <div className="admin-table-scroll admin-account-usage-scroll"><table className="admin-usage-table"><thead><tr><th scope="col">Email</th><th scope="col">Access</th><th scope="col">Allowance</th><th scope="col">Estimated</th><th scope="col">Held</th><th scope="col">Remaining</th></tr></thead><tbody>{sessions.map(session => <tr key={session.email}><th scope="row">{session.email}</th><td>{session.status} · {session.role}</td><td>{session.role === 'admin' ? 'Unlimited' : currency(session.allowance_usd)}</td><td>{currency(session.spending?.estimated_usage_usd)}</td><td>{currency(session.spending?.held_usd)}</td><td>{session.role === 'admin' ? 'Unlimited' : currency(session.spending?.remaining_usd)}</td></tr>)}</tbody></table></div> : <p className="cloud-access-bootstrap">No account usage has been recorded.</p>}
      </details>
    </section>
    {addOpen && createPortal(<div ref={newEntryPanel} className="admin-new-entry-panel" role="group" aria-label="Add authorized user" style={newEntryPosition ? { left: newEntryPosition.left, top: newEntryPosition.top, maxHeight: newEntryPosition.maxHeight } : { left: -10000, top: -10000 }}>
      <div className="admin-new-entry-heading"><h3>New Email or Domain</h3><div className="admin-new-entry-actions"><button type="button" className="admin-text-action" disabled={busy || !newValue.trim() || (newRole !== 'admin' && !validation(newAllowance)) || newValue.includes('@') !== (newKind === 'email')} onClick={() => void addEntry()}>Add</button><button type="button" className="admin-text-action" disabled={busy} onClick={cancelAdd}>Cancel</button></div></div>
      <div className="admin-new-entry-classification"><label>Entry type<select value={newKind} onChange={event => setNewKind(event.target.value as 'email' | 'domain')}><option value="email">Email</option><option value="domain">Domain</option></select></label>{newKind === 'email' && <label>Role<select aria-label="New authorization role" value={newRole} onChange={event => setNewRole(event.target.value as 'member' | 'admin')}><option value="member">Member</option><option value="admin">Admin</option></select></label>}</div>
      <label>{newKind === 'email' ? 'Email address' : 'Domain'}<input aria-label={newKind === 'email' ? 'New email address' : 'New domain'} value={newValue} placeholder={newKind === 'email' ? 'person@example.org' : 'example.org'} onChange={event => setNewValue(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); void addEntry(); } }}/></label>
      {newKind === 'email' && newRole === 'admin' ? <p>Administrator sponsorship: Unlimited</p> : <label>ChatGPT allowance<span className="admin-allowance-input"><span aria-hidden="true">$</span><input aria-label="New ChatGPT allowance" type="text" inputMode="decimal" value={newAllowance} placeholder="Default" aria-invalid={!validation(newAllowance)} onChange={event => setNewAllowance(event.target.value)}/></span><small>Blank uses the configured default</small></label>}
    </div>, dialog.current ?? document.body)}
    {confirmRemoveKey && createPortal(<div ref={removeConfirmation} className="admin-remove-confirm" role="group" aria-label={`Confirm remove access for ${confirmRemoveKey.slice(confirmRemoveKey.indexOf(':') + 1)}`} style={removeConfirmationPosition ? { left: removeConfirmationPosition.left, top: removeConfirmationPosition.top } : { left: -10000, top: -10000 }}>
      <p>Remove access for {confirmRemoveKey.slice(confirmRemoveKey.indexOf(':') + 1)}? Recorded usage will be retained.</p>
      <div className="admin-remove-confirm-actions"><button ref={removeConfirmButton} type="button" className="admin-text-action admin-remove" disabled={busy} onClick={() => { const grant = grants.find(item => `${item.kind}:${item.value}` === confirmRemoveKey); if (grant) void revoke(grant); }}>Confirm</button><button type="button" className="admin-text-action" disabled={busy} onClick={() => setConfirmRemoveKey('')}>Cancel</button></div>
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
            window.location.replace('/api/cloud-auth/login');
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
      const current = await response.json() as { status: string; guidance: string };
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
  async function updateFeedback(item: CloudFeedbackRequest, next: 'reviewed' | 'closed') {
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
      setConnectionError(cause instanceof Error ? cause.message : 'Connection choice could not be saved.');
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
  const context: CloudIdentityState | null = status ? { ...status, deniedIdentityAvailable, deniedInvitationStatus, funding, openAccessManagement: () => { setAccessOpen(true); setFailure(''); void loadGrants().catch(error => setFailure(error instanceof Error ? error.message : 'Access rules could not be loaded.')); } } : null;
  const navigationEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
  const showSponsorWelcome = !!status?.account?.invitation_welcome_pending
    && !welcomeDismissedForPage;
  const showGuestWelcome = !!status?.enabled && !status?.authenticated
    && window.location.pathname !== '/demo'
    && navigationEntry?.type !== 'reload'
    && window.sessionStorage.getItem('sigma.guestWelcomeDismissed') !== 'true'
    && !welcomeDismissedForPage;
  if (!status) return <main className="cloud-auth-shell"><p role="status">Checking access…</p></main>;
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

function InvitationWelcomeDialog({ audience, allowance, allowanceUsed, allowanceLoading, onDismiss }: { audience: 'guest' | 'invited' | 'sponsored'; allowance: number | null; allowanceUsed: number; allowanceLoading: boolean; onDismiss: () => Promise<void> }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [phrase] = useState(() => invitationWelcomePhrases[Math.floor(Math.random() * invitationWelcomePhrases.length)]);
  useEffect(() => {
    if (dialog.current && !dialog.current.open) dialog.current.showModal();
    return () => { if (dialog.current?.open) dialog.current.close(); };
  }, []);
  async function dismiss() {
    if (busy) return;
    setBusy(true); setError('');
    try {
      if (audience !== 'guest') {
        const response = await fetch('/api/cloud-auth/welcome', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        if (!response.ok) throw await cloudFailure(response, 'Your invitation welcome could not be saved.');
      }
      await onDismiss();
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  const heading = audience === 'guest' ? 'Welcome to SIGMA!' : 'You have been invited!';
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
    {audience === 'guest' && <p className="invitation-welcome-intro">Welcome to SIGMA. Explore as a guest without running or saving projects, or request an invitation to become a member. The administrator decides whether to include sponsorship when granting your invitation.</p>}
    {audience === 'sponsored' && <p className="invitation-welcome-intro">SIGMA tracks your sponsored allowance as you use ChatGPT. When you’re ready, you can connect your own ChatGPT account from the Sponsored ChatGPT pill.</p>}
    {audience === 'invited' && <p className="invitation-welcome-intro">Welcome to SIGMA.</p>}
    <p id="invitation-welcome-phrase" className="invitation-welcome-phrase">{phrase}</p>
    {error && <p role="alert">{error}</p>}
    <button type="button" className="google-text-action invitation-welcome-dismiss" disabled={busy} onClick={() => void dismiss()}>{busy ? 'Saving…' : "Let's get started"}</button>
  </dialog>;
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
  return <main className="cloud-auth-shell"><article className="cloud-auth-card privacy-notice-card">
    <div className="privacy-notice-heading"><h1>SIGMA Privacy Notice</h1><button type="button" className="privacy-close-button" onClick={closeNotice}>Close</button></div>
    <p><strong>Prepared October 26, 2026 · Version 1.0</strong></p>
    <p>This notice describes the information SIGMA handles when you use the hosted research workspace.</p>
    <h2>Information SIGMA stores</h2>
    <p>When you sign in with Google, SIGMA receives your stable Google account identifier and verified email address. SIGMA stores them with your access role, whether access is active, assigned workspace, sponsored eligibility, selected model-access mode, and connection status. The hosted sign-in session is represented by a browser cookie and a hashed session token in SIGMA's authentication database. Sessions last up to eight hours. Sign-in flow data expires after five minutes; a temporary denied-sign-in record expires after ten minutes.</p>
    <p>If you request an invitation, SIGMA stores your Google account identifier, verified email, request time, and request/notification/review status. SIGMA sends your verified email and request time through its configured mail service to the SIGMA invitation administrator. If you send product feedback, SIGMA stores your message, submission time, status, and any optional contact email. When signed in, the feedback record is associated with your account identifier and email. Feedback is reviewed in SIGMA's administrator interface; it is not sent to an AI or mail provider. Feedback submissions are limited to five per 24 hours per signed-in account or signed-out browser.</p>
    <p>Your account workspace can contain project titles and questions, project settings, strategies, research prompts and results, evidence, uploaded or imported project files, code and execution output, analyses, reports, and generated papers. SIGMA also stores research-session identifiers and sponsored-service accounting records, including reserved and estimated usage, call status, and token counts when the provider returns them. Usage estimates are used to enforce SIGMA spending limits and may differ from a provider's final bill.</p>
    <h2>How SIGMA uses and shares information</h2>
    <p>SIGMA uses your Google account information to sign you in, apply access rules, and keep your projects in your account workspace. SIGMA administrators can review invitation requests and product feedback, including any optional contact email.</p>
    <p>When you run an AI research feature, SIGMA sends the prompt and the project context required or selected for that action to the configured AI provider. In hosted sponsored mode, requests are sent to OpenAI using SIGMA's server-side service credential. The provider returns a response to SIGMA, and research results are saved in the project. Do not include information in a research request that you do not want sent to the selected provider.</p>
    <p>For an invitation request, SIGMA's configured mail service receives the verified email and request time so it can notify the invitation administrator. Product feedback is not included in invitation email. SIGMA does not send feedback messages to AI providers.</p>
    <h2>Where information is stored and how long it remains</h2>
    <p>In hosted SIGMA, authentication, access, invitation, and feedback records are kept in server-side SQLite databases. Each signed-in account has a separate server-side workspace for its projects and research files. Sponsored usage records are kept in a server-side accounting ledger. The service stores these in its configured persistent storage; the exact physical hosting location and backup schedule are set by the operator.</p>
    <p>SIGMA has no general time-based deletion schedule for account, invitation, feedback, research, or sponsored-usage records. Signing out ends your browser session but does not erase these records. Project controls can remove project data where available, but the hosted service does not currently offer a control that deletes all information associated with an account. If the operator makes backups, copies may remain according to the operator's backup schedule.</p>
    <h2>Cookies and account controls</h2>
    <p>Hosted sign-in uses Secure, HttpOnly, SameSite=Lax cookies for the sign-in flow and session. The session cookie expires after eight hours; the short-lived sign-in and denied-access cookies expire after five and ten minutes respectively. The feedback form uses a random, HttpOnly cookie to apply its five-per-day limit to signed-out browsers. Signing out removes the active session; it does not delete saved projects or records described above. For a request about your account data, contact the SIGMA administrator who invited you.</p>
  </article></main>;
}

function TermsOfServicePage() {
  useEffect(() => { document.title = 'Terms of Service · SIGMA'; }, []);
  return <main className="cloud-auth-shell"><article className="cloud-auth-card privacy-notice-card">
    <div className="privacy-notice-heading"><h1>Terms of Service</h1><button type="button" className="privacy-close-button" onClick={() => { window.location.assign('/'); }}>Close</button></div>
    <p>No terms yet, except just have fun.</p>
  </article></main>;
}


installRequestErrorToasts();
createRoot(document.getElementById('root')!).render(window.location.pathname === '/privacy' ? <PrivacyNoticePage/> : window.location.pathname === '/tos' ? <TermsOfServicePage/> : new URLSearchParams(window.location.search).has('session_log') ? <SessionLogPage/> : <><CloudAuthGate/><RequestErrorToasts/></>);
