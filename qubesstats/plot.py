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
import collections
import datetime
import distutils.version
import itertools
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

import numpy as np

import qubesstats


MM = 1 / 25.4
DPI = 300.0

BAR_WIDTH = 31.0  # days on X axis

parser = argparse.ArgumentParser()

parser = argparse.ArgumentParser()
parser.add_argument('--datafile', metavar='FILE',
    default=os.path.expanduser('~/.stats.json'),
    help='location of the data file (default: %(default)s)')

parser.add_argument('--output', metavar='PATH',
    default=os.path.expanduser('~/public_html/counter/stats'),
    help='location of the output files (default: %(default)s)')

x_major_locator = matplotlib.dates.MonthLocator(bymonth=[1, 4, 7, 10])
x_major_formatter = matplotlib.dates.DateFormatter('%Y-%m')
y_major_formatter = matplotlib.ticker.ScalarFormatter()

Colour = collections.namedtuple('Colour', (
    'plain', 'tor', 'current_plain', 'current_tor'))

class Hue(tuple):
    def get_colour(self, series, is_current=False):
        return self[int(series == 'plain') + int(bool(is_current))]

COLOURS = [
    # http://tango.freedesktop.org/Tango_Icon_Theme_Guidelines
    Hue(('#5c3566', '#75507b', '#ad7fa8')),  # Plum
    Hue(('#ce5c00', '#f57900', '#fcaf3e')),  # Orange
    Hue(('#4e9a06', '#73d216', '#8ae234')),  # Chameleon
    Hue(('#204a87', '#3465a4', '#729fcf')),  # SkyBlue
]

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

        months = sorted(stats)
        self.months = np.array(map(qubesstats.parse_date, months))

        for i, month in enumerate(months):
            for release in self.releases:
                for key in stats[month]:
                    if not key == release or key.startswith(release + '-'):
                        continue
                    for series, sdata in stats[month][key].items():
                        self[release, series][i] += sdata

    def __missing__(self, key):
        self[key] = np.zeros(self.months.size)
        return self[key]

class Graph(object):
    def __init__(self, stats):
        self.stats = stats
        self.now = self.stats.months[-1]
        self.x_min = self.now.replace(year=self.now.year-3)

        self.fig = matplotlib.pyplot.figure(
            figsize=(240 * MM, 160 * MM), dpi=DPI)
        self.ax = self.fig.add_axes((.10, .12, .85, .80))

        self.setup_ax()
        self.add_data()
        self.add_annotations()
        self.setup_text()

    def setup_ax(self):
        self.ax.xaxis.set_major_locator(x_major_locator)
        self.ax.xaxis.set_major_formatter(x_major_formatter)
        self.ax.yaxis.set_major_formatter(y_major_formatter)
        self.ax.tick_params(labelsize='small')
        self.ax.tick_params(axis='x', length=0)

        padding = datetime.timedelta(days=20)
        self.ax.set_xlim(self.x_min - padding, self.now + padding)

        self.ax.set_ylabel('Unique IP addresses')

        for spine in ('top', 'bottom', 'left', 'right'):
            self.ax.spines[spine].set_linewidth(0.5)

        self.ax.yaxis.grid(True, which='major', linestyle=':', alpha=0.7)

    def find_label_placement(self, release_cur):
        sdata_cur_plain = self.stats[release_cur, 'plain']
        sdata_cur_tor = self.stats[release_cur, 'tor']

        try:
            release_next = self.stats.releases[
                self.stats.releases.index(release_cur) + 1]
            sdata_next_plain = self.stats[release_next, 'plain']
            sdata_next_tor = self.stats[release_next, 'tor']
        except LookupError:
            # last release
            sdata_next_plain = np.zeros(sdata_cur_plain.size, dtype=np.int)
            sdata_next_tor = sdata_next_plain

        sdata_diff = ((sdata_next_plain + sdata_next_tor)
                    - (sdata_cur_plain + sdata_cur_tor))

        # [:-1] is not to label current month
        for i, diff in reversed(list(enumerate(sdata_diff[:-1]))):
            if diff < 0:
                return i, sdata_cur_plain[i] / 2.0

        # Loop didn't return. This means we have been long overtaken by next
        # version. So no label.
        return None, 0

    def add_data(self):
        bottom = np.zeros(self.stats.months.size)
        colours = itertools.cycle(COLOURS)

        for release in self.stats.releases:
            hue = next(colours)
            for series in ('tor', 'plain'):
                sdata = self.stats[release, series]

                self.ax.bar(
                    self.stats.months[:-1],
                    sdata[:-1],
                    bottom=bottom[:-1],
                    label=(release if series == 'plain' else None),
                    color=hue.get_colour(series, False),
                    width=BAR_WIDTH,
                    linewidth=0.5)

                # current month
                self.ax.bar(
                    self.stats.months[-1:],
                    sdata[-1:],
                    bottom=bottom[-1:],
                    label=None,
                    color=hue.get_colour(series, True),
                    width=BAR_WIDTH,
                    linewidth=0.5)

                bottom += sdata

            i, y_offset = self.find_label_placement(release)
            if i is not None and self.stats.months[i] >= self.x_min:
                self.ax.text(self.stats.months[i], bottom[i] - y_offset,
                    release, horizontalalignment='right',
                    bbox={'facecolor': '#ffffff'})

    def add_annotations(self):
        # methodology change
        self.ax.axvline(datetime.datetime(2018, 3, 15, 0, 0, 0),
            color='#ef2929', linewidth=2)
        self.ax.text(0.02, 0.98, 'shaded areas are Tor users',
                bbox={'facecolor': '#ffffff'},
                transform=self.ax.transAxes, verticalalignment='top')

    def setup_text(self):
        self.fig.text(0.02, 0.02,
            'last updated: {meta[last-updated]}\n{meta[source]}'.format(
                meta=self.stats.meta),
            size='x-small', alpha=0.5)
        self.fig.text(0.98, 0.02,
            'Estimate is based on counting the number of unique IPs '
            'connecting to the Qubes updates server each month.\n'
            'Because of accumulating nature of the estimate, current month '
            '(lighter bar) will continue to raise until next month.\n'
            'Red line: methodology of counting Tor users has changed.',
            size='x-small', alpha=0.5, ha='right')

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
