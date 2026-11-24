// The six pixel-art characters, the picker to choose one, and the karaoke room they sit in.
// A singer's character is their `avatar` (1-6), stored by the sessions service (migration V003).
// The picker is on the home and join forms; the room is on the session, recording and finale
// pages: everyone sits around the table, and whoever has the line being sung stands up with the mic.
//
// Every character is the same 16 x 18 pixel body with hair and an outfit on top, plus an open
// mouth and a mic while singing. In the grids each letter is a colour from the palettes below,
// and "." keeps whatever is underneath.

const BODY = [
  "................",
  "................",
  "................",
  "....OOOOOOOO....",
  "...OSSSSSSSSO...",
  "..OSSSSSSSSSSO..",
  "..OSSSSSSSSSSO..",
  "..OSSESSSSESSO..",
  "..OSSESSSSESSO..",
  "..OSBSSSSSSBSO..",
  "...OSSSMMSSSO...",
  "....OOSSSSOO....",
  ".....OsSSsO.....",
  "..OOCCCCCCCCOO..",
  ".OCCCCCCCCCCCCO.",
  ".OCCCCCCCCCCCCO.",
  ".OCCCCCCCCCCCCO.",
  ".OCCCCCCCCCCCCO.",
];
const SINGING = [ // from row 10: open mouth, and the mic in the right hand
  ".......DD.......",
  ".......DDKK.....",
  ".........KK.....",
  "..........k.....",
  ".........SSS....",
  "..........ccc...",
];
const HAIR = { // from row 0
  spiky: [
    "......O..O......",
    "....OOHOOHOO....",
    "...OHHHHHHHHO...",
    "..OHHhHHHHhHHO..",
    "..OHHHHHHHHHHO..",
    "..OHSSSHHSSSHO..",
    "..OH........HO..",
    "..OH........HO..",
  ],
  long: [
    "................",
    ".....OOOOOO.....",
    "...OOHHHHHHOO...",
    "..OHHHHHHHHHHO..",
    ".OHHhHHHHHHhHHO.",
    ".OHHSSHSSHSSHHO.",
    ".OHH........HHO.",
    ".OHH........HHO.",
    ".OHH........HHO.",
    ".OHH........HHO.",
    ".OHH........HHO.",
    ".OHH........HHO.",
    ".OHH........HHO.",
    ".OHH........HHO.",
    ".OHO........OHO.",
  ],
  buns: [
    "..OOO......OOO..",
    ".OHhHO....OHhHO.",
    ".OHHHOOOOOOHHHO.",
    "..OOHHHHHHHHOO..",
    "..OHHHHHHHHHHO..",
    "..OHHSSSSSSHHO..",
    "..OH........HO..",
  ],
  beanie: [
    "......OPPO......",
    "...OOOOOOOOOO...",
    "..OTTtTTtTTtTO..",
    "..OTTTTTTTTTTO..",
    "..OttttttttttO..",
    "..OHHSSSSSSHHO..",
    "..OH........HO..",
  ],
  sidepart: [
    "................",
    "....OOOOOOOO....",
    "...OHHHHHHhHO...",
    "..OHHHHHHHhHHO..",
    "..OHHHHHHSSSSO..",
    "..OHHSSSSSSSSO..",
    "..OH............",
  ],
  curls: [
    "...OOOOOOOOOO...",
    "..OHHhHHHHhHHO..",
    ".OHHHHHHHHHHHHO.",
    "OHHhHHHHHHHHhHHO",
    "OHHHHHHHHHHHHHHO",
    "OHHHSSSSSSSSHHHO",
    "OHH..........HHO",
    "OHH..........HHO",
    ".OH..........HO.",
  ],
};
const OUTFIT = { // from row 13
  hoodie: ["....cccccccc....", "......A..A......", "......A..A......", "...cccccccccc...", "...c........c..."],
  blazer: ["......AAAA......", "....cAATTAAc....", ".....cATTAc.....", "......cAAc......", "................"],
  suit: [".....cAAAAc.....", "....ccATTAcc....", ".....cATTAc.....", "......cTTc......", ".......TT......."],
  stage: ["...TTTTTTTTTT...", "....A.....A.....", "........A.......", "...A.......A....", "......A....A...."],
  tee: ["......cccc......", "................", "......AAAA......", ".......AA.......", "......AAAA......"],
  cardigan: ["......TTTT......", ".....cTTTTc.....", "......cTTc......", ".......A........", ".......A........"],
};
// O outline, E eyes, M mouth, D open mouth, K/k the mic. The rest is each character's own palette:
// S/s skin, B blush, H/h hair, C/c clothes, A/T/t details, P beanie bobble.
const SHARED_COLOURS = { O: "#24142c", E: "#24142c", M: "#b8505a", D: "#3a1622", K: "#3b3b46", k: "#c7c9d1" };

