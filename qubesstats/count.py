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
import json
import logging
import math
import pathlib

import click

from . import (
    schema,
    stats,
    utils,
)

def get_month(delta=0):
    month = datetime.date.today().replace(day=1)
    for _ in range(abs(delta)):
        month = (month + math.copysign(1, delta) * datetime.timedelta(days=1)).replace(day=1)
    return month

def cb_month(ctx, param, value):
#   click.echo(f'cb_month(..., {value=})')
    if value is None:
        return
    ctx.params['month'] = datetime.datetime.strptime(value, '%Y-%m').date()

def make_cb_month_symbolic(delta):
    def callback(ctx, _param, value):
#       click.echo(f'callback::<{delta=}>(..., {value=})')
        if not value:
            return
        if delta == 0:
            ctx.params['force_fetch'] = True
        ctx.params['month'] = get_month(delta)
#       click.echo(f"{ctx.params['month']=}")
    return callback

def cb_force(ctx, _param, value):
#   click.echo(f'cb_force(..., {value=})')
    if value is not None:
        ctx.params['force_fetch'] = value

@click.command()

@click.option('--force-fetch/--no-force-fetch', expose_value=False,
    callback=cb_force, default=None,
    help='force fetching exit node list')
@click.option('--month', metavar='MONTH', expose_value=False,
    callback=cb_month,
    help='process this specific month')
@click.option('--this-month', is_flag=True, expose_value=False,
    callback=make_cb_month_symbolic(0),
    help='process current month (also selects --force-fetch)')
@click.option('--last-month', is_flag=True, expose_value=False,
    callback=make_cb_month_symbolic(-1),
    help='process last month')

@click.option('--force-descriptor-type', metavar='TYPE',
    help='force descriptor type (to work around tor#21195)')

@click.option('--last-updated/--no-last-updated', default=True,
    hidden=True)

@click.argument('configfile', metavar='FILE', type=click.File('rb'),
    default='/etc/qubesstats.toml')

def main(configfile, force_descriptor_type, last_updated, month=None,
        force_fetch=False):
    # pylint: disable=too-many-arguments
    if month is None:
        month = get_month(0)
        force_fetch = True

    utils.setup_logging()

    config = schema.load_config(configfile)
    counter = stats.QubesCounter(month.year, month.month)

    if force_descriptor_type:
        stats.EXIT_DESCRIPTOR_TYPE = force_descriptor_type

    if force_fetch:
        counter.fetch_exit_cache()
    else:
        counter.load_or_fetch_exit_cache()

    for parserconfig in config['parsers']:
        assert parserconfig['format'] == 'combined'
        for path in parserconfig['files']:
            logging.log(25, 'parsing logfile %r', path)
            with open(path) as logfile:
                requests = stats.parse_combined(logfile)
                requests = stats.filter_for_status(requests)
                for record in stats.release_filter(requests, parserconfig['regexp_path']):
                    counter.count(record)

    datafile = pathlib.Path(config['path']) / 'stats.json'

    logging.log(25, 'writing stats for period %r to datafile %s',
        counter.timestamp, datafile)

    try:
        fh = open(datafile, 'r+')
        data = json.load(fh)
    except IOError:
        fh = open(datafile, 'w')
        data = {}
    with fh:
        data[counter.timestamp] = counter
        data['meta'] = {
            'title': config['title'],
            'comment':
                'Current month is not reliable. '
                'The methodology of counting Tor users changed on April 2018.',
            'source': 'https://github.com/woju/qubes-stats',
        }
        if last_updated:
            data['meta']['last-updated'] = (
                datetime.datetime.utcnow().strftime(utils.TIMESTAMP_FORMAT))
        fh.seek(0)
        stats.QubesJSONEncoder(sort_keys=True, indent=2).dump(data, fh)
        fh.truncate()

if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    main()

# vim: ts=4 sts=4 sw=4 et
