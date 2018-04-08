#!/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import errno
import logging
import os
import subprocess
import sys
import threading
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


# buffers events until a specified amount of seconds
# without set has ellapsed.
# has the same interface as threading.Event
class _BufferedEvent(object):
    def __init__(self, buffer_time_seconds):
        self._buffer_time_seconds = buffer_time_seconds
        self._ev = threading.Event()
        self._internal_ev = threading.Event()
        self._thread = threading.Thread(target=self._bufferer)
        self._thread.daemon = True
        self._thread.start()

    def _bufferer(self):
        while True:
            self._internal_ev.wait()
            self._internal_ev.clear()
            time.sleep(self._buffer_time_seconds)
            if not self._internal_ev.is_set():
                self._ev.set()

    def is_set(self):
        return self._ev.is_set()

    def isSet(self):
        return self._ev.isSet()

    def clear(self):
        self._ev.clear()

    def set(self):
        self._internal_ev.set()

    def wait(self, **kwargs):
        self._ev.wait(**kwargs)


# Shim class to allow windows to symlink the same as linux on python 2.7
class _SymlinkShim(object):
    def __init__(self):
        if os.name == 'nt':
            import ctypes
            win = ctypes.windll

            def win32_create_symlink(src, dst):
                # Set flags for the file or dir and then send the flag to allow
                # creation without admin permission
                flags = 1 if src is not None and os.path.isdir(src) else 0
                flags = flags | 2
                res = win.kernel32.CreateSymbolicLinkW(
                    unicode(dst), unicode(src), flags)
                if not res:
                    raise OSError(str(win.kernel32.GetLastError()))

            def win32_is_symlink(path):
                if not os.path.exists(path):
                    return False

                FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
                attributes = win.kernel32.GetFileAttributesW(
                    unicode(path))
                return (attributes & FILE_ATTRIBUTE_REPARSE_POINT) > 0

            def win32_unlink(path):
                if win32_is_symlink(path) is False:
                    raise OSError("unlink only possible with symlink.")

                if os.path.isdir(path):
                    os.rmdir(path)
                else:
                    os.remove(path)

            self._link = win32_create_symlink
            self._unlink = win32_unlink
            self._is_link = win32_is_symlink
        else:
            self._link = os.symlink
            self._unlink = os.unlink
            self._is_link = os.path.islink

    def link(self, src, dst):
        return self._link(src, dst)

    def is_link(self, path):
        return self._is_link(path)

    def unlink(self, path):
        return self._unlink(path)


