#
# Statistics aggregator for Qubes OS infrastructure.
# Copyright (C) 2015-2022  Wojtek Porczyk <woju@invisiblethingslab.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import argparse
import collections
import datetime
import functools
import json
import logging
import logging.handlers
import lzma
import os
import pickle
import re
import stat
import sys
import tempfile
import urllib.parse
import urllib.request

import dateutil.parser
import stem.descriptor.reader

LOGFILES = [
    '/var/log/nginx/access.log',
    '/var/log/nginx/access.log.1',
    '/var/log/nginx/access.log.2',
]

EXIT_LIST_URI = 'https://collector.torproject.org/archive/exit-lists/' \
    'exit-list-{timestamp}.tar.xz'

EXIT_DESCRIPTOR_TOLERANCE = 24 # hours

EXIT_DESCRIPTOR_TYPE = None

SYSLOG_TRY_SOCKETS = [
    '/var/run/log', # FreeBSD
    '/dev/log',     # Linux
]

CACHEDIR = '/tmp'

DEFAULT_DATE = datetime.datetime.now().replace(
    day=1, hour=0, minute=0, second=0, microsecond=0)
parse_date = functools.partial(dateutil.parser.parse, default=DEFAULT_DATE)

TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

logging.addLevelName(25, 'NOTICE')

class BetterSysLogHandler(logging.handlers.SysLogHandler):
    priority_map = logging.handlers.SysLogHandler.priority_map.copy()
    priority_map['NOTICE'] = 'notice'

def excepthook(exctype, value, traceback):
    logging.exception('exception')
    return sys.__excepthook__(exctype, value, traceback)

def setup_logging(level=25):
    # guess where the syslogd might listen
    handler = None
    for address in SYSLOG_TRY_SOCKETS:
        try:
            if not stat.S_ISSOCK(os.stat(address).st_mode):
                continue
        except OSError:
            continue

        handler = BetterSysLogHandler(address=address)

    if handler is None:
        # default, which probably will connect over UDP
        handler = BetterSysLogHandler()

    handler.setFormatter(
        logging.Formatter('%(module)s[%(process)d]: %(message)s'))
    logging.root.addHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logging.root.addHandler(handler)

    sys.excepthook = excepthook
    logging.root.setLevel(level)


class DownloadRecord(str):
    re_timestamp = re.compile(r'\[(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})')
    re_request_uri = re.compile(r'"GET ([^ "]+)[^"]*" [123]')
    re_address = re.compile(r'^(\d+:)?((\d{1,3}.){3}\d{1,3})')

    def __init__(self, line):
        super().__init__()
        m = self.re_timestamp.search(line)
        if not m:
            raise ValueError('date not found in {!r}'.format(self))
        self.timestamp = m.group(1)

        m = self.re_request_uri.search(line)
        if not m:
            raise ValueError('URI not found in {!r}'.format(self))
        self.path = urllib.parse.unquote(m.group(1))

        if not self.path.endswith('repomd.xml') \
                and not self.path.endswith('repomd.xml.metalink'):
            raise ValueError('Not a repomd.xml')

        m = self.re_address.search(line)
        if not m:
            raise ValueError('IP address not found in {!r}'.format(self))
        self.address = m.group(2)

        path_tokens = self.path.lstrip('/').split('/')
        if path_tokens[0][0] == '~':
            raise ValueError(
                'personal repo ({!r}), not counting'.format(path_tokens[0]))
        while path_tokens[0] in ('repo', 'yum'):
            path_tokens.pop(0)
        self.release = path_tokens[0]

        self.timestamp = datetime.datetime.strptime(
            self.timestamp, '%d/%b/%Y:%H:%M:%S')


class ExitNodeAddress(list):
    def register(self, descriptor):
        self.append((descriptor.published, descriptor.last_status))

    def was_active(self, date):
        # This assumes that an IP address is active for the entire lifespan of
        # the descriptor, which may or may not be true
        delta = datetime.timedelta(hours=EXIT_DESCRIPTOR_TOLERANCE)
        return any(
            (desc[0] - delta) <= date <= (desc[1] + delta) for desc in self)

    def compact(self):
        self.sort()
        i = 0
        while i < len(self) - 1:
            if self[i][1] >= self[i+1][0] \
                    - datetime.timedelta(hours=EXIT_DESCRIPTOR_TOLERANCE):
                desc0 = self.pop(i)
                desc1 = self.pop(i)
                self.insert(i, (desc0[0], desc1[1]))
            else:
                i += 1


