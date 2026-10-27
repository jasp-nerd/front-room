# Imagery

| File | What | Source |
|---|---|---|
| `../illustration/room-hero.jpg` | The drawn family on the sofa, seen over their shoulders, with Pip on the back of the sofa. The TV shows a real capture of `/tv?state=origin`, and the four phones show real captures of Rob's, Ana's, Leo's and Sam's screens. Used for the README hero, the home page (where the live TV is laid over it) and the video. | The room is a generated drawing with chroma-green screens (`../illustration/source/room.png`, prompt beside it), widened to a 16:9 TV by `widen_tv.py`. `compose_room.py --drawn` finds each screen and warps a capture onto it. |

We don't use photographs of people. Every person and character is drawn, in the flat style of the brand (see `BRAND.md`). Match imagery comes only from our own synthetic match render. The drawings are generated with OpenAI image generation through the Codex CLI, from the prompts kept next to each source.

To rebuild the hero after changing a surface, capture `/tv?state=origin&replay=0` at 1920×1080 and each phone at 390×844 (`/phone?fan=rob`, `ana`, `leo`, `sam`), then run:

    uv run --with pillow --with numpy --with scipy python compose_room.py \
        --source ../illustration/source/room-16x9.png --drawn \
        --tv tv.png --phones rob.png ana.png leo.png sam.png --out ../illustration/room-hero.jpg
