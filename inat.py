import logging
from typing import Tuple

import aiohttp
from sciolyid.util import cache
from sentry_sdk import capture_message

COUNT = 5
TAXON_ID_URL = "https://api.inaturalist.org/v1/taxa?q={taxon}"
OBSERVATIONS_URL = (
    "https://api.inaturalist.org/v1/observations?photos=true&photo_licensed=true"
    + "&taxon_id={taxon_id}&quality_grade=research&per_page={count}"
    + "&order_by=id&order=asc&id_above={last_id}"
)
IMAGE_URL = "https://inaturalist-open-data.s3.amazonaws.com/photos/{id}/medium.{ext}"

logger = logging.getLogger("bugbo")


@cache()
async def get_taxon_id(taxon: str, session: aiohttp.ClientSession) -> int | None:
    """Return the taxon ID of the specimen."""
    async with session.get(TAXON_ID_URL.format(taxon=taxon)) as resp:
        data = await resp.json()
    results = sorted(data["results"], key=lambda x: x["rank_level"], reverse=True)
    return None if len(results) == 0 else results[0]["id"]


async def get_urls(
    session: aiohttp.ClientSession,
    item: str,
    index: int,
    count: int = COUNT,
) -> Tuple[int, Tuple[str, ...], Tuple[str, ...]]:
    """Return URLS of images of the specimen to download.

    This method uses iNaturalist's API to fetch image urls. It will
    try up to 2 times to successfully retrieve URLS.

    `index` is the ID of the last observation that was downloaded.
    This function will try to return `images_to_download` number of
    images. The new ID is returned as the first element of the tuple.
    """
    taxon_id = await get_taxon_id(item, session)
    if not taxon_id:
        logger.info(f"no taxon id found for {item}, falling back")
        capture_message(f"no taxon id found for {item}")

    urls = []
    ids = []
    async with session.get(
        OBSERVATIONS_URL.format(taxon_id=taxon_id, count=count, last_id=index)
    ) as resp:
        observations = (await resp.json())["results"]

    if not observations:
        async with session.get(
            OBSERVATIONS_URL.format(taxon_id=taxon_id, count=count, last_id="")
        ) as resp:
            observations = (await resp.json())["results"]

    if not observations:
        return (0, tuple(), tuple())

    logger.info(f"observation ids: {','.join([str(o['id']) for o in observations])}")
    for observation in observations:
        logger.info(f"observation at: {observation['observed_on']}")
        for photo in observation["photos"]:
            urls.append(
                IMAGE_URL.format(id=photo["id"], ext=photo["url"].split(".")[-1])
            )
            ids.append(observation["id"])
    return (observations[-1]["id"], tuple(urls), tuple(ids))
