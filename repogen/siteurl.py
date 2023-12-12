from pathlib import Path


def siteurl() -> str:
    cname_file = Path(__file__).parent.parent.joinpath('content', 'extra', 'CNAME')
    if not cname_file.exists():
        # XXX: hack
        return 'https://throwaway96.github.io/apps-repo'
    return f'https://{cname_file.read_text().strip()}'
