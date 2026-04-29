"""Phase 7 MemoryPacket assembly — hyphen-named skill directory.

Canonical implementation lives in the underscore-named importable package
(`memory_packet_assembly.logic`). This file exists only because the skill
loader uses the directory name from SKILL.md; all imports should use the
underscore variant.
"""

from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import (
    assemble_memory_packet,
    assemble_memory_packet_stub,
)

__all__ = ["assemble_memory_packet", "assemble_memory_packet_stub"]