class _SymlinkHandler(FileSystemEventHandler):
    def __init__(self, source_dir, symlink_dir, build_event, logger, symlinker,
                 symlink_error_callback):
        self.source_dir = os.path.normpath(os.path.abspath(source_dir))
        self.symlink_dir = os.path.normpath(os.path.abspath(symlink_dir))
        self._build_event = build_event
        self._symlinker = symlinker
        self._logger = logger

        if symlink_error_callback is None:
            self._error_callback = lambda p, e: None
        else:
            self._error_callback = symlink_error_callback

        for n in os.listdir(self.source_dir):
            try:
                path = os.path.abspath(os.path.join(self.source_dir, n))
                msg = 'Creating initial symlink: %s' % path
                self._logger.info(msg)
                self._create_link(path)
            except Exception as e:
                msg = 'Failed to create symlink: %s' % str(e)
                self._logger.error(msg)
                raise e

    def on_moved(self, event):
        if (self._is_source_dir(event.src_path) or
                self._is_source_dir(event.dest_path)):
            return

        msg = 'Move detected: %s -> %s, \
Removing old symlink and creating new' % (event.src_path, event.dest_path)
        self._logger.info(msg)
        try:
            self._delete_link(event.src_path)
            self._create_link(event.dest_path)
        except Exception as e:
            msg = 'Failed to remove/create symlink: %s' % (str(e))
            self._logger.error(msg)
            self._error_callback(self.source_dir, e)

        self._build_event.set()

    def on_created(self, event):
        if self._is_source_dir(event.src_path):
            return

        msg = 'Create detected: %s, Creating symlink' % event.src_path
        self._logger.info(msg)
        try:
            self._create_link(event.src_path)
        except Exception as e:
            msg = 'Failed to create symlink: %s' % str(e)
            self._logger.error(msg)
            self._error_callback(self.source_dir, e)

        self._build_event.set()

    def on_deleted(self, event):
        if self._is_source_dir(event.src_path):
            return
        msg = 'Delete detected: %s, Deleting symlink' % event.src_path
        self._logger.info(msg)
        try:
            self._delete_link(event.src_path)
        except Exception as e:
            msg = 'Failed to delete symlink: %s' % (str(e))
            self._logger.error(msg)
            self._error_callback(self.source_dir, e)

        self._build_event.set()

    def on_modified(self, event):
        if self._is_source_dir(event.src_path):
            return
        msg = 'Change detected: %s, Recreating symlink' % event.src_path
        self._logger.info(msg)

        try:
            self._create_link(event.src_path)
        except Exception as e:
            msg = 'Failed to recreate symlink: %s' % (str(e))
            self._logger.error(msg)
            self._error_callback(self.source_dir, e)

        self._build_event.set()

    def _create_link(self, target):
        self._delete_link(target)
        self._symlinker.link(self._get_source(target),
                             self._get_target(target))

    def _delete_link(self, target):
        link = self._get_target(target)
        if not self._symlinker.is_link(link):
            return
        self._symlinker.unlink(link)

    def _is_source_dir(self, target):
        target = os.path.normpath(os.path.abspath(target))
        return target == self.source_dir

    def _get_link_name(self, target):
        target = os.path.normpath(os.path.abspath(target))
        return self._path_base(self.source_dir, target)

    def _get_source(self, target):
        return os.path.join(self.source_dir, self._get_link_name(target))

    def _get_target(self, target):
        return os.path.join(self.symlink_dir, self._get_link_name(target))

    def _path_base(self, root, path):
        abspath = os.path.normpath(os.path.abspath(path))
        stripped = os.path.relpath(abspath, root)

        head, tail = os.path.split(stripped)
        while head != '':
            head, tail = os.path.split(head)

        return tail


class _SphinxBuilder(object):
    def __init__(self, args, build_event, logger):
        self.exit_code = 1

        env = os.environ.get('SPHINXBUILD', None)
        if env:
            self._args = [env] + args
        else:
            self._args = [sys.executable, '-msphinx'] + args

        self._build_event = build_event
        self._logger = logger
        self._builder_thread = threading.Thread(target=self._builder)
        self._builder_thread.daemon = True
        self._builder_thread.start()

    def build(self):
        proc = subprocess.Popen(self._args, shell=False)
        self.exit_code = proc.wait()

    def _builder(self):
        while True:
            self._build_event.wait()
            self._build_event.clear()
            m = "================== Triggered Sphinx build =================="
            self._logger.info(m)
            self.build()


