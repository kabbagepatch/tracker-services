
# https://github.com/dwiv/colorgram.py/blob/79de8bedbc9de9228c7e479c2211dcf9c39e9282/colorgram/colorgram.py


import array
from collections import namedtuple
from io import BytesIO
from urllib.parse import urlparse

import httpx
from PIL import Image

ARRAY_DATATYPE = 'l'

Rgb = namedtuple('Rgb', ('r', 'g', 'b'))
Hsl = namedtuple('Hsl', ('h', 's', 'l'))
TraditionalHsl = namedtuple('TraditionalHsl', ('h', 's', 'l'))

class Color:
    def __init__(self, r, g, b, proportion):
        self.rgb = Rgb(r, g, b)
        self.proportion = proportion
    
    def __repr__(self):
        return f"<colorgram.py Color: {self.rgb!s}, {self.proportion * 100!s}%>"

    @property
    def hsl(self):
        try:
            return self._hsl
        except AttributeError:
            self._hsl = Hsl(*hsl(*self.rgb))
            return self._hsl

    @property
    def hex(self):
        try:
            return self._hex
        except AttributeError:
            self._hex = get_hex(*self.rgb)
            return self._hex

def get_top_colors(image_url):
    parsed_url = urlparse(image_url)
    if parsed_url.scheme != "https" or parsed_url.hostname != "i.discogs.com":
        return []
    try:
        with httpx.stream("GET", image_url, timeout=10) as response:
            response.raise_for_status()
            data = b""
            for chunk in response.iter_bytes():
                data += chunk
                if len(data) > 5_000_000:
                    return []
        image = Image.open(BytesIO(data))
        if image.width * image.height > 20_000_000:
            return []
        image.thumbnail((100, 100))

        colors = extract(image, 10)
        return [color.hex for color in colors]
    except Exception as e:  # noqa: BLE001
        print("Error opening image", e)
        return []

def extract(f, number_of_colors):
    image = f if isinstance(f, Image.Image) else Image.open(f)
    if image.mode not in ('RGB', 'RGBA', 'RGBa'):
        image = image.convert('RGB')
    
    samples = sample(image)
    used = pick_used(samples)
    used.sort(key=lambda x: x[0], reverse=True)
    return get_colors(samples, used, number_of_colors)

def sample(image):
    top_two_bits = 0b11000000

    sides = 1 << 2 # Left by the number of bits used.
    cubes = sides ** 7

    samples = array.array(ARRAY_DATATYPE, (0 for _ in range(cubes)))
    width, height = image.size
    
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            # Pack the top two bits of all 6 values into 12 bits.
            # 0bYYhhllrrggbb - luminance, hue, luminosity, red, green, blue.

            r, g, b = pixels[x, y][:3]
            h, _s, l = hsl(r, g, b) #this is still using the original HSL in case it's necessry for proper function
            # Standard constants for converting RGB to relative luminance.
            Y = int(r * 0.2126 + g * 0.7152 + b * 0.0722)

            # Everything's shifted into place from the top two
            # bits' original position - that is, bits 7-8.
            packed    = (Y & top_two_bits) << 4
            packed |= (h & top_two_bits) << 2
            packed |= (l & top_two_bits) << 0

            # Due to a bug in the original colorgram.js, RGB isn't included.
            # The original author tries using negative bit shifts, while in
            # fact JavaScript has the stupidest possible behavior for those.
            # By uncommenting these lines, "intended" behavior can be
            # restored, but in order to keep result compatibility with the
            # original the "error" exists here too. Add back in if it is
            # ever fixed in colorgram.js.

            # packed |= (r & top_two_bits) >> 2
            # packed |= (g & top_two_bits) >> 4
            # packed |= (b & top_two_bits) >> 6
            # print "Pixel #{}".format(str(y * width + x))
            # print "h: {}, s: {}, l: {}".format(str(h), str(s), str(l))
            # print "R: {}, G: {}, B: {}".format(str(r), str(g), str(b))
            # print "Y: {}".format(str(Y))
            # print "Packed: {}, binary: {}".format(str(packed), bin(packed)[2:])
            # print
            packed *= 4
            samples[packed]     += r
            samples[packed + 1] += g
            samples[packed + 2] += b
            samples[packed + 3] += 1
    return samples

def pick_used(samples):
    used = []
    for i in range(0, len(samples), 4):
        count = samples[i + 3]
        if count:
            used.append((count, i))
    return used

def get_colors(samples, used, number_of_colors):
    pixels = 0
    colors = []
    number_of_colors = min(number_of_colors, len(used))

    for count, index in used[:number_of_colors]:
        pixels += count

        color = Color(
            samples[index] // count,
            samples[index + 1] // count,
            samples[index + 2] // count,
            count
        )

        colors.append(color)
    for color in colors:
        color.proportion /= pixels
    return colors

def get_hex(r, g, b):
    return f"#{r:x}{g:x}{b:x}"

def hsl(hex_r, hex_g, hex_b):
    r = hex_r / 255
    g = hex_g / 255
    b = hex_b / 255
    if r > g:
        if b > r:
            most, least = b, g
        elif b > g:
            most, least = r, g
        else:
            most, least = r, b
    else:
        if b > g:
            most, least = b, r
        elif b > r:
            most, least = g, r
        else:
            most, least = g, b
    
    l = int((most + least) * 100 / 2)
    
    if most == least:
        h = s = 0
    else:
        diff = most - least
        if l > 0.5:
            s = int(diff * 100 / (2 - most - least))
        else:
            s = int(diff * 100 / (most + least))
        
        if most == r:
            h = int(60 * (g - b) / diff + (6 if g < b else 0))
        elif most == g:
            h = int(60 * (b - r) / diff + 2)
        else:
            h = int(60 * (r - g) / diff + 4)
    
    return h, s, l
