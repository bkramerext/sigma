import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path('docs/evaluations/RESEARCH_EXPERIENCE/evidence'); inv=json.loads((out/'browser-inventory.json').read_text());plans=json.loads(Path(__file__).with_name('continuation_plans.json').read_text());results=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=b.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
 page.route('**/api/**',lambda r:r.fulfill(response=r.fetch(url=r.request.url.replace('http://127.0.0.1:5267','http://127.0.0.1:8067'),headers={**r.request.headers,'origin':'http://127.0.0.1:5173'})))
 requests=[];page.on('request',lambda r:requests.append({'method':r.method,'url':r.url.split('?')[0]}))
 for item in inv['results']:
  slug=item['slug'];title,approach=plans[slug];start=time.monotonic();page.goto('http://127.0.0.1:5267/project?path='+item['copy_path']);page.locator('.strategies-pane').wait_for();page.wait_for_timeout(150)
  if not page.get_by_role('button',name=title,exact=True).count():
   row=page.locator('.strategy-row-disclosure').first
   if item['stock_strategies']:
    if row.get_attribute('aria-expanded')!='true':row.click()
    page.get_by_role('button',name='Fork',exact=True).first.click()
   else:page.get_by_role('button',name='New',exact=True).click()
   form=page.locator('.strategy-form');form.get_by_label('Title',exact=True).fill(title);form.get_by_label('Hypothesis / approach',exact=True).fill(approach);form.get_by_role('button',name='Save',exact=True).click();form.wait_for(state='hidden');page.get_by_role('button',name=title,exact=True).wait_for()
  page.reload();page.get_by_role('button',name=title,exact=True).wait_for()
  disclosure=page.get_by_role('button',name=title,exact=True)
  if disclosure.get_attribute('aria-expanded')!='true':disclosure.click()
  # Capture limits without launching research or altering historical limits.
  page.get_by_role('button',name='Project settings',exact=True).click();dialog=page.get_by_role('dialog');dialog.get_by_role('tab',name='Limits',exact=True).click();limits=dialog.inner_text();values=dialog.locator('input').evaluate_all('(es)=>es.map(e=>({id:e.id,value:e.value}))');dialog.get_by_role('button',name='Cancel',exact=True).click()
  (out/(slug+'-limits.txt')).write_text(limits+'\n'+json.dumps(values))
  # Check manual branch can be excluded and restored.
  branch=page.locator('.strategy-row').filter(has=page.get_by_role('button',name=title,exact=True)).last
  # strategy rows use li; fallback closest strategy container is checked dynamically.
  disable=branch.get_by_role('button',name='Disable',exact=True)
  if disable.count():
   disable.click();branch.get_by_role('button',name='Enable',exact=True).click();toggle=True
  else:toggle=False
  page.get_by_role('button',name='Generate',exact=True).click();page.locator('.agentic-proposal-form, .proposal-form, .generate-strategy').first.wait_for(timeout=1000) if False else None
  page.wait_for_timeout(150);generate_text=page.locator('body').inner_text();(out/(slug+'-generation-preflight.txt')).write_text(generate_text)
  # Only outer Generate is clicked; never submit inference.
  page.get_by_role('button',name='Cancel',exact=True).click()
  page.get_by_role('button',name='LaTeX research paper',exact=True).click();paper=page.get_by_role('dialog');page.wait_for_timeout(200);(out/(slug+'-paper-preflight.txt')).write_text(paper.inner_text());paper.get_by_role('button',name='Cancel',exact=True).click() if paper.get_by_role('button',name='Cancel',exact=True).count() else paper.get_by_role('button',name='Close',exact=True).click()
  (out/(slug+'-continuation.txt')).write_text(page.locator('body').inner_text())
  page.get_by_role('button',name='Export project',exact=True).click();dialog=page.get_by_role('dialog');dialog.get_by_role('radio',name='Text file',exact=True).check();dialog.get_by_role('checkbox').uncheck()
  with page.expect_download() as dl:dialog.get_by_role('button',name='Download',exact=True).click()
  dl.value.save_as(str(out/(slug+'-continuation-report.txt')))
  page.get_by_role('button',name='Back to home',exact=True).click();tab=page.get_by_role('tab',name='Recent',exact=True);tab.wait_for()
  if tab.get_attribute('aria-selected')!='true':tab.click()
  page.wait_for_timeout(200)
  (out/(slug+'-recent.txt')).write_text(page.locator('body').inner_text())
  # Reopen the managed copy from Recent, preserving its identity and branch.
  matches=page.locator('.recent-open').filter(has_text=item['title'])
  recent_reopened=False
  if matches.count():
   matches.first.click();page.get_by_role('button',name=title,exact=True).wait_for();recent_reopened=True
  results.append({'slug':slug,'manual_title':title,'manual_approach':approach,'creation':'fork' if item['stock_strategies'] else 'new','toggle_restored':toggle,'reload_preserved':True,'recent_reopened':recent_reopened,'limits':values,'elapsed_seconds':round(time.monotonic()-start,2)})
  (out/'continuations.json').write_text(json.dumps({'results':results,'requests':requests},indent=2));print(json.dumps(results[-1]),flush=True)
 b.close()
