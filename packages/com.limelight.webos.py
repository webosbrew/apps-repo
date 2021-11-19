import requests

title = 'Moonlight'
iconUri = 'https://github.com/mariotaku/moonlight-tv/raw/main/deploy/webos/icon.png'
manifestUrl = 'https://github.com/mariotaku/moonlight-tv/releases/latest/download/com.limelight.webos.manifest.json'
category = 'games'
description = '''
Moonlight TV is a GUI front end for [Moonlight GameStream Client](https://moonlight-stream.org/). With some components from [moonlight-embedded](https://github.com/irtimmer/moonlight-embedded).
It was originally designed for LG webOS TVs, but may support running on more devices in the future.

## Features

* Supports up to 4 controllers
* Utilizes system hardware decoder to get best performance (webOS 3/4/5)
* Easy to port to other OSes (Now runs on macOS, Linux, Raspberry Pi)

## Screenshots

![Launcher](https://user-images.githubusercontent.com/830358/141690137-529d3b94-b56a-4f24-a3c5-00a56eb30952.png)

![Settings](https://user-images.githubusercontent.com/830358/141690143-6752757b-5e1f-4a23-acf7-4b2667e2fd05.png)

![In-game Overlay](https://user-images.githubusercontent.com/830358/141690146-27ee2564-0cc8-43ef-a5b0-54b8487dda1e.png)
_Screenshot performed on TV has lower picture quality. Actual picture quality is better._

## [Documentations](https://github.com/mariotaku/moonlight-tv/wiki)
'''


def load():
    content = {
        'title': title,
        'iconUri': iconUri,
        'category': category,
        'description': description,
        'manifestUrl': manifestUrl
    }
    with requests.get('https://api.github.com/repos/mariotaku/moonlight-tv/releases', {'per_page': 1}) as resp:
        latest = resp.json()[0]
        if latest['prerelease']:
            for asset in filter(lambda x: x['name'] == 'com.limelight.webos.manifest.json', latest['assets']):
                content['manifestUrlBeta'] = asset['browser_download_url']
                break
    return content
