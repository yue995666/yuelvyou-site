"""Smoke + privacy tests for the public static sales app."""
from pathlib import Path
import re
import pytest
from playwright.sync_api import sync_playwright

SITE = Path(__file__).resolve().parents[1] / 'index.html'

@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as playwright:
        b = playwright.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox', '--disable-dev-shm-usage'])
        yield b
        b.close()


def new_page(browser, mobile=False):
    context = browser.new_context(viewport={'width': 390 if mobile else 1365, 'height': 844 if mobile else 900}, device_scale_factor=1)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    # Sandboxed Chromium may block file:// and network navigation.
    # Render the same tested HTML in-memory with a persistent storage shim.
    page.evaluate("Object.defineProperty(window, 'localStorage',{configurable:true,value:{_x:{},getItem(k){return this._x[k]||null},setItem(k,v){this._x[k]=v},removeItem(k){delete this._x[k]}}})")
    page.set_content(SITE.read_text(), wait_until='load')
    return context, page, errors


def test_privacy_of_distributed_html():
    html = SITE.read_text()
    for secret in ['Yvonne', '小九', '黄颖璇', '云觞', '芳婷', '露娜', '用户真实客户', '真实销售复盘']:
        assert secret not in html, secret
    assert 'PRIVATE_VERSION=false' in html
    assert re.search(r'const TEACHER_CASES=\[\{"id":"G01"', html)
    assert 'const INITIAL_DATA=' in html
    assert '规则生成' in html
    assert '公开体验版' in html
    assert '<script src="http' not in html and 'fetch(' not in html


def test_main_flow(browser):
    context, page, errors = new_page(browser)
    try:
        assert page.get_by_text('销售聚宝盆').first.is_visible()
        assert page.get_by_text('公开体验版').first.is_visible()
        assert page.locator('.srow').count() == 3
        page.get_by_role('button', name='我的客户').click()
        assert page.locator('.listtable tbody tr').count() == 3
        page.get_by_role('button', name='新建客户').click()
        page.locator('#newName').fill('演示客户甲')
        page.locator('#newRelation').fill('朋友')
        page.locator('#newNote').fill('对自由行感兴趣，但目前还没有计划。')
        page.get_by_role('button', name='创建客户档案').click()
        assert page.locator('.listtable tbody tr').count() == 4
        assert '演示客户甲' in page.locator('body').inner_text()
        # Recreate document in a new page using the same simulated browser storage.
        storage_copy = page.evaluate('JSON.stringify(localStorage._x)')
        page.close()
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.evaluate("Object.defineProperty(window, 'localStorage',{configurable:true,value:{_x:JSON.parse(" + repr(storage_copy) + "),getItem(k){return this._x[k]||null},setItem(k,v){this._x[k]=v},removeItem(k){delete this._x[k]}}})")
        page.set_content(SITE.read_text(), wait_until='load')
        page.get_by_role('button', name='我的客户').click()
        page.locator('#listSearch').fill('演示客户甲')
        assert page.locator('.listtable tbody tr').count() == 1
        page.locator('.listtable tbody tr button').first.click()
        page.locator('#edJob').fill('设计师')
        page.get_by_role('button', name='保存档案').click()
        assert page.evaluate("state.clients.find(x=>x.name==='演示客户甲').job") == '设计师'
        page.get_by_role('button', name='聊天助手').click()
        page.locator('#chatClient').select_option(label='演示客户甲')
        page.locator('#chatRaw').fill('客户：我现在暂时不想做副业，先别推荐了。\n我：好的，理解。')
        page.get_by_role('button', name='分析并生成回复').click()
        assert '应停止相应营销' in page.locator('#chatResults').inner_text()
        assert page.locator('#setNoPromo').is_checked()
        page.get_by_role('button', name='确认后保存到客户档案').click()
        assert page.evaluate("state.clients.find(x=>x.name==='演示客户甲').noPromoTypes.includes('旅游推广')")
        page.get_by_role('button', name='跟进计划').click()
        page.get_by_role('button', name='添加任务').click()
        page.locator('#taskTitle').fill('仅处理必要售后问题')
        page.get_by_role('button', name='保存跟进任务').click()
        assert '仅处理必要售后问题' in page.locator('body').inner_text()
        page.get_by_role('button', name='完成跟进').click()
        page.locator('#completeText').fill('已完成，无进一步营销')
        page.get_by_role('button', name='保存结果并完成').click()
        assert page.evaluate('state.tasks[0].done')
        assert not errors, errors
    finally:
        context.close()


def test_mobile_and_local_photo_preview(browser):
    context, page, errors = new_page(browser, mobile=True)
    try:
        page.get_by_role('button', name='菜单').click()
        assert page.locator('.sidebar.open').count() == 1
        page.locator('.sidebar button[onclick="go(\'chat\')"]').click()
        assert '截图不会自动识别文字' in page.locator('body').inner_text()
        assert page.locator('body').evaluate('(el)=>el.scrollWidth<=window.innerWidth+2')
        assert not errors, errors
    finally:
        context.close()