from __future__ import annotations

import hashlib
import importlib
import importlib.resources as resources
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, cast
from urllib.parse import quote, urljoin
from urllib.request import urlopen

_PACK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_PACK_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_PROMPTGUARD_INSTALL_HINT = (
    "PromptGuard backend requires the optional dependencies. "
    "Install hint: textguard[promptguard]."
)
_HASH_CHUNK_SIZE = 1024 * 1024
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_SIGNATURE_BYTES = 64 * 1024
_SSH_KEYGEN_TIMEOUT_SECONDS = 10


class PromptGuardBackend(Protocol):
    model_source: str

    def score_text(self, text: str) -> list[float]: ...


@dataclass(frozen=True, slots=True)
class PromptGuardThresholds:
    medium: float = 0.35
    high: float = 0.7
    critical: float = 0.9

    def __post_init__(self) -> None:
        values = (self.medium, self.high, self.critical)
        if any(item < 0.0 or item > 1.0 for item in values):
            raise ValueError("PromptGuard thresholds must stay within [0.0, 1.0]")
        if not self.medium < self.high < self.critical:
            raise ValueError("PromptGuard thresholds must be strictly increasing")

    def tier_for(self, score: float) -> str:
        normalized = min(max(float(score), 0.0), 1.0)
        if normalized >= self.critical:
            return "critical"
        if normalized >= self.high:
            return "high"
        if normalized >= self.medium:
            return "medium"
        return "none"


