"""Transform qualitative BOF records into structured analysis data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

import pandas as pd

from .config import (
    ACTION_STATUS_PATTERNS,
    COLUMN_ALIASES,
    GOVERNMENT_PROPOSER_PATTERNS,
    TECHNOLOGY_CLUSTER_PATTERNS,
)


def _normalize(text: object) -> str:
    if text is None:
        return ""
    return str(text).strip()


def _to_lower(text: object) -> str:
    return _normalize(text).lower()


def _match_first_category(text: str, mapping: dict[str, list[str]], fallback: str) -> str:
    for category, patterns in mapping.items():
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return category
    return fallback


def _match_multiple_categories(text: str, mapping: dict[str, list[str]]) -> list[str]:
    hits: list[str] = []
    for category, patterns in mapping.items():
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                hits.append(category)
                break
    return hits


@dataclass
class BOFTransformer:
    """Reusable transformer for a single CSV or Excel workbook."""

    input_path: Path

    def load(self) -> pd.DataFrame:
        suffix = self.input_path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(self.input_path)
        if suffix in {".xlsx", ".xls"}:
            workbook = pd.read_excel(self.input_path, sheet_name=None)
            candidate_frames: list[pd.DataFrame] = []
            for sheet_name, sheet_df in workbook.items():
                if sheet_df.empty:
                    continue
                normalized_cols = [str(col).lower().strip() for col in sheet_df.columns]
                has_subject = any("subject" in col for col in normalized_cols)
                has_action = any("action" in col or "disposition" in col for col in normalized_cols)
                if has_subject and has_action:
                    copy_df = sheet_df.copy()
                    copy_df["source_sheet"] = sheet_name
                    candidate_frames.append(copy_df)
            if candidate_frames:
                return pd.concat(candidate_frames, ignore_index=True)
            # Fall back to first sheet if no obvious match.
            first_sheet = next(iter(workbook.values()))
            return first_sheet
        raise ValueError(f"Unsupported file type: {self.input_path.suffix}")

    def _resolve_column(self, columns: Iterable[str], logical_name: str) -> str | None:
        lowered = {col.lower().strip(): col for col in columns}
        aliases = COLUMN_ALIASES.get(logical_name, [logical_name])
        for alias in aliases:
            if alias in lowered:
                return lowered[alias]
        # Fallback to contains-match for messy historical headers.
        for alias in aliases:
            for lowered_col, original_col in lowered.items():
                if alias in lowered_col:
                    return original_col
        return None

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        subject_col = self._resolve_column(df.columns, "subject")
        action_col = self._resolve_column(df.columns, "action")
        reasoning_col = self._resolve_column(df.columns, "reasoning")
        proposer_col = self._resolve_column(df.columns, "proposer")
        year_col = self._resolve_column(df.columns, "year")

        if subject_col is None or action_col is None:
            raise ValueError(
                "Required columns missing. Could not find Subject and Action columns."
            )

        out = df.copy()
        out["subject_text"] = out[subject_col].map(_normalize)
        out["action_text"] = out[action_col].map(_normalize)
        out["reasoning_text"] = out[reasoning_col].map(_normalize) if reasoning_col else ""
        out["proposer_text"] = out[proposer_col].map(_normalize) if proposer_col else ""

        # Status classification from Action vernacular.
        out["status"] = out["action_text"].map(
            lambda t: _match_first_category(_to_lower(t), ACTION_STATUS_PATTERNS, "Investigating")
        )

        # Technology taxonomy from Subject.
        out["technology_clusters"] = out["subject_text"].map(
            lambda t: _match_multiple_categories(_to_lower(t), TECHNOLOGY_CLUSTER_PATTERNS)
        )
        out["primary_cluster"] = out["technology_clusters"].map(
            lambda tags: tags[0] if tags else "Other/Unclassified"
        )

        # Proposer type using proposer text and subject/reasoning fallback.
        out["proposer_type"] = out.apply(self._classify_proposer_type, axis=1)

        # Year extraction supports explicit year field or date in any available field.
        if year_col:
            out["year"] = out[year_col].map(self._extract_year)
        else:
            out["year"] = out.apply(
                lambda row: self._extract_year(
                    " ".join(
                        [
                            _normalize(row.get("subject_text", "")),
                            _normalize(row.get("action_text", "")),
                            _normalize(row.get("reasoning_text", "")),
                        ]
                    )
                ),
                axis=1,
            )

        out["is_approved"] = (out["status"] == "Approved").astype(int)
        out["is_rejected"] = (out["status"] == "Rejected").astype(int)
        out["is_investigating"] = (out["status"] == "Investigating").astype(int)
        return out

    def _classify_proposer_type(self, row: pd.Series) -> str:
        source_text = " ".join(
            [
                _normalize(row.get("proposer_text", "")),
                _normalize(row.get("subject_text", "")),
                _normalize(row.get("reasoning_text", "")),
            ]
        ).lower()
        for pattern in GOVERNMENT_PROPOSER_PATTERNS:
            if re.search(pattern, source_text, flags=re.IGNORECASE):
                return "Government"
        if source_text:
            return "Private"
        return "Unknown"

    @staticmethod
    def _extract_year(value: object) -> int | pd.NA:
        text = _normalize(value)
        match = re.search(r"\b(18\d{2}|19\d{2}|20\d{2})\b", text)
        if match:
            return int(match.group(1))
        return pd.NA

    @staticmethod
    def approval_ratio_by_cluster_1901(df: pd.DataFrame) -> pd.DataFrame:
        yearly = df[df["year"] == 1901].copy()
        grouped = (
            yearly.groupby("primary_cluster", dropna=False)
            .agg(
                submissions=("primary_cluster", "count"),
                approved=("is_approved", "sum"),
            )
            .reset_index()
        )
        grouped["approval_to_submission_ratio"] = grouped["approved"] / grouped["submissions"]
        return grouped.sort_values("approval_to_submission_ratio", ascending=False)

    @staticmethod
    def proposer_success_table(df: pd.DataFrame) -> pd.DataFrame:
        grouped = (
            df.groupby(["year", "proposer_type"], dropna=False)
            .agg(submissions=("proposer_type", "count"), approved=("is_approved", "sum"))
            .reset_index()
        )
        grouped["success_rate"] = grouped["approved"] / grouped["submissions"]
        return grouped.sort_values(["year", "success_rate"], ascending=[True, False])


def run_batch_analysis(input_files: list[Path], output_dir: Path) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    transformed_frames: list[pd.DataFrame] = []
    for source_path in input_files:
        transformer = BOFTransformer(input_path=source_path)
        raw = transformer.load()
        transformed = transformer.transform(raw)
        transformed["source_file"] = source_path.name
        transformed_frames.append(transformed)

        transformed.to_csv(output_dir / f"{source_path.stem}_structured.csv", index=False)

    if not transformed_frames:
        raise ValueError("No input files found for analysis.")

    all_data = pd.concat(transformed_frames, ignore_index=True)
    all_data.to_csv(output_dir / "all_structured_records.csv", index=False)

    ratio_1901 = BOFTransformer.approval_ratio_by_cluster_1901(all_data)
    ratio_1901.to_csv(output_dir / "approval_ratio_by_cluster_1901.csv", index=False)

    proposer_rates = BOFTransformer.proposer_success_table(all_data)
    proposer_rates.to_csv(output_dir / "proposer_success_rate_by_year.csv", index=False)
    return all_data
