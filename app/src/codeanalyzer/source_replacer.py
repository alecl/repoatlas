from typing import Dict, List, Optional, Tuple

from app.src.logging import logger

from .models import ElementType, ReferenceResolutionStatus, UnresolvedReference


class SourceReplacer:
    """
    Apply removals (methods/comments) and replacements (constants) to source code
    in one pass, preserving byte‐offset correctness.
    """

    @staticmethod
    def apply_resolutions(
        source_code: str,
        resolve_constants: bool,
        removal_ops: list[tuple[int, int]],
        resolved_references: list[UnresolvedReference],
        include_element_types: list[ElementType] | None = None,
        include_methods: dict[str, list[str]] | None = None,
    ) -> str:
        """
        Args:
            source_code: Original source text
            resolve_constants: Whether to apply constant replacements
            removal_ops: Byte‐ranges to delete (start,end)
            resolved_references: Fully‐resolved references with offsets
            include_element_types: If given, only replace refs of these types
            include_methods: If given, only replace in these methods per class
        """
        logger.debug("SourceReplacer.apply_resolutions: removal_ops=%s", removal_ops)

        # Build unified ops list: (start, end, replacement_bytes)
        ops: list[tuple[int, int, bytes]] = []

        # First, merge overlapping removal operations to prevent conflicts
        merged_removals = SourceReplacer._merge_overlapping_ranges(removal_ops)
        logger.debug("Merged removal_ops: %s", merged_removals)

        # Add merged removals (always apply method/comment filtering)
        for start, end in merged_removals:
            ops.append((start, end, b""))

        logger.debug("After removals, ops=%s", ops)

        # Add replacements only if resolve_constants is True
        if resolve_constants:
            # Add replacements, but only if they don't fall within a removal range
            for ref in resolved_references:
                loc = ref.location
                if (
                    ref.resolution_status == ReferenceResolutionStatus.FULLY_RESOLVED
                    and loc.source_start_offset is not None
                    and loc.source_end_offset is not None
                    and (
                        include_element_types is None or loc.element_type in include_element_types
                    )
                    and not (
                        include_methods
                        and loc.element_type
                        in (ElementType.METHOD_ANNOTATION, ElementType.METHOD_BODY)
                        and loc.class_name in include_methods
                        and loc.element_name not in include_methods[loc.class_name]
                    )
                ):
                    # Check if this replacement falls within a removal range
                    replacement_start = loc.source_start_offset
                    replacement_end = loc.source_end_offset

                    is_within_removal = False
                    for removal_start, removal_end in merged_removals:
                        if (
                            removal_start <= replacement_start < removal_end
                            or removal_start < replacement_end <= removal_end
                            or (
                                replacement_start <= removal_start
                                and replacement_end >= removal_end
                            )
                        ):
                            is_within_removal = True
                            logger.debug(
                                "Skipping replacement (%d, %d) as it overlaps with removal (%d, %d)",
                                replacement_start,
                                replacement_end,
                                removal_start,
                                removal_end,
                            )
                            break

                    if not is_within_removal:
                        # wrap the resolved value in double-quotes for valid Java string literal
                        repl_value = (
                            f'"{ref.resolved_value}"' if ref.resolved_value is not None else ""
                        )
                        repl = repl_value.encode("utf-8")
                        ops.append((replacement_start, replacement_end, repl))
        else:
            logger.debug("Skipping constant replacements as resolve_constants=False")

        logger.debug("After replacements, ops=%s", ops)

        # Apply in descending start order
        ops.sort(key=lambda x: x[0], reverse=True)
        logger.debug("Sorted ops for application: %s", ops)

        buf = source_code.encode("utf-8")
        for s, e, r in ops:
            if s <= e <= len(buf):  # Bounds check
                buf = buf[:s] + r + buf[e:]
            else:
                logger.warning(
                    "Skipping invalid operation: (%d, %d) on buffer of length %d",
                    s,
                    e,
                    len(buf),
                )

        return buf.decode("utf-8")

    @staticmethod
    def _merge_overlapping_ranges(
        ranges: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """
        Merge overlapping ranges to prevent conflicts.

        Args:
            ranges: List of (start, end) tuples

        Returns:
            List of merged (start, end) tuples with no overlaps
        """
        if not ranges:
            return []

        # Sort by start position
        sorted_ranges = sorted(ranges)
        merged = [sorted_ranges[0]]

        for current_start, current_end in sorted_ranges[1:]:
            last_start, last_end = merged[-1]

            # If ranges overlap or are adjacent, merge them
            if current_start <= last_end:
                # Extend the last range to include the current one
                merged[-1] = (last_start, max(last_end, current_end))
            else:
                # No overlap, add as new range
                merged.append((current_start, current_end))

        return merged
