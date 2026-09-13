# Publishing FET Lab to Google Play

Everything below is the real checklist, in the order you actually do it.

---

## 0. Before anything

- A **Google Play Developer account** — one-off $25, and identity verification that can
  take a few days. Start this first; it is the only step with a queue.
- **Android Studio** (Ladybug 2024.2.1 or newer) and **JDK 17**.
- The app must build and run on a real device. It has never been compiled by its author's
  tooling, so **do this before anything else**:

```bash
cd android
./gradlew assembleDebug && ./gradlew installDebug
```

Fix whatever the compiler says before going further. Nothing else on this list matters
until a debug build runs on a phone.

---

## 1. Set your identity

Two places, both one line each.

**`android/app/build.gradle.kts`** — the application ID is permanent once published. It is
currently `io.github.ehsanulkarimpappu.fetlab`, which is fine if that is your GitHub username.
If it is not, change `namespace` and `applicationId` together, and move the source folder
to match.

**`android/app/src/main/java/.../AppInfo.kt`** — already points at
`github.com/ehsanul-karim-pappu/fet-lab`. Create that repository (or change `REPO` and
`SLUG` if you name it something else) before the first release, because the About screen
links to it and Play will check the privacy-policy URL resolves.

---

## 2. Create the upload key

Google signs the app you ship; you sign the *upload*. Lose this key and you can still
recover through Play App Signing, but do not lose it.

```bash
cd android
keytool -genkey -v -keystore upload-keystore.jks \
  -keyalg RSA -keysize 2048 -validity 10000 -alias upload
```

Then create `android/keystore.properties` — **already git-ignored, never commit it**:

```properties
storeFile=upload-keystore.jks
storePassword=<what you typed>
keyAlias=upload
keyPassword=<what you typed>
```

Back up the `.jks` and those passwords somewhere that is not this repository.

---

## 3. Build the release bundle

Play takes an **App Bundle** (`.aab`), not an APK.

```bash
cd android
./gradlew bundleRelease
# → app/build/outputs/bundle/release/app-release.aab
```

Test the release build before uploading — R8 is on, and minification is where things break:

```bash
./gradlew assembleRelease
./gradlew installRelease
```

Open every scene, rotate the phone, switch modes, open About and tap each link. If
something only breaks in release, it is a ProGuard rule; add it to `proguard-rules.pro`.

---

## 4. Screenshots

Play requires screenshots **of the actual app**. Not mockups, not the web version.

- Phone: 2–8 images, at least 1080 px on the short side, 16:9 or 9:16.
- Take them with Android Studio's **Running Devices** screenshot button, or
  `adb exec-out screencap -p > shot.png`.

Suggested set, in order: the isometric nanosheet device, the across-channel section with
callouts, a layout figure, an inverter with the logic bar visible, and the four-way
compare.

A 7-inch and 10-inch tablet screenshot each is optional but the listing looks unfinished
without them, and the app has a proper wide layout, so it is worth the two minutes.

---

## 5. Store listing

Copy is written for you in `store/listing.md`. Assets are in `store/`:

| Asset | Spec | File |
|---|---|---|
| App icon | 512×512 PNG, 32-bit | `store/icon-512.png` |
| Feature graphic | 1024×500 PNG | `store/feature-graphic-1024x500.png` |
| Screenshots | see above | you capture these |

Category: **Education**. Tags: science, engineering, reference.

---

## 6. Play Console declarations

These are the ones that trip people up. For this app the answers are unusually simple,
because it collects nothing and has no internet permission.

| Section | Answer |
|---|---|
| **Privacy policy** | Required. Publish `PRIVACY.md` — the GitHub Pages workflow or the raw GitHub URL both work. |
| **Data safety** | "Does your app collect or share any of the required user data types?" → **No**. "Is all of the user data encrypted in transit?" → not applicable. Declare nothing. |
| **App access** | All functionality available without restrictions — no login. |
| **Ads** | Contains no ads. |
| **Content rating** | Fill the questionnaire honestly; everything is "no". You will get **Everyone / PEGI 3**. |
| **Target audience** | 13+ is the simplest choice. Selecting under-13 pulls you into Families policy and extra review for no benefit here. |
| **Government app** | No. |
| **Financial features** | None. |
| **Health** | None. |

---

## 7. Release tracks

Do not go straight to production.

1. **Internal testing** — up to 100 testers, available in minutes. Put it on your own
   phone through Play, not sideloaded. This is where you catch a broken release build.
2. **Closed testing** — a handful of colleagues. Google now requires a period of closed
   testing with real testers before a personal developer account can promote to
   production; check the current requirement in Console, it has changed before.
3. **Production** — first review typically takes a few days.

---

## 8. After it is live

- **Crash reports**: Play Console → Quality → Android vitals. R8's `mapping.txt` is
  uploaded automatically with the bundle, so stack traces come back deobfuscated.
- **Version bumps**: `versionCode` must increase on *every* upload — it is the only thing
  Play compares. `versionName` is what users see. Tag the matching commit:

```bash
git tag -a v1.0.0 -m "First release" && git push --tags
```

- Attach the `.aab` and the release APK to the GitHub release so people who do not use
  Play can still install it.

---

## Known gaps to close before you publish

- The app has never been compiled. Build it first.
- No unit or instrumentation tests exist.
- Only English. `resourceConfigurations` is pinned to `en` — remove that line if you add
  translations.
- No in-app update flow, no review prompt. Neither is required.
