from urllib.parse import urlsplit, SplitResult, urlunsplit

from more_itertools import flatten

# Known FUNDING.yml platforms -> (URL template, label suffix, bootstrap-icon).
_PLATFORMS = {
    'github': ('https://github.com/sponsors/{}', 'on GitHub', 'bi-github'),
    'patreon': ('https://www.patreon.com/{}', 'on Patreon', 'bi-heart-fill'),
    'open_collective': ('https://opencollective.com/{}', 'on Open Collective', 'bi-people-fill'),
    'ko_fi': ('https://ko-fi.com/{}', 'on Ko-fi', 'bi-cup-hot-fill'),
    'liberapay': ('https://liberapay.com/{}', 'on Liberapay', 'bi-heart-fill'),
    'buy_me_a_coffee': ('https://www.buymeacoffee.com/{}', 'on Buy Me a Coffee', 'bi-cup-hot-fill'),
}

# Non-HTTP custom URI schemes (crypto wallets) -> (label, bootstrap-icon).
_CRYPTO = {
    'bitcoin': ('Bitcoin', 'bi-currency-bitcoin'),
    'ethereum': ('Ethereum', 'bi-currency-exchange'),
    'litecoin': ('Litecoin', 'bi-coin'),
    'monero': ('Monero', 'bi-coin'),
}


def _parse_custom(element: str) -> dict:
    comps = urlsplit(element)
    if not comps.scheme:
        # Bare domain/path, e.g. "example.com/donate" -> assume https.
        netloc, path = (comps.path.split('/', 1) + [''])[:2]
        comps = SplitResult(scheme='https', netloc=netloc, path=path,
                            query=comps.query, fragment=comps.fragment)
    href = urlunsplit(comps)
    if comps.scheme in ('http', 'https'):
        label = f'{comps.netloc}{comps.path}'.rstrip('/') or href
        return {'href': href, 'text': label, 'icon': 'bi-box-arrow-up-right'}
    # Non-web scheme (e.g. a bitcoin: address) — label by scheme, not the raw address.
    label, icon = _CRYPTO.get(comps.scheme, (comps.scheme.capitalize(), 'bi-wallet2'))
    return {'href': href, 'text': label, 'icon': icon}


def parse_links(funding: dict):
    if not funding:
        return None

    def parse_element(platform: str, element: str):
        if platform in _PLATFORMS:
            template, suffix, icon = _PLATFORMS[platform]
            return {'href': template.format(element), 'text': f'{element} {suffix}', 'icon': icon}
        if platform == 'custom':
            return _parse_custom(element)
        return None

    def parse_item(platform, value):
        if isinstance(value, str):
            return [parse_element(platform, value)]
        return map(lambda e: parse_element(platform, e), value)

    return list(filter(None, flatten(map(lambda item: parse_item(item[0], item[1]), funding.items()))))
