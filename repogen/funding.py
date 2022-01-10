from urllib.parse import urlsplit, SplitResult, urlunsplit

from more_itertools import flatten


def parse_links(funding: dict):
    if not funding:
        return None

    def parse_element(platform: str, element: str):
        if platform == 'github':
            return {'href': f'https://github.com/sponsors/{element}', 'text': f'{element} on Github'}
        elif platform == 'patreon':
            return {'href': f'https://www.patreon.com/{element}', 'text': f'{element} on Patreon'}
        elif platform == 'ko_fi':
            return {'href': f'https://ko-fi.com/{element}', 'text': f'{element} on Ko-fi'}
        elif platform == 'custom':
            comps = urlsplit(element)
            if not comps.scheme:
                netloc, path = (comps.path.split('/', 1) + [''])[:2]
                comps = SplitResult(scheme='https', netloc=netloc, path=path, query=comps.query,
                                    fragment=comps.fragment)
            return {'href': urlunsplit(comps), 'text': f'{comps.netloc}/{comps.path}'.rstrip('/')}
        else:
            return None

    def parse_item(platform, value):
        if value is str:
            return [parse_element(platform, value)]
        return map(lambda e: parse_element(platform, e), value)

    return list(filter(lambda x: x, flatten(map(lambda item: parse_item(item[0], item[1]), funding.items()))))
