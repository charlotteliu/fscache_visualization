const DEFAULT_TRACE = "A B C A D E A B F";
const RANDOM_KEYS = "ABCDEFGHIJKL".split("");
const VALID_KEY = /^[A-Za-z0-9_-]{1,8}$/;

const dom = {
  traceInput: document.querySelector("#trace-input"),
  traceError: document.querySelector("#trace-error"),
  stream: document.querySelector("#request-stream"),
  play: document.querySelector("#play-button"),
  pause: document.querySelector("#pause-button"),
  step: document.querySelector("#step-button"),
  previous: document.querySelector("#previous-button"),
  reset: document.querySelector("#reset-button"),
  random: document.querySelector("#random-button"),
  speed: document.querySelector("#speed-select"),
  cacheCapacity: document.querySelector("#cache-capacity"),
  smallRatio: document.querySelector("#small-ratio"),
  ghostCapacity: document.querySelector("#ghost-capacity"),
  frequencyCap: document.querySelector("#frequency-cap"),
  queues: {
    small: document.querySelector("#small-queue"),
    main: document.querySelector("#main-queue"),
    ghost: document.querySelector("#ghost-queue"),
  },
  capacities: {
    small: document.querySelector("#small-capacity"),
    main: document.querySelector("#main-capacity"),
    ghost: document.querySelector("#ghost-capacity-label"),
  },
  motionLayer: document.querySelector("#motion-layer"),
  explanation: document.querySelector("#step-explanation"),
  metrics: {
    total: document.querySelector("#metric-total"),
    hits: document.querySelector("#metric-hits"),
    misses: document.querySelector("#metric-misses"),
    hitRatio: document.querySelector("#metric-hit-ratio"),
    evictions: document.querySelector("#metric-evictions"),
    ghostHits: document.querySelector("#metric-ghost-hits"),
    currentRequest: document.querySelector("#metric-current-request"),
    currentEvent: document.querySelector("#metric-current-event"),
  },
};

const state = {
  trace: [],
  traceIndex: 0,
  pendingActions: [],
  playing: false,
  isAnimating: false,
  animationTimer: null,
  playTimer: null,
  queues: { small: [], main: [], ghost: [] },
  metrics: { total: 0, hits: 0, misses: 0, evictions: 0, ghostHits: 0 },
  currentRequest: "—",
  currentEvent: "Ready",
  explanation: "Press Step to pull the next request from the stream and observe one animation event at a time.",
  highlight: null,
  motion: null,
  history: [],
  config: { smallCapacity: 3, mainCapacity: 7, ghostCapacity: 7, frequencyCap: 3 },
};

function parseTrace(text) {
  const tokens = text.split(/[\s,]+/).map((token) => token.trim()).filter(Boolean);
  const invalid = tokens.filter((token) => !VALID_KEY.test(token));
  if (!tokens.length) return { error: "Trace must contain at least one request key.", trace: [] };
  if (invalid.length) return { error: `Invalid request key: ${invalid[0]}. Use letters, numbers, _ or -, up to 8 characters.`, trace: [] };
  return { error: "", trace: tokens.map((token) => token.toUpperCase()) };
}

function readConfig() {
  const cacheCapacity = clampNumber(dom.cacheCapacity.value, 2, 40, 10);
  const smallRatio = clampNumber(dom.smallRatio.value, 5, 80, 30);
  const smallCapacity = Math.max(1, Math.min(cacheCapacity - 1, Math.round((cacheCapacity * smallRatio) / 100)));
  return {
    smallCapacity,
    mainCapacity: Math.max(1, cacheCapacity - smallCapacity),
    ghostCapacity: clampNumber(dom.ghostCapacity.value, 1, 60, 7),
    frequencyCap: clampNumber(dom.frequencyCap.value, 1, 15, 3),
  };
}

function clampNumber(value, min, max, fallback) {
  const number = Number.parseInt(value, 10);
  if (Number.isNaN(number)) return fallback;
  return Math.max(min, Math.min(max, number));
}

function object(key, frequency = 0) {
  return { key, frequency };
}

function cloneQueues(queues) {
  return {
    small: queues.small.map((item) => ({ ...item })),
    main: queues.main.map((item) => ({ ...item })),
    ghost: queues.ghost.map((item) => ({ ...item })),
  };
}

