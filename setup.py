#!/usr/bin/env python3

import setuptools

if __name__ == '__main__':
    setuptools.setup(
        name='qubes-stats',
        version='2.0',
        author='Invisible Things Lab',
        author_email='woju@invisiblethingslab.com',
        description='TOR-aware distribution statistics',
        license='GPL2+',
        url='https://www.qubes-os.org/',

        packages=['qubesstats'],
        install_requires=[
#           'matplotlib',
            'pyliblzma',
            'python_dateutil',
            'stem',
        ],

        entry_points={
            'console_scripts': [
                'stats-count = qubesstats.count:main',
                'stats-plot = qubesstats.plot:main',
                'stats-bake-cache = qubesstats.bake:main',
            ]
        }
    )
