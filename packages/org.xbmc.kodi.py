import hashlib
import json
import os
import urllib.parse
from io import StringIO
from os import path
from tempfile import gettempdir
from typing import List

import requests
from lxml import etree
from lxml.etree import Element

from repogen import ipk_file, cache
from repogen.pkg_manifest import PackageManifest
from repogen.pkg_registery import PackageRegistry

title = 'Kodi'
iconUri = 'https://raw.githubusercontent.com/xbmc/xbmc/master/media/icon120x120.png'
detailIconUri = 'https://raw.githubusercontent.com/xbmc/xbmc/master/media/icon256x256.png'
category = 'multimedia'
requirements = {
    'webosRelease': '>=4.0'
}
description = '''![Kodi Logo](https://raw.githubusercontent.com/xbmc/xbmc/master/docs/resources/banner.png)
<p align="center">
  <strong>
    <a href="https://kodi.tv/">website</a>
    •
    <a href="https://kodi.wiki/view/Main_Page">docs</a>
    •
    <a href="https://forum.kodi.tv/">community</a>
    •
    <a href="https://kodi.tv/addons">add-ons</a>
  </strong>
</p>
<h1 align="center">
  Welcome to Kodi Home Theater Software!
</h1>
Kodi is an award-winning **free and open source** software media player and entertainment hub for digital media. 
Available as a native application for **Android, Linux, BSD, macOS, iOS, tvOS and Windows operating systems**,
Kodi runs on most common processor architectures.
Created in 2003 by a group of like minded programmers, Kodi is a non-profit project run by the XBMC Foundation and
developed by volunteers located around the world. More than 500 software developers have contributed to Kodi to date,
and 100-plus translators have worked to expand its reach, making it available in more than 70 languages.
While Kodi functions very well as a standard media player application for your computer, it has been designed to be the
perfect companion for your HTPC. With its **beautiful interface and powerful skinning engine**, Kodi feels very natural
to use from the couch with a remote control and is the ideal solution for your home theater.
## Give your media the love it deserves
Kodi can be used to play almost all popular audio and video formats around. It was designed for network playback, 
so you can stream your multimedia from anywhere in the house or directly from the internet using practically any
protocol available.
Point Kodi to your media and watch it **scan and automagically create a personalized library** complete with box covers,
descriptions, and fanart. There are playlist and slideshow functions, a weather forecast feature and many audio
visualizations. Once installed, your computer or HTPC will become a fully functional multimedia jukebox.
<p align="center">
  <img src="https://raw.githubusercontent.com/xbmc/xbmc/master/docs/resources/kodi.gif" alt="Kodi">
</p>
'''


def load() -> PackageRegistry:
    with requests.get('https://mirrors.kodi.tv/releases/webos/') as resp:
        doc: etree.ElementBase = etree.parse(StringIO(resp.text), parser=etree.HTMLParser())
        anchors: List[Element] = doc.xpath('//table[@id="list"]/tbody/tr/td[1]/a[@href!="../"]')
        urls: List[str] = list(map(lambda a: urllib.parse.urljoin(resp.url, a.attrib['href']), anchors))
    ipk_url = urls[0]
    url_hash = hashlib.sha256(ipk_url.encode(encoding='utf-8')).hexdigest()
    manifest_name = f'manifest_org.xbmc.kodi_snapshot_{url_hash[:10]}.json'
    manifest_path = cache.path(manifest_name)
    ipk_path = path.join(gettempdir(), f'repogen_org.xbmc.kodi_snapshot_{url_hash[:10]}.ipk')
    manifest: PackageManifest
    if not path.exists(manifest_path):
        if not path.exists(ipk_path):
            with requests.get(ipk_url) as resp, open(ipk_path, mode='wb') as f:
                f.write(resp.content)
        with open(ipk_path, 'rb') as f:
            ipk_hash = hashlib.sha256(f.read()).hexdigest()

        appinfo = ipk_file.get_appinfo(ipk_path)
        manifest = {
            'id': appinfo['id'],
            'title': appinfo['title'],
            'version': appinfo['version'],
            'type': appinfo['type'],
            'appDescription': appinfo.get('appDescription', None),
            'iconUri': iconUri,
            'sourceUrl': 'https://github.com/xbmc/xbmc',
            'ipkUrl': ipk_url,
            'ipkHash': {
                'sha256': ipk_hash
            },
            'ipkSize': os.stat(ipk_path).st_size
        }
        with cache.open_file(manifest_name, 'w') as f:
            json.dump(manifest, f)
    return {
        'title': title,
        'iconUri': iconUri,
        'detailIconUri': detailIconUri,
        'category': category,
        'description': description,
        'requirements': requirements,
        'pool': 'main',
        'manifestUrl': manifest_path.as_uri(),
        'funding': {
            'github': ['sundermann']
        }
    }


if __name__ == '__main__':
    print(load())
