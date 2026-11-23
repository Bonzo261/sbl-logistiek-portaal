/* Geluid- en trilsignaal voor het SBL Portaal. Eén knop (#geluidknop) per pagina; voorkeur per apparaat. */
window.SBLGeluid = (function () {
  var ctx = null, knop = null, toegestaan = true;
  function aan() { try { return localStorage.getItem('sbl_geluid') === 'aan'; } catch (e) { return false; } }
  function zet(v) { try { localStorage.setItem('sbl_geluid', v ? 'aan' : 'uit'); } catch (e) {} }
  function actief() { return aan() && !!ctx && ctx.state === 'running'; }
  function toon() {
    if (!knop) return;
    knop.hidden = !toegestaan;
    var wacht = aan() && !actief();
    knop.textContent = aan() ? '🔔' : '🔕';
    knop.className = 'ikoon' + (aan() ? ' aan' : '') + (wacht ? ' wacht' : '');
    knop.title = !aan() ? 'Geluid is uit – klik om aan te zetten'
      : wacht ? 'Klik om het geluid te activeren (vereist door de browser)' : 'Geluid is aan – klik om uit te zetten';
    knop.setAttribute('aria-label', knop.title);
  }
  function maakCtx() {
    var C = window.AudioContext || window.webkitAudioContext;
    if (!ctx && C) ctx = new C();
    if (ctx && ctx.resume) ctx.resume();
  }
  function piep() {
    if (!ctx) return;
    [0, 0.28].forEach(function (t, i) {
      var o = ctx.createOscillator(), g = ctx.createGain(), s = ctx.currentTime + t;
      o.type = 'sine'; o.frequency.value = i ? 1100 : 880;
      o.connect(g); g.connect(ctx.destination);
      g.gain.setValueAtTime(0.0001, s);
      g.gain.exponentialRampToValueAtTime(0.4, s + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, s + 0.25);
      o.start(s); o.stop(s + 0.27);
    });
  }
  function klik() {
    if (aan() && actief()) { zet(false); }
    else { zet(true); maakCtx(); setTimeout(piep, 60); }
    toon();
    setTimeout(toon, 300);
  }
  return {
    init: function (opties) {
      knop = document.getElementById('geluidknop');
      toegestaan = !opties || opties.toegestaan !== false;
      if (knop) knop.addEventListener('click', klik);
      toon();
    },
    toegestaan: function (b) { toegestaan = !!b; toon(); },
    /* speelt het signaal als de gebruiker geluid heeft aangezet en geactiveerd */
    signaal: function (trilpatroon) {
      if (toegestaan && actief()) piep();
      if (trilpatroon && navigator.vibrate) { try { navigator.vibrate(trilpatroon); } catch (e) {} }
    },
    actief: actief
  };
})();
