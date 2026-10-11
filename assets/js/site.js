/* Small enhancements. The site works without this file. */
(function () {
  'use strict';

  // Menu button on narrow screens.
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.getElementById('site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', open ? 'false' : 'true');
      nav.classList.toggle('is-open', !open);
    });
  }

  // Videos: the page shows a still picture. A click swaps in the YouTube player,
  // so nothing is loaded from YouTube's player until the visitor asks for it.
  document.addEventListener('click', function (event) {
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    var link = event.target.closest ? event.target.closest('a[data-youtube]') : null;
    if (!link) return;
    event.preventDefault();
    var frame = document.createElement('iframe');
    frame.src = 'https://www.youtube-nocookie.com/embed/' +
      encodeURIComponent(link.getAttribute('data-youtube')) + '?autoplay=1&rel=0';
    frame.title = (link.getAttribute('aria-label') || 'YouTube video').replace(/^Play video:?\s*/, '') || 'YouTube video';
    frame.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
    frame.allowFullscreen = true;
    frame.referrerPolicy = 'strict-origin-when-cross-origin';
    link.parentNode.replaceChild(frame, link);
    frame.focus();
  });
})();
