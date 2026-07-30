---
title: Segnala un errore o dai un suggerimento
description: Segnala errori o proponi miglioramenti — il messaggio arriva direttamente al docente.
---

<style>
.eng-feedback{display:flex;flex-direction:column;gap:14px;max-width:640px;margin:22px 0;}
.eng-feedback .eng-field{display:flex;flex-direction:column;gap:5px;font-size:.92rem;flex:1;}
.eng-feedback .eng-row{display:flex;flex-wrap:wrap;gap:14px;}
.eng-feedback textarea,.eng-feedback input{font:inherit;padding:10px 12px;border:1px solid var(--lightgray);border-radius:8px;background:var(--light);color:var(--dark);width:100%;box-sizing:border-box;}
.eng-feedback textarea:focus,.eng-feedback input:focus{outline:2px solid var(--secondary);border-color:var(--secondary);}
.eng-feedback button{align-self:flex-start;padding:10px 20px;border:0;border-radius:8px;background:var(--secondary);color:#fff;font-weight:700;font-size:1rem;cursor:pointer;}
.eng-feedback button:disabled{opacity:.5;cursor:default;}
.eng-feedback em{color:var(--secondary);font-style:normal;}
#eng-fb-status{margin:0;font-size:.92rem;}
#eng-fb-status.fb-ok{color:#1a7f37;}
#eng-fb-status.fb-err{color:#b00020;}
.eng-privacy{font-size:.86rem;opacity:.75;}
</style>

Hai trovato un **errore**, un refuso, un problema, o hai un **suggerimento** su cosa migliorare o aggiungere? Scrivimi qui sotto — leggo tutti i messaggi.

<form id="eng-feedback-form" class="eng-feedback" autocomplete="off">
  <label class="eng-field">
    <span>Messaggio <em>*</em></span>
    <textarea name="message" rows="6" required placeholder="Es. nell'opera … c'è un refuso / un link rotto / un errore di traduzione…"></textarea>
  </label>
  <div class="eng-row">
    <label class="eng-field">
      <span>Nome <small>(facoltativo)</small></span>
      <input name="name" type="text" placeholder="Come ti chiami">
    </label>
    <label class="eng-field">
      <span>Email <small>(facoltativa, se vuoi risposta)</small></span>
      <input name="email" type="email" placeholder="tua@email.it">
    </label>
  </div>
  <button type="submit">Invia messaggio</button>
  <p id="eng-fb-status" aria-live="polite"></p>
</form>

<p class="eng-privacy">Il messaggio viene inviato al docente via email. Non serve accedere. Nessun dato viene condiviso con terzi.</p>
