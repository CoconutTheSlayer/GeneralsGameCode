#!/usr/bin/env python3
#
# Copies the non-system libraries an executable depends on (SDL3, FFmpeg and everything they
# load in turn) into the Frameworks folder of an application bundle and points the executable
# and the libraries at the copies, so the bundle runs on Macs without Homebrew.
#
# Usage: scripts/macos/bundle-libs.py <path to .app>

import os
import shutil
import subprocess
import sys


def is_system(path):
    return path.startswith('/System/') or path.startswith('/usr/lib/')


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def dependencies(binary):
    """Returns the install names of the libraries a binary loads, without its own id."""
    lines = run('otool', '-L', binary).splitlines()[1:]
    deps = [line.strip().split(' (')[0] for line in lines if line.strip()]
    own_id = run('otool', '-D', binary).splitlines()[1:]
    if own_id:
        deps = [d for d in deps if d != own_id[0].strip()]
    return deps


def rpaths(binary):
    result = []
    lines = run('otool', '-l', binary).splitlines()
    for i, line in enumerate(lines):
        if line.strip() == 'cmd LC_RPATH':
            for follow in lines[i + 1:i + 4]:
                follow = follow.strip()
                if follow.startswith('path '):
                    result.append(follow.split(' ')[1])
    return result


def resolve(name, referrer):
    """Finds the file for an install name as seen from the referencing binary."""
    referrer_dir = os.path.dirname(os.path.realpath(referrer))
    if name.startswith('@loader_path/'):
        return os.path.realpath(os.path.join(referrer_dir, name[len('@loader_path/'):]))
    if name.startswith('@rpath/'):
        rest = name[len('@rpath/'):]
        candidates = [os.path.join(referrer_dir, rest)]
        for rpath in rpaths(referrer):
            rpath = rpath.replace('@loader_path', referrer_dir)
            candidates.append(os.path.join(rpath, rest))
        for candidate in candidates:
            if os.path.exists(candidate):
                return os.path.realpath(candidate)
        return None
    if name.startswith('@'):
        return None
    return os.path.realpath(name) if os.path.exists(name) else None


def main():
    if len(sys.argv) != 2:
        print(__doc__ or 'usage: bundle-libs.py <app>', file=sys.stderr)
        return 1
    app = sys.argv[1]
    macos_dir = os.path.join(app, 'Contents', 'MacOS')
    frameworks = os.path.join(app, 'Contents', 'Frameworks')
    os.makedirs(frameworks, exist_ok=True)

    executables = [os.path.join(macos_dir, f) for f in os.listdir(macos_dir)]
    # Maps install names seen in binaries to the bundled file name.
    bundled = {}
    queue = list(executables)
    processed = set()
    while queue:
        binary = queue.pop()
        if binary in processed:
            continue
        processed.add(binary)
        for name in dependencies(binary):
            if is_system(name):
                continue
            source = resolve(name, binary)
            if source is None:
                print(f'warning: cannot resolve {name} needed by {binary}', file=sys.stderr)
                continue
            target_name = os.path.basename(source)
            target = os.path.join(frameworks, target_name)
            if not os.path.exists(target):
                shutil.copy2(source, target)
                os.chmod(target, 0o755)
                queue.append(target)
            bundled.setdefault(binary, []).append((name, target_name))

    for binary in processed:
        args = ['install_name_tool']
        for name, target_name in bundled.get(binary, []):
            args += ['-change', name, f'@executable_path/../Frameworks/{target_name}']
        if os.path.dirname(binary) == frameworks:
            args += ['-id', f'@executable_path/../Frameworks/{os.path.basename(binary)}']
        if len(args) > 1:
            args.append(binary)
            subprocess.run(args, check=True, capture_output=True)

    print(f'Bundled {len(os.listdir(frameworks))} libraries into {frameworks}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
