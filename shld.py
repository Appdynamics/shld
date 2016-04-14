#!/usr/bin/python

# Copyright 2016, AppDynamics, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import atexit
import os
import re
import shlex
import sys
import tempfile

sys.path.append(
    os.path.join(sys.path[0], 'lib')
)
import custom_argparse

DESCRIPTION = """\
Description: Expands 'source' or '.' commands in shell scripts to "link" the
sourced files into a single, atomic shell script.  Output to STDOUT or the
specified output file name.

Operates recursively, so if a sourced script fragment sources a library itself,
that source command will also be expanded.

If a particular source command should *not* be expanded, include the comment
'#shldignore' on the line that immediately precedes it.
"""

USAGE = """\
Usage: shld.py [options] shell-script.sh [ output-file ]

Options:
  -f | --force      Overwrite output-file, if it exists.
  -h | --help       Print this help message and exit.
"""

# TODO: Add more shells that support '.' or 'source'.
SUPPORTED_SHELLS = (
    'sh',
    'bash',
    'dash',
    'ksh'
)
SHLDIGNORE_COMMENT_PATTERN = re.compile(ur'^\s*#shldignore', re.UNICODE | re.IGNORECASE)
SOURCE_CMD_PATTERN = re.compile(ur'^\s*(?:source|\.)\s+\.*', re.UNICODE)

# sad excuse for an enum
OPEN_FAILED = 1
UNSUPPORTED_SHELL = 2
IMPROPER_USE_OF_SHLDIGNORE = 3
WRONG_NUMBER_ARGS = 4
FILE_EXISTS = 5
FILE_NOT_WRITEABLE = 6
DIRECTORY_DOES_NOT_EXIST = 7
DIRECTORY_NOT_WRITEABLE = 8

output_fd = sys.stdout


def cleanup():
    if output_fd != sys.stdout:
        output_fd.close()
        try:
            os.remove(output_fd.name)
        except OSError:
            pass

atexit.register(cleanup)


def process_file(input_filename, output_fd, depth):
    input_fd = None
    try:
        input_fd = open(input_filename, mode='r')
    except IOError as e:
        sys.stderr.write(
            "Failed to open: {0}\n".format(e.filename) +
            "Reason: {0}\n".format(e.strerror)
        )
        exit(OPEN_FAILED)
    with input_fd:
        if depth == 0:
            line = input_fd.readline()
            match = re.search(
                ur'.*?([^/\s]+)\s*$',
                line,
                re.UNICODE
            )
            shell = match.group(1)
            if shell not in SUPPORTED_SHELLS:
                sys.stderr.write('Error: Detected shell, {0}, not a supported shell.\n'.format(shell))
                exit(UNSUPPORTED_SHELL)
            output_fd.write(line)
            line_number = 1
        else:
            # zero-indexing line_number because we are only using it for an
            # error reporting case where we WANT to reference the previous line.
            line_number = 0
        # conditional pushd
        input_dirname = os.path.dirname(input_filename)
        if input_dirname:
            saved_cwd = os.getcwd()
            os.chdir(input_dirname)
        else:
            saved_cwd = None
        while True:
            line = input_fd.readline()
            if line == '':
                # end of file
                break
            match = SHLDIGNORE_COMMENT_PATTERN.match(line)
            if match:
                line = input_fd.readline()
                if not SOURCE_CMD_PATTERN.match(line):
                    sys.stderr.write(
                        "Error: #shldignore comment without a following 'source' or '.' command\n"
                        "File: {0} line {1}\n".format(input_filename, line_number)
                    )
                    exit(IMPROPER_USE_OF_SHLDIGNORE)
                line_number += 1
                output_fd.write(line)
            else:
                if SOURCE_CMD_PATTERN.match(line):
                    process_file(
                        shlex.split(line)[1],  # get the filename that comes after the source command
                        output_fd,
                        depth + 1
                    )
                else:
                    output_fd.write(line)
            line_number += 1
        # popd
        if saved_cwd:
            os.chdir(saved_cwd)

cmdline = custom_argparse.ArgumentParser(
    description=DESCRIPTION,
    usage=USAGE,
    add_help=True
)

cmdline.add_argument('-f', '--force', action='store_true', required=False)

(args, filenames) = cmdline.parse_known_args()

errors = 0
num_filenames = len(filenames)
if num_filenames < 1 or num_filenames > 2:
    sys.stderr.write('Wrong number of arguments: 1 or 2 arguments expected, got {0}.\n'.format(num_filenames))
    exit(WRONG_NUMBER_ARGS)

if num_filenames == 2:
    output_filename = filenames[1]
    if os.access(output_filename, os.F_OK):  # exists
        if not args.force:
            sys.stderr.write("Error: File {0} exists.\nUse '-f' to overwrite.".format(output_filename))
            exit(FILE_EXISTS)
        if not os.access(output_filename, os.W_OK):
            sys.stderr.write('Error: File {0} not writeable.\n'.format(output_filename))
            exit(FILE_NOT_WRITEABLE)
    else:
        output_dir = os.path.dirname(output_filename)
        if not os.access(output_dir, os.F_OK):
            sys.stderr.write('Error: Directory {0} does not exist.\n'.format(output_dir))
            exit(DIRECTORY_DOES_NOT_EXIST)
        if not os.access(output_dir, os.W_OK):
            sys.stderr.write('Error: Directory {0} not writeable.\n'.format(output_dir))
            exit(DIRECTORY_NOT_WRITEABLE)
    output_fd = tempfile.NamedTemporaryFile(delete=False)

process_file(filenames[0], output_fd, 0)

if num_filenames == 2:
    output_fd.close()
    os.rename(output_fd.name, output_filename)