function makeSnapshot() {
  return {
    traceIndex: state.traceIndex,
    pendingActions: state.pendingActions.map((action) => ({ ...action })),
    queues: cloneQueues(state.queues),
    metrics: { ...state.metrics },
    currentRequest: state.currentRequest,
    currentEvent: state.currentEvent,
    explanation: state.explanation,
    highlight: state.highlight ? { ...state.highlight } : null,
    motion: null,
  };
}

function restoreSnapshot(snapshot) {
  state.traceIndex = snapshot.traceIndex;
  state.pendingActions = snapshot.pendingActions.map((action) => ({ ...action }));
  state.queues = cloneQueues(snapshot.queues);
  state.metrics = { ...snapshot.metrics };
  state.currentRequest = snapshot.currentRequest;
  state.currentEvent = snapshot.currentEvent;
  state.explanation = snapshot.explanation;
  state.highlight = snapshot.highlight ? { ...snapshot.highlight } : null;
  state.motion = null;
}

function rebuildSimulation() {
  pause();
  const parsed = parseTrace(dom.traceInput.value);
  dom.traceError.textContent = parsed.error;
  state.trace = parsed.trace;
  state.traceIndex = 0;
  state.pendingActions = [];
  state.queues = { small: [], main: [], ghost: [] };
  state.metrics = { total: 0, hits: 0, misses: 0, evictions: 0, ghostHits: 0 };
  state.currentRequest = "—";
  state.currentEvent = parsed.error ? "Invalid trace" : "Ready";
  state.explanation = parsed.error || "Press Step to pull the next request from the stream and observe one animation event at a time.";
  state.highlight = null;
  state.motion = null;
  state.config = readConfig();
  state.history = [makeSnapshot()];
  render();
}

function findItem(queues, queueName, key) {
  return queues[queueName].find((item) => item.key === key);
}

function removeGhost(queues, key) {
  queues.ghost = queues.ghost.filter((item) => item.key !== key);
}

function simulatePushGhost(queues, actions, key, reason) {
  removeGhost(queues, key);
  queues.ghost.unshift(object(key, 0));
  if (queues.ghost.length > state.config.ghostCapacity) {
    const dropped = queues.ghost.pop();
    actions.push({ type: "ghostDrop", key: dropped.key, reason });
  }
}

function simulateDrainMain(queues, actions) {
  let guard = 0;
  while (queues.main.length > state.config.mainCapacity && guard < 100) {
    guard += 1;
    const victim = queues.main[queues.main.length - 1];
    if (victim.frequency > 0) {
      queues.main.pop();
      queues.main.unshift(object(victim.key, victim.frequency - 1));
      actions.push({ type: "mainReinsert", key: victim.key, from: victim.frequency, to: victim.frequency - 1 });
    } else {
      queues.main.pop();
      actions.push({ type: "mainToGhost", key: victim.key });
      simulatePushGhost(queues, actions, victim.key, "main eviction");
    }
  }
}

function simulateDrainSmall(queues, actions) {
  while (queues.small.length > state.config.smallCapacity) {
    const victim = queues.small[queues.small.length - 1];
    if (victim.frequency > 0) {
      queues.small.pop();
      queues.main.unshift(object(victim.key, 0));
      actions.push({ type: "smallToMain", key: victim.key, from: victim.frequency });
      simulateDrainMain(queues, actions);
    } else {
      queues.small.pop();
      actions.push({ type: "smallToGhost", key: victim.key });
      simulatePushGhost(queues, actions, victim.key, "small eviction");
    }
  }
}

function planRequest(key) {
  const queues = cloneQueues(state.queues);
  const actions = [{ type: "request", key }];
  const smallHit = findItem(queues, "small", key);
  const mainHit = findItem(queues, "main", key);

  if (smallHit || mainHit) {
    const queue = smallHit ? "small" : "main";
    const hit = smallHit || mainHit;
    const before = hit.frequency;
    hit.frequency = Math.min(state.config.frequencyCap, hit.frequency + 1);
    actions.push({ type: "hit", key, queue, from: before, to: hit.frequency });
    return actions;
  }

  actions.push({ type: "miss", key });
  const ghostHit = findItem(queues, "ghost", key);
  if (ghostHit) {
    removeGhost(queues, key);
    queues.main.unshift(object(key, 0));
    actions.push({ type: "ghostHit", key });
    simulateDrainMain(queues, actions);
    return actions;
  }

  queues.small.unshift(object(key, 0));
  actions.push({ type: "insertSmall", key });
  simulateDrainSmall(queues, actions);
  return actions;
}

