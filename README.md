<img width="4000" height="3000" alt="keyboard-hero" src="https://github.com/user-attachments/assets/912e2ec0-1f34-44b0-8b41-8a9e0d0f97f5" />

> Kailh Choc v1 pinks, Chosfox CFX

# ezy54
A 54-key, column-staggered, ortholinear, wireless split keyboard, inspired by ZSA Voyager and totem.
Designed for Choc-spacing (18mm horizontal, 17mm vertical) and 1350 Choc v1 or v2 switches.

## Impressions

<img width="4000" height="3000" alt="keyboard-left" src="https://github.com/user-attachments/assets/64f6077a-da38-45d5-9764-d18071b39f98" />

> Left

<img width="4000" height="3000" alt="keyboard-bottom" src="https://github.com/user-attachments/assets/18541446-7abb-4e68-9b98-a4b11710b0f2" />

> Carry Case

<img width="4000" height="3000" alt="keyboard-top" src="https://github.com/user-attachments/assets/f007dd71-e5a4-4172-9491-80d7a7c4b7e7" />

---

## Bill of materials

For one complete board - e.g. two halves - you'll need:

- 2 Promicro NRF52840
- 2x 12-pin 0.1" (2.54mm) Pitch **3.5mm tall** Pin headers, female. *I just ordered 40-pin lengths and cut them to size.* (optional, but highly recommended). 
- 54 1N4148W SOD-123 Diodes
- 54 Kailh Low-profile 1350 Hotswap Sockets
- 54 Keyswitches, Choc v1 or v2
- 54 Choc-spaced Keycaps, Choc v1 or v2 stems
- 2 EVQPUL02K Switches ($\to$ board reset button)
- 2 SSSS811101 Switches ($\to$ power switch)
- 2 701535 3.7v, 350mAh
- 2 JST PH 2.0 THT Sockets

For the case you'll need:

- Obviously, the printed case files. See section about printing below.
- 8x M2x6mm flathead screws
- 4x M2x14mm (or 12mm) flathead screws
- 12x M2x3mm Heat set inserts
- Optionally, some painters tape.

## Build guide

### PCB manufacturing

> PCB related files are located in the `kicad` directory.

Assuming you have ordered the parts and don't want to route the PCB yourself, there's premade gerber archive located at `kicad/gerber.zip` which you can use. I've used JLCPCB, default settings (1.6mm two layer PCB) and with the black solder mask.

### Printing the case

> Case files are located in the `stl` directory.

I used a Babulab A1 mini and default slicer settings (Bambustudio). Everything was printed in their PLA Matte.

#### What do I need to print?

You'll need at least:

- 2x `ezy54_switchplate_left.stl`, which is the plate that sits on the PCB and where the keyswitches are mounted into - I recommend using the provided 3mf files for that: `ezy54_switchplate_left.3mf` and `ezy54_switchplate_right.3mf`. That'll give you mirrored versions so you have the buildplate-finish texture on the same side for both halves. 
- 2x `ezy54_case_left.stl`, which is the case where the PCB gets mounted in - same story, use the provided 3mf files for that: `ezy54_case_left.3mf` and `ezy54_case_right.3mf`. That'll also give you mirrored versions for both halves. Theoretically, you don't **need** the case, but I strongly recommend it to provide a little bit of protection for the PCB. If you're working directly with the stl, then you'll have to mirror it. I suggest using the fuzzy skin setting (in Bambustudio: `Others > Special mode > Fuzzy skin`, use "Contour").

Optional:

- 1x `ezy54_carry_case.stl`, which is a Go60-ish carry shell for the ezy54. Use `ezy54_carry_case.3mf` for a basic. I did manage to print it without support, but there's a bit of luck involved - the 3mf file uses supports.

### Soldering

Since the PCB is reversible it can get confusing quick. All of the components **except the ProMicro headers and the JST Battery connector** are soldered to the backside of each half.

1. Solder diodes, kailh hotswap sockets, reset- and powerswitches on the backside of each half. **This is also the side were you bridge all of the solder-jumpers with solder** (8 for the Mcu, 2 for the Battery connector).
2. If you have ordered the female 3.5mm tall pin headers, solder them to the front. If not, direct solder the ProMicro to the frontside of the PCB. Also solder on the JST connector to the frontside.
3. Prep the ProMicro. They are usually delivered with male pin headers. You need to solder them flush in order to ensure the MCU will fit into the case. Here's the process I have used:
<img width="9096" height="4000" alt="build-steps" src="https://github.com/user-attachments/assets/b4dd1b9a-5aab-45ff-a1e8-37dcb3f9aa5e" />

- left image: Push the pins, until they are almost flush with the plastic - a little (0.2mm) protrusion is ok. Ensure they are at the same depth.
- middle image: Insert the pins, MCU sits on the plastic, they act as the spacer for the insertion depth into the female header on the PCB. Tack-solder the outermost pins from the top (as shown in image).
- right image: Cut the pins flush with the MCU, then solder from the top. Do not use too much solder - we want to prevent the solder seeping through to the underside and forming a teardrop. Then, remove the plastic carefully - I have used a pair of flush cutters to gently lift it.

4. Mount the MCU to the header. Battery can wait for now.

> [!CAUTION]
> Before you continue it's a good idea to verify that there's no short between the JSTs +/- terminal as well as the ProMicros VCC and GND.

I suggest to load the firmware next and check that everything works before assembly.

### Loading the ZMK firmware

