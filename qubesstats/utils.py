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

import datetime
import functools
import logging
import os
import stat
import sys

import dateutil.parser

DEFAULT_DATE = datetime.datetime.now().replace(
    day=1, hour=0, minute=0, second=0, microsecond=0)
parse_date = functools.partial(dateutil.parser.parse, default=DEFAULT_DATE)
TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
logging.addLevelName(25, 'NOTICE')

SYSLOG_TRY_SOCKETS = [
    '/var/run/log', # FreeBSD
    '/dev/log',     # Linux
]

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
