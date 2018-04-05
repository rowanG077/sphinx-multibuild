sphinx-multibuild
=================
Build sphinx documentation from multiple source directories. Also includes an
automatic build on change feature. This works by symlinking all the input
directories to a single temporary directory and then running sphinx on that
temporary directory.

Should work with Python >= 2.7 on Linux and Windows Vista or later.

.. warning::
    Since symlinks on Windows require admin privilege this script has to run
    in admin mode. It works without admin privilege on Windows 10 creators update
    if you have `enabled developer mode <https://blogs.windows.com/buildingapps/2016/12/02/symlinks-windows-10/>`_.

How to install
--------------

You can use pip install to install the package: ``pip install sphinx-multibuild``

Sphinx-autobuild respects the ``SHPINXBUILD`` environment variable and will use the
contents of that to build. If it is not set it defaults to the python
executable with ``-msphinx`` as the argument.

How to use from command line
----------------------------

Output of the ``--help`` command:

::

    usage: sphinx_multibuild.py [-h] -i INPUTDIRS -s TEMPDIR -o OUTPUTDIR [-q]
                                [-m] [-b builder] [-M makebuilder] [-a] [-E]
                                [-d path] [-j N] [-c path] [-C] [-D setting=value]
                                [-t tag] [-A name=value] [-n] [-v] [-Q] [-w file]
                                [-W] [-T] [-N] [-P]
                                [filenames [filenames ...]]

    Build multiple sphinx documentation directories into a single document.
    Also supports automatic build on change. Sphinx options arguments are 
    passed through.

    positional arguments:
      filenames             See `sphinx-build -h`

    optional arguments:
      -h, --help            show this help message and exit
      -i INPUTDIRS, --inputdir INPUTDIRS
                            One or more input directories.
      -s TEMPDIR, --symlinkdir TEMPDIR
                            Temporary directory where symlinks are placed.
      -o OUTPUTDIR, --outputdir OUTPUTDIR
                            The directory where you want the output to be placed
      -q, --quiet           Only print warnings and errors.
      -m, --monitor         Monitor for changes and autobuild
      -b builder            See `sphinx-build -h`
      -M makebuilder        See `sphinx-build -h`
      -a                    See `sphinx-build -h`
      -E                    See `sphinx-build -h`
      -d path               See `sphinx-build -h`
      -j N                  See `sphinx-build -h`
      -c path               See `sphinx-build -h`
      -C                    See `sphinx-build -h`
      -D <setting=value>    See `sphinx-build -h`
      -t tag                See `sphinx-build -h`
      -A <name=value>       See `sphinx-build -h`
      -n                    See `sphinx-build -h`
      -v                    See `sphinx-build -h`
      -Q                    See `sphinx-build -h`
      -w files              See `sphinx-build -h`
      -W                    See `sphinx-build -h`
      -T                    See `sphinx-build -h`
      -N                    See `sphinx-build -h`
      -P                    See `sphinx-build -h`

Sphinx options are available and are passed through to
sphinx builder. The exception are the in- and output directories since those
arguments are used by sphinx-multibuild itself. The -i specifies an input
and can be repeated multiple times. The -s options specifies the temporary
directory where symlinks are placed and the -o options sets the sphinx output
directory. Please note that no real files or directories may be placed in the
temporary directory.

Here is an example of building a document with two input directories:

    ``sphinx-multibuild -i ../doc -i ./build/doc/apigen -s ./build/doc/tmp -o ./build/doc/sphinx -b html -c ./build/doc/sphinx``

Here is another example where the -M builder is used to build latexpdf in a single step.

    ``sphinx-multibuild -i ../doc -i ./build/doc/apigen -s ./build/doc/tmp -o ./build/doc/sphinx -M latexpdf -c ./build/doc/sphinx``

Using the ``-m`` option will continuously build the output when anything changes in any of the input directories.

    ``sphinx-multibuild -m -i ../doc -i ./build/doc/apigen -s ./build/doc/tmp -o ./build/doc/sphinx -b html -c ./build/doc/sphinx``


How to use as module
--------------------
It is also possible to use sphinx-autobuild as a module and control the building
programmatically. There is a single class ``SphinxMultiBuilder`` that you can
instantiate and create builds or automatically build on change:


.. code-block:: python

    from sphinx_multibuild import SphinxMultiBuilder
    import logging
    import time
    import sys

    # Package respects loglevel set by application. Info prints out change events
    # in input directories and warning prints exception that occur during symlink 
    # creation/deletion.
    loglevel = logging.INFO
    logging.basicConfig(format='%(message)s', level=loglevel)

    # You can register a handler that will be called when a symlink
    # Can't be created or deleted.
    def handle_autobuild_error(input_path, exception):
        pass

    # Instantiate multi builder. The last two params are optional.
    builder = SphinxMultiBuilder(# input directories
                                 ["./doc", "./build/api/doc"],
                                 # Temp directory where symlinks are placed.
                                 "/tmp",
                                 # Output directory
                                 "./build/sphinx"
                                 # Sphinx arguments, this doesn't include the in- 
                                 # and output directory and filenames argments.
                                 ["-m", "html", "-c", "./build/doc"], 
                                 # Specific files to build(optional).
                                 ["index.rst"],
                                 # Callback that will be called when symlinking
                                 # error occurs during autobuilding. (optional)
                                 handle_autobuild_error)
    # build once
    builder.build()

    # start autobuilding on change in any input directory until ctrl+c is pressed.
    builder.start_autobuilding()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        builder.stop_autobuilding()

    # return the last exit code sphinx build returned had as program exit code.
    sys.exit(builder.get_last_exit_code())
