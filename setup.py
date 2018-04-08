#!/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst')) as f:
    long_description = f.read()

setup(
  name='sphinx-multibuild',
  packages=['sphinx_multibuild'],
  version='1.1.1',
  description='Allow sphinx to build with multiple source directories and watch for changes.',
  long_description=long_description,
  long_description_content_type='text/x-rst',
  author='Rowan Goemans',
  author_email='goemansrowan@gmail.com',
  url='https://github.com/rowanG077/sphinx-multibuild',
  download_url='https://github.com/rowanG077/sphinx-multibuild/archive/1.1.1.tar.gz',
  keywords=['sphinx', 'autobuild', 'multiple-directories'],
  license='MIT',
  classifiers=[
    'Development Status :: 5 - Production/Stable',
    'Intended Audience :: Developers',
    'Topic :: Software Development :: Build Tools',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
  ],
  install_requires=['watchdog', 'sphinx'],
  python_requires='>=2.7',
  package_data={
    'sphinx_multibuild': ['README.rst'],
  },
  entry_points={
    'console_scripts': [
      'sphinx-multibuild=sphinx_multibuild.sphinx_multibuild:main'
    ]
  },
)