// Avatar n (1-6) is CHARACTERS[n - 1]. `look` is the name shown in the picker.
const CHARACTERS = [
  { look: "Hoodie", hair: "spiky", outfit: "hoodie", colours: {
    S: "#f2c7a5", s: "#d9a383", B: "#ec9a96", H: "#5a3a29", h: "#7b5640", C: "#d94b4b", c: "#a83636", A: "#f4efe6" } },
  { look: "Blazer", hair: "buns", outfit: "blazer", colours: {
    S: "#f6d2b8", s: "#dcae90", B: "#ef9ba2", H: "#1f1b2e", h: "#3d3656", C: "#2f3f74", c: "#22305a", A: "#f4efe6",
    T: "#d9445a" } },
  { look: "Suit", hair: "sidepart", outfit: "suit", colours: {
    S: "#c98e64", s: "#a8714d", B: "#c9706a", H: "#241c1c", h: "#4a3a36", C: "#5d6170", c: "#474a57", A: "#f4efe6",
    T: "#3b82c4" } },
  { look: "Stage", hair: "long", outfit: "stage", colours: {
    S: "#f7d6c4", s: "#ddb09a", B: "#f19bb0", H: "#e98bc0", h: "#f7b6d9", C: "#7b4bb8", c: "#5c3690", A: "#ffd76a",
    T: "#f4a6cf" } },
  { look: "Beanie", hair: "beanie", outfit: "tee", colours: {
    S: "#8d5a3b", s: "#6f4329", B: "#a8584f", H: "#1d1512", h: "#3a2a22", C: "#3f9a6a", c: "#2e7550", A: "#f4efe6",
    T: "#f2c14e", t: "#c99a2e", P: "#f4efe6" } },
  { look: "Cardigan", hair: "curls", outfit: "cardigan", colours: {
    S: "#a86b47", s: "#87523a", B: "#b5645a", H: "#2a1d16", h: "#4a3326", C: "#d9a93a", c: "#b0852a", A: "#f4efe6",
    T: "#e8e1d3" } },
];

// One character as a 16 x 18 canvas (made once, then reused).
const sprites = new Map();
function sprite(avatar, singing) {
  const character = CHARACTERS[avatar - 1] ?? CHARACTERS[0]; // someone without one (shouldn't happen): the first
  const key = `${character.look}:${singing}`;
  if (sprites.has(key)) return sprites.get(key);
  const grid = BODY.map((row) => [...row]);
  const layer = (rows, firstRow) => rows.forEach((row, r) => [...row].forEach((cell, c) => {
    if (cell !== ".") grid[firstRow + r][c] = cell;
  }));
  layer(HAIR[character.hair], 0);
  layer(OUTFIT[character.outfit], 13);
  if (singing) layer(SINGING, 10);
  const canvas = document.createElement("canvas");
  canvas.width = 16;
  canvas.height = 18;
  const ctx = canvas.getContext("2d");
  grid.forEach((row, r) => row.forEach((cell, c) => {
    const colour = character.colours[cell] ?? SHARED_COLOURS[cell];
    if (colour) {
      ctx.fillStyle = colour;
      ctx.fillRect(c, r, 1, 1);
    }
  }));
  sprites.set(key, canvas);
  return canvas;
}

// --- The picker ------------------------------------------------------------------------------

// The six characters as radio buttons named "avatar" inside `container`, with `selected` (1-6)
// chosen. The chosen one (and the one under the mouse) shows its singing pose.
// Returns { value } (the chosen avatar) and select(avatar).
function characterPicker(container, selected = 1) {
  container.classList.add("picker");
  container.setAttribute("role", "radiogroup");
  container.setAttribute("aria-label", "Your character");
  const choices = CHARACTERS.map((character, i) => {
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "avatar";
    input.value = i + 1;
    const canvas = document.createElement("canvas");
    canvas.width = 16;
    canvas.height = 18;
    const paint = (singing) => {
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, 16, 18);
      ctx.drawImage(sprite(i + 1, singing), 0, 0);
    };
    const label = el("label", "", "pick");
    label.append(input, canvas, el("span", character.look));
    label.addEventListener("pointerenter", () => paint(true));
    label.addEventListener("pointerleave", () => paint(input.checked));
    container.append(label);
    return { input, paint };
  });
  const repaint = () => choices.forEach(({ input, paint }) => paint(input.checked));
  container.addEventListener("change", repaint);
  const select = (avatar) => {
    choices.forEach(({ input }) => (input.checked = Number(input.value) === avatar));
    repaint();
  };
  select(selected);
  return {
    get value() {
      return Number(container.querySelector("input:checked")?.value ?? 1);
    },
    select,
  };
}

