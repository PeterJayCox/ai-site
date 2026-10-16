
/* Appearance: three states, default = auto (follows the OS). Click cycles
   auto -> pin -> the other pin -> auto; Shift-click returns to auto. Pinned
   choice lives in `ai-theme2`; the legacy `ai-theme` key is discarded. */
(function(){var d=document.documentElement;
function sys(){try{return (window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches)?'light':'dark';}catch(e){return 'dark';}}
function saved(){try{var s=localStorage.getItem('ai-theme2');return (s==='light'||s==='dark')?s:null;}catch(e){return null;}}
function mode(){return saved()||'auto';}
function save(m){try{if(m==='auto'){localStorage.removeItem('ai-theme2');}else{localStorage.setItem('ai-theme2',m);}}catch(e){}}
function label(m){var b=document.querySelector('.theme-toggle');if(!b){return;}
var t={auto:'Appearance: auto \u2014 follows your system ('+sys()+'). Click to cycle auto \u2192 light \u2192 dark.',
light:'Appearance: light (pinned). Shift-click to follow your system again.',
dark:'Appearance: dark (pinned). Shift-click to follow your system again.'}[m];
if(t){b.setAttribute('title',t);b.setAttribute('aria-label',t);}}
function apply(){var m=mode();d.setAttribute('data-theme',m==='auto'?sys():m);d.setAttribute('data-theme-mode',m);label(m);}
/* Cycle visits all three states, always flipping away from what is on screen
   first: auto -> a pin (opposite of the current look) -> the other pin -> auto. */
function cycle(ev){var m=mode();
if(ev&&ev.shiftKey){save('auto');}
else if(m==='auto'){save(sys()==='dark'?'light':'dark');}
else if(m===sys()){save('auto');}
else{save(m==='light'?'dark':'light');}
apply();}
function followSystem(){if(!saved()){apply();}}
try{localStorage.removeItem('ai-theme');}catch(e){}
window.__aiSysTheme=sys;
window.__aiTheme={cycle:cycle,apply:apply,mode:mode,setAuto:function(){save('auto');apply();}};
apply();
try{var mq=window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)');
if(mq&&mq.addEventListener){mq.addEventListener('change',followSystem);}}catch(e){}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',apply);}
})();
