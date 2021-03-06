#!/usr/bin/env python3
#
# Shadowrun Randomizer
# Osteoclave
# 2021-05-03

import argparse
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
randomizerVersion = "2022-07-18"

# Process the command line arguments.
parser = argparse.ArgumentParser(
    description = textwrap.dedent(f"""\
        Shadowrun Randomizer
        (version: {randomizerVersion})"""
    ),
    formatter_class = argparse.RawTextHelpFormatter,
)
parser.add_argument(
    "-s", "--seed",
    type = int,
    help = "specify the RNG seed value",
)
parser.add_argument(
    "-v", "--verbose",
    action = "count",
    help = "print spoiler log",
)
parser.add_argument(
    "-n", "--dry-run",
    action = "store_true",
    help = "execute without saving any changes",
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



# Seed the random number generator.
rng = random.Random()
seed = args.seed
if seed is None:
    seed = random.SystemRandom().getrandbits(32)
seed %= 2**32
rng.seed(seed)
print(f"RNG seed: {seed}")

# If we're not in dry-run mode, read the input and initial-item-state
# files. We don't need either of these right away, but if something is
# wrong (e.g. file not found), we want to fail quickly.
if not args.dry_run:
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
    with open("initial_item_state.hex", "rb") as iisFile:
        initialItemState = bytearray(iisFile.read())



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
        "ITEM___JESTER_SPIRIT",
        "ITEM___KEYWORD___DOG",
        "ITEM___KEYWORD___JESTER_SPIRIT",
        "ITEM___LEAVES",
        "ITEM___LONESTAR_BADGE",
        "ITEM___MAGIC_FETISH",
        "ITEM___MATCHBOX",
        "ITEM___MEMO",
        "ITEM___MERMAID_SCALES",
        "ITEM___NUYEN___OCTOPUS",
        "ITEM___NUYEN___RAT_SHAMAN",
        "ITEM___PAPERWEIGHT",
        "ITEM___PASSWORD___ANEKI",
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
        "EVENT___GLUTMAN_HIDES_YOU",
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
        "EVENT___NIRWANDA_OR_LAUGHLYN",
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
        "EVENT___GAME_COMPLETED",
    ],
)

