#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Covid19 slack bot.

Fetch latest information about covid19 progression and post it to a slack channel.
"""


import os
import sys
import json
import locale
import asyncio
import logging
import pathlib
import datetime
from typing import Any, List, Text, Union, Mapping, Optional

import bs4
import aiohttp
import aiofiles


try:
    import coloredlogs

    coloredlogs.install(level="DEBUG")
except ImportError:
    pass

try:
    import uvloop
except ImportError:
    uvloop = None


class Covid19:
    logger = logging.getLogger("covid19.bot")
    source_url = "https://www.worldometers.info/coronavirus/"
    payload_fields = [
        {
            "Total Cases:            ": lambda n: locale.format_string("%d", n[0], True),
            "New Cases:            ": lambda n: locale.format_string("%+d", n[1], True),
            "Tot Cases/1M pop:": lambda n: locale.format_string("%.1f", n[7], True).rstrip("0").rstrip("."),
        },
        {
            "Total deaths: ": lambda n: locale.format_string("%d", n[2], True),
            "New deaths: ": lambda n: locale.format_string("%+d", n[3], True),
            "Active/Total:": lambda n: (
                locale.format_string("%.1f", 100 * n[5] / n[0], True).rstrip("0").rstrip(".") + "%"
            ),
        },
        {
            "Total Recovered:": lambda n: locale.format_string("%d", n[4], True),
            "Active Cases:     ": lambda n: locale.format_string("%d", n[5], True),
            "Serious, Critical:": lambda n: locale.format_string("%d", n[6], True),
        },
    ]

    # pylint: disable=bad-continuation
    def __init__(
        self, slack_webhook: Text, channel: Text, refresh_time: Mapping, watched_countries: Mapping,
    ):
        """Fetch latest information about covid-19 progression and post it to a slack channel.

        slack_webhook: webhook url
        refresh_time: dict of time element (ex: {"hour": 23, "minute": 50, "second": 0})
        watched_countries: mapping between source country name and display string
        """
        self.session: Optional[aiohttp.ClientSession] = None
        self.cleanup_session: bool = False
        self.last_updated: Text = "no previous update"
        self.refresh_time: Mapping = refresh_time
        self.slack_webhook: Text = slack_webhook
        self.watched_countries: Mapping = watched_countries
        self.channel: Text = channel

    # pylint: disable=bad-continuation
    async def __aenter__(
        self, session: Optional[aiohttp.ClientSession] = None, loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        if not loop:
            loop = asyncio.get_running_loop()

        if session:
            self.session = session
        if not self.session:
            self.logger.info("Creating HTTP session")
            self.cleanup_session = True
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60), loop=loop)
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        if self.cleanup_session and self.session:
            self.logger.info("Closing HTTP session")
            await self.session.close()

    async def run(self):
        while True:
            await self.update()
            now = datetime.datetime.utcnow()
            next_event = now.replace(**self.refresh_time)
            to_wait = (next_event - now).seconds
            if to_wait < 0:
                next_event = next_event.replace(day=now.day)
                to_wait = (next_event - now).seconds
            self.logger.info(
                "Sleeping for %s seconds (waking at %s)", to_wait, next_event.isoformat(),
            )
            await asyncio.sleep(to_wait)
            self.logger.info("Waking up")

    async def update(self):
        data = await self.fetch_information()
        info = self.parse_webpage(data)
        if info:
            payload = self.create_payload(info)
            await self.post(payload)

    async def fetch_information(self):
        self.logger.debug("Loading page")
        async with self.session.get(self.source_url) as response:
            data = await response.text()
        self.logger.debug("Page loaded")
        return data

    def parse_webpage(self, data: Text):
        self.logger.debug("Loading HTML soup")
        soup = bs4.BeautifulSoup(data, "lxml")
        self.logger.debug("HTML soup loaded")

        last_updated = self.find_last_updated(soup)
        if last_updated == self.last_updated:
            self.logger.debug("Nothing new since last update (%s)", last_updated)
            return None
        self.logger.info(
            "New content from %s (previous: %s)", last_updated, self.last_updated,
        )
        self.last_updated = last_updated

        return self.get_stats(soup)

    @staticmethod
    def find_last_updated(soup: bs4.BeautifulSoup):
        match: bs4.Tag = soup.select_one(".content-inner > div:nth-child(5)")
        if not match:
            raise Exception("Unable to find last updated")
        last_updated = match.string.split(":", maxsplit=1)[1].strip()
        return last_updated

    def get_stats(self, soup: bs4.BeautifulSoup):
        table: bs4.Tag = soup.find("table", id="main_table_countries_today")
        headers: List[Text] = list(" ".join(th.strings) for th in table.thead.find_all("th"))
        stats = {}
        for tr_tag in table.find_all("tr"):
            if tr_tag.parent.name == "thead":
                continue
            all_tr = tr_tag.find_all("td")
            country = "".join(all_tr[0].stripped_strings)
            numbers: List[Union[int, float]] = []
            for td_tag in all_tr[1:]:
                value = "".join(td_tag.stripped_strings) or "0"
                # sometime, counter is negative, but has a + sign ...
                if value.startswith("+-"):
                    value = value[1:]
                try:
                    int_value = locale.atoi(value)
                    numbers.append(int_value)
                except ValueError:
                    try:
                        float_value = locale.atof(value)
                        numbers.append(float_value)
                    except ValueError:
                        self.logger.warning("Unable to parse value %s", value)
                        continue
            self.logger.debug("%s - %s", country, numbers)
            stats[country] = dict(zip(headers[1:], numbers))

        return stats

    def create_payload(self, info: Mapping):
        payload = {
            "text": f"*Coronavirus Covid-19 Lastest Report*\nAs of {self.last_updated}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Coronavirus Covid-19 Lastest Report*\nAs of {self.last_updated}",
                    },
                },
            ],
        }
        if self.channel:
            payload["channel"] = self.channel

        self.create_countries_payload(info, payload)

        return payload

    def create_countries_payload(self, info: Mapping, payload: Mapping):
        for country, intro in self.watched_countries.items():
            data = info[country]
            numbers = list(data.values())
            blocks = payload["blocks"]
            blocks.append({"type": "divider"})
            context: Any = {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": intro}],
            }

            for payload_field in self.payload_fields:
                msg_parts, max_len = self.country_create_msg_parts(numbers, payload_field)
                msg_splitted = self.country_format_message(msg_parts, max_len)
                context["elements"].append({"type": "mrkdwn", "text": "\n".join(msg_splitted)})

            blocks.append(context)

    @staticmethod
    def country_create_msg_parts(numbers, payload_field):
        max_len = 0
        msg_parts = {}
        for field, idx in payload_field.items():
            if callable(idx):
                value = idx(numbers)
            else:
                value = numbers[idx]
            value = str(value)

            min_len = len(field) + len(value)
            msg_parts[field] = value, min_len
            if min_len > max_len:
                max_len = min_len
        return msg_parts, max_len

    # old version was adjusting spacing
    # def country_format_message(msg_part, max_len):
    @staticmethod
    def country_format_message(msg_part, _):
        msg_splitted = []
        for field, value_and_size in msg_part.items():
            # value, min_len = value_and_size
            value, _ = value_and_size
            # len_diff = max_len - min_len
            msg_split = f"{field} `{value}`"
            msg_splitted.append(msg_split)
        return msg_splitted

    async def post(self, payload):
        for i in range(10):
            try:
                async with self.session.post(
                    url=self.slack_webhook, json=payload,  # pylint: disable=bad-continuation
                ) as response:
                    output = await response.text()
                    if response.status != 200:
                        raise Exception(f"Slack returned an error {output}")
                    break
            except asyncio.TimeoutError:
                self.logger.warning(
                    "Fail to send to Slack (Timeout), retrying (%s/10)", i + 1,
                )
                continue
        else:
            raise TimeoutError


async def run(webhook, channel):
    if uvloop:
        uvloop.install()

    current_dir = pathlib.Path(__file__).parent
    async with aiofiles.open(current_dir.joinpath("config.json")) as config_file:
        data = await config_file.read()
        config = json.loads(data)

    locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
    # pylint: disable=bad-continuation
    async with Covid19(
        slack_webhook=webhook,
        channel=channel,
        refresh_time={"hour": 23, "minute": 50, "second": 0},
        watched_countries=config["watched_countries"],
    ) as covid_19:
        await covid_19.run()


def main():
    try:
        webhook = os.getenv("SLACK_WEBHOOK")
        channel = os.getenv("CHANNEL")
    except IndexError:
        sys.stderr.write(f"Error missing SLACK_WEBHOOK and/or CHANNEL environment variables")
        sys.exit(1)

    asyncio.run(run(webhook, channel))


if __name__ == "__main__":
    main()
