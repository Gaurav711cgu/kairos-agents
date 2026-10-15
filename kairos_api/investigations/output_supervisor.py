"""Apply the host output-file limit in a fresh process, then exec its fixed argv.

The caller constructs this argv from the registered verifier. Models receive no
shell or launcher tool. Keeping setrlimit here avoids preexec_fn in a threaded
parent while retaining the Docker client's existing disk-output limit. This
POSIX launcher does not claim Windows runtime support.
"""
from __future__ import annotations

import os
import sys

MAXIMUM_BYTES = 1024 * 1024


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) < 3 or arguments[1] != '--':
        raise ValueError('Expected a file-size limit followed by -- and the registered argv')
    try:
        maximum = int(arguments[0])
    except (ValueError, TypeError):
        raise ValueError('File-size limit must be an integer') from None
    if not 1 <= maximum <= MAXIMUM_BYTES:
        raise ValueError('File-size limit exceeds the host output capture ceiling')
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE, (maximum, maximum))
    os.execvp(arguments[2], arguments[2:])


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not include argv, credentials, source, or environment in diagnostics.
        print('Output supervisor failed: ' + type(error).__name__, file=sys.stderr)
        raise SystemExit(126)
