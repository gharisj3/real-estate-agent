const messages = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
let chatState = null;
let history = [];

function addMessage(text, who) {
  const div = document.createElement("div");
  div.className = `msg ${who}`;
  div.textContent = text;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addMessage(text, "user");
  input.value = "";
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, state: chatState, history }),
    });
    if (!res.ok) throw new Error();
    const data = await res.json();
    chatState = data.state || null;
    history.push({ role: "user", content: text }, { role: "assistant", content: data.reply });
    history = history.slice(-20);
    addMessage(data.reply, "bot");
  } catch {
    addMessage("Sorry, something went wrong. Please try again.", "bot");
  }
});

addMessage("Hello! Welcome to PropDesk. How can I help you find a property today?", "bot");