class Category(Flag):
    CONSTANT = auto()
    PHYSICAL = auto()
    KEY_ITEM = auto()
    WEAPON = auto()
    ARMOR = auto()
    ITEM = auto()
    NPC = auto()
    PHYSICAL_KEY_ITEM = PHYSICAL | KEY_ITEM
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
        description = "Nirwanda or Laughlyn",
        vanilla = Entity(Category.CONSTANT, "Nirwanda or Laughlyn", None, [
            # Treat every "knows either Nirwanda or Laughlyn" requirement as
            # "knows Laughlyn" in order to avoid softlocks.
            (Progress.EVENT___NIRWANDA_OR_LAUGHLYN, [Progress.KEYWORD___LAUGHLYN]),
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
        category = Category.PHYSICAL_KEY_ITEM,
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
        category = Category.CONSTANT,
        description = "Mortician",
        vanilla = Entity(Category.CONSTANT, "Mortician", 0x6B81F, []),
        requires = [],
        address = 0xC8471,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Mortician",
        vanilla = Entity(Category.CONSTANT, "Mortician", 0x6B82D, [
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
        category = Category.PHYSICAL_KEY_ITEM,
        description = "Tickets",
        vanilla = Entity(Category.KEY_ITEM, "Tickets", 0x6B268, [
            (Progress.ITEM___TICKETS, []),
        ]),
        requires = [Progress.EVENT___MORGUE_CABINETS_UNLOCKED],
        address = 0xC8489,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_KEY_ITEM,
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
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Decker",
        vanilla = Entity(Category.CONSTANT, "Decker", 0x6C618, [
            (Progress.KEYWORD___HITMEN, []),
        ]),
        requires = [],
        address = 0xC816F,
        hidden = False,
    ),
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
    # In vanilla, "Progress.EVENT___GLUTMAN_HIDES_YOU" is required
    # to enter the Tenth Street monorail station.
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
        category = Category.PHYSICAL_KEY_ITEM,
        description = "Shades",
        vanilla = Entity(Category.KEY_ITEM, "Shades", 0x6B3F7, [
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
        vanilla = Entity(Category.KEY_ITEM, "Ripped Note", 0x6B674, [
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
        category = Category.WEAPON,
        description = "Beretta Pistol",
        vanilla = Entity(Category.WEAPON, "Beretta Pistol", 0x6C983, [
            (Progress.WEAPON___BERETTA_PISTOL, []),
        ]),
        requires = [],
        address = 0xC8871,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.ARMOR,
        description = "Leather Jacket",
        vanilla = Entity(Category.ARMOR, "Leather Jacket", 0x6BB52, [
            (Progress.ARMOR___LEATHER_JACKET, []),
        ]),
        requires = [],
        address = 0xC8877,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_KEY_ITEM,
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
        vanilla = Entity(Category.ITEM, "Paperweight", 0x6B7A8, [
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
        vanilla = Entity(Category.KEY_ITEM, "Iced Tea", 0x6BC08, [
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
    # TODO: This is Hamfist
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Orc",
        vanilla = Entity(Category.CONSTANT, "Orc", 0x6B7D2, []),
        requires = [],
        address = 0xC87CB,
        hidden = False,
    ),
    # TODO: This is Jangadance
    # He gets off the phone after you ask that one guy in The Cage
    # about Ghouls. Not sure if that's the only trigger or not.
    # If I'm going to randomize his location, I'll have to remove
    # all of that stuff, as well as change his coordinates to the
    # waypoint he gets placed at when not on the phone.
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Jamaican",
        vanilla = Entity(Category.CONSTANT, "Jamaican", 0x6BBD0, []),
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
    # TODO:
    # Might want to update the behaviour scripts so you don't have to
    # heal Chrome Coyote to get the item in the Ghoul Bone location.
    # Make that "definitely" if Chrome Coyote's location becomes
    # eligible for randomization.
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_ITEM,
        description = "Ghoul Bone",
        vanilla = Entity(Category.ITEM, "Ghoul Bone", 0x6C172, [
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
            (Progress.KEYWORD___SHAMAN,             [Progress.EVENT___CHROME_COYOTE_HEALED]),
            (Progress.KEYWORD___MAGIC_FETISH,       [Progress.EVENT___CHROME_COYOTE_HEALED]),
            (Progress.ITEM___MAGIC_FETISH,          [Progress.EVENT___CHROME_COYOTE_HEALED]),
        ]),
        requires = [],
        address = 0xC8933,
        hidden = False,
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
        category = Category.CONSTANT,
        description = "Lonely Gal",
        vanilla = Entity(Category.CONSTANT, "Lonely Gal", 0x6BB3D, []),
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
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Shady character...",
        vanilla = Entity(Category.CONSTANT, "Shady character...", 0x6B3F0, [
            (Progress.EVENT___GLUTMAN_HIDES_YOU, []),
        ]),
        requires = [Progress.EVENT___GLUTMAN_AT_THE_CAGE],
        address = 0xC86D9,
        hidden = False,
    ),
])
thisRegion.doors.extend([
    Door("Tenth Street - The Cage // Lobby", []),
    Door("Caryards - North", [Progress.EVENT___GLUTMAN_HIDES_YOU]),
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
    # TODO: This is Dances with Clams
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Magic user",
        vanilla = Entity(Category.CONSTANT, "Magic user", 0x6B9C3, []),
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
    # TODO: This is Orifice
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Large orc",
        vanilla = Entity(Category.CONSTANT, "Large orc", 0x6BB67, []),
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
        category = Category.ITEM,
        description = "Potion Bottles",
        vanilla = Entity(Category.ITEM, "Potion Bottles", 0x6B689, [
            (Progress.ITEM___POTION_BOTTLES, []),
        ]),
        requires = [],
        address = 0xC96F5,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.ITEM,
        description = "Black Bottle",
        vanilla = Entity(Category.ITEM, "Black Bottle", 0x6C975, [
            (Progress.ITEM___BLACK_BOTTLE, []),
        ]),
        requires = [],
        address = 0xC96FB,
        hidden = False,
    ),
    Location(
        region = thisRegion,
        category = Category.ITEM,
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
        vanilla = Entity(Category.WEAPON, "Colt L36 Pistol", 0x6C7F4, [
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
        vanilla = Entity(Category.WEAPON, "Viper H. Pistol ($4,000)", 0x6B181, [
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
        vanilla = Entity(Category.ARMOR, "Mesh Jacket ($5,000)", 0x6B881, [
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
        vanilla = Entity(Category.WEAPON, "Fichetti L. Pistol", 0x6C324, [
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
        vanilla = Entity(Category.WEAPON, "Warhawk H. Pistol", 0x6B16C, [
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
    # TODO: This is Akimi
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Akimi",
        vanilla = Entity(Category.CONSTANT, "Akimi", 0x6CBA5, []),
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
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Doggie",
        vanilla = Entity(Category.CONSTANT, "Doggie", 0x6C554, []),
        requires = [],
        address = 0xCA7D1,
        hidden = False,
    ),
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
    # TODO: This is Norbert
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Dwarf",
        vanilla = Entity(Category.CONSTANT, "Dwarf", 0x6C497, []),
        requires = [],
        address = 0xCBB4F,
        hidden = False,
    ),
    # TODO: This is Jetboy
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Decker",
        vanilla = Entity(Category.CONSTANT, "Decker", 0x6C5FC, [
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
    # TODO: This is Anders
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Mercenary",
        vanilla = Entity(Category.CONSTANT, "Mercenary", 0x6B8D5, [
            (Progress.KEYWORD___AKIMI,       [Progress.KEYWORD___SHADOWRUNNERS]),
            (Progress.KEYWORD___STEELFLIGHT, [Progress.KEYWORD___SHADOWRUNNERS]),
        ]),
        requires = [],
        address = 0xCBB5B,
        hidden = False,
    ),
    # TODO: This is Frogtongue
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Orc",
        vanilla = Entity(Category.CONSTANT, "Orc", 0x6B7AF, []),
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
                Progress.EVENT___NIRWANDA_OR_LAUGHLYN,
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
            (Progress.KEYWORD___DRAKE,                 []),
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
    # TODO: This is Kitsune
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Kitsune",
        vanilla = Entity(Category.CONSTANT, "Kitsune", 0x6BB7C, [
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
    # TODO: This is Steelflight
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Decker",
        vanilla = Entity(Category.CONSTANT, "Decker", 0x6C611, [
            (Progress.KEYWORD___ANDERS, [Progress.KEYWORD___SHADOWRUNNERS]),
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
    # TODO: This is Spatter
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Mage",
        vanilla = Entity(Category.CONSTANT, "Mage", 0x6BA41, []),
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
        vanilla = Entity(Category.PHYSICAL_KEY_ITEM, "Explosives", 0x6C3D3, [
            (Progress.ITEM___EXPLOSIVES, []),
        ]),
        # In vanilla, this requires knowing either "Nirwanda" or "Laughlyn".
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
        vanilla = Entity(Category.ITEM, "Mermaid Scales", 0x6B8C7, [
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
        category = Category.PHYSICAL_ITEM,
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
        category = Category.PHYSICAL_ITEM,
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
        vanilla = Entity(Category.WEAPON, "Viper H. Pistol ($3,000)", 0x6B188, [
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
        vanilla = Entity(Category.ARMOR, "Bulletproof Vest", 0x6C8D4, [
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
        vanilla = Entity(Category.ARMOR, "Mesh Jacket (free)", 0x6B88F, [
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
            (Progress.KEYWORD___LAUGHLYN, [
                Progress.ITEM___STROBE,
                Progress.ITEM___STAKE,
                Progress.KEYWORD___JESTER_SPIRIT,
            ]),
            (Progress.KEYWORD___BREMERTON, [
                Progress.ITEM___STROBE,
                Progress.ITEM___STAKE,
                Progress.KEYWORD___JESTER_SPIRIT,
            ]),
        ]),
        requires = [],
        address = 0xD0F53,
        hidden = False,
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
        vanilla = Entity(Category.ITEM, "Dog Tag", 0x6C55B, [
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
        category = Category.PHYSICAL_ITEM,
        description = "Safe Key",
        vanilla = Entity(Category.KEY_ITEM, "Safe Key", 0x6B65F, [
            (Progress.ITEM___SAFE_KEY, []),
        ]),
        requires = [],
        address = 0xD2315,
        hidden = True,
    ),
    Location(
        region = thisRegion,
        category = Category.PHYSICAL_KEY_ITEM,
        description = "Detonator",
        vanilla = Entity(Category.PHYSICAL_KEY_ITEM, "Detonator", 0x6C5EE, [
            (Progress.ITEM___DETONATOR, []),
        ]),
        requires = [Progress.ITEM___SAFE_KEY],
        address = 0xD230F,
        hidden = False,
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
        hidden = False,
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
        category = Category.PHYSICAL_KEY_ITEM,
        description = "Green Bottle",
        vanilla = Entity(Category.KEY_ITEM, "Green Bottle", 0x6C092, [
            (Progress.ITEM___GREEN_BOTTLE, []),
        ]),
        requires = [Progress.ITEM___TIME_BOMB],
        address = 0xD24E9,
        hidden = False,
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
        description = "Jester Spirit",
        vanilla = Entity(Category.CONSTANT, "Jester Spirit", 0x6BBB4, [
            (Progress.KEYWORD___DRAKE,                   []),
            (Progress.EVENT___JESTER_SPIRIT_DEFEATED,    [Progress.KEYWORD___LAUGHLYN]),
            (Progress.KEYWORD___VOLCANO,                 [
                Progress.EVENT___JESTER_SPIRIT_DEFEATED,
                Progress.KEYWORD___DRAKE,
            ]),
            (Progress.ITEM___JESTER_SPIRIT,              [Progress.KEYWORD___VOLCANO]),
            (Progress.EVENT___JESTER_SPIRIT_PORTAL_OPEN, [Progress.ITEM___JESTER_SPIRIT]),
            (Progress.EVENT___JESTER_SPIRIT_PORTAL_USED, [Progress.EVENT___JESTER_SPIRIT_PORTAL_OPEN]),
        ]),
        requires = [],
        address = 0xCAE11,
        hidden = False,
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
        vanilla = Entity(Category.CONSTANT, "Helicopter Pilot", 0x6BCEF, []),
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
        vanilla = Entity(Category.ITEM, "Serpent Scales", 0x6B3FE, [
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
            (Progress.EVENT___DRAKE_DEFEATED, [Progress.ITEM___JESTER_SPIRIT]),
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
    # TODO: This is Professor Pushkin
    Location(
        region = thisRegion,
        category = Category.CONSTANT,
        description = "Scientist",
        vanilla = Entity(Category.CONSTANT, "Scientist", 0x6B4E5, [
            # In vanilla, Professor Pushkin doesn't teach the
            # "Head Computer" keyword. We do it here to avoid
            # a possible softlock.
            (Progress.KEYWORD___HEAD_COMPUTER,           []),
            (Progress.ITEM___PASSWORD___ANEKI,           [Progress.KEYWORD___HEAD_COMPUTER]),
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
            (Progress.EVENT___ANEKI_BUILDING_2F_UNLOCKED, [
                Progress.ITEM___CYBERDECK,
                Progress.EVENT___DATAJACK_REPAIRED,
                Progress.ITEM___PASSWORD___ANEKI,
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
            (Progress.EVENT___GAME_COMPLETED, [
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
        print(f"Generated winnable seed on attempt #{attemptNumber}")
        print()
        break

    attemptNumber += 1

# If we're in verbose mode, print the spoiler log.
if args.verbose:
    for i, sphere in enumerate(spheres):
        print(f"Sphere {i}")
        for location, prize in sphere:
            print(f"{location.region.name:<60}   {location.description:<24} --> {prize.name}")
        print()

# If we're in dry-run mode, there's nothing left to do at this point.
if args.dry_run:
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 21 00", # 0005: If yes, jump to 0021
        "C2",       # 0008: Push $13
        "C2",       # 0009: Push $13
        "58 9C",    # 000A: Write byte to first byte of object's 7E2E00 data <-- Spawn index
        # Wait until object's 0x80 flag is set
        # Based on behaviour script 0x101
        "00 01",    # 000C: Push unsigned byte 0x01
        "BA",       # 000E: Duplicate
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 02",    # 0013: Push object's flags
        "00 80",    # 0015: Push unsigned byte 0x80
        "7E",       # 0017: Bitwise AND
        "BE",       # 0018: Convert to boolean
        "44 0C 00", # 0019: If false, jump to 000C
        # Display sprite
        # Based on behaviour script 0x244
        "C0",       # 001C: Push zero
        "C0",       # 001D: Push zero
        "C2",       # 001E: Push $13
        "58 D1",    # 001F: Display sprite
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 01",    # 001C: Push unsigned byte 0x01     1 = Strength required
        "00 00",    # 001E: Push unsigned byte 0x00     0 = Accuracy
        "00 03",    # 0020: Push unsigned byte 0x03     3 = Attack
        "00 06",    # 0022: Push unsigned byte 0x06     6 = Type (light)
        "C2",       # 0024: Push $13
        "52 11 00", # 0025: Execute behaviour script 0x11 = Common code for weapons
        "56",       # 0028: End
    ],
)
# Zip-Gun: Use the Beretta Pistol's sprite data (0xD420 --> 0xD052)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xB6), 0xD052)
# Zip-Gun: Increase the Zip-Gun's sprite priority
romBytes[0x6B031] = 0xFF

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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 01",    # 001C: Push unsigned byte 0x01     1 = Strength required
        "00 01",    # 001E: Push unsigned byte 0x01     1 = Accuracy
        "00 03",    # 0020: Push unsigned byte 0x03     3 = Attack
        "00 06",    # 0022: Push unsigned byte 0x06     6 = Type (light)
        "C2",       # 0024: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 01",    # 001C: Push unsigned byte 0x01     1 = Strength required
        "00 01",    # 001E: Push unsigned byte 0x01     1 = Accuracy
        "00 03",    # 0020: Push unsigned byte 0x03     3 = Attack
        "00 06",    # 0022: Push unsigned byte 0x06     6 = Type (light)
        "C2",       # 0024: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 01",    # 001C: Push unsigned byte 0x01     1 = Strength required
        "00 01",    # 001E: Push unsigned byte 0x01     1 = Accuracy
        "00 04",    # 0020: Push unsigned byte 0x04     4 = Attack
        "00 06",    # 0022: Push unsigned byte 0x06     6 = Type (light)
        "C2",       # 0024: Push $13
        "52 11 00", # 0025: Execute behaviour script 0x11 = Common code for weapons
        "56",       # 0028: End
    ],
)
# Fichetti L. Pistol: Use the Beretta Pistol's sprite data (0xE018 --> 0xD052)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xCC), 0xD052)
# Fichetti L. Pistol: Increase the Fichetti L. Pistol's sprite priority
romBytes[0x6C324] = 0xFF

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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 02",    # 001C: Push unsigned byte 0x02     2 = Strength required
        "00 02",    # 001E: Push unsigned byte 0x02     2 = Accuracy
        "00 04",    # 0020: Push unsigned byte 0x04     4 = Attack
        "00 00",    # 0022: Push unsigned byte 0x00     0 = Type (heavy)
        "C2",       # 0024: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 03",    # 001C: Push unsigned byte 0x03     3 = Strength required
        "00 02",    # 001E: Push unsigned byte 0x02     2 = Accuracy
        "00 06",    # 0020: Push unsigned byte 0x06     6 = Attack
        "00 00",    # 0022: Push unsigned byte 0x00     0 = Type (heavy)
        "C2",       # 0024: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 04",    # 001C: Push unsigned byte 0x04     4 = Strength required
        "00 02",    # 001E: Push unsigned byte 0x02     2 = Accuracy
        "00 08",    # 0020: Push unsigned byte 0x08     8 = Attack
        "00 00",    # 0022: Push unsigned byte 0x00     0 = Type (heavy)
        "C2",       # 0024: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 04",    # 001C: Push unsigned byte 0x04     4 = Strength required
        "00 03",    # 001E: Push unsigned byte 0x03     3 = Accuracy
        "00 08",    # 0020: Push unsigned byte 0x08     8 = Attack
        "00 01",    # 0022: Push unsigned byte 0x01     1 = Type (auto)
        "C2",       # 0024: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 05",    # 001C: Push unsigned byte 0x05     5 = Strength required
        "00 02",    # 001E: Push unsigned byte 0x02     2 = Accuracy
        "00 0A",    # 0020: Push unsigned byte 0x0A    10 = Attack
        "00 00",    # 0022: Push unsigned byte 0x00     0 = Type (heavy)
        "C2",       # 0024: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 05",    # 001C: Push unsigned byte 0x05     5 = Strength required
        "00 06",    # 001E: Push unsigned byte 0x06     6 = Accuracy
        "00 14",    # 0020: Push unsigned byte 0x14    20 = Attack
        "00 00",    # 0022: Push unsigned byte 0x00     0 = Type (heavy)
        "C2",       # 0024: Push $13
        "52 11 00", # 0025: Execute behaviour script 0x11 = Common code for weapons
        "56",       # 0028: End
    ],
)
# AS-7 A. Cannon: Use the Beretta Pistol's sprite data (0xE040 --> 0xD052)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xCE), 0xD052)
# AS-7 A. Cannon: Increase the AS-7 A. Cannon's sprite priority
romBytes[0x6CB90] = 0xFF

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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 01",    # 001C: Push unsigned byte 0x01     1 = Strength required
        "00 01",    # 001E: Push unsigned byte 0x01     1 = Defense
        "C2",       # 0020: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 02",    # 001C: Push unsigned byte 0x02     2 = Strength required
        "00 02",    # 001E: Push unsigned byte 0x02     2 = Defense
        "C2",       # 0020: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 03",    # 001C: Push unsigned byte 0x03     3 = Strength required
        "00 03",    # 001E: Push unsigned byte 0x03     3 = Defense
        "C2",       # 0020: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 04",    # 001C: Push unsigned byte 0x04     4 = Strength required
        "00 04",    # 001E: Push unsigned byte 0x04     4 = Defense
        "C2",       # 0020: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 05",    # 001C: Push unsigned byte 0x05     5 = Strength required
        "00 05",    # 001E: Push unsigned byte 0x05     5 = Defense
        "C2",       # 0020: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 1C 00", # 0005: If yes, jump to 001C
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "C0",       # 000C: Push zero
        "00 10",    # 000D: Push unsigned byte 0x10
        "58 9E",    # 000F: Register menu options / time delay
        "BC",       # 0011: Pop
        "C2",       # 0012: Push $13
        "58 6F",    # 0013: Set object's owner to Jake
        "52 4B 00", # 0015: Execute behaviour script 0x4B = "Got item" sound effect
        "C2",       # 0018: Push $13
        "58 B8",    # 0019: Despawn object
        "56",       # 001B: End
        "00 06",    # 001C: Push unsigned byte 0x06     6 = Strength required
        "00 06",    # 001E: Push unsigned byte 0x06     6 = Defense
        "C2",       # 0020: Push $13
        "52 20 03", # 0021: Execute behaviour script 0x320 = Common code for armor
        "56",       # 0024: End
    ],
)
# Full Bodysuit: Use the Mesh Jacket's sprite data (0xE0A4 --> 0xE054)
struct.pack_into("<H", romBytes, 0x66D8A + (2 * 0xD3), 0xE054)

# ------------------------------------------------------------------------
# Helper script for selling weapons and armor
# ------------------------------------------------------------------------
# When an item is sold, instead of setting the owner to 0x0BAD
# (vanilla owner-object for all items sold by the player), set
# the owner to 0xFFFF (no owner). This change makes sold items
# reappear at their original locations, so they won't be lost
# forever. It also serves as a source of money, since you can
# collect and sell weapons and armor repeatedly.
writeHelper(romBytes, 0xE7AA6, bytes.fromhex(' '.join([
    "14 FF FF", # 0227: Push short 0xFFFF
])))

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
        "C2",       # 000C: Push $13
        "58 D1",    # 000D: Display sprite
        # TOP_OF_LOOP
        # Check the glass case's 0x01 flag.
        "C2",       # 000F: Push $13
        "58 02",    # 0010: Push object's flags
        "00 01",    # 0012: Push unsigned byte 0x01
        "7E",       # 0014: Bitwise AND
        "BE",       # 0015: Convert to boolean
        "44 2C 00", # 0016: If false, jump to FLAG_01_CLEAR
        # If the glass case's 0x01 flag is set, check if the item inside
        # the case is owned by 0xFFFF (no owner). This is a change from
        # vanilla, which would check if the item was owned by 0x0BAD
        # (vanilla owner-object for all items sold by the player).
        "16 05",    # 0019: Push short from $13+05 <-- Object-id of item inside the case
        "58 CC",    # 001B: Push object's owner
        "14 FF FF", # 001D: Push short 0xFFFF
        "AA",       # 0020: Check if equal
        "44 36 00", # 0021: If not equal, jump to OUT_OF_STOCK
        # If the item inside the case is owned by 0xFFFF (i.e. the player
        # sold that item to someone), clear the glass case's 0x01 flag
        # and jump to the "item in stock" case.
        "0A FE",    # 0024: Push signed byte 0xFE
        "C2",       # 0026: Push $13
        "58 7A",    # 0027: Clear bits of object's flags
        "48 60 00", # 0029: Jump to IN_STOCK
        # FLAG_01_CLEAR
        # The glass case's 0x01 flag is clear.
        # Let's check the glass case's 0x02 flag.
        "C2",       # 002C: Push $13
        "58 02",    # 002D: Push object's flags
        "00 02",    # 002F: Push unsigned byte 0x02
        "7E",       # 0031: Bitwise AND
        "BE",       # 0032: Convert to boolean
        "44 60 00", # 0033: If false, jump to IN_STOCK
        # OUT_OF_STOCK
        "00 80",    # 0036: Push unsigned byte 0x80
        "C2",       # 0038: Push $13
        "58 CE",    # 0039: Set bits of 7E1474+n <-- Makes case contents invisible
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
        "58 26",    # 00DE: Add amount to object's quantity
        "48 E8 00", # 00E0: Jump to CHANGE_OWNERSHIP
        # NOT_STACKABLE
        # Set 0x01 bit of glass case to mark as purchased
        "00 01",    # 00E3: Push unsigned byte 0x01
        "C2",       # 00E5: Push $13
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
# Free object
# Vanilla: Mesh Jacket (Anders)
writeHelper(romBytes, 0x6B8A4, bytes.fromhex("FF 2A 3B 30 00 C6 02"))
# Keyword-item: Volcano
# Vanilla: Mesh Jacket (Looks unused)
writeHelper(romBytes, 0x6B8AB, bytes.fromhex("FF 39 3B 30 00 C6 02"))
# TODO: create a "VAMPIRE_DEFEATED" event once the "Laughlyn" keyword-item is in logic
# Keyword-item: Laughlyn
# Vanilla: Mesh Jacket (Hamfist)
writeHelper(romBytes, 0x6B8B2, bytes.fromhex("FF 52 3B 30 00 C6 02"))
# Keyword-item: Bremerton
# Vanilla: Vladimir
#writeHelper(romBytes, 0x6B17A, bytes.fromhex("FF 43 36 30 00 C6 02"))
# Nuyen-item: Rat Shaman
# Vanilla: Mesh Jacket (Spatter)
writeHelper(romBytes, 0x6B8B9, bytes.fromhex("FF FD 3A 9E 00 D6 00"))
# Keyword-item: Jester Spirit
# Vanilla: Mesh Jacket (Jetboy)
writeHelper(romBytes, 0x6B8C0, bytes.fromhex("FF 34 3B 30 00 C6 02"))
# TODO: Consider turning Glutman into a nuyen-item
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
        "C2",       # 0002: Push $13
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
        "14 88 08", # 0033: Push short 0x0888      <-- Object-id of keyword-item: Bremerton
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
        "14 7A 08", # 005D: Push short 0x087A      <-- Object-id of keyword-item: Volcano
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
        "C2",       # 0074: Push $13
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
        "C2",       # 00AE: Push $13
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

# TODO: Matchbox <-- Not currently subject to randomization

# Torn Paper
writeHelper(romBytes, 0xDEF22, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    "48 15 00", # 000C: Jump to 0015
])))
# Move the spawn point to the floor
romBytes[0xC848C] = 0x01

# Torn Paper: Slab
# Reveal the new item shuffled to this location
romBytes[0x1EF7A:0x1EF7A+2] = romBytes[0xC848F:0xC848F+2]

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
        "C2",       # 000A: Push $13
        "52 44 02", # 000B: Execute behaviour script 0x244 = Display sprite
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
        "58 4F",    # 003A: Push X coordinate / 4
        "14 D0 01", # 003C: Push short 0x01D0
        "9A",       # 003F: Check if greater than
        "44 49 00", # 0040: If no, jump to PICKUP_OK
        # TRIED_PICKUP_THROUGH_WALL
        "52 6C 02", # 0043: Execute behaviour script 0x26C
        "48 0E 00", # 0046: Jump to TOP_OF_LOOP
        # PICKUP_OK
        "00 01",    # 0049: Push unsigned byte 0x01
        "14 95 03", # 004B: Push short 0x0395 <-- Object-id of "Slap Patch" (stackable inventory item)
        "58 26",    # 004E: Add amount to object's quantity
        "14 B2 08", # 0050: Push short 0x08B2 <-- Object-id for Jake
        "14 95 03", # 0053: Push short 0x0395 <-- Object-id of "Slap Patch" (stackable inventory item)
        "58 74",    # 0056: Set object's owner
        "52 4B 00", # 0058: Execute behaviour script 0x4B = "Got item" sound effect
        # DONE
        "C2",       # 005B: Push $13
        "58 B8",    # 005C: Despawn object
        "56",       # 005E: End
    ],
)

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

# Memo
writeHelper(romBytes, 0xDF523, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
])))

# Door Key
writeHelper(romBytes, 0xDF415, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    "48 10 00", # 000C: Jump to 0010
])))
# Use facing direction 05's sprite for direction 00
romBytes[0x6418C] = 0x08

# Door Key: Seems familiar...
# Reveal the new item shuffled to this location
romBytes[0xDD221:0xDD221+2] = romBytes[0xC93F3:0xC93F3+2]

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
romBytes[0x6BB52] = 0xFF

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
    "C2",       # 00D0: Push $13
    "58 51",    # 00D1: Push Z coordinate / 4
    "00 02",    # 00D3: Push unsigned byte 0x02
    "7A",       # 00D5: Left shift
    "C2",       # 00D6: Push $13
    "58 50",    # 00D7: Push Y coordinate / 4
    "00 02",    # 00D9: Push unsigned byte 0x02
    "7A",       # 00DB: Left shift
    "00 02",    # 00DC: Push unsigned byte 0x02
    "5E",       # 00DE: Subtraction
    "C2",       # 00DF: Push $13
    "58 4F",    # 00E0: Push X coordinate / 4
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
    "58 CE",    # 0104: Set bits of 7E1474+n <-- Makes item drop subject to gravity
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
    "C2",       # 0038: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 11 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        "00 08",    # 000C: Push unsigned byte 0x08
        "C2",       # 000E: Push $13
        "58 D0",    # 000F: Change displayed sprite? <-- We do this to fix the "spinning Ghoul Bone" bug
        # TOP_OF_LOOP
        "C2",       # 0011: Push $13
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
        "C2",       # 002B: Push $13
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
        "C2",       # 004A: Push $13
        "58 6F",    # 004B: Set object's owner to Jake
        "52 4B 00", # 004D: Execute behaviour script 0x4B = "Got item" sound effect
        "0A FF",    # 0050: Push signed byte 0xFF
        "2C 01",    # 0052: Pop byte to $13+01 <-- Whether object has an owner
        # BOTTOM_OF_LOOP
        "0C 01",    # 0054: Push signed byte from $13+01 <-- Whether object has an owner
        "44 11 00", # 0056: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 0059: Push $13
        "58 B8",    # 005A: Despawn object
        "56",       # 005D: End
    ],
)
# Use facing direction 03's sprite for direction 00
romBytes[0x6661E] = 0x08
# Increase the Ghoul Bone's sprite priority
romBytes[0x6C172] = 0xFF
# Make the Ghoul Bone not inherently subject to gravity
romBytes[0x674F4] &= ~0x20

# Ghoul Bone: Scary Ghoul
# Reveal the new item shuffled to this location
writeHelper(romBytes, 0x1FEE6, bytes.fromhex(' '.join([
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
    "C2",       # 00FF: Push $13
    "58 51",    # 0100: Push Z coordinate / 4
    "00 02",    # 0102: Push unsigned byte 0x02
    "7A",       # 0104: Left shift
    "C2",       # 0105: Push $13
    "58 50",    # 0106: Push Y coordinate / 4
    "00 02",    # 0108: Push unsigned byte 0x02
    "7A",       # 010A: Left shift
    "C2",       # 010B: Push $13
    "58 4F",    # 010C: Push X coordinate / 4
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
    "58 CE",    # 012D: Set bits of 7E1474+n <-- Makes item drop subject to gravity
    "48 5C 01", # 012F: Jump to 015C
])))

# TODO: Magic Fetish <-- Not currently subject to randomization

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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        # TOP_OF_LOOP
        "C2",       # 000C: Push $13
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
        "C2",       # 0028: Push $13
        "58 4C",    # 0029: Play sound effect
        # BLUE_BOTTLE_STATUS
        "C2",       # 002B: Push $13
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
        "C2",       # 005C: Push $13
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
        "C2",       # 0098: Push $13
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
        "C2",       # 00C5: Push $13
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
        "C2",       # 00F0: Push $13
        "58 33",    # 00F1: Set bits of object's flags
        "52 4B 00", # 00F3: Execute behaviour script 0x4B = "Got item" sound effect
        "48 3B 01", # 00F6: Jump to BOTTOM_OF_LOOP
        # CHECK_IF_TOXIC_WATER
        "16 04",    # 00F9: Push short from $13+04 <-- Object-id that the Potion Bottles are being used on
        "14 22 02", # 00FB: Push short 0x0222 <-- Object-id of "Toxic Water"
        "AA",       # 00FE: Check if equal
        "44 36 01", # 00FF: If not equal, jump to NOT_USING_IT_ON_THAT
        # TOXIC_WATER
        "C2",       # 0102: Push $13
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
        "C2",       # 012D: Push $13
        "58 33",    # 012E: Set bits of object's flags
        "52 4B 00", # 0130: Execute behaviour script 0x4B = "Got item" sound effect
        "48 3B 01", # 0133: Jump to BOTTOM_OF_LOOP
        # NOT_USING_IT_ON_THAT
        "16 04",    # 0136: Push short from $13+04 <-- Object-id that the Potion Bottles are being used on
        "52 85 00", # 0138: Execute behaviour script 0x85 = "I'm not using it on..." helper script
        # BOTTOM_OF_LOOP
        "0C 01",    # 013B: Push signed byte from $13+01 <-- Whether object has an owner
        "44 0C 00", # 013D: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 0140: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        # TOP_OF_LOOP
        "C2",       # 000C: Push $13
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
        "C2",       # 0028: Push $13
        "58 4C",    # 0029: Play sound effect
        # BOTTLE_STATUS
        "C2",       # 002B: Push $13
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
        "C2",       # 0067: Push $13
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
        "C2",       # 00A2: Push $13
        "58 33",    # 00A3: Set bits of object's flags
        "52 4B 00", # 00A5: Execute behaviour script 0x4B = "Got item" sound effect <-- Absent in vanilla!
        "48 B0 00", # 00A8: Jump to BOTTOM_OF_LOOP
        # NOT_USING_IT_ON_THAT
        "16 04",    # 00AB: Push short from $13+04 <-- Object-id that the Black Bottle is being used on
        "52 85 00", # 00AD: Execute behaviour script 0x85 = "I'm not using it on..." helper script
        # BOTTOM_OF_LOOP
        "0C 01",    # 00B0: Push signed byte from $13+01 <-- Whether object has an owner
        "44 0C 00", # 00B2: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 00B5: Push $13
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        # TOP_OF_LOOP
        "C2",       # 000C: Push $13
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
        "C2",       # 0028: Push $13
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
        "C2",       # 0048: Push $13
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
        "52 85 00", # 00CB: Execute behaviour script 0x85 = "I'm not using it on..." helper script
        # BOTTOM_OF_LOOP
        "0C 01",    # 00CE: Push signed byte from $13+01 <-- Whether object has an owner
        "44 0C 00", # 00D0: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 00D3: Push $13
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

# Iron Key
writeHelper(romBytes, 0xF448C, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    "48 12 00", # 000C: Jump to 0012
])))
# Use facing direction 05's sprite for direction 00
romBytes[0x65F10] = 0x08

# Iron Key: Ferocious Orc
# Reveal the new item shuffled to this location
romBytes[0xF9067:0xF9067+2] = romBytes[0xCA7B9:0xCA7B9+2]

# Crowbar
writeHelper(romBytes, 0xF4320, bytes.fromhex(' '.join([
    "52 1D 01", # 0003: Execute behaviour script 0x11D = New item-drawing script
])))
# Increase the Crowbar's sprite priority
romBytes[0x6C6B9] = 0xFF

# Crowbar: Ferocious Orc
# Reveal the new item shuffled to this location
romBytes[0xF95F4:0xF95F4+2] = romBytes[0xD0827:0xD0827+2]

# Password (Drake)
writeHelper(romBytes, 0xF4909, bytes.fromhex(' '.join([
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    "48 12 00", # 000C: Jump to 0012
])))
# Use facing direction 05's sprite for direction 00
romBytes[0x66864] = 0x08
# Increase the Password's sprite priority
romBytes[0x6B79A] = 0xFF

# Password (Drake): Gang Leader
# Reveal the new item shuffled to this location
romBytes[0xF9102:0xF9102+2] = romBytes[0xD08ED:0xD08ED+2]

# TODO: Leaves <-- Not currently subject to randomization

# TODO: Strobe <-- Not currently subject to randomization

# Explosives
writeHelper(romBytes, 0xF4173, bytes.fromhex(' '.join([
    "C2",       # 0008: Push $13
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    "48 25 00", # 000C: Jump to 0025
])))
# Make the Explosives not inherently subject to gravity
romBytes[0x675BA] &= ~0x20

# Explosives: Massive Orc
# Appear after ice has been delivered to the docks. (In vanilla,
# the Massive Orc appears when you know either the Nirwanda or
# Laughlyn keywords, but this creates a risk of softlock if you
# don't collect the Orc's item and then use the Jester Spirit
# portal, which takes away those keywords.)
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
                # 006B: Push short 0x#### <-- Item drop's object-id
])))

# Mermaid Scales
writeHelper(romBytes, 0xF49B1, bytes.fromhex(' '.join([
    "C2",       # 0008: Push $13
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
        "00 80",    # 0000: Push unsigned byte 0x80
        f"14 {romBytes[0xCA691+0]:02X} {romBytes[0xCA691+1]:02X}",
                    # 0002: Push short 0x#### <-- Object-id of new item in "Mermaid Scales" location
        "58 0D",    # 0005: Set bits of object's flags
        "00 02",    # 0007: Push unsigned byte 0x02
        "14 0E 1C", # 0009: Push short 0x1C0E <-- Object-id of ice delivery guy at Wastelands
        "58 0D",    # 000C: Set bits of object's flags
        "56",       # 000D: End
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
romBytes[0xFA9CD:0xFA9CD+2] = romBytes[0xCB18D:0xCB18D+2]

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
        "58 51",    # 0198: Push Z coordinate / 4
        "00 02",    # 019A: Push unsigned byte 0x02
        "7A",       # 019C: Left shift
        "02 0A",    # 019D: Push unsigned byte from $13+0A <-- Corpse's spawn index
        "58 50",    # 019F: Push Y coordinate / 4
        "00 02",    # 01A1: Push unsigned byte 0x02
        "7A",       # 01A3: Left shift
        "02 0A",    # 01A4: Push unsigned byte from $13+0A <-- Corpse's spawn index
        "58 4F",    # 01A6: Push X coordinate / 4
        "00 02",    # 01A8: Push unsigned byte 0x02
        "7A",       # 01AA: Left shift
        "02 0E",    # 01AB: Push unsigned byte from $13+0E <-- Item drop's spawn index
        "58 82",    # 01AD: Set object X/Y/Z position
        "00 80",    # 01AF: Push unsigned byte 0x80
        "02 0E",    # 01B1: Push unsigned byte from $13+0E <-- Item drop's spawn index
        "58 33",    # 01B3: Set bits of object's flags
        # Nuyen: Rat Shaman
        # Reveal the new item shuffled to this location
        f"14 {romBytes[0xD2965+0]:02X} {romBytes[0xD2965+1]:02X}",
                    # 01B5: Push short 0x####   <-- Item drop's object-id
        "58 C2",    # 01B8: Push object's RAM_1 <-- Item drop's spawn index
        "2C 0E",    # 01BA: Pop byte to $13+0E  <-- Item drop's spawn index
        "02 0A",    # 01BC: Push unsigned byte from $13+0A <-- Corpse's spawn index
        "58 51",    # 01BE: Push Z coordinate / 4
        "00 02",    # 01C0: Push unsigned byte 0x02
        "7A",       # 01C2: Left shift
        "02 0A",    # 01C3: Push unsigned byte from $13+0A <-- Corpse's spawn index
        "58 50",    # 01C5: Push Y coordinate / 4
        "00 02",    # 01C7: Push unsigned byte 0x02
        "7A",       # 01C9: Left shift
        "02 0A",    # 01CA: Push unsigned byte from $13+0A <-- Corpse's spawn index
        "58 4F",    # 01CC: Push X coordinate / 4
        "00 02",    # 01CE: Push unsigned byte 0x02
        "7A",       # 01D0: Left shift
        "02 0E",    # 01D1: Push unsigned byte from $13+0E <-- Item drop's spawn index
        "58 82",    # 01D3: Set object X/Y/Z position
        "00 80",    # 01D5: Push unsigned byte 0x80
        "02 0E",    # 01D7: Push unsigned byte from $13+0E <-- Item drop's spawn index
        "58 33",    # 01D9: Set bits of object's flags
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

# Bronze Key
writeHelper(romBytes, 0xF4512, bytes.fromhex(' '.join([
    "48 0E 00", # 0002: Jump to 000E
])))
writeHelper(romBytes, 0xF4524, bytes.fromhex(' '.join([
    "C2",       # 0014: Push $13
    "52 1D 01", # 0015: Execute behaviour script 0x11D = New item-drawing script
    "C0",       # 0018: Push zero
    "BC",       # 0019: Pop
])))
# Use facing direction 05's sprite for direction 00
romBytes[0x65EFC] = 0x08
# Increase the Bronze Key's sprite priority
romBytes[0x6C921] = 0xFF

# Mesh Jacket (free)
# Change the behaviour script for the free Mesh Jacket from 0x388
# (Mesh Jacket in Dark Blade mansion) to 0x1A8 (Mesh Jacket).
# In vanilla, 0x388 was a more complicated script to handle the
# jacket in the mansion, while 0x1A8 just specified armor stats.
# With this change, script 0x388 should now be entirely unused.
struct.pack_into("<H", romBytes, 0x6B894, 0x01A8)
# Increase the free Mesh Jacket's sprite priority
romBytes[0x6B88F] = 0xFF

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
        "C2",       # 001C: Push $13
        "58 24",    # 001D: ???
        "00 1E",    # 001F: Push unsigned byte 0x1E
        "C2",       # 0021: Push $13
        "58 9F",    # 0022: Set object's quantity <-- Samurai Warrior's hit points
        "C0",       # 0024: Push zero
        "00 04",    # 0025: Push unsigned byte 0x04
        "C2",       # 0027: Push $13
        "58 D1",    # 0028: Display sprite
        "C2",       # 002A: Push $13
        "58 AB",    # 002B: ???
        # TOP_OF_LOOP
        "C2",       # 002D: Push $13
        "58 07",    # 002E: ???
        "BA",       # 0030: Duplicate
        "2C 02",    # 0031: Pop byte to $13+02
        "0A FF",    # 0033: Push signed byte 0xFF
        "AA",       # 0035: Check if equal
        "44 55 00", # 0036: If not equal, jump to SOMETHING_IS_NOT_EQUAL
        # SOMETHING_IS_EQUAL
        "0C 02",    # 0039: Push signed byte from $13+02
        "C2",       # 003B: Push $13
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
        "C2",       # 0061: Push $13
        "52 35 02", # 0062: Execute behaviour script 0x235
        "2C 01",    # 0065: Pop byte to $13+01
        # BOTTOM_OF_LOOP
        "0C 01",    # 0067: Push signed byte from $13+01
        "44 2D 00", # 0069: If false, jump to TOP_OF_LOOP
        # SAMURAI_WARRIOR_DEFEATED
        "00 09",    # 006C: Push unsigned byte 0x09
        "58 7B",    # 006E: Increase experience
        "C2",       # 0070: Push $13
        "58 BF",    # 0071: ???
        "C2",       # 0073: Push $13
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
        "C2",       # 0084: Push $13
        "52 5C 03", # 0085: Execute behaviour script 0x35C
        "52 BC 01", # 0088: Execute behaviour script 0x1BC
        "BC",       # 008B: Pop
        # DONE
        "56",       # 008C: End
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        # TOP_OF_LOOP
        "C2",       # 000C: Push $13
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
        "C2",       # 0026: Push $13
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
        "C2",       # 0046: Push $13
        "58 6F",    # 0047: Set object's owner to Jake
        "52 4B 00", # 0049: Execute behaviour script 0x4B = "Got item" sound effect
        "0A FF",    # 004C: Push signed byte 0xFF
        "2C 01",    # 004E: Pop byte to $13+01 <-- Whether object has an owner
        # BOTTOM_OF_LOOP
        "0C 01",    # 0050: Push signed byte from $13+01 <-- Whether object has an owner
        "44 0C 00", # 0052: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 0055: Push $13
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
        "C2",       # 00EF: Push $13
        "58 51",    # 00F0: Push Z coordinate / 4
        "00 02",    # 00F2: Push unsigned byte 0x02
        "7A",       # 00F4: Left shift
        "C2",       # 00F5: Push $13
        "58 50",    # 00F6: Push Y coordinate / 4
        "00 02",    # 00F8: Push unsigned byte 0x02
        "7A",       # 00FA: Left shift
        "C2",       # 00FB: Push $13
        "58 4F",    # 00FC: Push X coordinate / 4
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
        "C2",       # 0111: Push $13
        "58 B8",    # 0112: Despawn object
        "56",       # 0114: End
    ],
)

# TODO:
# I'm not sure if the doors on the two Safes will successfully conceal every
# item shuffled into the Detonator, Broken Bottle and Green Bottle slots.
# Might have to make those locations hidden, then update script 0x329 (Safe)
# so it makes the new items in those locations visible.
# We don't want the items in those three slots to be like the Slap Patch in
# the morgue, which can be picked up through a closed fridge door with some
# careful cursor placement.

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
writeHelper(romBytes, 0xF40C2, bytes.fromhex(' '.join([
    "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
    "C2",       # 0002: Push $13
    "58 C5",    # 0003: Check if object has an owner
    "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
    "C2",       # 0008: Push $13
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    # TOP_OF_LOOP
    "C2",       # 000C: Push $13
    "58 C5",    # 000D: Check if object has an owner
    "2C 01",    # 000F: Pop byte to $13+01 <-- Whether object has an owner
    "00 00",    # 0011: Push unsigned byte 0x00
])))
writeHelper(romBytes, 0xF410F, bytes.fromhex(' '.join([
    "44 0C 00", # 004D: If not owned, jump to TOP_OF_LOOP
])))

# Broken Bottle
writeHelper(romBytes, 0xF4118, bytes.fromhex(' '.join([
    "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
    "C2",       # 0002: Push $13
    "58 C5",    # 0003: Check if object has an owner
    "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
    "C2",       # 0008: Push $13
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    # TOP_OF_LOOP
    "C2",       # 000C: Push $13
    "58 C5",    # 000D: Check if object has an owner
    "2C 01",    # 000F: Pop byte to $13+01 <-- Whether object has an owner
    "00 00",    # 0011: Push unsigned byte 0x00
])))
writeHelper(romBytes, 0xF4162, bytes.fromhex(' '.join([
    "44 0C 00", # 004A: If not owned, jump to TOP_OF_LOOP
])))

# Green Bottle
writeHelper(romBytes, 0xF428E, bytes.fromhex(' '.join([
    "2C 00",    # 0000: Pop byte to $13+00 <-- Spawn index
    "C2",       # 0002: Push $13
    "58 C5",    # 0003: Check if object has an owner
    "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
    "C2",       # 0008: Push $13
    "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
    # TOP_OF_LOOP
    "C2",       # 000C: Push $13
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

# Jester Spirit portal
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

# Helicopter Pilot
# - Stock the $13,000 case at the Dark Blade Gun Shop (vanilla: Concealed Jacket)
writeHelper(romBytes, 0x177C0, bytes.fromhex(' '.join([
    "0A FD",    # 0010: Push signed byte 0xFD
    "14 45 10", # 0012: Push short 0x1045 <-- Object-id of "Concealed Jacket" glass case
    "58 4B",    # 0015: Clear bits of object's flags
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
        "C2",       # 0002: Push $13
        "58 C5",    # 0003: Check if object has an owner
        "46 0C 00", # 0005: If yes, jump to TOP_OF_LOOP
        "C2",       # 0008: Push $13
        "52 1D 01", # 0009: Execute behaviour script 0x11D = New item-drawing script
        # TOP_OF_LOOP
        "C2",       # 000C: Push $13
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
        "C2",       # 0026: Push $13
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
        "C2",       # 0045: Push $13
        "58 6F",    # 0046: Set object's owner to Jake
        "52 4B 00", # 0048: Execute behaviour script 0x4B = "Got item" sound effect
        "0A FF",    # 004B: Push signed byte 0xFF
        "2C 01",    # 004D: Pop byte to $13+01 <-- Whether object has an owner
        # BOTTOM_OF_LOOP
        "0C 01",    # 004F: Push signed byte from $13+01 <-- Whether object has an owner
        "44 0C 00", # 0051: If no, jump to TOP_OF_LOOP
        # DONE
        "C2",       # 0054: Push $13
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
        "C2",       # 001B: Push $13
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
        "C2",       # 0032: Push $13
        "58 51",    # 0033: Push Z coordinate / 4
        "00 02",    # 0035: Push unsigned byte 0x02
        "7A",       # 0037: Left shift
        "C2",       # 0038: Push $13
        "58 50",    # 0039: Push Y coordinate / 4
        "00 02",    # 003B: Push unsigned byte 0x02
        "7A",       # 003D: Left shift
        "C2",       # 003E: Push $13
        "58 4F",    # 003F: Push X coordinate / 4
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
        "58 CE",    # 0060: Set bits of 7E1474+n <-- Makes item drop subject to gravity
        # DONE
        "C2",       # 0062: Push $13
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
        "C0",       # 0006: Push zero
        "C2",       # 0007: Push $13
        "58 D0",    # 0008: Change displayed sprite?
        "00 40",    # 000A: Push unsigned byte 0x40
        "C2",       # 000C: Push $13
        "58 B4",    # 000D: Conversation related?
        # TOP_OF_LOOP
        "C2",       # 000F: Push $13
        "58 6C",    # 0010: ???
        "00 05",    # 0012: Push unsigned byte 0x05
        "00 03",    # 0014: Push unsigned byte 0x03
        "58 9E",    # 0016: Register menu options / time delay
        "BC",       # 0018: Pop
        "C2",       # 0019: Push $13
        "58 02",    # 001A: Push object's flags
        "00 80",    # 001C: Push unsigned byte 0x80
        "7E",       # 001E: Bitwise AND
        "BE",       # 001F: Convert to boolean
        "44 0F 00", # 0020: If false, jump to TOP_OF_LOOP
        # GIVE_ANEKI_PASSWORD
        "14 B2 08", # 0023: Push short 0x08B2 <-- Object-id for Jake
        "14 62 07", # 0026: Push short 0x0762 <-- Object-id for Password (Aneki)
        "58 74",    # 0029: Set object's owner
        # STOCK_DARK_BLADE_CASES
        "0A FD",    # 002B: Push signed byte 0xFD
        "14 F1 0F", # 002D: Push short 0x0FF1 <-- Object-id of "Full Bodysuit" glass case
        "58 4B",    # 0030: Clear bits of object's flags
        "0A FD",    # 0032: Push signed byte 0xFD
        "14 14 10", # 0034: Push short 0x1014 <-- Object-id of "AS-7 A. Cannon" glass case
        "58 4B",    # 0037: Clear bits of object's flags
        # EXIT_VOLCANO
        "14 AA 01", # 0039: Push short 0x01AA
        "C0",       # 003C: Push zero
        "00 02",    # 003D: Push unsigned byte 0x02
        "58 54",    # 003F: Teleport to door destination, with extra arguments?
        # DONE
        "56",       # 0041: End
    ],
)





# ------------------------------------------------------------------------
# TODO:
# This is the start of the QUICK UGLY CHANGE SECTION
# (Temporary changes for testing stuff)
# (Some of these may get promoted to permanent changes)
# ------------------------------------------------------------------------

# Update the glass cases containing weapons and armor so that their
# cost matches the new randomized contents.
# This causes power growth to be more money-driven.
equipmentPrices = {
    # Weapons
    0x1952 :   500, # Beretta Pistol
    0x17C3 :   500, # Colt L36 Pistol
    0x12F3 :  2000, # Fichetti L. Pistol
    0x0157 :  3000, # Viper H. Pistol ($3,000)
    0x0150 :  4000, # Viper H. Pistol ($4,000)
    0x013B :  9000, # Warhawk H. Pistol
    0x0276 : 12000, # T-250 Shotgun ($12,000)
    0x0261 : 15000, # T-250 Shotgun ($15,000)
    0x01A4 : 30000, # Uzi III SMG
    0x0BF3 : 24000, # HK 277 A. Rifle
    0x1B5F : 40000, # AS-7 A. Cannon
    # Armor
    0x0B21 :  2000, # Leather Jacket
    0x085E :  5000, # Mesh Jacket (free)
    0x0850 :  5000, # Mesh Jacket ($5,000)
    0x18A3 :  8000, # Bulletproof Vest
    0x1696 : 13000, # Concealed Jacket
    0x0770 : 20000, # Partial Bodysuit
    0x129F : 30000, # Full Bodysuit
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

# Make all of the "initially out of stock" items available
# This specifically undoes something we went out of our way to do
# just after the "common code for glass cases" script.
# If we decide to keep this behaviour, we can comment out those
# lines as well as these ones.
initialItemState[0x9F7] &= ~0x02 # HK 277 A. Rifle  ($24,000)
initialItemState[0xA01] &= ~0x02 # Concealed Jacket ($13,000)
initialItemState[0xA06] &= ~0x02 # Partial Bodysuit ($20,000)
initialItemState[0xA3D] &= ~0x02 # Full Bodysuit    ($30,000)
initialItemState[0xA42] &= ~0x02 # AS-7 A. Cannon   ($40,000)

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

# Update Glutman so he never gives you the Zip Gun
writeHelper(romBytes, 0xDCE1A, bytes.fromhex(' '.join([
    "48 0C 00", # 0000: Jump to 000C
])))
# TODO: Prevent keyword removal in the "Glutman hides you" cutscene?

# ------------------------------------------------------------------------

## Start out ridiculously overpowered
#romBytes[0x172E] = 0x14 # defense power: 20 <-- vanilla best: 6, or 8 w/ Dermal Plating
#romBytes[0x172F] = 0x00 # 0x0000 = object-id for Zip Gun
#romBytes[0x1730] = 0x00
#romBytes[0x1731] = 0x01 # weapon type: auto
#romBytes[0x1732] = 0x1E # attack power: 30 <-- vanilla best: 20
#romBytes[0x1733] = 0x09 # accuracy: 9      <-- vanilla best: 6

# ------------------------------------------------------------------------

# Open up the monorail early

# Change the behaviour script for the left Glass Door from 0x37D
# (left Glass Door helper) to 0xAD (left Glass Door unlocked).
# In vanilla, script 0x37D would check if Glutman had hidden you
# in the caryards and then execute either script 0x6 (locked) or
# script 0xAD (unlocked), as appropriate.
# With this change, script 0x37D should now be entirely unused.
struct.pack_into("<H", romBytes, 0x6C0B3, 0x00AD)

# Change the behaviour script for the right Glass Door from 0x1A6
# (right Glass Door helper) to 0x2B4 (right Glass Door unlocked).
# In vanilla, script 0x1A6 would check if Glutman had hidden you
# in the caryards and then execute either script 0x1DC (locked) or
# script 0x2B4 (unlocked), as appropriate.
# With this change, script 0x1A6 should now be entirely unused.
struct.pack_into("<H", romBytes, 0x6C0AC, 0x02B4)

# Update the station billboard ("station is now fully repaired")
writeHelper(romBytes, 0xDF7A3, bytes.fromhex(' '.join([
    "BC",       # 000F: Pop
    "C0",       # 0010: Push zero
    "BC",       # 0011: Pop
    "48 29 00", # 0012: Jump to 0029
])))

# ------------------------------------------------------------------------

## Forbid entry to the caryards until Glutman hides you there
#expandedOffset = scriptHelper(
#    scriptNumber = 0x246,
#    argsLen      = 0x00, # Script 0x246 now takes 0 bytes (= 0 stack item) as arguments
#    returnLen    = 0x00, # Script 0x246 now returns 0 bytes (= 0 stack items) upon completion
#    offset       = expandedOffset,
#    scratchLen   = 0x00, # Header byte: Script uses 0x00 bytes of $13+xx space
#    maxStackLen  = 0x0E, # Header byte: Maximum stack height of 0x0E bytes (= 7 stack items)
#    commandList  = [
#        "14 BF 03", # 0000: Push short 0x03BF <-- Object-id for Glutman
#        "14 38 15", # 0003: Push short 0x1538 <-- Object-id for Dog Food
#        "58 42",    # 0006: Check if first object owns second object
#        "46 27 00", # 0008: If yes, jump to SHADOWRUNNERS_WAIT_OUTSIDE
#        # NOT_HIDDEN_BY_GLUTMAN_YET
#        "00 01",    # 000B: Push unsigned byte 0x01
#        "14 CD 00", # 000D: Push short 0x00CD
#        "14 00 04", # 0010: Push short 0x0400
#        "00 04",    # 0013: Push unsigned byte 0x04
#        "00 13",    # 0015: Push unsigned byte 0x13
#        "00 06",    # 0017: Push unsigned byte 0x06
#        "00 07",    # 0019: Push unsigned byte 0x07
#        "58 C7",    # 001B: Print text ("Hey, where do you think you're going?")
#        "58 A2",    # 001D: Wait for player input
#        "14 18 00", # 001F: Push short 0x0018
#        "58 56",    # 0022: Teleport to door destination
#        "48 2C 00", # 0024: Jump to DONE
#        # SHADOWRUNNERS_WAIT_OUTSIDE
#        "00 3B",    # 0027: Push unsigned byte 0x3B
#        "52 0E 01", # 0029: Execute behaviour script 0x10E = "Shadowrunners wait outside" helper script
#        # DONE
#        "56",       # 002C: End
#    ],
#)

# Start with the King paid off, so you can leave the caryards freely
initialItemState[0x24F] |= 0x01

# ------------------------------------------------------------------------

# TODO: hide the inescapable-conversation dog at Daley Station?
# TODO: make the Dermal Plating always available at Maplethorpe's?

# ------------------------------------------------------------------------

## Open the door to the Rust Stilettos HQ
#initialItemState[0x59C] |= 0x80

# ------------------------------------------------------------------------

# Open up Jagged Nails without having to defeat the Rust Stilettos

# Force the "always room for a true shadowrunner" conversation
writeHelper(romBytes, 0xF628E, bytes.fromhex(' '.join([
    "BE",       # 0018: Convert to boolean
    "BC",       # 0019: Pop
    "48 1D 00", # 001A: Jump to 001D
])))

# Truncate the "handled that Stilettos gang mighty fine" text
romBytes[0xE9950] = 0xB8
romBytes[0xE9951] = 0x80

## Set the entry fee to 0 nuyen (doesn't change text)
#romBytes[0x179DF] = 0x00

# ------------------------------------------------------------------------

## Open the gate to the Rat Shaman Lair
## (Side effect: prevents Dog Spirit conversation where you learn "Rat")
#initialItemState[0x4CA] |= 0x01

## Open the gate to the Dark Blade mansion (creates possibility of
## softlock if you give Vladimir the Magic Fetish before showing it
## to the Dog Spirit)
## (Side effect: prevents "DBlade" phone conversation)
#initialItemState[0x565] |= 0x01

## Make the Massive Orc appear on the Taxiboat Dock (drops Explosives
## in vanilla, normally requires either "Nirwanda" or "Laughlyn")
#romBytes[0xFA9F5] = 0xBC
#romBytes[0xFA9F6] = 0xC0
#romBytes[0xFA9F7] = 0xBC

## Open up Bremerton (talk to the taxiboat driver once, no fee)
#romBytes[0xF898F] = 0xBC
#romBytes[0xF8990] = 0xC0
#romBytes[0xF8991] = 0xBC
#initialItemState[0x3E9] |= 0x80

## Open the door leading to Bremerton's interior
#initialItemState[0x32B] |= 0x01

## Start with the Cyberdeck
#initialItemState[0x229] = 0xB2 # 0x08B2 = object-id for Jake
#initialItemState[0x22A] = 0x08

## In the Computer helper script, skip the "Jake + datajack damaged" check
#romBytes[0xFD644] = 0x48
#romBytes[0xFD645] = 0x54
#romBytes[0xFD646] = 0x00

## Start with the Drake Password
## The computer on the first floor of the Drake Towers requires you to
## have the Drake Password in your inventory in order to proceed.
## Examining the Drake Password has no effect.
#initialItemState[0x81E] = 0xB2 # 0x08B2 = object-id for Jake
#initialItemState[0x81F] = 0x08

## Warp to the Gold Naga boss room when exiting the morgue's main room
## (For testing the item drop in the Serpent Scales location)
#romBytes[0xC84F4] = 0x9F # 0x009F = door-id to enter Gold Naga boss room from lower left
#romBytes[0xC84F5] = 0x00

## Start with the Aneki Password
## The computer on the first floor of the Aneki Building requires you to
## have the Aneki Password in your inventory in order to proceed.
#initialItemState[0x666] = 0xB2 # 0x08B2 = object-id for Jake
#initialItemState[0x667] = 0x08

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
    f" {randomizerVersion:>13.13}    -{randomizerFlags:<12.12} "
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
# This version has two additional objects:
# - Item shuffled to the "Keyword: Jester Spirit" location
# - Item shuffled to the "Nuyen: Rat Shaman" location
romBytes[0x114600]          = romBytes[0xD0636]            # Vanilla drawing data
romBytes[0x114601]          = romBytes[0xD0637]            # Vanilla music
romBytes[0x114602:0x114604] = struct.pack("<H", 0xC6AE)    # Vanilla camera pointer, adjusted for the new room data location
romBytes[0x114604]          = 0x08                         # +2 to the number of objects
romBytes[0x114605:0x114629] = romBytes[0xD063B:0xD065F]    # Vanilla objects
romBytes[0x114629:0x11462D] = bytes.fromhex("78 01 D0 19") # New object's coordinates (same location as Rat Shaman)
romBytes[0x11462D:0x11462F] = romBytes[0xD29A7:0xD29A9]    # New object's object-id
romBytes[0x11462F:0x114633] = bytes.fromhex("78 01 D0 19") # New object's coordinates (same location as Rat Shaman)
romBytes[0x114633:0x114635] = romBytes[0xD2965:0xD2967]    # New object's object-id
romBytes[0x114635:0x1146B0] = romBytes[0xD065F:0xD06DA]    # Vanilla remainder of room data
# Update the door destinations to lead to the new Rat Shaman boss room
struct.pack_into("<H", romBytes, 0x692AF + (9 * 0x12C), 0x4600)



outFileName = args.output_file
if outFileName is None:
    suffix = f"_{seed}"
    basename, dot, extension = inFileName.rpartition(".")
    if basename and extension:
        basename += suffix
    else:
        extension += suffix
    outFileName = basename + dot + extension

with open(outFileName, "xb") as outFile:
    outFile.write(romBytes)
