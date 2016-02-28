# Shell Script Linking Tool

## Usage and Description

```
Description: Expands 'source' or '.' commands in shell scripts to "link" the
sourced files into a single, atomic shell script.  Output to STDOUT or the
specified output file name.

Operates recursively, so if a sourced script fragment sources a library itself,
that source command will also be expanded.

If a particular source command should *not* be expanded, include the comment
'#shldignore' on the line that immediately precedes it.

Usage: shld.py shell-script.sh [ output-file ]

Options:
  -f | --force      Overwrite output-file, if it exists.
  -h | --help       Print this help message and exit.
```
