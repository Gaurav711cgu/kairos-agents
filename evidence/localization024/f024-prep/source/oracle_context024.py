"""DIAGNOSTIC UPPER BOUND ONLY: original-source regions around gold-patch hunks.

This reads the reference patch, so its output must never be reported as an
issue-only result. It answers one question for F024: can the model repair when
every edited line is visible? Regions use the same read_original handles and
bounds as issue-only selection; anything that does not fit is refused, never cut.
"""
import re

ORACLE_LABEL = 'DIAGNOSTIC oracle: gold-hunk window (not issue-only)'
MAX_REGIONS = 4
MAX_LINES = 80
PAD = 4


def oracle_regions(workspace, gold_patch, prefix):
    windows = {}
    for section in re.split(r'(?m)^(?=diff --git )', gold_patch):
        match = re.match(r'diff --git a/(\S+) b/(\S+)', section)
        if not match:
            continue
        if match[1] != match[2] or '\n--- /dev/null' in section or '\n+++ /dev/null' in section:
            if match[1].startswith(prefix) or match[2].startswith(prefix):
                raise ValueError('Gold patch creates, deletes or renames an approved file; case excluded from oracle arm')
            continue
        if not match[1].startswith(prefix) or not match[1].endswith('.py'):
            continue
        for start, count in re.findall(r'^@@ -(\d+)(?:,(\d+))? ', section, re.M):
            first, last = int(start), int(start) + max(int(count or 1), 1) - 1
            windows.setdefault(match[1], []).append([max(1, first - PAD), last + PAD])
    regions = []
    for path, spans in windows.items():
        total = len((workspace.registry.directory(workspace.case) / 'source' / path).read_text().splitlines())
        merged = []
        for low, high in sorted(spans):
            if merged and low <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], high)
            else:
                merged.append([low, high])
        for low, high in merged:
            high = min(high, total)
            if high - low + 1 > MAX_LINES:
                raise ValueError('Gold hunk window exceeds the 80-line region bound; case excluded from oracle arm')
            region = workspace.read_original(path, low, high)
            region['selection_reason'] = ORACLE_LABEL
            regions.append(region)
    if not regions or len(regions) > MAX_REGIONS:
        raise ValueError('Gold hunks need 1 to 4 regions; case excluded from oracle arm')
    return regions
