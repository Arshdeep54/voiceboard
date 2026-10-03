const examples = {
  code: {
    app: "YOUR CODING AGENT",
    text: "Before we write any code, walk me through how authentication works in this project. Then let’s figure out where the session is getting lost.",
    title: "Better context. Less typing.",
    description:
      "Explain the whole idea, not just the part you feel like typing.",
    footer: "A thought becomes a prompt.",
    number: "01 / 03",
    sample:
      "Before we write any code, walk me through how authentication works in this project.",
  },
  write: {
    app: "YOUR WRITING SPACE",
    text: "The idea came to me on a walk: what if we made the first five minutes feel effortless? Not more features. Just a better place to begin.",
    title: "Catch the thought while it’s here.",
    description:
      "Get the rough draft down. There’s always time to make it beautiful.",
    footer: "A passing thought becomes a first draft.",
    number: "02 / 03",
    sample:
      "What if we made the first five minutes feel effortless? Just a better place to begin.",
  },
  terminal: {
    app: "YOUR LINUX TERMINAL",
    text: "Here’s what I’ve tried so far. The database connection is fine, but the worker stops after the first batch. Can you help me trace what happens next?",
    title: "Keep your cursor where it belongs.",
    description:
      "Dictate context to your terminal agent without switching windows.",
    footer: "Your terminal. With room for the whole story.",
    number: "03 / 03",
    sample:
      "The database connection is fine, but the worker stops after the first batch.",
  },
};

const scene = document.querySelector("#demo");
const text = document.querySelector("#demo-text");
const send = document.querySelector("#demo-send");
const output = document.querySelector("#terminal-output");
const status = document.querySelector("#demo-status");
const hint = document.querySelector("#phone-hint");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
let sampleIndex = 0;

async function sendDemo() {
  if (send.disabled) return;
  const value = text.value.trim();
  if (!value) {
    hint.textContent = "Add a thought before sending";
    text.focus();
    status.textContent = "Enter or load some text before sending.";
    return;
  }
  send.disabled = true;
  scene.classList.add("is-sending");
  hint.textContent = "Sending your thought…";
  status.textContent = "Sending in the browser preview.";
  if (!reducedMotion.matches)
    await new Promise((resolve) => setTimeout(resolve, 550));
  output.textContent = value;
  hint.textContent = "Sent. Your flow, uninterrupted.";
  document.querySelector("#transfer-badge span").textContent =
    "Thought delivered.";
  status.textContent =
    "Your text arrived in the demo terminal. This preview stays in your browser.";
  scene.classList.remove("is-sending");
  send.disabled = false;
}

send.addEventListener("click", sendDemo);
document.querySelector("#demo-mic").addEventListener("click", () => {
  const samples = Object.values(examples).map((example) => example.sample);
  text.value = samples[sampleIndex++ % samples.length];
  hint.textContent = "Sample loaded. Edit it, or send it.";
  status.textContent =
    "An example spoken phrase was loaded. No audio is recorded.";
});
document.querySelector("#try-demo").addEventListener("click", () => {
  scene.scrollIntoView({
    behavior: reducedMotion.matches ? "instant" : "smooth",
    block: "center",
  });
  sendDemo();
});
text.addEventListener("input", () => {
  hint.textContent = "Your words. Ready to send.";
  document.querySelector("#transfer-badge span").textContent =
    "Your devices. Your network.";
});

function wireTabs(selector, activate) {
  const tabs = [...document.querySelectorAll(selector)];
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => {
      tabs.forEach((item) => {
        item.setAttribute("aria-selected", String(item === tab));
        item.tabIndex = item === tab ? 0 : -1;
      });
      activate(tab);
    });
    tab.addEventListener("keydown", (event) => {
      let next;
      if (event.key === "ArrowRight" || event.key === "ArrowDown")
        next = (index + 1) % tabs.length;
      if (event.key === "ArrowLeft" || event.key === "ArrowUp")
        next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      if (next !== undefined) {
        event.preventDefault();
        tabs[next].click();
        tabs[next].focus();
      }
    });
  });
}

wireTabs("[data-case]", (tab) => {
  const example = examples[tab.dataset.case];
  document.querySelector("#example-app").textContent = example.app;
  document.querySelector("#example-text").textContent = example.text;
  document.querySelector("#example-title").textContent = example.title;
  document.querySelector("#example-description").textContent =
    example.description;
  document.querySelector(".example-footer span:first-child").textContent =
    example.footer;
  document.querySelector(".example-footer span:last-child").textContent =
    example.number;
  document.querySelector("#use-panel").setAttribute("aria-labelledby", tab.id);
});

const commands = {
  quick:
    "# Get the source\ngit clone https://github.com/Arshdeep54/voiceboard.git\ncd voiceboard\n\n# Install and start the receiver\n./install.sh\nvoiceboard",
  venv: "# Get the source\ngit clone https://github.com/Arshdeep54/voiceboard.git\ncd voiceboard\n\n# Install in a virtual environment\npython3 -m venv .venv\n.venv/bin/python -m pip install .\n.venv/bin/voiceboard",
};
let installation = "quick";
wireTabs("[data-install]", (tab) => {
  installation = tab.dataset.install;
  const code = document.querySelector("#install-command");
  code.replaceChildren();
  commands[installation].split("\n").forEach((line, index) => {
    if (index) code.append("\n");
    if (line.startsWith("#")) {
      const comment = document.createElement("span");
      comment.className = "code-comment";
      comment.textContent = line;
      code.append(comment);
    } else {
      code.append(line);
    }
  });
  document
    .querySelector("#install-panel")
    .setAttribute("aria-labelledby", tab.id);
  document.querySelector("#copy-status").textContent = "";
  document.querySelector("#copy-command span").textContent = "Copy";
});

document.querySelector("#copy-command").addEventListener("click", async () => {
  const feedback = document.querySelector("#copy-status");
  try {
    await navigator.clipboard.writeText(commands[installation]);
    document.querySelector("#copy-command span").textContent = "Copied";
    feedback.textContent = "Commands copied. Run them in your Linux terminal.";
  } catch {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(document.querySelector("#install-command"));
    selection.removeAllRanges();
    selection.addRange(range);
    feedback.textContent =
      "Commands selected. Press Ctrl+C or copy them manually.";
  }
});
