# shadowrun-randomizer
Randomizer for Shadowrun (SNES)

## Quick Start
* To generate a seed without downloading or installing anything, use the web interface:
  [osteoclave.github.io/shadowrun-randomizer](https://osteoclave.github.io/shadowrun-randomizer)
* If you want to download the randomizer and generate seeds locally, read on.

## Local Setup
1. Check if you have Python installed.
   * Open a command prompt and try the following commands:
      * `py --version`
      * `python --version`
      * `python3 --version`
   * If one of these returns a Python 3.x version string (e.g. `Python 3.11.2`), you should be good to go.
   * If not, [download and install Python](https://www.python.org/downloads/).
1. Click the green "Code" button at the upper right of this repository page, then "Download ZIP".
1. Extract the ZIP archive's contents to a convenient directory.
1. Copy a Shadowrun (USA) ROM into the directory from the previous step.
1. **Optional:** Validate your Shadowrun (USA) ROM.
   * The ROM should be 1,048,576 bytes long.
      * If your ROM is 1,049,088 bytes long, it has a 512-byte copier header at the start.
      * You can remove the copier header with NSRT ([Windows](https://www.romhacking.net/utilities/400/),
        [Mac](https://www.romhacking.net/utilities/484/), [Linux](https://www.romhacking.net/utilities/401/)).
   * The ROM should have the following checksums:
     ```
       CRC32: 3F34DFF0
         MD5: 694BE8DF403EE59225C4B6B53C30FB7B
       SHA-1: B04AFB21C94DAB5C8B982D0C133898DD5EC1D104
     SHA-256: E6BC0A595D5C7C4BC0BBB61FFE35A70288A77EB78544ED74682D489A9E6F07F4
     ```

## Usage
* Open a command prompt and navigate to the directory with the randomizer files and Shadowrun (USA) ROM.<br/>
  These examples assume the ROM file name is: `Shadowrun (USA).sfc`
* To see the randomizer's own usage text:
   * `py shadowrun_randomizer.py -h`
* To generate a randomized ROM with no particular settings:
   * `py shadowrun_randomizer.py "Shadowrun (USA).sfc"`
   * This will generate a randomized ROM named: `Shadowrun (USA)_SEED.sfc`
* To generate a randomized ROM from a specific seed, use `-s SEED`
   * Valid seed values are 0 to 4294967295 (= 0 to 2<sup>32</sup> - 1).
   * Values outside that range will be mapped into that range via modulus.
   * Sample run:
     ```
     py shadowrun_randomizer.py -s 3816547290 "Shadowrun (USA).sfc"

     Version: YYYY-MM-DD
     Seed: 3816547290
     Flags: -

     Generating...
     Generated winnable seed on attempt #nnnn
     ```
* To view the spoiler log for the resulting ROM, use `-l`
* To perform a dry-run (do all the randomization, but don't generate a new ROM), use `-n`
   * This can be useful with `-s` and `-l` to preview the outcome for a given seed.
   * In dry-run mode, the ROM file name is optional and can be omitted.
* To re-enable the item duplication bug, use `-D`
* To specify the generated ROM's file name, use `-o OUTPUT_FILE_NAME`

## Gameplay
* If everything worked correctly, the title screen will show the randomizer version, seed, and flags.
* To win the game, complete the following tasks in any order:
   * Rescue Professor Pushkin from Drake Volcano
   * Destroy the AI Computer in the Aneki Building
* Items have been shuffled among their vanilla locations, plus the following:
   * The end of the Tenth Street alley (where the "hmmm...." dog is in vanilla)
   * Next to Glutman's booth at The Cage (after you've asked Glutman's secretary about Glutman)
   * Dropped by the Octopus
   * Dropped by the Rat Shaman (2 items)
   * The back of the left room at the Dark Blade mansion (where Vladimir is in vanilla)
   * Dropped by the Vampire (2 items)
   * Dropped by the Jester Spirit (2 items, up from 1 - the Jester Spirit Insignia - in vanilla)
* The following locations are incentivized, and will provide key items:
   * Dropped by the Rust Stiletto gang leader
   * Dropped by the Octopus
   * Dropped by the Rat Shaman (both items)
   * Dropped by the Vampire (both items)
   * Dropped by the Jester Spirit (both items)
* Five keywords are known by default at the beginning of the game:
   * HitMen
   * Firearms
   * Heal
   * Shadowrunners
   * Hiring
* Five keywords are now learned by picking up "keyword-items", shuffled among item locations:
   * Dog
   * Jester Spirit
   * Bremerton
   * Laughlyn
   * Volcano
* The following items are key items:
   * The five "keyword-items" listed above
   * Scalpel
   * Credstick
   * Dog Collar
   * Door Key
   * Cyberdeck
   * Magic Fetish
   * Stake
   * Iron Key
   * Crowbar
   * Drake Password
   * Bronze Key
   * Green Bottle
   * Jester Spirit Insignia
* Shadowrunners have been shuffled among their vanilla locations...
   * ...plus one: the Lonely Gal's location at The Cage
   * Jetboy will always be at Wastelands
   * Akimi is unchanged from vanilla
* Walking speed has been doubled from vanilla.
* Nuyen dropped by defeated enemies is automatically picked up.
   * This does not affect the 3,000-nuyen bundles that sometimes appear in item locations
* You can get one Slap Patch from the morgue fridge any time you have zero Slap Patches.
* There is a guaranteed early-game weapon and armor in the Tenth Street alley.
* Items from NPC conversations are generally unchanged (e.g. LoneStar Badge from Business Man)...
   * ...except for Chrome Coyote, who now gives you a random item after you heal him
   * Picking up the Magic Fetish now silently teaches you the associated keyword
* The Tenth Street monorail is open for business when the game begins.
* The King starts out paid off, so you can enter and leave the caryards freely.
* You don't have to defeat the Rust Stilettos to enter Jagged Nails.
* The Aneki Password is no longer required to enter the Aneki Building.
* Remember that you can hire shadowrunners to help you out.
