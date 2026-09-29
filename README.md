# Poly: a touchless virtual trackpad

Poly turns an area in the air into a trackpad. You mark out a zone with your index finger
in front of a webcam. After that, pointing inside the zone moves the mouse pointer, and a
pinch clicks. Everything is done with hand gestures: no keyboard, no mouse, no touching.

It is meant for people who can't or shouldn't touch a computer while they work, such as a
mechanic with oily hands or a surgeon who must stay sterile. It is also a comfortable,
low-effort way to control a screen from a distance.

> **Status:** working, but still being tuned. It runs on Windows with an ordinary webcam.
> It can feel fiddly until the settings suit your camera, lighting and hands; see
> [Making it less fiddly](#making-it-less-fiddly).

---

## Contents

1. [What you need](#what-you-need)
2. [Install](#install-windows)
3. [Your first five minutes](#your-first-five-minutes)
4. [Setting up your space](#setting-up-your-space)
5. [Gestures](#gestures)
6. [Reading the screen](#reading-the-screen)
7. [Pointer modes: tablet and trackpad](#pointer-modes-tablet-and-trackpad)
8. [Mouse control and safety](#mouse-control-and-safety)
9. [Profiles: your zone and settings are remembered](#profiles-your-zone-and-settings-are-remembered)
10. [Camera options](#camera-options)
11. [All command-line options](#all-command-line-options)
12. [Start it from a desktop shortcut](#start-it-from-a-desktop-shortcut)
13. [Making it less fiddly](#making-it-less-fiddly)
14. [Troubleshooting](#troubleshooting)
15. [Known limitations](#known-limitations)
16. [For developers](#for-developers)

---

## What you need

- **Windows 10 or 11.** The code is plain Python and may work elsewhere, but only Windows is
  tested.
- **A webcam.** Built-in is fine; an external USB webcam that can do 720p at 60 fps is better.
- **Python 3.11 or 3.12**, from [python.org](https://www.python.org/downloads/). Newer Python
  versions are not supported yet by MediaPipe, the hand-tracking library.
  When installing, tick **"Add python.exe to PATH"**.
- A few hundred MB of disk space for the libraries.

## Install (Windows)

Open **PowerShell** and run these one at a time:

```powershell
# 1. Get the code (or download the ZIP from GitHub and unzip it)
git clone https://github.com/colget/Poly.git
cd Poly

# 2. Make a private Python environment for Poly (keeps its libraries separate)
py -3.12 -m venv venv

# 3. Switch to it (your prompt then starts with "(venv)")
venv\Scripts\activate

# 4. Install the libraries
pip install -r requirements.txt

# 5. Check everything works (optional; takes a few seconds)
pytest
```

If step 3 says *"running scripts is disabled on this system"*, either run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again, or skip activating
and use `venv\Scripts\python` instead of `python` in all the commands below.

Each time you open a new PowerShell window later, `cd` into the Poly folder and run
`venv\Scripts\activate` again before starting Poly.

## Your first five minutes

**1. Start it in preview mode.** In preview mode the real mouse is not touched:

```powershell
python poly.py --sound
```

A window opens with your camera picture, mirrored like a mirror. The banner at the top says
**DRAWING** and tells you what you can do.

**2. Make a zone. The quick way:** hold your hand up with **fingers spread (open palm)** and
keep it there for about 1.5 seconds. A green ring labelled *Quick zone* fills up, then a
rectangle appears around your hand. The banner turns green and says **ACTIVE**.

**Or draw your own shape:** point with just your index finger and **hold still** for about
0.8 s. A cyan ring fills and a dot is placed. Move and repeat for each corner, in any order.
When you have 3 or more dots, rest your finger on an earlier dot: it turns green and says
*Hold to finish*. Hold still and the dots become your zone.

**3. Point inside the zone.** The small screen map in the bottom-right corner shows a green
dot where the mouse pointer *would* go. Move your finger around the zone and watch it follow.

**4. Try a click.** While pointing inside the zone, touch your **thumb tip to your index
fingertip** (a pinch). A line joins them, turns thick and green, and "Click" appears.

**5. Move the zone.** Open your hand and hold it open for half a second. The banner says
**MOVING ZONE** and the zone follows your hand. Close your hand to drop it.

**6. Hand over the real mouse** when you're happy:

```powershell
python poly.py --control-cursor --sound
```

Your zone is remembered, so it's already there. To let go of the mouse at any time, just move
your finger out of the zone.

**7. Quit** with `Esc` or `q`, or close the window. (Quitting is the one thing that uses the
keyboard or mouse. It's something the person setting the machine up does, not the user.)

## Setting up your space

Good tracking comes mostly from the setup, not the software:

- **Keep your whole hand in view, including your palm.** MediaPipe finds a hand by its palm
  first. When you point at the lower part of the picture, your palm drops below the camera's
  view and the hand is lost. A **shaded band** at the bottom of the picture shows where this
  happens (it adjusts to how far away you are). Keep zones above it; quick zones do this
  automatically.
- **Put the camera slightly above your hand, tilted down a little,** or sit a bit further
  back, so your hand sits in the upper-middle of the picture.
- **Light your hand from the front.** Avoid a bright window behind you; a backlit hand is a
  dark shape with no detail.
- **A plain background helps.** Busy patterns and other hands or faces near your hand can
  confuse it.
- **Distance:** start at about arm's length. The further away you are, the smaller your hand
  looks to the camera; use a higher camera resolution then
  (see [Camera options](#camera-options)).
- **Zone size:** a zone about the size of your hand's span is comfortable. Bigger zones give
  finer control in tablet mode; smaller zones mean less arm movement.

## Gestures

Hold each gesture steadily; a gesture only counts once it has been stable for a few frames,
so quick accidental movements are ignored.

| Gesture | How to make it |
|---|---|
| **Point** | Index finger straight, the other three fingers curled. Thumb can be in or out. |
| **Fist** | All four fingers curled. |
| **Open palm** | All four fingers straight and spread. |
| **Pinch** | While pointing, touch your thumb tip to your index fingertip. |

### While drawing a zone (banner says DRAWING, amber)

| Do this | What happens | You'll see |
|---|---|---|
| Point and **hold still ~0.8 s** | Places a dot where your fingertip is | Cyan ring fills around your fingertip, then "Point added" |
| Hold still on an **earlier dot** (3+ dots placed) | Finishes: the dots are joined into your zone | That dot gets a green ring and "Hold to finish", then "Zone finished" |
| **Fist** held ~1 s | Removes the last dot you placed | Orange "Undo" ring, then "Point undone" |
| **Open palm** held ~1.5 s (only before any dots are placed) | Makes a ready-made rectangle zone around your hand | Green "Quick zone" ring, then "Quick zone created" |

Dots can go anywhere in any order; no lines are drawn between them while you work. When you
finish, Poly joins them into a clean outline that never crosses itself. A dot placed further
in than the others makes a notch, so irregular shapes are possible. After placing a dot, move
your finger away before the next one; holding still longer never stacks dots.

### While the zone is active (banner says ACTIVE, green)

| Do this | What happens | You'll see |
|---|---|---|
| Point **inside** the zone | Moves the mouse pointer | Fingertip dot is green; banner says "inside" |
| Point **outside** the zone | Nothing: the pointer stays put | Fingertip dot is orange; banner says "outside" |
| **Pinch** (inside the zone) | Left click | Magenta line from thumb to fingertip while closing in, thick green on the click, "Click" |
| Two quick pinches | Double-click | Two "Click" messages |
| **Open palm** held ~0.5 s | Picks the zone up | Cyan "Grab" ring, then the banner says MOVING ZONE |
| **Fist** held ~2 s | Deletes the zone so you can draw a new one | Red "Clear" ring, then "Zone cleared - draw a new one" |

Clearing needs the longest hold because it's the only destructive action.

### While moving the zone (banner says MOVING ZONE, cyan)

| Do this | What happens |
|---|---|
| Move your open hand | The zone follows the centre of your palm (it can't leave the picture) |
| Close your hand (or take it out of view) | Drops the zone where it is: "Zone placed" |

If you drop the zone with a fist and keep it clenched, it won't start the 2-second clear.
Relax your hand first; a clear always needs a fresh, deliberate fist.

## Reading the screen

- **Banner (top):** the current mode (DRAWING / ACTIVE / MOVING ZONE), plus "inside",
  "outside" or "no hand", and a one-line reminder of the gestures you can use right now.
- **Fingertip dot:** where Poly thinks your index fingertip is (smoothed to remove jitter).
- **Rings around the fingertip:** something is being held and will happen when the ring is
  full. The label and colour say what: cyan = placing a dot, orange = Undo, red = Clear,
  green = Quick zone, cyan with "Grab" = picking up the zone. Let go early to cancel.
- **Shaded bottom band:** "Too low - your palm leaves the camera view". Keep your fingertip
  above it while drawing.
- **Screen map (bottom right, once a zone exists):** a miniature of your computer screen. The
  dot shows where the pointer is: green while your finger is moving it, grey when parked.
  The label says "Mouse: ON" or "Mouse: preview", and which pointer mode is in use.
- **Status line (bottom left):** the recognised hand shape (point, fist, palm, pinch...), the
  number of dots, the frames per second, and the profile name. If something doesn't respond,
  check here first that Poly sees the gesture you're making.
- **Messages (bottom centre):** confirmations like "Point added" or "Click".
- **Sounds (`--sound`):** a short beep for each recognised action. Higher beeps mean progress
  (dot added, zone finished, click), lower beeps mean undo or clear.

## Pointer modes: tablet and trackpad

Choose with `--pointer tablet` or `--pointer trackpad`. Your choice is remembered.

**Tablet (the default)** works like a drawing tablet: each spot in the zone *is* a spot on
the screen. The top-left corner of the zone is the top-left of the screen, and so on. It's
fast and direct: to go somewhere, point there. A four-cornered zone is stretched with a
*perspective transform*, so even a lopsided zone reaches every corner of the screen (other
shapes use their outer rectangle). The outer 6% of the zone already counts as the screen
edge, so edges are easy to reach.

**Trackpad** works like a laptop trackpad: moving your finger *nudges* the pointer from
wherever it is.

- Slow movements move the pointer a little, for precise aiming; a quick flick sends it
  across the screen (pointer acceleration).
- To reposition, "lift" your finger: move it out of the zone or relax it, move back, and
  carry on. The pointer doesn't jump when you come back.
- Movement is measured relative to the size of your hand, so it feels the same close to the
  camera or across the room. It's scaled to your screen width, so a big TV behaves like a
  laptop.
- It continues from wherever the real pointer is, even if someone moved the mouse.

Try both: tablet is usually quicker to learn, trackpad is usually more precise, especially
at a distance or with a shaky camera image.

## Mouse control and safety

By default Poly **never moves the real mouse**. It only shows where the pointer would go in
the screen map. Add `--control-cursor` to hand over the real mouse:

```powershell
python poly.py --control-cursor
```

This is deliberately never remembered between runs, so a tracking glitch can never grab
your mouse by surprise. To let go of the mouse at any time, move your finger out of the zone,
make a fist or open palm, or take your hand out of view; the pointer then stays still and a
real mouse works normally.

Only the main screen is used. The screen size is detected automatically; if the pointer
can't reach part of the screen, set it yourself, e.g. `--screen 1920x1080`.

## Profiles: your zone and settings are remembered

Poly saves automatically; there is nothing to click:

- **The zone** is saved when you finish it, create a quick zone, drop it after moving, or
  clear it. Next time Poly starts **ACTIVE** with your zone and shows
  "Zone loaded from profile ...".
- **Your options** are saved too: `--camera`, `--camera-backend`, `--resolution`, `--fps`,
  `--pointer` and `--sound` / `--no-sound`. So after one run like

  ```powershell
  python poly.py --camera-backend dshow --resolution 1280x720 --fps 60 --pointer trackpad --sound
  ```

  a plain `python poly.py` starts the same way. An option you type always wins over the
  saved one (and becomes the new saved value).

Useful extras:

- `--profile NAME`: keep separate profiles, e.g. `--profile workshop` and
  `--profile office`. The last one used loads by default.
- `--fresh`: ignore what's saved and start from scratch (the next save overwrites it).

Profiles are small readable files in the `profiles` folder (`profiles\default.json`). The
zone is stored as fractions of the camera picture, so it still fits if you change
resolution. Deleting the file is the same as starting fresh.

## Camera options

If tracking feels laggy, jumpy or loses your hand, the camera settings are the biggest single
improvement:

```powershell
python poly.py --camera-backend dshow --resolution 1280x720 --fps 60
```

- `--camera-backend dshow` uses Windows' DirectShow camera driver, which is often smoother
  than the default (Media Foundation, `msmf`). Try it first.
- `--resolution 1280x720` gives more detail, which helps most when you're far from the camera.
- `--fps 60` gives more frames per second, so the pointer feels less laggy.

Cameras quietly ignore settings they can't do, so check the line Poly prints at startup
(e.g. `Camera: 1280x720 @ 60 fps reported (driver: DSHOW)`). The frame rate at the bottom
of the window is what Poly actually achieves, which can be lower than the camera's number if
your PC can't keep up. If you have more than one camera, pick one with `--camera 1` (or 2...).

## All command-line options

| Option | What it does | Remembered? |
|---|---|---|
| `--control-cursor` | Move the real mouse (otherwise preview only) | No, on purpose |
| `--pointer tablet\|trackpad` | Pointer mode (default `tablet`) | Yes |
| `--sound` / `--no-sound` | Beep when a gesture is recognised | Yes |
| `--camera INDEX` | Which webcam (default 0) | Yes |
| `--camera-backend auto\|dshow\|msmf` | Windows camera driver | Yes |
| `--resolution WxH` | Ask the camera for a resolution, e.g. `1280x720` | Yes |
| `--fps N` | Ask the camera for a frame rate, e.g. `60` | Yes |
| `--profile NAME` | Which profile to load and save | Becomes the new default |
| `--fresh` | Ignore the saved zone and settings | - |
| `--screen WxH` | Override the detected screen size | No |
| `--model PATH` | Hand model file (default: `hand_landmarker.task` next to `poly.py`) | No |
| `--source VIDEO_FILE` | Replay a recorded video instead of the camera (never saves) | No |
| `--debug-keys` | Developer keys: `d` add dot, `f` finish, `r` clear | No |
| `-h`, `--help` | Show this list | - |

## Start it from a desktop shortcut

So nobody has to type commands:

1. Right-click the desktop and choose **New > Shortcut**.
2. For the location, enter (with your own path to the Poly folder):
   ```
   "C:\Users\YOU\Desktop\GitHub\Poly\venv\Scripts\python.exe" poly.py --control-cursor
   ```
3. Name it "Poly" and finish.
4. Right-click the new shortcut, choose **Properties**, and set **Start in** to the Poly
   folder, e.g. `C:\Users\YOU\Desktop\GitHub\Poly`.

Your saved profile supplies the other settings, so the shortcut only needs
`--control-cursor`.

## Making it less fiddly

All timings and thresholds live in one file, `poly/config.py`, with a comment explaining
each. Change a number, save, and restart Poly. The ones that matter most:

| If... | Change | Default |
|---|---|---|
| Placing a dot takes too long, or happens by accident | `dwell_time_s` (hold time) | 0.8 |
| Dots are hard to place because your hand wobbles | `dwell_radius_hands` (bigger = more forgiving) | 0.25 |
| The pointer feels jittery | `filter_min_cutoff_hz` (lower = steadier but laggier) | 0.5 |
| The pointer feels laggy | `filter_min_cutoff_hz` (higher) | 0.5 |
| Clicks don't register | `pinch_press_gap` (higher = easier to click) | 0.25 |
| Accidental clicks | `pinch_press_gap` (lower) | 0.25 |
| The pointer freezes too early when you start a pinch | `pinch_release_gap` (lower) | 0.45 |
| Pointing or fists aren't recognised (check the status line) | `finger_extended_ratio` | 1.3 |
| The hand is lost too easily | `min_hand_detection_confidence` and friends (lower) | 0.5 |
| Trackpad mode feels sluggish / too fast | `trackpad_min_gain`, `trackpad_max_gain` | 0.25, 1.5 |
| Screen edges are hard / too easy to reach (tablet) | `cursor_edge_padding` | 0.06 |
| The shaded "too low" band is too big for your camera | `reach_margin_hands` | 2.0 |
| Moving the zone starts too easily | `grab_hold_s` | 0.5 |

Change one thing at a time. The status line (hand shape) and frame rate make it easy to see
what Poly is actually seeing.

## Troubleshooting

**The window opens but there's no picture / "cannot open webcam".** Another app (Teams, Zoom,
the Camera app) may be using it; close it. Or try `--camera 1`. Or try
`--camera-backend dshow`.

**The fingertip dot keeps disappearing.** Your palm is probably out of view (see the shaded
band), the lighting is poor, or the background is busy. See
[Setting up your space](#setting-up-your-space). Try `--resolution 1280x720` if you're far away.

**It says "point" when I make a fist (or the other way round).** Check the status line while
you hold the gesture. Make gestures clearly facing the camera; fingers pointing straight at
the lens are harder to read. Adjust `finger_extended_ratio` if needed.

**Clicks land slightly off target.** The pointer freezes as your thumb approaches, so aim
first, then pinch without moving your hand. Trackpad mode is usually more precise.

**The pointer can't reach one edge, or overshoots.** Set your screen size, e.g.
`--screen 1920x1080`. With Windows display scaling (125%, 150%) Poly may report a smaller
size such as 1536x864; that's normal and still reaches the whole screen.

**My zone is gone / in a strange place.** Start with `--fresh` and make a new one, or delete
`profiles\default.json`.

**Lots of `W0000 ...` / `INFO: Created TensorFlow Lite ...` lines in the console.** These are
MediaPipe's normal start-up messages and can be ignored.

**`pip install` fails.** Check `python --version` says 3.11 or 3.12. Newer versions aren't
supported by MediaPipe yet.

## Known limitations

- **Gloves are untested.** MediaPipe is trained on bare hands. Nitrile, latex and especially
  dark work gloves may be detected poorly or not at all. Please test with the gloves you'll
  actually use.
- **Lighting and background matter a lot.** Backlighting, dim rooms and busy backgrounds
  reduce tracking quality.
- **Camera placement:** the palm must be visible, so the lower part of the picture is not
  usable for pointing (the shaded band).
- **One hand, one main screen.** Only the first hand found is tracked, and only the primary
  monitor is used.
- **Left click only.** No right-click, drag, or scrolling yet.
- **Quitting uses the keyboard or mouse** (Esc/q or closing the window).
- **Cheap webcams are laggy at their default settings**; see
  [Camera options](#camera-options).
- **Python 3.11 or 3.12 only**, because of MediaPipe.
- **Tested on Windows only.**

---

## For developers

**Layout.** All decisions are made in pure, tested code; only a thin layer touches the
camera, window and mouse.

```
poly.py            entry point: `from poly.app import main`
poly/
  app.py           main loop, command-line options, profile loading/saving (I/O layer)
  config.py        every threshold and timing, with explanations
  tracker.py       MediaPipe wrapper - the only module that imports mediapipe
  cursor.py        mouse backend (pynput) - the only module that moves the real mouse
  feedback.py      on-screen overlays and sounds
  modes.py         the DRAWING / ACTIVE / MOVING ZONE state machine
  gestures.py      hand-shape classification, pinch detection, dwell and hold timers
  filters.py       One Euro filter (smoothing) and frame-rate meter
  geometry.py      point-in-polygon, zone shapes, zone -> screen mapping (perspective transform)
  pointer.py       trackpad mode (relative movement with acceleration)
  profiles.py      saving and loading profiles as JSON
tests/             pytest suite, driven by synthetic hand landmarks and simulated time
```

**Tests.** Run `pytest`. The gesture and state-machine tests build fake 21-point hands
(`tests/synthetic_hands.py`) and feed them frame by frame with simulated timestamps, so
"hold a fist for 2 seconds" runs instantly and needs no camera.

**Repeatable manual testing.** Record a short clip of your hand and replay it with
`--source clip.mp4`; replays use the clip's own timeline and never change your profile.
`--debug-keys` adds keyboard shortcuts (`d` add dot, `f` finish, `r` clear) for developers.

**Design notes** are in `CLAUDE.md`: the gesture spec, why each gesture was chosen, and the
recognition rules (debouncing, hysteresis, the reach band).

## Background

Most air-gesture mice track your hand across the whole camera view, which means big,
tiring arm movements and a pointer that reacts to every stray gesture. Poly's bounded,
user-defined zone keeps movements small and ignores everything outside it. Possible uses
include workshops and operating theatres (dirty or sterile hands), accessibility, kiosks,
presentations on large screens, and environments where physical mice are impractical.

Built with [MediaPipe Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker),
OpenCV and pynput.
