// feedbackForm.inline.ts — hydrates the /feedback page form (see preprocess.mjs).
// Fire-and-forget POST to the shared Google Apps Script mail relay (same endpoint the
// sibling Physics/Mathematics sites use): the message is emailed to the teacher. No
// database, no login. The relay returns no CORS headers, so the request is `no-cors`
// and the response is unreadable — we optimistically report success and rely on the
// `page`/`site` fields to tag which site a message came from. Runs on every page but
// no-ops unless the form is present. SPA-safe via the Quartz "nav" event.
const RELAY_URL =
  "https://script.google.com/macros/s/AKfycbz86Y3_ReFHapwpv8N6A7xBWm-yFhTFSkjt8JryOwnrs5JtQyybGX_yb_ekEUP2GFmt/exec"
const RELAY_TOKEN = "fl_msg_2026"

function initFeedbackForm() {
  const form = document.getElementById("eng-feedback-form") as HTMLFormElement | null
  if (!form || form.dataset.bound === "1") return
  form.dataset.bound = "1"

  form.addEventListener("submit", (ev) => {
    ev.preventDefault()
    const status = document.getElementById("eng-fb-status")
    const msgField = form.querySelector<HTMLTextAreaElement>('[name="message"]')
    const msg = (msgField?.value || "").trim()
    if (!status) return
    if (!msg) {
      status.textContent = "Scrivi un messaggio."
      status.className = "fb-err"
      return
    }
    const name = form.querySelector<HTMLInputElement>('[name="name"]')?.value || ""
    const email = form.querySelector<HTMLInputElement>('[name="email"]')?.value || ""
    const btn = form.querySelector<HTMLButtonElement>('button[type="submit"]')
    if (btn) btn.disabled = true
    status.textContent = "Invio…"
    status.className = ""

    fetch(RELAY_URL, {
      method: "POST",
      mode: "no-cors",
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify({
        token: RELAY_TOKEN,
        site: "letteratura-inglese",
        message: msg,
        name,
        email,
        page: location.href,
      }),
    })
      .then(() => {
        status.textContent = "Messaggio inviato — grazie!"
        status.className = "fb-ok"
        form.reset()
      })
      .catch((e) => {
        status.textContent = "Errore nell'invio: " + (e && e.message ? e.message : e)
        status.className = "fb-err"
      })
      .then(() => {
        if (btn) btn.disabled = false
      })
  })
}

document.addEventListener("nav", initFeedbackForm)
initFeedbackForm()

export {}
