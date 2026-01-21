#!/usr/bin/python3

import os

from setuptools import setup, find_packages

from gspc import const

PROJECT_NAME = 'gspc'
PROJECT_PACKAGE_NAME = 'gspc'
PROJECT_LICENSE = 'GPL3'
PROJECT_AUTHOR = 'Derek Hageman'
PROJECT_COPYRIGHT = '2020, University of Colorado'
PROJECT_URL = 'https://www.esrl.noaa.gov/gmd/ccgg/'
PROJECT_EMAIL = 'derek.hageman@noaa.gov'

PROJECT_GITHUB_USERNAME = 'derek.hageman'
PROJECT_GITHUB_REPOSITORY = 'gspc'

GITLAB_PATH = '{}/{}'.format(PROJECT_GITHUB_USERNAME, PROJECT_GITHUB_REPOSITORY)
GITLAB_URL = 'https://gitlab.com/{}'.format(GITLAB_PATH)

#DOWNLOAD_URL = '{}/archive/v{}.zip'.format(GITLAB_URL, const.__version__)

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.md')) as readme:
    LONG_DESCRIPTION = readme.read()

with open(os.path.join(here, 'requirements.txt')) as requirements_txt:
    REQUIRES = requirements_txt.read().splitlines()

setup(
    nname=PROJECT_PACKAGE_NAME,
    version=const.__version__,
    license=PROJECT_LICENSE,
    url=GITLAB_URL,
    #download_url=DOWNLOAD_URL,
    author=PROJECT_AUTHOR,
    author_email=PROJECT_EMAIL,
    description="Gas sampling process control.",
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    include_package_data=True,
    zip_safe=False,
    install_requires=REQUIRES,
    tests_require=['pytest'],
    python_requires='>=3.7,<4.0',
    test_suite="tests",
    entry_points={"gui_scripts": ["gspc = gspc.__main__:main"]},
    packages=find_packages(exclude=["tests"]),
)