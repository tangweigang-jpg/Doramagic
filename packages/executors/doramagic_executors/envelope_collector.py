"""EnvelopeCollector -- fan-in aggregator for worker extraction results.

Filters, sorts, and normalizes RepoExtractionEnvelopes before synthesis.

WHY min_confidence=0.3: even low-confidence extractions may contain valuable
WHY or UNSAID items. The threshold only filters truly failed extractions.
Synthesis handles weighting by confidence, not the collector.
"""

from __future__ import annotations

from doramagic_contracts.worker import CollectionResult, RepoExtractionEnvelope


class EnvelopeCollector:
    """Collect and filter fan-out worker results."""

    def collect(
        self,
        envelopes: list[RepoExtractionEnvelope],
        min_confidence: float = 0.3,
    ) -> CollectionResult:
        """Filter, sort, and return qualified envelopes for synthesis.

        1. Filter out failed envelopes
        2. Filter out low-confidence envelopes
        3. Sort by confidence (highest first)
        4. Track filtered-out envelopes for degraded reporting
        """
        # Filter by status
        valid = [e for e in envelopes if e.status != "failed"]

        # Filter by confidence
        qualified = [e for e in valid if e.extraction_confidence >= min_confidence]

        # Sort by confidence descending
        qualified.sort(key=lambda e: e.extraction_confidence, reverse=True)

        # Collect filtered-out envelopes
        qualified_ids = {e.worker_id for e in qualified}
        filtered_out = [e for e in envelopes if e.worker_id not in qualified_ids]

        return CollectionResult(
            qualified_envelopes=qualified,
            filtered_envelopes=filtered_out,
            total_workers=len(envelopes),
            successful_workers=len(valid),
            qualified_workers=len(qualified),
        )
