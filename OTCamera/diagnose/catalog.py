"""Chip identification expressions and revision-specific populations."""

# Register, mask, shift, accepted values; SHT4x uses a CRC-protected conversion.
CHIPS = {
    "lis2dw12": (0x0F, 0xFF, 0, (0x44,)),
    "lps22hh": (0x0F, 0xFF, 0, (0xB3, 0xB1)),
    "bq25883": (0x25, 0x78, 3, (3,)),
    "sht40": (0xFD, 0xFF, 0, ()),
}
EXPECTED_POPULATION = {
    "v20d": (("lis2dw12", 0x18), ("sht40", 0x44), ("lps22hh", 0x5C), ("bq25883", 0x6B)),
}
