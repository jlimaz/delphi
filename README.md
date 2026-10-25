<p align="center"><img src="docs/banner.png" alt="Delphi. Your whole Mac, one sentence away." width="100%"></p>

<p align="center">
  Hold <kbd>⌃ control</kbd> <kbd>⌥ option</kbd> <kbd>space</kbd>, say what you need, let go.<br>
  Delphi moves your windows, finds your files, reads your screen and gets it done.
</p>

<p align="center"><a href="https://ko-fi.com/saarthr"><b>☕ Leave a tip</b></a> · Delphi is free; tips keep it going.</p>

<p align="center">
  <b>🧠 Learns as you use it</b> &nbsp;·&nbsp; <b>⚡ Fast</b> &nbsp;·&nbsp; <b>🔑 No API key</b> &nbsp;·&nbsp; <b>Free and open source</b>
</p>

## Quick install

```
curl -fsSL https://raw.githubusercontent.com/SaarthurR/atticus-mac/main/install.sh | bash
```

Needs macOS 26 and an AI client: Claude Code on a Claude plan, Devin, Pi or a local model. [Full install steps](#install)

## What it does

- **Learns.** Ask for something new once and it works out the steps. Ask again and it runs in a blink, with no AI.
- **Instant commands.** Opens apps, moves windows, plays music and searches the web with no AI at all.
- **Sees your screen.** Ask about anything on screen. Ask "where do I click?" and it points at the spot.
- **Draws to explain.** "Explain this and draw it" builds a labeled diagram on your screen.
- **Dictate anywhere.** Hold fn, talk, let go. Your words land in any text field, cleaned up.
- **Remembers you.** Say "remember…" and every ask after that knows it.
- **Your plan, no API key.** Runs on Claude, Devin, Pi or a local model.
- **Private and safe.** Your voice stays on your Mac. Deletes, sends and purchases ask first.

> **On Windows?** [@FindlayHi](https://github.com/FindlayHi) built **[Atticus for Windows](https://github.com/FindlayHi/atticus-windows)**, with integrations for Home Assistant, Jellyfin, Immich and more.

<p align="center">
  <img alt="macOS" src="https://img.shields.io/badge/macOS-1d1d1f?style=for-the-badge&logo=apple&logoColor=white">
  <img alt="Swift" src="https://img.shields.io/badge/Swift-1d1d1f?style=for-the-badge&logo=swift&logoColor=white">
  <img alt="Claude" src="https://img.shields.io/badge/Claude_Haiku-1d1d1f?style=for-the-badge&logo=anthropic&logoColor=white">
  <img alt="Cost" src="https://img.shields.io/badge/~0.18%C2%A2_per_ask-1d1d1f?style=for-the-badge">
  <a href="https://ko-fi.com/saarthr"><img alt="Support on Ko-fi" src="https://img.shields.io/badge/Support_on_Ko--fi-1d1d1f?style=for-the-badge&logo=kofi&logoColor=white"></a>
</p>

<br>

https://github.com/user-attachments/assets/26822ad2-6281-477d-b676-2f490a4a207b

<br>

## Just ask

| You say | Delphi |
|---|---|
| *"Code on my big screen, Chrome and Terminal on the laptop."* | Arranges three windows across two displays. |
| *"Open Spotify."* · *"Terminal on the left."* | Runs instantly, with no AI at all. |
| *"Find my notes about the Tokyo trip."* | Searches your files by what's inside them, opens the match on your other screen. |
| *"What's wrong with this code?"* | Looks at your screen and answers in a line. |
| *"Reply to this. Thursday works, send me a time."* | Reads the email on screen and writes the reply. Insert puts it at your cursor. It never sends. |
| *"Move my dentist appointment to 4."* | Shows the old and new time on a card and moves it when you approve. Adding is immediate; moving or deleting asks first. |
| *"Tell the agent in my terminal to also run the tests."* | Types it into that window in the background while you keep working. If it can't confirm the send, it leaves the text there and asks for the window. |
| *"Find me a desk lamp under $30 on Amazon."* | Works in Chrome behind your apps; a live mini screen shows it. |
| *"Where do I turn on Night Shift?"* | A ring lights up the exact spot on your screen (Show me where). |
| *"Summarize this article in three bullets."* | Reads the page for you. |
| *"Play my late night coding playlist on Spotify."* | Plays it in a second, no clicks. Any song, artist or playlist. |
| *"When I say focus mode, close Slack and open my to-do list."* | Remembers it. Next time, two words do it all. |

<p align="center"><img src="docs/demo.gif" alt="Delphi arranging windows across two screens" width="820"></p>

## Safe by default

Safe mode runs the AI's commands in Claude Code's sandbox, so they can only write to a scratch folder. Before anything deletes, sends, buys or changes a file, Delphi asks you first. <code>rm</code>, <code>sudo</code>, disk tools and shutdown are always blocked. Every exact command is in the ask log. Apple's on-device speech turns your voice into text, and audio never leaves your Mac.

<details>
<summary><b>How the shortcut and the box work</b></summary>
<br>

Choose **Hold to talk** or **Press to toggle** in Settings → General → Shortcut behavior. Hold mode sends when you release. Toggle mode starts on the first press and sends on the second; pauses keep listening. Pressing the shortcut while Delphi answers stops it; during spoken playback it stops the voice. Esc cancels listening without sending. Toggle recordings reach a review screen after 60 seconds, rather than sending automatically. Closing the overlay or pausing Delphi stops its microphone, workers and voice.

Click any answer to copy it, including earlier answers still shown in the box. Click your request to edit and ask again, or press ↑ in an empty typing box to recall the latest request. The overlay stays within your display when resized and respects Reduce Motion. While Delphi works in a covered window, another Space, or another display, a live mini screen shows that window; the steps below show the action. The finished view stays until the next ask, typing, or a click on it. Click it to open that exact window. The preview stays on your Mac, is never sent to the AI or saved, and stops streaming when the task ends. Without Screen Recording permission, the same card shows the app icon and window title.

Apple's final transcript confirms each voice request before AI tools or learned shortcuts run. AI reasoning can start during a pause, but its tools wait for confirmation. If speech finalization takes too long, Delphi offers the partial text for review. Instant commands still skip the AI entirely. Supported built-in commands run mid-sentence, before you send. Learned shortcuts wait for confirmed words.

When Delphi acts but can't see the result, it says so ("…but I couldn't confirm the result") and doesn't learn that shortcut. Try again checks what already happened before it acts again.

</details>

## Dictate anywhere

Hold fn to talk. Double-tap to lock. In any text field, hold the fn (🌐) key, speak, then let go. Double-tap it to lock dictation on for hands-free talking; an orange ring circles the pill, and one more press inserts. fn is the shortcut until you record another in Settings → Dictation (a key combo, an F-key, or a modifier chord like fn+Control); a shortcut you already set stays. If macOS's "Press 🌐 key to" setting opens emoji, switches input source or starts Apple dictation, Settings and setup show "Set Press 🌐 key to Do Nothing" with a button to Keyboard settings. fn with another key (fn+Delete, fn+←) stays that key's shortcut. While you talk, a small pill shows a sound wave. The Dictation tab shows your words today and all time, time saved, sessions, your dictionary and history. **Verbatim** types Apple's on-device transcript with no AI. **Clean up** makes one quick AI pass that keeps your words, fixes words it clearly misheard ("talk it and it' type" becomes "talk to it and it'll type"), and drops the slips: "um" and "you know" go, "scratch that" removes the thought before it, "four, actually five" leaves five, a spoken list becomes a list, and "new line" or "question mark" become formatting. It types what you dictate and never answers or acts on it. To spell names and terms it uses your Dictionary and the text just before your cursor. It starts while you talk, so the text lands soon after you let go; if the AI's version adds or drops too much, Delphi types your words with only the obvious fillers removed. Highlight text first and Clean up tidies that text in place. Esc cancels. When the words land, the pill turns into a green check and fades. With no text field selected, it says "Nothing selected to insert — saved to History." Dictation never leaves your words on the clipboard: if a field only takes a paste, Delphi borrows the clipboard for that one paste and puts back what you had copied. If the field changes or Delphi can't confirm the words landed, it saves them to Dictation History and says "Saved to History" instead of typing twice; with History off, the words stay in the pill.

## Draw on screen

Ask where to click or how to do something and Delphi shows you instead of only telling you: it draws boxes, circles, arrows and labels over your screen, with a pointer that moves to each spot. It goes one step at a time and moves on when you click the highlighted spot, change that value, or say "next".

Ask it to explain something and draw it ("explain the Pythagorean theorem and draw it on my screen") and the drawing builds up like a whiteboard: each step adds to the last, and a card in the opposite corner keeps every caption so far. It moves through the steps by itself. It works from what you have open: with a video, page or problem on screen, it marks up that figure and uses its numbers, unless you ask for a fresh example. Drawings go on the screen where you asked (the one with the Delphi box) unless you name another. Worked examples and practice problems are written line by line in large text on one panel, readable from your chair on a laptop or a monitor.

The drawing stays while you keep asking about it, and Delphi can add to it; it changes only when an answer draws something new. Click any mark (a box, an arrow, a label, a line of text) to select it, then ask "how does this work?": the question carries that mark and a picture of it. While a drawing is up, the Delphi box moves out of its way and comes back when it's gone. Close the card or press Esc to clear it. Steps are spoken only when Read answers aloud is on. The drawings never take focus, and clicks pass through everywhere except on a mark. Turn it off in Settings → General → Draw on screen to show you.

## Model choice

In Settings → Intelligence, choose **Cheapest**, **Balanced** (the default) or **Most capable**. Cheapest keeps every ask on Haiku. Balanced keeps questions and quick commands on Haiku and gives real work to your work model; if a task turns multi-step, fails, or ends without a confirmed result, it continues once on the work model. Most capable uses the work model for every AI ask. Instant commands skip the AI in every mode. **Work model** picks Sonnet or Opus; Opus is stronger and uses more of your plan.

With a custom server connected, Delphi uses that server's model.

## Use a local model

Delphi can send Claude Code to a local server that implements the Anthropic Messages API. Claude Code must be installed, but you do not need a Claude account.

1. Start a server and load a model:

   | Server | Version with `/v1/messages` | Default address |
   |---|---:|---|
   | Ollama | 0.14.0+ | `http://localhost:11434` |
   | LM Studio | 0.4.1+ | `http://localhost:1234` |
   | llama.cpp `llama-server` | builds after Nov 28, 2025 | `http://localhost:8080` |
   | vLLM | 0.11.1+ | `http://localhost:8000` |

   Ollama starts with `ollama serve`; LM Studio uses `lms server start --port 1234`; llama.cpp uses `llama-server -m /path/to/model.gguf`; vLLM uses `vllm serve <model>`.
2. Open setup → **Change provider** → **Custom server**, or Settings → Intelligence → **Custom server**. If a server is on a default port, Delphi offers **Use Ollama**, **Use LM Studio**, **Use llama.cpp**, or **Use vLLM**.
3. Leave Key empty for an unauthenticated local server. Pick a model from the list Delphi reads from `GET /v1/models`, then ask normally.

Small local models are usually weaker at reliable tool use and following long screen context. Screen reading also needs a vision-capable model; text-only models can still use accessible window and page text.

## Pi and Devin

Pi and Devin handle asks just like Claude. Pi has no built-in sandbox, so Delphi disables its direct file-edit and MCP tools and Safe mode asks before every shell command; its read tools still have your account’s file access.

## Feedback

Choose **Report Feedback…** in the menu bar, **Report feedback** in Settings, or say/type “report feedback” or “report a bug”. Review the exact text before opening a GitHub issue draft. It contains a short template, version/commit, macOS and Mac model, model, safe mode and input settings. **Include my last ask** starts off; answers, screen content and command logs are never attached. Submit the draft yourself on GitHub.

## Install

You need:
- **macOS 26** or later (Delphi uses Apple's new on-device speech)
- **An AI client:** a paid Claude plan (Pro or Max) and [Claude Code](https://claude.com/claude-code), the [Devin CLI](https://docs.devin.ai/cli) signed in to a Devin plan, [Pi](https://pi.dev) with your chosen provider/model, or a custom server through Claude Code with no Claude account. Pick one in setup (“Change provider”) or Settings → Intelligence.
- Apple's command line tools: `xcode-select --install`
- Accessibility permission enables native clicks, scrolling, menus, keys, dragging and field typing.

Paste this in Terminal:

```
curl -fsSL https://raw.githubusercontent.com/SaarthurR/atticus-mac/main/install.sh | bash
```

It checks your Mac, downloads Delphi to `~/.delphi`, builds `~/Applications/Delphi.app`, and opens it. Delphi starts at login and updates itself from there (turn that off in Settings → About & Updates).

### Nix

On macOS with Nix flakes enabled:

```bash
nix run github:SaarthurR/atticus-mac
```

The flake installs its packaged Delphi version, so macOS 26+ and Apple's command line tools are still required. Run that command again to update. `nix profile add github:SaarthurR/atticus-mac` installs a `delphi` launcher; update it with `nix profile upgrade delphi`, then run `delphi`. Nix installations show this update path in Settings instead of using Delphi's Git updater.

Working on the code instead? Clone the repo anywhere and run `./build.sh` after each change. A Devbox environment is included for Python regression tests; run `devbox shell`, then `devbox run test`.

The first launch opens a setup window. It checks your AI plan, then asks for each macOS permission.
After that, Delphi lives in the menu bar. Open it from Spotlight (⌘Space, "Delphi") for Settings: shortcut, voice, model, privacy and memory. Settings and setup follow your Mac's light or dark appearance.
If you sign out of your AI client later, the setup window comes back by itself.
To see it again: `defaults delete com.delphi.app onboarded`, then restart the app.

Test: `python3 delphi.py --selftest` on macOS, plus `python3 -m unittest discover -s tests -v` for offline regressions. After building, `~/Applications/Delphi.app/Contents/MacOS/Delphi --selftest` checks native transcript matching without opening the app. Node, when installed, also checks embedded JavaScript syntax. For the UI interaction checks, run `python3 -m http.server 8765 --bind 127.0.0.1` from the repo and open `http://127.0.0.1:8765/tests/ui.html`; it uses a mock native bridge and makes no Mac actions or AI calls.

Remove: `launchctl bootout gui/$(id -u)/com.delphi.app`, then delete `~/Applications/Delphi.app`, `~/.delphi`, `~/.config/delphi` (your settings and history) and `~/Library/LaunchAgents/com.delphi.app.plist`.

## Watch for me

Say "tell me when Codex is done" or "watch this page until it says shipped". Delphi sets it up once, then checks every 5 seconds on your Mac with no AI, so waiting is free. When it fires you get a notification, and it runs a follow-up if you asked for one. A window must stay open on this desktop (covered is fine). Coding agents like Codex are watched through their own log, with no screen at all. Say "stop watching" to cancel.

## Budget

Delphi has to stay fast and nearly free, so new features must fit under these limits:

- Instant commands: no AI, $0.
- AI asks: median under $0.002 and 6 s over the last 50 (Oct 10, 2026: $0.00095, 5.0 s). Check with `python3 delphi.py --budget`.
- System prompt: under 10,000 characters in source and at most 10,050 with the installed helper path. Every ask pays for it, and tests enforce both limits.
- Anything that waits or runs in the background: $0 while it waits. AI only to set it up and to act at the end.

## Anonymous usage

Delphi sends a random ID (made on your Mac, not tied to you) with daily use, ask outcomes, feature names, timings, dictation outcomes, and code locations for errors. It never sends task text, dictated words, file contents, paths, or screen content. Turn it off in Settings → Account & Access → Count me as a user.

If you say yes to **Help improve Delphi** (asked once, off until you do), a task that fails sends what you asked, the steps Delphi took and why it failed, under the same random ID. Emails, numbers, file paths, link details and anything typed for you are removed on your Mac first. Turn it off in Settings → Account & Access → Help improve Delphi.

## Files

- `Delphi.swift`: the app (hotkey, speech, overlay, onboarding window)
- `delphi.py`: the brain (fast commands, system prompt, helpers for windows, web and screen)
- `ui/ui.html`, `ui/onboarding.html`, `ui/settings.html`: the overlay, the welcome flow, and Settings
- `ui/AppIcon.icns`: the app icon
- `ui/orbs.js`: the [thinking-orbs](https://github.com/Jakubantalik/thinking-orbs) engine (MIT, Jakub Antalik)

## License

MIT. See `LICENSE`. `ui/orbs.js` is from [thinking-orbs](https://github.com/Jakubantalik/thinking-orbs), also MIT.

## Contributing

Run regressions with a scratch `DELPHI_DIR` and use `tests/ui.html` and `tests/settings.html` for mock-bridge UI checks. Keep personal settings, credentials and runtime state out of commits. Anonymous usage telemetry uses a public PostHog capture token. Set `DELPHI_POSTHOG_KEY` to override it (an empty value disables telemetry), or turn off Count me as a user in Settings.

Hands: ideas and some logic adapted from Plip (github.com/hussainn7/plip-oss, MIT). Background key authentication and menu-shortcut presses follow Cua Driver (github.com/trycua/cua, MIT).
