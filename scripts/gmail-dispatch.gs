/**
 * Timbre de Gmail -> GitHub para la ingesta de extractos por email.
 *
 * Google Apps Script asociado a la cuenta del BUZÓN de la liga. Cada minuto
 * mira si hay correos nuevos con adjunto y, si los hay, dispara el workflow
 * `.github/workflows/inbox.yml` mediante un `repository_dispatch`. Así el
 * extracto se procesa en segundos, sin esperar al cron de GitHub Actions.
 *
 * El script NO lee ni cifra el CSV: solo "llama al timbre". El trabajo de
 * verificar DMARC, cifrar y commitear lo sigue haciendo el workflow por IMAP.
 *
 * ─────────────────────────── INSTALACIÓN (una vez) ───────────────────────────
 *
 * 1. Entra en https://script.google.com CON LA CUENTA DEL BUZÓN de la liga
 *    (la misma de IMAP_USER, p. ej. liga.trader@gmail.com) y crea un proyecto
 *    nuevo. Pega este fichero como código (Código.gs).
 *
 * 2. Crea un token de GitHub de "grano fino" para que el script pueda avisar:
 *      https://github.com/settings/tokens?type=beta
 *    - Repository access: solo el repo de la liga (fedegarlo/trader).
 *    - Permisos: Contents -> Read and write  (lo mínimo para lanzar dispatch).
 *    Este token es del ADMIN y vive solo aquí; los jugadores no necesitan
 *    ninguno. Copia el `github_pat_...`.
 *
 * 3. En el editor: Configuración del proyecto (⚙) -> "Propiedades de la
 *    secuencia de comandos" -> añade estas propiedades:
 *        GH_OWNER = fedegarlo
 *        GH_REPO  = trader
 *        GH_TOKEN = github_pat_...            (el token del paso 2)
 *    (opcional) GH_EVENT = email-recibido    (por defecto ya es este)
 *    (opcional) GMAIL_QUERY = ...            (por defecto: correos no leídos
 *                                             con adjunto sin avisar aún)
 *
 * 4. Instala el disparador de 1 minuto: selecciona la función `createTrigger`
 *    en la barra superior y pulsa ▶ (Ejecutar) UNA vez. Google te pedirá
 *    autorizar el acceso a Gmail y a servicios externos: acéptalo. A partir de
 *    ahí, `checkInbox` corre solo cada minuto.
 *
 * Para comprobar que funciona: envíate un correo con un CSV adjunto (sin
 * abrirlo), espera ~1 min y mira en GitHub -> Actions que se lanza "Ingesta
 * por email". El menú Ejecuciones del editor de Apps Script muestra los logs.
 */

// Cada cuánto revisa el buzón (minutos). Google permite mínimo 1.
var CHECK_EVERY_MINUTES = 1;

// Etiqueta con la que marcamos los hilos ya avisados, para no disparar dos
// veces el mismo correo mientras el workflow lo procesa.
var DISPATCHED_LABEL = 'trader-dispatched';


/** Función que corre en cada tick del disparador. */
function checkInbox() {
  var props = PropertiesService.getScriptProperties();
  var owner = props.getProperty('GH_OWNER');
  var repo = props.getProperty('GH_REPO');
  var token = props.getProperty('GH_TOKEN');
  var eventType = props.getProperty('GH_EVENT') || 'email-recibido';
  if (!owner || !repo || !token) {
    throw new Error('Faltan propiedades GH_OWNER / GH_REPO / GH_TOKEN.');
  }

  // Correos no leídos, con adjunto, que aún no hemos avisado.
  var query = props.getProperty('GMAIL_QUERY') ||
      'is:unread has:attachment -label:' + DISPATCHED_LABEL + ' newer_than:7d';
  var threads = GmailApp.search(query, 0, 25);
  if (!threads.length) return;

  // Un solo dispatch aunque haya varios correos: el workflow lee de golpe
  // TODOS los no vistos del buzón por IMAP.
  triggerDispatch_(owner, repo, token, eventType);

  // Marca los hilos para no volver a dispararlos en el próximo minuto (el
  // workflow tardará unos segundos en marcarlos como leídos por IMAP).
  var label = GmailApp.getUserLabelByName(DISPATCHED_LABEL) ||
      GmailApp.createLabel(DISPATCHED_LABEL);
  for (var i = 0; i < threads.length; i++) threads[i].addLabel(label);
}


/** Lanza el repository_dispatch que activa el workflow de ingesta. */
function triggerDispatch_(owner, repo, token, eventType) {
  var url = 'https://api.github.com/repos/' + owner + '/' + repo + '/dispatches';
  var res = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'Authorization': 'Bearer ' + token,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    },
    payload: JSON.stringify({ event_type: eventType }),
    muteHttpExceptions: true
  });
  var code = res.getResponseCode();
  if (code === 204) {
    console.log('Dispatch enviado a GitHub (' + eventType + ').');
  } else {
    // 401/403 -> token sin permiso Contents; 404 -> owner/repo mal o sin acceso.
    console.error('Dispatch falló: ' + code + ' — ' + res.getContentText());
  }
}


/** Ejecuta esta función UNA vez para instalar el disparador de 1 minuto. */
function createTrigger() {
  var existing = ScriptApp.getProjectTriggers();
  for (var i = 0; i < existing.length; i++) {
    if (existing[i].getHandlerFunction() === 'checkInbox') {
      ScriptApp.deleteTrigger(existing[i]);
    }
  }
  ScriptApp.newTrigger('checkInbox')
      .timeBased()
      .everyMinutes(CHECK_EVERY_MINUTES)
      .create();
  console.log('Disparador instalado: checkInbox cada ' +
      CHECK_EVERY_MINUTES + ' min.');
}
