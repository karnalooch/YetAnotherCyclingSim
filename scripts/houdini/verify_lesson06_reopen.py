"""Fresh-process replay of the saved Lesson06 graph on one complete domain.

Uses retained mask files; never rebuilds Lesson02-05. See --help for arguments.
"""
import sys
from repair_lesson06_idmap import main

if __name__ == '__main__':
    if '--verify' not in sys.argv:
        sys.argv.append('--verify')
    main()