function ensurePendingActions() {
  if (state.pendingActions.length) return true;
  if (!state.trace.length || state.traceIndex >= state.trace.length) {
    state.currentEvent = "Complete";
    state.explanation = "The trace is complete. Use Previous Step to review or Reset to run it again.";
    render();
    return false;
  }
  const key = state.trace[state.traceIndex];
  state.traceIndex += 1;
  state.pendingActions = planRequest(key);
  return true;
}

function applyAction(action) {
  state.highlight = null;
  state.motion = null;

  switch (action.type) {
    case "request":
      state.currentRequest = action.key;
      state.currentEvent = "Request";
      state.metrics.total += 1;
      state.highlight = { type: "request", key: action.key };
      state.motion = { type: "request", key: action.key };
      state.explanation = `${action.key} enters from the Request Stream. The simulator now checks Small FIFO, Main FIFO, and then Ghost FIFO.`;
      break;
    case "hit": {
      const item = findItem(state.queues, action.queue, action.key);
      if (item) item.frequency = action.to;
      state.currentEvent = "Hit";
      state.metrics.hits += 1;
      state.highlight = { type: "hit", key: action.key, queue: action.queue };
      state.explanation = `${action.key} was found in the ${queueName(action.queue)}. Its frequency increased from ${action.from} to ${action.to}, but it was not moved because S3-FIFO uses lazy promotion.`;
      break;
    }
    case "miss":
      state.currentEvent = "Miss";
      state.metrics.misses += 1;
      state.highlight = { type: "miss", key: action.key };
      state.explanation = `${action.key} is a cache miss: it is not currently resident in Small FIFO or Main FIFO. The next step decides whether Ghost FIFO remembers it.`;
      break;
    case "insertSmall":
      state.queues.small.unshift(object(action.key, 0));
      state.currentEvent = "Insert Small";
      state.highlight = { type: "insert", key: action.key, queue: "small" };
      state.motion = { type: "insert-small", key: action.key };
      state.explanation = `${action.key} was not found in Ghost FIFO, so it enters the tail of Small FIFO with frequency 0.`;
      break;
    case "smallToMain":
      state.queues.small.pop();
      state.queues.main.unshift(object(action.key, 0));
      state.currentEvent = "Small → Main";
      state.highlight = { type: "move", key: action.key, queue: "main" };
      state.motion = { type: "small-main", key: action.key };
      state.explanation = `${action.key} reached the head of Small FIFO with frequency ${action.from}. Because it was reused, it moves along a curved path into the tail of Main FIFO and its frequency is reset to 0.`;
      break;
    case "smallToGhost":
      state.queues.small.pop();
      pushGhost(action.key);
      state.metrics.evictions += 1;
      state.currentEvent = "Small → Ghost";
      state.highlight = { type: "evict", key: action.key, queue: "ghost" };
      state.motion = { type: "evict-small", key: action.key };
      state.explanation = `${action.key} reached the head of Small FIFO with frequency 0, so it is evicted as a one-hit candidate and recorded in Ghost FIFO as metadata only.`;
      break;
    case "ghostHit":
      removeGhost(state.queues, action.key);
      state.queues.main.unshift(object(action.key, 0));
      state.metrics.ghostHits += 1;
      state.currentEvent = "Ghost Hit";
      state.highlight = { type: "ghost-hit", key: action.key, queue: "main" };
      state.motion = { type: "ghost-main", key: action.key };
      state.explanation = `${action.key} was found in Ghost FIFO. The ghost metadata fades out, and the object enters the tail of Main FIFO because it has shown reuse after eviction.`;
      break;
    case "mainReinsert":
      state.queues.main.pop();
      state.queues.main.unshift(object(action.key, action.to));
      state.currentEvent = "Main Reinsertion";
      state.highlight = { type: "move", key: action.key, queue: "main" };
      state.motion = { type: "main-reinsert", key: action.key };
      state.explanation = `${action.key} reached the head of Main FIFO with frequency ${action.from}. S3-FIFO reinserts it at the tail with frequency ${action.to} instead of evicting it immediately.`;
      break;
    case "mainToGhost":
      state.queues.main.pop();
      pushGhost(action.key);
      state.metrics.evictions += 1;
      state.currentEvent = "Main → Ghost";
      state.highlight = { type: "evict", key: action.key, queue: "ghost" };
      state.motion = { type: "evict-main", key: action.key };
      state.explanation = `${action.key} reached the head of Main FIFO with frequency 0, so it is evicted and remembered in Ghost FIFO.`;
      break;
    case "ghostDrop":
      state.queues.ghost.pop();
      state.currentEvent = "Ghost Eviction";
      state.highlight = { type: "evict", key: action.key, queue: "ghost" };
      state.motion = { type: "evict-ghost", key: action.key };
      state.explanation = `Ghost FIFO exceeded its metadata capacity, so ${action.key} is removed from the ghost history after a ${action.reason}.`;
      break;
    default:
      break;
  }
}

