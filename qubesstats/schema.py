#
# Copyright (C) 2022  Wojtek Porczyk <woju@invisiblethingslab.com>
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
#import pathlib
import re
import typing

from voluptuous import (
    All,
    Any,
    Date,
    Datetime,
    IsDir,
    Length,
    Required,
    Schema,
)

try:
    import tomli
    tomli_load = tomli.load
except ImportError:
    import io
    import toml
    def tomli_load(file):
        return toml.load(io.TextIOWrapper(file))

class Hue(typing.NamedTuple):
    dark: str
    medium: str
    light: str
    def get_colour(self, series, is_current=False):
        # pylint: disable=unsubscriptable-object
        return self[int(series == 'plain') + int(bool(is_current))]

class Annotation(typing.NamedTuple):
    timestamp: datetime.datetime
    text: str

DEFAULT_COLOURS = [
    ['#5c3566', '#75507b', '#ad7fa8'],  # Plum
    ['#ce5c00', '#f57900', '#fcaf3e'],  # Orange
    ['#4e9a06', '#73d216', '#8ae234'],  # Chameleon
    ['#204a87', '#3465a4', '#729fcf'],  # SkyBlue
]

DEFAULT_PARSERS = [{
    'format': 'combined',
    'files': [
        '/var/log/nginx/access.log',
        '/var/log/nginx/access.log.1',
        '/var/log/nginx/access.log.2',
    ],
    'regexp_path': r'^/(?P<release>[^~/]+)/(.*/)?repomd\.xml(\.metalink)?$',
}]

SCHEMA = Schema({
    Required('title'): str,
    Required('path'): IsDir(),
    Required('colours', default=DEFAULT_COLOURS): [
        All([str], Length(3)),
    ],
    Required('parsers', default=DEFAULT_PARSERS): [{
        Required('format', default='combined'): 'combined',
        Required('files'): [str],
        Required('regexp_path'): re.compile,
    }],
    Required('annotations', default=[]): [{
        Required('timestamp'): Any(
            datetime.datetime,
            datetime.date,
            Datetime,
            Date,
        ),
        Required('text'): str,
    }],
})

def load_config(file):
    return SCHEMA(tomli_load(file))
