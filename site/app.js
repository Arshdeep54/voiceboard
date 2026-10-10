const examples = {
  code: {
    app: "YOUR CODING AGENT",
    text: "Walk me through authentication, then trace where the session is lost.",
    title: "A complete prompt, in one go.",
    number: "01 / 03",
    sample: "Walk me through authentication, then trace where the session is lost.",
  },
  write: {
    app: "YOUR WRITING SPACE",
    text: "What would make the first five minutes feel effortless?",
    title: "Capture a first draft.",
    number: "02 / 03",
    sample: "What would make the first five minutes feel effortless?",
  },
  terminal: {
    app: "YOUR LINUX TERMINAL",
    text: "The worker stops after its first batch. Help me trace why.",
    title: "Keep context in the terminal.",
    number: "03 / 03",
    sample: "The worker stops after its first batch. Help me trace why.",
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
  hint.textContent = "Updating preview…";
  status.textContent = "Updating the browser preview.";
  if (!reducedMotion.matches)
    await new Promise((resolve) => setTimeout(resolve, 550));
  output.textContent = value;
  hint.textContent = "Preview updated.";
  document.querySelector("#transfer-badge span").textContent =
    "Nothing leaves this page.";
  status.textContent =
    "Your text appears in this browser preview only. Nothing was sent.";
  scene.classList.remove("is-sending");
  send.disabled = false;
}

send.addEventListener("click", sendDemo);
document.querySelector("#demo-mic").addEventListener("click", () => {
  const samples = Object.values(examples).map((example) => example.sample);
  text.value = samples[sampleIndex++ % samples.length];
  hint.textContent = "Sample loaded. Edit it or preview it.";
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
  hint.textContent = "Your text. Ready to preview.";
  document.querySelector("#transfer-badge span").textContent =
    "Nothing leaves this page.";
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
  document.querySelector(".example-footer span").textContent =
    example.number;
  document.querySelector("#use-panel").setAttribute("aria-labelledby", tab.id);
});

const installCommand = "pipx install voiceboard\nvoiceboard";

document.querySelector("#copy-command").addEventListener("click", async () => {
  const feedback = document.querySelector("#copy-status");
  try {
    await navigator.clipboard.writeText(installCommand);
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