class Release:
    def __init__(self, counter):
        self.counter = counter
        self._set_plain = set()
        self._req_plain = 0
        self._req_tor = 0

    plain = property(lambda self: len(self._set_plain))

    # Proportion between number of users and number of requests should be
    # approximately constant. However, Tor hides users behind exit nodes.
    # Therefore, for Tor we count requests and normalise them against users
    # who used plain HTTPS.
    tor = property(lambda self: self._req_tor * self.plain // self._req_plain)

    def count(self, record):
        if self.counter.was_exit(record):
            self._req_tor += 1
        else:
            self._set_plain.add(record.address)
            self._req_plain += 1

    def asdict(self):
        return {'plain': self.plain, 'tor': self.tor}

class QubesCounter(dict):
    release_class = Release

    def __init__(self, year, month):
        super().__init__()
        self.year, self.month = (year, month)
        self.exit_cache = collections.defaultdict(ExitNodeAddress)

    def __missing__(self, key):
        self[key] = self.release_class(self)
        return self[key]

    @property
    def exit_cache_file(self):
        return os.path.join(
            CACHEDIR, 'exit_cache-{}.pickle'.format(self.timestamp))

    @property
    def timestamp(self):
        return '{:04d}-{:02d}'.format(self.year, self.month)

    def load_or_fetch_exit_cache(self):
        try:
            self.load_exit_cache()
        except IOError:
            logging.log(25, 'loading exit node list failed')
            self.fetch_exit_cache()

    def load_exit_cache(self):
        logging.log(25, 'loading exit node list')
        with open(self.exit_cache_file, 'rb') as fh:
            self.exit_cache = pickle.load(fh)

    def fetch_exit_cache(self):
        logging.log(25, 'downloading exit node list')
        tmpfile = tempfile.NamedTemporaryFile(suffix='.tar')
        tmpfile.write(lzma.decompress(urllib.request.urlopen(
            EXIT_LIST_URI.format(timestamp=self.timestamp)).read()))
        tmpfile.flush()
        self.bake_exit_cache([tmpfile.name])

    def bake_exit_cache(self, paths):
        logging.log(25, 'parsing exit node list')
        n_desc = 0
        n_addr = 0
        with stem.descriptor.reader.DescriptorReader(
                paths, descriptor_type=EXIT_DESCRIPTOR_TYPE) as reader:
            for descriptor in reader:
                n_desc += 1
                for address in descriptor.exit_addresses:
                    n_addr += 1
                    self.exit_cache[address[0]].register(descriptor)
        logging.log(25, 'parsed %d descriptors with %d addresses',
            n_desc, n_addr)

        for cache in self.exit_cache.values():
            cache.compact()

        logging.log(25, 'saving exit node list')
        pickle.dump(self.exit_cache,
            open(self.exit_cache_file, 'wb'), pickle.HIGHEST_PROTOCOL)

    def was_exit(self, record):
        # avoid instantiating new object
        return record.address in self.exit_cache \
            and self.exit_cache[record.address].was_active(record.timestamp)

    def count(self, record):
        if not (record.timestamp.year, record.timestamp.month) \
                == (self.year, self.month):
            logging.debug('dropping, timestamp=%s', record.timestamp)
            return
        logging.log(5, 'counting %r, release=%r address=%r',
            record, record.release, record.address)
        self[record.release].count(record)
        self['any'].count(record)

    def process(self, stream):
        for line in stream:
            try:
                record = DownloadRecord(line)
            except ValueError:
                continue
            self.count(record)


class QubesJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Release):
            return o.asdict()
        return super().default(o)

    def dump(self, o, stream):
        for chunk in self.encode(o):
            stream.write(chunk)
        stream.flush()


# vim: ts=4 sts=4 sw=4 et
