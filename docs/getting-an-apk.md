# Getting an APK

Three routes, in order of how much you can trust what you end up with. The
short version: **paste the app page URL and let the tool resolve it**, and pull
from your own device when the answer has to be exact.

## Route 1 — paste the mirror URL

`apk-lens` takes an app page URL directly:

```bash
apk-lens analyze "https://apkpure.com/accessy/com.axessions.app" --category utility
```

It resolves the page to a file for you. For that example the chain is two hops:

```
following download link: https://apkpure.com/accessy/com.axessions.app/download
following download link: https://d.apkpure.com/b/XAPK/com.axessions.app?version=latest
   Accessy_2.15.3_APKPure.xapk — 34.8 MB, a bundle of split APKs with a manifest.json
   sha256 ...
```

Note what the second hop looks like: `.../b/XAPK/<package>?version=latest`, with
**no file extension**. That is why the resolver looks for a download-shaped
anchor and a download host rather than only for URLs ending in `.apk`.

### It refuses to download a different app

A mirror's pages carry adverts for other apps, and those adverts are frequently
better-formed file links than the real target. On the page above, the
best-looking `.apk` link belongs to the mirror's own installer app. Downloading
it would produce a confident report about the wrong software, so:

- the package id is taken from the URL you gave (`com.axessions.app`);
- any candidate naming a *different* package is skipped — including one that
  names yours too, because mirrors pass the referring app along in a query
  parameter;
- when your URL does not name a package (`/accessy/download`), the app is
  inferred from whichever package dominates the page's own links, and only when
  there is a clear winner.

If it cannot find a link for **your** app it stops and says so, rather than
taking the nearest file.

### When automatic resolution will not work

Interstitials, JavaScript-only buttons behind a countdown, region blocks and
sign-in walls all defeat a two-hop scraper. The error tells you the fallback:

> open the page in a browser, start the download, then copy the direct file URL
> and pass that instead

In practice: start the download, open your browser's download list, right-click
the entry, **Copy download link**, cancel the browser download, then:

```bash
apk-lens analyze "https://d.apkpure.com/b/XAPK/com.axessions.app?version=latest" \
  --category utility
```

Signed CDN links carry a token in the query string and expire, so paste the
whole URL and use it promptly.

## Route 2 — pull it off your own device

The most trustworthy option: the exact build running on your phone, with no
mirror in the middle.

```bash
adb shell pm list packages | grep -i accessy
adb shell pm path com.axessions.app
```

`pm path` prints one line per split:

```
package:/data/app/~~AbC==/com.axessions.app-XyZ==/base.apk
package:/data/app/~~AbC==/com.axessions.app-XyZ==/split_config.arm64_v8a.apk
package:/data/app/~~AbC==/com.axessions.app-XyZ==/split_config.xxhdpi.apk
```

Pull **every** one:

```bash
mkdir -p ~/apks/accessy && cd ~/apks/accessy
adb shell pm path com.axessions.app | sed 's/^package://' \
  | while read -r p; do adb pull "$p" .; done
```

Then zip them into a bundle so the tool sees the splits together:

```bash
zip -j accessy-device.apks *.apk
apk-lens analyze accessy-device.apks --category utility
```

## Route 3 — Google Play

Play does not hand you the file. Tools exist that reconstruct a bundle for an
account you own; the same verification caveat as any mirror applies, since you
are trusting the tool instead of the site.

## Why the file is a `.xapk` and why that matters

`Accessy_2.15.3_APKPure.xapk` is a ZIP containing the base APK plus its split
APKs. The pieces are not interchangeable:

| split | holds |
|---|---|
| base APK | `classes*.dex` and the manifest |
| `config.arm64_v8a` | the `.so` native libraries |
| `config.<lang>` / `config.<density>` | resources |
| feature modules | code downloaded after install |

**Take the plain `base.apk` alone and you get zero native libraries** — the part
of a hardened app where the interesting logic usually lives. `apk-lens` says so
explicitly when it finds none:

> no native libraries were examined […] If the bundle you downloaded was a base
> APK without its ABI split, native code exists but was not present here.

So prefer the `.xapk` / `.apks` bundle over a single `.apk` whenever a mirror
offers both.

## Pinning a version

Mirrors expose per-version pages and per-version download URLs alongside
"latest":

```
https://apkpure.com/accessy/com.axessions.app/download/2.14.2
https://d.apkpure.com/b/XAPK/com.axessions.app?versionCode=3104
```

Use them when you need to reproduce a finding or compare two releases. `latest`
moves, and a report that says "latest" is worthless six weeks later — which is
why every generated report names the version and the SHA-256 it analysed.

## Verifying what you got

Every acquisition writes a provenance record next to the file:

```bash
cat apks/Accessy_2.15.3_APKPure.xapk.provenance.json
```

```json
{
  "source": "https://apkpure.com/accessy/com.axessions.app",
  "resolved_url": "https://d.apkpure.com/b/XAPK/com.axessions.app?version=latest",
  "sha256": "…",
  "size_bytes": 36476092,
  "container": "xapk"
}
```

That hash is how someone else reproduces your run without you redistributing the
binary. It does **not** tell you the mirror served an untampered build. For that,
compare signing certificates:

```bash
apksigner verify --print-certs base-from-mirror.apk
apksigner verify --print-certs base-from-device.apk
```

Matching SHA-256 digests mean the mirror did not repackage the app. `apk-lens`
records this automatically in report 01 when `apksigner` is installed — and
`apk-lens doctor` will tell you if it is not.

## Size limits and caching

Downloads land in `apks/` (git-ignored) and are capped at 3 GB by default:

```bash
apk-lens analyze <url> --max-size 500     # refuse anything over 500 MB
```

The cache is checked **before** the network and keyed on the recorded SHA-256,
so re-running an analysis does not re-download — and a run still works when the
mirror is slow, has moved the file, or is offline.

## Before you download anything

Analyse apps you have a legitimate reason to inspect, do not redistribute the
binary or the decompilation, and remember that a mirror is a third party you are
trusting. [Limits and ethics](limits-and-ethics.md) has the rest.
