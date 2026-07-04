"""Maintain an append-only in-memory SHA-256 ledger of proof packets."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.engine.proof import ProofPacket
from app.models import canonical_json_hash


_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_GENESIS_HASH = "0" * 64


def _require_sha256_hex(value: str, field_name: str) -> str:
    """Reject values that are not lowercase SHA-256 hex digests."""

    if _SHA256_HEX_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a 64-character lowercase hex SHA-256 string")
    return value


class LedgerError(RuntimeError):
    """Signal invalid ledger state or operations that break the proof chain."""


class LedgerEntry(BaseModel):
    """Represent one append-only ledger row linking a proof packet into the chain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int
    run_id: str
    packet_hash: str
    previous_hash: str
    entry_hash: str

    @field_validator("index")
    @classmethod
    def validate_index(cls, value: int) -> int:
        """Reject negative ledger indices."""

        if value < 0:
            raise ValueError("index must be >= 0")
        return value

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        """Reject blank run identifiers."""

        if not value.strip():
            raise ValueError("run_id cannot be empty")
        return value.strip()

    @field_validator("packet_hash", "previous_hash", "entry_hash")
    @classmethod
    def validate_hash_fields(cls, value: str, info: object) -> str:
        """Require SHA-256 hex digests for all chain-linked hash fields."""

        return _require_sha256_hex(value, info.field_name)


def compute_entry_hash(index: int, run_id: str, packet_hash: str, previous_hash: str) -> str:
    """Hash the ledger linkage fields so packet order becomes tamper-evident."""

    return canonical_json_hash(
        {
            "index": index,
            "run_id": run_id,
            "packet_hash": packet_hash,
            "previous_hash": previous_hash,
        }
    )


def create_ledger_entry(
    index: int,
    run_id: str,
    packet_hash: str,
    previous_hash: str,
) -> LedgerEntry:
    """Create and validate one ledger entry from packet linkage data."""

    entry_hash = compute_entry_hash(index, run_id, packet_hash, previous_hash)
    try:
        return LedgerEntry(
            index=index,
            run_id=run_id,
            packet_hash=packet_hash,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )
    except ValidationError as exc:
        raise LedgerError(f"Invalid ledger entry: {exc}") from exc


class HashLedger:
    """Hold an explicit in-memory append-only ledger for proof packets."""

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        """Expose an immutable snapshot of the current ledger contents."""

        return tuple(self._entries)

    @property
    def latest_hash(self) -> str:
        """Return the current chain head or the genesis hash for an empty ledger."""

        if not self._entries:
            return _GENESIS_HASH
        return self._entries[-1].entry_hash

    def append(self, packet: ProofPacket) -> LedgerEntry:
        """Append a proof packet to the chain and return the resulting ledger entry."""

        packet_hash = packet.proof_hash()
        if _SHA256_HEX_RE.fullmatch(packet_hash) is None:
            raise LedgerError("ProofPacket produced an invalid packet hash")

        entry = create_ledger_entry(
            index=len(self._entries),
            run_id=packet.run_id,
            packet_hash=packet_hash,
            previous_hash=self.latest_hash,
        )
        self._entries.append(entry)
        return entry

    def verify_chain(self) -> bool:
        """Recompute the full ledger chain and return whether it remains intact."""

        expected_previous_hash = _GENESIS_HASH
        for expected_index, entry in enumerate(self._entries):
            try:
                validated_entry = LedgerEntry.model_validate(entry.model_dump())
            except ValidationError:
                return False

            if validated_entry.index != expected_index:
                return False
            if validated_entry.previous_hash != expected_previous_hash:
                return False

            expected_entry_hash = compute_entry_hash(
                index=validated_entry.index,
                run_id=validated_entry.run_id,
                packet_hash=validated_entry.packet_hash,
                previous_hash=validated_entry.previous_hash,
            )
            if validated_entry.entry_hash != expected_entry_hash:
                return False

            expected_previous_hash = validated_entry.entry_hash

        return True

    def verify_packet_entry(self, packet: ProofPacket, entry: LedgerEntry) -> bool:
        """Check that a ledger entry still matches the supplied proof packet."""

        try:
            validated_entry = LedgerEntry.model_validate(entry.model_dump())
        except ValidationError:
            return False

        packet_hash = packet.proof_hash()
        if validated_entry.packet_hash != packet_hash:
            return False
        if validated_entry.run_id != packet.run_id:
            return False

        expected_entry_hash = compute_entry_hash(
            index=validated_entry.index,
            run_id=validated_entry.run_id,
            packet_hash=validated_entry.packet_hash,
            previous_hash=validated_entry.previous_hash,
        )
        return validated_entry.entry_hash == expected_entry_hash

    def tamper_entry_for_demo(
        self,
        index: int,
        *,
        packet_hash: str | None = None,
        previous_hash: str | None = None,
    ) -> None:
        """Demo only: replace stored entry fields without recomputing the chain."""

        if index < 0 or index >= len(self._entries):
            raise LedgerError(f"Ledger entry index {index} is out of range")

        updates: dict[str, str] = {}
        if packet_hash is not None:
            updates["packet_hash"] = packet_hash
        if previous_hash is not None:
            updates["previous_hash"] = previous_hash

        self._entries[index] = self._entries[index].model_copy(update=updates)
