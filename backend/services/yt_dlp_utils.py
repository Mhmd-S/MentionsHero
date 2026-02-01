"""Shared yt-dlp configuration helpers."""

from pathlib import Path


def get_yt_dlp_base_args() -> list[str]:
    """Build common yt-dlp arguments for YouTube downloads."""
    args = [
        'yt-dlp',
        '--js-runtimes', 'node',
        '--remote-components', 'ejs:github'
    ]

    cookies_path = Path(__file__).resolve().parents[1] / 'cookies.txt'
    if cookies_path.exists():
        args.extend([
            '--cookies', str(cookies_path),
            '--extractor-args', 'youtube:player_client=web'
        ])
    else:
        args.extend(['--extractor-args', 'youtube:player_client=android'])

    return args
