
function syncScroll(){
var h=document.documentElement;
var p=(h.scrollTop||document.body.scrollTop)/(h.scrollHeight-h.clientHeight)*100;
document.getElementById('progress').style.width=Math.min(p,100)+'%';
var bt=document.getElementById('back-top');
bt.classList.toggle('visible',(h.scrollTop||document.body.scrollTop)>300);
var sections=document.querySelectorAll('section[id]');
var links=document.querySelectorAll('#toc a');
/* Default the marker to the first section so the rail is never blank: with
   cur starting empty, no link carried .active until a section crossed the
   250px line, so the panel showed no position marker on load. */
var cur=sections.length?sections[0].id:'';
sections.forEach(function(s){
var t=s.getBoundingClientRect().top;
if(t<250) cur=s.id;
});
links.forEach(function(l){
l.classList.toggle('active',l.dataset.section===cur);
});
}
window.addEventListener('scroll',syncScroll,{passive:true});
syncScroll();
/* Mobile rail collapse. Desktop is untouched: every rule lives inside the
   <=860px media query, so the class is inert above the breakpoint. Without JS
   the markup stays expanded (aria-expanded="true"), which is the old
   behaviour, not a broken one. */
var _tocNav=document.getElementById('toc');
var _tocBtn=document.getElementById('toc-toggle');
function tocIsNarrow(){return window.matchMedia('(max-width:860px)').matches;}
function setToc(open){
if(!_tocNav||!_tocBtn)return;
_tocNav.classList.toggle('toc-collapsed',!open);
_tocBtn.setAttribute('aria-expanded',open?'true':'false');
}
if(_tocBtn){
setToc(!tocIsNarrow());
_tocBtn.addEventListener('click',function(){setToc(_tocNav.classList.contains('toc-collapsed'));});
/* Choosing a destination should reveal it, not leave the open rail covering it.
   The rail sits ABOVE the content, so collapsing it shifts the target up by the
   rail's height (~412px) — which cancels the browser's own anchor scroll, and
   would yank the reader if we collapsed after landing. So: close the rail,
   force the reflow, then navigate. A native fragment change (not
   scrollIntoView) keeps :target working. Desktop stays on the native path. */
Array.prototype.forEach.call(_tocNav.querySelectorAll('#toc-list a'),function(a){
a.addEventListener('click',function(e){
if(!tocIsNarrow())return;
var id=(a.getAttribute('href')||'').slice(1);
var el=id&&document.getElementById(id);
if(!el)return;
e.preventDefault();
setToc(false);
void _tocNav.offsetHeight;
if(location.hash==='#'+id){el.scrollIntoView();}else{location.hash='#'+id;}
});
});
}
function setView(m){
document.body.classList.toggle('exec-view',m==='exec');
document.getElementById('btn-full').classList.toggle('active',m==='full');
document.getElementById('btn-exec').classList.toggle('active',m==='exec');
document.querySelectorAll('.story-card').forEach(function(c){
var interactive=m==='exec';
c.setAttribute('role',interactive?'button':null);
c.setAttribute('tabindex',interactive?'0':null);
c.setAttribute('aria-expanded',interactive?(c.classList.contains('expanded')?'true':'false'):null);
});
}
document.addEventListener('keydown',function(e){
if(e.key==='Escape') setView('full');
});
function toggleCard(c){ if(!document.body.classList.contains('exec-view'))return; c.classList.toggle('expanded'); c.setAttribute('aria-expanded',c.classList.contains('expanded')?'true':'false'); }
document.querySelectorAll('.story-card').forEach(function(c){
c.addEventListener('click',function(e){
if(e.target.closest('a')) return;
toggleCard(this);
});
c.addEventListener('keydown',function(e){
if(e.target.closest('a')) return;
if(e.key==='Enter'||e.key===' '){ e.preventDefault(); toggleCard(this); }
});
});
document.querySelectorAll('#toc a').forEach(function(l){
l.setAttribute('role','navigation');
});
var _tocObs=new MutationObserver(function(){
document.querySelectorAll('#toc a.active').forEach(function(a){a.setAttribute('aria-current','location');});
document.querySelectorAll('#toc a:not(.active)').forEach(function(a){a.removeAttribute('aria-current');});
});
_tocObs.observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
/* Executive Summary threads: collapse toggle + mini-TOC scrollspy (progressive). */
document.querySelectorAll('.exec-thread').forEach(function(c){
var btn=c.querySelector('.exec-toggle');if(!btn)return;
var body=c.querySelector('.exec-body');var prev=c.querySelector('.exec-preview');
function setOpen(open){body.hidden=!open;if(prev)prev.hidden=open;btn.setAttribute('aria-expanded',open?'true':'false');btn.textContent=open?'Collapse':'Expand';}
btn.addEventListener('click',function(){setOpen(body.hidden);});
});
/* mini-TOC scrollspy (progressive enhancement): highlight the thread whose
   card top has just crossed the top threshold — mirrors the main rail pattern. */
var _excur=null;
function execScrollSpy(){var cur=null;document.querySelectorAll('.exec-thread').forEach(function(t){if(t.getBoundingClientRect().top<=150){cur=t.id;}});if(cur!==_excur){_excur=cur;document.querySelectorAll('.exec-toc-link').forEach(function(a){a.classList.toggle('active',a.dataset.threadTarget===cur);});}}
window.addEventListener('scroll',execScrollSpy,{passive:true});
execScrollSpy();
