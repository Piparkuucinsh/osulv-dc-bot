from config import MODS_DICT

async def mods_int_from_list(mods):
    modint = 0
    for mod in mods:
        modint += MODS_DICT[mod]
    return int(modint)
