Front Room gives everyone on the sofa their own AI helper for the match, and keeps the one shared TV fair to all of them. **Bright, friendly and plain-spoken: a family product for match day, not a dashboard.**

Other products in this space draw a pitch. We draw the room: the sofa, the TV, the phones, the people, and Pip, the robin who referees what the room sees.

## Voice

- **Talk like a friend who knows football.** Short, specific, plain words: "Mensah won it back on halfway. Five passes later, Okafor scored." Never "AI-powered insight detected a key moment".
- **Words for fans:**
  - "your helper", not "agent";
  - "asks for the TV", not "bids";
  - "Pip, the referee", not "Room Director".
  - Technical words belong on /how, the studio and the docs.
- **A screen's main line is eight words or fewer.** Cut any sentence a skimmer would skip.
- **Credit, never blame.** Name the player who made something happen. Rival fans share the sofa.
- **Sentence case everywhere.** No tracked capitals, no Title Case, no emoji.
- **Shared screens:** no odds, win probability or betting language.
- **Banned words:** *elevate, unleash, seamless, supercharge, revolutionise, game-changing*.

Lines to reuse:
- "One TV. Everyone's own match."
- "Pip keeps it fair."
- "Scan to join the room"
- "3 of 4 in the room asked for this"
- "Kept neutral: both clubs are here"

## Colour

A white page, one loud colour, and big rounded colour fields. It is the brightness of a sunny matchday, not a stadium at night.

- **Paper:**
  - `surface` (#ffffff) is the ground;
  - `surface-raised` (mist, #f4f6f9) is for panels;
  - `surface-sunken` is for tracks.
  - Surfaces step by tone, not by shadow.
- **Robin** (`signal`, #d63d15) is Pip's breast and the one action colour.
  - It is for the main button on a screen, progress, the room's pick on the TV and the dots of those who asked.
  - Nothing else is robin, so robin always means "this one".
  - Put white text on it at 16px bold or larger.
- **Fields:**
  - `pitch` #178a47, `sun` #ffc43d, `sky` #4aa8ff and `pink` #ff8fb3 are big colour fields with `radius-l`, each with a `-wash` for chips and panels.
  - Text on sun, sky and pink is always ink. White goes only on pitch and navy, at 24px or larger.
- **Navy** (#14202f) is the ink of all text, and one contrast field per page: the moment the room decides.
- **Fans have colours:** Rob is sky, Ana sun, Leo pitch and Sam pink. Their phone accents and their helper's scarf use them.
- **Club colours are data.** Use them on that fan's own phone, team chips and charts. On the TV they are equal marks for both clubs, never one club's framing.
- **Captions** keep the classic black plate with white type (`access-plate`/`access-ink` for the transcript), and are never outbid.
- **Never use:**
  - gradients, glows or blurred glass;
  - dark pages;
  - the Premier League's purple and cyan;
  - Microsoft blue.

## Type

- **`display` (Gabarito 800), for headings:** round, friendly and heavy, tracked tight (−2% to −3.5%).
- **`text` (Figtree), for everything people read:** 17px body on phones and pages, a 14px floor.
- **`score` (Barlow Condensed 700):** only scores, clocks and big figures, always with tabular figures. That is the football energy, kept to numbers.
- **`code`:** real code and endpoints only.
- **Sizes:** three per view at most. Headlines run two lines at most and end without a full stop.

## Shape

- **Buttons and chips are pills.**
  - The main button sits on a solid darker lip (`signal-lip`, 4–5px), and pressing it squashes the lip.
  - Secondary buttons are white on a grey lip.
- **Cards** are `radius-m` (20px). **Fields** are `radius-l` (32px).
- **No blur shadows at rest.** A card that can be held or pressed sits on a flat `lip`. `shadow-float` is only for things that truly float.
- **TV cards** (score bug, lower third, replay label) are solid white with a 6–8px ink lip at 20%, so they lift off any picture.

## The shared screen (TV)

- **The base state is the match.** The score bug sits on a white card, with the minute on a sun tab.
- **One overlay at a time.** It is a white card with a robin edge: one headline of six words or fewer, one supporting line, and one provenance line ("3 of 4 in the room asked for this · Kept neutral: both clubs are here"). Pip blows the whistle in its corner.
- **Replays are labelled "Replay"**, and the match clock keeps running.
- **Captions persist** under any overlay, in every language present in the room.
- **The TV never says one action decided a goal.** It says what the match feed proves.

## The phone

- **Ownership:** each phone carries its fan's colour, and their helper robin signs what it sent.
- **The strip at the top** always says what is on the TV now, with "Why this?".
- **Analyst, simple, kid and listen views** change what is shown, not just the wording.
- **Nothing appears on a phone before the TV shows it.** Before then the phone waits, with the fan's helper on their colour.
- **Setup** asks one question per screen: join, how you like to watch, what your helper understood, done.
- **Ergonomics:** actions sit at the bottom within thumb reach, with 44px targets. Switches turn green when on.

## Logo, Pip and the cast

- **The logo** is Pip's head (`illustration/pip-head`) beside "Front Room" in Gabarito ExtraBold (`logo/wordmark.svg`, `-reversed` for navy). Use the lockup in page headers and on the join screen.
- **The app icon** is Pip's head on a sun tile (`logo/icons/`).
- **Pip is the robin referee, the fair one who holds the remote.** Pip wears the whistle and decides.
  - Poses: neutral, wave, whistle, remote, cheer, think, phone and sleep.
  - One Pip per screen, on a colour field where possible.
  - Never on the TV during play, except the small whistle on the lower third.
- **The helpers** are small robins in scarves, one per fan in that fan's colour. They ask; they never wear the whistle.
- **The family:** Rob, Ana, Leo and Sam, drawn head and shoulders (`FanFace`).
- **Clear space** is the height of Pip's head on every side. The wordmark is never narrower than 96px.

## Imagery

- **Everything is drawn:** a flat, mid-century cartoon style with simple shapes, flat fills and dot eyes. No photos of people, no 3D and no AI-photo look.
  - The drawings are generated from the prompts in `illustration/source/` and cut out by `cutout.py`.
- **Show the real product inside the drawings.** The hero is the drawn living room with our real TV and phone screens composited in (`imagery/compose_room.py`).
- **The match is our own synthetic render.** Never broadcast footage, never real clubs or league marks.
- **Icons** are 2px strokes on a 24px grid. No icon library and no emoji.

## Motion

- **Cards rise in** over 320ms (`cubic-bezier(.2,.8,.2,1)`), hold for their dwell time, and leave.
- **Buttons press down onto their lip.**
- **On the pitch:** rings draw on, and pass paths trace in time with the replay.
- **Phones change after the TV,** never before.
- **`prefers-reduced-motion` gets a cut** instead of a rise.
