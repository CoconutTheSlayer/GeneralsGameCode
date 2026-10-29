"""Read the player's installed Generals data for reusable animation/module definitions.

No original game assets are embedded in this repository. Generated derivatives live
alongside the existing local add-on assets. GENERALS_DATA_ROOT can select an install.
"""
from functools import lru_cache
from pathlib import Path
import os
import re
import struct


def entries(path):
    data = Path(path).read_bytes()
    count = struct.unpack_from('>I', data, 8)[0]
    at = 16
    for _ in range(count):
        offset, size = struct.unpack_from('>II', data, at)
        end = data.index(b'\0', at + 8)
        yield data[at + 8:end].decode('latin-1').replace('\\', '/'), data[offset:offset + size]
        at = end + 1


@lru_cache(None)
def files(kind='ini'):
    root = Path(os.environ.get('GENERALS_DATA_ROOT', str(Path.home() / 'Games')))
    order = {'ini': ['ini.big', 'inizh.big', 'patchini.big'],
             'w3d': ['w3d.big', 'w3dzh.big', 'w3denglishzh.big'],
             'textures': ['textures.big', 'textureszh.big']}[kind]
    paths = list(root.rglob('*.big'))
    result = {}
    for archive in order:
        # The install may keep an older backup under Data/INI. Prefer the actual
        # top-level archive over those nested copies, as the runtime does.
        matches = sorted((p for p in paths if p.name.lower() == archive), key=lambda p:(len(p.relative_to(root).parts),str(p)))
        if matches:
            for name, data in entries(matches[0]):
                key = name.lower()
                result[key] = result.get(key, b'') + b'\n' + data if kind == 'ini' else data
    if not result:
        raise FileNotFoundError(f'No {kind} archives in {root}; set GENERALS_DATA_ROOT to your game install')
    return result


def asset(name, kind='w3d'):
    suffix = '/' + name.lower()
    return next(data for key, data in files(kind).items() if key.endswith(suffix))


def clean(text):
    return '\n'.join(re.split(r';|//', line, maxsplit=1)[0].rstrip() for line in text.splitlines())


@lru_cache(None)
def record(kind, name):
    pattern = re.compile(r'^' + re.escape(kind) + r'\s+' + re.escape(name) + r'\s*\n(.*?)^End\b', re.M | re.S | re.I)
    candidates = list(files().items())
    if kind.lower() == 'object':
        # Generals' monolithic files can survive in the installed archive set,
        # alongside Zero Hour's newer per-faction object files. Prefer the
        # runtime Zero Hour definition when both contain the same object.
        legacy = {'factionunit.ini', 'factionbuilding.ini'}
        candidates.sort(key=lambda entry: entry[0].rsplit('/', 1)[-1] in legacy)
    for path, data in candidates:
        if not path.endswith('.ini'):
            continue
        matches = list(pattern.finditer(clean(data.decode('latin-1'))))
        if matches:
            return matches[-1].group(1).rstrip().splitlines()
    raise KeyError(f'{kind} {name} not found in installed game')


def module(object_name, tag):
    lines = record('Object', object_name)
    for i, line in enumerate(lines):
        if re.search(r'\b' + re.escape(tag) + r'\s*$', line) and re.match(r'\s*(Draw|Behavior|Body)\s*=', line):
            indent = len(line) - len(line.lstrip())
            out = [line.strip()]
            for rest in lines[i + 1:]:
                # Stock files occasionally close a module at a shallower indent
                # than its header. Remove whitespace only, never part of "End".
                leading = len(rest) - len(rest.lstrip())
                out.append(rest[min(indent, leading):])
                if rest.strip() == 'End' and len(rest) - len(rest.lstrip()) <= indent:
                    return out
    raise KeyError(f'{object_name}: module {tag} missing')


def replaced_module(object_name, tag, replacements=()):
    body = '\n'.join(module(object_name, tag))
    body = body.replace(tag, 'ModuleTag_Euro_' + tag.removeprefix('ModuleTag_'))
    for old, new in replacements:
        body = body.replace(old, new)
    return [f'ReplaceModule {tag}'] + ['  ' + line for line in body.splitlines()] + ['End']


def copied_record(kind, parent, name, replacements=()):
    body = '\n'.join(record(kind, parent))
    for old, new in replacements:
        body = body.replace(old, new)
    return [f'{kind} {name}', *body.splitlines(), 'End', '']