function pushGhost(key) {
  removeGhost(state.queues, key);
  state.queues.ghost.unshift(object(key, 0));
}

function queueName(queue) {
  if (queue === "small") return "Small FIFO";
  if (queue === "main") return "Main FIFO";
  return "Ghost FIFO";
}

function step() {
  if (state.isAnimating || dom.traceError.textContent) return;
  if (!ensurePendingActions()) return;
  const action = state.pendingActions.shift();
  applyAction(action);
  state.history.push(makeSnapshot());
  render();
  lockDuringAnimation();
}

function previousStep() {
  if (state.isAnimating || state.history.length <= 1) return;
  pause();
  state.history.pop();
  restoreSnapshot(state.history[state.history.length - 1]);
  state.currentEvent = state.currentEvent === "Ready" ? "Ready" : `Previous: ${state.currentEvent}`;
  render();
}

function lockDuringAnimation() {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const duration = reduced ? 1 : Math.round(640 / Number.parseFloat(dom.speed.value));
  state.isAnimating = true;
  updateButtonStates();
  window.clearTimeout(state.animationTimer);
  window.clearTimeout(state.playTimer);
  state.animationTimer = window.setTimeout(() => {
    state.isAnimating = false;
    render();
    if (state.playing) state.playTimer = window.setTimeout(step, Math.max(40, duration * 0.35));
  }, duration);
}

function play() {
  if (dom.traceError.textContent) return;
  state.playing = true;
  updateButtonStates();
  if (!state.isAnimating) step();
}

function pause() {
  state.playing = false;
  window.clearTimeout(state.playTimer);
  if (!state.isAnimating) updateButtonStates();
}

function reset() {
  rebuildSimulation();
}

function randomTrace() {
  const length = 14 + Math.floor(Math.random() * 8);
  const trace = Array.from({ length }, () => RANDOM_KEYS[Math.floor(Math.random() * RANDOM_KEYS.length)]);
  dom.traceInput.value = trace.join(" ");
  rebuildSimulation();
}

function render() {
  document.documentElement.style.setProperty("--animation-ms", `${Math.round(640 / Number.parseFloat(dom.speed.value))}ms`);
  renderStream();
  renderQueues();
  renderMetrics();
  renderMotion();
  dom.explanation.textContent = state.explanation;
  updateButtonStates();
}

function renderStream() {
  dom.stream.innerHTML = "";
  state.trace.forEach((key, index) => {
    const token = document.createElement("span");
    token.className = "request-token";
    if (index < state.traceIndex - (state.pendingActions.length ? 1 : 0)) token.classList.add("done");
    if (index === state.traceIndex - 1 && state.pendingActions.length) token.classList.add("active");
    token.textContent = key;
    token.setAttribute("aria-label", `Request ${index + 1}: ${key}`);
    dom.stream.append(token);
  });
}

function renderQueues() {
  renderQueue("small", state.config.smallCapacity);
  renderQueue("main", state.config.mainCapacity);
  renderQueue("ghost", state.config.ghostCapacity);
}

function renderQueue(queue, capacity) {
  const lane = dom.queues[queue];
  lane.innerHTML = "";
  state.queues[queue].forEach((item) => {
    const card = document.createElement("article");
    card.className = "object";
    card.style.setProperty("--object-color", queueColor(queue));
    if (queue === "ghost") card.classList.add("status-ghost");
    if (state.highlight?.key === item.key && state.highlight?.queue === queue) {
      if (state.highlight.type === "hit") card.classList.add("status-hit");
      if (["move", "insert", "ghost-hit"].includes(state.highlight.type)) card.classList.add("status-moving");
      if (state.highlight.type === "evict") card.classList.add("status-evicted");
    }
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-label", `${item.key}, frequency ${item.frequency}, in ${queueName(queue)}`);
    card.innerHTML = `<span class="object-key">${escapeHtml(item.key)}</span><span class="object-frequency">frequency ${item.frequency}</span>`;
    lane.append(card);
  });
  dom.capacities[queue].textContent = `${state.queues[queue].length} / ${capacity}`;
}

