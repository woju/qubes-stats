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

import click

from . import stats, utils

@click.command()
@click.option('--force-descriptor-type', metavar='TYPE',
    help='force descriptor type (to work around tor#21195)')
@click.argument('month', metavar='YYYY-MM',
    type=click.DateTime('%Y-%m'),
    help='process this specific month')
@click.argument('exit_list', metavar='PATH', nargs=-1, default=['.'],
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
    help='location of the exit list directories (default: %(default)r)')
def main(force_descriptor_type, month, exit_list):
    utils.setup_logging()
    if force_descriptor_type:
        stats.EXIT_DESCRIPTOR_TYPE = force_descriptor_type
    counter = stats.QubesCounter(month.year, month.month)
    counter.bake_exit_cache(exit_list)

if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    main()

# vim: ts=4 sts=4 sw=4 et
