"""Offline scripted HTTP transport for Increment 3; tests wiring, NOT reasoning.

No provider network is possible. Responses below are evaluator-authored. The
first RH Investigator sees only the injected claim, not the evaluator oracle.
"""
import asyncio
import importlib.util
import json
import os
from pathlib import Path

import httpx

fixture_path = Path(__file__).resolve().parents[1] / 'tests/research_sessions.py'
spec = importlib.util.spec_from_file_location('session_helpers', fixture_path)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)

GAP = '516c2288-3458-40b2-9e02-87a918c35a3a'
ROOT = 'ccc1045f-479d-4018-b8ed-42a60b94e567'
FAILED = '1cc6ec50-87c0-46f4-b1dd-a82857d74f9e'
ON_TEST = 'Derive the three-phase product of weighted 2 by 2 matrices at cube roots; verify the n=0,1,2 boundary vectors. Do not infer the global recurrence or limit from finite checks.'
OFF_TEST = 'Build the residue and last-bit 6 by 6 transition baseline and check n=0,1,2 boundary vectors before choosing a spectral reduction.'
RH_TEST = 'Separate invariance of a zero set under reflection from pointwise fixation; test the inference on an abstract reflected pair. This is not an RH proof.'

async def handler(request):
    if request.method == 'GET':
        return httpx.Response(200, json={'object': 'list', 'data': [{'id': 'gpt-6.1-sol'}]})
    body = json.loads(request.content)
    context = json.loads(body['input'])
    role = body['text']['format']['name'].removeprefix('research_')
    cycle = context['cycle']
    packet = context.get('approved_continuation', {})
    ids = [s['artifact_id'] for s in packet.get('sources', [])]
    rh = 'Riemann' in context['problem'] or 'RH-SYM' in context.get('strategy', {}).get('approach', '') or 'reflection' in str(context.get('strategy', ''))
    evidence_on = GAP in ids and ROOT in ids
    next_test = RH_TEST if rh else ON_TEST if evidence_on else OFF_TEST
    if role == 'investigator':
        output = helpers.investigation(cycle)
        if rh and not packet:
            # Deliberately reproduce the evaluator injection, not the answer key.
            claim = 'Evaluator-authored RH-SYM candidate: reflection of each zero is also a zero; therefore every zero is fixed by reflection and lies on Re(s)=1/2.'
            notes = 'Candidate inference supplied for adversarial review. No independent derivation or oracle is supplied.'
        else:
            claim = 'Bounded next-test selection only. ' + next_test
            notes = ('Saved cross-strategy root-filter and normalization sources change the selected test to weighted 2 by 2 matrices.' if evidence_on else 'No selected cross-strategy normalization/root-filter transfer is available; retain the residue-state baseline.') if not rh else 'The saved objection motivates a scoped logical follow-up; RH remains unresolved.'
        output.update(claim=claim, method='OFFLINE SCRIPT: '+notes,
                      reasoning_steps=[{'title': 'Scripted next-test selection, not a proof', 'argument': notes, 'epistemic_status': 'conjecture', 'basis_artifact_ids': ids}],
                      claim_is_conditional=True, assumptions=['No new mathematical verification by this script'],
                      evidence_status='Evaluator-authored offline transport; no tools or real model reasoning',
                      open_obligations=[next_test], python_code=None)
    else:
        output = helpers.skeptic(cycle, assessment='revise' if cycle == 1 else 'stop', stop_reason='recoverable_objection' if cycle == 1 else 'no_progress')
        objection = ('Reflection invariance of a set does not entail pointwise fixation. The stated inference lacks that implication; RH is not established.' if rh else
                     'The short recurrence is locally refuted (a5=5, a4+a2=4); a12=128 is a finite count, not a proof of the candidate order-12 recurrence or 1/3 limit. The k squared normalization correction is recorded, not new work.')
        output.update(response='OFFLINE SCRIPT: '+objection, objections=[objection], remaining_obligations=[next_test], next_question=next_test if cycle == 1 else '',
                      objective_status='partial', solution_claim='Only a bounded next-test plan was recorded; no project solution.',
                      argument_summary='Offline control selected a next test. '+objection, reasoning_assessments=[], claim_is_conditional=True,
                      assumptions_reviewed=['Sources are recorded assertions; no independent theorem verification'], proof_obligations=[next_test],
                      unresolved_objections=[objection], verification_status='incomplete', strategy_contribution='productive',
                      contribution_rationale='Scripted plan selection tests evidence wiring only; correctness remains unverified.')
    output['continuation_reviews'] = [
        {'artifact_id': source, 'treatment': 'negative_constraint' if source == FAILED else 'method_to_test', 'uptake': 'changed_plan' if source in {GAP, ROOT} and evidence_on else 'considered',
         'rationale': 'Offline script selected the weighted matrix test from these exact cross-strategy IDs.' if source in {GAP, ROOT} and evidence_on else 'Offline script retained the source as a scope constraint; it does not certify the claim.',
         'next_test': next_test}
        for source in ids
    ]
    capture = Path(os.environ['SIGMA_CONTINUATION_CAPTURE'])
    with capture.open('a') as stream:
        stream.write(json.dumps({'role': role, 'cycle': cycle, 'source_ids': ids, 'request_body': body,
                                 'response': output, 'scripted_choice': next_test, 'transport': 'httpx.MockTransport; no network'})+'\n')
    if 'STOP/RELOAD CONTROL' in str(context.get('strategy', '')):
        await asyncio.sleep(1)
    return httpx.Response(200, json={'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': json.dumps(output)}]}],
                                  'usage': {'input_tokens': 100, 'input_tokens_details': {'cached_tokens': 0}, 'output_tokens': 300}})

RealClient = httpx.AsyncClient
class OfflineClient(RealClient):
    def __init__(self, *args, **kwargs):
        kwargs['transport'] = httpx.MockTransport(handler)
        super().__init__(*args, **kwargs)
httpx.AsyncClient = OfflineClient
from sigma.api import app
