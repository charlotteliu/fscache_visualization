const CAPACITY = { small: 3, main: 7, ghost: 7 };
const TRACE = ["A", "B", "C", "A", "D", "E", "B", "F", "G", "A", "H", "B", "C", "I", "A", "B"];
const COLORS = ["#2563eb", "#7c3aed", "#0891b2", "#059669", "#dc2626", "#ea580c", "#9333ea", "#0f766e"];

const state = {
  small: [],
  main: [],
  ghost: [],
  hits: 0,
  misses: 0,
  traceIndex: 0,
  lastTouched: null,
  timer: null,
};

const elements = {
  input: document.querySelector("#request-input"),
  request: document.querySelector("#request-button"),
  traceButtons: document.querySelector("#trace-buttons"),
  step: document.querySelector("#step-button"),
  auto: document.querySelector("#auto-button"),
  reset: document.querySelector("#reset-button"),
  hits: document.querySelector("#hits"),
  misses: document.querySelector("#misses"),
  hitRate: document.querySelector("#hit-rate"),
  log: document.querySelector("#log"),
  queues: {
    small: document.querySelector("#small-queue"),
    main: document.querySelector("#main-queue"),
    ghost: document.querySelector("#ghost-queue"),
  },
  counts: {
    small: document.querySelector("#small-count"),
    main: document.querySelector("#main-count"),
    ghost: document.querySelector("#ghost-count"),
  },
};

function normalizeKey(value) {
  return value.trim().slice(0, 2).toUpperCase();
}

function colorFor(key) {
  const total = [...key].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return COLORS[total % COLORS.length];
}

function makeObject(key, counter = 0) {
  return { key, counter };
}

function findIn(queueName, key) {
  return state[queueName].find((item) => item.key === key);
}

function removeGhost(key) {
  state.ghost = state.ghost.filter((item) => item.key !== key);
}

function pushGhost(key, events) {
  removeGhost(key);
  state.ghost.unshift(makeObject(key, 0));
  events.push(`${key} enters G as metadata only.`);
  while (state.ghost.length > CAPACITY.ghost) {
    const evicted = state.ghost.pop();
    events.push(`${evicted.key} leaves G because the ghost FIFO is full.`);
  }
}

function drainSmall(events) {
  while (state.small.length > CAPACITY.small) {
    const victim = state.small.pop();
    if (victim.counter > 0) {
      state.main.unshift(makeObject(victim.key, 0));
      events.push(`${victim.key} had reuse in S, so it is promoted to M with cleared access bits.`);
      drainMain(events);
    } else {
      pushGhost(victim.key, events);
      events.push(`${victim.key} was a one-hit wonder candidate and is quickly demoted from S.`);
    }
  }
}

function drainMain(events) {
  let guard = 0;
  while (state.main.length > CAPACITY.main && guard < 40) {
    guard += 1;
    const victim = state.main.pop();
    if (victim.counter > 0) {
      state.main.unshift(makeObject(victim.key, victim.counter - 1));
      events.push(`${victim.key} was touched in M, so FIFO reinserts it with counter ${victim.counter - 1}.`);
    } else {
      pushGhost(victim.key, events);
      events.push(`${victim.key} is evicted from M into G.`);
    }
  }
}

function accessKey(rawKey) {
  const key = normalizeKey(rawKey);
  if (!key) return;

  const events = [`Request ${key}.`];
  state.lastTouched = key;

  const smallHit = findIn("small", key);
  const mainHit = findIn("main", key);
  if (smallHit || mainHit) {
    const hit = smallHit || mainHit;
    hit.counter = Math.min(3, hit.counter + 1);
    state.hits += 1;
    events.push(`${key} is a cache hit; its two-bit counter becomes ${hit.counter}.`);
    addLog(events);
    render();
    return;
  }

  state.misses += 1;
  const ghostHit = findIn("ghost", key);
  if (ghostHit) {
    removeGhost(key);
    state.main.unshift(makeObject(key, 0));
    events.push(`${key} is found in G, so this miss bypasses S and inserts into M.`);
    drainMain(events);
  } else {
    state.small.unshift(makeObject(key, 0));
    events.push(`${key} is not in G, so it enters the small FIFO S.`);
    drainSmall(events);
  }

  addLog(events);
  render();
}

function addLog(events) {
  const li = document.createElement("li");
  li.textContent = events.join(" ");
  elements.log.prepend(li);
  while (elements.log.children.length > 9) {
    elements.log.lastElementChild.remove();
  }
}

function renderQueue(queueName) {
  const lane = elements.queues[queueName];
  lane.innerHTML = "";
  const isGhost = queueName === "ghost";
  state[queueName].forEach((item) => {
    const object = document.createElement("div");
    object.className = `object ${isGhost ? "ghost-object" : ""} ${item.key === state.lastTouched ? "hit" : ""}`;
    object.style.setProperty("--object-color", colorFor(item.key));
    object.dataset.counter = item.counter;
    object.innerHTML = `${item.key}<small>${isGhost ? "metadata" : `freq ${item.counter}`}</small>`;
    lane.append(object);
  });
  elements.counts[queueName].textContent = `${state[queueName].length} / ${CAPACITY[queueName]}`;
}

function renderTrace() {
  [...elements.traceButtons.children].forEach((button, index) => {
    button.classList.toggle("active", index === state.traceIndex % TRACE.length);
  });
}

function render() {
  renderQueue("small");
  renderQueue("main");
  renderQueue("ghost");
  renderTrace();

  const total = state.hits + state.misses;
  elements.hits.textContent = state.hits;
  elements.misses.textContent = state.misses;
  elements.hitRate.textContent = total === 0 ? "0%" : `${Math.round((state.hits / total) * 100)}%`;

  document.querySelectorAll(".queue-card").forEach((card) => {
    card.classList.remove("pulse");
    void card.offsetWidth;
    if (card.textContent.includes(state.lastTouched)) card.classList.add("pulse");
  });
}

function stepTrace() {
  const key = TRACE[state.traceIndex % TRACE.length];
  elements.input.value = key;
  state.traceIndex += 1;
  accessKey(key);
}

function toggleAuto() {
  if (state.timer) {
    clearInterval(state.timer);
    state.timer = null;
    elements.auto.textContent = "Auto play";
    return;
  }
  elements.auto.textContent = "Pause";
  stepTrace();
  state.timer = setInterval(stepTrace, 1100);
}

function reset() {
  if (state.timer) toggleAuto();
  state.small = [];
  state.main = [];
  state.ghost = [];
  state.hits = 0;
  state.misses = 0;
  state.traceIndex = 0;
  state.lastTouched = null;
  elements.log.innerHTML = "";
  addLog(["Reset simulation. Access an object to begin."]);
  render();
}

function bootstrapTraceButtons() {
  TRACE.forEach((key, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = key;
    button.addEventListener("click", () => {
      state.traceIndex = index + 1;
      elements.input.value = key;
      accessKey(key);
    });
    elements.traceButtons.append(button);
  });
}

elements.request.addEventListener("click", () => accessKey(elements.input.value));
elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter") accessKey(elements.input.value);
});
elements.input.addEventListener("input", () => {
  elements.input.value = normalizeKey(elements.input.value);
});
elements.step.addEventListener("click", stepTrace);
elements.auto.addEventListener("click", toggleAuto);
elements.reset.addEventListener("click", reset);

bootstrapTraceButtons();
reset();
