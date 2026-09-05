"""Render the real chooser with delayed host data and cover refresh."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.verify_panel_layout_visual_46 import browser_session,close_browser,wait_eval,screenshot
root=Path(__file__).resolve().parents[1]
p=b=c=None
try:
 p,b,c=browser_session()
 c.call('Page.addScriptToEvaluateOnNewDocument',{'source':"""
 window.__pending=[];
 window.pywebview={api:new Proxy({plugins:()=>new Promise((resolve,reject)=>__pending.push({resolve,reject})),lexeditor_settings:async()=>({loadingTransitionMinimumSeconds:.1}),loading_quote:async()=>({quote:'Preparing your next adventure.'})},{get:(o,k)=>o[k]||(()=>Promise.resolve({}))})};
 addEventListener('load',()=>dispatchEvent(new Event('pywebviewready')));
 """})
 c.call('Page.navigate',{'url':(root/'ui/chooser.html').as_uri()})
 wait_eval(c,'window.__pending?.length===1',10)
 assert c.eval("!document.querySelector('#loading-screen').hidden && !document.querySelector('#games').textContent.includes('Loading plugins')")
 assert c.eval("document.querySelector('#loading-quote').textContent==='Preparing your next adventure.'")
 screenshot(c,'home-menu-loading.png')
 c.eval("window.__rows=[{id:'blank',name:'Blank',status:'ready',coverArt:{state:'ready',uri:'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyMCIgaGVpZ2h0PSIzMCI+PHJlY3Qgd2lkdGg9IjIwIiBoZWlnaHQ9IjMwIiBmaWxsPSJyZWQiLz48L3N2Zz4='}}];__pending.shift().resolve(__rows)")
 wait_eval(c,"document.querySelector('#loading-screen').hidden && !!document.querySelector('.game-cover')",10)
 c.eval("window.__cover=document.querySelector('.game-cover');__lexChooser.load()")
 wait_eval(c,'__pending.length===1',5)
 c.eval("__pending.shift().resolve([{...__rows[0],coverArt:{state:'loading'}}])")
 wait_eval(c,"document.querySelector('.hover-detail').textContent.includes('loading')",5)
 assert c.eval("document.querySelector('.game-cover')===__cover && !document.querySelector('#games').getAttribute('aria-busy').includes('true')")
 wait_eval(c,'__pending.length===1',5)
 c.eval("__pending.shift().reject(new Error('test host failure'))")
 wait_eval(c,"document.body.textContent.includes('Could not load games')",5)
 assert c.eval("document.querySelector('.game-cover')===__cover")
 print('PASS: existing loading overlay, decoded covers before reveal, retained cover during refresh/error, retry dialog')
finally:
 if p:close_browser(p,b,c)