class SphinxMultiBuilder(object):
    def __init__(self,
                 input_paths,
                 symlink_path,
                 dest_path,
                 sphinx_args,
                 sphinx_filenames_arg=[],
                 symlink_error_callback=None):

        # Organise arguments passed to sphinx.
        self._sphinx_args = sphinx_args
        try:
            buildIndex = self._sphinx_args.index('-M') + 2
            self._sphinx_args.insert(buildIndex, dest_path)
            self._sphinx_args.insert(buildIndex, symlink_path)
        except ValueError:
            self._sphinx_args.extend([symlink_path, dest_path])

        self._sphinx_args.extend(sphinx_filenames_arg)

        # setup logger.
        self._logger = logging.getLogger(__name__)

        # Check passed directories and make them if necessary.
        self._mkdir_p(dest_path)
        self._mkdir_p(symlink_path)

        symlinker = _SymlinkShim()

        for n in os.listdir(symlink_path):
            path = os.path.abspath(os.path.join(symlink_path, n))
            if symlinker.is_link(path):
                symlinker.unlink(path)
            else:
                msg = 'File in symlinkpath is not a symlink: %s' % path
                self._logger.error(msg)
                sys.exit(1)

        for i, e in enumerate(input_paths):
            if not os.path.isdir(e):
                msg = '%s is not a directory.' % e
                logging.error(msg)
                sys.exit(1)
            input_paths[i] = os.path.normpath(os.path.abspath(e))

        # create the sphinx builder and the directory observers.
        self._changed_event = _BufferedEvent(1)
        self._builder = _SphinxBuilder(sphinx_args, self._changed_event,
                                       self._logger)
        self._handlers = [_SymlinkHandler(p, symlink_path, self._changed_event,
                                          self._logger, symlinker,
                                          symlink_error_callback)
                          for p in input_paths]

        self._observer = Observer()
        for h in self._handlers:
            self._observer.schedule(h, h.source_dir, recursive=True)

    def _mkdir_p(self, path):
        try:
            os.makedirs(path)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise

    def get_last_exit_code(self):
        return self._builder.exit_code

    def build(self):
        self._builder.build()

    def start_autobuilding(self):
        self._observer.start()

    def stop_autobuilding(self):
        self._observer.stop()
        self._observer.join()


def main():
    SHPINX_OPTS = (
        ('b', 'builder'),
        ('M', 'makebuilder'),
        ('a', None),
        ('E', None),
        ('d', 'path'),
        ('j', 'N'),
        ('c', 'path'),
        ('C', None),
        ('D', 'setting=value'),
        ('t', 'tag'),
        ('A', 'name=value'),
        ('n', None),
        ('v', None),
        ('Q', None),
        ('w', 'file'),
        ('W', None),
        ('T', None),
        ('N', None),
        ('P', None)
    )

    """Parse and check the command line arguments."""
    parser = argparse.ArgumentParser(
        description=('Build multiple sphinx documentation directories \
into a single document. \
Also supports automatic build on change. \
Sphinx options arguments are passed through.'),
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-i', '--inputdir', action='append', type=str,
                        dest='inputdirs', required=True,
                        help='One or more input directories.')
    parser.add_argument('-s', '--symlinkdir', type=str, dest='symlinkdir',
                        help='Temporary directory where symlinks are placed.',
                        required=True)
    parser.add_argument('-o', '--outputdir', type=str, dest='outputdir',
                        required=True,
                        help='The directory where you \
want the output to be placed')
    parser.add_argument('-q', '--quiet', action='store_true',
                        dest='quiet', help='Only print warnings and errors.')
    parser.add_argument('-m', '--monitor', action='store_true',
                        dest='monitor',
                        help='Monitor for changes and autobuild')

    # sphinx build options.
    for o, m in SHPINX_OPTS:
        if m is None:
            parser.add_argument('-{0}'.format(o), action='count',
                                help='See `sphinx-build -h`')
        else:
            parser.add_argument('-{0}'.format(o), action='append',
                                metavar=m, help='See `sphinx-build -h`')

    parser.add_argument('filenames', nargs='*', help='See `sphinx-build -h`')

    args = parser.parse_args()

    sphinx_args = []
    for o, m in SHPINX_OPTS:
        val = getattr(args, o)
        if not val:
            continue
        opt = '-{0}'.format(o)
        if m is None:
            sphinx_args.extend([opt] * val)
        else:
            for v in val:
                sphinx_args.extend([opt, v])

    loglevel = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(format='%(message)s', level=loglevel)
    builder = SphinxMultiBuilder(args.inputdirs, args.symlinkdir,
                                 args.outputdir, sphinx_args, args.filenames)

    builder.build()

    if args.monitor:
        builder.start_autobuilding()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            builder.stop_autobuilding()

    sys.exit(builder.get_last_exit_code())

if __name__ == '__main__':
    main()
