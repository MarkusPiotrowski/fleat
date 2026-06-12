"""
python -m fleat setup-android [project_dir]

Builds a folder structure and copies .java files to be included by the Android
build tool Gradle

Usage
    python -m fleat setup-android
    python -m fleat setup-android /path/to/your/flet-project
"""

import sys
import shutil
from pathlib import Path


def setup_android(project_dir):
    package_dir = Path(__file__).parent

    # Copy Java files to build/flutter/android/app/src/main/java/
    java_src = package_dir / 'java'
    java_dst = (
        project_dir
        / 'build'
        / 'flutter'
        / 'android'
        / 'app'
        / 'src'
        / 'main'
        / 'java'
    )
    fleat_dst = java_dst / 'com' / 'fleat' / 'ble'
    jnius_dst = java_dst / 'bin' / 'jnius'

    files_ = (
        ('FleatScanCallback.java', fleat_dst),
        ('FleatGattCallback.java', fleat_dst),
        ('NativeInvocationHandler.java', jnius_dst),
    )

    try:
        fleat_dst.mkdir(parents=True, exist_ok=True)
        jnius_dst.mkdir(parents=True, exist_ok=True)
        for file_ in files_:
            src_file, dst = file_
            shutil.copy2(java_src / src_file, dst / src_file)
            print(f'Copy file {src_file} from {java_src} to {dst}')
    except Exception as e:
        print(f'An error occured: {e}')
        sys.exit(1)

    print(
        '\nFinished. Java files will be included during the next Android '
        'build.\n IMPORTANT: If you delete the "build" folder or use "flet '
        'build --clear-cache", you need to re-run this script ("python -m '
        'fleat setup-android").\n'
    )


def main():
    args = sys.argv[1:]

    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)

    if args[0] != 'setup-android':
        print(f'Unknown command: {args[0]}')
        print('Usage: python -m fleat setup-android [project_dir]')
        sys.exit(1)

    project_dir = Path(args[1]) if len(args) > 1 else Path.cwd()

    if not project_dir.exists():
        print(f'ERROR: Folder not found: {project_dir}')
        sys.exit(1)

    setup_android(project_dir)


if __name__ == '__main__':
    main()
