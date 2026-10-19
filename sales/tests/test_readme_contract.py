"""Documentation contract preventing accidental removal of key safeguards."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SALES = ROOT / 'sales'


def test_root_readme_documents_site_boundaries_and_release_requirements():
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    for required in ('/dayueyue/', '/sales/', 'sales/README.md', 'Git commit', 'pytest', '禁止', '公开'):
        assert required in text, f'root README missing: {required}'


def test_sales_readme_has_non_negotiable_commit_test_and_privacy_contracts():
    text = (SALES / 'README.md').read_text(encoding='utf-8')
    for required in (
        'https://yuelvyou.cn/sales/',
        '今日工作台', '我的客户', '聊天助手', '跟进计划',
        '海景蓝白', 'localStorage', '没有自动 OCR',
        'Git commit', 'commit SHA', '更新对应测试',
        'python -m pytest -q sales/tests',
        '全部通过才提交', '必须明确披露',
        '老师的课程原文', '客户原话', '未知信息',
        '注册游客', '购买398元会员', '明确拒绝',
        'git revert <commit-sha>',
    ):
        assert required in text, f'sales README missing: {required}'


def test_contracts_do_not_claim_unimplemented_ai_or_cloud_support():
    text = (SALES / 'README.md').read_text(encoding='utf-8')
    assert '本地规则' in text
    assert '尚未实现' in text
    assert 'API 密钥只能放服务端' in text