@dataclass(frozen=True, slots=True)
class PromptGuardModelPackFile:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class PromptGuardModelPackManifest:
    schema_version: str
    type: str
    name: str
    version: str
    created_at: str
    files: tuple[PromptGuardModelPackFile, ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_bytes(cls, payload: bytes) -> PromptGuardModelPackManifest:
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("promptguard_pack_invalid_manifest") from exc
        if not isinstance(data, dict):
            raise ValueError("promptguard_pack_invalid_manifest")

        schema_version = _require_manifest_str(data, "schema_version")
        if schema_version != "1":
            raise ValueError("promptguard_pack_unsupported_schema")
        manifest_type = _require_manifest_str(data, "type")
        if manifest_type != "promptguard_model_pack":
            raise ValueError("promptguard_pack_invalid_manifest")
        name = _require_manifest_str(data, "name")
        if not _PACK_NAME_RE.fullmatch(name):
            raise ValueError("promptguard_pack_invalid_manifest")
        version = _require_manifest_str(data, "version")
        if not _PACK_VERSION_RE.fullmatch(version):
            raise ValueError("promptguard_pack_invalid_manifest")
        created_at = _require_manifest_str(data, "created_at")
        files = _parse_manifest_files(data.get("files"))
        provenance = _require_manifest_dict(data, "provenance")
        runtime = _require_manifest_dict(data, "runtime")
        return cls(
            schema_version=schema_version,
            type=manifest_type,
            name=name,
            version=version,
            created_at=created_at,
            files=tuple(files),
            provenance=provenance,
            runtime=runtime,
        )


@dataclass(frozen=True, slots=True)
class PromptGuardModelPackInspection:
    valid: bool
    reason: str
    pack_dir: Path
    payload_dir: Path | None = None
    signer: str = ""
    manifest: PromptGuardModelPackManifest | None = None


@dataclass(frozen=True, slots=True)
class PromptGuardModelSpec:
    name: str
    repo_id: str
    manifest_url: str
    signature_url: str
    file_base_url: str


PROMPTGUARD_MODELS: dict[str, PromptGuardModelSpec] = {
    "promptguard2": PromptGuardModelSpec(
        name="promptguard2",
        repo_id="shisa-ai/promptguard2-onnx",
        manifest_url="https://huggingface.co/shisa-ai/promptguard2-onnx/raw/main/manifest.json",
        signature_url="https://huggingface.co/shisa-ai/promptguard2-onnx/raw/main/manifest.json.sig",
        file_base_url="https://huggingface.co/shisa-ai/promptguard2-onnx/raw/main/",
    ),
}


class OnnxPromptGuardBackend:
    """Local PromptGuard backend using Transformers tokenizer + ONNX Runtime."""

    def __init__(
        self,
        *,
        model_source: str,
        tokenizer: Any,
        config: Any,
        session: Any,
        numpy_module: Any,
        max_length: int = 512,
        stride: int = 64,
        max_segments: int = 8,
    ) -> None:
        self.model_source = model_source
        self._tokenizer = tokenizer
        self._config = config
        self._session = session
        self._np = numpy_module
        self._max_length = max_length
        self._stride = stride
        self._max_segments = max_segments
        self._input_names = tuple(item.name for item in self._session.get_inputs())
        outputs = self._session.get_outputs()
        self._output_name = outputs[0].name if outputs else "logits"

    @classmethod
    def from_local_path(cls, model_path: Path) -> OnnxPromptGuardBackend:
        onnx_path = _resolve_promptguard_onnx_path(model_path)
        if onnx_path is None:
            raise RuntimeError("PromptGuard ONNX model is missing from the supplied path.")

        np, ort, auto_config, auto_tokenizer = _import_runtime()
        if "CPUExecutionProvider" not in ort.get_available_providers():
            raise RuntimeError("PromptGuard requires onnxruntime CPUExecutionProvider.")

        try:
            tokenizer_loader = cast(Any, auto_tokenizer)
            config_loader = cast(Any, auto_config)
            tokenizer = tokenizer_loader.from_pretrained(
                str(model_path),
                local_files_only=True,
                trust_remote_code=False,
            )
            config = config_loader.from_pretrained(
                str(model_path),
                local_files_only=True,
                trust_remote_code=False,
            )
            session = ort.InferenceSession(
                str(onnx_path),
                providers=["CPUExecutionProvider"],
            )
        except Exception as exc:
            raise RuntimeError(f"PromptGuard model load failed: {exc}") from exc

        return cls(
            model_source=str(model_path),
            tokenizer=tokenizer,
            config=config,
            session=session,
            numpy_module=np,
        )

    def score_text(self, text: str) -> list[float]:
        try:
            batch = self._tokenizer(
                text,
                return_tensors="np",
                truncation=True,
                padding=True,
                max_length=self._max_length,
                stride=self._stride,
                return_overflowing_tokens=True,
            )
        except Exception as exc:
            raise RuntimeError(f"PromptGuard tokenization failed: {exc}") from exc

        payload = dict(batch)
        payload.pop("overflow_to_sample_mapping", None)

        all_scores: list[float] = []
        for model_inputs in self._iter_model_batches(payload):
            input_feed = {
                key: value for key, value in model_inputs.items() if key in self._input_names
            }
            try:
                logits = self._session.run([self._output_name], input_feed)[0]
                probabilities = self._softmax(logits)
            except Exception as exc:
                raise RuntimeError(f"PromptGuard inference failed: {exc}") from exc

            label_count = int(getattr(probabilities, "shape", [0, 0])[-1])
            malicious_index = self._malicious_index(label_count)
            score_tensor = probabilities[:, malicious_index]
            raw_scores = (
                score_tensor.tolist() if hasattr(score_tensor, "tolist") else [score_tensor]
            )
            all_scores.extend(min(max(float(item), 0.0), 1.0) for item in raw_scores)
        return all_scores

    def _iter_model_batches(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        segment_count = self._segment_count(payload)
        if segment_count <= 0 or segment_count <= self._max_segments:
            return [payload]
        return [
            self._slice_batch(payload, start, start + self._max_segments)
            for start in range(0, segment_count, self._max_segments)
        ]

    def _segment_count(self, payload: dict[str, Any]) -> int:
        for value in payload.values():
            shape = getattr(value, "shape", None)
            if shape:
                try:
                    return int(shape[0])
                except (TypeError, ValueError):
                    pass
            if hasattr(value, "__len__") and hasattr(value, "__getitem__"):
                try:
                    return len(value)
                except (TypeError, ValueError):
                    pass
        return 0

    def _slice_batch(self, payload: dict[str, Any], start: int, stop: int) -> dict[str, Any]:
        truncated: dict[str, Any] = {}
        for key, value in payload.items():
            if hasattr(value, "__getitem__"):
                try:
                    truncated[key] = value[start:stop]
                    continue
                except Exception:
                    pass
            truncated[key] = value
        return truncated

    def _malicious_index(self, label_count: int) -> int:
        id2label = getattr(self._config, "id2label", {}) if self._config is not None else {}
        if isinstance(id2label, dict):
            benign_indices: set[int] = set()
            for raw_index, raw_label in id2label.items():
                index = _coerce_label_index(raw_index)
                if index is None:
                    continue
                label = str(raw_label).strip().lower()
                if label == "malicious":
                    return index
                if label == "benign":
                    benign_indices.add(index)
            if label_count == 2 and benign_indices == {0}:
                return 1
        if label_count <= 1:
            return 0
        return 1

    def _softmax(self, logits: Any) -> Any:
        array = self._np.asarray(logits, dtype="float32")
        shifted = array - array.max(axis=-1, keepdims=True)
        exponents = self._np.exp(shifted)
        return exponents / exponents.sum(axis=-1, keepdims=True)


def load_promptguard_backend(
    model_path: Path,
    *,
    allowed_signers_path: Path | None = None,
) -> PromptGuardBackend:
    resolved_path = model_path.expanduser()
    if not resolved_path.exists():
        raise RuntimeError(f"PromptGuard model path does not exist: {resolved_path}")
    if not resolved_path.is_dir():
        raise RuntimeError(f"PromptGuard model path is not a directory: {resolved_path}")

    runtime_model_path = resolved_path
    if (resolved_path / "manifest.json").is_file():
        with _resolved_allowed_signers_path(allowed_signers_path) as allowed_path:
            inspection = inspect_promptguard_model_pack(
                resolved_path,
                allowed_signers_path=allowed_path,
            )
        if not inspection.valid or inspection.payload_dir is None:
            raise RuntimeError(
                f"PromptGuard model pack verification failed: {inspection.reason}"
            )
        runtime_model_path = inspection.payload_dir

    return OnnxPromptGuardBackend.from_local_path(runtime_model_path)


def inspect_promptguard_model_pack(
    pack_dir: Path,
    *,
    allowed_signers_path: Path,
) -> PromptGuardModelPackInspection:
    manifest_path = pack_dir / "manifest.json"
    signature_path = pack_dir / "manifest.json.sig"
    if not manifest_path.is_file():
        return PromptGuardModelPackInspection(
            valid=False,
            reason="promptguard_pack_manifest_missing",
            pack_dir=pack_dir,
        )

    try:
        manifest = PromptGuardModelPackManifest.from_bytes(
            _read_capped_file_bytes(
                manifest_path,
                max_bytes=_MAX_MANIFEST_BYTES,
                reason="promptguard_pack_manifest_too_large",
            )
        )
    except (OSError, ValueError):
        return PromptGuardModelPackInspection(
            valid=False,
            reason="promptguard_pack_invalid_manifest",
            pack_dir=pack_dir,
        )

    if not signature_path.is_file():
        return PromptGuardModelPackInspection(
            valid=False,
            reason="promptguard_pack_signature_missing",
            pack_dir=pack_dir,
            manifest=manifest,
        )
    if not allowed_signers_path.is_file():
        return PromptGuardModelPackInspection(
            valid=False,
            reason="promptguard_pack_trust_store_missing",
            pack_dir=pack_dir,
            manifest=manifest,
        )

    try:
        verified, signer = _verify_signature(
            manifest_path=manifest_path,
            signature_path=signature_path,
            allowed_signers_path=allowed_signers_path,
        )
    except RuntimeError as exc:
        return PromptGuardModelPackInspection(
            valid=False,
            reason=str(exc),
            pack_dir=pack_dir,
            manifest=manifest,
        )
    if not verified:
        return PromptGuardModelPackInspection(
            valid=False,
            reason="promptguard_pack_signature_verification_failed",
            pack_dir=pack_dir,
            manifest=manifest,
        )

    files_valid, files_reason = _validate_manifest_files(pack_dir=pack_dir, manifest=manifest)
    if not files_valid:
        return PromptGuardModelPackInspection(
            valid=False,
            reason=files_reason,
            pack_dir=pack_dir,
            signer=signer,
            manifest=manifest,
        )

    payload_dir = pack_dir / "payload"
    if not payload_dir.is_dir():
        return PromptGuardModelPackInspection(
            valid=False,
            reason="promptguard_pack_payload_missing",
            pack_dir=pack_dir,
            signer=signer,
            manifest=manifest,
        )

    return PromptGuardModelPackInspection(
        valid=True,
        reason="ok",
        pack_dir=pack_dir,
        payload_dir=payload_dir,
        signer=signer,
        manifest=manifest,
    )


def fetch_promptguard_model(
    model_name: str,
    *,
    install_dir: Path | None = None,
    allowed_signers_path: Path | None = None,
) -> Path:
    try:
        spec = PROMPTGUARD_MODELS[model_name]
    except KeyError as exc:
        supported = ", ".join(sorted(PROMPTGUARD_MODELS))
        raise ValueError(
            f"Unsupported PromptGuard model: {model_name!r}. Supported: {supported}"
        ) from exc

    destination = (
        install_dir.expanduser() if install_dir is not None else default_model_dir(model_name)
    )
    destination.parent.mkdir(parents=True, exist_ok=True)

    manifest_bytes = _download_bytes(spec.manifest_url, max_bytes=_MAX_MANIFEST_BYTES)
    signature_bytes = _download_bytes(spec.signature_url, max_bytes=_MAX_SIGNATURE_BYTES)

    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=f".{model_name}-") as temp_dir:
        staging_root = Path(temp_dir) / "pack"
        staging_root.mkdir()
        manifest_path = staging_root / "manifest.json"
        signature_path = staging_root / "manifest.json.sig"
        manifest_path.write_bytes(manifest_bytes)
        signature_path.write_bytes(signature_bytes)

        with _resolved_allowed_signers_path(allowed_signers_path) as allowed_path:
            try:
                verified, _signer = _verify_signature(
                    manifest_path=manifest_path,
                    signature_path=signature_path,
                    allowed_signers_path=allowed_path,
                )
            except RuntimeError as exc:
                raise RuntimeError(
                    f"PromptGuard model pack verification failed: {exc}"
                ) from exc
            if not verified:
                raise RuntimeError(
                    "PromptGuard model pack verification failed: "
                    "promptguard_pack_signature_verification_failed"
                )

            try:
                manifest = PromptGuardModelPackManifest.from_bytes(manifest_bytes)
            except ValueError as exc:
                raise RuntimeError(
                    "PromptGuard model pack verification failed: promptguard_pack_invalid_manifest"
                ) from exc

            for record in manifest.files:
                target_path = staging_root / record.path
                file_url = urljoin(spec.file_base_url, quote(record.path, safe="/"))
                _download_file(
                    file_url,
                    target_path,
                    expected_sha256=record.sha256,
                    expected_size=record.size,
                )

            inspection = inspect_promptguard_model_pack(
                staging_root,
                allowed_signers_path=allowed_path,
            )
            if not inspection.valid:
                raise RuntimeError(
                    f"PromptGuard model pack verification failed: {inspection.reason}"
                )

        if destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        shutil.move(str(staging_root), str(destination))

    return destination


def default_model_dir(model_name: str) -> Path:
    return xdg_data_home() / "textguard" / "models" / model_name


def xdg_data_home() -> Path:
    raw = os.environ.get("XDG_DATA_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".local" / "share"


def scores_to_semantic_result(
    scores: list[float],
    *,
    classifier_id: str = "promptguard-v2",
    thresholds: PromptGuardThresholds | None = None,
) -> tuple[float, str, str]:
    active_thresholds = thresholds or PromptGuardThresholds()
    score = max((float(item) for item in scores), default=0.0)
    return score, active_thresholds.tier_for(score), classifier_id


def _import_runtime() -> tuple[Any, Any, Any, Any]:
    try:
        np = importlib.import_module("numpy")
        ort = importlib.import_module("onnxruntime")
        transformers = importlib.import_module("transformers")
    except ImportError as exc:
        raise RuntimeError(_PROMPTGUARD_INSTALL_HINT) from exc
    transformers_module = cast(Any, transformers)
    auto_config = transformers_module.AutoConfig
    auto_tokenizer = transformers_module.AutoTokenizer
    return np, ort, auto_config, auto_tokenizer


def _resolve_promptguard_onnx_path(model_path: Path) -> Path | None:
    candidates = (
        model_path / "model.onnx",
        model_path / "onnx" / "model.onnx",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    root_matches = sorted(model_path.glob("*.onnx"))
    if len(root_matches) == 1:
        return root_matches[0]
    nested_dir = model_path / "onnx"
    nested_matches = sorted(nested_dir.glob("*.onnx")) if nested_dir.is_dir() else []
    if len(nested_matches) == 1:
        return nested_matches[0]
    return None


def _coerce_label_index(raw_index: object) -> int | None:
    if isinstance(raw_index, int):
        return raw_index
    if isinstance(raw_index, str):
        try:
            return int(raw_index)
        except ValueError:
            return None
    return None


def _require_manifest_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("promptguard_pack_invalid_manifest")
    return value


def _require_manifest_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError("promptguard_pack_invalid_manifest")
    return dict(value)


def _parse_manifest_files(value: object) -> list[PromptGuardModelPackFile]:
    if not isinstance(value, list):
        raise ValueError("promptguard_pack_invalid_manifest")
    files: list[PromptGuardModelPackFile] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("promptguard_pack_invalid_manifest")
        path = item.get("path")
        sha256 = item.get("sha256")
        size = item.get("size")
        if not isinstance(path, str) or not _safe_relative_path(path):
            raise ValueError("promptguard_pack_invalid_manifest")
        if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("promptguard_pack_invalid_manifest")
        if not isinstance(size, int) or size < 0:
            raise ValueError("promptguard_pack_invalid_manifest")
        files.append(PromptGuardModelPackFile(path=path, sha256=sha256, size=size))
    return files


def _safe_relative_path(value: str) -> bool:
    try:
        path = PurePosixPath(value)
    except ValueError:
        return False
    return not path.is_absolute() and ".." not in path.parts


def _validate_manifest_files(
    *,
    pack_dir: Path,
    manifest: PromptGuardModelPackManifest,
) -> tuple[bool, str]:
    declared = {item.path: item for item in manifest.files}
    if any(not _safe_relative_path(path) for path in declared):
        return False, "promptguard_pack_unsafe_relative_path"

    actual: dict[str, Path] = {}
    for path in sorted(pack_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {"manifest.json", "manifest.json.sig"}:
            continue
        relative = path.relative_to(pack_dir).as_posix()
        if not _safe_relative_path(relative):
            return False, "promptguard_pack_unsafe_relative_path"
        actual[relative] = path

    if set(actual) != set(declared):
        return False, "promptguard_pack_file_set_mismatch"

    for relative, record in declared.items():
        actual_path = actual[relative]
        if actual_path.stat().st_size != record.size:
            return False, "promptguard_pack_file_size_mismatch"
        if _hash_file(actual_path) != record.sha256:
            return False, "promptguard_pack_file_hash_mismatch"
    return True, "ok"


def _download_bytes(url: str, *, max_bytes: int) -> bytes:
    payload = bytearray()
    total = 0
    try:
        with urlopen(url, timeout=120) as response:
            while True:
                remaining = max_bytes - total + 1
                if remaining <= 0:
                    raise RuntimeError(
                        "PromptGuard download failed for "
                        f"{url}: response exceeded {max_bytes} bytes"
                    )
                chunk = response.read(min(_HASH_CHUNK_SIZE, remaining))
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError(
                        "PromptGuard download failed for "
                        f"{url}: response exceeded {max_bytes} bytes"
                    )
                payload.extend(chunk)
    except OSError as exc:
        raise RuntimeError(f"PromptGuard download failed for {url}: {exc}") from exc
    return bytes(payload)


def _download_file(
    url: str,
    destination: Path,
    *,
    expected_sha256: str,
    expected_size: int,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()
    total = 0
    try:
        with urlopen(url, timeout=120) as response, destination.open("wb") as handle:
            while True:
                remaining = expected_size - total + 1
                if remaining <= 0:
                    raise RuntimeError(
                        "PromptGuard model pack verification failed: "
                        "promptguard_pack_file_size_mismatch"
                    )
                chunk = response.read(min(_HASH_CHUNK_SIZE, remaining))
                if not chunk:
                    break
                total += len(chunk)
                if total > expected_size:
                    raise RuntimeError(
                        "PromptGuard model pack verification failed: "
                        "promptguard_pack_file_size_mismatch"
                    )
                hasher.update(chunk)
                handle.write(chunk)
    except OSError as exc:
        raise RuntimeError(f"PromptGuard download failed for {url}: {exc}") from exc

    if total != expected_size:
        raise RuntimeError(
            "PromptGuard model pack verification failed: promptguard_pack_file_size_mismatch"
        )
    if hasher.hexdigest() != expected_sha256:
        raise RuntimeError(
            "PromptGuard model pack verification failed: promptguard_pack_file_hash_mismatch"
        )


def _allowed_signer_principals(path: Path) -> list[str]:
    principals: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        principals.append(stripped.split()[0])
    return principals


def _verify_signature(
    *,
    manifest_path: Path,
    signature_path: Path,
    allowed_signers_path: Path,
) -> tuple[bool, str]:
    principals = _allowed_signer_principals(allowed_signers_path)
    if not principals:
        return False, ""
    try:
        manifest_text = _read_capped_file_bytes(
            manifest_path,
            max_bytes=_MAX_MANIFEST_BYTES,
            reason="promptguard_pack_manifest_too_large",
        ).decode("utf-8")
    except OSError as exc:
        raise RuntimeError("promptguard_pack_manifest_unreadable") from exc
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    except UnicodeDecodeError as exc:
        raise RuntimeError("promptguard_pack_invalid_manifest") from exc
    for principal in principals:
        try:
            result = subprocess.run(
                [
                    "ssh-keygen",
                    "-Y",
                    "verify",
                    "-f",
                    str(allowed_signers_path),
                    "-I",
                    principal,
                    "-n",
                    "file",
                    "-s",
                    str(signature_path),
                ],
                input=manifest_text,
                check=False,
                capture_output=True,
                text=True,
                timeout=_SSH_KEYGEN_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("promptguard_pack_verifier_unavailable") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("promptguard_pack_verifier_timeout") from exc
        except OSError as exc:
            raise RuntimeError("promptguard_pack_verifier_unavailable") from exc
        if result.returncode == 0:
            return True, principal
    return False, ""


@contextmanager
def _resolved_allowed_signers_path(override: Path | None) -> Iterator[Path]:
    if override is not None:
        yield override.expanduser()
        return
    resource = resources.files("textguard").joinpath("data").joinpath("allowed_signers")
    with resources.as_file(resource) as resource_path:
        yield resource_path


def _read_capped_file_bytes(path: Path, *, max_bytes: int, reason: str) -> bytes:
    total = 0
    payload = bytearray()
    with path.open("rb") as handle:
        while True:
            remaining = max_bytes - total + 1
            if remaining <= 0:
                raise ValueError(reason)
            chunk = handle.read(min(_HASH_CHUNK_SIZE, remaining))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(reason)
            payload.extend(chunk)
    return bytes(payload)


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_HASH_CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()
