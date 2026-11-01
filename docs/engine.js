/* Pure rules shared by the browser and Node tests. */
(function(root){
const norm=s=>String(s).normalize('NFKC').toLowerCase().replace(/ё/g,'е').replace(/[\s‐‑–—-]+/g,' ').trim();
const last=s=>[...norm(s)].reverse().find(c=>/[а-я]/.test(c)&&!'ьъы'.includes(c));
class Engine{
 constructor(data){this.data=data;this.index=new Map();for(const c of data){for(const a of [c.n,...c.a]){const k=norm(a);if(!this.index.has(k)||this.index.get(k).p<c.p)this.index.set(k,c)}}}
 eligible(state){const used=new Set(state.used);return this.data.filter(c=>c.bot&&!used.has(c.id)&&!c.a.some(a=>used.has(norm(a)))&&(!state.letter||norm(c.n).startsWith(state.letter))&&(state.mode!=='russia'||c.cc==='RU'))}
 move(text,state,random=Math.random){
  if(state.finished)throw Error('Игра завершена. Начни новое путешествие.');
  const key=norm(text),city=this.index.get(key);if(!city)throw Error('Не нашёл город. Проверь написание или загляни в атлас.');
  if(state.mode==='russia'&&city.cc!=='RU')throw Error('В этом режиме играем только в города России.');
  if(state.used.includes(city.id)||city.a.some(a=>state.used.includes(norm(a))))throw Error('Этот город уже был в маршруте. Назови другой.');
  if(state.letter&&!key.startsWith(state.letter))throw Error('Сейчас нужен город на «'+state.letter.toUpperCase()+'».');
  const next={...state,used:[...state.used,city.id,...city.a.map(norm)],letter:last(text),turns:state.turns+1};
  const choices=this.eligible(next).sort((a,b)=>b.p-a.p).slice(0,20);
  const reply=choices.length?choices[Math.floor(random()*choices.length)]:null;
  if(reply){next.used.push(reply.id,...reply.a.map(norm));next.letter=last(reply.n)}else next.finished=true;
  if(next.mode==='daily'&&next.turns>=10)next.finished=true;
  return{state:next,city:{...city,n:city.bot?city.n:text.trim()},reply};
 }
}
const api={norm,last,Engine};if(typeof module!=='undefined')module.exports=api;else root.CityRules=api;
})(globalThis);
