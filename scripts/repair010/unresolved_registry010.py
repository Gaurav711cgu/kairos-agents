"""Experimental registration for reviewed Python defects without reference fixes.

This is a trusted, local registration boundary, not a browser upload endpoint.
An operator prepares a pinned source tree and reviewed verifier under the
server-owned case root. A separate qualifier captures both baseline suites.
Hashes detect later changes; they do not prove who authored the tests or make
the verifier resistant to adversarial test forgery. No reference repair is read.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
from pathlib import Path, PurePosixPath
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kairos_api.investigations.patches import source_path
from kairos_api.investigations.registry import CaseRegistry, tree_hash

TASK_KIND = "reviewed-unresolved-python-v1"
REGISTRY_VERSION = "reviewed-task-registry-v1"
VERIFIER_COMMAND = ["python", "/verification/verify.py"]
SHA256 = r"^[a-f0-9]{64}$"
IDENTIFIER = r"^[a-z0-9][a-z0-9_-]{0,119}$"
MAX_MANIFEST_BYTES = 1_048_576
MAX_RECEIPT_BYTES = 2_200_000


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def _relative_name(value: str, *, directory: bool = False) -> str:
    """Accept canonical, ordinary relative POSIX names, never host locations."""
    candidate = value[:-1] if directory and value.endswith("/") else value
    path = PurePosixPath(candidate)
    if (not candidate or path.is_absolute() or str(path) != candidate or
            "\\" in candidate or not re.fullmatch(r"[A-Za-z0-9_./-]+", candidate) or
            any(part in {".", ".."} or part.startswith(".") for part in path.parts)):
        raise ValueError("Expected a canonical registered relative path")
    if directory and not value.endswith("/"):
        raise ValueError("Approved source prefix must end with a slash")
    return value


class VerificationFiles(StrictModel):
    test_patch: str = Field(pattern=SHA256)
    verify_py: str = Field(pattern=SHA256)


class BaselineFiles(StrictModel):
    regression: str = Field(pattern=SHA256)
    existing: str = Field(pattern=SHA256)


class ReviewedTask(StrictModel):
    task_kind: Literal["reviewed-unresolved-python-v1"]
    id: str = Field(pattern=IDENTIFIER)
    title: str = Field(min_length=1, max_length=500)
    issue: str = Field(min_length=1, max_length=20_000)
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", max_length=160)
    revision: str = Field(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
    approved_prefix: str = Field(min_length=2, max_length=180)
    entry_files: list[str] = Field(min_length=1, max_length=4)
    entry_lines: dict[str, int]
    localization: Literal["reviewer-provided-source-entry-files"]
    provenance: str = Field(min_length=1, max_length=2000)
    split: Literal["unresolved"]
    image: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    command: list[str]
    source_digest: str = Field(pattern=SHA256)
    verification_digest: str = Field(pattern=SHA256)
    environment_digest: str = Field(pattern=SHA256)
    verification_files: VerificationFiles
    baseline_receipts: BaselineFiles
    qualified: bool

    @field_validator("approved_prefix")
    @classmethod
    def validate_prefix(cls, value):
        return _relative_name(value, directory=True)

    @field_validator("command")
    @classmethod
    def fixed_command(cls, value):
        if value != VERIFIER_COMMAND:
            raise ValueError("Only the reviewed fixed verifier command is supported")
        return value

    @model_validator(mode="after")
    def validate_entries(self):
        if len(set(self.entry_files)) != len(self.entry_files):
            raise ValueError("Source entry files must be distinct")
        if set(self.entry_lines) != set(self.entry_files):
            raise ValueError("Every provided source entry requires an explicit starting line")
        for name in self.entry_files:
            _relative_name(name)
            # Use the existing source policy without opening any machine path.
            source_path(Path("/registered-source"), self.approved_prefix, name)
            if not 1 <= self.entry_lines[name] <= 100_000:
                raise ValueError("Source entry line is outside supported bounds")
        return self


class BaselineReceipt(StrictModel):
    """A trusted qualifier's complete per-suite result, not a model assertion."""
    version: Literal["independent-unresolved-baseline-v1"]
    captured_by: Literal["trusted-qualifier"]
    run_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{8,80}$")
    task_id: str = Field(pattern=IDENTIFIER)
    suite: Literal["regression", "existing"]
    revision: str = Field(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
    source_digest: str = Field(pattern=SHA256)
    verification_digest: str = Field(pattern=SHA256)
    image: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    environment_digest: str = Field(pattern=SHA256)
    command: list[str]
    completed: bool
    passed: bool
    returncode: int
    tests_run: int = Field(ge=1)
    failures: int = Field(ge=0)
    environment_error: bool
    timed_out: bool
    output_limit_exceeded: bool
    output_complete: bool
    stdout: str = Field(max_length=1_048_576)
    stderr: str = Field(max_length=1_048_576)

    @field_validator("command")
    @classmethod
    def fixed_command(cls, value):
        if value != VERIFIER_COMMAND:
            raise ValueError("Baseline command differs from the registered verifier")
        return value

    @model_validator(mode="after")
    def complete_baseline(self):
        if (not self.completed or not self.output_complete or self.environment_error or
                self.timed_out or self.output_limit_exceeded):
            raise ValueError("Qualification requires complete baseline checks without infrastructure failure")
        if self.failures > self.tests_run:
            raise ValueError("Baseline failure count exceeds executed tests")
        if self.suite == "regression":
            if self.passed or self.returncode not in range(1, 124) or self.failures < 1:
                raise ValueError("Regression baseline must fail a completed test assertion")
        elif not self.passed or self.returncode != 0 or self.failures:
            raise ValueError("Relevant existing tests must pass before investigation")
        return self


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON fields are forbidden")
        result[key] = value
    return result


def _load_json(path: Path, maximum: int):
    _regular_file(path, maximum)
    return json.loads(path.read_text(), object_pairs_hook=_no_duplicates)


def _regular_file(path: Path, maximum: int | None = None):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Registered files must be ordinary files without links")
    if maximum is not None and info.st_size > maximum:
        raise ValueError("Registered file exceeds its capture limit")


def _reject_link_components(path: Path):
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError("Registered paths must not traverse symlinks")


def _plain_tree(root: Path):
    _reject_link_components(root)
    if not root.is_dir():
        raise ValueError("Pinned source directory is missing")
    found = False
    for path in root.rglob("*"):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        _regular_file(path)
        found = True
    if not found:
        raise ValueError("Pinned source tree is empty")


class UnresolvedCaseRegistry010(CaseRegistry):
    """Keep historical registration unchanged; validate the new kind explicitly.

    ``manifest`` and ``runtime`` are trusted operator/CLI settings. Public
    requests select only an existing identifier. This adapter performs no fetch,
    shell execution, dependency setup, credential discovery, or reference lookup.
    """
    def manifest(self):
        if not self.path.exists():
            return super().manifest()
        value = _load_json(self.path, MAX_MANIFEST_BYTES)
        if not isinstance(value, dict) or not isinstance(value.get("cases"), list):
            raise ValueError("Registered manifest requires a cases list")
        if value.get("version") == REGISTRY_VERSION:
            if set(value) != {"version", "cases"}:
                raise ValueError("Unknown reviewed registry fields")
            if any(not isinstance(item, dict) or item.get("task_kind") != TASK_KIND for item in value["cases"]):
                raise ValueError("Reviewed registry contains an unsupported task kind")
        elif value.get("version") != "repository-cases-v1":
            raise ValueError("Unsupported registered manifest version")
        identifiers = []
        for item in value["cases"]:
            if not isinstance(item, dict):
                raise ValueError("Registered cases must be objects")
            if "task_kind" in item:
                item = ReviewedTask.model_validate(item).model_dump()
            identifiers.append(item.get("id"))
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Registered case identifiers must be unique")
        return value

    def directory(self, case):
        if case.get("task_kind") != TASK_KIND:
            return super().directory(case)
        return reviewed_directory(self, case)

    def get(self, identifier):
        case = super().get(identifier)
        if case.get("task_kind") == TASK_KIND:
            self.verify(case)
        return case

    def verify(self, case):
        if case.get("task_kind") != TASK_KIND:
            return super().verify(case)
        return verify_reviewed_case(self, case)


def validate_reviewed_case(case):
    """Validate strict server-owned metadata before adding a registry entry."""
    return ReviewedTask.model_validate(case).model_dump()


def reviewed_directory(registry, case):
    """Resolve a reviewed task using only the registry's trusted runtime root."""
    task = ReviewedTask.model_validate(case)
    root = Path(registry.runtime) / "cases"
    _reject_link_components(root)
    directory = root / task.id
    _reject_link_components(directory)
    if not directory.resolve().is_relative_to(root.resolve()):
        raise ValueError("Registered task escapes the server-owned case root")
    return directory


def verify_reviewed_case(registry, case):
    """Validate a reviewed task using either this adapter or base CaseRegistry.

    A caller integrating this into an existing registry must route only the
    explicit task kind here and validate its manifest before exposing entries.
    This helper does not mutate a manifest or mark an unqualified entry ready.
    """
    task = ReviewedTask.model_validate(case)
    if not task.qualified:
        raise HTTPException(409, "Task has not passed independent baseline qualification")
    directory = reviewed_directory(registry, case)
    if shutil.disk_usage(registry.runtime).free < 4 * 1024**3:
        raise ValueError("Storage reserve below 4GiB; investigation refused")
    size = sum(p.stat().st_size for p in registry.runtime.rglob("*")
               if p.is_file() and not p.is_symlink())
    if size > 6 * 1024**3:
        raise ValueError("Investigation runtime exceeds 6GiB storage budget")
    source = directory / "source"
    _plain_tree(source)
    if tree_hash(source) != task.source_digest:
        raise ValueError("Pinned source snapshot mismatch")
    for name in task.entry_files:
        target = source_path(source, task.approved_prefix, name)
        _regular_file(target, 250_000)
        if task.entry_lines[name] > len(target.read_text().splitlines()):
            raise ValueError("Provided source entry line exceeds the pinned file")
    verification = ""
    for name, expected in (("test.patch", task.verification_files.test_patch),
                           ("verify.py", task.verification_files.verify_py)):
        path = directory / name
        _regular_file(path, MAX_MANIFEST_BYTES)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Sealed verification file mismatch")
        verification += path.read_text()
    if hashlib.sha256(verification.encode()).hexdigest() != task.verification_digest:
        raise ValueError("Verification material mismatch")
    receipts = []
    baseline = directory / "baseline"
    _reject_link_components(baseline)
    for suite in ("regression", "existing"):
        path = baseline / (suite + ".json")
        _regular_file(path, MAX_RECEIPT_BYTES)
        if hashlib.sha256(path.read_bytes()).hexdigest() != getattr(task.baseline_receipts, suite):
            raise ValueError("Captured baseline receipt mismatch")
        receipt = BaselineReceipt.model_validate(_load_json(path, MAX_RECEIPT_BYTES))
        if receipt.suite != suite or receipt.task_id != task.id:
            raise ValueError("Baseline receipt belongs to another task or suite")
        for field in ("revision", "source_digest", "verification_digest", "image", "environment_digest", "command"):
            if getattr(receipt, field) != getattr(task, field):
                raise ValueError("Baseline receipt binding mismatch: " + field)
        receipts.append(receipt)
    if receipts[0].run_id != receipts[1].run_id:
        raise ValueError("Baseline suites must belong to the same independent qualification run")
    # No reference.patch operation occurs here. Unresolved cases need none.
