#!/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup
setup(
  name = 'sphinx-multibuild',
  packages = ['sphinx-multibuild'], # this must be the same as the name above
  version = '0.3',
  description = 'Allow sphinx to build with multiple source directories and watch for changes.',
  author = 'Rowan Goemans',
  author_email = 'goemansrowan@gmail.com',
  url = 'https://github.com/rowanG077/sphinx-multibuild', # use the URL to the github repo
  download_url = 'https://github.com/rowanG077/sphinx-multibuild/archive/0.3.tar.gz', # I'll explain this in a second
  keywords = ['sphinx', 'autobuild', 'multiple-directories'], # arbitrary keywords
  classifiers = [],
)
