from app.services.ccf import parse_mirror


def test_mirror_rejects_wrong_edition():
    payload = {"metadata": {"year": 2025, "edition": "第六版", "publisher": "中国计算机学会"}, "domains": []}
    try:
        parse_mirror(payload)
    except ValueError as exc:
        assert "seventh edition" in str(exc)
    else:
        raise AssertionError("invalid edition must be rejected")

from app.services.ccf import parse_official_conference_area


def test_parse_official_conference_area_reads_conference_not_journal():
    html = """
    <div>中国计算机学会推荐国际学术会议</div>
    <div>A类</div>
    <table>
      <tr><th>序号</th><th>会议简称</th><th>会议全称</th><th>出版社</th><th>地址</th></tr>
      <tr><td>1</td><td>CVPR</td><td>IEEE/CVF Conference on Computer Vision and Pattern Recognition</td><td>IEEE</td><td><a href='https://cvpr.thecvf.com/'>link</a></td></tr>
    </table>
    <div>中国计算机学会推荐国际学术刊物</div>
    <div>A类</div>
    <table>
      <tr><td>1</td><td>TPAMI</td><td>IEEE Transactions on Pattern Analysis and Machine Intelligence</td><td>IEEE</td><td></td></tr>
    </table>
    """
    items = parse_official_conference_area(html, "AI", "https://www.ccf.org.cn/Academic_Evaluation/AI/")
    assert len(items) == 1
    assert items[0]["shortName"] == "CVPR"
    assert items[0]["ccf"] == "A"
    assert items[0]["sub"] == "AI"
