# Privacy Policy — FET Lab

_Last updated: 19 September 2026_

**FET Lab does not collect, store, transmit or share any personal data.**

That is the whole policy, but here is what it means concretely.

## What the app does not do

- It has **no internet permission**. Look at `AndroidManifest.xml`: there is no
  `android.permission.INTERNET`. The app physically cannot send anything anywhere.
- It has **no analytics, crash reporting, advertising or tracking SDK** of any kind.
- It does **not** request the camera, microphone, location, contacts, storage, or any
  other runtime permission.
- It does **not** create an account, and there is nothing to sign in to.

## What the app stores on your device

The Android app stores the version of the guided tour you have started or skipped in
local DataStore preferences, so it does not repeatedly show the first-launch prompt.
This is not personal data and never leaves the device. Help lets you replay the tour
without clearing it. Geometry and the feature guide are bundled read-only assets
(`devices.json` and `guide.json`). Scene controls are not saved as durable preferences.
Android's automatic backup is disabled in `res/xml/data_extraction_rules.xml`.

The web viewer and PWA store the same tour-version preference in your browser's local
storage. The PWA also caches its files for offline use. Clearing the site's data removes
both. If local storage is unavailable, the viewer still works, but the welcome prompt
may appear again. Loading the website or following external links makes normal requests
to its hosting provider; FET Lab adds no analytics or tracking.

## Links out of the app

The About screen has three links: the source repository, the issue tracker, and this
policy. Tapping one hands the URL to your browser. Tapping the email address hands it to
your mail app. Once you leave FET Lab, that other app's privacy policy applies, not this
one.

## Children

The app contains nothing age-sensitive and collects no data, so it is suitable for all
ages.

## Changes

If this ever changes, the updated policy will appear at this URL and the change will be
noted in the release notes.

## Contact

Khandaker Ehsanul Karim — ehsan.pappu.99@gmail.com
