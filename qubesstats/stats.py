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

import collections
import csv
import dataclasses
import datetime
import json
import logging
import logging.handlers
import lzma
import os
import pickle
import tempfile
import urllib.parse
import urllib.request

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
CACHEDIR = '/tmp'
@dataclasses.dataclass
class Request:
    address: str
    timestamp: datetime.datetime
    path: str
    status: int

@dataclasses.dataclass
class Record:
    address: str
    timestamp: datetime.datetime
    release: str

def match_release(requests, regexp_path):
    for request in requests:
        match = regexp_path.search(request.path)
        if not match:
            logging.debug('dropping, no valid release (path=%s)', request.path)
            continue
        yield Record(request.address, request.timestamp, match.group('release'))

def filter_for_status(requests):
    """
    Reject statuses outside of range(200, 400)

    We're not interested in 403-404, because people might invent their own URIs
    and releases, so count only the valid ones. Redirects are included.
    """
    for request in requests:
        if not 200 <= request.status < 400:
            continue
        yield request

@dataclasses.dataclass
class Record:
    address: str
    timestamp: datetime.datetime
    release: str

def release_filter(requests, regexp_path):
    for request in requests:
        match = regexp_path.search(request.path)
        if not match:
            logging.debug('dropping, no valid release (path=%s)', request.path)
            continue
        yield Record(request.address, request.timestamp, match.group('release'))

def parse_combined(file):
    """
    Parses "combined" log format

    Does not include requests with status 400.

    .. seealso::

        https://en.wikipedia.org/wiki/Common_Log_Format
            Wikipedia article on the format

        https://nginx.org/en/docs/http/ngx_http_log_module.html#log_format
            nginx' definition
    """

    # pylint: disable=too-many-locals,unused-variable
    for line in csv.reader(file, delimiter=' '):
        try:
            (address, ident, user, localtime1, localtime2, request, status,
                length, referer, user_agent) = line

            status, length = int(status), int(length)
            if status == 400:
                # there's no guarantee that the split succeeds, because the
                # first line might be anything, even garbage; the line is
                # invalid anyway
                continue

            # https://www.rfc-editor.org/rfc/rfc9112.html#section-3.2 notes that
            # some clients might not properly format request line and insert
            # spaces in request-target (hereinafter `path`), even though it's
            # forbidden; RFC says server should have responeded either with 400
            # (rejected above) or 301, but we can't reject 301, so we need to
            # parse anyway and reject on regexp
            method, request_right = request.split(' ', 1)
            path, http_version = request_right.rsplit(' ', 1)

            timestamp = datetime.datetime.strptime(f'{localtime1} {localtime2}',
                '[%d/%b/%Y:%H:%M:%S %z]')
            path = urllib.parse.unquote(path)

            yield Request(address, timestamp, path, status)
        except:
            logging.error('error parsing log line: %r', line)
            raise

def parse_haproxy(file):
    # TODO
    raise NotImplementedError()

def get_parser_from_config(parserconfig):
    assert parserconfig['format'] == 'combined'
    return parse_combined


class ExitNodeAddress(list):
    def register(self, descriptor):
        self.append((
            descriptor.published.replace(tzinfo=datetime.timezone.utc),
            descriptor.last_status.replace(tzinfo=datetime.timezone.utc),
        ))

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
            logging.log(5, 'counted as tor')
            self._req_tor += 1
        else:
            logging.log(5, 'counted as plain')
            self._set_plain.add(record.address)
            self._req_plain += 1

    def asdict(self):
        return {'plain': self.plain, 'tor': self.tor}

    def __repr__(self):
        return (
            f'<{type(self).__name__} len(set_plain)={len(self._set_plain)}'
            f' req_plain={self._req_plain} req_tor={self._req_tor}>')

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

    def was_exit(self, request):
        # avoid instantiating new object
        return request.address in self.exit_cache \
            and self.exit_cache[request.address].was_active(request.timestamp)

    def count(self, record):
        if (record.timestamp.year, record.timestamp.month) \
                != (self.year, self.month):
            logging.debug('dropping, timestamp=%s', record.timestamp)
            return

        logging.log(5, 'counting %r, release=%r address=%r',
            record, record.release, record.address)

        self[record.release].count(record)
        self['any'].count(record)


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
