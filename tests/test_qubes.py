import io
import sys

import click.testing
import pytest

from qubesstats import count, stats

@pytest.fixture
def click_runner():
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem():
        yield runner

@pytest.fixture
def config_toml(click_runner):
    with open('config.toml', 'w') as file:
        file.write(r'''
title = "Estimated Qubes OS userbase"
path = '.'

[[parsers]]
files = [
    './access.log',
]
regexp_path = '^/(?P<release>[^~/]+)/(.*/)?repomd\.xml(\.metalink)?$'

[[annotations]]
timestamp = 2018-03-15
text = "Methodology of counting Tor users has changed"
''')

@pytest.fixture
def access_log(click_runner):
    with open('access.log', 'w') as file:
        file.write('''\
127.81.0.1 - - [01/Jul/2022:00:01:15 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.1 - - [01/Jul/2022:00:01:16 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.1 - - [01/Jul/2022:00:01:18 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.1 - - [01/Jul/2022:00:01:19 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.1 - - [01/Jul/2022:00:01:19 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.1 - - [01/Jul/2022:00:01:20 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.2 - - [01/Jul/2022:00:01:23 +0000] "GET /r4.1/current/vm/fc35/repodata/repomd.xml HTTP/1.1" 200 3853 "-" "libdnf (Fedora Linux 35; generic; Linux.x86_64)"
127.81.0.2 - - [01/Jul/2022:00:01:23 +0000] "GET /r4.1/current/vm/fc35/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora Linux 35; generic; Linux.x86_64)"
127.81.0.3 - - [01/Jul/2022:00:01:24 +0000] "GET /r4.0/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3853 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.4 - - [01/Jul/2022:00:01:44 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.4 - - [01/Jul/2022:00:01:45 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.4 - - [01/Jul/2022:00:01:46 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.4 - - [01/Jul/2022:00:01:47 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.5 - - [01/Jul/2022:00:01:47 +0000] "GET /r4.1/current/dom0/fc32/repodata/repomd.xml.metalink HTTP/1.1" 200 2809 "-" "libdnf (Fedora Linux 35; generic; Linux.x86_64)"
127.81.0.5 - - [01/Jul/2022:00:01:47 +0000] "GET /r4.1/unstable/dom0/fc32/repodata/repomd.xml.metalink HTTP/1.1" 200 2824 "-" "libdnf (Fedora Linux 35; generic; Linux.x86_64)"
127.81.0.4 - - [01/Jul/2022:00:01:54 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.6 - - [01/Jul/2022:00:01:54 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.4 - - [01/Jul/2022:00:01:55 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.4 - - [01/Jul/2022:00:02:00 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.4 - - [01/Jul/2022:00:02:01 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.7 - - [01/Jul/2022:00:02:04 +0000] "GET /r4.0/current/dom0/fc25/repodata/repomd.xml.metalink HTTP/1.1" 200 2809 "-" "libdnf"
127.81.0.1 - - [01/Jul/2022:00:02:05 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.1 - - [01/Jul/2022:00:02:07 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.7 - - [01/Jul/2022:00:02:07 +0000] "GET /r4.0/templates-itl/repodata/repomd.xml.metalink HTTP/1.1" 200 2749 "-" "libdnf"
127.81.0.1 - - [01/Jul/2022:00:02:08 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.1 - - [01/Jul/2022:00:02:09 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.7 - - [01/Jul/2022:00:02:10 +0000] "GET /r4.0/templates-itl/repodata/repomd.xml HTTP/1.1" 200 3078 "-" "libdnf"
127.81.0.8 - - [01/Jul/2022:00:02:15 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.8 - - [01/Jul/2022:00:02:15 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.8 - - [01/Jul/2022:00:02:34 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.8 - - [01/Jul/2022:00:02:34 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.9 - - [01/Jul/2022:00:02:49 +0000] "GET /r4.1/current/vm/fc36/repodata/repomd.xml HTTP/1.1" 200 3852 "-" "libdnf (Fedora Linux 36; generic; Linux.x86_64)"
127.81.0.9 - - [01/Jul/2022:00:02:50 +0000] "GET /r4.1/current/vm/fc36/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora Linux 36; generic; Linux.x86_64)"
127.81.0.10 - - [01/Jul/2022:00:02:50 +0000] "GET /r4.0/current/vm/fc32/repodata/repomd.xml HTTP/1.1" 200 3853 "-" "libdnf (Fedora 32; generic; Linux.x86_64)"
127.81.0.1 - - [01/Jul/2022:00:02:55 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.1 - - [01/Jul/2022:00:02:56 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml.asc HTTP/1.1" 200 833 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
127.81.0.1 - - [01/Jul/2022:00:02:57 +0000] "GET /r4.1/current/vm/fc34/repodata/repomd.xml HTTP/1.1" 200 3859 "-" "libdnf (Fedora 34; generic; Linux.x86_64)"
''')

def test_count(click_runner, access_log, config_toml):
    result = click_runner.invoke(count.main, ['--month', '2022-07', '--no-last-updated', 'config.toml'])
    if result.exit_code != 0:
        if result.stdout_bytes is not None:
            sys.stdout.buffer.write(result.stdout_bytes)
        if result.stderr_bytes is not None:
            sys.stderr.buffer.write(result.stderr_bytes)
        if result.exception is not None:
            raise result.exception
        assert result.exit_code == 0
    with open('stats.json', 'r') as file:
        assert file.read() == '''\
{
  "2022-07": {
    "any": {
      "plain": 10,
      "tor": 0
    },
    "r4.0": {
      "plain": 3,
      "tor": 0
    },
    "r4.1": {
      "plain": 7,
      "tor": 0
    }
  },
  "meta": {
    "comment": "Current month is not reliable. The methodology of counting Tor users changed on April 2018.",
    "source": "https://github.com/woju/qubes-stats",
    "title": "Estimated Qubes OS userbase"
  }
}'''
