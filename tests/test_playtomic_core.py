from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from playtomic_core import MonitorError, build_club_info, build_club_runs


class ConfiguredClubMetadataTests(unittest.TestCase):
    def test_builds_club_info_without_scraping_the_club_page(self) -> None:
        club_section = {
            "url": "https://playtomic.com/clubs/example-club",
            "sport_id": "PADEL",
            "tenant_id": "tenant-123",
            "name": "Example Club",
            "timezone": "Europe/Warsaw",
            "slug": "example-club",
            "resources": [
                {
                    "resource_id": "court-1",
                    "name": "Court 1",
                    "sport": "PADEL",
                    "features": ["indoor", "double"],
                }
            ],
        }

        with patch("playtomic_core.http_get_text") as http_get_text:
            club = build_club_info(club_section)

        http_get_text.assert_not_called()
        self.assertEqual(club.tenant_id, "tenant-123")
        self.assertEqual(club.timezone, "Europe/Warsaw")
        self.assertEqual(club.resources[0].resource_id, "court-1")
        self.assertEqual(club.resources[0].features, ("indoor", "double"))

    def test_rejects_url_only_config_without_scraping(self) -> None:
        club_section = {
            "url": "https://playtomic.com/clubs/example-club",
            "sport_id": "PADEL",
        }

        with patch("playtomic_core.http_get_text") as http_get_text:
            with self.assertRaisesRegex(MonitorError, "missing configured metadata"):
                build_club_info(club_section)

        http_get_text.assert_not_called()

    def test_shared_config_never_needs_the_club_webpage(self) -> None:
        config_path = Path(__file__).resolve().parents[1] / "config.shared.toml"

        with (
            patch("playtomic_core.http_get_text") as http_get_text,
            patch("playtomic_core.collect_matching_slots", return_value=[]),
        ):
            _, _, club_runs = build_club_runs(config_path)

        http_get_text.assert_not_called()
        self.assertEqual(
            [club_run.club.tenant_id for club_run in club_runs],
            [
                "a8b0e7b9-7db0-4c45-8569-28bf775e9208",
                "a51996c7-343f-4ff5-b6c9-902fbf06ba7a",
            ],
        )


if __name__ == "__main__":
    unittest.main()
