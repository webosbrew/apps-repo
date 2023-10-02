from pathlib import Path


def siteurl() -> str:
    cname_file = Path(__file__, '..', '..', 'content', 'extra', 'CNAME')
    if not cname_file.exists():
        return ''
    return f'https://{cname_file.read_text().strip()}'
