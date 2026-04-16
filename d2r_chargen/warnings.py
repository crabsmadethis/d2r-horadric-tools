"""Pre-encode warning layer for D2R item building.

Collects non-fatal warnings during item building. Warnings are diagnostic
only -- they don't halt the build. The scanner remains the authoritative
deployment gate.
"""


class BuildWarnings:
    """Collects non-fatal warnings during item building.

    Warnings are diagnostic -- they don't halt the build.
    The scanner remains the authoritative deployment gate.
    """

    def __init__(self):
        self.warnings = []

    def warn(self, context, message):
        """Record a warning.

        Args:
            context: Item type code or other identifying string.
            message: Human-readable warning description.
        """
        self.warnings.append((context, message))

    def has_warnings(self):
        """Return True if any warnings were recorded."""
        return len(self.warnings) > 0

    def dump(self):
        """Print all collected warnings to stdout."""
        for ctx, msg in self.warnings:
            print(f"  \u26a0 {ctx}: {msg}")

    def clear(self):
        """Discard all collected warnings."""
        self.warnings.clear()