function renderMetrics() {
  const total = state.metrics.total;
  dom.metrics.total.textContent = String(total);
  dom.metrics.hits.textContent = String(state.metrics.hits);
  dom.metrics.misses.textContent = String(state.metrics.misses);
  dom.metrics.evictions.textContent = String(state.metrics.evictions);
  dom.metrics.ghostHits.textContent = String(state.metrics.ghostHits);
  dom.metrics.hitRatio.textContent = total ? `${Math.round((state.metrics.hits / total) * 100)}%` : "0%";
  dom.metrics.currentRequest.textContent = state.currentRequest;
  dom.metrics.currentEvent.textContent = state.currentEvent;
  dom.metrics.currentEvent.className = statusClass(state.currentEvent);
}

function renderMotion() {
  dom.motionLayer.innerHTML = "";
  if (!state.motion) return;
  const flyer = document.createElement("div");
  flyer.className = "flying-object";
  flyer.innerHTML = `<span class="object-key">${escapeHtml(state.motion.key)}</span><span class="object-frequency">request</span>`;
  if (state.motion.type.startsWith("evict")) flyer.classList.add("fade-out");
  const position = motionPosition(state.motion.type);
  flyer.style.left = position.left;
  flyer.style.top = position.top;
  dom.motionLayer.append(flyer);
}

function motionPosition(type) {
  const map = {
    request: { left: "48%", top: "-6px" },
    "insert-small": { left: "36%", top: "110px" },
    "small-main": { left: "48%", top: "164px" },
    "ghost-main": { left: "52%", top: "394px" },
    "main-reinsert": { left: "55%", top: "282px" },
    "evict-small": { left: "68%", top: "150px" },
    "evict-main": { left: "68%", top: "282px" },
    "evict-ghost": { left: "68%", top: "414px" },
  };
  return map[type] || { left: "50%", top: "50%" };
}

function statusClass(event) {
  if (/Hit/.test(event)) return "status-text-hit";
  if (/Miss|Eviction|Ghost/.test(event)) return "status-text-ghost";
  if (/Complete|Ready/.test(event)) return "";
  return "";
}

function queueColor(queue) {
  if (queue === "small") return "var(--small)";
  if (queue === "main") return "var(--main)";
  return "var(--ghost)";
}

function updateButtonStates() {
  const invalid = Boolean(dom.traceError.textContent);
  dom.play.disabled = invalid || state.playing || state.traceIndex >= state.trace.length && !state.pendingActions.length;
  dom.pause.disabled = !state.playing;
  dom.step.disabled = invalid || state.isAnimating || state.traceIndex >= state.trace.length && !state.pendingActions.length;
  dom.previous.disabled = state.isAnimating || state.history.length <= 1;
  dom.reset.disabled = state.isAnimating;
  dom.random.disabled = state.isAnimating;
  dom.traceInput.disabled = state.isAnimating;
}

function escapeHtml(value) {
  return value.replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char]));
}

function bindEvents() {
  dom.play.addEventListener("click", play);
  dom.pause.addEventListener("click", pause);
  dom.step.addEventListener("click", step);
  dom.previous.addEventListener("click", previousStep);
  dom.reset.addEventListener("click", reset);
  dom.random.addEventListener("click", randomTrace);
  dom.traceInput.addEventListener("input", rebuildSimulation);
  [dom.cacheCapacity, dom.smallRatio, dom.ghostCapacity, dom.frequencyCap].forEach((input) => {
    input.addEventListener("change", rebuildSimulation);
  });
  dom.speed.addEventListener("change", render);
  document.addEventListener("keydown", (event) => {
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) return;
    if (event.code === "Space") {
      event.preventDefault();
      state.playing ? pause() : play();
    }
    if (event.key === "ArrowRight") step();
    if (event.key === "ArrowLeft") previousStep();
    if (event.key === "Escape") pause();
  });
}

bindEvents();
dom.traceInput.value = DEFAULT_TRACE;
rebuildSimulation();
