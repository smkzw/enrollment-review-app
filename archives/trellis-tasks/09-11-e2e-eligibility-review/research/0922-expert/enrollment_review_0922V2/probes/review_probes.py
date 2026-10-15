"""0922V2 offline probes. No network, credentials, repository writes or clinical DB.
Source excerpts are manually transcribed from the pinned connector reads.
They are NOT the complete app; dependencies and clinical context are synthetic.
"""
from __future__ import annotations
import json
import pathlib
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS

OUT = pathlib.Path(__file__).resolve().parent.parent
SHA = 'e7f34d0508c05481164cf13569f66ddf64e2e74f'
results = []

def add(id, source, observed, expected, boundary='Synthetic helper/control-flow probe; not full application acceptance'):
    results.append(dict(id=id, source=source, observed=observed, expected_after_fix=expected, boundary=boundary))

# Exact helper body. Deliberately has no global os, matching its source module.
PATH_HELPER = '''def _escape_repo_path(candidate: Path) -> Path:
    resolved = candidate.resolve()
    repo = _repo_root().resolve()
    if repo in resolved.parents or resolved == repo:
        safe = Path(os.environ.get("SCALE_SET_DIR", str(Path.home() / "wp08-scale-sets"))) / candidate.name
        safe.mkdir(parents=True, exist_ok=True)
        print(f"[F07] 拒绝把真实资料写入源码树，已改用源码树外路径: {safe}")
        return safe
    return resolved
'''
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp) / 'repo'
    root.mkdir()
    env = dict(Path=pathlib.Path, _repo_root=lambda: root)
    exec(PATH_HELPER, env)
    try:
        env['_escape_repo_path'](root/'runs'/'dataset')
        observed = 'unexpected success'
    except Exception as e:
        observed = f'{type(e).__name__}: {e}'
    add('P01', 'scripts/build_scale_validation_set.py::_escape_repo_path', observed,
        'Default output redirects without NameError')
    # Inject os only to expose the separate second defect after fixing P01.
    env['os'] = NS(environ={'SCALE_SET_DIR':str(root/'still-tracked')})
    redirected = env['_escape_repo_path'](root/'runs'/'dataset')
    add('P02', 'scripts/build_scale_validation_set.py::_escape_repo_path',
        {'fallback_is_inside_repo':root in redirected.resolve().parents},
        'Reject SCALE_SET_DIR if it resolves inside any source worktree; validate fallback too')

# Exact page counter behavior: pages is filled only for PDFs.
media = [('.pdf', 2), ('.jpg', None), ('.png', None), ('.tiff', None)]
total_pages = 0
for suffix, pages in media:
    if pages:
        total_pages += pages
add('P03', 'scripts/build_scale_validation_set.py::main',
    {'files':4,'reported_total_pages':total_pages,'synthetic_true_images_or_pages':7},
    'Count PDF pages + image pages + TIFF frames, or report unknown instead of omitting them',
    'Counter excerpt; synthetic TIFF has three frames; no actual clinical images processed')

# Exact predicate branch of the existing full selection helper.
SELECT_HELPER = '''def select_identity(*, predicate, usable_records, time_constraint=None, written_content_verified=False):
    policy = predicate.observation_policy
    if policy is not None and policy.mode == "unresolved":
        return [], [], ["observation_selection_unverified"]
    if getattr(predicate, "requires_professional_judgment", False) and not written_content_verified:
        return [], [], ["investigator_judgment_not_deterministic_value"]
    value_records = [item for item in usable_records if item.fact_attribute == "value"]
    fact_ids = _sorted_unique(item.fact_id for item in value_records)
    pair_ids = _sorted_unique(item.pair_id for item in value_records)
    if not fact_ids:
        return [], [], ["no_usable_qualified_pair"]
    if time_constraint is not None:
        date_records = [item for item in usable_records if item.fact_attribute == "date_range"]
        qualified_dates = {item.fact_id for item in date_records}
        if any(fact_id not in qualified_dates for fact_id in fact_ids):
            return [], [], ["event_date_not_qualified_for_selected_value"]
        pair_ids = _sorted_unique([*pair_ids, *(item.pair_id for item in date_records
                                               if item.fact_id in fact_ids)])
    if len(fact_ids) > 1 and (policy is None or policy.mode == "single"):
        return [], [], ["multiple_usable_pairs_without_selection_policy"]
    return fact_ids, pair_ids, []
'''
scope={'_sorted_unique': lambda values: sorted(set(values))}
exec(SELECT_HELPER,scope)
select=scope['select_identity']
pred=NS(observation_policy=NS(mode='single'), requires_professional_judgment=False)

