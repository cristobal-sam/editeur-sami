// Execute le vrai composant TSX ; seuls les hooks de temps/video sont fixes pour ce test sans navigateur.
import fs from 'node:fs';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const require=createRequire(new URL('../../../remotion/package.json',import.meta.url));
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const remotion=require('remotion'),{transformSync}=require('esbuild');
const src=fs.readFileSync(new URL('../../../remotion/src/graphics.tsx',import.meta.url),'utf8');
const {code}=transformSync(src,{loader:'tsx',format:'cjs'});
let time=0;
const module={exports:{}};
new Function('require','module','exports',code)(id=>id==='remotion'?{
  ...remotion,useCurrentFrame:()=>Math.round(time*30),useVideoConfig:()=>({width:1080,height:1920,fps:30})
}:require(id),module,module.exports);
const draw=(props,t)=>{
  time=t;
  const reel={style:{font:'Montserrat',highlight:'#7C3AED',stroke:'#000'},graphics:[{id:'test',kind:'chiffre',at:0,duration:4,props}]};
  return renderToStaticMarkup(React.createElement(module.exports.Graphics,{reel,t,url:p=>p})).replace(/<[^>]*>/g,'');
};
for(const t of [0,.2,.6,1.5])assert.equal(draw({value:3,from:100,count:false},t),'3');
assert.equal(draw({value:30,from:12},0),'12');
assert.equal(draw({value:30,from:12},1.5),'30');
assert.equal(draw({value:30},0),'0');
assert.equal(draw({value:30,from:-10},0),'-10');
console.log('8 verifications du vrai composant Chiffre reussies');
