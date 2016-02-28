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

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

TEST_ROOT = sys.path[0]

shld_py = os.path.normpath(
    os.path.join(TEST_ROOT, '..', 'shld.py' )
)

# sad excuse for an enum
OPEN_FAILED = 1
UNSUPPORTED_SHELL = 2
IMPROPER_USE_OF_SHLDIGNORE = 3
WRONG_NUMBER_ARGS = 4
FILE_EXISTS = 5
FILE_NOT_WRITEABLE = 6
DIRECTORY_DOES_NOT_EXIST = 7
DIRECTORY_NOT_WRITEABLE = 8


class TestShldContentHandling(unittest.TestCase):

    def setUp(self):
        self.saved_cwd = os.getcwd()
        os.chdir(TEST_ROOT)

    def tearDown(self):
        os.chdir(self.saved_cwd)

    def test_improper_use_of_shldignore(self):
        with self.assertRaises(subprocess.CalledProcessError) as context_mgr:
            subprocess.check_call(
                (
                    shld_py,
                    os.path.join('resources', 'improper-use-of-shldignore.sh')
                )
            )
        self.assertEqual(context_mgr.exception.returncode, IMPROPER_USE_OF_SHLDIGNORE)


    def test_unsupported_shell(self):
        with self.assertRaises(subprocess.CalledProcessError) as context_mgr:
            subprocess.check_call(
                (
                    shld_py,
                    os.path.join('resources', 'unsupported-shell.sh')
                )
            )
        self.assertEqual(context_mgr.exception.returncode, UNSUPPORTED_SHELL)

    def test_shldignore(self):
        expected_output = """\
#!/bin/bash
. file/to/source/at/runtime
echo "Simple script to test #shldignore."
"""
        output = subprocess.check_output(
            (
                shld_py,
                os.path.join('resources', 'shldignore.sh')
            )
        )
        self.assertEqual(output, expected_output)

    def test_relpath_and_recursion(self):
        expected_output = """\
#!/bin/bash
echo "Simple script to test handling of relative include paths and recursive"
echo "includes."
echo "Included from include_level_1/include1.sh"
echo "Included from include_level_1/include_level_2/include2.sh"
"""
        output = subprocess.check_output(
            (
                shld_py,
                os.path.join('resources', 'relpath-and-recursion.sh')
            )
        )
        self.assertEqual(
            output,
            expected_output,
            """\
Expected output:
{0}
###End of Expected Output###
Actual output:
{1}
###End of Actual Output###
""".format(expected_output, output)
        )

    def test_abspath(self):
        expected_output = """\
#!/bin/bash
echo "Include specified as absolute path."
"""
        tempdir = tempfile.mkdtemp()
        temp_include_filename = os.path.join(tempdir, 'include')
        temp_scriptname = os.path.join(tempdir, 'abspath.sh')
        shutil.copy(
            os.path.join('resources', 'include.sh'),
            temp_include_filename
        )
        scriptfile = open(
            temp_scriptname,
            mode='w'
        )
        scriptfile.write(
            """\
#!/bin/bash
. {0}
""".format(temp_include_filename)
        )
        scriptfile.close()
        output = subprocess.check_output(
            (
                shld_py,
                temp_scriptname
            )
        )
        self.assertEqual(
            output,
            expected_output,
            """\
Expected output:
{0}
###End of Expected Output###
Actual output:
{1}
###End of Actual Output###
""".format(expected_output, output)
        )


class TestShldFileHandling(unittest.TestCase):

    simple_sh = os.path.join('resources', 'simple.sh')

    def setUp(self):
        self.saved_cwd = os.getcwd()
        os.chdir(TEST_ROOT)
        self.tempdir = tempfile.mkdtemp()  # this is a directory and a string

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        os.chdir(self.saved_cwd)

    def test_non_writeable_output_file(self):
        temp_filename = os.path.join(self.tempdir, 'out.sh')
        with open(temp_filename, 'a'):
            # make the output file read only
            os.chmod(temp_filename, stat.S_IRUSR)
        with self.assertRaises(subprocess.CalledProcessError) as context_mgr:
            subprocess.check_call(
                (
                    shld_py,
                    '--force',
                    TestShldFileHandling.simple_sh,
                    temp_filename
                )
            )
        self.assertEqual(context_mgr.exception.returncode, FILE_NOT_WRITEABLE)

    def test_file_exists(self):
        temp_filename = os.path.join(self.tempdir, 'out.sh')
        with open(temp_filename, 'a'):
            pass
        with self.assertRaises(subprocess.CalledProcessError) as context_mgr:
            subprocess.check_call(
                (
                    shld_py,
                    TestShldFileHandling.simple_sh,
                    temp_filename
                )
            )
        self.assertEqual(context_mgr.exception.returncode, FILE_EXISTS)

    def test_non_writeable_output_dir(self):
        temp_filename = os.path.join(self.tempdir, 'out.sh')
        os.chmod(self.tempdir, stat.S_IRUSR)
        with self.assertRaises(subprocess.CalledProcessError) as context_mgr:
            subprocess.check_call(
                (
                    shld_py,
                    TestShldFileHandling.simple_sh,
                    temp_filename
                )
            )
        self.assertEqual(context_mgr.exception.returncode, DIRECTORY_NOT_WRITEABLE)

    def test_missing_output_dir(self):
        # generate a random, garbage path
        temp_filename = os.path.join(
            '/',
            hashlib.md5(
                str(
                    time.time()
                )
            ).hexdigest(),
            'out.sh'
        )
        with self.assertRaises(subprocess.CalledProcessError) as context_mgr:
            subprocess.check_call(
                (
                    shld_py,
                    TestShldFileHandling.simple_sh,
                    temp_filename
                )
            )
        self.assertEqual(context_mgr.exception.returncode, DIRECTORY_DOES_NOT_EXIST)

    def test_writes_to_output_file(self):
        temp_filename = os.path.join(self.tempdir, 'out.sh')
        subprocess.check_call(
            (
                shld_py,
                TestShldFileHandling.simple_sh,
                temp_filename
            )
        )
        with open(temp_filename) as output_fd:
            with open(TestShldFileHandling.simple_sh) as simple_sh_fd:
                self.assertEqual(
                    output_fd.read(),
                    simple_sh_fd.read()
                )

if __name__ == '__main__':
    unittest.main(verbosity=2)