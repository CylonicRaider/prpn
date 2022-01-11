#!/usr/bin/env python3
# -*- coding: ascii -*-

from setuptools import setup

setup(
    name='prpn',
    version='0.1',
    packages=['prpn'],
    include_package_data=True,
    zip_safe=False,
    install_requires=['flask>=2.0']
)
