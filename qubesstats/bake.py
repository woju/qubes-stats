#!/usr/bin/env python2

#
# Statistics aggregator for Qubes OS infrastructure.
# Copyright (C) 2015-2021  Wojtek Porczyk <woju@invisiblethingslab.com>
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
import dateutil

from . import (
    QubesCounter,
    parse_date,
    setup_logging,
)

parser = argparse.ArgumentParser()

parser.add_argument('--force-descriptor-type', metavar='TYPE',
    action='store', default=None,
    help='ignored for compatibility')
parser.add_argument('month', metavar='YYYY-MM',
    type=parse_date,
    help='process this specific month')
parser.add_argument('exit_list', metavar='PATH',
    nargs='*', default=['.'],
    help='location of the exit list directories (default: %(default)r)')

def main():
    setup_logging()
    args = parser.parse_args()
    counter = QubesCounter(args.month.year, args.month.month)
    counter.bake_exit_cache(args.exit_list)

if __name__ == '__main__':
    main()

# vim: ts=4 sts=4 sw=4 et
