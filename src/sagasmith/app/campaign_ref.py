"""Resolve user-facing campaign references to campaign directories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sagasmith.app.campaign import open_campaign, slugify
from sagasmith.app.paths import CampaignPaths
from sagasmith.schemas.campaign import CampaignManifest


@dataclass(frozen=True)
class OpenedCampaign:
    """A validated campaign opened from a user-facing reference."""

    paths: CampaignPaths
    manifest: CampaignManifest


def open_campaign_ref(ref: Path, *, search_root: Path | None = None) -> OpenedCampaign:
    """Open a campaign from a path, slug, or display name.

    Direct paths keep their existing strict behavior. For a single-part missing
    relative path, treat the value as a campaign reference and try:
    1. ``./<slugified reference>``
    2. immediate child campaign directories whose manifest slug or display-name
       slug matches the reference
    """

    root = Path.cwd() if search_root is None else search_root

    if search_root is not None and not ref.is_absolute() and len(ref.parts) == 1:
        rooted_ref = root / ref
        try:
            paths, manifest = open_campaign(rooted_ref)
            return OpenedCampaign(paths=paths, manifest=manifest)
        except ValueError as exc:
            if rooted_ref.exists():
                raise exc

    try:
        paths, manifest = open_campaign(ref)
        return OpenedCampaign(paths=paths, manifest=manifest)
    except ValueError as exc:
        direct_error = exc

    if ref.exists() or ref.is_absolute() or len(ref.parts) != 1:
        raise direct_error

    wanted_slug = slugify(str(ref))
    slug_path = root / wanted_slug
    if slug_path != ref:
        try:
            paths, manifest = open_campaign(slug_path)
            return OpenedCampaign(paths=paths, manifest=manifest)
        except ValueError as exc:
            if slug_path.exists():
                raise exc
            pass

    matches: list[OpenedCampaign] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if not child.is_dir() or not (child / "campaign.toml").is_file():
            continue
        try:
            paths, manifest = open_campaign(child)
        except ValueError:
            continue
        if manifest.campaign_slug == wanted_slug or slugify(manifest.campaign_name) == wanted_slug:
            matches.append(OpenedCampaign(paths=paths, manifest=manifest))

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        roots = ", ".join(str(match.paths.root) for match in matches)
        raise ValueError(f"campaign reference '{ref}' is ambiguous: {roots}")

    raise direct_error
