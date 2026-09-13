# Privacy Policy — FET Lab

_Last updated: 12 September 2026_

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

Nothing that persists. All geometry is read from a read-only asset bundled inside the
APK (`devices.json`). Your current scene and toggle settings live in memory only and are
gone when the app closes. Android's automatic backup is explicitly disabled in
`res/xml/data_extraction_rules.xml`.

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
