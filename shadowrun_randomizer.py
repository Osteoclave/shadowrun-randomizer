#!/usr/bin/env python3
#
# Shadowrun Randomizer
# Osteoclave
# 2021-05-03

import argparse
import pathlib
import random
import struct
import sys
import textwrap

from collections import defaultdict, deque
from enum import Enum, Flag, auto



# Randomizer version: The current version's release date in YYYY-MM-DD format.
# Update this with each new release.
# Add a suffix (e.g. "/b", "/c") if there's more than one release in a day.
# Title screen space is limited, so don't use more than 13 characters.
randomizerVersion = "2024-06-21"

# Process the command line arguments.
parser = argparse.ArgumentParser(
    description = textwrap.dedent(f"""\
        Shadowrun Randomizer
        (version: {randomizerVersion})"""
    ),
    formatter_class = argparse.RawTextHelpFormatter,
)
parser.add_argument(
    "-v", "--version",
    action = "version",
    version = randomizerVersion,
)
parser.add_argument(
    "-n", "--dry-run",
    action = "store_true",
    help = "execute without saving any changes",
)
parser.add_argument(
    "-s", "--seed",
    type = int,
    help = "specify the RNG seed value",
)
parser.add_argument(
    "-l", "--spoiler-log",
    action = "count",
    help = "print spoiler log",
)
parser.add_argument(
    "-D", "--allow-item-duplication",
    action = "store_true",
    help = "allow item duplication and quantity underflow",
)
# This option should be named "input-file". It isn't because of a bug with
# dash-to-underscore replacement for positional arguments:
# https://bugs.python.org/issue15125
# Workaround: Name the option "input_file" so we can use "args.input_file"
# to get its value, and set "metavar" so the name appears as "input-file"
# in help messages.
parser.add_argument(
    "input_file",
    metavar = "input-file",
    nargs = "?",
    help = "input file name: a 'Shadowrun (USA)' ROM"
)
parser.add_argument(
    "-o", "--output-file",
    type = str,
    help = "output file name"
)
args = parser.parse_args()

if args.input_file is None and not args.dry_run:
    parser.error("Argument 'input-file' is required when not in dry-run mode")

randomizerFlags = ""

if args.allow_item_duplication:
    randomizerFlags += "D"



# Seed the random number generator.
rng = random.Random()
seed = args.seed
if seed is None:
    seed = random.SystemRandom().getrandbits(32)
seed %= 2**32
rng.seed(seed)

print(f"Version: {randomizerVersion}")
print(f"Seed: {seed}")
print(f"Flags: {(randomizerFlags if randomizerFlags else '-')}")
print()

# If we have an input file (required for normal runs but optional for
# dry runs), then read the input and initial-item-state files.
# We don't need either of those right away, but if something is wrong
# (e.g. file not found), we want to fail quickly.
# Similarly, exit early if the output file name is already in use.
if args.input_file is not None:
    # Read the input file.
    inFileName = args.input_file
    with open(inFileName, "rb") as inFile:
        romBytes = bytearray(inFile.read())

    # Sanity-check the input file.
    if len(romBytes) != 1048576:
        raise ValueError(f"Input file '{inFileName}' is not 1048576 bytes in size")
    romName = bytes(romBytes[0x7FC0:0x7FD5])
    goodName = b"SHADOWRUN            "
    if romName != goodName:
        raise ValueError(f"Unexpected internal ROM name: {romName} # Expected: {goodName}")
    romChecksum = struct.unpack_from("<H", romBytes, 0x7FDE)[0]
    goodChecksum = 0xF834
    if romChecksum != goodChecksum:
        raise ValueError(f"Unexpected internal checksum: 0x{romChecksum:04X} # Expected: 0x{goodChecksum:04X}")

    # Read the (decompressed) "initial item state" data from a file.
    # In the ROM, this data is LZ77-compressed and located at 0x5FC42.
    # The decompressed data is 3,515 bytes long (703 entries * 5 bytes),
    # and is located in WRAM at 7E2E00.
    with open("initial_item_state.bin", "rb") as iisFile:
        initialItemState = bytearray(iisFile.read())

    # Determine the output file name.
    outFileName = args.output_file
    if outFileName is None:
        suffix = f"_{seed}"
        if randomizerFlags:
            suffix += f"_{randomizerFlags}"
        basename, dot, extension = inFileName.rpartition(".")
        if basename and extension:
            basename += suffix
        else:
            extension += suffix
        outFileName = basename + dot + extension

    # If a file already exists with that name, exit.
    outFilePath = pathlib.Path(outFileName)
    if outFilePath.is_symlink() or outFilePath.exists():
        raise FileExistsError(f"Output file '{outFileName}' already exists")



########################################################################
# CREATE THE RANDOMIZER LOGIC
########################################################################

Progress = Enum(
    "Progress",
    [
        # Keywords
        "KEYWORD___AKIMI",
        "KEYWORD___ANDERS",
        "KEYWORD___BREMERTON",
        "KEYWORD___CALLS",
        "KEYWORD___CARYARDS",
        "KEYWORD___CORTEX_BOMB",
        "KEYWORD___CYBERWARE",
        "KEYWORD___DARK_BLADE",
        "KEYWORD___DATAJACK",
        "KEYWORD___DECKER",
        "KEYWORD___DOCKS",
        "KEYWORD___DOG",
        "KEYWORD___DRAKE",
        "KEYWORD___EXAMINATION",
        "KEYWORD___FIREARMS",
        "KEYWORD___GHOULS",
        "KEYWORD___GLUTMAN",
        "KEYWORD___GRINDER",
        "KEYWORD___HEAD_COMPUTER",
        "KEYWORD___HEAL",
        "KEYWORD___HIRING",
        "KEYWORD___HITMEN",
        "KEYWORD___ICE",
        "KEYWORD___JESTER_SPIRIT",
        "KEYWORD___KING",
        "KEYWORD___KITSUNE",
        "KEYWORD___LAUGHLYN",
        "KEYWORD___LONE_STAR",
        "KEYWORD___MAGIC_FETISH",
        "KEYWORD___MARIA",
        "KEYWORD___MATRIX_SYSTEMS",
        "KEYWORD___MERMAIDS",
        "KEYWORD___NEGOTIATION",
        "KEYWORD___NUYEN",
        "KEYWORD___RAITSOV",
        "KEYWORD___RAT",
        "KEYWORD___SHADOWRUNNERS",
        "KEYWORD___SHAMAN",
        "KEYWORD___STEELFLIGHT",
        "KEYWORD___STREET_DOC",
        "KEYWORD___STROBES",
        "KEYWORD___TALISMANS",
        "KEYWORD___THE_CAGE",
        "KEYWORD___THE_MATRIX",
        "KEYWORD___TICKETS",
        "KEYWORD___VAMPIRES",
        "KEYWORD___VOLCANO",
        # Weapons
        "WEAPON___BERETTA_PISTOL",
        "WEAPON___COLT_L36_PISTOL",
        "WEAPON___FICHETTI_L_PISTOL",
        "WEAPON___VIPER_H_PISTOL___3000",
        "WEAPON___VIPER_H_PISTOL___4000",
        "WEAPON___WARHAWK_H_PISTOL",
        "WEAPON___T_250_SHOTGUN___12000",
        "WEAPON___T_250_SHOTGUN___15000",
        "WEAPON___UZI_III_SMG",
        "WEAPON___HK_277_A_RIFLE",
        "WEAPON___AS_7_A_CANNON",
        # Armor
        "ARMOR___LEATHER_JACKET",
        "ARMOR___MESH_JACKET___FREE",
        "ARMOR___MESH_JACKET___5000",
        "ARMOR___BULLETPROOF_VEST",
        "ARMOR___CONCEALED_JACKET",
        "ARMOR___PARTIAL_BODYSUIT",
        "ARMOR___FULL_BODYSUIT",
        # Items
        # For the Slap Patch, see "EVENT___UNLIMITED_SLAP_PATCHES"
        "ITEM___BLACK_BOTTLE",
        "ITEM___BROKEN_BOTTLE",
        "ITEM___BRONZE_KEY",
        "ITEM___CREDSTICK",
        "ITEM___CROWBAR",
        "ITEM___CYBERDECK",
        "ITEM___DETONATOR",
        "ITEM___DF_AN_ANTI_AI",
        "ITEM___DF_AN_PAYMENT",
        "ITEM___DF_BADNEWS",
        "ITEM___DF_DB_JESTER",
        "ITEM___DF_DR_1_4",
        "ITEM___DF_DR_2_4",
        "ITEM___DF_DR_3_4",
        "ITEM___DF_DR_4_4",
        "ITEM___DF_DR_MATRIX",
        "ITEM___DF_DR_VOLCANO",
        "ITEM___DF_DS_AI_END",
        "ITEM___DF_DS_AKIMI",
        "ITEM___DF_DS_FAILURE",
        "ITEM___DF_DS_TARGET",
        "ITEM___DF_MT_AI",
        "ITEM___DOG_COLLAR",
        "ITEM___DOG_TAG",
        "ITEM___DOOR_KEY",
        "ITEM___EXPLOSIVES",
        "ITEM___GHOUL_BONE",
        "ITEM___GREEN_BOTTLE",
        "ITEM___ICED_TEA",
        "ITEM___IRON_KEY",
        "ITEM___JESTER_SPIRIT_INSIGNIA",
        "ITEM___KEYWORD___BREMERTON",
        "ITEM___KEYWORD___DOG",
        "ITEM___KEYWORD___JESTER_SPIRIT",
        "ITEM___KEYWORD___LAUGHLYN",
        "ITEM___KEYWORD___VOLCANO",
        "ITEM___LEAVES",
        "ITEM___LONESTAR_BADGE",
        "ITEM___MAGIC_FETISH",
        "ITEM___MATCHBOX",
        "ITEM___MEMO",
        "ITEM___MERMAID_SCALES",
        "ITEM___NUYEN___GLUTMAN",
        "ITEM___NUYEN___OCTOPUS",
        "ITEM___NUYEN___RAT_SHAMAN",
        "ITEM___NUYEN___VAMPIRE",
        "ITEM___PAPERWEIGHT",
        "ITEM___PASSWORD___DRAKE",
        "ITEM___POTION_BOTTLES",
        "ITEM___RIPPED_NOTE",
        "ITEM___SAFE_KEY",
        "ITEM___SCALPEL",
        "ITEM___SERPENT_SCALES",
        "ITEM___SHADES",
        "ITEM___STAKE",
        "ITEM___STROBE",
        "ITEM___TICKETS",
        "ITEM___TIME_BOMB",
        "ITEM___TORN_PAPER",
        # Magic
        "MAGIC___HEAL",
        "MAGIC___POWERBALL",
        "MAGIC___FREEZE",
        "MAGIC___SUMMON_SPIRIT",
        "MAGIC___INVISIBILITY",
        "MAGIC___ARMOR",
        # Skills
        "SKILL___LEADERSHIP",
        "SKILL___NEGOTIATION",
        # Cyberware
        "CYBERWARE___SKILL_SOFTWARE",
        "CYBERWARE___BOOSTED_REFLEXES",
        "CYBERWARE___DERMAL_PLATING",
        # Phone numbers
        "PHONE_NUMBER___SASSIE",
        "PHONE_NUMBER___GLUTMAN",
        "PHONE_NUMBER___TALIS",
        "PHONE_NUMBER___DR_M",
        "PHONE_NUMBER___DBLADE",
        # Events
        "EVENT___ICED_TEA_GIVEN",
        "EVENT___MORGUE_CABINETS_UNLOCKED",
        "EVENT___CHROME_COYOTE_HEALED",
        "EVENT___TICKETS_REDEEMED",
        "EVENT___GLUTMAN_AT_THE_CAGE",
        "EVENT___UNLIMITED_SLAP_PATCHES",
        "EVENT___CLEAN_WATER_COLLECTED",
        "EVENT___MAPLETHORPE_DOOR_OPENED",
        "EVENT___DATAJACK_REPAIRED",
        "EVENT___RUST_STILETTOS_DEFEATED",
        "EVENT___OCTOPUS_DEFEATED",
        "EVENT___POOL_OF_INK_COLLECTED",
        "EVENT___EARTH_CREATURE_AND_MAN",
        "EVENT___RAT_SHAMAN_GATE_OPENED",
        "EVENT___RAT_SHAMAN_DEFEATED",
        "EVENT___DARK_BLADE_GATE_OPENED",
        "EVENT___VAMPIRE_DEFEATED",
        "EVENT___ICE_DELIVERED_TO_DOCKS",
        "EVENT___TAXIBOAT_HIRED",
        "EVENT___TOXIC_WATER_COLLECTED",
        "EVENT___JESTER_SPIRIT_DEFEATED",
        "EVENT___JESTER_SPIRIT_PORTAL_OPEN",
        "EVENT___JESTER_SPIRIT_PORTAL_USED",
        "EVENT___DRAKE_TOWERS_2F_UNLOCKED",
        "EVENT___DRAKE_TOWERS_3F_UNLOCKED",
        "EVENT___DRAKE_TOWERS_4F_UNLOCKED",
        "EVENT___DRAKE_TOWERS_5F_UNLOCKED",
        "EVENT___LEVEL_6_NODE_DEACTIVATED",
        "EVENT___DRAKE_TOWERS_6F_UNLOCKED",
        "EVENT___DRAKE_TOWERS_ROOF_UNLOCKED",
        "EVENT___DRAKE_TOWERS_CLEARED",
        "EVENT___DRAKE_VOLCANO_S2_UNLOCKED",
        "EVENT___DRAKE_VOLCANO_S3_UNLOCKED",
        "EVENT___DRAKE_VOLCANO_S4_UNLOCKED",
        "EVENT___DRAKE_DEFEATED",
        "EVENT___PROFESSOR_PUSHKIN_RESCUED",
        "EVENT___ANEKI_BUILDING_2F_UNLOCKED",
        "EVENT___LEVEL_3_NODE_DEACTIVATED",
        "EVENT___ANEKI_BUILDING_3F_UNLOCKED",
        "EVENT___ANEKI_BUILDING_4F_UNLOCKED",
        "EVENT___ANEKI_BUILDING_5F_UNLOCKED",
        "EVENT___AI_COMPUTER_DESTROYED",
        "EVENT___GAME_COMPLETED",
        # NPCs
        "NPC___HAMFIST",
        "NPC___JANGADANCE",
        "NPC___LONELY_GAL",
        "NPC___DANCES_WITH_CLAMS",
        "NPC___ORIFICE",
        "NPC___NORBERT",
        "NPC___JETBOY",
        "NPC___ANDERS",
        "NPC___FROGTONGUE",
        "NPC___KITSUNE",
        "NPC___STEELFLIGHT",
        "NPC___SPATTER",
        "NPC___AKIMI",
    ],
)

class Category(Flag):
    CONSTANT = auto()
    PHYSICAL = auto()
    KEY_ITEM = auto()
    EARLY = auto()
    WEAPON = auto()
    ARMOR = auto()
    TALISMAN = auto()
    ITEM = auto()
    NPC = auto()
    PHYSICAL_KEY_ITEM = PHYSICAL | KEY_ITEM
    EARLY_WEAPON = EARLY | WEAPON
    EARLY_ARMOR = EARLY | ARMOR
    WEAPON_OR_ARMOR = WEAPON | ARMOR
    PHYSICAL_ITEM = PHYSICAL | ITEM

class Entity:
    def __init__(self, category, description, entityAddress, progression):
        self.category = category
        self.description = description
        self.entityAddress = entityAddress
        self.progression = progression

class Location:
    def __init__(self, region, category, description, vanilla, requires, address, hidden):
        self.region = region
        self.category = category
        self.description = description
        self.vanilla = vanilla
        self.requires = requires
        self.address = address
        self.hidden = hidden
        self.current = vanilla

class Door:
    def __init__(self, destination, requires):
        self.destination = destination
        self.requires = requires

class Region:
    def __init__(self, name):
        self.name = name
        self.locations = []
        self.doors = []

regions = {}

# ------------------------------------------------------------------------
# Root
# ------------------------------------------------------------------------
regionName = "Root"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Default Keywords",
        vanilla = Entity(Category.CONSTANT, "Default Keywords", None, [
            (Progress.KEYWORD___HITMEN,        []),
            (Progress.KEYWORD___FIREARMS,      []),
            (Progress.KEYWORD___HEAL,          []),
            (Progress.KEYWORD___SHADOWRUNNERS, []),
            (Progress.KEYWORD___HIRING,        []),
        ]),
        requires = [],
        address = None,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Matchbox",
        vanilla = Entity(Category.CONSTANT, "Matchbox", 0x6B8FF, [
            (Progress.ITEM___MATCHBOX, []),
        ]),
        requires = [],
        address = 0xC84A1,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Learn 'Dog'",
        vanilla = Entity(Category.CONSTANT, "Learn 'Dog'", None, [
            (Progress.KEYWORD___DOG, [Progress.ITEM___KEYWORD___DOG]),
        ]),
        requires = [],
        address = None,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Examine Ripped Note",
        vanilla = Entity(Category.CONSTANT, "Examine Ripped Note", None, [
            (Progress.PHONE_NUMBER___SASSIE, [Progress.ITEM___RIPPED_NOTE]),
        ]),
        requires = [],
        address = None,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Learn 'Magic Fetish'",
        vanilla = Entity(Category.CONSTANT, "Learn 'Magic Fetish'", None, [
            (Progress.KEYWORD___MAGIC_FETISH, [Progress.ITEM___MAGIC_FETISH]),
        ]),
        requires = [],
        address = None,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Learn 'Jester Spirit'",
        vanilla = Entity(Category.CONSTANT, "Learn 'Jester Spirit'", None, [
            (Progress.KEYWORD___JESTER_SPIRIT, [Progress.ITEM___KEYWORD___JESTER_SPIRIT]),
        ]),
        requires = [],
        address = None,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Learn 'Bremerton'",
        vanilla = Entity(Category.CONSTANT, "Learn 'Bremerton'", None, [
            (Progress.KEYWORD___BREMERTON, [Progress.ITEM___KEYWORD___BREMERTON]),
        ]),
        requires = [],
        address = None,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Learn 'Laughlyn'",
        vanilla = Entity(Category.CONSTANT, "Learn 'Laughlyn'", None, [
            (Progress.KEYWORD___LAUGHLYN, [Progress.ITEM___KEYWORD___LAUGHLYN]),
        ]),
        requires = [],
        address = None,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Assemble Time Bomb",
        vanilla = Entity(Category.CONSTANT, "Time Bomb", 0x6B261, [
            (Progress.ITEM___TIME_BOMB, [
                Progress.ITEM___DETONATOR,
                Progress.ITEM___EXPLOSIVES,
            ]),
        ]),
        requires = [],
        address = 0xCB953,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Learn 'Volcano'",
        vanilla = Entity(Category.CONSTANT, "Learn 'Volcano'", None, [
            (Progress.KEYWORD___VOLCANO, [Progress.ITEM___KEYWORD___VOLCANO]),
        ]),
        requires = [],
        address = None,
        hidden = False,
    ),
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    # TODO: Will probably have to rewrite the item-merging behaviour
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Merge DF_DR Fragments",
        vanilla = Entity(Category.CONSTANT, "DF_DR-MATRIX", 0x6C5AF, [
            (Progress.ITEM___DF_DR_MATRIX, []),
        ]),
        requires = [
            Progress.ITEM___DF_DR_1_4,
            Progress.ITEM___DF_DR_2_4,
            Progress.ITEM___DF_DR_3_4,
            Progress.ITEM___DF_DR_4_4,
        ],
        address = 0xCB935,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Game Completed",
        vanilla = Entity(Category.CONSTANT, "Game Completed", None, [
            (Progress.EVENT___GAME_COMPLETED, [
                Progress.EVENT___PROFESSOR_PUSHKIN_RESCUED,
                Progress.EVENT___AI_COMPUTER_DESTROYED,
            ]),
        ]),
        requires = [],
        address = None,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - Morgue (main room)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Morgue (main room)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Morgue (main room)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Mortician (Larry)",
        vanilla = Entity(Category.CONSTANT, "Mortician (Larry)", 0x6B82D, [
            (Progress.EVENT___MORGUE_CABINETS_UNLOCKED, [
                Progress.ITEM___SHADES,
                Progress.ITEM___LONESTAR_BADGE,
                Progress.KEYWORD___GRINDER,
            ]),
        ]),
        requires = [],
        address = 0xC846B,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Mortician (Sam)",
        vanilla = Entity(Category.CONSTANT, "Mortician (Sam)", 0x6B81F, []),
        requires = [],
        address = 0xC8471,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Torn Paper",
        vanilla = Entity(Category.ITEM, "Torn Paper", 0x6B25A, [
            (Progress.ITEM___TORN_PAPER, []),
        ]),
        requires = [],
        address = 0xC848F,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Scalpel",
        vanilla = Entity(Category.KEY_ITEM, "Scalpel", 0x6B555, [
            (Progress.ITEM___SCALPEL, []),
        ]),
        requires = [],
        address = 0xC8483,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Slap Patch",
        vanilla = Entity(Category.CONSTANT, "Slap Patch", 0x6B3CD, [
            # In vanilla, this is a one-time pickup.
            (Progress.EVENT___UNLIMITED_SLAP_PATCHES, []),
        ]),
        requires = [],
        address = 0xC8495,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Tickets",
        vanilla = Entity(Category.ITEM, "Tickets", 0x6B268, [
            (Progress.ITEM___TICKETS, []),
        ]),
        requires = [Progress.EVENT___MORGUE_CABINETS_UNLOCKED],
        address = 0xC8489,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Credstick",
        vanilla = Entity(Category.KEY_ITEM, "Credstick", 0x6C6C0, [
            (Progress.ITEM___CREDSTICK, []),
        ]),
        requires = [Progress.EVENT___MORGUE_CABINETS_UNLOCKED],
        address = 0xC849B,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - Morgue (hallway)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Morgue (hallway)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Morgue (hallway)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - Morgue (main room)", []),
    Door("Tenth Street - Center", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Center
# ------------------------------------------------------------------------
regionName = "Tenth Street - Center"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    ## In vanilla, this is the "You can't be alive!" guy, who does
    ## not appear in the randomizer.
    #Location(
    #    region = thisRegion,
    #    category = Category.CONSTANT,
    #    description = "Decker",
    #    vanilla = Entity(Category.CONSTANT, "Decker", 0x6C618, [
    #        (Progress.KEYWORD___HITMEN, []),
    #    ]),
    #    requires = [],
    #    address = 0xC816F,
    #    hidden = False,
    #),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Dog Collar",
        vanilla = Entity(Category.KEY_ITEM, "Dog Collar", 0x6C577, [
            (Progress.ITEM___DOG_COLLAR, []),
        ]),
        requires = [],
        address = 0xC817B,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A Busy Man",
        vanilla = Entity(Category.CONSTANT, "A Busy Man", 0x6CC0E, []),
        requires = [],
        address = 0xC8133,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A Busy Man",
        vanilla = Entity(Category.CONSTANT, "A Busy Man", 0x6CBEB, []),
        requires = [],
        address = 0xC8139,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A Busy Man",
        vanilla = Entity(Category.CONSTANT, "A Busy Man", 0x6CC23, []),
        requires = [],
        address = 0xC813F,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A Busy Man",
        vanilla = Entity(Category.CONSTANT, "A Busy Man", 0x6CC54, []),
        requires = [],
        address = 0xC8163,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A Busy Man",
        vanilla = Entity(Category.CONSTANT, "A Busy Man", 0x6CC38, []),
        requires = [],
        address = 0xC8169,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Water Fountain",
        vanilla = Entity(Category.CONSTANT, "Water Fountain", 0x6B15E, [
            (Progress.EVENT___CLEAN_WATER_COLLECTED, [Progress.ITEM___POTION_BOTTLES]),
        ]),
        requires = [],
        address = 0xC814B,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - Morgue (hallway)", []),
    Door("Tenth Street - South", []),
    Door("Tenth Street - East", []),
    Door("Tenth Street - West", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - South
# ------------------------------------------------------------------------
regionName = "Tenth Street - South"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - Center", []),
    Door("Tenth Street - Dead Man's Building (hallway)", []),
    Door("Tenth Street - East", []),
    # In vanilla, you can't enter the Tenth Street monorail station
    # until after Glutman hides you in the caryards.
    Door("Tenth Street - Monorail Platform to Oldtown", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Dead Man's Building (hallway)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Dead Man's Building (hallway)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - South", []),
    Door("Tenth Street - Dead Man's Building (first room)", []),
    Door("Tenth Street - Dead Man's Building (second room)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Dead Man's Building (first room)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Dead Man's Building (first room)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Memo",
        vanilla = Entity(Category.ITEM, "Memo", 0x6B8DC, [
            (Progress.ITEM___MEMO, []),
        ]),
        requires = [],
        address = 0xC93ED,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Door Key",
        vanilla = Entity(Category.KEY_ITEM, "Door Key", 0x6C4B3, [
            (Progress.ITEM___DOOR_KEY, []),
        ]),
        requires = [],
        address = 0xC93F3,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - Dead Man's Building (hallway)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Dead Man's Building (second room)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Dead Man's Building (second room)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - Dead Man's Building (hallway)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - East
# ------------------------------------------------------------------------
regionName = "Tenth Street - East"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - South", []),
    Door("Tenth Street - Jake's Building (hallway)", []),
    Door("Tenth Street - Center", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Jake's Building (hallway)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Jake's Building (hallway)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - East", []),
    Door("Tenth Street - Jake's Building (first room: Apt 7+8)", []),
    Door("Tenth Street - Jake's Building (second room: Apt 6)", [Progress.ITEM___DOOR_KEY]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Jake's Building (first room: Apt 7+8)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Jake's Building (first room: Apt 7+8)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - Jake's Building (hallway)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Jake's Building (second room: Apt 6)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Jake's Building (second room: Apt 6)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Shades",
        vanilla = Entity(Category.ITEM, "Shades", 0x6B3F7, [
            (Progress.ITEM___SHADES, []),
        ]),
        requires = [],
        address = 0xC937D,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Ripped Note",
        vanilla = Entity(Category.ITEM, "Ripped Note", 0x6B674, [
            (Progress.ITEM___RIPPED_NOTE, []),
        ]),
        requires = [],
        address = 0xC9389,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - Jake's Building (hallway)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - West
# ------------------------------------------------------------------------
regionName = "Tenth Street - West"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - Center", []),
    Door("Tenth Street - Alley", []),
    Door("Tenth Street - Glutman's Building (hallway)", []),
    Door("Tenth Street - Business Man's Building (hallway)", []),
    Door("Tenth Street - Grim Reaper Club", []),
    Door("Tenth Street - North", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Alley
# ------------------------------------------------------------------------
regionName = "Tenth Street - Alley"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.EARLY_WEAPON,
        description = "Beretta Pistol",
        vanilla = Entity(Category.EARLY_WEAPON, "Beretta Pistol", 0x6C983, [
            (Progress.WEAPON___BERETTA_PISTOL, []),
        ]),
        requires = [],
        address = 0xC8871,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.EARLY_ARMOR,
        description = "Leather Jacket",
        vanilla = Entity(Category.EARLY_ARMOR, "Leather Jacket", 0x6BB52, [
            (Progress.ARMOR___LEATHER_JACKET, []),
        ]),
        requires = [],
        address = 0xC8877,
        hidden = True,
    ),
    # In vanilla, this is "hmmm...." (Dog in alley)
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Keyword: Dog",
        vanilla = Entity(Category.PHYSICAL_KEY_ITEM, "Keyword: Dog", 0x6BC16, [
            (Progress.ITEM___KEYWORD___DOG, []),
        ]),
        requires = [],
        address = 0xC8859,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - West", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Glutman's Building (hallway)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Glutman's Building (hallway)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - West", []),
    Door("Tenth Street - Glutman's Building (first room)", []),
    Door("Tenth Street - Glutman's Building (second room)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Glutman's Building (first room)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Glutman's Building (first room)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Paperweight",
        vanilla = Entity(Category.TALISMAN, "Paperweight", 0x6B7A8, [
            (Progress.ITEM___PAPERWEIGHT, []),
        ]),
        requires = [],
        address = 0xC921B,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - Glutman's Building (hallway)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Glutman's Building (second room)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Glutman's Building (second room)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Secretary",
        vanilla = Entity(Category.CONSTANT, "Secretary", 0x6B41A, [
            (Progress.KEYWORD___THE_CAGE,          [Progress.KEYWORD___GLUTMAN]),
            (Progress.EVENT___GLUTMAN_AT_THE_CAGE, [Progress.KEYWORD___GLUTMAN]),
        ]),
        requires = [],
        address = 0xC9319,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Cyberdeck",
        vanilla = Entity(Category.KEY_ITEM, "Cyberdeck", 0x6C634, [
            (Progress.ITEM___CYBERDECK, []),
        ]),
        requires = [],
        address = 0xC9325,
        hidden = False,
    ),
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "DF_BADNEWS", 0x6C5D9, [
            (Progress.ITEM___DF_BADNEWS, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xD2225,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - Glutman's Building (hallway)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Business Man's Building (hallway)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Business Man's Building (hallway)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - West", []),
    Door("Tenth Street - Business Man's Building (first room)", []),
    Door("Tenth Street - Business Man's Building (second room)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Business Man's Building (first room)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Business Man's Building (first room)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - Business Man's Building (hallway)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Business Man's Building (second room)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Business Man's Building (second room)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Business Man",
        vanilla = Entity(Category.CONSTANT, "Business Man", 0x6C8CD, [
            (Progress.KEYWORD___SHADOWRUNNERS, []),
            (Progress.KEYWORD___HIRING,        [Progress.KEYWORD___SHADOWRUNNERS]),
            (Progress.KEYWORD___NEGOTIATION,   [Progress.KEYWORD___HIRING]),
            (Progress.ITEM___LONESTAR_BADGE,   [Progress.KEYWORD___LONE_STAR]),
        ]),
        requires = [],
        address = 0xD2861,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - Business Man's Building (hallway)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Grim Reaper Club
# ------------------------------------------------------------------------
regionName = "Tenth Street - Grim Reaper Club"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A Busy Man",
        vanilla = Entity(Category.CONSTANT, "A Busy Man", 0x6CBF2, [
            (Progress.KEYWORD___HEAL,       []),
            (Progress.KEYWORD___STREET_DOC, [Progress.KEYWORD___HEAL]),
        ]),
        requires = [],
        address = 0xC87A7,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Club Manager",
        vanilla = Entity(Category.CONSTANT, "Club Manager", 0x6C8A3, [
            (Progress.KEYWORD___SHADOWRUNNERS, []),
            (Progress.KEYWORD___DECKER,        [Progress.KEYWORD___SHADOWRUNNERS]),
            (Progress.KEYWORD___HIRING,        [Progress.KEYWORD___SHADOWRUNNERS]),
            (Progress.KEYWORD___DATAJACK,      [Progress.KEYWORD___DECKER]),
        ]),
        requires = [],
        address = 0xC879B,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Iced Tea",
        vanilla = Entity(Category.ITEM, "Iced Tea", 0x6BC08, [
            (Progress.ITEM___ICED_TEA, []),
        ]),
        requires = [],
        address = 0xC87BF,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Club patron...",
        vanilla = Entity(Category.CONSTANT, "Club patron...", 0x6C88E, [
            (Progress.EVENT___ICED_TEA_GIVEN, [Progress.ITEM___ICED_TEA]),
            (Progress.KEYWORD___TICKETS,      [Progress.EVENT___ICED_TEA_GIVEN]),
            (Progress.KEYWORD___MARIA,        [Progress.EVENT___ICED_TEA_GIVEN, Progress.KEYWORD___TICKETS]),
            (Progress.KEYWORD___GRINDER,      [Progress.EVENT___ICED_TEA_GIVEN, Progress.KEYWORD___TICKETS]),
            (Progress.KEYWORD___LONE_STAR,    [Progress.EVENT___ICED_TEA_GIVEN, Progress.KEYWORD___GRINDER]),
        ]),
        requires = [],
        address = 0xC87AD,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.NPC,
        description = "Orc (Hamfist)",
        vanilla = Entity(Category.NPC, "Orc (Hamfist)", 0x6B7D2, [
            (Progress.NPC___HAMFIST, []),
        ]),
        requires = [],
        address = 0xC87CB,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.NPC,
        description = "Jamaican (Jangadance)",
        vanilla = Entity(Category.NPC, "Jamaican (Jangadance)", 0x6BBD0, [
            (Progress.NPC___JANGADANCE, []),
        ]),
        requires = [],
        address = 0xC87A1,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - West", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - North
# ------------------------------------------------------------------------
regionName = "Tenth Street - North"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Loyal citizen",
        vanilla = Entity(Category.CONSTANT, "Loyal citizen", 0x6BB2F, [
            (Progress.KEYWORD___THE_CAGE, [Progress.KEYWORD___MARIA]),
        ]),
        requires = [],
        address = 0xC8329,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Heavy Dude",
        vanilla = Entity(Category.CONSTANT, "Heavy Dude", 0x6BF11, [
            (Progress.KEYWORD___LONE_STAR, []),
        ]),
        requires = [],
        address = 0xC832F,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - West", []),
    Door("Tenth Street - Graveyard", []),
    Door("Tenth Street - The Cage // Lobby", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Graveyard
# ------------------------------------------------------------------------
regionName = "Tenth Street - Graveyard"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Ghoul Bone",
        vanilla = Entity(Category.TALISMAN, "Ghoul Bone", 0x6C172, [
            (Progress.ITEM___GHOUL_BONE, []),
        ]),
        requires = [Progress.EVENT___CHROME_COYOTE_HEALED],
        address = 0xC85D1,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - North", []),
    Door("Tenth Street - Graveyard (crypt #1 interior)", [Progress.ITEM___SCALPEL]),
    Door("Tenth Street - Graveyard (crypt #2 interior)", [Progress.ITEM___SCALPEL]),
    Door("Tenth Street - Graveyard (crypt #3 interior)", [Progress.ITEM___SCALPEL]),
    Door("Tenth Street - Graveyard (crypt #4 interior)", [Progress.ITEM___SCALPEL]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Graveyard (crypt #1 interior)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Graveyard (crypt #1 interior)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Indian Shaman",
        vanilla = Entity(Category.CONSTANT, "Indian Shaman", 0x6BBFA, [
            (Progress.EVENT___CHROME_COYOTE_HEALED, [Progress.EVENT___UNLIMITED_SLAP_PATCHES]),
            # In vanilla, you can get the following progressions by
            # talking to Chrome Coyote after you heal him:
            # - Progress.KEYWORD___SHAMAN
            # - Progress.KEYWORD___MAGIC_FETISH
            # - Progress.ITEM___MAGIC_FETISH
        ]),
        requires = [],
        address = 0xC8933,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Magic Fetish",
        vanilla = Entity(Category.PHYSICAL_KEY_ITEM, "Magic Fetish", 0x6B9CA, [
            (Progress.ITEM___MAGIC_FETISH, []),
        ]),
        requires = [Progress.EVENT___CHROME_COYOTE_HEALED],
        address = 0xC8951,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - Graveyard", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Graveyard (crypt #2 interior)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Graveyard (crypt #2 interior)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - Graveyard", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Graveyard (crypt #3 interior)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Graveyard (crypt #3 interior)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - Graveyard", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Graveyard (crypt #4 interior)
# ------------------------------------------------------------------------
regionName = "Tenth Street - Graveyard (crypt #4 interior)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Tenth Street - Graveyard", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - The Cage // Lobby
# ------------------------------------------------------------------------
regionName = "Tenth Street - The Cage // Lobby"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Heavy Bouncer",
        vanilla = Entity(Category.CONSTANT, "Heavy Bouncer", 0x6BFFF, [
            (Progress.KEYWORD___TICKETS,        []),
            (Progress.EVENT___TICKETS_REDEEMED, [Progress.ITEM___TICKETS]),
        ]),
        requires = [],
        address = 0xC8685,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - North", []),
    Door("Video Phone", [Progress.ITEM___CREDSTICK]),
    Door("Tenth Street - The Cage // Interior", [Progress.EVENT___TICKETS_REDEEMED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Video Phone
# ------------------------------------------------------------------------
regionName = "Video Phone"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Sassie 702-826",
        vanilla = Entity(Category.CONSTANT, "Sassie 702-826", None, [
            (Progress.KEYWORD___CALLS,        []),
            (Progress.KEYWORD___GLUTMAN,      [Progress.KEYWORD___CALLS]),
            (Progress.PHONE_NUMBER___GLUTMAN, [Progress.KEYWORD___CALLS]),
        ]),
        requires = [Progress.PHONE_NUMBER___SASSIE],
        address = None,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Glutman 934-782",
        vanilla = Entity(Category.CONSTANT, "Glutman 934-782", None, [
            (Progress.KEYWORD___THE_CAGE,          [Progress.KEYWORD___GLUTMAN]),
            (Progress.EVENT___GLUTMAN_AT_THE_CAGE, [Progress.KEYWORD___GLUTMAN]),
        ]),
        requires = [Progress.PHONE_NUMBER___GLUTMAN],
        address = None,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Talis. 416-822",
        vanilla = Entity(Category.CONSTANT, "Talis. 416-822", None, [
            (Progress.PHONE_NUMBER___DBLADE, [Progress.KEYWORD___DARK_BLADE]),
        ]),
        requires = [Progress.PHONE_NUMBER___TALIS],
        address = None,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Dr M. 261-688",
        vanilla = Entity(Category.CONSTANT, "Dr M. 261-688", None, []),
        requires = [Progress.PHONE_NUMBER___DR_M],
        address = None,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "DBlade 826-661",
        vanilla = Entity(Category.CONSTANT, "DBlade 826-661", None, [
            (Progress.EVENT___DARK_BLADE_GATE_OPENED, [Progress.KEYWORD___MAGIC_FETISH]),
        ]),
        requires = [Progress.PHONE_NUMBER___DBLADE],
        address = None,
        hidden = False,
    ),
    # TODO: Other phone conversations: Drake, Akimi
    # TODO: Looks like you learn Drake's phone number from the script
    #   for the computer that gives you DF_DR-VOLCANO. Should probably
    #   be revised so you learn it by examining DF_DR-VOLCANO.
    #   Ditto for Akimi's phone number and DF_DS-AKIMI.
    # TODO: Alternately, revise the Video Phone script so having those
    #   two items gives you the respective phone numbers.
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - The Cage // Interior
# ------------------------------------------------------------------------
regionName = "Tenth Street - The Cage // Interior"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Heavy Dude",
        vanilla = Entity(Category.CONSTANT, "Heavy Dude", 0x6BE77, [
            (Progress.KEYWORD___GHOULS, []),
        ]),
        requires = [],
        address = 0xC8697,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.NPC,
        description = "Lonely Gal",
        vanilla = Entity(Category.NPC, "Lonely Gal", 0x6BB3D, [
            (Progress.NPC___LONELY_GAL, []),
        ]),
        requires = [],
        address = 0xC86D3,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Busy Man",
        vanilla = Entity(Category.CONSTANT, "Busy Man", 0x6C8C6, []),
        requires = [],
        address = 0xC86CD,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Club Manager",
        vanilla = Entity(Category.CONSTANT, "Club Manager", 0x6C89C, [
            (Progress.KEYWORD___FIREARMS, [Progress.KEYWORD___SHADOWRUNNERS]),
        ]),
        requires = [],
        address = 0xC868B,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A Busy Man",
        vanilla = Entity(Category.CONSTANT, "A Busy Man", 0x6CC5B, []),
        requires = [],
        address = 0xC86C1,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A waitress",
        vanilla = Entity(Category.CONSTANT, "A waitress", 0x6CBE4, []),
        requires = [],
        address = 0xC8691,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Well dressed...",
        vanilla = Entity(Category.CONSTANT, "Well dressed...", 0x6B150, []),
        requires = [],
        address = 0xC86BB,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Dancing Hippie!",
        vanilla = Entity(Category.CONSTANT, "Dancing Hippie!", 0x6C61F, []),
        requires = [],
        address = 0xC86C7,
        hidden = False,
    ),
    # In vanilla, this is "Shady character..." (Glutman)
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Nuyen: Glutman",
        vanilla = Entity(Category.PHYSICAL_ITEM, "Nuyen: Glutman", 0x6B3F0, [
            # In vanilla, Glutman would hide you in the caryards here.
            (Progress.ITEM___NUYEN___GLUTMAN, []),
        ]),
        requires = [Progress.EVENT___GLUTMAN_AT_THE_CAGE],
        address = 0xC86D9,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - The Cage // Lobby", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Caryards - North
# ------------------------------------------------------------------------
regionName = "Caryards - North"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Caryards - Center", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Caryards - Center
# ------------------------------------------------------------------------
regionName = "Caryards - Center"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Gang member",
        vanilla = Entity(Category.CONSTANT, "Gang member", 0x6C29F, [
            (Progress.KEYWORD___CARYARDS, []),
            (Progress.KEYWORD___KING,     []),
        ]),
        requires = [],
        address = 0xC946F,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Street kid",
        vanilla = Entity(Category.CONSTANT, "Street kid", 0x6B325, [
            (Progress.KEYWORD___DECKER,     []),
            (Progress.KEYWORD___THE_MATRIX, []),
            (Progress.KEYWORD___DATAJACK,   [Progress.KEYWORD___DECKER]),
        ]),
        requires = [],
        address = 0xC9469,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Heavy Dude",
        vanilla = Entity(Category.CONSTANT, "Heavy Dude", 0x6BD43, [
            (Progress.KEYWORD___DRAKE,    []),
            (Progress.KEYWORD___CARYARDS, []),
        ]),
        requires = [],
        address = 0xC9457,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Street dweller",
        vanilla = Entity(Category.CONSTANT, "Street dweller", 0x6B341, []),
        requires = [],
        address = 0xC945D,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Street scum",
        vanilla = Entity(Category.CONSTANT, "Street scum", 0x6B2E6, [
            (Progress.KEYWORD___KING,  []),
            (Progress.KEYWORD___NUYEN, [Progress.KEYWORD___KING]),
        ]),
        requires = [],
        address = 0xC9463,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Little boy",
        vanilla = Entity(Category.CONSTANT, "Little boy", 0x6BB44, [
            (Progress.EVENT___UNLIMITED_SLAP_PATCHES, [Progress.KEYWORD___HEAL]),
        ]),
        requires = [],
        address = 0xC947B,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "The King",
        vanilla = Entity(Category.CONSTANT, "The King", 0x6B26F, []),
        requires = [],
        address = 0xC9475,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Caryards - North", []),
    Door("Caryards - Arena", []),
    Door("Caryards - South", []),
    Door("Oldtown - South", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Caryards - Arena
# ------------------------------------------------------------------------
regionName = "Caryards - Arena"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Arena owner",
        vanilla = Entity(Category.CONSTANT, "Arena owner", 0x6CB97, [
            (Progress.SKILL___NEGOTIATION, [Progress.KEYWORD___NEGOTIATION]),
        ]),
        requires = [],
        address = 0xD2541,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Caryards - Center", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Caryards - South
# ------------------------------------------------------------------------
regionName = "Caryards - South"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Caryards - Center", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Oldtown - South
# ------------------------------------------------------------------------
regionName = "Oldtown - South"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Street kid",
        vanilla = Entity(Category.CONSTANT, "Street kid", 0x6B333, []),
        requires = [],
        address = 0xC8D29,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Street Scum",
        vanilla = Entity(Category.CONSTANT, "Street Scum", 0x6B2ED, []),
        requires = [],
        address = 0xC8D2F,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Caryards - Center", []),
    Door("Oldtown - Sputnik Club", []),
    Door("Oldtown - Center", []),
    Door("Oldtown - Monorail Platform to Tenth Street", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Oldtown - Sputnik Club
# ------------------------------------------------------------------------
regionName = "Oldtown - Sputnik Club"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.NPC,
        description = "Magic user (Dances with Clams)",
        vanilla = Entity(Category.NPC, "Magic user (Dances with Clams)", 0x6B9C3, [
            (Progress.NPC___DANCES_WITH_CLAMS, []),
        ]),
        requires = [],
        address = 0xC977D,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Customer",
        vanilla = Entity(Category.CONSTANT, "Customer", 0x6C65E, [
            (Progress.KEYWORD___STREET_DOC, []),
        ]),
        requires = [],
        address = 0xC9753,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Customer",
        vanilla = Entity(Category.CONSTANT, "Customer", 0x6C657, [
            (Progress.KEYWORD___DECKER, []),
        ]),
        requires = [],
        address = 0xC9759,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Club Manager",
        vanilla = Entity(Category.CONSTANT, "Club Manager", 0x6C8AA, []),
        requires = [],
        address = 0xC9765,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Orc",
        vanilla = Entity(Category.CONSTANT, "Orc", 0x6B7C4, []),
        requires = [],
        address = 0xC975F,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Happy Customer",
        vanilla = Entity(Category.CONSTANT, "Happy Customer", 0x6C006, [
            (Progress.KEYWORD___HIRING, [Progress.KEYWORD___SHADOWRUNNERS]),
        ]),
        requires = [],
        address = 0xC976B,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.NPC,
        description = "Large orc (Orifice)",
        vanilla = Entity(Category.NPC, "Large orc (Orifice)", 0x6BB67, [
            (Progress.NPC___ORIFICE, []),
        ]),
        requires = [],
        address = 0xC9771,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Oldtown - South", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Oldtown - Center
# ------------------------------------------------------------------------
regionName = "Oldtown - Center"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Gang member",
        vanilla = Entity(Category.CONSTANT, "Gang member", 0x6C267, []),
        requires = [],
        address = 0xD1C81,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Gang member",
        vanilla = Entity(Category.CONSTANT, "Gang member", 0x6C291, []),
        requires = [],
        address = 0xD1C7B,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Oldtown - South", []),
    Door("Oldtown - North", []),
    Door("Oldtown - Ed's Alley", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Oldtown - North
# ------------------------------------------------------------------------
regionName = "Oldtown - North"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Person",
        vanilla = Entity(Category.CONSTANT, "Person", 0x6B6C1, []),
        requires = [],
        address = 0xC957F,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Person",
        vanilla = Entity(Category.CONSTANT, "Person", 0x6B6C8, []),
        requires = [],
        address = 0xC9591,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Oldtown - Center", []),
    Door("Oldtown - Magic Shop", []),
    Door("Oldtown - Gun Shop", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Oldtown - Magic Shop
# ------------------------------------------------------------------------
regionName = "Oldtown - Magic Shop"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Indian Shaman",
        vanilla = Entity(Category.CONSTANT, "Indian Shaman", 0x6BC01, [
            (Progress.KEYWORD___TALISMANS,   []),
            (Progress.KEYWORD___SHAMAN,      [Progress.KEYWORD___TALISMANS]),
            (Progress.PHONE_NUMBER___TALIS,  [Progress.KEYWORD___TALISMANS]),
            (Progress.PHONE_NUMBER___DBLADE, [Progress.KEYWORD___DARK_BLADE]),
        ]),
        requires = [],
        address = 0xC96E3,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.TALISMAN,
        description = "Potion Bottles",
        vanilla = Entity(Category.TALISMAN, "Potion Bottles", 0x6B689, [
            (Progress.ITEM___POTION_BOTTLES, []),
        ]),
        requires = [],
        address = 0xC96F5,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.TALISMAN,
        description = "Black Bottle",
        vanilla = Entity(Category.TALISMAN, "Black Bottle", 0x6C975, [
            (Progress.ITEM___BLACK_BOTTLE, []),
        ]),
        requires = [],
        address = 0xC96FB,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.TALISMAN,
        description = "Stake",
        vanilla = Entity(Category.KEY_ITEM, "Stake", 0x6B35D, [
            (Progress.ITEM___STAKE, []),
        ]),
        requires = [],
        address = 0xC9707,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Oldtown - North", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Oldtown - Gun Shop
# ------------------------------------------------------------------------
regionName = "Oldtown - Gun Shop"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Dwarf",
        vanilla = Entity(Category.CONSTANT, "Dwarf", 0x6C490, []),
        requires = [],
        address = 0xC9625,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "She's choosing...",
        vanilla = Entity(Category.CONSTANT, "She's choosing...", 0x6B3E9, []),
        requires = [],
        address = 0xC962B,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "Colt L36 Pistol",
        vanilla = Entity(Category.EARLY_WEAPON, "Colt L36 Pistol", 0x6C7F4, [
            (Progress.WEAPON___COLT_L36_PISTOL, []),
        ]),
        requires = [],
        address = 0xC9649,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "Viper H. Pistol ($4,000)",
        vanilla = Entity(Category.EARLY_WEAPON, "Viper H. Pistol ($4,000)", 0x6B181, [
            (Progress.WEAPON___VIPER_H_PISTOL___4000, []),
        ]),
        requires = [],
        address = 0xC964F,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "Mesh Jacket ($5,000)",
        vanilla = Entity(Category.EARLY_ARMOR, "Mesh Jacket ($5,000)", 0x6B881, [
            (Progress.ARMOR___MESH_JACKET___5000, []),
        ]),
        requires = [],
        address = 0xC9655,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "T-250 Shotgun ($15,000)",
        vanilla = Entity(Category.WEAPON, "T-250 Shotgun ($15,000)", 0x6B292, [
            (Progress.WEAPON___T_250_SHOTGUN___15000, []),
        ]),
        requires = [],
        address = 0xC965B,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "Fichetti L. Pistol",
        vanilla = Entity(Category.EARLY_WEAPON, "Fichetti L. Pistol", 0x6C324, [
            (Progress.WEAPON___FICHETTI_L_PISTOL, []),
        ]),
        requires = [],
        address = 0xC966D,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "Warhawk H. Pistol",
        vanilla = Entity(Category.EARLY_WEAPON, "Warhawk H. Pistol", 0x6B16C, [
            (Progress.WEAPON___WARHAWK_H_PISTOL, []),
        ]),
        requires = [],
        address = 0xC9673,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Oldtown - North", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Oldtown - Ed's Alley
# ------------------------------------------------------------------------
regionName = "Oldtown - Ed's Alley"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Oldtown - Center", []),
    Door("Oldtown - Ed's Office", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Oldtown - Ed's Office
# ------------------------------------------------------------------------
regionName = "Oldtown - Ed's Office"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Street Doc",
        vanilla = Entity(Category.CONSTANT, "Street Doc", 0x6B348, [
            (Progress.KEYWORD___EXAMINATION, [Progress.KEYWORD___DATAJACK]),
            (Progress.KEYWORD___CORTEX_BOMB, [Progress.KEYWORD___EXAMINATION]),
        ]),
        requires = [],
        address = 0xD2017,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Oldtown - Ed's Alley", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Oldtown - Monorail Platform to Tenth Street
# ------------------------------------------------------------------------
regionName = "Oldtown - Monorail Platform to Tenth Street"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Oldtown - South", []),
    Door("Tenth Street - Monorail Platform to Oldtown", []),
    Door("Oldtown - Monorail Platform to Downtown", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Tenth Street - Monorail Platform to Oldtown
# ------------------------------------------------------------------------
regionName = "Tenth Street - Monorail Platform to Oldtown"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Oldtown - Monorail Platform to Tenth Street", []),
    Door("Tenth Street - South", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Oldtown - Monorail Platform to Downtown
# ------------------------------------------------------------------------
regionName = "Oldtown - Monorail Platform to Downtown"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Oldtown - Monorail Platform to Tenth Street", []),
    Door("Downtown - Monorail Platform to Oldtown", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Monorail Platform to Oldtown
# ------------------------------------------------------------------------
regionName = "Downtown - Monorail Platform to Oldtown"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Street kid",
        vanilla = Entity(Category.CONSTANT, "Street kid", 0x6B32C, []),
        requires = [],
        address = 0xCA6F9,
        hidden = False,
    ),
    # Akimi's location is intentionally constant.
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Akimi",
        vanilla = Entity(Category.CONSTANT, "Akimi", 0x6CBA5, [
            (Progress.NPC___AKIMI, []),
        ]),
        requires = [],
        address = 0xCA717,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Oldtown - Monorail Platform to Downtown", []),
    Door("Downtown - Monorail Station", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Monorail Station
# ------------------------------------------------------------------------
regionName = "Downtown - Monorail Station"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Iron Key",
        vanilla = Entity(Category.KEY_ITEM, "Iron Key", 0x6BBF3, [
            (Progress.ITEM___IRON_KEY, []),
        ]),
        requires = [],
        address = 0xCA7B9,
        hidden = True,
    ),
    ## In vanilla, this is the dog at Daley Station, who does not
    ## appear in the randomizer.
    #Location(
    #    region = thisRegion,
    #    category = Category.CONSTANT,
    #    description = "Doggie",
    #    vanilla = Entity(Category.CONSTANT, "Doggie", 0x6C554, []),
    #    requires = [],
    #    address = 0xCA7D1,
    #    hidden = False,
    #),
])
thisRegion.doors.extend([
    Door("Downtown - Monorail Platform to Oldtown", []),
    Door("Downtown - Monorail Plaza", []),
    Door("Downtown - Monorail Street", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Monorail Plaza
# ------------------------------------------------------------------------
regionName = "Downtown - Monorail Plaza"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Person",
        vanilla = Entity(Category.CONSTANT, "Person", 0x6B6BA, []),
        requires = [],
        address = 0xCA8B5,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A Busy Man",
        vanilla = Entity(Category.CONSTANT, "A Busy Man", 0x6CC15, []),
        requires = [],
        address = 0xCA8BB,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A Busy Man",
        vanilla = Entity(Category.CONSTANT, "A Busy Man", 0x6CC00, []),
        requires = [],
        address = 0xCA8C1,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A Busy Man",
        vanilla = Entity(Category.CONSTANT, "A Busy Man", 0x6CC2A, []),
        requires = [],
        address = 0xCA8C7,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A Busy Man",
        vanilla = Entity(Category.CONSTANT, "A Busy Man", 0x6CBF9, []),
        requires = [],
        address = 0xCA8CD,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A Busy Man",
        vanilla = Entity(Category.CONSTANT, "A Busy Man", 0x6CC31, []),
        requires = [],
        address = 0xCA8D3,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Downtown - Monorail Station", []),
    Door("Downtown - Aneki Street", []),
    Door("Downtown - Crossroads", []),
    Door("Downtown - Graveyard and Graveyard Street // Graveyard", []),
    Door("Downtown - Dark Blade Street", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Aneki Street
# ------------------------------------------------------------------------
regionName = "Downtown - Aneki Street"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Mage",
        vanilla = Entity(Category.CONSTANT, "Mage", 0x6BB0C, []),
        requires = [],
        address = 0xD06E9,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Downtown - Monorail Plaza", []),
    Door("Downtown - Maplethorpe Plaza", []),
    Door("Aneki Building - 1st Floor", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Maplethorpe Plaza
# ------------------------------------------------------------------------
regionName = "Downtown - Maplethorpe Plaza"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Stall Keeper",
        vanilla = Entity(Category.CONSTANT, "Stall Keeper", 0x6B356, []),
        requires = [],
        address = 0xCB29D,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Dancing Hippie!",
        vanilla = Entity(Category.CONSTANT, "Dancing Hippie!", 0x6C626, []),
        requires = [],
        address = 0xCB297,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Downtown - Aneki Street", []),
    Door("Downtown - Maplethorpe Waiting Room", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Maplethorpe Waiting Room
# ------------------------------------------------------------------------
regionName = "Downtown - Maplethorpe Waiting Room"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Secretary",
        vanilla = Entity(Category.CONSTANT, "Secretary", 0x6B421, [
            (Progress.EVENT___MAPLETHORPE_DOOR_OPENED, [Progress.KEYWORD___CORTEX_BOMB]),
        ]),
        requires = [],
        address = 0xCB339,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Downtown - Maplethorpe Plaza", []),
    Door("Downtown - Maplethorpe Operating Room", [Progress.EVENT___MAPLETHORPE_DOOR_OPENED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Maplethorpe Operating Room
# ------------------------------------------------------------------------
regionName = "Downtown - Maplethorpe Operating Room"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Street Doc",
        vanilla = Entity(Category.CONSTANT, "Street Doc", 0x6B34F, [
            (Progress.EVENT___DATAJACK_REPAIRED,      [Progress.KEYWORD___CORTEX_BOMB]),
            (Progress.KEYWORD___CYBERWARE,            [Progress.EVENT___DATAJACK_REPAIRED]),
            (Progress.KEYWORD___HEAD_COMPUTER,        [Progress.EVENT___DATAJACK_REPAIRED]),
            (Progress.KEYWORD___MATRIX_SYSTEMS,       [Progress.EVENT___DATAJACK_REPAIRED]),
            (Progress.EVENT___UNLIMITED_SLAP_PATCHES, [Progress.KEYWORD___HEAL]),
        ]),
        requires = [],
        address = 0xCB3C9,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Skill Software",
        vanilla = Entity(Category.CONSTANT, "Skill Software", 0x6B3DB, [
            (Progress.CYBERWARE___SKILL_SOFTWARE, [Progress.KEYWORD___CYBERWARE]),
            (Progress.SKILL___LEADERSHIP,         [Progress.KEYWORD___CYBERWARE]),
        ]),
        requires = [],
        address = 0xCB3E7,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Boosted Reflexes",
        vanilla = Entity(Category.CONSTANT, "Boosted Reflexes", 0x6C960, [
            (Progress.CYBERWARE___BOOSTED_REFLEXES, [Progress.KEYWORD___CYBERWARE]),
        ]),
        requires = [],
        address = 0xCB3F3,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Dermal Plating",
        vanilla = Entity(Category.CONSTANT, "Dermal Plating", 0x6C5F5, [
            (Progress.CYBERWARE___DERMAL_PLATING, [
                Progress.KEYWORD___CYBERWARE,
                Progress.EVENT___JESTER_SPIRIT_PORTAL_USED,
            ]),
        ]),
        requires = [],
        address = 0xCB3ED,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Downtown - Maplethorpe Waiting Room", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Monorail Street
# ------------------------------------------------------------------------
regionName = "Downtown - Monorail Street"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Monorail Station", []),
    Door("Downtown - Wastelands Street", []),
    Door("Downtown - Crossroads", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Wastelands Street
# ------------------------------------------------------------------------
regionName = "Downtown - Wastelands Street"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Monorail Street", []),
    Door("Downtown - Wastelands Club", []),
    Door("Downtown - Rust Stilettos Street", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Wastelands Club
# ------------------------------------------------------------------------
regionName = "Downtown - Wastelands Club"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.NPC,
        description = "Dwarf (Norbert)",
        vanilla = Entity(Category.NPC, "Dwarf (Norbert)", 0x6C497, [
            (Progress.NPC___NORBERT, []),
        ]),
        requires = [],
        address = 0xCBB4F,
        hidden = False,
    ),
    # Jetboy's location is intentionally constant. This way, it's
    # easier to collect the $2,000 that he finds if you defeat the
    # Rust Stiletto gang leader with him in your party.
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Decker (Jetboy)",
        vanilla = Entity(Category.CONSTANT, "Decker (Jetboy)", 0x6C5FC, [
            (Progress.NPC___JETBOY,      []),
            (Progress.KEYWORD___RAITSOV, [Progress.KEYWORD___MATRIX_SYSTEMS]),
        ]),
        requires = [],
        address = 0xCBB49,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Club Manager",
        vanilla = Entity(Category.CONSTANT, "Club Manager", 0x6C895, [
            (Progress.KEYWORD___ICE, []),
        ]),
        requires = [],
        address = 0xCBB43,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.NPC,
        description = "Mercenary (Anders)",
        vanilla = Entity(Category.NPC, "Mercenary (Anders)", 0x6B8D5, [
            (Progress.NPC___ANDERS,          []),
            (Progress.KEYWORD___AKIMI,       [Progress.KEYWORD___SHADOWRUNNERS]),
            (Progress.KEYWORD___STEELFLIGHT, [Progress.KEYWORD___SHADOWRUNNERS]),
        ]),
        requires = [],
        address = 0xCBB5B,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.NPC,
        description = "Orc (Frogtongue)",
        vanilla = Entity(Category.NPC, "Orc (Frogtongue)", 0x6B7AF, [
            (Progress.NPC___FROGTONGUE, []),
        ]),
        requires = [],
        address = 0xCBB91,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Well dressed...",
        vanilla = Entity(Category.CONSTANT, "Well dressed...", 0x6B157, []),
        requires = [],
        address = 0xCBB8B,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Dancing Hippie!",
        vanilla = Entity(Category.CONSTANT, "Dancing Hippie!", 0x6C62D, []),
        requires = [],
        address = 0xCBB85,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "A Busy Man",
        vanilla = Entity(Category.CONSTANT, "A Busy Man", 0x6CC3F, [
            (Progress.EVENT___ICE_DELIVERED_TO_DOCKS, [
                # In vanilla, the ice delivery guy at Wastelands will not
                # appear until you know either "Nirwanda" or "Laughlyn".
                # In vanilla, this is equivalent to knowing "Bremerton",
                # since you can't learn either of the former without also
                # learning the latter (and vice versa).
                # It's been changed to the latter here to match the new
                # way of learning "Bremerton" (i.e. from a keyword-item).
                # This requirement is here instead of in "requires" below
                # because it is part of the ice delivery guy's behaviour
                # script, and would persist even if the ice delivery guy
                # was relocated.
                Progress.KEYWORD___BREMERTON,
                Progress.KEYWORD___ICE,
                Progress.KEYWORD___DOCKS,
            ]),
        ]),
        requires = [],
        address = 0xCBB55,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Downtown - Wastelands Street", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Rust Stilettos Street
# ------------------------------------------------------------------------
regionName = "Downtown - Rust Stilettos Street"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Wastelands Street", []),
    Door("Downtown - Rust Stilettos HQ (front room)", [Progress.ITEM___IRON_KEY]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Rust Stilettos HQ (front room)
# ------------------------------------------------------------------------
regionName = "Downtown - Rust Stilettos HQ (front room)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Crowbar",
        vanilla = Entity(Category.KEY_ITEM, "Crowbar", 0x6C6B9, [
            (Progress.ITEM___CROWBAR, []),
        ]),
        requires = [],
        address = 0xD0827,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Downtown - Rust Stilettos Street", []),
    Door("Downtown - Rust Stilettos HQ (back room)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Rust Stilettos HQ (back room)
# ------------------------------------------------------------------------
regionName = "Downtown - Rust Stilettos HQ (back room)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Gang Leader",
        vanilla = Entity(Category.CONSTANT, "Gang Leader", 0x6C2C9, [
            # In vanilla, defeating the Gang Leader would start an
            # automatic conversation that would teach you the
            # "Drake" keyword.
            (Progress.EVENT___RUST_STILETTOS_DEFEATED, []),
        ]),
        requires = [],
        address = 0xD08E7,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_KEY_ITEM,
        description = "Password (Drake)",
        vanilla = Entity(Category.KEY_ITEM, "Password (Drake)", 0x6B79A, [
            (Progress.ITEM___PASSWORD___DRAKE, []),
        ]),
        requires = [],
        address = 0xD08ED,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Downtown - Rust Stilettos HQ (front room)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Crossroads
# ------------------------------------------------------------------------
regionName = "Downtown - Crossroads"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Monorail Plaza", []),
    Door("Downtown - Monorail Street", []),
    Door("Downtown - Jagged Nails Street", []),
    Door("Downtown - Drake Street", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Jagged Nails Street
# ------------------------------------------------------------------------
regionName = "Downtown - Jagged Nails Street"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Crossroads", []),
    Door("Downtown - Hotel (lobby)", []),
    # In vanilla, "Progress.EVENT___RUST_STILETTOS_DEFEATED" is
    # required to enter Jagged Nails.
    Door("Downtown - Jagged Nails", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Hotel (lobby)
# ------------------------------------------------------------------------
regionName = "Downtown - Hotel (lobby)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Jagged Nails Street", []),
    Door("Downtown - Hotel (room)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Hotel (room)
# ------------------------------------------------------------------------
regionName = "Downtown - Hotel (room)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Hotel (lobby)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Jagged Nails
# ------------------------------------------------------------------------
regionName = "Downtown - Jagged Nails"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.NPC,
        description = "Kitsune",
        vanilla = Entity(Category.NPC, "Kitsune", 0x6BB7C, [
            (Progress.NPC___KITSUNE,        []),
            (Progress.ITEM___LEAVES,        [Progress.KEYWORD___DOG]),
            (Progress.KEYWORD___DARK_BLADE, [Progress.KEYWORD___JESTER_SPIRIT]),
            (Progress.KEYWORD___VAMPIRES,   [Progress.KEYWORD___DARK_BLADE]),
        ]),
        requires = [],
        address = 0xCB79B,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Club Manager",
        vanilla = Entity(Category.CONSTANT, "Club Manager", 0x6C8B8, [
            (Progress.KEYWORD___VAMPIRES, [Progress.KEYWORD___DARK_BLADE]),
            (Progress.ITEM___STROBE,      [Progress.KEYWORD___STROBES]),
        ]),
        requires = [],
        address = 0xCB77D,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.NPC,
        description = "Decker (Steelflight)",
        vanilla = Entity(Category.NPC, "Decker (Steelflight)", 0x6C611, [
            (Progress.NPC___STEELFLIGHT, []),
            (Progress.KEYWORD___ANDERS,  [Progress.KEYWORD___SHADOWRUNNERS]),
        ]),
        requires = [],
        address = 0xCB78F,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Club Manager",
        vanilla = Entity(Category.CONSTANT, "Club Manager", 0x6C8B1, [
            (Progress.KEYWORD___KITSUNE,   []),
            (Progress.PHONE_NUMBER___DR_M, [Progress.KEYWORD___STREET_DOC]),
            (Progress.KEYWORD___STROBES,   [Progress.KEYWORD___VAMPIRES]),
        ]),
        requires = [],
        address = 0xCB783,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.NPC,
        description = "Mage (Spatter)",
        vanilla = Entity(Category.NPC, "Mage (Spatter)", 0x6BA41, [
            (Progress.NPC___SPATTER, []),
        ]),
        requires = [],
        address = 0xCB7A1,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Downtown - Jagged Nails Street", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Drake Street
# ------------------------------------------------------------------------
regionName = "Downtown - Drake Street"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Crossroads", []),
    Door("Waterfront - Entrance", []),
    Door("Downtown - Graveyard and Graveyard Street // Graveyard Street", []),
    Door("Drake Towers - 1st Floor", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Waterfront - Entrance
# ------------------------------------------------------------------------
regionName = "Waterfront - Entrance"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Drake Street", []),
    Door("Waterfront - South", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Waterfront - South
# ------------------------------------------------------------------------
regionName = "Waterfront - South"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Waterfront - Entrance", []),
    Door("Waterfront - Taxiboat Dock", []),
    Door("Waterfront - Matrix Systems", []),
    Door("Waterfront - North", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Waterfront - Taxiboat Dock
# ------------------------------------------------------------------------
regionName = "Waterfront - Taxiboat Dock"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Boat driver",
        vanilla = Entity(Category.CONSTANT, "Boat driver", 0x6C96E, [
            (Progress.KEYWORD___DOCKS,        []),
            (Progress.KEYWORD___MERMAIDS,     [Progress.KEYWORD___BREMERTON]),
            (Progress.EVENT___TAXIBOAT_HIRED, [
                Progress.EVENT___ICE_DELIVERED_TO_DOCKS,
                Progress.KEYWORD___BREMERTON,
            ]),
        ]),
        requires = [],
        address = 0xCA5FB,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Explosives",
        vanilla = Entity(Category.PHYSICAL_ITEM, "Explosives", 0x6C3D3, [
            (Progress.ITEM___EXPLOSIVES, []),
        ]),
        # In vanilla, the Massive Orc that drops the Explosives will not
        # appear until you know either "Nirwanda" or "Laughlyn".
        requires = [Progress.EVENT___ICE_DELIVERED_TO_DOCKS],
        address = 0xCA60D,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Waterfront - South", []),
    Door("Bremerton - West // Lower", [Progress.EVENT___TAXIBOAT_HIRED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Waterfront - Matrix Systems
# ------------------------------------------------------------------------
regionName = "Waterfront - Matrix Systems"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "DF_MT-AI", 0x6C57E, [
            (Progress.ITEM___DF_MT_AI, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xCB8FF,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Waterfront - South", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Waterfront - North
# ------------------------------------------------------------------------
regionName = "Waterfront - North"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Mermaid Scales",
        vanilla = Entity(Category.TALISMAN, "Mermaid Scales", 0x6B8C7, [
            (Progress.ITEM___MERMAID_SCALES, []),
        ]),
        requires = [Progress.EVENT___ICE_DELIVERED_TO_DOCKS],
        address = 0xCA691,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Waterfront - South", []),
    Door("Waterfront - Dog Spirit", []),
    Door("Waterfront - Octopus boss room", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Waterfront - Dog Spirit
# ------------------------------------------------------------------------
regionName = "Waterfront - Dog Spirit"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Dog spirit",
        vanilla = Entity(Category.CONSTANT, "Dog spirit", 0x6C562, [
            (Progress.EVENT___EARTH_CREATURE_AND_MAN, [
                Progress.ITEM___LEAVES,
                Progress.ITEM___DOG_COLLAR,
                Progress.ITEM___MAGIC_FETISH,
            ]),
            (Progress.KEYWORD___RAT, [
                Progress.EVENT___EARTH_CREATURE_AND_MAN,
            ]),
            (Progress.EVENT___RAT_SHAMAN_GATE_OPENED, [
                Progress.EVENT___EARTH_CREATURE_AND_MAN,
            ]),
            (Progress.MAGIC___HEAL, [
                Progress.EVENT___EARTH_CREATURE_AND_MAN,
            ]),
            (Progress.MAGIC___POWERBALL, [
                Progress.EVENT___EARTH_CREATURE_AND_MAN,
                Progress.EVENT___RAT_SHAMAN_DEFEATED,
                Progress.ITEM___PAPERWEIGHT,
                Progress.ITEM___GHOUL_BONE,
            ]),
            (Progress.MAGIC___FREEZE, [
                Progress.EVENT___EARTH_CREATURE_AND_MAN,
                Progress.EVENT___RAT_SHAMAN_DEFEATED,
                Progress.ITEM___BLACK_BOTTLE,
                Progress.EVENT___POOL_OF_INK_COLLECTED,
                Progress.ITEM___MERMAID_SCALES,
            ]),
            (Progress.MAGIC___SUMMON_SPIRIT, [
                Progress.EVENT___EARTH_CREATURE_AND_MAN,
                Progress.EVENT___RAT_SHAMAN_DEFEATED,
                Progress.ITEM___DOG_COLLAR,
                Progress.ITEM___DOG_TAG,
            ]),
            (Progress.MAGIC___INVISIBILITY, [
                Progress.EVENT___EARTH_CREATURE_AND_MAN,
                Progress.EVENT___RAT_SHAMAN_DEFEATED,
                Progress.ITEM___POTION_BOTTLES,
                Progress.EVENT___CLEAN_WATER_COLLECTED,
                Progress.EVENT___TOXIC_WATER_COLLECTED,
            ]),
            (Progress.MAGIC___ARMOR, [
                Progress.EVENT___EARTH_CREATURE_AND_MAN,
                Progress.EVENT___RAT_SHAMAN_DEFEATED,
                Progress.ITEM___MERMAID_SCALES,
                Progress.ITEM___SERPENT_SCALES,
            ]),
        ]),
        requires = [],
        address = 0xCBE21,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Waterfront - North", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Waterfront - Octopus boss room
# ------------------------------------------------------------------------
regionName = "Waterfront - Octopus boss room"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Octopus",
        vanilla = Entity(Category.CONSTANT, "Octopus", 0x6B7E0, [
            (Progress.EVENT___OCTOPUS_DEFEATED, []),
        ]),
        requires = [],
        address = 0xCB181,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_KEY_ITEM,
        description = "Nuyen: Octopus",
        vanilla = Entity(Category.PHYSICAL_ITEM, "Nuyen: Octopus", 0x6B7E7, [
            (Progress.ITEM___NUYEN___OCTOPUS, []),
        ]),
        requires = [Progress.EVENT___OCTOPUS_DEFEATED],
        address = 0xCB18D,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Pool of Ink",
        vanilla = Entity(Category.CONSTANT, "Pool of Ink", 0x6B697, [
            (Progress.EVENT___POOL_OF_INK_COLLECTED, [Progress.ITEM___BLACK_BOTTLE]),
        ]),
        requires = [Progress.EVENT___OCTOPUS_DEFEATED],
        address = 0xCB1B1,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Waterfront - North", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Graveyard and Graveyard Street // Graveyard
# ------------------------------------------------------------------------
regionName = "Downtown - Graveyard and Graveyard Street // Graveyard"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Monorail Plaza", []),
    Door("Downtown - Rat Shaman's Lair (first hallway)", [Progress.EVENT___RAT_SHAMAN_GATE_OPENED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Rat Shaman's Lair (first hallway)
# ------------------------------------------------------------------------
regionName = "Downtown - Rat Shaman's Lair (first hallway)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Graveyard and Graveyard Street // Graveyard", []),
    Door("Downtown - Rat Shaman's Lair (first side room)", []),
    Door("Downtown - Rat Shaman's Lair (second hallway)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Rat Shaman's Lair (first side room)
# ------------------------------------------------------------------------
regionName = "Downtown - Rat Shaman's Lair (first side room)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Rat Shaman's Lair (first hallway)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Rat Shaman's Lair (second hallway)
# ------------------------------------------------------------------------
regionName = "Downtown - Rat Shaman's Lair (second hallway)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Rat Shaman's Lair (first hallway)", []),
    Door("Downtown - Rat Shaman's Lair (second side room)", []),
    Door("Downtown - Rat Shaman's Lair (Rat Shaman boss room)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Rat Shaman's Lair (second side room)
# ------------------------------------------------------------------------
regionName = "Downtown - Rat Shaman's Lair (second side room)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Rat Shaman's Lair (second hallway)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Rat Shaman's Lair (Rat Shaman boss room)
# ------------------------------------------------------------------------
regionName = "Downtown - Rat Shaman's Lair (Rat Shaman boss room)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Rat Shaman",
        vanilla = Entity(Category.CONSTANT, "Rat Shaman", 0x6B682, [
            (Progress.EVENT___RAT_SHAMAN_DEFEATED, []),
        ]),
        requires = [],
        address = 0xD065D,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_KEY_ITEM,
        description = "Keyword: Jester Spirit",
        vanilla = Entity(Category.PHYSICAL_KEY_ITEM, "Keyword: Jester Spirit", 0x6B8C0, [
            (Progress.ITEM___KEYWORD___JESTER_SPIRIT, []),
        ]),
        requires = [Progress.EVENT___RAT_SHAMAN_DEFEATED],
        address = 0xD29A7,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_KEY_ITEM,
        description = "Nuyen: Rat Shaman",
        vanilla = Entity(Category.PHYSICAL_ITEM, "Nuyen: Rat Shaman", 0x6B8B9, [
            (Progress.ITEM___NUYEN___RAT_SHAMAN, []),
        ]),
        requires = [Progress.EVENT___RAT_SHAMAN_DEFEATED],
        address = 0xD2965,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Downtown - Rat Shaman's Lair (second hallway)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Graveyard and Graveyard Street // Graveyard Street
# ------------------------------------------------------------------------
regionName = "Downtown - Graveyard and Graveyard Street // Graveyard Street"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Drake Street", []),
    Door("Downtown - Dark Blade Street", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Downtown - Dark Blade Street
# ------------------------------------------------------------------------
regionName = "Downtown - Dark Blade Street"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Graveyard and Graveyard Street // Graveyard Street", []),
    Door("Downtown - Monorail Plaza", []),
    Door("Dark Blade - Courtyard", [Progress.EVENT___DARK_BLADE_GATE_OPENED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Dark Blade - Courtyard
# ------------------------------------------------------------------------
regionName = "Dark Blade - Courtyard"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Downtown - Dark Blade Street", []),
    Door("Dark Blade - Gun Shop", []),
    Door("Dark Blade - Main Hall", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Dark Blade - Gun Shop
# ------------------------------------------------------------------------
regionName = "Dark Blade - Gun Shop"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Shopkeeper",
        vanilla = Entity(Category.CONSTANT, "Shopkeeper", 0x6B3E2, []),
        requires = [],
        address = 0xD16E5,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "Viper H. Pistol ($3,000)",
        vanilla = Entity(Category.EARLY_WEAPON, "Viper H. Pistol ($3,000)", 0x6B188, [
            (Progress.WEAPON___VIPER_H_PISTOL___3000, []),
        ]),
        requires = [],
        address = 0xD1715,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "T-250 Shotgun ($12,000)",
        vanilla = Entity(Category.WEAPON, "T-250 Shotgun ($12,000)", 0x6B2A7, [
            (Progress.WEAPON___T_250_SHOTGUN___12000, []),
        ]),
        requires = [],
        address = 0xD171B,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "Uzi III SMG",
        vanilla = Entity(Category.WEAPON, "Uzi III SMG", 0x6B1D5, [
            (Progress.WEAPON___UZI_III_SMG, []),
        ]),
        requires = [],
        address = 0xD1721,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "HK 277 A. Rifle",
        vanilla = Entity(Category.WEAPON, "HK 277 A. Rifle", 0x6BC24, [
            (Progress.WEAPON___HK_277_A_RIFLE, []),
        ]),
        requires = [Progress.EVENT___JESTER_SPIRIT_PORTAL_USED],
        address = 0xD1727,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "Bulletproof Vest",
        vanilla = Entity(Category.EARLY_ARMOR, "Bulletproof Vest", 0x6C8D4, [
            (Progress.ARMOR___BULLETPROOF_VEST, []),
        ]),
        requires = [],
        address = 0xD172D,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "Concealed Jacket",
        vanilla = Entity(Category.ARMOR, "Concealed Jacket", 0x6C6C7, [
            (Progress.ARMOR___CONCEALED_JACKET, []),
        ]),
        requires = [Progress.EVENT___DRAKE_TOWERS_CLEARED],
        address = 0xD1733,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "Partial Bodysuit",
        vanilla = Entity(Category.ARMOR, "Partial Bodysuit", 0x6B7A1, [
            (Progress.ARMOR___PARTIAL_BODYSUIT, []),
        ]),
        requires = [Progress.EVENT___JESTER_SPIRIT_PORTAL_USED],
        address = 0xD1739,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "Full Bodysuit",
        vanilla = Entity(Category.ARMOR, "Full Bodysuit", 0x6C2D0, [
            (Progress.ARMOR___FULL_BODYSUIT, []),
        ]),
        requires = [Progress.EVENT___PROFESSOR_PUSHKIN_RESCUED],
        address = 0xD1745,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.WEAPON_OR_ARMOR,
        description = "AS-7 A. Cannon",
        vanilla = Entity(Category.WEAPON, "AS-7 A. Cannon", 0x6CB90, [
            (Progress.WEAPON___AS_7_A_CANNON, []),
        ]),
        requires = [Progress.EVENT___PROFESSOR_PUSHKIN_RESCUED],
        address = 0xD174B,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Dark Blade - Courtyard", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Dark Blade - Main Hall
# ------------------------------------------------------------------------
regionName = "Dark Blade - Main Hall"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Dark Blade - Courtyard", []),
    Door("Dark Blade - Left Room", []),
    Door("Dark Blade - Right Room", []),
    Door("Dark Blade - Middle Room", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Dark Blade - Left Room
# ------------------------------------------------------------------------
regionName = "Dark Blade - Left Room"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    # In vanilla, this is "Vladimir"
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Keyword: Bremerton",
        vanilla = Entity(Category.PHYSICAL_KEY_ITEM, "Keyword: Bremerton", 0x6B17A, [
            (Progress.ITEM___KEYWORD___BREMERTON, []),
        ]),
        requires = [],
        address = 0xD0A95,
        hidden = False,
    ),
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer (left)",
        vanilla = Entity(Category.CONSTANT, "DF_DB-Jester", 0x6C5D2, [
            (Progress.ITEM___DF_DB_JESTER, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xCB905,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Dark Blade - Main Hall", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Dark Blade - Right Room
# ------------------------------------------------------------------------
regionName = "Dark Blade - Right Room"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Bronze Key",
        vanilla = Entity(Category.KEY_ITEM, "Bronze Key", 0x6C921, [
            (Progress.ITEM___BRONZE_KEY, []),
        ]),
        requires = [],
        address = 0xD0B0B,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.ARMOR,
        description = "Mesh Jacket (free)",
        vanilla = Entity(Category.EARLY_ARMOR, "Mesh Jacket (free)", 0x6B88F, [
            (Progress.ARMOR___MESH_JACKET___FREE, []),
        ]),
        requires = [],
        address = 0xD0B23,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Dark Blade - Main Hall", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Dark Blade - Middle Room
# ------------------------------------------------------------------------
regionName = "Dark Blade - Middle Room"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Dark Blade - Main Hall", []),
    Door("Dark Blade - Kitchen", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Dark Blade - Kitchen
# ------------------------------------------------------------------------
regionName = "Dark Blade - Kitchen"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Dark Blade - Middle Room", []),
    Door("Dark Blade - First Crypt", [Progress.ITEM___BRONZE_KEY]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Dark Blade - First Crypt
# ------------------------------------------------------------------------
regionName = "Dark Blade - First Crypt"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Dark Blade - Kitchen", []),
    Door("Dark Blade - Second Crypt", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Dark Blade - Second Crypt
# ------------------------------------------------------------------------
regionName = "Dark Blade - Second Crypt"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Dark Blade - First Crypt", []),
    Door("Dark Blade - Third Crypt", []),
    Door("Dark Blade - Vampire boss room", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Dark Blade - Third Crypt
# ------------------------------------------------------------------------
regionName = "Dark Blade - Third Crypt"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Dark Blade - Second Crypt", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Dark Blade - Vampire boss room
# ------------------------------------------------------------------------
regionName = "Dark Blade - Vampire boss room"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Vampire!",
        vanilla = Entity(Category.CONSTANT, "Vampire!", 0x6B1B9, [
            (Progress.EVENT___VAMPIRE_DEFEATED, [
                Progress.ITEM___STROBE,
                Progress.ITEM___STAKE,
                # In vanilla, "Progress.KEYWORD___JESTER_SPIRIT" is
                # also required in order to defeat the Vampire.
            ]),
        ]),
        requires = [],
        address = 0xD0F53,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_KEY_ITEM,
        description = "Keyword: Laughlyn",
        vanilla = Entity(Category.PHYSICAL_KEY_ITEM, "Keyword: Laughlyn", 0x6B8B2, [
            (Progress.ITEM___KEYWORD___LAUGHLYN, []),
        ]),
        requires = [Progress.EVENT___VAMPIRE_DEFEATED],
        address = 0xD29CB,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_KEY_ITEM,
        description = "Nuyen: Vampire",
        vanilla = Entity(Category.PHYSICAL_ITEM, "Nuyen: Vampire", 0x6B8AB, [
            (Progress.ITEM___NUYEN___VAMPIRE, []),
        ]),
        requires = [Progress.EVENT___VAMPIRE_DEFEATED],
        address = 0xD29AD,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Dark Blade - Second Crypt", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - West // Lower
# ------------------------------------------------------------------------
regionName = "Bremerton - West // Lower"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Waterfront - Taxiboat Dock", []),
    Door("Bremerton - East", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - East
# ------------------------------------------------------------------------
regionName = "Bremerton - East"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - West // Lower", []),
    Door("Bremerton - West // Upper", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - West // Upper
# ------------------------------------------------------------------------
regionName = "Bremerton - West // Upper"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Dog Tag",
        vanilla = Entity(Category.TALISMAN, "Dog Tag", 0x6C55B, [
            (Progress.ITEM___DOG_TAG, []),
        ]),
        requires = [],
        address = 0xC9C79,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Bremerton - East", []),
    Door("Bremerton - Interior (1) // Entrance", [Progress.ITEM___CROWBAR]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (1) // Entrance
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (1) // Entrance"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - West // Upper", []),
    Door("Bremerton - Interior (2)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (2)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (2)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (1) // Entrance", []),
    Door("Bremerton - Interior (1) // Walkway", []),
    Door("Bremerton - Interior (3)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (1) // Walkway
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (1) // Walkway"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (2)", []),
    Door("Bremerton - Interior (Staircase I, top)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (Staircase I, top)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (Staircase I, top)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (1) // Walkway", []),
    Door("Bremerton - Interior (Staircase I, middle)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (Staircase I, middle)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (Staircase I, middle)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (Staircase I, top)", []),
    Door("Bremerton - Interior (Staircase I, bottom)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (Staircase I, bottom)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (Staircase I, bottom)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (Staircase I, middle)", []),
    Door("Bremerton - Interior (Safe I)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (Safe I)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (Safe I)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Safe Key",
        vanilla = Entity(Category.CONSTANT, "Safe Key", 0x6B65F, [
            (Progress.ITEM___SAFE_KEY, []),
        ]),
        requires = [],
        address = 0xD2315,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Detonator",
        vanilla = Entity(Category.PHYSICAL_ITEM, "Detonator", 0x6C5EE, [
            (Progress.ITEM___DETONATOR, []),
        ]),
        requires = [Progress.ITEM___SAFE_KEY],
        address = 0xD230F,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Broken Bottle",
        vanilla = Entity(Category.ITEM, "Broken Bottle", 0x6C959, [
            (Progress.ITEM___BROKEN_BOTTLE, []),
        ]),
        requires = [Progress.ITEM___SAFE_KEY],
        address = 0xD2321,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Bremerton - Interior (Staircase I, bottom)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (3)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (3)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (2)", []),
    Door("Bremerton - Interior (4)", []),
    Door("Bremerton - Interior (5)", []),
    Door("Bremerton - Interior (6)", []),
    Door("Bremerton - Interior (9)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (4)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (4)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (3)", []),
    Door("Bremerton - Interior (5)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (5)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (5)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Toxic Water",
        vanilla = Entity(Category.CONSTANT, "Toxic Water", 0x6B253, [
            (Progress.EVENT___TOXIC_WATER_COLLECTED, [Progress.ITEM___POTION_BOTTLES]),
        ]),
        requires = [],
        address = 0xC9989,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Bremerton - Interior (3)", []),
    Door("Bremerton - Interior (4)", []),
    Door("Bremerton - Interior (Staircase II, top)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (Staircase II, top)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (Staircase II, top)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (5)", []),
    Door("Bremerton - Interior (Staircase II, middle)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (Staircase II, middle)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (Staircase II, middle)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (Staircase II, top)", []),
    Door("Bremerton - Interior (Staircase II, bottom)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (Staircase II, bottom)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (Staircase II, bottom)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (Staircase II, middle)", []),
    Door("Bremerton - Interior (Safe II)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (Safe II)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (Safe II)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Green Bottle",
        vanilla = Entity(Category.KEY_ITEM, "Green Bottle", 0x6C092, [
            (Progress.ITEM___GREEN_BOTTLE, []),
        ]),
        requires = [Progress.ITEM___TIME_BOMB],
        address = 0xD24E9,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Bremerton - Interior (Staircase II, bottom)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (6)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (6)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (3)", []),
    Door("Bremerton - Interior (7)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (7)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (7)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (6)", []),
    Door("Bremerton - Interior (8)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (8)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (8)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (7)", []),
    Door("Bremerton - Interior (9)", []),
    Door("Bremerton - Interior (10)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (9)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (9)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
])
thisRegion.doors.extend([
    Door("Bremerton - Interior (3)", []),
    Door("Bremerton - Interior (8)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (10)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (10)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (8)", []),
    Door("Bremerton - Interior (11)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (11)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (11)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (10)", []),
    Door("Bremerton - Interior (12)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (12)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (12)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (11)", []),
    Door("Bremerton - Interior (13, portal to Spirit World)", [Progress.ITEM___GREEN_BOTTLE]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Bremerton - Interior (13, portal to Spirit World)
# ------------------------------------------------------------------------
regionName = "Bremerton - Interior (13, portal to Spirit World)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (12)", []),
    Door("Spirit World - First Room (Naga boss room)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Spirit World - First Room (Naga boss room)
# ------------------------------------------------------------------------
regionName = "Spirit World - First Room (Naga boss room)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Bremerton - Interior (13, portal to Spirit World)", []),
    Door("Spirit World - Second Room", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Spirit World - Second Room
# ------------------------------------------------------------------------
regionName = "Spirit World - Second Room"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Spirit World - First Room (Naga boss room)", []),
    Door("Spirit World - Third Room (Jester Spirit boss room)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Spirit World - Third Room (Jester Spirit boss room)
# ------------------------------------------------------------------------
regionName = "Spirit World - Third Room (Jester Spirit boss room)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Jester Spirit (boss)",
        vanilla = Entity(Category.CONSTANT, "Jester Spirit (boss)", 0x6BBB4, [
            # In vanilla, the Jester Spirit boss script silently and
            # automatically teaches you "Progress.KEYWORD___DRAKE",
            # which is required to get "Progress.KEYWORD___VOLCANO".
            (Progress.EVENT___JESTER_SPIRIT_DEFEATED,    [Progress.KEYWORD___LAUGHLYN]),
            (Progress.EVENT___JESTER_SPIRIT_PORTAL_OPEN, [Progress.EVENT___JESTER_SPIRIT_DEFEATED]),
            (Progress.EVENT___JESTER_SPIRIT_PORTAL_USED, [Progress.EVENT___JESTER_SPIRIT_PORTAL_OPEN]),
            # In vanilla, the following progression order is enforced:
            # - Progress.EVENT___JESTER_SPIRIT_DEFEATED
            # - Progress.KEYWORD___VOLCANO
            # - Progress.ITEM___JESTER_SPIRIT_INSIGNIA
            # - Progress.EVENT___JESTER_SPIRIT_PORTAL_OPEN
        ]),
        requires = [],
        address = 0xCAE11,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_KEY_ITEM,
        description = "Keyword: Volcano",
        vanilla = Entity(Category.PHYSICAL_KEY_ITEM, "Keyword: Volcano", 0x6B8A4, [
            (Progress.ITEM___KEYWORD___VOLCANO, []),
        ]),
        requires = [Progress.EVENT___JESTER_SPIRIT_DEFEATED],
        address = 0xD299B,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_KEY_ITEM,
        description = "Jester Spirit Insignia",
        vanilla = Entity(Category.KEY_ITEM, "Jester Spirit Insignia", 0x6BBC9, [
            (Progress.ITEM___JESTER_SPIRIT_INSIGNIA, []),
        ]),
        requires = [Progress.EVENT___JESTER_SPIRIT_DEFEATED],
        address = 0xCAE23,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Spirit World - Second Room", []),
    Door("Waterfront - Taxiboat Dock", [Progress.EVENT___JESTER_SPIRIT_PORTAL_OPEN]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Drake Towers - 1st Floor
# ------------------------------------------------------------------------
regionName = "Drake Towers - 1st Floor"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "Computer", 0x6C730, [
            (Progress.EVENT___DRAKE_TOWERS_2F_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
                Progress.ITEM___PASSWORD___DRAKE,
            ]),
        ]),
        requires = [],
        address = 0xD17D9,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Downtown - Drake Street", []),
    Door("Drake Towers - 2nd Floor", [Progress.EVENT___DRAKE_TOWERS_2F_UNLOCKED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Drake Towers - 2nd Floor
# ------------------------------------------------------------------------
regionName = "Drake Towers - 2nd Floor"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer (left)",
        vanilla = Entity(Category.CONSTANT, "Computer (left)", 0x6C768, [
            (Progress.EVENT___DRAKE_TOWERS_3F_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
            ]),
        ]),
        requires = [],
        address = 0xD1857,
        hidden = False,
    ),
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer (right)",
        vanilla = Entity(Category.CONSTANT, "DF_DR 1-4", 0x6C5CB, [
            (Progress.ITEM___DF_DR_1_4, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xCB90B,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Drake Towers - 1st Floor", []),
    Door("Drake Towers - 3rd Floor", [Progress.EVENT___DRAKE_TOWERS_3F_UNLOCKED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Drake Towers - 3rd Floor
# ------------------------------------------------------------------------
regionName = "Drake Towers - 3rd Floor"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer (left)",
        vanilla = Entity(Category.CONSTANT, "DF_DR 2-4", 0x6C5C4, [
            (Progress.ITEM___DF_DR_2_4, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xCB911,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer (middle)",
        vanilla = Entity(Category.CONSTANT, "Computer (middle)", 0x6C70D, [
            (Progress.EVENT___DRAKE_TOWERS_4F_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
            ]),
        ]),
        requires = [],
        address = 0xD18F7,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Drake Towers - 2nd Floor", []),
    Door("Drake Towers - 4th Floor", [Progress.EVENT___DRAKE_TOWERS_4F_UNLOCKED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Drake Towers - 4th Floor
# ------------------------------------------------------------------------
regionName = "Drake Towers - 4th Floor"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer (left)",
        vanilla = Entity(Category.CONSTANT, "DF_DR 3-4", 0x6C5BD, [
            (Progress.ITEM___DF_DR_3_4, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xCB917,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer (right)",
        vanilla = Entity(Category.CONSTANT, "Computer (right)", 0x6C6CE, [
            (Progress.EVENT___DRAKE_TOWERS_5F_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
            ]),
        ]),
        requires = [],
        address = 0xD19A3,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Drake Towers - 3rd Floor", []),
    Door("Drake Towers - 5th Floor", [Progress.EVENT___DRAKE_TOWERS_5F_UNLOCKED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Drake Towers - 5th Floor
# ------------------------------------------------------------------------
regionName = "Drake Towers - 5th Floor"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer (left)",
        vanilla = Entity(Category.CONSTANT, "Computer (left)", 0x6C7C3, [
            (Progress.EVENT___LEVEL_6_NODE_DEACTIVATED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
            ]),
            (Progress.EVENT___DRAKE_TOWERS_6F_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
            ]),
        ]),
        requires = [],
        address = 0xD1A37,
        hidden = False,
    ),
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer (right)",
        vanilla = Entity(Category.CONSTANT, "DF_DR 4-4", 0x6C5B6, [
            (Progress.ITEM___DF_DR_4_4, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xCB91D,
        hidden = False,
    ),
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer (right)",
        vanilla = Entity(Category.CONSTANT, "DF_DR-VOLCANO", 0x6C5A8, [
            (Progress.ITEM___DF_DR_VOLCANO, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xCB923,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Drake Towers - 4th Floor", []),
    Door("Drake Towers - 6th Floor", [Progress.EVENT___DRAKE_TOWERS_6F_UNLOCKED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Drake Towers - 6th Floor
# ------------------------------------------------------------------------
regionName = "Drake Towers - 6th Floor"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "Computer", 0x6C7E6, [
            (Progress.EVENT___DRAKE_TOWERS_ROOF_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
                Progress.EVENT___LEVEL_6_NODE_DEACTIVATED,
            ]),
        ]),
        requires = [],
        address = 0xD1AEF,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Drake Towers - 5th Floor", []),
    Door("Drake Towers - Roof", [Progress.EVENT___DRAKE_TOWERS_ROOF_UNLOCKED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Drake Towers - Roof
# ------------------------------------------------------------------------
regionName = "Drake Towers - Roof"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Helicopter Pilot",
        vanilla = Entity(Category.CONSTANT, "Helicopter Pilot", 0x6BCF6, [
            (Progress.EVENT___DRAKE_TOWERS_CLEARED, []),
        ]),
        requires = [],
        address = 0xD1B83,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Drake Towers - 6th Floor", []),
    Door("Volcano - Exterior", [Progress.KEYWORD___VOLCANO]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Exterior
# ------------------------------------------------------------------------
regionName = "Volcano - Exterior"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Helicopter Pilot",
        vanilla = Entity(Category.CONSTANT, "Helicopter Pilot", 0x6BCEF, [
            # In vanilla, the Helicopter Pilot doesn't teach the
            # "Drake" keyword. We're teaching it here automatically
            # to guarantee that players can return to Drake Towers.
            (Progress.KEYWORD___DRAKE, []),
        ]),
        requires = [],
        address = 0xCBEAD,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Drake Towers - Roof", [Progress.KEYWORD___DRAKE]),
    Door("Volcano - Sublevel Zero", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Zero
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Zero"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Exterior", []),
    Door("Volcano - Sublevel One (1)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel One (1)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel One (1)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Zero", []),
    Door("Volcano - Sublevel One (2)", []),
    Door("Volcano - Sublevel One (3)", []),
    Door("Volcano - Sublevel One (7)", []),
    Door("Volcano - Sublevel One (9)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel One (2)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel One (2)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel One (1)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel One (3)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel One (3)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel One (1)", []),
    Door("Volcano - Sublevel One (4)", []),
    Door("Volcano - Sublevel One (5)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel One (4)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel One (4)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel One (3)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel One (5)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel One (5)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel One (3)", []),
    Door("Volcano - Sublevel One (6)", []),
    Door("Volcano - Sublevel One (7)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel One (6)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel One (6)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel One (5)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel One (7)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel One (7)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel One (1)", []),
    Door("Volcano - Sublevel One (5)", []),
    Door("Volcano - Sublevel One (8)", []),
    Door("Volcano - Sublevel One (9)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel One (8)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel One (8)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel One (7)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel One (9)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel One (9)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel One (1)", []),
    Door("Volcano - Sublevel One (7)", []),
    Door("Volcano - Sublevel One (10)", []),
    Door("Volcano - Sublevel Two (1)", [Progress.EVENT___DRAKE_VOLCANO_S2_UNLOCKED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel One (10)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel One (10)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "DF_DS-FAILURE", 0x6C593, [
            (Progress.ITEM___DF_DS_FAILURE, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xD21FB,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "Computer", 0x6C761, [
            (Progress.EVENT___DRAKE_VOLCANO_S2_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
            ]),
        ]),
        requires = [],
        address = 0xCC087,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Volcano - Sublevel One (9)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Two (1)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Two (1)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel One (9)", []),
    Door("Volcano - Sublevel Two (2)", []),
    Door("Volcano - Sublevel Two (3)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Two (2)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Two (2)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Two (1)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Two (3)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Two (3)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Two (1)", []),
    Door("Volcano - Sublevel Two (4)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Two (4)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Two (4)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Two (3)", []),
    Door("Volcano - Sublevel Two (5)", []),
    Door("Volcano - Sublevel Two (6)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Two (5)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Two (5)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "Computer", 0x6C74C, [
            (Progress.EVENT___DRAKE_VOLCANO_S3_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
            ]),
        ]),
        requires = [],
        address = 0xD28CB,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Volcano - Sublevel Two (4)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Two (6)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Two (6)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Two (4)", []),
    Door("Volcano - Sublevel Three (1)", [Progress.EVENT___DRAKE_VOLCANO_S3_UNLOCKED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Three (1)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Three (1)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Two (6)", []),
    Door("Volcano - Sublevel Three (2)", []),
    Door("Volcano - Sublevel Three (3)", []),
    Door("Volcano - Sublevel Three (6)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Three (2)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Three (2)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Three (1)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Three (3)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Three (3)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Three (1)", []),
    Door("Volcano - Sublevel Three (4)", []),
    Door("Volcano - Sublevel Three (5)", []),
    Door("Volcano - Sublevel Three (7)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Three (4)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Three (4)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Three (3)", []),
    Door("Volcano - Sublevel Three (5)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Three (5)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Three (5)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "DF_DS-AI END", 0x6C5A1, [
            (Progress.ITEM___DF_DS_AI_END, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xD2201,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Volcano - Sublevel Three (3)", []),
    Door("Volcano - Sublevel Three (4)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Three (6)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Three (6)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Three (1)", []),
    Door("Volcano - Sublevel Three (7)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Three (7)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Three (7)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Three (3)", []),
    Door("Volcano - Sublevel Three (6)", []),
    Door("Volcano - Sublevel Three (8)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Three (8)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Three (8)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Three (7)", []),
    Door("Volcano - Sublevel Three (9)", []),
    Door("Volcano - Sublevel Three (10)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Three (9)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Three (9)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer (upper right)",
        vanilla = Entity(Category.CONSTANT, "DF_DS-TARGET", 0x6C585, [
            (Progress.ITEM___DF_DS_TARGET, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xD2207,
        hidden = False,
    ),
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer (lower left)",
        vanilla = Entity(Category.CONSTANT, "DF_DS-AKIMI", 0x6C59A, [
            (Progress.ITEM___DF_DS_AKIMI, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xD220D,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Volcano - Sublevel Three (8)", []),
    Door("Volcano - Sublevel Three (10)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Three (10)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Three (10)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "Computer", 0x6C73E, [
            (Progress.EVENT___DRAKE_VOLCANO_S4_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
            ]),
        ]),
        requires = [],
        address = 0xD00C3,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Volcano - Sublevel Three (8)", []),
    Door("Volcano - Sublevel Three (9)", []),
    Door("Volcano - Sublevel Three (11)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Three (11)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Three (11)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Three (10)", []),
    Door("Volcano - Sublevel Four (1)", [Progress.EVENT___DRAKE_VOLCANO_S4_UNLOCKED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Four (1)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Four (1)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Three (11)", []),
    Door("Volcano - Sublevel Four (2)", []),
    Door("Volcano - Sublevel Four (6)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Four (2)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Four (2)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Four (1)", []),
    Door("Volcano - Sublevel Four (3)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Four (3)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Four (3)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Four (2)", []),
    Door("Volcano - Sublevel Four (4, Gold Naga boss room)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Four (4, Gold Naga boss room)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Four (4, Gold Naga boss room)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Serpent Scales",
        vanilla = Entity(Category.TALISMAN, "Serpent Scales", 0x6B3FE, [
            (Progress.ITEM___SERPENT_SCALES, []),
        ]),
        requires = [],
        address = 0xD26C7,
        hidden = True,
    ),
])
thisRegion.doors.extend([
    Door("Volcano - Sublevel Four (3)", []),
    Door("Volcano - Sublevel Four (5)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Four (5)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Four (5)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Four (4, Gold Naga boss room)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Four (6)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Four (6)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Four (1)", []),
    Door("Volcano - Sublevel Four (7)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Four (7)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Four (7)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Volcano - Sublevel Four (6)", []),
    Door("Volcano - Sublevel Four (8, Drake boss room)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Four (8, Drake boss room)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Four (8, Drake boss room)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Drake",
        vanilla = Entity(Category.CONSTANT, "Drake", 0x6C4A5, [
            (Progress.EVENT___DRAKE_DEFEATED, [Progress.ITEM___JESTER_SPIRIT_INSIGNIA]),
        ]),
        requires = [],
        address = 0xD03C9,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Volcano - Sublevel Four (7)", []),
    Door("Volcano - Sublevel Four (9)", [Progress.EVENT___DRAKE_DEFEATED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Volcano - Sublevel Four (9)
# ------------------------------------------------------------------------
regionName = "Volcano - Sublevel Four (9)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Scientist (Professor Pushkin)",
        vanilla = Entity(Category.CONSTANT, "Scientist (Professor Pushkin)", 0x6B4E5, [
            # In vanilla, Professor Pushkin doesn't teach the
            # "Head Computer" keyword. We're teaching it here
            # automatically to avoid a possible softlock.
            # In vanilla, Professor Pushkin gives you the
            # Aneki Password here.
            (Progress.KEYWORD___HEAD_COMPUTER,           []),
            (Progress.EVENT___PROFESSOR_PUSHKIN_RESCUED, [Progress.KEYWORD___HEAD_COMPUTER]),
        ]),
        requires = [],
        address = 0xD2773,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Volcano - Sublevel Four (8, Drake boss room)", []),
    Door("Drake Towers - Roof", [Progress.EVENT___PROFESSOR_PUSHKIN_RESCUED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Aneki Building - 1st Floor
# ------------------------------------------------------------------------
regionName = "Aneki Building - 1st Floor"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "Computer", 0x6C706, [
            # In vanilla, you need the Aneki Password to get
            # into this computer.
            (Progress.EVENT___ANEKI_BUILDING_2F_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
            ]),
        ]),
        requires = [],
        address = 0xD1E29,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Downtown - Aneki Street", []),
    Door("Aneki Building - 2nd Floor (center)", [Progress.EVENT___ANEKI_BUILDING_2F_UNLOCKED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Aneki Building - 2nd Floor (center)
# ------------------------------------------------------------------------
regionName = "Aneki Building - 2nd Floor (center)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Aneki Building - 1st Floor", []),
    Door("Aneki Building - 2nd Floor (right)", []),
    Door("Aneki Building - 2nd Floor (left)", []),
    Door("Aneki Building - 3rd Floor (center)", [Progress.EVENT___ANEKI_BUILDING_3F_UNLOCKED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Aneki Building - 2nd Floor (right)
# ------------------------------------------------------------------------
regionName = "Aneki Building - 2nd Floor (right)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "DF_AN-PAYMENT", 0x6C5E0, [
            (Progress.ITEM___DF_AN_PAYMENT, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xCB929,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "Computer", 0x6C729, [
            (Progress.EVENT___LEVEL_3_NODE_DEACTIVATED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
            ]),
        ]),
        requires = [],
        address = 0xD1185,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Aneki Building - 2nd Floor (center)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Aneki Building - 2nd Floor (left)
# ------------------------------------------------------------------------
regionName = "Aneki Building - 2nd Floor (left)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "Computer", 0x6C7DF, [
            (Progress.EVENT___ANEKI_BUILDING_3F_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
            ]),
        ]),
        requires = [],
        address = 0xD110B,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Aneki Building - 2nd Floor (center)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Aneki Building - 3rd Floor (center)
# ------------------------------------------------------------------------
regionName = "Aneki Building - 3rd Floor (center)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Aneki Building - 2nd Floor (center)", []),
    Door("Aneki Building - 3rd Floor (right)", []),
    Door("Aneki Building - 3rd Floor (left)", []),
    Door("Aneki Building - 4th Floor (center)", [Progress.EVENT___ANEKI_BUILDING_4F_UNLOCKED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Aneki Building - 3rd Floor (right)
# ------------------------------------------------------------------------
regionName = "Aneki Building - 3rd Floor (right)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    # TODO: Change to Category.ITEM, update datafile behaviour script to make it spawnable on map
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "DF_AN-ANTI-AI", 0x6C5E7, [
            (Progress.ITEM___DF_AN_ANTI_AI, []),
        ]),
        requires = [Progress.ITEM___CYBERDECK, Progress.EVENT___DATAJACK_REPAIRED],
        address = 0xCB92F,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Aneki Building - 3rd Floor (center)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Aneki Building - 3rd Floor (left)
# ------------------------------------------------------------------------
regionName = "Aneki Building - 3rd Floor (left)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "Computer", 0x6C6E3, [
            (Progress.EVENT___ANEKI_BUILDING_4F_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
                Progress.EVENT___LEVEL_3_NODE_DEACTIVATED,
            ]),
        ]),
        requires = [],
        address = 0xD1361,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Aneki Building - 3rd Floor (center)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Aneki Building - 4th Floor (center)
# ------------------------------------------------------------------------
regionName = "Aneki Building - 4th Floor (center)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Aneki Building - 3rd Floor (center)", []),
    Door("Aneki Building - 4th Floor (right)", []),
    Door("Aneki Building - 4th Floor (left)", []),
    Door("Aneki Building - 5th Floor (center)", [Progress.EVENT___ANEKI_BUILDING_5F_UNLOCKED]),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Aneki Building - 4th Floor (right)
# ------------------------------------------------------------------------
regionName = "Aneki Building - 4th Floor (right)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Aneki Building - 4th Floor (center)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Aneki Building - 4th Floor (left)
# ------------------------------------------------------------------------
regionName = "Aneki Building - 4th Floor (left)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Computer",
        vanilla = Entity(Category.CONSTANT, "Computer", 0x6C6EA, [
            (Progress.EVENT___ANEKI_BUILDING_5F_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
            ]),
        ]),
        requires = [],
        address = 0xD1473,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Aneki Building - 4th Floor (center)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Aneki Building - 5th Floor (center)
# ------------------------------------------------------------------------
regionName = "Aneki Building - 5th Floor (center)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Aneki Building - 4th Floor (center)", []),
    Door("Aneki Building - 5th Floor (right)", []),
    Door("Aneki Building - 5th Floor (left)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Aneki Building - 5th Floor (right)
# ------------------------------------------------------------------------
regionName = "Aneki Building - 5th Floor (right)"
thisRegion = Region(regionName)
thisRegion.doors.extend([
    Door("Aneki Building - 5th Floor (center)", []),
])
regions[regionName] = thisRegion

# ------------------------------------------------------------------------
# Aneki Building - 5th Floor (left)
# ------------------------------------------------------------------------
regionName = "Aneki Building - 5th Floor (left)"
thisRegion = Region(regionName)
thisRegion.locations.extend([
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "AI Computer",
        vanilla = Entity(Category.CONSTANT, "AI Computer", 0x6CBAC, [
            (Progress.EVENT___AI_COMPUTER_DESTROYED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
            ]),
        ]),
        requires = [],
        address = 0xD1567,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Aneki Building - 5th Floor (center)", []),
])
regions[regionName] = thisRegion



########################################################################
# GENERATE A WINNABLE SEED
########################################################################

def reachableSearch(inventory):
    root = regions["Root"]
    reachable = [root]
    frontier = deque()
    frontier.append(root)
    while frontier:
        region = frontier.popleft()
        for door in region.doors:
            if all(r in inventory for r in door.requires):
                destinationRegion = regions[door.destination]
                if destinationRegion not in reachable:
                    reachable.append(destinationRegion)
                    frontier.append(destinationRegion)
    return reachable

def sphereSearch():
    spheres = []
    inventory = []
    reachable = reachableSearch(inventory)

    while True:
        newSphere = []
        newInventory = []
        for region in reachable:
            for location in region.locations:
                if all(r in inventory for r in location.requires):
                    for prize, requires in location.current.progression:
                        if prize not in inventory and prize not in newInventory:
                            if all(r in inventory for r in requires):
                                newSphere.append((location, prize))
                                newInventory.append(prize)

        if not newInventory:
            break

        spheres.append(newSphere)
        inventory.extend(newInventory)
        reachable = reachableSearch(inventory)

    return spheres, inventory

#debugLocations = defaultdict(list)
#debugEntities = defaultdict(list)
#for region in regions.values():
#    for location in region.locations:
#        debugLocations[location.category].append(location)
#        debugEntities[location.vanilla.category].append(location.vanilla)
#print("DEBUG - Locations")
#for category, locationList in debugLocations.items():
#    print(f"DEBUG ---- {category} = {len(locationList)}")
#print("DEBUG - Entities")
#for category, entityList in debugEntities.items():
#    print(f"DEBUG ---- {category} = {len(entityList)}")

# Generate a winnable seed.
print("Generating...")
attemptNumber = 1
while True:
    # Generate a candidate seed.

    # Categorize the locations and entities.
    remainingLocations = defaultdict(list)
    remainingEntities = defaultdict(list)
    for region in regions.values():
        for location in region.locations:
            if location.category & Category.KEY_ITEM:
                remainingLocations[Category.KEY_ITEM].append(location)
            else:
                remainingLocations[location.category].append(location)
            if location.vanilla.category & Category.KEY_ITEM:
                remainingEntities[Category.KEY_ITEM].append(location.vanilla)
            else:
                remainingEntities[location.vanilla.category].append(location.vanilla)

    # Key items
    rng.shuffle(remainingLocations[Category.KEY_ITEM])
    rng.shuffle(remainingEntities[Category.KEY_ITEM])
    while remainingLocations[Category.KEY_ITEM] and remainingEntities[Category.KEY_ITEM]:
        poppedLocation = remainingLocations[Category.KEY_ITEM].pop()
        poppedEntity = remainingEntities[Category.KEY_ITEM].pop()
        poppedLocation.current = poppedEntity
    while remainingLocations[Category.KEY_ITEM]:
        poppedLocation = remainingLocations[Category.KEY_ITEM].pop()
        if poppedLocation.category & Category.PHYSICAL:
            remainingLocations[Category.PHYSICAL_ITEM].append(poppedLocation)
        else:
            remainingLocations[Category.ITEM].append(poppedLocation)
    while remainingEntities[Category.KEY_ITEM]:
        poppedEntity = remainingEntities[Category.KEY_ITEM].pop()
        if poppedEntity.category & Category.PHYSICAL:
            remainingEntities[Category.PHYSICAL_ITEM].append(poppedEntity)
        else:
            remainingEntities[Category.ITEM].append(poppedEntity)

    # Early weapons
    rng.shuffle(remainingLocations[Category.EARLY_WEAPON])
    rng.shuffle(remainingEntities[Category.EARLY_WEAPON])
    while remainingLocations[Category.EARLY_WEAPON] and remainingEntities[Category.EARLY_WEAPON]:
        poppedLocation = remainingLocations[Category.EARLY_WEAPON].pop()
        poppedEntity = remainingEntities[Category.EARLY_WEAPON].pop()
        poppedLocation.current = poppedEntity
    remainingLocations[Category.WEAPON].extend(remainingLocations[Category.EARLY_WEAPON])
    remainingLocations[Category.EARLY_WEAPON].clear()
    remainingEntities[Category.WEAPON].extend(remainingEntities[Category.EARLY_WEAPON])
    remainingEntities[Category.EARLY_WEAPON].clear()

    # Weapons
    rng.shuffle(remainingLocations[Category.WEAPON])
    rng.shuffle(remainingEntities[Category.WEAPON])
    while remainingLocations[Category.WEAPON] and remainingEntities[Category.WEAPON]:
        poppedLocation = remainingLocations[Category.WEAPON].pop()
        poppedEntity = remainingEntities[Category.WEAPON].pop()
        poppedLocation.current = poppedEntity
    remainingLocations[Category.WEAPON_OR_ARMOR].extend(remainingLocations[Category.WEAPON])
    remainingLocations[Category.WEAPON].clear()
    remainingEntities[Category.WEAPON_OR_ARMOR].extend(remainingEntities[Category.WEAPON])
    remainingEntities[Category.WEAPON].clear()

    # Early armor
    rng.shuffle(remainingLocations[Category.EARLY_ARMOR])
    rng.shuffle(remainingEntities[Category.EARLY_ARMOR])
    while remainingLocations[Category.EARLY_ARMOR] and remainingEntities[Category.EARLY_ARMOR]:
        poppedLocation = remainingLocations[Category.EARLY_ARMOR].pop()
        poppedEntity = remainingEntities[Category.EARLY_ARMOR].pop()
        poppedLocation.current = poppedEntity
    remainingLocations[Category.ARMOR].extend(remainingLocations[Category.EARLY_ARMOR])
    remainingLocations[Category.EARLY_ARMOR].clear()
    remainingEntities[Category.ARMOR].extend(remainingEntities[Category.EARLY_ARMOR])
    remainingEntities[Category.EARLY_ARMOR].clear()

    # Armor
    rng.shuffle(remainingLocations[Category.ARMOR])
    rng.shuffle(remainingEntities[Category.ARMOR])
    while remainingLocations[Category.ARMOR] and remainingEntities[Category.ARMOR]:
        poppedLocation = remainingLocations[Category.ARMOR].pop()
        poppedEntity = remainingEntities[Category.ARMOR].pop()
        poppedLocation.current = poppedEntity
    remainingLocations[Category.WEAPON_OR_ARMOR].extend(remainingLocations[Category.ARMOR])
    remainingLocations[Category.ARMOR].clear()
    remainingEntities[Category.WEAPON_OR_ARMOR].extend(remainingEntities[Category.ARMOR])
    remainingEntities[Category.ARMOR].clear()

    # Weapons or armor
    rng.shuffle(remainingLocations[Category.WEAPON_OR_ARMOR])
    rng.shuffle(remainingEntities[Category.WEAPON_OR_ARMOR])
    while remainingLocations[Category.WEAPON_OR_ARMOR] and remainingEntities[Category.WEAPON_OR_ARMOR]:
        poppedLocation = remainingLocations[Category.WEAPON_OR_ARMOR].pop()
        poppedEntity = remainingEntities[Category.WEAPON_OR_ARMOR].pop()
        poppedLocation.current = poppedEntity
    remainingLocations[Category.ITEM].extend(remainingLocations[Category.WEAPON_OR_ARMOR])
    remainingLocations[Category.WEAPON_OR_ARMOR].clear()
    remainingEntities[Category.ITEM].extend(remainingEntities[Category.WEAPON_OR_ARMOR])
    remainingEntities[Category.WEAPON_OR_ARMOR].clear()

    # Talismans
    rng.shuffle(remainingLocations[Category.TALISMAN])
    rng.shuffle(remainingEntities[Category.TALISMAN])
    while remainingLocations[Category.TALISMAN] and remainingEntities[Category.TALISMAN]:
        poppedLocation = remainingLocations[Category.TALISMAN].pop()
        poppedEntity = remainingEntities[Category.TALISMAN].pop()
        poppedLocation.current = poppedEntity
    remainingLocations[Category.ITEM].extend(remainingLocations[Category.TALISMAN])
    remainingLocations[Category.TALISMAN].clear()
    remainingEntities[Category.ITEM].extend(remainingEntities[Category.TALISMAN])
    remainingEntities[Category.TALISMAN].clear()

    # Physical items
    rng.shuffle(remainingLocations[Category.PHYSICAL_ITEM])
    rng.shuffle(remainingEntities[Category.PHYSICAL_ITEM])
    while remainingLocations[Category.PHYSICAL_ITEM] and remainingEntities[Category.PHYSICAL_ITEM]:
        poppedLocation = remainingLocations[Category.PHYSICAL_ITEM].pop()
        poppedEntity = remainingEntities[Category.PHYSICAL_ITEM].pop()
        poppedLocation.current = poppedEntity
    # Remaining "physical item" locations become "generic item" locations
    remainingLocations[Category.ITEM].extend(remainingLocations[Category.PHYSICAL_ITEM])
    remainingLocations[Category.PHYSICAL_ITEM].clear()
    # Remaining "physical item" entities should not happen
    if remainingEntities[Category.PHYSICAL_ITEM]:
        raise Exception("Could not place a 'Category.PHYSICAL_ITEM' entity")

    # Generic items
    rng.shuffle(remainingLocations[Category.ITEM])
    rng.shuffle(remainingEntities[Category.ITEM])
    while remainingLocations[Category.ITEM] and remainingEntities[Category.ITEM]:
        poppedLocation = remainingLocations[Category.ITEM].pop()
        poppedEntity = remainingEntities[Category.ITEM].pop()
        poppedLocation.current = poppedEntity
    # Remaining "generic item" locations and entities should not happen
    if remainingLocations[Category.ITEM]:
        raise Exception("Could not fill a 'Category.ITEM' location")
    if remainingEntities[Category.ITEM]:
        raise Exception("Could not place a 'Category.ITEM' entity")

    # NPCs
    rng.shuffle(remainingLocations[Category.NPC])
    rng.shuffle(remainingEntities[Category.NPC])
    while remainingLocations[Category.NPC] and remainingEntities[Category.NPC]:
        poppedLocation = remainingLocations[Category.NPC].pop()
        poppedEntity = remainingEntities[Category.NPC].pop()
        poppedLocation.current = poppedEntity
    # Remaining "NPC" locations and entities should not happen
    if remainingLocations[Category.NPC]:
        raise Exception("Could not fill a 'Category.NPC' location")
    if remainingEntities[Category.NPC]:
        raise Exception("Could not place a 'Category.NPC' entity")

    # Check if the candidate seed is winnable.
    # Any seed with "EVENT___GAME_COMPLETED" in the inventory after the
    # sphere search is technically winnable, but that doesn't guarantee
    # that everything will be reachable. So instead, we consider a seed
    # winnable only if 100% completion is possible.
    spheres, inventory = sphereSearch()
    if all(p in inventory for p in Progress):
        print(f"Generated a winnable seed on attempt #{attemptNumber}")
        print()
        break

    attemptNumber += 1

# Optional: Print the spoiler log.
if args.spoiler_log:
    for i, sphere in enumerate(spheres):
        print(f"Sphere {i}")
        for location, prize in sphere:
            print(f"{location.region.name:<60}   {location.description:<30} --> {prize.name}")
        print()

# If there's no input file (only possible in dry-run mode), exit.
# There's nothing more we can do.
if args.input_file is None:
    sys.exit()



########################################################################
# APPLY THE CHANGES TO THE ROM
########################################################################

# Helper function for writing blocks of bytes.
def writeHelper(buffer, offset, data):
    nextOffset = offset + len(data)
    buffer[offset:nextOffset] = data
    return nextOffset

# Helper function for replacing entire behaviour scripts.
def scriptHelper(scriptNumber, argsLen, returnLen, offset, scratchLen, maxStackLen, commandList):
    #print(f"DEBUG - Writing script {scriptNumber:3X} to offset {offset:X}")
    #if romBytes[0x16810 + scriptNumber] != argsLen:
    #    print(f"DEBUG ---- argsLen: {romBytes[0x16810 + scriptNumber]:02X} --> {argsLen:02X}")
    #if romBytes[0x16468 + scriptNumber] != returnLen:
    #    print(f"DEBUG ---- returnLen: {romBytes[0x16468 + scriptNumber]:02X} --> {returnLen:02X}")
    romBytes[0x16810 + scriptNumber] = argsLen
    romBytes[0x16468 + scriptNumber] = returnLen
    loromBank = 0x80 | (offset // 0x8000)
    romBytes[0x15970 + scriptNumber] = loromBank
    loromOffset = 0x8000 | (offset % 0x8000)
    struct.pack_into("<H", romBytes, 0x15D18 + (2 * scriptNumber), loromOffset)
    romBytes[offset + 0] = scratchLen
    romBytes[offset + 1] = maxStackLen
    nextOffset = writeHelper(romBytes, offset + 2, bytes.fromhex(' '.join(commandList)))
    return nextOffset

# Add four empty 32 KiB banks to the end of the ROM.
romBytes.extend([0x00] * (4 * 0x8000))
romBytes[0x7FD7] = 0x0B

# Write the new entity IDs.
for region in regions.values():
    for location in region.locations:
        if location.category != Category.CONSTANT:
            entityID = struct.pack("<H", location.current.entityAddress - 0x6B031)
            writeHelper(romBytes, location.address, entityID)

# Set the 0x80 flag for all visible (i.e. not hidden) randomized items.
# In vanilla, the 0x80 flag would start clear for all items, and only
# be set on hidden items when they became visible. Always-visible items
# would ignore the flag entirely, and initially-hidden items would wait
# for the flag to become set before drawing their sprite.
# With randomization, we don't know which items will be in "initially
# hidden" locations, so every item needs to check the 0x80 flag.
# (The new item-drawing script takes care of this.)
# Since every item is now checking the 0x80 flag, we need to set it for
# items in "always visible" locations, otherwise they'll start out
# hidden and remain that way indefinitely.
for region in regions.values():
    for location in region.locations:
        if location.category != Category.CONSTANT:
            memoryPointer = struct.unpack_from("<H", romBytes, location.current.entityAddress + 1)[0]
            if memoryPointer != 0:
                memoryPointer -= 0x2E00
                if not location.hidden:
                    initialItemState[memoryPointer + 1] |= 0x80

# Rewrite the 00/FE8B "print text in a window" function.
# 00/FE8B is the code behind the [58 C7] "print text in a window" command
# in behaviour script. The rewrite is to save a few bytes, which we will
# immediately spend to set $00 to the text-window-slot number used by the
# window we've just created.
# This rewrite will have no effect on [58 C7], since that command doesn't
# return any stack items upon completion.
# So why are we doing this? The plan is to repoint some other (currently
# unused) command to 00/FE8B, to create a new command that behaves like
# [58 C7] but also returns the text-window-slot number. This new command
# will help us create text windows with dynamic content.
writeHelper(romBytes, 0x7E8B, bytes.fromhex(' '.join([
    "A5 08",    # 00/FE8B: LDA $08
    "C9 00 04", # 00/FE8D: CMP #$0400
    "D0 06",    # 00/FE90: BNE $FE98
    "A9 1E 00", # 00/FE92: LDA #$001E
    "8D 1E 02", # 00/FE95: STA $021E
    "20 2D F9", # 00/FE98: JSR $F92D   ; Create the text window
    "A5 00",    # 00/FE9B: LDA $00     ; $00 = "text-window-slot" number
    "48",       # 00/FE9D: PHA
    "A5 0A",    # 00/FE9E: LDA $0A     ; $0A = "text-id" argument
    "0A",       # 00/FEA0: ASL
    "AA",       # 00/FEA1: TAX
    "BD 80 D9", # 00/FEA2: LDA $D980,X ; Load the corresponding text pointer
    "85 02",    # 00/FEA5: STA $02
    "20 33 FE", # 00/FEA7: JSR $FE33   ; Print the text to the window
    "A2 06 00", # 00/FEAA: LDX #$0006  ; Set up the "duration" countdown
    "A9 FF FF", # 00/FEAD: LDA #$FFFF  ; (Amount of time window is on screen)
    "48",       # 00/FEB0: PHA
    "BD 32 02", # 00/FEB1: LDA $0232,X
    "30 1A",    # 00/FEB4: BMI $FED0
    "68",       # 00/FEB6: PLA
    "DD 3A 02", # 00/FEB7: CMP $023A,X
    "90 04",    # 00/FEBA: BCC $FEC0
    "BD 3A 02", # 00/FEBC: LDA $023A,X
    "9B",       # 00/FEBF: TXY
    "CA",       # 00/FEC0: DEX
    "CA",       # 00/FEC1: DEX
    "10 EC",    # 00/FEC2: BPL $FEB0
    "48",       # 00/FEC4: PHA
    "BB",       # 00/FEC5: TYX
    "BD 32 02", # 00/FEC6: LDA $0232,X
    "85 00",    # 00/FEC9: STA $00
    "DA",       # 00/FECB: PHX
    "20 08 FA", # 00/FECC: JSR $FA08   ; Erase an existing window if necessary
    "FA",       # 00/FECF: PLX
    "A5 0C",    # 00/FED0: LDA $0C     ; $0C = "duration" argument
    "9D 3A 02", # 00/FED2: STA $023A,X
    "68",       # 00/FED5: PLA
    "68",       # 00/FED6: PLA
    "9D 32 02", # 00/FED7: STA $0232,X
    "85 00",    # 00/FEDA: STA $00     ; $00 = "text-window-slot" number
    "60",       # 00/FEDC: RTS
])))

# Repoint [58 3D] to 00/FE8B.
# [58 3D] is a behaviour script command that draws a text window and
# returns the "text-window-slot" number of the window it just created.
# [58 3D] is never used in behaviour script, though the underlying
# function that makes it work (at 00/F92D) does get called upon by
# other code.
# (For example, the [58 C7] code above invokes it as a subroutine.)
# So we can't change that code safely, but repointing [58 3D] is fine.
# With this repointing, [58 3D] behaves like [58 C7] (same arguments),
# but additionally returns the "text-window-slot" number. This will
# help us create text windows with dynamic content.
struct.pack_into("<H", romBytes, 0x15604 + (2 * 0x3D), 0xFE8B)
# Command [58 3D] now takes 7 stack items as arguments instead of 5.
romBytes[0x15895 + 0x3D] = 0x07
# Command [58 3D] now returns 2 bytes (= 1 stack item) upon completion.
romBytes[0x157BA + 0x3D] = 0x02

# The sixth argument for [58 C7] (and now [58 3D]) is a text-id.
# Text-ids are indices into a table of short text pointers at 0x5980.
# We want a text-id that maps to the empty string, so we can create
# empty text windows to later fill with dynamic content.
# No such text-id exists in vanilla, so let's repoint one that's not
# in use: 0x260, which corresponds to the "Winter CES'93" message.
# The new pointer destination will be the empty string at 0xE8765.
struct.pack_into("<H", romBytes, 0x5980 + (2 * 0x260), 0x0765)

# Repoint [58 53] to 00/FE33.
# It looks like [58 53] lets you set flags to apply text effects (e.g.
# bold, italics, underline, etc). It's never used in behaviour script,
# so I'm repointing it.
# 00/FE33 is a function that takes two arguments (a text-window-slot
# number and a text pointer), and prints the latter onto the former.
struct.pack_into("<H", romBytes, 0x15604 + (2 * 0x53), 0xFE33)
# Command [58 53] now takes 2 stack items as arguments.
romBytes[0x15895 + 0x53] = 0x02
# Command [58 53] now returns 0 bytes (= 0 stack items) upon completion.
romBytes[0x157BA + 0x53] = 0x00

# Repoint [58 0E] to 00/FA76.
# It looks like [58 0E] does... something related to text windows?
# It's never used in behaviour script, so I'm repointing it.
# 00/FA76 is a function that takes three arguments: a text-window-slot
# number, an X coordinate, and a Y coordinate. It sets the window's
# text cursor position to the given coordinates.
struct.pack_into("<H", romBytes, 0x15604 + (2 * 0x0E), 0xFA76)
# Command [58 0E] now takes 3 stack items as arguments.
romBytes[0x15895 + 0x0E] = 0x03
# Command [58 0E] now returns 0 bytes (= 0 stack items) upon completion.
romBytes[0x157BA + 0x0E] = 0x00

# Change the behaviour of [58 19].
# [58 19] takes an object-id, looks at the 0x66FB0 "appearance" entry
# for that object-id, and then pushes the third and fourth bytes of
# that entry as a short.
# [58 19] is never used in behaviour script, and even the underlying
# code at 00/CAC2 doesn't appear to be called by anything. On top of
# that, the third and fourth bytes are both zero for every entry in
# the 0x66FB0 table.
# So instead, let's make this command push the first and second bytes
# of the 0x66FB0 entry. Those hold the "mouseover description" short
# text pointer, which will be useful when randomizing the contents of
# glass cases in shops.
romBytes[0x4AD0] = 0xB0

# Use bank A0 (0x100000-0x107FFF) for rewritten behaviour scripts.
expandedOffset = 0x100000

# New item-drawing script.
# Items can be visible by default (e.g. Scalpel); visible after a flag is
# set (e.g. Tickets); or not visible at all (e.g. LoneStar Badge).
# The visibility behaviour is determined by the item's behaviour script,
# but the "expected by player" visibility behaviour depends on an item's
# location. (If an item is "inside" a filing cabinet, you don't expect to
# be able to see it until after you've looted the cabinet.)
# Since we don't know where any given item will end up after the location
# shuffle, each item needs to be able to handle all of the visibility
# behaviour cases. Hence, this script.
# Behaviour script 0x11D (the one containing the "Winter CES'93" message)
# isn't used by anything, so we can repurpose it safely.
# This script also writes the spawn-index of the object that's executing
# it to the first byte of said object's 7E2E00 data (which appears to be
# unused). This allows us to determine an object's current spawn-index
# from its object-id, which we need for randomization of objects dropped
# by non-stationary enemies (e.g. Leather Jacket, Ghoul Bone, Dog Tag,
# Serpent Scales).
expandedOffset = scriptHelper(
    scriptNumber = 0x11D,
    argsLen      = 0x02, # Script 0x11D now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x11D now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 21 00", # 0005: If yes, jump to 0021
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 9C",    # 000A: Write byte to first byte of object's 7E2E00 data <-- Spawn index
        # Wait until object's 0x80 flag is set
        # Based on behaviour script 0x101
        "00 01",    # 000C: Push unsigned byte 0x01
        "BA",       # 000E: Duplicate
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 0013: Push object's flags
        "00 80",    # 0015: Push unsigned byte 0x80
        "7E",       # 0017: Bitwise AND
        "BE",       # 0018: Convert to boolean
        "44 0C 00", # 0019: If false, jump to 000C
        # Display sprite with facing direction 00
        # Based on behaviour script 0x244
        "C0",       # 001C: Push zero
        "C0",       # 001D: Push zero
        "C2",       # 001E: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 001F: Display sprite with facing direction
        # End
        "56",       # 0021: End
    ],
)

# ------------------------------------------------------------------------
# Weapons
# ------------------------------------------------------------------------

# Zip-Gun
expandedOffset = scriptHelper(
    scriptNumber = 0x218,
    argsLen      = 0x02, # Script 0x218 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x218 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0A, # Header byte: Maximum stack height of 0x0A bytes (= 5 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 01",    # 001C: Push unsigned byte 0x01     1 = Strength required
        "00 00",    # 001E: Push unsigned byte 0x00     0 = Accuracy
        "00 03",    # 0020: Push unsigned byte 0x03     3 = Attack
        "00 06",    # 0022: Push unsigned byte 0x06     6 = Type (light)
        "C2",       # 0024: Push unsigned byte from $13+00 <-- Spawn index
        "52 11 00", # 0025: Execute behaviour script 0x11 = Common code for weapons
        "56",       # 0028: End
    ],
)
# Zip-Gun: Use the Beretta Pistol's sprite data (0xD420 --> 0xD052)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xB6), 0xD052)
# Zip-Gun: Increase the Zip-Gun's sprite priority
romBytes[0x6B031] |= 0x40

# Beretta Pistol
expandedOffset = scriptHelper(
    scriptNumber = 0x1BF,
    argsLen      = 0x02, # Script 0x1BF now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x1BF now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0A, # Header byte: Maximum stack height of 0x0A bytes (= 5 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 01",    # 001C: Push unsigned byte 0x01     1 = Strength required
        "00 01",    # 001E: Push unsigned byte 0x01     1 = Accuracy
        "00 03",    # 0020: Push unsigned byte 0x03     3 = Attack
        "00 06",    # 0022: Push unsigned byte 0x06     6 = Type (light)
        "C2",       # 0024: Push unsigned byte from $13+00 <-- Spawn index
        "52 11 00", # 0025: Execute behaviour script 0x11 = Common code for weapons
        "56",       # 0028: End
    ],
)
# Beretta Pistol: Change the behaviour script for Jetboy's Beretta Pistol
# from 0x34F (Colt L36 Pistol) to 0x1BF (Beretta Pistol).
# In vanilla, 0x1BF was a more complicated script to handle the Beretta
# in the alley, while 0x34F just specified weapon stats.
# The Beretta and the Colt L36 have the same stats, so it looks like the
# devs used the simpler script for Jetboy's gun as a shortcut.
struct.pack_into("<H", romBytes, 0x6C981, 0x01BF)

# Colt L36 Pistol
expandedOffset = scriptHelper(
    scriptNumber = 0x34F,
    argsLen      = 0x02, # Script 0x34F now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x34F now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0A, # Header byte: Maximum stack height of 0x0A bytes (= 5 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 01",    # 001C: Push unsigned byte 0x01     1 = Strength required
        "00 01",    # 001E: Push unsigned byte 0x01     1 = Accuracy
        "00 03",    # 0020: Push unsigned byte 0x03     3 = Attack
        "00 06",    # 0022: Push unsigned byte 0x06     6 = Type (light)
        "C2",       # 0024: Push unsigned byte from $13+00 <-- Spawn index
        "52 11 00", # 0025: Execute behaviour script 0x11 = Common code for weapons
        "56",       # 0028: End
    ],
)
# Colt L36 Pistol: Use the Beretta Pistol's sprite data (0xED8A --> 0xD052)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0x112), 0xD052)

# Fichetti L. Pistol
expandedOffset = scriptHelper(
    scriptNumber = 0x286,
    argsLen      = 0x02, # Script 0x286 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x286 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0A, # Header byte: Maximum stack height of 0x0A bytes (= 5 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 01",    # 001C: Push unsigned byte 0x01     1 = Strength required
        "00 01",    # 001E: Push unsigned byte 0x01     1 = Accuracy
        "00 04",    # 0020: Push unsigned byte 0x04     4 = Attack
        "00 06",    # 0022: Push unsigned byte 0x06     6 = Type (light)
        "C2",       # 0024: Push unsigned byte from $13+00 <-- Spawn index
        "52 11 00", # 0025: Execute behaviour script 0x11 = Common code for weapons
        "56",       # 0028: End
    ],
)
# Fichetti L. Pistol: Use the Beretta Pistol's sprite data (0xE018 --> 0xD052)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xCC), 0xD052)
# Fichetti L. Pistol: Increase the Fichetti L. Pistol's sprite priority
romBytes[0x6C324] |= 0x40

# Viper H. Pistol
expandedOffset = scriptHelper(
    scriptNumber = 0xAA,
    argsLen      = 0x02, # Script 0xAA now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0xAA now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0A, # Header byte: Maximum stack height of 0x0A bytes (= 5 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 02",    # 001C: Push unsigned byte 0x02     2 = Strength required
        "00 02",    # 001E: Push unsigned byte 0x02     2 = Accuracy
        "00 04",    # 0020: Push unsigned byte 0x04     4 = Attack
        "00 00",    # 0022: Push unsigned byte 0x00     0 = Type (heavy)
        "C2",       # 0024: Push unsigned byte from $13+00 <-- Spawn index
        "52 11 00", # 0025: Execute behaviour script 0x11 = Common code for weapons
        "56",       # 0028: End
    ],
)
# Viper H. Pistol: Use the Beretta Pistol's sprite data (0xD066 --> 0xD052)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xA9), 0xD052)

# Warhawk H. Pistol
expandedOffset = scriptHelper(
    scriptNumber = 0x29A,
    argsLen      = 0x02, # Script 0x29A now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x29A now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0A, # Header byte: Maximum stack height of 0x0A bytes (= 5 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 03",    # 001C: Push unsigned byte 0x03     3 = Strength required
        "00 02",    # 001E: Push unsigned byte 0x02     2 = Accuracy
        "00 06",    # 0020: Push unsigned byte 0x06     6 = Attack
        "00 00",    # 0022: Push unsigned byte 0x00     0 = Type (heavy)
        "C2",       # 0024: Push unsigned byte from $13+00 <-- Spawn index
        "52 11 00", # 0025: Execute behaviour script 0x11 = Common code for weapons
        "56",       # 0028: End
    ],
)
# Warhawk H. Pistol: Use the Beretta Pistol's sprite data (0xE02C --> 0xD052)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xCD), 0xD052)

# T-250 Shotgun
expandedOffset = scriptHelper(
    scriptNumber = 0x1F,
    argsLen      = 0x02, # Script 0x1F now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x1F now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0A, # Header byte: Maximum stack height of 0x0A bytes (= 5 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 04",    # 001C: Push unsigned byte 0x04     4 = Strength required
        "00 02",    # 001E: Push unsigned byte 0x02     2 = Accuracy
        "00 08",    # 0020: Push unsigned byte 0x08     8 = Attack
        "00 00",    # 0022: Push unsigned byte 0x00     0 = Type (heavy)
        "C2",       # 0024: Push unsigned byte from $13+00 <-- Spawn index
        "52 11 00", # 0025: Execute behaviour script 0x11 = Common code for weapons
        "56",       # 0028: End
    ],
)
# T-250 Shotgun: Use the Beretta Pistol's sprite data (0xD08E --> 0xD052)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xAB), 0xD052)

# Uzi III SMG
expandedOffset = scriptHelper(
    scriptNumber = 0x1A7,
    argsLen      = 0x02, # Script 0x1A7 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x1A7 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0A, # Header byte: Maximum stack height of 0x0A bytes (= 5 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 04",    # 001C: Push unsigned byte 0x04     4 = Strength required
        "00 03",    # 001E: Push unsigned byte 0x03     3 = Accuracy
        "00 08",    # 0020: Push unsigned byte 0x08     8 = Attack
        "00 01",    # 0022: Push unsigned byte 0x01     1 = Type (auto)
        "C2",       # 0024: Push unsigned byte from $13+00 <-- Spawn index
        "52 11 00", # 0025: Execute behaviour script 0x11 = Common code for weapons
        "56",       # 0028: End
    ],
)
# Uzi III SMG: Use the Beretta Pistol's sprite data (0xE97C --> 0xD052)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xEE), 0xD052)

# HK 277 A. Rifle
expandedOffset = scriptHelper(
    scriptNumber = 0x16C,
    argsLen      = 0x02, # Script 0x16C now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x16C now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0A, # Header byte: Maximum stack height of 0x0A bytes (= 5 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 05",    # 001C: Push unsigned byte 0x05     5 = Strength required
        "00 02",    # 001E: Push unsigned byte 0x02     2 = Accuracy
        "00 0A",    # 0020: Push unsigned byte 0x0A    10 = Attack
        "00 00",    # 0022: Push unsigned byte 0x00     0 = Type (heavy)
        "C2",       # 0024: Push unsigned byte from $13+00 <-- Spawn index
        "52 11 00", # 0025: Execute behaviour script 0x11 = Common code for weapons
        "56",       # 0028: End
    ],
)
# HK 277 A. Rifle: Use the Beretta Pistol's sprite data (0xD07A --> 0xD052)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xAA), 0xD052)

# AS-7 A. Cannon
expandedOffset = scriptHelper(
    scriptNumber = 0x315,
    argsLen      = 0x02, # Script 0x315 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x315 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0A, # Header byte: Maximum stack height of 0x0A bytes (= 5 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 05",    # 001C: Push unsigned byte 0x05     5 = Strength required
        "00 06",    # 001E: Push unsigned byte 0x06     6 = Accuracy
        "00 14",    # 0020: Push unsigned byte 0x14    20 = Attack
        "00 00",    # 0022: Push unsigned byte 0x00     0 = Type (heavy)
        "C2",       # 0024: Push unsigned byte from $13+00 <-- Spawn index
        "52 11 00", # 0025: Execute behaviour script 0x11 = Common code for weapons
        "56",       # 0028: End
    ],
)
# AS-7 A. Cannon: Use the Beretta Pistol's sprite data (0xE040 --> 0xD052)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xCE), 0xD052)
# AS-7 A. Cannon: Increase the AS-7 A. Cannon's sprite priority
romBytes[0x6CB90] |= 0x40

# ------------------------------------------------------------------------
# Armor
# ------------------------------------------------------------------------

# Leather Jacket
expandedOffset = scriptHelper(
    scriptNumber = 0x292,
    argsLen      = 0x02, # Script 0x292 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x292 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 01",    # 001C: Push unsigned byte 0x01     1 = Strength required
        "00 01",    # 001E: Push unsigned byte 0x01     1 = Defense
        "C2",       # 0020: Push unsigned byte from $13+00 <-- Spawn index
        "52 20 03", # 0021: Execute behaviour script 0x320 = Common code for armor
        "56",       # 0024: End
    ],
)

# Mesh Jacket
expandedOffset = scriptHelper(
    scriptNumber = 0x1A8,
    argsLen      = 0x02, # Script 0x1A8 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x1A8 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 02",    # 001C: Push unsigned byte 0x02     2 = Strength required
        "00 02",    # 001E: Push unsigned byte 0x02     2 = Defense
        "C2",       # 0020: Push unsigned byte from $13+00 <-- Spawn index
        "52 20 03", # 0021: Execute behaviour script 0x320 = Common code for armor
        "56",       # 0024: End
    ],
)

# Bulletproof Vest
expandedOffset = scriptHelper(
    scriptNumber = 0xA5,
    argsLen      = 0x02, # Script 0xA5 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0xA5 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 03",    # 001C: Push unsigned byte 0x03     3 = Strength required
        "00 03",    # 001E: Push unsigned byte 0x03     3 = Defense
        "C2",       # 0020: Push unsigned byte from $13+00 <-- Spawn index
        "52 20 03", # 0021: Execute behaviour script 0x320 = Common code for armor
        "56",       # 0024: End
    ],
)
# Bulletproof Vest: Use the Mesh Jacket's sprite data (0xE068 --> 0xE054)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xD0), 0xE054)

# Concealed Jacket
expandedOffset = scriptHelper(
    scriptNumber = 0x19C,
    argsLen      = 0x02, # Script 0x19C now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x19C now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 04",    # 001C: Push unsigned byte 0x04     4 = Strength required
        "00 04",    # 001E: Push unsigned byte 0x04     4 = Defense
        "C2",       # 0020: Push unsigned byte from $13+00 <-- Spawn index
        "52 20 03", # 0021: Execute behaviour script 0x320 = Common code for armor
        "56",       # 0024: End
    ],
)
# Concealed Jacket: Use the Mesh Jacket's sprite data (0xE07C --> 0xE054)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xD1), 0xE054)

# Partial Bodysuit
expandedOffset = scriptHelper(
    scriptNumber = 0x2BA,
    argsLen      = 0x02, # Script 0x2BA now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x2BA now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 05",    # 001C: Push unsigned byte 0x05     5 = Strength required
        "00 05",    # 001E: Push unsigned byte 0x05     5 = Defense
        "C2",       # 0020: Push unsigned byte from $13+00 <-- Spawn index
        "52 20 03", # 0021: Execute behaviour script 0x320 = Common code for armor
        "56",       # 0024: End
    ],
)
# Partial Bodysuit: Use the Mesh Jacket's sprite data (0xE090 --> 0xE054)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xD2), 0xE054)

# Full Bodysuit
expandedOffset = scriptHelper(
    scriptNumber = 0x1BE,
    argsLen      = 0x02, # Script 0x1BE now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x1BE now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 06",    # 001C: Push unsigned byte 0x06     6 = Strength required
        "00 06",    # 001E: Push unsigned byte 0x06     6 = Defense
        "C2",       # 0020: Push unsigned byte from $13+00 <-- Spawn index
        "52 20 03", # 0021: Execute behaviour script 0x320 = Common code for armor
        "56",       # 0024: End
    ],
)
# Full Bodysuit: Use the Mesh Jacket's sprite data (0xE0A4 --> 0xE054)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xD3), 0xE054)

# ------------------------------------------------------------------------
# Common code for glass cases
# ------------------------------------------------------------------------
# In vanilla, the flags for items in glass cases work like this:
# - The 0x01 flag of the glass case starts out clear, gets set
#   when you buy the item-inside-the-case, and can be cleared
#   again if you sell the item to someone.
# - The 0x01 flag of the item-inside-the-case is clear for items
#   that can be purchased right away, and is set for items that
#   become available after some event (e.g. some of the weapons
#   and armor at the Dark Blade shop) until the event occurs.
# - If either flag is set, you can't buy the item.
#
# Since we're randomizing what items are inside the glass cases,
# the 0x01 flag of the new item-inside-the-case might already be
# in use for some other purpose. So let's make the 0x02 flag of
# the glass case handle that behaviour instead.
expandedOffset = scriptHelper(
    scriptNumber = 0x28C,
    argsLen      = 0x0A, # Script 0x28C now takes 10 bytes (= 5 stack items) as arguments
    returnLen    = 0x00, # Script 0x28C now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x09, # Header byte: Script uses 0x09 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00  <-- Spawn index
        "34 01",    # 0002: Pop short to $13+01 <-- Text-id for description of item inside the case
        "34 03",    # 0004: Pop short to $13+03 <-- Price of item inside the case
        "34 05",    # 0006: Pop short to $13+05 <-- Object-id of item inside the case
        "2C 07",    # 0008: Pop byte to $13+07  <-- "Stackable" boolean for item inside the case
        # Display sprite
        "C0",       # 000A: Push zero
        "C0",       # 000B: Push zero
        "C2",       # 000C: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 000D: Display sprite with facing direction
        # TOP_OF_LOOP
        # Check the glass case's 0x01 flag.
        "C2",       # 000F: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 0010: Push object's flags
        "00 01",    # 0012: Push unsigned byte 0x01
        "7E",       # 0014: Bitwise AND
        "BE",       # 0015: Convert to boolean
        "44 2C 00", # 0016: If false, jump to FLAG_01_CLEAR
        # If the glass case's 0x01 flag is set, check if the item inside
        # the case is owned by 0x0BAD (vanilla owner-object for all items
        # sold by the player).
        "16 05",    # 0019: Push short from $13+05 <-- Object-id of item inside the case
        "58 CC",    # 001B: Push object's owner
        "14 AD 0B", # 001D: Push short 0x0BAD
        "AA",       # 0020: Check if equal
        "44 36 00", # 0021: If not equal, jump to OUT_OF_STOCK
        # If the item inside the case is owned by 0x0BAD (i.e. the player
        # sold that item to someone), clear the glass case's 0x01 flag
        # and jump to the "item in stock" case.
        "0A FE",    # 0024: Push signed byte 0xFE
        "C2",       # 0026: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 0027: Clear bits of object's flags
        "48 60 00", # 0029: Jump to IN_STOCK
        # FLAG_01_CLEAR
        # The glass case's 0x01 flag is clear.
        # Let's check the glass case's 0x02 flag.
        "C2",       # 002C: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 002D: Push object's flags
        "00 02",    # 002F: Push unsigned byte 0x02
        "7E",       # 0031: Bitwise AND
        "BE",       # 0032: Convert to boolean
        "44 60 00", # 0033: If false, jump to IN_STOCK
        # OUT_OF_STOCK
        "00 80",    # 0036: Push unsigned byte 0x80
        "C2",       # 0038: Push unsigned byte from $13+00 <-- Spawn index
        "58 CE",    # 0039: Set bits of 7E1474+n <-- Makes the case contents invisible
        "C0",       # 003B: Push zero
        "00 80",    # 003C: Push unsigned byte 0x80
        "58 9E",    # 003E: Register menu options / time delay
        "BC",       # 0040: Pop
        "58 A6",    # 0041: Erase all open text windows
        "00 02",    # 0043: Push unsigned byte 0x02
        "00 01",    # 0045: Push unsigned byte 0x01
        "58 9E",    # 0047: Register menu options / time delay
        "BC",       # 0049: Pop
        "00 F0",    # 004A: Push unsigned byte 0xF0
        "14 00 01", # 004C: Push short 0x0100
        "C0",       # 004F: Push zero
        "00 03",    # 0050: Push unsigned byte 0x03
        "00 0B",    # 0052: Push unsigned byte 0x0B <-- Was 0x0C
        "00 14",    # 0054: Push unsigned byte 0x14 <-- Was 0x12
        "00 05",    # 0056: Push unsigned byte 0x05 <-- Was 0x02
        "58 C7",    # 0058: Print text ("Out of stock:")
        "4C 23 01", # 005A: Execute SUBROUTINE_DESCRIBE_EXAMINE subroutine
        "48 0F 00", # 005D: Jump to TOP_OF_LOOP
        # IN_STOCK
        "C0",       # 0060: Push zero
        "00 A0",    # 0061: Push unsigned byte 0xA0
        "58 9E",    # 0063: Register menu options / time delay
        "58 A6",    # 0065: Erase all open text windows
        "00 02",    # 0067: Push unsigned byte 0x02
        "00 01",    # 0069: Push unsigned byte 0x01
        "58 9E",    # 006B: Register menu options / time delay
        "BC",       # 006D: Pop
        "00 80",    # 006E: Push unsigned byte 0x80
        "7E",       # 0070: Bitwise AND
        "BE",       # 0071: Convert to boolean
        "44 8A 00", # 0072: If false, jump to BUY
        # EXAMINE
        # Interaction menu option: Examine
        "00 F0",    # 0075: Push unsigned byte 0xF0
        "00 FF",    # 0077: Push unsigned byte 0xFF
        "C0",       # 0079: Push zero
        "00 03",    # 007A: Push unsigned byte 0x03
        "00 0D",    # 007C: Push unsigned byte 0x0D <-- Was 0x0E
        "00 14",    # 007E: Push unsigned byte 0x14 <-- Was 0x12
        "00 03",    # 0080: Push unsigned byte 0x03 <-- Was 0x02
        "58 C7",    # 0082: Print text ("Inside the case:")
        "4C 23 01", # 0084: Execute SUBROUTINE_DESCRIBE_EXAMINE subroutine
        "48 0F 00", # 0087: Jump to TOP_OF_LOOP
        # BUY
        # Interaction menu option: Buy
        "4C 10 01", # 008A: Execute SUBROUTINE_DESCRIBE_BUY subroutine
        "00 01",    # 008D: Push unsigned byte 0x01
        "00 15",    # 008F: Push unsigned byte 0x15
        "C0",       # 0091: Push zero
        "00 03",    # 0092: Push unsigned byte 0x03
        "00 06",    # 0094: Push unsigned byte 0x06
        "00 05",    # 0096: Push unsigned byte 0x05
        "00 15",    # 0098: Push unsigned byte 0x15
        "58 C7",    # 009A: Print text ("Buy?")
        "00 07",    # 009C: Push unsigned byte 0x07
        "00 17",    # 009E: Push unsigned byte 0x17
        "58 72",    # 00A0: Display Yes/No menu
        "58 A6",    # 00A2: Erase all open text windows
        "44 0F 00", # 00A4: If No/Cancel, jump to TOP_OF_LOOP
        # YES
        # Choose "Yes" when prompted to buy
        "16 03",    # 00A7: Push short from $13+03 <-- Price of item inside the case
        "58 BE",    # 00A9: Try to decrease nuyen
        "44 F5 00", # 00AB: If you don't have enough nuyen, jump to NOT_ENOUGH_NUYEN
        "16 05",    # 00AE: Push short from $13+05 <-- Object-id of item inside the case
        "58 C6",    # 00B0: Push object's quantity
        "00 06",    # 00B2: Push unsigned byte 0x06
        "8A",       # 00B4: Check if less than
        "46 D5 00", # 00B5: If you have less than six of the item, jump to QUANTITY_OK
        # QUANTITY_ALREADY_MAXED
        "00 02",    # 00B8: Push unsigned byte 0x02
        "00 01",    # 00BA: Push unsigned byte 0x01
        "58 9E",    # 00BC: Register menu options / time delay
        "BC",       # 00BE: Pop
        "00 78",    # 00BF: Push unsigned byte 0x78
        "00 25",    # 00C1: Push unsigned byte 0x25
        "C0",       # 00C3: Push zero
        "00 03",    # 00C4: Push unsigned byte 0x03
        "00 1C",    # 00C6: Push unsigned byte 0x1C
        "00 06",    # 00C8: Push unsigned byte 0x06
        "00 02",    # 00CA: Push unsigned byte 0x02
        "58 C7",    # 00CC: Print text ("You can't carry any more grenades!")
        "16 03",    # 00CE: Push short from $13+03 <-- Price of item inside the case
        "58 98",    # 00D0: Increase nuyen <-- Refund for failed purchase
        "48 0F 00", # 00D2: Jump to TOP_OF_LOOP
        # QUANTITY_OK
        "0C 07",    # 00D5: Push signed byte from $13+07 <-- "Stackable" boolean for item inside the case
        "44 E3 00", # 00D7: If false, jump to NOT_STACKABLE
        # STACKABLE
        # Add one to quantity
        "00 01",    # 00DA: Push unsigned byte 0x01
        "16 05",    # 00DC: Push short from $13+05 <-- Object-id of item inside the case
        "58 26",    # 00DE: Add amount to object's quantity (stackables)
        "48 E8 00", # 00E0: Jump to CHANGE_OWNERSHIP
        # NOT_STACKABLE
        # Set 0x01 bit of glass case to mark as purchased
        "00 01",    # 00E3: Push unsigned byte 0x01
        "C2",       # 00E5: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 00E6: Set bits of object's flags
        # CHANGE_OWNERSHIP
        # This is what puts the item in the player's inventory
        "14 B2 08", # 00E8: Push short 0x08B2 <-- Object-id for Jake
        "16 05",    # 00EB: Push short from $13+05 <-- Object-id of item inside the case
        "58 74",    # 00ED: Set object's owner
        "52 4B 00", # 00EF: Execute behaviour script 0x4B = "Got item" sound effect
        "48 0F 00", # 00F2: Jump to TOP_OF_LOOP
        # NOT_ENOUGH_NUYEN
        "00 02",    # 00F5: Push unsigned byte 0x02
        "00 01",    # 00F7: Push unsigned byte 0x01
        "58 9E",    # 00F9: Register menu options / time delay
        "BC",       # 00FB: Pop
        "00 F0",    # 00FC: Push unsigned byte 0xF0
        "00 02",    # 00FE: Push unsigned byte 0x02
        "14 00 04", # 0100: Push short 0x0400
        "00 03",    # 0103: Push unsigned byte 0x03
        "00 0F",    # 0105: Push unsigned byte 0x0F <-- Was 0x10
        "00 06",    # 0107: Push unsigned byte 0x06
        "00 09",    # 0109: Push unsigned byte 0x09 <-- Was 0x06
        "58 C7",    # 010B: Print text ("Not enough money!")
        "48 0F 00", # 010D: Jump to TOP_OF_LOOP
        # SUBROUTINE_DESCRIBE_BUY
        # Text window attributes
        "00 F0",    # 0110: Push unsigned byte 0xF0
        "14 60 02", # 0112: Push short 0x0260 <-- Text-id for "Winter CES'93", repointed to ""
        "14 00 04", # 0115: Push short 0x0400
        "00 04",    # 0118: Push unsigned byte 0x04
        "00 0E",    # 011A: Push unsigned byte 0x0E <-- Was 0x15
        "00 02",    # 011C: Push unsigned byte 0x02
        "00 09",    # 011E: Push unsigned byte 0x09 <-- Was 0x02
        "48 33 01", # 0120: Jump to SUBROUTINE_DESCRIBE_COMMON
        # SUBROUTINE_DESCRIBE_EXAMINE
        # Text window attributes
        "00 F0",    # 0123: Push unsigned byte 0xF0
        "14 60 02", # 0125: Push short 0x0260 <-- Text-id for "Winter CES'93", repointed to ""
        "14 00 08", # 0128: Push short 0x0800
        "00 04",    # 012B: Push unsigned byte 0x04
        "00 0E",    # 012D: Push unsigned byte 0x0E <-- Was 0x15
        "00 14",    # 012F: Push unsigned byte 0x14
        "00 10",    # 0131: Push unsigned byte 0x10 <-- Was 0x09
        # SUBROUTINE_DESCRIBE_COMMON
        # Create empty text window
        "58 3D",    # 0133: Print text, return text-window-slot number <-- Repurposed function!
        "2C 08",    # 0135: Pop byte to $13+08 <-- Text-window-slot number
        # Print item name
        "16 05",    # 0137: Push short from $13+05 <-- Object-id of item inside the case
        "58 19",    # 0139: Push object's hover-description pointer <-- Repurposed function!
        "02 08",    # 013B: Push unsigned byte from $13+08 <-- Text-window-slot number
        "58 53",    # 013D: Print text to window <-- Repurposed function!
        # Move text cursor
        "00 01",    # 013F: Push unsigned byte 0x01 <-- Y coordinate
        "00 00",    # 0141: Push unsigned byte 0x00 <-- X coordinate
        "02 08",    # 0143: Push unsigned byte from $13+08 <-- Text-window-slot number
        "58 0E",    # 0145: Set window's text cursor position <-- Repurposed function!
        # Print item price
        "C0",       # 0147: Push zero
        "16 03",    # 0148: Push short from $13+03 <-- Price of item inside the case
        "02 08",    # 014A: Push unsigned byte from $13+08 <-- Text-window-slot number
        "58 04",    # 014C: Print nuyen amount to window
        "50",       # 014E: Return
    ],
)

# Set the 0x02 flag on the "initially out of stock" glass cases.
# This is required to make those cases "initially out of stock"
# given the changes we've made to glass case behaviour.
# Since we don't set the flag for the Bulletproof Vest case, the
# item inside that case can be purchased at any time.
initialItemState[0x9F7] |= 0x02 # HK 277 A. Rifle  ($24,000)
initialItemState[0xA01] |= 0x02 # Concealed Jacket ($13,000)
initialItemState[0xA06] |= 0x02 # Partial Bodysuit ($20,000)
initialItemState[0xA3D] |= 0x02 # Full Bodysuit    ($30,000)
initialItemState[0xA42] |= 0x02 # AS-7 A. Cannon   ($40,000)

# Clear the 0x01 flag on the vanilla "initially out of stock" items.
# (Not strictly necessary, but cleaning this up feels tidier.)
initialItemState[0xA1A] &= ~0x01 # HK 277 A. Rifle
initialItemState[0xA1F] &= ~0x01 # Bulletproof Vest
initialItemState[0xA24] &= ~0x01 # Concealed Jacket
initialItemState[0xA29] &= ~0x01 # Partial Bodysuit
initialItemState[0xA33] &= ~0x01 # Full Bodysuit
initialItemState[0xA38] &= ~0x01 # AS-7 A. Cannon

# ------------------------------------------------------------------------
# Keyword-items and nuyen-items
# ------------------------------------------------------------------------
# Item randomization, on its own, produces seeds that are very linear
# and similar to vanilla. Progression is still gated by the chain of
# plot-significant keywords acquired through conversation.
# (i.e. "Dog", "Jester Spirit", "Bremerton", "Laughlyn", "Volcano".)
# To fix this, let's create some new "keyword" items, which will:
# - Be placed randomly as part of the item shuffle
# - Teach one plot-significant keyword when picked up
# To create these items, we'll have to repurpose existing objects.
# Since "Dog" is the first plot-significant keyword, let's start by
# repurposing the NPC that teaches you it: the "hmmm...." dog in the
# alley at Tenth Street.

# Change the "hmmm...." hover-description to "Keyword"
writeHelper(romBytes, 0xEEBA4, bytes.fromhex(' '.join([
    # "Keyword"
    "1C", # "K"  = 000111000
    "3B", # "ey" = 011101111
    "EC", # "wo" = 1011001100
    "C6", # "rd" = 0110011111
    "7F", # "\n" = 110010
    "20",
])))

# Change the "hmmm...." appearance so it uses the "Tickets" sprite
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0x30), 0xA46A)

# Create text strings for use by the new "keyword-item" script.
# Since the "hmmm...." dog's conversation will become inaccessible
# once the new script is in place, we can repurpose the bytes that
# currently contain that conversation's lines of text.
writeHelper(romBytes, 0xE8766, bytes.fromhex(' '.join([
    # Horizontal alignment fix: Start with a one-pixel-wide spacer
    "F7 DA", # "\x01" = 1111011111011010
    # "Keyword learned:"
    "1C", # "K"  = 000111000
    "3B", # "ey" = 011101111
    "EC", # "w"  = 101100111
    "E3", # "or" = 0001100
    "26", # "d " = 1001101
    "D5", # "le" = 10101011
    "FA", # "ar" = 11110101
    "EA", # "ne" = 11010101
    "85", # "d"  = 00001010
    "0A", # ":"  = 00010100000
    "0C", # "\n" = 110010
    "80",
])))
writeHelper(romBytes, 0xE8774, bytes.fromhex(' '.join([
    # "|Dog"
    "03", # "|"  = 000000111
    "84", # "Do" = 000010000
    "26", # "g"  = 10011000
    "32", # "\n" = 110010
])))
writeHelper(romBytes, 0xE8778, bytes.fromhex(' '.join([
    # "|Jester |Spirit"
    "03", # "|"  = 000000111
    "BE", # "J"  = 01111100011
    "3C", # "es" = 11000011
    "36", # "te" = 01101011
    "B9", # "r " = 1001111
    "E0", # "|"  = 000000111
    "75", # "S"  = 01011111
    "FA", # "p"  = 10100000
    "0E", # "ir" = 111010000
    "80", # "it" = 0000111
    "7C", # "\n" = 110010
    "80",
])))
writeHelper(romBytes, 0xE8784, bytes.fromhex(' '.join([
    # "|Bremerton"
    "03", # "|"  = 000000111
    "E9", # "B"  = 110100110
    "BF", # "re" = 1111110
    "06", # "me" = 0000110
    "15", # "rt" = 000101011
    "C2", # "on" = 1000010
    "C8", # "\n" = 110010
])))
writeHelper(romBytes, 0xE878B, bytes.fromhex(' '.join([
    # "|Laughlyn"
    "03", # "|"  = 000000111
    "F8", # "L"  = 111100010
    "8E", # "a"  = 00111011
    "CC", # "u"  = 0011000
    "41", # "gh" = 100000101
    "5D", # "ly" = 011101110
    "D5", # "n"  = 10101111
    "F9", # "\n" = 110010
    "00",
])))
writeHelper(romBytes, 0xE8794, bytes.fromhex(' '.join([
    # "|Volcano"
    "03", # "|"  = 000000111
    "B3", # "V"  = 0110011110
    "D3", # "ol" = 1001100110
    "31", # "ca" = 00100111
    "39", # "no" = 00110011
    "9E", # "\n" = 110010
    "40",
])))

# We need to free up some objects to create the new keyword-items.
# The "shadowrunner default equipment" objects look like they're only
# used to provide weapon/armor names on the status screen, so I think
# we can free some up by having the runners share objects.
# For now, let's make all of the runners with a default Mesh Jacket
# share Jangadance's Mesh Jacket (0x0857).
struct.pack_into("<H", romBytes, 0x1734, 0x0857) # Spatter
struct.pack_into("<H", romBytes, 0x173C, 0x0857) # Jetboy
struct.pack_into("<H", romBytes, 0x1744, 0x0857) # Norbert
struct.pack_into("<H", romBytes, 0x1754, 0x0857) # Anders
struct.pack_into("<H", romBytes, 0x177C, 0x0857) # Hamfist
struct.pack_into("<H", romBytes, 0x1784, 0x0857) # Orifice

# Next, we turn these freed objects into keyword-item objects.
# Set appearance to 0x0030: "hmmm...." appearance, which we changed
# to have a hover-description of "Keyword" and the "Tickets" sprite
# just now.
# Set behaviour script to 0x02C6: "hmmm...." dog's script, which
# will become the new "keyword-item" script in a moment.
# We'll also turn some into nuyen-item objects, by borrowing values
# from the "Nuyen dropped by Octopus" object.

# Free object
# Vanilla: Mesh Jacket (Orifice)
writeHelper(romBytes, 0x6B896, bytes.fromhex("FF 0C 3B 30 00 C6 02"))
# Free object
# Vanilla: Mesh Jacket (Norbert)
writeHelper(romBytes, 0x6B89D, bytes.fromhex("FF 16 3B 30 00 C6 02"))
# Keyword-item: Volcano
# Vanilla: Mesh Jacket (Anders)
writeHelper(romBytes, 0x6B8A4, bytes.fromhex("FF 2A 3B 30 00 C6 02"))
# Nuyen-item: Vampire
# Vanilla: Mesh Jacket (Looks unused)
writeHelper(romBytes, 0x6B8AB, bytes.fromhex("FF 39 3B 9E 00 D6 00"))
# Keyword-item: Laughlyn
# Vanilla: Mesh Jacket (Hamfist)
writeHelper(romBytes, 0x6B8B2, bytes.fromhex("FF 52 3B 30 00 C6 02"))
# Keyword-item: Bremerton
# Vanilla: Vladimir
writeHelper(romBytes, 0x6B17A, bytes.fromhex("FF 43 36 30 00 C6 02"))
# Nuyen-item: Rat Shaman
# Vanilla: Mesh Jacket (Spatter)
writeHelper(romBytes, 0x6B8B9, bytes.fromhex("FF FD 3A 9E 00 D6 00"))
# Keyword-item: Jester Spirit
# Vanilla: Mesh Jacket (Jetboy)
writeHelper(romBytes, 0x6B8C0, bytes.fromhex("FF 34 3B 30 00 C6 02"))
# Nuyen-item: Glutman
# Vanilla: "Shady character..." (Glutman)
writeHelper(romBytes, 0x6B3F0, bytes.fromhex("FF FA 2E 9E 00 D6 00"))
# Keyword-item: Dog
# Vanilla: "hmmm...." (Dog in alley)
writeHelper(romBytes, 0x6BC16, bytes.fromhex("FF 1D 2F 30 00 C6 02"))

# Replace the "hmmm...." dog's script with the new "keyword-item" script
expandedOffset = scriptHelper(
    scriptNumber = 0x2C6,
    argsLen      = 0x02, # Script 0x2C6 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x2C6 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x07, # Header byte: Script uses 0x07 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 CB",    # 0003: Push object-id
        "34 01",    # 0005: Pop short to $13+01 <-- Object-id of the keyword-item executing this code
        # CHECK_IF_DOG
        "16 01",    # 0007: Push short from $13+01 <-- Object-id of the keyword-item executing this code
        "14 E5 0B", # 0009: Push short 0x0BE5      <-- Object-id of keyword-item: Dog
        "AA",       # 000C: Check if equal
        "44 1C 00", # 000D: If not equal, jump to CHECK_IF_JESTER_SPIRIT
        # DOG
        "00 0D",    # 0010: Push unsigned byte 0x0D <-- Keyword-id for "Dog"
        "2C 03",    # 0012: Pop byte to $13+03      <-- Keyword-id
        "14 74 07", # 0014: Push short 0x0774       <-- Text pointer for "|Dog"
        "34 04",    # 0017: Pop short to $13+04     <-- Text pointer for bolded keyword
        "48 6D 00", # 0019: Jump to CHECK_IF_KEYWORD_KNOWN
        # CHECK_IF_JESTER_SPIRIT
        "16 01",    # 001C: Push short from $13+01 <-- Object-id of the keyword-item executing this code
        "14 8F 08", # 001E: Push short 0x088F      <-- Object-id of keyword-item: Jester Spirit
        "AA",       # 0021: Check if equal
        "44 31 00", # 0022: If not equal, jump to CHECK_IF_BREMERTON
        # JESTER_SPIRIT
        "00 19",    # 0025: Push unsigned byte 0x19 <-- Keyword-id for "Jester Spirit"
        "2C 03",    # 0027: Pop byte to $13+03      <-- Keyword-id
        "14 78 07", # 0029: Push short 0x0778       <-- Text pointer for "|Jester |Spirit"
        "34 04",    # 002C: Pop short to $13+04     <-- Text pointer for bolded keyword
        "48 6D 00", # 002E: Jump to CHECK_IF_KEYWORD_KNOWN
        # CHECK_IF_BREMERTON
        "16 01",    # 0031: Push short from $13+01 <-- Object-id of the keyword-item executing this code
        "14 49 01", # 0033: Push short 0x0149      <-- Object-id of keyword-item: Bremerton
        "AA",       # 0036: Check if equal
        "44 46 00", # 0037: If not equal, jump to CHECK_IF_LAUGHLYN
        # BREMERTON
        "00 04",    # 003A: Push unsigned byte 0x04 <-- Keyword-id for "Bremerton"
        "2C 03",    # 003C: Pop byte to $13+03      <-- Keyword-id
        "14 84 07", # 003E: Push short 0x0784       <-- Text pointer for "|Bremerton"
        "34 04",    # 0041: Pop short to $13+04     <-- Text pointer for bolded keyword
        "48 6D 00", # 0043: Jump to CHECK_IF_KEYWORD_KNOWN
        # CHECK_IF_LAUGHLYN
        "16 01",    # 0046: Push short from $13+01 <-- Object-id of the keyword-item executing this code
        "14 81 08", # 0048: Push short 0x0881      <-- Object-id of keyword-item: Laughlyn
        "AA",       # 004B: Check if equal
        "44 5B 00", # 004C: If not equal, jump to CHECK_IF_VOLCANO
        # LAUGHLYN
        "00 1C",    # 004F: Push unsigned byte 0x1C <-- Keyword-id for "Laughlyn"
        "2C 03",    # 0051: Pop byte to $13+03      <-- Keyword-id
        "14 8B 07", # 0053: Push short 0x078B       <-- Text pointer for "|Laughlyn"
        "34 04",    # 0056: Pop short to $13+04     <-- Text pointer for bolded keyword
        "48 6D 00", # 0058: Jump to CHECK_IF_KEYWORD_KNOWN
        # CHECK_IF_VOLCANO
        "16 01",    # 005B: Push short from $13+01 <-- Object-id of the keyword-item executing this code
        "14 73 08", # 005D: Push short 0x0873      <-- Object-id of keyword-item: Volcano
        "AA",       # 0060: Check if equal
        "44 AE 00", # 0061: If not equal, jump to DONE
        # VOLCANO
        "00 3F",    # 0064: Push unsigned byte 0x3F <-- Keyword-id for "Volcano"
        "2C 03",    # 0066: Pop byte to $13+03      <-- Keyword-id
        "14 94 07", # 0068: Push short 0x0794       <-- Text pointer for "|Volcano"
        "34 04",    # 006B: Pop short to $13+04     <-- Text pointer for bolded keyword
        # CHECK_IF_KEYWORD_KNOWN
        "02 03",    # 006D: Push unsigned byte from $13+03 <-- Keyword-id
        "58 97",    # 006F: Check if keyword known
        "46 AE 00", # 0071: If yes, jump to DONE
        # SPAWN_KEYWORD_ITEM
        "C2",       # 0074: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0075: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 0078: Push zero
        "00 10",    # 0079: Push unsigned byte 0x10
        "58 9E",    # 007B: Register menu options / time delay
        "BC",       # 007D: Pop
        # PICKUP
        # Play the sound effect and learn the keyword
        "52 4B 00", # 007E: Execute behaviour script 0x4B = "Got item" sound effect
        "02 03",    # 0081: Push unsigned byte from $13+03 <-- Keyword-id for object executing this code
        "58 71",    # 0083: Learn keyword
        # Text window attributes
        "00 F0",    # 0085: Push unsigned byte 0xF0
        "14 60 02", # 0087: Push short 0x0260 <-- Text-id for "Winter CES'93", repointed to ""
        "14 00 08", # 008A: Push short 0x0800
        "00 04",    # 008D: Push unsigned byte 0x04
        "00 0E",    # 008F: Push unsigned byte 0x0E
        "00 14",    # 0091: Push unsigned byte 0x14
        "00 09",    # 0093: Push unsigned byte 0x09
        # Create empty text window
        "58 3D",    # 0095: Print text, return text-window-slot number <-- Repurposed function!
        "2C 06",    # 0097: Pop byte to $13+06 <-- Text-window-slot number
        # Print the "keyword learned" line
        "14 66 07", # 0099: Push short 0x0766 <-- Text pointer for "Keyword learned:"
        "02 06",    # 009C: Push unsigned byte from $13+06 <-- Text-window-slot number
        "58 53",    # 009E: Print text to window <-- Repurposed function!
        # Move text cursor
        "00 01",    # 00A0: Push unsigned byte 0x01 <-- Y coordinate
        "00 00",    # 00A2: Push unsigned byte 0x00 <-- X coordinate
        "02 06",    # 00A4: Push unsigned byte from $13+06 <-- Text-window-slot number
        "58 0E",    # 00A6: Set window's text cursor position <-- Repurposed function!
        # Print the keyword
        "16 04",    # 00A8: Push short from $13+04 <-- Text pointer for bolded keyword
        "02 06",    # 00AA: Push unsigned byte from $13+06 <-- Text-window-slot number
        "58 53",    # 00AC: Print text to window <-- Repurposed function!
        # DONE
        "C2",       # 00AE: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 00AF: Despawn object
        "56",       # 00B1: End
    ],
)

# Update the nuyen-item script to use the new item-drawing script
writeHelper(romBytes, 0xF88F4, bytes.fromhex(' '.join([
    "52 1D 01", # 0003: Execute behaviour script 0x11D = New item-drawing script
    "48 0B 00", # 0006: Jump to 000B
])))
# Increase amount from 2,000 to 3,000 nuyen
writeHelper(romBytes, 0xF8907, bytes.fromhex(' '.join([
    "14 F4 01", # 0016: Push short 0x01F4 <-- Text-id for "3,000 nuyen." (was 0x01F5)
])))
writeHelper(romBytes, 0xF8913, bytes.fromhex(' '.join([
    "00 0B",    # 0022: Push unsigned byte 0x0B <-- X coordinate of text window (was 0x0A)
])))
writeHelper(romBytes, 0xF8917, bytes.fromhex(' '.join([
    "14 B8 0B", # 0026: Push short 0x0BB8 <-- Amount of nuyen (was 0x07D0)
])))

# ------------------------------------------------------------------------
# Items and NPCs
# ------------------------------------------------------------------------

# TODO:
# Standardize text window placement?
# "Examine" text windows should be left-aligned (X = 0x02)
# The sum of Y and height should be 0x18
# (e.g. Y = 0x15 + single-line window with height 0x03 = 0x18)
# For taller windows, reduce Y and increase height
# (e.g. "Memo" item with Y = 0x13 + height 0x05 = 0x18)
# "Action" text should be centered: 2*X + width = 0x20
# ("Action" examples: "The key won't fit", "It won't budge.")
# When width is odd, the sum should be 0x21

# Mortician (Larry)
# Skip most of the vanilla new-game cutscene
expandedOffset = scriptHelper(
    scriptNumber = 0x278,
    argsLen      = 0x02, # Script 0x278 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x278 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x0B, # Header byte: Script uses 0x0B bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        # Copy 0000-01CD from the original script
        romBytes[0x1E926:0x1EAF4].hex(' '),
        # Spawn Larry at his vanilla "end of new-game cutscene" position
        "00 05",    # 01CE: Push unsigned byte 0x05
        "C2",       # 01D0: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 01D1: Move object instantly to waypoint?
        "00 01",    # 01D3: Push unsigned byte 0x01
        "C0",       # 01D5: Push zero
        "C2",       # 01D6: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 01D7: Display sprite with facing direction
        # Set Larry's "new-game cutscene completed" (0x01) flag
        "00 01",    # 01D9: Push unsigned byte 0x01
        "C2",       # 01DB: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 01DC: Set bits of object's flags
        # WAIT_FOR_SCARE
        "00 05",    # 01DE: Push unsigned byte 0x05
        "00 01",    # 01E0: Push unsigned byte 0x01
        "58 9E",    # 01E2: Register menu options / time delay
        "BC",       # 01E4: Pop
        "C2",       # 01E5: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 01E6: Push object's flags
        "00 02",    # 01E8: Push unsigned byte 0x02
        "7E",       # 01EA: Bitwise AND
        "BE",       # 01EB: Convert to boolean
        "44 DE 01", # 01EC: If false, jump to WAIT_FOR_SCARE
        # Copy 02B8-02F4 from the original script
        romBytes[0x1EBDE:0x1EC1B].hex(' '),
    ],
)

# Mortician (Sam)
# Skip most of the vanilla new-game cutscene
expandedOffset = scriptHelper(
    scriptNumber = 0x336,
    argsLen      = 0x02, # Script 0x336 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x336 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        # Copy 0000-007D from the original script
        romBytes[0x1EC1D:0x1EC9B].hex(' '),
        # Replace the jump-to-the-end at 007E with in-place "end" codes
        "56",       # 007E: End
        "56",       # 007F: End
        "56",       # 0080: End
        # Spawn Sam at his vanilla "end of new-game cutscene" position
        "00 04",    # 0081: Push unsigned byte 0x04
        "C2",       # 0083: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 0084: Move object instantly to waypoint?
        "00 06",    # 0086: Push unsigned byte 0x06
        "C0",       # 0088: Push zero
        "C2",       # 0089: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 008A: Display sprite with facing direction
        # Set Sam's "new-game cutscene completed" (0x01) flag
        "00 01",    # 008C: Push unsigned byte 0x01
        "C2",       # 008E: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 008F: Set bits of object's flags
        # WAIT_FOR_SCARE
        "00 05",    # 0091: Push unsigned byte 0x05
        "00 01",    # 0093: Push unsigned byte 0x01
        "58 9E",    # 0095: Register menu options / time delay
        "BC",       # 0097: Pop
        "C2",       # 0098: Push unsigned byte from $13+00 <-- Spawn index
        "58 0A",    # 0099: Push distance between Jake and object?
        "00 64",    # 009B: Push unsigned byte 0x64
        "8A",       # 009D: Check if less than
        "C2",       # 009E: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 009F: Push object's flags
        "00 02",    # 00A1: Push unsigned byte 0x02
        "7E",       # 00A3: Bitwise AND
        "BE",       # 00A4: Convert to boolean
        "7E",       # 00A5: Bitwise AND
        "44 91 00", # 00A6: If false, jump to WAIT_FOR_SCARE
        # Copy 013E-01A5 from the original script
        romBytes[0x1ED5B:0x1EDC3].hex(' '),
    ],
)

# Wooden Door <-- Between the halves of the morgue main room
# Skip some code used by the vanilla new-game cutscene
writeHelper(romBytes, 0x1F129, bytes.fromhex(' '.join([
    "48 82 00", # 0025: Jump to 0082
])))

# Slab
# Skip some code used by the vanilla new-game cutscene
writeHelper(romBytes, 0x1EE69, bytes.fromhex(' '.join([
    "C0",       # 001E: Push zero
    "00 08",    # 001F: Push unsigned byte 0x08
    "C2",       # 0021: Push unsigned byte from $13+00 <-- Spawn index
    "58 D1",    # 0022: Display sprite with facing direction
    "48 93 00", # 0024: Jump to 0093
])))
# Skip the text popup for the vanilla Torn Paper
# Reveal the new item shuffled to this location
writeHelper(romBytes, 0x1EF5F, bytes.fromhex(' '.join([
    "C0",       # 0114: Push zero
    "BE",       # 0115: Convert to boolean
    "BE",       # 0116: Convert to boolean
    "BE",       # 0117: Convert to boolean
    "BE",       # 0118: Convert to boolean
    "BE",       # 0119: Convert to boolean
    "BE",       # 011A: Convert to boolean
    "BE",       # 011B: Convert to boolean
    "BE",       # 011C: Convert to boolean
    "BE",       # 011D: Convert to boolean
    "BE",       # 011E: Convert to boolean
    "BE",       # 011F: Convert to boolean
    "BE",       # 0120: Convert to boolean
    "BE",       # 0121: Convert to boolean
    "BE",       # 0122: Convert to boolean
    "BE",       # 0123: Convert to boolean
    "BE",       # 0124: Convert to boolean
    "BE",       # 0125: Convert to boolean
    "BE",       # 0126: Convert to boolean
    "BE",       # 0127: Convert to boolean
    "BE",       # 0128: Convert to boolean
    "BE",       # 0129: Convert to boolean
    "BE",       # 012A: Convert to boolean
    "BC",       # 012B: Pop
    "00 80",    # 012C: Push unsigned byte 0x80
    f"14 {romBytes[0xC848F+0]:02X} {romBytes[0xC848F+1]:02X}",
                # 012E: Push short 0x#### <-- Object-id of new item in "Torn Paper" location
    "58 0D",    # 0131: Set bits of object's flags
])))

# JAKE (morgue script 1)
# Shorten the delay before Jake opens the Slab from inside
writeHelper(romBytes, 0x1F040, bytes.fromhex(' '.join([
    "00 2D",    # 0027: Push unsigned byte 0x2D <-- Was 0xB4
])))

# JAKE (morgue script 2)
expandedOffset = scriptHelper(
    scriptNumber = 0x1B3,
    argsLen      = 0x02, # Script 0x1B3 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x1B3 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        # Copy 0000-005F from the original script
        romBytes[0x1F3D0:0x1F430].hex(' '),
        # Activate the "custom new-game actions" script
        "00 80",    # 0060: Push unsigned byte 0x80
        "14 15 0E", # 0062: Push short 0x0E15 <-- Object-id of "new-game mortician dialogue" object
        "58 0D",    # 0065: Set bits of object's flags
        # Start Jake's rolling-off-the-slab animation
        "C0",       # 0067: Push zero
        "C0",       # 0068: Push zero
        "C2",       # 0069: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 006A: Display sprite with facing direction
        # Wait for Jake to be standing up
        "00 40",    # 006C: Push unsigned byte 0x40
        "00 01",    # 006E: Push unsigned byte 0x01
        "58 9E",    # 0070: Register menu options / time delay
        "BC",       # 0072: Pop
        # Print text
        "00 F0",    # 0073: Push unsigned byte 0xF0
        "00 42",    # 0075: Push unsigned byte 0x42
        "14 00 08", # 0077: Push short 0x0800
        "00 03",    # 007A: Push unsigned byte 0x03
        "00 12",    # 007C: Push unsigned byte 0x12
        "00 15",    # 007E: Push unsigned byte 0x15 <-- Was 0x17
        "00 07",    # 0080: Push unsigned byte 0x07 <-- Was 0x06
        "58 C7",    # 0082: Print text ("Where am I? Who am I?")
        # Wait for Jake's animation to complete
        "C0",       # 0084: Push zero
        "00 08",    # 0085: Push unsigned byte 0x08
        "58 9E",    # 0087: Register menu options / time delay
        "BC",       # 0089: Pop
        # Spawn the player-controllable Jake
        "00 32",    # 008A: Push unsigned byte 0x32
        "14 B2 08", # 008C: Push short 0x08B2 <-- Object-id for Jake
        "00 06",    # 008F: Push unsigned byte 0x06
        "00 40",    # 0091: Push unsigned byte 0x40
        "14 F5 01", # 0093: Push short 0x01F5
        "14 66 01", # 0096: Push short 0x0166
        "00 0B",    # 0099: Push unsigned byte 0x0B
        "58 78",    # 009B: Spawn hired shadowrunner
        # Wait one frame
        "00 01",    # 009D: Push unsigned byte 0x01
        "BA",       # 009F: Duplicate
        "58 9E",    # 00A0: Register menu options / time delay
        "BC",       # 00A2: Pop
        # Despawn
        "C2",       # 00A3: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 00A4: Despawn object
        "56",       # 00A6: End
    ],
)
# Shorten Jake's rolling-off-the-slab animation
romBytes[0x61B5F] = 0x16 # <-- Was 0x19

# New-game mortician dialogue
# Replace the mortician dialogue with custom new-game actions
expandedOffset = scriptHelper(
    scriptNumber = 0x2CF,
    argsLen      = 0x02, # Script 0x1B3 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x1B3 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 0003: Push object's flags
        "00 01",    # 0005: Push unsigned byte 0x01
        "7E",       # 0007: Bitwise AND
        "BE",       # 0008: Convert to boolean
        "46 3A 00", # 0009: If true, jump to DONE
        # WAIT_FOR_ACTIVATION
        "00 01",    # 000C: Push unsigned byte 0x01
        "BA",       # 000E: Duplicate
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 0013: Push object's flags
        "00 80",    # 0015: Push unsigned byte 0x80
        "7E",       # 0017: Bitwise AND
        "BE",       # 0018: Convert to boolean
        "44 0C 00", # 0019: If false, jump to WAIT_FOR_ACTIVATION
        # CUSTOM_NEW_GAME_ACTIONS
        "00 7F",    # 001C: Push unsigned byte 0x7F
        "C2",       # 001E: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 001F: Clear bits of object's flags
        # Learn default keywords
        # - HitMen
        "00 17",    # 0021: Push unsigned byte 0x17 <-- Keyword-id for "HitMen"
        "58 71",    # 0023: Learn keyword
        # - Firearms
        "00 10",    # 0025: Push unsigned byte 0x10 <-- Keyword-id for "Firearms"
        "58 71",    # 0027: Learn keyword
        # - Heal
        "00 15",    # 0029: Push unsigned byte 0x15 <-- Keyword-id for "Heal"
        "58 71",    # 002B: Learn keyword
        # - Shadowrunners (required to learn "Hiring" in vanilla)
        "00 2A",    # 002D: Push unsigned byte 0x2A <-- Keyword-id for "Shadowrunners"
        "58 71",    # 002F: Learn keyword
        # - Hiring
        "00 16",    # 0031: Push unsigned byte 0x16 <-- Keyword-id for "Hiring"
        "58 71",    # 0033: Learn keyword
        ## - Decker (required to learn "Datajack" in vanilla)
        #"00 0B",    # ____: Push unsigned byte 0x0B <-- Keyword-id for "Decker"
        #"58 71",    # ____: Learn keyword
        ## - Datajack
        #"00 0A",    # ____: Push unsigned byte 0x0A <-- Keyword-id for "Datajack"
        #"58 71",    # ____: Learn keyword
        ## - Docks
        #"00 0C",    # ____: Push unsigned byte 0x0C <-- Keyword-id for "Docks"
        #"58 71",    # ____: Learn keyword
        # Set the "custom new-game actions completed" (0x01) flag
        "00 01",    # 0035: Push unsigned byte 0x01
        "C2",       # 0037: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 0038: Set bits of object's flags
        # DONE
        "C2",       # 003A: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 003B: Despawn object
        "56",       # 003D: End
    ],
)

# TODO: Matchbox <-- Not currently subject to randomization

# Torn Paper
writeHelper(romBytes, 0xC848B, bytes.fromhex(' '.join([
    "7F 01",    # Move the spawn point to the floor
    "F3 11",    # New coordinates: (383, 499, 64)
])))
writeHelper(romBytes, 0xDEF22, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    "48 15 00", # 000C: Jump to 0015
])))

# Torn Paper: Slab
# For these changes, see the modified "Slab" script above.

# Scalpel
writeHelper(romBytes, 0xDEE85, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
])))

# Slap Patch <-- "One-time dispenser" in morgue
# Allow pickup of a single Slap Patch any time you have no slap
# patches in your inventory, turning this location into a
# (technically) unlimited source of slap patches.
expandedOffset = scriptHelper(
    scriptNumber = 0x3C,
    argsLen      = 0x02, # Script 0x3C now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x3C now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x03, # Header byte: Script uses 0x03 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "14 95 03", # 0002: Push short 0x0395 <-- Object-id of "Slap Patch" (stackable inventory item)
        "58 C6",    # 0005: Push object's quantity
        "46 5B 00", # 0007: If nonzero, jump to DONE
        # NO_SLAP_PATCHES_IN_INVENTORY
        "C2",       # 000A: Push unsigned byte from $13+00 <-- Spawn index
        "52 44 02", # 000B: Execute behaviour script 0x244 = Display sprite with facing direction 00
        # TOP_OF_LOOP
        "C0",       # 000E: Push zero
        "C0",       # 000F: Push zero
        "52 AA 02", # 0010: Execute behaviour script 0x2AA = Interaction menu helper
        "BA",       # 0013: Duplicate
        "34 01",    # 0014: Pop short to $13+01 <-- Selected menu option
        # CHECK_IF_EXAMINE
        "00 80",    # 0016: Push unsigned byte 0x80
        "AA",       # 0018: Check if equal
        "44 30 00", # 0019: If not equal, jump to CHECK_IF_PICKUP
        # EXAMINE
        # Interaction menu option: Examine
        "00 F0",    # 001C: Push unsigned byte 0xF0
        "00 8D",    # 001E: Push unsigned byte 0x8D
        "14 00 08", # 0020: Push short 0x0800
        "00 03",    # 0023: Push unsigned byte 0x03
        "00 12",    # 0025: Push unsigned byte 0x12
        "00 15",    # 0027: Push unsigned byte 0x15
        "00 02",    # 0029: Push unsigned byte 0x02
        "58 C7",    # 002B: Print text ("This is a healing patch.")
        "48 0E 00", # 002D: Jump to TOP_OF_LOOP
        # CHECK_IF_PICKUP
        "16 01",    # 0030: Push short from $13+01 <-- Selected menu option
        "00 10",    # 0032: Push unsigned byte 0x10
        "AA",       # 0034: Check if equal
        "44 0E 00", # 0035: If not equal, jump to TOP_OF_LOOP
        # PICKUP
        # Interaction menu option: Pickup
        "58 28",    # 0038: Push Jake's spawn index
        "58 4F",    # 003A: Push object's X coordinate / 4
        "14 D0 01", # 003C: Push short 0x01D0
        "9A",       # 003F: Check if greater than
        "44 49 00", # 0040: If no, jump to PICKUP_OK
        # TRIED_PICKUP_THROUGH_WALL
        "52 6C 02", # 0043: Execute behaviour script 0x26C
        "48 0E 00", # 0046: Jump to TOP_OF_LOOP
        # PICKUP_OK
        "00 01",    # 0049: Push unsigned byte 0x01
        "14 95 03", # 004B: Push short 0x0395 <-- Object-id of "Slap Patch" (stackable inventory item)
        "58 26",    # 004E: Add amount to object's quantity (stackables)
        "14 B2 08", # 0050: Push short 0x08B2 <-- Object-id for Jake
        "14 95 03", # 0053: Push short 0x0395 <-- Object-id of "Slap Patch" (stackable inventory item)
        "58 74",    # 0056: Set object's owner
        "52 4B 00", # 0058: Execute behaviour script 0x4B = "Got item" sound effect
        # DONE
        "C2",       # 005B: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 005C: Despawn object
        "56",       # 005E: End
    ],
)

# Morgue Filing Cabinet helper script
# Skip the text popups for the vanilla Tickets and Credstick
writeHelper(romBytes, 0x1F292, bytes.fromhex(' '.join([
    "C0",       # 009B: Push zero
    "BE",       # 009C: Convert to boolean
    "BE",       # 009D: Convert to boolean
    "BE",       # 009E: Convert to boolean
    "BE",       # 009F: Convert to boolean
    "BE",       # 00A0: Convert to boolean
    "BE",       # 00A1: Convert to boolean
    "BE",       # 00A2: Convert to boolean
    "BE",       # 00A3: Convert to boolean
    "BE",       # 00A4: Convert to boolean
    "BE",       # 00A5: Convert to boolean
    "BE",       # 00A6: Convert to boolean
    "BE",       # 00A7: Convert to boolean
    "BE",       # 00A8: Convert to boolean
    "BE",       # 00A9: Convert to boolean
    "BE",       # 00AA: Convert to boolean
    "BC",       # 00AB: Pop
])))

# Tickets
writeHelper(romBytes, 0xDF139, bytes.fromhex(' '.join([
    "52 1D 01", # 0003: Execute behaviour script 0x11D = New item-drawing script
])))

# Tickets: Filing Cabinet
# Reveal the new item shuffled to this location
romBytes[0x1F2CE:0x1F2CE+2] = romBytes[0xC8489:0xC8489+2]

# Credstick
writeHelper(romBytes, 0xDF077, bytes.fromhex(' '.join([
    "52 1D 01", # 0003: Execute behaviour script 0x11D = New item-drawing script
])))

# Credstick: Filing Cabinet
# Reveal the new item shuffled to this location
romBytes[0x1F2DE:0x1F2DE+2] = romBytes[0xC849B:0xC849B+2]

# Wooden Door <-- In morgue main room, leading to morgue hallway
# Change the behaviour script for the Wooden Door from 0xAD
# (closed door) to 0xE2 (open door).
struct.pack_into("<H", romBytes, 0x6B147, 0x00E2)
# When the player-controllable Jake object is created at the beginning
# of a new game, some code in [58 78] (Spawn hired shadowrunner) sets
# the 0x0001 and 0x0002 bits of the Jake object's 7E1474+n entry.
# I'm not sure what this was intended to do. The bits are cleared upon
# map transition (i.e. as soon as you leave the morgue main room), and
# they appear to remain cleared afterwards.
# With doubled walking speed, however, these bits create an unexpected
# bug: the door to the morgue hallway becomes unpredictably difficult
# to traverse. Getting through might happen on your first attempt, or
# only after retreating and approaching the door half a dozen times.
# Very annoying, to say the least.
# So, let's avoid setting those bits in the first place.
romBytes[0x21F2] = 0x80 # <-- Was 0xD0

# Decker <-- "You can't be alive!" guy
# Tenth Street - Center
# Change the behaviour script for the Decker from 0x2C1 ("You can't be
# alive!" guy in Tenth Street Center) to 0x37B (do nothing).
# With this change, the Decker will no longer appear.
# We do this to skip the Decker's automatic conversation.
# Additionally, script 0x2C1 should now be entirely unused.
struct.pack_into("<H", romBytes, 0x6C61D, 0x037B)
# Tenth Street - West
# Change the behaviour script for the Decker from 0x2C5 ("You can't be
# alive!" guy in Tenth Street West) to 0x37B (do nothing).
# With this change, the Decker will no longer appear.
# We do this for consistency with the previous change.
# Additionally, script 0x2C5 should now be entirely unused.
struct.pack_into("<H", romBytes, 0x6C60F, 0x037B)

# Dog Collar
writeHelper(romBytes, 0xDF1BE, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    "48 10 00", # 000C: Jump to 0010
])))
# Use facing direction 05's sprite for direction 00
romBytes[0x649C4] = 0x08

# Dog Collar: Doggie
# Reveal the new item shuffled to this location
romBytes[0xDCA5F:0xDCA5F+2] = romBytes[0xC817B:0xC817B+2]

# Glass Door <-- Left door to Tenth Street monorail station
# Open up the monorail early
# Change the behaviour script for the left Glass Door from 0x37D
# (left Glass Door helper) to 0xE2 (open door).
# In vanilla, script 0x37D would check if Glutman had hidden you
# in the caryards and then execute either script 0x6 (locked) or
# script 0xAD (closed door) as appropriate.
# With this change, script 0x37D should now be entirely unused.
struct.pack_into("<H", romBytes, 0x6C0B3, 0x00E2)

# Glass Door <-- Right door to Tenth Street monorail station
# Open up the monorail early
# Change the behaviour script for the right Glass Door from 0x1A6
# (right Glass Door helper) to 0x2E6 (open door).
# In vanilla, script 0x1A6 would check if Glutman had hidden you
# in the caryards and then execute either script 0x1DC (locked) or
# script 0x2B4 (closed door) as appropriate.
# With this change, script 0x1A6 should now be entirely unused.
struct.pack_into("<H", romBytes, 0x6C0AC, 0x02E6)

# Bulletin Board <-- Outside Tenth Street monorail station
# We've opened up the monorail early, so let's update the bulletin
# board to match. ("TENTH STREET STATION IS NOW FULLY REPAIRED")
writeHelper(romBytes, 0xDF7A3, bytes.fromhex(' '.join([
    "BC",       # 000F: Pop
    "C0",       # 0010: Push zero
    "BC",       # 0011: Pop
    "48 29 00", # 0012: Jump to 0029
])))

# Memo
writeHelper(romBytes, 0xDF523, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
])))
# Inventory list item-hiding
# Don't hide the Memo after leaving Tenth Street
romBytes[0x6B8DC] |= 0x3F

# Door Key
writeHelper(romBytes, 0xDF415, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    "48 10 00", # 000C: Jump to 0010
])))
# Use facing direction 05's sprite for direction 00
romBytes[0x6418C] = 0x08

# Door Key: Seems familiar...
# Skip the text popup for the vanilla Door Key
# Reveal the new item shuffled to this location
writeHelper(romBytes, 0xDD209, bytes.fromhex(' '.join([
    "C0",       # 0046: Push zero
    "BE",       # 0047: Convert to boolean
    "BE",       # 0048: Convert to boolean
    "BE",       # 0049: Convert to boolean
    "BE",       # 004A: Convert to boolean
    "BE",       # 004B: Convert to boolean
    "BE",       # 004C: Convert to boolean
    "BE",       # 004D: Convert to boolean
    "BE",       # 004E: Convert to boolean
    "BE",       # 004F: Convert to boolean
    "BE",       # 0050: Convert to boolean
    "BE",       # 0051: Convert to boolean
    "BE",       # 0052: Convert to boolean
    "BE",       # 0053: Convert to boolean
    "BE",       # 0054: Convert to boolean
    "BC",       # 0055: Pop
    "00 01",    # 0056: Push unsigned byte 0x01
    "C2",       # 0058: Push unsigned byte from $13+00 <-- Spawn index
    "58 33",    # 0059: Set bits of object's flags
    "00 80",    # 005B: Push unsigned byte 0x80
    f"14 {romBytes[0xC93F3+0]:02X} {romBytes[0xC93F3+1]:02X}",
                # 005D: Push short 0x#### <-- Object-id of new item in "Door Key" location
    "58 0D",    # 0060: Set bits of object's flags
])))

# Shades
writeHelper(romBytes, 0xDF49D, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
])))
# Use facing direction 05's sprite for direction 00
romBytes[0x642D6] = 0x08

# Ripped Note
writeHelper(romBytes, 0xDEFC3, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
])))

# Video Phone <-- In Jake's apartment
# Change the behaviour script for the Video Phone from 0x1C6
# (Video Phone in Jake's apartment with recorded message) to
# 0x206 (Video Phone).
# We're doing this so we don't have to listen to the recorded
# message before using Jake's phone to make outgoing calls.
# With this change, script 0x1C6 should now be entirely unused.
struct.pack_into("<H", romBytes, 0x6B1A9, 0x0206)

# Beretta Pistol
writeHelper(romBytes, 0xC886D, bytes.fromhex(' '.join([
    "34 01",    # Move the spawn point to waypoint 0x01 on the alley map
    "16 11",    # Waypoint 0x01 coordinates: (308, 278, 64)
])))

# Leather Jacket
writeHelper(romBytes, 0xC8873, bytes.fromhex(' '.join([
    "5E 01",    # Move the spawn point to match the Orc's spawn point
    "4A 11",    # Orc's spawn coordinates: (350, 330, 64)
])))
# Change the behaviour script for the Leather Jacket from 0x354
# (Leather Jacket in alley) to 0x292 (Leather Jacket).
# In vanilla, 0x354 was a more complicated script to handle the
# jacket in the alley, while 0x292 just specified armor stats
# (with the former eventually invoking the latter).
# With this change, script 0x354 should now be entirely unused.
struct.pack_into("<H", romBytes, 0x6BB57, 0x0292)
# Increase the Leather Jacket's sprite priority
romBytes[0x6BB52] |= 0x40

# Leather Jacket: Orc
# Reveal the new item shuffled to this location
writeHelper(romBytes, 0xDD15A, bytes.fromhex(' '.join([
    "00 01",    # 00C3: Push unsigned byte 0x01
    "02 01",    # 00C5: Push unsigned byte from $13+01 <-- Copy of original spawn index
    "58 33",    # 00C7: Set bits of object's flags
    f"14 {romBytes[0xC8877+0]:02X} {romBytes[0xC8877+1]:02X}",
                # 00C9: Push short 0x####   <-- Item drop's object-id
    "58 C2",    # 00CC: Push object's RAM_1 <-- Item drop's spawn index
    "2C 01",    # 00CE: Pop byte to $13+01  <-- Item drop's spawn index
    "C2",       # 00D0: Push unsigned byte from $13+00 <-- Spawn index
    "58 51",    # 00D1: Push object's Z coordinate / 4
    "00 02",    # 00D3: Push unsigned byte 0x02
    "7A",       # 00D5: Left shift
    "C2",       # 00D6: Push unsigned byte from $13+00 <-- Spawn index
    "58 50",    # 00D7: Push object's Y coordinate / 4
    "00 02",    # 00D9: Push unsigned byte 0x02
    "7A",       # 00DB: Left shift
    "00 02",    # 00DC: Push unsigned byte 0x02
    "5E",       # 00DE: Subtraction
    "C2",       # 00DF: Push unsigned byte from $13+00 <-- Spawn index
    "58 4F",    # 00E0: Push object's X coordinate / 4
    "00 02",    # 00E2: Push unsigned byte 0x02
    "7A",       # 00E4: Left shift
    "00 02",    # 00E5: Push unsigned byte 0x02
    "5E",       # 00E7: Subtraction
    "02 01",    # 00E8: Push unsigned byte from $13+01 <-- Item drop's spawn index
    "58 82",    # 00EA: Set object X/Y/Z position
    "00 10",    # 00EC: Push unsigned byte 0x10
    "C0",       # 00EE: Push zero
    "C0",       # 00EF: Push zero
    "02 01",    # 00F0: Push unsigned byte from $13+01 <-- Item drop's spawn index
    "58 79",    # 00F2: Set object X/Y/Z deltas?
    "00 80",    # 00F4: Push unsigned byte 0x80
    "02 01",    # 00F6: Push unsigned byte from $13+01 <-- Item drop's spawn index
    "58 33",    # 00F8: Set bits of object's flags
    "00 01",    # 00FA: Push unsigned byte 0x01
    "BA",       # 00FC: Duplicate
    "58 9E",    # 00FD: Register menu options / time delay
    "BC",       # 00FF: Pop
    "00 20",    # 0100: Push unsigned byte 0x20
    "02 01",    # 0102: Push unsigned byte from $13+01 <-- Item drop's spawn index
    "58 CE",    # 0104: Set bits of 7E1474+n <-- Makes the item drop subject to gravity
    "C0",       # 0106: Push zero
    "00 80",    # 0107: Push unsigned byte 0x80
    "58 9E",    # 0109: Register menu options / time delay
    "BC",       # 010B: Pop
    "52 8D 03", # 010C: Execute behaviour script 0x38D = Body behaviour script: "Nothing special here."
    "48 06 01", # 010F: Jump to 0106
])))

# Keyword: Dog
writeHelper(romBytes, 0xC8855, bytes.fromhex(' '.join([
    "58 02",    # Move the spawn point a short distance down and right
    "2E 11",    # New coordinates: (600, 302, 64)
])))

# Paperweight
writeHelper(romBytes, 0xDF5F4, bytes.fromhex(' '.join([
    "C2",       # 0038: Push unsigned byte from $13+00 <-- Spawn index
    "52 1D 01", # 0039: Execute behaviour script 0x11D = New item-drawing script
    "00 00",    # 003C: Push unsigned byte 0x00
])))
writeHelper(romBytes, 0xDF608, bytes.fromhex(' '.join([
    "48 3C 00", # 004C: Jump to 003C
])))

# Cyberdeck
writeHelper(romBytes, 0xFD0E4, bytes.fromhex(' '.join([
    "52 1D 01", # 0015: Execute behaviour script 0x11D = New item-drawing script
])))
# Use facing direction 05's sprite for direction 00
romBytes[0x653AE] = 0x08

# TODO: LoneStar Badge <-- Not currently subject to randomization

# Iced Tea
writeHelper(romBytes, 0xDF2D1, bytes.fromhex(' '.join([
    "52 1D 01", # 0003: Execute behaviour script 0x11D = New item-drawing script
])))

# Iced Tea: Club Manager
# Reveal the new item shuffled to this location
romBytes[0x1E66C:0x1E66C+2] = romBytes[0xC87BF:0xC87BF+2]

# Jamaican <-- Jangadance
writeHelper(romBytes, 0xC879D, bytes.fromhex(' '.join([
    "08 02",    # Move the spawn point to waypoint 0x02 on the nightclub map
    "CC 11",    # Waypoint 0x02 coordinates: (520, 460, 64)
])))
# Skip the "on the phone" case
writeHelper(romBytes, 0xDD3AE, bytes.fromhex(' '.join([
    "44 54 00", # 000B: If false, jump to 0054
])))

# Video Phone <-- In the Grim Reaper Club
# Change the behaviour script for the Video Phone from 0x2DF
# (Video Phone in the Grim Reaper Club) to 0x206 (Video Phone).
# We're doing this because with NPC randomization, this phone
# will not initially be in use by someone making a call.
# With this change, script 0x2DF should now be entirely unused.
struct.pack_into("<H", romBytes, 0x6B1A2, 0x0206)

# Ghoul Bone
expandedOffset = scriptHelper(
    scriptNumber = 0x200,
    argsLen      = 0x02, # Script 0x200 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x200 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x04, # Header byte: Script uses 0x04 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 11 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "00 08",    # 000C: Push unsigned byte 0x08
        "C2",       # 000E: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 000F: Display sprite <-- We do this to fix the "spinning Ghoul Bone" bug
        # TOP_OF_LOOP
        "C2",       # 0011: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0012: Check if object has an owner
        "2C 01",    # 0014: Pop byte to $13+01 <-- Whether object has an owner
        "C0",       # 0016: Push zero
        "0C 01",    # 0017: Push signed byte from $13+01 <-- Whether object has an owner
        "52 AA 02", # 0019: Execute behaviour script 0x2AA = Interaction menu helper
        "BA",       # 001C: Duplicate
        "34 02",    # 001D: Pop short to $13+02 <-- Selected menu option
        # CHECK_IF_EXAMINE
        "00 80",    # 001F: Push unsigned byte 0x80
        "AA",       # 0021: Check if equal
        "44 42 00", # 0022: If not equal, jump to CHECK_IF_PICKUP
        # EXAMINE
        # Interaction menu option: Examine
        "00 03",    # 0025: Push unsigned byte 0x03
        "00 FF",    # 0027: Push unsigned byte 0xFF
        "00 32",    # 0029: Push unsigned byte 0x32
        "C2",       # 002B: Push unsigned byte from $13+00 <-- Spawn index
        "58 4C",    # 002C: Play sound effect
        "00 F0",    # 002E: Push unsigned byte 0xF0 <-- Was 0x78
        "00 99",    # 0030: Push unsigned byte 0x99
        "14 00 08", # 0032: Push short 0x0800
        "00 03",    # 0035: Push unsigned byte 0x03
        "00 14",    # 0037: Push unsigned byte 0x14
        "00 15",    # 0039: Push unsigned byte 0x15
        "00 02",    # 003B: Push unsigned byte 0x02
        "58 C7",    # 003D: Print text ("A bone of the living dead.")
        "48 54 00", # 003F: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_PICKUP
        "16 02",    # 0042: Push short from $13+02 <-- Selected menu option
        "00 10",    # 0044: Push unsigned byte 0x10
        "AA",       # 0046: Check if equal
        "44 54 00", # 0047: If not equal, jump to BOTTOM_OF_LOOP
        # PICKUP
        # Interaction menu option: Pickup
        "C2",       # 004A: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 004B: Set object's owner to Jake
        "52 4B 00", # 004D: Execute behaviour script 0x4B = "Got item" sound effect
        "0A FF",    # 0050: Push signed byte 0xFF
        "2C 01",    # 0052: Pop byte to $13+01 <-- Whether object has an owner
        # BOTTOM_OF_LOOP
        "0C 01",    # 0054: Push signed byte from $13+01 <-- Whether object has an owner
        "44 11 00", # 0056: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 0059: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 005A: Despawn object
        "56",       # 005D: End
    ],
)
# Use facing direction 03's sprite for direction 00
romBytes[0x6661E] = 0x08
# Increase the Ghoul Bone's sprite priority
romBytes[0x6C172] |= 0x40
# Make the Ghoul Bone not inherently subject to gravity
romBytes[0x674F4] &= ~0x20

# Ghoul Bone: Scary Ghoul
# Increase the Scary Ghoul's item-drop chance from 50% to 100%
# Reveal the new item shuffled to this location
writeHelper(romBytes, 0x1FEDD, bytes.fromhex(' '.join([
    "0A FF",    # 00E5: Push signed byte 0xFF
    "BE",       # 00E7: Convert to boolean
    "BE",       # 00E8: Convert to boolean
    "BE",       # 00E9: Convert to boolean
    "7E",       # 00EA: Bitwise AND
    "44 5C 01", # 00EB: If false, jump to 015C
    f"14 {romBytes[0xC85D1+0]:02X} {romBytes[0xC85D1+1]:02X}",
                # 00EE: Push short 0x####   <-- Item drop's object-id
    "BA",       # 00F1: Duplicate
    "58 C2",    # 00F2: Push object's RAM_1 <-- Item drop's spawn index
    "2C 0A",    # 00F4: Pop byte to $13+0A  <-- Item drop's spawn index
    "58 BA",    # 00F6: Push object's flags <-- Item drop's flags
    "00 80",    # 00F8: Push unsigned byte 0x80
    "7E",       # 00FA: Bitwise AND
    "BE",       # 00FB: Convert to boolean
    "46 5C 01", # 00FC: If true, jump to 015C
    "C2",       # 00FF: Push unsigned byte from $13+00 <-- Spawn index
    "58 51",    # 0100: Push object's Z coordinate / 4
    "00 02",    # 0102: Push unsigned byte 0x02
    "7A",       # 0104: Left shift
    "C2",       # 0105: Push unsigned byte from $13+00 <-- Spawn index
    "58 50",    # 0106: Push object's Y coordinate / 4
    "00 02",    # 0108: Push unsigned byte 0x02
    "7A",       # 010A: Left shift
    "C2",       # 010B: Push unsigned byte from $13+00 <-- Spawn index
    "58 4F",    # 010C: Push object's X coordinate / 4
    "00 02",    # 010E: Push unsigned byte 0x02
    "7A",       # 0110: Left shift
    "02 0A",    # 0111: Push unsigned byte from $13+0A <-- Item drop's spawn index
    "58 82",    # 0113: Set object X/Y/Z position
    "00 10",    # 0115: Push unsigned byte 0x10
    "C0",       # 0117: Push zero
    "C0",       # 0118: Push zero
    "02 0A",    # 0119: Push unsigned byte from $13+0A <-- Item drop's spawn index
    "58 79",    # 011B: Set object X/Y/Z deltas?
    "00 80",    # 011D: Push unsigned byte 0x80
    "02 0A",    # 011F: Push unsigned byte from $13+0A <-- Item drop's spawn index
    "58 33",    # 0121: Set bits of object's flags
    "00 01",    # 0123: Push unsigned byte 0x01
    "BA",       # 0125: Duplicate
    "58 9E",    # 0126: Register menu options / time delay
    "BC",       # 0128: Pop
    "00 20",    # 0129: Push unsigned byte 0x20
    "02 0A",    # 012B: Push unsigned byte from $13+0A <-- Item drop's spawn index
    "58 CE",    # 012D: Set bits of 7E1474+n <-- Makes the item drop subject to gravity
    "48 5C 01", # 012F: Jump to 015C
])))

# Magic Fetish
writeHelper(romBytes, 0xC894D, bytes.fromhex(' '.join([
    "76 02",    # Move the spawn point to match Chrome Coyote's spawn point
    "A0 11",    # Chrome Coyote's spawn coordinates: (630, 416, 64)
])))
expandedOffset = scriptHelper(
    scriptNumber = 0x1BB,
    argsLen      = 0x02, # Script 0x1BB now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x1BB now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x04, # Header byte: Script uses 0x04 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        # TOP_OF_LOOP
        "C2",       # 000C: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 000D: Check if object has an owner
        "2C 01",    # 000F: Pop byte to $13+01 <-- Whether object has an owner
        "C0",       # 0011: Push zero
        "0C 01",    # 0012: Push signed byte from $13+01 <-- Whether object has an owner
        "52 AA 02", # 0014: Execute behaviour script 0x2AA = Interaction menu helper
        "BA",       # 0017: Duplicate
        "34 02",    # 0018: Pop short to $13+02 <-- Selected menu option
        # CHECK_IF_EXAMINE
        "00 80",    # 001A: Push unsigned byte 0x80
        "AA",       # 001C: Check if equal
        "44 3D 00", # 001D: If not equal, jump to CHECK_IF_PICKUP
        # EXAMINE
        # Interaction menu option: Examine
        "00 03",    # 0020: Push unsigned byte 0x03
        "00 FF",    # 0022: Push unsigned byte 0xFF
        "00 32",    # 0024: Push unsigned byte 0x32
        "C2",       # 0026: Push unsigned byte from $13+00 <-- Spawn index
        "58 4C",    # 0027: Play sound effect
        "00 F0",    # 0029: Push unsigned byte 0xF0
        "00 83",    # 002B: Push unsigned byte 0x83
        "14 00 08", # 002D: Push short 0x0800
        "00 03",    # 0030: Push unsigned byte 0x03
        "00 19",    # 0032: Push unsigned byte 0x19
        "00 15",    # 0034: Push unsigned byte 0x15 <-- Was 0x14
        "00 02",    # 0036: Push unsigned byte 0x02
        "58 C7",    # 0038: Print text ("Engraved on the amulet is a bat.")
        "48 53 00", # 003A: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_PICKUP
        "16 02",    # 003D: Push short from $13+02 <-- Selected menu option
        "00 10",    # 003F: Push unsigned byte 0x10
        "AA",       # 0041: Check if equal
        "44 53 00", # 0042: If not equal, jump to BOTTOM_OF_LOOP
        # In vanilla, picking up the Magic Fetish does not teach you
        # the "Magic Fetish" keyword. Instead, you get both keyword
        # and item by talking to Chrome Coyote after you heal him.
        # So this "Pickup" case is actually entirely new.
        # PICKUP
        # Interaction menu option: Pickup
        "00 1E",    # 0045: Push unsigned byte 0x1E <-- Keyword-id for "Magic Fetish"
        "58 71",    # 0047: Learn keyword
        "C2",       # 0049: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 004A: Set object's owner to Jake
        "52 4B 00", # 004C: Execute behaviour script 0x4B = "Got item" sound effect
        "0A FF",    # 004F: Push signed byte 0xFF
        "2C 01",    # 0051: Pop byte to $13+01 <-- Whether object has an owner
        # In vanilla, you could "Give" the Magic Fetish to Vladimir.
        # The code for that interaction would be here, but since we've
        # replaced Vladimir with the "Bremerton" keyword-item, there's
        # no one to give the Magic Fetish to. Hence, no "Give" case.
        # BOTTOM_OF_LOOP
        "0C 01",    # 0053: Push signed byte from $13+01 <-- Whether object has an owner
        "44 0C 00", # 0055: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 0058: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0059: Despawn object
        "56",       # 005B: End
    ],
)
# Use the Talisman Case's sprite data (0xC1F4 --> 0xCFEC)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0x7F), 0xCFEC)

# Magic Fetish: Indian Shaman <-- Chrome Coyote
# Reveal the new item shuffled to this location
expandedOffset = scriptHelper(
    scriptNumber = 0x190,
    argsLen      = 0x02, # Script 0x190 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x190 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x04, # Header byte: Script uses 0x04 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        # 0000-0008
        # Copy 0000-0008 from the original script.
        romBytes[0xDC3C2:0xDC3CB].hex(' '),
        # 0009-000B
        # Update jump destination (changed due to presence of new code).
        "46 67 00", # 0009: If true, jump to 0067
        # 000C-0066
        # Copy 000C-0066 from the original script.
        romBytes[0xDC3CE:0xDC429].hex(' '),
        # 0067-00B2
        # New code.
        "00 05",    # 0067: Push unsigned byte 0x05
        "00 07",    # 0069: Push unsigned byte 0x07
        "C2",       # 006B: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 006C: Display sprite with facing direction
        "00 78",    # 006E: Push unsigned byte 0x78
        "00 16",    # 0070: Push unsigned byte 0x16
        "14 00 04", # 0072: Push short 0x0400
        "00 03",    # 0075: Push unsigned byte 0x03
        "00 07",    # 0077: Push unsigned byte 0x07
        "00 15",    # 0079: Push unsigned byte 0x15
        "00 0D",    # 007B: Push unsigned byte 0x0D
        "58 C7",    # 007D: Print text ("Thanks!")
        "00 02",    # 007F: Push unsigned byte 0x02
        "C2",       # 0081: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0082: Display sprite
        "C0",       # 0084: Push zero
        "00 08",    # 0085: Push unsigned byte 0x08
        "58 9E",    # 0087: Register menu options / time delay
        "BC",       # 0089: Pop
        "00 80",    # 008A: Push unsigned byte 0x80
        f"14 {romBytes[0xC8951+0]:02X} {romBytes[0xC8951+1]:02X}",
                    # 008C: Push short 0x#### <-- Object-id of new item in "Magic Fetish" location
        "58 0D",    # 008F: Set bits of object's flags
        "00 03",    # 0091: Push unsigned byte 0x03
        "C2",       # 0093: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0094: Display sprite
        "00 02",    # 0096: Push unsigned byte 0x02
        "C0",       # 0098: Push zero
        "C0",       # 0099: Push zero
        "C2",       # 009A: Push unsigned byte from $13+00 <-- Spawn index
        "58 79",    # 009B: Set object X/Y/Z deltas?
        "00 03",    # 009D: Push unsigned byte 0x03
        "00 FF",    # 009F: Push unsigned byte 0xFF
        "00 66",    # 00A1: Push unsigned byte 0x66
        "C2",       # 00A3: Push unsigned byte from $13+00 <-- Spawn index
        "58 4C",    # 00A4: Play sound effect
        "C0",       # 00A6: Push zero
        "00 08",    # 00A7: Push unsigned byte 0x08
        "58 9E",    # 00A9: Register menu options / time delay
        "BC",       # 00AB: Pop
        "C2",       # 00AC: Push unsigned byte from $13+00 <-- Spawn index
        "58 C4",    # 00AD: Set object's owner to "Dog Food"
        "C2",       # 00AF: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 00B0: Despawn object
        "56",       # 00B2: End
    ],
)

# Video Phone
# In vanilla, the Video Phone script checks if you know any phone
# numbers by reading a variable that's incremented when you read the
# Ripped Note (which gives you Sassie's number).
# If that variable is zero, you get the "You don't have any numbers
# to call" message, even if you know other phone numbers.
# This isn't the desired behaviour, so let's make the script check
# if there's anything in the "known phone numbers" list instead.
writeHelper(romBytes, 0x16FD8, bytes.fromhex(' '.join([
    "18 1C 3C", # 005E: Push short from $7E3C1C
])))

# Nuyen: Glutman
writeHelper(romBytes, 0xC86D5, bytes.fromhex(' '.join([
    "48 02",    # Move the spawn point a short distance up and right
    "14 12",    # New coordinates: (584, 532, 64)
])))
# Reveal the new item shuffled to this location
romBytes[0x1FFF5:0x1FFF5+2] = romBytes[0xC86D9:0xC86D9+2]

# The King
# Make the King behave as if he's been paid off, so players can leave
# the caryards freely. Previously, we did this by setting the King's
# "paid off" flag in "initialItemState", but it turns out that flag
# also prevents you from fighting the King in the arena.
# ("The King doesn't want to fight you...")
writeHelper(romBytes, 0xE75CD, bytes.fromhex(' '.join([
    "BC",       # 001C: Pop
    "C0",       # 001D: Push zero
    "BC",       # 001E: Pop
])))

# Arena owner
# Skip the "defeated all ten fighters and the King" case.
# In vanilla, defeating everyone replaces the arena owner conversation
# with a text popup ("Buddy, nobody left to fight here!!"), which also
# locks you out of buying the Negotiation skill.
writeHelper(romBytes, 0xFB6C5, bytes.fromhex(' '.join([
    "C0",       # 0053: Push zero
    "BC",       # 0054: Pop
    "48 7B 00", # 0055: Jump to 007B
])))

# Potion Bottles
expandedOffset = scriptHelper(
    scriptNumber = 0x291,
    argsLen      = 0x02, # Script 0x291 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x291 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x06, # Header byte: Script uses 0x06 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        # TOP_OF_LOOP
        "C2",       # 000C: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 000D: Check if object has an owner
        "2C 01",    # 000F: Pop byte to $13+01 <-- Whether object has an owner
        "14 00 01", # 0011: Push short 0x0100
        "0C 01",    # 0014: Push signed byte from $13+01 <-- Whether object has an owner
        "52 AA 02", # 0016: Execute behaviour script 0x2AA = Interaction menu helper
        "BA",       # 0019: Duplicate
        "34 02",    # 001A: Pop short to $13+02 <-- Selected menu option
        # CHECK_IF_EXAMINE
        "00 80",    # 001C: Push unsigned byte 0x80
        "AA",       # 001E: Check if equal
        "44 90 00", # 001F: If not equal, jump to CHECK_IF_PICKUP
        # EXAMINE
        # Interaction menu option: Examine
        "00 03",    # 0022: Push unsigned byte 0x03
        "00 FF",    # 0024: Push unsigned byte 0xFF
        "00 32",    # 0026: Push unsigned byte 0x32
        "C2",       # 0028: Push unsigned byte from $13+00 <-- Spawn index
        "58 4C",    # 0029: Play sound effect
        # BLUE_BOTTLE_STATUS
        "C2",       # 002B: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 002C: Push object's flags
        "00 01",    # 002E: Push unsigned byte 0x01
        "7E",       # 0030: Bitwise AND
        "BE",       # 0031: Convert to boolean
        "44 4A 00", # 0032: If false, jump to BLUE_BOTTLE_EMPTY
        # BLUE_BOTTLE_FULL
        "00 F0",    # 0035: Push unsigned byte 0xF0
        "14 07 01", # 0037: Push short 0x0107
        "14 00 08", # 003A: Push short 0x0800
        "00 03",    # 003D: Push unsigned byte 0x03
        "00 18",    # 003F: Push unsigned byte 0x18
        "00 13",    # 0041: Push unsigned byte 0x13
        "00 04",    # 0043: Push unsigned byte 0x04
        "58 C7",    # 0045: Print text ("The blue bottle contains water.")
        "48 5C 00", # 0047: Jump to PURPLE_BOTTLE_STATUS
        # BLUE_BOTTLE_EMPTY
        "00 F0",    # 004A: Push unsigned byte 0xF0
        "14 06 01", # 004C: Push short 0x0106
        "14 00 08", # 004F: Push short 0x0800
        "00 03",    # 0052: Push unsigned byte 0x03
        "00 13",    # 0054: Push unsigned byte 0x13
        "00 13",    # 0056: Push unsigned byte 0x13
        "00 07",    # 0058: Push unsigned byte 0x07
        "58 C7",    # 005A: Print text ("The blue bottle is empty.")
        # PURPLE_BOTTLE_STATUS
        "C2",       # 005C: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 005D: Push object's flags
        "00 02",    # 005F: Push unsigned byte 0x02
        "7E",       # 0061: Bitwise AND
        "BE",       # 0062: Convert to boolean
        "44 7B 00", # 0063: If false, jump to PURPLE_BOTTLE_EMPTY
        # PURPLE_BOTTLE_FULL
        "00 F0",    # 0066: Push unsigned byte 0xF0
        "14 09 01", # 0068: Push short 0x0109
        "14 00 08", # 006B: Push short 0x0800
        "00 03",    # 006E: Push unsigned byte 0x03
        "00 1D",    # 0070: Push unsigned byte 0x1D
        "00 15",    # 0072: Push unsigned byte 0x15
        "00 02",    # 0074: Push unsigned byte 0x02
        "58 C7",    # 0076: Print text ("The purple bottle contains toxic water.")
        "48 8D 00", # 0078: Jump to EXAMINE_DONE
        # PURPLE_BOTTLE_EMPTY
        "00 F0",    # 007B: Push unsigned byte 0xF0
        "14 08 01", # 007D: Push short 0x0108
        "14 00 08", # 0080: Push short 0x0800
        "00 03",    # 0083: Push unsigned byte 0x03
        "00 15",    # 0085: Push unsigned byte 0x15
        "00 15",    # 0087: Push unsigned byte 0x15
        "00 06",    # 0089: Push unsigned byte 0x06 <-- Was 0x05
        "58 C7",    # 008B: Print text ("The purple bottle is empty.")
        # EXAMINE_DONE
        "48 3B 01", # 008D: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_PICKUP
        "16 02",    # 0090: Push short from $13+02 <-- Selected menu option
        "00 10",    # 0092: Push unsigned byte 0x10
        "AA",       # 0094: Check if equal
        "44 A5 00", # 0095: If not equal, jump to CHECK_IF_USE
        # PICKUP
        # Interaction menu option: Pickup
        "C2",       # 0098: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0099: Set object's owner to Jake
        "52 4B 00", # 009B: Execute behaviour script 0x4B = "Got item" sound effect
        "0A FF",    # 009E: Push signed byte 0xFF
        "2C 01",    # 00A0: Pop byte to $13+01 <-- Whether object has an owner
        "48 3B 01", # 00A2: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_USE
        "16 02",    # 00A5: Push short from $13+02 <-- Selected menu option
        "14 00 01", # 00A7: Push short 0x0100
        "AA",       # 00AA: Check if equal
        "44 3B 01", # 00AB: If not equal, jump to BOTTOM_OF_LOOP
        # USE
        # Interaction menu option: Use
        "52 F9 00", # 00AE: Execute behaviour script 0xF9
        "58 D7",    # 00B1: ???
        "BA",       # 00B3: Duplicate
        "34 04",    # 00B4: Pop short to $13+04 <-- Object-id that the Potion Bottles are being used on
        "0A FF",    # 00B6: Push signed byte 0xFF
        "AA",       # 00B8: Check if equal
        "46 3B 01", # 00B9: If equal, jump to BOTTOM_OF_LOOP
        # CHECK_IF_WATER_FOUNTAIN
        "16 04",    # 00BC: Push short from $13+04 <-- Object-id that the Potion Bottles are being used on
        "14 2D 01", # 00BE: Push short 0x012D <-- Object-id of "Water Fountain"
        "AA",       # 00C1: Check if equal
        "44 F9 00", # 00C2: If not equal, jump to CHECK_IF_TOXIC_WATER
        # WATER_FOUNTAIN
        "C2",       # 00C5: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 00C6: Push object's flags
        "00 01",    # 00C8: Push unsigned byte 0x01
        "7E",       # 00CA: Bitwise AND
        "BE",       # 00CB: Convert to boolean
        "44 E2 00", # 00CC: If false, jump to COLLECT_WATER
        # ALREADY_HAVE_WATER
        "00 F0",    # 00CF: Push unsigned byte 0xF0
        "14 07 01", # 00D1: Push short 0x0107
        "C0",       # 00D4: Push zero
        "00 03",    # 00D5: Push unsigned byte 0x03
        "00 18",    # 00D7: Push unsigned byte 0x18
        "00 15",    # 00D9: Push unsigned byte 0x15
        "00 04",    # 00DB: Push unsigned byte 0x04
        "58 C7",    # 00DD: Print text ("The blue bottle contains water.")
        "48 3B 01", # 00DF: Jump to BOTTOM_OF_LOOP
        # COLLECT_WATER
        "00 01",    # 00E2: Push unsigned byte 0x01
        "BA",       # 00E4: Duplicate
        "58 9E",    # 00E5: Register menu options / time delay
        "BC",       # 00E7: Pop
        "00 80",    # 00E8: Push unsigned byte 0x80
        "16 04",    # 00EA: Push short from $13+04 <-- Object-id that the Potion Bottles are being used on
        "58 0D",    # 00EC: Set bits of object's flags
        "00 01",    # 00EE: Push unsigned byte 0x01
        "C2",       # 00F0: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 00F1: Set bits of object's flags
        "52 4B 00", # 00F3: Execute behaviour script 0x4B = "Got item" sound effect
        "48 3B 01", # 00F6: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_TOXIC_WATER
        "16 04",    # 00F9: Push short from $13+04 <-- Object-id that the Potion Bottles are being used on
        "14 22 02", # 00FB: Push short 0x0222 <-- Object-id of "Toxic Water"
        "AA",       # 00FE: Check if equal
        "44 36 01", # 00FF: If not equal, jump to NOT_USING_IT_ON_THAT
        # TOXIC_WATER
        "C2",       # 0102: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 0103: Push object's flags
        "00 02",    # 0105: Push unsigned byte 0x02
        "7E",       # 0107: Bitwise AND
        "BE",       # 0108: Convert to boolean
        "44 1F 01", # 0109: If false, jump to COLLECT_TOXIC_WATER
        # ALREADY_HAVE_TOXIC_WATER
        "00 F0",    # 010C: Push unsigned byte 0xF0
        "14 09 01", # 010E: Push short 0x0109
        "C0",       # 0111: Push zero
        "00 03",    # 0112: Push unsigned byte 0x03
        "00 1D",    # 0114: Push unsigned byte 0x1D
        "00 15",    # 0116: Push unsigned byte 0x15
        "00 02",    # 0118: Push unsigned byte 0x02
        "58 C7",    # 011A: Print text ("The purple bottle contains toxic water.")
        "48 3B 01", # 011C: Jump to BOTTOM_OF_LOOP
        # COLLECT_TOXIC_WATER
        "00 01",    # 011F: Push unsigned byte 0x01
        "BA",       # 0121: Duplicate
        "58 9E",    # 0122: Register menu options / time delay
        "BC",       # 0124: Pop
        "00 80",    # 0125: Push unsigned byte 0x80
        "16 04",    # 0127: Push short from $13+04 <-- Object-id that the Potion Bottles are being used on
        "58 0D",    # 0129: Set bits of object's flags
        "00 02",    # 012B: Push unsigned byte 0x02
        "C2",       # 012D: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 012E: Set bits of object's flags
        "52 4B 00", # 0130: Execute behaviour script 0x4B = "Got item" sound effect
        "48 3B 01", # 0133: Jump to BOTTOM_OF_LOOP
        # NOT_USING_IT_ON_THAT
        "16 04",    # 0136: Push short from $13+04 <-- Object-id that the Potion Bottles are being used on
        "52 85 00", # 0138: Execute behaviour script 0x85 = "I'm not using it on..." helper script (generic)
        # BOTTOM_OF_LOOP
        "0C 01",    # 013B: Push signed byte from $13+01 <-- Whether object has an owner
        "44 0C 00", # 013D: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 0140: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0141: Despawn object
        "56",       # 0143: End
    ],
)
# Use the Talisman Case's sprite data (0xD016 --> 0xCFEC)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xA5), 0xCFEC)

# Potion Bottles: Talisman Case
# Offer for sale the new item shuffled to this location
romBytes[0xE5D8F:0xE5D8F+2] = romBytes[0xC96F5:0xC96F5+2]

# Black Bottle
expandedOffset = scriptHelper(
    scriptNumber = 0x349,
    argsLen      = 0x02, # Script 0x349 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x349 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x06, # Header byte: Script uses 0x06 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        # TOP_OF_LOOP
        "C2",       # 000C: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 000D: Check if object has an owner
        "2C 01",    # 000F: Pop byte to $13+01 <-- Whether object has an owner
        "14 00 01", # 0011: Push short 0x0100
        "0C 01",    # 0014: Push signed byte from $13+01 <-- Whether object has an owner
        "52 AA 02", # 0016: Execute behaviour script 0x2AA = Interaction menu helper
        "BA",       # 0019: Duplicate
        "34 02",    # 001A: Pop short to $13+02 <-- Selected menu option
        # CHECK_IF_EXAMINE
        "00 80",    # 001C: Push unsigned byte 0x80
        "AA",       # 001E: Check if equal
        "44 5F 00", # 001F: If not equal, jump to CHECK_IF_PICKUP
        # EXAMINE
        # Interaction menu option: Examine
        "00 03",    # 0022: Push unsigned byte 0x03
        "00 FF",    # 0024: Push unsigned byte 0xFF
        "00 32",    # 0026: Push unsigned byte 0x32
        "C2",       # 0028: Push unsigned byte from $13+00 <-- Spawn index
        "58 4C",    # 0029: Play sound effect
        # BOTTLE_STATUS
        "C2",       # 002B: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 002C: Push object's flags
        "00 01",    # 002E: Push unsigned byte 0x01
        "7E",       # 0030: Bitwise AND
        "BE",       # 0031: Convert to boolean
        "44 4A 00", # 0032: If false, jump to BOTTLE_EMPTY
        # BOTTLE_FULL
        "00 F0",    # 0035: Push unsigned byte 0xF0
        "14 05 01", # 0037: Push short 0x0105
        "14 00 08", # 003A: Push short 0x0800
        "00 03",    # 003D: Push unsigned byte 0x03
        "00 18",    # 003F: Push unsigned byte 0x18
        "00 15",    # 0041: Push unsigned byte 0x15
        "00 04",    # 0043: Push unsigned byte 0x04 <-- Was 0x05
        "58 C7",    # 0045: Print text ("The bottle contains incubus ink.")
        "48 5C 00", # 0047: Jump to EXAMINE_DONE
        # BOTTLE_EMPTY
        "00 F0",    # 004A: Push unsigned byte 0xF0
        "14 04 01", # 004C: Push short 0x0104
        "14 00 08", # 004F: Push short 0x0800
        "00 03",    # 0052: Push unsigned byte 0x03
        "00 10",    # 0054: Push unsigned byte 0x10
        "00 15",    # 0056: Push unsigned byte 0x15
        "00 08",    # 0058: Push unsigned byte 0x08 <-- Was 0x09
        "58 C7",    # 005A: Print text ("The bottle is empty.")
        # EXAMINE_DONE
        "48 B0 00", # 005C: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_PICKUP
        "16 02",    # 005F: Push short from $13+02 <-- Selected menu option
        "00 10",    # 0061: Push unsigned byte 0x10
        "AA",       # 0063: Check if equal
        "44 74 00", # 0064: If not equal, jump to CHECK_IF_USE
        # PICKUP
        # Interaction menu option: Pickup
        "C2",       # 0067: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0068: Set object's owner to Jake
        "52 4B 00", # 006A: Execute behaviour script 0x4B = "Got item" sound effect
        "0A FF",    # 006D: Push signed byte 0xFF
        "2C 01",    # 006F: Pop byte to $13+01 <-- Whether object has an owner
        "48 B0 00", # 0071: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_USE
        "16 02",    # 0074: Push short from $13+02 <-- Selected menu option
        "14 00 01", # 0076: Push short 0x0100
        "AA",       # 0079: Check if equal
        "44 B0 00", # 007A: If not equal, jump to BOTTOM_OF_LOOP
        # USE
        # Interaction menu option: Use
        "52 F9 00", # 007D: Execute behaviour script 0xF9
        "58 D7",    # 0080: ???
        "BA",       # 0082: Duplicate
        "34 04",    # 0083: Pop short to $13+04 <-- Object-id that the Black Bottle is being used on
        "0A FF",    # 0085: Push signed byte 0xFF
        "AA",       # 0087: Check if equal
        "46 B0 00", # 0088: If equal, jump to BOTTOM_OF_LOOP
        # CHECK_IF_POOL_OF_INK
        "16 04",    # 008B: Push short from $13+04 <-- Object-id that the Black Bottle is being used on
        "14 66 06", # 008D: Push short 0x0666 <-- Object-id of "Pool of Ink"
        "AA",       # 0090: Check if equal
        "44 AB 00", # 0091: If not equal, jump to NOT_USING_IT_ON_THAT
        # COLLECT_INK
        "00 01",    # 0094: Push unsigned byte 0x01
        "BA",       # 0096: Duplicate
        "58 9E",    # 0097: Register menu options / time delay
        "BC",       # 0099: Pop
        "00 80",    # 009A: Push unsigned byte 0x80
        "16 04",    # 009C: Push short from $13+04 <-- Object-id that the Black Bottle is being used on
        "58 0D",    # 009E: Set bits of object's flags
        "00 01",    # 00A0: Push unsigned byte 0x01
        "C2",       # 00A2: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 00A3: Set bits of object's flags
        "52 4B 00", # 00A5: Execute behaviour script 0x4B = "Got item" sound effect <-- Absent in vanilla!
        "48 B0 00", # 00A8: Jump to BOTTOM_OF_LOOP
        # NOT_USING_IT_ON_THAT
        "16 04",    # 00AB: Push short from $13+04 <-- Object-id that the Black Bottle is being used on
        "52 85 00", # 00AD: Execute behaviour script 0x85 = "I'm not using it on..." helper script (generic)
        # BOTTOM_OF_LOOP
        "0C 01",    # 00B0: Push signed byte from $13+01 <-- Whether object has an owner
        "44 0C 00", # 00B2: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 00B5: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 00B6: Despawn object
        "56",       # 00B8: End
    ],
)
# Use the Talisman Case's sprite data (0xD02A --> 0xCFEC)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xA6), 0xCFEC)

# Black Bottle: Talisman Case
# Offer for sale the new item shuffled to this location
romBytes[0xE5DA2:0xE5DA2+2] = romBytes[0xC96FB:0xC96FB+2]

# Stake
expandedOffset = scriptHelper(
    scriptNumber = 0x57,
    argsLen      = 0x02, # Script 0x57 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x57 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x06, # Header byte: Script uses 0x06 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        # TOP_OF_LOOP
        "C2",       # 000C: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 000D: Check if object has an owner
        "2C 01",    # 000F: Pop byte to $13+01 <-- Whether object has an owner
        "14 00 01", # 0011: Push short 0x0100
        "0C 01",    # 0014: Push signed byte from $13+01 <-- Whether object has an owner
        "52 AA 02", # 0016: Execute behaviour script 0x2AA = Interaction menu helper
        "BA",       # 0019: Duplicate
        "34 02",    # 001A: Pop short to $13+02 <-- Selected menu option
        # CHECK_IF_EXAMINE
        "00 80",    # 001C: Push unsigned byte 0x80
        "AA",       # 001E: Check if equal
        "44 40 00", # 001F: If not equal, jump to CHECK_IF_PICKUP
        # EXAMINE
        # Interaction menu option: Examine
        "00 03",    # 0022: Push unsigned byte 0x03
        "00 FF",    # 0024: Push unsigned byte 0xFF
        "00 32",    # 0026: Push unsigned byte 0x32
        "C2",       # 0028: Push unsigned byte from $13+00 <-- Spawn index
        "58 4C",    # 0029: Play sound effect
        "00 F0",    # 002B: Push unsigned byte 0xF0
        "14 0B 01", # 002D: Push short 0x010B
        "14 00 08", # 0030: Push short 0x0800
        "00 03",    # 0033: Push unsigned byte 0x03
        "00 10",    # 0035: Push unsigned byte 0x10
        "00 15",    # 0037: Push unsigned byte 0x15
        "00 02",    # 0039: Push unsigned byte 0x02
        "58 C7",    # 003B: Print text ("Sharp wooden stake.")
        "48 CE 00", # 003D: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_PICKUP
        "16 02",    # 0040: Push short from $13+02 <-- Selected menu option
        "00 10",    # 0042: Push unsigned byte 0x10
        "AA",       # 0044: Check if equal
        "44 55 00", # 0045: If not equal, jump to CHECK_IF_USE
        # PICKUP
        # Interaction menu option: Pickup
        "C2",       # 0048: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0049: Set object's owner to Jake
        "52 4B 00", # 004B: Execute behaviour script 0x4B = "Got item" sound effect
        "0A FF",    # 004E: Push signed byte 0xFF
        "2C 01",    # 0050: Pop byte to $13+01 <-- Whether object has an owner
        "48 CE 00", # 0052: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_USE
        "16 02",    # 0055: Push short from $13+02 <-- Selected menu option
        "14 00 01", # 0057: Push short 0x0100
        "AA",       # 005A: Check if equal
        "44 CE 00", # 005B: If not equal, jump to BOTTOM_OF_LOOP
        # USE
        # Interaction menu option: Use
        "52 F9 00", # 005E: Execute behaviour script 0xF9
        "58 D7",    # 0061: ???
        "BA",       # 0063: Duplicate
        "34 04",    # 0064: Pop short to $13+04 <-- Object-id that the Stake is being used on
        "0A FF",    # 0066: Push signed byte 0xFF
        "AA",       # 0068: Check if equal
        "46 CE 00", # 0069: If equal, jump to BOTTOM_OF_LOOP
        # CHECK_IF_VAMPIRE
        "16 04",    # 006C: Push short from $13+04 <-- Object-id that the Stake is being used on
        "14 88 01", # 006E: Push short 0x0188 <-- Object-id of "Vampire!"
        "AA",       # 0071: Check if equal
        "44 C9 00", # 0072: If not equal, jump to NOT_USING_IT_ON_THAT
        # VAMPIRE
        "58 7F",    # 0075: ???
        "14 88 01", # 0077: Push short 0x0188 <-- Object-id of "Vampire!"
        "58 BA",    # 007A: Push object's flags
        "00 80",    # 007C: Push unsigned byte 0x80
        "7E",       # 007E: Bitwise AND
        "BE",       # 007F: Convert to boolean
        "44 B4 00", # 0080: If false, jump to VAMPIRE_NOT_STROBED
        # CHECK_IF_ALREADY_STAKED_TWICE
        "16 04",    # 0083: Push short from $13+04 <-- Object-id that the Stake is being used on
        "58 BA",    # 0085: Push object's flags
        "00 02",    # 0087: Push unsigned byte 0x02
        "7E",       # 0089: Bitwise AND
        "BE",       # 008A: Convert to boolean
        "44 97 00", # 008B: If false, jump to CHECK_IF_ALREADY_STAKED_ONCE
        # APPLY_THIRD_STAKING
        "00 04",    # 008E: Push unsigned byte 0x04
        "16 04",    # 0090: Push short from $13+04 <-- Object-id that the Stake is being used on
        "58 0D",    # 0092: Set bits of object's flags
        "48 CE 00", # 0094: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_ALREADY_STAKED_ONCE
        "16 04",    # 0097: Push short from $13+04 <-- Object-id that the Stake is being used on
        "58 BA",    # 0099: Push object's flags
        "00 01",    # 009B: Push unsigned byte 0x01
        "7E",       # 009D: Bitwise AND
        "BE",       # 009E: Convert to boolean
        "44 AB 00", # 009F: If false, jump to APPLY_FIRST_STAKING
        # APPLY_SECOND_STAKING
        "00 02",    # 00A2: Push unsigned byte 0x02
        "16 04",    # 00A4: Push short from $13+04 <-- Object-id that the Stake is being used on
        "58 0D",    # 00A6: Set bits of object's flags
        "48 CE 00", # 00A8: Jump to BOTTOM_OF_LOOP
        # APPLY_FIRST_STAKING
        "00 01",    # 00AB: Push unsigned byte 0x01
        "16 04",    # 00AD: Push short from $13+04 <-- Object-id that the Stake is being used on
        "58 0D",    # 00AF: Set bits of object's flags
        "48 CE 00", # 00B1: Jump to BOTTOM_OF_LOOP
        # VAMPIRE_NOT_STROBED
        "00 B4",    # 00B4: Push unsigned byte 0xB4
        "14 BC 01", # 00B6: Push short 0x01BC
        "14 00 08", # 00B9: Push short 0x0800
        "00 03",    # 00BC: Push unsigned byte 0x03
        "00 15",    # 00BE: Push unsigned byte 0x15
        "00 15",    # 00C0: Push unsigned byte 0x15
        "00 02",    # 00C2: Push unsigned byte 0x02
        "58 C7",    # 00C4: Print text ("You can't get close enough.")
        "48 CE 00", # 00C6: Jump to BOTTOM_OF_LOOP
        # NOT_USING_IT_ON_THAT
        "16 04",    # 00C9: Push short from $13+04 <-- Object-id that the Stake is being used on
        "52 85 00", # 00CB: Execute behaviour script 0x85 = "I'm not using it on..." helper script (generic)
        # BOTTOM_OF_LOOP
        "0C 01",    # 00CE: Push signed byte from $13+01 <-- Whether object has an owner
        "44 0C 00", # 00D0: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 00D3: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 00D4: Despawn object
        "56",       # 00D6: End
    ],
)
# Use the Talisman Case's sprite data (0xCB9A --> 0xCFEC)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0x9B), 0xCFEC)

# Stake: Talisman Case
# Offer for sale the new item shuffled to this location
romBytes[0xE5DB5:0xE5DB5+2] = romBytes[0xC9707:0xC9707+2]

# Colt L36 Pistol: Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xE5F3B:0xE5F3B+2] = romBytes[0xC9649:0xC9649+2]

# Viper H. Pistol ($4,000): Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xE5F4D:0xE5F4D+2] = romBytes[0xC964F:0xC964F+2]

# Mesh Jacket ($5,000): Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xE5F5F:0xE5F5F+2] = romBytes[0xC9655:0xC9655+2]

# T-250 Shotgun ($15,000): Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xE5F71:0xE5F71+2] = romBytes[0xC965B:0xC965B+2]

# Fichetti L. Pistol: Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xE5F83:0xE5F83+2] = romBytes[0xC966D:0xC966D+2]

# Warhawk H. Pistol: Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xE5F95:0xE5F95+2] = romBytes[0xC9673:0xC9673+2]

# Glass doors <-- Left door at Oldtown monorail station
# Change the behaviour script for the left glass door from 0x2B4
# (closed door) to 0x37B (do nothing).
# With this change, the glass door will no longer appear.
# We do this to make the doorway easier to traverse.
struct.pack_into("<H", romBytes, 0x6C0A5, 0x037B)

# Glass doors <-- Right door at Oldtown monorail station
# Change the behaviour script for the right glass door from 0xAD
# (closed door) to 0x37B (do nothing).
# With this change, the glass door will no longer appear.
# We do this to make the doorway easier to traverse.
struct.pack_into("<H", romBytes, 0x6C09E, 0x037B)

# Mono-Rail Car (Tenth Street to Oldtown) waypoints
writeHelper(romBytes, 0xCA0DF, bytes.fromhex(' '.join([
    "2E 02",    # Change waypoint #4 (sliding doors) Y coordinate from 559 to 558
])))

# Mono-Rail Car (Tenth Street to Oldtown) driver car
# Remove the arrival delay
expandedOffset = scriptHelper(
    scriptNumber = 0x186,
    argsLen      = 0x02, # Script 0x186 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x186 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 03",    # 0002: Push unsigned byte 0x03
        "C2",       # 0004: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 0005: Move object instantly to waypoint?
        "00 7F",    # 0007: Push unsigned byte 0x7F
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 000A: Clear bits of object's flags
        "00 02",    # 000C: Push unsigned byte 0x02
        "C0",       # 000E: Push zero
        "C2",       # 000F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0010: Display sprite with facing direction
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0013: ???
        "56",       # 0015: End
    ],
)

# Mono-Rail Car (Tenth Street to Oldtown) passenger car
# Remove the arrival delay
expandedOffset = scriptHelper(
    scriptNumber = 0xC1,
    argsLen      = 0x02, # Script 0xC1 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0xC1 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 05",    # 0002: Push unsigned byte 0x05
        "C2",       # 0004: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 0005: Move object instantly to waypoint?
        "00 7F",    # 0007: Push unsigned byte 0x7F
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 000A: Clear bits of object's flags
        "00 06",    # 000C: Push unsigned byte 0x06
        "C0",       # 000E: Push zero
        "C2",       # 000F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0010: Display sprite with facing direction
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0013: ???
        "56",       # 0015: End
    ],
)

# Mono-Rail Car (Tenth Street to Oldtown) sliding doors
# Remove the arrival delay
expandedOffset = scriptHelper(
    scriptNumber = 0x288,
    argsLen      = 0x02, # Script 0x288 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x288 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 04",    # 0002: Push unsigned byte 0x04
        "C2",       # 0004: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 0005: Move object instantly to waypoint?
        "00 7E",    # 0007: Push unsigned byte 0x7E
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 000A: Clear bits of object's flags
        "00 03",    # 000C: Push unsigned byte 0x03
        "C0",       # 000E: Push zero
        "C2",       # 000F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0010: Display sprite with facing direction
        "00 02",    # 0012: Push unsigned byte 0x02
        "C2",       # 0014: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0015: Display sprite
        "00 14",    # 0017: Push unsigned byte 0x14
        "00 01",    # 0019: Push unsigned byte 0x01
        "58 9E",    # 001B: Register menu options / time delay
        "BC",       # 001D: Pop
        "00 04",    # 001E: Push unsigned byte 0x04
        "C2",       # 0020: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0021: Display sprite
        "C0",       # 0023: Push zero
        "00 08",    # 0024: Push unsigned byte 0x08
        "58 9E",    # 0026: Register menu options / time delay
        "BC",       # 0028: Pop
        "00 01",    # 0029: Push unsigned byte 0x01
        "C2",       # 002B: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 002C: Set bits of object's flags
        "C0",       # 002E: Push zero
        "C2",       # 002F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0030: Display sprite
        "C2",       # 0032: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0033: ???
        "56",       # 0035: End
    ],
)

# Mono-Rail Car (Tenth Street to Oldtown) destination coordinates
writeHelper(romBytes, 0x692AF + (9 * 0x95) + 3, bytes.fromhex(' '.join([
    "65 01",    # Update the destination coordinates
    "F5 01",    # Old coordinates: (364, 518, 112)
    "70 00",    # New coordinates: (357, 501, 112)
])))

# Mono-Rail Car (Oldtown to Tenth Street) waypoints
writeHelper(romBytes, 0xCA2A3, bytes.fromhex(' '.join([
    "2E 02",    # Change waypoint #4 (sliding doors) Y coordinate from 559 to 558
])))

# Mono-Rail Car (Oldtown to Tenth Street) driver car
# Remove the arrival delay
expandedOffset = scriptHelper(
    scriptNumber = 0x187,
    argsLen      = 0x02, # Script 0x187 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x187 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 03",    # 0002: Push unsigned byte 0x03
        "C2",       # 0004: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 0005: Move object instantly to waypoint?
        "00 7F",    # 0007: Push unsigned byte 0x7F
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 000A: Clear bits of object's flags
        "00 02",    # 000C: Push unsigned byte 0x02
        "C0",       # 000E: Push zero
        "C2",       # 000F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0010: Display sprite with facing direction
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0013: ???
        "56",       # 0015: End
    ],
)

# Mono-Rail Car (Oldtown to Tenth Street) passenger car
# Remove the arrival delay
expandedOffset = scriptHelper(
    scriptNumber = 0xC2,
    argsLen      = 0x02, # Script 0xC2 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0xC2 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 05",    # 0002: Push unsigned byte 0x05
        "C2",       # 0004: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 0005: Move object instantly to waypoint?
        "00 7F",    # 0007: Push unsigned byte 0x7F
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 000A: Clear bits of object's flags
        "00 06",    # 000C: Push unsigned byte 0x06
        "C0",       # 000E: Push zero
        "C2",       # 000F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0010: Display sprite with facing direction
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0013: ???
        "56",       # 0015: End
    ],
)

# Mono-Rail Car (Oldtown to Tenth Street) sliding doors
# Remove the arrival delay
expandedOffset = scriptHelper(
    scriptNumber = 0x289,
    argsLen      = 0x02, # Script 0x289 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x289 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 04",    # 0002: Push unsigned byte 0x04
        "C2",       # 0004: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 0005: Move object instantly to waypoint?
        "00 7E",    # 0007: Push unsigned byte 0x7E
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 000A: Clear bits of object's flags
        "00 03",    # 000C: Push unsigned byte 0x03
        "C0",       # 000E: Push zero
        "C2",       # 000F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0010: Display sprite with facing direction
        "00 02",    # 0012: Push unsigned byte 0x02
        "C2",       # 0014: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0015: Display sprite
        "00 14",    # 0017: Push unsigned byte 0x14
        "00 01",    # 0019: Push unsigned byte 0x01
        "58 9E",    # 001B: Register menu options / time delay
        "BC",       # 001D: Pop
        "00 04",    # 001E: Push unsigned byte 0x04
        "C2",       # 0020: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0021: Display sprite
        "C0",       # 0023: Push zero
        "00 08",    # 0024: Push unsigned byte 0x08
        "58 9E",    # 0026: Register menu options / time delay
        "BC",       # 0028: Pop
        "00 01",    # 0029: Push unsigned byte 0x01
        "C2",       # 002B: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 002C: Set bits of object's flags
        "C0",       # 002E: Push zero
        "C2",       # 002F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0030: Display sprite
        "C2",       # 0032: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0033: ???
        "56",       # 0035: End
    ],
)

# Mono-Rail Car (Oldtown to Tenth Street) destination coordinates
writeHelper(romBytes, 0x692AF + (9 * 0x8B) + 3, bytes.fromhex(' '.join([
    "65 01",    # Update the destination coordinates
    "F5 01",    # Old coordinates: (370, 512, 112)
    "70 00",    # New coordinates: (357, 501, 112)
])))

# Mono-Rail Car (Oldtown to Downtown) waypoints
writeHelper(romBytes, 0xD1C57, bytes.fromhex(' '.join([
    "BD 01",    # Change waypoint #3 (driver car) Y coordinate from 435 to 445
])))
writeHelper(romBytes, 0xD1C5D, bytes.fromhex(' '.join([
    "9A 01",    # Change waypoint #4 (passenger car) Y coordinate from 400 to 410
])))
writeHelper(romBytes, 0xD1C61, bytes.fromhex(' '.join([
    "04 02",    # Change waypoint #5 (sliding doors) X coordinate from 517 to 516
    "A6 01",    # Change waypoint #5 (sliding doors) Y coordinate from 412 to 422
])))

# Mono-Rail Car (Oldtown to Downtown) driver car
# Remove the arrival delay
expandedOffset = scriptHelper(
    scriptNumber = 0x191,
    argsLen      = 0x02, # Script 0x191 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x191 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 03",    # 0002: Push unsigned byte 0x03
        "C2",       # 0004: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 0005: Move object instantly to waypoint?
        "00 7F",    # 0007: Push unsigned byte 0x7F
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 000A: Clear bits of object's flags
        "00 00",    # 000C: Push unsigned byte 0x00
        "C0",       # 000E: Push zero
        "C2",       # 000F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0010: Display sprite with facing direction
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0013: ???
        "56",       # 0015: End
    ],
)

# Mono-Rail Car (Oldtown to Downtown) passenger car
# Remove the arrival delay
expandedOffset = scriptHelper(
    scriptNumber = 0xCB,
    argsLen      = 0x02, # Script 0xCB now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0xCB now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 04",    # 0002: Push unsigned byte 0x04
        "C2",       # 0004: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 0005: Move object instantly to waypoint?
        "00 7F",    # 0007: Push unsigned byte 0x7F
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 000A: Clear bits of object's flags
        "00 04",    # 000C: Push unsigned byte 0x04
        "C0",       # 000E: Push zero
        "C2",       # 000F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0010: Display sprite with facing direction
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0013: ???
        "56",       # 0015: End
    ],
)

# Mono-Rail Car (Oldtown to Downtown) sliding doors
# Remove the arrival delay
expandedOffset = scriptHelper(
    scriptNumber = 0x28F,
    argsLen      = 0x02, # Script 0x28F now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x28F now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 05",    # 0002: Push unsigned byte 0x05
        "C2",       # 0004: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 0005: Move object instantly to waypoint?
        "00 7E",    # 0007: Push unsigned byte 0x7E
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 000A: Clear bits of object's flags
        "00 07",    # 000C: Push unsigned byte 0x07
        "C0",       # 000E: Push zero
        "C2",       # 000F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0010: Display sprite with facing direction
        "00 02",    # 0012: Push unsigned byte 0x02
        "C2",       # 0014: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0015: Display sprite
        "00 14",    # 0017: Push unsigned byte 0x14
        "00 01",    # 0019: Push unsigned byte 0x01
        "58 9E",    # 001B: Register menu options / time delay
        "BC",       # 001D: Pop
        "00 04",    # 001E: Push unsigned byte 0x04
        "C2",       # 0020: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0021: Display sprite
        "C0",       # 0023: Push zero
        "00 08",    # 0024: Push unsigned byte 0x08
        "58 9E",    # 0026: Register menu options / time delay
        "BC",       # 0028: Pop
        "00 01",    # 0029: Push unsigned byte 0x01
        "C2",       # 002B: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 002C: Set bits of object's flags
        "C0",       # 002E: Push zero
        "C2",       # 002F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0030: Display sprite
        "C2",       # 0032: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0033: ???
        "56",       # 0035: End
    ],
)

# Mono-Rail Car (Oldtown to Downtown) destination coordinates
writeHelper(romBytes, 0x692AF + (9 * 0x20) + 3, bytes.fromhex(' '.join([
    "B8 01",    # Update the destination coordinates
    "B8 01",    # Old coordinates: (448, 432,  64)
    "40 00",    # New coordinates: (440, 440,  64)
])))

# Mono-Rail Car (Downtown to Oldtown) waypoints
writeHelper(romBytes, 0xCA789, bytes.fromhex(' '.join([
    "EF 01",    # Change waypoint #3 (driver car) Y coordinate from 485 to 495
])))
writeHelper(romBytes, 0xCA78F, bytes.fromhex(' '.join([
    "CC 01",    # Change waypoint #4 (passenger car) Y coordinate from 450 to 460
])))
writeHelper(romBytes, 0xCA793, bytes.fromhex(' '.join([
    "16 02",    # Change waypoint #5 (sliding doors) X coordinate from 535 to 534
    "D8 01",    # Change waypoint #5 (sliding doors) Y coordinate from 462 to 472
])))

# Mono-Rail Car (Downtown to Oldtown) driver car
# Remove the arrival delay
expandedOffset = scriptHelper(
    scriptNumber = 0x192,
    argsLen      = 0x02, # Script 0x192 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x192 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 03",    # 0002: Push unsigned byte 0x03
        "C2",       # 0004: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 0005: Move object instantly to waypoint?
        "00 7F",    # 0007: Push unsigned byte 0x7F
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 000A: Clear bits of object's flags
        "00 00",    # 000C: Push unsigned byte 0x00
        "C0",       # 000E: Push zero
        "C2",       # 000F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0010: Display sprite with facing direction
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0013: ???
        "56",       # 0015: End
    ],
)

# Mono-Rail Car (Downtown to Oldtown) passenger car
# Remove the arrival delay
expandedOffset = scriptHelper(
    scriptNumber = 0xCC,
    argsLen      = 0x02, # Script 0xCC now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0xCC now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 04",    # 0002: Push unsigned byte 0x04
        "C2",       # 0004: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 0005: Move object instantly to waypoint?
        "00 7F",    # 0007: Push unsigned byte 0x7F
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 000A: Clear bits of object's flags
        "00 04",    # 000C: Push unsigned byte 0x04
        "C0",       # 000E: Push zero
        "C2",       # 000F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0010: Display sprite with facing direction
        "C2",       # 0012: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0013: ???
        "56",       # 0015: End
    ],
)

# Mono-Rail Car (Downtown to Oldtown) sliding doors
# Remove the arrival delay
expandedOffset = scriptHelper(
    scriptNumber = 0x290,
    argsLen      = 0x02, # Script 0x290 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x290 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 05",    # 0002: Push unsigned byte 0x05
        "C2",       # 0004: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 0005: Move object instantly to waypoint?
        "00 7E",    # 0007: Push unsigned byte 0x7E
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 000A: Clear bits of object's flags
        "00 07",    # 000C: Push unsigned byte 0x07
        "C0",       # 000E: Push zero
        "C2",       # 000F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0010: Display sprite with facing direction
        "00 02",    # 0012: Push unsigned byte 0x02
        "C2",       # 0014: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0015: Display sprite
        "00 14",    # 0017: Push unsigned byte 0x14
        "00 01",    # 0019: Push unsigned byte 0x01
        "58 9E",    # 001B: Register menu options / time delay
        "BC",       # 001D: Pop
        "00 04",    # 001E: Push unsigned byte 0x04
        "C2",       # 0020: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0021: Display sprite
        "C0",       # 0023: Push zero
        "00 08",    # 0024: Push unsigned byte 0x08
        "58 9E",    # 0026: Register menu options / time delay
        "BC",       # 0028: Pop
        "00 01",    # 0029: Push unsigned byte 0x01
        "C2",       # 002B: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 002C: Set bits of object's flags
        "C0",       # 002E: Push zero
        "C2",       # 002F: Push unsigned byte from $13+00 <-- Spawn index
        "58 D0",    # 0030: Display sprite
        "C2",       # 0032: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0033: ???
        "56",       # 0035: End
    ],
)

# Mono-Rail Car (Downtown to Oldtown) destination coordinates
writeHelper(romBytes, 0x692AF + (9 * 0x18D) + 3, bytes.fromhex(' '.join([
    "C1 01",    # Update the destination coordinates
    "91 01",    # Old coordinates: (462, 396, 104)
    "68 00",    # New coordinates: (449, 401, 104)
])))

# Iron Key
writeHelper(romBytes, 0xCA7B5, bytes.fromhex(' '.join([
    "6F 02",    # Move the spawn point to slightly below the Ferocious Orc
    "1C 1A",    # New coordinates: (623, 540, 96)
])))
writeHelper(romBytes, 0xF448C, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    "48 12 00", # 000C: Jump to 0012
])))
# Use facing direction 05's sprite for direction 00
romBytes[0x65F10] = 0x08

# Iron Key: Ferocious Orc
# Skip the automatic conversation after defeating the Ferocious Orc
# Reveal the new item shuffled to this location
writeHelper(romBytes, 0xF905F, bytes.fromhex(' '.join([
    "C0",       # 0006: Push zero
    "BE",       # 0007: Convert to boolean
    "BE",       # 0008: Convert to boolean
    "BE",       # 0009: Convert to boolean
    "BC",       # 000A: Pop
    "00 80",    # 000B: Push unsigned byte 0x80
    f"14 {romBytes[0xCA7B9+0]:02X} {romBytes[0xCA7B9+1]:02X}",
                # 000D: Push short 0x#### <-- Object-id of new item in "Iron Key" location
    "58 0D",    # 0010: Set bits of object's flags
])))

# Doggie <-- Daley Station
# Change the behaviour script for the Doggie from 0x1F8 (Doggie at
# Daley Station) to 0x37B (do nothing).
# With this change, the Doggie will no longer appear.
# We do this to skip the Doggie's automatic conversation.
# Additionally, script 0x1F8 should now be entirely unused.
struct.pack_into("<H", romBytes, 0x6C559, 0x037B)

# Doorway from Maplethorpe Plaza into Maplethorpe's waiting room
# Enlarge the doorway warp zone to make it easier to traverse
romBytes[0xCB2F0] = 0x16 # <-- Was 0x17

# Club Manager <-- Bartender at Wastelands
# Change conversation when you know the "Bremerton" keyword.
# In vanilla, this happens when you know either "Nirwanda" or "Laughlyn".
romBytes[0xF68C1] = 0x04 # Keyword-id for "Bremerton"
romBytes[0xF68C5] = 0x04 # Keyword-id for "Bremerton"

# A Busy Man <-- Ice delivery guy at Wastelands
# Appear when you know the "Bremerton" keyword.
# In vanilla, this happens when you know either "Nirwanda" or "Laughlyn".
romBytes[0xF69A9] = 0x04 # Keyword-id for "Bremerton"
romBytes[0xF69AD] = 0x04 # Keyword-id for "Bremerton"

# Heavy Dude <-- Guarding entrance to Rust Stiletto turf
# Skip the automatic conversation when entering Rust Stiletto turf
writeHelper(romBytes, 0xF9143, bytes.fromhex(' '.join([
    "C0",       # 0012: Push zero
    "BE",       # 0013: Convert to boolean
    "BE",       # 0014: Convert to boolean
    "BE",       # 0015: Convert to boolean
    "BE",       # 0016: Convert to boolean
    "BC",       # 0017: Pop
])))

# Crowbar
writeHelper(romBytes, 0xD0823, bytes.fromhex(' '.join([
    "70 01",    # Move the spawn point to slightly below the Ferocious Orc's waypoint
    "B3 11",    # New coordinates: (368, 435, 64)
])))
writeHelper(romBytes, 0xF4320, bytes.fromhex(' '.join([
    "52 1D 01", # 0003: Execute behaviour script 0x11D = New item-drawing script
])))
# Increase the Crowbar's sprite priority
romBytes[0x6C6B9] |= 0x40
# Inventory list item-hiding
# Don't hide the Crowbar after taking the helicopter to Drake Volcano
romBytes[0x6C6B9] |= 0x3F

# Crowbar: Ferocious Orc
# Reveal the new item shuffled to this location
romBytes[0xF95F4:0xF95F4+2] = romBytes[0xD0827:0xD0827+2]

# Password (Drake)
writeHelper(romBytes, 0xD08E9, bytes.fromhex(' '.join([
    "E3 02",    # Move the spawn point to slightly below the Gang Leader
    "FE 11",    # New coordinates: (739, 510, 64)
])))
writeHelper(romBytes, 0xF4909, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    "48 12 00", # 000C: Jump to 0012
])))
# Use facing direction 05's sprite for direction 00
romBytes[0x66864] = 0x08
# Inventory list item-hiding
# Don't hide the Password (Drake) after taking the helicopter to Drake Volcano
romBytes[0x6B79A] |= 0x3F

# Password (Drake): Gang Leader
# Skip the automatic conversation after defeating the Gang Leader
# Reveal the new item shuffled to this location
writeHelper(romBytes, 0xF90F1, bytes.fromhex(' '.join([
    "C0",       # 006A: Push zero
    "BE",       # 006B: Convert to boolean
    "BE",       # 006C: Convert to boolean
    "BE",       # 006D: Convert to boolean
    "BC",       # 006E: Pop
    "00 28",    # 006F: Push unsigned byte 0x28
    "58 57",    # 0071: Read short from 7E3BBB+n
    "86",       # 0073: Increment
    "00 28",    # 0074: Push unsigned byte 0x28
    "58 12",    # 0076: Write short to 7E3BBB+n
    "00 80",    # 0078: Push unsigned byte 0x80
    f"14 {romBytes[0xD08ED+0]:02X} {romBytes[0xD08ED+1]:02X}",
                # 007A: Push short 0x#### <-- Object-id of new item in "Password (Drake)" location
    "58 0D",    # 007D: Set bits of object's flags
])))

# Cruel man <-- Left bouncer at the entrance to Jagged Nails
# Allow access to Jagged Nails without having to defeat the Rust Stilettos
# Force the "always room for a true shadowrunner" conversation
writeHelper(romBytes, 0xF628E, bytes.fromhex(' '.join([
    "BE",       # 0018: Convert to boolean
    "BC",       # 0019: Pop
    "48 1D 00", # 001A: Jump to 001D
])))
# Truncate the "handled that Stilettos gang mighty fine" text
romBytes[0xE9950] = 0xB8
romBytes[0xE9951] = 0x80

# Kitsune
writeHelper(romBytes, 0xCB797, bytes.fromhex(' '.join([
    "3E 01",    # Move the spawn point to waypoint 0x04 on the nightclub map
    "9A 11",    # Waypoint 0x04 coordinates: (318, 410, 64)
])))
# Skip over the code for Kitsune's on-stage behaviour
writeHelper(romBytes, 0xF6317, bytes.fromhex(' '.join([
    "48 80 01", # 0002: Jump to 0180
])))

# TODO: Leaves <-- Not currently subject to randomization

# TODO: Strobe <-- Not currently subject to randomization
# Inventory list item-hiding
# Don't hide the Strobe after taking the helicopter to Drake Volcano
romBytes[0x6B2DF] |= 0x3F

# Explosives
writeHelper(romBytes, 0xCA609, bytes.fromhex(' '.join([
    "E1 81",    # Move the spawn point to slightly below the Massive Orc
    "F4 19",    # New coordinates: (481, 500, 112)
])))
writeHelper(romBytes, 0xF4173, bytes.fromhex(' '.join([
    "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    "48 25 00", # 000C: Jump to 0025
])))
# Inventory list item-hiding
# Don't hide the Explosives after taking the helicopter to Drake Volcano
romBytes[0x6C3D3] |= 0x3F
# Make the Explosives not inherently subject to gravity
romBytes[0x675BA] &= ~0x20

# Explosives: Massive Orc
# Appear after ice has been delivered to the docks.
# In vanilla, this happens after learning "Nirwanda" or "Laughlyn".
# Previously, the Massive Orc appeared after learning "Bremerton".
# This worked, but if you learned "Bremerton" early, it made getting
# the "Docks" keyword from the taxiboat driver difficult.
writeHelper(romBytes, 0xFA9EC, bytes.fromhex(' '.join([
    "14 0E 1C", # 0002: Push short 0x1C0E <-- Object-id of ice delivery guy at Wastelands
    "58 BA",    # 0005: Push object's flags
    "00 02",    # 0007: Push unsigned byte 0x02
    "7E",       # 0009: Bitwise AND
    "BE",       # 000A: Convert to boolean
])))
# Reveal the new item shuffled to this location
writeHelper(romBytes, 0xFAA53, bytes.fromhex(' '.join([
    "00 80",    # 0069: Push unsigned byte 0x80
    f"14 {romBytes[0xCA60D+0]:02X} {romBytes[0xCA60D+1]:02X}",
                # 006B: Push short 0x#### <-- Object-id of new item in "Explosives" location
])))

# Mermaid Scales
writeHelper(romBytes, 0xF49B1, bytes.fromhex(' '.join([
    "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    "48 20 00", # 000C: Jump to 0020
])))

# Mermaid Scales: A Busy Man <-- Ice delivery guy at Wastelands
# Reveal the new item shuffled to this location
expandedOffset = scriptHelper(
    scriptNumber = 0x284,
    argsLen      = 0x00, # Script 0x284 now takes 0 bytes (= 0 stack items) as arguments
    returnLen    = 0x00, # Script 0x284 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x00, # Header byte: Script uses 0x00 bytes of $13+xx space
    maxStackLen  = 0x04, # Header byte: Maximum stack height of 0x04 bytes (= 2 stack items)
    commandList  = [
        "00 02",    # 0000: Push unsigned byte 0x02
        "14 0E 1C", # 0002: Push short 0x1C0E <-- Object-id of ice delivery guy at Wastelands
        "58 0D",    # 0005: Set bits of object's flags
        "00 80",    # 0007: Push unsigned byte 0x80
        f"14 {romBytes[0xCA691+0]:02X} {romBytes[0xCA691+1]:02X}",
                    # 0009: Push short 0x#### <-- Object-id of new item in "Mermaid Scales" location
        "58 0D",    # 000C: Set bits of object's flags
        "56",       # 000E: End
    ],
)

# Nuyen: Octopus
# Reveal the new item shuffled to this location
romBytes[0xF87B4:0xF87B4+2] = romBytes[0xCB18D:0xCB18D+2]

# Loyal citizen <-- Turns into Octopus
# Take into account the new item shuffled to the "Nuyen: Octopus" location
romBytes[0xF866C:0xF866C+2] = romBytes[0xCB18D:0xCB18D+2]
romBytes[0xF8677:0xF8677+2] = romBytes[0xCB18D:0xCB18D+2]

# Randomly-appearing enemies in Waterfront - Octopus boss room
# Take into account the new item shuffled to the "Nuyen: Octopus" location
romBytes[0xFA9AC:0xFA9AC+2] = romBytes[0xCB18D:0xCB18D+2]
romBytes[0xFA9D2:0xFA9D2+2] = romBytes[0xCB18D:0xCB18D+2]

# Rat Shaman
expandedOffset = scriptHelper(
    scriptNumber = 0x10D,
    argsLen      = 0x06, # Script 0x10D now takes 6 bytes (= 3 stack items) as arguments
    returnLen    = 0x00, # Script 0x10D now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x0F, # Header byte: Script uses 0x0F bytes of $13+xx space
    maxStackLen  = 0x0A, # Header byte: Maximum stack height of 0x0A bytes (= 5 stack items)
    commandList  = [
        # Copy 0000-018E from the original script.
        romBytes[0xF4CC7:0xF4E56].hex(' '),
        # New code.
        # Keyword: Jester Spirit
        # Reveal the new item shuffled to this location
        f"14 {romBytes[0xD29A7+0]:02X} {romBytes[0xD29A7+1]:02X}",
                    # 018F: Push short 0x####   <-- Item drop's object-id
        "58 C2",    # 0192: Push object's RAM_1 <-- Item drop's spawn index
        "2C 0E",    # 0194: Pop byte to $13+0E  <-- Item drop's spawn index
        "02 0A",    # 0196: Push unsigned byte from $13+0A <-- Corpse's spawn index
        "58 51",    # 0198: Push object's Z coordinate / 4
        "00 02",    # 019A: Push unsigned byte 0x02
        "7A",       # 019C: Left shift
        "02 0A",    # 019D: Push unsigned byte from $13+0A <-- Corpse's spawn index
        "58 50",    # 019F: Push object's Y coordinate / 4
        "00 02",    # 01A1: Push unsigned byte 0x02
        "7A",       # 01A3: Left shift
        "00 42",    # 01A4: Push unsigned byte 0x42
        "5E",       # 01A6: Subtraction
        "02 0A",    # 01A7: Push unsigned byte from $13+0A <-- Corpse's spawn index
        "58 4F",    # 01A9: Push object's X coordinate / 4
        "00 02",    # 01AB: Push unsigned byte 0x02
        "7A",       # 01AD: Left shift
        "00 02",    # 01AE: Push unsigned byte 0x02
        "5E",       # 01B0: Subtraction
        "02 0E",    # 01B1: Push unsigned byte from $13+0E <-- Item drop's spawn index
        "58 82",    # 01B3: Set object X/Y/Z position
        "00 80",    # 01B5: Push unsigned byte 0x80
        "02 0E",    # 01B7: Push unsigned byte from $13+0E <-- Item drop's spawn index
        "58 33",    # 01B9: Set bits of object's flags
        # Nuyen: Rat Shaman
        # Reveal the new item shuffled to this location
        f"14 {romBytes[0xD2965+0]:02X} {romBytes[0xD2965+1]:02X}",
                    # 01BB: Push short 0x####   <-- Item drop's object-id
        "58 C2",    # 01BE: Push object's RAM_1 <-- Item drop's spawn index
        "2C 0E",    # 01C0: Pop byte to $13+0E  <-- Item drop's spawn index
        "02 0A",    # 01C2: Push unsigned byte from $13+0A <-- Corpse's spawn index
        "58 51",    # 01C4: Push object's Z coordinate / 4
        "00 02",    # 01C6: Push unsigned byte 0x02
        "7A",       # 01C8: Left shift
        "02 0A",    # 01C9: Push unsigned byte from $13+0A <-- Corpse's spawn index
        "58 50",    # 01CB: Push object's Y coordinate / 4
        "00 02",    # 01CD: Push unsigned byte 0x02
        "7A",       # 01CF: Left shift
        "00 02",    # 01D0: Push unsigned byte 0x02
        "5E",       # 01D2: Subtraction
        "02 0A",    # 01D3: Push unsigned byte from $13+0A <-- Corpse's spawn index
        "58 4F",    # 01D5: Push object's X coordinate / 4
        "00 02",    # 01D7: Push unsigned byte 0x02
        "7A",       # 01D9: Left shift
        "00 42",    # 01DA: Push unsigned byte 0x42
        "5E",       # 01DC: Subtraction
        "02 0E",    # 01DD: Push unsigned byte from $13+0E <-- Item drop's spawn index
        "58 82",    # 01DF: Set object X/Y/Z position
        "00 80",    # 01E1: Push unsigned byte 0x80
        "02 0E",    # 01E3: Push unsigned byte from $13+0E <-- Item drop's spawn index
        "58 33",    # 01E5: Set bits of object's flags
        # Copy 01A3-01D9 from the original script.
        romBytes[0xF4E6A:0xF4EA1].hex(' '),
    ],
)
# Skip the automatic conversations with the Jester Spirit and Kitsune
# that happen after you defeat the Rat Shaman
writeHelper(romBytes, 0xF4EF2, bytes.fromhex(' '.join([
    "BC",       # 0022: Pop
    "BC",       # 0023: Pop
])))
writeHelper(romBytes, 0xF4F3E, bytes.fromhex(' '.join([
    "BC",       # 006E: Pop
    "BC",       # 006F: Pop
])))

# Doorway from Dark Blade courtyard into Dark Blade mansion interior
# Enlarge the doorway warp zone to make it easier to traverse
romBytes[0xD105C] = 0x26 # <-- Was 0x27

# Viper H. Pistol ($3,000): Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xFCE76:0xFCE76+2] = romBytes[0xD1715:0xD1715+2]

# T-250 Shotgun ($12,000): Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xFCE88:0xFCE88+2] = romBytes[0xD171B:0xD171B+2]

# Uzi III SMG: Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xFCE9A:0xFCE9A+2] = romBytes[0xD1721:0xD1721+2]

# HK 277 A. Rifle: Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xFCEAC:0xFCEAC+2] = romBytes[0xD1727:0xD1727+2]

# Bulletproof Vest: Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xFCED0:0xFCED0+2] = romBytes[0xD172D:0xD172D+2]

# Concealed Jacket: Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xFCEE2:0xFCEE2+2] = romBytes[0xD1733:0xD1733+2]

# Partial Bodysuit: Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xFCEF4:0xFCEF4+2] = romBytes[0xD1739:0xD1739+2]

# Full Bodysuit: Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xFCF06:0xFCF06+2] = romBytes[0xD1745:0xD1745+2]

# AS-7 A. Cannon: Gun Case
# Offer for sale the new item shuffled to this location
romBytes[0xFCF18:0xFCF18+2] = romBytes[0xD174B:0xD174B+2]

# Dark Blade mansion security status
# Start with the mansion security on alert
initialItemState[0x83F] |= 0x40

# Mage <-- In the front hall of the Dark Blade mansion
# Don't disappear when you know the "Laughlyn" keyword
writeHelper(romBytes, 0xF36E4, bytes.fromhex(' '.join([
    "C0",       # 003E: Push zero
    "BC",       # 003F: Pop
    "C0",       # 0040: Push zero
    "BC",       # 0041: Pop
    "48 4C 00", # 0042: Jump to 004C
])))

# Bronze Key
writeHelper(romBytes, 0xF4512, bytes.fromhex(' '.join([
    "48 0E 00", # 0002: Jump to 000E
])))
writeHelper(romBytes, 0xF4524, bytes.fromhex(' '.join([
    "C2",       # 0014: Push unsigned byte from $13+00 <-- Spawn index
    "52 1D 01", # 0015: Execute behaviour script 0x11D = New item-drawing script
    "C0",       # 0018: Push zero
    "BC",       # 0019: Pop
])))
# Use facing direction 05's sprite for direction 00
romBytes[0x65EFC] = 0x08
# Inventory list item-hiding
# Don't hide the Bronze Key after taking the helicopter to Drake Volcano
romBytes[0x6C921] |= 0x3F

# Mesh Jacket (free)
# Change the behaviour script for the free Mesh Jacket from 0x388
# (Mesh Jacket in Dark Blade mansion) to 0x1A8 (Mesh Jacket).
# In vanilla, 0x388 was a more complicated script to handle the
# jacket in the mansion, while 0x1A8 just specified armor stats.
# With this change, script 0x388 should now be entirely unused.
struct.pack_into("<H", romBytes, 0x6B894, 0x01A8)
# Increase the free Mesh Jacket's sprite priority
romBytes[0x6B88F] |= 0x40

# Bronze Key and Mesh Jacket (free): Samurai Warrior
# Reveal the new items shuffled to these locations
# In vanilla, the Bronze Key doesn't appear until the Dark Blade
# mansion's security is on alert. Unlike most hidden items, the
# Bronze Key doesn't wait for its own 0x80 flag to be set before
# appearing. Instead, it checks the mansion's "on alert" flag.
# This behaviour doesn't make sense after randomization (since
# the Bronze Key can end up anywhere), so it's been skipped over
# as part of the Bronze Key's script changes above.
# That takes care of the Bronze Key, but leaves a problem for the
# new item shuffled to the vanilla Bronze Key location: it starts
# out hidden, with no way to make it visible.
# The most obvious fix would be to find the script that puts the
# mansion on alert, and add code to it to reveal the new item.
# Unfortunately, there are multiple scripts capable of alerting
# the mansion, making this solution inconvenient.
# So instead, let's update the script for the mansion's Samurai
# Warriors (which also handles the "Mesh Jacket (free)" drop).
# If the mansion is on alert, reveal the new item.
expandedOffset = scriptHelper(
    scriptNumber = 0x2D5,
    argsLen      = 0x02, # Script 0x2D5 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x2D5 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x03, # Header byte: Script uses 0x03 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C0",       # 0002: Push zero
        "00 2A",    # 0003: Push unsigned byte 0x2A
        "58 12",    # 0005: Write short to 7E3BBB+n
        "14 C1 0D", # 0007: Push short 0x0DC1
        "58 BA",    # 000A: Push object's flags
        "00 40",    # 000C: Push unsigned byte 0x40
        "7E",       # 000E: Bitwise AND
        "BE",       # 000F: Convert to boolean
        "44 8C 00", # 0010: If false, jump to DONE
        # MANSION_SECURITY_ALERTED
        "00 80",    # 0013: Push unsigned byte 0x80
        f"14 {romBytes[0xD0B0B+0]:02X} {romBytes[0xD0B0B+1]:02X}",
                    # 0015: Push short 0x#### <-- Object-id of new item in "Bronze Key" location
        "58 0D",    # 0018: Set bits of object's flags
        # SPAWN_SAMURAI_WARRIOR
        "00 03",    # 001A: Push unsigned byte 0x03
        "C2",       # 001C: Push unsigned byte from $13+00 <-- Spawn index
        "58 24",    # 001D: ???
        "00 1E",    # 001F: Push unsigned byte 0x1E
        "C2",       # 0021: Push unsigned byte from $13+00 <-- Spawn index
        "58 9F",    # 0022: Set object's quantity <-- Samurai Warrior's hit points
        "C0",       # 0024: Push zero
        "00 04",    # 0025: Push unsigned byte 0x04
        "C2",       # 0027: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0028: Display sprite with facing direction
        "C2",       # 002A: Push unsigned byte from $13+00 <-- Spawn index
        "58 AB",    # 002B: ???
        # TOP_OF_LOOP
        "C2",       # 002D: Push unsigned byte from $13+00 <-- Spawn index
        "58 07",    # 002E: ???
        "BA",       # 0030: Duplicate
        "2C 02",    # 0031: Pop byte to $13+02
        "0A FF",    # 0033: Push signed byte 0xFF
        "AA",       # 0035: Check if equal
        "44 55 00", # 0036: If not equal, jump to SOMETHING_IS_NOT_EQUAL
        # SOMETHING_IS_EQUAL
        "0C 02",    # 0039: Push signed byte from $13+02
        "C2",       # 003B: Push unsigned byte from $13+00 <-- Spawn index
        "58 1B",    # 003C: ???
        "00 0A",    # 003E: Push unsigned byte 0x0A
        "58 63",    # 0040: ???
        "00 0F",    # 0042: Push unsigned byte 0x0F
        "7E",       # 0044: Bitwise AND
        "5C",       # 0045: Addition
        "14 01 08", # 0046: Push short 0x0801
        "58 9E",    # 0049: Register menu options / time delay
        "14 00 08", # 004B: Push short 0x0800
        "7E",       # 004E: Bitwise AND
        "BE",       # 004F: Convert to boolean
        "2C 01",    # 0050: Pop byte to $13+01
        "48 67 00", # 0052: Jump to BOTTOM_OF_LOOP
        # SOMETHING_IS_NOT_EQUAL
        "00 32",    # 0055: Push unsigned byte 0x32
        "00 01",    # 0057: Push unsigned byte 0x01
        "00 04",    # 0059: Push unsigned byte 0x04
        "00 01",    # 005B: Push unsigned byte 0x01
        "00 02",    # 005D: Push unsigned byte 0x02
        "0C 02",    # 005F: Push signed byte from $13+02
        "C2",       # 0061: Push unsigned byte from $13+00 <-- Spawn index
        "52 35 02", # 0062: Execute behaviour script 0x235
        "2C 01",    # 0065: Pop byte to $13+01
        # BOTTOM_OF_LOOP
        "0C 01",    # 0067: Push signed byte from $13+01
        "44 2D 00", # 0069: If false, jump to TOP_OF_LOOP
        # SAMURAI_WARRIOR_DEFEATED
        "00 09",    # 006C: Push unsigned byte 0x09
        "58 7B",    # 006E: Increase experience
        "C2",       # 0070: Push unsigned byte from $13+00 <-- Spawn index
        "58 BF",    # 0071: ???
        "C2",       # 0073: Push unsigned byte from $13+00 <-- Spawn index
        "58 CB",    # 0074: Push object-id
        "14 B0 05", # 0076: Push short 0x05B0 <-- Object-id of Samurai Warrior that drops "Mesh Jacket (free)"
        "AA",       # 0079: Check if equal
        "44 84 00", # 007A: If not equal, jump to PERISH
        # DROP_ITEM
        "00 80",    # 007D: Push unsigned byte 0x80
        f"14 {romBytes[0xD0B23+0]:02X} {romBytes[0xD0B23+1]:02X}",
                    # 007F: Push short 0x#### <-- Object-id of new item in "Mesh Jacket (free)" location
        "58 0D",    # 0082: Set bits of object's flags
        # PERISH
        "C2",       # 0084: Push unsigned byte from $13+00 <-- Spawn index
        "52 5C 03", # 0085: Execute behaviour script 0x35C
        "52 BC 01", # 0088: Execute behaviour script 0x1BC
        "BC",       # 008B: Pop
        # DONE
        "56",       # 008C: End
    ],
)

# Vampire
expandedOffset = scriptHelper(
    scriptNumber = 0x385,
    argsLen      = 0x02, # Script 0x385 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x385 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x08, # Header byte: Script uses 0x08 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        # Copy 0000-003A from the original script.
        romBytes[0xF3B4F:0xF3B8A].hex(' '),
        # Spawn the Vampire if the game has been completed (in-credits
        # Vampire case), or if the Vampire hasn't been defeated yet.
        "00 2C",    # 003B: Push unsigned byte 0x2C
        "58 57",    # 003D: Read short from 7E3BBB+n
        "46 4F 00", # 003F: If nonzero, jump to VAMPIRE_NOT_DEFEATED_YET <-- In-credits Vampire case
        "C2",       # 0042: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 0043: Push object's flags
        "00 01",    # 0045: Push unsigned byte 0x01
        "7E",       # 0047: Bitwise AND
        "44 4F 00", # 0048: If zero, jump to VAMPIRE_NOT_DEFEATED_YET
        # VAMPIRE_ALREADY_DEFEATED
        "C2",       # 004B: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 004C: Despawn object
        "56",       # 004E: End
        # VAMPIRE_NOT_DEFEATED_YET
        # Copy 004F-0121 from the original script.
        romBytes[0xF3B9E:0xF3C71].hex(' '),
        # VAMPIRE_STAKED_ONCE
        # New Vampire behaviour:
        # - No conversations
        # - Defeated after one use of the Stake
        "00 F0",    # 0122: Push unsigned byte 0xF0
        "C2",       # 0124: Push unsigned byte from $13+00 <-- Spawn index
        "58 51",    # 0125: Push object's Z coordinate / 4
        "C2",       # 0127: Push unsigned byte from $13+00 <-- Spawn index
        "58 50",    # 0128: Push object's Y coordinate / 4
        "C2",       # 012A: Push unsigned byte from $13+00 <-- Spawn index
        "58 4F",    # 012B: Push object's X coordinate / 4
        "00 56",    # 012D: Push unsigned byte 0x56
        "58 A8",    # 012F: Spawn object at abs coords?
        "BC",       # 0131: Pop
        "C2",       # 0132: Push unsigned byte from $13+00 <-- Spawn index
        "58 AB",    # 0133: ???
        "00 20",    # 0135: Push unsigned byte 0x20
        "58 7B",    # 0137: Increase experience
        "C2",       # 0139: Push unsigned byte from $13+00 <-- Spawn index
        "58 BF",    # 013A: ???
        "00 01",    # 013C: Push unsigned byte 0x01
        "BA",       # 013E: Duplicate
        "58 9E",    # 013F: Register menu options / time delay
        "BC",       # 0141: Pop
        # Keyword: Laughlyn
        # Reveal the new item shuffled to this location
        f"14 {romBytes[0xD29CB+0]:02X} {romBytes[0xD29CB+1]:02X}",
                    # 0142: Push short 0x####   <-- Item drop's object-id
        "58 C2",    # 0145: Push object's RAM_1 <-- Item drop's spawn index
        "2C 07",    # 0147: Pop byte to $13+07  <-- Item drop's spawn index
        "C2",       # 0149: Push unsigned byte from $13+00 <-- Spawn index
        "58 51",    # 014A: Push object's Z coordinate / 4
        "00 02",    # 014C: Push unsigned byte 0x02
        "7A",       # 014E: Left shift
        "C2",       # 014F: Push unsigned byte from $13+00 <-- Spawn index
        "58 50",    # 0150: Push object's Y coordinate / 4
        "00 02",    # 0152: Push unsigned byte 0x02
        "7A",       # 0154: Left shift
        "00 42",    # 0155: Push unsigned byte 0x42
        "5E",       # 0157: Subtraction
        "C2",       # 0158: Push unsigned byte from $13+00 <-- Spawn index
        "58 4F",    # 0159: Push object's X coordinate / 4
        "00 02",    # 015B: Push unsigned byte 0x02
        "7A",       # 015D: Left shift
        "00 02",    # 015E: Push unsigned byte 0x02
        "5E",       # 0160: Subtraction
        "02 07",    # 0161: Push unsigned byte from $13+07 <-- Item drop's spawn index
        "58 82",    # 0163: Set object X/Y/Z position
        "00 80",    # 0165: Push unsigned byte 0x80
        "02 07",    # 0167: Push unsigned byte from $13+07 <-- Item drop's spawn index
        "58 33",    # 0169: Set bits of object's flags
        # Nuyen: Vampire
        # Reveal the new item shuffled to this location
        f"14 {romBytes[0xD29AD+0]:02X} {romBytes[0xD29AD+1]:02X}",
                    # 016B: Push short 0x####   <-- Item drop's object-id
        "58 C2",    # 016E: Push object's RAM_1 <-- Item drop's spawn index
        "2C 07",    # 0170: Pop byte to $13+07  <-- Item drop's spawn index
        "C2",       # 0172: Push unsigned byte from $13+00 <-- Spawn index
        "58 51",    # 0173: Push object's Z coordinate / 4
        "00 02",    # 0175: Push unsigned byte 0x02
        "7A",       # 0177: Left shift
        "C2",       # 0178: Push unsigned byte from $13+00 <-- Spawn index
        "58 50",    # 0179: Push object's Y coordinate / 4
        "00 02",    # 017B: Push unsigned byte 0x02
        "7A",       # 017D: Left shift
        "00 02",    # 017E: Push unsigned byte 0x02
        "5E",       # 0180: Subtraction
        "C2",       # 0181: Push unsigned byte from $13+00 <-- Spawn index
        "58 4F",    # 0182: Push object's X coordinate / 4
        "00 02",    # 0184: Push unsigned byte 0x02
        "7A",       # 0186: Left shift
        "00 42",    # 0187: Push unsigned byte 0x42
        "5E",       # 0189: Subtraction
        "02 07",    # 018A: Push unsigned byte from $13+07 <-- Item drop's spawn index
        "58 82",    # 018C: Set object X/Y/Z position
        "00 80",    # 018E: Push unsigned byte 0x80
        "02 07",    # 0190: Push unsigned byte from $13+07 <-- Item drop's spawn index
        "58 33",    # 0192: Set bits of object's flags
        # Despawn the Vampire and give the 5,000 nuyen reward.
        "C2",       # 0194: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0195: Despawn object
        "00 50",    # 0197: Push unsigned byte 0x50
        "00 01",    # 0199: Push unsigned byte 0x01
        "58 9E",    # 019B: Register menu options / time delay
        "BC",       # 019D: Pop
        "14 88 13", # 019E: Push short 0x1388
        "58 98",    # 01A1: Increase nuyen
        "52 4B 00", # 01A3: Execute behaviour script 0x4B = "Got item" sound effect
        "00 B4",    # 01A6: Push unsigned byte 0xB4
        "14 F6 01", # 01A8: Push short 0x01F6
        "C0",       # 01AB: Push zero
        "00 03",    # 01AC: Push unsigned byte 0x03
        "00 16",    # 01AE: Push unsigned byte 0x16
        "00 04",    # 01B0: Push unsigned byte 0x04
        "00 04",    # 01B2: Push unsigned byte 0x04
        "58 C7",    # 01B4: Print text ("The vampire had 5,000 nuyen.")
        "56",       # 01B6: End
    ],
)

# Ghoul <-- The ghouls in the Vampire boss room
expandedOffset = scriptHelper(
    scriptNumber = 0x6C,
    argsLen      = 0x02, # Script 0x6C now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x6C now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x07, # Header byte: Script uses 0x07 bytes of $13+xx space
    maxStackLen  = 0x0C, # Header byte: Maximum stack height of 0x0C bytes (= 6 stack items)
    commandList  = [
        # 0000-0050
        # Copy 0000-0050 from the original script.
        romBytes[0xF3E1F:0xF3E70].hex(' '),
        # 0051-0069
        # Spawn the ghouls if the game has been completed (in-credits
        # Vampire case).
        "00 2C",    # 0051: Push unsigned byte 0x2C
        "58 57",    # 0053: Read short from 7E3BBB+n
        "44 61 00", # 0055: If zero, jump to GAME_NOT_COMPLETED_YET
        # IN_CREDITS_CASE
        # Clear the Vampire's flags to prevent the ghouls from despawning
        # almost immediately during the credits. (This happens if the
        # Vampire's 0x40 "strobed successfully" flag is still set.)
        "C0",       # 0058: Push zero
        "14 88 01", # 0059: Push short 0x0188 <-- Object-id of "Vampire!"
        "58 60",    # 005C: Write byte to object's flags
        "48 73 00", # 005E: Jump to VAMPIRE_NOT_DEFEATED_YET
        # GAME_NOT_COMPLETED_YET
        # Wait one frame for the Vampire to update its flags.
        "00 01",    # 0061: Push unsigned byte 0x01
        "BA",       # 0063: Duplicate
        "58 9E",    # 0064: Register menu options / time delay
        "BC",       # 0066: Pop
        # Don't spawn the ghouls if the Vampire has been defeated.
        "14 88 01", # 0067: Push short 0x0188 <-- Object-id of "Vampire!"
        "58 BA",    # 006A: Push object's flags
        "00 01",    # 006C: Push unsigned byte 0x01
        "7E",       # 006E: Bitwise AND
        "BE",       # 006F: Convert to boolean
        "46 55 01", # 0070: If true, jump to 0155
        # VAMPIRE_NOT_DEFEATED_YET
        # 0073-008D
        # Copy 0051-006B from the original script.
        romBytes[0xF3E70:0xF3E8B].hex(' '),
        # ------------------------------------------------------------
        # We're skipping 006C-0071 from the original script here.
        # The skipped bytes zero out the Vampire's flags, probably
        # to fix the "ghouls despawning during the credits" bug
        # that we fixed in IN_CREDITS_CASE above.
        # ------------------------------------------------------------
        # 008E-0096
        # Copy 0072-007A from the original script.
        romBytes[0xF3E91:0xF3E9A].hex(' '),
        # 0097-0099
        # Update jump destination (changed due to presence of new code).
        "44 A1 00", # 0097: If false, jump to 00A1
        # 009A-009D
        # Copy 007E-0081 from the original script.
        romBytes[0xF3E9D:0xF3EA1].hex(' '),
        # 009E-00A0
        # Update jump destination (changed due to presence of new code).
        "48 2F 01", # 009E: Jump to 012F
        # 00A1-00A9
        # Copy 0085-008D from the original script.
        romBytes[0xF3EA4:0xF3EAD].hex(' '),
        # 00AA-00AC
        # Update jump destination (changed due to presence of new code).
        "44 1B 01", # 00AA: If false, jump to 011B
        # 00AD-00D2
        # Copy 0091-00B6 from the original script.
        romBytes[0xF3EB0:0xF3ED6].hex(' '),
        # 00D3-00D5
        # Update jump destination (changed due to presence of new code).
        "46 1B 01", # 00D3: If true, jump to 011B
        # 00D6-00EF
        # Copy 00BA-00D3 from the original script.
        romBytes[0xF3ED9:0xF3EF3].hex(' '),
        # 00F0-00F2
        # Update jump destination (changed due to presence of new code).
        "44 1B 01", # 00F0: If false, jump to 011B
        # 00F3-013A
        # Copy 00D7-011E from the original script.
        romBytes[0xF3EF6:0xF3F3E].hex(' '),
        # 013B-013D
        # Update jump destination (changed due to presence of new code).
        "44 8E 00", # 013B: If false, jump to 008E
        # 013E-0146
        # Copy 0122-012A from the original script.
        romBytes[0xF3F41:0xF3F4A].hex(' '),
        # 0147-0149
        # Update jump destination (changed due to presence of new code).
        "46 52 01", # 0147: If true, jump to 0152
        # 014A-0158
        # Copy 012E-013C from the original script.
        romBytes[0xF3F4D:0xF3F5C].hex(' '),
    ],
)

# Dog Tag
writeHelper(romBytes, 0xC9C75, bytes.fromhex(' '.join([
    "8F 21",    # Move the spawn point to match the Doggie's spawn point
    "6C 22",    # Doggie's spawn coordinates: (399, 620, 132)
])))
expandedOffset = scriptHelper(
    scriptNumber = 0x304,
    argsLen      = 0x02, # Script 0x304 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x304 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x04, # Header byte: Script uses 0x04 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        # TOP_OF_LOOP
        "C2",       # 000C: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 000D: Check if object has an owner
        "2C 01",    # 000F: Pop byte to $13+01 <-- Whether object has an owner
        "C0",       # 0011: Push zero
        "0C 01",    # 0012: Push signed byte from $13+01 <-- Whether object has an owner
        "52 AA 02", # 0014: Execute behaviour script 0x2AA = Interaction menu helper
        "BA",       # 0017: Duplicate
        "34 02",    # 0018: Pop short to $13+02 <-- Selected menu option
        # CHECK_IF_EXAMINE
        "00 80",    # 001A: Push unsigned byte 0x80
        "AA",       # 001C: Check if equal
        "44 3E 00", # 001D: If not equal, jump to CHECK_IF_PICKUP
        # EXAMINE
        # Interaction menu option: Examine
        "00 03",    # 0020: Push unsigned byte 0x03
        "00 FF",    # 0022: Push unsigned byte 0xFF
        "00 32",    # 0024: Push unsigned byte 0x32
        "C2",       # 0026: Push unsigned byte from $13+00 <-- Spawn index
        "58 4C",    # 0027: Play sound effect
        "00 F0",    # 0029: Push unsigned byte 0xF0
        "14 FD 01", # 002B: Push short 0x01FD
        "14 00 08", # 002E: Push short 0x0800
        "00 03",    # 0031: Push unsigned byte 0x03
        "00 10",    # 0033: Push unsigned byte 0x10
        "00 15",    # 0035: Push unsigned byte 0x15
        "00 02",    # 0037: Push unsigned byte 0x02 <-- Was 0x08
        "58 C7",    # 0039: Print text ("An ID tag for a dog.")
        "48 50 00", # 003B: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_PICKUP
        "16 02",    # 003E: Push short from $13+02 <-- Selected menu option
        "00 10",    # 0040: Push unsigned byte 0x10
        "AA",       # 0042: Check if equal
        "44 50 00", # 0043: If not equal, jump to BOTTOM_OF_LOOP
        # PICKUP
        # Interaction menu option: Pickup
        "C2",       # 0046: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0047: Set object's owner to Jake
        "52 4B 00", # 0049: Execute behaviour script 0x4B = "Got item" sound effect
        "0A FF",    # 004C: Push signed byte 0xFF
        "2C 01",    # 004E: Pop byte to $13+01 <-- Whether object has an owner
        # BOTTOM_OF_LOOP
        "0C 01",    # 0050: Push signed byte from $13+01 <-- Whether object has an owner
        "44 0C 00", # 0052: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 0055: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0056: Despawn object
        "56",       # 0058: End
    ],
)

# Dog Tag: Doggie
# Reveal the new item shuffled to this location
expandedOffset = scriptHelper(
    scriptNumber = 0x2DD,
    argsLen      = 0x02, # Script 0x2DD now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x2DD now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x05, # Header byte: Script uses 0x05 bytes of $13+xx space
    maxStackLen  = 0x0C, # Header byte: Maximum stack height of 0x0C bytes (= 6 stack items)
    commandList  = [
        # Copy 0000-0015 from the original script.
        romBytes[0xF512A:0xF5140].hex(' '),
        # New code.
        f"14 {romBytes[0xC9C79+0]:02X} {romBytes[0xC9C79+1]:02X}",
                    # 0016: Push short 0x####   <-- Item drop's object-id
        "58 BA",    # 0019: Push object's flags <-- Item drop's flags
        "00 80",    # 001B: Push unsigned byte 0x80
        "7E",       # 001D: Bitwise AND
        # Copy 001E-00E7 from the original script.
        romBytes[0xF5148:0xF5212].hex(' '),
        # More new code.
        f"14 {romBytes[0xC9C79+0]:02X} {romBytes[0xC9C79+1]:02X}",
                    # 00E8: Push short 0x####   <-- Item drop's object-id
        "58 C2",    # 00EB: Push object's RAM_1 <-- Item drop's spawn index
        "2C 04",    # 00ED: Pop byte to $13+04  <-- Item drop's spawn index
        "C2",       # 00EF: Push unsigned byte from $13+00 <-- Spawn index
        "58 51",    # 00F0: Push object's Z coordinate / 4
        "00 02",    # 00F2: Push unsigned byte 0x02
        "7A",       # 00F4: Left shift
        "C2",       # 00F5: Push unsigned byte from $13+00 <-- Spawn index
        "58 50",    # 00F6: Push object's Y coordinate / 4
        "00 02",    # 00F8: Push unsigned byte 0x02
        "7A",       # 00FA: Left shift
        "C2",       # 00FB: Push unsigned byte from $13+00 <-- Spawn index
        "58 4F",    # 00FC: Push object's X coordinate / 4
        "00 02",    # 00FE: Push unsigned byte 0x02
        "7A",       # 0100: Left shift
        "02 04",    # 0101: Push unsigned byte from $13+04 <-- Item drop's spawn index
        "58 82",    # 0103: Set object X/Y/Z position
        "00 80",    # 0105: Push unsigned byte 0x80
        "02 04",    # 0107: Push unsigned byte from $13+04 <-- Item drop's spawn index
        "58 33",    # 0109: Set bits of object's flags
        "00 01",    # 010B: Push unsigned byte 0x01
        "BA",       # 010D: Duplicate
        "58 9E",    # 010E: Register menu options / time delay
        "BC",       # 0110: Pop
        "C2",       # 0111: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0112: Despawn object
        "56",       # 0114: End
    ],
)

# Doorway from Bremerton West into Bremerton's interior (Crowbar-locked)
# Resize the doorway warp zone to make it easier to traverse
romBytes[0xC9D50] = 0x8B # <-- Was 0x90
romBytes[0xC9D58] = 0xFB # <-- Was 0x01
romBytes[0xC9D59] = 0x01 # <-- Was 0x02

# Safes I and II (unlocked with Safe Key and Time Bomb respectively)
expandedOffset = scriptHelper(
    scriptNumber = 0x329,
    argsLen      = 0x02, # Script 0x329 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x329 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x07, # Header byte: Script uses 0x07 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        # Copy 0000-00BC from the original script.
        romBytes[0xF5815:0xF58D2].hex(' '),
        # New code.
        # CHECK_IF_SAFE_I_IS_UNLOCKED
        "C2",       # 00BD: Push unsigned byte from $13+00 <-- Spawn index
        "58 CB",    # 00BE: Push object-id
        "14 35 06", # 00C0: Push short 0x0635 <-- Object-id of Safe I (unlocked with Safe Key)
        "AA",       # 00C3: Check if equal
        "44 D8 00", # 00C4: If not equal, jump to CHECK_IF_SAFE_II_IS_UNLOCKED
        # SAFE_I_IS_UNLOCKED
        # Safe I: Detonator
        # Reveal the new item shuffled to this location
        "00 80",    # 00C7: Push unsigned byte 0x80
        f"14 {romBytes[0xD230F+0]:02X} {romBytes[0xD230F+1]:02X}",
                    # 00C9: Push short 0x#### <-- Object-id of new item in "Detonator" location
        "58 0D",    # 00CC: Set bits of object's flags
        # Safe I: Broken Bottle
        # Reveal the new item shuffled to this location
        "00 80",    # 00CE: Push unsigned byte 0x80
        f"14 {romBytes[0xD2321+0]:02X} {romBytes[0xD2321+1]:02X}",
                    # 00D0: Push short 0x#### <-- Object-id of new item in "Broken Bottle" location
        "58 0D",    # 00D3: Set bits of object's flags
        "48 E9 00", # 00D5: Jump to SAFE_UNLOCKED
        # CHECK_IF_SAFE_II_IS_UNLOCKED
        "C2",       # 00D8: Push unsigned byte from $13+00 <-- Spawn index
        "58 CB",    # 00D9: Push object-id
        "14 3C 06", # 00DB: Push short 0x063C <-- Object-id of Safe II (unlocked with Time Bomb)
        "AA",       # 00DE: Check if equal
        "44 E9 00", # 00DF: If not equal, jump to SAFE_UNLOCKED
        # SAFE_II_IS_UNLOCKED
        # Safe II: Green Bottle
        # Reveal the new item shuffled to this location
        "00 80",    # 00E2: Push unsigned byte 0x80
        f"14 {romBytes[0xD24E9+0]:02X} {romBytes[0xD24E9+1]:02X}",
                    # 00E4: Push short 0x#### <-- Object-id of new item in "Detonator" location
        "58 0D",    # 00E7: Set bits of object's flags
        # SAFE_UNLOCKED
        "00 2E",    # 00E9: Push unsigned byte 0x2E
        "00 02",    # 00EB: Push unsigned byte 0x02
        "00 06",    # 00ED: Push unsigned byte 0x06
        "C0",       # 00EF: Push zero
        "C2",       # 00F0: Push unsigned byte from $13+00 <-- Spawn index
        "52 74 00", # 00F1: Execute behaviour script 0x74 = Open door helper script
        "00 2E",    # 00F4: Push unsigned byte 0x2E
        "00 2C",    # 00F6: Push unsigned byte 0x2C
        "C0",       # 00F8: Push zero
        "00 04",    # 00F9: Push unsigned byte 0x04
        "00 02",    # 00FB: Push unsigned byte 0x02
        "C2",       # 00FD: Push unsigned byte from $13+00 <-- Spawn index
        "52 A2 02", # 00FE: Execute behaviour script 0x2A2 = Closed door helper script
        "48 E9 00", # 0101: Jump to SAFE_UNLOCKED
        "56",       # 0104: End
    ],
)

# Safe Key
writeHelper(romBytes, 0xF4618, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    "48 12 00", # 000C: Jump to 0012
])))
# Use facing direction 05's sprite for direction 00
romBytes[0x66850] = 0x08

# Safe Key: Ferocious Orc
# Reveal the new item shuffled to this location
romBytes[0xF580E:0xF580E+2] = romBytes[0xD2315:0xD2315+2]

# Detonator
writeHelper(romBytes, 0xD230B, bytes.fromhex(' '.join([
    "44 02",    # Move the spawn point to the floor outside the safe
    "96 11",    # New coordinates: (580, 406, 64)
])))
writeHelper(romBytes, 0xF40C2, bytes.fromhex(' '.join([
    "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
    "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
    "58 C5",    # 0003: Check if object has an owner
    "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
    "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    # TOP_OF_LOOP
    "C2",       # 000C: Push unsigned byte from $13+00 <-- Spawn index
    "58 C5",    # 000D: Check if object has an owner
    "2C 01",    # 000F: Pop byte to $13+01 <-- Whether object has an owner
    "00 00",    # 0011: Push unsigned byte 0x00
])))
writeHelper(romBytes, 0xF410F, bytes.fromhex(' '.join([
    "44 0C 00", # 004D: If not owned, jump to TOP_OF_LOOP
])))

# Broken Bottle
writeHelper(romBytes, 0xD231D, bytes.fromhex(' '.join([
    "46 02",    # Move the spawn point to the floor outside the safe
    "B4 11",    # New coordinates: (582, 436, 64)
])))
writeHelper(romBytes, 0xF4118, bytes.fromhex(' '.join([
    "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
    "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
    "58 C5",    # 0003: Check if object has an owner
    "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
    "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    # TOP_OF_LOOP
    "C2",       # 000C: Push unsigned byte from $13+00 <-- Spawn index
    "58 C5",    # 000D: Check if object has an owner
    "2C 01",    # 000F: Pop byte to $13+01 <-- Whether object has an owner
    "00 00",    # 0011: Push unsigned byte 0x00
])))
writeHelper(romBytes, 0xF4162, bytes.fromhex(' '.join([
    "44 0C 00", # 004A: If not owned, jump to TOP_OF_LOOP
])))

# Green Bottle
writeHelper(romBytes, 0xD24E5, bytes.fromhex(' '.join([
    "45 02",    # Move the spawn point to the floor outside the safe
    "97 11",    # New coordinates: (581, 407, 64)
])))
writeHelper(romBytes, 0xF428E, bytes.fromhex(' '.join([
    "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
    "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
    "58 C5",    # 0003: Check if object has an owner
    "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
    "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    # TOP_OF_LOOP
    "C2",       # 000C: Push unsigned byte from $13+00 <-- Spawn index
    "58 C5",    # 000D: Check if object has an owner
    "2C 01",    # 000F: Pop byte to $13+01 <-- Whether object has an owner
    "14 00 01", # 0011: Push short 0x0100
    "0C 01",    # 0014: Push signed byte from $13+01 <-- Whether object has an owner
    "52 AA 02", # 0016: Execute behaviour script 0x2AA = Interaction menu helper
    "BA",       # 0019: Duplicate
    "34 02",    # 001A: Pop short to $13+02 <-- Selected menu option
    # CHECK_IF_EXAMINE
    "14 80 00", # 001C: Push short 0x0080
])))
writeHelper(romBytes, 0xF4314, bytes.fromhex(' '.join([
    "44 0C 00", # 0086: If not owned, jump to TOP_OF_LOOP
])))

# Jester Spirit (boss)
expandedOffset = scriptHelper(
    scriptNumber = 0x19E,
    argsLen      = 0x02, # Script 0x19E now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x19E now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x05, # Header byte: Script uses 0x05 bytes of $13+xx space
    maxStackLen  = 0x10, # Header byte: Maximum stack height of 0x10 bytes (= 8 stack items)
    commandList  = [
        # 0000-0005
        # Remove the silent teaching of the "Drake" keyword.
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 0E",    # 0002: Push unsigned byte 0x0E <-- Keyword-id for "Drake"
        "BE",       # 0004: Convert to boolean <-- Was "58 71" in vanilla ("Learn keyword")
        "BC",       # 0005: Pop
        # 0006-00FE
        # Copy 0006-00FE from the original script.
        romBytes[0xDE041:0xDE13A].hex(' '),
        # 00FF-0100
        # Move the defeated Jester Spirit a bit more to the lower left.
        "00 18",    # 00FF: Push unsigned byte 0x18
        # 0101-0132
        # Copy 0101-0132 from the original script.
        romBytes[0xDE13C:0xDE16E].hex(' '),
        # Skip the vanilla code that handles the post-defeat conversation.
        # 0133-017D
        # Copy 0157-01A1 from the original script.
        romBytes[0xDE192:0xDE1DD].hex(' '),
        # 017E-0180
        # Update jump destination (changed due to removal of some vanilla code).
        "44 3E 01", # 017E: If false, jump to 013E
        # 0181-01ED
        # New code.
        # Make the defeated Jester Spirit disappear in a puff of smoke.
        "C2",       # 0181: Push unsigned byte from $13+00 <-- Spawn index
        "58 4D",    # 0182: Stop object's movement?
        "00 F0",    # 0184: Push unsigned byte 0xF0
        "C2",       # 0186: Push unsigned byte from $13+00 <-- Spawn index
        "58 51",    # 0187: Push object's Z coordinate / 4
        "C2",       # 0189: Push unsigned byte from $13+00 <-- Spawn index
        "58 50",    # 018A: Push object's Y coordinate / 4
        "C2",       # 018C: Push unsigned byte from $13+00 <-- Spawn index
        "58 4F",    # 018D: Push object's X coordinate / 4
        "00 56",    # 018F: Push unsigned byte 0x56
        "58 A8",    # 0191: Spawn object at abs coords?
        "BC",       # 0193: Pop
        "00 01",    # 0194: Push unsigned byte 0x01
        "BA",       # 0196: Duplicate
        "58 9E",    # 0197: Register menu options / time delay
        "BC",       # 0199: Pop
        # Keyword: Volcano
        # Reveal the new item shuffled to this location
        f"14 {romBytes[0xD299B+0]:02X} {romBytes[0xD299B+1]:02X}",
                    # 019A: Push short 0x####   <-- Item drop's object-id
        "58 C2",    # 019D: Push object's RAM_1 <-- Item drop's spawn index
        "2C 04",    # 019F: Pop byte to $13+04  <-- Item drop's spawn index
        "C2",       # 01A1: Push unsigned byte from $13+00 <-- Spawn index
        "58 51",    # 01A2: Push object's Z coordinate / 4
        "00 02",    # 01A4: Push unsigned byte 0x02
        "7A",       # 01A6: Left shift
        "C2",       # 01A7: Push unsigned byte from $13+00 <-- Spawn index
        "58 50",    # 01A8: Push object's Y coordinate / 4
        "00 02",    # 01AA: Push unsigned byte 0x02
        "7A",       # 01AC: Left shift
        "00 42",    # 01AD: Push unsigned byte 0x42
        "5E",       # 01AF: Subtraction
        "C2",       # 01B0: Push unsigned byte from $13+00 <-- Spawn index
        "58 4F",    # 01B1: Push object's X coordinate / 4
        "00 02",    # 01B3: Push unsigned byte 0x02
        "7A",       # 01B5: Left shift
        "00 02",    # 01B6: Push unsigned byte 0x02
        "5E",       # 01B8: Subtraction
        "02 04",    # 01B9: Push unsigned byte from $13+04 <-- Item drop's spawn index
        "58 82",    # 01BB: Set object X/Y/Z position
        "00 80",    # 01BD: Push unsigned byte 0x80
        "02 04",    # 01BF: Push unsigned byte from $13+04 <-- Item drop's spawn index
        "58 33",    # 01C1: Set bits of object's flags
        # Jester Spirit Insignia
        # Reveal the new item shuffled to this location
        f"14 {romBytes[0xCAE23+0]:02X} {romBytes[0xCAE23+1]:02X}",
                    # 01C3: Push short 0x####   <-- Item drop's object-id
        "58 C2",    # 01C6: Push object's RAM_1 <-- Item drop's spawn index
        "2C 04",    # 01C8: Pop byte to $13+04  <-- Item drop's spawn index
        "C2",       # 01CA: Push unsigned byte from $13+00 <-- Spawn index
        "58 51",    # 01CB: Push object's Z coordinate / 4
        "00 02",    # 01CD: Push unsigned byte 0x02
        "7A",       # 01CF: Left shift
        "C2",       # 01D0: Push unsigned byte from $13+00 <-- Spawn index
        "58 50",    # 01D1: Push object's Y coordinate / 4
        "00 02",    # 01D3: Push unsigned byte 0x02
        "7A",       # 01D5: Left shift
        "00 02",    # 01D6: Push unsigned byte 0x02
        "5E",       # 01D8: Subtraction
        "C2",       # 01D9: Push unsigned byte from $13+00 <-- Spawn index
        "58 4F",    # 01DA: Push object's X coordinate / 4
        "00 02",    # 01DC: Push unsigned byte 0x02
        "7A",       # 01DE: Left shift
        "00 42",    # 01DF: Push unsigned byte 0x42
        "5E",       # 01E1: Subtraction
        "02 04",    # 01E2: Push unsigned byte from $13+04 <-- Item drop's spawn index
        "58 82",    # 01E4: Set object X/Y/Z position
        "00 80",    # 01E6: Push unsigned byte 0x80
        "02 04",    # 01E8: Push unsigned byte from $13+04 <-- Item drop's spawn index
        "58 33",    # 01EA: Set bits of object's flags
        # Reveal the Jester Spirit portal.
        "00 01",    # 01EC: Push unsigned byte 0x01
        "14 DF 1E", # 01EE: Push short 0x1EDF <-- Object-id of the Jester Spirit portal
        "58 0D",    # 01F1: Set bits of object's flags
        # Mark the Jester Spirit as defeated.
        "C2",       # 01F3: Push unsigned byte from $13+00 <-- Spawn index
        "58 C4",    # 01F4: Set object's owner to "Dog Food"
        # Despawn the Jester Spirit.
        "C2",       # 01F6: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 01F7: Despawn object
        "56",       # 01F9: End
    ],
)

# Jester Spirit Insignia
expandedOffset = scriptHelper(
    scriptNumber = 0x1F6,
    argsLen      = 0x02, # Script 0x1F6 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x1F6 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x09, # Header byte: Script uses 0x09 bytes of $13+xx space
    maxStackLen  = 0x10, # Header byte: Maximum stack height of 0x10 bytes (= 8 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 11 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "00 05",    # 000C: Push unsigned byte 0x05
        "C2",       # 000E: Push unsigned byte from $13+00 <-- Spawn index
        "58 6A",    # 000F: Set object's facing direction
        # TOP_OF_LOOP
        "C2",       # 0011: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0012: Check if object has an owner
        "2C 01",    # 0014: Pop byte to $13+01 <-- Whether object has an owner
        "14 00 01", # 0016: Push short 0x0100
        "0C 01",    # 0019: Push signed byte from $13+01 <-- Whether object has an owner
        "52 AA 02", # 001B: Execute behaviour script 0x2AA = Interaction menu helper
        "BA",       # 001E: Duplicate
        "34 02",    # 001F: Pop short to $13+02 <-- Selected menu option
        # CHECK_IF_EXAMINE
        "00 80",    # 0021: Push unsigned byte 0x80
        "AA",       # 0023: Check if equal
        "44 3C 00", # 0024: If not equal, jump to CHECK_IF_PICKUP
        # EXAMINE
        # Interaction menu option: Examine
        "00 F0",    # 0027: Push unsigned byte 0xF0
        "14 0F 01", # 0029: Push short 0x010F
        "14 00 08", # 002C: Push short 0x0800
        "00 03",    # 002F: Push unsigned byte 0x03
        "00 11",    # 0031: Push unsigned byte 0x11 <-- Was 0x13
        "00 15",    # 0033: Push unsigned byte 0x15 <-- Was 0x16
        "00 02",    # 0035: Push unsigned byte 0x02
        "58 C7",    # 0037: Print text ("Jester Spirit Insignia")
        "48 B2 01", # 0039: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_PICKUP
        "16 02",    # 003C: Push short from $13+02 <-- Selected menu option
        "00 10",    # 003E: Push unsigned byte 0x10
        "AA",       # 0040: Check if equal
        "44 51 00", # 0041: If not equal, jump to CHECK_IF_USE
        # PICKUP
        # Interaction menu option: Pickup
        "C2",       # 0044: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0045: Set object's owner to Jake
        "52 4B 00", # 0047: Execute behaviour script 0x4B = "Got item" sound effect
        "0A FF",    # 004A: Push signed byte 0xFF
        "2C 01",    # 004C: Pop byte to $13+01 <-- Whether object has an owner
        "48 B2 01", # 004E: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_USE
        "16 02",    # 0051: Push short from $13+02 <-- Selected menu option
        "14 00 01", # 0053: Push short 0x0100
        "AA",       # 0056: Check if equal
        "44 B2 01", # 0057: If not equal, jump to BOTTOM_OF_LOOP
        # USE
        # Interaction menu option: Use
        "C2",       # 005A: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 005B: Push object's flags
        "00 01",    # 005D: Push unsigned byte 0x01
        "7E",       # 005F: Bitwise AND
        "BE",       # 0060: Convert to boolean
        "46 B2 01", # 0061: If true, jump to BOTTOM_OF_LOOP
        # CHECK_IF_INSIDE_DRAKE_BOSS_ROOM
        "58 7E",    # 0064: Push current map data pointer
        "14 22 01", # 0066: Push short 0x0122
        "58 17",    # 0069: Push a door destination's map data pointer
        "AA",       # 006B: Check if equal
        "44 A1 01", # 006C: If not equal, jump to NOT_USING_IT_HERE
        # SPAWN_JESTER_SPIRIT
        "00 01",    # 006F: Push unsigned byte 0x01
        "C2",       # 0071: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 0072: Set bits of object's flags
        "14 01 80", # 0074: Push short 0x8001
        "C2",       # 0077: Push unsigned byte from $13+00 <-- Spawn index
        "58 B2",    # 0078: ???
        "58 7F",    # 007A: ???
        "00 01",    # 007C: Push unsigned byte 0x01
        "BA",       # 007E: Duplicate
        "58 9E",    # 007F: Register menu options / time delay
        "BC",       # 0081: Pop
        "C2",       # 0082: Push unsigned byte from $13+00 <-- Spawn index
        "58 C4",    # 0083: Set object's owner to "Dog Food"
        "00 0F",    # 0085: Push unsigned byte 0x0F
        "00 FF",    # 0087: Push unsigned byte 0xFF
        "00 58",    # 0089: Push unsigned byte 0x58
        "C2",       # 008B: Push unsigned byte from $13+00 <-- Spawn index
        "58 4C",    # 008C: Play sound effect
        "00 01",    # 008E: Push unsigned byte 0x01
        "00 14",    # 0090: Push unsigned byte 0x14
        "58 9A",    # 0092: Set bits of 7E3BBB+n
        "C0",       # 0094: Push zero
        "C0",       # 0095: Push zero
        "C2",       # 0096: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0097: Display sprite with facing direction
        "00 01",    # 0099: Push unsigned byte 0x01
        "C2",       # 009B: Push unsigned byte from $13+00 <-- Spawn index
        "58 B5",    # 009C: Move object instantly to waypoint?
        "00 20",    # 009E: Push unsigned byte 0x20
        "C2",       # 00A0: Push unsigned byte from $13+00 <-- Spawn index
        "58 CE",    # 00A1: Set bits of 7E1474+n <-- Makes the Jester Spirit subject to gravity
        "00 10",    # 00A3: Push unsigned byte 0x10
        "C0",       # 00A5: Push zero
        "C0",       # 00A6: Push zero
        "C2",       # 00A7: Push unsigned byte from $13+00 <-- Spawn index
        "58 79",    # 00A8: Set object X/Y/Z deltas?
        "C0",       # 00AA: Push zero
        "2C 04",    # 00AB: Pop byte to $13+04 <-- Facing direction (was $13+03 in vanilla)
        "00 80",    # 00AD: Push unsigned byte 0x80
        "34 05",    # 00AF: Pop short to $13+05 <-- Movement countdown (was $13+04 in vanilla)
        "00 01",    # 00B1: Push unsigned byte 0x01
        "34 07",    # 00B3: Pop short to $13+07 <-- Frames spent per facing (was $13+06 in vanilla)
        # ROTATE
        "02 04",    # 00B5: Push unsigned byte from $13+04 <-- Facing direction
        "C2",       # 00B7: Push unsigned byte from $13+00 <-- Spawn index
        "58 6A",    # 00B8: Set object's facing direction
        "02 04",    # 00BA: Push unsigned byte from $13+04 <-- Facing direction
        "86",       # 00BC: Increment
        "00 07",    # 00BD: Push unsigned byte 0x07
        "7E",       # 00BF: Bitwise AND
        "2C 04",    # 00C0: Pop byte to $13+04 <-- Facing direction
        "16 07",    # 00C2: Push short from $13+07 <-- Frames spent per facing
        "00 01",    # 00C4: Push unsigned byte 0x01
        "58 9E",    # 00C6: Register menu options / time delay
        "BC",       # 00C8: Pop
        "16 05",    # 00C9: Push short from $13+05 <-- Movement countdown
        "00 0A",    # 00CB: Push unsigned byte 0x0A
        "8A",       # 00CD: Check if less than
        "44 D6 00", # 00CE: If greater than or equal to ten, jump to CHECK_IF_DONE_ROTATING
        # SLOW_DOWN_ROTATION
        "16 07",    # 00D1: Push short from $13+07 <-- Frames spent per facing
        "86",       # 00D3: Increment
        "34 07",    # 00D4: Pop short to $13+07 <-- Frames spent per facing
        # CHECK_IF_DONE_ROTATING
        "16 05",    # 00D6: Push short from $13+05 <-- Movement countdown
        "C0",       # 00D8: Push zero
        "AA",       # 00D9: Check if equal
        "46 E5 00", # 00DA: If equal, jump to WAIT_FOR_DRAKE
        # ROTATION_COUNTDOWN
        "16 05",    # 00DD: Push short from $13+05 <-- Movement countdown
        "88",       # 00DF: Decrement
        "34 05",    # 00E0: Pop short to $13+05 <-- Movement countdown
        "48 B5 00", # 00E2: Jump to ROTATE
        # WAIT_FOR_DRAKE
        "00 05",    # 00E5: Push unsigned byte 0x05
        "00 01",    # 00E7: Push unsigned byte 0x01
        "58 9E",    # 00E9: Register menu options / time delay
        "BC",       # 00EB: Pop
        "00 14",    # 00EC: Push unsigned byte 0x14
        "58 57",    # 00EE: Read short from 7E3BBB+n
        "00 02",    # 00F0: Push unsigned byte 0x02
        "7E",       # 00F2: Bitwise AND
        "BE",       # 00F3: Convert to boolean
        "44 E5 00", # 00F4: If false, jump to WAIT_FOR_DRAKE
        # PREPARE_TO_ASCEND
        "0A DF",    # 00F7: Push signed byte 0xDF
        "C2",       # 00F9: Push unsigned byte from $13+00 <-- Spawn index
        "58 2C",    # 00FA: Clear bits of 7E1474+n <-- Makes the Jester Spirit no longer subject to gravity
        "00 01",    # 00FC: Push unsigned byte 0x01
        "C0",       # 00FE: Push zero
        "C0",       # 00FF: Push zero
        "C2",       # 0100: Push unsigned byte from $13+00 <-- Spawn index
        "58 79",    # 0101: Set object X/Y/Z deltas?
        "00 0F",    # 0103: Push unsigned byte 0x0F
        "34 05",    # 0105: Pop short to $13+05 <-- Movement countdown
        # ASCEND
        "00 0F",    # 0107: Push unsigned byte 0x0F
        "00 01",    # 0109: Push unsigned byte 0x01
        "58 9E",    # 010B: Register menu options / time delay
        "BC",       # 010D: Pop
        "4C CC 01", # 010E: Execute SUBROUTINE_CREATE_HOVER_BUBBLE subroutine
        "16 05",    # 0111: Push short from $13+05 <-- Movement countdown
        "88",       # 0113: Decrement
        "BA",       # 0114: Duplicate
        "34 05",    # 0115: Pop short to $13+05 <-- Movement countdown
        "C0",       # 0117: Push zero
        "AA",       # 0118: Check if equal
        "44 07 01", # 0119: If not equal, jump to ASCEND
        # PREPARE_TO_ATTACK
        "C2",       # 011C: Push unsigned byte from $13+00 <-- Spawn index
        "58 4D",    # 011D: Stop object's movement?
        "00 14",    # 011F: Push unsigned byte 0x14
        "34 05",    # 0121: Pop short to $13+05 <-- Movement countdown
        # ATTACK
        "00 0F",    # 0123: Push unsigned byte 0x0F
        "00 01",    # 0125: Push unsigned byte 0x01
        "58 9E",    # 0127: Register menu options / time delay
        "BC",       # 0129: Pop
        "4C BB 01", # 012A: Execute SUBROUTINE_CREATE_PROJECTILE subroutine
        "4C CC 01", # 012D: Execute SUBROUTINE_CREATE_HOVER_BUBBLE subroutine
        "16 05",    # 0130: Push short from $13+05 <-- Movement countdown
        "00 03",    # 0132: Push unsigned byte 0x03
        "7E",       # 0134: Bitwise AND
        "BE",       # 0135: Convert to boolean
        "46 42 01", # 0136: If true, jump to CHECK_IF_DONE_ATTACKING
        # LAUGH
        "00 06",    # 0139: Push unsigned byte 0x06
        "00 60",    # 013B: Push unsigned byte 0x60
        "00 56",    # 013D: Push unsigned byte 0x56
        "C2",       # 013F: Push unsigned byte from $13+00 <-- Spawn index
        "58 4C",    # 0140: Play sound effect
        # CHECK_IF_DONE_ATTACKING
        "16 05",    # 0142: Push short from $13+05 <-- Movement countdown
        "88",       # 0144: Decrement
        "BA",       # 0145: Duplicate
        "34 05",    # 0146: Pop short to $13+05 <-- Movement countdown
        "C0",       # 0148: Push zero
        "AA",       # 0149: Check if equal
        "44 23 01", # 014A: If not equal, jump to ATTACK
        # PREPARE_TO_DISAPPEAR
        "00 01",    # 014D: Push unsigned byte 0x01
        "C0",       # 014F: Push zero
        "C0",       # 0150: Push zero
        "C2",       # 0151: Push unsigned byte from $13+00 <-- Spawn index
        "58 79",    # 0152: Set object X/Y/Z deltas?
        "00 3C",    # 0154: Push unsigned byte 0x3C
        "34 05",    # 0156: Pop short to $13+05 <-- Movement countdown
        "00 04",    # 0158: Push unsigned byte 0x04
        "00 FF",    # 015A: Push unsigned byte 0xFF
        "00 56",    # 015C: Push unsigned byte 0x56
        "C2",       # 015E: Push unsigned byte from $13+00 <-- Spawn index
        "58 4C",    # 015F: Play sound effect
        # DISAPPEAR
        "00 01",    # 0161: Push unsigned byte 0x01
        "BA",       # 0163: Duplicate
        "58 9E",    # 0164: Register menu options / time delay
        "BC",       # 0166: Pop
        "00 80",    # 0167: Push unsigned byte 0x80
        "C2",       # 0169: Push unsigned byte from $13+00 <-- Spawn index
        "58 CE",    # 016A: Set bits of 7E1474+n <-- Makes the Jester Spirit invisible
        "00 01",    # 016C: Push unsigned byte 0x01
        "BA",       # 016E: Duplicate
        "58 9E",    # 016F: Register menu options / time delay
        "BC",       # 0171: Pop
        "14 7F FF", # 0172: Push short 0xFF7F
        "C2",       # 0175: Push unsigned byte from $13+00 <-- Spawn index
        "58 2C",    # 0176: Clear bits of 7E1474+n <-- Makes the Jester Spirit visible
        "16 05",    # 0178: Push short from $13+05 <-- Movement countdown
        "00 02",    # 017A: Push unsigned byte 0x02
        "5E",       # 017C: Subtraction
        "BA",       # 017D: Duplicate
        "34 05",    # 017E: Pop short to $13+05 <-- Movement countdown
        "00 03",    # 0180: Push unsigned byte 0x03
        "7E",       # 0182: Bitwise AND
        "BE",       # 0183: Convert to boolean
        "46 91 01", # 0184: If true, jump to CHECK_IF_DONE_DISAPPEARING
        # ROTATE_WHILE_DISAPPEARING
        "C2",       # 0187: Push unsigned byte from $13+00 <-- Spawn index
        "58 5D",    # 0188: Push object's facing direction
        "86",       # 018A: Increment
        "00 07",    # 018B: Push unsigned byte 0x07
        "7E",       # 018D: Bitwise AND
        "C2",       # 018E: Push unsigned byte from $13+00 <-- Spawn index
        "58 6A",    # 018F: Set object's facing direction
        # CHECK_IF_DONE_DISAPPEARING
        "16 05",    # 0191: Push short from $13+05 <-- Movement countdown
        "C0",       # 0193: Push zero
        "AA",       # 0194: Check if equal
        "44 61 01", # 0195: If not equal, jump to DISAPPEAR
        # FINAL_ACTIONS
        "0A FE",    # 0198: Push signed byte 0xFE
        "00 14",    # 019A: Push unsigned byte 0x14
        "58 03",    # 019C: Clear bits of 7E3BBB+n
        "48 B2 01", # 019E: Jump to BOTTOM_OF_LOOP
        # NOT_USING_IT_HERE
        "00 F0",    # 01A1: Push unsigned byte 0xF0
        "00 07",    # 01A3: Push unsigned byte 0x07
        "14 00 08", # 01A5: Push short 0x0800
        "00 03",    # 01A8: Push unsigned byte 0x03
        "00 11",    # 01AA: Push unsigned byte 0x11 <-- Was 0x13
        "00 15",    # 01AC: Push unsigned byte 0x15 <-- Was 0x16
        "00 02",    # 01AE: Push unsigned byte 0x02
        "58 C7",    # 01B0: Print text ("I'm not using it HERE!")
        # BOTTOM_OF_LOOP
        "0C 01",    # 01B2: Push signed byte from $13+01 <-- Whether object has an owner
        "44 11 00", # 01B4: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 01B7: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 01B8: Despawn object
        "56",       # 01BA: End
        # SUBROUTINE_CREATE_PROJECTILE
        "00 2E",    # 01BB: Push unsigned byte 0x2E
        "C2",       # 01BD: Push unsigned byte from $13+00 <-- Spawn index
        "58 51",    # 01BE: Push object's Z coordinate / 4
        "C2",       # 01C0: Push unsigned byte from $13+00 <-- Spawn index
        "58 50",    # 01C1: Push object's Y coordinate / 4
        "C2",       # 01C3: Push unsigned byte from $13+00 <-- Spawn index
        "58 4F",    # 01C4: Push object's X coordinate / 4
        "00 78",    # 01C6: Push unsigned byte 0x78
        "58 A8",    # 01C8: Spawn object at abs coords?
        "BC",       # 01CA: Pop
        "50",       # 01CB: Return
        # SUBROUTINE_CREATE_HOVER_BUBBLE
        "0A FC",    # 01CC: Push signed byte 0xFC
        "C0",       # 01CE: Push zero
        "C0",       # 01CF: Push zero
        "14 31 03", # 01D0: Push short 0x0331
        "C2",       # 01D3: Push unsigned byte from $13+00 <-- Spawn index
        "58 51",    # 01D4: Push object's Z coordinate / 4
        "C2",       # 01D6: Push unsigned byte from $13+00 <-- Spawn index
        "58 50",    # 01D7: Push object's Y coordinate / 4
        "88",       # 01D9: Decrement
        "C2",       # 01DA: Push unsigned byte from $13+00 <-- Spawn index
        "58 4F",    # 01DB: Push object's X coordinate / 4
        "88",       # 01DD: Decrement
        "00 78",    # 01DE: Push unsigned byte 0x78
        "58 A8",    # 01E0: Spawn object at abs coords?
        "58 79",    # 01E2: Set object X/Y/Z deltas?
        "50",       # 01E4: Return
    ],
)
# Increase the Jester Spirit Insignia's sprite priority
romBytes[0x6BBC9] |= 0x40

# Jester Spirit portal
# - Wait for the portal's 0x01 flag to be set before appearing.
#   Using the 0x80 flag would be more consistent, but the portal script
#   is already using that flag as part of player proximity detection.
writeHelper(romBytes, 0xDE224, bytes.fromhex(' '.join([
    "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
    "58 02",    # 000A: Push object's flags
    "00 01",    # 000C: Push unsigned byte 0x01
    "7E",       # 000E: Bitwise AND
    "BE",       # 000F: Convert to boolean
    "44 02 00", # 0010: If false, jump to 0002
    "C0",       # 0013: Push zero
    "BC",       # 0014: Pop
])))
# - Stock the $20,000 case at the Dark Blade Gun Shop (vanilla: Partial Bodysuit)
# - Stock the $24,000 case at the Dark Blade Gun Shop (vanilla: HK 277 A. Rifle)
writeHelper(romBytes, 0xDE297, bytes.fromhex(' '.join([
    "0A FD",    # 007C: Push signed byte 0xFD
    "14 0D 10", # 007E: Push short 0x100D <-- Object-id of "Partial Bodysuit" glass case
    "58 4B",    # 0081: Clear bits of object's flags
    "0A FD",    # 0083: Push signed byte 0xFD
    "14 3E 10", # 0085: Push short 0x103E <-- Object-id of "HK 277 A. Rifle" glass case
    "58 4B",    # 0088: Clear bits of object's flags
])))
# - Don't forget "Rust Stilettos"
writeHelper(romBytes, 0xDE2AE, bytes.fromhex(' '.join([
    "BC",       # 0093: Pop
    "C0",       # 0094: Push zero
])))
# - Don't forget "Laughlyn"
writeHelper(romBytes, 0xDE2B3, bytes.fromhex(' '.join([
    "BC",       # 0098: Pop
    "C0",       # 0099: Push zero
])))
# - Don't forget "Nirwanda"
writeHelper(romBytes, 0xDE2B8, bytes.fromhex(' '.join([
    "BC",       # 009D: Pop
    "C0",       # 009E: Push zero
])))
# - Don't forget "Ice"
writeHelper(romBytes, 0xDE2BD, bytes.fromhex(' '.join([
    "BC",       # 00A2: Pop
    "C0",       # 00A3: Push zero
])))
# - Don't forget "Docks"
writeHelper(romBytes, 0xDE2C2, bytes.fromhex(' '.join([
    "BC",       # 00A7: Pop
    "C0",       # 00A8: Push zero
])))
# - Don't forget "Bremerton"
writeHelper(romBytes, 0xDE2C7, bytes.fromhex(' '.join([
    "BC",       # 00AC: Pop
    "C0",       # 00AD: Push zero
])))
# TODO:
# Should the "Vampire respawns after going through the portal" behaviour
# be reinstated? It happens in vanilla because the portal takes away the
# "Laughlyn" keyword, and the Vampire appears if you don't know it.
# The Vampire has been updated to appear (or not appear) based on its
# event flags, so this arguably good bug doesn't happen anymore.
# To restore the vanilla behaviour, write 0x00 to the Vampire's flags as
# part of the portal's behaviour script.

# Elevator Doors helper script
# - Show the correct floor on the floor indicator in the "game won" case
writeHelper(romBytes, 0xF76E7, bytes.fromhex(' '.join([
    "00 20",    # 001A: Push unsigned byte 0x20
    "C2",       # 001C: Push unsigned byte from $13+00 <-- Spawn index
    "58 33",    # 001D: Set bits of object's flags
    "48 24 00", # 001F: Jump to 0024
])))
# - Remove the arrival delay from the Drake Towers / Aneki Building elevators
writeHelper(romBytes, 0xF771D, bytes.fromhex(' '.join([
    # SET_INDICATOR_FLOOR_NUMBER
    "16 07",    # 0050: Push short from $13+07         <-- Elevator Doors floor number
    "02 01",    # 0052: Push unsigned byte from $13+01 <-- "Event short" index for indicator's floor number
    "58 12",    # 0054: Write short to 7E3BBB+n        <-- Set indicator's floor number
    # SET_INDICATOR_DIRECTION
    "02 03",    # 0056: Push unsigned byte from $13+03 <-- 0x01 ascending, 0x00 descending
    "02 02",    # 0058: Push unsigned byte from $13+02 <-- "Event short" index for indicator's direction
    "58 12",    # 005A: Write short to 7E3BBB+n        <-- Set indicator's direction
    # CHECK_IF_DOORS_ALREADY_OPEN
    "16 05",    # 005C: Push short from $13+05         <-- Object-id of "elevator state object"
    "58 BA",    # 005E: Push object's flags
    "02 09",    # 0060: Push unsigned byte from $13+09 <-- 0x01 ascending, 0x02 descending
    "7E",       # 0062: Bitwise AND
    "C0",       # 0063: Push zero
    "9A",       # 0064: Check if greater than
    "C2",       # 0065: Push unsigned byte from $13+00 <-- Spawn index
    "58 02",    # 0066: Push object's flags
    "00 20",    # 0068: Push unsigned byte 0x20
    "7E",       # 006A: Bitwise AND
    "BE",       # 006B: Convert to boolean
    "80",       # 006C: Bitwise OR
    "44 78 00", # 006D: If false, jump to CHANGE_SPRITE
    # Previously, the conditional above was "If true, jump to 00DE".
    # (00DE contains the code for the "doors already open" case.)
    # However, 00DE doesn't set the 0x20 flag on the Elevator Doors.
    # This flag is what KEEPS the doors unlocked, since the "elevator
    # state object" flags get cleared when you change floors.
    # So the previous code created a bug in the Aneki Building:
    # - Hack an Aneki computer to unlock the elevator
    # - Successful hacking sets an "elevator state object" flag
    # - This flag unlocks the elevator (temporarily)
    # - Ascend to the next floor (which clears the flag)
    # - Return to the previous floor
    # - The elevator to the next floor is locked again
    # Solution: Set the 0x20 flag here before jumping to 00DE.
    "00 20",    # 0070: Push unsigned byte 0x20
    "C2",       # 0072: Push unsigned byte from $13+00 <-- Spawn index
    "58 33",    # 0073: Set bits of object's flags
    "48 DE 00", # 0075: Jump to 00DE
    # CHANGE_SPRITE
    "00 02",    # 0078: Push unsigned byte 0x02
    "C2",       # 007A: Push unsigned byte from $13+00 <-- Spawn index
    "58 D0",    # 007B: Display sprite
    # TOP_OF_LOOP
    "00 06",    # 007D: Push unsigned byte 0x06
    "00 01",    # 007F: Push unsigned byte 0x01
    "58 9E",    # 0081: Register menu options / time delay
    "BC",       # 0083: Pop
    "16 05",    # 0084: Push short from $13+05         <-- Object-id of "elevator state object"
    "58 BA",    # 0086: Push object's flags
    "02 09",    # 0088: Push unsigned byte from $13+09 <-- 0x01 ascending, 0x02 descending
    "7E",       # 008A: Bitwise AND
    "C0",       # 008B: Push zero
    "9A",       # 008C: Check if greater than
    "C2",       # 008D: Push unsigned byte from $13+00 <-- Spawn index
    "58 02",    # 008E: Push object's flags
    "00 20",    # 0090: Push unsigned byte 0x20
    "7E",       # 0092: Bitwise AND
    "BE",       # 0093: Convert to boolean
    "80",       # 0094: Bitwise OR
    "44 7D 00", # 0095: If false, jump to TOP_OF_LOOP
    # OPEN_DOORS
    "48 A6 00", # 0098: Jump to 00A6
])))

# Elevator Doors that never open
# Show the correct floor on the floor indicator
expandedOffset = scriptHelper(
    scriptNumber = 0xB8,
    argsLen      = 0x02, # Script 0xB8 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0xB8 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 byte of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        # CHECK_IF_DRAKE_TOWERS_1F_DESCENDING_ELEVATOR
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 CB",    # 0003: Push object-id
        "14 0B 14", # 0005: Push short 0x140B
        "AA",       # 0008: Check if equal
        "44 15 00", # 0009: If not equal, jump to CHECK_IF_ANEKI_BUILDING_1F_DESCENDING_ELEVATOR
        # DRAKE_TOWERS_1F_DESCENDING_ELEVATOR
        "00 01",    # 000C: Push unsigned byte 0x01
        "00 22",    # 000E: Push unsigned byte 0x22
        "58 12",    # 0010: Write short to 7E3BBB+n
        "48 38 00", # 0012: Jump to DISPLAY_SPRITE
        # CHECK_IF_ANEKI_BUILDING_1F_DESCENDING_ELEVATOR
        "C2",       # 0015: Push unsigned byte from $13+00 <-- Spawn index
        "58 CB",    # 0016: Push object-id
        "14 CC 13", # 0018: Push short 0x13CC
        "AA",       # 001B: Check if equal
        "44 28 00", # 001C: If not equal, jump to CHECK_IF_ANEKI_BUILDING_5F_ASCENDING_ELEVATOR
        # ANEKI_BUILDING_1F_DESCENDING_ELEVATOR
        "00 02",    # 001F: Push unsigned byte 0x02
        "00 22",    # 0021: Push unsigned byte 0x22
        "58 12",    # 0023: Write short to 7E3BBB+n
        "48 38 00", # 0025: Jump to DISPLAY_SPRITE
        # CHECK_IF_ANEKI_BUILDING_5F_ASCENDING_ELEVATOR
        "C2",       # 0028: Push unsigned byte from $13+00 <-- Spawn index
        "58 CB",    # 0029: Push object-id
        "14 2E 14", # 002B: Push short 0x142E
        "AA",       # 002E: Check if equal
        "44 38 00", # 002F: If not equal, jump to DISPLAY_SPRITE
        # ANEKI_BUILDING_5F_ASCENDING_ELEVATOR
        "00 06",    # 0032: Push unsigned byte 0x06
        "00 20",    # 0034: Push unsigned byte 0x20
        "58 12",    # 0036: Write short to 7E3BBB+n
        # DISPLAY_SPRITE
        "00 05",    # 0038: Push unsigned byte 0x05
        "00 02",    # 003A: Push unsigned byte 0x02
        "C2",       # 003C: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 003D: Display sprite with facing direction
        "14 00 01", # 003F: Push short 0x0100
        "C2",       # 0042: Push unsigned byte from $13+00 <-- Spawn index
        "58 CE",    # 0043: Set bits of 7E1474+n
        "C2",       # 0045: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0046: ???
        "56",       # 0048: End
    ],
)

# Floor indicator helper script
expandedOffset = scriptHelper(
    scriptNumber = 0xA,
    argsLen      = 0x0A, # Script 0xA now takes 10 bytes (= 5 stack items) as arguments
    returnLen    = 0x00, # Script 0xA now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x06, # Header byte: Script uses 0x06 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00  <-- Spawn index
        "2C 01",    # 0002: Pop byte to $13+01  <-- 0x20 ascending, 0x22 descending ("Event short" index for indicator's floor number)
        "2C 02",    # 0004: Pop byte to $13+02  <-- 0x24 ascending, 0x26 descending ("Event short" index for indicator's direction)
        "2C 03",    # 0006: Pop byte to $13+03  <-- 0x40 ascending, 0x80 descending
        "34 04",    # 0008: Pop short to $13+04 <-- 0x175A for Drake Towers, 0x16C0 for Aneki Building ("Elevator state object" object-ids)
        # CLEAR_FLAGS
        "02 03",    # 000A: Push unsigned byte from $13+03 <-- 0x40 ascending, 0x80 descending
        "84",       # 000C: Bitwise NOT
        "16 04",    # 000D: Push short from $13+04         <-- Object-id of "elevator state object"
        "58 4B",    # 000F: Clear bits of object's flags
        # WAIT_FOR_NEW_FLOOR_NUMBER
        "00 02",    # 0011: Push unsigned byte 0x02
        "00 01",    # 0013: Push unsigned byte 0x01
        "58 9E",    # 0015: Register menu options / time delay
        "BC",       # 0017: Pop
        # UPDATE_FLOOR_INDICATOR
        "C0",       # 0018: Push zero
        "02 01",    # 0019: Push unsigned byte from $13+01 <-- "Event short" index for indicator's floor number
        "58 57",    # 001B: Read short from 7E3BBB+n
        "88",       # 001D: Decrement
        "C2",       # 001E: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 001F: Display sprite with facing direction
        # DONE
        "C2",       # 0021: Push unsigned byte from $13+00 <-- Spawn index
        "58 5B",    # 0022: ???
        "56",       # 0024: End
    ],
)

# Helicopter Pilot <-- Drake Towers
# - Stock the $13,000 case at the Dark Blade Gun Shop (vanilla: Concealed Jacket)
writeHelper(romBytes, 0x177C0, bytes.fromhex(' '.join([
    "0A FD",    # 0010: Push signed byte 0xFD
    "14 45 10", # 0012: Push short 0x1045 <-- Object-id of "Concealed Jacket" glass case
    "58 4B",    # 0015: Clear bits of object's flags
])))

# Helicopter Pilot <-- Volcano
# - Silently teach the "Drake" keyword, to avoid a possible softlock
# - Don't spawn the pilot after landing the helicopter. Spawn the pilot
#   when entering the helipad map from Sublevel Zero of the volcano.
#   (This is vanilla behaviour, but implemented more efficiently.)
writeHelper(romBytes, 0x1753A, bytes.fromhex(' '.join([
    "00 0E",    # 0002: Push unsigned byte 0x0E <-- Keyword-id for "Drake"
    "58 71",    # 0004: Learn keyword
    "18 E2 2D", # 0006: Push short from $7E2DE2
    "14 F4 00", # 0009: Push short 0x00F4
    "AA",       # 000C: Check if equal
    "46 12 00", # 000D: If equal, jump to 0012
    "56",       # 0010: End
    "56",       # 0011: End
])))

# Serpent Scales
writeHelper(romBytes, 0xD26C3, bytes.fromhex(' '.join([
    "B6 01",    # Move the spawn point to match the Gold Naga's spawn point
    "22 11",    # Gold Naga's spawn coordinates: (438, 290, 64)
])))
expandedOffset = scriptHelper(
    scriptNumber = 0x17F,
    argsLen      = 0x02, # Script 0x17F now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x17F now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x04, # Header byte: Script uses 0x04 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C2",       # 0002: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 0003: Check if object has an owner
        "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push unsigned byte from $13+00 <-- Spawn index
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        # TOP_OF_LOOP
        "C2",       # 000C: Push unsigned byte from $13+00 <-- Spawn index
        "58 C5",    # 000D: Check if object has an owner
        "2C 01",    # 000F: Pop byte to $13+01 <-- Whether object has an owner
        "C0",       # 0011: Push zero
        "0C 01",    # 0012: Push signed byte from $13+01 <-- Whether object has an owner
        "52 AA 02", # 0014: Execute behaviour script 0x2AA = Interaction menu helper
        "BA",       # 0017: Duplicate
        "34 02",    # 0018: Pop short to $13+02 <-- Selected menu option
        # CHECK_IF_EXAMINE
        "00 80",    # 001A: Push unsigned byte 0x80
        "AA",       # 001C: Check if equal
        "44 3D 00", # 001D: If not equal, jump to CHECK_IF_PICKUP
        # EXAMINE
        # Interaction menu option: Examine
        "00 03",    # 0020: Push unsigned byte 0x03
        "00 FF",    # 0022: Push unsigned byte 0xFF
        "00 32",    # 0024: Push unsigned byte 0x32
        "C2",       # 0026: Push unsigned byte from $13+00 <-- Spawn index
        "58 4C",    # 0027: Play sound effect
        "00 F0",    # 0029: Push unsigned byte 0xF0 <-- Was 0x78
        "00 9A",    # 002B: Push unsigned byte 0x9A
        "14 00 08", # 002D: Push short 0x0800
        "00 03",    # 0030: Push unsigned byte 0x03
        "00 18",    # 0032: Push unsigned byte 0x18
        "00 15",    # 0034: Push unsigned byte 0x15
        "00 02",    # 0036: Push unsigned byte 0x02
        "58 C7",    # 0038: Print text ("The slippery scale of a reptile.")
        "48 4F 00", # 003A: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_PICKUP
        "16 02",    # 003D: Push short from $13+02 <-- Selected menu option
        "00 10",    # 003F: Push unsigned byte 0x10
        "AA",       # 0041: Check if equal
        "44 4F 00", # 0042: If not equal, jump to BOTTOM_OF_LOOP
        # PICKUP
        # Interaction menu option: Pickup
        "C2",       # 0045: Push unsigned byte from $13+00 <-- Spawn index
        "58 6F",    # 0046: Set object's owner to Jake
        "52 4B 00", # 0048: Execute behaviour script 0x4B = "Got item" sound effect
        "0A FF",    # 004B: Push signed byte 0xFF
        "2C 01",    # 004D: Pop byte to $13+01 <-- Whether object has an owner
        # BOTTOM_OF_LOOP
        "0C 01",    # 004F: Push signed byte from $13+01 <-- Whether object has an owner
        "44 0C 00", # 0051: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 0054: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0055: Despawn object
        "56",       # 0057: End
    ],
)
# Use facing direction 05's sprite for direction 00
romBytes[0x6683C] = 0x08

# Serpent Scales: Naga <-- Gold Naga boss
# Reveal the new item shuffled to this location
expandedOffset = scriptHelper(
    scriptNumber = 0x1FA,
    argsLen      = 0x02, # Script 0x1FA now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x1FA now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x02, # Header byte: Script uses 0x02 bytes of $13+xx space
    maxStackLen  = 0x0A, # Header byte: Maximum stack height of 0x0A bytes (= 5 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        f"14 {romBytes[0xD26C7+0]:02X} {romBytes[0xD26C7+1]:02X}",
                    # 0002: Push short 0x####  <-- Item drop's object-id
        "14 B2 08", # 0005: Push short 0x08B2  <-- Object-id for Jake
        "58 42",    # 0008: Check if first object owns second object
        "46 62 00", # 000A: If true, jump to DONE
        # GOLD_NAGA_BEHAVIOUR
        "14 CB 07", # 000D: Push short 0x07CB <-- Object-id for Gold Naga
        "00 08",    # 0010: Push unsigned byte 0x08
        "58 12",    # 0012: Write short to 7E3BBB+n
        "00 32",    # 0014: Push unsigned byte 0x32
        "00 C0",    # 0016: Push unsigned byte 0xC0
        "00 01",    # 0018: Push unsigned byte 0x01
        "C0",       # 001A: Push zero
        "C2",       # 001B: Push unsigned byte from $13+00 <-- Spawn index
        "52 0B 00", # 001C: Execute behaviour script 0xB
        # GOLD_NAGA_DEFEATED
        f"14 {romBytes[0xD26C7+0]:02X} {romBytes[0xD26C7+1]:02X}",
                    # 001F: Push short 0x####   <-- Item drop's object-id
        "58 BA",    # 0022: Push object's flags <-- Item drop's flags
        "00 80",    # 0024: Push unsigned byte 0x80
        "7E",       # 0026: Bitwise AND
        "BE",       # 0027: Convert to boolean
        "46 62 00", # 0028: If true, jump to DONE
        # REVEAL_ITEM_DROP
        f"14 {romBytes[0xD26C7+0]:02X} {romBytes[0xD26C7+1]:02X}",
                    # 002B: Push short 0x####   <-- Item drop's object-id
        "58 C2",    # 002E: Push object's RAM_1 <-- Item drop's spawn index
        "2C 01",    # 0030: Pop byte to $13+01  <-- Item drop's spawn index
        "C2",       # 0032: Push unsigned byte from $13+00 <-- Spawn index
        "58 51",    # 0033: Push object's Z coordinate / 4
        "00 02",    # 0035: Push unsigned byte 0x02
        "7A",       # 0037: Left shift
        "C2",       # 0038: Push unsigned byte from $13+00 <-- Spawn index
        "58 50",    # 0039: Push object's Y coordinate / 4
        "00 02",    # 003B: Push unsigned byte 0x02
        "7A",       # 003D: Left shift
        "C2",       # 003E: Push unsigned byte from $13+00 <-- Spawn index
        "58 4F",    # 003F: Push object's X coordinate / 4
        "00 02",    # 0041: Push unsigned byte 0x02
        "7A",       # 0043: Left shift
        "02 01",    # 0044: Push unsigned byte from $13+01 <-- Item drop's spawn index
        "58 82",    # 0046: Set object X/Y/Z position
        "00 08",    # 0048: Push unsigned byte 0x08
        "C0",       # 004A: Push zero
        "C0",       # 004B: Push zero
        "02 01",    # 004C: Push unsigned byte from $13+01 <-- Item drop's spawn index
        "58 79",    # 004E: Set object X/Y/Z deltas?
        "00 80",    # 0050: Push unsigned byte 0x80
        "02 01",    # 0052: Push unsigned byte from $13+01 <-- Item drop's spawn index
        "58 33",    # 0054: Set bits of object's flags
        "00 01",    # 0056: Push unsigned byte 0x01
        "BA",       # 0058: Duplicate
        "58 9E",    # 0059: Register menu options / time delay
        "BC",       # 005B: Pop
        "00 20",    # 005C: Push unsigned byte 0x20
        "02 01",    # 005E: Push unsigned byte from $13+01 <-- Item drop's spawn index
        "58 CE",    # 0060: Set bits of 7E1474+n <-- Makes the item drop subject to gravity
        # DONE
        "C2",       # 0062: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0063: Despawn object
        "56",       # 0065: End
    ],
)

# Scientist <-- Professor Pushkin
# - Silently teach the "Head Computer" keyword, to avoid a possible softlock
# - Stock the $30,000 case at the Dark Blade Gun Shop (vanilla: Full Bodysuit)
# - Stock the $40,000 case at the Dark Blade Gun Shop (vanilla: AS-7 A. Cannon)
expandedOffset = scriptHelper(
    scriptNumber = 0x38A,
    argsLen      = 0x02, # Script 0x38A now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x38A now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x06, # Header byte: Maximum stack height of 0x06 bytes (= 3 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "00 14",    # 0002: Push unsigned byte 0x14 <-- Keyword-id for "Head Computer"
        "58 71",    # 0004: Learn keyword
        "00 04",    # 0006: Push unsigned byte 0x04
        "C0",       # 0008: Push zero
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 000A: Display sprite with facing direction
        "00 40",    # 000C: Push unsigned byte 0x40
        "C2",       # 000E: Push unsigned byte from $13+00 <-- Spawn index
        "58 B4",    # 000F: Register conversation
        # TOP_OF_LOOP
        "C2",       # 0011: Push unsigned byte from $13+00 <-- Spawn index
        "58 6C",    # 0012: Face towards Jake
        "00 05",    # 0014: Push unsigned byte 0x05
        "00 03",    # 0016: Push unsigned byte 0x03
        "58 9E",    # 0018: Register menu options / time delay
        "BC",       # 001A: Pop
        "C2",       # 001B: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 001C: Push object's flags
        "00 80",    # 001E: Push unsigned byte 0x80
        "7E",       # 0020: Bitwise AND
        "BE",       # 0021: Convert to boolean
        "44 11 00", # 0022: If false, jump to TOP_OF_LOOP
        # STOCK_DARK_BLADE_CASES
        "0A FD",    # 0025: Push signed byte 0xFD
        "14 F1 0F", # 0027: Push short 0x0FF1 <-- Object-id of "Full Bodysuit" glass case
        "58 4B",    # 002A: Clear bits of object's flags
        "0A FD",    # 002C: Push signed byte 0xFD
        "14 14 10", # 002E: Push short 0x1014 <-- Object-id of "AS-7 A. Cannon" glass case
        "58 4B",    # 0031: Clear bits of object's flags
        # CHECK_IF_AI_COMPUTER_DESTROYED
        "14 7B 1B", # 0033: Push short 0x1B7B <-- Object-id of AI Computer
        "58 BA",    # 0036: Push object's flags
        "00 40",    # 0038: Push unsigned byte 0x40
        "7E",       # 003A: Bitwise AND
        "BE",       # 003B: Convert to boolean
        "46 4D 00", # 003C: If true, jump to AI_COMPUTER_DESTROYED
        # AI_COMPUTER_NOT_DESTROYED
        "14 AA 01", # 003F: Push short 0x01AA
        "58 56",    # 0042: Teleport to door destination
        "00 01",    # 0044: Push unsigned byte 0x01
        "BA",       # 0046: Duplicate
        "58 9E",    # 0047: Register menu options / time delay
        "BC",       # 0049: Pop
        "48 60 00", # 004A: Jump to DONE
        # AI_COMPUTER_DESTROYED
        "00 03",    # 004D: Push unsigned byte 0x03
        "00 2C",    # 004F: Push unsigned byte 0x2C
        "58 12",    # 0051: Write short to 7E3BBB+n
        "00 F2",    # 0053: Push unsigned byte 0xF2
        "C0",       # 0055: Push zero
        "00 14",    # 0056: Push unsigned byte 0x14
        "58 54",    # 0058: Teleport to door destination with vehicle cutscene
        "00 01",    # 005A: Push unsigned byte 0x01
        "BA",       # 005C: Duplicate
        "58 9E",    # 005D: Register menu options / time delay
        "BC",       # 005F: Pop
        # DONE
        "C2",       # 0060: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0061: Despawn object
        "56",       # 0063: End
    ],
)

# Computer <-- Aneki Building lobby
# Remove the check for the Aneki Password
writeHelper(romBytes, 0xFDE62, bytes.fromhex(' '.join([
    "BC",       # 0040: Pop
    "C0",       # 0041: Push zero
    "BC",       # 0042: Pop
])))

# AI Computer
expandedOffset = scriptHelper(
    scriptNumber = 0x105,
    argsLen      = 0x02, # Script 0x105 now takes 2 bytes (= 1 stack item) as arguments
    returnLen    = 0x00, # Script 0x105 now returns 0 bytes (= 0 stack items) upon completion
    offset       = expandedOffset,
    scratchLen   = 0x01, # Header byte: Script uses 0x01 bytes of $13+xx space
    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
    commandList  = [
        "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
        "C0",       # 0002: Push zero
        "C0",       # 0003: Push zero
        "C2",       # 0004: Push unsigned byte from $13+00 <-- Spawn index
        "58 D1",    # 0005: Display sprite with facing direction
        "00 80",    # 0007: Push unsigned byte 0x80
        "C2",       # 0009: Push unsigned byte from $13+00 <-- Spawn index
        "58 CE",    # 000A: Set bits of 7E1474+n <-- Makes the AI Computer object invisible
        # CHECK_IF_AI_COMPUTER_ALREADY_DESTROYED
        "C2",       # 000C: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 000D: Push object's flags
        "00 40",    # 000F: Push unsigned byte 0x40
        "7E",       # 0011: Bitwise AND
        "BE",       # 0012: Convert to boolean
        "46 90 00", # 0013: If true, jump to DONE
        # CHECK_IF_JUST_FINISHED_DECKING
        "C2",       # 0016: Push unsigned byte from $13+00 <-- Spawn index
        "58 02",    # 0017: Push object's flags
        "00 01",    # 0019: Push unsigned byte 0x01
        "7E",       # 001B: Bitwise AND
        "BE",       # 001C: Convert to boolean
        "44 7C 00", # 001D: If false, jump to WAIT_FOR_CYBERDECK
        # JUST_FINISHED_DECKING
        "00 01",    # 0020: Push unsigned byte 0x01
        "BA",       # 0022: Duplicate
        "58 9E",    # 0023: Register menu options / time delay
        "BC",       # 0025: Pop
        "14 7E FF", # 0026: Push short 0xFF7E
        "C2",       # 0029: Push unsigned byte from $13+00 <-- Spawn index
        "58 7A",    # 002A: Clear bits of object's flags <-- Clear the AI Computer's 0x80 and 0x01 flags
        # CHECK_IF_JUST_FINISHED_DESTROYING_THE_AI_COMPUTER
        "04 AE 1D", # 002C: Push unsigned byte from $7E1DAE <-- Bit flags for interacted-with Matrix objects
        "00 80",    # 002F: Push unsigned byte 0x80
        "7E",       # 0031: Bitwise AND
        "BE",       # 0032: Convert to boolean
        "44 7C 00", # 0033: If false, jump to WAIT_FOR_CYBERDECK
        # JUST_FINISHED_DESTROYING_THE_AI_COMPUTER
        "00 01",    # 0036: Push unsigned byte 0x01
        "14 5A 02", # 0038: Push short 0x025A
        "C0",       # 003B: Push zero
        "00 03",    # 003C: Push unsigned byte 0x03
        "00 10",    # 003E: Push unsigned byte 0x10
        "00 02",    # 0040: Push unsigned byte 0x02
        "00 08",    # 0042: Push unsigned byte 0x08
        "58 C7",    # 0044: Print text ("PROGRAM DOWNLOADED")
        "58 A2",    # 0046: Wait for player input
        "00 40",    # 0048: Push unsigned byte 0x40
        "C2",       # 004A: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 004B: Set bits of object's flags
        ## STOCK_DARK_BLADE_CASES
        #"0A FD",    # ____: Push signed byte 0xFD
        #"14 F1 0F", # ____: Push short 0x0FF1 <-- Object-id of "Full Bodysuit" glass case
        #"58 4B",    # ____: Clear bits of object's flags
        #"0A FD",    # ____: Push signed byte 0xFD
        #"14 14 10", # ____: Push short 0x1014 <-- Object-id of "AS-7 A. Cannon" glass case
        #"58 4B",    # ____: Clear bits of object's flags
        # CHECK_IF_PROFESSOR_PUSHKIN_RESCUED
        "14 B4 04", # 004D: Push short 0x04B4 <-- Object-id of Professor Pushkin
        "58 BA",    # 0050: Push object's flags
        "00 80",    # 0052: Push unsigned byte 0x80
        "7E",       # 0054: Bitwise AND
        "BE",       # 0055: Convert to boolean
        "46 66 00", # 0056: If true, jump to PROFESSOR_PUSHKIN_RESCUED
        # PROFESSOR_PUSHKIN_NOT_RESCUED
        "00 A0",    # 0059: Push unsigned byte 0xA0
        "58 56",    # 005B: Teleport to door destination <-- Reload the AI Computer room
        "00 01",    # 005D: Push unsigned byte 0x01
        "BA",       # 005F: Duplicate
        "58 9E",    # 0060: Register menu options / time delay
        "BC",       # 0062: Pop
        "48 90 00", # 0063: Jump to DONE
        # PROFESSOR_PUSHKIN_RESCUED
        "00 03",    # 0066: Push unsigned byte 0x03
        "00 2C",    # 0068: Push unsigned byte 0x2C
        "58 12",    # 006A: Write short to 7E3BBB+n
        "00 F2",    # 006C: Push unsigned byte 0xF2
        "C0",       # 006E: Push zero
        "00 14",    # 006F: Push unsigned byte 0x14
        "58 54",    # 0071: Teleport to door destination with vehicle cutscene
        "00 01",    # 0073: Push unsigned byte 0x01
        "BA",       # 0075: Duplicate
        "58 9E",    # 0076: Register menu options / time delay
        "BC",       # 0078: Pop
        "48 90 00", # 0079: Jump to DONE
        # WAIT_FOR_CYBERDECK
        # Using a Cyberdeck on the AI Computer will set the latter's 0x80 flag.
        "C2",       # 007C: Push unsigned byte from $13+00 <-- Spawn index
        "52 01 01", # 007D: Execute behaviour script 0x101 = Wait for object's 0x80 flag to be set
        "00 01",    # 0080: Push unsigned byte 0x01
        "C2",       # 0082: Push unsigned byte from $13+00 <-- Spawn index
        "58 33",    # 0083: Set bits of object's flags
        "00 03",    # 0085: Push unsigned byte 0x03
        "C0",       # 0087: Push zero
        "00 A0",    # 0088: Push unsigned byte 0xA0
        "00 10",    # 008A: Push unsigned byte 0x10
        "C2",       # 008C: Push unsigned byte from $13+00 <-- Spawn index
        "52 E7 02", # 008D: Execute behaviour script 0x2E7 = Matrix login helper script
        # DONE
        "C2",       # 0090: Push unsigned byte from $13+00 <-- Spawn index
        "58 B8",    # 0091: Despawn object
        "56",       # 0093: End
    ],
)





# ------------------------------------------------------------------------
# TODO:
# This is the start of the QUICK UGLY CHANGE SECTION
# (Temporary changes for testing stuff)
# (Some of these may get promoted to permanent changes)
# ------------------------------------------------------------------------

# Double Jake's walking speed
# - 5EF1 to 5F02 are X coordinate deltas for Jake walking
# - 5F03 to 5F14 are Y coordinate deltas for Jake walking
# - Ordering: deltas for directions 00-07, delta for no-input case
for offset in range(0x5EF1, 0x5F15, 2):
    delta = struct.unpack_from("<h", romBytes, offset)[0]
    delta *= 2
    struct.pack_into("<h", romBytes, offset, delta)

# ------------------------------------------------------------------------

# Auto-pickup nuyen dropped by defeated enemies
# Does not affect nuyen-items
# TODO: This also affects the multiple nuyen spawned at once
#   from examining Coffin Lids. Each nuyen prints an "amount"
#   text window, but the windows are all in the same place,
#   so only the topmost is visible. This makes it look like
#   you've picked up one 10-20 nuyen when you've actually
#   picked up several. Maybe change the Coffin Lids to drop
#   a single 30-60 nuyen instead?

# Behaviour script 15C: Random 10/20 nuyen
# Jump from "display sprite" setup to the pickup code
writeHelper(romBytes, 0xF96CD, bytes.fromhex(' '.join([
    "48 1D 00", # 0009: Jump to 001D
])))

# Behaviour script 15E: Random 30/40/50/60 nuyen
# Jump from "display sprite" setup to the pickup code
writeHelper(romBytes, 0xF972C, bytes.fromhex(' '.join([
    "48 1D 00", # 0009: Jump to 001D
])))

# Behaviour script 15F: Random 70/80/90/100 nuyen
# Jump from "display sprite" setup to the pickup code
writeHelper(romBytes, 0xF97C7, bytes.fromhex(' '.join([
    "48 1D 00", # 0009: Jump to 001D
])))

# Behaviour script 164: Random 150/170/180/200 nuyen
# Jump from "display sprite" setup to the pickup code
writeHelper(romBytes, 0xF9863, bytes.fromhex(' '.join([
    "48 1D 00", # 0009: Jump to 001D
])))

# Behaviour script 247: Spawn random 30/40/50/60 nuyen and fall lower-left to ground
# Repoint to use script 15E ("Random 30/40/50/60 nuyen") instead
struct.pack_into(
    "<H", romBytes, 0x15D18 + (2 * 0x247),
    struct.unpack_from("<H", romBytes, 0x15D18 + (2 * 0x15E))[0]
)

# Behaviour script 270: Spawn random 30/40/50/60 nuyen and fall lower-right to ground
# Repoint to use script 15E ("Random 30/40/50/60 nuyen") instead
struct.pack_into(
    "<H", romBytes, 0x15D18 + (2 * 0x270),
    struct.unpack_from("<H", romBytes, 0x15D18 + (2 * 0x15E))[0]
)

# ------------------------------------------------------------------------

## Disable randomly-spawning enemies
#writeHelper(romBytes, 0xF9B05, bytes.fromhex(' '.join([
#    "00 00",    # 001C: Push unsigned byte 0x00
#])))

# ------------------------------------------------------------------------

# Forbid item duplication (unless explicitly permitted)
#
# In vanilla, after selecting Use/Give/Throw on an item, there is a
# one-frame delay before target selection begins. During that frame,
# it's possible to re-enter the menu and select Use/Give/Throw on
# the same item a second time.
#
# This makes the "item duplication" glitch possible:
# - Stand next to a merchant NPC
# - Select "Give" twice on an equippable item (weapon or armor)
# - Use the first "Give" to sell the item to the merchant
# - Use the second "Give" to give the item back to yourself
#
# You can also use this behaviour to underflow item quantities:
# - Have exactly one Slap Patch in your inventory
# - Select "Use" twice on the Slap Patch
# - Slap Patch quantity: 1 --> 0 --> 255 (integer underflow)
# - This also works for Grenades
#
# The one-frame delay appears to be caused by the Use/Give/Throw
# textbox helper scripts, which wait a frame between erasing all
# open text windows and opening their own brand new text window
# ("Use on", "Give to", "Throw at").
# So, let's remove that delay and see what happens.

if not args.allow_item_duplication:
    # Behaviour script F9: "Use on" textbox helper script
    writeHelper(romBytes, 0xDED54, bytes.fromhex(' '.join([
        "C0",       # 000A: Push zero
        "BE",       # 000B: Convert to boolean
        "BE",       # 000C: Convert to boolean
        "BE",       # 000D: Convert to boolean
        "BE",       # 000E: Convert to boolean
        "BC",       # 000F: Pop
    ])))
    # Behaviour script 23F: "Give to" textbox helper script
    writeHelper(romBytes, 0xDED76, bytes.fromhex(' '.join([
        "C0",       # 000A: Push zero
        "BE",       # 000B: Convert to boolean
        "BE",       # 000C: Convert to boolean
        "BE",       # 000D: Convert to boolean
        "BE",       # 000E: Convert to boolean
        "BC",       # 000F: Pop
    ])))
    # Behaviour script 1FB: "Throw at" textbox helper script
    writeHelper(romBytes, 0xDED98, bytes.fromhex(' '.join([
        "C0",       # 000A: Push zero
        "BE",       # 000B: Convert to boolean
        "BE",       # 000C: Convert to boolean
        "BE",       # 000D: Convert to boolean
        "BE",       # 000E: Convert to boolean
        "BC",       # 000F: Pop
    ])))

# ------------------------------------------------------------------------

# Shorten the Matrix entry sequences
#
# Matrix entry text uses the following control codes:
#    [00] = End
#    [01] = Text style: Dark green
#    [02] = Text style: Bright green
#    [03] = Text style: Blink
#    [04] = Newline
# [05 XX] = Pause for XX frames
#    [06] = Backspace

# Matrix entry text - Datajack malfunction
writeHelper(romBytes, 0xC4F6, b"".join([
    bytes.fromhex("04 04 02"),
    b"ERROR!",
    bytes.fromhex("04 04"),
    b"- DATAJACK MALFUNCTION -",
    bytes.fromhex("04 04 05 96 00"),
]))

# Matrix entry text - Generic (e.g. Glutman's office)
writeHelper(romBytes, 0xC6E8, b"".join([
    bytes.fromhex("04 04 02"),
    b"NAUCAS-SEA-2309",
    bytes.fromhex("04"),
    b"Central Alpha",
    bytes.fromhex("04 04 05 3C 00"),
]))

# Matrix entry text - Drake Towers
writeHelper(romBytes, 0xC820, b"".join([
    bytes.fromhex("04 04 02"),
    b"NAUCAS-SEA-5437-DRAKEHQ",
    bytes.fromhex("04"),
    b"Drake Towers",
    bytes.fromhex("04 04 05 3C 00"),
]))

# Matrix entry text - Drake Volcano
writeHelper(romBytes, 0xC916, b"".join([
    bytes.fromhex("04 04 02"),
    b"NAUCAS-SEA-8194-DRAKEVOLC",
    bytes.fromhex("04"),
    b"Drake Volcano",
    bytes.fromhex("04 04 05 3C 00"),
]))

# Matrix entry text - Aneki
writeHelper(romBytes, 0xCB1D, b"".join([
    bytes.fromhex("04 04 02"),
    b"NAUCAS-SEA-3458-ANEKIHQ",
    bytes.fromhex("04"),
    b"Aneki Corporation",
    bytes.fromhex("04 04 05 3C 00"),
]))

# Matrix entry text - Matrix Systems
writeHelper(romBytes, 0xCBF0, b"".join([
    bytes.fromhex("04 04 02"),
    b"Unlisted",
    bytes.fromhex("04"),
    b"Matrix Systems Inc.",
    bytes.fromhex("04 04 05 3C 00"),
]))

# While testing the changes above, I noticed that sometimes the music
# would become glitchy after exiting a computer. So, let's fix that.
# The currently-playing music's track number is stored at $1CFA.
# During some events that interrupt the music (e.g. battle), the game
# backs up the track number to $1FE6, and restores it later.
# Entering a computer doesn't back up the currently-playing music,
# but exiting a computer restores the backed-up value.
# Most of the time, there's a stale backed-up value (e.g. written by
# a recent battle), so this mismatch goes unnoticed - but if you load
# a save and enter a computer without any battles in between, $1FE6
# will be undefined and the music will become glitchy.
# To test this for yourself:
# - Save the game at Jake's apartment, then load the save
# - Walk through Tenth Street Center to Glutman's office
# - Enter and exit Glutman's computer
# Reset if you get into a battle along the way.
#
# So, let's back up the current music when entering a computer.
# The code behind [58 7D] ("Enter the Matrix" in behaviour script)
# gets the pointer to the decker's 7E2E00 data in an inefficient and
# possibly buggy way, so let's optimize that to free up some space.

writeHelper(romBytes, 0x6327, bytes.fromhex(' '.join([
    "AD FA 1C",    # 00/E327: LDA $1CFA     ; $1CFA = Current music
    "8D E6 1F",    # 00/E32A: STA $1FE6     ; $1FE6 = Backup of current music
    "A5 08",       # 00/E32D: LDA $08       ; $08 = Object-id of decker
    "AA",          # 00/E32F: TAX
    "BF 32 B0 8D", # 00/E330: LDA $8DB032,X ; A = Pointer to decker's 7E2E00 data
    "F0 15",       # 00/E334: BEQ $E34B
    "AA",          # 00/E336: TAX
    "E2 20",       # 00/E337: SEP #$20
    "BF 02 00 7E", # 00/E339: LDA $7E0002,X
    "8D A7 1D",    # 00/E33D: STA $1DA7     ; $1DA7 = Decker's current HP
    "C2 20",       # 00/E340: REP #$20
    "8E AF 1D",    # 00/E342: STX $1DAF     ; $1DAF = Pointer to decker's 7E2E00 data
    "60",          # 00/E345: RTS
    "60",          # 00/E346: RTS
    "60",          # 00/E347: RTS
    "60",          # 00/E348: RTS
    "60",          # 00/E349: RTS
    "60",          # 00/E34A: RTS
    "60",          # 00/E34B: RTS           ; Vanilla RTS
])))

# ------------------------------------------------------------------------

# Update the glass cases containing weapons and armor so that their
# cost matches the new randomized contents.
# This causes power growth to be more money-driven.
equipmentPrices = {
    # Weapons
    0x1952 :   200, # Beretta Pistol
    0x17C3 :   200, # Colt L36 Pistol
    0x12F3 :  1000, # Fichetti L. Pistol
    0x0157 :  1300, # Viper H. Pistol ($3,000)
    0x0150 :  2000, # Viper H. Pistol ($4,000)
    0x013B :  4000, # Warhawk H. Pistol
    0x0276 :  6000, # T-250 Shotgun ($12,000)
    0x0261 :  7500, # T-250 Shotgun ($15,000)
    0x01A4 : 14000, # Uzi III SMG
    0x0BF3 : 11000, # HK 277 A. Rifle
    0x1B5F : 20000, # AS-7 A. Cannon
    # Armor
    0x0B21 :  1000, # Leather Jacket
    0x085E :  2500, # Mesh Jacket (free)
    0x0850 :  2500, # Mesh Jacket ($5,000)
    0x18A3 :  3000, # Bulletproof Vest
    0x1696 :  6000, # Concealed Jacket
    0x0770 :  9000, # Partial Bodysuit
    0x129F : 15000, # Full Bodysuit
}

# Oldtown - Gun Shop
struct.pack_into("<H", romBytes, 0xE5F3E, equipmentPrices[struct.unpack_from("<H", romBytes, 0xE5F3B)[0]]) # Colt L36 Pistol
struct.pack_into("<H", romBytes, 0xE5F50, equipmentPrices[struct.unpack_from("<H", romBytes, 0xE5F4D)[0]]) # Viper H. Pistol ($4,000)
struct.pack_into("<H", romBytes, 0xE5F62, equipmentPrices[struct.unpack_from("<H", romBytes, 0xE5F5F)[0]]) # Mesh Jacket ($5,000)
struct.pack_into("<H", romBytes, 0xE5F74, equipmentPrices[struct.unpack_from("<H", romBytes, 0xE5F71)[0]]) # T-250 Shotgun ($15,000)
struct.pack_into("<H", romBytes, 0xE5F86, equipmentPrices[struct.unpack_from("<H", romBytes, 0xE5F83)[0]]) # Fichetti L. Pistol
struct.pack_into("<H", romBytes, 0xE5F98, equipmentPrices[struct.unpack_from("<H", romBytes, 0xE5F95)[0]]) # Warhawk H. Pistol

# Dark Blade - Gun Shop
struct.pack_into("<H", romBytes, 0xFCE79, equipmentPrices[struct.unpack_from("<H", romBytes, 0xFCE76)[0]]) # Viper H. Pistol ($3,000)
struct.pack_into("<H", romBytes, 0xFCE8B, equipmentPrices[struct.unpack_from("<H", romBytes, 0xFCE88)[0]]) # T-250 Shotgun ($12,000)
struct.pack_into("<H", romBytes, 0xFCE9D, equipmentPrices[struct.unpack_from("<H", romBytes, 0xFCE9A)[0]]) # Uzi III SMG
struct.pack_into("<H", romBytes, 0xFCEAF, equipmentPrices[struct.unpack_from("<H", romBytes, 0xFCEAC)[0]]) # HK 277 A. Rifle
struct.pack_into("<H", romBytes, 0xFCED3, equipmentPrices[struct.unpack_from("<H", romBytes, 0xFCED0)[0]]) # Bulletproof Vest
struct.pack_into("<H", romBytes, 0xFCEE5, equipmentPrices[struct.unpack_from("<H", romBytes, 0xFCEE2)[0]]) # Concealed Jacket
struct.pack_into("<H", romBytes, 0xFCEF7, equipmentPrices[struct.unpack_from("<H", romBytes, 0xFCEF4)[0]]) # Partial Bodysuit
struct.pack_into("<H", romBytes, 0xFCF09, equipmentPrices[struct.unpack_from("<H", romBytes, 0xFCF06)[0]]) # Full Bodysuit
struct.pack_into("<H", romBytes, 0xFCF1B, equipmentPrices[struct.unpack_from("<H", romBytes, 0xFCF18)[0]]) # AS-7 A. Cannon

## Make all of the "initially out of stock" items available
## This specifically undoes something we went out of our way to do
## just after the "common code for glass cases" script.
## If we decide to keep this behaviour, we can comment out those
## lines as well as these ones.
#initialItemState[0x9F7] &= ~0x02 # HK 277 A. Rifle  ($24,000)
#initialItemState[0xA01] &= ~0x02 # Concealed Jacket ($13,000)
#initialItemState[0xA06] &= ~0x02 # Partial Bodysuit ($20,000)
#initialItemState[0xA3D] &= ~0x02 # Full Bodysuit    ($30,000)
#initialItemState[0xA42] &= ~0x02 # AS-7 A. Cannon   ($40,000)

# ------------------------------------------------------------------------

# Give Jake the Zip Gun as a default weapon
# The Zip Gun is never actually in Jake's inventory, so he can't give
# it away. It works like default equipment for shadowrunners.
romBytes[0x172F] = 0x00 # 0x0000 = object-id for Zip Gun
romBytes[0x1730] = 0x00
romBytes[0x1731] = 0x06 # weapon type: light
romBytes[0x1732] = 0x03 # attack power: 3
romBytes[0x1733] = 0x00 # accuracy: 0
# TODO: Fix the other values in the 0x172C table? The shadowrunners
#   get stats loaded that don't match their equipment, but that
#   might be intentional for game balance purposes. Hmm...

# When re-equipping default weapons, copy the weapon stats correctly
# (A bug in vanilla - two "STA" instructions that should be "LDA")
romBytes[0x1CDA] = 0xBD
romBytes[0x1CE3] = 0xBD

# ------------------------------------------------------------------------

## Start with 1 defense (Leather Jacket equivalent) instead of 0
#romBytes[0x172E] = 0x01 # defense power: 1

## Start with extremely high attack and defense power
#romBytes[0x172E] = 0x14 # defense power: 20 <-- vanilla best: 6, or 8 w/ Dermal Plating
#romBytes[0x172F] = 0x00 # 0x0000 = object-id for Zip Gun
#romBytes[0x1730] = 0x00
#romBytes[0x1731] = 0x01 # weapon type: auto
#romBytes[0x1732] = 0x1E # attack power: 30 <-- vanilla best: 20
#romBytes[0x1733] = 0x09 # accuracy: 9      <-- vanilla best: 6

## Start with 20 Body and 200 HP
#romBytes[0x18A3] = 0x14 # body: 20
#romBytes[0x18B3] = 0xC8 # max HP: 200
#initialItemState[0x5DE] = 0xC8 # starting HP: 200

## Start with a 6 in both Firearms and Computer
#romBytes[0x18F3] = 0x06

# ------------------------------------------------------------------------

## Make the Dermal Plating immediately available at Maplethorpe's
#initialItemState[0x55B] |= 0x01

## Open the door to the Rust Stilettos HQ
#initialItemState[0x59C] |= 0x80

## Set the Jagged Nails entry fee to 0 nuyen (doesn't change text)
#romBytes[0x179DF] = 0x00

## Open the gate to the Rat Shaman Lair
## (Side effect: prevents Dog Spirit conversation where you learn "Rat")
#initialItemState[0x4CA] |= 0x01

## Open the gate to the Dark Blade mansion
## (Side effect: prevents "DBlade" phone conversation)
#initialItemState[0x565] |= 0x01

## Make the Massive Orc appear on the Taxiboat Dock
## In vanilla, this happens if you know either "Nirwanda" or "Laughlyn"
## In vanilla, this enemy drops the Explosives upon death
#romBytes[0xFA9F5] = 0xBC
#romBytes[0xFA9F6] = 0xC0
#romBytes[0xFA9F7] = 0xBC

## Open up Bremerton (talk to the taxiboat driver once, no fee)
#romBytes[0xF898F] = 0xBC
#romBytes[0xF8990] = 0xC0
#romBytes[0xF8991] = 0xBC
#initialItemState[0x3E9] |= 0x80

## Start with the Crowbar
#initialItemState[0x814] = 0xB2 # 0x08B2 = Object-id for Jake
#initialItemState[0x815] = 0x08

## Open the door leading to Bremerton's interior
#initialItemState[0x32B] |= 0x01

## Warp to Safe I's room when exiting the morgue's main room
#romBytes[0xC84F4] = 0x4C # 0x014C = Door-id to enter Safe I's room
#romBytes[0xC84F5] = 0x01

## Start with the Safe Key
#initialItemState[0xC47] = 0xB2 # 0x08B2 = Object-id for Jake
#initialItemState[0xC48] = 0x08

## Warp to Safe II's room when exiting the morgue's main room
#romBytes[0xC84F4] = 0x56 # 0x0156 = Door-id to enter Safe II's room
#romBytes[0xC84F5] = 0x01

## Start with the Time Bomb
#initialItemState[0x66B] = 0xB2 # 0x08B2 = Object-id for Jake
#initialItemState[0x66C] = 0x08

## Start with Safe II's guards defeated
#initialItemState[0xCA6] = 0x38
#initialItemState[0xCA7] = 0x15
#initialItemState[0xCAB] = 0x38
#initialItemState[0xCAC] = 0x15
#initialItemState[0xCB0] = 0x38
#initialItemState[0xCB1] = 0x15
#initialItemState[0xCB5] = 0x38
#initialItemState[0xCB6] = 0x15

## Warp to the Jester Spirit boss room when exiting the morgue's main room
#romBytes[0xC84F4] = 0x4B # 0x004B = Door-id to enter Jester Spirit boss room
#romBytes[0xC84F5] = 0x00

## Start with the Cyberdeck
#initialItemState[0x229] = 0xB2 # 0x08B2 = Object-id for Jake
#initialItemState[0x22A] = 0x08

## In the Computer helper script, skip the "Jake + datajack damaged" check
#romBytes[0xFD644] = 0x48
#romBytes[0xFD645] = 0x54
#romBytes[0xFD646] = 0x00

## Start with the Drake Password
## The computer on the first floor of the Drake Towers requires you to
## have the Drake Password in your inventory in order to proceed.
## Examining the Drake Password has no effect.
#initialItemState[0x81E] = 0xB2 # 0x08B2 = Object-id for Jake
#initialItemState[0x81F] = 0x08

## Warp to the Gold Naga boss room when exiting the morgue's main room
## (For testing the item drop in the Serpent Scales location)
#romBytes[0xC84F4] = 0x9F # 0x009F = Door-id to enter Gold Naga boss room from lower left
#romBytes[0xC84F5] = 0x00

## Warp to Professor Pushkin's room when exiting the morgue's main room
#romBytes[0xC84F4] = 0xA2 # 0x00A2 = Door-id to enter Professor Pushkin's room
#romBytes[0xC84F5] = 0x00

## Start with the Aneki Password
## The computer on the first floor of the Aneki Building requires you to
## have the Aneki Password in your inventory in order to proceed.
#initialItemState[0x666] = 0xB2 # 0x08B2 = Object-id for Jake
#initialItemState[0x667] = 0x08

## Warp to the AI Computer room when exiting the morgue's main room
#romBytes[0xC84F4] = 0x76 # 0x0176 = Door-id to enter AI Computer room
#romBytes[0xC84F5] = 0x01

# ------------------------------------------------------------------------
# TODO:
# This is the end of the QUICK UGLY CHANGE SECTION
# ------------------------------------------------------------------------





# Recompressing the modified "initial item state" data would probably
# produce a result larger than the original compressed data. So instead,
# let's write the uncompressed modified data to 0x108000, and update the
# ROM to use that instead.
writeHelper(romBytes, 0x186C, bytes.fromhex(' '.join([
    "A2 3E 00",    # 00/986C: LDX #$003E
    "A9 00 00",    # 00/986F: LDA #$0000
    "9F BB 3B 7E", # 00/9872: STA $7E3BBB,X
    "CA",          # 00/9876: DEX
    "CA",          # 00/9877: DEX
    "10 F8",       # 00/9878: BPL $987E
    "8B",          # 00/987A: PHB
    "A2 00 80",    # 00/987B: LDX #$8000
    "A0 00 2E",    # 00/987E: LDY #$2E00
    "A9 BA 0D",    # 00/9881: LDA #$0DBA
    "54 7E A1",    # 00/9884: MVN $A1,$7E   ; Copy from 0x108000 to $7E2E00
])))
writeHelper(romBytes, 0x108000, initialItemState)



# Add the randomizer version, seed and flags to the title screen
# Update the main menu
writeHelper(romBytes, 0xE34E, bytes.fromhex(' '.join([
    "22 00 90 A1", # 01/E34E: JSL $A19000   ; New printing subroutine
    "4B",          # 01/E352: PHK
    "AB",          # 01/E353: PLB
])))
# Move the menu options down one row
struct.pack_into("<H", romBytes, 0xE355, 0x0454) # "START NEW GAME"
struct.pack_into("<H", romBytes, 0xE35F, 0x04D4) # "START SAVED GAME"
struct.pack_into("<H", romBytes, 0xE369, 0x0554) # "OPTIONS"

# Update the "START SAVED GAME" menu
writeHelper(romBytes, 0xE39B, bytes.fromhex(' '.join([
    "22 00 90 A1", # 01/E39B: JSL $A19000   ; New printing subroutine
    "4B",          # 01/E39F: PHK
    "AB",          # 01/E3A0: PLB
])))
# Move the menu options down one row
struct.pack_into("<H", romBytes, 0xE3C1, 0x0454) # "RESUME GAME 1"
struct.pack_into("<H", romBytes, 0xE3D0, 0x04D4) # "RESUME GAME 2"
struct.pack_into("<H", romBytes, 0xE3DC, 0x0554) # "EXIT"

# Update the "OPTIONS" menu
writeHelper(romBytes, 0xE407, bytes.fromhex(' '.join([
    "22 00 90 A1", # 01/E407: JSL $A19000   ; New printing subroutine
    "4B",          # 01/E40B: PHK
    "AB",          # 01/E40C: PLB
])))
# Move the menu options down one row
struct.pack_into("<H", romBytes, 0xE424, 0x0454) # "CONTROL TYPE (B|A)"
struct.pack_into("<H", romBytes, 0xE40E, 0x04D4) # "(STEREO|MONO)PHONIC"
struct.pack_into("<H", romBytes, 0xE43A, 0x0554) # "B.G. MUSIC (FULL|EVENT|OFF)"
struct.pack_into("<H", romBytes, 0xE458, 0x05D4) # "EXIT"

# Move the menu cursor down one row
struct.pack_into("<H", romBytes, 0xE2F7, 0x0450)

# Construct the new info lines
newInfoLines = (
    f" {'Randomizer':>13.13}    {str(seed):<13.13} "
    f" {randomizerVersion:>13.13}    {(randomizerFlags if randomizerFlags else '-'):<13.13} "
).encode("ascii") + b"\x00"

# New printing subroutine
writeHelper(romBytes, 0x109000, bytes.fromhex(' '.join([
    "22 12 D5 81", # A0/9000: JSL $81D512   ; Print the copyright line
    "4B",          # A0/9004: PHK
    "AB",          # A0/9005: PLB
    "A2 00 03",    # A0/9006: LDX #$0300    ; Destination on title screen
    "A0 20 90",    # A0/9009: LDY #$9020    ; Source address for text
    "22 EE D4 81", # A0/900C: JSL $81D4EE   ; Print the new info lines
    "6B",          # A0/9010: RTL
])))
writeHelper(romBytes, 0x109020, newInfoLines)



# Copy the map data from 0xC8000-D7FFF to 0x110000-11FFFF.
romBytes[0x110000:0x1145D8] = romBytes[0xC8000:0xCC5D8]
romBytes[0x118000:0x11AD64] = romBytes[0xD0000:0xD2D64]

# Look for the map data at 0x110000.
romBytes[0x23DE] = 0xA2

# Make a new version of the Rat Shaman boss room at 0x114600.
# This version has two randomized objects:
# - Item shuffled to the new "Keyword: Jester Spirit" location
# - Item shuffled to the new "Nuyen: Rat Shaman" location
romBytes[0x114600]          = romBytes[0xD0636]            # Vanilla drawing data
romBytes[0x114601]          = romBytes[0xD0637]            # Vanilla music
romBytes[0x114602:0x114604] = struct.pack("<H", 0xC6AE)    # Vanilla camera pointer, adjusted for the new room data location
romBytes[0x114604]          = romBytes[0xD063A] + 2        # +2 to the number of objects
romBytes[0x114605:0x114629] = romBytes[0xD063B:0xD065F]    # Vanilla objects
romBytes[0x114629:0x11462D] = bytes.fromhex("88 01 C8 19") # Randomized object's coordinates (near the Rat Shaman)
romBytes[0x11462D:0x11462F] = romBytes[0xD29A7:0xD29A9]    # Randomized object's object-id
romBytes[0x11462F:0x114633] = bytes.fromhex("70 01 E0 19") # Randomized object's coordinates (near the Rat Shaman)
romBytes[0x114633:0x114635] = romBytes[0xD2965:0xD2967]    # Randomized object's object-id
romBytes[0x114635:0x11465C] = romBytes[0xD065F:0xD0686]    # Vanilla remainder of room data, part 1
romBytes[0x11465C:0x11465E] = bytes.fromhex("60 02")       # Enlarge the entrance's warp zone to make it easier to traverse
romBytes[0x11465E:0x1146B0] = romBytes[0xD0688:0xD06DA]    # Vanilla remainder of room data, part 2
# Update the door destinations to lead to the new Rat Shaman boss room
struct.pack_into("<H", romBytes, 0x692AF + (9 * 0x12C), 0x4600)

# Make a new version of the Vampire boss room at 0x114700.
# This version has two randomized objects:
# - Item shuffled to the new "Keyword: Laughlyn" location
# - Item shuffled to the new "Nuyen: Vampire" location
romBytes[0x114700]          = romBytes[0xD0F4A]            # Vanilla drawing data
romBytes[0x114701]          = romBytes[0xD0F4B]            # Vanilla music
romBytes[0x114702:0x114704] = struct.pack("<H", 0xC796)    # Vanilla camera pointer, adjusted for the new room data location
romBytes[0x114704]          = romBytes[0xD0F4E] + 2        # +2 to the number of objects
romBytes[0x114705:0x114723] = romBytes[0xD0F4F:0xD0F6D]    # Vanilla objects
romBytes[0x114723:0x114727] = bytes.fromhex("C8 01 80 11") # Randomized object's coordinates (near the entrance stairs)
romBytes[0x114727:0x114729] = romBytes[0xD29CB:0xD29CD]    # Randomized object's object-id
romBytes[0x114729:0x11472D] = bytes.fromhex("C8 01 A0 11") # Randomized object's coordinates (near the entrance stairs)
romBytes[0x11472D:0x11472F] = romBytes[0xD29AD:0xD29AF]    # Randomized object's object-id
romBytes[0x11472F:0x1147A0] = romBytes[0xD0F6D:0xD0FDE]    # Vanilla remainder of room data
# Update the door destinations to lead to the new Vampire boss room
struct.pack_into("<H", romBytes, 0x692AF + (9 * 0x13D), 0x4700)

# Make a new version of the Jester Spirit boss room at 0x114800.
# This version has two randomized objects:
# - Item shuffled to the new "Keyword: Volcano" location
# - Item shuffled to the existing "Jester Spirit Insignia" location
romBytes[0x114800]          = romBytes[0xCAE08]            # Vanilla drawing data
romBytes[0x114801]          = romBytes[0xCAE09]            # Vanilla music
romBytes[0x114802:0x114804] = struct.pack("<H", 0xC946)    # Vanilla camera pointer, adjusted for the new room data location
romBytes[0x114804]          = romBytes[0xCAE0C] + 1        # +1 to the number of objects
romBytes[0x114805:0x114817] = romBytes[0xCAE0D:0xCAE1F]    # Vanilla objects
romBytes[0x114817:0x11481B] = bytes.fromhex("B0 01 3D 12") # Randomized object's coordinates (near the exit portal)
romBytes[0x11481B:0x11481D] = romBytes[0xD299B:0xD299D]    # Randomized object's object-id
romBytes[0x11481D:0x114823] = romBytes[0xCAE25:0xCAE2B]    # Vanilla object
romBytes[0x114823:0x114827] = bytes.fromhex("90 01 3D 12") # Randomized object's coordinates (near the exit portal)
romBytes[0x114827:0x114829] = romBytes[0xCAE23:0xCAE25]    # Randomized object's object-id
romBytes[0x114829:0x114948] = romBytes[0xCAE2B:0xCAF4A]    # Vanilla remainder of room data
# Update the door destinations to lead to the new Jester Spirit boss room
struct.pack_into("<H", romBytes, 0x692AF + (9 * 0x4B), 0x4800)



if not args.dry_run:
    with open(outFileName, "xb") as outFile:
        outFile.write(romBytes)
