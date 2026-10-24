import json,hashlib,time
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path('docs/evaluations/RESEARCH_EXPERIENCE/evidence');inv=json.loads((out/'browser-inventory.json').read_text());root=Path('/tmp/sigma-research-experience-blue/projects');observations={}
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True);page=b.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
 page.route('**/api/**',lambda r:r.fulfill(response=r.fetch(url=r.request.url.replace('http://127.0.0.1:5267','http://127.0.0.1:8067'),headers={**r.request.headers,'origin':'http://127.0.0.1:5173'})))
 # Replace giant stitched screenshots with selective fresh viewport captures.
 for p in out.glob('*.png'):
  if not p.name.startswith('maximum-regions-archive'):p.unlink()
 for slug in ['algorithm-design','arrival-sequel','nonconsecutive-subset-sums','operation-narrow-passage','xenopus-tail-regeneration']:
  item=next(x for x in inv['results'] if x['slug']==slug);page.goto('http://127.0.0.1:5267/project?path='+item['copy_path']);page.locator('.strategies-pane').wait_for();page.wait_for_timeout(100);page.screenshot(path=str(out/(slug+'-desktop.png')))
  page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(out/(slug+'-mobile.png')));page.set_viewport_size({'width':1440,'height':1000})
  if slug=='nonconsecutive-subset-sums':
   row=page.locator('li[data-session-id]').nth(3);dis=row.locator('.session-row-disclosure')
   if dis.get_attribute('aria-expanded')!='true':dis.click()
   prov=row.locator('.outcome-subsection').filter(has=page.locator(':scope > summary',has_text='Provenance')) if False else row.locator('.outcome-subsection').filter(has_text='Metric source inventory')
   if prov.get_attribute('open') is None:prov.locator(':scope > summary').click()
   refs=prov.get_by_role('button').filter(has_text='Session #1');refs.first.click();page.wait_for_timeout(100);observations['prior_source_navigation']={'target_session_expanded':page.locator('li[data-session-id]').first.locator('.session-row-disclosure').get_attribute('aria-expanded'),'scroll_y':page.evaluate('scrollY')}
   first=page.locator('li[data-session-id]').first;ev=first.locator('.outcome-evidence-subsection')
   if ev.get_attribute('open') is None:ev.locator(':scope > summary').click()
   artifact=ev.locator('.research-artifacts > ol > li > details').first
   if artifact.get_attribute('open') is None:artifact.locator(':scope > summary').click()
   artifact.scroll_into_view_if_needed();page.screenshot(path=str(out/'nonconsecutive-artifact.png'))
   # Text reference in conclusion is not an anchor; inspect semantics to distinguish from prior-session links.
   observations['outcome_reference_controls']=first.locator('.session-outcome-inline').evaluate('(el)=>({anchors:el.querySelectorAll("a").length,buttons:Array.from(el.querySelectorAll("button")).map(b=>b.getAttribute("aria-label"))})')
   if row.locator('.session-row-disclosure').get_attribute('aria-expanded')!='true':row.locator('.session-row-disclosure').click()
   status=row.locator('.outcome-subsection').filter(has=page.get_by_text('Status',exact=True))
   if status.get_attribute('open') is None:status.locator(':scope > summary').click()
   row.get_by_role('button',name='Fork strategy from findings',exact=True).click();form=page.locator('.strategy-form');observations['findings_fork_prefill']=form.get_by_label('Hypothesis / approach',exact=True).input_value();form.get_by_role('button',name='Cancel',exact=True).click()
 # Research-limit adjustment on a copy, no session start. Save a conservative 2-call single-cycle plan.
 item=next(x for x in inv['results'] if x['slug']=='counting-constrained-binary-strings');page.goto('http://127.0.0.1:5267/project?path='+item['copy_path']);page.get_by_role('button',name='Project settings',exact=True).click();d=page.get_by_role('dialog');d.get_by_role('tab',name='Limits',exact=True).click();page.locator('#research-rounds').fill('1');page.locator('#research-calls').fill('2');d.get_by_role('button',name='Save',exact=True).click();d.wait_for(state='hidden');page.reload();page.get_by_role('button',name='Project settings',exact=True).click();d=page.get_by_role('dialog');d.get_by_role('tab',name='Limits',exact=True).click();observations['counting_limits_adjustment']={'rounds':page.locator('#research-rounds').input_value(),'calls':page.locator('#research-calls').input_value(),'duration_unit':page.locator('#research-duration-unit').input_value() if page.locator('#research-duration-unit').count() else 'see selects','selects':d.locator('select').evaluate_all('(es)=>es.map(e=>({id:e.id,value:e.value}))')};(out/'counting-adjusted-limits.txt').write_text(d.inner_text());d.get_by_role('button',name='Cancel',exact=True).click()
 # HTML export actually opened in Chrome and inspected, no inference.
 page.goto('file://'+str((out/'maximum-regions-archive-report.html').resolve()));observations['html_report']={'title':page.title(),'text_chars':len(page.locator('body').inner_text()),'contains_formula':'1+n(n+1)/2' in page.locator('body').inner_text(),'contains_candidate':'candidate' in page.locator('body').inner_text().lower()};page.screenshot(path=str(out/'maximum-regions-html.png'))
 b.close()
now={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('samples').rglob('*') if p.is_file()};observations['canonical_sources_unchanged']=now==inv['source_sha256'];observations['live_provider_calls']=0;observations['study_provider_cost_usd']=0
(out/'deep-observations.json').write_text(json.dumps(observations,indent=2));print(json.dumps(observations,indent=2))
