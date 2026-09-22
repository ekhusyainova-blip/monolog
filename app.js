(function(){

  var DATA_URL = 'data.json';

  function el(id){ return document.getElementById(id); }

  function setTheme(t){
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('monolog_map_theme', t);
  }

  function toggleTheme(){
    var cur = document.documentElement.getAttribute('data-theme');
    setTheme(cur === 'dark' ? 'light' : 'dark');
  }

  (function(){
    var saved = localStorage.getItem('monolog_map_theme');
    if(saved) setTheme(saved);
    else if(window.matchMedia('(prefers-color-scheme: light)').matches) setTheme('light');
    else setTheme('dark');
  })();

  function renderWhere(data){
    el('whereContent').textContent = data.where || '—';
  }

  function renderTodo(data){
    var ol = el('todoContent');
    ol.innerHTML = '';
    var list = (data.todo || []).slice().sort(function(a,b){return (a.priority||99)-(b.priority||99);});
    list.forEach(function(item){
      var li = document.createElement('li');
      li.className = 'p' + (item.priority || 3);
      li.textContent = item.text || '';
      if(item.meta){
        var m = document.createElement('span');
        m.className = 'meta';
        m.textContent = item.meta;
        li.appendChild(m);
      }
      ol.appendChild(li);
    });
  }

  function metricClass(value){
    var v = String(value).toLowerCase();
    if(v === 'ok' || v === 'success' || v === 'готово') return 'ok';
    if(v === 'warning' || v === 'warn') return 'warn';
    if(v === 'bad' || v === 'critical' || v === 'fail') return 'bad';
    return '';
  }

  function renderMetrics(data){
    var box = el('metricsContent');
    box.innerHTML = '';
    (data.metrics || []).forEach(function(m){
      var d = document.createElement('div');
      d.className = 'metric';
      var k = document.createElement('div');
      k.className = 'k';
      k.textContent = m.key || '';
      var v = document.createElement('div');
      v.className = 'v ' + metricClass(m.value);
      v.textContent = String(m.value);
      d.appendChild(k);
      d.appendChild(v);
      if(m.note){
        var n = document.createElement('div');
        n.className = 'n';
        n.textContent = m.note;
        d.appendChild(n);
      }
      box.appendChild(d);
    });
  }

  function renderBlockers(data){
    var box = el('blockers');
    var content = el('blockersContent');
    var list = data.blockers || [];
    if(list.length === 0){
      box.classList.add('empty');
      content.textContent = 'Блокеров нет.';
      return;
    }
    box.classList.remove('empty');
    content.innerHTML = '';
    var ul = document.createElement('ul');
    ul.style.paddingLeft = '20px';
    list.forEach(function(b){
      var li = document.createElement('li');
      li.textContent = b;
      ul.appendChild(li);
    });
    content.appendChild(ul);
  }

  function renderHistory(data){
    var box = el('historyContent');
    box.innerHTML = '';
    var ul = document.createElement('ul');
    (data.history || []).forEach(function(h){
      var li = document.createElement('li');
      var when = document.createElement('span');
      when.className = 'when';
      when.textContent = h.when || '';
      li.appendChild(when);
      li.appendChild(document.createTextNode(h.text || ''));
      ul.appendChild(li);
    });
    box.appendChild(ul);
  }

  function renderUpdated(data){
    if(!data.updated){
      el('updated').textContent = '';
      return;
    }
    var d = new Date(data.updated);
    var s = isNaN(d.getTime()) ? data.updated : d.toLocaleString('ru-RU');
    el('updated').textContent = 'Обновлено: ' + s;
  }

  function render(data){
    renderWhere(data);
    renderTodo(data);
    renderMetrics(data);
    renderBlockers(data);
    renderHistory(data);
    renderUpdated(data);
  }

  async function load(){
    try{
      var r = await fetch(DATA_URL + '?t=' + Date.now(), {cache: 'no-store'});
      if(!r.ok) throw new Error('HTTP ' + r.status);
      var data = await r.json();
      render(data);
    }catch(e){
      el('whereContent').textContent = 'Не удалось загрузить data.json: ' + e.message;
    }
  }

  window.App = { toggleTheme: toggleTheme, load: load, render: render };
  load();
  setInterval(load, 60000);
})();