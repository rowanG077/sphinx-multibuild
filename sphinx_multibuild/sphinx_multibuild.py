#!/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import os
import errno
import sys
import time
import logging
import threading
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

# small hackerino for windows
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
        if os.path.islink(path) is False:
            raise Exception("unlink only possible with symlink.")

        if os.path.isdir(path):
            os.rmdir(path)
        else:
            os.remove(path)

    os.symlink = win32_create_symlink
    os.path.islink = win32_is_symlink
    os.unlink = win32_unlink


class SymlinkHandler(FileSystemEventHandler):
    def __init__(self, rootpath, symlinkdir, build_event):
        self.rootpath = os.path.normpath(os.path.abspath(rootpath))
        self.symlinkdir = os.path.normpath(os.path.abspath(symlinkdir))
        self._build_event = build_event

        for n in os.listdir(rootpath):
            try:
                path = os.path\
                    .abspath(os.path.join(rootpath, n))
                msg = """Creating initial \
symlink: %s""" % (path)
                logging.info(msg)
                self.create_link(path)
            except Exception as e:
                msg = 'Failed to create symlink: %s' % (str(e))
                logging.error(msg)

    def on_moved(self, event):
        if self.is_root_path(event.src_path) \
                or self.is_root_path(event.dest_path):
            return

        msg = """Move detected: %s -> %s, \
Removing old symlink and creating new\
""" % (event.src_path, event.dest_path)
        logging.info(msg)
        try:
            self.delete_link(event.src_path)
            self.create_link(event.dest_path)
        except Exception as e:
            msg = 'Failed to remove/create symlink: %s' % (str(e))
            logging.error(msg)

        self._build_event.set()

    def on_created(self, event):
        if self.is_root_path(event.src_path):
            return

        msg = 'Create detected: %s, Creating symlink' % (event.src_path)
        logging.info(msg)
        try:
            self.create_link(event.src_path)
        except Exception as e:
            msg = 'Failed to create symlink: %s' % (str(e))
            logging.error(msg)

        self._build_event.set()

    def on_deleted(self, event):
        if self.is_root_path(event.src_path):
            return
        msg = 'Delete detected: %s, Deleting symlink' % (event.src_path)
        logging.info(msg)
        try:
            self.delete_link(event.src_path)
        except Exception as e:
            msg = 'Failed to delete symlink: %s' % (str(e))
            logging.error(msg)

        self._build_event.set()

    def on_modified(self, event):
        if self.is_root_path(event.src_path):
            return
        msg = 'Change detected: %s, Recreating symlink' % \
            (event.src_path)
        logging.info(msg)

        try:
            self.create_link(event.src_path)
        except Exception as e:
            msg = 'Failed to recreate symlink: %s' % (str(e))
            logging.error(msg)

        self._build_event.set()

    def create_link(self, target):
        self.delete_link(target)
        os.symlink(self.get_source(target), self.get_target(target))

    def delete_link(self, target):
        link = self.get_target(target)
        if os.path.lexists(link) is False:
            return

        os.unlink(link)

    def is_root_path(self, target):
        target = os.path.normpath(os.path.abspath(target))
        return target == self.rootpath

    def get_source(self, target):
        target = os.path.normpath(os.path.abspath(target))
        link_name = self.path_base(self.rootpath, target)
        return os.path.join(self.rootpath, link_name)

    def get_target(self, target):
        target = os.path.normpath(os.path.abspath(target))
        link_name = self.path_base(self.rootpath, target)
        return os.path.join(self.symlinkdir, link_name)

    def path_base(self, root, path):
        abspath = os.path.normpath(os.path.abspath(path))
        stripped = os.path.relpath(abspath, root)

        head, tail = os.path.split(stripped)
        while head != '':
            head, tail = os.path.split(head)

        return tail


class SphinxBuilder(object):
    def __init__(self, args, build_event):
        self.ret_code = 1
        self._args = ['sphinx-build'] + args
        self._build_event = build_event
        self._builder_thread = threading.Thread(target=self._builder)
        self._builder_thread.daemon = True
        self._builder_thread.start()

    def build(self):
        proc = subprocess.Popen(self._args, shell=False)
        self.ret_code = proc.wait()

    def _builder(self):
        while True:
            self._build_event.wait()
            self._build_event.clear()
            m = "============= Triggered Sphinx build ============="
            logging.info(m)
            self.build()


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


def sphinx_multibuild(
    input_paths,
    dest_path,
    symlink_path,
    quiet,
    monitor,
    sphinx_args
):
    loglevel = logging.WARNING if quiet else logging.INFO
    logging.basicConfig(format='%(message)s', level=loglevel)

    mkdir_p(dest_path)
    mkdir_p(symlink_path)

    for n in os.listdir(symlink_path):
        path = os.path.abspath(os.path.join(symlink_path, n))
        if os.path.islink(path):
            os.unlink(path)
        else:
            msg = """Existing file in destdir \
that is not symlink: %s""" % (path)
            logging.error(msg)
            sys.exit(1)

    dest_path = os.path.normpath(os.path.abspath(dest_path))

    for i, e in enumerate(input_paths):
        if not os.path.isdir(e):
            msg = '%s is not a directory.' % (e)
            logging.error(msg)
            sys.exit(1)
        input_paths[i] = os.path.normpath(os.path.abspath(e))

    changed_event = threading.Event()

    builder = SphinxBuilder(sphinx_args, changed_event)
    handlers = [SymlinkHandler(x, symlink_path, changed_event)
                for x in input_paths]

    builder.build()

    if monitor:
        observer = Observer()
        for h in handlers:
            observer.schedule(h, h.rootpath, recursive=True)

        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
        logging.info('Stopped monitoring.')

    return builder.ret_code

if __name__ == '__main__':
    """Parse and check the command line arguments."""
    parser = argparse.ArgumentParser(
        description="""Build multiple sphinx documentation dir\
into a single document. \
Also supports automatic building.""",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-i', '--input', action='append', type=str,
                        dest='inputdirs', help='An input directory.',
                        required=True)
    parser.add_argument('-s', '--symlinkpath',
                        type=str, dest='tempdir',
                        help='Temporary directory where symlinks are placed.',
                        required=True)
    parser.add_argument('-q', '--quiet', action='store_true',
                        dest='quiet', help='Only print warnings and errors.')
    parser.add_argument('-m', '--monitor', action='store_true',
                        dest='monitor', help='Monitor for changes and \
autobuild')
    parser.add_argument('outputdir', type=str,
                        help='The directory where you want the output to \
be placed')

    # sphinx build options.
    for o, m in SHPINX_OPTS:
        if m is None:
            parser.add_argument('-{0}'.format(o), action='count',
                                help='See `sphinx-build -h`')
        else:
            parser.add_argument('-{0}'.format(o), action='append',
                                metavar=m, help='See `sphinx-build -h`')

    parser.add_argument('filenames', nargs='*',
                        help='See `sphinx-build -h`')

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

    sphinx_args.extend([args.tempdir, args.outputdir])
    sphinx_args.extend(args.filenames)

    ret_code = sphinx_multibuild(args.inputdirs, args.outputdir,
                                 args.tempdir, args.quiet,
                                 args.monitor, sphinx_args)

    sys.exit(ret_code)
