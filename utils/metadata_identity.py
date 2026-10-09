"""Shared, exact song identities for chart and video metadata."""


def song_identity(title, artist):
    if not isinstance(title, str):
        raise ValueError("song title must be a string")
    normalized_title = title.strip()
    # The public maimai catalog contains a song officially titled U+3000.
    if not normalized_title:
        if title != "\u3000":
            raise ValueError("song title must not be empty")
        normalized_title = title
    if artist is None:
        normalized_artist = ""
    elif isinstance(artist, str):
        normalized_artist = artist.strip()
    else:
        raise ValueError("artist must be a string or null")
    return normalized_title, normalized_artist