// The first character nobody in `participants` has yet (1 if all six are taken), to pre-select.
function firstFreeCharacter(participants) {
  const taken = new Set(participants.map((p) => p.avatar));
  return CHARACTERS.findIndex((_, i) => !taken.has(i + 1)) + 1 || 1;
}

// --- The room --------------------------------------------------------------------------------

const ROOM_WIDTH = 200; // in room pixels: the canvas is scaled up to the page width without smoothing
const ROOM_HEIGHT = 112;
const TABLE_TOP = 86;

// Draw the room in `container` and keep it animated. The TV and the name tags are HTML on top of
// the canvas, so their text stays sharp. Returns:
//   setPeople(participants, myId)  who sits around the table (in joining order), and which one is me
//   setSinger(participantId)       who stands up with the mic (null: everyone sits)
//   setTitle(text), setCaption(text)  the TV's two lines (the caption shows while nobody sings)
function createRoom(container) {
  const canvas = document.createElement("canvas");
  canvas.width = ROOM_WIDTH;
  canvas.height = ROOM_HEIGHT;
  canvas.setAttribute("aria-hidden", "true"); // the TV and the name tags carry the text
  const title = el("div", "", "tv-title");
  const who = el("div", "", "tv-who");
  const tv = el("div", "", "tv-text");
  tv.append(title, who);
  const tags = el("div");
  container.classList.add("room");
  container.replaceChildren(canvas, tv, tags);

  const ctx = canvas.getContext("2d");
  const px = (colour, x, y, w = 1, h = 1) => {
    ctx.fillStyle = colour;
    ctx.fillRect(x, y, w, h);
  };
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let people = []; // { id, name, avatar, x } with x the middle of their seat
  let singer = null; // the person standing with the mic
  let caption = "";
  let drawn = "";

  function draw(t) {
    // Back wall with panels and a neon strip
    px("#2b1838", 0, 0, ROOM_WIDTH, ROOM_HEIGHT);
    for (let x = 0; x < ROOM_WIDTH; x += 20) px("#251433", x, 0, 1, 60);
    px("#7a3a66", 0, 5, ROOM_WIDTH, 3);
    px("#ff7ab8", 0, 6, ROOM_WIDTH, 1);
    // The karaoke TV, with a speaker on each side and a small disco light above
    px("#0e0a14", 64, 13, 72, 38);
    px("#1b2a5c", 67, 16, 66, 32);
    px("#22357a", 67, 16, 66, 3);
    px("#0e0a14", 97, 51, 6, 3);
    for (const sx of [44, 145]) {
      px("#0e0a14", sx, 20, 11, 26);
      px("#3a2a44", sx + 3, 24, 5, 5);
      px("#3a2a44", sx + 2, 34, 7, 7);
      px("#15101c", sx + 4, 36, 3, 3);
    }
    px(["#ff7ab8", "#ffd76a", "#7ad0ff"][reduceMotion ? 0 : Math.floor(t / 400) % 3], 99, 9, 2, 2);
    // The sofa, with a soft spotlight behind whoever is singing
    px("#5c2240", 10, 54, 180, 26);
    px("#7a2e4a", 12, 56, 176, 22);
    for (let x = 40; x < 188; x += 30) px("#5c2240", x, 57, 1, 20);
    px("#8f3a58", 12, 56, 176, 2);
    if (singer) {
      px("#9a3f66", singer.x - 12, 56, 24, 22);
      px("#b24d78", singer.x - 8, 56, 16, 22);
    }
    // Everyone around the table: the singer stands (higher up), bounces and sings into the mic
    for (const person of people) {
      const singing = person === singer;
      const bounce = singing && !reduceMotion ? Math.floor(t / 260) % 2 : 0;
      const mouthOpen = singing && (reduceMotion || Math.floor(t / 200) % 3 !== 0);
      const top = singing ? TABLE_TOP - 21 - bounce : TABLE_TOP - 15;
      ctx.drawImage(sprite(person.avatar, mouthOpen), person.x - 8, top);
    }
    // Two music notes floating up from the singer
    if (singer && !reduceMotion) {
      for (let k = 0; k < 2; k++) {
        const phase = (t / 1600 + k * 0.5) % 1;
        const x = singer.x + 7 + k * 3 + Math.round(Math.sin(phase * 6) * 2);
        const y = TABLE_TOP - 24 - Math.round(phase * 14);
        ctx.globalAlpha = 1 - phase;
        px("#ffd76a", x, y, 1, 4);
        px("#ffd76a", x - 2, y + 3, 2, 2);
        px("#ffd76a", x + 1, y, 2, 1);
        ctx.globalAlpha = 1;
      }
    }
    // The low table with drinks, a songbook and a tambourine
    px("#a8714d", 20, TABLE_TOP, 160, 2);
    px("#8b5a3c", 20, TABLE_TOP + 2, 160, 5);
    px("#6b4029", 20, TABLE_TOP + 7, 160, 7);
    px("#4e2e1e", 24, TABLE_TOP + 14, 4, 4);
    px("#4e2e1e", 172, TABLE_TOP + 14, 4, 4);
    for (const [x, drink] of [[48, "#ffcf6e"], [74, "#7ad0ff"], [126, "#ff9fc8"], [152, "#b6f08a"]]) {
      px("#e9e4f0", x, TABLE_TOP - 4, 4, 5);
      px(drink, x, TABLE_TOP - 2, 4, 3);
      px("#f6ecf4", x + 2, TABLE_TOP - 7, 1, 4);
    }
    px("#2f3f74", 92, TABLE_TOP - 1, 10, 2);
    px("#f4efe6", 93, TABLE_TOP - 1, 8, 1);
    px("#d9a93a", 106, TABLE_TOP - 2, 6, 2);
    px("#f4efe6", 107, TABLE_TOP - 2, 1, 1);
    px("#f4efe6", 110, TABLE_TOP - 2, 1, 1);
    // The floor and a rug
    px("#1c1024", 0, 100, ROOM_WIDTH, 12);
    px("#3a1f44", 30, 104, 140, 6);
    for (let x = 34; x < 168; x += 8) px("#55306a", x, 106, 4, 1);
  }

  // About 12 frames a second is plenty for pixel art, and kinder to batteries. Nothing is drawn
  // while the room is hidden (e.g. the recording page before Start).
  let last = -Infinity;
  const frame = (t) => {
    if (t - last >= 80 && canvas.offsetParent !== null) {
      draw(t);
      last = t;
    }
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);

  function showText() {
    who.textContent = singer ? `♪ ${singer.name} ♪` : caption;
    [...tags.children].forEach((tag, i) => tag.classList.toggle("singing", people[i] === singer));
  }

  return {
    setPeople(participants, myId = null) {
      // Seats spread around the middle of the table, closer together when more people come
      const gap = participants.length > 1 ? Math.min(25, 150 / (participants.length - 1)) : 0;
      const key = JSON.stringify([participants.map((p) => [p.id, p.display_name, p.avatar]), myId]);
      if (key === drawn) return; // the session page reloads every few seconds: keep the tags
      drawn = key;
      const singerId = singer?.id;
      people = participants.map((p, i) => ({
        id: p.id, name: p.display_name, avatar: p.avatar,
        x: Math.round(ROOM_WIDTH / 2 + (i - (participants.length - 1) / 2) * gap),
      }));
      singer = people.find((p) => p.id === singerId) ?? null;
      tags.replaceChildren(...people.map((person) => {
        const tag = el("span", person.id === myId ? `${person.name} (you)` : person.name, "tag");
        tag.classList.toggle("me", person.id === myId);
        tag.style.left = `${(person.x / ROOM_WIDTH) * 100}%`;
        tag.style.maxWidth = `${(Math.max(gap, 24) / ROOM_WIDTH) * 100}%`;
        tag.title = person.name;
        return tag;
      }));
      showText();
    },
    setSinger(participantId) {
      const next = people.find((p) => p.id === participantId) ?? null;
      if (next === singer) return; // called on every screen refresh while the song plays
      singer = next;
      showText();
    },
    setTitle(text) {
      title.textContent = text;
    },
    setCaption(text) {
      caption = text;
      showText();
    },
  };
}
