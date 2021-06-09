#!/usr/bin/env python2

#
# Statistics aggregator for Qubes OS infrastructure.
# Copyright (C) 2015-2016  Wojtek Porczyk <woju@invisiblethingslab.com>
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

from __future__ import absolute_import, print_function

import argparse
import datetime
import json
import logging
import os

import dateutil

import qubesstats

parser = argparse.ArgumentParser()

parser.add_argument('--datafile', metavar='FILE',
    default=os.path.expanduser('~/.stats.json'),
    help='location of the data file (default: %(default)s)')

parser.add_argument('--force-fetch',
    action='store_true', default=False,
    help='force fetching exit node list')

parser.add_argument('--force-descriptor-type', metavar='TYPE',
    action='store', default=None,
    help='ignored for compatibility')

group_month = parser.add_mutually_exclusive_group(required=True)
group_month.add_argument('--current-month',
    action='store_true', default=False,
    help='process current month (also selects --force-fetch)')
group_month.add_argument('--last-month',
    action='store_true', default=False,
    help='process last month')
group_month.add_argument('--month', metavar='YYYY-MM',
    type=qubesstats.parse_date,
    help='process this specific month')

parser.add_argument('logfiles', metavar='LOGFILE',
    nargs='*', default=qubesstats.LOGFILES,
    help='process these logfiles instead of the default set')


def main():
    qubesstats.setup_logging()
    args = parser.parse_args()

    if args.current_month:
        month = datetime.date.today()
    elif args.last_month:
        month = datetime.date.today().replace(day=1)-datetime.timedelta(days=1)
    else:
        month = args.month

    counter = qubesstats.QubesCounter(month.year, month.month)

    if args.force_fetch or args.current_month:
        counter.fetch_exit_cache()
    else:
        counter.load_or_fetch_exit_cache()

    for filename in args.logfiles:
        logging.log(25, 'parsing logfile %r', filename)
        counter.process(open(filename))

    logging.log(25, 'writing stats for period %r to datafile %r',
        counter.timestamp, args.datafile)

    try:
        fh = open(args.datafile, 'r+')
        data = json.load(fh)
    except IOError:
        fh = open(args.datafile, 'w')
        data = {}

    data[counter.timestamp] = counter
    data['meta'] = {
        'title': 'Estimated Qubes OS userbase',
        'last-updated':
            datetime.datetime.utcnow().strftime(qubesstats.TIMESTAMP_FORMAT),
        'comment':
            'Current month is not reliable. '
            'The methodology of counting Tor users changed on April 2018.',
        'source': 'https://github.com/woju/qubes-stats',
    }
    fh.seek(0)
    qubesstats.QubesJSONEncoder(sort_keys=True, indent=2).dump(data, fh)
    fh.truncate()
    fh.close()


if __name__ == '__main__':
    main()

# vim: ts=4 sts=4 sw=4 et
