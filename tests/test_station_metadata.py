"""Station metadata, the query grammar it drives, and the catalog that uses it."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from terminal_radio.cli import _build_query, build_parser
from terminal_radio.core.config import Settings
from terminal_radio.enums import Band, Genre, Region
from terminal_radio.models import Station
from terminal_radio.services import StationCatalog, search_stations
from terminal_radio.services.custom_stations import CustomStationStore
from terminal_radio.services.station_search import parse_query


def station(slug: str, **overrides: object) -> Station:
    values: dict[str, object] = {
        "slug": slug,
        "name": slug,
        "band": Band.FM,
        "url": "https://example.com/live",
    }
    values.update(overrides)
    return Station(**values)


class StationMetadataModelTests(unittest.TestCase):
    def test_a_station_carries_as_many_regions_genres_and_languages_as_it_needs(
        self,
    ) -> None:
        """A police network is news, traffic and talk at once."""
        item = station(
            "pbs",
            regions=["national", "taipei"],
            genres=["news", "traffic", "talk"],
            languages=["zh-Hant", "nan"],
        )

        self.assertEqual(item.regions, (Region.NATIONAL, Region.TAIPEI))
        self.assertEqual(item.genres, (Genre.NEWS, Genre.TRAFFIC, Genre.TALK))
        self.assertEqual(item.languages, ("zh-Hant", "nan"))

    def test_metadata_is_optional_so_an_older_catalog_still_loads(self) -> None:
        """The fields were added after the catalog shipped without them."""
        item = station("bare")

        self.assertEqual((item.regions, item.genres, item.languages), ((), (), ()))
        self.assertIsNone(item.network)

    def test_a_repeated_entry_is_listed_once_in_the_order_given(self) -> None:
        item = station("dupe", genres=["talk", "news", "talk"])

        self.assertEqual(item.genres, (Genre.TALK, Genre.NEWS))

    def test_a_region_outside_the_closed_set_is_a_load_error(self) -> None:
        """A typo has to fail loudly rather than become unfindable."""
        with self.assertRaises(ValidationError):
            station("bad", regions=["atlantis"])

    def test_a_malformed_language_tag_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            station("bad", languages=["not a tag!"])


class QueryGrammarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stations = (
            station(
                "news-taipei",
                name="臺北新聞台",
                frequency="98.1",
                regions=["taipei"],
                genres=["news", "talk"],
                languages=["zh-Hant"],
                network="某聯播網",
            ),
            station(
                "hakka",
                name="客語電台",
                frequency="105.9",
                regions=["hsinchu"],
                genres=["culture"],
                languages=["hak"],
            ),
            station(
                "news-south",
                name="南部新聞台",
                band=Band.AM,
                frequency="801",
                regions=["tainan"],
                genres=["news"],
                languages=["nan"],
            ),
        )

    def _slugs(self, query: str) -> list[str]:
        return [item.slug for item in search_stations(self.stations, query)]

    def test_terms_naming_different_keys_narrow_the_result(self) -> None:
        self.assertEqual(self._slugs("genre:news region:taipei"), ["news-taipei"])

    def test_terms_naming_the_same_key_widen_it(self) -> None:
        self.assertEqual(
            self._slugs("region:taipei region:tainan"), ["news-taipei", "news-south"]
        )

    def test_a_filter_and_free_text_work_together(self) -> None:
        self.assertEqual(self._slugs("genre:news 客語"), [])
        self.assertEqual(self._slugs("genre:news 南部"), ["news-south"])

    def test_lang_is_accepted_as_shorthand_for_language(self) -> None:
        self.assertEqual(self._slugs("lang:hak"), self._slugs("language:hak"))

    def test_a_network_matches_on_part_of_its_name(self) -> None:
        self.assertEqual(self._slugs("network:聯播"), ["news-taipei"])

    def test_a_value_outside_a_closed_set_matches_nothing(self) -> None:
        """genre:banana is a mistake, not a request for the whole catalog."""
        self.assertEqual(self._slugs("genre:banana"), [])
        self.assertEqual(parse_query("genre:banana").unknown, ("genre:banana",))

    def test_an_unknown_key_is_searched_as_plain_text(self) -> None:
        """A pasted URL carries a colon and still has to be searchable."""
        parsed = parse_query("https://example.com/live")

        self.assertEqual(parsed.text, "https://example.com/live")
        self.assertEqual(parsed.unknown, ())

    def test_an_empty_query_returns_the_whole_catalog(self) -> None:
        self.assertEqual(search_stations(self.stations, "   "), self.stations)

    def test_metadata_is_searchable(self) -> None:
        """A genre nobody wrote in a name is still reachable as free text."""
        self.assertEqual(self._slugs("news"), ["news-taipei", "news-south"])

    def test_a_name_outranks_the_same_word_used_as_a_genre(self) -> None:
        """Somebody typing news wants News98 before everything tagged news."""
        named = station(
            "news98", name="News98", frequency="98.1", genres=["talk"]
        )

        found = search_stations((*self.stations, named), "news")

        self.assertEqual(
            [item.slug for item in found],
            ["news98", "news-taipei", "news-south"],
        )


class BundledCatalogMetadataTests(unittest.TestCase):
    """The shipped catalog has to be complete, or the filters lie."""

    def setUp(self) -> None:
        self.catalog = StationCatalog.from_file(Settings().stations_file)

    def test_every_station_declares_where_it_is_heard(self) -> None:
        missing = [item.slug for item in self.catalog if not item.regions]

        self.assertEqual(missing, [])

    def test_every_station_declares_what_it_broadcasts(self) -> None:
        missing = [item.slug for item in self.catalog if not item.genres]

        self.assertEqual(missing, [])

    def test_every_station_declares_the_language_it_is_heard_in(self) -> None:
        missing = [item.slug for item in self.catalog if not item.languages]

        self.assertEqual(missing, [])

    def test_the_frequencies_of_one_network_are_grouped_under_it(self) -> None:
        """Every police frequency has to answer the same network filter."""
        found = search_stations(self.catalog.all(), "network:警察廣播電臺")

        self.assertEqual(
            sorted(item.slug for item in found),
            sorted(item.slug for item in self.catalog if item.slug.startswith("pbs-")),
        )


class CustomStationMetadataTests(unittest.TestCase):
    def test_metadata_survives_a_write_and_a_read(self) -> None:
        """The hand written TOML has to carry the arrays and the quotes."""
        with tempfile.TemporaryDirectory() as directory:
            store = CustomStationStore(Path(directory) / "custom.toml")
            item = station(
                "custom-1",
                name='引號 " 測試',
                short_name="測試",
                network="某網",
                regions=["taipei", "hualien"],
                genres=["news", "talk"],
                languages=["zh-Hant", "nan"],
            )

            store.save([item])

            self.assertEqual(store.load(), (item,))


class StationsCommandTests(unittest.TestCase):
    def _parse(self, argv: list[str]) -> argparse.Namespace:
        return build_parser(Settings()).parse_args(argv)

    def test_the_flags_are_shorthand_for_the_query_grammar(self) -> None:
        arguments = self._parse(
            ["stations", "--genre", "news", "--region", "taipei", "--band", "AM"]
        )

        self.assertEqual(
            _build_query(arguments), "band:AM genre:news region:taipei"
        )

    def test_a_repeated_flag_widens_the_filter(self) -> None:
        arguments = self._parse(
            ["stations", "--genre", "news", "--genre", "talk"]
        )

        self.assertEqual(_build_query(arguments), "genre:news genre:talk")

    def test_free_text_and_flags_combine(self) -> None:
        arguments = self._parse(["stations", "廣播", "--region", "taipei"])

        self.assertEqual(_build_query(arguments), "廣播 region:taipei")

    def test_a_query_with_no_filters_is_passed_through(self) -> None:
        arguments = self._parse(["stations", "genre:news 台北"])

        self.assertEqual(_build_query(arguments), "genre:news 台北")


class TagLabelTests(unittest.TestCase):
    """Every classification code has to read as a word in both languages."""

    def setUp(self) -> None:
        from terminal_radio.core.i18n import LocaleRepository

        self.locales = LocaleRepository.from_directory(
            Settings().locales_dir, Settings().locale
        )

    def test_every_code_is_named_in_every_language(self) -> None:
        from terminal_radio.tui.labels import label

        for code in self.locales.codes():
            translator = self.locales.translator(code)
            for prefix, values in (
                ("genre", [item.value for item in Genre]),
                ("region", [item.value for item in Region]),
                ("language", ["zh-Hant", "nan", "hak", "en"]),
            ):
                for value in values:
                    with self.subTest(locale=code, tag=f"{prefix}.{value}"):
                        self.assertNotEqual(
                            label(translator, prefix, value),
                            value,
                            f"{prefix}.{value} is untranslated in {code}",
                        )

    def test_the_two_languages_do_not_share_a_name(self) -> None:
        """A key copied across instead of translated is worth catching."""
        from terminal_radio.tui.labels import label

        chinese = self.locales.translator("zh-Hant")
        english = self.locales.translator("en")
        shared = [
            value
            for value in (item.value for item in Genre)
            if label(chinese, "genre", value) == label(english, "genre", value)
        ]

        self.assertEqual(shared, [])

    def test_an_unnamed_language_tag_reads_as_itself(self) -> None:
        from terminal_radio.tui.labels import language_label

        translator = self.locales.translator("en")

        self.assertEqual(language_label(translator, "ja"), "ja")
        self.assertEqual(language_label(translator, "hak"), "Hakka")

    def test_a_station_without_a_blurb_shows_what_it_plays(self) -> None:
        from terminal_radio.tui.labels import format_tags

        translator = self.locales.translator("zh-Hant")
        relay = StationCatalog.from_file(Settings().stations_file).get("pbs-hualien")

        self.assertIsNone(relay.description)
        self.assertEqual(
            format_tags(translator, "genre", relay.genres), "新聞 · 路況 · 談話"
        )
