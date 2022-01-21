Title: Submit Application
URL: 
save_as: submit.html
status: hidden

Before submitting your application, please make sure it complies following basic rules:

1. **NO PIRACY**. We refuse to endorse or host any kind of information related to priacy, as well as breaking DRM protected content and applications. For IPTV services **only legal IPTV services are allowed**.
2. Be considerate to users' TV. It's not a cheap toy, so try your best not breaking it.
3. If you are making a port to existing applications, please make sure that you are following original project's open source license.

To submit your application to this central repository, refer to following steps:

### Fork This Repository

TODO: Submit without GitHub

### Add Your Application

Create a file named `your-package-name.yml` in `packages`. Example:

```yaml
# Display name of your application
title: Homebrew Channel
# Publicly accesible HTTP/HTTPS URL, or data uri to icon image.
iconUri: https://raw.githubusercontent.com/webosbrew/webos-homebrew-channel/main/assets/icon160.png
# Publicly accessible manifest file of your application
manifestUrl: https://github.com/webosbrew/webos-homebrew-channel/releases/latest/download/org.webosbrew.hbchannel.manifest.json
# Category for your application
category: tools
# If this is an open source application, use main, otherwise non-free
pool: main
# Long description for your application, in Markdown format
description: |
  Description in markdown format, we suggest you to add some screenshots to help users understand
# Sponsor information, like .github/FUNDING.yml
funding:
  github: [your-name]
```

### Submit a Pull Request

We'll be reviewing and testing your application, then merge it to our main branch. Then your application will be available to download by other users shortly.

## Report an Inappropriate Application

If you find any application listed is not appropriate according to rule above, please [submit an issue](https://github.com/webosbrew/apps-repo/issues/new).

## Self-Host a Repository

TODO: Make this repo configurable

## Related Resources

* [webOS Homebrew Channel](https://github.com/webosbrew/webos-homebrew-channel)
* [Documentation](https://github.com/webosbrew/docs)
* [Unofficial webOS NDK](https://github.com/webosbrew/meta-lg-webos-ndk)
* [openlgtv Project](https://openlgtv.github.io/)