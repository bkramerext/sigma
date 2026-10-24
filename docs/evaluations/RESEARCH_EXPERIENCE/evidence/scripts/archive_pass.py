import json
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path('docs/evaluations/RESEARCH_EXPERIENCE/evidence');raw=Path('docs/evaluations/fixtures/t17-8-answer-free/live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json');archive=json.loads(raw.read_text());dest=Path('/tmp/sigma-research-experience-blue/projects/maximum-regions-archived.sigma');dest.mkdir(exist_ok=True);(dest/'project.json').write_text(json.dumps(archive['project']));sd=dest/'research-sessions';sd.mkdir(exist_ok=True)
for session in archive['research_sessions']:
 session['project_path']=str(dest.resolve());(sd/(session['id']+'.json')).write_text(json.dumps(session))
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True);page=b.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
 page.route('**/api/**',lambda r:r.fulfill(response=r.fetch(url=r.request.url.replace('http://127.0.0.1:5267','http://127.0.0.1:8067'),headers={**r.request.headers,'origin':'http://127.0.0.1:5173'})))
 page.goto('http://127.0.0.1:5267/');page.get_by_role('button',name='Open',exact=True).click();dialog=page.get_by_role('dialog',name='Open Project');dialog.get_by_label('Project directory').fill(str(dest));dialog.get_by_role('button',name='Open Project',exact=True).click();page.locator('li[data-session-id]').wait_for()
 row=page.locator('li[data-session-id]').first;disclosure=row.locator('.session-row-disclosure')
 if disclosure.get_attribute('aria-expanded')!='true':disclosure.click()
 (out/'maximum-regions-archive-initial.txt').write_text(page.locator('body').inner_text())
 for details in row.locator('.outcome-subsection').all():
  if details.get_attribute('open') is None:details.locator(':scope > summary').click()
 for details in row.locator('.research-artifacts details').all():
  if details.get_attribute('open') is None:details.locator(':scope > summary').click()
 (out/'maximum-regions-archive-expanded.txt').write_text(page.locator('body').inner_text())
 row.locator('.outcome-conclusion').scroll_into_view_if_needed();page.screenshot(path=str(out/'maximum-regions-archive-conclusion.png'))
 refs=row.locator('.outcome-conclusion a, .outcome-conclusion button').all(); print('refs',[(r.inner_text(),r.get_attribute('href')) for r in refs])
 # Follow an artifact reference in the visible reasoning.
 links=row.locator('a').filter(has_text='Artifact')
 if links.count():
  links.first.click();(out/'maximum-regions-archive-reference.txt').write_text(page.locator('body').inner_text());page.screenshot(path=str(out/'maximum-regions-archive-reference.png'))
 page.get_by_role('button',name='Export project',exact=True).click();dialog=page.get_by_role('dialog');dialog.get_by_role('radio',name='HTML report',exact=True).check();dialog.get_by_role('checkbox').uncheck()
 with page.expect_download() as dl:dialog.get_by_role('button',name='Download',exact=True).click()
 dl.value.save_as(str(out/'maximum-regions-archive-report.html'))
 page.get_by_role('button',name='LaTeX research paper',exact=True).click();page.wait_for_timeout(200);(out/'maximum-regions-archive-paper-preflight.txt').write_text(page.get_by_role('dialog').inner_text());page.get_by_role('button',name='Close',exact=True).click()
 # Inspect a finding-derived branch before saving a bounded next question.
 row.get_by_role('button',name='Fork strategy from findings',exact=True).click();form=page.locator('.strategy-form');(out/'maximum-regions-archive-fork-prefill.txt').write_text(form.inner_text()+'\nTITLE: '+form.get_by_label('Title',exact=True).input_value()+'\nAPPROACH: '+form.get_by_label('Hypothesis / approach',exact=True).input_value());form.get_by_role('button',name='Cancel',exact=True).click()
 page.set_viewport_size({'width':390,'height':844});row.locator('.outcome-conclusion').scroll_into_view_if_needed();page.screenshot(path=str(out/'maximum-regions-archive-mobile.png'))
 print('archive observed without editing reasoning; source',str(raw));b.close()
