#!/usr/bin/env python2

#
# Statistics aggregator for Qubes OS infrastructure.
# Copyright (C) 2015  Wojtek Porczyk <woju@invisiblethingslab.com>
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

from __future__ import print_function

import argparse
import collections
import datetime
import json
import logging
import logging.handlers
import os
import re
import sys

import dateutil.parser

LOGFILES = [
    '/var/log/httpd-access.log',
    '/var/log/httpd-access.log.0',
    '/var/log/httpd-access.log.1',
]

_re_request_uri = re.compile(r'"GET ([^ "]+)[^"]*" [123]')
_re_date = re.compile(r'\[\d{2}/(\w{3}/\d{4})')
_re_ip = re.compile(r'^(\d+:)?((\d{1,3}.){3}\d{1,3})')

parser = argparse.ArgumentParser()
#parser.add_argument('--logfile', '-f', metavar='LOGFILE',
#    default='/var/log/httpd-access.log',
#    help='Which file to parse (default: %(default)s)')

parser.add_argument('--datafile', metavar='FILE',
    default=os.path.expanduser('~/.stats.json'),
    help='location of the data file (default: %(default)s)')

group_period = parser.add_mutually_exclusive_group(required=True)
group_period.add_argument('--current-month',
    action='store_true', default=False,
    help='process current month'
    )
group_period.add_argument('--last-month',
    action='store_true', default=False,
    help='process last month'
    )
group_period.add_argument('period', metavar='YYYY-MM',
    nargs='?',
    type=dateutil.parser.parse,
    help='process this specific month')


logging.addLevelName(25, 'NOTICE')
class BetterSysLogHandler(logging.handlers.SysLogHandler):
    priority_map = logging.handlers.SysLogHandler.priority_map.copy()
    priority_map['NOTICE'] = 'notice'

def excepthook(exctype, value, traceback):
    logging.exception('exception')
    return sys.__excepthook__(exctype, value, traceback)

def setup_logging(level=25):
    handler = BetterSysLogHandler(address='/var/run/log')
    handler.setFormatter(
        logging.Formatter('%(module)s[%(process)d]: %(message)s'))
    logging.root.addHandler(handler)

#   handler = logging.StreamHandler(sys.stderr)
#   handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
#   logging.root.addHandler(handler)

    sys.excepthook = excepthook
    logging.root.setLevel(level)


def main():
    setup_logging()
    args = parser.parse_args()
    if args.current_month:
        period = datetime.date.today()
    elif args.last_month:
        period = datetime.date.today().replace(day=1)-datetime.timedelta(days=1)
    else:
        period = args.period
    date_pattern = period.strftime('%b/%Y')

    releases = collections.defaultdict(set)

    for filename in LOGFILES:
        if not os.path.exists(filename):
            continue

        logging.log(25, 'parsing logfile {!r}'.format(filename))
        for line in open(filename):
            m = _re_date.search(line)
            if not m or m.group(1) != date_pattern:
                continue

            m = _re_request_uri.search(line)
            if not m:
                continue
            path = m.group(1)

            if not path.endswith('repomd.xml'):
                continue

            m = _re_ip.search(line)
            assert m, 'line without IP: {!r}'.format(line)
            ip = m.group(2)

            path_t = path.lstrip('/').split('/')
            while path_t[0] in ('repo', 'yum'):
                path_t.pop(0)

            releases[path_t[0]].add(ip)

    stats = {}
    any_release = set()
    for release, ips in releases.items():
        stats[release] = len(ips)
        any_release.update(releases[release])
    stats['any'] = len(any_release)

    timestamp = period.strftime('%Y-%m')
    logging.log(25, 'writing stats for period {!r} to datafile {!r};'
        ' stats[\'any\'] = {!r}'.format(timestamp, args.datafile, stats['any']))

    with open(args.datafile, 'r+') as fh:
        data = json.load(fh)
        data[timestamp] = stats
        data['meta'] = {
            'title': 'Estimated Qubes OS userbase',
            'last-updated': datetime.datetime.now().strftime('%d.%m.%Y %H:%M'),
            'comment': 'Stats are based on counting the number of unique IPs'
                ' connecting to the Qubes update server each month.',
            'source': 'https://github.com/woju/qubes-stats',
        }
        fh.seek(0)
        json.dump(data, fh, sort_keys=True, indent=2)
        fh.truncate()


if __name__ == '__main__':
    main()

# vim: ts=4 sts=4 sw=4 et