def current_loader_selection(records):
    # Reached only AFTER each pair's rejection reasons are empty; preserve that assumption.
    result={'p1':[]}
    for record in records:
        if record.rejection_reasons:
            continue
        if record.fact_id not in result['p1']:
            result['p1'].append(record.fact_id)
    if not any(result.values()):
        return None
    return {key:sorted(ids) for key,ids in result.items()}

def pair(fid, attr):
    return NS(fact_id=fid,fact_attribute=attr,pair_id=f'{fid}:{attr}',rejection_reasons=[])

for pid, records, temporal in [
    ('P04',[pair('f1','date_range')],True),
    ('P05',[pair('f1','value')],True),
    ('P06',[pair('f1','value'),pair('f2','value')],False),
    ('P07',[pair('f1','value'),pair('f1','date_range')],True),
]:
    ids, pairs, reasons=select(predicate=pred, usable_records=records, time_constraint=object() if temporal else None)
    add(pid, 'eligibility_review_projection.py::_load_binding_predicate_fact_ids vs qualified_binding_selection.py::_select_facts_for_identity',
        dict(loader=current_loader_selection(records), full_selection_ids=ids, full_selection_reasons=reasons),
        'Projection and frozen review share complete operand/date/multiplicity semantics; P07 is a positive control',
        'Selection-layer comparison; synthetic already pair-qualified records. Does not assert a real final clinical misdecision')

# Extracted early dispatch from _evaluate_atomic, stop before value comparison.
DISPATCH = '''def dispatch(predicate, context, fact_ids=None):
    policy = predicate.observation_policy
    if policy is not None and (policy.mode == "unresolved" or fact_ids is None):
        return "observation_selection_unverified"
    fact_type = f"{predicate.subject}.{predicate.attribute}"
    alias_types = context.predicate_fact_type_aliases.get(fact_type)
    if fact_ids is not None:
        matching = [fact for fact in context.facts if fact.fact_id in fact_ids]
    elif alias_types:
        matching = [fact for fact in context.facts if fact.fact_type in alias_types]
    else:
        matching = [fact for fact in context.facts if fact.fact_type == fact_type]
    if not matching:
        return "UNKNOWN"
    return [fact.fact_id for fact in matching]
'''
scope={}
exec(DISPATCH,scope)
rejected=pair('f-rejected','value'); rejected.rejection_reasons=['attribute_match_rejected']
loaded=current_loader_selection([rejected])
context=NS(facts=[NS(fact_id='f-rejected',fact_type='demographics')],
           predicate_fact_type_aliases={'person.age':['demographics']})
pred_without_policy=NS(subject='person',attribute='age',observation_policy=None)
add('P08', 'eligibility_review_projection.py all-rejected→None; expression.py::_evaluate_atomic dispatch',
    {'loader':loaded,'facts_reaching_value_comparison':scope['dispatch'](pred_without_policy,context,loaded)},
    'An explicit all-rejected qualification state must not fall back to category matching',
    'Synthetic condition with no observation_policy. Probe stops at matching, NOT final eligibility decision')
add('P09', 'expression.py::_evaluate_atomic dispatch',
    {'explicit_empty_result':scope['dispatch'](pred_without_policy,context,[])},
    'Keep explicit-empty UNKNOWN behavior; do not reintroduce empty→FALSE',
    'Positive safety control on the dispatch excerpt')

# Exact opencode provider early guard in page_completion_options.
def page_options(provider):
    if provider not in {'omlx','mtplx'}:
        return {}
    return {'local_adapter_branch':'not executed'}
add('P10','app/llm/page_review_transport_options.py::page_completion_options',
    {'opencode_go_options':page_options('opencode-go')},
    'Diagnose the actual application request; do not claim it sends json_object if this adapter does not',
    'Static guard behavior only; no actual HTTP request or provider capability assertion')

