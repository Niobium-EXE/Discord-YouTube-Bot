import html, asyncio, re
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urlparse

import aiohttp

from bot.models import YouTubeChannelInfo


YOUTUBE_BASE_URL = "https://www.youtube.com"


# Normal YouTube channel IDs are:
#
# UC + 22 characters
#
# Example:
# UCXuqSBlHAE6Xw-yeJA0Tunw

CHANNEL_ID_PATTERN = re.compile(
    r"UC[A-Za-z0-9_-]{22}"
)


class YouTubeLookupError(Exception):
    """
    Raised when a YouTube channel cannot be resolved.
    """

    pass


class YouTubeMetadataParser(HTMLParser):
    """
    Reads useful metadata from a YouTube channel page.
    """

    def __init__(self):
        super().__init__()

        self.channel_id: str | None = None
        self.display_name: str | None = None
        self.canonical_url: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs,
    ):
        attributes = dict(attrs)

        if tag == "meta":

            itemprop = attributes.get(
                "itemprop"
            )

            content = attributes.get(
                "content"
            )

            if (
                itemprop
                in {
                    "channelId",
                    "identifier",
                }
                and content
                and CHANNEL_ID_PATTERN.fullmatch(
                    content
                )
            ):
                self.channel_id = content

            if (
                attributes.get("property")
                == "og:title"
                and content
            ):
                self.display_name = html.unescape(
                    content
                )

        if tag == "link":

            rel = attributes.get("rel")

            href = attributes.get("href")

            if (
                rel == "canonical"
                and href
            ):
                self.canonical_url = href


def _extract_channel_id(
    page_html: str,
    parser: YouTubeMetadataParser,
) -> str | None:
    """
    Find the page owner's channel ID.

    We prefer owner-specific metadata before
    using broader fallback patterns.
    """

    if parser.channel_id:
        return parser.channel_id

    if parser.canonical_url:
        match = CHANNEL_ID_PATTERN.search(
            parser.canonical_url
        )

        if match:
            return match.group(0)

    # Common owner-specific field.
    match = re.search(
        r'"externalId":"'
        r'(UC[A-Za-z0-9_-]{22})"',
        page_html,
    )

    if match:
        return match.group(1)

    # Fallback used if YouTube changes the
    # metadata above.
    match = re.search(
        r'"browseId":"'
        r'(UC[A-Za-z0-9_-]{22})"',
        page_html,
    )

    if match:
        return match.group(1)

    return None


def _extract_handle(
    page_html: str,
) -> str | None:
    """
    Attempt to find the channel's current @handle.
    """

    patterns = [
        (
            r'"canonicalBaseUrl":'
            r'"/(@[^"]+)"'
        ),
        (
            r'"vanityChannelUrl":'
            r'"https?://www\.youtube\.com/'
            r'(@[^"]+)"'
        ),
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            page_html,
        )

        if match:
            return html.unescape(
                match.group(1)
            )

    return None


def _build_lookup_url(
    reference: str,
) -> tuple[str, str | None]:
    """
    Turn user input into a YouTube channel URL.

    Supported examples:

        @mkbhd

        mkbhd

        UCxxxxxxxxxxxxxxxxxxxxxx

        https://youtube.com/@mkbhd

        https://youtube.com/channel/UC...
    """

    reference = reference.strip()

    if not reference:
        raise YouTubeLookupError(
            "You need to provide a YouTube "
            "channel."
        )

    # Direct UC channel ID.
    if CHANNEL_ID_PATTERN.fullmatch(
        reference
    ):
        return (
            f"{YOUTUBE_BASE_URL}/channel/"
            f"{reference}",
            None,
        )

    # Existing URL.
    if (
        reference.startswith("http://")
        or reference.startswith("https://")
    ):
        parsed = urlparse(
            reference
        )

        if not (
            parsed.netloc.endswith(
                "youtube.com"
            )
            or parsed.netloc.endswith(
                "youtu.be"
            )
        ):
            raise YouTubeLookupError(
                "That does not look like a "
                "YouTube channel URL."
            )

        requested_handle = None

        path_parts = [
            unquote(part)
            for part in parsed.path.split("/")
            if part
        ]

        for part in path_parts:
            if part.startswith("@"):
                requested_handle = part
                break

        return (
            reference,
            requested_handle,
        )

    # Anything else is treated as a handle.
    if not reference.startswith("@"):
        reference = f"@{reference}"

    encoded_handle = quote(
        reference,
        safe="@._-",
    )

    return (
        f"{YOUTUBE_BASE_URL}/{encoded_handle}",
        reference,
    )


async def resolve_youtube_channel(
    reference: str,
) -> YouTubeChannelInfo:
    """
    Resolve a YouTube @handle, URL, or UC channel
    ID into permanent channel information.
    """

    url, requested_handle = (
        _build_lookup_url(reference)
    )

    timeout = aiohttp.ClientTimeout(
        total=15
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120 Safari/537.36"
        )
    }

    try:
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=headers,
        ) as session:

            async with session.get(
                url,
                allow_redirects=True,
            ) as response:

                if response.status == 404:
                    raise YouTubeLookupError(
                        "YouTube could not find "
                        "that channel."
                    )

                if response.status >= 400:
                    raise YouTubeLookupError(
                        "YouTube returned HTTP "
                        f"{response.status}."
                    )

                page_html = await response.text()

    except asyncio.TimeoutError:
        raise YouTubeLookupError(
            "YouTube took too long to respond."
        )

    except aiohttp.ClientError as error:
        raise YouTubeLookupError(
            "Could not connect to YouTube."
        ) from error

    parser = YouTubeMetadataParser()

    parser.feed(
        page_html
    )

    channel_id = _extract_channel_id(
        page_html,
        parser,
    )

    if not channel_id:
        raise YouTubeLookupError(
            "I found the YouTube page, but could "
            "not find its channel ID. YouTube may "
            "have changed its page layout."
        )

    handle = (
        _extract_handle(page_html)
        or requested_handle
    )

    display_name = (
        parser.display_name
        or handle
        or channel_id
    )

    return YouTubeChannelInfo(
        channel_id=channel_id,
        display_name=display_name,
        handle=handle,
        channel_url=(
            f"{YOUTUBE_BASE_URL}/channel/"
            f"{channel_id}"
        ),
    )