import json,time,hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path('docs/evaluations/RESEARCH_EXPERIENCE/evidence')
slugs=sorted(p.parent.name for p in Path('samples').glob('*/project.json'))
source={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('samples').rglob('*') if p.is_file()}
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=b.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
 page.route('**/api/**',lambda route:route.fulfill(response=route.fetch(url=route.request.url.replace('http://127.0.0.1:5267','http://127.0.0.1:8067'),headers={**route.request.headers,'origin':'http://127.0.0.1:5173'})))
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 results=[]
 for slug in slugs:
  start=time.monotonic();d=json.loads((Path('samples')/slug/'project.json').read_text())
  page.goto('http://127.0.0.1:5267/');tab=page.get_by_role('tab',name='Samples',exact=True)
  if tab.get_attribute('aria-selected')!='true':tab.click()
  button=page.get_by_role('button',name='Open '+d['title'],exact=True);button.wait_for();button.click();page.wait_for_url('**/project?*');page.locator('.strategies-pane').wait_for();page.wait_for_timeout(400)
  path=page.evaluate("new URL(location.href).searchParams.get('path')")
  for disclosure in page.locator('.strategy-row-disclosure').all():
   if disclosure.get_attribute('aria-expanded')!='true':disclosure.click()
  for disclosure in page.locator('.session-row-disclosure').all():
   if disclosure.get_attribute('aria-expanded')!='true':disclosure.click()
  initial=page.locator('body').inner_text()
  (out/(slug+'-workspace.txt')).write_text(initial)
  page.screenshot(path=str(out/(slug+'-desktop.png')),full_page=True)
  session_ids=page.locator('li[data-session-id]').evaluate_all('(els)=>els.map(el=>el.dataset.sessionId)')
  for details in page.locator('.outcome-subsection').all():
   if details.get_attribute('open') is None:details.locator(':scope > summary').click()
  for details in page.locator('.research-artifacts details').all():
   if details.get_attribute('open') is None:details.locator(':scope > summary').click()
  (out/(slug+'-expanded.txt')).write_text(page.locator('body').inner_text())
  if session_ids:page.screenshot(path=str(out/(slug+'-evidence.png')),full_page=True)
  page.get_by_role('button',name='Export project',exact=True).click();dialog=page.get_by_role('dialog',name='Export Project',exact=True)
  dialog.get_by_role('radio',name='Text file',exact=True).check()
  if dialog.get_by_role('checkbox').is_checked():dialog.get_by_role('checkbox').uncheck()
  with page.expect_download() as download:dialog.get_by_role('button',name='Download',exact=True).click()
  download.value.save_as(str(out/(slug+'-report.txt')))
  page.get_by_role('button',name='Project settings',exact=True).click();settings=page.get_by_role('dialog');(out/(slug+'-settings.txt')).write_text(settings.inner_text());settings.get_by_role('button',name='Cancel',exact=True).click()
  dims=[]
  for width,height in [(390,844),(320,700)]:
   page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(100)
   dims.append(page.evaluate('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,bodyWidth:document.body.scrollWidth})'))
  page.screenshot(path=str(out/(slug+'-mobile.png')),full_page=True);page.set_viewport_size({'width':1440,'height':1000})
  result={'slug':slug,'title':d['title'],'copy_path':path,'session_ids':session_ids,'stock_strategies':[s['title'] for s in d['strategies']],'dimensions':dims,'elapsed_seconds':round(time.monotonic()-start,2)};results.append(result);print(json.dumps(result),flush=True)
  (out/'browser-inventory.json').write_text(json.dumps({'revision':'6059d67','browser_version':b.version,'results':results,'page_errors':errors,'source_sha256':source},indent=2))
 b.close()
assert source=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('samples').rglob('*') if p.is_file()}
