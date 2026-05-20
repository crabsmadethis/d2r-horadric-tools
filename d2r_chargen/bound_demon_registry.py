"""Validated bound-demon synthesis packages.

The registry is deliberately exact. A package entry means public chargen may
build that one support record from explicit public data; it does not imply a
general monster, generated-name, aura, or source-affix algorithm.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from d2r_chargen.demon_synthesis import (
    ROW20_NO_AFFIX_TAIL_95_115,
    BoundDemonSynthesisFields,
    build_bound_demon_payload,
)


@dataclass(frozen=True)
class BoundDemonSemanticClaims:
    row: str
    generated_name: str | None = None
    aura: str | None = None
    visible_labels: tuple[str, ...] = ()
    combat_stats: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "row": self.row,
            "generated_name": self.generated_name,
            "aura": self.aura,
            "visible_labels": list(self.visible_labels),
            "combat_stats": self.combat_stats,
        }


@dataclass(frozen=True)
class BoundDemonValidatedPackage:
    package_id: str
    summary: str
    enabled: bool
    builder_version: int
    monster_hcidx: int
    monster_seed: int
    bind_metadata: int
    affixes: bytes
    runtime_stats_24_31: bytes = field(default_factory=lambda: bytes(8))
    percent_or_caps_44_51: bytes = field(default_factory=lambda: bytes(8))
    bitfields_64_79: bytes = field(default_factory=lambda: bytes(16))
    post_gf_tail_95_115: bytes = ROW20_NO_AFFIX_TAIL_95_115
    canonicalization_profile: str = ""
    semantic_claims: BoundDemonSemanticClaims = field(
        default_factory=lambda: BoundDemonSemanticClaims(row="validated")
    )
    evidence_level: tuple[str, ...] = ()
    unsupported_dimensions: tuple[str, ...] = ()

    def synthesis_fields(self) -> BoundDemonSynthesisFields:
        return BoundDemonSynthesisFields(
            monster_hcidx=self.monster_hcidx,
            monster_seed=self.monster_seed,
            bind_metadata=self.bind_metadata,
            affixes=self.affixes,
            runtime_stats_24_31=self.runtime_stats_24_31,
            percent_or_caps_44_51=self.percent_or_caps_44_51,
            bitfields_64_79=self.bitfields_64_79,
            post_gf_tail_95_115=self.post_gf_tail_95_115,
        )

    def to_public_dict(self) -> dict[str, object]:
        return {
            "package_id": self.package_id,
            "summary": self.summary,
            "enabled": self.enabled,
            "builder_version": self.builder_version,
            "supported_rows": [self.monster_hcidx],
            "inputs": {
                "monster_hcidx": self.monster_hcidx,
                "monster_seed": f"0x{self.monster_seed:08x}",
                "bind_metadata": self.bind_metadata,
                "affixes_hex": self.affixes.hex(" "),
                "runtime_stats_24_31_hex": self.runtime_stats_24_31.hex(" "),
            },
            "canonicalization_profile": self.canonicalization_profile,
            "semantic_claims": self.semantic_claims.to_dict(),
            "evidence_level": list(self.evidence_level),
            "unsupported_dimensions": list(self.unsupported_dimensions),
        }


_PACKAGES = {
    "row724-black-lancer-seedg-holy-shock-v1": BoundDemonValidatedPackage(
        package_id="row724-black-lancer-seedg-holy-shock-v1",
        summary=(
            "Row 724 Black Lancer seven-affix package with validated "
            "seed/context Holy Shock presentation."
        ),
        enabled=True,
        builder_version=1,
        monster_hcidx=724,
        monster_seed=0x0008F2C8,
        bind_metadata=7,
        affixes=bytes.fromhex("25 1e 07 1c 05 06 1b"),
        runtime_stats_24_31=bytes.fromhex("02 00 00 00 43 00 00 00"),
        canonicalization_profile=(
            "Known supported package; D2R may rewrite volatile runtime bytes "
            "+89..+91 on save/exit."
        ),
        semantic_claims=BoundDemonSemanticClaims(
            row="payload row 724 / Black Lancer support record",
            generated_name="Black Break the Tainted",
            aura="Holy Shock / MonHolyShock level 8; user-visible lightning aura",
        ),
        evidence_level=(
            "scanner-clean",
            "Offline accepted",
            "save/exit preserved follower_count=1",
            "runtime aura observed",
            "user-visible name/aura observed",
        ),
        unsupported_dimensions=(
            "alternate generated names",
            "arbitrary aura flavor selection",
            "visible source-label claims beyond the exact observed package",
            "alternate source-affix tuples",
            "pcount/combat-stat synthesis",
            "other monster rows",
        ),
    )
}


def iter_bound_demon_packages() -> Iterable[BoundDemonValidatedPackage]:
    return tuple(_PACKAGES.values())


def get_bound_demon_package(package_id: str) -> BoundDemonValidatedPackage | None:
    return _PACKAGES.get(package_id)


def list_bound_demon_package_ids(*, enabled_only: bool = True) -> list[str]:
    return [
        package.package_id
        for package in iter_bound_demon_packages()
        if package.enabled or not enabled_only
    ]


def bound_demon_registry_public_report(*, enabled_only: bool = True) -> dict[str, object]:
    packages = [
        package.to_public_dict()
        for package in iter_bound_demon_packages()
        if package.enabled or not enabled_only
    ]
    return {
        "schema": "bound-demon-validated-packages-v1",
        "packages": packages,
    }


def build_bound_demon_package_payload(package_id: str) -> bytes:
    package = get_bound_demon_package(package_id)
    if package is None:
        known = ", ".join(list_bound_demon_package_ids(enabled_only=False))
        raise ValueError(
            f"Unknown bound_demon package_id={package_id!r}. "
            f"Known package ids: {known or '(none)'}"
        )
    if not package.enabled:
        raise ValueError(
            f"bound_demon package_id={package_id!r} is documented but not "
            "enabled for public chargen"
        )
    return build_bound_demon_payload(package.synthesis_fields())
