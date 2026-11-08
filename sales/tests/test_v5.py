"""V5 browser flows. Cloud HTTP is simulated, never represented as production proof."""
import json
import pytest
from test_public_site import browser, new_page


def open_chat(page, text):
    page.evaluate("go('chat')")
    page.locator('#chatClient').select_option(index=1)
    page.locator('#chatRaw').fill(text)
    page.get_by_role('button', name='分析并生成回复').click()


@pytest.mark.parametrize('text,grade',[
    ('客户：帮我下单','A'),('客户：多少钱','B'),('客户：想了解一下','C'),
    ('我：我要买\n客户：你好','D'),('客户：先别推荐了','E')])
def test_evidence_grades(browser,text,grade):
    context,page,errors=new_page(browser,mobile=True)
    try:
        open_chat(page,text)
        assert grade+' 级建议' in page.locator('#chatResults').inner_text()
        assert '本地规则演示' in page.locator('#chatResults').inner_text()
        assert page.locator('body').evaluate('(e)=>e.scrollWidth<=innerWidth+2')
        assert page.locator('#bottomNav').is_visible()
        page.screenshot(path='/tmp/sales-v5-mobile-'+grade+'.png', full_page=True)
        if grade=='D':
            assert page.locator('.evidence').count()==0
        else:
            assert page.locator('.evidence').first.inner_text() in text
        assert not errors
    finally:
        context.close()


def test_refusal_stays_after_new_interest(browser):
    context,page,errors=new_page(browser)
    try:
        open_chat(page,'客户：停止联系')
        page.locator('#setNoPromo').uncheck()
        page.get_by_role('button',name='确认后保存到客户档案').click()
        assert page.evaluate('state.clients[0].contact')=='stop'
        open_chat(page,'客户：多少钱')
        page.get_by_role('button',name='确认后保存到客户档案').click()
        assert page.evaluate('state.clients[0].grade')=='E'
        assert page.evaluate('state.clients[0].events[0].verified') is False
        assert not errors
    finally:
        context.close()


def test_unconfigured_login_and_picture_never_upload(browser):
    context,page,errors=new_page(browser,mobile=True)
    try:
        requests=[]
        page.on('request',lambda r:requests.append(r.url))
        page.get_by_role('button',name='账号登录',exact=True).click()
        assert page.get_by_role('button',name='登录私有空间').is_disabled()
        page.locator('button[title="关闭"]').click()
        open_chat(page,'客户：你好')
        page.locator('#chatPic').set_input_files({'name':'example.svg','mimeType':'image/svg+xml','buffer':b'<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"/>'})
        assert page.locator('#photoPreview img').is_visible()
        assert not any(x.startswith('https:') for x in requests)
        assert not errors
    finally:
        context.close()


def test_restore_checkpoint(browser):
    context,page,errors=new_page(browser)
    try:
        page.on('dialog',lambda d:d.accept())
        page.get_by_role('button',name='备份与恢复',exact=True).click()
        data={'clients':[],'tasks':[],'settings':{}}
        page.locator('#modal input[type=file]').last.set_input_files({'name':'test.json','mimeType':'application/json','buffer':json.dumps(data).encode()})
        page.wait_for_function('state.clients.length===0')
        page.evaluate('restoreCheckpoint()')
        assert page.evaluate('state.clients.length')==3
        assert not errors
    finally:
        context.close()


def test_cloud_account_isolation_and_real_ai_failure_no_fallback(browser):
    context,page,errors=new_page(browser)
    try:
        # Simulate already-authenticated backend response, exercising UI data boundary.
        guest=page.evaluate('JSON.stringify(state)')
        page.evaluate("localStorage.setItem(STORAGE_KEY,JSON.stringify(state));session={access_token:'test',user:{email:'test@example.invalid'}};state={clients:[],tasks:[],settings:{}};save();")
        assert page.evaluate('localStorage.getItem(STORAGE_KEY)')==guest
        page.evaluate("session=null;state=guestSnapshot();service={auth:true,ai:true,cloud:true};render()")
        open_chat(page,'客户：多少钱')
        page.evaluate("session={access_token:'test',user:{email:'test@example.invalid'}};api=async()=>{throw Error('测试断网')};void 0")
        page.locator('#useAI').evaluate('(e)=>e.disabled=false')
        page.locator('#useAI').check()
        page.get_by_role('button',name='分析并生成回复').click()
        assert '分析未完成' in page.locator('#chatResults').inner_text()
        assert page.locator('#analysisSummary').count()==0
        assert not errors
    finally:
        context.close()


def test_served_assets_real_storage_and_mobile_routes(browser):
    from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
    from functools import partial
    from threading import Thread
    from test_public_site import SITE
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(SITE.parents[1])))
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    context=browser.new_context(viewport={'width':390,'height':844})
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        response=page.goto('http://127.0.0.1:'+str(server.server_port)+'/sales/')
        assert response.status==200
        page.get_by_role('button',name='开始分析聊天').click()
        assert page.locator('#chatRaw').is_visible()
        assert page.locator('.v5intro.compact').count()==1
        page.locator('#bottomNav').get_by_role('button',name='客户').click()
        assert page.locator('body').evaluate('(e)=>e.scrollWidth===innerWidth')
        page.get_by_role('button',name='新建客户').click()
        page.locator('#newName').fill('虚构验收客户')
        page.get_by_role('button',name='创建客户档案').click()
        page.reload()
        page.locator('#bottomNav').get_by_role('button',name='客户').click()
        assert '虚构验收客户' in page.locator('#clientRows').inner_text()
        assert not errors
    finally:
        context.close()
        server.shutdown()
