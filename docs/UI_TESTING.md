# Explorer UI checks

Run `python3 scripts/verify.py`, `python3 scripts/test_guide.py` and the Android build
before release. `ktcheck.py` is a lightweight source check, not a Kotlin compiler.

Check Android, standalone web and the installed PWA:

1. Fresh app/site data shows the optional welcome. Skip, reopen, and verify it does
   not reappear. Help → Guided tour must always replay it. Try unavailable browser
   local storage too: navigation must still work.
2. Run all eight tour steps, use Back, and exit midway. Try the actual highlighted
   controls. Finish/Skip must restore the original scene, view, cuts, layers,
   input, display switches and control tab. During a tour, feature-guide navigation
   should exit the tour and open the selected destination.
3. Search Help for views, layers, parasitics, logic, CFET and story. Each result must
   navigate to its scene/view/tab and reveal the highlighted control. Test no results.
4. At phone portrait and landscape sizes, open every tab and use each sheet position.
   Canvas dimensions and zoom must not change when opening the sheet. The background
   is translucent, not the text. Dragging sliders must not orbit the model. Orbit,
   pinch, pan and picking must still work in the uncovered stage.
5. Check a narrow 320-pixel viewport, large fonts, a tablet and a wide desktop. The
   sheet body must scroll independently; no controls should be unreachable. Expanded
   Story is a reading mode, intentionally more opaque.
6. Keyboard: open Help, search, activate a feature, use tool-tab arrow keys, zoom
   buttons and Escape. Dialog focus must stay inside while open and return on close.
   Check Android Back and TalkBack. Test reduced-motion browser settings.
7. Reload the PWA after an update, then test offline. Confirm the new guide and UI are
   cached together. Rebuild/install the APK: editing assets does not update an already
   installed application.

Implementation validation: all 16 scenes and bundled guide destinations passed the
Python checks. Headless Chrome exercised the eight tour steps, state restoration,
feature navigation and stable canvas dimensions. Full rendered-model validation was
not completed: the available test machine's Chrome GPU process lost its WebGL context.
Android source checks passed; an Android SDK/Gradle build and physical-device gesture
and readability checks remain required before release.
