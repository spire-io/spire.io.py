#!/usr/bin/env python
from setuptools import setup, find_packages

REQS = ['requests >= 0.6.4'] # ['gevent >= 0.13.6']

setup(
    name="spire",
    version="0.1",
    description="Client library for http://spire.io notification service",
    extras_require=dict(test=REQS + ['nose >= 1.1.2']),
    install_requires=REQS,
    packages=find_packages(),
    test_suite='nose.collector',
    )