> Firmware related files consist of: config/, boards/, zephyr/ directories, as well as the build.yml file and the GitHub Actions workflow in .github/workflows.build.yml

Get the latest firmware from https://github.com/shoelder/ezy54/actions, select the latest run and scroll down to Artifacts - you'll be able to download the zip archive from there. If the last runs artifact is expired, just fork the repo and trigger a build.

> [!NOTE]
> There'll be two .uf2 files per half in the zip archive - a `de-ch` and an `en` version. This refers to the keycode locale that's been used. I myself require a swiss locale, but, to make the default firmware more useful for more people, I've added an english version too. You can check the keymaps out in the `config/boards/shields/ezy54` directory.

For each half:

1. Plug in the half to your device using a USB cable.
2. Press the reset button twice within 500ms - on my versions of the ProMicro, their red LED breaths gently once you've entered bootloader mode.
3. You'll see a `NICENANO` appear in your device tree. Simply drag and drop the **correct** firmware for the half your working on onto the mcu - it should eject itself automatically once the firmware is flashed.

> [!NOTE]
> If you run into trouble, there's also a `settings_reset` firmware provided in the archive. See [the ZMK troubleshooting guide](https://zmk.dev/docs/troubleshooting/connection-issues#reset-split-keyboard-procedure) on how to flash it.

### Assembly

1. Mount the battery to the frontside - I suggest a thin double-sided tape to keep it in place for easier assembly. It goes just below the MCU.
2. Mount the switchplate to the frontside - ensure it sits flush. The MCUs USB-C should be perfectly aligned to its cutout in the print.
3. Prep the lower cases halves by installing the heat set inserts.
4. Optional, but highly recommended for better sound: Cover the bottom sides of the PCBs with tape (I used masking tape). Apply the first layer quite firmly, such that it follows the contours of the hotswap sockets. You'll want to make sure that you extend the tape over the edges of the PCB. Apply at least 3 layers. In my experience anything beyond 5 layers of standard painters tape yields no further improvements. Also, it gets thick quick. Trace the PCB outline to the tape with a pen. Also, trace the screw holes. Remove the tape, and cut out the shape - make sure to inset the cut about 2-3mm, so the tape is not visible when everything is assembled. For the screw holes, cut a ~5x5mm square. Apply the tape. (There is a more detailed guile to the exact same process on the shoedler54 README: https://github.com/shoedler/shoedler54)
5. Assemble both halves and mount the screws.
6. Install the switches. Done!

---

## Modifying the ergogen config

The whole point of using ergogen, is to easily adapt the PCB to your liking. So give it a go!
Modifying the config will force you to reroute the PCB again. Though fear not - using [Freerouting](www.freerouting.app) this literally takes a minute to do (including adding freerouting to KiCad), provided you have KiCad >=8 and JRE >= 17 for Freerouting already installed.

> [!NOTE]
> To add the Freerouting KiCad integration, just follow [this](https://github.com/freerouting/freerouting/blob/master/docs/integrations.md) official guide.

> [!TIP]
> There is a local toolchain in [`tools/`](tools/README.md) that builds the config without
> ergogen.xyz and then checks it: case clearances, a pre-routing DRC on the generated board,
> STL/cross-section/point-probe inspection of the printed parts, and layered drawings. Start
> with `cd tools && npm run setup`, then `node tools/build.ts` and
> `node tools/drc-lite.ts out/pcbs/ezy54.kicad_pcb`. Its README also documents the
> footprint rotation convention that ergogen + KiCad make easy to get backwards.

1. Paste `config.yml` located in `/ergogen` into [ergogen.xyz](ergogen.xyz) and download the `ezy54.kicad_pcb` file.
2. Copy (and overwrite) `ezy54.kicad_pcb` to the `kicad` directory of this repository *(this part is only required if you intend to keep the source of this repository up to date - e.g. if you forked this)*
3. Open the PCB in KiCad (Standalone PCB editor suffices). Press `B` to fill the GND pours - zones come out of ergogen empty until KiCad calculates them once - then click on `Tools > External Plugins > Freerouting`
4. Let it rip. In my experience, the defaults of Freerouting suffice.

> [!IMPORTANT]
> Back in KiCad, run the DRC in `Inspect > Design Rule Checker`. I usually right click `> Ignore all 'Footprint not found in libraries' violations` to ignore missing ceoloide footprint warnings. This might leave you with some warnings which you need to manually resolve. For example, i usually get "Track has unconnected end", which is easily resolved by deleting the stub.

5. `File > Plot... > Generate Drill Files`, name the folder "gerber", then press `Generate` and close that popup. Press `Plot` back in the plot dialog. Done!

## References

- Flatfootfox' detailed design guide: https://flatfootfox.com/ergogen-part1-units-points/
- nickcoutsos Keymap-editor: https://nickcoutsos.github.io/keymap-editor/
- nickcoutsos Keymap-layout-tools: https://nickcoutsos.github.io/keymap-layout-tools/
- Joel Spadins zmk-locale-generator for the de-swiss keycode header: https://github.com/joelspadin/zmk-locale-generator
- ZMK guide on how to add a new shield: https://zmk.dev/docs/development/hardware-integration/new-shield
- More of my keyboards:
  - effiddy - a 50-key wireless split, inspired by totem: https://github.com/shoedler/effiddy
  - shoedler54 - a 54-key wireless split, inspired by ZSA Voyager and silakka54: https://github.com/shoedler/shoedler54
