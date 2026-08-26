(function () {
  'use strict';

  // Fußzeile: aktuelles Jahr
  var jahrEl = document.getElementById('jahr');
  if (jahrEl) jahrEl.textContent = new Date().getFullYear();

  // Mobile Navigation
  var navToggle = document.getElementById('navToggle');
  var mainNav = document.getElementById('mainNav');
  if (navToggle && mainNav) {
    navToggle.addEventListener('click', function () {
      var isOpen = mainNav.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });
    mainNav.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        mainNav.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  // Statusmeldung nach Formular-Redirect anzeigen (?status=success / ?status=error / ?status=spam)
  var formMessage = document.getElementById('formMessage');
  if (formMessage) {
    var params = new URLSearchParams(window.location.search);
    var status = params.get('status');
    var messages = {
      success: { text: 'Vielen Dank für Ihre Anfrage! Wir melden uns zeitnah bei Ihnen.', cls: 'success' },
      error: { text: 'Beim Senden ist ein Fehler aufgetreten. Bitte prüfen Sie Ihre Angaben oder kontaktieren Sie uns telefonisch.', cls: 'error' },
      spam: { text: 'Ihre Anfrage konnte nicht verarbeitet werden.', cls: 'error' }
    };
    if (status && messages[status]) {
      formMessage.textContent = messages[status].text;
      formMessage.classList.add('show', messages[status].cls);
      formMessage.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  // Client-seitige Vorab-Prüfung des Foto-Uploads (Server prüft zusätzlich verbindlich)
  var fotoInput = document.getElementById('fotos');
  var anfrageForm = document.getElementById('anfrageForm');
  var MAX_FILES = 5;
  var MAX_SIZE = 5 * 1024 * 1024; // 5 MB
  var ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/heic', 'application/pdf'];

  if (fotoInput && anfrageForm) {
    anfrageForm.addEventListener('submit', function (e) {
      var files = fotoInput.files;
      if (!files || files.length === 0) return;

      if (files.length > MAX_FILES) {
        e.preventDefault();
        alert('Bitte maximal ' + MAX_FILES + ' Dateien hochladen.');
        return;
      }

      for (var i = 0; i < files.length; i++) {
        var file = files[i];
        if (file.size > MAX_SIZE) {
          e.preventDefault();
          alert('Die Datei "' + file.name + '" ist größer als 5 MB.');
          return;
        }
        var typeOk = ALLOWED_TYPES.indexOf(file.type) !== -1;
        var extOk = /\.(jpe?g|png|heic|pdf)$/i.test(file.name);
        if (!typeOk && !extOk) {
          e.preventDefault();
          alert('Die Datei "' + file.name + '" hat ein nicht erlaubtes Format. Erlaubt: JPG, PNG, HEIC, PDF.');
          return;
        }
      }
    });
  }
})();
