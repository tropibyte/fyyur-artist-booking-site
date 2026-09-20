window.parseISOString = function parseISOString(s) {
  var b = s.split(/\D+/);
  return new Date(Date.UTC(b[0], --b[1], b[2], b[3], b[4], b[5], b[6]));
};

/**
 * Delete buttons on the venue and artist pages.
 *
 * The endpoints answer HTTP DELETE, which a plain <form> cannot send, so the
 * click goes out through fetch() carrying the CSRF token from the page's meta
 * tag.  fetch() will not follow a redirect on the user's behalf, so the server
 * replies with the URL to visit next and we navigate there.
 */
document.addEventListener('DOMContentLoaded', function () {
  var token = document.querySelector('meta[name="csrf-token"]');
  var csrfToken = token ? token.getAttribute('content') : '';

  document.querySelectorAll('.delete-record').forEach(function (button) {
    button.addEventListener('click', function (event) {
      event.preventDefault();

      var name = button.dataset.name || 'this record';
      if (!window.confirm('Delete ' + name + '? This also removes its shows.')) {
        return;
      }

      button.disabled = true;
      fetch(button.dataset.url, {
        method: 'DELETE',
        headers: {
          'X-CSRFToken': csrfToken,
          'Content-Type': 'application/json'
        },
        credentials: 'same-origin'
      })
        .then(function (response) {
          return response.json().then(function (body) {
            return { ok: response.ok, body: body };
          });
        })
        .then(function (result) {
          if (result.ok && result.body.success) {
            window.location.href = result.body.redirect || '/';
          } else {
            button.disabled = false;
            window.alert('Could not delete ' + name + '. Please try again.');
          }
        })
        .catch(function () {
          button.disabled = false;
          window.alert('Could not reach the server. Please try again.');
        });
    });
  });
});
