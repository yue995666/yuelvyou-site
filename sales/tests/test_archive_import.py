"""Public-site privacy, customer-archive merge and interface regression checks."""
import json
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright

SITE = Path(__file__).resolve().parents[1] / 'index.html'


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as playwright:
        b = playwright.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox','--disable-dev-shm-usage'])
        yield b
        b.close()


def page_and_context(browser, mobile=False):
    context = browser.new_context(viewport={'width':390 if mobile else 1365,'height':844 if mobile else 900})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.evaluate("Object.defineProperty(window,'localStorage',{configurable:true,value:{_x:{},getItem(k){return this._x[k]||null},setItem(k,v){this._x[k]=v},removeItem(k){delete this._x[k]}}})")
    page.set_content(SITE.read_text(),wait_until='load')
    return context,page,errors


def test_public_html_remains_private():
    html=SITE.read_text()
    assert 'PRIVATE_VERSION=false' in html
    for secret in ('Yvonne','芳婷','三千','小九','云觞','露娜','客户真实手机号'):
        assert secret not in html
    assert 'fetch(' not in html and '<script src="http' not in html
    assert 'mergePrivateArchive(input)' in html


def test_demo_navigation_and_create_customer(browser):
    context,page,errors=page_and_context(browser)
    try:
        assert '公开体验版' in page.locator('body').inner_text()
        page.get_by_role('button',name='我的客户').click()
        assert page.locator('.listtable tbody tr').count()==3
        page.get_by_role('button',name='新建客户').click()
        page.locator('#newName').fill('演示客户甲')
        page.get_by_role('button',name='创建客户档案').click()
        assert page.evaluate('state.clients.length')==4
        assert not errors, errors
    finally:
        context.close()


def test_import_merges_without_overwriting_and_is_idempotent(browser):
    context,page,errors=page_and_context(browser)
    try:
        page.on('dialog',lambda dialog:dialog.accept())
        # Pre-existing task must survive import.
        page.evaluate("state.tasks.push({id:'task_one',date:'2026-10-22',title:'保留原任务',done:false});save()")
        original=page.evaluate('state.clients.length')
        archive={'source':'个人复盘','clients':[
            {'id':'R64','name':'测试学员甲','sourceType':'个人复盘','sourceRef':'个人复盘第64行','notes':'聊天复盘摘要，非逐字聊天原文','salesState':'用户复盘记载成交·未核验收款','events':[{'date':'2026-10-02','title':'复盘摘要','summary':'沟通了解旅游会员','verified':False}], 'grade':'B','stage':4,'contact':'nurture'},
            {'id':'R75','name':'测试学员乙','sourceType':'个人复盘','sourceRef':'个人复盘第75行','notes':'只了解需求，未成交','events':[], 'grade':'D','stage':2,'contact':'nurture'}
        ]}
        file_data={'name':'历史客户.json','mimeType':'application/json','buffer':json.dumps(archive,ensure_ascii=False).encode()}
        page.get_by_role('button',name='我的客户').click()
        page.locator('.sectiontitle input[type=file]').set_input_files(file_data)
        assert page.evaluate('state.clients.length')==original+2
        assert page.evaluate('state.tasks.length')==1
        assert page.evaluate("state.clients.find(c=>c.name==='测试学员甲').events[0].verified") is False
        assert '测试学员甲' in page.locator('body').inner_text()
        assert '复盘摘要不等于完整微信聊天' in page.locator('body').inner_text()
        page.locator('.listtable tbody tr').filter(has_text='测试学员甲').get_by_role('button',name='查看详情').click()
        assert '沟通了解旅游会员' in page.locator('body').inner_text()
        assert '尚未核对微信原始对话' in page.locator('body').inner_text()
        page.get_by_role('button',name='保存档案').click()
        assert page.evaluate("state.clients.find(c=>c.name==='测试学员甲').confirmed") is True
        page.get_by_role('button',name='我的客户').click()
        page.locator('.sectiontitle input[type=file]').set_input_files(file_data)
        assert page.evaluate('state.clients.length')==original+2
        assert page.evaluate("state.clients.find(c=>c.name==='测试学员甲').confirmed") is True
        assert page.evaluate('state.tasks[0].title')=='保留原任务'
        assert not errors, errors
    finally:
        context.close()


def test_malformed_archive_rejected_and_mobile_menu(browser):
    context,page,errors=page_and_context(browser,mobile=True)
    try:
        page.on('dialog',lambda dialog:dialog.dismiss())
        page.get_by_role('button',name='菜单').click()
        assert page.locator('.sidebar.open').count()==1
        page.locator('.sidebar button[onclick="go(\'clients\')"]').click()
        original=page.evaluate('state.clients.length')
        page.locator('.sectiontitle input[type=file]').set_input_files({'name':'broken.json','mimeType':'application/json','buffer':b'{"clients":"oops"}'})
        assert page.evaluate('state.clients.length')==original
        assert not errors, errors
    finally:
        context.close()


def test_chat_refusal_and_followup_regression(browser):
    context,page,errors=page_and_context(browser)
    try:
        page.locator('.sidebar button[onclick="go(\'chat\')"]').click()
        page.locator('#chatClient').select_option(index=1)
        page.locator('#chatRaw').fill('客户：我现在暂时不想做副业，先别推荐了。\n我：好的，理解。')
        page.get_by_role('button',name='分析并生成回复').click()
        assert '应停止相应营销' in page.locator('#chatResults').inner_text()
        assert page.locator('#setNoPromo').is_checked()
        page.get_by_role('button',name='确认后保存到客户档案').click()
        assert page.evaluate('state.clients[0].noPromoTypes.includes("旅游推广")')
        page.get_by_role('button',name='跟进计划').click()
        page.get_by_role('button',name='添加任务').click()
        page.locator('#taskTitle').fill('仅处理必要售后问题')
        page.get_by_role('button',name='保存跟进任务').click()
        assert '仅处理必要售后问题' in page.locator('body').inner_text()
        page.get_by_role('button',name='完成跟进').click()
        page.locator('#completeText').fill('已完成，无进一步营销')
        page.get_by_role('button',name='保存结果并完成').click()
        assert page.evaluate('state.tasks[0].done')
        assert not errors, errors
    finally:
        context.close()