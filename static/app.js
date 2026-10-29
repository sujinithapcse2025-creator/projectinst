(() => {
  const body = document.body;
  const voiceAllowed = body.dataset.voice === "on";
  const langMap = {"English":"en-IN", "தமிழ் (Tamil)":"ta-IN", "हिन्दी (Hindi)":"hi-IN"};

  function speak(text) {
    if (!voiceAllowed || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(String(text || ""));
    utterance.lang = langMap[body.dataset.language] || "en-IN";
    utterance.rate = 0.92;
    window.speechSynthesis.speak(utterance);
  }

  document.querySelectorAll("[data-speak]").forEach((button) => {
    button.addEventListener("click", () => speak(button.dataset.speak));
  });

  const range = document.getElementById("font-size");
  const output = document.getElementById("font-output");
  if (range && output) {
    range.addEventListener("input", () => { output.value = `${range.value}px`; output.textContent = `${range.value}px`; });
  }

  const assistantForm = document.getElementById("assistant-form");
  const replyBox = document.getElementById("assistant-reply");
  if (assistantForm && replyBox) {
    assistantForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const command = document.getElementById("assistant-command").value.trim();
      if (!command) { replyBox.textContent = "Please type a question or use the microphone button."; return; }
      const token = assistantForm.querySelector('[name="_csrf"]').value;
      replyBox.textContent = "Thinking…";
      try {
        const response = await fetch("/api/assistant", {
          method: "POST",
          headers: {"Content-Type": "application/json", "X-CSRF-Token": token},
          body: JSON.stringify({command})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || "Request failed");
        replyBox.textContent = data.reply;
        speak(data.reply);
      } catch (_) {
        replyBox.textContent = "The helper could not respond. Please refresh the page and try again.";
      }
    });
  }

  const voiceButton = document.getElementById("voice-input");
  if (voiceButton) {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      voiceButton.disabled = true;
      voiceButton.title = "Speech recognition is not available in this browser. You can type instead.";
      voiceButton.textContent = "🎙 Voice input unavailable";
    } else {
      voiceButton.addEventListener("click", () => {
        const recognition = new Recognition();
        recognition.lang = langMap[body.dataset.language] || "en-IN";
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;
        voiceButton.disabled = true;
        voiceButton.textContent = "Listening…";
        recognition.onresult = (event) => {
          document.getElementById("assistant-command").value = event.results[0][0].transcript;
          assistantForm.requestSubmit();
        };
        recognition.onerror = () => { replyBox.textContent = "Voice input was not understood. Please type your question instead."; };
        recognition.onend = () => { voiceButton.disabled = false; voiceButton.textContent = "🎙 Speak"; };
        recognition.start();
      });
    }
  }
})();
