"""Reviewed historical demo boundary; current-air coverage is not established."""

SOUTH, NORTH, WEST, EAST = 28.624, 28.638, 77.215, 77.243


def contains(lat, lng):
    return SOUTH <= lat <= NORTH and WEST <= lng <= EAST


def polygon():
    return {
        "type": "Polygon",
        "coordinates": [
            [[WEST, SOUTH], [EAST, SOUTH], [EAST, NORTH], [WEST, NORTH], [WEST, SOUTH]]
        ],
    }
