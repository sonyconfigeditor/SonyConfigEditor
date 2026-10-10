# Dependencies in the camera menu (from the manuals and the camera tests)

State 2026-10-09. Sources: the manuals of the FS7 (Mk1) and FS7 II (Mk2) as text extracts, plus observations from test files ("test"). Column *Status*: **done** = modelled in the program as a lock (`_locks`), a restriction of the choice (`requires`) or a companion value (`companions`); **open (ID)** = the condition is known, but the setting concerned has no ID yet; **open (model)** = not yet modelled in the GUI.

## Paint
| If ... | then ... | Source | Status |
|---|---|---|---|
| Shooting Mode = Cine EI | whole Paint menu locked; gain, scene file and lens file cannot be set | manual, test | done (Paint lock) |
| Gamma Setting = Off | all other gamma settings locked | test (gamma round 1) | done |
| Gamma Category is not STD | **Knee Setting** and **Black Gamma Setting** not active | manual (Mk1 and Mk2) | open (ID: knee / black gamma, rounds 11/12) |
| Knee Saturation = On | **Black Gamma** cannot be used at the same time (and the other way round) | manual | open (ID) |
| Gamma Category = S-Log2 or S-Log3 | **White Clip Setting** cannot be set (the camera switches it off) | manual, test | done (lock of the setting; choosing the category sets it) |
| White Clip Setting = Off | White Clip Level locked | test | done |
| White Clip Setting | returns to On when the camera is switched off; permanently off = level 109 % | manual | hint text only |
| Matrix Setting = Off | Adaptive Matrix, Preset Matrix, User Matrix, **Multi Matrix** locked | test (rounds 6, 7) | done |
| Preset Matrix = Off | Preset Select cannot be chosen | test (round 10) | done |
| Recording format is not 4K/QFHD | Preset Select **BT.2020** cannot be chosen (FS7 II only) | manual Mk2, test | done (ALL only, where the format is stored) |
| Detail Setting = Off | other detail settings locked | assumption as with gamma/black | done (not checked on the camera) |
| Level Depend = Off | Level Depend Level locked | test | done |
| Knee Aperture = Off | Knee Aperture Level locked | assumption | done |
| Aperture Setting = Off | Aperture Level locked | assumption | done |
| Multi Matrix Setting = Off | Multi Matrix (hue/saturation per axis) locked | assumption | done |
| Black Setting = Off | Master/R/B Black locked | assumption as with gamma | done |

## System / Video
| If ... | then ... | Source | Status |
|---|---|---|---|
| Shooting Mode = Custom | Color Space is **Matrix** | manual, test | done |
| Shooting Mode = Cine EI | Color Space S-Gamut/SLog2, S-Gamut3.Cine/SLog3 or S-Gamut3/SLog3 (not Matrix); Monitor LUT (MLUT) off when the colour space changes | manual, test | colour space done, MLUT open (ID) |
| Shooting Mode = Custom | Monitor LUT not available ("only when recording in Cine EI mode") | manual Mk1/Mk2 | open (ID) |
| Color Space is not S-Gamut/SLog2 | Monitor LUT choice **S-Log2** not available | manual | open (ID) |
| Color Space is neither S-Gamut3.Cine/SLog3 nor S-Gamut3/SLog3 | Monitor LUT choice **S-Log3** not available | manual | open (ID) |
| Color Space = S-Gamut/SLog2 | **User 3D LUT** cannot be chosen | manual | open (ID) |
| Codec = RAW, RAW & ... | only in Cine EI (and only with the XDCA-FS7); RAW 4096 needs scan mode Normal, RAW 2048 needs 2K Full/Center | manual, test | done |
| Codec = ProRes 422 / 422 HQ | only with the XDCA-FS7; HDMI Target Device not "Recorder" | manual | open (model) |
| Codec = RAW | **Parallel Rec** (SDI/HDMI Rec Control) cannot be chosen (FS7 II only) | manual Mk2 | open (ID) |
| Frame rate 24.00P (not 23.98P) | in the format list of the menu (NTSC) **only with codec XAVC-I and 4096x2160**; all other resolutions and codecs have 23.98P only. The manual does not tie it to Cine EI | manual Mk1 (page 104) and Mk2 | the format list contains exactly this entry (assumed format) |
| Interlaced format | frame rates up to and including 30p do not exist interlaced | test, manual | done (check rule) |
| Format/codec | S&Q frame rates per codec, region and scan mode (for example RAW only 2K 120/240 NTSC, 100/200 PAL; XAVC-I only up to 60) | manual | open (model) |
| S&Q Motion = On | auto iris and autofocus deactivated; no audio recording; Picture Cache Rec and Interval Rec not at the same time | manual | open (model) |
| Interval Rec | switched off automatically when the video format changes or after a restart; not together with Picture Cache Rec, S&Q | manual | open (model) |
| HDMI Target Device | controls which output/display combinations (SDI/HDMI, OSD, MLUT) can be chosen; invalid values are forced to the default | manual (table) | open (model) |
| Zoom Speed Type = Fix | Zoom Speed active only then; without the grip the zoom lever settings and auto black balance are deactivated | manual (hardware) | open (model) |
| Manual exposure | Detect Window (auto iris measuring area) not available | manual | open (model) |
| Slow/quick motion mode | Interval Rec/Picture Cache excluded; no audio recording | manual | open (model) |
| Distortion Comp. | not in the buffer recording mode and not during recording; not applied at 4K/QFHD | manual | open (model) |
| Audio Input | audio input level settings deactivated depending on the combination of the audio menus (diagram on page 142 of the Mk1 manual) | manual | open (model, audio follows) |

## Notes on the method
- Both manual text extracts were searched for "only available", "can only", "not at the same time", "is active when", "this option cannot", "automatically", "forcibly", "deactivated", "greyed out" (in the German manuals). The Mk2 layout (several columns) mixes columns; some hits there can be assigned safely only through the Mk1 wording.
- The restriction table at the end of the manual ("yes/no" for ALL and scene file) contains no dependencies, only which menu items are stored in which file.
- The "open (ID)" items are settled with the next camera files; the "open (model)" items first need the setting as an ID.
