# Privacy Policy — FET Lab

_Last updated: 3 October 2026_

**The FET Lab Android app has no personal-data collection or analytics.**

The website/PWA makes network requests as described below.

## What the app does not do

- It has **no internet permission**. Look at `AndroidManifest.xml`: there is no
  `android.permission.INTERNET`. It does not make direct network requests.
- It has **no analytics, crash reporting, advertising or tracking SDK** of any kind.
- It does **not** request the camera, microphone, location, contacts, storage, or any
  other runtime permission.
- It does **not** create an account, and there is nothing to sign in to.

## What the app stores on your device

The Android app saves four local preferences: whether you have seen or skipped the guided
tour, whether you have seen the Process mode tour, how see-through you set the control sheet,
and which nanosheet channel design you picked. None is personal data, and FET Lab does not
transmit them. You can replay the tours from Help; clearing the app's data resets all four. Geometry, the guide and technical references are read-only assets bundled in the APK.

Each scene remembers its camera, cuts and hidden layers while the app is open, so you can
switch away and come back; this is held in memory only and is gone when the app closes.
Other scene and display controls are not stored as durable user profiles. Android may
retain temporary UI state when recreating an activity. Backup and device-transfer exclusions
are configured in `res/xml/data_extraction_rules.xml`.

## Website and PWA

The no-internet-permission statement above applies to the Android APK, not the website.
The website makes normal requests to its hosting provider and loads fonts from Google
Fonts. Those providers can receive request information such as your IP address under
their own policies. The PWA caches app files for offline use, and the page keeps a few
display preferences in your browser's local storage: whether you have seen the two tours,
the nanosheet channel design and CFET integration you picked, and the last panel tab. They
stay in your browser and are not sent anywhere. Clearing site data removes the caches and
these preferences. FET Lab adds no analytics, advertising or tracking SDK.

## Links out of the app

The About screen links to the source repository, issue tracker, privacy policy and
technical references. Tapping a link hands the URL to your browser. Tapping the email address hands it to
your mail app. Once you leave FET Lab, that other app's privacy policy applies, not this
one.

## Children

The app presents educational semiconductor models and has no age-restricted content.
It does not ask for age or other personal information. External websites have their own policies.

## Changes

If this ever changes, the updated policy will appear at this URL and the change will be
noted in the release notes.

## Contact

Khandaker Ehsanul Karim — ehsan.pappu.99@gmail.com
