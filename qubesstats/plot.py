#!/usr/bin/env python2

#
# Statistics plotter for Qubes OS infrastructure.
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
import distutils.version
import json
import logging
import logging.handlers
import os

import dateutil.parser

import matplotlib
matplotlib.use('Agg')
import matplotlib.patches
import matplotlib.pyplot as plt
import matplotlib.dates
import matplotlib.ticker

import qubesstats


MM = 1 / 25.4
DPI = 300.0

BAR_WIDTH = 25.0  # days on X axis

parser = argparse.ArgumentParser()

parser = argparse.ArgumentParser()
parser.add_argument('--datafile', metavar='FILE',
    default=os.path.expanduser('~/.stats.json'),
    help='location of the data file (default: %(default)s)')

parser.add_argument('--output', metavar='PATH',
    default=os.path.expanduser('~/public_html/counter/stats'),
    help='location of the output files (default: %(default)s)')

x_major_locator = matplotlib.dates.MonthLocator()
x_major_formatter = matplotlib.dates.DateFormatter('%Y-%m')
y_major_formatter = matplotlib.ticker.ScalarFormatter()

QUBES_PALETTE = {
    'black':    '#333333',
    'red':      '#bd2727',
    'orange':   '#e79e27',
    'yellow':   '#e7e532',
    'green':    '#5ad840',
    'blue':     '#3874d8',
    'purple':   '#9f389f',
}

COLOURS = {
    'r1':   QUBES_PALETTE['red'],
    'r2':   QUBES_PALETTE['orange'],
    # skip yellow, since it is somewhat too bright
    'r3.0': QUBES_PALETTE['green'],
    'r3.1': QUBES_PALETTE['blue'],
    'r3.2': QUBES_PALETTE['purple'],
}

class LoadedStats(dict):
    def __init__(self, datafile):
        stats = json.load(open(datafile))
        self.meta = stats['meta']
        del stats['meta']

        logging.log(25, 'loaded datafile %r, last updated %r',
            datafile, self.meta['last-updated'])

        releases = set()
        for mdata in list(stats.values()):
            releases.update(ver.split('-')[0] for ver in mdata.keys())
        releases.discard('any')
        self.releases = list(sorted(releases,
            key=distutils.version.LooseVersion))

        for month in stats:
            if month not in self:
                self[month] = {}

            for release in self.releases:
                for key in stats[month]:
                    if not key == release or key.startswith(release + '-'):
                        continue
                    if release not in self:
                        self[month][release] = stats[month][release]
                    else:
                        for series, sdata in stats[month][key].items():
                            self[month][release][series] += sdata

    @property
    def months(self):
        return sorted(self)

    def get_series(self, release, series):
        for month in self.months:
            try:
                yield self[month][release][series]
            except KeyError:
                yield 0


class Graph(object):
    def __init__(self, stats):
        self.stats = stats

        self.fig = matplotlib.pyplot.figure(
            figsize=(240 * MM, 160 * MM), dpi=DPI)
        self.ax = self.fig.add_axes((.10, .15, .85, .80))

        self.handles = []

        self.setup_ax()
        self.add_data()
        self.setup_text()

    def setup_ax(self):
        self.ax.xaxis.set_major_locator(x_major_locator)
        self.ax.xaxis.set_major_formatter(x_major_formatter)
        self.ax.yaxis.set_major_formatter(y_major_formatter)
        self.ax.tick_params(labelsize='small')
        self.ax.tick_params(axis='x', length=0)

        padding = datetime.timedelta(days=20)
        self.ax.set_xlim(
            qubesstats.parse_date(self.stats.months[ 0]) - padding,
            qubesstats.parse_date(self.stats.months[-1]) + padding)

        self.ax.set_ylabel('Unique IP addresses')

        for spine in ('top', 'bottom', 'left', 'right'):
            self.ax.spines[spine].set_linewidth(0.5)

#       ax.set_xlim
        self.ax.yaxis.grid(True, which='major', linestyle=':', alpha=0.7)

    def add_data(self):
        bottom = (0,) * len(self.stats)
        offset = datetime.timedelta(days=BAR_WIDTH * 0.5)
        months = tuple(qubesstats.parse_date(i) - offset
            for i in self.stats.months)
        for release in self.stats.releases:
            for series in ('tor', 'plain'):
                sdata = tuple(self.stats.get_series(release, series))
                handle = self.ax.bar(
                    months,
                    sdata,
                    bottom=bottom,
                    hatch=('///' if series == 'tor' else None),
                    label=(release if series == 'plain' else None),
                    color=COLOURS.get(release, '#ff0000'), #TANGO['ScarletRed1']
                    width=BAR_WIDTH,
                    linewidth=0.5)
                if series == 'plain':
                    self.handles.append(handle)

                bottom = tuple(bottom[i] + sdata[i] for i in range(len(bottom)))

    def setup_text(self):
        plt.setp(self.ax.get_xticklabels(), rotation=45)
            #horizontalalignment='right', verticalalignment='top')

        self.fig.text(0.02, 0.02,
            'last updated: {meta[last-updated]}\n{meta[source]}'.format(
                meta=self.stats.meta),
            size='x-small', alpha=0.5)
        self.fig.text(0.98, 0.02,
            'Stats are based on counting the number of unique IPs\n'
            'connecting to the Qubes updates server each month.',
            size='x-small', alpha=0.5, ha='right')

        self.handles.append(matplotlib.patches.Patch(
            facecolor='white', hatch='///', label='Tor', linewidth=0.5))

        legend = plt.legend(
            loc=2, ncol=2, prop={'size': 8}, handles=self.handles)
        legend.get_frame().set_linewidth(0.5)

        plt.title(self.stats.meta['title'])

    def save(self, output):
        self.fig.savefig(output + '.png', format='png')
        self.fig.savefig(output + '.svg', format='svg')
        plt.close()


def main():
    qubesstats.setup_logging()
    args = parser.parse_args()
    stats = LoadedStats(args.datafile)
    graph = Graph(stats)
    graph.save(args.output)


if __name__ == '__main__':
    main()

# vim: ts=4 sts=4 sw=4 et
