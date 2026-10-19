#!/usr/bin/env python3
"""Step 7. Verify the built report in a real (headless) Chromium.

usage: python verify_report.py --work W --html W/report.html [--shots W/shots]
Needs playwright (python) + chromium. Writes W/verify.json and screenshots/print PDF into --shots.
Exit code 1 if any check fails.
"""
import argparse, asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import jload


async def run(o):
    from playwright.async_api import async_playwright
    QF = jload(os.path.join(o.work, 'qual_final.json')); QR = jload(os.path.join(o.work, 'quant_results.json'))
    url = 'file://' + os.path.abspath(o.html); os.makedirs(o.shots, exist_ok=True)
    res, fails = {}, []
    def check(name, cond, detail=''):
        res[name] = dict(ok=bool(cond), detail=detail)
        if not cond: fails.append(name)
    async with async_playwright() as p:
        kw = {}
        if os.path.exists('/opt/pw-browsers/chromium') and not os.environ.get('PLAYWRIGHT_BROWSERS_PATH'):
            kw['executable_path'] = '/opt/pw-browsers/chromium'
        try:
            b = await p.chromium.launch(**kw)
        except Exception:
            b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1280, 'height': 900})
        errs = []
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        pg.on('pageerror', lambda e: errs.append('PAGEERROR ' + str(e)))
        await pg.goto(url); await pg.wait_for_timeout(600)
        check('page_loaded', await pg.evaluate('window.__REPORT_OK__===true'))
        v = await pg.eval_on_selector_all('#verTbl td.vres', 'e=>e.map(x=>x.textContent)')
        check('official_match', v and all(x == '일치' for x in v), f'{v}')
        k0 = await pg.inner_text('#kpis'); n_off = [c['official_n'] for c in QR['official_check'] if c['metric'] == 'overall_satisfaction'][0]
        check('explorer_default_n', f'{n_off:,}건' in k0, k0.replace('\n', ' ')[:160])
        await pg.click('#fBasis button[data-v=person]'); k1 = await pg.inner_text('#kpis')
        check('basis_person_changes_kpi', k1 != k0 or QR['split_units']['units'] == 0)
        await pg.click('#fReset')
        years = await pg.eval_on_selector_all('#fYear option', 'e=>e.map(x=>x.value).filter(Boolean)')
        if years:
            await pg.select_option('#fYear', years[-1]); sc = await pg.inner_text('#scopeLine')
            check('year_filter_scope', years[-1] in sc, sc[:120])
        await pg.select_option('#fMetric', '6'); check('difficulty_warning', len((await pg.inner_text('#diffWarn')).strip()) > 0)
        await pg.click('#fReset')
        await pg.select_option('#fAxis', 'cmp'); bars = await pg.eval_on_selector_all('#barChart g.bar', 'e=>e.length')
        check('cmp_axis_bars', bars >= 2, f'{bars}')
        await pg.click('#fReset')
        rows = await pg.eval_on_selector_all('#eduTbl tbody tr', 'e=>e.length')
        n_edus = [c['edus'] for c in QR['official_check'] if c['metric'] == 'overall_satisfaction'][0]
        check('edu_table_rows', rows == n_edus, f'{rows} vs {n_edus}')
        await pg.click('#eduTbl th[data-k=mean]'); await pg.click('#eduTbl tbody tr:first-child'); await pg.wait_for_timeout(200)
        check('edu_drawer', await pg.evaluate("document.querySelector('#drawer').classList.contains('open')"))
        await pg.click('#dClose')
        ql = await pg.inner_text('#qScopeLine')
        check('qual_target_rows', f"원문 {QF['target']['base_rows']}행" in ql, ql[:120])
        if QF['target']['themes']:
            await pg.click('#themeChart g.bar >> nth=0'); qc = await pg.inner_text('#quoteCount')
            check('theme_click_quotes', int(qc.replace('행', '')) > 0, qc)
        await pg.click('#qScope button[data-v=OTHER]'); ql2 = await pg.inner_text('#qScopeLine')
        check('qual_other_rows', f"원문 {QF['other']['base_rows']}행" in ql2, ql2[:120])
        cells = await pg.eval_on_selector_all('#tHeat g.cell', 'e=>e.length')
        check('target_heat_cells', cells > 0, f'{cells}')
        await pg.click('#tHeat g.cell >> nth=0'); await pg.wait_for_timeout(150)
        check('cell_drawer', 'open' in (await pg.get_attribute('#drawer', 'class') or '')); await pg.click('#dClose')
        if await pg.is_visible('#sensBtn'):
            h0 = await pg.inner_text('#tScopeLine'); await pg.click('#sensBtn'); h1 = await pg.inner_text('#tScopeLine')
            check('sensitivity_toggle', h0 != h1); await pg.click('#tSens button[data-v=in]')
        miss = await pg.evaluate('''()=>{const Q=new Set(DATA.qual.map(q=>q.id)),R=new Set(DATA.resp.map(r=>r[0]));let m=[];
          document.querySelectorAll('.ev[data-q]').forEach(b=>b.dataset.q.split(',').forEach(i=>{if(!Q.has(i))m.push(i)}));
          document.querySelectorAll('.ev[data-r]').forEach(b=>b.dataset.r.split(',').forEach(i=>{if(!R.has(i))m.push(i)}));return m;}''')
        n_chips = await pg.eval_on_selector_all('.ev[data-q],.ev[data-r],.ev[data-edu],.ev[data-theme]', 'e=>e.length')
        check('evidence_resolve', not miss, f'chips={n_chips} missing={miss[:5]}')
        chip = await pg.query_selector('#insights .ev')
        if chip:
            await chip.click(); await pg.wait_for_timeout(150)
            check('insight_chip_drawer', len((await pg.inner_text('#dBody')).strip()) > 0); await pg.click('#dClose')
        await pg.click('#recOpen')
        for sid in ['s0', 's2', 's3', 's4', 's5', 's8']:
            el = await pg.query_selector('#' + sid)
            if el: await el.screenshot(path=os.path.join(o.shots, f'{sid}.png'))
        # --- 인쇄 준비 검사: 인쇄 버튼, 접힌 내용 펼침, 필터·검색창 숨김, 인쇄 후 복원 ---
        check('print_button', await pg.query_selector('#printbtn') is not None)
        await pg.evaluate("()=>{document.querySelectorAll('details').forEach(d=>d.open=false)}")
        await pg.evaluate("()=>dispatchEvent(new Event('beforeprint'))")
        await pg.emulate_media(media='print')
        pr = await pg.evaluate("""()=>{const vis=s=>[...document.querySelectorAll(s)].filter(e=>getComputedStyle(e).display!=='none').length;
          const det=[...document.querySelectorAll('details')];
          return {closed:det.filter(d=>!d.open).length,total:det.length,filters:vis('.filters'),inputs:vis('input,select'),btn:vis('#printbtn,.themebtn'),
                  theme:document.documentElement.dataset.theme||''};}""")
        check('print_expanded', pr['closed'] == 0, f"details {pr['total']}개 중 닫힘 {pr['closed']}")
        check('print_hides_controls', pr['filters'] == 0 and pr['inputs'] == 0 and pr['btn'] == 0, str(pr))
        check('print_light_theme', pr['theme'] == 'light', pr['theme'])
        await pg.pdf(path=os.path.join(o.shots, 'print.pdf'), format='A4', print_background=True,
                     margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'}, prefer_css_page_size=True)
        await pg.emulate_media(media='screen')
        await pg.evaluate("()=>dispatchEvent(new Event('afterprint'))")
        rest = await pg.evaluate("()=>[...document.querySelectorAll('details')].filter(d=>d.open).length")
        check('print_restores_screen', rest == 0, f'인쇄 후 펼침 {rest}개')
        m = await b.new_page(viewport={'width': 390, 'height': 844}); await m.goto(url); await m.wait_for_timeout(300)
        ov = await m.evaluate('document.documentElement.scrollWidth-innerWidth'); check('mobile_no_hscroll', ov <= 0, f'{ov}px')
        d = await b.new_page(viewport={'width': 1280, 'height': 900}, color_scheme='dark'); await d.goto(url); await d.wait_for_timeout(300)
        el = await d.query_selector('#s3'); await el.screenshot(path=os.path.join(o.shots, 'dark_s3.png'))
        check('no_console_errors', not errs, '; '.join(errs[:3]))
        await b.close()
    try:
        import subprocess
        pages = subprocess.run(['pdfinfo', os.path.join(o.shots, 'print.pdf')], capture_output=True, text=True).stdout
        res['print_pages'] = dict(ok=True, detail=[l for l in pages.splitlines() if l.startswith('Pages')])
    except Exception:
        pass
    json.dump(res, open(os.path.join(o.work, 'verify.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k, v in res.items(): print(('PASS ' if v['ok'] else 'FAIL ') + k, v['detail'] if v['detail'] else '')
    print(f'검증: {len(res) - len(fails)}/{len(res)} 통과')
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--work', required=True); ap.add_argument('--html', required=True); ap.add_argument('--shots', default='')
    o = ap.parse_args(); o.shots = o.shots or os.path.join(o.work, 'shots')
    sys.exit(asyncio.run(run(o)))


if __name__ == '__main__':
    main()
