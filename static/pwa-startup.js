// Early PWA startup helpers.
// Runs before the main UI bundle so installed launches can paint with the
// correct native-like classes and capture browser install events early.
(function(){
  'use strict';
  var root=document.documentElement;

  function mql(query){
    try{return window.matchMedia&&window.matchMedia(query).matches;}catch(_){return false;}
  }
  function isStandalone(){
    return window.navigator.standalone===true ||
      mql('(display-mode: standalone)') ||
      mql('(display-mode: fullscreen)') ||
      mql('(display-mode: window-controls-overlay)');
  }
  function isIOS(){
    return /iPad|iPhone|iPod/.test(window.navigator.userAgent||'') ||
      (window.navigator.platform==='MacIntel' && window.navigator.maxTouchPoints>1);
  }
  // The installed shell locks zoom; a browser tab must not.
  //
  // A standalone PWA that allows pinch-zoom rubber-bands like a web page instead
  // of behaving like an app, so the locked viewport is right there. It is wrong
  // in a normal tab, where blocking zoom is an accessibility failure. The meta
  // tag is static markup, so the only way to make it conditional is to rewrite it
  // once display mode is known — which is exactly what this file exists to do.
  var VIEWPORT_BROWSER='width=device-width, initial-scale=1, viewport-fit=cover';
  var VIEWPORT_STANDALONE='width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover';
  function syncViewportZoom(standalone){
    try{
      var meta=document.querySelector('meta[name="viewport"]');
      if(!meta) return;
      var want=standalone?VIEWPORT_STANDALONE:VIEWPORT_BROWSER;
      if(meta.getAttribute('content')!==want) meta.setAttribute('content',want);
    }catch(_){}
  }

  function syncMode(){
    var standalone=isStandalone();
    syncViewportZoom(standalone);
    root.classList.toggle('pwa-standalone',standalone);
    root.classList.toggle('pwa-browser',!standalone);
    root.classList.toggle('pwa-ios',isIOS());
    root.classList.toggle('pwa-offline',window.navigator.onLine===false);
    root.dataset.pwaDisplayMode=standalone?'standalone':'browser';
    return standalone;
  }
  function dispatch(name,detail){
    try{window.dispatchEvent(new CustomEvent(name,{detail:detail||{}}));}catch(_){}
  }

  syncMode();
  window.addEventListener('online',function(){syncMode();dispatch('hermes:pwa-connection-change',{online:true});});
  window.addEventListener('offline',function(){syncMode();dispatch('hermes:pwa-connection-change',{online:false});});
  if(window.matchMedia){
    ['(display-mode: standalone)','(display-mode: fullscreen)','(display-mode: window-controls-overlay)'].forEach(function(query){
      try{
        var media=window.matchMedia(query);
        var handler=function(){syncMode();};
        if(media.addEventListener)media.addEventListener('change',handler);
        else if(media.addListener)media.addListener(handler);
      }catch(_){}
    });
  }

  window.addEventListener('beforeinstallprompt',function(event){
    event.preventDefault();
    window.hermesDeferredInstallPrompt=event;
    root.classList.add('pwa-installable');
    dispatch('hermes:pwa-installable');
  });
  window.addEventListener('appinstalled',function(){
    window.hermesDeferredInstallPrompt=null;
    root.classList.remove('pwa-installable');
    root.classList.add('pwa-installed');
    dispatch('hermes:pwa-installed');
  });
  document.addEventListener('visibilitychange',function(){
    if(document.visibilityState==='visible'){
      syncMode();
      root.classList.add('pwa-resumed');
      window.setTimeout(function(){root.classList.remove('pwa-resumed');},1200);
    }
  });

  window.HermesPWA={
    isStandalone:isStandalone,
    syncMode:syncMode,
    syncViewportZoom:syncViewportZoom,
    launchAction:function(){
      try{return new URLSearchParams(window.location.search||'').get('action')||null;}catch(_){return null;}
    },
    promptInstall:function(){
      var prompt=window.hermesDeferredInstallPrompt;
      if(!prompt||typeof prompt['prompt']!=='function')return Promise.resolve({outcome:'unavailable'});
      window.hermesDeferredInstallPrompt=null;
      root.classList.remove('pwa-installable');
      prompt['prompt']();
      return Promise.resolve(prompt.userChoice).catch(function(){return {outcome:'dismissed'};});
    }
  };
})();
