#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Covid19 slack bot.

Fetch latest information about covid19 progression and post it to a slack channel.
"""

import asyncio
import re

import aiohttp
import uvloop


class Covid19:
    def __init__(self, session=None, loop=None):
        """Fetch latest information about covid19 progression and post it to a slack channel.

        session: http session
        loop: asyncio event loop
        """
        if not loop:
            loop = asyncio.get_running_loop()
        self.loop = loop

        self.cleanup_session = False
        if not session:
            session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
            self.cleanup_session = True
        self.session = session

        self.source_url = "https://www.worldometers.info/coronavirus/"
        self.last_updated = None

    def __del__(self):
        if self.cleanup_session and self.session:
            self.session.close()

    async def fetch_information(self):
        async with self.session.get(self.source_url) as response:
            data = await response.text()
            return data

    async def run(self):
        while True:
            await self.update()
            await asyncio.sleep(60)

    async def update(self):
        print("Waking up")
        # get info
        data = await self.fetch_information()

        # parse info
        match = re.search(r"Last updated: ([^<]+)", data)
        if not match:
            raise Exception("Unable to find last updated")

        last_updated = match.group(1)
        if last_updated != self.last_updated:
            print("New content")
            self.last_updated = last_updated
        else:
            print("Nothing new")

        # post info
        ...


async def main():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        covid_19 = Covid19(session)
        await covid_19.run()


if __name__ == "__main__":
    uvloop.install()
    asyncio.run(main())