# Actual record expression currently collapses missing/empty response identity.
requested='requested-model'
add('P11','app/llm/page_review_harness.py::read_page',
    {'response_missing_recorded_model':None or requested,'response_unexpected_recorded_model':'different-model' or requested},
    'Keep requested/returned/canonical IDs separately; missing is missing, unapproved mismatch cannot be adopted',
    'Expression-level identity probe; no real model called')

# Sibling heuristic does not inspect attributes or observation identity.
a=NS(fact_id='age',asserted_object='subject',locator_ids=['whole-page'],value=51)
b=NS(fact_id='height',asserted_object='subject',locator_ids=['whole-page'],value=170)
is_sibling=(b.fact_id!=a.fact_id and b.asserted_object==a.asserted_object and bool(set(b.locator_ids)&set(a.locator_ids)))
add('P12','app/services/fact_correction_service.py::_same_observation_siblings',
    {'same_page_age_height_marked_siblings':is_sibling},
    'Only show as potentially-related sources until same observation/attribute/time is proven; never bulk-overwrite by this heuristic',
    'Heuristic excerpt; actual current change is preview-only, not a demonstrated mass correction')

# Watcher's unchanged substring-based probe and shell exit path, no network.
for pid, finish in [('P13',None),('P14','length')]:
    body=json.dumps({'choices':[{'finish_reason':finish}]})
    add(pid,'scripts/wp08_muse_spark_watch.sh',
        {'finish_reason':finish,'detected_recovered':'"finish_reason"' in body},
        'Use validated success response and nonempty capability result, not key presence')
proc=subprocess.run(['bash','-c','NSTATE=failed_final; echo "done: normalization=$NSTATE"'],capture_output=True,text=True)
add('P15','scripts/wp08_muse_spark_watch.sh final echo',
    {'normalization':'failed_final','exit_code':proc.returncode},
    'Failure/timeout must return nonzero and structured partial-run status',
    'Only terminal shell lines executed; the original watcher was NOT run')

# Corrected projection response boundary: positive negative controls, then remaining hole.
def projection_acceptance(status, body):
    if status!=200: return 'rejected_http'
    if 'error' in body: return 'rejected_envelope'
    return {'clause_count':len(body['clauses']),'would_return_success':True}
add('P16','scripts/run_scale_validation.py projection checks',
    {'http_503':projection_acceptance(503,{}),'http_200_error':projection_acceptance(200,{'error':{'code':'X'}}),
     'http_200_empty':projection_acceptance(200,{'clauses':[]})},
    'Keep error checks; additionally verify expected rule coverage, scope and actual page dispositions')

for file in ['ui_selection.json']:
    f=OUT/'evidence'/file
    if f.exists():
        add('P17','frontend/src/pages/EligibilityWorkbenchPage.tsx defaultClause',json.loads(f.read_text()),
            'Sort individual issues within a highest-severity group; default selection must be input-order invariant',
            'Node executes transcribed TypeScript function with synthetic supporting types')
code_path=OUT/'evidence'/'tsc_exit_code.txt'
if code_path.exists():
    add('P18','frontend/src/pages/EligibilityWorkbenchPage.tsx::buildEligibilityIssueGroups',
        {'exit_code':int(code_path.read_text().strip()),'diagnostic':(OUT/'evidence'/'tsc_no_unused.txt').read_text().strip(),
         'compiler_used':'TypeScript 5.8.3','repo_declared_compiler':'TypeScript 7.0.2'},
        'Remove unused local or actually use it; run the real npm build with pinned dependencies',
        'Standalone noUnusedLocals compiler check, not full repository build; compiler version differs and is disclosed')

payload={'round':'0922V2','baseline':SHA,'mode':'offline excerpts and synthetic fixtures',
         'credentials_used':False,'original_watch_script_executed':False,'clinical_db_accessed':False,
         'whole_repository_tests_run':False,'count':len(results),'results':results}
(OUT/'probes'/'results.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'count':len(results),'result_file':str(OUT/'probes'/'results.json')},ensure_ascii=False))
